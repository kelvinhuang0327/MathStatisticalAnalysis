"""Render the concise Phase-7 T539 replication report from the locked result."""

from __future__ import annotations

import json
from fractions import Fraction
from pathlib import Path

RESULT_PATH = Path(
    "docs/research/matrix-native-results/"
    "constructor-frontier-next-generation-t539-v1-result.json"
)
OUTPUT_PATH = Path(
    "docs/research/matrix-native-results/constructor-frontier-next-generation-t539-v1-report.md"
)


def _exact(node: dict[str, object] | None) -> str:
    if node is None:
        return "NOT_APPLICABLE"
    return str(node["exact"])


def _float(node: dict[str, object] | None) -> str:
    if node is None:
        return "NOT_APPLICABLE"
    return f"{float(Fraction(str(node['exact']))):.8f}"


def main() -> None:
    result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    gate = result["t539_replication_gate"]
    rows: list[str] = []
    float_rows: list[str] = []
    geom_rows: list[str] = []
    for k in result["exposure_ladder"]:
        cell = result["per_k"][str(k)]
        rows.append(
            "| {k} | {qe} | {qb} | {qa} | {qd} | {deb} | {ded} |".format(
                k=k,
                qe=_exact(cell["q_e"]),
                qb=_exact(cell["q_b"]),
                qa=_exact(cell["q_a"]),
                qd=_exact(cell["q_d"]),
                deb=_exact(cell["delta_e_vs_b"]),
                ded=_exact(cell["delta_e_vs_d"]),
            )
        )
        float_rows.append(
            "| {k} | {qe} | {qb} | {qa} | {qd} | {deb} | {ded} |".format(
                k=k,
                qe=_float(cell["q_e"]),
                qb=_float(cell["q_b"]),
                qa=_float(cell["q_a"]),
                qd=_float(cell["q_d"]),
                deb=_float(cell["delta_e_vs_b"]),
                ded=_float(cell["delta_e_vs_d"]),
            )
        )
        geom = cell["geometry"]["e"]
        geom_rows.append(
            "| {k} | {mx} | {mean} | {n1} | {s2} | {uniq} | {disp:.6f} | {dup} | {sm} |".format(
                k=k,
                mx=geom["max_pairwise_overlap"],
                mean=_exact(geom["mean_pairwise_overlap"]),
                n1=geom["overlap_one_pair_count"],
                s2=geom["s2_geometry"],
                uniq=geom["unique_number_coverage"],
                disp=float(geom["reuse_dispersion_float"]),
                dup=geom["duplicate_count"],
                sm=geom["sum_pairwise_overlap"],
            )
        )
    clauses = "\n".join(
        f"- `{name}`: {str(value).upper()}" for name, value in sorted(gate["clauses"].items())
    )
    gate_status = "PASS" if gate["passed"] else "FAIL"
    eligible = "YES" if result["p638_replication_eligible"] else "NO"
    report = f"""# STRATEGY_MATRIX_PHASE7_T539_NEXT_GEN_CONSTRUCTOR_REPLICATION_V1 — result

Status: SEALED -- `{result["execution_classification"]}` -- 2026-08-17 --
T539 only

Preregistration hash:
`{result["canonical_input"]["locked_preregistration_sha256"]}`.
B649 was not rerun. Arm-C was not manufactured. P638 was not executed.

## Identity

```text
STUDY_ID: {result["study_id"]}
CONSTRUCTOR: {result["constructor_id"]}
LOTTERY: {result["lottery_type"]}
PRIMARY_EVENT: M3+
GLOBAL_OPTIMUM_STATUS: {result["global_optimum_status"]}
B649_RERUN: {result["b649_rerun"]}
ARM_C_RERUN: {result["arm_c_rerun"]}
P638_EXECUTION: {result["p638_execution"]}
PARAMETER_RESCUE_RUN: {result["parameter_rescue_run"]}
```

## Exact primary coverages

| k | Q_E | Q_B | Q_A | Q_D | Q_E-Q_B | Q_E-Q_D |
|---:|---|---|---|---|---|---|
{chr(10).join(rows)}

Approximate floats, presentation only:

| k | Q_E | Q_B | Q_A | Q_D | Q_E-Q_B | Q_E-Q_D |
|---:|---:|---:|---:|---:|---:|---:|
{chr(10).join(float_rows)}

## Candidate geometry

| k | max | mean | n_{{r=1}} | S2 | unique | reuse disp. | dup | sum |
|---:|---:|---|---:|---:|---:|---:|---:|---:|
{chr(10).join(geom_rows)}

## T539 replication gate

```text
T539_REPLICATION_GATE: {gate_status}
T539_REPLICATION_STATUS: {result["t539_replication_status"]}
P638_REPLICATION_ELIGIBLE: {eligible}
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

This cell supports exact deterministic T539 combinatorial replication
evidence for this constructor variant only. It does not prove global
optimality, predictive advantage, profitability, prize/economic value,
P638 replication, or universal portability.

```text
MONTE_CARLO: NONE
HISTORICAL_DRAWS: NOT_USED
B649_RERUN: NO
ARM_C_RERUN: NO
P638_EXECUTION: NOT_RUN
PARAMETER_RESCUE_RUN: NO
GLOBAL_OPTIMUM_STATUS: UNKNOWN
```
"""
    OUTPUT_PATH.write_text(report, encoding="utf-8")
    print(f"wrote {OUTPUT_PATH}")
    print(f"t539_replication_status={result['t539_replication_status']}")
    print(f"p638_replication_eligible={eligible}")


if __name__ == "__main__":
    main()
