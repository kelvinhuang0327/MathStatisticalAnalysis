"""Focused checks for the twelve-side F3 three-ticket cycle search and its sealed result."""

from __future__ import annotations

import json
from collections import Counter
from functools import cache
from math import comb
from pathlib import Path
from typing import Any, cast

import pytest

from lottolab.research import b649_k20_f2_neutral_f3_three_ticket_cycle_r1 as search
from lottolab.research.b649_official_any_prize_exact import (
    DrawMasks,
    all_main_draw_masks,
    evaluate_portfolio,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
RESULT_FILE = REPO_ROOT / search.RESULT_PATH
START_COUNT = 313_263_888
SLOT_DIGITS = "0123456789abcdefghijklmnopqrstuvwxyz"


@cache
def _start() -> search.Start:
    return search.load_start(REPO_ROOT)


@cache
def _structure() -> search.Structure:
    return search.derive_structure(_start().portfolio)


@cache
def _space() -> search.Space:
    return search.enumerate_space(_structure())


@cache
def _draws() -> DrawMasks:
    return all_main_draw_masks(49, 6)


@cache
def _result() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(RESULT_FILE.read_text(encoding="utf-8")))


def _sealed_start() -> dict[str, Any]:
    return cast(
        dict[str, Any], json.loads((REPO_ROOT / search.START_RESULT_PATH).read_text("utf-8"))
    )


def _tickets(value: object) -> search.Portfolio:
    return tuple(tuple(cast(list[int], ticket)) for ticket in cast(list[object], value))


def _replay(code: str) -> search.Portfolio:
    """Rebuild the slot-ordered candidate from its ``x-y-z@abc:D`` instantiation code."""

    numbers_text, rest = code.split("@")
    slot_text, direction_code = rest.split(":")
    x, y, z = (int(number) for number in numbers_text.split("-"))
    a, b, c = (SLOT_DIGITS.index(digit) for digit in slot_text)
    direction = {"F": "FORWARD", "R": "REVERSE"}[direction_code]
    assert search.instantiation_code((x, y, z), (a, b, c), direction) == code
    slotted, reason = search.apply_moves(
        _start().portfolio, search.cycle_moves((x, y, z), (a, b, c), direction)
    )
    assert reason is None and slotted is not None
    return slotted


def test_module_resolves_inside_this_checkout() -> None:
    assert Path(search.__file__).resolve().is_relative_to(REPO_ROOT)


def test_start_identity_and_canonical_rescore(tmp_path: Path) -> None:
    start = _start()
    sealed = _sealed_start()
    exact = evaluate_portfolio(start.portfolio, draws=_draws())

    assert start.count == START_COUNT
    assert start.sha256 == sealed["FINAL"]["NORMALIZED_SHA256"]
    assert search.portfolio_sha256(start.portfolio) == start.sha256
    assert exact.official_any_prize_outcome_count == START_COUNT
    assert start.single_ticket_status == search.SINGLE_TICKET_STATUS
    source = _result()["SOURCE_AUTHORITY"]
    assert source["START_SHA256"] == start.sha256
    assert source["START_RESULT_FILE_SHA256"] == start.file_sha256
    assert _result()["START"]["M3_PLUS_DRAW_COUNT"] == exact.m3_plus_draw_count
    identity = search.source_identity(REPO_ROOT)
    assert identity["START_AUTHORITY_COMMIT"] == search.START_AUTHORITY_COMMIT
    assert identity["START_RESULT_BLOB"] == source["START_RESULT_BLOB"]

    drifts: tuple[tuple[str, str | None, object], ...] = (
        ("FINAL", "OFFICIAL_ANY_PRIZE_OUTCOME_COUNT", START_COUNT + 1),
        ("FINAL", "NORMALIZED_SHA256", "0" * 64),
        ("LOCAL_OPTIMUM", None, False),
        ("READY_FOR_TWO_TICKET_ASCENT", None, "YES"),
        ("ACCEPTED_MOVE_COUNT", None, 1),
    )
    target = tmp_path / search.START_RESULT_PATH
    target.parent.mkdir(parents=True)
    for key, inner, value in drifts:
        drifted = _sealed_start()
        if inner is None:
            drifted[key] = value
        else:
            drifted[key][inner] = value
        target.write_text(json.dumps(drifted), encoding="utf-8")
        with pytest.raises(search.StartIdentityMismatchError):
            search.load_start(tmp_path)


