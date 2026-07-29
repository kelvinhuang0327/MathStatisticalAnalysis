#!/usr/bin/env python3
"""Verify wave-25 ports against frozen TME/cooccurrence/zonal classes."""

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
    FrozenUnifiedTickets,
    generate_frozen_unified_tickets,
)
from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.application.legacy_source_native_portfolios_wave25 import (
    CAG_METHOD_ID,
    CLUSTER_COVER_METHOD_ID,
    FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE25_METHOD,
    SOURCE_NATIVE_WAVE25_PROTOCOL,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE25_METHOD,
    SUPPORTED_SOURCE_NATIVE_WAVE25_METHODS,
    TME_OPTIMIZER_METHOD_ID,
    ZDP_METHOD_ID,
    LegacySourceNativeWave25Request,
    LegacySourceNativeWave25SourceError,
    generate_legacy_source_native_wave25_portfolio,
)
from lottolab.infrastructure.replay_backed_batch_import import (
    load_pinned_biglotto_history,
)

FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
PARITY_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_SOURCE_NATIVE_WAVE25_PARITY_V1"
)
_FULL_CLOSED_HISTORY_COUNTS = (
    2,
    3,
    4,
    5,
    6,
    7,
    8,
    9,
    10,
    11,
    12,
    13,
    14,
    15,
    16,
    17,
    18,
    19,
    20,
    21,
    22,
    23,
    24,
    26,
    27,
    28,
    29,
    33,
    40,
    43,
    63,
    81,
    94,
    96,
    97,
    105,
    110,
    122,
    123,
    126,
    133,
    151,
    157,
    169,
    202,
    240,
    261,
    271,
    282,
    298,
    321,
    331,
    337,
    342,
    357,
    359,
    374,
    375,
    406,
    423,
    487,
    488,
    511,
    563,
    565,
    672,
    677,
    704,
    924,
    945,
    966,
    985,
    1035,
    1087,
    1138,
    1243,
    1250,
    1272,
    1285,
    1286,
    1291,
    1295,
    1315,
    1316,
    1331,
    1334,
    1336,
    1338,
    1341,
    1345,
    1350,
    1362,
    1371,
    1374,
    1376,
    1377,
    1378,
    1414,
    1415,
    1416,
    1430,
    1431,
    1457,
    1515,
    1517,
    1733,
    1734,
    1737,
    1762,
    1772,
    1773,
    1803,
    1832,
    2074,
    2083,
    2096,
    2114,
    2115,
    2119,
    2127,
    2128,
    2129,
    2131,
    2134,
    2135,
    2137,
    2140,
)
_HISTORY_COUNTS = tuple(
    sorted(
        {
            *range(1, 31),
            50,
            150,
            2148,
            *_FULL_CLOSED_HISTORY_COUNTS,
        }
    )
)
_BASE_METHOD_ID = "lottery_api/models/biglotto_3bet_optimizer.py"
_CLASS_BY_METHOD = {
    TME_OPTIMIZER_METHOD_ID: (
        "BigLottoTMEOptimizer",
        "predict_4bets",
    ),
    CAG_METHOD_ID: ("CAGOptimizer", "predict_3bets_cag"),
    CLUSTER_COVER_METHOD_ID: (
        "ClusterCoverOptimizer",
        "predict_3bets_cluster_cover",
    ),
    ZDP_METHOD_ID: ("ZDPOptimizer", "predict_3bets_zdp"),
}


class ParityError(ValueError):
    """Frozen source identity or port output differs."""


