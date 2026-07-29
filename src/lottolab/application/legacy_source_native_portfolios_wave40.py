"""Faithful port of the fortieth frozen BIG_LOTTO source-native batch."""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from typing import Final

from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.application.legacy_source_native_portfolios_wave9 import (
    CLUSTER_PIVOT_BENCHMARK_METHOD_ID,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE9_METHOD,
    LegacySourceNativeWave9Request,
    generate_legacy_source_native_wave9_portfolio,
)
from lottolab.application.strategy_preserving_20_ticket import Ticket

SOURCE_NATIVE_WAVE40_PROTOCOL = "legacy_source_native_wave40/v1"
DEFAULT_SOURCE_NATIVE_WAVE40_USER_SEED = "biglotto-full-universe-source-native-wave40-v1"
PORTFOLIO_METHOD_ID = "tools/backtest_biglotto_portfolio.py"
SUPPORTED_SOURCE_NATIVE_WAVE40_METHODS = (PORTFOLIO_METHOD_ID,)
SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE40_METHOD: Final = {
    PORTFOLIO_METHOD_ID: ("0b8100ce7ac82678ce3bda9068368a144d86b355ef9f8eb29ba677ba19e70bd5"),
}
FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE40_METHOD: Final = {
    PORTFOLIO_METHOD_ID: (
        (
            CLUSTER_PIVOT_BENCHMARK_METHOD_ID,
            SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE9_METHOD[CLUSTER_PIVOT_BENCHMARK_METHOD_ID],
        ),
    ),
}
MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE40_METHOD: Final = {
    PORTFOLIO_METHOD_ID: 100,
}
NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE40_METHOD: Final = {
    PORTFOLIO_METHOD_ID: 4,
}
NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE40_METHOD: Final = {
    PORTFOLIO_METHOD_ID: (
        "THREE_CLUSTER_PIVOT_CORE_TICKETS_THEN_NONDUPLICATE_TOP_HYBRID_"
        "TICKET_THEN_AT_MOST_ONE_NONDUPLICATE_WINDOW50_FILL_TICKET_"
        "TRUNCATED_TO_FOUR"
    ),
}
SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE40_METHOD: Final = {
    PORTFOLIO_METHOD_ID: (
        "cluster_pivot_3bet_core",
        "cluster_pivot_hybrid_num_bets_1_auxiliary",
        "cluster_pivot_window50_num_bets_1_fill",
    ),
}
SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE40_METHOD: Final = {
    PORTFOLIO_METHOD_ID: 3,
}
SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE40_METHOD: Final = {
    PORTFOLIO_METHOD_ID: "OLDEST_FIRST",
}
SOURCE_HISTORY_ORDER_DETAIL_BY_SOURCE_NATIVE_WAVE40_METHOD: Final = {
    PORTFOLIO_METHOD_ID: ("GET_ALL_DRAWS_ORDER_BY_DATE_ASC_THEN_STRICT_PREFIX_BEFORE_TARGET"),
}


class LegacySourceNativeWave40Error(ValueError):
    """A request cannot satisfy the fortieth source-native contract."""


class LegacySourceNativeWave40SourceError(LegacySourceNativeWave40Error):
    """The frozen source emitted no legal native portfolio."""

    def __init__(self, reason_code: str) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code


@dataclass(frozen=True, slots=True)
class LegacySourceNativeWave40Request:
    legacy_method_id: str
    target_draw_number: str
    history: tuple[LegacyHistoryDraw, ...]
    replicate_id: int = 0
    user_seed: str | int = DEFAULT_SOURCE_NATIVE_WAVE40_USER_SEED


@dataclass(frozen=True, slots=True)
class LegacySourceNativeWave40Metadata:
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
    source_history_order_detail: str
    candidate_k: None
    native_ticket_count: int
    native_ticket_count_semantics: str
    native_ticket_order: str
    native_duplicate_ticket_count: int
    combination_count: None
    source_method_combination_count: int
    combination_members: tuple[str, ...]
    source_candidate_ticket_counts: tuple[int, ...]
    source_duplicate_suppression_results: tuple[str, ...]
    frozen_support_artifacts: tuple[tuple[str, str], ...]

    def canonical_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class LegacySourceNativeWave40Result:
    tickets: tuple[Ticket, ...]
    metadata: LegacySourceNativeWave40Metadata


def _validate_request(request: LegacySourceNativeWave40Request) -> None:
    if request.legacy_method_id not in SUPPORTED_SOURCE_NATIVE_WAVE40_METHODS:
        raise LegacySourceNativeWave40Error("unsupported frozen source-native wave-40 method")
    if (
        type(request.target_draw_number) is not str
        or not request.target_draw_number
        or type(request.replicate_id) is not int
        or request.replicate_id < 0
        or type(request.user_seed) not in (str, int)
    ):
        raise LegacySourceNativeWave40Error("invalid frozen source-native wave-40 request")
    minimum = MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE40_METHOD[request.legacy_method_id]
    if len(request.history) < minimum:
        raise LegacySourceNativeWave40Error(f"method requires at least {minimum} history draws")
    seen: set[str] = set()
    for draw in request.history:
        if (
            not draw.draw_number
            or draw.draw_number == request.target_draw_number
            or draw.draw_number in seen
            or len(draw.numbers) != 6
            or len(set(draw.numbers)) != 6
            or any(type(number) is not int or not 1 <= number <= 49 for number in draw.numbers)
        ):
            raise LegacySourceNativeWave40Error("causal history draw identities are invalid")
        seen.add(draw.draw_number)


