"""Target-native port of ``AutoOptimizeStrategy.predict``.

The donor is ``LotteryNewMeraged/src/engine/strategies/AutoOptimizeStrategy.js``.
This adapter keeps the donor's one live ``auto_optimize`` selector: it evaluates
the exact ordered candidate list on rolling historical prefixes, selects by the
legacy success-rate/average-hit comparator, and invokes the winning candidate
on the complete bounded history.

The donor launches candidate evaluations with ``Promise.allSettled``.  Several
of its candidates are asynchronous and share the process-global
``Math.random`` stream, so a simple candidate-major Python loop would change
the observable stochastic result.  The local task queue below is the narrow
orchestration needed to retain the donor's cooperative await order.  It does
not change any protected candidate adapter or introduce a shared framework.

Frontend rows are newest-first; LottoLab's causal history is oldest-first and
is reversed only at this adapter boundary.  The donor's response metadata is
not part of the native single-ticket contract, so only its final numbers are
emitted.
"""

from __future__ import annotations

import math
import random
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import cmp_to_key
from typing import Any, Final, Literal, Protocol

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters import biglotto_frontend_collaborative as collaborative
from lottolab.strategies.adapters import biglotto_frontend_ml as ml
from lottolab.strategies.adapters.base import BetAdapter, CausalDrawRow, RejectPrediction
from lottolab.strategies.adapters.biglotto_frontend_bayesian import (
    BigLottoFrontendBayesianAdapter,
)
from lottolab.strategies.adapters.biglotto_frontend_collaborative import (
    BigLottoFrontendCollaborativeHybridAdapter,
)
from lottolab.strategies.adapters.biglotto_frontend_deviation import (
    BigLottoFrontendDeviationAdapter,
)
from lottolab.strategies.adapters.biglotto_frontend_frequency import (
    BigLottoFrontendFrequencyAdapter,
)
from lottolab.strategies.adapters.biglotto_frontend_hot_cold import (
    BigLottoFrontendHotColdAdapter,
)
from lottolab.strategies.adapters.biglotto_frontend_markov import (
    BigLottoFrontendMarkovAdapter,
)
from lottolab.strategies.adapters.biglotto_frontend_ml import (
    BigLottoFrontendMLRandomForestAdapter,
)
from lottolab.strategies.adapters.biglotto_frontend_monte_carlo import (
    BigLottoFrontendMonteCarloAdapter,
)
from lottolab.strategies.adapters.biglotto_frontend_statistical_analysis import (
    BigLottoFrontendStatisticalAnalysisAdapter,
)
from lottolab.strategies.adapters.biglotto_frontend_sum_range import (
    BigLottoFrontendSumRangeAdapter,
)
from lottolab.strategies.adapters.biglotto_frontend_trend import (
    BigLottoFrontendTrendAdapter,
)
from lottolab.strategies.adapters.biglotto_frontend_unified_ensemble import (
    BigLottoFrontendUnifiedEnsembleWeightedAdapter,
    ticket_for_mode,
)

_STRATEGY_ID: Final = "legacy_biglotto__frontend_auto_optimize_strategy__a121d28125c6"
_MAX_DATA_SIZE: Final = 500
_MIN_HISTORY: Final = 30
_PICK_COUNT: Final = 6
_NUMBER_MIN: Final = 1
_NUMBER_MAX: Final = 49
_K_FOLD_COUNT: Final = 3
_MIN_FOLD_SIZE: Final = 5
_GENETIC_POPULATION: Final = 50
_GENETIC_GENERATIONS: Final = 30
_EXCELLENT_THRESHOLD: Final = 0.7
_GOOD_THRESHOLD: Final = 0.5

_FULL_STATISTICS_CONTEXT_EXPERTS: Final[frozenset[str]] = frozenset(
    {
        "Frequency",
        "Combined",
        "Bayesian",
        "Deviation",
        "MonteCarlo",
        "FeatureWeighted",
        "GeneticAlgorithm",
    }
)

