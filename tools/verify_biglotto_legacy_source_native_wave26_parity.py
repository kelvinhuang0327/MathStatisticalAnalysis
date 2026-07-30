#!/usr/bin/env python3
"""Verify wave-26 ports against frozen optimizer and Unified AST methods."""

from __future__ import annotations

import argparse
import ast
import contextlib
import hashlib
import io
import json
import math
import random
import subprocess
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path
from typing import Any, cast

from lottolab.application.legacy_frozen_unified_core import (
    frozen_deviation_ticket,
    frozen_hot_cold_ticket,
    frozen_markov_ticket,
    frozen_statistical_ticket,
    frozen_trend_ticket,
)
from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.application.legacy_source_native_portfolios_wave26 import (
    CES_METHOD_ID,
    DMS_METHOD_ID,
    FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE26_METHOD,
    GREEDY_METHOD_ID,
    MWSC_METHOD_ID,
    PCE_METHOD_ID,
    SMH_CLOSED_METHOD_ID,
    SMH_CLOSED_REASON_CODE,
    SOURCE_NATIVE_WAVE26_PROTOCOL,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE26_METHOD,
    SUPPORTED_SOURCE_NATIVE_WAVE26_METHODS,
    LegacySourceNativeWave26Request,
    LegacySourceNativeWave26SourceError,
    generate_legacy_source_native_wave26_portfolio,
)
from lottolab.infrastructure.replay_backed_batch_import import (
    load_pinned_biglotto_history,
)

FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
PARITY_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_SOURCE_NATIVE_WAVE26_PARITY_V1"
)
_BASE_METHOD_ID = "lottery_api/models/biglotto_3bet_optimizer.py"
_UNIFIED_METHOD_ID = "lottery_api/models/unified_predictor.py"
_NEGATIVE_SELECTOR_ID = "tools/negative_selector.py"
_HISTORY_COUNTS = (*range(1, 31), 50, 150, 2148)
_CLASS_BY_METHOD = {
    CES_METHOD_ID: ("CESOptimizer", "predict_3bets_ces"),
    DMS_METHOD_ID: ("DMSOptimizer", "predict_3bets_dms"),
    GREEDY_METHOD_ID: (
        "GreedyConstraintOptimizer",
        "predict_3bets_greedy",
    ),
    MWSC_METHOD_ID: ("MWSCOptimizer", "predict_3bets_mwsc"),
    PCE_METHOD_ID: ("PCEOptimizer", "predict_3bets_pce"),
}
_UNIFIED_METHODS = {
    "frequency_predict",
    "_adaptive_decay_rate",
    "bayesian_predict",
    "_adaptive_bayesian_weights",
    "_calculate_stability",
    "zone_balance_predict",
    "_dynamic_zone_partition",
    "_calculate_zone_quality",
}


class ParityError(ValueError):
    """Frozen source identity or port output differs."""


class _NumpyReference:
    @staticmethod
    def exp(value: float) -> float:
        return math.exp(value)

    @staticmethod
    def mean(values: list[float] | list[int]) -> float:
        return sum(values) / len(values)

    @staticmethod
    def std(values: list[float] | list[int]) -> float:
        mean = _NumpyReference.mean(values)
        return math.sqrt(
            sum((value - mean) ** 2 for value in values) / len(values)
        )


def _noop(*_args: object, **_kwargs: object) -> None:
    return None


def _predict_special(*_args: object, **_kwargs: object) -> None:
    return None


def _empty_data_range(_history: object) -> dict[str, object]:
    return {}


