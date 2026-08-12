"""Two-phase orchestration for the shared prospective-observer contracts.

``PredictionPhaseService`` owns no outcome reader or prize evaluator and gives
the producer only an outcome-free :class:`PredictionContext`.  Scoring is a
separate service that can run after an immutable prediction exists.  Storage is
an explicit create-once port; the in-memory implementation is a bounded
reference implementation, not a production database adapter.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from threading import RLock
from typing import Protocol, runtime_checkable

from lottolab.application.ports import LotteryPrizeEvaluator
from lottolab.domain.draws import LotteryType
from lottolab.domain.lottery_rules import (
    LOTTERY_RULE_CONTRACTS,
    LotteryRuleContract,
    resolve_lottery_rule_contract,
)
from lottolab.domain.prize_evaluation import LOTTERY_PRIZE_EVALUATOR, PrizeEvaluationResult
from lottolab.domain.prospective_observer import (
    CreateOnceOutcome,
    DiagnosticEvent,
    GameEvaluation,
    MatchedBaselineRef,
    OfficialOutcome,
    PredictionAvailability,
    PredictionContext,
    PredictionDraft,
    PredictionEntry,
    PredictionEntryDraft,
    PredictionPhaseRequest,
    PredictionRecord,
    ProducerFingerprint,
    ProspectiveObservationIdentity,
    ProspectiveSelection,
    ScoreAvailability,
    ScoreEntry,
    ScoreRecord,
)


class ProspectiveObserverError(RuntimeError):
    """Base class for fail-closed prospective-observer errors."""


class PredictionConflictError(ProspectiveObserverError):
    """A logical observation identity already contains different prediction content."""


class ScoreConflictError(ProspectiveObserverError):
    """A logical observation identity already contains different score content."""


class ProducerFingerprintDriftError(ProspectiveObserverError):
    """Current producer authority differs from the immutable prediction authority."""


class PredictionRequiredError(ProspectiveObserverError):
    """Scoring was requested before an immutable prediction existed."""


class GameContractError(ProspectiveObserverError):
    """A prediction or outcome violates its lottery-specific mechanics."""


class PredictionSyncStatus(StrEnum):
    CREATED = "CREATED"
    EXACT_IDEMPOTENT_NO_OP = "EXACT_IDEMPOTENT_NO_OP"


class ScoreSyncStatus(StrEnum):
    CREATED = "CREATED"
    EXACT_IDEMPOTENT_NO_OP = "EXACT_IDEMPOTENT_NO_OP"
    OUTCOME_UNAVAILABLE = "OUTCOME_UNAVAILABLE"


@runtime_checkable
class PredictionProducer(Protocol):
    """Phase A producer boundary: the input type has no outcome payload."""

    def predict(self, context: PredictionContext) -> PredictionDraft:
        """Produce one deterministic draft from strictly causal inputs."""
        ...


@runtime_checkable
class ProspectiveObservationStore(Protocol):
    """Create-once prediction/score boundary implemented by consumer infrastructure."""

    def get_prediction(
        self, identity: ProspectiveObservationIdentity
    ) -> PredictionRecord | None: ...

    def create_prediction(self, record: PredictionRecord) -> CreateOnceOutcome:
        """Atomically insert, accept equal canonical material, or report conflict."""
        ...

    def get_score(self, identity: ProspectiveObservationIdentity) -> ScoreRecord | None: ...

    def create_score(self, record: ScoreRecord) -> CreateOnceOutcome:
        """Atomically insert, accept equal canonical material, or report conflict."""
        ...


@runtime_checkable
class ProspectiveGameContract(Protocol):
    """Lottery-owned validation and evaluation boundary consumed by the core."""

    @property
    def lottery_type(self) -> LotteryType: ...

    def validate_prediction_entry(self, entry: PredictionEntryDraft) -> None: ...

    def evaluate(self, entry: PredictionEntry, outcome: OfficialOutcome) -> GameEvaluation: ...


@dataclass(frozen=True, slots=True)
class PredictionSyncResult:
    status: PredictionSyncStatus
    prediction: PredictionRecord


@dataclass(frozen=True, slots=True)
class ScorePhaseRequest:
    identity: ProspectiveObservationIdentity
    producer_fingerprint: ProducerFingerprint
    outcome: OfficialOutcome | None

    def __post_init__(self) -> None:
        if type(self.identity) is not ProspectiveObservationIdentity:
            raise ValueError("identity must be a ProspectiveObservationIdentity")
        if type(self.producer_fingerprint) is not ProducerFingerprint:
            raise ValueError("producer_fingerprint must be a ProducerFingerprint")
        if self.outcome is not None and type(self.outcome) is not OfficialOutcome:
            raise ValueError("outcome must be an OfficialOutcome or None")


@dataclass(frozen=True, slots=True)
class ScoreSyncResult:
    status: ScoreSyncStatus
    score: ScoreRecord | None


class InMemoryProspectiveObservationStore:
    """Atomic-by-operation reference store with immutable create-once cells."""

    def __init__(self) -> None:
        self._predictions: dict[ProspectiveObservationIdentity, PredictionRecord] = {}
        self._scores: dict[ProspectiveObservationIdentity, ScoreRecord] = {}
        self._lock = RLock()

    def get_prediction(
        self, identity: ProspectiveObservationIdentity
    ) -> PredictionRecord | None:
        with self._lock:
            return self._predictions.get(identity)

    def create_prediction(self, record: PredictionRecord) -> CreateOnceOutcome:
        with self._lock:
            existing = self._predictions.get(record.identity)
            if existing is None:
                self._predictions[record.identity] = record
                return CreateOnceOutcome.INSERTED
            if (
                existing.prediction_hash == record.prediction_hash
                and existing.canonical_material() == record.canonical_material()
            ):
                return CreateOnceOutcome.ALREADY_PRESENT
            return CreateOnceOutcome.CONFLICT

    def get_score(self, identity: ProspectiveObservationIdentity) -> ScoreRecord | None:
        with self._lock:
            return self._scores.get(identity)

    def create_score(self, record: ScoreRecord) -> CreateOnceOutcome:
        with self._lock:
            existing = self._scores.get(record.identity)
            if existing is None:
                self._scores[record.identity] = record
                return CreateOnceOutcome.INSERTED
            if (
                existing.score_hash == record.score_hash
                and existing.canonical_material() == record.canonical_material()
            ):
                return CreateOnceOutcome.ALREADY_PRESENT
            return CreateOnceOutcome.CONFLICT

    @property
    def predictions(self) -> tuple[PredictionRecord, ...]:
        with self._lock:
            return tuple(self._predictions.values())

    @property
    def scores(self) -> tuple[ScoreRecord, ...]:
        with self._lock:
            return tuple(self._scores.values())


@dataclass(frozen=True, slots=True)
class RepositoryLotteryGameContract:
    """Composition over the repository's existing rule and prize-evaluator contracts."""

    lottery_type: LotteryType
    rule_contract: LotteryRuleContract
    evaluator: LotteryPrizeEvaluator

    def __post_init__(self) -> None:
        if type(self.lottery_type) is not LotteryType:
            raise ValueError("lottery_type must be a LotteryType")
        if type(self.rule_contract) is not LotteryRuleContract:
            raise ValueError("rule_contract must be a LotteryRuleContract")
        if self.rule_contract.lottery_type is not self.lottery_type:
            raise ValueError("rule_contract has the wrong lottery type")

    def validate_prediction_entry(self, entry: PredictionEntryDraft) -> None:
        if entry.availability is PredictionAvailability.UNAVAILABLE:
            return
        assert entry.matched_baseline is not None
        self._validate_available_shape(entry.selections, entry.matched_baseline)

    def evaluate(self, entry: PredictionEntry, outcome: OfficialOutcome) -> GameEvaluation:
        if entry.availability is not PredictionAvailability.AVAILABLE:
            raise GameContractError("an unavailable prediction cannot be evaluated")
        assert entry.matched_baseline is not None
        self._validate_available_shape(entry.selections, entry.matched_baseline)
        self._validate_outcome(outcome)
        results = tuple(
            self.evaluator.evaluate(
                lottery_type=self.lottery_type,
                predicted_main_numbers=selection.main_numbers,
                predicted_special_number=selection.special_number,
                winning_main_numbers=outcome.main_numbers,
                winning_special_number=outcome.special_number,
            )
            for selection in entry.selections
        )
        return GameEvaluation(
            lottery_type=self.lottery_type,
            ticket_results=results,
            diagnostic_events=self._diagnostic_events(results),
        )

    def _validate_available_shape(
        self,
        selections: tuple[ProspectiveSelection, ...],
        baseline: MatchedBaselineRef,
    ) -> None:
        if baseline.lottery_type is not self.lottery_type:
            raise GameContractError("matched baseline has the wrong lottery type")
        if baseline.ticket_count != len(selections) or baseline.candidate_sizes != tuple(
            len(selection.main_numbers) for selection in selections
        ):
            raise GameContractError("matched baseline does not match prediction shape")
        for selection in selections:
            self._validate_main_numbers(selection.main_numbers, "predicted_main_numbers")
            self._validate_special_number(
                selection.special_number,
                selection.main_numbers,
                outcome=False,
            )

    def _validate_outcome(self, outcome: OfficialOutcome) -> None:
        if outcome.lottery_type is not self.lottery_type:
            raise GameContractError("official outcome has the wrong lottery type")
        self._validate_main_numbers(outcome.main_numbers, "winning_main_numbers")
        self._validate_special_number(
            outcome.special_number,
            outcome.main_numbers,
            outcome=True,
        )

    def _validate_main_numbers(self, numbers: tuple[int, ...], label: str) -> None:
        rule = self.rule_contract
        if len(numbers) != rule.main_number_count:
            raise GameContractError(
                f"{label} must contain exactly {rule.main_number_count} numbers"
            )
        if any(type(number) is not int for number in numbers):
            raise GameContractError(f"{label} must contain exact built-in integers")
        if any(not rule.main_number_min <= number <= rule.main_number_max for number in numbers):
            raise GameContractError(
                f"{label} must fall within [{rule.main_number_min}..{rule.main_number_max}]"
            )
        if len(numbers) != len(set(numbers)):
            raise GameContractError(f"{label} must not contain duplicates")
        if numbers != tuple(sorted(numbers)):
            raise GameContractError(f"{label} must use canonical ascending order")

    def _validate_special_number(
        self,
        number: int | None,
        main_numbers: tuple[int, ...],
        *,
        outcome: bool,
    ) -> None:
        if self.lottery_type is LotteryType.DAILY_539:
            if number is not None:
                raise GameContractError("DAILY_539 has no special-number semantics")
            return
        if self.lottery_type is LotteryType.BIG_LOTTO and not outcome:
            if number is not None:
                raise GameContractError("BIG_LOTTO tickets must not predict a special number")
            return
        if type(number) is not int:
            label = "outcome special number" if outcome else "ticket second-zone number"
            raise GameContractError(f"{label} is required")
        rule = self.rule_contract
        if not rule.special_number_min <= number <= rule.special_number_max:
            raise GameContractError("special number is outside the game contract range")
        if not rule.main_special_overlap_allowed and number in main_numbers:
            raise GameContractError("outcome special number must not overlap main numbers")

    def _diagnostic_events(
        self, results: tuple[PrizeEvaluationResult, ...]
    ) -> tuple[DiagnosticEvent, ...]:
        if self.lottery_type is LotteryType.BIG_LOTTO:
            return (
                DiagnosticEvent(
                    "B649_ANY_M2_PLUS",
                    any(result.zone1_hits >= 2 for result in results),
                ),
                DiagnosticEvent(
                    "B649_ANY_SPECIAL_HIT",
                    any(result.zone2_hit for result in results),
                ),
            )
        if self.lottery_type is LotteryType.DAILY_539:
            return (
                DiagnosticEvent(
                    "T539_ANY_M2_PLUS",
                    any(result.zone1_hits >= 2 for result in results),
                ),
            )
        return (
            DiagnosticEvent(
                "P638_ANY_ZONE1_M2_PLUS",
                any(result.zone1_hits >= 2 for result in results),
            ),
            DiagnosticEvent(
                "P638_ANY_ZONE2_HIT",
                any(result.zone2_hit for result in results),
            ),
        )


