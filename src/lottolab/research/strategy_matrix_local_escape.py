"""Canonical Strategy Matrix registration for exact local-escape methods.

The Matrix historically invoked the radius-one implementation directly from
phase-specific runners.  This module preserves that implementation unchanged
and adds the already-validated exact radius-two implementation behind the same
small, explicit dispatch surface.  Only the two frozen methods are registered;
this is not a radius-N framework.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Final, Literal

from lottolab.research.exact_radius_two_local_escape import (
    PackedWinningSpace,
    ProgressCallback,
    iterative_exact_radius_two_ascent,
)
from lottolab.research.reference_e_exact_one_exchange_refinement import (
    Portfolio,
)
from lottolab.research.reference_e_iterative_exact_one_exchange_ascent import (
    iterative_exact_one_exchange_ascent,
)

RADIUS_ONE_EXACT_ONE_EXCHANGE_METHOD_ID: Final = (
    "ITERATIVE_EXACT_1EXCHANGE_REFINEMENT_V1"
)
RADIUS_TWO_EXACT_TWO_EXCHANGE_METHOD_ID: Final = (
    "ITERATIVE_EXACT_RADIUS2_TWO_EXCHANGE_LOCAL_ESCAPE_V1"
)

type RegisteredMethodId = Literal[
    "ITERATIVE_EXACT_1EXCHANGE_REFINEMENT_V1",
    "ITERATIVE_EXACT_RADIUS2_TWO_EXCHANGE_LOCAL_ESCAPE_V1",
]


@dataclass(frozen=True, slots=True)
class StrategyMatrixLocalEscapeMethod:
    """One frozen local-escape method available to Matrix evaluation."""

    method_id: RegisteredMethodId
    exchange_radius: Literal[1, 2]
    exchange_semantics: str
    objective_id: str
    implementation_path: str
    implementation_symbol: str
    global_optimum_status: Literal["UNKNOWN"] = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class RegisteredLocalEscapeIteration:
    """Common exact trace row without changing either method's definition."""

    iteration_index: int
    input_portfolio: Portfolio
    input_q: Fraction
    best_endpoint_portfolio: Portfolio
    best_endpoint_q: Fraction
    delta: Fraction
    accepted_move: bool
    first_level_candidate_count: int
    single_replacement_endpoint_count: int | None
    two_replacement_endpoint_count: int | None
    unique_endpoint_count: int


@dataclass(frozen=True, slots=True)
class RegisteredLocalEscapeResult:
    """Normalized Matrix result for one registered exact local escape."""

    registration: StrategyMatrixLocalEscapeMethod
    seed_portfolio: Portfolio
    seed_q: Fraction
    iterations: tuple[RegisteredLocalEscapeIteration, ...]
    move_count: int
    unique_endpoints_evaluated: int
    terminal_portfolio: Portfolio
    terminal_q: Fraction


_REGISTERED_METHODS: Final = (
    StrategyMatrixLocalEscapeMethod(
        method_id=RADIUS_ONE_EXACT_ONE_EXCHANGE_METHOD_ID,
        exchange_radius=1,
        exchange_semantics="EXACT_ONE_NUMBER_EXCHANGE",
        objective_id="EXACT_M3_PLUS_FRACTION",
        implementation_path=(
            "src/lottolab/research/reference_e_iterative_exact_one_exchange_ascent.py"
        ),
        implementation_symbol="iterative_exact_one_exchange_ascent",
    ),
    StrategyMatrixLocalEscapeMethod(
        method_id=RADIUS_TWO_EXACT_TWO_EXCHANGE_METHOD_ID,
        exchange_radius=2,
        exchange_semantics="EXACT_TWO_ONE_NUMBER_EXCHANGE_ENDPOINT",
        objective_id="EXACT_M3_PLUS_FRACTION",
        implementation_path="src/lottolab/research/exact_radius_two_local_escape.py",
        implementation_symbol="iterative_exact_radius_two_ascent",
    ),
)


def registered_local_escape_methods() -> tuple[StrategyMatrixLocalEscapeMethod, ...]:
    """Return the two deterministic Matrix registrations in stable order."""

    return _REGISTERED_METHODS


def local_escape_method_registration(
    method_id: str,
) -> StrategyMatrixLocalEscapeMethod:
    """Resolve one exact Matrix method or fail without a fallback."""

    for registration in _REGISTERED_METHODS:
        if registration.method_id == method_id:
            return registration
    raise ValueError(f"unregistered Strategy Matrix local-escape method: {method_id}")