def _seed(
    request: LegacySourceNativeWave40Request,
) -> tuple[str, str, int]:
    material = "|".join(
        (
            SOURCE_NATIVE_WAVE40_PROTOCOL,
            request.legacy_method_id,
            SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE40_METHOD[request.legacy_method_id],
            request.target_draw_number,
            str(request.replicate_id),
            str(request.user_seed),
        )
    )
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return material, digest, int(digest, 16)


def _source_ordered_portfolio(
    request: LegacySourceNativeWave40Request,
) -> tuple[tuple[Ticket, ...], tuple[str, ...]]:
    support = generate_legacy_source_native_wave9_portfolio(
        LegacySourceNativeWave9Request(
            legacy_method_id=CLUSTER_PIVOT_BENCHMARK_METHOD_ID,
            target_draw_number=request.target_draw_number,
            history=request.history,
            replicate_id=request.replicate_id,
            user_seed=request.user_seed,
        )
    )
    candidate_counts = support.metadata.source_candidate_ticket_counts
    if candidate_counts != (1, 2, 3, 4, 2, 3, 4):
        raise LegacySourceNativeWave40SourceError("FROZEN_SUPPORT_CONFIGURATION_LAYOUT_MISMATCH")

    offsets: list[int] = []
    offset = 0
    for count in candidate_counts:
        offsets.append(offset)
        offset += count
    core = list(support.tickets[offsets[2] : offsets[2] + 3])
    auxiliary = support.tickets[offsets[5]]
    fill = support.tickets[offsets[4]]

    decisions: list[str] = []
    if auxiliary not in core:
        core.append(auxiliary)
        decisions.append("AUXILIARY_APPENDED")
    else:
        decisions.append("AUXILIARY_DUPLICATE_SUPPRESSED")
    if len(core) < 4:
        if fill not in core:
            core.append(fill)
            decisions.append("WINDOW50_FILL_APPENDED")
        else:
            decisions.append("WINDOW50_FILL_DUPLICATE_STOPPED")
    else:
        decisions.append("WINDOW50_FILL_NOT_NEEDED")
    return tuple(core[:4]), tuple(decisions)


def generate_legacy_source_native_wave40_portfolio(
    request: LegacySourceNativeWave40Request,
) -> LegacySourceNativeWave40Result:
    """Reproduce the frozen deterministic 3+1 Cluster Pivot portfolio."""

    _validate_request(request)
    seed_material, seed_digest, seed_integer = _seed(request)
    tickets, decisions = _source_ordered_portfolio(request)
    if not tickets:
        raise LegacySourceNativeWave40SourceError("FROZEN_SOURCE_NO_NATIVE_TICKETS")
    return LegacySourceNativeWave40Result(
        tickets=tickets,
        metadata=LegacySourceNativeWave40Metadata(
            protocol=SOURCE_NATIVE_WAVE40_PROTOCOL,
            legacy_method_id=request.legacy_method_id,
            source_sha256=(SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE40_METHOD[request.legacy_method_id]),
            target_draw_number=request.target_draw_number,
            replicate_id=request.replicate_id,
            user_seed=request.user_seed,
            seed_material=seed_material,
            seed_digest=seed_digest,
            seed_integer=seed_integer,
            random_protocol="NONE_DETERMINISTIC_NATIVE_SELECTION",
            randomness_used=False,
            randomness_reproduction=("SOURCE_NATIVE_PORTFOLIO_IGNORES_SEEDED_RANDOM_BASELINE"),
            history_draw_count=len(request.history),
            history_first_draw_number=request.history[0].draw_number,
            history_cutoff_draw_number=request.history[-1].draw_number,
            source_history_order=(
                SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE40_METHOD[request.legacy_method_id]
            ),
            source_history_order_detail=(
                SOURCE_HISTORY_ORDER_DETAIL_BY_SOURCE_NATIVE_WAVE40_METHOD[request.legacy_method_id]
            ),
            candidate_k=None,
            native_ticket_count=len(tickets),
            native_ticket_count_semantics=(
                NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE40_METHOD[request.legacy_method_id]
            ),
            native_ticket_order=("CORE_THREE_IN_SOURCE_ORDER_THEN_AUXILIARY_OR_WINDOW50_FILL"),
            native_duplicate_ticket_count=(len(tickets) - len(set(tickets))),
            combination_count=None,
            source_method_combination_count=(
                SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE40_METHOD[request.legacy_method_id]
            ),
            combination_members=(
                SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE40_METHOD[request.legacy_method_id]
            ),
            source_candidate_ticket_counts=(3, 1, 1),
            source_duplicate_suppression_results=decisions,
            frozen_support_artifacts=(
                FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE40_METHOD[request.legacy_method_id]
            ),
        ),
    )


__all__ = [
    "DEFAULT_SOURCE_NATIVE_WAVE40_USER_SEED",
    "FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE40_METHOD",
    "MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE40_METHOD",
    "NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE40_METHOD",
    "NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE40_METHOD",
    "PORTFOLIO_METHOD_ID",
    "SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE40_METHOD",
    "SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE40_METHOD",
    "SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE40_METHOD",
    "SOURCE_NATIVE_WAVE40_PROTOCOL",
    "SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE40_METHOD",
    "SUPPORTED_SOURCE_NATIVE_WAVE40_METHODS",
    "LegacySourceNativeWave40Error",
    "LegacySourceNativeWave40Metadata",
    "LegacySourceNativeWave40Request",
    "LegacySourceNativeWave40Result",
    "LegacySourceNativeWave40SourceError",
    "generate_legacy_source_native_wave40_portfolio",
]
