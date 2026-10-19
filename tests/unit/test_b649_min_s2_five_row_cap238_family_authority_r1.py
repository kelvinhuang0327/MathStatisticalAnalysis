"""Focused checks of the fifth certificate composition and complete family recount."""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import replace
from unittest.mock import patch

import pytest

from lottolab.research import b649_min_s2_five_row_cap238_family_authority_r1 as c


@pytest.fixture(scope="module")
def pinned() -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    return c.authorities()


@pytest.fixture(scope="module")
def ledger(pinned: tuple[dict[str, object], ...]) -> dict[str, c.Row]:
    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("integration executed a proof/search entrypoint")

    with (
        patch.object(c.chase.split, "degree_configurations", forbidden),
        patch.object(c.chase.split, "split_certificate", forbidden),
        patch.object(c.chase, "chase", forbidden),
        patch.object(c.chase, "refine", forbidden),
        patch.object(c.four.three, "core_zero_theorem", forbidden),
        patch.object(c.four.three, "witness", forbidden),
        patch.object(c.four.three, "compute_result", forbidden),
    ):
        return c.four_row_ledger(pinned[0])


@pytest.fixture(scope="module")
def derived(ledger: dict[str, c.Row]) -> Iterator[dict[str, object]]:
    # Only reuse the ledger that the real pinned replay above already verified.
    with patch.object(c, "four_row_ledger", return_value=ledger):
        yield c.compute_result()


def test_actual_donor_bytes_and_full_t_scope(pinned: tuple[dict[str, object], ...]) -> None:
    prior, donor, identity = pinned
    assert prior["CERTIFICATES_COMPOSED"] == 4
    assert donor["TRIANGLE_DOMAIN"] == [22, 238] and donor["TERM_COUNT"] == 217
    assert donor["S4_BASE"] == 112 and donor["A_MAX"] == 199
    assert donor["ARGMAX_TERM"] == [238, 313159012, 296, 199, 155015, 4857552]
    assert identity["JUDGE_STATUS"] == "VERIFIED"
    assert (
        c.sha256((c.ROOT / c.ARCHIVE / "d6-cap238-result.json").read_bytes())
        == c.DONOR_RESULT_SHA256
    )
    assert not (c.ROOT / f"src/lottolab/research/{c.DONOR_MODULE}.py").exists()


@pytest.mark.parametrize(
    "name",
    [
        "BASE_TREE",
        "DONOR_TREE",
        "COMMON_ANCESTOR",
        "THEOREM_BLOB",
        "BASE_RESULT_SHA256",
        "DONOR_RESULT_SHA256",
        "DONOR_SOURCE_SHA256",
        "DONOR_TEST_SHA256",
        "FOUR_JUDGE_SHA256",
    ],
)
def test_wrong_authority_rejected(name: str) -> None:
    with (
        patch.object(c, name, "0" * (64 if name.endswith("SHA256") else 40)),
        pytest.raises(AssertionError, match=r"tree|ancestry|theorem|digest"),
    ):
        c.authorities()


def test_four_row_seal(ledger: dict[str, c.Row], pinned: tuple[dict[str, object], ...]) -> None:
    assert len(ledger) == 4647
    assert c.two.full_digest(ledger) == pinned[0]["FULL_ROWS_SHA256_AFTER"]
    assert (ledger[c.TARGET_PROFILE].bound, ledger[c.TARGET_PROFILE].cap) == (313401180, 265)


def test_exactly_one_profile_changes(
    ledger: dict[str, c.Row], pinned: tuple[dict[str, object], ...]
) -> None:
    digest = c.two.full_digest(ledger)
    after = c.apply_fifth(ledger, pinned[1])
    assert c.two.full_digest(ledger) == digest
    assert [p for p in ledger if ledger[p] != after[p]] == [c.TARGET_PROFILE]
    assert (after[c.TARGET_PROFILE].bound, after[c.TARGET_PROFILE].cap) == (313159012, 238)
    assert after[c.TARGET_PROFILE].s4_base == 112
    assert (
        replace(
            after[c.TARGET_PROFILE],
            bound=ledger[c.TARGET_PROFILE].bound,
            cap=ledger[c.TARGET_PROFILE].cap,
            source=ledger[c.TARGET_PROFILE].source,
        )
        == (ledger[c.TARGET_PROFILE])
    )


