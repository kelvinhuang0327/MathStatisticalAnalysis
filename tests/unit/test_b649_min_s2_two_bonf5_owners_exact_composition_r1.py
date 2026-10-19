"""Full family replay and falsifiable guards for exact two-row composition."""

from __future__ import annotations

import copy
from fractions import Fraction
from math import comb

import pytest

from lottolab.research import b649_min_s2_two_bonf5_owners_exact_composition_r1 as c


@pytest.fixture(scope="module")
def inputs() -> c.Inputs:
    return c.load_inputs()


@pytest.fixture(scope="module")
def result() -> dict[str, object]:
    return c.compute_result()


def test_exact_result_and_authority_status(inputs: c.Inputs, result: dict[str, object]) -> None:
    path = c.result_path()
    assert path is not None and path.read_bytes() == c.render(result)
    assert path.name == f"{c.RESULT_PREFIX}{c.sha(c.render(result))}.json"
    for head, tree, path, digest in (
        (c.BASE_HEAD, c.BASE_TREE, c.BASE_RESULT, c.BASE_SHA),
        (c.DONOR_HEAD, c.DONOR_TREE, c.DONOR_RESULT, c.DONOR_SHA),
    ):
        assert c.git("rev-parse", f"{head}^{{tree}}").decode().strip() == tree
        assert c.sha(c.blob(head, path, digest)) == digest
    provenance = inputs[2]
    assert (
        provenance["BASE_FRESH_JUDGE"] == provenance["DONOR_FRESH_JUDGE"] == "VERIFIED_WITH_CAVEATS"
    )
    assert provenance["ORIGINAL_BONF5_STATUS"] == "SELF_CHECK_ONLY"
    assert result["DONOR_ORIGINAL_STATUS_VERBATIM"] == inputs[1]["ORIGINAL_DONOR_STATUS"]
    inherited = c.obj(result["INHERITED_CAVEATS_AND_STATUS_VERBATIM"])
    assert all(inputs[0][key] == value for key, value in inherited.items())
    assert result["CERTIFICATES_ADOPTED"] == inputs[0]["CERTIFICATES_ADOPTED"]
    assert result["INHERITED_TARGET_BONFERRONI_5"] == inputs[0]["BONFERRONI_5_ADOPTED"]
    assert result["GLOBAL_K20_OPTIMUM"] == "UNKNOWN"


