"""Isomorphism-cover certificate for the complete 112728-portfolio HHL augment family.

Claim: every legal distinct portfolio of the HHL single-augment family has a known exact
OFFICIAL_ANY_PRIZE outcome count; the family maximum is 313032783 (delta -231105 against
the 313263888 baseline) and no member strictly beats the baseline.

Proof shape:

1. The family is regenerated here from the pinned baseline by its fixed rule and must
   reproduce the producer's pinned count, rejection accounting and ordered-keys SHA256,
   plus the key and portfolio identity of every ledger row.
2. Anchors are exact integer counts: the 10240 rows of the two pinned formal ledgers (read,
   never rescored) and, for every representative that had no ledger row, one count from
   the pinned official evaluator.
3. The cover names, for every candidate, a representative anchor and an explicit
   permutation of 1..49 that maps the candidate's 20 tickets, as number sets, exactly onto
   the representative's 20 tickets. A number permutation maps the official outcome space
   (main draw D, special s not in D) bijectively onto itself and preserves every ticket/draw
   intersection, so the exact count carries over unchanged.

Only the explicit maps are evidence. No hash, invariant or WL refinement is consulted.
``build`` writes the certificate. ``verify`` replays it in a fresh process: it regenerates
the family and anchors itself, checks every map and rescores only the new anchors.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import itertools
import json
import os
import resource
import subprocess
import sys
import time
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import numpy as np
import numpy.typing as npt

from lottolab.research import b649_official_any_prize_exact as official

type Ticket = tuple[int, ...]
type Portfolio = tuple[Ticket, ...]
type Key = tuple[int, ...]
type MaskMatrix = npt.NDArray[np.uint64]
type IntArray = npt.NDArray[np.int64]
type TableArray = npt.NDArray[np.uint64]

TASK_ID = "B649_K20_HHL_FULL_FAMILY_PROOF_FORMALIZATION_R1"
CERTIFICATE_SCHEMA = "B649_K20_HHL_FAMILY_ISOMORPHISM_COVER_V1"
SCIENTIFIC_AUTHORITY = "PENDING_FRESH_JUDGE"

SOURCE_HEAD = "fc7d61b48bfdcfe16e65d30a5f983fd04a31b705"
SOURCE_TREE = "8e821acb434c6d85578ed77ca5fb0a741a0b28c5"
BASELINE_GIT_BLOB = "404e35563564a40bdd228dafa25fdf5b82e45812"
BASELINE_SHA256 = "eaed652900d101881b678a1515d2a366bff9de6723dbec2ec9c82fe0d0d7844c"
BASELINE_EXACT_COUNT = 313_263_888
EVALUATOR_RELATIVE_PATH = "src/lottolab/research/b649_official_any_prize_exact.py"
EVALUATOR_SHA256 = "92dcb836254cc6dbcd6c2ad907e619a5eb8cf3917197a8f6de3e5f989825cf66"
CERTIFICATE_RELATIVE_PATH = (
    "docs/research/matrix-native-results/b649-k20-hhl-full-family-isomorphism-cover-r1.json.gz"
)

POOL_SIZE = official.BIG_LOTTO_POOL_SIZE
DRAW_SIZE = official.BIG_LOTTO_DRAW_SIZE
SPECIALS_PER_MAIN_DRAW = POOL_SIZE - DRAW_SIZE
MAIN_DRAW_COUNT = 13_983_816
TOTAL_OFFICIAL_OUTCOMES = MAIN_DRAW_COUNT * SPECIALS_PER_MAIN_DRAW
MASK_BYTES = 7

H_INDICES: tuple[int, ...] = tuple(range(12))
L_INDICES: tuple[int, ...] = tuple(range(12, 20))
H_NUMBERS: frozenset[int] = frozenset(range(1, 27))
L_NUMBERS: frozenset[int] = frozenset(range(27, 50))

BASELINE_TICKETS: Portfolio = (
    (1, 2, 3, 4, 5, 21),
    (1, 6, 7, 8, 9, 22),
    (1, 11, 14, 18, 19, 26),
    (2, 7, 14, 16, 17, 24),
    (2, 10, 11, 12, 13, 22),
    (3, 6, 10, 14, 15, 23),
    (3, 8, 13, 17, 20, 26),
    (4, 6, 12, 19, 20, 24),
    (4, 8, 10, 16, 18, 25),
    (5, 7, 11, 15, 20, 25),
    (5, 9, 12, 17, 18, 23),
    (9, 13, 15, 16, 19, 21),
    (27, 29, 30, 31, 32, 33),
    (27, 34, 35, 36, 37, 38),
    (27, 39, 40, 41, 42, 43),
    (28, 29, 34, 39, 44, 45),
    (28, 30, 35, 40, 46, 47),
    (28, 31, 36, 41, 48, 49),
    (32, 37, 42, 44, 46, 48),
    (33, 38, 43, 45, 47, 49),
)

GENERATION_RULE = (
    "Seed cycle over i<j in H tickets 0..11, k in L tickets 12..19, x in T[i], y in T[j], "
    "z in T[k] (each ascending) and d in (0,1): d=0 moves y->T[i], z->T[j], x->T[k]; d=1 "
    "moves z->T[i], x->T[j], y->T[k], each replacing the ticket's own x/y/z. Augment: out = "
    "smallest original T[i] number still in F[i], then new = 1..49 not already in F[i] "
    "replaces out in F[i]. A seed and its augment are kept only if exactly tickets i, j, k "
    "differ from the baseline, each has six distinct numbers, the 20 tickets are distinct and "
    "every touching pair shares at most one number; the first occurrence of each normalized "
    "portfolio is kept. Key [i,j,k,x,y,z,d,out,new]; family index = order of keeping."
)
EXPECTED_FAMILY_STATS: dict[str, Any] = {
    "RAW_SEED_SPECS": 228_096,
    "LEGAL_SEED_CYCLES": 5760,
    "SEED_REJECTION_REASONS": {
        "CHANGED_TICKETS_NOT_EXACTLY_THREE": 6336,
        "PAIR_OVERLAP_ABOVE_ONE": 184_320,
        "TICKET_NOT_SIX_DISTINCT_LEGAL_NUMBERS": 31_680,
    },
    "RAW_AUGMENT_SPECS": 282_240,
    "AUGMENT_REJECTION_REASONS": {
        "NEW_ALREADY_IN_TARGET_TICKET": 34_560,
        "PAIR_OVERLAP_ABOVE_ONE": 134_952,
    },
    "DUPLICATE_PORTFOLIOS": 0,
    "LEGAL_UNIQUE_PORTFOLIOS": 112_728,
    "ORDERED_KEYS_SHA256": "d7f8ca3c5e4dbe13465ca28a22769ea0fbb84ab811043a9e287ce756d4346369",
}
EXPECTED_FAMILY_MAXIMUM = 313_032_783
EXPECTED_STRICT_GAIN_COUNT = 0

LEDGER_FIELD = "SAMPLE_SCORES"
LEDGER_COLUMNS = (
    "SAMPLE_INDEX",
    "FAMILY_INDEX",
    "I",
    "J",
    "K",
    "X",
    "Y",
    "Z",
    "D",
    "OUT",
    "NEW",
    "SAMPLE_RANK",
    "PORTFOLIO_SHA256",
    "EXACT_COUNT",
    "DELTA",
    "M3_PLUS_DRAW_COUNT",
    "RESCUED_SPECIAL_COUNT",
)
NEW_ANCHOR_SOURCE = 2
ANCHOR_COLUMNS = (
    "FAMILY_INDEX",
    "EXACT_COUNT",
    "M3_PLUS_DRAW_COUNT",
    "RESCUED_SPECIAL_COUNT",
    "SOURCE",
)


@dataclass(frozen=True, slots=True)
class SourceResult:
    """One pinned formal result whose score ledger supplies exact anchors."""

    source: int
    role: str
    path: Path
    sha256: str
    ledger_sha256: str
    rows: int


_WORKTREES = Path("/Users/kelvin/VibeCoding-WorkSpace/.worktrees/MathStatisticalAnalysis")
SOURCE_RESULTS: tuple[SourceResult, ...] = (
    SourceResult(
        0,
        "B649_K20_HHL_AUGMENT_SINGLE_SAMPLE8192_R1",
        _WORKTREES
        / "B649_K20_HHL_AUGMENT_SINGLE_SAMPLE8192_R1/.task-data"
        / "B649_K20_HHL_AUGMENT_SINGLE_SAMPLE8192_R1/hhl-augment-single-sample8192-r1-result.json",
        "7869772466bdc8ddb6428dee68b4a7f04e5d11e7c99d49aeaf405b417fa80eb9",
        "2107b2a81c2834f079fdffe19b28208d2f8b4f2e875624ccdd7f622bc5d9e7c1",
        8192,
    ),
    SourceResult(
        1,
        "B649_K20_HHL_GUIDED_RESIDUAL_EXACT2048_R1",
        _WORKTREES
        / "B649_K20_HHL_GUIDED_RESIDUAL_EXACT2048_R1/.task-data"
        / "B649_K20_HHL_GUIDED_RESIDUAL_EXACT2048_R1/hhl-guided-residual-exact2048-r1-result.json",
        "939bc98ee032bc58a8b9da2710b75578c1c299397aab6112c1eef1eb062abac3",
        "056b118b89a5444ab5b97f349e66cac9441b69554d300c8a99d28d6f5dea60db",
        2048,
    ),
)


def compact_json(value: object) -> str:
    return json.dumps(value, separators=(",", ":"), ensure_ascii=True)


def compact_json_sha256(value: object) -> str:
    return hashlib.sha256(compact_json(value).encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ticket_mask(ticket: Sequence[int]) -> int:
    mask = 0
    for number in ticket:
        mask |= 1 << (number - 1)
    return mask


def mask_numbers(mask: int) -> Ticket:
    return tuple(number for number in range(1, POOL_SIZE + 1) if mask >> (number - 1) & 1)


def normalize_portfolio(portfolio: Sequence[Sequence[int]]) -> list[list[int]]:
    """Each ticket ascending, tickets in lexicographic order."""

    return sorted(sorted(ticket) for ticket in portfolio)


def portfolio_sha256(portfolio: Sequence[Sequence[int]]) -> str:
    return compact_json_sha256(normalize_portfolio(portfolio))


def _git(checkout: Path, *arguments: str) -> bytes:
    return subprocess.run(
        ["git", "-C", str(checkout), *arguments], check=True, capture_output=True
    ).stdout


def load_baseline(checkout: Path) -> Portfolio:
    """Read the pinned baseline Git blob and check every pinned identity."""

    content = _git(checkout, "cat-file", "blob", BASELINE_GIT_BLOB)
    header = f"blob {len(content)}\0".encode("ascii")
    if hashlib.sha1(header + content).hexdigest() != BASELINE_GIT_BLOB:
        raise ValueError("baseline blob does not hash to its Git object id")
    payload = cast(dict[str, Any], json.loads(content))
    tickets: Portfolio = tuple(tuple(t) for t in cast(list[list[int]], payload["FINAL_TICKETS"]))
    if tickets != BASELINE_TICKETS:
        raise ValueError("baseline FINAL_TICKETS differ from the pinned index order")
    if payload["FINAL_COUNT"] != BASELINE_EXACT_COUNT:
        raise ValueError("baseline FINAL_COUNT differs from the pinned exact count")
    if portfolio_sha256(tickets) != BASELINE_SHA256:
        raise ValueError("baseline normalized SHA256 differs from the pinned identity")
    return tickets


def baseline_violation(baseline: Portfolio) -> str | None:
    """First failed fixed-baseline structure condition, else ``None``."""

    if len(baseline) != len(H_INDICES) + len(L_INDICES):
        return "BASELINE_NOT_20_TICKETS"
    for ticket in baseline:
        if len(ticket) != DRAW_SIZE or len(set(ticket)) != DRAW_SIZE:
            return "BASELINE_TICKET_NOT_SIX_DISTINCT_NUMBERS"
    if not all(set(baseline[index]) <= H_NUMBERS for index in H_INDICES):
        return "H_TICKET_OUTSIDE_1_26"
    if not all(set(baseline[index]) <= L_NUMBERS for index in L_INDICES):
        return "L_TICKET_OUTSIDE_27_49"
    if len({frozenset(ticket) for ticket in baseline}) != len(baseline):
        return "BASELINE_DUPLICATE_TICKET"
    if any(len(set(a) & set(b)) > 1 for a, b in itertools.combinations(baseline, 2)):
        return "BASELINE_PAIR_OVERLAP_ABOVE_ONE"
    return None


def move_violation(
    base: Sequence[int], masks: Sequence[int], changed: tuple[int, int, int]
) -> str | None:
    """First failed structure condition of a three-ticket move, else ``None``.

    Checked in this order: exactly the ``changed`` tickets differ from the baseline, each
    has six numbers, no ticket repeats, and every pair touching a changed ticket shares at
    most one number. Untouched pairs are baseline pairs, cleared by ``baseline_violation``;
    ``structure_recheck`` later re-checks all 190 pairs of every kept portfolio.
    """

    differing = {
        index for index, (old, new) in enumerate(zip(base, masks, strict=True)) if old != new
    }
    if differing != set(changed):
        return "CHANGED_TICKETS_NOT_EXACTLY_THREE"
    if any(masks[index].bit_count() != DRAW_SIZE for index in changed):
        return "TICKET_NOT_SIX_DISTINCT_LEGAL_NUMBERS"
    others = range(len(masks))
    for index in changed:
        if any(other != index and masks[other] == masks[index] for other in others):
            return "DUPLICATE_TICKET"
    for index in changed:
        if any(
            other != index and (masks[other] & masks[index]).bit_count() > 1 for other in others
        ):
            return "PAIR_OVERLAP_ABOVE_ONE"
    return None


@dataclass(frozen=True, slots=True)
class Family:
    """Kept candidates in family-index order; mask columns keep the baseline ticket order."""

    keys: tuple[Key, ...]
    masks: MaskMatrix
    stats: dict[str, Any]

    def tickets(self, index: int) -> Portfolio:
        return tuple(mask_numbers(int(mask)) for mask in self.masks[index])


def _swap(mask: int, out: int, into: int) -> int:
    return (mask & ~(1 << (out - 1))) | (1 << (into - 1))


def generate_family(baseline: Portfolio) -> Family:
    """Every seed spec and augmentation of ``GENERATION_RULE`` in its fixed order."""

    violation = baseline_violation(baseline)
    if violation is not None:
        raise ValueError(f"baseline structure violation: {violation}")
    base = [ticket_mask(ticket) for ticket in baseline]
    raw_seed = 0
    seed_reasons: Counter[str] = Counter()
    seeds: list[tuple[Key, list[int]]] = []
    for i, j in itertools.combinations(H_INDICES, 2):
        for k in L_INDICES:
            for x, y, z in itertools.product(
                sorted(baseline[i]), sorted(baseline[j]), sorted(baseline[k])
            ):
                for d in (0, 1):
                    raw_seed += 1
                    into_i, into_j, into_k = (y, z, x) if d == 0 else (z, x, y)
                    masks = list(base)
                    masks[i] = _swap(base[i], x, into_i)
                    masks[j] = _swap(base[j], y, into_j)
                    masks[k] = _swap(base[k], z, into_k)
                    reason = move_violation(base, masks, (i, j, k))
                    if reason is not None:
                        seed_reasons[reason] += 1
                        continue
                    seeds.append(((i, j, k, x, y, z, d), masks))

    raw_augment = 0
    augment_reasons: Counter[str] = Counter()
    seen: set[tuple[int, ...]] = set()
    keys: list[Key] = []
    rows: list[list[int]] = []
    for seed_key, seeded in seeds:
        i, j, k = seed_key[:3]
        retained = base[i] & seeded[i]
        if retained == 0:
            raise ValueError(f"seed {seed_key} keeps no original number of T[{i}]")
        out = (retained & -retained).bit_length()
        for new in range(1, POOL_SIZE + 1):
            raw_augment += 1
            if seeded[i] >> (new - 1) & 1:
                augment_reasons["NEW_ALREADY_IN_TARGET_TICKET"] += 1
                continue
            masks = list(seeded)
            masks[i] = _swap(seeded[i], out, new)
            reason = move_violation(base, masks, (i, j, k))
            if reason is not None:
                augment_reasons[reason] += 1
                continue
            identity = tuple(sorted(masks))
            if identity in seen:
                augment_reasons["DUPLICATE_NORMALIZED_PORTFOLIO"] += 1
                continue
            seen.add(identity)
            keys.append((*seed_key, out, new))
            rows.append(masks)
    stats: dict[str, Any] = {
        "RAW_SEED_SPECS": raw_seed,
        "LEGAL_SEED_CYCLES": len(seeds),
        "SEED_REJECTION_REASONS": dict(sorted(seed_reasons.items())),
        "RAW_AUGMENT_SPECS": raw_augment,
        "AUGMENT_REJECTION_REASONS": dict(sorted(augment_reasons.items())),
        "DUPLICATE_PORTFOLIOS": augment_reasons["DUPLICATE_NORMALIZED_PORTFOLIO"],
        "LEGAL_UNIQUE_PORTFOLIOS": len(keys),
        "ORDERED_KEYS_SHA256": compact_json_sha256([list(key) for key in keys]),
    }
    return Family(tuple(keys), np.array(rows, dtype=np.uint64), stats)


def structure_recheck(family: Family, baseline: Portfolio) -> dict[str, int]:
    """Re-check every kept portfolio over all 190 ticket pairs; reason -> count."""

    masks = family.masks
    base = np.array([ticket_mask(ticket) for ticket in baseline], dtype=np.uint64)
    expected_changed = np.zeros(masks.shape, dtype=np.bool_)
    for row, key in enumerate(family.keys):
        expected_changed[row, list(key[:3])] = True
    changed_ok = np.all((masks != base[np.newaxis, :]) == expected_changed, axis=1)
    legal_ok = np.all(np.bitwise_count(masks) == DRAW_SIZE, axis=1) & np.all(
        masks < np.uint64(1 << POOL_SIZE), axis=1
    )
    distinct_ok = np.ones(len(masks), dtype=np.bool_)
    overlap_ok = np.ones(len(masks), dtype=np.bool_)
    for first, second in itertools.combinations(range(masks.shape[1]), 2):
        distinct_ok &= masks[:, first] != masks[:, second]
        overlap_ok &= np.bitwise_count(masks[:, first] & masks[:, second]) <= 1
    reasons: Counter[str] = Counter()
    for row in range(len(masks)):
        if not changed_ok[row]:
            reasons["CHANGED_TICKETS_NOT_EXACTLY_THREE"] += 1
        elif not legal_ok[row]:
            reasons["TICKET_NOT_SIX_DISTINCT_LEGAL_NUMBERS"] += 1
        elif not distinct_ok[row]:
            reasons["DUPLICATE_TICKET"] += 1
        elif not overlap_ok[row]:
            reasons["PAIR_OVERLAP_ABOVE_ONE"] += 1
        else:
            reasons["OK"] += 1
    return dict(sorted(reasons.items()))


def family_portfolio_sha256s(family: Family) -> list[str]:
    """Normalized portfolio SHA256 of every candidate, in family-index order."""

    decoded: dict[int, Ticket] = {}
    digests: list[str] = []
    for row in family.masks.tolist():
        tickets = [decoded.setdefault(mask, mask_numbers(mask)) for mask in row]
        digests.append(portfolio_sha256(tickets))
    return digests


def checked_family(baseline: Portfolio) -> tuple[Family, list[str], dict[str, Any]]:
    """Generate the family and require the producer's pinned accounting and legality."""

    family = generate_family(baseline)
    if family.stats != EXPECTED_FAMILY_STATS:
        raise ValueError(f"family accounting differs from the pinned producer: {family.stats}")
    recheck = structure_recheck(family, baseline)
    if recheck != {"OK": len(family.keys)}:
        raise ValueError(f"family structure recheck failed: {recheck}")
    digests = family_portfolio_sha256s(family)
    if len(set(digests)) != len(digests):
        raise ValueError("family portfolios are not pairwise distinct")
    record: dict[str, Any] = {
        **family.stats,
        "GENERATION_RULE": GENERATION_RULE,
        "KEY_FORMAT": "[i,j,k,x,y,z,d,out,new]",
        "FIRST_KEY": list(family.keys[0]),
        "LAST_KEY": list(family.keys[-1]),
        "FULL_STRUCTURE_RECHECK": recheck,
        "ORDERED_PORTFOLIO_SHA256_DIGEST": compact_json_sha256(digests),
    }
    return family, digests, record


