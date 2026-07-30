#!/usr/bin/env python3
# pyright: reportUnknownArgumentType=false
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false
# pyright: reportUnknownLambdaType=false, reportAttributeAccessIssue=false
"""Build exact frozen evolution-engine parity shards and their ledger."""

from __future__ import annotations

import argparse
import bisect
import functools
import hashlib
import importlib
import json
import os
import platform
import subprocess
import sys
import tempfile
import time
import weakref
from collections import Counter, OrderedDict
from pathlib import Path
from typing import Any, cast

FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
METHOD_ID = "tools/evolving_strategy_engine/evolution_engine.py"
SOURCE_SHA256 = (
    "3df019c31ce48e38efc7fd8b52d3e6eb5fd6ab1927bc789785e6d1e85c794f54"
)
PINNED_DATASET_SHA256 = (
    "2f3d711cb97cddabfc6d351b5a639614da60dc3473cc23368711f605e3fe2d6b"
)
HISTORY_INPUT_FILE_SHA256 = (
    "e501c2e1b0a5c610bae3822a2784a72860e2c549daadb37c344de61d16129493"
)
HISTORY_INPUT_CANONICAL_SHA256 = (
    "155766ddc1f7581392d91fc8f5e79a433f6e245a9feefb5cb059b8d2594af7c9"
)
SHARD_SCHEMA_VERSION = "BIG_LOTTO_EVOLUTION_WAVE65_PARITY_SHARD_V1"
LEDGER_SCHEMA_VERSION = "BIG_LOTTO_EVOLUTION_WAVE65_TICKET_LEDGER_V1"
PARITY_SCHEMA_VERSION = "BIG_LOTTO_EVOLUTION_WAVE65_PARITY_V1"
CAUSAL_PROTOCOL = (
    "FROZEN_EVOLUTION_ENGINE_SEED42_DRIVER_DEFAULTS_STRICT_PREFIX_V1"
)
ACCELERATION_PROTOCOL = (
    "PURE_BOUNDED_LRU_PREDICT_AND_FEATURE_MEMOIZATION_BY_COMPLETE_"
    "STRATEGY_GRAPH_WITH_WEAK_OBJECT_GRAPH_KEY_CACHE_N_SELECT_AND_"
    "EXACT_INTEGER_PREFIX_PRECOMPUTATION_ON_PINNED_DRAWS_V5"
)
CLOSED_REASON = "OOS_EVALUATOR_REQUIRES_MORE_THAN_500_HISTORY_DRAWS"
FIRST_EXECUTABLE_TARGET_INDEX = 501
TARGET_COUNT = 2149
DRIVER_GENERATIONS = 8
DRIVER_POPULATION_SIZE = 50
DRIVER_N_TEST = 1500
ENGINE_SEED = 42
SOURCE_REFERENCE_RUNTIME = (
    "CPYTHON_3_9_6_NUMPY_1_26_2_SCIPY_1_13_1"
)
MAX_PREDICT_CACHE_ENTRIES = 250000
MAX_FEATURE_CACHE_ENTRIES = 50000
REFERENCE_CUTOFF_501_PROJECTION_SHA256 = (
    "5709d17e407f010deea705ede0e4f8a7b553a0d1f12e8667a3844996190bb24b"
)

SOURCE_ARTIFACTS = (
    {
        "blob_id": "ab5455e043fe408c890270340a75e93956fbabc5",
        "byte_size": 10504,
        "path": METHOD_ID,
        "sha256": SOURCE_SHA256,
    },
    {
        "blob_id": "426c708927705a0d72e1098b942f8005c805d8c1",
        "byte_size": 19698,
        "path": "tools/evolving_strategy_engine/strategy_generator.py",
        "sha256": (
            "e63da93ea11ad27e7368f7bd0d9215f371a059353c4c7adde"
            "7057fc803444ad6"
        ),
    },
    {
        "blob_id": "f37f0453c855009b8a0584fb8e1d323f121ecdd9",
        "byte_size": 4582,
        "path": "tools/evolving_strategy_engine/evaluator.py",
        "sha256": (
            "f95565da124e506cc5f5045b9136025831bac4dbee2ef8aed"
            "f66f177b5cefd34"
        ),
    },
    {
        "blob_id": "ff72f841c28f8e553d9dddc017b85c2a3ae518dd",
        "byte_size": 10543,
        "path": "tools/evolving_strategy_engine/strategy_base.py",
        "sha256": (
            "b9224ce1634482f751223752c7308233a8fd836b9e133facb"
            "95458edc85238ea"
        ),
    },
    {
        "blob_id": "5baf194d55ce5de2ad97bbaeffb41780610446cc",
        "byte_size": 3292,
        "path": "tools/evolving_strategy_engine/data_loader.py",
        "sha256": (
            "9a4ba5fd53737cbb7b2c88713c35c3fe4b8c3e7c21c8f283"
            "6c5b76a1e9784931"
        ),
    },
    {
        "blob_id": "57fe075fdd3594b18a69c919fa7cd6f3c96b9d66",
        "byte_size": 3546,
        "path": "tools/run_evolution.py",
        "sha256": (
            "0c1d3924493d8350f5d23068b50f29109ef96370026f1dce"
            "8711e244995c294f"
        ),
    },
)


