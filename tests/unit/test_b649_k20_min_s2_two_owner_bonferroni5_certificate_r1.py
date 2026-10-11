"""Focused exact-model, adoption, historical boundary and falsifiable mutation tests."""

from __future__ import annotations

import copy
import hashlib
import inspect
import json
import os
import subprocess
import sys
from collections.abc import Callable
from dataclasses import replace
from fractions import Fraction
from itertools import combinations
from math import comb
from pathlib import Path
from typing import cast

import pytest

from lottolab.research import b649_k20_min_s2_two_owner_bonferroni5_certificate_r1 as x

OWNER1, OWNER2 = x.OWNER_SOURCES
EXPECTED = {
    OWNER1: (760, 136, 7224, 285152, 313398920, 313283936, 313390152),
    OWNER2: (799, 136, 7497, 285831, 313398532, 313283530, 313389376),
}


@pytest.fixture(scope="module")
def authority() -> x.Authority:
    return x.load_authority()


@pytest.fixture(scope="module")
def result(authority: x.Authority) -> dict[str, object]:
    return x.compute_result(authority)


def proof_for(pid: str, auth: x.Authority) -> dict[str, object]:
    return x.object_row(x.rows(auth.r30["GROUP_ATTEMPTS"])[x.OWNER_SOURCES[pid][1]])


def test_pinned_base_result_and_transitive_sources(authority: x.Authority) -> None:
    assert x.chase.git("rev-parse", f"{x.BASE_HEAD}^{{tree}}").decode().strip() == x.BASE_TREE
    assert x.integration.pinned(x.BASE_HEAD, x.previous.RESULT_FILENAME, x.BASE_RESULT_SHA256) == (
        authority.sealed
    )
    for relative, expected in authority.provenance.items():
        blob = x.chase.git("show", f"{x.BASE_HEAD}:{relative}")
        assert (x.chase.ROOT / relative).read_bytes() == blob
        assert hashlib.sha256(blob).hexdigest() == expected
    assert (
        x.integration.family(authority.ledger, authority.inherited.inherited.inherited.inherited)
        == authority.sealed["FINAL_FAMILY"]
    )


def test_predecessor_source_tampering_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    target, original = Path(x.previous.__file__ or "").resolve(), Path.read_bytes

    def changed(path: Path) -> bytes:
        return original(path) + (b"\n# changed\n" if path == target else b"")

    x.load_authority.cache_clear()
    with monkeypatch.context() as patch:
        patch.setattr(Path, "read_bytes", changed)
        with pytest.raises(AssertionError, match="source identity"):
            x.load_authority()


def label_oracle(profile: tuple[int, ...]) -> int:
    """Small distinct-label oracle; no full official-outcome enumeration."""
    labels = [mask for mask, count in enumerate(profile) if mask for _ in range(count)]
    assert sum(sorted((m.bit_count() for m in labels), reverse=True)[:6]) < 15
    return 7 * sum(
        sum(m.bit_count() for m in q) >= 15
        and all(sum(bool(m & (1 << v)) for m in q) >= 3 for v in range(5))
        for q in combinations(labels, 7)
    )


@pytest.mark.parametrize(
    ("triples", "missing", "expected"),
    [
        ((), (), 0),
        (((0, 1, 2),), (), 7),
        (((0, 1, 2),), ((3, 4),), 7),
        (((0, 1, 2),), ((0, 3),), 0),
        (((0, 1, 2), (2, 3, 4)), (), 28),
        (((0, 1, 2), (2, 3, 4)), ((0, 3),), 0),
    ],
)
def test_local_five_ticket_weight_against_independent_label_oracle(
    triples: tuple[x.Support, ...], missing: tuple[x.Pair, ...], expected: int
) -> None:
    edges = set(combinations(range(5), 2)) - set(missing)
    profile = x.previous.local_profile(5, edges, triples)
    common, two = x.s5_counts(tuple(range(5)), edges, triples)
    assert (
        x.s5_identity_value(common, two)
        == x.previous.intersection_count(profile)
        == (label_oracle(profile))
        == expected
    )


def assert_identity() -> None:
    x.local_weight_table.cache_clear()
    proof = x.universal_proof()
    assert proof["LOCAL_CASE_COUNT"] == 2544
    assert proof["LOCAL_CASE_COUNTS_0_1_2_TRIPLES"] == [1024, 1280, 240]
    assert proof["TWO_TRIPLE_K5_WEIGHT"] == 28
    assert proof["LOCAL_WEIGHT_TABLE_SHA256"] == x.digest(x.local_weight_table())
    assert proof["LOCAL_WEIGHT_HISTOGRAM"] == [
        [0, 0, 1024],
        [1, 0, 1260],
        [1, 7, 20],
        [2, 0, 225],
        [2, 28, 15],
    ]


