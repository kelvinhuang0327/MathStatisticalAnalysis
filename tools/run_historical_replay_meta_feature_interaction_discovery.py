"""Preregister and run the frozen R2 meta-feature interaction discovery."""

from __future__ import annotations

import argparse
import json
from decimal import Decimal, localcontext
from fractions import Fraction
from pathlib import Path
from typing import cast

from lottolab.evidence import canonical_json
from lottolab.infrastructure.historical_replay_meta_feature_interaction_corpus import (
    load_historical_replay_discovery_corpus,
)
from lottolab.research.historical_replay_meta_feature_interaction_discovery import (
    FEATURE_COUNT,
    INTERACTION_CANDIDATE_COUNT,
    PINNED_R1_RESULT_SHA256,
    CandidateEvaluation,
    InteractionDiscoveryExecution,
    PerformanceMetrics,
    R1DiscoveryAuthority,
    candidate_universe_sha256,
    exact_fraction_text,
    preregistration_payload,
    r1_discovery_authority_from_result,
    run_interaction_discovery,
)


def _r1_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--r1-result", required=True, type=Path)
    parser.add_argument("--expected-r1-result-sha256", required=True)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Execute the frozen 612-rule R1-discovery-only meta-feature interaction study."
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    preregister = subparsers.add_parser(
        "preregister",
        help="Write the complete selector universe and robustness gate before scoring.",
    )
    _r1_arguments(preregister)
    preregister.add_argument("--output", required=True, type=Path)

    run = subparsers.add_parser(
        "run",
        help="Verify the frozen design and evaluate only the R1 discovery partition.",
    )
    _r1_arguments(run)
    run.add_argument("--research-db", required=True, type=Path)
    run.add_argument("--expected-db-sha256", required=True)
    run.add_argument("--source-run-id", required=True)
    run.add_argument("--preregistration", required=True, type=Path)
    run.add_argument("--expected-preregistration-sha256", required=True)
    run.add_argument("--result", required=True, type=Path)
    run.add_argument("--result-sha256", required=True, type=Path)
    run.add_argument("--report", required=True, type=Path)
    return parser


def _require_new_outputs(paths: tuple[Path, ...]) -> tuple[Path, ...]:
    resolved = tuple(path.resolve() for path in paths)
    if len(set(resolved)) != len(resolved):
        raise ValueError("output paths must be distinct")
    for path in resolved:
        if path.exists():
            raise ValueError(f"refusing to overwrite existing output: {path}")
        if not path.parent.is_dir():
            raise ValueError(f"output parent does not exist: {path.parent}")
    return resolved


def _load_canonical_object(path: Path, *, expected_sha256: str, label: str) -> dict[str, object]:
    if path.is_symlink():
        raise ValueError(f"{label} path must not be a symlink")
    resolved = path.resolve(strict=True)
    if not resolved.is_file():
        raise ValueError(f"{label} path must be a regular file")
    raw = resolved.read_bytes()
    actual_sha256 = canonical_json.sha256_hex(raw)
    if actual_sha256 != expected_sha256:
        raise ValueError(f"{label} SHA-256 does not match the frozen pin")
    value = cast(object, canonical_json.loads_canonical(raw))
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a canonical object")
    mapping = cast("dict[str, object]", value)
    if raw != canonical_json.canonical_file_bytes(mapping):
        raise ValueError(f"{label} bytes are not canonical LCJ-1 file bytes")
    return mapping


def _load_r1_authority(args: argparse.Namespace) -> R1DiscoveryAuthority:
    expected = cast(str, args.expected_r1_result_sha256)
    if expected != PINNED_R1_RESULT_SHA256:
        raise ValueError("requested R1 result SHA-256 differs from the R2 packet pin")
    value = _load_canonical_object(
        cast(Path, args.r1_result),
        expected_sha256=expected,
        label="R1 result",
    )
    return r1_discovery_authority_from_result(value, r1_result_sha256=expected)


def _decimal(value: Fraction, places: int = 6) -> str:
    with localcontext() as context:
        context.prec = 40
        resolved = Decimal(value.numerator) / Decimal(value.denominator)
        quantum = Decimal(1).scaleb(-places)
        return format(resolved.quantize(quantum), "f")


def _metric_line(metrics: PerformanceMetrics) -> str:
    return (
        f"support={metrics.support_count}; "
        f"M2+={exact_fraction_text(metrics.selected_m2_rate)} "
        f"({_decimal(metrics.selected_m2_rate)}); "
        f"pool={exact_fraction_text(metrics.pool_m2_rate)}; "
        f"delta_pool={exact_fraction_text(metrics.m2_delta_vs_pool)}; "
        f"avg_match={exact_fraction_text(metrics.selected_avg_match)}; "
        f"avg_match_delta_pool={exact_fraction_text(metrics.avg_match_delta_vs_pool)}"
    )


