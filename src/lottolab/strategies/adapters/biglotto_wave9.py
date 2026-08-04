"""BigLotto native-strategy wave 9: thin ports of frozen legacy BACKTESTED
``tools/test_cag.py`` / ``tools/test_cluster_cover.py`` / ``tools/test_zdp.py``
(donor commit ``49a25effa62fc24f40789c16be6f11bdfb41a4a9``, the same frozen
snapshot as waves 1-8). No algorithm was changed, tuned, or "improved"
during the port.

All three donor classes subclass ``lottery_api/models/biglotto_3bet_optimizer.py::
BigLotto3BetOptimizer`` and, like wave 4's already-shipped
``BigLottoThreeBetOptimizerAdapter``, start from its
``predict_3bets_diversified(use_kill=True)`` top-18 candidate pool: P1
dynamic kill-number exclusion (count=10) then three ``UnifiedPredictionEngine``
methods (deviation 2.0, markov 1.5, statistical 1.0) into a weighted
``Counter``, top-18 slice. ``_diversified_top18`` below reproduces that exact
pool (byte-identical to wave 4's own inlined computation -- re-derived here,
not imported, only because wave 4 does not expose it as a standalone
function; the weights/count/slice-size are unchanged from the already-judged
wave 4 port). CAG and Cluster-Cover both build a co-occurrence matrix over
the trailing 200 draws from that same pool. All three engine tickets
(``_unified_deviation_ticket`` / ``_unified_markov_ticket`` /
``_unified_statistical_ticket``) and ``_kill_numbers`` are byte-identical
reuse of waves 3-4's already-verified ports (sibling modules in the same
``strategies.adapters`` package -- not a layer violation, see
``tests/architecture/test_dependency_rules.py``); byte-identical reuse is
strictly stronger evidence of parity than a second independent
transcription. Per wave 3's own documented reasoning, the donor's
``markov_predict`` newest-first reversal guard is not ported: ``CausalDrawRow``
history is always oldest-first under this framework's contract, so the
branch is provably unreachable here.

* ``CAGOptimizer.predict_3bets_cag`` -- three bets, one per Top-3 anchor
  (``top_18[:3]``), each anchor plus its five highest co-occurrence
  companions from the full 18-candidate pool (``set(top_18)`` minus the
  anchor itself), ranked by ``(co_score, -top_18.index(candidate))``
  descending. That sort key is unique per candidate (each candidate has a
  distinct index in the duplicate-free ``top_18`` list), so the
  pre-sort traversal order of the donor's ``pool`` set never affects the
  final ranking; the set itself is still used here, matching the donor bit
  for bit. The donor's own ``companions[i][0]`` access for ``i in range(5)``
  is not defensively bounds-checked: when the candidate pool is too small
  (fewer than 6 usable numbers in ``top_18``) this raises ``IndexError``
  exactly as the donor script would -- a genuine, rare closure (the frozen
  ledger records exactly 1 across 2148 causal executions), not a bug to
  "fix" with an invented fallback.
* ``ClusterCoverOptimizer.predict_3bets_cluster_cover`` -- three bets seeded
  by the same three anchors, round-robin filled five more numbers each from
  the remaining 15 candidates by highest co-occurrence sum with each bet's
  current members so far; ties are broken by ``set`` iteration order
  (CPython's hash-based order for small ints is deterministic and
  reproducible -- no ``PYTHONHASHSEED`` sensitivity, unlike str/bytes
  hashing). The donor's own ``for b_idx in range(3): if not available: break``
  only exits the inner loop, not the outer ``for _ in range(5)`` -- ported
  as the literal nested-loop structure rather than "fixed" into a single
  early exit; both forms produce identical output (once ``available`` is
  empty every remaining inner iteration is already a no-op), but the
  literal structure keeps this port directly traceable to the donor source.
  When ``top_18`` has fewer than 18 candidates, one or more bets end up
  short of 6 numbers -- a genuine donor-faithful closure (128 of 2149
  recorded causal executions), surfaced here by ``_ticket``'s own exact-6
  validation rather than an invented pad/dedup.
* ``ZDPOptimizer.predict_3bets_zdp`` -- an independent top-30 pool (deviation
  1.5, markov 1.5, statistical 2.0, same ``count=10`` kill exclusion) split
  into three 16/16/17-wide numeric zones (1-16/17-32/33-49), then one bet
  per zone-heavy configuration: up to 4 numbers from the heavy zone, filled
  from the other two zones in pool order, with a fixed-seed(42) random
  fallback (``random.randint(1, 49)``, stdlib global ``random``, reseeded to
  42 immediately before each of the three bets -- never accumulated across
  bets) for any slots still unfilled. The donor's own ``predict_3bets_diversified``
  call at the top of this method is not ported: its result (``res``) is
  never read afterward, and every side effect it triggers (P1 kill-number
  computation, three engine calls) is either pure/re-computed independently
  by this method's own candidate collection or -- for ``statistical_predict``'s
  internal ``random.seed(len(history))`` -- always overwritten before use by
  this method's own ``random.seed(42)``, which runs before every
  ``random.randint`` call in every zone; the call is therefore provably
  side-effect-free on ``numbers`` and correctly omitted, not "improved
  away" (same standard wave 4 applied to donor fields that feed nothing --
  see that module's docstring). The random fallback never checks for
  duplicates against numbers already in the bet, so a bet can end up with
  fewer than 6 distinct numbers -- another genuine donor-faithful closure,
  surfaced by ``_ticket``.
"""