def _identity_constraints(
    _self: object,
    _history: object,
    numbers: list[int],
    _rules: object,
) -> list[int]:
    return numbers


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _git(frozen_root: Path, *arguments: str) -> bytes:
    completed = subprocess.run(
        ("git", "-C", str(frozen_root), *arguments),
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        raise ParityError("cannot read frozen source artifact")
    return completed.stdout


def _class_node(
    source_text: str,
    *,
    class_name: str,
    source_identity: str,
) -> ast.ClassDef:
    tree = ast.parse(source_text, filename=source_identity)
    matches = [
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == class_name
    ]
    if len(matches) != 1:
        raise ParityError(f"frozen class changed: {class_name}")
    return matches[0]


def _assignments(
    source_text: str,
    *,
    names: set[str],
    source_identity: str,
) -> list[ast.stmt]:
    tree = ast.parse(source_text, filename=source_identity)
    result: list[ast.stmt] = []
    found: set[str] = set()
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        targets = {
            target.id
            for target in node.targets
            if isinstance(target, ast.Name)
        }
        if targets & names:
            result.append(node)
            found.update(targets & names)
    if found != names:
        raise ParityError("frozen module assignments changed")
    return result


def _unified_reference_node(source_text: str) -> ast.ClassDef:
    source_class = _class_node(
        source_text,
        class_name="UnifiedPredictionEngine",
        source_identity=f"{FROZEN_SOURCE_COMMIT}:{_UNIFIED_METHOD_ID}",
    )
    method_nodes = [
        node
        for node in source_class.body
        if isinstance(node, ast.FunctionDef)
        and node.name in _UNIFIED_METHODS
    ]
    if {method.name for method in method_nodes} != _UNIFIED_METHODS:
        raise ParityError("frozen Unified selection methods changed")
    methods = cast(list[ast.stmt], method_nodes)
    return ast.ClassDef(
        name="FrozenUnifiedSelectionReference",
        bases=[],
        keywords=[],
        body=methods,
        decorator_list=[],
    )


def _qualified_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _qualified_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return None


def _verify_smh_disposition(source_text: str) -> dict[str, object]:
    source_class = _class_node(
        source_text,
        class_name="SMHOptimizer",
        source_identity=f"{FROZEN_SOURCE_COMMIT}:{SMH_CLOSED_METHOD_ID}",
    )
    methods = [
        node
        for node in source_class.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "predict_3bets_smh"
    ]
    if len(methods) != 1:
        raise ParityError("frozen SMH entrypoint changed")
    method = methods[0]
    calls = [
        name
        for node in ast.walk(method)
        if isinstance(node, ast.Call)
        for name in [_qualified_name(node.func)]
        if name is not None
    ]
    imports_random = any(
        isinstance(node, ast.Import)
        and any(alias.name == "random" for alias in node.names)
        for node in ast.walk(method)
    )
    random_sample_count = calls.count("random.sample")
    state_binding_calls = {
        "random.seed",
        "random.setstate",
        "random.Random",
    } & set(calls)
    if (
        not imports_random
        or random_sample_count != 2
        or state_binding_calls
        or [argument.arg for argument in method.args.args]
        != ["self", "history", "rules", "use_kill"]
    ):
        raise ParityError("frozen SMH random-state facts changed")
    return {
        "legacy_method_id": SMH_CLOSED_METHOD_ID,
        "random_sample_call_count": random_sample_count,
        "random_state_binding_calls": [],
        "reason_code": SMH_CLOSED_REASON_CODE,
        "source_sha256": (
            SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE26_METHOD[
                SMH_CLOSED_METHOD_ID
            ]
        ),
        "status": "CLOSED_UNEXECUTABLE",
    }


def _compile_frozen_classes(
    *,
    source_by_method: dict[str, str],
    base_source: str,
    negative_selector_source: str,
    unified_source: str,
) -> dict[str, type[Any]]:
    body: list[ast.stmt] = [
        *_assignments(
            base_source,
            names={"PREDICTION_METHODS", "BET_SLICES"},
            source_identity=f"{FROZEN_SOURCE_COMMIT}:{_BASE_METHOD_ID}",
        ),
        _class_node(
            negative_selector_source,
            class_name="NegativeSelector",
            source_identity=(
                f"{FROZEN_SOURCE_COMMIT}:{_NEGATIVE_SELECTOR_ID}"
            ),
        ),
        _class_node(
            base_source,
            class_name="BigLotto3BetOptimizer",
            source_identity=f"{FROZEN_SOURCE_COMMIT}:{_BASE_METHOD_ID}",
        ),
        _unified_reference_node(unified_source),
    ]
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE26_METHODS:
        class_name, _method_name = _CLASS_BY_METHOD[method_id]
        body.append(
            _class_node(
                source_by_method[method_id],
                class_name=class_name,
                source_identity=f"{FROZEN_SOURCE_COMMIT}:{method_id}",
            )
        )
    module = ast.Module(body=body, type_ignores=[])
    ast.fix_missing_locations(module)
    namespace: dict[str, Any] = {
        "Any": Any,
        "Counter": Counter,
        "Dict": dict,
        "List": list,
        "Optional": object,
        "Tuple": tuple,
        "UnifiedPredictionEngine": object,
        "__builtins__": __builtins__,
        "combinations": combinations,
        "defaultdict": defaultdict,
        "get_data_range_info": _empty_data_range,
        "log_data_range": _noop,
        "math": math,
        "np": _NumpyReference,
        "predict_special_number": _predict_special,
        "random": random,
    }
    exec(
        compile(
            module,
            f"{FROZEN_SOURCE_COMMIT}:wave26-classes",
            "exec",
        ),
        namespace,
    )
    reference = cast(
        type[Any], namespace["FrozenUnifiedSelectionReference"]
    )
    reference.filter_by_global_constraints = _identity_constraints
    names = {
        "NegativeSelector",
        "FrozenUnifiedSelectionReference",
        *(
            class_name
            for class_name, _method_name in _CLASS_BY_METHOD.values()
        ),
    }
    return {name: cast(type[Any], namespace[name]) for name in names}


class _UnifiedAdapter:
    def __init__(self, reference_class: type[Any]) -> None:
        self._reference = object.__new__(reference_class)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._reference, name)

    @staticmethod
    def _history(
        history: list[dict[str, object]],
    ) -> tuple[LegacyHistoryDraw, ...]:
        return tuple(
            LegacyHistoryDraw(
                draw_number=cast(str, row["draw"]),
                numbers=cast(
                    tuple[int, int, int, int, int, int],
                    tuple(cast(list[int], row["numbers"])),
                ),
            )
            for row in history
        )

    @staticmethod
    def _result(numbers: tuple[int, ...]) -> dict[str, object]:
        return {"confidence": 0.5, "numbers": list(numbers)}

    def statistical_predict(
        self,
        history: list[dict[str, object]],
        _rules: object,
    ) -> dict[str, object]:
        return self._result(
            frozen_statistical_ticket(self._history(history))[0]
        )

    def deviation_predict(
        self,
        history: list[dict[str, object]],
        _rules: object,
    ) -> dict[str, object]:
        return self._result(
            frozen_deviation_ticket(self._history(history))
        )

    def markov_predict(
        self,
        history: list[dict[str, object]],
        _rules: object,
    ) -> dict[str, object]:
        return self._result(
            frozen_markov_ticket(self._history(history))[0]
        )

    def trend_predict(
        self,
        history: list[dict[str, object]],
        _rules: object,
    ) -> dict[str, object]:
        return self._result(
            frozen_trend_ticket(self._history(history))
        )

    def hot_cold_mix_predict(
        self,
        history: list[dict[str, object]],
        _rules: object,
    ) -> dict[str, object]:
        return self._result(
            frozen_hot_cold_ticket(self._history(history))
        )