_CANDIDATE_ORDER: Final[tuple[str, ...]] = (
    "frequency",
    "trend",
    "bayesian",
    "montecarlo",
    "markov",
    "deviation",
    "ensemble_weighted",
    "ensemble_boosting",
    "ensemble_features",
    "ml_forest",
    "collaborative_hybrid",
    "hot_cold",
    "sum_range",
    "statistical",
)

_COLLABORATIVE_EXPERTS: Final[tuple[tuple[str, str, float], ...]] = (
    ("statistical", "Frequency", 1.0),
    ("statistical", "Trend", 1.2),
    ("statistical", "Combined", 1.5),
    ("probabilistic", "Bayesian", 1.3),
    ("probabilistic", "Deviation", 1.2),
    ("probabilistic", "MonteCarlo", 1.4),
    ("sequential", "Markov", 1.3),
    ("sequential", "CoOccurrence", 1.1),
    ("feature", "FeatureWeighted", 1.4),
    ("feature", "RandomForest", 1.5),
    ("optimizer", "GeneticAlgorithm", 1.6),
)


class _RandomSource(Protocol):
    """The one operation used by donor stochastic candidates."""

    def random(self) -> float:
        """Return one value in the half-open interval [0, 1)."""

        ...


PredictionFn = Callable[[tuple[CausalDrawRow, ...]], tuple[int, ...]]


@dataclass(frozen=True, slots=True)
class _CandidateScore:
    """The fields retained by the donor's ``Promise.allSettled`` projection."""

    strategy: str
    success_rate: float
    avg_hits: float
    total_tests: int


@dataclass(frozen=True, slots=True)
class _Selection:
    """Private selector evidence used by tests without widening the API."""

    test_size: int
    validation_method: str
    candidate_scores: tuple[_CandidateScore, ...]
    ordered_scores: tuple[_CandidateScore, ...]
    winner: str
    final_numbers: tuple[int, ...]


def _legacy_genetic_outcome(
    newest_first: tuple[CausalDrawRow, ...],
    rng: _RandomSource,
) -> Any:
    """Reproduce the donor GeneticAlgorithm expert without changing R18.

    The R18 collaborative adapter intentionally remains a protected artifact,
    but its copied fitness helper uses ``sum(...)``.  The donor's ML genetic
    helper incrementally accumulates the same values, and that tiny floating
    point distinction affects exact tie selection and subsequent RNG use.  Use
    the already-parity-tested ML helpers here and retain the donor
    collaborative probability projection for this one migrated strategy.
    """

    frequency = ml._frequency_map(newest_first)  # pyright: ignore[reportPrivateUsage]
    missing = ml._missing_map(newest_first)  # pyright: ignore[reportPrivateUsage]
    population = [
        ml._random_selection(  # pyright: ignore[reportPrivateUsage]
            _NUMBER_MAX,
            _PICK_COUNT,
            frequency,
            rng,
        )
        for _ in range(_GENETIC_POPULATION)
    ]

    for _ in range(_GENETIC_GENERATIONS):
        fitness = [
            ml._calculate_fitness(  # pyright: ignore[reportPrivateUsage]
                individual,
                frequency,
                missing,
            )
            for individual in population
        ]
        new_population: list[list[int]] = []
        for _ in range(_GENETIC_POPULATION):
            parent_one = ml._tournament_selection(  # pyright: ignore[reportPrivateUsage]
                population,
                fitness,
                rng,
            )
            parent_two = ml._tournament_selection(  # pyright: ignore[reportPrivateUsage]
                population,
                fitness,
                rng,
            )
            child = (
                ml._crossover(  # pyright: ignore[reportPrivateUsage]
                    parent_one,
                    parent_two,
                    rng,
                )
                if rng.random() > 0.2
                else list(parent_one)
            )
            if rng.random() < 0.1:
                child = ml._mutate(  # pyright: ignore[reportPrivateUsage]
                    child,
                    _NUMBER_MAX,
                    rng,
                )
            new_population.append(child)
        population = new_population

    final_fitness = [
        ml._calculate_fitness(  # pyright: ignore[reportPrivateUsage]
            individual,
            frequency,
            missing,
        )
        for individual in population
    ]
    best_individual = population[final_fitness.index(max(final_fitness))]

    probabilities = {number: 0.0 for number in range(_NUMBER_MIN, _NUMBER_MAX + 1)}
    for index, individual in enumerate(population):
        weight = final_fitness[index]
        for number in individual:
            probabilities[number] += weight
    total_probability = sum(probabilities.values())
    if total_probability > 0:
        probabilities = {
            number: probability / total_probability
            for number, probability in probabilities.items()
        }
    return collaborative._ModelOutcome(  # pyright: ignore[reportPrivateUsage]
        tuple(sorted(best_individual)),
        probabilities,
        81.0,
    )


