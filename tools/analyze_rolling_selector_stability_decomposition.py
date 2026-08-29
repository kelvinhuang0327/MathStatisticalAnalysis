"""Decompose the sealed rolling-selector pilot result by sign and switching activity.

This tool is deliberately descriptive.  It reads one already-produced JSON result,
validates its seal, and attributes the recorded rolling-minus-frozen deltas without
opening replay authorities, executing strategies, or defining a future selector.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from fractions import Fraction
from pathlib import Path
from typing import Any, cast

TASK_ID = "ROLLING_SELECTOR_STABILITY_DECOMPOSITION_R1"
STUDY_ID = "ROLLING_SELECTOR_STABILITY_DECOMPOSITION_V1"
SCHEMA_VERSION = "ROLLING_SELECTOR_STABILITY_DECOMPOSITION_RESULT_V1"
SOURCE_TASK_ID = "STRATEGY_MATRIX_CAUSAL_ROLLING_SELECTOR_PILOT_R1"
SOURCE_SCHEMA_VERSION = "STRATEGY_MATRIX_CAUSAL_ROLLING_SELECTOR_PILOT_RESULT_V1"
SOURCE_RESULT_HEAD = "abc367bd6d8b59d01ecc4d79e56c787bbc03cd20"
SOURCE_RESULT_TREE = "bf430efd66b7ce1ac38ee04fb0052e8c55cc972c"
SOURCE_RESULT_SHA256 = "04df0bfdffcf4ecc05d4f2ac3f58cfa1fa301061c5f1c30e549ddc3b5b174157"
EXPECTED_CELL_COUNT = 22
EXPECTED_EXPERIMENT_COUNT = 66

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_RELATIVE_PATH = (
    "docs/research/matrix-native-results/"
    "strategy-matrix-causal-rolling-selector-pilot-r1-result.json"
)
DEFAULT_SOURCE_JSON = REPOSITORY_ROOT / SOURCE_RELATIVE_PATH
DEFAULT_OUTPUT_JSON = (
    REPOSITORY_ROOT
    / "docs/research/matrix-native-results/"
    "rolling-selector-stability-decomposition-r1-result.json"
)
DEFAULT_OUTPUT_REPORT = (
    REPOSITORY_ROOT / "docs/research/rolling-selector-stability-decomposition-r1.md"
)

WINDOWS: tuple[tuple[str, str, int], ...] = (
    ("W50", "SHORT", 50),
    ("W300", "MEDIUM", 300),
    ("W750", "LONG", 750),
)
CLASSIFICATIONS = ("POSITIVE", "ZERO", "NEGATIVE", "INCONCLUSIVE")
SWITCH_ACTIVITIES = ("SWITCHING_ACTIVE", "ZERO_SWITCH", "INCONCLUSIVE")


class DecompositionDataError(ValueError):
    """The sealed source result cannot support the required decomposition."""


def _require_regular_file(file_path: Path) -> None:
    if file_path.is_symlink() or not file_path.is_file():
        raise DecompositionDataError(f"source result is not a regular file: {file_path}")


def sha256_file(file_path: Path) -> str:
    """Return the SHA-256 of a regular file without loading other data sources."""

    _require_regular_file(file_path)
    digest = hashlib.sha256()
    with file_path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json_bytes(payload: Mapping[str, Any]) -> bytes:
    """Serialize JSON deterministically."""

    return (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def _as_mapping(value: object, *, context: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise DecompositionDataError(f"{context} must be an object")
    return cast(Mapping[str, Any], value)


def _as_list(value: object, *, context: str) -> list[Any]:
    if not isinstance(value, list):
        raise DecompositionDataError(f"{context} must be an array")
    return cast(list[Any], value)


def _as_nonnegative_int(value: object, *, context: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise DecompositionDataError(f"{context} must be a nonnegative integer")
    return value


def _as_string(value: object, *, context: str) -> str:
    if not isinstance(value, str) or not value:
        raise DecompositionDataError(f"{context} must be a nonempty string")
    return value


def load_source_result(
    source_path: Path,
    *,
    expected_sha256: str = SOURCE_RESULT_SHA256,
) -> tuple[dict[str, Any], str, int]:
    """Load only the named source result after enforcing its exact SHA-256 seal."""

    _require_regular_file(source_path)
    source_bytes = source_path.read_bytes()
    actual_sha256 = hashlib.sha256(source_bytes).hexdigest()
    if actual_sha256 != expected_sha256:
        raise DecompositionDataError(
            "SOURCE_RESULT_IDENTITY_DRIFT: "
            f"expected sha256={expected_sha256}, actual sha256={actual_sha256}"
        )
    try:
        value = json.loads(source_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DecompositionDataError("sealed source result is not valid UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise DecompositionDataError("sealed source result must be a JSON object")
    return cast(dict[str, Any], value), actual_sha256, len(source_bytes)


def _validated_fraction(delta: object, *, context: str) -> Fraction:
    payload = _as_mapping(delta, context=context)
    numerator_raw = payload.get("numerator")
    denominator_raw = payload.get("denominator")
    if isinstance(numerator_raw, bool) or not isinstance(numerator_raw, int):
        raise DecompositionDataError(f"{context}.numerator must be an integer")
    if isinstance(denominator_raw, bool) or not isinstance(denominator_raw, int):
        raise DecompositionDataError(f"{context}.denominator must be an integer")
    if denominator_raw <= 0:
        raise DecompositionDataError(f"{context}.denominator must be positive")
    exact = _as_string(payload.get("exact"), context=f"{context}.exact")
    value = Fraction(numerator_raw, denominator_raw)
    canonical_exact = f"{value.numerator}/{value.denominator}"
    try:
        exact_value = Fraction(exact)
    except (ValueError, ZeroDivisionError) as exc:
        raise DecompositionDataError(f"{context}.exact is not a valid fraction") from exc
    if exact_value != value or exact != canonical_exact:
        raise DecompositionDataError(
            f"{context} exact fraction mismatch: {exact!r} != {canonical_exact!r}"
        )
    return value


def classify_delta(experiment: Mapping[str, Any]) -> str:
    """Classify one source delta using only its exact rational representation."""

    status = _as_string(experiment.get("status"), context="experiment.status")
    delta = experiment.get("absolute_paired_delta")
    if status != "COMPLETE":
        if delta is not None:
            raise DecompositionDataError(
                "inconclusive source experiment unexpectedly contains an exact delta"
            )
        return "INCONCLUSIVE"
    if delta is None:
        raise DecompositionDataError("complete source experiment is missing its exact delta")
    value = _validated_fraction(delta, context="experiment.absolute_paired_delta")
    if value.numerator > 0:
        return "POSITIVE"
    if value.numerator < 0:
        return "NEGATIVE"
    return "ZERO"


def dominant_strategy_identities(frequencies: object, *, context: str) -> tuple[str, ...]:
    """Return every strategy tied for the greatest recorded selection count."""

    payload = _as_mapping(frequencies, context=context)
    validated: dict[str, int] = {}
    for strategy_id_raw, count_raw in payload.items():
        strategy_id = _as_string(strategy_id_raw, context=f"{context} strategy id")
        validated[strategy_id] = _as_nonnegative_int(
            count_raw, context=f"{context}[{strategy_id!r}]"
        )
    if not validated:
        return ()
    maximum = max(validated.values())
    return tuple(sorted(key for key, count in validated.items() if count == maximum))


def _copy_exact_delta(delta: object, *, context: str) -> dict[str, Any]:
    payload = _as_mapping(delta, context=context)
    value = _validated_fraction(payload, context=context)
    return {
        "denominator": value.denominator,
        "exact": f"{value.numerator}/{value.denominator}",
        "numerator": value.numerator,
    }


def _decompose_window(
    experiment: Mapping[str, Any],
    *,
    cell_id: str,
    output_label: str,
    source_label: str,
    expected_window: int,
) -> dict[str, Any]:
    context = f"{cell_id}.{source_label}"
    if experiment.get("label") != source_label:
        raise DecompositionDataError(f"{context}.label does not match its source key")
    if experiment.get("window") != expected_window:
        raise DecompositionDataError(
            f"{context}.window does not match expected value {expected_window}"
        )

    classification = classify_delta(experiment)
    switch_count = _as_nonnegative_int(
        experiment.get("rolling_strategy_switch_count"),
        context=f"{context}.rolling_strategy_switch_count",
    )
    available = classification != "INCONCLUSIVE"
    frequencies = _as_mapping(
        experiment.get("rolling_selection_frequency"),
        context=f"{context}.rolling_selection_frequency",
    )
    dominant_ids = dominant_strategy_identities(
        frequencies, context=f"{context}.rolling_selection_frequency"
    )

    delta: dict[str, Any] | None = None
    frozen_identity: str | None = None
    dominant_count: int | None = None
    selection_target_count = sum(
        _as_nonnegative_int(count, context=f"{context}.rolling_selection_frequency count")
        for count in frequencies.values()
    )
    if available:
        frozen_identity = _as_string(
            experiment.get("frozen_baseline_strategy"),
            context=f"{context}.frozen_baseline_strategy",
        )
        delta = _copy_exact_delta(
            experiment.get("absolute_paired_delta"),
            context=f"{context}.absolute_paired_delta",
        )
        if not dominant_ids:
            raise DecompositionDataError(f"{context} has no rolling selection frequencies")
        dominant_count = max(
            _as_nonnegative_int(count, context=f"{context} selection frequency")
            for count in frequencies.values()
        )
        rolling_metric = _as_mapping(
            experiment.get("rolling_selector_primary_metric_result"),
            context=f"{context}.rolling_selector_primary_metric_result",
        )
        target_count = _as_nonnegative_int(
            rolling_metric.get("target_count"), context=f"{context} target_count"
        )
        if selection_target_count != target_count:
            raise DecompositionDataError(
                f"{context} rolling frequency total {selection_target_count} "
                f"does not equal target count {target_count}"
            )
    elif dominant_ids or selection_target_count != 0:
        raise DecompositionDataError(f"{context} is inconclusive but has rolling selections")

    if not available:
        switch_activity = "INCONCLUSIVE"
    elif switch_count > 0:
        switch_activity = "SWITCHING_ACTIVE"
    else:
        switch_activity = "ZERO_SWITCH"

    zero_with_zero_switch = switch_count == 0 if classification == "ZERO" else None

    dominant = [
        {"selection_count": dominant_count, "strategy_id": strategy_id}
        for strategy_id in dominant_ids
    ]
    return {
        "available": available,
        "classification": classification,
        "dominant_rolling_selected_strategy_identities": dominant,
        "frozen_strategy_identity": frozen_identity,
        "rolling_minus_frozen_exact_delta": delta,
        "rolling_selection_target_count": selection_target_count,
        "source_conclusion": experiment.get("conclusion"),
        "source_label": source_label,
        "source_status": experiment.get("status"),
        "switch_activity": switch_activity,
        "switch_count": switch_count,
        "window": expected_window,
        "window_label": output_label,
        "zero_result_accompanied_by_switch_count_zero": zero_with_zero_switch,
    }


def _reversal_pairs(windows: Sequence[Mapping[str, Any]]) -> list[dict[str, str]]:
    pairs: list[dict[str, str]] = []
    for left_index, left in enumerate(windows):
        left_class = cast(str, left["classification"])
        for right in windows[left_index + 1 :]:
            right_class = cast(str, right["classification"])
            if {left_class, right_class} == {"POSITIVE", "NEGATIVE"}:
                pairs.append(
                    {
                        "from_classification": left_class,
                        "from_window": cast(str, left["window_label"]),
                        "to_classification": right_class,
                        "to_window": cast(str, right["window_label"]),
                    }
                )
    return pairs


def decompose_cell(raw_cell: Mapping[str, Any]) -> dict[str, Any]:
    """Build the required three-window decomposition for one lottery/K cell."""

    cell_id = _as_string(raw_cell.get("cell_id"), context="cell.cell_id")
    lottery_id = _as_string(raw_cell.get("lottery_id"), context=f"{cell_id}.lottery_id")
    k = _as_nonnegative_int(
        raw_cell.get("native_ticket_count"), context=f"{cell_id}.native_ticket_count"
    )
    if k == 0 or cell_id != f"{lottery_id}:K{k}":
        raise DecompositionDataError(f"{cell_id} does not match lottery/K identity")
    experiments = _as_mapping(raw_cell.get("experiments"), context=f"{cell_id}.experiments")
    expected_source_labels = {source_label for _, source_label, _ in WINDOWS}
    if set(experiments) != expected_source_labels:
        raise DecompositionDataError(
            f"{cell_id} experiment keys must be {sorted(expected_source_labels)}"
        )

    windows = [
        _decompose_window(
            _as_mapping(experiments[source_label], context=f"{cell_id}.{source_label}"),
            cell_id=cell_id,
            output_label=output_label,
            source_label=source_label,
            expected_window=window,
        )
        for output_label, source_label, window in WINDOWS
    ]
    available = [window for window in windows if cast(bool, window["available"])]
    classifications = [cast(str, window["classification"]) for window in available]
    positive_count = classifications.count("POSITIVE")
    reversal_pairs = _reversal_pairs(windows)

    dominant_sets = [
        tuple(
            cast(str, item["strategy_id"])
            for item in cast(
                list[dict[str, Any]],
                window["dominant_rolling_selected_strategy_identities"],
            )
        )
        for window in available
    ]
    if len(dominant_sets) < 2:
        material_change = "INCONCLUSIVE_FEWER_THAN_TWO_AVAILABLE_WINDOWS"
    elif all(strategy_ids == dominant_sets[0] for strategy_ids in dominant_sets[1:]):
        material_change = "NO_DOMINANT_IDENTITY_STABLE"
    else:
        material_change = "YES_DOMINANT_IDENTITY_CHANGED"

    active_window_count = sum(
        cast(str, window["switch_activity"]) == "SWITCHING_ACTIVE" for window in available
    )
    if not available:
        switch_profile = "NO_AVAILABLE_WINDOWS"
    elif active_window_count:
        switch_profile = "SWITCHING_ACTIVE_IN_AT_LEAST_ONE_AVAILABLE_WINDOW"
    else:
        switch_profile = "ZERO_SWITCH_ACROSS_ALL_AVAILABLE_WINDOWS"

    return {
        "available_window_count": len(available),
        "cell_id": cell_id,
        "dominant_identity_materially_changes_with_window": material_change,
        "k": k,
        "lottery_id": lottery_id,
        "positive_classification_count": positive_count,
        "positive_repeats_across_two_or_more_available_windows": positive_count >= 2,
        "sign_pattern": {
            cast(str, window["window_label"]): cast(str, window["classification"])
            for window in windows
        },
        "sign_pattern_ordered": " / ".join(
            f"{window['window_label']}={window['classification']}" for window in windows
        ),
        "sign_reversal": bool(reversal_pairs),
        "sign_reversal_pairs": reversal_pairs,
        "switch_activity_profile": switch_profile,
        "switching_active_window_count": active_window_count,
        "windows": windows,
    }


def _classification_counts(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts = Counter(cast(str, row["classification"]) for row in rows)
    return {classification: counts[classification] for classification in CLASSIFICATIONS}


def _switch_activity_counts(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts = Counter(cast(str, row["switch_activity"]) for row in rows)
    return {activity: counts[activity] for activity in SWITCH_ACTIVITIES}


def _aggregate_rows(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    available = [row for row in rows if cast(bool, row["available"])]
    zero_rows = [row for row in available if row["classification"] == "ZERO"]
    switch_counts = [cast(int, row["switch_count"]) for row in available]
    return {
        "available_experiment_count": len(available),
        "classification_counts": _classification_counts(rows),
        "experiment_count": len(rows),
        "maximum_switch_count": max(switch_counts) if switch_counts else None,
        "switch_activity_counts": _switch_activity_counts(rows),
        "zero_result_count": len(zero_rows),
        "zero_with_nonzero_switch_count": sum(
            cast(int, row["switch_count"]) > 0 for row in zero_rows
        ),
        "zero_with_zero_switch_count": sum(
            cast(int, row["switch_count"]) == 0 for row in zero_rows
        ),
    }


def _all_window_rows(cells: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for cell in cells:
        for raw_window in cast(list[dict[str, Any]], cell["windows"]):
            rows.append(
                {
                    **raw_window,
                    "cell_id": cell["cell_id"],
                    "k": cell["k"],
                    "lottery_id": cell["lottery_id"],
                }
            )
    return rows


def _grouped_aggregates(
    rows: Sequence[Mapping[str, Any]],
    *,
    key_name: str,
) -> list[dict[str, Any]]:
    grouped: defaultdict[object, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row[key_name]].append(row)
    output: list[dict[str, Any]] = []
    for key in sorted(grouped, key=lambda item: (isinstance(item, str), item)):
        group_rows = grouped[key]
        output.append(
            {
                key_name: key,
                "cell_count": len({cast(str, row["cell_id"]) for row in group_rows}),
                **_aggregate_rows(group_rows),
            }
        )
    return output


def _row_reference(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "cell_id": row["cell_id"],
        "classification": row["classification"],
        "rolling_minus_frozen_exact_delta": row["rolling_minus_frozen_exact_delta"],
        "switch_count": row["switch_count"],
        "window_label": row["window_label"],
    }


def _diagnostics(
    cells: Sequence[Mapping[str, Any]], rows: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    available = [row for row in rows if cast(bool, row["available"])]
    zero_rows = [row for row in available if row["classification"] == "ZERO"]
    active_rows = [row for row in available if row["switch_activity"] == "SWITCHING_ACTIVE"]
    repeated_positive_cells = [
        cell
        for cell in cells
        if cast(bool, cell["positive_repeats_across_two_or_more_available_windows"])
    ]
    reversal_cells = [cell for cell in cells if cast(bool, cell["sign_reversal"])]

    positive_by_k: list[dict[str, int]] = []
    for aggregate in _grouped_aggregates(rows, key_name="k"):
        classifications = cast(dict[str, int], aggregate["classification_counts"])
        positive_by_k.append(
            {
                "available_experiment_count": cast(int, aggregate["available_experiment_count"]),
                "k": cast(int, aggregate["k"]),
                "positive_count": classifications["POSITIVE"],
            }
        )
    positive_total = sum(item["positive_count"] for item in positive_by_k)
    positive_k1_to_k3 = sum(
        item["positive_count"] for item in positive_by_k if item["k"] <= 3
    )
    max_positive = max((item["positive_count"] for item in positive_by_k), default=0)

    ranked_active = sorted(
        active_rows,
        key=lambda row: (
            -cast(int, row["switch_count"]),
            cast(str, row["cell_id"]),
            cast(int, row["window"]),
        ),
    )
    global_max = cast(int, ranked_active[0]["switch_count"]) if ranked_active else None
    at_global_max = (
        [_row_reference(row) for row in ranked_active if row["switch_count"] == global_max]
        if global_max is not None
        else []
    )
    three_largest = [_row_reference(row) for row in ranked_active[:3]]
    top_three_signs = {cast(str, row["classification"]) for row in ranked_active[:3]}
    if len(top_three_signs) > 1:
        extreme_outcome_description = "MIXED_AMONG_THREE_LARGEST_EXPERIMENTS"
    elif top_three_signs:
        extreme_outcome_description = f"{next(iter(top_three_signs))}_ONLY"
    else:
        extreme_outcome_description = "INCONCLUSIVE_NO_SWITCHING_ACTIVE_EXPERIMENTS"

    per_window_maxima: list[dict[str, Any]] = []
    for output_label, _, _ in WINDOWS:
        window_rows = [row for row in active_rows if row["window_label"] == output_label]
        maximum = max((cast(int, row["switch_count"]) for row in window_rows), default=None)
        per_window_maxima.append(
            {
                "experiments": (
                    [_row_reference(row) for row in window_rows if row["switch_count"] == maximum]
                    if maximum is not None
                    else []
                ),
                "maximum_switch_count": maximum,
                "window_label": output_label,
            }
        )

    candidates: list[dict[str, Any]] = []
    for cell in repeated_positive_cells:
        positive_windows: list[dict[str, Any]] = [
            window
            for window in cast(list[dict[str, Any]], cell["windows"])
            if window["classification"] == "POSITIVE"
        ]
        if positive_windows and all(
            window["switch_activity"] == "SWITCHING_ACTIVE" for window in positive_windows
        ):
            candidates.append(
                {
                    "basis": (
                        "POSITIVE_IN_AT_LEAST_TWO_AVAILABLE_WINDOWS_WITH_SWITCHING_ACTIVE_"
                        "POSITIVE_WINDOWS"
                    ),
                    "cell_id": cell["cell_id"],
                    "positive_windows": [window["window_label"] for window in positive_windows],
                    "sign_pattern": cell["sign_pattern"],
                    "sign_reversal": cell["sign_reversal"],
                }
            )

    return [
        {
            "answer": {
                "zero_experiment_count": len(zero_rows),
                "zero_with_nonzero_switch_count": sum(
                    cast(int, row["switch_count"]) > 0 for row in zero_rows
                ),
                "zero_with_zero_switch_count": sum(
                    cast(int, row["switch_count"]) == 0 for row in zero_rows
                ),
                "zero_with_nonzero_switch_experiments": [
                    _row_reference(row)
                    for row in zero_rows
                    if cast(int, row["switch_count"]) > 0
                ],
            },
            "question": "How many ZERO experiments are trivially zero because switch_count=0?",
            "question_id": 1,
        },
        {
            "answer": {
                "classification_counts": _classification_counts(active_rows),
                "switching_active_experiment_count": len(active_rows),
            },
            "question": (
                "Among switching-active experiments only, how many are positive, negative, or zero?"
            ),
            "question_id": 2,
        },
        {
            "answer": {
                "cell_count": len(repeated_positive_cells),
                "cells": [
                    {
                        "cell_id": cell["cell_id"],
                        "positive_windows": [
                            window["window_label"]
                            for window in cast(list[dict[str, Any]], cell["windows"])
                            if window["classification"] == "POSITIVE"
                        ],
                        "sign_pattern": cell["sign_pattern"],
                    }
                    for cell in repeated_positive_cells
                ],
            },
            "question": "Which cells show positive delta in at least two available windows?",
            "question_id": 3,
        },
        {
            "answer": {
                "cell_count": len(reversal_cells),
                "cells": [
                    {
                        "cell_id": cell["cell_id"],
                        "reversal_pairs": cell["sign_reversal_pairs"],
                        "sign_pattern": cell["sign_pattern"],
                    }
                    for cell in reversal_cells
                ],
            },
            "question": "Which cells reverse sign between short, medium, and long windows?",
            "question_id": 4,
        },
        {
            "answer": {
                "k_at_maximum_positive_count": [
                    item["k"] for item in positive_by_k if item["positive_count"] == max_positive
                ],
                "k1_to_k3_positive_count": positive_k1_to_k3,
                "positive_count_by_k": positive_by_k,
                "positive_experiment_count": positive_total,
            },
            "question": "Are positive effects concentrated in particular K ranges?",
            "question_id": 5,
        },
        {
            "answer": {
                "experiments_at_global_maximum": at_global_max,
                "global_maximum_switch_count": global_max,
                "outcome_description": extreme_outcome_description,
                "per_window_maxima": per_window_maxima,
                "three_largest_experiments": three_largest,
            },
            "question": (
                "Are the largest switching frequencies associated descriptively with better, "
                "worse, or mixed outcomes?"
            ),
            "question_id": 6,
        },
        {
            "answer": {
                "candidate_count": len(candidates),
                "candidates": candidates,
                "scope": (
                    "DESCRIPTIVE_CANDIDATE_IDENTIFICATION_ONLY; NO_FUTURE_SELECTOR_OR_"
                    "PROMOTION_THRESHOLD_DEFINED"
                ),
            },
            "question": (
                "Which cells are reasonable candidates for a separately preregistered future "
                "selector experiment?"
            ),
            "question_id": 7,
        },
    ]


def _validate_source_contract(source: Mapping[str, Any], *, enforce_sealed_shape: bool) -> None:
    windows = _as_mapping(source.get("windows"), context="source.windows")
    expected_windows = {source_label: window for _, source_label, window in WINDOWS}
    if dict(windows) != expected_windows:
        raise DecompositionDataError(
            f"source windows do not match required windows: {dict(windows)!r}"
        )
    if enforce_sealed_shape:
        if source.get("task_id") != SOURCE_TASK_ID:
            raise DecompositionDataError("sealed source task identity is unexpected")
        if source.get("schema_version") != SOURCE_SCHEMA_VERSION:
            raise DecompositionDataError("sealed source schema version is unexpected")


def build_decomposition(
    source: Mapping[str, Any],
    *,
    source_sha256: str = SOURCE_RESULT_SHA256,
    source_size_bytes: int | None = None,
    enforce_sealed_shape: bool = True,
) -> dict[str, Any]:
    """Build the deterministic decomposition from the already-loaded source object."""

    _validate_source_contract(source, enforce_sealed_shape=enforce_sealed_shape)
    raw_cells = _as_list(source.get("cells"), context="source.cells")
    cells = [decompose_cell(_as_mapping(cell, context="source.cells[]")) for cell in raw_cells]
    cells.sort(key=lambda cell: (cast(str, cell["lottery_id"]), cast(int, cell["k"])))
    cell_ids = [cast(str, cell["cell_id"]) for cell in cells]
    if len(cell_ids) != len(set(cell_ids)):
        raise DecompositionDataError("source contains duplicate lottery/K cell identities")

    rows = _all_window_rows(cells)
    if enforce_sealed_shape:
        if len(cells) != EXPECTED_CELL_COUNT:
            raise DecompositionDataError(
                f"sealed source cell count {len(cells)} != {EXPECTED_CELL_COUNT}"
            )
        if len(rows) != EXPECTED_EXPERIMENT_COUNT:
            raise DecompositionDataError(
                f"sealed source experiment count {len(rows)} != {EXPECTED_EXPERIMENT_COUNT}"
            )

    status_counts = Counter(cast(str, row["source_status"]) for row in rows)
    overall = {
        "cell_count": len(cells),
        **_aggregate_rows(rows),
    }
    cell_profile_counts = Counter(cast(str, cell["switch_activity_profile"]) for cell in cells)
    by_switch_activity: list[dict[str, Any]] = []
    for activity in SWITCH_ACTIVITIES:
        activity_rows = [row for row in rows if row["switch_activity"] == activity]
        by_switch_activity.append(
            {
                "switch_activity": activity,
                **_aggregate_rows(activity_rows),
            }
        )
    cell_profiles = (
        "SWITCHING_ACTIVE_IN_AT_LEAST_ONE_AVAILABLE_WINDOW",
        "ZERO_SWITCH_ACROSS_ALL_AVAILABLE_WINDOWS",
        "NO_AVAILABLE_WINDOWS",
    )
    by_cell_switch_activity_profile: list[dict[str, Any]] = []
    for profile in cell_profiles:
        profile_cells = [cell for cell in cells if cell["switch_activity_profile"] == profile]
        profile_rows = _all_window_rows(profile_cells)
        by_cell_switch_activity_profile.append(
            {
                "dominant_identity_change_cell_count": sum(
                    cell["dominant_identity_materially_changes_with_window"]
                    == "YES_DOMINANT_IDENTITY_CHANGED"
                    for cell in profile_cells
                ),
                "positive_repeating_cell_count": sum(
                    cast(bool, cell["positive_repeats_across_two_or_more_available_windows"])
                    for cell in profile_cells
                ),
                "sign_reversal_cell_count": sum(
                    cast(bool, cell["sign_reversal"]) for cell in profile_cells
                ),
                "switch_activity_profile": profile,
                **_aggregate_rows(profile_rows),
                "cell_count": len(profile_cells),
            }
        )

    return {
        "aggregates": {
            "by_cell_switch_activity_profile": by_cell_switch_activity_profile,
            "by_k": _grouped_aggregates(rows, key_name="k"),
            "by_lottery": _grouped_aggregates(rows, key_name="lottery_id"),
            "by_switch_activity": by_switch_activity,
            "by_window": _grouped_aggregates(rows, key_name="window"),
            "cell_switch_activity_profiles": {
                key: cell_profile_counts[key] for key in cell_profiles
            },
            "overall": overall,
        },
        "boundaries": {
            "composite_score": "NOT_CREATED",
            "database_access": "NO",
            "future_selector_definition": "NOT_CREATED",
            "new_historical_replay": "NOT_RUN",
            "new_selector": "NOT_IMPLEMENTED",
            "parameter_optimization": "NOT_RUN",
            "phase12_dependency": "NONE",
            "predictive_advantage": "NOT_ESTABLISHED",
            "profitability": "NOT_ESTABLISHED",
            "promotion_threshold": "NOT_CREATED",
            "statistical_significance": "NOT_CLAIMED",
            "strategy_execution": "NOT_RUN",
        },
        "cells": cells,
        "definitions": {
            "availability": (
                "A window is available only when the source experiment status is COMPLETE "
                "and its exact delta is present and valid."
            ),
            "classification": {
                "INCONCLUSIVE": "Source experiment is unavailable; no delta sign is inferred.",
                "NEGATIVE": "Exact rolling-minus-frozen delta numerator is less than zero.",
                "POSITIVE": "Exact rolling-minus-frozen delta numerator is greater than zero.",
                "ZERO": "Exact rolling-minus-frozen delta numerator equals zero.",
            },
            "dominant_strategy_identity": (
                "Every rolling-selected strategy tied for the greatest exact selection count."
            ),
            "material_window_change": (
                "YES only when the dominant strategy identity set differs across two or more "
                "available windows; no numeric threshold is used."
            ),
            "repeated_positive": "POSITIVE in at least two available windows.",
            "sign_reversal": (
                "At least one available-window pair contains one POSITIVE and one NEGATIVE sign."
            ),
            "switching_active": "Available experiment with switch_count greater than zero.",
            "window_order": [output_label for output_label, _, _ in WINDOWS],
            "zero_switch": "Available experiment with switch_count equal to zero.",
        },
        "diagnostic_answers": _diagnostics(cells, rows),
        "independence": {
            "input_files_read_by_analyzer": [SOURCE_RELATIVE_PATH],
            "phase12_paths_read": "NONE",
            "source_report_read_by_analyzer": "NO",
        },
        "schema_version": SCHEMA_VERSION,
        "source_data_quality": {
            "complete_experiment_count": status_counts["COMPLETE"],
            "duplicate_cell_id_count": len(cell_ids) - len(set(cell_ids)),
            "exact_rational_delta_count_validated": sum(
                cast(bool, row["available"]) for row in rows
            ),
            "excluded_experiment_count": len(rows) - status_counts["COMPLETE"],
            "experiment_count": len(rows),
            "inconclusive_experiment_count": sum(
                row["classification"] == "INCONCLUSIVE" for row in rows
            ),
            "negative_switch_count_rows": sum(cast(int, row["switch_count"]) < 0 for row in rows),
            "sign_classification_uses_decimal_field": False,
            "unexpected_window_count": 0,
        },
        "source_identity": {
            "result_head": SOURCE_RESULT_HEAD,
            "result_path": SOURCE_RELATIVE_PATH,
            "result_sha256": source_sha256,
            "result_size_bytes": source_size_bytes,
            "result_tree": SOURCE_RESULT_TREE,
            "source_schema_version": source.get("schema_version"),
            "source_study_id": source.get("study_id"),
            "source_task_id": source.get("task_id"),
        },
        "study_id": STUDY_ID,
        "task_id": TASK_ID,
    }


def _format_classification_counts(counts: Mapping[str, Any]) -> str:
    return ", ".join(f"{label}={counts[label]}" for label in CLASSIFICATIONS)


def _format_delta(delta: object) -> str:
    if delta is None:
        return "—"
    return cast(str, _as_mapping(delta, context="report delta")["exact"])


def _format_dominant(window: Mapping[str, Any]) -> str:
    dominant = cast(list[dict[str, Any]], window["dominant_rolling_selected_strategy_identities"])
    if not dominant:
        return "—"
    return ", ".join(
        f"{item['strategy_id']} ({item['selection_count']})" for item in dominant
    )


def render_report(payload: Mapping[str, Any]) -> str:
    """Render a deterministic human-readable report from the result payload."""

    source = _as_mapping(payload["source_identity"], context="payload.source_identity")
    aggregates = _as_mapping(payload["aggregates"], context="payload.aggregates")
    overall = _as_mapping(aggregates["overall"], context="payload.aggregates.overall")
    cells = cast(list[dict[str, Any]], payload["cells"])
    diagnostics = cast(list[dict[str, Any]], payload["diagnostic_answers"])

    lines = [
        "# Rolling selector stability decomposition R1",
        "",
        "This is descriptive attribution of one already-completed historical experiment. "
        "It does not rerun a strategy, alter the selector, optimize a window, or make a "
        "future-performance claim.",
        "",
        "## Sealed source and accounting",
        "",
        f"- Source path: `{source['result_path']}`",
        f"- Source HEAD: `{source['result_head']}`",
        f"- Source tree: `{source['result_tree']}`",
        f"- Source SHA-256: `{source['result_sha256']}`",
        f"- Cells accounted for: {overall['cell_count']}",
        f"- Experiments accounted for: {overall['experiment_count']}",
        f"- Available experiments: {overall['available_experiment_count']}",
        "- Sign classification uses the exact numerator/denominator only; `decimal_12` is "
        "not used.",
        "",
        "## Definitions",
        "",
        "- POSITIVE/ZERO/NEGATIVE follow the sign of the exact rolling-minus-frozen rational "
        "delta.",
        "- INCONCLUSIVE means the source window is unavailable; no sign is inferred.",
        "- Repeated positive means POSITIVE in at least two available windows.",
        "- Sign reversal means an available-window pair contains one POSITIVE and one NEGATIVE.",
        "- A material selected-strategy change means the exact dominant strategy identity set "
        "changes across available windows. No magnitude threshold is used.",
        "",
        "## Complete experiment decomposition",
        "",
        "| Cell | K | Window | Class | Available | Exact delta | Switches | Switch group | "
        "ZERO with switches=0 | Frozen strategy | Dominant rolling strategy (count) |",
        "|---|---:|---|---|---|---:|---:|---|---|---|---|",
    ]
    for cell in cells:
        for window in cast(list[dict[str, Any]], cell["windows"]):
            zero_switch = window["zero_result_accompanied_by_switch_count_zero"]
            zero_switch_display = "N/A" if zero_switch is None else ("YES" if zero_switch else "NO")
            lines.append(
                "| {cell} | {k} | {window} | {classification} | {available} | {delta} | "
                "{switches} | {activity} | {zero_switch} | {frozen} | {dominant} |".format(
                    cell=cell["cell_id"],
                    k=cell["k"],
                    window=window["window_label"],
                    classification=window["classification"],
                    available="YES" if window["available"] else "NO",
                    delta=_format_delta(window["rolling_minus_frozen_exact_delta"]),
                    switches=window["switch_count"],
                    activity=window["switch_activity"],
                    zero_switch=zero_switch_display,
                    frozen=window["frozen_strategy_identity"] or "—",
                    dominant=_format_dominant(window),
                )
            )

    lines.extend(
        [
            "",
            "## Cross-window cell patterns",
            "",
            "| Cell | Available | W50 / W300 / W750 | Repeated positive | Reversal | "
            "Switch-active windows | Dominant identity change |",
            "|---|---:|---|---|---|---:|---|",
        ]
    )
    for cell in cells:
        lines.append(
            "| {cell} | {available} | {pattern} | {repeat} | {reversal} | {active} | "
            "{change} |".format(
                cell=cell["cell_id"],
                available=cell["available_window_count"],
                pattern=cell["sign_pattern_ordered"],
                repeat=(
                    "YES"
                    if cell["positive_repeats_across_two_or_more_available_windows"]
                    else "NO"
                ),
                reversal="YES" if cell["sign_reversal"] else "NO",
                active=cell["switching_active_window_count"],
                change=cell["dominant_identity_materially_changes_with_window"],
            )
        )

    lines.extend(["", "## Descriptive aggregates", "", "### By lottery", ""])
    lines.extend(
        [
            "| Lottery | Cells | Experiments | Available | Sign counts | Active / zero-switch / "
            "inconclusive |",
            "|---|---:|---:|---:|---|---|",
        ]
    )
    for aggregate in cast(list[dict[str, Any]], aggregates["by_lottery"]):
        switch_counts = cast(dict[str, int], aggregate["switch_activity_counts"])
        classification_counts = cast(dict[str, Any], aggregate["classification_counts"])
        lines.append(
            f"| {aggregate['lottery_id']} | {aggregate['cell_count']} | "
            f"{aggregate['experiment_count']} | {aggregate['available_experiment_count']} | "
            f"{_format_classification_counts(classification_counts)} | "
            f"{switch_counts['SWITCHING_ACTIVE']} / {switch_counts['ZERO_SWITCH']} / "
            f"{switch_counts['INCONCLUSIVE']} |"
        )

    lines.extend(["", "### By K", ""])
    lines.extend(
        [
            "| K | Cells | Experiments | Available | Sign counts | Maximum switches |",
            "|---:|---:|---:|---:|---|---:|",
        ]
    )
    for aggregate in cast(list[dict[str, Any]], aggregates["by_k"]):
        classification_counts = cast(dict[str, Any], aggregate["classification_counts"])
        maximum_switches = aggregate["maximum_switch_count"]
        lines.append(
            f"| {aggregate['k']} | {aggregate['cell_count']} | {aggregate['experiment_count']} | "
            f"{aggregate['available_experiment_count']} | "
            f"{_format_classification_counts(classification_counts)} | "
            f"{maximum_switches if maximum_switches is not None else '—'} |"
        )

    lines.extend(["", "### By window", ""])
    lines.extend(
        [
            "| Window | Experiments | Available | Sign counts | Maximum switches |",
            "|---:|---:|---:|---|---:|",
        ]
    )
    window_label_by_value = {window: output for output, _, window in WINDOWS}
    for aggregate in cast(list[dict[str, Any]], aggregates["by_window"]):
        classification_counts = cast(dict[str, Any], aggregate["classification_counts"])
        maximum_switches = aggregate["maximum_switch_count"]
        lines.append(
            f"| {window_label_by_value[cast(int, aggregate['window'])]} | "
            f"{aggregate['experiment_count']} | {aggregate['available_experiment_count']} | "
            f"{_format_classification_counts(classification_counts)} | "
            f"{maximum_switches if maximum_switches is not None else '—'} |"
        )

    lines.extend(["", "### By switch activity", ""])
    lines.extend(
        [
            "| Group | Experiments | Available | Sign counts |",
            "|---|---:|---:|---|",
        ]
    )
    for aggregate in cast(list[dict[str, Any]], aggregates["by_switch_activity"]):
        classification_counts = cast(dict[str, Any], aggregate["classification_counts"])
        lines.append(
            f"| {aggregate['switch_activity']} | {aggregate['experiment_count']} | "
            f"{aggregate['available_experiment_count']} | "
            f"{_format_classification_counts(classification_counts)} |"
        )
    lines.extend(["", "### By cell switching profile", ""])
    lines.extend(
        [
            "| Cell profile | Cells | Available experiments | Sign counts | Repeated-positive "
            "cells | Reversal cells |",
            "|---|---:|---:|---|---:|---:|",
        ]
    )
    for aggregate in cast(
        list[dict[str, Any]], aggregates["by_cell_switch_activity_profile"]
    ):
        classification_counts = cast(dict[str, Any], aggregate["classification_counts"])
        lines.append(
            f"| {aggregate['switch_activity_profile']} | {aggregate['cell_count']} | "
            f"{aggregate['available_experiment_count']} | "
            f"{_format_classification_counts(classification_counts)} | "
            f"{aggregate['positive_repeating_cell_count']} | "
            f"{aggregate['sign_reversal_cell_count']} |"
        )
    profile_counts = cast(dict[str, int], aggregates["cell_switch_activity_profiles"])
    lines.extend(
        [
            "",
            "Cell profiles: "
            f"switching-active in at least one available window="
            f"{profile_counts['SWITCHING_ACTIVE_IN_AT_LEAST_ONE_AVAILABLE_WINDOW']}; "
            f"zero-switch across all available windows="
            f"{profile_counts['ZERO_SWITCH_ACROSS_ALL_AVAILABLE_WINDOWS']}; "
            f"no available windows={profile_counts['NO_AVAILABLE_WINDOWS']}.",
            "",
            "## Required diagnostic answers",
            "",
        ]
    )

    q1 = cast(dict[str, Any], diagnostics[0]["answer"])
    lines.extend(
        [
            "1. **ZERO experiments with switch_count=0.** "
            f"{q1['zero_with_zero_switch_count']} of {q1['zero_experiment_count']} ZERO "
            "experiments are zero-switch matches; "
            f"{q1['zero_with_nonzero_switch_count']} ZERO experiment is switching-active.",
            "",
        ]
    )
    q2 = cast(dict[str, Any], diagnostics[1]["answer"])
    q2_counts = cast(dict[str, int], q2["classification_counts"])
    lines.extend(
        [
            "2. **Switching-active experiments only.** "
            f"{q2['switching_active_experiment_count']} total: "
            f"POSITIVE={q2_counts['POSITIVE']}, NEGATIVE={q2_counts['NEGATIVE']}, "
            f"ZERO={q2_counts['ZERO']}.",
            "",
        ]
    )
    q3 = cast(dict[str, Any], diagnostics[2]["answer"])
    q3_cells = cast(list[dict[str, Any]], q3["cells"])
    lines.append(
        "3. **Positive in at least two available windows.** "
        + (", ".join(cast(str, cell["cell_id"]) for cell in q3_cells) if q3_cells else "None")
        + "."
    )
    lines.append("")
    q4 = cast(dict[str, Any], diagnostics[3]["answer"])
    q4_cells = cast(list[dict[str, Any]], q4["cells"])
    lines.append(
        "4. **Sign reversals.** "
        + (", ".join(cast(str, cell["cell_id"]) for cell in q4_cells) if q4_cells else "None")
        + "."
    )
    lines.append("")
    q5 = cast(dict[str, Any], diagnostics[4]["answer"])
    positive_by_k = cast(list[dict[str, int]], q5["positive_count_by_k"])
    lines.append(
        "5. **K concentration.** "
        f"K1-K3 contain {q5['k1_to_k3_positive_count']} of "
        f"{q5['positive_experiment_count']} positive experiments. Full counts: "
        + ", ".join(f"K{item['k']}={item['positive_count']}" for item in positive_by_k)
        + "."
    )
    lines.append("")
    q6 = cast(dict[str, Any], diagnostics[5]["answer"])
    top_three = cast(list[dict[str, Any]], q6["three_largest_experiments"])
    top_three_text = ", ".join(
        f"{row['cell_id']} {row['window_label']}={row['switch_count']} "
        f"({row['classification']})" for row in top_three
    )
    lines.append(
        "6. **Largest switching frequencies.** "
        f"{q6['outcome_description']}. The three largest observed experiments are "
        f"{top_three_text or 'none'}. The global maximum is {q6['global_maximum_switch_count']}."
    )
    lines.append("")
    q7 = cast(dict[str, Any], diagnostics[6]["answer"])
    candidates = cast(list[dict[str, Any]], q7["candidates"])
    candidate_text = (
        ", ".join(cast(str, candidate["cell_id"]) for candidate in candidates)
        if candidates
        else "None"
    )
    lines.append(
        "7. **Descriptive candidates for a separately preregistered experiment.** "
        + candidate_text
        + ". These are identified only because positive signs repeat in at least two available, "
        "switching-active windows. This is not a promotion rule, and no future selector is "
        "defined here."
    )

    lines.extend(
        [
            "",
            "## Interpretation boundary",
            "",
            "Every repeat-positive candidate also retains its full cross-window sign pattern "
            "above; a repeated historical sign is not evidence of future predictive advantage.",
            "",
            "```text",
            "NEW_HISTORICAL_REPLAY = NOT RUN",
            "DB_ACCESS = NO",
            "NEW_SELECTOR = NOT IMPLEMENTED",
            "PHASE12_DEPENDENCY = NONE",
            "PREDICTIVE_ADVANTAGE = NOT ESTABLISHED",
            "PROFITABILITY = NOT ESTABLISHED",
            "COMPOSITE_SCORE = NOT CREATED",
            "PROMOTION_THRESHOLD = NOT CREATED",
            "STATISTICAL_SIGNIFICANCE = NOT CLAIMED",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def run_analysis(
    source_path: Path = DEFAULT_SOURCE_JSON,
) -> tuple[dict[str, Any], bytes, bytes]:
    """Validate the seal and return payload, JSON bytes, and report bytes in memory."""

    source, source_sha256, source_size = load_source_result(source_path)
    payload = build_decomposition(
        source,
        source_sha256=source_sha256,
        source_size_bytes=source_size,
        enforce_sealed_shape=True,
    )
    json_bytes = canonical_json_bytes(payload)
    report_bytes = render_report(payload).encode("utf-8")
    return payload, json_bytes, report_bytes


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-json", type=Path, default=DEFAULT_SOURCE_JSON)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-report", type=Path, default=DEFAULT_OUTPUT_REPORT)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    source_path = cast(Path, arguments.source_json)
    output_json = cast(Path, arguments.output_json)
    output_report = cast(Path, arguments.output_report)
    _payload, json_bytes, report_bytes = run_analysis(source_path)
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
                "source_result_sha256": SOURCE_RESULT_SHA256,
                "status": "COMPLETE",
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
