"""Focused tests: the T<=257 proof, its witness, Route B and the three-row ledger."""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import replace
from unittest.mock import patch

import pytest

from lottolab.research import b649_min_s2_core_zero_t257_three_row_cert_r1 as c

Snapshot = tuple[dict[str, c.Row], dict[str, object], dict[str, str]]


@pytest.fixture(scope="module")
def snapshot() -> Snapshot:
    return c.two.baseline()


@pytest.fixture(scope="module")
def derived(snapshot: Snapshot) -> Iterator[dict[str, object]]:
    # The replay is expensive; share its genuine output and keep every other check live.
    with patch.object(c.two, "baseline", return_value=snapshot):
        yield c.compute_result()


@pytest.fixture(scope="module")
def two_row(snapshot: Snapshot) -> Iterator[dict[str, c.Row]]:
    with patch.object(c.two, "baseline", return_value=snapshot):
        yield c.two_row_ledger(c.pinned_two_row()[0])[1]


def test_addendum_audit_is_caveat_metadata_only() -> None:
    final, audit = c.pinned_two_row()
    assert audit["RESULT_KEYS_ADDED"] == ["PRIOR_COMBINED_FRESH_JUDGE"]
    assert audit["B_IDENTITY_KEYS_CHANGED"] == ["JUDGE_CAVEATS_TEXT"]
    assert audit["PRIOR_JUDGE_REVIEWED_FINAL_TREE"] is False
    assert c.object_row(final["CERTIFICATE_B_IDENTITY"])["JUDGE_STATUS"] == "VERIFIED_WITH_CAVEATS"
    with patch.object(c, "JUDGED_TREE", "0" * 40), pytest.raises(AssertionError, match="tree"):
        c.pinned_two_row()
    altered = (*c.two.B_WORKER_CAVEATS[:2], "a different caveat")
    with (
        patch.object(c.two, "B_WORKER_CAVEATS", altered),
        pytest.raises(AssertionError, match="caveat metadata only"),
    ):
        c.pinned_two_row()


def test_theorem_cap_and_equality_conditions() -> None:
    theorem = c.core_zero_theorem(c.C_PROFILE)
    assert theorem["STATUS"] == "PROVEN"
    assert theorem["TRIANGLE_CAP"] == 257
    assert theorem["IDENTITY_POINTS_CHECKED"] == 1 + 2 * 20
    assert theorem["SIGMA_RANGES"] == {"6": [0], "5": [0, 1], "4": [0, 1, 2]}
    assert theorem["EQUALITY_CONDITIONS"] == {
        "CORE_SIGMA": {"6": [0], "5": [0], "4": [0, 2]},
        "ZERO_ZETA": [0, 6],
        "P": 0,
    }


def test_theorem_does_not_transfer_to_another_profile() -> None:
    with pytest.raises(AssertionError, match="one profile only"):
        c.core_zero_theorem("66665555555421000000")


@pytest.mark.parametrize(
    ("name", "value", "message"),
    [
        ("CORE_TERM_CONSTANT", 3, "split identity"),
        ("ZERO_TERM_CONSTANT", 5, "split identity"),
        ("PROPOSED_CAP", 256, "split identity"),
    ],
)
def test_mutated_identity_rejected(name: str, value: int, message: str) -> None:
    with patch.object(c, name, value), pytest.raises(AssertionError, match=message):
        c.core_zero_theorem(c.C_PROFILE)


def test_identity_points_fix_every_separable_quadratic() -> None:
    points = c.identity_points(13, 7)
    assert len(points) == len(set(points)) == 41
    flat = [(*s, *z) for s, z in points]
    for i in range(20):
        assert {v[i] for v in flat if sum(v) == v[i]} == {0, 1, 2}


def test_witness_is_legal_and_attains_257() -> None:
    triples, pairs = c.witness()
    assert len(c.sts13_blocks()) == 26
    assert set(c.REMOVED_BLOCKS) <= set(c.sts13_blocks())
    seen = c.realization_split(triples, pairs)
    assert (seen["PROFILE_ID"], seen["TRIANGLES"], seen["F"]) == (c.C_PROFILE, 257, 257)
    assert seen["P_TERMS"] == [0, 0, 0, 0] and seen["R"] == 0


@pytest.mark.parametrize(
    "mutation", ["shadow_pair", "duplicate_pair", "missing_pair", "overfull_ticket"]
)
def test_illegal_structures_rejected(mutation: str) -> None:
    triples, pairs = c.witness()
    bad = list(pairs)
    if mutation == "shadow_pair":
        bad[0] = (0, 3)
    elif mutation == "duplicate_pair":
        bad[0] = bad[1]
    elif mutation == "missing_pair":
        bad.pop()
    else:
        bad[-1] = (1, 19)
    with pytest.raises(AssertionError):
        c.legal_degrees(triples, bad)
    with pytest.raises(ValueError):
        c.r5.validate_k20_support_realization(triples, bad, c.legal_degrees(triples, pairs))


