"""Attribute one verified sealed recommendation to one exact official outcome."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import cast

from lottolab.application.ports import (
    LotteryPrizeEvaluator,
    NextDrawOfficialOutcomeReader,
    NextDrawRecommendationSealAuthorityReader,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.next_draw_outcome_attribution import (
    BIG_LOTTO_PRIZE_EVALUATION_CONTRACT_SHA256,
    NextDrawBucketOutcomeAttribution,
    NextDrawOfficialOutcome,
    NextDrawOutcomeAttribution,
    NextDrawOutcomeAttributionContractError,
    NextDrawStrategyOutcomeAttribution,
    NextDrawTicketOutcomeAttribution,
    current_big_lotto_prize_evaluation_contract_sha256,
)
from lottolab.domain.next_draw_recommendation import BucketAvailabilityStatus
from lottolab.domain.next_draw_recommendation_seal import (
    SealedRecommendationBucket,
    SealedStrategyTickets,
    TicketSealStatus,
)

_SHA256 = re.compile(r"[0-9a-f]{64}", flags=re.ASCII)
_DRAW_NUMBER = re.compile(r"[0-9]{1,32}", flags=re.ASCII)


class OfficialNextDrawOutcomeNotFoundError(LookupError):
    """DRAW_DATA_V3 has no exact successful outcome for the sealed target."""


class NextDrawP4ScoringContractDriftError(RuntimeError):
    """The executing BIG_LOTTO rule contract no longer matches the frozen SHA."""


@dataclass(frozen=True, slots=True)
class AttributeSealedNextDrawOutcomeRequest:
    """Explicit authority inputs for one deterministic P4 attribution."""

    seal_file: Path
    expected_seal_file_sha256: str
    expected_seal_digest: str
    lottery_type: LotteryType
    target_draw_number: str
    target_draw_date: date

    def __post_init__(self) -> None:
        if not isinstance(cast(object, self.seal_file), Path):
            raise NextDrawOutcomeAttributionContractError("seal_file must be a Path")
        for label, value in (
            ("expected_seal_file_sha256", self.expected_seal_file_sha256),
            ("expected_seal_digest", self.expected_seal_digest),
        ):
            if type(value) is not str or _SHA256.fullmatch(value) is None:
                raise NextDrawOutcomeAttributionContractError(
                    f"{label} must be a lowercase SHA-256 digest"
                )
        if type(self.lottery_type) is not LotteryType:
            raise NextDrawOutcomeAttributionContractError(
                "lottery_type must be a LotteryType"
            )
        if _DRAW_NUMBER.fullmatch(self.target_draw_number) is None:
            raise NextDrawOutcomeAttributionContractError("target_draw_number is invalid")
        if type(self.target_draw_date) is not date:
            raise NextDrawOutcomeAttributionContractError("target_draw_date must be a date")


class AttributeSealedNextDrawOutcome:
    """Score sealed tickets only; never rerank, regenerate, or execute strategies."""

    def __init__(
        self,
        *,
        seal_reader: NextDrawRecommendationSealAuthorityReader,
        outcome_reader: NextDrawOfficialOutcomeReader,
        prize_evaluator: LotteryPrizeEvaluator,
    ) -> None:
        self._seal_reader = seal_reader
        self._outcome_reader = outcome_reader
        self._prize_evaluator = prize_evaluator

    def execute(
        self, request: AttributeSealedNextDrawOutcomeRequest
    ) -> NextDrawOutcomeAttribution:
        if request.lottery_type is not LotteryType.BIG_LOTTO:
            raise NextDrawOutcomeAttributionContractError(
                "P4 supports BIG_LOTTO_PRIZE_EVALUATION_V1 only"
            )
        if (
            current_big_lotto_prize_evaluation_contract_sha256()
            != BIG_LOTTO_PRIZE_EVALUATION_CONTRACT_SHA256
        ):
            raise NextDrawP4ScoringContractDriftError(
                "BIG_LOTTO scoring contract no longer matches the frozen P4 SHA"
            )

        seal = self._seal_reader.read_verified_seal(
            request.seal_file,
            expected_file_sha256=request.expected_seal_file_sha256,
            expected_seal_digest=request.expected_seal_digest,
            lottery_type=request.lottery_type,
            target_draw_number=request.target_draw_number,
            target_draw_date=request.target_draw_date,
        )
        outcome = self._outcome_reader.read_official_outcome(
            request.lottery_type,
            request.target_draw_number,
            request.target_draw_date,
        )
        if outcome is None:
            raise OfficialNextDrawOutcomeNotFoundError(
                "no exact successful DRAW_DATA_V3 outcome exists for the sealed target"
            )

        buckets = tuple(self._attribute_bucket(bucket, outcome) for bucket in seal.buckets)
        return NextDrawOutcomeAttribution.create(
            seal=seal,
            official_outcome=outcome,
            buckets=buckets,
        )

    def _attribute_bucket(
        self,
        bucket: SealedRecommendationBucket,
        outcome: NextDrawOfficialOutcome,
    ) -> NextDrawBucketOutcomeAttribution:
        availability = BucketAvailabilityStatus(bucket.availability)
        strategies = tuple(
            self._attribute_strategy(strategy, outcome)
            for strategy in bucket.sealed_tickets
        )
        return NextDrawBucketOutcomeAttribution(
            native_ticket_count=bucket.native_ticket_count,
            availability=availability,
            total_candidate_count=bucket.total_candidate_count,
            strategies=strategies,
        )

    def _attribute_strategy(
        self,
        strategy: SealedStrategyTickets,
        outcome: NextDrawOfficialOutcome,
    ) -> NextDrawStrategyOutcomeAttribution:
        if strategy.status is TicketSealStatus.OK:
            ticket_attributions = tuple(
                self._attribute_ticket(position, ticket, outcome)
                for position, ticket in enumerate(strategy.tickets, start=1)
            )
        else:
            ticket_attributions = ()
        return NextDrawStrategyOutcomeAttribution(
            rank=strategy.rank,
            strategy_id=strategy.strategy_id,
            strategy_name=strategy.strategy_name,
            seal_status=strategy.status,
            detail=strategy.detail,
            ticket_attributions=ticket_attributions,
        )

    def _attribute_ticket(
        self,
        position: int,
        ticket: tuple[int, ...],
        outcome: NextDrawOfficialOutcome,
    ) -> NextDrawTicketOutcomeAttribution:
        evaluation = self._prize_evaluator.evaluate(
            lottery_type=LotteryType.BIG_LOTTO,
            predicted_main_numbers=ticket,
            predicted_special_number=None,
            winning_main_numbers=outcome.winning_main_numbers,
            winning_special_number=outcome.winning_special_number,
        )
        if evaluation.lottery_type is not LotteryType.BIG_LOTTO:
            raise NextDrawOutcomeAttributionContractError(
                "prize evaluator returned the wrong lottery contract"
            )
        return NextDrawTicketOutcomeAttribution(
            ticket_position=position,
            predicted_main_numbers=ticket,
            is_winner=evaluation.is_winner,
            prize_tier=evaluation.prize_tier,
            main_number_hit_count=evaluation.zone1_hits,
            special_number_hit=evaluation.zone2_hit,
            prize_rule_version=evaluation.prize_rule_version,
            prize_rule_provenance=evaluation.prize_rule_provenance,
        )


__all__ = [
    "AttributeSealedNextDrawOutcome",
    "AttributeSealedNextDrawOutcomeRequest",
    "NextDrawP4ScoringContractDriftError",
    "OfficialNextDrawOutcomeNotFoundError",
]
