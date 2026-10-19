"""Compare the sealed R1 winner with its frozen current-default baseline.

This module is deliberately narrower than a Study runner. It verifies and
reuses the canonical R1 winner confirmation, reconstructs the exact fixed
confirmation identities from the sealed dataset authority, and evaluates only
the frozen default candidate. It never searches candidates, evaluates the
winner, promotes a strategy, or writes to a database.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Protocol, cast

from lottolab.application.historical_prefix_success_windows import (
    CONFIRMATION_TARGET_COUNT,
    DISCOVERY_TARGET_COUNT,
    REQUIRED_LABELED_TARGET_COUNT,
    TEMPORAL_HOLDOUT_SPLIT_METHOD,
)
from lottolab.application.legacy_source_grid_native_portfolios_wave46 import (
    CONTEXT_POLICY,
    FROZEN_SOURCE_COMMIT,
    LEDGER_CONTENT_SHA256,
    LEDGER_FILE_SHA256,
    LEDGER_SCHEMA_VERSION,
    PINNED_DATASET_SHA256,
    SOURCE_NATIVE_WAVE46_PROTOCOL,
    SOURCE_REFERENCE_RUNTIME,
    SUM_CONSTRAINT_METHOD_ID,
    load_legacy_source_grid_native_wave46_ledger_for_verification,
)
from lottolab.evidence import canonical_json
from lottolab.infrastructure.replay_backed_batch_import import (
    PinnedBigLottoDraw,
    PinnedBigLottoHistory,
    load_pinned_biglotto_history,
)
from lottolab.research.base_method_evaluation import (
    AVG_MATCH_ID,
    BASE_METHOD_EVALUATOR_SEMANTIC_VERSION,
    BIG_LOTTO_MATCH_CONTRACT,
    EvaluableStatus,
    ExposureKind,
    MethodDrawObservation,
    MethodEvaluationRecord,
    MethodExposure,
    MethodIdentity,
    MethodTargetCoverage,
    OutputShape,
    ReplayStatus,
    WindowKind,
    evaluate_method,
)

SCHEMA_ID = "lottolab.research.native_study_campaign_confirmation_baseline_headtohead_r2"
SCHEMA_VERSION = "1.0.0"
STUDY_ID = "native-study-campaign-confirmation-baseline-headtohead-r2"
R1_STUDY_ID = "native-study-first-strategy-campaign-r1"
R1_SCHEMA_ID = "lottolab.research.native_study"
R1_SCHEMA_VERSION = "1.0.0"
R1_CAMPAIGN_SCHEMA_ID = "lottolab.research.native_study_first_strategy_campaign_r1"
R1_CAMPAIGN_SCHEMA_VERSION = "1.0.0"
R1_EXPECTED_RESULT_SHA256 = "a71ba4e110f42172b8e5a89eaa61cdcb94b415a3631e65cc67204a44c599c33f"
CAMPAIGN_BASE_COMMIT = "db8bd5276ae9ec25bb88b9366eed7d0c38ccec7f"
WINNER_CANDIDATE_ID = "r1-015-sum-pool-8-bet1-only"
DEFAULT_CANDIDATE_ID = "r1-020-sum-pool-12-apply-all"
SUM_STRATEGY_ID = "legacy_biglotto__backtest_sum_constraint__acb3b118300d"
SUM_STRATEGY_VERSION = "v0.1"
AVG_MATCH_OBJECTIVE_ID = "AVG_MATCH_DELTA_VS_RANDOM"
M3_OBJECTIVE_ID = "M3_PLUS_OBSERVED_RATE"
COMMON_MINIMUM_HISTORY = 500
DEFAULT_TICKET_SLICE_START = 21
DEFAULT_TICKET_SLICE_STOP = 24
PROMOTION_DECISION = "NOT_AUTHORIZED"
PAIRED_EVIDENCE_STATUS = "NOT_APPLICABLE"
SIGNIFICANCE_RESULT_STATUS = "NOT_APPLICABLE"

type Ticket = tuple[int, int, int, int, int, int]

_WINNER_CONFIRMATION_VALUES = (Fraction(29, 14700), Fraction(19, 300))
_WINNER_PARAMETERS: dict[str, object] = {
    "apply_to": "bet1_only",
    "legacy_method_id": "tools/backtest_sum_constraint.py",
    "pool_size": 8,
    "portfolio_ticket_count": 3,
    "registered_default": False,
    "source_configuration": "POOL_8_APPLY_BET1_ONLY",
    "source_ticket_slice_start_inclusive": 9,
    "source_ticket_slice_stop_exclusive": 12,
    "strategy_id": SUM_STRATEGY_ID,
    "strategy_version": SUM_STRATEGY_VERSION,
}
_DEFAULT_PARAMETERS: dict[str, object] = {
    "apply_to": "all",
    "legacy_method_id": "tools/backtest_sum_constraint.py",
    "pool_size": 12,
    "portfolio_ticket_count": 3,
    "registered_default": True,
    "source_configuration": "POOL_12_APPLY_ALL",
    "source_ticket_slice_start_inclusive": DEFAULT_TICKET_SLICE_START,
    "source_ticket_slice_stop_exclusive": DEFAULT_TICKET_SLICE_STOP,
    "strategy_id": SUM_STRATEGY_ID,
    "strategy_version": SUM_STRATEGY_VERSION,
}


class BaselineHeadToHeadR2Error(ValueError):
    """A sealed input or exactly-once R2 execution invariant failed."""


class _Wave46Ledger(Protocol):
    target_index_by_number: Mapping[str, int]
    context_sha256: tuple[str, ...]
    tickets_by_method: Mapping[str, tuple[tuple[Ticket, ...] | None, ...]]


@dataclass(frozen=True, slots=True)
class _SealedTargetIdentity:
    draw_number: int
    draw_date: str
    draw_sha256: str

    def canonical_dict(self) -> dict[str, object]:
        return {
            "draw_date": self.draw_date,
            "draw_number": self.draw_number,
            "draw_sha256": self.draw_sha256,
        }


@dataclass(frozen=True, slots=True)
class ConfirmationObservationIdentity:
    draw_id: str
    draw_date: str
    draw_sha256: str

    def canonical_dict(self) -> dict[str, object]:
        return {
            "draw_date": self.draw_date,
            "draw_id": self.draw_id,
            "draw_sha256": self.draw_sha256,
        }


@dataclass(frozen=True, slots=True)
class _R1Authority:
    result_file: str
    result_sha256: str
    database_sha256: str
    dataset_content_sha256: str
    replay_truth_supplemented_draw_count: int
    total_assignment_count: int
    warmup_count: int
    discovery_count: int
    confirmation_count: int
    confirmation_first_target: _SealedTargetIdentity
    confirmation_last_target: _SealedTargetIdentity
    winner_parameters: dict[str, object]
    default_parameters: dict[str, object]
    winner_confirmation_values: tuple[Fraction, Fraction]


@dataclass(frozen=True, slots=True)
class _DefaultConfirmationResult:
    avg_match_observed_value: Fraction
    avg_match_random_reference: Fraction
    avg_match_delta_vs_random: Fraction
    m3_plus_success_draw_count: int
    m3_plus_observed_rate: Fraction
    m3_plus_random_reference: Fraction

    @property
    def objective_values(self) -> tuple[Fraction, Fraction]:
        return (self.avg_match_delta_vs_random, self.m3_plus_observed_rate)

    def canonical_dict(self) -> dict[str, object]:
        return {
            "avg_match": {
                "baseline_method": "HYPERGEOMETRIC_MEAN_EXACT",
                "delta_vs_random": _exact_metadata(self.avg_match_delta_vs_random),
                "observed_value": _exact_metadata(self.avg_match_observed_value),
                "random_reference": _exact_metadata(self.avg_match_random_reference),
            },
            "m3_plus": {
                "baseline_method": "BINOMIAL_EXACT",
                "observed_value": _exact_metadata(self.m3_plus_observed_rate),
                "random_reference": _exact_metadata(self.m3_plus_random_reference),
                "success_draw_count": self.m3_plus_success_draw_count,
            },
        }


@dataclass(frozen=True, slots=True)
class _DefaultEvaluation:
    result: _DefaultConfirmationResult
    identities: tuple[ConfirmationObservationIdentity, ...]


@dataclass(frozen=True, slots=True)
class R2Execution:
    result_document: dict[str, object]
    winner_confirmation_values: tuple[Fraction, Fraction]
    default_confirmation_values: tuple[Fraction, Fraction]
    head_to_head_deltas: tuple[Fraction, Fraction]
    point_estimate_classification: str
    winner_evaluation_count: int
    default_evaluation_count: int

    def canonical_result_bytes(self) -> bytes:
        return canonical_json.canonical_bytes(self.result_document)

    def canonical_result_sha256(self) -> str:
        return canonical_json.sha256_hex(self.canonical_result_bytes())


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise BaselineHeadToHeadR2Error(message)


def _object(value: object, context: str) -> dict[str, object]:
    _require(type(value) is dict, f"{context} must be an object")
    return cast(dict[str, object], value)


def _array(value: object, context: str) -> list[object]:
    _require(type(value) is list, f"{context} must be an array")
    return cast(list[object], value)


def _string(value: object, context: str) -> str:
    _require(type(value) is str and bool(value), f"{context} must be a non-empty string")
    return cast(str, value)


def _integer(value: object, context: str) -> int:
    _require(type(value) is int, f"{context} must be an integer")
    return cast(int, value)


def _expect_keys(value: Mapping[str, object], keys: set[str], context: str) -> None:
    _require(set(value) == keys, f"{context} keys changed")


def _sha256_text(value: object, context: str) -> str:
    text = _string(value, context)
    _require(
        len(text) == 64 and all(character in "0123456789abcdef" for character in text),
        f"{context} must be a lowercase SHA-256",
    )
    return text


def _fraction(value: object, context: str) -> Fraction:
    row = _object(value, context)
    _expect_keys(row, {"denominator", "numerator"}, context)
    numerator = _integer(row["numerator"], f"{context}.numerator")
    denominator = _integer(row["denominator"], f"{context}.denominator")
    _require(denominator > 0, f"{context}.denominator must be positive")
    exact = Fraction(numerator, denominator)
    _require(
        exact.numerator == numerator and exact.denominator == denominator,
        f"{context} must use a reduced positive-denominator rational",
    )
    return exact


def _parse_objective_values(value: object, context: str) -> tuple[Fraction, Fraction]:
    rows = _array(value, context)
    _require(len(rows) == 2, f"{context} must contain exactly two objectives")
    return (
        _fraction(rows[0], f"{context}[0]"),
        _fraction(rows[1], f"{context}[1]"),
    )


def _target_identity(value: object, context: str) -> _SealedTargetIdentity:
    row = _object(value, context)
    _expect_keys(row, {"draw_date", "draw_number", "draw_sha256"}, context)
    return _SealedTargetIdentity(
        draw_number=_integer(row["draw_number"], f"{context}.draw_number"),
        draw_date=_string(row["draw_date"], f"{context}.draw_date"),
        draw_sha256=_sha256_text(row["draw_sha256"], f"{context}.draw_sha256"),
    )


def _trial_by_id(
    trials: list[object],
    candidate_id: str,
    *,
    context: str,
) -> dict[str, object]:
    matches = [
        row
        for item in trials
        if (row := _object(item, context)).get("candidate_id") == candidate_id
    ]
    _require(len(matches) == 1, f"{context} must contain exactly one {candidate_id}")
    return matches[0]


def _validate_no_winner_per_draw_payload(confirmation: Mapping[str, object]) -> None:
    _expect_keys(
        confirmation,
        {"full_history_metadata", "objective_values", "winner"},
        "R1 confirmation",
    )
    metadata = _object(confirmation["full_history_metadata"], "R1 confirmation metadata")
    _expect_keys(
        metadata,
        {
            "candidate_id",
            "eligible_draw_count",
            "evaluator_semantic_version",
            "metrics",
            "rational_encoding",
            "selection_use",
            "strategy_id",
            "strategy_version",
            "window_kind",
            "window_role",
            "window_status",
        },
        "R1 confirmation metadata",
    )
    allowed_metric_keys = {
        "baseline_method",
        "delta_vs_random",
        "eligible_draw_count",
        "evaluable_status",
        "metric_id",
        "observed_value",
        "random_reference",
        "random_status",
        "success_draw_count",
    }
    for index, item in enumerate(_array(metadata["metrics"], "R1 full-history metrics")):
        metric = _object(item, f"R1 full-history metric[{index}]")
        _require(
            set(metric).issubset(allowed_metric_keys),
            "R1 full-history metric unexpectedly contains non-aggregate evidence",
        )
    _require(metadata["candidate_id"] == WINNER_CANDIDATE_ID, "R1 confirmation ID changed")
    _require(
        metadata["strategy_id"] == SUM_STRATEGY_ID
        and metadata["strategy_version"] == SUM_STRATEGY_VERSION,
        "R1 confirmation strategy identity changed",
    )
    _require(
        metadata["evaluator_semantic_version"] == BASE_METHOD_EVALUATOR_SEMANTIC_VERSION,
        "R1 confirmation evaluator semantics changed",
    )
    _require(
        metadata["selection_use"] == "FORBIDDEN_DESCRIPTIVE_ONLY"
        and metadata["window_kind"] == WindowKind.FULL_HISTORY.value
        and metadata["window_role"] == "DESCRIPTIVE_REFERENCE_ONLY"
        and metadata["window_status"] == "COMPLETE",
        "R1 full-history confirmation metadata is not descriptive-only",
    )


def _load_r1_authority(
    r1_result: Path,
    *,
    expected_r1_result_sha256: str,
) -> _R1Authority:
    _require(
        expected_r1_result_sha256 == R1_EXPECTED_RESULT_SHA256,
        "caller R1 result SHA differs from the task-sealed authority",
    )
    raw = r1_result.read_bytes()
    actual_sha256 = hashlib.sha256(raw).hexdigest()
    _require(actual_sha256 == expected_r1_result_sha256, "R1 result SHA-256 mismatch")
    parsed = canonical_json.loads_canonical(raw)
    document = _object(parsed, "R1 result")
    _require(
        raw == canonical_json.canonical_bytes(document),
        "R1 result is not exact LCJ-1 canonical bytes",
    )
    _expect_keys(
        document,
        {"confirmation", "schema_id", "schema_version", "spec", "trials", "winner"},
        "R1 result",
    )
    _require(document["schema_id"] == R1_SCHEMA_ID, "R1 result schema ID changed")
    _require(document["schema_version"] == R1_SCHEMA_VERSION, "R1 result schema changed")

    spec = _object(document["spec"], "R1 spec")
    _expect_keys(
        spec,
        {
            "full_history_metadata",
            "objectives",
            "study_id",
            "temporal_holdout_split",
            "trials",
        },
        "R1 spec",
    )
    _require(spec["study_id"] == R1_STUDY_ID, "R1 study identity changed")
    _require(
        spec["objectives"]
        == [
            {"direction": "MAXIMIZE", "objective_id": AVG_MATCH_OBJECTIVE_ID},
            {"direction": "MAXIMIZE", "objective_id": M3_OBJECTIVE_ID},
        ],
        "R1 objective order or direction changed",
    )

    metadata = _object(spec["full_history_metadata"], "R1 spec metadata")
    _expect_keys(
        metadata,
        {
            "base_commit",
            "campaign_schema_id",
            "campaign_schema_version",
            "candidate_universe_frozen_before_scoring",
            "candidate_universe_sha256",
            "canonicalization",
            "confirmation_objective_window",
            "context_policy",
            "database_sha256",
            "dataset_content_sha256",
            "discovery_objective_window",
            "evaluator_semantic_version",
            "full_history_selection_use",
            "ledger_content_sha256",
            "ledger_file_sha256",
            "ledger_schema_version",
            "objective_selection_contract",
            "pinned_source_dataset_sha256",
            "promotion_decision",
            "replay_truth_supplemented_draw_count",
            "source_commit",
            "source_protocol",
            "source_reference_runtime",
        },
        "R1 spec metadata",
    )
    _require(metadata["base_commit"] == CAMPAIGN_BASE_COMMIT, "R1 base commit changed")
    _require(
        metadata["campaign_schema_id"] == R1_CAMPAIGN_SCHEMA_ID
        and metadata["campaign_schema_version"] == R1_CAMPAIGN_SCHEMA_VERSION,
        "R1 campaign schema changed",
    )
    _require(
        metadata["candidate_universe_frozen_before_scoring"] is True,
        "R1 candidate universe was not frozen",
    )
    _sha256_text(metadata["candidate_universe_sha256"], "R1 candidate universe SHA")
    _require(metadata["canonicalization"] == "LCJ-1", "R1 canonicalization changed")
    _require(
        metadata["confirmation_objective_window"] == WindowKind.WINDOW_300.value,
        "R1 confirmation objective window changed",
    )
    _require(metadata["context_policy"] == CONTEXT_POLICY, "R1 context policy changed")
    _require(
        metadata["evaluator_semantic_version"] == BASE_METHOD_EVALUATOR_SEMANTIC_VERSION,
        "R1 evaluator semantics changed",
    )
    _require(
        metadata["full_history_selection_use"] == "FORBIDDEN_DESCRIPTIVE_ONLY",
        "R1 full-history selection rule changed",
    )
    _require(
        metadata["ledger_content_sha256"] == LEDGER_CONTENT_SHA256
        and metadata["ledger_file_sha256"] == LEDGER_FILE_SHA256
        and metadata["ledger_schema_version"] == LEDGER_SCHEMA_VERSION,
        "R1 ledger authority changed",
    )
    _require(
        metadata["pinned_source_dataset_sha256"] == PINNED_DATASET_SHA256,
        "R1 pinned source dataset changed",
    )
    _require(metadata["promotion_decision"] == PROMOTION_DECISION, "R1 promotion changed")
    _require(
        metadata["source_commit"] == FROZEN_SOURCE_COMMIT
        and metadata["source_protocol"] == SOURCE_NATIVE_WAVE46_PROTOCOL
        and metadata["source_reference_runtime"] == SOURCE_REFERENCE_RUNTIME,
        "R1 source authority changed",
    )

    split = _object(spec["temporal_holdout_split"], "R1 temporal holdout")
    _expect_keys(
        split,
        {
            "confirmation_count",
            "confirmation_first_target",
            "confirmation_last_target",
            "discovery_count",
            "discovery_first_target",
            "discovery_last_target",
            "split_method",
            "total_assignment_count",
            "warmup_count",
        },
        "R1 temporal holdout",
    )
    _require(
        split["split_method"] == TEMPORAL_HOLDOUT_SPLIT_METHOD,
        "R1 temporal split method changed",
    )
    confirmation_count = _integer(split["confirmation_count"], "R1 confirmation count")
    discovery_count = _integer(split["discovery_count"], "R1 discovery count")
    _require(
        confirmation_count == CONFIRMATION_TARGET_COUNT
        and discovery_count == DISCOVERY_TARGET_COUNT,
        "R1 temporal split counts changed",
    )
    total_assignment_count = _integer(
        split["total_assignment_count"],
        "R1 total assignment count",
    )
    warmup_count = _integer(split["warmup_count"], "R1 warmup count")
    _require(
        total_assignment_count == warmup_count + discovery_count + confirmation_count,
        "R1 temporal split accounting changed",
    )

    spec_trials = _array(spec["trials"], "R1 spec trials")
    result_trials = _array(document["trials"], "R1 result trials")
    _require(len(spec_trials) == 25 and len(result_trials) == 25, "R1 trial count changed")
    for index, item in enumerate(spec_trials):
        _expect_keys(
            _object(item, f"R1 spec trial[{index}]"),
            {"candidate_id", "parameters"},
            f"R1 spec trial[{index}]",
        )
    for index, item in enumerate(result_trials):
        _expect_keys(
            _object(item, f"R1 result trial[{index}]"),
            {
                "candidate_id",
                "full_history_metadata",
                "objective_values",
                "parameters",
                "state",
            },
            f"R1 result trial[{index}]",
        )

    winner = _object(document["winner"], "R1 winner")
    _expect_keys(
        winner,
        {"candidate_id", "discovery_objective_values", "parameters"},
        "R1 winner",
    )
    _require(winner["candidate_id"] == WINNER_CANDIDATE_ID, "R1 winner identity changed")
    winner_parameters = _object(winner["parameters"], "R1 winner parameters")
    _require(winner_parameters == _WINNER_PARAMETERS, "R1 winner parameters changed")

    winner_spec = _trial_by_id(spec_trials, WINNER_CANDIDATE_ID, context="R1 spec trials")
    default_spec = _trial_by_id(spec_trials, DEFAULT_CANDIDATE_ID, context="R1 spec trials")
    winner_trial = _trial_by_id(result_trials, WINNER_CANDIDATE_ID, context="R1 result trials")
    default_trial = _trial_by_id(result_trials, DEFAULT_CANDIDATE_ID, context="R1 result trials")
    _require(
        _object(winner_spec["parameters"], "R1 winner spec parameters") == _WINNER_PARAMETERS
        and _object(winner_trial["parameters"], "R1 winner trial parameters") == _WINNER_PARAMETERS,
        "R1 winner trial identity changed",
    )
    _require(
        _object(default_spec["parameters"], "R1 default spec parameters") == _DEFAULT_PARAMETERS
        and _object(default_trial["parameters"], "R1 default trial parameters")
        == _DEFAULT_PARAMETERS,
        "R1 default trial identity changed",
    )
    _require(
        winner_trial["state"] == "COMPLETE" and default_trial["state"] == "COMPLETE",
        "R1 winner/default discovery trial is incomplete",
    )
    _require(
        winner_trial["objective_values"] == winner["discovery_objective_values"],
        "R1 winner discovery values changed",
    )

    confirmation = _object(document["confirmation"], "R1 confirmation")
    _validate_no_winner_per_draw_payload(confirmation)
    confirmation_winner = _object(confirmation["winner"], "R1 confirmation winner")
    _require(confirmation_winner == winner, "R1 confirmation winner was not frozen")
    winner_confirmation_values = _parse_objective_values(
        confirmation["objective_values"],
        "R1 winner confirmation objectives",
    )
    _require(
        winner_confirmation_values == _WINNER_CONFIRMATION_VALUES,
        "R1 winner confirmation values differ from the task-sealed values",
    )

    return _R1Authority(
        result_file=r1_result.name,
        result_sha256=actual_sha256,
        database_sha256=_sha256_text(metadata["database_sha256"], "R1 database SHA"),
        dataset_content_sha256=_sha256_text(
            metadata["dataset_content_sha256"],
            "R1 dataset content SHA",
        ),
        replay_truth_supplemented_draw_count=_integer(
            metadata["replay_truth_supplemented_draw_count"],
            "R1 replay truth supplemented draw count",
        ),
        total_assignment_count=total_assignment_count,
        warmup_count=warmup_count,
        discovery_count=discovery_count,
        confirmation_count=confirmation_count,
        confirmation_first_target=_target_identity(
            split["confirmation_first_target"],
            "R1 confirmation first target",
        ),
        confirmation_last_target=_target_identity(
            split["confirmation_last_target"],
            "R1 confirmation last target",
        ),
        winner_parameters=dict(winner_parameters),
        default_parameters=dict(_object(default_trial["parameters"], "R1 default parameters")),
        winner_confirmation_values=winner_confirmation_values,
    )


def _draw_sha256(draw: PinnedBigLottoDraw) -> str:
    return canonical_json.sha256_hex(
        canonical_json.canonical_bytes(
            {
                "draw_date": draw.draw_date.isoformat(),
                "draw_number": draw.draw_number,
                "lottery_type": "BIG_LOTTO",
                "main_numbers": list(draw.numbers),
                "special_numbers": [draw.special],
            }
        )
    )


def _dataset_content_sha256(history: PinnedBigLottoHistory) -> str:
    document = {
        "database_sha256": history.database_sha256_before,
        "draws": [
            {
                "draw_date": draw.draw_date.isoformat(),
                "draw_number": draw.draw_number,
                "draw_sha256": _draw_sha256(draw),
            }
            for draw in history.draws
        ],
    }
    return canonical_json.sha256_hex(canonical_json.canonical_bytes(document))


def _confirmation_identity(draw: PinnedBigLottoDraw) -> ConfirmationObservationIdentity:
    return ConfirmationObservationIdentity(
        draw_id=draw.draw_number,
        draw_date=draw.draw_date.isoformat(),
        draw_sha256=_draw_sha256(draw),
    )


def _context_sha256(draws: tuple[PinnedBigLottoDraw, ...]) -> str:
    payload = [list(draw.numbers) for draw in draws]
    return hashlib.sha256(json.dumps(payload, separators=(",", ":")).encode("utf-8")).hexdigest()


def _prepare_confirmation_draws(
    authority: _R1Authority,
    *,
    archive_database: Path,
) -> tuple[
    PinnedBigLottoHistory,
    tuple[PinnedBigLottoDraw, ...],
    _Wave46Ledger,
]:
    history = load_pinned_biglotto_history(
        database=archive_database,
        expected_database_sha256=authority.database_sha256,
        require_replay_authority=True,
    )
    _require(
        history.database_sha256_before == authority.database_sha256
        and history.database_sha256_after == authority.database_sha256,
        "archived database identity changed during read",
    )
    _require(
        history.replay_truth_supplemented_draw_count
        == authority.replay_truth_supplemented_draw_count,
        "archived replay-truth supplementation count differs from R1",
    )
    draws = history.draws
    _require(
        len(draws) >= COMMON_MINIMUM_HISTORY + REQUIRED_LABELED_TARGET_COUNT,
        "archive cannot satisfy the sealed temporal holdout",
    )
    _require(
        len({draw.draw_number for draw in draws}) == len(draws),
        "archive draw identities are duplicated",
    )
    _require(
        tuple(sorted(draws, key=lambda draw: (draw.draw_date, int(draw.draw_number)))) == draws,
        "archive history is not chronological",
    )
    _require(
        _dataset_content_sha256(history) == authority.dataset_content_sha256,
        "archive dataset content differs from sealed R1",
    )

    eligible_draws = draws[COMMON_MINIMUM_HISTORY:]
    _require(
        len(eligible_draws) == authority.total_assignment_count,
        "eligible assignment count differs from sealed R1",
    )
    warmup_count = len(eligible_draws) - REQUIRED_LABELED_TARGET_COUNT
    _require(warmup_count == authority.warmup_count, "R1 warmup boundary changed")
    confirmation_draws = eligible_draws[-CONFIRMATION_TARGET_COUNT:]
    _require(
        len(confirmation_draws) == authority.confirmation_count,
        "confirmation draw count differs from sealed R1",
    )
    first = _confirmation_identity(confirmation_draws[0])
    last = _confirmation_identity(confirmation_draws[-1])
    _require(
        int(first.draw_id) == authority.confirmation_first_target.draw_number
        and first.draw_date == authority.confirmation_first_target.draw_date
        and first.draw_sha256 == authority.confirmation_first_target.draw_sha256,
        "confirmation first identity differs from sealed R1",
    )
    _require(
        int(last.draw_id) == authority.confirmation_last_target.draw_number
        and last.draw_date == authority.confirmation_last_target.draw_date
        and last.draw_sha256 == authority.confirmation_last_target.draw_sha256,
        "confirmation last identity differs from sealed R1",
    )
    ledger = cast(
        _Wave46Ledger,
        load_legacy_source_grid_native_wave46_ledger_for_verification(),
    )
    return history, confirmation_draws, ledger


def _method_identity(
    observations: tuple[MethodDrawObservation, ...],
) -> MethodIdentity:
    return MethodIdentity(
        method_id=DEFAULT_CANDIDATE_ID,
        method_version=f"{SUM_STRATEGY_VERSION}+{R1_STUDY_ID}",
        method_family=SUM_STRATEGY_ID,
        output_shape=OutputShape.PORTFOLIO,
        exposure=MethodExposure(
            kind=ExposureKind.FIXED,
            minimum_native_ticket_count=3,
            maximum_native_ticket_count=3,
        ),
        target_coverage=MethodTargetCoverage(
            eligible_draw_count=len(observations),
            first_draw_id=observations[0].draw_id,
            last_draw_id=observations[-1].draw_id,
        ),
        replay_status=ReplayStatus.RESEARCH_AVAILABLE,
    )


def _extract_default_result(record: MethodEvaluationRecord) -> _DefaultConfirmationResult:
    block = record.windows[WindowKind.WINDOW_300]
    _require(
        block.eligible_draw_count == CONFIRMATION_TARGET_COUNT,
        "default WINDOW_300 eligible count changed",
    )
    average = block.metrics[AVG_MATCH_ID]
    m3_plus = block.metrics["M3_PLUS"]
    _require(
        average.evaluable_status is EvaluableStatus.EVALUABLE
        and m3_plus.evaluable_status is EvaluableStatus.EVALUABLE,
        "default canonical objective cell is not evaluable",
    )
    _require(
        average.observed_value is not None
        and average.random_reference is not None
        and average.delta_vs_random is not None
        and m3_plus.success_draw_count is not None
        and m3_plus.observed_value is not None
        and m3_plus.random_reference is not None,
        "default canonical metric value is unavailable",
    )
    assert average.observed_value is not None
    assert average.random_reference is not None
    assert average.delta_vs_random is not None
    assert m3_plus.success_draw_count is not None
    assert m3_plus.observed_value is not None
    assert m3_plus.random_reference is not None
    return _DefaultConfirmationResult(
        avg_match_observed_value=average.observed_value,
        avg_match_random_reference=average.random_reference,
        avg_match_delta_vs_random=average.delta_vs_random,
        m3_plus_success_draw_count=m3_plus.success_draw_count,
        m3_plus_observed_rate=m3_plus.observed_value,
        m3_plus_random_reference=m3_plus.random_reference,
    )


class _DefaultEvaluator:
    def __init__(
        self,
        *,
        all_draws: tuple[PinnedBigLottoDraw, ...],
        ledger: _Wave46Ledger,
    ) -> None:
        self._all_draws = all_draws
        self._ledger = ledger
        self.call_count = 0

    def __call__(
        self,
        confirmation_draws: tuple[PinnedBigLottoDraw, ...],
    ) -> _DefaultEvaluation:
        self.call_count += 1
        _require(self.call_count == 1, "default evaluator invoked more than once")
        draw_index_by_number = {
            draw.draw_number: index for index, draw in enumerate(self._all_draws)
        }
        observations: list[MethodDrawObservation] = []
        identities: list[ConfirmationObservationIdentity] = []
        for target in confirmation_draws:
            history_index = draw_index_by_number.get(target.draw_number)
            _require(history_index is not None, "confirmation target left the sealed archive")
            assert history_index is not None
            ledger_index = self._ledger.target_index_by_number.get(target.draw_number)
            _require(ledger_index is not None, "confirmation target left the frozen ledger")
            assert ledger_index is not None
            _require(
                self._ledger.context_sha256[ledger_index]
                == _context_sha256(self._all_draws[:history_index]),
                f"causal context differs from frozen ledger at {target.draw_number}",
            )
            source_portfolio = self._ledger.tickets_by_method[SUM_CONSTRAINT_METHOD_ID][
                ledger_index
            ]
            _require(source_portfolio is not None, "default source portfolio is unavailable")
            assert source_portfolio is not None
            tickets = source_portfolio[DEFAULT_TICKET_SLICE_START:DEFAULT_TICKET_SLICE_STOP]
            _require(len(tickets) == 3, "default source ticket slice changed")
            winning = frozenset(target.numbers)
            observations.append(
                MethodDrawObservation(
                    draw_id=target.draw_number,
                    draw_date=target.draw_date.isoformat(),
                    native_ticket_count=len(tickets),
                    distinct_ticket_count=len(set(tickets)),
                    main_hit_counts=tuple(len(winning.intersection(ticket)) for ticket in tickets),
                )
            )
            identities.append(_confirmation_identity(target))
        typed_observations = tuple(observations)
        record = evaluate_method(
            BIG_LOTTO_MATCH_CONTRACT,
            _method_identity(typed_observations),
            typed_observations,
        )
        return _DefaultEvaluation(
            result=_extract_default_result(record),
            identities=tuple(identities),
        )


def _exact(value: Fraction) -> dict[str, int]:
    return {"denominator": value.denominator, "numerator": value.numerator}


def _exact_metadata(value: Fraction) -> dict[str, str]:
    """Encode arbitrary-size exact rationals inside LCJ-1's value domain."""

    return {
        "denominator_decimal": str(value.denominator),
        "numerator_decimal": str(value.numerator),
    }


