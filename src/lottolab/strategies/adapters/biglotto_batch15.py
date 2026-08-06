"""BigLotto native-strategy batch 15: thin ports of nine frozen legacy
BACKTESTED methods (donor commit ``49a25effa62fc24f40789c16be6f11bdfb41a4a9``,
the same frozen snapshot as waves 1-14). No algorithm was changed, tuned, or
"improved" during the port.

Two donor files supply the dominant family -- ``lottery_api/models/
cold_hunter_predictor.py`` (six methods) and its sibling ``lottery_api/
models/gap_pressure.py`` (one method). Both are explicitly documented by the
donor as "完全確定性(deterministic),無隨機元素" (fully deterministic, no random
element) and both reference real BIG_LOTTO draw-review incidents
(``115000006``, ``115000050``) in their own docstrings, unlike
several sibling modules in the same directory that default to Lotto539/
POWER_LOTTO ranges. Neither module has a dedicated ``tools/test_*.py``
driver in the donor tree (the same shape as wave 14's ``hpsb_optimizer.py``,
which also had none); donor-resolvability rests on the pinned git blob and
the source's own explicit incident-review docstrings, not an executed donor
backtest log.

* ``ColdHunterPredictor`` (``lottery_api/models/cold_hunter_predictor.py``)
  assumes history is ordered **newest-first** ("歷史開獎數據(最新在前)",
  every method's own docstring) -- opposite of this framework's
  ``CausalDrawRow`` contract (oldest-first, ``history[-1]`` most recent, per
  wave 3's module docstring). Every one of the six ported methods below
  therefore first reverses the received history
  (``history_desc = tuple(reversed(history))``) before running the donor's
  own newest-first index arithmetic untranslated. This is the same
  "transliterate against a known, fixed, opposite convention" precedent wave
  14 already used for ``repeat_booster_predict`` -- except here the fix is a
  single whole-history reversal up front (provably correct, since the donor
  code's only history-order assumption is "index 0 is the most recent
  draw"), not a partial/ambiguous case.
  - ``cold_hunter_predict``: hot(gap<=3)/warm(4-9)/cold(gap>=10) hybrid
    selection (default 3 hot + 1 warm + 2 cold), padded from the full
    gap-sorted list if short.
  - ``short_window_deviation_predict``: 50-draw rolling window (falls back
    to the full history if fewer than 10 draws are available) deviation
    score blended 75/25 with a gap-score computed over that same window.
  - ``rebound_aware_predict``: detects >=3 consecutive recent draws with
    <=2 "large" numbers (> the 25 midpoint) and, if triggered, skews the
    large/small split from 3:3 to 4:2; each half is filled hot-then-cold-
    then-warm from that half's own gap-sorted lists.
  - ``zone_momentum_predict``: 5 zones of size 9 (last zone absorbs the
    remainder to 49); momentum = recent-10-draw zone share minus full-
    history zone share; most-negative-momentum zones are filled first (2
    numbers if momentum < -0.05, else 1), each zone's own numbers ranked by
    gap descending. The donor has no pad/fallback step here (unlike
    ``cold_hunter_predict``/``moderate_rank_predict``): if none of the 5
    zones reach the -0.05 momentum threshold, every zone contributes only
    its 1-number quota and at most 5 numbers are ever collected -- a
    genuine donor-exact closure (caught by this port's own ``_ticket()``
    6-number check), not a bug in this port.
  - ``pure_cold_predict``: the 6 highest-gap numbers, full stop.
  - ``moderate_rank_predict``: excludes the immediately preceding draw's
    numbers, then deliberately skips the top 5 hottest numbers
    (``hot_nums[5:15]``) before building a 1-small+1-large-hot seed, 1 warm,
    and up to 2 "moderate cold" (gap 8-14) picks, padded from the full
    (last-draw-excluded) gap-ascending list.
  Only the ``numbers`` field of each donor return dict is load-bearing
  (matching every prior wave); each method's own discarded ``confidence``/
  ``method``/``meta_info`` fields (including the donor's own ``numpy``
  import, used only for a discarded ``np.mean`` confidence figure) are not
  ported, so this module needs no numpy dependency.
  The two donor composite methods on the same class
  (``ensemble_predict``/``anti_extreme_ensemble_predict``, both of which
  only recombine the six methods above into 3-4 native-ticket portfolios)
  are intentionally not registered in this batch -- see
  ``blocker_family_summary.md`` in this task's Evidence root.

* ``GapPressureScorer`` (``lottery_api/models/gap_pressure.py``) self-
  corrects its own history order by comparing ``history[0].date`` against
  ``history[-1].date`` and reversing only if descending -- since this
  framework's ``CausalDrawRow`` history is already ascending, that guard is
  always a no-op here and no reversal is performed. Its own "no data"
  fallback branch (``if not scores: ...`` inside ``predict``, reachable only
  when ``analyze()`` is handed a falsy/empty history) is not ported: this
  framework's own base-class ``min_history`` gate (set to 1 below) already
  makes an empty-history call to ``_predict`` unreachable, exactly like wave
  14's HPSB short-history branch reasoning. ``GapPressureScorer.__init__``'s
  own default is ``max_num=39`` (Lotto539-scale), but no caller anywhere in
  the donor tree ever instantiates this class with any value -- there is no
  real donor-observed default to inherit. The port uses ``max_num=49`` as
  the necessary BIG_LOTTO-correct value (39 would silently drop numbers
  40-49 from a 6/49 game), not as a transcription of a donor default.
  ``predict`` -- per-number "pressure ratio" (current gap / historical
  average inter-appearance interval) run through a fixed-steepness sigmoid,
  excluding the immediately preceding draw's own numbers, top-6 by score.

Two further methods port the same "dynamic method selection over a rolling
audit" family wave 14's HPSB already proved, reusing wave 14's own five
already-ported ``_unified_*_ticket`` functions (``hot_cold_mix``/``markov``/
``deviation``/``trend``/``statistical``, same fixed dict order) and its exact
``index = len(history) - window + offset`` audit-window formula -- no new
engine parity work is needed, only new audit/selection wiring:

* ``tools/test_dm_dms_biglotto.py`` ("DM-DMS"): the *same*
  ``audit_window=15`` rolling-hit-count audit as HPSB's own
  ``_dms_select_method``, but keeping the top **2** methods by hit count
  (ties broken by the fixed method order, since Python's ``sort`` is
  stable) rather than HPSB's top 1, and returning both methods' own tickets
  as a 2-native-ticket portfolio with no ZDP and no P1 kill-filtering (the
  donor script has neither). A method whose own ticket function raises
  (insufficient history) is skipped; the base class's own
  ``native_ticket_count`` check closes the strategy if fewer than 2 tickets
  survive -- not a bespoke exception here either.
* ``tools/test_dms_biglotto.py`` ("DMS", single-ticket, distinct from both
  wave 8's ``test_dms.py`` and HPSB's DMS): the audit only runs at all when
  causal history exceeds **50** draws (the donor's own
  ``if len(current_history) > audit_window`` gate, ``audit_window`` here
  being the donor's own default parameter value of 50 -- an unrelated
  constant from the audit-window formula's own window of 15); below that
  threshold ``best_method`` stays unconditionally ``'hot_cold_mix'`` with no
  audit computation performed at all. When the gate does fire, the audit
  itself uses a distinct fixed window of 15 (the donor's own
  ``fast_audit_p = min(15, audit_window)`` narrowing), and picks the
  strictly-highest hit count with first-occurrence-in-fixed-order tie-break
  (the donor's own ``elif m_hits == best_rate: if m_name == 'hot_cold_mix':
  best_method = m_name`` branch can never actually fire, since
  ``hot_cold_mix`` is always the first method audited and therefore always
  takes the initial ``if m_hits > best_rate`` branch on its own turn, never
  the ``elif`` -- ported literally rather than simplified away, the same
  "confirmed-dead branch stays, only proven-unreachable *whole functions*
  are omitted" precedent wave 14 already set for HPSB's static fallback).

Donor parity for the five shared engine methods (hot_cold_mix / markov /
deviation / trend / statistical) was already independently re-derived and
tested by waves 3/4/6 and reused byte-identically here (sibling modules in
the same ``strategies.adapters`` package, not a layer violation -- see
``tests/architecture/test_dependency_rules.py``). The six ``ColdHunterPredictor``
methods and ``GapPressureScorer.predict`` are new to this batch and were
independently derived by reading ``lottery_api/models/cold_hunter_predictor.py``
/ ``gap_pressure.py`` at the frozen commit.
"""

