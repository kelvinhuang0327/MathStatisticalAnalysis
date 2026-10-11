"""Focused boundary, cap, exact-envelope and complete-family regression guards."""

from __future__ import annotations

import copy
import hashlib
import json
import sys
from dataclasses import replace
from fractions import Fraction
from pathlib import Path

import pytest

from lottolab.research import b649_k20_min_s2_next_owners_and_loader_correction_r1 as x

OWNER1, OWNER2 = x.OWNER_SOURCES


@pytest.fixture(scope="module")
def authority() -> x.Authority:
    return x.load_authority()


@pytest.fixture(scope="module")
def result(authority: x.Authority) -> dict[str, object]:
    return x.compute_result(authority)


def test_historical_boundary_is_exact_and_accepts_loaded_descendants() -> None:
    # These are real descendants and the full actual historical import graph.
    assert x.__name__ in sys.modules and x.previous.__name__ in sys.modules
    sealed = x.previous.pinned(
        x.previous.BASE_HEAD, x.motif.RESULT_FILENAME, x.previous.BASE_RESULT_SHA256
    )
    actual = x.motif.historical_provenance()
    assert actual == sealed["MODULE_PROVENANCE"] and len(actual) == 27
    assert x.motif.load_authority().provenance == actual
    assert Path(x.__file__ or "").relative_to(x.chase.ROOT).as_posix() not in actual
    assert Path(x.previous.__file__ or "").relative_to(x.chase.ROOT).as_posix() not in actual


def test_pinned_historical_bytes_tampering_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    path = Path(x.split.__file__ or "").resolve()
    original = Path.read_bytes

    def tampered(p: Path) -> bytes:
        return original(p) + (b"\n# altered historical source\n" if p == path else b"")

    monkeypatch.setattr(Path, "read_bytes", tampered)
    x.motif.load_authority.cache_clear()
    with pytest.raises(AssertionError, match="reused module differs from base"):
        x.motif.load_authority()


def test_pinned_historical_source_identity_and_missing_module_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with monkeypatch.context() as patch:
        patch.setattr(x.split, "__file__", x.__file__)
        with pytest.raises(AssertionError, match="historical source identity"):
            x.motif.historical_provenance()
    with monkeypatch.context() as patch:
        patch.delitem(sys.modules, x.split.__name__)
        with pytest.raises(AssertionError, match="historical source module missing"):
            x.motif.historical_provenance()


def test_corrected_source_pins_and_base_bytes_preserved(authority: x.Authority) -> None:
    assert len(authority.provenance) == 29
    for module in (x.motif, x.previous):
        name = module.__name__.rsplit(".", 1)[-1]
        assert (
            hashlib.sha256(Path(module.__file__ or "").read_bytes()).hexdigest()
            == (x.CORRECTED_SOURCE_SHA256[name])
        )
    sealed = x.previous.pinned(x.BASE_HEAD, x.previous.RESULT_FILENAME, x.BASE_RESULT_SHA256)
    assert sealed == authority.sealed
    replay = x.previous.compute_result(authority.inherited)
    x.check_base_result(sealed, replay)
    with pytest.raises(AssertionError, match="sealed base result replay"):
        x.check_base_result({**sealed, "FINAL_COMPLETE_FAMILY_UB": 1}, replay)
    with pytest.raises(AssertionError, match="sealed base result replay"):
        x.check_base_result({**sealed, "SOURCE_SHA256": "0" * 64}, replay)


