"""B649 K20 conditional diversity beam R2, pinned to the H R1 exact scorer."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import os
import subprocess
import sys
import time
from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

# Bound numerical-library helper threads before importing the reused scorer.
for _thread_env in (
    "OMP_NUM_THREADS",
    "MKL_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
):
    os.environ[_thread_env] = "1"

REPO_ROOT = Path(__file__).resolve().parents[3]
TASK_ID = "B649_K20_CONDITIONAL_GLOBAL_DIVERSITY_BEAM_R2"
R1_SOURCE_COMMIT = "bf8f41d72750f881f5a68188eb7cb3bab7b3c108"
R1_RESULT_COMMIT = "3cab702fc65235a9b0fa6b98ba29edfad11899b3"
R1_SOURCE_SHA256 = "5826a274ae6cfe2d7d6115d896752bea821131ff99e249c3b8c9a213bd123269"
R1_SOURCE_PATH = "src/lottolab/research/b649_k20_conditional_global_repair_beam_r1.py"
R1_RESULT_PATH = (
    "docs/research/matrix-native-results/"
    "b649-k20-conditional-global-repair-beam-r1-result.json"
)
R1_WORKTREE_RELATIVE = Path(
    ".claude/worktrees/b649-k20-global-residual-pool-repair-pilot-r1"
)
PREREG_PATH = Path(
    "docs/research/matrix-native-results/"
    "b649-k20-conditional-global-diversity-beam-r2-preregistration.md"
)
RESULT_PATH = Path(
    "docs/research/matrix-native-results/"
    "b649-k20-conditional-global-diversity-beam-r2-result.json"
)
FROZEN_RULE_SHA256 = "42afff9a38fc9b5e1a581a09dba5de61ca5f1e807bbf0744d0347ba5b95ebece"
EXPECTED_START_COUNT = 313239661
EXPECTED_START_SHA256 = "7ce41ff21d5c0821f1d5dda683e23114086f5024fc6d98d4e574df5306659b1e"
TICKET_UNIVERSE_SIZE = 13_983_816
BEAM_WIDTH = 16
EXPANSION_WIDTH = 8

_ACTIVE_DIVERSITY_CONTEXT: dict[str, Any] | None = None


def _git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=root, text=True).strip()


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _state_sha256(r1: Any, tickets: Sequence[Sequence[int]]) -> str:
    canonical = r1.canonical_state(tickets)
    payload = json.dumps([list(ticket) for ticket in canonical], separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _extend_package_path(package: Any, path: Path) -> None:
    current = list(package.__path__)
    value = str(path.resolve())
    if value not in current:
        package.__path__ = [value, *current]


def _bind_r1(reference_root: Path) -> tuple[Any, dict[str, Any], dict[str, Any]]:
    expected_root = (REPO_ROOT / R1_WORKTREE_RELATIVE).resolve()
    reference_root = reference_root.resolve()
    if reference_root != expected_root:
        raise RuntimeError(f"unexpected H R1 source root: {reference_root}")
    if _git(reference_root, "rev-parse", "HEAD") != R1_RESULT_COMMIT:
        raise RuntimeError("H R1 reuse worktree is not at the pinned result commit")
    if _git(reference_root, "status", "--porcelain=v1", "--untracked-files=all"):
        raise RuntimeError("H R1 reuse worktree is dirty; refusing to import it")

    result_path = reference_root / R1_RESULT_PATH
    source_path = reference_root / R1_SOURCE_PATH
    result_document = json.loads(result_path.read_text(encoding="utf-8"))
    if result_document.get("RUN_HEAD") != R1_SOURCE_COMMIT:
        raise RuntimeError("H R1 result source HEAD differs from the pinned source commit")
    if result_document.get("SOURCE_MODULE_SHA256") != R1_SOURCE_SHA256:
        raise RuntimeError("H R1 result source module hash differs from the pinned hash")
    if _file_sha256(source_path) != R1_SOURCE_SHA256:
        raise RuntimeError("H R1 source file does not match its result hash")

    main_src = REPO_ROOT / "src"
    if str(main_src) not in sys.path:
        sys.path.insert(0, str(main_src))
    import lottolab
    import lottolab.research

    _extend_package_path(lottolab, reference_root / "src" / "lottolab")
    _extend_package_path(lottolab.research, reference_root / "src" / "lottolab" / "research")
    from lottolab.research import b649_k20_conditional_global_repair_beam_r1 as r1

    if Path(r1.__file__ or "").resolve() != source_path.resolve():
        raise RuntimeError("Python resolved H R1 from an unexpected source path")
    if r1.REPO_ROOT.resolve() != reference_root:
        raise RuntimeError("H R1 module repository root does not match its pinned worktree")
    current_canonical_blob = _git(
        REPO_ROOT, "rev-parse", "HEAD:src/lottolab/research/b649_official_any_prize_exact.py"
    )
    reference_canonical_blob = _git(
        reference_root,
        "rev-parse",
        "HEAD:src/lottolab/research/b649_official_any_prize_exact.py",
    )
    if current_canonical_blob != reference_canonical_blob:
        raise RuntimeError("canonical evaluator blob differs between current and H R1 trees")

    start_count = result_document.get("START_COUNT")
    start_sha = result_document.get("START_SHA256")
    if (start_count, start_sha) != (EXPECTED_START_COUNT, EXPECTED_START_SHA256):
        raise RuntimeError("H R1 result start identity differs from the authorized fallback")
    return r1, result_document, {
        "REFERENCE_ROOT": str(reference_root),
        "REFERENCE_HEAD": R1_RESULT_COMMIT,
        "REFERENCE_BRANCH": _git(reference_root, "branch", "--show-current"),
        "REFERENCE_TRACKED_TREE": _git(reference_root, "rev-parse", "HEAD^{tree}"),
        "SOURCE_MODULE_SHA256": R1_SOURCE_SHA256,
        "RESULT_FILE_SHA256": _file_sha256(result_path),
        "CANONICAL_EVALUATOR_GIT_BLOB": reference_canonical_blob,
    }


def _bind_inputs(
    reference_root: Path,
    prereg_path: Path,
    output_path: Path,
) -> tuple[Any, dict[str, Any], dict[str, Any], dict[int, tuple[tuple[int, ...], ...]], dict[Any, Any]]:
    prereg_path = prereg_path.resolve()
    output_path = output_path.resolve()
    if prereg_path != (REPO_ROOT / PREREG_PATH).resolve():
        raise RuntimeError("unexpected preregistration path")
    if _file_sha256(prereg_path) != FROZEN_RULE_SHA256:
        raise RuntimeError("the frozen selection rule changed after preregistration")
    if output_path != (REPO_ROOT / RESULT_PATH).resolve():
        raise RuntimeError("unexpected result path")
    if output_path.exists():
        raise FileExistsError(f"refusing to overwrite {output_path}")

    r1, result_document, reference_identity = _bind_r1(reference_root)
    reuse_document = r1.read_reuse_artifact()
    reuse_sets, prior_sets = r1.load_prior_sets(reuse_document)
    result_sets = {
        4: tuple(tuple(int(p) for p in positions) for positions in result_document["DESTROY4_SETS"]),
        5: tuple(tuple(int(p) for p in positions) for positions in result_document["DESTROY5_SETS"]),
    }
    if result_sets != reuse_sets:
        raise RuntimeError("H R1 result destroy sets differ from its pinned reuse artifact")
    if len(result_sets[4]) != 3 or len(result_sets[5]) != 3:
        raise RuntimeError("H R1 must supply exactly three destroy-4 and three destroy-5 sets")
    if result_document.get("PARITY_MISMATCHES") != 0:
        raise RuntimeError("the pinned H R1 result does not have zero parity mismatches")
    return r1, result_document, reference_identity, result_sets, prior_sets


def _residual_signature_distance(
    r1: Any,
    remaining: Sequence[tuple[int, ...]],
    left: Any,
    right: Any,
    recounter: Any,
    cache: dict[tuple[str, str], int],
) -> int:
    left_sha = _state_sha256(r1, left.tickets)
    right_sha = _state_sha256(r1, right.tickets)
    pair_key = tuple(sorted((left_sha, right_sha)))
    cached = cache.get(pair_key)
    if cached is not None:
        return cached

    replacement_union = tuple(sorted(set(left.tickets) | set(right.tickets)))
    union_portfolio = r1.normalize_portfolio((*remaining, *replacement_union))
    union_count = recounter.count(union_portfolio)
    left_count = r1.SUBSET_SIZE * left.covered
    right_count = r1.SUBSET_SIZE * right.covered
    numerator = 2 * union_count - left_count - right_count
    if numerator < 0 or numerator % r1.SUBSET_SIZE:
        raise r1.StopConditionError(
            "RESIDUAL_SIGNATURE_DISTANCE_MISMATCH",
            f"invalid exact residual Hamming numerator {numerator}",
        )
    distance = numerator // r1.SUBSET_SIZE
    cache[pair_key] = distance
    return distance


def _check_residual_signature_distance_parity(r1: Any) -> dict[str, Any]:
    """Compare the exact count identity to direct residual signatures on a small lottery."""
    left = ((1, 2, 3, 4, 5, 6), (1, 7, 8, 9, 10, 11))
    right = ((2, 4, 6, 8, 10, 12), (3, 5, 7, 9, 11, 13))
    union = tuple(sorted(set(left) | set(right)))
    subsets = tuple(itertools.combinations(range(1, 15), 7))

    def residual_signature(portfolio: Sequence[Sequence[int]]) -> set[tuple[int, ...]]:
        return {
            subset
            for subset in subsets
            if not any(len(set(ticket) & set(subset)) >= 3 for ticket in portfolio)
        }

    left_signature = residual_signature(left)
    right_signature = residual_signature(right)
    direct_distance = len(left_signature ^ right_signature)
    evaluator = r1.five_ticket.evaluate_portfolio
    left_count = evaluator(
        left, pool_size=14, draw_size=6, outright_matches=3
    ).official_any_prize_outcome_count
    right_count = evaluator(
        right, pool_size=14, draw_size=6, outright_matches=3
    ).official_any_prize_outcome_count
    union_count = evaluator(
        union, pool_size=14, draw_size=6, outright_matches=3
    ).official_any_prize_outcome_count
    numerator = 2 * union_count - left_count - right_count
    if numerator < 0 or numerator % r1.SUBSET_SIZE:
        algebraic_distance = None
    else:
        algebraic_distance = numerator // r1.SUBSET_SIZE
    return {
        "POOL_SIZE": 14,
        "DRAW_SIZE": 6,
        "OUTRIGHT_MATCHES": 3,
        "SEVEN_SUBSETS_ENUMERATED": len(subsets),
        "DIRECT_SIGNATURE_SYMMETRIC_DIFFERENCE": direct_distance,
        "CANONICAL_OUTCOME_FORMULA_DISTANCE": algebraic_distance,
        "MISMATCHES": int(algebraic_distance != direct_distance),
    }


def _select_diverse(
    r1: Any,
    candidates: Sequence[Any],
    beam_width: int,
    remaining: Sequence[tuple[int, ...]],
    recounter: Any,
    context: dict[str, Any],
) -> tuple[Any, ...]:
    by_coverage: dict[int, list[Any]] = defaultdict(list)
    for state in candidates:
        by_coverage[state.covered].append(state)
    coverage_groups = [by_coverage[value] for value in sorted(by_coverage, reverse=True)]
    stats = context["STATS"]
    stats["TIE_GROUPS_ENCOUNTERED"] += sum(len(group) > 1 for group in coverage_groups)

    selected: list[Any] = []
    residual_cache: dict[tuple[str, str], int] = context["RESIDUAL_DISTANCE_CACHE"]
    for group in coverage_groups:
        slots = beam_width - len(selected)
        if slots <= 0:
            break
        if len(group) <= slots:
            selected.extend(sorted(group, key=lambda state: _state_sha256(r1, state.tickets)))
            continue

        stats["TIE_GROUPS_AT_CUTOFF"] += 1
        stats["TIE_STATES_DROPPED"] += len(group) - slots
        remaining_group = list(group)
        initial_slots = slots
        while slots:
            scored: list[tuple[tuple[int, int] | None, str, Any, dict[str, Any]]] = []
            for state in remaining_group:
                state_sha = _state_sha256(r1, state.tickets)
                if not selected:
                    scored.append((None, state_sha, state, {"NEAREST": []}))
                    continue
                pair_distances: list[tuple[int, int, Any]] = []
                for prior_state in selected:
                    structural = len(set(state.tickets) ^ set(prior_state.tickets))
                    pair_distances.append((structural, 0, prior_state))
                min_structural = min(item[0] for item in pair_distances)
                nearest_structural = [
                    item for item in pair_distances if item[0] == min_structural
                ]
                nearest = [
                    (
                        item[0],
                        _residual_signature_distance(
                            r1,
                            remaining,
                            state,
                            item[2],
                            recounter,
                            residual_cache,
                        ),
                        item[2],
                    )
                    for item in nearest_structural
                ]
                min_residual = min(item[1] for item in nearest)
                scored.append(
                    (
                        (min_structural, min_residual),
                        state_sha,
                        state,
                        {"NEAREST": nearest},
                    )
                )

            if all(item[0] is None for item in scored):
                best_distance = None
                tied = scored
            else:
                best_distance = max(item[0] for item in scored if item[0] is not None)
                tied = [item for item in scored if item[0] == best_distance]
            chosen = min(tied, key=lambda item: item[1])
            selected.append(chosen[2])
            remaining_group.remove(chosen[2])
            slots -= 1

            nearest_records = []
            for structural, residual, prior_state in chosen[3]["NEAREST"]:
                nearest_records.append(
                    {
                        "STATE_SHA256": _state_sha256(r1, prior_state.tickets),
                        "PARTIAL_REPLACEMENT_TICKET_SYMMETRIC_DIFFERENCE": structural,
                        "RESIDUAL_COVERAGE_SIGNATURE_HAMMING_7SUBSETS": residual,
                    }
                )
            context["DIVERSITY_DISTANCES"].append(
                {
                    "DESTROY_SIZE": context["DESTROY_SIZE"],
                    "DESTROY_POSITIONS": list(context["DESTROY_POSITIONS"]),
                    "LEVEL": context["LEVEL"],
                    "COVERAGE_SEVEN_SUBSETS": chosen[2].covered,
                    "COVERAGE_OFFICIAL_OUTCOMES": r1.SUBSET_SIZE * chosen[2].covered,
                    "COVERAGE_TIE_GROUP_SIZE": len(group),
                    "SLOTS_FOR_TIE_GROUP": initial_slots,
                    "GREEDY_SELECTION_INDEX": initial_slots - slots,
                    "STATE_SHA256": chosen[1],
                    "MIN_PARTIAL_REPLACEMENT_TICKET_SYMMETRIC_DIFFERENCE": (
                        None if best_distance is None else best_distance[0]
                    ),
                    "MIN_RESIDUAL_COVERAGE_SIGNATURE_HAMMING_7SUBSETS": (
                        None if best_distance is None else best_distance[1]
                    ),
                    "NEAREST_STATES_AT_MIN_STRUCTURAL_DISTANCE": nearest_records,
                }
            )
        break
    return tuple(selected)


def _run_search(
    r1: Any,
    universe: Any,
    remaining: Sequence[tuple[int, ...]],
    depth: int,
    *,
    base_covered: int,
    beam_width: int,
    expansion_width: int,
    inspect: Any,
    clock: Any,
    context: dict[str, Any],
) -> Any:
    if depth < 1 or beam_width < 1 or expansion_width < 1:
        raise ValueError("depth, beam width and expansion width must be positive")
    remaining = tuple(remaining)
    subset_total = __import__("math").comb(universe.pool_size, r1.SUBSET_SIZE)
    beam = (r1.BeamState((), base_covered),)
    expansions: list[Any] = []
    levels: list[Any] = []
    for level in range(1, depth + 1):
        context["LEVEL"] = level
        children: dict[tuple[tuple[int, ...], ...], Any] = {}
        generated = 0
        duplicates = 0
        for parent in beam:
            started = clock()
            frozen = (*remaining, *parent.tickets)
            scores = r1.score_all_tickets(universe, frozen)
            residual = subset_total - parent.covered
            try:
                identities = r1.check_score_identities(scores, universe, residual)
            except AssertionError as error:
                raise r1.StopConditionError(
                    "CONDITIONAL_ENUMERATION_IDENTITY_REFUTED", str(error)
                ) from error
            if scores.tickets_scored != TICKET_UNIVERSE_SIZE:
                raise r1.StopConditionError(
                    "GLOBAL_TICKET_UNIVERSE_MISMATCH",
                    f"scored {scores.tickets_scored}, expected {TICKET_UNIVERSE_SIZE}",
                )
            frozen_indices = [universe.index_of(ticket) for ticket in frozen]
            chosen_indices = r1.next_ticket_indices(
                scores.marginals, universe.tickets, frozen_indices, expansion_width
            )
            next_tickets = tuple(
                r1.NextTicket(
                    universe.ticket_at(int(index)),
                    int(index),
                    int(scores.marginals[index]),
                    position,
                )
                for position, index in enumerate(chosen_indices, start=1)
            )
            expansion = r1.Expansion(
                level,
                parent,
                residual,
                identities,
                next_tickets,
                r1.cutoff_stats(scores.marginals, frozen_indices, next_tickets[-1].marginal),
                clock() - started,
            )
            if inspect is not None:
                inspect(expansion, scores, frozen)
            expansions.append(expansion)
            context["EXPANSIONS_COMPLETED"] += 1
            if context["EXPANSIONS_COMPLETED"] % 8 == 0:
                print(
                    json.dumps(
                        {
                            "EVENT": "EXACT_STATE_SCORING_PROGRESS",
                            "DESTROY_SIZE": context["DESTROY_SIZE"],
                            "DESTROY_POSITIONS": list(context["DESTROY_POSITIONS"]),
                            "POLICY": context["POLICY"],
                            "LEVEL": level,
                            "EXPANSIONS_COMPLETED": context["EXPANSIONS_COMPLETED"],
                            "TICKETS_SCORED_THIS_STATE": scores.tickets_scored,
                            "SECONDS_THIS_STATE": round(expansion.seconds, 3),
                        },
                        sort_keys=True,
                    ),
                    flush=True,
                )

            for child in next_tickets:
                generated += 1
                state_tickets = r1.canonical_state((*parent.tickets, child.ticket))
                covered = parent.covered + child.marginal
                existing = children.get(state_tickets)
                if existing is not None:
                    duplicates += 1
                    if existing.covered != covered:
                        raise r1.StopConditionError(
                            "PARITY_MISMATCH",
                            f"same child set has different exact coverage: {state_tickets}",
                        )
                    continue
                children[state_tickets] = r1.BeamState(
                    state_tickets,
                    covered,
                    parent.tickets,
                    child.ticket,
                    child.marginal,
                    child.position,
                )

        candidates = tuple(sorted(children.values(), key=r1.retention_key))
        if context["POLICY"] == "DIVERSITY":
            retained = _select_diverse(
                r1,
                candidates,
                beam_width,
                remaining,
                context["RECORDER"],
                context,
            )
        elif context["POLICY"] == "SHA_IDENTITY":
            retained = candidates[:beam_width]
        else:
            raise ValueError(f"unknown retention policy {context['POLICY']}")
        levels.append(r1.BeamLevel(level, generated, duplicates, candidates, retained))
        beam = retained
    return r1.BeamRun(
        remaining,
        base_covered,
        depth,
        beam_width,
        expansion_width,
        tuple(expansions),
        tuple(levels),
    )


def _run_diversity_beam(
    r1: Any,
    universe: Any,
    size: int,
    positions: Sequence[int],
    *,
    recounter: Any,
    tally: Any,
    prior: Any,
    context: dict[str, Any],
) -> Any:
    global _ACTIVE_DIVERSITY_CONTEXT
    original_run_beam = r1.run_beam

    def diverse_runner(
        universe_arg: Any,
        remaining_arg: Sequence[tuple[int, ...]],
        depth_arg: int,
        *,
        base_covered: int,
        beam_width: int = BEAM_WIDTH,
        expansion_width: int = EXPANSION_WIDTH,
        inspect: Any = None,
        clock: Any = time.perf_counter,
    ) -> Any:
        active = _ACTIVE_DIVERSITY_CONTEXT
        if active is None:
            raise RuntimeError("diversity runner has no active task context")
        return _run_search(
            r1,
            universe_arg,
            remaining_arg,
            depth_arg,
            base_covered=base_covered,
            beam_width=beam_width,
            expansion_width=expansion_width,
            inspect=inspect,
            clock=clock,
            context=active,
        )

    context["RECORDER"] = recounter
    context["EXPANSIONS_COMPLETED"] = 0
    _ACTIVE_DIVERSITY_CONTEXT = context
    r1.run_beam = diverse_runner
    try:
        return r1.beam_destroy_set(
            universe,
            size,
            positions,
            recounter=recounter,
            tally=tally,
            prior=prior,
            beam_width=BEAM_WIDTH,
            expansion_width=EXPANSION_WIDTH,
        )
    finally:
        r1.run_beam = original_run_beam
        _ACTIVE_DIVERSITY_CONTEXT = None


def _run_identity(root: Path) -> dict[str, str]:
    return {
        "RUN_BRANCH": _git(root, "branch", "--show-current"),
        "RUN_HEAD": _git(root, "rev-parse", "HEAD"),
        "RUN_TREE": _git(root, "rev-parse", "HEAD^{tree}"),
        "RUN_TRACKED_TREE_CLEAN": (
            "YES"
            if not _git(root, "status", "--porcelain=v1", "--untracked-files=no")
            else "NO"
        ),
    }


def _path_states(r1: Any, beam: Any, final_state: Any) -> list[tuple[tuple[int, ...], ...]]:
    current = final_state.tickets
    path: list[tuple[tuple[int, ...], ...]] = []
    for index in range(len(beam.run.levels) - 1, -1, -1):
        level = beam.run.levels[index]
        node = next((state for state in level.candidates if state.tickets == current), None)
        if node is None:
            raise r1.StopConditionError("BEST_PATH_RECONSTRUCTION_FAILED", str(current))
        path.append(node.tickets)
        if index == 0:
            break
        current = node.parent
    path.reverse()
    return path


def _set_summary(r1: Any, beam: Any, stats: Mapping[str, Any]) -> dict[str, Any]:
    best_portfolio = beam.best_portfolio
    final_ties = beam.run.final_ties()
    return {
        "DESTROY_SIZE": beam.size,
        "POSITIONS": list(beam.destroyed.positions),
        "BEAM_WIDTH": beam.run.beam_width,
        "CHILDREN_PER_STATE": beam.run.expansion_width,
        "CONDITIONAL_ENUMERATIONS": beam.run.enumerations,
        "GLOBAL_TICKETS_SCORED": beam.run.tickets_scored,
        "BEAM_STATES_GENERATED": beam.run.generated,
        "BEAM_STATES_UNIQUE": beam.run.unique,
        "BEAM_STATES_DUPLICATE": beam.run.duplicates,
        "BEAM_STATES_RETAINED": beam.run.retained,
        "BEST_COUNT": beam.best_count,
        "BEST_DELTA": beam.best_count - r1.START_COUNT,
        "BEST_PORTFOLIO_SHA256": r1.portfolio_sha256(best_portfolio),
        "BEST_CANONICAL_RECOUNT": beam.recount_of(beam.run.best),
        "FINAL_BEST_COUNT_TIES": len(final_ties),
        "FINAL_BEST_COUNT_TIES_CANONICALLY_RECOUNTED": r1.ties_recounted(beam),
        "TIE_GROUPS_ENCOUNTERED": stats["TIE_GROUPS_ENCOUNTERED"],
        "TIE_GROUPS_AT_CUTOFF": stats["TIE_GROUPS_AT_CUTOFF"],
        "TIE_STATES_DROPPED": stats["TIE_STATES_DROPPED"],
        "LEVELS": [
            {
                "LEVEL": level.level,
                "GENERATED": level.generated,
                "UNIQUE": level.unique,
                "DUPLICATES": level.duplicates,
                "RETAINED": len(level.retained),
                "COVERAGE_CUTOFF_SEVEN_SUBSETS": (
                    level.cutoff_covered if level.retained else None
                ),
                "CANDIDATES_TIED_AT_CUTOFF": (
                    level.candidates_tied_at_cutoff if level.retained else None
                ),
            }
            for level in beam.run.levels
        ],
    }


def _preflight(args: argparse.Namespace) -> dict[str, Any]:
    r1, result_document, reference_identity, sets, _priors = _bind_inputs(
        args.reference_root, args.preregistration, args.output
    )
    return {
        "PREFLIGHT": "PASS",
        "TASK_ID": TASK_ID,
        "FROZEN_RULE_SHA256": FROZEN_RULE_SHA256,
        "R1_SOURCE_COMMIT": R1_SOURCE_COMMIT,
        "R1_RESULT_COMMIT": R1_RESULT_COMMIT,
        "R1_RESULT_FILE_SHA256": reference_identity["RESULT_FILE_SHA256"],
        "START_COUNT": result_document["START_COUNT"],
        "START_SHA256": result_document["START_SHA256"],
        "DESTROY4_SETS": [list(item) for item in sets[4]],
        "DESTROY5_SETS": [list(item) for item in sets[5]],
        "REFERENCE_WORKTREE": reference_identity["REFERENCE_ROOT"],
        "REFERENCE_TRACKED_TREE": reference_identity["REFERENCE_TRACKED_TREE"],
        "CURRENT_TREE": _run_identity(REPO_ROOT),
        "OUTPUT_ABSENT": not args.output.exists(),
        "SCIENTIFIC_SCORING_STARTED": "NO",
        "PROTECTED_LANE_3_TOUCHED": "NO",
        "PROJECT_MEMORY_WRITE": "NO",
    }


def run_experiment(args: argparse.Namespace) -> dict[str, Any]:
    wall_started = time.perf_counter()
    r1, h_r1_result, reference_identity, sets, prior_sets = _bind_inputs(
        args.reference_root, args.preregistration, args.output
    )
    run_identity = _run_identity(REPO_ROOT)
    if run_identity["RUN_BRANCH"] != "main" or run_identity["RUN_HEAD"] != "76085ccc8f226c8752cc7df28390e27009d21746":
        raise RuntimeError("current checkout changed after protocol freeze; re-read before execution")

    universe = r1.build_universe()
    canonical = r1.CanonicalRecounter()
    recounter = r1.CachedRecounter(canonical)
    start_record = r1.reproduce_start(canonical)
    if (
        not start_record.get("MATCH")
        or start_record.get("CANONICAL_RECOUNT") != EXPECTED_START_COUNT
        or start_record.get("START_SHA256") != EXPECTED_START_SHA256
    ):
        raise r1.StopConditionError("START_REPRODUCTION_MISMATCH", json.dumps(start_record))
    pinned_elite_recounts = r1.verify_pins(canonical)
    if not pinned_elite_recounts:
        raise r1.StopConditionError("PINNED_ELITE_RECOUNT_FAILED", "no pin records returned")

    residual_signature_parity = _check_residual_signature_distance_parity(r1)

    parity = r1.run_parity(universe, recounter)
    print(
        json.dumps(
            {
                "EVENT": "PARITY_COMPLETE",
                "PARITY_SAMPLE_COUNT": parity["PARITY_SAMPLE_COUNT"],
                "PARITY_MISMATCHES": parity["PARITY_MISMATCHES"],
                "REAL_CONDITIONAL_MARGINAL_CHECKS": parity[
                    "REAL_CONDITIONAL_MARGINAL_CHECKS"
                ],
            },
            sort_keys=True,
        ),
        flush=True,
    )
    if (
        parity["PARITY_MISMATCHES"] != 0
        or residual_signature_parity["MISMATCHES"] != 0
        or not parity["COVERAGE_MEETS_PACKET_MINIMUM"]
    ):
        raise r1.StopConditionError(
            "PARITY_MISMATCH",
            json.dumps(
                {
                    "SCORER_PARITY": parity["PARITY_MISMATCHES"],
                    "RESIDUAL_SIGNATURE_PARITY": residual_signature_parity,
                },
                sort_keys=True,
            ),
        )

    control_positions = sets[4][0]
    control_prior = prior_sets[(4, control_positions)]
    control_tally = r1.ParityTally()
    control_beam = r1.beam_destroy_set(
        universe,
        4,
        control_positions,
        recounter=recounter,
        tally=control_tally,
        prior=control_prior,
        beam_width=8,
        expansion_width=8,
    )
    expected_control = next(
        row
        for row in h_r1_result["PER_DESTROY_SET"]
        if row["DESTROY_SIZE"] == 4 and tuple(row["POSITIONS"]) == control_positions
    )
    control_recount = control_beam.recount_of(control_beam.run.best)
    control_checks = {
        "BEST_COUNT": control_beam.best_count == expected_control["BEST_COUNT"],
        "BEST_PORTFOLIO_SHA256": (
            r1.portfolio_sha256(control_beam.best_portfolio)
            == expected_control["BEST_PORTFOLIO_SHA256"]
        ),
        "BEAM_STATES_GENERATED": (
            control_beam.run.generated == expected_control["BEAM_STATES_GENERATED"]
        ),
        "BEAM_STATES_RETAINED": (
            control_beam.run.retained == expected_control["BEAM_STATES_RETAINED"]
        ),
        "CONDITIONAL_ENUMERATIONS": (
            control_beam.run.enumerations == expected_control["CONDITIONAL_ENUMERATIONS"]
        ),
        "CANONICAL_RECOUNT": control_recount == expected_control["BEST_COUNT"],
        "FINAL_TIES_RECOUNTED": r1.ties_recounted(control_beam),
    }
    if not all(control_checks.values()):
        raise r1.StopConditionError(
            "R1_WIDTH8_CONTROL_MISMATCH", json.dumps(control_checks, sort_keys=True)
        )
    print(
        json.dumps(
            {
                "EVENT": "R1_WIDTH8_CONTROL_COMPLETE",
                "POSITIONS": list(control_positions),
                "BEST_COUNT": control_beam.best_count,
                "BEST_PORTFOLIO_SHA256": r1.portfolio_sha256(control_beam.best_portfolio),
                "MATCH": all(control_checks.values()),
            },
            sort_keys=True,
        ),
        flush=True,
    )

    beams: list[Any] = []
    diversity_stats: list[dict[str, Any]] = []
    all_distances: list[dict[str, Any]] = []
    main_tallies: list[Any] = []
    for size in (4, 5):
        for positions in sets[size]:
            stats: dict[str, Any] = {
                "TIE_GROUPS_ENCOUNTERED": 0,
                "TIE_GROUPS_AT_CUTOFF": 0,
                "TIE_STATES_DROPPED": 0,
            }
            context: dict[str, Any] = {
                "POLICY": "DIVERSITY",
                "DESTROY_SIZE": size,
                "DESTROY_POSITIONS": positions,
                "STATS": stats,
                "DIVERSITY_DISTANCES": all_distances,
                "RESIDUAL_DISTANCE_CACHE": {},
                "RECORDER": recounter,
                "EXPANSIONS_COMPLETED": 0,
            }
            tally = r1.ParityTally()
            beam = _run_diversity_beam(
                r1,
                universe,
                size,
                positions,
                recounter=recounter,
                tally=tally,
                prior=prior_sets[(size, positions)],
                context=context,
            )
            if any(
                expansion.tickets_scored != TICKET_UNIVERSE_SIZE
                for expansion in beam.run.expansions
            ):
                raise r1.StopConditionError(
                    "INCOMPLETE_TICKET_UNIVERSE_SCORE", f"{size}:{positions}"
                )
            beams.append(beam)
            main_tallies.append(tally)
            diversity_stats.append(
                {
                    "DESTROY_SIZE": size,
                    "POSITIONS": list(positions),
                    **stats,
                }
            )
            print(
                json.dumps(
                    {
                        "EVENT": "DIVERSITY_DESTROY_SET_COMPLETE",
                        "DESTROY_SIZE": size,
                        "POSITIONS": list(positions),
                        "CONDITIONAL_ENUMERATIONS": beam.run.enumerations,
                        "BEAM_STATES_GENERATED": beam.run.generated,
                        "BEAM_STATES_RETAINED": beam.run.retained,
                        "BEST_COUNT": beam.best_count,
                        "BEST_DELTA": beam.best_count - r1.START_COUNT,
                        "TIE_GROUPS_ENCOUNTERED": stats["TIE_GROUPS_ENCOUNTERED"],
                        "TIE_STATES_DROPPED": stats["TIE_STATES_DROPPED"],
                    },
                    sort_keys=True,
                ),
                flush=True,
            )

    best = r1.select_global_best(beams)
    best_portfolio = best.beam.portfolio_of(best.state)
    best_canonical_count = recounter.count(best_portfolio)
    global_ties_recounted = all(
        recounter.count(beam.portfolio_of(state)) == best.count
        for _sha, beam, state in best.ties
    )
    all_final_ties_recounted = all(r1.ties_recounted(beam) for beam in beams)
    canonical_recount_pass = (
        best_canonical_count == best.count
        and global_ties_recounted
        and all_final_ties_recounted
    )

    winning_size = best.beam.size
    winning_positions = best.beam.destroyed.positions
    sha_only_tally = r1.ParityTally()
    sha_only_beam = r1.beam_destroy_set(
        universe,
        winning_size,
        winning_positions,
        recounter=recounter,
        tally=sha_only_tally,
        prior=prior_sets[(winning_size, winning_positions)],
        beam_width=BEAM_WIDTH,
        expansion_width=EXPANSION_WIDTH,
    )
    best_path = _path_states(r1, best.beam, best.state)
    sha_only_final_states = {
        state.tickets for state in sha_only_beam.run.final.candidates
    }
    sha_only_found_best_state = best.state.tickets in sha_only_final_states
    sha_only_retained = [
        {state.tickets for state in level.retained} for level in sha_only_beam.run.levels
    ]
    missing_sha_only_prefixes = [
        depth
        for depth, state_tickets in enumerate(best_path[:-1], start=1)
        if state_tickets not in sha_only_retained[depth - 1]
    ]
    diverse_prefixes_retained = all(
        state_tickets
        in {state.tickets for state in level.retained}
        for state_tickets, level in zip(best_path[:-1], best.beam.run.levels[:-1], strict=True)
    )
    if not sha_only_found_best_state and (not missing_sha_only_prefixes or not diverse_prefixes_retained):
        raise r1.StopConditionError(
            "DIVERSITY_COUNTERFACTUAL_PATH_INCONSISTENT",
            "best terminal state is absent from SHA-only output without a verified retained-path split",
        )
    did_survive_only_by_diversity = (
        not sha_only_found_best_state and diverse_prefixes_retained
    )

    total_inline_mismatches = (
        control_tally.mismatches
        + sha_only_tally.mismatches
        + sum(tally.mismatches for tally in main_tallies)
    )
    total_inline_comparisons = (
        control_tally.comparisons
        + sha_only_tally.comparisons
        + sum(tally.comparisons for tally in main_tallies)
    )
    parity_mismatches = (
        int(parity["PARITY_MISMATCHES"])
        + residual_signature_parity["MISMATCHES"]
        + total_inline_mismatches
    )
    if parity_mismatches != 0:
        raise r1.StopConditionError("PARITY_MISMATCH", f"total mismatches={parity_mismatches}")

    per_destroy_set = []
    for beam, stats in zip(beams, diversity_stats, strict=True):
        per_destroy_set.append(_set_summary(r1, beam, stats))
    best_prior = prior_sets[(winning_size, winning_positions)]
    best_outside_top48 = r1.requires_ticket_outside_top48(best.state.tickets, best_prior)
    improved = best.count > r1.START_COUNT
    finding = (
        "ESTABLISHED"
        if best_outside_top48 and improved and canonical_recount_pass
        else "NOT_ESTABLISHED"
    )
    wall_seconds = time.perf_counter() - wall_started
    main_expansions = [exp for beam in beams for exp in beam.run.expansions]
    best_path_sha = [_state_sha256(r1, state) for state in best_path]
    document = {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "COMPLETE",
        "SCIENTIFIC_RESULT": "DIVERSITY_BEAM_STRICT_GAIN" if improved else "NO_STRICT_GAIN",
        "SEARCH_CLASS": "INTERACTION_AWARE_HEURISTIC_DIVERSITY_BEAM",
        "OPTIMALITY_STATUS": "HEURISTIC_BEAM_WIDTH_16_CHILDREN_8",
        "COMPLETE_N4_OPTIMUM": "NOT_CLAIMED",
        "COMPLETE_N5_OPTIMUM": "NOT_CLAIMED",
        "GLOBAL_K20_OPTIMUM": "NOT_CLAIMED",
        "NOT_CLAIMED": ["complete N4 optimum", "complete N5 optimum", "global K20 optimum"],
        "START_COUNT": r1.START_COUNT,
        "START_SHA256": r1.START_SHA256,
        "START_PORTFOLIO": r1._ticket_list(r1.START_PORTFOLIO),
        "START_REPRODUCTION": start_record,
        "PINNED_ELITE_RECOUNTS": pinned_elite_recounts,
        "START_SOURCE": h_r1_result["START_REPRODUCTION"],
        "R1_REUSE": {
            "SOURCE_COMMIT": R1_SOURCE_COMMIT,
            "RESULT_COMMIT": R1_RESULT_COMMIT,
            "SOURCE_MODULE_PATH": R1_SOURCE_PATH,
            "SOURCE_MODULE_SHA256": R1_SOURCE_SHA256,
            "RESULT_PATH": R1_RESULT_PATH,
            "RESULT_FILE_SHA256": reference_identity["RESULT_FILE_SHA256"],
            "REFERENCE_WORKTREE": reference_identity["REFERENCE_ROOT"],
            "H_R1_RESULT_STATUS": h_r1_result["SCIENTIFIC_RESULT"],
        },
        "FROZEN_RULE_PATH": str(PREREG_PATH),
        "FROZEN_RULE_SHA256": FROZEN_RULE_SHA256,
        "BEAM_DEFINITION": {
            "BEAM_WIDTH": BEAM_WIDTH,
            "CHILDREN_PER_STATE": EXPANSION_WIDTH,
            "DEPTH": {"DESTROY4": 4, "DESTROY5": 5},
            "TICKET_UNIVERSE_SIZE": TICKET_UNIVERSE_SIZE,
            "EXPANSION": (
                "every retained partial state conditions on R+S and exact-scores all legal tickets; "
                "the 8 largest conditional marginals are children, marginal ties by lexicographically "
                "lowest ticket; frozen tickets are illegal next tickets"
            ),
            "DEDUPLICATION": "canonical replacement-ticket sets; first generated parent owns provenance",
            "PRIMARY_RANK": "higher exact current coverage",
            "TIE_RETENTION": "greedy maximin lexicographic pair: replacement-set symmetric difference, then residual-signature Hamming distance",
            "RESIDUAL_SIGNATURE": "uncovered 7-number subsets after R+S",
            "RESIDUAL_DISTANCE_FORMULA": "(2*C(A_union_B)-C(A)-C(B))/7, exact canonical official-outcome recounts",
            "FINAL_STATE_TIE_BREAK": "lowest SHA-256 of compact canonical JSON for sorted partial replacement tickets",
            "RANDOM_TICKET_SAMPLING": "NONE",
            "PREFILTER": "NONE",
        },
        "DESTROY4_SETS": [list(item) for item in sets[4]],
        "DESTROY5_SETS": [list(item) for item in sets[5]],
        "BEAM_STATES_GENERATED": sum(beam.run.generated for beam in beams),
        "BEAM_STATES_UNIQUE": sum(beam.run.unique for beam in beams),
        "BEAM_STATES_DUPLICATE": sum(beam.run.duplicates for beam in beams),
        "BEAM_STATES_RETAINED": sum(beam.run.retained for beam in beams),
        "BEAM_STATES_DEFINITION": (
            "GENERATED before state deduplication; UNIQUE distinct child sets; RETAINED states kept over depths 1..D, root excluded"
        ),
        "TIE_GROUPS_ENCOUNTERED": sum(item["TIE_GROUPS_ENCOUNTERED"] for item in diversity_stats),
        "TIE_GROUPS_AT_CUTOFF": sum(item["TIE_GROUPS_AT_CUTOFF"] for item in diversity_stats),
        "TIE_STATES_DROPPED": sum(item["TIE_STATES_DROPPED"] for item in diversity_stats),
        "DIVERSITY_DISTANCES": all_distances,
        "CONDITIONAL_ENUMERATIONS": sum(beam.run.enumerations for beam in beams),
        "GLOBAL_TICKETS_SCORED": sum(beam.run.tickets_scored for beam in beams),
        "GLOBAL_TICKET_UNIVERSE_SIZE": TICKET_UNIVERSE_SIZE,
        "CONDITIONAL_ENUMERATION_SECONDS_MIN": round(min(exp.seconds for exp in main_expansions), 3),
        "CONDITIONAL_ENUMERATION_SECONDS_MAX": round(max(exp.seconds for exp in main_expansions), 3),
        "CONTROL_R1_WIDTH8": {
            "CONTROL_ROLE": "same first H R1 destroy-4 set, rerun with the original width-8 rule",
            "DESTROY_SIZE": 4,
            "POSITIONS": list(control_positions),
            "BEAM_WIDTH": 8,
            "CHILDREN_PER_STATE": 8,
            "BEST_COUNT": control_beam.best_count,
            "BEST_PORTFOLIO_SHA256": r1.portfolio_sha256(control_beam.best_portfolio),
            "CONDITIONAL_ENUMERATIONS": control_beam.run.enumerations,
            "BEAM_STATES_GENERATED": control_beam.run.generated,
            "BEAM_STATES_RETAINED": control_beam.run.retained,
            "CANONICAL_RECOUNT": control_recount,
            "CHECKS": control_checks,
            "STATUS": "PASS" if all(control_checks.values()) else "FAIL",
        },
        "WIDTH16_SHA_IDENTITY_COUNTERFACTUAL": {
            "DESTROY_SIZE": winning_size,
            "POSITIONS": list(winning_positions),
            "BEAM_WIDTH": BEAM_WIDTH,
            "CHILDREN_PER_STATE": EXPANSION_WIDTH,
            "TIE_RULE": "H R1 lowest canonical state identity (lexicographically lowest sorted replacement-ticket tuple)",
            "BEST_COUNT": sha_only_beam.best_count,
            "BEST_PORTFOLIO_SHA256": r1.portfolio_sha256(sha_only_beam.best_portfolio),
            "CONDITIONAL_ENUMERATIONS": sha_only_beam.run.enumerations,
            "BEAM_STATES_GENERATED": sha_only_beam.run.generated,
            "BEAM_STATES_RETAINED": sha_only_beam.run.retained,
            "BEST_DIVERSITY_STATE_GENERATED": sha_only_found_best_state,
            "BEST_PATH_PARTIAL_STATE_SHA256S": best_path_sha,
            "DIVERSITY_PREFIXES_RETAINED": diverse_prefixes_retained,
            "PREFIX_DEPTHS_MISSING_FROM_SHA_ONLY_BEAM": missing_sha_only_prefixes,
        },
        "DID_BEST_PATH_SURVIVE_ONLY_BECAUSE_OF_DIVERSITY_RULE": (
            "YES" if did_survive_only_by_diversity else "NO"
        ),
        "BEST_COUNT": best.count,
        "BEST_DELTA": best.count - r1.START_COUNT,
        "BEST_SHA256": best.sha256,
        "BEST_DESTROY_SET": {
            "DESTROY_SIZE": winning_size,
            "POSITIONS": list(winning_positions),
        },
        "BEST_REPLACEMENT_TICKETS": r1._ticket_list(best.state.tickets),
        "BEST_NEW_TICKETS": r1._ticket_list(sorted(set(best_portfolio) - set(r1.START_PORTFOLIO))),
        "BEST_REPLACED_INDICES": [
            index for index, ticket in enumerate(r1.START_PORTFOLIO) if ticket not in best_portfolio
        ],
        "BEST_PORTFOLIO": r1._ticket_list(best_portfolio),
        "BEST_CANONICAL_RECOUNT": best_canonical_count,
        "BEST_CANONICAL_RECOUNT_STATUS": "PASS" if canonical_recount_pass else "FAIL",
        "BEST_COUNT_TIE_COUNT": len(best.ties),
        "BEST_COUNT_TIES_ALL_CANONICALLY_RECOUNTED": global_ties_recounted,
        "DIVERSITY_BEAM_GAIN_ESTABLISHED": "YES" if improved else "NO",
        "INTERACTION_AWARE_FINDING": finding,
        "INTERACTION_AWARE_FINDING_RULE": (
            "ESTABLISHED only if the winner uses a ticket outside H R1's one-shot global top 48, strictly improves the start count, and passes canonical recount"
        ),
        "PARITY_SAMPLE_COUNT": parity["PARITY_SAMPLE_COUNT"],
        "PARITY_MISMATCHES": parity_mismatches,
        "PRE_BEAM_PARITY_MISMATCHES": parity["PARITY_MISMATCHES"],
        "RESIDUAL_SIGNATURE_DISTANCE_PARITY": residual_signature_parity,
        "REAL_CONDITIONAL_MARGINAL_CHECKS": parity["REAL_CONDITIONAL_MARGINAL_CHECKS"],
        "PARITY": parity,
        "INLINE_CHECKS": {
            "COMPARISONS": total_inline_comparisons,
            "MISMATCHES": total_inline_mismatches,
            "MAIN_BEAM_FAMILIES": [tally.detail() for tally in main_tallies],
            "CONTROL_FAMILIES": control_tally.detail(),
            "SHA_ONLY_COUNTERFACTUAL_FAMILIES": sha_only_tally.detail(),
        },
        "PER_DESTROY_SET": per_destroy_set,
        "CANONICAL_RECOUNTER_CALLS": canonical.calls,
        "WALL_SECONDS": round(wall_seconds, 3),
        "PEAK_MEMORY_BYTES": r1.peak_memory_bytes(),
        "CPU_POLICY": {
            "SCORING_PROCESSES": 1,
            "NUMERICAL_THREAD_ENV": {
                key: os.environ.get(key)
                for key in (
                    "OMP_NUM_THREADS",
                    "MKL_NUM_THREADS",
                    "OPENBLAS_NUM_THREADS",
                    "NUMEXPR_NUM_THREADS",
                    "VECLIB_MAXIMUM_THREADS",
                )
            },
        },
        "PROJECT_MEMORY_WRITE": "NO",
        "PUSH": "NO",
        "PR": "NOT_CREATED",
        "MERGE": "NO",
        "PRODUCTION_CHANGE": "NONE",
        "PROTECTED_LANE_3_TOUCHED": "NO",
        "RUNTIME_TRANSITION_OCCURRED": "NO",
        **run_identity,
        "R1_REFERENCE_IDENTITY": reference_identity,
        "R2_SOURCE_PATH": str(Path(__file__).relative_to(REPO_ROOT)),
        "R2_SOURCE_SHA256": _file_sha256(Path(__file__)),
        "RESULT_PATH": str(RESULT_PATH),
    }

    if not canonical_recount_pass:
        raise r1.StopConditionError("BEST_CANONICAL_RECOUNT_FAILED", json.dumps(best_canonical_count))
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite {args.output}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    r1.write_atomically(args.output, r1.canonical_json(document))
    print(
        json.dumps(
            {
                "EVENT": "RESULT_WRITTEN",
                "PATH": str(args.output),
                "BEST_COUNT": best.count,
                "BEST_DELTA": best.count - r1.START_COUNT,
                "BEST_SHA256": best.sha256,
                "PARITY_MISMATCHES": parity_mismatches,
            },
            sort_keys=True,
        ),
        flush=True,
    )
    return document


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="b649_k20_conditional_global_diversity_beam_r2")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("preflight", "run"):
        sub = subparsers.add_parser(command)
        sub.add_argument(
            "--repo-root", type=Path, default=REPO_ROOT, help="exact canonical repository root"
        )
        sub.add_argument(
            "--reference-root",
            type=Path,
            default=REPO_ROOT / R1_WORKTREE_RELATIVE,
            help="read-only H R1 reuse worktree at the pinned result commit",
        )
        sub.add_argument("--preregistration", type=Path, default=REPO_ROOT / PREREG_PATH)
        sub.add_argument("--output", type=Path, default=REPO_ROOT / RESULT_PATH)
    args = parser.parse_args(argv)
    if args.repo_root.resolve() != REPO_ROOT:
        raise RuntimeError("unexpected repository root")
    if args.command == "preflight":
        print(json.dumps(_preflight(args), indent=2, sort_keys=True))
        return 0
    document = run_experiment(args)
    print(
        "result={SCIENTIFIC_RESULT} best_count={BEST_COUNT} delta={BEST_DELTA} parity={PARITY_MISMATCHES}".format(
            **document
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
