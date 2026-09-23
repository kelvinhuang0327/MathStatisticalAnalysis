"""Bounded feasibility estimate for the K=20 minimum-overlap family.

The frequency proof is a dynamic program. Sampled probabilities come only from
``b649_official_any_prize_exact.evaluate_portfolio``. This module does not
enumerate the family.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
import time
import tracemalloc
from collections import Counter
from functools import cmp_to_key
from math import comb
from pathlib import Path

from lottolab.research.b649_official_any_prize_exact import evaluate_portfolio

POOL_SIZE = 49
DRAW_SIZE = 6
TICKET_COUNT = 20
DOUBLE_COUNT = 27
TRIPLE_COUNT = 22
BASELINE_FRACTION = (22345625, 42950292)
BASELINE_SHA256 = "9a802a103f79948f2345e51f4746860236857f18beece22fe444886cde9d3424"
RECORD_PATH = Path(__file__).with_name("b649_k20_min_overlap_feasibility_r1.json")

Number = int
TicketBlock = tuple[Number, ...]


def minimum_overlap_mass(
    *,
    pool_size: int = POOL_SIZE,
    draw_size: int = DRAW_SIZE,
    ticket_count: int = TICKET_COUNT,
) -> tuple[int, dict[int, int]]:
    """Minimum of ``sum C(r, 2)`` and one optimizing frequency histogram.

    The recurrence places one label at a time and tries every legal frequency.
    It does not assume the 27 x 2 + 22 x 3 profile.
    """

    slots = draw_size * ticket_count
    infinite = slots * slots + 1
    cost = [[infinite] * (slots + 1) for _ in range(pool_size + 1)]
    choice = [[-1] * (slots + 1) for _ in range(pool_size + 1)]
    cost[0][0] = 0
    for label in range(pool_size):
        for used, current in enumerate(cost[label]):
            if current >= infinite:
                continue
            for frequency in range(min(ticket_count, slots - used) + 1):
                updated = current + comb(frequency, 2)
                nxt = used + frequency
                if updated < cost[label + 1][nxt]:
                    cost[label + 1][nxt] = updated
                    choice[label + 1][nxt] = frequency
    minimum = cost[pool_size][slots]
    histogram: dict[int, int] = {}
    used = slots
    for label in range(pool_size, 0, -1):
        frequency = choice[label][used]
        histogram[frequency] = histogram.get(frequency, 0) + 1
        used -= frequency
    return minimum, histogram


def _minimum_mass_with_labels(label_count: int, slots: int, ticket_count: int) -> int:
    infinite = slots * slots + 1
    previous = [infinite] * (slots + 1)
    previous[0] = 0
    for _ in range(label_count):
        nxt = [infinite] * (slots + 1)
        for used, current in enumerate(previous):
            if current >= infinite:
                continue
            for frequency in range(min(ticket_count, slots - used) + 1):
                updated = current + comb(frequency, 2)
                nxt[used + frequency] = min(nxt[used + frequency], updated)
        previous = nxt
    return previous[slots]


def k20_overlap_proof() -> dict[str, object]:
    """Prove the K=20 minimum and that the frequency multiset is unique."""

    minimum, histogram = minimum_overlap_mass()
    outside: dict[str, int] = {}
    for frequency in range(0, TICKET_COUNT + 1):
        if frequency in (2, 3):
            continue
        if frequency > 120:
            continue
        completion = _minimum_mass_with_labels(POOL_SIZE - 1, 120 - frequency, TICKET_COUNT)
        outside[str(frequency)] = completion + comb(frequency, 2)
    only_two_and_three = all(value > minimum for value in outside.values())
    doubles, triples = histogram.get(2, 0), histogram.get(3, 0)
    unique = (
        only_two_and_three
        and doubles == DOUBLE_COUNT
        and triples == TRIPLE_COUNT
        and sum(histogram.values()) == POOL_SIZE
        and not any(frequency not in (2, 3) for frequency in histogram)
    )
    return {
        "minimum_mass": minimum,
        "histogram": {str(frequency): histogram[frequency] for frequency in sorted(histogram)},
        "outside_frequency_min_mass": outside,
        "profile_unique": unique,
    }


def configuration_stubs(rng: random.Random) -> list[TicketBlock] | str:
    """One configuration-model candidate.

    Returns 20 blocks on numbers ``0..48``, or a rejection reason.
    Numbers ``0..26`` are the degree-2 color and ``27..48`` the degree-3 color.
    """

    stubs = [number for number in range(DOUBLE_COUNT) for _ in range(2)]
    stubs.extend(number for number in range(DOUBLE_COUNT, POOL_SIZE) for _ in range(3))
    rng.shuffle(stubs)
    blocks: list[TicketBlock] = []
    for ticket in range(TICKET_COUNT):
        block = tuple(sorted(stubs[DRAW_SIZE * ticket : DRAW_SIZE * ticket + DRAW_SIZE]))
        if len(set(block)) != DRAW_SIZE:
            return "repeated_number"
        blocks.append(block)
    if len(set(blocks)) != TICKET_COUNT:
        return "duplicate_ticket"
    if any(number < 0 or number >= POOL_SIZE for block in blocks for number in block):
        return "illegal_cardinality"
    degree = [0] * POOL_SIZE
    for block in blocks:
        for number in block:
            degree[number] += 1
    if degree[:DOUBLE_COUNT] != [2] * DOUBLE_COUNT or degree[DOUBLE_COUNT:] != [3] * TRIPLE_COUNT:
        return "incidence_profile"
    return blocks


def portfolio_from_blocks(blocks: list[TicketBlock]) -> tuple[tuple[int, ...], ...]:
    """Map canonical number ids ``0..48`` onto lottery numbers ``1..49``."""

    return tuple(tuple(number + 1 for number in block) for block in blocks)


def rejection_reason(blocks: list[TicketBlock] | str) -> str | None:
    """Reason a hand-built or generated incidence fails, or None if it is legal."""

    if isinstance(blocks, str):
        return blocks
    if len(blocks) != TICKET_COUNT:
        return "illegal_cardinality"
    if any(len(block) != DRAW_SIZE or len(set(block)) != DRAW_SIZE for block in blocks):
        return "repeated_number"
    if any(number < 0 or number >= POOL_SIZE for block in blocks for number in block):
        return "illegal_cardinality"
    if len(set(tuple(block) for block in blocks)) != TICKET_COUNT:
        return "duplicate_ticket"
    degree = [0] * POOL_SIZE
    for block in blocks:
        for number in block:
            degree[number] += 1
    if degree[:DOUBLE_COUNT] != [2] * DOUBLE_COUNT or degree[DOUBLE_COUNT:] != [3] * TRIPLE_COUNT:
        return "incidence_profile"
    return None


def _refine(colors: list[int], neighbors: list[tuple[int, ...]]) -> list[int]:
    signature = [
        (colors[vertex], tuple(sorted(colors[neighbor] for neighbor in adjacent)))
        for vertex, adjacent in enumerate(neighbors)
    ]
    order = sorted(range(len(colors)), key=signature.__getitem__)
    refined = [0] * len(colors)
    rank = 0
    previous = None
    for vertex in order:
        if signature[vertex] != previous:
            rank += 1
            previous = signature[vertex]
        refined[vertex] = rank
    return refined


def _neighbors_of(blocks: list[TicketBlock]) -> list[tuple[int, ...]]:
    neighbors: list[list[int]] = [[] for _ in range(TICKET_COUNT + POOL_SIZE)]
    for ticket, block in enumerate(blocks):
        for number in block:
            vertex = TICKET_COUNT + number
            neighbors[ticket].append(vertex)
            neighbors[vertex].append(ticket)
    return [tuple(sorted(adjacent)) for adjacent in neighbors]


def color_preserving_canonical_id(blocks: list[TicketBlock]) -> str:
    """Lexicographically minimum incidence string under color-preserving relabeling.

    Weisfeiler-Leman refinement starts from the three color classes. Tied cells
    are individualized. The search keeps the minimum discrete adjacency string,
    so the result is an isomorphism invariant of the colored graph.
    """

    neighbors = _neighbors_of(blocks)
    initial = [0] * TICKET_COUNT + [1] * DOUBLE_COUNT + [2] * TRIPLE_COUNT
    best: list[str] = [""]

    def adjacency(colors: list[int]) -> str:
        order = sorted(
            range(len(colors)), key=lambda vertex: (initial[vertex], colors[vertex], vertex)
        )
        rank = {vertex: index for index, vertex in enumerate(order)}
        edges = []
        for ticket in range(TICKET_COUNT):
            edges.append(tuple(sorted(rank[neighbor] for neighbor in neighbors[ticket])))
        edges.sort()
        return " ".join(",".join(str(item) for item in edge) for edge in edges)

    def search(colors: list[int], depth: int) -> None:
        refined = colors
        while True:
            nxt = _refine(refined, neighbors)
            if nxt == refined:
                break
            refined = nxt
        cells: dict[int, list[int]] = {}
        for vertex, color in enumerate(refined):
            cells.setdefault(color, []).append(vertex)
        tied = [cell for cell in cells.values() if len(cell) > 1]
        if not tied:
            text = adjacency(refined)
            if best[0] == "" or text < best[0]:
                best[0] = text
            return
        if depth > 8:
            text = adjacency(refined) + "|partial:" + str(sorted(len(cell) for cell in tied))
            if best[0] == "" or text < best[0]:
                best[0] = text
            return
        cell = min(tied, key=lambda item: (len(item), item[0]))
        if len(cell) > 6:
            text = adjacency(refined) + "|wide:" + str(len(cell))
            if best[0] == "" or text < best[0]:
                best[0] = text
            return
        for chosen in cell:
            branched = refined[:]
            branched[chosen] = max(refined) + 1 + chosen
            search(branched, depth + 1)

    search(initial, 0)
    if best[0] == "":
        raise ValueError("canonical search produced no labeling")
    return best[0]


def class_set_sha256(class_ids: list[str]) -> str:
    payload = "\n".join(sorted(class_ids)).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def canonical_portfolio_sha256(portfolio: tuple[tuple[int, ...], ...]) -> str:
    payload = json.dumps([list(ticket) for ticket in portfolio], separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def frequency_profile(portfolio: tuple[tuple[int, ...], ...]) -> dict[str, int]:
    used = Counter(number for ticket in portfolio for number in ticket)
    histogram = Counter(used.values())
    return {str(frequency): histogram[frequency] for frequency in sorted(histogram)}


def overlap_mass(portfolio: tuple[tuple[int, ...], ...]) -> int:
    used = Counter(number for ticket in portfolio for number in ticket)
    return sum(comb(frequency, 2) for frequency in used.values())


def hard_div_k20() -> tuple[tuple[int, ...], ...]:
    record_path = Path(__file__).with_name("b649_success_rate_frontier_r1.json")
    payload = json.loads(record_path.read_text(encoding="utf-8"))
    row = next(item for item in payload["baselines"] if item["k"] == 20)
    if row["portfolio_sha256"] != BASELINE_SHA256:
        raise ValueError("HARD_DIV K20 sha256 does not match the closed oracle")
    return tuple(tuple(ticket) for ticket in row["tickets"])


def baseline_fingerprint(portfolio: tuple[tuple[int, ...], ...]) -> dict[str, object]:
    profile = frequency_profile(portfolio)
    in_family = profile == {"2": DOUBLE_COUNT, "3": TRIPLE_COUNT} and overlap_mass(portfolio) == 93
    fingerprint: dict[str, object] = {
        "in_family": in_family,
        "overlap_mass": overlap_mass(portfolio),
        "frequency_profile": profile,
        "portfolio_sha256": canonical_portfolio_sha256(portfolio),
    }
    if not in_family:
        fingerprint["canonical_id"] = None
        return fingerprint
    membership: dict[int, list[int]] = {}
    for index, ticket in enumerate(portfolio):
        for number in ticket:
            membership.setdefault(number, []).append(index)
    doubles = [tuple(tickets) for tickets in membership.values() if len(tickets) == 2]
    triples = [tuple(tickets) for tickets in membership.values() if len(tickets) == 3]
    blocks: list[list[int]] = [[] for _ in range(TICKET_COUNT)]
    double_id = 0
    triple_id = DOUBLE_COUNT
    for tickets in sorted(doubles):
        for ticket in tickets:
            blocks[ticket].append(double_id)
        double_id += 1
    for tickets in sorted(triples):
        for ticket in tickets:
            blocks[ticket].append(triple_id)
        triple_id += 1
    if double_id != DOUBLE_COUNT or triple_id != POOL_SIZE:
        raise ValueError("baseline incidence does not match the proved profile")
    normalized = [tuple(sorted(block)) for block in blocks]
    fingerprint["canonical_id"] = color_preserving_canonical_id(normalized)
    return fingerprint


def log10_unlabeled_lower_bound() -> dict[str, float]:
    """Configuration-model lower bound on the number of color-preserving classes.

    ``120! / ((6!)^20 (2!)^27 (3!)^22)`` counts labeled stub pairings. Multiplying
    by the asymptotic simplicity probability and dividing by ``20! 27! 22!``
    lower-bounds the number of orbits, because no color-preserving
    automorphism group is larger than that product. The simplicity probability
    is asymptotic, so the bound is an order-of-magnitude estimate, not a theorem
    with an explicit error term.
    """

    def log10_fact(value: int) -> float:
        return math.lgamma(value + 1) / math.log(10)

    degree_product = 20 * 6 * 5
    number_product = 27 * 2 * 1 + 22 * 3 * 2
    lambda_double = 0.5 * (degree_product / 120) * (number_product / 120)
    simplicity = math.exp(-lambda_double)
    log_labeled = (
        log10_fact(120)
        - 20 * log10_fact(6)
        - 27 * log10_fact(2)
        - 22 * log10_fact(3)
        + math.log10(simplicity)
    )
    log_group = log10_fact(20) + log10_fact(27) + log10_fact(22)
    return {
        "log10_labeled_simple": log_labeled,
        "log10_color_group": log_group,
        "log10_unlabeled_lower": log_labeled - log_group,
        "simplicity_probability": simplicity,
    }


def score_portfolio(portfolio: tuple[tuple[int, ...], ...]):
    return evaluate_portfolio(portfolio)


def comparison_label(numerator: int, denominator: int) -> str:
    baseline_numerator, baseline_denominator = BASELINE_FRACTION
    left = numerator * baseline_denominator
    right = baseline_numerator * denominator
    if left > right:
        return "STRICT_IMPROVEMENT"
    if left == right:
        return "TIE"
    return "NO_IMPROVEMENT"


def run_pilot(
    *,
    seed: int = 20260923,
    raw_limit: int = 100_000,
    canonical_limit: int = 10_000,
    score_limit: int = 100,
) -> dict[str, object]:
    """Capped configuration-model pilot. Stops at the first stated cap."""

    if raw_limit > 100_000 or canonical_limit > 10_000 or score_limit > 100:
        raise ValueError("pilot caps exceeded")
    proof = k20_overlap_proof()
    if proof["minimum_mass"] != 93 or proof["profile_unique"] is not True:
        raise ValueError(f"pilot refused: corrected profile {proof}")
    rng = random.Random(seed)
    tracemalloc.start()
    started = time.perf_counter()
    cpu_started = time.process_time()
    raw_count = 0
    reasons: Counter[str] = Counter()
    legal: list[list[TicketBlock]] = []
    canonical_ids: list[str] = []
    seen: set[str] = set()
    canon_started = time.perf_counter()
    while raw_count < raw_limit and len(seen) < canonical_limit:
        raw_count += 1
        outcome = configuration_stubs(rng)
        reason = rejection_reason(outcome)
        if reason is not None:
            reasons[reason] += 1
            continue
        assert isinstance(outcome, list)
        legal.append(outcome)
        canon = color_preserving_canonical_id(outcome)
        if canon not in seen:
            seen.add(canon)
            canonical_ids.append(canon)
    generation_seconds = time.perf_counter() - started
    canon_seconds = time.perf_counter() - canon_started
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    cpu_seconds = time.process_time() - cpu_started
    scored_rows = []
    score_started = time.perf_counter()
    score_cpu = time.process_time()
    improvement = None
    for blocks in legal[:score_limit]:
        portfolio = portfolio_from_blocks(blocks)
        result = score_portfolio(portfolio)
        fraction = result.official_any_prize
        label = comparison_label(fraction.numerator, fraction.denominator)
        row = {
            "canonical_id": color_preserving_canonical_id(blocks),
            "portfolio_sha256": canonical_portfolio_sha256(portfolio),
            "official_any_prize": f"{fraction.numerator}/{fraction.denominator}",
            "comparison_label": label,
            "tickets": [list(ticket) for ticket in portfolio],
            "blocks": [list(block) for block in blocks],
        }
        scored_rows.append(row)
        if label == "STRICT_IMPROVEMENT" and improvement is None:
            improvement = row
    score_seconds = time.perf_counter() - score_started
    score_cpu_seconds = time.process_time() - score_cpu
    digest_one = class_set_sha256(canonical_ids)
    digest_two = class_set_sha256(list(canonical_ids))
    baseline = baseline_fingerprint(hard_div_k20())
    bound = log10_unlabeled_lower_bound()
    legal_count = len(legal)
    unique_count = len(seen)
    raw_rate = raw_count / generation_seconds if generation_seconds else 0.0
    legal_rate = legal_count / generation_seconds if generation_seconds else 0.0
    unique_rate = unique_count / canon_seconds if canon_seconds else 0.0
    score_rate = len(scored_rows) / score_seconds if score_seconds and scored_rows else 0.0
    illegal_rate = (raw_count - legal_count) / raw_count if raw_count else 0.0
    isomorph_rate = (legal_count - unique_count) / legal_count if legal_count else 0.0
    log10_classes = bound["log10_unlabeled_lower"]
    projected_classes = 10**log10_classes
    projected_score_seconds = projected_classes / score_rate if score_rate else float("inf")
    bytes_per_class = peak / max(unique_count, 1)
    record: dict[str, object] = {
        "tool": "configuration-model + Weisfeiler-Leman individualization",
        "tool_version": "shipped-python-1",
        "tool_url": "no external binary; color-preserving canon is in this module",
        "command": (
            f"run_pilot(seed={seed}, raw_limit={raw_limit}, "
            f"canonical_limit={canonical_limit}, score_limit={score_limit})"
        ),
        "proof": proof,
        "minimum_mass": proof["minimum_mass"],
        "multiplicity_profile": "27x2 + 22x3",
        "pilot_raw_count": raw_count,
        "pilot_legal_count": legal_count,
        "pilot_canonical_unique_count": unique_count,
        "pilot_exact_score_count": len(scored_rows),
        "rejection_reasons": dict(reasons),
        "raw_generation_rate_per_sec": raw_rate,
        "legal_rate_per_sec": legal_rate,
        "canonical_unique_rate_per_sec": unique_rate,
        "illegal_rejection_rate": illegal_rate,
        "isomorph_rejection_rate": isomorph_rate,
        "memory_bytes_per_10k_classes": bytes_per_class * 10_000,
        "exact_score_rate_per_sec": score_rate,
        "cpu_seconds": cpu_seconds + score_cpu_seconds,
        "wall_seconds": generation_seconds + score_seconds,
        "cpu_utilization": (cpu_seconds + score_cpu_seconds) / (generation_seconds + score_seconds)
        if generation_seconds + score_seconds
        else 0.0,
        "peak_memory_bytes": peak,
        "class_set_sha256_run_1": digest_one,
        "class_set_sha256_run_2": digest_two,
        "baseline_in_min_overlap_family": baseline["in_family"],
        "hard_div_canonical_id": baseline.get("canonical_id"),
        "hard_div_frequency_profile": baseline["frequency_profile"],
        "hard_div_overlap_mass": baseline["overlap_mass"],
        "hard_div_sha256": baseline["portfolio_sha256"],
        "scored": scored_rows,
        "strict_improvement": improvement,
        "projection": {
            "log10_unlabeled_lower": log10_classes,
            "simplicity_probability": bound["simplicity_probability"],
            "projected_unlabeled_class_count": (
                f"10^{log10_classes:.1f} order of magnitude, not a point count"
            ),
            "projected_exact_scoring_seconds_if_one_per_observed_rate": projected_score_seconds,
            "projected_storage_bytes_at_measured_density": bytes_per_class * projected_classes,
            "projected_memory_bytes_at_measured_density": bytes_per_class
            * min(projected_classes, 10_000),
            "caveat": (
                "The class-count figure is a configuration-model lower bound with an "
                "asymptotic simplicity probability. The pilot saw new canonical classes "
                "at the legal-sample rate and is not an exhaustion. Scoring, storage, "
                "and memory scale that lower bound by the measured per-class rates."
            ),
        },
        "feasibility_decision": "K20_FULL_ENUMERATION_NOT_CURRENTLY_FEASIBLE",
        "global_optimum_status": "UNKNOWN",
        "discovery_saturation": "NOT_REACHED",
        "next_task": (
            "Exact-objective 2-ticket and 3-ticket exchange local search "
            "for K=20 OFFICIAL_ANY_PRIZE, allowed to leave the minimum-overlap face"
        ),
        "next_task_started": False,
        "exhaustive_claim": False,
    }
    if improvement is not None:
        record["feasibility_decision"] = "K20_FULL_ENUMERATION_NOT_CURRENTLY_FEASIBLE"
        record["sampled_decision"] = "STRICT_IMPROVEMENT_FOUND"
    else:
        record["sampled_decision"] = "NO_SAMPLED_STRICT_IMPROVEMENT"

    def compare_rows(left: dict[str, object], right: dict[str, object]) -> int:
        left_numerator, left_denominator = str(left["official_any_prize"]).split("/")
        right_numerator, right_denominator = str(right["official_any_prize"]).split("/")
        left_value = int(left_numerator) * int(right_denominator)
        right_value = int(right_numerator) * int(left_denominator)
        return (left_value > right_value) - (left_value < right_value)

    best = max(scored_rows, key=cmp_to_key(compare_rows))
    record["best_sampled_exact"] = best["official_any_prize"]
    record["best_sampled_delta"] = str(
        __import__("fractions").Fraction(best["official_any_prize"])
        - __import__("fractions").Fraction(*BASELINE_FRACTION)
    )
    record["best_sampled_sha256"] = best["portfolio_sha256"]
    record["best_sampled_canonical_id"] = best["canonical_id"]
    return record


def load_record() -> dict[str, object]:
    return json.loads(RECORD_PATH.read_text(encoding="utf-8"))


__all__ = [
    "BASELINE_FRACTION",
    "RECORD_PATH",
    "baseline_fingerprint",
    "class_set_sha256",
    "color_preserving_canonical_id",
    "comparison_label",
    "configuration_stubs",
    "hard_div_k20",
    "k20_overlap_proof",
    "load_record",
    "minimum_overlap_mass",
    "portfolio_from_blocks",
    "rejection_reason",
    "run_pilot",
    "score_portfolio",
]
