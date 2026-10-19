"""Import one frozen legacy capture and observe one existing ASGI GET endpoint.

Run from the repository with PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:src
.venv/bin/python -B tools/run_biglotto_single_endpoint_pilot.py.
This is captured-record conversion, not prediction regeneration or DB parity.
Inputs are exported files only; no legacy code, database, or service is opened.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
import sys
from dataclasses import asdict, fields
from datetime import date, datetime
from pathlib import Path
from typing import Any, cast

import httpx
from fastapi import FastAPI

from lottolab.application.use_cases.persist_replay_scoring_artifact import (
    PersistReplayScoringArtifact,
)
from lottolab.application.use_cases.score_replay_artifact import ScoreReplayArtifact
from lottolab.domain.draws import LotteryType
from lottolab.domain.replay_history import ReplayCausalDrawRow
from lottolab.domain.replay_predictions import ReplayTarget
from lottolab.domain.replay_scoring import (
    ReplayTargetOutcome,
    ReplayTargetOutcomeReadResult,
)
from lottolab.domain.replay_scoring_projection import (
    ReplayOverallAggregateProjection,
    ReplayScoredPredictionProjection,
    ReplayScoringPersistenceOutcome,
    ReplayScoringPersistResult,
    ReplayScoringRunProjection,
    ReplayStrategyAggregateProjection,
)
from lottolab.evidence.replay_artifact import (
    build_replay_artifact,
    build_replay_prediction_snapshot,
    deserialize_replay_artifact,
    serialize_replay_artifact,
)
from lottolab.evidence.replay_scoring_artifact import (
    ReplayScoringArtifact,
    build_replay_scoring_artifact,
    deserialize_replay_scoring_artifact,
    serialize_replay_scoring_artifact,
)
from lottolab.interfaces.api.replay_scoring_projections import (
    create_replay_scoring_projections_router,
)
from tools.import_snapshot import verify as verify_export

REPO = Path(__file__).resolve().parents[1]
TASK = REPO / ".task-data/biglotto-single-endpoint-pilot-r1"
MANIFEST = REPO / "data/manifests/biglotto-single-endpoint-pilot-r1.json"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _json(data: bytes) -> dict[str, Any]:
    value: Any = json.loads(data)
    _require(isinstance(value, dict), "expected a JSON object")
    return cast("dict[str, Any]", value)


class _OutcomeReader:
    def __init__(self, outcome: ReplayTargetOutcome) -> None:
        self.outcome = outcome

    def load_target_outcome(
        self, lottery_type: LotteryType, target_draw_number: str
    ) -> ReplayTargetOutcomeReadResult:
        _require(
            lottery_type is self.outcome.lottery_type
            and target_draw_number == self.outcome.target_draw_number,
            "unexpected outcome lookup",
        )
        return ReplayTargetOutcomeReadResult.found(self.outcome)


class _ArtifactFile:
    """Pilot-only immutable file storage; implements existing writer/reader ports."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def persist_replay_scoring_artifact(
        self, artifact: ReplayScoringArtifact, canonical_bytes: bytes
    ) -> ReplayScoringPersistResult:
        _require(
            deserialize_replay_scoring_artifact(canonical_bytes) == artifact,
            "scoring canonical round-trip mismatch",
        )
        with self.path.open("xb") as handle:
            handle.write(canonical_bytes)
        return ReplayScoringPersistResult(
            ReplayScoringPersistenceOutcome.INSERTED, artifact.payload_sha256
        )

    def get_replay_scoring_artifact(
        self, scoring_artifact_payload_sha256: str
    ) -> ReplayScoringArtifact | None:
        artifact = deserialize_replay_scoring_artifact(self.path.read_bytes())
        return artifact if artifact.payload_sha256 == scoring_artifact_payload_sha256 else None

    def get_run(self, scoring_artifact_payload_sha256: str) -> ReplayScoringRunProjection | None:
        sha = scoring_artifact_payload_sha256
        artifact = self.get_replay_scoring_artifact(sha)
        if artifact is None:
            return None
        return ReplayScoringRunProjection(
            artifact.artifact_schema_version,
            sha,
            artifact.source_replay_artifact_payload_sha256,
            artifact.dataset_id,
            artifact.dataset_version,
            artifact.lottery_type.value,
            len(artifact.target_identities),
            len(artifact.strategy_identities),
            artifact.scored_record_count,
            artifact.overall_aggregate.aggregation_sha256,
        )

    def list_scored_predictions(
        self,
        scoring_artifact_payload_sha256: str,
        *,
        target_draw_number: str | None = None,
        strategy_id: str | None = None,
    ) -> tuple[ReplayScoredPredictionProjection, ...]:
        sha = scoring_artifact_payload_sha256
        artifact = self.get_replay_scoring_artifact(sha)
        if artifact is None:
            return ()
        raw = _json(serialize_replay_scoring_artifact(artifact))
        projections: list[ReplayScoredPredictionProjection] = []
        for ordinal, record in enumerate(raw["scored_predictions"]):
            if (
                target_draw_number is not None
                and record["target_draw_number"] != target_draw_number
            ):
                continue
            if strategy_id is not None and record["strategy_id"] != strategy_id:
                continue
            values = {
                field.name: record.get(field.name)
                for field in fields(ReplayScoredPredictionProjection)
            }
            values.update(
                run_payload_sha256=sha,
                ordinal=ordinal,
                source_snapshot_result_sha256=record["source_replay_snapshot_result_sha256"],
            )
            numbers = record.get("predicted_main_numbers")
            values["predicted_main_numbers"] = tuple(numbers) if numbers is not None else None
            projections.append(ReplayScoredPredictionProjection(**values))
        return tuple(projections)

    def list_strategy_aggregates(
        self, scoring_artifact_payload_sha256: str
    ) -> tuple[ReplayStrategyAggregateProjection, ...]:
        sha = scoring_artifact_payload_sha256
        artifact = self.get_replay_scoring_artifact(sha)
        if artifact is None:
            return ()
        projections: list[ReplayStrategyAggregateProjection] = []
        for ordinal, record in enumerate(artifact.strategy_aggregates):
            values: dict[str, Any] = asdict(record)
            values.update(
                run_payload_sha256=sha, ordinal=ordinal, aggregate_sha256=record.aggregation_sha256
            )
            projections.append(
                ReplayStrategyAggregateProjection(
                    **{
                        field.name: values[field.name]
                        for field in fields(ReplayStrategyAggregateProjection)
                    }
                )
            )
        return tuple(projections)

    def get_overall_aggregate(
        self, scoring_artifact_payload_sha256: str
    ) -> ReplayOverallAggregateProjection | None:
        sha = scoring_artifact_payload_sha256
        artifact = self.get_replay_scoring_artifact(sha)
        if artifact is None:
            return None
        values: dict[str, Any] = {
            **asdict(artifact.overall_aggregate),
            "run_payload_sha256": sha,
            "aggregate_sha256": artifact.overall_aggregate.aggregation_sha256,
        }
        return ReplayOverallAggregateProjection(
            **{field.name: values[field.name] for field in fields(ReplayOverallAggregateProjection)}
        )