# pyright: reportPrivateUsage=false
# (intentional reuse of wave 3/4/6's already-verified private ticket
# helpers -- see module docstring; those wave modules are not modified)

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Callable

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import (
    BetAdapter,
    CausalDrawRow,
    PortfolioBetAdapter,
)
from lottolab.strategies.adapters.biglotto_wave3 import (
    _ticket,
    _unified_deviation_ticket,
    _unified_markov_ticket,
    _unified_statistical_ticket,
)
from lottolab.strategies.adapters.biglotto_wave4 import _unified_hot_cold_mix_ticket
from lottolab.strategies.adapters.biglotto_wave6 import _unified_trend_ticket

_MIN_NUM = 1
_MAX_NUM = 49
_PICK = 6
_MID_POINT = (_MIN_NUM + _MAX_NUM) // 2  # 25

_TicketFunc = Callable[[tuple[CausalDrawRow, ...]], tuple[int, ...]]


# ─── ColdHunterPredictor shared helper (newest-first convention; see module
#     docstring for the reversal reasoning) ─────────────────────────────────


def _gaps_desc(history_desc: tuple[CausalDrawRow, ...]) -> dict[int, int]:
    """Port ``ColdHunterPredictor.calculate_gaps`` (``history_desc[0]`` is
    the most recent draw; ``gap`` is periods since last appearance)."""

    gaps: dict[int, int] = {}
    for number in range(_MIN_NUM, _MAX_NUM + 1):
        for index, draw in enumerate(history_desc):
            if number in draw.numbers:
                gaps[number] = index
                break
        else:
            gaps[number] = len(history_desc)
    return gaps


