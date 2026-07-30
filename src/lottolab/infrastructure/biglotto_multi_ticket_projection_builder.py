"""Offline builder for the pinned B649 aggregate-history projection.

Every report path is explicit.  This module never discovers a newest report,
executes a strategy, opens a database, or regenerates a ticket.
"""

from __future__ import annotations

import hashlib
import json
import stat
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import cast

from lottolab.application.biglotto_multi_ticket_records import (
    B649_HISTORY_WINDOWS,
    B649_PREFIX_COUNTS,
    B649_SUCCESS_CRITERIA,
)
from lottolab.domain.biglotto_full_strategy_catalog import (
    FullStrategyCatalog,
    FullStrategyCatalogRecord,
    ReproductionStatus,
    load_full_strategy_catalog,
)
from lottolab.infrastructure.biglotto_multi_ticket_record_reader import (
    PROJECTION_SCHEMA_VERSION,
)


class B649ProjectionBuildError(RuntimeError):
    """Explicit pinned inputs cannot produce a complete aggregate projection."""


@dataclass(frozen=True, slots=True)
class ExpectedReport:
    report_file_sha256: str
    report_sha256: str
    strategy_ids: tuple[str, ...]


def build_b649_projection_bytes(report_paths: tuple[Path, ...]) -> bytes:
    """Build only when explicit reports cover all 135 BACKTESTED strategies."""

    catalog = load_full_strategy_catalog()
    manifest = expected_report_manifest(catalog)
    expected_by_file_hash = {
        report.report_file_sha256: report for report in manifest
    }
    supplied: dict[str, tuple[ExpectedReport, dict[str, object]]] = {}
    for path in report_paths:
        raw = _read_regular_file(path)
        file_sha256 = hashlib.sha256(raw).hexdigest()
        expected = expected_by_file_hash.get(file_sha256)
        if expected is None:
            raise B649ProjectionBuildError(
                f"{path} is not a checksum-pinned report from committed evidence"
            )
        if file_sha256 in supplied:
            raise B649ProjectionBuildError(
                f"report {file_sha256} was supplied more than once"
            )
        document = _report_document(raw, path)
        if document.get("report_sha256") != expected.report_sha256:
            raise B649ProjectionBuildError(
                f"{path} internal report SHA-256 does not match committed evidence"
            )
        _verify_report_self_hash(document, path)
        supplied[file_sha256] = (expected, document)

    required_strategy_ids = {
        row.strategy_id
        for row in catalog.records
        if row.reproduction_status is ReproductionStatus.BACKTESTED
    }
    supplied_strategy_ids = {
        strategy_id
        for expected, _document in supplied.values()
        for strategy_id in expected.strategy_ids
    }
    missing = sorted(required_strategy_ids - supplied_strategy_ids)
    unexpected = sorted(supplied_strategy_ids - required_strategy_ids)
    if missing or unexpected:
        raise B649ProjectionBuildError(
            "explicit reports do not cover exactly all 135 BACKTESTED strategies; "
            f"missing={len(missing)} unexpected={len(unexpected)}"
        )

    combinations_by_strategy: dict[str, dict[str, object]] = {}
    provenance_by_strategy: dict[str, tuple[str, str]] = {}
    source_reports: list[dict[str, object]] = []
    for file_sha256 in sorted(supplied):
        expected, document = supplied[file_sha256]
        _collect_report(
            document,
            expected,
            combinations_by_strategy,
            provenance_by_strategy,
        )
        source_reports.append(
            {
                "report_file_sha256": expected.report_file_sha256,
                "report_sha256": expected.report_sha256,
                "strategy_ids": list(expected.strategy_ids),
            }
        )

    records = [
        _projection_record(
            catalog_record,
            combinations_by_strategy,
            provenance_by_strategy,
        )
        for catalog_record in catalog.records
    ]
    document: dict[str, object] = {
        "catalog_sha256": catalog.catalog_sha256,
        "projection_schema_version": PROJECTION_SCHEMA_VERSION,
        "records": records,
        "source_reports": source_reports,
    }
    canonical = _canonical_json(document)
    document["projection_sha256"] = hashlib.sha256(canonical).hexdigest()
    return _canonical_json(document) + b"\n"


