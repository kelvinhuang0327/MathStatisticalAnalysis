"""Build/check the single canonical imported-optimizer Matrix artifact."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

from lottolab.research.strategy_matrix_comparison import (
    NATIVE_MEASUREMENT_PATH,
    RESULT_PATH,
    build_comparison,
    canonical_json_bytes,
    measure_native_coverage,
    repair_native_coverage,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="Recompute and compare without writing."
    )
    parser.add_argument(
        "--measure-native",
        action="store_true",
        help="Execute and write the pinned native evidence-completion artifact.",
    )
    parser.add_argument(
        "--repair-native",
        action="store_true",
        help="Complete and rewrite an existing native measurement checkpoint.",
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if sum((args.check, args.measure_native, args.repair_native)) > 1:
        parser.error("--check, --measure-native, and --repair-native are mutually exclusive")
    if args.repair_native:
        payload = repair_native_coverage(root)
        serialized = canonical_json_bytes(payload)
        (root / NATIVE_MEASUREMENT_PATH).write_bytes(serialized)
        print(
            "PASS: repaired native measurement artifact; "
            f"{payload['new_native_measured_count']} measured; "
            f"{payload['remaining_native_not_run_count']} not run"
        )
        print(
            "START_SUPPORTED_NATIVE_NOT_RUN_COUNT: "
            f"{payload['starting_supported_native_not_run_count']}"
        )
        print(f"NATIVE_MEASUREMENT_SHA256: {hashlib.sha256(serialized).hexdigest()}")
        return
    if args.measure_native:
        payload = measure_native_coverage(root)
        serialized = canonical_json_bytes(payload)
        (root / NATIVE_MEASUREMENT_PATH).write_bytes(serialized)
        print(
            "PASS: native measurement artifact; "
            f"{payload['new_native_measured_count']} measured; "
            f"{payload['remaining_native_not_run_count']} not run"
        )
        print(
            "START_SUPPORTED_NATIVE_NOT_RUN_COUNT: "
            f"{payload['starting_supported_native_not_run_count']}"
        )
        print(f"NATIVE_MEASUREMENT_SHA256: {hashlib.sha256(serialized).hexdigest()}")
        return
    payload = build_comparison(root)
    serialized = canonical_json_bytes(payload)
    result_path = root / RESULT_PATH
    if args.check:
        if result_path.read_bytes() != serialized:
            raise SystemExit("FAIL: canonical comparison differs")
    else:
        result_path.write_bytes(serialized)
    print(f"PASS: {len(payload['rows'])} rows; {payload['status_counts']}")
    print(f"METHOD_COUNT: {payload['imported_method_count']}")
    print(f"FAMILY_COUNT: {payload['distinct_family_count']}")
    print(f"SUPPORTED_K: {' / '.join(str(k) for k in payload['supported_k'])}")
    print(f"STRICT_IMPROVEMENTS: {len(payload['strict_improvements']) or 'NONE'}")
    for category, count in payload["gap_counts"].items():
        print(f"{category}: {count or 'NONE'}")
    print(f"FAMILY_EXPANSION_CANDIDATES: {len(payload['family_expansion_candidates'])}")
    print(f"SHA256: {hashlib.sha256(serialized).hexdigest()}")


if __name__ == "__main__":
    main()