@pytest.mark.parametrize(
    "pid,s5,full,cap_bound",
    [
        (c.PROFILES[0], 7042, 313386680, 313277174),
        (c.PROFILES[1], 7098, 313386292, 313277230),
    ],
)
def test_independent_complete_rational_envelope(
    inputs: c.Inputs, pid: str, s5: int, full: int, cap_bound: int
) -> None:
    cert = c.obj(c.obj(inputs[1]["PROFILE_CERTIFICATES"])[pid])
    degrees = [int(v) for v in pid]
    g = [6 + v for v in degrees]
    w, j = sum(comb(v, 2) for v in g), sum(comb(v, 3) for v in g)
    amax = sum(v * (4 + v) for v in degrees) // 3
    terms: list[list[int]] = []
    for t in range(22, 266):
        k4 = max(0, -(-(j - (max(g) - 2) * (w - 3 * t)) // 4))
        contained = min(k4, amax)
        s4 = max(112, 448 * contained + 679 * (k4 - contained))
        s3 = 2800 * w + 11872 * (t - 22) - 30800
        rational = Fraction(372228640 - 63838600 + s3) - Fraction(4 * s4, 7)
        fourth = -(-rational.numerator // rational.denominator)
        assert fourth - 1 < rational <= fourth
        bound = min(fourth, 372228640 - 63838600 + s3 - s4 + s5) if t == 265 else fourth
        terms.append([t, bound, k4, contained, s4, s3])
    assert cert["ALL_T_TERMS"] == terms
    assert cert["S5_CAP"] == s5 and cert["T_CAP"] == 265
    assert cert["TERM_COUNT"] == len(terms) == 244
    assert max(t[1] for t in terms) == cert["FULL_PROFILE_BOUND"] == full
    assert [t[0] for t in terms if t[1] == full] == [264]
    assert cert["MAX_T"] == 264 and terms[-1][1] == cap_bound < full
    assert terms[:-1] == c.items(cert["OLD_TERMS"])[:-1]
    assert terms[-1][2:] == c.items(c.items(cert["OLD_TERMS"])[-1])[2:]
    assert cert["STRICT_GAIN_EXCLUDED"] == "NO" and full > 313263888


def test_independent_full_family_and_single_updates(
    inputs: c.Inputs, result: dict[str, object]
) -> None:
    before = {p: c.integer(v) for p, v in c.obj(inputs[0]["RESOLVED_ROW_BOUNDS"]).items()}
    after = {p: c.integer(v) for p, v in c.obj(result["RESOLVED_ROW_BOUNDS"]).items()}
    coarse = {
        p: c.integer(v)
        for p, v in c.obj(c.obj(inputs[0]["CURSOR"])["COARSE_BOUND_PROJECTION"]).items()
    }
    assert len(before) == len(after) == 4647 and set(after) == set(before)
    assert {p for p in before if before[p] != after[p]} == set(c.PROFILES)
    others = {p: b for p, b in before.items() if p not in c.PROFILES}
    assert len(others) == 4645 and others == {p: b for p, b in after.items() if p not in c.PROFILES}
    assert result["OTHER_4645_BOUNDS_SHA256"] == c.sha(c.projection(others))
    assert result["CURSOR"] == inputs[0]["CURSOR"]
    assert result["CURSOR_SHA256"] == c.sha(c.render(inputs[0]["CURSOR"]))
    assert len(coarse) == result["CURSOR_PROFILE_COUNT"] == 197
    assert max(coarse.values()) == 313394584 and not set(after).intersection(coarse)
    assert max([*before.values(), *coarse.values()]) == result["FAMILY_BOUND_BEFORE"] == 313395448
    for pid in c.PROFILES:
        single = {**before, pid: after[pid], **coarse}
        assert max(single.values()) == c.obj(result["FAMILY_AFTER_SINGLE_UPDATE"])[pid] == 313395448
    merged = {**after, **coarse}
    maximum = max(merged.values())
    assert maximum == result["FAMILY_BOUND_AFTER"] == 313395344
    assert (
        sorted(p for p, b in merged.items() if b == maximum)
        == result["FAMILY_OWNER_IDS"]
        == ["66655555555511100000", "66665555554431000000"]
    )
    assert result["EXACT_DELTA"] == 104 and result["GAP_TO_INCUMBENT"] == 131456
    assert sum(b > 313263888 for b in merged.values()) == result["STILL_OPEN_PROFILE_COUNT"] == 1569
    assert result["SOLVER_CALLS"] == result["MATHEMATICAL_THEOREMS_REEXECUTED"] == 0


@pytest.mark.parametrize(
    "key,value",
    [
        ("PROFILE_ID", c.PROFILES[1]),
        ("S5_CAP", 7098),
        ("FULL_PROFILE_BOUND", 313277174),
        ("T_CAP", 266),
        ("T_CAP", 264),
        ("COMPLETE_T_RANGE", [23, 265]),
        ("TERM_COUNT", 243),
        ("MAX_T", 265),
        ("CHANGED_FIELDS", [[264, "BOUND"]]),
        ("STRICT_GAIN_EXCLUDED", "YES"),
    ],
)
def test_rejects_wrong_profile_certificate(inputs: c.Inputs, key: str, value: object) -> None:
    donor = copy.deepcopy(inputs[1])
    c.obj(c.obj(donor["PROFILE_CERTIFICATES"])[c.PROFILES[0]])[key] = value
    with pytest.raises(AssertionError):
        c.validate_donor(donor)


@pytest.mark.parametrize("mode", ["missing", "duplicate", "rounding", "lower_term"])
def test_rejects_t_term_tampering(inputs: c.Inputs, mode: str) -> None:
    donor = copy.deepcopy(inputs[1])
    terms = c.items(c.obj(c.obj(donor["PROFILE_CERTIFICATES"])[c.PROFILES[0]])["ALL_T_TERMS"])
    if mode == "missing":
        terms.pop()
    elif mode == "duplicate":
        terms[1] = copy.deepcopy(terms[0])
    else:
        row = c.items(terms[-2] if mode == "rounding" else terms[0])
        row[1] = c.integer(row[1]) - 1
    with pytest.raises(AssertionError, match="envelope"):
        c.validate_donor(donor)


@pytest.mark.parametrize("mutation", ["s4_sign", "s5_sign", "floor"])
def test_rejects_runtime_sign_rounding_mutations(
    inputs: c.Inputs, monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    original = c.moment_bounds

    def broken(s3: int, s4: int, s5: int) -> tuple[int, int]:
        fourth, fifth = original(s3, s4, s5)
        if mutation == "s4_sign":
            return (7 * (372228640 - 63838600 + s3) + 4 * s4 + 6) // 7, fifth
        if mutation == "s5_sign":
            return fourth, fifth - 2 * s5
        return (7 * (372228640 - 63838600 + s3) - 4 * s4) // 7, fifth

    monkeypatch.setattr(c, "moment_bounds", broken)
    with pytest.raises(AssertionError, match="sign or rounding"):
        c.validate_donor(inputs[1])


@pytest.mark.parametrize("mode", ["missing", "duplicate", "extra", "wrong_profile", "cap_term"])
def test_rejects_update_scope(inputs: c.Inputs, mode: str) -> None:
    sealed, donor, _ = inputs
    certs = c.validate_donor(donor)
    updates = [(p, c.integer(c.obj(certs[p])["FULL_PROFILE_BOUND"])) for p in c.PROFILES]
    if mode == "missing":
        updates.pop()
    elif mode == "duplicate":
        updates[1] = updates[0]
    elif mode == "extra":
        updates.append(updates[0])
    elif mode == "wrong_profile":
        updates[0] = (c.prior.TARGET, updates[0][1])
    else:
        updates[0] = (updates[0][0], c.integer(c.obj(certs[c.PROFILES[0]])["T265_TERM_BOUND"]))
    rows = [(p, c.integer(v)) for p, v in c.obj(sealed["RESOLVED_ROW_BOUNDS"]).items()]
    with pytest.raises(AssertionError):
        c.compose(rows, c.obj(sealed["CURSOR"]), sealed, certs, updates)


@pytest.mark.parametrize(
    "key", ["BOUND", "PROFILE_IDS", "COARSE_BOUND_PROJECTION", "SOURCE_IDENTITY"]
)
def test_rejects_cursor_mutation(inputs: c.Inputs, key: str) -> None:
    sealed, donor, _ = inputs
    cursor = copy.deepcopy(c.obj(sealed["CURSOR"]))
    cursor[key] = "tampered"
    certs = c.validate_donor(donor)
    rows = [(p, c.integer(v)) for p, v in c.obj(sealed["RESOLVED_ROW_BOUNDS"]).items()]
    updates = [(p, c.integer(c.obj(certs[p])["FULL_PROFILE_BOUND"])) for p in c.PROFILES]
    with pytest.raises(AssertionError):
        c.compose(rows, cursor, sealed, certs, updates)


@pytest.mark.parametrize("mode", ["duplicate", "missing", "other_bound"])
def test_rejects_ledger_tampering(inputs: c.Inputs, mode: str) -> None:
    sealed, donor, _ = inputs
    certs = c.validate_donor(donor)
    rows = [(p, c.integer(v)) for p, v in c.obj(sealed["RESOLVED_ROW_BOUNDS"]).items()]
    if mode == "duplicate":
        rows[1] = rows[0]
    elif mode == "missing":
        rows.pop()
    else:
        rows[0] = (rows[0][0], rows[0][1] + 1)
    updates = [(p, c.integer(c.obj(certs[p])["FULL_PROFILE_BOUND"])) for p in c.PROFILES]
    with pytest.raises(AssertionError):
        c.compose(rows, c.obj(sealed["CURSOR"]), sealed, certs, updates)


@pytest.mark.parametrize(
    "constant", ["BASE_SHA", "DONOR_SHA", "DONOR_SOURCE_SHA", "BASE_TREE", "DONOR_TREE"]
)
def test_rejects_source_result_identity_tampering(
    monkeypatch: pytest.MonkeyPatch, constant: str
) -> None:
    monkeypatch.setattr(c, constant, "0" * (40 if constant.endswith("TREE") else 64))
    with pytest.raises(AssertionError):
        c.load_inputs()


def test_rejects_report_tampering(inputs: c.Inputs) -> None:
    reports = copy.deepcopy(c.obj(inputs[2]["JUDGE_REPORTS_VERBATIM"]))
    reports["DONOR"] = c.string(reports["DONOR"]) + "\nVERIFIED\n"
    with pytest.raises(AssertionError, match="SHA"):
        c.validate_reports(reports)


def test_rejects_degree_cap_and_sign_tampering(inputs: c.Inputs) -> None:
    for key in ("S5_CAP", "COMMON_PAIR_SUM_CAP"):
        donor = copy.deepcopy(inputs[1])
        c.obj(c.obj(donor["DEGREE_S5_PROOFS"])[c.PROFILES[0]])[key] = 0
        with pytest.raises(AssertionError, match="S5"):
            c.validate_donor(donor)
    donor = copy.deepcopy(inputs[1])
    c.obj(donor["BONFERRONI_PROOF"])["SIGNS"] = [1, -1, 1, 1, -1]
    with pytest.raises(AssertionError):
        c.validate_donor(donor)
