"""Read formal B649 per-draw backtests from the verified recovery ZIP."""

from __future__ import annotations

import hashlib
import json
import os
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

B649_RESEARCH_RECORD_ARCHIVE_ROOT_ENV = "LOTTOLAB_B649_RESEARCH_RECORD_ARCHIVE_ROOT"
B649_RESEARCH_RECORD_ARCHIVE_TASK_ID = "NUMBER2_C_BACKTEST_RECOVERY_BUNDLE_20261102_R1"
B649_RESEARCH_RECORD_ARCHIVE_SHA256 = (
    "60c045d887df681b3cda0e689474d318f568848a407bcb7e187ed06c8a2ad099"
)
B649_RESEARCH_RECORD_MANIFEST_SHA256 = (
    "89822698c8e98021b47f46485211d539e09445a9195362932b5348aa60042e40"
)
B649_RESEARCH_RECORD_SOURCE_AUTHORITY = "fe3aa81d3844ac11d4360447c243e90fe4a6613a"
B649_RESEARCH_RECORD_TOTAL = 82_971

_EXPECTED_SOURCE_COUNTS = {
    "NUMBER2_D_NATIVE_SUBSET_W50_K235_20261101_R1": 15_804,
    "NUMBER2_D_DECISION_OBJECTIVE_W50_1317_20261101_R1": 15_804,
    "NUMBER2_D_GROUP_DRO_CAUSAL_W50_20261101_R1": 19_755,
    "NUMBER2_D_SPECIAL_LAG_BUCKET_W50_K235_20261102_R1": 15_804,
    "NUMBER2_D_DRAW_ORDER_POSITION_SIGNAL_V1_20261102_R1": 15_804,
}
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

# These mappings were verified against one fixed row from every manifest-pinned
# formal JSONL. Values copied into the common response remain source values.
_SOURCE_FIELDS = {
    "NUMBER2_D_NATIVE_SUBSET_W50_K235_20261101_R1": {
        "tickets": "tickets",
        "identity": ("strategy_id", "strategy_version"),
        "prize_fields": ("ticket_prize_tiers", "ticket_special_hits"),
        "any_prize": "any_official_prize",
        "execution_status": "execution_status",
    },
    "NUMBER2_D_DECISION_OBJECTIVE_W50_1317_20261101_R1": {
        "tickets": "tickets",
        "identity": ("arm",),
        "prize_fields": ("ticket_results",),
        "any_prize": "any_official_prize",
        "execution_status": None,
    },
    "NUMBER2_D_GROUP_DRO_CAUSAL_W50_20261101_R1": {
        "tickets": "tickets",
        "identity": ("strategy_id", "strategy_version"),
        "prize_fields": ("best_prize_tier", "ticket_prize_tiers"),
        "any_prize": "any_official_prize",
        "execution_status": "execution_status",
    },
    "NUMBER2_D_SPECIAL_LAG_BUCKET_W50_K235_20261102_R1": {
        "tickets": "ticket_numbers",
        "identity": ("arm",),
        "prize_fields": (
            "official_prize_tiers",
            "baseline_any_prize",
            "candidate_any_prize",
            "special_hit_per_ticket",
        ),
        "any_prize": None,
        "execution_status": "execution_status",
    },
    "NUMBER2_D_DRAW_ORDER_POSITION_SIGNAL_V1_20261102_R1": {
        "tickets": "tickets",
        "identity": ("strategy_id", "strategy_version"),
        "prize_fields": ("ticket_prize_tiers",),
        "any_prize": "any_official_prize",
        "execution_status": "execution_status",
    },
}


class B649ResearchRecordArchiveDataError(ValueError):
    """The pinned formal backtest archive is absent, damaged, or inconsistent."""


class B649ResearchRecordSourceNotFound(LookupError):
    """The requested source is not one of the five authorized formal sources."""


class B649ResearchRecordInvalidFilter(ValueError):
    """A record filter is not available in the selected source."""