def _source_history(
    history: tuple[LegacyHistoryDraw, ...],
) -> list[dict[str, object]]:
    return [
        {
            "date": f"{index:08d}",
            "draw": draw.draw_number,
            "numbers": list(draw.numbers),
        }
        for index, draw in enumerate(history)
    ]


def _source_instance(
    *,
    method_id: str,
    classes: dict[str, type[Any]],
) -> Any:
    class_name, _method_name = _CLASS_BY_METHOD[method_id]
    instance = object.__new__(classes[class_name])
    instance.engine = _UnifiedAdapter(
        classes["FrozenUnifiedSelectionReference"]
    )
    selector = object.__new__(classes["NegativeSelector"])
    selector.rules = {"maxNumber": 49}
    instance.selector = selector
    instance.verbose = False
    return instance


def _compare_case(
    *,
    method_id: str,
    classes: dict[str, type[Any]],
    history: tuple[LegacyHistoryDraw, ...],
    target_draw_number: str,
) -> dict[str, object]:
    instance = _source_instance(method_id=method_id, classes=classes)
    _class_name, method_name = _CLASS_BY_METHOD[method_id]
    source_history = _source_history(history)
    rules = {
        "hasSpecialNumber": False,
        "maxNumber": 49,
        "minNumber": 1,
        "name": "BIG_LOTTO",
        "pickCount": 6,
    }
    source_exception: str | None = None
    source_result: dict[str, object] | None = None
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            source_result = cast(
                dict[str, object],
                getattr(instance, method_name)(source_history, rules),
            )
    except Exception as exc:
        source_exception = type(exc).__name__
    source_tickets: list[list[int]] = []
    source_candidates: list[int] | None = None
    source_top_methods: list[str] | None = None
    if source_result is not None:
        source_tickets = [
            cast(list[int], bet["numbers"])
            for candidate in cast(list[object], source_result["bets"])
            if isinstance(candidate, dict)
            for bet in [cast(dict[str, object], candidate)]
        ]
        candidates = source_result.get("candidates")
        if isinstance(candidates, list):
            source_candidates = cast(list[int], candidates)
        top_methods = source_result.get("top_methods")
        if isinstance(top_methods, list):
            source_top_methods = cast(list[str], top_methods)
    source_valid = (
        source_exception is None
        and len(source_tickets) == 3
        and all(
            len(ticket) == 6
            and len(set(ticket)) == 6
            and all(1 <= number <= 49 for number in ticket)
            for ticket in source_tickets
        )
    )
    request = LegacySourceNativeWave26Request(
        legacy_method_id=method_id,
        target_draw_number=target_draw_number,
        history=history,
    )
    try:
        port = generate_legacy_source_native_wave26_portfolio(request)
    except LegacySourceNativeWave26SourceError as exc:
        if source_valid:
            raise ParityError(
                f"port closed valid source for {method_id} "
                f"at {target_draw_number}"
            ) from exc
        return {
            "candidate_k": (
                len(source_candidates)
                if source_candidates is not None
                else None
            ),
            "closure_reason": exc.reason_code,
            "history_draw_count": len(history),
            "legacy_method_id": method_id,
            "source_exception": source_exception,
            "status": "CLOSED_PARITY",
        }
    if not source_valid:
        raise ParityError(
            f"port accepted invalid source for {method_id} "
            f"at {target_draw_number}"
        )
    port_tickets = [list(ticket) for ticket in port.tickets]
    if source_tickets != port_tickets:
        raise ParityError(
            f"ticket parity failed for {method_id} at {target_draw_number}: "
            f"{source_tickets!r} != {port_tickets!r}"
        )
    if (
        source_candidates is not None
        and source_candidates != list(port.metadata.candidate_pool)
    ):
        raise ParityError(
            f"candidate parity failed for {method_id} at "
            f"{target_draw_number}"
        )
    if source_top_methods is not None and source_top_methods != list(
        port.metadata.selected_methods
    ):
        raise ParityError(
            f"selected-method parity failed for {method_id} at "
            f"{target_draw_number}"
        )
    if method_id in (
        CES_METHOD_ID,
        GREEDY_METHOD_ID,
        MWSC_METHOD_ID,
        PCE_METHOD_ID,
    ):
        source_kill = tuple(
            instance.selector.predict_kill_numbers(
                count=10,
                history=source_history,
            )
        )
        if source_kill != port.metadata.kill_numbers:
            raise ParityError(
                f"kill parity failed for {method_id} at "
                f"{target_draw_number}"
            )
    return {
        "candidate_k": port.metadata.candidate_pool_size,
        "history_draw_count": len(history),
        "legacy_method_id": method_id,
        "native_duplicate_ticket_count": (
            port.metadata.native_duplicate_ticket_count
        ),
        "native_ticket_count": len(port_tickets),
        "selected_methods": list(port.metadata.selected_methods),
        "status": "OK_PARITY",
        "ticket_sha256": hashlib.sha256(
            _canonical_bytes(port_tickets)
        ).hexdigest(),
    }


