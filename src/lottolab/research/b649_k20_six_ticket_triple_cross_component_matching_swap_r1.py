"""Six-ticket triple cross-component matching swap exact search on pinned K20 baseline.

Task ID: B649_K20_SIX_TICKET_TRIPLE_CROSS_COMPONENT_MATCHING_SWAP_R1

Implements:
1. Proven 2172 canonical representative generator for the three-pair H/L matching swap
   family on the pinned K20 baseline (313,263,888 outcomes).
2. Exact 49-bit special-ball coverage mask delta kernel and 128-event fixture verifier.
3. Baseline cache (D, H2, H3, B, U, L) with strict cache identity and U reuse only
   when the 14 retained ticket indices are identical.
4. Full 13,983,816 main-draw slice scan per candidate with exact int64 accumulation.
5. Independent 7-set oracle recount via the pinned repair module's ``outcome_count``.
6. Durable progress journal that preserves cumulative CPU and wall budgets across runs.
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import importlib.util
import inspect
import json
import os
import resource
import shutil
import subprocess
import sys
import tempfile
import time
from collections import Counter
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from fractions import Fraction
from itertools import combinations, product
from pathlib import Path
from types import ModuleType
from typing import Final, NamedTuple, cast

import numpy as np
import numpy.typing as npt

from lottolab.research import b649_official_any_prize_exact as official_exact
from lottolab.research.b649_official_any_prize_exact import (
    BIG_LOTTO_DRAW_SIZE,
    BIG_LOTTO_OUTRIGHT_MATCHES,
    BIG_LOTTO_POOL_SIZE,
    all_main_draw_masks,
    evaluate_portfolio,
)

type Ticket = tuple[int, ...]
type Portfolio = tuple[Ticket, ...]
type Triple = tuple[int, int, int]
type CanonicalKey = tuple[Triple, Triple, Triple]
type UInt64Array = npt.NDArray[np.uint64]
type UInt32Array = npt.NDArray[np.uint32]

TASK_ID: Final = "B649_K20_SIX_TICKET_TRIPLE_CROSS_COMPONENT_MATCHING_SWAP_R1"
PINNED_SOURCE_HEAD: Final = "df217c8784d974f73d2f5ed49c2cb45679425455"
PINNED_SOURCE_TREE: Final = "7250eccf353e2c9c99047adc6331e6fc7bc9e09f"
BASELINE_GIT_BLOB: Final = "404e35563564a40bdd228dafa25fdf5b82e45812"
BASELINE_PORTFOLIO_SHA256: Final = (
    "eaed652900d101881b678a1515d2a366bff9de6723dbec2ec9c82fe0d0d7844c"
)
BASELINE_EXACT_COUNT: Final = 313_263_888
TOTAL_OUTCOMES: Final = 601_304_088
MAIN_DRAW_COUNT: Final = 13_983_816
SPECIAL_BALL_COUNT: Final = 43
SEVEN_SET_MULTIPLIER: Final = 7

OFFICIAL_EVALUATOR_RELPATH: Final = "src/lottolab/research/b649_official_any_prize_exact.py"
OFFICIAL_EVALUATOR_SHA256: Final = (
    "92dcb836254cc6dbcd6c2ad907e619a5eb8cf3917197a8f6de3e5f989825cf66"
)

INDEPENDENT_ORACLE_RELPATH: Final = (
    ".task-data/B649_K20_DESTROY4_GLOBAL_POOL_EXHAUSTIVE_R1/"
    "run1/engine/src/lottolab/research/b649_k20_five_ticket_exact_repair_r1.py"
)
INDEPENDENT_ORACLE_SHA256: Final = (
    "2877785e3b956c5e6f79fc15b8e04f2f0b2c3b489625afbf44409ce62684c8d0"
)

EXPECTED_H_SUPPORT_TRIPLES: Final = 40
EXPECTED_FIRST_LAYER_KEYS: Final = 4320
EXPECTED_H_FIXED_POINTS: Final = 24
EXPECTED_CANONICAL_KEYS: Final = 2172
EXPECTED_CANONICAL_KEYS_SHA256: Final = (
    "43c59b88f506b1e687f58e7429ddb241764992ac1bf18377cec3173fb9db1e4b"
)
EXPECTED_ORDERED_GENERATOR_OUTPUT_SHA256: Final = (
    "6caf38753d8978160fecbaab358ba0290a65347148ceb5a28bf5969bc4bc18b0"
)

EXPECTED_FIXTURE_EVENTS: Final = 128
EXPECTED_FIXTURE_FORWARD_OLD: Final = 94
EXPECTED_FIXTURE_FORWARD_NEW: Final = 88
EXPECTED_FIXTURE_FORWARD_GAIN: Final = 27
EXPECTED_FIXTURE_FORWARD_LOSS: Final = 33
EXPECTED_FIXTURE_FORWARD_DELTA: Final = -6
EXPECTED_FIXTURE_REVERSE_OLD: Final = 88
EXPECTED_FIXTURE_REVERSE_NEW: Final = 94
EXPECTED_FIXTURE_REVERSE_GAIN: Final = 33
EXPECTED_FIXTURE_REVERSE_LOSS: Final = 27
EXPECTED_FIXTURE_REVERSE_DELTA: Final = 6
EXPECTED_FIXTURE_IDENTITY_OLD: Final = 94
EXPECTED_FIXTURE_IDENTITY_NEW: Final = 94
EXPECTED_FIXTURE_IDENTITY_DELTA: Final = 0

PORTFOLIO_SIZE: Final = 20
TICKET_SIZE: Final = 6
CHANGED_TICKET_COUNT: Final = 6
RETAINED_TICKET_COUNT: Final = 14
ALL49: Final = (1 << 49) - 1
ALL20_TICKET_MASK: Final = (1 << 20) - 1

L_NUMBERS: Final[Triple] = (29, 35, 41)
L_ENDPOINTS: Final[tuple[tuple[int, int], tuple[int, int], tuple[int, int]]] = (
    (12, 15),
    (13, 16),
    (14, 17),
)
H_POSITION_MAP: Final[tuple[int, ...]] = (11, 6, 4, 7, 2, 10, 1, 3, 8, 9, 5, 0)
H_NUMBER_PAIRS: Final[tuple[tuple[int, int], ...]] = (
    (1, 13),
    (2, 19),
    (3, 9),
    (4, 16),
    (5, 15),
    (6, 17),
    (7, 20),
    (10, 18),
    (12, 14),
    (22, 26),
)
H_NUMBER_MAP: Final[dict[int, int]] = {
    u: v for x, y in H_NUMBER_PAIRS for u, v in ((x, y), (y, x))
}

RESOURCE_POLICY: Final = "SHARED_WORKSTATION"
CPU_WORKERS: Final = 1
NUMERICAL_THREADS: Final = 1
MAX_TOTAL_MEMORY_BYTES: Final = 2 * 1024 * 1024 * 1024
MAX_CUMULATIVE_CPU_SECONDS: Final = 3600.0
MAX_WALL_SECONDS: Final = 5400.0

CANONICAL_BASELINE_TICKETS: Final[Portfolio] = (
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


class SixTicketSwapError(ValueError):
    """Raised when any source, symmetry, mask, cache, or budget invariant fails."""


def compact_json_sha256(value: object) -> str:
    """Deterministic SHA-256 of compact ASCII JSON representation."""

    encoded = json.dumps(value, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()


def normalize_ticket(ticket: Sequence[int]) -> Ticket:
    """Validate and sort a 6-number ticket in 1..49."""

    if len(ticket) != TICKET_SIZE:
        raise SixTicketSwapError(f"ticket must have {TICKET_SIZE} numbers, got {len(ticket)}")
    cleaned: list[int] = []
    for n in ticket:
        if type(n) is not int or not 1 <= n <= BIG_LOTTO_POOL_SIZE:
            raise SixTicketSwapError(f"illegal ticket number: {n!r}")
        cleaned.append(n)
    if len(set(cleaned)) != TICKET_SIZE:
        raise SixTicketSwapError(f"duplicate numbers in ticket: {tuple(ticket)}")
    return tuple(sorted(cleaned))


def normalize_portfolio(
    portfolio: Sequence[Sequence[int]], *, expected_size: int = PORTFOLIO_SIZE
) -> Portfolio:
    """Validate and sort a portfolio of distinct 6-number tickets."""

    if len(portfolio) != expected_size:
        raise SixTicketSwapError(
            f"portfolio must contain {expected_size} tickets, got {len(portfolio)}"
        )
    tickets = [normalize_ticket(t) for t in portfolio]
    if len(set(tickets)) != expected_size:
        raise SixTicketSwapError("portfolio contains duplicate tickets")
    return tuple(sorted(tickets))


def portfolio_sha256(portfolio: Sequence[Sequence[int]]) -> str:
    """Canonical set-identity SHA-256 of a normalized 20-ticket portfolio."""

    normalized = normalize_portfolio(portfolio)
    return compact_json_sha256(normalized)


def verify_baseline(tickets: Sequence[Sequence[int]]) -> Portfolio:
    """Verify that ``tickets`` is the exact canonical baseline in canonical slot order."""

    if len(tickets) != PORTFOLIO_SIZE:
        raise SixTicketSwapError("baseline must contain 20 tickets")
    slot_ordered = tuple(normalize_ticket(t) for t in tickets)
    if len(set(slot_ordered)) != PORTFOLIO_SIZE or slot_ordered != tuple(sorted(slot_ordered)):
        raise SixTicketSwapError("baseline is not in canonical sorted order")
    if compact_json_sha256(slot_ordered) != BASELINE_PORTFOLIO_SHA256:
        raise SixTicketSwapError("pinned baseline SHA256 mismatch")
    return slot_ordered


def _git_bytes(repo_or_worktree: Path, *args: str) -> bytes:
    env = dict(
        os.environ,
        GIT_OPTIONAL_LOCKS="0",
        GIT_NO_LAZY_FETCH="1",
        GIT_CONFIG_COUNT="1",
        GIT_CONFIG_KEY_0="core.fsmonitor",
        GIT_CONFIG_VALUE_0="false",
    )
    return subprocess.check_output(
        [
            "git",
            "--no-optional-locks",
            "-c",
            "core.fsmonitor=false",
            "-C",
            str(repo_or_worktree),
            *args,
        ],
        env=env,
    )


def load_pinned_baseline(repository: Path) -> Portfolio:
    """Load and verify the pinned baseline from git blob 404e3556..."""

    head = _git_bytes(repository, "rev-parse", "HEAD").decode("ascii").strip()
    tree = _git_bytes(repository, "rev-parse", "HEAD^{tree}").decode("ascii").strip()
    if head != PINNED_SOURCE_HEAD:
        raise SixTicketSwapError(f"HEAD mismatch: expected {PINNED_SOURCE_HEAD}, got {head}")
    if tree != PINNED_SOURCE_TREE:
        raise SixTicketSwapError(f"Tree mismatch: expected {PINNED_SOURCE_TREE}, got {tree}")
    blob = _git_bytes(repository, "cat-file", "blob", BASELINE_GIT_BLOB)
    git_hash = hashlib.sha1(
        b"blob " + str(len(blob)).encode("ascii") + b"\0" + blob
    ).hexdigest()
    if git_hash != BASELINE_GIT_BLOB:
        raise SixTicketSwapError(f"Git blob SHA1 mismatch: {git_hash}")
    payload = json.loads(blob.decode("utf-8"))
    return verify_baseline(payload["FINAL_TICKETS"])


@dataclass(frozen=True, slots=True)
class SourceIdentityReport:
    repository_path: str
    worktree_path: str
    actual_head: str
    actual_tree: str
    baseline_git_blob: str
    baseline_sha256: str
    evaluator_file_path: str
    evaluator_imported_path: str
    evaluator_sha256: str
    independent_oracle_path: str
    independent_oracle_sha256: str


def verify_source_identity(
    repository: Path, worktree: Path | None = None
) -> SourceIdentityReport:
    """Verify AC1: repository/worktree HEAD & tree, baseline blob/SHA, evaluator & oracle SHA."""

    repo_root = repository.resolve()
    wt_root = (worktree if worktree is not None else repository).resolve()

    repo_head = _git_bytes(repo_root, "rev-parse", "HEAD").decode("ascii").strip()
    repo_tree = _git_bytes(repo_root, "rev-parse", "HEAD^{tree}").decode("ascii").strip()
    wt_head = _git_bytes(wt_root, "rev-parse", "HEAD").decode("ascii").strip()
    wt_tree = _git_bytes(wt_root, "rev-parse", "HEAD^{tree}").decode("ascii").strip()

    if repo_head != PINNED_SOURCE_HEAD or wt_head != PINNED_SOURCE_HEAD:
        raise SixTicketSwapError(
            f"HEAD mismatch: repo={repo_head}, worktree={wt_head}, expected={PINNED_SOURCE_HEAD}"
        )
    if repo_tree != PINNED_SOURCE_TREE or wt_tree != PINNED_SOURCE_TREE:
        raise SixTicketSwapError(
            f"Tree mismatch: repo={repo_tree}, worktree={wt_tree}, expected={PINNED_SOURCE_TREE}"
        )

    baseline = load_pinned_baseline(wt_root)
    base_sha = compact_json_sha256(baseline)
    if base_sha != BASELINE_PORTFOLIO_SHA256:
        raise SixTicketSwapError("Baseline SHA256 mismatch")

    eval_path = (wt_root / OFFICIAL_EVALUATOR_RELPATH).resolve()
    if not eval_path.is_file():
        raise SixTicketSwapError(f"Missing official evaluator: {eval_path}")
    eval_sha = hashlib.sha256(eval_path.read_bytes()).hexdigest()
    if eval_sha != OFFICIAL_EVALUATOR_SHA256:
        raise SixTicketSwapError(
            f"Official evaluator SHA256 mismatch: expected {OFFICIAL_EVALUATOR_SHA256}, "
            f"got {eval_sha}"
        )

    imported_eval_file = inspect.getsourcefile(official_exact)
    if imported_eval_file is None:
        raise SixTicketSwapError("Could not resolve imported official evaluator file")
    imported_eval_path = Path(imported_eval_file).resolve()
    imported_eval_sha = hashlib.sha256(imported_eval_path.read_bytes()).hexdigest()
    if imported_eval_sha != OFFICIAL_EVALUATOR_SHA256:
        raise SixTicketSwapError(
            f"Imported evaluator SHA256 mismatch: {imported_eval_sha} at {imported_eval_path}"
        )

    oracle_path = (repo_root / INDEPENDENT_ORACLE_RELPATH).resolve()
    if not oracle_path.is_file():
        raise SixTicketSwapError(f"Missing independent 7-set oracle: {oracle_path}")
    oracle_sha = hashlib.sha256(oracle_path.read_bytes()).hexdigest()
    if oracle_sha != INDEPENDENT_ORACLE_SHA256:
        raise SixTicketSwapError(
            f"Independent oracle SHA256 mismatch: expected {INDEPENDENT_ORACLE_SHA256}, "
            f"got {oracle_sha}"
        )

    return SourceIdentityReport(
        repository_path=str(repo_root),
        worktree_path=str(wt_root),
        actual_head=wt_head,
        actual_tree=wt_tree,
        baseline_git_blob=BASELINE_GIT_BLOB,
        baseline_sha256=base_sha,
        evaluator_file_path=str(eval_path),
        evaluator_imported_path=str(imported_eval_path),
        evaluator_sha256=eval_sha,
        independent_oracle_path=str(oracle_path),
        independent_oracle_sha256=oracle_sha,
    )


# ---------------------------------------------------------------------------
# Section 七: 2172 Canonical Representative Generator
# ---------------------------------------------------------------------------


def transform(r: CanonicalKey) -> CanonicalKey:
    """Apply the non-trivial H-automorphism involution and re-normalize L endpoint bits.

    Domain: valid first-layer keys ``(a, h, e)`` with ``e[0] == 0``.
    """

    a, h, e = r
    rows = sorted(
        (H_NUMBER_MAP.get(n, n), H_POSITION_MAP[i], bit)
        for n, i, bit in zip(a, h, e, strict=True)
    )
    first_bit = rows[0][2]
    return (
        (rows[0][0], rows[1][0], rows[2][0]),
        (rows[0][1], rows[1][1], rows[2][1]),
        (rows[0][2] ^ first_bit, rows[1][2] ^ first_bit, rows[2][2] ^ first_bit),
    )


def canonical(r: CanonicalKey) -> CanonicalKey:
    """Lexicographic minimum of ``r`` and ``transform(r)`` in the size-2 H-orbit."""

    return min(r, transform(r))


@dataclass(frozen=True, slots=True)
class CandidateExchangeSpec:
    """Full structural specification for one canonical six-ticket exchange candidate."""

    index: int
    key: CanonicalKey
    removed_indices: tuple[int, int, int, int, int, int]
    retained_indices: tuple[int, ...]
    retained_bitmask: int
    slot_portfolio: Portfolio
    normalized_portfolio: Portfolio
    portfolio_sha256: str
    added_tickets: tuple[Ticket, Ticket, Ticket, Ticket, Ticket, Ticket]
    added_masks: tuple[int, int, int, int, int, int]


class CanonicalGenerator:
    """Deterministic generator for the 2172 canonical representatives of the 6-ticket family."""

    def __init__(self, baseline: Sequence[Sequence[int]] = CANONICAL_BASELINE_TICKETS) -> None:
        self.baseline: Portfolio = verify_baseline(baseline)
        self.supports: dict[int, tuple[int, ...]] = {
            n: tuple(i for i, t in enumerate(self.baseline[:12]) if n in t)
            for n in range(1, 21)
        }
        self.support_triples: tuple[Triple, ...] = tuple(
            (a1, a2, a3)
            for a1, a2, a3 in combinations(range(1, 21), 3)
            if (
                set(self.supports[a1]).isdisjoint(self.supports[a2])
                and set(self.supports[a1]).isdisjoint(self.supports[a3])
                and set(self.supports[a2]).isdisjoint(self.supports[a3])
            )
        )

    def raw_keys(self) -> Iterator[CanonicalKey]:
        """Yield the 4320 first-layer L-quotient representative keys."""

        for a in self.support_triples:
            s0, s1, s2 = self.supports[a[0]], self.supports[a[1]], self.supports[a[2]]
            for h0, h1, h2 in product(s0, s1, s2):
                h: Triple = (h0, h1, h2)
                for e2, e3 in product((0, 1), repeat=2):
                    e: Triple = (0, e2, e3)
                    yield (a, h, e)

    def canonical_keys(self) -> tuple[CanonicalKey, ...]:
        """Return the 2172 unique canonical representative keys in lexicographic order."""

        return tuple(sorted({canonical(r) for r in self.raw_keys()}))

    def portfolio(self, r: CanonicalKey) -> Portfolio:
        """Apply all three H/L exchanges simultaneously, preserving baseline slot order."""

        a, h, e = r
        if (
            a not in self.support_triples
            or len(h) != 3
            or len(e) != 3
            or e[0] != 0
            or any(type(b) is not int or b not in (0, 1) for b in e)
            or any(
                type(i) is not int or i not in self.supports[n]
                for n, i in zip(a, h, strict=True)
            )
        ):
            raise SixTicketSwapError(f"Invalid representative key: {r!r}")
        tickets = [set(t) for t in self.baseline]
        for j, (n, i, bit) in enumerate(zip(a, h, e, strict=True)):
            k, low = L_ENDPOINTS[j][bit], L_NUMBERS[j]
            tickets[i].remove(n)
            tickets[i].add(low)
            tickets[k].remove(low)
            tickets[k].add(n)
        return tuple(tuple(sorted(t)) for t in tickets)

    def generate(self) -> Iterator[tuple[CanonicalKey, Portfolio]]:
        """Yield ``(canonical_key, slot_portfolio)`` in canonical key order."""

        for r in self.canonical_keys():
            yield r, self.portfolio(r)

    def build_candidate_spec(self, index: int, r: CanonicalKey) -> CandidateExchangeSpec:
        """Build the full candidate exchange spec with masks and retained index bitmask."""

        slot_port = self.portfolio(r)
        _a, h, e = r
        low_slots = (
            L_ENDPOINTS[0][e[0]],
            L_ENDPOINTS[1][e[1]],
            L_ENDPOINTS[2][e[2]],
        )
        removed_sorted = tuple(sorted((*h, *low_slots)))
        if len(removed_sorted) != CHANGED_TICKET_COUNT:
            raise SixTicketSwapError(f"Expected 6 distinct changed slots, got {removed_sorted}")
        removed_6 = (
            removed_sorted[0],
            removed_sorted[1],
            removed_sorted[2],
            removed_sorted[3],
            removed_sorted[4],
            removed_sorted[5],
        )
        removed_set = set(removed_6)
        retained = tuple(i for i in range(PORTFOLIO_SIZE) if i not in removed_set)
        retained_bitmask = 0
        for i in retained:
            retained_bitmask |= 1 << i

        added_6 = (
            slot_port[removed_6[0]],
            slot_port[removed_6[1]],
            slot_port[removed_6[2]],
            slot_port[removed_6[3]],
            slot_port[removed_6[4]],
            slot_port[removed_6[5]],
        )
        added_masks = (
            ticket_to_mask(added_6[0]),
            ticket_to_mask(added_6[1]),
            ticket_to_mask(added_6[2]),
            ticket_to_mask(added_6[3]),
            ticket_to_mask(added_6[4]),
            ticket_to_mask(added_6[5]),
        )
        norm_port = normalize_portfolio(slot_port)
        return CandidateExchangeSpec(
            index=index,
            key=r,
            removed_indices=removed_6,
            retained_indices=retained,
            retained_bitmask=retained_bitmask,
            slot_portfolio=slot_port,
            normalized_portfolio=norm_port,
            portfolio_sha256=compact_json_sha256(norm_port),
            added_tickets=added_6,
            added_masks=added_masks,
        )


def legal_exchange(
    baseline: Portfolio, r: CanonicalKey, candidate: Portfolio
) -> bool:
    """Verify AC3 structural legality for one candidate portfolio."""

    if len(candidate) != PORTFOLIO_SIZE or len(set(candidate)) != PORTFOLIO_SIZE:
        return False
    if any(
        len(t) != TICKET_SIZE
        or len(set(t)) != TICKET_SIZE
        or t != tuple(sorted(t))
        or any(type(n) is not int or not 1 <= n <= BIG_LOTTO_POOL_SIZE for n in t)
        for t in candidate
    ):
        return False
    before = tuple(set(t) for t in baseline)
    after = tuple(set(t) for t in candidate)
    a, h, e = r
    low_slots = tuple(L_ENDPOINTS[j][e[j]] for j in range(3))
    expected_slots = set(h) | set(low_slots)
    changed = {i for i in range(PORTFOLIO_SIZE) if before[i] != after[i]}
    if len(expected_slots) != CHANGED_TICKET_COUNT or changed != expected_slots:
        return False
    for n, i, j, k in zip(a, h, range(3), low_slots, strict=True):
        low = L_NUMBERS[j]
        if (
            before[i] - after[i] != {n}
            or after[i] - before[i] != {low}
            or before[k] - after[k] != {low}
            or after[k] - before[k] != {n}
        ):
            return False
    if Counter(n for t in baseline for n in t) != Counter(
        n for t in candidate for n in t
    ):
        return False
    return all(len(x & y) <= 1 for x, y in combinations(after, 2))


@dataclass(frozen=True, slots=True)
class GeneratorValidationSummary:
    h_support_triples: int
    raw_first_layer_keys: int
    h_fixed_points: int
    canonical_keys: int
    involution_mismatches: int
    uncovered_keys: int
    duplicate_keys: int
    illegal_candidates: int
    distinct_portfolios: int
    canonical_keys_sha256: str
    ordered_generator_output_sha256: str


def validate_generator_and_candidates(
    baseline: Sequence[Sequence[int]] = CANONICAL_BASELINE_TICKETS,
) -> tuple[CanonicalGenerator, tuple[CandidateExchangeSpec, ...], GeneratorValidationSummary]:
    """Verify AC2 and AC3 on the 2172 canonical generator and return all candidate specs."""

    gen = CanonicalGenerator(baseline)
    raw = tuple(gen.raw_keys())
    raw_set = set(raw)
    keys = gen.canonical_keys()
    key_set = set(keys)
    transformed = tuple(transform(r) for r in raw)
    fixed = sum(r == t for r, t in zip(raw, transformed, strict=True))
    involution_mismatches = sum(
        transform(t) != r for r, t in zip(raw, transformed, strict=True)
    )
    uncovered = sum(canonical(r) not in key_set for r in raw)
    duplicates = len(keys) - len(key_set)

    generated = tuple(gen.generate())
    keys_sha = compact_json_sha256(keys)
    output_sha = compact_json_sha256(generated)

    illegal = sum(not legal_exchange(gen.baseline, r, p) for r, p in generated)
    distinct_portfolios = len({p for _, p in generated})

    summary = GeneratorValidationSummary(
        h_support_triples=len(gen.support_triples),
        raw_first_layer_keys=len(raw),
        h_fixed_points=fixed,
        canonical_keys=len(keys),
        involution_mismatches=involution_mismatches,
        uncovered_keys=uncovered,
        duplicate_keys=duplicates,
        illegal_candidates=illegal,
        distinct_portfolios=distinct_portfolios,
        canonical_keys_sha256=keys_sha,
        ordered_generator_output_sha256=output_sha,
    )

    if (
        summary.h_support_triples != EXPECTED_H_SUPPORT_TRIPLES
        or summary.raw_first_layer_keys != EXPECTED_FIRST_LAYER_KEYS
        or len(raw_set) != EXPECTED_FIRST_LAYER_KEYS
        or summary.h_fixed_points != EXPECTED_H_FIXED_POINTS
        or summary.canonical_keys != EXPECTED_CANONICAL_KEYS
        or summary.involution_mismatches != 0
        or summary.uncovered_keys != 0
        or summary.duplicate_keys != 0
        or summary.illegal_candidates != 0
        or summary.distinct_portfolios != EXPECTED_CANONICAL_KEYS
        or summary.canonical_keys_sha256 != EXPECTED_CANONICAL_KEYS_SHA256
        or summary.ordered_generator_output_sha256 != EXPECTED_ORDERED_GENERATOR_OUTPUT_SHA256
    ):
        raise SixTicketSwapError(f"Generator or candidate validation failed: {summary}")

    specs = tuple(
        gen.build_candidate_spec(idx, r) for idx, r in enumerate(keys)
    )
    return gen, specs, summary


# ---------------------------------------------------------------------------
# Section 八: Exact Special-Ball Mask Kernel & 128-Event Fixture (AC4)
# ---------------------------------------------------------------------------


def popcount64(x: int) -> int:
    """Exact bit count of a non-negative 64-bit integer."""

    if type(x) is not int or x < 0:
        raise SixTicketSwapError(f"Expected non-negative int mask, got {x!r}")
    return x.bit_count()


def ticket_to_mask(ticket: Sequence[int]) -> int:
    """Convert a 6-number ticket in 1..49 to a 49-bit uint64 mask."""

    if len(ticket) != TICKET_SIZE:
        raise SixTicketSwapError(f"Ticket must have {TICKET_SIZE} numbers, got {len(ticket)}")
    mask = 0
    for n in ticket:
        if type(n) is not int or not 1 <= n <= BIG_LOTTO_POOL_SIZE:
            raise SixTicketSwapError(f"Lottery number {n!r} is outside legal 1..49 range")
        mask |= 1 << (n - 1)
    if popcount64(mask) != TICKET_SIZE:
        raise SixTicketSwapError(f"Duplicate numbers detected in ticket: {tuple(ticket)}")
    return mask


def mask_to_ticket(mask: int) -> Ticket:
    """Convert a 49-bit mask with popcount 6 back to a sorted ticket tuple."""

    if type(mask) is not int or mask < 0 or (mask & ~ALL49):
        raise SixTicketSwapError("Mask contains illegal bits beyond 49-bit space")
    if popcount64(mask) != TICKET_SIZE:
        raise SixTicketSwapError(f"Ticket mask must have 6 bits set, got {popcount64(mask)}")
    return tuple(n for n in range(1, BIG_LOTTO_POOL_SIZE + 1) if (mask & (1 << (n - 1))))


class SliceDeltaResult(NamedTuple):
    """Exact evaluation result for a single main draw D slice."""

    baseline_mask: int
    fixed_mask: int
    added_mask: int
    gain: int
    loss: int
    delta: int


def compute_ticket_set_coverage_mask(
    ticket_masks: Sequence[int],
    d_mask: int,
    e_full_mask: int,
) -> int:
    """Compute special-ball coverage mask for a set of tickets on main draw D."""

    rescue = 0
    for tm in ticket_masks:
        if type(tm) is not int or tm < 0 or (tm & ~ALL49) or popcount64(tm) != TICKET_SIZE:
            raise SixTicketSwapError(f"Illegal ticket mask: {tm!r}")
        hits = popcount64(tm & d_mask)
        if hits >= BIG_LOTTO_OUTRIGHT_MATCHES:
            return e_full_mask
        if hits == BIG_LOTTO_OUTRIGHT_MATCHES - 1:
            rescue |= tm
    return rescue & e_full_mask


def compute_six_ticket_slice_delta(
    d_mask: int,
    fixed_masks: Sequence[int],
    added_masks: Sequence[int],
    baseline_masks: Sequence[int],
    active_specials_mask: int | None = None,
) -> SliceDeltaResult:
    """Exact 6-ticket delta mask counting kernel for a single main draw D slice."""

    if type(d_mask) is not int or d_mask < 0 or (d_mask & ~ALL49):
        raise SixTicketSwapError("D contains bits outside legal 49-bit space")
    if popcount64(d_mask) != BIG_LOTTO_DRAW_SIZE:
        raise SixTicketSwapError(
            f"D must have exactly 6 main numbers, got popcount={popcount64(d_mask)}"
        )
    if len(fixed_masks) != RETAINED_TICKET_COUNT or len(set(fixed_masks)) != RETAINED_TICKET_COUNT:
        raise SixTicketSwapError("fixed_masks must contain 14 distinct ticket masks")
    if len(added_masks) != CHANGED_TICKET_COUNT or len(set(added_masks)) != CHANGED_TICKET_COUNT:
        raise SixTicketSwapError("added_masks must contain 6 distinct ticket masks")
    if len(baseline_masks) != PORTFOLIO_SIZE or len(set(baseline_masks)) != PORTFOLIO_SIZE:
        raise SixTicketSwapError("baseline_masks must contain 20 distinct ticket masks")
    if not set(fixed_masks).issubset(set(baseline_masks)):
        raise SixTicketSwapError("fixed_masks must be a 14-ticket subset of baseline_masks")
    if set(fixed_masks) & set(added_masks):
        raise SixTicketSwapError(
            "added_masks overlaps fixed_masks (duplicate tickets in candidate)"
        )

    e_full = ALL49 & ~d_mask
    if active_specials_mask is None:
        e_active = e_full
    else:
        if (
            type(active_specials_mask) is not int
            or active_specials_mask < 0
            or (active_specials_mask & ~ALL49)
        ):
            raise SixTicketSwapError("active_specials_mask has bits outside 1..49")
        if active_specials_mask & d_mask:
            raise SixTicketSwapError("active_specials_mask overlaps main draw D")
        e_active = active_specials_mask & e_full

    b_mask = compute_ticket_set_coverage_mask(baseline_masks, d_mask, e_full)
    u_mask = compute_ticket_set_coverage_mask(fixed_masks, d_mask, e_full)
    a_mask = compute_ticket_set_coverage_mask(added_masks, d_mask, e_full)

    if u_mask & ~b_mask:
        raise SixTicketSwapError("Retained 14-ticket coverage U exceeded baseline B")

    gain = popcount64(a_mask & ~b_mask & e_active)
    loss = popcount64(b_mask & ~(u_mask | a_mask) & e_active)
    delta = gain - loss

    return SliceDeltaResult(
        baseline_mask=b_mask,
        fixed_mask=u_mask,
        added_mask=a_mask,
        gain=gain,
        loss=loss,
        delta=delta,
    )


def ticket_wins_oracle(ticket: Ticket, d_draw: Ticket, s: int) -> bool:
    """Direct set-based oracle for single-ticket win on outcome (D, s)."""

    if s in d_draw or not 1 <= s <= BIG_LOTTO_POOL_SIZE:
        raise SixTicketSwapError(f"Illegal special ball {s} for draw {d_draw}")
    inter = len(set(ticket) & set(d_draw))
    if inter >= BIG_LOTTO_OUTRIGHT_MATCHES:
        return True
    return inter == BIG_LOTTO_OUTRIGHT_MATCHES - 1 and s in ticket


def portfolio_wins_oracle(portfolio: Sequence[Ticket], d_draw: Ticket, s: int) -> bool:
    """Direct set-based oracle for portfolio win on outcome (D, s)."""

    return any(ticket_wins_oracle(t, d_draw, s) for t in portfolio)


@dataclass(frozen=True, slots=True)
class FixtureValidationSummary:
    event_count: int
    fwd_old: int
    fwd_new: int
    fwd_gain: int
    fwd_loss: int
    fwd_delta: int
    rev_old: int
    rev_new: int
    rev_gain: int
    rev_loss: int
    rev_delta: int
    ident_old: int
    ident_new: int
    ident_gain: int
    ident_loss: int
    ident_delta: int
    direct_oracle_mismatches: int


def run_128_fixture_validation() -> FixtureValidationSummary:
    """Execute the pinned 128-event fixture and verify AC4 parity."""

    removed_indices = (0, 1, 2, 12, 13, 14)
    retained_indices = tuple(i for i in range(PORTFOLIO_SIZE) if i not in removed_indices)

    t0_new = tuple(sorted((set(CANONICAL_BASELINE_TICKETS[0]) - {5}) | {33}))
    t12_new = tuple(sorted((set(CANONICAL_BASELINE_TICKETS[12]) - {33}) | {5}))
    t1_new = tuple(sorted((set(CANONICAL_BASELINE_TICKETS[1]) - {9}) | {38}))
    t13_new = tuple(sorted((set(CANONICAL_BASELINE_TICKETS[13]) - {38}) | {9}))
    t2_new = tuple(sorted((set(CANONICAL_BASELINE_TICKETS[2]) - {19}) | {43}))
    t14_new = tuple(sorted((set(CANONICAL_BASELINE_TICKETS[14]) - {43}) | {19}))

    added_6 = (t0_new, t1_new, t2_new, t12_new, t13_new, t14_new)
    removed_6 = tuple(CANONICAL_BASELINE_TICKETS[i] for i in removed_indices)
    fixed_14 = tuple(CANONICAL_BASELINE_TICKETS[i] for i in retained_indices)

    new_20_list: list[Ticket] = list(CANONICAL_BASELINE_TICKETS)
    new_20_list[0] = t0_new
    new_20_list[1] = t1_new
    new_20_list[2] = t2_new
    new_20_list[12] = t12_new
    new_20_list[13] = t13_new
    new_20_list[14] = t14_new
    new_20 = tuple(new_20_list)

    d1: Ticket = (2, 3, 5, 44, 45, 46)
    d2: Ticket = (2, 3, 33, 44, 45, 46)
    extra_d: tuple[Ticket, ...] = (
        (2, 8, 15, 28, 37, 43),
        (2, 3, 6, 8, 44, 45),
        (1, 2, 3, 4, 5, 21),
        (27, 29, 30, 31, 32, 33),
        (1, 2, 6, 7, 14, 44),
        (4, 6, 12, 19, 20, 24),
        (5, 9, 19, 33, 38, 43),
    )
    priority = (1, 5, 6, 9, 10, 19, 21, 27, 33, 38, 43, 48, 49)

    slices: list[tuple[Ticket, tuple[int, ...]]] = []
    for d_draw in (d1, d2):
        specials = tuple(s for s in range(1, 50) if s not in d_draw)
        slices.append((d_draw, specials))
    for d_draw in extra_d:
        specials = tuple(s for s in priority if s not in d_draw)[:6]
        slices.append((d_draw, specials))

    events: list[tuple[Ticket, int]] = []
    for d_draw, s_list in slices:
        for s in s_list:
            events.append((d_draw, s))

    if len(events) != EXPECTED_FIXTURE_EVENTS:
        raise SixTicketSwapError(f"Expected 128 events, got {len(events)}")

    base_masks = tuple(ticket_to_mask(t) for t in CANONICAL_BASELINE_TICKETS)
    fixed_masks = tuple(ticket_to_mask(t) for t in fixed_14)
    added_masks = tuple(ticket_to_mask(t) for t in added_6)
    removed_masks = tuple(ticket_to_mask(t) for t in removed_6)
    new_masks = tuple(ticket_to_mask(t) for t in new_20)

    fwd_old = fwd_new = fwd_gain = fwd_loss = 0
    rev_old = rev_new = rev_gain = rev_loss = 0
    ident_old = ident_new = ident_gain = ident_loss = 0

    for d_draw, specials in slices:
        d_mask = ticket_to_mask(d_draw)
        e_active = sum(1 << (s - 1) for s in specials)

        res_fwd = compute_six_ticket_slice_delta(
            d_mask, fixed_masks, added_masks, base_masks, e_active
        )
        fwd_gain += res_fwd.gain
        fwd_loss += res_fwd.loss
        fwd_old += popcount64(res_fwd.baseline_mask & e_active)
        fwd_new += popcount64((res_fwd.fixed_mask | res_fwd.added_mask) & e_active)

        res_rev = compute_six_ticket_slice_delta(
            d_mask, fixed_masks, removed_masks, new_masks, e_active
        )
        rev_gain += res_rev.gain
        rev_loss += res_rev.loss
        rev_old += popcount64(res_rev.baseline_mask & e_active)
        rev_new += popcount64((res_rev.fixed_mask | res_rev.added_mask) & e_active)

        res_id = compute_six_ticket_slice_delta(
            d_mask, fixed_masks, removed_masks, base_masks, e_active
        )
        ident_gain += res_id.gain
        ident_loss += res_id.loss
        ident_old += popcount64(res_id.baseline_mask & e_active)
        ident_new += popcount64((res_id.fixed_mask | res_id.added_mask) & e_active)

    fwd_delta = fwd_gain - fwd_loss
    rev_delta = rev_gain - rev_loss
    ident_delta = ident_gain - ident_loss

    mismatches = 0
    for d_draw, s in events:
        d_old = portfolio_wins_oracle(CANONICAL_BASELINE_TICKETS, d_draw, s)
        d_new = portfolio_wins_oracle(new_20, d_draw, s)
        d_gain = (not d_old) and d_new
        d_loss = d_old and (not d_new)
        d_delta = int(d_gain) - int(d_loss)

        d_set = set(d_draw)
        e_set = set(range(1, 50)) - d_set

        def _set_cov(
            port: Sequence[Ticket], d_s: set[int] = d_set, e_s: set[int] = e_set
        ) -> set[int]:
            if any(len(set(t) & d_s) >= 3 for t in port):
                return set(e_s)
            cov: set[int] = set()
            for t in port:
                if len(set(t) & d_s) == 2:
                    cov |= set(t) & e_s
            return cov

        s_b = _set_cov(CANONICAL_BASELINE_TICKETS)
        s_u = _set_cov(fixed_14)
        s_a = _set_cov(added_6)
        set_old = s in s_b
        set_new = s in (s_u | s_a)
        set_gain = (s in s_a) and (s not in s_b)
        set_loss = (s in s_b) and (s not in (s_u | s_a))
        set_delta = int(set_gain) - int(set_loss)

        d_mask = ticket_to_mask(d_draw)
        s_bit = 1 << (s - 1)
        res_ev = compute_six_ticket_slice_delta(
            d_mask, fixed_masks, added_masks, base_masks, s_bit
        )
        m_old = bool(res_ev.baseline_mask & s_bit)
        m_new = bool((res_ev.fixed_mask | res_ev.added_mask) & s_bit)
        m_gain = bool(res_ev.gain)
        m_loss = bool(res_ev.loss)
        m_delta = res_ev.delta

        if not (
            d_old == set_old == m_old
            and d_new == set_new == m_new
            and d_gain == set_gain == m_gain
            and d_loss == set_loss == m_loss
            and d_delta == set_delta == m_delta
        ):
            mismatches += 1

    summary = FixtureValidationSummary(
        event_count=len(events),
        fwd_old=fwd_old,
        fwd_new=fwd_new,
        fwd_gain=fwd_gain,
        fwd_loss=fwd_loss,
        fwd_delta=fwd_delta,
        rev_old=rev_old,
        rev_new=rev_new,
        rev_gain=rev_gain,
        rev_loss=rev_loss,
        rev_delta=rev_delta,
        ident_old=ident_old,
        ident_new=ident_new,
        ident_gain=ident_gain,
        ident_loss=ident_loss,
        ident_delta=ident_delta,
        direct_oracle_mismatches=mismatches,
    )
    if (
        summary.event_count != EXPECTED_FIXTURE_EVENTS
        or summary.fwd_old != EXPECTED_FIXTURE_FORWARD_OLD
        or summary.fwd_new != EXPECTED_FIXTURE_FORWARD_NEW
        or summary.fwd_gain != EXPECTED_FIXTURE_FORWARD_GAIN
        or summary.fwd_loss != EXPECTED_FIXTURE_FORWARD_LOSS
        or summary.fwd_delta != EXPECTED_FIXTURE_FORWARD_DELTA
        or summary.rev_old != EXPECTED_FIXTURE_REVERSE_OLD
        or summary.rev_new != EXPECTED_FIXTURE_REVERSE_NEW
        or summary.rev_gain != EXPECTED_FIXTURE_REVERSE_GAIN
        or summary.rev_loss != EXPECTED_FIXTURE_REVERSE_LOSS
        or summary.rev_delta != EXPECTED_FIXTURE_REVERSE_DELTA
        or summary.ident_old != EXPECTED_FIXTURE_IDENTITY_OLD
        or summary.ident_new != EXPECTED_FIXTURE_IDENTITY_NEW
        or summary.ident_delta != EXPECTED_FIXTURE_IDENTITY_DELTA
        or summary.direct_oracle_mismatches != 0
    ):
        raise SixTicketSwapError(f"128-event fixture validation failed: {summary}")
    return summary


# ---------------------------------------------------------------------------
# Section 九: Baseline Cache (D, H2, H3, B, U, L) & Exact Full-Slice Scorer
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CacheIdentity:
    """Strict identity binding for the baseline cache (never outcome-count-only)."""

    baseline_sha256: str
    evaluator_sha256: str
    ticket_position_indices: tuple[int, ...]
    ticket_masks: tuple[int, ...]
    official_prize_rule: dict[str, object]
    draw_enumeration_order: dict[str, object]
    dtypes: dict[str, str]

    def to_dict(self) -> dict[str, object]:
        return {
            "baseline_sha256": self.baseline_sha256,
            "evaluator_sha256": self.evaluator_sha256,
            "ticket_position_indices": list(self.ticket_position_indices),
            "ticket_masks": list(self.ticket_masks),
            "official_prize_rule": self.official_prize_rule,
            "draw_enumeration_order": self.draw_enumeration_order,
            "dtypes": self.dtypes,
        }

    @property
    def sha256(self) -> str:
        return compact_json_sha256(self.to_dict())


def validate_cache_identity(
    candidate_identity: Mapping[str, object], expected: CacheIdentity
) -> bool:
    """Reject any cache identity missing required fields or matching only by outcome count."""

    required_keys = {
        "baseline_sha256",
        "evaluator_sha256",
        "ticket_position_indices",
        "ticket_masks",
        "official_prize_rule",
        "draw_enumeration_order",
        "dtypes",
    }
    if not required_keys.issubset(set(candidate_identity.keys())):
        missing = required_keys - set(candidate_identity.keys())
        raise SixTicketSwapError(f"Cache identity missing required keys: {missing}")
    expected_dict = expected.to_dict()
    for key in required_keys:
        if candidate_identity.get(key) != expected_dict[key]:
            raise SixTicketSwapError(f"Cache identity mismatch on key {key!r}")
    return True


def build_subset_union_lookup(ticket_masks: Sequence[int]) -> UInt64Array:
    """Build L: uint64[2^K] mapping each ticket index subset bitmask to union of ticket masks."""

    k = len(ticket_masks)
    if not 1 <= k <= 20:
        raise SixTicketSwapError(f"Expected 1..20 tickets for lookup table L, got {k}")
    size = 1 << k
    lookup = np.zeros(size, dtype=np.uint64)
    for idx, mask in enumerate(ticket_masks):
        bit = 1 << idx
        lookup[bit] = np.uint64(mask)
    for q in range(1, size):
        lsb = q & -q
        prev = q ^ lsb
        if prev != 0:
            lookup[q] = lookup[prev] | lookup[lsb]
    return lookup


_C_KERNEL_SOURCE: Final = r"""
#include <stdint.h>
#include <stddef.h>

