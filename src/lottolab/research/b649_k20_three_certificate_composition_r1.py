"""Compose the verified T249, T251, and CCZ236 certificates locally.

The Family method keeps the frozen Family row for CCZ236. Bonf64 is a
separate profile-specific method and never updates or replaces that row.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

from lottolab.research import b649_k20_ccz236_bonf64_evidence_adoption_r1 as ccz
from lottolab.research import b649_k20_t249_t251_verified_overlay_r1 as overlay


CCZ_RESULT_PATH = (
    "docs/research/matrix-native-results/"
    "b649-k20-ccz236-bonf64-evidence-adoption-r1-result.json"
)
CCZ_RESULT_SHA256 = "5d5a7c75f8728258b4ee32f348fc8afb564967df1a2aabe0027768fb12ecbed9"
CCZ_VALIDATOR_PATH = (
    "src/lottolab/research/"
    "b649_k20_ccz236_bonf64_evidence_adoption_r1.py"
)
CCZ_VALIDATOR_SHA256 = "9abdc33d1190ff25a2fd43a6c440addd9305ba212b5b5d6dc5e3636f7b531598"

FROZEN_HEAD = "e6fee5ebbfb972a1432bbc10ab5a337feac38478"
FROZEN_TREE = "0f32a6e5c813953bb902cce395b5b6fea0a77c59"
FROZEN_FAMILY_RESULT_PATH = (
    "docs/research/matrix-native-results/"
    "b649-k20-min-s2-neighbor-deficit-sts13-family-closure-r1-result.json"
)
FROZEN_FAMILY_RESULT_SHA256 = "fef709c5168afa6da26ce18e0be78c40a12c6a711dec364e42659e1bb309d7b6"

BONF64_SOURCE_PATH = (
    "src/lottolab/research/b649_k20_min_s2_higher_order_closure_r2.py"
)
BONF64_SOURCE_SHA256 = "6897c974fe9679f2ec567602522bb4c38c996275368b714c6a7fadedd66d6e45"
BONF64_SUPPORT_SOURCE_PATH = (
    "src/lottolab/research/"
    "b649_k20_min_s2_realizable_core_class_bound_r4.py"
)
BONF64_SUPPORT_SOURCE_SHA256 = "cbc57debfcc037b8be605f9c3e157dba9029fbbcca50fa05dcff99390066edec"

T249_PROFILE = "65555555555541000000"
T249_BOUND = 313121137
T251_PROFILE = "66555555555531000000"
T251_BOUND = 313142921
CCZ_PROFILE = "55555555555551000000"
CCZ_FAMILY_BOUND = 313250644
CCZ_BONF64_BOUND = 313091112
FAMILY_MAXIMUM = 313263888

FAMILY_METHOD = "FAMILY_BOUND"
BONF64_METHOD = "U64(T)=B3(W,T)-64*Phi93(3*T-66); W=826; 22<=T<=236"

_EXPECTED_OVERLAY_OVERRIDES = {
    T249_PROFILE: T249_BOUND,
    T251_PROFILE: T251_BOUND,
}


class CompositionValidationError(ValueError):
    """Raised when any pinned certificate or method boundary fails."""


def _need(condition: bool, message: str) -> None:
    if not condition:
        raise CompositionValidationError(message)


def _root() -> Path:
    return Path(__file__).resolve().parents[3]


def _read_verified_file(
    root: Path, relative_path: str, expected_sha256: str, gate: str
) -> bytes:
    path = root / relative_path
    _need(not path.is_symlink() and path.is_file(), gate + "_NOT_REGULAR_FILE")
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise CompositionValidationError(gate + "_READ_FAILED") from exc
    _need(hashlib.sha256(data).hexdigest() == expected_sha256, gate + "_SHA_MISMATCH")
    return data


def _read_ccz_result(root: Path) -> Dict[str, Any]:
    data = _read_verified_file(
        root, CCZ_RESULT_PATH, CCZ_RESULT_SHA256, "CCZ_RESULT"
    )
    try:
        result = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CompositionValidationError("CCZ_RESULT_INVALID_JSON") from exc
    _need(type(result) is dict, "CCZ_RESULT_NOT_OBJECT")
    return result


def _verify_ccz_source_roles(root: Path, expected: Dict[str, Any]) -> None:
    validator_file = Path(ccz.__file__).resolve()
    expected_validator_file = (root / CCZ_VALIDATOR_PATH).resolve()
    _need(validator_file == expected_validator_file, "WRONG_CCZ_VALIDATOR_PATH")
    _read_verified_file(
        root, CCZ_VALIDATOR_PATH, CCZ_VALIDATOR_SHA256, "CCZ_VALIDATOR_SOURCE"
    )
    _read_verified_file(
        root, BONF64_SOURCE_PATH, BONF64_SOURCE_SHA256, "BONF64_SOURCE"
    )
    _read_verified_file(
        root,
        BONF64_SUPPORT_SOURCE_PATH,
        BONF64_SUPPORT_SOURCE_SHA256,
        "BONF64_SUPPORT_SOURCE",
    )

    expected_roles = {
        "PROFILE_ID": CCZ_PROFILE,
        "FROZEN_HEAD": FROZEN_HEAD,
        "FROZEN_TREE": FROZEN_TREE,
        "FROZEN_FAMILY_RESULT_PATH": FROZEN_FAMILY_RESULT_PATH,
        "FROZEN_RESULT_SHA256": FROZEN_FAMILY_RESULT_SHA256,
        "BONF64_SOURCE_PATH": BONF64_SOURCE_PATH,
        "BONF64_SOURCE_SHA256": BONF64_SOURCE_SHA256,
        "BONF64_SUPPORT_SOURCE_PATH": BONF64_SUPPORT_SOURCE_PATH,
        "BONF64_SUPPORT_SOURCE_SHA256": BONF64_SUPPORT_SOURCE_SHA256,
        "BONF64_METHOD_IDENTITY": BONF64_METHOD,
        "BONF64_CERTIFIED_BOUND": CCZ_BONF64_BOUND,
        "FROZEN_FAMILY_ROW_BOUND": CCZ_FAMILY_BOUND,
        "HISTORICAL_R30_CAP": 265,
        "FULL_FAMILY_CLOSURE": "NOT_CLAIMED",
        "GLOBAL_OPTIMUM": "NOT_CLAIMED",
        "FAMILY_MAXIMUM_REDUCED": False,
        "HISTORICAL_RESOURCE": "FAIL",
        "NEW_RESOURCE_VERDICT": "FAIL",
    }
    for key, value in expected_roles.items():
        _need(expected.get(key) == value, "WRONG_CCZ_EXPECTED_FIELD:" + key)


def _validated_ccz_bound(root: Path) -> int:
    certificate = _read_ccz_result(root)
    try:
        differences = ccz.validate_certificate(certificate)
    except (OSError, TypeError, ValueError, KeyError) as exc:
        raise CompositionValidationError("CCZ_PUBLIC_VALIDATOR_FAILED") from exc
    _need(not differences, "CCZ_PUBLIC_VALIDATOR_REJECTED")

    expected = ccz.expected_certificate()
    _need(type(expected) is dict, "CCZ_EXPECTED_CERTIFICATE_NOT_OBJECT")
    _verify_ccz_source_roles(root, expected)
    return CCZ_BONF64_BOUND


def _validated_overlay() -> overlay.VerifiedOverlay:
    try:
        verified = overlay.build_verified_overlay()
    except (overlay.OverlayValidationError, OSError, ValueError, KeyError, TypeError) as exc:
        raise CompositionValidationError(
            "T249_T251_OVERLAY_REJECTED:" + str(exc)
        ) from exc

    _need(verified.row_bound_overrides == _EXPECTED_OVERLAY_OVERRIDES,
          "THIRD_FAMILY_OVERRIDE")
    _need(verified.source_head == FROZEN_HEAD, "WRONG_FROZEN_HEAD")
    _need(verified.source_tree == FROZEN_TREE, "WRONG_FROZEN_TREE")
    _need(verified.source_result_path == FROZEN_FAMILY_RESULT_PATH,
          "WRONG_FROZEN_RESULT_PATH")
    _need(verified.source_result_sha256 == FROZEN_FAMILY_RESULT_SHA256,
          "WRONG_FROZEN_RESULT_SHA")
    _need(verified.family_max_before == FAMILY_MAXIMUM,
          "WRONG_FAMILY_MAX_BEFORE")
    _need(verified.family_max_after == FAMILY_MAXIMUM,
          "WRONG_FAMILY_MAX_AFTER")
    _need(verified.family_max_delta == 0, "FAMILY_MAXIMUM_CHANGED")
    _need(verified.other_rows_unchanged is True, "OTHER_FAMILY_ROWS_CHANGED")
    _need(verified.full_family_closure == "NOT_CLAIMED",
          "FALSE_FAMILY_CLOSURE")
    _need(verified.global_optimum == "NOT_CLAIMED", "FALSE_GLOBAL_OPTIMUM")

    try:
        ccz_family_bound = verified.row_bound_for(CCZ_PROFILE)
        verified.row_bound_for(T249_PROFILE)
        verified.row_bound_for(T251_PROFILE)
    except KeyError as exc:
        raise CompositionValidationError("UNKNOWN_FAMILY_PROFILE") from exc
    _need(ccz_family_bound == CCZ_FAMILY_BOUND,
          "CCZ_FAMILY_BOUND_MISMATCH")
    return verified


@dataclass(frozen=True)
class VerifiedEvidenceSet:
    """Three validated certificates with distinct Family and Bonf64 methods."""

    _overlay: overlay.VerifiedOverlay
    _bonf64_bound: int

    @property
    def family_maximum(self) -> int:
        return FAMILY_MAXIMUM

    @property
    def full_family_closure(self) -> str:
        return "NOT_CLAIMED"

    def query_certified_bound(self, profile_id: str, method: str) -> int:
        if type(profile_id) is not str:
            raise CompositionValidationError("UNKNOWN_PROFILE")
        try:
            family_bound = self._overlay.row_bound_for(profile_id)
        except KeyError as exc:
            raise CompositionValidationError("UNKNOWN_PROFILE") from exc

        if method == FAMILY_METHOD:
            return family_bound
        if method == BONF64_METHOD:
            _need(profile_id == CCZ_PROFILE, "BONF64_PROFILE_SCOPE_MISMATCH")
            return self._bonf64_bound
        raise CompositionValidationError("UNKNOWN_METHOD")


def build_verified_evidence_set() -> VerifiedEvidenceSet:
    """Validate the existing overlay and CCZ certificate, then return both methods."""

    root = _root()
    bonf64_bound = _validated_ccz_bound(root)
    verified_overlay = _validated_overlay()
    _need(bonf64_bound == CCZ_BONF64_BOUND, "WRONG_CCZ_BONF64_BOUND")
    _need(bonf64_bound != verified_overlay.row_bound_for(CCZ_PROFILE),
          "CCZ_BONF64_AS_FAMILY_BOUND")
    return VerifiedEvidenceSet(
        _overlay=verified_overlay,
        _bonf64_bound=bonf64_bound,
    )


def query_certified_bound(profile_id: str, method: str) -> int:
    """Return one verified Family or CCZ Bonf64 bound by explicit method identity."""

    return build_verified_evidence_set().query_certified_bound(profile_id, method)
