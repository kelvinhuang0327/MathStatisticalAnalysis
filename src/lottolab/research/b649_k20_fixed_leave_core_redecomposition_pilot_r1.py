"""Exact fixed-leave K20 core redecomposition pilot.

The core uses thirteen ticket slots. The incumbent frequency-three labels give
one triangle decomposition of a fixed 66-edge graph after removing the frozen
frequency-two pairs and the six-edge leave. This module regenerates every
decomposition, quotients by the color-preserving slot automorphism group, maps
the unlabeled orbit representatives to labels by the frozen rule, and scores
the resulting portfolios only with the canonical exact evaluator.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Final, cast

from lottolab.application.b649_sealed_geometry_portfolio import (
    SEALED_GEOMETRY_PORTFOLIOS,
    canonical_portfolio_sha256,
)
from lottolab.research.b649_official_any_prize_exact import (
    all_main_draw_masks,
    evaluate_portfolio,
)

type Triangle = tuple[int, int, int]
type Decomposition = tuple[int, ...]
type Permutation = tuple[int, ...]
type Ticket = tuple[int, ...]

TASK_ID: Final = "B649_K20_FIXED_LEAVE_CORE_REDECOMPOSITION_PILOT_R1"
FREQUENCY_3_LABELS: Final = (
    3,
    4,
    6,
    7,
    8,
    9,
    10,
    11,
    13,
    15,
    16,
    18,
    19,
    20,
    24,
    26,
    28,
    29,
    36,
    39,
    46,
    49,
)
CORE_SLOT_IDS: Final = (3, 4, 5, 6, 7, 9, 10, 11, 12, 13, 14, 15, 16)
PERIPHERY_SLOT_IDS: Final = (0, 1, 2, 8, 17, 18, 19)
ALL_SLOT_IDS: Final = tuple(range(20))
INCUMBENT_LABEL_TRIANGLES: Final[dict[int, Triangle]] = {
    3: (3, 4, 5),
    4: (3, 6, 7),
    6: (9, 10, 11),
    7: (6, 9, 12),
    8: (4, 12, 13),
    9: (5, 9, 13),
    10: (3, 10, 12),
    11: (10, 13, 14),
    13: (4, 9, 15),
    15: (3, 13, 15),
    16: (5, 10, 16),
    18: (7, 9, 14),
    19: (12, 15, 16),
    20: (7, 11, 13),
    24: (7, 10, 15),
    26: (3, 9, 16),
    28: (4, 7, 16),
    29: (5, 7, 12),
    36: (4, 6, 10),
    39: (5, 6, 11),
    46: (6, 13, 16),
    49: (6, 14, 15),
}
FROZEN_F_PAIRS: Final[dict[int, tuple[int, int]]] = {
    27: (3, 14),
    31: (4, 11),
    12: (5, 14),
    14: (11, 12),
    37: (11, 15),
    23: (14, 16),
}
EXPECTED_START_SHA256: Final = (
    "0045ac8837fc82e9a585d812173341ac12e05c5de201af7f8fedeacafa19e1ff"
)
EXPECTED_START_COUNT: Final = 313239661
EXPECTED_DECOMPOSITIONS: Final = 240_480
EXPECTED_SYMMETRY_ORDER: Final = 960
EXPECTED_CLASS_COUNT: Final = 262
EXPECTED_CLASS_SIZE_HISTOGRAM: Final = {240: 6, 480: 14, 960: 242}
EXPECTED_CANDIDATES: Final = 261
RESULT_PATH: Final = (
    Path(__file__).resolve().parents[3]
    / "docs/research/matrix-native-results/"
    "b649-k20-fixed-leave-core-redecomposition-pilot-r1-result.json"
)

START_TICKETS: Final = SEALED_GEOMETRY_PORTFOLIOS[20].tickets
START_BY_SLOT: Final[dict[int, Ticket]] = dict(zip(ALL_SLOT_IDS, START_TICKETS, strict=True))
FROZEN_F_EDGES: Final = tuple(sorted(tuple(sorted(pair)) for pair in FROZEN_F_PAIRS.values()))
_SLOT_INDEX: Final = {slot: index for index, slot in enumerate(CORE_SLOT_IDS)}
_ALL_CORE_PAIRS: Final[tuple[tuple[int, int], ...]] = tuple(
    (int(first), int(second)) for first, second in combinations(CORE_SLOT_IDS, 2)
)
_INCUMBENT_TRIANGLE_EDGE_SET: Final = {
    tuple(sorted(pair))
    for triangle in INCUMBENT_LABEL_TRIANGLES.values()
    for pair in combinations(triangle, 2)
}
FIXED_LEAVE_EDGES: Final = tuple(
    sorted(
        set(_ALL_CORE_PAIRS)
        - _INCUMBENT_TRIANGLE_EDGE_SET
        - set(FROZEN_F_EDGES)
    )
)
_EDGE_IDS: Final[dict[tuple[int, int], int]] = {
    edge: index for index, edge in enumerate(_ALL_CORE_PAIRS)
}
_FROZEN_EDGE_SET: Final = set(FROZEN_F_EDGES)
_LEAVE_EDGE_SET: Final = set(FIXED_LEAVE_EDGES)
_FORBIDDEN_EDGE_SET: Final = _FROZEN_EDGE_SET | _LEAVE_EDGE_SET
_AVAILABLE_EDGE_MASK: Final = sum(
    1 << edge_id
    for edge, edge_id in _EDGE_IDS.items()
    if edge not in _FORBIDDEN_EDGE_SET
)


@dataclass(frozen=True, slots=True)
class CombinatorialResult:
    """Regenerated exact covers and their symmetry quotient."""

    decompositions: tuple[Decomposition, ...]
    symmetry_group: tuple[Permutation, ...]
    representatives: tuple[Decomposition, ...]
    class_size_histogram: tuple[tuple[int, int], ...]
    incumbent_representative: Decomposition


@dataclass(frozen=True, slots=True)
class Candidate:
    """One labeled portfolio derived from an unlabeled orbit representative."""

    representative: Decomposition
    representative_sha256: str
    tickets: tuple[Ticket, ...]
    portfolio_sha256: str


def _triangle_edges(triangle: Triangle) -> tuple[tuple[int, int], ...]:
    return tuple(
        (min(triangle[first], triangle[second]), max(triangle[first], triangle[second]))
        for first, second in ((0, 1), (0, 2), (1, 2))
    )


_TRIANGLES: Final[tuple[Triangle, ...]] = tuple(
    triangle
    for triangle in combinations(CORE_SLOT_IDS, 3)
    if all(edge not in _FORBIDDEN_EDGE_SET for edge in _triangle_edges(triangle))
)
_TRIANGLE_IDS: Final[dict[Triangle, int]] = {
    triangle: index for index, triangle in enumerate(_TRIANGLES)
}
_TRIANGLE_EDGE_MASKS: Final = tuple(
    sum(1 << _EDGE_IDS[edge] for edge in _triangle_edges(triangle))
    for triangle in _TRIANGLES
)
_TRIANGLES_BY_EDGE: Final = tuple(
    tuple(
        triangle_id
        for triangle_id, triangle in enumerate(_TRIANGLES)
        if edge in _triangle_edges(triangle)
    )
    for edge in _ALL_CORE_PAIRS
)
INCUMBENT_DECOMPOSITION: Final[Decomposition] = tuple(
    sorted(
        _TRIANGLE_IDS[cast(Triangle, tuple(sorted(INCUMBENT_LABEL_TRIANGLES[label])))]
        for label in FREQUENCY_3_LABELS
    )
)


def _assert_frozen_contract() -> None:
    if tuple(sorted(INCUMBENT_LABEL_TRIANGLES)) != FREQUENCY_3_LABELS:
        raise AssertionError("frequency-three labels differ from the frozen label tuple")
    if set(CORE_SLOT_IDS) | set(PERIPHERY_SLOT_IDS) != set(ALL_SLOT_IDS):
        raise AssertionError("core and periphery slots do not partition K20 slots")
    if set(CORE_SLOT_IDS) & set(PERIPHERY_SLOT_IDS):
        raise AssertionError("core and periphery slots overlap")
    if len(INCUMBENT_LABEL_TRIANGLES) != 22 or len(FROZEN_F_PAIRS) != 6:
        raise AssertionError("frozen label or F-pair cardinality changed")
    if len(FIXED_LEAVE_EDGES) != 6:
        raise AssertionError("incumbent does not imply the six-edge fixed leave")
    if set(FROZEN_F_EDGES) & set(FIXED_LEAVE_EDGES):
        raise AssertionError("fixed F pairs overlap the fixed leave")
    if len(_INCUMBENT_TRIANGLE_EDGE_SET) != 66:
        raise AssertionError("incumbent triangles are not a linear edge packing")
    if _INCUMBENT_TRIANGLE_EDGE_SET & _FORBIDDEN_EDGE_SET:
        raise AssertionError("incumbent triangle edges overlap a frozen pair or leave edge")
    if len(INCUMBENT_DECOMPOSITION) != 22:
        raise AssertionError("incumbent does not contain 22 distinct triangles")


_assert_frozen_contract()


def enumerate_triangle_decompositions() -> tuple[Decomposition, ...]:
    """Enumerate all edge partitions of the fixed 66-edge core graph into triangles."""

    solutions: list[Decomposition] = []
    chosen: list[int] = []

    def visit(remaining: int) -> None:
        if remaining == 0:
            solutions.append(tuple(sorted(chosen)))
            return

        pending = remaining
        best_options: tuple[int, ...] | None = None
        while pending:
            edge_bit = pending & -pending
            edge_id = edge_bit.bit_length() - 1
            options = tuple(
                triangle_id
                for triangle_id in _TRIANGLES_BY_EDGE[edge_id]
                if _TRIANGLE_EDGE_MASKS[triangle_id] & remaining
                == _TRIANGLE_EDGE_MASKS[triangle_id]
            )
            if not options:
                return
            if best_options is None or len(options) < len(best_options):
                best_options = options
                if len(options) == 1:
                    break
            pending ^= edge_bit

        if best_options is None:
            raise AssertionError("nonempty edge remainder had no pivot")
        for triangle_id in best_options:
            chosen.append(triangle_id)
            visit(remaining ^ _TRIANGLE_EDGE_MASKS[triangle_id])
            chosen.pop()

    visit(_AVAILABLE_EDGE_MASK)
    return tuple(sorted(solutions))


def _edge_color_matrix() -> list[list[int]]:
    matrix = [[0] * len(CORE_SLOT_IDS) for _ in CORE_SLOT_IDS]
    for first, second in _ALL_CORE_PAIRS:
        edge = (first, second)
        color = 1 if edge in _FROZEN_EDGE_SET else 2 if edge in _LEAVE_EDGE_SET else 0
        a, b = _SLOT_INDEX[first], _SLOT_INDEX[second]
        matrix[a][b] = matrix[b][a] = color
    return matrix


def generate_symmetry_group() -> tuple[Permutation, ...]:
    """Return all permutations preserving frozen F edges and leave edges by color."""

    size = len(CORE_SLOT_IDS)
    edge_colors = _edge_color_matrix()
    initial_signatures = tuple(
        (
            sum(edge_colors[vertex][other] == 1 for other in range(size)),
            sum(edge_colors[vertex][other] == 2 for other in range(size)),
        )
        for vertex in range(size)
    )

    def color_ids(signatures: Sequence[tuple[int, ...]]) -> tuple[int, ...]:
        palette = {signature: index for index, signature in enumerate(sorted(set(signatures)))}
        return tuple(palette[signature] for signature in signatures)

    colors = color_ids(initial_signatures)
    while True:
        color_count = max(colors) + 1
        signatures = tuple(
            (
                colors[vertex],
                *(
                    sum(
                        edge_colors[vertex][other] == edge_color
                        and colors[other] == neighbor_color
                        for other in range(size)
                    )
                    for edge_color in range(3)
                    for neighbor_color in range(color_count)
                ),
            )
            for vertex in range(size)
        )
        refined = color_ids(signatures)
        if refined == colors:
            break
        colors = refined

    order = tuple(
        sorted(
            range(size),
            key=lambda vertex: (
                sum(color == colors[vertex] for color in colors),
                CORE_SLOT_IDS[vertex],
            ),
        )
    )
    mapping = [-1] * size
    used = [False] * size
    automorphisms: list[Permutation] = []

    def visit(position: int) -> None:
        if position == size:
            automorphisms.append(tuple(mapping))
            return
        source = order[position]
        for target in range(size):
            if used[target] or colors[source] != colors[target]:
                continue
            if any(
                edge_colors[source][order[prior]]
                != edge_colors[target][mapping[order[prior]]]
                for prior in range(position)
            ):
                continue
            mapping[source] = target
            used[target] = True
            visit(position + 1)
            used[target] = False
            mapping[source] = -1

    visit(0)
    return tuple(sorted(automorphisms))


def _triangle_action(permutation: Permutation) -> tuple[int, ...]:
    action: list[int] = []
    for triangle in _TRIANGLES:
        mapped = cast(
            Triangle,
            tuple(sorted(CORE_SLOT_IDS[permutation[_SLOT_INDEX[slot]]] for slot in triangle)),
        )
        action.append(_TRIANGLE_IDS[mapped])
    return tuple(action)


def _transform_decomposition(
    decomposition: Decomposition, triangle_action: Sequence[int]
) -> Decomposition:
    return tuple(sorted(triangle_action[triangle_id] for triangle_id in decomposition))


def _incumbent_orbit_representative(
    symmetry_group: Sequence[Permutation],
) -> Decomposition:
    orbit = {
        _transform_decomposition(INCUMBENT_DECOMPOSITION, _triangle_action(permutation))
        for permutation in symmetry_group
    }
    return min(orbit)


def _representative_sha256(decomposition: Decomposition) -> str:
    unlabeled = [list(_TRIANGLES[triangle_id]) for triangle_id in decomposition]
    raw = json.dumps(unlabeled, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def symmetry_class_representatives(
    decompositions: Sequence[Decomposition],
    symmetry_group: Sequence[Permutation],
) -> tuple[tuple[Decomposition, ...], tuple[tuple[int, int], ...]]:
    """Return lexicographic unlabeled orbit minima and the complete class histogram."""

    decomposition_set = set(decompositions)
    if len(decomposition_set) != len(decompositions):
        raise AssertionError("decomposition enumeration emitted duplicates")
    triangle_actions = tuple(_triangle_action(permutation) for permutation in symmetry_group)
    seen: set[Decomposition] = set()
    representatives: list[Decomposition] = []
    histogram: Counter[int] = Counter()

    for decomposition in decompositions:
        if decomposition in seen:
            continue
        representatives.append(decomposition)
        orbit = {
            _transform_decomposition(decomposition, action) for action in triangle_actions
        }
        if not orbit <= decomposition_set:
            raise AssertionError("symmetry action left the regenerated decomposition set")
        seen.update(orbit)
        histogram[len(orbit)] += 1

    if seen != decomposition_set:
        raise AssertionError("symmetry orbits do not cover every decomposition")
    if representatives != sorted(representatives):
        raise AssertionError("representatives are not in deterministic U(D) order")
    return tuple(representatives), tuple(sorted(histogram.items()))


def regenerate_combinatorics() -> CombinatorialResult:
    """Regenerate the frozen decomposition, symmetry, and class identities."""

    decompositions = enumerate_triangle_decompositions()
    if len(decompositions) != EXPECTED_DECOMPOSITIONS:
        raise RuntimeError(
            f"COMBINATORIAL_IDENTITY_MISMATCH: got {len(decompositions)} decompositions"
        )
    symmetry_group = generate_symmetry_group()
    if len(symmetry_group) != EXPECTED_SYMMETRY_ORDER:
        raise RuntimeError(
            f"COMBINATORIAL_IDENTITY_MISMATCH: got {len(symmetry_group)} symmetries"
        )
    representatives, histogram = symmetry_class_representatives(
        decompositions, symmetry_group
    )
    if len(representatives) != EXPECTED_CLASS_COUNT:
        raise RuntimeError(
            f"COMBINATORIAL_IDENTITY_MISMATCH: got {len(representatives)} classes"
        )
    if dict(histogram) != EXPECTED_CLASS_SIZE_HISTOGRAM:
        raise RuntimeError(
            "COMBINATORIAL_IDENTITY_MISMATCH: class-size histogram differs from frozen identity"
        )
    incumbent_representative = _incumbent_orbit_representative(symmetry_group)
    if incumbent_representative not in representatives:
        raise RuntimeError("incumbent symmetry class is absent from regenerated classes")
    if not any(decomposition == INCUMBENT_DECOMPOSITION for decomposition in decompositions):
        raise RuntimeError("incumbent is absent from the regenerated decomposition set")
    return CombinatorialResult(
        decompositions=decompositions,
        symmetry_group=symmetry_group,
        representatives=representatives,
        class_size_histogram=histogram,
        incumbent_representative=incumbent_representative,
    )


def map_labels(decomposition: Decomposition) -> dict[int, Triangle]:
    """Apply the frozen incumbent-preserving label mapping to one decomposition."""

    remaining = set(decomposition)
    mapping: dict[int, Triangle] = {}
    reserved_triangles: set[int] = set()
    for label in FREQUENCY_3_LABELS:
        incumbent_triangle = _TRIANGLE_IDS[INCUMBENT_LABEL_TRIANGLES[label]]
        if incumbent_triangle in remaining:
            mapping[label] = _TRIANGLES[incumbent_triangle]
            reserved_triangles.add(incumbent_triangle)
    remaining_labels = [label for label in FREQUENCY_3_LABELS if label not in mapping]
    remaining_triangles = sorted(remaining - reserved_triangles)
    if len(remaining_labels) != len(remaining_triangles):
        raise AssertionError("label and triangle cardinalities differ during deterministic mapping")
    mapping.update(
        (label, _TRIANGLES[triangle_id])
        for label, triangle_id in zip(remaining_labels, remaining_triangles, strict=True)
    )
    if tuple(sorted(mapping)) != FREQUENCY_3_LABELS:
        raise AssertionError("deterministic label mapping omitted or duplicated a label")
    return mapping


def reconstruct_portfolio(decomposition: Decomposition) -> tuple[Ticket, ...]:
    """Rebuild the 20 tickets from fixed periphery, mapped triangles, and F pairs."""

    mapping = map_labels(decomposition)
    core_tickets: list[Ticket] = []
    for slot in CORE_SLOT_IDS:
        values = [label for label, triangle in mapping.items() if slot in triangle]
        values.extend(number for number, pair in FROZEN_F_PAIRS.items() if slot in pair)
        if len(values) != 6 or len(set(values)) != 6:
            raise AssertionError(f"core slot {slot} does not produce six distinct labels")
        if any(type(number) is not int or not 1 <= number <= 49 for number in values):
            raise AssertionError(f"core slot {slot} contains an illegal lottery number")
        core_tickets.append(tuple(sorted(values)))

    portfolio = tuple(
        sorted([START_BY_SLOT[slot] for slot in PERIPHERY_SLOT_IDS] + core_tickets)
    )
    if len(portfolio) != 20 or len(set(portfolio)) != 20:
        raise AssertionError("reconstructed portfolio has invalid cardinality or duplicates")
    if any(
        len(ticket) != 6
        or tuple(sorted(set(ticket))) != ticket
        or any(type(number) is not int or not 1 <= number <= 49 for number in ticket)
        for ticket in portfolio
    ):
        raise AssertionError("reconstructed portfolio contains an illegal ticket")
    frequencies = Counter(number for ticket in portfolio for number in ticket)
    expected_frequencies = {
        number: 3 if number in FREQUENCY_3_LABELS else 2 for number in range(1, 50)
    }
    if frequencies != expected_frequencies:
        raise AssertionError("reconstructed portfolio changed frozen number frequencies")
    return portfolio


def generate_candidates(combinatorics: CombinatorialResult) -> tuple[Candidate, ...]:
    """Build all non-incumbent portfolios in the frozen unlabeled representative order."""

    candidates: list[Candidate] = []
    for representative in combinatorics.representatives:
        if representative == combinatorics.incumbent_representative:
            continue
        tickets = reconstruct_portfolio(representative)
        candidates.append(
            Candidate(
                representative=representative,
                representative_sha256=_representative_sha256(representative),
                tickets=tickets,
                portfolio_sha256=canonical_portfolio_sha256(tickets),
            )
        )
    if len(candidates) != EXPECTED_CANDIDATES:
        raise RuntimeError(
            f"REPRESENTATIVE_ACCOUNTING_MISMATCH: got {len(candidates)} non-incumbent classes"
        )
    if [candidate.representative for candidate in candidates] != sorted(
        candidate.representative for candidate in candidates
    ):
        raise AssertionError("candidate order differs from deterministic U(D) order")
    return tuple(candidates)


def _fresh_process_exact_recount(tickets: Sequence[Ticket], repo_root: Path) -> int:
    child = (
        "import json,sys; "
        "from lottolab.research.b649_official_any_prize_exact import evaluate_portfolio; "
        "p=json.loads(sys.argv[1]); "
        "print(evaluate_portfolio(p).official_any_prize_outcome_count)"
    )
    runtime_env = os.environ.copy()
    existing_pythonpath = runtime_env.get("PYTHONPATH")
    runtime_env["PYTHONPATH"] = os.pathsep.join(
        part for part in (str(repo_root / "src"), existing_pythonpath) if part
    )
    encoded_tickets = json.dumps([list(ticket) for ticket in tickets], separators=(",", ":"))
    completed = subprocess.run(
        [sys.executable, "-c", child, encoded_tickets],
        cwd=repo_root,
        env=runtime_env,
        capture_output=True,
        check=False,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "fresh-process canonical recount failed: "
            f"{completed.stderr.strip() or completed.stdout.strip()}"
        )
    try:
        return int(completed.stdout.strip())
    except ValueError as error:
        raise RuntimeError("fresh-process recount returned a non-integer result") from error


def run_pilot() -> dict[str, object]:
    """Run the single START recount and all 261 canonical candidate evaluations."""

    combinatorics = regenerate_combinatorics()
    candidates = generate_candidates(combinatorics)
    incumbent = reconstruct_portfolio(INCUMBENT_DECOMPOSITION)
    start_sha256 = canonical_portfolio_sha256(incumbent)
    if incumbent != START_TICKETS or start_sha256 != EXPECTED_START_SHA256:
        raise RuntimeError("INCUMBENT_BYTE_REPRODUCTION_FAILED")

    repo_root = Path(__file__).resolve().parents[3]
    draws = all_main_draw_masks(49, 6)
    start_count = evaluate_portfolio(incumbent, draws=draws).official_any_prize_outcome_count
    if start_count != EXPECTED_START_COUNT:
        raise RuntimeError(f"START_COUNT_MISMATCH: got {start_count}")

    score_rows: list[list[object]] = []
    candidate_counts: list[tuple[Candidate, int]] = []
    for candidate in candidates:
        count = evaluate_portfolio(candidate.tickets, draws=draws).official_any_prize_outcome_count
        candidate_counts.append((candidate, count))
        score_rows.append(
            [candidate.representative_sha256, candidate.portfolio_sha256, count]
        )

    highest_candidate_count = max(count for _, count in candidate_counts)
    improved = highest_candidate_count > EXPECTED_START_COUNT
    if improved:
        best_candidate, best_count = min(
            (
                (candidate, count)
                for candidate, count in candidate_counts
                if count == highest_candidate_count
            ),
            key=lambda row: row[0].portfolio_sha256,
        )
        best_tickets = best_candidate.tickets
        best_sha256 = best_candidate.portfolio_sha256
        fresh_count = _fresh_process_exact_recount(best_tickets, repo_root)
        if fresh_count != best_count:
            raise RuntimeError(
                f"FRESH_RECOUNT_MISMATCH: selected {best_count}, recounted {fresh_count}"
            )
        fresh_recount = "PASS"
        pilot_result = "IMPROVEMENT_FOUND"
        ready_for_next_expansion_review = "YES"
    else:
        best_count = EXPECTED_START_COUNT
        best_sha256 = EXPECTED_START_SHA256
        fresh_recount = "NOT_REQUIRED"
        pilot_result = "NO_IMPROVEMENT"
        ready_for_next_expansion_review = "NO"

    candidate_order_payload = [row[0] for row in score_rows]
    score_ledger_bytes = json.dumps(score_rows, separators=(",", ":")).encode("utf-8")
    representative_order_bytes = json.dumps(
        candidate_order_payload, separators=(",", ":")
    ).encode("utf-8")
    return {
        "TASK_ID": TASK_ID,
        "START_COUNT": start_count,
        "START_SHA256": start_sha256,
        "REGENERATED_TRIANGLE_DECOMPOSITIONS": len(combinatorics.decompositions),
        "SYMMETRY_GROUP_ORDER": len(combinatorics.symmetry_group),
        "REGENERATED_SYMMETRY_CLASSES": len(combinatorics.representatives),
        "CLASS_SIZE_HISTOGRAM": {
            str(size): count for size, count in combinatorics.class_size_histogram
        },
        "FIXED_F_PAIRS": [list(edge) for edge in FROZEN_F_EDGES],
        "FIXED_LEAVE_EDGES": [list(edge) for edge in FIXED_LEAVE_EDGES],
        "LABELED_NON_INCUMBENT_CLASSES": len(candidates),
        "CANONICAL_EVALUATOR": (
            "lottolab.research.b649_official_any_prize_exact.evaluate_portfolio"
        ),
        "CANONICAL_EXACT_EVALUATIONS": 1 + len(candidates) + int(improved),
        "INCUMBENT_BYTE_REPRODUCTION": "PASS",
        "STRUCTURAL_INVARIANTS": "PASS",
        "PILOT_RESULT": pilot_result,
        "BEST_COUNT": best_count,
        "BEST_DELTA": best_count - start_count,
        "BEST_PORTFOLIO_SHA256": best_sha256,
        "FRESH_RECOUNT": fresh_recount,
        "READY_FOR_NEXT_EXPANSION_REVIEW": ready_for_next_expansion_review,
        "CANDIDATE_ORDER_SHA256": hashlib.sha256(representative_order_bytes).hexdigest(),
        "CANDIDATE_SCORE_LEDGER_SHA256": hashlib.sha256(score_ledger_bytes).hexdigest(),
        "CANDIDATE_SCORES": score_rows,
        "GLOBAL_K20_OPTIMUM_STATUS": "UNKNOWN",
    }


def main() -> None:
    result = run_pilot()
    if RESULT_PATH.exists():
        raise FileExistsError(f"refusing to replace existing pilot result: {RESULT_PATH}")
    RESULT_PATH.write_text(json.dumps(result, separators=(",", ":")), encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key != "CANDIDATE_SCORES"}))


if __name__ == "__main__":
    main()


__all__ = [
    "CORE_SLOT_IDS",
    "EXPECTED_CANDIDATES",
    "EXPECTED_CLASS_COUNT",
    "EXPECTED_CLASS_SIZE_HISTOGRAM",
    "EXPECTED_DECOMPOSITIONS",
    "EXPECTED_START_COUNT",
    "EXPECTED_START_SHA256",
    "EXPECTED_SYMMETRY_ORDER",
    "FIXED_LEAVE_EDGES",
    "FREQUENCY_3_LABELS",
    "FROZEN_F_PAIRS",
    "INCUMBENT_DECOMPOSITION",
    "INCUMBENT_LABEL_TRIANGLES",
    "PERIPHERY_SLOT_IDS",
    "START_TICKETS",
    "Candidate",
    "CombinatorialResult",
    "_representative_sha256",
    "canonical_portfolio_sha256",
    "enumerate_triangle_decompositions",
    "generate_candidates",
    "generate_symmetry_group",
    "map_labels",
    "reconstruct_portfolio",
    "regenerate_combinatorics",
    "run_pilot",
    "symmetry_class_representatives",
]