static const uint64_t ALL49 = ((UINT64_C(1) << 49) - UINT64_C(1));

int64_t b649_init_baseline_arrays(
    const uint64_t * __restrict D,
    const uint64_t * __restrict ticket_masks,
    const uint64_t * __restrict L,
    uint32_t * __restrict H2,
    uint32_t * __restrict H3,
    uint64_t * __restrict B,
    size_t M
) {
    int64_t total_baseline_outcomes = 0;
    for (size_t i = 0; i < M; ++i) {
        uint64_t d = D[i];
        uint64_t e_mask = ALL49 & ~d;
        uint32_t h2 = 0;
        uint32_t h3 = 0;
        for (uint32_t t = 0; t < 20; ++t) {
            int hits = __builtin_popcountll(d & ticket_masks[t]);
            uint32_t bit = (UINT32_C(1) << t);
            if (hits >= 3) {
                h3 |= bit;
            } else if (hits == 2) {
                h2 |= bit;
            }
        }
        H2[i] = h2;
        H3[i] = h3;
        uint64_t b_mask = (h3 != 0) ? e_mask : (L[h2] & e_mask);
        B[i] = b_mask;
        total_baseline_outcomes += (int64_t)__builtin_popcountll(b_mask);
    }
    return total_baseline_outcomes;
}

