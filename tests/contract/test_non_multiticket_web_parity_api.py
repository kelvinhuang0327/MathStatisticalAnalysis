"""API acceptance for the non-multiticket web-parity workspaces."""

# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false
# pyright: reportUnknownArgumentType=false

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from lottolab.application.draw_automation import ProviderDrawRecord, ProviderFetchResult
from lottolab.application.strategy_evidence import (
    D3AvailabilityStatus,
    D3DefinitionSnapshot,
    StrategyEvidenceRegistryUnavailableError,
)
from lottolab.domain.draws import LotteryType
from lottolab.infrastructure.persistence.draw_schema import (
    DATA_DIRECTORY_ENV,
    LocalDataPaths,
    resolve_local_data_paths,
)
from lottolab.infrastructure.strategy_evidence_registry import CommittedStrategyEvidenceRegistry
from lottolab.interfaces.api.app import create_app

REPO_ROOT = Path(__file__).resolve().parents[2]
D3_AUTHORITY_PATH = "contracts/evidence/metric_definitions/d3.json"

_VALID_REGISTRY_PAYLOAD = {
    "entries": [],
    "schema_id": "lottolab.evidence.canonical_evidence_registry",
    "schema_version": "1.0.0",
}

_VALID_D3_PAYLOAD = {
    "metric_id": "D3",
    "metric_version": "v1",
    "schema_id": "lottolab.evidence.metric_definition",
    "schema_version": "1.0.0",
    "formula_status": "RESERVED_UNAVAILABLE",
    "direction": "DESCRIPTIVE_ONLY",
    "aggregation": "NONE",
    "sample_unit": "DRAWS",
    "decimal_scale": 4,
    "rounding_mode": "ROUND_HALF_EVEN",
    "unit": "UNITLESS",
    "definition_prose": "fixture prose",
}


class _Provider:
    provider_id = "fixture-provider"
    provider_version = "fixture-v1"

    def fetch_draws(
        self,
        *,
        lottery_type: LotteryType,
        date_from: date,
        date_to: date,
    ) -> ProviderFetchResult:
        assert lottery_type is LotteryType.BIG_LOTTO
        assert date_from <= date(2026, 7, 29) <= date_to
        return ProviderFetchResult(
            provider_id=self.provider_id,
            provider_version=self.provider_version,
            records=(
                ProviderDrawRecord(
                    lottery_type=lottery_type,
                    draw_number="1001",
                    draw_date=date(2026, 7, 29),
                    main_numbers=(1, 3, 9, 17, 24, 49),
                    special_numbers=(7,),
                    source_reference="fixture:1001",
                ),
            ),
        )


def _paths(tmp_path: Path) -> LocalDataPaths:
    return resolve_local_data_paths(
        environ={DATA_DIRECTORY_ENV: str(tmp_path / "non-multiticket-api")}
    )


def _request() -> dict[str, str]:
    return {
        "lottery_type": "BIG_LOTTO",
        "date_from": "2026-07-29",
        "date_to": "2026-07-29",
    }


