"""Focused scientific checks and falsifiable negative gates for the target only."""

from __future__ import annotations

import copy
import inspect
import json
from collections.abc import Callable
from fractions import Fraction
from itertools import combinations
from math import comb
from typing import cast

import pytest

from lottolab.research import b649_min_s2_bonferroni5_target_cert_r1 as x


@pytest.fixture(scope="module")
def result() -> dict[str, object]:
    return x.compute_result()


def test_donor_exact_source_result_and_disposition(result: dict[str, object]) -> None:
    assert result["DONOR_HEAD"] == "e3a9843db4339167bffcdc92fb782ff6bb663ed8"
    assert result["DONOR_TREE"] == "f63545acbc883f13ec9c50eea0b3a7e6a2190d3b"
    assert result["DONOR_ORIGINAL_STATUS"] == {
        "JUDGE_MODE": "SELF_CHECK_ONLY",
        "TASK_STATUS": "COMPLETE_SELF_CHECK_ONLY",
    }
    assert len(x.obj(result["HELPER_SHA256"])) == 28
    assert result["MODEL"] == {
        "TICKETS": 20,
        "LABELS_PER_TICKET": 6,
        "POOL": 49,
        "TRIPLES": 22,
        "PAIRS": 27,
        "PAIR_LINEARITY": True,
    }


def test_bonferroni_signs_and_four_sevenths_all_multiplicities() -> None:
    proof = x.multiplicity_proof()
    assert proof["R_CAP"] == 7
    for r, raw in enumerate(x.items(proof["TABLE"])):
        b5 = sum((-1) ** (k + 1) * comb(r, k) for k in range(1, 6))
        b3 = r - comb(r, 2) + comb(r, 3)
        assert x.items(raw) == [
            r,
            b5,
            int(r > 0),
            b5 - int(r > 0),
            7 * (b3 - int(r > 0)) - 4 * comb(r, 4),
        ]
        assert b5 >= int(r > 0)
        assert Fraction(b3) - Fraction(4 * comb(r, 4), 7) >= int(r > 0)
    with pytest.raises(AssertionError, match="signs"):
        x.multiplicity_proof((1, -1, 1, 1, -1))
    # Without linearity's r<=7, the old 4/7 correction fails at r=8.
    assert Fraction(8 - comb(8, 2) + comb(8, 3)) - Fraction(4 * comb(8, 4), 7) < 1


def test_s123_and_s4_independent_official_counts(result: dict[str, object]) -> None:
    assert result["S123"] == {
        "S1": 372228640,
        "S2": 63838600,
        "PAIR_WEIGHTS_0_1": [107800, 574000],
        "TRIPLE_WEIGHTS_0_TO_3_EDGES": [0, 0, 2800, 20272],
        "CORE_TRIPLE_WEIGHT": 7000,
    }
    assert result["S4_WEIGHTS"] == {
        "K4_NO_TRIPLE": 679,
        "K4_CONTAINED_TRIPLE": 448,
        "K4_MINUS_EDGE": 112,
    }


def test_exhaustive_2544_cases_and_external_support_projection(result: dict[str, object]) -> None:
    table = x.five_ticket_table()
    # Independent graph-first coverage, versus the verifier's packing-first order.
    pairs, triples = tuple(combinations(range(5), 2)), tuple(combinations(range(5), 3))
    seen: set[tuple[int, int]] = set()
    for edges in range(1024):
        graph = {e for i, e in enumerate(pairs) if edges >> i & 1}
        possible = [i for i, t in enumerate(triples) if set(combinations(t, 2)) <= graph]
        for mask in range(1 << len(possible)):
            packing = [triples[i] for j, i in enumerate(possible) if mask >> j & 1]
            shadow = [e for t in packing for e in combinations(t, 2)]
            if len(set(shadow)) == len(shadow):
                seen.add((edges, sum(1 << i for i, t in enumerate(triples) if t in packing)))
    assert seen == {cast(tuple[int, int], row[:2]) for row in table}
    assert len(seen) == 2544
    proof = x.obj(result["S5_PROOF"])
    assert proof["LOCAL_COUNTS"] == [1024, 1280, 240]
    assert proof["LOCAL_HISTOGRAM"] == [
        [0, 0, 1024],
        [1, 0, 1260],
        [1, 7, 20],
        [2, 0, 225],
        [2, 28, 15],
    ]
    assert (
        proof["LOCAL_TABLE_SHA256"]
        == "f2d1cdeeadbfe1951efa43ab32e7c2570a5202967c46003855da2fc3303c2e2b"
    )
    # A missing external endpoint leaves its label as a pair, not a contained triple.
    projected = x.local_profile(5, {(0, 1)}, ())
    assert projected[3] == 1 and projected[1] == projected[2] == 5
    assert sum(projected) == 49