@dataclass(frozen=True, slots=True)
class Anchor:
    """One exact OFFICIAL_ANY_PRIZE count tied to a family index."""

    family_index: int
    exact_count: int
    m3_plus_draw_count: int
    rescued_special_count: int
    source: int

    def row(self) -> list[int]:
        return [
            self.family_index,
            self.exact_count,
            self.m3_plus_draw_count,
            self.rescued_special_count,
            self.source,
        ]


def exact_fields_ok(count: int, m3_plus: int, rescued: int) -> bool:
    """Integer accounting of one exact count inside the official outcome space."""

    return (
        0 <= m3_plus <= MAIN_DRAW_COUNT
        and 0 <= rescued <= (MAIN_DRAW_COUNT - m3_plus) * SPECIALS_PER_MAIN_DRAW
        and count == SPECIALS_PER_MAIN_DRAW * m3_plus + rescued
    )


def ledger_anchors(
    family: Family, digests: Sequence[str], source: SourceResult, path: Path
) -> tuple[list[Anchor], dict[str, Any]]:
    """Anchors of one pinned ledger, every row tied to the regenerated family (read only)."""

    if file_sha256(path) != source.sha256:
        raise ValueError(f"{source.role}: result SHA256 differs from the pinned identity")
    payload = cast(dict[str, Any], json.loads(path.read_bytes()))
    identity = cast(dict[str, Any], payload["SOURCE_IDENTITY"])
    if (
        identity["BASELINE_SHA256"] != BASELINE_SHA256
        or identity["EVALUATOR_SHA256"] != EVALUATOR_SHA256
    ):
        raise ValueError(f"{source.role}: baseline or evaluator identity differs")
    if payload["SCORE_LEDGER_COLUMNS"] != list(LEDGER_COLUMNS):
        raise ValueError(f"{source.role}: ledger schema differs")
    rows = cast(list[list[Any]], payload[LEDGER_FIELD])
    if (
        len(rows) != source.rows
        or payload["SAMPLES_EXACT_SCORED"] != source.rows
        or payload["SCORE_LEDGER_SHA256"] != source.ledger_sha256
        or compact_json_sha256(rows) != source.ledger_sha256
    ):
        raise ValueError(f"{source.role}: ledger length or digest differs")
    anchors: list[Anchor] = []
    for position, row in enumerate(rows):
        index = row[1]
        if row[0] != position or type(index) is not int or not 0 <= index < len(family.keys):
            raise ValueError(f"{source.role}: ledger row {position} has a bad index")
        if row[2:11] != list(family.keys[index]) or row[12] != digests[index]:
            raise ValueError(f"{source.role}: row {position} differs from family index {index}")
        count, delta, m3_plus, rescued = row[13:17]
        if not all(type(value) is int for value in (count, delta, m3_plus, rescued)):
            raise ValueError(f"{source.role}: row {position} exact fields are not integers")
        if delta != count - BASELINE_EXACT_COUNT or not exact_fields_ok(count, m3_plus, rescued):
            raise ValueError(f"{source.role}: row {position} exact accounting fails")
        anchors.append(Anchor(index, count, m3_plus, rescued, source.source))
    if len({anchor.family_index for anchor in anchors}) != len(anchors):
        raise ValueError(f"{source.role}: ledger repeats a family index")
    record: dict[str, Any] = {
        "SOURCE": source.source,
        "ROLE": source.role,
        "PATH": str(path),
        "SHA256": source.sha256,
        "SCORE_LEDGER_SHA256": source.ledger_sha256,
        "ROWS": source.rows,
    }
    return anchors, record


