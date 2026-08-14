"""Research-facing composition root for accelerated Replay predictions.

Wires the existing, unmodified Replay stack -- ``BuildCausalHistory``,
``GenerateOneBet``, ``StrategyCatalog`` -- together with PR #127's opt-in
``ReplayResearchCache`` so B research code gets one reusable object instead of
re-deriving this wiring per script (compare
``src/lottolab/research/powerlotto_wave1.py``, which -- for an unrelated
reason, its own task-owned source is outside the production database -- hand
rolls a full replay loop). This module runs no prediction logic of its own:
every import from ``replay_historical_predictions`` is used verbatim, and the
only cache in play is the one already merged there.

Currently BIG_LOTTO only. The causal-history port this module composes
(``ReplayCausalDrawRow`` / ``SQLiteDrawHistoryReader``) validates every row
against ``BIG_LOTTO_RULE_CONTRACT`` unconditionally -- see
``lottolab.domain.replay_history``'s module docstring -- regardless of the
``lottery_type`` threaded through the request. A ``DAILY_539`` or
``POWER_LOTTO`` request fails closed inside that reader (or, for a 5-number
game, inside ``ReplayCausalDrawRow`` itself), not inside this module.
Widening that port to other lotteries would be a semantics change to a
merged, unmodified use case and is out of this task's scope.
"""

from __future__ import annotations

from collections.abc import Sequence

