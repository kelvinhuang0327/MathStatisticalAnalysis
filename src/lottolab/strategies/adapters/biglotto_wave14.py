"""BigLotto native-strategy wave 14: thin ports of three frozen legacy
BACKTESTED methods (donor commit ``49a25effa62fc24f40789c16be6f11bdfb41a4a9``,
the same frozen snapshot as waves 1-13). No algorithm was changed, tuned, or
"improved" during the port.

* ``legacy_biglotto__test_ecp__c9d5ac6decdd`` -- donor ``tools/test_ecp.py``,
  ``ECPOptimizer.predict_3bets_ecp``. The donor calls
  ``self.engine.statistical_predict(history, rules)`` 50 times in a loop and
  sums ``+1`` per returned number each time; since the call is a pure
  function of ``history`` (deterministic given the same causal history, see
  ``biglotto_wave3``'s own RNG note), all 50 calls return the identical
  ticket, so the net effect on the ``Counter`` is exactly "add 50 once" --
  reproduced here as a single weighted addition rather than a literal
  50-iteration loop (same final state, not a behavior change). Markov and
  deviation each contribute a further +5 boost per number (donor's own bare
  ``except: pass``/``except: continue`` around each call is reproduced as
  ``except ValueError`` -- the only exception type any of these ported
  ticket functions ever raises). P1 kill-filtering (count=10) then
  overwrites killed numbers to -9999, top-18 by ``most_common``, then the
  donor's own ``self._generate_bets(top_18)`` (inherited, unoverridden, from
  ``BigLotto3BetOptimizer`` -- the same fixed ``(0,6)/(4,10)/(8,14)`` slices
  wave 13's DCB already uses) -- a 3-native-ticket portfolio.
* ``legacy_biglotto__test_pce__9c0cf22b4217`` -- donor ``tools/test_pce.py``,
  ``PCEOptimizer.predict_3bets_pce``. Seven engine methods (frequency,
  bayesian, markov, deviation, statistical, trend, zone_balance, in the
  donor's own list order) each contribute one ticket; a pairwise vote
  Counter (``combinations(sorted(ticket), 2)``) and an individual-number
  vote Counter are built across all seven. P1 kill-filtering (count=10)
  excludes killed numbers from ever being used. Bets are built greedily: for
  each pair in descending pair-vote order (ties preserve the pair's first
  insertion order, exactly as every prior wave's ``Counter.most_common``
  already relies on), seed a bet with that pair, then greedily fill to 6
  numbers from the individual-vote ranking (also stable-tie-ordered),
  skipping killed numbers and already-selected numbers; a completed 6-number
  bet is kept only if it is not already in the bet list (donor's own
  ``if b_sorted not in bets`` dedup); stop once 3 bets are collected. Since
  every one of the seven feeder tickets is already ``_ticket()``-sorted by
  the shared sibling helpers (ascending, not the engine's own internal rank
  order) -- exactly like every prior wave's ``Counter``-based aggregation
  from these same ticket functions -- and the donor's own ``combinations(
  sorted(p), 2)`` call explicitly re-sorts each ticket before pairing
  regardless, this port is insensitive to that reuse: PCE's aggregation
  (pair/number presence-counting, always internally re-sorted before use)
  never depends on the donor's original per-method rank order. If fewer than
  3 legal 6-number bets can be assembled, the base class's own native ticket
  count check (not a bespoke exception here) closes it. A 3-native-ticket
  portfolio (native ticket count may close below 3; never above).
* ``legacy_biglotto__hpsb_optimizer__cf5cd7d971e8`` -- donor
  ``lottery_api/models/hpsb_optimizer.py``, ``HPSBOptimizer.predict_hpsb_v2``
  (delegates to ``predict_hpsb_dms`` with its own default
  ``audit_window=15`` -- confirmed as the V2/canonical entrypoint by the
  already-shipped, already-tested application-layer reference oracle at
  ``lottolab.application.legacy_hpsb_native_portfolios_wave57``, whose own
  ``LOCAL_SOURCE_CONFIGURATION`` is literally
  ``PREDICT_HPSB_V2_DEFAULT_AUDIT_WINDOW_15`` and whose own
  ``RANDOM_PROTOCOL`` confirms only the statistical submethod uses
  reproducible seeded randomness -- everything else in HPSB is
  deterministic, matching ``biglotto_wave3``'s own RNG note). A single-ticket
  strategy (``HPSBOptimizer`` predicts exactly one bet, never a portfolio).

  ``predict_hpsb_dms`` runs a rolling-window audit (window=15) over
  hot_cold_mix/markov/deviation/trend/statistical (the donor's own fixed
  dict order -- also this port's tie-break order for
  ``Counter.most_common(1)``, since each method's full audit completes
  before the next starts, exactly mirroring every prior wave's reliance on
  ``Counter`` insertion-order tie-breaking) against the causal prefix
  strictly before each of the trailing 15 draws, selects whichever method
  scored the most >=3-number hits (default ``hot_cold_mix`` if none scored),
  then re-runs only that one method against the *full* history and applies
  Zonal Density Protection (``_apply_zdp``, ported below) to its ticket.
  This audit loop's own ``history[idx]``/``history[:idx]`` indexing already
  assumes an oldest-first history (increasing index = later in time,
  matching every wave 1-13 adapter's own ``CausalDrawRow`` contract) --
  no reordering is needed here, only for ``repeat_booster_predict`` below.

  For causal history shorter than ``audit_window + 5`` (i.e. under 20
  draws) ``predict_hpsb_dms`` falls back to the static ``predict_hpsb``:
  a six-method weighted vote (statistical 1.5, markov 2.0, repeat_booster
  1.2, bayesian 1.5, hot_cold_mix 1.2, deviation 0.8, each further scaled by
  a small per-number position bonus) then the same ``_apply_zdp``. Every one
  of the 2,137 BIG_LOTTO targets in the R4 canonical baseline has at least
  20 causal draws (``MIN(history_draw_count) == 20`` -- confirmed against
  ``BIGLOTTO_CANONICAL_FULL_HISTORY_BASELINE_R4``), so this fallback path,
  and therefore ``repeat_booster_predict``, is never exercised by the R4
  execution; it is still ported faithfully below because the adapter
  contract must be correct for any future causal history, not only the R4
  target set.

  ``UnifiedPredictionEngine.repeat_booster_predict`` (new port,
  ``_unified_repeat_booster_ticket`` below) indexes ``history[0]`` /
  ``history[1]`` / ``history[:50]`` as if position 0 were the most recent
  draw and 50 were a trailing window -- inconsistent with every other
  method in the same engine class (``frequency_predict``, ``hot_cold_mix_
  predict``, ``zone_balance_predict``, and ``NegativeSelector.
  predict_kill_numbers`` all slice from the *end* of an oldest-first list;
  ``NegativeSelector.get_data()`` even documents its own history as "ASC
  Oldest -> Newest"; and ``predict_hpsb_dms``'s own audit loop above already
  assumes oldest-first). This framework's one fixed history contract is
  that ``CausalDrawRow`` history is always oldest-first (``history[-1]`` is
  the most recent draw, exactly as ``biglotto_wave3``'s module docstring
  already establishes for the dead ``markov_predict`` reversal guard).
  Rather than silently "correct" ``repeat_booster_predict``'s indexing to
  swap in this framework's actual most-recent-draw position -- which would
  be inventing behavior the donor never had -- it is ported by literal,
  untranslated transliteration against that one fixed convention: this is
  the same precedent ``biglotto_wave3`` already set (the ported function
  runs exactly as written against whatever history this framework always
  supplies; only a branch that is *provably unreachable* under that
  supply is omitted, never an untranslated index). Only its ``numbers``
  field is load-bearing; the donor's ``avg_repeat_count``/``confidence``
  computation is discarded like every other wave's non-``numbers`` fields.

  ``UnifiedPredictionEngine.ensemble_predictor``'s ``EnsemblePredictor.
  predict_ensemble`` (``lottery_api/models/ensemble_predictor.py``) is
  ``HPSBOptimizer.predict_hpsb_dms``'s own numbers blended with an AI V3
  model score that is unconditionally unavailable in this environment (no
  ``ai_lab``/torch port exists), so ``ai_weight`` is always forced to 0 and
  ``predict_ensemble`` always degenerates to exactly ``predict_hpsb_dms``'s
  own output -- confirmed a ``DUPLICATE_ALIAS`` of
  ``legacy_biglotto__hpsb_optimizer__cf5cd7d971e8`` by the existing full
  strategy catalog audit (``tests/unit/test_biglotto_full_strategy_catalog.
  py::test_duplicate_aliases_keep_explicit_target_and_unranked_reason``).
  Per this migration task's own contract, HPSB is the canonical entrypoint
  and ``ensemble_predictor`` is not separately registered here.

Donor parity for the shared engine methods (deviation/markov/statistical/
bayesian/frequency/hot_cold_mix/zone_balance/trend/kill_numbers) was already
independently re-derived and tested by waves 3/4/6; this module imports
those proven ports directly (sibling modules in the same
``strategies.adapters`` package -- not a layer violation, see
``tests/architecture/test_dependency_rules.py``) rather than re-deriving them
a second time. ``repeat_booster_predict`` and ``_apply_zdp`` are new to this
wave (no prior wave needed them) and were independently derived by reading
``lottery_api/models/unified_predictor.py``/``hpsb_optimizer.py`` at the
frozen commit.
"""