def _repository_game_contract(
    lottery_type: LotteryType,
    evaluator: LotteryPrizeEvaluator,
) -> RepositoryLotteryGameContract:
    rule = resolve_lottery_rule_contract(lottery_type, LOTTERY_RULE_CONTRACTS)
    if rule is None:
        raise GameContractError(f"no active rule contract for {lottery_type.value}")
    return RepositoryLotteryGameContract(lottery_type, rule, evaluator)


def big_lotto_game_contract(
    evaluator: LotteryPrizeEvaluator = LOTTERY_PRIZE_EVALUATOR,
) -> RepositoryLotteryGameContract:
    return _repository_game_contract(LotteryType.BIG_LOTTO, evaluator)


def daily_539_game_contract(
    evaluator: LotteryPrizeEvaluator = LOTTERY_PRIZE_EVALUATOR,
) -> RepositoryLotteryGameContract:
    return _repository_game_contract(LotteryType.DAILY_539, evaluator)


def power_lotto_game_contract(
    evaluator: LotteryPrizeEvaluator = LOTTERY_PRIZE_EVALUATOR,
) -> RepositoryLotteryGameContract:
    return _repository_game_contract(LotteryType.POWER_LOTTO, evaluator)


def repository_game_contracts() -> Mapping[LotteryType, ProspectiveGameContract]:
    return {
        LotteryType.BIG_LOTTO: big_lotto_game_contract(),
        LotteryType.DAILY_539: daily_539_game_contract(),
        LotteryType.POWER_LOTTO: power_lotto_game_contract(),
    }


