"""Historical replay of the ``ITERATIVE_EXACT_1EXCHANGE_EXPECTED_MAX_V1`` seed
and terminal BIG_LOTTO portfolios (``k`` in 2, 3, 5, 10) across the existing
FULL/RECENT_750/RECENT_300/RECENT_50 target-window contract.

Reuses, unmodified: the exact-native draw loader and window contract
(:mod:`lottolab.domain.exact_native_replay`,
:func:`lottolab.application.use_cases.replay_exact_native_targets.load_authoritative_draws`),
the official BIG_LOTTO prize evaluator
(:func:`lottolab.domain.prize_evaluation.evaluate_lottery_prize`), the
existing "any official prize" historical random baseline
(:mod:`lottolab.application.historical_success_random_baseline`), and the
producing optimizer's own portfolio-hash convention
(:func:`lottolab.research.expected_max_main_matches_exact_1exchange_ascent.portfolio_sha256`).

This module answers one question only: how much do the two *fixed*
portfolios' historical success rates differ under the existing "any official
prize" success event. It does not recompute -- and must never be read as
replacing -- the artifact's own ``EXPECTED_MAX_MAIN_MATCHES_V1`` structural
score, which is a theoretical expectation over all draws, not a historical
frequency.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from fractions import Fraction

from lottolab.application.historical_success_random_baseline import (
    OFFICIAL_ANY_PRIZE_BASELINE_POLICY_VERSION,
    HistoricalSuccessExactRational,
    official_any_prize_probability,
)
from lottolab.application.use_cases.replay_exact_native_targets import (
    DEFAULT_EXPECTED_MAIN_NUMBERS,
    DEFAULT_EXPECTED_SPECIAL_NUMBER,
    DEFAULT_MAX_VISIBLE_DRAW,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.exact_native_replay import (
    DEFAULT_WINDOW_ORDER,
    DEFAULT_WINDOW_SIZES,
    Draw,
    freeze_visible_draws,
)
from lottolab.domain.exact_native_replay import target_windows as compute_target_windows
from lottolab.domain.prize_evaluation import evaluate_lottery_prize
from lottolab.evidence.exact_native_replay_manifest import canonical_json_bytes, sha256_bytes
from lottolab.research.expected_max_main_matches_exact_1exchange_ascent import portfolio_sha256

Ticket = tuple[int, ...]
Portfolio = tuple[Ticket, ...]

SUCCESS_EVENT_ID = "BIG_LOTTO_OFFICIAL_ANY_PRIZE"
METHOD_ID = "ITERATIVE_EXACT_1EXCHANGE_EXPECTED_MAX_V1"
SUPPORTED_K: tuple[int, ...] = (2, 3, 5, 10)


class HistoricalReplayContractError(RuntimeError):
    """Frozen-input identity, portfolio-equality, or evidence-completeness violation."""


def as_portfolio(raw: Sequence[Sequence[int]]) -> Portfolio:
    return tuple(tuple(int(number) for number in ticket) for ticket in raw)


def portfolio_official_any_prize(portfolio: Portfolio, draw: Draw) -> bool:
    """True iff any ticket in ``portfolio`` wins an official BIG_LOTTO prize against ``draw``."""

    for ticket in portfolio:
        outcome = evaluate_lottery_prize(
            lottery_type=LotteryType.BIG_LOTTO,
            predicted_main_numbers=ticket,
            predicted_special_number=None,
            winning_main_numbers=draw.main_numbers,
            winning_special_number=draw.special_number,
        )
        if outcome.is_winner:
            return True
    return False


def replay_portfolio_over_draws(portfolio: Portfolio, draws: Sequence[Draw]) -> tuple[bool, ...]:
    """Per-draw success booleans, in the same order as ``draws``."""

    return tuple(portfolio_official_any_prize(portfolio, draw) for draw in draws)


def _fraction_dict(value: Fraction) -> dict[str, int]:
    return {"numerator": value.numerator, "denominator": value.denominator}


@dataclass(frozen=True, slots=True)
class WindowKCell:
    """One (window, k) replay cell: seed vs. terminal, same draw sample."""

    window_name: str
    k: int
    denominator: int
    seed_numerator: int
    terminal_numerator: int
    both_success: int
    only_terminal_success: int
    only_seed_success: int
    neither_success: int
    baseline_success_probability: HistoricalSuccessExactRational

    def __post_init__(self) -> None:
        if (
            self.both_success
            + self.only_terminal_success
            + self.only_seed_success
            + self.neither_success
            != self.denominator
        ):
            raise HistoricalReplayContractError(
                "pairwise contingency counts do not sum to denominator"
            )
        if self.both_success + self.only_seed_success != self.seed_numerator:
            raise HistoricalReplayContractError("seed numerator disagrees with pairwise counts")
        if self.both_success + self.only_terminal_success != self.terminal_numerator:
            raise HistoricalReplayContractError("terminal numerator disagrees with pairwise counts")

    def canonical_dict(self) -> dict[str, object]:
        denominator = self.denominator
        baseline_fraction = self.baseline_success_probability.as_fraction()
        seed_rate = Fraction(self.seed_numerator, denominator) if denominator else None
        terminal_rate = Fraction(self.terminal_numerator, denominator) if denominator else None
        delta_rate = (
            terminal_rate - seed_rate
            if seed_rate is not None and terminal_rate is not None
            else None
        )
        return {
            "window_name": self.window_name,
            "k": self.k,
            "denominator": denominator,
            "seed": _rate_payload(self.seed_numerator, denominator, seed_rate),
            "terminal": _rate_payload(self.terminal_numerator, denominator, terminal_rate),
            "terminal_minus_seed": {
                "rate_exact": _fraction_dict(delta_rate) if delta_rate is not None else None,
                "rate_float": float(delta_rate) if delta_rate is not None else None,
                "percentage_points": (float(delta_rate) * 100) if delta_rate is not None else None,
            },
            "pairwise_same_draw_counts": {
                "both_success": self.both_success,
                "only_terminal_success": self.only_terminal_success,
                "only_seed_success": self.only_seed_success,
                "neither_success": self.neither_success,
            },
            "baseline": {
                "event_id": SUCCESS_EVENT_ID,
                "policy_version": OFFICIAL_ANY_PRIZE_BASELINE_POLICY_VERSION,
                "kind": "EXACT_UNIFORM_IID_LEGAL_TICKET_WITH_REPLACEMENT",
                "applicable": denominator > 0,
                "success_probability_exact": self.baseline_success_probability.canonical_dict(),
                "success_probability_float": float(baseline_fraction),
                "seed_minus_baseline_pp": (
                    float(seed_rate - baseline_fraction) * 100 if seed_rate is not None else None
                ),
                "terminal_minus_baseline_pp": (
                    float(terminal_rate - baseline_fraction) * 100
                    if terminal_rate is not None
                    else None
                ),
            },
        }


def _rate_payload(numerator: int, denominator: int, rate: Fraction | None) -> dict[str, object]:
    return {
        "numerator": numerator,
        "denominator": denominator,
        "rate_exact": _fraction_dict(rate) if rate is not None else None,
        "rate_float": float(rate) if rate is not None else None,
    }


def evaluate_window_k_cell(
    *,
    window_name: str,
    k: int,
    seed_portfolio: Portfolio,
    terminal_portfolio: Portfolio,
    draws: Sequence[Draw],
) -> WindowKCell:
    """Replay ``seed_portfolio`` and ``terminal_portfolio`` over the same ``draws``.

    When the two portfolios are literally identical (``k`` in 2, 3, 5), the
    terminal series is not independently re-measured: the single measured
    series is reused for both, and the pairwise contingency degenerates to
    "both" / "neither" only -- never a manufactured independent measurement.
    """

    seed_hits = replay_portfolio_over_draws(seed_portfolio, draws)
    terminal_hits = (
        seed_hits
        if terminal_portfolio == seed_portfolio
        else replay_portfolio_over_draws(terminal_portfolio, draws)
    )
    paired = tuple(zip(seed_hits, terminal_hits, strict=True))
    both = sum(1 for seed_hit, terminal_hit in paired if seed_hit and terminal_hit)
    only_terminal = sum(1 for seed_hit, terminal_hit in paired if terminal_hit and not seed_hit)
    only_seed = sum(1 for seed_hit, terminal_hit in paired if seed_hit and not terminal_hit)
    neither = sum(1 for seed_hit, terminal_hit in paired if not seed_hit and not terminal_hit)
    return WindowKCell(
        window_name=window_name,
        k=k,
        denominator=len(draws),
        seed_numerator=sum(seed_hits),
        terminal_numerator=sum(terminal_hits),
        both_success=both,
        only_terminal_success=only_terminal,
        only_seed_success=only_seed,
        neither_success=neither,
        baseline_success_probability=official_any_prize_probability(k),
    )


@dataclass(frozen=True, slots=True)
class VerifiedPortfolioPair:
    k: int
    seed: Portfolio
    terminal: Portfolio
    seed_sha256_recorded: str
    terminal_sha256_recorded: str
    seed_equals_terminal: bool


def load_and_verify_portfolios(artifact: Mapping[str, object]) -> dict[int, VerifiedPortfolioPair]:
    """Extract k=2/3/5/10 seed/terminal portfolios and verify their recorded hashes.

    Raises :class:`HistoricalReplayContractError` rather than silently
    continuing when a recomputed hash disagrees with the artifact's own
    recorded value, or when k in (2, 3, 5) is not seed-terminal identical.
    """

    k_results = artifact["k_results"]
    if not isinstance(k_results, Mapping):
        raise HistoricalReplayContractError("artifact k_results is not a mapping")

    verified: dict[int, VerifiedPortfolioPair] = {}
    for k in SUPPORTED_K:
        entry = k_results[str(k)]
        seed = as_portfolio(entry["seed_portfolio"])
        terminal = as_portfolio(entry["terminal_portfolio"])
        if len(seed) != k or len(terminal) != k:
            raise HistoricalReplayContractError(f"k={k}: portfolio ticket count does not equal k")
        seed_recorded = entry["seed_portfolio_sha256"]
        terminal_recorded = entry["terminal_portfolio_sha256"]
        if portfolio_sha256(seed) != seed_recorded:
            raise HistoricalReplayContractError(f"k={k}: seed_portfolio_sha256 does not reproduce")
        if portfolio_sha256(terminal) != terminal_recorded:
            raise HistoricalReplayContractError(
                f"k={k}: terminal_portfolio_sha256 does not reproduce"
            )
        seed_equals_terminal = seed == terminal
        if seed_equals_terminal != (seed_recorded == terminal_recorded):
            raise HistoricalReplayContractError(
                f"k={k}: hash equality disagrees with value equality"
            )
        if k in (2, 3, 5) and not seed_equals_terminal:
            raise HistoricalReplayContractError(
                f"k={k}: expected seed==terminal (move_count=0) but portfolios differ"
            )
        verified[k] = VerifiedPortfolioPair(
            k=k,
            seed=seed,
            terminal=terminal,
            seed_sha256_recorded=seed_recorded,
            terminal_sha256_recorded=terminal_recorded,
            seed_equals_terminal=seed_equals_terminal,
        )
    return verified


def build_result(
    *,
    artifact: Mapping[str, object],
    input_artifact_path: str,
    input_artifact_sha256: str,
    pinned_commit: str,
    pinned_tree: str,
    all_draws: Sequence[Draw],
    draw_authority_metadata: Mapping[str, object],
    max_visible_draw: str = DEFAULT_MAX_VISIBLE_DRAW,
    expected_main_numbers: tuple[int, ...] | None = DEFAULT_EXPECTED_MAIN_NUMBERS,
    expected_special_number: int | None = DEFAULT_EXPECTED_SPECIAL_NUMBER,
    window_order: Sequence[str] = DEFAULT_WINDOW_ORDER,
    window_sizes: Mapping[str, int | None] = DEFAULT_WINDOW_SIZES,
    generated_at: datetime | None = None,
) -> dict[str, object]:
    """Assemble the complete historical-replay result payload (pure; no I/O)."""

    verified = load_and_verify_portfolios(artifact)
    later_present = any(int(draw.draw_number) > int(max_visible_draw) for draw in all_draws)
    visible = freeze_visible_draws(
        all_draws,
        max_visible_draw=max_visible_draw,
        expected_main_numbers=expected_main_numbers,
        expected_special_number=expected_special_number,
    )
    windows = compute_target_windows(visible, window_order=window_order, window_sizes=window_sizes)
    by_draw_number = {draw.draw_number: draw for draw in visible}

    windows_payload: dict[str, object] = {}
    results_payload: dict[str, dict[str, object]] = {}
    structural_reference: dict[str, object] = {}
    k_results = artifact["k_results"]

    for window_name in window_order:
        window = windows[window_name]
        draw_numbers = list(window["draw_numbers"])
        draw_numbers_sha256 = sha256_bytes(canonical_json_bytes(draw_numbers))
        windows_payload[window_name] = {
            "requested_size": window_sizes[window_name],
            "observations_required": window["observations_required"],
            "first_target": window["first_target"],
            "last_target": window["last_target"],
            "first_target_date": window["first_target_date"],
            "last_target_date": window["last_target_date"],
            "draw_numbers_sha256": draw_numbers_sha256,
        }
        window_draws = tuple(by_draw_number[number] for number in draw_numbers)
        for k in SUPPORTED_K:
            pair = verified[k]
            cell = evaluate_window_k_cell(
                window_name=window_name,
                k=k,
                seed_portfolio=pair.seed,
                terminal_portfolio=pair.terminal,
                draws=window_draws,
            )
            results_payload.setdefault(str(k), {})[window_name] = cell.canonical_dict()

    for k in SUPPORTED_K:
        entry = k_results[str(k)]
        structural_reference[str(k)] = {
            "seed_expected_max": entry["seed_expected_max"],
            "terminal_expected_max": entry["terminal_expected_max"],
            "delta_seed_to_terminal": entry["delta_seed_to_terminal"],
            "seed_equals_terminal": verified[k].seed_equals_terminal,
            "note": "cited verbatim from the pinned artifact; not recomputed by this replay",
        }

    generated = generated_at or datetime.now(UTC)
    return {
        "schema_version": "1.0.0",
        "task_id": "EXPECTED_MAX_MAIN_MATCHES_HISTORICAL_REPLAY_R1",
        "method_id": METHOD_ID,
        "success_event": {
            "id": SUCCESS_EVENT_ID,
            "definition": (
                "any ticket in the fixed k-ticket portfolio wins an official BIG_LOTTO "
                "prize tier against the actual historical draw"
            ),
            "evaluator_locator": {
                "repo_relative_path": "src/lottolab/domain/prize_evaluation.py",
                "symbol": "evaluate_lottery_prize",
            },
            "reused_from": (
                "lottolab.application.use_cases.replay_exact_native_targets._complete_row "
                "official_any_prize field (same BIG_LOTTO exact-native k5/k10/k20 replay lineage)"
            ),
        },
        "baseline": {
            "policy_version": OFFICIAL_ANY_PRIZE_BASELINE_POLICY_VERSION,
            "kind": "EXACT_UNIFORM_IID_LEGAL_TICKET_WITH_REPLACEMENT",
            "source_locator": {
                "repo_relative_path": (
                    "src/lottolab/application/historical_success_random_baseline.py"
                ),
                "symbol": "official_any_prize_probability",
            },
        },
        "input_artifact": {
            "repo_relative_path": input_artifact_path,
            "sha256": input_artifact_sha256,
            "pinned_commit": pinned_commit,
            "pinned_tree": pinned_tree,
        },
        "portfolio_identity_verification": {
            str(k): {
                "seed_portfolio_sha256_recorded": pair.seed_sha256_recorded,
                "terminal_portfolio_sha256_recorded": pair.terminal_sha256_recorded,
                "recomputed_via": (
                    "expected_max_main_matches_exact_1exchange_ascent.portfolio_sha256"
                ),
                "hash_reproduced": True,
                "seed_equals_terminal": pair.seed_equals_terminal,
            }
            for k, pair in verified.items()
        },
        "draw_authority": {
            **draw_authority_metadata,
            "max_visible_draw": max_visible_draw,
            "expected_main_numbers": (
                list(expected_main_numbers) if expected_main_numbers is not None else None
            ),
            "expected_special_number": expected_special_number,
            "later_draws_present_in_authority": later_present,
        },
        "windows": windows_payload,
        "results": results_payload,
        "structural_score_reference": structural_reference,
        "conclusion_boundary": {
            "structural_vs_historical": (
                "EXPECTED_MAX_MAIN_MATCHES_V1 is a theoretical expectation over all "
                "C(49,6) draws; the rates in `results` are historical replay frequencies "
                "under a real, finite, overlapping draw sample. Neither substitutes for "
                "the other."
            ),
            "window_overlap": (
                "FULL/RECENT_750/RECENT_300/RECENT_50 are nested, overlapping windows "
                "over the same draw sample, not four independent trials."
            ),
            "effect_detection_criterion": "DESCRIPTIVE_ONLY: no pre-existing significance "
            "or promotion criterion for this comparison was located; no such criterion is "
            "asserted here.",
            "no_promotion_claim": (
                "This result does not authorize promotion, ranking change, or any claim "
                "about future win rates or causal effect."
            ),
        },
        "generated_at_utc": generated.isoformat(),
    }


__all__ = [
    "METHOD_ID",
    "SUCCESS_EVENT_ID",
    "SUPPORTED_K",
    "HistoricalReplayContractError",
    "Portfolio",
    "Ticket",
    "VerifiedPortfolioPair",
    "WindowKCell",
    "as_portfolio",
    "build_result",
    "evaluate_window_k_cell",
    "load_and_verify_portfolios",
    "portfolio_official_any_prize",
    "replay_portfolio_over_draws",
]
