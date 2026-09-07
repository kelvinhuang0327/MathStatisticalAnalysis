"""Fixed-resource reader for the immutable B649 aggregate-history projection."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import fields
from functools import lru_cache
from importlib.resources import files
from typing import cast

from pydantic import TypeAdapter, ValidationError

from lottolab.application.biglotto_multi_ticket_records import (
    B649_AUTHORITY_MODE_FRESH_REPRODUCTION as AUTHORITY_MODE_FRESH_REPRODUCTION,
)
from lottolab.application.biglotto_multi_ticket_records import (
    B649_AUTHORITY_MODE_HISTORICAL_SEALED as AUTHORITY_MODE_HISTORICAL_SEALED,
)
from lottolab.application.biglotto_multi_ticket_records import (
    B649_EXACT_NATIVE_TICKET_COUNTS,
    B649_HISTORY_WINDOWS,
    B649_PREFIX_COUNTS,
    B649_SUCCESS_CRITERIA,
    B649ExactNativeRecord,
    B649ExactNativeRecordDataset,
    B649HistoryWindow,
    B649K10Provenance,
    B649K10Record,
    B649K10RecordDataset,
    B649K10WindowBoundary,
    B649MultiTicketRecord,
    B649MultiTicketRecordDataset,
    B649OfficialPrizeCounts,
    B649SuccessCriterion,
)
from lottolab.application.biglotto_multi_ticket_records import (
    B649_METRICS_UNAVAILABLE_STRATEGY_IDS as METRICS_UNAVAILABLE_STRATEGY_IDS,
)
from lottolab.domain.biglotto_full_strategy_catalog import (
    FullStrategyCatalogRecord,
    ReproductionStatus,
    load_full_strategy_catalog,
)
from lottolab.infrastructure.b649_dataset_authority import (
    B649DatasetAuthorityError,
    validate_b649_dataset_sha256,
)

PROJECTION_RESOURCE_NAME = "biglotto_multi_ticket_historical_records_v1.json"
PROJECTION_SCHEMA_VERSION = "B649_MULTI_TICKET_HISTORICAL_RECORDS_V2"
PROJECTION_RESOURCE_NAME_V3 = "biglotto_multi_ticket_historical_records_v2.json"
PROJECTION_SCHEMA_VERSION_V3 = "B649_MULTI_TICKET_HISTORICAL_RECORDS_V3"
_LEGACY_PROJECTION_SCHEMA_VERSION = "B649_MULTI_TICKET_HISTORICAL_RECORDS_V1"
_SHA256 = re.compile(r"^[0-9a-f]{64}$", flags=re.ASCII)
_DECIMAL_18 = re.compile(r"^-?[0-9]+\.[0-9]{18}$", flags=re.ASCII)
_COMBINATION_KEYS = frozenset(
    f"{prefix_count}|{window.value}|{criterion.value}"
    for prefix_count in B649_PREFIX_COUNTS
    for window in B649_HISTORY_WINDOWS
    for criterion in B649_SUCCESS_CRITERIA
)
_LEGACY_COMBINATION_FIELDS = {
    "coverage",
    "effective_backtest_draw_count",
    "historical_success_rate",
    "no_prize_count",
    "official_prize_counts",
    "random_baseline_rate_difference",
    "random_baseline_success_rate",
    "rank",
    "success_count",
    "successful_execution_count",
    "unranked_reason",
    "window_available_draws",
    "window_complete",
    "window_requested_draws",
}
_COMBINATION_FIELDS = _LEGACY_COMBINATION_FIELDS | {
    "official_any_prize_count",
    "official_any_prize_rate",
    "official_random_baseline_probability",
    "official_random_baseline_delta",
    "official_rank",
}
_PRIZE_FIELDS = {
    "first",
    "second",
    "third",
    "fourth",
    "fifth",
    "sixth",
    "seventh",
    "general",
}


class B649MultiTicketRecordProjectionError(RuntimeError):
    """The fixed packaged projection is absent or violates its closed contract."""


class B649ExactNativeRecordProjectionError(RuntimeError):
    """The fixed packaged V3 projection is absent or violates its closed contract."""


class PackagedB649MultiTicketRecordReader:
    """Read only the exact named resource; never discover reports at runtime."""

    def read(self) -> B649MultiTicketRecordDataset:
        return _read_packaged_projection()


class PackagedB649ExactNativeRecordReader:
    """Read only the exact named V3 resource; never discover reports at runtime."""

    def read(self) -> B649ExactNativeRecordDataset:
        return _read_packaged_exact_native_projection()


@lru_cache(maxsize=1)
def _read_packaged_projection() -> B649MultiTicketRecordDataset:
    resource = files("lottolab.strategies.data").joinpath(PROJECTION_RESOURCE_NAME)
    try:
        raw = resource.read_bytes()
    except (FileNotFoundError, OSError) as exc:
        raise B649MultiTicketRecordProjectionError(
            "the pinned B649 aggregate projection is unavailable"
        ) from exc
    return _parse_projection(raw)


def _parse_projection(raw: bytes) -> B649MultiTicketRecordDataset:
    try:
        parsed = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise B649MultiTicketRecordProjectionError(
            "the pinned B649 aggregate projection is invalid JSON"
        ) from exc
    document = _mapping(parsed, "projection")
    _exact_keys(
        document,
        {
            "catalog_sha256",
            "metrics_available_strategy_count",
            "metrics_unavailable_strategy_count",
            "projection_schema_version",
            "projection_sha256",
            "records",
            "source_reports",
        },
        "projection",
    )
    projection_schema_version = document["projection_schema_version"]
    if projection_schema_version not in (
        _LEGACY_PROJECTION_SCHEMA_VERSION,
        PROJECTION_SCHEMA_VERSION,
    ):
        raise B649MultiTicketRecordProjectionError(
            "the B649 aggregate projection schema is unsupported"
        )

    projection_sha256 = _sha256(document["projection_sha256"], "projection_sha256")
    canonical = json.dumps(
        {key: value for key, value in document.items() if key != "projection_sha256"},
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    if hashlib.sha256(canonical).hexdigest() != projection_sha256:
        raise B649MultiTicketRecordProjectionError(
            "the B649 aggregate projection checksum does not match"
        )

    catalog = load_full_strategy_catalog()
    if document["catalog_sha256"] != catalog.catalog_sha256:
        raise B649MultiTicketRecordProjectionError(
            "the B649 aggregate projection catalog checksum does not match"
        )

    report_by_strategy = _parse_source_reports(document["source_reports"])
    records_value = document["records"]
    if not isinstance(records_value, list):
        raise B649MultiTicketRecordProjectionError(
            "projection records must be a list"
        )
    records_raw = cast(list[object], records_value)
    if len(records_raw) != len(catalog.records):
        raise B649MultiTicketRecordProjectionError(
            "projection must contain exactly 221 strategy identities"
        )

    projected: list[B649MultiTicketRecord] = []
    seen_ids: set[str] = set()
    catalog_by_id = {record.strategy_id: record for record in catalog.records}
    for index, value in enumerate(records_raw):
        record = _mapping(value, f"records[{index}]")
        _exact_keys(
            record,
            {
                "authority_mode",
                "combinations",
                "duplicate_alias_target",
                "legacy_method_id",
                "method_family",
                "metrics_unavailable_reason",
                "report_file_sha256",
                "report_sha256",
                "reproduction_status",
                "source_path",
                "strategy_id",
                "strategy_version",
                "unranked_reason",
            },
            f"records[{index}]",
        )
        strategy_id = _string(record["strategy_id"], "strategy_id")
        if strategy_id in seen_ids or strategy_id not in catalog_by_id:
            raise B649MultiTicketRecordProjectionError(
                "projection strategy identities are not an exact unique catalog set"
            )
        seen_ids.add(strategy_id)
        catalog_record = catalog_by_id[strategy_id]
        _validate_identity(record, catalog_record)
        projected.extend(
            _expand_record(
                record,
                catalog_record,
                catalog.catalog_sha256,
                report_by_strategy,
                projection_schema_version=projection_schema_version,
            )
        )

    if seen_ids != set(catalog_by_id):
        raise B649MultiTicketRecordProjectionError(
            "projection strategy identities do not cover the catalog"
        )
    backtested_ids = {
        row.strategy_id
        for row in catalog.records
        if row.reproduction_status is ReproductionStatus.BACKTESTED
    }
    if set(report_by_strategy) != backtested_ids - METRICS_UNAVAILABLE_STRATEGY_IDS:
        raise B649MultiTicketRecordProjectionError(
            "source reports do not cover exactly all metrics-eligible "
            "BACKTESTED strategies"
        )
    metrics_available_strategy_count = _nonnegative_integer(
        document["metrics_available_strategy_count"],
        "metrics_available_strategy_count",
    )
    metrics_unavailable_strategy_count = _nonnegative_integer(
        document["metrics_unavailable_strategy_count"],
        "metrics_unavailable_strategy_count",
    )
    if (
        metrics_available_strategy_count + metrics_unavailable_strategy_count
        != len(backtested_ids)
    ):
        raise B649MultiTicketRecordProjectionError(
            "metrics completeness counts do not sum to the BACKTESTED total"
        )
    if metrics_unavailable_strategy_count != len(
        METRICS_UNAVAILABLE_STRATEGY_IDS & backtested_ids
    ):
        raise B649MultiTicketRecordProjectionError(
            "metrics_unavailable_strategy_count does not match the pinned exception set"
        )
    return B649MultiTicketRecordDataset(
        records=tuple(projected),
        catalog_sha256=catalog.catalog_sha256,
        projection_sha256=projection_sha256,
        source_report_count=len(
            {pair for pair, _mode in report_by_strategy.values()}
        ),
        metrics_available_strategy_count=metrics_available_strategy_count,
        metrics_unavailable_strategy_count=metrics_unavailable_strategy_count,
    )


def _parse_source_reports(
    value: object,
) -> dict[str, tuple[tuple[str, str], str]]:
    if not isinstance(value, list):
        raise B649MultiTicketRecordProjectionError(
            "projection source_reports must be a list"
        )
    source_reports = cast(list[object], value)
    report_by_strategy: dict[str, tuple[tuple[str, str], str]] = {}
    report_pairs: set[tuple[str, str]] = set()
    for index, candidate in enumerate(source_reports):
        report = _mapping(candidate, f"source_reports[{index}]")
        authority_mode = _string(report.get("authority_mode"), "authority_mode")
        if authority_mode == AUTHORITY_MODE_HISTORICAL_SEALED:
            _exact_keys(
                report,
                {"authority_mode", "report_file_sha256", "report_sha256", "strategy_ids"},
                f"source_reports[{index}]",
            )
        elif authority_mode == AUTHORITY_MODE_FRESH_REPRODUCTION:
            _exact_keys(
                report,
                {
                    "authority_mode",
                    "dataset_sha256",
                    "report_file_sha256",
                    "report_sha256",
                    "strategy_ids",
                },
                f"source_reports[{index}]",
            )
            try:
                validate_b649_dataset_sha256(
                    report["dataset_sha256"],
                    authority_mode=AUTHORITY_MODE_FRESH_REPRODUCTION,
                )
            except B649DatasetAuthorityError as exc:
                raise B649MultiTicketRecordProjectionError(
                    f"source_reports[{index}] dataset authority is invalid"
                ) from exc
        else:
            raise B649MultiTicketRecordProjectionError(
                f"source_reports[{index}] has an unknown authority_mode"
            )
        pair = (
            _sha256(report["report_file_sha256"], "report_file_sha256"),
            _sha256(report["report_sha256"], "report_sha256"),
        )
        if pair in report_pairs:
            raise B649MultiTicketRecordProjectionError(
                "projection source_reports contain a duplicate report"
            )
        report_pairs.add(pair)
        strategy_ids = report["strategy_ids"]
        if not isinstance(strategy_ids, list) or not strategy_ids:
            raise B649MultiTicketRecordProjectionError(
                "each source report must identify at least one strategy"
            )
        for strategy_id_value in cast(list[object], strategy_ids):
            strategy_id = _string(strategy_id_value, "source report strategy_id")
            if strategy_id in report_by_strategy:
                raise B649MultiTicketRecordProjectionError(
                    "a BACKTESTED strategy is claimed by multiple source reports"
                )
            report_by_strategy[strategy_id] = (pair, authority_mode)
    return report_by_strategy


def _validate_identity(
    record: dict[str, object],
    catalog_record: FullStrategyCatalogRecord,
) -> None:
    expected: dict[str, object] = {
        "duplicate_alias_target": catalog_record.duplicate_alias_target,
        "legacy_method_id": catalog_record.legacy_method_id,
        "method_family": catalog_record.method_family,
        "reproduction_status": catalog_record.reproduction_status.value,
        "source_path": catalog_record.source_path,
        "strategy_id": catalog_record.strategy_id,
        "strategy_version": catalog_record.strategy_version,
        "unranked_reason": catalog_record.unranked_reason,
    }
    if any(record[key] != value for key, value in expected.items()):
        raise B649MultiTicketRecordProjectionError(
            f"projection identity differs from catalog for {catalog_record.strategy_id}"
        )


def _expand_record(
    record: dict[str, object],
    catalog_record: FullStrategyCatalogRecord,
    catalog_sha256: str,
    report_by_strategy: dict[str, tuple[tuple[str, str], str]],
    *,
    projection_schema_version: object,
) -> list[B649MultiTicketRecord]:
    combinations = _mapping(record["combinations"], "record combinations")
    metrics_unavailable_reason = record["metrics_unavailable_reason"]
    if metrics_unavailable_reason is not None and (
        catalog_record.strategy_id not in METRICS_UNAVAILABLE_STRATEGY_IDS
        or not isinstance(metrics_unavailable_reason, str)
    ):
        raise B649MultiTicketRecordProjectionError(
            f"{catalog_record.strategy_id} may not claim a metrics-unavailable reason"
        )
    backtested = catalog_record.reproduction_status is ReproductionStatus.BACKTESTED
    has_metrics = backtested and metrics_unavailable_reason is None
    authority_mode: str | None = None
    if has_metrics:
        if frozenset(combinations) != _COMBINATION_KEYS:
            raise B649MultiTicketRecordProjectionError(
                f"{catalog_record.strategy_id} must contain all 128 aggregate combinations"
            )
        expected = report_by_strategy.get(catalog_record.strategy_id)
        pair = (
            _sha256(record["report_file_sha256"], "report_file_sha256"),
            _sha256(record["report_sha256"], "report_sha256"),
        )
        if expected is None or expected[0] != pair:
            raise B649MultiTicketRecordProjectionError(
                f"{catalog_record.strategy_id} report provenance does not match"
            )
        report_file_sha256, report_sha256 = pair
        authority_mode = expected[1]
        if record["authority_mode"] != authority_mode:
            raise B649MultiTicketRecordProjectionError(
                f"{catalog_record.strategy_id} authority_mode does not match its source report"
            )
    elif backtested:
        if combinations:
            raise B649MultiTicketRecordProjectionError(
                f"{catalog_record.strategy_id} is metrics-unavailable and may not "
                "carry aggregate combinations"
            )
        report_file_sha256 = _sha256(
            record["report_file_sha256"], "report_file_sha256"
        )
        report_sha256 = _sha256(record["report_sha256"], "report_sha256")
        if record["authority_mode"] is not None:
            raise B649MultiTicketRecordProjectionError(
                f"{catalog_record.strategy_id} is metrics-unavailable and may not "
                "carry an authority_mode"
            )
    else:
        if (
            combinations
            or record["report_file_sha256"] is not None
            or record["report_sha256"] is not None
            or record["authority_mode"] is not None
        ):
            raise B649MultiTicketRecordProjectionError(
                f"{catalog_record.strategy_id} may not claim aggregate report data"
            )
        report_file_sha256 = None
        report_sha256 = None

    result: list[B649MultiTicketRecord] = []
    for prefix_count in B649_PREFIX_COUNTS:
        for window in B649_HISTORY_WINDOWS:
            for criterion in B649_SUCCESS_CRITERIA:
                combination = (
                    _parse_combination(
                        combinations[
                            f"{prefix_count}|{window.value}|{criterion.value}"
                        ],
                        catalog_record.strategy_id,
                        projection_schema_version=projection_schema_version,
                    )
                    if has_metrics
                    else None
                )
                result.append(
                    _build_record(
                        catalog_record=catalog_record,
                        prefix_count=prefix_count,
                        window=window,
                        criterion=criterion,
                        combination=combination,
                        report_sha256=report_sha256,
                        report_file_sha256=report_file_sha256,
                        catalog_sha256=catalog_sha256,
                        authority_mode=authority_mode,
                        metrics_unavailable_reason=(
                            metrics_unavailable_reason
                            if isinstance(metrics_unavailable_reason, str)
                            else None
                        ),
                    )
                )
    return result


def _parse_combination(
    value: object,
    strategy_id: str,
    *,
    projection_schema_version: object,
) -> dict[str, object]:
    combination = _mapping(value, f"{strategy_id} combination")
    if projection_schema_version == _LEGACY_PROJECTION_SCHEMA_VERSION:
        _exact_keys(
            combination,
            _LEGACY_COMBINATION_FIELDS,
            f"{strategy_id} combination",
        )
        official_fields: dict[str, object] = {
            "official_any_prize_count": None,
            "official_any_prize_rate": None,
            "official_random_baseline_probability": None,
            "official_random_baseline_delta": None,
            "official_rank": None,
        }
    else:
        _exact_keys(combination, _COMBINATION_FIELDS, f"{strategy_id} combination")
        official_fields = {
            field_name: combination[field_name]
            for field_name in (
                "official_any_prize_count",
                "official_any_prize_rate",
                "official_random_baseline_probability",
                "official_random_baseline_delta",
                "official_rank",
            )
        }
    rank = combination["rank"]
    official_rank = official_fields["official_rank"]
    reason = combination["unranked_reason"]
    legacy_projection = (
        projection_schema_version == _LEGACY_PROJECTION_SCHEMA_VERSION
    )
    if rank is not None:
        _positive_integer(rank, "rank")
        if reason is not None:
            raise B649MultiTicketRecordProjectionError(
                "ranked combinations cannot carry an unranked reason"
            )
    elif not isinstance(reason, str) or not reason:
        raise B649MultiTicketRecordProjectionError(
            "unranked combinations require a formal reason"
        )
    if not legacy_projection:
        if official_rank is not None:
            _positive_integer(official_rank, "official_rank")
        elif reason is None:
            raise B649MultiTicketRecordProjectionError(
                "unranked official combinations require a formal reason"
            )
    for field_name in (
        "success_count",
        "effective_backtest_draw_count",
        "successful_execution_count",
        "window_available_draws",
        "window_requested_draws",
        "no_prize_count",
    ):
        _nonnegative_integer(combination[field_name], field_name)
    if not legacy_projection and official_fields["official_any_prize_count"] is None:
        raise B649MultiTicketRecordProjectionError(
            "official_any_prize_count is required in projection V2"
        )
    if official_fields["official_any_prize_count"] is not None:
        _nonnegative_integer(
            official_fields["official_any_prize_count"],
            "official_any_prize_count",
        )
        for field_name in (
            "official_any_prize_rate",
            "official_random_baseline_probability",
            "official_random_baseline_delta",
        ):
            value = official_fields[field_name]
            if not isinstance(value, str) or _DECIMAL_18.fullmatch(value) is None:
                raise B649MultiTicketRecordProjectionError(
                    f"{field_name} must be an exact decimal_18 string"
                )
    for field_name in (
        "historical_success_rate",
        "random_baseline_success_rate",
        "random_baseline_rate_difference",
        "coverage",
    ):
        value = combination[field_name]
        if not isinstance(value, str) or _DECIMAL_18.fullmatch(value) is None:
            raise B649MultiTicketRecordProjectionError(
                f"{field_name} must be an exact decimal_18 string"
            )
    if type(combination["window_complete"]) is not bool:
        raise B649MultiTicketRecordProjectionError(
            "window_complete must be a boolean"
        )
    prizes = _mapping(combination["official_prize_counts"], "official_prize_counts")
    _exact_keys(prizes, _PRIZE_FIELDS, "official_prize_counts")
    for field_name in _PRIZE_FIELDS:
        _nonnegative_integer(prizes[field_name], field_name)
    return {**combination, **official_fields}


def _build_record(
    *,
    catalog_record: FullStrategyCatalogRecord,
    prefix_count: int,
    window: B649HistoryWindow,
    criterion: B649SuccessCriterion,
    combination: dict[str, object] | None,
    report_sha256: str | None,
    report_file_sha256: str | None,
    catalog_sha256: str,
    authority_mode: str | None,
    metrics_unavailable_reason: str | None,
) -> B649MultiTicketRecord:
    if combination is None:
        return B649MultiTicketRecord(
            strategy_id=catalog_record.strategy_id,
            strategy_version=catalog_record.strategy_version,
            legacy_method_id=catalog_record.legacy_method_id,
            source_path=catalog_record.source_path,
            method_family=catalog_record.method_family,
            reproduction_status=catalog_record.reproduction_status,
            duplicate_alias_target=catalog_record.duplicate_alias_target,
            prefix_count=prefix_count,
            window=window,
            criterion=criterion,
            rank=None,
            official_rank=None,
            official_any_prize_count=None,
            official_any_prize_rate=None,
            official_random_baseline_probability=None,
            official_random_baseline_delta=None,
            unranked_reason=catalog_record.unranked_reason,
            success_count=None,
            effective_backtest_draw_count=None,
            successful_execution_count=None,
            historical_success_rate=None,
            random_baseline_success_rate=None,
            random_baseline_rate_difference=None,
            coverage=None,
            window_available_draws=None,
            window_requested_draws=None,
            window_complete=None,
            official_prize_counts=None,
            no_prize_count=None,
            report_sha256=report_sha256,
            report_file_sha256=report_file_sha256,
            catalog_sha256=catalog_sha256,
            authority_mode=authority_mode,
            metrics_unavailable_reason=metrics_unavailable_reason,
        )
    prizes = cast(dict[str, object], combination["official_prize_counts"])
    return B649MultiTicketRecord(
        strategy_id=catalog_record.strategy_id,
        strategy_version=catalog_record.strategy_version,
        legacy_method_id=catalog_record.legacy_method_id,
        source_path=catalog_record.source_path,
        method_family=catalog_record.method_family,
        reproduction_status=catalog_record.reproduction_status,
        duplicate_alias_target=catalog_record.duplicate_alias_target,
        prefix_count=prefix_count,
        window=window,
        criterion=criterion,
        rank=cast(int | None, combination["rank"]),
        official_rank=cast(int | None, combination["official_rank"]),
        official_any_prize_count=cast(
            int | None,
            combination["official_any_prize_count"],
        ),
        official_any_prize_rate=cast(
            str | None,
            combination["official_any_prize_rate"],
        ),
        official_random_baseline_probability=cast(
            str | None,
            combination["official_random_baseline_probability"],
        ),
        official_random_baseline_delta=cast(
            str | None,
            combination["official_random_baseline_delta"],
        ),
        unranked_reason=cast(str | None, combination["unranked_reason"]),
        success_count=cast(int, combination["success_count"]),
        effective_backtest_draw_count=cast(
            int, combination["effective_backtest_draw_count"]
        ),
        successful_execution_count=cast(
            int, combination["successful_execution_count"]
        ),
        historical_success_rate=cast(str, combination["historical_success_rate"]),
        random_baseline_success_rate=cast(
            str, combination["random_baseline_success_rate"]
        ),
        random_baseline_rate_difference=cast(
            str, combination["random_baseline_rate_difference"]
        ),
        coverage=cast(str, combination["coverage"]),
        window_available_draws=cast(int, combination["window_available_draws"]),
        window_requested_draws=cast(int, combination["window_requested_draws"]),
        window_complete=cast(bool, combination["window_complete"]),
        official_prize_counts=B649OfficialPrizeCounts(
            first=cast(int, prizes["first"]),
            second=cast(int, prizes["second"]),
            third=cast(int, prizes["third"]),
            fourth=cast(int, prizes["fourth"]),
            fifth=cast(int, prizes["fifth"]),
            sixth=cast(int, prizes["sixth"]),
            seventh=cast(int, prizes["seventh"]),
            general=cast(int, prizes["general"]),
        ),
        no_prize_count=cast(int, combination["no_prize_count"]),
        report_sha256=report_sha256,
        report_file_sha256=report_file_sha256,
        catalog_sha256=catalog_sha256,
        authority_mode=authority_mode,
        metrics_unavailable_reason=metrics_unavailable_reason,
    )


def _mapping(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(
        isinstance(key, str) for key in cast(dict[object, object], value)
    ):
        raise B649MultiTicketRecordProjectionError(f"{label} must be an object")
    return cast(dict[str, object], value)


def _exact_keys(value: dict[str, object], expected: set[str], label: str) -> None:
    if set(value) != expected:
        raise B649MultiTicketRecordProjectionError(
            f"{label} fields do not match the closed schema"
        )


def _string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise B649MultiTicketRecordProjectionError(f"{label} must be non-empty")
    return value


def _sha256(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise B649MultiTicketRecordProjectionError(
            f"{label} must be a lowercase SHA-256"
        )
    return value


def _positive_integer(value: object, label: str) -> int:
    integer = _nonnegative_integer(value, label)
    if integer == 0:
        raise B649MultiTicketRecordProjectionError(f"{label} must be positive")
    return integer


def _nonnegative_integer(value: object, label: str) -> int:
    if type(value) is not int or value < 0:
        raise B649MultiTicketRecordProjectionError(
            f"{label} must be a non-negative integer"
        )
    return value


@lru_cache(maxsize=1)
def _read_packaged_exact_native_projection() -> B649ExactNativeRecordDataset:
    resource = files("lottolab.strategies.data").joinpath(PROJECTION_RESOURCE_NAME_V3)
    try:
        raw = resource.read_bytes()
    except (FileNotFoundError, OSError) as exc:
        raise B649ExactNativeRecordProjectionError(
            "the pinned B649 exact-native projection is unavailable"
        ) from exc
    return _parse_exact_native_projection(raw)


def _exact_native_mapping(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(
        isinstance(key, str) for key in cast(dict[object, object], value)
    ):
        raise B649ExactNativeRecordProjectionError(f"{label} must be an object")
    return cast(dict[str, object], value)


def _exact_native_string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise B649ExactNativeRecordProjectionError(f"{label} must be non-empty")
    return value


def _exact_native_nonnegative_integer(value: object, label: str) -> int:
    if type(value) is not int or value < 0:
        raise B649ExactNativeRecordProjectionError(
            f"{label} must be a non-negative integer"
        )
    return value


def _exact_native_decimal_18(value: object, label: str) -> str:
    if not isinstance(value, str) or _DECIMAL_18.fullmatch(value) is None:
        raise B649ExactNativeRecordProjectionError(
            f"{label} must be an exact decimal_18 string"
        )
    return value


def _exact_native_opt_int(value: object, label: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    raise B649ExactNativeRecordProjectionError(
        f"{label} must be an integer or null"
    )


def _exact_native_opt_str(value: object, label: str) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    raise B649ExactNativeRecordProjectionError(
        f"{label} must be a string or null"
    )


def _exact_native_opt_bool(value: object, label: str) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    raise B649ExactNativeRecordProjectionError(
        f"{label} must be a boolean or null"
    )


def _parse_exact_native_projection(raw: bytes) -> B649ExactNativeRecordDataset:
    try:
        parsed = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise B649ExactNativeRecordProjectionError(
            "the pinned B649 exact-native projection is invalid JSON"
        ) from exc
    document = _exact_native_mapping(parsed, "exact_native_projection")
    if document.get("projection_schema_version") != PROJECTION_SCHEMA_VERSION_V3:
        raise B649ExactNativeRecordProjectionError(
            "the B649 exact-native projection schema is unsupported"
        )

    projection_sha256 = document.get("projection_sha256")
    if not isinstance(projection_sha256, str) or _SHA256.fullmatch(projection_sha256) is None:
        raise B649ExactNativeRecordProjectionError(
            "projection_sha256 must be a lowercase SHA-256"
        )

    canonical = json.dumps(
        {key: value for key, value in document.items() if key != "projection_sha256"},
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    if hashlib.sha256(canonical).hexdigest() != projection_sha256:
        raise B649ExactNativeRecordProjectionError(
            "the B649 exact-native projection checksum does not match"
        )

    catalog = load_full_strategy_catalog()
    if document.get("catalog_sha256") != catalog.catalog_sha256:
        raise B649ExactNativeRecordProjectionError(
            "the B649 exact-native projection catalog checksum does not match"
        )

    records_value = document.get("exact_native_records")
    if not isinstance(records_value, list):
        raise B649ExactNativeRecordProjectionError(
            "exact_native_records must be a list"
        )
    records_raw = cast(list[object], records_value)
    expected_count = (
        len(catalog.records)
        * len(B649_EXACT_NATIVE_TICKET_COUNTS)
        * len(B649_HISTORY_WINDOWS)
    )
    if len(records_raw) != expected_count:
        raise B649ExactNativeRecordProjectionError(
            f"exact_native_records must contain exactly {expected_count} records"
        )

    catalog_by_id = {record.strategy_id: record for record in catalog.records}
    projected: list[B649ExactNativeRecord] = []
    available_counts: dict[str, int] = {}
    if isinstance(document.get("available_strategy_count_by_exact_ticket_count"), dict):
        available_counts = {
            str(k): int(cast(int | str, v))
            for k, v in cast(
                dict[object, object],
                document["available_strategy_count_by_exact_ticket_count"],
            ).items()
        }

    for index, value in enumerate(records_raw):
        record = _exact_native_mapping(value, f"exact_native_records[{index}]")
        strategy_id = _exact_native_string(record.get("strategy_id"), "strategy_id")
        if strategy_id not in catalog_by_id:
            raise B649ExactNativeRecordProjectionError(
                f"unknown strategy_id {strategy_id} in exact_native_records[{index}]"
            )
        catalog_record = catalog_by_id[strategy_id]
        if record.get("reproduction_status") != catalog_record.reproduction_status.value:
            raise B649ExactNativeRecordProjectionError(
                f"reproduction_status mismatch for {strategy_id}"
            )
        ticket_count = _exact_native_nonnegative_integer(
            record.get("ticket_count"), "ticket_count"
        )
        if ticket_count not in B649_EXACT_NATIVE_TICKET_COUNTS:
            raise B649ExactNativeRecordProjectionError(
                f"invalid ticket_count {ticket_count} in exact_native_records[{index}]"
            )
        window_str = _exact_native_string(record.get("window"), "window")
        try:
            window = B649HistoryWindow(window_str)
        except ValueError as exc:
            raise B649ExactNativeRecordProjectionError(
                f"unsupported window {window_str} in exact_native_records[{index}]"
            ) from exc

        metric_status_raw = _exact_native_string(record.get("metric_status"), "metric_status")
        if metric_status_raw not in ("AVAILABLE", "UNAVAILABLE"):
            raise B649ExactNativeRecordProjectionError(
                f"invalid metric_status {metric_status_raw} in exact_native_records[{index}]"
            )
        metric_status = metric_status_raw

        rankable_raw = record.get("rankable")
        if not isinstance(rankable_raw, bool):
            raise B649ExactNativeRecordProjectionError(
                f"rankable must be boolean in exact_native_records[{index}]"
            )
        rankable = rankable_raw

        unavailable_reason: str | None = None
        if record.get("unavailable_reason") is not None:
            unavailable_reason = _exact_native_string(
                record.get("unavailable_reason"), "unavailable_reason"
            )

        official_prize_counts: B649OfficialPrizeCounts | None = None
        if record.get("official_prize_counts") is not None:
            prize_dict = _exact_native_mapping(
                record.get("official_prize_counts"), "official_prize_counts"
            )
            official_prize_counts = B649OfficialPrizeCounts(
                first=_exact_native_nonnegative_integer(prize_dict.get("first"), "first"),
                second=_exact_native_nonnegative_integer(prize_dict.get("second"), "second"),
                third=_exact_native_nonnegative_integer(prize_dict.get("third"), "third"),
                fourth=_exact_native_nonnegative_integer(prize_dict.get("fourth"), "fourth"),
                fifth=_exact_native_nonnegative_integer(prize_dict.get("fifth"), "fifth"),
                sixth=_exact_native_nonnegative_integer(prize_dict.get("sixth"), "sixth"),
                seventh=_exact_native_nonnegative_integer(prize_dict.get("seventh"), "seventh"),
                general=_exact_native_nonnegative_integer(prize_dict.get("general"), "general"),
            )

        official_any_prize_count: int | None = None
        if record.get("official_any_prize_count") is not None:
            official_any_prize_count = _exact_native_nonnegative_integer(
                record.get("official_any_prize_count"), "official_any_prize_count"
            )

        official_any_prize_rate: str | None = None
        if record.get("official_any_prize_rate") is not None:
            official_any_prize_rate = _exact_native_decimal_18(
                record.get("official_any_prize_rate"), "official_any_prize_rate"
            )

        official_random_baseline_probability: str | None = None
        if record.get("official_random_baseline_probability") is not None:
            official_random_baseline_probability = _exact_native_decimal_18(
                record.get("official_random_baseline_probability"),
                "official_random_baseline_probability",
            )

        official_random_baseline_delta: str | None = None
        if record.get("official_random_baseline_delta") is not None:
            official_random_baseline_delta = _exact_native_decimal_18(
                record.get("official_random_baseline_delta"),
                "official_random_baseline_delta",
            )

        coverage: str | None = None
        if record.get("coverage") is not None:
            coverage = _exact_native_decimal_18(record.get("coverage"), "coverage")

        native_dist: dict[str, int] = {}
        if isinstance(record.get("native_ticket_count_distribution"), dict):
            native_dist = {
                str(k): int(cast(int | str, v))
                for k, v in cast(
                    dict[object, object],
                    record["native_ticket_count_distribution"],
                ).items()
            }

        execution_status_counts: dict[str, int] = {}
        if isinstance(record.get("execution_status_counts"), dict):
            execution_status_counts = {
                str(k): int(cast(int | str, v))
                for k, v in cast(
                    dict[object, object],
                    record["execution_status_counts"],
                ).items()
            }

        projected.append(
            B649ExactNativeRecord(
                strategy_id=catalog_record.strategy_id,
                strategy_version=catalog_record.strategy_version,
                legacy_method_id=catalog_record.legacy_method_id,
                source_path=catalog_record.source_path,
                method_family=catalog_record.method_family,
                reproduction_status=catalog_record.reproduction_status,
                duplicate_alias_target=(
                    str(record["duplicate_alias_target"])
                    if record.get("duplicate_alias_target") is not None
                    else None
                ),
                ticket_count=ticket_count,
                window=window,
                criterion=_exact_native_string(record.get("criterion"), "criterion"),
                metric_status=metric_status,
                rankable=rankable,
                unavailable_reason=unavailable_reason,
                metrics_unavailable_reason=_exact_native_opt_str(
                    record.get("metrics_unavailable_reason"), "metrics_unavailable_reason"
                ),
                unranked_reason=_exact_native_opt_str(
                    record.get("unranked_reason"), "unranked_reason"
                ),
                official_any_prize_count=official_any_prize_count,
                official_any_prize_rate=official_any_prize_rate,
                official_random_baseline_probability=official_random_baseline_probability,
                official_random_baseline_delta=official_random_baseline_delta,
                coverage=coverage,
                official_prize_counts=official_prize_counts,
                no_prize_count=_exact_native_opt_int(
                    record.get("no_prize_count"), "no_prize_count"
                ),
                available_observation_count=_exact_native_opt_int(
                    record.get("available_observation_count"), "available_observation_count"
                ),
                effective_backtest_draw_count=_exact_native_opt_int(
                    record.get("effective_backtest_draw_count"), "effective_backtest_draw_count"
                ),
                successful_observation_count=_exact_native_opt_int(
                    record.get("successful_observation_count"), "successful_observation_count"
                ),
                ticket_position_count=_exact_native_opt_int(
                    record.get("ticket_position_count"), "ticket_position_count"
                ),
                observed_distinct_ticket_count=_exact_native_opt_int(
                    record.get("observed_distinct_ticket_count"), "observed_distinct_ticket_count"
                ),
                observed_duplicate_ticket_count=_exact_native_opt_int(
                    record.get("observed_duplicate_ticket_count"), "observed_duplicate_ticket_count"
                ),
                native_ticket_count_classification=_exact_native_opt_str(
                    record.get("native_ticket_count_classification"),
                    "native_ticket_count_classification",
                ),
                native_ticket_count_distribution=native_dist,
                execution_status_counts=execution_status_counts,
                window_available_draws=_exact_native_opt_int(
                    record.get("window_available_draws"), "window_available_draws"
                ),
                window_requested_draws=_exact_native_opt_int(
                    record.get("window_requested_draws"), "window_requested_draws"
                ),
                window_complete=_exact_native_opt_bool(
                    record.get("window_complete"), "window_complete"
                ),
                authority_mode=_exact_native_opt_str(
                    record.get("authority_mode"), "authority_mode"
                ),
                input_canonical_sha256=_exact_native_opt_str(
                    record.get("input_canonical_sha256"), "input_canonical_sha256"
                ),
                input_raw_sha256=_exact_native_opt_str(
                    record.get("input_raw_sha256"), "input_raw_sha256"
                ),
                catalog_sha256=catalog.catalog_sha256,
                official_rank=None,
            )
        )

    return B649ExactNativeRecordDataset(
        records=tuple(projected),
        catalog_sha256=catalog.catalog_sha256,
        projection_sha256=projection_sha256,
        available_strategy_count_by_exact_ticket_count=available_counts,
    )


__all__ = [
    "PROJECTION_RESOURCE_NAME",
    "PROJECTION_RESOURCE_NAME_V3",
    "PROJECTION_SCHEMA_VERSION",
    "PROJECTION_SCHEMA_VERSION_V3",
    "B649ExactNativeRecordProjectionError",
    "B649MultiTicketRecordProjectionError",
    "PackagedB649ExactNativeRecordReader",
    "PackagedB649MultiTicketRecordReader",
]

K10_PROJECTION_RESOURCE_NAME = "biglotto_exact_native_k10_115000084_records_v1.json"
K10_PROJECTION_SCHEMA_VERSION = "B649_EXACT_NATIVE_K10_RECORDS_V1"
K10_AUTHORITY: dict[str, object] = {
    "authority_head": "2c861c91490df9fae0a1484b0cca1e0dd93d4a22",
    "authority_tree": "693205beb9fb19f2a56847893d00e7dc9607b4f7",
    "manifest_locator": (
        '/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.task-data/BIGLOTTO_1'
        '15000084_K10_EXACT_NATIVE_CANONICAL_REFRESH_R1/sealed_manifest.json'
    ),
    "sealed_manifest_sha256": "32dc65b424cf805b481160a8b0d88d5a838daa30ffdb31d877d2a990f4d7c47d",
    "target_evidence_sha256": "e3e56e1e0bacc6bbb03edd3610ae2339f864f82285da00bb6723fc344f4f16c6",
    "source_ranking_locator": (
        '/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.task-data/BIGLOTTO_1'
        '15000084_K10_EXACT_NATIVE_CANONICAL_REFRESH_R1/ranking.json'
    ),
    "source_ranking_sha256": "075aa7d9667e62f87612d0e5fe15958e3ab93dc6d4e023ff5a503b5a2453ea25",
    "run_id": "BIGLOTTO_115000084_K10_EXACT_NATIVE_CANONICAL_REFRESH_R1",
    "lottery": "BIG_LOTTO",
    "k": 10,
    "cutoff": "115000084",
    "cutoff_label": "084",
    "evidence_record_count": 4332,
    "consumer_record_count": 8,
    "strategy_universe": [
        "legacy_biglotto__backtest_10bet_biglotto__054e85b088be",
        "legacy_biglotto__backtest_biglotto_coldpool_15__2a80423e3cf5",
    ],
    "producer_universe_fingerprint": (
        '3d3afa99db61965f4db80a24beb41ad56afa790c59409661e22454acf075ae93'
    ),
    "producer_catalog_fingerprint": (
        'c618e9d14692cfd23f6b08b3b103a6de64e4b3d5e47025263d3babb9fce47dba'
    ),
    "consumer_catalog_sha256": "9e2d9f6c3cffbfe9867d4aaafbf8c9315922503fc0b806dfc84627699e0d82e3",
}
K10_WINDOW_BOUNDARIES: dict[str, dict[str, object]] = {
    "FULL": {
        "first_target": "96000001",
        "first_target_date": "2007-01-02",
        "last_target": "115000084",
        "last_target_date": "2026-09-01",
        "observations_required": 2166,
    },
    "RECENT_300": {
        "first_target": "113000021",
        "first_target_date": "2024-02-16",
        "last_target": "115000084",
        "last_target_date": "2026-09-01",
        "observations_required": 300,
    },
    "RECENT_50": {
        "first_target": "115000035",
        "first_target_date": "2026-03-13",
        "last_target": "115000084",
        "last_target_date": "2026-09-01",
        "observations_required": 50,
    },
    "RECENT_750": {
        "first_target": "109000027",
        "first_target_date": "2020-03-06",
        "last_target": "115000084",
        "last_target_date": "2026-09-01",
        "observations_required": 750,
    },
}


class PackagedB649K10RecordReader:
    """Load only the tracked K10 resource, independently of the V3 resource."""

    def read(self, window: B649HistoryWindow | None = None) -> B649K10RecordDataset:
        return _read_packaged_k10_projection(window)


@lru_cache(maxsize=5)
def _read_packaged_k10_projection(
    window: B649HistoryWindow | None = None,
) -> B649K10RecordDataset:
    try:
        raw = files("lottolab.strategies.data").joinpath(K10_PROJECTION_RESOURCE_NAME).read_bytes()
    except OSError as exc:
        raise B649ExactNativeRecordProjectionError(
            "the pinned K10 projection is unavailable"
        ) from exc
    return parse_b649_k10_projection(raw, window)


def _k10_require(condition: bool, label: str) -> None:
    if not condition:
        raise B649ExactNativeRecordProjectionError(f"invalid K10 {label}")


def parse_b649_k10_projection(
    raw: bytes,
    window: B649HistoryWindow | None = None,
) -> B649K10RecordDataset:
    """Validate the envelope globally and metric payloads only in the selected window."""
    try:
        document = _exact_native_mapping(json.loads(raw), "K10 projection")
    except (ValueError, UnicodeDecodeError) as exc:
        raise B649ExactNativeRecordProjectionError("invalid K10 JSON") from exc
    _k10_require(
        set(document) == {"projection_schema_version", "projection_sha256", "records"},
        "projection fields",
    )
    _k10_require(document["projection_schema_version"] == K10_PROJECTION_SCHEMA_VERSION, "schema")
    canonical = json.dumps(
        {k: v for k, v in document.items() if k != "projection_sha256"},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    checksum = hashlib.sha256(canonical).hexdigest()
    _k10_require(document["projection_sha256"] == checksum, "checksum")
    values = document["records"]
    _k10_require(isinstance(values, list) and len(cast(list[object], values)) == 8, "record count")
    records = [_exact_native_mapping(v, "K10 record") for v in cast(list[object], values)]
    universe = cast(list[str], K10_AUTHORITY["strategy_universe"])
    expected = {(sid, w.value) for sid in universe for w in B649_HISTORY_WINDOWS}
    identities = [(v.get("strategy_id"), v.get("window")) for v in records]
    _k10_require(all(isinstance(s, str) and isinstance(w, str) for s, w in identities), "identity")
    _k10_require(
        set(identities) == expected and len(identities) == len(set(identities)), "universe"
    )
    catalog = load_full_strategy_catalog()
    _k10_require(catalog.catalog_sha256 == K10_AUTHORITY["consumer_catalog_sha256"], "catalog")
    catalog_by_id = {r.strategy_id: r for r in catalog.records}
    positions: dict[str, int] = {}
    result: list[B649K10Record] = []
    adapter = TypeAdapter(B649K10Record)
    for value in records:
        w = str(value["window"])
        positions[w] = positions.get(w, 0) + 1
        _k10_require(
            type(value.get("source_order")) is int and value["source_order"] == positions[w],
            "source order",
        )
        _k10_require(value.get("provenance") == K10_AUTHORITY, "authority")
        _k10_require(value.get("window_boundary") == K10_WINDOW_BOUNDARIES[w], "window boundary")
        if window is not None and w != window.value:
            continue
        _k10_require(set(value) == {f.name for f in fields(B649K10Record)}, "record fields")
        _k10_require(
            set(_exact_native_mapping(value["provenance"], "provenance"))
            == {f.name for f in fields(B649K10Provenance)},
            "provenance fields",
        )
        _k10_require(
            set(_exact_native_mapping(value["window_boundary"], "boundary"))
            == {f.name for f in fields(B649K10WindowBoundary)},
            "boundary fields",
        )
        try:
            row = adapter.validate_json(json.dumps(value), strict=True)
        except ValidationError as exc:
            raise B649ExactNativeRecordProjectionError("invalid K10 record schema") from exc
        _k10_require(row.strategy_version == "v0.1", "producer version")
        _k10_require(row.rank == row.official_rank and (row.rank is None or row.rank > 0), "rank")
        _k10_require(row.rank is not None or bool(row.unranked_reason), "unranked reason")
        _k10_require(
            row.requested_draws == row.window_boundary.observations_required, "requested draws"
        )
        meta = catalog_by_id[row.strategy_id]
        for key in (
            "legacy_method_id",
            "source_path",
            "method_family",
            "reproduction_status",
            "duplicate_alias_target",
        ):
            _k10_require(getattr(row, key) == getattr(meta, key), f"catalog {key}")
        _k10_require(row.catalog_strategy_version == meta.strategy_version, "catalog version")
        metrics = (
            row.official_any_prize_rate,
            row.official_random_baseline,
            row.baseline_delta,
            row.coverage,
        )
        for metric in metrics:
            _k10_require(metric is None or _DECIMAL_18.fullmatch(metric) is not None, "decimal")
        for count in (
            row.evaluated_draws,
            row.official_any_prize_numerator,
            row.official_any_prize_denominator,
            row.typed_replay_failures_count,
        ):
            _k10_require(count is None or count >= 0, "count")
        for counts in (row.best_prize_counts, row.replay_status_counts):
            _k10_require(counts is None or all(n >= 0 for n in counts.values()), "sparse counts")
        if row.best_prize_counts is not None:
            _k10_require(set(row.best_prize_counts) <= {p.upper() for p in _PRIZE_FIELDS}, "prizes")
        if row.metric_status == "UNAVAILABLE":
            _k10_require(
                bool(row.unavailable_reason) and row.rank is None, "unavailable reason/rank"
            )
            _k10_require(
                all(v is None for v in metrics)
                and row.official_any_prize_numerator is None
                and row.official_any_prize_denominator is None
                and row.best_prize_counts is None,
                "unavailable metrics",
            )
        else:
            _k10_require(
                all(v is not None for v in metrics)
                and row.official_any_prize_numerator is not None
                and row.official_any_prize_denominator is not None,
                "available metrics",
            )
        result.append(row)
    return B649K10RecordDataset(tuple(result), checksum)
