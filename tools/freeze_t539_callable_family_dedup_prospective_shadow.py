"""Build the outcome-free T539 callable-family-dedup prospective freeze.

The only research input is the sealed pilot JSON authenticated from ordinary
file bytes by its exact path, byte size, SHA-256, schema, and embedded authority
manifest.  Its historical commit and tree are descriptive origin metadata only.
This builder never opens a draw database, fetches a draw, replays a strategy, or
scores an observation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

FREEZE_SCHEMA_VERSION = "T539_CALLABLE_FAMILY_DEDUP_PROSPECTIVE_SHADOW_FREEZE_V1"
FREEZE_ID = "T539_CALLABLE_FAMILY_DEDUP_PROSPECTIVE_SHADOW_FREEZE_R1"
PILOT_SCHEMA_VERSION = "CALLABLE_FAMILY_DEDUP_CAUSAL_SELECTOR_PILOT_RESULT_V1"
PILOT_COMMIT = "0a4355cfcd13b26451e6d6c74bc873ca2b12fcdd"
PILOT_TREE = "34c1896bb2a3797ffb57b2bff44f9ddd8bff628e"
PILOT_RESULT_PATH = (
    "docs/research/matrix-native-results/"
    "callable-family-dedup-causal-selector-pilot-r1-result.json"
)
PILOT_RESULT_BLOB_OID = "6448d6f2cdd4f6a14406ba1fd68115bbc2db9120"
PILOT_RESULT_SHA256 = "1a4fbd067f3d9b4735a4a1143b3694222f38f05eb3ec91e4e8b782e0e90c5c86"
PILOT_RESULT_SIZE_BYTES = 532_005
SOURCE_AUTHORITIES_MANIFEST_SHA256 = (
    "53278d1c5bc44f274ae5a102bac6fee73bc71c0af5b6896bb91e3f4b65db8a72"
)
CANONICAL_BASE_HEAD = "07a5c3479123c03fd91b6f1ae2402046b5f16c2a"
CANONICAL_BASE_TREE = "cff549183e67ad49f12afb5076a11b1f8b712dde"

TARGET_LOTTERY_ID = "T539"
SOURCE_AUTHORITY_ID = "T539_HISTORICAL_SQLITE"
WINDOWS: tuple[tuple[str, int], ...] = (("W50", 50), ("W300", 300), ("W750", 750))
REPRESENTATIVE_RULE = "LEXICOGRAPHIC_MINIMUM_COMPLETE_AUTHORITY_QUALIFIED_IDENTITY"
REPRESENTATIVE_IDENTITY_FIELDS: tuple[str, ...] = (
    "source_authority_id",
    "lottery_id",
    "strategy_id",
    "strategy_version",
)
CALLABLE_GROUP_IDENTITY_FIELDS: tuple[str, ...] = (
    "source_authority_id",
    "lottery_id",
    "native_ticket_count",
    "callable_identity",
)
CALLABLE_GROUPING_SCOPE = (
    "SOURCE_AUTHORITY_ID_X_LOTTERY_ID_X_NATIVE_TICKET_COUNT_X_CALLABLE_IDENTITY"
)
FROZEN_SELECTOR_TIE_BREAK: tuple[str, ...] = (
    "OFFICIAL_ANY_PRIZE_TARGET_RATE_DESC",
    "OFFICIAL_PRIZE_TIER_COUNT_VECTOR_DESC",
    "OFFICIAL_WINNING_TICKET_RATE_DESC",
    "STRATEGY_ID_ASC",
)
COMPARATOR_IDS: tuple[str, ...] = (
    "ORIGINAL_ROLLING",
    "CALLABLE_FAMILY_DEDUP_ROLLING",
    "CALLABLE_FAMILY_DEDUP_FROZEN_BASELINE",
)

JSON_OUTPUT_PATH = Path(
    "docs/research/matrix-native-results/"
    "t539-callable-family-dedup-prospective-shadow-freeze-r1.json"
)
MARKDOWN_OUTPUT_PATH = Path(
    "docs/research/t539-callable-family-dedup-prospective-shadow-freeze-r1.md"
)
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
_TARGET_IDENTITY = re.compile(r"[0-9]{1,32}", flags=re.ASCII)


class FreezeContractError(RuntimeError):
    """The sealed source or derived freeze violates the authorized contract."""


def _compact_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def canonical_json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical_sha256(value: object) -> str:
    return _sha256(_compact_bytes(value))


def _mapping(value: object, *, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise FreezeContractError(f"{context} must be a JSON object")
    return cast(dict[str, Any], value)


def _list(value: object, *, context: str) -> list[Any]:
    if not isinstance(value, list):
        raise FreezeContractError(f"{context} must be a JSON array")
    return cast(list[Any], value)


def _text(value: object, *, context: str) -> str:
    if type(value) is not str or not value:
        raise FreezeContractError(f"{context} must be non-empty text")
    return value


def _integer(value: object, *, context: str) -> int:
    if type(value) is not int:
        raise FreezeContractError(f"{context} must be an exact integer")
    return value


def _string_list(value: object, *, context: str) -> list[str]:
    raw = _list(value, context=context)
    if any(type(item) is not str or not item for item in raw):
        raise FreezeContractError(f"{context} must contain non-empty strings")
    return sorted(cast(list[str], raw))


def _candidate_identity(value: object, *, context: str) -> list[str]:
    raw = _list(value, context=context)
    if len(raw) != 4 or any(type(item) is not str or not item for item in raw):
        raise FreezeContractError(f"{context} must be one complete four-field identity")
    return cast(list[str], raw)


def _callable_identity(value: object, *, context: str) -> list[str | int]:
    raw = _list(value, context=context)
    if (
        len(raw) != 4
        or type(raw[0]) is not str
        or type(raw[1]) is not str
        or type(raw[2]) is not int
        or type(raw[3]) is not str
        or not all(raw[index] for index in (0, 1, 3))
    ):
        raise FreezeContractError(f"{context} must be one complete callable identity")
    return cast(list[str | int], raw)


def load_sealed_pilot(repository_root: Path = REPOSITORY_ROOT) -> dict[str, Any]:
    """Load and authenticate the exact committed pilot artifact from ordinary bytes."""

    pilot_path = repository_root / PILOT_RESULT_PATH
    try:
        payload_bytes = pilot_path.read_bytes()
    except OSError as error:
        raise FreezeContractError(
            f"sealed pilot result is unavailable at {PILOT_RESULT_PATH}"
        ) from error
    if len(payload_bytes) != PILOT_RESULT_SIZE_BYTES:
        raise FreezeContractError(
            "pilot result byte-size mismatch: "
            f"expected {PILOT_RESULT_SIZE_BYTES}, observed {len(payload_bytes)}"
        )
    observed_sha256 = _sha256(payload_bytes)
    if observed_sha256 != PILOT_RESULT_SHA256:
        raise FreezeContractError(
            "pilot result SHA-256 mismatch: "
            f"expected {PILOT_RESULT_SHA256}, observed {observed_sha256}"
        )
    try:
        parsed = json.loads(payload_bytes)
    except json.JSONDecodeError as error:
        raise FreezeContractError("sealed pilot result is not valid JSON") from error
    pilot = _mapping(parsed, context="sealed pilot")
    if pilot.get("schema_version") != PILOT_SCHEMA_VERSION:
        raise FreezeContractError("sealed pilot schema_version changed")
    source_authorities = _mapping(
        pilot.get("source_authorities"), context="source_authorities"
    )
    observed_manifest_sha256 = _canonical_sha256(source_authorities)
    if observed_manifest_sha256 != SOURCE_AUTHORITIES_MANIFEST_SHA256:
        raise FreezeContractError(
            "sealed pilot source_authorities manifest SHA-256 mismatch: "
            f"expected {SOURCE_AUTHORITIES_MANIFEST_SHA256}, "
            f"observed {observed_manifest_sha256}"
        )
    canonical_base = _mapping(pilot.get("canonical_base"), context="canonical_base")
    if canonical_base != {
        "expected_head": CANONICAL_BASE_HEAD,
        "expected_tree": CANONICAL_BASE_TREE,
    }:
        raise FreezeContractError("sealed pilot canonical base changed")
    return pilot


def derive_freeze_boundary(pilot: Mapping[str, Any]) -> tuple[str, list[dict[str, str]], int]:
    """Return the maximum target identity actually evaluated by the sealed pilot."""

    references: list[tuple[str, str, str]] = []
    for cell_index, raw_cell in enumerate(_list(pilot.get("cells"), context="cells")):
        cell = _mapping(raw_cell, context=f"cells[{cell_index}]")
        cell_id = _text(cell.get("cell_id"), context=f"cells[{cell_index}].cell_id")
        for experiment_index, raw_experiment in enumerate(
            _list(cell.get("experiments"), context=f"{cell_id}.experiments")
        ):
            experiment = _mapping(
                raw_experiment,
                context=f"{cell_id}.experiments[{experiment_index}]",
            )
            eligible_count = _integer(
                experiment.get("eligible_target_count"),
                context=f"{cell_id}.eligible_target_count",
            )
            target = experiment.get("last_target")
            if eligible_count == 0:
                if target is not None:
                    raise FreezeContractError(
                        f"{cell_id} has a last_target without an evaluated target"
                    )
                continue
            target_text = _text(target, context=f"{cell_id}.last_target")
            if _TARGET_IDENTITY.fullmatch(target_text) is None:
                raise FreezeContractError(f"{cell_id} has a non-canonical last_target")
            window_label = _text(
                experiment.get("window_label"),
                context=f"{cell_id}.window_label",
            )
            references.append((target_text, cell_id, window_label))
    if not references:
        raise FreezeContractError("sealed pilot has no evaluated target identity")
    boundary = max(references, key=lambda item: (int(item[0]), item[0]))[0]
    contributors = [
        {"cell_id": cell_id, "window_label": window_label}
        for target, cell_id, window_label in references
        if target == boundary
    ]
    contributors.sort(key=lambda item: (item["cell_id"], item["window_label"]))
    return boundary, contributors, len(references)


def is_future_target_admissible(target_identity: str, freeze_boundary: str) -> bool:
    """Apply the frozen, fail-closed decimal target-identity boundary."""

    for value, label in (
        (target_identity, "target_identity"),
        (freeze_boundary, "freeze_boundary"),
    ):
        if type(value) is not str or _TARGET_IDENTITY.fullmatch(value) is None:
            raise FreezeContractError(f"{label} must contain 1-32 ASCII decimal digits")
    return int(target_identity) > int(freeze_boundary)


def _family_contract(
    raw_family: object,
    *,
    cell_id: str,
    source_authority_id: str,
    lottery_id: str,
    native_ticket_count: int,
    index: int,
) -> dict[str, Any]:
    context = f"{cell_id}.callable_families[{index}]"
    family = _mapping(raw_family, context=context)
    callable_id = _text(family.get("callable_identity"), context=f"{context}.callable_identity")
    authority_identity = _callable_identity(
        family.get("authority_qualified_callable_identity"),
        context=f"{context}.authority_qualified_callable_identity",
    )
    if authority_identity != [
        source_authority_id,
        lottery_id,
        native_ticket_count,
        callable_id,
    ]:
        raise FreezeContractError(f"{context} callable identity is not authority-qualified")

    raw_members = _list(family.get("member_identities"), context=f"{context}.member_identities")
    members = sorted(
        (_candidate_identity(item, context=f"{context}.member_identities") for item in raw_members),
        key=tuple,
    )
    if not members or len({tuple(item) for item in members}) != len(members):
        raise FreezeContractError(f"{context} members must be non-empty and unique")
    if any(item[:2] != [source_authority_id, lottery_id] for item in members):
        raise FreezeContractError(f"{context} contains a candidate from another authority")
    representative = _candidate_identity(
        family.get("representative_identity"),
        context=f"{context}.representative_identity",
    )
    expected_representative = min(members, key=tuple)
    if representative != expected_representative:
        raise FreezeContractError(f"{context} representative is not the lexicographic minimum")
    removed = sorted(
        (
            _candidate_identity(item, context=f"{context}.removed_sibling_identities")
            for item in _list(
                family.get("removed_sibling_identities"),
                context=f"{context}.removed_sibling_identities",
            )
        ),
        key=tuple,
    )
    expected_removed = [item for item in members if item != representative]
    if removed != expected_removed:
        raise FreezeContractError(f"{context} removed siblings do not match the family members")
    if family.get("representative_rule") != REPRESENTATIVE_RULE:
        raise FreezeContractError(f"{context} representative rule changed")
    if family.get("member_count") != len(members):
        raise FreezeContractError(f"{context} member_count changed")
    if family.get("removed_sibling_count") != len(removed):
        raise FreezeContractError(f"{context} removed_sibling_count changed")

    return {
        "authority_qualified_callable_identity": authority_identity,
        "callable_identity": callable_id,
        "callable_labels": _string_list(
            family.get("callable_labels"), context=f"{context}.callable_labels"
        ),
        "member_identities": members,
        "removed_sibling_identities": removed,
        "representative_identity": representative,
        "resolution_authorities": _string_list(
            family.get("resolution_authorities"),
            context=f"{context}.resolution_authorities",
        ),
    }


def _complete_window_experiments(cell: Mapping[str, Any], *, cell_id: str) -> dict[str, Any] | None:
    experiments: dict[str, Any] = {}
    for index, raw_experiment in enumerate(
        _list(cell.get("experiments"), context=f"{cell_id}.experiments")
    ):
        experiment = _mapping(raw_experiment, context=f"{cell_id}.experiments[{index}]")
        label = _text(experiment.get("window_label"), context=f"{cell_id}.window_label")
        if label in experiments:
            raise FreezeContractError(f"{cell_id} contains duplicate window {label}")
        experiments[label] = experiment
    if set(experiments) != {label for label, _ in WINDOWS}:
        return None
    for label, size in WINDOWS:
        experiment = _mapping(experiments[label], context=f"{cell_id}.{label}")
        exclusions = _mapping(experiment.get("exclusions"), context=f"{cell_id}.{label}.exclusions")
        if (
            experiment.get("window") != size
            or exclusions.get("original_status") != "COMPLETE"
            or exclusions.get("dedup_status") != "COMPLETE"
        ):
            return None
    return experiments


def _cell_contract(raw_cell: object, *, index: int) -> dict[str, Any] | None:
    context = f"cells[{index}]"
    cell = _mapping(raw_cell, context=context)
    if cell.get("lottery_id") != TARGET_LOTTERY_ID:
        return None
    cell_id = _text(cell.get("cell_id"), context=f"{context}.cell_id")
    source_authority_id = _text(
        cell.get("source_authority_id"), context=f"{cell_id}.source_authority_id"
    )
    if source_authority_id != SOURCE_AUTHORITY_ID:
        raise FreezeContractError(f"{cell_id} source authority changed")
    native_ticket_count = _integer(cell.get("k"), context=f"{cell_id}.k")
    if cell_id != f"{TARGET_LOTTERY_ID}:K{native_ticket_count}":
        raise FreezeContractError(f"{cell_id} does not match its native ticket count")
    experiments = _complete_window_experiments(cell, cell_id=cell_id)
    if experiments is None:
        return None

    families = [
        _family_contract(
            item,
            cell_id=cell_id,
            source_authority_id=source_authority_id,
            lottery_id=TARGET_LOTTERY_ID,
            native_ticket_count=native_ticket_count,
            index=family_index,
        )
        for family_index, item in enumerate(
            _list(cell.get("callable_families"), context=f"{cell_id}.callable_families")
        )
    ]
    families.sort(key=lambda item: tuple(item["authority_qualified_callable_identity"]))
    original_candidates = sorted(
        (
            identity
            for family in families
            for identity in cast(list[list[str]], family["member_identities"])
        ),
        key=tuple,
    )
    representatives = sorted(
        (cast(list[str], family["representative_identity"]) for family in families),
        key=tuple,
    )
    removed_siblings = sorted(
        (
            identity
            for family in families
            for identity in cast(list[list[str]], family["removed_sibling_identities"])
        ),
        key=tuple,
    )
    if len({tuple(item) for item in original_candidates}) != len(original_candidates):
        raise FreezeContractError(f"{cell_id} contains a candidate in more than one family")
    if cell.get("original_candidate_count") != len(original_candidates):
        raise FreezeContractError(f"{cell_id} original candidate count changed")
    if cell.get("deduplicated_callable_count") != len(families):
        raise FreezeContractError(f"{cell_id} callable count changed")
    if cell.get("removed_sibling_count") != len(removed_siblings):
        raise FreezeContractError(f"{cell_id} removed sibling count changed")

    representative_by_strategy = {identity[2]: identity for identity in representatives}
    window_contracts: list[dict[str, Any]] = []
    for label, size in WINDOWS:
        experiment = _mapping(experiments[label], context=f"{cell_id}.{label}")
        baseline_strategy_id = _text(
            experiment.get("dedup_frozen_strategy_id"),
            context=f"{cell_id}.{label}.dedup_frozen_strategy_id",
        )
        baseline_identity = representative_by_strategy.get(baseline_strategy_id)
        if baseline_identity is None:
            raise FreezeContractError(
                f"{cell_id}.{label} frozen baseline is outside the callable-reduced universe"
            )
        window_contracts.append(
            {
                "callable_family_dedup_frozen_baseline_identity": baseline_identity,
                "label": label,
                "size": size,
            }
        )

    original_material = {
        "candidates": original_candidates,
        "identity_fields": list(REPRESENTATIVE_IDENTITY_FIELDS),
    }
    reduced_material = {
        "identity_fields": list(REPRESENTATIVE_IDENTITY_FIELDS),
        "representatives": representatives,
    }
    return {
        "callable_families": families,
        "callable_reduced_universe_sha256": _canonical_sha256(reduced_material),
        "cell_id": cell_id,
        "deduplicated_callable_count": len(families),
        "lottery_id": TARGET_LOTTERY_ID,
        "native_ticket_count": native_ticket_count,
        "original_candidate_count": len(original_candidates),
        "original_candidate_universe": original_candidates,
        "original_candidate_universe_sha256": _canonical_sha256(original_material),
        "removed_sibling_count": len(removed_siblings),
        "windows": window_contracts,
    }


def _copy_selector_runner_locator(source_authorities: Mapping[str, Any]) -> dict[str, Any]:
    runner = _mapping(
        source_authorities.get("original_selector_runner"),
        context="source_authorities.original_selector_runner",
    )
    required = ("blob_oid", "commit", "path", "sha256", "size_bytes", "tree")
    copied: dict[str, Any] = {}
    for key in required:
        value = runner.get(key)
        if key == "size_bytes":
            copied[key] = _integer(value, context=f"original_selector_runner.{key}")
        else:
            copied[key] = _text(value, context=f"original_selector_runner.{key}")
    return copied


def build_manifest(pilot: Mapping[str, Any]) -> dict[str, Any]:
    """Derive the complete immutable freeze contract from the authenticated pilot."""

    if pilot.get("schema_version") != PILOT_SCHEMA_VERSION:
        raise FreezeContractError("sealed pilot schema_version changed")
    pilot_rule = _mapping(pilot.get("dedup_rule"), context="dedup_rule")
    if (
        pilot_rule.get("grouping_scope") != CALLABLE_GROUPING_SCOPE
        or pilot_rule.get("representative_rule") != REPRESENTATIVE_RULE
        or pilot_rule.get("representative_identity_order")
        != list(REPRESENTATIVE_IDENTITY_FIELDS)
        or pilot_rule.get("historical_outcomes_used_for_representative") is not False
        or pilot_rule.get("representative_sweep") != "NOT_RUN"
    ):
        raise FreezeContractError("sealed pilot callable-family rule changed")
    pilot_windows = _mapping(pilot.get("windows"), context="windows")
    if pilot_windows != {label: size for label, size in WINDOWS}:
        raise FreezeContractError("sealed pilot window contract changed")
    invariants = _mapping(pilot.get("invariants"), context="invariants")
    if invariants.get("selector_tie_break") != "ORIGINAL_UNCHANGED_AFTER_UNIVERSE_REDUCTION":
        raise FreezeContractError("sealed pilot selector tie-break invariant changed")

    cells = [
        contract
        for index, raw_cell in enumerate(_list(pilot.get("cells"), context="cells"))
        if (contract := _cell_contract(raw_cell, index=index)) is not None
    ]
    cells.sort(key=lambda item: cast(int, item["native_ticket_count"]))
    if not cells:
        raise FreezeContractError("sealed pilot contains no complete T539 cell")
    ticket_counts = [cast(int, item["native_ticket_count"]) for item in cells]
    if len(ticket_counts) != len(set(ticket_counts)):
        raise FreezeContractError("sealed pilot contains duplicate complete T539 cells")

    boundary, boundary_contributors, last_target_reference_count = derive_freeze_boundary(pilot)
    source_authorities = _mapping(pilot.get("source_authorities"), context="source_authorities")
    primary_metric = _mapping(pilot.get("primary_metric"), context="primary_metric")
    primary_metric_id = _text(primary_metric.get("id"), context="primary_metric.id")
    candidate_count = sum(cast(int, item["original_candidate_count"]) for item in cells)
    callable_count = sum(cast(int, item["deduplicated_callable_count"]) for item in cells)
    removed_count = sum(cast(int, item["removed_sibling_count"]) for item in cells)
    cell_universe_identities = [
        {
            "cell_id": item["cell_id"],
            "original_candidate_count": item["original_candidate_count"],
            "sha256": item["original_candidate_universe_sha256"],
        }
        for item in cells
    ]
    reduced_universe_identities = [
        {
            "cell_id": item["cell_id"],
            "representative_count": item["deduplicated_callable_count"],
            "sha256": item["callable_reduced_universe_sha256"],
        }
        for item in cells
    ]

    manifest: dict[str, Any] = {
        "callable_family_grouping": {
            "callable_count_sum_across_cells": callable_count,
            "group_identity_fields": list(CALLABLE_GROUP_IDENTITY_FIELDS),
            "grouping_scope": CALLABLE_GROUPING_SCOPE,
            "removed_sibling_count_sum_across_cells": removed_count,
        },
        "cells": cells,
        "comparators": [
            {
                "id": "ORIGINAL_ROLLING",
                "selection_mode": "STRICTLY_CAUSAL_ROLLING_WINDOW_SELECTOR",
                "universe_reference": "cells[].original_candidate_universe",
                "universe_sha256_field": "cells[].original_candidate_universe_sha256",
            },
            {
                "id": "CALLABLE_FAMILY_DEDUP_ROLLING",
                "selection_mode": "STRICTLY_CAUSAL_ROLLING_WINDOW_SELECTOR",
                "universe_reference": "cells[].callable_families[].representative_identity",
                "universe_sha256_field": "cells[].callable_reduced_universe_sha256",
            },
            {
                "baseline_identity_field": (
                    "cells[].windows[].callable_family_dedup_frozen_baseline_identity"
                ),
                "id": "CALLABLE_FAMILY_DEDUP_FROZEN_BASELINE",
                "selection_mode": "STATIC_EXACT_PILOT_FROZEN_BASELINE_IDENTITY",
                "universe_reference": "cells[].callable_families[].representative_identity",
                "universe_sha256_field": "cells[].callable_reduced_universe_sha256",
            },
        ],
        "freeze_boundary": {
            "comparison_type": "UNSIGNED_DECIMAL_INTEGER",
            "contributors": boundary_contributors,
            "derivation": "MAXIMUM_HISTORICAL_TARGET_IDENTITY_ACTUALLY_EVALUATED_BY_PILOT",
            "inclusive_historical_boundary": True,
            "last_target_reference_count": last_target_reference_count,
            "source_field": "cells[].experiments[].last_target",
            "target_identity": boundary,
        },
        "freeze_id": FREEZE_ID,
        "freeze_integrity": {
            "database_access": "NO",
            "future_outcome_access": "NO",
            "historical_replay": "NOT_RUN",
            "network_draw_refresh": "NOT_RUN",
            "post_freeze_outcome_records": [],
            "predictive_advantage": "NOT_ESTABLISHED",
            "profitability": "NOT_ESTABLISHED",
            "prospective_observation_records": [],
            "prospective_observations": 0,
            "strategy_rerun": "NOT_RUN",
        },
        "future_target_admissibility": {
            "eligible_rule": "target_identity > FREEZE_BOUNDARY",
            "eligible_status": "ELIGIBLE_STRICTLY_AFTER_FREEZE_BOUNDARY",
            "ineligible_status": "INELIGIBLE_AT_OR_BEFORE_FREEZE_BOUNDARY",
            "outcome_presence_at_prediction": "ABSENT",
            "predicate": "int(target_identity) > int(freeze_boundary.target_identity)",
            "rejected_identity_status": "REJECTED_NON_CANONICAL_TARGET_IDENTITY",
            "target_identity_format": "1_TO_32_ASCII_DECIMAL_DIGITS",
        },
        "original_candidate_universe": {
            "candidate_count_sum_across_cells": candidate_count,
            "cell_universes": cell_universe_identities,
            "identity_fields": list(REPRESENTATIVE_IDENTITY_FIELDS),
            "sha256": _canonical_sha256(cell_universe_identities),
        },
        "prospective_observer_compatibility": {
            "outcome_presence_at_prediction": ["ABSENT", "PRESENT"],
            "prediction_availability": ["AVAILABLE", "UNAVAILABLE"],
            "prediction_schema_version": "1.0.0",
            "prediction_sync_status": ["CREATED", "EXACT_IDEMPOTENT_NO_OP"],
            "score_availability": ["SCORED", "UNAVAILABLE_PREDICTION"],
            "score_schema_version": "1.0.0",
            "score_sync_status": [
                "CREATED",
                "EXACT_IDEMPOTENT_NO_OP",
                "OUTCOME_UNAVAILABLE",
            ],
            "shared_runtime_change": "NOT_REQUIRED",
            "temporal_provenance_required": "POST_FREEZE_DATE_PROSPECTIVE",
        },
        "representative_selection": {
            "chosen_representative_count": callable_count,
            "historical_outcomes_used": False,
            "identity_order": list(REPRESENTATIVE_IDENTITY_FIELDS),
            "removed_sibling_count": removed_count,
            "representative_sweep": "NOT_RUN",
            "rule": REPRESENTATIVE_RULE,
        },
        "result_status_vocabulary": {
            "prediction_availability": ["AVAILABLE", "UNAVAILABLE"],
            "prediction_sync": ["CREATED", "EXACT_IDEMPOTENT_NO_OP"],
            "score_availability": ["SCORED", "UNAVAILABLE_PREDICTION"],
            "score_sync": ["CREATED", "EXACT_IDEMPOTENT_NO_OP", "OUTCOME_UNAVAILABLE"],
            "target_admissibility": [
                "ELIGIBLE_STRICTLY_AFTER_FREEZE_BOUNDARY",
                "INELIGIBLE_AT_OR_BEFORE_FREEZE_BOUNDARY",
                "REJECTED_NON_CANONICAL_TARGET_IDENTITY",
            ],
        },
        "schema_version": FREEZE_SCHEMA_VERSION,
        "selector_contract": {
            "causal_history_rule": "EVERY_SELECTOR_INPUT_TARGET_IS_STRICTLY_BEFORE_TARGET",
            "current_target_excluded_from_history": True,
            "frozen_tie_break": list(FROZEN_SELECTOR_TIE_BREAK),
            "no_preferred_historical_window": True,
            "primary_metric_id": primary_metric_id,
            "rolling_history_rule": "EXACT_IMMEDIATELY_PRECEDING_WINDOW_TARGETS",
            "weighted_windows": "FORBIDDEN",
        },
        "source_pilot": {
            "canonical_base_head": CANONICAL_BASE_HEAD,
            "canonical_base_tree": CANONICAL_BASE_TREE,
            "commit": PILOT_COMMIT,
            "embedded_authority_manifest_key": "source_authorities",
            "embedded_authority_manifest_sha256": _canonical_sha256(source_authorities),
            "original_selector_runner": _copy_selector_runner_locator(source_authorities),
            "result_path": PILOT_RESULT_PATH,
            "result_schema_version": PILOT_SCHEMA_VERSION,
            "result_sha256": PILOT_RESULT_SHA256,
            "result_size_bytes": PILOT_RESULT_SIZE_BYTES,
            "supporting_research_locator_policy": "SOLE_EMBEDDED_AUTHORITY_MANIFEST",
            "tree": PILOT_TREE,
        },
        "surface": {
            "cell_inclusion_rule": (
                "EVERY_T539_CELL_COMPLETE_FOR_ORIGINAL_AND_DEDUP_IN_ALL_PILOT_WINDOWS"
            ),
            "included_cell_count": len(cells),
            "included_native_ticket_counts": ticket_counts,
            "lottery_id": TARGET_LOTTERY_ID,
            "windows": [{"label": label, "size": size} for label, size in WINDOWS],
        },
        "callable_reduced_universe": {
            "cell_universes": reduced_universe_identities,
            "representative_count_sum_across_cells": callable_count,
            "sha256": _canonical_sha256(reduced_universe_identities),
        },
    }
    if [item["id"] for item in manifest["comparators"]] != list(COMPARATOR_IDS):
        raise FreezeContractError("comparator order changed")
    manifest["immutable_rule_fingerprint"] = {
        "algorithm": "SHA-256",
        "canonicalization": "UTF8_COMPACT_JSON_SORTED_KEYS_NO_TRAILING_NEWLINE",
        "sha256": compute_rule_fingerprint(manifest),
    }
    return manifest


def compute_rule_fingerprint(manifest: Mapping[str, Any]) -> str:
    material = {
        key: value
        for key, value in manifest.items()
        if key != "immutable_rule_fingerprint"
    }
    return _canonical_sha256(material)


def _code(value: object) -> str:
    return f"`{str(value).replace('`', '')}`"


def render_markdown(
    manifest: Mapping[str, Any],
    *,
    json_sha256: str,
    json_size_bytes: int,
) -> bytes:
    source = _mapping(manifest.get("source_pilot"), context="source_pilot")
    boundary = _mapping(manifest.get("freeze_boundary"), context="freeze_boundary")
    surface = _mapping(manifest.get("surface"), context="surface")
    original = _mapping(
        manifest.get("original_candidate_universe"), context="original_candidate_universe"
    )
    reduced = _mapping(
        manifest.get("callable_reduced_universe"), context="callable_reduced_universe"
    )
    representative = _mapping(
        manifest.get("representative_selection"), context="representative_selection"
    )
    fingerprint = _mapping(
        manifest.get("immutable_rule_fingerprint"), context="immutable_rule_fingerprint"
    )
    cells = _list(manifest.get("cells"), context="cells")
    lines = [
        "# T539 callable-family-dedup prospective shadow freeze R1",
        "",
        "> Preregistration/freeze only. This artifact evaluates no post-freeze outcome and "
        "establishes neither predictive advantage nor profitability.",
        "",
        "## Frozen source and boundary",
        "",
        f"- Pilot commit: {_code(source['commit'])}",
        f"- Pilot tree: {_code(source['tree'])}",
        f"- Pilot result SHA-256: {_code(source['result_sha256'])}",
        f"- Pilot result bytes: {_code(source['result_size_bytes'])}",
        f"- Freeze boundary: {_code(boundary['target_identity'])}",
        "- Future admissibility: "
        f"{_code('target_identity > ' + cast(str, boundary['target_identity']))}",
        f"- Immutable rule fingerprint: {_code(fingerprint['sha256'])}",
        f"- JSON artifact SHA-256: {_code(json_sha256)} ({json_size_bytes} bytes)",
        "",
        "The pilot JSON's embedded `source_authorities` manifest is the sole supporting "
        "research locator. The boundary is the maximum non-null historical `last_target` "
        "actually evaluated by that sealed pilot.",
        "",
        "## Frozen experiment surface",
        "",
        f"- Lottery: {_code(surface['lottery_id'])}",
        "- Native ticket counts: "
        + ", ".join(
            _code(item)
            for item in cast(list[int], surface["included_native_ticket_counts"])
        ),
        "- Windows: `W50`, `W300`, `W750` (no preferred or weighted window)",
        "- Original candidates across cells: "
        f"{_code(original['candidate_count_sum_across_cells'])}",
        "- Callable representatives across cells: "
        f"{_code(reduced['representative_count_sum_across_cells'])}",
        "- Removed sibling identities across cells: "
        f"{_code(representative['removed_sibling_count'])}",
        "",
        "| Cell | K | Original | Callable | Removed | Windows |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for raw_cell in cells:
        cell = _mapping(raw_cell, context="cell")
        window_labels = ", ".join(
            cast(str, _mapping(item, context="window")["label"])
            for item in _list(cell["windows"], context="cell.windows")
        )
        lines.append(
            f"| {_code(cell['cell_id'])} | {cell['native_ticket_count']} | "
            f"{cell['original_candidate_count']} | {cell['deduplicated_callable_count']} | "
            f"{cell['removed_sibling_count']} | {window_labels} |"
        )

    lines.extend(
        [
            "",
            "## Frozen selector and comparators",
            "",
            "The selector uses exactly the immediately preceding window targets, all strictly "
            "before the target. The frozen tie-break is:",
            "",
        ]
    )
    for item in FROZEN_SELECTOR_TIE_BREAK:
        lines.append(f"1. {_code(item)}")
    lines.extend(
        [
            "",
            "The future contract contains exactly three arms:",
            "",
            "1. `ORIGINAL_ROLLING` — causal rolling selection over each cell's complete original "
            "candidate universe.",
            "2. `CALLABLE_FAMILY_DEDUP_ROLLING` — the same selector over the frozen callable "
            "representatives.",
            "3. `CALLABLE_FAMILY_DEDUP_FROZEN_BASELINE` — the exact per-cell/window baseline "
            "identity sealed below.",
            "",
            "Both dedup arms reference the identical per-cell "
            "`callable_reduced_universe_sha256`.",
            "",
            "### Fixed dedup baseline identities",
            "",
            "| Cell | Window | Complete identity |",
            "|---|---|---|",
        ]
    )
    for raw_cell in cells:
        cell = _mapping(raw_cell, context="cell")
        for raw_window in _list(cell["windows"], context="cell.windows"):
            window = _mapping(raw_window, context="window")
            identity = cast(list[str], window["callable_family_dedup_frozen_baseline_identity"])
            lines.append(
                f"| {_code(cell['cell_id'])} | {_code(window['label'])} | "
                f"{_code(' / '.join(identity))} |"
            )

    lines.extend(
        [
            "",
            "## Frozen callable representatives",
            "",
            "Each representative is the lexicographically smallest complete identity ordered by "
            "`(source_authority_id, lottery_id, strategy_id, strategy_version)`. Historical "
            "performance is not an input to representative selection.",
            "",
            "| Cell | Callable identity | Representative | Removed siblings |",
            "|---|---|---|---|",
        ]
    )
    for raw_cell in cells:
        cell = _mapping(raw_cell, context="cell")
        for raw_family in _list(cell["callable_families"], context="callable_families"):
            family = _mapping(raw_family, context="family")
            rep = " / ".join(cast(list[str], family["representative_identity"]))
            removed = [
                " / ".join(item)
                for item in cast(list[list[str]], family["removed_sibling_identities"])
            ]
            lines.append(
                f"| {_code(cell['cell_id'])} | {_code(family['callable_identity'])} | "
                f"{_code(rep)} | {_code('; '.join(removed) if removed else 'NONE')} |"
            )

    lines.extend(
        [
            "",
            "## Prospective boundary and status contract",
            "",
            f"A target is eligible only when {_code('target_identity > FREEZE_BOUNDARY')}, where "
            f"`FREEZE_BOUNDARY = {boundary['target_identity']}`. A target at or before the "
            "boundary is ineligible. Prediction input must report outcome presence as `ABSENT`, "
            "and its causal history must end strictly before the target.",
            "",
            "The existing observer vocabulary is reused: prediction entries are `AVAILABLE` or "
            "`UNAVAILABLE`; score entries are `SCORED` or `UNAVAILABLE_PREDICTION`; score sync can "
            "also return `OUTCOME_UNAVAILABLE`. No shared prospective runtime change is required.",
            "",
            "## Freeze integrity",
            "",
            "```text",
            "FUTURE_OUTCOME_ACCESS = NO",
            "PROSPECTIVE_OBSERVATIONS = 0",
            "HISTORICAL_REPLAY = NOT RUN",
            "STRATEGY_RERUN = NOT RUN",
            "DB_ACCESS = NO",
            "PREDICTIVE_ADVANTAGE = NOT ESTABLISHED",
            "PROFITABILITY = NOT ESTABLISHED",
            "```",
            "",
        ]
    )
    return "\n".join(lines).encode("utf-8")


def build_artifact_bytes(
    repository_root: Path = REPOSITORY_ROOT,
) -> tuple[dict[str, Any], bytes, bytes]:
    pilot = load_sealed_pilot(repository_root)
    manifest = build_manifest(pilot)
    json_bytes = canonical_json_bytes(manifest)
    markdown_bytes = render_markdown(
        manifest,
        json_sha256=_sha256(json_bytes),
        json_size_bytes=len(json_bytes),
    )
    return manifest, json_bytes, markdown_bytes


def write_artifacts(repository_root: Path = REPOSITORY_ROOT) -> dict[str, str | int]:
    _, json_bytes, markdown_bytes = build_artifact_bytes(repository_root)
    json_path = repository_root / JSON_OUTPUT_PATH
    markdown_path = repository_root / MARKDOWN_OUTPUT_PATH
    if not json_path.parent.is_dir() or not markdown_path.parent.is_dir():
        raise FreezeContractError("authorized output parent directory is missing")
    json_path.write_bytes(json_bytes)
    markdown_path.write_bytes(markdown_bytes)
    return {
        "json_bytes": len(json_bytes),
        "json_sha256": _sha256(json_bytes),
        "markdown_bytes": len(markdown_bytes),
        "markdown_sha256": _sha256(markdown_bytes),
    }


def check_artifacts(repository_root: Path = REPOSITORY_ROOT) -> dict[str, str | int]:
    _, expected_json, expected_markdown = build_artifact_bytes(repository_root)
    json_path = repository_root / JSON_OUTPUT_PATH
    markdown_path = repository_root / MARKDOWN_OUTPUT_PATH
    if not json_path.is_file() or json_path.read_bytes() != expected_json:
        raise FreezeContractError(f"{JSON_OUTPUT_PATH} is missing or stale")
    if not markdown_path.is_file() or markdown_path.read_bytes() != expected_markdown:
        raise FreezeContractError(f"{MARKDOWN_OUTPUT_PATH} is missing or stale")
    return {
        "json_bytes": len(expected_json),
        "json_sha256": _sha256(expected_json),
        "markdown_bytes": len(expected_markdown),
        "markdown_sha256": _sha256(expected_markdown),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify the two authorized artifacts without writing",
    )
    arguments = parser.parse_args()
    result = check_artifacts() if arguments.check else write_artifacts()
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
