#!/usr/bin/env python3
"""Freeze causal source outputs for three seeded benchmark methods."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, cast

from lottolab.infrastructure.replay_backed_batch_import import (
    load_pinned_biglotto_history,
)

FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
PINNED_DATASET_SHA256 = (
    "2f3d711cb97cddabfc6d351b5a639614da60dc3473cc23368711f605e3fe2d6b"
)
HYBRID_METHOD_ID = "tools/hybrid_integration_benchmark.py"
ORTHOGONAL_METHOD_ID = "tools/orthogonal_diversification_benchmark.py"
ZONE_METHOD_ID = "tools/zone_split_optimizer.py"
SUPPORTED_METHODS = (
    HYBRID_METHOD_ID,
    ORTHOGONAL_METHOD_ID,
    ZONE_METHOD_ID,
)
SOURCE_SHA256_BY_METHOD = {
    HYBRID_METHOD_ID: (
        "5789ca8854224383a3c84e62871bc891c0661699309ae32aeff65ca403b3a64b"
    ),
    ORTHOGONAL_METHOD_ID: (
        "ce068c676ca5b16e48d95499a8b9c4cc8ba105962b02c71ad9b076f68659ca71"
    ),
    ZONE_METHOD_ID: (
        "0bf85e3e151766d3bdc174f5395200e730d0c45233afad0d1d91d43200149fe3"
    ),
}
NATIVE_TICKET_COUNT_BY_METHOD = {
    HYBRID_METHOD_ID: 12,
    ORTHOGONAL_METHOD_ID: 35,
    ZONE_METHOD_ID: 18,
}
LOCAL_CONFIGURATION_COUNT_BY_METHOD = {
    HYBRID_METHOD_ID: 4,
    ORTHOGONAL_METHOD_ID: 14,
    ZONE_METHOD_ID: 6,
}
LEDGER_SCHEMA_VERSION = (
    "BIG_LOTTO_SEEDED_BENCHMARKS_WAVE60_TICKET_LEDGER_V1"
)
PARITY_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_SEEDED_BENCHMARKS_WAVE60_PARITY_V1"
)
CAUSAL_PROTOCOL = (
    "FROZEN_BIG_LOTTO_LOCAL_CONFIG_ORDER_TARGET_STABLE_SEED42_V1"
)
REFERENCE_SCRIPT = r'''
import importlib.util
import hashlib
import json
import random
import sys
from pathlib import Path

import numpy as np

config = json.loads(sys.stdin.read())
root = Path(config["source_root"])
sys.path.insert(0, str(root / "lottery_api"))
sys.path.insert(0, str(root))

def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, root / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

hybrid = load("wave60_hybrid", "tools/hybrid_integration_benchmark.py")
orthogonal = load(
    "wave60_orthogonal",
    "tools/orthogonal_diversification_benchmark.py",
)
zone = load("wave60_zone", "tools/zone_split_optimizer.py")

draws = config["draws"]

method_ids = config["method_ids"]
tickets_by_method = {method_id: [] for method_id in method_ids.values()}
closed_by_method = {method_id: [] for method_id in method_ids.values()}
contexts = []

orthogonal_functions = [
    orthogonal.strategy_full_random_orthogonal,
    orthogonal.strategy_zone_split,
    orthogonal.strategy_hot_cold_split,
    orthogonal.strategy_odd_even_split,
    orthogonal.strategy_consecutive_spread,
    orthogonal.strategy_prime_composite,
    orthogonal.strategy_fibonacci_geometric,
]
zone_functions = [
    zone.zone_split_pure,
    zone.zone_split_frequency_weighted,
    zone.zone_split_overlap,
    zone.zone_split_overlap,
    zone.zone_split_golden_ratio,
    zone.zone_split_adaptive,
]

for index, target in enumerate(draws):
    oldest_prefix = draws[:index]
    recent_prefix = list(reversed(oldest_prefix))
    contexts.append(
        hashlib.sha256(
            json.dumps(
                [draw["numbers"] for draw in oldest_prefix],
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
    )
    if index == 0:
        for method_id in method_ids.values():
            tickets_by_method[method_id].append(None)
            closed_by_method[method_id].append(
                "NO_PRIOR_DRAW_FOR_CAUSAL_CUTOFF"
            )
        continue

    random.seed(42)
    np.random.seed(42)
    hybrid_tickets = []
    for function in (
        hybrid.hybrid_zone_frequency,
        hybrid.hybrid_zone_gap,
        hybrid.hybrid_zone_entropy,
        hybrid.hybrid_mixed_strategy,
    ):
        hybrid_tickets.extend(function(recent_prefix, 49, 3))

    random.seed(42)
    np.random.seed(42)
    orthogonal_tickets = []
    for num_bets in (2, 3):
        for function in orthogonal_functions:
            if function is orthogonal.strategy_hot_cold_split:
                result = function(recent_prefix, 49, num_bets)
            else:
                result = function(49, num_bets)
            orthogonal_tickets.extend(result)

    random.seed(42)
    np.random.seed(42)
    zone_tickets = []
    for position, function in enumerate(zone_functions):
        if function in (
            zone.zone_split_frequency_weighted,
            zone.zone_split_adaptive,
        ):
            result = function(recent_prefix, 49, 3)
        elif position == 2:
            result = function(49, 3, 3)
        elif position == 3:
            result = function(49, 3, 5)
        else:
            result = function(49, 3)
        zone_tickets.extend(result)

    outputs = {
        method_ids["hybrid"]: hybrid_tickets,
        method_ids["orthogonal"]: orthogonal_tickets,
        method_ids["zone"]: zone_tickets,
    }
    for method_id, tickets in outputs.items():
        canonical = []
        for ticket in tickets:
            values = sorted(int(number) for number in ticket)
            if (
                len(values) != 6
                or len(set(values)) != 6
                or values[0] < 1
                or values[-1] > 49
            ):
                raise RuntimeError(
                    f"illegal frozen ticket: {method_id} {target['draw']}"
                )
            canonical.append(values)
        tickets_by_method[method_id].append(canonical)
        closed_by_method[method_id].append(None)

print(
    json.dumps(
        {
            "closed_reason_by_method": closed_by_method,
            "context_sha256": contexts,
            "targets": [draw["draw"] for draw in draws],
            "tickets_by_method": tickets_by_method,
        },
        separators=(",", ":"),
        sort_keys=True,
    )
)
'''


class ParityVerificationError(ValueError):
    """Frozen wave-60 source or output violates its contract."""


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
        raise ParityVerificationError(
            completed.stderr.decode(
                "utf-8",
                errors="replace",
            ).strip()
            or "frozen Git query failed"
        )
    return completed.stdout


def _validate_sources(
    frozen_root: Path,
    frozen_source_directory: Path,
) -> dict[str, dict[str, object]]:
    artifacts: dict[str, dict[str, object]] = {}
    for method_id in SUPPORTED_METHODS:
        raw = _git(
            frozen_root,
            "show",
            f"{FROZEN_SOURCE_COMMIT}:{method_id}",
        )
        extracted = frozen_source_directory.joinpath(method_id).read_bytes()
        source_sha256 = hashlib.sha256(raw).hexdigest()
        if (
            raw != extracted
            or source_sha256 != SOURCE_SHA256_BY_METHOD[method_id]
        ):
            raise ParityVerificationError(
                f"frozen source identity changed: {method_id}"
            )
        artifacts[method_id] = {
            "source_blob_id": (
                _git(
                    frozen_root,
                    "rev-parse",
                    f"{FROZEN_SOURCE_COMMIT}:{method_id}",
                )
                .decode("ascii")
                .strip()
            ),
            "source_byte_size": len(raw),
            "source_sha256": source_sha256,
        }
    return artifacts


def _run_reference(
    *,
    reference_python: Path,
    frozen_source_directory: Path,
    draws: list[dict[str, object]],
) -> dict[str, Any]:
    completed = subprocess.run(
        (str(reference_python), "-c", REFERENCE_SCRIPT),
        input=_canonical_bytes(
            {
                "draws": draws,
                "method_ids": {
                    "hybrid": HYBRID_METHOD_ID,
                    "orthogonal": ORTHOGONAL_METHOD_ID,
                    "zone": ZONE_METHOD_ID,
                },
                "source_root": str(frozen_source_directory),
            }
        ),
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        raise ParityVerificationError(
            completed.stderr.decode(
                "utf-8",
                errors="replace",
            ).strip()
            or "frozen reference execution failed"
        )
    try:
        parsed = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ParityVerificationError(
            "frozen reference output is invalid"
        ) from exc
    if not isinstance(parsed, dict):
        raise ParityVerificationError(
            "frozen reference output must be an object"
        )
    return cast(dict[str, Any], parsed)


def verify_wave60_parity(
    *,
    frozen_root: Path,
    frozen_source_directory: Path,
    database: Path,
    expected_database_sha256: str,
    reference_python: Path,
) -> tuple[dict[str, object], dict[str, object]]:
    """Execute frozen selectors and return ledger plus parity evidence."""

    database_raw_sha256 = hashlib.sha256(database.read_bytes()).hexdigest()
    if database_raw_sha256 != expected_database_sha256:
        raise ParityVerificationError(
            "physical regeneration database SHA changed"
        )
    source_artifacts = _validate_sources(
        frozen_root,
        frozen_source_directory,
    )
    pinned_history = load_pinned_biglotto_history(
        database=database,
        expected_database_sha256=expected_database_sha256,
    )
    reference = _run_reference(
        reference_python=reference_python,
        frozen_source_directory=frozen_source_directory,
        draws=[
            {
                "date": draw.draw_date.isoformat(),
                "draw": draw.draw_number,
                "numbers": list(draw.numbers),
                "special": draw.special,
            }
            for draw in pinned_history.draws
        ],
    )
    targets = cast(list[object], reference.get("targets", []))
    contexts = cast(
        list[object],
        reference.get("context_sha256", []),
    )
    tickets_by_method = cast(
        dict[str, list[object]],
        reference.get("tickets_by_method", {}),
    )
    closed_by_method = cast(
        dict[str, list[object]],
        reference.get("closed_reason_by_method", {}),
    )
    if (
        len(targets) != 2149
        or len(contexts) != 2149
        or set(tickets_by_method) != set(SUPPORTED_METHODS)
        or set(closed_by_method) != set(SUPPORTED_METHODS)
    ):
        raise ParityVerificationError(
            "frozen reference target universe changed"
        )
    status_counts_by_method: dict[str, dict[str, int]] = {}
    sequence_sha256_by_method: dict[str, str] = {}
    native_ticket_case_count = 0
    for method_id in SUPPORTED_METHODS:
        tickets = tickets_by_method[method_id]
        reasons = closed_by_method[method_id]
        native_count = NATIVE_TICKET_COUNT_BY_METHOD[method_id]
        if (
            len(tickets) != 2149
            or len(reasons) != 2149
            or tickets[0] is not None
            or reasons[0] != "NO_PRIOR_DRAW_FOR_CAUSAL_CUTOFF"
            or any(reason is not None for reason in reasons[1:])
            or any(
                not isinstance(portfolio, list)
                for portfolio in tickets[1:]
            )
            or any(
                len(cast(list[object], portfolio)) != native_count
                for portfolio in tickets[1:]
                if isinstance(portfolio, list)
            )
        ):
            raise ParityVerificationError(
                f"frozen method coverage changed: {method_id}"
            )
        status_counts_by_method[method_id] = {
            "CLOSED_INSUFFICIENT_HISTORY": 1,
            "OK": 2148,
        }
        sequence_sha256_by_method[method_id] = hashlib.sha256(
            _canonical_bytes(tickets)
        ).hexdigest()
        native_ticket_case_count += 2148 * native_count
    ledger: dict[str, object] = {
        "causal_protocol": CAUSAL_PROTOCOL,
        "closed_reason_by_method": closed_by_method,
        "context_sha256": contexts,
        "dataset_sha256": PINNED_DATASET_SHA256,
        "frozen_source_commit": FROZEN_SOURCE_COMMIT,
        "ledger_schema_version": LEDGER_SCHEMA_VERSION,
        "local_configuration_count_by_method": (
            LOCAL_CONFIGURATION_COUNT_BY_METHOD
        ),
        "native_ticket_count_by_method": NATIVE_TICKET_COUNT_BY_METHOD,
        "source_sha256_by_method": SOURCE_SHA256_BY_METHOD,
        "targets": targets,
        "tickets_by_method": tickets_by_method,
    }
    ledger["ledger_content_sha256"] = hashlib.sha256(
        _canonical_bytes(ledger)
    ).hexdigest()
    parity: dict[str, object] = {
        "causal_protocol": CAUSAL_PROTOCOL,
        "dataset_sha256": PINNED_DATASET_SHA256,
        "database_physical_sha256": database_raw_sha256,
        "frozen_source_commit": FROZEN_SOURCE_COMMIT,
        "ledger_content_sha256": ledger["ledger_content_sha256"],
        "native_ticket_case_count": native_ticket_case_count,
        "parity_schema_version": PARITY_SCHEMA_VERSION,
        "source_artifacts": source_artifacts,
        "source_reference_runtime": (
            "CPYTHON_3_9_6_NUMPY_1_26_2_SCIPY_1_12_0_"
            "TARGET_STABLE_PYTHON_AND_NUMPY_SEED_42"
        ),
        "status": "PASS",
        "status_counts_by_method": status_counts_by_method,
        "ticket_sequence_sha256_by_method": (
            sequence_sha256_by_method
        ),
    }
    parity["parity_sha256"] = hashlib.sha256(
        _canonical_bytes(parity)
    ).hexdigest()
    return ledger, parity


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frozen-root", required=True, type=Path)
    parser.add_argument(
        "--frozen-source-directory",
        required=True,
        type=Path,
    )
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--expected-database-sha256", required=True)
    parser.add_argument(
        "--reference-python",
        default=Path("/usr/bin/python3"),
        type=Path,
    )
    parser.add_argument("--ledger-output-file", required=True, type=Path)
    parser.add_argument("--output-file", required=True, type=Path)
    args = parser.parse_args()
    for path in (args.ledger_output_file, args.output_file):
        if path.exists():
            raise SystemExit(
                f"refusing to overwrite existing output: {path}"
            )
    ledger, parity = verify_wave60_parity(
        frozen_root=args.frozen_root,
        frozen_source_directory=args.frozen_source_directory,
        database=args.database,
        expected_database_sha256=args.expected_database_sha256,
        reference_python=args.reference_python,
    )
    ledger_payload = _canonical_bytes(ledger) + b"\n"
    parity_payload = _canonical_bytes(parity) + b"\n"
    args.ledger_output_file.parent.mkdir(parents=True, exist_ok=True)
    args.output_file.parent.mkdir(parents=True, exist_ok=True)
    args.ledger_output_file.write_bytes(ledger_payload)
    args.output_file.write_bytes(parity_payload)
    print(
        json.dumps(
            {
                "ledger_content_sha256": ledger[
                    "ledger_content_sha256"
                ],
                "ledger_file_sha256": hashlib.sha256(
                    ledger_payload
                ).hexdigest(),
                "native_ticket_case_count": parity[
                    "native_ticket_case_count"
                ],
                "output_file": str(args.output_file),
                "parity_file_sha256": hashlib.sha256(
                    parity_payload
                ).hexdigest(),
                "parity_sha256": parity["parity_sha256"],
                "status": parity["status"],
            },
            separators=(",", ":"),
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
