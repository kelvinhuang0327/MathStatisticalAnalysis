"""Focused guards for the zero-graph T<=240 cap of the tied owner 66655555554441000000."""

from __future__ import annotations

from itertools import combinations
from unittest.mock import patch

import pytest

from lottolab.research import b649_min_s2_tied_owner_zero_graph_t240_bound_r1 as c


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
    assert (result["SOURCE_PROFILE_BOUND"], result["SOURCE_T_CAP"]) == (313_398_248, 265)
    assert result["SOURCE_S4_BASE"] == 112


def test_frozen_result_digest_is_enforced() -> None:
    with (
        patch.object(c, "FROZEN_RESULT_SHA256", "0" * 64),
        pytest.raises(AssertionError, match="seven-row result digest"),
    ):
        c.frozen_row()


def test_premises_and_identity_with_e44() -> None:
    facts = c.premises()
    assert (facts["CORE_VERTICES"], facts["ZERO_VERTICES"]) == (14, 6)
    assert facts["CORE_DEGREE_CLASSES"] == {"6": 3, "5": 7, "4": 3, "1": 1}
    assert facts["PHI_INCLUSION_EXCLUSION"] == facts["PHI_GOODMAN"] == 295
    assert (facts["CONSTANT"], facts["ZERO_GRAPH_CONSTANT"]) == (241, 169)
    identity = c.identity_check()
    assert identity["E44_IDENTITY_POINTS_CHECKED"] == 1 + 2 * 20 + 190
    assert identity["SIGMA_RANGES"] == {
        "6": [0],
        "5": [0, 1],
        "4": [0, 1, 2],
        "1": list(range(6)),
    }
    assert identity["CORE_TERMS"] == {
        "6": {"0": 0},
        "5": {"0": 0, "1": 0},
        "4": {"0": 0, "1": 1, "2": 4},
        "1": {str(s): s * (s + 3) for s in range(6)},
    }


def test_wrong_constant_is_refuted_by_the_e44_identity() -> None:
    with patch.object(c, "CONSTANT", 240), pytest.raises(AssertionError, match="e44"):
        c.identity_check()


def test_zero_graph_lemma_cases_cover_every_graph() -> None:
    lemma = c.zero_graph_lemma()
    assert lemma["CASE_CAPS"] == {"ISOLATED_ZERO": 221, "NO_ISOLATED_NOT_K6": 238, "K6": 240}
    assert lemma["CASE_GRAPH_COUNTS"] == {
        "ISOLATED_ZERO": 5319,
        "NO_ISOLATED_NOT_K6": 27448,
        "K6": 1,
    }
    assert 5319 + 27448 + 1 == 2**15
    assert (lemma["CORE_PART_MAX"], lemma["CORE_MINUS_R_MAX"]) == (52, 41)
    assert lemma["CORE_PART_MAX_AT_R6"] == 41
    assert lemma["CAP"] == 240
    assert [c.case_cap(g) for g in ((5,) * 6, (0, 4, 4, 2, 2, 0), (5, 5, 5, 5, 4, 4))] == [
        240,
        221,
        238,
    ]


def test_lemma_refuses_a_lower_k6_case_cap() -> None:
    wrong = {**c.CASE_CAPS, "K6": 239}
    with patch.object(c, "CASE_CAPS", wrong), pytest.raises(AssertionError, match="lemma"):
        c.zero_graph_lemma()


def test_graph_degree_sequences_equal_erdos_gallai_and_exclude_the_support_argmax() -> None:
    graphic = c.graph_degree_sequences()
    assert len(graphic) == 102
    assert (5,) * 6 in graphic and (0,) * 6 in graphic
    assert (5, 5, 5, 5, 0, 0) not in graphic
    _, top, _ = c.relaxation_maximum(("SUPPORT_COUNT",))
    assert top == [(5, (2, 2, 2), 5, (6, 6, 1, 1, 1, 1))]


def test_cap_240_full_relaxation_and_independent_recount() -> None:
    cap, top, count = c.relaxation_maximum()
    assert cap == c.PROPOSED_CAP == 240
    assert count == len(list(c.relaxation()))
    assert top == [(0, (1, 0, 0), 5, (1, 1, 1, 1, 1, 1))]
    recount = c.labelled_recount()
    assert recount["MAXIMUM"] == 240
    assert recount["SIGMA_VECTORS"] == 2**7 * 3**3 * 6
    assert recount["ZERO_GRAPHS"] == 2**15


