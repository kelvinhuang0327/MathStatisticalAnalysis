"""Export a lossless JSONL index of the sealed B649 strategy history."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from importlib.resources import files
from pathlib import Path
from typing import Sequence

from lottolab.application.biglotto_multi_ticket_records import (
    B649_HISTORY_WINDOWS,
    B649MultiTicketRecord,
    B649_PREFIX_COUNTS,
    B649_SUCCESS_CRITERIA,
)
from lottolab.domain.biglotto_full_strategy_catalog import (
    CATALOG_RESOURCE_NAME,
    ReproductionStatus,
    load_full_strategy_catalog,
)
from lottolab.infrastructure.biglotto_multi_ticket_record_reader import (
    PROJECTION_RESOURCE_NAME,
    PackagedB649MultiTicketRecordReader,
)

EXPECTED_SOURCE_HEAD = "e382ae5f361ea29214cf7780fc31c09bfec1981e"
EXPECTED_SOURCE_TREE = "b2419f540c62a576a6f9591397e1e2432a0b00f7"
EXPECTED_STATUS_COUNTS = {
    "BACKTESTED": 135,
    "CLOSED_UNEXECUTABLE": 74,
    "DUPLICATE_ALIAS": 12,
}
EXPECTED_METRICS_AVAILABLE_COUNT = 133
EXPECTED_METRICS_UNAVAILABLE_COUNT = 2

ABOVE_RANDOM_DESCRIPTIVE = "ABOVE_RANDOM_DESCRIPTIVE"
AT_RANDOM_DESCRIPTIVE = "AT_RANDOM_DESCRIPTIVE"
BELOW_RANDOM_DESCRIPTIVE = "BELOW_RANDOM_DESCRIPTIVE"
METRIC_UNAVAILABLE = "METRIC_UNAVAILABLE"
NOT_COMPARABLE = "NOT_COMPARABLE"

CATALOG_RELATIVE_PATH = Path("src/lottolab/strategies/data") / CATALOG_RESOURCE_NAME
PROJECTION_RELATIVE_PATH = Path("src/lottolab/strategies/data") / PROJECTION_RESOURCE_NAME


@dataclass(frozen=True, slots=True)
class B649Index:
    strategy_status_records: tuple[dict[str, object], ...]
    backtest_metrics_records: tuple[dict[str, object], ...]
    summary: dict[str, object]


def _git_value(repo_root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo_root), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _decimal(value: str) -> Decimal | None:
    try:
        parsed = Decimal(value)
    except (InvalidOperation, TypeError, ValueError):
        return None
    return parsed if parsed.is_finite() else None


def classify_comparison(
    metrics_availability: str,
    *,
    numerator: int | None,
    denominator: int | None,
    observed_rate: str | None,
    random_baseline_rate: str | None,
    source_delta: str | None,
    require_numerator_le_denominator: bool = False,
) -> str:
    """Classify source values without rebuilding a historical rate.

    Some criteria count more than one successful event per effective draw, so
    their source count need not be bounded by ``effective_backtest_draw_count``.
    Official any-prize uses successful executions as its denominator and opts
    into the numerator bound explicitly.
    """

    if metrics_availability == "UNAVAILABLE":
        return METRIC_UNAVAILABLE
    if metrics_availability != "AVAILABLE":
        return NOT_COMPARABLE
    if (
        type(numerator) is not int
        or type(denominator) is not int
        or numerator < 0
        or denominator <= 0
        or (require_numerator_le_denominator and numerator > denominator)
        or observed_rate is None
        or random_baseline_rate is None
        or source_delta is None
    ):
        return NOT_COMPARABLE

    observed = _decimal(observed_rate)
    baseline = _decimal(random_baseline_rate)
    delta = _decimal(source_delta)
    if (
        observed is None
        or baseline is None
        or delta is None
        or not (Decimal(0) <= observed <= Decimal(1))
        or not (Decimal(0) <= baseline <= Decimal(1))
    ):
        return NOT_COMPARABLE
    if delta > 0:
        return ABOVE_RANDOM_DESCRIPTIVE
    if delta < 0:
        return BELOW_RANDOM_DESCRIPTIVE
    return AT_RANDOM_DESCRIPTIVE


def _source_identity(repo_root: Path) -> tuple[str, str]:
    head = _git_value(repo_root, "rev-parse", "HEAD")
    tree = _git_value(repo_root, "rev-parse", "HEAD^{tree}")
    if head != EXPECTED_SOURCE_HEAD or tree != EXPECTED_SOURCE_TREE:
        raise ValueError(
            "source checkout identity does not match the pinned HEAD/TREE: "
            f"{head}/{tree}"
        )
    return head, tree


def _source_bytes(repo_root: Path, relative_path: Path, resource_name: str) -> bytes:
    path_raw = (repo_root / relative_path).read_bytes()
    packaged_raw = files("lottolab.strategies.data").joinpath(resource_name).read_bytes()
    if path_raw != packaged_raw:
        raise ValueError(f"packaged resource differs from pinned source file: {relative_path}")
    return path_raw


def _row_metrics_available_fields(record: B649MultiTicketRecord) -> tuple[object, ...]:
    return (
        record.official_any_prize_count,
        record.official_any_prize_rate,
        record.official_random_baseline_probability,
        record.official_random_baseline_delta,
        record.success_count,
        record.effective_backtest_draw_count,
        record.successful_execution_count,
        record.historical_success_rate,
        record.random_baseline_success_rate,
        record.random_baseline_rate_difference,
    )


def build_b649_index(repo_root: Path) -> B649Index:
    """Read the pinned catalog and projection and build both lossless indexes."""

    repo_root = repo_root.resolve()
    source_head, source_tree = _source_identity(repo_root)
    catalog_raw = _source_bytes(repo_root, CATALOG_RELATIVE_PATH, CATALOG_RESOURCE_NAME)
    projection_raw = _source_bytes(
        repo_root,
        PROJECTION_RELATIVE_PATH,
        PROJECTION_RESOURCE_NAME,
    )
    catalog_file_sha256 = _sha256(catalog_raw)
    projection_file_sha256 = _sha256(projection_raw)

    catalog = load_full_strategy_catalog()
    dataset = PackagedB649MultiTicketRecordReader().read()
    if dataset.catalog_sha256 != catalog.catalog_sha256:
        raise ValueError("catalog and projection identities do not match")

    catalog_by_id = {record.strategy_id: record for record in catalog.records}
    if len(catalog_by_id) != 221:
        raise ValueError("catalog does not contain 221 unique strategy IDs")

    status_counts = Counter(record.reproduction_status.value for record in catalog.records)
    if dict(status_counts) != EXPECTED_STATUS_COUNTS:
        raise ValueError(f"catalog status counts changed: {dict(status_counts)}")
    if (
        dataset.metrics_available_strategy_count != EXPECTED_METRICS_AVAILABLE_COUNT
        or dataset.metrics_unavailable_strategy_count != EXPECTED_METRICS_UNAVAILABLE_COUNT
    ):
        raise ValueError("projection metrics availability counts changed")

    expected_combinations = {
        (prefix_count, window.value, criterion.value)
        for prefix_count in B649_PREFIX_COUNTS
        for window in B649_HISTORY_WINDOWS
        for criterion in B649_SUCCESS_CRITERIA
    }
    records_by_strategy: dict[str, list[B649MultiTicketRecord]] = defaultdict(list)
    seen_combinations: set[tuple[str, int, str, str]] = set()
    for row in dataset.records:
        strategy = catalog_by_id.get(row.strategy_id)
        if strategy is None:
            raise ValueError(f"projection contains an unknown strategy: {row.strategy_id}")
        if (
            row.strategy_version != strategy.strategy_version
            or row.legacy_method_id != strategy.legacy_method_id
            or row.source_path != strategy.source_path
            or row.reproduction_status is not strategy.reproduction_status
            or row.duplicate_alias_target != strategy.duplicate_alias_target
        ):
            raise ValueError(f"projection identity conflicts with catalog: {row.strategy_id}")
        combination = (row.prefix_count, row.window.value, row.criterion.value)
        if combination not in expected_combinations:
            raise ValueError(f"projection contains an unsupported metric dimension: {combination}")
        identity = (row.strategy_id, *combination)
        if identity in seen_combinations:
            raise ValueError(f"projection repeats a metric dimension: {identity}")
        seen_combinations.add(identity)
        records_by_strategy[row.strategy_id].append(row)

    strategy_status_records: list[dict[str, object]] = []
    availability_by_strategy: dict[str, str] = {}
    expected_combinations_per_strategy = len(expected_combinations)

    for strategy in catalog.records:
        strategy_rows = records_by_strategy.get(strategy.strategy_id, [])
        if len(strategy_rows) != expected_combinations_per_strategy:
            raise ValueError(
                f"strategy {strategy.strategy_id} has {len(strategy_rows)} of "
                f"{expected_combinations_per_strategy} dimensions"
            )
        reasons = {row.metrics_unavailable_reason for row in strategy_rows}
        if strategy.reproduction_status is ReproductionStatus.BACKTESTED:
            if reasons == {None}:
                availability = "AVAILABLE"
                unavailable_reason = None
            elif len(reasons) == 1 and None not in reasons:
                availability = "UNAVAILABLE"
                unavailable_reason = next(iter(reasons))
            else:
                raise ValueError(
                    f"strategy {strategy.strategy_id} has inconsistent metric availability"
                )
        else:
            if reasons != {None} or any(
                any(value is not None for value in _row_metrics_available_fields(row))
                for row in strategy_rows
            ):
                raise ValueError(
                    f"non-backtested strategy {strategy.strategy_id} contains metric values"
                )
            availability = "NOT_APPLICABLE"
            unavailable_reason = None

        availability_by_strategy[strategy.strategy_id] = availability
        status_row = strategy.canonical_dict()
        status_row["duplicate_alias_target"] = strategy.duplicate_alias_target
        status_row["metrics_availability"] = availability
        status_row["metrics_unavailable_reason"] = unavailable_reason
        status_row["catalog_sha256"] = catalog.catalog_sha256
        status_row["catalog_file_sha256"] = catalog_file_sha256
        status_row["source_repo_head"] = source_head
        status_row["source_repo_tree"] = source_tree
        strategy_status_records.append(status_row)

    metrics_records: list[dict[str, object]] = []
    for row in dataset.records:
        strategy = catalog_by_id[row.strategy_id]
        availability = availability_by_strategy[row.strategy_id]
        metric_row = asdict(row)
        metric_row["window"] = row.window.value
        metric_row["criterion"] = row.criterion.value
        metric_row["reproduction_status"] = row.reproduction_status.value
        metric_row["projection_rank"] = metric_row.pop("rank")
        metric_row["historical_success_rate_source_value"] = row.historical_success_rate
        metric_row["random_baseline_rate_difference_source_value"] = (
            row.random_baseline_rate_difference
        )
        metric_row["official_any_prize_rate_source_value"] = row.official_any_prize_rate
        metric_row["official_random_baseline_delta_source_value"] = (
            row.official_random_baseline_delta
        )
        if row.effective_backtest_draw_count == 0:
            metric_row["historical_success_rate"] = None
            metric_row["random_baseline_rate_difference"] = None
            metric_row["historical_success_rate_availability_reason"] = (
                "ZERO_EFFECTIVE_BACKTEST_DRAW_COUNT"
            )
        if row.successful_execution_count == 0:
            metric_row["official_any_prize_rate"] = None
            metric_row["official_random_baseline_delta"] = None
            metric_row["official_any_prize_rate_availability_reason"] = (
                "ZERO_SUCCESSFUL_EXECUTION_COUNT"
            )
        metric_row["source_commit"] = strategy.source_commit
        metric_row["source_sha256"] = strategy.source_sha256
        metric_row["source_blob_id"] = strategy.source_blob_id
        metric_row["status_reason"] = strategy.status_reason
        metric_row["why_not_runnable"] = strategy.why_not_runnable
        metric_row["metrics_availability"] = availability
        metric_row["catalog_file_sha256"] = catalog_file_sha256
        metric_row["projection_file_sha256"] = projection_file_sha256
        metric_row["projection_sha256"] = dataset.projection_sha256
        metric_row["source_repo_head"] = source_head
        metric_row["source_repo_tree"] = source_tree
        metric_row["descriptive_comparison_classification"] = classify_comparison(
            availability,
            numerator=row.success_count,
            denominator=row.effective_backtest_draw_count,
            observed_rate=row.historical_success_rate,
            random_baseline_rate=row.random_baseline_success_rate,
            source_delta=row.random_baseline_rate_difference,
        )
        metric_row["official_any_prize_descriptive_classification"] = classify_comparison(
            availability,
            numerator=row.official_any_prize_count,
            denominator=row.successful_execution_count,
            observed_rate=row.official_any_prize_rate,
            random_baseline_rate=row.official_random_baseline_probability,
            source_delta=row.official_random_baseline_delta,
            require_numerator_le_denominator=True,
        )
        metrics_records.append(metric_row)

    criterion_classifications = Counter(
        str(row["descriptive_comparison_classification"]) for row in metrics_records
    )
    official_classifications = Counter(
        str(row["official_any_prize_descriptive_classification"])
        for row in metrics_records
    )
    summary: dict[str, object] = {
        "source_head": source_head,
        "source_tree": source_tree,
        "catalog_sha256": catalog.catalog_sha256,
        "catalog_file_sha256": catalog_file_sha256,
        "projection_sha256": dataset.projection_sha256,
        "projection_file_sha256": projection_file_sha256,
        "source_report_count": dataset.source_report_count,
        "strategy_count": len(strategy_status_records),
        "status_counts": dict(status_counts),
        "metrics_available_strategy_count": dataset.metrics_available_strategy_count,
        "metrics_unavailable_strategy_count": dataset.metrics_unavailable_strategy_count,
        "metrics_not_applicable_strategy_count": sum(
            value == "NOT_APPLICABLE" for value in availability_by_strategy.values()
        ),
        "strategy_status_record_count": len(strategy_status_records),
        "backtest_metrics_record_count": len(metrics_records),
        "prefix_counts": list(B649_PREFIX_COUNTS),
        "windows": [window.value for window in B649_HISTORY_WINDOWS],
        "criteria": [criterion.value for criterion in B649_SUCCESS_CRITERIA],
        "criterion_comparison_counts": dict(criterion_classifications),
        "official_any_prize_comparison_counts": dict(official_classifications),
        "positive_delta_record_count": criterion_classifications[ABOVE_RANDOM_DESCRIPTIVE],
        "negative_delta_record_count": criterion_classifications[BELOW_RANDOM_DESCRIPTIVE],
        "zero_delta_record_count": criterion_classifications[AT_RANDOM_DESCRIPTIVE],
        "not_comparable_record_count": criterion_classifications[NOT_COMPARABLE],
        "metric_unavailable_record_count": criterion_classifications[METRIC_UNAVAILABLE],
        "official_any_prize_positive_delta_record_count": official_classifications[
            ABOVE_RANDOM_DESCRIPTIVE
        ],
        "official_any_prize_negative_delta_record_count": official_classifications[
            BELOW_RANDOM_DESCRIPTIVE
        ],
        "official_any_prize_zero_delta_record_count": official_classifications[
            AT_RANDOM_DESCRIPTIVE
        ],
        "official_any_prize_not_comparable_record_count": official_classifications[
            NOT_COMPARABLE
        ],
        "official_any_prize_metric_unavailable_record_count": official_classifications[
            METRIC_UNAVAILABLE
        ],
        "ranking_recomputed": False,
        "historical_backtests_recomputed": False,
        "predictive_lift": "NOT ESTABLISHED",
    }
    return B649Index(
        strategy_status_records=tuple(strategy_status_records),
        backtest_metrics_records=tuple(metrics_records),
        summary=summary,
    )


def _write_jsonl(
    path: Path,
    records: Sequence[dict[str, object]],
    *,
    overwrite: bool,
) -> str:
    digest = hashlib.sha256()
    mode = "wb" if overwrite else "xb"
    with path.open(mode) as stream:
        for record in records:
            line = (
                json.dumps(
                    record,
                    ensure_ascii=False,
                    allow_nan=False,
                    separators=(",", ":"),
                    sort_keys=True,
                )
                + "\n"
            ).encode("utf-8")
            stream.write(line)
            digest.update(line)
    return digest.hexdigest()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--overwrite-existing", action="store_true")
    args = parser.parse_args(argv)

    index = build_b649_index(args.repo_root)
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    status_path = output_dir / "strategy_status.jsonl"
    metrics_path = output_dir / "backtest_metrics.jsonl"
    if (status_path.exists() or metrics_path.exists()) and not args.overwrite_existing:
        raise FileExistsError("refusing to overwrite an existing B649 index")
    status_sha256 = _write_jsonl(
        status_path,
        index.strategy_status_records,
        overwrite=args.overwrite_existing,
    )
    metrics_sha256 = _write_jsonl(
        metrics_path,
        index.backtest_metrics_records,
        overwrite=args.overwrite_existing,
    )

    result = dict(index.summary)
    result["status_index"] = {
        "path": str(status_path),
        "record_count": len(index.strategy_status_records),
        "sha256": status_sha256,
    }
    result["metrics_index"] = {
        "path": str(metrics_path),
        "record_count": len(index.backtest_metrics_records),
        "sha256": metrics_sha256,
    }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
