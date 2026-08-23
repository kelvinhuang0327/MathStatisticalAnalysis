"""Frozen Lane-1 BigLotto cross-family redundancy-pruned ensemble.

This module is deliberately a small boundary around already-frozen parent
candidate producers.  It reads one immutable redundancy authority snapshot,
requires every independent parent to be available, and unions the native
ticket portfolios of the retained families.  It does not recompute
redundancy metrics, read outcomes, refresh membership, or register a
production strategy.
"""

from __future__ import annotations

import csv
import hashlib
import inspect
import io
import json
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from itertools import combinations, islice, pairwise
from pathlib import Path
from types import MappingProxyType
from typing import Final, cast

type Ticket = tuple[int, int, int, int, int, int]
type TicketPortfolio = tuple[Ticket, ...]
type HistoryInput = Sequence[object] | Iterable[object]
type ParentProvider = Callable[..., object]

HYPOTHESIS_VERSION: Final[str] = "V1"
HYPOTHESIS_ID: Final[str] = "XFAM_H_REDUNDANCY_PRUNED_ENSEMBLE"
NEW_FAMILY_ID: Final[str] = "CROSS_FAMILY_REDUNDANCY_PRUNED_ENSEMBLE_V1"
METHOD_FAMILY: Final[str] = (
    "Cross-family portfolio construction via redundancy-based family pruning"
)
LOTTERY_TYPE: Final[str] = "BIG_LOTTO"
PICK_COUNT: Final[int] = 6
NUMBER_DOMAIN: Final[tuple[int, int]] = (1, 49)
HISTORY_ORDER: Final[str] = "CHRONOLOGICAL_OLDEST_TO_NEWEST"
MINIMUM_HISTORY: Final[int] = 751
CAUSAL_CUTOFF_RULE: Final[str] = "STRICTLY_PRIOR_HISTORY_EXCLUSIVE_TARGET_INDEX"
PARAMETER_SELECTION_RULE: Final[str] = "FIXED_FROZEN_AUTHORITY_NO_OUTCOME_TUNING"
DETERMINISM_CLASS: Final[str] = "PURE_DETERMINISTIC_NO_RNG"
RNG_SEMANTICS: Final[str] = "NONE"
OUTPUT_SHAPE: Final[str] = "PORTFOLIO"

INDEPENDENT_FAMILIES: Final[tuple[str, ...]] = (
    "MULTISCALE_FREQUENCY",
    "CONDITIONAL_COOCCURRENCE",
    "GRAPH_NETWORK",
    "MULTISCALE_OMISSION_PRESSURE",
)
INDEPENDENT_FAMILY_SET: Final[frozenset[str]] = frozenset(INDEPENDENT_FAMILIES)
EXCLUDED_REFERENCE_FAMILY: Final[str] = "RENYI2_REGIME_SWITCHED"
CONSTRUCTOR_IDS: Final[tuple[str, str, str]] = (
    "B649_CANDIDATE_SET_LOW_OVERLAP_V1",
    "B649_CANDIDATE_SET_EXPOSURE_BALANCED_V1",
    "B649_CANDIDATE_SET_HYBRID_DIVERSITY_V1",
)
CONSTRUCTOR_ORDER_FOR_AUTHORITY: Final[tuple[str, ...]] = tuple(sorted(CONSTRUCTOR_IDS))
TICKET_BUDGETS: Final[tuple[int, int, int]] = (5, 10, 20)
TICKET_COUNTS: Final[tuple[int, int, int]] = TICKET_BUDGETS

REDUNDANCY_LABELS: Final[frozenset[str]] = frozenset(
    {
        "EXACT_DUPLICATE",
        "HIGH_REDUNDANCY",
        "PARTIAL_REDUNDANCY",
        "COMPLEMENTARY_SIGNAL",
        "LOW_DEPENDENCE_INCONCLUSIVE",
    }
)
REDUNDANT_LABELS: Final[frozenset[str]] = frozenset(
    {"EXACT_DUPLICATE", "HIGH_REDUNDANCY"}
)
REFERENCE_WINDOW: Final[str] = "WINDOW_750"
DATA_CUTOFF: Final[int] = 115000073
REDUNDANCY_REFRESH_CADENCE: Final[str] = "STATIC_FROZEN_SNAPSHOT_FOR_V1"
WITHIN_COHORT_REFRESH_ALLOWED: Final[bool] = False
CLUSTER_TIE_BREAK: Final[str] = (
    "ASCENDING_LEXICOGRAPHIC_FAMILY_ID_RETAIN_FIRST_DROP_REST"
)
UNION_ORDER_RULE: Final[str] = (
    "RETAINED_FAMILY_ID_ASCENDING_THEN_NATIVE_PARENT_ORDER;"
    "EXACT_DUPLICATE_TUPLES_FIRST_OCCURRENCE_WINS"
)
TICKET_CARDINALITY_RULE: Final[str] = (
    "UNION_OF_RETAINED_NATIVE_TICKETS_AT_MATCHED_BUDGET;"
    "EXACT_DUPLICATE_TUPLES_DEDUPLICATED;COMPUTED_AT_CONSTRUCTION"
)

AUTHORITY_SNAPSHOT_ID: Final[str] = (
    "CROSS_FAMILY_REDUNDANCY_PRUNED_ENSEMBLE_V1_AUTHORITY_SNAPSHOT_1"
)
AUTHORITY_SCHEMA_VERSION: Final[str] = (
    "BIGLOTTO_CROSS_FAMILY_REDUNDANCY_PRUNED_ENSEMBLE_V1_AUTHORITY_SNAPSHOT_V1"
)
AUTHORITY_METHODOLOGY_VERSION: Final[str] = (
    "BIGLOTTO_CROSS_FAMILY_EMPIRICAL_COMPLEMENTARITY_MATRIX_R1"
)
CLASSIFICATION_ARTIFACT_SHA256: Final[str] = (
    "13a423c732bd9af580dfd6aafd1bd09ed0682361cdc3bd40d1f7ff51d8525363"
)
ANALYSIS_PROTOCOL_SHA256: Final[str] = (
    "e6a8e9a0a34238617cdd1e724a49937435907c961208bee1cca5f3af7af288e4"
)
MATRIX_RUN_MANIFEST_SHA256: Final[str] = (
    "451c91d6214e063afd7b82622885e0611e9c62ed03d1eeb3f44cab030ff9f8f8"
)
DESIGN_SEMANTICS_SHA256: Final[str] = (
    "a11f8c63e84a5f595172ac03edbc09f571e537c07e153c6bb1c3fbae9407abbf"
)
IMPLEMENTATION_HANDOFF_SHA256: Final[str] = (
    "308856b068ea70d13beffee340908615abde94e3ad7a0f0457fccd76495f3b89"
)
DESIGN_SHA256SUMS_SHA256: Final[str] = (
    "9c31d5044ac8db2a9cfa4468b5f6a3d29e1be8559460d825a09c13c19669cd24"
)

CONFIRMATORY_RESTRICTION: Final[str] = (
    "FORWARD_ONLY_UNLESS_INDEPENDENT_UNTOUCHED_HOLDOUT_PROVEN"
)
SAME_DATA_CONFIRMATORY_ELIGIBILITY: Final[str] = "NO"
HYPOTHESIS_DERIVED_FROM_PRIOR_EMPIRICAL_RESULTS: Final[str] = "YES"
DISCOVERY_HISTORY_ROLE: Final[str] = "DEVELOPMENT_ONLY"
DIRECT_2B_REGISTRATION_AUTHORIZED: Final[str] = "NO"

PARENT_SOURCE_UNIVERSE_IDS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "MULTISCALE_FREQUENCY": "B649_MULTISCALE_FREQUENCY_RANKED_POOL_V1",
        "CONDITIONAL_COOCCURRENCE": "B649_CONDITIONAL_COOCCURRENCE_RANKED_POOL_V1",
        "GRAPH_NETWORK": "B649_MULTISCALE_GRAPH_PAGERANK_RANKED_POOL_V1",
        "MULTISCALE_OMISSION_PRESSURE": "B649_MULTISCALE_OMISSION_PRESSURE_RANKED_POOL_V1",
    }
)
PARENT_MINIMUM_HISTORY: Final[Mapping[str, int]] = MappingProxyType(
    {
        "MULTISCALE_FREQUENCY": 750,
        "CONDITIONAL_COOCCURRENCE": 751,
        "GRAPH_NETWORK": 750,
        "MULTISCALE_OMISSION_PRESSURE": 750,
    }
)
PARENT_VERSIONS: Final[Mapping[str, str]] = MappingProxyType(
    {family: "v1" for family in INDEPENDENT_FAMILIES}
)


class AuthorityError(ValueError):
    """Base class for fail-closed authority errors."""


class AuthorityUnavailableError(AuthorityError):
    """Raised when the required frozen authority is absent."""


class AuthorityMismatchError(AuthorityError):
    """Raised when an authority is stale, altered, incomplete, or mismatched."""


class RequiredParentUnavailableError(ValueError):
    """Raised when any required independent parent cannot be produced."""


class InsufficientHistoryError(ValueError):
    """Raised when the target index cannot supply the required prior prefix."""


def _json_ready(value: object) -> object:
    if isinstance(value, Mapping):
        mapping = cast(Mapping[object, object], value)
        result: dict[str, object] = {}
        for raw_key, item in mapping.items():
            if not isinstance(raw_key, str):
                raise TypeError("semantic records require string keys")
            result[raw_key] = _json_ready(item)
        return result
    if isinstance(value, tuple):
        items = cast(tuple[object, ...], value)
        return [_json_ready(item) for item in items]
    if isinstance(value, list):
        items = cast(list[object], value)
        return [_json_ready(item) for item in items]
    if isinstance(value, set | frozenset):
        items = cast(set[object] | frozenset[object], value)
        return [_json_ready(item) for item in sorted(items, key=repr)]
    return value