def test_zero_graph_is_load_bearing_and_parity_and_support_are_not() -> None:
    assert c.relaxation_maximum(())[0] == 246
    assert c.relaxation_maximum(("PARITY",))[0] == 241
    assert c.relaxation_maximum(("SUPPORT_COUNT",))[0] == 241
    assert c.relaxation_maximum(("PARITY", "SUPPORT_COUNT"))[0] == 241
    assert c.relaxation_maximum(c.OPTIONAL_PREMISES)[0] == 240
    with pytest.raises(AssertionError, match="unknown premise"):
        list(c.relaxation(("GRAPHICAL_K",)))


def test_a_claimed_cap_of_239_is_refuted() -> None:
    with patch.object(c, "PROPOSED_CAP", 239), pytest.raises(AssertionError, match="240"):
        c.theorem()


def test_range_only_chain_is_already_below_the_closure_threshold() -> None:
    chain = c.closed_form_chain()
    assert chain["CAP"] == 246 and chain["BELOW_CLOSURE_THRESHOLD"] is True
    assert chain["CORE_TERMS"] == {
        "6": {"0": 0},
        "5": {"0": 0, "1": -1},
        "4": {"0": 0, "1": 0, "2": 2},
        "1": {str(s): s * (s + 2) for s in range(6)},
    }


def test_route_b_reproduces_old_row_and_proves_new_bound() -> None:
    old_terms, old = c.route_b(265)
    assert old == 313_398_248
    assert c.route_b(264)[1] == 313_389_480
    new_terms, new = c.route_b(240)
    assert new == 313_174_392 and new_terms == old_terms[: len(new_terms)]
    assert c.route_b(240, 0)[1] == new
    assert c.route_b(246)[1] == 313_228_164 <= c.INCUMBENT
    assert c.route_b(249)[1] == 313_254_856 <= c.INCUMBENT < c.route_b(250)[1] == 313_264_012


def test_route_b_rounding_is_rechecked_exactly() -> None:
    terms, _ = c.route_b(240)
    t, bound, k4, contained, s4, s3 = terms[-1]
    for wrong in (bound - 1, bound + 1):
        with pytest.raises(AssertionError, match="exact arithmetic"):
            c.check_terms([*terms[:-1], (t, wrong, k4, contained, s4, s3)], 240, c.S4_BASE)


def test_supplemental_realizations_obey_the_chain() -> None:
    assert c.realization_check() == {
        "PROFILE_ID": c.TARGET_PROFILE,
        "T": 194,
        "D": 205,
        "P": 11,
        "R": 12,
        "CASE_CAP": 238,
    }
    assert c.realization_check(c.K6_TRIPLES, c.K6_PAIRS) == {
        "PROFILE_ID": c.TARGET_PROFILE,
        "T": 237,
        "D": 240,
        "P": 3,
        "R": 6,
        "CASE_CAP": 240,
    }
    with pytest.raises(AssertionError):
        c.realization_check(c.REALIZATION_TRIPLES, c.REALIZATION_PAIRS[:-1])


def test_graph_check_refuses_a_d6_vertex_reaching_z() -> None:
    d = c.three.legal_degrees(c.REALIZATION_TRIPLES, c.REALIZATION_PAIRS)
    g = {
        c.t256.edge(x, y)
        for s in (*c.REALIZATION_TRIPLES, *c.REALIZATION_PAIRS)
        for x, y in combinations(s, 2)
    }
    core = [v for v in range(20) if d[v]]
    zero = [v for v in range(20) if not d[v]]
    assert d[0] == 6 and (0, 1) in g and (16, 19) in g and (0, 16) not in g and (1, 19) not in g
    swapped = (g - {(0, 1), (16, 19)}) | {(0, 16), (1, 19)}
    with pytest.raises(AssertionError, match="degree premises"):
        c.graph_check(core, zero, dict(enumerate(d)), swapped)


def test_random_graphs_never_exceed_the_cap() -> None:
    out = c.random_graphs(40, seed=7)
    assert out["GRAPHS_CHECKED"] == 40
    assert isinstance(out["MAX_T"], int) and out["MAX_T"] <= 240


def test_scope_claims(result: dict[str, object]) -> None:
    assert result["PROOF_SCOPE"] == "FULL_PROFILE"
    assert (result["NEW_T_CAP"], result["NEW_ADMISSIBLE_BOUND"]) == (240, 313_174_392)
    assert result["STRICT_OWNER_BOUND_DELTA"] == 313_398_248 - 313_174_392
    assert result["OWNER_EXCLUSION_PROVED"] is True
    assert result["FAMILY_BOUND_DELTA_CLAIMED"] == 0
    assert result["NEW_STRICT_WINNING_OUTCOMES"] == 0
    assert result["OTHER_TIED_OWNERS_UNCHANGED"] == [c.TIED_OWNERS[0], c.TIED_OWNERS[2]]
    assert result["GLOBAL_K20_OPTIMUM"] == "UNKNOWN"
    assert result["SOLVER_CALLS"] == 0
