"""Offline builder for the pinned B649 aggregate-history projection.

Every report path is explicit.  This module never discovers a newest report,
executes a strategy, opens a database, or regenerates a ticket.
"""

from __future__ import annotations

import hashlib
import json
import stat
from dataclasses import dataclass
from fractions import Fraction
from importlib.resources import files
from pathlib import Path
from typing import cast

from lottolab.application.biglotto_multi_ticket_records import (
    B649_AUTHORITY_MODE_FRESH_REPRODUCTION,
    B649_AUTHORITY_MODE_HISTORICAL_SEALED,
    B649_HISTORY_WINDOWS,
    B649_METRICS_UNAVAILABLE_REASON,
    B649_METRICS_UNAVAILABLE_STRATEGY_IDS,
    B649_PREFIX_COUNTS,
    B649_SUCCESS_CRITERIA,
)
from lottolab.domain.biglotto_full_strategy_catalog import (
    FullStrategyCatalog,
    FullStrategyCatalogRecord,
    ReproductionStatus,
    load_full_strategy_catalog,
)
from lottolab.infrastructure.b649_dataset_authority import (
    APPROVED_FRESH_LOGICAL_DATASET_SHA256,
    LEGACY_PINNED_DATASET_SHA256,
    B649DatasetAuthorityError,
    validate_b649_dataset_sha256,
)
from lottolab.infrastructure.biglotto_multi_ticket_record_reader import (
    PROJECTION_SCHEMA_VERSION,
)


class B649ProjectionBuildError(RuntimeError):
    """Explicit pinned inputs cannot produce a complete aggregate projection."""


METRICS_UNAVAILABLE_STRATEGY_IDS = B649_METRICS_UNAVAILABLE_STRATEGY_IDS
METRICS_UNAVAILABLE_REASON = B649_METRICS_UNAVAILABLE_REASON
AUTHORITY_MODE_HISTORICAL_SEALED = B649_AUTHORITY_MODE_HISTORICAL_SEALED
AUTHORITY_MODE_FRESH_REPRODUCTION = B649_AUTHORITY_MODE_FRESH_REPRODUCTION


@dataclass(frozen=True, slots=True)
class ExpectedReport:
    report_file_sha256: str
    report_sha256: str
    strategy_ids: tuple[str, ...]


