"""Faithful ports of the seventh frozen BIG_LOTTO source-native batch."""

from __future__ import annotations

import hashlib
import random
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from itertools import combinations
from typing import Final

from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.application.strategy_preserving_20_ticket import Ticket

SOURCE_NATIVE_WAVE7_PROTOCOL = "legacy_source_native_wave7/v1"
DEFAULT_SOURCE_NATIVE_WAVE7_USER_SEED = (
    "biglotto-full-universe-source-native-wave7-v1"
)
CLUSTER_6_METHOD_ID = "tools/predict_biglotto_6bets_cluster.py"
CLUSTER_7_METHOD_ID = "tools/predict_biglotto_7bets_cluster.py"
APRIORI_PREDICT_METHOD_ID = "tools/predict_biglotto_apriori.py"
APRIORI_BACKTEST_METHOD_ID = "tools/backtest_apriori.py"
BEST_HYBRID_METHOD_ID = "tools/predict_biglotto_best.py"
SUPPORTED_SOURCE_NATIVE_WAVE7_METHODS = (
    CLUSTER_6_METHOD_ID,
    CLUSTER_7_METHOD_ID,
    APRIORI_PREDICT_METHOD_ID,
    APRIORI_BACKTEST_METHOD_ID,
    BEST_HYBRID_METHOD_ID,
)
SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE7_METHOD: Final = {
    CLUSTER_6_METHOD_ID: (
        "1fd9e8a7ae2ae9f19b97cb68cde009bce3962d8344a24f9bf07e15cc803abde3"
    ),
    CLUSTER_7_METHOD_ID: (
        "8f55b5d94669543524eef58d65598213097357925a8f982c84ae7614fa85a735"
    ),
    APRIORI_PREDICT_METHOD_ID: (
        "cda690ae84c2324b5f7d160a68e0ba3cf65d6073ecfc5c28ef48402b07018e7b"
    ),
    APRIORI_BACKTEST_METHOD_ID: (
        "2abb537657035eec87da9863055f817d81ffafe83084f0f53858ad31327282a1"
    ),
    BEST_HYBRID_METHOD_ID: (
        "8f7cb601fb6c329187859de3d7c35cca3e1ef7a94472c9c8c2c33b2238950fa3"
    ),
}
MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE7_METHOD: Final = {
    method_id: 1 for method_id in SUPPORTED_SOURCE_NATIVE_WAVE7_METHODS
}
NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE7_METHOD: Final = {
    CLUSTER_6_METHOD_ID: (
        "UP_TO_6_CLUSTER_CENTER_TICKETS_IN_SOURCE_LOOP_ORDER"
    ),
    CLUSTER_7_METHOD_ID: (
        "UP_TO_7_CLUSTER_CENTER_TICKETS_IN_SOURCE_LOOP_ORDER"
    ),
    APRIORI_PREDICT_METHOD_ID: (
        "UP_TO_7_DISTINCT_ANTECEDENT_RULE_TICKETS_IN_SOURCE_ORDER"
    ),
    APRIORI_BACKTEST_METHOD_ID: (
        "SOURCE_CONFIGURATIONS_1_2_3_7_FLATTENED_TO_13_POSITIONAL_TICKETS"
    ),
    BEST_HYBRID_METHOD_ID: (
        "DEFAULT_6_CLUSTER_TICKETS_THEN_1_SKEW_DEFENSE_TICKET"
    ),
}
RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE7_METHOD: Final = {
    CLUSTER_6_METHOD_ID: "NONE_DETERMINISTIC",
    CLUSTER_7_METHOD_ID: "NONE_DETERMINISTIC",
    APRIORI_PREDICT_METHOD_ID: "NONE_DETERMINISTIC",
    APRIORI_BACKTEST_METHOD_ID: (
        "random.Random(MT19937)_TARGET_STABLE_REPLACEMENT_"
        "FOR_UNPRESERVED_BACKTEST_HORIZON_GLOBAL_STREAM"
    ),
    BEST_HYBRID_METHOD_ID: (
        "random.Random(MT19937)_TARGET_STABLE_REPLACEMENT_"
        "FOR_UNPRESERVED_MODULE_GLOBAL_SKEW_STATE"
    ),
}
CANDIDATE_K_BY_SOURCE_NATIVE_WAVE7_METHOD: Final = {
    CLUSTER_6_METHOD_ID: 8,
    CLUSTER_7_METHOD_ID: 9,
    APRIORI_PREDICT_METHOD_ID: None,
    APRIORI_BACKTEST_METHOD_ID: None,
    BEST_HYBRID_METHOD_ID: 8,
}
SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE7_METHOD: Final = {
    CLUSTER_6_METHOD_ID: None,
    CLUSTER_7_METHOD_ID: None,
    APRIORI_PREDICT_METHOD_ID: None,
    APRIORI_BACKTEST_METHOD_ID: 4,
    BEST_HYBRID_METHOD_ID: None,
}
SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE7_METHOD: Final = {
    CLUSTER_6_METHOD_ID: ("generate_bets:num_bets=6,window=150",),
    CLUSTER_7_METHOD_ID: ("generate_bets:num_bets=7,window=150",),
    APRIORI_PREDICT_METHOD_ID: (
        "predict_next_draw:num_bets=7,window=150",
    ),
    APRIORI_BACKTEST_METHOD_ID: (
        "predict_for_backtest:num_bets=1,window=150",
        "predict_for_backtest:num_bets=2,window=150",
        "predict_for_backtest:num_bets=3,window=150",
        "predict_for_backtest:num_bets=7,window=150",
    ),
    BEST_HYBRID_METHOD_ID: (
        "main:default_num_bets=7:cluster_6_then_skew_1",
    ),
}
SOURCE_CANDIDATE_TICKET_COUNTS_BY_SOURCE_NATIVE_WAVE7_METHOD: Final = {
    method_id: () for method_id in SUPPORTED_SOURCE_NATIVE_WAVE7_METHODS
}
SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE7_METHOD: Final = {
    CLUSTER_6_METHOD_ID: "RECENT_FIRST",
    CLUSTER_7_METHOD_ID: "RECENT_FIRST",
    APRIORI_PREDICT_METHOD_ID: "RECENT_FIRST",
    APRIORI_BACKTEST_METHOD_ID: "OLDEST_FIRST",
    BEST_HYBRID_METHOD_ID: "RECENT_FIRST",
}