def canonicalize_semantic_record(record: Mapping[str, object]) -> bytes:
    """Return deterministic compact UTF-8 JSON for an identity record."""

    return json.dumps(
        _json_ready(record),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _field(mapping: Mapping[str, object], name: str) -> object:
    if name in mapping:
        return mapping[name]
    lower_name = name.lower()
    if lower_name in mapping:
        return mapping[lower_name]
    raise AuthorityMismatchError(f"authority is missing required field {name}")


def _as_string(mapping: Mapping[str, object], name: str) -> str:
    value = _field(mapping, name)
    if not isinstance(value, str) or not value:
        raise AuthorityMismatchError(f"authority field {name} must be a non-empty string")
    return value


def _as_string_tuple(mapping: Mapping[str, object], name: str) -> tuple[str, ...]:
    value = _field(mapping, name)
    if not isinstance(value, Sequence) or isinstance(value, str):
        raise AuthorityMismatchError(f"authority field {name} must be a string array")
    values = tuple(cast(Sequence[object], value))
    if not all(isinstance(item, str) and item for item in values):
        raise AuthorityMismatchError(f"authority field {name} contains a non-string")
    return tuple(cast(str, item) for item in values)


def _as_bool(mapping: Mapping[str, object], name: str) -> bool:
    value = _field(mapping, name)
    if type(value) is not bool:
        raise AuthorityMismatchError(f"authority field {name} must be boolean")
    return value


def _as_int(mapping: Mapping[str, object], name: str) -> int:
    value = _field(mapping, name)
    if type(value) is not int:
        raise AuthorityMismatchError(f"authority field {name} must be an integer")
    return value


def _parse_bool(value: object) -> bool:
    if type(value) is bool:
        return value
    if isinstance(value, str) and value.lower() in {"true", "false"}:
        return value.lower() == "true"
    raise AuthorityMismatchError("classification is_renyi2_pair must be boolean")


def _normalize_classification_cell(raw_cell: object) -> dict[str, object]:
    if not isinstance(raw_cell, Mapping):
        raise AuthorityMismatchError("classification cell must be an object")
    cell = cast(Mapping[str, object], raw_cell)
    family_a = _as_string(cell, "FAMILY_A")
    family_b = _as_string(cell, "FAMILY_B")
    pair = tuple(sorted((family_a, family_b)))
    if pair[0] == pair[1] or not set(pair) <= INDEPENDENT_FAMILY_SET:
        raise AuthorityMismatchError(f"classification pair is not independent: {pair}")
    constructor = _as_string(cell, "CONSTRUCTOR")
    if constructor not in CONSTRUCTOR_IDS:
        raise AuthorityMismatchError(f"unsupported constructor in authority: {constructor}")
    budget = _as_int(cell, "BUDGET")
    if budget not in TICKET_BUDGETS:
        raise AuthorityMismatchError(f"unsupported budget in authority: {budget}")
    horizon = _as_string(cell, "HORIZON")
    if horizon != REFERENCE_WINDOW:
        raise AuthorityMismatchError(f"authority contains non-frozen horizon: {horizon}")
    is_renyi2_pair = _parse_bool(_field(cell, "IS_RENYI2_PAIR"))
    if is_renyi2_pair:
        raise AuthorityMismatchError("Rényi2 pair cannot be part of the independent V1 authority")
    classification = _as_string(cell, "CLASSIFICATION")
    if classification not in REDUNDANCY_LABELS:
        raise AuthorityMismatchError(f"unknown redundancy classification: {classification}")
    return {
        "FAMILY_A": pair[0],
        "FAMILY_B": pair[1],
        "CONSTRUCTOR": constructor,
        "BUDGET": budget,
        "HORIZON": horizon,
        "IS_RENYI2_PAIR": False,
        "CLASSIFICATION": classification,
    }


def _classification_key(cell: Mapping[str, object]) -> tuple[str, str, str, int]:
    return (
        cast(str, cell["FAMILY_A"]),
        cast(str, cell["FAMILY_B"]),
        cast(str, cell["CONSTRUCTOR"]),
        cast(int, cell["BUDGET"]),
    )


def _expected_classification_keys() -> frozenset[tuple[str, str, str, int]]:
    return frozenset(
        (
            pair[0],
            pair[1],
            constructor,
            budget,
        )
        for pair in combinations(sorted(INDEPENDENT_FAMILIES), 2)
        for constructor in CONSTRUCTOR_ORDER_FOR_AUTHORITY
        for budget in TICKET_BUDGETS
    )


def _derive_membership(
    cells: Sequence[Mapping[str, object]],
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[Mapping[str, object], ...]]:
    labels_by_pair: dict[tuple[str, str], list[str]] = {}
    for cell in cells:
        pair = (cast(str, cell["FAMILY_A"]), cast(str, cell["FAMILY_B"]))
        labels_by_pair.setdefault(pair, []).append(cast(str, cell["CLASSIFICATION"]))

    parent = {family: family for family in INDEPENDENT_FAMILIES}

    def find(family: str) -> str:
        root = family
        while parent[root] != root:
            root = parent[root]
        while parent[family] != family:
            next_family = parent[family]
            parent[family] = root
            family = next_family
        return root

    def union(left: str, right: str) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parent[max(left_root, right_root)] = min(left_root, right_root)

    for pair in sorted(labels_by_pair):
        labels = labels_by_pair[pair]
        if labels and all(label in REDUNDANT_LABELS for label in labels):
            union(pair[0], pair[1])

    clusters_by_root: dict[str, list[str]] = {}
    for family in INDEPENDENT_FAMILIES:
        clusters_by_root.setdefault(find(family), []).append(family)

    clusters: list[Mapping[str, object]] = []
    pruned: set[str] = set()
    for members in sorted(
        (sorted(values) for values in clusters_by_root.values() if len(values) > 1),
        key=lambda values: values[0],
    ):
        retained = members[0]
        dropped = members[1:]
        pruned.update(dropped)
        clusters.append(
            {
                "FAMILIES": tuple(members),
                "RETAINED_FAMILY": retained,
                "DROPPED_FAMILIES": tuple(dropped),
                "TIE_BREAK": CLUSTER_TIE_BREAK,
            }
        )

    retained_families = tuple(sorted(set(INDEPENDENT_FAMILIES) - pruned))
    return retained_families, tuple(sorted(pruned)), tuple(clusters)


def _authority_core(snapshot: Mapping[str, object]) -> dict[str, object]:
    raw_cells = _field(snapshot, "CLASSIFICATION_CELLS")
    if not isinstance(raw_cells, Sequence) or isinstance(raw_cells, str):
        raise AuthorityMismatchError("CLASSIFICATION_CELLS must be an array")
    normalized = tuple(
        _normalize_classification_cell(cell) for cell in cast(Sequence[object], raw_cells)
    )
    keys = tuple(_classification_key(cell) for cell in normalized)
    expected = _expected_classification_keys()
    if len(keys) != len(set(keys)):
        raise AuthorityMismatchError("authority contains duplicate classification cells")
    if frozenset(keys) != expected:
        missing = sorted(expected - frozenset(keys))
        extra = sorted(frozenset(keys) - expected)
        raise AuthorityMismatchError(
            f"authority classification coverage mismatch; missing={missing}; extra={extra}"
        )
    normalized = tuple(sorted(normalized, key=_classification_key))
    return {
        "SNAPSHOT_ID": _as_string(snapshot, "SNAPSHOT_ID"),
        "SCHEMA_VERSION": _as_string(snapshot, "SCHEMA_VERSION"),
        "METHODOLOGY_VERSION": _as_string(snapshot, "METHODOLOGY_VERSION"),
        "REFERENCE_WINDOW": _as_string(snapshot, "REFERENCE_WINDOW"),
        "DATA_CUTOFF": _as_int(snapshot, "DATA_CUTOFF"),
        "MINIMUM_HISTORY": _as_int(snapshot, "MINIMUM_HISTORY"),
        "CLASSIFICATION_ARTIFACT_SHA256": _as_string(
            snapshot, "CLASSIFICATION_ARTIFACT_SHA256"
        ),
        "ANALYSIS_PROTOCOL_SHA256": _as_string(snapshot, "ANALYSIS_PROTOCOL_SHA256"),
        "MATRIX_RUN_MANIFEST_SHA256": _as_string(snapshot, "MATRIX_RUN_MANIFEST_SHA256"),
        "DESIGN_SEMANTICS_SHA256": _as_string(snapshot, "DESIGN_SEMANTICS_SHA256"),
        "IMPLEMENTATION_HANDOFF_SHA256": _as_string(
            snapshot, "IMPLEMENTATION_HANDOFF_SHA256"
        ),
        "DESIGN_SHA256SUMS_SHA256": _as_string(snapshot, "DESIGN_SHA256SUMS_SHA256"),
        "INDEPENDENT_FAMILIES": tuple(sorted(_as_string_tuple(snapshot, "INDEPENDENT_FAMILIES"))),
        "EXCLUDED_REFERENCE_FAMILY": _as_string(snapshot, "EXCLUDED_REFERENCE_FAMILY"),
        "SUPPORTED_BUDGETS": tuple(sorted(_as_int_values(snapshot, "SUPPORTED_BUDGETS"))),
        "SUPPORTED_CONSTRUCTORS": tuple(
            sorted(_as_string_tuple(snapshot, "SUPPORTED_CONSTRUCTORS"))
        ),
        "REDUNDANCY_LABELS": tuple(
            sorted(_as_string_tuple(snapshot, "REDUNDANCY_LABELS"))
        ),
        "HIGH_REDUNDANCY_RULE": _as_string(snapshot, "HIGH_REDUNDANCY_RULE"),
        "EXACT_DUPLICATE_RULE": _as_string(snapshot, "EXACT_DUPLICATE_RULE"),
        "CLUSTER_TIE_BREAK": _as_string(snapshot, "CLUSTER_TIE_BREAK"),
        "REDUNDANCY_REFRESH_CADENCE": _as_string(
            snapshot, "REDUNDANCY_REFRESH_CADENCE"
        ),
        "WITHIN_COHORT_REFRESH_ALLOWED": _as_bool(
            snapshot, "WITHIN_COHORT_REFRESH_ALLOWED"
        ),
        "HYPOTHESIS_DERIVED_FROM_PRIOR_EMPIRICAL_RESULTS": _as_string(
            snapshot, "HYPOTHESIS_DERIVED_FROM_PRIOR_EMPIRICAL_RESULTS"
        ),
        "SAME_DATA_CONFIRMATORY_ELIGIBILITY": _as_string(
            snapshot, "SAME_DATA_CONFIRMATORY_ELIGIBILITY"
        ),
        "DISCOVERY_HISTORY_ROLE": _as_string(snapshot, "DISCOVERY_HISTORY_ROLE"),
        "CONFIRMATORY_RESTRICTION": _as_string(snapshot, "CONFIRMATORY_RESTRICTION"),
        "DIRECT_2B_REGISTRATION_AUTHORIZED": _as_string(
            snapshot, "DIRECT_2B_REGISTRATION_AUTHORIZED"
        ),
        "CLASSIFICATION_CELLS": normalized,
    }


def _as_int_values(mapping: Mapping[str, object], name: str) -> tuple[int, ...]:
    value = _field(mapping, name)
    if not isinstance(value, Sequence) or isinstance(value, str):
        raise AuthorityMismatchError(f"authority field {name} must be an integer array")
    values = tuple(cast(Sequence[object], value))
    if not all(type(item) is int for item in values):
        raise AuthorityMismatchError(f"authority field {name} contains a non-integer")
    return tuple(cast(int, item) for item in values)


def authority_semantic_sha256(snapshot: Mapping[str, object]) -> str:
    """Hash the normalized authority semantics, excluding descriptive metrics."""

    return _sha256_bytes(canonicalize_semantic_record(_authority_core(snapshot)))


def seal_authority_snapshot(snapshot: Mapping[str, object]) -> dict[str, object]:
    """Return a copy with the V1 semantic authority hash bound into it."""

    result = dict(snapshot)
    digest = authority_semantic_sha256(result)
    result["AUTHORITY_SHA256"] = digest
    result["SNAPSHOT_SHA256"] = digest
    return result


@dataclass(frozen=True, slots=True)
class AuthorityBinding:
    """The exact immutable authority tuple used by one candidate batch."""

    SNAPSHOT_ID: str
    SCHEMA_VERSION: str
    METHODOLOGY_VERSION: str
    SNAPSHOT_SHA256: str
    RETAINED_FAMILIES: tuple[str, ...]
    PRUNED_FAMILIES: tuple[str, ...]
    SNAPSHOT: Mapping[str, object]

    def assert_unchanged(self, snapshot: Mapping[str, object]) -> None:
        """Reject any within-cohort authority replacement or refresh."""

        current = bind_authority(snapshot)
        if current.SNAPSHOT_SHA256 != self.SNAPSHOT_SHA256:
            raise AuthorityMismatchError(
                "within-cohort authority refresh would alter V1 membership or semantics"
            )


def bind_authority(
    snapshot: object,
    *,
    expected_file_sha256: str | None = None,
) -> AuthorityBinding:
    """Validate and bind one complete V1 authority; fail closed on any mismatch."""

    if snapshot is None:
        raise AuthorityUnavailableError("required redundancy authority is missing")
    if isinstance(snapshot, str | Path):
        snapshot_path = Path(snapshot)
        if not snapshot_path.is_file():
            raise AuthorityUnavailableError(f"authority snapshot is unavailable: {snapshot_path}")
        actual_file_sha = _sha256_file(snapshot_path)
        if expected_file_sha256 is not None and actual_file_sha != expected_file_sha256:
            raise AuthorityMismatchError(
                "authority file SHA mismatch: "
                f"expected {expected_file_sha256}, got {actual_file_sha}"
            )
        try:
            loaded = json.loads(snapshot_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise AuthorityUnavailableError("authority snapshot cannot be read as JSON") from error
        if not isinstance(loaded, Mapping):
            raise AuthorityMismatchError("authority snapshot JSON must be an object")
        snapshot = cast(Mapping[str, object], loaded)
    if not isinstance(snapshot, Mapping):
        raise AuthorityMismatchError("authority snapshot must be an object or path")
    authority = cast(Mapping[str, object], snapshot)
    schema_version = _as_string(authority, "SCHEMA_VERSION")
    snapshot_id = _as_string(authority, "SNAPSHOT_ID")
    methodology = _as_string(authority, "METHODOLOGY_VERSION")
    if schema_version != AUTHORITY_SCHEMA_VERSION:
        raise AuthorityMismatchError(f"authority schema/version mismatch: {schema_version}")
    if snapshot_id != AUTHORITY_SNAPSHOT_ID:
        raise AuthorityMismatchError(f"authority snapshot id mismatch: {snapshot_id}")
    if methodology != AUTHORITY_METHODOLOGY_VERSION:
        raise AuthorityMismatchError(f"authority methodology mismatch: {methodology}")
    if _as_string(authority, "REFERENCE_WINDOW") != REFERENCE_WINDOW:
        raise AuthorityMismatchError("authority reference window is not WINDOW_750")
    if _as_int(authority, "DATA_CUTOFF") != DATA_CUTOFF:
        raise AuthorityMismatchError("authority data cutoff mismatch")
    if _as_int(authority, "MINIMUM_HISTORY") != MINIMUM_HISTORY:
        raise AuthorityMismatchError("authority minimum-history mismatch")
    expected_sha_fields = {
        "CLASSIFICATION_ARTIFACT_SHA256": CLASSIFICATION_ARTIFACT_SHA256,
        "ANALYSIS_PROTOCOL_SHA256": ANALYSIS_PROTOCOL_SHA256,
        "MATRIX_RUN_MANIFEST_SHA256": MATRIX_RUN_MANIFEST_SHA256,
        "DESIGN_SEMANTICS_SHA256": DESIGN_SEMANTICS_SHA256,
        "IMPLEMENTATION_HANDOFF_SHA256": IMPLEMENTATION_HANDOFF_SHA256,
        "DESIGN_SHA256SUMS_SHA256": DESIGN_SHA256SUMS_SHA256,
    }
    for field_name, expected_value in expected_sha_fields.items():
        if _as_string(authority, field_name) != expected_value:
            raise AuthorityMismatchError(f"authority {field_name} mismatch")
    if tuple(sorted(_as_string_tuple(authority, "INDEPENDENT_FAMILIES"))) != tuple(
        sorted(INDEPENDENT_FAMILIES)
    ):
        raise AuthorityMismatchError("independent-family universe mismatch")
    if _as_string(authority, "EXCLUDED_REFERENCE_FAMILY") != EXCLUDED_REFERENCE_FAMILY:
        raise AuthorityMismatchError("excluded Rényi2 reference-family rule mismatch")
    if tuple(sorted(_as_int_values(authority, "SUPPORTED_BUDGETS"))) != TICKET_BUDGETS:
        raise AuthorityMismatchError("supported budget set mismatch")
    if tuple(sorted(_as_string_tuple(authority, "SUPPORTED_CONSTRUCTORS"))) != tuple(
        sorted(CONSTRUCTOR_IDS)
    ):
        raise AuthorityMismatchError("supported constructor set mismatch")
    if tuple(sorted(_as_string_tuple(authority, "REDUNDANCY_LABELS"))) != tuple(
        sorted(REDUNDANCY_LABELS)
    ):
        raise AuthorityMismatchError("redundancy-label vocabulary mismatch")
    if _as_string(authority, "HIGH_REDUNDANCY_RULE") != (
        "HIT_AGREEMENT_RATE >= 0.85 AND HIT_CORRELATION >= 0.6"
    ):
        raise AuthorityMismatchError("HIGH_REDUNDANCY threshold mismatch")
    if _as_string(authority, "EXACT_DUPLICATE_RULE") != (
        "HIT_AGREEMENT_RATE == 1.0 AND mean_portfolio_jaccard >= 0.98"
    ):
        raise AuthorityMismatchError("EXACT_DUPLICATE threshold mismatch")
    if _as_string(authority, "REDUNDANCY_REFRESH_CADENCE") != REDUNDANCY_REFRESH_CADENCE:
        raise AuthorityMismatchError("V1 redundancy refresh cadence mismatch")
    if _as_bool(authority, "WITHIN_COHORT_REFRESH_ALLOWED") is not False:
        raise AuthorityMismatchError("within-cohort refresh must be forbidden")
    if _as_string(authority, "CLUSTER_TIE_BREAK") != CLUSTER_TIE_BREAK:
        raise AuthorityMismatchError("cluster tie-break mismatch")
    expected_boundary_fields = {
        "HYPOTHESIS_DERIVED_FROM_PRIOR_EMPIRICAL_RESULTS": (
            HYPOTHESIS_DERIVED_FROM_PRIOR_EMPIRICAL_RESULTS
        ),
        "SAME_DATA_CONFIRMATORY_ELIGIBILITY": SAME_DATA_CONFIRMATORY_ELIGIBILITY,
        "DISCOVERY_HISTORY_ROLE": DISCOVERY_HISTORY_ROLE,
        "CONFIRMATORY_RESTRICTION": CONFIRMATORY_RESTRICTION,
        "DIRECT_2B_REGISTRATION_AUTHORIZED": DIRECT_2B_REGISTRATION_AUTHORIZED,
    }
    for field_name, expected_value in expected_boundary_fields.items():
        if _as_string(authority, field_name) != expected_value:
            raise AuthorityMismatchError(f"authority contamination boundary mismatch: {field_name}")
    core = _authority_core(authority)
    digest = _sha256_bytes(canonicalize_semantic_record(core))
    declared_hash = _as_string(authority, "AUTHORITY_SHA256")
    declared_snapshot_hash = _as_string(authority, "SNAPSHOT_SHA256")
    if declared_hash != digest or declared_snapshot_hash != digest:
        raise AuthorityMismatchError("authority semantic SHA mismatch")
    cells = cast(tuple[Mapping[str, object], ...], core["CLASSIFICATION_CELLS"])
    retained, pruned, clusters = _derive_membership(cells)
    declared_retained = tuple(sorted(_as_string_tuple(authority, "RETAINED_FAMILIES")))
    declared_pruned = tuple(sorted(_as_string_tuple(authority, "PRUNED_FAMILIES")))
    if (declared_retained, declared_pruned) != (retained, pruned):
        raise AuthorityMismatchError(
            f"authority membership mismatch: declared retained={declared_retained}, "
            f"derived retained={retained}, declared pruned={declared_pruned}, "
            f"derived pruned={pruned}"
        )
    declared_clusters = _json_ready(_field(authority, "PRUNED_CLUSTERS"))
    if declared_clusters != _json_ready(clusters):
        raise AuthorityMismatchError("authority redundancy-cluster membership mismatch")
    if not retained:
        raise AuthorityMismatchError("authority cannot prune every independent family")
    return AuthorityBinding(
        SNAPSHOT_ID=snapshot_id,
        SCHEMA_VERSION=schema_version,
        METHODOLOGY_VERSION=methodology,
        SNAPSHOT_SHA256=digest,
        RETAINED_FAMILIES=retained,
        PRUNED_FAMILIES=pruned,
        SNAPSHOT=MappingProxyType(dict(authority)),
    )


def assert_authority_unchanged(
    binding: AuthorityBinding, snapshot: Mapping[str, object]
) -> None:
    """Public helper for the V1 no-refresh cohort guard."""

    binding.assert_unchanged(snapshot)


def _default_classification_cells() -> tuple[dict[str, object], ...]:
    cells: list[dict[str, object]] = []
    redundant_pair = tuple(sorted(("GRAPH_NETWORK", "MULTISCALE_FREQUENCY")))
    for pair in combinations(sorted(INDEPENDENT_FAMILIES), 2):
        classification = "HIGH_REDUNDANCY" if pair == redundant_pair else "PARTIAL_REDUNDANCY"
        for constructor in CONSTRUCTOR_ORDER_FOR_AUTHORITY:
            for budget in TICKET_BUDGETS:
                cells.append(
                    {
                        "FAMILY_A": pair[0],
                        "FAMILY_B": pair[1],
                        "CONSTRUCTOR": constructor,
                        "BUDGET": budget,
                        "HORIZON": REFERENCE_WINDOW,
                        "IS_RENYI2_PAIR": False,
                        "CLASSIFICATION": classification,
                    }
                )
    return tuple(cells)


def _base_authority_snapshot() -> dict[str, object]:
    return {
        "SNAPSHOT_ID": AUTHORITY_SNAPSHOT_ID,
        "SCHEMA_VERSION": AUTHORITY_SCHEMA_VERSION,
        "METHODOLOGY_VERSION": AUTHORITY_METHODOLOGY_VERSION,
        "REFERENCE_WINDOW": REFERENCE_WINDOW,
        "DATA_CUTOFF": DATA_CUTOFF,
        "MINIMUM_HISTORY": MINIMUM_HISTORY,
        "CLASSIFICATION_ARTIFACT_SHA256": CLASSIFICATION_ARTIFACT_SHA256,
        "ANALYSIS_PROTOCOL_SHA256": ANALYSIS_PROTOCOL_SHA256,
        "MATRIX_RUN_MANIFEST_SHA256": MATRIX_RUN_MANIFEST_SHA256,
        "DESIGN_SEMANTICS_SHA256": DESIGN_SEMANTICS_SHA256,
        "IMPLEMENTATION_HANDOFF_SHA256": IMPLEMENTATION_HANDOFF_SHA256,
        "DESIGN_SHA256SUMS_SHA256": DESIGN_SHA256SUMS_SHA256,
        "INDEPENDENT_FAMILIES": list(INDEPENDENT_FAMILIES),
        "EXCLUDED_REFERENCE_FAMILY": EXCLUDED_REFERENCE_FAMILY,
        "SUPPORTED_BUDGETS": list(TICKET_BUDGETS),
        "SUPPORTED_CONSTRUCTORS": list(CONSTRUCTOR_IDS),
        "REDUNDANCY_LABELS": sorted(REDUNDANCY_LABELS),
        "HIGH_REDUNDANCY_RULE": (
            "HIT_AGREEMENT_RATE >= 0.85 AND HIT_CORRELATION >= 0.6"
        ),
        "EXACT_DUPLICATE_RULE": (
            "HIT_AGREEMENT_RATE == 1.0 AND mean_portfolio_jaccard >= 0.98"
        ),
        "CLUSTER_TIE_BREAK": CLUSTER_TIE_BREAK,
        "REDUNDANCY_REFRESH_CADENCE": REDUNDANCY_REFRESH_CADENCE,
        "WITHIN_COHORT_REFRESH_ALLOWED": WITHIN_COHORT_REFRESH_ALLOWED,
        "CLASSIFICATION_CELLS": list(_default_classification_cells()),
        "RETAINED_FAMILIES": [
            "CONDITIONAL_COOCCURRENCE",
            "GRAPH_NETWORK",
            "MULTISCALE_OMISSION_PRESSURE",
        ],
        "PRUNED_FAMILIES": ["MULTISCALE_FREQUENCY"],
        "PRUNED_CLUSTERS": [
            {
                "FAMILIES": ["GRAPH_NETWORK", "MULTISCALE_FREQUENCY"],
                "RETAINED_FAMILY": "GRAPH_NETWORK",
                "DROPPED_FAMILIES": ["MULTISCALE_FREQUENCY"],
                "TIE_BREAK": CLUSTER_TIE_BREAK,
            }
        ],
        "HYPOTHESIS_DERIVED_FROM_PRIOR_EMPIRICAL_RESULTS": (
            HYPOTHESIS_DERIVED_FROM_PRIOR_EMPIRICAL_RESULTS
        ),
        "SAME_DATA_CONFIRMATORY_ELIGIBILITY": SAME_DATA_CONFIRMATORY_ELIGIBILITY,
        "DISCOVERY_HISTORY_ROLE": DISCOVERY_HISTORY_ROLE,
        "CONFIRMATORY_RESTRICTION": CONFIRMATORY_RESTRICTION,
        "DIRECT_2B_REGISTRATION_AUTHORIZED": DIRECT_2B_REGISTRATION_AUTHORIZED,
    }


DEFAULT_AUTHORITY_SNAPSHOT: Final[Mapping[str, object]] = MappingProxyType(
    seal_authority_snapshot(_base_authority_snapshot())
)
DEFAULT_AUTHORITY_BINDING: Final[AuthorityBinding] = bind_authority(DEFAULT_AUTHORITY_SNAPSHOT)


def _classification_row_from_csv(raw_row: Mapping[str, str]) -> dict[str, object]:
    row: dict[str, object] = {key.upper(): value for key, value in raw_row.items()}
    row["BUDGET"] = int(cast(str, row["BUDGET"]))
    row["IS_RENYI2_PAIR"] = _parse_bool(row["IS_RENYI2_PAIR"])
    return row


def build_authority_snapshot_from_classification_rows(
    rows: Iterable[Mapping[str, object]],
    *,
    classification_artifact_sha256: str = CLASSIFICATION_ARTIFACT_SHA256,
    analysis_protocol_sha256: str = ANALYSIS_PROTOCOL_SHA256,
    matrix_run_manifest_sha256: str = MATRIX_RUN_MANIFEST_SHA256,
) -> dict[str, object]:
    """Freeze an existing classification artifact without recomputing labels."""

    selected: list[dict[str, object]] = []
    for raw_row in rows:
        row = {str(key).upper(): value for key, value in raw_row.items()}
        if row.get("HORIZON") != REFERENCE_WINDOW:
            continue
        if _parse_bool(row.get("IS_RENYI2_PAIR", False)):
            continue
        family_a = row.get("FAMILY_A")
        family_b = row.get("FAMILY_B")
        if family_a not in INDEPENDENT_FAMILY_SET or family_b not in INDEPENDENT_FAMILY_SET:
            continue
        selected.append(row)
    base = _base_authority_snapshot()
    base["CLASSIFICATION_ARTIFACT_SHA256"] = classification_artifact_sha256
    base["ANALYSIS_PROTOCOL_SHA256"] = analysis_protocol_sha256
    base["MATRIX_RUN_MANIFEST_SHA256"] = matrix_run_manifest_sha256
    base["CLASSIFICATION_CELLS"] = sorted(
        selected,
        key=lambda row: _classification_key(_normalize_classification_cell(row)),
    )
    cells = cast(Sequence[Mapping[str, object]], base["CLASSIFICATION_CELLS"])
    retained, pruned, clusters = _derive_membership(
        tuple(_normalize_classification_cell(cell) for cell in cells)
    )
    base["RETAINED_FAMILIES"] = list(retained)
    base["PRUNED_FAMILIES"] = list(pruned)
    base["PRUNED_CLUSTERS"] = [_json_ready(cluster) for cluster in clusters]
    return seal_authority_snapshot(base)


def load_classification_csv(path: str | Path) -> tuple[dict[str, object], ...]:
    """Read only the named classification CSV for authority freezing."""

    csv_path = Path(path)
    if not csv_path.is_file():
        raise AuthorityUnavailableError(f"classification artifact is unavailable: {csv_path}")
    try:
        with csv_path.open(newline="", encoding="utf-8") as handle:
            return tuple(_classification_row_from_csv(row) for row in csv.DictReader(handle))
    except (OSError, csv.Error, KeyError, ValueError) as error:
        raise AuthorityUnavailableError("classification artifact cannot be read") from error


@dataclass(frozen=True, slots=True)
class CandidateIdentity:
    CANDIDATE_ID: str
    SIGNATURE_HASH: str
    CANONICAL_SEMANTIC_JSON: str


@dataclass(frozen=True, slots=True)
class CandidateMetadata:
    CANDIDATE_ID: str
    SIGNATURE_HASH: str
    SEMANTICS: Mapping[str, object]
    CONSTRUCTOR_ID: str
    TICKET_BUDGET: int
    IMPLEMENTATION_SYMBOL: str


def derive_candidate_identity(record: Mapping[str, object]) -> CandidateIdentity:
    canonical = canonicalize_semantic_record(record)
    signature_hash = _sha256_bytes(canonical)
    return CandidateIdentity(
        CANDIDATE_ID=f"BMSGV1_XF_{signature_hash[:16]}",
        SIGNATURE_HASH=signature_hash,
        CANONICAL_SEMANTIC_JSON=canonical.decode("utf-8"),
    )


def signature_hash_for_semantics(record: Mapping[str, object]) -> str:
    return derive_candidate_identity(record).SIGNATURE_HASH


def candidate_id_for_semantics(record: Mapping[str, object]) -> str:
    return derive_candidate_identity(record).CANDIDATE_ID


_CONSTRUCTOR_SYMBOL_SLUGS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "B649_CANDIDATE_SET_LOW_OVERLAP_V1": "low_overlap",
        "B649_CANDIDATE_SET_EXPOSURE_BALANCED_V1": "exposure_balanced",
        "B649_CANDIDATE_SET_HYBRID_DIVERSITY_V1": "hybrid_diversity",
    }
)


