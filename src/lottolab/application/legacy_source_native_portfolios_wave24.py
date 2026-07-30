"""Faithful ports of the twenty-fourth frozen BIG_LOTTO source-native batch."""

from __future__ import annotations

import hashlib
import math
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from itertools import combinations
from typing import Final, cast

from lottolab.application.legacy_frozen_unified_core import (
    FROZEN_CONFIG_LOADER_SHA256,
    FROZEN_PREDICTION_CONFIG_SHA256,
    FROZEN_UNIFIED_SOURCE_SHA256,
    FrozenUnifiedTickets,
    generate_frozen_unified_tickets,
)
from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.application.strategy_preserving_20_ticket import Ticket

SOURCE_NATIVE_WAVE24_PROTOCOL = "legacy_source_native_wave24/v1"
DEFAULT_SOURCE_NATIVE_WAVE24_USER_SEED = (
    "biglotto-full-universe-source-native-wave24-v1"
)
TWO_BET_FINAL_METHOD_ID = "lottery_api/models/biglotto_2bet_final.py"
THREE_BET_OPTIMIZER_METHOD_ID = (
    "lottery_api/models/biglotto_3bet_optimizer.py"
)
ASM_METHOD_ID = "tools/test_asm.py"
DCB_METHOD_ID = "tools/test_dcb.py"
FOUR_BET_DCB_METHOD_ID = "tools/test_4bet_dcb.py"
ECP_METHOD_ID = "tools/test_ecp.py"
SUPPORTED_SOURCE_NATIVE_WAVE24_METHODS = (
    TWO_BET_FINAL_METHOD_ID,
    THREE_BET_OPTIMIZER_METHOD_ID,
    ASM_METHOD_ID,
    DCB_METHOD_ID,
    FOUR_BET_DCB_METHOD_ID,
    ECP_METHOD_ID,
)
SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE24_METHOD: Final = {
    TWO_BET_FINAL_METHOD_ID: (
        "7eaedb330a07e34ebcf1fb3b8dfede09636be5a5f840c3728e4141284982b6f2"
    ),
    THREE_BET_OPTIMIZER_METHOD_ID: (
        "2835d6cb20c5351f636ef649b9b437f8b474cfad7bbd585aba3d08a95b18742a"
    ),
    ASM_METHOD_ID: (
        "d39a233a4c75158cdab704e26980b89cbb96daf128e50718309731111ac55ddf"
    ),
    DCB_METHOD_ID: (
        "c3299c25ca5930f22bc9809c8e1eac1ba47094e0a18e6e549b5d24d10d591e38"
    ),
    FOUR_BET_DCB_METHOD_ID: (
        "3c7e3e661ad86ccdfac2ec7abd09c0c08101fdf1d639b17acd9427215cfe25a0"
    ),
    ECP_METHOD_ID: (
        "c9d5ac6decddac7940a6ad90739069afd4b13d181dddd4336586e3f718d8e6a2"
    ),
}
_THREE_BET_OPTIMIZER_SHA256 = (
    "2835d6cb20c5351f636ef649b9b437f8b474cfad7bbd585aba3d08a95b18742a"
)
_TOOLS_NEGATIVE_SELECTOR_SHA256 = (
    "80e79f80f9f5978ee2d7e71bb65e7b63bf101192a402ab8a9d0644796d4e3ff0"
)
_COMMON_SHA256 = (
    "c2da77b6e86e32d9cb41fbedb1be80cf62225ac1afff845d4b5bf28a8baf85d2"
)
_DCB_SHA256 = (
    "c3299c25ca5930f22bc9809c8e1eac1ba47094e0a18e6e549b5d24d10d591e38"
)
_CORE_SUPPORT = (
    ("lottery_api/models/unified_predictor.py", FROZEN_UNIFIED_SOURCE_SHA256),
    ("lottery_api/common.py", _COMMON_SHA256),
    ("lottery_api/config_loader.py", FROZEN_CONFIG_LOADER_SHA256),
    ("config/prediction_config.yaml", FROZEN_PREDICTION_CONFIG_SHA256),
)
_KILL_SUPPORT = (
    ("tools/negative_selector.py", _TOOLS_NEGATIVE_SELECTOR_SHA256),
)
_BASE_THREE_BET_SUPPORT = (
    (
        "lottery_api/models/biglotto_3bet_optimizer.py",
        _THREE_BET_OPTIMIZER_SHA256,
    ),
)
FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE24_METHOD: Final = {
    TWO_BET_FINAL_METHOD_ID: _CORE_SUPPORT,
    THREE_BET_OPTIMIZER_METHOD_ID: _CORE_SUPPORT + _KILL_SUPPORT,
    ASM_METHOD_ID: (
        _CORE_SUPPORT + _KILL_SUPPORT + _BASE_THREE_BET_SUPPORT
    ),
    DCB_METHOD_ID: (
        _CORE_SUPPORT + _KILL_SUPPORT + _BASE_THREE_BET_SUPPORT
    ),
    FOUR_BET_DCB_METHOD_ID: (
        _CORE_SUPPORT
        + _KILL_SUPPORT
        + _BASE_THREE_BET_SUPPORT
        + (("tools/test_dcb.py", _DCB_SHA256),)
    ),
    ECP_METHOD_ID: (
        _CORE_SUPPORT + _KILL_SUPPORT + _BASE_THREE_BET_SUPPORT
    ),
}
MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE24_METHOD: Final = {
    method_id: 1 for method_id in SUPPORTED_SOURCE_NATIVE_WAVE24_METHODS
}
NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE24_METHOD: Final = {
    TWO_BET_FINAL_METHOD_ID: 2,
    THREE_BET_OPTIMIZER_METHOD_ID: 3,
    ASM_METHOD_ID: 3,
    DCB_METHOD_ID: 3,
    FOUR_BET_DCB_METHOD_ID: 4,
    ECP_METHOD_ID: 3,
}
NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE24_METHOD: Final = {
    TWO_BET_FINAL_METHOD_ID: (
        "TWO_POSITIONAL_TICKETS_FROM_TOP15_WEIGHTED_POOL_WITH_SECOND_"
        "TICKET_LARGE_NUMBER_PRIORITY"
    ),
    THREE_BET_OPTIMIZER_METHOD_ID: (
        "THREE_POSITIONAL_OVERLAPPING_SLICES_0_6_4_10_8_14_FROM_TOP18"
    ),
    ASM_METHOD_ID: (
        "THREE_POSITIONAL_ANCHOR_SECONDARY_INDEX_MAPPINGS_FROM_BASE_TOP18"
    ),
    DCB_METHOD_ID: (
        "THREE_POSITIONAL_OVERLAPPING_SLICES_FROM_CORRELATION_BOOSTED_TOP18"
    ),
    FOUR_BET_DCB_METHOD_ID: (
        "FOUR_POSITIONAL_OVERLAPPING_SLICES_0_6_4_10_8_14_12_18_FROM_"
        "CORRELATION_BOOSTED_TOP18"
    ),
    ECP_METHOD_ID: (
        "THREE_POSITIONAL_OVERLAPPING_SLICES_FROM_FIFTY_SAMPLE_ELITE_"
        "CONSENSUS_TOP18"
    ),
}
RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE24_METHOD: Final = {
    method_id: (
        "PYTHON_RANDOM_SEED_EQUALS_CAUSAL_HISTORY_LENGTH_FOR_EACH_"
        "STATISTICAL_CALL"
    )
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE24_METHODS
}
SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE24_METHOD: Final = {
    TWO_BET_FINAL_METHOD_ID: 3,
    THREE_BET_OPTIMIZER_METHOD_ID: 3,
    ASM_METHOD_ID: 3,
    DCB_METHOD_ID: 4,
    FOUR_BET_DCB_METHOD_ID: 4,
    ECP_METHOD_ID: 3,
}
SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE24_METHOD: Final = {
    TWO_BET_FINAL_METHOD_ID: (
        "deviation_predict:weight_2.0",
        "markov_predict:weight_2.0",
        "statistical_predict:weight_2.0",
    ),
    THREE_BET_OPTIMIZER_METHOD_ID: (
        "deviation_predict:weight_2.0",
        "markov_predict:weight_1.5",
        "statistical_predict:weight_1.0",
    ),
    ASM_METHOD_ID: (
        "deviation_predict:weight_2.0",
        "markov_predict:weight_1.5",
        "statistical_predict:weight_1.0",
    ),
    DCB_METHOD_ID: (
        "deviation_predict:weight_1.5",
        "markov_predict:weight_1.5",
        "statistical_predict:weight_2.0",
        "hot_cold_mix_predict:weight_1.0",
    ),
    FOUR_BET_DCB_METHOD_ID: (
        "deviation_predict:weight_1.5",
        "markov_predict:weight_1.5",
        "statistical_predict:weight_2.0",
        "hot_cold_mix_predict:weight_1.0",
    ),
    ECP_METHOD_ID: (
        "statistical_predict:fifty_reseeded_samples_weight_1_each",
        "markov_predict:boost_5",
        "deviation_predict:boost_5",
    ),
}
SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE24_METHOD: Final = {
    method_id: "OLDEST_FIRST"
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE24_METHODS
}


