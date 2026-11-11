"""Observable dispatcher contracts and the actual fixed-portfolio consumer."""

from __future__ import annotations

import inspect
from unittest.mock import patch

import numpy as np
import pytest

from lottolab.application.b649_sealed_geometry_portfolio import SEALED_GEOMETRY_PORTFOLIOS
from lottolab.research import b649_official_any_prize_engine as engine
from lottolab.research import b649_official_any_prize_exact as exact
from lottolab.research.b649_k10_min_overlap_exhaustive_r1 import score_portfolio

TICKET = (1, 2, 3, 4, 5, 6)


def test_original_signature_and_defaults() -> None:
    signature = inspect.signature(exact.evaluate_portfolio)
    assert list(signature.parameters) == [
        "portfolio",
        "pool_size",
        "draw_size",
        "outright_matches",
        "draws",
        "chunk_size",
    ]
    assert [p.default for p in list(signature.parameters.values())[1:]] == [49, 6, 3, None, 1 << 21]


def test_reference_never_calls_dp_or_dispatcher() -> None:
    with (
        patch.object(engine, "count_loss_polynomial", side_effect=AssertionError),
        patch.object(engine, "evaluate_portfolio_with_diagnostics", side_effect=AssertionError),
    ):
        result = engine.evaluate_portfolio_reference((TICKET,), pool_size=12)
    assert result.main_draw_count == 924


def test_explicit_dp_never_calls_reference() -> None:
    with patch.object(engine, "evaluate_portfolio_reference", side_effect=AssertionError):
        observed = engine.evaluate_portfolio_with_diagnostics((TICKET,), pool_size=12, engine="dp")
    assert observed.diagnostics.actual_engine == "dp"


@pytest.mark.parametrize("mode", ["draws", "chunk", "generic", "enumeration", "pool6"])
def test_reference_dispatch_bypasses_dp(mode: str) -> None:
    with (
        patch.object(engine, "count_loss_polynomial", side_effect=AssertionError),
        patch.object(
            engine, "evaluate_portfolio_reference", wraps=engine.evaluate_portfolio_reference
        ) as reference,
    ):
        if mode == "draws":
            result = engine.evaluate_portfolio_with_diagnostics(
                (TICKET,), pool_size=12, draws=engine.all_main_draw_masks(12, 6)
            )
        elif mode == "chunk":
            result = engine.evaluate_portfolio_with_diagnostics(
                (TICKET,), pool_size=12, chunk_size=7
            )
        elif mode == "generic":
            result = engine.evaluate_portfolio_with_diagnostics(
                ((1, 2, 3),), pool_size=9, draw_size=3, outright_matches=2
            )
        elif mode == "pool6":
            result = engine.evaluate_portfolio_with_diagnostics((TICKET,), pool_size=6)
        else:
            result = engine.evaluate_portfolio_with_diagnostics(
                (TICKET,), pool_size=12, engine="enumeration"
            )
    assert result.diagnostics.actual_engine == "enumeration"
    assert result.diagnostics.dp_states == 0
    assert reference.call_count == 1


@pytest.mark.parametrize(
    "kwargs",
    [
        {"pool_size": 12, "chunk_size": 7},
        {"pool_size": 12, "draws": np.zeros(924, dtype=np.uint64)},
        {"pool_size": 6},
    ],
)
def test_explicit_unsupported_never_falls_back(kwargs: dict[str, object]) -> None:
    with (
        patch.object(engine, "evaluate_portfolio_reference", side_effect=AssertionError),
        pytest.raises(engine.UnsupportedDP),
    ):
        engine.evaluate_portfolio_with_diagnostics((TICKET,), engine="dp", **kwargs)  # type: ignore[arg-type]


@pytest.mark.parametrize("engine_name", ["auto", "dp", "enumeration"])
@pytest.mark.parametrize(
    "ticket", [(), (1, 2, 3, 4, 5, 5), (1, 2, 3, 4, 5, 13), (True, 2, 3, 4, 5, 6)]
)
def test_all_routes_reject_illegal_tickets(
    engine_name: engine.Engine, ticket: tuple[int, ...]
) -> None:
    with pytest.raises(ValueError):
        engine.evaluate_portfolio_with_diagnostics((ticket,), pool_size=12, engine=engine_name)


def test_other_invalid_requests_and_draw_space() -> None:
    with pytest.raises(ValueError):
        engine.evaluate_portfolio_with_diagnostics((TICKET,), engine="invalid")  # type: ignore[arg-type]
    for chunk in (0, -1):
        with pytest.raises(ValueError):
            engine.evaluate_portfolio((TICKET,), pool_size=12, chunk_size=chunk)
    with pytest.raises(ValueError):
        engine.evaluate_portfolio((TICKET,), pool_size=12, outright_matches=0)
    with pytest.raises(ValueError):
        engine.evaluate_portfolio((TICKET,), pool_size=12, draws=np.zeros(1, dtype=np.uint64))


@pytest.mark.parametrize(
    "size,m3,official",
    [
        (5, 1299120, 91979160),
        (10, 2548175, 176345645),
        (20, 4807892, 313263888),
    ],
)
def test_fixed_sealed_auto_counts_and_actual_route(size: int, m3: int, official: int) -> None:
    entry = SEALED_GEOMETRY_PORTFOLIOS[size]
    # Cross-check committed Fractions before invoking either engine.
    assert entry.m3_plus_probability * 13983816 == m3
    assert entry.official_any_prize_probability * 601304088 == official
    with patch.object(engine, "evaluate_portfolio_reference", side_effect=AssertionError):
        result = engine.evaluate_portfolio_with_diagnostics(entry.tickets)
    assert result.diagnostics.requested_engine == "auto"
    assert result.diagnostics.actual_engine == "dp"
    assert result.probability.main_draw_count == 13983816
    assert result.probability.special_count == 43
    assert result.probability.m3_plus_draw_count == m3
    assert result.probability.official_any_prize_outcome_count == official


def test_actual_k10_consumer_smoke_without_search() -> None:
    entry = SEALED_GEOMETRY_PORTFOLIOS[10]
    with patch.object(engine, "count_loss_polynomial", wraps=engine.count_loss_polynomial) as dp:
        observed = score_portfolio(entry.tickets)
    assert dp.call_count == 1
    assert observed.m3_plus == entry.m3_plus_probability
    assert observed.official_any_prize == entry.official_any_prize_probability