def original_anchors(
    family: Family, digests: Sequence[str], paths: Sequence[Path]
) -> tuple[dict[int, Anchor], list[dict[str, Any]]]:
    """All pinned ledger anchors; the two ledgers must be disjoint."""

    anchors: dict[int, Anchor] = {}
    records: list[dict[str, Any]] = []
    for source, path in zip(SOURCE_RESULTS, paths, strict=True):
        rows, record = ledger_anchors(family, digests, source, path)
        for anchor in rows:
            if anchor.family_index in anchors:
                raise ValueError(f"family index {anchor.family_index} is in two ledgers")
            anchors[anchor.family_index] = anchor
        records.append(record)
    return anchors, records


def require_permutations(perms: IntArray) -> None:
    """Every row must be a bijection of 1..49."""

    if perms.ndim != 2 or perms.shape[1] != POOL_SIZE or perms.shape[0] < 1:
        raise ValueError(f"permutation table has shape {perms.shape}")
    identity = np.arange(1, POOL_SIZE + 1, dtype=np.int64)
    if not np.all(np.sort(perms, axis=1) == identity[np.newaxis, :]):
        raise ValueError("a permutation row is not a bijection of 1..49")


def permutation_tables(perms: IntArray) -> TableArray:
    """``tables[p, b, v]``: image under ``perms[p]`` of the numbers set in mask byte ``b``."""

    require_permutations(perms)
    tables = np.zeros((perms.shape[0], MASK_BYTES, 256), dtype=np.uint64)
    values = np.arange(256, dtype=np.int64)
    for number in range(1, POOL_SIZE + 1):
        byte, bit = divmod(number - 1, 8)
        images = np.left_shift(np.uint64(1), (perms[:, number - 1] - 1).astype(np.uint64))
        holds = (values >> bit) & 1 == 1
        tables[:, byte, holds] |= images[:, np.newaxis]
    return tables