_MIN_NUMBER = 1
_MAX_NUMBER = 49
_PICK_COUNT = 6


class LegacySourceNativeWave7Error(ValueError):
    """A request cannot satisfy the seventh source-native batch contract."""


class LegacySourceNativeWave7SourceError(
    LegacySourceNativeWave7Error
):
    """A frozen source emitted no valid six-number native portfolio."""

    def __init__(self, reason_code: str) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code


@dataclass(frozen=True, slots=True)
class LegacySourceNativeWave7Request:
    legacy_method_id: str
    target_draw_number: str
    history: tuple[LegacyHistoryDraw, ...]
    replicate_id: int = 0
    user_seed: str | int = DEFAULT_SOURCE_NATIVE_WAVE7_USER_SEED


@dataclass(frozen=True, slots=True)
class LegacySourceNativeWave7Metadata:
    protocol: str
    legacy_method_id: str
    source_sha256: str
    target_draw_number: str
    replicate_id: int
    user_seed: str | int
    seed_material: str
    seed_digest: str
    seed_integer: int
    random_protocol: str
    randomness_used: bool
    randomness_reproduction: str
    history_draw_count: int
    history_first_draw_number: str
    history_cutoff_draw_number: str
    source_history_order: str
    native_ticket_count: int
    native_ticket_count_semantics: str
    native_ticket_order: str
    native_duplicate_ticket_count: int
    source_combination_members: tuple[str, ...]
    source_candidate_ticket_counts: tuple[int, ...]
    candidate_k: None
    combination_count: None

    def canonical_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class LegacySourceNativeWave7Result:
    tickets: tuple[Ticket, ...]
    metadata: LegacySourceNativeWave7Metadata


