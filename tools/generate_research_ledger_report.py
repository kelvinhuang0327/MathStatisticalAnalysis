"""Generate the human-readable ledger view from

`docs/research/cross_lottery_research_ledger_r1.json` (the source of
truth). Never hand-edit the generated markdown's content.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

LEDGER_PATH = Path("docs/research/cross_lottery_research_ledger_r1.json")
OUTPUT_PATH = Path("docs/research/cross-lottery-research-ledger-r1.md")

LOTTERY_ORDER = ("BIG_LOTTO", "DAILY_539", "POWER_LOTTO")


def _cell_lottery_columns(cells: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
    by_family: dict[str, dict[str, str]] = defaultdict(dict)
    for cell in cells:
        key = f"{cell['lottery_type']}" + (f"_{cell['zone']}" if cell["zone"] else "")
        label = cell["descriptive_classification"]
        if cell["evidence_grade"] == "REPORTED_UNVERIFIED":
            label += " (unverified)"
        by_family[cell["hypothesis_family_id"]][key] = label
    return by_family


def main() -> None:
    ledger = json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
    priors: list[dict[str, Any]] = ledger["priors"]
    cells: list[dict[str, Any]] = ledger["cells"]

    lines = [
        "# Cross-Lottery Research Ledger R1",
        "",
        f"Status: OPERATIONAL SSOT | generated {ledger['generated_at']} | "
        f"{len(priors)} priors, {len(cells)} cells",
        "",
        "Source of truth: `docs/research/cross_lottery_research_ledger_r1.json`. "
        "This file is generated from it — never hand-edited. Schema and lifecycle: "
        "`docs/research/cross-lottery-research-ledger-r1-schema.md`.",
        "",
        "## Priors (mechanism-level coverage facts)",
        "",
        "| Mechanism class | Lottery | Coverage | Detail |",
        "|---|---|---|---|",
    ]
    for prior in priors:
        lines.append(
            f"| {prior['mechanism_class']} | {prior['lottery_type']} | "
            f"`{prior['coverage']}` | {prior['detail']} |"
        )

    lines.extend(["", "## Hypothesis cells by lottery", ""])
    families_by_lottery = _cell_lottery_columns(cells)
    lines.append(
        "| Hypothesis family | BIG_LOTTO | DAILY_539 | POWER_LOTTO (z1/z2) | Next priority |"
    )
    lines.append("|---|---|---|---|---|")
    # dict.fromkeys, not a set comprehension: preserves each family's first
    # appearance order in `cells` as the tie-break for the sort below, so
    # regenerating this file twice from the same ledger is byte-identical
    # regardless of Python's per-process string-hash randomization (a set's
    # iteration order is not insertion order and is not stable across runs).
    family_order = sorted(
        dict.fromkeys(cell["hypothesis_family_id"] for cell in cells),
        key=lambda family_id: next(
            cell["next_priority"] for cell in cells if cell["hypothesis_family_id"] == family_id
        ),
    )
    priority_rank = {"HIGH": 0, "MEDIUM": 1, "LOW": 2, "NONE": 3}
    family_order.sort(
        key=lambda family_id: priority_rank.get(
            next(c["next_priority"] for c in cells if c["hypothesis_family_id"] == family_id), 9
        )
    )
    for family_id in family_order:
        columns = families_by_lottery[family_id]
        big_lotto = columns.get("BIG_LOTTO", "UNTESTED")
        daily_539 = columns.get("DAILY_539", "UNTESTED")
        z1 = columns.get("POWER_LOTTO_zone1", "UNTESTED")
        z2 = columns.get("POWER_LOTTO_zone2", "UNTESTED")
        next_priority = next(
            c["next_priority"] for c in cells if c["hypothesis_family_id"] == family_id
        )
        lines.append(
            f"| {family_id} | {big_lotto} | {daily_539} | {z1} / {z2} | {next_priority} |"
        )

    replication_queue = [c for c in cells if c["decision_state"] == "REPLICATION_REQUIRED"]
    lines.extend(["", "## Replication queue", ""])
    if replication_queue:
        lines.append(
            "Positive results awaiting a second lottery before being read as more than "
            "lottery-specific. Takes priority over starting a new discovery-queue "
            "mechanism in the same lottery."
        )
        lines.append("")
        lines.append("| Cell | Lottery | Classification | Next priority |")
        lines.append("|---|---|---|---|")
        for cell in replication_queue:
            zone_suffix = f" / {cell['zone']}" if cell["zone"] else ""
            lines.append(
                f"| `{cell['cell_id']}` | {cell['lottery_type']}{zone_suffix} | "
                f"{cell['descriptive_classification']} | {cell['next_priority']} |"
            )
    else:
        lines.append("Empty.")

    lines.extend(["", "## Full cell detail", ""])
    for cell in cells:
        zone_text = f" / {cell['zone']}" if cell["zone"] else ""
        lines.append(f"### `{cell['cell_id']}`")
        lines.append("")
        lines.append(f"- lottery: {cell['lottery_type']}{zone_text}")
        lines.append(f"- mechanism_class: {cell['mechanism_class']}")
        if cell.get("evidence_type"):
            lines.append(
                f"- evidence_type: `{cell['evidence_type']}` | uncertainty: {cell['uncertainty']}"
            )
        if cell.get("related_legacy_evidence"):
            related = ", ".join(f"`{ref}`" for ref in cell["related_legacy_evidence"])
            lines.append(f"- related_legacy_evidence (not the same design): {related}")
        lines.append(f"- record_state: `{cell['record_state']}`")
        lines.append(
            f"- preregistration_grade: `{cell['preregistration_grade']}` | "
            f"evidence_grade: `{cell['evidence_grade']}`"
        )
        lines.append(
            f"- descriptive_classification: `{cell['descriptive_classification']}` | "
            f"decision_state: `{cell['decision_state']}`"
        )
        if cell.get("global_mechanism_status"):
            lines.append(
                f"- global_mechanism_status: `{cell['global_mechanism_status']}` | "
                f"exhausted: {cell['exhausted']}"
            )
        if cell.get("predictive_advantage"):
            lines.append(
                f"- predictive_advantage: `{cell['predictive_advantage']}` | "
                f"prize_value_advantage: `{cell['prize_value_advantage']}` | "
                f"economic_optimality: `{cell['economic_optimality']}`"
            )
        if cell["primary_endpoint_value"] is not None:
            lines.append(
                f"- primary_endpoint: {cell['primary_endpoint_value']:+.6f} "
                f"({cell['primary_endpoint_definition']})"
            )
            if cell["null_replay_percentile"] is not None:
                lines.append(f"- null_replay_percentile: {cell['null_replay_percentile']:.2f}")
        if cell.get("record_state") == "DESIGN_ABANDONED":
            lines.append(
                f"- experiment_run: {cell['experiment_run']} | result: `{cell['result']}` "
                "(a deferral, not a negative finding)"
            )
            lines.append(f"- deferral_reason: {cell['deferral_reason']}")
        if cell["artifact_paths"]:
            lines.append(f"- artifacts: {', '.join(cell['artifact_paths'])}")
        lines.append(f"- retest_eligible: {cell['retest_eligible']}")
        lines.append(f"- source: {cell['source_note']}")
        lines.append("")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    serialized = "\n".join(lines).rstrip("\n") + "\n"
    OUTPUT_PATH.write_text(serialized, encoding="utf-8")
    print(f"wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
