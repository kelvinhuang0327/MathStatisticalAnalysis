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
CHECKSUM_FILENAME = "SHA256SUMS"
_OUTPUT_FILENAMES = (
    REPORT_JSON_FILENAME,
    UNIVERSE_CSV_FILENAME,
    EXECUTION_AUDIT_CSV_FILENAME,
    METRICS_CSV_FILENAME,
    PRIZES_CSV_FILENAME,
    RANKINGS_CSV_FILENAME,
    TOP10_CSV_FILENAME,
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
    "PRIZES_CSV_FILENAME",
    "RANKINGS_CSV_FILENAME",
    "REPORT_JSON_FILENAME",
    "TOP10_CSV_FILENAME",
    "UNIVERSE_CSV_FILENAME",
    "MultiTicketBacktestCliError",
    "build_multi_ticket_backtest_report",
    "multi_ticket_backtest_command",
]