def verify_parity(
    *,
    frozen_root: Path,
    database: Path,
    expected_database_sha256: str,
) -> dict[str, object]:
    pinned = load_pinned_biglotto_history(
        database=database,
        expected_database_sha256=expected_database_sha256,
    )
    all_history = tuple(
        LegacyHistoryDraw(
            draw_number=draw.draw_number,
            numbers=draw.numbers,
        )
        for draw in pinned.draws
    )
    source_artifacts: list[dict[str, object]] = []
    source_by_method: dict[str, str] = {}
    for method_id in (
        *SUPPORTED_SOURCE_NATIVE_WAVE26_METHODS,
        SMH_CLOSED_METHOD_ID,
    ):
        raw = _git(
            frozen_root,
            "show",
            f"{FROZEN_SOURCE_COMMIT}:{method_id}",
        )
        if hashlib.sha256(raw).hexdigest() != (
            SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE26_METHOD[method_id]
        ):
            raise ParityError("frozen source SHA changed")
        source_by_method[method_id] = raw.decode("utf-8")
        source_artifacts.append(
            {
                "path": method_id,
                "source_blob_id": _git(
                    frozen_root,
                    "rev-parse",
                    f"{FROZEN_SOURCE_COMMIT}:{method_id}",
                )
                .decode("utf-8")
                .strip(),
                "source_byte_size": len(raw),
                "source_sha256": hashlib.sha256(raw).hexdigest(),
            }
        )
    support_artifacts: dict[str, dict[str, object]] = {}
    support_source: dict[str, str] = {}
    for method_id in (
        *SUPPORTED_SOURCE_NATIVE_WAVE26_METHODS,
        SMH_CLOSED_METHOD_ID,
    ):
        for path, expected_sha256 in (
            FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE26_METHOD[
                method_id
            ]
        ):
            raw = _git(
                frozen_root,
                "show",
                f"{FROZEN_SOURCE_COMMIT}:{path}",
            )
            if hashlib.sha256(raw).hexdigest() != expected_sha256:
                raise ParityError(
                    f"frozen support SHA changed: {path}"
                )
            support_source[path] = raw.decode("utf-8")
            support_artifacts[path] = {
                "path": path,
                "source_blob_id": _git(
                    frozen_root,
                    "rev-parse",
                    f"{FROZEN_SOURCE_COMMIT}:{path}",
                )
                .decode("utf-8")
                .strip(),
                "source_byte_size": len(raw),
                "source_sha256": expected_sha256,
            }
    classes = _compile_frozen_classes(
        source_by_method=source_by_method,
        base_source=support_source[_BASE_METHOD_ID],
        negative_selector_source=support_source[_NEGATIVE_SELECTOR_ID],
        unified_source=support_source[_UNIFIED_METHOD_ID],
    )
    static_dispositions = [
        _verify_smh_disposition(
            source_by_method[SMH_CLOSED_METHOD_ID]
        )
    ]
    cases: list[dict[str, object]] = []
    for history_count in _HISTORY_COUNTS:
        history = all_history[:history_count]
        target = pinned.draws[history_count]
        for method_id in SUPPORTED_SOURCE_NATIVE_WAVE26_METHODS:
            cases.append(
                _compare_case(
                    method_id=method_id,
                    classes=classes,
                    history=history,
                    target_draw_number=target.draw_number,
                )
            )
    return {
        "case_count": len(cases),
        "cases": cases,
        "database_sha256": pinned.database_sha256_before,
        "execution_mode": (
            "FROZEN_AST_CLASSES_WITH_FROZEN_AST_UNIFIED_SELECTION_METHODS"
        ),
        "frozen_source_commit": FROZEN_SOURCE_COMMIT,
        "parity_schema_version": PARITY_SCHEMA_VERSION,
        "port_protocol": SOURCE_NATIVE_WAVE26_PROTOCOL,
        "source_artifacts": source_artifacts,
        "static_dispositions": static_dispositions,
        "status": "PASS",
        "support_artifacts": [
            support_artifacts[path]
            for path in sorted(support_artifacts)
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--legacy-repository", required=True, type=Path)
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--expected-database-sha256", required=True)
    parser.add_argument("--output-file", required=True, type=Path)
    args = parser.parse_args()
    report = verify_parity(
        frozen_root=args.legacy_repository,
        database=args.database,
        expected_database_sha256=args.expected_database_sha256,
    )
    payload = _canonical_bytes(report) + b"\n"
    if args.output_file.exists():
        raise ParityError("refusing to overwrite parity output")
    args.output_file.parent.mkdir(parents=True, exist_ok=True)
    args.output_file.write_bytes(payload)
    print(
        json.dumps(
            {
                "case_count": report["case_count"],
                "output_file": str(args.output_file),
                "parity_sha256": hashlib.sha256(payload).hexdigest(),
                "status": report["status"],
            },
            separators=(",", ":"),
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
