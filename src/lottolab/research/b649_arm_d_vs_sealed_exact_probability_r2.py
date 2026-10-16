"""ARM_D R2 local integration entrypoint with patched exact evaluator.

This module provides an isolated R2 entrypoint for exact fair-draw
OFFICIAL_ANY_PRIZE evaluation of frozen Branch2 ARM_D portfolios against the
sealed production baseline under BIG_LOTTO_UNIFORM_FAIR_DRAW.

Key boundaries:
1. Historical ARM_D R1 code and source pin are strictly preserved and unmodified.
2. R2 explicitly identifies and binds the patched evaluator SHA256 (b411536c).
3. Pure counting, sealed input loading, and stream aggregation logic are reused
   from R1 without duplicating large algorithms or modifying R1 globals.
4. R2 source verification fails closed on any evaluator digest mismatch.
5. This is a local integration candidate only; official R2 adoption is not authorized.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping
from fractions import Fraction
from pathlib import Path
from typing import Final, cast

from lottolab.research import b649_arm_d_vs_sealed_exact_probability as r1_module
from lottolab.research.b649_arm_d_vs_sealed_exact_probability import (
    ArmDEvaluationResult,
    EvaluatedRow,
    InconclusiveGateError,
    Portfolio,
    Ticket,
    default_frozen_v1_frontier_path,
    default_sealed_input_path,
    evaluate_arm_d_stream,
    load_frozen_arm_d_archive,
    load_frozen_v1_portfolio,
    load_frozen_v1_source_identity,
    verify_frozen_v1_frontier_file,
    verify_sealed_input_file,
    verify_upstream_authority_file,
)
from lottolab.research.b649_official_any_prize_exact import (
    BIG_LOTTO_DRAW_SIZE,
    BIG_LOTTO_OUTRIGHT_MATCHES,
    BIG_LOTTO_POOL_SIZE,
    DrawMasks,
    ExactPortfolioProbability,
    all_main_draw_masks,
    evaluate_portfolio,
    validate_main_draw_masks,
)

# R2 Research Identity and Version
TASK_ID: Final = "B649_ARM_D_VS_SEALED_OUTCOME_FREE_EXACT_PROBABILITY_R2"
METHOD_VERSION: Final = "2.0.0"
MODEL_IDENTITY: Final = "BIG_LOTTO_UNIFORM_FAIR_DRAW"
EVENT_DEFINITION: Final = "OFFICIAL_ANY_PRIZE"

POOL_SIZE: Final = BIG_LOTTO_POOL_SIZE  # 49
DRAW_SIZE: Final = BIG_LOTTO_DRAW_SIZE  # 6
OUTRIGHT_MATCHES: Final = BIG_LOTTO_OUTRIGHT_MATCHES  # 3
SPECIAL_COUNT: Final = POOL_SIZE - DRAW_SIZE  # 43
TOTAL_MAIN_DRAWS: Final = math.comb(POOL_SIZE, DRAW_SIZE)  # 13,983,816
TOTAL_OUTCOME_SPACE: Final = TOTAL_MAIN_DRAWS * SPECIAL_COUNT  # 601,304,088

# Historical R1 Provenance Constants (preserved, never modified)
HISTORICAL_R1_TASK_ID: Final = r1_module.TASK_ID
HISTORICAL_R1_METHOD_VERSION: Final = r1_module.METHOD_VERSION
HISTORICAL_R1_EVALUATOR_SHA256: Final = r1_module.EVALUATOR_CONTENT_SHA256

# Pinned Artifact Authorities
SEALED_INPUT_LOCATOR: Final = r1_module.SEALED_INPUT_LOCATOR
SEALED_INPUT_SHA256: Final = r1_module.SEALED_INPUT_SHA256
FROZEN_V1_FRONTIER_LOCATOR: Final = r1_module.FROZEN_V1_FRONTIER_LOCATOR
FROZEN_V1_FRONTIER_SHA256: Final = r1_module.FROZEN_V1_FRONTIER_SHA256

BRANCH2_UPSTREAM_COMMIT: Final = r1_module.BRANCH2_UPSTREAM_COMMIT
BRANCH2_UPSTREAM_TREE: Final = r1_module.BRANCH2_UPSTREAM_TREE
BRANCH2_UPSTREAM_SHA256: Final = r1_module.BRANCH2_UPSTREAM_SHA256
PRODUCTION_AUTHORITY_COMMIT: Final = r1_module.PRODUCTION_AUTHORITY_COMMIT

# Patched Evaluator Pin (b411536c)
TARGET_EVALUATOR_COMMIT: Final = "b411536c811d18fad530019c775527a818555513"
TARGET_EVALUATOR_TREE: Final = "63ac31d403c77e5fd8fd183f98e6c85ce2481363"
TARGET_EVALUATOR_GIT_BLOB: Final = "c5b5346d1369a7ee8456610df96d2b85c19db016"
EVALUATOR_CONTENT_SHA256: Final = "ae260a9f77f341483c9f86ed5854d603138e5be070c3aaaa70bb67c3cf8b16e6"

# Exact Sealed Baseline Probabilities
EXPECTED_SEALED_PROBABILITY_K10: Final = Fraction(1095245, 3734808)
EXPECTED_SEALED_PROBABILITY_K20: Final = Fraction(44615213, 85900584)

PRIMARY_K: Final = 10
SECONDARY_K: Final = 20
EXPECTED_ARCHIVE_ROW_COUNT: Final = 1761

LABEL_SUCCESS: Final = r1_module.LABEL_SUCCESS
LABEL_FAIL: Final = r1_module.LABEL_FAIL
LABEL_TIE: Final = r1_module.LABEL_TIE
LABEL_INCONCLUSIVE: Final = r1_module.LABEL_INCONCLUSIVE


def default_evaluator_path() -> Path:
    """Resolve sibling b649_official_any_prize_exact.py file."""
    return Path(__file__).parent / "b649_official_any_prize_exact.py"


def verify_evaluator_content_sha256(evaluator_path: Path | str | None = None) -> Path:
    """Verify the b649_official_any_prize_exact.py file SHA256 matches b411 pin.

    Compares raw file bytes (not git blob SHA) and fails closed on any mismatch.
    """
    path = default_evaluator_path() if evaluator_path is None else Path(evaluator_path)
    if not path.is_file():
        raise InconclusiveGateError(f"Exact evaluator file absent: {path}")
    raw_bytes = path.read_bytes()
    computed_sha256 = hashlib.sha256(raw_bytes).hexdigest()
    if computed_sha256 != EVALUATOR_CONTENT_SHA256:
        raise InconclusiveGateError(
            f"R2 exact evaluator content SHA256 mismatch: expected {EVALUATOR_CONTENT_SHA256}, "
            f"observed {computed_sha256}"
        )
    return path


def verify_production_sealed_portfolios(
    draws: DrawMasks | None = None,
) -> dict[int, Fraction]:
    """Verify frozen v1 production baselines using the patched exact evaluator."""
    if draws is None:
        draws = all_main_draw_masks(POOL_SIZE, DRAW_SIZE)
    validated_draws = validate_main_draw_masks(draws, POOL_SIZE, DRAW_SIZE)

    res10 = evaluate_portfolio(load_frozen_v1_portfolio(PRIMARY_K), draws=validated_draws)
    if res10.official_any_prize != EXPECTED_SEALED_PROBABILITY_K10:
        raise InconclusiveGateError(
            f"R2 sealed K10 reproduction failed: expected {EXPECTED_SEALED_PROBABILITY_K10}, "
            f"observed {res10.official_any_prize}"
        )

    res20 = evaluate_portfolio(load_frozen_v1_portfolio(SECONDARY_K), draws=validated_draws)
    if res20.official_any_prize != EXPECTED_SEALED_PROBABILITY_K20:
        raise InconclusiveGateError(
            f"R2 sealed K20 reproduction failed: expected {EXPECTED_SEALED_PROBABILITY_K20}, "
            f"observed {res20.official_any_prize}"
        )

    return {
        PRIMARY_K: res10.official_any_prize,
        SECONDARY_K: res20.official_any_prize,
    }


def verify_r2_sources_and_authorities(
    input_path: Path | str | None = None,
    *,
    evaluator_path: Path | str | None = None,
    frontier_path: Path | str | None = None,
) -> Path:
    """Validate all source authorities and pins prior to scoring.

    Fails closed if evaluator, input, or frontier files are tampered, missing,
    or mismatched.
    """
    sealed_path = verify_sealed_input_file(input_path)
    verify_evaluator_content_sha256(evaluator_path)
    verify_frozen_v1_frontier_file(frontier_path)
    return sealed_path


def run_exact_probability_study_r2(
    input_path: Path | str | None = None,
    *,
    evaluator_path: Path | str | None = None,
    max_workers: int = 2,
    draws: DrawMasks | None = None,
) -> dict[str, object]:
    """Execute the frozen ARM_D vs sealed production exact-probability study under R2."""
    # Step 1: Verify authorities and evaluator pin
    sealed_path = verify_r2_sources_and_authorities(input_path, evaluator_path=evaluator_path)

    # Step 2: Validate draw space once to reuse across portfolios without per-call deduplication
    if draws is None:
        draws = all_main_draw_masks(POOL_SIZE, DRAW_SIZE)
    validated_draws = validate_main_draw_masks(draws, POOL_SIZE, DRAW_SIZE)

    # Step 3: Verify production sealed reproduction
    sealed_probabilities = verify_production_sealed_portfolios(draws=validated_draws)
    sealed_k10_prob = sealed_probabilities[PRIMARY_K]
    sealed_k20_prob = sealed_probabilities[SECONDARY_K]

    # Step 4: Load frozen archive
    target_draws, portfolios_by_k = load_frozen_arm_d_archive(sealed_path)

    # Step 5: Evaluate K10 (primary)
    k10_result = evaluate_arm_d_stream(
        PRIMARY_K,
        portfolios_by_k[PRIMARY_K],
        target_draws,
        sealed_k10_prob,
        draws=validated_draws,
        max_workers=max_workers,
    )

    # Step 6: Evaluate K20 (secondary descriptive)
    k20_result = evaluate_arm_d_stream(
        SECONDARY_K,
        portfolios_by_k[SECONDARY_K],
        target_draws,
        sealed_k20_prob,
        draws=validated_draws,
        max_workers=max_workers,
    )

    # Step 7: Determine decision gates
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

    # Step 8: Build result payload with R2 provenance
    result_payload: dict[str, object] = {
        "task_id": TASK_ID,
        "method_version": METHOD_VERSION,
        "authorities": {
            "sealed_input_locator": SEALED_INPUT_LOCATOR,
            "sealed_input_sha256": SEALED_INPUT_SHA256,
            "branch2_upstream_commit": BRANCH2_UPSTREAM_COMMIT,
            "branch2_upstream_tree": BRANCH2_UPSTREAM_TREE,
            "branch2_upstream_sha256": BRANCH2_UPSTREAM_SHA256,
            "production_authority_commit": PRODUCTION_AUTHORITY_COMMIT,
            "evaluator_content_sha256": EVALUATOR_CONTENT_SHA256,
            "target_evaluator_commit": TARGET_EVALUATOR_COMMIT,
            "target_evaluator_tree": TARGET_EVALUATOR_TREE,
            "historical_r1_task_id": HISTORICAL_R1_TASK_ID,
            "historical_r1_method_version": HISTORICAL_R1_METHOD_VERSION,
            "historical_r1_evaluator_sha256": HISTORICAL_R1_EVALUATOR_SHA256,
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
                "ARM_D portfolios is evaluated with patched evaluator b411536c and compared to "
                "the current sealed production portfolio under BIG_LOTTO_UNIFORM_FAIR_DRAW."
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
                "OFFICIAL_R2_ADOPTION",
            ],
            "outcome_fields_used": False,
            "expected_payout_included": False,
            "historical_oos_rerun": False,
        },
    }

    return result_payload


# Alias for canonical call pattern
run_exact_probability_study = run_exact_probability_study_r2


def generate_markdown_report(result: Mapping[str, object]) -> str:
    """Generate the candidate research report from R2 study results."""
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

    sealed_locator = str(authorities.get("sealed_input_locator", ""))
    sealed_sha = str(authorities.get("sealed_input_sha256", ""))
    b2_commit = str(authorities.get("branch2_upstream_commit", ""))
    b2_tree = str(authorities.get("branch2_upstream_tree", ""))
    b2_sha = str(authorities.get("branch2_upstream_sha256", ""))
    prod_commit = str(authorities.get("production_authority_commit", ""))
    eval_sha = str(authorities.get("evaluator_content_sha256", ""))
    target_eval_commit = str(authorities.get("target_evaluator_commit", ""))
    target_eval_tree = str(authorities.get("target_evaluator_tree", ""))
    hist_r1_task_id = str(authorities.get("historical_r1_task_id", ""))
    hist_r1_version = str(authorities.get("historical_r1_method_version", ""))
    hist_r1_sha = str(authorities.get("historical_r1_evaluator_sha256", ""))

    lines = [
        f"# {TASK_ID} — Report",
        "",
        f"**Status**: CANDIDATE_INTEGRATION — {primary_label}",
        "",
        "## 0. Executive Summary",
        "",
        "This candidate study evaluates the exact, outcome-free geometry probability of winning",
        "`OFFICIAL_ANY_PRIZE` under the uniform fair-draw model",
        "(`BIG_LOTTO_UNIFORM_FAIR_DRAW`, 601,304,088 finite outcomes) using patched evaluator",
        f"`{target_eval_commit[:8]}` for:",
        "- Frozen Branch2 ARM_D (MIN_OVERLAP) archive: 1,761 historical target portfolios;",
        "- Sealed production portfolios (`B649_SEALED_GEOMETRY_PORTFOLIO` 1.0.0,",
        f"  commit `{prod_commit[:7]}`).",
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
        "## 1. Identity and Provenance",
        "",
        "```text",
        f"TASK_ID:                         {TASK_ID}",
        f"METHOD_VERSION:                  {METHOD_VERSION}",
        f"MODEL_IDENTITY:                  {model['model_identity']}",
        f"TOTAL_OUTCOME_SPACE:             {model['outcome_space_exact_count']:,}",
        f"EVENT_DEFINITION:                {model['event_definition']}",
        f"EVALUATION_METHOD:               {model['evaluation_method']}",
        f"SEALED_INPUT_LOCATOR:            {sealed_locator}",
        f"SEALED_INPUT_SHA256:             {sealed_sha}",
        f"BRANCH2_UPSTREAM_COMMIT:         {b2_commit}",
        f"BRANCH2_UPSTREAM_TREE:           {b2_tree}",
        f"BRANCH2_UPSTREAM_SHA256:         {b2_sha}",
        f"PRODUCTION_AUTHORITY_COMMIT:     {prod_commit}",
        f"TARGET_EVALUATOR_COMMIT:         {target_eval_commit}",
        f"TARGET_EVALUATOR_TREE:           {target_eval_tree}",
        f"EVALUATOR_CONTENT_SHA256:        {eval_sha}",
        f"HISTORICAL_R1_TASK_ID:           {hist_r1_task_id}",
        f"HISTORICAL_R1_METHOD_VERSION:    {hist_r1_version}",
        f"HISTORICAL_R1_EVALUATOR_SHA256: {hist_r1_sha}",
        "```",
        "",
        "## 2. Methodology & Scientific Safeguards",
        "",
        "1. **Exact Finite-Outcome Enumeration**: Every probability is an exact integer fraction",
        "   over the full outcome space (`C(49, 6) * 43 = 601,304,088`).",
        "2. **Outcome-Free Boundary**: Zero historical winning numbers, hit scores, or payout",
        "   amounts were provided to or consumed by the evaluator.",
        "3. **Weighting Discipline**: All 1,761 historical rows receive equal weight (1/1761).",
        "4. **Production Oracle Reproduction**: The patched exact evaluator independently",
        "   reproduced the production sealed baseline probabilities for K10 (`1095245/3734808`)",
        "   and K20 (`44615213/85900584`).",
        "5. **Source Identity Isolation**: R1 identity and pins are preserved unmodified. R2",
        "   identifies patched evaluator b411 without altering R1 provenance.",
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
        "## 5. Non-Authorization Notice",
        "",
        "This report is a candidate integration deliverable only. Official R2 adoption,",
        "production deployment, and PR merge are NOT authorized.",
    ]
    return "\n".join(lines) + "\n"


__all__ = [
    "BRANCH2_UPSTREAM_COMMIT",
    "BRANCH2_UPSTREAM_SHA256",
    "BRANCH2_UPSTREAM_TREE",
    "DRAW_SIZE",
    "EVALUATOR_CONTENT_SHA256",
    "EVENT_DEFINITION",
    "EXPECTED_ARCHIVE_ROW_COUNT",
    "EXPECTED_SEALED_PROBABILITY_K10",
    "EXPECTED_SEALED_PROBABILITY_K20",
    "FROZEN_V1_FRONTIER_LOCATOR",
    "FROZEN_V1_FRONTIER_SHA256",
    "HISTORICAL_R1_EVALUATOR_SHA256",
    "HISTORICAL_R1_METHOD_VERSION",
    "HISTORICAL_R1_TASK_ID",
    "LABEL_FAIL",
    "LABEL_INCONCLUSIVE",
    "LABEL_SUCCESS",
    "LABEL_TIE",
    "METHOD_VERSION",
    "MODEL_IDENTITY",
    "POOL_SIZE",
    "PRIMARY_K",
    "PRODUCTION_AUTHORITY_COMMIT",
    "SEALED_INPUT_LOCATOR",
    "SEALED_INPUT_SHA256",
    "SECONDARY_K",
    "SPECIAL_COUNT",
    "TARGET_EVALUATOR_COMMIT",
    "TARGET_EVALUATOR_GIT_BLOB",
    "TARGET_EVALUATOR_TREE",
    "TASK_ID",
    "TOTAL_MAIN_DRAWS",
    "TOTAL_OUTCOME_SPACE",
    "ArmDEvaluationResult",
    "EvaluatedRow",
    "ExactPortfolioProbability",
    "InconclusiveGateError",
    "Portfolio",
    "Ticket",
    "all_main_draw_masks",
    "default_evaluator_path",
    "default_frozen_v1_frontier_path",
    "default_sealed_input_path",
    "evaluate_arm_d_stream",
    "evaluate_portfolio",
    "generate_markdown_report",
    "load_frozen_arm_d_archive",
    "load_frozen_v1_portfolio",
    "load_frozen_v1_source_identity",
    "run_exact_probability_study",
    "run_exact_probability_study_r2",
    "validate_main_draw_masks",
    "verify_evaluator_content_sha256",
    "verify_frozen_v1_frontier_file",
    "verify_production_sealed_portfolios",
    "verify_r2_sources_and_authorities",
    "verify_sealed_input_file",
    "verify_upstream_authority_file",
]