@dataclass(slots=True)
class _EvaluationTask:
    """One cooperative donor evaluation coroutine represented synchronously."""

    strategy: str
    train_data: tuple[CausalDrawRow, ...]
    test_data: tuple[CausalDrawRow, ...]
    kind: Literal["simple", "weighted", "collaborative"]
    simple_predict: PredictionFn | None
    weighted_predict: PredictionFn | None
    rng: _RandomSource
    statistics_context: dict[str, tuple[CausalDrawRow, ...]]
    phase: int = 0
    test_index: int = 0
    pending_prediction: tuple[int, ...] | None = None
    success_count: int = 0
    total_hits: int = 0
    collaborative_results: list[collaborative._ExpertResult] = field(  # pyright: ignore[reportPrivateUsage, reportUnknownVariableType]
        default_factory=list
    )
    collaborative_wait: int = 0
    done: bool = False

    def step(self) -> None:
        """Advance one donor await boundary and enqueue-ready state."""

        if self.done:
            return
        if self.kind == "simple":
            self._step_simple()
        elif self.kind == "weighted":
            self._step_weighted()
        else:
            self._step_collaborative()

    def score(self) -> _CandidateScore:
        """Project per-period outcomes exactly as the donor does."""

        total_tests = len(self.test_data)
        if total_tests == 0:
            return _CandidateScore(self.strategy, 0.0, 0.0, 0)
        return _CandidateScore(
            self.strategy,
            self.success_count / total_tests,
            self.total_hits / total_tests,
            total_tests,
        )

    def _current_train_data(self) -> tuple[CausalDrawRow, ...]:
        """Return donor ``trainData + testData.slice(0, i)``."""

        if self.test_index == 0:
            return self.train_data
        return self.train_data + self.test_data[: self.test_index]

    def _native_current_train_data(self) -> tuple[CausalDrawRow, ...]:
        """Reverse one donor validation prefix into the native causal order."""

        return tuple(reversed(self._current_train_data()))

    def _set_statistics_context(
        self,
        newest_first: tuple[CausalDrawRow, ...],
    ) -> None:
        """Track the donor's shared StatisticsService current-data binding."""

        self.statistics_context["data"] = newest_first

    def _record_simple_statistics_context(self) -> None:
        """Apply source-visible stats side effects after one simple candidate."""

        current_train = self._current_train_data()
        if self.strategy == "ml_forest":
            self._set_statistics_context(current_train[:10])
        elif self.strategy in {
            "frequency",
            "bayesian",
            "montecarlo",
            "deviation",
            "ensemble_boosting",
            "ensemble_features",
            "sum_range",
            "statistical",
        }:
            self._set_statistics_context(current_train)

    def _begin_next_prediction(self) -> None:
        """Start the next ``await strategy.predict`` in the same continuation."""

        self.test_index += 1
        self.pending_prediction = None
        self.collaborative_results.clear()
        self.collaborative_wait = 0
        self.phase = 0

        if self.test_index >= len(self.test_data):
            self.done = True
            return

        if self.kind == "simple":
            self._run_simple_prediction()
        elif self.kind == "weighted":
            self._start_weighted_prediction()
        else:
            self._start_collaborative_prediction()
            # ``CollaborativeStrategy.hybridPredict`` invokes its first
            # Frequency expert before its first await, including when the
            # outer evaluation continuation starts the next period.
            self._append_collaborative_expert(0)
            self.phase = 1

    def _score_and_continue(self) -> None:
        """Score one completed/failed period, then enter the next period."""

        if self.pending_prediction is not None:
            actual = self.test_data[self.test_index].numbers
            hits = sum(number in actual for number in self.pending_prediction)
            self.total_hits += hits
            if hits >= math.ceil(_PICK_COUNT * 0.5):
                self.success_count += 1
        self._begin_next_prediction()

    def _run_simple_prediction(self) -> None:
        """Run one synchronous/simple donor candidate call."""

        self.pending_prediction = None
        if self.simple_predict is None:
            self.phase = 1
            return
        try:
            self.pending_prediction = self.simple_predict(self._native_current_train_data())
            self._record_simple_statistics_context()
        except Exception:
            # The donor catches one candidate-period failure and leaves that
            # period in the denominator with no hit contribution.
            self.pending_prediction = None
        self.phase = 1

    def _start_weighted_prediction(self) -> None:
        """Enter ``UnifiedEnsembleStrategy.predictWeighted`` at Frequency."""

        # The top-level async call and its first Frequency await are both
        # completed before the donor yields.  Frequency/Trend/Markov consume
        # no random values; the full target-native weighted call is deferred to
        # the donor's MonteCarlo phase below.
        self.pending_prediction = None
        self._set_statistics_context(self._current_train_data())
        self.phase = 1

    def _step_simple(self) -> None:
        if self.phase == 0:
            self._run_simple_prediction()
            return
        self._score_and_continue()

    def _step_weighted(self) -> None:
        if self.phase == 0:
            self._start_weighted_prediction()
            return
        if self.phase == 1:
            # Trend await.
            self.phase = 2
            return
        if self.phase == 2:
            # Markov await.
            self.phase = 3
            return
        if self.phase == 3:
            # MonteCarlo is the first stochastic leaf in the donor weighted
            # sequence.  The target adapter call reproduces all five leaves,
            # while this placement preserves the shared RNG position.
            if self.weighted_predict is None:
                self.phase = 5
                return
            try:
                self.pending_prediction = self.weighted_predict(
                    self._native_current_train_data()
                )
                self._set_statistics_context(self._current_train_data())
                self.phase = 4
            except Exception:
                self.pending_prediction = None
                self.phase = 5
            return
        if self.phase == 4:
            # Deviation await, followed by resolution of the weighted result.
            self.phase = 5
            return
        if self.phase == 5:
            # The outer async wrapper adopts the inner ensemble promise before
            # the evaluation loop receives its result.
            self.phase = 6
            return
        if self.phase == 6:
            # Preserve the second adoption continuation before resolving the
            # per-period evaluation coroutine.
            self.phase = 7
            return
        self._score_and_continue()

    def _start_collaborative_prediction(self) -> None:
        """Enter ``CollaborativeStrategy.hybridPredict`` at Frequency."""

        self.pending_prediction = None
        self.collaborative_results.clear()
        self.collaborative_wait = 0
        self.phase = 0

    def _append_collaborative_expert(self, index: int) -> None:
        group, name, weight = _COLLABORATIVE_EXPERTS[index]
        try:
            if name == "GeneticAlgorithm":
                outcome = _legacy_genetic_outcome(
                    self._current_train_data(),
                    self.rng,
                )
            else:
                outcome = collaborative._model_outcome(  # pyright: ignore[reportPrivateUsage]
                    name,
                    self._current_train_data(),
                    self.rng,
                )
        except Exception:
            # CollaborativeStrategy.runExpertGroups logs and omits one failed
            # expert, then continues the remaining group sequence.
            return
        self.collaborative_results.append(
            collaborative._ExpertResult(  # pyright: ignore[reportPrivateUsage]
                name=name,
                group=group,
                weight=weight,
                numbers=outcome.numbers,
                probabilities=outcome.probabilities,
                confidence=outcome.confidence,
            )
        )
        if name == "RandomForest":
            self._set_statistics_context(self._current_train_data()[:10])
        elif name in _FULL_STATISTICS_CONTEXT_EXPERTS:
            self._set_statistics_context(self._current_train_data())

    def _finish_collaborative_prediction(self) -> None:
        """Apply the donor hybrid post-processing after GeneticAlgorithm."""

        exploration_results = [
            result
            for result in self.collaborative_results
            if result.group in {"statistical", "probabilistic"}
        ]
        exploration_votes = collaborative._weighted_voting(  # pyright: ignore[reportPrivateUsage]
            exploration_results,
            _NUMBER_MAX,
        )
        candidates_25 = collaborative._ranked_numbers(  # pyright: ignore[reportPrivateUsage]
            exploration_votes,
            25,
        )

        refinement_results = [
            result
            for result in self.collaborative_results
            if result.group in {"sequential", "feature"}
        ]
        candidates_15 = collaborative._refine_candidates(  # pyright: ignore[reportPrivateUsage]
            candidates_25,
            refinement_results,
            15,
        )

        all_results = list(self.collaborative_results)
        final_votes = collaborative._weighted_voting(  # pyright: ignore[reportPrivateUsage]
            all_results,
            _NUMBER_MAX,
        )
        candidate_votes = {
            number: final_votes.get(number, 0.0) for number in candidates_15
        }
        final_numbers = collaborative._ranked_numbers(  # pyright: ignore[reportPrivateUsage]
            candidate_votes,
            _PICK_COUNT,
        )
        optimized_numbers = collaborative._apply_constraints(  # pyright: ignore[reportPrivateUsage]
            final_numbers,
            candidate_votes,
        )
        self.pending_prediction = tuple(sorted(optimized_numbers))

    def _step_collaborative(self) -> None:
        if self.collaborative_wait > 0:
            self.collaborative_wait -= 1
            return
        if self.phase <= len(_COLLABORATIVE_EXPERTS) - 1:
            expert_index = self.phase
            self._append_collaborative_expert(expert_index)
            if expert_index in {5, 9}:
                # Each completed runExpertGroups promise resumes hybridPredict
                # on one additional queued continuation before the next group.
                self.collaborative_wait = 1
                self.phase += 1
            elif expert_index == len(_COLLABORATIVE_EXPERTS) - 1:
                self._finish_collaborative_prediction()
                # hybridPredict, CollaborativeStrategy.predict, and the
                # enclosing evaluation await chain add three continuations
                # before the next rolling validation period begins.
                self.collaborative_wait = 3
                self.phase += 1
            else:
                self.phase += 1
            return
        self._score_and_continue()


