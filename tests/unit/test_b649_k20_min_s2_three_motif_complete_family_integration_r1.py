"""Focused checks for the three-certificate complete minimum-S2 family integration."""

from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Mapping
from dataclasses import replace
from itertools import combinations
from pathlib import Path

import pytest

from lottolab.research import b649_k20_min_s2_owner_66655555555440000000_motif_r1 as motif
from lottolab.research import b649_k20_min_s2_split_cap_current_owner_chase_r1 as chase

Ledger = dict[str, chase.Row]
FINAL_OWNER = "66665555555421000000"


def load():
    from lottolab.research import (
        b649_k20_min_s2_three_motif_complete_family_integration_r1 as integration,
    )

    return integration


@pytest.fixture(scope="module")
def authority() -> chase.Authority:
    return chase.load_authority()


@pytest.fixture(scope="module")
def result(authority: chase.Authority) -> dict[str, object]:
    return load().compute_result(authority)


@pytest.fixture(scope="module")
def pins() -> dict[str, dict[str, object]]:
    x = load()
    return {
        "chase": motif.pinned_result(chase.RESULT_FILENAME, x.CHASE_RESULT_SHA256),
        "motif": x.pinned(x.BASE_HEAD, motif.RESULT_FILENAME, x.BASE_RESULT_SHA256),
        "donor": x.pinned(x.STS13_DONOR_HEAD, x.STS13_RESULT_FILENAME, x.STS13_DONOR_RESULT_SHA256),
        "r30": motif.pinned_result(x.r32.CAP_SOURCE_RESULT, x.r32.R30_SHA256),
        "r32": motif.pinned_result(x.r32.RESULT_FILENAME),
    }


@pytest.fixture(scope="module")
def ledger(authority: chase.Authority, pins: dict[str, dict[str, object]]) -> Ledger:
    return load().chase_ledger(authority, pins["chase"])


@pytest.fixture(scope="module")
def t264_inputs(pins: dict[str, dict[str, object]]) -> tuple[dict[str, object], dict[str, object]]:
    x = load()
    proof = x.object_row(x.rows(pins["r30"]["GROUP_ATTEMPTS"])[x.T264_CAP_INDEX])
    source = x.object_row(x.rows(pins["r32"]["ROUTE_B_CERTIFICATES"])[x.T264_LEDGER_INDEX])
    return proof, source


def test_three_certificate_sources_and_scopes(
    result: dict[str, object], pins: dict[str, dict[str, object]], tmp_path: Path
) -> None:
    x = load()
    t264 = x.object_row(result["T264_OWNER_CERTIFICATE"])
    sts = x.object_row(result["STS13_CERTIFICATE"])
    owner = x.object_row(result["OWNER_MOTIF_CERTIFICATE"])
    assert [c["PROFILE_ID"] for c in (t264, sts, owner)] == [
        "66666555555311100000",
        "55555555555511111100",
        "66655555555440000000",
    ]
    assert len(set(x.rows(result["CERTIFIED_PROFILE_IDS"]))) == 3
    assert t264["CAP_SOURCE"] == f"{x.r32.CAP_SOURCE_RESULT}:GROUP_ATTEMPTS[2504]"
    assert t264["EXISTING_LEDGER_SOURCE"] == f"{x.r32.RESULT_FILENAME}:ROUTE_B_CERTIFICATES[4]"
    assert x.text(sts["CAP_SOURCE"]).endswith("NB_CERTIFICATES[1732]")
    assert owner["CAP_SOURCE"] == f"{x.r32.CAP_SOURCE_RESULT}:GROUP_ATTEMPTS[2981]"
    assert (sts["DONOR_HEAD"], sts["GRAPH_ISOLATION_REDERIVED"]) == (x.STS13_DONOR_HEAD, False)
    donor_cert = x.object_row(pins["donor"]["STS13_T270_CERTIFICATE"])
    assert sts["CERTIFICATE_SHA256"] == x.digest(donor_cert)
    assert owner["CERTIFICATE_SHA256"] == x.digest(pins["motif"]["OWNER_CERTIFICATE"])
    assert result["BASE_TREE"] == x.BASE_TREE and result["BASE_HEAD"] == x.BASE_HEAD
    reused = x.object_row(result["MODULE_PROVENANCE"])
    assert len(reused) == 17
    for module in (motif, chase, chase.split, x.r32):
        assert Path(module.__file__ or "").relative_to(x.ROOT).as_posix() in reused
    with pytest.raises(AssertionError, match="digest mismatch"):
        x.pinned(x.STS13_DONOR_HEAD, x.STS13_RESULT_FILENAME, "0" * 64)
    copy_dir = tmp_path / chase.prior.RESULT_DIRECTORY
    copy_dir.mkdir(parents=True)
    original = (x.ROOT / chase.prior.RESULT_DIRECTORY / x.STS13_RESULT_FILENAME).read_bytes()
    (copy_dir / x.STS13_RESULT_FILENAME).write_bytes(original.replace(b"331240", b"331247", 1))
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(x, "ROOT", tmp_path)
        with pytest.raises(AssertionError, match="in-tree result differs"):
            x.pinned(x.STS13_DONOR_HEAD, x.STS13_RESULT_FILENAME, x.STS13_DONOR_RESULT_SHA256)


