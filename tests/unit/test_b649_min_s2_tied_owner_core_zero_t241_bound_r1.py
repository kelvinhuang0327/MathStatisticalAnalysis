"""Focused guards for the core-zero T<=241 cap of the tied owner 66555555555531000000."""

from __future__ import annotations

from itertools import combinations
from unittest.mock import patch

import pytest

from lottolab.research import b649_min_s2_tied_owner_core_zero_t241_bound_r1 as c


@pytest.fixture(scope="module")
def result() -> dict[str, object]:
    return c.compute_result()


def test_committed_result_is_reproduced_exactly(result: dict[str, object]) -> None:
    assert c.RESULT_PATH.read_bytes() == c.render(result)


def test_frozen_identity_and_recorded_row(result: dict[str, object]) -> None:
    assert (result["FROZEN_HEAD"], result["FROZEN_TREE"]) == (c.FROZEN_HEAD, c.FROZEN_TREE)
    assert result["FROZEN_RESULT_SHA256_VERIFIED"] is True
    sources = result["FROZEN_SOURCE_SHA256"]
    assert isinstance(sources, dict)
    assert sources[c.FROZEN_RESULT] == c.FROZEN_RESULT_SHA256
    assert c.frozen_row() == result["FROZEN_ROW"]
    assert result["FROZEN_ROW"] == {
        "SEVEN_ROW_FAMILY_BOUND": 313_398_532,
        "SEVEN_ROW_NEXT_COMPETING_BOUND": 313_398_248,
        "SEVEN_ROW_NEXT_COMPETING_OWNER_IDS": list(c.TIED_OWNERS),
        "SIX_ROW_RESOLVED_BOUND": 313_398_248,
        "R30_REFINEMENT_CAPS": [267, 266, 265],
    }


def test_frozen_result_digest_is_enforced() -> None:
    with (
        patch.object(c, "FROZEN_RESULT_SHA256", "0" * 64),
        pytest.raises(AssertionError, match="seven-row result digest"),
    ):
        c.frozen_row()


def test_premises_and_identity_with_e44() -> None:
    facts = c.premises()
    assert (facts["CORE_VERTICES"], facts["ZERO_VERTICES"]) == (14, 6)
    assert facts["CORE_DEGREE_CLASSES"] == {"6": 2, "5": 10, "3": 1, "1": 1}
    assert facts["PHI_INCLUSION_EXCLUSION"] == facts["PHI_GOODMAN"] == 295
    assert facts["CONSTANT"] == 241
    identity = c.identity_check()
    assert identity["E44_IDENTITY_POINTS_CHECKED"] == 1 + 2 * 20 + 190
    assert identity["SIGMA_RANGES"] == {
        "6": [0],
        "5": [0, 1],
        "3": [0, 1, 2, 3],
        "1": list(range(6)),
    }
    assert identity["ZETA_RANGE"] == [1, 2, 3, 4, 5, 6]


def test_wrong_constant_is_refuted_by_the_e44_identity() -> None:
    with patch.object(c, "CONSTANT", 240), pytest.raises(AssertionError, match="e44"):
        c.identity_check()


def test_cap_241_full_relaxation_and_independent_recount() -> None:
    cap, top, count = c.relaxation_maximum()
    assert cap == c.PROPOSED_CAP == 241
    assert count == len(list(c.relaxation()))
    assert all(c.separable(c.core_degrees(), c.class_sigma(*p[:3]), p[3]) == 241 for p in top)
    assert (0, 1, 5, (1, 1, 1, 1, 1, 1)) in top
    assert c.labelled_recount()["MAXIMUM"] == 241
    assert c.labelled_recount()["SIGMA_VECTORS"] == 2**10 * 4 * 6


def test_support_count_is_load_bearing_and_parity_is_not() -> None:
    assert c.relaxation_maximum(())[0] == 246
    assert c.relaxation_maximum(("PARITY",))[0] == 243
    assert c.relaxation_maximum(c.OPTIONAL_PREMISES)[0] == 241
    assert c.relaxation_maximum(c.OPTIONAL_PREMISES, erdos_gallai=True)[0] == 241
    with pytest.raises(AssertionError, match="unknown premise"):
        list(c.relaxation(("GRAPHICAL_K",)))


