"""Prospective confirmation of the frozen B649 ``DETERMINISTIC_MIN_OVERLAP`` candidate.

``BRANCH2_PORTFOLIO_GEOMETRY_FOUR_ARM_OOS_R1`` scored the whole available BIG_LOTTO
history, so it cannot confirm its own winner. This module is the pre-registered
prospective test of that winner (ARM_D, ``MIN_OVERLAP``) against the operational
incumbent (ARM_A, ``RAW_MAJORITY``) on draws that fall strictly after that experiment's
complete dataset and after its freeze commit.

Every rule that decides the verdict is a constant in this file and is committed by the
protocol freeze commit before any confirmatory outcome is inspected. The candidate,
incumbent, candidate pool, outcome evaluator, metric, exact McNemar test, Holm
correction, bootstrap interval and verdict gate are the frozen experiment's own
functions, imported rather than copied. Discovery results are prior evidence only: they
size the analysis horizon, they never enter a test statistic, and they are never pooled
with prospective observations.

Outcome handling is blinded below the analysis horizon. Draw metadata (number and date)
is read to count eligible draws; winning numbers of eligible draws are read only as
PRE_DRAW history for later targets; no candidate-versus-incumbent outcome is computed
until the pre-registered number of paired draws exists, and then exactly once.

Only this module writes its state, into the ``state`` section of its own protocol
document. The canonical database is opened read-only. No forecast, DB write, scheduler
action, candidate change or production activation is performed.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import math
import sys
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from functools import cache
from importlib import metadata
from pathlib import Path
from typing import Final, cast
from zoneinfo import ZoneInfo

from lottolab.application.b649_k_dpp_portfolio_selector import (
    MIN_OVERLAP_METHOD_ID,
    MIN_OVERLAP_METHOD_VERSION,
    RAW_MAJORITY_METHOD_ID,
    RAW_MAJORITY_METHOD_VERSION,
    select_deterministic_min_overlap,
    select_raw_majority_top_k,
)
from lottolab.application.b649_operational_portfolio_selector import (
    StrategyCandidate,
    Ticket,
    build_portfolio,
)
from lottolab.domain.draws import LotteryType
from lottolab.infrastructure.b649_operational_portfolio_materializer import BUCKET_SIZES
from lottolab.infrastructure.persistence.draw_schema import (
    LocalDataPaths,
    open_database,
    verify_schema_read_only,
)
from lottolab.research import b649_portfolio_geometry_four_arm_oos as frozen
from lottolab.research.b649_portfolio_geometry_four_arm_oos import (
    BOOTSTRAP_REPLICATES,
    BOOTSTRAP_SEED,
    HARNESS_DONOR_COMMIT,
    MIN_DISCORDANT_DRAWS,
    MIN_PAIRED_DRAWS,
    PRIMARY_FAMILY_SIZE,
    PRIMARY_METRIC,
    SourceDraw,
    arm_verdict,
    build_pool,
    digest,
    geometry,
    score,
    source_identity,
    summarize_pair,
)
from lottolab.research.exact_statistics import (
    binomial_pmf,
    binomial_two_sided_exact_p_value,
    binomial_two_sided_exact_power,
    holm_bonferroni_adjusted,
)
from lottolab.strategies.adapters.base import BetAdapterError, CausalDrawRow

type DrawKey = tuple[date, int]
type PoolBuilder = Callable[[tuple[CausalDrawRow, ...], str, str], tuple[StrategyCandidate, ...]]

TASK_ID: Final = "B649_MIN_OVERLAP_PROSPECTIVE_CONFIRMATION_FREEZE_R1"
PROTOCOL_ID: Final = "B649_MIN_OVERLAP_PROSPECTIVE_CONFIRMATION_R1"
PROTOCOL_SCHEMA: Final = "b649-min-overlap-prospective-confirmation-protocol-v1"
DOCUMENT_SCHEMA: Final = "b649-min-overlap-prospective-confirmation-document-v1"
STATE_SCHEMA: Final = "b649-min-overlap-prospective-confirmation-state-v1"
PROTOCOL_TIMEZONE: Final = "Asia/Taipei"

# --- upstream authority -----------------------------------------------------------------
UPSTREAM_FINAL_COMMIT: Final = "d7665ee5d00fac09fdc593908e81e54ae080f2ba"
UPSTREAM_FINAL_TREE: Final = "5a9cbff94817c82163c32f1274f7c73d19bc8426"
EXPERIMENT_TASK: Final = "BRANCH2_PORTFOLIO_GEOMETRY_FOUR_ARM_OOS_R1"
EXPERIMENT_FREEZE_COMMIT: Final = "4a8516d8cbd6d1c682e4c9ffb9c7a7528adb20b3"
EXPERIMENT_FREEZE_TREE: Final = "b1d3513654ae953055898728a6f1dd5107c40596"
EXPERIMENT_FREEZE_COMMITTED_AT: Final = "2026-09-19T14:44:49+08:00"
#: Asia/Taipei calendar date of the candidate freeze commit. A draw dated on or before it
#: could already have been drawn when the candidate was frozen, so it is never eligible.
EXPERIMENT_FREEZE_LOCAL_DATE: Final = date(2026, 9, 19)
DISCOVERY_RESULT_PATH: Final = (
    "docs/research/branch2-portfolio-geometry-four-arm-oos-r1-result.json"
)
DISCOVERY_RESULT_SHA256: Final = "af1291ad73b8e78665a7181f4403c243b245855b2d1ce24e64ee950d23294ec3"
DISCOVERY_REPORT_PATH: Final = "docs/research/branch2-portfolio-geometry-four-arm-oos-r1-report.md"
DISCOVERY_REPORT_SHA256: Final = "1b4e5398c5faac2c41db0c9d46649c10da1b83afee84ba6154361bf2ed9f65fe"

# --- complete historical discovery/evaluation dataset -----------------------------------
DISCOVERY_DRAW_COUNT: Final = 2171
DISCOVERY_FIRST_DRAW: Final = "96000001"
DISCOVERY_LAST_DRAW: Final = "115000089"
DISCOVERY_LAST_DATE: Final = date(2026, 9, 18)
DISCOVERY_LOGICAL_SHA256: Final = "43b3cc4726b5a4cbe43ff40d8d08d20aeb37837db90f0857fb344ada0579b842"
DISCOVERY_PAIRED_DRAWS: Final = 1761
DISCOVERY_LAST_KEY: Final[DrawKey] = (DISCOVERY_LAST_DATE, int(DISCOVERY_LAST_DRAW))
#: Upper draw-number bound used only to express "through this date" as a canonical key.
MAX_DRAW_NUMBER: Final = 10**15

# --- arms, budgets, metric ---------------------------------------------------------------
CANDIDATE_ARM: Final = "MIN_OVERLAP"
INCUMBENT_ARM: Final = "RAW_MAJORITY"
ARMS: Final = (INCUMBENT_ARM, CANDIDATE_ARM)
PRIMARY_K: Final = 10
SECONDARY_K: Final = 20
CONFIRMATION_K: Final = (PRIMARY_K, SECONDARY_K)
#: The frozen replay needs the incumbent's joint K5/K10/K20 buckets, i.e. 20 distinct tickets.
MIN_DISTINCT_POOL_TICKETS: Final = 20
EXCLUSION_LT20: Final = "INCUMBENT_JOINT_K5_K10_K20_UNAVAILABLE_LT20_DISTINCT_TICKETS"

# --- statistical acceptance (reused unchanged from the frozen experiment) ---------------
GATE_ALPHA: Final = 0.05
#: The frozen Holm family (3 candidate arms x K10/K20) is retained unchanged, so this gate
#: can only be as strict as the discovery gate, never looser.
GATE_FAMILY_SIZE: Final = PRIMARY_FAMILY_SIZE
FAMILY_ALPHA: Final = GATE_ALPHA / GATE_FAMILY_SIZE

# --- analysis horizon (the one distinct confirmatory adequacy rule) ---------------------
#: Discovery K10 aggregates. They size the horizon below and nothing else.
PLANNING_PAIRED_DRAWS: Final = 1761
PLANNING_DISCORDANT_DRAWS: Final = 322
PLANNING_CANDIDATE_ONLY_WINS: Final = 199
PLANNING_TARGET_POWER: Final = 0.80
PLANNING_HORIZON_STEP: Final = 50
#: Smallest multiple of 50 whose exact power at the planning inputs reaches 0.80.
ANALYSIS_HORIZON_PAIRED_DRAWS: Final = 1250

# --- statuses ----------------------------------------------------------------------------
STATUS_WAIT: Final = "WAIT_FOR_FUTURE_DRAWS"
STATUS_INSUFFICIENT: Final = "INSUFFICIENT_INDEPENDENT_DATA"
STATUS_CONFIRMED: Final = "CONFIRMED_POSITIVE_LIFT"
STATUS_FAILED: Final = "FAILED_CONFIRMATION"
STATUS_INCONCLUSIVE: Final = "INCONCLUSIVE"
STATUSES: Final = (
    STATUS_CONFIRMED,
    STATUS_FAILED,
    STATUS_INCONCLUSIVE,
    STATUS_INSUFFICIENT,
    STATUS_WAIT,
)
#: A verdict computed on the frozen analysis set; it cannot change with later draws.
TERMINAL_STATUSES: Final = (STATUS_CONFIRMED, STATUS_FAILED, STATUS_INCONCLUSIVE)

ELIGIBLE: Final = "ELIGIBLE"
REASON_DISCOVERY: Final = "DISCOVERY_DATASET"
REASON_NOT_AFTER_FREEZE: Final = "OUTCOME_NOT_AFTER_CANDIDATE_FREEZE"
REASON_FUTURE: Final = "FUTURE_DATED"
BLINDED: Final = "NOT_SCORED_BLINDED_BELOW_ANALYSIS_HORIZON"


def _stream(strategy_id: str, native_ticket_count: int) -> dict[str, object]:
    return {
        "strategy_id": strategy_id,
        "version": "v0.1",
        "native_ticket_count": native_ticket_count,
    }


def _checkpoint(
    target_draw: str,
    target_date: str,
    history_count: int,
    candidate_count: int,
    *,
    history: str,
    pool: str,
    k10: tuple[str, str],
    k20: tuple[str, str],
) -> dict[str, object]:
    return {
        "target_draw": target_draw,
        "target_date": target_date,
        "history_count": history_count,
        "history_sha256": history,
        "pool_sha256": pool,
        "candidate_count": candidate_count,
        "portfolio_sha256": {
            "10": {INCUMBENT_ARM: k10[0], CANDIDATE_ARM: k10[1]},
            "20": {INCUMBENT_ARM: k20[0], CANDIDATE_ARM: k20[1]},
        },
    }


#: The eleven enabled streams that build the shared candidate pool, in pool order.
STREAM_IDENTITIES: Final[list[dict[str, object]]] = [
    _stream("b649_new_horizon_minimax_disagreement_r1", 2),
    _stream("biglotto_social_wisdom_anti_popularity", 1),
    _stream("biglotto_deviation_2bet", 1),
    _stream("legacy_biglotto__graph_predictor__cd70713a5709", 1),
    _stream("legacy_biglotto__pure_cold_predict__9e89f2b41add", 1),
    _stream("legacy_biglotto__hpsb_optimizer__cf5cd7d971e8", 1),
    _stream("legacy_biglotto__test_asm__d39a233a4c75", 3),
    _stream("legacy_biglotto__test_ces__78d17c530ab8", 3),
    _stream("legacy_biglotto__test_ecp__c9d5ac6decdd", 3),
    _stream("legacy_biglotto__test_mwsc__ba37643d6a3b", 3),
    _stream("legacy_biglotto__test_tme__f3bb5106dfe3", 3),
]

#: Sealed discovery outputs (from the committed discovery result) that the running code must
#: reproduce byte for byte from the discovery prefix: pool, history and both arms' portfolios.
REPRODUCTION_CHECKPOINTS: Final[list[dict[str, object]]] = [
    _checkpoint(
        "97000098",
        "2008-12-05",
        201,
        21,
        history="e6966715c093284d6fb57480fdf1e74d6f0339cf2f416530ed8a820f84e4c9d0",
        pool="46df05426bbd457219c39fbb8776594edbb7e145758e7d244340bea014a5dcf7",
        k10=(
            "86d328455d6677aba643990a7032cd00f55c093c2a439bfe14f4179f9cec7a5d",
            "c976c4f9b24f3bfe55f36e902c74b78592b7ab75ddbba3f4b7254a7176c0e1e3",
        ),
        k20=(
            "8c4f6490d961e4da48f29e3b07fbf8f7bee0d36e57d4a2e8b6e37d40ed5e9578",
            "b2a8abf7c9077b6854e5337b2407ea4e2e824e91562b811968d7f5b3fdf2eba4",
        ),
    ),
    _checkpoint(
        "107000047",
        "2018-05-29",
        1216,
        22,
        history="e9c44e1a3d5ae9508b45a128381bdca21fd5a1641338e3095fb36e9f55bdfb33",
        pool="c3e8ee37202731ab6113c676c754b7436330c508620d48c5b1002f115c48f2ad",
        k10=(
            "c46af4a7c4826eb02ff3ebd9b6760815d04592c77e7a030c03dbf72331e6e904",
            "dd72f804608cf204ce2eafd2e43723bcff339665a28d034c4516fb01215a8aae",
        ),
        k20=(
            "5ce07234880cf1939d0f682b2d3056736e889b2a6dcb57dabe0f5a4f102ae0cb",
            "c4714b8944ca1f796748b63e0b5c9deb198988a70794545f300bc87ec6275428",
        ),
    ),
    _checkpoint(
        "115000077",
        "2026-08-07",
        2158,
        20,
        history="b707aebf526470e34491dbe6ef961968e5681286b4a26208cebf41206a54e338",
        pool="e24dbef93438ee08637bebb90cb56185a8bfcc2a7674dadaad2428a4e89e8b13",
        k10=(
            "a6d14d5bd38af84a9934aae562cf8ba3424d9ac17e6745b0b8ca9d77410b9aaf",
            "b06a61aa9b92e58aee4eda8e7a4de07048d0ae747b996207b87bd02ee77dea4f",
        ),
        k20=(
            "d2e9636bc874904988c83547346e4470cfbf3c53d51dae0ca38a0498ed9e181d",
            "61146b0ef1203702a29e33ad26f63b83cd1e204d9e61759ac71d55be7fbe1895",
        ),
    ),
    _checkpoint(
        "115000088",
        "2026-09-15",
        2169,
        22,
        history="e42da779c7fb4300c1f1ab54587768fc2ae0c296b1786d059ec8704d08f062dc",
        pool="3666f7f46574519135fd9b2350f0f7f3e2ac8811083b7a3697d4771a76b42767",
        k10=(
            "095566f68558b590885eba66dd9c0b7206be5135b1aa28ca5a0cc147b6a83bc8",
            "c045c7f1b0d7134572d191983ee3b29d694eabd5b23f1d5c32713b61d6c1f68c",
        ),
        k20=(
            "2271ce0f930136e1a3e995fac3dc1a35e99e6f05a7cc21163f459ca1fcf1535c",
            "a883cb7347695b2d5f48280c64cdb53bb6e189154b7c911ba10e4f29a27766f0",
        ),
    ),
    _checkpoint(
        "115000089",
        "2026-09-18",
        2170,
        21,
        history="d2820b36e40b20e3aad99772274e566e03a561546aec46e72acfe3a1c4578fdb",
        pool="924b4561963cc26c78594e0abd0f784c6eeb11f5cb6394de8072748ca7481271",
        k10=(
            "cd6e7e173eed734cd0d211030ef299119afaf4f3ff30c1c36cb14462a70d2db1",
            "c788ad75af0b28fa30070e86d299ad8dee1904f363e0a0784e064caa42df32ba",
        ),
        k20=(
            "4caf4ee8dde18c173b5528056dc9ed3324301be0a2310f7b0964947bc45d5107",
            "de49b9117cf9b3dad0b28a7b78c523bb645c8c4fae63588e9325e8210efbf166",
        ),
    ),
]

#: Byte pins of the modules that ARE the candidate, incumbent and frozen replay semantics.
#: Files shared with unrelated lotteries (prize evaluation, statistics) are pinned by
#: behaviour instead, below, so unrelated additions cannot trip the confirmation.
SOURCE_SHA256_BY_MODULE: Final[dict[str, str]] = {
    "lottolab.application.b649_k_dpp_portfolio_selector": (
        "fb96b7f481d08dbea55b6dee42143fed5fa7cfe63055e1b581e92f3befb82576"
    ),
    "lottolab.application.b649_operational_portfolio_selector": (
        "ba4c666d3419cbea07e4582ee48710f1528f3c74a794e745610780a35ae11bfd"
    ),
    "lottolab.research.b649_portfolio_geometry_four_arm_oos": (
        "2754cc9765e83df63ec11da2fc69665393fa5f804ca78bcc621c78c880b7d375"
    ),
}

#: Winning draw 1-2-3-4-5-6 with special number 7; tickets carry no predicted special number.
METRIC_KNOWN_ANSWER_OUTCOME: Final[dict[str, object]] = {
    "winning_main_numbers": [1, 2, 3, 4, 5, 6],
    "winning_special_number": 7,
}
METRIC_KNOWN_ANSWERS: Final[list[dict[str, object]]] = [
    {"ticket": [1, 2, 3, 4, 5, 6], "zone1_hits": 6, "is_winner": True},
    {"ticket": [1, 2, 3, 4, 5, 7], "zone1_hits": 5, "is_winner": True},
    {"ticket": [1, 2, 3, 4, 5, 8], "zone1_hits": 5, "is_winner": True},
    {"ticket": [1, 2, 3, 4, 7, 8], "zone1_hits": 4, "is_winner": True},
    {"ticket": [1, 2, 3, 4, 8, 9], "zone1_hits": 4, "is_winner": True},
    {"ticket": [1, 2, 3, 7, 8, 9], "zone1_hits": 3, "is_winner": True},
    {"ticket": [1, 2, 3, 8, 9, 10], "zone1_hits": 3, "is_winner": True},
    {"ticket": [1, 2, 7, 8, 9, 10], "zone1_hits": 2, "is_winner": True},
    {"ticket": [1, 2, 8, 9, 10, 11], "zone1_hits": 2, "is_winner": False},
    {"ticket": [1, 7, 8, 9, 10, 11], "zone1_hits": 1, "is_winner": False},
    {"ticket": [1, 8, 9, 10, 11, 12], "zone1_hits": 1, "is_winner": False},
    {"ticket": [8, 9, 10, 11, 12, 13], "zone1_hits": 0, "is_winner": False},
]

#: Independent math.comb references for the exact two-sided McNemar test and Holm step-down.
STATISTICS_KNOWN_ANSWERS: Final[dict[str, object]] = {
    "exact_two_sided_binomial": [
        {"n": 10, "k": 9, "p": 0.021484375},
        {"n": 10, "k": 10, "p": 0.001953125},
        {"n": 20, "k": 15, "p": 0.04138946533203125},
        {"n": 30, "k": 25, "p": 0.00032491423189640045},
        {"n": 100, "k": 61, "p": 0.03520020021770481},
        {"n": 322, "k": 199, "p": 2.695687773116827e-05},
    ],
    "holm": [{"p_values": [0.01, 0.04, 0.03], "adjusted": [0.03, 0.06, 0.06]}],
    "relative_tolerance": 1e-9,
}

PROTOCOL: Final[dict[str, object]] = {
    "schema": PROTOCOL_SCHEMA,
    "protocol_id": PROTOCOL_ID,
    "task_id": TASK_ID,
    "objective": "MAXIMIZE_VERIFIED_OUT_OF_SAMPLE_PREDICTION_SUCCESS_RATE",
    "question": (
        "Does DETERMINISTIC_MIN_OVERLAP raise the per-draw probability of at least one "
        "official winning ticket over the operational incumbent on BIG_LOTTO draws that "
        "neither the frozen experiment nor its freeze commit could have seen?"
    ),
    "upstream": {
        "final_commit": UPSTREAM_FINAL_COMMIT,
        "final_tree": UPSTREAM_FINAL_TREE,
        "experiment_task": EXPERIMENT_TASK,
        "experiment_freeze_commit": EXPERIMENT_FREEZE_COMMIT,
        "experiment_freeze_tree": EXPERIMENT_FREEZE_TREE,
        "experiment_freeze_committed_at": EXPERIMENT_FREEZE_COMMITTED_AT,
        "experiment_freeze_local_date": EXPERIMENT_FREEZE_LOCAL_DATE.isoformat(),
        "harness_donor_commit": HARNESS_DONOR_COMMIT,
        "discovery_result_path": DISCOVERY_RESULT_PATH,
        "discovery_result_sha256": DISCOVERY_RESULT_SHA256,
        "discovery_report_path": DISCOVERY_REPORT_PATH,
        "discovery_report_sha256": DISCOVERY_REPORT_SHA256,
    },
    "candidate": {
        "arm": CANDIDATE_ARM,
        "method_id": MIN_OVERLAP_METHOD_ID,
        "method_version": MIN_OVERLAP_METHOD_VERSION,
        "selector": (
            "lottolab.application.b649_k_dpp_portfolio_selector.select_deterministic_min_overlap"
        ),
        "construction": (
            "Seed the portfolio with candidate_pool_index 0, then repeatedly append the "
            "not-yet-selected candidate minimising (max overlap with the selected set ASC, "
            "summed overlap with the selected set ASC, candidate_pool_index ASC); the K "
            "tickets are reported in ascending candidate_pool_index order."
        ),
        "seed": None,
        "tunable_parameters": [],
        "consumed_unchanged_from": EXPERIMENT_FREEZE_COMMIT,
        "outcome_tuning": "NONE",
    },
    "incumbent": {
        "arm": INCUMBENT_ARM,
        "method_id": RAW_MAJORITY_METHOD_ID,
        "method_version": RAW_MAJORITY_METHOD_VERSION,
        "selector": (
            "lottolab.application.b649_k_dpp_portfolio_selector.select_raw_majority_top_k"
        ),
        "operational_equivalence": (
            "At every draw and K the arm's tickets are asserted equal to "
            "build_portfolio(pool, {}, BUCKET_SIZES)[K]; the run aborts with "
            "INCUMBENT_ARM_NOT_OPERATIONAL_SELECTOR on any difference."
        ),
        "quality_by_strategy": {},
        "bucket_sizes": list(BUCKET_SIZES),
        "substitution": "FORBIDDEN",
    },
    "candidate_pool": {
        "builder": "lottolab.research.b649_portfolio_geometry_four_arm_oos.build_pool",
        "streams": STREAM_IDENTITIES,
        "min_distinct_tickets": MIN_DISTINCT_POOL_TICKETS,
        "change": "FORBIDDEN",
    },
    "identity_attestation": {
        "source_sha256_by_module": SOURCE_SHA256_BY_MODULE,
        "metric_known_answer_outcome": METRIC_KNOWN_ANSWER_OUTCOME,
        "metric_known_answers": METRIC_KNOWN_ANSWERS,
        "statistics_known_answers": STATISTICS_KNOWN_ANSWERS,
        "reproduction_checkpoints": REPRODUCTION_CHECKPOINTS,
        "on_mismatch": "FAIL_CLOSED_NO_VERDICT",
    },
    "primary": {
        "k": PRIMARY_K,
        "metric": PRIMARY_METRIC,
        "per_draw_indicator": "official_any_prize",
        "definition": (
            "1 when at least one of the K tickets is an official winner under "
            "evaluate_big_lotto_ticket for that draw, otherwise 0; the metric is the per-draw "
            "probability of at least one official winning ticket"
        ),
        "contrast": "MIN_OVERLAP minus RAW_MAJORITY on the same draw and the same K",
        "gates_verdict": True,
    },
    "secondary": {
        "k": SECONDARY_K,
        "metric": PRIMARY_METRIC,
        "gates_verdict": False,
        "reporting": (
            "Exact McNemar p-value and nominal intervals, outside the gate family, as K5 was "
            "in the discovery; it can neither confirm nor veto."
        ),
        "caveat": (
            "LOW_DECISION_LEVERAGE_FORCED_SELECTION: a draw whose pool holds exactly 20 "
            "distinct tickets admits one portfolio, so both arms are identical there by "
            "construction (608 of 1,761 discovery draws)."
        ),
    },
    "not_a_confirmation_target": {"k": [5], "reason": "diagnostic only in the frozen experiment"},
    "discovery_boundary": {
        "database_draw_count": DISCOVERY_DRAW_COUNT,
        "first_draw": DISCOVERY_FIRST_DRAW,
        "last_draw": DISCOVERY_LAST_DRAW,
        "last_draw_date": DISCOVERY_LAST_DATE.isoformat(),
        "logical_sha256": DISCOVERY_LOGICAL_SHA256,
        "logical_sha256_definition": (
            "digest() of [asdict(SourceDraw)] ordered by (draw_date, int(draw_number)): "
            "canonical JSON, sorted keys, compact separators, one trailing newline, SHA-256"
        ),
        "paired_draws_scored": DISCOVERY_PAIRED_DRAWS,
        "canonical_order": "(draw_date, int(draw_number)) ascending; never draw_number as text",
    },
    "eligibility": {
        "lottery_type": LotteryType.BIG_LOTTO.value,
        "rules": [
            "E1: canonical key (draw_date, int(draw_number)) is strictly greater than "
            f"({DISCOVERY_LAST_DATE.isoformat()}, {DISCOVERY_LAST_DRAW})",
            f"E2: draw_date is strictly later than {EXPERIMENT_FREEZE_LOCAL_DATE.isoformat()}, "
            "the Asia/Taipei date of the candidate freeze commit, so no outcome pre-dates it",
            "E3: draw_date is not later than the evaluation as-of date",
            "E4: exactly 2,171 rows precede the boundary and their logical SHA-256 equals the "
            "pinned value, otherwise the run fails closed",
            "E5: the outcome record is valid (six distinct main numbers and one special number "
            "outside them, all within 1..49), otherwise the run fails closed",
        ],
        "history_for_each_target": (
            "the discovery dataset plus every later draw in canonical order before the target, "
            "including later draws that are not themselves eligible; never the target or "
            "anything after it"
        ),
        "confirmatory_start_draw": (
            "the first eligible draw in canonical order; resolved after the protocol freeze by "
            "a metadata-only read, because no post-discovery draw was read to write this protocol"
        ),
        "never_used": [
            "recent windows of discovery data",
            "alternate windows",
            "bootstrap resampling of discovery rows",
            "re-scoring any discovery row",
        ],
    },
    "pairing": {
        "unit": "target draw",
        "arms": list(ARMS),
        "k": list(CONFIRMATION_K),
        "rule": (
            "A target is paired only when the shared pool holds at least 20 distinct tickets and "
            "both arms are FEASIBLE at K10 and K20; the same draws carry K10 and K20, in "
            "chronological order."
        ),
        "technical_exclusions": [
            EXCLUSION_LT20,
            "ARM_INFEASIBLE_K<k>",
            "STREAM_UNAVAILABLE:<reason>",
        ],
        "exclusions_depend_on_outcome": False,
    },
    "statistics": {
        "reused_from": f"{EXPERIMENT_TASK} (Lane-2 harness donor {HARNESS_DONOR_COMMIT})",
        "test": (
            "exact two-sided McNemar on paired any-prize discordant draws: "
            "binomial_two_sided_exact_p_value(b + c, b, 0.5)"
        ),
        "correction": (
            "Holm over the frozen family of 6 (3 candidate arms x K10/K20), retained unchanged; "
            "only ARM_D at K10 is tested, so its adjusted p-value is min(1, 6 x p)"
        ),
        "gate_alpha": GATE_ALPHA,
        "gate_family_size": GATE_FAMILY_SIZE,
        "interval": (
            "paired-draw bootstrap percentile interval, "
            f"seed {BOOTSTRAP_SEED}, {BOOTSTRAP_REPLICATES} replicates, alpha 0.05/6 (99.17%)"
        ),
        "nominal_interval": "the same bootstrap at alpha 0.05 (95%)",
        "gate": (
            "frozen arm_verdict(): Holm-adjusted p < 0.05 and the familywise interval lower "
            "bound > 0, with both adequacy floors met (POSITIVE_LIFT_VALIDATED)"
        ),
        "alternative": "two-sided; no one-sided test",
        "serial_dependence": "IID intervals do not establish temporal independence (frozen caveat)",
        "prior_evidence_pooling": "FORBIDDEN",
    },
    "adequacy": {
        "rule": "SINGLE_FINAL_ANALYSIS_AT_FIXED_PAIRED_DRAW_HORIZON",
        "horizon_paired_draws": ANALYSIS_HORIZON_PAIRED_DRAWS,
        "analysis_set": (
            f"the first {ANALYSIS_HORIZON_PAIRED_DRAWS} paired draws in chronological order; "
            "later draws are never added, so the frozen test is applied exactly once and the "
            "analysis cannot be extended, repeated on a longer sample, or stopped at a lucky look"
        ),
        "floors_retained": {
            "min_paired_draws": MIN_PAIRED_DRAWS,
            "min_primary_discordant_draws": MIN_DISCORDANT_DRAWS,
        },
        "why_a_distinct_rule": (
            "The frozen floors only make the test computable. Re-running an exact test as draws "
            "accumulate and stopping at the first p below the gate inflates the false "
            "confirmation rate, so the horizon fixes when the single analysis happens."
        ),
        "planning": {
            "source": "discovery K10 aggregates, used only to size the horizon",
            "paired_draws": PLANNING_PAIRED_DRAWS,
            "discordant_draws": PLANNING_DISCORDANT_DRAWS,
            "candidate_only_wins": PLANNING_CANDIDATE_ONLY_WINS,
            "test": "exact two-sided McNemar at the gate alpha 0.05/6",
            "target_power": PLANNING_TARGET_POWER,
            "horizon_step": PLANNING_HORIZON_STEP,
            "rule": "smallest multiple of the step whose exact power reaches the target",
        },
        "below_horizon": "no outcome is scored; only outcome-free diagnostics are reported",
    },
    "verdict": {
        "statuses": list(STATUSES),
        "rules": [
            f"no eligible draw -> {STATUS_WAIT}",
            f"eligible draws exist but fewer than {ANALYSIS_HORIZON_PAIRED_DRAWS} are paired -> "
            f"{STATUS_INSUFFICIENT} (outcomes not scored)",
            f"{ANALYSIS_HORIZON_PAIRED_DRAWS} paired draws but fewer than "
            f"{MIN_DISCORDANT_DRAWS} K10 discordant draws -> {STATUS_INSUFFICIENT}",
            f"frozen gate POSITIVE_LIFT_VALIDATED at K10 -> {STATUS_CONFIRMED}",
            f"gate not met and K10 absolute delta <= 0 -> {STATUS_FAILED}",
            f"gate not met and K10 absolute delta > 0 -> {STATUS_INCONCLUSIVE}",
        ],
        "k20": "reported, never gating; it can neither rescue nor veto the K10 verdict",
        "ready_for_branch6_adoption": f"YES only for {STATUS_CONFIRMED}, otherwise NO",
    },
    "outcome_handling": {
        "protocol_committed_before_confirmatory_outcome_inspection": True,
        "interim_policy": (
            "BLINDED_UNTIL_ANALYSIS_HORIZON: draw metadata is read to count eligible draws; "
            "winning numbers of eligible draws are read only as PRE_DRAW history for later "
            "targets; no candidate-versus-incumbent outcome is computed below the horizon"
        ),
        "selection_sealing": (
            "every paired draw's portfolios are selected and hashed (sealed_selection_sha256) "
            "before any outcome comparison"
        ),
        "selection_provenance": (
            "DETERMINISTIC_RECONSTRUCTION_FROM_PRE_DRAW_PREFIX; not a contemporaneously "
            "persisted PRE_DRAW archive"
        ),
    },
    "prior_evidence": {
        "role": "DISCOVERY_PRIOR_EVIDENCE_ONLY",
        "pooled_with_prospective_observations": False,
        "k10": {
            "paired_draws": 1761,
            "incumbent_wins": 423,
            "candidate_wins": 499,
            "absolute_delta_pp": 4.3157,
            "discordant_draws": 322,
            "holm_adjusted_p": 0.0001617412663870052,
        },
        "k20": {
            "paired_draws": 1761,
            "incumbent_wins": 701,
            "candidate_wins": 721,
            "absolute_delta_pp": 1.1357,
            "discordant_draws": 30,
            "holm_adjusted_p": 0.0016245711594819955,
        },
    },
    "out_of_scope": [
        "K5 as a confirmation target",
        "an expected-payout metric",
        "ARM_B SEEDED_RANDOM_K and ARM_C KDPP",
        "any change to the candidate, incumbent, pool, metric or statistics",
        "Branch6 adoption or production activation",
        "database, scheduler or runtime writes",
    ],
    "amendment_policy": (
        "No field may change once any confirmatory outcome has been scored. A change before "
        "that requires a new protocol_id and a new freeze commit."
    ),
}
PROTOCOL_SHA256: Final = digest(PROTOCOL)

FREEZE_STATE: Final[dict[str, object]] = {
    "state_schema": STATE_SCHEMA,
    "confirmation_status": None,
    "status_reason": "NOT_EVALUATED_AT_PROTOCOL_FREEZE",
    "confirmatory_outcomes_inspected": False,
    "ready_for_branch6_adoption": False,
}


# --- keys and eligibility ----------------------------------------------------------------
def draw_key(draw_number: str, draw_date: str) -> DrawKey:
    return date.fromisoformat(draw_date), int(draw_number)


def classify_key(key: DrawKey, *, as_of: date) -> str:
    """``ELIGIBLE``, or the first eligibility rule (E1-E3) that the draw key fails."""

    if key <= DISCOVERY_LAST_KEY:
        return REASON_DISCOVERY
    if key[0] <= EXPERIMENT_FREEZE_LOCAL_DATE:
        return REASON_NOT_AFTER_FREEZE
    if key[0] > as_of:
        return REASON_FUTURE
    return ELIGIBLE


@dataclass(frozen=True, slots=True)
class DrawIndexRow:
    """Draw identity only: what the metadata-only eligibility count reads."""

    draw_number: str
    draw_date: str

    @property
    def key(self) -> DrawKey:
        return draw_key(self.draw_number, self.draw_date)


def eligibility_summary(index: Sequence[DrawIndexRow], as_of: date) -> dict[str, object]:
    """Outcome-free accounting of every BIG_LOTTO row against the frozen boundary."""

    reasons = Counter(classify_key(row.key, as_of=as_of) for row in index)
    eligible = [row for row in index if classify_key(row.key, as_of=as_of) == ELIGIBLE]
    if reasons[REASON_DISCOVERY] != DISCOVERY_DRAW_COUNT:
        raise ValueError(f"DISCOVERY_PREFIX_MISMATCH:INDEX_COUNT:{reasons[REASON_DISCOVERY]}")
    first = eligible[0] if eligible else None
    last = eligible[-1] if eligible else None
    return {
        "database_big_lotto_draw_count": len(index),
        "discovery_dataset_draw_count": reasons[REASON_DISCOVERY],
        "post_discovery_draw_count": len(index) - reasons[REASON_DISCOVERY],
        "eligible_draw_count": len(eligible),
        "excluded_outcome_not_after_candidate_freeze": reasons[REASON_NOT_AFTER_FREEZE],
        "excluded_future_dated": reasons[REASON_FUTURE],
        "confirmatory_start_draw": None if first is None else first.draw_number,
        "confirmatory_start_draw_date": None if first is None else first.draw_date,
        "confirmatory_start_status": "RESOLVED" if first else "NOT_YET_DRAWN",
        "last_eligible_draw": None if last is None else last.draw_number,
        "last_eligible_draw_date": None if last is None else last.draw_date,
    }


# --- read-only canonical database access -------------------------------------------------
#: Draw identity only. This is the only query run before the analysis horizon is reached
#: over draws after the boundary, and it never selects an outcome column.
DRAW_INDEX_SQL: Final = (
    "SELECT draw_number, draw_date FROM draws WHERE lottery_type = ? "
    "ORDER BY draw_date, CAST(draw_number AS INTEGER)"
)
DRAW_SOURCE_SQL: Final = (
    "SELECT draw_number, draw_date, main_numbers_json, special_numbers_json, "
    "normalized_record_hash FROM draws WHERE lottery_type = ?"
)
_AFTER_CLAUSE: Final = (
    " AND (draw_date > ? OR (draw_date = ? AND CAST(draw_number AS INTEGER) > ?))"
)
_THROUGH_CLAUSE: Final = (
    " AND (draw_date < ? OR (draw_date = ? AND CAST(draw_number AS INTEGER) <= ?))"
)
_ORDER_CLAUSE: Final = " ORDER BY draw_date, CAST(draw_number AS INTEGER)"


def _fetch(database: Path, sql: str, params: Sequence[object]) -> list[tuple[object, ...]]:
    paths = LocalDataPaths(data_directory=database.parent, database=database)
    if not verify_schema_read_only(paths):
        raise ValueError("CANONICAL_OUTCOME_SCHEMA_UNAVAILABLE")
    with open_database(paths, read_only=True) as connection:
        connection.execute("PRAGMA query_only = ON")
        connection.execute("BEGIN")
        return connection.execute(sql, tuple(params)).fetchall()


def load_draw_index(database: Path) -> tuple[DrawIndexRow, ...]:
    """Metadata-only read of every BIG_LOTTO draw identity, in canonical order."""

    rows = _fetch(database, DRAW_INDEX_SQL, (LotteryType.BIG_LOTTO.value,))
    index = tuple(DrawIndexRow(str(number), str(day)) for number, day in rows)
    keys = [row.key for row in index]
    if keys != sorted(set(keys)) or len({row.draw_number for row in index}) != len(index):
        raise ValueError("CANONICAL_DRAW_ORDER_OR_DUPLICATE_IDENTITY")
    return index


def load_source_draws(
    database: Path, *, after: DrawKey | None = None, through: DrawKey | None = None
) -> tuple[SourceDraw, ...]:
    """The frozen ``load_draws`` read and validation, bounded by canonical keys in SQL.

    ``after`` and ``through`` are applied in the query, so rows outside the bounds are never
    returned to the process. With neither bound the result equals ``frozen.load_draws``.
    """

    sql = DRAW_SOURCE_SQL
    params: list[object] = [LotteryType.BIG_LOTTO.value]
    if after is not None:
        sql += _AFTER_CLAUSE
        params += [after[0].isoformat(), after[0].isoformat(), after[1]]
    if through is not None:
        sql += _THROUGH_CLAUSE
        params += [through[0].isoformat(), through[0].isoformat(), through[1]]
    sql += _ORDER_CLAUSE
    draws: list[SourceDraw] = []
    for number, day, main_json, special_json, record_hash in _fetch(database, sql, params):
        main = cast(list[int], json.loads(str(main_json)))
        special = cast(list[int], json.loads(str(special_json)))
        if (
            len(main) != 6
            or len(set(main)) != 6
            or len(special) != 1
            or any(type(n) is not int or not 1 <= n <= 49 for n in main + special)
            or special[0] in main
        ):
            raise ValueError("INVALID_CANONICAL_OUTCOME")
        draws.append(SourceDraw(str(number), str(day), tuple(main), special[0], str(record_hash)))
    keys = [draw.key for draw in draws]
    if keys != sorted(set(keys)) or len({draw.draw_number for draw in draws}) != len(draws):
        raise ValueError("CANONICAL_DRAW_ORDER_OR_DUPLICATE_IDENTITY")
    return tuple(draws)


def verify_discovery_prefix(prefix: Sequence[SourceDraw]) -> str:
    """Prove the PRE_DRAW history the discovery used is unchanged; return its logical SHA-256."""

    if len(prefix) != DISCOVERY_DRAW_COUNT:
        raise ValueError(f"DISCOVERY_PREFIX_MISMATCH:COUNT:{len(prefix)}")
    if (prefix[0].draw_number, prefix[-1].draw_number, prefix[-1].draw_date) != (
        DISCOVERY_FIRST_DRAW,
        DISCOVERY_LAST_DRAW,
        DISCOVERY_LAST_DATE.isoformat(),
    ):
        raise ValueError("DISCOVERY_PREFIX_MISMATCH:BOUNDARY")
    logical = digest([asdict(draw) for draw in prefix])
    if logical != DISCOVERY_LOGICAL_SHA256:
        raise ValueError("DISCOVERY_PREFIX_MISMATCH:LOGICAL_SHA256")
    return logical


# --- sealing: outcome-free selection of both arms ----------------------------------------
@dataclass(frozen=True, slots=True)
class SealedDraw:
    """One paired target: pool, history and both arms' portfolios, fixed before scoring."""

    target: SourceDraw
    cutoff_draw: str
    cutoff_date: str
    history_count: int
    history_sha256: str
    pool_sha256: str
    candidate_count: int
    tickets: Mapping[int, Mapping[str, tuple[Ticket, ...]]]
    portfolio_sha256: Mapping[int, Mapping[str, str]]