@dataclass(frozen=True, slots=True)
class _Rule:
    antecedent: tuple[int, ...]
    consequent: int
    confidence: float


def _validate_request(request: LegacySourceNativeWave7Request) -> None:
    if (
        request.legacy_method_id
        not in SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE7_METHOD
    ):
        raise LegacySourceNativeWave7Error(
            "legacy method is outside the seventh source-native batch"
        )
    if (
        type(request.target_draw_number) is not str
        or not request.target_draw_number
    ):
        raise LegacySourceNativeWave7Error(
            "target draw number must be non-empty"
        )
    if type(request.replicate_id) is not int or request.replicate_id < 0:
        raise LegacySourceNativeWave7Error(
            "replicate_id must be a non-negative integer"
        )
    if type(request.user_seed) not in (str, int):
        raise LegacySourceNativeWave7Error(
            "user_seed must be a string or integer"
        )
    seen: set[str] = set()
    for draw in request.history:
        if not draw.draw_number or draw.draw_number in seen:
            raise LegacySourceNativeWave7Error(
                "causal history draw identities are invalid"
            )
        seen.add(draw.draw_number)
        _ticket(draw.numbers)


def _seed(
    request: LegacySourceNativeWave7Request,
) -> tuple[str, str, int]:
    source_sha256 = SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE7_METHOD[
        request.legacy_method_id
    ]
    material = "|".join(
        (
            SOURCE_NATIVE_WAVE7_PROTOCOL,
            request.legacy_method_id,
            source_sha256,
            request.target_draw_number,
            str(request.replicate_id),
            str(request.user_seed),
        )
    )
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return material, digest, int(digest, 16)


def _ticket(numbers: tuple[int, ...] | list[int]) -> Ticket:
    values = tuple(sorted(numbers))
    if (
        len(values) != _PICK_COUNT
        or len(set(values)) != _PICK_COUNT
        or any(
            type(number) is not int
            or not _MIN_NUMBER <= number <= _MAX_NUMBER
            for number in values
        )
    ):
        raise LegacySourceNativeWave7SourceError(
            "FROZEN_SOURCE_INVALID_TICKET"
        )
    return values


def _newest_first_window(
    history: tuple[LegacyHistoryDraw, ...],
    *,
    window: int = 150,
) -> tuple[tuple[int, ...], ...]:
    return tuple(
        draw.numbers for draw in reversed(history)
    )[:window]


def _oldest_first_window(
    history: tuple[LegacyHistoryDraw, ...],
    *,
    window: int = 150,
) -> tuple[tuple[int, ...], ...]:
    return tuple(draw.numbers for draw in history[-window:])


def _cooccurrence(
    history: tuple[tuple[int, ...], ...],
) -> Counter[tuple[int, int]]:
    cooccur: Counter[tuple[int, int]] = Counter()
    for draw in history:
        for pair in combinations(sorted(draw), 2):
            cooccur[pair] += 1
    return cooccur


def _cluster_centers(
    cooccur: Counter[tuple[int, int]],
    *,
    top_k: int,
) -> list[int]:
    scores: Counter[int] = Counter()
    for (left, right), count in cooccur.items():
        scores[left] += count
        scores[right] += count
    return [number for number, _count in scores.most_common(top_k)]


