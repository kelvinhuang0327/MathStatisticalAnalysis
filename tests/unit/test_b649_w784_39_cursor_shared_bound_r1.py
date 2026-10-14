"""Independent arithmetic/census and live negative gates for all 39 W784 cursors."""

from __future__ import annotations

import json
import random
from collections import Counter
from collections.abc import Sequence
from copy import deepcopy
from fractions import Fraction
from itertools import combinations, combinations_with_replacement
from math import comb
from pathlib import Path
from typing import Any

import pytest

from lottolab.research import b649_w784_39_cursor_shared_bound_r1 as cert

type Record = dict[str, Any]


@pytest.fixture(scope="module")
def result() -> Record:
    return cert.compute_result()


def ceiling(value: Fraction) -> int:
    quotient, remainder = divmod(value.numerator, value.denominator)
    return quotient + bool(remainder)


def own_term(pid: str, t: int, floor: int = 112) -> cert.Term:
    d = list(map(int, pid))
    g = [6 + x for x in d]
    w = sum(x * (x - 1) // 2 for x in g)
    opened = w - 3 * t
    k4 = max(0, ceiling(Fraction(sum(comb(x, 3) for x in g) - (max(g) - 2) * opened, 4)))
    a = min(k4, sum(x * (x + 4) for x in d) // 3)
    s4 = max(floor, 448 * a + 679 * (k4 - a))
    s3 = 2800 * opened + 20272 * (t - 22) + 154000
    exact = Fraction(372228640 - 63838600 + s3) - Fraction(4 * s4, 7)
    return t, ceiling(exact), k4, a, s4, s3


def local_count(n: int, masks: dict[int, int]) -> int:
    """Seven-label sets with >=3 hits; each has seven main/special assignments."""
    masks = {**masks, 0: 49 - sum(masks.values())}
    states = {(0, (0,) * n): 1}
    for mask, multiplicity in masks.items():
        updated: dict[tuple[int, tuple[int, ...]], int] = {}
        for (drawn, hits), ways in states.items():
            for take in range(min(multiplicity, 7 - drawn) + 1):
                new_hits = tuple(
                    min(3, h + take * bool(mask & (1 << v))) for v, h in enumerate(hits)
                )
                key = drawn + take, new_hits
                updated[key] = updated.get(key, 0) + ways * comb(multiplicity, take)
        states = updated
    return 7 * states.get((7, (3,) * n), 0)


def test_all_source_pins_and_accepted_input_replay(result: Record) -> None:
    fixed, prior, base = cert.fixed_input()
    assert cert.git("rev-parse", cert.INPUT_HEAD + "^{tree}") == cert.INPUT_TREE
    assert cert.git("rev-parse", cert.UPSTREAM_HEAD + "^{tree}") == cert.UPSTREAM_TREE
    assert cert.git("rev-parse", cert.BASE_HEAD + "^{tree}") == cert.BASE_TREE
    assert result["EVALUATOR_SOURCE_PINS"] == prior["SOURCE_PINS"]
    assert len(result["EVALUATOR_SOURCE_PINS"]) == 22
    assert result["FAMILY_BEFORE"] == fixed["FAMILY_AFTER"]
    assert result["OWNER_IDS"] == fixed["ALL_NEW_MAX_OWNERS"]
    assert cert.ids_digest(result["OWNER_IDS"]) == cert.OWNER_ORDER_SHA
    assert base["ALL_T_BONFERRONI_5_ADOPTION"] == "NOT_VERIFIED"


def test_independent_histogram_census_and_exact_coverage(result: Record) -> None:
    raw: dict[str, int] = {}
    for combo in combinations_with_replacement(range(7), 20):
        if sum(combo) == 66:
            raw["".join(map(str, reversed(combo)))] = sum(comb(6 + x, 2) for x in combo)
    assert len(raw) == 5126
    cursor = result["CURSOR_ROW_BOUNDS_BEFORE"]
    owners = result["OWNER_IDS"]
    assert set(cursor) == {p for p, w in raw.items() if w <= 785} and len(cursor) == 197
    assert set(owners) == {p for p, w in raw.items() if w == 784} and len(owners) == 39
    assert sum(w == 785 for w in raw.values()) == 41
    resolved = result["RESOLVED_ROWS"]
    excluded = set(raw) - set(cursor) - set(resolved)
    assert len(resolved) == 4647 and len(excluded) == 282
    assert excluded == set(result["CURSOR_COVERAGE"]["EXCLUDED_IDS"])
    assert (
        cert.upstream.ids_digest(list(excluded))
        == result["INHERITED_EXCLUSION"]["ORIGINAL_CONDITIONS_VERBATIM"]["IDS_SHA256"]
    )
    assert not set(cursor) & set(resolved)


def test_model_local_counts_and_pointwise_union_inequality() -> None:
    assert 20 * local_count(1, {1: 6}) == 372228640
    assert 93 * local_count(2, {3: 1, 1: 5, 2: 5}) + 97 * local_count(2, {1: 6, 2: 6}) == 63838600
    assert local_count(3, {3: 1, 6: 1, 1: 5, 2: 4, 4: 5}) == 2800
    assert local_count(3, {3: 1, 5: 1, 6: 1, 1: 4, 2: 4, 4: 4}) == 20272
    assert local_count(3, {7: 1, 1: 5, 2: 5, 4: 5}) == 7000
    assert local_count(4, {7: 1, 9: 1, 10: 1, 12: 1, 1: 4, 2: 4, 4: 4, 8: 3}) == 448
    assert local_count(4, {3: 1, 5: 1, 6: 1, 9: 1, 10: 1, 12: 1, 1: 3, 2: 3, 4: 3, 8: 3}) == 679
    for r in range(8):
        rhs = r - comb(r, 2) + comb(r, 3) - Fraction(4 * comb(r, 4), 7)
        assert int(r > 0) <= rhs


def test_every_degree_premise_and_all_9360_terms_independently(result: Record) -> None:
    total = 0
    for pid in result["OWNER_IDS"]:
        p = result["PER_CURSOR"][pid]
        d = tuple(map(int, pid))
        assert sum(d) == 66 and sum(x * x for x in d) == 242
        assert sum(x * (x + 4) for x in d) == 506 and p["A_MAX"] == 168
        assert 3 * 168 <= 506 < 3 * 169
        assert p["INACTIVE_TICKETS"] == d.count(0) in (0, 1)
        assert p["SUM_C_G_3"] == sum(comb(6 + x, 3) for x in d)
        assert p["G_MAX"] == 6 + max(d) <= 12
        assert p["T_RANGE"] == [22, 261] and p["TERM_COUNT"] == 240
        own = [own_term(pid, t) for t in range(22, 262)]
        assert p["ALL_T_TERMS"] == own
        assert cert.sha(cert.render(own)) == p["ALL_T_TERMS_SHA256"]
        maximum = max(t[1] for t in own)
        assert p["NEW_BOUND"] == p["MAXIMUM"] == maximum < p["OLD_BOUND"] == 313391784
        assert p["ALL_ARGMAX"] == [t for t in own if t[1] == maximum]
        assert maximum == max(own_term(pid, t, 0)[1] for t in range(22, 262))
        coarse_exact = Fraction(372228640 - 63838600 + 2800 + 20272 * 239 + 154000) - Fraction(
            448, 7
        )
        assert ceiling(coarse_exact) == p["OLD_BOUND"]
        total += len(own)
    assert total == result["TOTAL_TERM_COUNT"] == 9360
    assert Counter(p["NEW_BOUND"] for p in result["PER_CURSOR"].values()) == {
        313222352: 5,
        313222740: 16,
        313223128: 14,
        313223516: 4,
    }


def test_shared_class_envelope_and_all_argmax(result: Record) -> None:
    shared = result["SHARED_THEOREM"]
    assert shared["J_MIN"] == min(p["SUM_C_G_3"] for p in result["PER_CURSOR"].values()) == 1971
    expected: list[cert.Term] = []
    for t in range(22, 262):
        k4 = max(0, ceiling(Fraction(1971 - 10 * (784 - 3 * t), 4)))
        a = min(k4, 168)
        s4 = max(112, 448 * a + 679 * (k4 - a))
        s3 = 2800 * (784 - 3 * t) + 20272 * (t - 22) + 154000
        bound = ceiling(Fraction(308390040 + s3) - Fraction(4 * s4, 7))
        expected.append((t, bound, k4, a, s4, s3))
    assert shared["ALL_T_TERMS"] == expected
    maximum = max(t[1] for t in expected)
    assert shared["BOUND"] == maximum < 313391784
    assert shared["ALL_ARGMAX"] == [t for t in expected if t[1] == maximum]
    for p in result["PER_CURSOR"].values():
        assert all(a[1] >= b[1] for a, b in zip(expected, p["ALL_T_TERMS"], strict=True))


def test_k4_and_contained_k4_combinatorial_bounds_on_small_configurations() -> None:
    rng = random.Random(78439)
    for _ in range(80):
        n = 8
        supports: list[tuple[int, ...]] = []
        used: set[tuple[int, int]] = set()
        for triple in rng.sample(list(combinations(range(n), 3)), 12):
            pairs = set(combinations(triple, 2))
            if not pairs & used:
                supports.append(triple)
                used |= pairs
        edges = used | {e for e in combinations(range(n), 2) if rng.random() < 0.3}
        g = [sum(v in e for e in edges) for v in range(n)]
        d = [sum(v in s for s in supports) for v in range(n)]
        triangles = sum(set(combinations(s, 2)) <= edges for s in combinations(range(n), 3))
        quartets = [s for s in combinations(range(n), 4) if set(combinations(s, 2)) <= edges]
        w = sum(comb(x, 2) for x in g)
        assert len(supports) <= triangles <= w // 3
        assert 4 * len(quartets) >= sum(comb(x, 3) for x in g) - (max(g) - 2) * (w - 3 * triangles)
        assert all(sum(set(s) <= set(q) for s in supports) <= 1 for q in quartets)
        a = sum(any(set(s) <= set(q) for s in supports) for q in quartets)
        assert a <= min(len(quartets), sum(x * (y - 2) for x, y in zip(d, g, strict=True)) // 3)


def test_full_ledger_aggregation_and_preservation(result: Record) -> None:
    fixed, _, _ = cert.fixed_input()
    resolved = result["RESOLVED_ROWS"]
    before, after = result["CURSOR_ROW_BOUNDS_BEFORE"], result["CURSOR_ROW_BOUNDS_AFTER"]
    owners = set(result["OWNER_IDS"])
    assert resolved == fixed["RESOLVED_ROWS_AFTER"] and len(resolved) == 4647
    assert len(before) == len(after) == 197 and set(before) == set(after)
    assert {p: b for p, b in after.items() if p not in owners} == {
        p: b for p, b in before.items() if p not in owners
    }
    assert sum(before[p] != after[p] for p in before) == 39
    merged = resolved | after
    levels = sorted(set(merged.values()), reverse=True)
    assert result["FAMILY_AFTER"]["MAXIMUM"] == levels[0] == 313391740
    assert result["NEXT_DISTINCT_BOUND"] == levels[1]
    assert result["ALL_NEW_MAX_OWNERS"] == sorted(p for p, b in merged.items() if b == levels[0])
    assert result["FAMILY_DELTA"] == 44 and result["GAP_TO_INCUMBENT"] == levels[0] - 313263888
    for key in ("INHERITED_EXCLUSION", "INHERITED_CAVEATS_REFERENCE"):
        assert result[key] == fixed[key]
    assert result["HISTORICAL_CERTIFICATES_RECERTIFIED"] is False
    assert result["S5_USED"] is False
    assert result["SOLVER_CALLS"] == result["FULL_SUPPORT_GRAPHS_ENUMERATED"] == 0
    assert result["PORTFOLIOS_ENUMERATED"] == 0


@pytest.mark.parametrize("pid", ["44444444444443332210", "65555555555531100000", "", "0123"])
def test_negative_wrong_histogram_or_w_class(result: Record, pid: str) -> None:
    with pytest.raises(ValueError, match="wrong histogram/W class"):
        cert.theorem(pid, result["OWNER_IDS"])
    if len(pid) == 20:
        with pytest.raises(ValueError, match="wrong histogram/W class"):
            cert.theorem(pid, [pid])


@pytest.mark.parametrize(
    "case", ["missing_owner", "wrong_owner", "wrong_cursor", "order", "resolved"]
)
def test_negative_coverage(result: Record, case: str) -> None:
    cursor, owners, resolved = (
        list(result["CURSOR_ROW_BOUNDS_BEFORE"]),
        list(result["OWNER_IDS"]),
        list(result["RESOLVED_ROWS"]),
    )
    if case == "missing_owner":
        owners.pop()
    elif case == "wrong_owner":
        owners[-1] = next(p for p in cursor if p not in owners)
    elif case == "wrong_cursor":
        cursor[-1] = resolved[0]
    elif case == "order":
        owners.reverse()
    else:
        resolved[0] = owners[0]
    with pytest.raises(ValueError):
        cert.coverage(cursor, owners, resolved)


@pytest.mark.parametrize("cap", [260, 250, 262, True])
def test_negative_shrunk_or_wrong_triangle_range(result: Record, cap: int) -> None:
    f = next(iter(result["PER_CURSOR"].values()))
    with pytest.raises(ValueError, match="universal triangle range"):
        cert.validate_envelope(f, cap, 112, f["ALL_T_TERMS"])


@pytest.mark.parametrize("at", [0, 120, 239])
def test_negative_missing_envelope_term(result: Record, at: int) -> None:
    f = next(iter(result["PER_CURSOR"].values()))
    terms = f["ALL_T_TERMS"]
    with pytest.raises(ValueError, match="incomplete envelope"):
        cert.validate_envelope(f, 261, 112, terms[:at] + terms[at + 1 :])


@pytest.mark.parametrize(
    "column,delta,message",
    [
        (2, -1, "K4 ceiling"),
        (2, 1, "K4 ceiling"),
        (3, 1, "A_max contained-K4"),
        (3, -1, "A_max contained-K4"),
        (4, 112, "S4 MAX floor"),
        (4, -1, "S4 MAX floor"),
        (5, 1, "S3 identity"),
        (1, -1, "Fraction ceiling"),
    ],
)
def test_negative_corrupted_math_term(
    result: Record, column: int, delta: int, message: str
) -> None:
    f = next(iter(result["PER_CURSOR"].values()))
    terms = [list(t) for t in f["ALL_T_TERMS"]]
    terms[-1][column] += delta
    with pytest.raises(ValueError, match=message):
        cert.validate_envelope(f, 261, 112, terms)


def test_negative_fraction_floor_in_a_nonintegral_credit(result: Record) -> None:
    f = next(iter(result["PER_CURSOR"].values()))
    probe = cert.envelope(f, 113)
    first = probe[0]
    exact = Fraction(308390040 + first[5]) - Fraction(4 * first[4], 7)
    assert exact.denominator == 7 and first[1] == exact.numerator // 7 + 1
    bad = [list(t) for t in probe]
    bad[0][1] = exact.numerator // 7
    with pytest.raises(ValueError, match="Fraction ceiling"):
        cert.validate_envelope(f, 261, 113, bad)


@pytest.mark.parametrize(
    "j,top,a_max,floor",
    [(1972, 12, 168, 112), (1971, 11, 168, 112), (1971, 12, 169, 112), (1971, 12, 168, 113)],
)
def test_negative_class_constants(result: Record, j: int, top: int, a_max: int, floor: int) -> None:
    with pytest.raises(ValueError):
        cert.class_envelope(result["PER_CURSOR"], result["OWNER_IDS"], j, top, a_max, floor)


def test_negative_wrong_base_s4_floor(result: Record, monkeypatch: pytest.MonkeyPatch) -> None:
    def damaged_floor(_: tuple[int, ...]) -> int:
        return 113

    monkeypatch.setattr(cert.route.r28, "profile_s4_floor", damaged_floor)
    with pytest.raises(ValueError, match="floor applicability"):
        cert.compute_result()


@pytest.mark.parametrize(
    "case", ["delete_resolved", "duplicate_resolved", "delete_cursor", "duplicate_cursor"]
)
def test_negative_deleted_or_duplicate_ledger_rows(result: Record, case: str) -> None:
    expected = (
        result["RESOLVED_ROWS"] if case.endswith("resolved") else result["CURSOR_ROW_BOUNDS_AFTER"]
    )
    rows = list(expected.items())
    if case.startswith("delete"):
        rows.pop()
    else:
        rows[-1] = rows[0]
    with pytest.raises(ValueError, match="ledger row count/duplicate"):
        cert.checked_rows(rows, expected)


def test_negative_duplicate_json_row() -> None:
    with pytest.raises(ValueError, match="duplicate JSON/ledger row"):
        cert.decode(b'{"rows":{"p":1,"p":2}}')


def test_negative_every_partial_owner_replacement(result: Record) -> None:
    owners = result["OWNER_IDS"]
    cursor, resolved = result["CURSOR_ROW_BOUNDS_BEFORE"], result["RESOLVED_ROWS"]
    new = {p: result["PER_CURSOR"][p]["NEW_BOUND"] for p in owners}
    for omitted in owners:
        partial = {p: b for p, b in new.items() if p != omitted}
        with pytest.raises(ValueError, match="all 39"):
            cert.replace_owners(cursor, partial, owners)
        actual = cert.family_summary(resolved, cursor | partial)
        assert actual["MAXIMUM"] == 313391784 and actual["ALL_MAX_OWNERS"] == [omitted]
        assert (
            cert.family_status(result["FAMILY_BEFORE"], actual, partial, owners)
            == "NO_PROVEN_FAMILY_GAIN"
        )
        assert (
            cert.family_status(result["FAMILY_BEFORE"], {"MAXIMUM": 1}, partial, owners)
            == "NO_PROVEN_FAMILY_GAIN"
        )
    with pytest.raises(ValueError, match="strict owner"):
        cert.replace_owners(cursor, new | {owners[0]: cursor[owners[0]]}, owners)


@pytest.mark.parametrize("kind", ["git", "result_sha", "source_sha"])
def test_negative_live_pin_corruption(kind: str, monkeypatch: pytest.MonkeyPatch) -> None:
    if kind == "git":
        original = cert.git

        def damaged_git(*args: str, repo: Path = cert.ROOT) -> str:
            raw = original(*args, repo=repo)
            return "0" * 40 if args == ("rev-parse", cert.INPUT_HEAD + "^{tree}") else raw

        monkeypatch.setattr(cert, "git", damaged_git)
        with pytest.raises(ValueError, match="Git TREE pin"):
            cert.compute_result()
    else:
        original_blob = cert.blob
        target = cert.INPUT_RESULT if kind == "result_sha" else cert.upstream.SOURCE

        def damaged_blob(head: str, path: str, repo: Path = cert.ROOT) -> bytes:
            raw = original_blob(head, path, repo)
            return raw + b"\n" if path == target else raw

        monkeypatch.setattr(cert, "blob", damaged_blob)
        with pytest.raises(ValueError, match="SHA pin"):
            cert.compute_result()


@pytest.mark.parametrize(
    "case", ["missing_owner", "triangle_range", "term", "argmax", "ledger", "exclusion", "gain"]
)
def test_negative_complete_payload_tampering(result: Record, case: str) -> None:
    bad = deepcopy(result)
    pid = bad["OWNER_IDS"][0]
    if case == "missing_owner":
        bad["PER_CURSOR"].pop(pid)
    elif case == "triangle_range":
        bad["PER_CURSOR"][pid]["T_RANGE"][1] -= 1
    elif case == "term":
        bad["PER_CURSOR"][pid]["ALL_T_TERMS"].pop(120)
    elif case == "argmax":
        bad["PER_CURSOR"][pid]["ALL_ARGMAX"] = []
    elif case == "ledger":
        bad["CURSOR_ROW_BOUNDS_AFTER"][pid] = bad["CURSOR_ROW_BOUNDS_BEFORE"][pid]
    elif case == "exclusion":
        bad["INHERITED_EXCLUSION"]["ORIGINAL_CONDITIONS_VERBATIM"]["COUNT"] -= 1
    else:
        bad["FAMILY_DELTA"] += 1
    with pytest.raises(ValueError, match="complete recomputation"):
        cert.validate_payload(bad, result)


def test_stored_result_exact_recomputation(result: Record) -> None:
    cert.verify_result()
    stored = json.loads((cert.ROOT / cert.RESULT).read_bytes())
    assert cert.render(stored) == cert.render(result)
    for rows in (stored["PER_CURSOR"].values(),):
        for p in rows:
            assert isinstance(p["ALL_T_TERMS"], Sequence)