@dataclass(frozen=True, slots=True)
class Exclusion:
    """A target dropped for a reason that cannot depend on whether any arm won."""

    target_draw: str
    target_date: str
    reason: str


@dataclass(frozen=True, slots=True)
class SealedWindow:
    sealed: tuple[SealedDraw, ...]
    exclusions: tuple[Exclusion, ...]
    eligible_seen: int
    eligible_unprocessed: int
    determinism_verified: bool


def seal_target(
    history: Sequence[CausalDrawRow], target: SourceDraw, pool_builder: PoolBuilder
) -> SealedDraw | Exclusion:
    """Select both arms for one target from strictly earlier rows only.

    Mirrors the frozen replay's per-draw sequence and reads no outcome of the target.
    """

    rows = tuple(history)
    if not rows or draw_key(rows[-1].draw, rows[-1].date) >= target.key:
        raise ValueError("PRE_DRAW_CUTOFF_VIOLATION")
    try:
        pool = pool_builder(rows, target.draw_number, target.draw_date)
    except BetAdapterError as exc:
        return Exclusion(target.draw_number, target.draw_date, f"STREAM_UNAVAILABLE:{exc}")
    distinct = {tuple(sorted(ticket)) for stream in pool for ticket in stream.tickets}
    if len(distinct) < MIN_DISTINCT_POOL_TICKETS:
        return Exclusion(target.draw_number, target.draw_date, EXCLUSION_LT20)
    fingerprint = digest([asdict(row) for row in rows])
    identity = source_identity(rows, target, fingerprint)
    incumbent_buckets = build_portfolio(pool, {}, bucket_sizes=BUCKET_SIZES)
    tickets: dict[int, dict[str, tuple[Ticket, ...]]] = {}
    hashes: dict[int, dict[str, str]] = {}
    candidate_count = 0
    for k in CONFIRMATION_K:
        selections = {
            INCUMBENT_ARM: select_raw_majority_top_k(pool, source=identity, k=k),
            CANDIDATE_ARM: select_deterministic_min_overlap(pool, source=identity, k=k),
        }
        if any(s.feasibility_status != "FEASIBLE" for s in selections.values()):
            return Exclusion(target.draw_number, target.draw_date, f"ARM_INFEASIBLE_K{k}")
        incumbent = selections[INCUMBENT_ARM]
        if list(incumbent.tickets) != list(incumbent_buckets[k]):
            raise ValueError("INCUMBENT_ARM_NOT_OPERATIONAL_SELECTOR")
        candidate_count = incumbent.candidate_count
        tickets[k] = {arm: selection.tickets for arm, selection in selections.items()}
        hashes[k] = {}
        for arm, selection in selections.items():
            if selection.portfolio_sha256 is None:
                raise ValueError("FEASIBLE_SELECTION_WITHOUT_PORTFOLIO_SHA256")
            hashes[k][arm] = selection.portfolio_sha256
    return SealedDraw(
        target=target,
        cutoff_draw=rows[-1].draw,
        cutoff_date=rows[-1].date,
        history_count=len(rows),
        history_sha256=fingerprint,
        pool_sha256=digest([(s.strategy_id, s.tickets) for s in pool]),
        candidate_count=candidate_count,
        tickets=tickets,
        portfolio_sha256=hashes,
    )


