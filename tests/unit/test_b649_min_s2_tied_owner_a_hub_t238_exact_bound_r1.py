"""Focused guards for the exact hub cap T<=238 of the tied row 66555555555441000000."""

from __future__ import annotations

from collections.abc import Sequence
from itertools import combinations
from unittest.mock import patch

import pytest

from lottolab.research import b649_min_s2_tied_owner_a_hub_t238_exact_bound_r1 as c


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
        "SEVEN_ROW_RESOLVED_BOUND": 313_395_448,
        "TIED_ROWS_AT_OLD_BOUND": ["66555555555441000000", "66555555555522000000"],
        "SEVEN_ROW_ROWS_ABOVE_TARGET": 8,
        "CURSOR": {"ID": "66544333333333332222", "BOUND": 313_394_584},
        "R30_REFINEMENT_CAPS": [268, 267, 266, 265],
    }
    assert (result["SOURCE_PROFILE_BOUND"], result["SOURCE_T_CAP"]) == (313_395_448, 265)
    assert result["SOURCE_S4_BASE"] == 112


def test_frozen_result_digest_and_cursor_are_enforced() -> None:
    with (
        patch.object(c, "FROZEN_RESULT_SHA256", "0" * 64),
        pytest.raises(AssertionError, match="seven-row result digest"),
    ):
        c.frozen_row()
    with (
        patch.object(c, "CURSOR_BOUND", 313_394_585),
        pytest.raises(AssertionError, match="as packeted"),
    ):
        c.frozen_row()


def test_premises_and_identity_with_e44() -> None:
    facts = c.premises()
    assert (facts["CORE_VERTICES"], facts["ZERO_VERTICES"]) == (14, 6)
    assert facts["CORE_DEGREE_CLASSES"] == {"6": 2, "5": 9, "4": 2, "1": 1}
    assert (facts["SUM_D"], facts["SUM_D_SQUARED"]) == (66, 330)
    assert facts["PHI_INCLUSION_EXCLUSION"] == facts["PHI_GOODMAN"] == 294
    assert (facts["CONSTANT"], facts["ZERO_GRAPH_CONSTANT"]) == (240, 168)
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
    with patch.object(c, "CONSTANT", 241), pytest.raises(AssertionError, match="e44"):
        c.identity_check()


def test_case_lemma_covers_every_graph_and_splits_k6_by_the_hub() -> None:
    lemma = c.case_lemma()
    assert lemma["CASE_CAPS"] == {"ISOLATED_ZERO": 216, "NO_ISOLATED_NOT_K6": 235, "K6": 238}
    assert lemma["CASE_GRAPH_COUNTS"] == {
        "ISOLATED_ZERO": 5319,
        "NO_ISOLATED_NOT_K6": 27448,
        "K6": 1,
    }
    assert 5319 + 27448 + 1 == 2**15
    assert (lemma["CORE_PART_MAX"], lemma["CORE_MINUS_R_MAX"]) == (48, 39)
    assert lemma["K6_CORE_PART_MAX_C_AT_MOST_4"] == 32
    assert lemma["K6_C5_POINTS_A_B_CORE_HUB_D_D_MINUS_HUB"] == [
        (0, [1, 0], 41, 1, 239, 238),
        (1, [0, 0], 40, 2, 238, 236),
    ]
    assert (lemma["ZERO_GRAPH_ONLY_CAP"], lemma["CAP"]) == (239, 238)
    assert [c.case_cap(g) for g in ((5,) * 6, (0, 4, 4, 2, 2, 0), (5, 5, 5, 5, 4, 4))] == [
        238,
        216,
        235,
    ]


def test_lemma_refuses_a_lower_k6_case_cap() -> None:
    wrong = {**c.CASE_CAPS, "K6": 237}
    with patch.object(c, "CASE_CAPS", wrong), pytest.raises(AssertionError, match="lemma"):
        c.case_lemma()


def test_hub_bound_on_the_k6_points() -> None:
    core = c.core_degrees()
    assert core == [6, 6, *[5] * 9, 4, 4, 1]
    assert c.hub_bound(core, c.class_sigma(0, (1, 0), 5)) == 1
    assert c.hub_bound(core, c.class_sigma(1, (0, 0), 5)) == 2
    assert c.hub_bound(core, c.class_sigma(0, (0, 0), 0)) == 0
    assert c.hub_bound(core[::-1], c.class_sigma(0, (1, 0), 5)[::-1]) == 1


def test_graph_degree_sequences_equal_erdos_gallai() -> None:
    graphic = c.graph_degree_sequences()
    assert len(graphic) == 102
    assert (5,) * 6 in graphic and (0,) * 6 in graphic
    assert (5, 5, 5, 5, 5, 1) not in graphic


def test_cap_238_full_relaxation_and_independent_recount() -> None:
    cap, top, count = c.relaxation_maximum()
    assert cap == c.PROPOSED_CAP == 238
    assert count == len(list(c.relaxation())) == 487
    assert top == [(0, (1, 0), 5, (1, 1, 1, 1, 1, 1))]
    recount = c.labelled_recount()
    assert recount["MAXIMUM"] == 238
    assert recount["SIGMA_VECTORS"] == 2**9 * 3**2 * 6
    assert recount["ZERO_GRAPHS"] == 2**15