def _implementation_symbol(constructor_id: str, ticket_budget: int) -> str:
    return (
        "produce_b649_cross_family_redundancy_pruned_ensemble_v1_"
        f"{_CONSTRUCTOR_SYMBOL_SLUGS[constructor_id]}_k{ticket_budget}"
    )


def _candidate_semantics(
    binding: AuthorityBinding, constructor_id: str, ticket_budget: int
) -> dict[str, object]:
    return {
        "HYPOTHESIS_VERSION": HYPOTHESIS_VERSION,
        "HYPOTHESIS_ID": HYPOTHESIS_ID,
        "NEW_FAMILY_ID": NEW_FAMILY_ID,
        "METHOD_FAMILY": METHOD_FAMILY,
        "FAMILY_VERSION": "V1",
        "LOTTERY_TYPE": LOTTERY_TYPE,
        "CONSTRUCTOR_ID": constructor_id,
        "CONSTRUCTOR_VERSION": "v1",
        "REQUESTED_BUDGET": ticket_budget,
        "TICKET_CARDINALITY_RULE": TICKET_CARDINALITY_RULE,
        "UNION_ORDER_RULE": UNION_ORDER_RULE,
        "OUTPUT_SHAPE": OUTPUT_SHAPE,
        "PARENT_MEMBERSHIP": binding.RETAINED_FAMILIES,
        "ALL_REQUIRED_PARENT_FAMILIES": tuple(sorted(INDEPENDENT_FAMILIES)),
        "PRUNED_PARENT_FAMILIES": binding.PRUNED_FAMILIES,
        "EXCLUDED_REFERENCE_FAMILY": EXCLUDED_REFERENCE_FAMILY,
        "AUTHORITY_SNAPSHOT_ID": binding.SNAPSHOT_ID,
        "AUTHORITY_SCHEMA_VERSION": binding.SCHEMA_VERSION,
        "AUTHORITY_METHODOLOGY_VERSION": binding.METHODOLOGY_VERSION,
        "AUTHORITY_SHA256": binding.SNAPSHOT_SHA256,
        "REDUNDANCY_REFRESH_CADENCE": REDUNDANCY_REFRESH_CADENCE,
        "WITHIN_COHORT_REFRESH_ALLOWED": WITHIN_COHORT_REFRESH_ALLOWED,
        "MINIMUM_HISTORY": MINIMUM_HISTORY,
        "CAUSAL_CUTOFF_RULE": CAUSAL_CUTOFF_RULE,
        "PARAMETER_SELECTION_RULE": PARAMETER_SELECTION_RULE,
        "DETERMINISM_CLASS": DETERMINISM_CLASS,
        "RNG_SEMANTICS": RNG_SEMANTICS,
        "HYPOTHESIS_DERIVED_FROM_PRIOR_EMPIRICAL_RESULTS": (
            HYPOTHESIS_DERIVED_FROM_PRIOR_EMPIRICAL_RESULTS
        ),
        "SAME_DATA_CONFIRMATORY_ELIGIBILITY": SAME_DATA_CONFIRMATORY_ELIGIBILITY,
        "DISCOVERY_HISTORY_ROLE": DISCOVERY_HISTORY_ROLE,
        "CONFIRMATORY_RESTRICTION": CONFIRMATORY_RESTRICTION,
        "DIRECT_2B_REGISTRATION_AUTHORIZED": DIRECT_2B_REGISTRATION_AUTHORIZED,
    }