class _UnifiedAdapter:
    def __init__(self, unified: FrozenUnifiedTickets) -> None:
        self.unified = unified

    @staticmethod
    def _result(numbers: tuple[int, ...]) -> dict[str, object]:
        return {"confidence": 0.5, "numbers": list(numbers)}

    def statistical_predict(
        self,
        _history: object,
        _rules: object,
    ) -> dict[str, object]:
        return self._result(self.unified.statistical)

    def deviation_predict(
        self,
        _history: object,
        _rules: object,
    ) -> dict[str, object]:
        return self._result(self.unified.deviation)

    def markov_predict(
        self,
        _history: object,
        _rules: object,
    ) -> dict[str, object]:
        return self._result(self.unified.markov)

    def hot_cold_mix_predict(
        self,
        _history: object,
        _rules: object,
    ) -> dict[str, object]:
        return self._result(self.unified.hot_cold)


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


def _compile_frozen_classes(
    *,
    source_by_method: dict[str, str],
    base_source: str,
    negative_selector_source: str,
) -> dict[str, type[Any]]:
    body: list[ast.stmt] = [
        *_assignments(
            base_source,
            names={"PREDICTION_METHODS", "BET_SLICES"},
            source_identity=f"{FROZEN_SOURCE_COMMIT}:{_BASE_METHOD_ID}",
        ),
        *_assignments(
            source_by_method[TME_OPTIMIZER_METHOD_ID],
            names={"TME_METHODS_3BET", "TME_METHODS_4BET"},
            source_identity=(
                f"{FROZEN_SOURCE_COMMIT}:{TME_OPTIMIZER_METHOD_ID}"
            ),
        ),
        _class_node(
            negative_selector_source,
            class_name="NegativeSelector",
            source_identity=(
                f"{FROZEN_SOURCE_COMMIT}:tools/negative_selector.py"
            ),
        ),
        _class_node(
            base_source,
            class_name="BigLotto3BetOptimizer",
            source_identity=f"{FROZEN_SOURCE_COMMIT}:{_BASE_METHOD_ID}",
        ),
    ]
    for method_id in (
        TME_OPTIMIZER_METHOD_ID,
        CAG_METHOD_ID,
        CLUSTER_COVER_METHOD_ID,
        ZDP_METHOD_ID,
    ):
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
        "Counter": Counter,
        "Dict": dict,
        "List": list,
        "Optional": object,
        "UnifiedPredictionEngine": object,
        "__builtins__": __builtins__,
        "combinations": combinations,
        "defaultdict": defaultdict,
        "math": math,
        "random": random,
    }
    exec(
        compile(
            module,
            f"{FROZEN_SOURCE_COMMIT}:wave25-classes",
            "exec",
        ),
        namespace,
    )
    names = {
        "NegativeSelector",
        *(
            class_name
            for class_name, _method_name in _CLASS_BY_METHOD.values()
        ),
    }
    return {name: cast(type[Any], namespace[name]) for name in names}


def _source_instance(
    *,
    method_id: str,
    classes: dict[str, type[Any]],
    unified: FrozenUnifiedTickets,
) -> Any:
    class_name, _method_name = _CLASS_BY_METHOD[method_id]
    instance = object.__new__(classes[class_name])
    instance.engine = _UnifiedAdapter(unified)
    instance.verbose = False
    selector_class = classes["NegativeSelector"]
    selector = object.__new__(selector_class)
    selector.rules = {"maxNumber": 49}
    instance.selector = selector
    return instance


def _source_history(
    history: tuple[LegacyHistoryDraw, ...],
) -> list[dict[str, object]]:
    return [
        {
            "draw": draw.draw_number,
            "numbers": list(draw.numbers),
        }
        for draw in history
    ]


