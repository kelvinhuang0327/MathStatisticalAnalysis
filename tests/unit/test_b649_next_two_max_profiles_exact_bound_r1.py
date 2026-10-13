"""Focused proof arithmetic, realization soundness, envelopes, projection and rejection gates."""

from __future__ import annotations

import random
from collections.abc import Sequence
from copy import deepcopy
from dataclasses import replace
from fractions import Fraction
from math import comb
from typing import cast

import pytest

from lottolab.research import b649_next_two_max_profiles_exact_bound_r1 as cert

A, B = cert.TARGETS
CAPS = {A: 228, B: 252}


@pytest.fixture(scope="module")
def result() -> dict[str, object]:
    return cert.compute_result()


def realize(target: list[int], rng: random.Random, tries: int) -> cert.Realization | None:
    """Random linear 2/3 support system whose ticket v carries exactly target[v] triples."""
    for _ in range(tries):
        need, covered = list(target), set[tuple[int, int]]()
        triples: list[tuple[int, int, int]] = []
        for _ in range(cert.MODEL.triples):
            chosen: list[int] = []
            for _ in range(60):
                chosen = []
                for _ in range(3):
                    pool = [
                        v
                        for v in range(20)
                        if need[v] > 0
                        and v not in chosen
                        and all((min(u, v), max(u, v)) not in covered for u in chosen)
                    ]
                    if not pool:
                        break
                    if not chosen:  # Anchor on a most-constrained vertex.
                        top = max(need[v] for v in pool)
                        pool = [v for v in pool if need[v] == top]
                    chosen.append(rng.choices(pool, weights=[need[v] for v in pool])[0])
                if len(chosen) == 3:
                    break
            if len(chosen) != 3:
                break
            a, b, c = sorted(chosen)
            triples.append((a, b, c))
            covered |= {(a, b), (a, c), (b, c)}
            for v in chosen:
                need[v] -= 1
        if len(triples) != cert.MODEL.triples:
            continue
        for _ in range(40):  # Retry only the pair completion on this triple layout.
            pairs = complete_pairs(target, covered, rng)
            if pairs is not None:
                return cert.Realization(tuple(triples), pairs)
    return None


def complete_pairs(
    target: list[int], covered: set[tuple[int, int]], rng: random.Random
) -> tuple[tuple[int, int], ...] | None:
    free, used = [6 - v for v in target], set(covered)
    pairs: list[tuple[int, int]] = []
    for _ in range(cert.MODEL.pairs):
        open_ = [v for v in range(20) if free[v] > 0]
        if not open_:
            return None
        a = max(open_, key=lambda v: (free[v], rng.random()))
        pool = [v for v in open_ if v != a and (min(a, v), max(a, v)) not in used]
        if not pool:
            return None
        b = rng.choices(pool, weights=[free[v] for v in pool])[0]
        edge = (min(a, b), max(a, b))
        pairs.append(edge)
        used.add(edge)
        free[a] -= 1
        free[b] -= 1
    return tuple(pairs) if not any(free) else None


@pytest.mark.parametrize(
    "pid,core,zeros,constant,floor,low",
    [(A, 14, 6, 240, 1, [3, 3, 2]), (B, 15, 5, 234, 2, [4, 2, 1, 1])],
)
def test_exact_profile_constants_rederived(
    pid: str, core: int, zeros: int, constant: int, floor: int, low: list[int]
) -> None:
    proof = cert.theorem(pid)
    d = [int(c) for c in pid]
    g = [6 + v for v in d]
    assert sum(comb(v, 2) for v in g) == proof["WEDGES"] == 828
    assert comb(20, 3) - (19 * sum(g) - sum(v * v for v in g)) // 2 == proof["GOODMAN_SUM"] == 294
    assert proof["SUPPORT_EDGES"] == 93 and sum(g) == 186
    assert proof["DEGREE_SUM_OF_D"] == sum(d) == 66 and proof["VERTICES"] == 20
    assert (proof["CORE_K"], proof["ZERO_Z"]) == (core, zeros) == (20 - d.count(0), d.count(0))
    assert proof["SPLIT_CONSTANT"] == 294 - 3 * zeros * (core - 11) == constant
    assert proof["ZETA_RANGE"] == [floor, 6] and proof["LOW_L_DEGREES"] == low
    assert (proof["H5_COUNT"], proof["H6_COUNT"]) == (8, 3)
    assert proof["COMPLETENESS"] == "NOT_APPLICABLE — ANALYTIC_BOUND"