def build_candidate_authorities(
    binding: AuthorityBinding = DEFAULT_AUTHORITY_BINDING,
) -> tuple[CandidateMetadata, ...]:
    """Build the exact 3-constructor by 3-budget identity matrix."""

    authorities: list[CandidateMetadata] = []
    seen_ids: set[str] = set()
    seen_hashes: set[str] = set()
    for constructor_id in CONSTRUCTOR_IDS:
        for ticket_budget in TICKET_BUDGETS:
            semantics = _candidate_semantics(binding, constructor_id, ticket_budget)
            identity = derive_candidate_identity(semantics)
            if identity.CANDIDATE_ID in seen_ids or identity.SIGNATURE_HASH in seen_hashes:
                raise RuntimeError("candidate identity collision")
            seen_ids.add(identity.CANDIDATE_ID)
            seen_hashes.add(identity.SIGNATURE_HASH)
            authorities.append(
                CandidateMetadata(
                    CANDIDATE_ID=identity.CANDIDATE_ID,
                    SIGNATURE_HASH=identity.SIGNATURE_HASH,
                    SEMANTICS=MappingProxyType(semantics),
                    CONSTRUCTOR_ID=constructor_id,
                    TICKET_BUDGET=ticket_budget,
                    IMPLEMENTATION_SYMBOL=_implementation_symbol(constructor_id, ticket_budget),
                )
            )
    if len(authorities) != 9:
        raise RuntimeError("candidate authority matrix must be exactly 3 by 3")
    return tuple(authorities)


