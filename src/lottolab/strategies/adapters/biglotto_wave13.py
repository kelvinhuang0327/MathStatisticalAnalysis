"""BigLotto native-strategy wave 13: thin ports of three frozen legacy
BACKTESTED methods (donor commit ``49a25effa62fc24f40789c16be6f11bdfb41a4a9``,
the same frozen snapshot as waves 1-12). No algorithm was changed, tuned, or
"improved" during the port.

All three donor files below are further thin coverage-optimization wrappers
around ``lottery_api/models/biglotto_3bet_optimizer.py::BigLotto3BetOptimizer``
(itself already ported as ``BigLottoThreeBetOptimizerAdapter`` in
``biglotto_wave4.py``), which is in turn a wrapper around the donor's shared
``UnifiedPredictionEngine``/``NegativeSelector`` methods wave 3 and wave 4
already ported and tested. Rather than re-derive and re-verify those five
functions a third time, this module imports wave 3's and wave 4's
already-tested ports directly (``_unified_deviation_ticket`` /
``_unified_markov_ticket`` / ``_unified_statistical_ticket`` /
``_unified_hot_cold_mix_ticket`` / ``_kill_numbers`` / ``_ticket``) --
``lottolab.strategies.adapters.biglotto_wave3``/``biglotto_wave4`` are sibling
modules in the same ``strategies.adapters`` package, so this is not a layer
violation (see ``tests/architecture/test_dependency_rules.py``); byte-identical
reuse is strictly stronger evidence of parity than a fourth independent
transcription would be.

* ``legacy_biglotto__test_asm__d39a233a4c75`` -- donor ``tools/test_asm.py``,
  ``ASMOptimizer.predict_3bets_asm``. Calls the donor's own
  ``predict_3bets_diversified(use_kill=True)`` (byte-identical to
  ``BigLottoThreeBetOptimizerAdapter``'s own top-18 candidate pool: P1 kill
  exclusion count=10, deviation 2.0 + markov 1.5 + statistical 1.0 weighted
  ``Counter``, top-18 by ``most_common``) to get its ``candidates`` field,
  then -- instead of ``BigLotto3BetOptimizer``'s own fixed
  ``(0,6)/(4,10)/(8,14)`` slices -- re-maps three fixed index sets onto that
  same top-18 list: ``[0,1,2,3,4,5]``, ``[0,1,6,7,8,9]``,
  ``[2,3,4,10,11,12]``. Three tickets. The donor indexes (not slices) into
  the candidate list, so a causal history whose weighted pool has fewer than
  13 distinct candidates after kill-filtering raises a native ``IndexError``
  in the original source; reproduced here as an explicit frozen closure
  (never an invented pad) via ``Wave13FrozenSourceError``.
* ``legacy_biglotto__test_dcb__c3299c25ca59`` -- donor ``tools/test_dcb.py``,
  ``DCBOptimizer.predict_3bets_dcb``. Its own weighted candidate pool
  (deviation 1.5, markov 1.5, statistical 2.0, hot_cold_mix 1.0), the same P1
  kill exclusion (count=10, via the same ``self.selector`` the base class
  constructs), then a *correlation boost* pass: a number/number co-occurrence
  ``Counter`` built from the trailing 200 causal draws, and the top-5
  (post-kill) candidates each donate ``base_score * 0.1 * (co_occurrence /
  10)`` to every co-occurring candidate still present with positive weight in
  the pool. Top-18 of the boosted pool, then the *same* fixed
  ``(0,6)/(4,10)/(8,14)`` slices ``BigLotto3BetOptimizer._generate_bets``
  uses (``DCBOptimizer`` never overrides it). Three tickets; a short boosted
  pool closes the same way wave 4's ``BigLottoThreeBetOptimizerAdapter``
  already does, via the shared ``_ticket`` helper's own
  ``FROZEN_UNIFIED_INVALID_TICKET`` (a slice, not an index -- no separate
  closure type needed here).
* ``legacy_biglotto__test_4bet_dcb__3c7e3e661ad8`` -- donor
  ``tools/test_4bet_dcb.py``, ``DCB4BetOptimizer.predict_4bets_dcb``. Calls
  the donor's own ``predict_3bets_dcb`` (byte-identical to the DCB port
  above) to get its ``candidates`` (the same correlation-boosted top-18),
  then re-slices it into four positional, overlapping 6-number windows:
  ``(0,6)/(4,10)/(8,14)/(12,18)``. Four tickets; same slice-based closure
  path as DCB.

Donor parity for all three was independently re-derived by reading
``tools/test_asm.py`` / ``tools/test_dcb.py`` / ``tools/test_4bet_dcb.py`` /
``lottery_api/models/biglotto_3bet_optimizer.py`` at the frozen commit (no
numpy/pandas/scipy/sklearn is installed in this environment to execute the
donor classes directly) and cross-checked against the separately-verified,
already-tested pure-Python research port of the same three methods at
``lottolab.application.legacy_source_native_portfolios_wave24`` (backed by
``lottolab.application.legacy_frozen_unified_core``; 2148/2148/2134 causal
executions recorded against the same frozen commit per
``strategies/data/biglotto_full_strategy_catalog_v1.json``); this module's
own test goldens were computed from that already-verified reference.

None of the three donor files construct their own ``NegativeSelector`` or
``UnifiedPredictionEngine`` -- ``ASMOptimizer``/``DCBOptimizer`` subclass
``BigLotto3BetOptimizer`` and only ever call inherited/overridden methods, so
``self.engine``/``self.selector`` resolve to the exact same instances (and
therefore the exact same frozen algorithms) wave 3/wave 4 already ported.
``DCB4BetOptimizer`` subclasses ``DCBOptimizer`` and only adds its own
slicing on top of the inherited ``predict_3bets_dcb``.
"""