@pytest.mark.parametrize(
    "pid", ["66555555555431100000", "65555555555532000000", "66655555555332000001", "", "6" * 20]
)
def test_wrong_or_relabelled_profile_rejected(pid: str) -> None:
    with pytest.raises(ValueError, match="exact profile"):
        cert.theorem(pid)


@pytest.mark.parametrize(
    "pid,change,message",
    [
        (A, {"wedges": 825}, "wedge"),
        (B, {"wedges": 825}, "wedge"),
        (B, {"goodman": 291}, "Goodman"),
        (B, {"core": 14, "zeros": 6}, "K/Z partition"),
        (A, {"core": 15, "zeros": 5}, "K/Z partition"),
        (A, {"split_constant": 237}, "split constant"),
        (B, {"split_constant": 240}, "split constant"),
        (B, {"zeta_floor": 1}, "zeta range"),
    ],
)
def test_wrong_wedge_goodman_partition_or_constant_rejected(
    pid: str, change: dict[str, int], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        cert.theorem(pid, replace(cert.CLAIMS[pid], **change))


@pytest.mark.parametrize(
    "changes",
    [{"tickets": 19}, {"labels": 48}, {"triples": 21}, {"pair_linearity": False}],
)
def test_wrong_support_assumptions_rejected(changes: dict[str, object]) -> None:
    with pytest.raises(ValueError, match="support assumptions"):
        cert.theorem(A, assumptions=replace(cert.MODEL, **changes))


def test_relaxation_caps_and_all_argmax_states() -> None:
    a, b = cert.relaxation(A), cert.relaxation(B)
    assert (a["CAP"], b["CAP"]) == (228, 252)
    states_a = cast(list[dict[str, object]], a["ALL_ARGMAX_STATES"])
    states_b = cast(list[dict[str, object]], b["ALL_ARGMAX_STATES"])
    assert [s["SIGMA_LOW"] for s in states_a] == [[2, 0, 4], [0, 2, 4]]
    assert all(s["ZETA"] == [1] * 6 and s["VALUE"] == 228 for s in states_a)
    assert len(states_b) == 1 and states_b[0]["SIGMA_LOW"] == [0, 0, 5, 5]
    assert states_b[0]["ZETA"] == [2] * 5 and states_b[0]["MIN_LOW_PENALTY"] == 2
    for pid, states in ((A, states_a), (B, states_b)):
        sh = cert.shape([int(c) for c in pid])
        for s in states:
            upper = cert.head(
                sh,
                cast(list[int], s["SIGMA_LOW"]),
                cert.integer(s["D5"]),
                cast(list[int], s["ZETA"]),
            )
            assert upper == s["UPPER_WITHOUT_PENALTIES"]
            low, zero = cert.integer(s["MIN_LOW_PENALTY"]), cert.integer(s["MIN_ZERO_PENALTY"])
            assert upper - zero - low == s["VALUE"] == CAPS[pid]


def test_ablation_records_load_bearing_ingredients() -> None:
    assert set(cert.ablation(A).values()) == {228}
    assert cert.ablation(B) == {
        "ALL": 252,
        "WITHOUT_ZERO_TRIANGLES": 260,
        "WITHOUT_LOW_PAIR_OVERLAP": 253,
        "WITHOUT_D5_OVERLAP": 256,
        "WITHOUT_CODEGREE": 256,
        "WITHOUT_DEGREE_BUDGET": 258,
        "NO_PENALTY": 270,
    }


@pytest.mark.parametrize("pid", cert.TARGETS)
def test_exact_profile_realizations_obey_split_and_every_penalty(pid: str) -> None:
    rng = random.Random(649 + cert.TARGETS.index(pid))
    seen = 0
    while seen < 2:
        real = realize([int(c) for c in pid], rng, 20000)
        assert real is not None
        audit = cert.audit(real)
        assert audit["SPLIT_CONSTANT"] == cert.CLAIMS[pid].split_constant
        assert audit["T"] <= audit["STATE_BOUND"] and audit["T"] <= CAPS[pid]
        assert audit["LOWER_Z"] == audit["T_N"] + audit["C_K"]
        seen += 1


def test_random_profiles_obey_split_and_every_penalty() -> None:
    rng = random.Random(2026)
    audited = 0
    while audited < 6:
        target = [0] * 20
        for _ in range(66):
            target[rng.choice([v for v in range(20) if target[v] < 6])] += 1
        real = realize(target, rng, 60)
        if real is None:
            continue
        audit = cert.audit(real)
        assert audit["T"] <= audit["STATE_BOUND"]
        audited += 1


def test_every_remainder_term_is_needed_and_mutations_are_caught(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real = realize([int(c) for c in B], random.Random(7), 20000)
    assert real is not None
    audit = cert.audit(real)
    exact_head = audit["T"] + audit["P"]
    for part in ("T_M", "T_N", "C_Z", "C_K"):
        if audit[part]:
            assert exact_head - (audit["P"] - audit[part]) != audit["T"]
    assert audit["T_M"] and audit["C_Z"]
    original = cert.zero_penalty

    def inflated(bits: Sequence[int], nonedges: Sequence[cert.Pair]) -> int:
        return original(bits, nonedges) + 1

    monkeypatch.setattr(cert, "zero_penalty", inflated)
    with pytest.raises(ValueError, match=r"\(Z\) is not exact"):
        cert.audit(real)
    monkeypatch.setattr(cert, "zero_penalty", original)
    exact_shape = cert.shape

    def shifted(profile: list[int]) -> cert.Shape:
        sh = exact_shape(profile)
        return replace(sh, constant=sh.constant + 1)

    monkeypatch.setattr(cert, "shape", shifted)
    with pytest.raises(ValueError, match="exact split identity"):
        cert.audit(real)


def test_full_envelopes_and_regression(result: dict[str, object]) -> None:
    rows = cast(list[dict[str, object]], result["CERTIFICATES"])
    assert [r["PROFILE_ID"] for r in rows] == list(cert.TARGETS)
    assert [r["OLD_T_CAP"] for r in rows] == [265, 265]
    assert [r["NEW_T_CAP"] for r in rows] == [228, 252]
    assert [r["OLD_BOUND"] for r in rows] == [313395060, 313395060]
    for row in rows:
        pid = cert.string(row["PROFILE_ID"])
        s4 = cert.integer(cert.obj(row["S4_AUTHORITY"])["INHERITED_FLOOR"])
        assert s4 == 112
        assert cert.obj(row["S5_AUTHORITY"])["USED"] is False
        assert cert.obj(row["S5_AUTHORITY"])["VALUE"] is None
        assert row["ROW_DELTA"] == cert.integer(row["OLD_BOUND"]) - cert.integer(row["NEW_BOUND"])
        assert cert.integer(row["NEW_BOUND"]) < 313394776
        for prefix in ("OLD", "NEW"):
            cap = cert.integer(row[f"{prefix}_T_CAP"])
            terms = cast(list[cert.Term], row[f"{prefix}_ALL_T_TERMS"])
            cert.validate_envelope(pid, cap, s4, terms)
            assert len(terms) == row[f"{prefix}_TERM_COUNT"] == cap - 21
            peak = max(t[1] for t in terms)
            assert [t for t in terms if t[1] == peak] == row[f"{prefix}_ALL_ARGMAX"]


def test_fractional_rounding_probe_detects_floor() -> None:
    terms = cert.envelope(B, 252, 113)
    t = terms[0]
    exact = Fraction(cert.route.K20_S1 - cert.route.K20_S2 + t[5]) - Fraction(4 * t[4], 7)
    assert exact.denominator == 7
    altered = list(terms)
    altered[0] = (t[0], exact.numerator // exact.denominator, *t[2:])
    with pytest.raises(ValueError, match="ceiling rounding"):
        cert.validate_envelope(B, 252, 113, altered)


@pytest.mark.parametrize("index", range(2))
@pytest.mark.parametrize("prefix", ("OLD", "NEW"))
def test_any_missing_term_or_endpoint_rejected(
    result: dict[str, object], index: int, prefix: str
) -> None:
    row = cast(list[dict[str, object]], result["CERTIFICATES"])[index]
    terms = cast(list[cert.Term], row[f"{prefix}_ALL_T_TERMS"])
    for omitted in range(len(terms)):
        with pytest.raises(ValueError, match="incomplete T envelope"):
            cert.validate_envelope(
                cert.string(row["PROFILE_ID"]),
                cert.integer(row[f"{prefix}_T_CAP"]),
                112,
                terms[:omitted] + terms[omitted + 1 :],
            )


def test_wrong_cap_rejected(result: dict[str, object]) -> None:
    row = cast(list[dict[str, object]], result["CERTIFICATES"])[1]
    terms = cast(list[cert.Term], row["NEW_ALL_T_TERMS"])
    for cap in (251, 253):
        with pytest.raises(ValueError, match="incomplete T envelope"):
            cert.validate_envelope(B, cap, 112, terms)
    with pytest.raises(ValueError, match="wrong profile"):
        cert.validate_envelope("66555555555431100000", 252, 112, terms)


def test_duplicate_and_missing_resolved_row_rejected(result: dict[str, object]) -> None:
    ledger = cast(dict[str, int], result["RESOLVED_ROW_BOUNDS_AFTER"])
    rows = list(ledger.items())
    for changed in (rows + rows[:1], rows[:-1], rows[:-1] + rows[:1]):
        with pytest.raises(ValueError, match="resolved rows"):
            cert.r2.checked_rows(changed, ledger)
    with pytest.raises(ValueError, match="duplicate JSON"):
        cert.decode(b'{"row":1,"row":2}')


def test_pin_and_source_damage_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(ValueError, match="blob pin"):
        cert.blob(cert.CERTIFICATE_HEAD, cert.R2_RESULT, "0" * 64)
    with pytest.raises(ValueError, match="tree pin"):
        cert.identity(cert.CERTIFICATE_HEAD, cert.IMPLEMENTATION_TREE)
    original = cert.r2.git

    def damaged(*args: str) -> bytes:
        raw = original(*args)
        if args[0] == "show" and args[1].endswith(cert.r2.SOURCE):
            return raw + b"\n"
        return raw

    monkeypatch.setattr(cert.r2, "git", damaged)
    with pytest.raises(ValueError, match="blob pin"):
        cert.r2_fixed_input()


def test_evaluator_source_drift_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    original = cert.r2.git

    def damaged(*args: str) -> bytes:
        raw = original(*args)
        if args[0] == "show" and args[1].endswith(
            "src/lottolab/research/b649_k20_min_s2_route_b_current_owner_refinement_r32.py"
        ):
            return raw + b"\n"
        return raw

    monkeypatch.setattr(cert.r2, "git", damaged)
    with pytest.raises(ValueError, match="evaluator differs"):
        cert.r2.source_pins()


def test_family_scans_all_rows_and_preserves_cursor(result: dict[str, object]) -> None:
    after = cast(dict[str, int], result["RESOLVED_ROW_BOUNDS_AFTER"])
    assert len(after) == result["RESOLVED_ROWS"] == 4647
    assert sorted(cast(dict[str, object], result["ROW_CHANGES"])) == sorted(cert.TARGETS)
    assert result["OTHER_ROWS_UNCHANGED"] == 4645
    cursor = cert.obj(result["CURSOR"])
    coarse = cast(dict[str, int], cursor["COARSE_BOUND_PROJECTION"])
    assert len(coarse) == result["CURSOR_COUNT"] == 197
    assert max(coarse.values()) == result["CURSOR_MAXIMUM"] == 313394584
    first = cert.obj(result["PROJECTED_FAMILY_BEFORE"])
    last = cert.obj(result["PROJECTED_FAMILY_AFTER"])
    assert last == cert.r2.family(after, coarse)
    assert first["MAXIMUM"] == 313395060 and first["ALL_MAX_OWNERS"] == sorted(cert.TARGETS)
    assert first["NEXT_DISTINCT_RESOLVED_BOUND"] == 313394776
    assert last["MAXIMUM"] == 313394776
    assert last["ALL_MAX_OWNERS"] == result["ALL_NEW_MAX_OWNERS"] == ["66555555555431100000"]
    assert result["FAMILY_DELTA"] == 284
    assert result["GAP_TO_INCUMBENT"] == 313394776 - 313263888 == 130888
    assert result["PROJECTION_STATUS"] == "CONDITIONAL_PROJECTION; NOT_CANONICAL_ADOPTION"


def test_no_authority_inflation(result: dict[str, object]) -> None:
    assert result["GLOBAL_OPTIMUM"] == "UNKNOWN"
    assert result["PREDICTION_GAIN_CLAIMED"] is False
    assert result["GRAPH_ENUMERATION_COMPLETENESS"] == "NOT_APPLICABLE — ANALYTIC_BOUND"
    assert result["SOLVER_CALLS"] == result["REALIZATIONS_ENUMERATED"] == 0
    assert result["CANONICAL_AUTHORITY_CHANGED"] == "NO" and result["REMOTE_WRITE"] == "NO"
    assert str(result["TASK_STATUS"]).startswith("PROVEN_IMPROVEMENT")
    assert len(cert.obj(result["SOURCE_PINS"])) == 22


def test_full_stored_result_reproduces(result: dict[str, object]) -> None:
    assert cert.RESULT.read_bytes() == cert.render(result)


def test_changed_cap_cannot_produce_certified_result(result: dict[str, object]) -> None:
    altered = deepcopy(result)
    cert.obj(cast(list[object], altered["CERTIFICATES"])[1])["NEW_T_CAP"] = 251
    with pytest.raises(ValueError, match="not exactly reproducible"):
        cert.verify_result(altered)
