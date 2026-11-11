"""Read-only, checksum-pinned K5 historical prediction/result events."""

# FastAPI discovers endpoint callables through route registration decorators.
# pyright: reportUnusedFunction=false

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from http import HTTPStatus
from pathlib import Path, PurePosixPath
from typing import Any, Literal, cast
from urllib.parse import parse_qs

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

API_VERSION = "v1"
EVENT_SCHEMA_VERSION = "backtest-row-evidence/1.0.0"
API_PATH = "/api/v1/research/backtests/draw-events"
EventRecordType = Literal["PREDICTION", "OFFICIAL_RESULT"]

BASE_EVENTS_PATH = Path(
    "/Users/kelvin/VibeCoding-WorkSpace/.task-data/20261103/"
    "NUMBER2_A_ROW_EVIDENCE_BATCH_WRITER_V2_20261103_R1/batch_import_events.jsonl"
)
VARIANT_EVENTS_PATH = Path(
    "/Users/kelvin/VibeCoding-WorkSpace/.task-data/20261103/"
    "NUMBER2_A_VARIANT_ROW_EVIDENCE_V2_IMPORT_20261103_R1/variant_events.jsonl"
)
BASE_EVENTS_SHA256 = "e7d665e5a43695a83fc0c715d326214e9c153726f274b5bb13c7ac0a1472d272"
VARIANT_EVENTS_SHA256 = "b8b5265e1931e5adcbb779727712b25494f5eb5ce13390a25f9c60d20a04f41c"

IDENTITY_FIELDS = (
    "lottery_type",
    "K",
    "target_draw",
    "strategy_id",
    "strategy_version",
    "policy_version",
    "algorithm_version",
    "run_identity",
    "history_cutoff",
)
QUERY_IDENTITY_FIELDS = (
    ("strategy_id", "strategy_id"),
    ("strategy_version", "strategy_version"),
    ("policy_version", "policy_version"),
    ("algorithm_version", "algorithm_version"),
    ("run_identity", "run_identity"),
    ("target_draw", "target_draw"),
)
QUERY_PARAMETERS = frozenset(
    {
        "strategy_id",
        "strategy_version",
        "policy_version",
        "algorithm_version",
        "run_identity",
        "K",
        "target_draw",
        "limit",
        "offset",
        "data_version",
    }
)

# Each tuple is the complete pinned policy/run identity, its source file group,
# its receipt-backed any-prize count, and its original source_variant value.
POLICY_IDENTITIES = (
    (
        "legacy_biglotto__backtest_biglotto_coldpool_15__2a80423e3cf5",
        "legacy-source-49a25effa62f-2a80423e3cf5",
        "native",
        "NOT_ESTABLISHED",
        "historical-import:NUMBER2_A_REAL_ROW_EVIDENCE_IMPORT_20261103_R1:K5",
        "base",
        251,
        None,
    ),
    (
        "GREEDY_DISJOINT_K",
        "greedy-disjoint-fixed-v1",
        "UNSPECIFIED_IN_SOURCE",
        "git-blob:5511f67d981f7f8a1c33183c966d76ee50249d7d",
        "historical-import:NUMBER2_A_REAL_ROW_EVIDENCE_IMPORT_20261103_R1:K5",
        "base",
        200,
        None,
    ),
    (
        "legacy_biglotto__enhanced_dual_bet_predictor__d5b3de348d01",
        "legacy-source-49a25effa62f-d5b3de348d01",
        "l3-enhanced-dual-bet-single-invalid-greedy-fallback-v1",
        "l3-enhanced-dual-bet-single-invalid-greedy-fallback-v1",
        "historical-row-evidence-v2:L3-single-invalid-Greedy-fallback-v1",
        "variants",
        209,
        "L3_ENHANCED_DUAL_BET_REPAIRED",
    ),
    (
        "SPARSE_SUBSET_SCAN_CONDITIONAL_EDGE_GATE",
        "EH27_R1_FIXED_30_V1",
        "one-slot-min-overlap-v1",
        "EH27_CAUSAL_CLEAN_R2",
        "historical-row-evidence-v2:EH27-counterfactual-23-roster-clean-history-r2",
        "variants",
        207,
        "counterfactual_23_roster_clean_history_r2",
    ),
)
EXPECTED_POLICY_BY_IDENTITY = {
    identity[:5]: {
        "source_id": identity[5],
        "successes": identity[6],
        "source_variant": identity[7],
    }
    for identity in POLICY_IDENTITIES
}


