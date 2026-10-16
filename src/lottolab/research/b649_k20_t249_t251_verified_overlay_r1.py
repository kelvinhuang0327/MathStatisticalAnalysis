"""Verified two-row overlay for the accepted T249 and T251 evidence.

This module composes the two existing adoption validators. It does not repeat
their mathematical checks and does not claim full Family closure.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Optional, Tuple

from lottolab.research import b649_k20_t249_evidence_adoption_r1 as t249
from lottolab.research import b649_k20_t251_evidence_adoption_r2 as t251


T249_RESULT_PATH = "docs/research/matrix-native-results/b649-k20-t249-evidence-adoption-r1-result.json"
T249_RESULT_SHA256 = "548119e80bbc2970e4691e40f5d6091e432dd8ac7d19b4f9ba1148cb6306f9aa"
T251_RESULT_PATH = "docs/research/matrix-native-results/b649-k20-t251-evidence-adoption-r2-result.json"
T251_RESULT_SHA256 = "c1fa1ac0cda4599199c5e0ae9124952b5f0dff340e9d5975a5990809ee8ad731"

T249_PROFILE = "65555555555541000000"
T251_PROFILE = "66555555555531000000"
FAMILY_MAX_OWNER_PROFILE = "55555555555511111100"
EXPECTED_FAMILY_MAX = 313263888

T249_OLD_BOUND, T249_NEW_BOUND = 313256489, 313121137
T251_OLD_BOUND, T251_NEW_BOUND = 313261354, 313142921

T249_ROW_BOUND_METHOD = "Maximum of stored per-T BOUND fields; no formula recomputation."
T251_METHOD_ID = "b649_k20_min_s2_shared_neighbor_deficit_certificate_r1"
T251_METHOD_PATH = "src/lottolab/research/b649_k20_min_s2_shared_neighbor_deficit_certificate_r1.py"
T251_METHOD_SHA256 = "ff1fe5bc00ec0fb50ad82af740f4747f7b8d0894830f7f151596d4ff4912ba53"


class OverlayValidationError(ValueError):
    """Raised when either pinned result or the exact two-row overlay fails."""


@dataclass(frozen=True)
class VerifiedOverlay:
    source_head: str
    source_tree: str
    source_result_path: str
    source_result_sha256: str
    _overrides: Tuple[Tuple[str, int], ...]
    _source_profile_bounds: Tuple[Tuple[str, int], ...]
    family_max_owner_profile: str
    family_max_before: int
    family_max_after: int
    family_max_delta: int
    other_rows_unchanged: bool
    full_family_closure: str = "NOT_CLAIMED"
    global_optimum: str = "NOT_CLAIMED"

    @property
    def row_bound_overrides(self) -> Dict[str, int]:
        """Return exactly the two accepted profile updates."""
        return dict(self._overrides)

    def row_bound_for(self, profile_id: str) -> int:
        """Query the overlay, falling back to that profile's frozen bound."""
        for candidate, bound in self._overrides:
            if candidate == profile_id:
                return bound
        for candidate, bound in self._source_profile_bounds:
            if candidate == profile_id:
                return bound
        raise KeyError(profile_id)


def _need(condition: bool, message: str) -> None:
    if not condition:
        raise OverlayValidationError(message)


def _same(actual: object, expected: object, gate: str) -> None:
    _need(type(actual) is type(expected) and actual == expected, gate)


def _object(parent: dict, key: str, gate: str) -> dict:
    value = parent.get(key)
    _need(type(value) is dict, gate)
    return value


def _read_result(root: Path, relative_path: str, expected_sha256: str) -> dict:
    path = root / relative_path
    _need(not path.is_symlink() and path.is_file(), "PINNED_RESULT_NOT_REGULAR_FILE")
    try:
        blob = path.read_bytes()
    except OSError as exc:
        raise OverlayValidationError("PINNED_RESULT_READ_FAILED") from exc
    _same(hashlib.sha256(blob).hexdigest(), expected_sha256, "PINNED_RESULT_SHA_MISMATCH")
    try:
        result = json.loads(blob)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OverlayValidationError("PINNED_RESULT_INVALID_JSON") from exc
    _need(type(result) is dict, "PINNED_RESULT_NOT_OBJECT")
    return result