def test_complete_local_graph_and_packing_coverage() -> None:
    assert_identity()
    observed = {tuple(row[:2]) for row in x.local_weight_table()}
    pairs, triples = tuple(combinations(range(5), 2)), tuple(combinations(range(5), 3))
    expected: set[tuple[int, int]] = set()
    # Independent enumeration: all graph masks, then supported 0/1/2-triple choices.
    for mask in range(1024):
        edges = {p for i, p in enumerate(pairs) if mask >> i & 1}
        available = [i for i, t in enumerate(triples) if set(combinations(t, 2)) <= edges]
        expected.add((mask, 0))
        for i in available:
            expected.add((mask, 1 << i))
        for i, j in combinations(available, 2):
            if len(set(triples[i]) & set(triples[j])) == 1:
                expected.add((mask, (1 << i) | (1 << j)))
    assert observed == expected


def test_sts13_global_identity_known_exact_s5() -> None:
    triples, pairs = x.split.witness_supports("STS13")
    edges = {e for tau in triples for e in combinations(tau, 2)} | set(pairs)
    common, two = x.s5_counts(tuple(range(20)), edges, triples)
    assert (sum(comb(m, 2) for m in common), two) == (740, 120)
    assert (
        x.s5_identity_value(common, two)
        == 6860
        == (x.previous.higher_order_sums(triples, pairs)["S5"])
    )


def assert_caps() -> None:
    for pid, expected in EXPECTED.items():
        cap = x.degree_s5_cap(pid)
        assert [cap[k] for k in ("COMMON_PAIR_SUM_CAP", "N_2T_CAP", "S5_CAP")] == list(expected[:3])
        assert cap["D"] == list(map(int, pid))
        assert cap["G"] == [6 + v for v in map(int, pid)]


@pytest.mark.parametrize("pid", [OWNER1, OWNER2])
def test_independent_degree_threshold_optimization(pid: str) -> None:
    assert_caps()
    d = tuple(map(int, pid))
    cap = x.degree_s5_cap(d)
    # Min-degree histograms of the 22 supports: a necessary relaxation.
    # Each threshold obeys high-incidence and low-vertex constraints.
    # Independent descending recursion optimizes the weighted objective directly.
    best = -1

    def visit(k: int, remaining: int, above: int, score: int) -> None:
        nonlocal best
        if k == 0:
            if not remaining:
                best = max(best, score)
            return
        high = [v for v in d if v >= k]
        low = [v for v in d if 0 < v < k]
        for count in range(remaining + 1):
            tail = above + count
            if (
                3 * tail <= sum(high)
                and (len(high) >= 3 or tail == 0)
                and all(tail <= 22 - v for v in low)
            ):
                visit(k - 1, remaining - count, tail, score + count * comb(k + 4, 2))

    visit(6, 22, 0, 0)
    assert best == cap["COMMON_PAIR_SUM_CAP"]
    assert sum(comb(v, 2) for v in d) == cap["N_2T_CAP"]
    assert x.degree_s5_cap(tuple(reversed(d))) == cap
    assert [x.rows(t)[5] for t in x.rows(cap["THRESHOLD_CAPS"])] == (
        [22, 22, 22, 22, 18, 0] if pid == OWNER1 else [22, 21, 20, 20, 20, 6]
    )


def assert_bonferroni() -> None:
    proof = x.bonferroni_check()
    assert proof["R_CAP"] == 7
    for r in range(8):
        terms = [comb(r, k) for k in range(1, 6)]
        rhs = terms[0] - terms[1] + terms[2] - terms[3] + terms[4]
        assert rhs >= int(r > 0)
        assert x.rows(x.rows(proof["TABLE"])[r]) == [r, rhs, int(r > 0), rhs - int(r > 0)]


def test_safe_bonferroni_for_every_possible_winner_multiplicity() -> None:
    assert_bonferroni()
    assert comb(7, 2) // comb(3, 2) == 7
    # The fourth-order alternating truncation is unsafe at r=5; the S5 term repairs it.
    assert 5 - 10 + 10 - 5 == 0 < 1
    assert 5 - 10 + 10 - 5 + 1 == 1