class Wave65ParityError(ValueError):
    """The frozen source or generated parity artifact is inconsistent."""


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _git(frozen_root: Path, *arguments: str) -> bytes:
    try:
        return subprocess.run(
            ("git", "-C", str(frozen_root), *arguments),
            check=True,
            capture_output=True,
        ).stdout
    except subprocess.CalledProcessError as exc:
        raise Wave65ParityError("frozen Git authority lookup failed") from exc


def _validate_regular_file(path: Path, context: str) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise Wave65ParityError(
            f"{context} must be a regular non-symlink file"
        )
    return path.read_bytes()


def _validate_source_artifacts(
    *,
    frozen_root: Path,
    frozen_source_directory: Path,
) -> None:
    commit = _git(
        frozen_root,
        "rev-parse",
        FROZEN_SOURCE_COMMIT,
    ).decode("ascii").strip()
    if commit != FROZEN_SOURCE_COMMIT:
        raise Wave65ParityError("frozen source commit changed")
    for artifact in SOURCE_ARTIFACTS:
        path = cast(str, artifact["path"])
        expected_blob = cast(str, artifact["blob_id"])
        expected_size = cast(int, artifact["byte_size"])
        expected_sha256 = cast(str, artifact["sha256"])
        git_raw = _git(
            frozen_root,
            "show",
            f"{FROZEN_SOURCE_COMMIT}:{path}",
        )
        extracted_raw = _validate_regular_file(
            frozen_source_directory / path,
            f"frozen source {path}",
        )
        blob = _git(
            frozen_root,
            "rev-parse",
            f"{FROZEN_SOURCE_COMMIT}:{path}",
        ).decode("ascii").strip()
        if (
            blob != expected_blob
            or len(git_raw) != expected_size
            or _sha256(git_raw) != expected_sha256
            or extracted_raw != git_raw
        ):
            raise Wave65ParityError(f"frozen source identity changed: {path}")


def _load_history_input(path: Path) -> tuple[list[dict[str, Any]], list[list[int]]]:
    raw = _validate_regular_file(path, "history input")
    if _sha256(raw) != HISTORY_INPUT_FILE_SHA256:
        raise Wave65ParityError("history input physical SHA-256 changed")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise Wave65ParityError("history input is invalid JSON") from exc
    if not isinstance(parsed, dict):
        raise Wave65ParityError("history input must be an object")
    document = cast(dict[str, Any], parsed)
    if (
        _sha256(_canonical_bytes(document))
        != HISTORY_INPUT_CANONICAL_SHA256
        or document.get("dataset_sha256") != PINNED_DATASET_SHA256
        or document.get("lottery_type") != "BIG_LOTTO"
    ):
        raise Wave65ParityError("history input authority changed")
    targets_raw = document.get("targets")
    if not isinstance(targets_raw, list) or len(targets_raw) != TARGET_COUNT:
        raise Wave65ParityError("history target count changed")
    targets: list[dict[str, Any]] = []
    draws: list[list[int]] = []
    for index, candidate in enumerate(cast(list[object], targets_raw)):
        if not isinstance(candidate, dict):
            raise Wave65ParityError(f"target {index} is malformed")
        target = cast(dict[str, Any], candidate)
        draw_number = target.get("draw_number")
        draw_date = target.get("draw_date")
        numbers = target.get("winning_main_numbers")
        special = target.get("winning_special_number")
        if (
            type(draw_number) is not str
            or type(draw_date) is not str
            or not isinstance(numbers, list)
            or len(numbers) != 6
            or any(type(number) is not int for number in numbers)
            or cast(list[int], numbers) != sorted(cast(list[int], numbers))
            or len(set(cast(list[int], numbers))) != 6
            or any(not 1 <= number <= 49 for number in cast(list[int], numbers))
            or type(special) is not int
        ):
            raise Wave65ParityError(f"target {index} identity changed")
        targets.append(target)
        draws.append(cast(list[int], numbers))
    if (
        targets[0]["draw_number"] != "96000001"
        or targets[-1]["draw_number"] != "115000073"
        or len({target["draw_number"] for target in targets}) != TARGET_COUNT
    ):
        raise Wave65ParityError("history target universe changed")
    return targets, draws


def _validate_runtime(np_module: Any, scipy_module: Any) -> None:
    if (
        platform.python_version() != "3.9.6"
        or np_module.__version__ != "1.26.2"
        or scipy_module.__version__ != "1.13.1"
    ):
        raise Wave65ParityError("source reference runtime changed")