def expected_report_manifest(
    catalog: FullStrategyCatalog | None = None,
) -> tuple[ExpectedReport, ...]:
    """Resolve exact report checksums from fixed catalog-declared evidence files."""

    resolved_catalog = catalog if catalog is not None else load_full_strategy_catalog()
    data_root = files("lottolab.strategies.data")
    by_legacy_method_id = {
        record.legacy_method_id: record
        for record in resolved_catalog.records
        if record.reproduction_status is ReproductionStatus.BACKTESTED
    }
    by_strategy_id = {
        record.strategy_id: record
        for record in resolved_catalog.records
        if record.reproduction_status is ReproductionStatus.BACKTESTED
    }
    reports: list[ExpectedReport] = []
    claimed: set[str] = set()
    for artifact_name, artifact_sha256, _role in resolved_catalog.source_artifacts:
        if not artifact_name.endswith(".json"):
            continue
        resource = data_root.joinpath(artifact_name)
        try:
            raw = resource.read_bytes()
        except (FileNotFoundError, OSError):
            continue
        try:
            parsed = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise B649ProjectionBuildError(
                f"committed evidence is invalid JSON: {artifact_name}"
            ) from exc
        evidence = _mapping(parsed, f"evidence {artifact_name}")
        evidence_sha256 = evidence.get("evidence_sha256")
        if isinstance(evidence_sha256, str):
            evidence_canonical = _canonical_json(
                {
                    key: value
                    for key, value in evidence.items()
                    if key != "evidence_sha256"
                }
            )
            verified_evidence_sha256 = hashlib.sha256(evidence_canonical).hexdigest()
        else:
            verified_evidence_sha256 = hashlib.sha256(raw).hexdigest()
        if (
            verified_evidence_sha256 != artifact_sha256
            or (
                isinstance(evidence_sha256, str)
                and evidence_sha256 != verified_evidence_sha256
            )
        ):
            raise B649ProjectionBuildError(
                f"committed evidence checksum mismatch: {artifact_name}"
            )
        report_file_sha256, report_sha256 = _evidence_report_identity(evidence)
        strategies_value = evidence.get("strategies")
        if (
            not isinstance(report_file_sha256, str)
            or not isinstance(report_sha256, str)
            or not isinstance(strategies_value, list)
        ):
            continue
        strategy_ids: list[str] = []
        for index, strategy_value in enumerate(cast(list[object], strategies_value)):
            strategy = _mapping(
                strategy_value,
                f"evidence {artifact_name} strategies[{index}]",
            )
            catalog_strategy_id = strategy.get("catalog_strategy_id")
            legacy_method_id = strategy.get("legacy_method_id")
            catalog_record: FullStrategyCatalogRecord | None = None
            if isinstance(catalog_strategy_id, str):
                catalog_record = by_strategy_id.get(catalog_strategy_id)
            if catalog_record is None and isinstance(legacy_method_id, str):
                catalog_record = by_legacy_method_id.get(legacy_method_id)
            if catalog_record is None:
                raise B649ProjectionBuildError(
                    f"{artifact_name} contains an unknown BACKTESTED strategy"
                )
            if catalog_record.strategy_id in claimed:
                raise B649ProjectionBuildError(
                    f"{catalog_record.strategy_id} is claimed by multiple evidence reports"
                )
            claimed.add(catalog_record.strategy_id)
            strategy_ids.append(catalog_record.strategy_id)
        reports.append(
            ExpectedReport(
                report_file_sha256=_sha256(
                    report_file_sha256,
                    f"{artifact_name} report_file_sha256",
                ),
                report_sha256=_sha256(
                    report_sha256,
                    f"{artifact_name} report_sha256",
                ),
                strategy_ids=tuple(sorted(strategy_ids)),
            )
        )

    required = set(by_strategy_id)
    if claimed != required:
        raise B649ProjectionBuildError(
            "committed report evidence does not cover exactly all 135 "
            f"BACKTESTED strategies; missing={len(required - claimed)}"
        )
    if len({report.report_file_sha256 for report in reports}) != len(reports):
        raise B649ProjectionBuildError(
            "committed evidence contains duplicate physical report checksums"
        )
    return tuple(sorted(reports, key=lambda report: report.report_file_sha256))


