"""Exhaust the fixed 12+8 overlap-block family for the B649 K=20 portfolio."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import os
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache
from math import comb
from pathlib import Path
from typing import cast

import numpy as np
import numpy.typing as npt

from lottolab.research.b649_official_any_prize_exact import (
    DrawMasks,
    all_main_draw_masks,
    evaluate_portfolio,
)

POINT_COUNT = 13
TICKET_SIZE = 6
PORTFOLIO_SIZE = 20
BASELINE_COUNT = 313_239_661
KNOWN_CYCLIC_COUNT = 313_263_867
EXPECTED_CANDIDATES = 26
FIXED_EIGHT_TICKETS: tuple[tuple[int, ...], ...] = (
    (27, 29, 30, 31, 32, 33),
    (27, 34, 35, 36, 37, 38),
    (27, 39, 40, 41, 42, 43),
    (28, 29, 34, 39, 44, 45),
    (28, 30, 35, 40, 46, 47),
    (28, 31, 36, 41, 48, 49),
    (32, 37, 42, 44, 46, 48),
    (33, 38, 43, 45, 47, 49),
)
RECORD_PATH = (
    Path(__file__).resolve().parents[3]
    / "docs/research/matrix-native-results/"
    "b649-k20-overlap-block-repartition-12-8-exhaustive-r1-result.json"
)

type Pair = tuple[int, int]
type Block = tuple[int, int, int]
type Design = tuple[Block, ...]
type Ticket = tuple[int, ...]
type Portfolio = tuple[Ticket, ...]
type PaschConfiguration = tuple[Block, Block, Block, Block]
type PaschTrade = tuple[PaschConfiguration, PaschConfiguration]


@dataclass(frozen=True, slots=True)
class STS13Classes:
    cyclic: Design
    noncyclic: Design
    cyclic_pasch_count: int
    noncyclic_pasch_count: int
    valid_pasch_trade_count: int
    pasch_count_8_trade_result_count: int
    pasch_count_8_isomorphism_class_count: int


@dataclass(frozen=True, slots=True)
class PortfolioCandidate:
    sts_class: str
    deleted_point: int
    tickets: Portfolio
    sha256: str


@dataclass(frozen=True, slots=True)
class ScoredCandidate:
    candidate: PortfolioCandidate
    official_any_prize_outcome_count: int


def _normalize_block(points: Sequence[int]) -> Block:
    if len(points) != 3:
        raise ValueError("an STS block must contain exactly three points")
    return cast(Block, tuple(sorted(points)))


def is_valid_sts13(blocks: Sequence[Block]) -> bool:
    """Return whether the blocks form a Steiner triple system on 0..12."""

    if len(blocks) != 26 or len(set(blocks)) != 26:
        return False
    if any(
        len(block) != 3
        or tuple(sorted(block)) != block
        or len(set(block)) != 3
        or any(point < 0 or point >= POINT_COUNT for point in block)
        for block in blocks
    ):
        return False
    pair_counts = Counter(pair for block in blocks for pair in itertools.combinations(block, 2))
    return len(pair_counts) == comb(POINT_COUNT, 2) and all(
        count == 1 for count in pair_counts.values()
    )


def _pasch_configurations(blocks: Design) -> tuple[PaschConfiguration, ...]:
    configurations: list[PaschConfiguration] = []
    for selected in itertools.combinations(blocks, 4):
        point_counts = Counter(point for block in selected for point in block)
        if len(point_counts) == 6 and all(count == 2 for count in point_counts.values()):
            configurations.append(selected)
    return tuple(configurations)


def pasch_count(blocks: Sequence[Block]) -> int:
    """Count four-block Pasch configurations in an STS(13)."""

    normalized = tuple(sorted(_normalize_block(block) for block in blocks))
    if not is_valid_sts13(normalized):
        raise ValueError("Pasch count requires a valid STS(13)")
    return len(_pasch_configurations(normalized))


@lru_cache(maxsize=1)
def _cyclic_sts13() -> Design:
    base_blocks: tuple[Block, Block] = ((0, 1, 4), (0, 2, 7))
    blocks = tuple(
        sorted(
            {
                _normalize_block(tuple((point + shift) % POINT_COUNT for point in base))
                for base in base_blocks
                for shift in range(POINT_COUNT)
            }
        )
    )
    if not is_valid_sts13(blocks) or pasch_count(blocks) != 13:
        raise ValueError("cyclic STS(13) identity mismatch")
    return blocks


def _negative_pasches(removed: PaschConfiguration) -> tuple[PaschConfiguration, ...]:
    support = tuple(sorted({point for block in removed for point in block}))
    positive_pairs = {
        pair for block in removed for pair in itertools.combinations(block, 2)
    }
    eligible_blocks = tuple(
        triple
        for triple in itertools.combinations(support, 3)
        if all(pair in positive_pairs for pair in itertools.combinations(triple, 2))
    )
    replacements: set[PaschConfiguration] = set()
    for selected in itertools.combinations(eligible_blocks, 4):
        replacement_pairs = {
            pair for block in selected for pair in itertools.combinations(block, 2)
        }
        if replacement_pairs == positive_pairs and set(selected).isdisjoint(removed):
            replacements.add(selected)
    return tuple(sorted(replacements))


def _valid_pasch_trades(blocks: Design) -> tuple[PaschTrade, ...]:
    trades = {
        (removed, replacement)
        for removed in _pasch_configurations(blocks)
        for replacement in _negative_pasches(removed)
    }
    return tuple(sorted(trades))


def _completion_table(blocks: Design) -> list[list[int | None]]:
    completion: list[list[int | None]] = [
        [None for _ in range(POINT_COUNT)] for _ in range(POINT_COUNT)
    ]
    for block in blocks:
        for left, right in itertools.combinations(block, 2):
            third = next(point for point in block if point != left and point != right)
            completion[left][right] = third
            completion[right][left] = third
    return completion


def _pasch_point_signature(blocks: Design) -> tuple[int, ...]:
    counts = [0] * POINT_COUNT
    for configuration in _pasch_configurations(blocks):
        for point in {point for block in configuration for point in block}:
            counts[point] += 1
    return tuple(counts)


def sts13_are_isomorphic(left: Design, right: Design) -> bool:
    """Exact point-map check using each pair's unique third-point completion."""

    if not is_valid_sts13(left) or not is_valid_sts13(right):
        return False
    if pasch_count(left) != pasch_count(right):
        return False

    left_completion = _completion_table(left)
    right_completion = _completion_table(right)
    left_signature = _pasch_point_signature(left)
    right_signature = _pasch_point_signature(right)

    def search(mapping: list[int], inverse: list[int]) -> bool:
        changed = True
        while changed:
            changed = False
            for left_point in range(POINT_COUNT):
                for other_point in range(left_point + 1, POINT_COUNT):
                    mapped_left = mapping[left_point]
                    mapped_other = mapping[other_point]
                    if mapped_left < 0 or mapped_other < 0:
                        continue
                    left_third = left_completion[left_point][other_point]
                    right_third = right_completion[mapped_left][mapped_other]
                    if left_third is None or right_third is None:
                        return False
                    mapped_third = mapping[left_third]
                    if mapped_third < 0:
                        if inverse[right_third] >= 0:
                            return False
                        mapping[left_third] = right_third
                        inverse[right_third] = left_third
                        changed = True
                    elif mapped_third != right_third:
                        return False

        unmapped = [point for point, image in enumerate(mapping) if image < 0]
        if not unmapped:
            return True
        left_point = unmapped[0]
        for right_point in range(POINT_COUNT):
            if (
                inverse[right_point] >= 0
                or left_signature[left_point] != right_signature[right_point]
            ):
                continue
            next_mapping = mapping.copy()
            next_inverse = inverse.copy()
            next_mapping[left_point] = right_point
            next_inverse[right_point] = left_point
            if search(next_mapping, next_inverse):
                return True
        return False

    for image in range(POINT_COUNT):
        if left_signature[0] != right_signature[image]:
            continue
        mapping = [-1] * POINT_COUNT
        inverse = [-1] * POINT_COUNT
        mapping[0] = image
        inverse[image] = 0
        if search(mapping, inverse):
            return True
    return False


