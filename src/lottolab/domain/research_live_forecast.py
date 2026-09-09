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

# The same top-level required leaves feed SQL constraints and Python validation.
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
LEGACY_MISSING = {
    "research_runs.rule_contract_id": "NOT_CAPTURED",
    **{field: "NOT_CAPTURED" for field in ORIGINAL_FIELDS},
    **{
        f"{field}.{path}": "NOT_CAPTURED"
        for field, paths in NATIVE_REQUIRED_PATHS.items()
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
            or type(t.get("history_draw_count")) is not int
            or cast(int, t["history_draw_count"]) < 1
            or int(str(t["data_cutoff"])) >= int(str(t["target_draw_number"]))
        ):
            raise ValueError("invalid causal target")
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
            ):
                raise ValueError("invalid native provenance class")
            require_sha(t.get("schedule_authority_sha256"))
            _validate_native(original, self.payload_bytes, t)
        else:
            raise ValueError("unknown provenance class")


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
            if not isinstance(group.get(name), types[kind]) or group[name] in ("", None):
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
