"""Exact three-owner composition, strongest-source selection and rejection gates."""

from __future__ import annotations

import copy
import subprocess
from dataclasses import replace
from fractions import Fraction
from pathlib import Path

import pytest

from lottolab.research import b649_min_s2_three_max_owners_exact_authority_r1 as m


@pytest.fixture(scope="module")
def inputs() -> m.Inputs:
    return m.load_inputs()


@pytest.fixture(scope="module")
def result(inputs: m.Inputs) -> m.Document:
    return m.compute_result(inputs)


def updates() -> list[tuple[str, int, int]]:
    return list(zip(m.PROFILES, m.CAPS, (313072532, 313054608, 313008408), strict=True))


def compose(inputs: m.Inputs, changes: list[tuple[str, int, int]]) -> dict[str, int]:
    base = inputs[0].result
    rows = [(p, m.integer(b)) for p, b in m.obj(base["RESOLVED_ROW_BOUNDS"]).items()]
    return m.compose(rows, m.obj(base["CURSOR"]), inputs, changes)


def test_complete_family_and_all_preserved_rows(inputs: m.Inputs, result: m.Document) -> None:
    before = m.obj(inputs[0].result["RESOLVED_ROW_BOUNDS"])
    after = m.obj(result["RESOLVED_ROW_BOUNDS"])
    assert len(after) == len(before) == 4647
    assert {p for p in before if before[p] != after[p]} == set(m.PROFILES)
    assert {p: b for p, b in before.items() if p not in m.PROFILES} == {
        p: b for p, b in after.items() if p not in m.PROFILES
    }
    assert result["CURSOR"] == inputs[0].result["CURSOR"]
    cursor = m.obj(result["CURSOR"])
    assert (
        len(m.obj(cursor["COARSE_BOUND_PROJECTION"])) == len(m.items(cursor["PROFILE_IDS"])) == 197
    )
    assert result["FAMILY_BOUND_BEFORE"] == 313395164
    assert result["FAMILY_BOUND_AFTER"] == 313395060
    assert result["EXACT_FAMILY_DELTA"] == 104
    assert result["FAMILY_OWNER_IDS"] == ["66655555555332000000", "66655555555421100000"]
    assert result["GAP_TO_INCUMBENT"] == 131172
    assert result["STILL_OPEN_PROFILE_COUNT_BEFORE"] == 1567
    assert result["STILL_OPEN_PROFILE_COUNT"] == 1564
    assert result["STRICT_GAIN_EXCLUDED_PROFILE_COUNT"] == 3280
    assert result["NEWLY_STRICT_GAIN_EXCLUDED_PROFILE_IDS"] == sorted(m.PROFILES)
    assert set(m.obj(result["FAMILY_AFTER_SINGLE_UPDATE"]).values()) == {313395164}


