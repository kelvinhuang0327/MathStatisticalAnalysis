"""Deterministic proof, boundary and falsifiability checks for the T264 cell."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import replace
from fractions import Fraction

import pytest

from lottolab.research import b649_min_s2_next_owner_t264_s4_cert_r1 as x


@pytest.fixture(scope="module")
def result() -> dict[str, object]:
    return x.compute_result()


def test_exact_sealed_result_reproduces(result: Mapping[str, object]) -> None:
    assert x.render(result) == x.RESULT_PATH.read_bytes()
    assert result["T264_S4_LOWER_BOUND"] == 308_560
    assert result["T264_UPPER_BOUND"] == 313_388_344
    assert result["FULL_PROFILE_UPPER_BOUND"] == 313_392_308
    assert result["FULL_PROFILE_ARGMAX_T"] == 263
    assert result["PROFILE_BOUND_BEFORE"] == 313_401_464
    assert result["CERTIFICATE_SCOPE"] == "TARGET_PROFILE_T264_ONLY"
    assert result["FAMILY_BOUND_AUTHORITY_PRODUCED"] is False


def test_all_local_types_are_complete_and_official(result: Mapping[str, object]) -> None:
    local = x.object_row(result["LOCAL_QUARTET_CHECK"])
    assert local["PATTERNS_CHECKED"] == 64 + 4 * 8
    assert local["WEIGHTS"] == [0, 112, 448, 679]
    # Named load-bearing types independently pin the combinatorial table.
    claw, _ = x.local_pattern(0b000111, None)
    assert (claw.k, claw.j, claw.r, claw.c, claw.s4) == (0, 1, 3, 1, 0)
    diamond, _ = x.local_pattern(63 ^ (1 << 5), (0, 1, 2))
    assert (diamond.j, diamond.r, diamond.d1, diamond.s4) == (2, 2, 1, 0)
    core_k4, _ = x.local_pattern(63, (0, 1, 2))
    assert (core_k4.k, core_k4.a, core_k4.s4) == (1, 1, 448)


def test_quartet_identity_detects_missing_claw_correction(monkeypatch: pytest.MonkeyPatch) -> None:
    original = x.Incidence.s4.fget
    assert original is not None
    monkeypatch.setattr(x.Incidence, "s4", property(lambda c: original(c) - 56 * c.c))
    with pytest.raises(AssertionError, match="quartet identity"):
        x.verify_local_identity()


def test_profile_identities_and_rounding() -> None:
    q = x.target_inequalities()
    assert (q["W"], q["J"], q["OPEN_WEDGES"], q["R_MAX"], q["K_MIN"], q["B"]) == (
        833,
        2366,
        41,
        410,
        489,
        604,
    )
    assert q["K_MIN"] == -(-(q["J"] - q["R_MAX"]) // 4)
    assert q["S4_LOWER_BOUND"] == 231 * 489 + 112 * 2366 - 56 * 410 - 46_431


def test_capacity_loss_exhausts_the_actual_integer_relaxation() -> None:
    loss, a, d1, p1 = x.maximum_loss(604)
    assert (loss, a, d1, p1) == (46_431, 201, 0, 1)
    for aa in range(604 // 3 + 1):
        for dd in range((604 - 3 * aa) // 2 + 1):
            pp = 604 - 3 * aa - 2 * dd
            assert pp >= 0
            assert 231 * aa + 112 * dd <= loss
    # Both branches are needed: the near-maximal A=200 branch misses by only 7.
    assert loss - 7 == 231 * 200 + 112 * 2


def test_false_capacity_loss_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    def false_loss(_capacity: int) -> tuple[int, int, int, int]:
        return 46_424, 200, 2, 0

    monkeypatch.setattr(x, "maximum_loss", false_loss)
    with pytest.raises(AssertionError, match="loss proof"):
        x.target_inequalities()


@pytest.mark.parametrize("bad_floor", [488, 490])
def test_wrong_k4_ceilings_are_rejected(monkeypatch: pytest.MonkeyPatch, bad_floor: int) -> None:
    def false_floor(_degrees: Sequence[int], _open_wedges: int) -> int:
        return bad_floor

    monkeypatch.setattr(x.r32.r30, "k4_lower_bound", false_floor)
    with pytest.raises(AssertionError, match="K4 ceiling"):
        x.target_inequalities()


def test_relaxation_boundary_attains_floor_without_claiming_realizability() -> None:
    boundary = x.Incidence(k=489, j=2366, r=410, a=201, d1=0, c=0, p1=1)
    assert x.verify_target_counts(boundary) == 308_560
    second_branch = replace(boundary, a=200, d1=2, p1=0)
    assert x.verify_target_counts(second_branch) == 308_567


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("k", 488, "K lower bound"),
        ("j", 2365, "J identity"),
        ("r", 411, "R upper bound"),
        ("a", 202, "core capacity"),
        ("d1", 1, "core capacity"),
        ("p1", 0, "core capacity"),
        ("p1", -1, "negative/noninteger"),
        ("c", -1, "negative/noninteger"),
        ("c", True, "negative/noninteger"),
    ],
)
def test_actual_load_bearing_inequalities_reject_counterinputs(
    field: str,
    value: int,
    reason: str,
) -> None:
    boundary = x.Incidence(k=489, j=2366, r=410, a=201, d1=0, c=0, p1=1)
    bad = replace(boundary, **{field: value})
    with pytest.raises(AssertionError, match=reason):
        x.verify_target_counts(bad)


@pytest.mark.parametrize("triangles", [22, 263, 265, 266])
def test_no_new_inequality_outside_t264(triangles: int) -> None:
    with pytest.raises(ValueError, match="scope"):
        x.target_inequalities(triangles=triangles)


def test_no_new_inequality_for_other_profile() -> None:
    with pytest.raises(ValueError, match="scope"):
        x.target_inequalities(tuple(map(int, "66666555555311100000")))


def test_lower_t_envelope_is_preserved(result: Mapping[str, object]) -> None:
    before, after, q = x.profile_envelope()
    assert len(before) == len(after) == 243
    assert [t[0] for t in after] == list(range(22, 265))
    assert before[:-1] == after[:-1]
    assert before[-1][4] == 285_600
    assert after[-1][4] == q["S4_LOWER_BOUND"]
    assert max(before[:-1], key=lambda t: t[1]) == (263, 313392308, 482, 201, 280847, 5162752)
    assert result["LOWER_T_TERMS_SHA256"] == x.sha256(
        json.dumps(before[:-1], separators=(",", ":")).encode()
    )
    for _t, bound, _k, _a, s4, s3 in after:
        exact = x.r32.K20_S1 - x.r32.K20_S2 + s3 - Fraction(4 * s4, 7)
        assert bound == -(-exact.numerator // exact.denominator)


@pytest.mark.parametrize(
    ("key", "bad"),
    [
        ("STATUS", "FEASIBLE"),
        ("STATUS", "UNKNOWN"),
        ("PROFILE_IDS", ["66666555555311100000"]),
        ("CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND", 266),
        ("REFUTED_GRAPH_TRIANGLE_COUNT", 266),
        ("OPEN_WEDGE_CEILING_REFUTED", 39),
        ("ROUTE", "NB_CAP_266"),
        ("ATTEMPT_INDEX", 2780),
        ("WEDGE_COUNT", 834),
    ],
)
def test_cap_identity_fails_closed(
    result: Mapping[str, object],
    key: str,
    bad: object,
) -> None:
    proof = dict(x.object_row(result["R30_ATTEMPT"]))
    proof[key] = bad
    with pytest.raises(AssertionError):
        x.cap_identity(proof)


def test_supersession_audit_fails_closed() -> None:
    with pytest.raises(AssertionError, match="already supersedes"):
        x.reject_superseding_rows(
            {"PROFILE_ID": x.TARGET_PROFILE, "CURRENT_BOUND": 313_392_000},
            313_392_308,
        )
    with pytest.raises(AssertionError, match="stricter cap"):
        x.reject_superseding_rows(
            {
                "PROFILE_IDS": [x.TARGET_PROFILE],
                "STATUS": "INFEASIBLE",
                "CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND": 263,
            },
            313_392_308,
        )
    x.reject_superseding_rows({"PROFILE_ID": "another", "CURRENT_BOUND": 1}, 313_392_308)


@pytest.mark.parametrize("mask,core", [(-1, None), (64, None), (0, (0, 1, 2)), (63, (0, 1, 4))])
def test_illegal_local_support_is_rejected(mask: int, core: tuple[int, ...] | None) -> None:
    with pytest.raises(ValueError):
        x.local_pattern(mask, core)
