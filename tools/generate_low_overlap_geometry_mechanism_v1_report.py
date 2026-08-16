"""Render the human-readable report for the sealed LOW_OVERLAP_GEOMETRY_MECHANISM_V1 result.

Pure formatting over `low-overlap-geometry-mechanism-v1-result.json`: every
number in the report is read from that file, never recomputed here. Produces
the tables `low-overlap-geometry-mechanism-v1-execution-plan-schema.md`
S11 requires: metric semantics, per lottery/k coverage-redundancy-S2, the
full signed decomposition, pairwise contribution share and descriptor,
geometry, the exact identity/check table, replicated classifications, the
unchanged claim boundary, and runtime/memory/provenance.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_MATRIX_RESULTS = "docs/research/matrix-native-results/"
RESULT_PATH = Path(_MATRIX_RESULTS + "low-overlap-geometry-mechanism-v1-result.json")
OUTPUT_PATH = Path(_MATRIX_RESULTS + "low-overlap-geometry-mechanism-v1-report.md")

LADDER = (1, 3, 5, 10, 15, 20)


def _fmt_rational_or_sentinel(value: dict[str, Any] | str) -> str:
    if isinstance(value, str):
        return value
    return value["exact"]


def _render_metric_semantics(result: dict[str, Any]) -> str:
    semantics = result["metric_semantics"]
    lines = [
        "## 1. Metric semantics (sealed-label correction)",
        "",
        "| Name | Formula |",
        "|---|---|",
        f"| `RELATIVE_LIFT_VS_RANDOM` | `{semantics['RELATIVE_LIFT_VS_RANDOM']}` |",
        (
            "| `RELATIVE_COVERAGE_DELTA_VS_SIDON` | "
            f"`{semantics['RELATIVE_COVERAGE_DELTA_VS_SIDON']}` |"
        ),
        (
            "| `GAIN_OVER_RANDOM_RATIO_TO_SIDON` | "
            f"`{semantics['GAIN_OVER_RANDOM_RATIO_TO_SIDON']}` |"
        ),
        "",
        (
            "The sealed report label `REL_GAIN_OVER_SIDON` maps only to "
            f"`{semantics['sealed_REL_GAIN_OVER_SIDON_maps_to']}` -- **not** to "
            "`RELATIVE_COVERAGE_DELTA_VS_SIDON`. This mapping is unchanged from the "
            "locked preregistration."
        ),
        "",
    ]
    return "\n".join(lines)


def _render_coverage_redundancy_s2_table(result: dict[str, Any]) -> str:
    lines = [
        "## 2. Per lottery/k coverage, redundancy, and S2 comparison",
        "",
        "| Lottery | k | Q_ARM_B | Q_SIDON | REDUNDANCY_B | REDUNDANCY_S | S2_B | S2_S |",
        "|---|---:|---|---|---:|---:|---:|---:|",
    ]
    for lottery_key, lottery in result["per_lottery"].items():
        for k in LADDER:
            cell = lottery["per_k"][str(k)]
            arm_b = cell["arms"]["ARM_B"]
            sidon = cell["arms"]["SIDON"]
            lines.append(
                f"| {lottery_key} | {k} | {arm_b['q']['exact']} | {sidon['q']['exact']} | "
                f"{arm_b['redundancy']} | {sidon['redundancy']} | "
                f"{arm_b['s2_multiplicity']} | {sidon['s2_multiplicity']} |"
            )
    lines.append("")
    return "\n".join(lines)


def _render_signed_decomposition_table(result: dict[str, Any]) -> str:
    lines = [
        "## 3. Full signed decomposition (Arm-B minus Sidon)",
        "",
        (
            "| Lottery | k | DELTA_COVERED | -DELTA_S2 (P) | +DELTA_S3 | -DELTA_S4 | "
            "+DELTA_S5 (higher j alternate sign) | H (higher-order residual) |"
        ),
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for lottery_key, lottery in result["per_lottery"].items():
        for k in LADDER:
            comparison = lottery["per_k"][str(k)]["comparison"]
            terms = comparison["higher_order_signed_terms"]
            t3 = terms.get("3", "n/a" if k < 3 else 0)
            t4 = terms.get("4", "n/a" if k < 4 else 0)
            t5 = terms.get("5", "n/a" if k < 5 else 0)
            lines.append(
                f"| {lottery_key} | {k} | {comparison['delta_covered']} | "
                f"{comparison['pairwise_component']} | {t3} | {t4} | {t5} | "
                f"{comparison['higher_order_residual']} |"
            )
    lines.append("")
    lines.append(
        "Every signed `T_j` for `j` up to `k` is persisted in the machine-readable "
        "result's `comparison.higher_order_signed_terms`; only `j in {3,4,5}` are "
        "tabulated above for readability. `n/a` marks a `j` that exceeds that cell's "
        "own `k` (no such term exists, not a suppressed one)."
    )
    lines.append("")
    return "\n".join(lines)


def _render_contribution_share_table(result: dict[str, Any]) -> str:
    lines = [
        "## 4. Pairwise contribution share and per-cell mechanism descriptor",
        "",
        "| Lottery | k | \\|P\\|/(\\|P\\|+sum\\|T_j\\|) | Mechanism descriptor |",
        "|---|---:|---|---|",
    ]
    for lottery_key, lottery in result["per_lottery"].items():
        for k in LADDER:
            comparison = lottery["per_k"][str(k)]["comparison"]
            share = _fmt_rational_or_sentinel(comparison["pairwise_absolute_contribution_share"])
            descriptor = comparison["mechanism_descriptor"]
            lines.append(f"| {lottery_key} | {k} | {share} | {descriptor} |")
    lines.append("")
    return "\n".join(lines)


def _render_geometry_table(result: dict[str, Any]) -> str:
    lines = [
        "## 5. Geometry (both arms)",
        "",
        (
            "| Lottery | k | Arm | Max overlap | Mean overlap | Unique numbers | "
            "Reuse dispersion (float) | Duplicates |"
        ),
        "|---|---:|---|---:|---|---:|---:|---:|",
    ]
    for lottery_key, lottery in result["per_lottery"].items():
        for k in LADDER:
            cell = lottery["per_k"][str(k)]
            for arm_label in ("ARM_B", "SIDON"):
                geometry = cell["arms"][arm_label]["geometry"]
                lines.append(
                    f"| {lottery_key} | {k} | {arm_label} | "
                    f"{geometry['max_pairwise_overlap']} | "
                    f"{geometry['mean_pairwise_overlap']['exact']} | "
                    f"{geometry['unique_number_coverage']} | "
                    f"{geometry['reuse_dispersion_float']:.6f} | "
                    f"{geometry['duplicate_count']} |"
                )
    lines.append("")
    return "\n".join(lines)


def _render_checks_table(result: dict[str, Any]) -> str:
    check_names = [
        "n_c_sums_to_winning_space",
        "fixed_incidence_identity",
        "redundancy_identity",
        "inclusion_exclusion_identity",
        "s2_geometry_identity",
        "reuse_vector_identity",
        "zero_duplicates",
        "q_arm_b_matches_sealed",
        "q_sidon_matches_sealed",
    ]
    lines = [
        "## 6. Exact identity/check table",
        "",
        "Every cell below passed every check; a single failure would have raised "
        "before this result file could ever be written (no partial result is ever "
        "persisted).",
        "",
        "| Lottery | k | " + " | ".join(check_names) + " |",
        "|---|---:|" + "---|" * len(check_names),
    ]
    for lottery_key, lottery in result["per_lottery"].items():
        for k in LADDER:
            checks = lottery["per_k"][str(k)]["checks"]
            values = " | ".join("PASS" if checks[name] else "FAIL" for name in check_names)
            lines.append(f"| {lottery_key} | {k} | {values} |")
    lines.append("")
    return "\n".join(lines)


def _render_classifications(result: dict[str, Any]) -> str:
    classifications = result["classifications"]
    redundancy = classifications["redundancy_reduction"]
    pairwise = classifications["pairwise_collision_reduction"]
    lines = [
        "## 7. Replicated classifications",
        "",
        f"```text",  # noqa: F541
        f"REDUNDANCY_REDUCTION_STATUS: {redundancy['value']}",
        f"  failing_or_equal_cells: {redundancy['failing_or_equal_cells'] or 'NONE'}",
        f"PAIRWISE_COLLISION_STATUS: {pairwise['value']}",
        f"  failing_or_equal_cells: {pairwise['failing_or_equal_cells'] or 'NONE'}",
        (
            "MECHANISM_DESCRIPTOR_COUNTS (k>1 cells only): "
            f"{classifications['mechanism_descriptor_counts']}"
        ),
        f"AGGREGATE_MECHANISM_DESCRIPTOR: {classifications['aggregate_mechanism_descriptor']}",
        f"GLOBAL_OPTIMUM_STATUS: {classifications['global_optimum_status']}",
        f"FINAL_CLASSIFICATION: {result['final_classification']}",
        "```",
        "",
    ]
    return "\n".join(lines)


def _render_claim_boundary(result: dict[str, Any]) -> str:
    scope = result["scope"]
    return "\n".join(
        [
            "## 8. Claim boundary (unchanged from lock)",
            "",
            "This study supports exact combinatorial mechanism claims only.",
            "",
            "```text",
            f"predictive_advantage:   {scope['predictive_advantage']}",
            f"prize_value_advantage:  {scope['prize_value_advantage']}",
            f"economic_optimality:    {scope['economic_optimality']}",
            f"global_optimum_status:  {result['classifications']['global_optimum_status']}",
            f"p638_zone2:             {scope['p638_zone2']}",
            f"arm_c:                  {scope['arm_c']}",
            f"monte_carlo:            {scope['monte_carlo']}",
            f"historical_draws_read:  {scope['historical_draws_read']}",
            "```",
            "",
        ]
    )


def _render_provenance(result: dict[str, Any]) -> str:
    canonical_input = result["canonical_input"]
    runtime = result["runtime_seconds"]
    lines = [
        "## 9. Runtime, memory, and exact input provenance",
        "",
        "```text",
        f"repository: {canonical_input['repository']}",
        f"canonical_input_commit: {canonical_input['commit']}",
        f"canonical_input_tree:   {canonical_input['tree']}",
        f"locked_preregistration_path:   {canonical_input['locked_preregistration_path']}",
        f"locked_preregistration_sha256: {canonical_input['locked_preregistration_sha256']}",
        "```",
        "",
        "Input Git blobs (frozen at lock time, re-verified byte-identical during Phase 0):",
        "",
        "| Path | Git blob SHA-1 |",
        "|---|---|",
    ]
    for path, blob in sorted(canonical_input["input_blobs"].items()):
        lines.append(f"| `{path}` | `{blob}` |")
    lines.append("")
    lines.append("```text")
    for lottery_key, seconds_by_arm in runtime["portfolio_generation_by_lottery_and_arm"].items():
        lines.append(
            f"{lottery_key} portfolio generation: "
            f"SIDON={seconds_by_arm['SIDON']:.3f}s ARM_B={seconds_by_arm['ARM_B']:.3f}s"
        )
    for lottery_key, seconds in runtime["winning_space_enumeration_by_lottery"].items():
        lines.append(f"{lottery_key} winning-space enumeration: {seconds:.3f}s")
    lines.append(f"derivation_and_validation: {runtime['derivation_and_validation']:.3f}s")
    lines.append(f"total: {runtime['total']:.3f}s")
    lines.append(f"peak_memory_bytes: {result['peak_memory_bytes']}")
    lines.append("```")
    lines.append("")
    return "\n".join(lines)


def render_report(result: dict[str, Any]) -> str:
    header = "\n".join(
        [
            f"# {result['study_id']} -- report",
            "",
            "Status: SEALED | exact combinatorial mechanism decomposition, real "
            "B649/T539/P638 Zone-1 winning-space scale | native execution complete",
            "",
            "No historical draw is read. No Monte Carlo estimate is used. Predictive "
            "advantage, prize-value advantage, economic optimality, P638 Zone-2, and "
            "Arm-C are all out of scope for this study (see S8 for the full claim "
            "boundary).",
            "",
        ]
    )
    sections = [
        _render_metric_semantics(result),
        _render_coverage_redundancy_s2_table(result),
        _render_signed_decomposition_table(result),
        _render_contribution_share_table(result),
        _render_geometry_table(result),
        _render_checks_table(result),
        _render_classifications(result),
        _render_claim_boundary(result),
        _render_provenance(result),
    ]
    return header + "\n".join(sections)


def main() -> None:
    result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    report = render_report(result)
    OUTPUT_PATH.write_text(report, encoding="utf-8")
    print(f"wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