def reproduce(
    draw: SealedDraw, history: Sequence[CausalDrawRow], pool_builder: PoolBuilder
) -> None:
    """Re-seal one target from the same history and require an identical result."""

    if seal_target(history[: draw.history_count], draw.target, pool_builder) != draw:
        raise ValueError("NONDETERMINISTIC_CANDIDATE_REPRODUCTION")


def seal_window(
    prefix: Sequence[SourceDraw],
    targets: Sequence[SourceDraw],
    *,
    is_eligible: Callable[[SourceDraw], bool],
    horizon: int,
    pool_builder: PoolBuilder,
) -> SealedWindow:
    """Seal eligible targets in canonical order until ``horizon`` paired draws exist.

    Every target, eligible or not, joins the history after it is processed, so a later
    target sees exactly the draws that preceded it and never itself.
    """

    history: list[CausalDrawRow] = [draw.history_row() for draw in prefix]
    sealed: list[SealedDraw] = []
    exclusions: list[Exclusion] = []
    eligible_seen = 0
    unprocessed = 0
    for position, target in enumerate(targets):
        if len(sealed) >= horizon:
            unprocessed = sum(1 for later in targets[position:] if is_eligible(later))
            break
        if is_eligible(target):
            eligible_seen += 1
            result = seal_target(history, target, pool_builder)
            if isinstance(result, Exclusion):
                exclusions.append(result)
            else:
                sealed.append(result)
        history.append(target.history_row())
    if sealed:
        for draw in (sealed[0], sealed[-1]):
            reproduce(draw, history, pool_builder)
    return SealedWindow(
        sealed=tuple(sealed),
        exclusions=tuple(exclusions),
        eligible_seen=eligible_seen,
        eligible_unprocessed=unprocessed,
        determinism_verified=bool(sealed),
    )


