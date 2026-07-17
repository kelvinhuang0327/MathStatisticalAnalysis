"""Validate one LottoLab strategy-evaluation evidence JSON file.

Read-only: never modifies its inputs, uses no DB or network, creates no
output artifact, and performs no directory recursion. Prints a concise
sanitized report and exits nonzero on any validation failure.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from lottolab.evidence import validator

REPO_ROOT = Path(__file__).resolve().parents[1]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence_path", type=Path, help="Path to one evidence JSON file.")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=None,
        help="Optional dataset-snapshot JSON path for cross-checking.",
    )
    return parser.parse_args()


def _print_report(evidence_path: Path, report: validator.ValidationReport) -> None:
    print(f"EVIDENCE_FILE {evidence_path}")
    print(f"schema_valid={report.schema_valid}")
    print(f"structurally_valid={report.structurally_valid}")
    trust = report.trust_classification.value if report.trust_classification is not None else "NONE"
    print(f"trust_classification={trust}")
    print(f"canonical_gate_passed={report.canonical_gate_passed}")
    print(f"hash_checks={len(report.hash_checks)}")
    for check in report.hash_checks:
        print(f"  HASH {check.pointer} {check.state.value}")
    print(f"findings={len(report.findings)}")
    for finding in report.findings:
        print(
            f"  FINDING {finding.category.value} {finding.code} "
            f"{finding.pointer} {finding.message}"
        )


def main() -> int:
    args = _parse_args()
    report = validator.validate_evidence_file(
        args.evidence_path,
        repo_root=REPO_ROOT,
        dataset_path=args.dataset,
    )
    _print_report(args.evidence_path, report)
    if report.structurally_valid and not report.findings:
        print("EVIDENCE_VALIDATION_PASS")
        return 0
    print("EVIDENCE_VALIDATION_FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