@dataclass(frozen=True, slots=True)
class B649ResearchRecordSource:
    source_task_id: str
    record_count: int
    research_class: str
    artifact_sha256: str
    availability_status: str
    _records: tuple[B649ResearchBacktestRecord, ...]
    _K_values: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class B649ResearchBacktestRecord:
    source_task_id: str
    source_record_identity: str
    target_draw: str | None
    arm_or_method_identity: str | None
    K: int | None
    predicted_tickets: Any
    actual_main_numbers: Any
    actual_special_number: Any
    official_prize_result: dict[str, Any]
    any_official_prize: bool | None
    execution_status: str | None
    original_source_sha256: str
    null_reasons: dict[str, str]


@dataclass(frozen=True, slots=True)
class B649ResearchRecordArchiveDataset:
    archive_sha256: str
    manifest_sha256: str
    source_authority: str
    sources: tuple[B649ResearchRecordSource, ...]

    def source(self, source_task_id: str) -> B649ResearchRecordSource:
        for source in self.sources:
            if source.source_task_id == source_task_id:
                return source
        raise B649ResearchRecordSourceNotFound(source_task_id)

    def query_records(
        self,
        source_task_id: str,
        *,
        target_draw: str | None,
        arm: str | None,
        K: int | None,
        limit: int,
        offset: int,
    ) -> tuple[tuple[B649ResearchBacktestRecord, ...], int]:
        source = self.source(source_task_id)
        if K is not None and K not in source._K_values:
            raise B649ResearchRecordInvalidFilter("K is not available for this source")
        selected = tuple(
            row
            for row in source._records
            if (target_draw is None or row.target_draw == target_draw)
            and (
                arm is None
                or row.arm_or_method_identity == arm
                or row.arm_or_method_identity.split("@", maxsplit=1)[0] == arm
            )
            and (K is None or row.K == K)
        )
        return selected[offset : offset + limit], len(selected)


