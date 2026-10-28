from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest
from tools.b649_k235_historical_report_bridge_r1 import main

from lottolab.research.b649_k235_cutoff_rank_refresh_r1 import refresh_from_files
from lottolab.research.b649_k235_historical_report_bridge_r1 import (
    HistoricalBridgeInputError,
    build_historical_report,
)


def _sources(tmp_path: Path, count: int = 60) -> tuple[Path, Path]:
    rank = tmp_path / "rank.json"
    evidence = tmp_path / "evidence.jsonl"
    rank.write_text(
        json.dumps(
            {
                "ids": {"a": [2, "A"], "b": [2, "B"], "c": [3, "C"]},
                "cutoffs": [str(i) for i in range(1, count + 1)],
                "hist": {},
            }
        )
    )
    rows: list[dict[str, Any]] = []
    for i in range(1, count + 1):
        for sid, k in (("a", 2), ("b", 2), ("c", 3)):
            if sid == "b" and i == count:
                continue
            tickets = [list(range(1 + j * 6, 7 + j * 6)) for j in range(k)]
            if sid == "b":
                tickets = [list(range(20 + j * 6, 26 + j * 6)) for j in range(k)]
            if sid == "a" and i == count:
                tickets = [[1, 2, 7, 20, 21, 22], [22, 23, 24, 25, 26, 27]]
            state = "COMPLETE"
            if sid == "a" and i == count - 1:
                state = "WINDOW_INELIGIBLE_INCOMPLETE_OBSERVATIONS"
            if sid == "b" and i == count - 2:
                state = "EXECUTION_FAILURE"
            rows.append(
                {
                    "strategy_id": sid,
                    "native_ticket_count": k,
                    "actual_native_ticket_count": k if state == "COMPLETE" else None,
                    "target_draw_number": str(i),
                    "target_draw_date": (date(2020, 1, 1) + timedelta(days=i)).isoformat(),
                    "actual_main_numbers": [1, 2, 3, 4, 5, 6],
                    "actual_special_number": 7,
                    "native_portfolio": tickets if state == "COMPLETE" else None,
                    "target_outcome_excluded": True,
                    "causal_cutoff_draw_number": str(i - 1) if i > 1 else None,
                    "replay_status": state,
                    "official_any_prize": sid != "b" if state == "COMPLETE" else None,
                }
            )
    evidence.write_text("".join(json.dumps(row) + "\n" for row in rows))
    return rank, evidence


def _report(rank: Path, evidence: Path, cutoff: str = "60") -> dict[str, Any]:
    return build_historical_report(
        rank_history_path=rank,
        replay_paths=[evidence],
        cutoff_draw=cutoff,
        evidence_kind="SYNTHETIC",
    )


def test_composition_preserves_c_native_identity_windows_and_missingness(tmp_path: Path) -> None:
    rank, evidence = _sources(tmp_path, 1601)
    report = _report(rank, evidence, "1601")
    original = refresh_from_files(
        rank_history_path=rank, replay_paths=[evidence], cutoff_draw="1601"
    )
    assert report["ranking"] == json.loads(json.dumps(original))
    assert report["validation"]["native_strategy_report_count"] == 3
    assert report["validation"]["official_outcome_crosscheck_count"] == 4800
    rows = {(r["strategy_id"], r["window"]): r for r in report["window_metrics"]}
    for window, size in (("50", 50), ("300", 300), ("750", 750), ("1500", 1500), ("FULL", 1601)):
        a = rows["a", window]
        b = rows["b", window]
        assert (a["denominator"], a["official_any_prize_success_count"]) == (size - 1, size - 1)
        assert (b["denominator"], b["missing_period_count"], b["failed_period_count"]) == (
            size - 2,
            1,
            1,
        )
        assert a["supplementary"]["M3_PLUS"]["success_count"] == size - 2
        assert a["supplementary"]["EXPECTED_MAX_MAIN_MATCHES"]["value"] is None
        assert a["evidence_kind"] == "SYNTHETIC"
        assert a["statistical_result"]["method"] == "POISSON_BINOMIAL_DP_FLOAT64"
        assert a["state_counts"] == {"OBSERVED": 0, "SYNTHETIC": size - 1, "MISSING": 1}
    stats = report["statistical_results"]
    assert stats["candidate_count"] == 3
    assert stats["hypothesis_count"] == 15
    assert stats["paired_hypothesis_count"] == 5
    assert stats["independence_status"] == "REUSED_SELECTION_HISTORY_NOT_INDEPENDENT"
    assert not stats["independent_holdout_claim_is_verified"]
    full_pair = next(r for r in stats["paired_results"] if r["window"] == "FULL")
    assert full_pair["common_evaluable_period_count"] == 1598
    for row in stats["candidate_results"]:
        assert row["holm_adjusted_p_value"] >= row["one_sided_p_value"]
        assert row["bonferroni_adjusted_p_value"] == min(1.0, row["one_sided_p_value"] * 15)