# pyright: reportPrivateUsage=false
# (intentional reuse of wave 3's/wave 4's already-verified private ticket/
# kill-number helpers -- see module docstring; wave 3/wave 4 are not modified)

from __future__ import annotations

from collections import Counter, defaultdict
from itertools import combinations
from typing import cast

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import (
    CausalDrawRow,
    PortfolioBetAdapter,
)
from lottolab.strategies.adapters.biglotto_wave3 import (
    _ticket,
    _unified_deviation_ticket,
    _unified_markov_ticket,
    _unified_statistical_ticket,
)
from lottolab.strategies.adapters.biglotto_wave4 import (
    _kill_numbers,
    _unified_hot_cold_mix_ticket,
)


class Wave13FrozenSourceError(ValueError):
    """A frozen wave-13 donor deterministically closes for this causal history."""

    def __init__(self, reason_code: str) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code


def _base_top18(history: tuple[CausalDrawRow, ...]) -> list[int]:
    """Port ``BigLotto3BetOptimizer.predict_3bets_diversified``'s candidate
    pool (``use_kill=True``, the donor's own default): the exact top-18
    computation ``BigLottoThreeBetOptimizerAdapter`` already builds."""

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


def _dcb_top18(history: tuple[CausalDrawRow, ...]) -> list[int]:
    """Port ``DCBOptimizer.predict_3bets_dcb``'s correlation-boosted
    candidate pool (``use_kill=True``, the donor's own default)."""

    kill_numbers = _kill_numbers(history, count=10)
    deviation = _unified_deviation_ticket(history)
    markov = _unified_markov_ticket(history)
    statistical = _unified_statistical_ticket(history)
    hot_cold = _unified_hot_cold_mix_ticket(history)
    candidates: Counter[int] = Counter()
    for ticket, weight in (
        (deviation, 1.5),
        (markov, 1.5),
        (statistical, 2.0),
        (hot_cold, 1.0),
    ):
        for number in ticket:
            candidates[number] += cast(int, weight)
    for number in kill_numbers:
        candidates[number] = -9999

    matrix: defaultdict[int, Counter[int]] = defaultdict(Counter)
    for draw in history[-200:]:
        for left, right in combinations(sorted(draw.numbers), 2):
            matrix[left][right] += 1
            matrix[right][left] += 1

    top_five = [number for number, _score in candidates.most_common(5)]
    boosted_candidates = Counter(candidates)
    for anchor in top_five:
        base_score = candidates[anchor]
        for neighbor, cooccurrence_count in matrix[anchor].items():
            if neighbor in boosted_candidates and boosted_candidates[neighbor] > 0:
                boosted_candidates[neighbor] += cast(
                    int, base_score * 0.1 * (cooccurrence_count / 10)
                )
    return [number for number, _score in boosted_candidates.most_common(18)]