class LegacySourceNativeWave24Error(ValueError):
    """A request cannot satisfy the twenty-fourth source-native contract."""


class LegacySourceNativeWave24SourceError(
    LegacySourceNativeWave24Error
):
    """The frozen source emitted no valid six-number native portfolio."""

    def __init__(self, reason_code: str) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code


@dataclass(frozen=True, slots=True)
class LegacySourceNativeWave24Request:
    legacy_method_id: str
    target_draw_number: str
    history: tuple[LegacyHistoryDraw, ...]
    replicate_id: int = 0
    user_seed: str | int = DEFAULT_SOURCE_NATIVE_WAVE24_USER_SEED


@dataclass(frozen=True, slots=True)
class LegacySourceNativeWave24Metadata:
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
    native_ticket_order: str
    native_duplicate_ticket_count: int
    candidate_k: int | None
    candidate_pool: tuple[int, ...]
    candidate_pool_size: int
    combination_count: int | None
    combination_members: tuple[str, ...]
    source_method_combination_count: int
    kill_numbers: tuple[int, ...]
    markov_order: int
    statistical_call_count: int
    config_loader_runtime_semantics: str
    frozen_support_artifacts: tuple[tuple[str, str], ...]

    def canonical_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class LegacySourceNativeWave24Result:
    tickets: tuple[Ticket, ...]
    metadata: LegacySourceNativeWave24Metadata


