"""Replay validation errors must match the documented sanitized response."""

from typing import Protocol, cast

import httpx
from fastapi.testclient import TestClient

from lottolab.interfaces.api.app import create_app
from lottolab.interfaces.api.draw_data import ApiValidationErrorResponse


class JsonTestClient(Protocol):
    def get(self, url: str, **kwargs: object) -> httpx.Response: ...


def test_replay_query_validation_matches_openapi() -> None:
    client = cast(JsonTestClient, TestClient(create_app()))
    document = client.get("/openapi.json").json()
    paths = document["paths"]
    routes = (
        ("/api/v1/replay-strategy-inventory", {"lottery_type": "INVALID"}),
        ("/api/v1/b649/sealed-084-replays", {"ticket_count": 0}),
        ("/api/v1/replay-backfill/strategies", {"lottery_type": "INVALID"}),
        ("/api/v1/replay-backfill/predictions", {"lottery_type": "INVALID"}),
        ("/api/v1/replay-backfill/coverage", {"lottery_type": "INVALID"}),
    )
    for path, params in routes:
        response = client.get(path, params=params)
        assert response.status_code == 422
        assert response.json()["error_code"] == "REQUEST_VALIDATION_FAILED"
        ApiValidationErrorResponse.model_validate(response.json())
        schema = paths[path]["get"]["responses"]["422"]["content"]["application/json"]["schema"]
        expected_ref = "#/components/schemas/ApiValidationErrorResponse"
        if "anyOf" in schema:
            assert {entry["$ref"] for entry in schema["anyOf"]} == {
                expected_ref,
                "#/components/schemas/ReplayBackfillErrorResponse",
            }
        else:
            assert schema == {"$ref": expected_ref}
