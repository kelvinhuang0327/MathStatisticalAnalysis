"""Read-only application API for the completed D backtest ranking receipts.

The app reads only paths pinned by the fixed read_model_manifest.json. It never
writes to those files, opens a database, or accepts a source path from a request.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from http import HTTPStatus
from pathlib import Path, PureWindowsPath
from types import MappingProxyType
from typing import Any
from urllib.parse import parse_qs

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

API_VERSION = "v1"
DEFAULT_MANIFEST_PATH = Path(
    "/Users/kelvin/VibeCoding-WorkSpace/.task-data/20261102/"
    "NUMBER2_D_BACKTEST_RANKING_READ_API_20261102_R1/read_model_manifest.json"
)
MANIFEST_PATH_ENV = "NUMBER2_D_BACKTEST_MANIFEST_PATH"
PINNED_MANIFEST_SHA256 = "230bc8bbacccb7290f0fe715dfd8134289c39e8e7e738df8ee5a05312a1e26d0"
PINNED_SOURCE_FILES = {
    "rankings": {
        "path": (
            "/Users/kelvin/VibeCoding-WorkSpace/.task-data/20261102/"
            "NUMBER2_D_OWNER_RANKING_CONSOLIDATION_20261102_R1/owner_all_horizon_ranks.csv"
        ),
        "sha256": "8a61f2731ae842504dea4602ad3ddc456dd140d9563c130ec099ef82621d7965",
        "row_count": 1444,
    },
    "scores": {
        "path": (
            "/Users/kelvin/VibeCoding-WorkSpace/.task-data/20261102/"
            "NUMBER2_D_OWNER_RANKING_CONSOLIDATION_20261102_R1/owner_all_horizon_scores.csv"
        ),
        "sha256": "f60c22ae602c4986ad869fc7650e7b6a3f5deb372c95cf3b96ef41133c836668",
        "row_count": 1806,
    },
    "method_status": {
        "path": (
            "/Users/kelvin/VibeCoding-WorkSpace/.task-data/20261102/"
            "NUMBER2_D_OWNER_RANKING_CONSOLIDATION_20261102_R1/owner_all_methods_status.csv"
        ),
        "sha256": "404ed0aeb03b75e5988205892d8bffb692b436a7bd061b646c9626d74d5b706b",
        "row_count": 3286,
    },
    "manual_review": {
        "path": (
            "/Users/kelvin/VibeCoding-WorkSpace/.task-data/20261102/"
            "NUMBER2_D_OWNER_RANKING_CONSOLIDATION_20261102_R1/owner_manual_review.csv"
        ),
        "sha256": "325ce436c84e690db12a7b5d26bb3529548e2b3cdf5fe9149501b85d818049f3",
        "row_count": 3286,
    },
    "retained_methods": {
        "path": (
            "/Users/kelvin/VibeCoding-WorkSpace/.task-data/20261102/"
            "NUMBER2_D_ALL_BACKTEST_METHOD_RETENTION_20261102_R1/retained_methods.csv"
        ),
        "sha256": "c0bcf2b15274f13223222a6a0b3ee1ce1dc5122635cd5b86239c639af8d18994",
        "row_count": 1064,
    },
}
PINNED_SOURCE_RECEIPTS = {
    "history_contract": {
        "path": (
            "/Users/kelvin/VibeCoding-WorkSpace/.task-data/"
            "NUMBER2_D_STANDARD_HISTORY_CONTRACT_READ_1030_R1/result.json"
        ),
        "sha256": "da6305c1ebc48fd0004efee3645f79af2116dfbb4be49c4b185da602a6b27739",
    },
    "owner_ranking": {
        "path": (
            "/Users/kelvin/VibeCoding-WorkSpace/.task-data/20261102/"
            "NUMBER2_D_OWNER_RANKING_CONSOLIDATION_20261102_R1/result.json"
        ),
        "sha256": "a254c5217ab8f7fa6b3041e0f9fa8fd6b664642cdbd63bb475229dcf415f18c1",
    },
    "method_retention": {
        "path": (
            "/Users/kelvin/VibeCoding-WorkSpace/.task-data/20261102/"
            "NUMBER2_D_ALL_BACKTEST_METHOD_RETENTION_20261102_R1/result.json"
        ),
        "sha256": "ea93da174fb7fde95d8fcca68955bbddffc1087fb5ac9a5a23cfd37dd5097d1a",
    },
}
PINNED_EXPECTED_COUNTS = {
    "formal_rank_rows": 1417,
    "descriptive_rank_rows": 27,
    "score_rows": 1806,
    "status_rows": 3286,
    "manual_review_rows": 3286,
    "retained_rows": 1064,
    "source_coverage_identities": 184,
}
PINNED_FORMAL_RANK_COUNTS_BY_WINDOW_K = {
    "LONG_K2": 161,
    "LONG_K3": 154,
    "LONG_K5": 143,
    "MID_K2": 163,
    "MID_K3": 158,
    "MID_K5": 145,
    "SHORT_K2": 171,
    "SHORT_K3": 167,
    "SHORT_K5": 155,
}
PINNED_REFERENCE = {
    "history_contract_id": "D2_STANDARD_HISTORY_CONTRACT_READ_1030_R1",
    "historical_source_sha256": "f32e0228c1346c0ab12e090d7934e4b03e756c873a8a7b72aab462988d2e443a",
    "windows": {"LONG": 1317, "MID": 520, "SHORT": 104},
    "greedy_success_count_by_window_k": {
        "LONG": {"K2": 72, "K3": 117, "K5": 200},
        "MID": {"K2": 29, "K3": 44, "K5": 77},
        "SHORT": {"K2": 8, "K3": 13, "K5": 24},
    },
    "coldpool_k5_long_mid_short": [251, 98, 23],
    "l3_repaired_k5_long_mid_short": [209, 73, 20],
    "h24_master_status": "CANONICAL_NOT_SELECTED",
}
PINNED_MANIFEST_IDENTITY = {
    "schema_version": "1",
    "task_id": "NUMBER2_D_BACKTEST_RANKING_READ_API_20261102_R1",
    "source_task_id": "NUMBER2_D_OWNER_RANKING_CONSOLIDATION_20261102_R1",
    "source_task_lane": "D",
    "canonical_source_commit": "fe3aa81d3844ac11d4360447c243e90fe4a6613a",
}
ROUTES = {
    "/v1/research/backtests/strategies",
    "/v1/research/backtests/rankings",
    "/v1/research/backtests/scores",
}
RANK_TYPES = {
    "formal": "FORMAL",
    "descriptive": "DESCRIPTIVE_VERSION_REVIEW",
}
WINDOWS = frozenset({"LONG", "MID", "SHORT"})
K_VALUES = frozenset({2, 3, 5})
MANUAL_FIELDS = ("manual_rank", "owner_decision", "owner_notes")
SCORE_IDENTITY_FIELDS = (
    "source_group",
    "source_task_id",
    "origin_task_id",
    "strategy_id",
    "strategy_version",
    "policy_version",
    "algorithm_version",
    "K",
    "window",
    "variant_type",
    "identity_key",
)
INTEGER_FIELDS = frozenset(
    {
        "K",
        "historical_success_count",
        "window_n",
        "greedy_success_count",
        "W",
        "L",
        "T",
        "formal_rank",
        "descriptive_rank",
        "source_formal_rank",
        "source_overlay_rank",
        "source_patch_rank",
        "source_reported_success_count",
        "original_formal_rank",
        "rank_change",
    }
)
FLOAT_FIELDS = frozenset(
    {
        "historical_success_rate",
        "delta_pp",
        "source_delta_pp",
        "native_ratio",
        "adapted_ratio",
        "fallback_ratio",
        "exact_gap",
        "exact_two_sided_p",
    }
)
REQUIRED_HEADERS = {
    "rankings": frozenset(
        {
            "source_group",
            "source_task_id",
            "origin_task_id",
            "strategy_id",
            "strategy_version",
            "policy_version",
            "algorithm_version",
            "K",
            "window",
            "historical_success_count",
            "historical_success_rate",
            "window_n",
            "greedy_success_count",
            "W",
            "L",
            "T",
            "formal_rank",
            "descriptive_rank",
            "rank_type",
            "rank_reason",
            "identity_key",
            "source_locator",
            "source_sha256",
            "source_identity",
            "retention_status",
            "source_status",
            "scoring_status",
            "standard_comparability",
            "causality_status",
            "advance_recommendation",
            "variant_type",
            "counterfactual_status",
            "formal_eligible",
        }
    ),
    "scores": frozenset(
        {
            "source_group",
            "source_task_id",
            "origin_task_id",
            "strategy_id",
            "strategy_version",
            "policy_version",
            "algorithm_version",
            "K",
            "window",
            "historical_success_count",
            "historical_success_rate",
            "window_n",
            "greedy_success_count",
            "W",
            "L",
            "T",
            "identity_key",
            "source_locator",
            "source_sha256",
            "source_identity",
            "retention_status",
            "source_status",
            "scoring_status",
            "standard_comparability",
            "causality_status",
            "advance_recommendation",
            "variant_type",
            "counterfactual_status",
        }
    ),
    "method_status": frozenset(
        {
            "status_record_id",
            "record_type",
            "source_group",
            "source_task_id",
            "origin_task_id",
            "strategy_id",
            "strategy_version",
            "policy_version",
            "source_policy_versions",
            "algorithm_version",
            "K",
            "window",
            "source_statuses",
            "scoring_status",
            "standard_comparability",
            "causality_status",
            "retention_status",
            "retention_flags",
            "advance_recommendation",
            "retention_record_ids",
            "source_locators",
            "source_sha256s",
            "source_identities",
            "manual_rank",
            "owner_decision",
            "owner_notes",
        }
    ),
    "manual_review": frozenset({"status_record_id", *MANUAL_FIELDS}),
    "retained_methods": frozenset(
        {
            "record_id",
            "record_kind",
            "source_group",
            "source_task_id",
            "evidence_task_id",
            "strategy_id",
            "strategy_version",
            "policy_version",
            "algorithm_version",
            "variant_type",
            "K",
            "source_window",
            "result_locator",
            "source_sha256",
            "source_identity",
            "task_lifecycle_state",
            "scoring_status",
            "causal_status",
            "comparability",
            "retention_status",
            "retention_flags",
            "advance_recommendation",
            "human_review_eligible",
            "human_review_reason",
        }
    ),
}
STRATEGY_FIELDS = (
    "status_record_id",
    "record_type",
    "source_group",
    "source_task_id",
    "origin_task_id",
    "strategy_id",
    "strategy_version",
    "policy_version",
    "source_policy_versions",
    "algorithm_version",
    "K",
    "window",
    "source_statuses",
    "source_status",
    "scoring_status",
    "standard_comparability",
    "causality_status",
    "historical_success_count",
    "historical_success_rate",
    "window_n",
    "greedy_success_count",
    "delta_pp",
    "source_delta_pp",
    "W",
    "L",
    "T",
    "retention_status",
    "retention_flags",
    "advance_recommendation",
    "retention_record_ids",
    "source_locators",
    "source_sha256s",
    "source_identities",
    "source_artifact_sha256s",
    "source_locator",
    "source_sha256",
    "source_identity",
    "source_artifact_sha256",
    "source_policy_version",
    "original_formal_rank",
    "patch_action",
    "rank_change",
    "variant_type",
    "configured_seed",
    "source_variant",
    "qualification",
    "limitations",
    "counterfactual_status",
    "formal_eligible",
    "formal_rank",
    "descriptive_rank",
    "rank_type",
    "rank_reason",
    "source_formal_rank",
    "source_overlay_rank",
    "source_patch_rank",
    "source_reported_success_count",
    "rank_truth_override",
    "rank_truth_source",
    "rank_truth_conflict_note",
    "identity_key",
    "n3_identity_status",
    "n3_version_basis",
    "superseded_by_variant",
    "exact_two_sided_p",
    "overlay_source_group",
    "manual_rank",
    "owner_decision",
    "owner_notes",
)
RETENTION_FIELDS = (
    "record_id",
    "record_kind",
    "source_group",
    "source_task_id",
    "evidence_task_id",
    "strategy_id",
    "strategy_version",
    "policy_version",
    "algorithm_version",
    "variant_type",
    "K",
    "history_contract",
    "source_window",
    "result_locator",
    "source_sha256",
    "source_identity",
    "task_lifecycle_state",
    "scoring_status",
    "causal_status",
    "comparability",
    "retention_status",
    "retention_flags",
    "advance_recommendation",
    "human_review_eligible",
    "human_review_reason",
    "equivalence_class",
)


class ReadModelError(RuntimeError):
    """Raised when a pinned source cannot be read without ambiguity."""


@dataclass(frozen=True)
class ReadModel:
    manifest: Mapping[str, Any]
    manifest_path: Path
    manifest_sha256: str
    data_version: str
    rankings: tuple[Mapping[str, Any], ...]
    scores: tuple[Mapping[str, Any], ...]
    method_status: tuple[Mapping[str, Any], ...]
    retained_methods: tuple[Mapping[str, Any], ...]
    score_indexes: Mapping[str, Mapping[Any, tuple[Mapping[str, Any], ...]]]

    def scores_for(self, filters: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
        """Apply all supplied exact filters using read-only per-field indexes."""
        candidates: list[tuple[Mapping[str, Any], ...]] = []
        for field, value in filters.items():
            index = self.score_indexes[field]
            matches = index.get(value, ())
            if not matches:
                return ()
            candidates.append(matches)
        if not candidates:
            return self.scores
        smallest = min(candidates, key=len)
        return tuple(
            row
            for row in smallest
            if all(row.get(field) == value for field, value in filters.items())
        )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise ReadModelError(f"Cannot read pinned source: {path}") from exc
    return digest.hexdigest()


def _normalise_value(field: str, raw: str | None) -> Any:
    if raw is None or raw == "":
        return None
    if field in INTEGER_FIELDS:
        try:
            return int(raw)
        except (TypeError, ValueError):
            return raw
    if field in FLOAT_FIELDS:
        try:
            value = float(raw)
        except (TypeError, ValueError):
            return raw
        return value if math.isfinite(value) else None
    return raw


def _freeze_row(row: Mapping[str, str | None]) -> Mapping[str, Any]:
    return MappingProxyType({field: _normalise_value(field, value) for field, value in row.items()})


def _read_csv(
    path: Path, label: str, expected_sha: str, expected_rows: int
) -> tuple[Mapping[str, Any], ...]:
    observed_sha = _sha256(path)
    if observed_sha != expected_sha:
        raise ReadModelError(
            f"Source SHA mismatch for {label}: expected {expected_sha}, got {observed_sha}"
        )
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            headers = reader.fieldnames or []
            if len(headers) != len(set(headers)):
                raise ReadModelError(f"Duplicate CSV headers in {label}")
            missing = REQUIRED_HEADERS[label].difference(headers)
            if missing:
                raise ReadModelError(f"Missing required columns in {label}: {sorted(missing)}")
            rows = tuple(_freeze_row(row) for row in reader)
    except OSError as exc:
        raise ReadModelError(f"Cannot read pinned source: {path}") from exc
    if len(rows) != expected_rows:
        raise ReadModelError(
            f"Row count mismatch for {label}: expected {expected_rows}, got {len(rows)}"
        )
    return rows


def _is_default_manifest(path: Path) -> bool:
    try:
        return path.resolve() == DEFAULT_MANIFEST_PATH.resolve()
    except OSError:
        return False


def _load_manifest(path: Path) -> tuple[Mapping[str, Any], str]:
    try:
        manifest_bytes = path.read_bytes()
    except OSError as exc:
        raise ReadModelError(f"Cannot read manifest: {path}") from exc
    manifest_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
    is_default_manifest = _is_default_manifest(path)
    if is_default_manifest and manifest_sha256 != PINNED_MANIFEST_SHA256:
        raise ReadModelError(f"Pinned source manifest SHA mismatch: {path}")
    try:
        manifest = json.loads(manifest_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReadModelError(f"Cannot read manifest: {path}") from exc
    if not isinstance(manifest, dict):
        raise ReadModelError("Manifest must be a JSON object")

    expected_manifest_keys = {
        "schema_version",
        "task_id",
        "source_task_id",
        "source_task_lane",
        "canonical_source_commit",
        "source_receipts",
        "source_files",
        "expected_counts",
        "formal_rank_counts_by_window_k",
        "reference",
    }
    if set(manifest) != expected_manifest_keys:
        raise ReadModelError("Manifest schema fields are incomplete or unexpected")
    if manifest.get("schema_version") != "1":
        raise ReadModelError("Unsupported manifest schema version")
    if any(manifest.get(key) != value for key, value in PINNED_MANIFEST_IDENTITY.items()):
        raise ReadModelError("Manifest source identity is not the accepted D source")

    source_receipts = manifest.get("source_receipts")
    if not isinstance(source_receipts, dict) or set(source_receipts) != set(
        PINNED_SOURCE_RECEIPTS
    ):
        raise ReadModelError("Manifest receipt set is incomplete or unexpected")
    for name, expected in PINNED_SOURCE_RECEIPTS.items():
        item = source_receipts[name]
        if not isinstance(item, dict) or set(item) != {"path", "sha256"} or item != expected:
            raise ReadModelError(f"Manifest receipt reference is not approved: {name}")

    source_files = manifest.get("source_files")
    if not isinstance(source_files, dict) or set(source_files) != set(PINNED_SOURCE_FILES):
        raise ReadModelError("Manifest source file set is incomplete or unexpected")
    for name, expected in PINNED_SOURCE_FILES.items():
        item = source_files[name]
        if not isinstance(item, dict) or set(item) != {"path", "sha256", "row_count"}:
            raise ReadModelError(f"Manifest source schema is invalid: {name}")
        if (
            item.get("sha256") != expected["sha256"]
            or item.get("row_count") != expected["row_count"]
            or not isinstance(item.get("path"), str)
            or not item["path"].strip()
        ):
            raise ReadModelError(f"Manifest source identity is not approved: {name}")
        if is_default_manifest and item["path"] != expected["path"]:
            raise ReadModelError(f"Default manifest source path changed: {name}")

    if manifest.get("expected_counts") != PINNED_EXPECTED_COUNTS:
        raise ReadModelError("Manifest row counts do not match the completed receipt")
    if manifest.get("formal_rank_counts_by_window_k") != PINNED_FORMAL_RANK_COUNTS_BY_WINDOW_K:
        raise ReadModelError("Manifest ranking totals do not match the completed receipt")
    if manifest.get("reference") != PINNED_REFERENCE:
        raise ReadModelError("Manifest research reference identity is unexpected")
    return manifest, manifest_sha256


def _resolve_source_path(manifest_path: Path, raw_path: str, label: str) -> Path:
    if _is_default_manifest(manifest_path):
        return Path(raw_path)

    relative_path = Path(raw_path)
    if (
        relative_path.is_absolute()
        or PureWindowsPath(raw_path).is_absolute()
        or ".." in relative_path.parts
        or ".." in PureWindowsPath(raw_path).parts
        or raw_path.startswith("~")
    ):
        raise ReadModelError(f"Unapproved external or escaping source path for {label}")
    try:
        manifest_root = manifest_path.parent.resolve(strict=True)
        source_path = (manifest_root / relative_path).resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise ReadModelError(f"Cannot resolve manifest source for {label}") from exc
    try:
        source_path.relative_to(manifest_root)
    except ValueError as exc:
        raise ReadModelError(f"Manifest source escapes its directory for {label}") from exc
    if not source_path.is_file():
        raise ReadModelError(f"Manifest source is not a file for {label}")
    return source_path


def _read_verified_receipt(item: Mapping[str, Any], label: str) -> Mapping[str, Any]:
    path = Path(item["path"])
    if _sha256(path) != item["sha256"]:
        raise ReadModelError(f"Source receipt SHA mismatch: {path}")
    try:
        with path.open("r", encoding="utf-8") as stream:
            receipt = json.load(stream)
    except (OSError, json.JSONDecodeError) as exc:
        raise ReadModelError(f"Cannot read source receipt: {path}") from exc
    if receipt.get("task_id") != label or receipt.get("task_lifecycle_state") != "COMPLETED":
        raise ReadModelError(f"Source receipt identity or lifecycle mismatch: {path}")
    return receipt


def _verify_receipt_links(
    manifest: Mapping[str, Any], receipts: Mapping[str, Mapping[str, Any]]
) -> None:
    history = receipts["history_contract"]
    owner = receipts["owner_ranking"]
    retention = receipts["method_retention"]
    canonical_commit = manifest["canonical_source_commit"]
    expected_receipt_ids = {
        "history_contract": "NUMBER2_D_STANDARD_HISTORY_CONTRACT_READ_1030_R1",
        "owner_ranking": "NUMBER2_D_OWNER_RANKING_CONSOLIDATION_20261102_R1",
        "method_retention": "NUMBER2_D_ALL_BACKTEST_METHOD_RETENTION_20261102_R1",
    }
    for key, expected_id in expected_receipt_ids.items():
        if receipts[key].get("task_id") != expected_id:
            raise ReadModelError(f"Unexpected task identity in {key} receipt")
    if history.get("data_identity", {}).get("SOURCE_COMMIT") != canonical_commit:
        raise ReadModelError("History contract commit does not match the manifest")
    if (
        history.get("data_identity", {}).get("HISTORICAL_DATA_SHA256")
        != manifest["reference"]["historical_source_sha256"]
    ):
        raise ReadModelError("History data SHA does not match the manifest")
    if owner.get("source_identity", {}).get("canonical_source_commit") != canonical_commit:
        raise ReadModelError("Owner ranking source commit does not match the manifest")
    if owner.get("source_integrity", {}).get("required_sources_missing") != []:
        raise ReadModelError("Owner receipt reports missing required sources")

    expected_output_names = {
        "rankings": "owner_all_horizon_ranks.csv",
        "scores": "owner_all_horizon_scores.csv",
        "method_status": "owner_all_methods_status.csv",
        "manual_review": "owner_manual_review.csv",
    }
    owner_hashes = owner.get("output_hashes", {})
    for key, filename in expected_output_names.items():
        item = manifest["source_files"][key]
        if Path(item["path"]).name != filename or owner_hashes.get(filename) != item["sha256"]:
            raise ReadModelError(f"Owner receipt does not claim the pinned {key} source")
    retained_item = manifest["source_files"]["retained_methods"]
    canonical_retained_path = PINNED_SOURCE_FILES["retained_methods"]["path"]
    if owner.get("source_sha256", {}).get(canonical_retained_path) != retained_item["sha256"]:
        raise ReadModelError("Owner receipt does not claim the pinned retention CSV")

    counts = manifest["expected_counts"]
    accounting = owner.get("accounting", {})
    owner_count_claims = {
        "all_score_cells": counts["score_rows"],
        "all_status_rows": counts["status_rows"],
        "owner_manual_review_rows": counts["manual_review_rows"],
        "combined_rank_table_rows": counts["formal_rank_rows"] + counts["descriptive_rank_rows"],
        "final_formal_rank_rows": counts["formal_rank_rows"],
        "h24_descriptive_version_rows": counts["descriptive_rank_rows"],
    }
    if any(accounting.get(key) != value for key, value in owner_count_claims.items()):
        raise ReadModelError("Owner receipt row counts do not match the manifest")
    retention_count_claims = {
        "retained_record_count": counts["retained_rows"],
        "source_identity_count": counts["source_coverage_identities"],
    }
    if any(retention.get(key) != value for key, value in retention_count_claims.items()):
        raise ReadModelError("Retention receipt counts do not match the manifest")


def load_read_model(manifest_path: str | Path | None = None) -> ReadModel:
    """Load exact CSV inputs from the manifest and verify all receipt identities.

    The optional path is local startup configuration; HTTP requests cannot select it.
    Relative CSV paths in a configured manifest stay inside that manifest's directory.
    """
    if manifest_path is not None and not str(manifest_path).strip():
        raise ReadModelError(f"{MANIFEST_PATH_ENV} must not be empty")
    if manifest_path is None:
        configured_path = os.environ.get(MANIFEST_PATH_ENV)
        if configured_path is not None:
            if not configured_path.strip():
                raise ReadModelError(f"{MANIFEST_PATH_ENV} must not be empty")
            manifest_path = configured_path
        else:
            manifest_path = DEFAULT_MANIFEST_PATH
    manifest_file = Path(manifest_path)
    manifest, manifest_sha256 = _load_manifest(manifest_file)
    resolved_source_paths = {
        name: _resolve_source_path(manifest_file, item["path"], name)
        for name, item in manifest["source_files"].items()
    }
    receipt_ids = {
        "history_contract": "NUMBER2_D_STANDARD_HISTORY_CONTRACT_READ_1030_R1",
        "owner_ranking": "NUMBER2_D_OWNER_RANKING_CONSOLIDATION_20261102_R1",
        "method_retention": "NUMBER2_D_ALL_BACKTEST_METHOD_RETENTION_20261102_R1",
    }
    receipts = {
        key: _read_verified_receipt(item, receipt_ids[key])
        for key, item in manifest["source_receipts"].items()
    }
    _verify_receipt_links(manifest, receipts)

    expected_counts = manifest["expected_counts"]
    expected_by_source = {
        "rankings": expected_counts["formal_rank_rows"] + expected_counts["descriptive_rank_rows"],
        "scores": expected_counts["score_rows"],
        "method_status": expected_counts["status_rows"],
        "manual_review": expected_counts["manual_review_rows"],
        "retained_methods": expected_counts["retained_rows"],
    }
    sources: dict[str, tuple[Mapping[str, Any], ...]] = {}
    for name in sorted(expected_by_source):
        item = manifest["source_files"][name]
        path = resolved_source_paths[name]
        rows = _read_csv(path, name, item["sha256"], item["row_count"])
        if item["row_count"] != expected_by_source[name]:
            raise ReadModelError(f"Manifest count does not match receipt for {name}")
        sources[name] = rows

    _validate_records(manifest, sources)
    status_by_id = {row["status_record_id"]: row for row in sources["method_status"]}
    manual_by_id = {row["status_record_id"]: row for row in sources["manual_review"]}
    merged_status: list[Mapping[str, Any]] = []
    for status_id in sorted(status_by_id):
        row = dict(status_by_id[status_id])
        manual = manual_by_id[status_id]
        for field in MANUAL_FIELDS:
            row[field] = manual[field]
        merged_status.append(MappingProxyType(row))

    # Preserve the historical version while making it independent of local
    # source locations. Every path-independent identity field above is pinned.
    source_identity = {
        "manifest_sha256": PINNED_MANIFEST_SHA256,
        "source_task_id": manifest["source_task_id"],
        "source_receipts": {
            key: dict(value) for key, value in sorted(PINNED_SOURCE_RECEIPTS.items())
        },
        "canonical_source_commit": manifest["canonical_source_commit"],
        "source_files": {
            key: dict(value) for key, value in sorted(PINNED_SOURCE_FILES.items())
        },
    }
    identity_bytes = json.dumps(
        source_identity, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    data_version = hashlib.sha256(identity_bytes).hexdigest()
    score_indexes = _build_score_indexes(sources["scores"])
    return ReadModel(
        manifest=MappingProxyType(manifest),
        manifest_path=manifest_file.resolve(),
        manifest_sha256=manifest_sha256,
        data_version=data_version,
        rankings=tuple(sorted(sources["rankings"], key=_rank_sort_key)),
        scores=tuple(sorted(sources["scores"], key=_score_sort_key)),
        method_status=tuple(merged_status),
        retained_methods=tuple(
            sorted(sources["retained_methods"], key=lambda row: str(row["record_id"]))
        ),
        score_indexes=MappingProxyType(score_indexes),
    )


def _validate_records(
    manifest: Mapping[str, Any], sources: Mapping[str, tuple[Mapping[str, Any], ...]]
) -> None:
    status_rows = sources["method_status"]
    manual_rows = sources["manual_review"]
    retained_rows = sources["retained_methods"]
    rankings = sources["rankings"]
    scores = sources["scores"]

    _require_unique(status_rows, "status_record_id", "method_status")
    _require_unique(manual_rows, "status_record_id", "manual_review")
    _require_unique(retained_rows, "record_id", "retained_methods")
    status_ids = {row["status_record_id"] for row in status_rows}
    manual_ids = {row["status_record_id"] for row in manual_rows}
    if status_ids != manual_ids:
        raise ReadModelError("Manual review IDs do not exactly match status IDs")
    manual_by_id = {row["status_record_id"]: row for row in manual_rows}
    for status in status_rows:
        manual = manual_by_id[status["status_record_id"]]
        for field in MANUAL_FIELDS:
            if status[field] != manual[field]:
                raise ReadModelError(
                    f"Manual field mismatch for {status['status_record_id']}: {field}"
                )

    rank_type_counts: dict[str, int] = {}
    formal_by_window_k: dict[str, int] = {}
    for row in rankings:
        rank_type = row["rank_type"]
        rank_type_counts[rank_type] = rank_type_counts.get(rank_type, 0) + 1
        if row["K"] not in K_VALUES or row["window"] not in WINDOWS:
            raise ReadModelError("Ranking source contains an unsupported K or window")
        if rank_type == "FORMAL":
            if row["formal_rank"] is None or row["descriptive_rank"] is not None:
                raise ReadModelError("Formal ranking row has an invalid rank field")
            key = f"{row['window']}_K{row['K']}"
            formal_by_window_k[key] = formal_by_window_k.get(key, 0) + 1
        elif rank_type == "DESCRIPTIVE_VERSION_REVIEW":
            if row["formal_rank"] is not None or row["descriptive_rank"] is None:
                raise ReadModelError("Descriptive row must not carry a formal rank")
        else:
            raise ReadModelError(f"Unexpected ranking type: {rank_type}")

    counts = manifest["expected_counts"]
    if rank_type_counts != {
        "FORMAL": counts["formal_rank_rows"],
        "DESCRIPTIVE_VERSION_REVIEW": counts["descriptive_rank_rows"],
    }:
        raise ReadModelError("Ranking type totals do not match the completed receipt")
    if formal_by_window_k != manifest["formal_rank_counts_by_window_k"]:
        raise ReadModelError("Formal rank K/window totals do not match the completed receipt")
    coverage_count = sum(row["record_kind"] == "SOURCE_COVERAGE_IDENTITY" for row in retained_rows)
    if coverage_count != counts["source_coverage_identities"]:
        raise ReadModelError("Retained source coverage identity count does not match the receipt")
    score_keys = [tuple(row.get(field) for field in SCORE_IDENTITY_FIELDS) for row in scores]
    if len(score_keys) != len(set(score_keys)):
        raise ReadModelError("Score source contains duplicate complete identities")


def _require_unique(rows: Iterable[Mapping[str, Any]], field: str, label: str) -> None:
    values = [row.get(field) for row in rows]
    if any(value in (None, "") for value in values) or len(values) != len(set(values)):
        raise ReadModelError(f"Missing or duplicate {field} in {label}")


def _rank_sort_key(row: Mapping[str, Any]) -> tuple[Any, ...]:
    rank = row["formal_rank"] if row["rank_type"] == "FORMAL" else row["descriptive_rank"]
    return (
        row["K"],
        row["window"],
        row["rank_type"],
        rank,
        str(row.get("strategy_id") or ""),
        str(row.get("strategy_version") or ""),
        str(row.get("policy_version") or ""),
        str(row.get("source_task_id") or ""),
        str(row.get("origin_task_id") or ""),
        str(row.get("identity_key") or ""),
        str(row.get("source_sha256") or ""),
    )


def _score_sort_key(row: Mapping[str, Any]) -> tuple[str, ...]:
    return tuple(str(row.get(field) or "") for field in SCORE_IDENTITY_FIELDS)


def _build_score_indexes(
    rows: tuple[Mapping[str, Any], ...],
) -> dict[str, Mapping[Any, tuple[Mapping[str, Any], ...]]]:
    fields = (
        "strategy_id",
        "strategy_version",
        "policy_version",
        "algorithm_version",
        "K",
        "window",
    )
    result: dict[str, Mapping[Any, tuple[Mapping[str, Any], ...]]] = {}
    for field in fields:
        grouped: dict[Any, list[Mapping[str, Any]]] = {}
        for row in rows:
            grouped.setdefault(row.get(field), []).append(row)
        result[field] = MappingProxyType(
            {value: tuple(sorted(group, key=_score_sort_key)) for value, group in grouped.items()}
        )
    return result


def _source_metadata(model: ReadModel) -> dict[str, Any]:
    manifest = model.manifest
    return {
        "api_version": API_VERSION,
        "data_version": model.data_version,
        "source_task": {
            "task_id": manifest["source_task_id"],
            "lane": manifest["source_task_lane"],
            "canonical_source_commit": manifest["canonical_source_commit"],
        },
        "source_manifest": {
            "path": str(model.manifest_path),
            "sha256": model.manifest_sha256,
        },
        "source_receipts": {
            key: dict(value) for key, value in sorted(manifest["source_receipts"].items())
        },
        "source_files": {
            key: dict(value) for key, value in sorted(manifest["source_files"].items())
        },
        "source_reference": dict(manifest["reference"]),
    }


def _json_row(row: Mapping[str, Any]) -> dict[str, Any]:
    return dict(row)


def _project_row(row: Mapping[str, Any], fields: Iterable[str]) -> dict[str, Any]:
    return {field: row.get(field) for field in fields}


def _query(environ: Mapping[str, Any], allowed: set[str]) -> dict[str, str]:
    try:
        parsed = parse_qs(
            environ.get("QUERY_STRING", ""), keep_blank_values=True, strict_parsing=True
        )
    except ValueError as exc:
        raise _BadRequest("Malformed query string") from exc
    unknown = set(parsed).difference(allowed)
    if unknown:
        raise _BadRequest(f"Unsupported query parameters: {', '.join(sorted(unknown))}")
    result: dict[str, str] = {}
    for key, values in parsed.items():
        if len(values) != 1:
            raise _BadRequest(f"Parameter must appear once: {key}")
        result[key] = values[0]
    return result


class _BadRequest(ValueError):
    pass


def _required(query: Mapping[str, str], name: str) -> str:
    value = query.get(name)
    if value is None or value == "":
        raise _BadRequest(f"Missing required parameter: {name}")
    return value


def _parse_k(value: str) -> int:
    if value not in {"2", "3", "5"}:
        raise _BadRequest("K must be one of 2, 3, or 5")
    return int(value)


def _parse_window(value: str) -> str:
    normalised = value.upper()
    if normalised not in WINDOWS:
        raise _BadRequest("window must be LONG, MID, or SHORT")
    return normalised


def _parse_pagination(query: Mapping[str, str]) -> tuple[int, int]:
    try:
        offset = int(query.get("offset", "0"))
        limit = int(query.get("limit", "100"))
    except ValueError as exc:
        raise _BadRequest("offset and limit must be integers") from exc
    if offset < 0 or offset > 1_000_000:
        raise _BadRequest("offset must be between 0 and 1000000")
    if limit < 1 or limit > 500:
        raise _BadRequest("limit must be between 1 and 500")
    return offset, limit


def _version_mismatch(model: ReadModel, query: Mapping[str, str]) -> dict[str, Any] | None:
    requested = query.get("data_version")
    if requested is None or requested == model.data_version:
        return None
    return {
        **_source_metadata(model),
        "error": "source_version_mismatch",
        "message": "The requested data_version does not match the pinned D source.",
    }


def _response_for(model: ReadModel, path: str, query_string: str) -> tuple[int, dict[str, Any]]:
    metadata = _source_metadata(model)
    if path == "/v1/research/backtests/strategies":
        query = _query({"QUERY_STRING": query_string}, {"data_version"})
        mismatch = _version_mismatch(model, query)
        if mismatch is not None:
            return HTTPStatus.CONFLICT, mismatch
        coverage_count = sum(
            row["record_kind"] == "SOURCE_COVERAGE_IDENTITY" for row in model.retained_methods
        )
        return HTTPStatus.OK, {
            **metadata,
            "counts": {
                "status_rows": len(model.method_status),
                "retained_records": len(model.retained_methods),
                "source_coverage_identities": coverage_count,
            },
            "strategies": [_project_row(row, STRATEGY_FIELDS) for row in model.method_status],
            "retention_evidence": [
                _project_row(row, RETENTION_FIELDS) for row in model.retained_methods
            ],
        }

    if path == "/v1/research/backtests/rankings":
        query = _query(
            {"QUERY_STRING": query_string},
            {"K", "window", "type", "offset", "limit", "data_version"},
        )
        mismatch = _version_mismatch(model, query)
        if mismatch is not None:
            return HTTPStatus.CONFLICT, mismatch
        k = _parse_k(_required(query, "K"))
        window = _parse_window(_required(query, "window"))
        requested_type = _required(query, "type").lower()
        if requested_type not in RANK_TYPES:
            raise _BadRequest("type must be formal or descriptive")
        rank_type = RANK_TYPES[requested_type]
        offset, limit = _parse_pagination(query)
        matches = tuple(
            row
            for row in model.rankings
            if row["K"] == k and row["window"] == window and row["rank_type"] == rank_type
        )
        page = matches[offset : offset + limit]
        result_rows = []
        for row in page:
            item = _json_row(row)
            if rank_type == "FORMAL":
                item["rank"] = row["formal_rank"]
                item["rank_basis"] = "formal_rank"
            else:
                item["formal_rank"] = None
                item["rank"] = row["descriptive_rank"]
                item["rank_basis"] = "descriptive_rank"
            result_rows.append(item)
        return HTTPStatus.OK, {
            **metadata,
            "query": {
                "K": k,
                "window": window,
                "type": requested_type,
                "offset": offset,
                "limit": limit,
            },
            "count": len(matches),
            "returned": len(result_rows),
            "rankings": result_rows,
        }

    if path == "/v1/research/backtests/scores":
        query = _query(
            {"QUERY_STRING": query_string},
            {
                "strategy_id",
                "strategy_version",
                "policy_version",
                "algorithm_version",
                "K",
                "window",
                "offset",
                "limit",
                "data_version",
            },
        )
        mismatch = _version_mismatch(model, query)
        if mismatch is not None:
            return HTTPStatus.CONFLICT, mismatch
        filters: dict[str, Any] = {}
        for key in ("strategy_id", "strategy_version", "algorithm_version"):
            if key in query:
                filters[key] = _required(query, key)
        if "policy_version" in query:
            filters["policy_version"] = query["policy_version"] or None
        if "K" in query:
            filters["K"] = _parse_k(query["K"])
        if "window" in query:
            filters["window"] = _parse_window(_required(query, "window"))
        matches = model.scores_for(filters)
        offset, limit = _parse_pagination(query)
        page = matches[offset : offset + limit]
        return HTTPStatus.OK, {
            **metadata,
            "query": {
                **{key: query[key] for key in sorted(query) if key not in {"offset", "limit"}},
                "offset": offset,
                "limit": limit,
            },
            "count": len(matches),
            "returned": len(page),
            "scores": [_json_row(row) for row in page],
        }

    return HTTPStatus.NOT_FOUND, {
        "api_version": API_VERSION,
        "error": "not_found",
        "message": "Unknown endpoint",
    }


def create_research_backtests_router(
    read_model_provider: Callable[[], ReadModel] | None = None,
) -> APIRouter:
    """Register the D read model on the host FastAPI application."""
    router = APIRouter(prefix="/api/v1/research/backtests", tags=["research-backtests"])
    environment_manifest_path = os.environ.get(MANIFEST_PATH_ENV)
    configured_manifest_path = (
        DEFAULT_MANIFEST_PATH
        if environment_manifest_path is None
        else environment_manifest_path
    )

    def configured_provider() -> ReadModel:
        return load_read_model(configured_manifest_path)

    def respond(path: str, request: Request) -> JSONResponse:
        try:
            provider = read_model_provider or configured_provider
            model = provider()
            status, payload = _response_for(model, path, request.url.query)
        except _BadRequest as exc:
            status = HTTPStatus.BAD_REQUEST
            payload = {
                "api_version": API_VERSION,
                "error": "invalid_request",
                "message": str(exc),
            }
        except ReadModelError as exc:
            status = HTTPStatus.SERVICE_UNAVAILABLE
            payload = {
                "api_version": API_VERSION,
                "error": "source_unavailable",
                "message": str(exc),
            }
        except Exception:
            status = HTTPStatus.INTERNAL_SERVER_ERROR
            payload = {
                "api_version": API_VERSION,
                "error": "internal_error",
                "message": "The backtest read request could not be completed.",
            }
        return JSONResponse(
            status_code=status.value,
            content=payload,
            headers={"Cache-Control": "no-store"},
        )

    @router.get("/strategies")
    def strategies(request: Request) -> JSONResponse:
        return respond("/v1/research/backtests/strategies", request)

    @router.get("/rankings")
    def rankings(request: Request) -> JSONResponse:
        return respond("/v1/research/backtests/rankings", request)

    @router.get("/scores")
    def scores(request: Request) -> JSONResponse:
        return respond("/v1/research/backtests/scores", request)

    return router
