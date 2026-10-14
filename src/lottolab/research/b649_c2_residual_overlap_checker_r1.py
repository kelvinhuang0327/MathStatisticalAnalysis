"""Decide residual overlap for fixed R, X, Y; never classify gain or ties.

In the unmutated sealed donor, ``overlap_R`` (tbr_engine.c:439) counts
7-sets W with |W & X| >= 3, |W & Y| >= 3 and |W & r| <= 2 for every r in R.
The Mobius coefficients (1, -3, 6, -10) give the threshold indicator:
sum(c(j) * C(h, j), j=3..h) is 0 for h<3 and 1 for h=3..6.
``a_R_at`` counts uncovered extensions, including its COVERED7 0/1 case.
Thus the double sum counts each doubly covered residual W once (no factor 7).
Donor SHA256: ed7c88467a56648c6587aadbbce6b23bc419c9218f840405238019ac7286d4fa.
Source characterization only: executing donor modes would compute forbidden
gain quantities and/or build tables; this module never executes the donor.

Coverage proof: choose any threshold-sized A inside W & X and B inside W & Y.
Their union S is an enumerated seed, and W is one of its enumerated extensions.
Equal unions have exactly the same extension family; removing duplicate unions
does not remove any W. Families of different seeds may overlap: repeated full
sets count against the budget, so no unbounded full-set cache is needed.

Only prune: if S already meets an r in at least threshold numbers, every
superset W also does. Every other seed enumerates ALL combinations in U minus S
of size draw_size minus |S|. Zero requires every family to be pruned or exhausted.
A budget exit leaves an explicit prefix and never constitutes a zero proof.

Defaults are exactly B649 K20 (49, 6, 7, 3, 18). Smaller explicit parameters
support exhaustive toy verification; they do not certify a real K20 instance.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from itertools import combinations
from math import comb
from typing import Literal

Ticket = tuple[int, ...]


@dataclass(frozen=True)
class Parameters:
    universe_size: int = 49
    ticket_size: int = 6
    draw_size: int = 7
    threshold: int = 3
    untouched_count: int = 18

    def __post_init__(self) -> None:
        values = (
            self.universe_size,
            self.ticket_size,
            self.draw_size,
            self.threshold,
            self.untouched_count,
        )
        if any(type(v) is not int for v in values):
            raise ValueError("parameters must be integers (not bool)")
        if not 1 <= self.universe_size <= 49:
            raise ValueError("universe_size must be in 1..49")
        if not 1 <= self.ticket_size <= min(6, self.universe_size):
            raise ValueError("ticket_size must be in 1..min(6, universe_size)")
        if not 1 <= self.threshold <= self.ticket_size:
            raise ValueError("threshold must be in 1..ticket_size")
        if not self.threshold <= self.draw_size <= self.universe_size:
            raise ValueError("draw_size must be in threshold..universe_size")
        if not 0 <= self.untouched_count <= 18:
            raise ValueError("untouched_count must be in 0..18")


K20_PARAMETERS = Parameters()


class Status(StrEnum):
    OVERLAP_POSITIVE = "OVERLAP_POSITIVE"
    OVERLAP_ZERO_PROVEN = "OVERLAP_ZERO_PROVEN"
    UNKNOWN_BUDGET = "UNKNOWN_BUDGET"


@dataclass(frozen=True)
class SeedProgress:
    seed: Ticket
    total_extensions: int
    checked_extensions: int
    state: Literal["PRUNED_R", "EXHAUSTED", "PARTIAL", "WITNESS"]


@dataclass(frozen=True)
class WitnessReplay:
    legal_draw: bool
    hits_x: bool
    hits_y: bool
    uncovered_by_r: bool

    @property
    def valid(self) -> bool:
        return self.legal_draw and self.hits_x and self.hits_y and self.uncovered_by_r


@dataclass(frozen=True)
class OverlapResult:
    status: Status
    witness: Ticket | None
    replay: WitnessReplay | None
    raw_seed_pairs: int
    unique_seeds: int
    full_sets_checked: int
    progress: tuple[SeedProgress, ...]
    # For UNKNOWN, restart the deterministic family at this zero-based ordinal.
    # This is an audit cursor, not an unchecked resume input.
    next_seed_index: int | None = None
    next_extension_index: int | None = None

    def __bool__(self) -> bool:
        raise TypeError("inspect status explicitly; UNKNOWN_BUDGET is not a zero decision")


def _is_sequence(values: object) -> bool:
    # Validate untyped callers at runtime without treating type hints as checks.
    return isinstance(values, Sequence)


def _ticket(values: Sequence[int], p: Parameters, label: str) -> Ticket:
    if not _is_sequence(values) or len(values) != p.ticket_size:
        raise ValueError(f"{label} must contain exactly {p.ticket_size} numbers")
    if any(type(n) is not int or not 1 <= n <= p.universe_size for n in values):
        raise ValueError(f"{label} numbers must be integers in 1..{p.universe_size}")
    if len(set(values)) != p.ticket_size:
        raise ValueError(f"{label} contains duplicate numbers")
    return tuple(sorted(values))


def _inputs(
    r: Sequence[Sequence[int]],
    x: Sequence[int],
    y: Sequence[int],
    p: Parameters,
) -> tuple[tuple[Ticket, ...], Ticket, Ticket]:
    if not _is_sequence(r) or len(r) != p.untouched_count:
        raise ValueError(f"R must contain exactly {p.untouched_count} untouched tickets")
    xn, yn = _ticket(x, p, "X"), _ticket(y, p, "Y")
    rn = tuple(_ticket(t, p, f"R[{i}]") for i, t in enumerate(r))
    if len(set((*rn, xn, yn))) != len(rn) + 2:
        raise ValueError("R, X and Y must be distinct tickets (no duplicate tickets)")
    return rn, xn, yn


def seed_unions(
    x: Sequence[int],
    y: Sequence[int],
    *,
    parameters: Parameters = K20_PARAMETERS,
) -> tuple[Ticket, ...]:
    """Return sorted unique unions of all threshold-subset pairs (<=400 pairs)."""
    xn, yn = _ticket(x, parameters, "X"), _ticket(y, parameters, "Y")
    if xn == yn:
        raise ValueError("X and Y must be distinct tickets")
    return tuple(
        sorted(
            {
                tuple(sorted(set(a) | set(b)))
                for a in combinations(xn, parameters.threshold)
                for b in combinations(yn, parameters.threshold)
            }
        )
    )


def replay_witness(
    r: Sequence[Sequence[int]],
    x: Sequence[int],
    y: Sequence[int],
    witness: Sequence[int],
    *,
    parameters: Parameters = K20_PARAMETERS,
) -> WitnessReplay:
    """Independent direct set checker: no seeds, masks, pruning, or search calls.

    Malformed instance inputs raise ValueError; a malformed witness fails replay.
    The four booleans describe draw legality, X hits, Y hits, and every R ticket.
    """
    rn, xn, yn = _inputs(r, x, y, parameters)
    if not _is_sequence(witness) or any(
        type(n) is not int or not 1 <= n <= parameters.universe_size for n in witness
    ):
        return WitnessReplay(False, False, False, False)
    w = set(witness)
    return WitnessReplay(
        len(witness) == len(w) == parameters.draw_size,
        len(w & set(xn)) >= parameters.threshold,
        len(w & set(yn)) >= parameters.threshold,
        all(len(w & set(t)) < parameters.threshold for t in rn),
    )


def _mask(values: Sequence[int]) -> int:
    return sum(1 << (n - 1) for n in values)


def check_residual_overlap(
    r: Sequence[Sequence[int]],
    x: Sequence[int],
    y: Sequence[int],
    *,
    max_full_sets: int = 20_000,
    parameters: Parameters = K20_PARAMETERS,
) -> OverlapResult:
    """Search only extensions of fixed X/Y seeds, using complete R ticket masks.

    max_full_sets caps candidate validations, including repetitions across seeds.
    Replay of a positive witness is an additional direct check of that same W.
    Progress records every completed family and, on exit, the partial family.
    Structural seed exclusions remain permissible with a zero validation budget.
    """
    if type(max_full_sets) is not int or not 0 <= max_full_sets <= 20_000:
        raise ValueError("max_full_sets must be an integer in 0..20000 (not bool)")
    rn, xn, yn = _inputs(r, x, y, parameters)
    seeds = seed_unions(xn, yn, parameters=parameters)
    r_masks, xm, ym = tuple(_mask(t) for t in rn), _mask(xn), _mask(yn)
    raw_pairs = comb(parameters.ticket_size, parameters.threshold) ** 2
    progress: list[SeedProgress] = []
    checked = 0
    for i, seed in enumerate(seeds):
        sm = _mask(seed)
        needed = parameters.draw_size - len(seed)
        total = comb(parameters.universe_size - len(seed), needed) if needed >= 0 else 0
        if any((sm & rm).bit_count() >= parameters.threshold for rm in r_masks):
            progress.append(SeedProgress(seed, total, 0, "PRUNED_R"))
            continue
        if total == 0:
            # Empty family: the seed is too large to fit in a draw.
            progress.append(SeedProgress(seed, 0, 0, "EXHAUSTED"))
            continue
        outside = tuple(n for n in range(1, parameters.universe_size + 1) if n not in seed)
        family_checked = 0
        for extra in combinations(outside, needed):
            if checked == max_full_sets:
                progress.append(SeedProgress(seed, total, family_checked, "PARTIAL"))
                return OverlapResult(
                    Status.UNKNOWN_BUDGET,
                    None,
                    None,
                    raw_pairs,
                    len(seeds),
                    checked,
                    tuple(progress),
                    i,
                    family_checked,
                )
            wm = sm | _mask(extra)
            checked += 1
            family_checked += 1
            if (
                wm.bit_count() == parameters.draw_size
                and (wm & xm).bit_count() >= parameters.threshold
                and (wm & ym).bit_count() >= parameters.threshold
                and all((wm & rm).bit_count() < parameters.threshold for rm in r_masks)
            ):
                witness = tuple(sorted((*seed, *extra)))
                replay = replay_witness(rn, xn, yn, witness, parameters=parameters)
                if not replay.valid:
                    raise RuntimeError("search witness failed independent set replay")
                progress.append(SeedProgress(seed, total, family_checked, "WITNESS"))
                return OverlapResult(
                    Status.OVERLAP_POSITIVE,
                    witness,
                    replay,
                    raw_pairs,
                    len(seeds),
                    checked,
                    tuple(progress),
                )
        progress.append(SeedProgress(seed, total, family_checked, "EXHAUSTED"))
    return OverlapResult(
        Status.OVERLAP_ZERO_PROVEN,
        None,
        None,
        raw_pairs,
        len(seeds),
        checked,
        tuple(progress),
    )
