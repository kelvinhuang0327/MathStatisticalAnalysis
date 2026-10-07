"""Exhaustive twelve-side F3 three-ticket occurrence cycles from the F2-neutral K20 winner.

START is the N1-closed equal-score winner of the 12+8 component-internal F2 rewire
(``b649-k20-f2-rewire-winner-single-ticket-ascent-r1-result.json``, local commit 9c2258e0).
Every F2 support and the whole 8-ticket component stay frozen. For every unordered triple
``x < y < z`` of twelve-side frequency-3 numbers and every choice of one occurrence slot from
each support (``a`` for ``x``, ``b`` for ``y``, ``c`` for ``z``) both cycle directions are
generated:

* FORWARD: ``x: a -> b``, ``y: b -> c``, ``z: c -> a``;
* REVERSE: ``x: a -> c``, ``z: c -> b``, ``y: b -> a``.

Instantiations with repeated slots, a receiving ticket that already holds the moved number,
duplicate tickets, or a normalized portfolio equal to START are rejected. Every remaining
unique normalized portfolio is scored with the canonical exact evaluator over one shared
complete draw space. No sampling, proxy score, prefilter, or symmetry quotient is used.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import platform
import subprocess
import time
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from math import comb
from multiprocessing import get_context
from multiprocessing.shared_memory import SharedMemory
from pathlib import Path
from typing import cast

import numpy as np

from lottolab.research.b649_k20_12_8_component_internal_f2_rewire_r1 import (
    CandidateInvariantError,
    CheckpointIdentityError,
    ScoreCheckpoint,
    ScoreRow,
    StopError,
    file_sha256,
    ledger_sha256,
    normalize_portfolio,
    number_supports,
    portfolio_sha256,
    render_json,
    shared_draw_space,
    ticket_components,
)
from lottolab.research.b649_official_any_prize_exact import (
    BIG_LOTTO_DRAW_SIZE,
    BIG_LOTTO_POOL_SIZE,
    DrawMasks,
    evaluate_portfolio,
)

type Ticket = tuple[int, ...]
type Portfolio = tuple[Ticket, ...]
type Move = tuple[int, int, int]
type ScoreJob = tuple[int, str, Portfolio]
type ScoreReply = tuple[int, str, int, int]

TASK_ID = "B649_K20_F2_NEUTRAL_WINNER_12_SIDE_F3_THREE_TICKET_CYCLE_EXHAUSTIVE_R1"
SEARCH_DEFINITION_VERSION = "b649-k20-f2-neutral-12-side-f3-three-ticket-cycle-v1"
START_RESULT_PATH = (
    "docs/research/matrix-native-results/"
    "b649-k20-f2-rewire-winner-single-ticket-ascent-r1-result.json"
)
START_AUTHORITY_COMMIT = "9c2258e01ca7e22cbe34334a7131a078b5fa4fb8"
EXPECTED_START_TASK_ID = "B649_K20_F2_REWIRE_WINNER_SINGLE_TICKET_ASCENT_R1"
EXPECTED_START_COUNT = 313_263_888
EVALUATOR_PATH = "src/lottolab/research/b649_official_any_prize_exact.py"
RESULT_PATH = (
    "docs/research/matrix-native-results/b649-k20-f2-neutral-f3-three-ticket-cycle-r1-result.json"
)
SCORING_FUNCTION = "evaluate_portfolio(...).official_any_prize_outcome_count"
FAMILY = "TWELVE_SIDE_F3_THREE_TICKET_CYCLE"

TICKET_COUNT = 20
COMPONENT_SIZES = (12, 8)
EXPECTED_TWELVE_SIDE_F3_COUNT = 20
SPECIAL_COUNT = BIG_LOTTO_POOL_SIZE - BIG_LOTTO_DRAW_SIZE
MAX_WORKERS = 2
DIRECTIONS = ("FORWARD", "REVERSE")
SINGLE_TICKET_STATUS = "PROVEN_FOR_VALIDATED_EXACT_SINGLE_TICKET_NEIGHBORHOOD"
NO_GAIN_STATUS = "NO_STRICT_GAIN_FOR_DEFINED_12_SIDE_F3_THREE_TICKET_CYCLE_FAMILY"
GAIN_STATUS = "STRICT_GAIN_FOUND_IN_DEFINED_12_SIDE_F3_THREE_TICKET_CYCLE_FAMILY"
CLAIM_SCOPE = (
    "Exact for the defined twelve-side F3 three-ticket occurrence-cycle family of START only. "
    "Not a generic N3 closure, not an N2 result, and not a global K20 optimality claim."
)
REJECT_SLOT_COLLISION = "SLOT_COLLISION"
REJECT_RECEIVER_HOLDS_NUMBER = "RECEIVING_TICKET_ALREADY_HOLDS_NUMBER"
REJECT_DUPLICATE_TICKET = "DUPLICATE_TICKET"
REJECT_INERT = "INERT_EQUALS_START"
REJECTION_ORDER = (
    REJECT_SLOT_COLLISION,
    REJECT_RECEIVER_HOLDS_NUMBER,
    REJECT_DUPLICATE_TICKET,
    REJECT_INERT,
)
_PROGRESS_EVERY = 1000
_TOP_RECORDS = 10
_SLOT_DIGITS = "0123456789abcdefghijklmnopqrstuvwxyz"


class StartIdentityMismatchError(StopError):
    token = "START_IDENTITY_MISMATCH"


class StructureIdentityMismatchError(StopError):
    token = "START_STRUCTURE_IDENTITY_MISMATCH"


class ScoreCrossCheckError(StopError):
    token = "EXACT_SCORE_CROSSCHECK_MISMATCH"


# --- START authority ----------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Start:
    portfolio: Portfolio
    count: int
    sha256: str
    file_sha256: str
    single_ticket_status: str


def _portfolio_from_json(value: object) -> Portfolio:
    if not isinstance(value, list):
        raise StartIdentityMismatchError("FINAL.TICKETS is not a list")
    tickets: list[Ticket] = []
    for raw_ticket in cast(list[object], value):
        if not isinstance(raw_ticket, list):
            raise StartIdentityMismatchError("FINAL.TICKETS contains a non-list ticket")
        numbers = cast(list[object], raw_ticket)
        if any(type(number) is not int for number in numbers):
            raise StartIdentityMismatchError("FINAL.TICKETS contains a non-integer number")
        tickets.append(tuple(cast(list[int], numbers)))
    return tuple(tickets)


def load_start(repo_root: Path) -> Start:
    """Load the sealed N1 result and require its terminal identity; SHA comes from the file."""

    path = repo_root / START_RESULT_PATH
    data = cast(dict[str, object], json.loads(path.read_text(encoding="utf-8")))
    final = data.get("FINAL")
    if not isinstance(final, dict):
        raise StartIdentityMismatchError("sealed START result has no FINAL record")
    final_record = cast(dict[str, object], final)
    raw = _portfolio_from_json(final_record.get("TICKETS"))
    try:
        portfolio = normalize_portfolio(raw)
    except CandidateInvariantError as error:
        raise StartIdentityMismatchError(f"START portfolio is illegal: {error}") from error
    sealed_sha = final_record.get("NORMALIZED_SHA256")
    # The sealed result states single-ticket closure as LOCAL_OPTIMUM over one complete exact
    # N1 pass with no accepted move; that is the Packet's
    # SINGLE_TICKET_LOCAL_OPTIMUM_STATUS = PROVEN_FOR_VALIDATED_EXACT_SINGLE_TICKET_NEIGHBORHOOD.
    checks = {
        "TASK_ID": data.get("TASK_ID") == EXPECTED_START_TASK_ID,
        "TASK_STATUS": data.get("TASK_STATUS") == "COMPLETE",
        "FINAL_COUNT": final_record.get("OFFICIAL_ANY_PRIZE_OUTCOME_COUNT") == EXPECTED_START_COUNT,
        "FINAL_CANONICAL_RECOUNT": final_record.get("CANONICAL_RECOUNT") == "PASS",
        "LOCAL_OPTIMUM": data.get("LOCAL_OPTIMUM") is True,
        "ACCEPTED_MOVE_COUNT": data.get("ACCEPTED_MOVE_COUNT") == 0,
        "TERMINAL_BEST_DELTA": data.get("TERMINAL_BEST_DELTA") == 0,
        "FULL_PASSES": type(data.get("FULL_PASSES")) is int
        and cast(int, data.get("FULL_PASSES")) >= 1,
        "READY_FOR_TWO_TICKET_ASCENT": data.get("READY_FOR_TWO_TICKET_ASCENT") == "NO",
        "TICKET_COUNT": len(portfolio) == TICKET_COUNT,
        "NORMALIZED_ORDER": portfolio == raw,
        "SEALED_SHA_PRESENT": isinstance(sealed_sha, str) and len(sealed_sha) == 64,
        "RECOMPUTED_SHA256": portfolio_sha256(portfolio) == sealed_sha,
    }
    failed = sorted(name for name, passed in checks.items() if not passed)
    if failed:
        raise StartIdentityMismatchError(f"START checks failed: {failed}")
    return Start(
        portfolio=portfolio,
        count=EXPECTED_START_COUNT,
        sha256=cast(str, sealed_sha),
        file_sha256=file_sha256(path),
        single_ticket_status=SINGLE_TICKET_STATUS,
    )


def source_identity(repo_root: Path) -> dict[str, object]:
    """START file and evaluator are clean at HEAD and START is byte-identical to its commit."""

    def git(*arguments: str) -> str:
        completed = subprocess.run(
            ["git", "-C", str(repo_root), *arguments],
            check=True,
            capture_output=True,
            text=True,
        )
        return completed.stdout.strip()

    if git("status", "--porcelain", "--", START_RESULT_PATH, EVALUATOR_PATH):
        raise StartIdentityMismatchError("START result or evaluator differs from HEAD")
    ancestor = subprocess.run(
        [
            "git",
            "-C",
            str(repo_root),
            "merge-base",
            "--is-ancestor",
            START_AUTHORITY_COMMIT,
            "HEAD",
        ],
        check=False,
    )
    if ancestor.returncode != 0:
        raise StartIdentityMismatchError("START authority commit is not an ancestor of HEAD")
    head_blob = git("rev-parse", f"HEAD:{START_RESULT_PATH}")
    authority_blob = git("rev-parse", f"{START_AUTHORITY_COMMIT}:{START_RESULT_PATH}")
    if head_blob != authority_blob:
        raise StartIdentityMismatchError("START result differs from the authority commit")
    return {
        "SOURCE_HEAD": git("rev-parse", "HEAD"),
        "SOURCE_TREE": git("rev-parse", "HEAD^{tree}"),
        "START_AUTHORITY_COMMIT": START_AUTHORITY_COMMIT,
        "START_RESULT_BLOB": head_blob,
        "START_AND_EVALUATOR_CLEAN_AT_SOURCE_HEAD": True,
    }


# --- structure ----------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Structure:
    start: Portfolio
    twelve_slots: tuple[int, ...]
    eight_slots: tuple[int, ...]
    supports: Mapping[int, tuple[int, ...]]
    twelve_f3: tuple[int, ...]
    f2_supports: tuple[tuple[int, tuple[int, ...]], ...]

    @property
    def eight_tickets(self) -> tuple[Ticket, ...]:
        return tuple(sorted(self.start[slot] for slot in self.eight_slots))


def derive_structure(start: Portfolio) -> Structure:
    """Recompute the 12+8 components, twelve-side F3 numbers, and every F2 support."""

    supports = number_supports(start)
    components = ticket_components(start)
    if tuple(len(component) for component in components) != COMPONENT_SIZES:
        raise StructureIdentityMismatchError(
            f"component sizes {[len(component) for component in components]}"
        )
    twelve_slots, eight_slots = components
    twelve = set(twelve_slots)
    for number, slots in supports.items():
        sides = {slot in twelve for slot in slots}
        if len(sides) != 1:
            raise StructureIdentityMismatchError(f"number {number} crosses the 12/8 boundary")
        if len(slots) not in (2, 3):
            raise StructureIdentityMismatchError(f"number {number} has frequency {len(slots)}")
    twelve_f3 = tuple(
        number for number, slots in supports.items() if len(slots) == 3 and set(slots) <= twelve
    )
    if len(twelve_f3) != EXPECTED_TWELVE_SIDE_F3_COUNT:
        raise StructureIdentityMismatchError(f"{len(twelve_f3)} twelve-side F3 numbers")
    f2_supports = tuple((number, slots) for number, slots in supports.items() if len(slots) == 2)
    return Structure(
        start=start,
        twelve_slots=twelve_slots,
        eight_slots=eight_slots,
        supports=supports,
        twelve_f3=twelve_f3,
        f2_supports=f2_supports,
    )


# --- operator and candidate invariants ----------------------------------------------------


def cycle_moves(
    numbers: tuple[int, int, int], slots: tuple[int, int, int], direction: str
) -> tuple[Move, Move, Move]:
    """``(number, from_slot, to_slot)`` for one cycle direction of ``x, y, z`` at ``a, b, c``."""

    (x, y, z), (a, b, c) = numbers, slots
    if direction == "FORWARD":
        return ((x, a, b), (y, b, c), (z, c, a))
    if direction == "REVERSE":
        return ((x, a, c), (z, c, b), (y, b, a))
    raise ValueError(f"unknown direction {direction}")


def apply_moves(start: Portfolio, moves: Sequence[Move]) -> tuple[Portfolio | None, str | None]:
    """Slot-ordered candidate, or the rejection reason that makes the instantiation illegal."""

    if len({source for _, source, _ in moves}) != len(moves):
        return None, REJECT_SLOT_COLLISION
    tickets = [set(ticket) for ticket in start]
    for number, source, _ in moves:
        if number not in tickets[source]:
            raise CandidateInvariantError(f"number {number} is not on slot {source}")
        tickets[source].discard(number)
    for number, _, target in moves:
        if number in tickets[target]:
            return None, REJECT_RECEIVER_HOLDS_NUMBER
        tickets[target].add(number)
    return tuple(tuple(sorted(ticket)) for ticket in tickets), None


def instantiation_code(
    numbers: tuple[int, int, int], slots: tuple[int, int, int], direction: str
) -> str:
    """``x-y-z@abc:F`` with one base-36 digit per slot; F is FORWARD and R is REVERSE."""

    slot_code = "".join(_SLOT_DIGITS[slot] for slot in slots)
    return f"{numbers[0]}-{numbers[1]}-{numbers[2]}@{slot_code}:{direction[0]}"


@dataclass(frozen=True, slots=True)
class OverlapHistogram:
    counts: tuple[int, ...]

    @property
    def max_overlap(self) -> int:
        return max(overlap for overlap, count in enumerate(self.counts) if count)

    def as_dict(self) -> dict[str, int]:
        return {str(overlap): count for overlap, count in enumerate(self.counts)}


def overlap_histogram(portfolio: Sequence[Sequence[int]]) -> OverlapHistogram:
    """Exact count of ticket pairs at each overlap 0..5."""

    sets = [frozenset(ticket) for ticket in portfolio]
    counts = [0] * BIG_LOTTO_DRAW_SIZE
    for first, second in itertools.combinations(sets, 2):
        counts[len(first & second)] += 1
    return OverlapHistogram(tuple(counts))


def check_candidate(structure: Structure, slotted: Portfolio) -> Portfolio:
    """Assert every Packet candidate invariant and return the normalized portfolio."""

    start = structure.start
    differing = [slot for slot in range(TICKET_COUNT) if slotted[slot] != start[slot]]
    if len(differing) != 3:
        raise CandidateInvariantError(f"{len(differing)} ticket slots differ from START")
    if not set(differing) <= set(structure.twelve_slots):
        raise CandidateInvariantError("a differing slot lies outside the twelve-side component")
    normalized = normalize_portfolio(slotted)
    if len(normalized) != TICKET_COUNT:
        raise CandidateInvariantError("candidate does not have 20 tickets")
    supports = number_supports(slotted)
    if set(supports) != set(structure.supports):
        raise CandidateInvariantError("candidate uses a different number set")
    for number, slots in structure.supports.items():
        if len(supports[number]) != len(slots):
            raise CandidateInvariantError(f"frequency of {number} changed")
    for number, slots in structure.f2_supports:
        if supports[number] != slots:
            raise CandidateInvariantError(f"F2 support of {number} changed")
    twelve = set(structure.twelve_slots)
    for number, slots in supports.items():
        if {slot in twelve for slot in slots} != {structure.supports[number][0] in twelve}:
            raise CandidateInvariantError(f"number {number} crosses the 12/8 boundary")
    eight = tuple(sorted(slotted[slot] for slot in structure.eight_slots))
    if eight != structure.eight_tickets:
        raise CandidateInvariantError("the 8-ticket component changed")
    if normalized == start:
        raise CandidateInvariantError("candidate equals START")
    return normalized


# --- enumeration --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Candidate:
    """One unique normalized portfolio; ``code`` is its first raw instantiation."""

    index: int
    code: str
    instantiation_codes: tuple[str, ...]
    portfolio: Portfolio
    sha256: str
    overlap: OverlapHistogram


@dataclass(frozen=True, slots=True)
class Space:
    raw_closed_form: int
    raw_enumerated: int
    rejections: Mapping[str, int]
    legal: int
    candidates: tuple[Candidate, ...]

    @property
    def duplicate_legal(self) -> int:
        return self.legal - len(self.candidates)


def enumerate_space(structure: Structure) -> Space:
    """Every raw instantiation in (triple, slot product, direction) order, then dedupe."""

    f3 = structure.twelve_f3
    raw_closed_form = comb(len(f3), 3) * 3**3 * len(DIRECTIONS)
    rejections: dict[str, int] = dict.fromkeys(REJECTION_ORDER, 0)
    by_portfolio: dict[Portfolio, list[str]] = {}
    raw = 0
    legal = 0
    for numbers in itertools.combinations(f3, 3):
        for slots in itertools.product(*(structure.supports[number] for number in numbers)):
            slot_triple = cast(tuple[int, int, int], slots)
            for direction in DIRECTIONS:
                raw += 1
                moves = cycle_moves(numbers, slot_triple, direction)
                slotted, reason = apply_moves(structure.start, moves)
                if slotted is None:
                    rejections[cast(str, reason)] += 1
                    continue
                if len(set(slotted)) != TICKET_COUNT:
                    rejections[REJECT_DUPLICATE_TICKET] += 1
                    continue
                if tuple(sorted(slotted)) == structure.start:
                    rejections[REJECT_INERT] += 1
                    continue
                normalized = check_candidate(structure, slotted)
                legal += 1
                code = instantiation_code(numbers, slot_triple, direction)
                by_portfolio.setdefault(normalized, []).append(code)
    if raw != raw_closed_form:
        raise StructureIdentityMismatchError(f"enumerated {raw} != closed form {raw_closed_form}")
    if raw - sum(rejections.values()) != legal:
        raise StructureIdentityMismatchError("raw/rejected/legal accounting does not balance")
    candidates = tuple(
        Candidate(
            index=index,
            code=codes[0],
            instantiation_codes=tuple(codes),
            portfolio=portfolio,
            sha256=portfolio_sha256(portfolio),
            overlap=overlap_histogram(portfolio),
        )
        for index, (portfolio, codes) in enumerate(by_portfolio.items())
    )
    return Space(raw_closed_form, raw, rejections, legal, candidates)


# --- protected parallel scoring -----------------------------------------------------------


@dataclass(slots=True)
class _WorkerContext:
    memory: SharedMemory
    draws: DrawMasks


_worker_context: _WorkerContext | None = None


def _init_worker(memory_name: str, draw_count: int) -> None:
    global _worker_context
    memory = SharedMemory(name=memory_name, track=False)
    buffer = memory.buf
    if buffer is None:
        raise RuntimeError("shared draw-space buffer is unavailable")
    draws: DrawMasks = np.frombuffer(buffer, dtype=np.uint64, count=draw_count)
    _worker_context = _WorkerContext(memory, draws)


def _score_job(job: ScoreJob) -> ScoreReply:
    if _worker_context is None:
        raise RuntimeError("worker draw space is not attached")
    index, code, portfolio = job
    exact = evaluate_portfolio(portfolio, draws=_worker_context.draws)
    return index, code, exact.official_any_prize_outcome_count, exact.m3_plus_draw_count


def _score_pending(
    pending: Sequence[ScoreJob],
    *,
    memory_name: str,
    workers: int,
    checkpoint: ScoreCheckpoint,
    completed: dict[tuple[str, int], ScoreRow],
) -> int:
    if not pending:
        return 0
    started = time.monotonic()
    scored = 0
    draw_count = comb(BIG_LOTTO_POOL_SIZE, BIG_LOTTO_DRAW_SIZE)
    with get_context("spawn").Pool(
        processes=workers, initializer=_init_worker, initargs=(memory_name, draw_count)
    ) as pool:
        for index, code, count, m3_plus in pool.imap_unordered(_score_job, pending, chunksize=4):
            row = ScoreRow(FAMILY, index, code, count, m3_plus)
            checkpoint.append(row)
            completed[(FAMILY, index)] = row
            scored += 1
            if scored % _PROGRESS_EVERY == 0 or scored == len(pending):
                elapsed = time.monotonic() - started
                print(f"[{elapsed:.0f}s] scored {scored}/{len(pending)} pending", flush=True)
    checkpoint.sync()
    return scored


# --- result assembly ----------------------------------------------------------------------


def candidate_record(candidate: Candidate, row: ScoreRow, baseline_count: int) -> dict[str, object]:
    return {
        "UNIQUE_INDEX": candidate.index,
        "CODE": candidate.code,
        "INSTANTIATION_CODES": list(candidate.instantiation_codes),
        "OFFICIAL_ANY_PRIZE_OUTCOME_COUNT": row.count,
        "DELTA_VS_BASELINE": row.count - baseline_count,
        "M3_PLUS_DRAW_COUNT": row.m3_plus,
        "SPECIAL_RESCUE_OUTCOMES": row.count - SPECIAL_COUNT * row.m3_plus,
        "MAX_TICKET_PAIR_OVERLAP": candidate.overlap.max_overlap,
        "PAIR_OVERLAP_HISTOGRAM": candidate.overlap.as_dict(),
        "NORMALIZED_SHA256": candidate.sha256,
        "TICKETS": [list(ticket) for ticket in candidate.portfolio],
    }


def rank_key(candidate: Candidate, rows: Mapping[int, ScoreRow]) -> tuple[int, str]:
    """Maximum exact count first, then ascending normalized SHA-256."""

    return (-rows[candidate.index].count, candidate.sha256)


def ledger_rows(
    candidates: Sequence[Candidate], rows: Mapping[int, ScoreRow]
) -> list[list[object]]:
    return [
        [
            candidate.index,
            candidate.code,
            rows[candidate.index].count,
            rows[candidate.index].m3_plus,
            rows[candidate.index].count - SPECIAL_COUNT * rows[candidate.index].m3_plus,
            candidate.overlap.max_overlap,
            *candidate.overlap.counts,
        ]
        for candidate in candidates
    ]


def structure_section(structure: Structure) -> dict[str, object]:
    return {
        "STATUS": "PASS",
        "COMPONENT_SIZES": [len(structure.twelve_slots), len(structure.eight_slots)],
        "TWELVE_SIDE_SLOTS": list(structure.twelve_slots),
        "EIGHT_SIDE_SLOTS": list(structure.eight_slots),
        "SLOT_CONVENTION": "index into the normalized START ticket order",
        "TWELVE_SIDE_F3_COUNT": len(structure.twelve_f3),
        "TWELVE_SIDE_F3_SUPPORTS": {
            str(number): list(structure.supports[number]) for number in structure.twelve_f3
        },
        "F2_SUPPORTS_FROZEN": {str(number): list(slots) for number, slots in structure.f2_supports},
        "EIGHT_SIDE_TICKETS_FROZEN": [list(ticket) for ticket in structure.eight_tickets],
    }


def run(
    repo_root: Path, checkpoint_dir: Path, workers: int, execution_id: str
) -> dict[str, object]:
    if not 1 <= workers <= MAX_WORKERS:
        raise ValueError(f"workers must be within 1..{MAX_WORKERS}")
    started = time.monotonic()
    output = repo_root / RESULT_PATH
    if output.exists():
        raise FileExistsError(f"{output} exists; refusing to overwrite a result")
    start = load_start(repo_root)
    source = source_identity(repo_root)
    evaluator_sha256 = file_sha256(repo_root / EVALUATOR_PATH)
    structure = derive_structure(start.portfolio)
    space = enumerate_space(structure)
    candidates = space.candidates
    print(
        f"f3={len(structure.twelve_f3)} raw={space.raw_enumerated} legal={space.legal} "
        f"unique={len(candidates)} rejections={dict(space.rejections)}",
        flush=True,
    )
    jobs: list[ScoreJob] = [
        (candidate.index, candidate.code, candidate.portfolio) for candidate in candidates
    ]
    expected_codes = {(FAMILY, candidate.index): candidate.code for candidate in candidates}

    with shared_draw_space() as (memory, draws):
        draw_space_sha256 = hashlib.sha256(draws.tobytes()).hexdigest()
        start_exact = evaluate_portfolio(start.portfolio, draws=draws)
        del draws
        if start_exact.official_any_prize_outcome_count != start.count:
            raise StartIdentityMismatchError(
                f"canonical rescore {start_exact.official_any_prize_outcome_count} != {start.count}"
            )
        jobs_digest = ledger_sha256(
            [[candidate.index, candidate.code, candidate.sha256] for candidate in candidates]
        )
        checkpoint = ScoreCheckpoint(
            checkpoint_dir / "f3-cycle-scores.jsonl",
            {
                "task_id": TASK_ID,
                "search_definition_version": SEARCH_DEFINITION_VERSION,
                "start_sha256": start.sha256,
                "start_file_sha256": start.file_sha256,
                "evaluator_sha256": evaluator_sha256,
                "draw_space_sha256": draw_space_sha256,
                "jobs_sha256": jobs_digest,
            },
        )
        completed = checkpoint.load()
        for key, row in completed.items():
            if expected_codes.get(key) != row.code:
                raise CheckpointIdentityError(f"checkpoint row {key} is not a job of this search")
        reused = len(completed)
        pending = [job for job in jobs if (FAMILY, job[0]) not in completed]
        print(f"jobs={len(jobs)} reused={reused} pending={len(pending)}", flush=True)
        scored = _score_pending(
            pending,
            memory_name=memory.name,
            workers=workers,
            checkpoint=checkpoint,
            completed=completed,
        )
    if set(completed) != set(expected_codes):
        raise CheckpointIdentityError("scored rows do not cover every job exactly")

    baseline_count = start.count
    rows = {index: row for (_, index), row in completed.items()}
    ranked = sorted(candidates, key=lambda candidate: rank_key(candidate, rows))
    best = ranked[0]
    best_record = candidate_record(best, rows[best.index], baseline_count)
    fresh = evaluate_portfolio(best.portfolio)
    if (fresh.official_any_prize_outcome_count, fresh.m3_plus_draw_count) != (
        rows[best.index].count,
        rows[best.index].m3_plus,
    ):
        raise ScoreCrossCheckError("best candidate fresh canonical recount disagrees")
    best_count = rows[best.index].count
    strict_gain = best_count > baseline_count
    counts = [rows[candidate.index].count for candidate in candidates]
    max_overlaps = Counter(candidate.overlap.max_overlap for candidate in candidates)
    by_direction: dict[str, dict[str, int]] = {}
    for direction in DIRECTIONS:
        members = [
            rows[candidate.index].count
            for candidate in candidates
            if candidate.code.endswith(f":{direction[0]}")
        ]
        by_direction[direction] = {
            "CANDIDATES": len(members),
            "BEST_COUNT": max(members),
            "BEST_DELTA": max(members) - baseline_count,
        }
    equal = [candidate for candidate in ranked if rows[candidate.index].count == baseline_count]
    start_profile = overlap_histogram(start.portfolio)
    ledger = ledger_rows(candidates, rows)

    result: dict[str, object] = {
        "SCHEMA_VERSION": 1,
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "COMPLETE",
        "SEARCH_DEFINITION_VERSION": SEARCH_DEFINITION_VERSION,
        "SOURCE_AUTHORITY": {
            **source,
            "START_RESULT_PATH": START_RESULT_PATH,
            "START_RESULT_FILE_SHA256": start.file_sha256,
            "START_TASK_ID": EXPECTED_START_TASK_ID,
            "START_COUNT": start.count,
            "START_SHA256": start.sha256,
            "START_SINGLE_TICKET_LOCAL_OPTIMUM_STATUS": start.single_ticket_status,
            "START_SINGLE_TICKET_STATUS_EVIDENCE": (
                "sealed LOCAL_OPTIMUM=true, ACCEPTED_MOVE_COUNT=0, TERMINAL_BEST_DELTA=0, "
                "FULL_PASSES>=1, FINAL.CANONICAL_RECOUNT=PASS"
            ),
            "START_READY_FOR_TWO_TICKET_ASCENT": "NO",
            "EVALUATOR_PATH": EVALUATOR_PATH,
            "EVALUATOR_SHA256": evaluator_sha256,
            "SCORING_FUNCTION": SCORING_FUNCTION,
        },
        "DRAW_SPACE": {
            "MAIN_DRAW_COUNT": start_exact.main_draw_count,
            "SPECIAL_COUNT": start_exact.special_count,
            "TOTAL_OUTCOMES": start_exact.main_draw_count * start_exact.special_count,
            "SHA256": draw_space_sha256,
            "CONSTRUCTION": "all_main_draw_masks(49, 6) once, shared read-only by every worker",
        },
        "START": {
            "OFFICIAL_ANY_PRIZE_OUTCOME_COUNT": baseline_count,
            "NORMALIZED_SHA256": start.sha256,
            "M3_PLUS_DRAW_COUNT": start_exact.m3_plus_draw_count,
            "SPECIAL_RESCUE_OUTCOMES": baseline_count
            - SPECIAL_COUNT * start_exact.m3_plus_draw_count,
            "CANONICAL_RESCORE": "PASS",
            "MAX_TICKET_PAIR_OVERLAP": start_profile.max_overlap,
            "PAIR_OVERLAP_HISTOGRAM": start_profile.as_dict(),
            "TICKETS": [list(ticket) for ticket in start.portfolio],
        },
        "STRUCTURE": structure_section(structure),
        "OPERATOR": {
            "TRIPLES": "every unordered x < y < z of twelve-side F3 numbers",
            "SLOTS": "a in SUPPORT(x), b in SUPPORT(y), c in SUPPORT(z), ascending products",
            "FORWARD": "x: a -> b, y: b -> c, z: c -> a",
            "REVERSE": "x: a -> c, z: c -> b, y: b -> a",
            "CODE_CONVENTION": "x-y-z@abc:D, one base-36 digit per slot, D in {F, R}",
            "SYMMETRY_QUOTIENT": "NOT_USED; every legal unique candidate is scored",
            "PAIRWISE_OVERLAP_LE_1_REQUIRED": False,
        },
        "ENUMERATION": {
            "RAW_CLOSED_FORM": "C(20,3) * 3^3 * 2",
            "RAW_CLOSED_FORM_VALUE": space.raw_closed_form,
            "RAW_OPERATOR_INSTANTIATIONS": space.raw_enumerated,
            "REJECTIONS": dict(space.rejections),
            "LEGAL_CANDIDATES": space.legal,
            "UNIQUE_NORMALIZED_CANDIDATES": len(candidates),
            "DUPLICATE_LEGAL_INSTANTIATIONS": space.duplicate_legal,
            "SCORED": len(completed),
        },
        "CANDIDATE_INVARIANTS": {
            "STATUS": "PASS",
            "CHECKED_LEGAL_INSTANTIATIONS": space.legal,
            "INVARIANTS": [
                "exactly three ticket slots differ from START, all twelve-side",
                "20 legal distinct tickets of six distinct numbers",
                "every number frequency unchanged",
                "every F2 support unchanged slot for slot",
                "no number crosses the 12/8 component boundary",
                "8-ticket component equal up to canonical ticket ordering",
                "normalized portfolio differs from START",
            ],
        },
        "SCORES": {
            "BEST_COUNT": best_count,
            "BEST_DELTA": best_count - baseline_count,
            "BEST_SHA256": best.sha256,
            "BEST_TIE_COUNT": counts.count(best_count),
            "TIE_BREAK": "maximum exact count, then ascending normalized SHA-256",
            "WORST_COUNT": min(counts),
            "ABOVE_BASELINE": sum(1 for count in counts if count > baseline_count),
            "EQUAL_BASELINE": len(equal),
            "BELOW_BASELINE": sum(1 for count in counts if count < baseline_count),
            "BY_DIRECTION_OF_FIRST_INSTANTIATION": by_direction,
            "MAX_TICKET_PAIR_OVERLAP_DISTRIBUTION": {
                str(overlap): max_overlaps[overlap] for overlap in sorted(max_overlaps)
            },
            "EQUAL_BASELINE_CANDIDATES": [
                [candidate.code, candidate.sha256] for candidate in equal
            ],
            "TOP": [
                candidate_record(candidate, rows[candidate.index], baseline_count)
                for candidate in ranked[:_TOP_RECORDS]
            ],
        },
        "BEST": best_record,
        "BEST_FRESH_RECOUNT": {
            "STATUS": "PASS",
            "OFFICIAL_ANY_PRIZE_OUTCOME_COUNT": fresh.official_any_prize_outcome_count,
            "M3_PLUS_DRAW_COUNT": fresh.m3_plus_draw_count,
            "DRAW_SPACE": "freshly constructed by evaluate_portfolio(draws=None)",
        },
        "STRICT_GAIN": "YES" if strict_gain else "NO",
        "FAMILY_STATUS": GAIN_STATUS if strict_gain else NO_GAIN_STATUS,
        "READY_FOR_N1_ASCENT": "YES" if strict_gain else "NO",
        "N1_EXECUTED": "NO",
        "N2_EXECUTED": "NO",
        "CLAIM_SCOPE": CLAIM_SCOPE,
        "EXECUTION": {
            "EXECUTION_ID": execution_id,
            "WORKERS": workers,
            "PYTHON": platform.python_version(),
            "NUMPY": np.__version__,
            "DRIVER_SHA256": file_sha256(Path(__file__)),
            "CHECKPOINT_FILE": str(checkpoint.path),
            "CHECKPOINT_ROWS_REUSED": reused,
            "CHECKPOINT_ROWS_SCORED_THIS_RUN": scored,
            "WALL_SECONDS_THIS_RUN": round(time.monotonic() - started),
        },
        "PUSH": "NOT RUN",
        "PR": "NOT CREATED",
        "PRODUCTION_MUTATION": "NONE",
        "GLOBAL_K20_OPTIMUM_STATUS": "UNKNOWN",
        "LEDGER_COLUMNS": [
            "UNIQUE_INDEX",
            "CODE",
            "OFFICIAL_ANY_PRIZE_OUTCOME_COUNT",
            "M3_PLUS_DRAW_COUNT",
            "SPECIAL_RESCUE_OUTCOMES",
            "MAX_TICKET_PAIR_OVERLAP",
            *(f"PAIRS_AT_OVERLAP_{overlap}" for overlap in range(BIG_LOTTO_DRAW_SIZE)),
        ],
        "LEDGER_SHA256": ledger_sha256(ledger),
        "LEDGER": ledger,
    }
    text = render_json(result) + "\n"
    if json.loads(text) != result:
        raise RuntimeError("result JSON does not round-trip")
    output.write_text(text, encoding="utf-8")
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="B649 K20 twelve-side F3 three-ticket cycles")
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--checkpoint-dir", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=MAX_WORKERS)
    parser.add_argument("--execution-id", default="")
    args = parser.parse_args(argv)
    try:
        result = run(
            Path(args.repo_root).resolve(),
            Path(args.checkpoint_dir).resolve(),
            int(args.workers),
            str(args.execution_id),
        )
    except StopError as error:
        print(error, flush=True)
        return 3
    enumeration = cast(dict[str, object], result["ENUMERATION"])
    best = cast(dict[str, object], result["BEST"])
    for label, value in (
        ("RAW_OPERATOR_INSTANTIATIONS", enumeration["RAW_OPERATOR_INSTANTIATIONS"]),
        ("LEGAL_CANDIDATES", enumeration["LEGAL_CANDIDATES"]),
        ("UNIQUE_NORMALIZED_CANDIDATES", enumeration["UNIQUE_NORMALIZED_CANDIDATES"]),
        ("BEST_EXACT_COUNT", best["OFFICIAL_ANY_PRIZE_OUTCOME_COUNT"]),
        ("BEST_DELTA", best["DELTA_VS_BASELINE"]),
        ("BEST_NORMALIZED_SHA", best["NORMALIZED_SHA256"]),
        ("STRICT_GAIN", result["STRICT_GAIN"]),
        ("FAMILY_STATUS", result["FAMILY_STATUS"]),
    ):
        print(f"{label}: {value}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
