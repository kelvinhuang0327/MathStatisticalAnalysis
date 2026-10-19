"""Independent numeric reproduction and rejecting mutations for two exact profiles."""

from __future__ import annotations

import copy
import inspect
from collections.abc import Callable
from fractions import Fraction
from math import comb
from typing import cast

import pytest

from lottolab.research import b649_min_s2_bonf5_tied_owners_cert_r1 as x


@pytest.fixture(scope="module")
def result() -> dict[str, object]:
    return x.compute_result()


def test_source_identity_status_and_model(result: dict[str, object]) -> None:
    assert result["BASE_HEAD"] == "8fac3d41b2d519d92b06d6ceb933fe31072c6409"
    assert result["BASE_TREE"] == "62f80eecf3f1045c905d345a3e68fb2ad078eaec"
    assert result["ORIGINAL_DONOR_STATUS"] == {
        "JUDGE_MODE": "SELF_CHECK_ONLY",
        "TASK_STATUS": "COMPLETE_SELF_CHECK_ONLY",
    }
    assert result["MODEL"] == {
        "TICKETS": 20,
        "LABELS_PER_TICKET": 6,
        "POOL": 49,
        "TRIPLES": 22,
        "PAIRS": 27,
        "PAIR_LINEARITY": True,
    }
    assert set(x.obj(result["PROFILE_CERTIFICATES"])) == set(x.PROFILES)
    assert len(x.obj(result["HELPER_SHA256"])) == 29
    assert result["SOURCE_SHA256"] == x.sha((x.ROOT / x.SOURCE).read_bytes())


@pytest.mark.parametrize("pid", x.PROFILES)
def test_applicability_and_cap_identity(pid: str, result: dict[str, object]) -> None:
    d = x.profile_degrees(pid)
    assert len(d) == 20 and sum(d) == 3 * 22 and sum(6 - v for v in d) == 2 * 27
    assert sum(6 + v for v in d) == 2 * 93 and sum(comb(6 + v, 2) for v in d) == 828
    proof = x.obj(x.obj(result["CAP_AUTHORITIES"])[pid])
    x.cap_authority(pid, proof)
    assert proof["ATTEMPT_INDEX"] == (3074 if pid == x.PROFILE_1 else 3073)
    assert proof["REFUTED_GRAPH_TRIANGLE_COUNT"] == 266
    assert proof["CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND"] == 265
    for key in (
        "PROFILE_IDS",
        "STATUS",
        "TARGET_TRIANGLE_CAP",
        "ATTEMPT_INDEX",
        "ROUTE",
        "CERTIFICATE_KIND",
        "WEDGE_COUNT",
        "EXTERNAL_TIMEOUT_EXIT_CODE",
        "REFUTED_GRAPH_TRIANGLE_COUNT",
        "CERTIFIED_OPEN_WEDGE_LOWER_BOUND",
    ):
        with pytest.raises(AssertionError, match="cap authority"):
            x.cap_authority(pid, {**proof, key: None})
    other = x.PROFILE_2 if pid == x.PROFILE_1 else x.PROFILE_1
    with pytest.raises(AssertionError, match="cap authority"):
        x.cap_authority(other, proof)


@pytest.mark.parametrize(
    "pid,thresholds,common,cap",
    [
        (x.PROFILE_1, [22, 21, 21, 21, 18, 0], 742, 7042),
        (x.PROFILE_2, [22, 22, 20, 20, 20, 0], 750, 7098),
    ],
)
def test_independent_s5_caps(
    pid: str, thresholds: list[int], common: int, cap: int, result: dict[str, object]
) -> None:
    proof = x.obj(x.obj(result["DEGREE_S5_PROOFS"])[pid])
    assert [x.items(r)[5] for r in x.items(proof["THRESHOLD_CAPS"])] == thresholds
    assert 22 * comb(5, 2) + sum(thresholds[k - 1] * (k + 3) for k in range(2, 7)) == common
    assert sum(comb(int(v), 2) for v in pid) == 132
    assert proof["COMMON_PAIR_SUM_CAP"] == common
    assert proof["N_2T_CAP"] == 132 and proof["S5_CAP"] == 7 * (common + 2 * 132) == cap
    assert proof["BOUND_DIRECTION"] == "UPPER_BOUND_ADDED"
    for key in ("D", "THRESHOLD_CAPS", "S5_CAP", "N_2T_CAP"):
        with pytest.raises(AssertionError, match="S5 proof"):
            x.degree_s5_proof(pid, {**proof, key: None})