def _objective_contract() -> list[dict[str, object]]:
    return [
        {
            "direction": "MAXIMIZE",
            "metric_id": AVG_MATCH_ID,
            "objective_id": AVG_MATCH_OBJECTIVE_ID,
            "value_field": "DELTA_VS_RANDOM",
        },
        {
            "direction": "MAXIMIZE",
            "metric_id": "M3_PLUS",
            "objective_id": M3_OBJECTIVE_ID,
            "value_field": "OBSERVED_VALUE",
        },
    ]


def _serialized_objective_values(
    values: tuple[Fraction, Fraction],
) -> list[dict[str, int]]:
    return [_exact(values[0]), _exact(values[1])]


def _classify_point_estimate(deltas: tuple[Fraction, Fraction]) -> str:
    for delta in deltas:
        if delta > 0:
            return "WINNER_BETTER"
        if delta < 0:
            return "DEFAULT_BETTER"
    return "EQUAL"


def _identity_sha256(identities: tuple[ConfirmationObservationIdentity, ...]) -> str:
    rows = [identity.canonical_dict() for identity in identities]
    return canonical_json.sha256_hex(canonical_json.canonical_bytes(rows))


def run_native_study_campaign_confirmation_baseline_headtohead_r2(
    *,
    r1_result: Path,
    archive_database: Path,
    expected_r1_result_sha256: str = R1_EXPECTED_RESULT_SHA256,
) -> R2Execution:
    """Evaluate the frozen default once and compare it with sealed R1 values."""

    authority = _load_r1_authority(
        r1_result,
        expected_r1_result_sha256=expected_r1_result_sha256,
    )
    history, confirmation_draws, ledger = _prepare_confirmation_draws(
        authority,
        archive_database=archive_database,
    )
    default_evaluator = _DefaultEvaluator(all_draws=history.draws, ledger=ledger)
    default_evaluation = default_evaluator(confirmation_draws)
    _require(default_evaluator.call_count == 1, "default evaluation count is not one")
    _require(
        len(default_evaluation.identities) == authority.confirmation_count,
        "default confirmation identity count changed",
    )

    winner_values = authority.winner_confirmation_values
    default_values = default_evaluation.result.objective_values
    deltas = (
        winner_values[0] - default_values[0],
        winner_values[1] - default_values[1],
    )
    classification = _classify_point_estimate(deltas)
    identities = default_evaluation.identities
    identity_rows = [identity.canonical_dict() for identity in identities]
    identity_sha256 = _identity_sha256(identities)
    result_document: dict[str, object] = {
        "confirmation_partition": {
            "confirmation_count": len(identities),
            "default_confirmation_identity_sha256": identity_sha256,
            "first_target": identity_rows[0],
            "identical_confirmation_ids": "PASS",
            "identity_authority": (
                "SEALED_FIXED_LAST_300_SPLIT_ON_MATCHING_DATASET_CONTENT_SHA256"
            ),
            "identity_digest_canonical_form": "LCJ-1_ARRAY_OF_ORDERED_IDENTITIES",
            "identity_sha256": identity_sha256,
            "last_target": identity_rows[-1],
            "observation_identities": identity_rows,
            "split_method": TEMPORAL_HOLDOUT_SPLIT_METHOD,
            "winner_confirmation_identity_sha256": identity_sha256,
        },
        "controls": {
            "confirmation_leakage": False,
            "default_evaluation_count": default_evaluator.call_count,
            "full_history_role": "DESCRIPTIVE_ONLY_NOT_EVALUATED_IN_R2",
            "full_history_selection": False,
            "new_candidate_search": False,
            "parameter_tuning": False,
            "promotion_authorized": False,
            "r1_result_sha256_verification": "PASS",
            "winner_evaluation_count": 0,
            "winner_stored_confirmation_verification": "PASS",
        },
        "default_confirmation_result": {
            "candidate_id": DEFAULT_CANDIDATE_ID,
            "exact_parameters": authority.default_parameters,
            "metric_details": default_evaluation.result.canonical_dict(),
            "objective_contract": _objective_contract(),
            "objective_values": _serialized_objective_values(default_values),
            "source": "SINGLE_CANONICAL_EVALUATION",
        },
        "head_to_head": {
            "avg_match_head_to_head_delta": _exact(deltas[0]),
            "delta_direction": "WINNER_MINUS_DEFAULT",
            "m3_plus_head_to_head_delta": _exact(deltas[1]),
            "point_estimate_classification": classification,
            "point_estimate_classification_rule": (
                "REUSE_R1_LEXICOGRAPHIC_OBJECTIVE_ORDER_FIRST_NONZERO_DELTA"
            ),
        },
        "paired_evidence": {
            "reason": (
                "SEALED_R1_ARTIFACT_HAS_NO_WINNER_PER_DRAW_OUTCOMES_AND_WINNER_"
                "REEVALUATION_IS_FORBIDDEN"
            ),
            "status": PAIRED_EVIDENCE_STATUS,
        },
        "promotion_decision": PROMOTION_DECISION,
        "r1_authority": {
            "base_commit": CAMPAIGN_BASE_COMMIT,
            "database_sha256": authority.database_sha256,
            "dataset_content_sha256": authority.dataset_content_sha256,
            "result_file": authority.result_file,
            "result_sha256": authority.result_sha256,
            "study_id": R1_STUDY_ID,
        },
        "schema_id": SCHEMA_ID,
        "schema_version": SCHEMA_VERSION,
        "significance_result": {
            "reason": (
                "NO_EXISTING_CANONICAL_TWO_SAMPLE_UTILITY_DIRECTLY_APPLIES_"
                "WITHOUT_WINNER_PER_DRAW_OUTCOMES"
            ),
            "status": SIGNIFICANCE_RESULT_STATUS,
        },
        "study_id": STUDY_ID,
        "winner_confirmation_result": {
            "candidate_id": WINNER_CANDIDATE_ID,
            "exact_parameters": authority.winner_parameters,
            "objective_contract": _objective_contract(),
            "objective_values": _serialized_objective_values(winner_values),
            "source": "SEALED_R1_ARTIFACT_REUSED",
        },
    }
    canonical_json.validate_value_domain(result_document)
    return R2Execution(
        result_document=result_document,
        winner_confirmation_values=winner_values,
        default_confirmation_values=default_values,
        head_to_head_deltas=deltas,
        point_estimate_classification=classification,
        winner_evaluation_count=0,
        default_evaluation_count=default_evaluator.call_count,
    )


__all__ = [
    "AVG_MATCH_OBJECTIVE_ID",
    "CAMPAIGN_BASE_COMMIT",
    "DEFAULT_CANDIDATE_ID",
    "M3_OBJECTIVE_ID",
    "PAIRED_EVIDENCE_STATUS",
    "PROMOTION_DECISION",
    "R1_EXPECTED_RESULT_SHA256",
    "SCHEMA_ID",
    "SCHEMA_VERSION",
    "SIGNIFICANCE_RESULT_STATUS",
    "STUDY_ID",
    "WINNER_CANDIDATE_ID",
    "BaselineHeadToHeadR2Error",
    "ConfirmationObservationIdentity",
    "R2Execution",
    "run_native_study_campaign_confirmation_baseline_headtohead_r2",
]
