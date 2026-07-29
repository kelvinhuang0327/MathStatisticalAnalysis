#!/usr/bin/env python3
"""Build frozen-source model-compatibility closures for wave 35."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import pickle
import subprocess
import zipfile
from pathlib import Path
from typing import Any, cast

FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
BASE_CATALOG_SHA256 = (
    "3d17d7c7d030dc1309045beeef6172bdbe1a839a1f28eaf6a5763422dc279d0a"
)
BASE_CATALOG_FILE_SHA256 = (
    "a634edc4008e3935475449e791e286672f4e645c56918279a739a65370a0074a"
)
EVIDENCE_SCHEMA_VERSION = (
    "BIG_LOTTO_STATIC_DISPOSITION_WAVE35_EVIDENCE_V1"
)
REVIEW_POLICY_VERSION = "BIG_LOTTO_FROZEN_SOURCE_DISPOSITION_REVIEW_V7"
REASON_CODE = "FROZEN_MODEL_CHECKPOINT_ARCHITECTURE_INCOMPATIBLE"
TRANSFORMER_PATH = "ai_lab/ai_models/transformer_v2.py"
TRANSFORMER_SHA256 = (
    "c2fa21888ee5de7c8a28523792babf91ce3185602ccaf762bafcfc3a86c27583"
)
HYBRID_SUPPORT_PATH = "ai_lab/scripts/benchmark_hybrid.py"
HYBRID_SUPPORT_SHA256 = (
    "b1f675531fcf92be2ae45b0203fc7983bc62b8ce8c804a6cf600212d687bf74f"
)
EXPECTED_BASE_STATUS_COUNTS = {
    "BACKTESTED": 78,
    "CLOSED_UNEXECUTABLE": 38,
    "DUPLICATE_ALIAS": 5,
    "OWNER_DECISION_REQUIRED": 100,
}
CLOSED_METHOD_SPECS: dict[str, dict[str, object]] = {
    "ai_lab/scripts/benchmark_hybrid.py": {
        "source_sha256": HYBRID_SUPPORT_SHA256,
        "checkpoint_path": "ai_lab/ai_models/hybrid_best.pth",
        "checkpoint_sha256": (
            "d363b1203c44791d4cd516d40dee738353486d77b344d4bd72d2a9049e29a082"
        ),
        "required_fragments": (
            "self.model = HybridLotteryTransformer().to(device)",
            "self.model.load_state_dict(torch.load(model_path, map_location=device))",
            "stats.append(self.dataset._extract_stats(context_draws[i], prev))",
        ),
        "status_reason": (
            "The frozen Hybrid benchmark cannot initialize its local "
            "predictor. HybridLotteryTransformer defaults to nine input "
            "features, while hybrid_best.pth stores a 32-by-7 "
            "stat_projector weight and the frozen feature extractor emits "
            "seven values. Strict state loading fails before any ticket "
            "can be selected."
        ),
    },
    "ai_lab/scripts/benchmark_rl.py": {
        "source_sha256": (
            "ba7a42835b53a38ec70652966c30f3944b6d0a9f84e0227d7be96f6e73fb6642"
        ),
        "checkpoint_path": "ai_lab/ai_models/rl_gen3_best.pth",
        "checkpoint_sha256": (
            "c3a4057535722bb9e7bd45d422d7cb0257f918d22582aab249016e8e8c60fdf5"
        ),
        "required_fragments": (
            "class RLPredictor(HybridPredictor):",
            "return super().predict(history, rules)",
            "rl_predictor = RLPredictor(rl_model_path)",
            "hybrid_predictor = HybridPredictor(hybrid_model_path)",
        ),
        "status_reason": (
            "The frozen RL benchmark inherits the same seven-feature "
            "HybridPredictor and loads a 32-by-7 rl_gen3 checkpoint into "
            "the frozen nine-feature HybridLotteryTransformer. Strict "
            "state loading fails before the RL or Hybrid comparison can "
            "emit a ticket."
        ),
    },
}


class EvidenceBuildError(ValueError):
    """Frozen source or catalog identity violates the wave-35 review."""


class _CheckpointUnpickler(pickle.Unpickler):
    """Read tensor metadata without importing or executing PyTorch."""

    def find_class(self, module: str, name: str) -> object:
        if module == "torch._utils" and name in {
            "_rebuild_tensor",
            "_rebuild_tensor_v2",
        }:
            return self._tensor
        if module == "torch" and name.endswith("Storage"):
            return f"{module}.{name}"
        return super().find_class(module, name)

    def persistent_load(self, pid: object) -> object:
        return {"persistent_storage": pid}

    @staticmethod
    def _tensor(
        _storage: object,
        _offset: int,
        size: tuple[int, ...],
        stride: tuple[int, ...],
        *_rest: object,
    ) -> dict[str, tuple[int, ...]]:
        return {"shape": tuple(size), "stride": tuple(stride)}


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


def _frozen_blob(
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
        raise EvidenceBuildError(f"frozen artifact SHA changed: {path}")
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


def _checkpoint_shape(raw: bytes, key: str) -> tuple[int, ...]:
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            data_name = next(
                name
                for name in archive.namelist()
                if name.endswith("/data.pkl")
            )
            state_raw = cast(
                object,
                _CheckpointUnpickler(
                    io.BytesIO(archive.read(data_name))
                ).load(),
            )
    except (
        KeyError,
        pickle.UnpicklingError,
        StopIteration,
        zipfile.BadZipFile,
    ) as exc:
        raise EvidenceBuildError(
            "frozen checkpoint metadata is unreadable"
        ) from exc
    if not isinstance(state_raw, dict):
        raise EvidenceBuildError("frozen checkpoint state is not a mapping")
    state = cast(dict[object, object], state_raw)
    tensor_raw = state.get(key)
    if not isinstance(tensor_raw, dict):
        raise EvidenceBuildError(f"checkpoint tensor is missing: {key}")
    tensor = cast(dict[object, object], tensor_raw)
    shape = tensor.get("shape")
    if not isinstance(shape, tuple):
        raise EvidenceBuildError(f"checkpoint shape is invalid: {key}")
    shape_values = cast(tuple[object, ...], shape)
    if not all(type(item) is int for item in shape_values):
        raise EvidenceBuildError(f"checkpoint shape is invalid: {key}")
    return cast(tuple[int, ...], shape_values)


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

    transformer_raw, transformer_blob_id = _frozen_blob(
        frozen_root,
        TRANSFORMER_PATH,
        TRANSFORMER_SHA256,
    )
    transformer_text = transformer_raw.decode("utf-8")
    if (
        "stat_dim=9" not in transformer_text
        or "self.stat_projector = nn.Linear(stat_dim, d_model // 4)"
        not in transformer_text
    ):
        raise EvidenceBuildError(
            "frozen transformer feature dimension changed"
        )

    dispositions: list[dict[str, object]] = []
    checkpoints: list[dict[str, object]] = []
    for method_id, spec in CLOSED_METHOD_SPECS.items():
        source_sha256 = cast(str, spec["source_sha256"])
        raw, blob_id = _frozen_blob(
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
        if any(
            fragment not in text
            for fragment in cast(
                tuple[str, ...],
                spec["required_fragments"],
            )
        ):
            raise EvidenceBuildError(
                f"decisive source fact changed: {method_id}"
            )
        checkpoint_path = cast(str, spec["checkpoint_path"])
        checkpoint_sha256 = cast(str, spec["checkpoint_sha256"])
        checkpoint_raw, checkpoint_blob_id = _frozen_blob(
            frozen_root,
            checkpoint_path,
            checkpoint_sha256,
        )
        checkpoint_shape = _checkpoint_shape(
            checkpoint_raw,
            "stat_projector.weight",
        )
        if checkpoint_shape != (32, 7):
            raise EvidenceBuildError(
                f"checkpoint feature shape changed: {checkpoint_path}"
            )
        checkpoints.append(
            {
                "artifact_path": checkpoint_path,
                "artifact_sha256": checkpoint_sha256,
                "source_blob_id": checkpoint_blob_id,
                "stat_projector_weight_shape": list(checkpoint_shape),
            }
        )
        dispositions.append(
            {
                "checkpoint_path": checkpoint_path,
                "checkpoint_sha256": checkpoint_sha256,
                "checkpoint_stat_projector_weight_shape": list(
                    checkpoint_shape
                ),
                "decisive_source_facts": [
                    "Frozen HybridLotteryTransformer defaults to "
                    "stat_dim=9 and constructs a 32-by-9 "
                    "stat_projector weight.",
                    "The required frozen checkpoint contains a 32-by-7 "
                    "stat_projector weight.",
                    "The source uses strict load_state_dict before any "
                    "predict call, so the mismatch prevents ticket output.",
                ],
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
        "checkpoint_artifacts": checkpoints,
        "dispositions": dispositions,
        "evidence_schema_version": EVIDENCE_SCHEMA_VERSION,
        "frozen_source_commit": FROZEN_SOURCE_COMMIT,
        "review_policy_version": REVIEW_POLICY_VERSION,
        "support_artifacts": [
            {
                "artifact_path": TRANSFORMER_PATH,
                "artifact_sha256": TRANSFORMER_SHA256,
                "source_blob_id": transformer_blob_id,
            }
        ],
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
