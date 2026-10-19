"""Exact full-ledger composition and adversarial authority checks."""

from __future__ import annotations

import copy
import json
import subprocess
from fractions import Fraction
from math import comb
from pathlib import Path
from typing import cast

import pytest

from lottolab.research import b649_min_s2_t249_bonf5_single_row_composition_r1 as c


@pytest.fixture(scope="module")
def inputs() -> c.Inputs:
    return c.load_inputs()


@pytest.fixture(scope="module")
def result() -> dict[str, object]:
    return c.compute_result()


def test_result_bytes_and_authorities(inputs: c.Inputs, result: dict[str, object]) -> None:
    assert c.render(result) == c.RESULT_PATH.read_bytes()
    assert c.sha(c.blob(c.BASE_HEAD, c.BASE_RESULT, c.BASE_SHA)) == c.BASE_SHA
    assert c.sha(c.blob(c.DONOR_HEAD, c.DONOR_RESULT, c.DONOR_SHA)) == c.DONOR_SHA
    assert result["IMPLEMENTATION_SHA256"] == c.sha((c.ROOT / c.SOURCE).read_bytes())
    external = c.obj(inputs[2]["EXTERNAL_JUDGES"])
    assert c.obj(external["BASE"])["STATUS"] == "VERIFIED_WITH_CAVEATS"
    assert c.obj(external["DONOR"])["STATUS"] == "VERIFIED"


