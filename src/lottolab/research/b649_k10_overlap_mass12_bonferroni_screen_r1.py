"""Checkpointable exact Bonferroni screening for K10 overlap mass 12."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import os
import subprocess
import tempfile
import time
from collections import Counter
from collections.abc import Iterable, Iterator, Sequence
from fractions import Fraction
from functools import cache
from math import comb
from pathlib import Path
from typing import Any, cast

from lottolab.research.b649_k10_min_overlap_exhaustive_r1 import (
    canonical_class_id,
    canonical_portfolio_sha256,
    graph_is_admissible,
    parse_multig_line,
    portfolio_from_edges,
)

TASK_ID = "B649_K10_OVERLAP_MASS12_BONFERRONI_SCREEN_R1"
BASE_HEAD = "1ad73707a1a2690cc5a17301f05fca1321cfbaf8"
BASE_TREE = "5c0f4ba856559665c8eb10160df6584ce0975f47"
MASS11_RECORD = "src/lottolab/research/b649_k10_min_overlap_exhaustive_r1.json"
MASS11_CLASSES = "src/lottolab/research/b649_k10_min_overlap_classes.txt"
TICKET_COUNT = 10
POOL_SIZE = 49
DRAW_SIZE = 6
OUTRIGHT_MATCHES = 3
MASS12 = 12
CHECKPOINT_SCHEMA = 1
CHECKPOINT_INTERVAL = 5_000
CHECKPOINT_SECONDS = 60.0
MAX_CANONICAL_STAGE_STATES = 750_000
MAX_RAW_EXTENSIONS_PER_FAMILY = 20_000_000
MAX_PROJECTED_FINAL_CLASSES = 2_000_000
MAX_SCREEN_CLASSES = 1_000_000
SHARD_COUNT = 2
SHARD_SPLIT_STAGE = 7
SHARDING_STRATEGY = "independent-canonical-prefix-parent-v1"

RepoState = tuple[int, tuple[int, ...], int]


class _Mass12ResourceLimit(RuntimeError):
    def __init__(self, projection: object) -> None:
        super().__init__("MASS12_REQUIRES_BRANCH_AND_BOUND")
        self.projection = projection


def _json_object(value: object, *, context: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise RuntimeError(f"invalid JSON object for {context}")
    result: dict[str, object] = {}
    raw = cast(dict[object, object], value)
    for key, item in raw.items():
        if not isinstance(key, str):
            raise RuntimeError(f"invalid JSON key for {context}")
        result[key] = item
    return result


def _integer(value: object, *, context: str) -> int:
    if type(value) is not int:
        raise RuntimeError(f"invalid integer field for {context}")
    return value


def _floating(value: object, *, context: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise RuntimeError(f"invalid numeric field for {context}")
    return float(value)


def _summary_map(value: object, *, context: str) -> dict[str, dict[str, object]]:
    raw = _json_object(value, context=context)
    return {
        key: _json_object(summary, context=f"{context}.{key}")
        for key, summary in raw.items()
    }


def _portfolio_value(value: object, *, context: str) -> tuple[tuple[int, ...], ...]:
    if not isinstance(value, list):
        raise RuntimeError(f"invalid portfolio field for {context}")
    raw_tickets = cast(list[object], value)
    tickets: list[tuple[int, ...]] = []
    for ticket in raw_tickets:
        if not isinstance(ticket, list):
            raise RuntimeError(f"invalid ticket in {context}")
        raw_numbers = cast(list[object], ticket)
        tickets.append(tuple(_integer(number, context=context) for number in raw_numbers))
    return tuple(tickets)


def _survivor_list(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        raise RuntimeError("invalid survivor list in checkpoint")
    raw_survivors = cast(list[object], value)
    return [_json_object(survivor, context="survivor") for survivor in raw_survivors]


def total_official_outcomes(pool_size: int = POOL_SIZE, draw_size: int = DRAW_SIZE) -> int:
    if not 0 <= draw_size <= pool_size:
        raise ValueError("draw size must be within the pool")
    return comb(pool_size, draw_size) * (pool_size - draw_size)


def incumbent_outcome_count(numerator: int, denominator: int) -> int:
    if numerator <= 0 or denominator <= 0:
        raise ValueError("incumbent fraction must be positive")
    outcomes = total_official_outcomes()
    count, remainder = divmod(numerator * outcomes, denominator)
    if remainder:
        raise ValueError("incumbent fraction is not integral over the official outcome space")
    return count


def prove_mass12_profiles() -> dict[str, object]:
    """Prove the only profiles using incidence excess and overlap mass."""

    incidences = TICKET_COUNT * DRAW_SIZE
    mass = MASS12
    labels = POOL_SIZE
    # U is the number of used labels.  E = incidences - U is at least 11.
    # For every r >= 2, r-1 <= C(r,2), so E <= mass = 12.
    # The deficit is sum_{r>=3} C(r-1,2) m_r = mass-E, hence is 0 or 1.
    profiles: list[dict[str, int]] = []
    for deficit in (0, 1):
        triple_count = deficit
        pair_count = mass - 3 * triple_count
        singleton_count = incidences - 2 * pair_count - 3 * triple_count
        used = singleton_count + pair_count + triple_count
        if pair_count < 0 or singleton_count < 0 or used > labels:
            raise AssertionError("derived mass-12 profile is infeasible")
        profile = {"1": singleton_count, "2": pair_count}
        if triple_count:
            profile["3"] = triple_count
        profiles.append(profile)
    expected = [
        {"1": 36, "2": 12},
        {"1": 39, "2": 9, "3": 1},
    ]
    if profiles != expected:
        raise AssertionError(f"mass-12 multiplicity model changed: {profiles}")
    return {
        "incidences": incidences,
        "overlap_mass": mass,
        "label_cap": labels,
        "used_label_range": [48, 49],
        "profiles": {"A": profiles[0], "B": profiles[1]},
        "proof": (
            "11 <= E=60-U <= 12; mass-E is the sum of C(r-1,2) over r>=3, "
            "so it is 0 or 1. Thus there are either twelve doubles, or nine "
            "doubles and one triple. The incidence equation fixes the singles."
        ),
    }


def _region_sizes_for_tickets(ticket_masks: Sequence[int]) -> tuple[int, ...]:
    count = len(ticket_masks)
    if not 1 <= count <= 3:
        raise ValueError("joint event counts support one to three tickets")
    union_mask = 0
    for mask in ticket_masks:
        union_mask |= mask
    regions = [0] * (1 << count)
    remaining = union_mask
    while remaining:
        bit = remaining & -remaining
        signature = 0
        for index, mask in enumerate(ticket_masks):
            if mask & bit:
                signature |= 1 << index
        regions[signature] += 1
        remaining ^= bit
    return tuple(regions[1:])


@cache
def _joint_count_from_regions(
    region_sizes: tuple[int, ...],
    ticket_count: int,
    pool_size: int,
    draw_size: int,
    outright_matches: int,
) -> int:
    """Count exact outcomes shared by all ticket events from Venn regions."""

    expected_regions = (1 << ticket_count) - 1
    if len(region_sizes) != expected_regions:
        raise ValueError("wrong Venn-region count")
    if any(size < 0 for size in region_sizes):
        raise ValueError("Venn regions cannot be negative")
    if not 1 <= outright_matches <= draw_size <= pool_size:
        raise ValueError("invalid lottery parameters")
    union_size = sum(region_sizes)
    if union_size > pool_size:
        raise ValueError("ticket union exceeds the lottery pool")
    rescue_hits = outright_matches - 1
    selected = [0] * expected_regions
    total = 0

    def count_regions(region: int, remaining: int, ways: int) -> None:
        nonlocal total
        if region == expected_regions:
            hits = [0] * ticket_count
            for region_index, selected_count in enumerate(selected, start=1):
                for ticket_index in range(ticket_count):
                    if region_index & (1 << ticket_index):
                        hits[ticket_index] += selected_count
            rescue_mask = 0
            for ticket_index, hit_count in enumerate(hits):
                if hit_count >= outright_matches:
                    continue
                if hit_count == rescue_hits:
                    rescue_mask |= 1 << ticket_index
                else:
                    return
            if rescue_mask == 0:
                special_ways = pool_size - draw_size
            else:
                special_ways = 0
                for region_index, region_size in enumerate(region_sizes, start=1):
                    if region_index & rescue_mask == rescue_mask:
                        special_ways += region_size - selected[region_index - 1]
            outside_count = pool_size - union_size
            if remaining > outside_count:
                return
            outside_ways = comb(outside_count, remaining)
            total += ways * outside_ways * special_ways
            return

        maximum = min(region_sizes[region], remaining)
        for selected_count in range(maximum + 1):
            selected[region] = selected_count
            count_regions(
                region + 1,
                remaining - selected_count,
                ways * comb(region_sizes[region], selected_count),
            )
        selected[region] = 0

    count_regions(0, draw_size, 1)
    return total


def _joint_event_count(
    ticket_masks: Sequence[int],
    *,
    pool_size: int = POOL_SIZE,
    draw_size: int = DRAW_SIZE,
    outright_matches: int = OUTRIGHT_MATCHES,
) -> int:
    if not ticket_masks:
        raise ValueError("at least one ticket is required")
    regions = _region_sizes_for_tickets(ticket_masks)
    return _joint_count_from_regions(
        regions,
        len(ticket_masks),
        pool_size,
        draw_size,
        outright_matches,
    )


def u3_outcome_count(
    portfolio: Sequence[Sequence[int]],
    *,
    pool_size: int = POOL_SIZE,
    draw_size: int = DRAW_SIZE,
    outright_matches: int = OUTRIGHT_MATCHES,
) -> int:
    """Third-order Bonferroni upper bound for OFFICIAL_ANY_PRIZE outcomes."""

    if not portfolio:
        raise ValueError("portfolio must contain at least one ticket")
    masks: list[int] = []
    for ticket in portfolio:
        if (
            len(ticket) != draw_size
            or len(set(ticket)) != draw_size
            or any(type(number) is not int or not 1 <= number <= pool_size for number in ticket)
        ):
            raise ValueError(f"illegal ticket: {tuple(ticket)}")
        mask = 0
        for number in ticket:
            mask |= 1 << (number - 1)
        masks.append(mask)
    singles = sum(
        _joint_event_count(
            (mask,),
            pool_size=pool_size,
            draw_size=draw_size,
            outright_matches=outright_matches,
        )
        for mask in masks
    )
    pairs = sum(
        _joint_event_count(
            pair,
            pool_size=pool_size,
            draw_size=draw_size,
            outright_matches=outright_matches,
        )
        for pair in itertools.combinations(masks, 2)
    )
    triples = sum(
        _joint_event_count(
            triple,
            pool_size=pool_size,
            draw_size=draw_size,
            outright_matches=outright_matches,
        )
        for triple in itertools.combinations(masks, 3)
    )
    return singles - pairs + triples


def exact_union_outcome_count(
    portfolio: Sequence[Sequence[int]],
    *,
    pool_size: int = POOL_SIZE,
    draw_size: int = DRAW_SIZE,
    outright_matches: int = OUTRIGHT_MATCHES,
) -> int:
    """Small-oracle-capable exact union count over main draws and specials."""

    if not portfolio:
        raise ValueError("portfolio must contain at least one ticket")
    if not 1 <= outright_matches <= draw_size <= pool_size:
        raise ValueError("invalid lottery parameters")
    total = 0
    all_numbers = tuple(range(1, pool_size + 1))
    for main_draw in itertools.combinations(all_numbers, draw_size):
        draw = set(main_draw)
        special_pool = set(all_numbers).difference(draw)
        winning_specials: set[int] = set()
        for ticket in portfolio:
            hits = len(set(ticket).intersection(draw))
            if hits >= outright_matches:
                winning_specials.update(special_pool)
            elif hits == outright_matches - 1:
                winning_specials.update(set(ticket).difference(draw))
        total += len(winning_specials)
    return total


def _state_key(state: RepoState) -> str:
    vertex_count, weights, triple_mask = state
    return f"{vertex_count}:{triple_mask:x}:{''.join(str(value) for value in weights)}"


def _state_from_key(key: str) -> RepoState:
    parts = key.split(":", 2)
    if len(parts) != 3:
        raise ValueError(f"invalid canonical state id: {key!r}")
    vertex_count = int(parts[0])
    triple_mask = int(parts[1], 16)
    weights = tuple(int(value) for value in parts[2])
    if len(weights) != vertex_count * (vertex_count - 1) // 2 or any(
        value < 0 or value > DRAW_SIZE for value in weights
    ):
        raise ValueError(f"invalid canonical state body: {key!r}")
    if triple_mask >= 1 << vertex_count:
        raise ValueError(f"invalid triple mask: {key!r}")
    return vertex_count, weights, triple_mask


def _adjacency(vertex_count: int, weights: Sequence[int]) -> list[list[int]]:
    matrix = [[0] * vertex_count for _ in range(vertex_count)]
    cursor = 0
    for left in range(vertex_count):
        for right in range(left + 1, vertex_count):
            weight = weights[cursor]
            matrix[left][right] = weight
            matrix[right][left] = weight
            cursor += 1
    if cursor != len(weights):
        raise ValueError("adjacency weight count does not match vertex count")
    return matrix


def _canonicalize_state(state: RepoState) -> RepoState:
    """Exact color-preserving canonical labeling by refinement and branching."""

    vertex_count, weights, triple_mask = state
    if vertex_count == 0:
        return state
    matrix = _adjacency(vertex_count, weights)

    def refine(colors: tuple[int, ...]) -> tuple[int, ...]:
        while True:
            color_values = sorted(set(colors))
            signatures: list[tuple[int, tuple[int, ...]]] = []
            for vertex in range(vertex_count):
                profile: list[int] = []
                for color in color_values:
                    counts = [0] * (DRAW_SIZE + 1)
                    for neighbor in range(vertex_count):
                        if colors[neighbor] == color:
                            counts[matrix[vertex][neighbor]] += 1
                    profile.extend(counts)
                signatures.append((colors[vertex], tuple(profile)))
            ordered = sorted(set(signatures))
            ids = {signature: index for index, signature in enumerate(ordered)}
            updated = tuple(ids[signature] for signature in signatures)
            if len(set(updated)) == len(set(colors)):
                return updated
            colors = updated

    def encode_leaf(colors: tuple[int, ...]) -> bytes:
        order = sorted(range(vertex_count), key=colors.__getitem__)
        marks = 0
        for new_index, old_index in enumerate(order):
            if triple_mask & (1 << old_index):
                marks |= 1 << new_index
        canonical_weights = bytes(
            matrix[order[left]][order[right]]
            for left in range(vertex_count)
            for right in range(left + 1, vertex_count)
        )
        return bytes((vertex_count,)) + marks.to_bytes(2, "big") + canonical_weights

    def visit(seed: tuple[int, ...]) -> bytes:
        colors = refine(seed)
        groups: dict[int, list[int]] = {}
        for vertex, color in enumerate(colors):
            groups.setdefault(color, []).append(vertex)
        cell = next((group for _, group in sorted(groups.items()) if len(group) > 1), None)
        if cell is None:
            return encode_leaf(colors)

        representatives: list[int] = []
        for candidate in cell:
            if any(
                all(
                    matrix[candidate][other] == matrix[representative][other]
                    for other in range(vertex_count)
                    if other not in {candidate, representative}
                )
                for representative in representatives
            ):
                continue
            representatives.append(candidate)

        best: bytes | None = None
        unique_color = max(colors) + 1
        for candidate in representatives:
            individualized = list(colors)
            individualized[candidate] = unique_color
            label = visit(tuple(individualized))
            if best is None or label < best:
                best = label
        if best is None:
            raise AssertionError("canonical labeling produced no branch")
        return best

    initial_colors = tuple(
        1 if triple_mask & (1 << vertex) else 0 for vertex in range(vertex_count)
    )
    canonical = visit(initial_colors)
    canonical_count = canonical[0]
    canonical_mask = int.from_bytes(canonical[1:3], "big")
    canonical_weights = tuple(canonical[3:])
    return canonical_count, canonical_weights, canonical_mask


def _degrees(state: RepoState) -> tuple[int, ...]:
    vertex_count, weights, triple_mask = state
    result = [1 if triple_mask & (1 << vertex) else 0 for vertex in range(vertex_count)]
    cursor = 0
    for left in range(vertex_count):
        for right in range(left + 1, vertex_count):
            weight = weights[cursor]
            result[left] += weight
            result[right] += weight
            cursor += 1
    return tuple(result)


def _portfolio_from_state(state: RepoState, family: str) -> tuple[tuple[int, ...], ...]:
    vertex_count, weights, triple_mask = state
    if vertex_count != TICKET_COUNT:
        raise ValueError("a legal B649 portfolio requires ten ticket vertices")
    if family not in {"A", "B"}:
        raise ValueError(f"unknown multiplicity family: {family}")
    if family == "A" and triple_mask:
        raise ValueError("Family A cannot contain a degree-three label")
    if family == "B" and triple_mask.bit_count() != 3:
        raise ValueError("Family B requires exactly one degree-three label")
    if any(degree > DRAW_SIZE for degree in _degrees(state)):
        raise ValueError("repeated-number degree exceeds ticket size")

    tickets: list[list[int]] = [[] for _ in range(vertex_count)]
    number = 1
    cursor = 0
    for left in range(vertex_count):
        for right in range(left + 1, vertex_count):
            multiplicity = weights[cursor]
            for _ in range(multiplicity):
                tickets[left].append(number)
                tickets[right].append(number)
                number += 1
            cursor += 1
    if triple_mask:
        for vertex in range(vertex_count):
            if triple_mask & (1 << vertex):
                tickets[vertex].append(number)
        number += 1
    for vertex, ticket in enumerate(tickets):
        for _ in range(DRAW_SIZE - len(ticket)):
            tickets[vertex].append(number)
            number += 1

    portfolio = tuple(tuple(sorted(ticket)) for ticket in tickets)
    if any(len(ticket) != DRAW_SIZE or len(set(ticket)) != DRAW_SIZE for ticket in portfolio):
        raise ValueError("reconstruction produced an invalid ticket")
    if any(number < 1 or number > POOL_SIZE for ticket in portfolio for number in ticket):
        raise ValueError("reconstruction produced a number outside 1..49")
    if len(set(portfolio)) != vertex_count:
        raise ValueError("reconstruction produced duplicate tickets")

    frequencies = Counter(number for ticket in portfolio for number in ticket)
    histogram = Counter(frequencies.values())
    unused_count = POOL_SIZE - len(frequencies)
    if unused_count:
        histogram[0] = unused_count
    expected = {"A": {1: 36, 2: 12, 0: 1}, "B": {1: 39, 2: 9, 3: 1}}[family]
    if dict(histogram) != expected:
        raise ValueError(f"wrong multiplicity histogram for Family {family}: {dict(histogram)}")
    overlap_mass = sum(comb(frequency, 2) for frequency in frequencies.values())
    if overlap_mass != MASS12:
        raise ValueError(f"wrong pairwise overlap mass: {overlap_mass}")
    pair_mass = sum(weights)
    if family == "A" and pair_mass != 12:
        raise ValueError("Family A requires twelve pair labels")
    if family == "B" and pair_mass != 9:
        raise ValueError("Family B requires nine pair labels")
    return portfolio


def _json_atomic(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as stream:
        temporary = Path(stream.name)
        json.dump(value, stream, sort_keys=True, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    try:
        descriptor = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    except OSError:
        pass


def _checkpoint_root(raw_path: str) -> Path:
    root = Path(raw_path)
    if not root.is_absolute():
        root = _repo_root() / root
    return root.resolve()


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _live_base_identity() -> tuple[str, str]:
    root = _repo_root()
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    tree = subprocess.check_output(["git", "rev-parse", "HEAD^{tree}"], cwd=root, text=True).strip()
    return head, tree


def _require_base_identity() -> None:
    head, tree = _live_base_identity()
    base_tree = subprocess.check_output(
        ["git", "rev-parse", f"{BASE_HEAD}^{{tree}}"], cwd=_repo_root(), text=True
    ).strip()
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", BASE_HEAD, "HEAD"],
        cwd=_repo_root(),
        check=False,
        capture_output=True,
        text=True,
    )
    if base_tree != BASE_TREE or ancestor.returncode != 0:
        raise RuntimeError(
            "WORKTREE_IDENTITY_MISMATCH: pinned authority commit/tree must be an ancestor; "
            f"expected {BASE_HEAD}/{BASE_TREE}, got HEAD {head}/{tree} and base tree {base_tree}"
        )


def _sha256_lines(values: Iterable[str]) -> str:
    payload = "\n".join(sorted(values)).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _mass11_class_inputs(
    authority_commit: str, classes_file: str
) -> tuple[bytes, dict[str, object]]:
    if authority_commit != BASE_HEAD:
        raise RuntimeError("mass-11 authority commit does not match the authorized pin")
    root = _repo_root()
    path = Path(classes_file)
    if not path.is_absolute():
        path = root / path
    path = path.resolve()
    relative = path.relative_to(root).as_posix()
    if relative != MASS11_CLASSES:
        raise RuntimeError(f"unexpected mass-11 classes path: {relative}")
    committed_classes = subprocess.check_output(
        ["git", "show", f"{authority_commit}:{relative}"], cwd=root
    )
    if path.read_bytes() != committed_classes:
        raise RuntimeError("working class file does not match the pinned committed artifact")
    record_bytes = subprocess.check_output(
        ["git", "show", f"{authority_commit}:{MASS11_RECORD}"], cwd=root
    )
    return committed_classes, _json_object(
        json.loads(record_bytes), context="mass-11 authority record"
    )


def _validate_checkpoint_identity(
    checkpoint: dict[str, object], *, phase: str, numerator: int, denominator: int
) -> None:
    expected = {
        "schema_version": CHECKPOINT_SCHEMA,
        "task_id": TASK_ID,
        "phase": phase,
        "base_head": BASE_HEAD,
        "base_tree": BASE_TREE,
        "incumbent_numerator": numerator,
        "incumbent_denominator": denominator,
        "incumbent_outcome_count": incumbent_outcome_count(numerator, denominator),
    }
    for key, value in expected.items():
        if checkpoint.get(key) != value:
            raise RuntimeError(f"checkpoint identity mismatch for {key}")


def _base_checkpoint(
    phase: str, numerator: int, denominator: int, *, family: str | None = None
) -> dict[str, object]:
    value: dict[str, object] = {
        "schema_version": CHECKPOINT_SCHEMA,
        "task_id": TASK_ID,
        "phase": phase,
        "base_head": BASE_HEAD,
        "base_tree": BASE_TREE,
        "incumbent_numerator": numerator,
        "incumbent_denominator": denominator,
        "incumbent_outcome_count": incumbent_outcome_count(numerator, denominator),
        "family": family,
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    return value


def _read_checkpoint(path: Path) -> dict[str, object] | None:
    if not path.exists():
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    return _json_object(value, context=f"checkpoint {path}")


def _mass11_certificate(
    *,
    authority_commit: str,
    classes_file: str,
    numerator: int,
    denominator: int,
    checkpoint_root: Path,
    resume: bool,
) -> dict[str, object]:
    _require_base_identity()
    classes_bytes, authority_record = _mass11_class_inputs(authority_commit, classes_file)
    classes_sha = hashlib.sha256(classes_bytes).hexdigest()
    lines = classes_bytes.decode("ascii").splitlines()
    expected_count = _integer(
        authority_record["canonical_unique_count"], context="canonical_unique_count"
    )
    expected_digest = str(authority_record["class_set_sha256_run_1"])
    expected_outcome_count = incumbent_outcome_count(numerator, denominator)
    if authority_record.get("hard_div_exact") != f"{numerator}/{denominator}":
        raise RuntimeError("incumbent fraction disagrees with committed mass-11 authority")
    if _integer(
        authority_record["enumerator_raw_count"], context="enumerator_raw_count"
    ) != len(lines):
        raise RuntimeError("committed raw class count does not match the classes artifact")

    checkpoint_path = checkpoint_root / "mass11_certificate_checkpoint.json"
    result_path = checkpoint_root / "mass11_certificate_result.json"
    checkpoint = _read_checkpoint(checkpoint_path) if resume else None
    if checkpoint is not None:
        _validate_checkpoint_identity(
            checkpoint, phase="mass11_certificate", numerator=numerator, denominator=denominator
        )
        if checkpoint.get("authority_commit") != authority_commit:
            raise RuntimeError("mass-11 checkpoint authority mismatch")
        if checkpoint.get("classes_sha256") != classes_sha:
            raise RuntimeError("mass-11 checkpoint class artifact mismatch")
        if checkpoint.get("status") == "COMPLETE":
            if not result_path.exists():
                raise RuntimeError("completed mass-11 checkpoint has no result")
            return _json_object(
                json.loads(result_path.read_text(encoding="utf-8")),
                context="mass-11 result",
            )
        start_index = _integer(
            checkpoint.get("processed_raw_count", 0), context="processed_raw_count"
        )
        safe_pruned = _integer(checkpoint.get("safe_pruned", 0), context="safe_pruned")
        survivors = _survivor_list(checkpoint.get("survivors", []))
        invalid_count = _integer(checkpoint.get("invalid_count", 0), context="invalid_count")
        raw_ids: set[str] = set()
        legal_ids: set[str] = set()
        legacy_to_authority_id: dict[str, str] = {}
        for line in lines[:start_index]:
            group_size, edges = parse_multig_line(line)
            class_id = canonical_class_id(TICKET_COUNT, edges, group_size)
            raw_ids.add(class_id)
            legacy_to_authority_id[canonical_class_id(TICKET_COUNT, edges, None)] = class_id
            if not graph_is_admissible(edges, edge_count=11, max_degree=DRAW_SIZE):
                invalid_count += 0
                continue
            try:
                portfolio = portfolio_from_edges(edges)
            except ValueError:
                continue
            if len(set(portfolio)) == TICKET_COUNT:
                legal_ids.add(class_id)
        if len(legal_ids) != _integer(
            checkpoint.get("legal_count", 0), context="legal_count"
        ):
            raise RuntimeError("mass-11 checkpoint prefix does not reproduce its legal count")
        if len(raw_ids) != start_index:
            raise RuntimeError("mass-11 checkpoint prefix contains duplicate raw class identities")
        last_id = checkpoint.get("last_completed_class_id")
        if start_index:
            last_group, last_edges = parse_multig_line(lines[start_index - 1])
            authority_last_id = canonical_class_id(TICKET_COUNT, last_edges, last_group)
            legacy_last_id = canonical_class_id(TICKET_COUNT, last_edges, None)
            if last_id not in {authority_last_id, legacy_last_id}:
                raise RuntimeError("mass-11 checkpoint last class does not match source prefix")
            checkpoint["last_completed_class_id"] = authority_last_id
        for survivor in survivors:
            old_id = str(survivor.get("class_id", ""))
            if old_id in legacy_to_authority_id:
                survivor["class_id"] = legacy_to_authority_id[old_id]
    else:
        if checkpoint_path.exists():
            raise RuntimeError("mass-11 checkpoint exists; pass --resume to continue it")
        start_index = 0
        safe_pruned = 0
        survivors: list[dict[str, object]] = []
        invalid_count = 0
        raw_ids = set()
        legal_ids = set()
        checkpoint = _base_checkpoint("mass11_certificate", numerator, denominator)
        checkpoint.update(
            {
                "authority_commit": authority_commit,
                "classes_sha256": classes_sha,
                "raw_generated_count": 0,
                "legal_count": 0,
                "canonical_count": 0,
                "processed_raw_count": 0,
                "last_completed_class_id": None,
                "safe_pruned": 0,
                "survivor_count": 0,
                "survivors": [],
                "invalid_count": 0,
                "status": "RUNNING",
            }
        )
        _json_atomic(checkpoint_path, checkpoint)

    accepted = len(legal_ids)
    current_u3 = (
        _integer(
            checkpoint.get("last_u3_outcome_count", 0), context="last_u3_outcome_count"
        )
        if start_index
        else 0
    )
    last_save_time = time.monotonic()
    last_saved_accepted = accepted - (accepted % CHECKPOINT_INTERVAL)

    for raw_index in range(start_index, len(lines)):
        line = lines[raw_index]
        group_size, edges = parse_multig_line(line)
        class_id = canonical_class_id(TICKET_COUNT, edges, group_size)
        if class_id in raw_ids:
            raise RuntimeError(f"duplicate pinned raw class identity: {class_id}")
        raw_ids.add(class_id)
        legal = graph_is_admissible(edges, edge_count=11, max_degree=DRAW_SIZE)
        portfolio: tuple[tuple[int, ...], ...] | None = None
        if legal:
            try:
                portfolio = portfolio_from_edges(edges)
            except ValueError:
                legal = False
        if legal and portfolio is not None:
            if class_id in legal_ids:
                raise RuntimeError(f"duplicate committed canonical class identity: {class_id}")
            legal_ids.add(class_id)
            accepted += 1
            bound = u3_outcome_count(portfolio)
            current_u3 = bound
            if bound <= expected_outcome_count:
                safe_pruned += 1
            else:
                survivors.append(
                    {
                        "class_id": class_id,
                        "portfolio": [list(ticket) for ticket in portfolio],
                        "u3_outcome_count": bound,
                    }
                )
        else:
            invalid_count += 1

        processed = raw_index + 1
        now = time.monotonic()
        must_save = (
            accepted - last_saved_accepted >= CHECKPOINT_INTERVAL
            or now - last_save_time >= CHECKPOINT_SECONDS
        )
        if must_save or processed == len(lines):
            checkpoint = _base_checkpoint("mass11_certificate", numerator, denominator)
            checkpoint.update(
                {
                    "authority_commit": authority_commit,
                    "classes_sha256": classes_sha,
                    "raw_generated_count": processed,
                    "legal_count": accepted,
                    "canonical_count": accepted,
                    "processed_raw_count": processed,
                    "last_completed_class_id": class_id,
                    "last_u3_outcome_count": current_u3,
                    "safe_pruned": safe_pruned,
                    "survivor_count": len(survivors),
                    "survivors": survivors,
                    "invalid_count": invalid_count,
                    "status": "RUNNING",
                }
            )
            _json_atomic(checkpoint_path, checkpoint)
            last_save_time = now
            last_saved_accepted = accepted
            print(
                json.dumps(
                    {"phase": "mass11_certificate", "processed_raw": processed, "legal": accepted},
                    sort_keys=True,
                ),
                flush=True,
            )

    raw_class_digest = _sha256_lines(raw_ids)
    legal_class_digest = _sha256_lines(legal_ids)
    if len(lines) != _integer(
        authority_record["enumerator_raw_count"], context="enumerator_raw_count"
    ):
        raise RuntimeError("mass-11 raw class count mismatch")
    if (
        len(raw_ids) != len(lines)
        or accepted != expected_count
        or raw_class_digest != expected_digest
    ):
        raise RuntimeError(
            "mass-11 class evidence mismatch: "
            f"raw={len(raw_ids)}/{len(lines)} raw_digest={raw_class_digest} legal={accepted}"
        )
    if safe_pruned != 89_197 or len(survivors) != 1:
        raise RuntimeError(
            f"BONFERRONI_CERTIFICATE_REGRESSION: pruned={safe_pruned}, survivors={len(survivors)}"
        )

    exact_module: Any = __import__(
        "lottolab.research.b649_official_any_prize_exact", fromlist=["evaluate_portfolio"]
    )
    survivor = survivors[0]
    survivor_portfolio = _portfolio_value(survivor["portfolio"], context="mass-11 survivor")
    exact = exact_module.evaluate_portfolio(survivor_portfolio).official_any_prize
    expected_fraction = Fraction(numerator, denominator)
    if exact != expected_fraction:
        raise RuntimeError(f"BONFERRONI_CERTIFICATE_REGRESSION: survivor exact={exact}")
    result: dict[str, object] = {
        "schema_version": CHECKPOINT_SCHEMA,
        "task_id": TASK_ID,
        "authority_commit": authority_commit,
        "base_head": BASE_HEAD,
        "base_tree": BASE_TREE,
        "raw_classes": len(lines),
        "raw_class_set_sha256": raw_class_digest,
        "legal_classes": accepted,
        "legal_class_set_sha256": legal_class_digest,
        "safe_pruned": safe_pruned,
        "survivors": len(survivors),
        "survivor_class_id": survivor["class_id"],
        "survivor_u3_outcome_count": survivor["u3_outcome_count"],
        "survivor_exact": str(exact),
        "survivor_exact_outcome_count": exact.numerator
        * (total_official_outcomes() // exact.denominator),
        "incumbent_outcome_count": expected_outcome_count,
        "pruning_oracle": "fresh U3 computation; committed scores JSONL not read",
        "status": "PASS",
    }
    _json_atomic(result_path, result)
    checkpoint = _base_checkpoint("mass11_certificate", numerator, denominator)
    checkpoint.update(
        {
            "authority_commit": authority_commit,
            "classes_sha256": classes_sha,
            "raw_generated_count": len(lines),
            "legal_count": accepted,
            "canonical_count": accepted,
            "processed_raw_count": len(lines),
            "last_completed_class_id": canonical_class_id(
                TICKET_COUNT,
                parse_multig_line(lines[-1])[1],
                parse_multig_line(lines[-1])[0],
            ),
            "safe_pruned": safe_pruned,
            "survivor_count": len(survivors),
            "survivors": survivors,
            "invalid_count": invalid_count,
            "status": "COMPLETE",
        }
    )
    _json_atomic(checkpoint_path, checkpoint)
    print(json.dumps(result, sort_keys=True), flush=True)
    return result


def _atomic_lines(path: Path, values: Iterable[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as stream:
        temporary = Path(stream.name)
        for value in values:
            stream.write(value)
            stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def _read_lines(path: Path, *, limit: int | None = None) -> list[str]:
    if not path.exists():
        return []
    values: list[str] = []
    with path.open("rb") as stream:
        remaining = limit
        while remaining is None or remaining > 0:
            line = stream.readline()
            if not line:
                break
            if remaining is not None:
                remaining = max(0, remaining - len(line))
            values.append(line.rstrip(b"\r\n").decode("utf-8"))
    return values


def _append_json_line(stream: Any, value: dict[str, object]) -> int:
    line = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"
    stream.write(line)
    return stream.tell()


def _can_complete(
    state: RepoState, *, target_pair_mass: int, target_triples: int
) -> bool:
    vertex_count, weights, triple_mask = state
    pair_mass = sum(weights)
    triple_count = triple_mask.bit_count()
    if pair_mass > target_pair_mass or triple_count > target_triples:
        return False
    future_vertices = TICKET_COUNT - vertex_count
    missing_triples = target_triples - triple_count
    if missing_triples > future_vertices:
        return False
    if future_vertices == 0:
        return pair_mass == target_pair_mass and missing_triples == 0
    needed_pair_mass = target_pair_mass - pair_mass
    existing_capacity = sum(DRAW_SIZE - degree for degree in _degrees(state))
    future_capacity = DRAW_SIZE * future_vertices - missing_triples
    available_pairs = comb(TICKET_COUNT, 2) - comb(vertex_count, 2)
    max_pair_mass = min((existing_capacity + future_capacity) // 2, DRAW_SIZE * available_pairs)
    return needed_pair_mass <= max_pair_mass


def _iter_extensions(
    state: RepoState, *, target_pair_mass: int, target_triples: int
) -> Iterator[RepoState]:
    vertex_count, weights, triple_mask = state
    current_mass = sum(weights)
    current_triples = triple_mask.bit_count()
    remaining_mass = target_pair_mass - current_mass
    if remaining_mass < 0:
        return
    degrees = _degrees(state)
    capacities = tuple(DRAW_SIZE - degree for degree in degrees)
    mark_options = (0, 1) if current_triples < target_triples else (0,)

    for new_mark in mark_options:
        if new_mark and current_triples >= target_triples:
            continue
        new_vertex_capacity = DRAW_SIZE - new_mark
        chosen: list[int] = []

        def walk(
            index: int,
            mass_left: int,
            incidence_left: int,
            mark: int = new_mark,
            choices: list[int] = chosen,
        ) -> Iterator[RepoState]:
            if index == vertex_count:
                new_mask = triple_mask | ((1 << vertex_count) if mark else 0)
                child = (vertex_count + 1, weights + tuple(choices), new_mask)
                if _can_complete(
                    child,
                    target_pair_mass=target_pair_mass,
                    target_triples=target_triples,
                ):
                    yield child
                return
            maximum = min(capacities[index], mass_left, incidence_left)
            for value in range(maximum + 1):
                choices.append(value)
                yield from walk(index + 1, mass_left - value, incidence_left - value)
                choices.pop()

        yield from walk(0, remaining_mass, new_vertex_capacity)


def _stage_path(root: Path, pass_name: str, family: str, vertex_count: int) -> Path:
    return root / f"mass12_{pass_name}_{family}_stage_{vertex_count:02d}.jsonl"


def _shard_pass_name(shard_index: int) -> str:
    if not 0 <= shard_index < SHARD_COUNT:
        raise ValueError("shard index is outside the configured shard range")
    return f"sharded_v1_s{shard_index}"


def _prefix_parent_shard(family: str, class_id: str) -> int:
    digest = hashlib.sha256(
        f"mass12-prefix-shard-v1|{family}|{class_id}".encode()
    ).digest()
    return digest[0] % SHARD_COUNT


def _owned_prefix_parents(
    class_ids: Sequence[str], *, family: str, shard_index: int
) -> list[str]:
    if not 0 <= shard_index < SHARD_COUNT:
        raise ValueError("shard index is outside the configured shard range")
    return [
        class_id
        for class_id in class_ids
        if _prefix_parent_shard(family, class_id) == shard_index
    ]


def _write_root_state(path: Path) -> None:
    if path.exists():
        if _read_lines(path) != ["0:0:"]:
            raise RuntimeError(f"invalid root enumeration state: {path}")
        return
    _atomic_lines(path, ["0:0:"])


def _save_enumeration_checkpoint(path: Path, checkpoint: dict[str, object]) -> None:
    checkpoint["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    _json_atomic(path, checkpoint)


def _save_screen_checkpoint(path: Path, checkpoint: dict[str, object]) -> None:
    checkpoint["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    _json_atomic(path, checkpoint)


def _initialize_enumerator(
    *,
    root: Path,
    checkpoint_path: Path,
    checkpoint: dict[str, object],
    pass_name: str,
    family: str,
    shard_index: int | None = None,
) -> dict[str, object]:
    active_value = checkpoint.get("active_enumerator")
    if active_value is not None:
        active = _json_object(active_value, context="active enumeration checkpoint")
        if (
            active.get("pass_name") != pass_name
            or active.get("family") != family
            or active.get("shard_index") != shard_index
        ):
            raise RuntimeError("active enumeration checkpoint does not match requested family")
        state_value = checkpoint.get("enumerator_state")
        state = _json_object(state_value, context="enumerator_state")
        if state.get("pass_name") != pass_name or state.get("family") != family:
            raise RuntimeError("enumerator state does not match active family")
        active_stage = _integer(active.get("stage_n"), context="active.stage_n")
        state_stage = _integer(state.get("stage_n"), context="enumerator_state.stage_n")
        active_offset = _integer(active.get("output_offset"), context="active.output_offset")
        state_offset = _integer(
            state.get("output_offset"), context="enumerator_state.output_offset"
        )
        state_is_newer = state_stage > active_stage or (
            state_stage == active_stage and state_offset > active_offset
        )
        if state_is_newer:
            active.update(
                {
                    "stage_n": state_stage,
                    "parent_index": _integer(
                        state.get("parent_index"), context="enumerator_state.parent_index"
                    ),
                    "extension_index": _integer(
                        state.get("extension_index"),
                        context="enumerator_state.extension_index",
                    ),
                    "output_offset": state_offset,
                    "stage_raw_generated_count": 0,
                    "last_checkpoint_canonical_count": _integer(
                        checkpoint.get("canonical_count", 0), context="canonical_count"
                    ),
                    "last_checkpoint_monotonic": time.monotonic(),
                }
            )
            if state_stage > 1:
                parent_file = _stage_path(root, pass_name, family, state_stage - 1)
                active["previous_stage_canonical_count"] = len(_read_lines(parent_file))
        active["raw_generated_count"] = max(
            _integer(active.get("raw_generated_count", 0), context="active.raw_generated_count"),
            _integer(checkpoint.get("raw_generated_count", 0), context="raw_generated_count"),
        )
        active["canonical_count"] = _integer(
            checkpoint.get("canonical_count", active.get("canonical_count", 0)),
            context="canonical_count",
        )
        active["last_completed_class_id"] = checkpoint.get(
            "last_completed_class_id", active.get("last_completed_class_id")
        )
        checkpoint["active_enumerator"] = active
        checkpoint["enumerator_state"] = {
            "pass_name": pass_name,
            "family": family,
            "stage_n": active["stage_n"],
            "parent_index": active["parent_index"],
            "extension_index": active["extension_index"],
            "output_offset": active["output_offset"],
        }
        return active
    summary_key = f"{pass_name}_families"
    summaries = _summary_map(checkpoint.get(summary_key, {}), context=summary_key)
    checkpoint[summary_key] = summaries
    if family in summaries:
        raise RuntimeError("requested family is already complete")
    _write_root_state(_stage_path(root, pass_name, family, 0))
    active: dict[str, object] = {
        "pass_name": pass_name,
        "family": family,
        "shard_index": shard_index,
        "stage_n": 1,
        "parent_index": 0,
        "extension_index": 0,
        "output_offset": 0,
        "raw_generated_count": 0,
        "stage_raw_generated_count": 0,
        "canonical_count": 0,
        "last_completed_class_id": None,
        "last_checkpoint_canonical_count": 0,
        "last_checkpoint_monotonic": time.monotonic(),
    }
    checkpoint["active_enumerator"] = active
    checkpoint["enumerator_state"] = {
        "pass_name": pass_name,
        "family": family,
        "stage_n": 1,
        "parent_index": 0,
        "extension_index": 0,
        "output_offset": 0,
    }
    checkpoint["family"] = family
    checkpoint["raw_generated_count"] = 0
    checkpoint["legal_count"] = 0
    checkpoint["canonical_count"] = 0
    checkpoint["last_completed_class_id"] = None
    checkpoint["class_set_digest_inputs_path"] = str(
        _stage_path(root, pass_name, family, TICKET_COUNT)
    )
    checkpoint["pass_name"] = pass_name
    _save_enumeration_checkpoint(checkpoint_path, checkpoint)
    return active


def _generate_family(
    *,
    root: Path,
    checkpoint_path: Path,
    checkpoint: dict[str, object],
    pass_name: str,
    family: str,
    numerator: int,
    denominator: int,
    shard_index: int | None = None,
) -> dict[str, object]:
    summaries_key = f"{pass_name}_families"
    summaries = _summary_map(checkpoint.get(summaries_key, {}), context=summaries_key)
    checkpoint[summaries_key] = summaries
    if family in summaries:
        return summaries[family]
    target_pair_mass = 12 if family == "A" else 9
    target_triples = 0 if family == "A" else 3
    active = _initialize_enumerator(
        root=root,
        checkpoint_path=checkpoint_path,
        checkpoint=checkpoint,
        pass_name=pass_name,
        family=family,
        shard_index=shard_index,
    )
    stage_started = time.monotonic()
    previous_stage_count: int | None = None

    while _integer(active["stage_n"], context="stage_n") <= TICKET_COUNT:
        stage_n = _integer(active["stage_n"], context="stage_n")
        parent_path = _stage_path(root, pass_name, family, stage_n - 1)
        output_path = _stage_path(root, pass_name, family, stage_n)
        parent_keys = sorted(_read_lines(parent_path))
        if shard_index is not None and stage_n == SHARD_SPLIT_STAGE + 1:
            parent_keys = _owned_prefix_parents(
                parent_keys, family=family, shard_index=shard_index
            )
        if not parent_keys:
            raise RuntimeError(f"missing parent stage states: {parent_path}")
        byte_offset = _integer(active["output_offset"], context="output_offset")
        if output_path.exists() and output_path.stat().st_size < byte_offset:
            raise RuntimeError("stage output is shorter than its durable checkpoint")
        seen: set[str] = set(_read_lines(output_path, limit=byte_offset)) if byte_offset else set()
        parent_index = _integer(active["parent_index"], context="parent_index")
        extension_index = _integer(active["extension_index"], context="extension_index")
        canonical_count = len(seen)
        raw_generated_count = _integer(active["raw_generated_count"], context="raw_generated_count")
        stage_raw_generated_count = _integer(
            active.get("stage_raw_generated_count", 0), context="stage_raw_generated_count"
        )
        last_completed = active.get("last_completed_class_id")
        if not output_path.exists():
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.touch()

        with output_path.open("r+b") as stream:
            stream.truncate(byte_offset)
            stream.seek(byte_offset)
            for parent_at in range(parent_index, len(parent_keys)):
                parent = _state_from_key(parent_keys[parent_at])
                skip_extensions = extension_index if parent_at == parent_index else 0
                for extension_at, child in enumerate(
                    _iter_extensions(
                        parent,
                        target_pair_mass=target_pair_mass,
                        target_triples=target_triples,
                    )
                ):
                    if extension_at < skip_extensions:
                        continue
                    raw_generated_count += 1
                    stage_raw_generated_count += 1
                    canonical = _canonicalize_state(child)
                    key = _state_key(canonical)
                    if key not in seen:
                        stream.write(key.encode("ascii") + b"\n")
                        seen.add(key)
                        canonical_count += 1
                        last_completed = key
                    active["parent_index"] = parent_at
                    active["extension_index"] = extension_at + 1
                    active["raw_generated_count"] = raw_generated_count
                    active["stage_raw_generated_count"] = stage_raw_generated_count
                    active["canonical_count"] = canonical_count
                    active["last_completed_class_id"] = last_completed
                    if (
                        raw_generated_count > MAX_RAW_EXTENSIONS_PER_FAMILY
                        or canonical_count > MAX_CANONICAL_STAGE_STATES
                    ):
                        stream.flush()
                        os.fsync(stream.fileno())
                        active["output_offset"] = stream.tell()
                        active["last_checkpoint_canonical_count"] = canonical_count
                        active["last_checkpoint_monotonic"] = time.monotonic()
                        checkpoint["enumerator_state"] = {
                            "pass_name": pass_name,
                            "family": family,
                            "stage_n": stage_n,
                            "parent_index": parent_at,
                            "extension_index": extension_at + 1,
                            "output_offset": active["output_offset"],
                        }
                        checkpoint["raw_generated_count"] = raw_generated_count
                        checkpoint["canonical_count"] = canonical_count
                        checkpoint["status"] = "MASS12_REQUIRES_BRANCH_AND_BOUND"
                        checkpoint["resource_stop"] = {
                            "stage_vertices": stage_n,
                            "stage_canonical_count": canonical_count,
                            "raw_extensions_so_far": raw_generated_count,
                            "limits": {
                                "max_canonical_stage_states": MAX_CANONICAL_STAGE_STATES,
                                "max_raw_extensions_per_family": MAX_RAW_EXTENSIONS_PER_FAMILY,
                            },
                        }
                        _save_enumeration_checkpoint(checkpoint_path, checkpoint)
                        raise _Mass12ResourceLimit(checkpoint["resource_stop"])
                    now = time.monotonic()
                    last_count = _integer(
                        active["last_checkpoint_canonical_count"],
                        context="last_checkpoint_canonical_count",
                    )
                    last_time = _floating(
                        active["last_checkpoint_monotonic"],
                        context="last_checkpoint_monotonic",
                    )
                    if (
                        canonical_count - last_count >= CHECKPOINT_INTERVAL
                        or now - last_time >= CHECKPOINT_SECONDS
                    ):
                        stream.flush()
                        os.fsync(stream.fileno())
                        active["output_offset"] = stream.tell()
                        active["last_checkpoint_canonical_count"] = canonical_count
                        active["last_checkpoint_monotonic"] = now
                        checkpoint["enumerator_state"] = {
                            "pass_name": pass_name,
                            "family": family,
                            "stage_n": stage_n,
                            "parent_index": active["parent_index"],
                            "extension_index": active["extension_index"],
                            "output_offset": active["output_offset"],
                        }
                        checkpoint["raw_generated_count"] = raw_generated_count
                        checkpoint["legal_count"] = 0
                        checkpoint["canonical_count"] = canonical_count
                        checkpoint["last_completed_class_id"] = last_completed
                        _save_enumeration_checkpoint(checkpoint_path, checkpoint)
                        print(
                            json.dumps(
                                {
                                    "phase": "mass12_enumeration",
                                    "pass": pass_name,
                                    "family": family,
                                    "stage_vertices": stage_n,
                                    "raw_generated": raw_generated_count,
                                    "canonical_stage_count": canonical_count,
                                    "canonicalization_rate_per_sec": round(
                                        stage_raw_generated_count
                                        / max(now - stage_started, 0.001),
                                        2,
                                    ),
                                },
                                sort_keys=True,
                            ),
                            flush=True,
                        )
                active["parent_index"] = parent_at + 1
                active["extension_index"] = 0
                now = time.monotonic()
                if now - _floating(
                    active["last_checkpoint_monotonic"], context="last_checkpoint_monotonic"
                ) >= CHECKPOINT_SECONDS:
                    stream.flush()
                    os.fsync(stream.fileno())
                    active["output_offset"] = stream.tell()
                    active["last_checkpoint_canonical_count"] = canonical_count
                    active["last_checkpoint_monotonic"] = now
                    checkpoint["enumerator_state"] = {
                        "pass_name": pass_name,
                        "family": family,
                        "stage_n": stage_n,
                        "parent_index": parent_at + 1,
                        "extension_index": 0,
                        "output_offset": active["output_offset"],
                    }
                    checkpoint["raw_generated_count"] = raw_generated_count
                    checkpoint["canonical_count"] = canonical_count
                    checkpoint["last_completed_class_id"] = last_completed
                    _save_enumeration_checkpoint(checkpoint_path, checkpoint)
            stream.flush()
            os.fsync(stream.fileno())
            active["output_offset"] = stream.tell()

        previous_stage_count = (
            _integer(
                active.get("previous_stage_canonical_count", 0),
                context="previous_stage_canonical_count",
            )
            or None
        )
        projected_final = canonical_count
        if previous_stage_count is not None and previous_stage_count > 0 and stage_n >= 7:
            growth = min(1.5, max(1.0, canonical_count / previous_stage_count))
            projected_final = int(canonical_count * growth ** (TICKET_COUNT - stage_n))
        checkpoint["resource_projection"] = {
            "stage_vertices": stage_n,
            "stage_canonical_count": canonical_count,
            "stage_raw_extensions": stage_raw_generated_count,
            "projected_final_class_upper_estimate": projected_final,
            "projection_method": "last-stage canonical growth ratio capped at 1.5, floored at 1",
            "limits": {
                "max_canonical_stage_states": MAX_CANONICAL_STAGE_STATES,
                "max_raw_extensions_per_family": MAX_RAW_EXTENSIONS_PER_FAMILY,
                "max_projected_final_classes": MAX_PROJECTED_FINAL_CLASSES,
            },
        }
        if (
            canonical_count > MAX_CANONICAL_STAGE_STATES
            or raw_generated_count > MAX_RAW_EXTENSIONS_PER_FAMILY
            or projected_final > MAX_PROJECTED_FINAL_CLASSES
        ):
            checkpoint["status"] = "MASS12_REQUIRES_BRANCH_AND_BOUND"
            checkpoint["resource_stop"] = dict(checkpoint["resource_projection"])
            _save_enumeration_checkpoint(checkpoint_path, checkpoint)
            raise _Mass12ResourceLimit(checkpoint["resource_projection"])

        if stage_n < TICKET_COUNT:
            active.update(
                {
                    "stage_n": stage_n + 1,
                    "parent_index": 0,
                    "extension_index": 0,
                    "output_offset": 0,
                    "previous_stage_canonical_count": canonical_count,
                    "stage_raw_generated_count": 0,
                    "canonical_count": 0,
                    "last_completed_class_id": None,
                    "last_checkpoint_canonical_count": 0,
                    "last_checkpoint_monotonic": time.monotonic(),
                }
            )
            checkpoint["enumerator_state"] = {
                "pass_name": pass_name,
                "family": family,
                "stage_n": stage_n + 1,
                "parent_index": 0,
                "extension_index": 0,
                "output_offset": 0,
            }
            checkpoint["raw_generated_count"] = raw_generated_count
            checkpoint["canonical_count"] = 0
            checkpoint["last_completed_class_id"] = None
            _save_enumeration_checkpoint(checkpoint_path, checkpoint)
            print(
                json.dumps(
                    {
                        "phase": "mass12_stage_complete",
                        "pass": pass_name,
                        "family": family,
                        "stage_vertices": stage_n,
                        "canonical_stage_count": canonical_count,
                        "stage_wall_time_sec": round(time.monotonic() - stage_started, 3),
                    },
                    sort_keys=True,
                ),
                flush=True,
            )
        else:
            break

    final_path = _stage_path(root, pass_name, family, TICKET_COUNT)
    raw_states: list[str] = []
    legal_ids: list[str] = []
    for key in sorted(_read_lines(final_path)):
        state = _state_from_key(key)
        if sum(state[1]) != target_pair_mass or state[2].bit_count() != target_triples:
            continue
        raw_states.append(key)
        try:
            _portfolio_from_state(state, family)
        except ValueError:
            continue
        legal_ids.append(f"{family}:{key}")
    if len(set(legal_ids)) != len(legal_ids):
        raise RuntimeError("canonical generator emitted duplicate final class identities")
    class_path = root / f"mass12_{pass_name}_{family}_classes.txt"
    _atomic_lines(class_path, legal_ids)
    summary: dict[str, object] = {
        "family": family,
        "raw_count": _integer(active["raw_generated_count"], context="raw_generated_count"),
        "canonical_state_count_before_ticket_legality": len(raw_states),
        "legal_count": len(legal_ids),
        "canonical_count": len(set(legal_ids)),
        "class_set_sha256": _sha256_lines(legal_ids),
        "illegal_duplicate_ticket_count": len(raw_states) - len(legal_ids),
        "class_ids_path": str(class_path),
        "stage_path": str(final_path),
    }
    if shard_index is not None:
        prefix_keys = sorted(
            _read_lines(_stage_path(root, pass_name, family, SHARD_SPLIT_STAGE))
        )
        owned_prefix_keys = _owned_prefix_parents(
            prefix_keys, family=family, shard_index=shard_index
        )
        summary["shard_reproduction"] = {
            "strategy": SHARDING_STRATEGY,
            "shard_index": shard_index,
            "shard_count": SHARD_COUNT,
            "split_stage_vertices": SHARD_SPLIT_STAGE,
            "recomputed_prefix_state_count": len(prefix_keys),
            "recomputed_prefix_state_sha256": _sha256_lines(prefix_keys),
            "owned_parent_count": len(owned_prefix_keys),
            "owned_parent_sha256": _sha256_lines(owned_prefix_keys),
        }
    summaries_key = f"{pass_name}_families"
    summaries = _summary_map(checkpoint.get(summaries_key, {}), context=summaries_key)
    summaries[family] = summary
    checkpoint[summaries_key] = summaries
    checkpoint["active_enumerator"] = None
    checkpoint["enumerator_state"] = {
        "pass_name": pass_name,
        "family": family,
        "stage_n": TICKET_COUNT,
        "status": "COMPLETE",
        "class_set_digest_inputs_path": str(class_path),
    }
    checkpoint["raw_generated_count"] = _integer(
        active["raw_generated_count"], context="raw_generated_count"
    )
    checkpoint["legal_count"] = len(legal_ids)
    checkpoint["canonical_count"] = len(set(legal_ids))
    checkpoint["last_completed_class_id"] = legal_ids[-1] if legal_ids else None
    checkpoint["class_set_digest_inputs_path"] = str(class_path)
    _save_enumeration_checkpoint(checkpoint_path, checkpoint)
    return summary


def _new_mass12_checkpoint(
    numerator: int, denominator: int, requested_family: str
) -> dict[str, object]:
    checkpoint = _base_checkpoint("mass12_screen", numerator, denominator, family=requested_family)
    checkpoint.update(
        {
            "status": "RUNNING",
            "requested_family": requested_family,
            "pass_name": "full",
            "active_enumerator": None,
            "enumerator_state": None,
            "raw_generated_count": 0,
            "legal_count": 0,
            "canonical_count": 0,
            "last_completed_class_id": None,
            "full_families": {},
            "sharded_families": {},
            "sharding_strategy": SHARDING_STRATEGY,
            "class_set_digest_inputs_path": None,
            "pruned_count": 0,
            "survivor_count": 0,
            "exact_scored_count": 0,
            "current_best_outcome_count": incumbent_outcome_count(numerator, denominator),
            "current_best_class_id": None,
        }
    )
    return checkpoint


def _load_family_class_ids(root: Path, pass_name: str, family: str) -> list[str]:
    path = root / f"mass12_{pass_name}_{family}_classes.txt"
    return sorted(_read_lines(path))


def _aggregate_sharded_family(
    *,
    root: Path,
    checkpoint: dict[str, object],
    family: str,
    full_summary: dict[str, object],
) -> dict[str, object]:
    full_prefix = sorted(
        _read_lines(_stage_path(root, "full", family, SHARD_SPLIT_STAGE))
    )
    full_prefix_digest = _sha256_lines(full_prefix)
    expected_partitions = [
        _owned_prefix_parents(full_prefix, family=family, shard_index=index)
        for index in range(SHARD_COUNT)
    ]
    if sum(map(len, expected_partitions)) != len(full_prefix):
        raise RuntimeError("deterministic shard parent partition is incomplete")

    shard_summaries: list[dict[str, object]] = []
    shard_class_sets: list[set[str]] = []
    raw_state_union: set[str] = set()
    for shard_index in range(SHARD_COUNT):
        pass_name = _shard_pass_name(shard_index)
        summaries_key = f"{pass_name}_families"
        summaries = _summary_map(checkpoint.get(summaries_key, {}), context=summaries_key)
        shard_summary = summaries.get(family)
        if shard_summary is None:
            raise RuntimeError(f"sharded family is incomplete: {family}/{shard_index}")
        shard_reproduction = _json_object(
            shard_summary.get("shard_reproduction"), context="shard reproduction summary"
        )
        prefix_keys = sorted(
            _read_lines(_stage_path(root, pass_name, family, SHARD_SPLIT_STAGE))
        )
        if prefix_keys != full_prefix:
            raise RuntimeError(f"independent shard prefix mismatch: {family}/{shard_index}")
        owned_parents = expected_partitions[shard_index]
        if (
            shard_reproduction.get("strategy") != SHARDING_STRATEGY
            or shard_reproduction.get("shard_index") != shard_index
            or shard_reproduction.get("split_stage_vertices") != SHARD_SPLIT_STAGE
            or shard_reproduction.get("recomputed_prefix_state_count") != len(prefix_keys)
            or shard_reproduction.get("recomputed_prefix_state_sha256")
            != full_prefix_digest
            or shard_reproduction.get("owned_parent_count") != len(owned_parents)
            or shard_reproduction.get("owned_parent_sha256") != _sha256_lines(owned_parents)
        ):
            raise RuntimeError(f"deterministic shard ownership mismatch: {family}/{shard_index}")

        parent_path = root / f"mass12_sharded_{family}_s{shard_index}_parent_states.txt"
        _atomic_lines(parent_path, owned_parents)
        shard_class_ids = _load_family_class_ids(root, pass_name, family)
        if len(shard_class_ids) != len(set(shard_class_ids)):
            raise RuntimeError(f"duplicate class ids inside shard: {family}/{shard_index}")
        shard_class_sets.append(set(shard_class_ids))
        stage_keys = _read_lines(_stage_path(root, pass_name, family, TICKET_COUNT))
        target_pair_mass = 12 if family == "A" else 9
        target_triples = 0 if family == "A" else 3
        for key in stage_keys:
            state = _state_from_key(key)
            if sum(state[1]) == target_pair_mass and state[2].bit_count() == target_triples:
                raw_state_union.add(key)
        shard_summaries.append(
            {
                **shard_summary,
                "owned_parent_ids_path": str(parent_path),
                "owned_parent_count": len(owned_parents),
                "owned_parent_sha256": _sha256_lines(owned_parents),
            }
        )

    flattened_parents = [
        parent
        for partition in expected_partitions
        for parent in partition
    ]
    if len(flattened_parents) != len(set(flattened_parents)) or set(flattened_parents) != set(
        full_prefix
    ):
        raise RuntimeError(f"shard parent partitions do not cover the prefix: {family}")

    merged_class_set: set[str] = set()
    for shard_class_set in shard_class_sets:
        merged_class_set.update(shard_class_set)
    merged_class_ids = sorted(merged_class_set)
    if not set(merged_class_ids).issubset({f"{family}:{key}" for key in raw_state_union}):
        raise RuntimeError(f"sharded legal classes are absent from their final states: {family}")
    class_path = root / f"mass12_sharded_{family}_classes.txt"
    _atomic_lines(class_path, merged_class_ids)
    shard_final_counts = [len(class_ids) for class_ids in shard_class_sets]
    overlap_count = sum(shard_final_counts) - len(merged_class_ids)
    summary: dict[str, object] = {
        "family": family,
        "raw_count": sum(
            _integer(item.get("raw_count"), context="shard raw_count")
            for item in shard_summaries
        ),
        "canonical_state_count_before_ticket_legality": len(raw_state_union),
        "legal_count": len(merged_class_ids),
        "canonical_count": len(merged_class_ids),
        "class_set_sha256": _sha256_lines(merged_class_ids),
        "illegal_duplicate_ticket_count": len(raw_state_union) - len(merged_class_ids),
        "class_ids_path": str(class_path),
        "shard_stage_paths": [item["stage_path"] for item in shard_summaries],
        "shards": [
            {
                "shard_index": index,
                "legal_count": shard_final_counts[index],
                "class_set_sha256": _sha256_lines(sorted(shard_class_sets[index])),
                "class_ids_path": shard_summaries[index]["class_ids_path"],
                "owned_parent_count": shard_summaries[index]["owned_parent_count"],
                "owned_parent_sha256": shard_summaries[index]["owned_parent_sha256"],
            }
            for index in range(SHARD_COUNT)
        ],
        "sharding_strategy": SHARDING_STRATEGY,
        "split_stage_vertices": SHARD_SPLIT_STAGE,
        "recomputed_prefix_count": len(full_prefix),
        "recomputed_prefix_sha256": full_prefix_digest,
        "overlap_class_count_across_shards": overlap_count,
    }
    if (
        summary["canonical_state_count_before_ticket_legality"]
        != full_summary["canonical_state_count_before_ticket_legality"]
        or summary["illegal_duplicate_ticket_count"]
        != full_summary["illegal_duplicate_ticket_count"]
    ):
        raise RuntimeError(f"sharded final-state coverage mismatch: {family}")
    family_summaries = _summary_map(
        checkpoint.get("sharded_families", {}), context="sharded_families"
    )
    family_summaries[family] = summary
    checkpoint["sharded_families"] = family_summaries
    return summary


def _write_shard_files(root: Path, families: Sequence[str]) -> dict[str, object]:
    buckets: list[list[str]] = [[], []]
    for family in families:
        for shard_index in range(SHARD_COUNT):
            buckets[shard_index].extend(
                _load_family_class_ids(root, _shard_pass_name(shard_index), family)
            )
    for index, values in enumerate(buckets):
        values.sort()
        _atomic_lines(root / f"mass12_shard_{index}_class_ids.txt", values)
    reproduced = sorted(set(buckets[0]).union(buckets[1]))
    return {
        "shard_count": SHARD_COUNT,
        "strategy": SHARDING_STRATEGY,
        "split_stage_vertices": SHARD_SPLIT_STAGE,
        "shard_counts": [len(buckets[0]), len(buckets[1])],
        "cross_shard_duplicate_class_count": sum(map(len, buckets)) - len(reproduced),
        "sharded_legal_canonical_count": len(reproduced),
        "sharded_class_set_sha256": _sha256_lines(reproduced),
        "shard_files": [
            str(root / "mass12_shard_0_class_ids.txt"),
            str(root / "mass12_shard_1_class_ids.txt"),
        ],
    }


def _combined_class_ids(root: Path, pass_name: str, families: Sequence[str]) -> list[str]:
    result: list[str] = []
    for family in families:
        result.extend(_load_family_class_ids(root, pass_name, family))
    return sorted(result)


def _screen_mass12(
    *,
    root: Path,
    checkpoint_path: Path,
    checkpoint: dict[str, object],
    families: Sequence[str],
    numerator: int,
    denominator: int,
) -> dict[str, object]:
    incumbent = incumbent_outcome_count(numerator, denominator)
    class_ids = _combined_class_ids(root, "full", families)
    class_digest = _sha256_lines(class_ids)
    screen_path = root / "mass12_screen_results.jsonl"
    exact_path = root / "mass12_exact_results.jsonl"
    screen_checkpoint_path = root / "mass12_screen_checkpoint.json"

    screen_checkpoint = _read_checkpoint(screen_checkpoint_path)
    if screen_checkpoint is None:
        screen_checkpoint = _base_checkpoint("mass12_screen_progress", numerator, denominator)
        screen_checkpoint.update(
            {
                "requested_family": checkpoint.get("family"),
                "families": list(families),
                "full_class_set_sha256": class_digest,
                "full_legal_canonical_count": len(class_ids),
                "screen_index": 0,
                "screen_output_offset": 0,
                "last_completed_class_id": None,
                "pruned_count": 0,
                "survivor_count": 0,
                "exact_scored_count": 0,
                "exact_output_offset": 0,
                "current_best_outcome_count": incumbent,
                "current_best_class_id": None,
                "status": "SCREENING",
            }
        )
        _save_screen_checkpoint(screen_checkpoint_path, screen_checkpoint)
    else:
        _validate_checkpoint_identity(
            screen_checkpoint,
            phase="mass12_screen_progress",
            numerator=numerator,
            denominator=denominator,
        )
        if screen_checkpoint.get("families") != list(families):
            raise RuntimeError("screen checkpoint family mismatch")
        if screen_checkpoint.get("full_class_set_sha256") != class_digest:
            raise RuntimeError("screen checkpoint class-set digest mismatch")

    start_index = _integer(screen_checkpoint.get("screen_index", 0), context="screen_index")
    pruned_count = _integer(screen_checkpoint.get("pruned_count", 0), context="pruned_count")
    survivor_count = _integer(
        screen_checkpoint.get("survivor_count", 0), context="survivor_count"
    )
    screen_offset = _integer(
        screen_checkpoint.get("screen_output_offset", 0), context="screen_output_offset"
    )
    if screen_path.exists() and screen_path.stat().st_size < screen_offset:
        raise RuntimeError("screen results are shorter than their checkpoint")
    if not screen_path.exists():
        screen_path.touch()
    screen_started = time.monotonic()
    last_saved = start_index
    last_saved_at = screen_started
    with screen_path.open("r+b") as output:
        output.truncate(screen_offset)
        output.seek(screen_offset)
        for index in range(start_index, len(class_ids)):
            family, state_key = class_ids[index].split(":", 1)
            portfolio = _portfolio_from_state(_state_from_key(state_key), family)
            portfolio_hash = canonical_portfolio_sha256(portfolio)
            bound = u3_outcome_count(portfolio)
            safe_prune = bound <= incumbent
            row: dict[str, object] = {
                "class_id": class_ids[index],
                "family": family,
                "portfolio_sha256": portfolio_hash,
                "u3_outcome_count": bound,
                "bound_gap_vs_incumbent": bound - incumbent,
                "screen_status": "SAFE_PRUNE" if safe_prune else "EXACT_SURVIVOR",
            }
            output_offset = _append_json_line(output, row)
            if safe_prune:
                pruned_count += 1
            else:
                survivor_count += 1
            processed = index + 1
            now = time.monotonic()
            if (
                processed - last_saved >= CHECKPOINT_INTERVAL
                or now - last_saved_at >= CHECKPOINT_SECONDS
                or processed == len(class_ids)
            ):
                output.flush()
                os.fsync(output.fileno())
                screen_checkpoint.update(
                    {
                        "screen_index": processed,
                        "screen_output_offset": output_offset,
                        "last_completed_class_id": class_ids[index],
                        "pruned_count": pruned_count,
                        "survivor_count": survivor_count,
                        "status": "SCREENING",
                    }
                )
                _save_screen_checkpoint(screen_checkpoint_path, screen_checkpoint)
                last_saved = processed
                last_saved_at = now
                print(
                    json.dumps(
                        {
                            "phase": "mass12_screen",
                            "processed": processed,
                            "total": len(class_ids),
                            "pruned": pruned_count,
                            "survivors": survivor_count,
                        },
                        sort_keys=True,
                    ),
                    flush=True,
                )

    screen_checkpoint.update(
        {
            "screen_index": len(class_ids),
            "screen_output_offset": screen_path.stat().st_size,
            "pruned_count": pruned_count,
            "survivor_count": survivor_count,
            "status": "SCREENED",
        }
    )
    _save_screen_checkpoint(screen_checkpoint_path, screen_checkpoint)
    screen_completed = time.monotonic()

    survivor_rows: list[dict[str, object]] = []
    for line in _read_lines(screen_path):
        row = _json_object(json.loads(line), context="screen result row")
        if row["screen_status"] == "EXACT_SURVIVOR":
            survivor_rows.append(row)
    if len(survivor_rows) != survivor_count:
        raise RuntimeError("screen survivor count does not match durable screen rows")

    scored_count = _integer(
        screen_checkpoint.get("exact_scored_count", 0), context="exact_scored_count"
    )
    exact_offset = _integer(
        screen_checkpoint.get("exact_output_offset", 0), context="exact_output_offset"
    )
    if exact_path.exists() and exact_path.stat().st_size < exact_offset:
        raise RuntimeError("exact result log is shorter than its checkpoint")
    if not exact_path.exists():
        exact_path.touch()
    prior_exact_rows = _read_lines(exact_path, limit=exact_offset)
    if len(prior_exact_rows) != scored_count:
        raise RuntimeError("exact score checkpoint count does not match durable result rows")
    current_best = _integer(
        screen_checkpoint.get("current_best_outcome_count", incumbent),
        context="current_best_outcome_count",
    )
    current_best_id = screen_checkpoint.get("current_best_class_id")
    exact_started = time.monotonic()
    exact_module: Any = __import__(
        "lottolab.research.b649_official_any_prize_exact",
        fromlist=["all_main_draw_masks", "evaluate_portfolio"],
    )
    draws: Any = exact_module.all_main_draw_masks(POOL_SIZE, DRAW_SIZE)
    with exact_path.open("r+b") as output:
        output.truncate(exact_offset)
        output.seek(exact_offset)
        for index in range(scored_count, len(survivor_rows)):
            screen_row = survivor_rows[index]
            _, state_key = str(screen_row["class_id"]).split(":", 1)
            family = str(screen_row["family"])
            portfolio = _portfolio_from_state(_state_from_key(state_key), family)
            scored = exact_module.evaluate_portfolio(portfolio, draws=draws)
            exact_count = scored.official_any_prize_outcome_count
            exact_fraction = Fraction(exact_count, total_official_outcomes())
            row = {
                "class_id": screen_row["class_id"],
                "family": family,
                "portfolio_sha256": screen_row["portfolio_sha256"],
                "u3_outcome_count": screen_row["u3_outcome_count"],
                "official_any_prize_outcome_count": exact_count,
                "fraction": str(exact_fraction),
                "delta_vs_incumbent": str(
                    exact_fraction - Fraction(numerator, denominator)
                ),
            }
            output_offset = _append_json_line(output, row)
            scored_count += 1
            if exact_count > current_best:
                current_best = exact_count
                current_best_id = screen_row["class_id"]
            output.flush()
            os.fsync(output.fileno())
            screen_checkpoint.update(
                {
                    "exact_scored_count": scored_count,
                    "exact_output_offset": output_offset,
                    "current_best_outcome_count": current_best,
                    "current_best_class_id": current_best_id,
                    "status": "EXACT_SCORING",
                }
            )
            _save_screen_checkpoint(screen_checkpoint_path, screen_checkpoint)
            if scored_count % 25 == 0 or scored_count == len(survivor_rows):
                print(
                    json.dumps(
                        {
                            "phase": "mass12_exact_scoring",
                            "exact_scored": scored_count,
                            "survivors": len(survivor_rows),
                            "best_outcome_count": current_best,
                        },
                        sort_keys=True,
                    ),
                    flush=True,
                )

    exact_rows = [json.loads(line) for line in _read_lines(exact_path)]
    if len(exact_rows) != len(survivor_rows):
        raise RuntimeError("every U3 survivor must have one exact result")
    best_count = max(
        [incumbent, *(int(row["official_any_prize_outcome_count"]) for row in exact_rows)]
    )
    best_row = next(
        (row for row in exact_rows if int(row["official_any_prize_outcome_count"]) == best_count),
        None,
    )
    best_fraction = Fraction(best_count, total_official_outcomes())
    best_delta = best_fraction - Fraction(numerator, denominator)
    screen_checkpoint.update(
        {
            "exact_scored_count": len(exact_rows),
            "current_best_outcome_count": best_count,
            "current_best_class_id": best_row["class_id"] if best_row else None,
            "status": "COMPLETE",
        }
    )
    _save_screen_checkpoint(screen_checkpoint_path, screen_checkpoint)
    family_summaries = _summary_map(
        checkpoint.get("full_families", {}), context="full_families"
    )
    return {
        "families": {family: family_summaries[family] for family in families},
        "total_legal_canonical_count": len(class_ids),
        "full_class_set_sha256": class_digest,
        "pruned_class_count": pruned_count,
        "survivor_class_count": survivor_count,
        "exact_evaluation_count": len(exact_rows),
        "best_exact": str(best_fraction),
        "best_delta": str(best_delta),
        "best_class_id": best_row["class_id"] if best_row else None,
        "best_portfolio_sha256": best_row["portfolio_sha256"] if best_row else None,
        "exact_rows": exact_rows,
        "screen_wall_time_sec": round(screen_completed - screen_started, 3),
        "exact_scoring_wall_time_sec": round(time.monotonic() - exact_started, 3),
    }


def _validated_mass11_certificate(root: Path) -> dict[str, object]:
    result_path = root / "mass11_certificate_result.json"
    if not result_path.exists():
        raise RuntimeError("MASS11_CERTIFICATE_REQUIRED: result file is missing")
    result = _json_object(
        json.loads(result_path.read_text(encoding="utf-8")), context="mass-11 result"
    )
    expected = {
        "status": "PASS",
        "authority_commit": BASE_HEAD,
        "raw_classes": 89_262,
        "legal_classes": 89_198,
        "safe_pruned": 89_197,
        "survivors": 1,
        "survivor_exact": "536005/1827672",
    }
    for key, value in expected.items():
        if result.get(key) != value:
            raise RuntimeError(f"MASS11_CERTIFICATE_REQUIRED: {key}={result.get(key)!r}")
    return result


def _write_mass12_result(root: Path, result: dict[str, object]) -> None:
    _json_atomic(root / "mass12_result.json", result)


def _resource_limited_result(
    *,
    root: Path,
    checkpoint_path: Path,
    checkpoint: dict[str, object],
    requested_family: str,
    projection: object,
) -> dict[str, object]:
    result: dict[str, object] = {
        "schema_version": CHECKPOINT_SCHEMA,
        "task_id": TASK_ID,
        "base_head": BASE_HEAD,
        "base_tree": BASE_TREE,
        "sharding_strategy": SHARDING_STRATEGY,
        "requested_family": requested_family,
        "final_decision": "MASS12_REQUIRES_BRANCH_AND_BOUND",
        "exhaustive_status": "NOT_PROVEN",
        "global_k10_optimum_status": "UNKNOWN",
        "resource_projection": projection,
        "completed_full_families": checkpoint.get("full_families", {}),
        "completed_sharded_families": checkpoint.get("sharded_families", {}),
    }
    checkpoint["status"] = "MASS12_REQUIRES_BRANCH_AND_BOUND"
    checkpoint["final_decision"] = result["final_decision"]
    checkpoint["resource_stop"] = projection
    _save_enumeration_checkpoint(checkpoint_path, checkpoint)
    _write_mass12_result(root, result)
    print(json.dumps(result, sort_keys=True), flush=True)
    return result


def _resource_projection_within_current_limits(
    projection: object, active_enumerator: object = None
) -> bool:
    values = _json_object(projection, context="resource stop")
    if "max_screen_classes" in values:
        return _integer(
            values.get("full_legal_canonical_count"), context="full_legal_canonical_count"
        ) <= MAX_SCREEN_CLASSES
    stage_count = values.get("stage_canonical_count")
    if stage_count is not None and _integer(
        stage_count, context="stage_canonical_count"
    ) > MAX_CANONICAL_STAGE_STATES:
        return False
    active: dict[str, object] | None = None
    if active_enumerator is not None:
        active = _json_object(active_enumerator, context="active enumeration checkpoint")
    raw_count = values.get("raw_extensions_so_far")
    if raw_count is None and active is not None:
        raw_count = active.get("raw_generated_count")
    if raw_count is not None and _integer(
        raw_count, context="raw_extensions_so_far"
    ) > MAX_RAW_EXTENSIONS_PER_FAMILY:
        return False
    projected = values.get("projected_final_class_upper_estimate")
    if active is not None and values.get("stage_canonical_count") is not None:
        previous_stage_count = _integer(
            active.get("previous_stage_canonical_count", 0),
            context="previous_stage_canonical_count",
        )
        stage_n = _integer(active.get("stage_n", 0), context="stage_n")
        stage_count = _integer(
            values["stage_canonical_count"], context="stage_canonical_count"
        )
        if previous_stage_count > 0 and stage_n >= 7:
            growth = min(1.5, max(1.0, stage_count / previous_stage_count))
            projected = int(stage_count * growth ** (TICKET_COUNT - stage_n))
    if projected is not None and _integer(
        projected, context="projected_final_class_upper_estimate"
    ) > MAX_PROJECTED_FINAL_CLASSES:
        return False
    return stage_count is not None or raw_count is not None or projected is not None


def _run_mass12(
    *,
    numerator: int,
    denominator: int,
    requested_family: str,
    root: Path,
    resume: bool,
) -> dict[str, object]:
    _require_base_identity()
    _validated_mass11_certificate(root)
    structural_proof = prove_mass12_profiles()
    checkpoint_path = root / "mass12_enumeration_checkpoint.json"
    checkpoint = _read_checkpoint(checkpoint_path) if resume else None
    result_path = root / "mass12_result.json"
    if checkpoint is not None:
        _validate_checkpoint_identity(
            checkpoint, phase="mass12_screen", numerator=numerator, denominator=denominator
        )
        checkpoint_family = checkpoint.get("requested_family")
        if checkpoint_family is None and result_path.exists():
            prior_result = _json_object(
                json.loads(result_path.read_text(encoding="utf-8")),
                context="prior mass-12 result",
            )
            checkpoint_family = prior_result.get("requested_family")
            if checkpoint_family is not None:
                checkpoint["requested_family"] = checkpoint_family
        if checkpoint_family != requested_family:
            raise RuntimeError("mass-12 checkpoint family mismatch")
        if checkpoint.get("structural_profile_proof") != structural_proof:
            raise RuntimeError("mass-12 checkpoint structural profile proof mismatch")
        if checkpoint.get("sharding_strategy") != SHARDING_STRATEGY:
            active_value = checkpoint.get("active_enumerator")
            active_pass = None
            if active_value is not None:
                active_pass = _json_object(
                    active_value, context="active enumeration checkpoint"
                ).get("pass_name")
            checkpoint["sharding_strategy"] = SHARDING_STRATEGY
            checkpoint["sharded_families"] = {}
            if active_pass != "full":
                checkpoint["active_enumerator"] = None
                checkpoint["enumerator_state"] = None
                checkpoint["status"] = "RUNNING"
                checkpoint.pop("resource_stop", None)
                checkpoint.pop("final_decision", None)
            _save_enumeration_checkpoint(checkpoint_path, checkpoint)
        if checkpoint.get("status") == "MASS12_REQUIRES_BRANCH_AND_BOUND":
            projection = checkpoint.get("resource_stop")
            if _resource_projection_within_current_limits(
                projection, checkpoint.get("active_enumerator")
            ):
                checkpoint["status"] = "RUNNING"
                checkpoint.pop("resource_stop", None)
                checkpoint.pop("final_decision", None)
                _save_enumeration_checkpoint(checkpoint_path, checkpoint)
            elif not result_path.exists():
                return _resource_limited_result(
                    root=root,
                    checkpoint_path=checkpoint_path,
                    checkpoint=checkpoint,
                    requested_family=requested_family,
                    projection=checkpoint.get("resource_stop"),
                )
            else:
                prior_result = _json_object(
                    json.loads(result_path.read_text(encoding="utf-8")),
                    context="mass-12 result",
                )
                if prior_result.get("sharding_strategy") == SHARDING_STRATEGY:
                    return prior_result
                return _resource_limited_result(
                    root=root,
                    checkpoint_path=checkpoint_path,
                    checkpoint=checkpoint,
                    requested_family=requested_family,
                    projection=checkpoint.get("resource_stop"),
                )
        if checkpoint.get("status") == "COMPLETE" and result_path.exists():
            return _json_object(
                json.loads(result_path.read_text(encoding="utf-8")),
                context="mass-12 result",
            )
    else:
        if not resume and checkpoint_path.exists():
            raise RuntimeError("checkpoint exists; pass --resume to continue it")
        checkpoint = _new_mass12_checkpoint(numerator, denominator, requested_family)
        checkpoint["structural_profile_proof"] = structural_proof
        _save_enumeration_checkpoint(checkpoint_path, checkpoint)

    families = ("A", "B") if requested_family == "all" else (requested_family,)
    try:
        for family in families:
            _generate_family(
                root=root,
                checkpoint_path=checkpoint_path,
                checkpoint=checkpoint,
                pass_name="full",
                family=family,
                numerator=numerator,
                denominator=denominator,
            )
        for shard_index in range(SHARD_COUNT):
            pass_name = _shard_pass_name(shard_index)
            for family in families:
                _generate_family(
                    root=root,
                    checkpoint_path=checkpoint_path,
                    checkpoint=checkpoint,
                    pass_name=pass_name,
                    family=family,
                    numerator=numerator,
                    denominator=denominator,
                    shard_index=shard_index,
                )
        full_summaries = _summary_map(checkpoint["full_families"], context="full_families")
        for family in families:
            _aggregate_sharded_family(
                root=root,
                checkpoint=checkpoint,
                family=family,
                full_summary=full_summaries[family],
            )
    except _Mass12ResourceLimit as exc:
        return _resource_limited_result(
            root=root,
            checkpoint_path=checkpoint_path,
            checkpoint=checkpoint,
            requested_family=requested_family,
            projection=exc.projection,
        )

    full_ids = _combined_class_ids(root, "full", families)
    sharded_ids = _combined_class_ids(root, "sharded", families)
    full_digest = _sha256_lines(full_ids)
    shard_summary = _write_shard_files(root, families)
    shard_digest = str(shard_summary["sharded_class_set_sha256"])
    if (
        len(full_ids) != len(set(full_ids))
        or len(sharded_ids) != len(set(sharded_ids))
        or len(full_ids) != len(sharded_ids)
        or full_digest != shard_digest
    ):
        raise RuntimeError("FULL_SHARDED_CLASS_SET_MISMATCH")
    full_summaries = _summary_map(checkpoint["full_families"], context="full_families")
    sharded_summaries = _summary_map(
        checkpoint["sharded_families"], context="sharded_families"
    )
    for family in families:
        full_summary = full_summaries[family]
        sharded_summary = sharded_summaries[family]
        if (
            full_summary["class_set_sha256"] != sharded_summary["class_set_sha256"]
            or full_summary["canonical_count"] != sharded_summary["canonical_count"]
        ):
            raise RuntimeError(f"FULL_SHARDED_FAMILY_MISMATCH: {family}")

    if len(full_ids) > MAX_SCREEN_CLASSES:
        return _resource_limited_result(
            root=root,
            checkpoint_path=checkpoint_path,
            checkpoint=checkpoint,
            requested_family=requested_family,
            projection={
                "full_legal_canonical_count": len(full_ids),
                "max_screen_classes": MAX_SCREEN_CLASSES,
                "reason": "exact U3 screening cost exceeds the bounded execution budget",
            },
        )

    screen_result = _screen_mass12(
        root=root,
        checkpoint_path=checkpoint_path,
        checkpoint=checkpoint,
        families=families,
        numerator=numerator,
        denominator=denominator,
    )
    all_families = families == ("A", "B")
    exhaustive_status = (
        "PROVEN"
        if all_families and full_digest == shard_digest
        else "SELECTED_FAMILY_ONLY"
    )
    if not all_families:
        decision = "BOUNDED_SCREEN_ONLY"
    elif Fraction(str(screen_result["best_exact"])) > Fraction(numerator, denominator):
        decision = "STRICT_IMPROVEMENT_FOUND"
    else:
        decision = "NO_STRICT_IMPROVEMENT_IN_EXHAUSTED_K10_OVERLAP_MASS12_SHELL"
    result: dict[str, object] = {
        "schema_version": CHECKPOINT_SCHEMA,
        "task_id": TASK_ID,
        "base_head": BASE_HEAD,
        "base_tree": BASE_TREE,
        "sharding_strategy": SHARDING_STRATEGY,
        "mass11_certificate_status": "PASS",
        "requested_family": requested_family,
        "structural_profile_proof": structural_proof,
        "families": {
            family: {
                "full": full_summaries[family],
                "sharded": sharded_summaries[family],
            }
            for family in families
        },
        "total_legal_canonical_count": len(full_ids),
        "full_class_set_sha256": full_digest,
        "sharded_class_set_sha256": shard_digest,
        "shard_assignment": shard_summary,
        "independent_reproduction_status": "MATCH" if full_digest == shard_digest else "MISMATCH",
        "exhaustive_status": exhaustive_status,
        "screen": screen_result,
        "final_decision": decision,
        "global_k10_optimum_status": "UNKNOWN",
    }
    checkpoint["status"] = "COMPLETE" if all_families else "SELECTED_FAMILY_COMPLETE"
    checkpoint["full_class_set_sha256"] = full_digest
    checkpoint["sharded_class_set_sha256"] = shard_digest
    checkpoint["pruned_count"] = screen_result["pruned_class_count"]
    checkpoint["survivor_count"] = screen_result["survivor_class_count"]
    checkpoint["exact_scored_count"] = screen_result["exact_evaluation_count"]
    best_fraction = Fraction(str(screen_result["best_exact"]))
    checkpoint["current_best_outcome_count"] = (
        best_fraction.numerator
        * (total_official_outcomes() // best_fraction.denominator)
    )
    checkpoint["current_best_class_id"] = screen_result["best_class_id"]
    checkpoint["final_decision"] = decision
    _save_enumeration_checkpoint(checkpoint_path, checkpoint)
    _write_mass12_result(root, result)
    if all_families:
        _json_atomic(
            _repo_root()
            / "src/lottolab/research/b649_k10_overlap_mass12_bonferroni_screen_r1.json",
            result,
        )
    print(json.dumps(result, sort_keys=True), flush=True)
    return result


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    mass11 = subparsers.add_parser("mass11-certificate")
    mass11.add_argument("--authority-commit", required=True)
    mass11.add_argument("--classes-file", required=True)
    mass11.add_argument("--incumbent-numerator", required=True, type=int)
    mass11.add_argument("--incumbent-denominator", required=True, type=int)
    mass11.add_argument("--checkpoint-root", required=True)
    mass11.add_argument("--resume", action="store_true")
    mass12 = subparsers.add_parser("mass12-screen")
    mass12.add_argument("--incumbent-numerator", required=True, type=int)
    mass12.add_argument("--incumbent-denominator", required=True, type=int)
    mass12.add_argument("--family", choices=("all", "A", "B"), default="all")
    mass12.add_argument("--checkpoint-root", required=True)
    mass12.add_argument("--resume", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    root = _checkpoint_root(args.checkpoint_root)
    root.mkdir(parents=True, exist_ok=True)
    if args.command == "mass11-certificate":
        _mass11_certificate(
            authority_commit=args.authority_commit,
            classes_file=args.classes_file,
            numerator=args.incumbent_numerator,
            denominator=args.incumbent_denominator,
            checkpoint_root=root,
            resume=args.resume,
        )
        return 0
    _run_mass12(
        numerator=args.incumbent_numerator,
        denominator=args.incumbent_denominator,
        requested_family=args.family,
        root=root,
        resume=args.resume,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
