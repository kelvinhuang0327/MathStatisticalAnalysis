"""Validated access to the complete audited BIG_LOTTO strategy universe.

The research catalog is deliberately separate from the production
``StrategyCatalog``.  Legacy governance state is evidence here, never an
execution filter.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from dataclasses import dataclass
from enum import StrEnum
from importlib.resources import files
from types import MappingProxyType
from typing import Any, cast

CATALOG_RESOURCE_NAME = "biglotto_full_strategy_catalog_v1.json"
CATALOG_SCHEMA_VERSION = "BIG_LOTTO_FULL_STRATEGY_CATALOG_V1"
CATALOG_POLICY_VERSION = "BIG_LOTTO_ALL_ACTUAL_METHODS_REGARDLESS_LEGACY_GOVERNANCE_V1"
EXPECTED_TOTAL_STRATEGY_COUNT = 221
EXPECTED_FIRST_BATCH_COUNT = 11
_SHA256 = re.compile(r"[0-9a-f]{64}", flags=re.ASCII)


class FullStrategyCatalogError(ValueError):
    """The packaged research-universe catalog violates its closed contract."""


class ReproductionStatus(StrEnum):
    BACKTESTED = "BACKTESTED"
    CLOSED_UNEXECUTABLE = "CLOSED_UNEXECUTABLE"
    DUPLICATE_ALIAS = "DUPLICATE_ALIAS"
    OWNER_DECISION_REQUIRED = "OWNER_DECISION_REQUIRED"


class ReplayBatchMappingStatus(StrEnum):
    EXACT_SOURCE_SYMBOL_MATCH = "EXACT_SOURCE_SYMBOL_MATCH"
    OWNER_DECISION_REQUIRED = "OWNER_DECISION_REQUIRED"


@dataclass(frozen=True, slots=True)
class ReplayBatchMapping:
    registry_strategy_id: str
    mapping_status: ReplayBatchMappingStatus
    mapping_reason: str
    catalog_strategy_id: str | None = None
    legacy_method_id: str | None = None

    def __post_init__(self) -> None:
        if not self.registry_strategy_id or not self.mapping_reason:
            raise FullStrategyCatalogError(
                "replay-batch mapping identity and reason must be non-empty"
            )
        if self.mapping_status is ReplayBatchMappingStatus.EXACT_SOURCE_SYMBOL_MATCH:
            if not self.catalog_strategy_id or not self.legacy_method_id:
                raise FullStrategyCatalogError(
                    "exact replay-batch mapping requires both catalog identities"
                )
        elif self.catalog_strategy_id is not None or self.legacy_method_id is not None:
            raise FullStrategyCatalogError(
                "unresolved replay-batch mapping cannot claim catalog identity"
            )


@dataclass(frozen=True, slots=True)
class FullStrategyCatalogRecord:
    strategy_id: str
    strategy_version: str
    legacy_method_id: str
    source_path: str
    source_commit: str
    source_blob_id: str
    source_sha256: str
    source_byte_size: int
    source_scan_status: str
    source_type: str
    discovery_group: str
    method_family: str
    legacy_runnable_status: str
    legacy_recommended_action: str
    r2_safety_disposition: str
    reproduction_status: ReproductionStatus
    status_reason: str
    native_ticket_semantics: str
    ticket_order_semantics: str
    ticket_duplicate_semantics: str
    candidate_k_semantics: str
    combination_count_semantics: str
    unranked_reason: str
    why_not_runnable: str
    duplicate_alias_target: str | None = None

    def __post_init__(self) -> None:
        for field_name in (
            "strategy_id",
            "strategy_version",
            "legacy_method_id",
            "source_path",
            "source_commit",
            "source_blob_id",
            "source_sha256",
            "source_scan_status",
            "source_type",
            "discovery_group",
            "method_family",
            "legacy_runnable_status",
            "legacy_recommended_action",
            "r2_safety_disposition",
            "status_reason",
            "native_ticket_semantics",
            "ticket_order_semantics",
            "ticket_duplicate_semantics",
            "candidate_k_semantics",
            "combination_count_semantics",
            "unranked_reason",
            "why_not_runnable",
        ):
            value = getattr(self, field_name)
            if type(value) is not str or not value:
                raise FullStrategyCatalogError(f"{field_name} must be non-empty")
        if _SHA256.fullmatch(self.source_sha256) is None:
            raise FullStrategyCatalogError("source_sha256 must be an exact lowercase SHA-256")
        if type(self.source_byte_size) is not int or self.source_byte_size < 0:
            raise FullStrategyCatalogError("source_byte_size must be non-negative")
        if type(self.reproduction_status) is not ReproductionStatus:
            raise FullStrategyCatalogError("reproduction_status is outside the closed set")
        alias = self.duplicate_alias_target
        if self.reproduction_status is ReproductionStatus.DUPLICATE_ALIAS:
            if type(alias) is not str or not alias:
                raise FullStrategyCatalogError(
                    "DUPLICATE_ALIAS requires duplicate_alias_target"
                )
        elif alias is not None:
            raise FullStrategyCatalogError(
                "only DUPLICATE_ALIAS may carry duplicate_alias_target"
            )

    def canonical_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "candidate_k_semantics": self.candidate_k_semantics,
            "combination_count_semantics": self.combination_count_semantics,
            "discovery_group": self.discovery_group,
            "legacy_method_id": self.legacy_method_id,
            "legacy_recommended_action": self.legacy_recommended_action,
            "legacy_runnable_status": self.legacy_runnable_status,
            "method_family": self.method_family,
            "native_ticket_semantics": self.native_ticket_semantics,
            "r2_safety_disposition": self.r2_safety_disposition,
            "reproduction_status": self.reproduction_status.value,
            "source_blob_id": self.source_blob_id,
            "source_byte_size": self.source_byte_size,
            "source_commit": self.source_commit,
            "source_path": self.source_path,
            "source_scan_status": self.source_scan_status,
            "source_sha256": self.source_sha256,
            "source_type": self.source_type,
            "status_reason": self.status_reason,
            "strategy_id": self.strategy_id,
            "strategy_version": self.strategy_version,
            "ticket_duplicate_semantics": self.ticket_duplicate_semantics,
            "ticket_order_semantics": self.ticket_order_semantics,
            "unranked_reason": self.unranked_reason,
            "why_not_runnable": self.why_not_runnable,
        }
        if self.duplicate_alias_target is not None:
            payload["duplicate_alias_target"] = self.duplicate_alias_target
        return payload


@dataclass(frozen=True, slots=True)
class FullStrategyCatalogProgress:
    total_strategy_count: int
    reproduced_count: int
    backtested_count: int
    closed_count: int
    duplicate_alias_count: int
    owner_decision_required_count: int
    uncompleted_count: int

    def canonical_dict(self) -> dict[str, int]:
        return {
            "backtested_count": self.backtested_count,
            "closed_count": self.closed_count,
            "duplicate_alias_count": self.duplicate_alias_count,
            "owner_decision_required_count": self.owner_decision_required_count,
            "reproduced_count": self.reproduced_count,
            "total_strategy_count": self.total_strategy_count,
            "uncompleted_count": self.uncompleted_count,
        }


@dataclass(frozen=True, slots=True)
class FullStrategyCatalog:
    records: tuple[FullStrategyCatalogRecord, ...]
    catalog_sha256: str
    frozen_source_commit: str
    research_disclaimer: str
    first_batch_strategy_ids: tuple[str, ...]
    first_batch_mappings: tuple[ReplayBatchMapping, ...]
    source_artifacts: tuple[tuple[str, str, str], ...]
    full_universe_complete: bool
    _raw_document: dict[str, object]

    def __post_init__(self) -> None:
        if len(self.records) != EXPECTED_TOTAL_STRATEGY_COUNT:
            raise FullStrategyCatalogError("catalog must contain exactly 221 records")
        if len({record.strategy_id for record in self.records}) != len(self.records):
            raise FullStrategyCatalogError("catalog strategy IDs must be unique")
        if len({record.legacy_method_id for record in self.records}) != len(self.records):
            raise FullStrategyCatalogError("catalog legacy method IDs must be unique")
        if tuple(sorted(self.records, key=lambda row: row.legacy_method_id)) != self.records:
            raise FullStrategyCatalogError("catalog records must use legacy method ID order")
        if _SHA256.fullmatch(self.catalog_sha256) is None:
            raise FullStrategyCatalogError("catalog_sha256 must be a lowercase SHA-256")
        if len(self.first_batch_strategy_ids) != EXPECTED_FIRST_BATCH_COUNT:
            raise FullStrategyCatalogError("first replay-backed batch must contain 11 IDs")
        if len(set(self.first_batch_strategy_ids)) != EXPECTED_FIRST_BATCH_COUNT:
            raise FullStrategyCatalogError("first replay-backed batch IDs must be unique")
        if len(self.first_batch_mappings) != EXPECTED_FIRST_BATCH_COUNT:
            raise FullStrategyCatalogError(
                "first replay-backed batch must have 11 mapping decisions"
            )
        if tuple(
            mapping.registry_strategy_id for mapping in self.first_batch_mappings
        ) != self.first_batch_strategy_ids:
            raise FullStrategyCatalogError(
                "first replay-backed mapping order must match declared IDs"
            )
        exact_catalog_ids = {
            mapping.catalog_strategy_id
            for mapping in self.first_batch_mappings
            if mapping.mapping_status
            is ReplayBatchMappingStatus.EXACT_SOURCE_SYMBOL_MATCH
        }
        if len(exact_catalog_ids) != 2 or not exact_catalog_ids <= {
            record.strategy_id for record in self.records
        }:
            raise FullStrategyCatalogError(
                "first replay-backed batch must preserve two exact 221-row mappings"
            )
        if not self.research_disclaimer:
            raise FullStrategyCatalogError("research disclaimer must not be blank")
        if type(self.full_universe_complete) is not bool:
            raise FullStrategyCatalogError("full_universe_complete must be a boolean")
        if self.full_universe_complete is (self.progress.uncompleted_count != 0):
            raise FullStrategyCatalogError(
                "full_universe_complete must be true exactly when uncompleted_count is zero"
            )

    @property
    def progress(self) -> FullStrategyCatalogProgress:
        counts = {
            status: sum(
                record.reproduction_status is status for record in self.records
            )
            for status in ReproductionStatus
        }
        backtested = counts[ReproductionStatus.BACKTESTED]
        closed = counts[ReproductionStatus.CLOSED_UNEXECUTABLE]
        aliases = counts[ReproductionStatus.DUPLICATE_ALIAS]
        pending = counts[ReproductionStatus.OWNER_DECISION_REQUIRED]
        return FullStrategyCatalogProgress(
            total_strategy_count=len(self.records),
            reproduced_count=backtested,
            backtested_count=backtested,
            closed_count=closed,
            duplicate_alias_count=aliases,
            owner_decision_required_count=pending,
            uncompleted_count=len(self.records) - backtested - closed - aliases,
        )

    def get(self, strategy_id: str) -> FullStrategyCatalogRecord:
        by_id = MappingProxyType({record.strategy_id: record for record in self.records})
        try:
            return by_id[strategy_id]
        except KeyError as exc:
            raise FullStrategyCatalogError(
                f"unknown full-universe strategy ID: {strategy_id}"
            ) from exc

    def canonical_json_bytes(self) -> bytes:
        return (
            json.dumps(
                self._raw_document,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
            + b"\n"
        )

    def canonical_csv_bytes(self) -> bytes:
        fieldnames = (
            "strategy_id",
            "strategy_version",
            "legacy_method_id",
            "source_path",
            "source_commit",
            "source_blob_id",
            "source_sha256",
            "source_byte_size",
            "source_scan_status",
            "source_type",
            "discovery_group",
            "method_family",
            "legacy_runnable_status",
            "legacy_recommended_action",
            "r2_safety_disposition",
            "reproduction_status",
            "status_reason",
            "native_ticket_semantics",
            "ticket_order_semantics",
            "ticket_duplicate_semantics",
            "candidate_k_semantics",
            "combination_count_semantics",
            "duplicate_alias_target",
            "unranked_reason",
            "why_not_runnable",
        )
        buffer = io.StringIO(newline="")
        writer = csv.DictWriter(buffer, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for record in self.records:
            row = record.canonical_dict()
            row["duplicate_alias_target"] = record.duplicate_alias_target or ""
            writer.writerow(cast(Any, row))
        return buffer.getvalue().encode("utf-8")


def _canonical_without_catalog_hash(document: dict[str, Any]) -> bytes:
    reduced = {key: value for key, value in document.items() if key != "catalog_sha256"}
    return json.dumps(
        reduced,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def load_full_strategy_catalog() -> FullStrategyCatalog:
    resource = files("lottolab.strategies.data").joinpath(CATALOG_RESOURCE_NAME)
    raw = resource.read_bytes()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise FullStrategyCatalogError("packaged catalog is invalid JSON") from exc
    if not isinstance(parsed, dict):
        raise FullStrategyCatalogError("packaged catalog must be a JSON object")
    document = cast(dict[str, Any], parsed)
    if document.get("catalog_schema_version") != CATALOG_SCHEMA_VERSION:
        raise FullStrategyCatalogError("unsupported catalog schema version")
    if document.get("catalog_policy_version") != CATALOG_POLICY_VERSION:
        raise FullStrategyCatalogError("unsupported catalog policy version")
    if document.get("expected_total_strategy_count") != EXPECTED_TOTAL_STRATEGY_COUNT:
        raise FullStrategyCatalogError("catalog expected-total declaration is not 221")
    if document.get("lottery_type") != "BIG_LOTTO":
        raise FullStrategyCatalogError("catalog lottery type must be BIG_LOTTO")
    full_universe_complete = document.get("full_universe_complete")
    if type(full_universe_complete) is not bool:
        raise FullStrategyCatalogError("full_universe_complete must be a boolean")

    catalog_sha256 = document.get("catalog_sha256")
    if not isinstance(catalog_sha256, str):
        raise FullStrategyCatalogError("catalog_sha256 is missing")
    expected_hash = hashlib.sha256(_canonical_without_catalog_hash(document)).hexdigest()
    if catalog_sha256 != expected_hash:
        raise FullStrategyCatalogError("catalog_sha256 does not match catalog content")

    records_value = document.get("records")
    if not isinstance(records_value, list):
        raise FullStrategyCatalogError("catalog records must be a list")
    records_raw = cast(list[object], records_value)
    records: list[FullStrategyCatalogRecord] = []
    for index, candidate in enumerate(records_raw):
        if not isinstance(candidate, dict):
            raise FullStrategyCatalogError(f"catalog record {index} must be an object")
        row = cast(dict[str, Any], candidate)
        try:
            records.append(
                FullStrategyCatalogRecord(
                    strategy_id=row["strategy_id"],
                    strategy_version=row["strategy_version"],
                    legacy_method_id=row["legacy_method_id"],
                    source_path=row["source_path"],
                    source_commit=row["source_commit"],
                    source_blob_id=row["source_blob_id"],
                    source_sha256=row["source_sha256"],
                    source_byte_size=row["source_byte_size"],
                    source_scan_status=row["source_scan_status"],
                    source_type=row["source_type"],
                    discovery_group=row["discovery_group"],
                    method_family=row["method_family"],
                    legacy_runnable_status=row["legacy_runnable_status"],
                    legacy_recommended_action=row["legacy_recommended_action"],
                    r2_safety_disposition=row["r2_safety_disposition"],
                    reproduction_status=ReproductionStatus(row["reproduction_status"]),
                    status_reason=row["status_reason"],
                    native_ticket_semantics=row["native_ticket_semantics"],
                    ticket_order_semantics=row["ticket_order_semantics"],
                    ticket_duplicate_semantics=row["ticket_duplicate_semantics"],
                    candidate_k_semantics=row["candidate_k_semantics"],
                    combination_count_semantics=row["combination_count_semantics"],
                    unranked_reason=row["unranked_reason"],
                    why_not_runnable=row["why_not_runnable"],
                    duplicate_alias_target=row.get("duplicate_alias_target"),
                )
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise FullStrategyCatalogError(f"invalid catalog record at index {index}") from exc

    first_batch_value = document.get("first_batch")
    if not isinstance(first_batch_value, dict):
        raise FullStrategyCatalogError("first_batch must be an object")
    first_batch_raw = cast(dict[str, object], first_batch_value)
    first_batch_ids_value = first_batch_raw.get("strategy_ids")
    if (
        first_batch_raw.get("declared_strategy_count") != EXPECTED_FIRST_BATCH_COUNT
        or first_batch_raw.get("is_full_universe") is not False
        or not isinstance(first_batch_ids_value, list)
        or not all(
            isinstance(item, str)
            for item in cast(list[object], first_batch_ids_value)
        )
    ):
        raise FullStrategyCatalogError("invalid 11-strategy first-batch declaration")
    first_batch_ids_raw = cast(list[str], first_batch_ids_value)
    mappings_value = first_batch_raw.get("mappings")
    if not isinstance(mappings_value, list):
        raise FullStrategyCatalogError("first_batch.mappings must be a list")
    mapping_rows = cast(list[object], mappings_value)
    mappings: list[ReplayBatchMapping] = []
    for index, mapping_value in enumerate(mapping_rows):
        if not isinstance(mapping_value, dict):
            raise FullStrategyCatalogError(
                f"first_batch.mappings[{index}] must be an object"
            )
        mapping = cast(dict[str, object], mapping_value)
        registry_strategy_id = mapping.get("registry_strategy_id")
        mapping_status = mapping.get("mapping_status")
        mapping_reason = mapping.get("mapping_reason")
        if (
            not isinstance(registry_strategy_id, str)
            or not isinstance(mapping_status, str)
            or not isinstance(mapping_reason, str)
        ):
            raise FullStrategyCatalogError(
                f"invalid first_batch.mappings[{index}]"
            )
        catalog_strategy_id = mapping.get("catalog_strategy_id")
        legacy_method_id = mapping.get("legacy_method_id")
        if catalog_strategy_id is not None and not isinstance(
            catalog_strategy_id,
            str,
        ):
            raise FullStrategyCatalogError("invalid mapped catalog strategy ID")
        if legacy_method_id is not None and not isinstance(legacy_method_id, str):
            raise FullStrategyCatalogError("invalid mapped legacy method ID")
        try:
            status = ReplayBatchMappingStatus(mapping_status)
        except ValueError as exc:
            raise FullStrategyCatalogError(
                "first-batch mapping status is outside the closed set"
            ) from exc
        mappings.append(
            ReplayBatchMapping(
                registry_strategy_id=registry_strategy_id,
                mapping_status=status,
                mapping_reason=mapping_reason,
                catalog_strategy_id=catalog_strategy_id,
                legacy_method_id=legacy_method_id,
            )
        )
    exact_mapping_count = sum(
        mapping.mapping_status
        is ReplayBatchMappingStatus.EXACT_SOURCE_SYMBOL_MATCH
        for mapping in mappings
    )
    if (
        first_batch_raw.get("exact_mapping_count") != exact_mapping_count
        or first_batch_raw.get("owner_decision_required_mapping_count")
        != EXPECTED_FIRST_BATCH_COUNT - exact_mapping_count
    ):
        raise FullStrategyCatalogError(
            "first-batch mapping counts contradict mapping rows"
        )

    artifacts_value = document.get("source_artifacts")
    if not isinstance(artifacts_value, list):
        raise FullStrategyCatalogError("source_artifacts must be a list")
    artifacts_raw = cast(list[object], artifacts_value)
    artifacts: list[tuple[str, str, str]] = []
    for artifact_value in artifacts_raw:
        if not isinstance(artifact_value, dict):
            raise FullStrategyCatalogError("source artifact must be an object")
        artifact = cast(dict[str, object], artifact_value)
        name = artifact.get("artifact_name")
        digest = artifact.get("artifact_sha256")
        role = artifact.get("evidence_role")
        if (
            not isinstance(name, str)
            or not name
            or not isinstance(digest, str)
            or _SHA256.fullmatch(digest) is None
            or not isinstance(role, str)
            or not role
        ):
            raise FullStrategyCatalogError("invalid source artifact identity")
        artifacts.append((name, digest, role))

    frozen_source_commit = document.get("frozen_source_commit")
    research_disclaimer = document.get("research_disclaimer")
    if not isinstance(frozen_source_commit, str) or not frozen_source_commit:
        raise FullStrategyCatalogError("frozen_source_commit must be non-empty")
    if not isinstance(research_disclaimer, str) or not research_disclaimer:
        raise FullStrategyCatalogError("research_disclaimer must be non-empty")
    catalog = FullStrategyCatalog(
        records=tuple(records),
        catalog_sha256=catalog_sha256,
        frozen_source_commit=frozen_source_commit,
        research_disclaimer=research_disclaimer,
        first_batch_strategy_ids=tuple(first_batch_ids_raw),
        first_batch_mappings=tuple(mappings),
        source_artifacts=tuple(artifacts),
        full_universe_complete=full_universe_complete,
        _raw_document=cast(dict[str, object], document),
    )
    status_counts_raw = document.get("status_counts")
    expected_status_counts = {
        status.value: sum(
            record.reproduction_status is status for record in catalog.records
        )
        for status in ReproductionStatus
    }
    if status_counts_raw != expected_status_counts:
        raise FullStrategyCatalogError(
            "declared status_counts do not match catalog records"
        )
    return catalog


__all__ = [
    "CATALOG_POLICY_VERSION",
    "CATALOG_RESOURCE_NAME",
    "CATALOG_SCHEMA_VERSION",
    "EXPECTED_FIRST_BATCH_COUNT",
    "EXPECTED_TOTAL_STRATEGY_COUNT",
    "FullStrategyCatalog",
    "FullStrategyCatalogError",
    "FullStrategyCatalogProgress",
    "FullStrategyCatalogRecord",
    "ReplayBatchMapping",
    "ReplayBatchMappingStatus",
    "ReproductionStatus",
    "load_full_strategy_catalog",
]