def _candidate_report_lines(rank: int, candidate: CandidateEvaluation) -> list[str]:
    lines = [
        f"### {rank}. `{candidate.rule.candidate_id}`",
        "",
        f"- Exact interaction: {candidate.rule.exact_rule}",
        f"- Pooled discovery: {_metric_line(candidate.performance)}",
        "- Frozen trailing discovery windows:",
        "",
    ]
    for window in (50, 300, 750):
        lines.append(f"  - {window} draws: {_metric_line(candidate.windows[window])}")
    lines.extend(
        [
            "",
            "- Selected-strategy support: "
            + ", ".join(
                f"{strategy_id}={count}"
                for strategy_id, count in sorted(candidate.selection_counts.items())
            ),
            "",
        ]
    )
    return lines


def _render_report(execution: InteractionDiscoveryExecution, result_sha256: str) -> str:
    winner = execution.winner
    pooled_winner = execution.pooled_winner
    metrics = winner.performance
    authority = execution.authority
    robustness = execution.temporal_robustness
    profile = execution.corpus.profile
    m2_delta_vs_r1 = metrics.m2_delta_vs_pool - authority.benchmark_m2_delta_vs_pool
    avg_delta_vs_r1 = (
        metrics.avg_match_delta_vs_pool - authority.benchmark_avg_match_delta_vs_pool
    )
    lines = [
        "# Historical Replay Meta-Feature Interaction Discovery R2",
        "",
        f"FINAL_CLASSIFICATION: **{execution.final_classification.value}**",
        "",
        execution.classification_reason,
        "",
        "This is discovery-only hypothesis generation. The consumed R1 confirmation set was "
        "excluded at the SQL boundary; no confirmation or strategy-promotion claim is made.",
        "",
        "## Required output",
        "",
        f"FEATURE_COUNT: **{FEATURE_COUNT}**",
        f"INTERACTION_CANDIDATE_COUNT: **{INTERACTION_CANDIDATE_COUNT}**",
        f"COMPLETED_COUNT: **{execution.completed_count}**",
        "FAILED_COUNT: **0**",
        "PRUNED_COUNT: **0**",
        f"ROBUST_CANDIDATE_COUNT: **{execution.robust_candidate_count}**",
        "",
        f"BEST_DISCOVERY_INTERACTION: `{winner.rule.candidate_id}`",
        "",
        f"Exact selector: {winner.rule.exact_rule}",
        "",
        f"RAW_BEST_POOLED_DISCOVERY_INTERACTION: `{pooled_winner.rule.candidate_id}`",
        "",
        f"Raw pooled winner result: {_metric_line(pooled_winner.performance)}",
        "",
        "Acceptance rule: keep the pooled ranking unchanged and freeze the first "
        "ranked interaction that passes the separately preregistered temporal gate.",
        "",
        f"DISCOVERY_RESULT: {_metric_line(metrics)}",
        "",
        "TEMPORAL_ROBUSTNESS:",
        "",
    ]
    for window in (50, 300, 750):
        window_metrics = winner.windows[window]
        lines.append(f"- {window} draws: {_metric_line(window_metrics)}")
    lines.extend(
        [
            f"- Frozen gate passed: **{str(robustness.passed).upper()}**",
            "- Gate: M2 and average-match deltas versus the pooled first-ticket baseline "
            "must both be strictly positive in each trailing 50/300/750 discovery window.",
            "- Robustness did not alter pooled discovery scores or rank order; it is the "
            "predeclared acceptance gate applied after all 612 candidates complete.",
            "",
            "DELTA_VS_BEST_R1_SINGLE_FEATURE_RULE:",
            "",
            f"- R1 rule: `{authority.benchmark_candidate_id}`",
            "- R1 pooled discovery M2 delta vs pool: "
            f"`{exact_fraction_text(authority.benchmark_m2_delta_vs_pool)}`",
            "- R2 pooled discovery M2 delta vs pool: "
            f"`{exact_fraction_text(metrics.m2_delta_vs_pool)}`",
            f"- Difference: `{exact_fraction_text(m2_delta_vs_r1)}`",
            "- R1 pooled discovery average-match delta vs pool: "
            f"`{exact_fraction_text(authority.benchmark_avg_match_delta_vs_pool)}`",
            "- R2 pooled discovery average-match delta vs pool: "
            f"`{exact_fraction_text(metrics.avg_match_delta_vs_pool)}`",
            f"- Difference: `{exact_fraction_text(avg_delta_vs_r1)}`",
            "",
            "FUTURE_CONFIRMATION_STATUS: **REQUIRES_FRESH_UNSEEN_DATA**",
            "",
            "PROMOTION_DECISION: **NOT_AUTHORIZED**",
            "",
            "## Corpus and exclusion evidence",
            "",
            f"- R1 result SHA-256: `{authority.r1_result_sha256}`",
            f"- R1 discovery-authority projection SHA-256: `{authority.projection_sha256}`",
            f"- Database SHA-256: `{execution.database_sha256}`",
            f"- Source run: `{execution.corpus.source_run_id}`",
            f"- Loaded draws: {len(execution.corpus.draws)} "
            f"({authority.partition.warmup_count} warmup + "
            f"{authority.partition.discovery_count} discovery)",
            "- Loaded confirmation observations: 0",
            "- Discovery first target: "
            f"{authority.partition.discovery_first_target.draw_date} / "
            f"{authority.partition.discovery_first_target.draw_number}",
            "- Discovery last target: "
            f"{authority.partition.discovery_last_target.draw_date} / "
            f"{authority.partition.discovery_last_target.draw_number}",
            "- Bounded targets / tickets / results: "
            f"{profile.bounded_target_row_count} / {profile.bounded_ticket_row_count} / "
            f"{profile.bounded_result_row_count}",
            "- Required nulls / invalid JSON / recomputed-hit mismatches / "
            "causal-date violations / extra result versions: "
            f"{profile.required_null_count} / {profile.invalid_json_count} / "
            f"{profile.recomputed_hit_mismatch_count} / "
            f"{profile.causal_date_violation_count} / {profile.result_version_extra_count}",
            "- Duplicate native ticket positions retained: "
            f"{profile.duplicate_native_ticket_position_count}",
            "",
            "## Frozen universe and determinism",
            "",
            f"- Candidate universe SHA-256: `{candidate_universe_sha256()}`",
            f"- Preregistration SHA-256: `{execution.preregistration_sha256}`",
            f"- Canonical result / determinism SHA-256: `{result_sha256}`",
            "- Candidate construction: C(18,2) unordered feature pairs x four MAX/MIN "
            "direction combinations.",
            "- A is primary; B only resolves equal A; strategy ID is the final tie-break.",
            "- No learned threshold, continuous tuning, optimizer dependency, or pruning.",
            "",
            "## Top pooled discovery candidates",
            "",
        ]
    )
    for rank, candidate in enumerate(execution.top_discovery_candidates, start=1):
        lines.extend(_candidate_report_lines(rank, candidate))
    return "\n".join(lines).rstrip() + "\n"


