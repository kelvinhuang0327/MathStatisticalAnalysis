#!/usr/bin/env python3
"""Build frozen unbound-ticket-randomness closures for wave 37."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, cast

FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
BASE_CATALOG_SHA256 = (
    "77987cc9a0bc6c2f048a946a2c09143730ebe0bb4b2dac12ce989614bbb92513"
)
BASE_CATALOG_FILE_SHA256 = (
    "30927825f4e8dd7ecfb088e6492b62ec36f5936f32880cb242c51d5ba80ea798"
)
EVIDENCE_SCHEMA_VERSION = (
    "BIG_LOTTO_STATIC_DISPOSITION_WAVE37_EVIDENCE_V1"
)
REVIEW_POLICY_VERSION = "BIG_LOTTO_FROZEN_SOURCE_DISPOSITION_REVIEW_V9"
REASON_CODE = (
    "UNBOUND_TICKET_GENERATION_RANDOMNESS_WITHOUT_FROZEN_PRESTATE"
)
EXPECTED_BASE_STATUS_COUNTS = {
    "BACKTESTED": 78,
    "CLOSED_UNEXECUTABLE": 42,
    "DUPLICATE_ALIAS": 5,
    "OWNER_DECISION_REQUIRED": 96,
}
FORBIDDEN_SEED_BINDINGS = (
    "manual_seed(",
    "random.seed(",
    "np.random.seed(",
    "set_random_seed(",
    "set_seed(",
    "use_deterministic_algorithms(",
)
CLOSED_METHOD_SPECS: dict[str, dict[str, object]] = {
    "lottery_api/engine/multi_bet_optimizer.py": {
        "source_sha256": (
            "10e45b087256c10ed50f1f0cc38903d796296ea862a1b8cea9c881be47f39cb6"
        ),
        "required_fragments": (
            "pb_predictor = PerBallLSTMPredictor(",
            "pb_predictor.train(train_data, epochs=35, verbose=0)",
            "bet1_nums = pb_predictor._greedy_dedup_sample(",
            "pb_predictor.predict_with_temperature(",
            "bets = optimizer.generate_3bets(history)",
        ),
        "forbidden_fragments": FORBIDDEN_SEED_BINDINGS,
        "decisive_source_facts": (
            "The frozen generate_3bets entrypoint constructs and trains a "
            "fresh Per-Ball LSTM before producing its first native ticket.",
            "The source binds no seed, RNG pre-state, deterministic setting, "
            "or checkpoint identity; its imported Per-Ball implementation "
            "is independently closed for that missing neural pre-state.",
            "When no anomaly is detected, the second native ticket also "
            "uses temperature sampling, so the three-ticket portfolio does "
            "not have one frozen reproducible sequence.",
        ),
        "status_reason": (
            "The frozen multi-bet optimizer cannot reproduce one historical "
            "three-ticket sequence because it trains fresh unseeded neural "
            "weights and may temperature-sample its second ticket. Neither "
            "RNG pre-state nor a checkpoint is preserved, and inventing "
            "either would change the frozen method."
        ),
    },
    "tools/coverage_strategy_research.py": {
        "source_sha256": (
            "85f3a0c86a826a1634b79c2c284abfff3aae96de4c1ff206a6387be07d729b59"
        ),
        "required_fragments": (
            "random.shuffle(pool)",
            "line = random.sample(pool, 6)",
            "pool = random.sample(range(1, 50), pool_size)",
            "lines = generate_matrices(pool, num_lines, anchor, strat)",
            "cur_lines = generate_matrices(",
        ),
        "forbidden_fragments": FORBIDDEN_SEED_BINDINGS,
        "decisive_source_facts": (
            "The frozen experiment constructs every evaluated portfolio "
            "through generate_matrices, which shuffles or samples ticket "
            "numbers with module-global Python randomness.",
            "Several source signal pools also use unseeded sample/randint, "
            "including the random baseline and fallback completion paths.",
            "The main entrypoint and published current two-ticket output bind "
            "no seed or serialized RNG pre-state.",
        ),
        "status_reason": (
            "The frozen coverage research entrypoint has no unique native "
            "ticket sequence: source portfolios and its final recommendation "
            "use unseeded module-global randomness with no preserved "
            "pre-state. Choosing a new seed would define a different method."
        ),
    },
    "tools/covering_research.py": {
        "source_sha256": (
            "4ffaf2571955145dbb78ae290127f1a6cea309c267c42320ea559a19cb8af365"
        ),
        "required_fragments": (
            "pool = set(random.sample(hot_nums, pool_size))",
            "pool.add(random.choice(tails[t]))",
            "random.shuffle(pool)",
            "lines = generate_covering(pool, n_lines)",
            "lines_5 = generate_covering(pool_5, 5)",
        ),
        "forbidden_fragments": FORBIDDEN_SEED_BINDINGS,
        "decisive_source_facts": (
            "The frozen generate_covering function shuffles every signal "
            "pool before splitting it into ordered native tickets.",
            "FreqOrt, TailBalance, Random, and fallback pool construction "
            "also sample numbers from module-global Python randomness.",
            "Neither the historical experiment nor the final 2/3/5-ticket "
            "recommendations bind a seed or serialized RNG pre-state.",
        ),
        "status_reason": (
            "The frozen covering research entrypoint cannot reproduce its "
            "ordered native portfolios because ticket splitting and several "
            "signal pools consume unseeded module-global randomness. No "
            "historical RNG pre-state was preserved, so assigning a seed "
            "would create a new method."
        ),
    },
}


class EvidenceBuildError(ValueError):
    """Frozen source or catalog identity violates the wave-37 review."""


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
        raise EvidenceBuildError(
            completed.stderr.decode("utf-8", errors="replace").strip()
            or "frozen Git query failed"
        )
    return completed.stdout


def _frozen_source(
    frozen_root: Path,
    path: str,
    expected_sha256: str,
) -> tuple[bytes, str]:
    raw = _git(
        frozen_root,
        "show",
        f"{FROZEN_SOURCE_COMMIT}:{path}",
    )
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise EvidenceBuildError(f"frozen source SHA changed: {path}")
    blob_id = (
        _git(
            frozen_root,
            "rev-parse",
            f"{FROZEN_SOURCE_COMMIT}:{path}",
        )
        .decode("ascii")
        .strip()
    )
    return raw, blob_id


def _read_catalog(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise EvidenceBuildError("base catalog is invalid JSON") from exc
    if not isinstance(parsed, dict):
        raise EvidenceBuildError("base catalog must be an object")
    catalog = cast(dict[str, Any], parsed)
    if (
        hashlib.sha256(raw).hexdigest() != BASE_CATALOG_FILE_SHA256
        or catalog.get("catalog_sha256") != BASE_CATALOG_SHA256
        or catalog.get("frozen_source_commit") != FROZEN_SOURCE_COMMIT
        or catalog.get("status_counts") != EXPECTED_BASE_STATUS_COUNTS
        or catalog.get("full_universe_complete") is not False
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
    record_by_method = {
        cast(str, row["legacy_method_id"]): row
        for candidate in cast(list[object], records_raw)
        if isinstance(candidate, dict)
        for row in (cast(dict[str, Any], candidate),)
        if isinstance(row.get("legacy_method_id"), str)
    }
    if len(record_by_method) != 221:
        raise EvidenceBuildError("base catalog record count changed")

    dispositions: list[dict[str, object]] = []
    for method_id, spec in CLOSED_METHOD_SPECS.items():
        source_sha256 = cast(str, spec["source_sha256"])
        raw, blob_id = _frozen_source(
            frozen_root,
            method_id,
            source_sha256,
        )
        record = record_by_method.get(method_id)
        if (
            record is None
            or record.get("reproduction_status")
            != "OWNER_DECISION_REQUIRED"
            or record.get("source_sha256") != source_sha256
            or record.get("source_blob_id") != blob_id
            or record.get("source_byte_size") != len(raw)
        ):
            raise EvidenceBuildError(
                f"catalog method identity changed: {method_id}"
            )
        text = raw.decode("utf-8")
        required = cast(tuple[str, ...], spec["required_fragments"])
        forbidden = cast(tuple[str, ...], spec["forbidden_fragments"])
        if any(fragment not in text for fragment in required):
            raise EvidenceBuildError(
                f"decisive source fact changed: {method_id}"
            )
        if any(fragment in text for fragment in forbidden):
            raise EvidenceBuildError(
                f"unbound randomness premise changed: {method_id}"
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
                "source_sha256": source_sha256,
                "status_reason": spec["status_reason"],
            }
        )

    return {
        "base_catalog_file_sha256": BASE_CATALOG_FILE_SHA256,
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
    evidence = build_evidence(
        frozen_root=args.frozen_root,
        base_catalog_path=args.base_catalog,
    )
    payload = _canonical_bytes(evidence) + b"\n"
    args.output_file.parent.mkdir(parents=True, exist_ok=True)
    args.output_file.write_bytes(payload)
    print(
        json.dumps(
            {
                "evidence_sha256": hashlib.sha256(payload).hexdigest(),
                "output_file": str(args.output_file),
            },
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