def _validate_result_pair(t249_result: dict, t251_result: dict) -> None:
    t249_source = {
        "FROZEN_HEAD": t249_result.get("FROZEN_HEAD"),
        "FROZEN_TREE": t249_result.get("FROZEN_TREE"),
        "FROZEN_RESULT_PATH": t249_result.get("FROZEN_RESULT_PATH"),
        "FROZEN_RESULT_SHA256": t249_result.get("FROZEN_RESULT_SHA256"),
    }
    t251_provenance = _object(t251_result, "PROVENANCE", "T251_PROVENANCE_MISSING")
    t251_source = {
        "FROZEN_HEAD": t251_provenance.get("FROZEN_HEAD"),
        "FROZEN_TREE": t251_provenance.get("FROZEN_TREE"),
        "FROZEN_RESULT_PATH": t251_provenance.get("FROZEN_RESULT_PATH"),
        "FROZEN_RESULT_SHA256": t251_provenance.get("FROZEN_RESULT_SHA256"),
    }
    expected_source = {
        "FROZEN_HEAD": t249.FROZEN_HEAD,
        "FROZEN_TREE": t249.FROZEN_TREE,
        "FROZEN_RESULT_PATH": t249.FROZEN_RESULT_PATH,
        "FROZEN_RESULT_SHA256": t249.FROZEN_RESULT_SHA256,
    }
    _same(t249_source, t251_source, "MISMATCHED_FROZEN_SOURCE")
    _same(t249_source, expected_source, "MISMATCHED_FROZEN_SOURCE")

    _same(t249_result.get("PROFILE_ID"), T249_PROFILE, "WRONG_PROFILE_MAPPING")
    _same(t251_result.get("PROFILE"), T251_PROFILE, "WRONG_PROFILE_MAPPING")
    _need(T249_PROFILE != T251_PROFILE, "DUPLICATE_PROFILE")

    t249_method = _object(
        t249_result, "ROW_BOUND_EVIDENCE", "WRONG_BOUND_METHOD"
    )
    _same(t249_method.get("SOURCE_COLUMN"), "BOUND", "WRONG_BOUND_METHOD")
    _same(t249_method.get("SOURCE_METHOD"), T249_ROW_BOUND_METHOD, "WRONG_BOUND_METHOD")
    _same(t251_provenance.get("SOURCE_METHOD"), T251_METHOD_ID, "WRONG_BOUND_METHOD")
    _same(t251_provenance.get("SOURCE_METHOD_PATH"), T251_METHOD_PATH, "WRONG_BOUND_METHOD")
    _same(t251_provenance.get("SOURCE_METHOD_SHA256"), T251_METHOD_SHA256, "WRONG_BOUND_METHOD")
    _same(t251_provenance.get("SOURCE_COLUMN"), "BOUND", "WRONG_BOUND_METHOD")
    _same(t251_provenance.get("SOURCE_COLUMN_INDEX"), 12, "WRONG_BOUND_METHOD")
    _same(
        t251_provenance.get("SOURCE_INPUT_PATH"),
        t249_result.get("PROOF_SOURCE_PATH"),
        "MISMATCHED_PER_T_SOURCE",
    )
    _same(
        t251_provenance.get("SOURCE_INPUT_SHA256"),
        t249_result.get("PROOF_SOURCE_SHA256"),
        "MISMATCHED_PER_T_SOURCE",
    )

    t249_numeric = {
        "OLD_CAP": 265,
        "NEW_CAP": 249,
        "OLD_ROW_BOUND": T249_OLD_BOUND,
        "NEW_ROW_BOUND": T249_NEW_BOUND,
        "ROW_IMPROVEMENT": 135352,
        "PER_T_BEFORE_COUNT": 244,
        "PER_T_AFTER_COUNT": 228,
    }
    for key, expected in t249_numeric.items():
        _same(t249_result.get(key), expected, "WRONG_T249_EVIDENCE_VALUE:" + key)

    t251_numeric = {
        "OLD_CAP": 265,
        "T_CAP": 251,
        "OLD_ROW_BOUND": T251_OLD_BOUND,
        "NEW_ROW_BOUND": T251_NEW_BOUND,
        "ROW_DELTA": 118433,
        "OLD_TERM_COUNT": 244,
        "TERM_COUNT": 230,
    }
    for key, expected in t251_numeric.items():
        _same(t251_result.get(key), expected, "WRONG_T251_EVIDENCE_VALUE:" + key)
    updates = t251_result.get("PROFILE_UPDATES")
    _same(updates, [[T251_PROFILE, T251_OLD_BOUND, T251_NEW_BOUND]], "WRONG_PROFILE_MAPPING")

    _same(t249_result.get("FULL_FAMILY_CLOSURE"), "NOT_CLAIMED", "FALSE_FAMILY_CLOSURE")
    _same(
        t249_result.get("FULL_FAMILY_MATHEMATICS"),
        "NOT_VERIFIED",
        "FALSE_FAMILY_CLOSURE",
    )
    historical = _object(t251_result, "HISTORICAL_STATUS", "RESOURCE_HISTORY_PROMOTION")
    _same(historical.get("FULL_FAMILY_CLOSURE"), "NOT_CLAIMED", "FALSE_FAMILY_CLOSURE")
    _same(historical.get("GLOBAL_OPTIMUM"), "NOT_CLAIMED", "FALSE_FAMILY_CLOSURE")
    _same(t249_result.get("MATHEMATICS"), "ACCEPTED", "HISTORICAL_STATUS_CHANGED")
    _same(t249_result.get("ORIGINAL_RESOURCE"), "FAIL", "RESOURCE_HISTORY_PROMOTION")
    _same(historical.get("HISTORICAL_MATH_RESOURCE"), "FAIL", "RESOURCE_HISTORY_PROMOTION")


