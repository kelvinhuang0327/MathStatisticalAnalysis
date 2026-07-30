#!/usr/bin/env python3
"""Build frozen-source closure evidence for exclusion-pool-only methods."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, cast

FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
BASE_CATALOG_SHA256 = (
    "7907f97b78837a1633da92268b891c450ca0ca4e7bb94dad8eb31ee23fa3358f"
)
EVIDENCE_SCHEMA_VERSION = (
    "BIG_LOTTO_STATIC_DISPOSITION_WAVE13_EVIDENCE_V1"
)
REVIEW_POLICY_VERSION = "BIG_LOTTO_FROZEN_SOURCE_DISPOSITION_REVIEW_V4"
REASON_CODE = "EXCLUSION_NUMBER_POOLS_WITHOUT_TICKET_CONSTRUCTION"
METHOD_SPECS: dict[str, dict[str, object]] = {
    "tools/backtest_must_not_hit.py": {
        "source_sha256": (
            "bcc49069158bbd79bcf5939cb82d4d5d0f07763271286f165bb5290a58e4e3b5"
        ),
        "required_fragments": (
            "def predict_must_not_hit(self, history, bottom_n=10):",
            "return [n for n, s in all_scores[:bottom_n]]",
            "leaks = len(must_not_hit_nums & actual_nums)",
            "for bottom_n in [5, 10, 15]:",
        ),
        "decisive_source_facts": (
            "The source emits bottom-5, bottom-10, and bottom-15 number "
            "pools whose declared meaning is numbers that should not hit.",
            "Its evaluation counts how many excluded numbers leak into the "
            "winning draw; it never constructs a six-number lottery ticket.",
            "The source provides no ordering or rule for selecting six "
            "numbers from the complement of an exclusion pool.",
        ),
        "status_reason": (
            "The frozen method predicts exclusion pools, not legal tickets. "
            "Turning a bottom-N pool or its complement into a six-number "
            "portfolio would require new selection logic absent from source."
        ),
    },
    "tools/backtest_p1_dynamic.py": {
        "source_sha256": (
            "dec641938dd2e2701b6ec6fae3aa5ea9a6b0670e0ea3ec31593a11367ad7e611"
        ),
        "required_fragments": (
            "s10_kill = set([n for n, s in s10_scores[:10]])",
            "p1_kill = set(self.selector.predict_kill_numbers(count=10, history=history))",
            "s10_hit = len(s10_kill & winning_nums)",
            "p1_hit = len(p1_kill & winning_nums)",
        ),
        "decisive_source_facts": (
            "Both compared outputs are ten-number kill sets: a local "
            "Smart-10 exclusion pool and a NegativeSelector P1 exclusion pool.",
            "The backtest measures leaks and clean-kill rates, not prize or "
            "match results for any six-number ticket.",
            "No source step converts either kill set into a ranked complement "
            "or an ordered legal ticket portfolio.",
        ),
        "status_reason": (
            "The frozen comparison produces only exclusion sets and their "
            "leak statistics. A ticket portfolio would need an unpreserved "
            "upstream selector plus a rule for applying the exclusions."
        ),
    },
}


class EvidenceBuildError(ValueError):
    """Frozen source or catalog identity violates the closure review."""


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _git(
    frozen_root: Path,
    *arguments: str,
) -> bytes:
    completed = subprocess.run(
        ("git", "-C", str(frozen_root), *arguments),
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        raise EvidenceBuildError(
            completed.stderr.decode(
                "utf-8",
                errors="replace",
            ).strip()
            or "frozen Git query failed"
        )
    return completed.stdout


def _read_catalog(path: Path) -> dict[str, Any]:
    try:
        parsed = json.loads(path.read_bytes())
    except json.JSONDecodeError as exc:
        raise EvidenceBuildError("base catalog is invalid JSON") from exc
    if not isinstance(parsed, dict):
        raise EvidenceBuildError("base catalog must be an object")
    catalog = cast(dict[str, Any], parsed)
    if (
        catalog.get("catalog_sha256") != BASE_CATALOG_SHA256
        or catalog.get("frozen_source_commit")
        != FROZEN_SOURCE_COMMIT
        or catalog.get("status_counts")
        != {
            "BACKTESTED": 37,
            "CLOSED_UNEXECUTABLE": 25,
            "DUPLICATE_ALIAS": 4,
            "OWNER_DECISION_REQUIRED": 155,
        }
    ):
        raise EvidenceBuildError("base catalog identity changed")
    return catalog


def build_evidence(
    *,
    frozen_root: Path,
    base_catalog_path: Path,
) -> dict[str, object]:
    catalog = _read_catalog(base_catalog_path)
    records_raw = catalog.get("records")
    if not isinstance(records_raw, list):
        raise EvidenceBuildError("base catalog records are missing")
    record_by_method: dict[str, dict[str, Any]] = {}
    for candidate in cast(list[object], records_raw):
        if not isinstance(candidate, dict):
            raise EvidenceBuildError("base catalog record is invalid")
        row = cast(dict[str, Any], candidate)
        method_id = row.get("legacy_method_id")
        if isinstance(method_id, str):
            record_by_method[method_id] = row

    dispositions: list[dict[str, object]] = []
    for method_id, spec in METHOD_SPECS.items():
        record = record_by_method.get(method_id)
        expected_sha256 = cast(str, spec["source_sha256"])
        if (
            record is None
            or record.get("reproduction_status")
            != "OWNER_DECISION_REQUIRED"
            or record.get("source_sha256") != expected_sha256
        ):
            raise EvidenceBuildError(
                f"catalog method identity changed: {method_id}"
            )
        raw = _git(
            frozen_root,
            "show",
            f"{FROZEN_SOURCE_COMMIT}:{method_id}",
        )
        actual_sha256 = hashlib.sha256(raw).hexdigest()
        if actual_sha256 != expected_sha256:
            raise EvidenceBuildError(
                f"frozen source SHA changed: {method_id}"
            )
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise EvidenceBuildError(
                f"frozen source is not UTF-8: {method_id}"
            ) from exc
        required_fragments = cast(
            tuple[str, ...],
            spec["required_fragments"],
        )
        if any(fragment not in text for fragment in required_fragments):
            raise EvidenceBuildError(
                f"decisive frozen-source fact changed: {method_id}"
            )
        blob_id = (
            _git(
                frozen_root,
                "rev-parse",
                f"{FROZEN_SOURCE_COMMIT}:{method_id}",
            )
            .decode("ascii")
            .strip()
        )
        if (
            record.get("source_blob_id") != blob_id
            or record.get("source_byte_size") != len(raw)
        ):
            raise EvidenceBuildError(
                f"catalog frozen blob identity changed: {method_id}"
            )
        dispositions.append(
            {
                "decisive_source_facts": list(
                    cast(
                        tuple[str, ...],
                        spec["decisive_source_facts"],
                    )
                ),
                "legacy_method_id": method_id,
                "reason_code": REASON_CODE,
                "reproduction_status": "CLOSED_UNEXECUTABLE",
                "source_blob_id": blob_id,
                "source_byte_size": len(raw),
                "source_sha256": actual_sha256,
                "status_reason": spec["status_reason"],
            }
        )
    return {
        "base_catalog_sha256": BASE_CATALOG_SHA256,
        "dispositions": dispositions,
        "evidence_schema_version": EVIDENCE_SCHEMA_VERSION,
        "frozen_source_commit": FROZEN_SOURCE_COMMIT,
        "review_policy_version": REVIEW_POLICY_VERSION,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frozen-root", required=True, type=Path)
    parser.add_argument("--base-catalog", required=True, type=Path)
    parser.add_argument("--output-file", required=True, type=Path)
    args = parser.parse_args()
    if args.output_file.exists():
        raise SystemExit(
            f"refusing to overwrite existing output: {args.output_file}"
        )
    document = build_evidence(
        frozen_root=args.frozen_root,
        base_catalog_path=args.base_catalog,
    )
    payload = _canonical_bytes(document) + b"\n"
    args.output_file.parent.mkdir(parents=True, exist_ok=True)
    args.output_file.write_bytes(payload)
    print(
        json.dumps(
            {
                "disposition_count": len(
                    cast(list[object], document["dispositions"])
                ),
                "evidence_sha256": hashlib.sha256(payload).hexdigest(),
                "output_file": str(args.output_file),
            },
            separators=(",", ":"),
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
