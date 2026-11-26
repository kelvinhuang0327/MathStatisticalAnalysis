"""Native EH02 conditional TE ticket producer. No historical replay is implied."""

from __future__ import annotations

import numpy as np

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import CausalDrawRow, PortfolioBetAdapter

IMPLEMENTATION_IDENTITY = "conditional_te_native_adapter_v1"


def joint_counts(window):
    """Dense code histogram, independent from the auditor's integer bitsets."""
    prev, nxt = np.asarray(window[:-1], dtype=np.int64), np.asarray(window[1:], dtype=np.int64)
    assert len(prev) == 749
    m = prev.shape[1]
    code = 4 * prev[:, :, None] + 2 * prev[:, None, :] + nxt[:, None, :]
    offsets = 8 * np.arange(m * m).reshape(m, m)
    return np.bincount((code + offsets).ravel(), minlength=m * m * 8).reshape(m, m, 2, 2, 2)


def own_counts(window):
    prev, nxt = window[:-1], window[1:]
    m = prev.shape[1]
    code = np.arange(m)[None, :] * 4 + prev * 2 + nxt
    return np.bincount(code.ravel(), minlength=m * 4).reshape(m, 2, 2)


def smoothed_information(counts):
    """The fixed eight-cell distribution and its two consistent marginals."""
    assert np.issubdtype(counts.dtype, np.integer) and np.all(counts >= 0)
    assert np.all(counts.sum(axis=(2, 3, 4)) == 749)
    joint = (counts + 0.5) / 753.0
    px = (counts + 0.5) / (counts.sum(axis=4, keepdims=True) + 1.0)
    marginal = (counts.sum(axis=2) + 1.0) / (counts.sum(axis=(2, 4))[:, :, :, None] + 2.0)
    assert np.allclose(joint.sum(axis=(2, 3, 4)), 1, rtol=0, atol=5e-16)
    assert np.allclose(px.sum(axis=4), 1, rtol=0, atol=3e-16)
    assert np.allclose(marginal.sum(axis=3), 1, rtol=0, atol=3e-16)
    raw_te = np.sum(joint * np.log(px / marginal[:, :, None, :, :]), axis=(2, 3, 4))
    return joint, px, marginal, raw_te


def conditional_model(counts, self_counts, current, frequency):
    """Single fixed smoothed joint distribution; natural log, no TE search."""
    n = len(current)
    off = ~np.eye(n, dtype=bool)
    assert np.all(counts.sum(axis=2) == self_counts[None, :, :, :])
    _joint, px, _marginal, raw_te = smoothed_information(counts)
    assert float(raw_te[off].min()) >= -1e-12, "SIGNIFICANT_NEGATIVE_TE_STOP"
    te = np.maximum(raw_te, 0.0)
    te[~off] = 0.0
    weight = te / (te + 0.01)
    assert np.all((weight >= 0) & (weight <= 1))
    pself = (self_counts[:, :, 1] + 1) / (self_counts.sum(axis=2) + 2)
    own = pself[np.arange(n), current]
    assert np.all((own > 0) & (own < 1))
    pc = np.take_along_axis(
        px[:, :, 1, :, 1], np.broadcast_to(current[None, :, None], (n, n, 1)), axis=2
    )[:, :, 0]
    residual = pc - own[None, :]
    latest = np.flatnonzero(current)
    assert len(latest) == 6
    signal = (weight * residual)[latest].sum(axis=0) / 6.0
    main = own + signal
    freq = (frequency + 100 * (6 / 49)) / 850
    assert np.isfinite(main).all() and np.all((main > 0) & (main < 1))
    # Main is a convex mixture of own and conditional Bernoulli scores; no clipping.
    return (
        {"MAIN": main, "MARKOV_CONTROL": own, "FREQ_CONTROL": freq},
        te,
        weight,
        residual,
        signal,
        raw_te,
    )


def score_history(y, t):
    w = y[t - 750 : t]
    c = joint_counts(w)
    s = own_counts(w)
    return c, s, conditional_model(c, s, w[-1], w.sum(axis=0))


def tickets_from_score(score, k):
    rank = sorted(range(1, 50), key=lambda n: (-float(score[n - 1]), n))
    return [sorted(rank[i : i + 6]) for i in range(0, 6 * k, 6)]


class _ConditionalTEAdapter(PortfolioBetAdapter):
    strategy_name = "Conditional transfer entropy"
    strategy_version = "EH02_V1"
    implementation_identity = IMPLEMENTATION_IDENTITY
    min_history = 750
    supported_lottery_types = (LotteryType.BIG_LOTTO,)

    def _history_window(self, history: tuple[object, ...]) -> tuple[object, ...]:
        return history[-750:]

    def _predict_all(
        self, history: tuple[CausalDrawRow, ...], lottery_type: LotteryType
    ) -> tuple[tuple[int, ...], ...]:
        window = np.zeros((750, 49), dtype=np.int64)
        for index, row in enumerate(history):
            window[index, np.asarray(row.numbers, dtype=np.int64) - 1] = 1
        _, _, model = score_history(window, 750)
        return tuple(
            tuple(ticket)
            for ticket in tickets_from_score(model[0]["MAIN"], self.native_ticket_count)
        )


class BigLottoConditionalTEK2Adapter(_ConditionalTEAdapter):
    strategy_id = "research_conditional_transfer_entropy_k2"
    native_ticket_count = 2


class BigLottoConditionalTEK3Adapter(_ConditionalTEAdapter):
    strategy_id = "research_conditional_transfer_entropy_k3"
    native_ticket_count = 3


class BigLottoConditionalTEK5Adapter(_ConditionalTEAdapter):
    strategy_id = "research_conditional_transfer_entropy_k5"
    native_ticket_count = 5