CANDIDATE_AUTHORITIES: Final[tuple[CandidateMetadata, ...]] = build_candidate_authorities()
CANDIDATE_METADATA: Final[Mapping[str, CandidateMetadata]] = MappingProxyType(
    {metadata.CANDIDATE_ID: metadata for metadata in CANDIDATE_AUTHORITIES}
)
CANDIDATE_IDS: Final[tuple[str, ...]] = tuple(
    metadata.CANDIDATE_ID for metadata in CANDIDATE_AUTHORITIES
)
CANDIDATE_SIGNATURE_HASHES: Final[tuple[str, ...]] = tuple(
    metadata.SIGNATURE_HASH for metadata in CANDIDATE_AUTHORITIES
)
CANDIDATE_IDS_BY_CONSTRUCTOR_AND_BUDGET: Final[Mapping[tuple[str, int], str]] = MappingProxyType(
    {
        (metadata.CONSTRUCTOR_ID, metadata.TICKET_BUDGET): metadata.CANDIDATE_ID
        for metadata in CANDIDATE_AUTHORITIES
    }
)


def candidate_id_for(constructor_id: str, ticket_budget: int) -> str:
    try:
        return CANDIDATE_IDS_BY_CONSTRUCTOR_AND_BUDGET[(constructor_id, ticket_budget)]
    except KeyError as error:
        raise KeyError(
            f"unsupported constructor/budget pair: {constructor_id!r}, {ticket_budget!r}"
        ) from error


def prune_families(
    authority_snapshot: Mapping[str, object] = DEFAULT_AUTHORITY_SNAPSHOT,
) -> tuple[str, ...]:
    """Return the authority-bound retained family order."""

    return bind_authority(authority_snapshot).RETAINED_FAMILIES


def _read_prior_prefix(history: HistoryInput, target_index: int) -> tuple[object, ...]:
    if type(target_index) is not int or target_index < MINIMUM_HISTORY:
        raise InsufficientHistoryError(
            f"target_index must provide at least {MINIMUM_HISTORY} strictly prior draws"
        )
    try:
        if isinstance(history, Sequence):
            if target_index > len(history):
                raise ValueError("target_index must not exceed history length")
            return tuple(history[:target_index])
        prefix = tuple(islice(iter(history), target_index))
        if len(prefix) != target_index:
            raise ValueError("target_index must not exceed history length")
        return prefix
    except InsufficientHistoryError:
        raise
    except (TypeError, IndexError, ValueError) as error:
        raise ValueError("history must supply a finite chronological prefix") from error


def _validate_ticket(raw_ticket: object, location: str) -> Ticket:
    if not isinstance(raw_ticket, tuple):
        raise ValueError(f"{location} must be an immutable tuple of six integers")
    values = cast(tuple[object, ...], raw_ticket)
    if len(values) != PICK_COUNT:
        raise ValueError(f"{location} must contain exactly {PICK_COUNT} numbers")
    if not all(type(number) is int for number in values):
        raise ValueError(f"{location} must contain only integers")
    numbers = cast(tuple[int, ...], values)
    if any(number < NUMBER_DOMAIN[0] or number > NUMBER_DOMAIN[1] for number in numbers):
        raise ValueError(f"{location} contains a number outside 1..49")
    if any(left >= right for left, right in pairwise(numbers)):
        raise ValueError(f"{location} must be strictly ascending with no duplicates")
    return cast(Ticket, numbers)


def _validate_parent_portfolio(
    raw_portfolio: object, family: str, ticket_budget: int
) -> TicketPortfolio:
    if isinstance(raw_portfolio, (Mapping, str)):
        raise ValueError(f"parent {family} did not emit a ticket portfolio")
    try:
        raw_tickets = tuple(cast(Iterable[object], raw_portfolio))
    except TypeError as error:
        raise ValueError(f"parent {family} did not emit a ticket portfolio") from error
    if len(raw_tickets) != ticket_budget:
        raise ValueError(
            f"parent {family} must emit exactly budget={ticket_budget} tickets; "
            f"received {len(raw_tickets)}"
        )
    tickets = tuple(
        _validate_ticket(raw_ticket, f"parent {family}[{index}]")
        for index, raw_ticket in enumerate(raw_tickets)
    )
    if len(set(tickets)) != len(tickets):
        raise ValueError(f"parent {family} emitted duplicate tickets")
    return tickets


def _mapping_lookup(
    value: Mapping[object, object], constructor_id: str, ticket_budget: int
) -> object:
    candidate_keys: tuple[object, ...] = (
        (constructor_id, ticket_budget),
        f"{constructor_id}:{ticket_budget}",
        ticket_budget,
        str(ticket_budget),
        "TICKETS",
    )
    for key in candidate_keys:
        if key in value:
            return value[key]
    raise RequiredParentUnavailableError(
        f"parent output lacks constructor={constructor_id}, budget={ticket_budget}"
    )


def _resolve_parent_value(
    raw_parent: object,
    family: str,
    constructor_id: str,
    ticket_budget: int,
) -> TicketPortfolio:
    value = raw_parent
    if isinstance(raw_parent, Mapping):
        value = _mapping_lookup(
            cast(Mapping[object, object], raw_parent), constructor_id, ticket_budget
        )
    return _validate_parent_portfolio(value, family, ticket_budget)


def _call_parent_provider(
    provider: ParentProvider,
    prior_history: tuple[object, ...],
    target_index: int,
    constructor_id: str,
    ticket_budget: int,
) -> object:
    try:
        signature = inspect.signature(provider)
    except (TypeError, ValueError):
        return provider(prior_history, target_index, constructor_id, ticket_budget)
    positional = [
        parameter
        for parameter in signature.parameters.values()
        if parameter.kind
        in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
    ]
    has_varargs = any(
        parameter.kind is inspect.Parameter.VAR_POSITIONAL
        for parameter in signature.parameters.values()
    )
    if has_varargs or len(positional) >= 4:
        return provider(prior_history, target_index, constructor_id, ticket_budget)
    if len(positional) == 3:
        return provider(prior_history, target_index, ticket_budget)
    if len(positional) == 2:
        return provider(prior_history, target_index)
    if len(positional) == 1:
        return provider(prior_history)
    return provider()


def _parent_portfolios_from_inputs(
    *,
    history: HistoryInput,
    target_index: int,
    constructor_id: str,
    ticket_budget: int,
    parent_producers: Mapping[str, object] | None,
    parent_portfolios: Mapping[str, object] | None,
) -> Mapping[str, TicketPortfolio]:
    if parent_producers is not None and parent_portfolios is not None:
        raise ValueError("provide parent_producers or parent_portfolios, not both")
    source = parent_producers if parent_producers is not None else parent_portfolios
    if source is None:
        raise RequiredParentUnavailableError(
            "required parent producers or parent portfolios are unavailable"
        )
    source_keys = frozenset(source)
    if source_keys != INDEPENDENT_FAMILY_SET:
        missing = sorted(INDEPENDENT_FAMILY_SET - source_keys)
        extra = sorted(source_keys - INDEPENDENT_FAMILY_SET)
        raise RequiredParentUnavailableError(
            f"required parent set mismatch; missing={missing}, extra={extra}"
        )
    prior_history = _read_prior_prefix(history, target_index)
    resolved: dict[str, TicketPortfolio] = {}
    for family in sorted(INDEPENDENT_FAMILIES):
        raw_parent = source[family]
        if parent_producers is not None:
            if not callable(raw_parent):
                raise RequiredParentUnavailableError(f"parent producer unavailable: {family}")
            raw_parent = _call_parent_provider(
                raw_parent,
                prior_history,
                target_index,
                constructor_id,
                ticket_budget,
            )
        resolved[family] = _resolve_parent_value(
            raw_parent, family, constructor_id, ticket_budget
        )
    return MappingProxyType(resolved)


