"""Verify wave-6 ports against functions executed from frozen Git bytes."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from types import CodeType, ModuleType, SimpleNamespace
from typing import Any, cast

from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.application.legacy_source_native_portfolios_wave6 import (
    COMPARE_RANDOM_METHOD_ID,
    ECHO_PHASE2_METHOD_ID,
    HOT_STOP_REBOUND_METHOD_ID,
    SBP_RANDOM_METHOD_ID,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE6_METHOD,
    LegacySourceNativeWave6Request,
    generate_legacy_source_native_wave6_portfolio,
)
from lottolab.infrastructure.replay_backed_batch_import import (
    load_pinned_biglotto_history,
)

FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
PARITY_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_SOURCE_NATIVE_WAVE6_FROZEN_PARITY_V1"
)
SOURCE_BLOB_BY_METHOD = {
    ECHO_PHASE2_METHOD_ID: (
        "ce910e3f3fd29929a4dea7eef3a2a439bb0570c9"
    ),
    HOT_STOP_REBOUND_METHOD_ID: (
        "b3758b5c855fe42bae5d9a9de5b66b8079755ba7"
    ),
    COMPARE_RANDOM_METHOD_ID: (
        "b02ec11f4b3ecde5eb258878bdda7cc2da1586e2"
    ),
    SBP_RANDOM_METHOD_ID: (
        "98660baa5fcc230edc3a145cc962f3558e30bb26"
    ),
}
SOURCE_BYTE_SIZE_BY_METHOD = {
    ECHO_PHASE2_METHOD_ID: 9156,
    HOT_STOP_REBOUND_METHOD_ID: 12217,
    COMPARE_RANDOM_METHOD_ID: 2189,
    SBP_RANDOM_METHOD_ID: 1611,
}
DEPENDENCY_SOURCES = {
    "tools/predict_biglotto_echo_2bet.py": {
        "source_blob_id": (
            "26b6b9c1f0f15e625934896347368dd815b0e6a0"
        ),
        "source_byte_size": 10654,
        "source_sha256": (
            "59c20b25b1fa59ef9edad2a6a6c031321bfbafea7752351c692ab5cfa2fa6620"
        ),
    },
    "tools/predict_biglotto_echo_3bet.py": {
        "source_blob_id": (
            "a1852cb7d63b995c3e05935425a31160cc434faa"
        ),
        "source_byte_size": 6838,
        "source_sha256": (
            "ed4878fb59e22c44f26313646a762e034c7f92355e5df56a6f72eed887d11320"
        ),
    },
}
HISTORY_COUNTS_BY_METHOD = {
    ECHO_PHASE2_METHOD_ID: (1, 6, 60, 100, 2148),
    HOT_STOP_REBOUND_METHOD_ID: (200, 500, 2148),
    COMPARE_RANDOM_METHOD_ID: (1, 2148),
    SBP_RANDOM_METHOD_ID: (1, 2148),
}
_HOT_STOP_PARAMETER_GRID = (
    (12, 8),
    (12, 10),
    (15, 8),
    (15, 10),
    (15, 12),
    (18, 8),
    (18, 10),
    (20, 10),
)


class FrozenParityError(ValueError):
    """Frozen-source identity or generated tickets failed parity."""


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _git_bytes(repository: Path, method_id: str) -> bytes:
    try:
        return subprocess.check_output(
            [
                "git",
                "-C",
                str(repository),
                "show",
                f"{FROZEN_SOURCE_COMMIT}:{method_id}",
            ],
            stderr=subprocess.PIPE,
        )
    except subprocess.CalledProcessError as exc:
        raise FrozenParityError(
            f"cannot read frozen source: {method_id}"
        ) from exc


def _git_blob(repository: Path, method_id: str) -> str:
    try:
        output = subprocess.check_output(
            [
                "git",
                "-C",
                str(repository),
                "ls-tree",
                FROZEN_SOURCE_COMMIT,
                "--",
                method_id,
            ],
            stderr=subprocess.PIPE,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        raise FrozenParityError(
            f"cannot read frozen blob identity: {method_id}"
        ) from exc
    columns = output.strip().split()
    if len(columns) < 4 or columns[1] != "blob":
        raise FrozenParityError(
            f"invalid frozen blob identity: {method_id}"
        )
    return columns[2]


def _validate_source(
    *,
    repository: Path,
    method_id: str,
    expected_sha256: str,
    expected_blob: str,
    expected_size: int,
) -> bytes:
    source = _git_bytes(repository, method_id)
    if (
        hashlib.sha256(source).hexdigest() != expected_sha256
        or _git_blob(repository, method_id) != expected_blob
        or len(source) != expected_size
    ):
        raise FrozenParityError(
            f"frozen source identity changed: {method_id}"
        )
    return source


def _execute_module(
    *,
    repository: Path,
    method_id: str,
    source: bytes,
    module_name: str,
) -> ModuleType:
    source_path = repository / method_id
    module = ModuleType(module_name)
    module.__file__ = str(source_path)
    module.__dict__["__name__"] = module_name
    code: CodeType = compile(source, str(source_path), "exec")
    exec(code, module.__dict__)
    sys.modules[module_name] = module
    return module


def _call(
    module: ModuleType,
    name: str,
    *args: object,
    **kwargs: object,
) -> Any:
    function = module.__dict__.get(name)
    if not callable(function):
        raise FrozenParityError(f"frozen callable is missing: {name}")
    return cast(Callable[..., Any], function)(*args, **kwargs)


def _install_import_stubs() -> None:
    def ignore_seed(_seed: object) -> None:
        return None

    def ignore_binomtest(
        *_args: object,
        **_kwargs: object,
    ) -> None:
        return None

    numpy = ModuleType("numpy")
    numpy.__dict__["random"] = SimpleNamespace(
        seed=ignore_seed,
    )
    sys.modules["numpy"] = numpy

    database = ModuleType("database")
    database.__dict__["DatabaseManager"] = object
    sys.modules["database"] = database

    lottery_api = ModuleType("lottery_api")
    lottery_api.__path__ = []
    lottery_database = ModuleType("lottery_api.database")
    lottery_database.__dict__["DatabaseManager"] = object
    sys.modules["lottery_api"] = lottery_api
    sys.modules["lottery_api.database"] = lottery_database

    scipy_stats = ModuleType("scipy.stats")
    scipy_stats.__dict__["binomtest"] = ignore_binomtest
    scipy = ModuleType("scipy")
    scipy.__dict__["stats"] = scipy_stats
    sys.modules["scipy"] = scipy
    sys.modules["scipy.stats"] = scipy_stats


def _load_frozen_modules(
    repository: Path,
) -> tuple[dict[str, ModuleType], list[dict[str, object]]]:
    _install_import_stubs()
    source_rows: list[dict[str, object]] = []
    dependency_modules: dict[str, ModuleType] = {}
    for method_id, facts in DEPENDENCY_SOURCES.items():
        source = _validate_source(
            repository=repository,
            method_id=method_id,
            expected_sha256=cast(str, facts["source_sha256"]),
            expected_blob=cast(str, facts["source_blob_id"]),
            expected_size=cast(int, facts["source_byte_size"]),
        )
        module_name = Path(method_id).stem
        dependency_modules[method_id] = _execute_module(
            repository=repository,
            method_id=method_id,
            source=source,
            module_name=module_name,
        )
        source_rows.append(
            {
                "legacy_method_id": method_id,
                "source_blob_id": facts["source_blob_id"],
                "source_byte_size": facts["source_byte_size"],
                "source_role": "FROZEN_IMPORTED_DEPENDENCY",
                "source_sha256": facts["source_sha256"],
            }
        )
    modules: dict[str, ModuleType] = {}
    for method_id in HISTORY_COUNTS_BY_METHOD:
        source = _validate_source(
            repository=repository,
            method_id=method_id,
            expected_sha256=(
                SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE6_METHOD[
                    method_id
                ]
            ),
            expected_blob=SOURCE_BLOB_BY_METHOD[method_id],
            expected_size=SOURCE_BYTE_SIZE_BY_METHOD[method_id],
        )
        modules[method_id] = _execute_module(
            repository=repository,
            method_id=method_id,
            source=source,
            module_name=f"frozen_wave6_{Path(method_id).stem}",
        )
        source_rows.append(
            {
                "legacy_method_id": method_id,
                "source_blob_id": SOURCE_BLOB_BY_METHOD[method_id],
                "source_byte_size": SOURCE_BYTE_SIZE_BY_METHOD[
                    method_id
                ],
                "source_role": "PRIMARY_METHOD",
                "source_sha256": (
                    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE6_METHOD[
                        method_id
                    ]
                ),
            }
        )
    return modules, source_rows


def _frozen_tickets(
    *,
    method_id: str,
    module: ModuleType,
    history: list[dict[str, object]],
    seed_integer: int,
) -> tuple[tuple[int, ...], ...]:
    raw: list[list[int]]
    if method_id == ECHO_PHASE2_METHOD_ID:
        two_bet = _call(
            module,
            "phase2_echo_2bet",
            history,
            window=50,
            lookback=50,
        )[0]
        three_bet = _call(
            module,
            "phase2_echo_3bet",
            history,
            window=50,
            lookback=50,
        )[0]
        raw = [*two_bet, *three_bet]
    elif method_id == HOT_STOP_REBOUND_METHOD_ID:
        raw = [
            _call(
                module,
                "generate_hot_stop_bet",
                history,
                freq_threshold=frequency_threshold,
                gap_threshold=gap_threshold,
            )
            for frequency_threshold, gap_threshold in (
                _HOT_STOP_PARAMETER_GRID
            )
        ]
    elif method_id == COMPARE_RANDOM_METHOD_ID:
        frozen_random = module.__dict__.get("random")
        if not isinstance(frozen_random, ModuleType):
            raise FrozenParityError("frozen random module is missing")
        frozen_random.seed(seed_integer)
        raw = _call(
            module,
            "generate_random_5_bets",
            "BIG_LOTTO",
        )
    else:
        frozen_random = module.__dict__.get("random")
        if not isinstance(frozen_random, ModuleType):
            raise FrozenParityError("frozen random module is missing")
        frozen_random.seed(seed_integer)
        raw = [
            frozen_random.sample(range(1, 50), 6)
            for _ in range(3)
        ]
    return tuple(tuple(sorted(ticket)) for ticket in raw)


def verify_frozen_parity(
    *,
    legacy_repository: Path,
    database: Path,
    expected_database_sha256: str,
) -> dict[str, object]:
    """Run exact ticket/order comparisons at twelve history cutoffs."""

    pinned = load_pinned_biglotto_history(
        database=database,
        expected_database_sha256=expected_database_sha256,
        require_replay_authority=False,
    )
    modules, source_rows = _load_frozen_modules(legacy_repository)
    parity_cases: list[dict[str, object]] = []
    for method_id, history_counts in HISTORY_COUNTS_BY_METHOD.items():
        for history_count in history_counts:
            draws = pinned.draws[:history_count]
            frozen_history: list[dict[str, object]] = [
                {"numbers": list(draw.numbers)} for draw in draws
            ]
            port_history = tuple(
                LegacyHistoryDraw(
                    draw_number=draw.draw_number,
                    numbers=draw.numbers,
                )
                for draw in draws
            )
            result = generate_legacy_source_native_wave6_portfolio(
                LegacySourceNativeWave6Request(
                    legacy_method_id=method_id,
                    target_draw_number=(
                        f"frozen-parity-{history_count}"
                    ),
                    history=port_history,
                )
            )
            expected = _frozen_tickets(
                method_id=method_id,
                module=modules[method_id],
                history=frozen_history,
                seed_integer=result.metadata.seed_integer,
            )
            if result.tickets != expected:
                raise FrozenParityError(
                    "ticket/order mismatch: "
                    f"{method_id} history={history_count}"
                )
            parity_cases.append(
                {
                    "history_draw_count": history_count,
                    "legacy_method_id": method_id,
                    "native_duplicate_ticket_count": (
                        len(result.tickets)
                        - len(set(result.tickets))
                    ),
                    "native_ticket_count": len(result.tickets),
                    "ordered_tickets_sha256": hashlib.sha256(
                        _canonical_bytes(
                            [
                                list(ticket)
                                for ticket in result.tickets
                            ]
                        )
                    ).hexdigest(),
                    "randomness_used": (
                        result.metadata.randomness_used
                    ),
                    "status": "PASS",
                }
            )
    return {
        "database_sha256_after": pinned.database_sha256_after,
        "database_sha256_before": pinned.database_sha256_before,
        "frozen_source_commit": FROZEN_SOURCE_COMMIT,
        "parity_case_count": len(parity_cases),
        "parity_cases": parity_cases,
        "parity_schema_version": PARITY_SCHEMA_VERSION,
        "random_parity_semantics": (
            "EXACT_FROZEN_RANDOM_SAMPLE_CALL_ORDER_UNDER_INJECTED_"
            "VERSIONED_TARGET_STABLE_SEED_NOT_ORIGINAL_STATE_RECOVERY"
        ),
        "source_execution_mode": (
            "PYTHON_COMPILE_EXEC_OF_EXACT_GIT_SHOW_BYTES_CALLING_"
            "FROZEN_SELECTION_FUNCTIONS_ONLY"
        ),
        "sources": source_rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--legacy-repository",
        type=Path,
        required=True,
    )
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument(
        "--expected-database-sha256",
        required=True,
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FrozenParityError(
            f"refusing to overwrite existing output: {args.output}"
        )
    result = verify_frozen_parity(
        legacy_repository=args.legacy_repository,
        database=args.database,
        expected_database_sha256=args.expected_database_sha256,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(_canonical_bytes(result) + b"\n")


if __name__ == "__main__":
    main()
