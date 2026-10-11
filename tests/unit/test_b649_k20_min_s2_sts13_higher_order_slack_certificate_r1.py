"""Exact induced-label oracles, universal proof, immutable adoption and mutants."""

from __future__ import annotations

import copy
import hashlib
import inspect
import json
from collections.abc import Callable
from dataclasses import replace
from fractions import Fraction
from itertools import combinations
from math import comb
from pathlib import Path
from typing import cast

import pytest

from lottolab.research import b649_k20_min_s2_sts13_higher_order_slack_certificate_r1 as x


@pytest.fixture(scope="module")
def authority() -> x.Authority:
    return x.load_authority()


@pytest.fixture(scope="module")
def result(authority: x.Authority) -> dict[str, object]:
    return x.compute_result(authority)


def test_exact_base_and_imported_source_identity(authority: x.Authority) -> None:
    assert x.chase.git("rev-parse", f"{x.BASE_HEAD}^{{tree}}").decode().strip() == x.BASE_TREE
    assert x.integration.pinned(x.BASE_HEAD, x.previous.RESULT_FILENAME, x.BASE_RESULT_SHA256) == (
        authority.sealed
    )
    assert len(authority.provenance) == 31
    for relative, expected in authority.provenance.items():
        blob = x.chase.git("show", f"{x.BASE_HEAD}:{relative}")
        assert (x.chase.ROOT / relative).read_bytes() == blob
        assert hashlib.sha256(blob).hexdigest() == expected
    assert (
        x.integration.family(authority.ledger, authority.inherited.inherited.inherited)
        == (authority.sealed["FINAL_FAMILY"])
    )


def test_predecessor_source_tampering_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    path, original = Path(x.previous.__file__ or "").resolve(), Path.read_bytes

    def changed(p: Path) -> bytes:
        return original(p) + (b"\n# changed\n" if p == path else b"")

    x.load_authority.cache_clear()
    with monkeypatch.context() as patch:
        patch.setattr(Path, "read_bytes", changed)
        with pytest.raises(AssertionError, match="source identity"):
            x.load_authority()


def assert_universal() -> None:
    proof = x.universal_proof()
    assert (proof["EXACT_S4"], proof["EXACT_S5"], proof["EXACT_S7"]) == (331240, 6860, 0)
    assert proof["S6_FORMULA"] == "7 * PASCH_SIX_SET_COUNT"
    assert proof["K12_FIVE_SET_COUNTS_0_1_2"] == [192, 480, 120]
    assert proof["K12_TRIPLE_FIVE_SET_INCIDENCES"] == 720
    assert proof["K8_MINUS_E_COMPLETE_FIVE_SET_COUNTS_0_1"] == [18, 18]
    assert proof["K8_MINUS_E_MISSING_FIVE_SET_COUNTS_0_1"] == [18, 2]
    assert proof["LOCAL_FIVE_PACKING_COUNT"] == 26
    assert proof["LOCAL_SIX_PACKING_COUNT"] == 271
    assert proof["LOCAL_PASCH_PACKING_COUNT"] == 30
    assert (proof["FANO_REQUIRED_CROSSING_TRIPLES"], proof["FANO_AVAILABLE_OUTSIDE_PAIRS"]) == (
        14,
        10,
    )
    assert proof["PROVED_SLACK_NUMERATOR_OVER_7"] == 945700
    assert proof["PROVED_SLACK_LOWER_BOUND"] == 135100 >= x.REQUESTED_SLACK
    assert proof["CERTIFIED_SLACK"] == 15595
    assert proof["LOCAL_WEIGHT_TABLE_SHA256"] == x.digest(proof["LOCAL_WEIGHT_TABLE"])


@pytest.mark.parametrize("n", [5, 6])
def test_universal_slack_and_local_support_coverage(n: int) -> None:
    assert_universal()
    packings = x.linear_packings(n)
    assert len(set(packings)) == len(packings)
    # Independent exhaustive backtracking over local triple decisions.
    found: set[tuple[x.Support, ...]] = set()
    triples = tuple(combinations(range(n), 3))

    def visit(i: int, chosen: tuple[x.Support, ...], used: set[x.Pair]) -> None:
        if i == len(triples):
            found.add(chosen)
            return
        visit(i + 1, chosen, used)
        edges = set(combinations(triples[i], 2))
        if not used & edges:
            visit(i + 1, (*chosen, triples[i]), used | edges)

    visit(0, (), set())
    assert set(packings) == found
    splits = [
        x.rows(row) for row in x.rows(x.universal_proof()["MIXED_COMPONENT_MIN_SELECTED_LABELS"])
    ]
    assert len(splits) == 15 and all(x.integer(row[2]) > 7 for row in splits)


