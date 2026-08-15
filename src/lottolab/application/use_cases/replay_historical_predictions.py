"""Execute Replay predictions for a fixed set of target draws x strategies.

Composes two existing, unmodified use cases — never a second prediction
engine: :class:`BuildCausalHistory` resolves one causal history window per
target, and :class:`GenerateOneBet` resolves each uncached target x strategy
pair, delegating to whichever adapter the caller injected. This module only
orchestrates, records, and optionally reuses deterministic results; it contains
no prediction logic of its own.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date

from lottolab.application.use_cases.build_causal_history import (
    BuildCausalHistory,
    BuildCausalHistoryInput,
    BuildCausalHistoryResult,
    BuildCausalHistoryStatus,
)
from lottolab.application.use_cases.generate_bet import (
    GenerateOneBet,
    GenerateOneBetInput,
    GenerateOneBetStatus,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.replay_history import ReplayCausalDrawRow
from lottolab.domain.replay_predictions import (
    SNAPSHOT_SCHEMA_VERSION,
    ReplayPredictionSnapshot,
    ReplayTarget,
)
from lottolab.domain.strategies import StrategyDescriptor
from lottolab.evidence.replay_artifact import (
    build_replay_prediction_snapshot,
    causal_history_sha256,
)
from lottolab.strategies.adapters.base import CausalDrawRow
from lottolab.strategies.catalog import StrategyCatalog, UnknownStrategyError

REPLAY_RESEARCH_CACHE_ADAPTER_VERSION = "replay-historical-predictions/1.0.0"


class DuplicateReplayTargetError(ValueError):
    """``targets`` contains two entries with the same ``draw_number``."""


class DuplicateReplayStrategyError(ValueError):
    """``strategy_ids`` contains the same strategy id twice."""


@dataclass(frozen=True, slots=True)
class ReplayResearchCacheKey:
    """Complete identity of one deterministic research replay snapshot.

    The key deliberately binds both the target and its strictly causal input
    history. A corrected historical row therefore changes
    ``input_history_fingerprint`` even when the target and cutoff identifiers
    stay the same. Dataset identity is included because the cached object is a
    complete, dataset-bound :class:`ReplayPredictionSnapshot`.
    """

    lottery_type: LotteryType
    dataset_id: str
    dataset_version: str
    target_draw_id: str
    target_draw_date: date
    history_cutoff: str | None
    history_draw_count: int
    strategy_id: str
    strategy_version: str
    strategy_config_hash: str
    input_history_fingerprint: str
    adapter_version: str
    output_representation_version: str

    def __post_init__(self) -> None:
        if type(self.lottery_type) is not LotteryType:
            raise ValueError("lottery_type must be a LotteryType")
        if type(self.target_draw_date) is not date:
            raise ValueError("target_draw_date must be a date")
        if type(self.history_draw_count) is not int or self.history_draw_count < 0:
            raise ValueError("history_draw_count must be a non-negative integer")
        if self.history_cutoff is not None and (
            type(self.history_cutoff) is not str or not self.history_cutoff
        ):
            raise ValueError("history_cutoff must be a non-empty string when supplied")
        for value, label in (
            (self.dataset_id, "dataset_id"),
            (self.dataset_version, "dataset_version"),
            (self.target_draw_id, "target_draw_id"),
            (self.strategy_id, "strategy_id"),
            (self.strategy_version, "strategy_version"),
            (self.adapter_version, "adapter_version"),
            (self.output_representation_version, "output_representation_version"),
        ):
            if type(value) is not str or not value:
                raise ValueError(f"{label} must be a non-empty string")
        for value, label in (
            (self.strategy_config_hash, "strategy_config_hash"),
            (self.input_history_fingerprint, "input_history_fingerprint"),
        ):
            if (
                type(value) is not str
                or len(value) != 64
                or any(character not in "0123456789abcdef" for character in value)
            ):
                raise ValueError(f"{label} must be a lowercase SHA-256 digest")


@dataclass(frozen=True, slots=True)
class ReplayResearchCacheStats:
    hits: int
    misses: int
    entries: int
    evictions: int

    @property
    def hit_rate(self) -> float:
        request_count = self.hits + self.misses
        return self.hits / request_count if request_count else 0.0


class ReplayResearchCache:
    """Bounded process-local LRU cache for deterministic causal replay snapshots.

    This cache performs no I/O. It is intentionally explicit and opt-in so a
    research caller can share it across repeated target/strategy batches while
    production and CLI behavior remain unchanged.
    """

    def __init__(self, *, max_entries: int = 4096) -> None:
        if type(max_entries) is not int or max_entries <= 0:
            raise ValueError("max_entries must be a positive integer")
        self._max_entries = max_entries
        self._entries: dict[ReplayResearchCacheKey, ReplayPredictionSnapshot] = {}
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    @property
    def stats(self) -> ReplayResearchCacheStats:
        return ReplayResearchCacheStats(
            hits=self._hits,
            misses=self._misses,
            entries=len(self._entries),
            evictions=self._evictions,
        )

    def clear(self) -> None:
        """Drop all cached objects and reset measurement counters."""

        self._entries.clear()
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    def lookup(self, key: ReplayResearchCacheKey) -> ReplayPredictionSnapshot | None:
        """Return a matching cached snapshot while recording hit/miss telemetry."""

        snapshot = self._entries.pop(key, None)
        if snapshot is None:
            self._misses += 1
        else:
            self._hits += 1
            self._entries[key] = snapshot
        return snapshot

    def store(
        self,
        key: ReplayResearchCacheKey,
        snapshot: ReplayPredictionSnapshot,
    ) -> None:
        """Store a snapshot only when its load-bearing identity matches the key."""

        if (
            snapshot.lottery_type is not key.lottery_type
            or snapshot.dataset_id != key.dataset_id
            or snapshot.dataset_version != key.dataset_version
            or snapshot.target_draw_number != key.target_draw_id
            or snapshot.target_draw_date != key.target_draw_date
            or snapshot.strategy_id != key.strategy_id
            or snapshot.strategy_version != key.strategy_version
            or snapshot.causal_history_count != key.history_draw_count
            or snapshot.causal_history_sha256 != key.input_history_fingerprint
            or snapshot.cutoff_draw_number != key.history_cutoff
        ):
            raise ValueError("cache key does not match replay snapshot identity")
        if key not in self._entries and len(self._entries) >= self._max_entries:
            oldest_key = next(iter(self._entries))
            del self._entries[oldest_key]
            self._evictions += 1
        self._entries[key] = snapshot


@dataclass(frozen=True, slots=True)
class ReplayHistoricalPredictionsInput:
    lottery_type: LotteryType
    dataset_id: str
    dataset_version: str
    targets: tuple[ReplayTarget, ...]
    strategy_ids: tuple[str, ...]
    maximum_history_draws: int | None = None
    minimum_history_draws: int | None = None

    def __post_init__(self) -> None:
        if not self.targets:
            raise ValueError("targets must not be empty")
        if not self.strategy_ids:
            raise ValueError("strategy_ids must not be empty")
        draw_numbers = [target.draw_number for target in self.targets]
        if len(set(draw_numbers)) != len(draw_numbers):
            raise DuplicateReplayTargetError("targets must not contain duplicate draw numbers")
        if len(set(self.strategy_ids)) != len(self.strategy_ids):
            raise DuplicateReplayStrategyError("strategy_ids must not contain duplicates")


@dataclass(frozen=True, slots=True)
class ReplayHistoricalPredictionsResult:
    """``snapshots`` is ordered target-major, strategy-minor, mirroring the
    caller-supplied ``targets``/``strategy_ids`` order exactly — Replay never
    silently reorders a caller's pairs, matching ``BuildCausalHistory``'s own
    never-reorder convention."""

    snapshots: tuple[ReplayPredictionSnapshot, ...]


@dataclass(frozen=True, slots=True)
class _StrategyCacheIdentity:
    strategy_version: str
    strategy_config_hash: str
    adapter_version: str


def _strategy_config_hash(descriptor: StrategyDescriptor) -> str:
    payload = {
        "adapter_path": descriptor.adapter_path or "",
        "executable": descriptor.executable,
        "lifecycle_status": descriptor.lifecycle_status.value,
        "lottery_types": [lottery_type.value for lottery_type in descriptor.lottery_types],
        "min_history": descriptor.min_history,
        "native_ticket_count": descriptor.native_ticket_count,
        "provenance": list(descriptor.provenance),
        "response_shape": descriptor.response_shape.value,
        "strategy_id": descriptor.strategy_id,
        "strategy_name": descriptor.strategy_name,
        "strategy_version": descriptor.version,
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _strategy_cache_identity(descriptor: StrategyDescriptor) -> _StrategyCacheIdentity:
    adapter_path = descriptor.adapter_path or "NO_ADAPTER"
    return _StrategyCacheIdentity(
        strategy_version=descriptor.version,
        strategy_config_hash=_strategy_config_hash(descriptor),
        adapter_version=(
            f"{REPLAY_RESEARCH_CACHE_ADAPTER_VERSION}:{adapter_path}:{descriptor.version}"
        ),
    )


def to_causal_draw_rows(history: tuple[ReplayCausalDrawRow, ...]) -> tuple[CausalDrawRow, ...]:
    """Narrow Replay provenance rows down to the strategy adapter's own input shape.

    Deliberately drops ``special_number``: the strategy-facing ``CausalDrawRow``
    has no such field and must never be widened to add one (see
    ``lottolab.domain.replay_history`` module docstring). Replay's own
    provenance hash is computed separately, from the full
    ``ReplayCausalDrawRow`` tuple, so no information is actually lost.

    Public (not module-private) because
    :mod:`lottolab.application.use_cases.replay_historical_portfolio_predictions`
    reuses it verbatim for the PORTFOLIO response-shape path -- the causal
    history a strategy adapter sees must be identical regardless of whether
    its response shape is SINGLE_TICKET or PORTFOLIO.
    """

    return tuple(
        CausalDrawRow(
            draw=row.draw_number,
            date=row.draw_date.isoformat(),
            numbers=row.main_numbers,
        )
        for row in history
    )


class ReplayHistoricalPredictions:
    """Resolve one closed-result :class:`ReplayPredictionSnapshot` per target x strategy pair."""

    def __init__(
        self,
        build_causal_history: BuildCausalHistory,
        generate_one_bet: GenerateOneBet,
        catalog: StrategyCatalog,
        *,
        cache: ReplayResearchCache | None = None,
    ) -> None:
        self._build_causal_history = build_causal_history
        self._generate_one_bet = generate_one_bet
        self._catalog = catalog
        self._cache = cache
        self._cache_identity_by_strategy_id = {
            descriptor.strategy_id: _strategy_cache_identity(descriptor) for descriptor in catalog
        }

    def execute(
        self, request: ReplayHistoricalPredictionsInput
    ) -> ReplayHistoricalPredictionsResult:
        history_by_target: dict[str, BuildCausalHistoryResult] = {}
        snapshots: list[ReplayPredictionSnapshot] = []

        for target in request.targets:
            history_result = history_by_target.get(target.draw_number)
            if history_result is None:
                history_result = self._build_causal_history.execute(
                    BuildCausalHistoryInput(
                        lottery_type=request.lottery_type,
                        target_draw_number=target.draw_number,
                        maximum_history_draws=request.maximum_history_draws,
                        minimum_history_draws=request.minimum_history_draws,
                    )
                )
                history_by_target[target.draw_number] = history_result

            if history_result.status is BuildCausalHistoryStatus.OK:
                assert history_result.history is not None
                adapter_history = to_causal_draw_rows(history_result.history)
                history_fingerprint = (
                    causal_history_sha256(history_result.history)
                    if self._cache is not None
                    else None
                )
            else:
                adapter_history = None
                history_fingerprint = None

            for strategy_id in request.strategy_ids:
                snapshots.append(
                    self._build_one_snapshot(
                        request,
                        target,
                        strategy_id,
                        history_result,
                        adapter_history=adapter_history,
                        history_fingerprint=history_fingerprint,
                    )
                )

        return ReplayHistoricalPredictionsResult(snapshots=tuple(snapshots))

    def _build_one_snapshot(
        self,
        request: ReplayHistoricalPredictionsInput,
        target: ReplayTarget,
        strategy_id: str,
        history_result: BuildCausalHistoryResult,
        *,
        adapter_history: tuple[CausalDrawRow, ...] | None,
        history_fingerprint: str | None,
    ) -> ReplayPredictionSnapshot:
        try:
            descriptor = self._catalog.get(strategy_id)
        except UnknownStrategyError:
            strategy_identity = None
        else:
            strategy_identity = (
                descriptor.strategy_id,
                descriptor.strategy_name,
                descriptor.version,
            )

        if history_result.status is not BuildCausalHistoryStatus.OK:
            return build_replay_prediction_snapshot(
                dataset_id=request.dataset_id,
                dataset_version=request.dataset_version,
                lottery_type=request.lottery_type,
                target=target,
                strategy_id=strategy_id,
                strategy_identity=strategy_identity,
                history_status=history_result.status.value,
                history_reason_code=(
                    history_result.reason_code.value
                    if history_result.reason_code is not None
                    else None
                ),
                causal_history=None,
                prediction_status=None,
                prediction_reason_code=None,
                predicted_main_numbers=None,
            )

        assert history_result.history is not None  # OK results always carry history
        assert adapter_history is not None
        cache_key: ReplayResearchCacheKey | None = None
        cache_identity = self._cache_identity_by_strategy_id.get(strategy_id)
        if self._cache is not None and cache_identity is not None:
            assert history_fingerprint is not None
            cache_key = ReplayResearchCacheKey(
                lottery_type=request.lottery_type,
                dataset_id=request.dataset_id,
                dataset_version=request.dataset_version,
                target_draw_id=target.draw_number,
                target_draw_date=target.draw_date,
                history_cutoff=(
                    history_result.history[-1].draw_number if history_result.history else None
                ),
                history_draw_count=len(history_result.history),
                strategy_id=strategy_id,
                strategy_version=cache_identity.strategy_version,
                strategy_config_hash=cache_identity.strategy_config_hash,
                input_history_fingerprint=history_fingerprint,
                adapter_version=cache_identity.adapter_version,
                output_representation_version=SNAPSHOT_SCHEMA_VERSION,
            )
            cached = self._cache.lookup(cache_key)
            if cached is not None:
                return cached

        prediction_result = self._generate_one_bet.execute(
            GenerateOneBetInput(
                strategy_id=strategy_id,
                lottery_type=request.lottery_type,
                history=adapter_history,
            )
        )
        snapshot = build_replay_prediction_snapshot(
            dataset_id=request.dataset_id,
            dataset_version=request.dataset_version,
            lottery_type=request.lottery_type,
            target=target,
            strategy_id=strategy_id,
            strategy_identity=strategy_identity,
            history_status=history_result.status.value,
            history_reason_code=None,
            causal_history=history_result.history,
            prediction_status=prediction_result.status.value,
            prediction_reason_code=(
                prediction_result.reason_code.value
                if prediction_result.reason_code is not None
                else None
            ),
            predicted_main_numbers=prediction_result.numbers,
        )
        if (
            self._cache is not None
            and cache_key is not None
            and prediction_result.status is not GenerateOneBetStatus.REPLAY_ERROR
        ):
            self._cache.store(cache_key, snapshot)
        return snapshot


__all__ = [
    "REPLAY_RESEARCH_CACHE_ADAPTER_VERSION",
    "DuplicateReplayStrategyError",
    "DuplicateReplayTargetError",
    "ReplayHistoricalPredictions",
    "ReplayHistoricalPredictionsInput",
    "ReplayHistoricalPredictionsResult",
    "ReplayResearchCache",
    "ReplayResearchCacheKey",
    "ReplayResearchCacheStats",
    "to_causal_draw_rows",
]