class PredictionPhaseService:
    """Create or reproduce one immutable outcome-free prediction record."""

    def __init__(
        self,
        *,
        store: ProspectiveObservationStore,
        producer: PredictionProducer,
        game_contracts: Mapping[LotteryType, ProspectiveGameContract],
        clock: Callable[[], datetime],
    ) -> None:
        self._store = store
        self._producer = producer
        self._game_contracts = _validated_contracts(game_contracts)
        self._clock = clock

    def sync(self, request: PredictionPhaseRequest) -> PredictionSyncResult:
        identity = ProspectiveObservationIdentity.from_context(request.context)
        existing = self._store.get_prediction(identity)
        if existing is not None and (
            existing.producer_fingerprint != request.context.producer_fingerprint
        ):
            raise ProducerFingerprintDriftError(
                "producer fingerprint differs from immutable prediction authority"
            )
        draft = self._producer.predict(request.context)
        contract = self._game_contract(request.context.target.lottery_type)
        for entry in draft.entries:
            contract.validate_prediction_entry(entry)
        predicted_at = existing.predicted_at if existing is not None else self._clock()
        record = PredictionRecord.create(
            request=request,
            draft=draft,
            predicted_at=predicted_at,
        )
        outcome = self._store.create_prediction(record)
        if outcome is CreateOnceOutcome.CONFLICT:
            raise PredictionConflictError(
                "prediction identity already contains different immutable content"
            )
        if outcome is CreateOnceOutcome.INSERTED:
            return PredictionSyncResult(PredictionSyncStatus.CREATED, record)
        persisted = self._store.get_prediction(identity)
        if (
            persisted is None
            or persisted.prediction_hash != record.prediction_hash
            or persisted.canonical_material() != record.canonical_material()
        ):
            raise PredictionConflictError(
                "store reported an idempotent prediction without equal persisted content"
            )
        return PredictionSyncResult(
            PredictionSyncStatus.EXACT_IDEMPOTENT_NO_OP,
            persisted,
        )

    def _game_contract(self, lottery_type: LotteryType) -> ProspectiveGameContract:
        try:
            return self._game_contracts[lottery_type]
        except KeyError as exc:
            raise GameContractError(
                f"no prospective game contract for {lottery_type.value}"
            ) from exc