async def _observe_endpoint(
    store: _ArtifactFile, sha: str, expected: dict[str, Any]
) -> dict[str, Any]:
    app = FastAPI()
    app.include_router(create_replay_scoring_projections_router(lambda: store))
    path = f"/api/v1/replay-scoring/{sha}/predictions"
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://pilot.invalid"
    ) as client:
        response = await client.get(
            path,
            params={
                "target_draw": expected["target_draw_number"],
                "strategy_id": expected["strategy_id"],
            },
        )
    _require(response.status_code == 200, f"GET failed: HTTP {response.status_code}")
    raw_records: Any = response.json()
    _require(isinstance(raw_records, list), "GET must return a list")
    records = cast("list[dict[str, Any]]", raw_records)
    _require(len(records) == 1, "GET must return exactly one record")
    observed = records[0]
    mismatches = {
        key: {"expected": value, "observed": observed.get(key)}
        for key, value in expected.items()
        if observed.get(key) != value
    }
    _require(not mismatches, f"mapped capture parity mismatch: {mismatches}")
    return {
        "path": path,
        "query": {
            "target_draw": expected["target_draw_number"],
            "strategy_id": expected["strategy_id"],
        },
        "transport": "in-process ASGI; no network listener",
        "status_code": response.status_code,
        "response": records,
        "response_sha256": _sha(response.content),
        "compared_fields": expected,
        "mismatches": mismatches,
    }


