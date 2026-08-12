"""Bounded readers for the three sealed B649 analytics authorities."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass
from enum import StrEnum
from functools import cached_property
from pathlib import Path
from typing import cast

from lottolab.application.b649_strategy_k_combinations import (
    B649AnalyticsAuthorityError,
    B649CombinationCriterion,
    B649CombinationDataset,
    B649CombinationPage,
    B649CombinationProxyMode,
    B649CombinationProxyOption,
    B649CombinationQuery,
    B649CombinationRecord,
    B649CombinationSummary,
    B649CombinationWindow,
    B649EffectiveUniqueKCount,
    B649EvidenceStatus,
    B649StrategyAvailability,
    B649StrategyAvailabilityRecord,
    B649StrategyKCriterion,
    B649StrategyKDataset,
    B649StrategyKPage,
    B649StrategyKQuery,
    B649StrategyKRecord,
    B649StrategyKSummary,
    B649StrategyKWindowKind,
    B649WindowOption,
    B649WindowRole,
    query_b649_combinations,
    query_b649_strategy_k,
)

STRATEGY_K_TASK_TREE = "4de80ce1d43fe858122ee05d1e4b18cd4b4661351b3565db019adf9c5fe2fad9"
STRATEGY_K_FULL_OUTPUT_TREE = "876b162535d07fc67361253b7834b373d9b50fa780c82b6233222f3b4747f760"
COMBINATION_TASK_TREE = "6278aa9e7ce6f625e5ba9bbc76047005ff6be852b3f8e24f7ace702ed258fb03"
OBSERVER_TASK_TREE = "eea60ba3981f46070eef1eeabf1e452682649961b64d84bfde8f9185bb16378c"

_STRATEGY_FILES = (
    "authority_contract.json",
    "strategy_k_matrix.jsonl",
    "strategy_universe.json",
    "validation.json",
)
_COMBINATION_PAYLOAD_FILES = (
    "combination_projection.csv.gz",
    "report.md",
    "reproduce_projection.py",
    "top_candidates.csv",
)
_COMBINATION_FIELDS = (
    "proxy_mode",
    "proxy_label",
    "member_count",
    "member_strategy_ids",
    "combination_id",
    "evaluation_window",
    "event",
    "rank",
    "eligible_draws",
    "successes",
    "observed_rate",
    "exact_random_baseline_rate_fraction",
    "random_baseline_rate",
    "descriptive_delta",
    "evaluable_status",
    "evaluable_reason",
    "long_delta_sign",
    "mid_delta_sign",
    "short_delta_sign",
    "positive_window_count",
    "minimum_delta",
    "delta_range",
    "cross_window_stable_positive",
    "historical_search_only",
    "predictive_advantage_claimed",
    "prospective_validation_required",
    "candidate_disposition",
)


@dataclass(frozen=True, slots=True)
class B649AnalyticsAuthorityPaths:
    strategy_k_root: Path
    combination_root: Path
    observer_root: Path


class SealedB649AnalyticsArtifactReader:
    """Read only exact roots; no discovery, regeneration, database, or network access."""

    def __init__(self, paths: B649AnalyticsAuthorityPaths) -> None:
        self._paths = paths

    def strategy_k_summary(self) -> B649StrategyKSummary:
        return self._strategy_dataset.summary

    def query_strategy_k(self, query: B649StrategyKQuery) -> B649StrategyKPage:
        return query_b649_strategy_k(self._strategy_dataset, query)

    def combination_summary(self) -> B649CombinationSummary:
        return self._combination_dataset.summary

    def query_combinations(self, query: B649CombinationQuery) -> B649CombinationPage:
        return query_b649_combinations(self._combination_dataset, query)

    def evidence_status(self) -> B649EvidenceStatus:
        return self._observer_status

    @cached_property
    def _strategy_dataset(self) -> B649StrategyKDataset:
        root = self._paths.strategy_k_root
        manifest = _mapping(_read_json(root / "MANIFEST.json"), "Strategy-K manifest")
        entries = _manifest_entries(manifest, "Strategy-K manifest")
        task_entries = [entry for entry in entries if entry["path"] != "report.md"]
        if _tree(task_entries) != STRATEGY_K_TASK_TREE:
            raise _error("Strategy-K TASK_TREE does not match the sealed authority")
        if _tree(entries) != STRATEGY_K_FULL_OUTPUT_TREE:
            raise _error("Strategy-K FULL_OUTPUT_TREE does not match the sealed authority")
        if (
            manifest.get("task_tree") != STRATEGY_K_TASK_TREE
            or manifest.get("full_output_tree") != STRATEGY_K_FULL_OUTPUT_TREE
        ):
            raise _error("Strategy-K manifest tree labels do not match their content")

        entries_by_path = {cast(str, entry["path"]): entry for entry in entries}
        for name in _STRATEGY_FILES:
            _validate_manifest_file(root, name, entries_by_path)

        contract = _mapping(_read_json(root / "authority_contract.json"), "authority contract")
        universe = _mapping(_read_json(root / "strategy_universe.json"), "strategy universe")
        validation = _mapping(_read_json(root / "validation.json"), "validation")
        supported_k = tuple(
            _positive_integer(value, "candidate K")
            for value in _list(contract.get("big_lotto_candidate_k_range"), "candidate K range")
        )
        if not supported_k or len(set(supported_k)) != len(supported_k):
            raise _error("Strategy-K candidate range is empty or duplicated")
        supported_criteria = tuple(
            _strategy_criterion(value) for value in _list(contract.get("criteria"), "criteria")
        )
        if supported_criteria != tuple(B649StrategyKCriterion):
            raise _error("Strategy-K criteria differ from the canonical API contract")

        window_policy = _mapping(contract.get("window_policy"), "window policy")
        windows = _strategy_windows(window_policy)
        window_by_kind = {B649StrategyKWindowKind(option.window_kind): option for option in windows}
        measurement_mode = _string(
            _mapping(contract.get("matrix_contract"), "matrix contract").get("measurement_mode"),
            "measurement mode",
        )
        duplicate_policy = _string(
            _mapping(contract.get("candidate_k_contract"), "candidate K contract").get(
                "duplicate_handling_policy"
            ),
            "duplicate handling policy",
        )
        policy_version = _string(window_policy.get("policy_version"), "window policy version")
        if measurement_mode != "CANDIDATE_COVERAGE":
            raise _error("Strategy-K authority is not candidate coverage")
        if window_policy.get("nested_windows_independent") is not False:
            raise _error("Strategy-K nested-window independence changed")

        counts = _mapping(universe.get("counts"), "strategy-universe counts")
        strategy_values = _list(
            universe.get("current_executable_big_lotto_strategies"),
            "current executable strategies",
        )
        strategies = tuple(_parse_strategy_availability(value) for value in strategy_values)
        available_identities = {
            (item.strategy_id, item.strategy_version)
            for item in strategies
            if item.availability is B649StrategyAvailability.MATRIX_AVAILABLE
        }
        unavailable_identities = {
            (item.strategy_id, item.strategy_version)
            for item in strategies
            if item.availability is B649StrategyAvailability.PORTFOLIO_ORDER_AGGREGATION_NOT_DEFINED
        }
        if available_identities & unavailable_identities or len(
            available_identities | unavailable_identities
        ) != len(strategies):
            raise _error("Strategy-K availability identities are not an exact partition")
        _match_count(counts, "current_executable_big_lotto", len(strategies))
        _match_count(counts, "matrix_available", len(available_identities))
        _match_count(counts, "matrix_unavailable", len(unavailable_identities))
        _match_count(
            counts,
            "portfolio_order_aggregation_not_defined",
            len(unavailable_identities),
        )
        historical_count = _nonnegative_integer(
            counts.get("historical_accounted"), "historical accounted count"
        )

        records = _read_strategy_matrix(
            root / "strategy_k_matrix.jsonl",
            supported_k=supported_k,
            supported_criteria=supported_criteria,
            windows=window_by_kind,
            available_identities=available_identities,
            measurement_mode=measurement_mode,
            policy_version=policy_version,
        )
        matrix_validation = _mapping(validation.get("matrix"), "matrix validation")
        matrix_row_count = _positive_integer(
            matrix_validation.get("matrix_key_count"), "matrix row count"
        )
        if len(records) != matrix_row_count:
            raise _error("Strategy-K row count differs from sealed validation metadata")

        expected_keys = {
            (strategy_id, strategy_version, requested_k, criterion, window)
            for strategy_id, strategy_version in available_identities
            for requested_k in supported_k
            for criterion in supported_criteria
            for window in window_by_kind
        }
        actual_keys = {
            (
                row.strategy_id,
                row.strategy_version,
                row.requested_k,
                row.criterion,
                row.window_kind,
            )
            for row in records
        }
        if actual_keys != expected_keys or len(actual_keys) != len(records):
            raise _error("Strategy-K matrix does not cover each sealed comparable cell once")

        summary = B649StrategyKSummary(
            authority_task_tree=STRATEGY_K_TASK_TREE,
            authority_full_output_tree=STRATEGY_K_FULL_OUTPUT_TREE,
            matrix_row_count=matrix_row_count,
            supported_k_values=supported_k,
            supported_criteria=supported_criteria,
            windows=windows,
            strategies=strategies,
            current_executable_strategy_count=len(strategies),
            matrix_available_strategy_count=len(available_identities),
            matrix_unavailable_strategy_count=len(unavailable_identities),
            historical_accounted_identity_count=historical_count,
            measurement_mode=measurement_mode,
            window_policy_version=policy_version,
            duplicate_handling_policy=duplicate_policy,
            nested_windows_independent=False,
            predictive_advantage_claimed=False,
        )
        return B649StrategyKDataset(summary=summary, records=records)

    @cached_property
    def _combination_dataset(self) -> B649CombinationDataset:
        root = self._paths.combination_root
        sums = _read_sha256sums(root / "SHA256SUMS")
        if set(sums) != set(_COMBINATION_PAYLOAD_FILES):
            raise _error("combination SHA256SUMS does not name the sealed payload")

        entries: list[dict[str, object]] = []
        for name in sorted((*_COMBINATION_PAYLOAD_FILES, "SHA256SUMS")):
            path = root / name
            try:
                size = path.stat().st_size
            except OSError as exc:
                raise _error(f"combination authority file is unavailable: {name}") from exc
            digest = (
                _sha256_file(path) if name in {"SHA256SUMS", "top_candidates.csv"} else sums[name]
            )
            if name == "top_candidates.csv" and digest != sums[name]:
                raise _error("sealed combination Top-20 checksum does not match")
            entries.append({"path": name, "sha256": digest, "size": size})
        if _tree(entries) != COMBINATION_TASK_TREE:
            raise _error("combination TASK_TREE does not match the sealed authority")

        records = _read_combination_top_candidates(root / "top_candidates.csv")
        groups: dict[
            tuple[
                B649CombinationProxyMode,
                int,
                B649CombinationWindow,
                B649CombinationCriterion,
            ],
            list[int],
        ] = defaultdict(list)
        for row in records:
            groups[(row.proxy_mode, row.member_count, row.evaluation_window, row.criterion)].append(
                row.sealed_rank
            )
        for ranks in groups.values():
            if len(ranks) > 20 or sorted(ranks) != list(range(1, len(ranks) + 1)):
                raise _error("combination Top-20 ranks are not complete and deterministic")

        proxy_labels: dict[B649CombinationProxyMode, str] = {}
        for row in records:
            existing = proxy_labels.setdefault(row.proxy_mode, row.proxy_label)
            if existing != row.proxy_label:
                raise _error("combination proxy label is inconsistent")
        proxy_options = tuple(
            B649CombinationProxyOption(proxy_mode=mode, proxy_label=proxy_labels[mode])
            for mode in B649CombinationProxyMode
        )
        member_counts = tuple(sorted({row.member_count for row in records}))
        if member_counts != (2, 3):
            raise _error("combination authority is not pair/triple only")
        criteria = tuple(
            criterion
            for criterion in B649CombinationCriterion
            if any(row.criterion is criterion for row in records)
        )
        if criteria != tuple(B649CombinationCriterion):
            raise _error("combination criteria differ from the canonical API contract")
        windows = _combination_windows()
        if {row.evaluation_window.value for row in records} != {
            item.window_kind for item in windows
        }:
            raise _error("combination window coverage is incomplete")

        summary = B649CombinationSummary(
            authority_task_tree=COMBINATION_TASK_TREE,
            sealed_top_candidate_count=len(records),
            proxy_modes=proxy_options,
            member_counts=member_counts,
            windows=windows,
            supported_criteria=criteria,
            source_scope="SEALED_TOP_20_PER_PROXY_MEMBER_COUNT_WINDOW_CRITERION",
            full_projection_sent_to_browser=False,
            predictive_advantage_claimed=False,
        )
        return B649CombinationDataset(summary=summary, records=records)

    @cached_property
    def _observer_status(self) -> B649EvidenceStatus:
        root = self._paths.observer_root
        manifest = _mapping(_read_json(root / "MANIFEST.json"), "observer manifest")
        entries = _manifest_entries(manifest, "observer manifest")
        if _tree(entries) != OBSERVER_TASK_TREE or manifest.get("task_tree") != OBSERVER_TASK_TREE:
            raise _error("observer TASK_TREE does not match the sealed authority")
        entries_by_path = {cast(str, entry["path"]): entry for entry in entries}
        _validate_manifest_file(root, "observer_contract.json", entries_by_path)
        contract = _mapping(_read_json(root / "observer_contract.json"), "observer contract")
        observation_names = sorted(
            name for name in entries_by_path if name.startswith("observations/")
        )
        observations: list[dict[str, object]] = []
        for name in observation_names:
            _validate_manifest_file(root, name, entries_by_path)
            observations.append(_mapping(_read_json(root / name), name))

        temporal_counts: dict[str, int] = defaultdict(int)
        latest_draw: str | None = None
        for observation in observations:
            temporal_counts[
                _string(observation.get("temporal_provenance"), "temporal provenance")
            ] += 1
            draw = _string(observation.get("target_draw"), "target draw")
            latest_draw = draw if latest_draw is None or draw > latest_draw else latest_draw
            if observation.get("membership_changed") is not False:
                raise _error("observer changed frozen cohort membership")
            if observation.get("predictive_advantage_claimed") is not False:
                raise _error("observer claims predictive advantage")
            prediction_before = _mapping(
                observation.get("prediction_before_outcome"), "prediction-before-outcome"
            )
            if prediction_before.get("status") != "PASS":
                raise _error("observer causality evidence is not PASS")

        boundary = _mapping(contract.get("frozen_boundary"), "observer frozen boundary")
        checkpoints = tuple(
            _positive_integer(value, "checkpoint")
            for value in _list(boundary.get("checkpoints"), "checkpoints")
        )
        c_rule = _mapping(
            _mapping(contract.get("proxy_rules"), "proxy rules").get("C"),
            "proxy C rule",
        )
        if boundary.get("predictive_advantage_claimed") is not False:
            raise _error("observer contract claims predictive advantage")
        observation_count = len(observations)
        return B649EvidenceStatus(
            observer_task_tree=OBSERVER_TASK_TREE,
            historical_evidence_status="AVAILABLE",
            pre_freeze_date_unseen_holdout_count=temporal_counts["PRE_FREEZE_DATE_UNSEEN_HOLDOUT"],
            post_freeze_date_prospective_count=temporal_counts["POST_FREEZE_DATE_PROSPECTIVE"],
            observation_count=observation_count,
            observation_start_draw=_string(
                boundary.get("observation_start_draw"), "observation start draw"
            ),
            latest_observed_draw=latest_draw,
            checkpoints=checkpoints,
            checkpoints_reached=tuple(value for value in checkpoints if value <= observation_count),
            primary_outcome=_string(boundary.get("primary_outcome"), "primary outcome"),
            c_forward_status=_string(
                c_rule.get("unavailable_reason_code"), "proxy C unavailable reason code"
            ),
            c_forward_reason=_string(c_rule.get("unavailable_reason"), "proxy C reason"),
            holdout_used_to_rerank_historical_results=False,
            predictive_advantage_claimed=False,
        )


def _read_strategy_matrix(
    path: Path,
    *,
    supported_k: tuple[int, ...],
    supported_criteria: tuple[B649StrategyKCriterion, ...],
    windows: dict[B649StrategyKWindowKind, B649WindowOption],
    available_identities: set[tuple[str, str]],
    measurement_mode: str,
    policy_version: str,
) -> tuple[B649StrategyKRecord, ...]:
    records: list[B649StrategyKRecord] = []
    try:
        stream = path.open(encoding="utf-8")
    except OSError as exc:
        raise _error("Strategy-K matrix is unavailable") from exc
    with stream:
        for line_number, line in enumerate(stream, start=1):
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise _error(f"Strategy-K row {line_number} is invalid JSON") from exc
            row = _mapping(value, f"Strategy-K row {line_number}")
            strategy_id = _string(row.get("strategy_id"), "strategy_id")
            strategy_version = _string(row.get("strategy_version"), "strategy version")
            requested_k = _positive_integer(row.get("requested_k"), "requested_k")
            criterion = _strategy_criterion(row.get("criterion"))
            window_kind = _enum(B649StrategyKWindowKind, row.get("window_kind"), "window kind")
            option = windows.get(window_kind)
            if (
                (strategy_id, strategy_version) not in available_identities
                or requested_k not in supported_k
                or criterion not in supported_criteria
                or option is None
            ):
                raise _error("Strategy-K row is outside the sealed universe")
            if row.get("measurement_mode") != measurement_mode:
                raise _error("Strategy-K row measurement mode changed")
            if row.get("window_policy_version") != policy_version:
                raise _error("Strategy-K row window policy changed")
            if row.get("window_role") != option.window_role.value:
                raise _error("Strategy-K row window role changed")
            if row.get("requested_draw_count") != option.requested_draw_count:
                raise _error("Strategy-K requested draw count changed")
            if row.get("nested_windows_independent") is not False:
                raise _error("Strategy-K row describes nested windows as independent")

            effective_counts = tuple(
                B649EffectiveUniqueKCount(
                    effective_unique_k=_positive_integer(
                        _mapping(item, "effective K count").get("effective_unique_k"),
                        "effective unique K",
                    ),
                    observation_count=_nonnegative_integer(
                        _mapping(item, "effective K count").get("observation_count"),
                        "effective K observation count",
                    ),
                )
                for item in _list(row.get("effective_unique_k_counts"), "effective K counts")
            )
            source_count = _nonnegative_integer(
                row.get("source_observation_count"), "source observation count"
            )
            eligible_count = _nonnegative_integer(
                row.get("eligible_observation_count"), "eligible observation count"
            )
            excluded_count = _nonnegative_integer(
                row.get("excluded_observation_count"), "excluded observation count"
            )
            success_numerator = _nonnegative_integer(
                row.get("success_numerator"), "success numerator"
            )
            success_denominator = _positive_integer(
                row.get("success_denominator"), "success denominator"
            )
            baseline_numerator = _nonnegative_integer(
                row.get("random_baseline_numerator"), "baseline numerator"
            )
            baseline_denominator = _positive_integer(
                row.get("random_baseline_denominator"), "baseline denominator"
            )
            if (
                source_count != eligible_count + excluded_count
                or success_denominator != eligible_count
                or success_numerator > success_denominator
                or baseline_numerator > baseline_denominator
                or sum(item.observation_count for item in effective_counts) != eligible_count
            ):
                raise _error("Strategy-K count identity is inconsistent")
            records.append(
                B649StrategyKRecord(
                    strategy_id=strategy_id,
                    strategy_version=strategy_version,
                    requested_k=requested_k,
                    effective_unique_k_counts=effective_counts,
                    criterion=criterion,
                    window_kind=window_kind,
                    window_role=option.window_role,
                    requested_draw_count=option.requested_draw_count,
                    source_observation_count=source_count,
                    eligible_observation_count=eligible_count,
                    excluded_observation_count=excluded_count,
                    success_numerator=success_numerator,
                    success_denominator=success_denominator,
                    random_baseline_numerator=baseline_numerator,
                    random_baseline_denominator=baseline_denominator,
                    observed_minus_baseline=_string(
                        row.get("observed_minus_baseline"), "observed-minus-baseline"
                    ),
                    first_target_draw=_string(row.get("first_target_draw"), "first target"),
                    last_target_draw=_string(row.get("last_target_draw"), "last target"),
                    evaluation_status=_string(row.get("evaluation_status"), "evaluation status"),
                    measurement_mode=measurement_mode,
                    window_policy_version=policy_version,
                    nested_windows_independent=False,
                )
            )
    return tuple(records)


def _read_combination_top_candidates(path: Path) -> tuple[B649CombinationRecord, ...]:
    records: list[B649CombinationRecord] = []
    try:
        stream = path.open(encoding="utf-8", newline="")
    except OSError as exc:
        raise _error("sealed combination Top-20 file is unavailable") from exc
    with stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != _COMBINATION_FIELDS:
            raise _error("sealed combination Top-20 schema changed")
        for line_number, raw in enumerate(reader, start=2):
            row = cast(dict[str, object], raw)
            proxy = _enum(B649CombinationProxyMode, row.get("proxy_mode"), "proxy mode")
            member_count = _csv_positive_integer(row.get("member_count"), "member count")
            members = tuple(
                part
                for part in _string(row.get("member_strategy_ids"), "members").split("|")
                if part
            )
            combination_id = _string(row.get("combination_id"), "combination ID")
            if member_count not in (2, 3) or len(members) != member_count:
                raise _error(f"combination row {line_number} is not pair/triple")
            expected_prefix = "PAIR_" if member_count == 2 else "TRIPLE_"
            if not combination_id.startswith(expected_prefix):
                raise _error(f"combination row {line_number} identity/member count mismatch")
            numerator, denominator = _fraction(
                row.get("exact_random_baseline_rate_fraction"), "exact baseline fraction"
            )
            predictive_advantage = _yes_no(
                row.get("predictive_advantage_claimed"), "predictive advantage"
            )
            historical_only = _yes_no(row.get("historical_search_only"), "historical search only")
            prospective_required = _yes_no(
                row.get("prospective_validation_required"), "prospective validation"
            )
            if predictive_advantage or not historical_only or not prospective_required:
                raise _error("combination Top-20 row changed its descriptive-only contract")
            eligible = _csv_nonnegative_integer(row.get("eligible_draws"), "eligible draws")
            successes = _csv_nonnegative_integer(row.get("successes"), "successes")
            if successes > eligible:
                raise _error("combination successes exceed eligible draws")
            records.append(
                B649CombinationRecord(
                    proxy_mode=proxy,
                    proxy_label=_string(row.get("proxy_label"), "proxy label"),
                    member_count=member_count,
                    member_strategy_ids=members,
                    combination_id=combination_id,
                    evaluation_window=_enum(
                        B649CombinationWindow,
                        row.get("evaluation_window"),
                        "combination window",
                    ),
                    criterion=_combination_criterion(row.get("event")),
                    sealed_rank=_csv_positive_integer(row.get("rank"), "sealed rank"),
                    eligible_draws=eligible,
                    success_numerator=successes,
                    success_denominator=eligible,
                    observed_rate=_string(row.get("observed_rate"), "observed rate"),
                    exact_random_baseline_numerator=numerator,
                    exact_random_baseline_denominator=denominator,
                    random_baseline_rate=_string(
                        row.get("random_baseline_rate"), "random baseline rate"
                    ),
                    descriptive_delta=_string(row.get("descriptive_delta"), "descriptive delta"),
                    evaluation_status=_string(row.get("evaluable_status"), "evaluation status"),
                    evaluation_reason=_string(row.get("evaluable_reason"), "evaluation reason"),
                    long_delta_sign=_optional_string(row.get("long_delta_sign"), "long delta sign"),
                    mid_delta_sign=_optional_string(row.get("mid_delta_sign"), "mid delta sign"),
                    short_delta_sign=_optional_string(
                        row.get("short_delta_sign"), "short delta sign"
                    ),
                    positive_window_count=_csv_nonnegative_integer(
                        row.get("positive_window_count"), "positive-window count"
                    ),
                    minimum_delta=_optional_string(row.get("minimum_delta"), "minimum delta"),
                    delta_range=_optional_string(row.get("delta_range"), "delta range"),
                    cross_window_stable_positive=_yes_no(
                        row.get("cross_window_stable_positive"), "cross-window status"
                    ),
                    historical_search_only=historical_only,
                    predictive_advantage_claimed=predictive_advantage,
                    prospective_validation_required=prospective_required,
                    candidate_disposition=_string(
                        row.get("candidate_disposition"), "candidate disposition"
                    ),
                )
            )
    return tuple(records)


def _parse_strategy_availability(value: object) -> B649StrategyAvailabilityRecord:
    row = _mapping(value, "strategy availability")
    availability = _enum(
        B649StrategyAvailability,
        row.get("matrix_classification"),
        "matrix classification",
    )
    return B649StrategyAvailabilityRecord(
        strategy_id=_string(row.get("strategy_id"), "strategy ID"),
        strategy_version=_string(row.get("strategy_version"), "strategy version"),
        availability=availability,
        availability_reason=_string(
            row.get("matrix_classification_reason"), "matrix classification reason"
        ),
        response_shape=_string(row.get("response_shape"), "response shape"),
        native_ticket_count=_positive_integer(
            row.get("native_ticket_count"), "native ticket count"
        ),
    )


def _strategy_windows(policy: dict[str, object]) -> tuple[B649WindowOption, ...]:
    return (
        B649WindowOption(
            window_kind=B649StrategyKWindowKind.LONG,
            window_role=_enum(B649WindowRole, policy.get("long_role"), "long role"),
            requested_draw_count=_positive_integer(policy.get("long_draws"), "long draws"),
            default_emphasis=True,
        ),
        B649WindowOption(
            window_kind=B649StrategyKWindowKind.MEDIUM,
            window_role=_enum(B649WindowRole, policy.get("medium_role"), "medium role"),
            requested_draw_count=_positive_integer(policy.get("medium_draws"), "medium draws"),
            default_emphasis=False,
        ),
        B649WindowOption(
            window_kind=B649StrategyKWindowKind.SHORT,
            window_role=_enum(B649WindowRole, policy.get("short_role"), "short role"),
            requested_draw_count=_positive_integer(policy.get("short_draws"), "short draws"),
            default_emphasis=False,
        ),
        B649WindowOption(
            window_kind=B649StrategyKWindowKind.FULL_HISTORY,
            window_role=_enum(B649WindowRole, policy.get("full_history_role"), "full role"),
            requested_draw_count=None,
            default_emphasis=False,
        ),
    )


def _combination_windows() -> tuple[B649WindowOption, ...]:
    return (
        B649WindowOption("LONG_750", B649WindowRole.PRIMARY_EVIDENCE, 750, True),
        B649WindowOption("MID_300", B649WindowRole.STABILITY_CONFIRMATION, 300, False),
        B649WindowOption("SHORT_50", B649WindowRole.DEGRADATION_VETO, 50, False),
        B649WindowOption("FULL", B649WindowRole.REFERENCE_ONLY, None, False),
    )


def _manifest_entries(manifest: dict[str, object], label: str) -> list[dict[str, object]]:
    values = _list(manifest.get("entries"), f"{label} entries")
    entries: list[dict[str, object]] = []
    paths: list[str] = []
    for value in values:
        entry = _mapping(value, f"{label} entry")
        path = _string(entry.get("path"), "manifest path")
        digest = _string(entry.get("sha256"), "manifest sha256")
        size = _nonnegative_integer(entry.get("size"), "manifest size")
        if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
            raise _error(f"{label} contains an invalid SHA-256")
        entries.append({"path": path, "sha256": digest, "size": size})
        paths.append(path)
    if paths != sorted(paths, key=lambda value: value.encode("utf-8")) or len(paths) != len(
        set(paths)
    ):
        raise _error(f"{label} entries are not unique UTF-8 path order")
    return entries


def _validate_manifest_file(
    root: Path, name: str, entries_by_path: dict[str, dict[str, object]]
) -> None:
    entry = entries_by_path.get(name)
    if entry is None:
        raise _error(f"sealed manifest does not include {name}")
    path = root / name
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise _error(f"sealed authority file is unavailable: {name}") from exc
    if size != entry["size"] or _sha256_file(path) != entry["sha256"]:
        raise _error(f"sealed authority checksum differs: {name}")


def _read_sha256sums(path: Path) -> dict[str, str]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise _error("sealed SHA256SUMS is unavailable") from exc
    result: dict[str, str] = {}
    for line in lines:
        digest, separator, name = line.partition("  ")
        if not separator or len(digest) != 64 or not name or name in result:
            raise _error("sealed SHA256SUMS is malformed")
        result[name] = digest
    return result


def _read_json(path: Path) -> object:
    try:
        return json.loads(path.read_bytes())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise _error(f"sealed JSON is unavailable or malformed: {path.name}") from exc


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise _error(f"sealed authority file is unavailable: {path.name}") from exc
    return digest.hexdigest()


def _tree(entries: list[dict[str, object]]) -> str:
    canonical = json.dumps(
        entries,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _mapping(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise _error(f"{label} must be an object")
    mapping = cast(dict[object, object], value)
    if not all(isinstance(key, str) for key in mapping):
        raise _error(f"{label} must use string keys")
    return cast(dict[str, object], mapping)


def _list(value: object, label: str) -> list[object]:
    if not isinstance(value, list):
        raise _error(f"{label} must be a list")
    return cast(list[object], value)


def _string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise _error(f"{label} must be a non-empty string")
    return value


def _optional_string(value: object, label: str) -> str | None:
    if value == "":
        return None
    return _string(value, label)


def _nonnegative_integer(value: object, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise _error(f"{label} must be a non-negative integer")
    return value


def _positive_integer(value: object, label: str) -> int:
    result = _nonnegative_integer(value, label)
    if result == 0:
        raise _error(f"{label} must be positive")
    return result


def _strategy_criterion(value: object) -> B649StrategyKCriterion:
    return _enum(B649StrategyKCriterion, value, "Strategy-K criterion")


def _combination_criterion(value: object) -> B649CombinationCriterion:
    return _enum(B649CombinationCriterion, value, "combination criterion")


def _csv_nonnegative_integer(value: object, label: str) -> int:
    if not isinstance(value, str) or not value.isascii() or not value.isdecimal():
        raise _error(f"{label} must be a CSV non-negative integer")
    return int(value)


def _csv_positive_integer(value: object, label: str) -> int:
    result = _csv_nonnegative_integer(value, label)
    if result == 0:
        raise _error(f"{label} must be positive")
    return result


def _enum[T: StrEnum](enum_type: type[T], value: object, label: str) -> T:
    try:
        return enum_type(value)
    except (TypeError, ValueError) as exc:
        raise _error(f"{label} is outside the sealed contract") from exc


def _fraction(value: object, label: str) -> tuple[int, int]:
    raw = _string(value, label)
    numerator_raw, separator, denominator_raw = raw.partition("/")
    try:
        numerator = int(numerator_raw)
        denominator = int(denominator_raw)
    except ValueError as exc:
        raise _error(f"{label} is not an exact fraction") from exc
    if not separator or numerator < 0 or denominator <= 0 or numerator > denominator:
        raise _error(f"{label} is not a valid probability fraction")
    return numerator, denominator


def _yes_no(value: object, label: str) -> bool:
    if value == "YES":
        return True
    if value == "NO":
        return False
    raise _error(f"{label} must be YES or NO")


def _match_count(counts: dict[str, object], key: str, actual: int) -> None:
    if _nonnegative_integer(counts.get(key), key) != actual:
        raise _error(f"authority count does not match parsed {key}")


def _error(message: str) -> B649AnalyticsAuthorityError:
    return B649AnalyticsAuthorityError(message)


__all__ = [
    "COMBINATION_TASK_TREE",
    "OBSERVER_TASK_TREE",
    "STRATEGY_K_FULL_OUTPUT_TREE",
    "STRATEGY_K_TASK_TREE",
    "B649AnalyticsAuthorityPaths",
    "SealedB649AnalyticsArtifactReader",
]
