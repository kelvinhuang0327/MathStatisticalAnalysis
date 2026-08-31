"""Deterministic two-phase T539 prospective shadow observer harness.

PRETARGET_PREPARE is the only phase allowed to select an arm identity or copy a
precomputed target prediction.  POSTTARGET_SCORE accepts only the sealed
snapshot and an official outcome, so it cannot revisit the input authority,
rerun the selector, or regenerate tickets after the outcome is known.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, cast

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
FREEZE_RELATIVE_PATH = Path(
    "docs/research/matrix-native-results/"
    "t539-callable-family-dedup-prospective-shadow-freeze-r1.json"
)
DEFAULT_FREEZE_PATH = REPOSITORY_ROOT / FREEZE_RELATIVE_PATH

EXPECTED_FREEZE_SHA256: Final = (
    "f1b299ace019393440bce8bd2768f6618b2362d220d81b4cc14151a5080908a8"
)
EXPECTED_FREEZE_ID: Final = "T539_CALLABLE_FAMILY_DEDUP_PROSPECTIVE_SHADOW_FREEZE_R1"
EXPECTED_FREEZE_SCHEMA_VERSION: Final = (
    "T539_CALLABLE_FAMILY_DEDUP_PROSPECTIVE_SHADOW_FREEZE_V1"
)
EXPECTED_RULE_FINGERPRINT: Final = (
    "eb4eb89082cd782041c240e80858efd8453c3bbf08edec3b76e98e2e8051f446"
)
EXPECTED_PILOT_RESULT_SHA256: Final = (
    "1a4fbd067f3d9b4735a4a1143b3694222f38f05eb3ec91e4e8b782e0e90c5c86"
)
FREEZE_BOUNDARY: Final = "115000186"

PRETARGET_INPUT_SCHEMA_VERSION: Final = "T539_PROSPECTIVE_PRETARGET_INPUT_V1"
PRETARGET_SNAPSHOT_SCHEMA_VERSION: Final = "T539_PROSPECTIVE_PRETARGET_SNAPSHOT_V1"
POSTTARGET_OUTCOME_SCHEMA_VERSION: Final = "T539_OFFICIAL_OUTCOME_V1"
POSTTARGET_RESULT_SCHEMA_VERSION: Final = "T539_PROSPECTIVE_TARGET_SCORE_V1"

FROZEN_K_VALUES: Final = (1, 2, 3, 4, 5, 7, 10, 11, 12, 25)
FROZEN_WINDOWS: Final = (("W50", 50), ("W300", 300), ("W750", 750))
FROZEN_ARMS: Final = (
    "ORIGINAL_ROLLING",
    "CALLABLE_FAMILY_DEDUP_ROLLING",
    "CALLABLE_FAMILY_DEDUP_FROZEN_BASELINE",
)

PRETARGET_SEAL_CONFIRMED: Final = "PRETARGET_SEAL_CONFIRMED_BEFORE_OUTCOME"
MISSED_PRETARGET_SEAL: Final = "MISSED_PRETARGET_SEAL"
VALID_PROSPECTIVE_OBSERVATION: Final = "VALID_PROSPECTIVE_OBSERVATION"

_TARGET_IDENTITY = re.compile(r"[0-9]{1,32}", flags=re.ASCII)
_SHA256 = re.compile(r"[0-9a-f]{64}", flags=re.ASCII)
_LOGICAL_AUTHORITY_IDENTITY = re.compile(
    r"[A-Za-z0-9][A-Za-z0-9._:@/\-]{0,255}", flags=re.ASCII
)
_PROHIBITED_OUTCOME_KEYS = frozenset(
    {
        "main_numbers",
        "official_numbers",
        "official_outcome",
        "outcome",
        "outcome_hash",
        "outcome_numbers",
        "score_hash",
        "target_official_outcome",
        "target_outcome",
        "winning_numbers",
    }
)

Identity = tuple[str, str, str, str]
TierVector = tuple[int, int, int, int]
Ticket = tuple[int, int, int, int, int]


class ObserverContractError(ValueError):
    """A supplied artifact cannot satisfy the frozen prospective contract."""


@dataclass(frozen=True, slots=True)
class FreezeCell:
    cell_id: str
    k: int
    original_identities: tuple[Identity, ...]
    representative_identities: tuple[Identity, ...]
    callable_by_identity: Mapping[Identity, str]
    original_universe_sha256: str
    callable_universe_sha256: str
    baseline_by_window: Mapping[int, Identity]


@dataclass(frozen=True, slots=True)
class FreezeContract:
    manifest_sha256: str
    freeze_id: str
    boundary: str
    rule_fingerprint: str
    pilot_result_sha256: str
    cells: Mapping[int, FreezeCell]


@dataclass(frozen=True, slots=True)
class CandidateMetric:
    success: bool
    prize_tier_counts: TierVector
    winning_ticket_count: int


@dataclass(frozen=True, slots=True)
class HistoryRow:
    target_identity: str
    metrics: Mapping[Identity, CandidateMetric]


@dataclass(frozen=True, slots=True)
class PretargetCellInput:
    k: int
    history: tuple[HistoryRow, ...]
    predictions: Mapping[Identity, tuple[Ticket, ...]]


def canonical_json_bytes(value: object) -> bytes:
    """Return the repository's deterministic, human-readable JSON encoding."""

    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n"
    ).encode()


def _compact_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        allow_nan=False,
    ).encode()


def _content_sha256(value: object) -> str:
    return hashlib.sha256(_compact_json_bytes(value)).hexdigest()


def snapshot_content_hash(snapshot: Mapping[str, Any]) -> str:
    """Hash every deterministic snapshot field except the hash field itself."""

    material = dict(snapshot)
    material.pop("snapshot_content_hash", None)
    return _content_sha256(material)


def result_content_hash(result: Mapping[str, Any]) -> str:
    """Hash every deterministic score-result field except its own hash field."""

    material = dict(result)
    material.pop("result_content_hash", None)
    return _content_sha256(material)


