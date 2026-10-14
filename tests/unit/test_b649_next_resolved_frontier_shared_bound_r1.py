"""Independent focused checks for the shared resolved-frontier triangle cap."""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterable, Mapping
from fractions import Fraction
from itertools import combinations, combinations_with_replacement, product
from math import comb
from typing import cast

import pytest

# Keep bootstrap first so certificate imports resolve from the pinned source snapshot.
# isort: off
from tests.unit.b649_certificate_replay import replay_certificate_call, replay_fixed_result
from lottolab.research import b649_next_resolved_frontier_shared_bound_r1 as cert
# isort: on

PROFILE_IDS = (
    "65555555555541000000",
    "66655555555431000000",
    "66665555544441000000",
)
EXPECTED_CAPS = {
    "65555555555541000000": 238,
    "66655555555431000000": 242,
    "66665555544441000000": 241,
}
EXPECTED_OLD_CAPS = {
    "65555555555541000000": 265,
    "66655555555431000000": 264,
    "66665555544441000000": 264,
}
EXPECTED_OLD_BOUNDS = {
    "65555555555541000000": 313392516,
    "66655555555431000000": 313392412,
    "66665555544441000000": 313392412,
}
EXPECTED_NEW_BOUNDS = {
    "65555555555541000000": 313186584,
    "66655555555431000000": 313195248,
    "66665555544441000000": 313195248,
}
S1_MINUS_S2 = 372_228_640 - 63_838_600


@pytest.fixture(scope="module")
def result() -> dict[str, object]:
    return replay_fixed_result(cert.__name__)


