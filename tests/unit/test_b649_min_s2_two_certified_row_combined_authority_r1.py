"""Deterministic integration and rejection tests using the real frozen ledger."""

from __future__ import annotations

import copy
import json
from collections.abc import Iterator
from dataclasses import replace
from unittest.mock import patch

import pytest

from lottolab.research import b649_min_s2_two_certified_row_combined_authority_r1 as x

Snapshot = tuple[dict[str, x.chase.Row], dict[str, object], dict[str, str]]
Certificates = tuple[dict[str, object], dict[str, object]]


@pytest.fixture(scope="module")
def snapshot() -> Snapshot:
    return x.baseline()


@pytest.fixture(scope="module")
def certificates() -> Certificates:
    return x.certificate(x.A)[0], x.certificate(x.B)[0]


@pytest.fixture(scope="module")
def derived(snapshot: Snapshot) -> Iterator[dict[str, object]]:
    # Replay is expensive; share its genuine output, leaving certificate checks live.
    with patch.object(x, "baseline", return_value=snapshot):
        yield x.compute_result()


def test_pinned_commits_proof_and_archives() -> None:
    for pin, blob_count in ((x.A, 2), (x.B, 10)):
        result, identity = x.certificate(pin)
        assert result["TARGET_PROFILE"] == pin.profile
        assert identity["JUDGE_STATUS"] == pin.judge_status
        assert len(x.object_row(identity["BLOB_SHA256"])) == blob_count


@pytest.mark.parametrize("field", ["tree", "source_sha256", "result_sha256"])
def test_wrong_identity_rejected(field: str) -> None:
    bad = replace(x.A, **{field: "0" * (40 if field == "tree" else 64)})
    with pytest.raises(AssertionError, match="mismatch"):
        x.certificate(bad)


def test_frozen_baseline_is_exact(snapshot: Snapshot) -> None:
    ledger, result, _provenance = snapshot
    assert len(ledger) == 4647
    assert x.bounds_digest(ledger) == x.LEDGER_DIGEST == result["FINAL_RESOLVED_ROWS_SHA256"]
    assert x.family(ledger) == (313404008, [x.A_PROFILE])
    assert x.chase.prior.CURSOR_ID not in ledger
    assert x.object_row(result["COVERAGE"])["UNDER_CURSOR_PROFILE_COUNT"] == 197


def test_complete_family_independently_recomputed(
    snapshot: Snapshot, derived: dict[str, object]
) -> None:
    ledger = snapshot[0]
    manual = {p: r.bound for p, r in ledger.items()}
    manual[x.A_PROFILE], manual[x.B_PROFILE] = 313242692, 313263888
    manual[x.chase.prior.CURSOR_ID] = x.chase.prior.CURSOR_BOUND
    best = max(manual.values())
    assert best == derived["FAMILY_BOUND_AFTER"] == 313401852
    assert sorted(p for p, b in manual.items() if b == best) == derived["NEW_FAMILY_OWNER"]
    assert derived["NEW_FAMILY_OWNER"] == ["66655555555440000000"]
    assert derived["EXACT_DELTA"] == 2156
    assert derived["NEW_GAP_TO_INCUMBENT"] == 137964
    assert derived["RESOLVED_ROWS_ABOVE_INCUMBENT_BEFORE"] == 1381
    assert derived["RESOLVED_ROWS_ABOVE_INCUMBENT"] == 1379
    assert derived["EXPECTED_VALUES_MATCH"] is True


def test_only_two_full_rows_change_and_order_is_irrelevant(
    snapshot: Snapshot, certificates: Certificates
) -> None:
    ledger = snapshot[0]
    before = copy.deepcopy(ledger)
    updates = x.certified_updates(ledger, *certificates)
    after = x.apply_updates(ledger, updates)
    assert after == x.apply_updates(ledger, updates[::-1])
    assert ledger == before
    assert sorted(p for p in ledger if ledger[p] != after[p]) == sorted((x.A_PROFILE, x.B_PROFILE))
    assert after[x.A_PROFILE].cap == 246
    assert after[x.B_PROFILE].cap == ledger[x.B_PROFILE].cap == 270
    for pid in ledger:
        assert after[pid].realization == ledger[pid].realization
        assert after[pid].s4_base == ledger[pid].s4_base