@pytest.mark.parametrize("pid,cap,bound", updates())
def test_complete_exact_profile_envelopes(
    pid: str, cap: int, bound: int, result: m.Document
) -> None:
    certificate = m.obj(m.obj(result["PROFILE_CERTIFICATES"])[pid])
    terms = [m.items(t) for t in m.items(certificate["ALL_T_TERMS"])]
    assert len(terms) == certificate["TERM_COUNT"] == cap - 21
    assert [t[0] for t in terms] == list(range(22, cap + 1))
    assert max(m.integer(t[1]) for t in terms) == bound
    assert certificate["MAXIMIZING_TERMS"] == [terms[-1]]
    for t in terms:
        exact = Fraction(372228640 - 63838600 + m.integer(t[5])) - Fraction(4 * m.integer(t[4]), 7)
        assert m.integer(t[1]) == -(-exact.numerator // exact.denominator)
    assert m.envelope(pid, 266)[: len(terms)] == [tuple(m.integer(v) for v in t) for t in terms]
    assert certificate["S5_ADOPTED"] is False
    assert certificate["ATTAINMENT"] == "UNKNOWN"


def test_exact_sources_and_external_review_stay_distinct(
    inputs: m.Inputs, result: m.Document
) -> None:
    assert tuple(a.pin for a in inputs) == (m.BASE, m.T223, m.R2)
    assert inputs[2].result["TASK_STATUS"] == "COMPLETE_PROVEN; PENDING_EXTERNAL_FOCUSED_REVIEW"
    assert (
        inputs[2].result["NEW_CERTIFICATE_ACCEPTANCE"]
        == "CANDIDATE_FOR_ONE_FRESH_FOCUSED_SCIENTIFIC_REVIEW"
    )
    assert inputs[2].acceptance["VERDICT"] == "VERIFIED_WITH_CAVEATS"
    assert inputs[2].acceptance["JUDGED_TREE"] == m.R2.tree != m.PR_TREE
    assert m.obj(result["R2_CURRENT_PR"])["TREE_IDENTICAL"] is False
    for key, original in (
        ("BASE_INHERITED_CAVEATS_AND_STATUS_VERBATIM", "INHERITED_CAVEATS_AND_STATUS_VERBATIM"),
        ("BASE_SOURCE_STATUS_VERBATIM", "SOURCE_STATUS_VERBATIM"),
        ("BASE_PROVENANCE_VERBATIM", "PROVENANCE"),
    ):
        assert result[key] == inputs[0].result[original]
    caveat = m.obj(result["OWNER_A_HISTORICAL_REPORT_DIGEST_CAVEAT"])
    assert caveat["REPORT_DECLARED_SHA256"] != caveat["REPORT_COMMITTED_TEXT_SHA256"]
    strongest = m.obj(m.obj(result["PROFILE_CERTIFICATES"])[m.PROFILES[2]])
    assert strongest["T_CAP"] == 223 < m.integer(strongest["R2_CAP_RETAINED_AS_HISTORY"])
    assert (
        strongest["FULL_PROFILE_BOUND"]
        == 313008408
        < m.integer(strongest["R2_BOUND_RETAINED_AS_HISTORY"])
    )
    assert strongest["SOURCE_HEAD"] == m.T223.head
    assert result["GLOBAL_K20_OPTIMUM"] == "UNKNOWN"
    assert result["SOLVER_CALLS"] == result["MATHEMATICAL_THEOREMS_REEXECUTED"] == 0


@pytest.mark.parametrize("index", range(3))
def test_wrong_source_hash_rejected(index: int, inputs: m.Inputs) -> None:
    changed = list(inputs)
    changed[index] = replace(changed[index], source=changed[index].source + b"\n")
    with pytest.raises(ValueError, match="source SHA256"):
        m.certificates((changed[0], changed[1], changed[2]))


def test_wrong_immutable_blob_hash_rejected() -> None:
    with pytest.raises(ValueError, match="SHA256 mismatch"):
        m.checked_blob(m.R2.head, m.R2.source, "0" * 64)


def test_wrong_review_hash_rejected(inputs: m.Inputs) -> None:
    with pytest.raises(ValueError, match="review SHA256"):
        m.review_record(m.string(inputs[2].acceptance["REPORT_VERBATIM"]).encode() + b"\n")


@pytest.mark.parametrize("index", range(3))
def test_wrong_t_cap_rejected(index: int, inputs: m.Inputs) -> None:
    changed = updates()
    p, c, b = changed[index]
    changed[index] = p, c + 1, b
    with pytest.raises(ValueError, match="T cap"):
        compose(inputs, changed)


def test_weaker_t227_certificate_substitution_rejected(inputs: m.Inputs) -> None:
    changed = updates()
    changed[2] = m.PROFILES[2], 227, 313045840
    with pytest.raises(ValueError, match="weaker substitution"):
        compose(inputs, changed)


@pytest.mark.parametrize("index", range(3))
def test_wrong_full_profile_bound_rejected(index: int, inputs: m.Inputs) -> None:
    changed = updates()
    p, c, b = changed[index]
    changed[index] = p, c, b - 1
    with pytest.raises(ValueError, match="full-profile bound"):
        compose(inputs, changed)


@pytest.mark.parametrize("kind", ("duplicate", "missing", "neighbor"))
def test_invalid_update_set_rejected(kind: str, inputs: m.Inputs) -> None:
    changed = updates()
    if kind == "duplicate":
        changed[2] = changed[0]
    elif kind == "missing":
        changed.pop()
    else:
        changed[2] = "66655555555332000000", 223, 313008408
    with pytest.raises(ValueError, match="wrong-profile update"):
        compose(inputs, changed)


@pytest.mark.parametrize("kind", ("missing", "duplicate", "altered"))
def test_invalid_ledger_rejected(kind: str, inputs: m.Inputs) -> None:
    base = inputs[0].result
    rows = [(p, m.integer(b)) for p, b in m.obj(base["RESOLVED_ROW_BOUNDS"]).items()]
    if kind == "missing":
        rows.pop()
    elif kind == "duplicate":
        rows[-1] = rows[0]
    else:
        p, b = rows[-1]
        rows[-1] = p, b - 1
    with pytest.raises(ValueError, match="ledger row"):
        m.compose(rows, m.obj(base["CURSOR"]), inputs, updates())


@pytest.mark.parametrize("kind", ("bound", "identity", "coverage"))
def test_altered_cursor_rejected(kind: str, inputs: m.Inputs) -> None:
    base = inputs[0].result
    cursor = copy.deepcopy(m.obj(base["CURSOR"]))
    if kind == "bound":
        coarse = m.obj(cursor["COARSE_BOUND_PROJECTION"])
        pid = next(iter(coarse))
        coarse[pid] = m.integer(coarse[pid]) - 1
    elif kind == "identity":
        cursor["ID"] = "wrong-cursor"
    else:
        m.items(cursor["PROFILE_IDS"]).pop()
    rows = [(p, m.integer(b)) for p, b in m.obj(base["RESOLVED_ROW_BOUNDS"]).items()]
    with pytest.raises(ValueError, match="altered cursor"):
        m.compose(rows, cursor, inputs, updates())


def test_altered_base_authority_rejected(inputs: m.Inputs) -> None:
    base = copy.deepcopy(inputs[0].result)
    m.obj(base["RESOLVED_ROW_BOUNDS"]).pop(m.PROFILES[0])
    with pytest.raises(ValueError, match="altered Base authority"):
        m.replay_base(base)


def test_wrong_pin_rejected(inputs: m.Inputs) -> None:
    with pytest.raises(ValueError, match="source identity"):
        m.certificates((replace(inputs[0], pin=m.R2), inputs[1], inputs[2]))


def test_invalid_result_identity_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    directory = tmp_path / m.DIRECTORY
    directory.mkdir(parents=True)
    (directory / f"{m.RESULT_PREFIX}{'0' * 64}.json").write_bytes(b"{}\n")
    monkeypatch.setattr(m, "ROOT", tmp_path)
    with pytest.raises(ValueError, match="invalid result identity"):
        m.result_path()


@pytest.mark.parametrize(
    "pid,cap", (("66655555555332000000", 223), (m.PROFILES[0], True), (m.PROFILES[0], 267))
)
def test_exact_envelope_domain_rejected(pid: str, cap: int) -> None:
    with pytest.raises(ValueError, match="exact profile/cap"):
        m.envelope(pid, cap)


def test_sealed_result_and_real_cli(result: m.Document) -> None:
    path = m.result_path()
    assert path is not None
    assert path.read_bytes() == m.render(result)
    child = subprocess.run(
        [__import__("sys").executable, "-B", "-m", m.__name__, "--verify"],
        cwd=m.ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert child.returncode == 0, child.stderr
    assert '"FAMILY_BOUND_AFTER": 313395060' in child.stdout