def _profile_rows(family: dict) -> Tuple[Tuple[str, int], ...]:
    rows = family.get("COMPLETE_PROFILE_BOUNDS")
    _need(type(rows) is list and bool(rows), "FROZEN_PROFILE_ROWS_MISSING")
    profile_bounds = []
    seen = set()
    for row in rows:
        _need(type(row) is list and len(row) == 2, "FROZEN_PROFILE_ROW_SHAPE_MISMATCH")
        profile, bound = row
        _need(type(profile) is str and type(bound) is int, "FROZEN_PROFILE_ROW_TYPE_MISMATCH")
        _need(profile not in seen, "DUPLICATE_FROZEN_PROFILE")
        seen.add(profile)
        profile_bounds.append((profile, bound))
    return tuple(profile_bounds)


def _validated_updates(
    candidate_updates: Optional[Iterable[Tuple[str, int]]],
) -> Tuple[Tuple[str, int], ...]:
    expected = {T249_PROFILE: T249_NEW_BOUND, T251_PROFILE: T251_NEW_BOUND}
    if candidate_updates is None:
        return ((T249_PROFILE, T249_NEW_BOUND), (T251_PROFILE, T251_NEW_BOUND))
    _need(isinstance(candidate_updates, (list, tuple)), "WRONG_PROFILE_MAPPING")
    supplied = {}
    for item in candidate_updates:
        _need(type(item) in (list, tuple) and len(item) == 2, "WRONG_PROFILE_MAPPING")
        profile, bound = item
        _need(type(profile) is str and type(bound) is int, "WRONG_ROW_BOUND")
        _need(profile not in supplied, "DUPLICATE_PROFILE")
        supplied[profile] = bound
    _need(
        len(supplied) <= 2 and set(supplied).issubset(set(expected)),
        "THIRD_PROFILE_UPDATE",
    )
    _need(set(supplied) == set(expected), "WRONG_PROFILE_MAPPING")
    _same(supplied, expected, "WRONG_ROW_BOUND_OR_PROFILE_MAPPING")
    return ((T249_PROFILE, T249_NEW_BOUND), (T251_PROFILE, T251_NEW_BOUND))