def _validate_request(request: LegacySourceNativeWave24Request) -> None:
    if (
        request.legacy_method_id
        not in SUPPORTED_SOURCE_NATIVE_WAVE24_METHODS
    ):
        raise LegacySourceNativeWave24Error(
            "unsupported frozen source-native wave-24 method"
        )
    if (
        type(request.target_draw_number) is not str
        or not request.target_draw_number
        or type(request.replicate_id) is not int
        or request.replicate_id < 0
        or type(request.user_seed) not in (str, int)
        or not request.history
    ):
        raise LegacySourceNativeWave24Error(
            "invalid frozen source-native wave-24 request"
        )
    seen: set[str] = set()
    for draw in request.history:
        if (
            not draw.draw_number
            or draw.draw_number == request.target_draw_number
            or draw.draw_number in seen
        ):
            raise LegacySourceNativeWave24Error(
                "causal history draw identities are invalid"
            )
        seen.add(draw.draw_number)
        if (
            len(draw.numbers) != 6
            or len(set(draw.numbers)) != 6
            or any(
                type(number) is not int or not 1 <= number <= 49
                for number in draw.numbers
            )
        ):
            raise LegacySourceNativeWave24Error(
                "causal history ticket is invalid"
            )


def _seed(
    request: LegacySourceNativeWave24Request,
) -> tuple[str, str, int]:
    material = "|".join(
        (
            SOURCE_NATIVE_WAVE24_PROTOCOL,
            request.legacy_method_id,
            SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE24_METHOD[
                request.legacy_method_id
            ],
            request.target_draw_number,
            str(request.replicate_id),
            str(request.user_seed),
        )
    )
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return material, digest, int(digest, 16)