def _mapping(value: object, *, context: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ObserverContractError(f"{context} must be a JSON object")
    return cast(Mapping[str, Any], value)


def _list(value: object, *, context: str) -> list[Any]:
    if not isinstance(value, list):
        raise ObserverContractError(f"{context} must be a JSON array")
    return cast(list[Any], value)


def _text(value: object, *, context: str) -> str:
    if type(value) is not str or not value:
        raise ObserverContractError(f"{context} must be a non-empty string")
    return value


def _integer(value: object, *, context: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise ObserverContractError(f"{context} must be an integer >= {minimum}")
    return value


def _boolean(value: object, *, context: str) -> bool:
    if type(value) is not bool:
        raise ObserverContractError(f"{context} must be a boolean")
    return value


def _exact_keys(value: Mapping[str, Any], expected: set[str], *, context: str) -> None:
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(str(key) for key in actual - expected)
        raise ObserverContractError(
            f"{context} schema mismatch; missing={missing}, extra={extra}"
        )


def _sha256_text(value: object, *, context: str) -> str:
    text = _text(value, context=context)
    if _SHA256.fullmatch(text) is None:
        raise ObserverContractError(f"{context} must be a lowercase SHA-256 digest")
    return text


def _target_text(value: object, *, context: str) -> str:
    if type(value) is not str or _TARGET_IDENTITY.fullmatch(value) is None:
        raise ObserverContractError(
            f"{context} must contain 1-32 ASCII decimal digits"
        )
    return value


def _identity(value: object, *, context: str) -> Identity:
    items = _list(value, context=context)
    if len(items) != 4:
        raise ObserverContractError(f"{context} must contain four identity fields")
    fields = tuple(_text(item, context=f"{context}[{index}]") for index, item in enumerate(items))
    return cast(Identity, fields)


def _logical_authority_identity(value: object) -> str:
    identity = _text(value, context="pretarget_inputs.authority_identity")
    if (
        _LOGICAL_AUTHORITY_IDENTITY.fullmatch(identity) is None
        or identity.startswith("/")
        or re.match(r"[A-Za-z]:[\\/]", identity) is not None
    ):
        raise ObserverContractError(
            "pretarget_inputs.authority_identity must be an opaque logical identity, not a path"
        )
    return identity


def _reject_target_outcome_fields(value: object, *, context: str = "pretarget_inputs") -> None:
    if isinstance(value, Mapping):
        mapping = cast(Mapping[object, object], value)
        for raw_key, child in mapping.items():
            key = str(raw_key).lower()
            if key in _PROHIBITED_OUTCOME_KEYS or (
                "outcome" in key and key != "outcome_presence"
            ):
                raise ObserverContractError("TARGET_OUTCOME_PRESENT_DURING_PRETARGET")
            _reject_target_outcome_fields(child, context=f"{context}.{raw_key}")
    elif isinstance(value, list):
        children = cast(list[object], value)
        for index, child in enumerate(children):
            _reject_target_outcome_fields(child, context=f"{context}[{index}]")


def _tier_vector(value: object, *, context: str) -> TierVector:
    items = _list(value, context=context)
    if len(items) != 4:
        raise ObserverContractError(f"{context} must contain [hits5,hits4,hits3,hits2]")
    result = tuple(
        _integer(item, context=f"{context}[{index}]") for index, item in enumerate(items)
    )
    return cast(TierVector, result)


def _normalize_ticket(value: object, *, context: str) -> Ticket:
    items = _list(value, context=context)
    if len(items) != 5:
        raise ObserverContractError(f"{context} must contain exactly five numbers")
    numbers = tuple(
        _integer(item, context=f"{context}[{index}]", minimum=1)
        for index, item in enumerate(items)
    )
    if any(number > 39 for number in numbers) or len(set(numbers)) != 5:
        raise ObserverContractError(f"{context} must contain five unique numbers in 1..39")
    return cast(Ticket, tuple(sorted(numbers)))


def _normalize_tickets(value: object, *, k: int, context: str) -> tuple[Ticket, ...]:
    items = _list(value, context=context)
    if len(items) != k:
        raise ObserverContractError(f"{context} must contain exactly {k} native tickets")
    tickets = tuple(
        sorted(
            _normalize_ticket(item, context=f"{context}[{index}]")
            for index, item in enumerate(items)
        )
    )
    if len(set(tickets)) != k:
        raise ObserverContractError(f"{context} contains duplicate native tickets")
    return tickets


def _read_json_object(path: Path, *, context: str) -> Mapping[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise ObserverContractError(f"{context} is not a regular file: {path}")
    try:
        value: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ObserverContractError(f"{context} is not valid UTF-8 JSON: {path}") from exc
    return _mapping(value, context=context)


def load_freeze_contract(path: Path = DEFAULT_FREEZE_PATH) -> FreezeContract:
    """Load and validate the one authorized frozen selector contract."""

    if path.is_symlink() or not path.is_file():
        raise ObserverContractError(f"FREEZE_IDENTITY_DRIFT: not a regular file: {path}")
    raw = path.read_bytes()
    observed_sha256 = hashlib.sha256(raw).hexdigest()
    if observed_sha256 != EXPECTED_FREEZE_SHA256:
        raise ObserverContractError(
            f"FREEZE_IDENTITY_DRIFT: expected {EXPECTED_FREEZE_SHA256}, got {observed_sha256}"
        )
    try:
        parsed: object = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ObserverContractError("FREEZE_IDENTITY_DRIFT: invalid JSON") from exc
    manifest = _mapping(parsed, context="freeze")
    if manifest.get("schema_version") != EXPECTED_FREEZE_SCHEMA_VERSION:
        raise ObserverContractError("FREEZE_IDENTITY_DRIFT: schema version mismatch")
    if manifest.get("freeze_id") != EXPECTED_FREEZE_ID:
        raise ObserverContractError("FREEZE_IDENTITY_DRIFT: freeze id mismatch")

    boundary = _mapping(manifest.get("freeze_boundary"), context="freeze.freeze_boundary")
    boundary_target = _target_text(
        boundary.get("target_identity"), context="freeze.freeze_boundary.target_identity"
    )
    if boundary_target != FREEZE_BOUNDARY:
        raise ObserverContractError("FREEZE_IDENTITY_DRIFT: boundary mismatch")

    fingerprint = _mapping(
        manifest.get("immutable_rule_fingerprint"),
        context="freeze.immutable_rule_fingerprint",
    )
    fingerprint_sha256 = _sha256_text(
        fingerprint.get("sha256"), context="freeze.immutable_rule_fingerprint.sha256"
    )
    if fingerprint_sha256 != EXPECTED_RULE_FINGERPRINT:
        raise ObserverContractError("FREEZE_IDENTITY_DRIFT: rule fingerprint mismatch")

    source_pilot = _mapping(manifest.get("source_pilot"), context="freeze.source_pilot")
    pilot_result_sha256 = _sha256_text(
        source_pilot.get("result_sha256"), context="freeze.source_pilot.result_sha256"
    )
    if pilot_result_sha256 != EXPECTED_PILOT_RESULT_SHA256:
        raise ObserverContractError("FREEZE_IDENTITY_DRIFT: pilot result mismatch")

    surface = _mapping(manifest.get("surface"), context="freeze.surface")
    if surface.get("lottery_id") != "T539":
        raise ObserverContractError("FREEZE_IDENTITY_DRIFT: lottery mismatch")
    observed_k_values = tuple(
        _integer(item, context="freeze.surface.included_native_ticket_counts[]", minimum=1)
        for item in _list(
            surface.get("included_native_ticket_counts"),
            context="freeze.surface.included_native_ticket_counts",
        )
    )
    if observed_k_values != FROZEN_K_VALUES:
        raise ObserverContractError("FREEZE_IDENTITY_DRIFT: K surface mismatch")
    observed_windows = tuple(
        (
            _text(
                _mapping(item, context="freeze.surface.windows[]").get("label"),
                context="freeze.surface.windows[].label",
            ),
            _integer(
                _mapping(item, context="freeze.surface.windows[]").get("size"),
                context="freeze.surface.windows[].size",
                minimum=1,
            ),
        )
        for item in _list(surface.get("windows"), context="freeze.surface.windows")
    )
    if observed_windows != FROZEN_WINDOWS:
        raise ObserverContractError("FREEZE_IDENTITY_DRIFT: window surface mismatch")

    comparator_ids = tuple(
        _text(
            _mapping(item, context="freeze.comparators[]").get("id"),
            context="freeze.comparators[].id",
        )
        for item in _list(manifest.get("comparators"), context="freeze.comparators")
    )
    if comparator_ids != FROZEN_ARMS:
        raise ObserverContractError("FREEZE_IDENTITY_DRIFT: arm surface mismatch")

    cells: dict[int, FreezeCell] = {}
    raw_cells = _list(manifest.get("cells"), context="freeze.cells")
    if len(raw_cells) != len(FROZEN_K_VALUES):
        raise ObserverContractError("FREEZE_IDENTITY_DRIFT: cell count mismatch")
    for expected_k, raw_cell in zip(FROZEN_K_VALUES, raw_cells, strict=True):
        cell = _mapping(raw_cell, context=f"freeze.cells.K{expected_k}")
        k = _integer(cell.get("native_ticket_count"), context=f"freeze.cells.K{expected_k}.k")
        cell_id = _text(cell.get("cell_id"), context=f"freeze.cells.K{expected_k}.cell_id")
        if k != expected_k or cell_id != f"T539:K{k}" or cell.get("lottery_id") != "T539":
            raise ObserverContractError("FREEZE_IDENTITY_DRIFT: cell identity mismatch")

        original = tuple(
            _identity(item, context=f"{cell_id}.original_candidate_universe[]")
            for item in _list(
                cell.get("original_candidate_universe"),
                context=f"{cell_id}.original_candidate_universe",
            )
        )
        if not original or len(set(original)) != len(original):
            raise ObserverContractError("FREEZE_IDENTITY_DRIFT: original universe invalid")
        original_sha256 = _sha256_text(
            cell.get("original_candidate_universe_sha256"),
            context=f"{cell_id}.original_candidate_universe_sha256",
        )
        callable_sha256 = _sha256_text(
            cell.get("callable_reduced_universe_sha256"),
            context=f"{cell_id}.callable_reduced_universe_sha256",
        )

        representatives: list[Identity] = []
        callable_by_identity: dict[Identity, str] = {}
        for family_index, raw_family in enumerate(
            _list(cell.get("callable_families"), context=f"{cell_id}.callable_families")
        ):
            family = _mapping(raw_family, context=f"{cell_id}.families[{family_index}]")
            callable_identity = _text(
                family.get("callable_identity"),
                context=f"{cell_id}.families[{family_index}].callable_identity",
            )
            representative = _identity(
                family.get("representative_identity"),
                context=f"{cell_id}.families[{family_index}].representative_identity",
            )
            members = tuple(
                _identity(item, context=f"{cell_id}.families[{family_index}].members[]")
                for item in _list(
                    family.get("member_identities"),
                    context=f"{cell_id}.families[{family_index}].member_identities",
                )
            )
            if representative not in members or representative != min(members):
                raise ObserverContractError("FREEZE_IDENTITY_DRIFT: representative mismatch")
            representatives.append(representative)
            for member in members:
                if member in callable_by_identity:
                    raise ObserverContractError("FREEZE_IDENTITY_DRIFT: duplicate family member")
                callable_by_identity[member] = callable_identity
        if set(callable_by_identity) != set(original):
            raise ObserverContractError("FREEZE_IDENTITY_DRIFT: callable family coverage mismatch")
        representative_tuple = tuple(sorted(representatives))
        if not representative_tuple or len(set(representative_tuple)) != len(representative_tuple):
            raise ObserverContractError("FREEZE_IDENTITY_DRIFT: representative universe invalid")

        baseline_by_window: dict[int, Identity] = {}
        raw_windows = _list(cell.get("windows"), context=f"{cell_id}.windows")
        if len(raw_windows) != len(FROZEN_WINDOWS):
            raise ObserverContractError("FREEZE_IDENTITY_DRIFT: cell window count mismatch")
        for (expected_label, expected_window), raw_window in zip(
            FROZEN_WINDOWS, raw_windows, strict=True
        ):
            window_item = _mapping(raw_window, context=f"{cell_id}.{expected_label}")
            if (
                window_item.get("label") != expected_label
                or window_item.get("size") != expected_window
            ):
                raise ObserverContractError("FREEZE_IDENTITY_DRIFT: cell window mismatch")
            baseline = _identity(
                window_item.get("callable_family_dedup_frozen_baseline_identity"),
                context=f"{cell_id}.{expected_label}.baseline_identity",
            )
            if baseline not in representative_tuple:
                raise ObserverContractError("FREEZE_IDENTITY_DRIFT: baseline is not representative")
            baseline_by_window[expected_window] = baseline

        cells[k] = FreezeCell(
            cell_id=cell_id,
            k=k,
            original_identities=tuple(sorted(original)),
            representative_identities=representative_tuple,
            callable_by_identity=callable_by_identity,
            original_universe_sha256=original_sha256,
            callable_universe_sha256=callable_sha256,
            baseline_by_window=baseline_by_window,
        )

    return FreezeContract(
        manifest_sha256=observed_sha256,
        freeze_id=EXPECTED_FREEZE_ID,
        boundary=boundary_target,
        rule_fingerprint=fingerprint_sha256,
        pilot_result_sha256=pilot_result_sha256,
        cells=cells,
    )


def _normalize_candidate_metric(
    value: object, *, context: str, k: int
) -> tuple[Identity, CandidateMetric, dict[str, Any]]:
    item = _mapping(value, context=context)
    _exact_keys(
        item,
        {"identity", "prize_tier_counts", "success", "winning_ticket_count"},
        context=context,
    )
    identity = _identity(item.get("identity"), context=f"{context}.identity")
    success = _boolean(item.get("success"), context=f"{context}.success")
    tiers = _tier_vector(item.get("prize_tier_counts"), context=f"{context}.prize_tier_counts")
    winning = _integer(
        item.get("winning_ticket_count"), context=f"{context}.winning_ticket_count"
    )
    if winning > k or sum(tiers) != winning or success != (winning > 0):
        raise ObserverContractError(f"{context} has inconsistent frozen selector metrics")
    metric = CandidateMetric(
        success=success,
        prize_tier_counts=tiers,
        winning_ticket_count=winning,
    )
    payload = {
        "identity": list(identity),
        "prize_tier_counts": list(tiers),
        "success": success,
        "winning_ticket_count": winning,
    }
    return identity, metric, payload


def _normalize_pretarget_inputs(
    pretarget_inputs: Mapping[str, Any],
    *,
    target_identity: str,
    contract: FreezeContract,
) -> tuple[dict[str, Any], dict[int, PretargetCellInput]]:
    _reject_target_outcome_fields(pretarget_inputs)
    _exact_keys(
        pretarget_inputs,
        {"authority_identity", "cells", "outcome_presence", "schema_version"},
        context="pretarget_inputs",
    )
    if pretarget_inputs.get("schema_version") != PRETARGET_INPUT_SCHEMA_VERSION:
        raise ObserverContractError("PRETARGET_INPUT_SCHEMA_VERSION_MISMATCH")
    if pretarget_inputs.get("outcome_presence") != "ABSENT":
        raise ObserverContractError("TARGET_OUTCOME_PRESENT_DURING_PRETARGET")
    authority_identity = _logical_authority_identity(pretarget_inputs.get("authority_identity"))

    raw_cells = _list(pretarget_inputs.get("cells"), context="pretarget_inputs.cells")
    if len(raw_cells) != len(FROZEN_K_VALUES):
        raise ObserverContractError("PRETARGET_CELL_SURFACE_INCOMPLETE")
    cells: dict[int, PretargetCellInput] = {}
    normalized_cells: list[dict[str, Any]] = []
    target_number = int(target_identity)

    for raw_cell in raw_cells:
        cell = _mapping(raw_cell, context="pretarget_inputs.cells[]")
        _exact_keys(
            cell,
            {"history", "k", "lottery_id", "predictions"},
            context="pretarget_inputs.cells[]",
        )
        k = _integer(cell.get("k"), context="pretarget_inputs.cells[].k", minimum=1)
        if k in cells or k not in contract.cells or cell.get("lottery_id") != "T539":
            raise ObserverContractError(f"PRETARGET_CELL_IDENTITY_INVALID: K{k}")
        frozen_cell = contract.cells[k]
        expected_identities = frozenset(frozen_cell.original_identities)

        history_rows: list[HistoryRow] = []
        normalized_history: list[dict[str, Any]] = []
        seen_history_numbers: set[int] = set()
        for history_index, raw_history in enumerate(
            _list(cell.get("history"), context=f"pretarget_inputs.K{k}.history")
        ):
            history = _mapping(
                raw_history,
                context=f"pretarget_inputs.K{k}.history[{history_index}]",
            )
            _exact_keys(
                history,
                {"candidate_metrics", "target_identity"},
                context=f"pretarget_inputs.K{k}.history[{history_index}]",
            )
            history_target = _target_text(
                history.get("target_identity"),
                context=f"pretarget_inputs.K{k}.history[{history_index}].target_identity",
            )
            history_number = int(history_target)
            if history_number >= target_number:
                raise ObserverContractError(
                    "HISTORY_TARGET_NOT_STRICTLY_BEFORE_TARGET: "
                    f"{history_target} >= {target_identity}"
                )
            if history_number in seen_history_numbers:
                raise ObserverContractError(
                    f"DUPLICATE_HISTORY_TARGET_IDENTITY: K{k}:{history_target}"
                )
            seen_history_numbers.add(history_number)

            metric_map: dict[Identity, CandidateMetric] = {}
            normalized_metrics: list[dict[str, Any]] = []
            for metric_index, raw_metric in enumerate(
                _list(
                    history.get("candidate_metrics"),
                    context=f"pretarget_inputs.K{k}.history[{history_index}].candidate_metrics",
                )
            ):
                identity, metric, metric_payload = _normalize_candidate_metric(
                    raw_metric,
                    context=(
                        f"pretarget_inputs.K{k}.history[{history_index}]"
                        f".candidate_metrics[{metric_index}]"
                    ),
                    k=k,
                )
                if identity not in expected_identities or identity in metric_map:
                    raise ObserverContractError(
                        f"PRETARGET_HISTORY_CANDIDATE_UNIVERSE_MISMATCH: K{k}"
                    )
                metric_map[identity] = metric
                normalized_metrics.append(metric_payload)
            if frozenset(metric_map) != expected_identities:
                raise ObserverContractError(
                    f"PRETARGET_HISTORY_CANDIDATE_UNIVERSE_MISMATCH: K{k}:{history_target}"
                )
            normalized_metrics.sort(key=lambda item: tuple(cast(list[str], item["identity"])))
            history_rows.append(HistoryRow(history_target, metric_map))
            normalized_history.append(
                {
                    "candidate_metrics": normalized_metrics,
                    "target_identity": history_target,
                }
            )

        paired_history = sorted(
            zip(history_rows, normalized_history, strict=True),
            key=lambda item: (int(item[0].target_identity), item[0].target_identity),
        )
        history_rows = [item[0] for item in paired_history]
        normalized_history = [item[1] for item in paired_history]
        if len(history_rows) < FROZEN_WINDOWS[-1][1]:
            raise ObserverContractError(f"INSUFFICIENT_PRETARGET_HISTORY: K{k}")

        predictions: dict[Identity, tuple[Ticket, ...]] = {}
        normalized_predictions: list[dict[str, Any]] = []
        for prediction_index, raw_prediction in enumerate(
            _list(cell.get("predictions"), context=f"pretarget_inputs.K{k}.predictions")
        ):
            prediction = _mapping(
                raw_prediction, context=f"pretarget_inputs.K{k}.predictions[{prediction_index}]"
            )
            _exact_keys(
                prediction,
                {"identity", "tickets"},
                context=f"pretarget_inputs.K{k}.predictions[{prediction_index}]",
            )
            identity = _identity(
                prediction.get("identity"),
                context=f"pretarget_inputs.K{k}.predictions[{prediction_index}].identity",
            )
            if identity not in expected_identities or identity in predictions:
                raise ObserverContractError(f"PRETARGET_PREDICTION_UNIVERSE_MISMATCH: K{k}")
            tickets = _normalize_tickets(
                prediction.get("tickets"),
                k=k,
                context=f"pretarget_inputs.K{k}.predictions[{prediction_index}].tickets",
            )
            predictions[identity] = tickets
            normalized_predictions.append(
                {"identity": list(identity), "tickets": [list(ticket) for ticket in tickets]}
            )
        if frozenset(predictions) != expected_identities:
            raise ObserverContractError(f"PRETARGET_PREDICTION_UNIVERSE_MISMATCH: K{k}")
        normalized_predictions.sort(
            key=lambda item: tuple(cast(list[str], item["identity"]))
        )

        cells[k] = PretargetCellInput(k, tuple(history_rows), predictions)
        normalized_cells.append(
            {
                "history": normalized_history,
                "k": k,
                "lottery_id": "T539",
                "predictions": normalized_predictions,
            }
        )

    if tuple(sorted(cells)) != FROZEN_K_VALUES:
        raise ObserverContractError("PRETARGET_CELL_SURFACE_INCOMPLETE")
    normalized_cells.sort(key=lambda item: cast(int, item["k"]))

    max_window = FROZEN_WINDOWS[-1][1]
    common_history: tuple[str, ...] | None = None
    for k in FROZEN_K_VALUES:
        suffix = tuple(row.target_identity for row in cells[k].history[-max_window:])
        if common_history is None:
            common_history = suffix
        elif suffix != common_history:
            raise ObserverContractError("PRETARGET_HISTORY_TARGET_SET_MISMATCH_ACROSS_CELLS")

    normalized = {
        "authority_identity": authority_identity,
        "cells": normalized_cells,
        "outcome_presence": "ABSENT",
        "schema_version": PRETARGET_INPUT_SCHEMA_VERSION,
    }
    return normalized, cells


def _selector_statistics(
    cell: PretargetCellInput,
    candidate_identities: Sequence[Identity],
    *,
    window: int,
) -> list[dict[str, Any]]:
    rows = cell.history[-window:]
    statistics: list[dict[str, Any]] = []
    for identity in sorted(candidate_identities):
        metrics = [row.metrics[identity] for row in rows]
        tiers = tuple(
            sum(metric.prize_tier_counts[index] for metric in metrics) for index in range(4)
        )
        statistics.append(
            {
                "identity": list(identity),
                "prize_tier_counts": list(tiers),
                "success_count": sum(metric.success for metric in metrics),
                "winning_ticket_count": sum(metric.winning_ticket_count for metric in metrics),
            }
        )
    return statistics


def _select_strategy(statistics: Sequence[Mapping[str, Any]]) -> Identity:
    """Apply the exact sealed rolling-selector ordering to one prior window."""

    if not statistics:
        raise ObserverContractError("EMPTY_SELECTOR_UNIVERSE")

    def rank_key(item: Mapping[str, Any]) -> tuple[object, ...]:
        identity = _identity(item.get("identity"), context="selector.identity")
        success_count = _integer(item.get("success_count"), context="selector.success_count")
        tiers = _tier_vector(item.get("prize_tier_counts"), context="selector.prize_tier_counts")
        winning = _integer(
            item.get("winning_ticket_count"), context="selector.winning_ticket_count"
        )
        return (
            -success_count,
            tuple(-count for count in tiers),
            -winning,
            identity[2],
        )

    selected = min(statistics, key=rank_key)
    return _identity(selected.get("identity"), context="selector.selected_identity")


def _prediction_for_identity(
    predictions: Mapping[Identity, tuple[Ticket, ...]], identity: Identity
) -> list[list[int]]:
    """Copy an already generated pretarget prediction into the sealed snapshot."""

    try:
        tickets = predictions[identity]
    except KeyError as exc:
        raise ObserverContractError(f"SELECTED_PRETARGET_PREDICTION_MISSING: {identity}") from exc
    return [list(ticket) for ticket in tickets]


def _surface_payload() -> dict[str, Any]:
    return {
        "arm_record_count": len(FROZEN_K_VALUES) * len(FROZEN_WINDOWS) * len(FROZEN_ARMS),
        "arms": list(FROZEN_ARMS),
        "experiment_count": len(FROZEN_K_VALUES) * len(FROZEN_WINDOWS),
        "k_values": list(FROZEN_K_VALUES),
        "windows": [
            {"label": label, "size": window} for label, window in FROZEN_WINDOWS
        ],
    }


def _freeze_snapshot_payload(contract: FreezeContract) -> dict[str, str]:
    return {
        "freeze_boundary_target_identity": contract.boundary,
        "freeze_id": contract.freeze_id,
        "freeze_manifest_sha256": contract.manifest_sha256,
        "source_pilot_result_sha256": contract.pilot_result_sha256,
    }


def pretarget_prepare(
    *,
    target_identity: str,
    pretarget_inputs: Mapping[str, Any],
    freeze_path: Path = DEFAULT_FREEZE_PATH,
) -> dict[str, Any]:
    """Select and seal all frozen arms without accepting a target outcome."""

    target = _target_text(target_identity, context="target_identity")
    contract = load_freeze_contract(freeze_path)
    if int(target) <= int(contract.boundary):
        raise ObserverContractError(
            f"TARGET_AT_OR_BELOW_FREEZE_BOUNDARY: {target} <= {contract.boundary}"
        )
    normalized_inputs, cells = _normalize_pretarget_inputs(
        pretarget_inputs,
        target_identity=target,
        contract=contract,
    )

    experiments: list[dict[str, Any]] = []
    experiment_index = 0
    for k in FROZEN_K_VALUES:
        frozen_cell = contract.cells[k]
        cell_input = cells[k]
        for window_label, window in FROZEN_WINDOWS:
            history_ids = [row.target_identity for row in cell_input.history[-window:]]
            original_statistics = _selector_statistics(
                cell_input, frozen_cell.original_identities, window=window
            )
            representative_statistics = _selector_statistics(
                cell_input, frozen_cell.representative_identities, window=window
            )
            original_selected = _select_strategy(original_statistics)
            representative_selected = _select_strategy(representative_statistics)
            baseline_selected = frozen_cell.baseline_by_window[window]

            arm_material = (
                (
                    FROZEN_ARMS[0],
                    "STRICTLY_CAUSAL_ROLLING_WINDOW_SELECTOR",
                    frozen_cell.original_identities,
                    frozen_cell.original_universe_sha256,
                    original_selected,
                    original_statistics,
                ),
                (
                    FROZEN_ARMS[1],
                    "STRICTLY_CAUSAL_ROLLING_WINDOW_SELECTOR",
                    frozen_cell.representative_identities,
                    frozen_cell.callable_universe_sha256,
                    representative_selected,
                    representative_statistics,
                ),
                (
                    FROZEN_ARMS[2],
                    "STATIC_EXACT_PILOT_FROZEN_BASELINE_IDENTITY",
                    frozen_cell.representative_identities,
                    frozen_cell.callable_universe_sha256,
                    baseline_selected,
                    None,
                ),
            )
            arms: list[dict[str, Any]] = []
            for arm_index, (
                arm,
                selection_mode,
                candidate_identities,
                universe_sha256,
                selected_identity,
                statistics,
            ) in enumerate(arm_material):
                arms.append(
                    {
                        "arm": arm,
                        "arm_index": arm_index,
                        "candidate_identity_count": len(candidate_identities),
                        "candidate_universe_sha256": universe_sha256,
                        "prediction_tickets": _prediction_for_identity(
                            cell_input.predictions, selected_identity
                        ),
                        "selected_callable_identity": frozen_cell.callable_by_identity[
                            selected_identity
                        ],
                        "selected_strategy_identity": list(selected_identity),
                        "selection_mode": selection_mode,
                        "selector_statistics": statistics,
                    }
                )
            experiments.append(
                {
                    "arms": arms,
                    "experiment_id": f"T539:K{k}:{window_label}",
                    "experiment_index": experiment_index,
                    "history_target_identities": history_ids,
                    "k": k,
                    "lottery_id": "T539",
                    "window": window,
                    "window_label": window_label,
                }
            )
            experiment_index += 1

    snapshot: dict[str, Any] = {
        "experiments": experiments,
        "freeze": _freeze_snapshot_payload(contract),
        "input_authority": {
            "identity": normalized_inputs["authority_identity"],
            "schema_version": PRETARGET_INPUT_SCHEMA_VERSION,
            "sha256": _content_sha256(normalized_inputs),
        },
        "outcome_presence_at_prepare": "ABSENT",
        "phase": "PRETARGET_PREPARE",
        "phase_status": "PRETARGET_SNAPSHOT_MATERIALIZED",
        "prospective_classification": "PENDING_EXTERNAL_PRETARGET_SEAL_ATTESTATION",
        "rule_fingerprint": contract.rule_fingerprint,
        "schema_version": PRETARGET_SNAPSHOT_SCHEMA_VERSION,
        "surface": _surface_payload(),
        "target_identity": target,
    }
    snapshot["snapshot_content_hash"] = snapshot_content_hash(snapshot)
    return snapshot


def _validate_selector_statistics(
    value: object,
    *,
    candidates: Sequence[Identity],
    k: int,
    window: int,
    context: str,
) -> None:
    items = _list(value, context=context)
    if len(items) != len(candidates):
        raise ObserverContractError(f"{context} candidate count mismatch")
    observed: list[Identity] = []
    for index, raw_item in enumerate(items):
        item = _mapping(raw_item, context=f"{context}[{index}]")
        _exact_keys(
            item,
            {"identity", "prize_tier_counts", "success_count", "winning_ticket_count"},
            context=f"{context}[{index}]",
        )
        identity = _identity(item.get("identity"), context=f"{context}[{index}].identity")
        success_count = _integer(
            item.get("success_count"), context=f"{context}[{index}].success_count"
        )
        tiers = _tier_vector(
            item.get("prize_tier_counts"),
            context=f"{context}[{index}].prize_tier_counts",
        )
        winning = _integer(
            item.get("winning_ticket_count"),
            context=f"{context}[{index}].winning_ticket_count",
        )
        if (
            success_count > window
            or winning > k * window
            or sum(tiers) != winning
            or success_count > winning
        ):
            raise ObserverContractError(f"{context}[{index}] metric bounds mismatch")
        observed.append(identity)
    if tuple(observed) != tuple(sorted(candidates)):
        raise ObserverContractError(f"{context} candidate identity/order mismatch")


def verify_pretarget_snapshot(
    snapshot: Mapping[str, Any] | None,
    *,
    freeze_path: Path = DEFAULT_FREEZE_PATH,
) -> Mapping[str, Any]:
    """Validate a sealed Phase-1 snapshot without rerunning its selector."""

    if snapshot is None:
        raise ObserverContractError("MISSING_PRETARGET_SNAPSHOT")
    value = _mapping(snapshot, context="snapshot")
    _exact_keys(
        value,
        {
            "experiments",
            "freeze",
            "input_authority",
            "outcome_presence_at_prepare",
            "phase",
            "phase_status",
            "prospective_classification",
            "rule_fingerprint",
            "schema_version",
            "snapshot_content_hash",
            "surface",
            "target_identity",
        },
        context="snapshot",
    )
    supplied_hash = _sha256_text(
        value.get("snapshot_content_hash"), context="snapshot.snapshot_content_hash"
    )
    if supplied_hash != snapshot_content_hash(value):
        raise ObserverContractError("SNAPSHOT_HASH_MISMATCH")

    contract = load_freeze_contract(freeze_path)
    freeze = _mapping(value.get("freeze"), context="snapshot.freeze")
    _exact_keys(
        freeze,
        {
            "freeze_boundary_target_identity",
            "freeze_id",
            "freeze_manifest_sha256",
            "source_pilot_result_sha256",
        },
        context="snapshot.freeze",
    )
    if dict(freeze) != _freeze_snapshot_payload(contract):
        raise ObserverContractError("SNAPSHOT_FREEZE_IDENTITY_MISMATCH")
    if value.get("rule_fingerprint") != contract.rule_fingerprint:
        raise ObserverContractError("RULE_FINGERPRINT_MISMATCH")
    if value.get("schema_version") != PRETARGET_SNAPSHOT_SCHEMA_VERSION:
        raise ObserverContractError("PRETARGET_SNAPSHOT_SCHEMA_VERSION_MISMATCH")
    if (
        value.get("phase") != "PRETARGET_PREPARE"
        or value.get("phase_status") != "PRETARGET_SNAPSHOT_MATERIALIZED"
        or value.get("outcome_presence_at_prepare") != "ABSENT"
        or value.get("prospective_classification")
        != "PENDING_EXTERNAL_PRETARGET_SEAL_ATTESTATION"
    ):
        raise ObserverContractError("PRETARGET_SNAPSHOT_PHASE_MISMATCH")
    target = _target_text(value.get("target_identity"), context="snapshot.target_identity")
    if int(target) <= int(contract.boundary):
        raise ObserverContractError("SNAPSHOT_TARGET_AT_OR_BELOW_FREEZE_BOUNDARY")

    input_authority = _mapping(value.get("input_authority"), context="snapshot.input_authority")
    _exact_keys(
        input_authority,
        {"identity", "schema_version", "sha256"},
        context="snapshot.input_authority",
    )
    _logical_authority_identity(input_authority.get("identity"))
    if input_authority.get("schema_version") != PRETARGET_INPUT_SCHEMA_VERSION:
        raise ObserverContractError("SNAPSHOT_INPUT_AUTHORITY_SCHEMA_MISMATCH")
    _sha256_text(input_authority.get("sha256"), context="snapshot.input_authority.sha256")

    surface = _mapping(value.get("surface"), context="snapshot.surface")
    if dict(surface) != _surface_payload():
        raise ObserverContractError("INCOMPLETE_EXPERIMENT_SURFACE")
    experiments = _list(value.get("experiments"), context="snapshot.experiments")
    if len(experiments) != len(FROZEN_K_VALUES) * len(FROZEN_WINDOWS):
        raise ObserverContractError("INCOMPLETE_EXPERIMENT_SURFACE")

    expected_experiments = [
        (k, label, window)
        for k in FROZEN_K_VALUES
        for label, window in FROZEN_WINDOWS
    ]
    history_by_experiment: dict[tuple[int, int], tuple[str, ...]] = {}
    for index, (raw_experiment, (expected_k, expected_label, expected_window)) in enumerate(
        zip(experiments, expected_experiments, strict=True)
    ):
        experiment = _mapping(raw_experiment, context=f"snapshot.experiments[{index}]")
        _exact_keys(
            experiment,
            {
                "arms",
                "experiment_id",
                "experiment_index",
                "history_target_identities",
                "k",
                "lottery_id",
                "window",
                "window_label",
            },
            context=f"snapshot.experiments[{index}]",
        )
        if (
            experiment.get("experiment_index") != index
            or experiment.get("experiment_id") != f"T539:K{expected_k}:{expected_label}"
            or experiment.get("k") != expected_k
            or experiment.get("lottery_id") != "T539"
            or experiment.get("window") != expected_window
            or experiment.get("window_label") != expected_label
        ):
            raise ObserverContractError("INCOMPLETE_EXPERIMENT_SURFACE")

        raw_history = _list(
            experiment.get("history_target_identities"),
            context=f"snapshot.experiments[{index}].history_target_identities",
        )
        history = tuple(
            _target_text(item, context=f"snapshot.experiments[{index}].history[]")
            for item in raw_history
        )
        if (
            len(history) != expected_window
            or len({int(item) for item in history}) != len(history)
            or tuple(sorted(history, key=lambda item: (int(item), item))) != history
            or any(int(item) >= int(target) for item in history)
        ):
            raise ObserverContractError("SNAPSHOT_HISTORY_BOUNDARY_MISMATCH")
        history_by_experiment[(expected_k, expected_window)] = history

        frozen_cell = contract.cells[expected_k]
        arms = _list(experiment.get("arms"), context=f"snapshot.experiments[{index}].arms")
        if len(arms) != len(FROZEN_ARMS):
            raise ObserverContractError("THREE_ARM_SURFACE_INCOMPLETE")
        for arm_index, (raw_arm, expected_arm) in enumerate(zip(arms, FROZEN_ARMS, strict=True)):
            arm = _mapping(
                raw_arm, context=f"snapshot.experiments[{index}].arms[{arm_index}]"
            )
            _exact_keys(
                arm,
                {
                    "arm",
                    "arm_index",
                    "candidate_identity_count",
                    "candidate_universe_sha256",
                    "prediction_tickets",
                    "selected_callable_identity",
                    "selected_strategy_identity",
                    "selection_mode",
                    "selector_statistics",
                },
                context=f"snapshot.experiments[{index}].arms[{arm_index}]",
            )
            if arm.get("arm") != expected_arm or arm.get("arm_index") != arm_index:
                raise ObserverContractError("THREE_ARM_SURFACE_INCOMPLETE")
            if expected_arm == FROZEN_ARMS[0]:
                candidates = frozen_cell.original_identities
                expected_sha = frozen_cell.original_universe_sha256
                expected_mode = "STRICTLY_CAUSAL_ROLLING_WINDOW_SELECTOR"
            else:
                candidates = frozen_cell.representative_identities
                expected_sha = frozen_cell.callable_universe_sha256
                expected_mode = (
                    "STRICTLY_CAUSAL_ROLLING_WINDOW_SELECTOR"
                    if expected_arm == FROZEN_ARMS[1]
                    else "STATIC_EXACT_PILOT_FROZEN_BASELINE_IDENTITY"
                )
            if (
                arm.get("candidate_identity_count") != len(candidates)
                or arm.get("candidate_universe_sha256") != expected_sha
                or arm.get("selection_mode") != expected_mode
            ):
                raise ObserverContractError("SNAPSHOT_ARM_CONTRACT_MISMATCH")
            selected = _identity(
                arm.get("selected_strategy_identity"),
                context=f"snapshot.experiments[{index}].arms[{arm_index}].selected_identity",
            )
            if selected not in candidates:
                raise ObserverContractError("SNAPSHOT_SELECTED_IDENTITY_OUTSIDE_FROZEN_UNIVERSE")
            if expected_arm == FROZEN_ARMS[2] and selected != frozen_cell.baseline_by_window[
                expected_window
            ]:
                raise ObserverContractError("SNAPSHOT_FROZEN_BASELINE_IDENTITY_MISMATCH")
            if arm.get("selected_callable_identity") != frozen_cell.callable_by_identity[selected]:
                raise ObserverContractError("SNAPSHOT_CALLABLE_IDENTITY_MISMATCH")

            normalized_tickets = _normalize_tickets(
                arm.get("prediction_tickets"),
                k=expected_k,
                context=f"snapshot.experiments[{index}].arms[{arm_index}].prediction_tickets",
            )
            if arm.get("prediction_tickets") != [list(ticket) for ticket in normalized_tickets]:
                raise ObserverContractError("SNAPSHOT_PREDICTION_ORDER_MISMATCH")

            statistics = arm.get("selector_statistics")
            if expected_arm == FROZEN_ARMS[2]:
                if statistics is not None:
                    raise ObserverContractError("SNAPSHOT_FROZEN_BASELINE_HAS_SELECTOR_STATE")
            else:
                _validate_selector_statistics(
                    statistics,
                    candidates=candidates,
                    k=expected_k,
                    window=expected_window,
                    context=f"snapshot.experiments[{index}].arms[{arm_index}].statistics",
                )

    for k in FROZEN_K_VALUES:
        history_50 = history_by_experiment[(k, 50)]
        history_300 = history_by_experiment[(k, 300)]
        history_750 = history_by_experiment[(k, 750)]
        if history_50 != history_300[-50:] or history_300 != history_750[-300:]:
            raise ObserverContractError("SNAPSHOT_HISTORY_WINDOW_SUFFIX_MISMATCH")
    reference_history = history_by_experiment[(FROZEN_K_VALUES[0], 750)]
    if any(
        history_by_experiment[(k, 750)] != reference_history for k in FROZEN_K_VALUES[1:]
    ):
        raise ObserverContractError("SNAPSHOT_HISTORY_TARGET_SET_MISMATCH_ACROSS_CELLS")
    return value


def _normalize_official_outcome(
    value: Mapping[str, Any], *, expected_target_identity: str
) -> dict[str, Any]:
    _exact_keys(
        value,
        {"schema_version", "target_identity", "winning_numbers"},
        context="official_outcome",
    )
    if value.get("schema_version") != POSTTARGET_OUTCOME_SCHEMA_VERSION:
        raise ObserverContractError("OFFICIAL_OUTCOME_SCHEMA_VERSION_MISMATCH")
    target = _target_text(value.get("target_identity"), context="official_outcome.target_identity")
    if target != expected_target_identity:
        raise ObserverContractError(
            f"OUTCOME_TARGET_MISMATCH: {target} != {expected_target_identity}"
        )
    winning_numbers = _normalize_ticket(
        value.get("winning_numbers"), context="official_outcome.winning_numbers"
    )
    return {
        "schema_version": POSTTARGET_OUTCOME_SCHEMA_VERSION,
        "target_identity": target,
        "winning_numbers": list(winning_numbers),
    }


def _score_prediction_tickets(
    value: object, *, winning_numbers: frozenset[int], context: str
) -> dict[str, Any]:
    tickets = _list(value, context=context)
    ticket_scores: list[dict[str, Any]] = []
    tier_counts = [0, 0, 0, 0]
    winning_ticket_count = 0
    for position, raw_ticket in enumerate(tickets, start=1):
        ticket = _normalize_ticket(raw_ticket, context=f"{context}[{position - 1}]")
        matched = sorted(set(ticket) & winning_numbers)
        hits = len(matched)
        if 2 <= hits <= 5:
            winning_ticket_count += 1
            tier_counts[5 - hits] += 1
        ticket_scores.append(
            {
                "hit_count": hits,
                "matched_numbers": matched,
                "ticket": list(ticket),
                "ticket_position": position,
            }
        )
    return {
        "official_any_prize_success": winning_ticket_count > 0,
        "official_prize_tier_count_vector": tier_counts,
        "official_winning_ticket_count": winning_ticket_count,
        "ticket_scores": ticket_scores,
    }


def posttarget_score(
    *,
    snapshot: Mapping[str, Any] | None,
    official_outcome: Mapping[str, Any],
    pretarget_seal_status: str = MISSED_PRETARGET_SEAL,
    freeze_path: Path = DEFAULT_FREEZE_PATH,
) -> dict[str, Any]:
    """Score only the tickets already present in a verified PRETARGET snapshot."""

    verified = verify_pretarget_snapshot(snapshot, freeze_path=freeze_path)
    target = _target_text(verified.get("target_identity"), context="snapshot.target_identity")
    normalized_outcome = _normalize_official_outcome(
        official_outcome, expected_target_identity=target
    )
    if pretarget_seal_status == PRETARGET_SEAL_CONFIRMED:
        prospective_status = VALID_PROSPECTIVE_OBSERVATION
        counts_as_prospective = True
    elif pretarget_seal_status == MISSED_PRETARGET_SEAL:
        prospective_status = MISSED_PRETARGET_SEAL
        counts_as_prospective = False
    else:
        raise ObserverContractError("INVALID_PRETARGET_SEAL_STATUS")

    winning_numbers = frozenset(cast(list[int], normalized_outcome["winning_numbers"]))
    scored_experiments: list[dict[str, Any]] = []
    for raw_experiment in _list(verified.get("experiments"), context="snapshot.experiments"):
        experiment = _mapping(raw_experiment, context="snapshot.experiments[]")
        scored_arms: list[dict[str, Any]] = []
        for raw_arm in _list(experiment.get("arms"), context="snapshot.experiments[].arms"):
            arm = _mapping(raw_arm, context="snapshot.experiments[].arms[]")
            prediction_tickets = _list(
                arm.get("prediction_tickets"),
                context="snapshot.experiments[].arms[].prediction_tickets",
            )
            score = _score_prediction_tickets(
                prediction_tickets,
                winning_numbers=winning_numbers,
                context="snapshot.experiments[].arms[].prediction_tickets",
            )
            scored_arms.append(
                {
                    "arm": arm["arm"],
                    "official_any_prize_success": score["official_any_prize_success"],
                    "official_prize_tier_count_vector": score[
                        "official_prize_tier_count_vector"
                    ],
                    "official_winning_ticket_count": score["official_winning_ticket_count"],
                    "prediction_tickets": [
                        list(cast(list[int], ticket)) for ticket in prediction_tickets
                    ],
                    "selected_callable_identity": arm["selected_callable_identity"],
                    "selected_strategy_identity": list(
                        cast(list[str], arm["selected_strategy_identity"])
                    ),
                    "ticket_scores": score["ticket_scores"],
                }
            )
        scored_experiments.append(
            {
                "arms": scored_arms,
                "experiment_id": experiment["experiment_id"],
                "experiment_index": experiment["experiment_index"],
                "k": experiment["k"],
                "lottery_id": "T539",
                "window": experiment["window"],
                "window_label": experiment["window_label"],
            }
        )

    freeze = _mapping(verified.get("freeze"), context="snapshot.freeze")
    result: dict[str, Any] = {
        "counts_as_valid_prospective_observation": counts_as_prospective,
        "experiments": scored_experiments,
        "freeze_manifest_sha256": freeze["freeze_manifest_sha256"],
        "input_authority": dict(
            _mapping(verified.get("input_authority"), context="snapshot.input_authority")
        ),
        "official_outcome": normalized_outcome,
        "official_outcome_sha256": _content_sha256(normalized_outcome),
        "phase": "POSTTARGET_SCORE",
        "pretarget_seal_status": pretarget_seal_status,
        "pretarget_snapshot_content_hash": verified["snapshot_content_hash"],
        "prospective_observation_status": prospective_status,
        "rule_fingerprint": verified["rule_fingerprint"],
        "schema_version": POSTTARGET_RESULT_SCHEMA_VERSION,
        "score_status": "STRUCTURALLY_VALID_TARGET_SCORE",
        "surface": _surface_payload(),
        "target_identity": target,
    }
    result["result_content_hash"] = result_content_hash(result)
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="phase", required=True)

    prepare = subparsers.add_parser("pretarget-prepare")
    prepare.add_argument("--target-identity", required=True)
    prepare.add_argument("--input-json", type=Path, required=True)
    prepare.add_argument("--snapshot-json", type=Path, required=True)
    prepare.add_argument("--freeze-json", type=Path, default=DEFAULT_FREEZE_PATH)

    score = subparsers.add_parser("posttarget-score")
    score.add_argument("--snapshot-json", type=Path, required=True)
    score.add_argument("--outcome-json", type=Path, required=True)
    score.add_argument("--result-json", type=Path, required=True)
    score.add_argument("--freeze-json", type=Path, default=DEFAULT_FREEZE_PATH)
    score.add_argument(
        "--pretarget-seal-status",
        choices=(PRETARGET_SEAL_CONFIRMED, MISSED_PRETARGET_SEAL),
        default=MISSED_PRETARGET_SEAL,
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.phase == "pretarget-prepare":
        pretarget_inputs = _read_json_object(args.input_json, context="pretarget input")
        snapshot = pretarget_prepare(
            target_identity=args.target_identity,
            pretarget_inputs=pretarget_inputs,
            freeze_path=args.freeze_json,
        )
        args.snapshot_json.write_bytes(canonical_json_bytes(snapshot))
        print(snapshot["snapshot_content_hash"])
        return 0
    if args.phase == "posttarget-score":
        snapshot = _read_json_object(args.snapshot_json, context="pretarget snapshot")
        outcome = _read_json_object(args.outcome_json, context="official outcome")
        result = posttarget_score(
            snapshot=snapshot,
            official_outcome=outcome,
            pretarget_seal_status=args.pretarget_seal_status,
            freeze_path=args.freeze_json,
        )
        args.result_json.write_bytes(canonical_json_bytes(result))
        print(result["result_content_hash"])
        return 0
    raise ObserverContractError(f"unsupported phase: {args.phase}")


if __name__ == "__main__":
    raise SystemExit(main())