def _evidence_report_identity(
    evidence: dict[str, object],
) -> tuple[object, object]:
    report_file_sha256 = evidence.get("report_file_sha256")
    report_sha256 = evidence.get("report_sha256")
    report_checksums_value = evidence.get("report_checksums")
    if isinstance(report_checksums_value, dict):
        report_checksums = cast(dict[object, object], report_checksums_value)
        report_file_sha256 = report_file_sha256 or report_checksums.get(
            "biglotto_multi_ticket_backtest_report.json"
        )
    full_report_value = evidence.get("full_report")
    if isinstance(full_report_value, dict):
        full_report = cast(dict[object, object], full_report_value)
        report_file_sha256 = report_file_sha256 or full_report.get("artifact_sha256")
        report_sha256 = report_sha256 or full_report.get("internal_report_sha256")
    return report_file_sha256, report_sha256


def _collect_report(
    report: dict[str, object],
    expected: ExpectedReport,
    combinations_by_strategy: dict[str, dict[str, object]],
    provenance_by_strategy: dict[str, tuple[str, str]],
) -> None:
    metrics = _list_of_mappings(report.get("metrics"), "report metrics")
    rankings = _list_of_mappings(report.get("rankings"), "report rankings")
    distributions = _list_of_mappings(
        report.get("official_prize_distributions"),
        "report official_prize_distributions",
    )
    expected_ids = set(expected.strategy_ids)
    own_metrics = [row for row in metrics if row.get("strategy_id") in expected_ids]
    own_rankings = [row for row in rankings if row.get("strategy_id") in expected_ids]
    own_distributions = [
        row for row in distributions if row.get("strategy_id") in expected_ids
    ]
    if {
        _string(row.get("strategy_id"), "metric strategy_id") for row in metrics
    } != expected_ids:
        raise B649ProjectionBuildError(
            "a pinned report metric set differs from committed evidence"
        )
    if {
        _string(row.get("strategy_id"), "prize strategy_id")
        for row in distributions
    } != expected_ids:
        raise B649ProjectionBuildError(
            "a pinned report prize set differs from committed evidence"
        )
    if len(own_metrics) != len(expected_ids) * 128:
        raise B649ProjectionBuildError(
            "a pinned report does not contain 128 metrics per expected strategy"
        )
    if len(own_rankings) != len(expected_ids) * 128:
        raise B649ProjectionBuildError(
            "a pinned report does not contain 128 rankings per expected strategy"
        )
    if len(own_distributions) != len(expected_ids) * 16:
        raise B649ProjectionBuildError(
            "a pinned report does not contain 16 prize distributions per expected strategy"
        )

    metric_index = {_metric_key(row): row for row in own_metrics}
    ranking_index = {_metric_key(row): row for row in own_rankings}
    prize_index = {_prize_key(row): row for row in own_distributions}
    if (
        len(metric_index) != len(own_metrics)
        or len(ranking_index) != len(own_rankings)
        or len(prize_index) != len(own_distributions)
    ):
        raise B649ProjectionBuildError(
            "a pinned report contains duplicate aggregate identities"
        )

    for strategy_id in expected.strategy_ids:
        if strategy_id in combinations_by_strategy:
            raise B649ProjectionBuildError(
                f"{strategy_id} was collected from multiple reports"
            )
        combinations: dict[str, object] = {}
        for prefix_count in B649_PREFIX_COUNTS:
            for window in B649_HISTORY_WINDOWS:
                prize = prize_index.get((strategy_id, prefix_count, window.value))
                if prize is None:
                    raise B649ProjectionBuildError(
                        f"{strategy_id} is missing an official prize distribution"
                    )
                for criterion in B649_SUCCESS_CRITERIA:
                    key = (
                        strategy_id,
                        prefix_count,
                        window.value,
                        criterion.value,
                    )
                    metric = metric_index.get(key)
                    ranking = ranking_index.get(key)
                    if metric is None or ranking is None:
                        raise B649ProjectionBuildError(
                            f"{strategy_id} is missing an aggregate combination"
                        )
                    combinations[
                        f"{prefix_count}|{window.value}|{criterion.value}"
                    ] = _combination(metric, ranking, prize)
        combinations_by_strategy[strategy_id] = combinations
        provenance_by_strategy[strategy_id] = (
            expected.report_file_sha256,
            expected.report_sha256,
        )