from lottolab.application.draw_data import DrawDataApplicationError, DrawHistoryQuery
from lottolab.application.use_cases.build_causal_history import BuildCausalHistory
from lottolab.application.use_cases.generate_bet import build_production_generate_one_bet
from lottolab.application.use_cases.replay_historical_predictions import (
    ReplayHistoricalPredictions,
    ReplayHistoricalPredictionsInput,
    ReplayHistoricalPredictionsResult,
    ReplayResearchCache,
    ReplayResearchCacheStats,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.replay_predictions import ReplayTarget
from lottolab.infrastructure.persistence.draw_schema import (
    LocalDataError,
    LocalDataPaths,
    resolve_local_data_paths,
)
from lottolab.infrastructure.persistence.replay_history_reader import SQLiteDrawHistoryReader
from lottolab.infrastructure.persistence.repositories import SQLiteDrawDataRepository
from lottolab.strategies.catalog import production_catalog

#: One SQLite page (application.draw_data.MAX_HISTORY_PAGE_SIZE); call
#: most_recent_target_draw_numbers() once per page for a wider range.
MOST_RECENT_TARGET_PAGE_SIZE_LIMIT = 100


class ResearchReplayError(RuntimeError):
    """A caller-safe research replay composition failure."""


class ReplayResearchSession:
    """One reusable, cache-sharing composition of the production Replay stack.

    Construct once per research process (or per parameter-search run), then
    call :meth:`replay_targets` as many times as needed for different
    target/strategy batches. Every call after the first reuses the same
    injected adapters and catalog, and -- when a target/strategy pair's
    identity and causal history match a prior call exactly -- reuses the
    cached :class:`ReplayPredictionSnapshot` instead of recomputing it.

    A fresh session with no shared ``cache`` still accelerates repeated
    calls made through *that* session, but gives up cross-session reuse; pass
    the same :class:`ReplayResearchCache` instance to two sessions to share
    hits across them (e.g. two lottery-scoped sessions should not share one,
    since cache identity already binds ``lottery_type``).

    ``paths`` defaults to the resolved production local database
    (``resolve_local_data_paths()``, matching the CLI); pass an explicit
    :class:`LocalDataPaths` to point a session at a task-owned database
    instead, e.g. in a hermetic test.
    """

    def __init__(
        self,
        *,
        lottery_type: LotteryType = LotteryType.BIG_LOTTO,
        cache: ReplayResearchCache | None = None,
        paths: LocalDataPaths | None = None,
    ) -> None:
        paths = _resolve_local_data_paths() if paths is None else paths
        self._lottery_type = lottery_type
        self._repository = SQLiteDrawDataRepository(paths)
        self._cache = cache if cache is not None else ReplayResearchCache()
        self._replay = ReplayHistoricalPredictions(
            BuildCausalHistory(lambda: SQLiteDrawHistoryReader(paths)),
            build_production_generate_one_bet(),
            production_catalog(),
            cache=self._cache,
        )

    @property
    def lottery_type(self) -> LotteryType:
        return self._lottery_type

    @property
    def cache_stats(self) -> ReplayResearchCacheStats:
        """Hit/miss/entry/eviction counters for this session's shared cache."""

        return self._cache.stats

    def most_recent_target_draw_numbers(self, count: int) -> tuple[str, ...]:
        """The ``count`` most recently stored draw numbers, oldest first.

        Oldest-first matches ``ReplayHistoricalPredictionsResult``'s own
        target-major ordering convention. Backed entirely by the existing
        ``DrawRepository.list_draws`` port (descending ``draw_date`` /
        ``draw_number``) -- no new query semantics.
        """

        if type(count) is not int or count <= 0:
            raise ValueError("count must be a positive integer")
        if count > MOST_RECENT_TARGET_PAGE_SIZE_LIMIT:
            raise ValueError(
                f"count must not exceed {MOST_RECENT_TARGET_PAGE_SIZE_LIMIT} draws per call "
                "(one page); call this once per page to cover a wider range"
            )
        try:
            page = self._repository.list_draws(
                DrawHistoryQuery(
                    lottery_type=self._lottery_type,
                    page=1,
                    page_size=count,
                )
            )
        except DrawDataApplicationError as exc:
            raise ResearchReplayError("local draw database is unavailable") from exc
        return tuple(record.draw_number for record in reversed(page.records))

    def replay_targets(
        self,
        *,
        dataset_id: str,
        dataset_version: str,
        target_draw_numbers: Sequence[str],
        strategy_ids: Sequence[str],
        maximum_history_draws: int | None = None,
        minimum_history_draws: int | None = None,
    ) -> ReplayHistoricalPredictionsResult:
        """Resolve one batch of target x strategy Replay snapshots.

        Reuses the exact production wiring
        ``lottolab.interfaces.cli.replay_predictions`` composes
        (``BuildCausalHistory`` over ``SQLiteDrawHistoryReader``,
        ``build_production_generate_one_bet()``, ``production_catalog()``)
        plus this session's shared :class:`ReplayResearchCache`.

        Never raises for an unknown or lottery-unavailable ``strategy_id`` --
        ``ReplayHistoricalPredictions``/``GenerateOneBet`` already resolve
        that as a closed per-snapshot ``STRATEGY_UNAVAILABLE`` result (see
        ``GenerateOneBetStatus``), which a parameter sweep needs to keep
        iterating past rather than have raised out from under it. Raises
        :class:`ResearchReplayError` only when a target draw genuinely does
        not exist in the local database: no ``ReplayTarget`` can be
        constructed without its ``draw_date``, so there is no closed-result
        slot available to carry that failure instead.
        """

        if not target_draw_numbers:
            raise ValueError("target_draw_numbers must not be empty")
        if not strategy_ids:
            raise ValueError("strategy_ids must not be empty")

        targets: list[ReplayTarget] = []
        try:
            for draw_number in target_draw_numbers:
                record = self._repository.get_draw(self._lottery_type, draw_number)
                if record is None:
                    raise ResearchReplayError(f"target draw was not found: {draw_number}")
                targets.append(
                    ReplayTarget(draw_number=record.draw_number, draw_date=record.draw_date)
                )
        except DrawDataApplicationError as exc:
            raise ResearchReplayError("local draw database is unavailable") from exc

        return self._replay.execute(
            ReplayHistoricalPredictionsInput(
                lottery_type=self._lottery_type,
                dataset_id=dataset_id,
                dataset_version=dataset_version,
                targets=tuple(targets),
                strategy_ids=tuple(strategy_ids),
                maximum_history_draws=maximum_history_draws,
                minimum_history_draws=minimum_history_draws,
            )
        )


def _resolve_local_data_paths() -> LocalDataPaths:
    try:
        paths = resolve_local_data_paths()
    except LocalDataError as exc:
        raise ResearchReplayError("local draw database is unavailable") from exc
    if not paths.database.is_file():
        raise ResearchReplayError("local draw database is unavailable")
    return paths


__all__ = [
    "MOST_RECENT_TARGET_PAGE_SIZE_LIMIT",
    "ReplayResearchSession",
    "ResearchReplayError",
]