def test_hub_is_load_bearing_and_parity_support_zero_graph_are_interchangeable() -> None:
    assert c.relaxation_maximum(())[0] == 241
    for single in ("PARITY", "SUPPORT_COUNT", c.ZERO_GRAPH):
        assert c.relaxation_maximum((single,))[0] == 239
        assert c.relaxation_maximum((single, c.HUB))[0] == 238
    assert c.relaxation_maximum((c.HUB,))[0] == 240
    assert c.relaxation_maximum(("PARITY", "SUPPORT_COUNT", c.ZERO_GRAPH))[0] == 239
    assert c.relaxation_maximum(c.OPTIONAL_PREMISES)[0] == 238
    with pytest.raises(AssertionError, match="unknown premise"):
        list(c.relaxation(("GRAPHICAL_K",)))


def test_a_claimed_cap_of_237_is_refuted() -> None:
    with patch.object(c, "PROPOSED_CAP", 237), pytest.raises(AssertionError, match="238"):
        c.theorem()


def test_witness_attains_238_exactly() -> None:
    triples, pairs = c.witness()
    assert len(triples) == 22 and len(pairs) == 27
    assert (0, 1, 13) in triples and not set(c.DOUBLE_STAR) & set(triples)
    assert c.realization_check() == {
        "PROFILE_ID": c.TARGET_PROFILE,
        "T": 238,
        "D": 239,
        "P": 1,
        "T_M": 1,
        "HUB_BOUND": 1,
        "R": 6,
        "CASE_CAP": 238,
    }
    with pytest.raises(AssertionError):
        c.realization_check(triples, pairs[:-1])


def test_hub_plus_one_is_refuted_by_the_witness() -> None:
    original = c.hub_bound

    def inflated(core: Sequence[int], sigma: Sequence[int]) -> int:
        return original(core, sigma) + 1

    with patch.object(c, "hub_bound", inflated), pytest.raises(AssertionError, match="hub lemma"):
        c.realization_check()


def test_graph_check_refuses_a_d6_vertex_reaching_z() -> None:
    triples, pairs = c.witness()
    d = c.three.legal_degrees(triples, pairs)
    g = {c.t256.edge(x, y) for s in (*triples, *pairs) for x, y in combinations(s, 2)}
    core = [v for v in range(20) if d[v]]
    zero = [v for v in range(20) if not d[v]]
    assert d[9] == 6 and (0, 9) in g and (14, 15) in g and (9, 14) not in g and (0, 15) not in g
    swapped = (g - {(0, 9), (14, 15)}) | {(9, 14), (0, 15)}
    with pytest.raises(AssertionError, match="degree premises"):
        c.graph_check(core, zero, dict(enumerate(d)), swapped)


def test_range_only_chains_already_meet_the_cursor_and_the_incumbent() -> None:
    chains = c.closed_form_chains()
    assert chains["CAPS"] == {"MINIMAL": 246, "CONVEXITY": 243}
    assert chains["AT_OR_BELOW_CURSOR_SUFFICIENT_CAP"] is True
    assert chains["AT_OR_BELOW_CLOSURE_THRESHOLD"] is True


def test_route_b_reproduces_old_row_and_proves_new_bound() -> None:
    old_terms, old = c.route_b(265)
    assert old == 313_395_448
    assert c.route_b(264)[1] == 313_386_680 <= c.CURSOR_BOUND < old
    new_terms, new = c.route_b(238)
    assert new == 313_153_668 and new_terms == old_terms[: len(new_terms)]
    assert c.route_b(238, 0)[1] == new
    assert c.route_b(239)[1] == 313_162_436
    assert c.route_b(250)[1] == 313_261_212 <= c.INCUMBENT < c.route_b(251)[1] == 313_269_980


def test_route_b_rounding_is_rechecked_exactly() -> None:
    terms, _ = c.route_b(238)
    t, bound, k4, contained, s4, s3 = terms[-1]
    for wrong in (bound - 1, bound + 1):
        with pytest.raises(AssertionError, match="exact arithmetic"):
            c.check_terms([*terms[:-1], (t, wrong, k4, contained, s4, s3)], 238, c.S4_BASE)


def test_random_graphs_never_exceed_the_cap() -> None:
    general = c.random_graphs(40, seed=7)
    binding = c.random_graphs(40, seed=7, binding=True)
    assert general["GRAPHS_CHECKED"] == binding["GRAPHS_CHECKED"] == 40
    assert isinstance(general["MAX_T"], int) and general["MAX_T"] <= 238
    assert binding["CASE_CAP_COUNTS"] == {"238": 40}
    assert isinstance(binding["MAX_T"], int) and binding["MAX_T"] <= 238


def test_scope_claims(result: dict[str, object]) -> None:
    assert result["PROOF_SCOPE"] == "FULL_PROFILE"
    assert (result["NEW_T_CAP"], result["NEW_ADMISSIBLE_BOUND"]) == (238, 313_153_668)
    assert result["NEW_T_CAP_EXACT"] is True
    assert result["SUFFICIENT_CAP_FOR_CURSOR"] == 264
    assert result["OWNER_BOUND_REDUCTION"] == 313_395_448 - 313_153_668
    assert result["BOUND_BELOW_CURSOR"] is True
    assert result["OWNER_EXCLUSION_PROVED"] is True
    assert result["FAMILY_BOUND_GAIN_CLAIMED"] == 0
    assert result["NEW_WINNING_OUTCOMES"] == 0
    assert result["TIED_PARTNER_UNCHANGED"] == "66555555555522000000"
    assert result["GLOBAL_K20_OPTIMUM"] == "UNKNOWN"
    assert result["FAMILY_AUTHORITY_UPDATED"] == "NO"
    assert result["SOLVER_CALLS"] == 0
