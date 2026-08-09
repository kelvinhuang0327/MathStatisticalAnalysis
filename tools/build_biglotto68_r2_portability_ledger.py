"""Build the machine-readable BIGLOTTO68 R2 dual-target ledger."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Literal, Protocol, TypedDict, cast

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.daily539_biglotto_portable import (
    DAILY539_BIGLOTTO_PORTABLE_SPECS,
)
from lottolab.strategies.adapters.powerlotto_wave3 import WAVE3_STRATEGIES
from lottolab.strategies.adapters.powerlotto_wave4 import WAVE4_STRATEGIES
from lottolab.strategies.adapters.powerlotto_wave5 import WAVE5_STRATEGIES
from lottolab.strategies.adapters.powerlotto_wave6 import WAVE6_STRATEGIES
from lottolab.strategies.catalog import production_catalog
from tools.run_daily539_t539_wave1 import (
    BIGLOTTO68_TO_T539_CROSS_LOTTERY_R2_STRATEGY_SPECS,
)

RUNTIME_ROOT = Path(
    "/Users/kelvin/VibeCoding-WorkSpace/.runs/MathStatisticalAnalysis/"
    "BIGLOTTO68_CROSSLOTTERY_EXHAUSTIVE_CLOSURE_R2"
)
R1_LEDGER = Path(
    "/Users/kelvin/VibeCoding-WorkSpace/.runs/MathStatisticalAnalysis/"
    "BIGLOTTO_TO_P638_CROSS_LOTTERY_STRATEGY_BATCH_MIGRATION_R1/portability_ledger.md"
)

_CLASS_NAMES = {
    "PD": "PORTABLE_DIRECT",
    "PG": "PORTABLE_WITH_GAMESPEC",
    "A": "DUPLICATE_OR_ALIAS",
    "BR": "SOURCE_LOTTERY_RULE_DEPENDENT",
    "B": "BLOCKED_DEPENDENCY_OR_NONDETERMINISM",
}

_BATCH15_ROWS = {
    "legacy_biglotto__cold_hunter_predict__9e89f2b41add": (
        "power_biglotto_cold_hunter_1bet",
        "t539_biglotto_cold_hunter_1bet",
    ),
    "legacy_biglotto__short_window_deviation_predict__9e89f2b41add": (
        "power_biglotto_short_window_deviation_1bet",
        "t539_biglotto_short_window_deviation_1bet",
    ),
    "legacy_biglotto__rebound_aware_predict__9e89f2b41add": (
        "power_biglotto_rebound_aware_1bet",
        "t539_biglotto_rebound_aware_1bet",
    ),
    "legacy_biglotto__zone_momentum_predict__9e89f2b41add": (
        "power_biglotto_zone_momentum_1bet",
        "t539_biglotto_zone_momentum_1bet",
    ),
    "legacy_biglotto__pure_cold_predict__9e89f2b41add": (
        "power_biglotto_pure_cold_1bet",
        "t539_biglotto_pure_cold_1bet",
    ),
    "legacy_biglotto__moderate_rank_predict__9e89f2b41add": (
        "power_biglotto_moderate_rank_1bet",
        "t539_biglotto_moderate_rank_1bet",
    ),
    "legacy_biglotto__gap_pressure_scorer__5e862ef27ee6": (
        "power_biglotto_gap_pressure_1bet",
        "t539_biglotto_gap_pressure_1bet",
    ),
    "legacy_biglotto__test_dm_dms_biglotto__bad71858012d": (
        "power_biglotto_dm_dms_2bet",
        "t539_biglotto_dm_dms_2bet",
    ),
    "legacy_biglotto__test_dms_biglotto__10e39919c3a1": (
        "power_biglotto_dms_1bet",
        "t539_biglotto_dms_1bet",
    ),
}

_ALIAS_TARGETS = {
    "biglotto_zone_split_3bet_bet2": "biglotto_zone_split_3bet_bet1",
    "biglotto_zone_split_3bet_bet3": "biglotto_zone_split_3bet_bet1",
    "biglotto_deviation_2bet_bet2": "biglotto_deviation_2bet",
    "biglotto_p0_2bet_bet2": "biglotto_p0_2bet_bet1",
}


class _StrategySpec(Protocol):
    strategy_id: str
    strategy_version: str
    native_ticket_count: int
    min_history: int


class _TargetPayload(TypedDict):
    disposition: str
    target_strategy_id: str | None
    adaptation_mode: str
    native_ticket_count: int | None
    min_history: int | None
    reason_evidence: str
    evidence_mode: str
    alias_of_source_strategy_id: str | None


_R1Row = TypedDict(
    "_R1Row",
    {
        "source_order": int,
        "class": str,
        "target_strategy_id": str | None,
        "reason_evidence": str,
        "native_ticket_count": int | None,
        "min_history": int | None,
    },
)


class _LedgerRow(TypedDict):
    source_order: int
    source_strategy_id: str
    source_strategy_name: str
    source_version: str
    source_adapter_path: str | None
    source_native_ticket_count: int
    source_min_history: int | None
    source_provenance: list[str]
    p638: _TargetPayload
    t539: _TargetPayload


def _clean(value: str) -> str:
    return value.strip().strip("`")


def _parse_r1_rows() -> dict[str, _R1Row]:
    rows: dict[str, _R1Row] = {}
    pattern = re.compile(
        r"^\|\s*(\d+)\s*\|\s*`([^`]+)`\s*\|\s*([^|]+)\|\s*(.*?)\s*\|\s*([^|]+)\|\s*([^|]+)\|$"
    )
    for line in R1_LEDGER.read_text(encoding="utf-8").splitlines():
        match = pattern.match(line)
        if match is None:
            continue
        _, source_id, raw_class, raw_target, raw_count, raw_min = match.groups()
        # The target cell is either exactly one backtick-wrapped strategy ID or
        # a prose disposition.  Do not search the prose for backtick fragments:
        # blocked reasons legitimately quote donor slices such as ``[8:14]``.
        target_match = re.fullmatch(r"\s*`([A-Za-z0-9_]+)`\s*", raw_target)
        rows[source_id] = {
            "source_order": int(match.group(1)),
            "class": _CLASS_NAMES[_clean(raw_class)],
            "target_strategy_id": target_match.group(1) if target_match else None,
            "reason_evidence": re.sub(r"\s+", " ", raw_target).strip(),
            "native_ticket_count": None if "—" in raw_count else int(raw_count.strip()),
            "min_history": None if "—" in raw_min else int(raw_min.strip()),
        }
    if len(rows) != 59:
        raise RuntimeError(f"expected 59 reused R1 rows, found {len(rows)}")
    return rows


def _target_payload(
    *,
    disposition: str,
    target_strategy_id: str | None,
    native_ticket_count: int | None,
    min_history: int | None,
    adaptation_mode: str,
    reason_evidence: str,
    evidence_mode: str,
    alias_of: str | None = None,
) -> _TargetPayload:
    return {
        "disposition": disposition,
        "target_strategy_id": target_strategy_id,
        "adaptation_mode": adaptation_mode,
        "native_ticket_count": native_ticket_count,
        "min_history": min_history,
        "reason_evidence": reason_evidence,
        "evidence_mode": evidence_mode,
        "alias_of_source_strategy_id": alias_of,
    }


def main() -> None:
    r1_rows = _parse_r1_rows()
    catalog_rows = production_catalog().list(lottery_type=LotteryType.BIG_LOTTO)
    if len(catalog_rows) != 68:
        raise RuntimeError(f"expected 68 live BIG_LOTTO rows, found {len(catalog_rows)}")
    p638_specs: dict[str, _StrategySpec] = {
        cast(_StrategySpec, spec).strategy_id: cast(_StrategySpec, spec)
        for spec in (*WAVE3_STRATEGIES, *WAVE4_STRATEGIES, *WAVE5_STRATEGIES, *WAVE6_STRATEGIES)
    }
    t539_specs: dict[str, _StrategySpec] = {
        cast(_StrategySpec, spec).strategy_id: cast(_StrategySpec, spec)
        for spec in BIGLOTTO68_TO_T539_CROSS_LOTTERY_R2_STRATEGY_SPECS
    }
    portable_specs = {spec.source_strategy_id: spec for spec in DAILY539_BIGLOTTO_PORTABLE_SPECS}
    rows: list[_LedgerRow] = []
    for source in catalog_rows:
        source_id = source.strategy_id
        p638_info = r1_rows.get(source_id)
        if p638_info is None:
            p638_target_id, t539_target_id = _BATCH15_ROWS[source_id]
            p638_spec = p638_specs[p638_target_id]
            t539_spec = next(
                spec for spec in t539_specs.values() if spec.strategy_id == t539_target_id
            )
            p638_target = _target_payload(
                disposition="PORTABLE_WITH_GAMESPEC",
                target_strategy_id=p638_target_id,
                native_ticket_count=p638_spec.native_ticket_count,
                min_history=p638_spec.min_history,
                adaptation_mode="GAMESPEC_PARAMETERIZED_SHARED_BATCH15_CORE",
                reason_evidence=(
                    "Reused the accepted Wave6 Batch15 mapping and verified the nine "
                    "current P638 identities."
                ),
                evidence_mode="REUSED_MAIN_BATCH15_VERIFIED_EVIDENCE",
            )
            t539_target = _target_payload(
                disposition="ALREADY_EQUIVALENT_IN_TARGET",
                target_strategy_id=t539_target_id,
                native_ticket_count=t539_spec.native_ticket_count,
                min_history=t539_spec.min_history,
                adaptation_mode="REUSED_TARGET_NATIVE_BATCH15_ADAPTER",
                reason_evidence=(
                    "The current main tree already contains this target-native DAILY_539 identity."
                ),
                evidence_mode="REUSED_MAIN_BATCH15_VERIFIED_EVIDENCE",
            )
        else:
            p638_target_id = p638_info["target_strategy_id"]
            p638_spec = p638_specs.get(p638_target_id) if p638_target_id else None
            p638_count = p638_spec.native_ticket_count if p638_spec else None
            p638_min = p638_spec.min_history if p638_spec else None
            p638_target = _target_payload(
                disposition=p638_info["class"],
                target_strategy_id=p638_target_id,
                native_ticket_count=p638_count,
                min_history=p638_min,
                adaptation_mode=(
                    "REUSED_MERGED_P638_MAPPING"
                    if p638_info["class"] in {"PORTABLE_DIRECT", "PORTABLE_WITH_GAMESPEC"}
                    else "NO_TARGET_ADAPTER"
                ),
                reason_evidence=str(p638_info["reason_evidence"]),
                evidence_mode="REUSED_PR109_MERGED_EVIDENCE",
                alias_of=_ALIAS_TARGETS.get(source_id),
            )
            portable_spec = portable_specs.get(source_id)
            if portable_spec is not None:
                t539_spec = t539_specs[portable_spec.strategy_id]
                t539_target = _target_payload(
                    disposition=p638_info["class"],
                    target_strategy_id=portable_spec.strategy_id,
                    native_ticket_count=t539_spec.native_ticket_count,
                    min_history=t539_spec.min_history,
                    adaptation_mode="GAMESPEC_PARAMETERIZED_SHARED_PORTABLE_CORE",
                    reason_evidence=(
                        "R2 target-native 5-of-39 adapter added and exhaustively "
                        "shape-verified before replay."
                    ),
                    evidence_mode="NEWLY_VERIFIED_R2_EVIDENCE",
                )
            elif source_id in _ALIAS_TARGETS:
                canonical_source = _ALIAS_TARGETS[source_id]
                canonical_port = portable_specs[canonical_source]
                canonical_t539 = t539_specs[canonical_port.strategy_id]
                t539_target = _target_payload(
                    disposition="DUPLICATE_OR_ALIAS",
                    target_strategy_id=canonical_port.strategy_id,
                    native_ticket_count=canonical_t539.native_ticket_count,
                    min_history=canonical_t539.min_history,
                    adaptation_mode="COLLAPSED_EXACT_ALIAS",
                    reason_evidence=(
                        "Exact source position alias collapsed into the canonical "
                        "native target portfolio."
                    ),
                    evidence_mode="NEWLY_VERIFIED_R2_EVIDENCE",
                    alias_of=canonical_source,
                )
            else:
                t539_target = _target_payload(
                    disposition=p638_info["class"],
                    target_strategy_id=None,
                    native_ticket_count=None,
                    min_history=None,
                    adaptation_mode="NO_TARGET_ADAPTER",
                    reason_evidence=str(p638_info["reason_evidence"]),
                    evidence_mode="REUSED_MERGED_EVIDENCE_WITH_T539_RULE_REVIEW",
                )
        rows.append(
            {
                "source_order": len(rows) + 1,
                "source_strategy_id": source_id,
                "source_strategy_name": source.strategy_name,
                "source_version": source.version,
                "source_adapter_path": source.adapter_path,
                "source_native_ticket_count": source.native_ticket_count,
                "source_min_history": source.min_history,
                "source_provenance": list(source.provenance),
                "p638": p638_target,
                "t539": t539_target,
            }
        )

    def counts(target: Literal["p638", "t539"]) -> dict[str, int]:
        values = {
            "ALREADY_EQUIVALENT_IN_TARGET": 0,
            **{name: 0 for name in _CLASS_NAMES.values()},
        }
        for row in rows:
            values[row[target]["disposition"]] += 1
        return values

    payload = {
        "task_id": "BIGLOTTO68_CROSSLOTTERY_EXHAUSTIVE_CLOSURE_R2",
        "source_commit": "b2ce6a3daaef4925a8e3f15d93a883d173882714",
        "source_universe": {
            "lottery_type": "BIG_LOTTO",
            "count": len(rows),
            "definition": "production_catalog().list(lottery_type=BIG_LOTTO)",
        },
        "target_contracts": {
            "P638": {"pool": [1, 38], "pick_count": 6, "second_zone": [1, 8]},
            "T539": {"pool": [1, 39], "pick_count": 5, "second_zone": None},
        },
        "reused_evidence": {
            "p638_ledger": str(R1_LEDGER),
            "p638_current_strategy_count_at_entry": 70,
            "t539_entry_strategy_count": 24,
            "batch15_mapping_count": len(_BATCH15_ROWS),
        },
        "counts": {"p638": counts("p638"), "t539": counts("t539")},
        "rows": rows,
        "newly_migrated": {
            "p638": [
                row["p638"]["target_strategy_id"]
                for row in rows
                if row["p638"]["evidence_mode"] == "NEWLY_VERIFIED_R2_EVIDENCE"
            ],
            "t539": [
                row["t539"]["target_strategy_id"]
                for row in rows
                if row["t539"]["evidence_mode"] == "NEWLY_VERIFIED_R2_EVIDENCE"
                and row["t539"]["disposition"]
                in {
                    "PORTABLE_DIRECT",
                    "PORTABLE_WITH_GAMESPEC",
                }
            ],
        },
    }
    RUNTIME_ROOT.mkdir(parents=True, exist_ok=True)
    (RUNTIME_ROOT / "portability_ledger.json").write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {"rows": len(rows), "p638": counts("p638"), "t539": counts("t539")}, sort_keys=True
        )
    )


if __name__ == "__main__":
    main()