def apply_permutations(masks: MaskMatrix, tables: TableArray, which: IntArray) -> MaskMatrix:
    """Row ``r`` of ``masks`` relabelled ticket by ticket by permutation ``which[r]``."""

    image = np.zeros_like(masks)
    rows = which[:, np.newaxis]
    for byte in range(MASK_BYTES):
        values = ((masks >> np.uint64(8 * byte)) & np.uint64(0xFF)).astype(np.intp)
        image |= tables[rows, byte, values]
    return image


def relabel(portfolio: Sequence[Sequence[int]], perm: Sequence[int]) -> list[list[int]]:
    """Reference relabelling: ``perm[n - 1]`` is the image of number ``n``."""

    return normalize_portfolio([[perm[number - 1] for number in ticket] for ticket in portfolio])


def block_automorphisms(baseline: Portfolio, block: Sequence[int]) -> list[dict[int, int]]:
    """Number relabellings induced by line-preserving ticket permutations of one block.

    A line is the set of block tickets holding a number. Exhaustive backtracking over
    ticket images; each full assignment that maps the line set onto itself induces the
    relabelling number -> number of the image line.
    """

    numbers = sorted({number for ticket in block for number in baseline[ticket]})
    lines = {n: frozenset(t for t in block if n in baseline[t]) for n in numbers}
    line_set = set(lines.values())
    if len(line_set) != len(lines):
        raise ValueError("two numbers of the block lie on the same ticket set")
    number_of = {line: number for number, line in lines.items()}
    order = list(block)
    found: list[dict[int, int]] = []

    def extend(assign: dict[int, int]) -> None:
        if len(assign) == len(order):
            images = {line: frozenset(assign[t] for t in line) for line in line_set}
            if set(images.values()) == line_set:
                found.append({n: number_of[images[line]] for n, line in lines.items()})
            return
        ticket = order[len(assign)]
        used = set(assign.values())
        for target in order:
            if target in used:
                continue
            assign[ticket] = target
            if all(
                frozenset(assign[t] for t in line) in line_set
                for line in line_set
                if ticket in line and all(t in assign for t in line)
            ):
                extend(assign)
            del assign[ticket]

    extend({})
    return found


