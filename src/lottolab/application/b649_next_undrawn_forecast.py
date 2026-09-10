"""Canonical OFFICIAL_ANY_PRIZE ranking and dedicated pre-outcome sealing.

History and replay evidence are explicit inputs. This module never refreshes
evidence, opens a database, schedules a job, or calls the frozen campaign.
"""

from __future__ import annotations

import json
import random
from collections.abc import Callable, Iterator, Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Protocol, cast

from lottolab.application.historical_success_random_baseline import (
    OFFICIAL_ANY_PRIZE_BASELINE_POLICY_VERSION,
    official_any_prize_probability,
)
from lottolab.application.pre_outcome_target_operational import OperationalRegistrationResult
from lottolab.application.prospective_observer import (
    InMemoryProspectiveObservationStore,
    ProspectiveObservationStore,
    repository_game_contracts,
)
from lottolab.application.prospective_prediction_seal import (
    RunnablePredictionSealService,
    RunnableTargetRegistrationService,
)
from lottolab.application.use_cases.generate_bet import (
    GenerateOneBet,
    GenerateOneBetInput,
    GenerateOneBetStatus,
    GeneratePortfolio,
    GeneratePortfolioStatus,
    instantiate_adapter,
    instantiate_portfolio_adapter,
)
from lottolab.application.use_cases.replay_exact_native_targets import causal_row, seed_metadata
from lottolab.domain.b649_next_undrawn_forecast import (
    COHORT_ID,
    OUTPUT_BUCKETS,
    REQUIRED_HISTORY_CUTOFF,
    CandidateEvidence,
    ClassifiedObservation,
    ExactMetric,
    ForecastBundle,
    ForecastContractError,
    ForecastIdentity,
    GenerationConfig,
    ObservationStatus,
    ReplayObservation,
    TicketSet,
    canonical_json,
    catalog_exclusion,
    digest,
    history_ref,
    rank_candidates,
    rational_payload,
    require_digest,
    validate_history,
    validate_tickets,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.exact_native_replay import Draw
from lottolab.domain.pre_outcome_target import TargetAnnouncement
from lottolab.domain.prize_evaluation import evaluate_lottery_prize
from lottolab.domain.prospective_observer import (
    CausalHistoryRef,
    FrozenCohortRef,
    MatchedBaselineRef,
    ObservationTarget,
    PredictionContext,
    PredictionDraft,
    PredictionEntryDraft,
    PredictionRecord,
    ProducerDependency,
    ProducerFingerprint,
    ProspectiveObservationIdentity,
    ProspectiveSelection,
    TemporalProvenance,
)
from lottolab.domain.strategies import ResponseShape, StrategyDescriptor
from lottolab.strategies.catalog import StrategyCatalog, production_catalog
from lottolab.strategies.executable_registry import ExecutableRegistry


class ForecastGenerationError(RuntimeError):
    """A winning strategy could not emit its exact native output."""


class ForecastTimingError(RuntimeError):
    """Fresh pre-persistence time, schedule, or outcome presence check failed."""


class ForecastConflictError(RuntimeError):
    """An existing bundle identity contains different immutable content."""


class NativeTicketGenerator(Protocol):
    def generate(
        self, descriptor: StrategyDescriptor, config: GenerationConfig, history: tuple[Draw, ...]
    ) -> TicketSet: ...


def native_generation_config(
    descriptor: StrategyDescriptor,
    history: tuple[Draw, ...],
    *,
    seed: int | None = None,
) -> GenerationConfig:
    if seed is not None and type(seed) is not int:
        raise ForecastContractError("seed must be an exact integer")
    rng = seed_metadata(descriptor, tuple(causal_row(d) for d in history))
    parameters: dict[str, object] = {"adapter_parameters": "CANONICAL_DEFAULTS"}
    rng["rng_source"] = descriptor.adapter_path
    # The canonical portfolio use case threads the caller seed only through
    # with_seed. In every other path it is bookkeeping, not generation state.
    explicit_seed = False
    if (
        descriptor.response_shape is ResponseShape.PORTFOLIO
        and descriptor.adapter_path != "fixture:ticket_snapshot"
    ):
        adapter = ExecutableRegistry(StrategyCatalog((descriptor,))).load_adapter(
            descriptor.strategy_id
        )
        explicit_seed = callable(getattr(adapter, "with_seed", None))
    if explicit_seed:
        if seed is None:
            raise ForecastContractError("EXPLICIT_GENERATION_SEED_REQUIRED")
        parameters["seed"] = seed
        rng.update(
            behavior="SEEDED_STOCHASTIC",
            seed=seed,
            rng_source=f"{descriptor.adapter_path}.with_seed",
            rng_state_rule="GeneratePortfolio calls adapter.with_seed(request.seed)",
            prestate_dependency="causal_history_and_explicit_seed",
        )
    else:
        # Newer catalog contracts can declare an unseeded global stream that
        # the older replay helper's deterministic default does not describe.
        unseeded = tuple(
            sorted(
                value
                for value in descriptor.provenance
                if value.startswith(("randomness:", "rng_sharing:")) and "UNSEEDED" in value
            )
        )
        if unseeded:
            rng.update(
                behavior="UNSEEDED_STOCHASTIC",
                seed=None,
                rng_state_rule=";".join(unseeded),
                prestate_dependency="uncaptured_process_global_rng_state",
            )
    return GenerationConfig(
        descriptor.strategy_id,
        descriptor.version,
        descriptor.native_ticket_count,
        canonical_json(parameters),
        canonical_json(rng),
    )


class CanonicalNativeTicketGenerator:
    """Use each canonical response path without changing descriptor type or K."""

    def __init__(
        self,
        catalog: StrategyCatalog,
        *,
        before_execution: Callable[[str, object], None] | None = None,
    ) -> None:
        self.catalog = catalog
        self.registry = ExecutableRegistry(catalog)
        self.before_execution = before_execution

    def generate(
        self, descriptor: StrategyDescriptor, config: GenerationConfig, history: tuple[Draw, ...]
    ) -> TicketSet:
        if self.catalog.get(descriptor.strategy_id) != descriptor:
            raise ForecastGenerationError("CATALOG_IDENTITY_MISMATCH")
        parameters = cast(dict[str, object], json.loads(config.parameters_json))
        seed = parameters.get("seed")
        if seed is not None and type(seed) is not int:
            raise ForecastGenerationError("INVALID_SEED")
        if native_generation_config(descriptor, history, seed=seed) != config:
            raise ForecastGenerationError("GENERATION_CONFIGURATION_MISMATCH")
        adapter_class = self.registry.load_adapter(descriptor.strategy_id)
        request = GenerateOneBetInput(
            descriptor.strategy_id,
            LotteryType.BIG_LOTTO,
            tuple(causal_row(d) for d in history),
            seed=seed,
        )
        if descriptor.response_shape is ResponseShape.SINGLE_TICKET:
            adapter = instantiate_adapter(descriptor.strategy_id, adapter_class)
            result = GenerateOneBet(
                self.catalog,
                {descriptor.strategy_id: adapter},
                before_execution=self.before_execution,
            ).execute(request)
            if result.status is not GenerateOneBetStatus.OK or result.numbers is None:
                raise ForecastGenerationError(f"SINGLE_TICKET:{result.status}:{result.reason_code}")
            if result.special_number is not None:
                raise ForecastGenerationError("BIG_LOTTO_TICKET_HAS_NO_SEPARATE_SPECIAL_PICK")
            tickets = (result.numbers,)
        else:
            portfolio = instantiate_portfolio_adapter(descriptor.strategy_id, adapter_class)
            result_many = GeneratePortfolio(
                self.catalog,
                {descriptor.strategy_id: portfolio},
                before_execution=self.before_execution,
            ).execute(request)
            if result_many.status is not GeneratePortfolioStatus.OK or result_many.numbers is None:
                raise ForecastGenerationError(
                    f"PORTFOLIO:{result_many.status}:{result_many.reason_code}"
                )
            tickets = result_many.numbers
        validate_tickets(tickets, descriptor.native_ticket_count)
        return tickets


_PROCESS_GLOBAL_RNG_STREAM = "python.random.module"
_PROCESS_GLOBAL_RNG_STATE_FORMAT = "python.random.getstate.v3"


def _process_global_rng_state_digest(state: object) -> str:
    return digest({"format": _PROCESS_GLOBAL_RNG_STATE_FORMAT, "state": state})


def _replay_invocation_identity(
    *,
    descriptor: StrategyDescriptor,
    draw: Draw,
    causal_history_sha256: str,
    configuration: GenerationConfig,
    producer: ProducerFingerprint,
    invocation_ordinal: int,
    prestate_sha256: str,
    poststate_sha256: str,
) -> str:
    payload: dict[str, object] = {
        "causal_history_sha256": causal_history_sha256,
        "draw_date": draw.draw_date.isoformat(),
        "draw_number": draw.draw_number,
        "generation_config_sha256": configuration.sha256,
        "invocation_ordinal": invocation_ordinal,
        "poststate_sha256": poststate_sha256,
        "prestate_sha256": prestate_sha256,
        "producer_fingerprint": producer.digest,
        "state_format": _PROCESS_GLOBAL_RNG_STATE_FORMAT,
        "strategy_id": descriptor.strategy_id,
        "stream": _PROCESS_GLOBAL_RNG_STREAM,
    }
    return canonical_json({**payload, "identity_sha256": digest(payload)})


def _validate_replay_invocation_identity(
    observation: ReplayObservation,
    configuration: GenerationConfig,
) -> None:
    raw = observation.replay_invocation_identity
    if raw is None:
        raise ForecastContractError("REPLAY_RNG_STATE_UNAVAILABLE_REGENERATION_REQUIRED")
    try:
        parsed = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ForecastContractError("INVALID_REPLAY_INVOCATION_IDENTITY") from exc
    if type(parsed) is not dict:
        raise ForecastContractError("INVALID_REPLAY_INVOCATION_IDENTITY")
    payload = cast(dict[str, object], parsed).copy()
    identity_sha256 = payload.pop("identity_sha256", None)
    if type(identity_sha256) is not str or digest(payload) != identity_sha256:
        raise ForecastContractError("INVALID_REPLAY_INVOCATION_IDENTITY")
    expected_keys = {
        "causal_history_sha256",
        "draw_date",
        "draw_number",
        "generation_config_sha256",
        "invocation_ordinal",
        "poststate_sha256",
        "prestate_sha256",
        "producer_fingerprint",
        "state_format",
        "strategy_id",
        "stream",
    }
    if set(payload) != expected_keys:
        raise ForecastContractError("INVALID_REPLAY_INVOCATION_IDENTITY")
    if (
        payload["causal_history_sha256"] != observation.causal_history_sha256
        or payload["draw_date"] != observation.draw_date.isoformat()
        or payload["draw_number"] != observation.draw_number
        or payload["generation_config_sha256"] != configuration.sha256
        or payload["producer_fingerprint"] != observation.producer_fingerprint
        or payload["strategy_id"] != observation.strategy_id
        or payload["state_format"] != _PROCESS_GLOBAL_RNG_STATE_FORMAT
        or payload["stream"] != _PROCESS_GLOBAL_RNG_STREAM
        or type(payload["invocation_ordinal"]) is not int
        or payload["invocation_ordinal"] < 1
    ):
        raise ForecastContractError("REPLAY_INVOCATION_IDENTITY_MISMATCH")
    require_digest(cast(str, payload["prestate_sha256"]))
    require_digest(cast(str, payload["poststate_sha256"]))


def iter_native_replay_observations(
    *,
    target: ObservationTarget,
    history: tuple[Draw, ...],
    catalog: tuple[StrategyDescriptor, ...],
    producer: ProducerFingerprint,
    generator: NativeTicketGenerator,
    seeds: Mapping[str, int] | None = None,
) -> Iterator[ReplayObservation]:
    """Yield typed replay cells using the current native generation contract.

    The target is used only to validate the causal boundary; its outcome is not
    an input. Process-global unseeded strategies run through their native
    adapter unchanged; the exact global RNG state fingerprints and canonical
    invocation ordinal are bound to each resulting observation. Caller seeds
    are passed only where the current generator contract requires them; native
    internal seed rules remain in the generation configuration for each exact
    causal prefix.
    """

    if not history:
        raise ForecastContractError("BIG_LOTTO_FULL_HISTORY_REQUIRED")
    caller_seeds = dict(seeds or {})
    descriptors = tuple(
        sorted(
            (descriptor for descriptor in catalog if catalog_exclusion(descriptor) is None),
            key=lambda descriptor: descriptor.strategy_id,
        )
    )
    descriptor_ids = {descriptor.strategy_id for descriptor in descriptors}
    if len(descriptor_ids) != len(descriptors):
        raise ForecastContractError("DUPLICATE_CATALOG_IDENTITY")
    if set(caller_seeds) - descriptor_ids:
        raise ForecastContractError("SEED_AUTHORITY_OUTSIDE_CANONICAL_UNIVERSE")
    history_authority = history_ref(history)
    validate_history(history, target, history_authority, history[-1].draw_number)
    prefix_authorities = tuple(history_ref(history[:index]) for index in range(len(history)))
    invocation_ordinal = 0

    for descriptor in descriptors:
        caller_seed = caller_seeds.get(descriptor.strategy_id)
        for index, draw in enumerate(history):
            prefix = history[:index]
            try:
                configuration = native_generation_config(
                    descriptor, prefix, seed=caller_seed
                )
            except ForecastContractError as exc:
                raise ForecastContractError(
                    f"REPLAY_SEED_AUTHORITY_REQUIRED:{descriptor.strategy_id}"
                ) from exc
            if index < descriptor.min_history:
                yield ReplayObservation(
                    descriptor.strategy_id,
                    descriptor.version,
                    descriptor.native_ticket_count,
                    draw.draw_number,
                    draw.draw_date,
                    prefix_authorities[index].history_sha256,
                    configuration.sha256,
                    status=ObservationStatus.WARMUP,
                    producer_fingerprint=producer.digest,
                )
                continue

            semantics = json.loads(configuration.rng_semantics_json)
            unseeded = semantics.get("behavior") == "UNSEEDED_STOCHASTIC"
            invocation_ordinal += 1
            prestate_sha256 = _process_global_rng_state_digest(random.getstate())
            try:
                tickets = generator.generate(descriptor, configuration, prefix)
                validate_tickets(tickets, descriptor.native_ticket_count)
            except Exception as exc:
                poststate_sha256 = _process_global_rng_state_digest(random.getstate())
                yield ReplayObservation(
                    descriptor.strategy_id,
                    descriptor.version,
                    descriptor.native_ticket_count,
                    draw.draw_number,
                    draw.draw_date,
                    prefix_authorities[index].history_sha256,
                    configuration.sha256,
                    status=ObservationStatus.FAILURE,
                    producer_fingerprint=producer.digest,
                    failure_code=(
                        f"REPLAY_GENERATION_FAILURE:{type(exc).__name__}:{exc}"
                    ),
                    replay_invocation_identity=(
                        _replay_invocation_identity(
                            descriptor=descriptor,
                            draw=draw,
                            causal_history_sha256=prefix_authorities[index].history_sha256,
                            configuration=configuration,
                            producer=producer,
                            invocation_ordinal=invocation_ordinal,
                            prestate_sha256=prestate_sha256,
                            poststate_sha256=poststate_sha256,
                        )
                        if unseeded
                        else None
                    ),
                )
                continue
            poststate_sha256 = _process_global_rng_state_digest(random.getstate())
            yield ReplayObservation(
                descriptor.strategy_id,
                descriptor.version,
                descriptor.native_ticket_count,
                draw.draw_number,
                draw.draw_date,
                prefix_authorities[index].history_sha256,
                configuration.sha256,
                status=ObservationStatus.EVALUATED,
                producer_fingerprint=producer.digest,
                tickets=tickets,
                replay_invocation_identity=(
                    _replay_invocation_identity(
                        descriptor=descriptor,
                        draw=draw,
                        causal_history_sha256=prefix_authorities[index].history_sha256,
                        configuration=configuration,
                        producer=producer,
                        invocation_ordinal=invocation_ordinal,
                        prestate_sha256=prestate_sha256,
                        poststate_sha256=poststate_sha256,
                    )
                    if unseeded
                    else None
                ),
            )


@dataclass(frozen=True, slots=True)
class ForecastRequest:
    target: ObservationTarget
    history: tuple[Draw, ...]
    history_authority: CausalHistoryRef
    schedule_authority_sha256: str
    catalog: tuple[StrategyDescriptor, ...]
    generation_configs: tuple[GenerationConfig, ...]
    observations: tuple[ReplayObservation, ...]
    producer: ProducerFingerprint
    required_cutoff: str = REQUIRED_HISTORY_CUTOFF
    fixture_only: bool = False

    def __post_init__(self) -> None:
        if type(self.fixture_only) is not bool:
            raise ForecastContractError("execution mode must be explicit")
        if not self.fixture_only:
            canonical = production_catalog().list(lottery_type=LotteryType.BIG_LOTTO)
            if sorted(self.catalog, key=lambda d: d.strategy_id) != sorted(
                canonical, key=lambda d: d.strategy_id
            ):
                raise ForecastContractError("CANONICAL_CATALOG_UNIVERSE_MISMATCH")
        validate_history(self.history, self.target, self.history_authority, self.required_cutoff)
        ids = [d.strategy_id for d in self.catalog]
        if len(ids) != len(set(ids)):
            raise ForecastContractError("DUPLICATE_CATALOG_IDENTITY")
        expected = {
            (d.strategy_id, d.version, d.native_ticket_count)
            for d in self.catalog
            if catalog_exclusion(d) is None
        }
        actual = [(c.strategy_id, c.strategy_version, c.native_k) for c in self.generation_configs]
        if set(actual) != expected or len(actual) != len(set(actual)):
            raise ForecastContractError("GENERATION_CONFIG_UNIVERSE_MISMATCH")
        if any(k == 20 for _, _, k in expected):
            raise ForecastContractError(
                "FORECAST_AUTHORITY_DRIFT: canonical native K20 unavailable"
            )

    @property
    def identity(self) -> ForecastIdentity:
        return ForecastIdentity(
            self.target,
            self.schedule_authority_sha256,
            self.required_cutoff,
            self.history_authority.history_sha256,
            self.producer,
            digest([asdict(d) for d in sorted(self.catalog, key=lambda d: d.strategy_id)]),
            digest(
                {
                    "fixture_only": self.fixture_only,
                    "strategies": [
                        c.payload()
                        for c in sorted(self.generation_configs, key=lambda c: c.strategy_id)
                    ],
                }
            ),
        )


def evaluate_evidence(request: ForecastRequest) -> tuple[CandidateEvidence, ...]:
    """Account for every FULL-history cell; only canonical warm-up reduces eligibility."""
    descriptors = {d.strategy_id: d for d in request.catalog if catalog_exclusion(d) is None}
    configs = {c.strategy_id: c for c in request.generation_configs}
    seeds: dict[str, int | None] = {}
    for strategy_id, descriptor in descriptors.items():
        config = configs[strategy_id]
        parameters = cast(dict[str, object], json.loads(config.parameters_json))
        seed = parameters.get("seed")
        if seed is not None and type(seed) is not int:
            raise ForecastContractError("INVALID_GENERATION_SEED")
        if config != native_generation_config(descriptor, request.history, seed=seed):
            raise ForecastContractError("REQUEST_GENERATION_CONFIGURATION_MISMATCH")
        seeds[strategy_id] = seed
    draws = {d.draw_number: (i, d) for i, d in enumerate(request.history)}
    prefixes = {
        d.draw_number: history_ref(request.history[:i]).history_sha256
        for i, d in enumerate(request.history)
    }
    indexed: dict[tuple[str, str], ReplayObservation] = {}
    for observation in request.observations:
        descriptor = descriptors.get(observation.strategy_id)
        draw_cell = draws.get(observation.draw_number)
        if descriptor is None or draw_cell is None:
            raise ForecastContractError("EVIDENCE_OUTSIDE_CANONICAL_UNIVERSE_OR_CAUSAL_HISTORY")
        index, draw = draw_cell
        effective_config = native_generation_config(
            descriptor, request.history[:index], seed=seeds[descriptor.strategy_id]
        )
        if (
            observation.strategy_version != descriptor.version
            or observation.native_k != descriptor.native_ticket_count
            or observation.draw_date != draw.draw_date
            or observation.causal_history_sha256 != prefixes[draw.draw_number]
            or observation.generation_config_sha256 != effective_config.sha256
            or observation.producer_fingerprint != request.producer.digest
        ):
            raise ForecastContractError("REPLAY_HISTORY_OR_GENERATION_IDENTITY_MISMATCH")
        behavior = json.loads(effective_config.rng_semantics_json)["behavior"]
        if observation.replay_invocation_identity is not None:
            if behavior != "UNSEEDED_STOCHASTIC":
                raise ForecastContractError("UNEXPECTED_REPLAY_INVOCATION_IDENTITY")
            _validate_replay_invocation_identity(observation, effective_config)
        elif (
            observation.status is ObservationStatus.EVALUATED
            and behavior == "UNSEEDED_STOCHASTIC"
        ):
            raise ForecastContractError("REPLAY_RNG_STATE_UNAVAILABLE_REGENERATION_REQUIRED")
        key = observation.strategy_id, observation.draw_number
        if key in indexed:
            raise ForecastContractError("DUPLICATE_OBSERVATION")
        indexed[key] = observation
    evidence: list[CandidateEvidence] = []
    for descriptor in sorted(descriptors.values(), key=lambda d: d.strategy_id):
        cells: list[ClassifiedObservation] = []
        for index, draw in enumerate(request.history):
            observation = indexed.get((descriptor.strategy_id, draw.draw_number))
            canonical_warmup = index < descriptor.min_history
            if canonical_warmup:
                if observation is not None and observation.status is not ObservationStatus.WARMUP:
                    raise ForecastContractError("OBSERVATION_CONTRADICTS_CANONICAL_WARMUP")
                cells.append(ClassifiedObservation(draw.draw_number, ObservationStatus.WARMUP))
            elif observation is None:
                cells.append(ClassifiedObservation(draw.draw_number, ObservationStatus.MISSING))
            elif observation.status is ObservationStatus.WARMUP:
                raise ForecastContractError("NONCANONICAL_WARMUP_EXCLUSION")
            elif observation.status is ObservationStatus.EVALUATED:
                won = any(
                    evaluate_lottery_prize(
                        lottery_type=LotteryType.BIG_LOTTO,
                        predicted_main_numbers=ticket,
                        predicted_special_number=None,
                        winning_main_numbers=draw.main_numbers,
                        winning_special_number=draw.special_number,
                    ).is_winner
                    for ticket in observation.tickets
                )
                cells.append(ClassifiedObservation(draw.draw_number, observation.status, won))
            else:
                cells.append(
                    ClassifiedObservation(
                        draw.draw_number, observation.status, failure_code=observation.failure_code
                    )
                )
        evidence.append(CandidateEvidence(descriptor, tuple(cells)))
    return tuple(evidence)


def _diagnostics(candidate: CandidateEvidence) -> dict[str, object]:
    windows: dict[str, object] = {}
    for size in (50, 300, 750):
        cells = candidate.observations[-size:]
        evaluated = [o for o in cells if o.status is ObservationStatus.EVALUATED]
        windows[f"RECENT_{size}"] = {
            "requested": len(cells),
            "window_size": size,
            "full_window_available": len(cells) == size,
            "evidence_complete": all(
                o.status in (ObservationStatus.EVALUATED, ObservationStatus.WARMUP) for o in cells
            ),
            "metric": ExactMetric(
                sum(o.official_any_prize is True for o in evaluated), len(evaluated)
            ).payload(),
        }
    baseline = official_any_prize_probability(
        candidate.descriptor.native_ticket_count
    ).as_fraction()
    rate = candidate.metric.rate if candidate.rankable else None
    return {
        "selection_weight": "NONE",
        "recent_windows": windows,
        "iid_official_prize_baseline": rational_payload(baseline),
        "baseline_delta": rational_payload(None if rate is None else rate - baseline),
    }


@dataclass(frozen=True, slots=True)
class PreparedForecast:
    bundle: ForecastBundle
    draft: PredictionDraft


def prepare_forecast(
    request: ForecastRequest, generator: NativeTicketGenerator
) -> PreparedForecast:
    evidence = evaluate_evidence(request)
    configs = {c.strategy_id: c for c in request.generation_configs}
    identity = request.identity
    entries: list[PredictionEntryDraft] = []
    buckets: list[dict[str, object]] = []
    for k in OUTPUT_BUCKETS:
        candidates = tuple(c for c in evidence if c.descriptor.native_ticket_count == k)
        ranked = rank_candidates(candidates)
        complete = bool(ranked) and all(c.complete for c in candidates)
        winner = ranked[0] if complete else None
        status = (
            "UNAVAILABLE_NO_CANONICAL_NATIVE_K20_STRATEGY"
            if k == 20
            else "UNAVAILABLE_NO_CANONICAL_NATIVE_STRATEGY"
            if not candidates
            else "INCOMPLETE_EVIDENCE"
            if not all(c.complete for c in candidates)
            else "UNAVAILABLE_NO_ELIGIBLE_EVIDENCE"
            if not ranked
            else "AVAILABLE"
        )
        tickets: TicketSet = ()
        generation_failure: str | None = None
        if winner is not None:
            try:
                tickets = generator.generate(
                    winner.descriptor, configs[winner.descriptor.strategy_id], request.history
                )
                validate_tickets(tickets, k)
            except Exception as exc:
                status = "UNAVAILABLE_GENERATION_FAILURE"
                generation_failure = f"{type(exc).__name__}:{exc}"
                tickets = ()
        selected = (
            None
            if winner is None
            else {
                "strategy_id": winner.descriptor.strategy_id,
                "strategy_version": winner.descriptor.version,
                "response_shape": winner.descriptor.response_shape.value,
                "metric": winner.metric.payload(),
                "coverage": winner.payload()["coverage"],
            }
        )
        available = status == "AVAILABLE"
        member_identity: list[object] = [identity.bundle_id, k]
        if available:
            assert winner is not None
            member_identity.extend((winner.descriptor.strategy_id, winner.descriptor.version))
        member_id = canonical_json(member_identity)
        baseline_material = {
            "lottery_type": LotteryType.BIG_LOTTO.value,
            "policy_version": OFFICIAL_ANY_PRIZE_BASELINE_POLICY_VERSION,
            "sampling": "UNIFORM_IID_LEGAL_TICKETS_WITH_REPLACEMENT",
            "native_k": k,
            "candidate_sizes": [6] * k,
            "probability": rational_payload(official_any_prize_probability(k).as_fraction()),
        }
        if available:
            entries.append(
                PredictionEntryDraft.available(
                    member_id=member_id,
                    selections=tuple(ProspectiveSelection(ticket) for ticket in tickets),
                    matched_baseline=MatchedBaselineRef(
                        LotteryType.BIG_LOTTO,
                        "BIG_LOTTO_IID_OFFICIAL_ANY_PRIZE",
                        OFFICIAL_ANY_PRIZE_BASELINE_POLICY_VERSION,
                        digest(baseline_material),
                        k,
                        (6,) * k,
                    ),
                )
            )
        else:
            entries.append(PredictionEntryDraft.unavailable(member_id=member_id, reason=status))
        buckets.append(
            {
                "bucket": f"K{k}",
                "native_k": k,
                "status": status,
                "entry_identity": member_identity,
                "ranking_complete": complete,
                "selected": selected,
                "tickets": [list(t) for t in tickets],
                "generation_status": "COMPLETE"
                if available
                else "FAILURE"
                if generation_failure
                else "NOT_RUN",
                "generation_failure": generation_failure,
                "semantic_tie": bool(
                    winner and sum(c.metric.rate == winner.metric.rate for c in ranked) > 1
                ),
                "tied_strategy_ids": [
                    c.descriptor.strategy_id
                    for c in ranked
                    if winner and c.metric.rate == winner.metric.rate
                ],
                "display_tie_break": "strategy_id ASCENDING",
                "ranked_strategy_ids": [c.descriptor.strategy_id for c in ranked],
                "candidate_count": len(candidates),
                "rankable_count": len(ranked),
                "excluded_count": len(candidates) - len(ranked),
                "candidates": [{**c.payload(), "diagnostics": _diagnostics(c)} for c in candidates],
                "baseline": baseline_material if available else None,
            }
        )
    payload = {
        "bundle_id": identity.bundle_id,
        "identity": identity.payload(),
        "forecast_output_semantics": "STRATEGY_RANKING_PLUS_TICKETS",
        "evaluation_window": "FULL",
        "fixture_only": request.fixture_only,
        "latest_data_ranking_complete": all(c.rankable for c in evidence) and bool(evidence),
        "history": request.history_authority.canonical_dict(),
        "catalog": [asdict(d) for d in sorted(request.catalog, key=lambda d: d.strategy_id)],
        "generation_configs": [
            c.payload() for c in sorted(request.generation_configs, key=lambda c: c.strategy_id)
        ],
        "catalog_exclusions": [
            {"strategy_id": d.strategy_id, "reason": catalog_exclusion(d)}
            for d in sorted(request.catalog, key=lambda d: d.strategy_id)
            if catalog_exclusion(d) is not None
        ],
        "evidence_payload_sha256": digest(
            [
                asdict(o) | {"draw_date": o.draw_date.isoformat()}
                for o in sorted(request.observations, key=lambda o: (o.strategy_id, o.draw_number))
            ]
        ),
        "buckets": buckets,
    }
    return PreparedForecast(
        ForecastBundle(identity, canonical_json(payload)), PredictionDraft(tuple(entries))
    )


@dataclass(frozen=True, slots=True)
class ForecastLiveState:
    scheduled_at: datetime
    schedule_authority_sha256: str
    outcome_present: bool


@dataclass(frozen=True, slots=True)
class StoredForecast:
    bundle: ForecastBundle
    prediction: PredictionRecord


class ForecastBundleStore(Protocol):
    def load(self, identity: ForecastIdentity) -> StoredForecast | None: ...

    def publish(
        self,
        bundle: ForecastBundle,
        seal: Callable[[ProspectiveObservationStore], PredictionRecord],
        before_publish: Callable[[], None],
    ) -> StoredForecast: ...


@dataclass(frozen=True, slots=True)
class _Registration:
    authority: OperationalRegistrationResult

    def register_earliest(self, lottery_type: LotteryType) -> OperationalRegistrationResult:
        if lottery_type is not LotteryType.BIG_LOTTO:
            raise ForecastContractError("BIG_LOTTO_REQUIRED")
        return self.authority


@dataclass(frozen=True, slots=True)
class _Producer:
    draft: PredictionDraft

    def predict(self, context: PredictionContext) -> PredictionDraft:
        if context.cohort.member_ids != tuple(e.member_id for e in self.draft.entries):
            raise ForecastContractError("FORECAST_MEMBERSHIP_MISMATCH")
        return self.draft


@dataclass(frozen=True, slots=True)
class NextUndrawnForecastService:
    registration_service: RunnableTargetRegistrationService
    read_live_state: Callable[[ObservationTarget], ForecastLiveState]
    clock: Callable[[], datetime]
    generator: NativeTicketGenerator
    store: ForecastBundleStore

    def run(self, request: ForecastRequest) -> StoredForecast:
        started = self.clock()
        if started.tzinfo is not UTC:
            raise ForecastTimingError("UTC_CLOCK_REQUIRED")
        authority = self.registration_service.register_earliest(LotteryType.BIG_LOTTO)
        announcement = authority.announcement
        if (
            announcement is None
            or authority.registration is None
            or announcement.target != request.target
            or authority.causal_history != request.history_authority
            or authority.immutable_schedule_sha256 != request.schedule_authority_sha256
        ):
            raise ForecastContractError("CANONICAL_TARGET_OR_HISTORY_AUTHORITY_MISMATCH")

        def gate() -> None:
            live = self.read_live_state(request.target)
            now = self.clock()  # After the presence read, including any time it consumed.
            if (
                now.tzinfo is not UTC
                or now < started
                or live.scheduled_at != announcement.scheduled_at
                or live.schedule_authority_sha256 != request.schedule_authority_sha256
            ):
                raise ForecastTimingError("CLOCK_OR_SCHEDULE_AUTHORITY_DRIFT")
            if type(live.outcome_present) is not bool or live.outcome_present:
                raise ForecastTimingError("OUTCOME_PRESENT_OR_UNKNOWN")
            if now >= live.scheduled_at:
                raise ForecastTimingError("PERSISTENCE_DEADLINE_REACHED")

        gate()
        prepared = prepare_forecast(request, self.generator)
        existing = self.store.load(request.identity)
        gate()

        def seal(
            store: ProspectiveObservationStore, previous: PredictionRecord | None = None
        ) -> PredictionRecord:
            if previous is None:
                gate()
            elif previous.predicted_at >= announcement.scheduled_at:
                raise ForecastConflictError("stored prediction was not pre-deadline")
            cohort = FrozenCohortRef(
                LotteryType.BIG_LOTTO,
                COHORT_ID,
                request.identity.bundle_id,
                prepared.bundle.payload_sha256,
                previous.cohort.frozen_at if previous else self.clock(),
                tuple(e.member_id for e in prepared.draft.entries),
                (1,),
                (TemporalProvenance.POST_FREEZE_DATE_PROSPECTIVE,),
            )
            fingerprint = ProducerFingerprint.create(
                producer_id=request.producer.producer_id,
                producer_version=request.producer.producer_version,
                dependencies=(
                    *request.producer.dependencies,
                    ProducerDependency(
                        f"lottolab://b649-next-undrawn-bundle/{request.identity.bundle_id}",
                        prepared.bundle.payload_sha256,
                        "complete forecast report and native tickets",
                    ),
                ),
            )

            def factory(announcement: TargetAnnouncement, reference_time: datetime) -> _Producer:
                return _Producer(prepared.draft)

            result = RunnablePredictionSealService(
                LotteryType.BIG_LOTTO,
                _Registration(authority),
                store,
                factory,
                cohort,
                fingerprint,
                repository_game_contracts(),
                self.clock if previous is None else lambda: previous.predicted_at,
            ).seal_earliest()
            if result.prediction is None:
                raise ForecastContractError("NO_RUNNABLE_TARGET")
            return result.prediction

        def verify(stored: StoredForecast) -> StoredForecast:
            if stored.bundle != prepared.bundle:
                raise ForecastConflictError("same bundle_id with conflicting payload")
            memory = InMemoryProspectiveObservationStore()
            memory.create_prediction(stored.prediction)
            verified = seal(memory, stored.prediction)
            if verified != stored.prediction:
                raise ForecastConflictError("durable record differs from verified prediction")
            return stored

        if existing is not None:
            return verify(existing)
        stored = self.store.publish(prepared.bundle, seal, gate)
        # A competing equal writer is re-read, including its original timestamps.
        return verify(stored)


def observation_identity(identity: ForecastIdentity) -> ProspectiveObservationIdentity:
    return ProspectiveObservationIdentity(
        LotteryType.BIG_LOTTO,
        COHORT_ID,
        identity.bundle_id,
        identity.target.draw_number,
        identity.target.draw_date,
    )
