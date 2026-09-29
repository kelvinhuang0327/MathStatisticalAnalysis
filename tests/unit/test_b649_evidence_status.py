"""Existing-evidence-first discovery, stale-vs-absent semantics and README live index."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import tools.b649_evidence_status as ev

REAL_README = ev.README_PATH


def _exact(sid: str, k: int, rate: str, window: str = "FULL") -> dict[str, object]:
    return {
        "strategy_id": sid,
        "ticket_count": k,
        "window": window,
        "rankable": True,
        "official_any_prize_rate": rate,
        "official_random_baseline_delta": "0.0",
        "coverage": "0.9",
    }


def _write_multi(
    data_dir: Path,
    *,
    cutoff: str,
    ticket_counts: list[int],
    gaps: list[str] | None = None,
) -> Path:
    doc: dict[str, object] = {
        "projection_schema_version": "FIXTURE_V3",
        "exact_native_backtest_policy_version": "FIXTURE_EXACT_2_3",
        "dataset": {"cutoff_draw_number": cutoff},
        "ticket_counts": ticket_counts,
        "records": [{"strategy_id": "a", "combinations": {}}],
        "exact_native_records": [
            _exact(sid, k, rate)
            for k in ticket_counts
            for sid, rate in (("s_low", "0.10"), ("s_high", "0.30"), ("s_mid", "0.20"))
        ],
    }
    if gaps is not None:
        doc["known_gap_draws"] = gaps
    path = data_dir / "biglotto_multi_ticket_historical_records_v2.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    return path


@pytest.fixture
def roots(tmp_path: Path) -> tuple[Path, Path]:
    data = tmp_path / "src" / "data"
    research = tmp_path / "docs" / "research"
    data.mkdir(parents=True)
    research.mkdir(parents=True)
    return data, research


def _discover(
    roots: tuple[Path, Path], *, readme_text: str = "", latest_draw: str | None = None
) -> ev.EvidenceReport:
    data, research = roots
    return ev.discover(
        data_dir=data,
        research_dir=research,
        repo_root=data.parents[1],
        readme_text=readme_text,
        latest_draw=latest_draw,
        ticket_counts=(2, 3),
    )


def _family(report: ev.EvidenceReport, k: int) -> ev.FamilyStatus:
    return next(f for f in report.families if f.ticket_count == k)


# 1 / Case B — README silence never means absence
def test_readme_missing_ticket_count_does_not_imply_absent(roots: tuple[Path, Path]) -> None:
    _write_multi(roots[0], cutoff="115000084", ticket_counts=[2, 3])
    readme = "只提供 5\uff0f10\uff0f15\uff0f20 注紀錄"
    report = _discover(roots, readme_text=readme, latest_draw="115000084")
    for k in (2, 3):
        fam = _family(report, k)
        assert fam.readme_mentions_ticket_count is False
        assert fam.status is ev.EvidenceStatus.AVAILABLE_CURRENT
        assert fam.ranking_available is True
    assert report.readme_discovery_complete is False


# 2 + 4 / Case A — stale is not absent; missing draws are deterministic
def test_stale_evidence_with_gap_is_available_stale(roots: tuple[Path, Path]) -> None:
    _write_multi(roots[0], cutoff="115000082", ticket_counts=[2, 3], gaps=["115000081"])
    report = _discover(roots, latest_draw="115000091")
    expected = ("115000081", *(f"1150000{n:02d}" for n in range(83, 92)))
    for k in (2, 3):
        fam = _family(report, k)
        assert fam.status is ev.EvidenceStatus.AVAILABLE_STALE
        assert fam.status is not ev.EvidenceStatus.ABSENT
        assert fam.data_cutoff == "115000082"
        assert fam.known_missing_draws == expected
        assert fam.refresh.historical_ranking_available is True
        assert fam.refresh.mode is ev.RefreshMode.DELTA_REFRESH
        assert fam.refresh.full_rerun_reason is None
        assert fam.refresh.refresh_required_for_validity is False
    again = _discover(roots, latest_draw="115000091")
    assert again == report


def test_missing_draws_across_roc_year_is_unknown() -> None:
    assert ev.missing_draws("114000110", "115000002") is None
    assert ev.missing_draws("115000084", "115000084") == ()


# 3 — historical ranking exposed before any refresh recommendation
def test_historical_ranking_reported_first(roots: tuple[Path, Path]) -> None:
    _write_multi(roots[0], cutoff="115000073", ticket_counts=[2])
    fam = _family(_discover(roots, latest_draw="115000091"), 2)
    assert [r.strategy_id for r in fam.historical_ranking] == ["s_high", "s_mid", "s_low"]
    assert fam.historical_ranking_cutoff == "115000073"
    assert fam.refresh.report_existing_ranking_first is True
    assert fam.refresh.refresh_recommended is True


# 5 — delta refresh preferred while incremental extension is valid
def test_delta_refresh_preferred_over_full_rerun() -> None:
    plan = ev.plan_refresh(
        ev.EvidenceStatus.AVAILABLE_STALE, ranking_available=True, missing=("115000085",)
    )
    assert plan.mode is ev.RefreshMode.DELTA_REFRESH
    incompatible = ev.plan_refresh(
        ev.EvidenceStatus.AVAILABLE_STALE,
        ranking_available=True,
        missing=("115000085",),
        schema_compatible=False,
    )
    assert incompatible.mode is ev.RefreshMode.FULL_RERUN
    assert incompatible.full_rerun_reason is ev.FullRerunReason.INCOMPATIBLE_SCHEMA
    assert incompatible.report_existing_ranking_first is True


# 6 — full rerun needs one explicit reason
@pytest.mark.parametrize("reason", [None, "", "README_DID_NOT_SHOW_IT", 3])
def test_full_rerun_requires_explicit_reason(reason: object) -> None:
    with pytest.raises(ValueError, match="full rerun requires"):
        ev.require_full_rerun_reason(reason)


def test_owner_requested_full_rerun_is_accepted() -> None:
    reason = ev.require_full_rerun_reason("OWNER_REQUESTED_FULL_RERUN")
    plan = ev.plan_refresh(
        ev.EvidenceStatus.AVAILABLE_STALE,
        ranking_available=True,
        missing=(),
        owner_full_rerun_reason=reason,
    )
    assert plan.mode is ev.RefreshMode.FULL_RERUN
    assert plan.full_rerun_reason is ev.FullRerunReason.OWNER_REQUESTED_FULL_RERUN


# 10 / Case C — ABSENT only after the bounded canonical lookup finds nothing
def test_truly_absent_only_after_lookup(roots: tuple[Path, Path]) -> None:
    _write_multi(roots[0], cutoff="115000084", ticket_counts=[3])
    report = _discover(roots, readme_text="2 注")
    fam2 = _family(report, 2)
    assert fam2.status is ev.EvidenceStatus.ABSENT
    assert fam2.refresh.mode is ev.RefreshMode.NO_EXISTING_EVIDENCE
    assert report.lookup_roots and all("data" in r or "research" in r for r in report.lookup_roots)
    assert _family(report, 3).status is ev.EvidenceStatus.AVAILABLE_CURRENT


def test_unparseable_evidence_is_invalid_not_absent(roots: tuple[Path, Path]) -> None:
    (roots[0] / "biglotto_multi_ticket_historical_records_v2.json").write_text("{", "utf-8")
    fam = _family(_discover(roots), 2)
    assert fam.status is ev.EvidenceStatus.UNAVAILABLE_INVALID
    assert fam.refresh.full_rerun_reason is ev.FullRerunReason.INVALID_EXISTING_EVIDENCE


def test_task_owned_ranking_declared_by_committed_provenance(roots: tuple[Path, Path]) -> None:
    data, _ = roots
    _write_multi(data, cutoff="115000073", ticket_counts=[2])
    k5 = {
        "projection_schema_version": "FIXTURE_K5",
        "provenance": {
            "cutoff": "115000084",
            "source_ranking_locator": "/elsewhere/checkout/.task-data/RUN/rankings.json",
            "source_ranking_k_values": [2, 5],
            "source_ranking_schema": "FIXTURE_RANKINGS",
            "source_ranking_run_id": "RUN",
        },
        "records": [{"strategy_id": "k5a", "ticket_count": 5, "window": "FULL", "rank": 1}],
    }
    (data / "biglotto_exact_native_k5_115000084_records_v1.json").write_text(
        json.dumps(k5), encoding="utf-8"
    )
    fam = _family(_discover(roots, latest_draw="115000091"), 2)
    assert fam.data_cutoff == "115000084"
    assert fam.evidence_locator == ".task-data/RUN/rankings.json"
    assert fam.evidence_packaged is False
    assert fam.historical_ranking_cutoff == "115000073"
    assert fam.known_missing_draws == tuple(f"1150000{n}" for n in range(85, 92))


def test_ranking_comparison_exposes_stability() -> None:
    rows = ev.compare_rankings(["a", "b", "c"], ["c", "a", "d"])
    by_id = {r["strategy_id"]: r for r in rows}
    assert by_id["a"]["rank_change"] == -1 and by_id["a"]["strategy_stability"] == "STABLE"
    assert by_id["c"]["rank_change"] == 2 and by_id["c"]["strategy_stability"] == "UNSTABLE"
    assert by_id["b"]["strategy_stability"] == "DROPPED"
    assert by_id["d"]["strategy_stability"] == "ENTERED"


# 7 / 8 / 9 / Case D — README generated block
_README = f"# X\n\n{ev.BEGIN_MARKER}\nold\n{ev.END_MARKER}\n\n## Tail\n"


def test_readme_generation_idempotent_and_detects_stale(roots: tuple[Path, Path]) -> None:
    data, research = roots
    repo = data.parents[1]
    _write_multi(data, cutoff="115000073", ticket_counts=[2, 3])
    kw = {"data_dir": data, "research_dir": research, "repo_root": repo}
    first = ev.expected_readme(_README, **kw)
    assert first != _README  # stale block detected
    assert ev.expected_readme(first, **kw) == first  # idempotent
    assert first.endswith("## Tail\n") and first.count(ev.BEGIN_MARKER) == 1
    assert "`src/data/biglotto_multi_ticket_historical_records_v2.json`" in first
    _write_multi(data, cutoff="115000084", ticket_counts=[2, 3])
    assert ev.expected_readme(first, **kw) != first  # authority changed -> check fails


def test_readme_markers_required() -> None:
    with pytest.raises(ValueError, match="markers missing"):
        ev.replace_readme_block("# no markers\n", "x")


def test_repository_readme_generated_block_is_current() -> None:
    text = REAL_README.read_text(encoding="utf-8")
    assert text == ev.expected_readme(text), (
        "README B649 evidence block is stale: run "
        "`uv run python tools/b649_evidence_status.py --write-readme`"
    )
    block = text[text.index(ev.BEGIN_MARKER) : text.index(ev.END_MARKER)]
    for locator in ("biglotto_multi_ticket_historical_records_v2.json", "exact_native_k5"):
        assert locator in block
    for path in ev.discover(readme_text=text).families:
        if path.evidence_packaged and path.evidence_locator:
            assert (ev.REPO_ROOT / path.evidence_locator).is_file()