# ─── legacy_biglotto__cold_hunter_predict__9e89f2b41add ─────────────────────


def _cold_hunter_predict(history: tuple[CausalDrawRow, ...]) -> tuple[int, ...]:
    """Port ``ColdHunterPredictor.cold_hunter_predict`` (defaults:
    ``hot_count=3, warm_count=1, cold_count=2``)."""

    history_desc = tuple(reversed(history))
    gaps = _gaps_desc(history_desc)
    hot_nums = sorted((item for item in gaps.items() if item[1] <= 3), key=lambda item: item[1])
    warm_nums = sorted(
        (item for item in gaps.items() if 4 <= item[1] <= 9),
        key=lambda item: item[1],
        reverse=True,
    )
    cold_nums = sorted(
        (item for item in gaps.items() if item[1] >= 10),
        key=lambda item: item[1],
        reverse=True,
    )

    predicted: list[int] = []
    for number, _gap in hot_nums[:3]:
        predicted.append(number)
    for number, _gap in warm_nums[:1]:
        if number not in predicted:
            predicted.append(number)
    for number, _gap in cold_nums[:2]:
        if number not in predicted:
            predicted.append(number)

    all_sorted = sorted(gaps.items(), key=lambda item: item[1], reverse=True)
    for number, _gap in all_sorted:
        if len(predicted) >= _PICK:
            break
        if number not in predicted:
            predicted.append(number)

    return _ticket(predicted[:_PICK])