# --- scoring: the single frozen paired comparison ----------------------------------------
def score_analysis(sealed: Sequence[SealedDraw]) -> dict[int, list[dict[str, object]]]:
    """Frozen ``score`` of every sealed portfolio, shaped for ``summarize_pair``."""

    rows: dict[int, list[dict[str, object]]] = {k: [] for k in CONFIRMATION_K}
    for draw in sealed:
        for k in CONFIRMATION_K:
            arm_tickets = draw.tickets[k]
            rows[k].append(
                {
                    "target_draw": draw.target.draw_number,
                    "scores": {arm: score(t, draw.target, k) for arm, t in arm_tickets.items()},
                    "tickets": dict(arm_tickets),
                }
            )
    return rows


def _mapping(value: object) -> dict[str, object]:
    return cast(dict[str, object], value)


def classify_primary(summary: Mapping[str, object]) -> tuple[str, str, dict[str, object]]:
    """Map the frozen K10 gate onto the five confirmation statuses."""

    p_value = cast(float, summary["primary_exact_p_value"])
    adjusted = holm_bonferroni_adjusted([p_value, *([1.0] * (GATE_FAMILY_SIZE - 1))])[0]
    label = arm_verdict(dict(summary), adjusted)
    delta = cast(float, _mapping(summary["official_any_prize"])["absolute_delta"])
    gate: dict[str, object] = {
        "exact_p_value": p_value,
        "holm_adjusted_p_value": adjusted,
        "gate_family_size": GATE_FAMILY_SIZE,
        "gate_alpha": GATE_ALPHA,
        "frozen_gate_label": label,
        "absolute_delta": delta,
    }
    if label == "INSUFFICIENT_EVIDENCE":
        return STATUS_INSUFFICIENT, "PRIMARY_ADEQUACY_FLOOR_NOT_MET", gate
    if label == "POSITIVE_LIFT_VALIDATED":
        return STATUS_CONFIRMED, "FROZEN_GATE_MET_AT_K10", gate
    if delta <= 0:
        return STATUS_FAILED, "FROZEN_GATE_NOT_MET_AND_K10_DELTA_NOT_POSITIVE", gate
    return STATUS_INCONCLUSIVE, "FROZEN_GATE_NOT_MET_AND_K10_DELTA_POSITIVE", gate