def run(manifest_path: Path, output: Path) -> None:
    manifest = _json(manifest_path.read_bytes())
    input_root = (REPO / manifest["root"]).resolve()
    _require(input_root == TASK / "input", "input root outside fixed pilot")
    _require(output.resolve() == TASK / "output", "output root outside fixed pilot")
    _require(not output.exists(), "retain existing outputs; use no overwrite")
    _require(not input_root.is_symlink(), "input root must be a regular directory")
    for entry in manifest["files"]:
        path = input_root / entry["path"]
        _require(
            path.is_file() and not path.is_symlink() and path.resolve().parent == input_root,
            "unsafe input file",
        )
    for path, expected_hash in manifest["target_code_sha256"].items():
        _require(
            _sha((REPO / path).read_bytes()) == expected_hash, f"target source changed: {path}"
        )
    # Invoke the repository's actual snapshot intake boundary, not legacy runtime.
    verify_export(manifest_path)
    capture = _json((input_root / "legacy-capture.json").read_bytes())["candidates_sample"][0]
    dataset_bytes = (input_root / "reference-dataset.json").read_bytes()
    dataset = _json(dataset_bytes)
    _require(_sha(dataset_bytes) == manifest["dataset_version"], "dataset version mismatch")
    _require(capture["lottery_type"] == dataset["lottery_type"] == "BIG_LOTTO", "wrong lottery")
    _require(capture["prediction_status"] == "READY", "capture is not a successful prediction")
    _require(capture["predicted_special"] is None, "unexpected separate special prediction")
    target = ReplayTarget(
        capture["draw_number"], datetime.strptime(capture["draw_date"], "%Y/%m/%d").date()
    )
    history = tuple(
        ReplayCausalDrawRow(
            lottery_type=LotteryType.BIG_LOTTO,
            draw_number=row["draw_number"],
            draw_date=date.fromisoformat(row["draw_date"]),
            main_numbers=tuple(row["main_numbers"]),
            special_number=row["special_number"],
        )
        for row in dataset["history_rows"]
    )
    keys = [(row.draw_date, int(row.draw_number)) for row in history]
    _require(
        keys == sorted(keys)
        and len(set(keys)) == len(keys)
        and len({row.draw_number for row in history}) == len(history),
        "invalid history order",
    )
    _require(
        bool(keys) and keys[-1] < (target.draw_date, int(target.draw_number)), "future history"
    )
    trace = re.fullmatch(r"ts3_regime_3bet:get_one_bet:hist=([0-9]+)", capture["source_trace"])
    _require(
        trace is not None and int(trace[1]) == len(history) == 635, "capture history count mismatch"
    )
    row = dataset["target_outcome"]
    _require(
        row["draw_number"] == target.draw_number
        and row["draw_date"] == target.draw_date.isoformat()
        and row["main_numbers"] == capture["actual_numbers"]
        and row["special_number"] == capture["actual_special"],
        "captured outcome mismatch",
    )
    predicted = tuple(capture["predicted_numbers"])
    legacy_preimage = f"{capture['strategy_id']}:{target.draw_number}:{sorted(predicted)}".encode()
    _require(
        _sha(legacy_preimage)[:16] == capture["provenance_hash"], "legacy fingerprint mismatch"
    )
    snapshot = build_replay_prediction_snapshot(
        dataset_id=manifest["dataset_id"],
        dataset_version=manifest["dataset_version"],
        lottery_type=LotteryType.BIG_LOTTO,
        target=target,
        strategy_id=capture["strategy_id"],
        strategy_identity=(
            capture["strategy_id"],
            capture["strategy_name"],
            manifest["strategy_version"],
        ),
        history_status="OK",
        history_reason_code=None,
        causal_history=history,
        prediction_status="OK",
        prediction_reason_code=None,
        predicted_main_numbers=predicted,
    )
    source = build_replay_artifact(
        dataset_id=manifest["dataset_id"],
        dataset_version=manifest["dataset_version"],
        lottery_type=LotteryType.BIG_LOTTO,
        strategy_ids=(capture["strategy_id"],),
        targets=(target,),
        snapshots=(snapshot,),
    )
    source_bytes = serialize_replay_artifact(source)
    _require(deserialize_replay_artifact(source_bytes) == source, "source round-trip mismatch")
    outcome = ReplayTargetOutcome.create(
        lottery_type=LotteryType.BIG_LOTTO,
        target_draw_number=target.draw_number,
        target_draw_date=target.draw_date,
        winning_main_numbers=tuple(row["main_numbers"]),
        winning_special_number=row["special_number"],
    )
    result = ScoreReplayArtifact(_OutcomeReader(outcome)).execute(source)
    scoring = build_replay_scoring_artifact(
        source_artifact=source,
        scored_predictions=result.scored_predictions,
        strategy_aggregates=result.strategy_aggregates,
        overall_aggregate=result.overall_aggregate,
    )
    output.mkdir()
    with (output / "source-artifact.json").open("xb") as handle:
        handle.write(source_bytes)
    store = _ArtifactFile(output / "scoring-artifact.json")
    persisted = PersistReplayScoringArtifact(store).execute(scoring)
    expected = {
        "ordinal": 0,
        "target_draw_number": target.draw_number,
        "target_draw_date": target.draw_date.isoformat(),
        "strategy_id": capture["strategy_id"],
        "predicted_main_numbers": capture["predicted_numbers"],
        "source_prediction_status": "OK",
        "main_number_hit_count": capture["hit_count"],
        "special_number_hit": capture["special_hit"],
    }
    observed = asyncio.run(_observe_endpoint(store, scoring.payload_sha256, expected))
    receipt: dict[str, Any] = {
        "pilot_id": manifest["pilot_id"],
        "status": "PASS_CAPTURE_CONVERSION_PARITY",
        "source_capture": manifest["capture_source"],
        "draw_source": manifest["draw_source"],
        "dataset_id": source.dataset_id,
        "dataset_version": source.dataset_version,
        "source_artifact_payload_sha256": source.payload_sha256,
        "source_artifact_file_sha256": _sha(source_bytes),
        "snapshot_result_sha256": snapshot.result_sha256,
        "causal_history_sha256": snapshot.causal_history_sha256,
        "causal_history_count": snapshot.causal_history_count,
        "cutoff_draw_number": snapshot.cutoff_draw_number,
        "cutoff_draw_date": str(snapshot.cutoff_draw_date),
        "outcome_sha256": outcome.outcome_sha256,
        "scoring_artifact_payload_sha256": scoring.payload_sha256,
        "scoring_artifact_file_sha256": _sha(store.path.read_bytes()),
        "scored_result_sha256": scoring.scored_predictions[0].scored_result_sha256,
        "manifest_sha256": _sha(manifest_path.read_bytes()),
        "converter_sha256": _sha(Path(__file__).read_bytes()),
        "target_source_commit": manifest["target_source_commit"],
        "target_code_sha256": manifest["target_code_sha256"],
        "python_version": sys.version.split()[0],
        "persistence": persisted.outcome.value,
        "storage": "immutable canonical artifact file; no SQLite",
        "endpoint": observed,
        "status_mapping": {"legacy READY": "imported snapshot OK"},
        "derived_strategy_version": manifest["strategy_version"],
        "strategy_version_semantics": manifest["strategy_version_semantics"],
        "evidence_limits": manifest["evidence_limits"],
        "manual_tests": "NOT_RUN_OWNER_CONSTRAINT",
        "ci_reruns": "NOT_RUN",
        "legacy_runtime_access": "NONE",
        "writes": [
            str(output / name)
            for name in ("source-artifact.json", "scoring-artifact.json", "evidence.json")
        ],
    }
    with (output / "evidence.json").open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                "status": receipt["status"],
                "record_count": 1,
                "scoring_sha256": scoring.payload_sha256,
                "evidence": str(output / "evidence.json"),
            }
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    parser.add_argument("--output", type=Path, default=TASK / "output")
    arguments = parser.parse_args()
    run(arguments.manifest, arguments.output)
