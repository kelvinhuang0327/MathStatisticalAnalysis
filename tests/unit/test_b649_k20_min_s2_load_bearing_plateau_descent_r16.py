from __future__ import annotations

import json
from pathlib import Path
from time import monotonic

from lottolab.research.b649_k20_min_s2_current_bound_owner_refinement_r15 import (
    canonical_primitive_preflight,
)
from lottolab.research.b649_k20_min_s2_load_bearing_plateau_descent_r16 import (
    CERTIFIED_DROP_TARGET,
    EXPECTED_R15_CURSOR,
    INCUMBENT,
    MAX_GENERIC_CLASS_ELIMINATIONS,
    MAX_PROFILE_RESOLVES,
    PACKET_PROFILE,
    RESULT_FILENAME,
    START_BOUND,
    _current_state,
    _terminal_reason,
    freeze_current_plateau,
    profile_identity,
)
from lottolab.research.b649_k20_min_s2_next_active_profile_exact_bound_r8 import (
    coarse_profile_envelope,
)


def test_canonical_primitives_match_packet() -> None:
    assert canonical_primitive_preflight() == {
        "STATUS": "PASS",
        "SINGLE_TICKET_ANY_PRIZE": 18_611_432,
        "K20_S1": 372_228_640,
    }


def test_packet_profile_is_reused_from_prior_complete_class_certificate() -> None:
    state = _current_state()

    assert state.cursor_profile == EXPECTED_R15_CURSOR
    assert state.cursor_bound == START_BOUND
    assert PACKET_PROFILE in state.prior_profiles
    assert state.packet_profile_class_certificate == {
        "PROFILE": "66666665444111111100",
        "SQUARE_SUM": 332,
        "PROFILE_COUNT": 30,
        "CLASS_FAMILY_UPPER_BOUND": 313_636_504,
        "CERTIFICATION_STATUS": "CERTIFIED_BELOW_ACTIVE_BOUND",
        "REUSED_FROM": "R14.CLASS_CERTIFICATES[SQUARE_SUM=332]",
    }
    assert set(state.owner_profiles) == {
        (6, 6, 6, 5, 5, 5, 5, 5, 5, 5, 5, 5, 1, 1, 1, 0, 0, 0, 0, 0),
        (6, 6, 6, 6, 6, 5, 5, 5, 5, 5, 4, 4, 2, 1, 0, 0, 0, 0, 0, 0),
    }
    assert set(state.owner_profiles) <= state.prior_profiles
    assert state.prior_family_bound == 313_674_248
    assert state.prior_family_bound_owner_profiles == (
        (6, 6, 6, 6, 6, 5, 5, 5, 5, 5, 5, 3, 1, 1, 1, 0, 0, 0, 0, 0),
    )


def test_current_plateau_is_complete_and_ranked_before_first_lower_cursor() -> None:
    state = _current_state()
    plateau = freeze_current_plateau(
        cursor=state.cursor_profile,
        active_bound=state.cursor_bound,
        prior_profiles=state.prior_profiles,
        deadline=monotonic() + 120,
    )

    assert len(plateau.profiles) == 48
    assert plateau.profiles[0] == EXPECTED_R15_CURSOR
    assert all(
        coarse_profile_envelope(profile).family_upper_bound == START_BOUND
        for profile in plateau.profiles
    )
    assert plateau.next_profile is not None
    assert plateau.next_bound is not None
    assert plateau.next_bound == coarse_profile_envelope(
        plateau.next_profile
    ).family_upper_bound
    assert plateau.next_bound < START_BOUND
    assert not set(state.owner_profiles).intersection(plateau.profiles)
    assert plateau.lookup_profile_count == len(plateau.profiles) + 16
    assert plateau.frontier.lookup_complete is False


