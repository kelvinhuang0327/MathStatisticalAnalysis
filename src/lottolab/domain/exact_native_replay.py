"""Exact-native portfolio replay: pure domain types and rules.

Canonicalizes the BIG_LOTTO exact-native K5/K10/K20 replay universe (fixed
``native_ticket_count_bounds`` equal to the descriptor's own
``native_ticket_count`` -- so a variable-bounds strategy such as
``legacy_biglotto__evolution_engine__3df019c31ce4`` (bounds ``(1, 10)``) can
never satisfy the filter for any fixed ticket count).

Pure dataclasses and rules only -- no hashing, no canonical-JSON logic, no
adapter execution. Content hashing lives in
:mod:`lottolab.evidence.exact_native_replay_manifest` (the evidence layer may
depend on domain; domain must never depend on evidence). Adapter loading and
execution live in
:mod:`lottolab.application.use_cases.replay_exact_native_targets` (domain
must never depend on application or on ``lottolab.strategies``).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import cast

from lottolab.domain.strategies import ResponseShape, StrategyDescriptor

#: Current canonical exact-native ticket counts. Exposed as a CLI default,
#: not a hardcoded behavior -- callers may pass a different set explicitly.
DEFAULT_NATIVE_TICKET_COUNTS: tuple[int, ...] = (5, 10, 20)

#: Current canonical target-window contract. Exposed as CLI defaults.
DEFAULT_WINDOW_ORDER: tuple[str, ...] = ("FULL", "RECENT_750", "RECENT_300", "RECENT_50")
DEFAULT_WINDOW_SIZES: Mapping[str, int | None] = {
    "FULL": None,
    "RECENT_750": 750,
    "RECENT_300": 300,
    "RECENT_50": 50,
}


class ExactNativeReplayError(RuntimeError):
    """The exact-native replay contract cannot be completed safely."""


@dataclass(frozen=True, slots=True)
class Draw:
    """One validated lottery draw from the canonical draw authority."""

    draw_number: str
    draw_date: date
    main_numbers: tuple[int, ...]
    special_number: int

    @property
    def sort_key(self) -> tuple[date, int]:
        return self.draw_date, int(self.draw_number)


@dataclass(frozen=True, slots=True)
class RuntimeBinding:
    """One strategy descriptor paired with its loaded adapter, or a binding failure.

    ``implementation`` is intentionally untyped (``object | None``): domain
    must not import ``lottolab.strategies.adapters.base.PortfolioBetAdapter``.
    Callers that execute the binding (application layer) narrow the type.
    """

    descriptor: StrategyDescriptor
    implementation: object | None
    adapter_class_name: str | None
    binding_error: str | None


def assert_causal_history(target: Draw, history: Sequence[Draw]) -> None:
    """Reject any history row at or after the target draw's ordering key."""

    if any(draw.sort_key >= target.sort_key for draw in history):
        raise ExactNativeReplayError(f"CAUSAL_CUTOFF_VIOLATION before target {target.draw_number}")


def exact_native_descriptors(
    descriptors: Sequence[StrategyDescriptor],
    *,
    native_ticket_counts: Sequence[int],
) -> tuple[StrategyDescriptor, ...]:
    """Filter to PORTFOLIO strategies whose bounds are exactly one fixed ticket count.

    A descriptor qualifies only when its ``native_ticket_count_bounds`` equal
    ``(native_ticket_count, native_ticket_count)`` -- a true range (such as
    Evolution Engine's ``(1, 10)``) never qualifies for any requested count.
    """

    allowed = tuple(native_ticket_counts)
    exact = tuple(
        descriptor
        for descriptor in descriptors
        if descriptor.response_shape is ResponseShape.PORTFOLIO
        and descriptor.native_ticket_count in allowed
        and tuple(descriptor.native_ticket_count_bounds)
        == (descriptor.native_ticket_count, descriptor.native_ticket_count)
    )
    ids = [descriptor.strategy_id for descriptor in exact]
    if len(ids) != len(set(ids)):
        raise ExactNativeReplayError("EXACT_NATIVE_UNIVERSE_CONTRACT_INVALID")
    return exact


