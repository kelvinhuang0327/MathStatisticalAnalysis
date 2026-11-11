"""Read-only API projection for the sealed-084 B649 research replays."""

# pyright: reportUnusedFunction=false
# (route handlers are registered by FastAPI decorators, not called by name)

from __future__ import annotations

import csv
import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Literal

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from lottolab.interfaces.api.strategy_catalog import API_PREFIX

SOURCE_CUTOFF = "115000084"
SOURCE_TIER = "SEALED_ATTESTED_DRAW_ROWS"
REPLAY_STATUS = "SEALED_084_RESEARCH_REPLAY"
WINDOWS = ("FULL", "RECENT_750", "RECENT_300", "RECENT_50")
HORIZON_STRATEGY_ID = "b649_new_horizon_minimax_disagreement_r1"


@dataclass(frozen=True)
class _SourceSpec:
    task_id: str
    strategy_ids: tuple[str, ...]
    strategy_version: str
    ticket_counts: tuple[int, ...]
    expected_hashes: dict[str, str]


_RENEWAL_TASK = "NUMBER2_A_B649_RENEWAL_K235_SEALED084_REPLAY_20261102_R1"
_TE_TASK = "NUMBER2_A_B649_CONDITIONAL_TE_K235_SEALED084_REPLAY_20261102_R1"
_HORIZON_TASK = "NUMBER2_A_B649_HORIZON_V01_K2_SEALED084_REPLAY_20261102_R1"
_ARTIFACT_NAMES = (
    "result.json",
    "four_window_results.csv",
    "per_issue_results.jsonl",
    "draw_issue_manifest.json",
)
_ARCHIVE_TASK_ID = "NUMBER2_A_B649_084_ARCHIVE_20261102_R1"
_ARCHIVE_MANIFEST_NAME = "archive_manifest.json"
_ARCHIVE_MANIFEST_SHA256 = "7816f6e7b6d12e0ae08a21eaa5ceb3232c3982938c686b201cefc120e45fd2fe"
_ARCHIVE_FILE_NAMES = frozenset((*_ARTIFACT_NAMES, "final_reply.md"))
_SOURCES = (
    _SourceSpec(
        task_id=_RENEWAL_TASK,
        strategy_ids=(
            "research_causal_renewal_hazard_k2",
            "research_causal_renewal_hazard_k3",
            "research_causal_renewal_hazard_k5",
        ),
        strategy_version="v1.0",
        ticket_counts=(2, 3, 5),
        expected_hashes={
            "result.json": "fb096f78406bb03672b4ec7cb2cba6f5dd0d7c1f8b93d332a55f2cec90f741cf",
            "four_window_results.csv": (
                "b8a138d4f7614adc848d93f853311ac2de15ee4e8599df060feb1c0435e2f5eb"
            ),
            "per_issue_results.jsonl": (
                "0f7a7d852e8d0b6470a7a69f8020b3fae2b2706884c089c1e5972ef03c6b8282"
            ),
            "draw_issue_manifest.json": (
                "7ac7f3fb15d1aca655164fe891739cdb195e8adc6459feeb9b55496edf5094fa"
            ),
        },
    ),
    _SourceSpec(
        task_id=_TE_TASK,
        strategy_ids=(
            "research_conditional_transfer_entropy_k2",
            "research_conditional_transfer_entropy_k3",
            "research_conditional_transfer_entropy_k5",
        ),
        strategy_version="v1.0",
        ticket_counts=(2, 3, 5),
        expected_hashes={
            "result.json": "33853319770c85bab08209e3dd4868914fdce6579ab8f50880420c91de20a4ef",
            "four_window_results.csv": (
                "c87dc85035cf2ad0d098e5446b33b0aba202f8b8b32c397bff96b7e2452eb48b"
            ),
            "per_issue_results.jsonl": (
                "2729edf3b154cb9b59ae8f9724cbdbe5c59cf3c6eb943288c34c0d637419034a"
            ),
            "draw_issue_manifest.json": (
                "e889f2fd864344b281b63cb5abda2e91dd8a9db1d34484e010c0ab337c082b24"
            ),
        },
    ),
    _SourceSpec(
        task_id=_HORIZON_TASK,
        strategy_ids=(HORIZON_STRATEGY_ID,),
        strategy_version="v0.1",
        ticket_counts=(2,),
        expected_hashes={
            "result.json": "b9a0bcf3c6d558c502d9dcb205d286029f736389b7aaaa056a0cb99a90cec9b5",
            "four_window_results.csv": (
                "58f80bd5d2b343164a103ae5ba579dc64a5f90f650ab469cb532f3c27db51581"
            ),
            "per_issue_results.jsonl": (
                "c89e1c6717d49d50a77b15bd3c307d9472980244b10b28d0f2eaae9404de214d"
            ),
            "draw_issue_manifest.json": (
                "5518cb318d03f619be8beda6b634ddf9f9b6c1f7edf7927e7a7aa3d38e316c60"
            ),
        },
    ),
)