def baseline_automorphisms(baseline: Portfolio) -> IntArray:
    """Aut(H block) x Aut(L block) as rows of images of 1..49, identity first."""

    rows: list[list[int]] = []
    for h_map, l_map in itertools.product(
        block_automorphisms(baseline, H_INDICES), block_automorphisms(baseline, L_INDICES)
    ):
        combined = {**h_map, **l_map}
        rows.append([combined[number] for number in range(1, POOL_SIZE + 1)])
    rows.sort()
    perms = np.array(rows, dtype=np.int64)
    require_permutations(perms)
    base = sorted(ticket_mask(ticket) for ticket in baseline)
    for row in rows:
        if sorted(ticket_mask(t) for t in relabel(baseline, row)) != base:
            raise ValueError("a block automorphism does not fix the baseline")
    if rows[0] != list(range(1, POOL_SIZE + 1)):
        raise ValueError("identity is missing from the automorphism group")
    return perms


def orbit_cover(
    family: Family, perms: IntArray, anchors: Mapping[int, Anchor]
) -> tuple[IntArray, IntArray]:
    """Builder: representative and permutation index for every candidate.

    A candidate's canonical form is the lexicographically smallest sorted mask row over
    all permutations. Candidates sharing it share one representative: the smallest
    anchored family index, else the smallest index. The stored map for candidate ``c`` is
    ``g_r^-1 o g_c``, where ``g_c`` and ``g_r`` send ``c`` and its representative to the
    canonical form; it must itself be a row of ``perms``.
    """

    if perms[0].tolist() != list(range(1, POOL_SIZE + 1)):
        raise ValueError("permutation row 0 must be the identity")
    tables = permutation_tables(perms)
    count = len(family.keys)
    best = np.sort(family.masks, axis=1)
    best_perm = np.zeros(count, dtype=np.int64)
    for p in range(1, perms.shape[0]):
        which = np.full(count, p, dtype=np.int64)
        image = np.sort(apply_permutations(family.masks, tables, which), axis=1)
        differs = image != best
        rows = np.nonzero(differs.any(axis=1))[0]
        first = differs[rows].argmax(axis=1)
        smaller = rows[image[rows, first] < best[rows, first]]
        best[smaller] = image[smaller]
        best_perm[smaller] = p
    groups: dict[bytes, list[int]] = {}
    for index in range(count):
        groups.setdefault(best[index].tobytes(), []).append(index)
    representative = np.empty(count, dtype=np.int64)
    for members in groups.values():
        anchored = [index for index in members if index in anchors]
        representative[members] = min(anchored) if anchored else min(members)
    inverse = np.empty_like(perms)
    inverse[np.arange(perms.shape[0])[:, np.newaxis], perms - 1] = np.arange(1, POOL_SIZE + 1)
    index_of = {tuple(row): p for p, row in enumerate(perms.tolist())}
    composed: dict[tuple[int, int], int] = {}
    permutation = np.empty(count, dtype=np.int64)
    for index in range(count):
        pair = (int(best_perm[index]), int(best_perm[representative[index]]))
        if pair not in composed:
            row = tuple(inverse[pair[1]][perms[pair[0]] - 1].tolist())
            if row not in index_of:
                raise ValueError("permutation rows are not closed under composition")
            composed[pair] = index_of[row]
        permutation[index] = composed[pair]
    return representative, permutation


def verify_cover(
    masks: MaskMatrix,
    perms: IntArray,
    representative: IntArray,
    permutation: IntArray,
    anchors: Mapping[int, Anchor],
) -> tuple[IntArray, dict[str, int]]:
    """Check every explicit map and return the exact count of every candidate.

    For candidate ``c`` the 20 tickets relabelled by ``perms[permutation[c]]`` must equal,
    as a set of number sets, the 20 tickets of ``representative[c]``, which must carry an
    exact anchor. An anchored candidate must agree with its representative's count.
    """

    count = masks.shape[0]
    if representative.shape != (count,) or permutation.shape != (count,):
        raise ValueError("cover arrays do not have one entry per candidate")
    if np.any((representative < 0) | (representative >= count)):
        raise ValueError("a representative index is outside the family")
    if np.any((permutation < 0) | (permutation >= perms.shape[0])):
        raise ValueError("a permutation index is outside the permutation table")
    anchor_count = np.full(count, -1, dtype=np.int64)
    for anchor in anchors.values():
        anchor_count[anchor.family_index] = anchor.exact_count
    if np.any(anchor_count[representative] < 0):
        raise ValueError("a representative has no exact anchor")
    tables = permutation_tables(perms)
    image = np.sort(apply_permutations(masks, tables, permutation), axis=1)
    target = np.sort(masks[representative], axis=1)
    failed = np.nonzero(np.any(image != target, axis=1))[0]
    if failed.size:
        raise ValueError(f"{failed.size} maps fail; first family index {int(failed[0])}")
    counts = anchor_count[representative]
    anchored = np.nonzero(anchor_count >= 0)[0]
    conflicts = anchored[counts[anchored] != anchor_count[anchored]]
    if conflicts.size:
        raise ValueError(f"{conflicts.size} anchors disagree with their representative")
    own = np.arange(count, dtype=np.int64)
    stats = {
        "MAPS_CHECKED": count,
        "MAPS_TO_ANOTHER_PORTFOLIO": int(np.count_nonzero(representative != own)),
        "MAP_FAILURES": 0,
        "ANCHORS_CHECKED_AGAINST_REPRESENTATIVE": int(
            np.count_nonzero(representative[anchored] != anchored)
        ),
        "ANCHOR_CONFLICTS": 0,
    }
    return counts, stats