class EventSourceError(RuntimeError):
    """Raised when fixed event sources fail their integrity or schema checks."""


class _BadRequest(ValueError):
    """Raised for invalid or unsupported query parameters."""


class _AmbiguousQuery(ValueError):
    """Raised when a strategy filter leaves multiple exact identities."""


@dataclass(frozen=True)
class EventSourceSpec:
    source_id: str
    path: Path
    file_name: str
    sha256: str
    expected_events: int


@dataclass(frozen=True)
class DrawEvent:
    identity: tuple[Any, ...]
    source_id: str
    prediction: Mapping[str, Any]
    official_result: Mapping[str, Any]


@dataclass(frozen=True)
class EventIndex:
    records: tuple[DrawEvent, ...]
    data_version: str
    source_manifest: Mapping[str, Any]


def _source_specs() -> tuple[EventSourceSpec, ...]:
    return (
        EventSourceSpec(
            source_id="base",
            path=BASE_EVENTS_PATH,
            file_name="batch_import_events.jsonl",
            sha256=BASE_EVENTS_SHA256,
            expected_events=5268,
        ),
        EventSourceSpec(
            source_id="variants",
            path=VARIANT_EVENTS_PATH,
            file_name="variant_events.jsonl",
            sha256=VARIANT_EVENTS_SHA256,
            expected_events=5268,
        ),
    )


def _event_identity(event: Mapping[str, Any]) -> tuple[Any, ...]:
    try:
        identity = tuple(event[field] for field in IDENTITY_FIELDS)
    except KeyError as exc:
        raise EventSourceError("An event is missing a required identity field.") from exc
    if (
        identity[0] != "BIG_LOTTO"
        or identity[1] != 5
        or not all(isinstance(value, str) and value for value in identity[2:])
    ):
        raise EventSourceError("An event has an invalid K5 identity.")
    return identity


def _validate_event(event: Any, source_id: str) -> tuple[tuple[Any, ...], str]:
    if not isinstance(event, dict):
        raise EventSourceError("An event is not a JSON object.")
    event = cast(dict[str, Any], event)
    if event.get("schema_version") != EVENT_SCHEMA_VERSION:
        raise EventSourceError("An event has an unsupported schema version.")
    record_type = event.get("record_type")
    if record_type not in {"PREDICTION", "OFFICIAL_RESULT"}:
        raise EventSourceError("An event has an unsupported record type.")
    record_type = cast(EventRecordType, record_type)
    identity = _event_identity(event)
    policy_identity = identity[3:8]
    expected = EXPECTED_POLICY_BY_IDENTITY.get(policy_identity)
    if expected is None or expected["source_id"] != source_id:
        raise EventSourceError("An event does not match one of the four pinned policies.")
    if record_type == "PREDICTION":
        tickets_value = event.get("ordered_tickets")
        if not isinstance(tickets_value, list):
            raise EventSourceError("A K5 prediction does not contain five ordered tickets.")
        tickets = cast(list[Any], tickets_value)
        if len(tickets) != 5:
            raise EventSourceError("A K5 prediction does not contain five ordered tickets.")
        for ticket_value in tickets:
            if not isinstance(ticket_value, list) or len(cast(list[Any], ticket_value)) != 6:
                raise EventSourceError("A K5 prediction does not contain five ordered tickets.")
    else:
        if not isinstance(event.get("candidate_any_prize"), bool):
            raise EventSourceError("An official result is missing its saved any-prize flag.")
        result = event.get("winning_result")
        tiers = event.get("ticket_prize_tiers")
        if not isinstance(result, dict) or not isinstance(tiers, list):
            raise EventSourceError(
                "An official result is missing its saved result or ticket tiers."
            )
        if len(cast(list[Any], tiers)) != 5:
            raise EventSourceError(
                "An official result is missing its saved result or ticket tiers."
            )
    return identity, record_type