def _expand_from_anchor(
    *,
    anchor: int,
    cooccur: Counter[tuple[int, int]],
    exclude: set[int],
) -> list[int]:
    candidates: Counter[int] = Counter()
    for (left, right), count in cooccur.items():
        if left == anchor and right not in exclude:
            candidates[right] += count
        elif right == anchor and left not in exclude:
            candidates[left] += count
    selected = [anchor]
    for number, _count in candidates.most_common(12):
        if number not in selected and number not in exclude:
            selected.append(number)
        if len(selected) >= _PICK_COUNT:
            break
    if len(selected) < _PICK_COUNT:
        all_numbers: Counter[int] = Counter()
        for left, right in cooccur:
            all_numbers[left] += 1
            all_numbers[right] += 1
        for number, _count in all_numbers.most_common(50):
            if number not in selected and number not in exclude:
                selected.append(number)
            if len(selected) >= _PICK_COUNT:
                break
    return sorted(selected[:_PICK_COUNT])


def _cluster_tickets(
    history: tuple[tuple[int, ...], ...],
    *,
    num_bets: int,
) -> list[list[int]]:
    cooccur = _cooccurrence(history)
    centers = _cluster_centers(cooccur, top_k=num_bets + 2)
    bets: list[list[int]] = []
    for index in range(num_bets):
        if index >= len(centers):
            break
        exclude = {
            number
            for previous in bets
            for number in previous[:2]
        }
        candidate = _expand_from_anchor(
            anchor=centers[index],
            cooccur=cooccur,
            exclude=exclude,
        )
        if any(set(previous) == set(candidate) for previous in bets):
            continue
        bets.append(candidate)
    return bets


def _frequent_itemsets(
    history: tuple[tuple[int, ...], ...],
) -> dict[tuple[int, ...], int]:
    counts: defaultdict[tuple[int, ...], int] = defaultdict(int)
    for draw in history:
        numbers = sorted(draw)
        for number in numbers:
            counts[(number,)] += 1
        for pair in combinations(numbers, 2):
            counts[pair] += 1
        for trio in combinations(numbers, 3):
            counts[trio] += 1
    return {
        itemset: count
        for itemset, count in counts.items()
        if count >= 3
    }


def _rules(
    frequent: dict[tuple[int, ...], int],
) -> list[_Rule]:
    rules: list[_Rule] = []
    for itemset, support_union in frequent.items():
        if len(itemset) < 2:
            continue
        for consequent_tuple in combinations(itemset, 1):
            consequent = consequent_tuple[0]
            antecedent = tuple(
                sorted(set(itemset) - {consequent})
            )
            if antecedent not in frequent:
                continue
            confidence = support_union / frequent[antecedent]
            if confidence >= 0.4:
                rules.append(
                    _Rule(
                        antecedent=antecedent,
                        consequent=consequent,
                        confidence=confidence,
                    )
                )
    return sorted(
        rules,
        key=lambda rule: rule.confidence,
        reverse=True,
    )


def _rule_ticket(
    *,
    target_rule: _Rule,
    rules: list[_Rule],
    bet_index: int,
) -> list[int]:
    current = sorted(
        set((*target_rule.antecedent, target_rule.consequent))
    )
    while len(current) < _PICK_COUNT:
        last_number = current[-1]
        candidates = [
            rule
            for rule in rules
            if rule.consequent not in current
            and (
                rule.antecedent == (last_number,)
                or (
                    len(rule.antecedent) == 1
                    and rule.antecedent[0] in current
                )
            )
        ]
        if candidates:
            candidates.sort(
                key=lambda rule: rule.confidence,
                reverse=True,
            )
            next_number = candidates[0].consequent
        else:
            remaining = [
                number
                for number in range(_MIN_NUMBER, _MAX_NUMBER + 1)
                if number not in current
            ]
            if not remaining:
                break
            next_number = remaining[bet_index % len(remaining)]
        current.append(next_number)
        current = sorted(set(current))
    return sorted(current[:_PICK_COUNT])