def test_a_claimed_cap_of_240_is_refuted() -> None:
    with patch.object(c, "PROPOSED_CAP", 240), pytest.raises(AssertionError, match="not 241"):
        c.theorem()


def test_closed_form_chain_reaches_the_closure_threshold() -> None:
    chain = c.closed_form_chain()
    assert chain["CAP"] == 249
    assert chain["CORE_TERMS"] == {
        "6": {"0": 0},
        "5": {"0": 0, "1": -1},
        "3": {"0": 0, "1": 1, "2": 4, "3": 9},
        "1": {str(s): s * (s + 2) for s in range(6)},
    }


def test_route_b_reproduces_old_row_and_proves_new_bound() -> None:
    old_terms, old = c.route_b(265)
    assert old == 313_398_248
    assert c.route_b(264)[1] == 313_389_480
    new_terms, new = c.route_b(241)
    assert new == 313_183_160 and new_terms == old_terms[: len(new_terms)]
    assert c.route_b(241, 0)[1] == new
    assert c.route_b(249)[1] == 313_254_856 <= c.INCUMBENT < c.route_b(250)[1] == 313_264_012


def test_route_b_rounding_is_rechecked_exactly() -> None:
    terms, _ = c.route_b(241)
    t, bound, *rest = terms[-1]
    for wrong in (bound - 1, bound + 1):
        with pytest.raises(AssertionError, match="exact arithmetic"):
            c.check_terms([*terms[:-1], (t, wrong, *rest)], 241, c.S4_BASE)


def test_supplemental_realization_obeys_the_chain() -> None:
    assert c.realization_check() == {
        "PROFILE_ID": c.TARGET_PROFILE,
        "T": 209,
        "D": 223,
        "P": 14,
        "R": 12,
    }
    with (
        patch.object(c, "REALIZATION_PAIRS", c.REALIZATION_PAIRS[:-1]),
        pytest.raises(AssertionError),
    ):
        c.realization_check()


def test_graph_check_refuses_a_d6_vertex_reaching_z() -> None:
    d = c.three.legal_degrees(c.REALIZATION_TRIPLES, c.REALIZATION_PAIRS)
    g = {
        c.t256.edge(x, y)
        for s in (*c.REALIZATION_TRIPLES, *c.REALIZATION_PAIRS)
        for x, y in combinations(s, 2)
    }
    core = [v for v in range(20) if d[v]]
    zero = [v for v in range(20) if not d[v]]
    assert d[0] == 6 and (0, 1) in g and (16, 18) in g and (0, 16) not in g and (1, 18) not in g
    swapped = (g - {(0, 1), (16, 18)}) | {(0, 16), (1, 18)}
    with pytest.raises(AssertionError, match="degree premises"):
        c.graph_check(core, zero, dict(enumerate(d)), swapped)


def test_random_graphs_never_exceed_the_cap() -> None:
    out = c.random_graphs(40, seed=7)
    assert out["GRAPHS_CHECKED"] == 40
    assert isinstance(out["MAX_T"], int) and out["MAX_T"] <= 241


def test_scope_claims(result: dict[str, object]) -> None:
    assert result["PROOF_SCOPE"] == "FULL_PROFILE"
    assert (result["NEW_T_CAP"], result["NEW_ADMISSIBLE_BOUND"]) == (241, 313_183_160)
    assert result["STRICT_OWNER_BOUND_REDUCTION"] == 313_398_248 - 313_183_160
    assert result["FAMILY_BOUND_REDUCTION_CLAIMED"] == "NO"
    assert result["OTHER_TIED_OWNERS_UNCHANGED"] == list(c.TIED_OWNERS[1:])
    assert result["GLOBAL_K20_OPTIMUM"] == "UNKNOWN"
    assert result["SOLVER_CALLS"] == 0