def _stable_json_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def _validate_pair_metadata(
    prediction: Mapping[str, Any], official_result: Mapping[str, Any]
) -> None:
    for field in (
        "schema_version",
        "lottery_type",
        "K",
        "target_draw",
        "strategy_id",
        "strategy_version",
        "policy_version",
        "algorithm_version",
        "run_identity",
        "history_cutoff",
        "source_variant",
        "method_id",
        "source_record_label",
        "policy_source",
        "native_fallback_class",
        "native_used",
        "fallback_reason",
    ):
        if (field in prediction or field in official_result) and prediction.get(
            field
        ) != official_result.get(field):
            raise EventSourceError("Prediction and official-result metadata conflict.")


def _insert_event(
    raw_events: dict[tuple[Any, ...], dict[str, Mapping[str, Any]]],
    event: Any,
    source_id: str,
) -> tuple[tuple[Any, ...], str]:
    identity, record_type = _validate_event(event, source_id)
    records = raw_events.setdefault(identity, {})
    if record_type in records:
        raise EventSourceError("A duplicate event identity was found.")
    records[record_type] = event
    return identity, record_type


def _pair_event_records(
    raw_events: Mapping[tuple[Any, ...], Mapping[str, Mapping[str, Any]]],
    *,
    expected_identities: int = 5268,
) -> list[DrawEvent]:
    if len(raw_events) != expected_identities:
        raise EventSourceError("The pinned event set has an unexpected identity count.")
    paired_records: list[DrawEvent] = []
    for identity, pair in raw_events.items():
        if set(pair) != {"PREDICTION", "OFFICIAL_RESULT"}:
            raise EventSourceError("An event identity has an orphan prediction or result.")
        prediction = pair["PREDICTION"]
        official_result = pair["OFFICIAL_RESULT"]
        if _event_identity(prediction) != identity or _event_identity(official_result) != identity:
            raise EventSourceError("An event does not match its indexed identity.")
        _validate_pair_metadata(prediction, official_result)
        policy_identity = identity[3:8]
        try:
            source_id = EXPECTED_POLICY_BY_IDENTITY[policy_identity]["source_id"]
        except KeyError as exc:
            raise EventSourceError("An event identity is not in the pinned policy set.") from exc
        if not isinstance(source_id, str):
            raise EventSourceError("An event identity has an invalid source identifier.")
        paired_records.append(
            DrawEvent(
                identity=identity,
                source_id=source_id,
                prediction=prediction,
                official_result=official_result,
            )
        )
    paired_records.sort(key=lambda record: record.identity)
    return paired_records