@pytest.mark.parametrize("pid", [OWNER1, OWNER2])
def test_cap_source_identity(pid: str, authority: x.Authority) -> None:
    cap, index, _source = x.OWNER_SOURCES[pid]
    row = authority.ledger[pid]
    proof = x.object_row(x.rows(authority.r30["GROUP_ATTEMPTS"])[index])
    x.check_cap(pid, row, proof)
    cert = x.owner_certificate(pid, row, proof)
    assert x.previous.text(cert["CAP_SOURCE"]).endswith(f"GROUP_ATTEMPTS[{index}]")
    assert cert["CAP_SOURCE_IDENTITY"] == proof and cert["TRIANGLE_CAP"] == cap
    for bad in (
        replace(row, cap=cap - 1),
        replace(row, cap=float(cap)),
        replace(row, source="other"),
    ):
        with pytest.raises(AssertionError, match="cap-source identity"):
            x.check_cap(pid, bad, proof)
    with pytest.raises(AssertionError, match="sealed ledger"):
        x.owner_certificate(pid, replace(row, bound=row.bound + 1), proof)


@pytest.mark.parametrize("pid", [OWNER1, OWNER2])
@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("STATUS", "FEASIBLE"),
        ("CERTIFICATE_KIND", "CP_SAT_FEASIBLE"),
        ("ATTEMPT_INDEX", -1),
        ("PROFILE_IDS", ["66666555554411100000"]),
        ("ROUTE", "OTHER"),
        ("WEDGE_COUNT", 0),
        ("TARGET_TRIANGLE_CAP", 264.0),
        ("REFUTED_GRAPH_TRIANGLE_COUNT", 264),
        ("CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND", 265.0),
        ("OPEN_WEDGE_CEILING_REFUTED", 0),
        ("CERTIFIED_OPEN_WEDGE_LOWER_BOUND", 0),
    ],
)
def test_owner_cap_source_tampering_rejected(
    pid: str,
    key: str,
    value: object,
    authority: x.Authority,
) -> None:
    proof = x.object_row(x.rows(authority.r30["GROUP_ATTEMPTS"])[x.OWNER_SOURCES[pid][1]])
    with pytest.raises(AssertionError, match="cap-source identity"):
        x.owner_certificate(pid, authority.ledger[pid], {**proof, key: value})