# pyright: reportPrivateUsage=false
# (intentional reuse of wave 3/4's already-verified private ticket/kill
# helpers -- see module docstring; waves 3-4 are not modified)

from __future__ import annotations

import random
from collections import Counter, defaultdict
from itertools import combinations
from typing import cast

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import CausalDrawRow, PortfolioBetAdapter
from lottolab.strategies.adapters.biglotto_wave3 import (
    _ticket,
    _unified_deviation_ticket,
    _unified_markov_ticket,
    _unified_statistical_ticket,
)
from lottolab.strategies.adapters.biglotto_wave4 import _kill_numbers

_MIN_NUM = 1
_MAX_NUM = 49
_COOCCURRENCE_WINDOW = 200


def _diversified_top18(history: tuple[CausalDrawRow, ...]) -> list[int]:
    """Reproduce ``BigLotto3BetOptimizer.predict_3bets_diversified``'s
    top-18 candidate pool (see module docstring)."""

    kill_numbers = _kill_numbers(history, count=10)
    deviation = _unified_deviation_ticket(history)
    markov = _unified_markov_ticket(history)
    statistical = _unified_statistical_ticket(history)
    candidates: Counter[int] = Counter()
    for ticket, weight in ((deviation, 2.0), (markov, 1.5), (statistical, 1.0)):
        for number in ticket:
            candidates[number] += cast(int, weight)
    for number in kill_numbers:
        candidates[number] = -9999
    return [number for number, _score in candidates.most_common(18)]


def _cooccurrence_matrix(
    history: tuple[CausalDrawRow, ...],
) -> defaultdict[int, Counter[int]]:
    """Port the CAG/Cluster-Cover co-occurrence matrix over the trailing
    200 draws (``CausalDrawRow.numbers`` is already ascending, matching the
    donor's own ``sorted(nums)`` before pairing)."""

    matrix: defaultdict[int, Counter[int]] = defaultdict(Counter)
    for draw in history[-_COOCCURRENCE_WINDOW:]:
        for a, b in combinations(draw.numbers, 2):
            matrix[a][b] += 1
            matrix[b][a] += 1
    return matrix


# ─── legacy_biglotto__test_cag__7ca5343dfedd ───────────────────────────────
# Donor: tools/test_cag.py -- CAGOptimizer.predict_3bets_cag(use_kill=True,
# the donor's own default). Top-18 diversified pool, 3 anchors, each anchor
# plus 5 co-occurrence-ranked companions from the full pool.