class _SourceUnavailable(Exception):
    def __init__(self, code: str, source_task_id: str | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.source_task_id = source_task_id


def _error_response(error: _SourceUnavailable) -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={
            "status": "SOURCE_UNAVAILABLE",
            "error_code": error.code,
            "source_task_id": error.source_task_id,
        },
    )


def _int_value(value: object, code: str, task_id: str) -> int:
    try:
        return int(str(value))
    except (TypeError, ValueError) as error:
        raise _SourceUnavailable(code, task_id) from error


def _float_value(value: object, code: str, task_id: str) -> float:
    try:
        result = float(str(value))
    except (TypeError, ValueError) as error:
        raise _SourceUnavailable(code, task_id) from error
    if not math.isfinite(result):
        raise _SourceUnavailable(code, task_id)
    return result


def _receipt_cells(
    result: dict[str, object], spec: _SourceSpec
) -> dict[tuple[str, str], tuple[int, int, float]]:
    cells: dict[tuple[str, str], tuple[int, int, float]] = {}
    raw_rows = result.get("window_results")
    if isinstance(raw_rows, list):
        for raw_row in raw_rows:
            if not isinstance(raw_row, dict):
                raise _SourceUnavailable("SOURCE_FORMAT_INVALID", spec.task_id)
            strategy_id = str(raw_row.get("strategy_id", ""))
            window = str(raw_row.get("window", ""))
            strategy_version = str(raw_row.get("strategy_version", raw_row.get("version", "")))
            ticket_count = _int_value(
                raw_row.get("ticket_count"), "SOURCE_IDENTITY_CONFLICT", spec.task_id
            )
            if (
                strategy_id not in spec.strategy_ids
                or strategy_version != spec.strategy_version
                or ticket_count != spec.ticket_counts[spec.strategy_ids.index(strategy_id)]
                or raw_row.get("game") != "BIG_LOTTO"
            ):
                raise _SourceUnavailable("SOURCE_IDENTITY_CONFLICT", spec.task_id)
            successes = _int_value(
                raw_row.get("successful_issues", raw_row.get("success_count")),
                "SOURCE_FORMAT_INVALID",
                spec.task_id,
            )
            evaluated = _int_value(
                raw_row.get("evaluated_issues"), "SOURCE_FORMAT_INVALID", spec.task_id
            )
            rate = _float_value(raw_row.get("success_rate"), "SOURCE_FORMAT_INVALID", spec.task_id)
            cells[(strategy_id, window)] = (successes, evaluated, rate)
        return cells

    raw_windows = result.get("windows")
    identity = result.get("generator_identity")
    if not isinstance(raw_windows, dict) or not isinstance(identity, dict):
        raise _SourceUnavailable("SOURCE_FORMAT_INVALID", spec.task_id)
    strategy_id = str(identity.get("strategy_id", ""))
    version = str(identity.get("version", ""))
    native_k = _int_value(identity.get("native_k"), "SOURCE_IDENTITY_CONFLICT", spec.task_id)
    if (
        strategy_id not in spec.strategy_ids
        or version != spec.strategy_version
        or native_k != spec.ticket_counts[spec.strategy_ids.index(strategy_id)]
    ):
        raise _SourceUnavailable("SOURCE_IDENTITY_CONFLICT", spec.task_id)
    for window, raw_metrics in raw_windows.items():
        if not isinstance(raw_metrics, dict):
            raise _SourceUnavailable("SOURCE_FORMAT_INVALID", spec.task_id)
        cells[(strategy_id, str(window))] = (
            _int_value(raw_metrics.get("success"), "SOURCE_FORMAT_INVALID", spec.task_id),
            _int_value(raw_metrics.get("eligible"), "SOURCE_FORMAT_INVALID", spec.task_id),
            _float_value(raw_metrics.get("rate"), "SOURCE_FORMAT_INVALID", spec.task_id),
        )
    return cells