def test_reused_counting_and_sign_directions(result: dict[str, object]) -> None:
    proof = x.obj(result["BONFERRONI_PROOF"])
    assert proof["R_CAP"] == 7 and proof["SIGNS"] == [1, -1, 1, -1, 1]
    assert proof["S4_DIRECTION"] == "LOWER_BOUND_SUBTRACTED"
    assert proof["S5_DIRECTION"] == "UPPER_BOUND_ADDED"
    assert x.obj(result["S123"])["S1"] == 372228640
    assert x.obj(result["S123"])["S2"] == 63838600
    local = x.obj(result["S5_LOCAL_IDENTITY"])
    assert local["LOCAL_CASE_COUNT"] == 2544
    assert local["LOCAL_COUNTS"] == [1024, 1280, 240]
    assert local["LOCAL_TABLE_SHA256"] == (
        "f2d1cdeeadbfe1951efa43ab32e7c2570a5202967c46003855da2fc3303c2e2b"
    )
    with pytest.raises(AssertionError, match="incorrect Bonferroni signs"):
        x.proven.multiplicity_proof((1, -1, 1, 1, -1))
    low = x.proven.moment_bounds(1000000, 1000, 100)
    assert x.proven.moment_bounds(1000000, 1001, 100)[1] == low[1] - 1
    assert x.proven.moment_bounds(1000000, 1000, 101)[1] == low[1] + 1


