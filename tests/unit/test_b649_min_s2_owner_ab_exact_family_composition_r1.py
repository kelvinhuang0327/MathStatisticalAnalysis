"""Focused exact-source, complete-envelope and ledger mutation guards."""

from __future__ import annotations

import copy
import subprocess
import sys
from dataclasses import replace
from fractions import Fraction
from math import comb

import pytest

from lottolab.research import b649_min_s2_owner_ab_exact_family_composition_r1 as m


@pytest.fixture(scope="module")
def sources() -> m.Inputs:
    return m.load_inputs()


@pytest.fixture(scope="module")
def result(sources: m.Inputs) -> m.Document:
    return m.compute_result(sources)


def updates(sources: m.Inputs) -> list[tuple[str, int]]:
    return [
        (p, m.integer(a.result["NEW_FULL_PROFILE_BOUND"]))
        for p, a in zip(m.PROFILES, sources[1:], strict=True)
    ]


def test_exact_git_identities_and_original_acceptance(sources: m.Inputs) -> None:
    for a in sources:
        assert m.sha(m.render(a.result)) == a.pin.result_sha256
        assert m.sha(a.source) == a.pin.source_sha256
        assert a.acceptance["JUDGED_TREE"] == a.pin.tree
        assert a.acceptance["VERDICT"] == "VERIFIED_WITH_CAVEATS"
    assert (
        sources[1].acceptance["REPORT_DECLARED_SHA256"]
        != sources[1].acceptance["REPORT_COMMITTED_TEXT_SHA256"]
    )


