#!/usr/bin/env python3
"""Build frozen unbound-training-randomness closures for wave 36."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, cast

FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
BASE_CATALOG_SHA256 = (
    "fca99742869404dd397cdb6cdc2b0755db2d7ff591002e2b30004c7a9e57fab9"
)
BASE_CATALOG_FILE_SHA256 = (
    "d2d15de8a6ee168def33636c9d6a724bc780b4218f24866be7e6ab8f4473a846"
)
EVIDENCE_SCHEMA_VERSION = (
    "BIG_LOTTO_STATIC_DISPOSITION_WAVE36_EVIDENCE_V1"
)
REVIEW_POLICY_VERSION = "BIG_LOTTO_FROZEN_SOURCE_DISPOSITION_REVIEW_V8"
REASON_CODE = "UNBOUND_NEURAL_TRAINING_RANDOMNESS_WITHOUT_FROZEN_PRESTATE"
EXPECTED_BASE_STATUS_COUNTS = {
    "BACKTESTED": 78,
    "CLOSED_UNEXECUTABLE": 40,
    "DUPLICATE_ALIAS": 5,
    "OWNER_DECISION_REQUIRED": 98,
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
    "lottery_api/models/lstm_attention_predictor.py": {
        "source_sha256": (
            "99fa7814c95d7cf0c4c73cf43ad2aaedbc13b024ac77d5d1ead331a84649872c"
        ),
        "required_fragments": (
            "DataLoader(train_dataset, batch_size=batch_size, shuffle=True)",
            "_lstm_predictor = None",
            "predictor = get_lstm_predictor()",
            "predictor.train(history, epochs=50, verbose=False)",
            "self.model = LotteryLSTMAttention(",
        ),
        "forbidden_fragments": (
            "lstm_attention_model.pth",
            *FORBIDDEN_SEED_BINDINGS,
        ),
        "decisive_source_facts": (
            "The frozen unified entrypoint trains a newly initialized "
            "LSTM-attention model on first use with a shuffled DataLoader.",
            "No Python, NumPy, or PyTorch seed, RNG pre-state, deterministic "
            "algorithm setting, or checkpoint identity is bound by the "
            "selection entrypoint.",
            "The trained predictor is cached in a module-global singleton, "
            "so results also depend on prior call order and process state.",
        ),
        "status_reason": (
            "The frozen LSTM-attention entrypoint cannot reproduce one "
            "historical native ticket sequence: it trains random initial "
            "weights with shuffled batches, binds no seed or pre-state, "
            "loads no checkpoint, and then reuses process-global trained "
            "state. Supplying a new seed or reset policy would create a "
            "different method."
        ),
    },
    "lottery_api/models/perball_lstm.py": {
        "source_sha256": (
            "cfe6216f73d308963afabedc282d0c2f74c779e3e1220c746090e205280056d8"
        ),
        "required_fragments": (
            "self.model = self._build_model()",
            "train_history = self.model.fit(",
            "predictor = PerBallLSTMPredictor(",
            "predictor.train(train_data, epochs=40, verbose=0)",
            "numbers = predictor.predict(train_data, n_numbers=n_numbers)",
        ),
        "forbidden_fragments": FORBIDDEN_SEED_BINDINGS,
        "decisive_source_facts": (
            "The frozen perball_lstm_predict entrypoint constructs and "
            "trains a fresh TensorFlow/Keras model for each call.",
            "Model initialization and model.fit shuffling are not bound to "
            "a seed, RNG pre-state, deterministic setting, or source-named "
            "checkpoint.",
            "The primary entrypoint returns the newly trained model's greedy "
            "ticket, so training randomness directly changes native numbers.",
        ),
        "status_reason": (
            "The frozen Per-Ball LSTM entrypoint cannot reproduce one "
            "historical native ticket sequence because every call trains "
            "new unseeded TensorFlow weights and the source binds neither "
            "RNG pre-state nor checkpoint identity. Inventing a seed would "
            "change the frozen selection method."
        ),
    },
}


class EvidenceBuildError(ValueError):
    """Frozen source or catalog identity violates the wave-36 review."""


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
