"""Focused proof arithmetic, Base provenance, full envelopes and rejection gates."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from fractions import Fraction
from typing import cast

import pytest

from lottolab.research import b649_three_max_profiles_shared_certificate_r2 as cert


@pytest.fixture(scope="module")
def result() -> dict[str, object]:
    return cert.compute_result()


@pytest.mark.parametrize(
    "pid,cap,positive", list(zip(cert.TARGETS, (230, 227, 228), (29, 26, 27), strict=True))
)
def test_exact_profiles_and_analytic_derivation(pid: str, cap: int, positive: int) -> None:
    proof = cert.theorem(pid)
    assert proof["ANALYTIC_CAP"] == 291 - 54 + positive - 36 == cap
    assert proof["EDGES"] == 93
    assert proof["DEGREE_SUM"] == 66
    assert proof["WEDGES"] == 825
    assert (proof["CORE_COUNT"], proof["ZERO_COUNT"]) == (14, 6)
    assert proof["COMPLETENESS"] == "NOT_APPLICABLE — ANALYTIC_UNIVERSAL_BOUND"


@pytest.mark.parametrize(
    "changes",
    [
        {"tickets": 19},
        {"labels_per_ticket": 5},
        {"labels": 48},
        {"triples": 21},
        {"pairs": 28},
        {"pair_linearity": False},
        {"support_sizes": (1, 2, 3)},
    ],
)
def test_wrong_support_assumptions_rejected(changes: dict[str, object]) -> None:
    with pytest.raises(ValueError, match="support assumptions"):
        cert.theorem(cert.TARGETS[0], replace(cert.Assumptions(), **changes))


@pytest.mark.parametrize("pid", ["66665555554431000000", "65555555555523000000", "", "6" * 20])
def test_wrong_or_relabelled_profile_rejected(pid: str) -> None:
    with pytest.raises(ValueError, match="exact profile"):
        cert.theorem(pid)


def test_full_envelopes_and_regression(result: dict[str, object]) -> None:
    rows = cast(list[dict[str, object]], result["CERTIFICATES"])
    assert [r["OLD_T_CAP"] for r in rows] == [266] * 3
    assert [r["NEW_T_CAP"] for r in rows] == [230, 227, 228]
    assert [r["OLD_BOUND"] for r in rows] == [313395164] * 3
    assert [r["NEW_BOUND"] for r in rows] == [313072532, 313045840, 313054608]
    assert [r["ROW_DELTA"] for r in rows] == [322632, 349324, 340556]
    for row in rows:
        pid = cert.string(row["PROFILE_ID"])
        s4 = cert.integer(cert.obj(row["S4_AUTHORITY"])["INHERITED_FLOOR"])
        assert s4 == 112
        assert cert.obj(row["S5_AUTHORITY"])["USED"] is False
        assert cert.obj(row["S5_AUTHORITY"])["VALUE"] is None
        for prefix in ("OLD", "NEW"):
            cap = cert.integer(row[f"{prefix}_T_CAP"])
            terms = cast(list[cert.Term], row[f"{prefix}_ALL_T_TERMS"])
            cert.validate_envelope(pid, cap, s4, terms)
            assert len(terms) == row[f"{prefix}_TERM_COUNT"] == cap - 21
            peak = max(t[1] for t in terms)
            assert [t for t in terms if t[1] == peak] == row[f"{prefix}_ALL_ARGMAX"]
            assert len(cast(list[cert.Term], row[f"{prefix}_ALL_ARGMAX"])) == 1


def test_fractional_rounding_probe_detects_floor() -> None:
    # Targets' peak S4 happens to divide by seven; this actual low-T term does not.
    terms = cert.envelope(cert.TARGETS[1], 227, 113)
    t = terms[0]
    exact = Fraction(cert.route.K20_S1 - cert.route.K20_S2 + t[5]) - Fraction(4 * t[4], 7)
    assert exact.denominator == 7
    altered = list(terms)
    altered[0] = (t[0], exact.numerator // exact.denominator, *t[2:])
    with pytest.raises(ValueError, match="ceiling rounding"):
        cert.validate_envelope(cert.TARGETS[1], 227, 113, altered)


@pytest.mark.parametrize("index", range(3))
@pytest.mark.parametrize("prefix", ("OLD", "NEW"))
def test_any_missing_term_or_endpoint_rejected(
    result: dict[str, object],
    index: int,
    prefix: str,
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
    with pytest.raises(ValueError, match="incomplete T envelope"):
        cert.validate_envelope(
            cert.TARGETS[1], 228, 112, cast(list[cert.Term], row["NEW_ALL_T_TERMS"])
        )


def test_duplicate_and_missing_resolved_row_rejected(result: dict[str, object]) -> None:
    ledger = cast(dict[str, int], result["RESOLVED_ROW_BOUNDS_AFTER"])
    rows = list(ledger.items())
    for changed in (rows + rows[:1], rows[:-1], rows[:-1] + rows[:1]):
        with pytest.raises(ValueError, match="resolved rows"):
            cert.checked_rows(changed, ledger)
    with pytest.raises(ValueError, match="duplicate JSON"):
        cert.decode(b'{"row":1,"row":2}')


def test_pin_and_source_damage_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(ValueError, match="blob pin"):
        cert.blob(cert.BASE_HEAD, cert.BASE_RESULT, "0" * 64)
    with pytest.raises(ValueError, match="tree pin"):
        cert.identity(cert.BASE_HEAD, cert.IMPLEMENTATION_TREE)
    original = cert.git

    def damaged(*args: str) -> bytes:
        raw = original(*args)
        if args[0] == "show" and args[1].endswith(
            "src/lottolab/research/b649_k20_min_s2_route_b_current_owner_refinement_r32.py"
        ):
            return raw + b"\n"
        return raw

    monkeypatch.setattr(cert, "git", damaged)
    with pytest.raises(ValueError, match="evaluator differs"):
        cert.source_pins()


def test_family_scans_all_rows_and_preserves_all_cursor_values(result: dict[str, object]) -> None:
    before = cast(dict[str, int], result["RESOLVED_ROW_BOUNDS_BEFORE"])
    after = cast(dict[str, int], result["RESOLVED_ROW_BOUNDS_AFTER"])
    assert len(before) == len(after) == 4647
    assert sorted(p for p in before if before[p] != after[p]) == sorted(cert.TARGETS)
    cursor = cert.obj(result["CURSOR"])
    coarse = cast(dict[str, int], cursor["COARSE_BOUND_PROJECTION"])
    assert len(coarse) == 197
    assert max(coarse.values()) == 313394584
    assert result["CURSOR_SHA256_BEFORE"] == result["CURSOR_SHA256_AFTER"]
    first, last = (
        cert.obj(result["PROJECTED_FAMILY_BEFORE"]),
        cert.obj(result["PROJECTED_FAMILY_AFTER"]),
    )
    assert first == cert.family(before, coarse)
    assert last == cert.family(after, coarse)
    assert first["MAXIMUM"] == 313395164
    assert first["ALL_MAX_OWNERS"] == sorted(cert.TARGETS)
    assert first["NEXT_DISTINCT_RESOLVED_BOUND"] == 313395060
    assert result["FAMILY_DELTA"] == 104
    assert last["MAXIMUM"] == 313395060
    assert last["ALL_MAX_OWNERS"] == ["66655555555332000000", "66655555555421100000"]
    assert result["GAP_TO_INCUMBENT"] == 131172
    assert result["CANONICAL_AUTHORITY_CHANGED"] == "NO"


def test_no_authority_inflation_or_enumeration(result: dict[str, object]) -> None:
    assert result["GLOBAL_OPTIMUM"] == "UNKNOWN"
    assert (
        result["GRAPHS_ENUMERATED"]
        == result["PORTFOLIOS_ENUMERATED"]
        == result["SOLVER_CALLS"]
        == 0
    )
    assert result["PROJECTION_STATUS"] == "BASE_SPECIFIC_CONDITIONAL; NOT_CANONICAL_ADOPTION"
    assert len(cert.obj(result["SOURCE_PINS"])) == 22


def test_full_stored_result_reproduces(result: dict[str, object]) -> None:
    assert cert.RESULT.read_bytes() == cert.render(result)
    cert.verify_result(cert.decode(cert.RESULT.read_bytes()))


def test_changed_cap_cannot_produce_certified_result(result: dict[str, object]) -> None:
    altered = deepcopy(result)
    cert.obj(cast(list[object], altered["CERTIFICATES"])[1])["NEW_T_CAP"] = 228
    with pytest.raises(ValueError, match="not exactly reproducible"):
        cert.verify_result(altered)
