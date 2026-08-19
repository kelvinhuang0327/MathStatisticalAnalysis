"""Render the concise Phase-7 B649 report from the locked result JSON."""

from __future__ import annotations

import json
from pathlib import Path

RESULT_PATH = Path(
    "docs/research/matrix-native-results/constructor-frontier-next-generation-v1-result.json"
)
OUTPUT_PATH = Path(
    "docs/research/matrix-native-results/constructor-frontier-next-generation-v1-report.md"
)


def _exact(node: dict[str, object] | None) -> str:
    if node is None:
        return "NOT_APPLICABLE"
    return str(node["exact"])


def _float(node: dict[str, object] | None) -> str:
    if node is None:
        return "NOT_APPLICABLE"
    value = node["exact"]
    from fractions import Fraction

    return f"{float(Fraction(str(value))):.8f}"


def main() -> None:
    result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    gate = result["b649_advance_gate"]
    rows: list[str] = []
    geom_rows: list[str] = []
    for k in result["exposure_ladder"]:
        cell = result["per_k"][str(k)]
        rows.append(
            "| {k} | {qe} | {qb} | {qd} | {qc} | {deb} | {cap} | {gap} |".format(
                k=k,
                qe=_exact(cell["q_e"]),
                qb=_exact(cell["q_b"]),
                qd=_exact(cell["q_d"]),
                qc=_exact(cell["q_c_sealed"]),
                deb=_exact(cell["delta_e_vs_b"]),
                cap=_exact(cell["frontier_capture_ratio_e"]),
                gap=_exact(cell["b_to_c_gap_capture"]),
            )
        )
        geom = cell["geometry"]["e"]
        geom_rows.append(
            "| {k} | {mx} | {mean} | {n1} | {s2} | {uniq} | {disp:.6f} | {dup} |".format(
                k=k,
                mx=geom["max_pairwise_overlap"],
                mean=_exact(geom["mean_pairwise_overlap"]),
                n1=geom["overlap_one_pair_count"],
                s2=geom["s2_geometry"],
                uniq=geom["unique_number_coverage"],
                disp=float(geom["reuse_dispersion_float"]),
                dup=geom["duplicate_count"],
            )
        )
    float_rows: list[str] = []
    for k in result["exposure_ladder"]:
        cell = result["per_k"][str(k)]
        float_rows.append(
            "| {k} | {qe} | {qb} | {qd} | {qc} | {deb} | {cap} | {gap} |".format(
                k=k,
                qe=_float(cell["q_e"]),
                qb=_float(cell["q_b"]),
                qd=_float(cell["q_d"]),
                qc=_float(cell["q_c_sealed"]),
                deb=_float(cell["delta_e_vs_b"]),
                cap=_float(cell["frontier_capture_ratio_e"]),
                gap=_float(cell["b_to_c_gap_capture"]),
            )
        )
    clauses = "\n".join(
        f"- `{name}`: {str(value).upper()}" for name, value in sorted(gate["clauses"].items())
    )
    gate_status = "PASS" if gate["passed"] else "FAIL"
    replication = "YES" if result["cross_lottery_replication_eligible"] else "NO"
    report = f"""# STRATEGY_MATRIX_PHASE7_CONSTRUCTOR_FRONTIER_NEXT_GENERATION_V1 — result

Status: SEALED -- `{result["execution_classification"]}` -- 2026-08-17 --
B649 only

Preregistration hash:
`{result["canonical_input"]["locked_preregistration_sha256"]}`.
Arm-C was not rerun. T539 and P638 were not executed.

## Identity

```text
STUDY_ID: {result["study_id"]}
CONSTRUCTOR: {result["constructor_id"]}
LOTTERY: {result["lottery_type"]}
PRIMARY_EVENT: M3_PLUS
GLOBAL_OPTIMUM_STATUS: {result["global_optimum_status"]}
ARM_C_RERUN: {result["arm_c_rerun"]}
T539_EXECUTION: {result["t539_execution"]}
P638_EXECUTION: {result["p638_execution"]}
PARAMETER_RESCUE_RUN: {result["parameter_rescue_run"]}
```

## Exact primary coverages

| k | Q_E | Q_B | Q_D | Q_C_SEALED | Q_E-Q_B | FRONTIER_CAPTURE | B_TO_C_GAP_CAPTURE |
|---:|---|---|---|---|---|---|---|
{chr(10).join(rows)}

Approximate floats, presentation only:

| k | Q_E | Q_B | Q_D | Q_C_SEALED | Q_E-Q_B | FRONTIER_CAPTURE | B_TO_C_GAP_CAPTURE |
|---:|---:|---:|---:|---:|---:|---:|---:|
{chr(10).join(float_rows)}

## Candidate geometry

| k | max | mean | n_{{r=1}} | S2 | unique | reuse disp. | dup |
|---:|---:|---|---:|---:|---:|---:|---:|
{chr(10).join(geom_rows)}

## B649 advance gate

```text
B649_ADVANCE_GATE: {gate_status}
EXECUTION_CLASSIFICATION: {result["execution_classification"]}
CROSS_LOTTERY_REPLICATION_ELIGIBLE: {replication}
```

{clauses}

## Runtime

```text
arm_a_seconds: {result["runtime"]["arm_a_seconds"]}
arm_b_seconds: {result["runtime"]["arm_b_seconds"]}
arm_e_seconds: {result["runtime"]["arm_e_seconds"]}
winning_space_seconds: {result["runtime"]["winning_space_seconds"]}
total_seconds: {result["runtime"]["total_seconds"]}
peak_memory_bytes: {result["runtime"]["peak_memory_bytes"]}
```

## Claim boundary

This cell supports exact deterministic B649 combinatorial
coverage/frontier evidence for this constructor variant only. It does
not prove global optimality, predictive advantage, profitability,
prize/economic value, or cross-lottery replication.

```text
MONTE_CARLO: NONE
HISTORICAL_DRAWS: NOT_USED
ARM_C_RERUN: NO
T539_EXECUTION: NOT_RUN
P638_EXECUTION: NOT_RUN
PARAMETER_RESCUE_RUN: NO
GLOBAL_OPTIMUM_STATUS: UNKNOWN
```
"""
    OUTPUT_PATH.write_text(report, encoding="utf-8")
    print(f"wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
