"""Render the human-readable report for the sealed HIGHER_ORDER_RESIDUAL_MECHANISM_V1 result.

Pure formatting over `higher-order-residual-mechanism-v1-result.json`: every
number in the report is read from that file, never recomputed here. Produces
the tables `higher-order-residual-mechanism-v1-execution-plan-schema.md` S11
requires: S3_GEOMETRY vs sealed S3_MULTIPLICITY, the ticket-triple
intersection histogram, saturated-triple-count by k against the sealed
residual magnitude, the Necessary Mass Bound Lemma prediction vs the sealed
zero/nonzero pattern, and the unchanged claim boundary.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_MATRIX_RESULTS = "docs/research/matrix-native-results/"
RESULT_PATH = Path(_MATRIX_RESULTS + "higher-order-residual-mechanism-v1-result.json")
OUTPUT_PATH = Path(_MATRIX_RESULTS + "higher-order-residual-mechanism-v1-report.md")

TRIPLE_LADDER = (3, 5, 10, 15, 20)
ARM_KEYS = ("ARM_B", "SIDON")


def _fmt_rational_or_sentinel(value: dict[str, Any] | str) -> str:
    if isinstance(value, str):
        return value
    return value["exact"]


def _render_identity_table(result: dict[str, Any]) -> str:
    lines = [
        "## 1. S3_GEOMETRY vs sealed S3_MULTIPLICITY (the core new identity)",
        "",
        "| Lottery | k | Arm | S3_GEOMETRY | S3_MULTIPLICITY | Identity |",
        "|---|---:|---|---:|---:|---|",
    ]
    for lottery_key, lottery in result["per_lottery"].items():
        for k in TRIPLE_LADDER:
            for arm in ARM_KEYS:
                cell = lottery["per_k"][str(k)]["arms"][arm]
                identity = "PASS" if cell["s3_geometry_identity"] else "FAIL"
                lines.append(
                    f"| {lottery_key} | {k} | {arm} | {cell['s3_geometry']} | "
                    f"{cell['s3_multiplicity']} | {identity} |"
                )
    lines.append("")
    lines.append(
        "Every row above passed; a single failure would have raised before this "
        "result file could ever be written (no partial result is ever persisted)."
    )
    lines.append("")
    return "\n".join(lines)


def _render_histogram_section(result: dict[str, Any]) -> str:
    lines = [
        "## 2. Ticket-triple intersection histogram (canonical shape `r_min,r_mid,r_max,s`)",
        "",
    ]
    for lottery_key, lottery in result["per_lottery"].items():
        for k in TRIPLE_LADDER:
            for arm in ARM_KEYS:
                cell = lottery["per_k"][str(k)]["arms"][arm]
                histogram = cell["ticket_triple_intersection_histogram"]
                total = sum(histogram.values())
                ordered = sorted(histogram.items(), key=lambda kv: kv[1], reverse=True)
                parts = ", ".join(f"{shape}:{count}" for shape, count in ordered)
                lines.append(f"- `{lottery_key}` k={k} `{arm}` ({total} triples): {parts}")
    lines.append("")
    return "\n".join(lines)


def _render_saturated_triple_table(result: dict[str, Any]) -> str:
    lines = [
        "## 3. Saturated-triple count by k (the H2 endpoint) vs sealed residual magnitude",
        "",
        (
            "| Lottery | k | Arm | Saturated triples | Total triples | Sealed T3 | "
            "Sealed H | Sealed \\|H\\|/\\|DELTA_COVERED\\| |"
        ),
        "|---|---:|---|---:|---:|---:|---:|---|",
    ]
    for lottery_key, lottery in result["per_lottery"].items():
        for k in TRIPLE_LADDER:
            comparison = lottery["per_k"][str(k)]["comparison"]
            for arm in ARM_KEYS:
                cell = lottery["per_k"][str(k)]["arms"][arm]
                total = sum(cell["ticket_triple_intersection_histogram"].values())
                ratio = _fmt_rational_or_sentinel(comparison["residual_to_net_gain_ratio"])
                lines.append(
                    f"| {lottery_key} | {k} | {arm} | {cell['saturated_triple_count']} | "
                    f"{total} | {comparison['sealed_t3']} | "
                    f"{comparison['sealed_higher_order_residual']} | {ratio} |"
                )
    lines.append("")
    lines.append(
        "`residual_to_net_gain_ratio = H / DELTA_COVERED` is read from the sealed "
        "Phase-5 result unchanged (both terms already exact and sealed); it is "
        "reported once per `(lottery, k)` cell, not per arm, since `DELTA_COVERED` "
        "is itself an Arm-B-minus-Sidon comparison quantity."
    )
    lines.append("")
    return "\n".join(lines)


def _render_mass_bound_table(result: dict[str, Any]) -> str:
    lines = [
        "## 4. Necessary Mass Bound Lemma prediction vs the sealed zero/nonzero pattern",
        "",
        (
            "| Lottery | k | Arm | mass_bound_prediction_correct | S3_MULTIPLICITY==0 | "
            "Sealed max_pairwise_overlap |"
        ),
        "|---|---:|---|---|---|---:|",
    ]
    for lottery_key, lottery in result["per_lottery"].items():
        for k in TRIPLE_LADDER:
            for arm in ARM_KEYS:
                cell = lottery["per_k"][str(k)]["arms"][arm]
                correct = "PASS" if cell["mass_bound_prediction_correct"] else "EXCEPTION"
                lines.append(
                    f"| {lottery_key} | {k} | {arm} | {correct} | "
                    f"{cell['s3_multiplicity'] == 0} | {cell['sealed_max_pairwise_overlap']} |"
                )
    lines.append("")
    return "\n".join(lines)


def _render_mechanism_context_table(result: dict[str, Any]) -> str:
    lines = [
        "## 5. Sealed higher-order terms and mechanism descriptor (context only, read-only)",
        "",
        (
            "| Lottery | k | Sealed T3 | Sealed T4 | Sealed T5 | Sealed H | "
            "Sealed DELTA_COVERED | Sealed mechanism descriptor |"
        ),
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for lottery_key, lottery in result["per_lottery"].items():
        for k in TRIPLE_LADDER:
            comparison = lottery["per_k"][str(k)]["comparison"]
            lines.append(
                f"| {lottery_key} | {k} | {comparison['sealed_t3']} | "
                f"{comparison['sealed_t4']} | {comparison['sealed_t5']} | "
                f"{comparison['sealed_higher_order_residual']} | "
                f"{comparison['sealed_delta_covered']} | "
                f"{comparison['sealed_mechanism_descriptor']} |"
            )
    lines.append("")
    lines.append(
        "`J4_GEOMETRY` (whether `S4_GEOMETRY == S4_MULTIPLICITY` holds the same way "
        "`S3` does) is `OUT_OF_SCOPE` for this lock -- `T4`/`T5` above are copied "
        "read-only from the sealed Phase-5 result for context, never recomputed or "
        "geometrically explained by this study."
    )
    lines.append("")
    return "\n".join(lines)


def _render_portfolio_hash_table(result: dict[str, Any]) -> str:
    lines = [
        "## 6. Portfolio hash verification (licenses reusing sealed S3_MULTIPLICITY)",
        "",
        "| Lottery | Arm | Regenerated SHA-256 matches sealed |",
        "|---|---|---|",
    ]
    for lottery_key, lottery in result["per_lottery"].items():
        for arm in ARM_KEYS:
            status = "PASS" if lottery["portfolio_hash_status"][arm] else "FAIL"
            lines.append(f"| {lottery_key} | {arm} | {status} |")
    lines.append("")
    return "\n".join(lines)


def _render_classifications(result: dict[str, Any]) -> str:
    classifications = result["classifications"]
    s3_identity = classifications["s3_geometry_identity"]
    mass_bound = classifications["mass_bound_prediction"]
    lines = [
        "## 7. Classifications",
        "",
        "```text",
        f"S3_GEOMETRY_IDENTITY_STATUS: {s3_identity['value']}",
        f"  failing_cells: {s3_identity['failing_cells'] or 'NONE'}",
        f"MASS_BOUND_PREDICTION_STATUS: {mass_bound['value']}",
        f"  exception_cells: {mass_bound['exception_cells'] or 'NONE'}",
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
            "This study supports exact combinatorial `S3` triple-geometry mechanism "
            "claims only.",
            "",
            "```text",
            f"predictive_advantage:   {scope['predictive_advantage']}",
            f"prize_value_advantage:  {scope['prize_value_advantage']}",
            f"economic_optimality:    {scope['economic_optimality']}",
            f"global_optimum_status:  {result['classifications']['global_optimum_status']}",
            f"p638_zone2:             {scope['p638_zone2']}",
            f"arm_c:                  {scope['arm_c']}",
            f"j4_geometry:            {scope['j4_geometry']}",
            f"monte_carlo:            {scope['monte_carlo']}",
            f"historical_draws_read:  {scope['historical_draws_read']}",
            f"native_winning_space_enumeration: {scope['native_winning_space_enumeration']}",
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
        f"sealed_phase5_result_path: {canonical_input['sealed_phase5_result_path']}",
        f"sealed_phase5_result_blob: {canonical_input['sealed_phase5_result_blob']}",
        (
            "sealed_phase5_preregistration_sha256: "
            f"{canonical_input['sealed_phase5_preregistration_sha256']}"
        ),
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
    for lottery_key, seconds in runtime["triple_geometry_computation_by_lottery"].items():
        lines.append(f"{lottery_key} triple-geometry computation: {seconds:.3f}s")
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
            "Status: SEALED | exact combinatorial S3 triple-geometry mechanism, real "
            "B649/T539/P638 Zone-1 sealed portfolios | native execution complete",
            "",
            "No historical draw is read. No Monte Carlo estimate is used. No "
            "winning-space enumeration is performed -- `S3_MULTIPLICITY` is reused "
            "read-only from the already-sealed Phase-5 result. Predictive advantage, "
            "prize-value advantage, economic optimality, P638 Zone-2, Arm-C, and "
            "`J4_GEOMETRY` are all out of scope for this study (see S8 for the full "
            "claim boundary).",
            "",
        ]
    )
    sections = [
        _render_identity_table(result),
        _render_histogram_section(result),
        _render_saturated_triple_table(result),
        _render_mass_bound_table(result),
        _render_mechanism_context_table(result),
        _render_portfolio_hash_table(result),
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
