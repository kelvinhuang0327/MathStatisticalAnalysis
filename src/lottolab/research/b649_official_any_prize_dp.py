"""Integer frontier elimination for the complete degree 0..7 loss polynomial.

For threshold three, a losing subset intersects every ticket in at most two
numbers. Incidence groups of size c contribute binomial weights C(c,q).
Completed ticket counters can be forgotten; disconnected components multiply,
as does (1+z)^unused. Truncation above degree seven preserves L6 and L7.
No partial polynomial is returned on interruption or resource exhaustion.
"""

from __future__ import annotations

import ctypes
import gc
import math
import os
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from math import comb


class CountIncomplete(RuntimeError):
    """The exact count is unknown; no probability accompanies this exception."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


class UnsupportedDP(CountIncomplete):
    """A valid request lies outside the DP contract."""


def current_rss_bytes() -> int:
    """Resident memory now, never getrusage's historical high-water mark.

    Polling cannot enforce an instantaneous RSS ceiling during native allocation.
    Unavailable current-RSS telemetry fails closed rather than assuming free RAM.
    """
    if sys.platform == "darwin":
        library = ctypes.CDLL("/usr/lib/libSystem.B.dylib")
        task = ctypes.c_uint32.in_dll(library, "mach_task_self_").value
        data = (ctypes.c_uint64 * 6)()
        count = ctypes.c_uint32(12)
        if library.task_info(task, 20, ctypes.byref(data), ctypes.byref(count)) != 0:
            raise CountIncomplete("RSS_UNAVAILABLE")
        return int(data[1])
    if sys.platform.startswith("linux"):
        with open("/proc/self/statm", encoding="ascii") as stream:
            return int(stream.read().split()[1]) * os.sysconf("SC_PAGE_SIZE")
    raise CountIncomplete("RSS_UNAVAILABLE")


@dataclass(frozen=True, slots=True)
class EvaluationLimits:
    state_limit: int = 1_000_000
    dp_seconds: float = 5.0
    total_seconds: float = 900.0
    max_rss_bytes: int = 2 * 1024**3

    def __post_init__(self) -> None:
        if (
            type(self.state_limit) is not int
            or self.state_limit < 1
            or not math.isfinite(self.dp_seconds)
            or self.dp_seconds < 0
            or not math.isfinite(self.total_seconds)
            or self.total_seconds < 0
            or type(self.max_rss_bytes) is not int
            or self.max_rss_bytes < 1
        ):
            raise ValueError("invalid evaluation resource limits")


@dataclass(frozen=True, slots=True)
class EvaluationRuntime:
    """Per-call telemetry seam; no global timer or mutable cross-call state."""

    clock: Callable[[], float] = time.monotonic
    rss: Callable[[], int] = current_rss_bytes


class EvaluationBudget:
    def __init__(self, limits: EvaluationLimits, runtime: EvaluationRuntime) -> None:
        self.limits = limits
        self.runtime = runtime
        self.started = runtime.clock()
        self.deadline = self.started + limits.total_seconds
        self.dp_deadline = min(self.deadline, self.started + limits.dp_seconds)
        self.in_dp = True
        self.states = 0
        self.peak_live_states = 0
        self.observed_rss = 0

    def check(self) -> None:
        now = self.runtime.clock()
        if now >= self.deadline:
            raise CountIncomplete("TOTAL_TIME_LIMIT")
        if self.in_dp and now >= self.dp_deadline:
            raise CountIncomplete("DP_TIME_LIMIT")
        rss = self.runtime.rss()
        self.observed_rss = max(self.observed_rss, rss)
        if rss >= self.limits.max_rss_bytes:
            raise CountIncomplete("RSS_LIMIT")

    def visit(self, live: int) -> None:
        # Cumulative distinct insertions, including initial states/coefficients.
        if self.states >= self.limits.state_limit:
            raise CountIncomplete("STATE_LIMIT")
        self.states += 1
        self.peak_live_states = max(self.peak_live_states, live)
        if self.states % 2048 == 0:
            self.check()

    def admit_reference(
        self, pool_size: int, draw_size: int, tickets: int, chunk_size: int, supplied: bool
    ) -> None:
        self.in_dp = False
        self.check()
        draws = comb(pool_size, draw_size)
        # Conservative working-space estimate, including the construction tuples
        # and vector temporaries. Caller-owned draw memory is already in RSS.
        construction = 0 if supplied else 8 * draws + 256 * comb(pool_size, max(0, draw_size - 2))
        required = construction + 96 * min(draws, chunk_size) + tickets * 64
        if self.runtime.rss() + required >= self.limits.max_rss_bytes:
            raise CountIncomplete("REFERENCE_MEMORY_ADMISSION")
        # Admission estimate only, not a throughput guarantee. Every reference
        # phase also checks the original deadline before and after bounded work.
        estimated_seconds = 0.01 + draws * (tickets + 1) / 5_000_000
        if self.deadline - self.runtime.clock() <= estimated_seconds:
            raise CountIncomplete("REFERENCE_TIME_ADMISSION")

    def release_partial(self) -> None:
        # Called outside the except block, after the traceback and DP frame die.
        gc.collect()


@dataclass(frozen=True, slots=True)
class _Step:
    low_mask: int
    keep_mask: int
    weights: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class LossPolynomial:
    coefficients: tuple[int, ...]
    component_count: int
    signature_count: int
    unused_count: int


def supports_dp(pool_size: int, draw_size: int, outright_matches: int) -> bool:
    return draw_size == 6 and outright_matches == 3 and 6 < pool_size <= 64


def _build_model(
    portfolio: Sequence[Sequence[int]], pool_size: int, budget: EvaluationBudget
) -> tuple[list[list[_Step]], int, int]:
    budget.check()
    tickets = tuple(sorted({tuple(sorted(ticket)) for ticket in portfolio}))
    groups: dict[tuple[int, ...], int] = {}
    for number in range(1, pool_size + 1):
        budget.check()
        signature = tuple(i for i, ticket in enumerate(tickets) if number in ticket)
        groups[signature] = groups.get(signature, 0) + 1
    unused = groups.pop((), 0)
    remaining = set(range(len(tickets)))
    components: list[list[_Step]] = []
    while remaining:
        budget.check()
        connected = {min(remaining)}
        while True:
            expanded = connected | {
                i for signature in groups if connected.intersection(signature) for i in signature
            }
            budget.check()
            if expanded == connected:
                break
            connected = expanded
        remaining -= connected
        pending = sorted(signature for signature in groups if connected.intersection(signature))
        seen: set[int] = set()
        steps: list[_Step] = []
        while pending:
            budget.check()

            def score(
                signature: tuple[int, ...],
                pending: list[tuple[int, ...]] = pending,
                seen: set[int] = seen,
            ) -> tuple[int, int, tuple[int, ...]]:
                budget.check()
                future = {i for other in pending if other != signature for i in other}
                touched = seen | set(signature)
                return len(touched & future), -len(touched - future), signature

            signature = min(pending, key=score)
            pending.remove(signature)
            future = {i for other in pending for i in other}
            seen.update(signature)
            steps.append(
                _Step(
                    sum(1 << (2 * i) for i in signature),
                    sum(3 << (2 * i) for i in seen & future),
                    tuple(comb(groups[signature], q) for q in range(min(groups[signature], 2) + 1)),
                )
            )
        components.append(steps)
    return components, unused, len(groups)


def _convolve(left: list[int], right: list[int], budget: EvaluationBudget) -> list[int]:
    result = [0] * 8
    for i, x in enumerate(left):
        for j, y in enumerate(right[: 8 - i]):
            result[i + j] += x * y
    for value in result:
        if value:
            budget.visit(8)
    budget.check()
    return result


def count_loss_polynomial(
    portfolio: Sequence[Sequence[int]], *, pool_size: int, budget: EvaluationBudget
) -> LossPolynomial:
    """Return all eight coefficients or raise; input tickets are validated by caller.

    Two bits per active ticket encode 0..2 hits. The low three key bits encode
    subset degree 0..7. q=1 rejects a counter at two; q=2 rejects any nonzero
    counter. Addition is therefore carry-free. Forgetting counters happens only
    after their last incidence group. Every transition uses Python integers.
    """
    components, unused, signatures = _build_model(portfolio, pool_size, budget)
    polynomial = [1] + [0] * 7
    for steps in components:
        states = {0: 1}
        budget.visit(1)
        for step in steps:
            target: dict[int, int] = {}
            for index, (key, multiplicity) in enumerate(states.items()):
                if index % 2048 == 0:
                    budget.check()
                degree, hits = key & 7, key >> 3
                for q, weight in enumerate(step.weights):
                    if degree + q > 7:
                        break
                    if q == 1 and ((hits >> 1) & step.low_mask):
                        continue
                    if q == 2 and (hits & (step.low_mask | (step.low_mask << 1))):
                        continue
                    new_key = (((hits + q * step.low_mask) & step.keep_mask) << 3) | (degree + q)
                    if new_key not in target:
                        budget.visit(len(states) + len(target) + 1)
                        target[new_key] = multiplicity * weight
                    else:
                        target[new_key] += multiplicity * weight
            states = target
        local = [0] * 8
        for key, value in states.items():
            if key >> 3:
                raise AssertionError("a completed component retained ticket counters")
            local[key & 7] += value
        polynomial = _convolve(polynomial, local, budget)
    polynomial = _convolve(polynomial, [comb(unused, q) for q in range(min(unused, 7) + 1)], budget)
    budget.check()
    return LossPolynomial(tuple(polynomial), len(components), signatures, unused)