class ScoringPhaseService:
    """Create or reproduce a score only after its prediction is immutable."""

    def __init__(
        self,
        *,
        store: ProspectiveObservationStore,
        game_contracts: Mapping[LotteryType, ProspectiveGameContract],
        clock: Callable[[], datetime],
    ) -> None:
        self._store = store
        self._game_contracts = _validated_contracts(game_contracts)
        self._clock = clock

    def sync(self, request: ScorePhaseRequest) -> ScoreSyncResult:
        prediction = self._store.get_prediction(request.identity)
        if prediction is None:
            raise PredictionRequiredError("score requires an immutable prediction")
        if prediction.producer_fingerprint != request.producer_fingerprint:
            raise ProducerFingerprintDriftError(
                "producer fingerprint differs from immutable prediction authority"
            )
        if request.outcome is None:
            return ScoreSyncResult(ScoreSyncStatus.OUTCOME_UNAVAILABLE, None)
        outcome = request.outcome
        if (
            outcome.lottery_type is not request.identity.lottery_type
            or outcome.draw_number != request.identity.target_draw_number
            or outcome.draw_date != request.identity.target_draw_date
        ):
            raise GameContractError("official outcome identity does not match prediction")
        contract = self._game_contract(request.identity.lottery_type)
        entries = tuple(self._score_entry(contract, entry, outcome) for entry in prediction.entries)
        existing = self._store.get_score(request.identity)
        scored_at = existing.scored_at if existing is not None else self._clock()
        record = ScoreRecord.create(
            prediction=prediction,
            outcome=outcome,
            entries=entries,
            scored_at=scored_at,
        )
        create_outcome = self._store.create_score(record)
        if create_outcome is CreateOnceOutcome.CONFLICT:
            raise ScoreConflictError("score identity already contains different immutable content")
        if create_outcome is CreateOnceOutcome.INSERTED:
            return ScoreSyncResult(ScoreSyncStatus.CREATED, record)
        persisted = self._store.get_score(request.identity)
        if (
            persisted is None
            or persisted.score_hash != record.score_hash
            or persisted.canonical_material() != record.canonical_material()
        ):
            raise ScoreConflictError(
                "store reported an idempotent score without equal persisted content"
            )
        return ScoreSyncResult(ScoreSyncStatus.EXACT_IDEMPOTENT_NO_OP, persisted)

    def _score_entry(
        self,
        contract: ProspectiveGameContract,
        prediction: PredictionEntry,
        outcome: OfficialOutcome,
    ) -> ScoreEntry:
        if prediction.availability is PredictionAvailability.UNAVAILABLE:
            return ScoreEntry(
                member_id=prediction.member_id,
                prediction_hash=prediction.prediction_hash,
                availability=ScoreAvailability.UNAVAILABLE_PREDICTION,
                evaluation=None,
            )
        return ScoreEntry(
            member_id=prediction.member_id,
            prediction_hash=prediction.prediction_hash,
            availability=ScoreAvailability.SCORED,
            evaluation=contract.evaluate(prediction, outcome),
        )

    def _game_contract(self, lottery_type: LotteryType) -> ProspectiveGameContract:
        try:
            return self._game_contracts[lottery_type]
        except KeyError as exc:
            raise GameContractError(
                f"no prospective game contract for {lottery_type.value}"
            ) from exc


def _validated_contracts(
    contracts: Mapping[LotteryType, ProspectiveGameContract],
) -> dict[LotteryType, ProspectiveGameContract]:
    copied = dict(contracts)
    for lottery_type, contract in copied.items():
        if type(lottery_type) is not LotteryType or contract.lottery_type is not lottery_type:
            raise ValueError("game contract mapping contains an identity mismatch")
    return copied