@pytest.mark.parametrize("index", [1, 2])
def test_every_full_envelope_term_has_independent_rational_arithmetic(
    sources: m.Inputs, index: int
) -> None:
    a = sources[index]
    cert = m.adopt_certificate(a, sources[0].result)
    d = tuple(int(c) for c in m.string(cert["PROFILE_ID"]))
    g = [6 + v for v in d]
    w, j = sum(comb(v, 2) for v in g), sum(comb(v, 3) for v in g)
    expected: list[list[int]] = []
    for t in range(22, m.integer(cert["T_CAP"]) + 1):
        excess = Fraction(j - (max(g) - 2) * (w - 3 * t), 4)
        k4 = max(0, -(-excess.numerator // excess.denominator))
        contained = min(k4, sum(v * (4 + v) for v in d) // 3)
        floor = max(112, 448 * contained + 679 * (k4 - contained))
        third = 2800 * w + 11872 * (t - 22) - 30800
        rational = Fraction(372_228_640 - 63_838_600 + third) - Fraction(4 * floor, 7)
        expected.append(
            [t, -(-rational.numerator // rational.denominator), k4, contained, floor, third]
        )
    assert cert["ALL_T_TERMS"] == expected
    assert cert["FULL_PROFILE_BOUND"] == max(t[1] for t in expected)
    assert cert["TERM_COUNT"] == len(expected)


def test_ceiling_is_distinguished_from_floor() -> None:
    exact = Fraction(372_228_640 - 63_838_600) - Fraction(4, 7)
    assert m.rounded_bound(0, 1) == -(-exact.numerator // exact.denominator)
    assert m.rounded_bound(0, 1) != exact.numerator // exact.denominator


def test_complete_family_independent_scan_and_every_unchanged_row(
    sources: m.Inputs, result: m.Document
) -> None:
    before = m.obj(sources[0].result["RESOLVED_ROW_BOUNDS"])
    after = m.obj(result["RESOLVED_ROW_BOUNDS"])
    cursor = m.obj(result["CURSOR"])
    assert len(before) == len(after) == result["ROWS_TOTAL"]
    assert {p for p in before if before[p] != after[p]} == set(m.PROFILES)
    for p in before.keys() - set(m.PROFILES):
        assert after[p] == before[p]
    assert cursor == sources[0].result["CURSOR"]
    all_rows = {**after, **m.obj(cursor["COARSE_BOUND_PROJECTION"])}
    maximum = max(m.integer(v) for v in all_rows.values())
    incumbent = m.integer(sources[0].result["INCUMBENT"])
    assert result["FAMILY_BOUND_AFTER"] == maximum
    assert result["FAMILY_OWNER_IDS"] == sorted(p for p, b in all_rows.items() if b == maximum)
    assert result["GAP_TO_INCUMBENT"] == maximum - incumbent
    assert result["STILL_OPEN_PROFILE_COUNT"] == sum(
        m.integer(v) > incumbent for v in all_rows.values()
    )
    assert result["EXACT_FAMILY_DELTA"] == m.integer(result["FAMILY_BOUND_BEFORE"]) - maximum
    singles = m.obj(result["FAMILY_AFTER_SINGLE_UPDATE"])
    for pid, bound in updates(sources):
        independent_single = {**before, pid: bound, **m.obj(cursor["COARSE_BOUND_PROJECTION"])}
        assert singles[pid] == max(m.integer(v) for v in independent_single.values())


@pytest.mark.parametrize(
    "index,key",
    [(0, "G01_TO_G15_AT_SEAL"), (1, "A01_TO_A16_AT_SEAL"), (2, "B01_TO_B16_AT_SEAL")],
)
def test_original_at_seal_tables_preserved(
    sources: m.Inputs, result: m.Document, index: int, key: str
) -> None:
    # Compare literal immutable-source fields, independently of the filter.
    source = sources[index]
    saved = m.obj(m.obj(result["SOURCE_STATUS_VERBATIM"])[source.pin.tag])
    assert saved[key] == source.result[key]


def test_all_status_caveats_and_provenance_preserved(sources: m.Inputs, result: m.Document) -> None:
    assert (
        result["INHERITED_CAVEATS_AND_STATUS_VERBATIM"]
        == sources[0].result["INHERITED_CAVEATS_AND_STATUS_VERBATIM"]
    )
    assert result["BASE_PROVENANCE_VERBATIM"] == sources[0].result["PROVENANCE"]
    statuses = m.obj(result["SOURCE_STATUS_VERBATIM"])
    for a in sources:
        assert statuses[a.pin.tag] == m.status_snapshot(a.result)
        assert m.obj(m.obj(result["PROVENANCE"])[a.pin.tag])["ACCEPTANCE"] == a.acceptance
    assert m.obj(statuses["B"])["BOUND_SOURCE"] == sources[2].result["BOUND_SOURCE"]
    assert result["GLOBAL_K20_OPTIMUM"] == "UNKNOWN"
    assert (
        result["MATHEMATICAL_THEOREMS_REEXECUTED"]
        == result["SOLVER_CALLS"]
        == result["PORTFOLIOS_ENUMERATED"]
        == 0
    )


@pytest.mark.parametrize(
    "change", ["duplicate", "omitted", "wrong_profile", "wrong_bound", "noninteger"]
)
def test_bad_updates_rejected(sources: m.Inputs, change: str) -> None:
    rows, cursor = m.replay_base(sources[0].result)
    proposed = updates(sources)
    if change == "duplicate":
        proposed[1] = proposed[0]
    elif change == "omitted":
        proposed.pop()
    elif change == "wrong_profile":
        proposed[0] = (next(p for p in rows if p not in m.PROFILES), proposed[0][1])
    elif change == "wrong_bound":
        proposed[0] = (proposed[0][0], proposed[0][1] + 1)
    else:
        proposed[0] = (proposed[0][0], True)
    with pytest.raises(ValueError):
        m.compose(list(rows.items()), cursor, sources, proposed)


@pytest.mark.parametrize(
    "change", ["duplicate", "omitted", "modified", "wrong_profile", "noninteger"]
)
def test_bad_ledger_rows_rejected(sources: m.Inputs, change: str) -> None:
    frozen, cursor = m.replay_base(sources[0].result)
    rows = list(frozen.items())
    if change == "duplicate":
        rows[-1] = rows[0]
    elif change == "omitted":
        rows.pop()
    elif change == "modified":
        rows[0] = (rows[0][0], rows[0][1] + 1)
    elif change == "wrong_profile":
        rows[0] = ("0" * 20, rows[0][1])
    else:
        rows[0] = (rows[0][0], True)
    with pytest.raises(ValueError, match="ledger row"):
        m.compose(rows, cursor, sources, updates(sources))


@pytest.mark.parametrize(
    "field", ["BOUND", "PROFILE_IDS", "COARSE_BOUND_PROJECTION", "PARTITION", "STATUS"]
)
def test_any_cursor_modification_rejected(sources: m.Inputs, field: str) -> None:
    rows, cursor = m.replay_base(sources[0].result)
    changed = copy.deepcopy(cursor)
    if field == "BOUND":
        changed[field] = m.integer(changed[field]) - 1
    elif field == "PROFILE_IDS":
        m.items(changed[field]).pop()
    elif field == "COARSE_BOUND_PROJECTION":
        coarse = m.obj(changed[field])
        p = next(iter(coarse))
        coarse[p] = m.integer(coarse[p]) + 1
    elif field == "PARTITION":
        m.obj(changed[field]).clear()
    else:
        changed[field] = "MODIFIED"
    with pytest.raises(ValueError, match="cursor modification"):
        m.compose(list(rows.items()), changed, sources, updates(sources))


@pytest.mark.parametrize(
    "field,value",
    [
        ("PAIR_LINEARITY", False),
        ("PAIR_LINEARITY", 1),
        ("TRIPLES", 21),
        ("PAIRS", 28),
        ("TICKETS", True),
        ("LABELS_PER_TICKET", 5),
    ],
)
def test_weakened_mathematical_assumptions_rejected(field: str, value: object) -> None:
    model = dict(m.MODEL)
    model[field] = value
    with pytest.raises(ValueError, match="mathematical assumptions"):
        m.validate_model(m.PROFILES[0], model)


@pytest.mark.parametrize(
    "pid", [m.PROFILES[0][:-1], "0" * 20, "77777777777777777777", m.PROFILES[0][::-1]]
)
def test_wrong_profile_domain_rejected(pid: str) -> None:
    with pytest.raises(ValueError):
        m.profile(pid)


@pytest.mark.parametrize("index", [1, 2])
@pytest.mark.parametrize(
    "field",
    ["TARGET_PROFILE", "NEW_FULL_PROFILE_BOUND", "NEW_PROVEN_T_CAP", "PROOF", "GLOBAL_K20_OPTIMUM"],
)
def test_mutated_donor_rejected(sources: m.Inputs, index: int, field: str) -> None:
    a = sources[index]
    changed = copy.deepcopy(a.result)
    changed[field] = "MUTATED"
    with pytest.raises(ValueError, match="altered donor authority"):
        m.adopt_certificate(replace(a, result=changed), sources[0].result)


def test_source_and_judge_mismatches_rejected(sources: m.Inputs) -> None:
    with pytest.raises(ValueError, match="SHA256 mismatch"):
        m.checked_blob(m.A.head, m.A.result, "0" * 64)
    with pytest.raises(ValueError, match="immutable blob"):
        m.checked_blob(m.A.head, m.B.result, m.B.result_sha256)
    with pytest.raises(ValueError, match="altered donor source"):
        m.adopt_certificate(
            replace(sources[1], source=sources[1].source + b"\n"), sources[0].result
        )
    for pin, a in ((m.A, sources[1]), (m.B, sources[2])):
        with pytest.raises(ValueError, match="Judge binding differs"):
            m.acceptance(pin, a.message.replace(pin.tree, "0" * 40))
        with pytest.raises(ValueError, match="Judge binding differs"):
            m.acceptance(
                pin,
                a.message.replace(
                    "Fresh-context Judge: VERIFIED_WITH_CAVEATS",
                    "Fresh-context Judge: SELF_CHECK_ONLY",
                ),
            )


def test_duplicate_json_rows_rejected() -> None:
    with pytest.raises(ValueError, match="duplicate JSON key"):
        m.decode(b'{"RESOLVED_ROW_BOUNDS":{"profile":1,"profile":2}}')


def test_wrong_source_identity_rejected(sources: m.Inputs) -> None:
    changed = replace(sources[0], pin=replace(m.BASE, tree="0" * 40))
    with pytest.raises(ValueError, match="source identity mismatch"):
        m.compute_result((changed, sources[1], sources[2]))


def test_altered_base_rejected(sources: m.Inputs) -> None:
    changed = copy.deepcopy(sources[0].result)
    changed["INCUMBENT"] = m.integer(changed["INCUMBENT"]) + 1
    with pytest.raises(ValueError, match="altered Base authority"):
        m.replay_base(changed)


def test_exact_sealed_result_and_cli_replay(result: m.Document) -> None:
    path = m.result_path()
    assert path is not None and path.read_bytes() == m.render(result)
    completed = subprocess.run(
        [sys.executable, "-m", m.__name__, "--verify"],
        cwd=m.ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert "ortools" not in sys.modules
