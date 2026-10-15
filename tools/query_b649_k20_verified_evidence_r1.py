"""Offline query entrypoint for verified K20 three-certificate composition evidence.

This tool reuses the verified composition API from
src/lottolab/research/b649_k20_three_certificate_composition_r1.py
without modifying or re-implementing any mathematical proof, validator, or
family authority.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

# Ensure src is on sys.path for direct script execution
_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC_DIR = _REPO_ROOT / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from lottolab.research import (
    b649_k20_three_certificate_composition_r1 as composition,
)

VERIFIED_SOURCE_COMMIT = "e0d27985b87399e47c59840fc0424bde28032885"
VERIFIED_TREE = "5b72188dedbcb90a0ebf6481663a248c1a1512c7"
FROZEN_FAMILY_HEAD = composition.FROZEN_HEAD
FROZEN_FAMILY_RESULT_SHA256 = composition.FROZEN_FAMILY_RESULT_SHA256
FAMILY_MAXIMUM = composition.FAMILY_MAXIMUM

# Exact certified profiles
T249_PROFILE = composition.T249_PROFILE
T251_PROFILE = composition.T251_PROFILE
CCZ_PROFILE = composition.CCZ_PROFILE

# Exact certified bounds
T249_FAMILY_BOUND = composition.T249_BOUND
T251_FAMILY_BOUND = composition.T251_BOUND
CCZ_FAMILY_BOUND = composition.CCZ_FAMILY_BOUND
CCZ_BONF64_BOUND = composition.CCZ_BONF64_BOUND

# Canonical method identities
FAMILY_METHOD = composition.FAMILY_METHOD
BONF64_METHOD = composition.BONF64_METHOD

# Profile mapping aliases
PROFILE_ALIASES: Dict[str, str] = {
    "T249": T249_PROFILE,
    T249_PROFILE: T249_PROFILE,
    "T251": T251_PROFILE,
    T251_PROFILE: T251_PROFILE,
    "CCZ": CCZ_PROFILE,
    "CCZ236": CCZ_PROFILE,
    CCZ_PROFILE: CCZ_PROFILE,
}

# Method mapping aliases
METHOD_ALIASES: Dict[str, str] = {
    "FAMILY": FAMILY_METHOD,
    "FAMILY_BOUND": FAMILY_METHOD,
    FAMILY_METHOD: FAMILY_METHOD,
    "BONF64": BONF64_METHOD,
    "BONF64_BOUND": BONF64_METHOD,
    BONF64_METHOD: BONF64_METHOD,
}

# Approved (canonical_profile, canonical_method) -> expected_bound
APPROVED_QUERY_COMBINATIONS: Dict[tuple[str, str], int] = {
    (T249_PROFILE, FAMILY_METHOD): T249_FAMILY_BOUND,
    (T251_PROFILE, FAMILY_METHOD): T251_FAMILY_BOUND,
    (CCZ_PROFILE, FAMILY_METHOD): CCZ_FAMILY_BOUND,
    (CCZ_PROFILE, BONF64_METHOD): CCZ_BONF64_BOUND,
}


class VerifiedEvidenceQueryError(ValueError):
    """Raised when query fails validation or violates query bounds."""


def canonicalize_profile(profile_raw: str) -> str:
    """Resolve raw profile alias or string to canonical profile id."""
    if not isinstance(profile_raw, str):
        raise VerifiedEvidenceQueryError("UNKNOWN_PROFILE")
    stripped = profile_raw.strip()
    if stripped in PROFILE_ALIASES:
        return PROFILE_ALIASES[stripped]
    raise VerifiedEvidenceQueryError(f"UNKNOWN_PROFILE: {profile_raw}")


def canonicalize_method(method_raw: str) -> str:
    """Resolve raw method alias or string to canonical method identity."""
    if not isinstance(method_raw, str):
        raise VerifiedEvidenceQueryError("UNKNOWN_METHOD")
    stripped = method_raw.strip()
    if stripped in METHOD_ALIASES:
        return METHOD_ALIASES[stripped]
    raise VerifiedEvidenceQueryError(f"UNKNOWN_METHOD: {method_raw}")


def query_verified_evidence(
    profile: str,
    method: str,
    *,
    evidence_set: composition.VerifiedEvidenceSet | None = None,
) -> Dict[str, Any]:
    """Execute certified evidence query against verified composition API.

    Only the four approved combinations are permitted:
    - T249 / FAMILY
    - T251 / FAMILY
    - CCZ236 / FAMILY
    - CCZ236 / BONF64
    """
    canonical_profile = canonicalize_profile(profile)
    canonical_method = canonicalize_method(method)

    # Validate method profile compatibility
    if canonical_method == BONF64_METHOD and canonical_profile != CCZ_PROFILE:
        raise VerifiedEvidenceQueryError(
            f"WRONG_PROFILE_METHOD_MAPPING: BONF64 method only certified for CCZ236 ({CCZ_PROFILE}), got {canonical_profile}"
        )

    combo = (canonical_profile, canonical_method)
    if combo not in APPROVED_QUERY_COMBINATIONS:
        raise VerifiedEvidenceQueryError(
            f"WRONG_PROFILE_METHOD_MAPPING: combination ({canonical_profile}, {canonical_method}) is not an approved query combination"
        )
    expected_bound = APPROVED_QUERY_COMBINATIONS[combo]

    # Use existing composition API
    if evidence_set is None:
        evidence_set = composition.build_verified_evidence_set()

    # Query certified bound using both public methods to ensure API conformance
    bound = evidence_set.query_certified_bound(canonical_profile, canonical_method)
    direct_bound = composition.query_certified_bound(canonical_profile, canonical_method)
    if bound != direct_bound:
        raise VerifiedEvidenceQueryError(
            f"WRONG_BOUND: evidence_set bound {bound} does not match direct query_certified_bound {direct_bound}"
        )

    if bound != expected_bound:
        raise VerifiedEvidenceQueryError(
            f"WRONG_BOUND: queried bound {bound} does not match expected certified bound {expected_bound}"
        )

    # Validate family maximum and closure invariants
    if evidence_set.family_maximum != FAMILY_MAXIMUM:
        raise VerifiedEvidenceQueryError(
            f"WRONG_FAMILY_MAXIMUM: expected {FAMILY_MAXIMUM}, got {evidence_set.family_maximum}"
        )
    if evidence_set.full_family_closure != "NOT_CLAIMED":
        raise VerifiedEvidenceQueryError(
            f"FALSE_FAMILY_CLOSURE: expected NOT_CLAIMED, got {evidence_set.full_family_closure}"
        )

    # Validate method isolation: CCZ Family bound must differ from CCZ Bonf64 bound
    if canonical_profile == CCZ_PROFILE:
        if canonical_method == FAMILY_METHOD and bound == CCZ_BONF64_BOUND:
            raise VerifiedEvidenceQueryError("BONF64_AS_FAMILY: CCZ Family bound cannot equal CCZ Bonf64 bound")
        if canonical_method == BONF64_METHOD and bound == CCZ_FAMILY_BOUND:
            raise VerifiedEvidenceQueryError("FAMILY_AS_BONF64: CCZ Bonf64 bound cannot equal CCZ Family bound")

    return {
        "PROFILE_ID": canonical_profile,
        "METHOD_IDENTITY": canonical_method,
        "CERTIFIED_BOUND": bound,
        "SOURCE_COMMIT": VERIFIED_SOURCE_COMMIT,
        "PROOF_SCOPE": f"PROFILE_{canonical_profile}_LOCAL_BOUND_ONLY",
        "FULL_FAMILY_CLOSURE": "NOT_CLAIMED",
        "GLOBAL_OPTIMUM": "NOT_CLAIMED",
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Offline query CLI for verified K20 three-certificate composition evidence."
    )
    parser.add_argument(
        "--profile",
        required=True,
        help="Profile identifier or alias (T249, T251, CCZ236 / CCZ, or canonical 20-digit string).",
    )
    parser.add_argument(
        "--method",
        required=True,
        help="Method identity or alias (FAMILY / FAMILY_BOUND, or BONF64 / BONF64_BOUND).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    try:
        args = parse_args(argv)
        result = query_verified_evidence(args.profile, args.method)
        print(json.dumps(result, indent=2))
        return 0
    except (VerifiedEvidenceQueryError, composition.CompositionValidationError) as exc:
        sys.stderr.write(f"ERROR: {exc}\n")
        return 1
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2
    except Exception as exc:
        sys.stderr.write(f"UNEXPECTED_ERROR: {exc}\n")
        return 2


if __name__ == "__main__":
    sys.exit(main())