def _normalise_csv_row(row: dict[str, str], spec: _SourceSpec) -> dict[str, object]:
    strategy_id = row.get("strategy_id") or (
        spec.strategy_ids[0] if len(spec.strategy_ids) == 1 else ""
    )
    strategy_version = row.get("strategy_version") or row.get("version") or spec.strategy_version
    window = row.get("window", "")
    if strategy_id not in spec.strategy_ids or strategy_version != spec.strategy_version:
        raise _SourceUnavailable("SOURCE_IDENTITY_CONFLICT", spec.task_id)
    if window not in WINDOWS:
        raise _SourceUnavailable("SOURCE_FORMAT_INVALID", spec.task_id)
    ticket_count = _int_value(
        row.get("ticket_count")
        or (str(spec.ticket_counts[0]) if len(spec.ticket_counts) == 1 else ""),
        "SOURCE_IDENTITY_CONFLICT",
        spec.task_id,
    )
    if ticket_count not in spec.ticket_counts:
        raise _SourceUnavailable("SOURCE_IDENTITY_CONFLICT", spec.task_id)
    expected_source_identity = f"{SOURCE_TIER}:{SOURCE_CUTOFF}"
    source_identity = row.get("source_identity") or row.get("source_snapshot")
    if source_identity and source_identity != expected_source_identity:
        raise _SourceUnavailable("SOURCE_IDENTITY_CONFLICT", spec.task_id)
    classification = row.get("result_classification")
    if classification and classification != REPLAY_STATUS:
        raise _SourceUnavailable("SOURCE_IDENTITY_CONFLICT", spec.task_id)
    successes = _int_value(
        row.get("successful_issues") or row.get("success_count"),
        "SOURCE_FORMAT_INVALID",
        spec.task_id,
    )
    evaluated = _int_value(
        row.get("evaluated_issues") or row.get("eligible_count"),
        "SOURCE_FORMAT_INVALID",
        spec.task_id,
    )
    if evaluated <= 0:
        raise _SourceUnavailable("EMPTY_DENOMINATOR", spec.task_id)
    if successes < 0 or successes > evaluated:
        raise _SourceUnavailable("INVALID_METRICS", spec.task_id)
    rate = _float_value(row.get("success_rate"), "SOURCE_FORMAT_INVALID", spec.task_id)
    if not math.isclose(rate, successes / evaluated, rel_tol=0.0, abs_tol=1e-15):
        raise _SourceUnavailable("SOURCE_RATE_MISMATCH", spec.task_id)
    return {
        "game": row.get("game") or "BIG_LOTTO",
        "strategy_id": strategy_id,
        "strategy_version": strategy_version,
        "ticket_count": ticket_count,
        "window": window,
        "successful_issues": successes,
        "evaluated_issues": evaluated,
        "success_rate": rate,
        "source_cutoff": SOURCE_CUTOFF,
        "source_tier": SOURCE_TIER,
        "source_task_id": spec.task_id,
        "historical_replay_status": REPLAY_STATUS,
        "owner_rank": None,
    }