def _compare_case(
    *,
    method_id: str,
    classes: dict[str, type[Any]],
    history: tuple[LegacyHistoryDraw, ...],
    target_draw_number: str,
    unified: FrozenUnifiedTickets,
) -> dict[str, object]:
    instance = _source_instance(
        method_id=method_id,
        classes=classes,
        unified=unified,
    )
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
                getattr(instance, method_name)(
                    source_history,
                    rules,
                ),
            )
    except Exception as exc:  # Frozen wrappers intentionally catch broadly.
        source_exception = type(exc).__name__
    source_tickets: list[list[int]] = []
    source_candidates: list[int] | None = None
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
    source_valid = (
        source_exception is None
        and bool(source_tickets)
        and all(
            len(ticket) == 6
            and len(set(ticket)) == 6
            and all(1 <= number <= 49 for number in ticket)
            for ticket in source_tickets
        )
    )
    request = LegacySourceNativeWave25Request(
        legacy_method_id=method_id,
        target_draw_number=target_draw_number,
        history=history,
    )
    try:
        port = generate_legacy_source_native_wave25_portfolio(request)
    except LegacySourceNativeWave25SourceError as exc:
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
            f"ticket parity failed for {method_id} at {target_draw_number}"
        )
    if (
        source_candidates is not None
        and source_candidates != list(port.metadata.candidate_pool)
    ):
        raise ParityError(
            f"candidate parity failed for {method_id} at {target_draw_number}"
        )
    if method_id != TME_OPTIMIZER_METHOD_ID:
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
        "markov_order": port.metadata.markov_order,
        "native_duplicate_ticket_count": (
            port.metadata.native_duplicate_ticket_count
        ),
        "native_ticket_count": len(port_tickets),
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
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE25_METHODS:
        raw = _git(
            frozen_root,
            "show",
            f"{FROZEN_SOURCE_COMMIT}:{method_id}",
        )
        if hashlib.sha256(raw).hexdigest() != (
            SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE25_METHOD[method_id]
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
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE25_METHODS:
        for path, expected_sha256 in (
            FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE25_METHOD[
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
        negative_selector_source=support_source[
            "tools/negative_selector.py"
        ],
    )
    cases: list[dict[str, object]] = []
    for count in _HISTORY_COUNTS:
        history = all_history[:count]
        unified = generate_frozen_unified_tickets(history)
        cases.extend(
            _compare_case(
                method_id=method_id,
                classes=classes,
                history=history,
                target_draw_number=f"parity-{method_id}-{count}",
                unified=unified,
            )
            for method_id in SUPPORTED_SOURCE_NATIVE_WAVE25_METHODS
        )
    return {
        "case_count": len(cases),
        "cases": cases,
        "database_sha256": pinned.database_sha256_before,
        "execution_mode": (
            "AST_COMPILE_FROZEN_TME_CAG_CLUSTER_COVER_ZDP_AND_BASE_"
            "CLASSES_WITH_WAVE23_PARITY_BACKED_UNIFIED_OUTPUTS"
        ),
        "frozen_source_commit": FROZEN_SOURCE_COMMIT,
        "parity_schema_version": PARITY_SCHEMA_VERSION,
        "port_protocol": SOURCE_NATIVE_WAVE25_PROTOCOL,
        "source_artifacts": source_artifacts,
        "status": "PASS",
        "support_artifacts": [
            support_artifacts[path] for path in sorted(support_artifacts)
        ],
        "upstream_unified_parity_evidence_sha256": (
            "8064df37f44f695699e87071a4ffe2cb7a816405862f73d37fa14e038f73edd5"
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--legacy-repository",
        required=True,
        type=Path,
    )
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument(
        "--expected-database-sha256",
        required=True,
    )
    parser.add_argument("--output-file", required=True, type=Path)
    args = parser.parse_args()
    if args.output_file.exists():
        raise SystemExit(
            f"refusing to overwrite existing output: {args.output_file}"
        )
    result = verify_parity(
        frozen_root=args.legacy_repository,
        database=args.database,
        expected_database_sha256=args.expected_database_sha256,
    )
    payload = _canonical_bytes(result) + b"\n"
    args.output_file.parent.mkdir(parents=True, exist_ok=True)
    args.output_file.write_bytes(payload)
    print(
        json.dumps(
            {
                "case_count": result["case_count"],
                "output_file": str(args.output_file),
                "parity_sha256": hashlib.sha256(payload).hexdigest(),
                "status": result["status"],
            },
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
