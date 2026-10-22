"""Independent outcome census, polynomial census, and resource fault injection."""

from __future__ import annotations

import itertools
import random
from fractions import Fraction
from math import comb

import pytest

from lottolab.research import b649_official_any_prize_exact as exact
from lottolab.research.b649_official_any_prize_dp import (
    CountIncomplete,
    EvaluationLimits,
    EvaluationRuntime,
    current_rss_bytes,
)

TICKET = (1, 2, 3, 4, 5, 6)


def direct(portfolio: tuple[tuple[int, ...], ...], pool: int) -> exact.ExactPortfolioProbability:
    """Enumerate (main,special), independently of masks/signatures/seven-sets."""
    m3 = official = 0
    for main in itertools.combinations(range(1, pool + 1), 6):
        hits = [len(set(ticket).intersection(main)) for ticket in portfolio]
        m3 += any(hit >= 3 for hit in hits)
        for special in range(1, pool + 1):
            if special not in main:
                official += any(
                    hit >= 3 or (hit == 2 and special in ticket)
                    for ticket, hit in zip(portfolio, hits, strict=True)
                )
    return exact.ExactPortfolioProbability(comb(pool, 6), pool - 6, m3, official)


def small(pool: int) -> tuple[tuple[int, ...], ...]:
    return tuple(
        random.Random(20261021).sample(list(itertools.combinations(range(1, pool + 1), 6)), 6)
    )


@pytest.mark.parametrize("pool,official", [(12, 5544), (16, 78323)])
def test_fixed_small_three_independent_routes(pool: int, official: int) -> None:
    portfolio = small(pool)
    import hashlib
    import json

    identities = {
        12: "1bbc70fdf5edbcdecddf99d4b5978da8b0d0479461ec9ba868106c3becc4f96c",
        16: "323d28da51a9da4effa9b25da7eb6808b93b3c716917b0e432ff4ececa5664ec",
    }
    assert (
        hashlib.sha256(json.dumps(portfolio, separators=(",", ":")).encode()).hexdigest()
        == identities[pool]
    )
    observed = exact.evaluate_portfolio_with_diagnostics(portfolio, pool_size=pool, engine="dp")
    expected = direct(portfolio, pool)
    assert observed.probability == exact.evaluate_portfolio_reference(portfolio, pool_size=pool)
    assert observed.probability == expected
    assert expected.official_any_prize_outcome_count == official
    assert observed.diagnostics.actual_engine == "dp"
    assert observed.probability.m3_plus == Fraction(expected.m3_plus_draw_count, comb(pool, 6))
    assert observed.probability.official_any_prize == Fraction(official, comb(pool, 6) * (pool - 6))


@pytest.mark.parametrize(
    "portfolio,pool",
    [
        ((TICKET,), 12),
        ((TICKET, TICKET), 12),
        ((TICKET, (4, 5, 6, 7, 8, 9)), 12),
        ((TICKET, (7, 8, 9, 10, 11, 12)), 14),
    ],
)
def test_every_coefficient_multiplicity_components_and_unused(
    portfolio: tuple[tuple[int, ...], ...],
    pool: int,
) -> None:
    expected = tuple(
        sum(
            all(len(set(subset).intersection(ticket)) <= 2 for ticket in portfolio)
            for subset in itertools.combinations(range(1, pool + 1), degree)
        )
        for degree in range(8)
    )
    observed = exact.evaluate_portfolio_with_diagnostics(portfolio, pool_size=pool, engine="dp")
    assert observed.diagnostics.loss_polynomial == expected
    assert observed.probability == direct(portfolio, pool)
    relabeled = tuple(tuple(pool + 1 - n for n in reversed(t)) for t in reversed(portfolio))
    replay = exact.evaluate_portfolio_with_diagnostics(relabeled, pool_size=pool, engine="dp")
    assert replay.probability == observed.probability
    assert replay.diagnostics.loss_polynomial == expected


