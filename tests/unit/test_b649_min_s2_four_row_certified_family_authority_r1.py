"""Focused deterministic coverage of the fourth certificate's integration only."""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import replace
from unittest.mock import patch

import pytest

from lottolab.research import b649_min_s2_four_row_certified_family_authority_r1 as c

Snapshot = tuple[dict[str, c.Row], dict[str, object], dict[str, str]]


@pytest.fixture(scope="module")
def snapshot() -> Snapshot:
    return c.two.baseline()


@pytest.fixture(scope="module")
def pinned() -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    return c.authorities()


@pytest.fixture(scope="module")
def ledger(snapshot: Snapshot, pinned: tuple[dict[str, object], ...]) -> dict[str, c.Row]:
    with patch.object(c.two, "baseline", return_value=snapshot):
        return c.three_row_ledger(pinned[0])[1]


@pytest.fixture(scope="module")
def derived(snapshot: Snapshot) -> Iterator[dict[str, object]]:
    with patch.object(c.two, "baseline", return_value=snapshot):
        yield c.compute_result()


def test_exact_immutable_sibling_authorities(pinned: tuple[dict[str, object], ...]) -> None:
    first, donor, identities = pinned
    assert first["FAMILY_BOUND_AFTER"] == 313401464
    assert donor["FULL_PROFILE_UPPER_BOUND"] == 313392308
    assert c.object_row(identities["CERTIFICATE_C_IDENTITY"])["JUDGE_STATUS"] == (
        "VERIFIED_WITH_CAVEATS"
    )
    assert c.object_row(identities["CERTIFICATE_D_IDENTITY"])["JUDGE_STATUS"] == "VERIFIED"
    assert not (c.ROOT / f"src/lottolab/research/{c.D_MODULE}.py").exists()


@pytest.mark.parametrize(
    "name",
    [
        "BASE_TREE",
        "DONOR_TREE",
        "C_SOURCE_SHA256",
        "D_SOURCE_SHA256",
        "DONOR_RESULT_SHA256",
        "D_TEST_SHA256",
    ],
)
def test_wrong_authority_rejected(name: str) -> None:
    with (
        patch.object(c, name, "0" * (40 if name.endswith("TREE") else 64)),
        pytest.raises(AssertionError, match=r"tree|digest"),
    ):
        c.authorities()


def test_complete_envelope_keeps_lower_t(
    ledger: dict[str, c.Row], pinned: tuple[dict[str, object], ...]
) -> None:
    before, after = c.envelope(ledger[c.D_PROFILE], pinned[1])
    assert before[:-1] == after[:-1] and len(after) == 243
    assert after[-1] == (264, 313388344, 489, 201, 308560, 5174624)
    assert max(after, key=lambda t: t[1]) == (263, 313392308, 482, 201, 280847, 5162752)
    assert max(t[1] for t in after) > after[-1][1]


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("FULL_PROFILE_UPPER_BOUND", 313388344),
        ("T264_S4_LOWER_BOUND", 308559),
        ("LOWER_T_TERMS_SHA256", "0" * 64),
        ("LOWER_T_TERMS_UNCHANGED", False),
        ("CERTIFIED_T_CAP", 263),
    ],
)
def test_wrong_envelope_rejected(
    ledger: dict[str, c.Row], pinned: tuple[dict[str, object], ...], key: str, value: object
) -> None:
    mutated = {**pinned[1], key: value}
    with pytest.raises(AssertionError, match=r"binding|envelope"):
        c.apply_fourth(ledger, mutated)


def test_only_bound_and_source_change(
    ledger: dict[str, c.Row], pinned: tuple[dict[str, object], ...]
) -> None:
    frozen = c.two.full_digest(ledger)
    after = c.apply_fourth(ledger, pinned[1])
    assert c.two.full_digest(ledger) == frozen
    assert [p for p in ledger if ledger[p] != after[p]] == [c.D_PROFILE]
    assert (
        replace(
            after[c.D_PROFILE], bound=ledger[c.D_PROFILE].bound, source=ledger[c.D_PROFILE].source
        )
        == ledger[c.D_PROFILE]
    )
    assert after[c.D_PROFILE].cap == 264 and after[c.D_PROFILE].s4_base == 112
    for pid in (c.two.A_PROFILE, c.two.B_PROFILE, c.three.C_PROFILE):
        assert after[pid] == ledger[pid]


def test_all_rows_and_cursor_independent_recount(
    ledger: dict[str, c.Row], pinned: tuple[dict[str, object], ...], derived: dict[str, object]
) -> None:
    after = c.apply_fourth(ledger, pinned[1])
    terms = {p: row.bound for p, row in after.items()}
    terms[c.chase.prior.CURSOR_ID] = c.chase.prior.CURSOR_BOUND
    best = max(terms.values())
    owners = sorted(p for p, bound in terms.items() if bound == best)
    assert len(after) == 4647 and best == 313401180
    assert owners == ["66665555554422000000"] == derived["CURRENT_FAMILY_OWNER"]
    assert best == derived["FAMILY_BOUND_AFTER"]
    assert max(row.bound for row in ledger.values()) - best == 284 == derived["EXACT_DELTA"]
    assert best - c.two.INCUMBENT == 137292 == derived["GAP_TO_INCUMBENT"]
    assert derived["EXPECTED_VALUES_MATCH"] is True
    assert derived["CERTIFICATES_COMPOSED"] == 4
    assert derived["ROWS_CHANGED_FROM_THREE_ROW"] == 1
    assert len(c.rows(derived["ROWS_CHANGED_VS_ORIGINAL"])) == 4


def test_prior_judge_caveats_verbatim(pinned: tuple[dict[str, object], ...]) -> None:
    prior = c.prior_judge(pinned[0])
    report = (c.ROOT / c.JUDGE_ARCHIVE).read_text()
    assert c.text(prior["CAVEATS_TEXT"]) in report
    assert prior["JUDGED_TREE"] == c.BASE_TREE
    assert prior["HEAD_AT_REVIEW"] == c.COMMON_PARENT
    assert prior["PRIOR_JUDGE_REVIEWED_FOUR_ROW_TREE"] is False
    with (
        patch.object(c, "JUDGE_SHA256", "0" * 64),
        pytest.raises(AssertionError, match="archive changed"),
    ):
        c.prior_judge(pinned[0])
    mutated = {**pinned[0], "CERTIFICATE_B_CAVEATS_SOURCE": "CURRENT_JUDGE"}
    with pytest.raises(AssertionError, match="caveats or provenance"):
        c.prior_judge(mutated)


def test_exact_result_and_no_proof_reexecution(
    snapshot: Snapshot, derived: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    assert c.RESULT_PATH.read_bytes() == c.two.render(derived)
    assert json.loads(c.RESULT_PATH.read_bytes())["GLOBAL_K20_OPTIMUM"] == "UNKNOWN"

    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("integration invoked a proof or search entrypoint")

    monkeypatch.setattr(c.two, "baseline", lambda: snapshot)
    for name in ("compute_result", "core_zero_theorem", "witness"):
        monkeypatch.setattr(c.three, name, forbidden)
    monkeypatch.setattr(c.chase, "chase", forbidden)
    monkeypatch.setattr(c.chase, "refine", forbidden)
    result = c.compute_result()
    assert result == derived
    assert result["SOLVER_CALLS"] == 0
    assert (
        result["RUN1_MUTATED"] == result["HEAVY_SOLVER_STARTED"] == result["REMOTE_WRITE"] == "NO"
    )