def test_duplicate_application_rejected(
    ledger: dict[str, c.Row], pinned: tuple[dict[str, object], ...]
) -> None:
    once = c.apply_fifth(ledger, pinned[1])
    with pytest.raises(AssertionError, match="already tightened"):
        c.apply_fifth(once, pinned[1])
    for cap in (237, 238):
        stronger = {**ledger, c.TARGET_PROFILE: replace(ledger[c.TARGET_PROFILE], cap=cap)}
        with pytest.raises(AssertionError, match="already tightened"):
            c.apply_fifth(stronger, pinned[1])


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("TARGET_PROFILE", "66665555555421000000"),
        ("PROVEN_NEW_CAP", 239),
        ("NEW_PROFILE_BOUND", 313159011),
        ("S4_BASE", 111),
    ],
)
def test_wrong_scope_or_weight_rejected(
    ledger: dict[str, c.Row], pinned: tuple[dict[str, object], ...], key: str, value: object
) -> None:
    with pytest.raises(AssertionError, match=r"target|bound/cap/S4"):
        c.apply_fifth(ledger, {**pinned[1], key: value})


def test_full_family_independent_recount(
    ledger: dict[str, c.Row], pinned: tuple[dict[str, object], ...], derived: dict[str, object]
) -> None:
    after = c.apply_fifth(ledger, pinned[1])
    bounds = {p: row.bound for p, row in after.items()}
    cursor = c.object_row(pinned[0]["CURSOR"])
    bounds[c.text(cursor["ID"])] = c.integer(cursor["BOUND"])
    best = max(bounds.values())
    owners = sorted(p for p, bound in bounds.items() if bound == best)
    assert best == derived["FAMILY_BOUND_AFTER"]
    assert best > 313159012 and best >= 313394584
    assert owners == derived["NEW_FAMILY_OWNER_IDS"]
    assert 313401180 - best == derived["EXACT_FAMILY_DELTA"]
    assert best - 313263888 == derived["NEW_GAP_TO_INCUMBENT"]
    above = sorted(p for p, row in after.items() if row.bound > 313263888)
    assert len(above) == 1378 == derived["RESOLVED_ROWS_ABOVE_INCUMBENT"]
    assert above == derived["RESOLVED_ROW_IDS_ABOVE_INCUMBENT"]
    assert {p: row.bound for p, row in after.items()} == derived["RESOLVED_ROW_BOUNDS"]


def test_cursor_is_load_bearing(ledger: dict[str, c.Row]) -> None:
    below = {p: replace(row, bound=313263888) for p, row in ledger.items()}
    best, owners, _ = c.four.three.family(below)
    assert (best, owners) == (313394584, ["66544333333333332222"])


def test_original_authority_caveats_and_rows_preserved(
    ledger: dict[str, c.Row], pinned: tuple[dict[str, object], ...], derived: dict[str, object]
) -> None:
    prior = c.object_row(
        json.loads(c.two.blob(c.BASE_HEAD, c.BASE_RESULT_PATH, c.BASE_RESULT_SHA256))
    )
    assert derived["PRESERVED_FOUR_ROW_AUTHORITY"] == prior == pinned[0]
    assert derived["AUTHORITY_JUDGE_STATUS"] == "VERIFIED_WITH_CAVEATS"
    assert derived["PRIOR_JUDGE_CAVEATS"] == "PRESERVED"
    report = (c.ROOT / c.ARCHIVE / "four-row-fresh-judge.md").read_bytes()
    judge = c.object_row(derived["PRIOR_FOUR_ROW_JUDGE"])
    assert c.sha256(report) == c.FOUR_JUDGE_SHA256 == judge["REPORT_SHA256"]
    assert c.text(judge["CAVEATS_TEXT"]) in report.decode()
    assert judge["VERDICT"] == "VERIFIED_WITH_CAVEATS"
    assert judge["PRIOR_JUDGE_REVIEWED_FIVE_ROW_TREE"] is False
    assert derived["CURSOR"] == prior["CURSOR"]
    assert (
        derived["CURSOR_PARTITION_AUTHORITY"] == c.chase.pinned_authority()["INHERITED_PARTITION"]
    )
    after = c.apply_fifth(ledger, pinned[1])
    ids = c.rows(derived["CERTIFICATE_PROFILE_IDS"])
    assert len(ids) == len(set(c.text(p) for p in ids)) == 5
    for p in ids[:-1]:
        assert after[c.text(p)] == ledger[c.text(p)]


def test_exact_result(derived: dict[str, object]) -> None:
    assert c.RESULT_PATH.read_bytes() == c.two.render(derived)
    assert derived["ROWS_TOTAL"] == 4647 and derived["ROWS_CHANGED_FROM_FOUR_ROW"] == 1
    assert derived["CERTIFICATES_COMPOSED"] == 5
    assert derived["GLOBAL_K20_OPTIMUM"] == "UNKNOWN"
    assert (
        derived["SOLVER_CALLS"]
        == derived["DEGREE_CONFIGURATIONS_REENUMERATED"]
        == (derived["D6_ROUTE_B_TERMS_REVERIFIED"])
        == 0
    )
    assert (
        derived["RUN1_MUTATED"]
        == derived["HEAVY_SEARCH_STARTED"]
        == derived["REMOTE_WRITE"]
        == "NO"
    )
