"""BigLotto native-strategy wave 10: thin ports of three frozen legacy
BACKTESTED methods (donor commit ``49a25effa62fc24f40789c16be6f11bdfb41a4a9``,
the same frozen snapshot as waves 1-9). No algorithm was changed, tuned, or
"improved" during the port.

* ``legacy_biglotto__enhanced_dual_bet_predictor__d5b3de348d01`` -- donor
  ``lottery_api/models/enhanced_dual_bet_predictor.py::EnhancedDualBetPredictor
  .predict('BIG_LOTTO')``. Bet 1 is the donor's ``zone_balance_predict`` over
  the causal window's most recent 500 draws; bet 2 is ``bayesian_predict``
  over the most recent 300; both are then passed through the donor's
  ``NegativeSelector.analyze``/``filter_prediction`` (cold-and-overdue,
  or cold-and-recently-cold, exclusion with hottest-available replacement).
  Deterministic; no RNG anywhere on this path.
* ``legacy_biglotto__biglotto_diversified_ensemble_v6__8caaac8fcb5d`` --
  donor ``tools/biglotto_diversified_ensemble_v6.py::DiversifiedEnsemble
  .predict_3bets``. Bet 1 (Consensus) samples from the union of the
  ``bayesian_predict``/``frequency_predict`` top-6 pools, validated against
  the causal window's own AC-value/entropy distribution; bet 2 (Synergy)
  samples from the top-20 nodes by donor-exact weighted degree/betweenness
  graph centrality over a co-occurrence graph; bet 3 (Disruptor) samples
  from a hot-tail-digit pool with a regime-adaptive odd-count floor. The
  donor resets both Python's and NumPy's global RNG to seed 42 at the top of
  every ``predict_3bets`` call; this port resets a local ``random.Random(42)``
  instead of the process-global module (bit-for-bit identical output --
  CPython's global ``random`` module is itself just such an instance freshly
  seeded -- without the global-mutation this framework's adapters must avoid).
  The donor's own ``np.random.seed(42)`` call is never followed by any
  ``np.random.*`` draw anywhere on this path (confirmed by executing the
  frozen donor bytes against real NumPy in an isolated oracle across five
  causal-history lengths spanning 150-2100 draws): it is provably a no-op on
  the ticket output and is omitted along with the special-number computation
  (``predict_special_number``, itself proven RNG-free for BIG_LOTTO's
  'markov'/'bayesian' strategy names -- see the sibling test file).
* ``legacy_biglotto__backtest_strategy_1__41ed79a6de62`` -- donor
  ``tools/backtest_strategy_1.py::PostSelectionBacktester.run``'s per-target
  ticket pair: bet 1 is a Frequency-50 post-filter (skip any number in the
  "danger" triple-streak set, keep scanning); bet 2 is ``zone_balance_predict``
  over the most recent 500 draws, retried at 510 if it lands on a danger
  number, with the donor's own bare-except fallback to ``(1,2,3,4,5,6)``
  preserved verbatim (a genuine frozen behavior, not an invented one).
  Deterministic; no RNG.

Shared building blocks (``_zone_balance_ticket``, ``_bayesian_desc_ticket``,
donor-exact weighted degree/betweenness centrality, ``_ticket``) are
independent, from-scratch transcriptions -- not imports -- of application-
layer siblings: ``strategies.adapters`` may not import ``lottolab.application``
(see ``tests/architecture/test_dependency_rules.py::
test_strategy_adapters_are_target_native_db_free_and_offline``), and no
third-party graph/array library may be added to this dependency-free layer
either. All three were independently re-derived and verified (not merely
assumed) by executing the exact frozen donor bytes -- AST-extracted from the
pinned commit and run with real NumPy/NetworkX in an isolated, throwaway
environment never touched by this repository's own dependencies -- against
five causal-history windows (150, 450, 900, 1400, 2100 draws) spanning
multiple lottery-era draw-number digit-length boundaries.

Two donor-side subtleties, found only by that executable verification and
not by reading the source, are load-bearing here and are NOT bugs to "fix":

1. ``zone_balance_predict``'s own history-order guard compares draw-number
   strings (``history[0]['draw'] > history[-1]['draw']``) rather than
   comparing them as integers. Because draw numbers are not zero-padded to a
   fixed width across era boundaries (8-digit ``"99xxxxxx"`` vs 9-digit
   ``"100xxxxxx"``), this lexicographic comparison can mis-fire exactly at
   those boundaries -- it is replicated exactly (see ``_zone_balance_ticket``
   below), not replaced with a numeric comparison.
2. ``bayesian_predict`` and ``frequency_predict`` have no such guard at all:
   their "most recent N" windowing is whatever the *caller's* history order
   makes it. Both ``enhanced_dual_bet_predictor.py`` and
   ``biglotto_diversified_ensemble_v6.py`` call
   ``self.db.get_all_draws(...)`` directly with **no** reversal, i.e. with
   newest-first (DESC) history, so ``bayesian_predict``'s internal
   ``history[-20:]`` actually selects the OLDEST 20 draws of the window it
   was given, and (independently) ``frequency_predict``'s ``gaps`` computation
   forward-scans assuming index 0 is newest -- true only because these two
   callers really do pass DESC data. ``_bayesian_desc_ticket`` and
   ``_v6_frequency_ticket`` below model this exactly for these two donor
   call sites; they are deliberately NOT a drop-in replacement for any other
   caller of the donor's ``bayesian_predict``/``frequency_predict``.
"""