# ─── legacy_biglotto__test_asm__d39a233a4c75 ───────────────────────────────

_ASM_INDEX_MAPS = (
    (0, 1, 2, 3, 4, 5),
    (0, 1, 6, 7, 8, 9),
    (2, 3, 4, 10, 11, 12),
)


class BigLottoTestAsmAdapter(PortfolioBetAdapter):
    """Anchor-Secondary Mixed: three fixed index-maps onto the base 3-bet
    optimizer's own top-18 candidate pool -- a 3-native-ticket portfolio."""

    strategy_id = "legacy_biglotto__test_asm__d39a233a4c75"
    strategy_name = "大樂透 ASM 錨點次選混合預測器"
    strategy_version = "v0.1"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)
    native_ticket_count = 3

    def _predict_all(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[tuple[int, ...], ...]:
        top_18 = _base_top18(history)
        try:
            rows = [[top_18[index] for index in indexes] for indexes in _ASM_INDEX_MAPS]
        except IndexError as exc:
            raise Wave13FrozenSourceError(
                "FROZEN_SOURCE_CANDIDATE_INDEX_OUT_OF_RANGE"
            ) from exc
        return tuple(_ticket(row) for row in rows)


# ─── legacy_biglotto__test_dcb__c3299c25ca59 ───────────────────────────────

_DCB_SLICES = ((0, 6), (4, 10), (8, 14))


class BigLottoTestDcbAdapter(PortfolioBetAdapter):
    """Dynamic Correlation Boosting: co-occurrence-boosted top-18 candidate
    pool sliced into three overlapping 6-number tickets -- a 3-native-ticket
    portfolio."""

    strategy_id = "legacy_biglotto__test_dcb__c3299c25ca59"
    strategy_name = "大樂透 DCB 動態關聯增強預測器"
    strategy_version = "v0.1"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)
    native_ticket_count = 3

    def _predict_all(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[tuple[int, ...], ...]:
        top_18 = _dcb_top18(history)
        return tuple(_ticket(top_18[start:end]) for start, end in _DCB_SLICES)


# ─── legacy_biglotto__test_4bet_dcb__3c7e3e661ad8 ──────────────────────────

_FOUR_BET_DCB_SLICES = ((0, 6), (4, 10), (8, 14), (12, 18))


class BigLottoTestFourBetDcbAdapter(PortfolioBetAdapter):
    """4-Bet DCB (full pool coverage): the same correlation-boosted top-18
    pool as DCB, sliced into four overlapping 6-number tickets -- a
    4-native-ticket portfolio."""

    strategy_id = "legacy_biglotto__test_4bet_dcb__3c7e3e661ad8"
    strategy_name = "大樂透 4注 DCB 全池覆蓋預測器"
    strategy_version = "v0.1"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)
    native_ticket_count = 4

    def _predict_all(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[tuple[int, ...], ...]:
        top_18 = _dcb_top18(history)
        return tuple(_ticket(top_18[start:end]) for start, end in _FOUR_BET_DCB_SLICES)


__all__ = [
    "BigLottoTestAsmAdapter",
    "BigLottoTestDcbAdapter",
    "BigLottoTestFourBetDcbAdapter",
    "Wave13FrozenSourceError",
]
