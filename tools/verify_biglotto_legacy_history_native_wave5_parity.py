"""Verify wave-5 ports against functions executed from the frozen Git bytes."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections.abc import Callable
from pathlib import Path
from types import CodeType
from typing import Any, cast

from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.application.legacy_history_native_portfolios_wave5 import (
    DIVERSIFIED_2BET_METHOD_ID,
    ECHO_2BET_METHOD_ID,
    MODERATE_SELECTION_METHOD_ID,
    SOURCE_SHA256_BY_HISTORY_NATIVE_WAVE5_METHOD,
    LegacyHistoryNativeWave5Request,
    generate_legacy_history_native_wave5_portfolio,
)
from lottolab.infrastructure.replay_backed_batch_import import (
    load_pinned_biglotto_history,
)

FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
PARITY_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_HISTORY_NATIVE_WAVE5_FROZEN_PARITY_V1"
)
SOURCE_BLOB_BY_METHOD = {
    MODERATE_SELECTION_METHOD_ID: (
        "48264eb687251143cf56354134939e7f58a1c728"
    ),
    DIVERSIFIED_2BET_METHOD_ID: (
        "461750505baf123bd7d48c81ad86562d2841a35b"
    ),
    ECHO_2BET_METHOD_ID: (
        "26b6b9c1f0f15e625934896347368dd815b0e6a0"
    ),
}
SOURCE_BYTE_SIZE_BY_METHOD = {
    MODERATE_SELECTION_METHOD_ID: 15083,
    DIVERSIFIED_2BET_METHOD_ID: 12677,
    ECHO_2BET_METHOD_ID: 10654,
}
HISTORY_COUNTS_BY_METHOD = {
    MODERATE_SELECTION_METHOD_ID: (10, 30, 50, 100, 2148),
    DIVERSIFIED_2BET_METHOD_ID: (30, 50, 100, 2148),
    ECHO_2BET_METHOD_ID: (1, 6, 50, 100, 2148),
}


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
        raise FrozenParityError(f"invalid frozen blob identity: {method_id}")
    return columns[2]


def _execute_frozen_module(
    *,
    repository: Path,
    method_id: str,
    source: bytes,
) -> dict[str, Any]:
    source_path = repository / method_id
    namespace: dict[str, Any] = {
        "__file__": str(source_path),
        "__name__": f"frozen_wave5_{source_path.stem}",
    }
    code: CodeType = compile(source, str(source_path), "exec")
    exec(code, namespace)
    return namespace


def _call(
    namespace: dict[str, Any],
    name: str,
    *args: object,
    **kwargs: object,
) -> Any:
    function = namespace.get(name)
    if not callable(function):
        raise FrozenParityError(f"frozen callable is missing: {name}")
    return cast(Callable[..., Any], function)(*args, **kwargs)


def _frozen_tickets(
    *,
    method_id: str,
    namespace: dict[str, Any],
    history: list[dict[str, object]],
) -> tuple[tuple[int, ...], ...]:
    raw: list[list[int]]
    if method_id == MODERATE_SELECTION_METHOD_ID:
        rules = _call(namespace, "get_lottery_rules", "BIG_LOTTO")
        raw = [
            _call(
                namespace,
                "moderate_selection_strategy",
                history,
                rules,
            ),
            *_call(
                namespace,
                "moderate_selection_2bet",
                history,
                rules,
            ),
        ]
    elif method_id == DIVERSIFIED_2BET_METHOD_ID:
        hot = _call(namespace, "strategy_moderate_hot", history)
        comeback = _call(namespace, "strategy_comeback", history)
        zone = _call(namespace, "strategy_zone_balance", history)
        raw = [
            hot,
            comeback,
            zone,
            *_call(namespace, "diversified_2bet", history),
            *_call(namespace, "diversified_3bet", history),
        ]
    else:
        raw = _call(
            namespace,
            "echo_aware_deviation_2bet",
            history,
            window=50,
            echo_weight=0.25,
        )
    return tuple(tuple(ticket) for ticket in raw)


def verify_frozen_parity(
    *,
    legacy_repository: Path,
    database: Path,
    expected_database_sha256: str,
) -> dict[str, object]:
    """Run exact ticket/order comparisons at fourteen history cutoffs."""

    pinned = load_pinned_biglotto_history(
        database=database,
        expected_database_sha256=expected_database_sha256,
    )
    source_rows: list[dict[str, object]] = []
    parity_cases: list[dict[str, object]] = []
    for method_id, history_counts in HISTORY_COUNTS_BY_METHOD.items():
        source = _git_bytes(legacy_repository, method_id)
        source_sha256 = hashlib.sha256(source).hexdigest()
        source_blob = _git_blob(legacy_repository, method_id)
        if (
            source_sha256
            != SOURCE_SHA256_BY_HISTORY_NATIVE_WAVE5_METHOD[method_id]
            or source_blob != SOURCE_BLOB_BY_METHOD[method_id]
            or len(source) != SOURCE_BYTE_SIZE_BY_METHOD[method_id]
        ):
            raise FrozenParityError(
                f"frozen source identity changed: {method_id}"
            )
        namespace = _execute_frozen_module(
            repository=legacy_repository,
            method_id=method_id,
            source=source,
        )
        source_rows.append(
            {
                "legacy_method_id": method_id,
                "source_blob_id": source_blob,
                "source_byte_size": len(source),
                "source_sha256": source_sha256,
            }
        )
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
            expected = _frozen_tickets(
                method_id=method_id,
                namespace=namespace,
                history=frozen_history,
            )
            actual = generate_legacy_history_native_wave5_portfolio(
                LegacyHistoryNativeWave5Request(
                    legacy_method_id=method_id,
                    target_draw_number=f"frozen-parity-{history_count}",
                    history=port_history,
                )
            ).tickets
            if actual != expected:
                raise FrozenParityError(
                    "ticket/order mismatch: "
                    f"{method_id} history={history_count}"
                )
            parity_cases.append(
                {
                    "history_draw_count": history_count,
                    "legacy_method_id": method_id,
                    "native_duplicate_ticket_count": (
                        len(actual) - len(set(actual))
                    ),
                    "native_ticket_count": len(actual),
                    "ordered_tickets_sha256": hashlib.sha256(
                        _canonical_bytes(
                            [list(ticket) for ticket in actual]
                        )
                    ).hexdigest(),
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