def test_four_point_incidence_identity_and_independent_probes() -> None:
    x = load()
    checked = x.incidence_identity_check()
    assert checked["STATUS"] == "PASS" and checked["LOCAL_CASES"] == 96
    k4 = set(combinations(range(4), 2))
    diamond = k4 - {(2, 3)}
    claw = {(0, 1), (0, 2), (0, 3)}
    paw = {(0, 1), (0, 2), (1, 2), (2, 3)}
    # (edges, triple, U, L, R, K, A, slack) counted by hand.
    probes = [
        (k4, None, 4, 0, 0, 1, 0, 0),
        (k4, (0, 1, 2), 4, 0, 3, 1, 1, 0),
        (diamond, None, 2, 2, 0, 0, 0, 0),
        (claw, None, 1, 3, 0, 0, 0, 56),
        (paw, (0, 1, 2), 1, 2, 1, 0, 0, 56),
    ]
    for edges, triple, u, ell, r, k, a, slack in probes:
        assert motif.incidences(4, edges, () if triple is None else (triple,)) == (u, ell, r)
        weight = motif.local_weight(edges, triple)
        assert weight == 231 * k - 63 * a + 56 * (2 * u - ell - r) + slack
    assert [motif.local_weight(e, t) for e, t, *_ in probes] == [679, 448, 112, 0, 0]


def test_incidence_floor_values_and_worst_case_wedge_load() -> None:
    x = load()
    p = chase.split.profile_values("66666555555311100000")
    floor = x.incidence_floor(p, 264)
    assert floor == {
        "W": 834,
        "U": 2379,
        "R": 606,
        "OW": 42,
        "L_MAX": 420,
        "K4_FLOOR": 490,
        "A_MAX": 202,
        "S4_FLOOR": 309456,
    }
    assert 231 * 490 - 63 * 202 + 56 * (2 * 2379 - 420 - 606) == 309456
    # The floor is the minimum over every admissible open-wedge load L <= L_MAX.
    u, r = floor["U"], floor["R"]
    values = [
        231 * max(0, -(-(u - ell) // 4)) - 63 * (r // 3) + 56 * (2 * u - ell - r)
        for ell in range(floor["L_MAX"] + 1)
    ]
    assert min(values) == values[-1] == 309456
    other = chase.split.profile_values("66655555555440000000")
    assert (
        x.incidence_floor(other, 264)["S4_FLOOR"] - 21
        == motif.degree_floor(other, 264)["S4_CERTIFIED_FLOOR"]
    )
    with pytest.raises(ValueError, match="negative open-wedge"):
        x.incidence_floor(p, 279)


def test_t264_owner_replaces_only_the_cap_term(
    ledger: Ledger, t264_inputs: tuple[dict[str, object], dict[str, object]]
) -> None:
    x = load()
    row = ledger[x.T264_PROFILE]
    assert (row.bound, row.cap, row.s4_base) == (313404008, 264, 112)
    c = x.t264_certificate(row, *t264_inputs)
    assert (c["OLD_ROUTE_B_S4_FLOOR"], c["NEW_S4_FLOOR"], c["CREDIT_GAIN"]) == (
        286048,
        309456,
        13376,
    )
    assert (c["T264_OLD_BOUND"], c["T264_NEW_BOUND"]) == (313404008, 313390632)
    assert (c["RETAINED_LOWER_T_MAX"], c["CERTIFIED_PROFILE_BOUND"]) == (313394852, 313394852)
    old = chase.split.route_b_terms(chase.split.profile_values(x.T264_PROFILE), 264, 112)
    new = x.rows(c["ALL_T_TERMS"])
    assert len(new) == 243 and new[:-1] == [list(t) for t in old[:-1]]
    assert new[-1] == [264, 313390632, 490, 202, 309456, old[-1][5]]
    # Replacement, not addition, of the overlapping Route-B credit.
    assert c["NEW_S4_FLOOR"] != 286048 + 309456
    # Applying the floor at every t would give 313,390,632; only t=264 is certified here.
    assert x.integer(c["CERTIFIED_PROFILE_BOUND"]) > x.integer(c["T264_NEW_BOUND"])


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("STATUS", "FEASIBLE"),
        ("ATTEMPT_INDEX", 2981),
        ("PROFILE_IDS", ["66655555555440000000"]),
        ("TARGET_TRIANGLE_CAP", 265),
        ("REFUTED_GRAPH_TRIANGLE_COUNT", 264),
        ("CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND", 264.0),
        ("WEDGE_COUNT", 833),
        ("ROUTE", "OTHER"),
    ],
)
def test_t264_cap_source_tampering_rejected(
    key: str,
    value: object,
    ledger: Ledger,
    t264_inputs: tuple[dict[str, object], dict[str, object]],
) -> None:
    x = load()
    proof, source = t264_inputs
    with pytest.raises(AssertionError, match="cap-source"):
        x.t264_certificate(ledger[x.T264_PROFILE], {**proof, key: value}, source)