def frozen_tools_kill_numbers(
    history: tuple[LegacyHistoryDraw, ...],
    *,
    count: int = 10,
) -> tuple[int, ...]:
    """Port tools/negative_selector.py dynamic entropy kill selection."""

    if len(history) < 30:
        return ()
    zone_counts = [0] * 5
    zone_size = 49 / 5
    for draw in history[-30:]:
        for number in draw.numbers:
            zone_index = min(int((number - 1) / zone_size), 4)
            zone_counts[zone_index] += 1
    total_hits = sum(zone_counts)
    entropy = 0.0
    if total_hits:
        for zone_count in zone_counts:
            probability = zone_count / total_hits
            if probability > 0:
                entropy -= probability * math.log2(probability)
    if entropy < 2.0:
        dynamic_count = min(15, count + 2)
    elif entropy > 2.2:
        dynamic_count = max(5, count - 5)
    else:
        dynamic_count = count

    frequency = Counter(
        number for draw in history[-100:] for number in draw.numbers
    )
    gaps = {number: 999 for number in range(1, 50)}
    for index, draw in enumerate(reversed(history)):
        for number in draw.numbers:
            if gaps[number] == 999:
                gaps[number] = index
    scores: list[tuple[int, int]] = []
    for number in range(1, 50):
        score = frequency.get(number, 0)
        if gaps[number] > 22:
            score += 100
        scores.append((number, score))
    scores.sort(key=lambda item: item[1])
    return tuple(
        sorted(number for number, _score in scores[:dynamic_count])
    )


def _weighted_candidates(
    unified: FrozenUnifiedTickets,
    specifications: tuple[tuple[str, float], ...],
) -> Counter[int]:
    tickets = {
        "deviation": unified.deviation,
        "markov": unified.markov,
        "statistical": unified.statistical,
        "hot_cold": unified.hot_cold,
    }
    candidates: Counter[int] = Counter()
    for name, weight in specifications:
        for number in tickets[name]:
            candidates[number] += cast(int, weight)
    return candidates


def _apply_kill(
    candidates: Counter[int],
    kill_numbers: tuple[int, ...],
) -> None:
    for number in kill_numbers:
        candidates[number] = -9999


def _tickets_or_close(
    rows: list[list[int]],
) -> tuple[Ticket, ...]:
    tickets: list[Ticket] = []
    for row in rows:
        ticket = tuple(sorted(row))
        if (
            len(ticket) != 6
            or len(set(ticket)) != 6
            or any(not 1 <= number <= 49 for number in ticket)
        ):
            raise LegacySourceNativeWave24SourceError(
                "FROZEN_SOURCE_EMITTED_INVALID_NATIVE_TICKET"
            )
        tickets.append(ticket)
    return tuple(tickets)


def _base_top18(
    unified: FrozenUnifiedTickets,
    kill_numbers: tuple[int, ...],
) -> list[int]:
    candidates = _weighted_candidates(
        unified,
        (
            ("deviation", 2.0),
            ("markov", 1.5),
            ("statistical", 1.0),
        ),
    )
    _apply_kill(candidates, kill_numbers)
    return [number for number, _score in candidates.most_common(18)]


def _dcb_top18(
    history: tuple[LegacyHistoryDraw, ...],
    unified: FrozenUnifiedTickets,
    kill_numbers: tuple[int, ...],
) -> list[int]:
    candidates = _weighted_candidates(
        unified,
        (
            ("deviation", 1.5),
            ("markov", 1.5),
            ("statistical", 2.0),
            ("hot_cold", 1.0),
        ),
    )
    _apply_kill(candidates, kill_numbers)
    matrix: defaultdict[int, Counter[int]] = defaultdict(Counter)
    for draw in history[-200:]:
        for left, right in combinations(sorted(draw.numbers), 2):
            matrix[left][right] += 1
            matrix[right][left] += 1
    top_five = [number for number, _score in candidates.most_common(5)]
    boosted_candidates = Counter(candidates)
    for anchor in top_five:
        base_score = candidates[anchor]
        for neighbor, cooccurrence_count in matrix[anchor].items():
            if (
                neighbor in boosted_candidates
                and boosted_candidates[neighbor] > 0
            ):
                boosted_candidates[neighbor] += cast(
                    int,
                    base_score * 0.1 * (cooccurrence_count / 10),
                )
    return [
        number
        for number, _score in boosted_candidates.most_common(18)
    ]