def require_evaluator(checkout: Path) -> str:
    """The imported official evaluator must be this checkout's SHA-pinned file."""

    path = (checkout / EVALUATOR_RELATIVE_PATH).resolve()
    if Path(official.__file__).resolve() != path:
        raise ValueError(f"official evaluator resolved outside this checkout: {official.__file__}")
    if file_sha256(path) != EVALUATOR_SHA256:
        raise ValueError("official evaluator SHA256 differs from the pinned identity")
    return EVALUATOR_SHA256


def score_portfolios(
    checkout: Path, family: Family, indices: Sequence[int], source: int
) -> list[Anchor]:
    """Exact counts from the pinned official evaluator over the full outcome space."""

    require_evaluator(checkout)
    draws = official.all_main_draw_masks(POOL_SIZE, DRAW_SIZE)
    anchors: list[Anchor] = []
    for index in indices:
        result = official.evaluate_portfolio(family.tickets(index), draws=draws)
        count = result.official_any_prize_outcome_count
        m3_plus = result.m3_plus_draw_count
        anchors.append(
            Anchor(index, count, m3_plus, count - SPECIALS_PER_MAIN_DRAW * m3_plus, source)
        )
    return anchors


def family_claims(
    family: Family, counts: IntArray, anchors: Mapping[int, Anchor], representative: IntArray
) -> dict[str, Any]:
    maximum = int(counts.max())
    at_maximum = np.nonzero(counts == maximum)[0].tolist()
    new = sum(1 for anchor in anchors.values() if anchor.source == NEW_ANCHOR_SOURCE)
    return {
        "FAMILY_PORTFOLIOS": len(family.keys),
        "ORIGINAL_EXACT_SCORED": len(anchors) - new,
        "NEW_EXACT_SCORED": new,
        "ISOMORPHISM_COVERED": len(family.keys) - len(anchors),
        "UNRESOLVED_PORTFOLIOS": int(np.count_nonzero(counts < 0)),
        "REPRESENTATIVES": len(set(representative.tolist())),
        "FAMILY_MAXIMUM_EXACT_COUNT": maximum,
        "FAMILY_MAXIMUM_DELTA": maximum - BASELINE_EXACT_COUNT,
        "MAXIMUM_TIE_COUNT": len(at_maximum),
        "MAXIMUM_FAMILY_INDICES": at_maximum,
        "MAXIMUM_KEYS": [list(family.keys[index]) for index in at_maximum],
        "STRICT_GAIN_COUNT": int(np.count_nonzero(counts > BASELINE_EXACT_COUNT)),
        "BASELINE_TIE_COUNT": int(np.count_nonzero(counts == BASELINE_EXACT_COUNT)),
        "FAMILY_MINIMUM_EXACT_COUNT": int(counts.min()),
        "EXACT_COUNTS_SHA256": compact_json_sha256(counts.tolist()),
    }


THREAD_ENV = ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS")
INVARIANCE_PREMISE = (
    "A permutation s of 1..49 maps the outcome space {(D, special): D a 6-subset, special "
    "not in D} bijectively onto itself and keeps |t & D| and (special in t) for every ticket "
    "t, so a portfolio and its relabelling win on equally many outcomes."
)
CLAIM_BOUNDARY = (
    "Exact counts for the 112728 members of this HHL single-augment family only, under the "
    "uniform fair-draw model. No other family, forecast, recommendation or global optimum. "
    "Scientific authority stays PENDING_FRESH_JUDGE until an independent Judge verifies it."
)


def checkout_root() -> Path:
    return Path(__file__).resolve().parents[3]


def git_identity(checkout: Path) -> dict[str, Any]:
    ancestor = subprocess.run(
        ["git", "-C", str(checkout), "merge-base", "--is-ancestor", SOURCE_HEAD, "HEAD"],
        check=False,
        capture_output=True,
    )
    return {
        "HEAD": _git(checkout, "rev-parse", "HEAD").decode("ascii").strip(),
        "TREE": _git(checkout, "rev-parse", "HEAD^{tree}").decode("ascii").strip(),
        "BRANCH": _git(checkout, "branch", "--show-current").decode("utf-8").strip(),
        "SOURCE_HEAD_IS_ANCESTOR": ancestor.returncode == 0,
        "STATUS_PORCELAIN": _git(checkout, "status", "--porcelain=v1", "-uall")
        .decode("utf-8")
        .splitlines(),
    }


def resources(started: float) -> dict[str, Any]:
    own = resource.getrusage(resource.RUSAGE_SELF)
    children = resource.getrusage(resource.RUSAGE_CHILDREN)
    return {
        "CPU_SECONDS": round(
            own.ru_utime + own.ru_stime + children.ru_utime + children.ru_stime, 3
        ),
        "WALL_SECONDS": round(time.monotonic() - started, 3),
        "PEAK_RSS_BYTES": own.ru_maxrss,
        "PEAK_RSS_UNIT": "bytes (Darwin ru_maxrss)" if sys.platform == "darwin" else "KiB",
        "CPU_WORKERS": 1,
        "THREAD_ENV": {name: os.environ.get(name) for name in THREAD_ENV},
    }


def source_identity(checkout: Path, identity: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "SOURCE_HEAD": SOURCE_HEAD,
        "SOURCE_TREE": SOURCE_TREE,
        "BUILD_HEAD": identity["HEAD"],
        "BUILD_TREE": identity["TREE"],
        "BUILDER_SHA256": file_sha256(Path(__file__).resolve()),
        "BASELINE_GIT_BLOB": BASELINE_GIT_BLOB,
        "BASELINE_SHA256": BASELINE_SHA256,
        "BASELINE_EXACT_COUNT": BASELINE_EXACT_COUNT,
        "EVALUATOR_PATH": EVALUATOR_RELATIVE_PATH,
        "EVALUATOR_SHA256": require_evaluator(checkout),
        "PYTHON": sys.version.split()[0],
        "NUMPY": np.__version__,
    }