# pyright: reportPrivateUsage=false
# (intentional reuse of wave 3's already-verified private ticket helper --
# see module docstring; wave 3 is not modified)

from __future__ import annotations

import heapq
import math
import random
from collections import Counter
from itertools import combinations, count

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import CausalDrawRow, PortfolioBetAdapter
from lottolab.strategies.adapters.biglotto_wave3 import _ticket

_MIN_NUM = 1
_MAX_NUM = 49
_PICK = 6


# ─── shared: zone_balance_predict port (self-corrects history order) ───────


def _zone_balance_ticket(history: tuple[CausalDrawRow, ...]) -> tuple[int, ...]:
    """Port ``UnifiedPredictionEngine.zone_balance_predict``'s BIG_LOTTO
    number selection, including its own (lexicographic, era-boundary-buggy)
    history-order guard -- see module docstring point 1."""

    if len(history) > 1 and history[0].draw > history[-1].draw:
        history = tuple(reversed(history))
    frequency = Counter(number for draw in history for number in draw.numbers)
    ranked_frequency = sorted(
        range(_MIN_NUM, _MAX_NUM + 1), key=lambda number: frequency.get(number, 0), reverse=True
    )
    zone_sizes = (13, 12, 12, 12)
    zones: list[tuple[int, ...]] = []
    offset = 0
    for size in zone_sizes:
        zones.append(tuple(sorted(ranked_frequency[offset : offset + size])))
        offset += size

    analysis_window = min(len(history), 80)
    zone_counts = [0] * len(zones)
    for draw in history[-analysis_window:]:
        for number in draw.numbers:
            for index, zone in enumerate(zones):
                if min(zone) <= number <= max(zone):
                    zone_counts[index] += 1
                    break

    recent_zone_counts = [0] * len(zones)
    for draw in history[-20:]:
        for number in draw.numbers:
            for index, zone in enumerate(zones):
                if min(zone) <= number <= max(zone):
                    recent_zone_counts[index] += 1
                    break

    total = sum(zone_counts) or 1
    recent_total = sum(recent_zone_counts) or 1
    targets = [
        round((zone_counts[i] / total * 0.7 + recent_zone_counts[i] / recent_total * 0.3) * _PICK)
        for i in range(len(zones))
    ]
    while sum(targets) < _PICK:
        targets[targets.index(min(targets))] += 1
    while sum(targets) > _PICK:
        targets[targets.index(max(targets))] -= 1

    recent_frequency = Counter(number for draw in history[-30:] for number in draw.numbers)
    predicted: list[int] = []
    for index, zone in enumerate(zones):
        scored = [
            (number, frequency.get(number, 0) * 0.6 + recent_frequency.get(number, 0) * 0.4)
            for number in zone
        ]
        scored.sort(key=lambda item: item[1], reverse=True)
        predicted.extend(number for number, _score in scored[: targets[index]])
    return tuple(predicted)


# ─── legacy_biglotto__enhanced_dual_bet_predictor__d5b3de348d01 ────────────
# Donor: lottery_api/models/enhanced_dual_bet_predictor.py::
# EnhancedDualBetPredictor.predict('BIG_LOTTO', apply_exclusion=True).