def test_real_small_state_limit_discards_all_coefficients_and_falls_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = exact.evaluate_portfolio_reference((TICKET,), pool_size=12)
    reference = exact.evaluate_portfolio_reference
    calls = 0

    def spy(*args: object, **kwargs: object) -> exact.ExactPortfolioProbability:
        nonlocal calls
        calls += 1
        return reference(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(exact, "evaluate_portfolio_reference", spy)
    limits = EvaluationLimits(state_limit=7)
    observed = exact.evaluate_portfolio_with_diagnostics((TICKET,), pool_size=12, limits=limits)
    assert observed.probability == expected
    assert observed.diagnostics.dp_states == 7
    assert observed.diagnostics.loss_polynomial is None
    assert observed.diagnostics.fallback_reason == "STATE_LIMIT"
    assert observed.diagnostics.actual_engine == "enumeration"
    assert calls == 1
    with pytest.raises(CountIncomplete, match="STATE_LIMIT") as error:
        exact.evaluate_portfolio_with_diagnostics(
            (TICKET,), pool_size=12, engine="dp", limits=limits
        )
    assert not hasattr(error.value, "coefficients")
    assert calls == 1


@pytest.mark.parametrize(
    "error", [AssertionError("defect"), RuntimeError("defect"), KeyboardInterrupt(), SystemExit(2)]
)
def test_defects_and_cancellation_propagate(
    monkeypatch: pytest.MonkeyPatch, error: BaseException
) -> None:
    def fail(*args: object, **kwargs: object) -> None:
        raise error

    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("unexpected fallback")

    monkeypatch.setattr(exact, "count_loss_polynomial", fail)
    monkeypatch.setattr(exact, "evaluate_portfolio_reference", forbidden)
    with pytest.raises(type(error)):
        exact.evaluate_portfolio_with_diagnostics((TICKET,), pool_size=12)


def test_memory_error_releases_partial_state_before_reference(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import weakref

    class Partial:
        pass

    partial: weakref.ReferenceType[Partial] | None = None
    reference = exact.evaluate_portfolio_reference

    def fail(*args: object, **kwargs: object) -> None:
        nonlocal partial
        state = Partial()
        partial = weakref.ref(state)
        raise MemoryError

    def spy(*args: object, **kwargs: object) -> exact.ExactPortfolioProbability:
        assert partial is not None and partial() is None
        return reference(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(exact, "count_loss_polynomial", fail)
    monkeypatch.setattr(exact, "evaluate_portfolio_reference", spy)
    result = exact.evaluate_portfolio_with_diagnostics((TICKET,), pool_size=12)
    assert result.probability == direct((TICKET,), 12)
    assert result.diagnostics.fallback_reason == "MEMORY_LIMIT"
    assert result.diagnostics.loss_polynomial is None


def test_time_limit_includes_build_and_shared_deadline(monkeypatch: pytest.MonkeyPatch) -> None:
    now = [0.0]
    runtime = EvaluationRuntime(clock=lambda: now[0], rss=lambda: 1)
    original = exact.count_loss_polynomial

    def delayed(*args: object, **kwargs: object) -> object:
        now[0] = 6.0
        return original(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(exact, "count_loss_polynomial", delayed)
    result = exact.evaluate_portfolio_with_diagnostics((TICKET,), pool_size=12, runtime=runtime)
    assert result.diagnostics.fallback_reason == "DP_TIME_LIMIT"
    assert result.diagnostics.total_seconds == 6
    with pytest.raises(CountIncomplete, match="REFERENCE_TIME_ADMISSION"):
        now[0] = 0
        exact.evaluate_portfolio_with_diagnostics(
            (TICKET,),
            pool_size=12,
            runtime=runtime,
            limits=EvaluationLimits(total_seconds=6.001),
        )
    with pytest.raises(CountIncomplete, match="TOTAL_TIME_LIMIT"):
        now[0] = 0
        exact.evaluate_portfolio_with_diagnostics(
            (TICKET,),
            pool_size=12,
            runtime=runtime,
            limits=EvaluationLimits(total_seconds=6),
        )


def test_reference_checks_original_deadline_after_progress(monkeypatch: pytest.MonkeyPatch) -> None:
    now = [0.0]
    runtime = EvaluationRuntime(clock=lambda: now[0], rss=lambda: 1)
    original = exact.np.count_nonzero

    def expire(*args: object, **kwargs: object) -> object:
        now[0] = 2.0
        return original(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(exact.np, "count_nonzero", expire)
    with pytest.raises(CountIncomplete, match="TOTAL_TIME_LIMIT"):
        exact.evaluate_portfolio_with_diagnostics(
            (TICKET,),
            pool_size=12,
            runtime=runtime,
            limits=EvaluationLimits(state_limit=1, total_seconds=1),
        )


def test_current_rss_admission_rejects_and_can_recover() -> None:
    reads = [0]

    def transient_rss() -> int:
        reads[0] += 1
        return 2 * 1024**3 if reads[0] == 1 else 1

    observed = exact.evaluate_portfolio_with_diagnostics(
        (TICKET,), pool_size=12, runtime=EvaluationRuntime(rss=transient_rss)
    )
    assert observed.diagnostics.fallback_reason == "RSS_LIMIT"
    assert observed.probability == direct((TICKET,), 12)
    with pytest.raises(CountIncomplete, match="REFERENCE_MEMORY_ADMISSION"):
        exact.evaluate_portfolio_with_diagnostics(
            (TICKET,),
            pool_size=12,
            runtime=EvaluationRuntime(rss=lambda: 500),
            limits=EvaluationLimits(state_limit=1, max_rss_bytes=1000),
        )
    with pytest.raises(CountIncomplete, match="RSS_LIMIT"):
        exact.evaluate_portfolio_with_diagnostics(
            (TICKET,),
            pool_size=12,
            runtime=EvaluationRuntime(rss=lambda: 1000),
            limits=EvaluationLimits(max_rss_bytes=1000),
        )
    assert current_rss_bytes() > 0


def test_supported_pool64_without_materializing_draws() -> None:
    result = exact.evaluate_portfolio_with_diagnostics((TICKET,), pool_size=64, engine="dp")
    m3 = sum(comb(6, hits) * comb(58, 6 - hits) for hits in range(3, 7))
    assert result.probability.m3_plus_draw_count == m3
    assert result.probability.official_any_prize == exact.evaluate_single_ticket_closed_form(
        pool_size=64
    )
    assert result.diagnostics.actual_engine == "dp"


@pytest.mark.parametrize(
    "limits",
    [
        {"state_limit": 0},
        {"dp_seconds": -1},
        {"total_seconds": float("nan")},
        {"max_rss_bytes": 0},
    ],
)
def test_invalid_limits_fail_before_counting(limits: dict[str, int | float]) -> None:
    with pytest.raises(ValueError):
        EvaluationLimits(**limits)  # type: ignore[arg-type]


def test_independent_checker_detects_corrupt_polynomial(monkeypatch: pytest.MonkeyPatch) -> None:
    from lottolab.research import b649_official_any_prize_dp as dp

    original = dp._convolve  # pyright: ignore[reportPrivateUsage]
    expected = direct((TICKET,), 12)

    def check() -> None:
        assert exact.evaluate_portfolio((TICKET,), pool_size=12) == expected

    def corrupt(left: list[int], right: list[int], budget: dp.EvaluationBudget) -> list[int]:
        polynomial = original(left, right, budget)
        polynomial[6] += 1
        return polynomial

    check()
    with monkeypatch.context() as mutation:
        mutation.setattr(dp, "_convolve", corrupt)
        with pytest.raises(AssertionError):
            check()
    check()
