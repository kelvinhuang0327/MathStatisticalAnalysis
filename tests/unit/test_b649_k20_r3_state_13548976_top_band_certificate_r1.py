"""State 13548976 top-band certificate: ledger pins, band, rational certificates, tamper checks."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable, Iterator
from typing import Any, NoReturn, cast

import pytest

from lottolab.research import b649_k20_r3_state_13548976_top_band_certificate_r1 as band

FIRST_NEXT_LEVEL = 355_637_030
NEXT_LEVEL_OWNERS = [
    [[0, 12], [4, 5], [25, 1]],
    [[0, 12], [1, 1], [4, 4], [25, 1]],
    [[0, 12], [1, 2], [4, 3], [25, 1]],
    [[0, 12], [1, 3], [4, 2], [25, 1]],
    [[0, 12], [1, 4], [4, 1], [25, 1]],
    [[0, 12], [1, 5], [25, 1]],
]
# (witness counts, raw bound, certified bound) for all 21 top-band members.
EXPECTED_BAND = [
    ([[0, 10], [4, 2], [5, 6]], 355_726_896, 354_079_512),
    ([[0, 10], [1, 1], [4, 1], [5, 6]], 355_726_896, 354_079_201),
    ([[0, 10], [1, 2], [5, 6]], 355_726_896, 354_079_512),
    ([[0, 10], [4, 2], [5, 5], [16, 1]], 355_726_448, 353_982_716),
    ([[0, 10], [1, 1], [4, 1], [5, 5], [16, 1]], 355_726_448, 353_982_405),
    ([[0, 10], [1, 2], [5, 5], [16, 1]], 355_726_448, 353_982_716),
    ([[0, 10], [4, 2], [5, 4], [16, 2]], 355_726_000, 353_885_930),
    ([[0, 10], [1, 1], [4, 1], [5, 4], [16, 2]], 355_726_000, 353_885_619),
    ([[0, 10], [1, 2], [5, 4], [16, 2]], 355_726_000, 353_885_930),
    ([[0, 10], [4, 2], [5, 3], [16, 3]], 355_725_552, 353_789_152),
    ([[0, 10], [1, 1], [4, 1], [5, 3], [16, 3]], 355_725_552, 353_788_841),
    ([[0, 10], [1, 2], [5, 3], [16, 3]], 355_725_552, 353_789_152),
    ([[0, 10], [4, 2], [5, 2], [16, 4]], 355_725_104, 353_692_384),
    ([[0, 10], [1, 1], [4, 1], [5, 2], [16, 4]], 355_725_104, 353_692_073),
    ([[0, 10], [1, 2], [5, 2], [16, 4]], 355_725_104, 353_692_384),
    ([[0, 10], [4, 2], [5, 1], [16, 5]], 355_724_656, 353_584_220),
    ([[0, 10], [1, 1], [4, 1], [5, 1], [16, 5]], 355_724_656, 353_583_909),
    ([[0, 10], [1, 2], [5, 1], [16, 5]], 355_724_656, 353_584_220),
    ([[0, 10], [4, 2], [16, 6]], 355_724_208, 353_469_632),
    ([[0, 10], [1, 1], [4, 1], [16, 6]], 355_724_208, 353_469_321),
    ([[0, 10], [1, 2], [16, 6]], 355_724_208, 353_469_632),
]
COMPRESSED_RAW_MEMBER = [[0, 9], [1, 2], [4, 3], [5, 3], [17, 1]]
# Captured before any test patches ``r24_authority``.
CACHED = (band.r24_authority, band.target_region_ledger, band.carried_member_certificates)


def forbidden(*_: object, **__: object) -> NoReturn:
    pytest.fail("forbidden census, tail walk, solver or classification work")


def stored_result() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(band.RESULT_PATH.read_text(encoding="utf-8")))


def ledger_member(witness: list[list[int]]) -> band.LedgerMember:
    counts = band.dense(witness)
    return next(member for member in band.target_region_ledger() if member.counts == counts)


def clear_caches() -> None:
    for function in CACHED:
        function.cache_clear()


@pytest.fixture
def isolated_caches() -> Iterator[None]:
    clear_caches()
    yield
    clear_caches()


def target_region(stored: dict[str, Any]) -> dict[str, Any]:
    return next(
        row
        for row in stored["STATE_REGION_CERTIFICATES"]
        if row["owner_id"] == band.TARGET_STATE_ID
    )


def test_base_tree_and_upstream_pins_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    assert band.__file__.startswith(str(band.REPO_ROOT / "src"))
    tree = subprocess.run(
        ["git", "-C", str(band.REPO_ROOT), "rev-parse", f"{band.BASE_HEAD}^{{tree}}"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert tree.stdout.strip() == band.BASE_TREE
    assert band.verify_upstream_fingerprints() == band.UPSTREAM_SHA256
    assert len(band.UPSTREAM_SHA256) == 7
    for relative in band.UPSTREAM_SHA256:
        monkeypatch.setattr(band, "UPSTREAM_SHA256", band.UPSTREAM_SHA256 | {relative: "0" * 64})
        with pytest.raises(AssertionError, match="R24 authority fingerprint mismatch"):
            band.verify_upstream_fingerprints()
        monkeypatch.undo()
    authority = band.r24_authority()
    assert authority["R3_BOUND"] == band.R24_DURABLE_R3_BOUND == 355_734_631
    assert authority["FINAL_OWNER_IDS"] == [band.r24.TAIL_ID]
    assert authority["STATE_MAX_OWNER_IDS"] == [band.TARGET_STATE_ID]
    assert band.r14.joint_constant() == 372_228_640 - 3_469_942


def test_region_ledger_fingerprint_and_carried_completeness() -> None:
    members = band.target_region_ledger()
    assert len(members) == band.REGION_MEMBER_COUNT == 1_427
    assert sum(member.represented_vector_count for member in members) == 1_543
    assert sum(member.represented_vector_count > 1 for member in members) == 114
    assert band.region_fingerprint(members) == band.TARGET_REGION_SHA256
    assert max(member.final_bound for member in members) == band.START_STATE_BOUND
    carried = band.carried_member_certificates()
    assert len(carried) == 62
    assert {label for label, _ in carried.values()} == {"R24"}
    assert {member.counts for member in members if member.final_bound != member.raw_bound} == set(
        carried
    )
    # No earlier round (R14-R23) ever certified a member of this region.
    assert band.r24.carried_member_certificates(band.TARGET_STATE_ID) == ()


def uncertified_row(stored: dict[str, Any]) -> dict[str, Any]:
    return next(
        row
        for row in target_region(stored)["complete_region_members"]
        if row["final_bound"] == row["raw_bound"] and row["final_bound"] < 355_000_000
    )


def tamper_member_bounds(stored: dict[str, Any]) -> None:
    # Raw and final move together, so only the region fingerprint can notice.
    row = uncertified_row(stored)
    row["raw_bound"] += 1
    row["final_bound"] += 1


def tamper_region_digest_consistently(stored: dict[str, Any]) -> None:
    # Every stored digest is rewritten to match; only the Packet pin can notice.
    tamper_member_bounds(stored)
    region = target_region(stored)
    members = tuple(
        band.LedgerMember(
            band.dense(row["witness_counts"]),
            row["represented_vector_count"],
            row["raw_bound"],
            row["final_bound"],
        )
        for row in region["complete_region_members"]
    )
    region["region_sha256"] = band.region_fingerprint(members)
    for entry in stored["CARRIED_OWNER_REGION_CERTIFICATES"]:
        if entry["owner_id"] == band.TARGET_STATE_ID:
            entry["region_sha256"] = region["region_sha256"]


def tamper_unbacked_reduction(stored: dict[str, Any]) -> None:
    uncertified_row(stored)["final_bound"] -= 1
    # Keep the ledger's own count consistent so only the certificate backing can fail.
    target_region(stored)["certified_member_count"] += 1


def tamper_duplicate_certificate(stored: dict[str, Any]) -> None:
    rows = stored["STATE_OWNER_CERTIFICATES"]
    rows.append(next(row for row in rows if row["owner_id"] == band.TARGET_STATE_ID))


def tamper_missing_member(stored: dict[str, Any]) -> None:
    del target_region(stored)["complete_region_members"][-1]


def tamper_represented_count(stored: dict[str, Any]) -> None:
    target_region(stored)["complete_region_members"][0]["represented_vector_count"] += 1


@pytest.mark.parametrize(
    ("tamper", "message"),
    [
        (tamper_member_bounds, "ledger fingerprint or completeness"),
        (tamper_region_digest_consistently, "ledger fingerprint or completeness"),
        (tamper_unbacked_reduction, "not backed by its committed certificate"),
        (tamper_duplicate_certificate, "more than one committed correction"),
        (tamper_missing_member, "ledger fingerprint or completeness"),
        (tamper_represented_count, "ledger fingerprint or completeness"),
    ],
)
def test_tampered_r24_ledger_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    isolated_caches: None,
    tamper: Callable[[dict[str, Any]], None],
    message: str,
) -> None:
    stored = json.loads((band.REPO_ROOT / band.R24_RESULT_RELATIVE).read_text(encoding="utf-8"))
    tamper(stored)
    monkeypatch.setattr(band, "r24_authority", lambda: stored)
    with pytest.raises(AssertionError, match=message):
        band.target_region_ledger()
        band.carried_member_certificates()


def test_every_ledger_raw_bound_replays_from_r7_state_fields() -> None:
    members = band.target_region_ledger()
    for member in members:
        state = band.rebuild_member(member)
        assert band.r14.raw_bound(state) == member.raw_bound
        assert state.witness_counts == member.counts
    member = members[0]
    with pytest.raises(AssertionError, match="does not replay its ledger raw bound"):
        band.rebuild_member(band.LedgerMember(member.counts, 1, member.raw_bound + 1, 0))


def test_top_band_is_seven_raw_448_step_levels_of_three() -> None:
    members = band.target_region_ledger()
    levels = band.top_band(members)
    assert [level for level, _ in levels] == [355_726_896 - 448 * step for step in range(7)]
    rows = [member for _, level_rows in levels for member in level_rows]
    assert [(band.sparse(member.counts), member.raw_bound) for member in rows] == [
        (witness, raw) for witness, raw, _ in EXPECTED_BAND
    ]
    assert all(member.final_bound == member.raw_bound for member in rows)
    assert all(member.represented_vector_count == 1 for member in rows)
    rest = [member.final_bound for member in members if member not in rows]
    assert max(rest) == FIRST_NEXT_LEVEL
    with pytest.raises(AssertionError, match="seven levels of three"):
        band.top_band(tuple(member for member in members if member != rows[-1]))


def test_each_band_member_takes_one_rational_correction() -> None:
    result = stored_result()
    records = result["NEW_MEMBER_CERTIFICATES"]
    assert [
        (row["member"]["witness_counts"], row["member_raw_bound"], row["member_new_bound"])
        for row in records
    ] == EXPECTED_BAND
    for row in records:
        band.check_certificate_arithmetic(row)
        applied = row["prior_applied_correction"]
        rational = row["minimum_vector_rational_correction"]
        assert applied == 3_444_000 < rational
        assert row["member_certified_correction"] == rational
        assert row["member_raw_bound"] - row["member_new_bound"] == rational - applied
        assert len(row["vector_certificates"]) == len(row["support_witnesses"]) == 1
    assert result["MAXIMUM_NEW_MEMBER_BOUND"] == 354_079_512
    assert result["MINIMUM_NEW_MEMBER_DROP"] == 1_647_384
    assert band.normalized(band.certify_member(ledger_member(EXPECTED_BAND[0][0]))) == records[0]


def test_compressed_member_certificate_covers_every_vector(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    member = ledger_member(COMPRESSED_RAW_MEMBER)
    assert member.represented_vector_count == 2 and member.final_bound == member.raw_bound
    record = band.certify_member(member)
    assert len(record["represented_vectors"]) == len(record["support_witnesses"]) == 2
    assert record["represented_vectors"][0] == COMPRESSED_RAW_MEMBER
    band.verify_member_certificate(band.normalized(record), member)
    # Distinct vector corrections: the member must take the smaller one.
    original = band.r14.moment_certificate
    raised: list[int] = []

    def uneven(counts: Any) -> dict[str, Any]:
        row = original(counts)
        if counts != member.counts:
            row = row | {"correction_lower_bound": row["correction_lower_bound"] + 1_000}
            raised.append(row["correction_lower_bound"])
        return row

    monkeypatch.setattr(band.r14, "moment_certificate", uneven)
    uneven_record = band.certify_member(member)
    corrections = [row["correction_lower_bound"] for row in uneven_record["vector_certificates"]]
    assert raised and corrections[1] == corrections[0] + 1_000
    assert uneven_record["minimum_vector_rational_correction"] == corrections[0]
    assert uneven_record["member_new_bound"] == record["member_new_bound"]
    monkeypatch.undo()
    with pytest.raises(AssertionError, match="represented vectors were not recovered"):
        band.certify_member(band.LedgerMember(member.counts, 1, member.raw_bound, member.raw_bound))


def test_spent_or_forest_dominated_member_is_never_recertified(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    carried = band.carried_member_certificates()
    spent = ledger_member([[0, 8], [4, 9], [25, 1]])
    assert (
        carried[spent.counts] == ("R24", spent.final_bound) and spent.final_bound < spent.raw_bound
    )
    monkeypatch.setattr(band.r17, "represented_vectors", forbidden)
    with pytest.raises(band.r15.RationalRouteExhausted):
        band.certify_member(spent)
    monkeypatch.undo()
    # Good count 14: the R7 forest floor 5,740,000 exceeds every vector's rational correction.
    dominated = ledger_member([[0, 14], [4, 1], [9, 1], [17, 2]])
    assert dominated.represented_vector_count == 4 and dominated.counts not in carried
    assert band.rebuild_member(dominated).applied_residual_union_penalty == 5_740_000
    with pytest.raises(band.r15.RationalRouteExhausted):
        band.certify_member(dominated)


def test_state_recomputation_replaces_only_band_bounds() -> None:
    members = band.target_region_ledger()
    records = stored_result()["NEW_MEMBER_CERTIFICATES"]
    bounds = band.recompute_state(members, records)
    certified = {band.dense(row["member"]["witness_counts"]) for row in records}
    assert len(certified) == band.TOP_BAND_MEMBER_COUNT
    assert all(
        bounds[member.counts] == member.final_bound
        for member in members
        if member.counts not in certified
    )
    assert max(bounds.values()) == FIRST_NEXT_LEVEL
    assert [
        band.sparse(member.counts)
        for member in members
        if bounds[member.counts] == FIRST_NEXT_LEVEL
    ] == NEXT_LEVEL_OWNERS
    assert sum(bounds[member.counts] != member.raw_bound for member in members) == 83
    with pytest.raises(AssertionError, match="certified twice"):
        band.recompute_state(members, [*records, records[0]])
    stale = records[0] | {"member_prior_bound": records[0]["member_prior_bound"] - 1}
    with pytest.raises(AssertionError, match="does not replace a carried R24 member bound"):
        band.recompute_state(members, [stale, *records[1:]])


def test_build_is_zero_solve_band_local_and_byte_replays(
    monkeypatch: pytest.MonkeyPatch, isolated_caches: None
) -> None:
    for module, name in (
        (band.r7, "joint_residual_census"),
        (band.r24, "pinned_r7_census"),
        (band.r24, "state_region"),
        (band.r24.r22, "pinned_r7_census"),
        (band.r24.r22, "state_region"),
        (band.r14, "owner_region"),
        (band.r24, "run_chase"),
        (band.r24, "advance_tail"),
        (band.r24, "next_tail_level"),
        (band.r24.r16, "next_attained_loss"),
        (band.r24.r13, "classify_vector"),
        (band.r14, "s4_child"),
        (band.r6, "iter_type_count_vectors"),
    ):
        monkeypatch.setattr(module, name, forbidden)
    windows: list[tuple[int, int]] = []
    original = band.r24.r16.iter_interval_vectors

    def spy(losses: Any, tickets: int, lower: int, upper: int) -> Any:
        windows.append((lower, upper))
        return original(losses, tickets, lower, upper)

    monkeypatch.setattr(band.r24.r16, "iter_interval_vectors", spy)
    result = band.build_result()
    band_losses = {
        row["local_loss"] for level in result["TOP_BAND_LEVELS"] for row in level["members"]
    }
    assert {lower for lower, _ in windows} == band_losses and len(band_losses) == 7
    assert all(lower == upper for lower, upper in windows)
    assert band.encode(result) == band.RESULT_PATH.read_text(encoding="utf-8")


def test_stored_result_summary_and_no_r3_claim() -> None:
    result = stored_result()
    assert band.verify_result(result) == {
        "verified_member_certificates": 21,
        "final_state_bound": FIRST_NEXT_LEVEL,
        "status": "PASS",
    }
    assert result["TASK_STATUS"] == "SUCCESS"
    assert result["TOP_BAND_CLEARED"] is True
    assert result["PREVIOUSLY_CERTIFIED_BAND_MEMBERS"] == []
    assert result["START_STATE_BOUND"] == 355_726_896
    assert result["FINAL_STATE_BOUND"] == result["RESEARCH_PROJECTED_STATE_BOUND"]
    assert result["STATE_DROP"] == 89_866
    assert result["TOP_BAND_LEVEL_SPACING"] == [448]
    assert result["NEXT_COMPETING_STATE_ID"] == "state:s2-12692531-s3-681744"
    assert result["NEXT_COMPETING_STATE_BOUND"] == 355_722_668
    assert result["PACKET_KNOWN_NEXT_STATE_IDS"] == ["state:s2-14122976-s3-1005536"]
    assert result["PACKET_KNOWN_NEXT_STATE_RANK"] == 2
    assert result["R3_DURABLE_BOUND"] == 355_734_631
    assert result["R3_DURABLE_BOUND_UNCHANGED"] is True
    assert result["R3_CLAIM"] == "NONE_STATE_LOCAL_CERTIFICATE_ONLY"
    assert result["NEW_HEAVY_SOLVER_STARTED"] == "NO"
    assert result["PRODUCTION_MUTATION"] == "NONE"


def first(result: dict[str, Any]) -> dict[str, Any]:
    return cast(dict[str, Any], result["NEW_MEMBER_CERTIFICATES"][0])


def sync_region_row(result: dict[str, Any]) -> None:
    """Carry a tampered member bound into the region rows, so only the targeted check fails."""

    row = first(result)
    region_row = next(
        region_row
        for region_row in result["COMPLETE_REGION_MEMBERS"]
        if region_row["witness_counts"] == row["member"]["witness_counts"]
    )
    region_row["final_bound"] = row["member_new_bound"]


def lower_new_bound(result: dict[str, Any]) -> None:
    row = first(result)
    row["member_new_bound"] -= 1
    row["member_drop"] += 1
    sync_region_row(result)


def sum_corrections(result: dict[str, Any]) -> None:
    row = first(result)
    rational = row["minimum_vector_rational_correction"]
    row["member_certified_correction"] = row["prior_applied_correction"] + rational
    row["member_new_bound"] = row["member_raw_bound"] - rational
    row["member_drop"] = rational
    sync_region_row(result)


def round_down_correction(result: dict[str, Any]) -> None:
    certificate = first(result)["vector_certificates"][0]
    certificate["correction_lower_bound"] += 1


def inflate_pair_moment_consistently(result: dict[str, Any]) -> None:
    row = first(result)
    certificate = row["vector_certificates"][0]
    certificate["residual_s2_lower_bound"] += 9
    certificate["correction_lower_bound"] += 1
    for key in ("minimum_vector_rational_correction", "member_certified_correction"):
        row[key] += 1
    row["member_new_bound"] -= 1
    row["member_drop"] += 1
    sync_region_row(result)


def collide_support_witness(result: dict[str, Any]) -> None:
    witness = first(result)["support_witnesses"][0]["support_witness"]
    witness[1] = list(witness[0])


def shift_member_identity(result: dict[str, Any]) -> None:
    first(result)["member"]["anchor_triple_s3"] += 1


def drop_band_member(result: dict[str, Any]) -> None:
    del result["NEW_MEMBER_CERTIFICATES"][-1]


def duplicate_band_member(result: dict[str, Any]) -> None:
    result["NEW_MEMBER_CERTIFICATES"].append(first(result))


def lower_non_band_member(result: dict[str, Any]) -> None:
    row = next(row for row in result["COMPLETE_REGION_MEMBERS"] if row["raw_bound"] < 355_000_000)
    row["final_bound"] -= 1


def raise_final_bound(result: dict[str, Any]) -> None:
    result["FINAL_STATE_BOUND"] += 1


def swap_region(result: dict[str, Any]) -> None:
    result["REGION_SHA256"] = "0" * 64


def claim_r3(result: dict[str, Any]) -> None:
    result["R3_CLAIM"] = "DURABLE_GLOBAL_R3"


@pytest.mark.parametrize(
    "tamper",
    [
        lower_new_bound,
        sum_corrections,
        round_down_correction,
        inflate_pair_moment_consistently,
        collide_support_witness,
        shift_member_identity,
        drop_band_member,
        duplicate_band_member,
        lower_non_band_member,
        raise_final_bound,
        swap_region,
        claim_r3,
    ],
)
def test_tampered_certificate_is_rejected(tamper: Callable[[dict[str, Any]], None]) -> None:
    result = stored_result()
    tamper(result)
    with pytest.raises(AssertionError):
        band.verify_result(result)
