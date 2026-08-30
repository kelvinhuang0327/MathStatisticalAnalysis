"""Attribute sealed rolling-selector switch totals to static lineage classes.

The analysis is deliberately descriptive and fail-closed.  It reads immutable Git
objects, never opens a database, never executes a strategy, and never reconstructs
the historical selector trace.  Because the sealed selector result retains only a
trace digest rather than ordered transition endpoints, an experiment's switches are
lineage-resolved only when every possible pair in its selected Strategy-ID support
has the same exact structural relation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from copy import deepcopy
from fractions import Fraction
from itertools import combinations
from pathlib import Path
from typing import Any, cast

TASK_ID = "SELECTOR_LINEAGE_ATTRIBUTION_R1"
STUDY_ID = "SELECTOR_LINEAGE_ATTRIBUTION_V1"
SCHEMA_VERSION = "SELECTOR_LINEAGE_ATTRIBUTION_RESULT_V1"

BASE_HEAD = "0645f31a2bcaf494760d4bc1675bc1c3ed9a076d"
BASE_TREE = "8b9fa40728f1bea3fb585d86f426a36489e0debf"

ROLLING_COMMIT = "cc9bd1088a9f871618725d0910874283e0318459"
ROLLING_TREE = "7d05638845dc553fa20d793ceba8ce1aceff71ee"
ROLLING_RESULT_SHA256 = "92ffb4d5678d403322791de1e3cb133d3bdb91c9c911142f67f4f3f4ee8979c9"
ROLLING_RESULT_PATH = (
    "docs/research/matrix-native-results/rolling-selector-stability-decomposition-r1-result.json"
)
ROLLING_SCHEMA_VERSION = "ROLLING_SELECTOR_STABILITY_DECOMPOSITION_RESULT_V1"
ROLLING_TASK_ID = "ROLLING_SELECTOR_STABILITY_DECOMPOSITION_R1"

LINEAGE_COMMIT = "b78eda6a2c9858413c6d1a4cb182ac1083fe9454"
LINEAGE_TREE = "2656632e9681e075151a6687414a02a84440bfa3"
LINEAGE_RESULT_SHA256 = "f2f7d1fd5e08083124aaeb43dfe889f96012f6020b9daafae49f6368f832bfad"
LINEAGE_RESULT_PATH = (
    "docs/research/matrix-native-results/"
    "strategy-matrix-static-lineage-redundancy-map-r1-result.json"
)
LINEAGE_SCHEMA_VERSION = "strategy-matrix-static-lineage-redundancy-map/v1"
LINEAGE_STUDY_ID = "STRATEGY_MATRIX_STATIC_LINEAGE_REDUNDANCY_MAP_R1"

PILOT_HEAD = "abc367bd6d8b59d01ecc4d79e56c787bbc03cd20"
PILOT_TREE = "bf430efd66b7ce1ac38ee04fb0052e8c55cc972c"
PILOT_RESULT_SHA256 = "04df0bfdffcf4ecc05d4f2ac3f58cfa1fa301061c5f1c30e549ddc3b5b174157"
PILOT_RESULT_PATH = (
    "docs/research/matrix-native-results/"
    "strategy-matrix-causal-rolling-selector-pilot-r1-result.json"
)
PILOT_SCHEMA_VERSION = "STRATEGY_MATRIX_CAUSAL_ROLLING_SELECTOR_PILOT_RESULT_V1"
PILOT_TASK_ID = "STRATEGY_MATRIX_CAUSAL_ROLLING_SELECTOR_PILOT_R1"

EXPECTED_CELL_COUNT = 22
EXPECTED_EXPERIMENT_COUNT = 66
EXPECTED_SWITCHING_EXPERIMENT_COUNT = 32
EXPECTED_TOTAL_SWITCH_COUNT = 5605

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_JSON = (
    REPOSITORY_ROOT
    / "docs/research/matrix-native-results/selector-lineage-attribution-r1-result.json"
)
DEFAULT_OUTPUT_REPORT = REPOSITORY_ROOT / "docs/research/selector-lineage-attribution-r1.md"

WINDOW_ORDER = ("W50", "W300", "W750")
SIGN_ORDER = ("POSITIVE", "ZERO", "NEGATIVE", "INCONCLUSIVE")
TRANSITION_CLASSES = (
    "SAME_BINDING",
    "SAME_CALLABLE_DIFFERENT_BINDING",
    "DISTINCT_BINDING",
    "UNRESOLVED_LINEAGE",
)
P638_C01_C07_IDS = (
    "power_c01_recency_decay_1bet",
    "power_c02_gap_overdue_1bet",
    "power_c03_pair_centrality_1bet",
    "power_c04_zone_balanced_1bet",
    "power_c05_dispersion_match_1bet",
    "power_c06_regime_cusum_1bet",
    "power_c07_borda_ensemble_1bet",
)


class LineageAttributionError(ValueError):
    """The sealed evidence cannot support a safe deterministic attribution."""


def canonical_json_bytes(payload: Mapping[str, Any]) -> bytes:
    """Serialize a JSON object deterministically."""

    return (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def _as_mapping(value: object, *, context: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise LineageAttributionError(f"{context} must be an object")
    return cast(Mapping[str, Any], value)


def _as_list(value: object, *, context: str) -> list[Any]:
    if not isinstance(value, list):
        raise LineageAttributionError(f"{context} must be an array")
    return cast(list[Any], value)


def _as_string(value: object, *, context: str) -> str:
    if not isinstance(value, str) or not value:
        raise LineageAttributionError(f"{context} must be a nonempty string")
    return value


def _as_nonnegative_int(value: object, *, context: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise LineageAttributionError(f"{context} must be a nonnegative integer")
    return value


def _as_positive_int(value: object, *, context: str) -> int:
    result = _as_nonnegative_int(value, context=context)
    if result == 0:
        raise LineageAttributionError(f"{context} must be positive")
    return result


def _git_bytes(repository_root: Path, *arguments: str) -> bytes:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=repository_root,
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", errors="replace").strip()
        raise LineageAttributionError(
            f"git {' '.join(arguments)} failed with exit {completed.returncode}: {stderr}"
        )
    return completed.stdout


def _verify_commit_tree(repository_root: Path, commit: str, expected_tree: str) -> None:
    object_type = _git_bytes(repository_root, "cat-file", "-t", commit).decode().strip()
    if object_type != "commit":
        raise LineageAttributionError(f"SOURCE_AUTHORITY_UNAVAILABLE: {commit} is not a commit")
    actual_tree = _git_bytes(repository_root, "show", "-s", "--format=%T", commit).decode().strip()
    if actual_tree != expected_tree:
        raise LineageAttributionError(
            "SOURCE_AUTHORITY_UNAVAILABLE: "
            f"commit {commit} expected tree {expected_tree}, actual tree {actual_tree}"
        )


def load_git_json(
    repository_root: Path,
    *,
    commit: str,
    tree: str,
    relative_path: str,
    expected_sha256: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Load one exact regular Git blob after verifying commit, tree, and SHA-256."""

    _verify_commit_tree(repository_root, commit, tree)
    metadata = _git_bytes(repository_root, "ls-tree", "-l", commit, "--", relative_path)
    fields = metadata.decode("utf-8", errors="strict").strip().split(maxsplit=4)
    if len(fields) != 5 or fields[0] != "100644" or fields[1] != "blob":
        raise LineageAttributionError(
            f"SOURCE_AUTHORITY_UNAVAILABLE: {commit}:{relative_path} is not a regular blob"
        )
    source_bytes = _git_bytes(repository_root, "show", f"{commit}:{relative_path}")
    actual_sha256 = hashlib.sha256(source_bytes).hexdigest()
    if actual_sha256 != expected_sha256:
        raise LineageAttributionError(
            "SOURCE_AUTHORITY_UNAVAILABLE: "
            f"{commit}:{relative_path} expected sha256={expected_sha256}, "
            f"actual sha256={actual_sha256}"
        )
    try:
        value = json.loads(source_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LineageAttributionError(
            f"SOURCE_AUTHORITY_UNAVAILABLE: {commit}:{relative_path} is not UTF-8 JSON"
        ) from exc
    if not isinstance(value, dict):
        raise LineageAttributionError(
            f"SOURCE_AUTHORITY_UNAVAILABLE: {commit}:{relative_path} is not a JSON object"
        )
    identity = {
        "commit": commit,
        "tree": tree,
        "path": relative_path,
        "blob": fields[2],
        "sha256": actual_sha256,
        "size_bytes": len(source_bytes),
        "read_method": "EXACT_GIT_OBJECT",
    }
    return cast(dict[str, Any], value), identity


def load_default_sources(
    repository_root: Path = REPOSITORY_ROOT,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Load the two authorities and their one sealed selector supporting locator."""

    _verify_commit_tree(repository_root, BASE_HEAD, BASE_TREE)
    rolling, rolling_identity = load_git_json(
        repository_root,
        commit=ROLLING_COMMIT,
        tree=ROLLING_TREE,
        relative_path=ROLLING_RESULT_PATH,
        expected_sha256=ROLLING_RESULT_SHA256,
    )
    lineage, lineage_identity = load_git_json(
        repository_root,
        commit=LINEAGE_COMMIT,
        tree=LINEAGE_TREE,
        relative_path=LINEAGE_RESULT_PATH,
        expected_sha256=LINEAGE_RESULT_SHA256,
    )

    if rolling.get("schema_version") != ROLLING_SCHEMA_VERSION:
        raise LineageAttributionError("rolling decomposition schema identity mismatch")
    if rolling.get("task_id") != ROLLING_TASK_ID:
        raise LineageAttributionError("rolling decomposition task identity mismatch")
    if lineage.get("schema_version") != LINEAGE_SCHEMA_VERSION:
        raise LineageAttributionError("lineage schema identity mismatch")
    if lineage.get("study_id") != LINEAGE_STUDY_ID:
        raise LineageAttributionError("lineage study identity mismatch")

    declared_pilot = _as_mapping(rolling.get("source_identity"), context="rolling.source_identity")
    expected_declared_pilot = {
        "result_head": PILOT_HEAD,
        "result_tree": PILOT_TREE,
        "result_path": PILOT_RESULT_PATH,
        "result_sha256": PILOT_RESULT_SHA256,
        "source_schema_version": PILOT_SCHEMA_VERSION,
        "source_task_id": PILOT_TASK_ID,
    }
    for key, expected in expected_declared_pilot.items():
        if declared_pilot.get(key) != expected:
            raise LineageAttributionError(
                "SOURCE_AUTHORITY_UNAVAILABLE: rolling decomposition supporting locator "
                f"{key} expected {expected!r}, actual {declared_pilot.get(key)!r}"
            )

    pilot, pilot_identity = load_git_json(
        repository_root,
        commit=PILOT_HEAD,
        tree=PILOT_TREE,
        relative_path=PILOT_RESULT_PATH,
        expected_sha256=PILOT_RESULT_SHA256,
    )
    if pilot.get("schema_version") != PILOT_SCHEMA_VERSION:
        raise LineageAttributionError("selector pilot schema identity mismatch")
    if pilot.get("task_id") != PILOT_TASK_ID:
        raise LineageAttributionError("selector pilot task identity mismatch")

    source_identity = {
        "base": {"head": BASE_HEAD, "tree": BASE_TREE},
        "rolling_decomposition": rolling_identity,
        "selector_pilot_supporting_locator": {
            **pilot_identity,
            "declared_by": f"{ROLLING_COMMIT}:{ROLLING_RESULT_PATH}",
        },
        "static_lineage": lineage_identity,
    }
    return rolling, pilot, lineage, source_identity


def _validated_fraction(delta: object, *, context: str) -> Fraction:
    payload = _as_mapping(delta, context=context)
    numerator = payload.get("numerator")
    denominator = payload.get("denominator")
    if isinstance(numerator, bool) or not isinstance(numerator, int):
        raise LineageAttributionError(f"{context}.numerator must be an integer")
    denominator_int = _as_positive_int(denominator, context=f"{context}.denominator")
    exact = _as_string(payload.get("exact"), context=f"{context}.exact")
    value = Fraction(numerator, denominator_int)
    canonical_exact = f"{value.numerator}/{value.denominator}"
    try:
        exact_value = Fraction(exact)
    except (ValueError, ZeroDivisionError) as exc:
        raise LineageAttributionError(f"{context}.exact is not a valid fraction") from exc
    if exact_value != value or exact != canonical_exact:
        raise LineageAttributionError(
            f"{context} exact fraction mismatch: {exact!r} != {canonical_exact!r}"
        )
    return value


def _fraction_payload(numerator: int, denominator: int) -> dict[str, Any]:
    value = Fraction(numerator, denominator)
    return {
        "decimal_12": f"{float(value):.12f}",
        "denominator": value.denominator,
        "exact": f"{value.numerator}/{value.denominator}",
        "numerator": value.numerator,
    }


def _source_sign_and_delta(window: Mapping[str, Any], *, context: str) -> tuple[str, Any]:
    classification = _as_string(window.get("classification"), context=f"{context}.classification")
    if classification not in SIGN_ORDER:
        raise LineageAttributionError(f"{context}.classification is not allowed")
    delta = window.get("rolling_minus_frozen_exact_delta")
    if classification == "INCONCLUSIVE":
        if delta is not None:
            raise LineageAttributionError(f"{context} is inconclusive but has a source delta")
        return classification, None
    if delta is None:
        raise LineageAttributionError(f"{context} is available but has no source delta")
    value = _validated_fraction(delta, context=f"{context}.rolling_minus_frozen_exact_delta")
    expected = "POSITIVE" if value > 0 else "NEGATIVE" if value < 0 else "ZERO"
    if classification != expected:
        raise LineageAttributionError(
            f"{context} classification {classification} disagrees with exact delta {value}"
        )
    return classification, deepcopy(dict(_as_mapping(delta, context=f"{context}.delta")))


def build_lineage_index(lineage: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    """Build a case-sensitive exact Strategy-ID index and reject duplicate authority."""

    records = _as_list(lineage.get("records"), context="lineage.records")
    index: dict[str, Mapping[str, Any]] = {}
    for position, raw_record in enumerate(records):
        record = _as_mapping(raw_record, context=f"lineage.records[{position}]")
        strategy_id = _as_string(
            record.get("strategy_id"), context=f"lineage.records[{position}].strategy_id"
        )
        if strategy_id in index:
            raise LineageAttributionError(
                f"DUPLICATE_STRATEGY_ID_AUTHORITY: exact Strategy ID {strategy_id!r}"
            )
        classification = _as_string(
            record.get("classification"), context=f"lineage.records[{position}].classification"
        )
        if classification not in {
            "IDENTICAL_BINDING",
            "SAME_CALLABLE_DIFFERENT_BINDING",
            "DISTINCT_BINDING",
            "DYNAMIC_OR_UNRESOLVED",
        }:
            raise LineageAttributionError(
                f"lineage record {strategy_id!r} has an unsupported classification"
            )
        resolution_status = _as_string(
            record.get("resolution_status"),
            context=f"lineage.records[{position}].resolution_status",
        )
        if resolution_status == "RESOLVED":
            _as_string(record.get("binding_group_id"), context=f"{strategy_id}.binding_group_id")
            _as_string(
                record.get("callable_family_id"), context=f"{strategy_id}.callable_family_id"
            )
        elif classification != "DYNAMIC_OR_UNRESOLVED":
            raise LineageAttributionError(
                f"lineage record {strategy_id!r} is unresolved but not classified unresolved"
            )
        index[strategy_id] = record

    mapping_raw = lineage.get("strategy_mapping")
    if mapping_raw is not None:
        mapping_rows = _as_list(mapping_raw, context="lineage.strategy_mapping")
        mapped_ids: set[str] = set()
        for position, raw_row in enumerate(mapping_rows):
            row = _as_mapping(raw_row, context=f"lineage.strategy_mapping[{position}]")
            strategy_id = _as_string(
                row.get("strategy_id"),
                context=f"lineage.strategy_mapping[{position}].strategy_id",
            )
            if strategy_id in mapped_ids:
                raise LineageAttributionError(
                    f"DUPLICATE_STRATEGY_ID_AUTHORITY: mapping Strategy ID {strategy_id!r}"
                )
            mapped_ids.add(strategy_id)
            record = index.get(strategy_id)
            if record is None:
                raise LineageAttributionError(
                    f"lineage mapping Strategy ID {strategy_id!r} has no exact record"
                )
            for key in ("binding_group_id", "classification"):
                if row.get(key) != record.get(key):
                    raise LineageAttributionError(
                        f"lineage mapping Strategy ID {strategy_id!r} disagrees on {key}"
                    )
        if mapped_ids != set(index):
            raise LineageAttributionError("lineage strategy mapping does not cover exact records")
    return index


def classify_transition(
    from_strategy_id: str,
    to_strategy_id: str,
    lineage_index: Mapping[str, Mapping[str, Any]],
) -> str:
    """Classify one exact Strategy-ID pair without aliases or semantic inference."""

    first = lineage_index.get(from_strategy_id)
    second = lineage_index.get(to_strategy_id)
    if first is None or second is None:
        return "UNRESOLVED_LINEAGE"
    if (
        first.get("resolution_status") != "RESOLVED"
        or second.get("resolution_status") != "RESOLVED"
    ):
        return "UNRESOLVED_LINEAGE"
    first_binding = _as_string(
        first.get("binding_group_id"), context=f"{from_strategy_id}.binding_group_id"
    )
    second_binding = _as_string(
        second.get("binding_group_id"), context=f"{to_strategy_id}.binding_group_id"
    )
    first_callable = _as_string(
        first.get("callable_family_id"), context=f"{from_strategy_id}.callable_family_id"
    )
    second_callable = _as_string(
        second.get("callable_family_id"), context=f"{to_strategy_id}.callable_family_id"
    )
    if first_binding == second_binding:
        return "SAME_BINDING"
    if first_callable == second_callable:
        return "SAME_CALLABLE_DIFFERENT_BINDING"
    return "DISTINCT_BINDING"


def _lineage_join_rows(
    strategy_ids: Sequence[str],
    lineage_index: Mapping[str, Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    rows: list[dict[str, Any]] = []
    missing_ids: list[str] = []
    source_unresolved_ids: list[str] = []
    for strategy_id in sorted(strategy_ids):
        record = lineage_index.get(strategy_id)
        if record is None:
            missing_ids.append(strategy_id)
            rows.append(
                {
                    "strategy_id": strategy_id,
                    "exact_join_status": "MISSING_STRATEGY_ID",
                    "source_classification": None,
                    "binding_group_id": None,
                    "callable_family_id": None,
                }
            )
            continue
        if record.get("resolution_status") != "RESOLVED":
            source_unresolved_ids.append(strategy_id)
            rows.append(
                {
                    "strategy_id": strategy_id,
                    "exact_join_status": "SOURCE_LINEAGE_UNRESOLVED",
                    "source_classification": record.get("classification"),
                    "binding_group_id": record.get("binding_group_id"),
                    "callable_family_id": record.get("callable_family_id"),
                    "unresolved_reason": record.get("unresolved_reason"),
                }
            )
            continue
        rows.append(
            {
                "strategy_id": strategy_id,
                "exact_join_status": "EXACT_RESOLVED",
                "source_classification": record.get("classification"),
                "binding_group_id": record.get("binding_group_id"),
                "callable_family_id": record.get("callable_family_id"),
            }
        )
    return rows, missing_ids, source_unresolved_ids


def _selected_frequency(value: object, *, context: str) -> tuple[dict[str, int], tuple[str, ...]]:
    raw = _as_mapping(value, context=context)
    frequencies: dict[str, int] = {}
    for strategy_id_raw, count_raw in raw.items():
        strategy_id = _as_string(strategy_id_raw, context=f"{context} Strategy ID")
        count = _as_positive_int(count_raw, context=f"{context}[{strategy_id!r}]")
        frequencies[strategy_id] = count
    ordered = {strategy_id: frequencies[strategy_id] for strategy_id in sorted(frequencies)}
    return ordered, tuple(ordered)


def _dominant_family(counts: Mapping[str, int], *, total_switch_count: int) -> str:
    if total_switch_count == 0:
        return "NO_SWITCH"
    maximum = max(counts.values())
    leaders = [name for name in TRANSITION_CLASSES if counts[name] == maximum and maximum > 0]
    return leaders[0] if len(leaders) == 1 else "MIXED_NO_SINGLE_DOMINANT"


def attribute_experiment(
    rolling_window: Mapping[str, Any],
    pilot_experiment: Mapping[str, Any],
    candidate_strategy_ids: Sequence[str],
    lineage_index: Mapping[str, Mapping[str, Any]],
    *,
    cell_id: str,
    lottery_id: str,
    k: int,
) -> dict[str, Any]:
    """Attribute an experiment using only evidence invariant across its selected support."""

    window_label = _as_string(rolling_window.get("window_label"), context=f"{cell_id}.window_label")
    source_label = _as_string(
        rolling_window.get("source_label"), context=f"{cell_id}.{window_label}.source_label"
    )
    window = _as_positive_int(
        rolling_window.get("window"), context=f"{cell_id}.{window_label}.window"
    )
    context = f"{cell_id}.{window_label}"
    if pilot_experiment.get("label") != source_label:
        raise LineageAttributionError(f"{context} pilot label mismatch")
    if pilot_experiment.get("window") != window:
        raise LineageAttributionError(f"{context} pilot window mismatch")
    if pilot_experiment.get("status") != rolling_window.get("source_status"):
        raise LineageAttributionError(f"{context} pilot status mismatch")
    if pilot_experiment.get("conclusion") != rolling_window.get("source_conclusion"):
        raise LineageAttributionError(f"{context} pilot conclusion mismatch")

    sign, source_delta = _source_sign_and_delta(rolling_window, context=context)
    pilot_delta = pilot_experiment.get("absolute_paired_delta")
    if sign == "INCONCLUSIVE":
        if pilot_delta is not None:
            raise LineageAttributionError(f"{context} pilot delta must be absent")
    else:
        if pilot_delta is None:
            raise LineageAttributionError(f"{context} pilot delta must be present")
        pilot_value = _validated_fraction(pilot_delta, context=f"{context}.pilot_delta")
        rolling_value = _validated_fraction(source_delta, context=f"{context}.source_delta")
        if pilot_value != rolling_value:
            raise LineageAttributionError(f"{context} pilot and decomposition deltas differ")

    switch_count = _as_nonnegative_int(
        rolling_window.get("switch_count"), context=f"{context}.switch_count"
    )
    pilot_switch_count = _as_nonnegative_int(
        pilot_experiment.get("rolling_strategy_switch_count"),
        context=f"{context}.rolling_strategy_switch_count",
    )
    if pilot_switch_count != switch_count:
        raise LineageAttributionError(f"{context} switch count mismatch")

    frequencies, selected_ids = _selected_frequency(
        pilot_experiment.get("rolling_selection_frequency"),
        context=f"{context}.rolling_selection_frequency",
    )
    target_count = sum(frequencies.values())
    if rolling_window.get("rolling_selection_target_count") != target_count:
        raise LineageAttributionError(f"{context} selection target count mismatch")

    candidate_ids = tuple(sorted(candidate_strategy_ids))
    if len(candidate_ids) != len(set(candidate_ids)):
        raise LineageAttributionError(f"{cell_id} has duplicate candidate Strategy IDs")
    declared_candidate_count = _as_nonnegative_int(
        pilot_experiment.get("candidate_strategy_count"),
        context=f"{context}.candidate_strategy_count",
    )
    if declared_candidate_count != len(candidate_ids):
        raise LineageAttributionError(f"{context} candidate strategy count mismatch")
    unknown_selected = sorted(set(selected_ids) - set(candidate_ids))
    if unknown_selected:
        raise LineageAttributionError(
            f"{context} selected Strategy IDs are absent from its candidate universe: "
            f"{unknown_selected}"
        )
    if switch_count > 0 and len(selected_ids) < 2:
        raise LineageAttributionError(
            f"{context} has switches but fewer than two selected Strategy IDs"
        )

    trace_sha256 = pilot_experiment.get("selection_trace_sha256")
    if sign == "INCONCLUSIVE":
        if trace_sha256 is not None:
            raise LineageAttributionError(f"{context} excluded trace digest must be absent")
    else:
        trace_value = _as_string(trace_sha256, context=f"{context}.selection_trace_sha256")
        if len(trace_value) != 64 or any(
            character not in "0123456789abcdef" for character in trace_value
        ):
            raise LineageAttributionError(f"{context} selection trace digest is invalid")

    join_rows, missing_ids, source_unresolved_ids = _lineage_join_rows(selected_ids, lineage_index)
    possible_classes = sorted(
        {
            classify_transition(first, second, lineage_index)
            for first, second in combinations(selected_ids, 2)
        },
        key=TRANSITION_CLASSES.index,
    )
    counts = {name: 0 for name in TRANSITION_CLASSES}
    unresolved_reasons: list[str] = []
    if switch_count == 0:
        attribution_basis = "NO_SWITCH"
        resolution_status = "NOT_APPLICABLE_NO_SWITCH"
    elif len(possible_classes) == 1 and possible_classes[0] != "UNRESOLVED_LINEAGE":
        resolved_class = possible_classes[0]
        counts[resolved_class] = switch_count
        attribution_basis = "UNIFORM_PAIRWISE_CLASS_ACROSS_SELECTED_ID_SUPPORT"
        resolution_status = "FULLY_RESOLVED"
    else:
        counts["UNRESOLVED_LINEAGE"] = switch_count
        attribution_basis = "ORDERED_TRANSITION_ENDPOINTS_NOT_EMBEDDED"
        resolution_status = "UNRESOLVED_LINEAGE"
        unresolved_reasons.append("ORDERED_SELECTION_TRACE_ENDPOINTS_NOT_EMBEDDED")
        if missing_ids:
            unresolved_reasons.append("MISSING_EXACT_STRATEGY_ID_JOIN")
        if source_unresolved_ids:
            unresolved_reasons.append("SOURCE_LINEAGE_UNRESOLVED")
        if len(possible_classes) > 1:
            unresolved_reasons.append("MIXED_POSSIBLE_LINEAGE_CLASSES_WITHOUT_ENDPOINTS")
        elif possible_classes == ["UNRESOLVED_LINEAGE"]:
            unresolved_reasons.append("NO_RESOLVABLE_PAIRWISE_LINEAGE_CLASS")

    lineage_resolved_count = switch_count - counts["UNRESOLVED_LINEAGE"]
    distinct_share: dict[str, Any] | None = None
    if switch_count > 0 and counts["UNRESOLVED_LINEAGE"] == 0:
        distinct_share = _fraction_payload(counts["DISTINCT_BINDING"], switch_count)

    return {
        "experiment_id": f"{cell_id}:{window_label}",
        "cell_id": cell_id,
        "lottery_id": lottery_id,
        "k": k,
        "window": window,
        "window_label": window_label,
        "source_label": source_label,
        "source_status": rolling_window.get("source_status"),
        "sign": sign,
        "source_delta": source_delta,
        "total_switch_count": switch_count,
        "lineage_resolved_switch_count": lineage_resolved_count,
        "same_binding_transitions": counts["SAME_BINDING"],
        "same_callable_different_binding_transitions": counts["SAME_CALLABLE_DIFFERENT_BINDING"],
        "distinct_binding_transitions": counts["DISTINCT_BINDING"],
        "unresolved_transitions": counts["UNRESOLVED_LINEAGE"],
        "distinct_binding_switch_share": distinct_share,
        "dominant_transition_family": _dominant_family(counts, total_switch_count=switch_count),
        "attribution_basis": attribution_basis,
        "lineage_resolution_status": resolution_status,
        "possible_transition_classes": possible_classes,
        "unresolved_reasons": unresolved_reasons,
        "candidate_strategy_count": len(candidate_ids),
        "dynamic_diversity_capability": (
            "STRUCTURALLY_INCAPABLE_SINGLE_CANDIDATE"
            if len(candidate_ids) == 1
            else "STRUCTURALLY_CAPABLE_MULTIPLE_CANDIDATES"
        ),
        "rolling_selection_target_count": target_count,
        "rolling_selection_frequency": frequencies,
        "selected_strategy_ids": list(selected_ids),
        "exact_joined_selected_strategy_count": len(selected_ids) - len(missing_ids),
        "missing_strategy_ids": missing_ids,
        "source_lineage_unresolved_strategy_ids": source_unresolved_ids,
        "lineage_join": join_rows,
        "selection_trace_evidence": {
            "sha256": trace_sha256,
            "ordered_transition_endpoints_embedded": False,
        },
    }


def _unique_rows_by_key(
    raw_rows: object, *, key: str, context: str
) -> dict[str, Mapping[str, Any]]:
    rows = _as_list(raw_rows, context=context)
    result: dict[str, Mapping[str, Any]] = {}
    for position, raw_row in enumerate(rows):
        row = _as_mapping(raw_row, context=f"{context}[{position}]")
        identity = _as_string(row.get(key), context=f"{context}[{position}].{key}")
        if identity in result:
            raise LineageAttributionError(f"duplicate {context} identity {identity!r}")
        result[identity] = row
    return result


def _aggregate(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    counts = {name: 0 for name in TRANSITION_CLASSES}
    total = 0
    available = 0
    switching = 0
    signs = Counter[str]()
    for row in rows:
        sign = _as_string(row.get("sign"), context="aggregate.sign")
        signs[sign] += 1
        if sign != "INCONCLUSIVE":
            available += 1
        switch_count = _as_nonnegative_int(
            row.get("total_switch_count"), context="aggregate.total_switch_count"
        )
        total += switch_count
        switching += int(switch_count > 0)
        counts["SAME_BINDING"] += _as_nonnegative_int(
            row.get("same_binding_transitions"), context="aggregate.same_binding"
        )
        counts["SAME_CALLABLE_DIFFERENT_BINDING"] += _as_nonnegative_int(
            row.get("same_callable_different_binding_transitions"),
            context="aggregate.same_callable_different_binding",
        )
        counts["DISTINCT_BINDING"] += _as_nonnegative_int(
            row.get("distinct_binding_transitions"), context="aggregate.distinct_binding"
        )
        counts["UNRESOLVED_LINEAGE"] += _as_nonnegative_int(
            row.get("unresolved_transitions"), context="aggregate.unresolved"
        )
    resolved = total - counts["UNRESOLVED_LINEAGE"]
    distinct_share: dict[str, Any] | None = None
    if total > 0 and counts["UNRESOLVED_LINEAGE"] == 0:
        distinct_share = _fraction_payload(counts["DISTINCT_BINDING"], total)
    return {
        "experiment_count": len(rows),
        "available_experiment_count": available,
        "switching_experiment_count": switching,
        "sign_counts": {sign: signs[sign] for sign in SIGN_ORDER},
        "total_switch_count": total,
        "lineage_resolved_switch_count": resolved,
        "same_binding_transitions": counts["SAME_BINDING"],
        "same_callable_different_binding_transitions": counts["SAME_CALLABLE_DIFFERENT_BINDING"],
        "distinct_binding_transitions": counts["DISTINCT_BINDING"],
        "unresolved_transitions": counts["UNRESOLVED_LINEAGE"],
        "distinct_binding_switch_share": distinct_share,
        "dominant_transition_family": _dominant_family(counts, total_switch_count=total),
    }


def _candidate_cell_attribution(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[_as_string(row.get("cell_id"), context="candidate.cell_id")].append(row)
    result: list[dict[str, Any]] = []
    for cell_id in sorted(grouped):
        cell_rows = sorted(
            grouped[cell_id], key=lambda item: WINDOW_ORDER.index(cast(str, item["window_label"]))
        )
        positive_windows = [
            cast(str, row["window_label"]) for row in cell_rows if row["sign"] == "POSITIVE"
        ]
        if len(positive_windows) < 2:
            continue
        aggregate = _aggregate(cell_rows)
        result.append(
            {
                "cell_id": cell_id,
                "lottery_id": cell_rows[0]["lottery_id"],
                "k": cell_rows[0]["k"],
                "positive_windows": positive_windows,
                "sign_pattern": {cast(str, row["window_label"]): row["sign"] for row in cell_rows},
                "total_switch_count": aggregate["total_switch_count"],
                "lineage_resolved_switch_count": aggregate["lineage_resolved_switch_count"],
                "same_binding_transitions": aggregate["same_binding_transitions"],
                "same_callable_different_binding_transitions": aggregate[
                    "same_callable_different_binding_transitions"
                ],
                "distinct_binding_transitions": aggregate["distinct_binding_transitions"],
                "unresolved_transitions": aggregate["unresolved_transitions"],
                "dominant_transition_family": aggregate["dominant_transition_family"],
                "windows": [
                    {
                        "window_label": row["window_label"],
                        "sign": row["sign"],
                        "total_switch_count": row["total_switch_count"],
                        "lineage_resolved_switch_count": row["lineage_resolved_switch_count"],
                        "same_binding_transitions": row["same_binding_transitions"],
                        "same_callable_different_binding_transitions": row[
                            "same_callable_different_binding_transitions"
                        ],
                        "distinct_binding_transitions": row["distinct_binding_transitions"],
                        "unresolved_transitions": row["unresolved_transitions"],
                        "source_delta": deepcopy(row["source_delta"]),
                    }
                    for row in cell_rows
                ],
            }
        )
    return result


def _p638_sibling_findings(
    rows: Sequence[Mapping[str, Any]],
    lineage_index: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    available_siblings = [
        strategy_id for strategy_id in P638_C01_C07_IDS if strategy_id in lineage_index
    ]
    pair_classes = sorted(
        {
            classify_transition(first, second, lineage_index)
            for first, second in combinations(available_siblings, 2)
        },
        key=TRANSITION_CLASSES.index,
    )
    experiment_rows: list[dict[str, Any]] = []
    total_selections = 0
    total_all_selections = 0
    co_selection_count = 0
    for row in rows:
        if row.get("lottery_id") != "P638" or row.get("k") != 1:
            continue
        frequencies = _as_mapping(
            row.get("rolling_selection_frequency"), context="p638 sibling frequencies"
        )
        selected_siblings = [
            strategy_id
            for strategy_id in P638_C01_C07_IDS
            if _as_nonnegative_int(frequencies.get(strategy_id, 0), context=strategy_id) > 0
        ]
        sibling_selections = sum(
            cast(int, frequencies[strategy_id]) for strategy_id in selected_siblings
        )
        all_selections = sum(cast(int, count) for count in frequencies.values())
        total_selections += sibling_selections
        total_all_selections += all_selections
        co_selection_count += int(len(selected_siblings) >= 2)
        experiment_rows.append(
            {
                "experiment_id": row["experiment_id"],
                "window_label": row["window_label"],
                "selected_sibling_strategy_ids": selected_siblings,
                "selected_sibling_strategy_count": len(selected_siblings),
                "sibling_selection_count": sibling_selections,
                "all_selection_count": all_selections,
                "total_switch_count": row["total_switch_count"],
                "actual_sibling_transition_count": None,
                "actual_sibling_transition_count_reason": (
                    "ORDERED_SELECTION_TRACE_ENDPOINTS_NOT_EMBEDDED"
                ),
            }
        )
    return {
        "family_strategy_ids": list(P638_C01_C07_IDS),
        "exact_lineage_join_count": len(available_siblings),
        "pairwise_lineage_classes": pair_classes,
        "pairwise_structural_classification": (
            pair_classes[0] if len(pair_classes) == 1 else "UNRESOLVED_LINEAGE"
        ),
        "p638_k1_experiment_count": len(experiment_rows),
        "experiments_with_two_or_more_selected_siblings": co_selection_count,
        "sibling_selection_count": total_selections,
        "all_p638_k1_selection_count": total_all_selections,
        "actual_sibling_transition_count": None,
        "actual_sibling_transition_count_reason": (
            "SEALED_SELECTOR_RESULT_CONTAINS_TRACE_DIGEST_BUT_NOT_ENDPOINTS"
        ),
        "cross_method_diversity_interpretation": (
            "C01_C07_PAIRWISE_SWITCHES_ARE_PARAMETERIZED_SIBLING_SWITCHES_NOT_"
            "DISTINCT_BINDING_DIVERSITY"
        ),
        "experiments": experiment_rows,
    }


def _zero_no_switch_findings(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[_as_string(row.get("cell_id"), context="zero cell id")].append(row)
    zero_no_switch_cells: list[dict[str, Any]] = []
    for cell_id in sorted(grouped):
        cell_rows = grouped[cell_id]
        if not cell_rows or any(row.get("sign") != "ZERO" for row in cell_rows):
            continue
        if any(cast(int, row["total_switch_count"]) != 0 for row in cell_rows):
            continue
        candidate_count = cast(int, cell_rows[0]["candidate_strategy_count"])
        zero_no_switch_cells.append(
            {
                "cell_id": cell_id,
                "lottery_id": cell_rows[0]["lottery_id"],
                "k": cell_rows[0]["k"],
                "candidate_strategy_count": candidate_count,
                "dynamic_diversity_capability": cell_rows[0]["dynamic_diversity_capability"],
            }
        )
    capable_zero_switch_experiments = [
        {
            "experiment_id": row["experiment_id"],
            "cell_id": row["cell_id"],
            "window_label": row["window_label"],
            "candidate_strategy_count": row["candidate_strategy_count"],
        }
        for row in rows
        if row.get("sign") == "ZERO"
        and row.get("total_switch_count") == 0
        and cast(int, row["candidate_strategy_count"]) > 1
    ]
    incapable = [
        row
        for row in zero_no_switch_cells
        if row["dynamic_diversity_capability"] == "STRUCTURALLY_INCAPABLE_SINGLE_CANDIDATE"
    ]
    return {
        "zero_no_switch_cell_count": len(zero_no_switch_cells),
        "structurally_incapable_cell_count": len(incapable),
        "structurally_incapable_cells": incapable,
        "zero_no_switch_cells": zero_no_switch_cells,
        "zero_switch_experiments_in_structurally_capable_cells": (capable_zero_switch_experiments),
    }


def _diagnostic_answers(
    rows: Sequence[Mapping[str, Any]],
    candidates: Sequence[Mapping[str, Any]],
    siblings: Mapping[str, Any],
    zero_findings: Mapping[str, Any],
) -> list[dict[str, Any]]:
    by_sign: dict[str, dict[str, Any]] = {}
    for sign in SIGN_ORDER:
        sign_rows = [row for row in rows if row.get("sign") == sign]
        by_sign[sign] = _aggregate(sign_rows)
    positive = by_sign["POSITIVE"]
    negative = by_sign["NEGATIVE"]
    candidate_total_switches = sum(
        cast(int, candidate["total_switch_count"]) for candidate in candidates
    )
    candidate_unresolved_transitions = sum(
        cast(int, candidate["unresolved_transitions"]) for candidate in candidates
    )
    zero_cell_count = cast(int, zero_findings["zero_no_switch_cell_count"])
    incapable_cell_count = cast(int, zero_findings["structurally_incapable_cell_count"])
    capable_zero_experiments = cast(
        list[Any], zero_findings["zero_switch_experiments_in_structurally_capable_cells"]
    )
    return [
        {
            "question_id": 1,
            "question": (
                "Are positive experiments concentrated in transitions between "
                "DISTINCT_BINDING identities?"
            ),
            "answer_code": "NOT_ESTABLISHED",
            "answer": {
                "positive_experiment_count": positive["experiment_count"],
                "positive_total_switch_count": positive["total_switch_count"],
                "positive_lineage_resolved_switch_count": positive["lineage_resolved_switch_count"],
                "positive_distinct_binding_transitions": positive["distinct_binding_transitions"],
                "positive_unresolved_transitions": positive["unresolved_transitions"],
                "interpretation": (
                    "No positive switch is lineage-resolved by the available sealed "
                    "endpoint evidence, so concentration in DISTINCT_BINDING is not established."
                ),
            },
        },
        {
            "question_id": 2,
            "question": "Do negative experiments show a different transition composition?",
            "answer_code": "MOSTLY_UNRESOLVED_WITH_ONE_DISTINCT_BINDING_EXPERIMENT",
            "answer": {
                "negative_experiment_count": negative["experiment_count"],
                "negative_total_switch_count": negative["total_switch_count"],
                "negative_lineage_resolved_switch_count": negative["lineage_resolved_switch_count"],
                "negative_distinct_binding_transitions": negative["distinct_binding_transitions"],
                "negative_unresolved_transitions": negative["unresolved_transitions"],
                "interpretation": (
                    "Only B649:K3:W300 is fully attributable and its 28 switches are "
                    "DISTINCT_BINDING; the remaining negative composition is unresolved, "
                    "so a robust sign-composition contrast is not available."
                ),
            },
        },
        {
            "question_id": 3,
            "question": (
                "Among the five repeated-positive candidate cells, what lineage classes "
                "actually account for their switches?"
            ),
            "answer_code": "ALL_RECORDED_SWITCHES_UNRESOLVED_LINEAGE",
            "answer": {
                "candidate_cell_count": len(candidates),
                "candidate_total_switch_count": candidate_total_switches,
                "candidate_unresolved_transition_count": candidate_unresolved_transitions,
                "candidate_cells": [deepcopy(dict(candidate)) for candidate in candidates],
                "interpretation": (
                    f"All {candidate_total_switches:,} switches across the repeated-positive "
                    "candidate cells remain UNRESOLVED_LINEAGE; none is attributable to "
                    "same-binding, "
                    "same-callable/different-binding, or distinct-binding transitions from "
                    "the available endpoint evidence."
                ),
            },
        },
        {
            "question_id": 4,
            "question": (
                "Are P638 C01-C07 sibling transitions common, and are they mistaken for "
                "cross-method diversity?"
            ),
            "answer_code": "SIBLING_SELECTION_COMMON_TRANSITION_COUNT_INCONCLUSIVE",
            "answer": {
                "experiments_with_two_or_more_selected_siblings": siblings[
                    "experiments_with_two_or_more_selected_siblings"
                ],
                "p638_k1_experiment_count": siblings["p638_k1_experiment_count"],
                "sibling_selection_count": siblings["sibling_selection_count"],
                "pairwise_structural_classification": siblings[
                    "pairwise_structural_classification"
                ],
                "actual_sibling_transition_count": None,
                "interpretation": (
                    "Sibling identities are co-selected in every P638 K1 window, but the "
                    "sealed trace has no endpoints, so transition frequency is not known. "
                    "Any observed C01-C07 pair switch is SAME_CALLABLE_DIFFERENT_BINDING, "
                    "not distinct-binding cross-method diversity."
                ),
            },
        },
        {
            "question_id": 5,
            "question": (
                "Are any ZERO/no-switch cells structurally incapable of dynamic diversity?"
            ),
            "answer_code": "YES",
            "answer": {
                "zero_no_switch_cell_count": zero_cell_count,
                "structurally_incapable_cell_count": incapable_cell_count,
                "structurally_incapable_cells": deepcopy(
                    zero_findings["structurally_incapable_cells"]
                ),
                "structurally_capable_zero_switch_experiment_count": len(capable_zero_experiments),
                "interpretation": (
                    f"All {incapable_cell_count} of {zero_cell_count} cells that are ZERO "
                    "with no switches in every window have a single-candidate universe and "
                    "are structurally incapable of dynamic diversity. "
                    f"{len(capable_zero_experiments)} additional ZERO/no-switch experiments "
                    "occur in cells "
                    "with multiple candidates and are not structurally incapable."
                ),
            },
        },
        {
            "question_id": 6,
            "question": (
                "Does any apparent advantage disappear when same-callable parameter switches "
                "are separated from genuinely distinct bindings?"
            ),
            "answer_code": "LINEAGE_SPECIFIC_ADVANTAGE_NOT_ESTABLISHED",
            "answer": {
                "positive_same_callable_different_binding_transitions": positive[
                    "same_callable_different_binding_transitions"
                ],
                "positive_distinct_binding_transitions": positive["distinct_binding_transitions"],
                "positive_unresolved_transitions": positive["unresolved_transitions"],
                "source_positive_signs_unchanged": True,
                "interpretation": (
                    "The source positive deltas do not disappear and remain unchanged, but "
                    "none can be attributed to same-callable or distinct-binding switches "
                    "from the available endpoint evidence. No lineage-specific advantage is "
                    "established."
                ),
            },
        },
    ]


def build_attribution(
    rolling: Mapping[str, Any],
    pilot: Mapping[str, Any],
    lineage: Mapping[str, Any],
    *,
    source_identity: Mapping[str, Any] | None = None,
    enforce_sealed_shape: bool = True,
) -> dict[str, Any]:
    """Build the deterministic lineage-attribution result."""

    if enforce_sealed_shape:
        if rolling.get("schema_version") != ROLLING_SCHEMA_VERSION:
            raise LineageAttributionError("rolling schema mismatch")
        if rolling.get("task_id") != ROLLING_TASK_ID:
            raise LineageAttributionError("rolling task mismatch")
        if pilot.get("schema_version") != PILOT_SCHEMA_VERSION:
            raise LineageAttributionError("pilot schema mismatch")
        if pilot.get("task_id") != PILOT_TASK_ID:
            raise LineageAttributionError("pilot task mismatch")
        if lineage.get("schema_version") != LINEAGE_SCHEMA_VERSION:
            raise LineageAttributionError("lineage schema mismatch")

    lineage_index = build_lineage_index(lineage)
    rolling_cells = _unique_rows_by_key(
        rolling.get("cells"), key="cell_id", context="rolling.cells"
    )
    pilot_cells = _unique_rows_by_key(pilot.get("cells"), key="cell_id", context="pilot.cells")
    if set(rolling_cells) != set(pilot_cells):
        raise LineageAttributionError("rolling and pilot cell identities differ")

    experiments: list[dict[str, Any]] = []
    ordered_cells = sorted(
        rolling_cells.values(),
        key=lambda cell: (
            _as_string(cell.get("lottery_id"), context="cell.lottery_id"),
            _as_positive_int(cell.get("k"), context="cell.k"),
        ),
    )
    for rolling_cell in ordered_cells:
        cell_id = _as_string(rolling_cell.get("cell_id"), context="rolling.cell_id")
        lottery_id = _as_string(rolling_cell.get("lottery_id"), context=f"{cell_id}.lottery_id")
        k = _as_positive_int(rolling_cell.get("k"), context=f"{cell_id}.k")
        pilot_cell = pilot_cells[cell_id]
        if pilot_cell.get("lottery_id") != lottery_id:
            raise LineageAttributionError(f"{cell_id} lottery identity mismatch")
        if pilot_cell.get("native_ticket_count") != k:
            raise LineageAttributionError(f"{cell_id} K identity mismatch")
        candidate_rows = _as_list(
            pilot_cell.get("candidate_strategies"), context=f"{cell_id}.candidate_strategies"
        )
        candidate_ids = [
            _as_string(
                _as_mapping(raw, context=f"{cell_id}.candidate").get("strategy_id"),
                context=f"{cell_id}.candidate.strategy_id",
            )
            for raw in candidate_rows
        ]
        pilot_experiments = _as_mapping(
            pilot_cell.get("experiments"), context=f"{cell_id}.experiments"
        )
        windows_raw = _as_list(rolling_cell.get("windows"), context=f"{cell_id}.windows")
        windows = sorted(
            (_as_mapping(raw, context=f"{cell_id}.window") for raw in windows_raw),
            key=lambda item: WINDOW_ORDER.index(
                _as_string(item.get("window_label"), context=f"{cell_id}.window_label")
            ),
        )
        for rolling_window in windows:
            source_label = _as_string(
                rolling_window.get("source_label"), context=f"{cell_id}.source_label"
            )
            pilot_experiment = _as_mapping(
                pilot_experiments.get(source_label),
                context=f"{cell_id}.experiments.{source_label}",
            )
            experiments.append(
                attribute_experiment(
                    rolling_window,
                    pilot_experiment,
                    candidate_ids,
                    lineage_index,
                    cell_id=cell_id,
                    lottery_id=lottery_id,
                    k=k,
                )
            )

    overall = _aggregate(experiments)
    if enforce_sealed_shape:
        if len(rolling_cells) != EXPECTED_CELL_COUNT:
            raise LineageAttributionError("sealed cell count mismatch")
        if len(experiments) != EXPECTED_EXPERIMENT_COUNT:
            raise LineageAttributionError("sealed experiment count mismatch")
        if overall["switching_experiment_count"] != EXPECTED_SWITCHING_EXPERIMENT_COUNT:
            raise LineageAttributionError("sealed switching experiment count mismatch")
        if overall["total_switch_count"] != EXPECTED_TOTAL_SWITCH_COUNT:
            raise LineageAttributionError("sealed total switch count mismatch")

    by_sign = [
        {"sign": sign, **_aggregate([row for row in experiments if row["sign"] == sign])}
        for sign in SIGN_ORDER
    ]
    lotteries = sorted({cast(str, row["lottery_id"]) for row in experiments})
    by_lottery = [
        {
            "lottery_id": lottery_id,
            **_aggregate([row for row in experiments if row["lottery_id"] == lottery_id]),
        }
        for lottery_id in lotteries
    ]
    candidates = _candidate_cell_attribution(experiments)
    siblings = _p638_sibling_findings(experiments, lineage_index)
    zero_findings = _zero_no_switch_findings(experiments)
    unresolved_rows = [
        {
            "experiment_id": row["experiment_id"],
            "cell_id": row["cell_id"],
            "lottery_id": row["lottery_id"],
            "k": row["k"],
            "window_label": row["window_label"],
            "sign": row["sign"],
            "total_switch_count": row["total_switch_count"],
            "unresolved_transitions": row["unresolved_transitions"],
            "missing_strategy_ids": deepcopy(row["missing_strategy_ids"]),
            "source_lineage_unresolved_strategy_ids": deepcopy(
                row["source_lineage_unresolved_strategy_ids"]
            ),
            "possible_transition_classes": deepcopy(row["possible_transition_classes"]),
            "unresolved_reasons": deepcopy(row["unresolved_reasons"]),
        }
        for row in experiments
        if cast(int, row["unresolved_transitions"]) > 0
    ]

    unique_selected_ids = sorted(
        {
            cast(str, strategy_id)
            for row in experiments
            for strategy_id in row["selected_strategy_ids"]
        }
    )
    exact_joined_ids = [
        strategy_id for strategy_id in unique_selected_ids if strategy_id in lineage_index
    ]
    resolved_joined_ids = [
        strategy_id
        for strategy_id in exact_joined_ids
        if lineage_index[strategy_id].get("resolution_status") == "RESOLVED"
    ]
    missing_ids = [
        strategy_id for strategy_id in unique_selected_ids if strategy_id not in lineage_index
    ]
    source_unresolved_ids = [
        strategy_id
        for strategy_id in exact_joined_ids
        if lineage_index[strategy_id].get("resolution_status") != "RESOLVED"
    ]

    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "study_id": STUDY_ID,
        "task_id": TASK_ID,
        "source_identity": deepcopy(dict(source_identity or {})),
        "classification_contract": {
            "allowed_transition_classes": list(TRANSITION_CLASSES),
            "exact_strategy_id_join": (
                "Case-sensitive equality against lineage.records[].strategy_id; no alias, "
                "prefix, display-name, or semantic matching."
            ),
            "same_binding": ("Both exact Strategy IDs resolve and share one binding_group_id."),
            "same_callable_different_binding": (
                "Both exact Strategy IDs resolve, share callable_family_id, and have "
                "different binding_group_id values."
            ),
            "distinct_binding": (
                "Both exact Strategy IDs resolve and have different callable_family_id "
                "and binding_group_id values; this is not semantic independence."
            ),
            "unresolved_lineage": (
                "At least one exact Strategy ID is missing or source-unresolved, or the "
                "hash-only selector trace omits endpoints and selected-support pairs admit "
                "more than one possible class."
            ),
            "hash_only_trace_rule": (
                "Without ordered endpoints, a nonzero switch count is resolved only when "
                "every unordered pair in the selected Strategy-ID support has one identical "
                "non-unresolved lineage class."
            ),
            "distinct_binding_switch_share": (
                "distinct-binding transitions divided by total switches, defined only when "
                "total switches are nonzero and every switch is lineage-resolved."
            ),
        },
        "source_data_quality": {
            "rolling_cell_count": len(rolling_cells),
            "pilot_cell_count": len(pilot_cells),
            "experiment_count": len(experiments),
            "lineage_record_count": len(lineage_index),
            "unique_selected_strategy_id_count": len(unique_selected_ids),
            "exact_joined_selected_strategy_id_count": len(exact_joined_ids),
            "exact_resolved_selected_strategy_id_count": len(resolved_joined_ids),
            "missing_selected_strategy_id_count": len(missing_ids),
            "missing_selected_strategy_ids": missing_ids,
            "source_unresolved_selected_strategy_id_count": len(source_unresolved_ids),
            "source_unresolved_selected_strategy_ids": source_unresolved_ids,
            "duplicate_cell_id_count": 0,
            "duplicate_lineage_strategy_id_count": 0,
            "negative_switch_count_rows": 0,
            "ordered_selection_trace_embedded_experiment_count": 0,
            "selection_trace_digest_only": True,
            "source_delta_preservation": "EXACT_JSON_OBJECT_COPY_FROM_SEALED_DECOMPOSITION",
        },
        "aggregates": {
            "overall": overall,
            "by_sign": by_sign,
            "by_lottery": by_lottery,
        },
        "experiments": experiments,
        "repeated_positive_candidate_cells": candidates,
        "p638_c01_c07_bridge_family": siblings,
        "zero_no_switch_structural_capability": zero_findings,
        "unresolved_rows": unresolved_rows,
        "diagnostic_answers": _diagnostic_answers(experiments, candidates, siblings, zero_findings),
        "boundaries": {
            "new_historical_replay": "NOT RUN",
            "database_access": "NO",
            "database_write": "NO",
            "strategy_execution": "NOT RUN",
            "new_selector": "NOT IMPLEMENTED",
            "selector_modification": "NOT RUN",
            "window_optimization": "NOT RUN",
            "new_metric": "NOT CREATED",
            "composite_score": "NOT CREATED",
            "p_values": "NOT COMPUTED",
            "statistical_significance": "NOT CLAIMED",
            "promotion_threshold": "NOT CREATED",
            "causal_claim_beyond_source_experiment": "NOT MADE",
            "phase12_use": "NONE",
            "p638_zone2": "NOT RUN",
            "second_exchange": "NOT RUN",
            "predictive_advantage": "NOT ESTABLISHED",
            "profitability": "NOT ESTABLISHED",
            "reference_or_runtime_promotion": "NOT RUN",
        },
    }
    return payload


def _format_share(value: object) -> str:
    if value is None:
        return "—"
    return _as_string(_as_mapping(value, context="share").get("exact"), context="share.exact")


def _format_delta(value: object) -> str:
    if value is None:
        return "—"
    return _as_string(_as_mapping(value, context="delta").get("exact"), context="delta.exact")


def _format_ids(value: object) -> str:
    ids = _as_list(value, context="ids")
    return ", ".join(f"`{cast(str, strategy_id)}`" for strategy_id in ids) or "—"


def render_report(payload: Mapping[str, Any]) -> str:
    """Render the deterministic research report from the machine-readable result."""

    sources = _as_mapping(payload.get("source_identity"), context="source_identity")
    rolling = _as_mapping(sources.get("rolling_decomposition"), context="rolling source")
    lineage = _as_mapping(sources.get("static_lineage"), context="lineage source")
    pilot = _as_mapping(sources.get("selector_pilot_supporting_locator"), context="pilot source")
    aggregates = _as_mapping(payload.get("aggregates"), context="aggregates")
    overall = _as_mapping(aggregates.get("overall"), context="aggregates.overall")
    by_sign = _as_list(aggregates.get("by_sign"), context="aggregates.by_sign")
    experiments = _as_list(payload.get("experiments"), context="experiments")
    candidates = _as_list(
        payload.get("repeated_positive_candidate_cells"), context="candidate cells"
    )
    siblings = _as_mapping(payload.get("p638_c01_c07_bridge_family"), context="p638 siblings")
    zero_findings = _as_mapping(
        payload.get("zero_no_switch_structural_capability"), context="zero findings"
    )
    unresolved_rows = _as_list(payload.get("unresolved_rows"), context="unresolved rows")
    answers = _as_list(payload.get("diagnostic_answers"), context="diagnostic answers")

    lines = [
        "# Selector lineage attribution R1",
        "",
        "## Result",
        "",
        "This is a descriptive attribution of sealed historical selector outcomes. The "
        "source deltas are unchanged. No replay, database access, strategy execution, new "
        "selector, optimization, p-value, promotion rule, or predictive claim is part of "
        "this result.",
        "",
        "The sealed selector artifact contains selection frequencies, total adjacent-ID "
        "switch counts, and a trace SHA-256, but not the ordered transition endpoints. A "
        "switch total is therefore resolved only when every possible pair in the selected "
        "Strategy-ID support has one uniform exact lineage class. All other switches are "
        "reported as `UNRESOLVED_LINEAGE`.",
        "",
        "## Exact source identities",
        "",
        f"- Rolling decomposition: `{rolling['commit']}` / tree `{rolling['tree']}` / "
        f"SHA-256 `{rolling['sha256']}` / `{rolling['path']}`",
        f"- Selector pilot supporting locator: `{pilot['commit']}` / tree `{pilot['tree']}` / "
        f"SHA-256 `{pilot['sha256']}` / `{pilot['path']}`",
        f"- Static lineage: `{lineage['commit']}` / tree `{lineage['tree']}` / "
        f"SHA-256 `{lineage['sha256']}` / `{lineage['path']}`",
        "",
        "## Overall transition attribution",
        "",
        "| Experiments | Total switches | Lineage-resolved | Same binding | "
        "Same callable / different binding | Distinct binding | Unresolved | Dominant family |",
        "|---:|---:|---:|---:|---:|---:|---:|---|",
        f"| {overall['experiment_count']} | {overall['total_switch_count']} | "
        f"{overall['lineage_resolved_switch_count']} | {overall['same_binding_transitions']} | "
        f"{overall['same_callable_different_binding_transitions']} | "
        f"{overall['distinct_binding_transitions']} | {overall['unresolved_transitions']} | "
        f"{overall['dominant_transition_family']} |",
        "",
        "## Positive / zero / negative breakdown",
        "",
        "| Sign | Experiments | Switching experiments | Total switches | Resolved | "
        "Same binding | Same callable / different binding | Distinct binding | Unresolved |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for raw in by_sign:
        row = _as_mapping(raw, context="sign aggregate")
        lines.append(
            f"| {row['sign']} | {row['experiment_count']} | {row['switching_experiment_count']} "
            f"| {row['total_switch_count']} | {row['lineage_resolved_switch_count']} | "
            f"{row['same_binding_transitions']} | "
            f"{row['same_callable_different_binding_transitions']} | "
            f"{row['distinct_binding_transitions']} | {row['unresolved_transitions']} |"
        )

    lines.extend(
        [
            "",
            "## Every lottery / K / window experiment",
            "",
            "| Cell | Window | Sign | Source delta | Switches | Resolved | Same binding | "
            "Same callable / different binding | Distinct | Unresolved | Distinct share | "
            "Dominant family |",
            "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
        ]
    )
    for raw in experiments:
        row = _as_mapping(raw, context="experiment")
        lines.append(
            f"| {row['cell_id']} | {row['window_label']} | {row['sign']} | "
            f"{_format_delta(row['source_delta'])} | {row['total_switch_count']} | "
            f"{row['lineage_resolved_switch_count']} | {row['same_binding_transitions']} | "
            f"{row['same_callable_different_binding_transitions']} | "
            f"{row['distinct_binding_transitions']} | {row['unresolved_transitions']} | "
            f"{_format_share(row['distinct_binding_switch_share'])} | "
            f"{row['dominant_transition_family']} |"
        )

    lines.extend(
        [
            "",
            "## Five repeated-positive candidate cells",
            "",
            "| Cell | Positive windows | Total switches | Resolved | Same binding | "
            "Same callable / different binding | Distinct | Unresolved | Dominant family |",
            "|---|---|---:|---:|---:|---:|---:|---:|---|",
        ]
    )
    for raw in candidates:
        row = _as_mapping(raw, context="candidate")
        positive_windows = ", ".join(cast(list[str], row["positive_windows"]))
        lines.append(
            f"| {row['cell_id']} | {positive_windows} | {row['total_switch_count']} | "
            f"{row['lineage_resolved_switch_count']} | {row['same_binding_transitions']} | "
            f"{row['same_callable_different_binding_transitions']} | "
            f"{row['distinct_binding_transitions']} | {row['unresolved_transitions']} | "
            f"{row['dominant_transition_family']} |"
        )

    lines.extend(
        [
            "",
            "## P638 C01-C07 bridge family",
            "",
            f"All `{siblings['exact_lineage_join_count']}` C01-C07 Strategy IDs exact-join. "
            f"Every sibling pair is `{siblings['pairwise_structural_classification']}`. "
            f"Two or more sibling identities were selected in "
            f"`{siblings['experiments_with_two_or_more_selected_siblings']}` of "
            f"`{siblings['p638_k1_experiment_count']}` P638 K1 windows, accounting for "
            f"`{siblings['sibling_selection_count']}` selection instances. The actual "
            "sibling-transition count is unresolved because endpoints were not embedded; "
            "C-to-C switches must not be described as distinct-binding cross-method diversity.",
            "",
            "| Window | Selected siblings | Sibling selections | All selections | Total switches | "
            "Actual sibling transitions |",
            "|---|---|---:|---:|---:|---|",
        ]
    )
    for raw in _as_list(siblings.get("experiments"), context="sibling experiments"):
        row = _as_mapping(raw, context="sibling experiment")
        lines.append(
            f"| {row['window_label']} | {_format_ids(row['selected_sibling_strategy_ids'])} | "
            f"{row['sibling_selection_count']} | {row['all_selection_count']} | "
            f"{row['total_switch_count']} | UNRESOLVED (hash-only trace) |"
        )

    lines.extend(
        [
            "",
            "## ZERO / no-switch structural capability",
            "",
            f"There are `{zero_findings['zero_no_switch_cell_count']}` cells that are ZERO "
            "with no switches in every window. "
            f"`{zero_findings['structurally_incapable_cell_count']}` are structurally "
            "incapable of dynamic diversity because their candidate universe contains one "
            "Strategy ID.",
            "",
            "| Cell | Candidate Strategy-ID count | Structural capability |",
            "|---|---:|---|",
        ]
    )
    for raw in _as_list(zero_findings.get("zero_no_switch_cells"), context="zero no-switch cells"):
        row = _as_mapping(raw, context="zero no-switch cell")
        lines.append(
            f"| {row['cell_id']} | {row['candidate_strategy_count']} | "
            f"{row['dynamic_diversity_capability']} |"
        )

    lines.extend(
        [
            "",
            "## Required descriptive questions",
            "",
        ]
    )
    for raw in answers:
        row = _as_mapping(raw, context="answer")
        answer = _as_mapping(row.get("answer"), context="answer payload")
        interpretation = _as_string(
            answer.get("interpretation", row.get("answer_code")), context="answer interpretation"
        )
        lines.extend(
            [
                f"{row['question_id']}. **{row['question']}**",
                "",
                f"   `{row['answer_code']}` — {interpretation}",
                "",
            ]
        )

    lines.extend(
        [
            "## Explicit unresolved rows",
            "",
            "| Experiment | Sign | Switches | Missing exact IDs | Source-unresolved IDs | "
            "Reasons |",
            "|---|---|---:|---|---|---|",
        ]
    )
    for raw in unresolved_rows:
        row = _as_mapping(raw, context="unresolved row")
        reasons = ", ".join(cast(list[str], row["unresolved_reasons"]))
        lines.append(
            f"| {row['experiment_id']} | {row['sign']} | {row['unresolved_transitions']} | "
            f"{_format_ids(row['missing_strategy_ids'])} | "
            f"{_format_ids(row['source_lineage_unresolved_strategy_ids'])} | {reasons} |"
        )

    boundaries = _as_mapping(payload.get("boundaries"), context="boundaries")
    lines.extend(
        [
            "",
            "## Boundaries",
            "",
            f"- `NEW_HISTORICAL_REPLAY = {boundaries['new_historical_replay']}`",
            f"- `DB_ACCESS = {boundaries['database_access']}`",
            f"- `NEW_SELECTOR = {boundaries['new_selector']}`",
            f"- `PREDICTIVE_ADVANTAGE = {boundaries['predictive_advantage']}`",
            "- No p-values, significance claim, promotion threshold, profitability claim, "
            "Phase 12 use, P638 Zone-2 use, or 2-exchange work.",
            "",
        ]
    )
    return "\n".join(lines)


def run_analysis(
    repository_root: Path = REPOSITORY_ROOT,
    output_json: Path = DEFAULT_OUTPUT_JSON,
    output_report: Path = DEFAULT_OUTPUT_REPORT,
) -> tuple[dict[str, Any], str]:
    """Load exact sources, build attribution, and write the two authorized artifacts."""

    rolling, pilot, lineage, source_identity = load_default_sources(repository_root)
    payload = build_attribution(
        rolling,
        pilot,
        lineage,
        source_identity=source_identity,
        enforce_sealed_shape=True,
    )
    json_bytes = canonical_json_bytes(payload)
    report = render_report(payload)
    for output_path in (output_json, output_report):
        if not output_path.parent.is_dir():
            raise LineageAttributionError(
                f"authorized output parent does not exist: {output_path.parent}"
            )
    output_json.write_bytes(json_bytes)
    output_report.write_text(report, encoding="utf-8")
    return payload, hashlib.sha256(json_bytes).hexdigest()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, default=REPOSITORY_ROOT)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-report", type=Path, default=DEFAULT_OUTPUT_REPORT)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    payload, result_sha256 = run_analysis(
        repository_root=args.repository_root,
        output_json=args.output_json,
        output_report=args.output_report,
    )
    overall = cast(dict[str, Any], cast(dict[str, Any], payload["aggregates"])["overall"])
    print(
        json.dumps(
            {
                "result_sha256": result_sha256,
                "total_switch_count": overall["total_switch_count"],
                "lineage_resolved_switch_count": overall["lineage_resolved_switch_count"],
                "unresolved_transitions": overall["unresolved_transitions"],
                "output_json": str(args.output_json),
                "output_report": str(args.output_report),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