class B649ResearchRecordArchiveReader:
    """Verify and cache only the five formal sources named by the archive manifest."""

    def __init__(self, root: str | Path) -> None:
        self._root = Path(root)
        self._dataset: B649ResearchRecordArchiveDataset | None = None

    @classmethod
    def from_environment(cls) -> B649ResearchRecordArchiveReader | None:
        configured_root = os.environ.get(B649_RESEARCH_RECORD_ARCHIVE_ROOT_ENV)
        if configured_root is None or not configured_root.strip():
            return None
        return cls(configured_root.strip())

    def read(self) -> B649ResearchRecordArchiveDataset:
        if self._dataset is not None:
            return self._dataset
        try:
            dataset = self._read_verified_archive()
        except B649ResearchRecordArchiveDataError:
            raise
        except (
            OSError,
            UnicodeError,
            json.JSONDecodeError,
            zipfile.BadZipFile,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise B649ResearchRecordArchiveDataError(
                "the configured formal backtest archive is unavailable or invalid"
            ) from exc
        self._dataset = dataset
        return dataset

    def _read_verified_archive(self) -> B649ResearchRecordArchiveDataset:
        if not self._root.is_absolute():
            raise B649ResearchRecordArchiveDataError("the archive root must be absolute")
        root = self._root.resolve(strict=True)
        if not root.is_dir():
            raise B649ResearchRecordArchiveDataError("the archive root is not a directory")

        manifest_path = root / "archive_manifest.json"
        archive_path = root / "backtest_bundle.zip"
        result_path = root / "result.json"
        checksums_path = root / "sha256sums.txt"
        for path in (manifest_path, archive_path, result_path, checksums_path):
            if path.is_symlink() or not path.is_file():
                raise B649ResearchRecordArchiveDataError("a required archive artifact is invalid")

        manifest_bytes = manifest_path.read_bytes()
        manifest_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
        if manifest_sha256 != B649_RESEARCH_RECORD_MANIFEST_SHA256:
            raise B649ResearchRecordArchiveDataError("the archive manifest checksum does not match")

        archive_bytes = archive_path.read_bytes()
        archive_sha256 = hashlib.sha256(archive_bytes).hexdigest()
        if archive_sha256 != B649_RESEARCH_RECORD_ARCHIVE_SHA256:
            raise B649ResearchRecordArchiveDataError("the archive checksum does not match")

        manifest = _json_object(manifest_bytes, "archive manifest")
        result = _json_object(result_path.read_bytes(), "archive result")
        _validate_archive_receipts(manifest, result, checksums_path.read_text(encoding="utf-8"))
        source_specs = _formal_source_specs(manifest)
        file_specs = _manifest_file_specs(manifest)

        with zipfile.ZipFile(archive_path) as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            if len(names) != len(set(names)):
                raise B649ResearchRecordArchiveDataError("the archive contains duplicate members")
            if len(names) != manifest.get("archive_entry_count"):
                raise B649ResearchRecordArchiveDataError("the archive member count is invalid")
            if set(names) != set(file_specs):
                raise B649ResearchRecordArchiveDataError("the archive member inventory is invalid")
            info_by_name = {info.filename: info for info in infos}
            for name, info in info_by_name.items():
                _validate_archive_member_name(name)
                if _is_symlink(info):
                    raise B649ResearchRecordArchiveDataError(
                        "the archive contains a symlink member"
                    )

            sources: list[B649ResearchRecordSource] = []
            for source_task_id, expected_count, relative_path in source_specs:
                entry = file_specs.get(relative_path)
                if entry is None:
                    raise B649ResearchRecordArchiveDataError(
                        "a formal source is missing from the archive manifest"
                    )
                if (
                    entry.get("evidence_class") != "raw_backtest_per_draw"
                    or entry.get("source_task_id") != source_task_id
                ):
                    raise B649ResearchRecordArchiveDataError(
                        "a formal source does not match its archive identity"
                    )
                info = info_by_name[relative_path]
                expected_size = entry.get("byte_size")
                expected_sha256 = entry.get("sha256")
                if (
                    not isinstance(expected_size, int)
                    or expected_size != info.file_size
                    or not isinstance(expected_sha256, str)
                    or not _SHA256_RE.fullmatch(expected_sha256)
                ):
                    raise B649ResearchRecordArchiveDataError(
                        "a formal source has invalid manifest metadata"
                    )
                raw_source = archive.read(info)
                if hashlib.sha256(raw_source).hexdigest() != expected_sha256:
                    raise B649ResearchRecordArchiveDataError(
                        "a formal source checksum does not match"
                    )
                rows = _parse_source_rows(
                    source_task_id, raw_source, expected_count, expected_sha256
                )
                K_values = tuple(sorted({row.K for row in rows if row.K is not None}))
                if K_values != (2, 3, 5):
                    raise B649ResearchRecordArchiveDataError(
                        "a formal source K inventory is invalid"
                    )
                sources.append(
                    B649ResearchRecordSource(
                        source_task_id=source_task_id,
                        record_count=len(rows),
                        research_class="FORMAL_HISTORICAL_BACKTEST",
                        artifact_sha256=expected_sha256,
                        availability_status="AVAILABLE",
                        _records=rows,
                        _K_values=K_values,
                    )
                )

        if sum(source.record_count for source in sources) != B649_RESEARCH_RECORD_TOTAL:
            raise B649ResearchRecordArchiveDataError("the formal source total is invalid")
        return B649ResearchRecordArchiveDataset(
            archive_sha256=archive_sha256,
            manifest_sha256=manifest_sha256,
            source_authority=B649_RESEARCH_RECORD_SOURCE_AUTHORITY,
            sources=tuple(sources),
        )


def _json_object(raw: bytes, label: str) -> dict[str, Any]:
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise B649ResearchRecordArchiveDataError(f"the {label} is not an object")
    return value


def _validate_archive_receipts(
    manifest: dict[str, Any], result: dict[str, Any], checksums_text: str
) -> None:
    if (
        manifest.get("task_id") != B649_RESEARCH_RECORD_ARCHIVE_TASK_ID
        or manifest.get("archive_sha256") != B649_RESEARCH_RECORD_ARCHIVE_SHA256
        or manifest.get("canonical_data_source_commit") != B649_RESEARCH_RECORD_SOURCE_AUTHORITY
        or result.get("task_id") != B649_RESEARCH_RECORD_ARCHIVE_TASK_ID
        or result.get("task_lifecycle_state") != "COMPLETED"
        or result.get("archive_sha256") != B649_RESEARCH_RECORD_ARCHIVE_SHA256
        or result.get("archive_manifest_sha256") != B649_RESEARCH_RECORD_MANIFEST_SHA256
    ):
        raise B649ResearchRecordArchiveDataError("the archive task identity is invalid")

    coverage = manifest.get("raw_backtest_coverage")
    result_coverage = result.get("raw_backtest_coverage")
    if (
        not isinstance(coverage, dict)
        or coverage.get("expected_records") != B649_RESEARCH_RECORD_TOTAL
        or coverage.get("produced_records") != B649_RESEARCH_RECORD_TOTAL
        or not isinstance(result_coverage, dict)
        or result_coverage.get("expected_records") != B649_RESEARCH_RECORD_TOTAL
        or result_coverage.get("produced_records") != B649_RESEARCH_RECORD_TOTAL
    ):
        raise B649ResearchRecordArchiveDataError("the formal backtest coverage receipt is invalid")

    checksum_entries: dict[str, str] = {}
    for line in checksums_text.splitlines():
        parts = line.split()
        if len(parts) < 2 or not _SHA256_RE.fullmatch(parts[0]):
            continue
        checksum_entries[Path(parts[-1]).name] = parts[0]
    if (
        checksum_entries.get("backtest_bundle.zip") != B649_RESEARCH_RECORD_ARCHIVE_SHA256
        or checksum_entries.get("archive_manifest.json") != B649_RESEARCH_RECORD_MANIFEST_SHA256
    ):
        raise B649ResearchRecordArchiveDataError("the archive checksum receipt is invalid")


def _formal_source_specs(
    manifest: dict[str, Any],
) -> tuple[tuple[str, int, str], ...]:
    coverage = manifest.get("raw_backtest_coverage")
    if not isinstance(coverage, dict):
        raise B649ResearchRecordArchiveDataError("the formal source manifest is missing")
    declared = coverage.get("formal_primary_sources")
    if not isinstance(declared, list) or len(declared) != len(_EXPECTED_SOURCE_COUNTS):
        raise B649ResearchRecordArchiveDataError("the formal source inventory is invalid")

    by_id: dict[str, dict[str, Any]] = {}
    for item in declared:
        if not isinstance(item, dict):
            raise B649ResearchRecordArchiveDataError("a formal source entry is invalid")
        source_task_id = item.get("source_task_id")
        if not isinstance(source_task_id, str) or source_task_id in by_id:
            raise B649ResearchRecordArchiveDataError("a formal source identity is invalid")
        by_id[source_task_id] = item

    if set(by_id) != set(_EXPECTED_SOURCE_COUNTS):
        raise B649ResearchRecordArchiveDataError("the formal source identities do not match")

    specs: list[tuple[str, int, str]] = []
    for source_task_id, expected_count in _EXPECTED_SOURCE_COUNTS.items():
        item = by_id[source_task_id]
        relative_path = item.get("archive_relative_path")
        if (
            item.get("status") != "PASS"
            or item.get("expected_records") != expected_count
            or item.get("produced_records") != expected_count
            or not isinstance(relative_path, str)
        ):
            raise B649ResearchRecordArchiveDataError("a formal source count is invalid")
        _validate_archive_member_name(relative_path)
        if not relative_path.startswith(f"sources/{source_task_id}/"):
            raise B649ResearchRecordArchiveDataError("a formal source path is invalid")
        specs.append((source_task_id, expected_count, relative_path))
    return tuple(specs)


def _manifest_file_specs(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    entries = manifest.get("files")
    if not isinstance(entries, list):
        raise B649ResearchRecordArchiveDataError("the archive file manifest is invalid")
    result: dict[str, dict[str, Any]] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise B649ResearchRecordArchiveDataError("an archive file entry is invalid")
        relative_path = entry.get("archive_relative_path")
        if not isinstance(relative_path, str):
            raise B649ResearchRecordArchiveDataError("an archive member path is invalid")
        _validate_archive_member_name(relative_path)
        if relative_path in result:
            raise B649ResearchRecordArchiveDataError("the archive manifest has duplicate paths")
        result[relative_path] = entry
    return result


def _validate_archive_member_name(name: str) -> None:
    path = PurePosixPath(name)
    raw_parts = name.split("/")
    if (
        not name
        or "\\" in name
        or "\x00" in name
        or path.is_absolute()
        or any(part in {"", ".", ".."} for part in raw_parts)
    ):
        raise B649ResearchRecordArchiveDataError("the archive contains an unsafe member path")


def _is_symlink(info: zipfile.ZipInfo) -> bool:
    return (info.external_attr >> 16) & 0o170000 == 0o120000


def _parse_source_rows(
    source_task_id: str,
    raw_source: bytes,
    expected_count: int,
    original_source_sha256: str,
) -> tuple[B649ResearchBacktestRecord, ...]:
    field_map = _SOURCE_FIELDS[source_task_id]
    rows: list[B649ResearchBacktestRecord] = []
    lines = raw_source.splitlines()
    if len(lines) != expected_count or any(not line.strip() for line in lines):
        raise B649ResearchRecordArchiveDataError("a formal source record count is invalid")

    for line_number, raw_line in enumerate(lines, start=1):
        try:
            raw_record = json.loads(raw_line)
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise B649ResearchRecordArchiveDataError("a formal source record is malformed") from exc
        if not isinstance(raw_record, dict):
            raise B649ResearchRecordArchiveDataError("a formal source record is not an object")

        identity_fields = field_map["identity"]
        if any(name not in raw_record for name in identity_fields):
            raise B649ResearchRecordArchiveDataError("a formal source method identity is missing")
        if len(identity_fields) == 1:
            arm_or_method_identity = raw_record[identity_fields[0]]
        else:
            arm_or_method_identity = "@".join(str(raw_record[name]) for name in identity_fields)

        tickets_field = field_map["tickets"]
        execution_field = field_map["execution_status"]
        any_prize_field = field_map["any_prize"]
        required_fields = (
            "target_draw",
            "K",
            tickets_field,
            "actual_main_numbers",
            "actual_special_number",
            *identity_fields,
            *field_map["prize_fields"],
        )
        if any(name not in raw_record for name in required_fields):
            raise B649ResearchRecordArchiveDataError("a formal source record field is missing")
        if execution_field is not None and execution_field not in raw_record:
            raise B649ResearchRecordArchiveDataError("a formal source execution status is missing")
        if any_prize_field is not None and any_prize_field not in raw_record:
            raise B649ResearchRecordArchiveDataError("a formal source success flag is missing")
        if (
            not isinstance(raw_record["target_draw"], str)
            or re.fullmatch(r"[0-9]{9}", raw_record["target_draw"]) is None
            or isinstance(raw_record["K"], bool)
            or not isinstance(raw_record["K"], int)
            or not isinstance(raw_record[tickets_field], list)
            or not isinstance(raw_record["actual_main_numbers"], list)
            or isinstance(raw_record["actual_special_number"], bool)
            or not isinstance(raw_record["actual_special_number"], int)
            or any(not isinstance(raw_record[name], str) for name in identity_fields)
            or (execution_field is not None and not isinstance(raw_record[execution_field], str))
            or (any_prize_field is not None and not isinstance(raw_record[any_prize_field], bool))
        ):
            raise B649ResearchRecordArchiveDataError("a formal source record value is invalid")

        prize_result = {name: raw_record[name] for name in field_map["prize_fields"]}
        null_reasons: dict[str, str] = {}
        if any_prize_field is None:
            null_reasons["any_official_prize"] = (
                "The original source has baseline/candidate flags but no any_official_prize field; "
                "the value is not inferred."
            )
        if execution_field is None:
            null_reasons["execution_status"] = (
                "The original source has no execution_status field; the value is not inferred."
            )

        rows.append(
            B649ResearchBacktestRecord(
                source_task_id=source_task_id,
                source_record_identity=f"{source_task_id}:record:{line_number:06d}",
                target_draw=raw_record["target_draw"],
                arm_or_method_identity=str(arm_or_method_identity),
                K=raw_record["K"],
                predicted_tickets=raw_record[tickets_field],
                actual_main_numbers=raw_record["actual_main_numbers"],
                actual_special_number=raw_record["actual_special_number"],
                official_prize_result=prize_result,
                any_official_prize=(
                    raw_record[any_prize_field] if any_prize_field is not None else None
                ),
                execution_status=(
                    raw_record[execution_field] if execution_field is not None else None
                ),
                original_source_sha256=original_source_sha256,
                null_reasons=null_reasons,
            )
        )
    return tuple(rows)