def union_native_ticket_sets(
    parent_portfolios: Mapping[str, object],
    retained_families: Sequence[str],
    ticket_budget: int,
) -> TicketPortfolio:
    """Union retained native portfolios with deterministic first-occurrence order."""

    if ticket_budget not in TICKET_BUDGETS:
        raise ValueError(f"unsupported ticket budget: {ticket_budget}")
    retained = tuple(sorted(retained_families))
    if not retained or not set(retained) <= INDEPENDENT_FAMILY_SET:
        raise AuthorityMismatchError("retained family set is invalid")
    parent_keys = frozenset(parent_portfolios)
    if parent_keys != INDEPENDENT_FAMILY_SET:
        raise RequiredParentUnavailableError("all four independent parents are required")
    validated = {
        family: _validate_parent_portfolio(parent_portfolios[family], family, ticket_budget)
        for family in sorted(INDEPENDENT_FAMILIES)
    }
    seen: set[Ticket] = set()
    union: list[Ticket] = []
    for family in retained:
        for ticket in validated[family]:
            if ticket not in seen:
                seen.add(ticket)
                union.append(ticket)
    if not ticket_budget <= len(union) <= ticket_budget * len(retained):
        raise ValueError("union cardinality violates retained-family budget bounds")
    return tuple(union)


@dataclass(frozen=True, slots=True)
class CandidatePortfolio:
    TICKETS: TicketPortfolio
    REQUESTED_BUDGET: int
    TICKET_CARDINALITY: int
    RETAINED_FAMILIES: tuple[str, ...]
    PRUNED_FAMILIES: tuple[str, ...]
    AUTHORITY_SHA256: str


def build_candidate_portfolio(
    candidate_id: str,
    history: HistoryInput,
    target_index: int,
    parent_producers: Mapping[str, object] | None = None,
    *,
    parent_portfolios: Mapping[str, object] | None = None,
    authority_snapshot: object = DEFAULT_AUTHORITY_SNAPSHOT,
    authority_binding: AuthorityBinding | None = None,
) -> CandidatePortfolio:
    """Build one candidate using only the exact frozen authority and parents."""

    metadata = CANDIDATE_METADATA.get(candidate_id)
    if metadata is None:
        raise KeyError(f"unknown candidate_id: {candidate_id}")
    binding = authority_binding
    if binding is None:
        if authority_snapshot is None:
            raise AuthorityUnavailableError("required redundancy authority is missing")
        binding = bind_authority(authority_snapshot)
    elif authority_snapshot is not DEFAULT_AUTHORITY_SNAPSHOT:
        if not isinstance(authority_snapshot, Mapping):
            raise AuthorityMismatchError("authority replacement is not a snapshot object")
        binding.assert_unchanged(cast(Mapping[str, object], authority_snapshot))
    candidate_authority_sha = cast(str, metadata.SEMANTICS["AUTHORITY_SHA256"])
    if candidate_authority_sha != binding.SNAPSHOT_SHA256:
        raise AuthorityMismatchError("candidate semantics are bound to a different authority")
    parent_portfolio_map = _parent_portfolios_from_inputs(
        history=history,
        target_index=target_index,
        constructor_id=metadata.CONSTRUCTOR_ID,
        ticket_budget=metadata.TICKET_BUDGET,
        parent_producers=parent_producers,
        parent_portfolios=parent_portfolios,
    )
    tickets = union_native_ticket_sets(
        parent_portfolio_map,
        binding.RETAINED_FAMILIES,
        metadata.TICKET_BUDGET,
    )
    return CandidatePortfolio(
        TICKETS=tickets,
        REQUESTED_BUDGET=metadata.TICKET_BUDGET,
        TICKET_CARDINALITY=len(tickets),
        RETAINED_FAMILIES=binding.RETAINED_FAMILIES,
        PRUNED_FAMILIES=binding.PRUNED_FAMILIES,
        AUTHORITY_SHA256=binding.SNAPSHOT_SHA256,
    )


def produce_candidate_portfolio(
    candidate_id: str,
    history: HistoryInput,
    target_index: int,
    parent_producers: Mapping[str, object] | None = None,
    *,
    parent_portfolios: Mapping[str, object] | None = None,
    authority_snapshot: object = DEFAULT_AUTHORITY_SNAPSHOT,
    authority_binding: AuthorityBinding | None = None,
) -> TicketPortfolio:
    return build_candidate_portfolio(
        candidate_id,
        history,
        target_index,
        parent_producers,
        parent_portfolios=parent_portfolios,
        authority_snapshot=authority_snapshot,
        authority_binding=authority_binding,
    ).TICKETS


produce_biglotto_cross_family_redundancy_pruned_ensemble_candidate = produce_candidate_portfolio


def _named_producer(
    constructor_id: str,
    ticket_budget: int,
    history: HistoryInput,
    target_index: int,
    parent_producers: Mapping[str, object] | None,
    *,
    parent_portfolios: Mapping[str, object] | None,
    authority_snapshot: object,
    authority_binding: AuthorityBinding | None,
) -> TicketPortfolio:
    return produce_candidate_portfolio(
        candidate_id_for(constructor_id, ticket_budget),
        history,
        target_index,
        parent_producers,
        parent_portfolios=parent_portfolios,
        authority_snapshot=authority_snapshot,
        authority_binding=authority_binding,
    )


def produce_b649_cross_family_redundancy_pruned_ensemble_v1_low_overlap_k5(
    history: HistoryInput,
    target_index: int,
    parent_producers: Mapping[str, object] | None = None,
    *,
    parent_portfolios: Mapping[str, object] | None = None,
    authority_snapshot: object = DEFAULT_AUTHORITY_SNAPSHOT,
    authority_binding: AuthorityBinding | None = None,
) -> TicketPortfolio:
    return _named_producer(
        CONSTRUCTOR_IDS[0],
        5,
        history,
        target_index,
        parent_producers,
        parent_portfolios=parent_portfolios,
        authority_snapshot=authority_snapshot,
        authority_binding=authority_binding,
    )


def produce_b649_cross_family_redundancy_pruned_ensemble_v1_low_overlap_k10(
    history: HistoryInput,
    target_index: int,
    parent_producers: Mapping[str, object] | None = None,
    *,
    parent_portfolios: Mapping[str, object] | None = None,
    authority_snapshot: object = DEFAULT_AUTHORITY_SNAPSHOT,
    authority_binding: AuthorityBinding | None = None,
) -> TicketPortfolio:
    return _named_producer(
        CONSTRUCTOR_IDS[0],
        10,
        history,
        target_index,
        parent_producers,
        parent_portfolios=parent_portfolios,
        authority_snapshot=authority_snapshot,
        authority_binding=authority_binding,
    )


def produce_b649_cross_family_redundancy_pruned_ensemble_v1_low_overlap_k20(
    history: HistoryInput,
    target_index: int,
    parent_producers: Mapping[str, object] | None = None,
    *,
    parent_portfolios: Mapping[str, object] | None = None,
    authority_snapshot: object = DEFAULT_AUTHORITY_SNAPSHOT,
    authority_binding: AuthorityBinding | None = None,
) -> TicketPortfolio:
    return _named_producer(
        CONSTRUCTOR_IDS[0],
        20,
        history,
        target_index,
        parent_producers,
        parent_portfolios=parent_portfolios,
        authority_snapshot=authority_snapshot,
        authority_binding=authority_binding,
    )


def produce_b649_cross_family_redundancy_pruned_ensemble_v1_exposure_balanced_k5(
    history: HistoryInput,
    target_index: int,
    parent_producers: Mapping[str, object] | None = None,
    *,
    parent_portfolios: Mapping[str, object] | None = None,
    authority_snapshot: object = DEFAULT_AUTHORITY_SNAPSHOT,
    authority_binding: AuthorityBinding | None = None,
) -> TicketPortfolio:
    return _named_producer(
        CONSTRUCTOR_IDS[1],
        5,
        history,
        target_index,
        parent_producers,
        parent_portfolios=parent_portfolios,
        authority_snapshot=authority_snapshot,
        authority_binding=authority_binding,
    )


def produce_b649_cross_family_redundancy_pruned_ensemble_v1_exposure_balanced_k10(
    history: HistoryInput,
    target_index: int,
    parent_producers: Mapping[str, object] | None = None,
    *,
    parent_portfolios: Mapping[str, object] | None = None,
    authority_snapshot: object = DEFAULT_AUTHORITY_SNAPSHOT,
    authority_binding: AuthorityBinding | None = None,
) -> TicketPortfolio:
    return _named_producer(
        CONSTRUCTOR_IDS[1],
        10,
        history,
        target_index,
        parent_producers,
        parent_portfolios=parent_portfolios,
        authority_snapshot=authority_snapshot,
        authority_binding=authority_binding,
    )


def produce_b649_cross_family_redundancy_pruned_ensemble_v1_exposure_balanced_k20(
    history: HistoryInput,
    target_index: int,
    parent_producers: Mapping[str, object] | None = None,
    *,
    parent_portfolios: Mapping[str, object] | None = None,
    authority_snapshot: object = DEFAULT_AUTHORITY_SNAPSHOT,
    authority_binding: AuthorityBinding | None = None,
) -> TicketPortfolio:
    return _named_producer(
        CONSTRUCTOR_IDS[1],
        20,
        history,
        target_index,
        parent_producers,
        parent_portfolios=parent_portfolios,
        authority_snapshot=authority_snapshot,
        authority_binding=authority_binding,
    )


def produce_b649_cross_family_redundancy_pruned_ensemble_v1_hybrid_diversity_k5(
    history: HistoryInput,
    target_index: int,
    parent_producers: Mapping[str, object] | None = None,
    *,
    parent_portfolios: Mapping[str, object] | None = None,
    authority_snapshot: object = DEFAULT_AUTHORITY_SNAPSHOT,
    authority_binding: AuthorityBinding | None = None,
) -> TicketPortfolio:
    return _named_producer(
        CONSTRUCTOR_IDS[2],
        5,
        history,
        target_index,
        parent_producers,
        parent_portfolios=parent_portfolios,
        authority_snapshot=authority_snapshot,
        authority_binding=authority_binding,
    )


def produce_b649_cross_family_redundancy_pruned_ensemble_v1_hybrid_diversity_k10(
    history: HistoryInput,
    target_index: int,
    parent_producers: Mapping[str, object] | None = None,
    *,
    parent_portfolios: Mapping[str, object] | None = None,
    authority_snapshot: object = DEFAULT_AUTHORITY_SNAPSHOT,
    authority_binding: AuthorityBinding | None = None,
) -> TicketPortfolio:
    return _named_producer(
        CONSTRUCTOR_IDS[2],
        10,
        history,
        target_index,
        parent_producers,
        parent_portfolios=parent_portfolios,
        authority_snapshot=authority_snapshot,
        authority_binding=authority_binding,
    )


def produce_b649_cross_family_redundancy_pruned_ensemble_v1_hybrid_diversity_k20(
    history: HistoryInput,
    target_index: int,
    parent_producers: Mapping[str, object] | None = None,
    *,
    parent_portfolios: Mapping[str, object] | None = None,
    authority_snapshot: object = DEFAULT_AUTHORITY_SNAPSHOT,
    authority_binding: AuthorityBinding | None = None,
) -> TicketPortfolio:
    return _named_producer(
        CONSTRUCTOR_IDS[2],
        20,
        history,
        target_index,
        parent_producers,
        parent_portfolios=parent_portfolios,
        authority_snapshot=authority_snapshot,
        authority_binding=authority_binding,
    )