@pytest.mark.parametrize(
    "packing,edges,expected",
    [
        ((), set(combinations(range(5), 2)), 0),
        (((0, 1, 2),), set(combinations(range(5), 2)) - {(3, 4)}, 7),
        (((0, 1, 2), (2, 3, 4)), set(combinations(range(5), 2)), 28),
        (((0, 1, 2), (2, 3, 4)), set(combinations(range(5), 2)) - {(0, 3)}, 0),
    ],
)
def test_s5_special_cases(packing: tuple[x.Triple, ...], edges: set[x.Pair], expected: int) -> None:
    assert x.selected_label_count(x.local_profile(5, edges, packing)) == expected
    assert x.local_identity_value(edges, packing)[2] == expected


def test_s5_degree_upper_bound_and_thresholds(result: dict[str, object]) -> None:
    proof = x.obj(result["S5_PROOF"])
    assert [x.items(row)[5] for row in x.items(proof["THRESHOLD_CAPS"])] == [22, 22, 22, 22, 22, 0]
    # One degree-six vertex cannot make a high-degree triple.
    assert proof["COMMON_PAIR_SUM_CAP"] == 22 * comb(9, 2) == 792
    assert proof["N_2T_CAP"] == comb(6, 2) + 12 * comb(5, 2) == 135
    assert proof["S5_CAP"] == 7 * (792 + 2 * 135) == 7434


def test_cap_authority_and_wrong_target_or_cap(result: dict[str, object]) -> None:
    proof = x.obj(result["CAP_AUTHORITY"])
    x.cap_authority(proof)
    for key in (
        "STATUS",
        "ROUTE",
        "PROFILE_IDS",
        "WEDGE_COUNT",
        "TARGET_TRIANGLE_CAP",
        "REFUTED_GRAPH_TRIANGLE_COUNT",
        "CERTIFIED_OPEN_WEDGE_LOWER_BOUND",
        "CERTIFICATE_KIND",
        "EXTERNAL_TIMEOUT_EXIT_CODE",
        "ATTEMPT_INDEX",
    ):
        with pytest.raises(AssertionError, match="cap authority"):
            x.cap_authority({**proof, key: None})
    with pytest.raises(AssertionError, match="wrong target"):
        x.cap_authority(proof, "66555555555522000000")
    with pytest.raises(AssertionError, match="wrong cap"):
        x.cap_authority(proof, cap=265)