class BigLottoColdHunterPredictAdapter(BetAdapter):
    """Cold Hunter V2: hot(3)+warm(1)+cold(2) hybrid gap-based selection."""

    strategy_id = "legacy_biglotto__cold_hunter_predict__9e89f2b41add"
    strategy_name = "大樂透冷號獵手V2預測器"
    strategy_version = "v0.1"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)

    def _predict(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[int, ...]:
        return _cold_hunter_predict(history)


# ─── legacy_biglotto__short_window_deviation_predict__9e89f2b41add ──────────


def _short_window_deviation_predict(history: tuple[CausalDrawRow, ...]) -> tuple[int, ...]:
    """Port ``ColdHunterPredictor.short_window_deviation_predict``
    (``window_size=50``)."""

    history_desc = tuple(reversed(history))
    total_numbers = _MAX_NUM - _MIN_NUM + 1

    recent_history = history_desc[:50]
    if len(recent_history) < 10:
        recent_history = history_desc

    all_numbers = [number for draw in recent_history for number in draw.numbers]
    frequency = Counter(all_numbers)
    expected_freq = (len(recent_history) * _PICK) / total_numbers

    scores: dict[int, float] = {}
    for number in range(_MIN_NUM, _MAX_NUM + 1):
        actual = frequency.get(number, 0)
        deviation = expected_freq - actual
        scores[number] = max(0.0, deviation)

    gaps = _gaps_desc(recent_history)
    max_gap = max(gaps.values()) if gaps else 1

    for number in range(_MIN_NUM, _MAX_NUM + 1):
        gap_score = gaps.get(number, 0) / max_gap
        scores[number] = scores.get(number, 0.0) * 0.75 + gap_score * 0.25

    sorted_scores = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    predicted = [number for number, _score in sorted_scores[:_PICK]]
    return _ticket(predicted)


class BigLottoShortWindowDeviationPredictAdapter(BetAdapter):
    """Short-window (50-draw) deviation score blended 75/25 with a
    same-window gap score."""

    strategy_id = "legacy_biglotto__short_window_deviation_predict__9e89f2b41add"
    strategy_name = "大樂透短期窗口偏差預測器"
    strategy_version = "v0.1"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)

    def _predict(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[int, ...]:
        return _short_window_deviation_predict(history)


# ─── legacy_biglotto__rebound_aware_predict__9e89f2b41add ───────────────────


def _detect_large_number_rebound(history_desc: tuple[CausalDrawRow, ...]) -> bool:
    """Port ``ColdHunterPredictor.detect_large_number_rebound`` (defaults:
    ``consecutive_threshold=3, max_large_count=2``); returns only
    ``should_rebound`` (the only field the caller reads)."""

    consecutive_small = 0
    found_break = False
    for draw in history_desc[:10]:
        large_count = sum(1 for number in draw.numbers if number > _MID_POINT)
        if not found_break:
            if large_count <= 2:
                consecutive_small += 1
            else:
                found_break = True
    return consecutive_small >= 3


def _rebound_aware_predict(history: tuple[CausalDrawRow, ...]) -> tuple[int, ...]:
    """Port ``ColdHunterPredictor.rebound_aware_predict``."""

    history_desc = tuple(reversed(history))
    should_rebound = _detect_large_number_rebound(history_desc)
    gaps = _gaps_desc(history_desc)

    large_nums = {number: gap for number, gap in gaps.items() if number > _MID_POINT}
    small_nums = {number: gap for number, gap in gaps.items() if number <= _MID_POINT}

    target_large, target_small = (4, 2) if should_rebound else (3, 3)

    predicted: list[int] = []

    large_hot = sorted(
        (item for item in large_nums.items() if item[1] <= 3), key=lambda item: item[1]
    )
    large_cold = sorted(
        (item for item in large_nums.items() if item[1] >= 10),
        key=lambda item: item[1],
        reverse=True,
    )
    large_warm = sorted(
        (item for item in large_nums.items() if 4 <= item[1] <= 9),
        key=lambda item: item[1],
        reverse=True,
    )

    if large_hot:
        predicted.append(large_hot[0][0])
    if large_cold:
        for number, _gap in large_cold:
            if number not in predicted:
                predicted.append(number)
                break
    for number, _gap in large_warm + large_cold[1:] + large_hot[1:]:
        if len([p for p in predicted if p > _MID_POINT]) >= target_large:
            break
        if number not in predicted:
            predicted.append(number)

    small_hot = sorted(
        (item for item in small_nums.items() if item[1] <= 3), key=lambda item: item[1]
    )
    small_cold = sorted(
        (item for item in small_nums.items() if item[1] >= 10),
        key=lambda item: item[1],
        reverse=True,
    )
    small_warm = sorted(
        (item for item in small_nums.items() if 4 <= item[1] <= 9),
        key=lambda item: item[1],
        reverse=True,
    )

    if small_hot:
        for number, _gap in small_hot:
            if number not in predicted:
                predicted.append(number)
                break
    for number, _gap in small_warm + small_cold + small_hot[1:]:
        if len([p for p in predicted if p <= _MID_POINT]) >= target_small:
            break
        if number not in predicted:
            predicted.append(number)

    return _ticket(predicted[:_PICK])


class BigLottoReboundAwarePredictAdapter(BetAdapter):
    """Rebound-aware V2: large/small split skewed 4:2 (vs normal 3:3) when
    >=3 consecutive recent draws show <=2 large numbers; each half filled
    hot-then-cold-then-warm."""

    strategy_id = "legacy_biglotto__rebound_aware_predict__9e89f2b41add"
    strategy_name = "大樂透回擺感知V2預測器"
    strategy_version = "v0.1"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)

    def _predict(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[int, ...]:
        return _rebound_aware_predict(history)


# ─── legacy_biglotto__zone_momentum_predict__9e89f2b41add ───────────────────

_ZONE_SIZE = (_MAX_NUM - _MIN_NUM + 1) // 5  # 9


def _zone_ranges() -> dict[int, list[int]]:
    zones: dict[int, list[int]] = {}
    for i in range(1, 6):
        start = _MIN_NUM + (i - 1) * _ZONE_SIZE
        end = _MAX_NUM if i == 5 else _MIN_NUM + i * _ZONE_SIZE - 1
        zones[i] = list(range(start, end + 1))
    return zones


def _zone_momentum(history_desc: tuple[CausalDrawRow, ...]) -> dict[int, float]:
    """Port ``ColdHunterPredictor.calculate_zone_momentum`` (``window_size=10``);
    returns only the ``momentum`` mapping (the only field the caller reads)."""

    zones = _zone_ranges()
    number_zone = {number: zone_id for zone_id, numbers in zones.items() for number in numbers}

    long_term_counts = dict.fromkeys(zones, 0)
    for draw in history_desc:
        for number in draw.numbers:
            long_term_counts[number_zone[number]] += 1
    total_long = sum(long_term_counts.values())
    long_term_ratio = {
        zone: (count / total_long if total_long > 0 else 0.2)
        for zone, count in long_term_counts.items()
    }

    short_term_counts = dict.fromkeys(zones, 0)
    for draw in history_desc[:10]:
        for number in draw.numbers:
            short_term_counts[number_zone[number]] += 1
    total_short = sum(short_term_counts.values())
    short_term_ratio = {
        zone: (count / total_short if total_short > 0 else 0.2)
        for zone, count in short_term_counts.items()
    }

    return {zone: short_term_ratio[zone] - long_term_ratio[zone] for zone in zones}


def _zone_momentum_predict(history: tuple[CausalDrawRow, ...]) -> tuple[int, ...]:
    """Port ``ColdHunterPredictor.zone_momentum_predict``."""

    history_desc = tuple(reversed(history))
    zones = _zone_ranges()
    momentum = _zone_momentum(history_desc)
    gaps = _gaps_desc(history_desc)

    sorted_zones = sorted(momentum.items(), key=lambda item: item[1])

    predicted: list[int] = []
    for zone_id, mom in sorted_zones:
        if len(predicted) >= _PICK:
            break
        zone_gaps = sorted(
            ((number, gaps.get(number, 0)) for number in zones[zone_id]),
            key=lambda item: item[1],
            reverse=True,
        )
        count = 2 if mom < -0.05 else 1
        for number, _gap in zone_gaps:
            if number not in predicted:
                predicted.append(number)
                if len(predicted) >= _PICK:
                    break
                count -= 1
                if count <= 0:
                    break

    return _ticket(predicted[:_PICK])


class BigLottoZoneMomentumPredictAdapter(BetAdapter):
    """5-zone (size 9, last zone absorbs the remainder) momentum-tilt
    selection: most-negative-momentum zones filled first. Closes (no
    fallback pad) if none of the 5 zones reach the -0.05 momentum
    threshold -- see module docstring."""

    strategy_id = "legacy_biglotto__zone_momentum_predict__9e89f2b41add"
    strategy_name = "大樂透區域動量預測器"
    strategy_version = "v0.1"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)

    def _predict(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[int, ...]:
        return _zone_momentum_predict(history)


# ─── legacy_biglotto__pure_cold_predict__9e89f2b41add ───────────────────────


def _pure_cold_predict(history: tuple[CausalDrawRow, ...]) -> tuple[int, ...]:
    """Port ``ColdHunterPredictor.pure_cold_predict`` (``top_n=6``)."""

    history_desc = tuple(reversed(history))
    gaps = _gaps_desc(history_desc)
    sorted_by_gap = sorted(gaps.items(), key=lambda item: item[1], reverse=True)
    predicted = [number for number, _gap in sorted_by_gap[:6]]
    return _ticket(predicted)


class BigLottoPureColdPredictAdapter(BetAdapter):
    """Pure Cold: the 6 highest-gap numbers, full stop."""

    strategy_id = "legacy_biglotto__pure_cold_predict__9e89f2b41add"
    strategy_name = "大樂透純冷號預測器"
    strategy_version = "v0.1"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)

    def _predict(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[int, ...]:
        return _pure_cold_predict(history)


# ─── legacy_biglotto__moderate_rank_predict__9e89f2b41add ───────────────────


def _moderate_rank_predict(history: tuple[CausalDrawRow, ...]) -> tuple[int, ...]:
    """Port ``ColdHunterPredictor.moderate_rank_predict`` (defaults:
    ``exclude_last_draw=True, hot_rank_range=(5, 15), cold_gap_range=(8, 14)``)."""

    history_desc = tuple(reversed(history))
    gaps = _gaps_desc(history_desc)

    last_draw_nums: set[int] = set(history_desc[0].numbers) if history_desc else set()
    filtered_gaps = {number: gap for number, gap in gaps.items() if number not in last_draw_nums}

    hot_nums = sorted(
        (item for item in filtered_gaps.items() if item[1] <= 3), key=lambda item: item[1]
    )
    warm_nums = sorted(
        (item for item in filtered_gaps.items() if 4 <= item[1] <= 7),
        key=lambda item: item[1],
        reverse=True,
    )
    moderate_cold = sorted(
        (item for item in filtered_gaps.items() if 8 <= item[1] <= 14),
        key=lambda item: item[1],
        reverse=True,
    )

    predicted: list[int] = []

    selected_hot = hot_nums[5:15]
    hot_small = [number for number, _gap in selected_hot if number <= _MID_POINT]
    hot_large = [number for number, _gap in selected_hot if number > _MID_POINT]
    if hot_small:
        predicted.append(hot_small[0])
    if hot_large:
        predicted.append(hot_large[0])
    for number, _gap in selected_hot:
        if len([p for p in predicted if gaps.get(p, 0) <= 3]) >= 3:
            break
        if number not in predicted:
            predicted.append(number)

    for number, _gap in warm_nums[:3]:
        if number not in predicted:
            predicted.append(number)
            break

    cold_count = 0
    for number, _gap in moderate_cold:
        if cold_count >= 2:
            break
        if number not in predicted:
            predicted.append(number)
            cold_count += 1

    all_filtered = sorted(filtered_gaps.items(), key=lambda item: item[1])
    for number, _gap in all_filtered:
        if len(predicted) >= _PICK:
            break
        if number not in predicted:
            predicted.append(number)

    return _ticket(predicted[:_PICK])


class BigLottoModerateRankPredictAdapter(BetAdapter):
    """Moderate-rank selection: excludes the prior draw's own numbers,
    deliberately skips the top-5 hottest numbers, then blends a
    mid-ranked hot/warm/moderate-cold structure."""

    strategy_id = "legacy_biglotto__moderate_rank_predict__9e89f2b41add"
    strategy_name = "大樂透中值選號預測器"
    strategy_version = "v0.1"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)

    def _predict(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[int, ...]:
        return _moderate_rank_predict(history)


# ─── legacy_biglotto__gap_pressure_scorer__5e862ef27ee6 ─────────────────────


def _gap_pressure_sigmoid(x: float, steepness: float = 3.0) -> float:
    return 1.0 / (1.0 + math.exp(-steepness * x))


def _gap_pressure_scores(history_asc: tuple[CausalDrawRow, ...]) -> dict[int, float]:
    """Port ``GapPressureScorer.analyze`` (``max_num=49``); returns only the
    ``scores`` mapping (the only field the caller reads). ``history_asc`` is
    already ascending -- see module docstring for why no reversal guard is
    needed here."""

    n_draws = len(history_asc)
    scores: dict[int, float] = {}
    for number in range(_MIN_NUM, _MAX_NUM + 1):
        appearances = [index for index, draw in enumerate(history_asc) if number in draw.numbers]
        if not appearances:
            scores[number] = 2.0
            continue
        count = len(appearances)
        last_appearance = appearances[-1]
        current_gap = (n_draws - 1) - last_appearance
        if count >= 2:
            intervals = [appearances[i + 1] - appearances[i] for i in range(count - 1)]
            avg_interval = sum(intervals) / len(intervals)
        else:
            avg_interval = n_draws / count
        avg_interval = max(avg_interval, 1.0)
        ratio = current_gap / avg_interval
        scores[number] = _gap_pressure_sigmoid(ratio - 1.0) * 2.0
    return scores


def _gap_pressure_predict(history: tuple[CausalDrawRow, ...]) -> tuple[int, ...]:
    """Port ``GapPressureScorer.predict`` (the "no data" fallback is
    unreachable given ``min_history=1``; see module docstring)."""

    scores = _gap_pressure_scores(history)
    last_draw_nums = set(history[-1].numbers)
    candidates = sorted(
        ((number, score) for number, score in scores.items() if number not in last_draw_nums),
        key=lambda item: item[1],
        reverse=True,
    )
    predicted = [number for number, _score in candidates[:_PICK]]
    return _ticket(predicted)


class BigLottoGapPressureScorerAdapter(BetAdapter):
    """Gap Pressure Scorer: per-number sigmoid("current gap / historical
    average interval") pressure score, excluding the immediately preceding
    draw's own numbers."""

    strategy_id = "legacy_biglotto__gap_pressure_scorer__5e862ef27ee6"
    strategy_name = "大樂透遺漏壓力計分預測器"
    strategy_version = "v0.1"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)

    def _predict(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[int, ...]:
        return _gap_pressure_predict(history)


# ─── Dynamic-method-selection family (reuses wave 3/4/6's already-ported
#     engine tickets and wave 14 HPSB's audit-window formula) ───────────────

_DMS_METHODS: tuple[tuple[str, _TicketFunc], ...] = (
    ("hot_cold_mix", _unified_hot_cold_mix_ticket),
    ("markov", _unified_markov_ticket),
    ("deviation", _unified_deviation_ticket),
    ("trend", _unified_trend_ticket),
    ("statistical", _unified_statistical_ticket),
)


def _audit_hit_counts(
    history: tuple[CausalDrawRow, ...],
    window: int,
) -> list[tuple[str, int]]:
    """Shared rolling-window hit-count audit (fixed method order; matches
    wave 14 HPSB's ``_dms_select_method`` formula exactly, parameterized by
    ``window``)."""

    perf: list[tuple[str, int]] = []
    for name, func in _DMS_METHODS:
        hits = 0
        for offset in range(window):
            index = len(history) - window + offset
            if index <= 0:
                continue
            target = set(history[index].numbers)
            causal_prefix = history[:index]
            try:
                result = func(causal_prefix)
            except ValueError:
                continue
            if len(set(result) & target) >= 3:
                hits += 1
        perf.append((name, hits))
    return perf


# ─── legacy_biglotto__test_dm_dms_biglotto__bad71858012d ────────────────────

_DM_DMS_AUDIT_WINDOW = 15


def _dm_dms_tickets(history: tuple[CausalDrawRow, ...]) -> tuple[tuple[int, ...], ...]:
    """Port ``run_dm_dms_benchmark``'s top-2 method selection (audit_window=15,
    no outer gate, no ZDP, no P1 kill-filtering)."""

    perf = _audit_hit_counts(history, _DM_DMS_AUDIT_WINDOW)
    ranked = sorted(perf, key=lambda item: item[1], reverse=True)
    top2_names = [name for name, _hits in ranked[:2]]
    methods_by_name = dict(_DMS_METHODS)

    tickets: list[tuple[int, ...]] = []
    for name in top2_names:
        try:
            tickets.append(methods_by_name[name](history))
        except ValueError:
            continue
    return tuple(tickets)


class BigLottoTestDmDmsBiglottoAdapter(PortfolioBetAdapter):
    """DM-DMS: rolling audit_window=15 hit-count audit over
    hot_cold_mix/markov/deviation/trend/statistical, top-2 methods each
    contribute one native ticket -- a 2-native-ticket portfolio (fewer than
    2 legal bets closes via the base class's own native ticket count
    check)."""

    strategy_id = "legacy_biglotto__test_dm_dms_biglotto__bad71858012d"
    strategy_name = "大樂透 DM-DMS 雙注動態方法選擇預測器"
    strategy_version = "v0.1"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)
    native_ticket_count = 2

    def _predict_all(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[tuple[int, ...], ...]:
        return _dm_dms_tickets(history)


# ─── legacy_biglotto__test_dms_biglotto__10e39919c3a1 ───────────────────────

_DMS_SOLO_AUDIT_GATE = 50
_DMS_SOLO_FAST_AUDIT = 15


def _dms_solo_select_method(history: tuple[CausalDrawRow, ...]) -> str:
    """Port ``run_dms_benchmark``'s single-method selection: the audit only
    runs when causal history exceeds 50 draws (the donor's own
    ``audit_window`` default, unrelated to the fast-audit window of 15
    below); otherwise ``best_method`` stays unconditionally
    ``'hot_cold_mix'``. See module docstring for why the donor's own
    ``elif m_hits == best_rate: ... 'hot_cold_mix'`` tie-break branch is
    ported as literally-dead code rather than omitted."""

    if len(history) <= _DMS_SOLO_AUDIT_GATE:
        return "hot_cold_mix"

    best_method = "hot_cold_mix"
    best_rate = -1
    for name, func in _DMS_METHODS:
        hits = 0
        for offset in range(_DMS_SOLO_FAST_AUDIT):
            index = len(history) - _DMS_SOLO_FAST_AUDIT + offset
            if index <= 0:
                continue
            target = set(history[index].numbers)
            causal_prefix = history[:index]
            try:
                result = func(causal_prefix)
            except ValueError:
                continue
            if len(set(result) & target) >= 3:
                hits += 1
        if hits > best_rate:
            best_rate = hits
            best_method = name
        elif hits == best_rate and name == "hot_cold_mix":
            best_method = name
    return best_method


def _dms_solo_ticket(history: tuple[CausalDrawRow, ...]) -> tuple[int, ...]:
    methods_by_name = dict(_DMS_METHODS)
    chosen = methods_by_name[_dms_solo_select_method(history)]
    return chosen(history)


class BigLottoTestDmsBiglottoAdapter(BetAdapter):
    """DMS (single-ticket): audit-gated (>50 causal draws) single-method
    selection via a fast_audit_p=15 rolling-hit-count window; below the
    gate, always ``hot_cold_mix`` with no audit at all -- a single-ticket
    strategy, distinct from both wave 8's ``test_dms`` (window=30, top-3,
    8-method pool) and HPSB's DMS (gate at 20 draws, not 50)."""

    strategy_id = "legacy_biglotto__test_dms_biglotto__10e39919c3a1"
    strategy_name = "大樂透 DMS 動態方法選擇預測器"
    strategy_version = "v0.1"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)

    def _predict(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[int, ...]:
        return _dms_solo_ticket(history)


__all__ = [
    "BigLottoColdHunterPredictAdapter",
    "BigLottoGapPressureScorerAdapter",
    "BigLottoModerateRankPredictAdapter",
    "BigLottoPureColdPredictAdapter",
    "BigLottoReboundAwarePredictAdapter",
    "BigLottoShortWindowDeviationPredictAdapter",
    "BigLottoTestDmDmsBiglottoAdapter",
    "BigLottoTestDmsBiglottoAdapter",
    "BigLottoZoneMomentumPredictAdapter",
]