def _native_rows(
    method_id: str,
    history: tuple[LegacyHistoryDraw, ...],
    unified: FrozenUnifiedTickets,
) -> tuple[list[list[int]], list[int], tuple[int, ...], int]:
    kill_numbers: tuple[int, ...] = ()
    statistical_call_count = 1
    if method_id == TWO_BET_FINAL_METHOD_ID:
        candidates = _weighted_candidates(
            unified,
            (
                ("deviation", 2.0),
                ("markov", 2.0),
                ("statistical", 2.0),
            ),
        )
        top_candidates = [
            number for number, _score in candidates.most_common(15)
        ]
        second_candidates = top_candidates[3:12]
        second: list[int] = []
        for number in second_candidates:
            if (
                number > 24
                and sum(item > 24 for item in second) < 3
            ):
                second.append(number)
        for number in second_candidates:
            if number not in second and len(second) < 6:
                second.append(number)
        return (
            [top_candidates[:6], second],
            top_candidates,
            (),
            statistical_call_count,
        )

    kill_numbers = frozen_tools_kill_numbers(history)
    if method_id in (
        THREE_BET_OPTIMIZER_METHOD_ID,
        ASM_METHOD_ID,
    ):
        top_candidates = _base_top18(unified, kill_numbers)
        if method_id == THREE_BET_OPTIMIZER_METHOD_ID:
            slices = ((0, 6), (4, 10), (8, 14))
            rows = [
                top_candidates[start:end] for start, end in slices
            ]
        else:
            index_maps = (
                (0, 1, 2, 3, 4, 5),
                (0, 1, 6, 7, 8, 9),
                (2, 3, 4, 10, 11, 12),
            )
            try:
                rows = [
                    [top_candidates[index] for index in indexes]
                    for indexes in index_maps
                ]
            except IndexError as exc:
                raise LegacySourceNativeWave24SourceError(
                    "FROZEN_SOURCE_CANDIDATE_INDEX_OUT_OF_RANGE"
                ) from exc
        return (
            rows,
            top_candidates,
            kill_numbers,
            statistical_call_count,
        )

    if method_id in (DCB_METHOD_ID, FOUR_BET_DCB_METHOD_ID):
        top_candidates = _dcb_top18(
            history,
            unified,
            kill_numbers,
        )
        slices = (
            ((0, 6), (4, 10), (8, 14), (12, 18))
            if method_id == FOUR_BET_DCB_METHOD_ID
            else ((0, 6), (4, 10), (8, 14))
        )
        rows = [top_candidates[start:end] for start, end in slices]
        return (
            rows,
            top_candidates,
            kill_numbers,
            statistical_call_count,
        )

    consensus: Counter[int] = Counter()
    statistical_call_count = 50
    for _sample in range(statistical_call_count):
        for number in unified.statistical:
            consensus[number] += 1
    for number in unified.markov:
        consensus[number] += 5
    for number in unified.deviation:
        consensus[number] += 5
    _apply_kill(consensus, kill_numbers)
    top_candidates = [
        number for number, _score in consensus.most_common(18)
    ]
    rows = [
        top_candidates[start:end]
        for start, end in ((0, 6), (4, 10), (8, 14))
    ]
    return (
        rows,
        top_candidates,
        kill_numbers,
        statistical_call_count,
    )