def test_input_identity_accepts_pinned_base_or_direct_candidate_child(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pinned_tree = ("rev-parse", f"{cert.INPUT_HEAD}^{{tree}}")
    head = ("rev-parse", "HEAD")
    head_tree = ("rev-parse", "HEAD^{tree}")
    parent = ("rev-parse", "HEAD^")

    responses = {
        pinned_tree: cert.INPUT_TREE,
        head: cert.INPUT_HEAD,
        head_tree: cert.INPUT_TREE,
    }
    monkeypatch.setattr(cert, "git", lambda *args: responses[args])
    assert cert.verify_input_identity() == "INPUT_HEAD"

    responses = {pinned_tree: cert.INPUT_TREE, head: "candidate-head", parent: cert.INPUT_HEAD}
    monkeypatch.setattr(cert, "git", lambda *args: responses[args])
    assert cert.verify_input_identity() == "DIRECT_CANDIDATE_CHILD"

    responses[parent] = "unrelated-parent"
    with pytest.raises(ValueError, match="wrong input HEAD"):
        cert.verify_input_identity()

    responses[pinned_tree] = "wrong-pinned-tree"
    with pytest.raises(ValueError, match="pinned input TREE mismatch"):
        cert.verify_input_identity()

    responses[pinned_tree] = cert.INPUT_TREE
    responses[head_tree] = "wrong-current-tree"
    monkeypatch.setattr(cert, "git", lambda *args: responses[args])
    responses[head] = cert.INPUT_HEAD
    with pytest.raises(ValueError, match="wrong input TREE"):
        cert.verify_input_identity()


def independent_graphical_zeta_sequences() -> tuple[tuple[int, ...], ...]:
    """Use Havel-Hakimi over all sorted degree multisets, not graph-mask code."""

    def graphical(degrees: Iterable[int]) -> bool:
        remaining = sorted(degrees, reverse=True)
        while remaining:
            first = remaining.pop(0)
            if first == 0:
                return True
            if first < 0 or first > len(remaining):
                return False
            for index in range(first):
                remaining[index] -= 1
                if remaining[index] < 0:
                    return False
            remaining.sort(reverse=True)
        return True

    sequences = {
        tuple(6 - degree for degree in reversed(ascending))
        for ascending in combinations_with_replacement(range(6), 6)
        if graphical(reversed(ascending))
    }
    return tuple(sorted(sequences))


def independent_relaxation(pid: str, zeta_sequences: tuple[tuple[int, ...], ...]) -> tuple[int, set[tuple[object, ...]]]:
    """Enumerate labelled sigma vectors and independently aggregate their symmetry."""
    d = tuple(map(int, pid))
    active = tuple(value for value in d if value > 0)
    best_sigma: dict[int, int] = {}
    arg_sigma: dict[int, set[tuple[tuple[int, tuple[int, ...]], ...]]] = {}
    choices = tuple(range(7 - value) for value in active)
    for sigma_values in product(*choices):
        r = sum(sigma_values)
        score = sum(sigma * (7 - value + sigma) for value, sigma in zip(active, sigma_values, strict=True))
        signature = tuple(
            (value, tuple(sorted(sigma for degree, sigma in zip(active, sigma_values, strict=True) if degree == value)))
            for value in sorted(set(active), reverse=True)
        )
        old = best_sigma.get(r)
        if old is None or score > old:
            best_sigma[r] = score
            arg_sigma[r] = {signature}
        elif score == old:
            arg_sigma[r].add(signature)

    best_zeta: dict[int, int] = {}
    arg_zeta: dict[int, set[tuple[int, ...]]] = {}
    for zeta in zeta_sequences:
        r = sum(zeta)
        score = sum(value * (value - 1) for value in zeta)
        old = best_zeta.get(r)
        if old is None or score > old:
            best_zeta[r] = score
            arg_zeta[r] = {zeta}
        elif score == old:
            arg_zeta[r].add(zeta)

    goodman = comb(20, 3) - sum(
        (6 + value) * (19 - (6 + value)) for value in d
    ) // 2
    caps = {
        r: goodman - 54 - 10 * r + best_sigma[r] + best_zeta[r]
        for r in set(best_sigma) & set(best_zeta)
    }
    cap = max(caps.values())
    argmax: set[tuple[object, ...]] = set()
    for r, bound in caps.items():
        if bound != cap:
            continue
        for signature in arg_sigma[r]:
            for zeta in arg_zeta[r]:
                argmax.add(
                    (
                        r,
                        best_sigma[r],
                        signature,
                        best_zeta[r],
                        zeta,
                        bound,
                    )
                )
    return cap, argmax


def result_argmax_key(row: Mapping[str, object]) -> tuple[object, ...]:
    signature = tuple(
        (int(value), tuple(map(int, sigmas)))
        for value, sigmas in cast(list[list[object]], row["SIGMA_SIGNATURE_BY_D"])
    )
    return (
        int(row["R"]),
        int(row["SIGMA_SCORE"]),
        signature,
        int(row["ZETA_SCORE"]),
        tuple(map(int, cast(list[int], row["ZETA_SEQUENCE"]))),
        int(row["UPPER_BOUND"]),
    )


def independent_term(pid: str, t: int, floor: int = 112) -> tuple[int, int, int, int, int, int]:
    d = tuple(map(int, pid))
    g = tuple(6 + value for value in d)
    w = sum(comb(value, 2) for value in g)
    opened = w - 3 * t
    k4_numerator = sum(comb(value, 3) for value in g) - (max(g) - 2) * opened
    k4 = max(0, -(-k4_numerator // 4))
    a_max = sum(value * (6 + value - 2) for value in d) // 3
    contained = min(k4, a_max)
    s4 = max(floor, 679 * k4 - 231 * contained)
    s3 = 2800 * opened + 20272 * (t - 22) + 154000
    exact = Fraction(S1_MINUS_S2 + s3) - Fraction(4 * s4, 7)
    bound = -(-exact.numerator // exact.denominator)
    return t, bound, k4, contained, s4, s3


@pytest.fixture(scope="module")
def independent_zeta() -> tuple[tuple[int, ...], ...]:
    return independent_graphical_zeta_sequences()


def test_fixed_input_reproduces_family_and_complete_frontier(result: dict[str, object]) -> None:
    assert result["INPUT_CERTIFICATE"]["HEAD"] == "06664eeb1a7ecb8138e15f70bac32681f84bbf55"
    assert result["INPUT_CERTIFICATE"]["TREE"] == "11cf44e93cf921446118edf3b26127ff24e0fd49"
    assert result["INPUT_CERTIFICATE"]["REPRODUCED_BYTE_FOR_BYTE"] is True
    assert result["FRONTIER_OWNER_IDS"] == list(PROFILE_IDS)
    assert result["FAMILY_BEFORE"]["MAXIMUM"] == 313392516
    assert result["FAMILY_BEFORE"]["ALL_MAX_OWNERS"] == [PROFILE_IDS[0]]
    assert result["FAMILY_BEFORE"]["NEXT_DISTINCT_BOUND"] == 313392412
    assert result["FAMILY_BEFORE"]["ALL_NEXT_DISTINCT_OWNERS"] == list(PROFILE_IDS[1:])
    assert result["CURSOR_197_PRESERVED"]["COUNT"] == 197
    assert result["CURSOR_197_PRESERVED"]["MAXIMUM"] == 313391784
    assert result["RESOLVED_ROW_COUNT"] == 4647
    assert result["INHERITED_EXCLUSION"]["COUNT"] == 282
    assert result["INHERITED_EXCLUSION"]["IDS_SHA256"] == cert.EXCLUDED_IDS_SHA256
    assert result["INHERITED_EXCLUSION"]["W_RANGE"] == [822, 861]
    assert result["CONDITIONAL_PROJECTION_ONLY"] is True


def test_shared_k_z_relaxation_matches_independent_labelled_enumeration(
    result: dict[str, object], independent_zeta: tuple[tuple[int, ...], ...]
) -> None:
    assert len(independent_zeta) == 102
    assert cert.zeta_graphical_sequences()[0] == 32768
    assert cert.zeta_graphical_sequences()[1] == independent_zeta
    profiles = result["PROFILES"]
    for pid in PROFILE_IDS:
        profile = profiles[pid]
        theorem = profile["RELAXATION_CAP"]
        independent_cap, independent_argmax = independent_relaxation(pid, independent_zeta)
        actual_argmax = {
            result_argmax_key(row)
            for row in cast(list[Mapping[str, object]], theorem["ALL_RELAXATION_ARGMAX"])
        }
        assert theorem["CAP"] == independent_cap == EXPECTED_CAPS[pid]
        assert actual_argmax == independent_argmax
        assert theorem["STATE_ATTAINABILITY"] == "NOT_ASSERTED; NECESSARY_CONDITION_RELAXATION"
    caps = {pid: int(profiles[pid]["RELAXATION_CAP"]["CAP"]) for pid in PROFILE_IDS}
    cert.validate_shared_cap(242, caps)
    assert result["SHARED_THEOREM"]["COMMON_T_CAP"] == 242
    assert result["SHARED_THEOREM"]["FULL_SUPPORT_GRAPHS_ENUMERATED"] == 0
    assert result["SHARED_THEOREM"]["PORTFOLIOS_ENUMERATED"] == 0
    assert result["SHARED_THEOREM"]["RELAXATION_STATES_ASSERTED_REALIZABLE"] is False


@pytest.mark.parametrize("bad_cap", [241, 243, True])
def test_shared_cap_rejects_under_or_overstatement(
    bad_cap: int,
) -> None:
    caps = EXPECTED_CAPS
    assert cert.validate_shared_cap(242, caps) is None
    with pytest.raises(ValueError, match="shared cap"):
        cert.validate_shared_cap(bad_cap, caps)


def test_sigma_ranges_and_graphical_zeta_membership_have_negative_controls() -> None:
    assert cert.validate_zeta_sequence((1, 1, 1, 1, 1, 1)) is None
    with pytest.raises(ValueError, match="non-graphical"):
        cert.validate_zeta_sequence((1, 1, 1, 1, 1, 6))
    signature = list(cert.sigma_signatures(PROFILE_IDS[0])[0])
    assert cert.validate_sigma_signature(PROFILE_IDS[0], signature) is None
    d_value, sigmas = signature[-1]
    assert d_value == 1
    signature[-1] = (d_value, (*sigmas[:-1], 6))
    with pytest.raises(ValueError, match="sigma range"):
        cert.validate_sigma_signature(PROFILE_IDS[0], signature)


def test_s4_and_s5_authority_is_preserved_and_wrong_s5_use_is_rejected(
    result: dict[str, object]
) -> None:
    base = json.loads(
        cert.prior.blob(cert.prior.BASE_HEAD, cert.prior.r2.BASE_RESULT, cert.prior.r2.BASE_SHA)
    )
    for pid in PROFILE_IDS:
        assert cert.s4_floor(pid) == 112
        assert cert.validate_s5_claim(pid, base, False) is None
        with pytest.raises(ValueError, match="S5 cannot be claimed"):
            cert.validate_s5_claim(pid, base, True)
    assert result["S4_S5_AUTHORITY"]["S5_ALL_T_ADOPTION"] == "NOT_VERIFIED"
    assert result["S4_S5_AUTHORITY"]["S5_USED_FOR_FRONTIER"] is False


def test_every_old_and_new_t_envelope_term_and_all_argmax_recomputed(
    result: dict[str, object]
) -> None:
    for pid in PROFILE_IDS:
        profile = result["PROFILES"][pid]
        old_cap = EXPECTED_OLD_CAPS[pid]
        new_cap = 242
        old_terms = [independent_term(pid, t) for t in range(22, old_cap + 1)]
        new_terms = [independent_term(pid, t) for t in range(22, new_cap + 1)]
        assert profile["OLD_EFFECTIVE_T_CAP_RECONSTRUCTED_FROM_INPUT_BOUND"] == old_cap
        assert max(term[1] for term in old_terms) == EXPECTED_OLD_BOUNDS[pid]
        assert max(term[1] for term in new_terms) == EXPECTED_NEW_BOUNDS[pid]
        assert new_terms == [tuple(term) for term in profile["NEW_ALL_T_TERMS"]]
        assert [term for term in new_terms if term[1] == max(row[1] for row in new_terms)] == [
            tuple(term) for term in profile["NEW_ALL_ARGMAX"]
        ]
        assert profile["NEW_TERM_COUNT"] == len(new_terms) == 221
        assert profile["FRACTIONAL_S4_CREDIT_TERM_COUNT"] == sum(
            (4 * term[4]) % 7 != 0 for term in new_terms
        )
        cert.validate_envelope(pid, new_cap, 112, new_terms)
        with pytest.raises(ValueError, match="S4 lower-bound direction/floor"):
            cert.validate_envelope(pid, new_cap, 113, new_terms)


def test_envelope_rejects_missing_terms_bad_s4_k4_s3_and_rational_floor(
    result: dict[str, object]
) -> None:
    pid = PROFILE_IDS[1]
    profile = result["PROFILES"][pid]
    terms = [tuple(map(int, row)) for row in cast(list[list[int]], profile["NEW_ALL_T_TERMS"])]
    cert.validate_envelope(pid, 242, 112, terms)
    with pytest.raises(ValueError, match="incomplete T envelope"):
        cert.validate_envelope(pid, 242, 112, terms[:-1])

    index = len(terms) - 1
    row = terms[index]
    changed = list(terms)
    changed[index] = (row[0], row[1], row[2] + 1, *row[3:])
    with pytest.raises(ValueError, match="K4 ceiling"):
        cert.validate_envelope(pid, 242, 112, changed)
    changed[index] = (row[0], row[1], row[2], row[3] - 1, *row[4:])
    with pytest.raises(ValueError, match="A_max floor/containment"):
        cert.validate_envelope(pid, 242, 112, changed)
    changed[index] = (row[0], row[1], row[2], row[3], row[4] + 7, row[5])
    with pytest.raises(ValueError, match="S4 lower-bound direction/floor"):
        cert.validate_envelope(pid, 242, 112, changed)
    changed[index] = (row[0], row[1], row[2], row[3], row[4], row[5] + 1)
    with pytest.raises(ValueError, match="S3 identity"):
        cert.validate_envelope(pid, 242, 112, changed)

    # The adopted floor 112 produces integral credits in this envelope. Use a
    # controlled floor only to exercise the exact ceiling's negative control.
    probe_terms = cert.envelope(pid, 242, 113)
    fractional_index = next(
        i
        for i, term in enumerate(probe_terms)
        if (S1_MINUS_S2 + term[5] - Fraction(4 * term[4], 7)).denominator != 1
    )
    term = probe_terms[fractional_index]
    exact = S1_MINUS_S2 + term[5] - Fraction(4 * term[4], 7)
    changed = list(probe_terms)
    changed[fractional_index] = (
        term[0],
        exact.numerator // exact.denominator,
        *term[2:],
    )
    with pytest.raises(ValueError, match="final exact rational ceiling"):
        cert.validate_envelope(pid, 242, 113, changed)


def test_family_delta_uses_every_row_and_does_not_copy_the_top_row_delta(
    result: dict[str, object]
) -> None:
    before = cast(dict[str, int], result["RESOLVED_ROWS_BEFORE"])
    after = cast(dict[str, int], result["RESOLVED_ROWS_AFTER"])
    cursor = cast(dict[str, int], result["CURSOR_197_PRESERVED"]["ROW_BOUNDS"])
    assert len(before) == len(after) == 4647
    assert len(cursor) == 197
    assert {pid for pid in before if before[pid] != after[pid]} == set(PROFILE_IDS)
    assert sum(before[pid] == after[pid] for pid in before) == 4644
    assert before[PROFILE_IDS[0]] - after[PROFILE_IDS[0]] == 205932
    assert result["FAMILY_DELTA"] == 208
    assert result["FAMILY_AFTER"]["MAXIMUM"] == 313392308
    assert result["ALL_NEW_MAX_OWNERS"] == ["66665555555421000000"]
    assert result["NEXT_DISTINCT_BOUND"] == 313392232
    assert result["FAMILY_AFTER"]["ALL_NEXT_DISTINCT_OWNERS"] == [
        "65555555555442000000",
        "66555555554433000000",
    ]
    one_row = dict(before)
    one_row[PROFILE_IDS[0]] = EXPECTED_NEW_BOUNDS[PROFILE_IDS[0]]
    one_row_family = cert.family_summary(one_row, cursor)
    assert one_row_family["MAXIMUM"] == 313392412
    assert one_row_family["ALL_MAX_OWNERS"] == list(PROFILE_IDS[1:])
    assert one_row_family["MAXIMUM"] - result["FAMILY_AFTER"]["MAXIMUM"] == 104
    assert result["CURSOR_197_PRESERVED"]["UNCHANGED"] is True


def test_result_bytes_reproduce() -> None:
    assert replay_certificate_call(cert.__name__, "verify_result") is None