@lru_cache(maxsize=1)
def build_sts13_classes() -> STS13Classes:
    """Build both classes and fail unless count-8 trade results are unique up to isomorphism."""

    cyclic = _cyclic_sts13()
    trades = _valid_pasch_trades(cyclic)
    count_8_results: list[Design] = []
    for removed, replacement in trades:
        blocks = tuple(sorted((set(cyclic) - set(removed)) | set(replacement)))
        if is_valid_sts13(blocks) and pasch_count(blocks) == 8:
            count_8_results.append(blocks)
    if not count_8_results:
        raise ValueError("no lexicographic Pasch trade produced a valid Pasch-count-8 STS(13)")

    selected = count_8_results[0]
    if sts13_are_isomorphic(cyclic, selected):
        raise ValueError("Pasch trade did not produce a second STS(13) isomorphism class")
    if any(not sts13_are_isomorphic(selected, design) for design in count_8_results[1:]):
        raise ValueError("Pasch-count-8 trade results contain multiple isomorphism classes")
    return STS13Classes(
        cyclic=cyclic,
        noncyclic=selected,
        cyclic_pasch_count=pasch_count(cyclic),
        noncyclic_pasch_count=pasch_count(selected),
        valid_pasch_trade_count=len(trades),
        pasch_count_8_trade_result_count=len(count_8_results),
        pasch_count_8_isomorphism_class_count=1,
    )