def build_legacy_source_native_wave24_result(
    request: LegacySourceNativeWave24Request,
    unified: FrozenUnifiedTickets,
) -> LegacySourceNativeWave24Result:
    """Build method-specific native output from one shared frozen core run."""

    _validate_request(request)
    rows, candidate_pool, kill_numbers, statistical_call_count = (
        _native_rows(request.legacy_method_id, request.history, unified)
    )
    tickets = _tickets_or_close(rows)
    expected_count = (
        NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE24_METHOD[
            request.legacy_method_id
        ]
    )
    if len(tickets) != expected_count:
        raise LegacySourceNativeWave24SourceError(
            "FROZEN_SOURCE_NATIVE_TICKET_COUNT_CHANGED"
        )
    seed_material, seed_digest, seed_integer = _seed(request)
    return LegacySourceNativeWave24Result(
        tickets=tickets,
        metadata=LegacySourceNativeWave24Metadata(
            protocol=SOURCE_NATIVE_WAVE24_PROTOCOL,
            legacy_method_id=request.legacy_method_id,
            source_sha256=(
                SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE24_METHOD[
                    request.legacy_method_id
                ]
            ),
            target_draw_number=request.target_draw_number,
            replicate_id=request.replicate_id,
            user_seed=request.user_seed,
            seed_material=seed_material,
            seed_digest=seed_digest,
            seed_integer=seed_integer,
            random_protocol=(
                RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE24_METHOD[
                    request.legacy_method_id
                ]
            ),
            randomness_used=True,
            randomness_reproduction=(
                "FROZEN_SOURCE_RESEEDS_PYTHON_RANDOM_WITH_CAUSAL_HISTORY_"
                "LENGTH_INSIDE_EVERY_STATISTICAL_PREDICT_CALL"
            ),
            history_draw_count=len(request.history),
            history_first_draw_number=request.history[0].draw_number,
            history_cutoff_draw_number=request.history[-1].draw_number,
            source_history_order=(
                SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE24_METHOD[
                    request.legacy_method_id
                ]
            ),
            native_ticket_count=len(tickets),
            native_ticket_order=(
                "FROZEN_SOURCE_ENTRYPOINT_POSITIONAL_ORDER"
            ),
            native_duplicate_ticket_count=(
                len(tickets) - len(set(tickets))
            ),
            candidate_k=None,
            candidate_pool=tuple(candidate_pool),
            candidate_pool_size=len(candidate_pool),
            combination_count=None,
            combination_members=(
                SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE24_METHOD[
                    request.legacy_method_id
                ]
            ),
            source_method_combination_count=(
                SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE24_METHOD[
                    request.legacy_method_id
                ]
            ),
            kill_numbers=kill_numbers,
            markov_order=unified.markov_order,
            statistical_call_count=statistical_call_count,
            config_loader_runtime_semantics=(
                "PINNED_PREDICTION_CONFIG_BIG_LOTTO_STATISTICAL_"
                "OPTIMIZED_PARAMETERS"
            ),
            frozen_support_artifacts=(
                FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE24_METHOD[
                    request.legacy_method_id
                ]
            ),
        ),
    )


def generate_legacy_source_native_wave24_portfolio(
    request: LegacySourceNativeWave24Request,
) -> LegacySourceNativeWave24Result:
    """Reproduce one frozen weighted candidate-pool native portfolio."""

    _validate_request(request)
    try:
        unified = generate_frozen_unified_tickets(request.history)
    except ValueError as exc:
        raise LegacySourceNativeWave24SourceError(str(exc)) from exc
    return build_legacy_source_native_wave24_result(request, unified)


__all__ = [
    "ASM_METHOD_ID",
    "DCB_METHOD_ID",
    "DEFAULT_SOURCE_NATIVE_WAVE24_USER_SEED",
    "ECP_METHOD_ID",
    "FOUR_BET_DCB_METHOD_ID",
    "FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE24_METHOD",
    "MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE24_METHOD",
    "NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE24_METHOD",
    "NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE24_METHOD",
    "RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE24_METHOD",
    "SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE24_METHOD",
    "SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE24_METHOD",
    "SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE24_METHOD",
    "SOURCE_NATIVE_WAVE24_PROTOCOL",
    "SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE24_METHOD",
    "SUPPORTED_SOURCE_NATIVE_WAVE24_METHODS",
    "THREE_BET_OPTIMIZER_METHOD_ID",
    "TWO_BET_FINAL_METHOD_ID",
    "LegacySourceNativeWave24Error",
    "LegacySourceNativeWave24Metadata",
    "LegacySourceNativeWave24Request",
    "LegacySourceNativeWave24Result",
    "LegacySourceNativeWave24SourceError",
    "build_legacy_source_native_wave24_result",
    "frozen_tools_kill_numbers",
    "generate_legacy_source_native_wave24_portfolio",
]
