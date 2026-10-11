"""Focused guards for exact existing S4 adoption and complete-family recount."""

from __future__ import annotations

import copy
import json
import sys
from collections.abc import Iterator
from dataclasses import replace
from unittest.mock import patch

import pytest

from lottolab.research import b649_min_s2_six_row_existing_s4_family_authority_r1 as c


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
        patch.object(c.five.four.three, "core_zero_theorem", forbidden),
        patch.object(c.five.four.three, "witness", forbidden),
        patch.object(c.five.four.three, "compute_result", forbidden),
    ):
        return c.five_row_ledger(pinned[0])


@pytest.fixture(scope="module")
def derived(ledger: dict[str, c.Row]) -> Iterator[dict[str, object]]:
    # Reuse only the genuine, digest-validated replay in the fixture above.
    with patch.object(c, "five_row_ledger", return_value=ledger):
        yield c.compute_result()


def test_exact_donor_identity_and_actual_disposition(pinned: tuple[dict[str, object], ...]) -> None:
    prior, cert, identity = pinned
    assert prior["AUTHORITY_JUDGE_STATUS"] == "VERIFIED_WITH_CAVEATS"
    assert identity["JUDGE_STATUS"] == "SELF_CHECK_ONLY"
    assert identity["JUDGE_STATUS_SOURCE"] == "PINNED_DONOR_RESULT_JUDGE_MODE"
    assert identity["SHARED_SCIENTIFIC_DEPENDENCIES"] == 27
    assert len(c.rows(identity["DONOR_ONLY_DEPENDENCIES"])) == 3
    assert cert["NEW_S4_FLOOR"] == 309183
    assert cert["CAP_NEW_BOUND"] == 313387988
    assert cert["CERTIFIED_PROFILE_BOUND"] == 313391920
    assert not (c.ROOT / f"src/lottolab/research/{c.DONOR_MODULE}.py").exists()
    assert f"lottolab.research.{c.DONOR_MODULE}" not in sys.modules


@pytest.mark.parametrize(
    "name",
    [
        "BASE_TREE",
        "DONOR_TREE",
        "COMMON_ANCESTOR",
        "BASE_RESULT_SHA256",
        "DONOR_RESULT_SHA256",
        "DONOR_SOURCE_SHA256",
        "DONOR_TEST_SHA256",
        "FIVE_JUDGE_SHA256",
    ],
)
def test_wrong_authority_rejected(name: str) -> None:
    with (
        patch.object(c, name, "0" * (64 if name.endswith("SHA256") else 40)),
        pytest.raises(AssertionError, match=r"tree|ancestry|digest"),
    ):
        c.authorities()


def test_five_row_seal(ledger: dict[str, c.Row], pinned: tuple[dict[str, object], ...]) -> None:
    assert len(ledger) == 4647
    assert c.two.full_digest(ledger) == pinned[0]["FULL_ROWS_SHA256_AFTER"]
    assert c.two.bounds_digest(ledger) == pinned[0]["BOUNDS_SHA256_AFTER"]
    assert (ledger[c.TARGET_PROFILE].bound, ledger[c.TARGET_PROFILE].cap) == (313401076, 264)


def test_only_one_bound_source_changes(
    ledger: dict[str, c.Row], pinned: tuple[dict[str, object], ...]
) -> None:
    digest = c.two.full_digest(ledger)
    after = c.apply_sixth(ledger, pinned[1])
    assert c.two.full_digest(ledger) == digest
    assert [p for p in ledger if after[p] != ledger[p]] == [c.TARGET_PROFILE]
    assert after[c.TARGET_PROFILE].bound == 313391920
    assert (
        replace(
            after[c.TARGET_PROFILE],
            bound=ledger[c.TARGET_PROFILE].bound,
            source=ledger[c.TARGET_PROFILE].source,
        )
        == ledger[c.TARGET_PROFILE]
    )
    assert all(
        after[c.text(p)] == ledger[c.text(p)] for p in c.rows(pinned[0]["CERTIFICATE_PROFILE_IDS"])
    )


def test_equal_stronger_and_duplicate_rejected(
    ledger: dict[str, c.Row], pinned: tuple[dict[str, object], ...]
) -> None:
    once = c.apply_sixth(ledger, pinned[1])
    for candidate in (
        once,
        {**ledger, c.TARGET_PROFILE: replace(ledger[c.TARGET_PROFILE], bound=313391919)},
    ):
        with pytest.raises(AssertionError, match="already tightened"):
            c.apply_sixth(candidate, pinned[1])


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("PROFILE_ID", "66555555555540000000"),
        ("TRIANGLE_CAP", 263),
        ("S4_BASE", 111),
        ("NEW_S4_FLOOR", 309182),
        ("CERTIFIED_PROFILE_BOUND", 313387988),
    ],
)
def test_wrong_scope_and_cap_term_only_bound_rejected(
    pinned: tuple[dict[str, object], ...], key: str, value: object
) -> None:
    with pytest.raises(AssertionError, match="target/premises/bound/S4"):
        c.verify_scope({**pinned[1], key: value})