void b649_update_u_array(
    const uint64_t * __restrict D,
    const uint32_t * __restrict H2,
    const uint32_t * __restrict H3,
    const uint64_t * __restrict L,
    uint32_t retained_bitmask,
    uint64_t * __restrict U,
    size_t M
) {
    for (size_t i = 0; i < M; ++i) {
        uint64_t e_mask = ALL49 & ~D[i];
        if ((H3[i] & retained_bitmask) != 0) {
            U[i] = e_mask;
        } else {
            U[i] = L[H2[i] & retained_bitmask] & e_mask;
        }
    }
}

size_t b649_score_candidate_full(
    const uint64_t * __restrict D,
    const uint64_t * __restrict B,
    const uint64_t * __restrict U,
    uint64_t t0,
    uint64_t t1,
    uint64_t t2,
    uint64_t t3,
    uint64_t t4,
    uint64_t t5,
    size_t M,
    int64_t * __restrict out_gain,
    int64_t * __restrict out_loss
) {
    int64_t gain = 0;
    int64_t loss = 0;
    for (size_t i = 0; i < M; ++i) {
        uint64_t d = D[i];
        uint64_t e_mask = ALL49 & ~d;
        int c0 = __builtin_popcountll(d & t0);
        int c1 = __builtin_popcountll(d & t1);
        int c2 = __builtin_popcountll(d & t2);
        int c3 = __builtin_popcountll(d & t3);
        int c4 = __builtin_popcountll(d & t4);
        int c5 = __builtin_popcountll(d & t5);
        uint64_t a_mask;
        if (c0 >= 3 || c1 >= 3 || c2 >= 3 || c3 >= 3 || c4 >= 3 || c5 >= 3) {
            a_mask = e_mask;
        } else {
            uint64_t rescue = 0;
            if (c0 == 2) rescue |= t0;
            if (c1 == 2) rescue |= t1;
            if (c2 == 2) rescue |= t2;
            if (c3 == 2) rescue |= t3;
            if (c4 == 2) rescue |= t4;
            if (c5 == 2) rescue |= t5;
            a_mask = rescue & e_mask;
        }
        uint64_t b_mask = B[i];
        uint64_t u_mask = U[i];
        gain += (int64_t)__builtin_popcountll(a_mask & ~b_mask & e_mask);
        loss += (int64_t)__builtin_popcountll(b_mask & ~(u_mask | a_mask) & e_mask);
    }
    *out_gain = gain;
    *out_loss = loss;
    return M;
}
"""


class _CompiledNativeKernel:
    """Single-threaded native C kernel compiled in a disposable TemporaryDirectory."""

    def __init__(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory(prefix="b649_k20_six_ticket_")
        c_path = Path(self._tmpdir.name) / "kernel.c"
        so_path = Path(self._tmpdir.name) / "kernel.dylib"
        c_path.write_text(_C_KERNEL_SOURCE, encoding="utf-8")
        cc = shutil.which("clang") or shutil.which("cc")
        if cc is None:
            raise SixTicketSwapError("No C compiler available for single-thread native kernel")
        subprocess.run(
            [cc, "-O3", "-std=c11", "-shared", "-fPIC", str(c_path), "-o", str(so_path)],
            check=True,
            capture_output=True,
            text=True,
        )
        lib = ctypes.CDLL(str(so_path))

        self.init_baseline = lib.b649_init_baseline_arrays
        self.init_baseline.argtypes = [
            ctypes.POINTER(ctypes.c_uint64),
            ctypes.POINTER(ctypes.c_uint64),
            ctypes.POINTER(ctypes.c_uint64),
            ctypes.POINTER(ctypes.c_uint32),
            ctypes.POINTER(ctypes.c_uint32),
            ctypes.POINTER(ctypes.c_uint64),
            ctypes.c_size_t,
        ]
        self.init_baseline.restype = ctypes.c_int64

        self.update_u = lib.b649_update_u_array
        self.update_u.argtypes = [
            ctypes.POINTER(ctypes.c_uint64),
            ctypes.POINTER(ctypes.c_uint32),
            ctypes.POINTER(ctypes.c_uint32),
            ctypes.POINTER(ctypes.c_uint64),
            ctypes.c_uint32,
            ctypes.POINTER(ctypes.c_uint64),
            ctypes.c_size_t,
        ]
        self.update_u.restype = None

        self.score_candidate = lib.b649_score_candidate_full
        self.score_candidate.argtypes = [
            ctypes.POINTER(ctypes.c_uint64),
            ctypes.POINTER(ctypes.c_uint64),
            ctypes.POINTER(ctypes.c_uint64),
            ctypes.c_uint64,
            ctypes.c_uint64,
            ctypes.c_uint64,
            ctypes.c_uint64,
            ctypes.c_uint64,
            ctypes.c_uint64,
            ctypes.c_size_t,
            ctypes.POINTER(ctypes.c_int64),
            ctypes.POINTER(ctypes.c_int64),
        ]
        self.score_candidate.restype = ctypes.c_size_t

    def close(self) -> None:
        self._tmpdir.cleanup()


_native_kernel: _CompiledNativeKernel | None = None


def _get_native_kernel() -> _CompiledNativeKernel:
    global _native_kernel
    if _native_kernel is None:
        _native_kernel = _CompiledNativeKernel()
    return _native_kernel


@dataclass(frozen=True, slots=True)
class CandidateScoreResult:
    gain: int
    loss: int
    delta: int
    new_count: int
    slices_scanned: int
    u_reused: bool


class SixTicketBaselineCache:
    """Exact baseline cache (D, H2, H3, B, U, L) obeying Section 九 & 十."""

    def __init__(
        self,
        baseline: Sequence[Sequence[int]] = CANONICAL_BASELINE_TICKETS,
        *,
        draws: UInt64Array | None = None,
        use_native_kernel: bool = True,
        expected_baseline_count: int | None = BASELINE_EXACT_COUNT,
    ) -> None:
        self.baseline: Portfolio = tuple(normalize_ticket(t) for t in baseline)
        if len(self.baseline) != PORTFOLIO_SIZE or len(set(self.baseline)) != PORTFOLIO_SIZE:
            raise SixTicketSwapError("Baseline cache requires 20 distinct legal tickets")
        self.ticket_masks: tuple[int, ...] = tuple(ticket_to_mask(t) for t in self.baseline)
        self._ticket_masks_arr: UInt64Array = np.array(self.ticket_masks, dtype=np.uint64)

        if draws is None:
            draws = all_main_draw_masks(BIG_LOTTO_POOL_SIZE, BIG_LOTTO_DRAW_SIZE)
        if draws.dtype != np.uint64 or not draws.flags["C_CONTIGUOUS"]:
            draws = np.ascontiguousarray(draws, dtype=np.uint64)
        if draws.ndim != 1 or draws.size == 0:
            raise SixTicketSwapError("draws must be a non-empty 1D uint64 array")

        self.D: UInt64Array = draws
        self.M: int = int(draws.size)
        self.H2: UInt32Array = np.zeros(self.M, dtype=np.uint32)
        self.H3: UInt32Array = np.zeros(self.M, dtype=np.uint32)
        self.B: UInt64Array = np.zeros(self.M, dtype=np.uint64)
        self.U: UInt64Array = np.zeros(self.M, dtype=np.uint64)
        self.L: UInt64Array = build_subset_union_lookup(self.ticket_masks)

        self.use_native_kernel: bool = use_native_kernel
        self._current_u_retained_indices: tuple[int, ...] | None = None
        self._current_u_retained_bitmask: int | None = None
        self.u_recompute_count: int = 0
        self.u_reuse_count: int = 0

        self.identity: CacheIdentity = CacheIdentity(
            baseline_sha256=compact_json_sha256(self.baseline),
            evaluator_sha256=OFFICIAL_EVALUATOR_SHA256,
            ticket_position_indices=tuple(range(PORTFOLIO_SIZE)),
            ticket_masks=self.ticket_masks,
            official_prize_rule={
                "pool_size": BIG_LOTTO_POOL_SIZE,
                "draw_size": BIG_LOTTO_DRAW_SIZE,
                "outright_matches": BIG_LOTTO_OUTRIGHT_MATCHES,
                "rescue_matches": BIG_LOTTO_OUTRIGHT_MATCHES - 1,
                "main_special_overlap_allowed": False,
            },
            draw_enumeration_order={
                "generator": "all_main_draw_masks(low,high,tail)",
                "slice_count": self.M,
                "first_draw_mask": int(self.D[0]),
                "last_draw_mask": int(self.D[-1]),
            },
            dtypes={
                "D": str(self.D.dtype),
                "H2": str(self.H2.dtype),
                "H3": str(self.H3.dtype),
                "B": str(self.B.dtype),
                "U": str(self.U.dtype),
                "L": str(self.L.dtype),
            },
        )

        self.baseline_full_count: int = self._populate_baseline_arrays()
        if (
            expected_baseline_count is not None
            and self.baseline_full_count != expected_baseline_count
        ):
            raise SixTicketSwapError(
                f"AC5 baseline full recount mismatch: expected {expected_baseline_count}, "
                f"got {self.baseline_full_count}"
            )

    @property
    def allocated_array_bytes(self) -> int:
        return int(
            self.D.nbytes
            + self.H2.nbytes
            + self.H3.nbytes
            + self.B.nbytes
            + self.U.nbytes
            + self.L.nbytes
        )

    def _populate_baseline_arrays(self) -> int:
        if self.use_native_kernel:
            kernel = _get_native_kernel()
            total = int(
                kernel.init_baseline(
                    self.D.ctypes.data_as(ctypes.POINTER(ctypes.c_uint64)),
                    self._ticket_masks_arr.ctypes.data_as(ctypes.POINTER(ctypes.c_uint64)),
                    self.L.ctypes.data_as(ctypes.POINTER(ctypes.c_uint64)),
                    self.H2.ctypes.data_as(ctypes.POINTER(ctypes.c_uint32)),
                    self.H3.ctypes.data_as(ctypes.POINTER(ctypes.c_uint32)),
                    self.B.ctypes.data_as(ctypes.POINTER(ctypes.c_uint64)),
                    ctypes.c_size_t(self.M),
                )
            )
            return total

        all49_u64 = np.uint64(ALL49)
        chunk_size = 1 << 19
        for start in range(0, self.M, chunk_size):
            end = min(start + chunk_size, self.M)
            d_chunk = self.D[start:end]
            e_chunk = all49_u64 & ~d_chunk
            h2_chunk = np.zeros(end - start, dtype=np.uint32)
            h3_chunk = np.zeros(end - start, dtype=np.uint32)
            for idx, tm in enumerate(self.ticket_masks):
                hits = np.bitwise_count(d_chunk & np.uint64(tm))
                bit = np.uint32(1 << idx)
                h3_chunk |= np.where(hits >= 3, bit, np.uint32(0))
                h2_chunk |= np.where(hits == 2, bit, np.uint32(0))
            self.H2[start:end] = h2_chunk
            self.H3[start:end] = h3_chunk
            b_chunk = np.where(h3_chunk != 0, e_chunk, self.L[h2_chunk] & e_chunk)
            self.B[start:end] = b_chunk
        return int(np.bitwise_count(self.B).sum(dtype=np.int64))

    def ensure_u_for_retained(
        self, retained_indices: Sequence[int], retained_bitmask: int | None = None
    ) -> bool:
        """Ensure U[0..M-1] holds the coverage mask for the exact 14 retained ticket indices.

        Returns True if U was reused from cache, False if U was recomputed.
        """

        retained_tuple = tuple(retained_indices)
        if (
            len(retained_tuple) != RETAINED_TICKET_COUNT
            or len(set(retained_tuple)) != RETAINED_TICKET_COUNT
            or retained_tuple != tuple(sorted(retained_tuple))
            or any(not 0 <= i < PORTFOLIO_SIZE for i in retained_tuple)
        ):
            raise SixTicketSwapError(f"Illegal 14-ticket retained indices: {retained_tuple}")

        computed_mask = 0
        for i in retained_tuple:
            computed_mask |= 1 << i
        if retained_bitmask is not None and retained_bitmask != computed_mask:
            raise SixTicketSwapError("retained_bitmask does not match retained_indices")

        if (
            self._current_u_retained_indices == retained_tuple
            and self._current_u_retained_bitmask == computed_mask
        ):
            self.u_reuse_count += 1
            return True

        if self.use_native_kernel:
            kernel = _get_native_kernel()
            kernel.update_u(
                self.D.ctypes.data_as(ctypes.POINTER(ctypes.c_uint64)),
                self.H2.ctypes.data_as(ctypes.POINTER(ctypes.c_uint32)),
                self.H3.ctypes.data_as(ctypes.POINTER(ctypes.c_uint32)),
                self.L.ctypes.data_as(ctypes.POINTER(ctypes.c_uint64)),
                ctypes.c_uint32(computed_mask),
                self.U.ctypes.data_as(ctypes.POINTER(ctypes.c_uint64)),
                ctypes.c_size_t(self.M),
            )
        else:
            all49_u64 = np.uint64(ALL49)
            k_u32 = np.uint32(computed_mask)
            chunk_size = 1 << 19
            for start in range(0, self.M, chunk_size):
                end = min(start + chunk_size, self.M)
                d_chunk = self.D[start:end]
                e_chunk = all49_u64 & ~d_chunk
                h3_masked = self.H3[start:end] & k_u32
                h2_masked = self.H2[start:end] & k_u32
                self.U[start:end] = np.where(
                    h3_masked != 0, e_chunk, self.L[h2_masked] & e_chunk
                )

        self._current_u_retained_indices = retained_tuple
        self._current_u_retained_bitmask = computed_mask
        self.u_recompute_count += 1
        return False

    def score_candidate(
        self,
        retained_indices: Sequence[int],
        added_masks: Sequence[int],
        *,
        retained_bitmask: int | None = None,
        require_full_draw_space: bool = True,
        max_slices: int | None = None,
    ) -> CandidateScoreResult:
        """Score one 6-ticket swap candidate over all D slices in the cache."""

        if (
            len(added_masks) != CHANGED_TICKET_COUNT
            or len(set(added_masks)) != CHANGED_TICKET_COUNT
        ):
            raise SixTicketSwapError("Candidate must supply 6 distinct added ticket masks")
        for m in added_masks:
            if type(m) is not int or m < 0 or (m & ~ALL49) or popcount64(m) != TICKET_SIZE:
                raise SixTicketSwapError(f"Illegal added ticket mask: {m!r}")

        slices_to_scan = self.M if max_slices is None else min(max_slices, self.M)
        if require_full_draw_space and slices_to_scan != MAIN_DRAW_COUNT:
            raise SixTicketSwapError(
                f"AC6 violation: candidate scan covers {slices_to_scan} slices, "
                f"requires full {MAIN_DRAW_COUNT} main-draw space"
            )

        u_reused = self.ensure_u_for_retained(retained_indices, retained_bitmask)
        retained_set = set(retained_indices)
        for idx in retained_set:
            if self.ticket_masks[idx] in set(added_masks):
                raise SixTicketSwapError("Added ticket duplicates a retained ticket")

        t0, t1, t2, t3, t4, t5 = (
            added_masks[0],
            added_masks[1],
            added_masks[2],
            added_masks[3],
            added_masks[4],
            added_masks[5],
        )

        if self.use_native_kernel:
            kernel = _get_native_kernel()
            out_gain = ctypes.c_int64(0)
            out_loss = ctypes.c_int64(0)
            scanned = int(
                kernel.score_candidate(
                    self.D.ctypes.data_as(ctypes.POINTER(ctypes.c_uint64)),
                    self.B.ctypes.data_as(ctypes.POINTER(ctypes.c_uint64)),
                    self.U.ctypes.data_as(ctypes.POINTER(ctypes.c_uint64)),
                    ctypes.c_uint64(t0),
                    ctypes.c_uint64(t1),
                    ctypes.c_uint64(t2),
                    ctypes.c_uint64(t3),
                    ctypes.c_uint64(t4),
                    ctypes.c_uint64(t5),
                    ctypes.c_size_t(slices_to_scan),
                    ctypes.byref(out_gain),
                    ctypes.byref(out_loss),
                )
            )
            gain = int(out_gain.value)
            loss = int(out_loss.value)
        else:
            all49_u64 = np.uint64(ALL49)
            zero_u64 = np.uint64(0)
            gain = 0
            loss = 0
            scanned = 0
            chunk_size = 1 << 19
            for start in range(0, slices_to_scan, chunk_size):
                end = min(start + chunk_size, slices_to_scan)
                d_chunk = self.D[start:end]
                e_chunk = all49_u64 & ~d_chunk
                won = np.zeros(end - start, dtype=np.bool_)
                rescue = np.zeros(end - start, dtype=np.uint64)
                for tm in (t0, t1, t2, t3, t4, t5):
                    tm_u64 = np.uint64(tm)
                    hits = np.bitwise_count(d_chunk & tm_u64)
                    won |= hits >= 3
                    rescue |= np.where(hits == 2, tm_u64, zero_u64)
                a_chunk = np.where(won, e_chunk, rescue & e_chunk)
                b_chunk = self.B[start:end]
                u_chunk = self.U[start:end]
                gain += int(
                    np.bitwise_count(a_chunk & ~b_chunk & e_chunk).sum(dtype=np.int64)
                )
                loss += int(
                    np.bitwise_count(b_chunk & ~(u_chunk | a_chunk) & e_chunk).sum(
                        dtype=np.int64
                    )
                )
                scanned += end - start

        if scanned != slices_to_scan:
            raise SixTicketSwapError(f"Incomplete scan: {scanned} != {slices_to_scan}")

        delta = gain - loss
        new_count = self.baseline_full_count + delta
        return CandidateScoreResult(
            gain=gain,
            loss=loss,
            delta=delta,
            new_count=new_count,
            slices_scanned=scanned,
            u_reused=u_reused,
        )


# ---------------------------------------------------------------------------
# Section 十 (AC7): Independent 7-Set Oracle Loader & Verifier
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class IndependentOracleRecount:
    label: str
    portfolio_sha256: str
    covered_seven_sets: int
    seven_set_outcome_count: int
    official_evaluator_outcome_count: int
    primary_outcome_count: int
    matches_all: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "label": self.label,
            "portfolio_sha256": self.portfolio_sha256,
            "covered_seven_sets": self.covered_seven_sets,
            "seven_set_outcome_count": self.seven_set_outcome_count,
            "official_evaluator_outcome_count": self.official_evaluator_outcome_count,
            "primary_outcome_count": self.primary_outcome_count,
            "matches_all": self.matches_all,
        }


def load_independent_seven_set_oracle(repository: Path) -> tuple[ModuleType, Path, str]:
    """Load the pinned AC7 7-set oracle module and verify its SHA-256."""

    oracle_path = (repository.resolve() / INDEPENDENT_ORACLE_RELPATH).resolve()
    if not oracle_path.is_file():
        raise SixTicketSwapError(f"Missing independent 7-set oracle file: {oracle_path}")
    sha = hashlib.sha256(oracle_path.read_bytes()).hexdigest()
    if sha != INDEPENDENT_ORACLE_SHA256:
        raise SixTicketSwapError(
            f"Independent 7-set oracle SHA256 mismatch: expected {INDEPENDENT_ORACLE_SHA256}, "
            f"got {sha}"
        )
    spec = importlib.util.spec_from_file_location(
        "b649_k20_five_ticket_exact_repair_r1_oracle", oracle_path
    )
    if spec is None or spec.loader is None:
        raise SixTicketSwapError(f"Unable to load module spec from {oracle_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module, oracle_path, sha


def run_independent_recount(
    oracle_module: ModuleType,
    label: str,
    portfolio: Portfolio,
    *,
    primary_outcome_count: int,
    draws: UInt64Array | None = None,
) -> IndependentOracleRecount:
    """Recompute exact outcome count via 7-set oracle (7 * covered_subset_count) & official."""

    normalized = normalize_portfolio(portfolio)
    covered_fn = oracle_module.covered_subset_count
    outcome_fn = oracle_module.outcome_count

    covered_7 = int(covered_fn(normalized))
    oracle_outcomes = int(outcome_fn(normalized))
    if oracle_outcomes != SEVEN_SET_MULTIPLIER * covered_7:
        raise SixTicketSwapError(
            f"7-set oracle internal mismatch: {oracle_outcomes} != 7 * {covered_7}"
        )

    official_res = evaluate_portfolio(normalized, draws=draws)
    official_outcomes = int(official_res.official_any_prize_outcome_count)
    matches = oracle_outcomes == official_outcomes == primary_outcome_count
    return IndependentOracleRecount(
        label=label,
        portfolio_sha256=compact_json_sha256(normalized),
        covered_seven_sets=covered_7,
        seven_set_outcome_count=oracle_outcomes,
        official_evaluator_outcome_count=official_outcomes,
        primary_outcome_count=primary_outcome_count,
        matches_all=matches,
    )


# ---------------------------------------------------------------------------
# Section 十一: Resource Measurement, Durable Progress Journal & Exact Search
# ---------------------------------------------------------------------------


def current_peak_rss_bytes() -> int:
    """Return current process peak RSS in bytes."""

    self_rss = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    child_rss = int(resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss)
    peak = max(self_rss, child_rss)
    return peak if os.uname().sysname == "Darwin" else peak * 1024


def enforce_single_thread_env() -> dict[str, str]:
    """Verify and enforce single-worker, single-thread environment variables."""

    required = {
        "OMP_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
        "OPENBLAS_NUM_THREADS": "1",
        "NUMEXPR_NUM_THREADS": "1",
    }
    observed: dict[str, str] = {}
    for k, expected in required.items():
        val = os.environ.get(k)
        if val is None:
            os.environ[k] = expected
            val = expected
        if val != expected:
            raise SixTicketSwapError(f"Resource policy violation: {k}={val!r}, expected '1'")
        observed[k] = val
    return observed


def write_json_durably(path: Path, payload: Mapping[str, object]) -> str:
    """Atomically write JSON with fsync and return its SHA-256."""

    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (
        json.dumps(payload, sort_keys=True, indent=2, allow_nan=False) + "\n"
    ).encode("utf-8")
    staging = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with staging.open("wb") as stream:
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(staging, path)
    dir_fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)
    return hashlib.sha256(encoded).hexdigest()


def build_journal_identity(
    cache_identity: CacheIdentity,
    generator_keys_sha256: str,
    generator_output_sha256: str,
) -> dict[str, object]:
    """Build deterministic journal identity binding task, source, generator, and cache."""

    payload: dict[str, object] = {
        "task_id": TASK_ID,
        "pinned_source_head": PINNED_SOURCE_HEAD,
        "pinned_source_tree": PINNED_SOURCE_TREE,
        "baseline_sha256": BASELINE_PORTFOLIO_SHA256,
        "evaluator_sha256": OFFICIAL_EVALUATOR_SHA256,
        "generator_keys_sha256": generator_keys_sha256,
        "generator_output_sha256": generator_output_sha256,
        "cache_identity_sha256": cache_identity.sha256,
        "candidates_expected": EXPECTED_CANONICAL_KEYS,
    }
    payload["journal_identity_sha256"] = compact_json_sha256(payload)
    return payload


def load_or_init_journal(
    journal_path: Path,
    expected_identity: Mapping[str, object],
) -> dict[str, object]:
    """Load an existing task-owned journal without resetting cumulative budgets, or init new."""

    if not journal_path.exists():
        return {
            "TASK_ID": TASK_ID,
            "JOURNAL_IDENTITY": dict(expected_identity),
            "STATUS": "INITIALIZED",
            "RUN_COUNT": 0,
            "CANDIDATES_EXPECTED": EXPECTED_CANONICAL_KEYS,
            "NEXT_UNTESTED_INDEX": 0,
            "CANDIDATES_PROCESSED": 0,
            "CANDIDATES_EXACT_SCORED": 0,
            "CUMULATIVE_CPU_SECONDS": 0.0,
            "CUMULATIVE_WALL_SECONDS": 0.0,
            "PEAK_MEMORY_BYTES": current_peak_rss_bytes(),
            "CURRENT_BEST": None,
            "STRICT_GAIN_CANDIDATES": [],
            "UPDATED_AT_UTC": datetime.now(UTC).isoformat(),
        }

    loaded_raw: object = json.loads(journal_path.read_text(encoding="utf-8"))
    if not isinstance(loaded_raw, dict):
        raise SixTicketSwapError("Progress journal is not a JSON object")
    loaded = cast(dict[str, object], loaded_raw)
    if loaded.get("TASK_ID") != TASK_ID:
        raise SixTicketSwapError("Progress journal TASK_ID mismatch")
    if loaded.get("JOURNAL_IDENTITY") != dict(expected_identity):
        raise SixTicketSwapError("Progress journal identity mismatch; refusing to mix lineages")
    next_idx = loaded.get("NEXT_UNTESTED_INDEX")
    proc = loaded.get("CANDIDATES_PROCESSED")
    scored = loaded.get("CANDIDATES_EXACT_SCORED")
    if (
        type(next_idx) is not int
        or type(proc) is not int
        or type(scored) is not int
        or not (0 <= next_idx == proc == scored <= EXPECTED_CANONICAL_KEYS)
    ):
        raise SixTicketSwapError("Progress journal counters are inconsistent")
    cpu_prev = loaded.get("CUMULATIVE_CPU_SECONDS")
    wall_prev = loaded.get("CUMULATIVE_WALL_SECONDS")
    if not isinstance(cpu_prev, (int, float)) or not isinstance(wall_prev, (int, float)):
        raise SixTicketSwapError("Progress journal cumulative budgets are invalid")
    if cpu_prev < 0 or wall_prev < 0:
        raise SixTicketSwapError("Progress journal cumulative budgets cannot be negative")
    return loaded


def run_exact_search(
    repository: Path,
    worktree: Path,
    result_path: Path,
    journal_path: Path,
    *,
    max_candidates_this_invocation: int | None = None,
    cpu_budget_seconds: float = MAX_CUMULATIVE_CPU_SECONDS,
    wall_budget_seconds: float = MAX_WALL_SECONDS,
    memory_budget_bytes: int = MAX_TOTAL_MEMORY_BYTES,
) -> dict[str, object]:
    """Execute the full verified 2172 canonical exact search with durable progress journaling."""

    thread_env = enforce_single_thread_env()
    wall_t0 = time.monotonic()
    cpu_t0 = time.process_time()

    source_report = verify_source_identity(repository, worktree)
    _, specs, gen_summary = validate_generator_and_candidates(CANONICAL_BASELINE_TICKETS)
    fixture_summary = run_128_fixture_validation()
    oracle_module, oracle_path, oracle_sha = load_independent_seven_set_oracle(repository)

    cache = SixTicketBaselineCache(
        CANONICAL_BASELINE_TICKETS,
        use_native_kernel=True,
        expected_baseline_count=BASELINE_EXACT_COUNT,
    )
    validate_cache_identity(cache.identity.to_dict(), cache.identity)

    journal_identity = build_journal_identity(
        cache.identity,
        gen_summary.canonical_keys_sha256,
        gen_summary.ordered_generator_output_sha256,
    )
    journal = load_or_init_journal(journal_path, journal_identity)

    prior_cpu = float(cast(float | int, journal["CUMULATIVE_CPU_SECONDS"]))
    prior_wall = float(cast(float | int, journal["CUMULATIVE_WALL_SECONDS"]))
    run_count = int(cast(int, journal["RUN_COUNT"])) + 1
    next_index = int(cast(int, journal["NEXT_UNTESTED_INDEX"]))
    processed = int(cast(int, journal["CANDIDATES_PROCESSED"]))
    exact_scored = int(cast(int, journal["CANDIDATES_EXACT_SCORED"]))
    best_record = cast(dict[str, object] | None, journal.get("CURRENT_BEST"))
    strict_gain_records = list(
        cast(list[dict[str, object]], journal.get("STRICT_GAIN_CANDIDATES", []))
    )

    journal["RUN_COUNT"] = run_count
    journal["STATUS"] = "RUNNING"
    write_json_durably(journal_path, journal)

    def _elapsed_totals() -> tuple[float, float, int]:
        cur_cpu = prior_cpu + (time.process_time() - cpu_t0)
        cur_wall = prior_wall + (time.monotonic() - wall_t0)
        cur_mem = max(
            int(cast(int, journal.get("PEAK_MEMORY_BYTES", 0))),
            current_peak_rss_bytes(),
        )
        return cur_cpu, cur_wall, cur_mem

    budget_limit_reached = False
    verified_strict_gain_found = False
    independent_recounts: list[dict[str, object]] = []

    # Independent 7-set recount on baseline first (AC7)
    baseline_recount = run_independent_recount(
        oracle_module,
        "BASELINE",
        CANONICAL_BASELINE_TICKETS,
        primary_outcome_count=cache.baseline_full_count,
        draws=cache.D,
    )
    if not baseline_recount.matches_all:
        raise SixTicketSwapError(f"AC7 baseline independent recount failed: {baseline_recount}")
    independent_recounts.append(baseline_recount.to_dict())

    stop_index = EXPECTED_CANONICAL_KEYS
    if max_candidates_this_invocation is not None:
        stop_index = min(stop_index, next_index + max_candidates_this_invocation)

    while next_index < stop_index:
        cur_cpu, cur_wall, cur_mem = _elapsed_totals()
        if (
            cur_cpu >= cpu_budget_seconds
            or cur_wall >= wall_budget_seconds
            or cur_mem >= memory_budget_bytes
        ):
            budget_limit_reached = True
            break

        spec = specs[next_index]
        score = cache.score_candidate(
            spec.retained_indices,
            spec.added_masks,
            retained_bitmask=spec.retained_bitmask,
            require_full_draw_space=True,
        )
        if score.slices_scanned != MAIN_DRAW_COUNT:
            raise SixTicketSwapError("AC6 violation: candidate did not scan all 13983816 slices")

        candidate_entry: dict[str, object] = {
            "CANDIDATE_INDEX": spec.index,
            "CANONICAL_KEY": [list(part) for part in spec.key],
            "REMOVED_INDICES": list(spec.removed_indices),
            "RETAINED_INDICES": list(spec.retained_indices),
            "GAIN": score.gain,
            "LOSS": score.loss,
            "DELTA": score.delta,
            "EXACT_COUNT": score.new_count,
            "SLICES_SCANNED": score.slices_scanned,
            "PORTFOLIO_SHA256": spec.portfolio_sha256,
            "SLOT_PORTFOLIO_TICKETS": [list(t) for t in spec.slot_portfolio],
            "NORMALIZED_PORTFOLIO_TICKETS": [list(t) for t in spec.normalized_portfolio],
        }

        if best_record is None or (
            score.new_count > int(cast(int, best_record["EXACT_COUNT"]))
            or (
                score.new_count == int(cast(int, best_record["EXACT_COUNT"]))
                and spec.portfolio_sha256 < str(best_record["PORTFOLIO_SHA256"])
            )
        ):
            best_record = candidate_entry

        next_index += 1
        processed += 1
        exact_scored += 1

        if score.new_count > BASELINE_EXACT_COUNT:
            recount = run_independent_recount(
                oracle_module,
                f"STRICT_GAIN_CANDIDATE_{spec.index}",
                spec.normalized_portfolio,
                primary_outcome_count=score.new_count,
                draws=cache.D,
            )
            independent_recounts.append(recount.to_dict())
            candidate_entry["INDEPENDENT_RECOUNT"] = recount.to_dict()
            strict_gain_records.append(candidate_entry)
            if not recount.matches_all:
                raise SixTicketSwapError(
                    f"AC7 independent recount mismatch on strict gain candidate {spec.index}"
                )
            verified_strict_gain_found = True
            break

        if next_index % 250 == 0 or next_index == stop_index:
            cur_cpu, cur_wall, cur_mem = _elapsed_totals()
            journal.update(
                NEXT_UNTESTED_INDEX=next_index,
                CANDIDATES_PROCESSED=processed,
                CANDIDATES_EXACT_SCORED=exact_scored,
                CUMULATIVE_CPU_SECONDS=round(cur_cpu, 6),
                CUMULATIVE_WALL_SECONDS=round(cur_wall, 6),
                PEAK_MEMORY_BYTES=cur_mem,
                CURRENT_BEST=best_record,
                STRICT_GAIN_CANDIDATES=strict_gain_records,
                UPDATED_AT_UTC=datetime.now(UTC).isoformat(),
            )
            write_json_durably(journal_path, journal)

    # AC7 boundary checks (first and last canonical representatives, plus best candidate)
    if next_index == EXPECTED_CANONICAL_KEYS and not budget_limit_reached:
        last_idx = EXPECTED_CANONICAL_KEYS - 1
        for boundary_idx, label in (
            (0, "BOUNDARY_FIRST_CANONICAL_KEY_0"),
            (last_idx, f"BOUNDARY_LAST_CANONICAL_KEY_{last_idx}"),
        ):
            b_spec = specs[boundary_idx]
            b_score = cache.score_candidate(
                b_spec.retained_indices,
                b_spec.added_masks,
                retained_bitmask=b_spec.retained_bitmask,
                require_full_draw_space=True,
            )
            b_recount = run_independent_recount(
                oracle_module,
                label,
                b_spec.normalized_portfolio,
                primary_outcome_count=b_score.new_count,
                draws=cache.D,
            )
            if not b_recount.matches_all:
                raise SixTicketSwapError(f"AC7 boundary recount mismatch: {b_recount}")
            independent_recounts.append(b_recount.to_dict())

        if best_record is not None:
            best_idx = int(cast(int, best_record["CANDIDATE_INDEX"]))
            best_spec = specs[best_idx]
            best_count = int(cast(int, best_record["EXACT_COUNT"]))
            best_recount = run_independent_recount(
                oracle_module,
                f"BEST_CANDIDATE_{best_idx}",
                best_spec.normalized_portfolio,
                primary_outcome_count=best_count,
                draws=cache.D,
            )
            if not best_recount.matches_all:
                raise SixTicketSwapError(f"AC7 best candidate recount mismatch: {best_recount}")
            independent_recounts.append(best_recount.to_dict())

    final_cpu, final_wall, final_mem = _elapsed_totals()
    if (
        final_cpu > cpu_budget_seconds
        or final_wall > wall_budget_seconds
        or final_mem > memory_budget_bytes
    ):
        budget_limit_reached = True

    exact_mismatch_count = sum(
        0 if bool(r.get("matches_all")) else 1 for r in independent_recounts
    )

    if verified_strict_gain_found and not budget_limit_reached and exact_mismatch_count == 0:
        task_status = "SUCCESS"
        scientific_result = "NEW_VERIFIED_COVERAGE_GAIN"
        journal_status = "COMPLETE_SUCCESS"
        resource_budget_status = "PASS"
    elif (
        next_index == EXPECTED_CANONICAL_KEYS
        and not budget_limit_reached
        and exact_mismatch_count == 0
    ):
        task_status = "COMPLETE_NO_GAIN"
        scientific_result = "NO_STRICT_GAIN_IN_FIXED_FAMILY"
        journal_status = "COMPLETE_NO_GAIN"
        resource_budget_status = "PASS"
    else:
        task_status = "INCOMPLETE"
        scientific_result = "INCOMPLETE_BUDGET" if budget_limit_reached else "INCOMPLETE"
        journal_status = "PAUSED_INCOMPLETE"
        resource_budget_status = "LIMIT_REACHED" if budget_limit_reached else "PASS"

    journal.update(
        STATUS=journal_status,
        NEXT_UNTESTED_INDEX=next_index,
        CANDIDATES_PROCESSED=processed,
        CANDIDATES_EXACT_SCORED=exact_scored,
        CUMULATIVE_CPU_SECONDS=round(final_cpu, 6),
        CUMULATIVE_WALL_SECONDS=round(final_wall, 6),
        PEAK_MEMORY_BYTES=final_mem,
        CURRENT_BEST=best_record,
        STRICT_GAIN_CANDIDATES=strict_gain_records,
        UPDATED_AT_UTC=datetime.now(UTC).isoformat(),
    )
    journal_sha256 = write_json_durably(journal_path, journal)

    if best_record is None:
        best_exact_count = BASELINE_EXACT_COUNT
        best_delta = 0
        best_portfolio_sha256 = BASELINE_PORTFOLIO_SHA256
        best_portfolio_tickets = [list(t) for t in CANONICAL_BASELINE_TICKETS]
    else:
        best_exact_count = int(cast(int, best_record["EXACT_COUNT"]))
        best_delta = int(cast(int, best_record["DELTA"]))
        best_portfolio_sha256 = str(best_record["PORTFOLIO_SHA256"])
        best_portfolio_tickets = cast(
            list[list[int]], best_record["NORMALIZED_PORTFOLIO_TICKETS"]
        )

    new_gain_outcomes = max(0, best_exact_count - BASELINE_EXACT_COUNT)
    new_gain_pp = float(Fraction(new_gain_outcomes * 100, TOTAL_OUTCOMES))

    independent_status = (
        "PASS"
        if (independent_recounts and exact_mismatch_count == 0)
        else ("FAIL" if exact_mismatch_count > 0 else "NOT RUN")
    )
    independent_exact_count = (
        int(cast(int, independent_recounts[-1]["seven_set_outcome_count"]))
        if independent_recounts
        else BASELINE_EXACT_COUNT
    )

    result_payload: dict[str, object] = {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": task_status,
        "SCIENTIFIC_RESULT": scientific_result,
        "OWNER_DELTA_STATUS": "APPROVED_AND_APPLIED",
        "FABLE_EXECUTION_GATE": "PASS",
        "SOURCE_IDENTITY": {
            "ACTUAL_REPOSITORY": source_report.repository_path,
            "ACTUAL_WORKTREE": source_report.worktree_path,
            "ACTUAL_HEAD": source_report.actual_head,
            "ACTUAL_TREE": source_report.actual_tree,
            "BASELINE_GIT_BLOB": source_report.baseline_git_blob,
            "BASELINE_SHA256": source_report.baseline_sha256,
            "EVALUATOR_FILE_PATH": source_report.evaluator_file_path,
            "EVALUATOR_IMPORTED_PATH": source_report.evaluator_imported_path,
            "EVALUATOR_SHA256": source_report.evaluator_sha256,
            "INDEPENDENT_ORACLE_PATH": str(oracle_path),
            "INDEPENDENT_ORACLE_SHA256": oracle_sha,
        },
        "GENERATOR_SUMMARY": {
            "H_SUPPORT_TRIPLES": gen_summary.h_support_triples,
            "RAW_FIRST_LAYER_KEYS": gen_summary.raw_first_layer_keys,
            "H_FIXED_POINTS": gen_summary.h_fixed_points,
            "CANONICAL_KEYS": gen_summary.canonical_keys,
            "INVOLUTION_MISMATCHES": gen_summary.involution_mismatches,
            "UNCOVERED_KEYS": gen_summary.uncovered_keys,
            "DUPLICATE_KEYS": gen_summary.duplicate_keys,
            "ILLEGAL_CANDIDATES": gen_summary.illegal_candidates,
            "DISTINCT_PORTFOLIOS": gen_summary.distinct_portfolios,
            "GENERATOR_KEYS_SHA256": gen_summary.canonical_keys_sha256,
            "GENERATOR_OUTPUT_SHA256": gen_summary.ordered_generator_output_sha256,
        },
        "FIXTURE_SUMMARY": {
            "FIXTURE_EVENTS": fixture_summary.event_count,
            "FORWARD_OLD": fixture_summary.fwd_old,
            "FORWARD_NEW": fixture_summary.fwd_new,
            "FORWARD_GAIN": fixture_summary.fwd_gain,
            "FORWARD_LOSS": fixture_summary.fwd_loss,
            "FORWARD_DELTA": fixture_summary.fwd_delta,
            "REVERSE_OLD": fixture_summary.rev_old,
            "REVERSE_NEW": fixture_summary.rev_new,
            "REVERSE_DELTA": fixture_summary.rev_delta,
            "IDENTITY_OLD": fixture_summary.ident_old,
            "IDENTITY_NEW": fixture_summary.ident_new,
            "IDENTITY_DELTA": fixture_summary.ident_delta,
            "DIRECT_ORACLE_MISMATCHES": fixture_summary.direct_oracle_mismatches,
        },
        "CACHE_SUMMARY": {
            "CACHE_IDENTITY": cache.identity.to_dict(),
            "CACHE_IDENTITY_SHA256": cache.identity.sha256,
            "ALLOCATED_ARRAY_BYTES": cache.allocated_array_bytes,
            "U_RECOMPUTE_COUNT": cache.u_recompute_count,
            "U_REUSE_COUNT": cache.u_reuse_count,
        },
        "BASELINE_FULL_RECOUNT": "PASS",
        "BASELINE_FULL_COUNT": cache.baseline_full_count,
        "CANDIDATES_EXPECTED": EXPECTED_CANONICAL_KEYS,
        "CANDIDATES_PROCESSED": processed,
        "CANDIDATES_EXACT_SCORED": exact_scored,
        "NEXT_UNTESTED_INDEX": next_index,
        "BEST_EXACT_COUNT": best_exact_count,
        "BEST_DELTA": best_delta,
        "BEST_PORTFOLIO_SHA256": best_portfolio_sha256,
        "BEST_PORTFOLIO_TICKETS": best_portfolio_tickets,
        "BEST_CANDIDATE_DETAIL": best_record,
        "INDEPENDENT_RECOUNT": independent_status,
        "INDEPENDENT_EXACT_COUNT": independent_exact_count,
        "EXACT_MISMATCH_COUNT": exact_mismatch_count,
        "INDEPENDENT_RECOUNT_RECORDS": independent_recounts,
        "NEW_COVERAGE_GAIN_OUTCOMES": new_gain_outcomes,
        "NEW_COVERAGE_GAIN_PERCENTAGE_POINTS": new_gain_pp,
        "RESOURCE_METRICS": {
            "RESOURCE_POLICY": RESOURCE_POLICY,
            "CPU_WORKERS": CPU_WORKERS,
            "NUMERICAL_THREADS": NUMERICAL_THREADS,
            "THREAD_ENV": thread_env,
            "CPU_SECONDS": round(final_cpu, 6),
            "WALL_SECONDS": round(final_wall, 6),
            "PEAK_MEMORY_BYTES": final_mem,
            "MAX_TOTAL_MEMORY_BYTES": memory_budget_bytes,
            "MAX_CUMULATIVE_CPU_SECONDS": cpu_budget_seconds,
            "MAX_WALL_SECONDS": wall_budget_seconds,
            "RESOURCE_BUDGET_STATUS": resource_budget_status,
        },
        "PROGRESS_JOURNAL_LOCATOR": str(journal_path),
        "PROGRESS_JOURNAL_SHA256": journal_sha256,
        "COMPLETED_AT_UTC": datetime.now(UTC).isoformat(),
    }
    result_sha256 = write_json_durably(result_path, result_payload)
    result_payload["RESULT_LOCATOR"] = str(result_path)
    result_payload["RESULT_SHA256"] = result_sha256
    return result_payload


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Execute B649 K20 six-ticket triple cross-component matching swap exact search."
    )
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--worktree-root", type=Path, required=True)
    parser.add_argument("--result-path", type=Path, required=True)
    parser.add_argument("--journal-path", type=Path, required=True)
    parser.add_argument("--max-candidates", type=int, default=None)
    args = parser.parse_args(argv)

    result = run_exact_search(
        repository=args.repo_root.resolve(),
        worktree=args.worktree_root.resolve(),
        result_path=args.result_path.resolve(),
        journal_path=args.journal_path.resolve(),
        max_candidates_this_invocation=args.max_candidates,
    )
    summary = {
        "TASK_ID": result["TASK_ID"],
        "TASK_STATUS": result["TASK_STATUS"],
        "SCIENTIFIC_RESULT": result["SCIENTIFIC_RESULT"],
        "CANDIDATES_PROCESSED": result["CANDIDATES_PROCESSED"],
        "CANDIDATES_EXACT_SCORED": result["CANDIDATES_EXACT_SCORED"],
        "NEXT_UNTESTED_INDEX": result["NEXT_UNTESTED_INDEX"],
        "BEST_EXACT_COUNT": result["BEST_EXACT_COUNT"],
        "BEST_DELTA": result["BEST_DELTA"],
        "BEST_PORTFOLIO_SHA256": result["BEST_PORTFOLIO_SHA256"],
        "INDEPENDENT_RECOUNT": result["INDEPENDENT_RECOUNT"],
        "INDEPENDENT_EXACT_COUNT": result["INDEPENDENT_EXACT_COUNT"],
        "EXACT_MISMATCH_COUNT": result["EXACT_MISMATCH_COUNT"],
        "RESULT_SHA256": result["RESULT_SHA256"],
        "PROGRESS_JOURNAL_SHA256": result["PROGRESS_JOURNAL_SHA256"],
        "RESOURCE_METRICS": result["RESOURCE_METRICS"],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if result["TASK_STATUS"] in ("SUCCESS", "COMPLETE_NO_GAIN") else 1


if __name__ == "__main__":
    raise SystemExit(main())
