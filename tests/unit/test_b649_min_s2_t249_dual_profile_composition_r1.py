"""Independent exact composition checks and fail-closed certificate mutations."""

from __future__ import annotations

import copy
import subprocess
from fractions import Fraction
from math import comb
from pathlib import Path

import pytest

from lottolab.research import b649_min_s2_t249_dual_profile_composition_r1 as c


@pytest.fixture(scope="module")
def inputs() -> c.Inputs:
    return c.load_inputs()


@pytest.fixture(scope="module")
def result() -> dict[str, object]:
    return c.compute_result()


def test_sealed_result_reproduces(result: dict[str, object]) -> None:
    assert c.RESULT_PATH.read_bytes() == c.render(result)
    assert result["IMPLEMENTATION_SHA256"] == c.sha((c.ROOT / c.SOURCE).read_bytes())


def test_immutable_inputs_and_judged_sibling_identities(inputs: c.Inputs) -> None:
    base, donor, pins = inputs
    assert pins["BASE_HEAD"] == c.BASE_HEAD and pins["BASE_TREE"] == c.BASE_TREE
    assert pins["DONOR_HEAD"] == c.DONOR_HEAD and pins["DONOR_TREE"] == c.DONOR_TREE
    assert c.git("merge-base", c.BASE_HEAD, c.DONOR_HEAD).decode().strip() == base["BASE_HEAD"]
    assert donor["BASE_HEAD"] == base["BASE_HEAD"]
    with pytest.raises(subprocess.CalledProcessError) as rejected:
        c.git("merge-base", "--is-ancestor", c.DONOR_HEAD, c.BASE_HEAD)
    assert rejected.value.returncode == 1


