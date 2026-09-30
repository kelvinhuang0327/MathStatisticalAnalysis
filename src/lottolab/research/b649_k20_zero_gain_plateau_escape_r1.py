"""Bounded zero-gain plateau pilot for the three-ticket single-number cycle.

The root family is exhausted. Only exact-zero portfolios enter the frontier;
each retained plateau state probes a fixed SHA-derived sample of ticket triples.
All scores come from the existing exact triple residual, and every positive
candidate and retained plateau state is checked by the canonical evaluator.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import os
import random
import subprocess
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import cast

from lottolab.research import b649_k20_three_ticket_single_number_cycle_r1 as cycle

TASK_ID = "B649_K20_ZERO_GAIN_PLATEAU_ESCAPE_PILOT_R1"
FAMILY_NAME = cycle.FAMILY_NAME
ROOT_COUNT = 313_239_661
ROOT_SHA256 = "7ce41ff21d5c0821f1d5dda683e23114086f5024fc6d98d4e574df5306659b1e"
ROOT_DONOR = (
    "docs/research/matrix-native-results/b649-k20-three-ticket-cycle-full-family-r1-result.json"
)
ROOT_DONOR_SHA256 = "2ba9308faa96518b8a75bb1ee8b1ddcf62e7cd66258c8f36999e48f68c676266"
RESULT_PATH = (
    "docs/research/matrix-native-results/b649-k20-zero-gain-plateau-escape-pilot-r1-result.json"
)
RUNTIME_DIR = ".task-data/B649_K20_ZERO_GAIN_PLATEAU_ESCAPE_PILOT_R1"
SCIENTIFIC_SCOPE = "BOUNDED_ZERO_GAIN_THREE_TICKET_CYCLE_PLATEAU_ESCAPE"
Triple = tuple[int, int, int]
_worker_draws: cycle.DrawMasks | None = None


@dataclass(frozen=True, slots=True)
class SearchConfig:
    max_plateau_depth: int = 3
    max_states_per_depth: int = 32
    max_total_plateau_states: int = 96
    escape_triple_sample_count: int = 64
    escape_seed: int = 20260930

    def __post_init__(self) -> None:
        if (
            min(
                self.max_plateau_depth,
                self.max_states_per_depth,
                self.max_total_plateau_states,
                self.escape_triple_sample_count,
            )
            < 1
        ):
            raise ValueError("all search bounds must be positive")


FROZEN_CONFIG = SearchConfig()


@dataclass(frozen=True, slots=True)
class MoveStep:
    parent_sha256: str
    child_sha256: str
    indices: Triple
    numbers: Triple
    direction: str
    count: int
    delta_from_root: int


@dataclass(frozen=True, slots=True)
class PlateauState:
    portfolio: cycle.Portfolio
    sha256: str
    depth: int
    path: tuple[MoveStep, ...]


@dataclass(frozen=True, slots=True)
class ScoredRow:
    sha256: str
    count: int
    numbers: Triple
    direction: str


@dataclass(frozen=True, slots=True)
class TripleResult:
    triple: Triple
    rows: tuple[ScoredRow, ...]
    raw_attempts: int
    legal_emissions: int
    within_triple_duplicates: int


@dataclass(frozen=True, slots=True)
class BestCandidate:
    portfolio: cycle.Portfolio
    sha256: str
    count: int
    path: tuple[MoveStep, ...]


def sample_triples(
    state_sha256: str,
    ticket_count: int,
    *,
    sample_count: int = FROZEN_CONFIG.escape_triple_sample_count,
    seed: int = FROZEN_CONFIG.escape_seed,
) -> tuple[Triple, ...]:
    """Choose triples solely from the frozen seed and this normalized state SHA."""
    if len(state_sha256) != 64 or any(char not in "0123456789abcdef" for char in state_sha256):
        raise ValueError("state SHA must be 64 lowercase hex characters")
    triples = tuple(itertools.combinations(range(ticket_count), 3))
    digest = hashlib.sha256(f"{seed}:{state_sha256}".encode()).digest()
    selected = random.Random(int.from_bytes(digest, "big")).sample(
        triples, min(sample_count, len(triples))
    )
    return tuple(sorted(selected))


def _init_worker(pool_size: int) -> None:
    global _worker_draws
    _worker_draws = cycle.load_draws(pool_size)


def score_triple(
    portfolio: cycle.Portfolio,
    expected_count: int,
    triple: Triple,
    pool_size: int,
    draws: cycle.DrawMasks,
) -> TripleResult:
    residual = cycle.build_triple_residual(portfolio, triple, pool_size=pool_size, draws=draws)
    if residual.outcome_count(tuple(portfolio[index] for index in triple)) != expected_count:
        raise AssertionError("parent count does not rebind in the exact triple residual")
    seen: set[str] = set()
    rows: list[ScoredRow] = []
    legal = duplicates = raw = 0
    for spec in cycle.iter_triple_cycle_specs(portfolio, triple, pool_size=pool_size):
        raw += 1
        emission = cycle.emit_spec(portfolio, spec, pool_size=pool_size)
        if emission is None:
            continue
        legal += 1
        if emission.sha256 in seen:
            duplicates += 1
            continue
        seen.add(emission.sha256)
        rows.append(
            ScoredRow(
                emission.sha256,
                residual.outcome_count(emission.added),
                spec.numbers,
                spec.direction,
            )
        )
    if raw != cycle.TRIPLE_RAW_ATTEMPTS:
        raise AssertionError("triple did not enumerate all 432 raw cycle attempts")
    return TripleResult(triple, tuple(rows), raw, legal, duplicates)


def _score_triple_worker(payload: tuple[cycle.Portfolio, int, Triple, int]) -> TripleResult:
    if _worker_draws is None:
        raise RuntimeError("worker draw space was not initialized")
    portfolio, expected_count, triple, pool_size = payload
    return score_triple(portfolio, expected_count, triple, pool_size, _worker_draws)


def reconstruct_emission(
    state: PlateauState, triple: Triple, row: ScoredRow, pool_size: int
) -> cycle.EmittedCycle:
    emitted = cycle.emit_spec(
        state.portfolio, cycle.RawCycleSpec(triple, row.numbers, row.direction), pool_size=pool_size
    )
    if emitted is None or emitted.sha256 != row.sha256:
        raise AssertionError("stored scored row cannot be reconstructed as the declared legal move")
    return emitted


class ZeroCollector:
    """Deterministic encounter-order frontier admission with global visited SHA."""

    def __init__(
        self,
        config: SearchConfig,
        root_count: int,
        visited: set[str],
        already_retained: int,
        next_depth: int,
    ) -> None:
        self.config = config
        self.root_count = root_count
        self.visited = visited
        self.already_retained = already_retained
        self.next_depth = next_depth
        self.seen_this_depth: set[str] = set()
        self.states: list[PlateauState] = []
        self.generated = 0
        self.deduplicated = 0

    def consider(
        self, parent: PlateauState, triple: Triple, row: ScoredRow, pool_size: int
    ) -> bool:
        if row.count != self.root_count or self.next_depth > self.config.max_plateau_depth:
            return False
        self.generated += 1
        if row.sha256 in self.visited or row.sha256 in self.seen_this_depth:
            self.deduplicated += 1
            return False
        self.seen_this_depth.add(row.sha256)
        if (
            len(self.states) >= self.config.max_states_per_depth
            or self.already_retained + len(self.states) >= self.config.max_total_plateau_states
        ):
            return False
        emitted = reconstruct_emission(parent, triple, row, pool_size)
        step = MoveStep(parent.sha256, row.sha256, triple, row.numbers, row.direction, row.count, 0)
        self.states.append(
            PlateauState(emitted.portfolio, row.sha256, self.next_depth, (*parent.path, step))
        )
        return True

    def finish(self) -> tuple[PlateauState, ...]:
        self.visited.update(state.sha256 for state in self.states)
        return tuple(self.states)


class BestTracker:
    def __init__(self, root_count: int, root_sha256: str, root_portfolio: cycle.Portfolio) -> None:
        self.root_count = root_count
        self.global_best = BestCandidate(root_portfolio, root_sha256, root_count, ())
        self.direct: BestCandidate | None = None
        self.plateau: BestCandidate | None = None
        self.history = [root_count]

    @staticmethod
    def _better(candidate: BestCandidate, incumbent: BestCandidate | None) -> bool:
        return (
            incumbent is None
            or candidate.count > incumbent.count
            or (candidate.count == incumbent.count and candidate.sha256 < incumbent.sha256)
        )

    def consider(self, candidate: BestCandidate, parent_depth: int) -> None:
        if candidate.count <= self.root_count:
            return
        if parent_depth == 0:
            if self._better(candidate, self.direct):
                self.direct = candidate
        elif self._better(candidate, self.plateau):
            self.plateau = candidate
        previous = self.global_best.count
        if self._better(candidate, self.global_best):
            self.global_best = candidate
        if self.global_best.count < previous:
            raise AssertionError("BEST_EVER decreased")
        if self.global_best.count > previous:
            self.history.append(self.global_best.count)


class TripleStore:
    """One atomic, identity-checked record per completed triple for same-run resume."""

    def __init__(self, directory: Path, manifest: dict[str, object]) -> None:
        self.directory = directory
        self.triples = directory / "triples"
        self.triples.mkdir(parents=True, exist_ok=True)
        path = directory / "manifest.json"
        if path.exists():
            if json.loads(path.read_text()) != manifest:
                raise RuntimeError("existing pilot manifest differs; refusing a second lineage")
        else:
            write_json_atomically(path, manifest)

    def path(self, state: PlateauState, triple: Triple) -> Path:
        return self.triples / state.sha256 / f"{triple[0]}-{triple[1]}-{triple[2]}.json"

    def read(self, state: PlateauState, triple: Triple) -> TripleResult | None:
        path = self.path(state, triple)
        if not path.exists():
            return None
        data = json.loads(path.read_text())
        if data["STATE_SHA256"] != state.sha256 or tuple(data["TRIPLE"]) != triple:
            raise RuntimeError("cached triple identity mismatch")
        rows = tuple(
            ScoredRow(str(sha), int(count), tuple(numbers), str(direction))
            for sha, count, numbers, direction in data["ROWS"]
        )
        return TripleResult(
            triple,
            rows,
            int(data["RAW_ATTEMPTS"]),
            int(data["LEGAL_EMISSIONS"]),
            int(data["WITHIN_TRIPLE_DUPLICATES"]),
        )

    def write(self, state: PlateauState, result: TripleResult) -> None:
        path = self.path(state, result.triple)
        if path.exists():
            raise RuntimeError("cached triple appeared during this execution")
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "STATE_SHA256": state.sha256,
            "TRIPLE": result.triple,
            "RAW_ATTEMPTS": result.raw_attempts,
            "LEGAL_EMISSIONS": result.legal_emissions,
            "WITHIN_TRIPLE_DUPLICATES": result.within_triple_duplicates,
            "ROWS": [[row.sha256, row.count, row.numbers, row.direction] for row in result.rows],
        }
        payload = (json.dumps(data, sort_keys=True, separators=(",", ":")) + "\n").encode()
        temp = path.with_name(path.name + f".{os.getpid()}.tmp")
        temp.write_bytes(payload)
        os.replace(temp, path)

    def ledger_sha256(self) -> str:
        digest = hashlib.sha256()
        for path in sorted(self.triples.rglob("*.json")):
            digest.update(str(path.relative_to(self.directory)).encode() + b"\0")
            digest.update(hashlib.sha256(path.read_bytes()).digest())
        return digest.hexdigest()


def _git_identity(repo_root: Path) -> dict[str, str]:
    def rev(expression: str) -> str:
        return subprocess.check_output(
            ["git", "-C", str(repo_root), "rev-parse", expression], text=True
        ).strip()

    return {"RUN_HEAD": rev("HEAD"), "RUN_TREE": rev("HEAD^{tree}")}


def write_json_atomically(path: Path, payload: dict[str, object]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(payload, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
    staging = path.with_name(path.name + f".{os.getpid()}.tmp")
    staging.write_bytes(encoded)
    os.replace(staging, path)
    return hashlib.sha256(encoded).hexdigest()


def load_root(repo_root: Path, draws: cycle.DrawMasks) -> cycle.StartBinding:
    raw = (repo_root / ROOT_DONOR).read_bytes()
    if hashlib.sha256(raw).hexdigest() != ROOT_DONOR_SHA256:
        raise RuntimeError("root donor artifact bytes changed")
    donor = json.loads(raw)
    if (
        donor.get("TASK_ID") != "B649_K20_THREE_TICKET_CYCLE_FULL_FAMILY_R1"
        or donor.get("BEST_COUNT") != ROOT_COUNT
        or donor.get("BEST_PORTFOLIO_SHA256") != ROOT_SHA256
        or donor.get("BEST_CANONICAL_RECOUNT_STATUS") != "PASS"
    ):
        raise RuntimeError("root donor identity or canonical recount is not the frozen authority")
    return cycle.bind_start(
        donor["BEST_PORTFOLIO"],
        pool_size=49,
        expected_sha256=ROOT_SHA256,
        expected_outcome_count=ROOT_COUNT,
        draws=draws,
    )


def run_search(
    root: cycle.StartBinding,
    *,
    draws: cycle.DrawMasks,
    config: SearchConfig,
    workers: int = 1,
    store: TripleStore | None = None,
    progress_path: Path | None = None,
) -> dict[str, object]:
    """Run the frozen pilot. With a store, completed triples resume without rescoring."""
    if workers < 1:
        raise ValueError("workers must be positive")
    root_state = PlateauState(root.portfolio, root.sha256, 0, ())
    visited = {root.sha256}
    tracker = BestTracker(root.outcome_count, root.sha256, root.portfolio)
    recounts: dict[str, int] = {root.sha256: root.outcome_count}
    positive_recounts: set[str] = set()
    zero_recount_count = 0
    total_scored = root_raw = root_legal_raw = root_within_duplicate = root_cross_duplicate = 0
    escape_probes = plateau_generated = plateau_deduplicated = plateau_retained = 0
    root_negative = root_zero = root_positive = 0
    root_seen: set[str] = set()
    depth_reached = 0
    per_depth: list[dict[str, int]] = []
    all_triples = tuple(itertools.combinations(range(len(root.portfolio)), 3))
    executor = (
        ProcessPoolExecutor(
            max_workers=workers, initializer=_init_worker, initargs=(root.pool_size,)
        )
        if workers > 1
        else None
    )

    def recount(portfolio: cycle.Portfolio, sha256: str, expected: int) -> None:
        observed = recounts.get(sha256)
        if observed is None:
            observed = cycle.official_any_prize_outcome_count(
                portfolio, pool_size=root.pool_size, draws=draws
            )
            recounts[sha256] = observed
        if observed != expected:
            raise AssertionError(
                f"canonical recount mismatch for {sha256}: {observed} != {expected}"
            )

    def scan_state(
        state: PlateauState, triples: tuple[Triple, ...], collector: ZeroCollector | None
    ) -> tuple[int, int, int, int, int]:
        nonlocal total_scored, escape_probes
        futures = {
            triple: executor.submit(
                _score_triple_worker, (state.portfolio, root.outcome_count, triple, root.pool_size)
            )
            for triple in triples
            if executor is not None and (store is None or store.read(state, triple) is None)
        }
        seen_parent: set[str] = set()
        raw = legal = within_duplicates = cross_duplicates = processed = 0
        for triple in triples:
            cached = store.read(state, triple) if store is not None else None
            if cached is None:
                if executor is None:
                    result = score_triple(
                        state.portfolio, root.outcome_count, triple, root.pool_size, draws
                    )
                else:
                    result = futures[triple].result()
                if store is not None:
                    store.write(state, result)
            else:
                result = cached
            if result.triple != triple or result.raw_attempts != cycle.TRIPLE_RAW_ATTEMPTS:
                raise AssertionError("triple result violated the frozen move family")
            raw += result.raw_attempts
            legal += result.legal_emissions
            within_duplicates += result.within_triple_duplicates
            total_scored += len(result.rows)
            if state.depth > 0:
                escape_probes += 1
            for row in result.rows:
                if row.sha256 in seen_parent:
                    cross_duplicates += 1
                    continue
                seen_parent.add(row.sha256)
                if state.depth == 0:
                    root_seen.add(row.sha256)
                    if row.count < root.outcome_count:
                        nonlocal_root_counts[0] += 1
                    elif row.count == root.outcome_count:
                        nonlocal_root_counts[1] += 1
                    else:
                        nonlocal_root_counts[2] += 1
                if row.count == root.outcome_count and collector is not None:
                    collector.consider(state, triple, row, root.pool_size)
                elif row.count > root.outcome_count:
                    emission = reconstruct_emission(state, triple, row, root.pool_size)
                    recount(emission.portfolio, row.sha256, row.count)
                    positive_recounts.add(row.sha256)
                    step = MoveStep(
                        state.sha256,
                        row.sha256,
                        triple,
                        row.numbers,
                        row.direction,
                        row.count,
                        row.count - root.outcome_count,
                    )
                    tracker.consider(
                        BestCandidate(
                            emission.portfolio, row.sha256, row.count, (*state.path, step)
                        ),
                        state.depth,
                    )
            processed += 1
            if progress_path is not None and (processed % 20 == 0 or processed == len(triples)):
                write_json_atomically(
                    progress_path,
                    {
                        "PHASE": "ROOT" if state.depth == 0 else "PLATEAU",
                        "STATE_SHA256": state.sha256,
                        "STATE_DEPTH": state.depth,
                        "TRIPLES_DONE_FOR_STATE": processed,
                        "TRIPLES_FOR_STATE": len(triples),
                        "ROOT_FAMILY_LEGAL_SO_FAR": len(root_seen),
                        "PLATEAU_STATES_RETAINED_SO_FAR": plateau_retained,
                        "BEST_EVER_COUNT": tracker.global_best.count,
                    },
                )
                print(
                    json.dumps(
                        {
                            "DEPTH": state.depth,
                            "STATE": state.sha256[:12],
                            "TRIPLES_DONE": processed,
                            "TRIPLES_TOTAL": len(triples),
                            "BEST": tracker.global_best.count,
                        }
                    ),
                    flush=True,
                )
        return raw, legal, within_duplicates, cross_duplicates, len(seen_parent)

    nonlocal_root_counts = [0, 0, 0]
    try:
        collector = ZeroCollector(config, root.outcome_count, visited, 0, 1)
        root_raw, root_legal_raw, root_within_duplicate, root_cross_duplicate, unique = scan_state(
            root_state, all_triples, collector
        )
        if len(root_seen) != unique:
            raise AssertionError("root legal/deduplicated accounting mismatch")
        root_negative, root_zero, root_positive = nonlocal_root_counts
        if root_negative + root_zero + root_positive != len(root_seen):
            raise AssertionError(
                "root family sign classification does not cover unique legal moves"
            )
        if (
            root.pool_size == 49
            and len(root.portfolio) == 20
            and root_raw != cycle.K20_RAW_ATTEMPT_CAP
        ):
            raise AssertionError("root family did not exhaust the frozen 49/20 move family")
        if root_legal_raw - root_within_duplicate - root_cross_duplicate != len(root_seen):
            raise AssertionError("root legal/deduplicated accounting mismatch")
        frontier = collector.finish()
        plateau_generated += collector.generated
        plateau_deduplicated += collector.deduplicated
        plateau_retained += len(frontier)
        if frontier:
            depth_reached = 1
        per_depth.append(
            {
                "DEPTH": 1,
                "GENERATED": collector.generated,
                "DEDUPLICATED": collector.deduplicated,
                "RETAINED": len(frontier),
            }
        )
        for depth in range(1, config.max_plateau_depth + 1):
            if not frontier:
                break
            next_collector = (
                ZeroCollector(config, root.outcome_count, visited, plateau_retained, depth + 1)
                if depth < config.max_plateau_depth
                else None
            )
            for state in frontier:
                recount(state.portfolio, state.sha256, root.outcome_count)
                zero_recount_count += 1
                triples = sample_triples(
                    state.sha256,
                    len(state.portfolio),
                    sample_count=config.escape_triple_sample_count,
                    seed=config.escape_seed,
                )
                scan_state(state, triples, next_collector)
            if next_collector is None:
                break
            frontier = next_collector.finish()
            plateau_generated += next_collector.generated
            plateau_deduplicated += next_collector.deduplicated
            plateau_retained += len(frontier)
            if frontier:
                depth_reached = depth + 1
            per_depth.append(
                {
                    "DEPTH": depth + 1,
                    "GENERATED": next_collector.generated,
                    "DEDUPLICATED": next_collector.deduplicated,
                    "RETAINED": len(frontier),
                }
            )
        if plateau_retained > config.max_total_plateau_states:
            raise AssertionError("total plateau state cap was exceeded")
        if plateau_retained != sum(row["RETAINED"] for row in per_depth):
            raise AssertionError("per-depth plateau state accounting mismatch")
        if any(row["RETAINED"] > config.max_states_per_depth for row in per_depth):
            raise AssertionError("per-depth plateau state cap was exceeded")
        if depth_reached > config.max_plateau_depth:
            raise AssertionError("plateau depth cap was exceeded")
        expected_probes = plateau_retained * min(
            config.escape_triple_sample_count, len(all_triples)
        )
        if escape_probes != expected_probes:
            raise AssertionError("not every retained plateau state received its frozen probes")
        if any(count < root.outcome_count for count in tracker.history):
            raise AssertionError("BEST_EVER decreased below root")
    finally:
        if executor is not None:
            executor.shutdown(wait=True, cancel_futures=True)

    direct = tracker.direct
    plateau = tracker.plateau
    best = tracker.global_best
    if direct is not None:
        scientific_result = "DIRECT_ONLY_GAIN"
        plateau_escape = "NO"
    elif plateau is not None:
        scientific_result = "PLATEAU_ESCAPE"
        plateau_escape = "YES"
    else:
        scientific_result = "NO_IMPROVEMENT"
        plateau_escape = "NO"
    recount(best.portfolio, best.sha256, best.count)
    digest = hashlib.sha256()
    for sha256 in sorted(positive_recounts):
        digest.update(f"{sha256}:{recounts[sha256]}\n".encode())

    def best_json(candidate: BestCandidate | None) -> dict[str, object] | None:
        return (
            {
                "COUNT": candidate.count,
                "SHA256": candidate.sha256,
                "PATH_SHA256S": [root.sha256, *(step.child_sha256 for step in candidate.path)],
                "PATH_DELTAS": [0, *(step.delta_from_root for step in candidate.path)],
                "PATH_MOVES": [asdict(step) for step in candidate.path],
            }
            if candidate is not None
            else None
        )

    return {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "COMPLETE",
        "SCIENTIFIC_SCOPE": SCIENTIFIC_SCOPE,
        "MOVE_FAMILY": FAMILY_NAME,
        "CONFIG": asdict(config),
        "ROOT_COUNT": root.outcome_count,
        "ROOT_SHA256": root.sha256,
        "ROOT_CANONICAL_RECOUNT_STATUS": "PASS",
        "ROOT_FAMILY_RAW_ATTEMPTS": root_raw,
        "ROOT_FAMILY_LEGAL_RAW": root_legal_raw,
        "ROOT_FAMILY_LEGAL": len(root_seen),
        "ROOT_WITHIN_TRIPLE_DUPLICATES": root_within_duplicate,
        "ROOT_CROSS_TRIPLE_DUPLICATES": root_cross_duplicate,
        "ROOT_NEGATIVE_COUNT": root_negative,
        "ROOT_ZERO_COUNT": root_zero,
        "ROOT_POSITIVE_COUNT": root_positive,
        "PLATEAU_DEPTH_REACHED": depth_reached,
        "PLATEAU_STATES_GENERATED": plateau_generated,
        "PLATEAU_STATES_RETAINED": plateau_retained,
        "PLATEAU_STATES_DEDUPLICATED": plateau_deduplicated,
        "PLATEAU_PER_DEPTH": per_depth,
        "PLATEAU_CANONICAL_RECOUNTS": zero_recount_count,
        "ESCAPE_PROBES": escape_probes,
        "EXACT_CANDIDATES_SCORED": total_scored,
        "DIRECT_ROOT_IMPROVEMENT": "YES" if direct is not None else "NO",
        "PLATEAU_ESCAPE_ESTABLISHED": plateau_escape,
        "DIRECT_ROOT_BEST_COUNT": direct.count if direct is not None else None,
        "PLATEAU_BEST_COUNT": plateau.count if plateau is not None else None,
        "DIRECT_ROOT_BEST": best_json(direct),
        "PLATEAU_BEST": best_json(plateau),
        "BEST_COUNT": best.count,
        "BEST_DELTA": best.count - root.outcome_count,
        "BEST_SHA256": best.sha256,
        "BEST_PORTFOLIO": [list(ticket) for ticket in best.portfolio],
        "BEST_CANONICAL_RECOUNT_STATUS": "PASS",
        "BEST_EVER_HISTORY": tracker.history,
        "ESCAPE_PATH_LENGTH": len(best.path),
        "ESCAPE_PATH_SHA256S": [root.sha256, *(step.child_sha256 for step in best.path)],
        "ESCAPE_PATH_DELTAS": [0, *(step.delta_from_root for step in best.path)],
        "ESCAPE_PATH_MOVES": [asdict(step) for step in best.path],
        "POSITIVE_CANDIDATES_CANONICALLY_RECOUNTED": len(positive_recounts),
        "POSITIVE_RECOUNT_LEDGER_SHA256": digest.hexdigest(),
        "ALL_CLAIMED_IMPROVEMENTS_RECOUNT_STATUS": "PASS",
        "SCIENTIFIC_RESULT": scientific_result,
        "PROTECTED_LANE_3_TOUCHED": "NO",
        "ACTIVE_EXACT_REPAIR_TASK_TOUCHED": "NO",
        "FOUR_TICKET_TASK_TOUCHED": "NO",
        "ACCOUNTING_DEFINITIONS": {
            "ROOT_FAMILY_LEGAL": "unique normalized legal root emissions",
            "PLATEAU_STATES_GENERATED": "zero-count emissions considered before visited/depth caps",
            "PLATEAU_STATES_DEDUPLICATED": (
                "zero-count emissions already visited or seen at current depth"
            ),
            "PLATEAU_STATES_RETAINED": "accepted unique exact-zero frontier states",
            "ESCAPE_PROBES": "sampled ticket triples scored from retained plateau states",
            "EXACT_CANDIDATES_SCORED": "residual calls for legal, within-triple-unique emissions",
        },
    }


def run_pilot(repo_root: Path, *, workers: int = 2) -> dict[str, object]:
    repo_root = repo_root.resolve()
    result_path = repo_root / RESULT_PATH
    if result_path.exists():
        existing = json.loads(result_path.read_text())
        if existing.get("TASK_ID") != TASK_ID or existing.get("TASK_STATUS") != "COMPLETE":
            raise RuntimeError("existing pilot result has conflicting identity")
        return cast(dict[str, object], existing)
    draws = cycle.load_draws(49)
    root = load_root(repo_root, draws)
    config = FROZEN_CONFIG
    source_sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    store = TripleStore(
        repo_root / RUNTIME_DIR,
        {
            "TASK_ID": TASK_ID,
            "ROOT_SHA256": root.sha256,
            "ROOT_DONOR_SHA256": ROOT_DONOR_SHA256,
            "SOURCE_SHA256": source_sha,
            "CONFIG": asdict(config),
            "POOL_SIZE": root.pool_size,
        },
    )
    report = run_search(
        root,
        draws=draws,
        config=config,
        workers=workers,
        store=store,
        progress_path=repo_root / RUNTIME_DIR / "progress.json",
    )
    report.update(_git_identity(repo_root))
    report["ROOT_DONOR"] = ROOT_DONOR
    report["ROOT_DONOR_SHA256"] = ROOT_DONOR_SHA256
    report["SOURCE_SHA256"] = source_sha
    report["TRIPLE_LEDGER_SHA256"] = store.ledger_sha256()
    write_json_atomically(result_path, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()
    report = run_pilot(args.repo_root, workers=args.workers)
    print(
        json.dumps(
            {
                key: report[key]
                for key in (
                    "TASK_STATUS",
                    "SCIENTIFIC_RESULT",
                    "ROOT_FAMILY_LEGAL",
                    "BEST_COUNT",
                    "BEST_DELTA",
                    "PLATEAU_STATES_RETAINED",
                    "ESCAPE_PROBES",
                )
            }
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