def build_verified_overlay(
    candidate_updates: Optional[Iterable[Tuple[str, int]]] = None,
) -> VerifiedOverlay:
    """Validate both pinned adoptions and return the exact two-row overlay.

    ``candidate_updates`` is optional. When supplied, it is checked against the
    two fixed profile-to-bound pairs before the verified overlay is returned.
    """
    root = Path(__file__).resolve().parents[3]
    try:
        t249_result = _read_result(root, T249_RESULT_PATH, T249_RESULT_SHA256)
        t251_result = _read_result(root, T251_RESULT_PATH, T251_RESULT_SHA256)

        # Reuse both accepted public validators; result status strings alone
        # are not evidence of a valid adoption.
        sources = t249.load_pinned_sources(root)
        t249_evidence = t249.verify_adoption(sources)
        t249.validate_result_status(t249_result, t249_evidence)
        t251.validate_evidence_adoption(t251_result)

        _validate_result_pair(t249_result, t251_result)
        overrides = _validated_updates(candidate_updates)
        frozen_bounds = _profile_rows(sources.family)
        bounds_by_profile = dict(frozen_bounds)
        _same(bounds_by_profile.get(T249_PROFILE), T249_OLD_BOUND, "WRONG_T249_OLD_ROW_BOUND")
        _same(bounds_by_profile.get(T251_PROFILE), T251_OLD_BOUND, "WRONG_T251_OLD_ROW_BOUND")

        owner_rows = [
            (profile, bound) for profile, bound in frozen_bounds if bound == EXPECTED_FAMILY_MAX
        ]
        _same(sources.family.get("CANONICAL_INCUMBENT"), EXPECTED_FAMILY_MAX, "WRONG_FAMILY_MAX")
        _same(owner_rows, [(FAMILY_MAX_OWNER_PROFILE, EXPECTED_FAMILY_MAX)], "WRONG_FAMILY_MAX_OWNER")

        after_bounds = dict(frozen_bounds)
        for profile, new_bound in overrides:
            after_bounds[profile] = new_bound
        other_rows_unchanged = all(
            after_bounds[profile] == bound
            for profile, bound in frozen_bounds
            if profile not in (T249_PROFILE, T251_PROFILE)
        )
        _need(other_rows_unchanged, "OTHER_ROWS_CHANGED")
        _need(
            after_bounds[T249_PROFILE] < EXPECTED_FAMILY_MAX
            and after_bounds[T251_PROFILE] < EXPECTED_FAMILY_MAX,
            "ROW_BOUND_EXCEEDS_FAMILY_MAX",
        )
        max_after = max(after_bounds.values())
        after_owners = [profile for profile, bound in after_bounds.items() if bound == max_after]
        _same(max_after, EXPECTED_FAMILY_MAX, "FAMILY_MAX_CHANGED")
        _same(after_owners, [FAMILY_MAX_OWNER_PROFILE], "FAMILY_MAX_OWNER_CHANGED")

        return VerifiedOverlay(
            source_head=t249.FROZEN_HEAD,
            source_tree=t249.FROZEN_TREE,
            source_result_path=t249.FROZEN_RESULT_PATH,
            source_result_sha256=t249.FROZEN_RESULT_SHA256,
            _overrides=overrides,
            _source_profile_bounds=frozen_bounds,
            family_max_owner_profile=FAMILY_MAX_OWNER_PROFILE,
            family_max_before=EXPECTED_FAMILY_MAX,
            family_max_after=max_after,
            family_max_delta=max_after - EXPECTED_FAMILY_MAX,
            other_rows_unchanged=other_rows_unchanged,
        )
    except OverlayValidationError:
        raise
    except (t249.AdoptionError, t251.EvidenceValidationError, OSError, ValueError, KeyError, TypeError) as exc:
        raise OverlayValidationError(str(exc)) from exc


def query_row_bound(profile_id: str) -> int:
    """Return the adopted or frozen bound after validating both source artifacts."""
    return build_verified_overlay().row_bound_for(profile_id)
