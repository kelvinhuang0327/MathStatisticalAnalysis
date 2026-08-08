"""Fixed-resource reader for the immutable B649 aggregate-history projection."""

from __future__ import annotations

import hashlib
import json
import re
from functools import lru_cache
from importlib.resources import files
from typing import cast

from lottolab.application.biglotto_multi_ticket_records import (
    B649_AUTHORITY_MODE_FRESH_REPRODUCTION as AUTHORITY_MODE_FRESH_REPRODUCTION,
)
from lottolab.application.biglotto_multi_ticket_records import (
    B649_AUTHORITY_MODE_HISTORICAL_SEALED as AUTHORITY_MODE_HISTORICAL_SEALED,
)
from lottolab.application.biglotto_multi_ticket_records import (
    B649_HISTORY_WINDOWS,
    B649_PREFIX_COUNTS,
    B649_SUCCESS_CRITERIA,
    B649HistoryWindow,
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
PROJECTION_SCHEMA_VERSION = "B649_MULTI_TICKET_HISTORICAL_RECORDS_V1"
_SHA256 = re.compile(r"^[0-9a-f]{64}$", flags=re.ASCII)
_DECIMAL_18 = re.compile(r"^-?[0-9]+\.[0-9]{18}$", flags=re.ASCII)
_COMBINATION_KEYS = frozenset(
    f"{prefix_count}|{window.value}|{criterion.value}"
    for prefix_count in B649_PREFIX_COUNTS
    for window in B649_HISTORY_WINDOWS
    for criterion in B649_SUCCESS_CRITERIA
)
_COMBINATION_FIELDS = {
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


class PackagedB649MultiTicketRecordReader:
    """Read only the exact named resource; never discover reports at runtime."""

    def read(self) -> B649MultiTicketRecordDataset:
        return _read_packaged_projection()


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
    if document["projection_schema_version"] != PROJECTION_SCHEMA_VERSION:
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


def _parse_combination(value: object, strategy_id: str) -> dict[str, object]:
    combination = _mapping(value, f"{strategy_id} combination")
    _exact_keys(combination, _COMBINATION_FIELDS, f"{strategy_id} combination")
    rank = combination["rank"]
    reason = combination["unranked_reason"]
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
    for field_name in (
        "success_count",
        "effective_backtest_draw_count",
        "successful_execution_count",
        "window_available_draws",
        "window_requested_draws",
        "no_prize_count",
    ):
        _nonnegative_integer(combination[field_name], field_name)
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
    return combination


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


__all__ = [
    "PROJECTION_RESOURCE_NAME",
    "PROJECTION_SCHEMA_VERSION",
    "B649MultiTicketRecordProjectionError",
    "PackagedB649MultiTicketRecordReader",
]