def load_event_index(
    source_specs: Sequence[EventSourceSpec] | None = None,
) -> EventIndex:
    """Read the two fixed JSONL sources once and construct a paired immutable view."""
    specs = tuple(source_specs) if source_specs is not None else _source_specs()
    if {spec.source_id for spec in specs} != {"base", "variants"} or len(specs) != 2:
        raise EventSourceError("The event source set is incomplete.")

    raw_events: dict[tuple[Any, ...], dict[str, Mapping[str, Any]]] = defaultdict(dict)
    source_metadata: list[dict[str, Any]] = []
    per_policy_counts: dict[tuple[str, ...], dict[str, Any]] = {
        identity[:5]: {"targets": set(), "successes": 0} for identity in POLICY_IDENTITIES
    }
    target_sets: list[set[str]] = []

    for spec in specs:
        try:
            raw = spec.path.read_bytes()
        except OSError as exc:
            raise EventSourceError("A checksum-pinned event source is unavailable.") from exc
        observed_sha256 = hashlib.sha256(raw).hexdigest()
        if observed_sha256 != spec.sha256:
            raise EventSourceError("A checksum-pinned event source failed integrity validation.")
        lines = raw.splitlines()
        if len(lines) != spec.expected_events:
            raise EventSourceError("A checksum-pinned event source has an unexpected event count.")

        record_counts: Counter[str] = Counter()
        source_targets: set[str] = set()
        for line in lines:
            try:
                event = json.loads(line)
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise EventSourceError(
                    "A checksum-pinned event source is not valid JSONL."
                ) from exc
            identity, record_type = _insert_event(raw_events, event, spec.source_id)
            record_counts[record_type] += 1
            source_targets.add(identity[2])
            policy_identity = identity[3:8]
            policy_counts = per_policy_counts[policy_identity]
            policy_counts["targets"].add(identity[2])
            if record_type == "OFFICIAL_RESULT" and event["candidate_any_prize"] is True:
                policy_counts["successes"] += 1
        if record_counts != {"PREDICTION": 2634, "OFFICIAL_RESULT": 2634}:
            raise EventSourceError("A checksum-pinned event source has unexpected record types.")
        target_sets.append(source_targets)
        source_metadata.append(
            {
                "source_id": spec.source_id,
                "file_name": spec.file_name,
                "sha256": observed_sha256,
                "bytes": len(raw),
                "events": len(lines),
                "prediction_events": record_counts["PREDICTION"],
                "official_result_events": record_counts["OFFICIAL_RESULT"],
            }
        )

    if target_sets[0] != target_sets[1] or len(target_sets[0]) != 1317:
        raise EventSourceError("The pinned K5 policy sources do not cover the same 1,317 draws.")
    if len(raw_events) != 5268:
        raise EventSourceError("The pinned event set does not contain 5,268 identities.")

    paired_records = _pair_event_records(raw_events)

    for policy_identity, expected in EXPECTED_POLICY_BY_IDENTITY.items():
        observed = per_policy_counts[policy_identity]
        if len(observed["targets"]) != 1317 or observed["successes"] != expected["successes"]:
            raise EventSourceError("A pinned policy count differs from its completion receipt.")

    source_hashes = {item["source_id"]: item["sha256"] for item in source_metadata}
    version_digest = hashlib.sha256(
        _stable_json_bytes({"schema_version": EVENT_SCHEMA_VERSION, "source_sha256": source_hashes})
    ).hexdigest()
    data_version = f"k5-draw-events-v1:{version_digest}"
    source_manifest = {
        "schema_version": EVENT_SCHEMA_VERSION,
        "data_version": data_version,
        "source_files": sorted(source_metadata, key=lambda item: item["source_id"]),
        "event_count": 10536,
        "identity_count": len(paired_records),
        "policy_count": len(POLICY_IDENTITIES),
        "event_time_semantics": "historical_import",
        "original_predraw_evidence": "NOT_ESTABLISHED_BY_IMPORT_TIME",
        "producer_causality": "NOT_ESTABLISHED",
        "prospective_gain_established": False,
        "eh27_clean_status": "COUNTERFACTUAL",
    }
    return EventIndex(
        records=tuple(paired_records),
        data_version=data_version,
        source_manifest=source_manifest,
    )