@pytest.mark.parametrize(
    ("pid", "expected"),
    [
        (OWNER1, (833, 2366, 604, 41, 410, 489, 201, 308504)),
        (OWNER2, (830, 2342, 598, 35, 350, 498, 199, 311717)),
    ],
)
def test_generic_quartet_identity_and_floor(pid: str, expected: tuple[int, ...]) -> None:
    p, cap = x.split.profile_values(pid), x.OWNER_SOURCES[pid][0]
    floor = x.previous.incidence_floor(p, cap)
    assert tuple(floor.values()) == expected
    assert x.previous.incidence_identity_check()["LOCAL_CASES"] == 96
    # Independent exact minimization over all allowed wedge loads; no owner-specific branch.
    u, r, ell = floor["U"], floor["R"], floor["L_MAX"]
    values = [
        231 * max(0, -(-(u - load) // 4)) - 63 * (r // 3) + 56 * (2 * u - load - r)
        for load in range(ell + 1)
    ]
    assert min(values) == values[-1] == floor["S4_FLOOR"]
    assert floor["S4_FLOOR"] == x.motif.degree_floor(p, cap)["S4_CERTIFIED_FLOOR"] + 21 * (r % 3)


@pytest.mark.parametrize(
    ("pid", "expected"),
    [
        (OWNER1, (285600, 308504, 313401464, 313388376, 313392308, 313392308)),
        (OWNER2, (292173, 311717, 313401180, 313390012, 313392024, 313392024)),
    ],
)
def test_all_t_exact_integer_envelope_and_no_double_credit(
    pid: str,
    expected: tuple[int, ...],
    authority: x.Authority,
) -> None:
    row = authority.ledger[pid]
    proof = x.object_row(x.rows(authority.r30["GROUP_ATTEMPTS"])[x.OWNER_SOURCES[pid][1]])
    c = x.owner_certificate(pid, row, proof)
    assert (
        tuple(
            c[key]
            for key in (
                "OLD_ROUTE_B_S4_FLOOR",
                "NEW_S4_FLOOR",
                "CAP_OLD_BOUND",
                "CAP_NEW_BOUND",
                "RETAINED_LOWER_T_MAX",
                "CERTIFIED_PROFILE_BOUND",
            )
        )
        == expected
    )
    old = x.split.route_b_terms(x.split.profile_values(pid), row.cap, row.s4_base)
    terms = x.rows(c["ALL_T_TERMS"])
    assert terms[:-1] == [list(term) for term in old[:-1]]
    assert [x.rows(term)[0] for term in terms] == list(range(22, row.cap + 1))
    assert c["RETAINED_TERMS_SHA256"] == x.digest(old[:-1])
    assert c["NEW_S4_FLOOR"] == max(
        expected[0], x.integer(x.object_row(c["INCIDENCE_FLOOR"])["S4_FLOOR"])
    )
    assert c["NEW_S4_FLOOR"] != expected[0] + expected[1]
    for term in terms:
        t, bound, _k, _a, s4, s3 = x.rows(term)
        s3_check, rounded = x.chase.r20.bound_from_cap(
            x.split.profile_values(pid), x.integer(t), x.integer(s4)
        )
        rational = (
            x.motif.event.K20_S1
            - x.motif.event.K20_S2
            + x.integer(s3)
            - Fraction(4 * x.integer(s4), 7)
        )
        assert bound == rounded and s3 == s3_check and 0 <= rounded - rational < 1
    # The cap-only envelope must retain the larger lower-t maximum.
    assert c["CERTIFIED_PROFILE_BOUND"] != c["CAP_NEW_BOUND"]


@pytest.mark.parametrize("pid", [OWNER1, OWNER2])
def test_tampered_owner_terms_fail_at_certificate_guard(pid: str, authority: x.Authority) -> None:
    row = authority.ledger[pid]
    proof = x.object_row(x.rows(authority.r30["GROUP_ATTEMPTS"])[x.OWNER_SOURCES[pid][1]])
    cert = x.owner_certificate(pid, row, proof)
    for key in ("NEW_S4_FLOOR", "CAP_NEW_BOUND", "RETAINED_LOWER_T_MAX", "CERTIFIED_PROFILE_BOUND"):
        with pytest.raises(AssertionError, match="tampered owner certificate"):
            x.verify_certificate({**cert, key: x.integer(cert[key]) + 1}, row, proof)
    tampered = copy.deepcopy(cert)
    x.rows(x.rows(tampered["ALL_T_TERMS"])[0])[1] = 1
    with pytest.raises(AssertionError, match="tampered owner certificate"):
        x.verify_certificate(tampered, row, proof)


def test_complete_family_coverage_and_only_two_rows_change(
    authority: x.Authority,
    result: dict[str, object],
) -> None:
    start, final = x.object_row(result["START_FAMILY"]), x.object_row(result["FINAL_FAMILY"])
    assert (start["FAMILY_UB"], start["OWNER_IDS"]) == (313401464, [OWNER1])
    assert (final["FAMILY_UB"], final["OWNER_IDS"], final["REMAINING_GAP"]) == (
        313401076,
        ["66666555554411100000"],
        137188,
    )
    assert result["START_COMPLETE_FAMILY_UB"] == start["FAMILY_UB"]
    assert result["FINAL_COMPLETE_FAMILY_UB"] == final["FAMILY_UB"]
    assert result["FINAL_OWNER_IDS"] == final["OWNER_IDS"]
    coverage = x.object_row(final["COVERAGE"])
    assert tuple(
        coverage[k]
        for k in (
            "ADMISSIBLE_PROFILE_COUNT",
            "RESOLVED_ROW_COUNT",
            "UNDER_CURSOR_PROFILE_COUNT",
            "UNCOVERED_PROFILE_COUNT",
        )
    ) == (4844, 4647, 197, 0)
    assert start["COVERAGE"] == final["COVERAGE"]
    certs = x.object_row(result["OWNER_CERTIFICATES"])
    assert set(certs) == {OWNER1, OWNER2}
    final_ledger = dict(authority.ledger)
    for pid in certs:
        final_ledger = x.previous.install(
            final_ledger,
            pid,
            x.integer(x.object_row(certs[pid])["CERTIFIED_PROFILE_BOUND"]),
            f"{x.RESULT_FILENAME}:OWNER_CERTIFICATES[{pid}]",
        )
    assert x.previous.family(final_ledger, authority.inherited) == final
    assert {pid for pid in final_ledger if final_ledger[pid] != authority.ledger[pid]} == set(certs)
    assert result["OTHER_PROFILE_ROWS_UNCHANGED"] == 4645
    assert result["OTHER_ROWS_SHA256"] == x.digest(
        {pid: r.bound for pid, r in authority.ledger.items() if pid not in certs}
    )
    assert x.object_row(result["INHERITED_CERTIFICATES"]) == {
        key: authority.sealed[key]
        for key in ("T264_OWNER_CERTIFICATE", "STS13_CERTIFICATE", "OWNER_MOTIF_CERTIFICATE")
    }
    transitions = [x.object_row(step) for step in x.rows(result["OWNER_TRANSITIONS"])]
    assert [(s["FAMILY_BEFORE"], s["FAMILY_AFTER"]) for s in transitions] == [
        (313401464, 313401180),
        (313401180, 313401076),
    ]
    dropped = {pid: r for pid, r in final_ledger.items() if pid != "66666555554411100000"}
    with pytest.raises(AssertionError, match="coverage changed"):
        x.previous.family(dropped, authority.inherited)
    with pytest.raises(AssertionError, match="strictly improve"):
        x.previous.install(final_ledger, OWNER1, final_ledger[OWNER1].bound, "duplicate")


def test_sts13_p2_and_owner_witness_soundness(
    result: dict[str, object], authority: x.Authority
) -> None:
    sound = x.object_row(result["WITNESS_SOUNDNESS"])
    assert sound["STATUS"] == "PASS"
    realizations = x.object_row(sound["INCIDENCE_FLOOR_REALIZATIONS"])
    assert x.object_row(realizations["P2"])["TRIANGLES"] == 250
    assert (
        x.object_row(realizations["STS13"])["TRIANGLES"],
        x.object_row(realizations["STS13"])["EXACT_S4"],
    ) == (270, 331240)
    assert x.object_row(sound["CANONICAL_WITNESS"])["INCUMBENT"] == 313263888
    current = x.object_row(result["CURRENT_OWNER_REALIZATIONS"])
    assert set(current) == {OWNER1, OWNER2}
    for pid, raw in current.items():
        seen = x.object_row(raw)
        if authority.ledger[pid].realization is None:
            assert seen == {"STATUS": "NO_RECORDED_REALIZATION_IN_INHERITED_LEDGER"}
        else:
            assert seen["STATUS"] == "PASS" and seen["PROFILE_ID"] == pid
            assert x.integer(seen["TRIANGLES"]) <= x.OWNER_SOURCES[pid][0]


def test_immutable_successor_reproduces_and_rejects_tampering(
    result: dict[str, object],
    authority: x.Authority,
) -> None:
    assert result["SOLVER_CALLS"] == result["OUTCOME_ENUMERATIONS"] == 0
    assert result["NEW_HEAVY_SOLVER_STARTED"] == result["NEW_PORTFOLIO_SEARCH_STARTED"] == "NO"
    assert result["PRODUCTION_MUTATION"] == "NONE"
    x.verify_result(result, authority)
    with pytest.raises(AssertionError, match="tampered immutable successor"):
        x.verify_result({**result, "FINAL_COMPLETE_FAMILY_UB": 313392308}, authority)
    if x.RESULT_PATH.exists():
        assert json.loads(x.RESULT_PATH.read_text()) == result
        with pytest.raises(AssertionError, match="immutable successor result already exists"):
            x.main()