class BigLottoCagAdapter(PortfolioBetAdapter):
    """Three co-occurrence-anchor-grouped tickets: one per Top-3 anchor,
    each paired with its five highest co-occurrence companions."""

    strategy_id = "legacy_biglotto__test_cag__7ca5343dfedd"
    strategy_name = "大樂透 CAG 共現錨點分組三注"
    strategy_version = "v0.1"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)
    native_ticket_count = 3

    def _predict_all(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[tuple[int, ...], ...]:
        top_18 = _diversified_top18(history)
        matrix = _cooccurrence_matrix(history)
        anchors = top_18[:3]
        pool = set(top_18)
        bets: list[tuple[int, ...]] = []
        for anchor in anchors:
            companions: list[tuple[int, int]] = []
            for candidate in pool:
                if candidate == anchor:
                    continue
                companions.append((candidate, matrix[anchor][candidate]))
            companions.sort(key=lambda entry: (entry[1], -top_18.index(entry[0])), reverse=True)
            bet = [anchor]
            for index in range(5):
                bet.append(companions[index][0])
            bets.append(_ticket(bet))
        return tuple(bets)


# ─── legacy_biglotto__test_cluster_cover__5b43959e7c55 ─────────────────────
# Donor: tools/test_cluster_cover.py --
# ClusterCoverOptimizer.predict_3bets_cluster_cover(use_kill=True, the
# donor's own default). Top-18 diversified pool, 3 anchors, round-robin
# co-occurrence fill from the remaining 15 candidates.


class BigLottoClusterCoverAdapter(PortfolioBetAdapter):
    """Three co-occurrence-cluster tickets: three anchors round-robin
    filled by highest co-occurrence sum with each bet's own members."""

    strategy_id = "legacy_biglotto__test_cluster_cover__5b43959e7c55"
    strategy_name = "大樂透 Cluster-Cover 共現分群三注"
    strategy_version = "v0.1"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)
    native_ticket_count = 3

    def _predict_all(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[tuple[int, ...], ...]:
        top_18 = _diversified_top18(history)
        matrix = _cooccurrence_matrix(history)
        anchors = top_18[:3]
        remaining = top_18[3:]
        bets: list[list[int]] = [[anchor] for anchor in anchors]
        available = set(remaining)
        for _pass in range(5):
            for bet_index in range(3):
                if not available:
                    break
                best_candidate: int | None = None
                max_score = -1
                for candidate in available:
                    score = sum(matrix[candidate][member] for member in bets[bet_index])
                    if score > max_score:
                        max_score = score
                        best_candidate = candidate
                if best_candidate is not None:
                    bets[bet_index].append(best_candidate)
                    available.remove(best_candidate)
        return tuple(_ticket(sorted(bet)) for bet in bets)


# ─── legacy_biglotto__test_zdp__e80cc7e95453 ───────────────────────────────
# Donor: tools/test_zdp.py -- ZDPOptimizer.predict_3bets_zdp(use_kill=True,
# the donor's own default). Independent top-30 pool split into three
# numeric zones (1-16/17-32/33-49), one bet per heavy-zone configuration
# with a fixed-seed(42) random fallback.


class BigLottoZdpAdapter(PortfolioBetAdapter):
    """Three zonal-density-protection tickets: one per heavy-zone
    configuration (low/mid/high), fixed-seed(42) random fallback."""

    strategy_id = "legacy_biglotto__test_zdp__e80cc7e95453"
    strategy_name = "大樂透 ZDP 區域密度保護三注"
    strategy_version = "v0.1"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)
    native_ticket_count = 3

    def _predict_all(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[tuple[int, ...], ...]:
        kill_numbers = _kill_numbers(history, count=10)
        deviation = _unified_deviation_ticket(history)
        markov = _unified_markov_ticket(history)
        statistical = _unified_statistical_ticket(history)
        candidates: Counter[int] = Counter()
        for ticket, weight in ((deviation, 1.5), (markov, 1.5), (statistical, 2.0)):
            for number in ticket:
                candidates[number] += cast(int, weight)
        for number in kill_numbers:
            candidates[number] = -9999
        top_30 = [number for number, _score in candidates.most_common(30)]

        zone_low = [number for number in top_30 if 1 <= number <= 16]
        zone_mid = [number for number in top_30 if 17 <= number <= 32]
        zone_high = [number for number in top_30 if 33 <= number <= 49]
        configs = (
            (zone_low, zone_mid + zone_high),
            (zone_mid, zone_low + zone_high),
            (zone_high, zone_low + zone_mid),
        )

        bets: list[tuple[int, ...]] = []
        for heavy, others in configs:
            random.seed(42)
            bet: list[int] = list(heavy[:4]) if len(heavy) >= 4 else list(heavy)
            index = 0
            while len(bet) < 6 and index < len(others):
                if others[index] not in bet:
                    bet.append(others[index])
                index += 1
            while len(bet) < 6:
                bet.append(random.randint(_MIN_NUM, _MAX_NUM))
            bets.append(_ticket(sorted(bet)))
        return tuple(bets)


__all__ = [
    "BigLottoCagAdapter",
    "BigLottoClusterCoverAdapter",
    "BigLottoZdpAdapter",
]
