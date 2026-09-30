"""Packaged cutoff-084 K2/K3 ranking evidence and fresh-checkout lookup."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any, cast

import pytest
import tools.b649_evidence_status as evidence_status

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "src" / "lottolab" / "strategies" / "data"
SOURCE_RANKING_SHA256 = "eb41d668c9356a0ce68db2504953e2a2f916f02a709e60dd6ce0d716bcb11e44"
CONTRACT_DIFFERENCES = [
    "E1 strategy universe",
    "E2 draw population",
    "E3 window anchoring",
    "E4 seeded producer semantics",
    "E5 eligibility semantics",
]


def _artifact_path(k: int) -> Path:
    return DATA_DIR / f"biglotto_exact_native_k{k}_115000084_records_v1.json"


def _load_artifact(path: Path) -> dict[str, Any]:
    document: object = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(document, dict)
    return cast(dict[str, Any], document)


def _records(document: dict[str, Any]) -> list[dict[str, Any]]:
    rows: object = document.get("records")
    assert isinstance(rows, list)
    unknown_rows = cast(list[object], rows)
    result: list[dict[str, Any]] = []
    for row in unknown_rows:
        assert isinstance(row, dict)
        result.append(cast(dict[str, Any], row))
    return result


def _projection_sha256(document: dict[str, Any]) -> str:
    payload = {key: value for key, value in document.items() if key != "projection_sha256"}
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@pytest.mark.parametrize(
    ("k", "ranked_count", "unavailable_count"),
    [(2, 17, 2), (3, 16, 3)],
)
def test_cutoff_084_projection_preserves_full_ranking_and_contract(
    k: int, ranked_count: int, unavailable_count: int
) -> None:
    path = _artifact_path(k)
    document = _load_artifact(path)
    rows = _records(document)
    provenance = document["provenance"]

    assert document["projection_schema_version"] == f"B649_EXACT_NATIVE_K{k}_RECORDS_V1"
    assert document["projection_sha256"] == _projection_sha256(document)
    assert provenance["cutoff"] == "115000084"
    assert provenance["k"] == k
    assert provenance["source_ranking_run_id"] == "BRANCH6_BIGLOTTO_K2_K3_K5_K10_FINALIZATION_R1"
    assert provenance["source_ranking_schema"] == "BRANCH6_LANE6_FINALIZATION_RANKINGS_V1"
    assert provenance["source_ranking_sha256"] == SOURCE_RANKING_SHA256
    assert provenance["full_window"] == {
        "first_target": "96000001",
        "last_target": "115000084",
        "observations_required": 2166,
        "requested_draws": 2166,
        "strategy_universe_count": 19,
        "eligible_count": ranked_count,
        "metric_unavailable_count": unavailable_count,
    }
    assert provenance["eligibility_semantics"] == {
        "execution_failure_inside_window": "WINDOW_UNAVAILABLE",
        "execution_failure_outside_window": "CURRENT_WINDOW_UNAFFECTED",
        "partition": "strategy x window",
        "unavailable_metric_value": "null (never 0)",
        "window_ineligible_incomplete_observations": "DENOMINATOR_EXCLUSION_ONLY",
    }

    interpretation = provenance["contract_interpretation"]
    assert interpretation["status"] == "VALID_DIFFERENT_CONTRACT"
    comparison = interpretation["comparison_to_cutoff_115000073_v2"]
    assert comparison["same_contract_time_series"] is False
    assert comparison["relationship"] == (
        "DIFFERENT_CONTRACT_NOT_AN_EARLIER_SAME_CONTRACT_OBSERVATION"
    )
    assert comparison["differences"] == CONTRACT_DIFFERENCES

    universe = provenance["strategy_universe"]
    assert len(universe) == 19
    assert len(rows) == len(universe)
    assert {row["strategy_id"] for row in rows} == set(universe)
    assert all(row["ticket_count"] == k and row["window"] == "FULL" for row in rows)
    assert all(row["requested_draws"] == 2166 for row in rows)
    assert sum(row["rankable"] is True for row in rows) == ranked_count
    assert sum(row["rankable"] is False for row in rows) == unavailable_count
    assert all(
        row["rankable"] is (row["metric_status"] == "AVAILABLE") for row in rows
    )
    assert all(
        row["official_any_prize_rate"] is not None and row["coverage"] is not None
        for row in rows
        if row["rankable"]
    )
    assert all(
        row["official_any_prize_rate"] is None
        and row["coverage"] is None
        and row["metric_unavailable_reason"] == "EXECUTION_FAILURE_IN_WINDOW"
        for row in rows
        if not row["rankable"]
    )
    serialized = path.read_text(encoding="utf-8")
    assert "/Users/" not in serialized
    assert ".task-data" not in serialized


def test_k2_k3_rankings_resolve_from_fresh_checkout_without_task_data(tmp_path: Path) -> None:
    fresh_root = tmp_path / "fresh-checkout"
    data_dir = fresh_root / "src" / "lottolab" / "strategies" / "data"
    research_dir = fresh_root / "docs" / "research" / "matrix-native-results"
    data_dir.mkdir(parents=True)
    research_dir.mkdir(parents=True)

    for k in (2, 3):
        source = _artifact_path(k)
        if source.is_file():
            shutil.copyfile(source, data_dir / source.name)

    assert not (fresh_root / ".task-data").exists()
    report: evidence_status.EvidenceReport = evidence_status.discover(
        data_dir=data_dir,
        research_dir=research_dir,
        repo_root=fresh_root,
        latest_draw="115000084",
        ticket_counts=(2, 3),
    )

    for k in (2, 3):
        family: evidence_status.FamilyStatus = next(
            item for item in report.families if item.ticket_count == k
        )
        relative_path = (
            "src/lottolab/strategies/data/"
            f"biglotto_exact_native_k{k}_115000084_records_v1.json"
        )
        assert cast(Any, family).status is evidence_status.EvidenceStatus.AVAILABLE_CURRENT
        assert family.data_cutoff == "115000084"
        assert family.evidence_packaged is True
        assert family.evidence_locator == relative_path
        assert family.ranking_available is True
        assert family.ranking_locator == relative_path
        assert family.historical_ranking_cutoff == "115000084"

        document = _load_artifact(data_dir / Path(relative_path).name)
        rankable_rows = sorted(
            (row for row in _records(document) if row["rankable"]),
            key=lambda row: (row["rank"], row["strategy_id"]),
        )
        assert [row.strategy_id for row in family.historical_ranking] == [
            row["strategy_id"] for row in rankable_rows[:3]
        ]
        assert [row.official_any_prize_rate for row in family.historical_ranking] == [
            row["official_any_prize_rate"] for row in rankable_rows[:3]
        ]