def test_exact_integer_rounding_for_all_seven_residues() -> None:
    for s4 in range(285152, 285159):
        fourth, fifth = x.moment_bounds(5171824, s4, 7224)
        exact = x.event.K20_S1 - x.event.K20_S2 + 5171824 - Fraction(4 * s4, 7)
        assert fourth == -(-exact.numerator // exact.denominator)
        assert 0 <= fourth - exact < 1
        assert fifth == x.event.K20_S1 - x.event.K20_S2 + 5171824 - s4 + 7224


def assert_adoption(authority: x.Authority) -> None:
    for pid, expected in EXPECTED.items():
        row, proof = authority.ledger[pid], proof_for(pid, authority)
        cert = x.owner_certificate(pid, row, proof)
        assert [
            cert[k]
            for k in (
                "EXISTING_S4_FLOOR",
                "OLD_T264_BOUND",
                "NEW_T264_BOUND",
                "CERTIFIED_PROFILE_BOUND",
            )
        ] == list(expected[3:])
        old = x.split.route_b_terms(x.split.profile_values(pid), row.cap, row.s4_base)
        new = x.rows(cert["ALL_T_TERMS"])
        assert new[:-1] == [list(t) for t in old[:-1]]
        assert x.rows(new[-1])[2:] == list(old[-1][2:])
        assert cert["RETAINED_LOWER_T_COUNT"] == 242
        assert cert["RETAINED_LOWER_T_MAX"] == expected[-1]
        assert cert["RETAINED_TERMS_SHA256"] == x.digest(old[:-1])
        assert [x.rows(t)[0] for t in new] == list(range(22, 265))
        assert cert["CAP_SOURCE"] == row.source
        assert cert["CAP_SOURCE_IDENTITY"] == proof
        assert cert["NEW_T264_BOUND"] == min(
            expected[4], x.event.K20_S1 - x.event.K20_S2 + old[-1][5] - old[-1][4] + expected[2]
        )
        rational = x.event.K20_S1 - x.event.K20_S2 + old[-1][5] - Fraction(4 * old[-1][4], 7)
        assert 0 <= expected[4] - rational < 1
        assert cert["EXACT_INTEGER_GAIN"] == (old[-1][4] - 4 * old[-1][4] // 7 - expected[2])


def test_only_two_cap_terms_changed_no_double_count_and_exact_rounding(
    authority: x.Authority,
) -> None:
    assert_adoption(authority)


@pytest.mark.parametrize("pid", [OWNER1, OWNER2])
def test_cap_source_identity_and_tampering(pid: str, authority: x.Authority) -> None:
    row, proof = authority.ledger[pid], proof_for(pid, authority)
    x.check_cap(pid, row, proof)
    for bad in (
        replace(row, cap=263),
        replace(row, cap=264.0),
        replace(row, source="other"),
        replace(row, s4_base=row.s4_base + 1),
    ):
        with pytest.raises(AssertionError, match="cap-source identity"):
            x.check_cap(pid, bad, proof)
    with pytest.raises(AssertionError, match="sealed ledger"):
        x.owner_certificate(pid, replace(row, bound=row.bound + 1), proof)
    for key in proof:
        if key in (
            "ATTEMPT_INDEX",
            "PROFILE_IDS",
            "STATUS",
            "CERTIFICATE_KIND",
            "ROUTE",
            "WEDGE_COUNT",
            "TARGET_TRIANGLE_CAP",
            "REFUTED_GRAPH_TRIANGLE_COUNT",
            "CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND",
            "OPEN_WEDGE_CEILING_REFUTED",
            "CERTIFIED_OPEN_WEDGE_LOWER_BOUND",
        ):
            with pytest.raises(AssertionError, match="cap-source identity"):
                x.check_cap(pid, row, {**proof, key: None})


def test_family_max_owner_transition_and_coverage(
    authority: x.Authority, result: dict[str, object]
) -> None:
    start, final = x.object_row(result["START_FAMILY"]), x.object_row(result["FINAL_FAMILY"])
    assert start["FAMILY_UB"] == 313398920 and start["OWNER_IDS"] == [OWNER1]
    assert final["FAMILY_UB"] == 313398248
    assert result["REMAINING_GAP"] == 134360
    assert final["OWNER_IDS"] == [
        "66555555555531000000",
        "66655555554441000000",
        "66655555555422000000",
    ]
    assert start["COVERAGE"] == final["COVERAGE"]
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
    assert (start["CURSOR_ID"], start["CURSOR_BOUND"]) == (
        final["CURSOR_ID"],
        final["CURSOR_BOUND"],
    )
    assert result["OTHER_PROFILE_ROWS_UNCHANGED"] == 4645
    assert result["OTHER_ROWS_SHA256"] == x.digest(
        {pid: row.bound for pid, row in authority.ledger.items() if pid not in x.OWNER_SOURCES}
    )
    assert result["INHERITED_CERTIFICATES"] == authority.sealed["INHERITED_CERTIFICATES"]
    assert result["STS13_CERTIFICATE_SHA256"] == x.digest(authority.sealed["OWNER_CERTIFICATE"])
    assert result["STS13_ROW_UNCHANGED"] is True
    # Independent maximum over the actual inherited ledger plus both computed profiles and cursor.
    bounds = {pid: row.bound for pid, row in authority.ledger.items()}
    for pid in x.OWNER_SOURCES:
        bounds[pid] = x.integer(
            x.object_row(x.object_row(result["OWNER_CERTIFICATES"])[pid])["CERTIFIED_PROFILE_BOUND"]
        )
    bounds[x.chase.prior.CURSOR_ID] = x.chase.prior.CURSOR_BOUND
    maximum = max(bounds.values())
    assert maximum == final["FAMILY_UB"]
    assert sorted(pid for pid, b in bounds.items() if b == maximum) == final["OWNER_IDS"]
    first = x.integration.install(authority.ledger, OWNER1, EXPECTED[OWNER1][-1], "test")
    assert x.chase.family_state(first) == (313398532, [OWNER2])


def test_legal_p2_sts13_and_owner_witnesses(result: dict[str, object]) -> None:
    sound = x.object_row(result["WITNESS_SOUNDNESS"])
    assert sound["STATUS"] == "PASS"
    witnesses = x.object_row(sound["WITNESSES"])
    assert set(witnesses) == {OWNER1, OWNER2, "P2", "STS13"}
    for name, raw in witnesses.items():
        w = x.object_row(raw)
        assert w["STATUS"] == "PASS" and x.integer(w["EXACT_S5"]) <= x.integer(w["S5_CAP"])
        if name in x.OWNER_SOURCES:
            assert w["PROFILE_ID"] == name and x.integer(w["TRIANGLES"]) <= 264
    assert x.object_row(sound["STS13_EXACT_UNION"])["EXACT_ANY_PRIZE_UNION"] == 313263867


def test_witness_tripwire_rejects_unsound_owner_bound(authority: x.Authority) -> None:
    certs = {
        pid: x.owner_certificate(pid, authority.ledger[pid], proof_for(pid, authority))
        for pid in x.OWNER_SOURCES
    }
    certs[OWNER1]["NEW_T264_BOUND"] = 0
    with pytest.raises(AssertionError, match="legal owner witness"):
        x.witness_soundness(authority.ledger, certs)


@pytest.mark.parametrize("first", ["motif", "successor"])
def test_both_historical_import_orders_in_fresh_process(first: str) -> None:
    predecessor = x.motif.__name__
    successor = x.__name__
    order = (predecessor, successor) if first == "motif" else (successor, predecessor)
    script = (
        "import importlib; "
        f"importlib.import_module({order[0]!r}); "
        f"importlib.import_module({order[1]!r}); "
        f"x=importlib.import_module({successor!r}); "
        "a=x.load_authority(); "
        "assert a.sealed['FINAL_COMPLETE_FAMILY_UB']==313398920; "
        "assert len(x.motif.historical_provenance())==27"
    )
    env = {**os.environ, "PYTHONPATH": str(x.chase.ROOT / "src"), "PYTHONDONTWRITEBYTECODE": "1"}
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=x.chase.ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_certificate_and_immutable_result_tampering_rejected(
    authority: x.Authority, result: dict[str, object]
) -> None:
    pid, row, proof = OWNER1, authority.ledger[OWNER1], proof_for(OWNER1, authority)
    cert = x.owner_certificate(pid, row, proof)
    for key in ("NEW_T264_BOUND", "CERTIFIED_PROFILE_BOUND", "EXISTING_S4_FLOOR"):
        with pytest.raises(AssertionError, match="tampered Bonferroni5"):
            x.verify_certificate({**cert, key: x.integer(cert[key]) + 1}, pid, row, proof)
    for key in ("DEGREE_S5_PROOF", "CAP_SOURCE_IDENTITY"):
        bad = copy.deepcopy(cert)
        x.object_row(bad[key])["S5_CAP" if key == "DEGREE_S5_PROOF" else "STATUS"] = 0
        with pytest.raises(AssertionError, match="tampered Bonferroni5"):
            x.verify_certificate(bad, pid, row, proof)
    x.rows(x.rows(cert["ALL_T_TERMS"])[0])[1] = 0
    with pytest.raises(AssertionError, match="tampered Bonferroni5"):
        x.verify_certificate(cert, pid, row, proof)
    with pytest.raises(AssertionError, match="tampered immutable"):
        x.verify_result({**result, "FINAL_COMPLETE_FAMILY_UB": 313283936}, authority)
    x.verify_result(result, authority)
    if x.RESULT_PATH.exists():
        assert json.loads(x.RESULT_PATH.read_text()) == result
        with pytest.raises(AssertionError, match="already exists"):
            x.main()


MUTATIONS = {
    "wrong_s5_sign": ("s5_identity_value", "+ 2 * n2", "- 2 * n2"),
    "two_triple_k5_weight_14": ("s5_identity_value", "+ 2 * n2", "+ 0 * n2"),
    "require_external_edge": (
        "s5_counts",
        "if v not in tau",
        "if v not in tau and any(tuple(sorted((v,w))) in edges "
        "for w in vertices if w not in tau and w != v)",
    ),
    "drop_two_triple_correction": ("degree_s5_cap", "common_cap + 2 * n2_cap", "common_cap"),
    "copy_owner1_degrees": (
        "degree_s5_cap",
        "d = split.profile_values(profile)",
        "d = split.profile_values('66555555555540000000')",
    ),
    "wrong_high_incidence_divisor": ("degree_s5_cap", "sum(high) // 3", "sum(high) // 2"),
    "forget_low_vertex_constraint": ("degree_s5_cap", "22 - max(low, default=0)", "22"),
    "unsafe_fourth_truncation": ("bonferroni_check", "range(1, 6)", "range(1, 5)"),
    "round_fourth_bound_down": (
        "moment_bounds",
        "-(-exact.numerator // exact.denominator)",
        "exact.numerator // exact.denominator",
    ),
    "deduct_overlapping_credit": (
        "owner_certificate",
        "min(old_bound, fifth)",
        "min(old_bound, fifth) - (4 * s4) // 7",
    ),
    "take_weaker_bound": ("owner_certificate", "min(old_bound, fifth)", "max(old_bound, fifth)"),
    "drop_lower_t_terms": ("owner_certificate", "[*lower, (t, new_bound", "[(t, new_bound"),
    "cap_term_as_profile_bound": (
        "owner_certificate",
        "max(term[1] for term in terms)",
        "new_bound",
    ),
    "ignore_cap_source": (
        "check_cap",
        'row.source != f"{nb.RESULT_FILENAME}:NB_CERTIFICATES[{index}]"',
        "False",
    ),
    "ignore_witness_bound": (
        "witness_soundness",
        'fifth > integer(cert["NEW_T264_BOUND"])',
        "False",
    ),
}


@pytest.mark.parametrize("name", MUTATIONS)
def test_targeted_non_equivalent_mutations_killed(
    name: str, authority: x.Authority, monkeypatch: pytest.MonkeyPatch
) -> None:
    function, old, new = MUTATIONS[name]
    original = cast(Callable[..., object], getattr(x, function))
    source = inspect.getsource(original)
    assert source.count(old) == 1
    namespace: dict[str, object] = dict(vars(x))
    exec(compile(source.replace(old, new), f"<mutation:{name}>", "exec"), namespace)

    def guard() -> None:
        if function in ("s5_identity_value", "s5_counts"):
            test_local_five_ticket_weight_against_independent_label_oracle(
                ((0, 1, 2), (2, 3, 4)), (), 28
            )
            test_local_five_ticket_weight_against_independent_label_oracle(
                ((0, 1, 2),), ((3, 4),), 7
            )
        elif function == "degree_s5_cap":
            assert_caps()
        elif function == "bonferroni_check":
            assert_bonferroni()
        elif function == "moment_bounds":
            test_exact_integer_rounding_for_all_seven_residues()
        elif function == "check_cap":
            test_cap_source_identity_and_tampering(OWNER1, authority)
        elif function == "witness_soundness":
            test_witness_tripwire_rejects_unsound_owner_bound(authority)
        else:
            assert_adoption(authority)

    guard()
    with monkeypatch.context() as patch:
        patch.setattr(x, function, namespace[function])
        with pytest.raises((AssertionError, pytest.fail.Exception)):
            guard()
    guard()