def comparison_block(summary: Mapping[str, object]) -> dict[str, object]:
    """The required per-K diagnostics, taken from the frozen ``summarize_pair`` result."""

    primary = _mapping(summary["official_any_prize"])
    return {
        "incumbent_wins": primary["reference_count_or_sum"],
        "candidate_wins": primary["arm_count_or_sum"],
        "incumbent_rate": primary["reference"],
        "candidate_rate": primary["arm"],
        "absolute_delta": primary["absolute_delta"],
        "relative_lift": primary["relative_lift"],
        "paired_delta_counts": primary["paired_delta_counts"],
        "discordant_draws": summary["primary_discordant_draw_count"],
        "candidate_only_wins": summary["primary_positive_discordant"],
        "incumbent_only_wins": summary["primary_negative_discordant"],
        "exact_mcnemar_p_value": summary["primary_exact_p_value"],
        "nominal_95_interval": primary["paired_bootstrap_95_interval"],
        "familywise_interval": summary["primary_familywise_interval"],
        "familywise_interval_alpha": FAMILY_ALPHA,
        "ticket_set_changed_draws": summary["ticket_set_changed_draws"],
    }


def geometry_report(sealed: Sequence[SealedDraw], k: int) -> dict[str, object]:
    """Outcome-free overlap diagnostics of both arms at ``k``, aggregated as the frozen report."""

    count = len(sealed)
    report: dict[str, object] = {}
    for arm in ARMS:
        per_draw = [geometry(draw.tickets[k][arm]) for draw in sealed]
        distribution = [
            sum(cast(list[int], g["overlap_distribution"])[i] for g in per_draw) for i in range(7)
        ]
        report[arm] = {
            "mean_pairwise_overlap": (
                sum(cast(float, g["mean_pairwise_overlap"]) for g in per_draw) / count
                if count
                else None
            ),
            "mean_unique_main_number_coverage": (
                sum(cast(int, g["unique_main_number_coverage"]) for g in per_draw) / count
                if count
                else None
            ),
            "duplicate_ticket_draws": sum(1 for g in per_draw if g["duplicate_ticket_count"]),
            "all_tickets_legal": all(g["all_tickets_legal"] for g in per_draw) if count else None,
            "overlap_distribution": distribution,
        }
    report["ticket_set_changed_draws"] = sum(
        1
        for draw in sealed
        if set(draw.tickets[k][INCUMBENT_ARM]) != set(draw.tickets[k][CANDIDATE_ARM])
    )
    return report