def test_exact_integer_full_t_domain(inputs: c.Inputs, result: dict[str, object]) -> None:
    donor = inputs[1]
    d = tuple(map(int, c.string(donor["TARGET_PROFILE"])))
    degrees = tuple(6 + x for x in d)
    w = sum(x * (x - 1) // 2 for x in degrees)
    triples = sum(x * (x - 1) * (x - 2) // 6 for x in degrees)
    contained_cap = sum(x * (g - 2) for x, g in zip(d, degrees, strict=True)) // 3
    theorem = c.obj(donor["THEOREM"])
    model = c.obj(donor["SUPPORT_MODEL"])
    expected: list[list[int]] = []
    for t in range(c.integer(model["T_MIN"]), c.integer(theorem["T_CAP"]) + 1):
        k4 = max(0, -(-(triples - (max(degrees) - 2) * (w - 3 * t)) // 4))
        contained = min(k4, contained_cap)
        s4 = max(112, 448 * contained + 679 * (k4 - contained))
        s3 = 2800 * w + 11872 * (t - 22) - 30800
        rational = Fraction(372228640 - 63838600 + s3) - Fraction(4 * s4, 7)
        bound = -(-rational.numerator // rational.denominator)
        assert Fraction(bound - 1) < rational <= bound
        expected.append([t, bound, k4, contained, s4, s3])
    assert c.obj(result["ROUTE_B"])["ALL_T_TERMS"] == expected
    assert expected == c.obj(donor["ROUTE_B"])["ALL_T_TERMS"]
    assert len(expected) == c.integer(theorem["T_CAP"]) - c.integer(model["T_MIN"]) + 1
    assert max(t[1] for t in expected) == donor["PROFILE_BOUND"]
    assert w == sum(comb(g, 2) for g in degrees)


def test_exactly_one_row_and_all_4646_others(inputs: c.Inputs, result: dict[str, object]) -> None:
    before = c.obj(inputs[0]["RESOLVED_ROW_BOUNDS"])
    after = c.obj(result["RESOLVED_ROW_BOUNDS"])
    assert len(before) == len(after) == 4647 and set(before) == set(after)
    assert [p for p in before if before[p] != after[p]] == [c.TARGET]
    untouched_before = {p: v for p, v in before.items() if p != c.TARGET}
    untouched_after = {p: v for p, v in after.items() if p != c.TARGET}
    assert len(untouched_before) == 4646 and untouched_before == untouched_after
    assert result["INHERITED_TWO_PROFILE_ROW_UPDATES_VERBATIM"] == inputs[0]["ROW_UPDATES"]
    for p in c.inherited.TARGETS:
        assert before[p] == after[p] == c.obj(c.obj(inputs[0]["ROW_UPDATES"])[p])["AFTER_BOUND"]


def test_entire_cursor_identity_bounds_and_coverage(
    inputs: c.Inputs, result: dict[str, object]
) -> None:
    cursor = c.obj(result["CURSOR"])
    assert cursor == inputs[0]["CURSOR"] == c.obj(inputs[1]["BASE_AUTHORITY"])["CURSOR"]
    assert c.sha(c.render(cursor)) == c.CURSOR_SHA
    ids = c.items(cursor["PROFILE_IDS"])
    assert len(ids) == len(set(c.string(p) for p in ids)) == cursor["PROFILE_COUNT"] == 197
    assert set(ids) == set(c.obj(cursor["COARSE_BOUND_PROJECTION"]))
    assert not set(ids).intersection(c.obj(result["RESOLVED_ROW_BOUNDS"]))


def test_family_all_rows_all_cursor_ties_and_remaining_profiles(result: dict[str, object]) -> None:
    ledger = c.obj(result["RESOLVED_ROW_BOUNDS"])
    cursor = c.obj(result["CURSOR"])
    all_bounds = {**ledger, **c.obj(cursor["COARSE_BOUND_PROJECTION"])}
    assert len(all_bounds) == 4647 + c.integer(cursor["PROFILE_COUNT"])
    ranked = sorted((c.integer(b), p) for p, b in all_bounds.items())
    maximum = ranked[-1][0]
    owners = sorted(p for b, p in ranked if b == maximum)
    assert result["FAMILY_BOUND_AFTER"] == maximum
    assert result["FAMILY_OWNER_IDS"] == owners
    incumbent = c.integer(result["INCUMBENT"])
    assert result["GAP_TO_INCUMBENT"] == maximum - incumbent
    assert result["EXACT_FAMILY_DELTA"] == c.integer(result["FAMILY_BOUND_BEFORE"]) - maximum
    assert result["STILL_OPEN_PROFILE_COUNT"] == sum(b > incumbent for b, _ in ranked)
    assert result["RESOLVED_OPEN_PROFILE_IDS"] == sorted(
        p for p, b in ledger.items() if c.integer(b) > incumbent
    )
    assert c.family(
        {"row1": maximum, "row2": maximum}, {"COARSE_BOUND_PROJECTION": {"cursor1": maximum}}
    ) == (maximum, ["cursor1", "row1", "row2"])


def test_all_caveats_status_snapshots_and_no_bonferroni(
    inputs: c.Inputs, result: dict[str, object]
) -> None:
    original, donor, _ = inputs
    snapshots = c.obj(result["INHERITED_CAVEATS_AND_STATUS_VERBATIM"])
    for k, v in original.items():
        if k.startswith("INHERITED_") or k in (
            "ATTAINABILITY",
            "FULL_METADATA_DIGEST_AFTER",
            "LEDGER_VIEW",
        ):
            assert snapshots[k] == v
    assert result["INHERITED_TWO_PROFILE_THEOREMS_VERBATIM"] == original["THEOREMS"]
    assert result["DONOR_THEOREM_VERBATIM"] == donor["THEOREM"]
    status = c.obj(result["DONOR_STATUS_SNAPSHOTS_VERBATIM"])
    assert status["TASK_STATUS"] == donor["TASK_STATUS"]
    assert status["HISTORICAL_R2"] == donor["HISTORICAL_R2"]
    assert status["SCENARIO_2_STATUS"] == "PROJECTED_ONLY"
    assert result["CERTIFICATES_ADOPTED"] == {**c.inherited.CAPS, c.TARGET: c.CAP}
    assert result["BONFERRONI_5_ADOPTED"] == "NO"
    assert result["GLOBAL_K20_OPTIMUM"] == "UNKNOWN"


def test_theorem_execution_forbidden(
    monkeypatch: pytest.MonkeyPatch, result: dict[str, object]
) -> None:
    def forbidden() -> dict[str, object]:
        pytest.fail("theorem must not be re-executed")

    monkeypatch.setattr(c.inherited, "theorem_a", forbidden)
    monkeypatch.setattr(c.inherited, "theorem_b", forbidden)
    assert c.compute_result() == result


@pytest.mark.parametrize("pid", [c.inherited.PROFILE_A, "0" * 20])
def test_wrong_donor_profile_fails_closed(inputs: c.Inputs, pid: str) -> None:
    donor = copy.deepcopy(inputs[1])
    donor["TARGET_PROFILE"] = pid
    with pytest.raises(AssertionError, match="wrong donor profile"):
        c.validate_donor(donor)


@pytest.mark.parametrize(
    "mutation", ["bound", "cap", "first_term", "last_term", "rounding", "bonferroni"]
)
def test_mutated_certificate_fails_closed(inputs: c.Inputs, mutation: str) -> None:
    donor = copy.deepcopy(inputs[1])
    if mutation == "bound":
        donor["PROFILE_BOUND"] = c.integer(donor["PROFILE_BOUND"]) + 1
    elif mutation == "cap":
        c.obj(donor["THEOREM"])["T_CAP"] = c.CAP - 1
    elif mutation in ("first_term", "last_term"):
        c.items(c.obj(donor["ROUTE_B"])["ALL_T_TERMS"]).pop(0 if mutation == "first_term" else -1)
    elif mutation == "rounding":
        row = c.items(c.items(c.obj(donor["ROUTE_B"])["ALL_T_TERMS"])[-1])
        row[1] = c.integer(row[1]) - 1
    else:
        c.obj(donor["HISTORICAL_R2"])["BONFERRONI_5_USED"] = "YES"
    with pytest.raises(AssertionError, match=r"scope|bound/domain|unadopted"):
        c.validate_donor(donor)


@pytest.mark.parametrize(
    "mutation",
    ["profile", "bound", "float", "cursor_bound", "cursor_id", "cursor_partition", "other_row"],
)
def test_composition_mutations_fail_closed(inputs: c.Inputs, mutation: str) -> None:
    base, donor, _ = inputs
    bounds = {p: c.integer(v) for p, v in c.obj(base["RESOLVED_ROW_BOUNDS"]).items()}
    cursor = copy.deepcopy(c.obj(base["CURSOR"]))
    pid, bound = c.TARGET, c.integer(donor["PROFILE_BOUND"])
    if mutation == "profile":
        pid = c.inherited.PROFILE_B
    elif mutation == "bound":
        bound += 1
    elif mutation == "float":
        c.obj(c.obj(donor := copy.deepcopy(donor))["ROW_UPDATE"])["AFTER"] = {
            "cap": 249,
            "bound": float(bound),
            "s4_base": 112,
        }
    elif mutation == "cursor_bound":
        cursor["BOUND"] = c.integer(cursor["BOUND"]) - 1
    elif mutation == "cursor_id":
        c.items(cursor["PROFILE_IDS"])[0] = "0" * 20
    elif mutation == "cursor_partition":
        c.obj(c.obj(cursor["PARTITION"])["UNRESOLVED_FRONTIER_UNDER_W785_CURSOR"])["COUNT"] = 196
    else:
        bounds[c.inherited.PROFILE_A] += 1
    with pytest.raises(AssertionError, match=r"wrong update|bound/domain|cursor|projection"):
        c.compose(bounds, cursor, c.obj(base["CURSOR"]), donor, pid, bound)


def test_source_hash_and_missing_donor_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(AssertionError, match="source-hash"):
        c.blob(c.BASE_HEAD, c.BASE_RESULT, "0" * 64)
    with pytest.raises(AssertionError, match="source-hash"):
        c.local_blob(f"{c.SOURCES}/donor-result.json", "0" * 64)
    monkeypatch.setattr(c, "DONOR_HEAD", "0" * 40)
    with pytest.raises(subprocess.CalledProcessError):
        c.load_inputs()


def test_missing_snapshot_fails_closed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(c, "ROOT", tmp_path)
    with pytest.raises(FileNotFoundError):
        c.local_blob(f"{c.SOURCES}/donor-result.json", c.DONOR_RESULT_SHA)


def test_duplicate_missing_rows_and_duplicate_json_fail_closed(inputs: c.Inputs) -> None:
    rows = [(p, c.integer(v)) for p, v in c.obj(inputs[0]["RESOLVED_ROW_BOUNDS"]).items()]
    for bad in [rows[:-1], [rows[0], *rows[:-1]]]:
        with pytest.raises(AssertionError, match="row count"):
            c.validate_rows(bad)
    with pytest.raises(AssertionError, match="duplicate JSON"):
        c.decode(b'{"PROFILE_BOUND":1,"PROFILE_BOUND":2}')


def test_forged_expected_cursor_fails_closed(inputs: c.Inputs) -> None:
    cursor = copy.deepcopy(c.obj(inputs[0]["CURSOR"]))
    cursor["BOUND"] = c.integer(cursor["BOUND"]) - 1
    with pytest.raises(AssertionError, match="expected cursor source-hash"):
        c.validate_cursor(cursor, cursor)
