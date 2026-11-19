"""Causal, reproducible v0.2 of the frontend auto optimizer.

The v0.1 donor-parity adapter remains available for historical reproduction.
This version validates each candidate on strictly earlier prefixes and gives
each candidate/validation target its own deterministic, history-only stream.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
from functools import cmp_to_key

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import BetAdapter, CausalDrawRow, RejectPrediction
from lottolab.strategies.adapters.biglotto_frontend_auto_optimize import (
    _CANDIDATE_ORDER,
    _MAX_DATA_SIZE,
    _MIN_HISTORY,
    BigLottoFrontendAutoOptimizeAdapter,
    _CandidateScore,
    _compare_scores,
)

_SEED_CONTRACT = "biglotto-auto-optimize-causal-v0.2-sha256-v1"


def _seed_for_candidate(strategy: str, history: tuple[CausalDrawRow, ...]) -> int:
    """Derive a local seed from the candidate and only the available prefix."""
    payload = {
        "contract": _SEED_CONTRACT,
        "candidate": strategy,
        "history": [[row.draw, row.date, list(row.numbers)] for row in history],
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return int.from_bytes(hashlib.sha256(raw.encode("utf-8")).digest(), "big")


class BigLottoFrontendAutoOptimizeCausalAdapter(BetAdapter):
    """Evaluate an oldest-first holdout without future information."""

    strategy_id = BigLottoFrontendAutoOptimizeAdapter.strategy_id
    strategy_name = BigLottoFrontendAutoOptimizeAdapter.strategy_name
    strategy_version = "v0.2"
    min_history = _MIN_HISTORY
    supported_lottery_types = (LotteryType.BIG_LOTTO,)

    def _history_window(self, history: tuple[object, ...]) -> tuple[object, ...]:
        return history[-_MAX_DATA_SIZE:]

    def _candidate_prediction(
        self, name: str, history: tuple[CausalDrawRow, ...]
    ) -> tuple[int, ...]:
        seed = _seed_for_candidate(name, history)
        isolated = BigLottoFrontendAutoOptimizeAdapter(random.Random(seed))
        # Each call gets a new adapter and statistics context; other candidates
        # and later validation periods cannot affect this input or RNG stream.
        return isolated._predict_candidate(name, history)

    def _scores(self, history: tuple[CausalDrawRow, ...]) -> tuple[_CandidateScore, ...]:
        test_size = min(10, math.floor(len(history) * 0.2))
        start = len(history) - test_size
        scores: list[_CandidateScore] = []
        for name in _CANDIDATE_ORDER:
            success = 0
            total_hits = 0
            for index in range(start, len(history)):
                try:
                    predicted = self._candidate_prediction(name, history[:index])
                    if (
                        len(predicted) != 6
                        or len(set(predicted)) != 6
                        or any(type(n) is not int or not 1 <= n <= 49 for n in predicted)
                    ):
                        raise ValueError("candidate emitted an invalid ticket")
                except Exception:
                    # A failed validation period has unknown outcome. Exclude
                    # the whole candidate instead of counting it as a loss.
                    break
                hits = len(set(predicted).intersection(history[index].numbers))
                success += int(hits >= 3)
                total_hits += hits
            else:
                scores.append(
                    _CandidateScore(name, success / test_size, total_hits / test_size, test_size)
                )
        return tuple(scores)

    def _predict(
        self, history: tuple[CausalDrawRow, ...], lottery_type: LotteryType
    ) -> tuple[int, ...]:
        del lottery_type
        scores = self._scores(history)
        if not scores:
            raise RejectPrediction(f"{self.strategy_id}: no fully evaluated candidate")
        for score in sorted(scores, key=cmp_to_key(_compare_scores)):
            try:
                return self._candidate_prediction(score.strategy, history)
            except Exception:
                continue
        raise RejectPrediction(f"{self.strategy_id}: no candidate could generate a final ticket")