def test_route_b_exact_prefix() -> None:
    old, old_bound = c.route_b(264)
    new, new_bound = c.route_b(257)
    assert old_bound == 313401852
    assert new_bound == 313339312 == new[-1][1]
    assert new == old[: len(new)]


def test_three_row_family(derived: dict[str, object]) -> None:
    assert derived["EXPECTED_VALUES_MATCH"] is True
    assert derived["PROFILE_BOUND_AFTER"] == 313339312
    assert derived["FAMILY_BOUND_AFTER"] == 313401464
    assert derived["DELTA_VS_TWO_ROW"] == 388
    assert derived["DELTA_VS_ORIGINAL"] == 2544
    assert derived["NEW_FAMILY_OWNER"] == ["66665555555421000000"]
    assert derived["GAP_TO_INCUMBENT"] == 137576
    assert derived["LEDGER_ROWS"] == 4647
    assert derived["CERTIFICATES_COMPOSED"] == 3
    assert derived["ROWS_CHANGED_VS_ORIGINAL"] == sorted(
        (c.two.A_PROFILE, c.two.B_PROFILE, c.C_PROFILE)
    )
    assert derived["CERTIFICATE_B_JUDGE_STATUS"] == "VERIFIED_WITH_CAVEATS"
    assert derived["CERTIFICATE_B_CAVEATS"] == list(c.two.B_WORKER_CAVEATS)
    assert derived["CERTIFICATE_B_CAVEATS_SOURCE"] == "OWNER_SUPPLIED_ORIGINAL_WORKER_REPORT"
    assert derived["GLOBAL_K20_OPTIMUM"] == "UNKNOWN"
    recorded = c.object_row(derived["RECORDED_ROW_REALIZATION"])
    assert c.integer(recorded["TRIANGLES"]) <= 257


def test_independent_family_recount(two_row: dict[str, c.Row]) -> None:
    manual = {p: r.bound for p, r in two_row.items()}
    manual[c.C_PROFILE] = 313339312
    manual[c.chase.prior.CURSOR_ID] = c.chase.prior.CURSOR_BOUND
    best = max(manual.values())
    assert best == 313401464
    assert [p for p, b in manual.items() if b == best] == ["66665555555421000000"]


def test_exactly_one_extra_row_and_two_preserved(two_row: dict[str, c.Row]) -> None:
    after = c.apply_third(two_row, 313339312, 257, "test")
    assert [p for p in two_row if two_row[p] != after[p]] == [c.C_PROFILE]
    assert after[c.C_PROFILE].s4_base == c.S4_BASE
    assert after[c.C_PROFILE].realization == two_row[c.C_PROFILE].realization
    for pid in (c.two.A_PROFILE, c.two.B_PROFILE):
        assert after[pid] == two_row[pid]


@pytest.mark.parametrize(("bound", "cap"), [(313401852, 257), (313339312, 264), (313339312, 21)])
def test_non_tightening_third_update_rejected(
    two_row: dict[str, c.Row], bound: int, cap: int
) -> None:
    with pytest.raises(AssertionError, match="does not tighten"):
        c.apply_third(two_row, bound, cap, "test")


def test_wrong_row_authority_rejected(two_row: dict[str, c.Row]) -> None:
    altered = dict(two_row)
    altered[c.C_PROFILE] = replace(two_row[c.C_PROFILE], s4_base=112)
    with pytest.raises(AssertionError, match="does not tighten"):
        c.apply_third(altered, 313339312, 257, "test")


def test_cursor_can_own_the_family() -> None:
    cursor = c.chase.prior.CURSOR_BOUND
    row = c.Row(cursor - 1, 257, 1680, "fixture")
    assert c.family({c.C_PROFILE: row, c.two.A_PROFILE: replace(row, bound=cursor - 2)}) == (
        cursor,
        [c.chase.prior.CURSOR_ID],
        cursor - 1,
    )


def test_content_address_and_no_search(
    derived: dict[str, object], snapshot: Snapshot, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = c.two.render(derived)
    path = c.ROOT / c.two.RESULT_DIRECTORY / f"{c.RESULT_STEM}-{c.sha256(payload)}.json"
    assert path.read_bytes() == payload
    assert json.loads(payload)["SOLVER_CALLS"] == 0

    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("certificate invoked a search entrypoint")

    monkeypatch.setattr(c.two, "baseline", lambda: snapshot)
    monkeypatch.setattr(c.chase, "chase", forbidden)
    monkeypatch.setattr(c.chase, "refine", forbidden)
    assert c.compute_result() == derived