def test_t264_ledger_source_and_row_tampering_rejected(
    ledger: Ledger, t264_inputs: tuple[dict[str, object], dict[str, object]]
) -> None:
    x = load()
    proof, source = t264_inputs
    row = ledger[x.T264_PROFILE]
    origin = {**x.object_row(source["CERTIFICATE_SOURCE"]), "SOURCE_ROW": "GROUP_ATTEMPTS[1391]"}
    for bad in (
        {**source, "CERTIFIED_TRIANGLE_CAP": 265},
        {**source, "CERTIFICATE_SOURCE": origin},
        {**source, "ALL_T_MAX_BOUND": row.bound + 1},
        {**source, "GLOBAL_S4_FLOOR": 113},
        {**source, "CERTIFICATE_INDEX": 5},
    ):
        with pytest.raises(AssertionError, match="cap-source"):
            x.t264_certificate(row, proof, bad)
    with pytest.raises(AssertionError, match="cap-source"):
        x.t264_certificate(replace(row, cap=263), proof, source)
    with pytest.raises(AssertionError, match="cap-source"):
        x.t264_certificate(replace(row, source="other"), proof, source)
    with pytest.raises(AssertionError, match="degree constants"):
        x.t264_certificate(row, proof, {**source, "SUM_GRAPH_DEGREE_CHOOSE_3": 2378})


def test_sts13_exact_certificate_adopted_without_rederivation(
    ledger: Ledger, pins: dict[str, dict[str, object]]
) -> None:
    x = load()
    row = ledger[x.STS13_PROFILE]
    assert (row.bound, row.cap, row.s4_base) == (313402304, 270, 112)
    c = x.sts13_certificate(row, pins["donor"])
    assert (c["K4"], c["A"], c["DIAMONDS"], c["EXACT_S4"]) == (550, 190, 15, 331240)
    assert c["GRAPH_STRUCTURE"] == "K12 + (K8-e)"
    assert (c["OLD_ROUTE_B_S4_FLOOR"], c["T270_OLD_BOUND"], c["T270_NEW_BOUND"]) == (
        325486,
        313402304,
        313399016,
    )
    assert (c["RETAINED_LOWER_T_COUNT"], c["RETAINED_LOWER_T_MAX"]) == (248, 313392760)
    assert c["CERTIFIED_PROFILE_BOUND"] == 313399016


def _tamper(donor: Mapping[str, object], path: tuple[str, ...], value: object) -> dict[str, object]:
    out = copy.deepcopy(dict(donor))
    node: dict[str, object] = out
    for key in path[:-1]:
        node = load().object_row(node[key])
    node[path[-1]] = value
    return out