def descriptor_payload(descriptor: StrategyDescriptor) -> dict[str, object]:
    """Stable, hashable projection of one strategy descriptor's identity fields."""

    return {
        "strategy_id": descriptor.strategy_id,
        "display_name": descriptor.strategy_name,
        "version": descriptor.version,
        "lottery_types": [lottery_type.value for lottery_type in descriptor.lottery_types],
        "lifecycle_status": descriptor.lifecycle_status.value,
        "executable": descriptor.executable,
        "adapter_path": descriptor.adapter_path,
        "min_history": descriptor.min_history,
        "response_shape": descriptor.response_shape.value,
        "native_ticket_count": descriptor.native_ticket_count,
        "native_ticket_count_bounds": list(descriptor.native_ticket_count_bounds),
        "provenance": list(descriptor.provenance),
    }


def freeze_visible_draws(
    draws: Sequence[Draw],
    *,
    max_visible_draw: str,
    expected_main_numbers: tuple[int, ...] | None = None,
    expected_special_number: int | None = None,
) -> tuple[Draw, ...]:
    """Truncate to draws at or before ``max_visible_draw`` and verify its identity.

    ``expected_main_numbers``/``expected_special_number`` are an optional
    known-answer guard on the max-visible draw's payload (current default
    run pins draw 115000083); omit both to skip the identity guard.
    """

    visible = tuple(draw for draw in draws if int(draw.draw_number) <= int(max_visible_draw))
    target = next((draw for draw in visible if draw.draw_number == max_visible_draw), None)
    if target is None:
        raise ExactNativeReplayError(f"DRAW_AUTHORITY_{max_visible_draw}_UNAVAILABLE")
    if expected_main_numbers is not None and tuple(target.main_numbers) != expected_main_numbers:
        raise ExactNativeReplayError(
            f"unexpected {max_visible_draw} main numbers: {target.main_numbers}"
        )
    if expected_special_number is not None and target.special_number != expected_special_number:
        raise ExactNativeReplayError(
            f"unexpected {max_visible_draw} special number: {target.special_number}"
        )
    if visible[-1].draw_number != max_visible_draw:
        raise ExactNativeReplayError(
            f"visible last draw {visible[-1].draw_number} != {max_visible_draw}"
        )
    return visible


def target_windows(
    draws: Sequence[Draw],
    *,
    window_order: Sequence[str] = DEFAULT_WINDOW_ORDER,
    window_sizes: Mapping[str, int | None] = DEFAULT_WINDOW_SIZES,
) -> dict[str, dict[str, object]]:
    """Compute the named target-window contract (``FULL``/``RECENT_*``) over visible draws."""

    windows: dict[str, dict[str, object]] = {}
    for name in window_order:
        size = window_sizes[name]
        if size is not None and len(draws) < size:
            raise ExactNativeReplayError(f"DRAW_AUTHORITY_INSUFFICIENT_FOR_{name}")
        selected = tuple(draws) if size is None else tuple(draws)[-size:]
        numbers = [draw.draw_number for draw in selected]
        if len(numbers) != len(set(numbers)):
            raise ExactNativeReplayError(f"window draw sequence is not unique: {name}")
        windows[name] = {
            "observations_required": len(selected),
            "draw_numbers": numbers,
            "first_target": selected[0].draw_number,
            "last_target": selected[-1].draw_number,
            "first_target_date": selected[0].draw_date.isoformat(),
            "last_target_date": selected[-1].draw_date.isoformat(),
        }
    return windows


def window_names_for_target(target: Draw, windows: Mapping[str, Mapping[str, object]]) -> list[str]:
    """Names of every window whose ``draw_numbers`` contains this target."""

    return [name for name, window in windows.items() if target.draw_number in _draw_numbers(window)]