def _safe_locator(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    if value in {"", "UNKNOWN"}:
        return value or None
    normalized = value.replace("\\", "/")
    return PurePosixPath(normalized).name or None


def _public_source_identity(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        return None
    value = cast(Mapping[str, Any], value)
    return {
        "locator": _safe_locator(value.get("locator")),
        "sha256": value.get("sha256"),
    }


def _project_record(record: DrawEvent, data_version: str) -> dict[str, Any]:
    prediction = record.prediction
    official_result = record.official_result
    return {
        "lottery": prediction["lottery_type"],
        "K": prediction["K"],
        "target_draw": prediction["target_draw"],
        "strategy_id": prediction["strategy_id"],
        "strategy_version": prediction["strategy_version"],
        "policy_version": prediction["policy_version"],
        "algorithm_version": prediction["algorithm_version"],
        "run_identity": prediction["run_identity"],
        "history_cutoff": prediction["history_cutoff"],
        "ordered_tickets": json.loads(json.dumps(prediction["ordered_tickets"])),
        "prediction_any_prize": prediction.get("candidate_any_prize"),
        "official_result": {
            "winning_result": json.loads(json.dumps(official_result["winning_result"])),
            "candidate_any_prize": official_result["candidate_any_prize"],
            "ticket_prize_tiers": json.loads(json.dumps(official_result["ticket_prize_tiers"])),
        },
        "official_any_prize": official_result["candidate_any_prize"],
        "ticket_prize_tiers": json.loads(json.dumps(official_result["ticket_prize_tiers"])),
        "source_variant": prediction.get("source_variant"),
        "fallback": {
            "source_record_label": prediction.get("source_record_label"),
            "policy_source": prediction.get("policy_source"),
            "native_fallback_class": prediction.get("native_fallback_class"),
            "native_used": prediction.get("native_used"),
            "fallback_reason": prediction.get("fallback_reason"),
        },
        "source_identity": {
            "event_source_id": record.source_id,
            "prediction": {
                "producer": _public_source_identity(prediction.get("producer_source_identity")),
                "scorer": _public_source_identity(prediction.get("scorer_source_identity")),
                "source_input_sha256": prediction.get("source_input_sha256"),
                "result_artifact_sha256": prediction.get("result_artifact_sha256"),
                "source_prediction_artifact": _safe_locator(
                    prediction.get("source_prediction_artifact")
                ),
            },
            "official_result": {
                "source": _public_source_identity(
                    official_result.get("official_result_source_identity")
                ),
                "scorer": _public_source_identity(official_result.get("scorer_source_identity")),
                "prize_rule": _public_source_identity(
                    official_result.get("prize_rule_source_identity")
                ),
                "result_artifact_sha256": official_result.get("result_artifact_sha256"),
            },
        },
        "data_version": data_version,
    }


def _parse_query(query_string: str) -> tuple[dict[str, str], int, int]:
    parsed = parse_qs(query_string, keep_blank_values=True, strict_parsing=False)
    unsupported = sorted(set(parsed) - QUERY_PARAMETERS)
    if unsupported:
        raise _BadRequest("Unsupported query parameter.")
    query: dict[str, str] = {}
    for key, values in parsed.items():
        if len(values) != 1:
            raise _BadRequest(f"{key} must be provided once.")
        value = values[0]
        if key in QUERY_PARAMETERS - {"data_version", "limit", "offset", "K"} and (
            not value or value != value.strip()
        ):
            raise _BadRequest(f"{key} must be a nonblank exact value.")
        query[key] = value

    if "K" not in query:
        raise _BadRequest("K is required; this endpoint only serves K=5.")
    if query["K"] != "5":
        raise _BadRequest("K must be 5 for the pinned K5 event set.")
    if "strategy_id" not in query and "target_draw" not in query:
        raise _BadRequest("Provide strategy_id or target_draw to bound the query.")
    if "target_draw" in query and (
        not query["target_draw"].isascii() or not query["target_draw"].isdigit()
    ):
        raise _BadRequest("target_draw must contain only draw-number digits.")
    if "data_version" in query and not query["data_version"]:
        raise _BadRequest("data_version must be nonblank when provided.")

    def parse_integer(name: str, default: int, minimum: int, maximum: int) -> int:
        raw = query.get(name)
        if raw is None:
            return default
        try:
            value = int(raw)
        except ValueError as exc:
            raise _BadRequest(f"{name} must be an integer.") from exc
        if value < minimum or value > maximum:
            raise _BadRequest(f"{name} must be between {minimum} and {maximum}.")
        return value

    offset = parse_integer("offset", 0, 0, 1_000_000)
    limit = parse_integer("limit", 100, 1, 500)
    return query, offset, limit


def _check_ambiguous_strategy_query(matches: Sequence[DrawEvent], query: Mapping[str, str]) -> None:
    if "strategy_id" not in query or not matches:
        return
    for field in ("strategy_version", "policy_version", "algorithm_version", "run_identity"):
        if field not in query:
            values = {record.prediction.get(field) for record in matches}
            if len(values) > 1:
                raise _AmbiguousQuery(
                    f"strategy_id matches multiple {field} values; provide {field}."
                )


def _matches_query(record: DrawEvent, query: Mapping[str, str]) -> bool:
    prediction = record.prediction
    for query_field, event_field in QUERY_IDENTITY_FIELDS:
        if query_field in query and prediction.get(event_field) != query[query_field]:
            return False
    return True


def _response_metadata(index: EventIndex) -> dict[str, Any]:
    return {
        "api_version": API_VERSION,
        "data_version": index.data_version,
        "source_manifest": json.loads(json.dumps(index.source_manifest)),
    }


def create_research_backtest_events_router(
    event_index: EventIndex | None = None,
) -> APIRouter:
    """Register the fixed historical K5 event route on the host FastAPI app."""
    index = event_index
    if index is None:
        try:
            # Load and checksum sources when the host app is constructed; requests
            # only read this fixed in-memory index and cannot select another source.
            index = load_event_index()
        except EventSourceError:
            index = None

    router = APIRouter(prefix="/api/v1/research/backtests", tags=["research-backtests"])

    @router.get("/draw-events")
    def draw_events(request: Request) -> JSONResponse:
        if index is None:
            return JSONResponse(
                status_code=HTTPStatus.SERVICE_UNAVAILABLE,
                content={
                    "api_version": API_VERSION,
                    "error": "source_unavailable",
                    "message": "The checksum-pinned K5 event source is unavailable.",
                },
                headers={"Cache-Control": "no-store"},
            )
        try:
            query, offset, limit = _parse_query(request.url.query)
            if "data_version" in query and query["data_version"] != index.data_version:
                return JSONResponse(
                    status_code=HTTPStatus.CONFLICT,
                    content={
                        **_response_metadata(index),
                        "error": "source_version_mismatch",
                        "message": (
                            "The requested data_version does not match the pinned event source."
                        ),
                    },
                    headers={"Cache-Control": "no-store"},
                )
            matches = [record for record in index.records if _matches_query(record, query)]
            _check_ambiguous_strategy_query(matches, query)
            page = matches[offset : offset + limit]
            return JSONResponse(
                status_code=HTTPStatus.OK,
                content={
                    **_response_metadata(index),
                    "query": {
                        **{key: value for key, value in query.items() if key != "data_version"},
                        "offset": offset,
                        "limit": limit,
                    },
                    "count": len(matches),
                    "returned": len(page),
                    "draw_events": [_project_record(record, index.data_version) for record in page],
                },
                headers={"Cache-Control": "no-store"},
            )
        except _BadRequest as exc:
            status_code = HTTPStatus.BAD_REQUEST
            payload = {
                "api_version": API_VERSION,
                "error": "invalid_request",
                "message": str(exc),
            }
        except _AmbiguousQuery as exc:
            status_code = HTTPStatus.CONFLICT
            payload = {
                **_response_metadata(index),
                "error": "ambiguous_identity",
                "message": str(exc),
            }
        except Exception:
            status_code = HTTPStatus.INTERNAL_SERVER_ERROR
            payload = {
                "api_version": API_VERSION,
                "error": "internal_error",
                "message": "The K5 draw-event request could not be completed.",
            }
        return JSONResponse(
            status_code=status_code,
            content=payload,
            headers={"Cache-Control": "no-store"},
        )

    return router