def _apriori_predict_tickets(
    history: tuple[tuple[int, ...], ...],
    *,
    num_bets: int,
) -> list[list[int]]:
    rules = _rules(_frequent_itemsets(history))
    used_antecedents: set[tuple[int, ...]] = set()
    bets: list[list[int]] = []
    for index in range(num_bets):
        target_rule = next(
            (
                rule
                for rule in rules
                if rule.antecedent not in used_antecedents
            ),
            None,
        )
        if target_rule is None:
            break
        used_antecedents.add(target_rule.antecedent)
        bets.append(
            _rule_ticket(
                target_rule=target_rule,
                rules=rules,
                bet_index=index,
            )
        )
    return bets


def _apriori_backtest_tickets(
    history: tuple[tuple[int, ...], ...],
    *,
    num_bets: int,
    rng: random.Random,
) -> list[list[int]]:
    rules = _rules(_frequent_itemsets(history))
    used_antecedents: set[tuple[int, ...]] = set()
    bets: list[list[int]] = []
    for index in range(num_bets):
        target_rule = next(
            (
                rule
                for rule in rules
                if rule.antecedent not in used_antecedents
            ),
            None,
        )
        if target_rule is None:
            bets.append(
                sorted(rng.sample(range(_MIN_NUMBER, _MAX_NUMBER + 1), 6))
            )
            continue
        used_antecedents.add(target_rule.antecedent)
        bets.append(
            _rule_ticket(
                target_rule=target_rule,
                rules=rules,
                bet_index=index,
            )
        )
    return bets


def _skew_ticket(rng: random.Random) -> list[int]:
    skew_type = rng.choice(
        ("ALL_BIG", "ALL_SMALL", "ALL_ODD", "ALL_EVEN", "ZONE_FOCUS")
    )
    if skew_type == "ALL_BIG":
        return sorted(rng.sample(range(25, 50), 6))
    if skew_type == "ALL_SMALL":
        return sorted(rng.sample(range(1, 25), 6))
    if skew_type == "ALL_ODD":
        return sorted(
            rng.sample(
                [number for number in range(1, 50) if number % 2 != 0],
                6,
            )
        )
    if skew_type == "ALL_EVEN":
        return sorted(
            rng.sample(
                [number for number in range(1, 50) if number % 2 == 0],
                6,
            )
        )
    start = rng.choice((1, 11, 21, 31))
    zone_pool = list(range(start, min(start + 10, 50)))
    others = [
        number
        for number in range(1, 50)
        if number not in zone_pool
    ]
    return sorted(
        rng.sample(zone_pool, 4) + rng.sample(others, 2)
    )


def _raw_tickets(
    request: LegacySourceNativeWave7Request,
    *,
    seed_integer: int,
) -> list[list[int]]:
    method_id = request.legacy_method_id
    rng = random.Random()
    rng.seed(seed_integer, version=2)
    if method_id == CLUSTER_6_METHOD_ID:
        return _cluster_tickets(
            _newest_first_window(request.history),
            num_bets=6,
        )
    if method_id == CLUSTER_7_METHOD_ID:
        return _cluster_tickets(
            _newest_first_window(request.history),
            num_bets=7,
        )
    if method_id == APRIORI_PREDICT_METHOD_ID:
        return _apriori_predict_tickets(
            _newest_first_window(request.history),
            num_bets=7,
        )
    if method_id == APRIORI_BACKTEST_METHOD_ID:
        history = _oldest_first_window(request.history)
        return [
            ticket
            for num_bets in (1, 2, 3, 7)
            for ticket in _apriori_backtest_tickets(
                history,
                num_bets=num_bets,
                rng=rng,
            )
        ]
    return [
        *_cluster_tickets(
            _newest_first_window(request.history),
            num_bets=6,
        ),
        _skew_ticket(rng),
    ]