def test_exact_excess_identity_for_every_allowed_multiplicity() -> None:
    proof = x.excess_identity_check()
    assert proof["R_CAP"] == 7
    for raw in x.rows(proof["TABLE"]):
        r, s4, s5, s6, s7, numerator = map(x.integer, x.rows(raw))
        exact = r - comb(r, 2) + comb(r, 3) - Fraction(4 * s4, 7) - int(r > 0)
        assert exact == Fraction(3 * s4, 7) - s5 + s6 - s7 == Fraction(numerator, 7)
        assert s6 >= s7 and exact >= 0


def label_oracle(profile: tuple[int, ...]) -> int:
    """Enumerate only one tiny induced-label model, independently of the class DP."""
    n = len(profile).bit_length() - 1
    masks = [m for m, count in enumerate(profile) if m for _ in range(count)]
    # No contributing seven-set can contain an outside label for these test classes.
    assert sum(sorted((m.bit_count() for m in masks), reverse=True)[:6]) < 3 * n
    total = 0
    for chosen in combinations(masks, 7):
        if sum(m.bit_count() for m in chosen) < 3 * n:
            continue
        if all(sum(bool(m & (1 << v)) for m in chosen) >= 3 for v in range(n)):
            total += 7
    return total


@pytest.mark.parametrize(
    "blocks,expected", [((), 0), (((0, 1, 2),), 7), (((0, 1, 2), (2, 3, 4)), 28)]
)
def test_s5_definition_against_distinct_label_oracle(
    blocks: tuple[x.Support, ...], expected: int
) -> None:
    profile = x.local_profile(5, set(combinations(range(5), 2)), blocks)
    assert x.intersection_count(profile) == label_oracle(profile) == expected


def test_s6_definition_and_pinned_event_semantics() -> None:
    pasch = ((0, 1, 2), (0, 3, 4), (1, 3, 5), (2, 4, 5))
    profile = x.local_profile(6, set(combinations(range(6), 2)), pasch)
    assert x.intersection_count(profile) == label_oracle(profile) == 7
    for blocks in ((), ((0, 1, 2),)):
        profile4 = x.local_profile(4, set(combinations(range(4), 2)), blocks)
        pinned = x.event.compressed_four_ticket_intersection_count(
            profile4, pool_size=49, draw_size=6, outright_matches=3
        )
        assert x.intersection_count(profile4) == pinned


def test_invalid_local_models_fail_closed() -> None:
    with pytest.raises(ValueError, match="nonlinear"):
        x.local_profile(5, set(combinations(range(5), 2)), ((0, 1, 2), (0, 1, 3)))
    with pytest.raises(ValueError, match="dimension"):
        x.intersection_count((49,))
    with pytest.raises(ValueError, match="counts"):
        x.intersection_count((0,) * 32)
    profile = [0] * 32
    profile[0], profile[31] = 43, 6
    with pytest.raises(ValueError, match="support exceeds"):
        x.intersection_count(tuple(profile))
    with pytest.raises(ValueError, match="capacity"):
        x.intersection_count((49,) + (0,) * 31)
    with pytest.raises(ValueError, match="scope"):
        x.linear_packings(7)


def test_s7_definition_and_unextendible_fano_subsystem() -> None:
    fano = ((0, 1, 2), (0, 3, 4), (0, 5, 6), (1, 3, 5), (1, 4, 6), (2, 3, 6), (2, 4, 5))
    profile = x.local_profile(7, set(combinations(range(7), 2)), fano)
    assert x.intersection_count(profile) == 7
    assert comb(5, 2) < 7 * (5 - 3)  # Cannot extend to the pinned degree-five K12 core.


