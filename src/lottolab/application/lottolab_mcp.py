"""Generic, read-only LottoLab historical query service.

This module is the application boundary used by the LottoLab MCP adapter.  It
does not know about MCP transport, SQLite, database paths, or SQL.  The
injected repositories are the existing read-only query ports, while lottery
rules and prize evaluation continue to come from the canonical domain.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Protocol, cast

from lottolab.application.biglotto_multi_ticket_records import (
    B649_HISTORY_WINDOWS,
    B649_PREFIX_COUNTS,
    B649_SUCCESS_CRITERIA,
    B649HistoryWindow,
    B649MultiTicketRecord,
    B649MultiTicketRecordDataset,
)
from lottolab.application.draw_data import DrawRecord
from lottolab.application.historical_prefix_success_windows import (
    HistoricalPrefixSuccessCriterion,
)
from lottolab.application.historical_queries import (
    HistoricalDrawIdentity,
    HistoricalPortfolioRecord,
    HistoricalReplayQuery,
    HistoricalResultsUnavailableError,
    HistoricalRunQuery,
    HistoricalRunSummary,
)
from lottolab.application.p638_historical import (
    P638HistoricalResultsUnavailableError,
    P638RankingRecord,
    P638ReplayQuery,
    P638ReplayRecord,
    P638RunSummary,
    P638StrategyRecord,
)
from lottolab.application.ports import (
    B649MultiTicketRecordReaderFactory,
    DrawDataRepositoryFactory,
    HistoricalResultQueryRepository,
    HistoricalResultQueryRepositoryFactory,
    P638CurrentRankingQueryRepositoryFactory,
    P638HistoricalQueryRepository,
    P638HistoricalQueryRepositoryFactory,
    T539HistoricalQueryRepository,
    T539HistoricalQueryRepositoryFactory,
)
from lottolab.application.t539_historical import (
    T539HistoricalResultsUnavailableError,
    T539RankingRecord,
    T539ReplayQuery,
    T539ReplayRecord,
    T539RunSummary,
    T539StrategyRecord,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.historical_results import HistoricalLotteryType
from lottolab.domain.lottery_rules import (
    BIG_LOTTO_RULE_CONTRACT,
    LOTTERY_RULE_CONTRACTS,
    LotteryRuleContract,
    resolve_lottery_rule_contract,
)
from lottolab.domain.prize_evaluation import (
    LOTTERY_PRIZE_EVALUATOR,
    PrizeEvaluationResult,
)
from lottolab.domain.strategy_success_evaluation import WindowKind
from lottolab.domain.strategy_success_measurement import (
    DEFAULT_WINDOW_POLICY,
)

HISTORICAL_RESULTS_NOT_CONFIGURED = "HISTORICAL_RESULTS_NOT_CONFIGURED"
HISTORICAL_RESULTS_UNAVAILABLE = "HISTORICAL_RESULTS_UNAVAILABLE"
SCHEMA_MISMATCH = "SCHEMA_MISMATCH"
STORAGE_UNAVAILABLE = "STORAGE_UNAVAILABLE"
AUTHORITY_UNRESOLVED = "AUTHORITY_UNRESOLVED"
INVALID_LOTTERY_TYPE = "INVALID_LOTTERY_TYPE"
STRATEGY_NOT_FOUND = "STRATEGY_NOT_FOUND"
RUN_NOT_FOUND = "RUN_NOT_FOUND"
AUTHORITY_NOT_FOUND = "AUTHORITY_NOT_FOUND"
MULTIPLE_AUTHORITIES_REQUIRES_SELECTION = "MULTIPLE_AUTHORITIES_REQUIRES_SELECTION"
INVALID_WINDOW = "INVALID_WINDOW"
INVALID_CRITERION = "INVALID_CRITERION"
INVALID_MATCH_THRESHOLD = "INVALID_MATCH_THRESHOLD"
OFFICIAL_PRIZE_EVIDENCE_UNAVAILABLE = "OFFICIAL_PRIZE_EVIDENCE_UNAVAILABLE"
EVIDENCE_UNAVAILABLE = "EVIDENCE_UNAVAILABLE"
INVALID_STATUS = "INVALID_STATUS"
INVALID_ARGUMENTS = "INVALID_ARGUMENTS"

_MAX_PAGE_SIZE = 200
_FULL_TICKET_COUNT = 20
_SUPPORTED_RUN_STATUS = "COMPLETED"
_ANY_OFFICIAL_PRIZE = "ANY_OFFICIAL_PRIZE"
_B649_DEFAULT_PREFIX_COUNT = max(B649_PREFIX_COUNTS)
_B649_CRITERION_BY_THRESHOLD = {
    3: "M3_PLUS",
    4: "M4_PLUS",
    5: "M5_PLUS",
    6: "M6",
}

_CURRENT_WINDOW_ALIASES: dict[str, tuple[str, int | None]] = {
    "FULL_HISTORY": ("FULL_HISTORY", None),
    "FULL": ("FULL_HISTORY", None),
    "LONG": ("LONG", 750),
    "LONG_750": ("LONG", 750),
    "RECENT_750": ("LONG", 750),
    "MEDIUM": ("MEDIUM", 300),
    "MEDIUM_300": ("MEDIUM", 300),
    "RECENT_300": ("MEDIUM", 300),
    "SHORT": ("SHORT", 50),
    "SHORT_50": ("SHORT", 50),
    "RECENT_50": ("SHORT", 50),
}


class StrategyNameResolver(Protocol):
    def __call__(self, strategy_id: str) -> str | None:
        """Return the canonical display name when the registry knows it."""


class HistoricalDrawReader(Protocol):
    def get_draw(self, run_id: str, draw_number: str) -> HistoricalDrawIdentity | None:
        """Return one committed draw from a completed run, when supported."""


@dataclass(frozen=True, slots=True)
class ReadOnlyAuthorityDescriptor:
    """Sanitized logical identity for one registry-selected authority."""

    authority_id: str
    capability: str
    lottery_type: str
    status: str
    schema: str
    run_id: str | None = None
    immutable: bool = False
    resolved: bool = False
    strategy_count: int | None = None
    draw_count: int | None = None
    target_count: int | None = None
    ticket_count: int | None = None
    provenance: str = ""

    def public_payload(self) -> dict[str, object]:
        coverage = {
            name: value
            for name, value in (
                ("strategy_count", self.strategy_count),
                ("draw_count", self.draw_count),
                ("target_count", self.target_count),
                ("ticket_count", self.ticket_count),
            )
            if value is not None
        }
        return {
            "authority_id": self.authority_id,
            "capability": self.capability,
            "lottery_type": self.lottery_type,
            "status": self.status,
            "schema": self.schema,
            "run_id": self.run_id,
            "immutable": self.immutable,
            "resolved": self.resolved,
            "coverage": coverage,
            "provenance": self.provenance or "registry-selected logical authority",
        }


class LottoLabMcpQueryError(RuntimeError):
    """A sanitized application error safe to expose through MCP."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: Mapping[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = dict(details) if details is not None else {}

    def as_payload(self) -> dict[str, object]:
        return {
            "error_code": self.code,
            "message": self.message,
            "details": self.details,
        }


@dataclass(frozen=True, slots=True)
class ReadOnlyHistoricalSources:
    """Factories for the exact configured read-only historical authority."""

    generic_factory: HistoricalResultQueryRepositoryFactory | None
    p638_factory: P638HistoricalQueryRepositoryFactory | None = None
    draw_factory: DrawDataRepositoryFactory | None = None
    b649_factory: B649MultiTicketRecordReaderFactory | None = None
    p638_current_factory: P638HistoricalQueryRepositoryFactory | None = None
    p638_ranking_factory: P638CurrentRankingQueryRepositoryFactory | None = None
    t539_factory: T539HistoricalQueryRepositoryFactory | None = None
    authority_descriptors: tuple[ReadOnlyAuthorityDescriptor, ...] = ()


@dataclass(frozen=True, slots=True)
class _StrategyRef:
    strategy_id: str
    display_name: str
    strategy_version: str
    replicate: int | None
    native_ticket_count: int | None
    observation_count: int
    provenance: str | None = None


@dataclass(frozen=True, slots=True)
class _TicketEvidence:
    position: int
    main_numbers: tuple[int, ...]
    special_number: int | None
    main_matches: int
    special_hit: bool
    persisted_prize_tier: str | None = None
    persisted_prize_order: int | None = None
    persisted_prize_amount: int | None = None


@dataclass(frozen=True, slots=True)
class _Observation:
    strategy_id: str
    strategy_version: str
    draw_number: str
    draw_date: str
    target_main_numbers: tuple[int, ...]
    target_special_numbers: tuple[int, ...]
    tickets: tuple[_TicketEvidence, ...]
    status: str
    provenance: str | None = None


def _criterion_values() -> tuple[str, ...]:
    return (*tuple(item.value for item in HistoricalPrefixSuccessCriterion), _ANY_OFFICIAL_PRIZE)


def _window_value(window: WindowKind) -> str:
    return window.value


