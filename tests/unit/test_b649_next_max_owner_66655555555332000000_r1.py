"""Focused, falsifiable guards for the single-profile contained-triple restriction."""

from __future__ import annotations

import json
from itertools import combinations
from unittest.mock import patch

import pytest

from lottolab.research import b649_next_max_owner_66655555555332000000_r1 as c


@pytest.fixture(scope="module")
def result() -> dict[str, object]:
    return c.compute_result()


def test_result_reproduces_committed_json(result: dict[str, object]) -> None:
    stored = c.obj(json.loads(c.RESULT_PATH.read_bytes()))
    # Validation is observed after execution; it is separate from the scientific payload.
    stored.pop("VALIDATION", None)
    assert c.render(stored) == c.render(result)


def test_source_target_row_is_bound_to_frozen_lineage(result: dict[str, object]) -> None:
    row = c.obj(result["SOURCE_ROW"])
    assert (row["BOUND"], row["TRIANGLE_CAP"], row["S4_BASE"]) == (313395060, 265, 112)
    assert row["SOURCE"] == c.SOURCE_LOCATOR
    assert c.obj(row["FROZEN_LINEAGE_TARGET_REPLAY"])["realization"] is None


def test_prior_art_is_reused_not_claimed_as_new() -> None:
    cert = c.prior_cap()
    assert (cert["COUNT"], cert["MAX_F"]) == (428, 228)
    assert cert["STATUS"] == "EXISTING_PROOF_REUSED"
    maxima = c.array(cert["ARGMAX"])
    assert len(maxima) == 2
    assert maxima[0] == {"SIGMA": [0] * 12 + [2, 4], "ZETA": [1] * 6, "F": 228}
    assert all(c.obj(row)["F"] == 228 for row in maxima)


def test_complete_low_incidence_relaxation_and_analytic_cap() -> None:
    cert = c.contained_certificate()
    reduced = c.obj(cert["RELAXATION"])
    assert cert["CAP"] == 187
    assert reduced["BOX_SIZE"] == 5184
    assert reduced["MIN_LOSS"] == 12
    # Verify every optimum's incidences and pair multiplicities directly.
    for raw in c.array(reduced["ARGMIN"]):
        counts = c.array(raw)
        assert all(type(n) is int for n in counts)
        seq = [int(str(n)) for n in counts]
        assert [
            sum(n for n, p in zip(seq, c.LOW_PATTERNS, strict=True) if v in p) for v in range(3)
        ] == [3, 3, 2]
        assert all(
            sum(n for n, p in zip(seq, c.LOW_PATTERNS, strict=True) if set(pair) <= set(p)) <= 1
            for pair in combinations(range(3), 2)
        )


def test_pair_linearity_removal_is_a_real_countermodel() -> None:
    relaxed = c.low_relaxation(False)
    assert (relaxed["MIN_LOSS"], relaxed["CONTAINED_CAP"]) == (8, 191)
    # Two ABC blocks and one AB block have the correct (3,3,2) incidences,
    # but reuse low ticket pairs and invalidate the claimed loss 12.
    assert [0, 0, 0, 1, 0, 0, 2] in c.array(relaxed["ARGMIN"])
    with pytest.raises(AssertionError, match="linearity premise removed"):
        c.contained_certificate(linear=False)
    with (
        patch.object(c, "low_relaxation", return_value=relaxed),
        pytest.raises(AssertionError, match="loss lemma"),
    ):
        c.contained_certificate()


@pytest.mark.parametrize("claim", [186, 188])
def test_wrong_contained_cap_rejected(claim: int) -> None:
    with pytest.raises(AssertionError, match="wrong contained cap"):
        c.contained_certificate(claim)


@pytest.mark.parametrize("claim", [227, 229])
def test_wrong_triangle_cap_rejected(claim: int) -> None:
    with pytest.raises(AssertionError, match="wrong T cap"):
        c.prior_cap(claim)


