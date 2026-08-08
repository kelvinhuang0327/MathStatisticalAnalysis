"""CLI for complete-universe BIG_LOTTO multi-ticket backtest reports."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
from pathlib import Path
from typing import Annotated, Any, NoReturn, cast

import typer

from lottolab.application.biglotto_multi_ticket_backtest import (
    MultiTicketBacktestInputError,
    evaluate_biglotto_multi_ticket_backtest,
)

REPORT_JSON_FILENAME = "biglotto_multi_ticket_backtest_report.json"
UNIVERSE_CSV_FILENAME = "biglotto_strategy_universe.csv"
EXECUTION_AUDIT_CSV_FILENAME = "biglotto_execution_audit.csv"
METRICS_CSV_FILENAME = "biglotto_success_metrics.csv"
PRIZES_CSV_FILENAME = "biglotto_official_prize_distributions.csv"
RANKINGS_CSV_FILENAME = "biglotto_full_rankings.csv"
TOP10_CSV_FILENAME = "biglotto_top10.csv"
OFFICIAL_RANKINGS_CSV_FILENAME = "official_full_ranking.csv"
OFFICIAL_TOP20_CSV_FILENAME = "official_top20_by_ticket_window.csv"
OFFICIAL_PRIZE_DISTRIBUTION_CSV_FILENAME = "official_prize_distribution.csv"
OFFICIAL_STABILITY_CSV_FILENAME = "official_cross_period_stability.csv"
OFFICIAL_REVIEW_FILENAME = "official_ranking_review.md"
CHECKSUM_FILENAME = "SHA256SUMS"
_OUTPUT_FILENAMES = (
    REPORT_JSON_FILENAME,
    UNIVERSE_CSV_FILENAME,
    EXECUTION_AUDIT_CSV_FILENAME,
    METRICS_CSV_FILENAME,
    PRIZES_CSV_FILENAME,
    RANKINGS_CSV_FILENAME,
    TOP10_CSV_FILENAME,
    OFFICIAL_RANKINGS_CSV_FILENAME,
    OFFICIAL_TOP20_CSV_FILENAME,
    OFFICIAL_PRIZE_DISTRIBUTION_CSV_FILENAME,
    OFFICIAL_STABILITY_CSV_FILENAME,
    OFFICIAL_REVIEW_FILENAME,
    CHECKSUM_FILENAME,
)


class MultiTicketBacktestCliError(RuntimeError):
    """A caller-safe multi-ticket backtest CLI failure."""


def _canonical_json_bytes(payload: object) -> bytes:
    return (
        json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        + b"\n"
    )


def _csv_cell(value: object) -> object:
    if isinstance(value, dict | list):
        return json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    if type(value) is bool:
        return "true" if value else "false"
    return value


def _csv_bytes(rows: object, fieldnames: tuple[str, ...], context: str) -> bytes:
    if not isinstance(rows, list):
        raise MultiTicketBacktestCliError(f"report {context} is malformed")
    typed_rows = cast(list[object], rows)
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(
        buffer,
        fieldnames=fieldnames,
        lineterminator="\n",
        extrasaction="ignore",
    )
    writer.writeheader()
    for index, candidate in enumerate(typed_rows):
        if not isinstance(candidate, dict):
            raise MultiTicketBacktestCliError(
                f"report {context}[{index}] is malformed"
            )
        row = cast(dict[str, Any], candidate)
        writer.writerow(
            cast(
                Any,
                {field: _csv_cell(row.get(field, "")) for field in fieldnames},
            )
        )
    return buffer.getvalue().encode("utf-8")


_OFFICIAL_WINDOWS = ("FULL", "RECENT_750", "RECENT_300", "RECENT_50")
_OFFICIAL_PREFIX_COUNTS = (5, 10, 15, 20)


def _official_cross_period_stability_rows(
    report: dict[str, object],
) -> list[dict[str, object]]:
    """Build descriptive rank-stability rows without combining ticket counts."""

    universe = report.get("universe")
    rankings = report.get("official_rankings")
    if not isinstance(universe, list) or not isinstance(rankings, list):
        raise MultiTicketBacktestCliError(
            "report official ranking inputs are malformed"
        )
    ranking_candidates = cast(list[object], rankings)
    ranking_index: dict[tuple[str, int, str], dict[str, object]] = {}
    for index, candidate in enumerate(ranking_candidates):
        if not isinstance(candidate, dict):
            raise MultiTicketBacktestCliError(
                f"report official_rankings[{index}] is malformed"
            )
        row = cast(dict[str, object], candidate)
        strategy_id = row.get("strategy_id")
        prefix_count = row.get("prefix_count")
        window = row.get("window")
        if (
            not isinstance(strategy_id, str)
            or type(prefix_count) is not int
            or not isinstance(window, str)
        ):
            raise MultiTicketBacktestCliError(
                f"report official_rankings[{index}] has an invalid identity"
            )
        key = (strategy_id, prefix_count, window)
        if key in ranking_index:
            raise MultiTicketBacktestCliError(
                "report official_rankings contains duplicate identities"
            )
        ranking_index[key] = row

    rows: list[dict[str, object]] = []
    universe_candidates = cast(list[object], universe)
    for index, candidate in enumerate(universe_candidates):
        if not isinstance(candidate, dict):
            raise MultiTicketBacktestCliError(f"report universe[{index}] is malformed")
        universe_row = cast(dict[str, object], candidate)
        strategy_id = universe_row.get("strategy_id")
        if not isinstance(strategy_id, str):
            raise MultiTicketBacktestCliError(
                f"report universe[{index}] has no strategy_id"
            )
        for prefix_count in _OFFICIAL_PREFIX_COUNTS:
            by_window = {
                window: ranking_index.get((strategy_id, prefix_count, window), {})
                for window in _OFFICIAL_WINDOWS
            }
            rank_by_window = {
                window: row.get("official_rank")
                for window, row in by_window.items()
            }
            ranked = {
                window: value
                for window, value in rank_by_window.items()
                if type(value) is int
            }
            best_window = min(
                ranked,
                key=lambda window: (ranked[window], _OFFICIAL_WINDOWS.index(window)),
                default="",
            )
            worst_window = max(
                ranked,
                key=lambda window: (ranked[window], -_OFFICIAL_WINDOWS.index(window)),
                default="",
            )
            best_rank = ranked.get(best_window, "")
            worst_rank = ranked.get(worst_window, "")
            rows.append(
                {
                    "prefix_count": prefix_count,
                    "strategy_id": strategy_id,
                    "strategy_version": universe_row.get("strategy_version", ""),
                    "method_family": universe_row.get("method_family", ""),
                    "reproduction_status": universe_row.get(
                        "reproduction_status", ""
                    ),
                    **{
                        f"{window.lower()}_official_rank": rank_by_window[window]
                        for window in _OFFICIAL_WINDOWS
                    },
                    **{
                        f"{window.lower()}_official_any_prize_rate": by_window[
                            window
                        ].get("official_any_prize_rate", "")
                        for window in _OFFICIAL_WINDOWS
                    },
                    "best_official_rank": best_rank,
                    "best_window": best_window,
                    "worst_official_rank": worst_rank,
                    "worst_window": worst_window,
                    "official_rank_range": (
                        cast(int, worst_rank) - cast(int, best_rank)
                        if ranked
                        else ""
                    ),
                }
            )
    return rows


def _official_review_markdown(report: dict[str, object]) -> bytes:
    progress = report.get("progress")
    official_metrics = report.get("official_metrics")
    official_rankings = report.get("official_rankings")
    if not isinstance(progress, dict):
        raise MultiTicketBacktestCliError("report progress is malformed")
    if not isinstance(official_metrics, list) or not isinstance(
        official_rankings, list
    ):
        raise MultiTicketBacktestCliError("report official ranking views are malformed")

    progress_row = cast(dict[str, object], progress)
    baseline_by_prefix: dict[int, str] = {}
    official_metric_candidates = cast(list[object], official_metrics)
    for candidate in official_metric_candidates:
        if not isinstance(candidate, dict):
            continue
        row = cast(dict[str, object], candidate)
        prefix_count = row.get("prefix_count")
        baseline = row.get("official_random_baseline_probability")
        if type(prefix_count) is int and isinstance(baseline, dict):
            baseline_row = cast(dict[str, object], baseline)
            decimal = baseline_row.get("decimal_18")
            if isinstance(decimal, str):
                baseline_by_prefix.setdefault(prefix_count, decimal)

    lines = [
        "# BIG_LOTTO official any-prize primary ranking review",
        "",
        "Descriptive historical research only; this artifact does not make a future "
        "prediction or recommendation.",
        "",
        "## Contract",
        "",
        "- Primary criterion: `OFFICIAL_ANY_PRIZE`.",
        "- A successful execution counts once when at least one selected portfolio "
        "ticket resolves to `FIRST` through `GENERAL`; `NO_PRIZE` does not count.",
        "- Rankings are isolated independently for 5, 10, 15, and 20 tickets within "
        "each history window.",
        "- Sort order: official any-prize rate DESC, official random-baseline delta "
        "DESC, coverage DESC, strategy ID ASC.",
        "- The eight M-based criteria remain secondary diagnostics; cross-ticket "
        "comparisons are descriptive and never a combined rank.",
        "",
        "## Exact random baseline",
        "",
        "- Legal six-number tickets: C(49, 6) = 13,983,816.",
        "- Official any-prize tickets under the committed BIG_LOTTO rule: 432,824.",
        "- With-replacement portfolio baseline for K tickets: `1 - ((13,983,816 - "
        "432,824) / 13,983,816)^K`.",
        "",
        "| Tickets (K) | Official random baseline |",
        "| ---: | ---: |",
    ]
    for prefix_count in _OFFICIAL_PREFIX_COUNTS:
        lines.append(
            f"| {prefix_count} | {baseline_by_prefix.get(prefix_count, 'UNAVAILABLE')} |"
        )
    lines.extend(
        [
            "",
            "## Reconciliation",
            "",
            f"- Strategies in catalog: {progress_row.get('total_strategy_count', 'UNAVAILABLE')}",
            f"- BACKTESTED: {progress_row.get('backtested_count', 'UNAVAILABLE')}; "
            "metric-bearing: 133; metrics-unavailable: 2.",
            f"- CLOSED_EXECUTABLE: {progress_row.get('closed_count', 'UNAVAILABLE')}; "
            f"DUPLICATE_ALIAS: {progress_row.get('duplicate_alias_count', 'UNAVAILABLE')}.",
            "- No performance-based exclusions are applied to the catalog or to the "
            "ranking output.",
            "",
            "## Official top 20 by isolated ticket window",
            "",
        ]
    )
    official_ranking_candidates = cast(list[object], official_rankings)
    ranking_rows = [
        cast(dict[str, object], candidate)
        for candidate in official_ranking_candidates
        if isinstance(candidate, dict)
    ]
    for prefix_count in _OFFICIAL_PREFIX_COUNTS:
        lines.extend([f"### {prefix_count} tickets", ""])
        for window in _OFFICIAL_WINDOWS:
            top = sorted(
                (
                    row
                    for row in ranking_rows
                    if row.get("prefix_count") == prefix_count
                    and row.get("window") == window
                    and type(row.get("official_rank")) is int
                ),
                key=lambda row: cast(int, row["official_rank"]),
            )[:20]
            lines.extend(
                [
                    f"#### {window}",
                    "",
                    "| Rank | Strategy | Rate | Delta | Coverage |",
                    "| ---: | --- | ---: | ---: | ---: |",
                ]
            )
            for row in top:
                lines.append(
                    f"| {row['official_rank']} | {row.get('strategy_id', '')} | "
                    f"{_csv_cell(row.get('official_any_prize_rate', ''))} | "
                    f"{_csv_cell(row.get('official_random_baseline_delta', ''))} | "
                    f"{_csv_cell(row.get('coverage', ''))} |"
                )
            lines.append("")
    return ("\n".join(lines).rstrip("\n") + "\n").encode("utf-8")


def _report_files(report: dict[str, object]) -> dict[str, bytes]:
    ranking_fields = (
        "prefix_count",
        "window",
        "criterion",
        "rank",
        "strategy_id",
        "coverage",
        "observed_success_rate",
        "random_baseline_rate_difference",
        "unranked_reason",
    )
    official_ranking_fields = (
        "prefix_count",
        "window",
        "criterion",
        "official_rank",
        "strategy_id",
        "coverage",
        "official_any_prize_count",
        "official_any_prize_rate",
        "official_random_baseline_probability",
        "official_random_baseline_delta",
        "unranked_reason",
    )
    stability_fields = (
        "prefix_count",
        "strategy_id",
        "strategy_version",
        "method_family",
        "reproduction_status",
        "full_official_rank",
        "recent_750_official_rank",
        "recent_300_official_rank",
        "recent_50_official_rank",
        "full_official_any_prize_rate",
        "recent_750_official_any_prize_rate",
        "recent_300_official_any_prize_rate",
        "recent_50_official_any_prize_rate",
        "best_official_rank",
        "best_window",
        "worst_official_rank",
        "worst_window",
        "official_rank_range",
    )
    return {
        REPORT_JSON_FILENAME: _canonical_json_bytes(report),
        UNIVERSE_CSV_FILENAME: _csv_bytes(
            report.get("universe"),
            (
                "strategy_id",
                "strategy_version",
                "legacy_method_id",
                "source_path",
                "source_commit",
                "source_sha256",
                "reproduction_status",
                "duplicate_alias_target",
                "unranked_reason",
            ),
            "universe",
        ),
        EXECUTION_AUDIT_CSV_FILENAME: _csv_bytes(
            report.get("execution_audit"),
            (
                "strategy_id",
                "strategy_version",
                "target_draw_number",
                "status",
                "reason_code",
                "history_cutoff_draw_number",
                "history_cutoff_draw_date",
                "candidate_k",
                "combination_count",
                "native_ticket_count",
                "native_generation",
                "native_duplicate_ticket_count",
                "native_tickets",
                "native_tickets_ordered_sha256",
                "portfolio_ticket_count",
                "portfolio_duplicate_ticket_count",
                "ordered_portfolio",
                "ordered_portfolio_sha256",
                "portfolio_derivation",
            ),
            "execution_audit",
        ),
        METRICS_CSV_FILENAME: _csv_bytes(
            report.get("metrics"),
            (
                "strategy_id",
                "strategy_version",
                "prefix_count",
                "window",
                "window_requested_draws",
                "window_available_draws",
                "window_complete",
                "criterion",
                "successful_execution_count",
                "execution_status_counts",
                "coverage",
                "official_any_prize_count",
                "official_any_prize_rate",
                "official_random_baseline_probability",
                "official_random_baseline_delta",
                "observed_success_count",
                "observed_success_rate",
                "exact_random_baseline_probability",
                "random_baseline_rate_difference",
                "rankable",
            ),
            "metrics",
        ),
        PRIZES_CSV_FILENAME: _csv_bytes(
            report.get("official_prize_distributions"),
            (
                "strategy_id",
                "prefix_count",
                "window",
                "window_requested_draws",
                "window_available_draws",
                "execution_count",
                "ticket_position_count",
                "observed_distinct_ticket_count",
                "observed_duplicate_ticket_count",
                "observation_count_with_duplicate_tickets",
                "official_prize_tier_counts",
                "no_prize_count",
            ),
            "official_prize_distributions",
        ),
        RANKINGS_CSV_FILENAME: _csv_bytes(
            report.get("rankings"),
            ranking_fields,
            "rankings",
        ),
        TOP10_CSV_FILENAME: _csv_bytes(
            report.get("top_10"),
            ranking_fields,
            "top_10",
        ),
        OFFICIAL_RANKINGS_CSV_FILENAME: _csv_bytes(
            report.get("official_rankings"),
            official_ranking_fields,
            "official_rankings",
        ),
        OFFICIAL_TOP20_CSV_FILENAME: _csv_bytes(
            report.get("official_top_20"),
            official_ranking_fields,
            "official_top_20",
        ),
        OFFICIAL_PRIZE_DISTRIBUTION_CSV_FILENAME: _csv_bytes(
            report.get("official_prize_distributions"),
            (
                "strategy_id",
                "prefix_count",
                "window",
                "window_requested_draws",
                "window_available_draws",
                "execution_count",
                "ticket_position_count",
                "observed_distinct_ticket_count",
                "observed_duplicate_ticket_count",
                "observation_count_with_duplicate_tickets",
                "official_prize_tier_counts",
                "no_prize_count",
            ),
            "official_prize_distributions",
        ),
        OFFICIAL_STABILITY_CSV_FILENAME: _csv_bytes(
            _official_cross_period_stability_rows(report),
            stability_fields,
            "official_cross_period_stability",
        ),
        OFFICIAL_REVIEW_FILENAME: _official_review_markdown(report),
    }


def build_multi_ticket_backtest_report(
    *,
    input_file: Path,
    output_directory: Path,
) -> str:
    """Evaluate one input artifact and atomically export all report views."""

    try:
        raw_input = input_file.read_bytes()
    except OSError as exc:
        raise MultiTicketBacktestCliError("input file is unavailable") from exc
    try:
        report = evaluate_biglotto_multi_ticket_backtest(raw_input)
    except MultiTicketBacktestInputError as exc:
        raise MultiTicketBacktestCliError(str(exc)) from exc

    try:
        if output_directory.exists() and not output_directory.is_dir():
            raise MultiTicketBacktestCliError(
                "output path exists and is not a directory"
            )
        output_directory.mkdir(parents=True, exist_ok=True)
        existing = [
            filename
            for filename in _OUTPUT_FILENAMES
            if (output_directory / filename).exists()
        ]
        if existing:
            raise MultiTicketBacktestCliError(
                "refusing to overwrite existing output: " + ",".join(existing)
            )
        content_by_name = _report_files(report)
        checksums = "".join(
            f"{hashlib.sha256(content).hexdigest()}  {filename}\n"
            for filename, content in sorted(content_by_name.items())
        ).encode("ascii")
        content_by_name[CHECKSUM_FILENAME] = checksums

        temporary_paths: list[Path] = []
        try:
            for filename, content in content_by_name.items():
                temporary = output_directory / f".{filename}.tmp-{os.getpid()}"
                temporary_paths.append(temporary)
                with temporary.open("xb") as handle:
                    handle.write(content)
                    handle.flush()
                    os.fsync(handle.fileno())
            for filename in _OUTPUT_FILENAMES:
                os.replace(
                    output_directory / f".{filename}.tmp-{os.getpid()}",
                    output_directory / filename,
                )
        finally:
            for temporary in temporary_paths:
                temporary.unlink(missing_ok=True)
    except MultiTicketBacktestCliError:
        raise
    except OSError as exc:
        raise MultiTicketBacktestCliError("report export failed") from exc

    progress = report["progress"]
    if not isinstance(progress, dict):
        raise MultiTicketBacktestCliError("report progress is malformed")
    summary: dict[str, object] = {
        "output_directory": str(output_directory),
        "report_sha256": report["report_sha256"],
        **cast(dict[str, object], progress),
    }
    return _canonical_json_bytes(summary).decode("utf-8").rstrip("\n")


def multi_ticket_backtest_command(
    input_file: Annotated[
        Path,
        typer.Option("--input-file", exists=True, dir_okay=False),
    ],
    output_directory: Annotated[Path, typer.Option("--output-directory")],
) -> None:
    """Run causal ordered-20 portfolio backtests for 5/10/15/20 prefixes."""

    try:
        typer.echo(
            build_multi_ticket_backtest_report(
                input_file=input_file,
                output_directory=output_directory,
            )
        )
    except MultiTicketBacktestCliError as exc:
        _fail(str(exc))
    except Exception:
        _fail("backtest failed safely")


def _fail(message: str) -> NoReturn:
    typer.echo(f"backtest-biglotto-portfolios error: {message}", err=True)
    raise typer.Exit(code=1)


__all__ = [
    "CHECKSUM_FILENAME",
    "EXECUTION_AUDIT_CSV_FILENAME",
    "METRICS_CSV_FILENAME",
    "OFFICIAL_PRIZE_DISTRIBUTION_CSV_FILENAME",
    "OFFICIAL_RANKINGS_CSV_FILENAME",
    "OFFICIAL_REVIEW_FILENAME",
    "OFFICIAL_STABILITY_CSV_FILENAME",
    "OFFICIAL_TOP20_CSV_FILENAME",
    "PRIZES_CSV_FILENAME",
    "RANKINGS_CSV_FILENAME",
    "REPORT_JSON_FILENAME",
    "TOP10_CSV_FILENAME",
    "UNIVERSE_CSV_FILENAME",
    "MultiTicketBacktestCliError",
    "build_multi_ticket_backtest_report",
    "multi_ticket_backtest_command",
]
