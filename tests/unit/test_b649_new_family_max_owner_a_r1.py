"""Proof completeness, exact arithmetic, and focused authority fault injection."""

from __future__ import annotations

import json
from dataclasses import replace
from itertools import combinations_with_replacement
from unittest.mock import patch

import pytest

from lottolab.research import b649_new_family_max_owner_a_r1 as c


@pytest.fixture(scope="module")
def row() -> c.SourceRow:
    return c.source_authority()[0]


def test_frozen_result_reproduced() -> None:
    assert c.RESULT_PATH.read_bytes() == c.render(c.compute_result())


def test_complete_zero_graph_degree_image() -> None:
    # Independent Erdos-Gallai characterization checks the image of all 1,024 masks.
    degrees = [v for v in combinations_with_replacement(range(5), 5) if c.split.graphical(v)]
    expected = {tuple(2 + d for d in v) for v in degrees}
    assert set(c.zero_vectors()) == expected


def test_every_prior_degree_configuration_maps_into_new_superset() -> None:
    # The old complete relaxation carries more simultaneous graph conditions.
    # Every one of its 302 configurations must survive with all eligible low masks.
    states = set(c.states())
    configurations = list(c.split.degree_configurations(c.PROFILE_ID))
    assert len(configurations) == 302
    for config in configurations:
        a, q = sum(config.sigma[3:12]), config.sigma[12:]
        for mask in range(8):
            if 2 * mask.bit_count() <= 2 + sum(5 - v for v in q):
                state = c.State(a, q, config.zeta, mask)
                assert state in states
                assert state.objective() == config.f
                assert state.bound() <= 257


def test_full_profile_theorem_and_target_arithmetic() -> None:
    proof = c.theorem()
    assert (proof["CORE_COUNT"], proof["ZERO_COUNT"], proof["GOODMAN_CONSTANT"]) == (15, 5, 297)
    assert proof["PROOF_SCOPE"] == "FULL_PROFILE" and proof["RELAXATION_STATES"] == 3771
    assert proof["UNPROVED_ASSUMPTIONS"] == [] and proof["NEW_PROVED_T_CAP"] == 257
    terms = c.route_b(264)
    prefix = [max(t[1] for t in terms[: i + 1]) for i in range(len(terms))]
    assert max(t[0] for t, b in zip(terms, prefix, strict=True) if b <= c.TARGET_BOUND) == 263
    assert max(c.route_b(257), key=lambda t: t[1]) == (257, 313332416, 438, 200, 251202, 5085920)
    assert max(terms, key=lambda t: t[1]) == (264, 313395344, 490, 200, 286510, 5169024)


def test_new_constraint_is_load_bearing() -> None:
    # The maximum prior-relaxation F=285 is too large; its leaf constraint is essential.
    state = c.State(9, (5, 5, 5), (4, 4, 4, 6, 6), 1)
    assert state in set(c.states()) and state.objective() == 285
    assert c.remainder_floor(state.q, state.mask) == 28 and state.bound() == 257
    # The invalid complete G[L] would remove that entire contribution.
    invalid = replace(state, mask=7)
    assert invalid not in set(c.states()) and invalid.bound() == 285


def test_recorded_witness_and_vertex_relabelling(row: c.SourceRow) -> None:
    seen = c.realization_check(*row.realization)
    assert (seen["T"], seen["T_H"]) == (190, 107)
    for permutation in (tuple(reversed(range(20))), tuple((v + 7) % 20 for v in range(20))):
        triples, pairs = (
            tuple(tuple(sorted(permutation[v] for v in support)) for support in supports)
            for supports in row.realization
        )
        assert c.realization_check(triples, pairs) == seen


@pytest.mark.parametrize("profile", ["66555555555540000000", "66655555555521000000", "0" * 20])
def test_wrong_profile_rejected(profile: str) -> None:
    with pytest.raises(AssertionError, match="wrong Profile"):
        c.theorem(profile=profile)


def test_wrong_core_or_zero_premise_rejected() -> None:
    with (
        patch.object(c, "PROFILE_ID", "66555555555540000000"),
        pytest.raises(AssertionError, match="distribution"),
    ):
        c.premises(c.PROFILE_ID)
    with pytest.raises(AssertionError, match="q range"):
        c.remainder_floor((5, 5, 6), 1)


def test_missing_relaxation_state_and_wrong_zero_premise_rejected() -> None:
    all_states = tuple(c.states())
    with (
        patch.object(c, "states", return_value=iter(all_states[:-1])),
        pytest.raises(AssertionError, match="completeness"),
    ):
        c.theorem()
    with (
        patch.object(c, "zero_vectors", return_value=(*c.zero_vectors(), (2, 2, 2, 2, 6))),
        pytest.raises(AssertionError, match="completeness"),
    ):
        c.theorem()


@pytest.mark.parametrize("cap", [256, 258, 264])
def test_wrong_claimed_cap_rejected(cap: int) -> None:
    with pytest.raises(AssertionError, match="cap"):
        c.theorem(cap)


@pytest.mark.parametrize("field", ["bound", "cap", "s4_base", "source"])
def test_source_row_tampering_rejected(row: c.SourceRow, field: str) -> None:
    changes: dict[str, object] = {field: "other-source" if field == "source" else 0}
    wrong = replace(row, **changes)  # pyright: ignore[reportArgumentType]
    with pytest.raises(AssertionError, match="source Row identity"):
        c.audit_row(wrong)


def test_frozen_digest_and_tree_tampering_rejected() -> None:
    with patch.object(c, "FROZEN_SHA256", "0" * 64), pytest.raises(AssertionError, match="digest"):
        c.source_authority()
    with patch.object(c, "FROZEN_TREE", "0" * 40), pytest.raises(AssertionError, match="tree"):
        c.source_authority()


@pytest.mark.parametrize("index", [1, 2, 3, 4, 5])
def test_wrong_rounding_or_route_premise_rejected(index: int) -> None:
    term = list(c.route_b(257)[-1])
    term[index] -= 1
    wrong: c.Term = (term[0], term[1], term[2], term[3], term[4], term[5])
    with pytest.raises(AssertionError, match="wrong"):
        c.audit_term(wrong)


def test_wrong_route_cap_and_source_implementation_rejected() -> None:
    with pytest.raises(AssertionError, match="cap range"):
        c.route_b(265)
    with (
        patch.object(c.r32, "route_b_envelope", return_value=[]),
        pytest.raises(AssertionError, match="implementations differ"),
    ):
        c.route_b(257)


def test_no_family_or_outcome_claims() -> None:
    result = c.object_row(json.loads(c.RESULT_PATH.read_bytes()))
    assert result["FAMILY_GAIN_CLAIMED"] == result["NEW_WINNING_OUTCOMES"] == 0
    assert result["GLOBAL_K20_OPTIMUM"] == "UNKNOWN" and result["HEAVY_SOLVER_STARTED"] == "NO"
    assert result["JUDGE_MODE"] == "SELF_CHECK_ONLY" and result["PRODUCTION_MUTATION"] == "NONE"