def test_wrong_profile_rejected() -> None:
    with pytest.raises(AssertionError, match="wrong profile"):
        c.validate_profile(tuple(map(int, "66655555555421100000")))
    with pytest.raises(AssertionError, match="wrong profile"):
        c.validate_profile([6.0, *c.PROFILE[1:]])  # type: ignore[arg-type]


@pytest.mark.parametrize("support", [(0, 0, 1), (0, 1, 20), (0, 1, -1)])
def test_illegal_support_vertices_rejected(support: c.Support) -> None:
    with pytest.raises(AssertionError, match="illegal support vertices"):
        c.validate_support([support] * 22, [(0, 1)] * 27)


def test_repeated_ticket_pair_rejected() -> None:
    with pytest.raises(AssertionError, match="repeated ticket pair"):
        c.validate_support([(0, 1, 2), (0, 1, 3)] + [(4, 5, 6)] * 20, [(7, 8)] * 27)


def test_support_count_premise_rejected() -> None:
    with pytest.raises(AssertionError, match="support counts"):
        c.validate_support([], [])


def test_goodman_and_remainder_are_exact_cardinality_identities() -> None:
    assert c.goodman()["CONSTANT"] == 294
    edges = list(combinations(range(5), 2))
    positive = 0
    # Every simple graph on this small partition; supplemental identity QA only.
    for mask in range(1 << len(edges)):
        g = {edge for bit, edge in enumerate(edges) if mask & (1 << bit)}
        seen = c.graph_identity([0, 1, 2], [3, 4], g)
        assert seen["T_H"] == seen["BARE"] + seen["P"]
        assert seen["P"] >= 0
        positive += seen["P"] > 0
    assert positive > 0
    complete = c.graph_identity(list(range(14)), list(range(14, 20)), set())
    assert complete["P"] > 0 and complete["T_H"] != complete["BARE"]


def test_route_b_sufficient_boundary_and_all_integer_terms(result: dict[str, object]) -> None:
    assert c.maximum_sufficient_cap(198) == 264
    assert c.maximum_sufficient_cap(187) == 265
    assert c.route_b(264, 198)[1][1] <= c.NEXT_COMPETITOR < c.route_b(265, 198)[1][1]
    assert c.route_b(265, 187)[1][1] <= c.NEXT_COMPETITOR < c.route_b(266, 187)[1][1]
    terms, best = c.route_b(228, 187)
    assert [t[0] for t in terms] == list(range(22, 229))
    assert terms == c.route_b(265, 187)[0][:207]
    assert best == (228, 313062208, 221, 187, 106862, 4733232)
    assert result["OWNER_BOUND_REDUCTION"] == 332852
    assert result["NEW_RESTRICTION_ONLY_REDUCTION"] == 1452
    assert result["NOVEL_RESTRICTION_GAIN_AT_PRIOR_CAP"] == 1452
    assert result["FAMILY_GAIN_CLAIMED"] == result["NEW_WINNING_OUTCOMES"] == 0


@pytest.mark.parametrize("name", ["FROZEN_SHA", "SIX_SHA", "ARCHIVE_SHA", "PRIOR_SHA", "ROUTE_SHA"])
def test_wrong_source_sha_rejected(name: str) -> None:
    with patch.object(c, name, "0" * 64), pytest.raises(AssertionError, match="source SHA"):
        c.source_authority()


@pytest.mark.parametrize(
    "name,value,message",
    [
        ("FROZEN_TREE", "0" * 40, "tree mismatch"),
        ("SOURCE_CAP", 264, "row/cap mismatch"),
        ("S4_BASE", 113, "S4 base mismatch"),
    ],
)
def test_wrong_authority_premise_rejected(name: str, value: object, message: str) -> None:
    with patch.object(c, name, value), pytest.raises(AssertionError, match=message):
        c.source_authority()


def test_corrupt_prior_objective_is_detected() -> None:
    original = list(c.prior.degree_configurations(c.PROFILE))
    from dataclasses import replace

    mutated = [replace(original[0], f=original[0].f + 1), *original[1:]]
    with (
        patch.object(c.prior, "degree_configurations", return_value=iter(mutated)),
        pytest.raises(AssertionError, match="identity mismatch"),
    ):
        c.prior_cap()