def _radius_one_result(
    registration: StrategyMatrixLocalEscapeMethod,
    *,
    pool_size: int,
    draw_size: int,
    minimum_matches: int,
    seed_portfolio: Portfolio,
) -> RegisteredLocalEscapeResult:
    raw = iterative_exact_one_exchange_ascent(
        pool_size=pool_size,
        draw_size=draw_size,
        minimum_matches=minimum_matches,
        seed_portfolio=seed_portfolio,
    )
    iterations = tuple(
        RegisteredLocalEscapeIteration(
            iteration_index=iteration.iteration_index,
            input_portfolio=iteration.input_portfolio,
            input_q=iteration.input_q,
            best_endpoint_portfolio=iteration.best_neighbor_portfolio,
            best_endpoint_q=iteration.best_neighbor_q,
            delta=iteration.delta,
            accepted_move=iteration.accepted_move,
            first_level_candidate_count=iteration.unique_legal_neighbor_count,
            single_replacement_endpoint_count=None,
            two_replacement_endpoint_count=None,
            unique_endpoint_count=iteration.unique_legal_neighbor_count,
        )
        for iteration in raw.iterations
    )
    return RegisteredLocalEscapeResult(
        registration=registration,
        seed_portfolio=raw.seed_portfolio,
        seed_q=raw.seed_q,
        iterations=iterations,
        move_count=raw.move_count,
        unique_endpoints_evaluated=sum(
            iteration.unique_endpoint_count for iteration in iterations
        ),
        terminal_portfolio=raw.terminal_portfolio,
        terminal_q=raw.terminal_q,
    )


def _radius_two_result(
    registration: StrategyMatrixLocalEscapeMethod,
    *,
    pool_size: int,
    draw_size: int,
    seed_portfolio: Portfolio,
    progress: ProgressCallback | None,
) -> RegisteredLocalEscapeResult:
    raw = iterative_exact_radius_two_ascent(
        PackedWinningSpace.build(pool_size, draw_size),
        seed_portfolio,
        progress=progress,
    )
    iterations = tuple(
        RegisteredLocalEscapeIteration(
            iteration_index=iteration.iteration_index,
            input_portfolio=iteration.input_portfolio,
            input_q=iteration.input_q,
            best_endpoint_portfolio=iteration.best_endpoint_portfolio,
            best_endpoint_q=iteration.best_endpoint_q,
            delta=iteration.delta,
            accepted_move=iteration.accepted_move,
            first_level_candidate_count=iteration.first_level_neighbor_count,
            single_replacement_endpoint_count=(
                iteration.single_replacement_endpoint_count
            ),
            two_replacement_endpoint_count=iteration.two_replacement_endpoint_count,
            unique_endpoint_count=iteration.unique_endpoint_count,
        )
        for iteration in raw.iterations
    )
    return RegisteredLocalEscapeResult(
        registration=registration,
        seed_portfolio=raw.seed_portfolio,
        seed_q=raw.seed_q,
        iterations=iterations,
        move_count=raw.move_count,
        unique_endpoints_evaluated=raw.unique_endpoints_evaluated,
        terminal_portfolio=raw.terminal_portfolio,
        terminal_q=raw.terminal_q,
    )


def evaluate_registered_local_escape(
    method_id: str,
    *,
    pool_size: int,
    draw_size: int,
    minimum_matches: int,
    seed_portfolio: Portfolio,
    progress: ProgressCallback | None = None,
) -> RegisteredLocalEscapeResult:
    """Invoke exactly one registered radius-one or radius-two method.

    The Matrix slice is frozen to exact M3+ coverage.  Radius one keeps its
    existing implementation and radius two delegates directly to the preserved
    exact core; neither algorithm is reimplemented here.
    """

    registration = local_escape_method_registration(method_id)
    if minimum_matches != 3:
        raise ValueError("Strategy Matrix local escape is frozen to exact M3_PLUS")
    if registration.method_id == RADIUS_ONE_EXACT_ONE_EXCHANGE_METHOD_ID:
        return _radius_one_result(
            registration,
            pool_size=pool_size,
            draw_size=draw_size,
            minimum_matches=minimum_matches,
            seed_portfolio=seed_portfolio,
        )
    return _radius_two_result(
        registration,
        pool_size=pool_size,
        draw_size=draw_size,
        seed_portfolio=seed_portfolio,
        progress=progress,
    )