@pytest.mark.parametrize(
    "field,value,match",
    [
        ("actual_special_number", 1, "invalid actual draw"),
        ("official_any_prize", False, "official prize conflict"),
        ("native_portfolio", None, "missing exact native portfolio"),
    ],
)
def test_bridge_rejects_prize_conflicts_and_missing_native_evidence(
    tmp_path: Path,
    field: str,
    value: Any,
    match: str,
) -> None:
    rank, evidence = _sources(tmp_path)
    rows = [json.loads(line) for line in evidence.read_text().splitlines()]
    rows[0][field] = value
    evidence.write_text("".join(json.dumps(row) + "\n" for row in rows))
    with pytest.raises(HistoricalBridgeInputError, match=match):
        _report(rank, evidence)


def test_observed_requires_saved_ranking_and_saved_ranking_cannot_be_rewritten(
    tmp_path: Path,
) -> None:
    rank, evidence = _sources(tmp_path)
    with pytest.raises(HistoricalBridgeInputError, match="OBSERVED requires"):
        build_historical_report(
            rank_history_path=rank,
            replay_paths=[evidence],
            cutoff_draw="60",
            evidence_kind="OBSERVED",
        )
    saved = refresh_from_files(rank_history_path=rank, replay_paths=[evidence], cutoff_draw="60")
    saved["strategies"][0]["windows"]["FULL"]["success_count"] += 1
    snapshot = tmp_path / "snapshot.json"
    snapshot.write_text(json.dumps(saved))
    with pytest.raises(HistoricalBridgeInputError, match="saved C ranking mismatch"):
        build_historical_report(
            rank_history_path=rank,
            replay_paths=[evidence],
            cutoff_draw="60",
            evidence_kind="SYNTHETIC",
            saved_ranking_path=snapshot,
        )


def test_cli_and_absent_cutoff_are_explicitly_missing(tmp_path: Path) -> None:
    rank, evidence = _sources(tmp_path)
    output = tmp_path / "report.json"
    assert (
        main(
            [
                "--rank-history",
                str(rank),
                "--evidence",
                str(evidence),
                "--cutoff",
                "60",
                "--evidence-kind",
                "SYNTHETIC",
                "--output",
                str(output),
            ]
        )
        == 0
    )
    assert json.loads(output.read_text())["evidence_kind"] == "SYNTHETIC"
    missing = _report(rank, evidence, "115000099")
    assert missing["status"] == "MISSING"
    assert missing["window_metrics"] == []
    assert missing["statistical_results"] is None
    assert missing["cutoff"]["actual_cutoff_applied"] is None


def test_no_common_targets_do_not_get_a_paired_p_value(tmp_path: Path) -> None:
    rank, evidence = _sources(tmp_path, 2)
    rows = [json.loads(line) for line in evidence.read_text().splitlines()]
    # A is ineligible on target 1; B is missing on target 2.
    assert any(r["strategy_id"] == "b" and r["target_draw_number"] == "1" for r in rows)
    report = _report(rank, evidence, "2")
    for pair in report["statistical_results"]["paired_results"]:
        assert pair["common_evaluable_period_count"] == 0
        assert pair["mcnemar_exact_two_sided_p_value"] is None
        assert pair["holm_adjusted_p_value"] is None
        assert pair["status"] == "MISSING_NO_COMMON_TARGETS"