# pyright: reportPrivateUsage=false
# (intentional reuse of waves 3/4/6's already-verified private ticket/kill
# helpers -- see module docstring; those modules are not modified)

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Callable
from itertools import combinations

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import (
    BetAdapter,
    CausalDrawRow,
    PortfolioBetAdapter,
)
from lottolab.strategies.adapters.biglotto_wave3 import (
    _ticket,
    _unified_bayesian_ticket,
    _unified_deviation_ticket,
    _unified_frequency_ticket,
    _unified_markov_ticket,
    _unified_statistical_ticket,
)
from lottolab.strategies.adapters.biglotto_wave4 import (
    _kill_numbers,
    _unified_hot_cold_mix_ticket,
    _unified_zone_balance_ticket,
)
from lottolab.strategies.adapters.biglotto_wave6 import _unified_trend_ticket

_MIN_NUM = 1
_MAX_NUM = 49
_PICK = 6

_TicketFunc = Callable[[tuple[CausalDrawRow, ...]], tuple[int, ...]]


# ─── UnifiedPredictionEngine.repeat_booster_predict (new port; see module
#     docstring for the history-orientation reasoning) ─────────────────────


def _unified_repeat_booster_ticket(history: tuple[CausalDrawRow, ...]) -> tuple[int, ...]:
    """Port ``UnifiedPredictionEngine.repeat_booster_predict``'s number
    selection (numbers-only; see module docstring for the discarded
    confidence computation and the history-orientation reasoning)."""

    if not history:
        raise ValueError("FROZEN_REPEAT_BOOSTER_REQUIRES_HISTORY")
    last_1: set[int] = set(history[0].numbers)
    last_2: set[int] = set(history[1].numbers) if len(history) > 1 else set()
    scores: defaultdict[int, float] = defaultdict(float)
    for number in last_1:
        scores[number] += 1.5
    for number in last_2:
        if number not in last_1:
            scores[number] += 1.0
    all_numbers = [number for draw in history[:50] for number in draw.numbers]
    freq = Counter(all_numbers)
    for number in scores:
        scores[number] *= 1 + freq.get(number, 0) / 10.0
    ranked = sorted(scores.items(), key=lambda item: -item[1])
    predicted = [number for number, _score in ranked[:_PICK]]
    if len(predicted) < _PICK:
        top_freq = [number for number, _count in freq.most_common(20) if number not in predicted]
        predicted.extend(top_freq[: _PICK - len(predicted)])
    return _ticket(sorted(predicted[:_PICK]))


