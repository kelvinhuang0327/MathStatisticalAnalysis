"""Focused exact composition, complete-envelope and adversarial input checks."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from fractions import Fraction
from pathlib import Path

import pytest

from lottolab.research import b649_min_s2_t248_t228_exact_family_composition_r1 as c


@pytest.fixture(scope="module")
def inputs() -> c.Inputs:
    return c.load_inputs()


def updates(inputs: c.Inputs) -> list[tuple[str, int, int]]:
    certs = c.certificates(inputs)
    return [
        (p, c.integer(certs[p]["T_CAP"]), c.integer(certs[p]["FULL_PROFILE_BOUND"]))
        for p in c.PROFILES
    ]


def test_exact_immutable_sources_and_fresh_judges(inputs: c.Inputs) -> None:
    c.validate_inputs(inputs)
    for a in inputs:
        assert c.git("rev-parse", f"{a.pin.head}^{{tree}}").decode().strip() == a.pin.tree
        assert c.sha(c.git("show", f"{a.pin.head}:{a.pin.result}")) == a.pin.result_sha256
        assert a.acceptance["VERDICT"] == "VERIFIED_WITH_CAVEATS"
        assert a.acceptance["JUDGED_TREE"] == a.pin.tree
        assert a.acceptance["JUDGE_MODE"] == "FRESH_CONTEXT"


@pytest.mark.parametrize(
    "pid,cap,constant,bound,count",
    [
        (c.PROFILES[0], 248, 5954, 313242512, 227),
        (c.PROFILES[1], 228, 5956, 313063660, 207),
    ],
)
def test_complete_old_new_rational_envelopes(
    pid: str,
    cap: int,
    constant: int,
    bound: int,
    count: int,
) -> None:
    old, new = c.envelope(pid, 265), c.envelope(pid, cap, constant)
    assert len(old) == 244 and len(new) == count and old[:count] == new
    assert max(t[1] for t in old) == 313395060
    assert max(t[1] for t in new) == bound
    for t, value, q, contained, s4, s3 in old:
        rational_q = max(Fraction(0), Fraction(30 * t - constant, 4))
        assert q == -(-rational_q.numerator // rational_q.denominator)
        assert contained == min(q, 198)
        assert s4 == max(112, 448 * contained + 679 * (q - contained))
        exact = Fraction(372228640 - 63838600 + s3) - Fraction(4, 7) * s4
        assert value == -(-exact.numerator // exact.denominator)
    assert new[-1][0] == cap


def test_both_rows_and_single_row_family_arithmetic(inputs: c.Inputs) -> None:
    before, cursor = c.replay_base(inputs[0].result)
    after = c.compose(list(before.items()), cursor, inputs, updates(inputs))
    assert len(before) == len(after) == 4647
    assert {p for p in before if before[p] != after[p]} == set(c.PROFILES)
    assert len([p for p in before if p not in c.PROFILES]) == 4645
    for p in before:
        if p not in c.PROFILES:
            assert after[p] == before[p]
    assert len(c.obj(cursor["COARSE_BOUND_PROJECTION"])) == 197
    for p in c.PROFILES:
        assert c.family({**before, p: after[p]}, cursor)[0] == 313395060
    all_rows = {
        **after,
        **{p: c.integer(b) for p, b in c.obj(cursor["COARSE_BOUND_PROJECTION"]).items()},
    }
    maximum = max(all_rows.values())
    owners = sorted(p for p, b in all_rows.items() if b == maximum)
    assert c.family(after, cursor) == (maximum, owners)
    assert maximum == 313394776
    assert owners == ["66555555555431100000"]
    assert 313395060 - maximum == 284
    assert maximum - c.integer(inputs[0].result["INCUMBENT"]) == 130888
    assert sum(b > 313263888 for b in all_rows.values()) == 1562


def test_exact_result_and_all_inherited_dispositions(inputs: c.Inputs) -> None:
    result = c.compute_result(inputs)
    assert (c.ROOT / c.RESULT).read_bytes() == c.render(result)
    provenance = c.obj(result["PROVENANCE"])
    for a in inputs:
        preserved = c.obj(provenance[a.pin.tag])
        assert c.render(preserved["ORIGINAL_RESULT_VERBATIM"]) == c.render(a.result)
        assert preserved["ACCEPTANCE"] == a.acceptance
    assert c.obj(inputs[1].result["ENUMERATION"])["LEGACY_DIGEST_MATCH"] == "NOT_VERIFIED"
    assert inputs[2].result["PRIOR_ART_ORIGINAL_STATUS"] == (
        "PROVEN_IMPROVEMENT; PENDING_ONE_FRESH_FOCUSED_SCIENTIFIC_REVIEW"
    )
    assert inputs[2].result["PRIOR_ART_ORIGINAL_PROJECTION_STATUS"] == (
        "CONDITIONAL_PROJECTION; NOT_CANONICAL_ADOPTION"
    )
    assert result["CURSOR"] == inputs[0].result["CURSOR"]
    assert result["GLOBAL_K20_OPTIMUM"] == result["LEGAL_ATTAINMENT"] == "UNKNOWN"
    assert result["MATHEMATICAL_THEOREMS_REEXECUTED"] == result["GRAPHS_ENUMERATED"] == 0


def test_portable_pinned_report(inputs: c.Inputs, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(c, "T228_REPORT", Path(c.ROOT / ".task-data/absent-donor-report"))
    assert c.load_report(c.T228, inputs[2].message) == inputs[2].acceptance["REPORT_VERBATIM"]


@pytest.mark.parametrize(
    "pid,cap,constant",
    [
        (c.PROFILES[0], 248, 5956),
        (c.PROFILES[1], 228, 5954),
        ("66555555555431100000", 248, 5954),
        (c.PROFILES[0], 228, 5954),
        (c.PROFILES[1], 248, 5956),
    ],
)
def test_reject_wrong_profile_cap_or_swapped_constants(pid: str, cap: int, constant: int) -> None:
    with pytest.raises(ValueError):
        c.envelope(pid, cap, constant)


@pytest.mark.parametrize("bad", ["head", "tree", "result", "source", "judge"])
def test_reject_incorrect_source_identity(inputs: c.Inputs, bad: str) -> None:
    donor = inputs[1]
    if bad == "judge":
        altered = {**donor.acceptance, "JUDGED_TREE": c.T228.tree}
        donor = replace(donor, acceptance=altered)
    elif bad == "source":
        donor = replace(donor, source=donor.source + b"\n")
    elif bad == "result":
        donor = replace(donor, result={**donor.result, "NEW_PROVEN_T_CAP": 228})
    else:
        donor = replace(donor, pin=replace(donor.pin, **{bad: "0" * 40}))
    with pytest.raises(ValueError):
        c.validate_inputs((inputs[0], donor, inputs[2]))


@pytest.mark.parametrize("bad", ["missing", "duplicate", "changed", "cursor", "coverage"])
def test_reject_row_or_cursor_mutation(inputs: c.Inputs, bad: str) -> None:
    before, cursor = c.replay_base(inputs[0].result)
    rows = list(before.items())
    cursor = deepcopy(cursor)
    if bad == "missing":
        rows.pop()
    elif bad == "duplicate":
        rows.append(rows[0])
    elif bad == "changed":
        rows[0] = rows[0][0], rows[0][1] - 1
    elif bad == "cursor":
        cursor["BOUND"] = 313394583
    else:
        c.items(cursor["PROFILE_IDS"]).pop()
    with pytest.raises(ValueError):
        c.compose(rows, cursor, inputs, updates(inputs))


@pytest.mark.parametrize("bad", ["missing", "duplicate", "profile", "cap", "bound", "swapped"])
def test_reject_missing_duplicate_or_misplaced_updates(inputs: c.Inputs, bad: str) -> None:
    before, cursor = c.replay_base(inputs[0].result)
    proposed = updates(inputs)
    pid, cap, bound = proposed[0]
    if bad == "missing":
        proposed.pop()
    elif bad == "duplicate":
        proposed[1] = proposed[0]
    elif bad == "profile":
        proposed[0] = "66555555555431100000", cap, bound
    elif bad == "cap":
        proposed[0] = pid, cap - 1, bound
    elif bad == "bound":
        proposed[0] = pid, cap, bound - 1
    else:
        proposed[0] = pid, cap, proposed[1][2]
    with pytest.raises(ValueError):
        c.compose(list(before.items()), cursor, inputs, proposed)