def sealed_selection_sha256(sealed: Sequence[SealedDraw]) -> str:
    return digest(
        [
            [
                draw.target.draw_number,
                draw.pool_sha256,
                {str(k): dict(hashes) for k, hashes in draw.portfolio_sha256.items()},
            ]
            for draw in sealed
        ]
    )


def assess(
    index: Sequence[DrawIndexRow],
    prefix: Sequence[SourceDraw],
    targets: Sequence[SourceDraw],
    *,
    as_of: date,
    now: datetime,
    pool_builder: PoolBuilder = build_pool,
    horizon: int = ANALYSIS_HORIZON_PAIRED_DRAWS,
    attestation: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Resolve the confirmation status from already-loaded rows; reads no database.

    ``targets`` are every row after the boundary up to ``as_of``. ``horizon`` exists so tests
    can exercise the gate on small samples; ``run`` always uses the frozen horizon.
    """

    eligibility = eligibility_summary(index, as_of)
    window = seal_window(
        prefix,
        targets,
        is_eligible=lambda draw: classify_key(draw.key, as_of=as_of) == ELIGIBLE,
        horizon=horizon,
        pool_builder=pool_builder,
    )
    eligible_total = cast(int, eligibility["eligible_draw_count"])
    if window.eligible_seen + window.eligible_unprocessed != eligible_total:
        raise ValueError("ELIGIBILITY_INDEX_MISMATCH")
    paired = len(window.sealed)
    summaries: dict[int, dict[str, object]] | None = None
    gate: dict[str, object] | None = None
    if eligible_total == 0:
        status, reason = STATUS_WAIT, "NO_ELIGIBLE_DRAW_AFTER_BOUNDARY"
    elif paired < horizon:
        status, reason = (
            STATUS_INSUFFICIENT,
            f"PAIRED_DRAWS_{paired}_BELOW_ANALYSIS_HORIZON_{horizon}",
        )
    else:
        rows = score_analysis(window.sealed)
        summaries = {
            k: summarize_pair(rows[k], INCUMBENT_ARM, CANDIDATE_ARM, family_alpha=FAMILY_ALPHA)
            for k in CONFIRMATION_K
        }
        status, reason, gate = classify_primary(summaries[PRIMARY_K])
    by_k: dict[str, object] = {}
    for k in CONFIRMATION_K:
        block: dict[str, object] = {
            "role": "PRIMARY" if k == PRIMARY_K else "SECONDARY",
            "gates_verdict": k == PRIMARY_K,
            "eligible_draw_count": eligible_total,
            "paired_draw_count": paired,
            "forced_selection_draws": sum(1 for d in window.sealed if d.candidate_count == k),
            "geometry": geometry_report(window.sealed, k),
        }
        if summaries is None:
            block["outcome_comparison"] = {"status": BLINDED}
        else:
            comparison = comparison_block(summaries[k])
            if k == PRIMARY_K:
                comparison["gate"] = gate
            block["outcome_comparison"] = comparison
        by_k[str(k)] = block
    return {
        "state_schema": STATE_SCHEMA,
        "confirmation_status": status,
        "status_reason": reason,
        "ready_for_branch6_adoption": status == STATUS_CONFIRMED,
        "confirmatory_outcomes_inspected": summaries is not None,
        "as_of_date": as_of.isoformat(),
        "evaluated_at_utc": now.astimezone(UTC).isoformat(timespec="seconds"),
        "module_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "runtime": {"python": sys.version.split()[0], "numpy": _package_version("numpy")},
        "eligibility": eligibility,
        "analysis": {
            "horizon_paired_draws": horizon,
            "paired_draws_available": paired,
            "remaining_paired_draws": max(0, horizon - paired),
            "performed": summaries is not None,
            "eligible_draws_beyond_analysis_set": window.eligible_unprocessed,
            "technical_exclusions": dict(Counter(e.reason for e in window.exclusions)),
            "excluded_targets": [asdict(e) for e in window.exclusions],
            "analysis_set_first_draw": window.sealed[0].target.draw_number if paired else None,
            "analysis_set_last_draw": window.sealed[-1].target.draw_number if paired else None,
            "determinism_verified": window.determinism_verified,
        },
        "sealed_selection_sha256": sealed_selection_sha256(window.sealed),
        "by_k": by_k,
        "identity_attestation": dict(attestation) if attestation is not None else None,
        "prior_evidence_pooled": False,
    }


def _package_version(name: str) -> str:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return "UNKNOWN"


# --- frozen-identity attestation ----------------------------------------------------------
def verify_source_pins() -> None:
    for name, expected in SOURCE_SHA256_BY_MODULE.items():
        module_file = importlib.import_module(name).__file__
        if module_file is None:
            raise ValueError(f"FROZEN_SOURCE_IDENTITY_MISMATCH:{name}")
        if hashlib.sha256(Path(module_file).read_bytes()).hexdigest() != expected:
            raise ValueError(f"FROZEN_SOURCE_IDENTITY_MISMATCH:{name}")


def verify_stream_identities() -> None:
    live = [
        _stream(s.strategy_id, s.native_ticket_count) | {"version": s.strategy_version}
        for s in frozen.STRATEGY_STREAMS
        if s.enabled
    ]
    if live != STREAM_IDENTITIES:
        raise ValueError("FROZEN_STREAM_SET_MISMATCH")


def verify_metric_known_answers() -> None:
    outcome = SourceDraw(
        "115000089",
        "2026-09-18",
        tuple(cast(list[int], METRIC_KNOWN_ANSWER_OUTCOME["winning_main_numbers"])),
        cast(int, METRIC_KNOWN_ANSWER_OUTCOME["winning_special_number"]),
        "0" * 64,
    )
    for case in METRIC_KNOWN_ANSWERS:
        ticket = tuple(cast(list[int], case["ticket"]))
        result = score([ticket], outcome, 1)
        if result["ticket_hits"] != [case["zone1_hits"]] or result["official_any_prize"] != int(
            cast(bool, case["is_winner"])
        ):
            raise ValueError("FROZEN_METRIC_KNOWN_ANSWER_MISMATCH")


def verify_statistics_known_answers() -> None:
    tolerance = cast(float, STATISTICS_KNOWN_ANSWERS["relative_tolerance"])
    for case in cast(list[dict[str, float]], STATISTICS_KNOWN_ANSWERS["exact_two_sided_binomial"]):
        p_value = binomial_two_sided_exact_p_value(int(case["n"]), int(case["k"]), 0.5)
        if not math.isclose(p_value, case["p"], rel_tol=tolerance):
            raise ValueError("FROZEN_STATISTICS_KNOWN_ANSWER_MISMATCH")
    for holm in cast(list[dict[str, list[float]]], STATISTICS_KNOWN_ANSWERS["holm"]):
        adjusted = holm_bonferroni_adjusted(holm["p_values"])
        if not all(
            math.isclose(a, b, rel_tol=tolerance)
            for a, b in zip(adjusted, holm["adjusted"], strict=True)
        ):
            raise ValueError("FROZEN_STATISTICS_KNOWN_ANSWER_MISMATCH")


def verify_reproduction_checkpoints(
    prefix: Sequence[SourceDraw],
    pool_builder: PoolBuilder = build_pool,
    checkpoints: Sequence[Mapping[str, object]] = REPRODUCTION_CHECKPOINTS,
) -> int:
    """Reproduce sealed discovery outputs from the discovery prefix; return how many matched."""

    position = {draw.draw_number: index for index, draw in enumerate(prefix)}
    for checkpoint in checkpoints:
        target_draw = cast(str, checkpoint["target_draw"])
        if target_draw not in position:
            raise ValueError("FROZEN_REPRODUCTION_CHECKPOINT_MISMATCH")
        at = position[target_draw]
        sealed = seal_target([draw.history_row() for draw in prefix[:at]], prefix[at], pool_builder)
        expected_hashes = _mapping(checkpoint["portfolio_sha256"])
        if (
            isinstance(sealed, Exclusion)
            or sealed.history_count != checkpoint["history_count"]
            or sealed.history_sha256 != checkpoint["history_sha256"]
            or sealed.pool_sha256 != checkpoint["pool_sha256"]
            or sealed.candidate_count != checkpoint["candidate_count"]
            or {str(k): dict(v) for k, v in sealed.portfolio_sha256.items()} != expected_hashes
        ):
            raise ValueError("FROZEN_REPRODUCTION_CHECKPOINT_MISMATCH")
    return len(checkpoints)


def attest_frozen_identity(
    prefix: Sequence[SourceDraw], pool_builder: PoolBuilder = build_pool
) -> dict[str, object]:
    verify_source_pins()
    verify_stream_identities()
    verify_metric_known_answers()
    verify_statistics_known_answers()
    checked = verify_reproduction_checkpoints(prefix, pool_builder)
    return {
        "source_pins": "VERIFIED",
        "stream_identities": "VERIFIED",
        "metric_known_answers": "VERIFIED",
        "statistics_known_answers": "VERIFIED",
        "reproduction_checkpoints_verified": checked,
    }


@cache
def planning_power(paired_draws: int) -> float:
    """Exact power of the gate's exact McNemar test at the planning inputs.

    The discordant count is Binomial(paired_draws, discordance rate); given it, the
    candidate-only count is Binomial(discordant, planning direction probability).
    """

    rate = PLANNING_DISCORDANT_DRAWS / PLANNING_PAIRED_DRAWS
    direction = PLANNING_CANDIDATE_ONLY_WINS / PLANNING_DISCORDANT_DRAWS
    mean = paired_draws * rate
    spread = math.sqrt(paired_draws * rate * (1.0 - rate))
    low = max(1, int(mean - 6.0 * spread))
    high = min(paired_draws, int(mean + 6.0 * spread) + 1)
    return math.fsum(
        binomial_pmf(paired_draws, m, rate)
        * binomial_two_sided_exact_power(m, 0.5, direction, alpha=FAMILY_ALPHA)
        for m in range(low, high + 1)
    )


# --- orchestration and the protocol document ---------------------------------------------
def default_as_of(now: datetime) -> date:
    return now.astimezone(ZoneInfo(PROTOCOL_TIMEZONE)).date()


def run(
    database: Path,
    *,
    as_of: date | None = None,
    now: datetime | None = None,
    pool_builder: PoolBuilder = build_pool,
) -> dict[str, object]:
    """Resolve the confirmation status from the canonical database, read-only."""

    evaluated_at = now if now is not None else datetime.now(UTC)
    as_of_date = as_of if as_of is not None else default_as_of(evaluated_at)
    index = load_draw_index(database)
    eligible_total = cast(int, eligibility_summary(index, as_of_date)["eligible_draw_count"])
    prefix = load_source_draws(database, through=DISCOVERY_LAST_KEY)
    logical = verify_discovery_prefix(prefix)
    attestation = attest_frozen_identity(prefix, pool_builder)
    attestation["discovery_prefix_logical_sha256"] = logical
    targets = (
        load_source_draws(database, after=DISCOVERY_LAST_KEY, through=(as_of_date, MAX_DRAW_NUMBER))
        if eligible_total
        else ()
    )
    state = assess(
        index,
        prefix,
        targets,
        as_of=as_of_date,
        now=evaluated_at,
        pool_builder=pool_builder,
        attestation=attestation,
    )
    state["database"] = str(database)
    return state


def render_document(state: Mapping[str, object]) -> str:
    document: dict[str, object] = {
        "schema": DOCUMENT_SCHEMA,
        "protocol": PROTOCOL,
        "protocol_sha256": PROTOCOL_SHA256,
        "state": state,
    }
    return json.dumps(document, sort_keys=True, indent=2, allow_nan=False) + "\n"


def emit_freeze_document(path: Path) -> None:
    """Create the protocol document with an unevaluated state; never overwrites."""

    with path.open("x", encoding="utf-8") as handle:
        handle.write(render_document(FREEZE_STATE))


def update_document(path: Path, state: Mapping[str, object]) -> None:
    """Replace only the ``state`` section; refuse a changed protocol or a changed verdict."""

    existing = cast(dict[str, object], json.loads(path.read_text(encoding="utf-8")))
    if existing.get("protocol") != PROTOCOL or existing.get("protocol_sha256") != PROTOCOL_SHA256:
        raise ValueError("PROTOCOL_DOCUMENT_MISMATCH")
    previous = _mapping(existing.get("state")).get("confirmation_status")
    if previous in TERMINAL_STATUSES and state["confirmation_status"] != previous:
        raise ValueError("TERMINAL_VERDICT_ALREADY_RECORDED")
    path.write_text(render_document(state), encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, help="canonical lottolab.db, opened read-only")
    parser.add_argument("--document", type=Path, help="protocol document to update")
    parser.add_argument("--write", action="store_true", help="write the state into --document")
    parser.add_argument("--as-of", type=date.fromisoformat, default=None)
    parser.add_argument("--emit-freeze-document", type=Path, default=None)
    args = parser.parse_args(argv)
    if args.emit_freeze_document is not None:
        emit_freeze_document(args.emit_freeze_document)
        print(PROTOCOL_SHA256)
        return 0
    if args.database is None:
        parser.error("--database is required")
    state = run(args.database, as_of=args.as_of)
    if args.write:
        if args.document is None:
            parser.error("--write requires --document")
        update_document(args.document, state)
    print(json.dumps(state, sort_keys=True, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