def _json_safe(value: object, np_module: Any) -> object:
    if isinstance(value, np_module.generic):
        return value.item()
    if isinstance(value, np_module.ndarray):
        return [
            _json_safe(item, np_module)
            for item in cast(list[object], value.tolist())
        ]
    if isinstance(value, dict):
        return {
            str(key): _json_safe(item, np_module)
            for key, item in cast(dict[object, object], value).items()
        }
    if isinstance(value, (list, tuple)):
        return [_json_safe(item, np_module) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    raise Wave65ParityError(
        f"source output contains unsupported type: {type(value).__name__}"
    )


def _install_exact_memoization(
    *,
    base_strategy: type[Any],
    feature_library: type[Any],
    data_loader: Any,
    np_module: Any,
    pinned_draws: Any,
) -> tuple[
    OrderedDict[object, tuple[int, ...]],
    OrderedDict[object, object],
]:
    predict_cache: OrderedDict[object, tuple[int, ...]] = OrderedDict()
    feature_cache: OrderedDict[object, object] = OrderedDict()
    strategy_key_cache: weakref.WeakKeyDictionary[Any, object] = (
        weakref.WeakKeyDictionary()
    )
    full_binary = data_loader.build_binary_matrix(pinned_draws)
    prefix_frequency = np_module.zeros(
        (len(pinned_draws) + 1, 49),
        dtype=np_module.int64,
    )
    prefix_frequency[1:] = np_module.cumsum(
        full_binary,
        axis=0,
        dtype=np_module.int64,
    )
    prefix_co_occurrence = np_module.zeros(
        (len(pinned_draws) + 1, 49, 49),
        dtype=np_module.int64,
    )
    prefix_consecutive = np_module.zeros(
        (len(pinned_draws) + 1, 49),
        dtype=np_module.int64,
    )
    positions: list[list[int]] = [[] for _ in range(49)]
    for draw_index, row in enumerate(pinned_draws):
        prefix_co_occurrence[draw_index + 1] = prefix_co_occurrence[
            draw_index
        ]
        prefix_consecutive[draw_index + 1] = prefix_consecutive[
            draw_index
        ]
        typed_row = [int(number) for number in row]
        for number in typed_row:
            positions[number - 1].append(draw_index)
        for left_index, left in enumerate(typed_row):
            for right in typed_row[left_index + 1 :]:
                prefix_co_occurrence[draw_index + 1, left - 1, right - 1] += 1
                prefix_co_occurrence[draw_index + 1, right - 1, left - 1] += 1
        ordered = sorted(typed_row)
        for position in range(len(ordered) - 1):
            if ordered[position + 1] - ordered[position] == 1:
                prefix_consecutive[
                    draw_index + 1,
                    ordered[position] - 1,
                ] += 1
                prefix_consecutive[
                    draw_index + 1,
                    ordered[position + 1] - 1,
                ] += 1
    full_sums = np_module.asarray(
        [sum(int(number) for number in row) for row in pinned_draws],
        dtype=np_module.int64,
    )
    transition_prefix_by_order: dict[int, object] = {}

    def freeze(value: object) -> object:
        if isinstance(value, np_module.generic):
            return ("numpy", value.dtype.str, value.item())
        if isinstance(value, base_strategy):
            found = strategy_key_cache.get(value)
            if found is not None:
                return found
            key = (
                "strategy",
                value.__class__.__module__,
                value.__class__.__qualname__,
                freeze(vars(value)),
            )
            strategy_key_cache[value] = key
            return key
        if isinstance(value, dict):
            typed = cast(dict[object, object], value)
            return (
                "dict",
                tuple(
                    (str(key), freeze(item))
                    for key, item in sorted(
                        typed.items(),
                        key=lambda row: str(row[0]),
                    )
                ),
            )
        if isinstance(value, (list, tuple)):
            return (
                type(value).__name__,
                tuple(freeze(item) for item in value),
            )
        if isinstance(value, np_module.ndarray):
            return (
                "array",
                value.dtype.str,
                value.shape,
                value.tobytes(),
            )
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        raise Wave65ParityError(
            f"memoization key contains unsupported type: {type(value).__name__}"
        )

    classes: list[type[Any]] = []
    stack = list(base_strategy.__subclasses__())
    while stack:
        strategy_class = stack.pop()
        classes.append(strategy_class)
        stack.extend(strategy_class.__subclasses__())

    def predict_wrapper(
        strategy_class: type[Any],
        original: Any,
    ) -> Any:
        @functools.wraps(original)
        def cached(
            strategy: Any,
            draws: Any,
            n_select: int = 6,
        ) -> list[int]:
            key = (
                strategy_class.__module__,
                strategy_class.__qualname__,
                freeze(vars(strategy)),
                len(draws),
                n_select,
            )
            found = predict_cache.get(key)
            if found is not None:
                predict_cache.move_to_end(key)
                return list(found)
            result = cast(list[int], original(strategy, draws, n_select))
            predict_cache[key] = tuple(result)
            if len(predict_cache) > MAX_PREDICT_CACHE_ENTRIES:
                predict_cache.popitem(last=False)
            return list(result)

        return cached

    for strategy_class in classes:
        original = strategy_class.predict
        strategy_class.predict = predict_wrapper(strategy_class, original)

    def window_start(draw_count: int, window: int | None) -> int:
        if window is None:
            return 0
        return max(0, draw_count - window)

    def exact_frequency(draws: Any, window: int | None = None) -> object:
        draw_count = len(draws)
        start = window_start(draw_count, window)
        counts = prefix_frequency[draw_count] - prefix_frequency[start]
        return counts.astype(float) / (draw_count - start)

    def exact_binary(draws: Any) -> object:
        return full_binary[: len(draws)]

    def exact_co_occurrence(
        draws: Any,
        window: int = 100,
    ) -> object:
        draw_count = len(draws)
        start = window_start(draw_count, window)
        return (
            prefix_co_occurrence[draw_count]
            - prefix_co_occurrence[start]
        )

    def exact_consecutive_pairs(
        draws: Any,
        window: int = 50,
    ) -> object:
        draw_count = len(draws)
        start = window_start(draw_count, window)
        counts = prefix_consecutive[draw_count] - prefix_consecutive[start]
        return counts.astype(float) / (draw_count - start)

    def exact_sum_trend(draws: Any, window: int = 30) -> object:
        draw_count = len(draws)
        start = window_start(draw_count, window)
        return full_sums[start:draw_count]

    def exact_gap_current(draws: Any) -> object:
        draw_count = len(draws)
        gaps = np_module.zeros(49, dtype=int)
        for number_index, number_positions in enumerate(positions):
            count = bisect.bisect_left(number_positions, draw_count)
            gaps[number_index] = (
                draw_count - 1 - number_positions[count - 1]
                if count
                else draw_count
            )
        return gaps

    def exact_gap_mean_std(draws: Any) -> tuple[object, object]:
        draw_count = len(draws)
        means = np_module.zeros(49)
        stds = np_module.zeros(49)
        for number_index, number_positions in enumerate(positions):
            count = bisect.bisect_left(number_positions, draw_count)
            if count >= 2:
                gaps = np_module.diff(number_positions[:count])
                means[number_index] = np_module.mean(gaps)
                stds[number_index] = np_module.std(gaps)
            else:
                means[number_index] = draw_count
                stds[number_index] = 0
        return means, stds

    def transition_prefix(order: int) -> object:
        cached = transition_prefix_by_order.get(order)
        if cached is not None:
            return cached
        cumulative = np_module.zeros(
            (len(pinned_draws) + 1, 49, 2, 2),
            dtype=np_module.int64,
        )
        number_indices = np_module.arange(49)
        for draw_index in range(len(pinned_draws)):
            cumulative[draw_index + 1] = cumulative[draw_index]
            if draw_index < order:
                continue
            previous = full_binary[draw_index - order].astype(int)
            current = full_binary[draw_index].astype(int)
            cumulative[
                draw_index + 1,
                number_indices,
                previous,
                current,
            ] += 1
        transition_prefix_by_order[order] = cumulative
        return cumulative

    def exact_markov_transition(draws: Any, order: int = 1) -> object:
        trans = cast(Any, transition_prefix(order))[len(draws)]
        probabilities = np_module.zeros((49, 2))
        for number_index in range(49):
            for state in range(2):
                total = trans[number_index, state, :].sum()
                if total > 0:
                    probabilities[number_index, state] = (
                        trans[number_index, state, 1] / total
                    )
        return probabilities

    feature_library.frequency = staticmethod(exact_frequency)
    feature_library.gap_current = staticmethod(exact_gap_current)
    feature_library.gap_mean_std = staticmethod(exact_gap_mean_std)
    feature_library.co_occurrence = staticmethod(exact_co_occurrence)
    feature_library.sum_trend = staticmethod(exact_sum_trend)
    feature_library.consecutive_pairs = staticmethod(
        exact_consecutive_pairs
    )
    feature_library.markov_transition = staticmethod(
        exact_markov_transition
    )
    data_loader.build_binary_matrix = exact_binary

    feature_names = (
        "frequency",
        "gap_current",
        "gap_mean_std",
        "hot_cold_score",
        "co_occurrence",
        "zone_distribution",
        "odd_even_ratio",
        "sum_trend",
        "consecutive_pairs",
        "lag_autocorrelation",
        "fourier_phase",
        "markov_transition",
        "deviation_score",
        "gap_pressure",
        "zonal_density_score",
        "gap_momentum",
    )

    def feature_wrapper(name: str, original: Any) -> Any:
        def cached(draws: Any, *args: object, **kwargs: object) -> object:
            key = (name, len(draws), freeze(args), freeze(kwargs))
            if key not in feature_cache:
                feature_cache[key] = original(draws, *args, **kwargs)
                if len(feature_cache) > MAX_FEATURE_CACHE_ENTRIES:
                    feature_cache.popitem(last=False)
            else:
                feature_cache.move_to_end(key)
            return feature_cache[key]

        return cached

    for name in feature_names:
        original = getattr(feature_library, name)
        setattr(
            feature_library,
            name,
            staticmethod(feature_wrapper(name, original)),
        )

    original_binary = data_loader.build_binary_matrix

    def cached_binary(draws: Any) -> object:
        key = ("build_binary_matrix", len(draws))
        if key not in feature_cache:
            feature_cache[key] = original_binary(draws)
            if len(feature_cache) > MAX_FEATURE_CACHE_ENTRIES:
                feature_cache.popitem(last=False)
        else:
            feature_cache.move_to_end(key)
        return feature_cache[key]

    data_loader.build_binary_matrix = cached_binary
    return predict_cache, feature_cache


def _validate_ticket(value: object, context: str) -> list[int]:
    if not isinstance(value, list):
        raise Wave65ParityError(f"{context}: ticket is not an array")
    numbers = cast(list[object], value)
    if (
        len(numbers) != 6
        or any(type(number) is not int for number in numbers)
        or cast(list[int], numbers) != sorted(cast(list[int], numbers))
        or len(set(cast(list[int], numbers))) != 6
        or any(not 1 <= number <= 49 for number in cast(list[int], numbers))
    ):
        raise Wave65ParityError(f"{context}: ticket is not canonical")
    return cast(list[int], numbers)


def _leaderboard_projection(
    report: dict[str, Any],
    np_module: Any,
) -> list[dict[str, object]]:
    raw = report.get("1_leaderboard")
    if not isinstance(raw, list):
        raise Wave65ParityError("source leaderboard is missing")
    projected: list[dict[str, object]] = []
    for position, candidate in enumerate(cast(list[object], raw)):
        if not isinstance(candidate, dict):
            raise Wave65ParityError("source leaderboard row is malformed")
        row = cast(dict[str, object], candidate)
        projected_row = {
            key: _json_safe(row.get(key), np_module)
            for key in (
                "name",
                "numbers",
                "generation",
                "edge_>=3",
                "hit_rates",
                "params",
            )
        }
        _validate_ticket(
            projected_row["numbers"],
            f"leaderboard position {position}",
        )
        projected.append(projected_row)
    if not 1 <= len(projected) <= 10:
        raise Wave65ParityError("executable leaderboard count is invalid")
    return projected


def _write_new_json(path: Path, document: dict[str, object]) -> tuple[int, str]:
    if path.exists():
        raise Wave65ParityError(f"refusing to overwrite existing output: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = _canonical_bytes(document) + b"\n"
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        if path.exists():
            raise Wave65ParityError(
                f"refusing to overwrite existing output: {path}"
            )
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)
    return len(payload), _sha256(payload)


def build_shard(
    *,
    frozen_root: Path,
    frozen_source_directory: Path,
    history_input: Path,
    target_start: int,
    target_stop: int,
    output_file: Path,
) -> dict[str, object]:
    """Run one exact, memoized, contiguous executable target shard."""

    if not (
        FIRST_EXECUTABLE_TARGET_INDEX
        <= target_start
        < target_stop
        <= TARGET_COUNT
    ):
        raise Wave65ParityError("invalid executable target shard range")
    _validate_source_artifacts(
        frozen_root=frozen_root,
        frozen_source_directory=frozen_source_directory,
    )
    targets, draw_rows = _load_history_input(history_input)
    tools_directory = frozen_source_directory / "tools"
    sys.path.insert(0, str(tools_directory))
    np_module = importlib.import_module("numpy")
    scipy_module = importlib.import_module("scipy")
    _validate_runtime(np_module, scipy_module)
    data_loader = importlib.import_module(
        "evolving_strategy_engine.data_loader"
    )
    evolution_engine = importlib.import_module(
        "evolving_strategy_engine.evolution_engine"
    )
    strategy_base = importlib.import_module(
        "evolving_strategy_engine.strategy_base"
    )
    evolution_engine._print = lambda _message: None
    draws = np_module.asarray(draw_rows, dtype=np_module.int32)
    predict_cache, feature_cache = _install_exact_memoization(
        base_strategy=strategy_base.BaseStrategy,
        feature_library=strategy_base.FeatureLibrary,
        data_loader=data_loader,
        np_module=np_module,
        pinned_draws=draws,
    )
    rows: list[dict[str, object]] = []
    started = time.perf_counter()
    for target_index in range(target_start, target_stop):
        engine = evolution_engine.EvolutionEngine(
            draws=draws[:target_index],
            meta=[],
            seed=ENGINE_SEED,
        )
        report = cast(
            dict[str, Any],
            engine.run(
                n_generations=DRIVER_GENERATIONS,
                n_test=DRIVER_N_TEST,
                pop_size=DRIVER_POPULATION_SIZE,
            ),
        )
        leaderboard = _leaderboard_projection(report, np_module)
        if target_index == FIRST_EXECUTABLE_TARGET_INDEX:
            reference_projection = [
                {
                    key: row[key]
                    for key in (
                        "name",
                        "numbers",
                        "generation",
                        "edge_>=3",
                        "hit_rates",
                        "params",
                    )
                }
                for row in leaderboard
            ]
            if (
                _sha256(_canonical_bytes(reference_projection))
                != REFERENCE_CUTOFF_501_PROJECTION_SHA256
            ):
                raise Wave65ParityError(
                    "memoized cutoff-501 output changed from native reference"
                )
        tickets = [
            _validate_ticket(
                row["numbers"],
                f"target {target_index} native ticket {position}",
            )
            for position, row in enumerate(leaderboard)
        ]
        generation_history = report.get("evolution_history")
        if not isinstance(generation_history, list) or len(
            generation_history
        ) != DRIVER_GENERATIONS:
            raise Wave65ParityError("source generation history changed")
        generation_population: list[int] = []
        for generation in cast(list[object], generation_history):
            if (
                not isinstance(generation, dict)
                or type(generation.get("pop_size")) is not int
            ):
                raise Wave65ParityError(
                    "source generation population is malformed"
                )
            generation_population.append(
                cast(int, generation["pop_size"])
            )
        total_strategies_tested = report.get("total_strategies_tested")
        pattern_exists = report.get("6_pattern_exists")
        why_no_pattern = report.get("8_why_no_pattern")
        if (
            type(total_strategies_tested) is not int
            or type(pattern_exists) is not bool
            or type(why_no_pattern) is not str
        ):
            raise Wave65ParityError("source report metadata changed")
        rows.append(
            {
                "context_numbers_sha256": _sha256(
                    _canonical_bytes(draw_rows[:target_index])
                ),
                "generation_population": generation_population,
                "leaderboard": leaderboard,
                "leaderboard_sha256": _sha256(
                    _canonical_bytes(leaderboard)
                ),
                "native_duplicate_ticket_count": (
                    len(tickets)
                    - len({tuple(ticket) for ticket in tickets})
                ),
                "native_ticket_count": len(tickets),
                "native_tickets": tickets,
                "pattern_exists": pattern_exists,
                "target_draw_number": targets[target_index]["draw_number"],
                "target_index": target_index,
                "total_strategies_tested": total_strategies_tested,
                "why_no_pattern": why_no_pattern,
            }
        )
    document: dict[str, object] = {
        "acceleration_protocol": ACCELERATION_PROTOCOL,
        "causal_protocol": CAUSAL_PROTOCOL,
        "engine_seed": ENGINE_SEED,
        "max_feature_cache_entries": MAX_FEATURE_CACHE_ENTRIES,
        "max_predict_cache_entries": MAX_PREDICT_CACHE_ENTRIES,
        "frozen_source_commit": FROZEN_SOURCE_COMMIT,
        "history_input_file_sha256": HISTORY_INPUT_FILE_SHA256,
        "legacy_method_id": METHOD_ID,
        "rows": rows,
        "shard_schema_version": SHARD_SCHEMA_VERSION,
        "source_artifacts": list(SOURCE_ARTIFACTS),
        "source_reference_runtime": SOURCE_REFERENCE_RUNTIME,
        "target_start": target_start,
        "target_stop": target_stop,
    }
    document["shard_content_sha256"] = _sha256(_canonical_bytes(document))
    byte_size, physical_sha256 = _write_new_json(output_file, document)
    return {
        "byte_size": byte_size,
        "elapsed_seconds": time.perf_counter() - started,
        "feature_cache_entry_count": len(feature_cache),
        "output_file": str(output_file),
        "physical_file_sha256": physical_sha256,
        "predict_cache_entry_count": len(predict_cache),
        "shard_content_sha256": document["shard_content_sha256"],
        "target_count": target_stop - target_start,
        "target_start": target_start,
        "target_stop": target_stop,
    }


def _read_shard(path: Path) -> tuple[dict[str, Any], str]:
    raw = _validate_regular_file(path, "parity shard")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise Wave65ParityError(f"invalid parity shard: {path}") from exc
    if not isinstance(parsed, dict):
        raise Wave65ParityError(f"invalid parity shard: {path}")
    shard = cast(dict[str, Any], parsed)
    reduced = {
        key: value
        for key, value in shard.items()
        if key != "shard_content_sha256"
    }
    if (
        shard.get("shard_schema_version") != SHARD_SCHEMA_VERSION
        or shard.get("frozen_source_commit") != FROZEN_SOURCE_COMMIT
        or shard.get("legacy_method_id") != METHOD_ID
        or shard.get("source_artifacts") != list(SOURCE_ARTIFACTS)
        or shard.get("source_reference_runtime")
        != SOURCE_REFERENCE_RUNTIME
        or shard.get("causal_protocol") != CAUSAL_PROTOCOL
        or shard.get("acceleration_protocol")
        != ACCELERATION_PROTOCOL
        or shard.get("history_input_file_sha256")
        != HISTORY_INPUT_FILE_SHA256
        or shard.get("max_feature_cache_entries")
        != MAX_FEATURE_CACHE_ENTRIES
        or shard.get("max_predict_cache_entries")
        != MAX_PREDICT_CACHE_ENTRIES
        or shard.get("shard_content_sha256")
        != _sha256(_canonical_bytes(reduced))
    ):
        raise Wave65ParityError(f"parity shard identity changed: {path}")
    return shard, _sha256(raw)


def combine_shards(
    *,
    frozen_root: Path,
    frozen_source_directory: Path,
    history_input: Path,
    shard_files: list[Path],
    ledger_output: Path,
    parity_output: Path,
) -> dict[str, object]:
    """Combine complete executable shards with the proven closed prefix."""

    if not shard_files:
        raise Wave65ParityError("at least one shard is required")
    _validate_source_artifacts(
        frozen_root=frozen_root,
        frozen_source_directory=frozen_source_directory,
    )
    targets, draw_rows = _load_history_input(history_input)
    rows_by_index: dict[int, dict[str, Any]] = {}
    shard_identities: list[dict[str, object]] = []
    for shard_file in shard_files:
        shard, physical_sha256 = _read_shard(shard_file)
        rows = shard.get("rows")
        if not isinstance(rows, list):
            raise Wave65ParityError("parity shard rows are missing")
        for candidate in cast(list[object], rows):
            if (
                not isinstance(candidate, dict)
                or type(candidate.get("target_index")) is not int
            ):
                raise Wave65ParityError("parity shard row is malformed")
            row = cast(dict[str, Any], candidate)
            target_index = cast(int, row["target_index"])
            if target_index in rows_by_index:
                raise Wave65ParityError(
                    f"duplicate parity target index: {target_index}"
                )
            rows_by_index[target_index] = row
        shard_identities.append(
            {
                "physical_file_sha256": physical_sha256,
                "shard_content_sha256": shard["shard_content_sha256"],
                "target_start": shard["target_start"],
                "target_stop": shard["target_stop"],
            }
        )
    expected_indices = set(range(FIRST_EXECUTABLE_TARGET_INDEX, TARGET_COUNT))
    if set(rows_by_index) != expected_indices:
        missing = sorted(expected_indices - set(rows_by_index))
        extra = sorted(set(rows_by_index) - expected_indices)
        raise Wave65ParityError(
            f"parity shard coverage changed: missing={missing[:3]} extra={extra[:3]}"
        )

    statuses: list[str] = []
    closed_reasons: list[str | None] = []
    contexts: list[str] = []
    native_tickets: list[list[list[int]] | None] = []
    leaderboards: list[list[dict[str, object]] | None] = []
    total_strategies: list[int | None] = []
    generation_populations: list[list[int] | None] = []
    pattern_exists: list[bool | None] = []
    native_counts: Counter[int] = Counter()
    duplicate_counts: Counter[int] = Counter()
    native_ticket_position_count = 0
    for target_index, target in enumerate(targets):
        expected_context = _sha256(
            _canonical_bytes(draw_rows[:target_index])
        )
        contexts.append(expected_context)
        if target_index < FIRST_EXECUTABLE_TARGET_INDEX:
            statuses.append("CLOSED_INSUFFICIENT_HISTORY")
            closed_reasons.append(CLOSED_REASON)
            native_tickets.append(None)
            leaderboards.append(None)
            total_strategies.append(None)
            generation_populations.append(None)
            pattern_exists.append(None)
            continue
        row = rows_by_index[target_index]
        tickets = row.get("native_tickets")
        leaderboard = row.get("leaderboard")
        if (
            row.get("target_draw_number") != target["draw_number"]
            or row.get("context_numbers_sha256") != expected_context
            or not isinstance(tickets, list)
            or not isinstance(leaderboard, list)
            or row.get("native_ticket_count") != len(tickets)
            or row.get("leaderboard_sha256")
            != _sha256(_canonical_bytes(leaderboard))
            or len(tickets) != len(leaderboard)
        ):
            raise Wave65ParityError(
                f"parity row identity changed: {target_index}"
            )
        typed_tickets = [
            _validate_ticket(
                ticket,
                f"target {target_index} native ticket {position}",
            )
            for position, ticket in enumerate(cast(list[object], tickets))
        ]
        duplicate_count = (
            len(typed_tickets)
            - len({tuple(ticket) for ticket in typed_tickets})
        )
        if row.get("native_duplicate_ticket_count") != duplicate_count:
            raise Wave65ParityError(
                f"parity duplicate count changed: {target_index}"
            )
        statuses.append("OK")
        closed_reasons.append(None)
        native_tickets.append(typed_tickets)
        leaderboards.append(cast(list[dict[str, object]], leaderboard))
        total_strategies.append(cast(int, row["total_strategies_tested"]))
        generation_populations.append(
            cast(list[int], row["generation_population"])
        )
        pattern_exists.append(cast(bool, row["pattern_exists"]))
        native_counts[len(typed_tickets)] += 1
        duplicate_counts[duplicate_count] += 1
        native_ticket_position_count += len(typed_tickets)

    ledger: dict[str, object] = {
        "acceleration_protocol": ACCELERATION_PROTOCOL,
        "causal_protocol": CAUSAL_PROTOCOL,
        "closed_reason_by_target": closed_reasons,
        "context_numbers_sha256_by_target": contexts,
        "dataset_sha256": PINNED_DATASET_SHA256,
        "driver_generations": DRIVER_GENERATIONS,
        "driver_n_test": DRIVER_N_TEST,
        "driver_population_size": DRIVER_POPULATION_SIZE,
        "engine_seed": ENGINE_SEED,
        "max_feature_cache_entries": MAX_FEATURE_CACHE_ENTRIES,
        "max_predict_cache_entries": MAX_PREDICT_CACHE_ENTRIES,
        "execution_status_by_target": statuses,
        "first_executable_target_index": FIRST_EXECUTABLE_TARGET_INDEX,
        "frozen_source_commit": FROZEN_SOURCE_COMMIT,
        "generation_population_by_target": generation_populations,
        "history_input_draw_count": list(range(TARGET_COUNT)),
        "history_input_file_sha256": HISTORY_INPUT_FILE_SHA256,
        "leaderboard_by_target": leaderboards,
        "legacy_method_id": METHOD_ID,
        "native_ticket_count_distribution": {
            str(key): value for key, value in sorted(native_counts.items())
        },
        "native_ticket_position_count": native_ticket_position_count,
        "native_tickets_by_target": native_tickets,
        "native_duplicate_ticket_count_distribution": {
            str(key): value
            for key, value in sorted(duplicate_counts.items())
        },
        "pattern_exists_by_target": pattern_exists,
        "source_artifacts": list(SOURCE_ARTIFACTS),
        "source_reference_runtime": SOURCE_REFERENCE_RUNTIME,
        "target_draw_numbers": [
            cast(str, target["draw_number"]) for target in targets
        ],
        "total_strategies_tested_by_target": total_strategies,
        "ledger_schema_version": LEDGER_SCHEMA_VERSION,
    }
    ledger["context_sequence_sha256"] = _sha256(_canonical_bytes(contexts))
    ledger["leaderboard_sequence_sha256"] = _sha256(
        _canonical_bytes(leaderboards)
    )
    ledger["status_sequence_sha256"] = _sha256(_canonical_bytes(statuses))
    ledger["ticket_sequence_sha256"] = _sha256(
        _canonical_bytes(native_tickets)
    )
    ledger["ledger_content_sha256"] = _sha256(_canonical_bytes(ledger))
    ledger_size, ledger_file_sha256 = _write_new_json(
        ledger_output,
        ledger,
    )

    status_counts = Counter(statuses)
    parity: dict[str, object] = {
        "acceleration_protocol": ACCELERATION_PROTOCOL,
        "causal_protocol": CAUSAL_PROTOCOL,
        "closed_boundary": {
            "closed_history_draw_count_max": 500,
            "first_executable_history_draw_count": 501,
            "reason_code": CLOSED_REASON,
        },
        "context_sequence_sha256": ledger["context_sequence_sha256"],
        "first_target_status": statuses[0],
        "frozen_source_commit": FROZEN_SOURCE_COMMIT,
        "leaderboard_sequence_sha256": ledger[
            "leaderboard_sequence_sha256"
        ],
        "ledger_content_sha256": ledger["ledger_content_sha256"],
        "ledger_file_sha256": ledger_file_sha256,
        "legacy_method_id": METHOD_ID,
        "native_duplicate_ticket_count_distribution": ledger[
            "native_duplicate_ticket_count_distribution"
        ],
        "native_ticket_count_distribution": ledger[
            "native_ticket_count_distribution"
        ],
        "native_ticket_position_count": native_ticket_position_count,
        "parity_schema_version": PARITY_SCHEMA_VERSION,
        "reference_equivalence": {
            "cutoff_501_memoized_projection_sha256": (
                REFERENCE_CUTOFF_501_PROJECTION_SHA256
            ),
            "cutoff_501_native_projection_sha256": (
                REFERENCE_CUTOFF_501_PROJECTION_SHA256
            ),
            "status": "PASS",
        },
        "shards": sorted(
            shard_identities,
            key=lambda item: cast(int, item["target_start"]),
        ),
        "source_artifacts": list(SOURCE_ARTIFACTS),
        "source_reference_runtime": SOURCE_REFERENCE_RUNTIME,
        "status": "PASS",
        "status_counts": dict(sorted(status_counts.items())),
        "status_sequence_sha256": ledger["status_sequence_sha256"],
        "target_count": TARGET_COUNT,
        "ticket_sequence_sha256": ledger["ticket_sequence_sha256"],
    }
    parity["parity_sha256"] = _sha256(_canonical_bytes(parity))
    parity_size, parity_file_sha256 = _write_new_json(
        parity_output,
        parity,
    )
    return {
        "ledger_content_sha256": ledger["ledger_content_sha256"],
        "ledger_file_sha256": ledger_file_sha256,
        "ledger_size": ledger_size,
        "native_ticket_position_count": native_ticket_position_count,
        "parity_file_sha256": parity_file_sha256,
        "parity_sha256": parity["parity_sha256"],
        "parity_size": parity_size,
        "status_counts": dict(sorted(status_counts.items())),
        "ticket_sequence_sha256": ledger["ticket_sequence_sha256"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    shard_parser = subparsers.add_parser("shard")
    shard_parser.add_argument("--frozen-root", required=True, type=Path)
    shard_parser.add_argument(
        "--frozen-source-directory",
        required=True,
        type=Path,
    )
    shard_parser.add_argument("--history-input", required=True, type=Path)
    shard_parser.add_argument("--target-start", required=True, type=int)
    shard_parser.add_argument("--target-stop", required=True, type=int)
    shard_parser.add_argument("--output-file", required=True, type=Path)
    combine_parser = subparsers.add_parser("combine")
    combine_parser.add_argument("--frozen-root", required=True, type=Path)
    combine_parser.add_argument(
        "--frozen-source-directory",
        required=True,
        type=Path,
    )
    combine_parser.add_argument(
        "--history-input",
        required=True,
        type=Path,
    )
    combine_parser.add_argument(
        "--shard-file",
        action="append",
        required=True,
        type=Path,
    )
    combine_parser.add_argument(
        "--ledger-output",
        required=True,
        type=Path,
    )
    combine_parser.add_argument(
        "--parity-output",
        required=True,
        type=Path,
    )
    args = parser.parse_args()
    if args.command == "shard":
        result = build_shard(
            frozen_root=args.frozen_root,
            frozen_source_directory=args.frozen_source_directory,
            history_input=args.history_input,
            target_start=args.target_start,
            target_stop=args.target_stop,
            output_file=args.output_file,
        )
    else:
        result = combine_shards(
            frozen_root=args.frozen_root,
            frozen_source_directory=args.frozen_source_directory,
            history_input=args.history_input,
            shard_files=args.shard_file,
            ledger_output=args.ledger_output,
            parity_output=args.parity_output,
        )
    print(
        json.dumps(
            result,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
