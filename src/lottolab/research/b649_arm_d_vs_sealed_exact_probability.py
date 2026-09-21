"""Exact fair-draw OFFICIAL_ANY_PRIZE evaluation of frozen Branch2 ARM_D vs sealed production.

This module evaluates the frozen Branch2 ARM_D (MIN_OVERLAP) ticket portfolios against
the current sealed production geometry portfolios (B649_SEALED_GEOMETRY_PORTFOLIO 1.0.0)
under the BIG_LOTTO_UNIFORM_FAIR_DRAW finite outcome space (601,304,088 outcomes).

All outcome counts and probabilities are computed and aggregated using exact integer
and Fraction arithmetic. No historical draw outcomes are scored.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from multiprocessing import get_context
from pathlib import Path
from typing import Final, cast

import numpy as np

from lottolab.application.b649_sealed_geometry_portfolio import (
    SEALED_GEOMETRY_PORTFOLIOS,
    canonical_portfolio_sha256,
)
from lottolab.research.b649_official_any_prize_exact import (
    BIG_LOTTO_DRAW_SIZE,
    BIG_LOTTO_POOL_SIZE,
    DrawMasks,
    all_main_draw_masks,
    evaluate_portfolio,
)

TASK_ID: Final = "B649_ARM_D_VS_SEALED_OUTCOME_FREE_EXACT_PROBABILITY_R1"
METHOD_VERSION: Final = "1.0.0"
MODEL_IDENTITY: Final = "BIG_LOTTO_UNIFORM_FAIR_DRAW"
EVENT_DEFINITION: Final = "OFFICIAL_ANY_PRIZE"

POOL_SIZE: Final = BIG_LOTTO_POOL_SIZE  # 49
DRAW_SIZE: Final = BIG_LOTTO_DRAW_SIZE  # 6
SPECIAL_COUNT: Final = POOL_SIZE - DRAW_SIZE  # 43
TOTAL_MAIN_DRAWS: Final = math.comb(POOL_SIZE, DRAW_SIZE)  # 13,983,816
TOTAL_OUTCOME_SPACE: Final = TOTAL_MAIN_DRAWS * SPECIAL_COUNT  # 601,304,088

UPSTREAM_AUTHORITY_LOCATOR: Final = (
    "/Users/kelvin/VibeCoding-WorkSpace/.worktrees/MathStatisticalAnalysis/"
    "BRANCH2_PORTFOLIO_GEOMETRY_FOUR_ARM_OOS_R1/docs/research/"
    "branch2-portfolio-geometry-four-arm-oos-r1-result.json"
)
UPSTREAM_AUTHORITY_COMMIT: Final = "d7665ee5d00fac09fdc593908e81e54ae080f2ba"
UPSTREAM_AUTHORITY_TREE: Final = "5a9cbff94817c82163c32f1274f7c73d19bc8426"
UPSTREAM_AUTHORITY_SHA256: Final = (
    "af1291ad73b8e78665a7181f4403c243b245855b2d1ce24e64ee950d23294ec3"
)

PRODUCTION_AUTHORITY_COMMIT: Final = "2560407ec6267e0fcf3b7cfb5627c1a4f1158baf"
EVALUATOR_CONTENT_SHA256: Final = "92dcb836254cc6dbcd6c2ad907e619a5eb8cf3917197a8f6de3e5f989825cf66"

EXPECTED_SEALED_PROBABILITY_K10: Final = Fraction(1095245, 3734808)
EXPECTED_SEALED_PROBABILITY_K20: Final = Fraction(44615213, 85900584)

EXPECTED_ARCHIVE_ROW_COUNT: Final = 1761
PRIMARY_K: Final = 10
SECONDARY_K: Final = 20

LABEL_SUCCESS: Final = "EXACT_GEOMETRY_ADVANTAGE_ON_FROZEN_ARCHIVE"
LABEL_FAIL: Final = "NO_MEAN_GEOMETRY_SUPERIORITY_ON_FROZEN_ARCHIVE"
LABEL_TIE: Final = "EXACT_TIE"
LABEL_INCONCLUSIVE: Final = "INCONCLUSIVE_GATE"

type Ticket = tuple[int, ...]
type Portfolio = tuple[Ticket, ...]


class InconclusiveGateError(RuntimeError):
    """Raised when any identity, integrity, completeness or oracle check fails."""


@dataclass(frozen=True, slots=True)
class EvaluatedRow:
    """Deterministic exact evaluation record for one draw row."""

    target_draw: str | int
    portfolio_sha256: str
    outcome_count: int
    probability_str: str


@dataclass(frozen=True, slots=True)
class ArmDEvaluationResult:
    """Exact aggregation results for one K bucket across all archive rows."""

    k: int
    row_count: int
    unique_portfolio_count: int
    cache_hit_count: int
    exact_production_probability: Fraction
    exact_sum_arm_d_outcomes: int
    exact_mean_arm_d_probability: Fraction
    exact_delta: Fraction
    decimal_mean_arm_d_probability: float
    decimal_production_probability: float
    decimal_delta: float
    row_evaluations: tuple[EvaluatedRow, ...]
    row_outcomes_sha256: str

    def to_summary_dict(self) -> dict[str, object]:
        """Convert to canonical JSON-safe dictionary (excluding huge per-row lists)."""
        return {
            "k": self.k,
            "row_count": self.row_count,
            "unique_portfolio_count": self.unique_portfolio_count,
            "cache_hit_count": self.cache_hit_count,
            "exact_production_probability": str(self.exact_production_probability),
            "exact_sum_arm_d_outcomes": self.exact_sum_arm_d_outcomes,
            "exact_mean_arm_d_probability": str(self.exact_mean_arm_d_probability),
            "exact_delta": str(self.exact_delta),
            "decimal_production_probability": self.decimal_production_probability,
            "decimal_mean_arm_d_probability": self.decimal_mean_arm_d_probability,
            "decimal_delta": self.decimal_delta,
            "row_outcomes_sha256": self.row_outcomes_sha256,
        }


# Global worker state for multiprocessing pool
_worker_draws: DrawMasks | None = None


def _init_evaluator_worker() -> None:
    global _worker_draws
    _worker_draws = all_main_draw_masks(POOL_SIZE, DRAW_SIZE)


def _eval_portfolio_worker(tickets: Sequence[Sequence[int]]) -> int:
    global _worker_draws
    if _worker_draws is None:
        _worker_draws = all_main_draw_masks(POOL_SIZE, DRAW_SIZE)
    res = evaluate_portfolio(tickets, draws=_worker_draws)
    return res.official_any_prize_outcome_count


def verify_upstream_authority_file(upstream_path: Path | str = UPSTREAM_AUTHORITY_LOCATOR) -> None:
    """Verify the Branch2 upstream result artifact existence and SHA256 digest."""
    path = Path(upstream_path)
    if not path.is_file():
        raise InconclusiveGateError(f"Branch2 upstream artifact absent: {path}")
    raw_bytes = path.read_bytes()
    computed_sha256 = hashlib.sha256(raw_bytes).hexdigest()
    if computed_sha256 != UPSTREAM_AUTHORITY_SHA256:
        raise InconclusiveGateError(
            f"Branch2 upstream SHA256 mismatch: expected {UPSTREAM_AUTHORITY_SHA256}, "
            f"observed {computed_sha256}"
        )


def verify_evaluator_content_sha256(evaluator_path: Path | str | None = None) -> None:
    """Verify the b649_official_any_prize_exact.py source content digest."""
    if evaluator_path is None:
        # Resolve sibling module path relative to this file
        evaluator_path = Path(__file__).parent / "b649_official_any_prize_exact.py"
    path = Path(evaluator_path)
    if not path.is_file():
        raise InconclusiveGateError(f"Exact evaluator file absent: {path}")
    raw_bytes = path.read_bytes()
    computed_sha256 = hashlib.sha256(raw_bytes).hexdigest()
    if computed_sha256 != EVALUATOR_CONTENT_SHA256:
        raise InconclusiveGateError(
            f"Exact evaluator content SHA256 mismatch: expected {EVALUATOR_CONTENT_SHA256}, "
            f"observed {computed_sha256}"
        )


def verify_production_sealed_portfolios(
    draws: DrawMasks | None = None,
) -> dict[int, Fraction]:
    """Verify production sealed K10 and K20 reproduce expected probabilities."""
    for size in (PRIMARY_K, SECONDARY_K):
        entry = SEALED_GEOMETRY_PORTFOLIOS.get(size)
        if entry is None:
            raise InconclusiveGateError(f"Sealed geometry portfolio missing for K{size}")

    if draws is None:
        draws = all_main_draw_masks(POOL_SIZE, DRAW_SIZE)

    res10 = evaluate_portfolio(SEALED_GEOMETRY_PORTFOLIOS[PRIMARY_K].tickets, draws=draws)
    if res10.official_any_prize != EXPECTED_SEALED_PROBABILITY_K10:
        raise InconclusiveGateError(
            f"Sealed K10 reproduction failed: expected {EXPECTED_SEALED_PROBABILITY_K10}, "
            f"observed {res10.official_any_prize}"
        )

    res20 = evaluate_portfolio(SEALED_GEOMETRY_PORTFOLIOS[SECONDARY_K].tickets, draws=draws)
    if res20.official_any_prize != EXPECTED_SEALED_PROBABILITY_K20:
        raise InconclusiveGateError(
            f"Sealed K20 reproduction failed: expected {EXPECTED_SEALED_PROBABILITY_K20}, "
            f"observed {res20.official_any_prize}"
        )

    return {
        PRIMARY_K: res10.official_any_prize,
        SECONDARY_K: res20.official_any_prize,
    }


def load_frozen_arm_d_archive(
    upstream_path: Path | str = UPSTREAM_AUTHORITY_LOCATOR,
) -> tuple[tuple[str, ...], dict[int, tuple[Portfolio, ...]]]:
    """Load only target identities and MIN_OVERLAP portfolios from frozen Branch2 result.

    Explicitly does NOT consume:
    - winning numbers;
    - baseline / candidate hit scores;
    - winner flags;
    - prize results;
    - recent-window results;
    - historical payout;
    - any outcome-derived values.
    """
    verify_upstream_authority_file(upstream_path)
    raw_obj: object = json.loads(Path(upstream_path).read_text(encoding="utf-8"))
    if not isinstance(raw_obj, dict):
        raise InconclusiveGateError("Malformed upstream artifact: not a JSON object")
    raw = cast(dict[str, object], raw_obj)

    by_k_obj = raw.get("by_k")
    if not isinstance(by_k_obj, dict):
        raise InconclusiveGateError("Malformed upstream artifact: 'by_k' missing or not dict")
    by_k = cast(dict[str, object], by_k_obj)

    loaded_portfolios: dict[int, list[Portfolio]] = {}
    target_ids_by_k: dict[int, list[str]] = {}

    for k in (PRIMARY_K, SECONDARY_K):
        k_str = str(k)
        if k_str not in by_k:
            raise InconclusiveGateError(f"Missing 'by_k[{k_str}]' in upstream artifact")
        k_data_obj = by_k[k_str]
        if not isinstance(k_data_obj, dict):
            raise InconclusiveGateError(f"'by_k[{k_str}]' is not a dict")
        k_data = cast(dict[str, object], k_data_obj)
        paired_draws_obj = k_data.get("paired_draws")
        if not isinstance(paired_draws_obj, list):
            raise InconclusiveGateError(f"'paired_draws' for K{k} missing or not a list")
        paired_draws = cast(list[object], paired_draws_obj)
        if len(paired_draws) != EXPECTED_ARCHIVE_ROW_COUNT:
            raise InconclusiveGateError(
                f"K{k} archive row count mismatch: expected {EXPECTED_ARCHIVE_ROW_COUNT}, "
                f"observed {len(paired_draws)}"
            )

        k_portfolios: list[Portfolio] = []
        k_target_ids: list[str] = []

        for idx, row_obj in enumerate(paired_draws):
            if not isinstance(row_obj, dict):
                raise InconclusiveGateError(f"K{k} row {idx} is not a dictionary")
            row = cast(dict[str, object], row_obj)
            target_draw = row.get("target_draw")
            if not isinstance(target_draw, (str, int)):
                raise InconclusiveGateError(
                    f"K{k} row {idx} has invalid target_draw: {target_draw}"
                )
            target_str = str(target_draw)
            k_target_ids.append(target_str)

            tickets_dict_obj = row.get("tickets")
            if not isinstance(tickets_dict_obj, dict):
                raise InconclusiveGateError(f"K{k} row {idx} missing tickets dictionary")
            tickets_dict = cast(dict[str, object], tickets_dict_obj)
            raw_min_overlap_obj = tickets_dict.get("MIN_OVERLAP")
            if not isinstance(raw_min_overlap_obj, list):
                raise InconclusiveGateError(f"K{k} row {idx} missing MIN_OVERLAP ticket list")
            raw_min_overlap = cast(list[object], raw_min_overlap_obj)
            if len(raw_min_overlap) != k:
                raise InconclusiveGateError(
                    f"K{k} row {idx} ticket count {len(raw_min_overlap)} != {k}"
                )

            # Validate tickets
            canonical_tickets: list[Ticket] = []
            for t_raw_obj in raw_min_overlap:
                if not isinstance(t_raw_obj, list):
                    raise InconclusiveGateError(
                        f"K{k} row {idx} ticket is not a list: {t_raw_obj}"
                    )
                t_raw = cast(list[object], t_raw_obj)
                if len(t_raw) != DRAW_SIZE:
                    raise InconclusiveGateError(
                        f"K{k} row {idx} ticket illegal length: {t_raw}"
                    )
                int_numbers: list[int] = []
                for n in t_raw:
                    if not isinstance(n, int) or not (1 <= n <= POOL_SIZE):
                        raise InconclusiveGateError(
                            f"K{k} row {idx} ticket numbers out of pool: {t_raw}"
                        )
                    int_numbers.append(n)
                if len(set(int_numbers)) != DRAW_SIZE:
                    raise InconclusiveGateError(f"K{k} row {idx} ticket has duplicates: {t_raw}")
                canonical_tickets.append(tuple(sorted(int_numbers)))

            k_portfolios.append(tuple(canonical_tickets))

        loaded_portfolios[k] = k_portfolios
        target_ids_by_k[k] = k_target_ids

    # Target sets and order must be identical between K10 and K20
    if target_ids_by_k[PRIMARY_K] != target_ids_by_k[SECONDARY_K]:
        raise InconclusiveGateError("K10 and K20 target draw ID sequences differ between archives")

    target_ids_tuple = tuple(target_ids_by_k[PRIMARY_K])
    frozen_portfolios = {
        PRIMARY_K: tuple(loaded_portfolios[PRIMARY_K]),
        SECONDARY_K: tuple(loaded_portfolios[SECONDARY_K]),
    }
    return target_ids_tuple, frozen_portfolios


def evaluate_arm_d_stream(
    k: int,
    portfolios: Sequence[Portfolio],
    target_draws: Sequence[str | int],
    sealed_prob: Fraction,
    *,
    draws: DrawMasks | None = None,
    max_workers: int = 2,
) -> ArmDEvaluationResult:
    """Evaluate all portfolios in one K bucket with memoization, preserving equal weighting."""
    if len(portfolios) != len(target_draws):
        raise InconclusiveGateError("Portfolios and target_draws length mismatch")
    if len(portfolios) != EXPECTED_ARCHIVE_ROW_COUNT:
        raise InconclusiveGateError(
            f"Expected exactly {EXPECTED_ARCHIVE_ROW_COUNT} rows, got {len(portfolios)}"
        )

    # Find unique portfolios for evaluation
    unique_portfolios = list(dict.fromkeys(portfolios))
    unique_count = len(unique_portfolios)
    cache_hit_count = len(portfolios) - unique_count

    # Evaluate unique portfolios
    unique_outcome_map: dict[Portfolio, int] = {}

    if max_workers > 1:
        ctx = get_context("spawn")
        with ctx.Pool(processes=max_workers, initializer=_init_evaluator_worker) as pool:
            counts = pool.map(_eval_portfolio_worker, unique_portfolios)
            for p, count in zip(unique_portfolios, counts, strict=True):
                unique_outcome_map[p] = count
    else:
        if draws is None:
            draws = all_main_draw_masks(POOL_SIZE, DRAW_SIZE)
        for p in unique_portfolios:
            res = evaluate_portfolio(p, draws=draws)
            unique_outcome_map[p] = res.official_any_prize_outcome_count

    # Reconstruct weighted evaluation for all rows in exact archive sequence
    evaluated_rows: list[EvaluatedRow] = []
    row_outcome_counts: list[int] = []

    for target_draw, p in zip(target_draws, portfolios, strict=True):
        count = unique_outcome_map[p]
        p_sha256 = canonical_portfolio_sha256(p)
        prob = Fraction(count, TOTAL_OUTCOME_SPACE)
        evaluated_rows.append(
            EvaluatedRow(
                target_draw=target_draw,
                portfolio_sha256=p_sha256,
                outcome_count=count,
                probability_str=str(prob),
            )
        )
        row_outcome_counts.append(count)

    exact_sum_arm_d_outcomes = sum(row_outcome_counts)
    total_space_all_rows = len(portfolios) * TOTAL_OUTCOME_SPACE
    exact_mean_arm_d_probability = Fraction(exact_sum_arm_d_outcomes, total_space_all_rows)
    exact_delta = exact_mean_arm_d_probability - sealed_prob

    # Deterministic hash of outcome counts sequence to certify aggregate integrity
    counts_bytes = np.array(row_outcome_counts, dtype=np.int64).tobytes()
    row_outcomes_sha256 = hashlib.sha256(counts_bytes).hexdigest()

    return ArmDEvaluationResult(
        k=k,
        row_count=len(portfolios),
        unique_portfolio_count=unique_count,
        cache_hit_count=cache_hit_count,
        exact_production_probability=sealed_prob,
        exact_sum_arm_d_outcomes=exact_sum_arm_d_outcomes,
        exact_mean_arm_d_probability=exact_mean_arm_d_probability,
        exact_delta=exact_delta,
        decimal_mean_arm_d_probability=float(exact_mean_arm_d_probability),
        decimal_production_probability=float(sealed_prob),
        decimal_delta=float(exact_delta),
        row_evaluations=tuple(evaluated_rows),
        row_outcomes_sha256=row_outcomes_sha256,
    )


def run_exact_probability_study(
    upstream_path: Path | str = UPSTREAM_AUTHORITY_LOCATOR,
    *,
    evaluator_path: Path | str | None = None,
    max_workers: int = 2,
    draws: DrawMasks | None = None,
) -> dict[str, object]:
    """Execute the full frozen ARM_D vs sealed production exact-probability study."""
    # Step 1: Verify authorities
    verify_upstream_authority_file(upstream_path)
    verify_evaluator_content_sha256(evaluator_path)

    # Step 2: Verify production sealed reproduction
    sealed_probabilities = verify_production_sealed_portfolios(draws=draws)
    sealed_k10_prob = sealed_probabilities[PRIMARY_K]
    sealed_k20_prob = sealed_probabilities[SECONDARY_K]

    # Step 3: Load frozen archive (contract: no outcome fields)
    target_draws, portfolios_by_k = load_frozen_arm_d_archive(upstream_path)

    # Step 4: Evaluate K10 (primary)
    k10_result = evaluate_arm_d_stream(
        PRIMARY_K,
        portfolios_by_k[PRIMARY_K],
        target_draws,
        sealed_k10_prob,
        draws=draws,
        max_workers=max_workers,
    )

    # Step 5: Evaluate K20 (secondary descriptive)
    k20_result = evaluate_arm_d_stream(
        SECONDARY_K,
        portfolios_by_k[SECONDARY_K],
        target_draws,
        sealed_k20_prob,
        draws=draws,
        max_workers=max_workers,
    )

    # Step 6: Determine decision gates
    exact_tie = False
    if k10_result.exact_delta > 0:
        primary_result_label = LABEL_SUCCESS
    elif k10_result.exact_delta < 0:
        primary_result_label = LABEL_FAIL
    else:
        primary_result_label = LABEL_FAIL
        exact_tie = True

    if k20_result.exact_delta > 0:
        secondary_k20_description = "EXACT_GEOMETRY_ADVANTAGE_AT_K20"
    elif k20_result.exact_delta < 0:
        secondary_k20_description = "NO_MEAN_GEOMETRY_SUPERIORITY_AT_K20"
    else:
        secondary_k20_description = "EXACT_TIE_AT_K20"

    # Step 7: Build result payload
    result_payload: dict[str, object] = {
        "task_id": TASK_ID,
        "method_version": METHOD_VERSION,
        "authorities": {
            "branch2_upstream_locator": UPSTREAM_AUTHORITY_LOCATOR,
            "branch2_upstream_commit": UPSTREAM_AUTHORITY_COMMIT,
            "branch2_upstream_tree": UPSTREAM_AUTHORITY_TREE,
            "branch2_upstream_sha256": UPSTREAM_AUTHORITY_SHA256,
            "production_authority_commit": PRODUCTION_AUTHORITY_COMMIT,
            "evaluator_content_sha256": EVALUATOR_CONTENT_SHA256,
        },
        "model": {
            "model_identity": MODEL_IDENTITY,
            "outcome_space_exact_count": TOTAL_OUTCOME_SPACE,
            "total_main_draws": TOTAL_MAIN_DRAWS,
            "special_count": SPECIAL_COUNT,
            "event_definition": EVENT_DEFINITION,
            "evaluation_method": "MAIN_DRAW_COLLAPSED_EXACT_SPECIAL_UNION",
        },
        "gates": {
            "primary_result_label": primary_result_label,
            "secondary_k20_description": secondary_k20_description,
            "exact_tie": exact_tie,
            "k10_delta_positive": k10_result.exact_delta > 0,
            "k20_delta_positive": k20_result.exact_delta > 0,
            "all_identity_checks_passed": True,
            "reproduction_oracle_passed": True,
        },
        "k10": {
            **k10_result.to_summary_dict(),
            "target_draw_count": len(target_draws),
            "first_target_draw": target_draws[0],
            "last_target_draw": target_draws[-1],
        },
        "k20": {
            **k20_result.to_summary_dict(),
            "target_draw_count": len(target_draws),
            "first_target_draw": target_draws[0],
            "last_target_draw": target_draws[-1],
        },
        "claim_boundary": {
            "permitted_claim": (
                "The exact average OFFICIAL_ANY_PRIZE geometry probability of the 1,761 frozen "
                "ARM_D portfolios is compared to the current sealed production portfolio under "
                "BIG_LOTTO_UNIFORM_FAIR_DRAW."
            ),
            "forbidden_claims": [
                "CONFIRMATORY_OOS_SUCCESS",
                "PREDICTIVE_EDGE",
                "FUTURE_SUCCESS_RATE_IMPROVEMENT",
                "EXPECTED_PAYOUT_ADVANTAGE",
                "PROFIT",
                "ROI",
                "PRODUCTION_PROMOTION",
                "PRODUCTION_ADOPTION",
            ],
            "outcome_fields_used": False,
            "expected_payout_included": False,
            "historical_oos_rerun": False,
        },
    }

    return result_payload


def generate_markdown_report(result: Mapping[str, object]) -> str:
    """Generate the canonical research report from the study results."""
    gates = cast(dict[str, object], result["gates"])
    k10 = cast(dict[str, object], result["k10"])
    k20 = cast(dict[str, object], result["k20"])
    authorities = cast(dict[str, object], result["authorities"])
    model = cast(dict[str, object], result["model"])

    primary_label = str(gates["primary_result_label"])
    secondary_desc = str(gates["secondary_k20_description"])

    k10_m_p = k10["exact_mean_arm_d_probability"]
    k10_d_m_p = float(cast(float, k10["decimal_mean_arm_d_probability"]))
    k10_s_p = k10["exact_production_probability"]
    k10_d_s_p = float(cast(float, k10["decimal_production_probability"]))
    k10_del = k10["exact_delta"]
    k10_d_del = float(cast(float, k10["decimal_delta"]))

    k20_m_p = k20["exact_mean_arm_d_probability"]
    k20_d_m_p = float(cast(float, k20["decimal_mean_arm_d_probability"]))
    k20_s_p = k20["exact_production_probability"]
    k20_d_s_p = float(cast(float, k20["decimal_production_probability"]))
    k20_del = k20["exact_delta"]
    k20_d_del = float(cast(float, k20["decimal_delta"]))

    lines = [
        f"# {TASK_ID} — Report",
        "",
        f"**Status**: COMPLETE — {primary_label} | 2026-09-21",
        "",
        "## 0. Executive Summary",
        "",
        "This study evaluates the exact, outcome-free geometry probability of winning",
        "`OFFICIAL_ANY_PRIZE` under the uniform fair-draw model",
        "(`BIG_LOTTO_UNIFORM_FAIR_DRAW`, 601,304,088 finite outcomes) for:",
        "- Frozen Branch2 ARM_D (MIN_OVERLAP) archive: 1,761 historical target portfolios;",
        "- Sealed production portfolios (`B649_SEALED_GEOMETRY_PORTFOLIO` 1.0.0,",
        "  commit `2560407`).",
        "",
        "**Primary Metric (K10)**:",
        f"- Result Label: `{primary_label}`",
        f"- Mean ARM_D Exact Probability: `{k10_m_p}` ({k10_d_m_p:.8f})",
        f"- Sealed Production Exact Probability: `{k10_s_p}` ({k10_d_s_p:.8f})",
        f"- Exact Delta (ARM_D - Sealed): `{k10_del}` ({k10_d_del:+.8e})",
        "",
        "**Secondary Descriptive Metric (K20)**:",
        f"- Result Description: `{secondary_desc}`",
        f"- Mean ARM_D Exact Probability: `{k20_m_p}` ({k20_d_m_p:.8f})",
        f"- Sealed Production Exact Probability: `{k20_s_p}` ({k20_d_s_p:.8f})",
        f"- Exact Delta (ARM_D - Sealed): `{k20_del}` ({k20_d_del:+.8e})",
        "",
        "**Note**: Per the frozen protocol, K20 is descriptive only and does not rescue K10.",
        "",
        "## 1. Identity and Provenance",
        "",
        "```text",
        f"TASK_ID:                         {TASK_ID}",
        f"METHOD_VERSION:                  {METHOD_VERSION}",
        f"MODEL_IDENTITY:                  {model['model_identity']}",
        f"TOTAL_OUTCOME_SPACE:             {model['outcome_space_exact_count']:,}",
        f"EVENT_DEFINITION:                {model['event_definition']}",
        f"EVALUATION_METHOD:               {model['evaluation_method']}",
        f"BRANCH2_UPSTREAM_COMMIT:         {authorities['branch2_upstream_commit']}",
        f"BRANCH2_UPSTREAM_TREE:           {authorities['branch2_upstream_tree']}",
        f"BRANCH2_UPSTREAM_SHA256:         {authorities['branch2_upstream_sha256']}",
        f"PRODUCTION_AUTHORITY_COMMIT:     {authorities['production_authority_commit']}",
        f"EVALUATOR_CONTENT_SHA256:        {authorities['evaluator_content_sha256']}",
        "```",
        "",
        "## 2. Methodology & Scientific Safeguards",
        "",
        "1. **Exact Finite-Outcome Enumeration**: Every probability is an exact integer fraction",
        "   over the full outcome space (`C(49, 6) * 43 = 601,304,088`). Special ball union is",
        "   collapsed analytically (`MAIN_DRAW_COLLAPSED_EXACT_SPECIAL_UNION`).",
        "2. **Outcome-Free Boundary**: Zero historical winning numbers, hit scores, or payout",
        "   amounts were provided to or consumed by the evaluator.",
        "3. **Weighting Discipline**: All 1,761 historical rows receive equal weight (1/1761).",
        "   Repeated portfolios and forced-selection draws are fully preserved.",
        "4. **Production Oracle Reproduction**: The exact evaluator independently reproduced the",
        "   production sealed baseline probabilities for K10 (`1095245/3734808`) and",
        "   K20 (`44615213/85900584`).",
        "",
        "## 3. Detailed Results",
        "",
        "| Metric | K10 (Primary) | K20 (Secondary) |",
        "|---|---|---|",
        f"| Archive Row Count | {k10['row_count']} | {k20['row_count']} |",
        f"| Unique Portfolios | {k10['unique_portfolio_count']} | "
        f"{k20['unique_portfolio_count']} |",
        f"| Evaluation Cache Hits | {k10['cache_hit_count']} | {k20['cache_hit_count']} |",
        f"| Sum Successful Outcomes | {k10['exact_sum_arm_d_outcomes']:,} | "
        f"{k20['exact_sum_arm_d_outcomes']:,} |",
        f"| Mean ARM_D Probability | {k10['exact_mean_arm_d_probability']} | "
        f"{k20['exact_mean_arm_d_probability']} |",
        f"| Sealed Production Probability | {k10['exact_production_probability']} | "
        f"{k20['exact_production_probability']} |",
        f"| Exact Delta (ARM_D - Sealed) | {k10['exact_delta']} | {k20['exact_delta']} |",
        f"| Decimal Delta | {k10_d_del:+.8e} | {k20_d_del:+.8e} |",
        f"| Row Outcomes SHA-256 | `{str(k10['row_outcomes_sha256'])[:16]}...` | "
        f"`{str(k20['row_outcomes_sha256'])[:16]}...` |",
        "",
        "## 4. Decision Gate Adjudication",
        "",
        f"- `Delta_10 > 0`: **{gates['k10_delta_positive']}**",
        f"- Primary Gate Result: `{primary_label}`",
        f"- `Delta_20 > 0`: **{gates['k20_delta_positive']}**",
        f"- Secondary Description: `{secondary_desc}`",
        "",
        "## 5. Claim Boundary & Non-Claims",
        "",
        "**Permitted Statement**:",
        "- The exact average OFFICIAL_ANY_PRIZE geometry probability of the 1,761 frozen ARM_D",
        "  portfolios is compared to the current sealed production portfolio under",
        "  BIG_LOTTO_UNIFORM_FAIR_DRAW.",
        "",
        "**Strictly Forbidden & Unclaimed**:",
        "- `CONFIRMATORY_OOS_SUCCESS`: Not claimed.",
        "- `PREDICTIVE_EDGE`: Not claimed.",
        "- `FUTURE_SUCCESS_RATE_IMPROVEMENT`: Not claimed.",
        "- `EXPECTED_PAYOUT_ADVANTAGE`: Not claimed.",
        "- `PROFIT`: Not claimed.",
        "- `ROI`: Not claimed.",
        "- `PRODUCTION_PROMOTION`: Not claimed.",
        "- `PRODUCTION_ADOPTION`: Not claimed.",
        "",
        "## 6. Verification and Reproducibility",
        "",
        "To independently reproduce the evaluation:",
        "```bash",
        "PYTHONPATH=src python -m lottolab.research.b649_arm_d_vs_sealed_exact_probability",
        "```",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    """CLI entry point to execute the study and write canonical output artifacts."""
    import argparse

    parser = argparse.ArgumentParser(description=f"Run {TASK_ID}")
    parser.add_argument(
        "--upstream",
        default=UPSTREAM_AUTHORITY_LOCATOR,
        help="Path to Branch2 upstream result JSON",
    )
    parser.add_argument(
        "--output-dir",
        default="docs/research",
        help="Directory to write canonical result JSON and report MD",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=2,
        help="Number of worker processes (max 2 per policy)",
    )
    args = parser.parse_args()

    max_workers = min(args.workers, 2)
    print(f"Starting {TASK_ID} evaluation (max_workers={max_workers})...")
    result = run_exact_probability_study(args.upstream, max_workers=max_workers)

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    result_file = out_dir / "b649-arm-d-vs-sealed-outcome-free-exact-probability-r1-result.json"
    report_file = out_dir / "b649-arm-d-vs-sealed-outcome-free-exact-probability-r1-report.md"

    result_file.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"Wrote canonical result JSON: {result_file}")

    report_content = generate_markdown_report(result)
    report_file.write_text(report_content, encoding="utf-8")
    print(f"Wrote canonical report MD: {report_file}")

    gates_obj = result.get("gates")
    if isinstance(gates_obj, dict):
        primary_label = str(cast(dict[str, object], gates_obj).get("primary_result_label", ""))
    else:
        primary_label = ""
    print(f"Completed {TASK_ID}: {primary_label}")


if __name__ == "__main__":
    main()