def test_structure_recomputes_components_f3_and_f2() -> None:
    structure = _structure()
    section = _result()["STRUCTURE"]

    assert structure.twelve_slots == tuple(range(12))
    assert structure.eight_slots == tuple(range(12, 20))
    assert len(structure.twelve_f3) == 20
    assert all(
        len(structure.supports[number]) == 3
        and set(structure.supports[number]) <= set(structure.twelve_slots)
        for number in structure.twelve_f3
    )
    assert len(structure.f2_supports) == 27
    assert section["TWELVE_SIDE_F3_COUNT"] == 20
    assert section["TWELVE_SIDE_F3_SUPPORTS"] == {
        str(number): list(structure.supports[number]) for number in structure.twelve_f3
    }
    assert section["F2_SUPPORTS_FROZEN"] == {
        str(number): list(slots) for number, slots in structure.f2_supports
    }

    crossed = [list(ticket) for ticket in _start().portfolio]
    crossed[0][crossed[0].index(21)] = 27
    crossed[12][crossed[12].index(27)] = 21
    with pytest.raises(search.StructureIdentityMismatchError):
        search.derive_structure(tuple(tuple(sorted(ticket)) for ticket in crossed))


def test_operator_directions_and_rejections() -> None:
    assert search.cycle_moves((1, 2, 3), (4, 5, 6), "FORWARD") == ((1, 4, 5), (2, 5, 6), (3, 6, 4))
    assert search.cycle_moves((1, 2, 3), (4, 5, 6), "REVERSE") == ((1, 4, 6), (3, 6, 5), (2, 5, 4))
    start = _start().portfolio
    supports = _structure().supports
    assert (supports[1], supports[2], supports[3]) == ((0, 1, 2), (0, 3, 4), (0, 5, 6))
    collision = search.cycle_moves((1, 2, 3), (0, 0, 0), "FORWARD")
    assert search.apply_moves(start, collision) == (None, search.REJECT_SLOT_COLLISION)
    # FORWARD sends 1 from slot 1 to slot 0, which already holds 1.
    receiver = search.cycle_moves((1, 2, 3), (1, 0, 5), "FORWARD")
    assert 1 in start[0]
    assert search.apply_moves(start, receiver) == (None, search.REJECT_RECEIVER_HOLDS_NUMBER)
    legal, reason = search.apply_moves(start, search.cycle_moves((1, 2, 3), (1, 3, 5), "FORWARD"))
    assert reason is None and legal is not None
    assert (1 in legal[3], 2 in legal[5], 3 in legal[1]) == (True, True, True)
    assert (1 in legal[1], 2 in legal[3], 3 in legal[5]) == (False, False, False)


def test_invariant_checker_rejects_each_violation() -> None:
    structure = _structure()
    start = [list(ticket) for ticket in structure.start]
    legal = list(_replay(_space().candidates[0].code))

    def check(tickets: list[list[int]] | list[tuple[int, ...]]) -> None:
        search.check_candidate(structure, tuple(tuple(sorted(ticket)) for ticket in tickets))

    check(legal)
    with pytest.raises(search.CandidateInvariantError):
        check(start)
    # Swap an F2 number between two already-changed slots: three slots still differ and every
    # frequency is kept, so only the F2-support invariant can reject it.
    changed = [slot for slot in range(20) if tuple(legal[slot]) != structure.start[slot]]
    first, second = changed[:2]
    f2_number = next(
        number
        for number in legal[first]
        if len(structure.supports[number]) == 2 and number not in legal[second]
    )
    partner = next(number for number in legal[second] if number not in legal[first])
    f2_moved = [list(ticket) for ticket in legal]
    f2_moved[first][f2_moved[first].index(f2_number)] = partner
    f2_moved[second][f2_moved[second].index(partner)] = f2_number
    assert [slot for slot in range(20) if sorted(f2_moved[slot]) != list(start[slot])] == changed
    with pytest.raises(search.CandidateInvariantError, match="F2 support"):
        check(f2_moved)
    eight_changed = [list(ticket) for ticket in legal]
    eight_changed[12][eight_changed[12].index(27)] = 28
    with pytest.raises(search.CandidateInvariantError):
        check(eight_changed)


def test_enumeration_accounting_matches_result() -> None:
    space = _space()
    enumeration = _result()["ENUMERATION"]

    assert space.raw_closed_form == comb(20, 3) * 3**3 * 2 == 61_560
    assert space.raw_enumerated == space.raw_closed_form
    assert space.raw_enumerated - sum(space.rejections.values()) == space.legal
    assert enumeration["RAW_OPERATOR_INSTANTIATIONS"] == space.raw_enumerated
    assert enumeration["REJECTIONS"] == dict(space.rejections)
    assert enumeration["LEGAL_CANDIDATES"] == space.legal
    assert enumeration["UNIQUE_NORMALIZED_CANDIDATES"] == len(space.candidates)
    assert enumeration["DUPLICATE_LEGAL_INSTANTIATIONS"] == space.duplicate_legal
    assert enumeration["SCORED"] == len(space.candidates)
    assert sum(len(candidate.instantiation_codes) for candidate in space.candidates) == space.legal
    assert len({candidate.portfolio for candidate in space.candidates}) == len(space.candidates)