@pytest.mark.parametrize(
    "pid,j,cap,bound,last",
    [
        (x.PROFILE_1, 2320, 7042, 313386680, 313277174),
        (x.PROFILE_2, 2322, 7098, 313386292, 313277230),
    ],
)
def test_every_term_and_maximum(
    pid: str, j: int, cap: int, bound: int, last: int, result: dict[str, object]
) -> None:
    env = x.obj(x.obj(result["PROFILE_CERTIFICATES"])[pid])
    old, terms = x.items(env["OLD_TERMS"]), x.items(env["ALL_T_TERMS"])
    assert [x.items(r)[0] for r in terms] == list(range(22, 266))
    assert len(terms) == env["TERM_COUNT"] == 244 and old[:-1] == terms[:-1]
    for raw_old, raw_new in zip(old, terms, strict=True):
        t, fourth, k4, a, s4, s3 = [x.integer(v) for v in x.items(raw_old)]
        assert k4 == max(0, -(-(j - 10 * (828 - 3 * t)) // 4))
        assert a == min(k4, 198) and s4 == max(112, 679 * k4 - 231 * a)
        assert s3 == 2800 * 828 + 11872 * (t - 22) - 30800
        exact = Fraction(372228640 - 63838600 + s3) - Fraction(4 * s4, 7)
        assert fourth == -(-exact.numerator // exact.denominator)
        assert 0 <= fourth - exact < 1
        fifth = 372228640 - 63838600 + s3 - s4 + cap
        expected = min(fourth, fifth) if t == 265 else fourth
        assert x.items(raw_new) == [t, expected, k4, a, s4, s3]
    assert x.items(terms[-1])[1] == last == env["T265_TERM_BOUND"]
    assert max(x.integer(x.items(r)[1]) for r in terms) == env["FULL_PROFILE_BOUND"] == bound
    assert [x.items(r)[0] for r in terms if x.items(r)[1] == bound] == [264]
    assert env["PRE_UPDATE_BOUND"] == 313395448
    assert env["STRICT_GAIN_EXCLUDED"] == "NO"
    assert env["BOUND_MINUS_INCUMBENT"] == bound - 313263888 > 0


@pytest.mark.parametrize("pid", x.PROFILES)
def test_bad_s5_range_and_profile_substitution(pid: str) -> None:
    donor = x.decode(x.pinned_bytes(x.proven.DONOR_RESULT))
    cert = x.obj(x.obj(donor["PROFILE_CERTIFICATES"])[pid])
    other = x.PROFILE_2 if pid == x.PROFILE_1 else x.PROFILE_1
    for cap in (0, x.S5_CAPS[pid] - 1, x.S5_CAPS[pid] + 1, x.S5_CAPS[other]):
        with pytest.raises(AssertionError, match="wrong S5 cap"):
            x.envelope(pid, cert, cap)
    with pytest.raises(AssertionError, match="cross-profile"):
        x.envelope(other, cert, x.S5_CAPS[other])
    for cap, t_min in ((264, 22), (266, 22), (265, 23), (265, 21)):
        with pytest.raises(AssertionError, match="wrong T range"):
            x.original_terms(pid, cap, t_min)
    with pytest.raises(AssertionError, match="profile identity"):
        x.profile_degrees(x.proven.TARGET)
    damaged = copy.deepcopy(cert)
    damaged["ALL_T_TERMS"] = x.items(damaged["ALL_T_TERMS"])[1:]
    with pytest.raises(AssertionError, match="T envelope"):
        x.envelope(pid, damaged, x.S5_CAPS[pid])


def test_family_projection_includes_every_cursor_profile(result: dict[str, object]) -> None:
    effect = x.obj(result["FAMILY_EFFECT"])
    assert effect["STATUS"] == "PROJECTED_COMPOSITION"
    views = x.obj(effect["VIEWS"])
    for name in ("AFTER_TARGET_BONF5", "AFTER_ONLY_PROFILE_1", "AFTER_ONLY_PROFILE_2"):
        assert x.obj(views[name])["BOUND"] == 313395448
    assert x.obj(views["AFTER_ONLY_PROFILE_1"])["OWNERS"] == [x.PROFILE_2]
    assert x.obj(views["AFTER_ONLY_PROFILE_2"])["OWNERS"] == [x.PROFILE_1]
    assert x.obj(views["AFTER_BOTH_PROFILES"])["BOUND"] == 313395344
    assert effect["NEXT_OWNER_IDS"] == ["66655555555511100000", "66665555554431000000"]
    assert effect["PROJECTED_FAMILY_DELTA"] == 104 and effect["GAP_TO_INCUMBENT"] == 131456
    assert effect["SOURCE_LEDGER_SHA256_BEFORE"] == effect["SOURCE_LEDGER_SHA256_AFTER"]
    assert effect["CURSOR_SHA256_BEFORE"] == effect["CURSOR_SHA256_AFTER"]
    cursor = x.obj(effect["CURSOR"])
    assert cursor["ID"] == "66544333333333332222" and cursor["BOUND"] == 313394584
    assert len(x.obj(cursor["COARSE_BOUND_PROJECTION"])) == cursor["PROFILE_COUNT"] == 197
    assert effect["TOTAL_PROFILES"] == effect["RESOLVED_ROWS"] + effect["CURSOR_PROFILES"] == 4844
    assert effect["CURSOR_PRESERVED"] == "PASS"
    assert effect["SHARED_LEDGER_ADOPTION"] == "NONE"
    assert effect["REPLACES_A_COMBINED_AUTHORITY"] == "NO"


def test_composition_rejects_scope_and_cursor_tampering(result: dict[str, object]) -> None:
    ledger = x.decode(x.pinned_bytes(x.T249_RESULT))
    original = x.render(ledger)
    certs = x.obj(result["PROFILE_CERTIFICATES"])
    with pytest.raises(AssertionError, match="certificate scope"):
        x.family_effect(ledger, {x.PROFILE_1: certs[x.PROFILE_1]})
    damaged = copy.deepcopy(certs)
    x.obj(damaged[x.PROFILE_1])["PROFILE_ID"] = x.PROFILE_2
    with pytest.raises(AssertionError, match="row replacement"):
        x.family_effect(ledger, damaged)
    changed = copy.deepcopy(ledger)
    x.obj(changed["CURSOR"])["BOUND"] = 313395500
    with pytest.raises(AssertionError, match="cursor integrity"):
        x.replay_t249(changed)
    assert x.render(ledger) == original


@pytest.mark.parametrize(
    "path",
    [
        x.proven.DONOR_RESULT,
        f"src/lottolab/research/{x.proven.DONOR_MODULE}.py",
        x.T249_RESULT,
        x.T249_SOURCE,
        x.TARGET_RESULT,
        x.proven.R30_RESULT,
    ],
)
def test_tampered_source_bytes_rejected(path: str, monkeypatch: pytest.MonkeyPatch) -> None:
    original = x.git
    head = x.PINS[path][0]

    def changed(*args: str) -> bytes:
        raw = original(*args)
        return raw + b" " if args == ("show", f"{head}:{path}") else raw

    with monkeypatch.context() as patch:
        patch.setattr(x, "git", changed)
        with pytest.raises(AssertionError, match="tampered source bytes"):
            x.pinned_bytes(path)


@pytest.mark.parametrize("field", ["BASE_TREE", "T249_TREE"])
def test_wrong_tree_rejected(field: str, monkeypatch: pytest.MonkeyPatch) -> None:
    with monkeypatch.context() as patch:
        patch.setattr(x, field, "0" * 40)
        with pytest.raises(AssertionError, match="tree identity"):
            x.authority()


@pytest.mark.parametrize(
    "before,after",
    [
        ("fixed - s4_floor + s5_cap", "fixed + s4_floor + s5_cap"),
        ("fixed - s4_floor + s5_cap", "fixed - s4_floor - s5_cap"),
        ("-(-exact.numerator // exact.denominator)", "exact.numerator // exact.denominator"),
    ],
)
def test_sign_and_rounding_mutations_killed(
    before: str, after: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = x.proven.moment_bounds
    source = inspect.getsource(original)
    assert source.count(before) == 1
    namespace: dict[str, object] = dict(original.__globals__)
    exec(compile(source.replace(before, after), "<controlled-mutation>", "exec"), namespace)
    mutant = cast(Callable[[int, int, int], tuple[int, int]], namespace["moment_bounds"])

    def guard() -> None:
        fourth, fifth = x.proven.moment_bounds(5169024, 285153, 7042)
        rational = Fraction(372228640 - 63838600 + 5169024) - Fraction(4 * 285153, 7)
        assert fourth == -(-rational.numerator // rational.denominator)
        assert fifth == 372228640 - 63838600 + 5169024 - 285153 + 7042

    guard()
    with monkeypatch.context() as patch:
        patch.setattr(x.proven, "moment_bounds", mutant)
        with pytest.raises(AssertionError):
            guard()
    guard()


def test_sealed_json_replay_and_restrictions(result: dict[str, object]) -> None:
    assert x.RESULT_PATH.read_bytes() == x.render(result)
    x.verify_result(result)
    assert result["SOLVER_CALLS"] == result["PORTFOLIO_ENUMERATIONS"] == 0
    assert result["SHARED_LEDGER_WRITES"] == 0
    assert result["HEAVY_SOLVER_STARTED"] == result["REMOTE_WRITE"] == "NO"
    assert result["GLOBAL_K20_OPTIMUM"] == "UNKNOWN"


def test_sealed_result_tampering_rejected(
    result: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    # The real recomputation is checked above; this seam isolates serialization integrity.
    with monkeypatch.context() as patch:
        patch.setattr(x, "compute_result", lambda: result)
        for field in ("S5_CAP", "FULL_PROFILE_BOUND", "T_CAP", "PROFILE_ID"):
            damaged = copy.deepcopy(result)
            x.obj(x.obj(damaged["PROFILE_CERTIFICATES"])[x.PROFILE_1])[field] = None
            with pytest.raises(AssertionError, match="tampered formal"):
                x.verify_result(damaged)