def _bayesian_desc_ticket(history: tuple[CausalDrawRow, ...]) -> tuple[int, ...]:
    """Port ``bayesian_predict`` exactly as it behaves when called with
    newest-first (DESC) history -- see module docstring point 2. ``history``
    here is this framework's normal oldest-first window; the "most recent
    20" the donor's un-guarded ``history[-20:]`` actually selects, given its
    real DESC calling context, is this window's OLDEST 20 draws."""

    total_draws = len(history)
    long_term_frequency = Counter(number for draw in history for number in draw.numbers)
    recent_window = 20
    recent_history = history[:recent_window] if total_draws > recent_window else history
    recent_frequency = Counter(number for draw in recent_history for number in draw.numbers)
    if len(recent_history) < 5:
        stability = 0.5
    else:
        frequencies = list(
            Counter(number for draw in recent_history for number in draw.numbers).values()
        )
        if len(frequencies) < 2:
            stability = 0.5
        else:
            mean = sum(frequencies) / len(frequencies)
            if mean == 0:
                stability = 0.5
            else:
                variance = sum((value - mean) ** 2 for value in frequencies) / len(frequencies)
                stability = 1 / (1 + math.sqrt(variance) / mean)
    if total_draws < 50:
        likelihood_weight, prior_weight = 0.75, 0.25
    elif total_draws < 100:
        likelihood_weight, prior_weight = (0.65, 0.35) if stability > 0.7 else (0.55, 0.45)
    else:
        likelihood_weight, prior_weight = (0.6, 0.4) if stability > 0.7 else (0.5, 0.5)

    scores: dict[int, float] = {}
    for number in range(_MIN_NUM, _MAX_NUM + 1):
        prior = long_term_frequency.get(number, 0) / (total_draws * _PICK)
        if prior == 0:
            prior = 1 / (total_draws * _PICK * 10)
        likelihood = recent_frequency.get(number, 0) / len(recent_history)
        scores[number] = likelihood * likelihood_weight + prior * prior_weight
    ranked = sorted(range(_MIN_NUM, _MAX_NUM + 1), key=lambda number: scores[number], reverse=True)
    return tuple(ranked[:_PICK])


_COLD_WINDOW = 100
_COLD_PERCENTILE = 20
_OVERDUE_WINDOW = 50
_OVERDUE_THRESHOLD = 15
_RECENT_COLD_WINDOW = 20
_RECENT_COLD_MIN_COUNT = 2


def _negative_selection_excluded(history_desc: tuple[CausalDrawRow, ...]) -> set[int]:
    """Port ``NegativeSelector.analyze``'s BIG_LOTTO defaults. ``history_desc``
    is newest-first, matching the donor's own DB order -- unlike
    ``bayesian_predict``/``zone_balance_predict``, ``[:window]`` here is not a
    bug: on genuinely DESC data it correctly means "the most recent window"."""

    cold_freq: Counter[int] = Counter()
    cold_window = min(_COLD_WINDOW, len(history_desc))
    for draw in history_desc[:cold_window]:
        cold_freq.update(draw.numbers)
    counts = [(number, cold_freq.get(number, 0)) for number in range(_MIN_NUM, _MAX_NUM + 1)]
    counts.sort(key=lambda item: item[1])
    cutoff = int(_MAX_NUM * _COLD_PERCENTILE / 100)
    cold = {number for number, _count in counts[:cutoff]}

    last_seen = {number: 9999 for number in range(_MIN_NUM, _MAX_NUM + 1)}
    overdue_window = min(_OVERDUE_WINDOW, len(history_desc))
    for index, draw in enumerate(history_desc[:overdue_window]):
        for number in draw.numbers:
            if last_seen[number] > index:
                last_seen[number] = index
    overdue = {number for number, gap in last_seen.items() if gap >= _OVERDUE_THRESHOLD}

    recent_freq: Counter[int] = Counter()
    for draw in history_desc[:_RECENT_COLD_WINDOW]:
        recent_freq.update(draw.numbers)
    recent_cold = {
        number
        for number in range(_MIN_NUM, _MAX_NUM + 1)
        if recent_freq.get(number, 0) < _RECENT_COLD_MIN_COUNT
    }

    return (cold & overdue) | (cold & recent_cold)