def build_b649_projection_bytes(
    report_paths: tuple[Path, ...] = (),
    *,
    fresh_report_paths: tuple[Path, ...] = (),
    fresh_authority: str | None = None,
    official_recomputed_report_paths: tuple[Path, ...] = (),
) -> bytes:
    """Build when explicit reports cover all BACKTESTED strategies except the
    fixed, Owner-approved METRICS_UNAVAILABLE_STRATEGY_IDS exception set.

    ``report_paths`` are checksum-pinned historical evidence (validated
    against ``expected_report_manifest``). ``fresh_report_paths`` are
    self-consistent reports freshly computed against the current catalog only
    when ``fresh_authority`` explicitly equals
    ``FRESH_CURRENT_CATALOG_REPRODUCTION_V1``. They are not required to match
    a historical pinned checksum, but must use the one approved fresh logical
    dataset identity, be evaluated against the exact current catalog, and pass
    the same report self-hash contract. ``official_recomputed_report_paths``
    is an explicit task-scoped route for reports recomputed from ordered
    portfolios. It accepts either authorized dataset identity, preserves the
    corresponding historical/fresh authority per strategy, and bypasses only
    the old physical report checksum manifest. A strategy may be supplied by
    exactly one source.
    """

    if official_recomputed_report_paths and (
        report_paths or fresh_report_paths or fresh_authority is not None
    ):
        raise B649ProjectionBuildError(
            "official recomputed reports cannot be combined with sealed or fresh "
            "report inputs"
        )
    if fresh_report_paths and fresh_authority != AUTHORITY_MODE_FRESH_REPRODUCTION:
        raise B649ProjectionBuildError(
            "fresh reports require explicit FRESH_CURRENT_CATALOG_REPRODUCTION_V1 authority"
        )
    if not fresh_report_paths and fresh_authority is not None:
        raise B649ProjectionBuildError(
            "fresh authority cannot be supplied without fresh reports"
        )

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

    fresh_supplied: dict[str, tuple[ExpectedReport, dict[str, object]]] = {}
    for path in fresh_report_paths:
        raw = _read_regular_file(path)
        file_sha256 = hashlib.sha256(raw).hexdigest()
        if file_sha256 in supplied or file_sha256 in fresh_supplied:
            raise B649ProjectionBuildError(
                f"report {file_sha256} was supplied more than once"
            )
        document = _report_document(raw, path)
        _verify_report_self_hash(document, path)
        if document.get("catalog_sha256") != catalog.catalog_sha256:
            raise B649ProjectionBuildError(
                f"{path} was not evaluated against the current catalog"
            )
        try:
            validate_b649_dataset_sha256(
                document.get("dataset_sha256"),
                authority_mode=fresh_authority,
            )
        except B649DatasetAuthorityError as exc:
            raise B649ProjectionBuildError(f"{path}: {exc}") from exc
        report_sha256 = document.get("report_sha256")
        if not isinstance(report_sha256, str):
            raise B649ProjectionBuildError(f"{path} has no report_sha256")
        strategy_ids = tuple(
            sorted(
                {
                    _string(row.get("strategy_id"), "metric strategy_id")
                    for row in _list_of_mappings(
                        document.get("metrics"), "report metrics"
                    )
                }
            )
        )
        expected = ExpectedReport(
            report_file_sha256=file_sha256,
            report_sha256=_sha256(report_sha256, f"{path} report_sha256"),
            strategy_ids=strategy_ids,
        )
        fresh_supplied[file_sha256] = (expected, document)

    official_recomputed_supplied: dict[
        str, tuple[ExpectedReport, dict[str, object], str]
    ] = {}
    for path in official_recomputed_report_paths:
        raw = _read_regular_file(path)
        file_sha256 = hashlib.sha256(raw).hexdigest()
        if file_sha256 in official_recomputed_supplied:
            raise B649ProjectionBuildError(
                "official recomputed report "
                f"{file_sha256} was supplied more than once"
            )
        document = _report_document(raw, path)
        _verify_report_self_hash(document, path)
        if document.get("catalog_sha256") != catalog.catalog_sha256:
            raise B649ProjectionBuildError(
                f"{path} was not evaluated against the current catalog"
            )
        dataset_sha256 = document.get("dataset_sha256")
        if dataset_sha256 == LEGACY_PINNED_DATASET_SHA256:
            authority_mode = AUTHORITY_MODE_HISTORICAL_SEALED
        elif dataset_sha256 == APPROVED_FRESH_LOGICAL_DATASET_SHA256:
            authority_mode = AUTHORITY_MODE_FRESH_REPRODUCTION
        else:
            raise B649ProjectionBuildError(
                f"{path} does not carry an authorized B649 dataset identity"
            )
        try:
            validate_b649_dataset_sha256(
                dataset_sha256,
                authority_mode=authority_mode,
            )
        except B649DatasetAuthorityError as exc:
            raise B649ProjectionBuildError(f"{path}: {exc}") from exc
        report_sha256 = document.get("report_sha256")
        if not isinstance(report_sha256, str):
            raise B649ProjectionBuildError(f"{path} has no report_sha256")
        strategy_ids = tuple(
            sorted(
                {
                    _string(row.get("strategy_id"), "metric strategy_id")
                    for row in _list_of_mappings(
                        document.get("metrics"), "report metrics"
                    )
                }
            )
        )
        expected = ExpectedReport(
            report_file_sha256=file_sha256,
            report_sha256=_sha256(report_sha256, f"{path} report_sha256"),
            strategy_ids=strategy_ids,
        )
        official_recomputed_supplied[file_sha256] = (
            expected,
            document,
            authority_mode,
        )

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
    fresh_strategy_ids = {
        strategy_id
        for expected, _document in fresh_supplied.values()
        for strategy_id in expected.strategy_ids
    }
    official_recomputed_strategy_ids = {
        strategy_id
        for expected, _document, _authority_mode in official_recomputed_supplied.values()
        for strategy_id in expected.strategy_ids
    }
    if supplied_strategy_ids & fresh_strategy_ids:
        raise B649ProjectionBuildError(
            "a strategy was supplied by both historical and fresh reports"
        )
    if (supplied_strategy_ids | fresh_strategy_ids) & official_recomputed_strategy_ids:
        raise B649ProjectionBuildError(
            "a strategy was supplied by both ordinary and official recomputed reports"
        )
    combined_supplied_strategy_ids = (
        supplied_strategy_ids | fresh_strategy_ids | official_recomputed_strategy_ids
    )
    if combined_supplied_strategy_ids & METRICS_UNAVAILABLE_STRATEGY_IDS:
        raise B649ProjectionBuildError(
            "metrics-unavailable strategies must not be supplied via report_paths"
        )
    missing = sorted(
        required_strategy_ids
        - combined_supplied_strategy_ids
        - METRICS_UNAVAILABLE_STRATEGY_IDS
    )
    unexpected = sorted(combined_supplied_strategy_ids - required_strategy_ids)
    if missing or unexpected:
        raise B649ProjectionBuildError(
            "explicit reports do not cover exactly all metrics-eligible "
            f"BACKTESTED strategies; missing={len(missing)} unexpected={len(unexpected)}"
        )

    combinations_by_strategy: dict[str, dict[str, object]] = {}
    provenance_by_strategy: dict[str, tuple[str, str]] = {}
    authority_mode_by_strategy: dict[str, str] = {}
    source_reports: list[dict[str, object]] = []
    for file_sha256 in sorted(supplied):
        expected, document = supplied[file_sha256]
        _collect_report(
            document,
            expected,
            combinations_by_strategy,
            provenance_by_strategy,
        )
        for strategy_id in expected.strategy_ids:
            authority_mode_by_strategy[strategy_id] = AUTHORITY_MODE_HISTORICAL_SEALED
        source_reports.append(
            {
                "authority_mode": AUTHORITY_MODE_HISTORICAL_SEALED,
                "report_file_sha256": expected.report_file_sha256,
                "report_sha256": expected.report_sha256,
                "strategy_ids": list(expected.strategy_ids),
            }
        )
    for file_sha256 in sorted(fresh_supplied):
        expected, document = fresh_supplied[file_sha256]
        _collect_report(
            document,
            expected,
            combinations_by_strategy,
            provenance_by_strategy,
        )
        for strategy_id in expected.strategy_ids:
            authority_mode_by_strategy[strategy_id] = AUTHORITY_MODE_FRESH_REPRODUCTION
        source_reports.append(
            {
                "authority_mode": AUTHORITY_MODE_FRESH_REPRODUCTION,
                "dataset_sha256": cast(str, document["dataset_sha256"]),
                "report_file_sha256": expected.report_file_sha256,
                "report_sha256": expected.report_sha256,
                "strategy_ids": list(expected.strategy_ids),
            }
        )
    for file_sha256 in sorted(official_recomputed_supplied):
        expected, document, authority_mode = official_recomputed_supplied[file_sha256]
        _collect_report(
            document,
            expected,
            combinations_by_strategy,
            provenance_by_strategy,
        )
        for strategy_id in expected.strategy_ids:
            authority_mode_by_strategy[strategy_id] = authority_mode
        source_report: dict[str, object] = {
            "authority_mode": authority_mode,
            "report_file_sha256": expected.report_file_sha256,
            "report_sha256": expected.report_sha256,
            "strategy_ids": list(expected.strategy_ids),
        }
        if authority_mode == AUTHORITY_MODE_FRESH_REPRODUCTION:
            source_report["dataset_sha256"] = document["dataset_sha256"]
        source_reports.append(source_report)

    _assign_official_ranks(combinations_by_strategy)

    metrics_unavailable_provenance: dict[str, tuple[str, str]] = {
        strategy_id: (report.report_file_sha256, report.report_sha256)
        for report in manifest
        for strategy_id in report.strategy_ids
        if strategy_id in METRICS_UNAVAILABLE_STRATEGY_IDS
    }

    records = [
        _projection_record(
            catalog_record,
            combinations_by_strategy,
            provenance_by_strategy,
            metrics_unavailable_provenance,
            authority_mode_by_strategy,
        )
        for catalog_record in catalog.records
    ]
    document: dict[str, object] = {
        "catalog_sha256": catalog.catalog_sha256,
        "metrics_available_strategy_count": len(required_strategy_ids)
        - len(METRICS_UNAVAILABLE_STRATEGY_IDS & required_strategy_ids),
        "metrics_unavailable_strategy_count": len(
            METRICS_UNAVAILABLE_STRATEGY_IDS & required_strategy_ids
        ),
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


def _decimal_fraction(value: object, label: str) -> Fraction:
    if not isinstance(value, str):
        raise B649ProjectionBuildError(f"{label} must be a decimal string")
    try:
        return Fraction(value)
    except (TypeError, ValueError, ZeroDivisionError) as exc:
        raise B649ProjectionBuildError(f"{label} is not an exact decimal") from exc


def _assign_official_ranks(
    combinations_by_strategy: dict[str, dict[str, object]],
) -> None:
    """Re-rank the complete metric-bearing universe after report collection."""

    ranking_criterion = B649_SUCCESS_CRITERIA[0].value
    for prefix_count in B649_PREFIX_COUNTS:
        for window in B649_HISTORY_WINDOWS:
            candidates: list[tuple[Fraction, Fraction, Fraction, str]] = []
            for strategy_id, combinations in combinations_by_strategy.items():
                combination = combinations.get(
                    f"{prefix_count}|{window.value}|{ranking_criterion}"
                )
                if not isinstance(combination, dict):
                    continue
                combination_row = cast(dict[str, object], combination)
                if type(combination_row.get("official_rank")) is not int:
                    continue
                candidates.append(
                    (
                        _decimal_fraction(
                            combination_row.get("official_any_prize_rate"),
                            "official_any_prize_rate",
                        ),
                        _decimal_fraction(
                            combination_row.get("official_random_baseline_delta"),
                            "official_random_baseline_delta",
                        ),
                        _decimal_fraction(
                            combination_row.get("coverage"),
                            "coverage",
                        ),
                        strategy_id,
                    )
                )
            candidates.sort(key=lambda item: (-item[0], -item[1], -item[2], item[3]))
            rank_by_strategy = {
                item[3]: rank for rank, item in enumerate(candidates, start=1)
            }
            prefix = f"{prefix_count}|{window.value}|"
            for strategy_id, combinations in combinations_by_strategy.items():
                rank = rank_by_strategy.get(strategy_id)
                for key, combination in combinations.items():
                    if not key.startswith(prefix) or not isinstance(combination, dict):
                        continue
                    combination_row = cast(dict[str, object], combination)
                    if type(combination_row.get("official_rank")) is int:
                        combination_row["official_rank"] = rank


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
    official_rate = _rational(
        metric.get("official_any_prize_rate"),
        "official any-prize rate",
    )
    official_baseline = _rational(
        metric.get("official_random_baseline_probability"),
        "official random baseline",
    )
    official_difference = _rational(
        metric.get("official_random_baseline_delta"),
        "official random baseline difference",
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
    official_rank_value = ranking.get("official_rank")
    official_rank = (
        official_rank_value if type(official_rank_value) is int else None
    )
    if (official_rank is None) is (unranked_reason is None):
        raise B649ProjectionBuildError(
            "ranking must contain exactly one of official_rank or unranked_reason"
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
        "official_any_prize_count": _integer(
            metric.get("official_any_prize_count"),
            "official_any_prize_count",
        ),
        "official_any_prize_rate": official_rate["decimal_18"],
        "official_random_baseline_probability": official_baseline[
            "decimal_18"
        ],
        "official_random_baseline_delta": official_difference["decimal_18"],
        "official_rank": official_rank,
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
    metrics_unavailable_provenance: dict[str, tuple[str, str]],
    authority_mode_by_strategy: dict[str, str],
) -> dict[str, object]:
    metrics_unavailable_reason: str | None = None
    authority_mode: str | None = None
    if catalog_record.strategy_id in METRICS_UNAVAILABLE_STRATEGY_IDS:
        if catalog_record.reproduction_status is not ReproductionStatus.BACKTESTED:
            raise B649ProjectionBuildError(
                f"{catalog_record.strategy_id} is a pinned metrics-unavailable "
                "exception but is no longer BACKTESTED in the catalog"
            )
        provenance = metrics_unavailable_provenance.get(catalog_record.strategy_id)
        if provenance is None:
            raise B649ProjectionBuildError(
                f"{catalog_record.strategy_id} has no pinned evidence provenance"
            )
        report_file_sha256, report_sha256 = provenance
        combinations = {}
        metrics_unavailable_reason = METRICS_UNAVAILABLE_REASON
    elif catalog_record.reproduction_status is ReproductionStatus.BACKTESTED:
        provenance = provenance_by_strategy.get(catalog_record.strategy_id)
        if provenance is None:
            raise B649ProjectionBuildError(
                f"{catalog_record.strategy_id} has no pinned report provenance"
            )
        report_file_sha256, report_sha256 = provenance
        combinations = combinations_by_strategy[catalog_record.strategy_id]
        authority_mode = authority_mode_by_strategy.get(catalog_record.strategy_id)
        if authority_mode is None:
            raise B649ProjectionBuildError(
                f"{catalog_record.strategy_id} has no recorded authority mode"
            )
    else:
        report_file_sha256 = None
        report_sha256 = None
        combinations = {}
    return {
        "authority_mode": authority_mode,
        "combinations": combinations,
        "duplicate_alias_target": catalog_record.duplicate_alias_target,
        "legacy_method_id": catalog_record.legacy_method_id,
        "method_family": catalog_record.method_family,
        "metrics_unavailable_reason": metrics_unavailable_reason,
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
    "AUTHORITY_MODE_FRESH_REPRODUCTION",
    "AUTHORITY_MODE_HISTORICAL_SEALED",
    "B649ProjectionBuildError",
    "ExpectedReport",
    "build_b649_projection_bytes",
    "expected_report_manifest",
]