def test_stop_thresholds_are_exact_and_ordered() -> None:
    deadline = monotonic() + 60
    assert (
        _terminal_reason(
            family_bound=INCUMBENT,
            start_bound=START_BOUND,
            incumbent=INCUMBENT,
            certified_classes=0,
            resolved_profiles=0,
            deadline=deadline,
        )
        == "FAMILY_CLOSED"
    )
    assert (
        _terminal_reason(
            family_bound=START_BOUND - CERTIFIED_DROP_TARGET,
            start_bound=START_BOUND,
            incumbent=INCUMBENT,
            certified_classes=0,
            resolved_profiles=0,
            deadline=deadline,
        )
        == "CERTIFIED_DROP_TARGET_REACHED"
    )
    assert (
        _terminal_reason(
            family_bound=START_BOUND - 1,
            start_bound=START_BOUND,
            incumbent=INCUMBENT,
            certified_classes=MAX_GENERIC_CLASS_ELIMINATIONS,
            resolved_profiles=0,
            deadline=deadline,
        )
        == "THREE_COMPLETE_CLASSES_ELIMINATED_GENERALLY"
    )
    assert (
        _terminal_reason(
            family_bound=START_BOUND - 1,
            start_bound=START_BOUND,
            incumbent=INCUMBENT,
            certified_classes=0,
            resolved_profiles=MAX_PROFILE_RESOLVES,
            deadline=deadline,
        )
        == "PROFILE_CAP_REACHED"
    )


def test_profile_identity_is_unambiguous() -> None:
    assert profile_identity(EXPECTED_R15_CURSOR) == "66666665443111111110"


def test_result_artifact_resolves_the_complete_plateau_and_exact_cursor() -> None:
    result_path = (
        Path(__file__).resolve().parents[2]
        / "docs"
        / "research"
        / "matrix-native-results"
        / RESULT_FILENAME
    )
    result = json.loads(result_path.read_text(encoding="utf-8"))

    assert result["TASK_STATUS"] == "SUCCESS_C_EXACT_CURSOR"
    assert result["STOP_REASON"] == "CURRENT_CURSOR_NOT_FAMILY_BOUND"
    assert result["START_BOUND"] == START_BOUND
    assert result["END_BOUND"] == 313_674_248
    assert result["CUMULATIVE_DROP"] == 1_344
    assert result["CURRENT_PLATEAU_PROFILE_COUNT"] == 48
    assert result["PROFILES_PROCESSED"] == 0
    assert result["CLASSES_ANALYZED"] == 1
    assert result["CLASSES_CERTIFIED"] == 1
    assert result["PROFILES_ELIMINATED_BY_CLASS_BOUND"] == 48
    assert result["PRIOR_RESOLVED_FAMILY_UPPER_BOUND"] == 313_674_248
    assert result["PRIOR_RESOLVED_FAMILY_BOUND_OWNER_PROFILES"] == [
        "66666555555311100000"
    ]
    assert result["NEXT_ACTIVE_BOUND"] == 313_672_792
    assert result["NEXT_ACTIVE_PROFILE"] == "66666665442211111110"
    assert result["FAMILY_UPPER_BOUND"] == 313_674_248
    assert result["REMAINING_GAP"] == 434_587
    assert result["CANONICAL_PRIMITIVE_STATUS"] == "PASS"
    assert result["SOLVER_RUNTIME_PREFLIGHT"]["STATUS"] == "PASS"
    assert result["FULL_4850_PROFILE_CENSUS_REBUILT"] is False
    assert result["R15_OWNER_PROFILES_RERUN"] == []
    assert result["NEW_PORTFOLIO_SEARCH_STARTED"] is False
    assert result["PRODUCTION_MUTATION"] == "NONE"

    class_certificate = result["CLASS_CERTIFICATES"][0]
    class_profiles = {
        profile_identity(tuple(profile)) for profile in class_certificate["PROFILE_IDENTITIES"]
    }
    plateau_profiles = set(result["CURRENT_LOAD_BEARING_PLATEAU"])
    assert class_certificate["SQUARE_SUM"] == 326
    assert class_certificate["CLASS_FAMILY_UPPER_BOUND"] == 313_651_848
    assert class_certificate["CERTIFICATION_STATUS"] == "CERTIFIED_BELOW_ACTIVE_BOUND"
    assert class_certificate["COMPLETE_SUFFIX_ENUMERATION"] is True
    assert class_profiles == plateau_profiles
    histogram_rows = class_certificate["HISTOGRAM_ENVELOPES"]
    assert len(histogram_rows) == 48
    assert all(row["RELAXATION_STATUS"] == "OPTIMAL" for row in histogram_rows)