def _preregister(args: argparse.Namespace) -> int:
    authority = _load_r1_authority(args)
    payload = preregistration_payload(authority)
    raw = canonical_json.canonical_file_bytes(payload)
    (output,) = _require_new_outputs((cast(Path, args.output),))
    output.write_bytes(raw)
    print(
        json.dumps(
            {
                "candidate_universe_sha256": payload["candidate_universe_sha256"],
                "feature_count": FEATURE_COUNT,
                "interaction_candidate_count": INTERACTION_CANDIDATE_COUNT,
                "output": str(output),
                "preregistration_sha256": canonical_json.sha256_hex(raw),
                "r1_discovery_authority_sha256": authority.projection_sha256,
            },
            sort_keys=True,
        )
    )
    return 0


def _run(args: argparse.Namespace) -> int:
    authority = _load_r1_authority(args)
    expected_preregistration_sha256 = cast(str, args.expected_preregistration_sha256)
    frozen = _load_canonical_object(
        cast(Path, args.preregistration),
        expected_sha256=expected_preregistration_sha256,
        label="preregistration",
    )
    current = preregistration_payload(authority)
    if frozen != current:
        raise ValueError("live R1 authority/design no longer matches the frozen preregistration")

    expected_database_sha256 = cast(str, args.expected_db_sha256)
    source_run_id = cast(str, args.source_run_id)
    if expected_database_sha256 != authority.source_database_sha256:
        raise ValueError("requested database SHA-256 differs from the R1 discovery authority")
    if source_run_id != authority.source_run_id:
        raise ValueError("requested source run differs from the R1 discovery authority")

    result_path, sidecar_path, report_path = _require_new_outputs(
        (
            cast(Path, args.result),
            cast(Path, args.result_sha256),
            cast(Path, args.report),
        )
    )
    loaded = load_historical_replay_discovery_corpus(
        cast(Path, args.research_db),
        expected_database_sha256=expected_database_sha256,
        source_run_id=source_run_id,
        partition=authority.partition,
    )
    execution = run_interaction_discovery(
        loaded.corpus,
        database_sha256=loaded.database_sha256,
        preregistration_sha256=expected_preregistration_sha256,
        authority=authority,
    )
    result_raw = canonical_json.canonical_file_bytes(execution.canonical_dict())
    result_sha256 = canonical_json.sha256_hex(result_raw)
    report_raw = _render_report(execution, result_sha256).encode("utf-8")
    sidecar_raw = f"{result_sha256}  {result_path.name}\n".encode()

    result_path.write_bytes(result_raw)
    sidecar_path.write_bytes(sidecar_raw)
    report_path.write_bytes(report_raw)
    print(
        json.dumps(
            {
                "completed_count": execution.completed_count,
                "failed_count": 0,
                "final_classification": execution.final_classification.value,
                "interaction_candidate_count": INTERACTION_CANDIDATE_COUNT,
                "pruned_count": 0,
                "report": str(report_path),
                "result": str(result_path),
                "result_sha256": result_sha256,
                "robust_candidate_count": execution.robust_candidate_count,
                "temporal_robustness_passed": execution.temporal_robustness.passed,
                "winner_candidate_id": execution.winner.rule.candidate_id,
            },
            sort_keys=True,
        )
    )
    return 0


def main() -> int:
    args = _parser().parse_args()
    if args.command == "preregister":
        return _preregister(args)
    if args.command == "run":
        return _run(args)
    raise AssertionError("unreachable command")


if __name__ == "__main__":
    raise SystemExit(main())