# ─── HPSBOptimizer._apply_zdp (Zonal Density Protection; new port) ─────────


def _apply_zdp(candidates: list[int], pick_count: int) -> list[int]:
    """Port ``HPSBOptimizer._apply_zdp`` for BIG_LOTTO (``max_num=49``):
    zones low=(1,16) mid=(17,32) high=(33,49), each capped at 3 per zone
    (the donor's own smaller ``MAX_PER_ZONE_HIGH=2`` branch only fires when
    the high zone spans fewer than 10 numbers -- unreachable here since
    49-32=17)."""

    z1 = _MAX_NUM // 3
    z2 = 2 * (_MAX_NUM // 3)
    zones: dict[str, tuple[int, int]] = {
        "low": (1, z1),
        "mid": (z1 + 1, z2),
        "high": (z2 + 1, _MAX_NUM),
    }
    max_per_zone = 3
    max_per_zone_high = 2 if (_MAX_NUM - z2) < 10 else 3

    selected: list[int] = []
    zone_counts: Counter[str] = Counter()
    for number in candidates:
        if len(selected) >= pick_count:
            break
        target_zone: str | None = None
        for zone_name, (start, end) in zones.items():
            if start <= number <= end:
                target_zone = zone_name
                break
        current_max = max_per_zone_high if target_zone == "high" else max_per_zone
        if target_zone and zone_counts[target_zone] < current_max:
            selected.append(number)
            zone_counts[target_zone] += 1
        elif not target_zone:
            selected.append(number)

    if len(selected) < pick_count:
        remaining = [number for number in candidates if number not in selected]
        selected.extend(remaining[: pick_count - len(selected)])

    return sorted(selected[:pick_count])


# ─── legacy_biglotto__test_ecp__c9d5ac6decdd ────────────────────────────────

_ECP_SLICES = ((0, 6), (4, 10), (8, 14))


def _ecp_top18(history: tuple[CausalDrawRow, ...]) -> list[int]:
    """Port ``ECPOptimizer.predict_3bets_ecp``'s candidate pool (see module
    docstring for the collapsed 50-sample-loop reasoning)."""

    consensus: Counter[int] = Counter()
    try:
        for number in _unified_statistical_ticket(history):
            consensus[number] += 50
    except ValueError:
        pass
    try:
        for number in _unified_markov_ticket(history):
            consensus[number] += 5
    except ValueError:
        pass
    try:
        for number in _unified_deviation_ticket(history):
            consensus[number] += 5
    except ValueError:
        pass
    for number in _kill_numbers(history, count=10):
        consensus[number] = -9999
    return [number for number, _score in consensus.most_common(18)]


class BigLottoTestEcpAdapter(PortfolioBetAdapter):
    """Elite Consensus Pool: 50x-weighted statistical consensus blended with
    markov/deviation boosts and P1 kill, sliced like wave 13's DCB -- a
    3-native-ticket portfolio."""

    strategy_id = "legacy_biglotto__test_ecp__c9d5ac6decdd"
    strategy_name = "大樂透 ECP 菁英共識池預測器"
    strategy_version = "v0.1"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)
    native_ticket_count = 3

    def _predict_all(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[tuple[int, ...], ...]:
        top_18 = _ecp_top18(history)
        return tuple(_ticket(top_18[start:end]) for start, end in _ECP_SLICES)


# ─── legacy_biglotto__test_pce__9c0cf22b4217 ────────────────────────────────

_PCE_METHODS: tuple[tuple[str, _TicketFunc], ...] = (
    ("frequency", _unified_frequency_ticket),
    ("bayesian", _unified_bayesian_ticket),
    ("markov", _unified_markov_ticket),
    ("deviation", _unified_deviation_ticket),
    ("statistical", _unified_statistical_ticket),
    ("trend", _unified_trend_ticket),
    ("zone_balance", _unified_zone_balance_ticket),
)


def _pce_bets(history: tuple[CausalDrawRow, ...]) -> tuple[tuple[int, ...], ...]:
    """Port ``PCEOptimizer.predict_3bets_pce``'s greedy pair-consensus bet
    construction (see module docstring for why value-sorted feeder tickets
    do not change this method's own aggregation)."""

    all_predictions: list[tuple[int, ...]] = []
    for _name, func in _PCE_METHODS:
        try:
            all_predictions.append(func(history))
        except ValueError:
            continue

    pair_votes: Counter[tuple[int, int]] = Counter()
    num_votes: Counter[int] = Counter()
    for prediction in all_predictions:
        for number in prediction:
            num_votes[number] += 1
        for left, right in combinations(sorted(prediction), 2):
            pair_votes[(left, right)] += 1

    kill_set = set(_kill_numbers(history, count=10))
    sorted_pairs = sorted(pair_votes.items(), key=lambda item: item[1], reverse=True)

    bets: list[list[int]] = []
    for (left, right), _votes in sorted_pairs:
        if left in kill_set or right in kill_set:
            continue
        bet: set[int] = {left, right}
        remaining = sorted(num_votes.items(), key=lambda item: item[1], reverse=True)
        for number, _count in remaining:
            if number not in bet and number not in kill_set:
                bet.add(number)
            if len(bet) >= _PICK:
                break
        if len(bet) == _PICK:
            sorted_bet = sorted(bet)
            if sorted_bet not in bets:
                bets.append(sorted_bet)
        if len(bets) >= 3:
            break

    return tuple(_ticket(bet) for bet in bets)


class BigLottoTestPceAdapter(PortfolioBetAdapter):
    """Pairwise Consensus Ensemble: greedy pair-vote bet construction across
    seven engine methods, P1 kill-filtered -- up to a 3-native-ticket
    portfolio (fewer than 3 legal bets closes via the base class's own
    native ticket count check, not a bespoke exception)."""

    strategy_id = "legacy_biglotto__test_pce__9c0cf22b4217"
    strategy_name = "大樂透 PCE 配對共識集成預測器"
    strategy_version = "v0.1"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)
    native_ticket_count = 3

    def _predict_all(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[tuple[int, ...], ...]:
        return _pce_bets(history)


# ─── legacy_biglotto__hpsb_optimizer__cf5cd7d971e8 ──────────────────────────

_DMS_AUDIT_WINDOW = 15
_DMS_METHODS: tuple[tuple[str, _TicketFunc], ...] = (
    ("hot_cold_mix", _unified_hot_cold_mix_ticket),
    ("markov", _unified_markov_ticket),
    ("deviation", _unified_deviation_ticket),
    ("trend", _unified_trend_ticket),
    ("statistical", _unified_statistical_ticket),
)
_HPSB_STATIC_METHODS: tuple[tuple[str, float, _TicketFunc], ...] = (
    ("statistical", 1.5, _unified_statistical_ticket),
    ("markov", 2.0, _unified_markov_ticket),
    ("repeat_booster", 1.2, _unified_repeat_booster_ticket),
    ("bayesian", 1.5, _unified_bayesian_ticket),
    ("hot_cold_mix", 1.2, _unified_hot_cold_mix_ticket),
    ("deviation", 0.8, _unified_deviation_ticket),
)


def _dms_select_method(history: tuple[CausalDrawRow, ...]) -> str:
    """Port ``predict_hpsb_dms``'s rolling-window (window=15) method audit;
    see module docstring for the tie-break/insertion-order reasoning."""

    method_perf: Counter[str] = Counter()
    for name, func in _DMS_METHODS:
        for offset in range(_DMS_AUDIT_WINDOW):
            index = len(history) - _DMS_AUDIT_WINDOW + offset
            if index <= 0:
                continue
            target = set(history[index].numbers)
            causal_prefix = history[:index]
            try:
                result = func(causal_prefix)
            except ValueError:
                continue
            if len(set(result) & target) >= 3:
                method_perf[name] += 1
    return method_perf.most_common(1)[0][0] if method_perf else "hot_cold_mix"


def _predict_hpsb_static(history: tuple[CausalDrawRow, ...]) -> tuple[int, ...]:
    """Port the static ``predict_hpsb`` weighted vote (the ``predict_hpsb_
    dms`` fallback for causal history under 20 draws; unreachable on the R4
    target set -- see module docstring)."""

    votes: defaultdict[int, float] = defaultdict(float)
    for _name, weight, func in _HPSB_STATIC_METHODS:
        try:
            numbers = func(history)
        except ValueError:
            continue
        for rank, number in enumerate(numbers):
            position_weight = (_PICK - rank) / _PICK
            votes[number] += weight * (0.8 + 0.2 * position_weight)
    sorted_candidates = sorted(votes.keys(), key=lambda number: votes[number], reverse=True)
    return _ticket(_apply_zdp(sorted_candidates, _PICK))


def _predict_hpsb_dms(history: tuple[CausalDrawRow, ...]) -> tuple[int, ...]:
    """Port ``predict_hpsb_v2`` -> ``predict_hpsb_dms`` (default
    ``audit_window=15``)."""

    if len(history) < _DMS_AUDIT_WINDOW + 5:
        return _predict_hpsb_static(history)
    methods_by_name = dict(_DMS_METHODS)
    chosen = methods_by_name[_dms_select_method(history)]
    final_ticket = chosen(history)
    return _ticket(_apply_zdp(list(final_ticket), _PICK))


class BigLottoHpsbOptimizerAdapter(BetAdapter):
    """Hyper-Precision Single Bet V2: DMS rolling-window method selection
    among hot_cold_mix/markov/deviation/trend/statistical (falling back to
    a six-method weighted vote + ZDP for causal history under 20 draws,
    never exercised by the R4 target set) -- a single-ticket strategy."""

    strategy_id = "legacy_biglotto__hpsb_optimizer__cf5cd7d971e8"
    strategy_name = "大樂透 HPSB 超精準單注預測器（V2 動態方法選擇）"  # noqa: RUF001
    strategy_version = "v0.1"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)

    def _predict(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[int, ...]:
        return _predict_hpsb_dms(history)


__all__ = [
    "BigLottoHpsbOptimizerAdapter",
    "BigLottoTestEcpAdapter",
    "BigLottoTestPceAdapter",
]