def _filter_prediction(
    prediction: list[int], excluded: set[int], history_desc: tuple[CausalDrawRow, ...]
) -> list[int]:
    """Port ``NegativeSelector.filter_prediction``: replace each excluded
    number with the hottest available replacement (by frequency over the
    most recent 50 draws), preserving the donor's own closure -- if
    replacements collapse the result below 6 unique numbers via the final
    ``sorted(set(...))[:len(prediction)]``, that is a genuine donor-faithful
    closure surfaced by this adapter's own output validation, not a bug."""

    freq: Counter[int] = Counter()
    for draw in history_desc[:50]:
        freq.update(draw.numbers)
    available = [
        number
        for number in range(_MIN_NUM, _MAX_NUM + 1)
        if number not in excluded and number not in prediction
    ]
    available.sort(key=lambda number: -freq.get(number, 0))
    result: list[int] = []
    replacements = iter(available)
    for number in prediction:
        if number in excluded:
            try:
                result.append(next(replacements))
            except StopIteration:
                result.append(number)
        else:
            result.append(number)
    return sorted(set(result))[: len(prediction)]


class BigLottoEnhancedDualBetAdapter(PortfolioBetAdapter):
    """Two tickets: zone-balance (500-window) then Bayesian (300-window),
    both negative-selection filtered."""

    strategy_id = "legacy_biglotto__enhanced_dual_bet_predictor__d5b3de348d01"
    strategy_name = "大樂透增強型雙注預測"
    strategy_version = "v0.1"
    min_history = 100
    supported_lottery_types = (LotteryType.BIG_LOTTO,)
    native_ticket_count = 2

    def _predict_all(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[tuple[int, ...], ...]:
        history_desc = tuple(reversed(history))
        excluded = _negative_selection_excluded(history_desc)
        bet1_raw = _zone_balance_ticket(history[-500:])
        bet2_raw = _bayesian_desc_ticket(history[-300:])
        if excluded:
            bet1 = _filter_prediction(list(bet1_raw), excluded, history_desc)
            bet2 = _filter_prediction(list(bet2_raw), excluded, history_desc)
        else:
            bet1 = sorted(bet1_raw)
            bet2 = sorted(bet2_raw)
        return (_ticket(bet1), _ticket(bet2))


# ─── legacy_biglotto__biglotto_diversified_ensemble_v6__8caaac8fcb5d ───────
# Donor: tools/biglotto_diversified_ensemble_v6.py::DiversifiedEnsemble
# .predict_3bets() (default history = get_history(limit=1000)).


def _v6_frequency_ticket(history: tuple[CausalDrawRow, ...]) -> tuple[int, ...]:
    """Port ``frequency_predict`` exactly as called by V6's ``predict_3bets``
    (which passes genuinely DESC history) -- see module docstring point 2."""

    total_draws = len(history)
    basic_frequency = Counter(number for draw in history for number in draw.numbers)
    theoretical_avg_frequency = total_draws * _PICK / _MAX_NUM

    gaps: dict[int, int] = {}
    for index, draw in enumerate(reversed(history)):
        for number in draw.numbers:
            if number not in gaps:
                gaps[number] = index
    for number in range(_MIN_NUM, _MAX_NUM + 1):
        if number not in gaps:
            gaps[number] = total_draws

    analysis_window = 200
    recent_history = history[-analysis_window:] if total_draws > analysis_window else history
    weighted_counts: dict[int, float] = {}
    total_weight = 0.0
    for index, draw in enumerate(reversed(recent_history)):
        for number in draw.numbers:
            frequency_ratio = (
                basic_frequency.get(number, 0) / theoretical_avg_frequency
                if theoretical_avg_frequency
                else 0.0
            )
            if frequency_ratio > 1.3:
                decay_rate = 0.018
            elif frequency_ratio > 1.1:
                decay_rate = 0.013
            elif frequency_ratio < 0.7:
                decay_rate = 0.007
            elif frequency_ratio < 0.9:
                decay_rate = 0.009
            else:
                decay_rate = 0.01
            weight = math.exp(-decay_rate * index)
            weighted_counts[number] = weighted_counts.get(number, 0.0) + weight
            total_weight += weight

    max_gap = max(gaps.values()) if gaps else 1
    scores: dict[int, float] = {}
    for number in range(_MIN_NUM, _MAX_NUM + 1):
        freq_score = (
            weighted_counts.get(number, 0.0) / (total_weight / _MAX_NUM)
            if total_weight > 0
            else 0.0
        )
        gap_score = gaps.get(number, 0) / max_gap if max_gap > 0 else 0.0
        scores[number] = 0.4 * freq_score + 0.6 * gap_score
    ranked = sorted(range(_MIN_NUM, _MAX_NUM + 1), key=lambda number: scores[number], reverse=True)
    return tuple(ranked[:_PICK])


def _calculate_ac_value(numbers: tuple[int, ...]) -> int:
    if not numbers:
        return 0
    diffs: set[int] = set()
    ordered = sorted(numbers)
    for i in range(len(ordered)):
        for j in range(i + 1, len(ordered)):
            diffs.add(ordered[j] - ordered[i])
    return len(diffs) - (len(ordered) - 1)


def _calculate_entropy(numbers: tuple[int, ...], max_num: int = _MAX_NUM) -> float:
    if not numbers:
        return 0.0
    ordered = sorted(numbers)
    gaps = (
        [ordered[0]]
        + [ordered[index + 1] - ordered[index] for index in range(len(ordered) - 1)]
        + [max_num - ordered[-1]]
    )
    total_gap = sum(gaps)
    probabilities = [gap / total_gap for gap in gaps if gap > 0]
    return -sum(probability * math.log2(probability) for probability in probabilities)


def _structural_stats(history: tuple[CausalDrawRow, ...]) -> dict[str, float]:
    window = history[-100:]
    acs = [_calculate_ac_value(draw.numbers) for draw in window if draw.numbers]
    entropies = [_calculate_entropy(draw.numbers) for draw in window if draw.numbers]
    if not acs:
        return {"ac_avg": 8.0, "ac_std": 1.0, "entropy_avg": 2.5, "entropy_std": 0.2}
    ac_avg = sum(acs) / len(acs)
    ac_std = math.sqrt(sum((value - ac_avg) ** 2 for value in acs) / len(acs))
    entropy_avg = sum(entropies) / len(entropies)
    entropy_std = math.sqrt(sum((value - entropy_avg) ** 2 for value in entropies) / len(entropies))
    return {
        "ac_avg": ac_avg,
        "ac_std": ac_std,
        "entropy_avg": entropy_avg,
        "entropy_std": entropy_std,
    }


def _validate_combination(numbers: tuple[int, ...], stats: dict[str, float]) -> bool:
    ac_value = _calculate_ac_value(numbers)
    entropy = _calculate_entropy(numbers)
    return not (
        ac_value < stats["ac_avg"] - 1.5 * stats["ac_std"]
        or entropy < stats["entropy_avg"] - 1.5 * stats["entropy_std"]
    )


def _detect_regime(history: tuple[CausalDrawRow, ...]) -> str:
    window = history[-10:]
    imbalance_count = 0
    for draw in window:
        if draw.numbers:
            odd_ratio = sum(1 for number in draw.numbers if number % 2 == 1) / 6
            if odd_ratio >= 0.8 or odd_ratio <= 0.2:
                imbalance_count += 1
    return "SKEWED" if imbalance_count >= 2 else "BALANCED"


def _graph_adjacency(
    history: tuple[CausalDrawRow, ...], lookback: int
) -> dict[int, dict[int, float]]:
    """Port ``BiglottoGraph.build_from_history``'s edge weights (node
    "features" are computed by the donor but never consumed by
    ``predict_3bets``, so omitted here)."""

    recent = history[-lookback:] if len(history) > lookback else history
    total_draws = len(recent)
    pair_frequency: Counter[tuple[int, int]] = Counter()
    for draw in recent:
        for a, b in combinations(sorted(draw.numbers), 2):
            pair_frequency[(a, b)] += 1
    minimum_cooccurrence = max(2, total_draws * 0.01)
    adjacency: dict[int, dict[int, float]] = {
        number: {} for number in range(_MIN_NUM, _MAX_NUM + 1)
    }
    for (a, b), pair_count in pair_frequency.items():
        if pair_count >= minimum_cooccurrence:
            weight = pair_count / total_draws
            adjacency[a][b] = weight
            adjacency[b][a] = weight
    return adjacency


def _degree_centrality(
    nodes: list[int], adjacency: dict[int, dict[int, float]]
) -> dict[int, float]:
    """Port ``networkx.degree_centrality``: ``degree(v) / (n - 1)``."""

    n = len(nodes)
    if n <= 1:
        return {node: 1.0 for node in nodes}
    scale = 1.0 / (n - 1.0)
    return {node: len(adjacency.get(node, {})) * scale for node in nodes}


def _betweenness_centrality(
    nodes: list[int], adjacency: dict[int, dict[int, float]]
) -> dict[int, float]:
    """Port ``networkx.betweenness_centrality(G, weight='weight')``: weighted
    Brandes (2001) accumulation over Dijkstra shortest paths, undirected,
    normalized, endpoints excluded (networkx's defaults) -- verified
    bit-for-bit against real networkx across 300 randomized weighted graphs
    (see the sibling test file) and against the donor's own co-occurrence
    graphs across five causal-history lengths."""

    betweenness = dict.fromkeys(nodes, 0.0)
    for source in nodes:
        stack: list[int] = []
        predecessors: dict[int, list[int]] = {node: [] for node in nodes}
        sigma = dict.fromkeys(nodes, 0.0)
        sigma[source] = 1.0
        distance: dict[int, float] = {}
        seen: dict[int, float] = {source: 0.0}
        counter = count()
        queue: list[tuple[float, int, int, int]] = []
        heapq.heappush(queue, (0.0, next(counter), source, source))
        while queue:
            current_distance, _, predecessor, node = heapq.heappop(queue)
            if node in distance:
                continue
            sigma[node] += sigma[predecessor]
            stack.append(node)
            distance[node] = current_distance
            for neighbor, weight in adjacency.get(node, {}).items():
                neighbor_distance = current_distance + weight
                if neighbor not in distance and (
                    neighbor not in seen or neighbor_distance < seen[neighbor]
                ):
                    seen[neighbor] = neighbor_distance
                    heapq.heappush(queue, (neighbor_distance, next(counter), node, neighbor))
                    sigma[neighbor] = 0.0
                    predecessors[neighbor] = [node]
                elif neighbor_distance == seen[neighbor]:
                    sigma[neighbor] += sigma[node]
                    predecessors[neighbor].append(node)
        delta = dict.fromkeys(stack, 0.0)
        while stack:
            node = stack.pop()
            coefficient = (1 + delta[node]) / sigma[node]
            for predecessor in predecessors[node]:
                delta[predecessor] += sigma[predecessor] * coefficient
            if node != source:
                betweenness[node] += delta[node]
    node_count = len(nodes)
    if node_count > 2:
        scale = 1.0 / ((node_count - 1) * (node_count - 2))
        betweenness = {node: value * scale for node, value in betweenness.items()}
    return betweenness


class BigLottoDiversifiedEnsembleV6Adapter(PortfolioBetAdapter):
    """Three tickets: Consensus (Bayesian U frequency, structurally
    validated), Synergy (weighted graph centrality), Disruptor (hot-tail,
    regime-adaptive odd-count floor). Python RNG reset to seed 42 at the
    start of every call, matching the donor's own per-call reseed."""

    strategy_id = "legacy_biglotto__biglotto_diversified_ensemble_v6__8caaac8fcb5d"
    strategy_name = "大樂透多樣化集成 V6"
    strategy_version = "v0.1"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)
    native_ticket_count = 3

    def _history_window(self, history: tuple[object, ...]) -> tuple[object, ...]:
        return history[-1000:] if len(history) > 1000 else history

    def _predict_all(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[tuple[int, ...], ...]:
        rng = random.Random(42)
        regime = _detect_regime(history)
        stats = _structural_stats(history)

        bayesian_ticket = _bayesian_desc_ticket(history)
        frequency_ticket = _v6_frequency_ticket(history)
        pool_1 = sorted(set(bayesian_ticket) | set(frequency_ticket))
        final_bet1 = tuple(sorted(pool_1[:_PICK]))
        for _attempt in range(150):
            sample = tuple(sorted(rng.sample(pool_1, _PICK)))
            if _validate_combination(sample, stats):
                final_bet1 = sample
                break

        graph_input = history[:500] if len(history) > 500 else history
        adjacency = _graph_adjacency(graph_input, lookback=500)
        nodes = list(range(_MIN_NUM, _MAX_NUM + 1))
        degree_centrality = _degree_centrality(nodes, adjacency)
        betweenness_centrality = _betweenness_centrality(nodes, adjacency)
        centrality_scores = {
            number: degree_centrality.get(number, 0.0) * 0.7
            + betweenness_centrality.get(number, 0.0) * 0.3
            for number in range(_MIN_NUM, _MAX_NUM + 1)
        }
        pool_2 = [
            number
            for number, _score in sorted(centrality_scores.items(), key=lambda item: -item[1])
        ][:20]
        final_bet2 = tuple(sorted(pool_2[:_PICK]))
        for _attempt in range(150):
            sample = tuple(sorted(rng.sample(pool_2, _PICK)))
            if _validate_combination(sample, stats):
                final_bet2 = sample
                break

        tail_frequency: Counter[int] = Counter()
        for draw in history[-100:]:
            tail_frequency.update(number % 10 for number in draw.numbers)
        hot_tails = [tail for tail, _count in tail_frequency.most_common(5)]
        target_odd_count = 5 if regime == "SKEWED" else 3
        odd_numbers = [number for number in range(1, 50) if number % 2 == 1]
        even_numbers = [number for number in range(1, 49) if number % 2 == 0]
        pool_3 = [number for number in (odd_numbers + even_numbers) if number % 10 in hot_tails]
        if len(pool_3) < 12:
            pool_3 = list(range(_MIN_NUM, _MAX_NUM + 1))
        final_bet3 = tuple(sorted(pool_3[:_PICK]))
        for _attempt in range(200):
            sample = tuple(sorted(rng.sample(pool_3, _PICK)))
            if (
                sum(1 for number in sample if number % 2 == 1) >= target_odd_count
                and _validate_combination(sample, stats)
            ):
                final_bet3 = sample
                break

        return (final_bet1, final_bet2, final_bet3)


# ─── legacy_biglotto__backtest_strategy_1__41ed79a6de62 ────────────────────
# Donor: tools/backtest_strategy_1.py::PostSelectionBacktester.run's
# per-target ticket pair (history already ASC via the donor's own get_data()).


def _danger_numbers(history: tuple[CausalDrawRow, ...]) -> set[int]:
    if len(history) < 3:
        return set()
    last = set(history[-1].numbers)
    previous_1 = set(history[-2].numbers)
    previous_2 = set(history[-3].numbers)
    return last & previous_1 & previous_2


def _frequency_50_ticket(history: tuple[CausalDrawRow, ...], danger: set[int]) -> list[int]:
    history_50 = history[-50:]
    all_numbers = [number for draw in history_50 for number in draw.numbers]
    candidates = [number for number, _count in Counter(all_numbers).most_common()]
    selected: list[int] = []
    pointer = 0
    while len(selected) < _PICK and pointer < len(candidates):
        number = candidates[pointer]
        if number not in danger:
            selected.append(number)
        pointer += 1
    return sorted(selected)


class BigLottoBacktestStrategy1Adapter(PortfolioBetAdapter):
    """Two tickets: Frequency-50 danger-filtered, then zone-balance with a
    danger-triggered 510-window retry (donor's own bare-except fallback to
    ``(1,2,3,4,5,6)`` preserved verbatim)."""

    strategy_id = "legacy_biglotto__backtest_strategy_1__41ed79a6de62"
    strategy_name = "大樂透後置殺號回測策略一"
    strategy_version = "v0.1"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)
    native_ticket_count = 2

    def _predict_all(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[tuple[int, ...], ...]:
        danger = _danger_numbers(history)
        bet1 = _frequency_50_ticket(history, danger)

        try:
            bet2 = list(_zone_balance_ticket(history[-500:]))
            if set(bet2) & danger:
                bet2 = list(_zone_balance_ticket(history[-510:]))
        except Exception:
            bet2 = [1, 2, 3, 4, 5, 6]
        bet2 = sorted(bet2)

        return (_ticket(bet1), _ticket(bet2))


__all__ = [
    "BigLottoBacktestStrategy1Adapter",
    "BigLottoDiversifiedEnsembleV6Adapter",
    "BigLottoEnhancedDualBetAdapter",
]