def _combination(
    metric: dict[str, object],
    ranking: dict[str, object],
    prize: dict[str, object],
) -> dict[str, object]:
    observed_rate = _rational(metric.get("observed_success_rate"), "observed rate")
    baseline = _rational(
        metric.get("exact_random_baseline_probability"),
        "random baseline",
    )
    difference = _rational(
        metric.get("random_baseline_rate_difference"),
        "random baseline difference",
    )
    coverage = _rational(metric.get("coverage"), "coverage")
    prize_counts = _mapping(
        prize.get("official_prize_tier_counts"),
        "official prize tier counts",
    )
    rank_value = ranking.get("rank")
    rank = rank_value if type(rank_value) is int else None
    unranked_reason_value = ranking.get("unranked_reason")
    unranked_reason = (
        unranked_reason_value
        if isinstance(unranked_reason_value, str) and unranked_reason_value
        else None
    )
    if (rank is None) is (unranked_reason is None):
        raise B649ProjectionBuildError(
            "ranking must contain exactly one of rank or unranked_reason"
        )
    return {
        "coverage": coverage["decimal_18"],
        "effective_backtest_draw_count": observed_rate["denominator"],
        "historical_success_rate": observed_rate["decimal_18"],
        "no_prize_count": _integer(prize.get("no_prize_count"), "no_prize_count"),
        "official_prize_counts": {
            "first": _integer(prize_counts.get("FIRST"), "FIRST"),
            "second": _integer(prize_counts.get("SECOND"), "SECOND"),
            "third": _integer(prize_counts.get("THIRD"), "THIRD"),
            "fourth": _integer(prize_counts.get("FOURTH"), "FOURTH"),
            "fifth": _integer(prize_counts.get("FIFTH"), "FIFTH"),
            "sixth": _integer(prize_counts.get("SIXTH"), "SIXTH"),
            "seventh": _integer(prize_counts.get("SEVENTH"), "SEVENTH"),
            "general": _integer(prize_counts.get("GENERAL"), "GENERAL"),
        },
        "random_baseline_rate_difference": difference["decimal_18"],
        "random_baseline_success_rate": baseline["decimal_18"],
        "rank": rank,
        "success_count": _integer(
            metric.get("observed_success_count"),
            "observed_success_count",
        ),
        "successful_execution_count": _integer(
            metric.get("successful_execution_count"),
            "successful_execution_count",
        ),
        "unranked_reason": unranked_reason,
        "window_available_draws": _integer(
            metric.get("window_available_draws"),
            "window_available_draws",
        ),
        "window_complete": _boolean(metric.get("window_complete"), "window_complete"),
        "window_requested_draws": _integer(
            metric.get("window_requested_draws"),
            "window_requested_draws",
        ),
    }


def _projection_record(
    catalog_record: FullStrategyCatalogRecord,
    combinations_by_strategy: dict[str, dict[str, object]],
    provenance_by_strategy: dict[str, tuple[str, str]],
) -> dict[str, object]:
    provenance = provenance_by_strategy.get(catalog_record.strategy_id)
    if catalog_record.reproduction_status is ReproductionStatus.BACKTESTED:
        if provenance is None:
            raise B649ProjectionBuildError(
                f"{catalog_record.strategy_id} has no pinned report provenance"
            )
        report_file_sha256, report_sha256 = provenance
        combinations = combinations_by_strategy[catalog_record.strategy_id]
    else:
        report_file_sha256 = None
        report_sha256 = None
        combinations = {}
    return {
        "combinations": combinations,
        "duplicate_alias_target": catalog_record.duplicate_alias_target,
        "legacy_method_id": catalog_record.legacy_method_id,
        "method_family": catalog_record.method_family,
        "report_file_sha256": report_file_sha256,
        "report_sha256": report_sha256,
        "reproduction_status": catalog_record.reproduction_status.value,
        "source_path": catalog_record.source_path,
        "strategy_id": catalog_record.strategy_id,
        "strategy_version": catalog_record.strategy_version,
        "unranked_reason": catalog_record.unranked_reason,
    }