class BigLottoFrontendAutoOptimizeAdapter(BetAdapter):
    """Reproduce the live ``auto_optimize`` selector for Big Lotto."""

    strategy_id = _STRATEGY_ID
    strategy_name = "大樂透 Frontend Auto Optimize Strategy"
    strategy_version = "v0.1"
    min_history = _MIN_HISTORY
    supported_lottery_types = (LotteryType.BIG_LOTTO,)

    def __init__(self, rng: _RandomSource | None = None) -> None:
        # The donor shares one unseeded global Math.random stream across every
        # candidate instance and the final winner call.
        self._rng: _RandomSource = random if rng is None else rng
        self.candidate_strategies = list(_CANDIDATE_ORDER)
        self.excellent_threshold = _EXCELLENT_THRESHOLD
        self.good_threshold = _GOOD_THRESHOLD
        self.use_k_fold = True
        self.k_fold_count = _K_FOLD_COUNT
        self.min_fold_size = _MIN_FOLD_SIZE
        self._candidate_adapters: dict[str, BetAdapter] = {
            "frequency": BigLottoFrontendFrequencyAdapter(),
            "trend": BigLottoFrontendTrendAdapter(),
            "bayesian": BigLottoFrontendBayesianAdapter(),
            "montecarlo": BigLottoFrontendMonteCarloAdapter(self._rng),
            "markov": BigLottoFrontendMarkovAdapter(),
            "deviation": BigLottoFrontendDeviationAdapter(),
            "ensemble_weighted": BigLottoFrontendUnifiedEnsembleWeightedAdapter(
                self._rng
            ),
            "ml_forest": BigLottoFrontendMLRandomForestAdapter(self._rng),
            "collaborative_hybrid": BigLottoFrontendCollaborativeHybridAdapter(
                self._rng
            ),
            "hot_cold": BigLottoFrontendHotColdAdapter(),
            "sum_range": BigLottoFrontendSumRangeAdapter(),
            "statistical": BigLottoFrontendStatisticalAnalysisAdapter(self._rng),
        }
        self._statistics_context: dict[str, tuple[CausalDrawRow, ...]] = {"data": ()}

    def _history_window(self, history: tuple[object, ...]) -> tuple[object, ...]:
        """Keep the donor's newest 500 rows before canonical row validation."""

        return history[-_MAX_DATA_SIZE:]

    def _predict(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[int, ...]:
        del lottery_type
        return self._select(history).final_numbers

    def _select(self, history: tuple[CausalDrawRow, ...]) -> _Selection:
        """Run validation, winner selection, and the final winner prediction."""

        self._statistics_context["data"] = ()
        donor_data = tuple(reversed(history))
        test_size = min(10, math.floor(len(donor_data) * 0.2))
        train_data = donor_data[test_size:]
        test_data = donor_data[:test_size]

        will_use_k_fold = (
            self.use_k_fold
            and len(test_data) >= self.min_fold_size * self.k_fold_count
        )
        if will_use_k_fold:
            # With the donor's fixed max-500 window and max-10 test split this
            # branch is unreachable for the live configuration.  Keep the
            # exact donor branch available for private characterization calls.
            scores = tuple(
                self._evaluate_strategy_kfold(name, train_data, test_data)
                for name in self.candidate_strategies
            )
            validation_method = f"{self.k_fold_count}-fold CV"
        else:
            scores = self._evaluate_all_single(train_data, test_data)
            validation_method = "single-split"

        if not scores:
            raise RejectPrediction(
                f"{self.strategy_id}: all legacy candidate evaluations failed"
            )

        ordered_scores = tuple(sorted(scores, key=cmp_to_key(_compare_scores)))
        winner = ordered_scores[0].strategy
        final_numbers = self._predict_candidate(winner, history)
        return _Selection(
            test_size=test_size,
            validation_method=validation_method,
            candidate_scores=scores,
            ordered_scores=ordered_scores,
            winner=winner,
            final_numbers=final_numbers,
        )

    def _evaluate_all_single(
        self,
        train_data: tuple[CausalDrawRow, ...],
        test_data: tuple[CausalDrawRow, ...],
    ) -> tuple[_CandidateScore, ...]:
        """Run donor single-split tasks in Promise.allSettled order."""

        task_list = [
            self._make_task(name, train_data, test_data)
            for name in self.candidate_strategies
        ]
        tasks = deque(task_list)
        while tasks:
            task = tasks.popleft()
            task.step()
            if not task.done:
                tasks.append(task)
        # Promise.allSettled returns results in map/input order, not completion
        # order.  Keep this exact candidate-order projection for stable ties.
        return tuple(task.score() for task in task_list)

    def _make_task(
        self,
        strategy: str,
        train_data: tuple[CausalDrawRow, ...],
        test_data: tuple[CausalDrawRow, ...],
    ) -> _EvaluationTask:
        kind: Literal["simple", "weighted", "collaborative"] = "simple"
        simple_predict: PredictionFn | None = self._simple_candidate(strategy)
        weighted_predict: PredictionFn | None = None
        if strategy == "ensemble_weighted":
            kind = "weighted"
            simple_predict = None
            weighted_predict = self._candidate_adapter_predict(strategy)
        elif strategy == "collaborative_hybrid":
            kind = "collaborative"
            simple_predict = None
        return _EvaluationTask(
            strategy=strategy,
            train_data=train_data,
            test_data=test_data,
            kind=kind,
            simple_predict=simple_predict,
            weighted_predict=weighted_predict,
            rng=self._rng,
            statistics_context=self._statistics_context,
        )

    def _candidate_adapter_predict(self, strategy: str) -> PredictionFn:
        adapter = self._candidate_adapters[strategy]

        def predict(history: tuple[CausalDrawRow, ...]) -> tuple[int, ...]:
            if strategy == "hot_cold":
                newest_first = self._statistics_context["data"]
                if not newest_first:
                    newest_first = tuple(reversed(history))
                return adapter._predict(  # pyright: ignore[reportPrivateUsage]
                    tuple(reversed(newest_first)),
                    LotteryType.BIG_LOTTO,
                )
            return adapter.get_one_bet(history, LotteryType.BIG_LOTTO)[0]

        return predict

    def _simple_candidate(self, strategy: str) -> PredictionFn | None:
        if strategy in self._candidate_adapters and strategy not in {
            "ensemble_weighted",
            "collaborative_hybrid",
        }:
            return self._candidate_adapter_predict(strategy)
        if strategy == "ensemble_boosting":
            return self._unified_mode_predict("boosting")
        if strategy == "ensemble_features":
            return self._unified_mode_predict("feature_weighted")
        return None

    def _unified_mode_predict(self, mode: str) -> PredictionFn:
        def predict(history: tuple[CausalDrawRow, ...]) -> tuple[int, ...]:
            return ticket_for_mode(tuple(reversed(history)), mode)  # type: ignore[arg-type]

        return predict

    def _predict_candidate(
        self,
        strategy: str,
        history: tuple[CausalDrawRow, ...],
    ) -> tuple[int, ...]:
        """Invoke the reused donor winner instance on the full history."""

        if strategy == "ensemble_weighted":
            return self._candidate_adapter_predict(strategy)(history)
        if strategy == "collaborative_hybrid":
            return self._candidate_adapter_predict(strategy)(history)
        predictor = self._simple_candidate(strategy)
        if predictor is None:
            raise RejectPrediction(f"{self.strategy_id}: unknown winner {strategy}")
        return predictor(history)

    def _evaluate_strategy_kfold(
        self,
        strategy: str,
        train_data: tuple[CausalDrawRow, ...],
        test_data: tuple[CausalDrawRow, ...],
    ) -> _CandidateScore:
        """Characterize the donor's private three-fold evaluator if reached."""

        min_hits = math.ceil(_PICK_COUNT * 0.5)
        fold_size = math.floor(len(test_data) / self.k_fold_count)
        success_count = 0
        total_hits = 0
        total_tests = 0
        predictor = self._simple_candidate(strategy)
        if strategy == "ensemble_weighted":
            predictor = self._candidate_adapter_predict(strategy)
        if strategy == "collaborative_hybrid":
            predictor = self._candidate_adapter_predict(strategy)

        for fold_index in range(self.k_fold_count):
            fold_start = fold_index * fold_size
            fold_end = (
                len(test_data)
                if fold_index == self.k_fold_count - 1
                else (fold_index + 1) * fold_size
            )
            fold_test = test_data[fold_start:fold_end]
            for index, target in enumerate(fold_test):
                current_train = train_data + test_data[: fold_start + index]
                try:
                    if predictor is None:
                        raise KeyError(strategy)
                    predicted = predictor(tuple(reversed(current_train)))
                    hits = sum(number in target.numbers for number in predicted)
                    total_hits += hits
                    if hits >= min_hits:
                        success_count += 1
                except Exception:
                    pass
            if fold_test:
                total_tests += len(fold_test)
        if total_tests == 0:
            return _CandidateScore(strategy, 0.0, 0.0, 0)
        return _CandidateScore(
            strategy,
            success_count / total_tests,
            total_hits / total_tests,
            total_tests,
        )


def _compare_scores(left: _CandidateScore, right: _CandidateScore) -> int:
    """Match the donor comparator and preserve stable candidate-order ties."""

    if abs(left.success_rate - right.success_rate) > 0.01:
        return -1 if left.success_rate > right.success_rate else 1
    if left.avg_hits == right.avg_hits:
        return 0
    return -1 if left.avg_hits > right.avg_hits else 1


__all__ = ["BigLottoFrontendAutoOptimizeAdapter"]