def test_complete_envelope_independent_rational_replay(inputs: c.Inputs) -> None:
    donor = inputs[1]
    envelope = c.obj(donor["ENVELOPE"])
    d = tuple(int(v) for v in c.TARGET)
    g = tuple(6 + v for v in d)
    w, j = sum(comb(v, 2) for v in g), sum(comb(v, 3) for v in g)
    contained_cap = sum(v * (degree - 2) for v, degree in zip(d, g, strict=True)) // 3
    cap = c.integer(donor["TRIANGLE_CAP"])
    s5 = c.integer(c.obj(donor["S5_PROOF"])["S5_CAP"])
    independent: list[list[int]] = []
    for t in range(22, cap + 1):
        floor = max(0, -(-(j - (max(g) - 2) * (w - 3 * t)) // 4))
        a = min(floor, contained_cap)
        s4 = max(comb(d.count(0), 4) * 48, 448 * a + 679 * (floor - a))
        s3 = 2800 * w + 11872 * (t - 22) - 30800
        rational = Fraction(372228640 - 63838600 + s3) - Fraction(4 * s4, 7)
        fourth = -(-rational.numerator // rational.denominator)
        assert fourth - 1 < rational <= fourth
        fifth = 372228640 - 63838600 + s3 - s4 + s5
        bound = min(fourth, fifth) if t == cap else fourth
        independent.append([t, bound, floor, a, s4, s3])
    assert envelope["ALL_T_TERMS"] == independent
    assert len(independent) == cap - 22 + 1
    maximum = max(row[1] for row in independent)
    assert envelope["FULL_PROFILE_BOUND"] == maximum
    assert envelope["MAX_T"] == max(row[0] for row in independent if row[1] == maximum)
    assert maximum > independent[-1][1]
    old = c.items(envelope["OLD_TERMS"])
    assert independent[:-1] == old[:-1]
    assert independent[-1][2:] == c.items(old[-1])[2:]
    assert envelope["LOWER_T_SHA256"] == c.sha(json.dumps(old[:-1], sort_keys=True).encode())


def test_all_rows_cursor_and_certificate_preservation(
    inputs: c.Inputs, result: dict[str, object]
) -> None:
    sealed = inputs[0]
    before, after = c.obj(sealed["RESOLVED_ROW_BOUNDS"]), c.obj(result["RESOLVED_ROW_BOUNDS"])
    assert set(before) == set(after) and len(after) == 4647
    assert [p for p in before if before[p] != after[p]] == [c.TARGET]
    assert {p: v for p, v in before.items() if p != c.TARGET} == {
        p: v for p, v in after.items() if p != c.TARGET
    }
    assert c.replay_base(sealed) == before
    for pid in c.base.TARGETS:
        assert before[pid] == after[pid]
    assert result["CERTIFICATES_ADOPTED"] == sealed["CERTIFICATES_ADOPTED"]
    assert result["BONFERRONI_5_OTHER_PROFILES_ADOPTED"] == []
    for pid in ("66555555555441000000", "66555555555522000000"):
        assert after[pid] == before[pid]
    cursor = c.obj(result["CURSOR"])
    assert cursor == sealed["CURSOR"]
    assert c.sha(c.render(cursor)) == c.base.CURSOR_SHA
    assert (
        len(c.items(cursor["PROFILE_IDS"])) == len(c.obj(cursor["COARSE_BOUND_PROJECTION"])) == 197
    )
    assert not set(after).intersection(c.obj(cursor["COARSE_BOUND_PROJECTION"]))


def test_family_all_ties_and_open_count(inputs: c.Inputs, result: dict[str, object]) -> None:
    cursor = c.obj(result["CURSOR"])
    coarse = c.obj(cursor["COARSE_BOUND_PROJECTION"])
    before = {**c.obj(inputs[0]["RESOLVED_ROW_BOUNDS"]), **coarse}
    after = {**c.obj(result["RESOLVED_ROW_BOUNDS"]), **coarse}
    assert len(after) == 4844
    maximum = max(c.integer(v) for v in after.values())
    owners = sorted(p for p, v in after.items() if v == maximum)
    incumbent = c.integer(result["INCUMBENT"])
    assert result["FAMILY_BOUND_AFTER"] == maximum
    assert result["FAMILY_OWNER_IDS"] == owners
    assert result["EXACT_DELTA"] == max(c.integer(v) for v in before.values()) - maximum
    assert result["GAP_TO_INCUMBENT"] == maximum - incumbent
    assert result["STILL_OPEN_PROFILE_COUNT"] == sum(
        c.integer(v) > incumbent for v in after.values()
    )
    assert c.base.family(
        {"a": maximum, "b": maximum}, {"COARSE_BOUND_PROJECTION": {"c": maximum}}
    ) == (maximum, ["a", "b", "c"])


def test_statuses_caveats_and_scope_verbatim(inputs: c.Inputs, result: dict[str, object]) -> None:
    sealed, donor, _ = inputs
    inherited = c.obj(result["INHERITED_CAVEATS_AND_STATUS_VERBATIM"])
    for k, v in sealed.items():
        if k.startswith("INHERITED_"):
            assert inherited[k] == v
    assert inherited["PROVENANCE"] == sealed["PROVENANCE"]
    assert inherited["TASK_STATUS"] == sealed["TASK_STATUS"]
    assert result["DONOR_ORIGINAL_STATUS_VERBATIM"] == donor["DONOR_ORIGINAL_STATUS"]
    assert result["DONOR_PRE_JUDGE_STATUS_VERBATIM"] == donor["TASK_STATUS"]
    assert result["DONOR_FAMILY_EFFECT_SNAPSHOT_VERBATIM"] == donor["FAMILY_EFFECT"]
    assert c.obj(result["ENVELOPE"])["ALL_T_BONFERRONI5_ADOPTION"] == "OUT_OF_SCOPE_NOT_VERIFIED"
    assert result["GLOBAL_K20_OPTIMUM"] == "UNKNOWN"


@pytest.mark.parametrize("mutation", ["profile", "bound", "float", "other_row", "duplicate"])
def test_wrong_or_reapplied_update_rejected(inputs: c.Inputs, mutation: str) -> None:
    sealed, donor, _ = inputs
    rows = [(p, c.integer(v)) for p, v in c.obj(sealed["RESOLVED_ROW_BOUNDS"]).items()]
    pid = c.TARGET
    bound = c.integer(c.obj(donor["ENVELOPE"])["FULL_PROFILE_BOUND"])
    if mutation == "profile":
        pid = c.base.TARGET
    elif mutation == "bound":
        bound = c.integer(c.obj(donor["ENVELOPE"])["T264_TERM_BOUND"])
    elif mutation == "float":
        bound = cast(int, float(bound))
    else:
        rows = (
            [(p, bound if p == c.TARGET else v) for p, v in rows]
            if mutation == "duplicate"
            else [(p, v + (p == c.base.TARGET)) for p, v in rows]
        )
    with pytest.raises(AssertionError, match=r"wrong update|base projection"):
        c.compose(rows, c.obj(sealed["CURSOR"]), sealed, donor, pid, bound)


@pytest.mark.parametrize(
    "field", ["BOUND", "ID", "PROFILE_IDS", "COARSE_BOUND_PROJECTION", "PARTITION"]
)
def test_cursor_mutations_rejected(inputs: c.Inputs, field: str) -> None:
    sealed, donor, _ = inputs
    cursor = copy.deepcopy(c.obj(sealed["CURSOR"]))
    cursor[field] = None
    rows = [(p, c.integer(v)) for p, v in c.obj(sealed["RESOLVED_ROW_BOUNDS"]).items()]
    with pytest.raises(AssertionError, match="cursor"):
        c.compose(
            rows,
            cursor,
            sealed,
            donor,
            c.TARGET,
            c.integer(c.obj(donor["ENVELOPE"])["FULL_PROFILE_BOUND"]),
        )


@pytest.mark.parametrize(
    "mutation", ["profile", "bound", "cap", "s5", "first", "last", "rounding", "status", "all_t"]
)
def test_donor_mutations_rejected(inputs: c.Inputs, mutation: str) -> None:
    donor = copy.deepcopy(inputs[1])
    envelope = c.obj(donor["ENVELOPE"])
    if mutation == "profile":
        donor["PROFILE_ID"] = c.base.TARGET
    elif mutation == "bound":
        envelope["FULL_PROFILE_BOUND"] = envelope["T264_TERM_BOUND"]
    elif mutation == "cap":
        donor["TRIANGLE_CAP"] = c.integer(donor["TRIANGLE_CAP"]) - 1
    elif mutation == "s5":
        c.obj(donor["S5_PROOF"])["S5_CAP"] = 0
    elif mutation in ("first", "last"):
        c.items(envelope["ALL_T_TERMS"]).pop(0 if mutation == "first" else -1)
    elif mutation == "rounding":
        row = c.items(c.items(envelope["ALL_T_TERMS"])[-2])
        row[1] = c.integer(row[1]) - 1
    elif mutation == "status":
        c.obj(donor["DONOR_ORIGINAL_STATUS"])["JUDGE_MODE"] = "VERIFIED"
    else:
        envelope["ALL_T_BONFERRONI5_ADOPTION"] = "VERIFIED"
    with pytest.raises(AssertionError):
        c.validate_donor(donor)


def test_missing_donor_and_changed_hash_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(AssertionError, match="source-hash"):
        c.blob(c.DONOR_HEAD, c.DONOR_RESULT, "0" * 64)
    with pytest.raises(AssertionError, match="source-hash"):
        c.local_blob(c.BASE_SOURCE, "0" * 64)
    monkeypatch.setattr(c, "DONOR_HEAD", "0" * 40)
    with pytest.raises(subprocess.CalledProcessError):
        c.load_inputs()


def test_missing_report_rejected(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(c, "ROOT", tmp_path)
    with pytest.raises(FileNotFoundError):
        c.judges()


def test_duplicate_json_and_rows_rejected(inputs: c.Inputs) -> None:
    with pytest.raises(AssertionError, match="duplicate JSON"):
        c.decode(b'{"BOUND":1,"BOUND":2}')
    rows = [(p, c.integer(v)) for p, v in c.obj(inputs[0]["RESOLVED_ROW_BOUNDS"]).items()]
    for bad in (rows[:-1], [rows[0], *rows[:-1]]):
        with pytest.raises(AssertionError, match="row count"):
            c.validate_rows(bad, inputs[0])


def test_no_theorem_or_method_reexecution(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden() -> dict[str, object]:
        pytest.fail("accepted theorem must not be re-executed")

    monkeypatch.setattr(c.base.inherited, "theorem_a", forbidden)
    monkeypatch.setattr(c.base.inherited, "theorem_b", forbidden)
    assert c.compute_result()["MATHEMATICAL_THEOREMS_REEXECUTED"] == 0
    assert "lottolab.research.b649_min_s2_bonferroni5_target_cert_r1" not in c.sys.modules
