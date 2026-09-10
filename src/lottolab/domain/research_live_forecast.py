"""Class-specific provenance for canonical research live forecast versions.

Original execution and import execution are separate events. The one permitted
legacy artifact cannot be used as a general escape hatch for native generation.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast

LEGACY_STREAM = "B649_CURRENT_INFORMATION_FORECAST_R1"
NATIVE_STREAM = "B649_NEXT_UNDRAWN_FORECAST"
NATIVE_STREAM_VERSION = "B649_FULL_OFFICIAL_ANY_PRIZE_R1"
CONSENSUS_STREAM = "B649_11_STREAM_EQUAL_WEIGHT_NUMBER_CONSENSUS"
CONSENSUS_STREAM_VERSION = "1.0.0"
CONSENSUS_SCHEMA_VERSION = "b649-canonical-forecast-v1"
CONSENSUS_METHOD_ID = "B649_11_STREAM_EQUAL_WEIGHT_NUMBER_CONSENSUS"
CONSENSUS_METHOD_VERSION = "1.0.0"
CONSENSUS_AGGREGATION_UNIT = "NUMBER_LEVEL"
CONSENSUS_WEIGHT_POLICY = "EQUAL_STREAM_WEIGHT"
CONSENSUS_CORRELATED_FAMILY_POLICY = "FULL_VOTE_PER_FROZEN_STREAM_NO_FAMILY_NORMALIZATION"
CONSENSUS_TIE_BREAK = "SUPPORT_UNITS_DESC_NUMBER_ASC"
CONSENSUS_SCORE_DENOMINATOR = 66
CONSENSUS_TARGET_LOTTERY_TYPE = "BIG_LOTTO"
CONSENSUS_TARGET_DRAW_NUMBER = "115000087"
CONSENSUS_TARGET_DRAW_DATE = "2026-09-11"
CONSENSUS_TARGET_SCHEDULED_AT = "2026-09-11T20:30:00+08:00"
CONSENSUS_TARGET_TIMEZONE = "Asia/Taipei"
CONSENSUS_TARGET_DATA_CUTOFF = "115000086"
CONSENSUS_TARGET_HISTORY_DRAW_COUNT = 2168
CONSENSUS_TARGET_HISTORY_SHA256 = "c2ba95be375c739c096baaae6ac03b666bc93ef81c9a721ec9381ed7b4c2cec4"
CONSENSUS_UPSTREAM_TASK_ID = "B649_OPERATIONAL_PREDICTION_LOOP_R1"
CONSENSUS_PRODUCTION_TASK_ID = (
    "B649_11_STREAM_CANONICAL_AGGREGATION_IMPLEMENT_AND_MATERIALIZE_115000087_R1"
)
CONSENSUS_IMPLEMENTATION_COMMIT = "573eb1aa519ccf4eb0c688bff0ca2b6c28183558"
CONSENSUS_IMPLEMENTATION_TREE = "0f1e24d26c6e0c37a709178569cd084f6f7750f7"
CONSENSUS_IMPLEMENTATION_SOURCE_HASHES = (
    (
        "src/lottolab/domain/b649_canonical_consensus.py",
        "85f32dae369234b86d092fe115c1578de3590673328d334b807b40968f01d0f7",
    ),
    (
        "src/lottolab/infrastructure/b649_canonical_forecast_writer.py",
        "76764d5d74a259f8a16ba3e7b54853e4daffc2de7dd4a5cd760a7caaed6a0c10",
    ),
    (
        "tools/materialize_b649_canonical_forecast.py",
        "28564e94d4aae65933309886937073b6601a170cf39641f412818bb9c56a504d",
    ),
)
CONSENSUS_STREAM_SPECS = (
    (
        "b649_new_horizon_minimax_disagreement_r1",
        "v0.1",
        2,
        "predictions/115000087/b649_new_horizon_minimax_disagreement_r1/"
        "115000087-b649_new_horizon_minimax_disagreement_r1-20260908T220756458387p0800-06e621e7.json",
    ),
    (
        "biglotto_deviation_2bet",
        "v0.1",
        1,
        "predictions/115000087/biglotto_deviation_2bet/"
        "115000087-biglotto_deviation_2bet-20260908T220756549249p0800-ee8a5778.json",
    ),
    (
        "biglotto_social_wisdom_anti_popularity",
        "v0.1",
        1,
        "predictions/115000087/biglotto_social_wisdom_anti_popularity/"
        "115000087-biglotto_social_wisdom_anti_popularity-20260908T220756520593p0800-2dd5f277.json",
    ),
    (
        "legacy_biglotto__graph_predictor__cd70713a5709",
        "v0.1",
        1,
        "predictions/115000087/legacy_biglotto__graph_predictor__cd70713a5709/"
        "115000087-legacy_biglotto__graph_predictor__cd70713a5709-20260908T220756579053p0800-b2a25749.json",
    ),
    (
        "legacy_biglotto__hpsb_optimizer__cf5cd7d971e8",
        "v0.1",
        1,
        "predictions/115000087/legacy_biglotto__hpsb_optimizer__cf5cd7d971e8/"
        "115000087-legacy_biglotto__hpsb_optimizer__cf5cd7d971e8-20260908T220756655001p0800-c29b6fe8.json",
    ),
    (
        "legacy_biglotto__pure_cold_predict__9e89f2b41add",
        "v0.1",
        1,
        "predictions/115000087/legacy_biglotto__pure_cold_predict__9e89f2b41add/"
        "115000087-legacy_biglotto__pure_cold_predict__9e89f2b41add-20260908T220756630806p0800-ff2d46c3.json",
    ),
    (
        "legacy_biglotto__test_asm__d39a233a4c75",
        "v0.1",
        3,
        "predictions/115000087/legacy_biglotto__test_asm__d39a233a4c75/"
        "115000087-legacy_biglotto__test_asm__d39a233a4c75-20260908T220756904980p0800-67e675a6.json",
    ),
    (
        "legacy_biglotto__test_ces__78d17c530ab8",
        "v0.1",
        3,
        "predictions/115000087/legacy_biglotto__test_ces__78d17c530ab8/"
        "115000087-legacy_biglotto__test_ces__78d17c530ab8-20260908T220756949668p0800-046fc46c.json",
    ),
    (
        "legacy_biglotto__test_ecp__c9d5ac6decdd",
        "v0.1",
        3,
        "predictions/115000087/legacy_biglotto__test_ecp__c9d5ac6decdd/"
        "115000087-legacy_biglotto__test_ecp__c9d5ac6decdd-20260908T220757075956p0800-7db57da2.json",
    ),
    (
        "legacy_biglotto__test_mwsc__ba37643d6a3b",
        "v0.1",
        3,
        "predictions/115000087/legacy_biglotto__test_mwsc__ba37643d6a3b/"
        "115000087-legacy_biglotto__test_mwsc__ba37643d6a3b-20260908T220757124722p0800-4ea6d9e2.json",
    ),
    (
        "legacy_biglotto__test_tme__f3bb5106dfe3",
        "v0.1",
        3,
        "predictions/115000087/legacy_biglotto__test_tme__f3bb5106dfe3/"
        "115000087-legacy_biglotto__test_tme__f3bb5106dfe3-20260908T220757155867p0800-92a4b552.json",
    ),
)
CONSENSUS_DECISION_RANKING = (
    (29, 30),
    (26, 29),
    (4, 19),
    (24, 18),
    (25, 18),
    (12, 17),
    (47, 16),
    (16, 15),
    (9, 14),
    (43, 14),
    (45, 14),
    (10, 12),
    (39, 12),
    (42, 12),
    (1, 10),
    (18, 10),
    (36, 10),
    (7, 9),
    (22, 9),
    (23, 9),
    (34, 9),
    (35, 9),
    (6, 8),
    (8, 8),
    (11, 8),
    (38, 8),
    (44, 8),
    (19, 6),
    (31, 6),
    (46, 6),
    (49, 6),
    (2, 4),
    (28, 4),
    (15, 3),
    (3, 2),
    (32, 2),
    (40, 2),
    (5, 0),
    (13, 0),
    (14, 0),
    (17, 0),
    (20, 0),
    (21, 0),
    (27, 0),
    (30, 0),
    (33, 0),
    (37, 0),
    (41, 0),
    (48, 0),
)
CANONICAL_CONSENSUS = "CANONICAL_CONSENSUS"
CONSENSUS_PROVENANCE_SCHEMA_VERSION = "b649-canonical-consensus-provenance-v1"
LEGACY_SOURCE_TASK = "B649_NEXT_DRAW_115000087_CURRENT_INFORMATION_FORECAST_R1"
LEGACY_MATERIALIZATION_TASK = "B649_NEXT_DRAW_115000087_FORECAST_PAYLOAD_MATERIALIZATION_R1"
LEGACY_SHA256 = "71b0071eff43e789d5b96c0a29c7ff1130b03645317d68f4012b5ef5b8060867"
LEGACY_HISTORY_SHA256 = "8b1e6295024c65c0ff21928239fc57063c811276691342e231849a990fee583f"
LEGACY_SEAL_SHA256 = "4c9c5bed7bfb60c65986645e4366fd44295e402b30837131e1403d6e63368bc9"
LEGACY_IMPORT_KEY = f"legacy-materialized:{LEGACY_SOURCE_TASK}:{LEGACY_SHA256}"

# SQL columns remain NULL for legacy. Each uncaptured leaf is named in the
# missing map; a JSON null, importer identity or placeholder hash is not a value.
ORIGINAL_JSON_FIELDS = (
    "producer_json",
    "source_execution_json",
    "runtime_manifest_json",
    "history_snapshot_json",
    "catalog_json",
    "generation_configs_json",
    "effective_parameters_json",
    "rng_semantics_json",
    "ranking_evidence_json",
    "ticket_lineage_json",
)
ORIGINAL_TIME_FIELDS = ("generation_started_at", "generation_finished_at")
ORIGINAL_FIELDS = ORIGINAL_JSON_FIELDS + ORIGINAL_TIME_FIELDS

# Required leaves feed both SQL constraints and Python validation.
NATIVE_REQUIRED_PATHS: dict[str, dict[str, str]] = {
    "producer_json": {
        "schema_version": "text",
        "producer_id": "text",
        "producer_version": "text",
        "dependencies": "array",
        "digest": "text",
    },
    "source_execution_json": {
        "repository": "text",
        "commit": "text",
        "tree": "text",
        "loaded_code_sha256": "text",
    },
    "runtime_manifest_json": {
        "python": "object",
        "python.implementation": "text",
        "python.version": "text",
        "python.executable": "text",
        "python.executable_sha256": "text",
        "os": "text",
        "architecture": "text",
        "dependencies": "array",
        "sha256": "text",
    },
    "history_snapshot_json": {"reference": "text", "draws": "array", "sha256": "text"},
    "catalog_json": {"strategies": "array", "catalog_universe_sha256": "text"},
    "generation_configs_json": {"strategies": "array", "generation_config_sha256": "text"},
    "effective_parameters_json": {"strategies": "array", "sha256": "text"},
    "rng_semantics_json": {"stages": "array", "reproducibility_boundary": "text"},
    "ranking_evidence_json": {
        "objective": "text",
        "ranking_policy_version": "text",
        "evaluation_window": "text",
        "observations": "array",
        "evidence_payload_sha256": "text",
    },
    "ticket_lineage_json": {"buckets": "array", "upstream_payload_sha256": "text"},
}
NATIVE_ARRAY_REQUIRED_PATHS: dict[str, dict[str, str]] = {
    "producer_json.dependencies": {
        "locator": "text",
        "source_sha256": "text",
        "load_bearing_role": "text",
    },
    "runtime_manifest_json.dependencies": {
        "name": "text",
        "locator": "text",
        "versions": "object",
        "content_sha256": "text",
    },
    "history_snapshot_json.draws": {
        "lottery_type": "text",
        "draw_number": "text",
        "draw_date": "text",
        "main_numbers": "array",
        "special_number": "integer",
    },
    "catalog_json.strategies": {"strategy_id": "text", "version": "text"},
    "generation_configs_json.strategies": {
        "strategy_id": "text",
        "strategy_version": "text",
        "native_k": "integer",
        "parameters": "object",
        "rng_semantics": "object",
        "rng_semantics.behavior": "text",
        "rng_semantics.rng_source": "text",
        "rng_semantics.rng_state_rule": "text",
        "rng_semantics.configuration": "text",
        "rng_semantics.prestate_dependency": "text",
    },
    "effective_parameters_json.strategies": {
        "strategy_id": "text",
        "strategy_version": "text",
        "native_k": "integer",
        "parameters_json": "text",
        "generation_config_sha256": "text",
        "status": "text",
    },
    "rng_semantics_json.stages": {
        "strategy_id": "text",
        "stage": "text",
        "status": "text",
        "rng_semantics": "object",
        "rng_semantics.behavior": "text",
        "rng_semantics.rng_source": "text",
        "rng_semantics.rng_state_rule": "text",
        "rng_semantics.configuration": "text",
        "rng_semantics.prestate_dependency": "text",
        "seed_status": "text",
        "invocation_identity": "text",
        "replicate": "integer",
    },
    "ranking_evidence_json.observations": {
        "strategy_id": "text",
        "strategy_version": "text",
        "native_k": "integer",
        "draw_number": "text",
        "draw_date": "text",
        "causal_history_sha256": "text",
        "generation_config_sha256": "text",
        "status": "text",
        "producer_fingerprint": "text",
        "tickets": "array",
    },
    "ticket_lineage_json.buckets": {
        "native_k": "integer",
        "status": "text",
        "tickets": "array",
        "selector_status": "text",
        "selection_rule": "text",
        "tie_break": "text",
        "candidate_binding_sha256": "text",
        "evidence_payload_sha256": "text",
        "constructor_status": "text",
    },
}
LEGACY_MISSING = {
    "research_runs.rule_contract_id": "NOT_CAPTURED",
    **{field: "NOT_CAPTURED" for field in ORIGINAL_FIELDS},
    **{
        f"{field}.{path}": "NOT_CAPTURED"
        for field, paths in NATIVE_REQUIRED_PATHS.items()
        for path in paths
    },
    **{
        f"{inventory}[].{path}": "NOT_CAPTURED"
        for inventory, paths in NATIVE_ARRAY_REQUIRED_PATHS.items()
        for path in paths
    },
}
CONSENSUS_MISSING = {
    "research_runs.rule_contract_id": "NOT_APPLICABLE",
    **{field: "NOT_APPLICABLE" for field in ORIGINAL_FIELDS},
    **{
        f"{field}.{path}": "NOT_APPLICABLE"
        for field, paths in NATIVE_REQUIRED_PATHS.items()
        for path in paths
    },
    **{
        f"{inventory}[].{path}": "NOT_APPLICABLE"
        for inventory, paths in NATIVE_ARRAY_REQUIRED_PATHS.items()
        for path in paths
    },
}


def canonical_json(value: object) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def digest(value: object) -> str:
    return sha256(canonical_json(value).encode())


def object_json(value: str) -> dict[str, object]:
    decoded: object = json.loads(value)
    if not isinstance(decoded, dict) or canonical_json(cast(dict[str, object], decoded)) != value:
        raise ValueError("expected canonical JSON object")
    return cast(dict[str, object], decoded)


def require_sha(value: object) -> None:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ValueError("expected SHA-256")


def utc_text(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value):
        raise ValueError("UTC timestamp required")
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")


@dataclass(frozen=True, slots=True)
class LiveForecastInput:
    request_id: str
    request_sha256: str
    provenance_class: str
    forecast_stream_id: str
    forecast_stream_version: str
    target_json: str
    payload_bytes: bytes
    source_locator: str
    original_execution_json: str
    missing_provenance_json: str
    import_execution_json: str | None = None
    consensus_provenance_json: str | None = None

    @property
    def payload_sha256(self) -> str:
        return sha256(self.payload_bytes)

    @property
    def target(self) -> dict[str, object]:
        return object_json(self.target_json)

    @property
    def original(self) -> dict[str, object]:
        return object_json(self.original_execution_json)

    @property
    def consensus_provenance(self) -> dict[str, object] | None:
        if self.consensus_provenance_json is None:
            return None
        return object_json(self.consensus_provenance_json)

    @property
    def scope(self) -> tuple[str, str, str, str, str]:
        t = self.target
        return (
            str(t["lottery_type"]),
            str(t["target_draw_number"]),
            str(t["target_draw_date"]),
            self.forecast_stream_id,
            self.forecast_stream_version,
        )

    def validate(self) -> None:
        if not self.request_id.strip() or not self.source_locator.strip():
            raise ValueError("request and source locator required")
        require_sha(self.request_sha256)
        t = self.target
        for name in (
            "lottery_type",
            "target_draw_number",
            "target_draw_date",
            "scheduled_at",
            "timezone",
            "data_cutoff",
            "causal_history_sha256",
        ):
            if not isinstance(t.get(name), str) or not str(t[name]).strip():
                raise ValueError(f"missing target identity: {name}")
        if (
            t["lottery_type"] != "BIG_LOTTO"
            or t.get("forecast_horizon") != 1
            or int(str(t["data_cutoff"])) >= int(str(t["target_draw_number"]))
        ):
            raise ValueError("invalid causal target")
        if self.provenance_class != CANONICAL_CONSENSUS and (
            type(t.get("history_draw_count")) is not int or cast(int, t["history_draw_count"]) < 1
        ):
            raise ValueError("invalid causal target")
        if self.provenance_class == CANONICAL_CONSENSUS and (
            type(t.get("history_draw_count")) is not int
            or t["history_draw_count"] != CONSENSUS_TARGET_HISTORY_DRAW_COUNT
        ):
            raise ValueError("invalid consensus history count")
        require_sha(t["causal_history_sha256"])
        scheduled = datetime.fromisoformat(str(t["scheduled_at"]).replace("Z", "+00:00"))
        if scheduled.tzinfo is None:
            raise ValueError("scheduled time requires timezone")
        original = self.original
        if set(original) != set(ORIGINAL_FIELDS):
            raise ValueError("original execution field inventory mismatch")
        missing = object_json(self.missing_provenance_json)
        if self.provenance_class == "LEGACY_MATERIALIZED":
            if (
                self.forecast_stream_id != LEGACY_STREAM
                or self.forecast_stream_version != LEGACY_STREAM
                or self.payload_sha256 != LEGACY_SHA256
                or self.request_id != LEGACY_IMPORT_KEY
                or any(value is not None for value in original.values())
                or missing != LEGACY_MISSING
                or self.import_execution_json is None
                or self.consensus_provenance_json is not None
            ):
                raise ValueError(
                    "legacy import is restricted to the pinned artifact and NULL provenance"
                )
            imported = object_json(self.import_execution_json)
            for name in ("imported_at", "producer_id", "source_execution", "runtime_manifest"):
                if name not in imported:
                    raise ValueError(f"missing import execution: {name}")
            payload = cast(dict[str, object], json.loads(self.payload_bytes))
            expected = {
                "source_task": LEGACY_SOURCE_TASK,
                "materialization_task": LEGACY_MATERIALIZATION_TASK,
                "forecast_target": 115000087,
                "data_cutoff": 115000086,
                "forecast_horizon": 1,
                "history_draw_count": 2168,
                "causal_history_sha256": LEGACY_HISTORY_SHA256,
                "sealed_forecast_sha256": LEGACY_SEAL_SHA256,
                "target_outcome_inspected": False,
                "source_forecast_recomputed": False,
                "sealed_forecast_mutated": False,
            }
            if any(payload.get(k) != v for k, v in expected.items()):
                raise ValueError("pinned legacy identity mismatch")
            if (
                t["target_draw_number"] != "115000087"
                or t["data_cutoff"] != "115000086"
                or t["causal_history_sha256"] != LEGACY_HISTORY_SHA256
                or t["history_draw_count"] != 2168
                or t["scheduled_at"] != "2026-09-11T20:30:00+08:00"
                or t["target_draw_date"] != "2026-09-11"
                or t["timezone"] != "Asia/Taipei"
            ):
                raise ValueError("legacy target binding mismatch")
        elif self.provenance_class == "NATIVE_GENERATED":
            if (
                self.forecast_stream_id != NATIVE_STREAM
                or self.forecast_stream_version != NATIVE_STREAM_VERSION
                or missing
                or self.import_execution_json is not None
                or self.consensus_provenance_json is not None
            ):
                raise ValueError("invalid native provenance class")
            require_sha(t.get("schedule_authority_sha256"))
            _validate_native(original, self.payload_bytes, t)
        elif self.provenance_class == CANONICAL_CONSENSUS:
            if (
                self.forecast_stream_id != CONSENSUS_STREAM
                or self.forecast_stream_version != CONSENSUS_STREAM_VERSION
            ):
                raise ValueError("invalid canonical consensus stream")
            if (
                t["lottery_type"] != CONSENSUS_TARGET_LOTTERY_TYPE
                or t["target_draw_number"] != CONSENSUS_TARGET_DRAW_NUMBER
                or t["target_draw_date"] != CONSENSUS_TARGET_DRAW_DATE
                or t["scheduled_at"] != CONSENSUS_TARGET_SCHEDULED_AT
                or t["timezone"] != CONSENSUS_TARGET_TIMEZONE
                or t["data_cutoff"] != CONSENSUS_TARGET_DATA_CUTOFF
                or t["causal_history_sha256"] != CONSENSUS_TARGET_HISTORY_SHA256
                or t.get("forecast_horizon") != 1
                or type(t.get("schedule_authority_sha256")) is not str
                or self.import_execution_json is None
                or self.consensus_provenance_json is None
                or any(value is not None for value in original.values())
                or missing != CONSENSUS_MISSING
            ):
                raise ValueError("invalid canonical consensus provenance class")
            require_sha(t["schedule_authority_sha256"])
            payload = json.loads(self.payload_bytes)
            if not isinstance(payload, dict):
                raise ValueError("canonical consensus payload must be an object")
            _validate_consensus_payload(cast(dict[str, object], payload))
            _validate_consensus_provenance(
                self.consensus_provenance_json,
                cast(dict[str, object], payload),
                t,
                self.source_locator,
                self.payload_sha256,
            )
            _validate_consensus_import_execution(
                self.import_execution_json,
                cast(str, t["schedule_authority_sha256"]),
            )
        else:
            raise ValueError("unknown provenance class")


def _consensus_mapping(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return cast(dict[str, object], value)


def _consensus_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be non-empty text")
    return value


def _consensus_sha(value: object, label: str) -> str:
    require_sha(value)
    return cast(str, value)


def _consensus_datetime(value: object, label: str) -> None:
    text = _consensus_text(value, label)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{label} must be an ISO timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{label} must include a timezone")


def _consensus_link(value: object, label: str) -> dict[str, object]:
    link = _consensus_mapping(value, label)
    _consensus_text(link.get("locator"), f"{label}.locator")
    _consensus_sha(link.get("sha256"), f"{label}.sha256")
    return link


def _validate_consensus_streams(value: object, label: str) -> list[dict[str, object]]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must contain exactly 11 streams")
    items = cast(list[object], value)
    if len(items) != len(CONSENSUS_STREAM_SPECS):
        raise ValueError(f"{label} must contain exactly 11 streams")
    expected = {spec[0]: spec for spec in CONSENSUS_STREAM_SPECS}
    streams: list[dict[str, object]] = []
    identities: set[tuple[str, str, str]] = set()
    for index, item in enumerate(items):
        stream = _consensus_mapping(item, f"{label}[{index}]")
        if set(stream) != {
            "native_ticket_count",
            "prediction_run_id",
            "source_relative_path",
            "source_sha256",
            "strategy_id",
            "strategy_version",
        }:
            raise ValueError(f"{label}[{index}] field inventory mismatch")
        strategy_id = _consensus_text(stream.get("strategy_id"), f"{label}[{index}].strategy_id")
        strategy_version = _consensus_text(
            stream.get("strategy_version"), f"{label}[{index}].strategy_version"
        )
        prediction_run_id = _consensus_text(
            stream.get("prediction_run_id"), f"{label}[{index}].prediction_run_id"
        )
        source_path = _consensus_text(
            stream.get("source_relative_path"), f"{label}[{index}].source_relative_path"
        )
        if (
            source_path.startswith("/")
            or "\\" in source_path
            or any(part in {"", ".", ".."} for part in source_path.split("/"))
        ):
            raise ValueError(f"{label}[{index}].source_relative_path is unsafe")
        _consensus_sha(stream.get("source_sha256"), f"{label}[{index}].source_sha256")
        count = stream.get("native_ticket_count")
        if type(count) is not int or count < 1 or 6 % count != 0:
            raise ValueError(f"{label}[{index}].native_ticket_count is invalid")
        identity = (strategy_id, strategy_version, prediction_run_id)
        if identity in identities:
            raise ValueError(f"{label} contains duplicate stream identities")
        identities.add(identity)
        expected_spec = expected.get(strategy_id)
        if (
            expected_spec is None
            or (
                strategy_id,
                strategy_version,
                count,
                source_path,
            )
            != expected_spec
        ):
            raise ValueError(f"{label}[{index}] is not an Authority B stream")
        streams.append(stream)
    return streams


def _validate_consensus_payload(payload: dict[str, object]) -> None:
    expected_keys = {
        "aggregation_contract_approved_at",
        "aggregation_contract_review_id",
        "aggregation_method_id",
        "aggregation_method_version",
        "aggregation_unit",
        "correlated_family_policy",
        "created_at",
        "decision_ranking_formula",
        "exact_stream_ids",
        "final_decision_ranking",
        "final_recommended_output",
        "history_caveat",
        "history_draw_count",
        "history_sha256",
        "implementation_commit",
        "implementation_source_hashes",
        "implementation_tree",
        "lottery_type",
        "max_data_cutoff",
        "pre_outcome_temporal_integrity",
        "scheduled_at",
        "schema_version",
        "score_denominator",
        "stream_count",
        "stream_input_manifest_sha256",
        "stream_inputs",
        "target_draw",
        "target_result_used",
        "task_id",
        "tie_break",
        "upstream_task_id",
        "weight_policy",
    }
    if set(payload) != expected_keys:
        raise ValueError("canonical consensus payload field inventory mismatch")
    expected_scalars = {
        "schema_version": CONSENSUS_SCHEMA_VERSION,
        "aggregation_method_id": CONSENSUS_METHOD_ID,
        "aggregation_method_version": CONSENSUS_METHOD_VERSION,
        "aggregation_unit": CONSENSUS_AGGREGATION_UNIT,
        "weight_policy": CONSENSUS_WEIGHT_POLICY,
        "correlated_family_policy": CONSENSUS_CORRELATED_FAMILY_POLICY,
        "tie_break": CONSENSUS_TIE_BREAK,
        "score_denominator": CONSENSUS_SCORE_DENOMINATOR,
        "lottery_type": CONSENSUS_TARGET_LOTTERY_TYPE,
        "history_draw_count": CONSENSUS_TARGET_HISTORY_DRAW_COUNT,
        "history_sha256": CONSENSUS_TARGET_HISTORY_SHA256,
        "history_caveat": "YES",
        "pre_outcome_temporal_integrity": "PASS",
        "target_result_used": False,
        "stream_count": len(CONSENSUS_STREAM_SPECS),
        "task_id": CONSENSUS_PRODUCTION_TASK_ID,
        "upstream_task_id": CONSENSUS_UPSTREAM_TASK_ID,
        "aggregation_contract_review_id": "B649_11_STREAM_CANONICAL_AGGREGATION_CTO_REVIEW_R1",
        "aggregation_contract_approved_at": "2026-09-10T05:50:29Z",
        "decision_ranking_formula": (
            "U(n)=sum_i((6/k_i)*c_i(n)); rank by U(n) descending, then number ascending; "
            "each stream has equal weight and c_i(n) counts native ticket positions containing n"
        ),
    }
    for key, expected in expected_scalars.items():
        if payload.get(key) != expected:
            raise ValueError(f"canonical consensus payload {key} mismatch")
    target_draw = _consensus_mapping(payload.get("target_draw"), "payload.target_draw")
    if target_draw != {
        "draw_date": CONSENSUS_TARGET_DRAW_DATE,
        "draw_number": CONSENSUS_TARGET_DRAW_NUMBER,
    }:
        raise ValueError("canonical consensus target mismatch")
    cutoff = _consensus_mapping(payload.get("max_data_cutoff"), "payload.max_data_cutoff")
    if cutoff != {"draw_date": "2026-09-08", "draw_number": CONSENSUS_TARGET_DATA_CUTOFF}:
        raise ValueError("canonical consensus cutoff mismatch")
    _consensus_datetime(payload.get("created_at"), "payload.created_at")
    _consensus_text(payload.get("scheduled_at"), "payload.scheduled_at")
    if payload["scheduled_at"] != CONSENSUS_TARGET_SCHEDULED_AT:
        raise ValueError("canonical consensus schedule mismatch")
    _consensus_sha(
        payload.get("stream_input_manifest_sha256"),
        "payload.stream_input_manifest_sha256",
    )
    streams = _validate_consensus_streams(payload.get("stream_inputs"), "payload.stream_inputs")
    if payload.get("exact_stream_ids") != [spec[0] for spec in CONSENSUS_STREAM_SPECS]:
        raise ValueError("canonical consensus stream id inventory mismatch")
    if payload.get("stream_input_manifest_sha256") != digest(streams):
        raise ValueError("canonical consensus stream manifest hash mismatch")
    source_hashes = payload.get("implementation_source_hashes")
    expected_source_hashes = [
        {"path": path, "sha256": source_sha}
        for path, source_sha in CONSENSUS_IMPLEMENTATION_SOURCE_HASHES
    ]
    if source_hashes != expected_source_hashes:
        raise ValueError("canonical consensus implementation source lineage mismatch")
    if payload.get("implementation_commit") != CONSENSUS_IMPLEMENTATION_COMMIT:
        raise ValueError("canonical consensus implementation commit mismatch")
    if payload.get("implementation_tree") != CONSENSUS_IMPLEMENTATION_TREE:
        raise ValueError("canonical consensus implementation tree mismatch")
    ranking = payload.get("final_decision_ranking")
    expected_ranking = [
        {"number": number, "rank": rank, "support_units": support}
        for rank, (number, support) in enumerate(CONSENSUS_DECISION_RANKING, start=1)
    ]
    if ranking != expected_ranking:
        raise ValueError("canonical consensus final ranking mismatch")
    if payload.get("final_recommended_output") != [
        {"predicted_numbers": [4, 12, 24, 25, 26, 29], "ticket_position": 1}
    ]:
        raise ValueError("canonical consensus final recommendation mismatch")
    _reject_consensus_outcome_keys(payload)


def _validate_consensus_provenance(
    raw: str,
    payload: dict[str, object],
    target: dict[str, object],
    source_locator: str,
    payload_sha256: str,
) -> None:
    provenance = object_json(raw)
    expected_keys = {
        "algorithm",
        "aggregation_reexecution",
        "candidate",
        "contract_version",
        "final_decision_ranking",
        "final_recommended_output",
        "generated_at",
        "implementation",
        "production",
        "source_provenance",
        "strategy_reexecution",
        "streams",
        "target",
    }
    if set(provenance) != expected_keys:
        raise ValueError("canonical consensus provenance field inventory mismatch")
    if provenance.get("contract_version") != CONSENSUS_PROVENANCE_SCHEMA_VERSION:
        raise ValueError("canonical consensus provenance schema mismatch")
    candidate = _consensus_link(provenance.get("candidate"), "candidate")
    if candidate != {"locator": source_locator, "sha256": payload_sha256}:
        raise ValueError("canonical consensus candidate binding mismatch")
    implementation = _consensus_mapping(provenance.get("implementation"), "implementation")
    expected_implementation = {
        "commit": payload["implementation_commit"],
        "tree": payload["implementation_tree"],
        "source_hashes": payload["implementation_source_hashes"],
    }
    if implementation != expected_implementation:
        raise ValueError("canonical consensus implementation binding mismatch")
    for key in ("commit", "tree"):
        value = _consensus_text(implementation.get(key), f"implementation.{key}")
        if re.fullmatch(r"[0-9a-f]{40}", value) is None:
            raise ValueError(f"implementation.{key} must be a full Git identity")
    source_provenance = _consensus_mapping(provenance.get("source_provenance"), "source_provenance")
    if source_provenance != {
        "locator": source_locator,
        "sha256": payload_sha256,
        "document": provenance.get("production"),
    }:
        raise ValueError("canonical consensus source provenance mismatch")
    production = _consensus_mapping(provenance.get("production"), "production")
    expected_production = {
        "task_id": payload["task_id"],
        "upstream_task_id": payload["upstream_task_id"],
        "created_at": payload["created_at"],
        "pre_outcome_temporal_integrity": payload["pre_outcome_temporal_integrity"],
        "stream_input_manifest_sha256": payload["stream_input_manifest_sha256"],
        "implementation": expected_implementation,
    }
    if production != expected_production:
        raise ValueError("canonical consensus production lineage mismatch")
    algorithm = _consensus_mapping(provenance.get("algorithm"), "algorithm")
    expected_algorithm = {
        "algorithm_id": "build_canonical_consensus",
        "method_id": payload["aggregation_method_id"],
        "method_version": payload["aggregation_method_version"],
        "aggregation_unit": payload["aggregation_unit"],
        "weight_policy": payload["weight_policy"],
        "correlated_family_policy": payload["correlated_family_policy"],
        "tie_break": payload["tie_break"],
        "score_denominator": payload["score_denominator"],
        "decision_ranking_formula": payload["decision_ranking_formula"],
    }
    if algorithm != expected_algorithm:
        raise ValueError("canonical consensus algorithm identity mismatch")
    if provenance.get("generated_at") != payload["created_at"]:
        raise ValueError("canonical consensus generated_at mismatch")
    _consensus_datetime(provenance.get("generated_at"), "generated_at")
    expected_target = {
        "lottery_type": CONSENSUS_TARGET_LOTTERY_TYPE,
        "draw_number": CONSENSUS_TARGET_DRAW_NUMBER,
        "draw_date": CONSENSUS_TARGET_DRAW_DATE,
        "scheduled_at": CONSENSUS_TARGET_SCHEDULED_AT,
        "timezone": CONSENSUS_TARGET_TIMEZONE,
        "cutoff": CONSENSUS_TARGET_DATA_CUTOFF,
        "history_draw_count": CONSENSUS_TARGET_HISTORY_DRAW_COUNT,
        "causal_history_sha256": CONSENSUS_TARGET_HISTORY_SHA256,
        "temporal_class": "PRE_DRAW",
        "target_result_used": False,
        "schedule_authority_sha256": target["schedule_authority_sha256"],
    }
    if _consensus_mapping(provenance.get("target"), "target") != expected_target:
        raise ValueError("canonical consensus target binding mismatch")
    if {
        key: target.get(key)
        for key in (
            "lottery_type",
            "target_draw_number",
            "target_draw_date",
            "scheduled_at",
            "timezone",
            "data_cutoff",
            "history_draw_count",
            "causal_history_sha256",
            "schedule_authority_sha256",
        )
    } != {
        "lottery_type": CONSENSUS_TARGET_LOTTERY_TYPE,
        "target_draw_number": CONSENSUS_TARGET_DRAW_NUMBER,
        "target_draw_date": CONSENSUS_TARGET_DRAW_DATE,
        "scheduled_at": CONSENSUS_TARGET_SCHEDULED_AT,
        "timezone": CONSENSUS_TARGET_TIMEZONE,
        "data_cutoff": CONSENSUS_TARGET_DATA_CUTOFF,
        "history_draw_count": CONSENSUS_TARGET_HISTORY_DRAW_COUNT,
        "causal_history_sha256": CONSENSUS_TARGET_HISTORY_SHA256,
        "schedule_authority_sha256": target["schedule_authority_sha256"],
    }:
        raise ValueError("canonical consensus target and payload disagree")
    if provenance.get("strategy_reexecution") != "NO":
        raise ValueError("canonical consensus provenance re-executed strategy")
    if provenance.get("aggregation_reexecution") != "NO":
        raise ValueError("canonical consensus provenance re-executed aggregation")
    if _validate_consensus_streams(provenance.get("streams"), "streams") != payload.get(
        "stream_inputs"
    ):
        raise ValueError("canonical consensus stream lineage mismatch")
    if provenance.get("final_decision_ranking") != payload.get("final_decision_ranking"):
        raise ValueError("canonical consensus ranking lineage mismatch")
    if provenance.get("final_recommended_output") != payload.get("final_recommended_output"):
        raise ValueError("canonical consensus recommendation lineage mismatch")


def _validate_consensus_import_execution(raw: str, schedule_hash: str) -> None:
    imported = object_json(raw)
    expected_keys = {
        "activation_event",
        "aggregation_execution",
        "authorization_evidence_reference",
        "command_runtime_identity",
        "execution_source",
        "native_generation",
        "promotion_attempted_at",
        "promotion_executor_identity",
        "schedule_authority_sha256",
    }
    if set(imported) != expected_keys:
        raise ValueError("canonical consensus import execution field inventory mismatch")
    for name in (
        "promotion_executor_identity",
        "authorization_evidence_reference",
        "activation_event",
        "aggregation_execution",
        "native_generation",
    ):
        _consensus_text(imported.get(name), f"import_execution.{name}")
    if imported["activation_event"] != "CANONICAL_CONSENSUS_PROMOTION_IMPORT":
        raise ValueError("invalid canonical consensus activation event")
    if imported["aggregation_execution"] != "NOT_PERFORMED":
        raise ValueError("canonical consensus aggregation was re-executed")
    if imported["native_generation"] != "NOT_PERFORMED":
        raise ValueError("canonical consensus native generation was re-executed")
    if imported.get("schedule_authority_sha256") != schedule_hash:
        raise ValueError("canonical consensus schedule hash binding mismatch")
    _consensus_sha(
        imported.get("schedule_authority_sha256"),
        "import_execution.schedule_authority_sha256",
    )
    _consensus_datetime(imported.get("promotion_attempted_at"), "promotion_attempted_at")
    execution_source = _consensus_mapping(imported.get("execution_source"), "execution_source")
    _consensus_text(execution_source.get("source_id"), "execution_source.source_id")
    _consensus_text(execution_source.get("source_version"), "execution_source.source_version")
    runtime = _consensus_mapping(
        imported.get("command_runtime_identity"), "command_runtime_identity"
    )
    _consensus_text(runtime.get("python"), "command_runtime_identity.python")
    _consensus_text(runtime.get("executable"), "command_runtime_identity.executable")
    command = runtime.get("command")
    if (
        not isinstance(command, list)
        or not command
        or any(not isinstance(part, str) or not part for part in cast(list[object], command))
    ):
        raise ValueError("command_runtime_identity.command must be a non-empty argv")


def _reject_consensus_outcome_keys(value: object) -> None:
    forbidden = {
        "outcome",
        "result",
        "official_outcome",
        "winning_numbers",
        "main_numbers",
        "special_number",
    }
    if isinstance(value, dict):
        entries = cast(dict[str, object], value)
        for key, item in entries.items():
            if key in forbidden:
                raise ValueError(f"canonical consensus payload contains forbidden key: {key}")
            _reject_consensus_outcome_keys(item)
    elif isinstance(value, list):
        items = cast(list[object], value)
        for item in items:
            _reject_consensus_outcome_keys(item)


def _json_leaf(value: object, path: str) -> object:
    for part in path.split("."):
        if not isinstance(value, dict):
            return None
        value = cast(dict[str, object], value).get(part)
    return value


def _validate_native(
    original: dict[str, object], payload_bytes: bytes, target: dict[str, object]
) -> None:
    types: dict[str, type] = {"text": str, "object": dict, "array": list}
    groups: dict[str, dict[str, object]] = {}
    for field, paths in NATIVE_REQUIRED_PATHS.items():
        value = original[field]
        if not isinstance(value, str):
            raise ValueError(f"native original field is missing: {field}")
        group = object_json(value)
        for name, kind in paths.items():
            leaf = _json_leaf(group, name)
            if not isinstance(leaf, types[kind]) or leaf in ("", None):
                raise ValueError(f"native provenance missing: {field}.{name}")
        groups[field] = group
    for field in ORIGINAL_TIME_FIELDS:
        if not isinstance(original[field], str):
            raise ValueError("native execution timestamps required")
        utc_text(datetime.fromisoformat(str(original[field]).replace("Z", "+00:00")))
    if str(original["generation_started_at"]) > str(original["generation_finished_at"]):
        raise ValueError("generation timestamps reversed")
    payload = cast(dict[str, object], json.loads(payload_bytes))
    if (
        canonical_json(payload).encode() != payload_bytes
        or payload.get("fixture_only") is not False
    ):
        raise ValueError("native payload requires canonical production serialization")
    producer = groups["producer_json"]
    if digest({k: v for k, v in producer.items() if k != "digest"}) != producer["digest"]:
        raise ValueError("producer digest mismatch")
    dependencies = cast(list[dict[str, object]], producer["dependencies"])
    if not dependencies:
        raise ValueError("native producer dependencies required")
    for dependency in dependencies:
        require_sha(dependency.get("source_sha256"))
        if not dependency.get("locator") or not dependency.get("load_bearing_role"):
            raise ValueError("incomplete producer dependency")
    source = groups["source_execution_json"]
    for key in ("commit", "tree"):
        if re.fullmatch(r"[0-9a-f]{40}", str(source[key])) is None:
            raise ValueError("full executed Git identity required")
    require_sha(source["loaded_code_sha256"])
    for field in ("runtime_manifest_json", "effective_parameters_json"):
        group = groups[field]
        if group["sha256"] != digest({k: v for k, v in group.items() if k != "sha256"}):
            raise ValueError(f"{field} digest mismatch")
    history = groups["history_snapshot_json"]
    if (
        digest(history["draws"]) != target["causal_history_sha256"]
        or history["sha256"] != target["causal_history_sha256"]
        or len(cast(list[object], history["draws"])) != target["history_draw_count"]
    ):
        raise ValueError("immutable causal history mismatch")
    if groups["catalog_json"]["strategies"] != payload.get("catalog"):
        raise ValueError("catalog payload binding mismatch")
    if groups["catalog_json"]["catalog_universe_sha256"] != digest(payload["catalog"]):
        raise ValueError("catalog digest mismatch")
    config = groups["generation_configs_json"]
    if config["strategies"] != payload.get("generation_configs") or config[
        "generation_config_sha256"
    ] != digest({"fixture_only": False, "strategies": config["strategies"]}):
        raise ValueError("generation config binding mismatch")
    evidence = groups["ranking_evidence_json"]
    if (
        evidence["objective"] != "OFFICIAL_ANY_PRIZE"
        or evidence["ranking_policy_version"] != NATIVE_STREAM_VERSION
        or evidence["evaluation_window"] != "FULL"
        or digest(evidence["observations"]) != evidence["evidence_payload_sha256"]
        or evidence["evidence_payload_sha256"] != payload.get("evidence_payload_sha256")
    ):
        raise ValueError("ranking evidence binding mismatch")
    lineage = groups["ticket_lineage_json"]
    if lineage["upstream_payload_sha256"] != sha256(payload_bytes):
        raise ValueError("lineage payload binding mismatch")
    buckets = cast(list[dict[str, object]], payload["buckets"])
    identity = payload.get("identity")
    if not isinstance(identity, dict):
        raise ValueError("native payload identity required")
    identity = cast(dict[str, object], identity)
    expected_identity = {
        "lottery_type": target["lottery_type"],
        "target_draw_number": target["target_draw_number"],
        "target_draw_date": target["target_draw_date"],
        "schedule_authority_sha256": target["schedule_authority_sha256"],
        "history_cutoff": target["data_cutoff"],
        "history_payload_sha256": target["causal_history_sha256"],
        "producer_fingerprint": producer["digest"],
        "catalog_universe_sha256": groups["catalog_json"]["catalog_universe_sha256"],
        "generation_config_sha256": config["generation_config_sha256"],
    }
    if any(identity.get(key) != value for key, value in expected_identity.items()):
        raise ValueError("native payload and provenance identities disagree")
    runtime = groups["runtime_manifest_json"]
    python = cast(dict[str, object], runtime["python"])
    for key in ("implementation", "version", "executable", "executable_sha256"):
        if not python.get(key):
            raise ValueError("incomplete Python runtime identity")
    require_sha(python["executable_sha256"])
    if not runtime["dependencies"]:
        raise ValueError("runtime dependency manifest is empty")
    for dep in cast(list[dict[str, object]], runtime["dependencies"]):
        require_sha(dep.get("content_sha256"))
        if not dep.get("name") or not dep.get("locator") or not dep.get("versions"):
            raise ValueError("incomplete runtime dependency")
    config_rows = cast(list[dict[str, object]], config["strategies"])
    configs_by_id = {str(row["strategy_id"]): row for row in config_rows}
    parameter_rows = cast(
        list[dict[str, object]], groups["effective_parameters_json"]["strategies"]
    )
    rng_rows = cast(list[dict[str, object]], groups["rng_semantics_json"]["stages"])
    if (
        not configs_by_id
        or len(configs_by_id) != len(config_rows)
        or len(parameter_rows) != len(config_rows)
        or len(rng_rows) != len(config_rows)
        or {row.get("strategy_id") for row in parameter_rows} != set(configs_by_id)
        or {row.get("strategy_id") for row in rng_rows} != set(configs_by_id)
    ):
        raise ValueError("effective configuration and RNG inventory mismatch")
    for row in parameter_rows:
        item = configs_by_id[str(row["strategy_id"])]
        if (
            row.get("parameters_json") != canonical_json(item["parameters"])
            or row.get("generation_config_sha256") != digest(item)
            or row.get("strategy_version") != item["strategy_version"]
            or row.get("native_k") != item["native_k"]
        ):
            raise ValueError("effective parameter binding mismatch")
        if row.get("status") == "EXECUTED":
            if not isinstance(row.get("constructor_defaults"), dict) or not isinstance(
                row.get("instance_state"), dict
            ):
                raise ValueError("effective adapter state was not captured")
        elif row.get("status") != "NOT_EXECUTED":
            raise ValueError("unknown effective parameter execution status")
    for row in rng_rows:
        rng = row.get("rng_semantics")
        if (
            not isinstance(rng, dict)
            or rng != configs_by_id[str(row["strategy_id"])]["rng_semantics"]
        ):
            raise ValueError("RNG configuration binding mismatch")
        rng = cast(dict[str, object], rng)
        for key in (
            "behavior",
            "rng_source",
            "rng_state_rule",
            "configuration",
            "prestate_dependency",
        ):
            if not rng.get(key):
                raise ValueError(f"missing RNG execution provenance: {key}")
        if rng["behavior"] == "DETERMINISTIC":
            if rng.get("seed") is not None or row.get("seed_status") != "NOT_APPLICABLE":
                raise ValueError("deterministic execution cannot invent a seed")
        elif rng["behavior"] == "SEEDED_STOCHASTIC":
            if (
                type(rng.get("seed")) not in (str, int)
                or row.get("seed_status") != "EFFECTIVE_SEED_CAPTURED"
            ):
                raise ValueError("seeded execution requires the effective seed")
            if "seed_material" in rng and sha256(str(rng["seed_material"]).encode()) != rng.get(
                "seed_digest"
            ):
                raise ValueError("seed derivation binding mismatch")
        elif rng["behavior"] == "UNSEEDED_STOCHASTIC":
            if row.get("seed_status") != "uncaptured_process_global_rng_state":
                raise ValueError("unseeded execution cannot claim exact regeneration")
        else:
            raise ValueError("unknown RNG behavior")
        if not row.get("invocation_identity") or row.get("replicate") != 1:
            raise ValueError("missing RNG invocation identity")
    lines = cast(list[dict[str, object]], lineage["buckets"])
    if len(lines) != len(buckets):
        raise ValueError("incomplete K-ticket lineage")
    for line, bucket in zip(lines, buckets, strict=True):
        if (
            line.get("native_k") != bucket["native_k"]
            or line.get("tickets") != bucket["tickets"]
            or line.get("status") != bucket["status"]
            or line.get("candidate_binding_sha256") != digest(bucket["candidates"])
            or line.get("evidence_payload_sha256") != evidence["evidence_payload_sha256"]
            or line.get("selection_rule") != NATIVE_STREAM_VERSION
            or line.get("tie_break") != bucket["display_tie_break"]
        ):
            raise ValueError("K-ticket lineage binding mismatch")
        if line.get("constructor_status") == "EXECUTED":
            for key in ("adapter_source_sha256", "generation_config_sha256", "rng_binding_sha256"):
                require_sha(line.get(key))
            if (
                not line.get("adapter_locator")
                or not line.get("adapter_version")
                or not line.get("selected_strategy")
            ):
                raise ValueError("incomplete executed constructor identity")
        elif (
            line.get("constructor_status") != "NOT_EXECUTED" or bucket.get("status") == "AVAILABLE"
        ):
            raise ValueError("executed constructor cannot be reported NOT_EXECUTED")
    if not any(
        b.get("native_k") == 20
        and b.get("tickets") == []
        and b.get("status") == "UNAVAILABLE_NO_CANONICAL_NATIVE_K20_STRATEGY"
        for b in buckets
    ):
        raise ValueError("native K20 authority mismatch")


@dataclass(frozen=True, slots=True)
class LiveForecastResult:
    run_id: str
    version: int
    pointer_advanced: bool
    idempotent: bool
    payload_sha256: str
    provenance_envelope_sha256: str
