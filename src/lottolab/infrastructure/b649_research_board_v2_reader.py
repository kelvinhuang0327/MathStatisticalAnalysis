"""Read the checksum-pinned V2 B649 research board without modifying its source."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

B649_RESEARCH_BOARD_V2_ROOT_ENV = "LOTTOLAB_B649_RESEARCH_BOARD_V2_ROOT"
B649_RESEARCH_BOARD_V2_TASK_ID = "NUMBER2_D_LMS_HUMAN_BOARD_V2_INTEGRATION_20261102_R1"
B649_RESEARCH_BOARD_V2_SOURCE_AUTHORITY = "fe3aa81d3844ac11d4360447c243e90fe4a6613a"

INVENTORY_HEADERS = (
    "method_id",
    "method_version",
    "method_family",
    "source_identity",
    "task_id",
    "evaluation_cohort",
    "history_window",
    "K",
    "official_prize_metric",
    "successful_draws",
    "eligible_draws",
    "success_rate",
    "baseline_identity",
    "baseline_success_rate",
    "paired_difference",
    "research_status",
    "original_advance_decision",
    "artifact_locator",
    "artifact_sha256",
    "backtest_artifact_locator",
    "backtest_artifact_sha256",
    "metrics_availability",
    "metrics_unavailable_reason",
    "shared_output_identity",
    "method_type",
    "auxiliary_statistics_json",
    "arm_identity",
    "lottery_type",
    "window",
    "prize_metric",
    "wins",
    "baseline_rate",
    "delta_percentage_points",
    "research_class",
    "target_draw_set_identity",
    "comparison_rank",
    "comparison_group_id",
    "comparison_status",
    "original_board_metrics_availability",
    "original_board_metrics_unavailable_reason",
    "board_original_advance_decision",
    "source_identity_chain",
    "source_shared_output_identities",
    "source_lineage",
    "source_record_id",
    "source_inventory_json",
)
OWNER_HEADERS = (
    "owner_long_rank",
    "owner_middle_rank",
    "owner_short_rank",
    "owner_selected",
    "owner_reason",
)
MANUAL_REVIEW_HEADERS = (*INVENTORY_HEADERS, *OWNER_HEADERS)
RANKING_HEADERS = (
    "method_id",
    "method_version",
    "arm_identity",
    "method_family",
    "task_id",
    "source_identity",
    "source_identity_chain",
    "lottery_type",
    "evaluation_cohort",
    "target_draw_set_identity",
    "window",
    "K",
    "prize_metric",
    "wins",
    "eligible_draws",
    "success_rate",
    "comparison_rank",
    "rank_basis_identity_count",
    "shared_output_identity",
    "source_shared_output_identities",
    "baseline_identity",
    "baseline_rate",
    "delta_percentage_points",
    "research_status",
    "research_class",
    "original_advance_decision",
    "original_board_metrics_availability",
    "original_board_metrics_unavailable_reason",
    "board_original_advance_decision",
    "comparison_status",
    "comparison_notes",
    "artifact_locator",
    "artifact_sha256",
    "source_rank",
    "source_lineage",
)

_EXPECTED_OUTPUTS = {
    "integration_summary.json",
    "lms_rankings_v2.csv",
    "manual_review_v2.csv",
    "method_inventory_v2.csv",
}
_INT_COLUMNS = {
    "K",
    "successful_draws",
    "eligible_draws",
    "wins",
    "comparison_rank",
    "rank_basis_identity_count",
    "source_rank",
}
_DECIMAL_COLUMNS = {
    "success_rate",
    "baseline_success_rate",
    "paired_difference",
    "baseline_rate",
    "delta_percentage_points",
}
_WINDOWS = ("FULL", "RECENT_750", "RECENT_300", "RECENT_50")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

type CsvRow = dict[str, str]


class B649ResearchBoardV2DataError(ValueError):
    """The configured V2 board is missing, malformed, or fails its pinned checksums."""


@dataclass(frozen=True, slots=True)
class B649ResearchBoardV2Dataset:
    source_manifest_sha256: str
    source_authority_commit: str
    observed_checkout_head: str
    method_version_count: int
    inventory_records: tuple[CsvRow, ...]
    method_records: tuple[CsvRow, ...]
    ranking_records: tuple[CsvRow, ...]
    metrics_availability_counts: dict[str, int]
    research_status_counts: dict[str, int]
    windows: tuple[str, ...]
    k_values: tuple[int, ...]
    prize_metrics: tuple[str, ...]
    comparison_group_count: int
    comparable_group_count: int
    duplicate_output_groups: int

    @property
    def inventory_count(self) -> int:
        return len(self.inventory_records)

    @property
    def ranking_count(self) -> int:
        return len(self.ranking_records)


class B649ResearchBoardV2Reader:
    """Load the configured V2 artifacts once and validate their published identity."""

    def __init__(self, root: str | Path) -> None:
        self._root = Path(root)
        self._dataset: B649ResearchBoardV2Dataset | None = None

    @classmethod
    def from_environment(cls) -> B649ResearchBoardV2Reader | None:
        configured_root = os.environ.get(B649_RESEARCH_BOARD_V2_ROOT_ENV)
        if configured_root is None or not configured_root.strip():
            return None
        return cls(configured_root.strip())

    def read(self) -> B649ResearchBoardV2Dataset:
        if self._dataset is not None:
            return self._dataset
        try:
            dataset = self._read_configured_root()
        except B649ResearchBoardV2DataError:
            raise
        except (OSError, UnicodeError, csv.Error, json.JSONDecodeError, TypeError) as exc:
            raise B649ResearchBoardV2DataError(
                "the configured V2 research board is unavailable or invalid"
            ) from exc
        self._dataset = dataset
        return dataset

    def _read_configured_root(self) -> B649ResearchBoardV2Dataset:
        if not self._root.is_absolute():
            raise B649ResearchBoardV2DataError("the configured V2 root must be absolute")
        root = self._root.resolve(strict=True)
        if not root.is_dir():
            raise B649ResearchBoardV2DataError("the configured V2 root is not a directory")

        manifest_bytes = (root / "source_manifest.json").read_bytes()
        manifest = _json_object(manifest_bytes, "source_manifest.json")
        result = _json_object((root / "result.json").read_bytes(), "result.json")
        integration = _json_object(
            (root / "integration_summary.json").read_bytes(), "integration_summary.json"
        )
        _validate_source_identity(manifest, result)

        declared_outputs = manifest.get("outputs")
        if not isinstance(declared_outputs, dict) or set(declared_outputs) != _EXPECTED_OUTPUTS:
            raise B649ResearchBoardV2DataError("the V2 manifest output inventory is invalid")

        output_bytes: dict[str, bytes] = {}
        for filename in sorted(_EXPECTED_OUTPUTS):
            raw = (root / filename).read_bytes()
            _validate_declared_output(filename, raw, declared_outputs[filename])
            output_bytes[filename] = raw

        inventory_records = _csv_records(
            output_bytes["method_inventory_v2.csv"],
            "method_inventory_v2.csv",
            INVENTORY_HEADERS,
        )
        method_records = _csv_records(
            output_bytes["manual_review_v2.csv"],
            "manual_review_v2.csv",
            MANUAL_REVIEW_HEADERS,
        )
        ranking_records = _csv_records(
            output_bytes["lms_rankings_v2.csv"], "lms_rankings_v2.csv", RANKING_HEADERS
        )
        _validate_records_match(inventory_records, method_records)
        _validate_numeric_cells(inventory_records, INVENTORY_HEADERS)
        _validate_numeric_cells(method_records, MANUAL_REVIEW_HEADERS)
        _validate_numeric_cells(ranking_records, RANKING_HEADERS)

        row_counts = manifest.get("row_counts")
        expected_counts = {
            "method_inventory_v2.csv": 2968,
            "manual_review_v2.csv": 2968,
            "lms_rankings_v2.csv": 2818,
        }
        observed_counts = {
            "method_inventory_v2.csv": len(inventory_records),
            "manual_review_v2.csv": len(method_records),
            "lms_rankings_v2.csv": len(ranking_records),
        }
        if row_counts != expected_counts or observed_counts != expected_counts:
            raise B649ResearchBoardV2DataError("the V2 row counts do not match the manifest")

        method_version_count = len(
            {(row["method_id"], row["method_version"]) for row in inventory_records}
        )
        metrics_counts = Counter(row["metrics_availability"] for row in inventory_records)
        status_counts = Counter(row["research_status"] for row in inventory_records)
        if method_version_count != 305:
            raise B649ResearchBoardV2DataError("the V2 method/version count is invalid")
        if metrics_counts["UNAVAILABLE"] != 60 or metrics_counts["NOT_APPLICABLE"] != 90:
            raise B649ResearchBoardV2DataError("the V2 metric availability counts are invalid")

        available_windows = tuple(
            window for window in _WINDOWS if any(row["window"] == window for row in ranking_records)
        )
        if available_windows != _WINDOWS:
            raise B649ResearchBoardV2DataError("the V2 ranking windows are incomplete")
        k_values = tuple(sorted({int(row["K"]) for row in ranking_records}))
        prize_metrics = tuple(sorted({row["prize_metric"] for row in ranking_records}))

        comparison_groups = integration.get("comparison_group_count")
        comparable_groups = integration.get("comparable_group_count")
        duplicate_groups = integration.get("duplicate_output_groups")
        if comparison_groups != 504 or comparable_groups != 224 or duplicate_groups != 48:
            raise B649ResearchBoardV2DataError("the V2 comparison identity counts are invalid")
        if integration.get("final_method_version_count") != method_version_count:
            raise B649ResearchBoardV2DataError("the V2 integration summary is inconsistent")
        if integration.get("final_inventory_rows") != len(inventory_records):
            raise B649ResearchBoardV2DataError("the V2 integration inventory count is inconsistent")
        if integration.get("final_ranking_rows") != len(ranking_records):
            raise B649ResearchBoardV2DataError("the V2 integration ranking count is inconsistent")
        if result.get("final_method_version_count") != method_version_count:
            raise B649ResearchBoardV2DataError("the V2 result receipt is inconsistent")
        if result.get("final_inventory_rows") != len(inventory_records):
            raise B649ResearchBoardV2DataError("the V2 result inventory count is inconsistent")
        if result.get("final_ranking_rows") != len(ranking_records):
            raise B649ResearchBoardV2DataError("the V2 result ranking count is inconsistent")

        return B649ResearchBoardV2Dataset(
            source_manifest_sha256=hashlib.sha256(manifest_bytes).hexdigest(),
            source_authority_commit=B649_RESEARCH_BOARD_V2_SOURCE_AUTHORITY,
            observed_checkout_head=_required_string(manifest, "observed_checkout_head"),
            method_version_count=method_version_count,
            inventory_records=tuple(inventory_records),
            method_records=tuple(method_records),
            ranking_records=tuple(ranking_records),
            metrics_availability_counts=dict(sorted(metrics_counts.items())),
            research_status_counts=dict(sorted(status_counts.items())),
            windows=available_windows,
            k_values=k_values,
            prize_metrics=prize_metrics,
            comparison_group_count=comparison_groups,
            comparable_group_count=comparable_groups,
            duplicate_output_groups=duplicate_groups,
        )


def _json_object(raw: bytes, label: str) -> dict[str, object]:
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise B649ResearchBoardV2DataError(f"{label} must contain a JSON object")
    return value


def _validate_source_identity(manifest: dict[str, object], result: dict[str, object]) -> None:
    if manifest.get("task_id") != B649_RESEARCH_BOARD_V2_TASK_ID:
        raise B649ResearchBoardV2DataError("the V2 manifest task identity is invalid")
    if result.get("task_id") != B649_RESEARCH_BOARD_V2_TASK_ID:
        raise B649ResearchBoardV2DataError("the V2 result task identity is invalid")
    if result.get("task_lifecycle_state") != "COMPLETED":
        raise B649ResearchBoardV2DataError("the V2 source task is not complete")
    if manifest.get("canonical_source_authority") != B649_RESEARCH_BOARD_V2_SOURCE_AUTHORITY:
        raise B649ResearchBoardV2DataError("the V2 canonical source authority is invalid")
    if manifest.get("source_identity_status") != "PASS":
        raise B649ResearchBoardV2DataError("the V2 source identity is not verified")
    result_identity_status = result.get("source_identity_status")
    if not isinstance(result_identity_status, str) or not result_identity_status.startswith("PASS"):
        raise B649ResearchBoardV2DataError("the V2 result source identity is not verified")


def _validate_declared_output(filename: str, raw: bytes, declared: object) -> None:
    if not isinstance(declared, dict):
        raise B649ResearchBoardV2DataError(f"the V2 manifest entry for {filename} is invalid")
    expected_bytes = declared.get("bytes")
    expected_sha256 = declared.get("sha256")
    if type(expected_bytes) is not int or not isinstance(expected_sha256, str):
        raise B649ResearchBoardV2DataError(f"the V2 manifest entry for {filename} is incomplete")
    if not _SHA256_RE.fullmatch(expected_sha256):
        raise B649ResearchBoardV2DataError(f"the V2 checksum for {filename} is malformed")
    actual_sha256 = hashlib.sha256(raw).hexdigest()
    if len(raw) != expected_bytes or actual_sha256 != expected_sha256:
        raise B649ResearchBoardV2DataError(f"the V2 checksum for {filename} does not match")


def _csv_records(raw: bytes, label: str, expected_headers: tuple[str, ...]) -> list[CsvRow]:
    text = raw.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text, newline=""))
    if tuple(reader.fieldnames or ()) != expected_headers:
        raise B649ResearchBoardV2DataError(f"the V2 header for {label} is invalid")
    rows: list[CsvRow] = []
    for row in reader:
        if None in row or any(value is None for value in row.values()):
            raise B649ResearchBoardV2DataError(f"the V2 row shape in {label} is invalid")
        rows.append({key: value for key, value in row.items() if key is not None})
    return rows


def _validate_records_match(inventory_records: list[CsvRow], method_records: list[CsvRow]) -> None:
    if len(inventory_records) != len(method_records):
        raise B649ResearchBoardV2DataError("the V2 manual review row count is inconsistent")
    source_differences = {"source_identity_chain", "source_lineage"}
    for index, (inventory, manual) in enumerate(
        zip(inventory_records, method_records, strict=True)
    ):
        if any(
            inventory[field] != manual[field]
            for field in INVENTORY_HEADERS
            if field not in source_differences
        ):
            raise B649ResearchBoardV2DataError(
                f"the V2 manual review identity differs at row {index + 2}"
            )


def _validate_numeric_cells(records: list[CsvRow], headers: tuple[str, ...]) -> None:
    int_columns = _INT_COLUMNS.intersection(headers)
    decimal_columns = _DECIMAL_COLUMNS.intersection(headers)
    for row_number, row in enumerate(records, start=2):
        for column in int_columns:
            value = row[column]
            if value:
                try:
                    int(value)
                except ValueError as exc:
                    raise B649ResearchBoardV2DataError(
                        f"the V2 integer field {column} is invalid at row {row_number}"
                    ) from exc
        for column in decimal_columns:
            value = row[column]
            if value:
                try:
                    decimal_value = Decimal(value)
                except InvalidOperation as exc:
                    raise B649ResearchBoardV2DataError(
                        f"the V2 decimal field {column} is invalid at row {row_number}"
                    ) from exc
                if not decimal_value.is_finite():
                    raise B649ResearchBoardV2DataError(
                        f"the V2 decimal field {column} is non-finite at row {row_number}"
                    )


def _required_string(value: dict[str, object], key: str) -> str:
    candidate = value.get(key)
    if not isinstance(candidate, str) or not candidate:
        raise B649ResearchBoardV2DataError(f"the V2 manifest field {key} is invalid")
    return candidate
