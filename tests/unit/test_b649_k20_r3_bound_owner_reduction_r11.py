"""Focused owner and exact-tail regression checks for R11."""

from __future__ import annotations

from lottolab.research.b649_k20_r3_bound_owner_reduction_r11 import (
    BoundTerm,
    build_result,
    canonical_primitives,
    exact_tail_spectrum,
    identify_owner_set,
)


def test_canonical_primitives_match_the_authoritative_counts() -> None:
    primitives = canonical_primitives()

    assert primitives["SINGLE_TICKET_ANY_PRIZE"] == 18_611_432
    assert primitives["PAIR_DIAGONAL_I6"] == 18_611_432
    assert primitives["K20_S1"] == 372_228_640


def test_owner_selector_preserves_all_exact_ties() -> None:
    terms = (
        BoundTerm("tail", 100, (), "fixture"),
        BoundTerm("state-a", 100, (), "fixture"),
        BoundTerm("state-b", 99, (), "fixture"),
    )

    assert identify_owner_set(terms) == ("tail", "state-a")


def test_corrected_tail_is_the_unique_load_bearing_owner() -> None:
    result = build_result()
    terms = result["TOP_LEVEL_R3_TERMS"]
    tail = next(term for term in terms if term["stable_id"] == "corrected-tail")
    state_terms = [term for term in terms if term["stable_id"].startswith("state:")]

    assert result["CURRENT_BOUND_OWNER_SET"] == ["corrected-tail"]
    assert result["OWNER_TERM_COUNT"] == 1
    assert len(terms) == 24
    assert len(state_terms) == 23
    top_state = max(state_terms, key=lambda term: term["bound"])
    assert top_state["stable_id"] == "state:s2-12695020-s3-735532"
    assert top_state["bound"] == 356_799_210
    assert all(term["bound"] < tail["bound"] for term in state_terms)


def test_exact_tail_spectrum_excludes_cutoff_plus_one_and_two() -> None:
    spectrum = exact_tail_spectrum()

    assert spectrum["ANCHOR_INCIDENCE_PROFILE_COUNT"] == 30
    assert spectrum["RESIDUAL_TICKET_COUNT"] == 18
    assert spectrum["CERTIFIED_CANDIDATE_VECTOR_COUNT_AT_CUTOFF"] == 10_816
    assert spectrum["EXACT_TYPE_VECTOR_COUNT_THROUGH_CUTOFF_PLUS_TWO"] == 10_816
    assert spectrum["VECTORS_AT_EXACT_CUTOFF_PLUS_ONE"] == 0
    assert spectrum["VECTORS_AT_EXACT_CUTOFF_PLUS_TWO"] == 0
    assert spectrum["MINIMUM_OMITTED_LOCAL_LOSS"] == 6_695_801
    assert spectrum["CORRECTED_TAIL_BOUND"] == 358_352_827


def test_final_formula_and_owner_are_self_consistent() -> None:
    result = build_result()
    terms = result["TOP_LEVEL_R3_TERMS"]
    state_bounds = [term["bound"] for term in terms if term["stable_id"].startswith("state:")]

    assert result["R3_BOUND"] == max(result["CORRECTED_TAIL_BOUND"], *state_bounds)
    assert result["R3_BOUND"] == 358_352_827
    assert result["SUCCESS_A"] is False
    assert result["SUCCESS_B"] is True
    assert result["SUCCESS_C"] is True