def generate_legacy_source_native_wave7_portfolio(
    request: LegacySourceNativeWave7Request,
) -> LegacySourceNativeWave7Result:
    """Generate source-ordered native tickets from strictly prior history."""

    _validate_request(request)
    minimum_history = MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE7_METHOD[
        request.legacy_method_id
    ]
    if len(request.history) < minimum_history:
        raise LegacySourceNativeWave7Error(
            f"method requires at least {minimum_history} history draws"
        )
    seed_material, seed_digest, seed_integer = _seed(request)
    raw_tickets = _raw_tickets(
        request,
        seed_integer=seed_integer,
    )
    if not raw_tickets:
        raise LegacySourceNativeWave7SourceError(
            "FROZEN_SOURCE_NO_NATIVE_TICKETS"
        )
    tickets = tuple(_ticket(ticket) for ticket in raw_tickets)
    random_protocol = RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE7_METHOD[
        request.legacy_method_id
    ]
    return LegacySourceNativeWave7Result(
        tickets=tickets,
        metadata=LegacySourceNativeWave7Metadata(
            protocol=SOURCE_NATIVE_WAVE7_PROTOCOL,
            legacy_method_id=request.legacy_method_id,
            source_sha256=(
                SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE7_METHOD[
                    request.legacy_method_id
                ]
            ),
            target_draw_number=request.target_draw_number,
            replicate_id=request.replicate_id,
            user_seed=request.user_seed,
            seed_material=seed_material,
            seed_digest=seed_digest,
            seed_integer=seed_integer,
            random_protocol=random_protocol,
            randomness_used=random_protocol != "NONE_DETERMINISTIC",
            randomness_reproduction=(
                "SOURCE_DETERMINISTIC"
                if random_protocol == "NONE_DETERMINISTIC"
                else (
                    "TARGET_STABLE_SOURCE_CALL_ORDER_PRESERVING_"
                    "VERSIONED_SEED"
                )
            ),
            history_draw_count=len(request.history),
            history_first_draw_number=request.history[0].draw_number,
            history_cutoff_draw_number=request.history[-1].draw_number,
            source_history_order=(
                SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE7_METHOD[
                    request.legacy_method_id
                ]
            ),
            native_ticket_count=len(tickets),
            native_ticket_count_semantics=(
                NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE7_METHOD[
                    request.legacy_method_id
                ]
            ),
            native_ticket_order=(
                "FROZEN_SOURCE_CONFIGURATION_AND_BET_LOOP_ORDER"
            ),
            native_duplicate_ticket_count=(
                len(tickets) - len(set(tickets))
            ),
            source_combination_members=(
                SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE7_METHOD[
                    request.legacy_method_id
                ]
            ),
            source_candidate_ticket_counts=(),
            candidate_k=None,
            combination_count=None,
        ),
    )


__all__ = [
    "APRIORI_BACKTEST_METHOD_ID",
    "APRIORI_PREDICT_METHOD_ID",
    "BEST_HYBRID_METHOD_ID",
    "CANDIDATE_K_BY_SOURCE_NATIVE_WAVE7_METHOD",
    "CLUSTER_6_METHOD_ID",
    "CLUSTER_7_METHOD_ID",
    "DEFAULT_SOURCE_NATIVE_WAVE7_USER_SEED",
    "MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE7_METHOD",
    "NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE7_METHOD",
    "RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE7_METHOD",
    "SOURCE_CANDIDATE_TICKET_COUNTS_BY_SOURCE_NATIVE_WAVE7_METHOD",
    "SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE7_METHOD",
    "SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE7_METHOD",
    "SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE7_METHOD",
    "SOURCE_NATIVE_WAVE7_PROTOCOL",
    "SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE7_METHOD",
    "SUPPORTED_SOURCE_NATIVE_WAVE7_METHODS",
    "LegacySourceNativeWave7Error",
    "LegacySourceNativeWave7Metadata",
    "LegacySourceNativeWave7Request",
    "LegacySourceNativeWave7Result",
    "LegacySourceNativeWave7SourceError",
    "generate_legacy_source_native_wave7_portfolio",
]