def test_every_candidate_preserves_frozen_structure_independently() -> None:
    structure = _structure()
    start = structure.start
    start_frequency = Counter(number for ticket in start for number in ticket)
    for candidate in _space().candidates:
        for code in candidate.instantiation_codes:
            slotted = _replay(code)
            differing = [slot for slot in range(20) if slotted[slot] != start[slot]]
            assert len(differing) == 3
            assert set(differing) <= set(structure.twelve_slots)
            assert slotted[12:] == start[12:]
            assert all(len(set(ticket)) == 6 for ticket in slotted)
            assert len(set(slotted)) == 20
            assert Counter(number for ticket in slotted for number in ticket) == start_frequency
            for number, slots in structure.f2_supports:
                assert tuple(slot for slot in range(20) if number in slotted[slot]) == slots
            assert all(max(ticket) <= 26 for ticket in slotted[:12])
            assert tuple(sorted(slotted)) == candidate.portfolio != start
        assert search.portfolio_sha256(candidate.portfolio) == candidate.sha256


def test_ledger_is_complete_and_best_is_its_maximum() -> None:
    result = _result()
    candidates = _space().candidates
    ledger = cast(list[list[Any]], result["LEDGER"])

    assert result["LEDGER_SHA256"] == search.ledger_sha256(ledger)
    assert [row[0] for row in ledger] == list(range(len(candidates)))
    assert [row[1] for row in ledger] == [candidate.code for candidate in candidates]
    for row, candidate in zip(ledger, candidates, strict=True):
        assert row[4] == row[2] - 43 * row[3]
        assert row[5] == candidate.overlap.max_overlap
        assert tuple(row[6:]) == candidate.overlap.counts
    best_row = min(ledger, key=lambda row: (-row[2], candidates[int(row[0])].sha256))
    best = result["BEST"]
    assert best["UNIQUE_INDEX"] == best_row[0]
    assert best["OFFICIAL_ANY_PRIZE_OUTCOME_COUNT"] == best_row[2]
    assert best["NORMALIZED_SHA256"] == candidates[int(best_row[0])].sha256
    assert _tickets(best["TICKETS"]) == candidates[int(best_row[0])].portfolio
    counts = [row[2] for row in ledger]
    scores = result["SCORES"]
    assert scores["BEST_COUNT"] == max(counts)
    assert scores["BEST_DELTA"] == max(counts) - START_COUNT
    assert scores["ABOVE_BASELINE"] == sum(count > START_COUNT for count in counts)
    assert scores["EQUAL_BASELINE"] == sum(count == START_COUNT for count in counts)
    assert scores["BELOW_BASELINE"] == sum(count < START_COUNT for count in counts)
    gain = max(counts) > START_COUNT
    assert result["STRICT_GAIN"] == ("YES" if gain else "NO")
    assert result["READY_FOR_N1_ASCENT"] == ("YES" if gain else "NO")
    assert result["FAMILY_STATUS"] == (search.GAIN_STATUS if gain else search.NO_GAIN_STATUS)
    assert result["N2_EXECUTED"] == "NO"
    assert result["GLOBAL_K20_OPTIMUM_STATUS"] == "UNKNOWN"
    execution = result["EXECUTION"]
    assert execution["CHECKPOINT_ROWS_REUSED"] + execution[
        "CHECKPOINT_ROWS_SCORED_THIS_RUN"
    ] == len(candidates)


def test_best_and_sampled_rows_recount_canonically() -> None:
    result = _result()
    candidates = _space().candidates
    ledger = cast(list[list[Any]], result["LEDGER"])
    best = result["BEST"]

    fresh = evaluate_portfolio(_tickets(best["TICKETS"]))
    assert fresh.official_any_prize_outcome_count == best["OFFICIAL_ANY_PRIZE_OUTCOME_COUNT"]
    assert fresh.m3_plus_draw_count == best["M3_PLUS_DRAW_COUNT"]
    worst = min(ledger, key=lambda row: (row[2], row[0]))
    for row in (ledger[0], ledger[len(ledger) // 2], ledger[-1], worst):
        exact = evaluate_portfolio(candidates[int(row[0])].portfolio, draws=_draws())
        assert (exact.official_any_prize_outcome_count, exact.m3_plus_draw_count) == (
            row[2],
            row[3],
        )


def test_result_json_round_trips() -> None:
    text = RESULT_FILE.read_text(encoding="utf-8")
    assert search.render_json(json.loads(text)) + "\n" == text