def build_certificate(output: Path, result_paths: Sequence[Path]) -> dict[str, Any]:
    """Derive the cover, score each unanchored representative and write the certificate."""

    started = time.monotonic()
    checkout = checkout_root()
    identity = git_identity(checkout)
    if not identity["SOURCE_HEAD_IS_ANCESTOR"]:
        raise ValueError("the pinned source head is not an ancestor of HEAD")
    baseline = load_baseline(checkout)
    family, digests, family_record = checked_family(baseline)
    anchors, source_records = original_anchors(family, digests, result_paths)
    perms = baseline_automorphisms(baseline)
    representative, permutation = orbit_cover(family, perms, anchors)
    unanchored = sorted(set(representative.tolist()) - anchors.keys())
    for anchor in score_portfolios(checkout, family, unanchored, NEW_ANCHOR_SOURCE):
        anchors[anchor.family_index] = anchor
    counts, cover_stats = verify_cover(family.masks, perms, representative, permutation, anchors)
    claims = family_claims(family, counts, anchors, representative)
    anchor_rows = [anchors[index].row() for index in sorted(anchors)]
    cover = [representative.tolist(), permutation.tolist()]
    certificate: dict[str, Any] = {
        "SCHEMA": CERTIFICATE_SCHEMA,
        "TASK_ID": TASK_ID,
        "SCIENTIFIC_AUTHORITY": SCIENTIFIC_AUTHORITY,
        "SOURCE_IDENTITY": source_identity(checkout, identity),
        "OUTCOME_SPACE": {
            "TOTAL_OFFICIAL_OUTCOMES": TOTAL_OFFICIAL_OUTCOMES,
            "MAIN_DRAW_COUNT": MAIN_DRAW_COUNT,
            "SPECIALS_PER_MAIN_DRAW": SPECIALS_PER_MAIN_DRAW,
            "WIN_RULE": "|t & D| >= 3 or (|t & D| == 2 and special in t), special not in D",
        },
        "INVARIANCE_PREMISE": INVARIANCE_PREMISE,
        "FAMILY": family_record,
        "SOURCE_RESULTS": source_records,
        "PERMUTATIONS": {
            "CONVENTION": "row p lists the images of numbers 1..49; row 0 is the identity",
            "DERIVATION": "Aut(H tickets 0..11) x Aut(L tickets 12..19) of the baseline by "
            "exhaustive line-preserving backtracking; soundness needs only bijectivity",
            "ROWS": perms.tolist(),
            "ROWS_SHA256": compact_json_sha256(perms.tolist()),
        },
        "ANCHORS": {
            "COLUMNS": list(ANCHOR_COLUMNS),
            "SOURCE_CODES": {
                **{str(source.source): source.role for source in SOURCE_RESULTS},
                str(NEW_ANCHOR_SOURCE): f"{TASK_ID}: pinned official evaluator",
            },
            "ROWS": anchor_rows,
            "ROWS_SHA256": compact_json_sha256(anchor_rows),
        },
        "COVER": {
            "CONVENTION": "candidate c: PERMUTATIONS.ROWS[PERMUTATION_INDEX[c]] maps its "
            "tickets onto those of REPRESENTATIVE_FAMILY_INDEX[c], an anchored candidate",
            "REPRESENTATIVE_FAMILY_INDEX": cover[0],
            "PERMUTATION_INDEX": cover[1],
            "SHA256": compact_json_sha256(cover),
        },
        "CLAIMS": claims,
        "CLAIM_BOUNDARY": CLAIM_BOUNDARY,
    }
    data = gzip.compress(compact_json(certificate).encode("ascii"), compresslevel=9, mtime=0)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(data)
    return {
        "TASK_ID": TASK_ID,
        "MODE": "BUILD",
        "IDENTITY": identity,
        "CERTIFICATE_PATH": str(output.resolve()),
        "CERTIFICATE_SHA256": hashlib.sha256(data).hexdigest(),
        "CERTIFICATE_BYTES": len(data),
        "NEW_ANCHORS_SCORED": len(unanchored),
        "COVER": cover_stats,
        "CLAIMS": claims,
        "RESOURCES": resources(started),
    }


def parse_anchors(section: Mapping[str, Any], family_size: int) -> dict[int, Anchor]:
    if section["COLUMNS"] != list(ANCHOR_COLUMNS):
        raise ValueError("anchor schema differs")
    rows = cast(list[list[Any]], section["ROWS"])
    if compact_json_sha256(rows) != section["ROWS_SHA256"]:
        raise ValueError("anchor rows digest differs")
    anchors: dict[int, Anchor] = {}
    previous = -1
    for row in rows:
        if len(row) != len(ANCHOR_COLUMNS) or not all(type(value) is int for value in row):
            raise ValueError(f"anchor row is malformed: {row}")
        index, count, m3_plus, rescued, source = cast(list[int], row)
        if not previous < index < family_size or source not in (0, 1, NEW_ANCHOR_SOURCE):
            raise ValueError(f"anchor row has a bad index or source: {row}")
        if not exact_fields_ok(count, m3_plus, rescued):
            raise ValueError(f"anchor row exact accounting fails: {row}")
        anchors[index] = Anchor(index, count, m3_plus, rescued, source)
        previous = index
    return anchors


def require_header(certificate: Mapping[str, Any], checkout: Path) -> None:
    pinned = cast(dict[str, Any], certificate["SOURCE_IDENTITY"])
    expected = {
        "SOURCE_HEAD": SOURCE_HEAD,
        "SOURCE_TREE": SOURCE_TREE,
        "BASELINE_GIT_BLOB": BASELINE_GIT_BLOB,
        "BASELINE_SHA256": BASELINE_SHA256,
        "BASELINE_EXACT_COUNT": BASELINE_EXACT_COUNT,
        "EVALUATOR_PATH": EVALUATOR_RELATIVE_PATH,
        "EVALUATOR_SHA256": require_evaluator(checkout),
    }
    if (
        certificate["SCHEMA"] != CERTIFICATE_SCHEMA
        or certificate["TASK_ID"] != TASK_ID
        or certificate["SCIENTIFIC_AUTHORITY"] != SCIENTIFIC_AUTHORITY
        or {name: pinned.get(name) for name in expected} != expected
    ):
        raise ValueError("certificate header differs from the pinned identities")