@pytest.mark.parametrize(
    ("path", "value", "message"),
    [
        (("TASK_ID",), "OTHER", "donor authority"),
        (("BASE_HEAD",), "0" * 40, "donor authority"),
        (("STS13_T270_CERTIFICATE", "PROFILE_ID"), "66666555555311100000", "identity"),
        (("STS13_T270_CERTIFICATE", "GRAPH_ISOLATION", "STRUCTURE"), "K13 + K7", "identity"),
        (("STS13_T270_CERTIFICATE", "GRAPH_ISOLATION", "OPEN_WEDGES"), 7, "identity"),
        (("STS13_T270_CERTIFICATE", "LABEL_SUPPORTS", "EXACT_S4"), 331247, "counts"),
        (("STS13_T270_CERTIFICATE", "LABEL_SUPPORTS", "K4_COUNT"), 551, "counts"),
        (("STS13_T270_CERTIFICATE", "WITNESS", "S4_CLASS_DP"), 331233, "counts"),
        (("STS13_T270_CERTIFICATE", "ADOPTION", "CAP_AUTHORITY"), "other", "apply"),
        (("STS13_T270_CERTIFICATE", "ADOPTION", "T270_NEW_BOUND"), 313399015, "adoption"),
        (("STS13_T270_CERTIFICATE", "ADOPTION", "LOWER_T_MAX_BOUND"), 313392761, "adoption"),
        (("STS13_T270_CERTIFICATE", "ADOPTION", "FULL_PROFILE_BOUND"), 313392760, "adoption"),
    ],
)
def test_sts13_tampered_certificate_rejected(
    path: tuple[str, ...],
    value: object,
    message: str,
    ledger: Ledger,
    pins: dict[str, dict[str, object]],
) -> None:
    x = load()
    with pytest.raises(AssertionError, match=message):
        x.sts13_certificate(ledger[x.STS13_PROFILE], _tamper(pins["donor"], path, value))


def test_sts13_tampered_lower_term_and_wrong_row_rejected(
    ledger: Ledger, pins: dict[str, dict[str, object]]
) -> None:
    x = load()
    row = ledger[x.STS13_PROFILE]
    donor = copy.deepcopy(pins["donor"])
    adoption = x.object_row(x.object_row(donor["STS13_T270_CERTIFICATE"])["ADOPTION"])
    first = x.rows(x.rows(adoption["ALL_T_TERMS"])[0])
    first[1] = x.integer(first[1]) - 1
    with pytest.raises(AssertionError, match="adoption"):
        x.sts13_certificate(row, donor)
    for bad in (
        replace(row, cap=269),
        replace(row, bound=row.bound + 1),
        replace(row, s4_base=113),
    ):
        with pytest.raises(AssertionError, match="apply"):
            x.sts13_certificate(bad, pins["donor"])


def test_owner_motif_result_preserved_and_tampering_rejected(
    result: dict[str, object], ledger: Ledger, pins: dict[str, dict[str, object]]
) -> None:
    x = load()
    owner = x.object_row(result["OWNER_MOTIF_CERTIFICATE"])
    assert (owner["T264_NEW_BOUND"], owner["CERTIFIED_PROFILE_BOUND"]) == (313388904, 313393084)
    assert owner["STATUS"] == "PRESERVED_SEALED_BYTES_REVERIFIED"
    on_disk = (x.ROOT / chase.prior.RESULT_DIRECTORY / motif.RESULT_FILENAME).read_bytes()
    assert on_disk == chase.git(
        "show", f"{x.BASE_HEAD}:{chase.prior.RESULT_DIRECTORY}/{motif.RESULT_FILENAME}"
    )
    proof = x.object_row(x.rows(pins["r30"]["GROUP_ATTEMPTS"])[motif.CAP_INDEX])
    row = ledger[x.OWNER_PROFILE]
    sealed = copy.deepcopy(pins["motif"])
    x.object_row(sealed["OWNER_CERTIFICATE"])["CERTIFIED_OWNER_BOUND"] = 313393083
    with pytest.raises(AssertionError, match="tampered owner"):
        x.owner_motif_certificate(row, proof, sealed, ledger)
    sealed = {**pins["motif"], "OTHER_ROWS_SHA256": "0" * 64}
    with pytest.raises(AssertionError, match="owner motif authority"):
        x.owner_motif_certificate(row, proof, sealed, ledger)
    moved = {**ledger, "66665555555421000000": replace(ledger["66665555555421000000"], bound=1)}
    with pytest.raises(AssertionError, match="owner motif authority"):
        x.owner_motif_certificate(row, proof, pins["motif"], moved)