def _parent_membership_records(binding: AuthorityBinding) -> tuple[dict[str, object], ...]:
    return tuple(
        {
            "FAMILY_ID": family,
            "FAMILY_VERSION": PARENT_VERSIONS[family],
            "SOURCE_UNIVERSE_ID": PARENT_SOURCE_UNIVERSE_IDS[family],
            "MINIMUM_HISTORY": PARENT_MINIMUM_HISTORY[family],
            "REQUIRED": True,
            "RETAINED": family in binding.RETAINED_FAMILIES,
        }
        for family in sorted(INDEPENDENT_FAMILIES)
    )


def build_source_universe_contract(
    binding: AuthorityBinding = DEFAULT_AUTHORITY_BINDING,
    *,
    authority_file_sha256: str = "GENERATED_AFTER_AUTHORITY_FILE_WRITE",
) -> dict[str, object]:
    return {
        "SCHEMA_VERSION": (
            "BIGLOTTO_CROSS_FAMILY_REDUNDANCY_PRUNED_ENSEMBLE_V1_"
            "SOURCE_UNIVERSE_CONTRACT_V1"
        ),
        "LOTTERY_TYPE": LOTTERY_TYPE,
        "PICK_COUNT": PICK_COUNT,
        "NUMBER_DOMAIN": list(NUMBER_DOMAIN),
        "HISTORY_ORDER": HISTORY_ORDER,
        "MINIMUM_HISTORY": MINIMUM_HISTORY,
        "SOURCE_UNIVERSE_ID": NEW_FAMILY_ID,
        "SOURCE_UNIVERSE_VERSION": "v1",
        "METHOD_FAMILY": METHOD_FAMILY,
        "PARENT_MEMBERSHIP": list(_parent_membership_records(binding)),
        "RETAINED_FAMILIES": list(binding.RETAINED_FAMILIES),
        "PRUNED_FAMILIES": list(binding.PRUNED_FAMILIES),
        "EXCLUDED_REFERENCE_FAMILY": EXCLUDED_REFERENCE_FAMILY,
        "SUPPORTED_CONSTRUCTORS": list(CONSTRUCTOR_IDS),
        "SUPPORTED_BUDGETS": list(TICKET_BUDGETS),
        "TICKET_CARDINALITY_RULE": TICKET_CARDINALITY_RULE,
        "UNION_ORDER_RULE": UNION_ORDER_RULE,
        "CAUSAL_CUTOFF_RULE": CAUSAL_CUTOFF_RULE,
        "PARAMETER_SELECTION_RULE": PARAMETER_SELECTION_RULE,
        "DETERMINISM_CLASS": DETERMINISM_CLASS,
        "RNG_SEMANTICS": RNG_SEMANTICS,
        "REDUNDANCY_AUTHORITY": {
            "SNAPSHOT_ID": binding.SNAPSHOT_ID,
            "SCHEMA_VERSION": binding.SCHEMA_VERSION,
            "METHODOLOGY_VERSION": binding.METHODOLOGY_VERSION,
            "SEMANTIC_SHA256": binding.SNAPSHOT_SHA256,
            "FILE_SHA256": authority_file_sha256,
            "REFERENCE_WINDOW": REFERENCE_WINDOW,
            "DATA_CUTOFF": DATA_CUTOFF,
            "REFRESH_CADENCE": REDUNDANCY_REFRESH_CADENCE,
            "WITHIN_COHORT_REFRESH_ALLOWED": WITHIN_COHORT_REFRESH_ALLOWED,
        },
        "HYPOTHESIS_DERIVED_FROM_PRIOR_EMPIRICAL_RESULTS": (
            HYPOTHESIS_DERIVED_FROM_PRIOR_EMPIRICAL_RESULTS
        ),
        "SAME_DATA_CONFIRMATORY_ELIGIBILITY": SAME_DATA_CONFIRMATORY_ELIGIBILITY,
        "DISCOVERY_HISTORY_ROLE": DISCOVERY_HISTORY_ROLE,
        "CONFIRMATORY_RESTRICTION": CONFIRMATORY_RESTRICTION,
        "DIRECT_2B_REGISTRATION_AUTHORIZED": DIRECT_2B_REGISTRATION_AUTHORIZED,
    }


def _candidate_rows(
    binding: AuthorityBinding,
    *,
    authority_file_sha256: str,
    implementation_commit: str,
) -> tuple[dict[str, str], ...]:
    rows: list[dict[str, str]] = []
    for metadata in build_candidate_authorities(binding):
        semantics = metadata.SEMANTICS
        rows.append(
            {
                "CANDIDATE_ID": metadata.CANDIDATE_ID,
                "SIGNATURE_HASH": metadata.SIGNATURE_HASH,
                "HYPOTHESIS_VERSION": HYPOTHESIS_VERSION,
                "HYPOTHESIS_ID": HYPOTHESIS_ID,
                "NEW_FAMILY_ID": NEW_FAMILY_ID,
                "FAMILY_VERSION": "V1",
                "PARENT_MEMBERSHIP": ";".join(binding.RETAINED_FAMILIES),
                "ALL_REQUIRED_PARENT_FAMILIES": ";".join(sorted(INDEPENDENT_FAMILIES)),
                "PRUNED_PARENT_FAMILIES": ";".join(binding.PRUNED_FAMILIES),
                "EXCLUDED_REFERENCE_FAMILY": EXCLUDED_REFERENCE_FAMILY,
                "AUTHORITY_SNAPSHOT_ID": binding.SNAPSHOT_ID,
                "AUTHORITY_SCHEMA_VERSION": binding.SCHEMA_VERSION,
                "AUTHORITY_METHODOLOGY_VERSION": binding.METHODOLOGY_VERSION,
                "AUTHORITY_SEMANTIC_SHA256": binding.SNAPSHOT_SHA256,
                "AUTHORITY_FILE_SHA256": authority_file_sha256,
                "CONSTRUCTOR_ID": metadata.CONSTRUCTOR_ID,
                "CONSTRUCTOR_VERSION": "v1",
                "REQUESTED_BUDGET": str(metadata.TICKET_BUDGET),
                "TICKET_COUNT": "DYNAMIC_UNION_CARDINALITY",
                "TICKET_CARDINALITY_RULE": cast(str, semantics["TICKET_CARDINALITY_RULE"]),
                "MINIMUM_HISTORY": str(MINIMUM_HISTORY),
                "OUTPUT_SHAPE": OUTPUT_SHAPE,
                "CAUSAL_CUTOFF_RULE": CAUSAL_CUTOFF_RULE,
                "PARAMETER_SELECTION_RULE": PARAMETER_SELECTION_RULE,
                "DETERMINISM_CLASS": DETERMINISM_CLASS,
                "RNG_SEMANTICS": RNG_SEMANTICS,
                "REDUNDANCY_REFRESH_CADENCE": REDUNDANCY_REFRESH_CADENCE,
                "WITHIN_COHORT_REFRESH_ALLOWED": "NO",
                "HYPOTHESIS_DERIVED_FROM_PRIOR_EMPIRICAL_RESULTS": (
                    HYPOTHESIS_DERIVED_FROM_PRIOR_EMPIRICAL_RESULTS
                ),
                "SAME_DATA_CONFIRMATORY_ELIGIBILITY": SAME_DATA_CONFIRMATORY_ELIGIBILITY,
                "DISCOVERY_HISTORY_ROLE": DISCOVERY_HISTORY_ROLE,
                "CONFIRMATORY_RESTRICTION": CONFIRMATORY_RESTRICTION,
                "DIRECT_2B_REGISTRATION_AUTHORIZED": DIRECT_2B_REGISTRATION_AUTHORIZED,
                "IMPLEMENTATION_MODULE": (
                    "lottolab.research."
                    "biglotto_cross_family_redundancy_pruned_ensemble_v1_candidate_batch_r1"
                ),
                "IMPLEMENTATION_SYMBOL": metadata.IMPLEMENTATION_SYMBOL,
                "IMPLEMENTATION_COMMIT": implementation_commit,
            }
        )
    return tuple(rows)


def _handoff_rows(
    binding: AuthorityBinding,
    *,
    authority_file_sha256: str,
    implementation_commit: str,
) -> tuple[dict[str, str], ...]:
    rows: list[dict[str, str]] = []
    for row in _candidate_rows(
        binding,
        authority_file_sha256=authority_file_sha256,
        implementation_commit=implementation_commit,
    ):
        rows.append(
            {
                "CANDIDATE_ID": row["CANDIDATE_ID"],
                "HYPOTHESIS_VERSION": row["HYPOTHESIS_VERSION"],
                "SIGNATURE_HASH": row["SIGNATURE_HASH"],
                "NEW_FAMILY_ID": row["NEW_FAMILY_ID"],
                "PARENT_MEMBERSHIP": row["PARENT_MEMBERSHIP"],
                "PRUNED_PARENT_FAMILIES": row["PRUNED_PARENT_FAMILIES"],
                "AUTHORITY_SNAPSHOT_ID": row["AUTHORITY_SNAPSHOT_ID"],
                "AUTHORITY_SEMANTIC_SHA256": row["AUTHORITY_SEMANTIC_SHA256"],
                "AUTHORITY_FILE_SHA256": row["AUTHORITY_FILE_SHA256"],
                "CONSTRUCTOR_ID": row["CONSTRUCTOR_ID"],
                "REQUESTED_BUDGET": row["REQUESTED_BUDGET"],
                "TICKET_COUNT": row["TICKET_COUNT"],
                "MINIMUM_HISTORY": row["MINIMUM_HISTORY"],
                "IMPLEMENTATION_MODULE": row["IMPLEMENTATION_MODULE"],
                "IMPLEMENTATION_SYMBOL": row["IMPLEMENTATION_SYMBOL"],
                "IMPLEMENTATION_COMMIT": implementation_commit,
                "TECHNICAL_IMPLEMENTATION_STATUS": "COMPLETE",
                "CATALOG_STATUS": "NOT_CATALOG_WIRED",
                "HISTORICAL_VALIDATION_STATUS": "NOT_RUN_BY_DESIGN",
                "ROLLING_STATUS": "NOT_RUN_BY_DESIGN",
                "FORWARD_REGISTRATION_STATUS": "NOT_RUN_BY_DESIGN",
                "PERFORMANCE_CONTAMINATION_STATUS": (
                    "SAME_DATA_NOT_ELIGIBLE_FORWARD_ONLY_AFTER_IMPLEMENTATION_FREEZE"
                ),
                "DIRECT_2B_REGISTRATION_AUTHORIZED": "NO",
            }
        )
    return tuple(rows)