def verify_certificate(
    certificate_path: Path, result_paths: Sequence[Path] | None
) -> dict[str, Any]:
    """Replay the certificate from scratch; fail closed on the first broken check.

    With ``result_paths`` None the ledger cross-check (AC3) is NOT_RUN and the replay can
    at best be INCOMPLETE. The original 10240 ledger counts are never rescored.
    """

    started = time.monotonic()
    checks: dict[str, str] = {}
    report: dict[str, Any] = {"TASK_ID": TASK_ID, "MODE": "VERIFY"}
    try:
        checkout = checkout_root()
        identity = git_identity(checkout)
        data = certificate_path.read_bytes()
        verifier = Path(__file__).resolve()
        report["IDENTITY"] = {
            **identity,
            "VERIFIER_PATH": str(verifier),
            "VERIFIER_SHA256": file_sha256(verifier),
            "CERTIFICATE_PATH": str(certificate_path.resolve()),
            "CERTIFICATE_SHA256": hashlib.sha256(data).hexdigest(),
            "EVALUATOR_SHA256": require_evaluator(checkout),
            "PYTHON": sys.version.split()[0],
            "NUMPY": np.__version__,
        }
        if not identity["SOURCE_HEAD_IS_ANCESTOR"]:
            raise ValueError("the pinned source head is not an ancestor of HEAD")
        certificate = cast(dict[str, Any], json.loads(gzip.decompress(data)))
        require_header(certificate, checkout)
        checks["AC1_IDENTITY"] = "PASS"

        baseline = load_baseline(checkout)
        family, digests, family_record = checked_family(baseline)
        if certificate["FAMILY"] != family_record:
            raise ValueError("certificate family record differs from the regenerated family")
        checks["AC2_FAMILY"] = "PASS"

        anchors = parse_anchors(certificate["ANCHORS"], len(family.keys))
        listed = {index: a for index, a in anchors.items() if a.source != NEW_ANCHOR_SOURCE}
        if result_paths is None:
            checks["AC3_ORIGINAL_ANCHORS"] = "NOT_RUN"
        else:
            ledger, records = original_anchors(family, digests, result_paths)
            pinned = cast(list[dict[str, Any]], certificate["SOURCE_RESULTS"])
            strip = [{k: v for k, v in r.items() if k != "PATH"} for r in records]
            if (
                listed != ledger
                or [{k: v for k, v in r.items() if k != "PATH"} for r in pinned] != strip
            ):
                raise ValueError("certificate anchors differ from the pinned formal ledgers")
            checks["AC3_ORIGINAL_ANCHORS"] = "PASS"

        section = cast(dict[str, Any], certificate["PERMUTATIONS"])
        perms = np.array(section["ROWS"], dtype=np.int64)
        if compact_json_sha256(perms.tolist()) != section["ROWS_SHA256"]:
            raise ValueError("permutation rows digest differs")
        require_permutations(perms)
        base = sorted(ticket_mask(ticket) for ticket in baseline)
        fixing = sum(
            sorted(ticket_mask(t) for t in relabel(baseline, row)) == base for row in perms.tolist()
        )
        cover = cast(dict[str, Any], certificate["COVER"])
        lists = [cover["REPRESENTATIVE_FAMILY_INDEX"], cover["PERMUTATION_INDEX"]]
        if compact_json_sha256(lists) != cover["SHA256"]:
            raise ValueError("cover digest differs")
        representative = np.array(lists[0], dtype=np.int64)
        permutation = np.array(lists[1], dtype=np.int64)
        counts, cover_stats = verify_cover(
            family.masks, perms, representative, permutation, anchors
        )
        checks["AC4_AC5_EXPLICIT_ISOMORPHISM_MAPS"] = "PASS"

        new = sorted(index for index, a in anchors.items() if a.source == NEW_ANCHOR_SOURCE)
        if any(int(representative[index]) != index for index in new):
            raise ValueError("a newly scored anchor is not its own representative")
        rescored = score_portfolios(checkout, family, new, NEW_ANCHOR_SOURCE)
        wrong = [a.family_index for a in rescored if anchors[a.family_index] != a]
        if wrong:
            raise ValueError(f"{len(wrong)} new anchors differ on rescoring; first {wrong[0]}")
        checks["NEW_ANCHOR_RESCORE"] = "PASS"

        claims = family_claims(family, counts, anchors, representative)
        if claims["UNRESOLVED_PORTFOLIOS"] != 0 or len(counts) != len(family.keys):
            raise ValueError("some candidate has no exact count")
        checks["AC6_ALL_EXACT_COUNTS"] = "PASS"
        if claims != certificate["CLAIMS"]:
            raise ValueError("recomputed claims differ from the certificate claims")
        if (
            claims["FAMILY_MAXIMUM_EXACT_COUNT"] != EXPECTED_FAMILY_MAXIMUM
            or claims["STRICT_GAIN_COUNT"] != EXPECTED_STRICT_GAIN_COUNT
        ):
            raise ValueError("family maximum or strict gain count differs from the target")
        checks["AC7_FAMILY_CLAIMS"] = "PASS"
        report.update(
            {
                "FAMILY": {k: v for k, v in family_record.items() if k != "GENERATION_RULE"},
                "PERMUTATIONS": {"ROWS": len(perms), "BASELINE_AUTOMORPHISMS": fixing},
                "ANCHORS": {
                    "ORIGINAL": len(listed),
                    "NEW_RESCORED": len(rescored),
                    "ORIGINAL_RESCORED": 0,
                },
                "COVER": cover_stats,
                "CLAIMS": claims,
            }
        )
    except (ValueError, KeyError, TypeError, OSError, subprocess.CalledProcessError) as error:
        report["FAILURE"] = f"{type(error).__name__}: {error}"
    if "FAILURE" in report:
        report["STATUS"] = "FAIL"
    elif "NOT_RUN" in checks.values():
        report["STATUS"] = "INCOMPLETE"
    else:
        report["STATUS"] = "PASS"
    report["CHECKS"] = checks
    report["SCIENTIFIC_AUTHORITY"] = SCIENTIFIC_AUTHORITY
    report["RESOURCES"] = resources(started)
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("build", "verify"):
        command = commands.add_parser(name)
        command.add_argument(
            "--certificate", type=Path, default=checkout_root() / CERTIFICATE_RELATIVE_PATH
        )
        command.add_argument("--report", type=Path, default=None)
        command.add_argument("--old-result", type=Path, default=SOURCE_RESULTS[0].path)
        command.add_argument("--guided-result", type=Path, default=SOURCE_RESULTS[1].path)
    commands.choices["verify"].add_argument("--anchors-from-certificate-only", action="store_true")
    arguments = parser.parse_args(argv)
    paths = [cast(Path, arguments.old_result), cast(Path, arguments.guided_result)]
    certificate = cast(Path, arguments.certificate)
    if arguments.command == "build":
        report = build_certificate(certificate, paths)
        status = "PASS"
    else:
        only = cast(bool, arguments.anchors_from_certificate_only)
        report = verify_certificate(certificate, None if only else paths)
        status = cast(str, report["STATUS"])
    text = json.dumps(report, indent=2, sort_keys=True)
    if arguments.report is not None:
        target = cast(Path, arguments.report)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
