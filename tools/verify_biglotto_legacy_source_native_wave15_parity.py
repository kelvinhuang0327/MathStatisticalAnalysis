#!/usr/bin/env python3
"""Verify wave-15 port against the frozen attention replay class."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.application.legacy_source_native_portfolios_wave15 import (
    ATTENTION_REPLAY_METHOD_ID,
    FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE15_METHOD,
    SOURCE_NATIVE_WAVE15_PROTOCOL,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE15_METHOD,
    LegacySourceNativeWave15Request,
    generate_legacy_source_native_wave15_portfolio,
)
from lottolab.infrastructure.replay_backed_batch_import import (
    load_pinned_biglotto_history,
)

FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
PARITY_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_SOURCE_NATIVE_WAVE15_PARITY_V1"
)
_HISTORY_COUNTS = (1, 15, 100, 2148)


class ParityError(ValueError):
    """Frozen source identity or port output differs."""


class _Array(list[float]):
    def sum(self) -> float:
        return sum(self)

    def __itruediv__(self, divisor: float) -> _Array:
        for index, value in enumerate(self):
            self[index] = value / divisor
        return self


class _NumpyCompatibility:
    @staticmethod
    def array(values: list[float]) -> _Array:
        return _Array(values)


class _Tensor:
    requires_grad = False


class _NoGrad:
    def __enter__(self) -> None:
        return None

    def __exit__(
        self,
        exc_type: object,
        exc_value: object,
        traceback: object,
    ) -> bool:
        return False


class _TorchCompatibility:
    long = object()
    float = object()

    @staticmethod
    def tensor(_values: object, *, dtype: object) -> _Tensor:
        del dtype
        return _Tensor()

    @staticmethod
    def no_grad() -> _NoGrad:
        return _NoGrad()


class _Model:
    def __call__(self, _x: object, _stats: object) -> None:
        return None


class _Dataset:
    @staticmethod
    def _extract_v3_stats(
        _draw: list[int],
        _previous: list[int] | None,
    ) -> list[float]:
        return [0.0] * 9


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


def _load_frozen_class(
    source_text: str,
    source_identity: str,
) -> type[Any]:
    tree = ast.parse(source_text, filename=source_identity)
    selected: list[ast.stmt] = [
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef)
        and node.name == "AttentionReplayPredictor"
    ]
    if len(selected) != 1:
        raise ParityError("frozen attention class is missing")
    module = ast.Module(body=selected, type_ignores=[])
    ast.fix_missing_locations(module)
    namespace: dict[str, Any] = {
        "Counter": Counter,
        "Dict": dict,
        "List": list,
        "__builtins__": __builtins__,
        "np": _NumpyCompatibility,
        "torch": _TorchCompatibility,
    }
    exec(compile(module, source_identity, "exec"), namespace)
    return namespace["AttentionReplayPredictor"]


def _source_history(
    history: tuple[LegacyHistoryDraw, ...],
) -> list[dict[str, object]]:
    return [
        {
            "draw_number": draw.draw_number,
            "numbers": list(draw.numbers),
        }
        for draw in history
    ]


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
    source_raw = _git(
        frozen_root,
        "show",
        f"{FROZEN_SOURCE_COMMIT}:{ATTENTION_REPLAY_METHOD_ID}",
    )
    if hashlib.sha256(source_raw).hexdigest() != (
        SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE15_METHOD[
            ATTENTION_REPLAY_METHOD_ID
        ]
    ):
        raise ParityError("frozen source SHA changed")
    source_class = _load_frozen_class(
        source_raw.decode("utf-8"),
        f"{FROZEN_SOURCE_COMMIT}:{ATTENTION_REPLAY_METHOD_ID}",
    )
    support_artifacts: list[dict[str, object]] = []
    for path, expected_sha256 in (
        FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE15_METHOD[
            ATTENTION_REPLAY_METHOD_ID
        ]
    ):
        raw = _git(
            frozen_root,
            "show",
            f"{FROZEN_SOURCE_COMMIT}:{path}",
        )
        if hashlib.sha256(raw).hexdigest() != expected_sha256:
            raise ParityError(f"frozen support artifact changed: {path}")
        blob_id = (
            _git(
                frozen_root,
                "rev-parse",
                f"{FROZEN_SOURCE_COMMIT}:{path}",
            )
            .decode("ascii")
            .strip()
        )
        support_artifacts.append(
            {
                "path": path,
                "source_blob_id": blob_id,
                "source_byte_size": len(raw),
                "source_sha256": expected_sha256,
            }
        )

    cases: list[dict[str, object]] = []
    for count in _HISTORY_COUNTS:
        history = all_history[:count]
        predictor = source_class()
        predictor.model = _Model()
        predictor.dataset = _Dataset()
        source_result = predictor.predict(
            _source_history(history),
            {"maxNumber": 49, "pickCount": 6},
        )
        source_tickets = [sorted(source_result["numbers"])]
        port = generate_legacy_source_native_wave15_portfolio(
            LegacySourceNativeWave15Request(
                legacy_method_id=ATTENTION_REPLAY_METHOD_ID,
                target_draw_number=f"parity-after-{count}",
                history=history,
            )
        )
        port_tickets = [list(ticket) for ticket in port.tickets]
        if source_tickets != port_tickets:
            raise ParityError(f"ticket parity failed at {count}")
        cases.append(
            {
                "history_draw_count": count,
                "legacy_method_id": ATTENTION_REPLAY_METHOD_ID,
                "native_ticket_count": 1,
                "ticket_sha256": hashlib.sha256(
                    _canonical_bytes(port_tickets)
                ).hexdigest(),
            }
        )
    return {
        "case_count": len(cases),
        "cases": cases,
        "database_sha256": pinned.database_sha256_before,
        "execution_mode": (
            "AST_COMPILE_FROZEN_ATTENTION_CLASS_WITH_FORWARD_PASS_"
            "COMPATIBILITY_AND_COMPARE_FIXED_RECENCY_OUTPUT"
        ),
        "frozen_source_commit": FROZEN_SOURCE_COMMIT,
        "parity_schema_version": PARITY_SCHEMA_VERSION,
        "port_protocol": SOURCE_NATIVE_WAVE15_PROTOCOL,
        "source_sha256": dict(
            SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE15_METHOD
        ),
        "status": "PASS",
        "support_artifacts": support_artifacts,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frozen-root", required=True, type=Path)
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--expected-database-sha256", required=True)
    parser.add_argument("--output-file", required=True, type=Path)
    args = parser.parse_args()
    if args.output_file.exists():
        raise SystemExit(
            f"refusing to overwrite existing output: {args.output_file}"
        )
    document = verify_parity(
        frozen_root=args.frozen_root,
        database=args.database,
        expected_database_sha256=args.expected_database_sha256,
    )
    payload = _canonical_bytes(document) + b"\n"
    args.output_file.parent.mkdir(parents=True, exist_ok=True)
    args.output_file.write_bytes(payload)
    print(
        json.dumps(
            {
                "case_count": document["case_count"],
                "output_file": str(args.output_file),
                "sha256": hashlib.sha256(payload).hexdigest(),
                "status": "PASS",
            },
            separators=(",", ":"),
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