def _csv_bytes(rows: Sequence[Mapping[str, str]], fieldnames: Sequence[str]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def _json_bytes(payload: Mapping[str, object]) -> bytes:
    return (
        json.dumps(_json_ready(payload), ensure_ascii=False, sort_keys=True, indent=2)
        + "\n"
    ).encode("utf-8")


def write_candidate_batch_artifacts(
    output_root: str | Path,
    *,
    authority_snapshot: Mapping[str, object] = DEFAULT_AUTHORITY_SNAPSHOT,
    implementation_commit: str = "UNCOMMITTED_WORKTREE_BASE_3d25db7",
) -> tuple[Path, ...]:
    """Write the six deterministic Lane-1 batch artifacts."""

    binding = bind_authority(authority_snapshot)
    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    expected_names = {
        "source_universe_contract.json",
        "redundancy_authority_snapshot.json",
        "candidate_authority.csv",
        "candidate_validation_handoff.csv",
        "candidate_batch_manifest.json",
        "SHA256SUMS",
    }
    existing = {path.name for path in root.iterdir() if path.is_file()}
    unexpected = existing - expected_names
    if unexpected:
        raise FileExistsError(f"output root contains unrelated files: {sorted(unexpected)}")

    authority_payload = dict(authority_snapshot)
    authority_bytes = _json_bytes(cast(Mapping[str, object], authority_payload))
    authority_path = root / "redundancy_authority_snapshot.json"
    authority_path.write_bytes(authority_bytes)
    authority_file_sha = _sha256_bytes(authority_bytes)

    source_contract = build_source_universe_contract(
        binding, authority_file_sha256=authority_file_sha
    )
    source_contract_path = root / "source_universe_contract.json"
    source_contract_path.write_bytes(_json_bytes(source_contract))

    authority_rows = _candidate_rows(
        binding,
        authority_file_sha256=authority_file_sha,
        implementation_commit=implementation_commit,
    )
    authority_fields = tuple(authority_rows[0])
    authority_path_csv = root / "candidate_authority.csv"
    authority_path_csv.write_bytes(_csv_bytes(authority_rows, authority_fields))

    handoff_rows = _handoff_rows(
        binding,
        authority_file_sha256=authority_file_sha,
        implementation_commit=implementation_commit,
    )
    handoff_path = root / "candidate_validation_handoff.csv"
    handoff_path.write_bytes(_csv_bytes(handoff_rows, tuple(handoff_rows[0])))

    manifest = {
        "SCHEMA_VERSION": (
            "BIGLOTTO_CROSS_FAMILY_REDUNDANCY_PRUNED_ENSEMBLE_V1_"
            "CANDIDATE_BATCH_MANIFEST_V1"
        ),
        "TASK_ID": "BIGLOTTO_CROSS_FAMILY_REDUNDANCY_PRUNED_ENSEMBLE_V1_CANDIDATE_BATCH_R1",
        "CLASSIFICATION": (
            "BIGLOTTO_CROSS_FAMILY_REDUNDANCY_PRUNED_ENSEMBLE_V1_"
            "CANDIDATE_BATCH_R1_COMPLETE"
        ),
        "HYPOTHESIS_ID": HYPOTHESIS_ID,
        "NEW_FAMILY_ID": NEW_FAMILY_ID,
        "WORKER_ROUTE": "STANDARD",
        "AUTHORITY": {
            "SNAPSHOT_ID": binding.SNAPSHOT_ID,
            "SCHEMA_VERSION": binding.SCHEMA_VERSION,
            "METHODOLOGY_VERSION": binding.METHODOLOGY_VERSION,
            "SEMANTIC_SHA256": binding.SNAPSHOT_SHA256,
            "FILE_SHA256": authority_file_sha,
            "REFERENCE_WINDOW": REFERENCE_WINDOW,
            "DATA_CUTOFF": DATA_CUTOFF,
            "REDUNDANCY_REFRESH_CADENCE": REDUNDANCY_REFRESH_CADENCE,
            "WITHIN_COHORT_REFRESH_ALLOWED": WITHIN_COHORT_REFRESH_ALLOWED,
            "RETAINED_FAMILIES": list(binding.RETAINED_FAMILIES),
            "PRUNED_FAMILIES": list(binding.PRUNED_FAMILIES),
        },
        "CANDIDATE_MATRIX": {
            "CONSTRUCTORS": list(CONSTRUCTOR_IDS),
            "REQUESTED_BUDGETS": list(TICKET_BUDGETS),
            "COUNT": len(authority_rows),
            "TICKET_CARDINALITY": TICKET_CARDINALITY_RULE,
        },
        "ALL_CANDIDATE_IDS": [row["CANDIDATE_ID"] for row in authority_rows],
        "ALL_SIGNATURE_HASHES": [row["SIGNATURE_HASH"] for row in authority_rows],
        "ALL_CANDIDATES_DETERMINISTIC": "YES",
        "ALL_CANDIDATES_REQUIRE_ALL_INDEPENDENT_PARENTS": "YES",
        "HISTORICAL_VALIDATION": "NOT_RUN_BY_DESIGN",
        "ROLLING": "NOT_RUN_BY_DESIGN",
        "FORWARD_PREDICTION_REGISTRATION": "NOT_RUN_BY_DESIGN",
        "PRODUCTION_CATALOG_MUTATION": "NONE",
        "CONTAMINATION_BOUNDARY": {
            "HYPOTHESIS_DERIVED_FROM_PRIOR_EMPIRICAL_RESULTS": (
                HYPOTHESIS_DERIVED_FROM_PRIOR_EMPIRICAL_RESULTS
            ),
            "SAME_DATA_CONFIRMATORY_ELIGIBILITY": SAME_DATA_CONFIRMATORY_ELIGIBILITY,
            "DISCOVERY_HISTORY_ROLE": DISCOVERY_HISTORY_ROLE,
            "CONFIRMATORY_RESTRICTION": CONFIRMATORY_RESTRICTION,
            "DIRECT_2B_REGISTRATION_AUTHORIZED": DIRECT_2B_REGISTRATION_AUTHORIZED,
        },
        "IMPLEMENTATION": {
            "MODULE": (
                "lottolab.research."
                "biglotto_cross_family_redundancy_pruned_ensemble_v1_candidate_batch_r1"
            ),
            "CHANGED_PATHS": [
                "src/lottolab/research/biglotto_cross_family_redundancy_pruned_ensemble_v1_candidate_batch_r1.py",
                "tests/unit/test_biglotto_cross_family_redundancy_pruned_ensemble_v1_candidate_batch_r1.py",
            ],
            "IMPLEMENTATION_COMMIT": implementation_commit,
            "PRODUCTION_RUNTIME_WIRING": "NONE",
        },
        "OUTPUT_FILES": sorted(expected_names - {"SHA256SUMS"}),
    }
    manifest_path = root / "candidate_batch_manifest.json"
    manifest_path.write_bytes(_json_bytes(manifest))

    payloads = {
        path.name: path.read_bytes()
        for path in (
            source_contract_path,
            authority_path,
            authority_path_csv,
            handoff_path,
            manifest_path,
        )
    }
    checksum_bytes = "".join(
        f"{_sha256_bytes(payloads[name])}  {name}\n" for name in sorted(payloads)
    ).encode("utf-8")
    checksum_path = root / "SHA256SUMS"
    checksum_path.write_bytes(checksum_bytes)
    return tuple(root / name for name in sorted(expected_names))


__all__ = [
    "ANALYSIS_PROTOCOL_SHA256",
    "AUTHORITY_SCHEMA_VERSION",
    "AUTHORITY_SNAPSHOT_ID",
    "CANDIDATE_AUTHORITIES",
    "CANDIDATE_IDS",
    "CANDIDATE_IDS_BY_CONSTRUCTOR_AND_BUDGET",
    "CANDIDATE_METADATA",
    "CANDIDATE_SIGNATURE_HASHES",
    "CLASSIFICATION_ARTIFACT_SHA256",
    "CONSTRUCTOR_IDS",
    "DATA_CUTOFF",
    "DEFAULT_AUTHORITY_BINDING",
    "DEFAULT_AUTHORITY_SNAPSHOT",
    "DIRECT_2B_REGISTRATION_AUTHORIZED",
    "DISCOVERY_HISTORY_ROLE",
    "EXCLUDED_REFERENCE_FAMILY",
    "HISTORY_ORDER",
    "HYPOTHESIS_DERIVED_FROM_PRIOR_EMPIRICAL_RESULTS",
    "HYPOTHESIS_ID",
    "INDEPENDENT_FAMILIES",
    "MINIMUM_HISTORY",
    "NEW_FAMILY_ID",
    "PARENT_SOURCE_UNIVERSE_IDS",
    "REDUNDANCY_REFRESH_CADENCE",
    "REFERENCE_WINDOW",
    "SAME_DATA_CONFIRMATORY_ELIGIBILITY",
    "TICKET_BUDGETS",
    "TICKET_CARDINALITY_RULE",
    "UNION_ORDER_RULE",
    "WITHIN_COHORT_REFRESH_ALLOWED",
    "AuthorityBinding",
    "AuthorityError",
    "AuthorityMismatchError",
    "AuthorityUnavailableError",
    "CandidateIdentity",
    "CandidateMetadata",
    "CandidatePortfolio",
    "RequiredParentUnavailableError",
    "assert_authority_unchanged",
    "authority_semantic_sha256",
    "bind_authority",
    "build_authority_snapshot_from_classification_rows",
    "build_candidate_authorities",
    "build_candidate_portfolio",
    "build_source_universe_contract",
    "candidate_id_for",
    "candidate_id_for_semantics",
    "canonicalize_semantic_record",
    "derive_candidate_identity",
    "load_classification_csv",
    "produce_b649_cross_family_redundancy_pruned_ensemble_v1_exposure_balanced_k5",
    "produce_b649_cross_family_redundancy_pruned_ensemble_v1_exposure_balanced_k10",
    "produce_b649_cross_family_redundancy_pruned_ensemble_v1_exposure_balanced_k20",
    "produce_b649_cross_family_redundancy_pruned_ensemble_v1_hybrid_diversity_k5",
    "produce_b649_cross_family_redundancy_pruned_ensemble_v1_hybrid_diversity_k10",
    "produce_b649_cross_family_redundancy_pruned_ensemble_v1_hybrid_diversity_k20",
    "produce_b649_cross_family_redundancy_pruned_ensemble_v1_low_overlap_k5",
    "produce_b649_cross_family_redundancy_pruned_ensemble_v1_low_overlap_k10",
    "produce_b649_cross_family_redundancy_pruned_ensemble_v1_low_overlap_k20",
    "produce_biglotto_cross_family_redundancy_pruned_ensemble_candidate",
    "produce_candidate_portfolio",
    "prune_families",
    "seal_authority_snapshot",
    "signature_hash_for_semantics",
    "union_native_ticket_sets",
    "write_candidate_batch_artifacts",
]