def portfolio_sha256(portfolio: Portfolio) -> str:
    """Hash compact JSON of ordered tickets, matching the repository convention."""

    payload = json.dumps([list(ticket) for ticket in portfolio], separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _portfolio_for_deleted_point(blocks: Design, deleted_point: int) -> Portfolio:
    remaining_points = tuple(point for point in range(POINT_COUNT) if point != deleted_point)
    point_index = {point: index for index, point in enumerate(remaining_points)}
    avoiding_triples = tuple(sorted(block for block in blocks if deleted_point not in block))
    through_point_pairs = tuple(
        sorted(
            cast(Pair, tuple(point for point in block if point != deleted_point))
            for block in blocks
            if deleted_point in block
        )
    )
    if len(avoiding_triples) != 20 or len(through_point_pairs) != 6:
        raise ValueError("deleted-point STS(13) block counts are not 20 and 6")

    tickets: list[list[int]] = [[] for _ in remaining_points]
    for label, triple in enumerate(avoiding_triples, start=1):
        for point in triple:
            tickets[point_index[point]].append(label)
    for label, pair in enumerate(through_point_pairs, start=21):
        for point in pair:
            tickets[point_index[point]].append(label)
    twelve_tickets = tuple(tuple(sorted(ticket)) for ticket in tickets)
    return twelve_tickets + FIXED_EIGHT_TICKETS


def build_family_candidates() -> tuple[PortfolioCandidate, ...]:
    classes = build_sts13_classes()
    candidates = tuple(
        PortfolioCandidate(
            sts_class=class_name,
            deleted_point=deleted_point,
            tickets=_portfolio_for_deleted_point(design, deleted_point),
            sha256=portfolio_sha256(_portfolio_for_deleted_point(design, deleted_point)),
        )
        for class_name, design in (
            ("CYCLIC", classes.cyclic),
            ("NONCYCLIC", classes.noncyclic),
        )
        for deleted_point in range(POINT_COUNT)
    )
    if len(candidates) != EXPECTED_CANDIDATES:
        raise ValueError("family must contain exactly 26 candidate portfolios")
    return candidates


def structural_invariants(portfolio: Portfolio) -> dict[str, object]:
    legal_distinct = (
        len(portfolio) == PORTFOLIO_SIZE
        and len(set(portfolio)) == PORTFOLIO_SIZE
        and all(
            len(ticket) == TICKET_SIZE
            and len(set(ticket)) == TICKET_SIZE
            and all(type(number) is int and 1 <= number <= 49 for number in ticket)
            for ticket in portfolio
        )
    )
    frequency = Counter(number for ticket in portfolio for number in ticket)
    frequency_profile = {
        str(target): sum(frequency[number] == target for number in range(1, 50))
        for target in (2, 3)
    }
    all_number_frequencies_are_2_or_3 = all(
        frequency[number] in (2, 3) for number in range(1, 50)
    ) and all(1 <= number <= 49 for number in frequency)

    overlap_counts = Counter(
        len(set(left).intersection(right))
        for left, right in itertools.combinations(portfolio, 2)
    )
    overlap_histogram = {
        str(overlap): overlap_counts[overlap] for overlap in (0, 1) if overlap_counts[overlap]
    }
    return {
        "TICKET_COUNT": len(portfolio),
        "LEGAL_DISTINCT_TICKETS": legal_distinct,
        "FREQUENCY_PROFILE": frequency_profile,
        "ALL_NUMBER_FREQUENCIES_ARE_2_OR_3": all_number_frequencies_are_2_or_3,
        "PAIRWISE_OVERLAP_HISTOGRAM": overlap_histogram,
        "MAXIMUM_PAIRWISE_OVERLAP": max(overlap_counts, default=0),
    }


def _validate_family_structure(
    candidates: Sequence[PortfolioCandidate],
) -> dict[str, object]:
    if len(candidates) != EXPECTED_CANDIDATES:
        raise ValueError("FAMILY_IDENTITY_MISMATCH: candidate count is not 26")
    expected = {
        "TICKET_COUNT": 20,
        "LEGAL_DISTINCT_TICKETS": True,
        "FREQUENCY_PROFILE": {"2": 27, "3": 22},
        "ALL_NUMBER_FREQUENCIES_ARE_2_OR_3": True,
        "PAIRWISE_OVERLAP_HISTOGRAM": {"0": 97, "1": 93},
        "MAXIMUM_PAIRWISE_OVERLAP": 1,
    }
    summaries = [structural_invariants(candidate.tickets) for candidate in candidates]
    if any(summary != expected for summary in summaries):
        raise ValueError(f"FAMILY_IDENTITY_MISMATCH: structural invariant failure: {summaries}")
    return {
        "CANDIDATE_PORTFOLIOS_CHECKED": len(summaries),
        "ALL_CANDIDATES_PASS": True,
        "TICKET_COUNT": 20,
        "LEGAL_DISTINCT_TICKETS": True,
        "FREQUENCY_PROFILE": {"NUMBERS_APPEARING_3_TIMES": 22, "NUMBERS_APPEARING_2_TIMES": 27},
        "PAIRWISE_OVERLAP_HISTOGRAM": {"OVERLAP_1": 93, "OVERLAP_0": 97},
        "MAXIMUM_PAIRWISE_OVERLAP": 1,
    }


def select_winner(scored: Sequence[ScoredCandidate]) -> ScoredCandidate:
    if not scored:
        raise ValueError("cannot select a winner from no scores")
    return min(
        scored,
        key=lambda row: (
            -row.official_any_prize_outcome_count,
            row.candidate.sha256,
            row.candidate.sts_class,
            row.candidate.deleted_point,
        ),
    )


def score_family_candidates(
    candidates: Sequence[PortfolioCandidate],
) -> tuple[ScoredCandidate, ...]:
    """Score every structurally valid candidate exactly once through the official evaluator."""

    structural = _validate_family_structure(candidates)
    if structural["CANDIDATE_PORTFOLIOS_CHECKED"] != EXPECTED_CANDIDATES:
        raise ValueError("candidate structural gate did not check all 26 portfolios")
    draws: DrawMasks = all_main_draw_masks(49, 6)
    scored = tuple(
        ScoredCandidate(
            candidate=candidate,
            official_any_prize_outcome_count=evaluate_portfolio(
                candidate.tickets,
                draws=draws,
            ).official_any_prize_outcome_count,
        )
        for candidate in candidates
    )
    if len(scored) != EXPECTED_CANDIDATES:
        raise ValueError("canonical evaluator did not score exactly 26 candidates")
    return scored


def _candidate_score_row(scored: ScoredCandidate) -> dict[str, object]:
    return {
        "STS_CLASS": scored.candidate.sts_class,
        "DELETED_POINT": scored.candidate.deleted_point,
        "PORTFOLIO_SHA256": scored.candidate.sha256,
        "OFFICIAL_ANY_PRIZE_OUTCOME_COUNT": scored.official_any_prize_outcome_count,
    }


def _class_report(classes: STS13Classes) -> dict[str, object]:
    return {
        "CYCLIC_PASCH_COUNT": classes.cyclic_pasch_count,
        "NONCYCLIC_PASCH_COUNT": classes.noncyclic_pasch_count,
        "VALID_PASCH_TRADE_COUNT": classes.valid_pasch_trade_count,
        "PASCH_COUNT_8_TRADE_RESULT_COUNT": classes.pasch_count_8_trade_result_count,
        "PASCH_COUNT_8_ISOMORPHISM_CLASS_COUNT": classes.pasch_count_8_isomorphism_class_count,
        "CLASSES_NONISOMORPHIC": not sts13_are_isomorphic(classes.cyclic, classes.noncyclic),
    }


def build_stage_one_record(scored: Sequence[ScoredCandidate]) -> dict[str, object]:
    if len(scored) != EXPECTED_CANDIDATES:
        raise ValueError("stage one requires exactly 26 canonical candidate scores")
    classes = build_sts13_classes()
    candidates = tuple(row.candidate for row in scored)
    structural = _validate_family_structure(candidates)
    cyclic_witnesses = [
        row
        for row in scored
        if row.candidate.sts_class == "CYCLIC"
        and row.official_any_prize_outcome_count == KNOWN_CYCLIC_COUNT
    ]
    best = select_winner(scored)
    known_parity = {
        "EXPECTED_COUNT": KNOWN_CYCLIC_COUNT,
        "MATCHING_CYCLIC_CANDIDATES": [
            {
                "DELETED_POINT": row.candidate.deleted_point,
                "PORTFOLIO_SHA256": row.candidate.sha256,
            }
            for row in cyclic_witnesses
        ],
        "STATUS": "PASS" if cyclic_witnesses else "FAIL",
    }
    task_status = (
        "FAMILY_SCORED_READY_TO_SEAL"
        if cyclic_witnesses
        else "STOPPED_KNOWN_WITNESS_COUNT_PARITY_MISMATCH"
    )
    family_result = (
        "PENDING_SEAL" if cyclic_witnesses else "STOPPED_KNOWN_WITNESS_COUNT_PARITY_MISMATCH"
    )
    return {
        "SCHEMA_VERSION": "B649_K20_OVERLAP_BLOCK_REPARTITION_12_8_EXHAUSTIVE_R1_V1",
        "TASK_ID": "B649_K20_OVERLAP_BLOCK_REPARTITION_12_8_EXHAUSTIVE_R1",
        "TASK_STATUS": task_status,
        "CANDIDATES_TOTAL": EXPECTED_CANDIDATES,
        "CANONICAL_CANDIDATE_EVALUATIONS": len(scored),
        "FAMILY_EVALUATION_PROCESS_ID": os.getpid(),
        "CYCLIC_PASCH_COUNT": classes.cyclic_pasch_count,
        "NONCYCLIC_PASCH_COUNT": classes.noncyclic_pasch_count,
        "STS_CLASSES": _class_report(classes),
        "STRUCTURAL_INVARIANTS": structural,
        "KNOWN_WITNESS_COUNT_PARITY": known_parity,
        "CANDIDATE_COUNTS": [_candidate_score_row(row) for row in scored],
        "BEST_COUNT": best.official_any_prize_outcome_count,
        "BEST_DELTA_VS_313239661": best.official_any_prize_outcome_count - BASELINE_COUNT,
        "BEST_PORTFOLIO_SHA256": best.candidate.sha256,
        "BEST_STS_CLASS": best.candidate.sts_class,
        "BEST_DELETED_POINT": best.candidate.deleted_point,
        "BEST_PORTFOLIO": [list(ticket) for ticket in best.candidate.tickets],
        "FRESH_CANONICAL_RECOUNT": "NOT RUN",
        "INDEPENDENT_7SET_RECOUNT": "NOT RUN",
        "FAMILY_RESULT": family_result,
        "READY_FOR_LOCAL_ASCENT": "PENDING_SEAL" if cyclic_witnesses else "NO",
        "CANONICAL_EVALUATION_BUDGET": {
            "FAMILY_CANDIDATES": len(scored),
            "FRESH_WINNER_RECOUNT": 0,
            "TOTAL_USED": len(scored),
        },
        "PUSH": "NOT RUN",
        "PR": "NOT CREATED",
        "PRODUCTION_MUTATION": "NONE",
        "GLOBAL_K20_OPTIMUM_STATUS": "UNKNOWN",
    }


def _ticket_mask(ticket: Sequence[int]) -> int:
    mask = 0
    for number in ticket:
        mask |= 1 << (number - 1)
    return mask


def _winning_subset_count(
    subset_masks: npt.NDArray[np.uint64],
    ticket_masks: Sequence[int],
    minimum_matches: int,
) -> int:
    won = np.zeros(subset_masks.size, dtype=np.bool_)
    for mask in ticket_masks:
        won |= np.bitwise_count(subset_masks & np.uint64(mask)) >= minimum_matches
        if bool(np.all(won)):
            break
    return int(np.count_nonzero(won))


def count_winning_subsets(
    portfolio: Sequence[Sequence[int]],
    *,
    pool_size: int,
    subset_size: int,
    minimum_matches: int,
    chunk_size: int = 1 << 18,
) -> int:
    """Count subsets containing at least minimum_matches from any ticket."""

    if not portfolio or not 1 <= subset_size <= pool_size <= 64 or chunk_size < 1:
        raise ValueError("invalid subset-count parameters")
    if not 1 <= minimum_matches <= subset_size:
        raise ValueError("minimum_matches must be in 1..subset_size")
    if any(
        not ticket
        or len(set(ticket)) != len(ticket)
        or any(type(number) is not int or not 1 <= number <= pool_size for number in ticket)
        for ticket in portfolio
    ):
        raise ValueError("tickets must contain distinct numbers in the subset pool")

    masks = tuple(_ticket_mask(ticket) for ticket in portfolio)
    subset_buffer = np.empty(chunk_size, dtype=np.uint64)
    subset_count = 0
    filled = 0
    for subset in itertools.combinations(range(1, pool_size + 1), subset_size):
        subset_mask = 0
        for number in subset:
            subset_mask |= 1 << (number - 1)
        subset_buffer[filled] = np.uint64(subset_mask)
        filled += 1
        if filled == chunk_size:
            subset_count += _winning_subset_count(subset_buffer[:filled], masks, minimum_matches)
            filled = 0
    if filled:
        subset_count += _winning_subset_count(subset_buffer[:filled], masks, minimum_matches)
    if subset_count > comb(pool_size, subset_size):
        raise AssertionError("winning subset count exceeds the complete subset space")
    return subset_count


def independent_7set_recount(portfolio: Portfolio, *, chunk_size: int = 1 << 18) -> int:
    """Independently count the 7-number sets that trigger any prize, then multiply by seven.

    Each 7-set is the union of one official six-number main draw and its special
    number. It has seven possible special assignments. A ticket wins for an
    assignment exactly when it intersects the 7-set in at least three numbers.
    """

    winning_seven_sets = count_winning_subsets(
        portfolio,
        pool_size=49,
        subset_size=7,
        minimum_matches=3,
        chunk_size=chunk_size,
    )
    return winning_seven_sets * 7


def _load_stage_one_record(output_path: Path) -> dict[str, object]:
    raw = json.loads(output_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("result artifact must contain a JSON object")
    return cast(dict[str, object], raw)


def _integer_field(record: dict[str, object], field: str) -> int:
    value = record.get(field)
    if type(value) is not int:
        raise ValueError(f"result artifact field {field} must be an integer")
    return value


def _validated_winner(record: dict[str, object]) -> PortfolioCandidate:
    if record.get("TASK_ID") != "B649_K20_OVERLAP_BLOCK_REPARTITION_12_8_EXHAUSTIVE_R1":
        raise ValueError("result artifact task identity mismatch")
    if record.get("CANDIDATES_TOTAL") != EXPECTED_CANDIDATES:
        raise ValueError("result artifact candidate total mismatch")
    if record.get("CANONICAL_CANDIDATE_EVALUATIONS") != EXPECTED_CANDIDATES:
        raise ValueError("result artifact canonical candidate evaluation count mismatch")
    if record.get("TASK_STATUS") != "FAMILY_SCORED_READY_TO_SEAL":
        raise ValueError("family parity gate did not pass")

    candidates = build_family_candidates()
    candidates_by_identity = {
        (candidate.sts_class, candidate.deleted_point): candidate for candidate in candidates
    }
    rows_value = record.get("CANDIDATE_COUNTS")
    if not isinstance(rows_value, list):
        raise ValueError("result artifact must contain 26 candidate score rows")
    candidate_rows = cast(list[object], rows_value)
    if len(candidate_rows) != EXPECTED_CANDIDATES:
        raise ValueError("result artifact must contain 26 candidate score rows")
    row_by_identity: dict[tuple[str, int], dict[str, object]] = {}
    for raw_row in candidate_rows:
        if not isinstance(raw_row, dict):
            raise ValueError("candidate score row must be a JSON object")
        row = cast(dict[str, object], raw_row)
        class_value = row.get("STS_CLASS")
        point_value = row.get("DELETED_POINT")
        sha_value = row.get("PORTFOLIO_SHA256")
        count_value = row.get("OFFICIAL_ANY_PRIZE_OUTCOME_COUNT")
        if (
            not isinstance(class_value, str)
            or type(point_value) is not int
            or not isinstance(sha_value, str)
            or type(count_value) is not int
        ):
            raise ValueError("candidate score row has invalid identity or count fields")
        identity = (class_value, point_value)
        candidate = candidates_by_identity.get(identity)
        if candidate is None or candidate.sha256 != sha_value or identity in row_by_identity:
            raise ValueError("candidate score row identity or frozen SHA mismatch")
        row_by_identity[identity] = row
    if set(row_by_identity) != set(candidates_by_identity):
        raise ValueError("candidate score rows do not cover the complete 26-member family")

    known_parity_value = record.get("KNOWN_WITNESS_COUNT_PARITY")
    if not isinstance(known_parity_value, dict):
        raise ValueError("known cyclic witness count parity is not sealed")
    known_parity = cast(dict[str, object], known_parity_value)
    if known_parity.get("STATUS") != "PASS":
        raise ValueError("known cyclic witness count parity is not sealed")
    if not any(
        candidate_class == "CYCLIC"
        and row.get("OFFICIAL_ANY_PRIZE_OUTCOME_COUNT") == KNOWN_CYCLIC_COUNT
        for (candidate_class, _), row in row_by_identity.items()
    ):
        raise ValueError("known cyclic witness count is absent from the candidate rows")

    winner_row = min(
        row_by_identity.values(),
        key=lambda row: (
            -cast(int, row["OFFICIAL_ANY_PRIZE_OUTCOME_COUNT"]),
            cast(str, row["PORTFOLIO_SHA256"]),
            cast(str, row["STS_CLASS"]),
            cast(int, row["DELETED_POINT"]),
        ),
    )
    winner_class = cast(str, winner_row["STS_CLASS"])
    winner_point = cast(int, winner_row["DELETED_POINT"])
    candidate = candidates_by_identity[(winner_class, winner_point)]
    if (
        record.get("BEST_COUNT") != winner_row["OFFICIAL_ANY_PRIZE_OUTCOME_COUNT"]
        or record.get("BEST_PORTFOLIO_SHA256") != candidate.sha256
        or record.get("BEST_STS_CLASS") != candidate.sts_class
        or record.get("BEST_DELETED_POINT") != candidate.deleted_point
        or record.get("BEST_DELTA_VS_313239661")
        != cast(int, winner_row["OFFICIAL_ANY_PRIZE_OUTCOME_COUNT"]) - BASELINE_COUNT
        or record.get("BEST_PORTFOLIO") != [list(ticket) for ticket in candidate.tickets]
    ):
        raise ValueError("result artifact winner fields are inconsistent with the candidate scores")
    return candidate


def seal_result(output_path: Path = RECORD_PATH) -> dict[str, object]:
    """Fresh-process canonical recount and independent seven-set recount of the family winner."""

    record = _load_stage_one_record(output_path)
    winner = _validated_winner(record)
    recount_process_id = os.getpid()
    family_process_id = _integer_field(record, "FAMILY_EVALUATION_PROCESS_ID")
    if recount_process_id == family_process_id:
        raise ValueError("winner recount must run in a fresh process")

    draws: DrawMasks = all_main_draw_masks(49, 6)
    fresh_count = evaluate_portfolio(winner.tickets, draws=draws).official_any_prize_outcome_count
    independent_count = independent_7set_recount(winner.tickets)
    parity_pass = fresh_count == independent_count == _integer_field(record, "BEST_COUNT")
    improvement = fresh_count > BASELINE_COUNT
    record.update(
        {
            "FRESH_CANONICAL_RECOUNT": fresh_count,
            "FRESH_CANONICAL_RECOUNT_PROCESS_ID": recount_process_id,
            "INDEPENDENT_7SET_RECOUNT": independent_count,
            "SEAL_PARITY": "PASS" if parity_pass else "FAIL",
            "FAMILY_RESULT": (
                "IMPROVEMENT_CONFIRMED" if improvement else "NO_IMPROVEMENT"
            )
            if parity_pass
            else "STOPPED_RECOUNT_PARITY_MISMATCH",
            "READY_FOR_LOCAL_ASCENT": "YES" if parity_pass and improvement else "NO",
            "TASK_STATUS": "COMPLETE" if parity_pass else "STOPPED_RECOUNT_PARITY_MISMATCH",
            "CANONICAL_EVALUATION_BUDGET": {
                "FAMILY_CANDIDATES": EXPECTED_CANDIDATES,
                "FRESH_WINNER_RECOUNT": 1,
                "TOTAL_USED": EXPECTED_CANDIDATES + 1,
            },
        }
    )
    _write_record(output_path, record)
    return record


def _write_record(output_path: Path, record: dict[str, object]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def run_family(output_path: Path = RECORD_PATH) -> dict[str, object]:
    candidates = build_family_candidates()
    scored = score_family_candidates(candidates)
    record = build_stage_one_record(scored)
    _write_record(output_path, record)
    return record


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("family", "seal"), default="family")
    parser.add_argument("--output", type=Path, default=RECORD_PATH)
    args = parser.parse_args(argv)

    if args.phase == "family":
        record = run_family(args.output)
        print(
            json.dumps(
                {
                    "TASK_STATUS": record["TASK_STATUS"],
                    "CANDIDATES_TOTAL": record["CANDIDATES_TOTAL"],
                    "CANONICAL_CANDIDATE_EVALUATIONS": record[
                        "CANONICAL_CANDIDATE_EVALUATIONS"
                    ],
                    "BEST_COUNT": record["BEST_COUNT"],
                    "KNOWN_WITNESS_COUNT_PARITY": record[
                        "KNOWN_WITNESS_COUNT_PARITY"
                    ],
                },
                sort_keys=True,
            )
        )
        return 0 if record["TASK_STATUS"] == "FAMILY_SCORED_READY_TO_SEAL" else 1

    record = seal_result(args.output)
    print(
        json.dumps(
            {
                "TASK_STATUS": record["TASK_STATUS"],
                "BEST_COUNT": record["BEST_COUNT"],
                "FRESH_CANONICAL_RECOUNT": record["FRESH_CANONICAL_RECOUNT"],
                "INDEPENDENT_7SET_RECOUNT": record["INDEPENDENT_7SET_RECOUNT"],
                "FAMILY_RESULT": record["FAMILY_RESULT"],
                "READY_FOR_LOCAL_ASCENT": record["READY_FOR_LOCAL_ASCENT"],
            },
            sort_keys=True,
        )
    )
    return 0 if record["TASK_STATUS"] == "COMPLETE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