def test_two_legal_sts13_presentations_have_different_s6() -> None:
    a = x.higher_order_sums(*x.split.witness_supports("STS13"))
    b = x.higher_order_sums(*x.traded_witness())
    assert (a["S5"], a["S6"], a["S7"], a["EXACT_ANY_PRIZE_UNION"]) == (6860, 49, 0, 313263867)
    assert (b["S5"], b["S6"], b["S7"], b["EXACT_ANY_PRIZE_UNION"]) == (6860, 28, 0, 313263888)
    triples, pairs = x.traded_witness()
    permutation = tuple(reversed(range(20)))

    def relabel(s: x.Support) -> x.Support:
        return tuple(sorted(permutation[v] for v in s))

    c = x.higher_order_sums(tuple(relabel(t) for t in triples), tuple(relabel(p) for p in pairs))
    assert [c[k] for k in ("S5", "S6", "S7")] == [b[k] for k in ("S5", "S6", "S7")]
    with pytest.raises(ValueError):
        x.higher_order_sums(triples[:-1], pairs)
    with pytest.raises(ValueError):
        x.higher_order_sums(triples, (*pairs[:-1], pairs[0]))


def assert_envelope(authority: x.Authority) -> None:
    cert = x.owner_certificate(authority)
    assert (cert["OLD_T270_BOUND"], cert["NEW_T270_BOUND"], cert["EXACT_S4"]) == (
        313399016,
        313383421,
        331240,
    )
    assert (cert["RETAINED_LOWER_T_COUNT"], cert["RETAINED_LOWER_T_MAX"]) == (248, 313392760)
    assert cert["CERTIFIED_PROFILE_BOUND"] == 313392760
    old = x.rows(x.object_row(authority.donor["ADOPTION"])["ALL_T_TERMS"])
    new = x.rows(cert["ALL_T_TERMS"])
    assert new[:-1] == old[:-1] and cert["RETAINED_TERMS_SHA256"] == x.digest(old[:-1])
    assert x.rows(new[-1])[2:] == x.rows(old[-1])[2:]
    assert [x.rows(t)[0] for t in new] == list(range(22, 271))
    assert cert["EXISTING_LEDGER_SOURCE"] == authority.ledger[x.PROFILE].source
    assert cert["CAP_SOURCE"] == x.object_row(authority.donor["ADOPTION"])["CAP_AUTHORITY"]
    assert cert["CAP_SOURCE"] == (
        "b649-k20-min-s2-nb-degree-cap-frontier-r1-result.json:NB_CERTIFICATES[1732]"
    )


def test_one_term_adoption_preserves_all_lower_t_and_cap(authority: x.Authority) -> None:
    assert_envelope(authority)
    row = authority.ledger[x.PROFILE]
    for bad in (
        replace(row, cap=269),
        replace(row, cap=270.0),
        replace(row, source="other"),
        replace(row, bound=row.bound - 1),
    ):
        with pytest.raises(AssertionError, match="identity"):
            x.owner_certificate(replace(authority, ledger={**authority.ledger, x.PROFILE: bad}))


def test_witness_union_soundness_guard(authority: x.Authority) -> None:
    assert x.witness_soundness(313392760, authority)["STATUS"] == "PASS"
    with pytest.raises(AssertionError, match="legal witness union"):
        x.witness_soundness(313263887, authority)


def test_complete_family_max_and_next_owner(
    result: dict[str, object], authority: x.Authority
) -> None:
    start, final = x.object_row(result["START_FAMILY"]), x.object_row(result["FINAL_FAMILY"])
    assert (start["FAMILY_UB"], final["FAMILY_UB"], final["OWNER_IDS"]) == (
        313399016,
        313398920,
        ["66555555555540000000"],
    )
    assert result["REMAINING_GAP"] == 135032
    assert result["FINAL_PROFILE_BOUND"] == 313392760
    coverage = x.object_row(final["COVERAGE"])
    assert [
        coverage[k]
        for k in (
            "ADMISSIBLE_PROFILE_COUNT",
            "RESOLVED_ROW_COUNT",
            "UNDER_CURSOR_PROFILE_COUNT",
            "UNCOVERED_PROFILE_COUNT",
        )
    ] == ([4844, 4647, 197, 0])
    assert start["COVERAGE"] == final["COVERAGE"]
    assert (start["CURSOR_ID"], start["CURSOR_BOUND"]) == (
        final["CURSOR_ID"],
        final["CURSOR_BOUND"],
    )
    assert result["OTHER_PROFILE_ROWS_UNCHANGED"] == 4646
    assert result["OTHER_ROWS_SHA256"] == x.digest(
        {pid: row.bound for pid, row in authority.ledger.items() if pid != x.PROFILE}
    )
    assert result["INHERITED_CERTIFICATES"] == authority.sealed["INHERITED_CERTIFICATES"]
    assert result["SOLVER_CALLS"] == result["OUTCOME_ENUMERATIONS"] == 0