def test_retained_lower_t_and_cap_source_tampering_rejected(
    ledger: dict[str, c.Row], pinned: tuple[dict[str, object], ...]
) -> None:
    cert = copy.deepcopy(pinned[1])
    terms = c.rows(cert["ALL_T_TERMS"])
    terms[-2] = [263, 313387988, 483, 201, 281526, 5162752]
    with pytest.raises(AssertionError, match="retained lower-T"):
        c.verify_scope(cert)
    cert = copy.deepcopy(pinned[1])
    cert["CAP_SOURCE_IDENTITY"] = {**c.object_row(cert["CAP_SOURCE_IDENTITY"]), "STATUS": "UNKNOWN"}
    with pytest.raises(AssertionError, match="cap-source identity"):
        c.apply_sixth(ledger, cert)


def test_complete_family_independent_recount(
    ledger: dict[str, c.Row], pinned: tuple[dict[str, object], ...], derived: dict[str, object]
) -> None:
    after = c.apply_sixth(ledger, pinned[1])
    bounds = {p: r.bound for p, r in after.items()}
    cursor = c.object_row(pinned[0]["CURSOR"])
    bounds[c.text(cursor["ID"])] = c.integer(cursor["BOUND"])
    best = max(bounds.values())
    assert best == 313398920 == derived["FAMILY_BOUND_AFTER"]
    assert sorted(p for p, v in bounds.items() if v == best) == ["66555555555540000000"]
    assert derived["FAMILY_OWNER_IDS"] == ["66555555555540000000"]
    assert 313401076 - best == derived["FAMILY_BOUND_DELTA"] == 2156
    assert best - 313263888 == derived["GAP_TO_INCUMBENT"] == 135032
    above = sorted(p for p, r in after.items() if r.bound > 313263888)
    assert len(above) == derived["RESOLVED_ROWS_ABOVE_INCUMBENT"] == 1378
    assert above == derived["RESOLVED_ROW_IDS_ABOVE_INCUMBENT"]
    assert derived["STILL_OPEN_PROFILE_COUNT"] == 1575
    assert {p: r.bound for p, r in after.items()} == derived["RESOLVED_ROW_BOUNDS"]


def test_cursor_and_all_tied_owners_are_load_bearing(ledger: dict[str, c.Row]) -> None:
    cursor, owner = "66544333333333332222", "66555555555540000000"
    below = {p: replace(r, bound=313263888) for p, r in ledger.items()}
    assert c.five.four.three.family(below)[:2] == (313394584, [cursor])
    below[owner] = replace(below[owner], bound=313394584)
    assert c.five.four.three.family(below)[:2] == (313394584, sorted([cursor, owner]))


def test_full_prior_authority_and_caveats_preserved(
    pinned: tuple[dict[str, object], ...], derived: dict[str, object]
) -> None:
    prior = json.loads(c.two.blob(c.BASE_HEAD, c.BASE_RESULT_PATH, c.BASE_RESULT_SHA256))
    assert derived["PRESERVED_FIVE_ROW_AUTHORITY"] == prior == pinned[0]
    assert derived["PRIOR_JUDGE_CAVEATS"] == "PRESERVED"
    assert derived["AUTHORITY_JUDGE_STATUS"] == "VERIFIED_WITH_CAVEATS"
    assert derived["DONOR_JUDGE_STATUS"] == "SELF_CHECK_ONLY"
    assert (
        c.sha256((c.ROOT / c.ARCHIVE / "five-row-fresh-judge.md").read_bytes())
        == c.FIVE_JUDGE_SHA256
    )
    assert derived["CURSOR"] == prior["CURSOR"]
    assert derived["CURSOR_PARTITION_AUTHORITY"] == prior["CURSOR_PARTITION_AUTHORITY"]


def test_exact_result(derived: dict[str, object]) -> None:
    assert c.RESULT_PATH.read_bytes() == c.two.render(derived)
    assert derived["LEDGER_ROWS"] == 4647 and derived["ROWS_CHANGED_FROM_FIVE_ROW"] == 1
    assert derived["CERTIFICATES_COMPOSED"] == 6
    assert derived["GLOBAL_K20_OPTIMUM"] == "UNKNOWN"
    assert derived["SOLVER_CALLS"] == derived["DONOR_LOCAL_CASES_REVERIFIED"] == 0
    assert derived["DONOR_FULL_T_ARITHMETIC_REVERIFIED"] == 0
    assert (
        derived["RUN1_MUTATED"]
        == derived["HEAVY_SOLVER_STARTED"]
        == derived["REMOTE_WRITE"]
        == "NO"
    )