def _report_document(raw: bytes, path: Path) -> dict[str, object]:
    try:
        parsed = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise B649ProjectionBuildError(f"{path} is invalid JSON") from exc
    return _mapping(parsed, f"report {path}")


def _verify_report_self_hash(report: dict[str, object], path: Path) -> None:
    report_sha256 = report.get("report_sha256")
    canonical = _canonical_json(
        {key: value for key, value in report.items() if key != "report_sha256"}
    )
    if report_sha256 != hashlib.sha256(canonical).hexdigest():
        raise B649ProjectionBuildError(
            f"{path} does not satisfy the report self-hash contract"
        )


def _read_regular_file(path: Path) -> bytes:
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise B649ProjectionBuildError(f"cannot inspect report path {path}") from exc
    if not stat.S_ISREG(metadata.st_mode):
        raise B649ProjectionBuildError(
            f"report path must be a regular non-symlink file: {path}"
        )
    try:
        return path.read_bytes()
    except OSError as exc:
        raise B649ProjectionBuildError(f"cannot read report path {path}") from exc


def _metric_key(row: dict[str, object]) -> tuple[str, int, str, str]:
    return (
        _string(row.get("strategy_id"), "strategy_id"),
        _integer(row.get("prefix_count"), "prefix_count"),
        _string(row.get("window"), "window"),
        _string(row.get("criterion"), "criterion"),
    )


def _prize_key(row: dict[str, object]) -> tuple[str, int, str]:
    return (
        _string(row.get("strategy_id"), "strategy_id"),
        _integer(row.get("prefix_count"), "prefix_count"),
        _string(row.get("window"), "window"),
    )


def _rational(value: object, label: str) -> dict[str, object]:
    rational = _mapping(value, label)
    if set(rational) != {"decimal_18", "denominator", "numerator"}:
        raise B649ProjectionBuildError(f"{label} has an invalid rational shape")
    _string(rational["decimal_18"], f"{label} decimal_18")
    _integer(rational["denominator"], f"{label} denominator")
    numerator = rational["numerator"]
    if type(numerator) is not int:
        raise B649ProjectionBuildError(f"{label} numerator must be an integer")
    return rational


def _list_of_mappings(value: object, label: str) -> list[dict[str, object]]:
    if not isinstance(value, list):
        raise B649ProjectionBuildError(f"{label} must be a list")
    return [
        _mapping(item, f"{label}[{index}]")
        for index, item in enumerate(cast(list[object], value))
    ]


def _mapping(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(
        isinstance(key, str) for key in cast(dict[object, object], value)
    ):
        raise B649ProjectionBuildError(f"{label} must be an object")
    return cast(dict[str, object], value)


def _sha256(value: str, label: str) -> str:
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise B649ProjectionBuildError(f"{label} must be a lowercase SHA-256")
    return value


def _string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise B649ProjectionBuildError(f"{label} must be a non-empty string")
    return value


def _integer(value: object, label: str) -> int:
    if type(value) is not int or value < 0:
        raise B649ProjectionBuildError(f"{label} must be a non-negative integer")
    return value


def _boolean(value: object, label: str) -> bool:
    if type(value) is not bool:
        raise B649ProjectionBuildError(f"{label} must be a boolean")
    return value


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


__all__ = [
    "B649ProjectionBuildError",
    "ExpectedReport",
    "build_b649_projection_bytes",
    "expected_report_manifest",
]