def _load_source(
    source_dir: Path, spec: _SourceSpec
) -> tuple[list[dict[str, object]], dict[str, object]]:
    if not source_dir.is_dir():
        raise _SourceUnavailable("SOURCE_TASK_DIRECTORY_MISSING", spec.task_id)
    artifact_hashes: dict[str, str] = {}
    artifact_bytes: dict[str, bytes] = {}
    for name in _ARTIFACT_NAMES:
        artifact = source_dir / name
        try:
            data = artifact.read_bytes()
        except OSError as error:
            raise _SourceUnavailable("SOURCE_FILE_MISSING", spec.task_id) from error
        actual_hash = hashlib.sha256(data).hexdigest()
        expected_hash = spec.expected_hashes[name]
        if actual_hash != expected_hash:
            raise _SourceUnavailable("SOURCE_HASH_MISMATCH", spec.task_id)
        artifact_hashes[name] = actual_hash
        artifact_bytes[name] = data

    try:
        result = json.loads(artifact_bytes["result.json"])
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise _SourceUnavailable("SOURCE_FORMAT_INVALID", spec.task_id) from error
    if not isinstance(result, dict):
        raise _SourceUnavailable("SOURCE_FORMAT_INVALID", spec.task_id)
    if (
        result.get("task_id") != spec.task_id
        or result.get("task_lifecycle_state") != "COMPLETED"
        or result.get("source_tier") != SOURCE_TIER
    ):
        raise _SourceUnavailable("SOURCE_IDENTITY_CONFLICT", spec.task_id)
    cutoff_values = {
        str(result.get(key))
        for key in ("source_cutoff", "source_snapshot_cutoff", "cutoff_issue")
        if result.get(key) is not None
    }
    if SOURCE_CUTOFF not in cutoff_values:
        raise _SourceUnavailable("SOURCE_IDENTITY_CONFLICT", spec.task_id)

    declared_artifacts = result.get("artifacts")
    if isinstance(declared_artifacts, dict):
        for name in _ARTIFACT_NAMES[1:]:
            declaration = declared_artifacts.get(name)
            if isinstance(declaration, dict) and declaration.get("sha256") != artifact_hashes[name]:
                raise _SourceUnavailable("SOURCE_HASH_MISMATCH", spec.task_id)

    try:
        csv_text = artifact_bytes["four_window_results.csv"].decode("utf-8-sig")
        reader = csv.DictReader(csv_text.splitlines())
        if not reader.fieldnames:
            raise _SourceUnavailable("SOURCE_FORMAT_INVALID", spec.task_id)
        raw_rows = list(reader)
    except (UnicodeDecodeError, csv.Error) as error:
        raise _SourceUnavailable("SOURCE_FORMAT_INVALID", spec.task_id) from error

    normalised = [_normalise_csv_row(row, spec) for row in raw_rows]
    expected_count = len(spec.strategy_ids) * len(WINDOWS)
    keys = [
        (
            str(row["strategy_id"]),
            str(row["strategy_version"]),
            int(row["ticket_count"]),
            str(row["window"]),
        )
        for row in normalised
    ]
    if len(normalised) != expected_count or len(set(keys)) != expected_count:
        raise _SourceUnavailable("SOURCE_WINDOW_MISSING_OR_DUPLICATE", spec.task_id)
    for strategy_id in spec.strategy_ids:
        strategy_rows = [row for row in normalised if row["strategy_id"] == strategy_id]
        if {row["window"] for row in strategy_rows} != set(WINDOWS):
            raise _SourceUnavailable("SOURCE_WINDOW_MISSING_OR_DUPLICATE", spec.task_id)

    receipt_cells = _receipt_cells(result, spec)
    if len(receipt_cells) != expected_count:
        raise _SourceUnavailable("SOURCE_RECEIPT_CSV_MISMATCH", spec.task_id)
    for row in normalised:
        identity = (str(row["strategy_id"]), str(row["window"]))
        expected_metrics = receipt_cells.get(identity)
        actual_metrics = (
            int(row["successful_issues"]),
            int(row["evaluated_issues"]),
            float(row["success_rate"]),
        )
        if (
            expected_metrics is None
            or expected_metrics[:2] != actual_metrics[:2]
            or not math.isclose(expected_metrics[2], actual_metrics[2], rel_tol=0.0, abs_tol=1e-15)
        ):
            raise _SourceUnavailable("SOURCE_RECEIPT_CSV_MISMATCH", spec.task_id)

    artifact_identity_payload = json.dumps(
        {"source_task_id": spec.task_id, "artifacts": artifact_hashes},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    artifact_identity = "sha256:" + hashlib.sha256(artifact_identity_payload).hexdigest()
    for row in normalised:
        if row["strategy_id"] == HORIZON_STRATEGY_ID and row["window"] == "FULL":
            row["comparability_status"] = "NOT_DIRECTLY_COMPARABLE_ELIGIBLE_ISSUE_SET"
        else:
            row["comparability_status"] = "COMPARABLE_WITHIN_MATCHED_WINDOW"
        row["source_artifact_identity"] = artifact_identity
        row["source_validation_status"] = str(result.get("validation_status", "UNKNOWN"))
        row["draw_source_status"] = str(result.get("draw_source_status", "NOT_RECORDED"))
        row["original_draw_data_v3_status"] = str(
            result.get("original_authority_status")
            or result.get("original_payload_parity_status")
            or "NOT_DIRECTLY_VERIFIED"
        )
        row["source_gaps"] = result.get("source_gaps")

    source_status: dict[str, object] = {
        "source_task_id": spec.task_id,
        "source_artifact_identity": artifact_identity,
        "source_validation_status": str(result.get("validation_status", "UNKNOWN")),
        "draw_source_status": str(result.get("draw_source_status", "NOT_RECORDED")),
        "original_draw_data_v3_status": str(
            result.get("original_authority_status")
            or result.get("original_payload_parity_status")
            or "NOT_DIRECTLY_VERIFIED"
        ),
        "source_gaps": result.get("source_gaps"),
    }
    return normalised, source_status


def _load_archive_source_directories(root: Path) -> dict[str, Path] | None:
    manifest_path = root / _ARCHIVE_MANIFEST_NAME
    if not manifest_path.exists():
        if (root / "restore_check.json").exists():
            raise _SourceUnavailable("SOURCE_ARCHIVE_MANIFEST_MISSING")
        return None
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise _SourceUnavailable("SOURCE_ARCHIVE_MANIFEST_INVALID")

    try:
        manifest_bytes = manifest_path.read_bytes()
    except OSError as error:
        raise _SourceUnavailable("SOURCE_ARCHIVE_MANIFEST_MISSING") from error
    if hashlib.sha256(manifest_bytes).hexdigest() != _ARCHIVE_MANIFEST_SHA256:
        raise _SourceUnavailable("SOURCE_ARCHIVE_MANIFEST_HASH_MISMATCH")

    try:
        manifest = json.loads(manifest_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise _SourceUnavailable("SOURCE_ARCHIVE_MANIFEST_INVALID") from error
    if not isinstance(manifest, dict):
        raise _SourceUnavailable("SOURCE_ARCHIVE_MANIFEST_INVALID")
    if manifest.get("schema_version") != 1 or manifest.get("task_id") != _ARCHIVE_TASK_ID:
        raise _SourceUnavailable("SOURCE_ARCHIVE_IDENTITY_CONFLICT")

    expected_ids = {spec.task_id for spec in _SOURCES}
    source_rows = manifest.get("source_tasks")
    if not isinstance(source_rows, list) or len(source_rows) != len(expected_ids):
        raise _SourceUnavailable("SOURCE_ARCHIVE_MANIFEST_INVALID")

    sources: dict[str, dict[str, str]] = {}
    used_subdirectories: set[str] = set()
    for row in source_rows:
        if not isinstance(row, dict):
            raise _SourceUnavailable("SOURCE_ARCHIVE_MANIFEST_INVALID")
        task_id = row.get("task_id")
        source_group = row.get("source_group")
        subdirectory = row.get("archive_subdirectory")
        subdirectory_path = PurePosixPath(subdirectory) if isinstance(subdirectory, str) else None
        if (
            task_id not in expected_ids
            or task_id in sources
            or not isinstance(source_group, str)
            or not source_group
            or subdirectory_path is None
            or len(subdirectory_path.parts) != 1
            or subdirectory_path.is_absolute()
            or subdirectory_path.name in {".", ".."}
            or subdirectory_path.name in used_subdirectories
            or row.get("task_lifecycle_state") != "COMPLETED"
            or row.get("source_tier") != SOURCE_TIER
            or row.get("cutoff") != SOURCE_CUTOFF
        ):
            raise _SourceUnavailable("SOURCE_ARCHIVE_IDENTITY_CONFLICT", str(task_id or ""))
        sources[task_id] = {
            "source_group": source_group,
            "archive_subdirectory": subdirectory_path.as_posix(),
        }
        used_subdirectories.add(subdirectory_path.name)
    if set(sources) != expected_ids:
        raise _SourceUnavailable("SOURCE_ARCHIVE_IDENTITY_CONFLICT")

    archived_files = manifest.get("archived_files")
    expected_file_count = len(_SOURCES) * len(_ARCHIVE_FILE_NAMES)
    if not isinstance(archived_files, list) or len(archived_files) != expected_file_count:
        raise _SourceUnavailable("SOURCE_ARCHIVE_MANIFEST_INVALID")

    specs = {spec.task_id: spec for spec in _SOURCES}
    files_by_task: dict[str, set[str]] = {task_id: set() for task_id in expected_ids}
    seen_archive_paths: set[str] = set()
    root_resolved = root.resolve()
    for row in archived_files:
        if not isinstance(row, dict):
            raise _SourceUnavailable("SOURCE_ARCHIVE_MANIFEST_INVALID")
        task_id = row.get("source_task_id")
        source = sources.get(task_id)
        relative_value = row.get("relative_source_path")
        archive_value = row.get("archive_relative_path")
        relative = PurePosixPath(relative_value) if isinstance(relative_value, str) else None
        archive_relative = PurePosixPath(archive_value) if isinstance(archive_value, str) else None
        if (
            source is None
            or row.get("source_group") != source["source_group"]
            or relative is None
            or len(relative.parts) != 1
            or relative.is_absolute()
            or relative.name in {".", ".."}
            or relative.name not in _ARCHIVE_FILE_NAMES
            or archive_relative is None
            or archive_relative.is_absolute()
            or archive_relative != PurePosixPath(source["archive_subdirectory"]) / relative
            or archive_relative.as_posix() in seen_archive_paths
        ):
            raise _SourceUnavailable("SOURCE_ARCHIVE_MANIFEST_INVALID", str(task_id or ""))

        name = relative.name
        files_by_task[task_id].add(name)
        seen_archive_paths.add(archive_relative.as_posix())
        try:
            byte_size = row["byte_size"]
            expected_hash = row["sha256"]
            if isinstance(byte_size, bool) or not isinstance(byte_size, int) or byte_size < 0:
                raise ValueError("invalid archive byte size")
            if not isinstance(expected_hash, str) or len(expected_hash) != 64:
                raise ValueError("invalid archive SHA-256")
            int(expected_hash, 16)
            artifact = root.joinpath(*archive_relative.parts)
            current = root
            for part in archive_relative.parts:
                current = current / part
                if current.is_symlink():
                    raise ValueError("archive path contains a symlink")
            resolved_artifact = artifact.resolve(strict=True)
            if root_resolved not in resolved_artifact.parents or not resolved_artifact.is_file():
                raise FileNotFoundError(str(artifact))
            actual_size = resolved_artifact.stat().st_size
        except (KeyError, ValueError) as error:
            raise _SourceUnavailable("SOURCE_ARCHIVE_MANIFEST_INVALID", task_id) from error
        except OSError as error:
            raise _SourceUnavailable("SOURCE_FILE_MISSING", task_id) from error

        spec = specs[task_id]
        pinned_hash = spec.expected_hashes.get(name)
        if actual_size != byte_size or (pinned_hash is not None and expected_hash != pinned_hash):
            raise _SourceUnavailable("SOURCE_HASH_MISMATCH", task_id)

    if any(names != _ARCHIVE_FILE_NAMES for names in files_by_task.values()):
        raise _SourceUnavailable("SOURCE_ARCHIVE_MANIFEST_INVALID")

    source_directories: dict[str, Path] = {}
    for task_id, source in sources.items():
        source_dir = root / source["archive_subdirectory"]
        try:
            resolved_dir = source_dir.resolve(strict=True)
        except OSError as error:
            raise _SourceUnavailable("SOURCE_TASK_DIRECTORY_MISSING", task_id) from error
        if root_resolved not in resolved_dir.parents or not resolved_dir.is_dir():
            raise _SourceUnavailable("SOURCE_TASK_DIRECTORY_MISSING", task_id)
        source_directories[task_id] = resolved_dir
    return source_directories


def _load_dataset(
    source_root: Path | None,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    if source_root is None:
        raise _SourceUnavailable("SOURCE_ROOT_NOT_CONFIGURED")
    if not source_root.is_absolute():
        raise _SourceUnavailable("SOURCE_ROOT_MUST_BE_ABSOLUTE")
    if not source_root.is_dir():
        raise _SourceUnavailable("SOURCE_ROOT_MISSING")
    archive_sources = _load_archive_source_directories(source_root)
    rows: list[dict[str, object]] = []
    source_statuses: list[dict[str, object]] = []
    for spec in _SOURCES:
        source_dir = (
            archive_sources[spec.task_id]
            if archive_sources is not None
            else source_root / spec.task_id
        )
        source_rows, source_status = _load_source(source_dir, spec)
        rows.extend(source_rows)
        source_statuses.append(source_status)
    expected_rows = sum(len(spec.strategy_ids) * len(WINDOWS) for spec in _SOURCES)
    identities = {
        (
            row["game"],
            row["strategy_id"],
            row["strategy_version"],
            row["ticket_count"],
            row["window"],
        )
        for row in rows
    }
    if len(rows) != expected_rows or len(identities) != expected_rows:
        raise _SourceUnavailable("SOURCE_DATASET_INCOMPLETE")
    return rows, source_statuses


def create_b649_sealed084_replays_router(source_root: Path | None) -> APIRouter:
    """Bind the checked source root without writing to it or loading it at startup."""

    router = APIRouter(prefix=API_PREFIX, tags=["b649-sealed-084-replays"])
    dataset_cache: tuple[list[dict[str, object]], list[dict[str, object]]] | None = None

    def dataset() -> tuple[list[dict[str, object]], list[dict[str, object]]]:
        nonlocal dataset_cache
        if dataset_cache is None:
            dataset_cache = _load_dataset(source_root)
        return dataset_cache

    @router.get(
        "/b649/sealed-084-replays/status",
        response_model=None,
        operation_id="getB649Sealed084ReplayStatus",
    )
    def status() -> dict[str, object] | JSONResponse:
        try:
            rows, sources = dataset()
        except _SourceUnavailable as error:
            return _error_response(error)
        return {
            "status": "READY",
            "game": "BIG_LOTTO",
            "source_cutoff": SOURCE_CUTOFF,
            "source_tier": SOURCE_TIER,
            "strategy_count": len({row["strategy_id"] for row in rows}),
            "returned_window_rows": len(rows),
            "sources": sources,
        }

    @router.get(
        "/b649/sealed-084-replays",
        response_model=None,
        operation_id="listB649Sealed084ResearchReplays",
    )
    def list_replays(
        strategy_id: str | None = Query(default=None),
        strategy_version: str | None = Query(default=None),
        ticket_count: int | None = Query(default=None, ge=1),
        window: Literal["FULL", "RECENT_750", "RECENT_300", "RECENT_50"] | None = Query(
            default=None
        ),
    ) -> dict[str, object] | JSONResponse:
        try:
            rows, sources = dataset()
        except _SourceUnavailable as error:
            return _error_response(error)
        filters = {
            "strategy_id": strategy_id,
            "strategy_version": strategy_version,
            "ticket_count": ticket_count,
            "window": window,
        }
        selected = [
            row
            for row in rows
            if all(value is None or row[key] == value for key, value in filters.items())
        ]
        if not selected:
            return JSONResponse(
                status_code=404,
                content={"status": "NO_MATCHING_RESULTS", "error_code": "RESULT_NOT_FOUND"},
            )
        return {
            "status": "READY",
            "game": "BIG_LOTTO",
            "source_cutoff": SOURCE_CUTOFF,
            "source_tier": SOURCE_TIER,
            "strategy_count": len({row["strategy_id"] for row in rows}),
            "returned_window_rows": len(selected),
            "sources": sources,
            "results": selected,
        }

    return router