def test_no_double_count_one_term_per_distinct_profile(
    result: dict[str, object], ledger: Ledger
) -> None:
    x = load()
    final_bounds = {
        x.T264_PROFILE: x.object_row(result["T264_OWNER_CERTIFICATE"])["CERTIFIED_PROFILE_BOUND"],
        x.STS13_PROFILE: x.object_row(result["STS13_CERTIFICATE"])["CERTIFIED_PROFILE_BOUND"],
        x.OWNER_PROFILE: x.object_row(result["OWNER_MOTIF_CERTIFICATE"])["CERTIFIED_PROFILE_BOUND"],
    }
    assert final_bounds == {
        "66666555555311100000": 313394852,
        "55555555555511111100": 313399016,
        "66655555555440000000": 313393084,
    }
    assert result["OTHER_PROFILE_ROWS_UNCHANGED"] == 4644
    assert result["OTHER_ROWS_SHA256"] == x.digest(
        {pid: r.bound for pid, r in ledger.items() if pid not in final_bounds}
    )
    once = x.install(ledger, x.T264_PROFILE, 313394852, x.T264_LOCATOR)
    with pytest.raises(AssertionError, match="strictly improve"):
        x.install(once, x.T264_PROFILE, 313394852, x.T264_LOCATOR)
    with pytest.raises(AssertionError, match="strictly improve"):
        x.install(ledger, x.STS13_PROFILE, x.INCUMBENT - 1, x.STS13_LOCATOR)


def test_coverage_owner_transitions_and_complete_family(
    result: dict[str, object], authority: chase.Authority, ledger: Ledger
) -> None:
    x = load()
    start = x.object_row(result["START_FAMILY"])
    final = x.object_row(result["FINAL_FAMILY"])
    assert (start["FAMILY_UB"], start["OWNER_IDS"]) == (313404008, ["66666555555311100000"])
    assert (final["FAMILY_UB"], final["OWNER_IDS"]) == (313401464, [FINAL_OWNER])
    assert (result["START_COMPLETE_FAMILY_UB"], result["FINAL_COMPLETE_FAMILY_UB"]) == (
        313404008,
        313401464,
    )
    assert result["FINAL_OWNER_IDS"] == [FINAL_OWNER] and result["REMAINING_GAP"] == 137576
    assert final["NEXT_COMPETING_BOUND"] == 313401180
    coverage = x.object_row(final["COVERAGE"])
    assert (
        coverage["ADMISSIBLE_PROFILE_COUNT"],
        coverage["RESOLVED_ROW_COUNT"],
        coverage["UNDER_CURSOR_PROFILE_COUNT"],
        coverage["UNCOVERED_PROFILE_COUNT"],
    ) == (4844, 4647, 197, 0)
    steps = [x.object_row(s) for s in x.rows(result["OWNER_TRANSITIONS"])]
    assert [(s["FAMILY_BEFORE"], s["FAMILY_AFTER"]) for s in steps] == [
        (313404008, 313402304),
        (313402304, 313401464),
    ]
    assert [s["OWNER_IDS_AFTER"] for s in steps] == [["55555555555511111100"], [FINAL_OWNER]]
    above = [x.object_row(r) for r in x.rows(final["ROWS_ABOVE_CURSOR"])]
    assert above[0]["PROFILE_ID"] == FINAL_OWNER and len(above) == 24
    assert all(x.integer(r["BOUND"]) > x.prior.CURSOR_BOUND for r in above)
    # Order independence: installing in the reverse order gives the same final ledger.
    t264 = x.object_row(result["T264_OWNER_CERTIFICATE"])
    sts = x.object_row(result["STS13_CERTIFICATE"])
    start_ledger = x.install(ledger, x.OWNER_PROFILE, 313393084, x.OWNER_LOCATOR)
    forward, _ = x.transitions(
        start_ledger,
        [
            (x.T264_PROFILE, x.integer(t264["CERTIFIED_PROFILE_BOUND"]), x.T264_LOCATOR),
            (x.STS13_PROFILE, x.integer(sts["CERTIFIED_PROFILE_BOUND"]), x.STS13_LOCATOR),
        ],
    )
    backward, _ = x.transitions(
        start_ledger,
        [
            (x.STS13_PROFILE, x.integer(sts["CERTIFIED_PROFILE_BOUND"]), x.STS13_LOCATOR),
            (x.T264_PROFILE, x.integer(t264["CERTIFIED_PROFILE_BOUND"]), x.T264_LOCATOR),
        ],
    )
    assert forward == backward
    assert x.family(forward, authority) == final
    dropped = dict(forward)
    del dropped[FINAL_OWNER]
    with pytest.raises(AssertionError, match="coverage changed"):
        x.family(dropped, authority)