class LottoLabMcpQueryService:
    """Expose generic historical queries over existing LottoLab read ports."""

    def __init__(
        self,
        sources: ReadOnlyHistoricalSources,
        *,
        strategy_name_resolver: StrategyNameResolver | None = None,
    ) -> None:
        self._sources = sources
        self._strategy_name_resolver = strategy_name_resolver

    def list_lottery_types(self) -> dict[str, object]:
        """List canonical lottery types and logical authority capabilities."""

        items: list[dict[str, object]] = []
        for lottery_type in self._supported_lottery_types():
            capabilities = self._capabilities_for_lottery(lottery_type)
            summaries: tuple[HistoricalRunSummary, ...] = ()
            if self._provider_kind(lottery_type) == "generic" and self._sources.generic_factory:
                try:
                    summaries = self._list_runs(lottery_type)
                except LottoLabMcpQueryError:
                    summaries = ()

            draw_status = self._capability_status("DRAW_DATA")
            if summaries and self._sources.draw_factory is None:
                draw_status = (
                    {"status": "AVAILABLE"}
                    if any(summary.draw_count > 0 for summary in summaries)
                    else {"status": "UNAVAILABLE", "reason": "NO_DRAW_EVIDENCE"}
                )

            historical_capability = self._historical_capability_for(lottery_type)
            historical_status = self._capability_status(historical_capability)
            replay_status = self._replay_capability_status(lottery_type)
            if summaries and historical_status["status"] != "AVAILABLE":
                historical_status = {"status": "AVAILABLE"}
                replay_status = (
                    {"status": "AVAILABLE"}
                    if any(
                        summary.strategy_count > 0 and summary.portfolio_count > 0
                        for summary in summaries
                    )
                    else {"status": "UNAVAILABLE", "reason": "NO_REPLAY_EVIDENCE"}
                )

            items.append(
                {
                    "lottery_type": lottery_type.value,
                    "display_name": lottery_type.value,
                    "draw_data_availability": draw_status,
                    "historical_results_availability": historical_status,
                    "replay_availability": replay_status,
                    "ranking_availability": self._ranking_capability_status(lottery_type),
                    "official_prize_semantics_availability": self._prize_capability(
                        lottery_type
                    ),
                    "authority_capabilities": capabilities,
                    "observed_authority_count": len(summaries),
                }
            )
        return {"lottery_types": items}

    def list_historical_runs(
        self,
        *,
        lottery_type: str,
        strategy_id: str | None = None,
        status: str | None = None,
        authority: str | None = None,
    ) -> dict[str, object]:
        selected_type = self._resolve_lottery_type(lottery_type)
        if status is not None and status != _SUPPORTED_RUN_STATUS:
            raise LottoLabMcpQueryError(
                INVALID_STATUS,
                "status is outside the completed read-only query contract.",
            )
        self._reject_unresolved_authority(authority)
        provider = self._provider_kind(selected_type)
        if provider != "generic":
            return self._provider_list_historical_runs(selected_type, authority)
        self._require_generic_or_unresolved(selected_type, authority)
        summaries = list(self._list_runs(selected_type))
        if authority is not None:
            matching = [item for item in summaries if self._authority_matches(item, authority)]
            if not matching:
                raise self._authority_not_found(selected_type, authority, summaries)
            summaries = matching

        items: list[dict[str, object]] = []
        for summary in summaries:
            refs: tuple[_StrategyRef, ...] | None = None
            if strategy_id is not None:
                refs = self._strategy_refs(selected_type, summary.run_id)
                if not any(ref.strategy_id == strategy_id for ref in refs):
                    continue
            items.append(
                self._run_payload(
                    selected_type,
                    summary,
                    has_strategy_evidence=(
                        bool(refs)
                        if refs is not None
                        else summary.strategy_count > 0
                    ),
                )
            )
        return {
            "lottery_type": selected_type.value,
            "items": items,
            "competing_authorities": [
                self._authority_payload(selected_type, summary) for summary in summaries
            ],
        }

    def get_strategy_window_ranking(
        self,
        *,
        lottery_type: str,
        window: str,
        criterion: str,
        authority: str | None = None,
    ) -> dict[str, object]:
        selected_type = self._resolve_lottery_type(lottery_type)
        self._reject_unresolved_authority(authority)
        provider = self._provider_kind(selected_type)
        if provider != "generic":
            return self._provider_window_ranking(
                selected_type,
                window=window,
                criterion=criterion,
                authority=authority,
            )
        selected_window = self._resolve_window(window)
        self._validate_criterion(selected_type, criterion)
        summary = self._select_authority(selected_type, authority)
        refs = self._strategy_refs(selected_type, summary.run_id)
        rows: list[dict[str, object]] = []
        for ref in refs:
            observations = self._complete_observations(
                selected_type, summary.run_id, ref.strategy_id
            )
            window_observations = self._observations_for_window(observations, selected_window)
            if window_observations is None:
                continue
            metric = self._criterion_metric(selected_type, window_observations, criterion)
            if metric is None:
                continue
            successes, observation_count = metric
            rows.append(
                {
                    "rank": 0,
                    "strategy_id": ref.strategy_id,
                    "display_name": ref.display_name,
                    "lottery_type": selected_type.value,
                    "observation_count": observation_count,
                    "successes": successes,
                    "success_rate": (
                        successes / observation_count if observation_count else None
                    ),
                    "success_rate_exact": {
                        "numerator": successes,
                        "denominator": observation_count,
                    },
                    "window": _window_value(selected_window),
                    "criterion": criterion,
                    "baseline": None,
                    "baseline_delta": None,
                    "authority": self._authority_payload(selected_type, summary),
                }
            )
        rows.sort(
            key=lambda item: (
                -(
                    float(cast(float, item["success_rate"]))
                    if item["success_rate"] is not None
                    else -1.0
                ),
                -cast(int, item["successes"]),
                str(item["strategy_id"]),
            )
        )
        for index, row in enumerate(rows, start=1):
            row["rank"] = index
        if not rows:
            raise LottoLabMcpQueryError(
                EVIDENCE_UNAVAILABLE,
                "the selected authority has no complete evidence for this window.",
                details={
                    "available_windows": self._available_windows_from_refs(
                        selected_type, summary.run_id, refs
                    )
                },
            )
        return {
            "lottery_type": selected_type.value,
            "window": _window_value(selected_window),
            "criterion": criterion,
            "authority": self._authority_payload(selected_type, summary),
            "items": rows,
        }

    def get_strategy_replay_summary(
        self,
        *,
        lottery_type: str,
        strategy_id: str,
        authority: str | None = None,
    ) -> dict[str, object]:
        selected_type = self._resolve_lottery_type(lottery_type)
        self._reject_unresolved_authority(authority)
        provider = self._provider_kind(selected_type)
        if provider != "generic":
            return self._provider_replay_summary(selected_type, strategy_id, authority)
        summary = self._select_authority(selected_type, authority)
        ref = self._require_strategy(selected_type, summary.run_id, strategy_id)
        observations = self._complete_observations(selected_type, summary.run_id, strategy_id)
        authority_payload = self._authority_payload(selected_type, summary)
        if not observations:
            return {
                "strategy": self._strategy_payload(ref, selected_type),
                "lottery_type": selected_type.value,
                "completed_observation_count": 0,
                "hit_distribution": None,
                "official_prize_distribution": None,
                "available_windows": [],
                "available_criteria": [],
                "replay_status": "UNAVAILABLE",
                "provenance": authority_payload["source_provenance"],
                "authority": authority_payload,
                "available_authorities": self._authority_list(selected_type),
                "unavailable_reasons": ["EVIDENCE_UNAVAILABLE"],
            }

        hit_distribution = self._hit_distribution(selected_type, observations)
        prize_distribution = self._prize_distribution(selected_type, observations)
        replay_status = (
            "COMPLETE"
            if all(item.status == "COMPLETE" for item in observations)
            else "PARTIAL"
        )
        return {
            "strategy": self._strategy_payload(ref, selected_type),
            "lottery_type": selected_type.value,
            "completed_observation_count": len(
                {item.draw_number for item in observations}
            ),
            "hit_distribution": hit_distribution,
            "official_prize_distribution": prize_distribution,
            "available_windows": self._available_windows(observations),
            "available_criteria": self._available_criteria(selected_type, observations),
            "replay_status": replay_status,
            "provenance": authority_payload["source_provenance"],
            "authority": authority_payload,
            "available_authorities": self._authority_list(selected_type),
            "unavailable_reasons": [],
        }

    def get_strategy_match_summary(
        self,
        *,
        lottery_type: str,
        strategy_id: str,
        min_main_matches: int = 4,
        authority: str | None = None,
    ) -> dict[str, object]:
        selected_type = self._resolve_lottery_type(lottery_type)
        self._validate_match_threshold(selected_type, min_main_matches)
        self._reject_unresolved_authority(authority)
        provider = self._provider_kind(selected_type)
        if provider != "generic":
            return self._provider_match_summary(
                selected_type,
                strategy_id,
                min_main_matches,
                authority,
            )
        summary = self._select_authority(selected_type, authority)
        ref = self._require_strategy(selected_type, summary.run_id, strategy_id)
        observations = self._complete_observations(selected_type, summary.run_id, strategy_id)
        authority_payload = self._authority_payload(selected_type, summary)
        if not observations:
            return {
                "strategy": self._strategy_payload(ref, selected_type),
                "lottery_type": selected_type.value,
                "min_main_matches": min_main_matches,
                "exact_main_match_distribution": None,
                "threshold_distinct_draw_count": None,
                "threshold_ticket_hit_count": None,
                "best_match": None,
                "authority": authority_payload,
                "unavailable_reason": "EVIDENCE_UNAVAILABLE",
            }

        qualifying_draws: set[str] = set()
        threshold_ticket_count = 0
        distribution: Counter[tuple[int, bool]] = Counter()
        best: tuple[int, bool, _Observation, _TicketEvidence] | None = None
        for observation in observations:
            for ticket in observation.tickets:
                distribution[(ticket.main_matches, ticket.special_hit)] += 1
                if ticket.main_matches >= min_main_matches:
                    qualifying_draws.add(observation.draw_number)
                    threshold_ticket_count += 1
                candidate = (ticket.main_matches, ticket.special_hit, observation, ticket)
                if best is None or self._best_match_key(candidate) < self._best_match_key(best):
                    best = candidate

        return {
            "strategy": self._strategy_payload(ref, selected_type),
            "lottery_type": selected_type.value,
            "min_main_matches": min_main_matches,
            "exact_main_match_distribution": [
                {
                    "main_matches": main_matches,
                    "special_hit": (
                        special_hit if self._has_special_number(selected_type) else None
                    ),
                    "ticket_count": count,
                }
                for (main_matches, special_hit), count in sorted(distribution.items())
            ],
            "threshold_distinct_draw_count": len(qualifying_draws),
            "threshold_ticket_hit_count": threshold_ticket_count,
            "best_match": None if best is None else self._best_match_payload(best),
            "authority": authority_payload,
            "unavailable_reason": None,
        }

    def get_strategies_by_match_threshold(
        self,
        *,
        lottery_type: str,
        min_main_matches: int,
        authority: str | None = None,
        window: str | None = None,
    ) -> dict[str, object]:
        selected_type = self._resolve_lottery_type(lottery_type)
        self._validate_match_threshold(selected_type, min_main_matches)
        self._reject_unresolved_authority(authority)
        provider = self._provider_kind(selected_type)
        if provider != "generic":
            return self._provider_threshold_search(
                selected_type,
                min_main_matches,
                authority,
                window,
            )
        selected_window = None if window is None else self._resolve_window(window)
        summary = self._select_authority(selected_type, authority)
        refs = self._strategy_refs(selected_type, summary.run_id)
        rows: list[dict[str, object]] = []
        for ref in refs:
            observations = self._complete_observations(
                selected_type, summary.run_id, ref.strategy_id
            )
            if selected_window is not None:
                observations = self._observations_for_window(observations, selected_window) or ()
            if not observations:
                continue
            qualifying_draws = {
                observation.draw_number
                for observation in observations
                if any(
                    ticket.main_matches >= min_main_matches
                    for ticket in observation.tickets
                )
            }
            if not qualifying_draws:
                continue
            prize_summary = self._best_prize(selected_type, observations)
            rows.append(
                {
                    "strategy_id": ref.strategy_id,
                    "display_name": ref.display_name,
                    "observation_count": len({item.draw_number for item in observations}),
                    "exact_match_distribution": self._hit_distribution(
                        selected_type, observations
                    ),
                    "threshold_distinct_draw_count": len(qualifying_draws),
                    "threshold_ticket_hit_count": sum(
                        1
                        for observation in observations
                        for ticket in observation.tickets
                        if ticket.main_matches >= min_main_matches
                    ),
                    "highest_main_match_count": max(
                        ticket.main_matches
                        for observation in observations
                        for ticket in observation.tickets
                    ),
                    "best_official_prize": prize_summary,
                    "best_prize_draw": (
                        None if prize_summary is None else prize_summary["draw_number"]
                    ),
                    "authority": self._authority_payload(selected_type, summary),
                }
            )
        rows.sort(
            key=lambda item: (
                -cast(int, item["threshold_distinct_draw_count"]),
                self._prize_sort_key_from_payload(item["best_official_prize"]),
                -cast(int, item["highest_main_match_count"]),
                str(item["strategy_id"]),
            )
        )
        return {
            "lottery_type": selected_type.value,
            "min_main_matches": min_main_matches,
            "window": None if selected_window is None else _window_value(selected_window),
            "authority": self._authority_payload(selected_type, summary),
            "items": rows,
        }

    def get_strategy_best_prize(
        self,
        *,
        lottery_type: str,
        strategy_id: str,
        authority: str | None = None,
    ) -> dict[str, object]:
        selected_type = self._resolve_lottery_type(lottery_type)
        self._reject_unresolved_authority(authority)
        provider = self._provider_kind(selected_type)
        if provider != "generic":
            return self._provider_best_prize(selected_type, strategy_id, authority)
        summary = self._select_authority(selected_type, authority)
        ref = self._require_strategy(selected_type, summary.run_id, strategy_id)
        observations = self._complete_observations(selected_type, summary.run_id, strategy_id)
        authority_payload = self._authority_payload(selected_type, summary)
        if not observations:
            return {
                "strategy": self._strategy_payload(ref, selected_type),
                "lottery_type": selected_type.value,
                "highest_official_prize": None,
                "draw_number": None,
                "draw_date": None,
                "winning_ticket": None,
                "canonical_match_information": None,
                "authority": authority_payload,
                "reason": OFFICIAL_PRIZE_EVIDENCE_UNAVAILABLE,
            }
        best = self._best_prize(selected_type, observations, include_ticket=True)
        return {
            "strategy": self._strategy_payload(ref, selected_type),
            "lottery_type": selected_type.value,
            "highest_official_prize": best["prize"] if best is not None else None,
            "draw_number": best["draw_number"] if best is not None else None,
            "draw_date": best["draw_date"] if best is not None else None,
            "winning_ticket": best["ticket"] if best is not None else None,
            "canonical_match_information": best["match"] if best is not None else None,
            "authority": authority_payload,
            "reason": None if best is not None else "NO_WINNING_PRIZE_OBSERVED",
        }

    def get_draw(
        self,
        *,
        lottery_type: str,
        draw_number: str,
        authority: str | None = None,
    ) -> dict[str, object]:
        selected_type = self._resolve_lottery_type(lottery_type)
        if type(draw_number) is not str or not draw_number:
            raise LottoLabMcpQueryError(EVIDENCE_UNAVAILABLE, "draw_number is invalid.")
        self._reject_unresolved_authority(authority)
        if self._sources.draw_factory is not None or self._provider_kind(
            selected_type
        ) != "generic":
            return self._provider_draw(selected_type, draw_number, authority)
        summary = self._select_authority(selected_type, authority)
        draw: dict[str, object] | None = None
        if selected_type is LotteryType.POWER_LOTTO and self._sources.p638_factory is not None:
            try:
                record = self._p638_repository().get_draw(summary.run_id, draw_number)
            except (P638HistoricalResultsUnavailableError, LottoLabMcpQueryError):
                record = None
            if record is not None:
                draw = {
                    "draw_number": record.draw_number,
                    "draw_date": record.draw_date,
                    "main_numbers": list(record.winning_zone1_numbers),
                    "special_numbers": [],
                    "secondary_numbers": [record.winning_zone2_number],
                }
        if draw is None:
            repository = cast(HistoricalDrawReader, self._generic_repository())
            record = repository.get_draw(summary.run_id, draw_number)
            if record is not None:
                draw = self._draw_identity_payload(selected_type, record)
        if draw is None:
            raise LottoLabMcpQueryError(
                EVIDENCE_UNAVAILABLE,
                "the requested canonical draw is unavailable.",
                details={"lottery_type": selected_type.value, "draw_number": draw_number},
            )
        draw["lottery_type"] = selected_type.value
        draw["source_metadata"] = {
            "authority": self._authority_payload(selected_type, summary),
            "rule_contract_version": self._rule_contract(selected_type).contract_version,
        }
        return draw

    def _provider_kind(self, lottery_type: LotteryType) -> str:
        if lottery_type is LotteryType.BIG_LOTTO and self._sources.b649_factory is not None:
            return "b649"
        if lottery_type is LotteryType.POWER_LOTTO and (
            self._sources.p638_current_factory is not None
            or self._sources.p638_ranking_factory is not None
        ):
            return "power"
        if lottery_type is LotteryType.DAILY_539 and self._sources.t539_factory is not None:
            return "daily"
        return "generic"

    def _descriptor_for(self, capability: str) -> ReadOnlyAuthorityDescriptor | None:
        return next(
            (
                descriptor
                for descriptor in self._sources.authority_descriptors
                if descriptor.capability == capability
            ),
            None,
        )

    def _capabilities_for_lottery(self, lottery_type: LotteryType) -> list[dict[str, object]]:
        return [
            {
                **descriptor.public_payload(),
                "availability": self._capability_status(descriptor.capability),
            }
            for descriptor in self._sources.authority_descriptors
            if descriptor.lottery_type in {lottery_type.value, "MULTI_LOTTERY"}
        ]

    def _capability_status(self, capability: str) -> dict[str, object]:
        available = (
            capability == "DRAW_DATA" and self._sources.draw_factory is not None
        ) or (
            capability == "BIG_LOTTO_PACKAGED_RECORDS"
            and self._sources.b649_factory is not None
        ) or (
            capability == "POWER_LOTTO_CURRENT_REPLAY"
            and self._sources.p638_current_factory is not None
        ) or (
            capability == "POWER_LOTTO_CURRENT_RANKING"
            and self._sources.p638_ranking_factory is not None
        ) or (
            capability == "DAILY_539_HISTORICAL" and self._sources.t539_factory is not None
        )
        descriptor = self._descriptor_for(capability)
        if available:
            return {
                "status": "AVAILABLE",
                "authority_id": None if descriptor is None else descriptor.authority_id,
            }
        if descriptor is not None and descriptor.status == "UNRESOLVED":
            return {
                "status": "UNAVAILABLE",
                "reason": AUTHORITY_UNRESOLVED,
                "authority_id": descriptor.authority_id,
            }
        return {
            "status": "UNAVAILABLE",
            "reason": STORAGE_UNAVAILABLE,
            "authority_id": None if descriptor is None else descriptor.authority_id,
        }

    def _historical_capability_for(self, lottery_type: LotteryType) -> str:
        if lottery_type is LotteryType.BIG_LOTTO:
            return "BIG_LOTTO_PACKAGED_RECORDS"
        if lottery_type is LotteryType.POWER_LOTTO:
            return "POWER_LOTTO_CURRENT_REPLAY"
        return "DAILY_539_HISTORICAL"

    def _replay_capability_status(self, lottery_type: LotteryType) -> dict[str, object]:
        if lottery_type is LotteryType.BIG_LOTTO:
            return self._capability_status("BIG_LOTTO_PACKAGED_RECORDS")
        if lottery_type is LotteryType.POWER_LOTTO:
            current = self._capability_status("POWER_LOTTO_CURRENT_REPLAY")
            if current["status"] == "AVAILABLE":
                return current
            return self._capability_status("POWER_LOTTO_HISTORICAL_RESULTS_V2")
        return self._capability_status("DAILY_539_HISTORICAL")

    def _ranking_capability_status(self, lottery_type: LotteryType) -> dict[str, object]:
        if lottery_type is LotteryType.POWER_LOTTO:
            return self._capability_status("POWER_LOTTO_CURRENT_RANKING")
        return self._capability_status(self._historical_capability_for(lottery_type))

    def _reject_unresolved_authority(self, authority: str | None) -> None:
        if authority is None:
            return
        if type(authority) is not str or not authority or "/" in authority or "\\" in authority:
            raise LottoLabMcpQueryError(
                INVALID_ARGUMENTS,
                "authority must be a logical authority identity.",
            )
        descriptor = next(
            (
                item
                for item in self._sources.authority_descriptors
                if item.status == "UNRESOLVED"
                and authority in {item.authority_id, item.capability}
            ),
            None,
        )
        if descriptor is not None:
            raise LottoLabMcpQueryError(
                AUTHORITY_UNRESOLVED,
                "the requested authority is intentionally unresolved.",
                details={"capability": descriptor.capability},
            )

    def _require_generic_or_unresolved(
        self, lottery_type: LotteryType, authority: str | None
    ) -> None:
        if self._sources.generic_factory is not None:
            return
        unresolved = [
            descriptor.capability
            for descriptor in self._sources.authority_descriptors
            if descriptor.status == "UNRESOLVED"
            and descriptor.lottery_type in {lottery_type.value, "MULTI_LOTTERY"}
        ]
        if authority is not None:
            self._reject_unresolved_authority(authority)
        if unresolved:
            raise LottoLabMcpQueryError(
                AUTHORITY_UNRESOLVED,
                "no accepted authority is available for this lottery type.",
                details={"capabilities": unresolved},
            )
        raise LottoLabMcpQueryError(
            EVIDENCE_UNAVAILABLE,
            "no read-only evidence provider is available for this lottery type.",
        )

    def _provider_authority_payload(
        self,
        capability: str,
        *,
        run_id: str | None = None,
        coverage: Mapping[str, object] | None = None,
    ) -> dict[str, object]:
        descriptor = self._descriptor_for(capability)
        if descriptor is None:
            payload: dict[str, object] = {
                "authority_id": capability,
                "capability": capability,
                "lottery_type": "MULTI_LOTTERY",
                "status": "CANONICAL_CURRENT",
                "schema": "APPLICATION_READ_ONLY_PROJECTION",
                "run_id": run_id,
                "immutable": True,
                "resolved": True,
                "coverage": {},
                "provenance": "injected read-only test authority",
            }
        else:
            payload = descriptor.public_payload()
            if run_id is not None:
                payload["run_id"] = run_id
        if coverage is not None:
            payload["coverage"] = dict(coverage)
        return payload

    def _select_provider_authority(
        self,
        capability: str,
        authority: str | None,
        *,
        run_id: str | None = None,
    ) -> None:
        descriptor = self._descriptor_for(capability)
        allowed = {capability}
        if descriptor is not None:
            allowed.add(descriptor.authority_id)
        if run_id is not None:
            allowed.add(run_id)
        if authority is not None and authority not in allowed:
            raise LottoLabMcpQueryError(
                AUTHORITY_NOT_FOUND,
                "the requested logical authority was not found.",
                details={"capability": capability},
            )

    def _b649_dataset(self) -> B649MultiTicketRecordDataset:
        factory = self._sources.b649_factory
        if factory is None:
            raise LottoLabMcpQueryError(
                AUTHORITY_UNRESOLVED,
                "BIG_LOTTO packaged evidence is unavailable.",
                details={"capability": "BIG_LOTTO_PACKAGED_RECORDS"},
            )
        try:
            return factory().read()
        except LottoLabMcpQueryError:
            raise
        except Exception as exc:
            raise LottoLabMcpQueryError(
                EVIDENCE_UNAVAILABLE,
                "BIG_LOTTO packaged evidence is unavailable.",
            ) from exc

    def _p638_current_repository(self) -> P638HistoricalQueryRepository:
        factory = self._sources.p638_current_factory
        if factory is None:
            raise LottoLabMcpQueryError(
                AUTHORITY_UNRESOLVED,
                "POWER_LOTTO current replay evidence is unavailable.",
                details={"capability": "POWER_LOTTO_CURRENT_REPLAY"},
            )
        try:
            return factory()
        except LottoLabMcpQueryError:
            raise
        except Exception as exc:
            raise LottoLabMcpQueryError(
                STORAGE_UNAVAILABLE,
                "POWER_LOTTO current replay storage is unavailable.",
            ) from exc

    def _t539_repository(self) -> T539HistoricalQueryRepository:
        factory = self._sources.t539_factory
        if factory is None:
            raise LottoLabMcpQueryError(
                AUTHORITY_UNRESOLVED,
                "DAILY_539 historical evidence is unavailable.",
                details={"capability": "DAILY_539_HISTORICAL"},
            )
        try:
            return factory()
        except LottoLabMcpQueryError:
            raise
        except Exception as exc:
            raise LottoLabMcpQueryError(
                STORAGE_UNAVAILABLE,
                "DAILY_539 historical storage is unavailable.",
            ) from exc

    def _p638_current_run(
        self, authority: str | None
    ) -> P638RunSummary:
        try:
            page = self._p638_current_repository().list_runs(
                limit=_MAX_PAGE_SIZE, offset=0
            )
        except P638HistoricalResultsUnavailableError as exc:
            raise LottoLabMcpQueryError(
                STORAGE_UNAVAILABLE,
                "POWER_LOTTO current replay storage is unavailable.",
            ) from exc
        except LottoLabMcpQueryError:
            raise
        except Exception as exc:
            raise LottoLabMcpQueryError(
                STORAGE_UNAVAILABLE,
                "POWER_LOTTO current replay storage is unavailable.",
            ) from exc
        descriptor = self._descriptor_for("POWER_LOTTO_CURRENT_REPLAY")
        selected_id = None if descriptor is None else descriptor.run_id
        if authority is not None:
            self._select_provider_authority(
                "POWER_LOTTO_CURRENT_REPLAY", authority, run_id=selected_id
            )
        if selected_id is not None:
            selected = next((item for item in page.items if item.run_id == selected_id), None)
            if selected is None:
                raise LottoLabMcpQueryError(
                    EVIDENCE_UNAVAILABLE,
                    "the registered POWER_LOTTO current replay run is unavailable.",
                    details={"capability": "POWER_LOTTO_CURRENT_REPLAY"},
                )
            return selected
        if len(page.items) == 1:
            return page.items[0]
        if not page.items:
            raise LottoLabMcpQueryError(
                EVIDENCE_UNAVAILABLE,
                "POWER_LOTTO current replay has no completed run.",
            )
        raise LottoLabMcpQueryError(
            MULTIPLE_AUTHORITIES_REQUIRES_SELECTION,
            "multiple POWER_LOTTO current replay runs exist; select one explicitly.",
            details={"capability": "POWER_LOTTO_CURRENT_REPLAY"},
        )

    def _t539_run(self, authority: str | None) -> T539RunSummary:
        try:
            page = self._t539_repository().list_runs(limit=_MAX_PAGE_SIZE, offset=0)
        except T539HistoricalResultsUnavailableError as exc:
            raise LottoLabMcpQueryError(
                STORAGE_UNAVAILABLE,
                "DAILY_539 historical storage is unavailable.",
            ) from exc
        except LottoLabMcpQueryError:
            raise
        except Exception as exc:
            raise LottoLabMcpQueryError(
                STORAGE_UNAVAILABLE,
                "DAILY_539 historical storage is unavailable.",
            ) from exc
        descriptor = self._descriptor_for("DAILY_539_HISTORICAL")
        selected_id = None if descriptor is None else descriptor.run_id
        if authority is not None:
            self._select_provider_authority(
                "DAILY_539_HISTORICAL", authority, run_id=selected_id
            )
        if selected_id is not None:
            selected = next((item for item in page.items if item.run_id == selected_id), None)
            if selected is None:
                raise LottoLabMcpQueryError(
                    EVIDENCE_UNAVAILABLE,
                    "the registered DAILY_539 historical run is unavailable.",
                    details={"capability": "DAILY_539_HISTORICAL"},
                )
            return selected
        if len(page.items) == 1:
            return page.items[0]
        if not page.items:
            raise LottoLabMcpQueryError(
                EVIDENCE_UNAVAILABLE,
                "DAILY_539 historical evidence has no completed run.",
            )
        raise LottoLabMcpQueryError(
            MULTIPLE_AUTHORITIES_REQUIRES_SELECTION,
            "multiple DAILY_539 historical runs exist; select one explicitly.",
            details={"capability": "DAILY_539_HISTORICAL"},
        )

    def _provider_list_historical_runs(
        self, lottery_type: LotteryType, authority: str | None
    ) -> dict[str, object]:
        provider = self._provider_kind(lottery_type)
        if provider == "b649":
            self._select_provider_authority("BIG_LOTTO_PACKAGED_RECORDS", authority)
            dataset = self._b649_dataset()
            strategy_count = len({record.strategy_id for record in dataset.records})
            authority_payload = self._provider_authority_payload(
                "BIG_LOTTO_PACKAGED_RECORDS",
                coverage={
                    "strategy_count": strategy_count,
                    "record_count": len(dataset.records),
                    "source_report_count": dataset.source_report_count,
                },
            )
            item = {
                **authority_payload,
                "available_windows": [item.value for item in B649_HISTORY_WINDOWS],
                "available_criteria": [item.value for item in B649_SUCCESS_CRITERIA]
                + [_ANY_OFFICIAL_PRIZE],
            }
            if authority is not None:
                return {
                    "lottery_type": lottery_type.value,
                    "items": [item],
                    "competing_authorities": [],
                }
            return {
                "lottery_type": lottery_type.value,
                "items": [item],
                "competing_authorities": [],
            }
        if provider == "power":
            run = self._p638_current_run(authority)
            authority_payload = self._provider_authority_payload(
                "POWER_LOTTO_CURRENT_REPLAY",
                run_id=run.run_id,
                coverage={
                    "strategy_count": run.strategy_count,
                    "draw_count": run.draw_count,
                    "target_count": run.complete_target_count + run.excluded_target_count,
                    "ticket_count": run.ticket_count,
                },
            )
            item = {
                **authority_payload,
                "status": run.status,
                "available_windows": [window.value for window in WindowKind],
                "available_criteria": self._available_criteria_for_rule(lottery_type),
            }
            return {
                "lottery_type": lottery_type.value,
                "items": [item],
                "competing_authorities": [],
            }
        if provider == "daily":
            run = self._t539_run(authority)
            authority_payload = self._provider_authority_payload(
                "DAILY_539_HISTORICAL",
                run_id=run.run_id,
                coverage={
                    "strategy_count": run.strategy_count,
                    "draw_count": run.draw_count,
                    "target_count": run.eligible_target_count,
                    "ticket_count": run.ticket_count,
                },
            )
            item = {
                **authority_payload,
                "status": run.status,
                "available_windows": [window.value for window in WindowKind],
                "available_criteria": self._available_criteria_for_rule(lottery_type),
            }
            return {
                "lottery_type": lottery_type.value,
                "items": [item],
                "competing_authorities": [],
            }
        raise LottoLabMcpQueryError(
            EVIDENCE_UNAVAILABLE,
            "the selected provider is unavailable.",
        )

    def _provider_strategy_refs(
        self, lottery_type: LotteryType, run_id: str
    ) -> tuple[_StrategyRef, ...]:
        provider = self._provider_kind(lottery_type)
        if provider == "b649":
            rows = self._b649_dataset().records
            selected: dict[str, B649MultiTicketRecord] = {}
            for row in rows:
                selected.setdefault(row.strategy_id, row)
            return tuple(
                _StrategyRef(
                    strategy_id=row.strategy_id,
                    display_name=row.strategy_id,
                    strategy_version=row.strategy_version,
                    replicate=None,
                    native_ticket_count=row.prefix_count,
                    observation_count=row.successful_execution_count or 0,
                    provenance=row.authority_mode,
                )
                for row in sorted(selected.values(), key=lambda item: item.strategy_id)
            )
        if provider == "power":
            try:
                page = self._p638_current_repository().list_strategies(
                    run_id, limit=_MAX_PAGE_SIZE, offset=0
                )
            except P638HistoricalResultsUnavailableError as exc:
                raise LottoLabMcpQueryError(
                    STORAGE_UNAVAILABLE,
                    "POWER_LOTTO current replay storage is unavailable.",
                ) from exc
            except Exception as exc:
                raise LottoLabMcpQueryError(
                    STORAGE_UNAVAILABLE,
                    "POWER_LOTTO current replay storage is unavailable.",
                ) from exc
            if page is None:
                return ()
            return tuple(self._p638_strategy_ref(item) for item in page.items)
        if provider == "daily":
            try:
                page = self._t539_repository().list_strategies(
                    run_id, limit=_MAX_PAGE_SIZE, offset=0
                )
            except T539HistoricalResultsUnavailableError as exc:
                raise LottoLabMcpQueryError(
                    STORAGE_UNAVAILABLE,
                    "DAILY_539 historical storage is unavailable.",
                ) from exc
            except Exception as exc:
                raise LottoLabMcpQueryError(
                    STORAGE_UNAVAILABLE,
                    "DAILY_539 historical storage is unavailable.",
                ) from exc
            if page is None:
                return ()
            return tuple(self._t539_strategy_ref(item) for item in page.items)
        return ()

    @staticmethod
    def _t539_strategy_ref(item: T539StrategyRecord) -> _StrategyRef:
        return _StrategyRef(
            strategy_id=item.strategy_id,
            display_name=item.strategy_id,
            strategy_version=item.strategy_version,
            replicate=None,
            native_ticket_count=item.native_ticket_count,
            observation_count=item.processed_target_draw_count,
        )

    def _provider_strategy_ref(
        self, lottery_type: LotteryType, run_id: str, strategy_id: str
    ) -> _StrategyRef:
        for ref in self._provider_strategy_refs(lottery_type, run_id):
            if ref.strategy_id == strategy_id:
                return ref
        raise LottoLabMcpQueryError(
            STRATEGY_NOT_FOUND,
            "strategy_id was not found in the selected authority.",
            details={"strategy_id": strategy_id},
        )

    def _provider_window(
        self, lottery_type: LotteryType, value: str
    ) -> tuple[str, int | None]:
        if type(value) is not str or not value:
            raise LottoLabMcpQueryError(
                INVALID_WINDOW,
                "window is outside the canonical provider set.",
            )
        if lottery_type is LotteryType.BIG_LOTTO:
            if value in {item.value for item in B649_HISTORY_WINDOWS}:
                return value, {
                    "FULL": None,
                    "RECENT_750": 750,
                    "RECENT_300": 300,
                    "RECENT_50": 50,
                }[value]
            aliases = {
                "FULL_HISTORY": "FULL",
                "LONG": "RECENT_750",
                "LONG_750": "RECENT_750",
                "MEDIUM": "RECENT_300",
                "MEDIUM_300": "RECENT_300",
                "SHORT": "RECENT_50",
                "SHORT_50": "RECENT_50",
            }
            if value in aliases:
                selected = aliases[value]
                return selected, {
                    "FULL": None,
                    "RECENT_750": 750,
                    "RECENT_300": 300,
                    "RECENT_50": 50,
                }[selected]
        else:
            selected = _CURRENT_WINDOW_ALIASES.get(value)
            if selected is not None:
                return selected
        raise LottoLabMcpQueryError(
            INVALID_WINDOW,
            "window is outside the canonical provider set.",
            details={"lottery_type": lottery_type.value},
        )

    def _provider_window_observations(
        self, observations: tuple[_Observation, ...], window_count: int | None
    ) -> tuple[_Observation, ...] | None:
        ordered = tuple(sorted(observations, key=self._observation_sort_key))
        if window_count is None:
            return ordered or None
        draw_keys = tuple(
            sorted(
                {item.draw_number for item in ordered},
                key=lambda value: self._draw_sort_key(value, ""),
            )
        )
        if len(draw_keys) < window_count:
            return None
        selected = set(draw_keys[-window_count:])
        return tuple(item for item in ordered if item.draw_number in selected)

    def _provider_window_ranking(
        self,
        lottery_type: LotteryType,
        *,
        window: str,
        criterion: str,
        authority: str | None,
    ) -> dict[str, object]:
        self._validate_criterion(lottery_type, criterion)
        selected_window, window_count = self._provider_window(lottery_type, window)
        provider = self._provider_kind(lottery_type)
        if provider == "b649":
            return self._b649_window_ranking(
                lottery_type, selected_window, criterion, authority
            )
        if provider == "power":
            run = self._p638_current_run(authority)
            run_id = run.run_id
            ranking_records = ()
            if selected_window == "FULL_HISTORY" and criterion == _ANY_OFFICIAL_PRIZE:
                ranking_records = self._provider_ranking_records(lottery_type, run_id)
            if ranking_records:
                authority_payload = self._provider_authority_payload(
                    "POWER_LOTTO_CURRENT_RANKING", run_id=run_id
                )
                rows = [
                    self._ranking_record_payload(lottery_type, item, authority_payload)
                    for item in ranking_records
                ]
                return {
                    "lottery_type": lottery_type.value,
                    "window": selected_window,
                    "criterion": criterion,
                    "authority": authority_payload,
                    "items": rows,
                }
            capability = "POWER_LOTTO_CURRENT_REPLAY"
        elif provider == "daily":
            run = self._t539_run(authority)
            run_id = run.run_id
            ranking_records = ()
            if selected_window == "FULL_HISTORY" and criterion == _ANY_OFFICIAL_PRIZE:
                ranking_records = self._provider_ranking_records(lottery_type, run_id)
            if ranking_records:
                authority_payload = self._provider_authority_payload(
                    "DAILY_539_HISTORICAL", run_id=run_id
                )
                rows = [
                    self._ranking_record_payload(lottery_type, item, authority_payload)
                    for item in ranking_records
                ]
                return {
                    "lottery_type": lottery_type.value,
                    "window": selected_window,
                    "criterion": criterion,
                    "authority": authority_payload,
                    "items": rows,
                }
            capability = "DAILY_539_HISTORICAL"
        else:
            raise LottoLabMcpQueryError(
                EVIDENCE_UNAVAILABLE,
                "the selected replay provider is unavailable.",
            )

        refs = self._provider_strategy_refs(lottery_type, run_id)
        rows: list[dict[str, object]] = []
        authority_payload = self._provider_authority_payload(capability, run_id=run_id)
        for ref in refs:
            observations = self._provider_observations(lottery_type, run_id, ref.strategy_id)
            selected = self._provider_window_observations(observations, window_count)
            if selected is None:
                continue
            metric = self._criterion_metric(lottery_type, selected, criterion)
            if metric is None:
                continue
            successes, observation_count = metric
            rows.append(
                {
                    "rank": 0,
                    "strategy_id": ref.strategy_id,
                    "display_name": ref.display_name,
                    "lottery_type": lottery_type.value,
                    "observation_count": observation_count,
                    "successes": successes,
                    "success_rate": (
                        successes / observation_count if observation_count else None
                    ),
                    "success_rate_exact": {
                        "numerator": successes,
                        "denominator": observation_count,
                    },
                    "window": selected_window,
                    "criterion": criterion,
                    "baseline": None,
                    "baseline_delta": None,
                    "authority": authority_payload,
                }
            )
        rows.sort(
            key=lambda item: (
                -(
                    float(cast(float, item["success_rate"]))
                    if item["success_rate"] is not None
                    else -1.0
                ),
                -cast(int, item["successes"]),
                str(item["strategy_id"]),
            )
        )
        for index, row in enumerate(rows, start=1):
            row["rank"] = index
        if not rows:
            raise LottoLabMcpQueryError(
                EVIDENCE_UNAVAILABLE,
                "the selected authority has no complete evidence for this window.",
                details={"lottery_type": lottery_type.value, "window": selected_window},
            )
        return {
            "lottery_type": lottery_type.value,
            "window": selected_window,
            "criterion": criterion,
            "authority": authority_payload,
            "items": rows,
        }

    def _provider_ranking_records(
        self, lottery_type: LotteryType, run_id: str
    ) -> tuple[P638RankingRecord | T539RankingRecord, ...]:
        try:
            if lottery_type is LotteryType.POWER_LOTTO:
                factory = self._sources.p638_ranking_factory
                if factory is None:
                    return ()
                page = factory().list_rankings(run_id)
                return () if page is None else tuple(page.items)
            if lottery_type is LotteryType.DAILY_539:
                page = self._t539_repository().list_rankings(run_id)
                return () if page is None else tuple(page.items)
        except (
            P638HistoricalResultsUnavailableError,
            T539HistoricalResultsUnavailableError,
        ) as exc:
            raise LottoLabMcpQueryError(
                STORAGE_UNAVAILABLE,
                "official-prize ranking storage is unavailable.",
            ) from exc
        except Exception as exc:
            raise LottoLabMcpQueryError(
                STORAGE_UNAVAILABLE,
                "official-prize ranking storage is unavailable.",
            ) from exc
        return ()

    def _ranking_record_payload(
        self,
        lottery_type: LotteryType,
        record: P638RankingRecord | T539RankingRecord,
        authority: Mapping[str, object],
    ) -> dict[str, object]:
        winning = record.winning_target_count
        eligible = record.eligible_target_count
        return {
            "rank": record.rank,
            "strategy_id": record.strategy_id,
            "display_name": record.strategy_id,
            "lottery_type": lottery_type.value,
            "observation_count": eligible,
            "successes": winning,
            "success_rate": record.winning_target_rate,
            "success_rate_exact": {"numerator": winning, "denominator": eligible},
            "window": "FULL_HISTORY",
            "criterion": _ANY_OFFICIAL_PRIZE,
            "baseline": None,
            "baseline_delta": None,
            "official_prize": record.highest_prize_tier_achieved,
            "authority": dict(authority),
        }

    def _provider_observations(
        self, lottery_type: LotteryType, run_id: str, strategy_id: str
    ) -> tuple[_Observation, ...]:
        provider = self._provider_kind(lottery_type)
        if provider == "power":
            repository = self._p638_current_repository()
            p638_records: list[P638ReplayRecord] = []
            offset = 0
            try:
                while True:
                    page = repository.list_replay(
                        run_id,
                        P638ReplayQuery(
                            strategy_id=strategy_id,
                            limit=_MAX_PAGE_SIZE,
                            offset=offset,
                        ),
                    )
                    if page is None:
                        break
                    p638_records.extend(page.items)
                    if not page.items or len(p638_records) >= page.total_count:
                        break
                    offset += len(page.items)
            except P638HistoricalResultsUnavailableError as exc:
                raise LottoLabMcpQueryError(
                    STORAGE_UNAVAILABLE,
                    "POWER_LOTTO current replay storage is unavailable.",
                ) from exc
            except Exception as exc:
                raise LottoLabMcpQueryError(
                    EVIDENCE_UNAVAILABLE,
                    "POWER_LOTTO replay evidence is unavailable.",
                ) from exc
            return tuple(
                self._p638_observation(item)
                for item in p638_records
                if item.status == "COMPLETE" and item.tickets
            )
        if provider == "daily":
            repository = self._t539_repository()
            t539_records: list[T539ReplayRecord] = []
            offset = 0
            try:
                while True:
                    page = repository.list_replay(
                        run_id,
                        T539ReplayQuery(
                            strategy_id=strategy_id,
                            limit=_MAX_PAGE_SIZE,
                            offset=offset,
                        ),
                    )
                    if page is None:
                        break
                    t539_records.extend(page.items)
                    if not page.items or len(t539_records) >= page.total_count:
                        break
                    offset += len(page.items)
            except T539HistoricalResultsUnavailableError as exc:
                raise LottoLabMcpQueryError(
                    STORAGE_UNAVAILABLE,
                    "DAILY_539 historical storage is unavailable.",
                ) from exc
            except Exception as exc:
                raise LottoLabMcpQueryError(
                    EVIDENCE_UNAVAILABLE,
                    "DAILY_539 replay evidence is unavailable.",
                ) from exc
            return tuple(
                self._t539_observation(item)
                for item in t539_records
                if item.status == "SUCCESS" and item.tickets
            )
        return ()

    @staticmethod
    def _t539_observation(record: T539ReplayRecord) -> _Observation:
        return _Observation(
            strategy_id=record.strategy_id,
            strategy_version=record.strategy_version,
            draw_number=record.target_draw_id,
            draw_date=record.target_draw_date or "",
            target_main_numbers=(record.tickets[0].actual_numbers if record.tickets else ()),
            target_special_numbers=(),
            tickets=tuple(
                _TicketEvidence(
                    position=ticket.ticket_position,
                    main_numbers=ticket.predicted_numbers,
                    special_number=None,
                    main_matches=ticket.hits,
                    special_hit=False,
                    persisted_prize_tier=ticket.prize_tier,
                    persisted_prize_order=ticket.prize_tier_order,
                    persisted_prize_amount=ticket.prize_amount,
                )
                for ticket in record.tickets
            ),
            status="COMPLETE",
        )

    def _provider_replay_summary(
        self, lottery_type: LotteryType, strategy_id: str, authority: str | None
    ) -> dict[str, object]:
        provider = self._provider_kind(lottery_type)
        if provider == "b649":
            self._select_provider_authority("BIG_LOTTO_PACKAGED_RECORDS", authority)
            rows = tuple(
                row
                for row in self._b649_dataset().records
                if row.strategy_id == strategy_id and row.prefix_count == _B649_DEFAULT_PREFIX_COUNT
            )
            if not rows:
                raise LottoLabMcpQueryError(
                    STRATEGY_NOT_FOUND,
                    "strategy_id was not found in the packaged authority.",
                    details={"strategy_id": strategy_id},
                )
            metric_rows = tuple(row for row in rows if row.success_count is not None)
            authority_payload = self._provider_authority_payload(
                "BIG_LOTTO_PACKAGED_RECORDS"
            )
            if not metric_rows:
                return {
                    "strategy": self._strategy_payload(
                        _StrategyRef(
                            strategy_id=strategy_id,
                            display_name=strategy_id,
                            strategy_version=rows[0].strategy_version,
                            replicate=None,
                            native_ticket_count=rows[0].prefix_count,
                            observation_count=0,
                        ),
                        lottery_type,
                    ),
                    "lottery_type": lottery_type.value,
                    "completed_observation_count": 0,
                    "hit_distribution": None,
                    "official_prize_distribution": None,
                    "available_windows": [],
                    "available_criteria": [],
                    "replay_status": "UNAVAILABLE",
                    "provenance": authority_payload.get("provenance"),
                    "authority": authority_payload,
                    "available_authorities": [authority_payload],
                    "unavailable_reasons": [
                        rows[0].metrics_unavailable_reason or EVIDENCE_UNAVAILABLE
                    ],
                }
            full = next(
                (
                    row
                    for row in metric_rows
                    if row.window is B649HistoryWindow.FULL
                    and row.criterion.value == "M4_PLUS"
                ),
                metric_rows[0],
            )
            return {
                "strategy": self._strategy_payload(
                    _StrategyRef(
                        strategy_id=strategy_id,
                        display_name=strategy_id,
                        strategy_version=full.strategy_version,
                        replicate=None,
                        native_ticket_count=full.prefix_count,
                        observation_count=full.successful_execution_count or 0,
                    ),
                    lottery_type,
                ),
                "lottery_type": lottery_type.value,
                "completed_observation_count": full.successful_execution_count or 0,
                "hit_distribution": None,
                "official_prize_distribution": self._b649_prize_distribution(full),
                "available_windows": sorted({row.window.value for row in metric_rows}),
                "available_criteria": [
                    *sorted({row.criterion.value for row in metric_rows}),
                    _ANY_OFFICIAL_PRIZE,
                ],
                "replay_status": "COMPLETE",
                "provenance": authority_payload.get("provenance"),
                "authority": authority_payload,
                "available_authorities": [authority_payload],
                "unavailable_reasons": [],
                "aggregate_evidence": [self._b649_metric_payload(row) for row in metric_rows],
            }

        if provider == "power":
            run = self._p638_current_run(authority)
            ref = self._provider_strategy_ref(lottery_type, run.run_id, strategy_id)
            observations = self._provider_observations(lottery_type, run.run_id, strategy_id)
            capability = "POWER_LOTTO_CURRENT_REPLAY"
        elif provider == "daily":
            run = self._t539_run(authority)
            ref = self._provider_strategy_ref(lottery_type, run.run_id, strategy_id)
            capability = "DAILY_539_HISTORICAL"
            try:
                metrics = self._t539_repository().get_metrics(
                    run.run_id, strategy_id=strategy_id
                )
            except T539HistoricalResultsUnavailableError as exc:
                raise LottoLabMcpQueryError(
                    STORAGE_UNAVAILABLE,
                    "DAILY_539 historical storage is unavailable.",
                ) from exc
            except Exception as exc:
                raise LottoLabMcpQueryError(
                    STORAGE_UNAVAILABLE,
                    "DAILY_539 historical storage is unavailable.",
                ) from exc
            authority_payload = self._provider_authority_payload(
                capability, run_id=run.run_id
            )
            if metrics is None:
                raise LottoLabMcpQueryError(
                    STRATEGY_NOT_FOUND,
                    "strategy_id was not found in the selected authority.",
                    details={"strategy_id": strategy_id},
                )
            return {
                "strategy": self._strategy_payload(ref, lottery_type),
                "lottery_type": lottery_type.value,
                "completed_observation_count": metrics.target_count,
                "hit_distribution": [
                    {
                        "main_matches": hits,
                        "special_hit": None,
                        "ticket_count": count,
                    }
                    for hits, count in metrics.hit_distribution
                ],
                "official_prize_distribution": [
                    {"prize_tier": tier, "ticket_count": count}
                    for tier, count in metrics.prize_tier_counts
                    if count > 0
                ],
                "available_windows": self._available_windows_for_count(
                    metrics.target_count
                ),
                "available_criteria": self._available_criteria_for_rule(lottery_type),
                "replay_status": "COMPLETE" if metrics.target_count > 0 else "UNAVAILABLE",
                "provenance": authority_payload.get("provenance"),
                "authority": authority_payload,
                "available_authorities": [authority_payload],
                "unavailable_reasons": []
                if metrics.target_count > 0
                else [EVIDENCE_UNAVAILABLE],
            }
        else:
            raise LottoLabMcpQueryError(
                EVIDENCE_UNAVAILABLE,
                "the selected replay provider is unavailable.",
            )
        authority_payload = self._provider_authority_payload(capability, run_id=run.run_id)
        if not observations:
            return {
                "strategy": self._strategy_payload(ref, lottery_type),
                "lottery_type": lottery_type.value,
                "completed_observation_count": 0,
                "hit_distribution": None,
                "official_prize_distribution": None,
                "available_windows": [],
                "available_criteria": [],
                "replay_status": "UNAVAILABLE",
                "provenance": authority_payload.get("provenance"),
                "authority": authority_payload,
                "available_authorities": [authority_payload],
                "unavailable_reasons": [EVIDENCE_UNAVAILABLE],
            }
        return {
            "strategy": self._strategy_payload(ref, lottery_type),
            "lottery_type": lottery_type.value,
            "completed_observation_count": len({item.draw_number for item in observations}),
            "hit_distribution": self._hit_distribution(lottery_type, observations),
            "official_prize_distribution": self._prize_distribution(
                lottery_type, observations
            ),
            "available_windows": self._available_windows(observations),
            "available_criteria": self._available_criteria(lottery_type, observations),
            "replay_status": "COMPLETE",
            "provenance": authority_payload.get("provenance"),
            "authority": authority_payload,
            "available_authorities": [authority_payload],
            "unavailable_reasons": [],
        }

    def _provider_match_summary(
        self,
        lottery_type: LotteryType,
        strategy_id: str,
        min_main_matches: int,
        authority: str | None,
    ) -> dict[str, object]:
        provider = self._provider_kind(lottery_type)
        if provider == "b649":
            self._select_provider_authority("BIG_LOTTO_PACKAGED_RECORDS", authority)
            criterion = _B649_CRITERION_BY_THRESHOLD.get(min_main_matches)
            if criterion is None:
                raise LottoLabMcpQueryError(
                    EVIDENCE_UNAVAILABLE,
                    "the packaged BIG_LOTTO authority does not persist this match threshold.",
                    details={"available_thresholds": [3, 4, 5, 6]},
                )
            rows = tuple(
                row
                for row in self._b649_dataset().records
                if row.strategy_id == strategy_id
                and row.prefix_count == _B649_DEFAULT_PREFIX_COUNT
                and row.window is B649HistoryWindow.FULL
                and row.criterion.value == criterion
                and row.success_count is not None
            )
            if not rows:
                raise LottoLabMcpQueryError(
                    STRATEGY_NOT_FOUND,
                    "strategy_id was not found in the packaged authority.",
                    details={"strategy_id": strategy_id},
                )
            row = rows[0]
            ref = _StrategyRef(
                strategy_id=row.strategy_id,
                display_name=row.strategy_id,
                strategy_version=row.strategy_version,
                replicate=None,
                native_ticket_count=row.prefix_count,
                observation_count=row.successful_execution_count or 0,
            )
            authority_payload = self._provider_authority_payload(
                "BIG_LOTTO_PACKAGED_RECORDS"
            )
            return {
                "strategy": self._strategy_payload(ref, lottery_type),
                "lottery_type": lottery_type.value,
                "min_main_matches": min_main_matches,
                "exact_main_match_distribution": None,
                "threshold_distinct_draw_count": row.success_count,
                "threshold_ticket_hit_count": None,
                "best_match": None,
                "authority": authority_payload,
                "unavailable_reason": None,
                "evidence_semantics": "persisted_provider_aggregate",
            }
        if provider == "power":
            run = self._p638_current_run(authority)
            ref = self._provider_strategy_ref(lottery_type, run.run_id, strategy_id)
            observations = self._provider_observations(lottery_type, run.run_id, strategy_id)
            capability = "POWER_LOTTO_CURRENT_REPLAY"
        elif provider == "daily":
            run = self._t539_run(authority)
            ref = self._provider_strategy_ref(lottery_type, run.run_id, strategy_id)
            observations = self._provider_observations(lottery_type, run.run_id, strategy_id)
            capability = "DAILY_539_HISTORICAL"
        else:
            raise LottoLabMcpQueryError(
                EVIDENCE_UNAVAILABLE,
                "the selected replay provider is unavailable.",
            )
        qualifying_draws = {
            observation.draw_number
            for observation in observations
            if any(ticket.main_matches >= min_main_matches for ticket in observation.tickets)
        }
        authority_payload = self._provider_authority_payload(capability, run_id=run.run_id)
        best = None
        if observations:
            candidates = [
                (ticket.main_matches, ticket.special_hit, observation, ticket)
                for observation in observations
                for ticket in observation.tickets
            ]
            if candidates:
                best = min(candidates, key=self._best_match_key)
        return {
            "strategy": self._strategy_payload(ref, lottery_type),
            "lottery_type": lottery_type.value,
            "min_main_matches": min_main_matches,
            "exact_main_match_distribution": self._hit_distribution(
                lottery_type, observations
            )
            if observations
            else None,
            "threshold_distinct_draw_count": len(qualifying_draws),
            "threshold_ticket_hit_count": sum(
                1
                for observation in observations
                for ticket in observation.tickets
                if ticket.main_matches >= min_main_matches
            ),
            "best_match": None if best is None else self._best_match_payload(best),
            "authority": authority_payload,
            "unavailable_reason": None if observations else EVIDENCE_UNAVAILABLE,
        }

    def _provider_threshold_search(
        self,
        lottery_type: LotteryType,
        min_main_matches: int,
        authority: str | None,
        window: str | None,
    ) -> dict[str, object]:
        provider = self._provider_kind(lottery_type)
        if provider == "b649":
            self._select_provider_authority("BIG_LOTTO_PACKAGED_RECORDS", authority)
            criterion = _B649_CRITERION_BY_THRESHOLD.get(min_main_matches)
            if criterion is None:
                raise LottoLabMcpQueryError(
                    EVIDENCE_UNAVAILABLE,
                    "the packaged BIG_LOTTO authority does not persist this match threshold.",
                    details={"available_thresholds": [3, 4, 5, 6]},
                )
            selected_window, _ = self._provider_window(
                lottery_type, "FULL" if window is None else window
            )
            rows: list[dict[str, object]] = []
            dataset = self._b649_dataset()
            grouped: dict[str, B649MultiTicketRecord] = {}
            for record in dataset.records:
                if (
                    record.prefix_count == _B649_DEFAULT_PREFIX_COUNT
                    and record.window.value == selected_window
                    and record.criterion.value == criterion
                    and record.success_count is not None
                ):
                    grouped[record.strategy_id] = record
            authority_payload = self._provider_authority_payload(
                "BIG_LOTTO_PACKAGED_RECORDS"
            )
            for record in grouped.values():
                if not record.success_count:
                    continue
                rows.append(
                    {
                        "strategy_id": record.strategy_id,
                        "display_name": record.strategy_id,
                        "observation_count": record.successful_execution_count,
                        "exact_match_distribution": None,
                        "threshold_distinct_draw_count": record.success_count,
                        "threshold_ticket_hit_count": None,
                        "highest_main_match_count": min_main_matches,
                        "best_official_prize": self._b649_best_prize_payload(record),
                        "best_prize_draw": None,
                        "authority": authority_payload,
                    }
                )
            rows.sort(
                key=lambda item: (
                    -cast(int, item["threshold_distinct_draw_count"]),
                    self._prize_sort_key_from_payload(item["best_official_prize"]),
                    str(item["strategy_id"]),
                )
            )
            return {
                "lottery_type": lottery_type.value,
                "min_main_matches": min_main_matches,
                "window": selected_window,
                "authority": authority_payload,
                "items": rows,
            }

        if provider == "power":
            run = self._p638_current_run(authority)
            capability = "POWER_LOTTO_CURRENT_REPLAY"
        elif provider == "daily":
            run = self._t539_run(authority)
            capability = "DAILY_539_HISTORICAL"
        else:
            raise LottoLabMcpQueryError(
                EVIDENCE_UNAVAILABLE,
                "the selected replay provider is unavailable.",
            )
        window_count: int | None = None
        selected_window = None
        if window is not None:
            selected_window, window_count = self._provider_window(lottery_type, window)
        authority_payload = self._provider_authority_payload(capability, run_id=run.run_id)
        rows = []
        for ref in self._provider_strategy_refs(lottery_type, run.run_id):
            observations = self._provider_observations(lottery_type, run.run_id, ref.strategy_id)
            selected = self._provider_window_observations(observations, window_count)
            if selected is None:
                continue
            qualifying_draws = {
                observation.draw_number
                for observation in selected
                if any(ticket.main_matches >= min_main_matches for ticket in observation.tickets)
            }
            if not qualifying_draws:
                continue
            best_prize = self._best_prize(lottery_type, selected)
            rows.append(
                {
                    "strategy_id": ref.strategy_id,
                    "display_name": ref.display_name,
                    "observation_count": len({item.draw_number for item in selected}),
                    "exact_match_distribution": self._hit_distribution(
                        lottery_type, selected
                    ),
                    "threshold_distinct_draw_count": len(qualifying_draws),
                    "threshold_ticket_hit_count": sum(
                        1
                        for observation in selected
                        for ticket in observation.tickets
                        if ticket.main_matches >= min_main_matches
                    ),
                    "highest_main_match_count": max(
                        ticket.main_matches
                        for observation in selected
                        for ticket in observation.tickets
                    ),
                    "best_official_prize": best_prize,
                    "best_prize_draw": None if best_prize is None else best_prize["draw_number"],
                    "authority": authority_payload,
                }
            )
        rows.sort(
            key=lambda item: (
                -cast(int, item["threshold_distinct_draw_count"]),
                self._prize_sort_key_from_payload(item["best_official_prize"]),
                -cast(int, item["highest_main_match_count"]),
                str(item["strategy_id"]),
            )
        )
        return {
            "lottery_type": lottery_type.value,
            "min_main_matches": min_main_matches,
            "window": selected_window,
            "authority": authority_payload,
            "items": rows,
        }

    def _provider_best_prize(
        self, lottery_type: LotteryType, strategy_id: str, authority: str | None
    ) -> dict[str, object]:
        provider = self._provider_kind(lottery_type)
        if provider == "b649":
            self._select_provider_authority("BIG_LOTTO_PACKAGED_RECORDS", authority)
            rows = tuple(
                row
                for row in self._b649_dataset().records
                if row.strategy_id == strategy_id
                and row.prefix_count == _B649_DEFAULT_PREFIX_COUNT
                and row.window is B649HistoryWindow.FULL
                and row.official_prize_counts is not None
            )
            if not rows:
                raise LottoLabMcpQueryError(
                    STRATEGY_NOT_FOUND,
                    "strategy_id was not found in the packaged authority.",
                    details={"strategy_id": strategy_id},
                )
            record = rows[0]
            authority_payload = self._provider_authority_payload(
                "BIG_LOTTO_PACKAGED_RECORDS"
            )
            return {
                "strategy": self._strategy_payload(
                    _StrategyRef(
                        strategy_id=strategy_id,
                        display_name=strategy_id,
                        strategy_version=record.strategy_version,
                        replicate=None,
                        native_ticket_count=record.prefix_count,
                        observation_count=record.successful_execution_count or 0,
                    ),
                    lottery_type,
                ),
                "lottery_type": lottery_type.value,
                "highest_official_prize": self._b649_best_prize_payload(record),
                "draw_number": None,
                "draw_date": None,
                "winning_ticket": None,
                "canonical_match_information": {
                    "source": "persisted_official_prize_counts",
                    "lottery_type": lottery_type.value,
                },
                "authority": authority_payload,
                "reason": None,
            }
        if provider == "power":
            run = self._p638_current_run(authority)
            capability = "POWER_LOTTO_CURRENT_REPLAY"
        elif provider == "daily":
            run = self._t539_run(authority)
            capability = "DAILY_539_HISTORICAL"
        else:
            raise LottoLabMcpQueryError(
                EVIDENCE_UNAVAILABLE,
                "the selected replay provider is unavailable.",
            )
        ref = self._provider_strategy_ref(lottery_type, run.run_id, strategy_id)
        ranking = next(
            (
                item
                for item in self._provider_ranking_records(lottery_type, run.run_id)
                if item.strategy_id == strategy_id
            ),
            None,
        )
        authority_payload = self._provider_authority_payload(capability, run_id=run.run_id)
        if ranking is not None and ranking.highest_prize_tier_achieved is not None:
            authority_payload = self._provider_authority_payload(
                "POWER_LOTTO_CURRENT_RANKING"
                if lottery_type is LotteryType.POWER_LOTTO
                else "DAILY_539_HISTORICAL",
                run_id=run.run_id,
            )
            return {
                "strategy": self._strategy_payload(ref, lottery_type),
                "lottery_type": lottery_type.value,
                "highest_official_prize": {
                    "prize_tier": ranking.highest_prize_tier_achieved,
                    "tier_order": self._tier_sort_key(
                        lottery_type, ranking.highest_prize_tier_achieved
                    ),
                    "prize_amount": self._prize_amount(
                        lottery_type, ranking.highest_prize_tier_achieved
                    ),
                },
                "draw_number": None,
                "draw_date": None,
                "winning_ticket": None,
                "canonical_match_information": {
                    "source": "persisted_official_prize_ranking",
                    "lottery_type": lottery_type.value,
                },
                "authority": authority_payload,
                "reason": None,
            }
        observations = self._provider_observations(lottery_type, run.run_id, strategy_id)
        best = self._best_prize(lottery_type, observations, include_ticket=True)
        return {
            "strategy": self._strategy_payload(ref, lottery_type),
            "lottery_type": lottery_type.value,
            "highest_official_prize": None if best is None else best["prize"],
            "draw_number": None if best is None else best["draw_number"],
            "draw_date": None if best is None else best["draw_date"],
            "winning_ticket": None if best is None else best.get("ticket"),
            "canonical_match_information": None if best is None else best["match"],
            "authority": authority_payload,
            "reason": None if best is not None else OFFICIAL_PRIZE_EVIDENCE_UNAVAILABLE,
        }

    def _provider_draw(
        self, lottery_type: LotteryType, draw_number: str, authority: str | None
    ) -> dict[str, object]:
        allowed = {"DRAW_DATA", "draw-data"}
        capability = self._historical_capability_for(lottery_type)
        descriptor = self._descriptor_for(capability)
        allowed.add(capability)
        if descriptor is not None:
            allowed.add(descriptor.authority_id)
            if descriptor.run_id is not None:
                allowed.add(descriptor.run_id)
        if authority is not None and authority not in allowed:
            raise LottoLabMcpQueryError(
                AUTHORITY_NOT_FOUND,
                "the requested logical authority was not found.",
                details={"capability": "DRAW_DATA"},
            )
        if self._sources.draw_factory is not None:
            try:
                record = self._sources.draw_factory().get_draw(lottery_type, draw_number)
            except Exception as exc:
                raise LottoLabMcpQueryError(
                    STORAGE_UNAVAILABLE,
                    "canonical draw data is unavailable.",
                ) from exc
            if record is not None:
                payload = self._draw_record_payload(lottery_type, record)
                payload["source_metadata"] = {
                    "authority": self._provider_authority_payload("DRAW_DATA"),
                    "rule_contract_version": self._rule_contract(lottery_type).contract_version,
                }
                return payload
        provider = self._provider_kind(lottery_type)
        if provider == "power":
            run = self._p638_current_run(authority)
            try:
                record = self._p638_current_repository().get_draw(run.run_id, draw_number)
            except Exception as exc:
                raise LottoLabMcpQueryError(
                    STORAGE_UNAVAILABLE,
                    "POWER_LOTTO canonical draw data is unavailable.",
                ) from exc
            if record is not None:
                return {
                    "lottery_type": lottery_type.value,
                    "draw_number": record.draw_number,
                    "draw_date": record.draw_date,
                    "main_numbers": list(record.winning_zone1_numbers),
                    "special_numbers": [],
                    "secondary_numbers": [record.winning_zone2_number],
                    "source_metadata": {
                        "authority": self._provider_authority_payload(
                            "POWER_LOTTO_CURRENT_REPLAY", run_id=run.run_id
                        ),
                        "rule_contract_version": self._rule_contract(
                            lottery_type
                        ).contract_version,
                    },
                }
        if provider == "daily":
            run = self._t539_run(authority)
            try:
                record = self._t539_repository().get_draw(run.run_id, draw_number)
            except Exception as exc:
                raise LottoLabMcpQueryError(
                    STORAGE_UNAVAILABLE,
                    "DAILY_539 canonical draw data is unavailable.",
                ) from exc
            if record is not None:
                return {
                    "lottery_type": lottery_type.value,
                    "draw_number": record.draw_id,
                    "draw_date": record.draw_date,
                    "main_numbers": list(record.winning_numbers),
                    "special_numbers": [],
                    "secondary_numbers": [],
                    "source_metadata": {
                        "authority": self._provider_authority_payload(
                            "DAILY_539_HISTORICAL", run_id=run.run_id
                        ),
                        "rule_contract_version": self._rule_contract(
                            lottery_type
                        ).contract_version,
                    },
                }
        raise LottoLabMcpQueryError(
            EVIDENCE_UNAVAILABLE,
            "the requested canonical draw is unavailable.",
            details={"lottery_type": lottery_type.value, "draw_number": draw_number},
        )

    @staticmethod
    def _draw_record_payload(lottery_type: LotteryType, record: DrawRecord) -> dict[str, object]:
        draw_date = record.draw_date.isoformat()
        if lottery_type is LotteryType.BIG_LOTTO:
            special_numbers = list(record.special_numbers)
            secondary_numbers: list[int] = []
        elif lottery_type is LotteryType.POWER_LOTTO:
            special_numbers = []
            secondary_numbers = list(record.special_numbers)
        else:
            special_numbers = []
            secondary_numbers = []
        return {
            "lottery_type": lottery_type.value,
            "draw_number": record.draw_number,
            "draw_date": draw_date,
            "main_numbers": list(record.main_numbers),
            "special_numbers": special_numbers,
            "secondary_numbers": secondary_numbers,
        }

    def _b649_window_ranking(
        self,
        lottery_type: LotteryType,
        window: str,
        criterion: str,
        authority: str | None,
    ) -> dict[str, object]:
        self._select_provider_authority("BIG_LOTTO_PACKAGED_RECORDS", authority)
        dataset = self._b649_dataset()
        rows = tuple(
            row
            for row in dataset.records
            if row.prefix_count == _B649_DEFAULT_PREFIX_COUNT
            and row.window.value == window
            and row.success_count is not None
            and (criterion == _ANY_OFFICIAL_PRIZE or row.criterion.value == criterion)
        )
        if criterion == _ANY_OFFICIAL_PRIZE:
            rows = tuple(
                row
                for row in dataset.records
                if row.prefix_count == _B649_DEFAULT_PREFIX_COUNT
                and row.window.value == window
                and row.official_any_prize_count is not None
            )
        if not rows:
            raise LottoLabMcpQueryError(
                EVIDENCE_UNAVAILABLE,
                "the packaged BIG_LOTTO authority has no complete evidence for this window.",
                details={"window": window, "criterion": criterion},
            )
        authority_payload = self._provider_authority_payload(
            "BIG_LOTTO_PACKAGED_RECORDS"
        )
        output: list[dict[str, object]] = []
        for row in rows:
            if criterion == _ANY_OFFICIAL_PRIZE:
                successes = row.official_any_prize_count or 0
                observation_count = row.successful_execution_count or 0
                rate = row.official_any_prize_rate
                rank = row.official_rank
            else:
                successes = row.success_count or 0
                observation_count = row.successful_execution_count or 0
                rate = row.historical_success_rate
                rank = row.rank
            if rate is None:
                continue
            output.append(
                {
                    "rank": rank or 0,
                    "strategy_id": row.strategy_id,
                    "display_name": row.strategy_id,
                    "lottery_type": lottery_type.value,
                    "observation_count": observation_count,
                    "successes": successes,
                    "success_rate": self._decimal_float(rate),
                    "success_rate_exact": {
                        "numerator": successes,
                        "denominator": observation_count,
                        "persisted_decimal": rate,
                    },
                    "window": window,
                    "criterion": criterion,
                    "baseline": row.random_baseline_success_rate,
                    "baseline_delta": row.random_baseline_rate_difference,
                    "authority": authority_payload,
                }
            )
        output.sort(
            key=lambda item: (
                -cast(float, item["success_rate"]),
                -cast(int, item["successes"]),
                str(item["strategy_id"]),
            )
        )
        for index, row in enumerate(output, start=1):
            row["rank"] = index
        return {
            "lottery_type": lottery_type.value,
            "window": window,
            "criterion": criterion,
            "authority": authority_payload,
            "items": output,
        }

    @staticmethod
    def _decimal_float(value: str) -> float:
        try:
            return float(Decimal(value))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise LottoLabMcpQueryError(
                SCHEMA_MISMATCH,
                "packaged evidence contains an invalid persisted rate.",
            ) from exc

    def _b649_metric_payload(self, row: B649MultiTicketRecord) -> dict[str, object]:
        return {
            "window": row.window.value,
            "criterion": row.criterion.value,
            "success_count": row.success_count,
            "effective_backtest_draw_count": row.effective_backtest_draw_count,
            "successful_execution_count": row.successful_execution_count,
            "historical_success_rate": row.historical_success_rate,
            "official_any_prize_count": row.official_any_prize_count,
            "window_complete": row.window_complete,
        }

    def _b649_prize_distribution(
        self, row: B649MultiTicketRecord
    ) -> list[dict[str, object]] | None:
        counts = row.official_prize_counts
        if counts is None:
            return None
        values = {
            "FIRST": counts.first,
            "SECOND": counts.second,
            "THIRD": counts.third,
            "FOURTH": counts.fourth,
            "FIFTH": counts.fifth,
            "SIXTH": counts.sixth,
            "SEVENTH": counts.seventh,
            "GENERAL": counts.general,
        }
        return [
            {"prize_tier": tier, "ticket_count": count}
            for tier, count in values.items()
            if count > 0
        ]

    def _b649_best_prize_payload(
        self, row: B649MultiTicketRecord
    ) -> dict[str, object] | None:
        counts = row.official_prize_counts
        if counts is None:
            return None
        values = {
            "FIRST": counts.first,
            "SECOND": counts.second,
            "THIRD": counts.third,
            "FOURTH": counts.fourth,
            "FIFTH": counts.fifth,
            "SIXTH": counts.sixth,
            "SEVENTH": counts.seventh,
            "GENERAL": counts.general,
        }
        prize_rule = BIG_LOTTO_RULE_CONTRACT.prize_rule
        if prize_rule is None:
            raise LottoLabMcpQueryError(
                OFFICIAL_PRIZE_EVIDENCE_UNAVAILABLE,
                "BIG_LOTTO prize semantics are unavailable.",
            )
        tier = next(
            (item.tier_id.value for item in prize_rule.tiers if values[item.tier_id.value] > 0),
            None,
        )
        if tier is None:
            return None
        return {
            "prize_tier": tier,
            "tier_order": self._tier_sort_key(LotteryType.BIG_LOTTO, tier),
            "prize_amount": None,
            "ticket_count": values[tier],
            "source": "persisted_official_prize_counts",
        }

    def _supported_lottery_types(self) -> tuple[LotteryType, ...]:
        return tuple(
            lottery_type
            for lottery_type in LOTTERY_RULE_CONTRACTS
            if resolve_lottery_rule_contract(lottery_type, LOTTERY_RULE_CONTRACTS) is not None
        )

    def _resolve_lottery_type(self, value: str) -> LotteryType:
        if type(value) is not str:
            raise LottoLabMcpQueryError(INVALID_LOTTERY_TYPE, "lottery_type is not supported.")
        try:
            lottery_type = LotteryType(value)
        except ValueError as exc:
            raise LottoLabMcpQueryError(
                INVALID_LOTTERY_TYPE,
                "lottery_type is not supported.",
            ) from exc
        if lottery_type not in self._supported_lottery_types():
            raise LottoLabMcpQueryError(INVALID_LOTTERY_TYPE, "lottery_type is not supported.")
        return lottery_type

    def _rule_contract(self, lottery_type: LotteryType) -> LotteryRuleContract:
        contract = resolve_lottery_rule_contract(lottery_type, LOTTERY_RULE_CONTRACTS)
        if contract is None:
            raise LottoLabMcpQueryError(
                INVALID_LOTTERY_TYPE,
                "lottery_type has no active canonical rule contract.",
            )
        return contract

    def _prize_capability(self, lottery_type: LotteryType) -> dict[str, object]:
        try:
            self._rule_contract(lottery_type)
            return {
                "status": "AVAILABLE",
                "source": "canonical_domain_prize_evaluator",
            }
        except LottoLabMcpQueryError as exc:
            return {"status": "UNAVAILABLE", "reason": exc.code}

    def _generic_repository(self) -> HistoricalResultQueryRepository:
        factory = self._sources.generic_factory
        if factory is None:
            unresolved = [
                descriptor.capability
                for descriptor in self._sources.authority_descriptors
                if descriptor.status == "UNRESOLVED"
            ]
            if unresolved:
                raise LottoLabMcpQueryError(
                    AUTHORITY_UNRESOLVED,
                    "no accepted historical authority is available.",
                    details={"capabilities": unresolved},
                )
            raise LottoLabMcpQueryError(
                EVIDENCE_UNAVAILABLE,
                "no read-only historical evidence provider is available.",
            )
        try:
            return factory()
        except LottoLabMcpQueryError:
            raise
        except Exception as exc:
            raise LottoLabMcpQueryError(
                STORAGE_UNAVAILABLE,
                "Historical Results storage is unavailable.",
            ) from exc

    def _p638_repository(self) -> P638HistoricalQueryRepository:
        factory = self._sources.p638_factory
        if factory is None:
            raise LottoLabMcpQueryError(
                EVIDENCE_UNAVAILABLE,
                "POWER_LOTTO replay evidence is unavailable.",
            )
        try:
            return factory()
        except LottoLabMcpQueryError:
            raise
        except Exception as exc:
            raise LottoLabMcpQueryError(
                EVIDENCE_UNAVAILABLE,
                "POWER_LOTTO replay evidence is unavailable.",
            ) from exc

    def _list_runs(self, lottery_type: LotteryType) -> tuple[HistoricalRunSummary, ...]:
        try:
            historical_type = HistoricalLotteryType(lottery_type.value)
        except ValueError:
            return ()
        repository = self._generic_repository()
        items: list[HistoricalRunSummary] = []
        offset = 0
        while True:
            try:
                page = repository.list_runs(
                    HistoricalRunQuery(
                        limit=_MAX_PAGE_SIZE,
                        offset=offset,
                        lottery_type=historical_type,
                    )
                )
            except HistoricalResultsUnavailableError as exc:
                raise LottoLabMcpQueryError(
                    STORAGE_UNAVAILABLE,
                    "Historical Results storage is unavailable.",
                ) from exc
            items.extend(page.items)
            if not page.items or len(items) >= page.total_count:
                break
            offset += len(page.items)
        return tuple(items)

    def _select_authority(
        self, lottery_type: LotteryType, authority: str | None
    ) -> HistoricalRunSummary:
        summaries = self._list_runs(lottery_type)
        if not summaries:
            raise LottoLabMcpQueryError(
                RUN_NOT_FOUND,
                "no completed historical authority exists for lottery_type.",
                details={"lottery_type": lottery_type.value},
            )
        if authority is not None:
            matching = [item for item in summaries if self._authority_matches(item, authority)]
            if not matching:
                raise self._authority_not_found(lottery_type, authority, summaries)
            return matching[0]
        if len(summaries) > 1:
            raise LottoLabMcpQueryError(
                MULTIPLE_AUTHORITIES_REQUIRES_SELECTION,
                "multiple completed authorities exist; select one explicitly.",
                details={
                    "lottery_type": lottery_type.value,
                    "authorities": [
                        self._authority_payload(lottery_type, item) for item in summaries
                    ],
                },
            )
        return next(iter(summaries))

    def _authority_not_found(
        self,
        lottery_type: LotteryType,
        authority: str,
        summaries: tuple[HistoricalRunSummary, ...] | list[HistoricalRunSummary],
    ) -> LottoLabMcpQueryError:
        return LottoLabMcpQueryError(
            AUTHORITY_NOT_FOUND,
            "the requested historical authority was not found.",
            details={
                "lottery_type": lottery_type.value,
                "available_authorities": [
                    self._authority_payload(lottery_type, item) for item in summaries
                ],
            },
        )

    @staticmethod
    def _authority_matches(summary: HistoricalRunSummary, authority: str) -> bool:
        return authority in {summary.run_id, summary.import_identity_sha256}

    def _authority_list(self, lottery_type: LotteryType) -> list[dict[str, object]]:
        return [
            self._authority_payload(lottery_type, summary)
            for summary in self._list_runs(lottery_type)
        ]

    def _authority_payload(
        self, lottery_type: LotteryType, summary: HistoricalRunSummary
    ) -> dict[str, object]:
        return {
            "run_id": summary.run_id,
            "import_identity": summary.import_identity_sha256,
            "lottery_type": lottery_type.value,
            "status": summary.status,
            "coverage": {
                "strategy_count": summary.strategy_count,
                "draw_count": summary.draw_count,
                "observation_count": summary.portfolio_count,
            },
            "source_provenance": {
                "source_kind": self._public_provenance_value(summary.source_kind),
                "source_commit_oid": self._public_provenance_value(
                    summary.source_commit_oid
                ),
                "source_artifact_sha256": summary.source_artifact_sha256,
                "dataset_identity": self._public_provenance_value(
                    summary.dataset_identity
                ),
                "dataset_sha256": summary.dataset_sha256,
                "legacy_run_id": self._public_provenance_value(summary.legacy_run_id),
            },
        }

    @staticmethod
    def _public_provenance_value(value: str | None) -> str | None:
        if value is None:
            return None
        if any(token in value for token in ("/", "\\", ".runs", ".runtime")):
            return "REDACTED_PRIVATE_LOCATION"
        return value

    def _run_payload(
        self,
        lottery_type: LotteryType,
        summary: HistoricalRunSummary,
        *,
        has_strategy_evidence: bool,
    ) -> dict[str, object]:
        has_observations = has_strategy_evidence and summary.portfolio_count > 0
        return {
            **self._authority_payload(lottery_type, summary),
            "available_criteria": (
                self._available_criteria_for_rule(lottery_type) if has_observations else []
            ),
            "available_windows": (
                [_window_value(WindowKind.FULL_HISTORY)] if has_observations else []
            ),
        }

    def _strategy_refs(self, lottery_type: LotteryType, run_id: str) -> tuple[_StrategyRef, ...]:
        if lottery_type is LotteryType.POWER_LOTTO:
            try:
                repository = self._p638_repository()
                page = repository.list_strategies(
                    run_id, limit=_MAX_PAGE_SIZE, offset=0
                )
            except (P638HistoricalResultsUnavailableError, LottoLabMcpQueryError):
                return self._generic_strategy_refs(lottery_type, run_id)
            if page is None:
                return ()
            return tuple(self._p638_strategy_ref(item) for item in page.items)
        return self._generic_strategy_refs(lottery_type, run_id)

    def _generic_strategy_refs(
        self, lottery_type: LotteryType, run_id: str
    ) -> tuple[_StrategyRef, ...]:
        del lottery_type
        try:
            result = self._generic_repository().list_strategies(
                run_id, ticket_count=_FULL_TICKET_COUNT
            )
        except HistoricalResultsUnavailableError as exc:
            raise LottoLabMcpQueryError(
                STORAGE_UNAVAILABLE,
                "Historical Results storage is unavailable.",
            ) from exc
        if result is None:
            return ()
        return tuple(
            _StrategyRef(
                strategy_id=item.strategy_id,
                display_name=self._display_name(item.strategy_id),
                strategy_version=item.strategy_version,
                replicate=item.replicate,
                native_ticket_count=item.ticket_count,
                observation_count=item.evaluated_draws,
            )
            for item in result.items
        )

    def _p638_strategy_ref(self, item: P638StrategyRecord) -> _StrategyRef:
        return _StrategyRef(
            strategy_id=item.strategy_id,
            display_name=item.display_label,
            strategy_version=item.strategy_version,
            replicate=None,
            native_ticket_count=item.native_ticket_count,
            observation_count=item.complete_target_count,
            provenance=item.provenance,
        )

    def _display_name(self, strategy_id: str) -> str:
        if self._strategy_name_resolver is None:
            return strategy_id
        try:
            value = self._strategy_name_resolver(strategy_id)
        except Exception:
            value = None
        return value if value else strategy_id

    def _require_strategy(
        self, lottery_type: LotteryType, run_id: str, strategy_id: str
    ) -> _StrategyRef:
        if type(strategy_id) is not str or not strategy_id:
            raise LottoLabMcpQueryError(STRATEGY_NOT_FOUND, "strategy_id was not found.")
        for ref in self._strategy_refs(lottery_type, run_id):
            if ref.strategy_id == strategy_id:
                return ref
        raise LottoLabMcpQueryError(
            STRATEGY_NOT_FOUND,
            "strategy_id was not found in the selected authority.",
            details={"strategy_id": strategy_id},
        )

    def _complete_observations(
        self, lottery_type: LotteryType, run_id: str, strategy_id: str
    ) -> tuple[_Observation, ...]:
        if lottery_type is LotteryType.POWER_LOTTO:
            try:
                repository = self._p638_repository()
                records: list[P638ReplayRecord] = []
                offset = 0
                while True:
                    page = repository.list_replay(
                        run_id,
                        P638ReplayQuery(
                            strategy_id=strategy_id,
                            limit=_MAX_PAGE_SIZE,
                            offset=offset,
                        ),
                    )
                    if page is None:
                        break
                    records.extend(page.items)
                    if not page.items or len(records) >= page.total_count:
                        break
                    offset += len(page.items)
                if records:
                    return tuple(
                        self._p638_observation(item)
                        for item in records
                        if item.status == "COMPLETE" and item.tickets
                    )
            except (P638HistoricalResultsUnavailableError, LottoLabMcpQueryError):
                pass
            # A generic POWER_LOTTO import can still be queried if no P638
            # projection exists; it is never merged with a P638 projection.
        try:
            repository = self._generic_repository()
            generic_records: list[HistoricalPortfolioRecord] = []
            offset = 0
            while True:
                page = repository.list_replay_portfolios(
                    run_id,
                    HistoricalReplayQuery(
                        strategy_id=strategy_id,
                        ticket_count=_FULL_TICKET_COUNT,
                        limit=_MAX_PAGE_SIZE,
                        offset=offset,
                    ),
                )
                if page is None:
                    break
                generic_records.extend(page.items)
                if not page.items or len(generic_records) >= page.total_count:
                    break
                offset += len(page.items)
            return tuple(
                _Observation(
                    strategy_id=item.strategy_id,
                    strategy_version=item.strategy_version,
                    draw_number=item.target_draw.draw_number,
                    draw_date=item.target_draw.draw_date,
                    target_main_numbers=item.target_draw.main_numbers,
                    target_special_numbers=item.target_draw.special_numbers,
                    tickets=tuple(
                        _TicketEvidence(
                            position=ticket.portfolio_position,
                            main_numbers=ticket.main_numbers,
                            special_number=(
                                ticket.special_numbers[0]
                                if ticket.special_numbers
                                else None
                            ),
                            main_matches=ticket.main_hit_count,
                            special_hit=ticket.special_hit,
                        )
                        for ticket in item.tickets
                    ),
                    status="COMPLETE",
                )
                for item in generic_records
            )
        except HistoricalResultsUnavailableError as exc:
            raise LottoLabMcpQueryError(
                STORAGE_UNAVAILABLE,
                "Historical Results storage is unavailable.",
            ) from exc

    @staticmethod
    def _p638_observation(record: P638ReplayRecord) -> _Observation:
        return _Observation(
            strategy_id=record.strategy_id,
            strategy_version=record.strategy_version,
            draw_number=record.target_draw_number,
            draw_date=record.target_draw_date,
            target_main_numbers=record.actual_zone1_numbers,
            target_special_numbers=(record.actual_zone2_number,),
            tickets=tuple(
                _TicketEvidence(
                    position=ticket.ticket_position,
                    main_numbers=ticket.predicted_zone1_numbers,
                    special_number=ticket.predicted_zone2_number,
                    main_matches=ticket.zone1_hit_count,
                    special_hit=ticket.zone2_hit,
                    persisted_prize_tier=ticket.prize_tier,
                    persisted_prize_order=ticket.prize_tier_order,
                    persisted_prize_amount=ticket.prize_amount,
                )
                for ticket in record.tickets
            ),
            status=record.status,
            provenance=record.provenance,
        )

    def _resolve_window(self, value: str) -> WindowKind:
        if type(value) is not str:
            raise LottoLabMcpQueryError(INVALID_WINDOW, "window is outside the canonical set.")
        try:
            return WindowKind(value)
        except ValueError as exc:
            raise LottoLabMcpQueryError(
                INVALID_WINDOW,
                "window is outside the canonical set.",
                details={"available_windows": [item.value for item in WindowKind]},
            ) from exc

    def _validate_criterion(self, lottery_type: LotteryType, value: str) -> None:
        if type(value) is not str or value not in _criterion_values():
            raise LottoLabMcpQueryError(
                INVALID_CRITERION,
                "criterion is outside the canonical set.",
                details={"available_criteria": self._available_criteria_for_rule(lottery_type)},
            )
        if value == _ANY_OFFICIAL_PRIZE:
            return
        criterion = HistoricalPrefixSuccessCriterion(value)
        minimum = self._criterion_minimum(criterion)
        if minimum > self._rule_contract(lottery_type).main_number_count:
            raise LottoLabMcpQueryError(
                INVALID_CRITERION,
                "criterion is not applicable to this lottery type.",
            )
        if criterion.value.endswith("_SPECIAL") and not self._has_special_number(
            lottery_type
        ):
            raise LottoLabMcpQueryError(
                INVALID_CRITERION,
                "special-number criteria are not applicable to this lottery type.",
            )

    def _validate_match_threshold(self, lottery_type: LotteryType, value: int) -> None:
        if type(value) is not int or isinstance(value, bool):
            raise LottoLabMcpQueryError(
                INVALID_MATCH_THRESHOLD,
                "min_main_matches must be an integer in the canonical main-number range.",
            )
        if value < 0 or value > self._rule_contract(lottery_type).main_number_count:
            raise LottoLabMcpQueryError(
                INVALID_MATCH_THRESHOLD,
                "min_main_matches is outside the canonical main-number range.",
            )

    def _observations_for_window(
        self, observations: tuple[_Observation, ...], window: WindowKind
    ) -> tuple[_Observation, ...] | None:
        if not observations:
            return None
        ordered = tuple(sorted(observations, key=self._observation_sort_key))
        requested = {
            WindowKind.FULL_HISTORY: None,
            WindowKind.LONG: self._rule_window_count(WindowKind.LONG),
            WindowKind.MEDIUM: self._rule_window_count(WindowKind.MEDIUM),
            WindowKind.SHORT: self._rule_window_count(WindowKind.SHORT),
        }[window]
        if requested is None:
            return ordered
        draw_keys = tuple(
            sorted(
                {item.draw_number for item in ordered},
                key=lambda value: self._draw_sort_key(value, ""),
            )
        )
        if len(draw_keys) < requested:
            return None
        selected = set(draw_keys[-requested:])
        return tuple(item for item in ordered if item.draw_number in selected)

    @staticmethod
    def _rule_window_count(window: WindowKind) -> int:
        return {
            WindowKind.LONG: DEFAULT_WINDOW_POLICY.long_draws,
            WindowKind.MEDIUM: DEFAULT_WINDOW_POLICY.medium_draws,
            WindowKind.SHORT: DEFAULT_WINDOW_POLICY.short_draws,
            WindowKind.FULL_HISTORY: 0,
        }[window]

    @staticmethod
    def _observation_sort_key(item: _Observation) -> tuple[str, int, str, str]:
        return (
            item.draw_date,
            LottoLabMcpQueryService._draw_sort_key(item.draw_number, item.draw_date)[1],
            item.strategy_id,
            item.strategy_version,
        )

    @staticmethod
    def _draw_sort_key(draw_number: str, draw_date: str) -> tuple[str, int]:
        try:
            numeric = int(draw_number)
        except (TypeError, ValueError) as exc:
            raise LottoLabMcpQueryError(
                EVIDENCE_UNAVAILABLE,
                "stored draw identity is malformed.",
            ) from exc
        return draw_date, numeric

    def _criterion_metric(
        self,
        lottery_type: LotteryType,
        observations: tuple[_Observation, ...],
        criterion: str,
    ) -> tuple[int, int] | None:
        if not observations:
            return None
        successful_draws: set[str] = set()
        for observation in observations:
            if any(
                self._criterion_matches(lottery_type, observation, ticket, criterion)
                for ticket in observation.tickets
            ):
                successful_draws.add(observation.draw_number)
        return len(successful_draws), len({item.draw_number for item in observations})

    def _criterion_matches(
        self,
        lottery_type: LotteryType,
        observation: _Observation,
        ticket: _TicketEvidence,
        criterion: str,
    ) -> bool:
        if criterion == _ANY_OFFICIAL_PRIZE:
            return self._evaluate_ticket(lottery_type, observation, ticket).is_winner
        parsed = HistoricalPrefixSuccessCriterion(criterion)
        minimum = self._criterion_minimum(parsed)
        return ticket.main_matches >= minimum and (
            not parsed.value.endswith("_SPECIAL") or ticket.special_hit
        )

    @staticmethod
    def _criterion_minimum(criterion: HistoricalPrefixSuccessCriterion) -> int:
        name = criterion.value
        if name == "M6":
            return 6
        prefix = name.split("_", 1)[0]
        return int(prefix[1:])

    def _available_criteria_for_rule(self, lottery_type: LotteryType) -> list[str]:
        contract = self._rule_contract(lottery_type)
        values: list[str] = []
        for criterion in HistoricalPrefixSuccessCriterion:
            if self._criterion_minimum(criterion) > contract.main_number_count:
                continue
            if criterion.value.endswith("_SPECIAL") and not self._has_special_number(
                lottery_type
            ):
                continue
            values.append(criterion.value)
        values.append(_ANY_OFFICIAL_PRIZE)
        return values

    def _available_criteria(
        self, lottery_type: LotteryType, observations: tuple[_Observation, ...]
    ) -> list[str]:
        return self._available_criteria_for_rule(lottery_type) if observations else []

    def _available_windows(self, observations: tuple[_Observation, ...]) -> list[str]:
        return self._available_windows_for_count(
            len({item.draw_number for item in observations})
        )

    def _available_windows_for_count(self, count: int) -> list[str]:
        values: list[str] = []
        for window in WindowKind:
            requested = self._rule_window_count(window)
            if requested == 0 or count >= requested:
                values.append(window.value)
        return values

    def _available_windows_from_refs(
        self, lottery_type: LotteryType, run_id: str, refs: tuple[_StrategyRef, ...]
    ) -> list[str]:
        del lottery_type
        counts = [ref.observation_count for ref in refs if ref.observation_count > 0]
        if not counts:
            return []
        count = max(counts)
        return [
            window.value
            for window in WindowKind
            if self._rule_window_count(window) == 0 or count >= self._rule_window_count(window)
        ]

    def _hit_distribution(
        self,
        lottery_type: LotteryType,
        observations: tuple[_Observation, ...],
    ) -> list[dict[str, object]]:
        counts: Counter[tuple[int, bool | None]] = Counter(
            (
                ticket.main_matches,
                ticket.special_hit if self._has_special_number(lottery_type) else None,
            )
            for observation in observations
            for ticket in observation.tickets
        )
        return [
            {
                "main_matches": main_matches,
                "special_hit": special_hit,
                "ticket_count": count,
            }
            for (main_matches, special_hit), count in sorted(counts.items())
        ]

    def _prize_distribution(
        self, lottery_type: LotteryType, observations: tuple[_Observation, ...]
    ) -> list[dict[str, object]]:
        counts: Counter[str] = Counter()
        for observation in observations:
            for ticket in observation.tickets:
                result = self._evaluate_ticket(lottery_type, observation, ticket)
                if result.prize_tier is not None:
                    counts[result.prize_tier] += 1
        return [
            {"prize_tier": tier, "ticket_count": count}
            for tier, count in sorted(
                counts.items(), key=lambda item: self._tier_sort_key(lottery_type, item[0])
            )
        ]

    def _best_prize(
        self,
        lottery_type: LotteryType,
        observations: tuple[_Observation, ...],
        *,
        include_ticket: bool = False,
    ) -> dict[str, object] | None:
        candidates: list[
            tuple[
                tuple[int, str, int, int],
                _Observation,
                _TicketEvidence,
                PrizeEvaluationResult,
            ]
        ] = []
        for observation in observations:
            for ticket in observation.tickets:
                result = self._evaluate_ticket(lottery_type, observation, ticket)
                tier = result.prize_tier
                if tier is None:
                    continue
                candidates.append(
                    (
                        (
                            self._tier_sort_key(lottery_type, tier),
                            observation.draw_date,
                            self._numeric_draw_number(observation.draw_number),
                            ticket.position,
                        ),
                        observation,
                        ticket,
                        result,
                    )
                )
        if not candidates:
            return None
        _, observation, ticket, result = min(candidates, key=lambda item: item[0])
        tier = result.prize_tier
        if tier is None:
            raise LottoLabMcpQueryError(
                OFFICIAL_PRIZE_EVIDENCE_UNAVAILABLE,
                "canonical prize evidence became inconsistent while ranking.",
            )
        value: dict[str, object] = {
            "prize": {
                "prize_tier": tier,
                "tier_order": self._tier_sort_key(lottery_type, tier),
                "prize_amount": self._prize_amount(lottery_type, tier),
            },
            "draw_number": observation.draw_number,
            "draw_date": observation.draw_date,
            "match": {
                "main_matches": result.zone1_hits,
                "special_match": (
                    result.zone2_hit if self._has_special_number(lottery_type) else None
                ),
                "secondary_match": (
                    result.zone2_hit if self._has_secondary_zone(lottery_type) else None
                ),
                "lottery_type": lottery_type.value,
            },
        }
        if include_ticket:
            value["ticket"] = {
                "ticket_position": ticket.position,
                "main_numbers": list(ticket.main_numbers),
                "special_number": (
                    ticket.special_number if self._has_special_number(lottery_type) else None
                ),
                "secondary_number": (
                    ticket.special_number if self._has_secondary_zone(lottery_type) else None
                ),
            }
        return value

    def _evaluate_ticket(
        self, lottery_type: LotteryType, observation: _Observation, ticket: _TicketEvidence
    ) -> PrizeEvaluationResult:
        contract = self._rule_contract(lottery_type)
        if ticket.persisted_prize_tier is not None:
            return PrizeEvaluationResult(
                lottery_type=lottery_type,
                is_winner=True,
                prize_tier=ticket.persisted_prize_tier,
                prize_tier_order=ticket.persisted_prize_order,
                zone1_hits=ticket.main_matches,
                zone2_hit=ticket.special_hit,
                prize_rule_version=contract.contract_version,
                prize_rule_provenance="persisted canonical official-prize evidence",
            )
        winning_special: int | None
        predicted_special: int | None
        if contract.special_number_count == 0:
            winning_special = None
            predicted_special = None
        elif lottery_type is LotteryType.BIG_LOTTO:
            if len(observation.target_special_numbers) != 1:
                raise LottoLabMcpQueryError(
                    OFFICIAL_PRIZE_EVIDENCE_UNAVAILABLE,
                    "BIG_LOTTO official-prize evidence has no canonical special number.",
                )
            winning_special = observation.target_special_numbers[0]
            predicted_special = None
        else:
            if len(observation.target_special_numbers) != 1 or ticket.special_number is None:
                raise LottoLabMcpQueryError(
                    OFFICIAL_PRIZE_EVIDENCE_UNAVAILABLE,
                    "official-prize evidence is missing the canonical secondary zone.",
                )
            winning_special = observation.target_special_numbers[0]
            predicted_special = ticket.special_number
        try:
            return LOTTERY_PRIZE_EVALUATOR.evaluate(
                lottery_type=lottery_type,
                predicted_main_numbers=ticket.main_numbers,
                predicted_special_number=predicted_special,
                winning_main_numbers=observation.target_main_numbers,
                winning_special_number=winning_special,
            )
        except (NotImplementedError, TypeError, ValueError) as exc:
            raise LottoLabMcpQueryError(
                OFFICIAL_PRIZE_EVIDENCE_UNAVAILABLE,
                "official-prize evidence could not be verified by the canonical evaluator.",
            ) from exc

    def _tier_sort_key(self, lottery_type: LotteryType, tier: str) -> int:
        if lottery_type is LotteryType.BIG_LOTTO:
            prize_rule = BIG_LOTTO_RULE_CONTRACT.prize_rule
            if prize_rule is not None:
                for index, item in enumerate(prize_rule.tiers, start=1):
                    if item.tier_id.value == tier:
                        return index
            raise LottoLabMcpQueryError(
                OFFICIAL_PRIZE_EVIDENCE_UNAVAILABLE,
                "BIG_LOTTO official-prize tier is not in the canonical rule contract.",
            )
        try:
            return int(tier)
        except ValueError:
            # POWER_LOTTO and DAILY_539 expose their order through the typed
            # evaluator result; this fallback only handles canonical IDs when
            # ordering a persisted distribution without a result object.
            return {
                "FIRST": 1,
                "SECOND": 2,
                "THIRD": 3,
                "FOURTH": 4,
                "FIFTH": 5,
                "SIXTH": 6,
                "SEVENTH": 7,
                "EIGHTH": 8,
                "NINTH": 9,
                "GENERAL": 10,
            }.get(tier, 10_000)

    def _prize_amount(self, lottery_type: LotteryType, tier: str) -> int | None:
        if lottery_type is LotteryType.BIG_LOTTO:
            return None
        from lottolab.domain.prize_evaluation import (
            DAILY_FIVE39_PRIZE_RULE_CONTRACT,
            POWER_LOTTO_PRIZE_RULE_CONTRACT,
        )

        rules = (
            POWER_LOTTO_PRIZE_RULE_CONTRACT
            if lottery_type is LotteryType.POWER_LOTTO
            else DAILY_FIVE39_PRIZE_RULE_CONTRACT
        )
        for item in rules.tiers:
            if item.tier_id.value == tier:
                return item.prize_amount
        return None

    @staticmethod
    def _numeric_draw_number(value: str) -> int:
        try:
            return int(value)
        except (TypeError, ValueError) as exc:
            raise LottoLabMcpQueryError(
                EVIDENCE_UNAVAILABLE,
                "stored draw identity is malformed.",
            ) from exc

    def _best_match_key(
        self,
        value: tuple[int, bool, _Observation, _TicketEvidence],
    ) -> tuple[int, int, str, int, int]:
        main_matches, special_hit, observation, ticket = value
        return (
            -main_matches,
            -int(special_hit),
            observation.draw_date,
            self._numeric_draw_number(observation.draw_number),
            ticket.position,
        )

    def _best_match_payload(
        self,
        value: tuple[int, bool, _Observation, _TicketEvidence],
    ) -> dict[str, object]:
        main_matches, special_hit, observation, ticket = value
        return {
            "main_matches": main_matches,
            "special_hit": special_hit,
            "draw_number": observation.draw_number,
            "draw_date": observation.draw_date,
            "ticket_position": ticket.position,
        }

    @staticmethod
    def _has_special_number(lottery_type: LotteryType) -> bool:
        return lottery_type in (LotteryType.BIG_LOTTO, LotteryType.POWER_LOTTO)

    @staticmethod
    def _has_secondary_zone(lottery_type: LotteryType) -> bool:
        return lottery_type is LotteryType.POWER_LOTTO

    def _strategy_payload(
        self, ref: _StrategyRef, lottery_type: LotteryType
    ) -> dict[str, object]:
        return {
            "strategy_id": ref.strategy_id,
            "display_name": ref.display_name,
            "strategy_version": ref.strategy_version,
            "replicate": ref.replicate,
            "lottery_type": lottery_type.value,
            "native_ticket_count": ref.native_ticket_count,
        }

    @staticmethod
    def _draw_identity_payload(
        lottery_type: LotteryType, record: HistoricalDrawIdentity
    ) -> dict[str, object]:
        draw_number = record.draw_number
        draw_date = record.draw_date
        main_numbers = list(record.main_numbers)
        special_numbers = list(record.special_numbers)
        if lottery_type is LotteryType.BIG_LOTTO:
            return {
                "draw_number": draw_number,
                "draw_date": draw_date,
                "main_numbers": main_numbers,
                "special_numbers": special_numbers,
                "secondary_numbers": [],
            }
        if lottery_type is LotteryType.POWER_LOTTO:
            return {
                "draw_number": draw_number,
                "draw_date": draw_date,
                "main_numbers": main_numbers,
                "special_numbers": [],
                "secondary_numbers": special_numbers,
            }
        return {
            "draw_number": draw_number,
            "draw_date": draw_date,
            "main_numbers": main_numbers,
            "special_numbers": [],
            "secondary_numbers": [],
        }

    @staticmethod
    def _prize_sort_key_from_payload(value: object) -> int:
        if not isinstance(value, dict):
            return 10_000
        payload = cast(dict[str, object], value)
        prize = payload.get("prize_tier")
        if not isinstance(prize, str):
            return 10_000
        tier_order = payload.get("tier_order")
        return tier_order if type(tier_order) is int else 10_000


__all__ = [
    "AUTHORITY_NOT_FOUND",
    "AUTHORITY_UNRESOLVED",
    "EVIDENCE_UNAVAILABLE",
    "HISTORICAL_RESULTS_NOT_CONFIGURED",
    "HISTORICAL_RESULTS_UNAVAILABLE",
    "INVALID_ARGUMENTS",
    "INVALID_CRITERION",
    "INVALID_LOTTERY_TYPE",
    "INVALID_MATCH_THRESHOLD",
    "INVALID_STATUS",
    "INVALID_WINDOW",
    "MULTIPLE_AUTHORITIES_REQUIRES_SELECTION",
    "OFFICIAL_PRIZE_EVIDENCE_UNAVAILABLE",
    "RUN_NOT_FOUND",
    "SCHEMA_MISMATCH",
    "STORAGE_UNAVAILABLE",
    "STRATEGY_NOT_FOUND",
    "LottoLabMcpQueryError",
    "LottoLabMcpQueryService",
    "ReadOnlyAuthorityDescriptor",
    "ReadOnlyHistoricalSources",
]