def assert_all_terms(result: dict[str, object]) -> None:
    env = x.obj(result["ENVELOPE"])
    old, terms = x.items(env["OLD_TERMS"]), x.items(env["ALL_T_TERMS"])
    assert [x.items(row)[0] for row in terms] == list(range(22, 265))
    assert old[:-1] == terms[:-1] and x.items(old[-1])[2:] == x.items(terms[-1])[2:]
    for raw in old:
        t, bound, k4, a, s4, s3 = [x.integer(v) for v in x.items(raw)]
        # Independent fixed numeric invariants and rational rounding for every term.
        assert k4 == max(0, -((-(2340 - 10 * (831 - 3 * t))) // 4))
        assert a == min(k4, 200)
        assert s4 == max(1680, 679 * k4 - 231 * a)
        assert s3 == 2800 * 831 + 11872 * (t - 22) - 30800
        exact = Fraction(372228640 - 63838600 + s3) - Fraction(4 * s4, 7)
        assert bound == -(-exact.numerator // exact.denominator)
        assert 0 <= bound - exact < 1
    assert x.items(terms[-1]) == [264, 313281346, 488, 200, 285152, 5169024]
    assert (
        max(x.integer(x.items(row)[1]) for row in terms) == env["FULL_PROFILE_BOUND"] == 313387352
    )
    assert [x.items(row)[0] for row in terms if x.items(row)[1] == 313387352] == [263]
    assert env["PROFILE_DELTA"] == 8768
    assert (
        env["LOWER_T_SHA256"] == "1e5c228547b7648dcd3e011ab340a942a27ceff5d5fd0d1d9aae8221786b0dcf"
    )


def test_all_243_terms_and_true_full_envelope(result: dict[str, object]) -> None:
    assert_all_terms(result)
    for s4 in range(285152, 285159):
        fourth, fifth = x.moment_bounds(5169024, s4, 7434)
        exact = Fraction(372228640 - 63838600 + 5169024) - Fraction(4 * s4, 7)
        assert fourth == -(-exact.numerator // exact.denominator)
        assert fifth == 372228640 - 63838600 + 5169024 - s4 + 7434


def test_family_views_and_no_shared_adoption(result: dict[str, object]) -> None:
    family = x.obj(result["FAMILY_EFFECT"])
    views = x.obj(family["VIEWS"])
    assert x.obj(views["CURRENT_BASE_WITH_TARGET"])["BOUND"] == 313397860
    assert x.obj(views["HYPOTHETICAL_T249_ONLY"])["BOUND"] == 313396120
    assert x.obj(views["HYPOTHETICAL_T249_AND_TARGET"]) == {
        "BOUND": 313395448,
        "OWNERS": ["66555555555441000000", "66555555555522000000"],
    }
    assert family["PROJECTED_DELTA_VS_T249"] == 672
    assert family["BASE_LEDGER_SHA256_BEFORE"] == family["BASE_LEDGER_SHA256_AFTER"]
    assert family["SHARED_LEDGER_ADOPTION"] == "NONE"
    assert family["T249_AUTHORITY"] == "HYPOTHETICAL_CAP_ONLY_NOT_CERTIFIED_OR_ADOPTED"


@pytest.mark.parametrize("path", list(x.PINS)[:3])
def test_tampered_donor_bytes_rejected(path: str, monkeypatch: pytest.MonkeyPatch) -> None:
    original = x.git

    def changed(*args: str) -> bytes:
        raw = original(*args)
        return raw + b" " if args == ("show", f"{x.DONOR_HEAD}:{path}") else raw

    with monkeypatch.context() as patch:
        patch.setattr(x, "git", changed)
        with pytest.raises(AssertionError, match="tampered pinned bytes"):
            x.pinned_bytes(path)


@pytest.mark.parametrize("constant", ["DONOR_TREE", "DONOR_PARENT", "BASE_TREE"])
def test_wrong_commit_identities_rejected(constant: str, monkeypatch: pytest.MonkeyPatch) -> None:
    with monkeypatch.context() as patch:
        patch.setattr(x, constant, "0" * 40)
        with pytest.raises(AssertionError, match=r"identity|parent"):
            x.authority()


MUTATIONS = [
    ("moment_bounds", "fixed - s4_floor + s5_cap", "fixed + s4_floor + s5_cap"),
    ("moment_bounds", "fixed - s4_floor + s5_cap", "fixed - s4_floor - s5_cap"),
    (
        "moment_bounds",
        "-(-exact.numerator // exact.denominator)",
        "exact.numerator // exact.denominator",
    ),
    ("envelope", "min(before, fifth)", "max(before, fifth)"),
    ("envelope", "[*old[:-1], (t, min", "[(t, min"),
    ("local_identity_value", "common_pairs + 2 * two", "common_pairs - 2 * two"),
]


@pytest.mark.parametrize("function,before,after", MUTATIONS)
def test_non_equivalent_mutations_are_killed(
    function: str, before: str, after: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = cast(Callable[..., object], getattr(x, function))
    source = inspect.getsource(original)
    assert source.count(before) == 1
    namespace: dict[str, object] = dict(original.__globals__)
    exec(compile(source.replace(before, after), "<controlled-test-mutation>", "exec"), namespace)

    def guard() -> None:
        if function == "local_identity_value":
            test_s5_special_cases(((0, 1, 2), (2, 3, 4)), set(combinations(range(5), 2)), 28)
        elif function == "moment_bounds":
            test_all_243_terms_and_true_full_envelope(x.compute_result())
        else:
            assert_all_terms(x.compute_result())

    guard()
    with monkeypatch.context() as patch:
        patch.setattr(x, function, namespace[function])
        with pytest.raises(AssertionError):
            guard()
    guard()


def test_sealed_json_exact_replay_and_tampering(result: dict[str, object]) -> None:
    assert json.loads(x.RESULT_PATH.read_bytes()) == result
    assert x.RESULT_PATH.read_bytes() == x.render(result)
    x.verify_result(result)
    for key, value in (("PROFILE_ID", "other"), ("TRIANGLE_CAP", 265)):
        with pytest.raises(AssertionError, match="tampered formal"):
            x.verify_result({**result, key: value})
    damaged = copy.deepcopy(result)
    x.obj(damaged["S5_PROOF"])["S5_CAP"] = 0
    with pytest.raises(AssertionError, match="tampered formal"):
        x.verify_result(damaged)


def test_restrictions_are_explicit(result: dict[str, object]) -> None:
    assert (
        result["SOLVER_CALLS"]
        == result["PORTFOLIO_ENUMERATIONS"]
        == result["SHARED_LEDGER_WRITES"]
        == 0
    )
    assert result["HEAVY_SOLVER_STARTED"] == result["REMOTE_WRITE"] == "NO"
    assert result["GLOBAL_K20_OPTIMUM"] == "UNKNOWN"
    assert x.obj(result["ENVELOPE"])["ALL_T_BONFERRONI5_ADOPTION"] == "OUT_OF_SCOPE_NOT_VERIFIED"