def test_manual_sync_persists_draw_and_queryable_audit_context(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    client = TestClient(
        create_app(
            data_paths_provider=lambda: paths,
            draw_data_provider_factory=lambda: _Provider(),
        )
    )

    response = client.post("/api/v1/draw-sync/manual", json=_request())

    assert response.status_code == 200
    payload = response.json()
    assert payload["operation_type"] == "MANUAL_SYNC"
    assert payload["provider"] == "fixture-provider"
    assert payload["fetched_count"] == 1
    assert payload["result"]["inserted_count"] == 1
    run_id = payload["result"]["run_id"]

    runs = client.get(
        "/api/v1/ingestion-runs",
        params={
            "operation_type": "MANUAL_SYNC",
            "source": "fixture-provider",
        },
    )
    assert runs.status_code == 200
    run = runs.json()["records"][0]
    assert run["run_id"] == run_id
    assert run["trigger"] == "MANUAL_SYNC"
    assert run["provider_version"] == "fixture-v1"
    assert run["requested_start"] == run["resolved_start"] == "2026-07-29"
    assert run["requested_end"] == run["resolved_end"] == "2026-07-29"

    detail = client.get(f"/api/v1/ingestion-runs/{run_id}")
    assert detail.status_code == 200
    assert detail.json()["items"][0]["source"] == "fixture-provider"

    draw = client.get("/api/v1/draws/BIG_LOTTO/1001")
    assert draw.status_code == 200
    assert draw.json()["main_numbers"] == [1, 3, 9, 17, 24, 49]


def test_not_configured_returns_reason_code_and_failed_audit(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    client = TestClient(create_app(data_paths_provider=lambda: paths))

    response = client.post("/api/v1/draw-sync/manual", json=_request())

    assert response.status_code == 503
    assert response.json() == {
        "error_code": "AUTOMATION_NOT_CONFIGURED",
        "message": "Draw automation is not configured.",
    }
    audit = client.get(
        "/api/v1/ingestion-runs",
        params={"status": "FAILED", "operation_type": "MANUAL_SYNC"},
    )
    assert audit.status_code == 200
    record = audit.json()["records"][0]
    assert record["provider"] == "NOT_CONFIGURED"
    assert record["error_summary"] == "AUTOMATION_NOT_CONFIGURED"
    assert record["inserted_count"] == 0


def test_strategy_evidence_is_fail_closed_and_excludes_multiticket_ranking() -> None:
    response = TestClient(create_app()).get("/api/v1/strategy-evidence")

    assert response.status_code == 200
    payload = response.json()
    assert payload["items"]
    assert all(item["replicate"] == "NOT_APPLICABLE" for item in payload["items"])
    assert all(
        item["registration_status"] == "CANONICAL_EVIDENCE_MISSING"
        for item in payload["items"]
    )
    assert payload["best_strategy"] == {
        "status": "UNAVAILABLE",
        "reason": "NO_CANONICAL_STRATEGY_EVALUATION_EVIDENCE",
    }
    assert payload["strategy_combination_hit_rate"] == {
        "status": "EXCLUDED_ACTIVE_MULTITICKET_SCOPE",
        "value": "NOT_AVAILABLE",
        "owner": "ACTIVE_MULTITICKET_AGENT",
    }
    assert payload["d3"]["status"] == "RESERVED_UNAVAILABLE"
    assert payload["d3"]["value"] == "NOT_AVAILABLE"

    canonical_d3 = json.loads((REPO_ROOT / D3_AUTHORITY_PATH).read_text(encoding="utf-8"))
    assert payload["d3"]["definition"] == {
        "metric_id": canonical_d3["metric_id"],
        "metric_version": canonical_d3["metric_version"],
        "schema_id": canonical_d3["schema_id"],
        "schema_version": canonical_d3["schema_version"],
        "formula_status": canonical_d3["formula_status"],
        "direction": canonical_d3["direction"],
        "aggregation": canonical_d3["aggregation"],
        "sample_unit": canonical_d3["sample_unit"],
        "decimal_scale": canonical_d3["decimal_scale"],
        "rounding_mode": canonical_d3["rounding_mode"],
        "unit": canonical_d3["unit"],
        "definition_prose": canonical_d3["definition_prose"],
        "authority_path": D3_AUTHORITY_PATH,
    }


def test_committed_strategy_evidence_registry_parses_canonical_d3_definition(
    tmp_path: Path,
) -> None:
    registry_path = tmp_path / "canonical_evidence_registry.json"
    d3_path = tmp_path / "d3.json"
    registry_path.write_text(json.dumps(_VALID_REGISTRY_PAYLOAD), encoding="utf-8")
    d3_path.write_text(json.dumps(_VALID_D3_PAYLOAD), encoding="utf-8")
    registry = CommittedStrategyEvidenceRegistry(registry_path, d3_path, D3_AUTHORITY_PATH)

    snapshot = registry.read()

    assert snapshot.d3_status == D3AvailabilityStatus.RESERVED_UNAVAILABLE
    assert snapshot.d3_definition == D3DefinitionSnapshot(
        metric_id="D3",
        metric_version="v1",
        schema_id="lottolab.evidence.metric_definition",
        schema_version="1.0.0",
        formula_status="RESERVED_UNAVAILABLE",
        direction="DESCRIPTIVE_ONLY",
        aggregation="NONE",
        sample_unit="DRAWS",
        decimal_scale=4,
        rounding_mode="ROUND_HALF_EVEN",
        unit="UNITLESS",
        definition_prose="fixture prose",
        authority_path=D3_AUTHORITY_PATH,
    )


def test_committed_strategy_evidence_registry_fails_closed_when_d3_definition_missing(
    tmp_path: Path,
) -> None:
    registry_path = tmp_path / "canonical_evidence_registry.json"
    registry_path.write_text(json.dumps(_VALID_REGISTRY_PAYLOAD), encoding="utf-8")
    registry = CommittedStrategyEvidenceRegistry(registry_path, tmp_path / "missing-d3.json")

    with pytest.raises(StrategyEvidenceRegistryUnavailableError):
        registry.read()


@pytest.mark.parametrize(
    "overrides",
    [
        {"metric_id": "NOT_D3"},
        {"metric_version": ""},
        {"metric_version": None},
        {"schema_id": "wrong.schema"},
        {"schema_version": ""},
        {"formula_status": 1},
        {"direction": None},
        {"aggregation": None},
        {"sample_unit": None},
        {"decimal_scale": -1},
        {"decimal_scale": "4"},
        {"rounding_mode": None},
        {"unit": None},
        {"definition_prose": ""},
        {"definition_prose": None},
    ],
)
def test_committed_strategy_evidence_registry_fails_closed_on_malformed_d3_definition(
    tmp_path: Path, overrides: dict[str, object]
) -> None:
    registry_path = tmp_path / "canonical_evidence_registry.json"
    d3_path = tmp_path / "d3.json"
    registry_path.write_text(json.dumps(_VALID_REGISTRY_PAYLOAD), encoding="utf-8")
    d3_path.write_text(json.dumps({**_VALID_D3_PAYLOAD, **overrides}), encoding="utf-8")
    registry = CommittedStrategyEvidenceRegistry(registry_path, d3_path, D3_AUTHORITY_PATH)

    with pytest.raises(StrategyEvidenceRegistryUnavailableError):
        registry.read()


def test_strategy_evidence_api_fails_closed_when_d3_definition_is_malformed(
    tmp_path: Path,
) -> None:
    registry_path = tmp_path / "canonical_evidence_registry.json"
    d3_path = tmp_path / "d3.json"
    registry_path.write_text(json.dumps(_VALID_REGISTRY_PAYLOAD), encoding="utf-8")
    d3_path.write_text(
        json.dumps({**_VALID_D3_PAYLOAD, "decimal_scale": -1}), encoding="utf-8"
    )
    registry = CommittedStrategyEvidenceRegistry(registry_path, d3_path, D3_AUTHORITY_PATH)

    response = TestClient(
        create_app(strategy_evidence_registry_reader=registry)
    ).get("/api/v1/strategy-evidence")

    assert response.status_code == 503
    assert response.json() == {
        "error_code": "STRATEGY_EVIDENCE_REGISTRY_UNAVAILABLE",
        "message": "Canonical strategy evidence metadata is unavailable.",
    }


def test_historical_import_metadata_route_is_explicitly_not_configured() -> None:
    response = TestClient(create_app()).get("/api/v1/historical-results/runs")

    assert response.status_code == 503
    assert response.json()["error_code"] == "HISTORICAL_RESULTS_NOT_CONFIGURED"


def test_openapi_adds_only_the_approved_read_only_multiticket_paths() -> None:
    paths = set(create_app().openapi()["paths"])

    assert {
        "/api/v1/draw-sync/manual",
        "/api/v1/draw-sync/missing-scan",
        "/api/v1/draw-sync/backfill",
        "/api/v1/draw-sync/scheduled",
        "/api/v1/ingestion-runs",
        "/api/v1/ingestion-runs/{run_id}",
        "/api/v1/strategy-evidence",
        "/api/v1/historical-results/runs",
    } <= paths
    assert {
        path
        for path in paths
        if "multi-ticket" in path or "multiticket" in path
    } == {
        "/api/v1/b649-multi-ticket-records",
        "/api/v1/b649-multi-ticket-records/summary",
    }