def _draw_numbers(window: Mapping[str, object]) -> Sequence[str]:
    value = window["draw_numbers"]
    if not isinstance(value, Sequence):
        raise ExactNativeReplayError("window draw_numbers must be a sequence")
    return cast(Sequence[str], value)


@dataclass(frozen=True, slots=True)
class WindowReaggregationEligibility:
    """Evaluation result for one (strategy, window) ranking eligibility check."""

    window_name: str
    metric_status: str  # "AVAILABLE" | "UNAVAILABLE"
    rankable: bool
    unavailable_reason: str | None
    requested_draw_count: int
    available_observation_count: int
    excluded_observation_count: int
    failure_count: int
    coverage: float


def evaluate_window_reaggregation_eligibility(
    *,
    window_name: str,
    window_draw_numbers: Sequence[str],
    evidence_rows: Sequence[Mapping[str, object]],
) -> WindowReaggregationEligibility:
    """Evaluate ranking availability and observation counts for one window.

    Determines ranking availability per strategy x window independently:
    - An ``EXECUTION_FAILURE`` inside ``window_draw_numbers`` marks the window
      ``UNAVAILABLE``.
    - An ``EXECUTION_FAILURE`` outside ``window_draw_numbers`` has no effect
      on this window.
    - ``WINDOW_INELIGIBLE_INCOMPLETE_OBSERVATIONS`` is excluded from the evaluated
      denominator without marking the window ``UNAVAILABLE``.
    - Membership is derived strictly from ``window_draw_numbers``; persisted
      ``window_names`` on evidence rows are ignored as stale.
    - Availability is never cached globally across windows.
    """
    target_set = set(window_draw_numbers)
    requested = len(window_draw_numbers)

    matching_rows = [
        row
        for row in evidence_rows
        if str(row.get("target_draw_number", "")) in target_set
    ]

    available_count = 0
    excluded_count = 0
    failure_count = 0
    first_failure_reason: str | None = None

    for row in matching_rows:
        status = row.get("replay_status")
        if status == "COMPLETE":
            available_count += 1
        elif status == "WINDOW_INELIGIBLE_INCOMPLETE_OBSERVATIONS":
            excluded_count += 1
        elif status in ("EXECUTION_FAILURE", "NATIVE_TICKET_COUNT_VIOLATION"):
            failure_count += 1
            if first_failure_reason is None:
                first_failure_reason = cast(str | None, row.get("reason")) or str(status)
        else:
            failure_count += 1
            if first_failure_reason is None:
                first_failure_reason = cast(str | None, row.get("reason")) or str(status)

    denominator = requested - excluded_count
    coverage = (available_count / denominator) if denominator > 0 else 0.0
    coverage = min(1.0, max(0.0, coverage))

    if failure_count > 0:
        metric_status = "UNAVAILABLE"
        rankable = False
        unavailable_reason = first_failure_reason or "EXECUTION_FAILURE"
    elif available_count == 0:
        metric_status = "UNAVAILABLE"
        rankable = False
        unavailable_reason = "NO_AVAILABLE_OBSERVATIONS"
    else:
        metric_status = "AVAILABLE"
        rankable = True
        unavailable_reason = None

    return WindowReaggregationEligibility(
        window_name=window_name,
        metric_status=metric_status,
        rankable=rankable,
        unavailable_reason=unavailable_reason,
        requested_draw_count=requested,
        available_observation_count=available_count,
        excluded_observation_count=excluded_count,
        failure_count=failure_count,
        coverage=coverage,
    )


__all__ = [
    "DEFAULT_NATIVE_TICKET_COUNTS",
    "DEFAULT_WINDOW_ORDER",
    "DEFAULT_WINDOW_SIZES",
    "Draw",
    "ExactNativeReplayError",
    "RuntimeBinding",
    "WindowReaggregationEligibility",
    "assert_causal_history",
    "descriptor_payload",
    "evaluate_window_reaggregation_eligibility",
    "exact_native_descriptors",
    "freeze_visible_draws",
    "target_windows",
    "window_names_for_target",
]