@pytest.mark.parametrize("selection", [(0,), (0, 0), (0, 1, 1)])
def test_missing_duplicate_and_extra_updates_rejected(
    snapshot: Snapshot, certificates: Certificates, selection: tuple[int, ...]
) -> None:
    updates = x.certified_updates(snapshot[0], *certificates)
    with pytest.raises(AssertionError, match="exactly two"):
        x.apply_updates(snapshot[0], [updates[i] for i in selection])


@pytest.mark.parametrize("which", [0, 1])
def test_certificate_does_not_transfer_to_another_profile(
    snapshot: Snapshot, certificates: Certificates, which: int
) -> None:
    a, b = copy.deepcopy(certificates)
    (a if which == 0 else b)["TARGET_PROFILE"] = "66655555555440000000"
    with pytest.raises(AssertionError, match="scope mismatch"):
        x.certified_updates(snapshot[0], a, b)


def test_a_envelope_and_b_partition_tampering_rejected(
    snapshot: Snapshot, certificates: Certificates
) -> None:
    a, b = copy.deepcopy(certificates)
    a["PROFILE_BOUND_AFTER"] = 313242691
    with pytest.raises(AssertionError, match="certificate A"):
        x.certified_updates(snapshot[0], a, b)
    a, b = copy.deepcopy(certificates)
    partition = x.object_row(b["PARTITION"])
    cells = x.rows(partition["RANGES"])
    x.object_row(cells[1])["T_LOW"] = 257
    with pytest.raises(AssertionError, match="partition gap"):
        x.certified_updates(snapshot[0], a, b)


def test_cursor_can_own_or_tie_family() -> None:
    cursor = x.chase.prior.CURSOR_BOUND
    assert x.family({x.A_PROFILE: x.chase.Row(cursor - 1, 246, 112, "fixture")}) == (
        cursor, [x.chase.prior.CURSOR_ID]
    )
    assert x.family({x.A_PROFILE: x.chase.Row(cursor, 246, 112, "fixture")}) == (
        cursor, sorted((x.A_PROFILE, x.chase.prior.CURSOR_ID))
    )


def test_all_row_metadata_is_part_of_preservation_digest(snapshot: Snapshot) -> None:
    ledger = snapshot[0]
    altered = dict(ledger)
    pid = "66655555555440000000"
    altered[pid] = replace(ledger[pid], source="different authority")
    assert x.bounds_digest(altered) == x.bounds_digest(ledger)
    assert x.full_digest(altered) != x.full_digest(ledger)


def test_status_scope_and_content_address(derived: dict[str, object]) -> None:
    b_identity = x.object_row(derived["CERTIFICATE_B_IDENTITY"])
    assert b_identity["JUDGE_STATUS"] == "VERIFIED_WITH_CAVEATS"
    assert derived["UNCHANGED_ROWS_COUNT"] == 4645
    assert derived["ROWS_CHANGED"] == 2
    assert derived["OTHER_PROFILES_AFFECTED"] == []
    assert derived["GLOBAL_K20_OPTIMUM"] == "UNKNOWN"
    assert derived["T264_DISPOSITION"] == "SUPERSEDED_INCOMPLETE"
    payload = x.render(derived)
    path = x.ROOT / x.RESULT_DIRECTORY / f"{x.RESULT_STEM}-{x.sha256(payload)}.json"
    assert path.read_bytes() == payload
    assert json.loads(payload) == json.loads(x.render(derived))


def test_no_search_entrypoint_called(snapshot: Snapshot, monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("combined integration invoked a new search")

    monkeypatch.setattr(x, "baseline", lambda: snapshot)
    monkeypatch.setattr(x.chase, "chase", forbidden)
    monkeypatch.setattr(x.chase, "refine", forbidden)
    monkeypatch.setattr(x.chase.split, "split_certificate", forbidden)
    assert x.compute_result()["SOLVER_CALLS"] == 0