def test_certificate_and_result_tampering_rejected(
    authority: x.Authority, result: dict[str, object]
) -> None:
    cert = x.owner_certificate(authority)
    for key in ("CERTIFIED_SLACK", "EXACT_S4", "NEW_T270_BOUND", "CERTIFIED_PROFILE_BOUND"):
        with pytest.raises(AssertionError, match="tampered higher-order"):
            x.verify_certificate({**cert, key: x.integer(cert[key]) + 1}, authority)
    bad = copy.deepcopy(cert)
    x.object_row(bad["HIGHER_ORDER_PROOF"])["EXACT_S5"] = 0
    with pytest.raises(AssertionError, match="tampered higher-order"):
        x.verify_certificate(bad, authority)
    # In-place tampering must not poison the independent expected certificate.
    x.object_row(cert["HIGHER_ORDER_PROOF"])["EXACT_S5"] = 0
    with pytest.raises(AssertionError, match="tampered higher-order"):
        x.verify_certificate(cert, authority)
    cert = x.owner_certificate(authority)
    x.rows(x.rows(cert["ALL_T_TERMS"])[0])[2] = 999
    with pytest.raises(AssertionError, match="tampered higher-order"):
        x.verify_certificate(cert, authority)
    with pytest.raises(AssertionError, match="tampered immutable"):
        x.verify_result({**result, "FINAL_COMPLETE_FAMILY_UB": 313383421}, authority)
    x.verify_result(result, authority)
    if x.RESULT_PATH.exists():
        assert json.loads(x.RESULT_PATH.read_text()) == result
        with pytest.raises(AssertionError, match="already exists"):
            x.main()


def test_unproved_requested_credit_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    with monkeypatch.context() as patch:
        patch.setattr(x, "REQUESTED_SLACK", 135101)
        with pytest.raises(AssertionError, match="universal premise"):
            x.universal_proof()
    assert_universal()


MUTATIONS = {
    "wrong_official_special_factor": (
        "intersection_count",
        "return 7 * states.get",
        "return 6 * states.get",
    ),
    "assume_identical_s6": ("higher_order_sums", "7 * len(pasches)", "49"),
    "incorrect_s5_support_incidence": ("universal_proof", "12 * comb(5, 2)", "11 * comb(5, 2)"),
    "drop_s5_from_slack": ("universal_proof", "3 * s4 - 7 * s5", "3 * s4"),
    "incorrect_excess_coefficient": ("excess_identity_check", "3 * s4 - 7 * s5", "4 * s4 - 7 * s5"),
    "false_fano_premise": ("universal_proof", "7 * (5 - 3)", "7 * (5 - 4)"),
    "drop_lower_t": ("owner_certificate", "[*lower, [last[0]", "[[last[0]"),
    "cap_as_profile_max": (
        "owner_certificate",
        "max(integer(t[1]) for t in new_terms)",
        "new_bound",
    ),
    "deduct_slack_twice": (
        "owner_certificate",
        'integer(proof["CERTIFIED_SLACK"])',
        '2 * integer(proof["CERTIFIED_SLACK"])',
    ),
    "ignore_legal_witness": (
        "witness_soundness",
        'bound < integer(w["EXACT_ANY_PRIZE_UNION"])',
        "False",
    ),
}


@pytest.mark.parametrize("name", MUTATIONS)
def test_targeted_non_equivalent_mutations_killed(
    name: str, authority: x.Authority, monkeypatch: pytest.MonkeyPatch
) -> None:
    function_name, old, new = MUTATIONS[name]
    original = cast(Callable[..., object], getattr(x, function_name))
    source = inspect.getsource(original)
    assert source.count(old) == 1
    namespace: dict[str, object] = dict(vars(x))
    exec(compile(source.replace(old, new), f"<mutation:{name}>", "exec"), namespace)

    def guard() -> None:
        if function_name == "owner_certificate":
            assert_envelope(authority)
        elif function_name == "witness_soundness":
            test_witness_union_soundness_guard(authority)
        elif function_name == "excess_identity_check":
            test_exact_excess_identity_for_every_allowed_multiplicity()
        elif function_name == "intersection_count":
            test_s5_definition_against_distinct_label_oracle(((0, 1, 2),), 7)
        elif function_name == "higher_order_sums":
            test_two_legal_sts13_presentations_have_different_s6()
        else:
            assert_universal()

    guard()
    with monkeypatch.context() as patch:
        patch.setattr(x, function_name, namespace[function_name])
        with pytest.raises((AssertionError, pytest.fail.Exception)):
            guard()
    guard()
