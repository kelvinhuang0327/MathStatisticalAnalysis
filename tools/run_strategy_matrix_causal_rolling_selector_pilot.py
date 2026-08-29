"""Run the causal rolling-selector versus frozen-strategy research pilot.

The runner consumes three already-sealed historical replay authorities read-only.
For every lottery/native-ticket-count cell it fixes one candidate universe and one
intersection of complete targets.  Strategy selection for target ``t`` sees exactly
the preceding W comparable targets and never the current or a future outcome.

This is a historical research pilot.  It does not claim predictive advantage,
profitability, statistical significance, or production readiness.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from collections import Counter, defaultdict
from collections.abc import Generator, Iterable, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from decimal import Decimal, localcontext
from fractions import Fraction
from pathlib import Path
from typing import Any, cast

from lottolab.domain.prize_evaluation import DAILY_FIVE39_PRIZE_RULE_CONTRACT

STUDY_ID = "STRATEGY_MATRIX_CAUSAL_ROLLING_SELECTOR_PILOT_V1"
TASK_ID = "STRATEGY_MATRIX_CAUSAL_ROLLING_SELECTOR_PILOT_R1"
SCHEMA_VERSION = "STRATEGY_MATRIX_CAUSAL_ROLLING_SELECTOR_PILOT_RESULT_V1"
PRIMARY_METRIC_ID = "OFFICIAL_ANY_PRIZE_TARGET_RATE"
WINDOWS: tuple[tuple[str, int], ...] = (
    ("SHORT", 50),
    ("MEDIUM", 300),
    ("LONG", 750),
)
EXPECTED_BASE_HEAD = "0645f31a2bcaf494760d4bc1675bc1c3ed9a076d"
EXPECTED_BASE_TREE = "8b9fa40728f1bea3fb585d86f426a36489e0debf"

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_AUTHORITY_ROOT = Path.home() / "Library" / "Application Support" / "LottoLab"
DEFAULT_B649_AUTHORITY_DIRECTORY = (
    DEFAULT_AUTHORITY_ROOT / "authorities" / "big_lotto" / "exact_native_k2_k3"
)
DEFAULT_T539_AUTHORITY = (
    DEFAULT_AUTHORITY_ROOT / "authorities" / "daily_539" / "historical.sqlite3"
)
DEFAULT_P638_REPLAY_AUTHORITY = (
    DEFAULT_AUTHORITY_ROOT / "authorities" / "power_lotto" / "current_replay.sqlite3"
)
DEFAULT_P638_RANKING_AUTHORITY = (
    DEFAULT_AUTHORITY_ROOT / "authorities" / "power_lotto" / "current_ranking.sqlite3"
)
DEFAULT_OUTPUT_JSON = (
    REPOSITORY_ROOT
    / "docs/research/matrix-native-results/"
    "strategy-matrix-causal-rolling-selector-pilot-r1-result.json"
)
DEFAULT_OUTPUT_REPORT = (
    REPOSITORY_ROOT
    / "docs/research/strategy-matrix-causal-rolling-selector-pilot-r1.md"
)

_B649_REQUIRED_FILES = (
    "promotion_provenance.json",
    "ranking.json",
    "sealed_manifest.json",
    "target_evidence.jsonl",
)
_P638_TIER_COUNT = 10
_T539_WINNING_HITS = frozenset(
    match_count
    for match_count in range(6)
    if DAILY_FIVE39_PRIZE_RULE_CONTRACT.resolve(match_count=match_count) is not None
)


class PilotDataError(ValueError):
    """The canonical authority cannot support a deterministic causal comparison."""


@dataclass(frozen=True, slots=True)
class TargetRef:
    draw_id: str
    draw_date: str
    order: int

    @property
    def chronological_key(self) -> tuple[str, int]:
        return (self.draw_date, _numeric_draw_id(self.draw_id))


@dataclass(frozen=True, slots=True)
class Candidate:
    strategy_id: str
    strategy_version: str
    display_name: str
    native_ticket_count: int
    minimum_history: int


@dataclass(frozen=True, slots=True)
class TargetOutcome:
    strategy_id: str
    strategy_version: str
    target: TargetRef
    causal_cutoff_draw_id: str
    causal_cutoff_date: str
    success: bool
    winning_ticket_count: int
    ticket_count: int
    prize_tier_counts: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class CellData:
    lottery_id: str
    native_ticket_count: int
    authority_target_count: int
    authority_targets: tuple[TargetRef, ...]
    candidates: tuple[Candidate, ...]
    comparable_targets: tuple[TargetRef, ...]
    outcomes_by_strategy: Mapping[str, Mapping[str, TargetOutcome]]
    coverage_exclusion_reason_target_ids: Mapping[str, frozenset[str]]
    source_authority_id: str
    selection_tie_break: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SelectionStep:
    target: TargetRef
    history_targets: tuple[TargetRef, ...]
    rolling_strategy_id: str
    frozen_strategy_id: str
    rolling_success: bool
    frozen_success: bool


@dataclass(frozen=True, slots=True)
class ExperimentEvaluation:
    label: str
    window: int
    status: str
    exclusion_reason: str | None
    cell: CellData
    frozen_strategy_id: str | None
    steps: tuple[SelectionStep, ...]

    @property
    def rolling_target_ids(self) -> tuple[str, ...]:
        return tuple(step.target.draw_id for step in self.steps)

    @property
    def frozen_target_ids(self) -> tuple[str, ...]:
        return tuple(step.target.draw_id for step in self.steps)


@dataclass(frozen=True, slots=True)
class SourceAuthority:
    authority_id: str
    lottery_id: str
    details: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class AuthorityPaths:
    b649_directory: Path
    t539_database: Path
    p638_replay_database: Path
    p638_ranking_database: Path

    def files(self) -> tuple[Path, ...]:
        return (
            *(self.b649_directory / name for name in _B649_REQUIRED_FILES),
            self.t539_database,
            self.p638_replay_database,
            self.p638_ranking_database,
        )


def _numeric_draw_id(value: str) -> int:
    if not value.isdecimal():
        raise PilotDataError(f"CAUSAL_TARGET_ORDER_UNRESOLVED: non-numeric draw id {value!r}")
    return int(value)


def _require_regular_file(path: Path) -> None:
    if path.is_symlink() or not path.is_file():
        raise PilotDataError(f"CANONICAL_REPLAY_DATA_INSUFFICIENT: {path} is not a regular file")


def sha256_file(path: Path) -> str:
    _require_regular_file(path)
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json_bytes(payload: Mapping[str, Any]) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def _canonical_compact_bytes(payload: object) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PilotDataError(f"invalid canonical JSON authority: {path}") from exc
    if not isinstance(value, dict):
        raise PilotDataError(f"canonical JSON authority is not an object: {path}")
    return cast(dict[str, Any], value)


@contextmanager
def _read_only_sqlite(path: Path) -> Generator[sqlite3.Connection]:
    _require_regular_file(path)
    uri = f"{path.resolve().as_uri()}?mode=ro&immutable=1"
    connection = sqlite3.connect(uri, uri=True, isolation_level=None)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA query_only=ON")
        row = connection.execute("PRAGMA query_only").fetchone()
        if row is None or int(row[0]) != 1:
            raise PilotDataError(f"read-only SQLite query gate failed: {path}")
        yield connection
    finally:
        connection.close()


def _verify_required_tables(
    connection: sqlite3.Connection,
    required: frozenset[str],
    *,
    authority: str,
) -> None:
    actual = {
        str(row[0])
        for row in connection.execute(
            "SELECT name FROM sqlite_schema WHERE type='table' ORDER BY name"
        )
    }
    missing = sorted(required - actual)
    if missing:
        raise PilotDataError(f"{authority} required tables missing: {missing}")


def _validate_target_order(targets: Sequence[TargetRef], *, authority: str) -> None:
    seen_ids: set[str] = set()
    previous_key: tuple[str, int] | None = None
    previous_order: int | None = None
    for target in targets:
        if target.draw_id in seen_ids:
            raise PilotDataError(f"DUPLICATE_REPLAY_TARGET: {authority}:{target.draw_id}")
        seen_ids.add(target.draw_id)
        key = target.chronological_key
        if previous_key is not None and key <= previous_key:
            raise PilotDataError(f"NON_MONOTONIC_TARGET_ORDER: {authority}:{target.draw_id}")
        if previous_order is not None and target.order <= previous_order:
            raise PilotDataError(f"NON_MONOTONIC_TARGET_ORDER: {authority}:{target.draw_id}")
        previous_key = key
        previous_order = target.order


def build_cell_data(
    *,
    lottery_id: str,
    native_ticket_count: int,
    authority_targets: Sequence[TargetRef],
    candidates: Sequence[Candidate],
    complete_outcomes: Sequence[TargetOutcome],
    coverage_exclusion_reason_target_ids: Mapping[str, Iterable[str]],
    source_authority_id: str,
    selection_tie_break: Sequence[str],
) -> CellData:
    """Validate and freeze one comparable lottery/ticket-count cell."""

    target_tuple = tuple(authority_targets)
    _validate_target_order(target_tuple, authority=f"{lottery_id}:K{native_ticket_count}")
    target_by_id = {target.draw_id: target for target in target_tuple}

    candidate_tuple = tuple(sorted(candidates, key=lambda item: item.strategy_id))
    if not candidate_tuple:
        raise PilotDataError(f"COMPARABLE_STRATEGY_UNIVERSE_UNRESOLVED: {lottery_id}")
    candidate_by_id: dict[str, Candidate] = {}
    for candidate in candidate_tuple:
        if candidate.native_ticket_count != native_ticket_count:
            raise PilotDataError("candidate native ticket count does not match its cell")
        if candidate.strategy_id in candidate_by_id:
            raise PilotDataError(
                f"DUPLICATE_STRATEGY_IDENTITY: {lottery_id}:{candidate.strategy_id}"
            )
        candidate_by_id[candidate.strategy_id] = candidate

    outcome_maps: dict[str, dict[str, TargetOutcome]] = {
        candidate.strategy_id: {} for candidate in candidate_tuple
    }
    previous_order_by_strategy: dict[str, int] = {}
    for outcome in complete_outcomes:
        candidate = candidate_by_id.get(outcome.strategy_id)
        if candidate is None or candidate.strategy_version != outcome.strategy_version:
            raise PilotDataError(
                f"COMPARABLE_STRATEGY_UNIVERSE_UNRESOLVED: unknown outcome identity "
                f"{outcome.strategy_id}@{outcome.strategy_version}"
            )
        canonical_target = target_by_id.get(outcome.target.draw_id)
        if canonical_target != outcome.target:
            raise PilotDataError(
                f"CAUSAL_TARGET_ORDER_UNRESOLVED: inconsistent target {outcome.target.draw_id}"
            )
        strategy_outcomes = outcome_maps[outcome.strategy_id]
        if outcome.target.draw_id in strategy_outcomes:
            raise PilotDataError(
                "DUPLICATE_REPLAY_ROW: "
                f"{lottery_id}:{native_ticket_count}:{outcome.strategy_id}:"
                f"{outcome.target.draw_id}"
            )
        previous_order = previous_order_by_strategy.get(outcome.strategy_id)
        if previous_order is not None and outcome.target.order <= previous_order:
            raise PilotDataError(
                "NON_MONOTONIC_TARGET_ORDER: "
                f"{lottery_id}:{outcome.strategy_id}:{outcome.target.draw_id}"
            )
        previous_order_by_strategy[outcome.strategy_id] = outcome.target.order
        cutoff_key = (
            outcome.causal_cutoff_date,
            _numeric_draw_id(outcome.causal_cutoff_draw_id),
        )
        if cutoff_key >= outcome.target.chronological_key:
            raise PilotDataError(
                "CAUSAL_HISTORY_LEAKAGE: "
                f"{lottery_id}:{outcome.strategy_id}:{outcome.target.draw_id}"
            )
        if outcome.ticket_count != native_ticket_count:
            raise PilotDataError(
                f"native ticket count mismatch for {outcome.strategy_id}:{outcome.target.draw_id}"
            )
        if not 0 <= outcome.winning_ticket_count <= outcome.ticket_count:
            raise PilotDataError("winning ticket count is outside its valid range")
        strategy_outcomes[outcome.target.draw_id] = outcome

    comparable = tuple(
        target
        for target in target_tuple
        if all(
            target.draw_id in outcome_maps[candidate.strategy_id]
            for candidate in candidate_tuple
        )
    )
    comparable_ids = {target.draw_id for target in comparable}
    excluded_ids = set(target_by_id) - comparable_ids
    frozen_reasons = {
        reason: frozenset(target_ids)
        for reason, target_ids in coverage_exclusion_reason_target_ids.items()
        if frozenset(target_ids)
    }
    explained_ids: set[str] = set()
    for target_ids in frozen_reasons.values():
        explained_ids.update(target_ids)
    unknown_reason_ids = explained_ids - set(target_by_id)
    if unknown_reason_ids:
        raise PilotDataError(
            f"coverage reasons reference unknown targets: {sorted(unknown_reason_ids)[:3]}"
        )
    unexplained = excluded_ids - explained_ids
    if unexplained:
        raise PilotDataError(
            "UNEXPLAINED_MISSING_STRATEGY_COVERAGE: "
            f"{lottery_id}:K{native_ticket_count}:{sorted(unexplained)[:3]}"
        )

    tier_lengths = {
        len(outcome.prize_tier_counts)
        for strategy_outcomes in outcome_maps.values()
        for outcome in strategy_outcomes.values()
    }
    if len(tier_lengths) > 1:
        raise PilotDataError("prize tier vector length changes within one cell")

    return CellData(
        lottery_id=lottery_id,
        native_ticket_count=native_ticket_count,
        authority_target_count=len(target_tuple),
        authority_targets=target_tuple,
        candidates=candidate_tuple,
        comparable_targets=comparable,
        outcomes_by_strategy=outcome_maps,
        coverage_exclusion_reason_target_ids=frozen_reasons,
        source_authority_id=source_authority_id,
        selection_tie_break=tuple(selection_tie_break),
    )


def _window_statistics(
    cell: CellData,
    strategy_id: str,
    history_targets: Sequence[TargetRef],
) -> tuple[int, tuple[int, ...], int]:
    outcomes = cell.outcomes_by_strategy[strategy_id]
    selected = [outcomes[target.draw_id] for target in history_targets]
    success_count = sum(outcome.success for outcome in selected)
    tier_length = len(selected[0].prize_tier_counts) if selected else 0
    tier_counts = tuple(
        sum(outcome.prize_tier_counts[index] for outcome in selected)
        for index in range(tier_length)
    )
    winning_ticket_count = sum(outcome.winning_ticket_count for outcome in selected)
    return success_count, tier_counts, winning_ticket_count


def _select_strategy(cell: CellData, history_targets: Sequence[TargetRef]) -> str:
    if not history_targets:
        raise PilotDataError("selector history must not be empty")
    ranked: list[tuple[tuple[object, ...], str]] = []
    for candidate in cell.candidates:
        success_count, tier_counts, winning_ticket_count = _window_statistics(
            cell, candidate.strategy_id, history_targets
        )
        if cell.lottery_id == "B649":
            key: tuple[object, ...] = (-success_count, candidate.strategy_id)
        else:
            key = (
                -success_count,
                tuple(-count for count in tier_counts),
                -winning_ticket_count,
                candidate.strategy_id,
            )
        ranked.append((key, candidate.strategy_id))
    ranked.sort(key=lambda item: item[0])
    return ranked[0][1]


def evaluate_cell(cell: CellData, *, label: str, window: int) -> ExperimentEvaluation:
    comparable = cell.comparable_targets
    if len(comparable) <= window:
        reason = (
            "NO_COMPLETE_FIXED_UNIVERSE_TARGET"
            if not comparable
            else "INSUFFICIENT_COMPARABLE_TARGETS_FOR_PRIOR_WINDOW_AND_CURRENT_TARGET"
        )
        return ExperimentEvaluation(
            label=label,
            window=window,
            status="EXCLUDED",
            exclusion_reason=reason,
            cell=cell,
            frozen_strategy_id=None,
            steps=(),
        )

    first_history = comparable[:window]
    frozen_strategy_id = _select_strategy(cell, first_history)
    steps: list[SelectionStep] = []
    for index in range(window, len(comparable)):
        target = comparable[index]
        history_targets = comparable[index - window : index]
        if len(history_targets) != window:
            raise PilotDataError("EXACT_PRIOR_WINDOW_BOUNDARY_VIOLATION")
        if any(history.order >= target.order for history in history_targets):
            raise PilotDataError("CAUSAL_HISTORY_LEAKAGE")
        rolling_strategy_id = _select_strategy(cell, history_targets)
        rolling_outcome = cell.outcomes_by_strategy[rolling_strategy_id][target.draw_id]
        frozen_outcome = cell.outcomes_by_strategy[frozen_strategy_id][target.draw_id]
        steps.append(
            SelectionStep(
                target=target,
                history_targets=tuple(history_targets),
                rolling_strategy_id=rolling_strategy_id,
                frozen_strategy_id=frozen_strategy_id,
                rolling_success=rolling_outcome.success,
                frozen_success=frozen_outcome.success,
            )
        )

    evaluation = ExperimentEvaluation(
        label=label,
        window=window,
        status="COMPLETE",
        exclusion_reason=None,
        cell=cell,
        frozen_strategy_id=frozen_strategy_id,
        steps=tuple(steps),
    )
    if evaluation.rolling_target_ids != evaluation.frozen_target_ids:
        raise PilotDataError("ROLLING_FROZEN_TARGET_SET_MISMATCH")
    return evaluation


def _fraction_payload(value: Fraction) -> dict[str, Any]:
    with localcontext() as context:
        context.prec = 40
        decimal_value = Decimal(value.numerator) / Decimal(value.denominator)
    return {
        "decimal_12": format(decimal_value, ".12f"),
        "denominator": value.denominator,
        "exact": f"{value.numerator}/{value.denominator}",
        "numerator": value.numerator,
    }


def _metric_payload(success_count: int, target_count: int) -> dict[str, Any]:
    if target_count <= 0:
        raise PilotDataError("metric target count must be positive")
    return {
        "metric_id": PRIMARY_METRIC_ID,
        "success_count": success_count,
        "target_count": target_count,
        "rate": _fraction_payload(Fraction(success_count, target_count)),
    }


def _coverage_payload(cell: CellData) -> dict[str, Any]:
    return {
        "authority_target_count": cell.authority_target_count,
        "comparable_target_count": len(cell.comparable_targets),
        "coverage_excluded_missing_target_count": (
            cell.authority_target_count - len(cell.comparable_targets)
        ),
        "coverage_exclusion_reason_target_counts": {
            reason: len(target_ids)
            for reason, target_ids in sorted(
                cell.coverage_exclusion_reason_target_ids.items()
            )
        },
        "first_comparable_target": (
            cell.comparable_targets[0].draw_id if cell.comparable_targets else None
        ),
        "last_comparable_target": (
            cell.comparable_targets[-1].draw_id if cell.comparable_targets else None
        ),
    }


def experiment_payload(evaluation: ExperimentEvaluation) -> dict[str, Any]:
    cell = evaluation.cell
    common: dict[str, Any] = {
        "candidate_strategy_count": len(cell.candidates),
        "coverage": _coverage_payload(cell),
        "eligible_target_count": len(evaluation.steps),
        "exclusion_reason": evaluation.exclusion_reason,
        "first_evaluated_target": (
            evaluation.steps[0].target.draw_id if evaluation.steps else None
        ),
        "frozen_baseline_strategy": evaluation.frozen_strategy_id,
        "history_warmup_target_count": min(evaluation.window, len(cell.comparable_targets)),
        "label": evaluation.label,
        "last_evaluated_target": (
            evaluation.steps[-1].target.draw_id if evaluation.steps else None
        ),
        "rolling_frozen_identical_target_set": True,
        "status": evaluation.status,
        "window": evaluation.window,
    }
    if evaluation.status != "COMPLETE":
        return {
            **common,
            "absolute_paired_delta": None,
            "conclusion": "INCONCLUSIVE_CANONICAL_COVERAGE_INSUFFICIENT",
            "frozen_baseline_primary_metric_result": None,
            "relative_paired_delta": None,
            "required_comparable_target_count": evaluation.window + 1,
            "rolling_selection_frequency": {},
            "rolling_selector_primary_metric_result": None,
            "rolling_strategy_switch_count": 0,
            "selection_trace_sha256": None,
        }

    rolling_success_count = sum(step.rolling_success for step in evaluation.steps)
    frozen_success_count = sum(step.frozen_success for step in evaluation.steps)
    target_count = len(evaluation.steps)
    rolling_rate = Fraction(rolling_success_count, target_count)
    frozen_rate = Fraction(frozen_success_count, target_count)
    delta = rolling_rate - frozen_rate
    relative_delta = delta / frozen_rate if frozen_rate else None
    frequencies = Counter(step.rolling_strategy_id for step in evaluation.steps)
    switches = sum(
        previous.rolling_strategy_id != current.rolling_strategy_id
        for previous, current in zip(evaluation.steps, evaluation.steps[1:], strict=False)
    )
    trace = [
        {
            "frozen_strategy_id": step.frozen_strategy_id,
            "history_first_target": step.history_targets[0].draw_id,
            "history_last_target": step.history_targets[-1].draw_id,
            "rolling_strategy_id": step.rolling_strategy_id,
            "target": step.target.draw_id,
        }
        for step in evaluation.steps
    ]
    conclusion = (
        "ROLLING_HISTORICALLY_EXCEEDED_PAIRED_CAUSAL_FROZEN_BASELINE"
        if delta > 0
        else (
            "ROLLING_HISTORICALLY_UNDERPERFORMED_PAIRED_CAUSAL_FROZEN_BASELINE"
            if delta < 0
            else "ROLLING_HISTORICALLY_MATCHED_PAIRED_CAUSAL_FROZEN_BASELINE"
        )
    )
    return {
        **common,
        "absolute_paired_delta": _fraction_payload(delta),
        "conclusion": conclusion,
        "frozen_baseline_primary_metric_result": _metric_payload(
            frozen_success_count, target_count
        ),
        "relative_paired_delta": (
            _fraction_payload(relative_delta) if relative_delta is not None else None
        ),
        "relative_paired_delta_undefined_reason": (
            None if relative_delta is not None else "FROZEN_BASELINE_RATE_IS_ZERO"
        ),
        "rolling_selection_frequency": {
            strategy_id: frequencies[strategy_id] for strategy_id in sorted(frequencies)
        },
        "rolling_selector_primary_metric_result": _metric_payload(
            rolling_success_count, target_count
        ),
        "rolling_strategy_switch_count": switches,
        "selection_trace_sha256": hashlib.sha256(
            _canonical_compact_bytes(trace)
        ).hexdigest(),
        "strictly_before_target_selection_checks": len(evaluation.steps),
    }


def _candidate_payload(candidate: Candidate) -> dict[str, Any]:
    return {
        "display_name": candidate.display_name,
        "minimum_history": candidate.minimum_history,
        "strategy_id": candidate.strategy_id,
        "strategy_version": candidate.strategy_version,
    }


def _parse_b649_authority(
    directory: Path,
    hashes: Mapping[Path, str],
) -> tuple[SourceAuthority, tuple[CellData, ...]]:
    provenance_path = directory / "promotion_provenance.json"
    ranking_path = directory / "ranking.json"
    manifest_path = directory / "sealed_manifest.json"
    evidence_path = directory / "target_evidence.jsonl"
    provenance = _load_json_object(provenance_path)
    ranking = _load_json_object(ranking_path)
    manifest = _load_json_object(manifest_path)

    expected_hashes = {
        evidence_path: provenance.get("replay_sha256"),
        ranking_path: provenance.get("ranking_sha256"),
        manifest_path: provenance.get("manifest_sha256"),
    }
    for path, expected in expected_hashes.items():
        if not isinstance(expected, str) or hashes[path] != expected:
            raise PilotDataError(f"B649 sealed authority hash mismatch: {path}")
    if provenance.get("metric") != "OFFICIAL_ANY_PRIZE":
        raise PilotDataError("B649 canonical primary metric is not OFFICIAL_ANY_PRIZE")
    raw_ranking_contract = ranking.get("ranking_contract")
    if not isinstance(raw_ranking_contract, dict):
        raise PilotDataError("B649 ranking contract primary metric is ambiguous")
    ranking_contract = cast(dict[str, Any], raw_ranking_contract)
    if ranking_contract.get("primary_metric") != "OFFICIAL_ANY_PRIZE_RATE":
        raise PilotDataError("B649 ranking contract primary metric is ambiguous")
    raw_execution_contract = manifest.get("execution_contract")
    if not isinstance(raw_execution_contract, dict):
        raise PilotDataError("B649 target-outcome exclusion contract is not sealed")
    execution_contract = cast(dict[str, Any], raw_execution_contract)
    if execution_contract.get("target_outcome_excluded") is not True:
        raise PilotDataError("B649 target-outcome exclusion contract is not sealed")

    candidates_by_count: dict[int, dict[str, Candidate]] = defaultdict(dict)
    targets_by_count: dict[int, dict[str, TargetRef]] = defaultdict(dict)
    outcomes_by_count: dict[int, list[TargetOutcome]] = defaultdict(list)
    reasons_by_count: dict[int, dict[str, set[str]]] = defaultdict(
        lambda: defaultdict(set)
    )
    previous_key: dict[tuple[int, str], tuple[str, int]] = {}
    record_count = 0
    with evidence_path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            try:
                raw = json.loads(line)
            except json.JSONDecodeError as exc:
                raise PilotDataError(
                    f"B649 target evidence JSON is invalid at line {line_number}"
                ) from exc
            if not isinstance(raw, dict):
                raise PilotDataError("B649 target evidence row is not an object")
            row = cast(dict[str, Any], raw)
            record_count += 1
            ticket_count = int(row["native_ticket_count"])
            strategy_id = str(row["strategy_id"])
            strategy_version = str(row["strategy_version"])
            draw_id = str(row["target_draw_number"])
            draw_date = str(row["target_draw_date"])
            key = (draw_date, _numeric_draw_id(draw_id))
            prior_key = previous_key.get((ticket_count, strategy_id))
            if prior_key is not None and key <= prior_key:
                raise PilotDataError(
                    f"NON_MONOTONIC_TARGET_ORDER: B649:{strategy_id}:{draw_id}"
                )
            previous_key[(ticket_count, strategy_id)] = key
            candidate = Candidate(
                strategy_id=strategy_id,
                strategy_version=strategy_version,
                display_name=str(row["display_name"]),
                native_ticket_count=ticket_count,
                minimum_history=0,
            )
            existing_candidate = candidates_by_count[ticket_count].get(strategy_id)
            if existing_candidate is not None and existing_candidate != candidate:
                raise PilotDataError(f"B649 candidate identity drift: {strategy_id}")
            candidates_by_count[ticket_count][strategy_id] = candidate
            existing_target = targets_by_count[ticket_count].get(draw_id)
            provisional_target = TargetRef(draw_id=draw_id, draw_date=draw_date, order=-1)
            if existing_target is not None and (
                existing_target.draw_date != provisional_target.draw_date
            ):
                raise PilotDataError(f"B649 target identity drift: {draw_id}")
            targets_by_count[ticket_count].setdefault(draw_id, provisional_target)

            replay_status = str(row["replay_status"])
            if replay_status != "COMPLETE":
                reasons_by_count[ticket_count][replay_status].add(draw_id)
                continue
            success = row.get("official_any_prize")
            if not isinstance(success, bool):
                raise PilotDataError("B649 complete row lacks boolean official_any_prize")
            if row.get("target_outcome_excluded") is not True:
                raise PilotDataError("CAUSAL_HISTORY_LEAKAGE: B649 outcome exclusion absent")
            raw_tickets = row.get("ticket_evaluations")
            if not isinstance(raw_tickets, list):
                raise PilotDataError("B649 ticket evaluation count mismatch")
            ticket_rows = cast(list[Any], raw_tickets)
            if len(ticket_rows) != ticket_count:
                raise PilotDataError("B649 ticket evaluation count mismatch")
            if not all(isinstance(item, dict) for item in ticket_rows):
                raise PilotDataError("B649 ticket evaluation row is not an object")
            tickets = cast(list[dict[str, Any]], ticket_rows)
            winning_ticket_count = sum(
                item.get("is_winner") is True for item in tickets
            )
            outcomes_by_count[ticket_count].append(
                TargetOutcome(
                    strategy_id=strategy_id,
                    strategy_version=strategy_version,
                    target=provisional_target,
                    causal_cutoff_draw_id=str(row["causal_cutoff_draw_number"]),
                    causal_cutoff_date=str(row["causal_cutoff_date"]),
                    success=success,
                    winning_ticket_count=winning_ticket_count,
                    ticket_count=ticket_count,
                    prize_tier_counts=(),
                )
            )

    replay_rows = provenance.get("replay_rows")
    if not isinstance(replay_rows, int) or replay_rows != record_count:
        raise PilotDataError("B649 replay row count differs from promotion provenance")

    cells: list[CellData] = []
    raw_tie_break = ranking_contract.get("tie_break")
    if not isinstance(raw_tie_break, list):
        raise PilotDataError("B649 canonical tie-break is invalid")
    tie_break_values = cast(list[Any], raw_tie_break)
    if not all(isinstance(item, str) for item in tie_break_values):
        raise PilotDataError("B649 canonical tie-break is invalid")
    tie_break = cast(list[str], tie_break_values)
    for ticket_count in sorted(candidates_by_count):
        sorted_targets = sorted(
            targets_by_count[ticket_count].values(),
            key=lambda target: target.chronological_key,
        )
        canonical_targets = tuple(
            TargetRef(target.draw_id, target.draw_date, index)
            for index, target in enumerate(sorted_targets)
        )
        target_lookup = {target.draw_id: target for target in canonical_targets}
        canonical_outcomes = tuple(
            TargetOutcome(
                strategy_id=outcome.strategy_id,
                strategy_version=outcome.strategy_version,
                target=target_lookup[outcome.target.draw_id],
                causal_cutoff_draw_id=outcome.causal_cutoff_draw_id,
                causal_cutoff_date=outcome.causal_cutoff_date,
                success=outcome.success,
                winning_ticket_count=outcome.winning_ticket_count,
                ticket_count=outcome.ticket_count,
                prize_tier_counts=outcome.prize_tier_counts,
            )
            for outcome in outcomes_by_count[ticket_count]
        )
        cells.append(
            build_cell_data(
                lottery_id="B649",
                native_ticket_count=ticket_count,
                authority_targets=canonical_targets,
                candidates=tuple(candidates_by_count[ticket_count].values()),
                complete_outcomes=canonical_outcomes,
                coverage_exclusion_reason_target_ids=reasons_by_count[ticket_count],
                source_authority_id="B649_EXACT_NATIVE_K2_K3",
                selection_tie_break=tie_break,
            )
        )

    authority = SourceAuthority(
        authority_id="B649_EXACT_NATIVE_K2_K3",
        lottery_id="B649",
        details={
            "authority_directory": str(directory.resolve()),
            "canonical_relative_path": provenance.get("canonical_relative_path"),
            "files": {
                path.name: {"sha256": hashes[path], "size_bytes": path.stat().st_size}
                for path in sorted(hashes, key=lambda item: item.name)
                if path.parent == directory
            },
            "primary_metric": ranking_contract.get("primary_metric"),
            "run_id": manifest.get("run_id"),
            "source_head": provenance.get("source_head"),
            "source_tree": provenance.get("source_tree"),
            "stability_verified_before_after_load": True,
            "success_unit": ranking_contract.get("success_unit"),
            "tie_break": tie_break,
        },
    )
    return authority, tuple(cells)


def _parse_t539_authority(
    database: Path,
    database_sha256: str,
) -> tuple[SourceAuthority, tuple[CellData, ...]]:
    required_tables = frozenset(
        {
            "prediction_scores",
            "prediction_tickets",
            "run_metadata",
            "source_draws",
            "strategy_coverage",
            "target_completion",
        }
    )
    with _read_only_sqlite(database) as connection:
        _verify_required_tables(connection, required_tables, authority="T539")
        metadata_rows = connection.execute(
            "SELECT run_id,schema_version,source_endpoint,source_sha256,as_of_date,"
            "adapter_source_commit,status FROM run_metadata ORDER BY run_id"
        ).fetchall()
        if len(metadata_rows) != 1 or str(metadata_rows[0]["status"]) != "COMPLETE":
            raise PilotDataError("T539 canonical run is not uniquely complete")
        metadata = metadata_rows[0]
        run_id = str(metadata["run_id"])

        target_rows = connection.execute(
            "SELECT draw_id,draw_date,draw_order FROM source_draws ORDER BY draw_order"
        ).fetchall()
        targets = tuple(
            TargetRef(str(row["draw_id"]), str(row["draw_date"]), int(row["draw_order"]))
            for row in target_rows
        )
        if any(target.order != index for index, target in enumerate(targets)):
            raise PilotDataError(
                "NON_MONOTONIC_TARGET_ORDER: T539 draw_order is not contiguous"
            )
        _validate_target_order(targets, authority="T539")
        target_by_id = {target.draw_id: target for target in targets}

        coverage_rows = connection.execute(
            "SELECT strategy_id,strategy_version,native_ticket_count,min_history,"
            "expected_target_draw_count,processed_target_draw_count,"
            "successful_target_draw_count,failed_target_draw_count,status "
            "FROM strategy_coverage WHERE run_id=? "
            "ORDER BY native_ticket_count,strategy_id,strategy_version",
            (run_id,),
        ).fetchall()
        candidates_by_count: dict[int, list[Candidate]] = defaultdict(list)
        for row in coverage_rows:
            minimum_history = int(row["min_history"])
            expected = len(targets) - minimum_history
            observed_counts = (
                int(row["expected_target_draw_count"]),
                int(row["processed_target_draw_count"]),
                int(row["successful_target_draw_count"]),
            )
            if (
                str(row["status"]) != "COMPLETE"
                or observed_counts != (expected, expected, expected)
                or int(row["failed_target_draw_count"]) != 0
            ):
                raise PilotDataError("T539 strategy coverage is not complete and comparable")
            ticket_count = int(row["native_ticket_count"])
            strategy_id = str(row["strategy_id"])
            candidates_by_count[ticket_count].append(
                Candidate(
                    strategy_id=strategy_id,
                    strategy_version=str(row["strategy_version"]),
                    display_name=strategy_id,
                    native_ticket_count=ticket_count,
                    minimum_history=minimum_history,
                )
            )

        outcome_rows = connection.execute(
            """
            SELECT c.native_ticket_count,tc.strategy_id,tc.strategy_version,
                   tc.target_draw_id,d.draw_date,d.draw_order,
                   MIN(pt.cutoff_draw_id) AS cutoff_draw_id,
                   MAX(pt.cutoff_draw_id) AS cutoff_draw_id_max,
                   MIN(pt.cutoff_draw_date) AS cutoff_draw_date,
                   MAX(pt.cutoff_draw_date) AS cutoff_draw_date_max,
                   COUNT(ps.ticket_position) AS ticket_count,
                   SUM(CASE WHEN ps.hits IN (2,3,4,5) THEN 1 ELSE 0 END)
                       AS winning_ticket_count,
                   SUM(CASE WHEN ps.hits=5 THEN 1 ELSE 0 END) AS tier_1,
                   SUM(CASE WHEN ps.hits=4 THEN 1 ELSE 0 END) AS tier_2,
                   SUM(CASE WHEN ps.hits=3 THEN 1 ELSE 0 END) AS tier_3,
                   SUM(CASE WHEN ps.hits=2 THEN 1 ELSE 0 END) AS tier_4
            FROM target_completion tc
            JOIN strategy_coverage c
              ON c.run_id=tc.run_id AND c.strategy_id=tc.strategy_id
             AND c.strategy_version=tc.strategy_version
            JOIN source_draws d ON d.draw_id=tc.target_draw_id
            JOIN prediction_tickets pt
              ON pt.run_id=tc.run_id AND pt.strategy_id=tc.strategy_id
             AND pt.strategy_version=tc.strategy_version
             AND pt.target_draw_id=tc.target_draw_id
            JOIN prediction_scores ps
              ON ps.run_id=pt.run_id AND ps.strategy_id=pt.strategy_id
             AND ps.strategy_version=pt.strategy_version
             AND ps.target_draw_id=pt.target_draw_id
             AND ps.ticket_position=pt.ticket_position
            WHERE tc.run_id=? AND tc.status='SUCCESS'
            GROUP BY c.native_ticket_count,tc.strategy_id,tc.strategy_version,
                     tc.target_draw_id,d.draw_date,d.draw_order
            ORDER BY c.native_ticket_count,tc.strategy_id,tc.strategy_version,d.draw_order
            """,
            (run_id,),
        )
        outcomes_by_count: dict[int, list[TargetOutcome]] = defaultdict(list)
        outcome_count_by_strategy: Counter[tuple[str, str]] = Counter()
        for row in outcome_rows:
            if row["cutoff_draw_id"] != row["cutoff_draw_id_max"] or row[
                "cutoff_draw_date"
            ] != row["cutoff_draw_date_max"]:
                raise PilotDataError("T539 target tickets disagree on causal cutoff")
            ticket_count = int(row["native_ticket_count"])
            actual_ticket_count = int(row["ticket_count"])
            if actual_ticket_count != ticket_count:
                raise PilotDataError("T539 native ticket result count mismatch")
            winning_ticket_count = int(row["winning_ticket_count"])
            strategy_id = str(row["strategy_id"])
            strategy_version = str(row["strategy_version"])
            outcome_count_by_strategy[(strategy_id, strategy_version)] += 1
            target = target_by_id[str(row["target_draw_id"])]
            outcomes_by_count[ticket_count].append(
                TargetOutcome(
                    strategy_id=strategy_id,
                    strategy_version=strategy_version,
                    target=target,
                    causal_cutoff_draw_id=str(row["cutoff_draw_id"]),
                    causal_cutoff_date=str(row["cutoff_draw_date"]),
                    success=winning_ticket_count > 0,
                    winning_ticket_count=winning_ticket_count,
                    ticket_count=actual_ticket_count,
                    prize_tier_counts=tuple(int(row[f"tier_{index}"]) for index in range(1, 5)),
                )
            )

        for row in coverage_rows:
            identity = (str(row["strategy_id"]), str(row["strategy_version"]))
            if outcome_count_by_strategy[identity] != int(row["expected_target_draw_count"]):
                raise PilotDataError(f"T539 outcome coverage mismatch: {identity[0]}")

    cells: list[CellData] = []
    for ticket_count in sorted(candidates_by_count):
        candidates = candidates_by_count[ticket_count]
        common_minimum_history = max(candidate.minimum_history for candidate in candidates)
        pre_eligibility = {
            target.draw_id for target in targets if target.order < common_minimum_history
        }
        cells.append(
            build_cell_data(
                lottery_id="T539",
                native_ticket_count=ticket_count,
                authority_targets=targets,
                candidates=candidates,
                complete_outcomes=outcomes_by_count[ticket_count],
                coverage_exclusion_reason_target_ids={
                    "FIXED_UNIVERSE_PRE_ELIGIBILITY_MINIMUM_HISTORY": pre_eligibility
                },
                source_authority_id="T539_HISTORICAL_SQLITE",
                selection_tie_break=(
                    "OFFICIAL_ANY_PRIZE_TARGET_RATE_DESC",
                    "OFFICIAL_PRIZE_TIER_COUNT_VECTOR_DESC",
                    "OFFICIAL_WINNING_TICKET_RATE_DESC",
                    "STRATEGY_ID_ASC",
                ),
            )
        )

    authority = SourceAuthority(
        authority_id="T539_HISTORICAL_SQLITE",
        lottery_id="T539",
        details={
            "adapter_source_commit": str(metadata["adapter_source_commit"]),
            "as_of_date": str(metadata["as_of_date"]),
            "authority_path": str(database.resolve()),
            "authority_sha256": database_sha256,
            "authority_size_bytes": database.stat().st_size,
            "primary_metric": PRIMARY_METRIC_ID,
            "prize_rule_definition_sha256": DAILY_FIVE39_PRIZE_RULE_CONTRACT.source_sha256,
            "prize_rule_source": DAILY_FIVE39_PRIZE_RULE_CONTRACT.source_locator,
            "prize_rule_version": DAILY_FIVE39_PRIZE_RULE_CONTRACT.schema_version,
            "run_id": run_id,
            "schema_version": str(metadata["schema_version"]),
            "source_dataset_sha256": str(metadata["source_sha256"]),
            "source_endpoint": str(metadata["source_endpoint"]),
            "stability_verified_before_after_load": True,
        },
    )
    return authority, tuple(cells)


def _parse_p638_authority(
    replay_database: Path,
    ranking_database: Path,
    replay_sha256: str,
    ranking_sha256: str,
) -> tuple[SourceAuthority, tuple[CellData, ...]]:
    required_tables = frozenset(
        {
            "p638_current_ranking",
            "p638_current_run",
            "p638_current_strategy",
            "p638_current_target",
            "p638_current_ticket",
        }
    )
    with _read_only_sqlite(ranking_database) as connection:
        _verify_required_tables(connection, required_tables, authority="P638_CURRENT")
        run_rows = connection.execute("SELECT * FROM p638_current_run ORDER BY run_id").fetchall()
        if len(run_rows) != 1:
            raise PilotDataError("P638 current ranking authority does not contain one run")
        run = run_rows[0]
        run_id = str(run["run_id"])
        if str(run["source_replay_db_sha256"]) != replay_sha256:
            raise PilotDataError("P638 current ranking source replay SHA-256 mismatch")
        if int(run["excluded_strategy_count"]) != 0 or int(
            run["eligible_target_failure_count"]
        ) != 0:
            raise PilotDataError("P638 current ranking run is not canonically complete")

        target_rows = connection.execute(
            "SELECT DISTINCT target_draw_number,target_draw_date "
            "FROM p638_current_target ORDER BY target_draw_date,CAST(target_draw_number AS INTEGER)"
        ).fetchall()
        targets = tuple(
            TargetRef(str(row["target_draw_number"]), str(row["target_draw_date"]), index)
            for index, row in enumerate(target_rows)
        )
        if len(targets) != int(run["draw_count"]):
            raise PilotDataError("P638 target authority count differs from run metadata")
        _validate_target_order(targets, authority="P638")
        target_by_id = {target.draw_id: target for target in targets}
        if (
            targets[0].draw_id != str(run["first_draw_number"])
            or targets[-1].draw_id != str(run["last_draw_number"])
        ):
            raise PilotDataError("P638 run target bounds mismatch")

        strategy_rows = connection.execute(
            "SELECT strategy_id,strategy_version,native_ticket_count,min_history "
            "FROM p638_current_strategy WHERE run_id=? "
            "ORDER BY native_ticket_count,strategy_id",
            (run_id,),
        ).fetchall()
        if len(strategy_rows) != int(run["strategy_count"]):
            raise PilotDataError("P638 strategy count differs from run metadata")
        candidates_by_count: dict[int, list[Candidate]] = defaultdict(list)
        for row in strategy_rows:
            ticket_count = int(row["native_ticket_count"])
            strategy_id = str(row["strategy_id"])
            candidates_by_count[ticket_count].append(
                Candidate(
                    strategy_id=strategy_id,
                    strategy_version=str(row["strategy_version"]),
                    display_name=strategy_id,
                    native_ticket_count=ticket_count,
                    minimum_history=int(row["min_history"]),
                )
            )

        projection_rows = connection.execute(
            """
            SELECT s.native_ticket_count,t.strategy_id,t.strategy_version,
                   t.target_draw_number,t.target_draw_date,
                   t.cutoff_draw_number,
                   t.expected_ticket_count,t.status,t.target_is_winner,
                   COUNT(ticket.id) AS ticket_count,
                   COALESCE(SUM(ticket.is_winner),0) AS winning_ticket_count,
                   COALESCE(SUM(CASE WHEN ticket.prize_tier_order=1 THEN 1 ELSE 0 END),0)
                       AS tier_1,
                   COALESCE(SUM(CASE WHEN ticket.prize_tier_order=2 THEN 1 ELSE 0 END),0)
                       AS tier_2,
                   COALESCE(SUM(CASE WHEN ticket.prize_tier_order=3 THEN 1 ELSE 0 END),0)
                       AS tier_3,
                   COALESCE(SUM(CASE WHEN ticket.prize_tier_order=4 THEN 1 ELSE 0 END),0)
                       AS tier_4,
                   COALESCE(SUM(CASE WHEN ticket.prize_tier_order=5 THEN 1 ELSE 0 END),0)
                       AS tier_5,
                   COALESCE(SUM(CASE WHEN ticket.prize_tier_order=6 THEN 1 ELSE 0 END),0)
                       AS tier_6,
                   COALESCE(SUM(CASE WHEN ticket.prize_tier_order=7 THEN 1 ELSE 0 END),0)
                       AS tier_7,
                   COALESCE(SUM(CASE WHEN ticket.prize_tier_order=8 THEN 1 ELSE 0 END),0)
                       AS tier_8,
                   COALESCE(SUM(CASE WHEN ticket.prize_tier_order=9 THEN 1 ELSE 0 END),0)
                       AS tier_9,
                   COALESCE(SUM(CASE WHEN ticket.prize_tier_order=10 THEN 1 ELSE 0 END),0)
                       AS tier_10
            FROM p638_current_target t
            JOIN p638_current_strategy s
              ON s.run_id=t.run_id AND s.strategy_id=t.strategy_id
            LEFT JOIN p638_current_ticket ticket ON ticket.target_id=t.id
            WHERE t.run_id=?
            GROUP BY s.native_ticket_count,t.id,t.strategy_id,t.strategy_version,
                     t.target_draw_number,t.target_draw_date,
                     t.cutoff_draw_number,
                     t.expected_ticket_count,t.status,t.target_is_winner
            ORDER BY s.native_ticket_count,t.strategy_id,
                     t.target_draw_date,CAST(t.target_draw_number AS INTEGER)
            """,
            (run_id,),
        ).fetchall()

    candidate_identity_by_count = {
        ticket_count: {candidate.strategy_id: candidate for candidate in candidates}
        for ticket_count, candidates in candidates_by_count.items()
    }
    outcomes_by_count: dict[int, list[TargetOutcome]] = defaultdict(list)
    reasons_by_count: dict[int, dict[str, set[str]]] = defaultdict(
        lambda: defaultdict(set)
    )
    target_row_count_by_strategy: Counter[tuple[str, str]] = Counter()
    for row in projection_rows:
        ticket_count = int(row["native_ticket_count"])
        strategy_id = str(row["strategy_id"])
        strategy_version = str(row["strategy_version"])
        candidate = candidate_identity_by_count[ticket_count].get(strategy_id)
        if candidate is None or candidate.strategy_version != strategy_version:
            raise PilotDataError("P638 projection contains an unknown strategy identity")
        target_row_count_by_strategy[(strategy_id, strategy_version)] += 1
        draw_id = str(row["target_draw_number"])
        target = target_by_id[draw_id]
        status = str(row["status"])
        if status != "COMPLETE":
            reasons_by_count[ticket_count][status].add(draw_id)
            if row["target_is_winner"] is not None:
                raise PilotDataError("P638 excluded target contains a winning outcome")
            continue
        cutoff_draw_id = row["cutoff_draw_number"]
        if cutoff_draw_id is None or str(cutoff_draw_id) not in target_by_id:
            raise PilotDataError("P638 complete target lacks a canonical causal cutoff")
        cutoff_target = target_by_id[str(cutoff_draw_id)]
        actual_ticket_count = int(row["ticket_count"])
        if actual_ticket_count != ticket_count or int(row["expected_ticket_count"]) != ticket_count:
            raise PilotDataError("P638 native ticket result count mismatch")
        winning_ticket_count = int(row["winning_ticket_count"])
        target_is_winner = int(row["target_is_winner"])
        if target_is_winner != int(winning_ticket_count > 0):
            raise PilotDataError("P638 target winner flag disagrees with ticket evidence")
        outcomes_by_count[ticket_count].append(
            TargetOutcome(
                strategy_id=strategy_id,
                strategy_version=strategy_version,
                target=target,
                causal_cutoff_draw_id=cutoff_target.draw_id,
                causal_cutoff_date=cutoff_target.draw_date,
                success=bool(target_is_winner),
                winning_ticket_count=winning_ticket_count,
                ticket_count=actual_ticket_count,
                prize_tier_counts=tuple(
                    int(row[f"tier_{index}"]) for index in range(1, _P638_TIER_COUNT + 1)
                ),
            )
        )

    for candidates in candidates_by_count.values():
        for candidate in candidates:
            if target_row_count_by_strategy[
                (candidate.strategy_id, candidate.strategy_version)
            ] != len(targets):
                raise PilotDataError(f"P638 target coverage mismatch: {candidate.strategy_id}")

    cells = tuple(
        build_cell_data(
            lottery_id="P638",
            native_ticket_count=ticket_count,
            authority_targets=targets,
            candidates=candidates_by_count[ticket_count],
            complete_outcomes=outcomes_by_count[ticket_count],
            coverage_exclusion_reason_target_ids=reasons_by_count[ticket_count],
            source_authority_id="P638_CURRENT_REPLAY_AND_RANKING",
            selection_tie_break=(
                "WINNING_TARGET_RATE_DESC",
                "OFFICIAL_PRIZE_TIER_COUNT_VECTOR_DESC",
                "WINNING_TICKET_RATE_DESC",
                "WINNING_TARGET_COUNT_DESC",
                "ELIGIBLE_TARGET_COUNT_DESC",
                "STRATEGY_ID_ASC",
            ),
        )
        for ticket_count in sorted(candidates_by_count)
    )
    authority = SourceAuthority(
        authority_id="P638_CURRENT_REPLAY_AND_RANKING",
        lottery_id="P638",
        details={
            "contract_version": str(run["contract_version"]),
            "current_ranking_path": str(ranking_database.resolve()),
            "current_ranking_sha256": ranking_sha256,
            "current_ranking_size_bytes": ranking_database.stat().st_size,
            "current_replay_path": str(replay_database.resolve()),
            "current_replay_sha256": replay_sha256,
            "current_replay_size_bytes": replay_database.stat().st_size,
            "primary_metric": "winning_target_rate",
            "prize_rule_provenance": str(run["prize_rule_provenance"]),
            "prize_rule_version": str(run["prize_rule_version"]),
            "run_id": run_id,
            "source_draw_db_sha256": str(run["source_draw_db_sha256"]),
            "stability_verified_before_after_load": True,
            "strategy_set_fingerprint": str(run["strategy_set_fingerprint"]),
        },
    )
    return authority, cells


def load_authorities(
    paths: AuthorityPaths,
) -> tuple[tuple[SourceAuthority, ...], tuple[CellData, ...]]:
    authority_files = paths.files()
    before_hashes = {path: sha256_file(path) for path in authority_files}
    b649_authority, b649_cells = _parse_b649_authority(
        paths.b649_directory, before_hashes
    )
    t539_authority, t539_cells = _parse_t539_authority(
        paths.t539_database, before_hashes[paths.t539_database]
    )
    p638_authority, p638_cells = _parse_p638_authority(
        paths.p638_replay_database,
        paths.p638_ranking_database,
        before_hashes[paths.p638_replay_database],
        before_hashes[paths.p638_ranking_database],
    )
    after_hashes = {path: sha256_file(path) for path in authority_files}
    if before_hashes != after_hashes:
        changed = sorted(
            str(path)
            for path in authority_files
            if before_hashes[path] != after_hashes[path]
        )
        raise PilotDataError(f"CANONICAL_REPLAY_AUTHORITY_CHANGED_DURING_LOAD: {changed}")
    authorities = (b649_authority, t539_authority, p638_authority)
    cells = tuple(
        sorted(
            (*b649_cells, *t539_cells, *p638_cells),
            key=lambda cell: (cell.lottery_id, cell.native_ticket_count),
        )
    )
    return authorities, cells


def build_result(
    authorities: Sequence[SourceAuthority],
    cells: Sequence[CellData],
) -> dict[str, Any]:
    cell_payloads: list[dict[str, Any]] = []
    eligible_cells: list[str] = []
    excluded_cells: list[dict[str, Any]] = []
    for cell in cells:
        experiments = {
            label: experiment_payload(evaluate_cell(cell, label=label, window=window))
            for label, window in WINDOWS
        }
        cell_id = f"{cell.lottery_id}:K{cell.native_ticket_count}"
        if cell.comparable_targets:
            eligible_cells.append(cell_id)
        else:
            excluded_cells.append(
                {
                    "cell_id": cell_id,
                    "reason": "NO_COMPLETE_FIXED_UNIVERSE_TARGET",
                    "coverage": _coverage_payload(cell),
                }
            )
        cell_payloads.append(
            {
                "candidate_strategies": [
                    _candidate_payload(candidate) for candidate in cell.candidates
                ],
                "cell_id": cell_id,
                "coverage": _coverage_payload(cell),
                "experiments": experiments,
                "lottery_id": cell.lottery_id,
                "native_ticket_count": cell.native_ticket_count,
                "selection_tie_break": list(cell.selection_tie_break),
                "source_authority_id": cell.source_authority_id,
            }
        )

    return {
        "canonical_base": {
            "expected_head": EXPECTED_BASE_HEAD,
            "expected_tree": EXPECTED_BASE_TREE,
        },
        "cells": cell_payloads,
        "claim_boundary": {
            "pilot_only": True,
            "predictive_advantage": "NOT_CLAIMED",
            "production_readiness": "NOT_CLAIMED",
            "profitability": "NOT_CLAIMED",
            "statistical_significance": "NOT_CLAIMED",
        },
        "independence": {
            "phase12_dependency": "NONE",
            "phase12_paths_changed": "NONE",
        },
        "invariants": {
            "composite_score": "NOT_USED",
            "database_writes": "NONE",
            "future_target_selection_input": "FORBIDDEN_AND_VALIDATED",
            "p638_zone2_refinement": "NOT_RUN",
            "reference_promotion": "NOT_AUTHORIZED",
            "rolling_frozen_target_sets": "IDENTICAL_BY_CONSTRUCTION_AND_CHECKED",
            "runtime_promotion": "NOT_AUTHORIZED",
            "second_exchange": "NOT_RUN",
            "selection_history_boundary": "STRICTLY_BEFORE_TARGET",
            "window_sweep": "NOT_RUN",
        },
        "phase0": {
            "eligible_fixed_universe_cells": eligible_cells,
            "excluded_fixed_universe_cells": excluded_cells,
        },
        "primary_metric": {
            "id": PRIMARY_METRIC_ID,
            "sample_unit": "DISTINCT_TARGET_DRAW",
            "success_definition": "AT_LEAST_ONE_NATIVE_TICKET_WINS_AN_OFFICIAL_PRIZE",
        },
        "schema_version": SCHEMA_VERSION,
        "scientific_question": (
            "Can a strictly pre-target rolling selector outperform the strategy frozen "
            "as leader at the start of the same causal evaluation horizon?"
        ),
        "source_authorities": [
            {
                "authority_id": authority.authority_id,
                "details": dict(authority.details),
                "lottery_id": authority.lottery_id,
            }
            for authority in authorities
        ],
        "study_id": STUDY_ID,
        "task_id": TASK_ID,
        "windows": {label: window for label, window in WINDOWS},
    }


def render_report(payload: Mapping[str, Any]) -> str:
    cells = cast(list[dict[str, Any]], payload["cells"])
    lines = [
        "# Strategy Matrix causal rolling selector pilot R1",
        "",
        "This pilot compares a strictly pre-target rolling strategy selector with a "
        "strategy frozen at the first eligible target. It is historical evidence only.",
        "",
        "## Metric and causal contract",
        "",
        "- Primary metric: official-any-prize rate per distinct target draw.",
        "- Windows: SHORT=50, MEDIUM=300, LONG=750 prior completed comparable targets.",
        "- Each cell uses one fixed candidate universe and the intersection of complete targets.",
        "- Rolling and frozen outcomes are evaluated on identical targets.",
        "",
        "## Rolling versus frozen results",
        "",
        "| Lottery | Tickets | Window | Status | Targets | Candidates | Rolling | Frozen | "
        "Delta | Relative delta | Switches | Frozen strategy |",
        "|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for cell in cells:
        experiments = cast(dict[str, dict[str, Any]], cell["experiments"])
        for label, window in WINDOWS:
            experiment = experiments[label]
            rolling_metric = cast(
                dict[str, Any] | None,
                experiment["rolling_selector_primary_metric_result"],
            )
            frozen_metric = cast(
                dict[str, Any] | None,
                experiment["frozen_baseline_primary_metric_result"],
            )
            delta = cast(dict[str, Any] | None, experiment["absolute_paired_delta"])
            relative = cast(dict[str, Any] | None, experiment["relative_paired_delta"])
            lines.append(
                "| {lottery} | {tickets} | {window} | {status} | {targets} | "
                "{candidates} | {rolling} | {frozen} | {delta} | {relative} | "
                "{switches} | {frozen_strategy} |".format(
                    lottery=cell["lottery_id"],
                    tickets=cell["native_ticket_count"],
                    window=window,
                    status=experiment["status"],
                    targets=experiment["eligible_target_count"],
                    candidates=experiment["candidate_strategy_count"],
                    rolling=(rolling_metric["rate"]["exact"] if rolling_metric else "—"),
                    frozen=(frozen_metric["rate"]["exact"] if frozen_metric else "—"),
                    delta=(delta["exact"] if delta else "—"),
                    relative=(relative["exact"] if relative else "—"),
                    switches=experiment["rolling_strategy_switch_count"],
                    frozen_strategy=experiment["frozen_baseline_strategy"] or "—",
                )
            )

    lines.extend(["", "## Cell coverage and selection details", ""])
    for cell in cells:
        coverage = cast(dict[str, Any], cell["coverage"])
        coverage_reasons = json.dumps(
            coverage["coverage_exclusion_reason_target_counts"], sort_keys=True
        )
        lines.extend(
            [
                f"### {cell['cell_id']}",
                "",
                f"- Candidates: {len(cast(list[Any], cell['candidate_strategies']))}",
                f"- Comparable targets: {coverage['comparable_target_count']} of "
                f"{coverage['authority_target_count']}",
                f"- Coverage-excluded/missing targets: "
                f"{coverage['coverage_excluded_missing_target_count']}",
                f"- Coverage exclusion reasons: `{coverage_reasons}`",
            ]
        )
        experiments = cast(dict[str, dict[str, Any]], cell["experiments"])
        for label, _window in WINDOWS:
            experiment = experiments[label]
            lines.append(
                f"- {label}: conclusion={experiment['conclusion']}; "
                f"first={experiment['first_evaluated_target']}; "
                f"last={experiment['last_evaluated_target']}; "
                f"switches={experiment['rolling_strategy_switch_count']}; "
                "selection_frequency="
                f"`{json.dumps(experiment['rolling_selection_frequency'], sort_keys=True)}`"
            )
        lines.append("")

    lines.extend(
        [
            "## Scientific limitations",
            "",
            "- Historical outperformance, equality, or underperformance does not prove future "
            "predictive advantage.",
            "- No profitability, production-readiness, promotion, p-value, or significance claim "
            "is made.",
            "- B649 K2 is excluded because every authority target contains at least one strategy "
            "execution failure; its strategy universe cannot be compared without changing "
            "membership.",
            "- A window is inconclusive whenever the fixed comparable series cannot provide W "
            "prior "
            "targets plus a current evaluation target.",
            "",
            "## Explicit boundaries",
            "",
            "```text",
            "PHASE12_DEPENDENCY = NONE",
            "PHASE12_PATHS_CHANGED = NONE",
            "P638_ZONE2 = NOT RUN",
            "SECOND_EXCHANGE = NOT RUN",
            "REFERENCE_PROMOTION = NOT AUTHORIZED",
            "RUNTIME_PROMOTION = NOT AUTHORIZED",
            "PREDICTIVE_ADVANTAGE = NOT CLAIMED",
            "PROFITABILITY = NOT CLAIMED",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def run_pilot(paths: AuthorityPaths) -> tuple[dict[str, Any], bytes, bytes]:
    authorities, cells = load_authorities(paths)
    payload = build_result(authorities, cells)
    json_bytes = canonical_json_bytes(payload)
    report_bytes = render_report(payload).encode("utf-8")
    return payload, json_bytes, report_bytes


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--b649-authority-directory", type=Path, default=DEFAULT_B649_AUTHORITY_DIRECTORY
    )
    parser.add_argument("--t539-authority", type=Path, default=DEFAULT_T539_AUTHORITY)
    parser.add_argument(
        "--p638-replay-authority", type=Path, default=DEFAULT_P638_REPLAY_AUTHORITY
    )
    parser.add_argument(
        "--p638-ranking-authority", type=Path, default=DEFAULT_P638_RANKING_AUTHORITY
    )
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-report", type=Path, default=DEFAULT_OUTPUT_REPORT)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    paths = AuthorityPaths(
        b649_directory=cast(Path, arguments.b649_authority_directory),
        t539_database=cast(Path, arguments.t539_authority),
        p638_replay_database=cast(Path, arguments.p638_replay_authority),
        p638_ranking_database=cast(Path, arguments.p638_ranking_authority),
    )
    output_json = cast(Path, arguments.output_json)
    output_report = cast(Path, arguments.output_report)
    _payload, json_bytes, report_bytes = run_pilot(paths)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_report.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_bytes(json_bytes)
    output_report.write_bytes(report_bytes)
    print(
        json.dumps(
            {
                "output_json": str(output_json),
                "output_json_sha256": hashlib.sha256(json_bytes).hexdigest(),
                "output_report": str(output_report),
                "output_report_sha256": hashlib.sha256(report_bytes).hexdigest(),
                "status": "COMPLETE",
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