def test_sts13_p2_and_canonical_witness_tripwires(
    result: dict[str, object], ledger: Ledger, pins: dict[str, dict[str, object]]
) -> None:
    x = load()
    checks = x.object_row(result["WITNESS_SOUNDNESS"])
    seen = x.object_row(checks["INCIDENCE_FLOOR_REALIZATIONS"])
    assert set(seen) == {"T264_OWNER", "OWNER_MOTIF", f"FINAL_OWNER_{FINAL_OWNER}", "P2", "STS13"}
    assert x.object_row(seen["P2"])["TRIANGLES"] == 250
    assert (x.object_row(seen["STS13"])["TRIANGLES"], x.object_row(seen["STS13"])["EXACT_S4"]) == (
        270,
        331240,
    )
    canonical = x.object_row(checks["CANONICAL_WITNESS"])
    assert canonical["STS13_PROFILE_BOUND"] == canonical["ROUTES_1_TO_4_FLOOR"] == 313399016
    assert canonical["EXACT_ANY_PRIZE_UNION"] == 313263867
    sts = x.object_row(result["STS13_CERTIFICATE"])
    final = {
        **ledger,
        x.T264_PROFILE: replace(ledger[x.T264_PROFILE], bound=313394852),
        x.OWNER_PROFILE: replace(ledger[x.OWNER_PROFILE], bound=313393084),
        x.STS13_PROFILE: replace(ledger[x.STS13_PROFILE], bound=313399016),
    }
    x.soundness(final, pins["r30"], sts)
    over = {**final, x.STS13_PROFILE: replace(final[x.STS13_PROFILE], bound=313399015)}
    with pytest.raises(AssertionError, match="canonical"):
        x.soundness(over, pins["r30"], sts)
    with pytest.raises(AssertionError, match="canonical"):
        x.soundness(final, pins["r30"], {**sts, "EXACT_S4": 331247})
    capped = {**final, x.T264_PROFILE: replace(final[x.T264_PROFILE], cap=191)}
    with pytest.raises(AssertionError, match="legal realization"):
        x.soundness(capped, pins["r30"], sts)


def test_immutable_result_reproduces_and_starts_no_forbidden_work(
    result: dict[str, object], authority: chase.Authority
) -> None:
    x = load()
    assert result["SOLVER_CALLS"] == result["OUTCOME_ENUMERATIONS"] == 0
    assert result["NEW_HEAVY_SOLVER_STARTED"] == result["NEW_PORTFOLIO_SEARCH_STARTED"] == "NO"
    assert result["PRODUCTION_MUTATION"] == "NONE"
    x.verify_result(result, authority)
    with pytest.raises(AssertionError, match="tampered immutable"):
        x.verify_result({**result, "FINAL_COMPLETE_FAMILY_UB": 313399016}, authority)
    tampered = copy.deepcopy(result)
    x.object_row(tampered["T264_OWNER_CERTIFICATE"])["NEW_S4_FLOOR"] = 286048 + 309456
    with pytest.raises(AssertionError, match="tampered immutable"):
        x.verify_result(tampered, authority)
    if x.RESULT_PATH.exists():
        sealed = x.object_row(json.loads(x.RESULT_PATH.read_text(encoding="utf-8")))
        head = "a5eb5081180dd9cbe1745b0f2577cd18eb76a90b"
        source = Path(x.__file__ or "").relative_to(x.ROOT).as_posix()
        owner_source = Path(motif.__file__ or "").relative_to(x.ROOT).as_posix()
        assert (
            sealed["SOURCE_SHA256"]
            == hashlib.sha256(chase.git("show", f"{head}:{source}")).hexdigest()
        )
        old_modules = x.object_row(sealed["MODULE_PROVENANCE"])
        assert (
            old_modules[owner_source]
            == hashlib.sha256(chase.git("show", f"{head}:{owner_source}")).hexdigest()
        )
        assert result["MODULE_PROVENANCE"] == {**old_modules, owner_source: x.MOTIF_SOURCE_SHA256}
        assert {
            **sealed,
            "SOURCE_SHA256": result["SOURCE_SHA256"],
            "MODULE_PROVENANCE": result["MODULE_PROVENANCE"],
        } == result
        with pytest.raises(AssertionError, match="immutable result already exists"):
            x.main()
