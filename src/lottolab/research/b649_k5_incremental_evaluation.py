"""One-target, fixed B649 M0/M2 K5 prediction, scoring, and summary adapter.

The fixed K235 study remains the only source of method generation, ticket
quality, and official prize evaluation. This module adds durable, idempotent
single-target records around those already-accepted interfaces.
"""

from __future__ import annotations

import fcntl
import hashlib
import importlib
import json
import os
import subprocess
import tempfile
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from collections.abc import Generator as GeneratorABC
from contextlib import contextmanager
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, cast

import lottolab.research.b649_k235_output_quality as output_quality
import lottolab.research.b649_k235_shared_evaluation as shared
from lottolab.strategies.adapters.base import BetAdapterError, CausalDrawRow, InsufficientHistory

Record = dict[str, Any]
Tickets = tuple[tuple[int, ...], ...]
Generate = Callable[[str, int, tuple[CausalDrawRow, ...]], Tickets]
Clock = Callable[[], datetime]

TASK_ID = "B649_M0_M2_K5_INCREMENTAL_EVAL_R1"
GAME = "B649"
K = 5
MODELS = ("M0", "M2")
RECORD_CLASSES = (
    "SYNTHETIC_TEST",
    "HISTORICAL_DEMO",
    "LOCAL_RECORDED_UNATTESTED",
)
FIXED_SOURCE_COMMIT = "2d0130f95d168f9a0afd2f7b2015923bed947974"
FIXED_SOURCE_TREE = "bd1b7434ac16c19d0930e4ffde36322bacdf8c2f"
FIXED_SOURCE_SHA256 = {
    "src/lottolab/application/use_cases/generate_bet.py":
        "46e56fadfd2629ea5aed5fc0354499e2596a318b7bafce59d09f69ae5cf19fac",
    "src/lottolab/domain/prize_evaluation.py":
        "976c977eee7475ea9b824ff6da2725308df6eef801ae8e257497bdec67ca4228",
    "src/lottolab/research/b649_k235_output_quality.py":
        "cce887f6d365aed13a509d28b1d51ab0c527facc74f0d118be6d6069c8c01c70",
    "src/lottolab/research/b649_k235_shared_evaluation.py":
        "5b07f569888cce0458900e5375b3d28394e42fae7accd3e923ba6eaa647a6b41",
    "src/lottolab/strategies/adapters/base.py":
        "0e398185f5c0bc105d9dd4da20d9d50eec5342a40d20b6e362c71c34ce68dd0a",
    "src/lottolab/strategies/adapters/biglotto_orthogonal_5bet.py":
        "7d5e7ae430379a9521fe2eba92c025a2792469deec78cc2c50e7c479b78db92b",
    "src/lottolab/strategies/catalog.py":
        "d28ce36637e722b2456049cea8afed9906252c7a5f6b8c3d2aae30c417175eab",
    "src/lottolab/strategies/executable_registry.py":
        "9c6d2e424a61241cfa4917c47a149ebeef6c65fac5c04b11cf1256e00f399312",
}


class EvaluationError(ValueError):
    """The requested single-target operation violates its recorded contract."""


class RecordConflictError(EvaluationError):
    """A target already has a different immutable prediction or result identity."""


class MissingPredictionError(EvaluationError):
    """A score was requested for a target with no fixed prediction package."""


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value: object) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _repository_root() -> Path:
    return Path(shared.__file__).resolve().parents[3]


def _source_identity(adapters: Mapping[int, Any]) -> Record:
    root = _repository_root()
    actual: dict[str, str] = {}
    for relative, expected in FIXED_SOURCE_SHA256.items():
        path = root / relative
        if not path.is_file():
            raise EvaluationError(f"Required fixed source is missing: {relative}")
        value = _sha256(path)
        if value != expected:
            raise EvaluationError(f"Fixed source identity mismatch: {relative}")
        actual[relative] = value

    implementation_path = Path(__file__).resolve()
    cli_path = root / "tools/b649_k5_incremental_evaluation.py"
    implementation_commit = subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "HEAD"], text=True
    ).strip()
    implementation_tree = subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "HEAD^{tree}"], text=True
    ).strip()
    adapter = adapters.get(K)
    adapter_type: type[Any] | None = cast(type[Any], type(adapter)) if adapter is not None else None
    adapter_module = importlib.import_module(adapter_type.__module__) if adapter_type else None
    adapter_path_value = getattr(adapter_module, "__file__", None)
    adapter_path = (
        Path(adapter_path_value).resolve() if isinstance(adapter_path_value, str) else None
    )
    if adapter_path is not None and not adapter_path.is_relative_to(root):
        raise EvaluationError(f"M0 adapter imported outside the fixed source tree: {adapter_path}")

    return {
        "study_id": "B649_K235_SHARED_EVAL_FIRST_BATCH_R1",
        "commit": FIXED_SOURCE_COMMIT,
        "tree": FIXED_SOURCE_TREE,
        "implementation_commit": implementation_commit,
        "implementation_tree": implementation_tree,
        "fixed_component_sha256": actual,
        "incremental_adapter_sha256": _sha256(implementation_path),
        "incremental_cli_sha256": _sha256(cli_path),
        "m0_adapter_module": str(adapter_path.relative_to(root)) if adapter_path else None,
        "m0_adapter_sha256": _sha256(adapter_path) if adapter_path else None,
    }


def _validate_draw(value: object, label: str) -> tuple[str, int]:
    if type(value) is not str or not value.isascii() or not value.isdigit():
        raise EvaluationError(f"{label} must be an ASCII numeric draw id")
    parsed = int(value)
    if parsed < 1:
        raise EvaluationError(f"{label} must be positive")
    return value, parsed


def _validate_date(value: object, label: str) -> tuple[str, date]:
    if type(value) is not str:
        raise EvaluationError(f"{label} must be an ISO date string")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as error:
        raise EvaluationError(f"{label} must be an ISO date string") from error
    if parsed.isoformat() != value:
        raise EvaluationError(f"{label} must use canonical YYYY-MM-DD form")
    return value, parsed


def _validate_record_class(record_class: str) -> str:
    if record_class not in RECORD_CLASSES:
        raise EvaluationError(f"Unsupported record class: {record_class}")
    return record_class


def prepare_strict_history(
    snapshot: Sequence[Mapping[str, Any]], target_draw: str, target_date: str
) -> list[Record]:
    """Project a full snapshot to model inputs strictly before both target axes.

    The returned rows contain only draw id, date, and main numbers. Target and
    future outcomes, including special numbers and provenance, never cross the
    generation boundary.
    """
    _, target_number = _validate_draw(target_draw, "target_draw")
    _, target_day = _validate_date(target_date, "target_date")
    history: list[Record] = []
    seen: set[str] = set()
    last_draw = 0
    last_date: date | None = None
    for row in snapshot:
        draw, draw_number = _validate_draw(row.get("draw"), "snapshot draw")
        day_text, day = _validate_date(row.get("date"), f"snapshot date for {draw}")
        if draw_number >= target_number or day >= target_day:
            continue
        if draw in seen or draw_number <= last_draw or (last_date is not None and day <= last_date):
            raise EvaluationError("Pre-target history must be unique and chronologically ordered")
        numbers_value = row.get("numbers")
        if not isinstance(numbers_value, (list, tuple)):
            raise EvaluationError(f"Invalid B649 main numbers in pre-target draw {draw}")
        numbers: Sequence[Any] = cast(Sequence[Any], numbers_value)
        if (
            len(numbers) != 6
            or any(type(number) is not int or not 1 <= number <= 49 for number in numbers)
            or len(set(numbers)) != 6
        ):
            raise EvaluationError(f"Invalid B649 main numbers in pre-target draw {draw}")
        history.append(cast(Record, {"draw": draw, "date": day_text, "numbers": list(numbers)}))
        seen.add(draw)
        last_draw = draw_number
        last_date = day
    return history


def read_jsonl(path: Path) -> list[Record]:
    rows: list[Record] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as error:
            raise EvaluationError(f"Invalid JSONL at line {line_number}") from error
        if not isinstance(row, dict):
            raise EvaluationError(f"Expected a JSON object at line {line_number}")
        rows.append(cast(Record, row))
    return rows


def _model_identity(model: str) -> Record:
    config = json.loads(shared.canonical(shared.MODEL_CONFIGS[model]))
    identity: Record = {
        "model_id": model,
        "K": K,
        "fixed_config": config,
        "model_config_hash": shared.model_hash(model),
    }
    if model == "M0":
        identity.update(
            {
                "strategy_id": shared.BASELINES[K],
                "parameters": "native constructors, no overrides",
                "selection": "R1 frozen validation-selected identity; no reselection",
                "seed": "native causal-history seed protocol; no retries",
            }
        )
    else:
        identity["parameters"] = {
            "half_life_draws": 50,
            "max_history": 750,
            "initial_level": 6 / 49,
            "order": "oldest to newest",
        }
    return identity


def _clock_text(clock: Clock) -> str:
    value = clock()
    if value.tzinfo is None or value.utcoffset() is None:
        raise EvaluationError("Internal clock must return a timezone-aware datetime")
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _default_clock() -> datetime:
    return datetime.now(UTC)


def _safe_json_value(value: Any) -> Any:
    try:
        return json.loads(json.dumps(value, ensure_ascii=False))
    except (TypeError, ValueError):
        return {"unserializable_type": type(value).__name__, "repr": repr(value)[:300]}


def _generate_method(
    model: str,
    history: tuple[CausalDrawRow, ...],
    generator: Generate,
    adapter_error: str | None,
) -> Record:
    tickets: Any = []
    status = "OK"
    reason = ""
    try:
        if model == "M0" and adapter_error:
            raise RuntimeError(adapter_error)
        tickets = generator(model, K, history)
    except InsufficientHistory as error:
        status, reason = "UNAVAILABLE", f"{type(error).__name__}: {error}"
    except BetAdapterError as error:
        status, reason = "STRATEGY_REJECTED", f"{type(error).__name__}: {error}"
    except Exception as error:  # retain a method-specific technical attempt
        status, reason = "TECHNICAL_FAILURE", f"{type(error).__name__}: {error}"

    quality = output_quality.evaluate_candidate_quality(tickets, K).canonical_dict()
    if status == "OK" and not quality["is_valid"]:
        status = "INVALID_TICKETS"
        reason = "; ".join(quality["rejection_reasons"])
    serializable_tickets = _safe_json_value(tickets)
    return {
        "method_identity": _model_identity(model),
        "generation_status": status,
        "failure_reason": reason,
        "generated_tickets": serializable_tickets,
        "ticket_quality": quality,
        "history_length": len(history),
        "actual_history_cutoff": (
            {"draw": history[-1].draw, "date": history[-1].date} if history else None
        ),
        "effective_window_lengths": shared.effective_windows(model, K, len(history)),
    }


def prediction_path(output_root: Path, record_class: str, target_draw: str) -> Path:
    _validate_record_class(record_class)
    draw, _ = _validate_draw(target_draw, "target_draw")
    return output_root / record_class / "predictions" / f"{draw}.json"


def score_path(output_root: Path, record_class: str, target_draw: str) -> Path:
    _validate_record_class(record_class)
    draw, _ = _validate_draw(target_draw, "target_draw")
    return output_root / record_class / "scores" / f"{draw}.json"


@contextmanager
def _registry_lock(output_root: Path, record_class: str) -> GeneratorABC[None]:
    mode_root = output_root / _validate_record_class(record_class)
    mode_root.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(mode_root / ".registry.lock", os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def _write_json_atomic(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def predict_compare(
    snapshot: Sequence[Mapping[str, Any]],
    *,
    target_draw: str,
    target_date: str,
    output_root: Path,
    record_class: str,
    generator_fn: Generate | None = None,
    clock: Clock = _default_clock,
) -> Record:
    """Create or idempotently return one fixed M0/M2 K5 prediction package."""
    _validate_record_class(record_class)
    draw, _ = _validate_draw(target_draw, "target_draw")
    day_text, _ = _validate_date(target_date, "target_date")
    history_rows = prepare_strict_history(snapshot, draw, day_text)
    history_hash = digest(history_rows)
    target = {"draw": draw, "date": day_text}
    causal_rows = shared.causal_history(history_rows, target)

    adapters: Mapping[int, Any] = {}
    adapter_error: str | None = None
    if generator_fn is None:
        try:
            adapters = shared.native_adapters()
        except Exception as error:
            adapter_error = f"{type(error).__name__}: {error}"
        generator_fn = shared.generator(dict(adapters))
    source = _source_identity(adapters)
    identities = {model: _model_identity(model) for model in MODELS}
    request_identity = {
        "game": GAME,
        "target": {"draw": draw, "date": day_text},
        "record_class": record_class,
        "history_sha256": history_hash,
        "methods": identities,
        "source_identity": source,
    }
    destination = prediction_path(output_root, record_class, draw)

    with _registry_lock(output_root, record_class):
        if destination.exists():
            existing = json.loads(destination.read_text(encoding="utf-8"))
            if existing.get("request_identity") != request_identity:
                raise RecordConflictError(
                    f"Prediction conflict for target {draw}: input or fixed identity changed"
                )
            return existing

        methods = {
            model: _generate_method(model, causal_rows, generator_fn, adapter_error)
            for model in MODELS
        }
        package: Record = {
            "schema": f"{TASK_ID}.PREDICTION.V1",
            "classification": record_class,
            "game": GAME,
            "target": target,
            "created_at": _clock_text(clock),
            "request_identity": request_identity,
            "input_identity": {
                "history_sha256": history_hash,
                "history_row_count": len(causal_rows),
                "actual_history_cutoff": (
                    {"draw": causal_rows[-1].draw, "date": causal_rows[-1].date}
                    if causal_rows
                    else None
                ),
            },
            "methods": methods,
        }
        _write_json_atomic(destination, package)
        return package


def _normalize_result(result: Mapping[str, Any], prediction: Mapping[str, Any]) -> Record:
    target = prediction["target"]
    draw, _ = _validate_draw(result.get("draw"), "result draw")
    day_text, _ = _validate_date(result.get("date"), "result date")
    if draw != target["draw"] or day_text != target["date"]:
        raise EvaluationError("Official result target does not match the fixed prediction")
    numbers_value = result.get("numbers")
    special = result.get("special")
    if not isinstance(numbers_value, (list, tuple)):
        raise EvaluationError("Official result has invalid B649 numbers")
    numbers: Sequence[Any] = cast(Sequence[Any], numbers_value)
    if (
        len(numbers) != 6
        or any(type(number) is not int or not 1 <= number <= 49 for number in numbers)
        or len(set(numbers)) != 6
        or type(special) is not int
        or not 1 <= special <= 49
        or special in numbers
    ):
        raise EvaluationError("Official result has invalid B649 numbers")
    version = result.get("result_version")
    if version is not None and (type(version) is not str or not version):
        raise EvaluationError("result_version must be a non-empty string when supplied")
    identity: Record = {
        "draw": draw,
        "date": day_text,
        "numbers": list(numbers),
        "special": special,
        "result_version": version,
    }
    return {**identity, "result_sha256": digest(identity)}


def score_fixed_prediction(
    *,
    target_draw: str,
    output_root: Path,
    record_class: str,
    official_result: Mapping[str, Any] | None = None,
    clock: Clock = _default_clock,
) -> Record:
    """Score only the stored ticket package; this path never calls a generator."""
    _validate_record_class(record_class)
    draw, _ = _validate_draw(target_draw, "target_draw")
    prediction_file = prediction_path(output_root, record_class, draw)
    destination = score_path(output_root, record_class, draw)

    with _registry_lock(output_root, record_class):
        if not prediction_file.is_file():
            raise MissingPredictionError(f"No registered prediction package for target {draw}")
        prediction = json.loads(prediction_file.read_text(encoding="utf-8"))
        if prediction.get("classification") != record_class or prediction.get("game") != GAME:
            raise EvaluationError("Prediction package classification or game mismatch")
        if prediction.get("target", {}).get("draw") != draw:
            raise EvaluationError("Prediction path target mismatch")
        normalized_result = (
            _normalize_result(official_result, prediction) if official_result is not None else None
        )
        previous: Record | None = None
        if destination.exists():
            stored_record: Record = json.loads(destination.read_text(encoding="utf-8"))
            previous = stored_record
            if (
                stored_record.get("classification") != record_class
                or stored_record.get("target_draw") != draw
            ):
                raise EvaluationError("Stored score identity mismatch")
            previous_result = stored_record.get("official_result")
            if previous_result is not None:
                if normalized_result is None:
                    return stored_record
                if previous_result.get("result_sha256") != normalized_result["result_sha256"]:
                    raise RecordConflictError(f"Result-version conflict for target {draw}")
                return stored_record
            if normalized_result is None:
                return stored_record

        if normalized_result is None:
            scored_at = None
            result_payload = None
            score_status = "PENDING"
            methods = {
                model: {
                    "generation_status": prediction["methods"][model]["generation_status"],
                    "ticket_quality": prediction["methods"][model]["ticket_quality"],
                    "result_status": "PENDING",
                    "delivery_failure": prediction["methods"][model]["generation_status"] != "OK",
                    "ticket_evaluations": None,
                    "successful": None,
                    "failure_reason": prediction["methods"][model]["failure_reason"],
                }
                for model in MODELS
            }
        else:
            scored_at = _clock_text(clock)
            result_payload = normalized_result
            score_status = "SCORED"
            methods = {}
            for model in MODELS:
                method = prediction["methods"][model]
                failed_delivery = (
                    method["generation_status"] != "OK"
                    or not method["ticket_quality"]["is_valid"]
                )
                if failed_delivery:
                    methods[model] = {
                        "generation_status": method["generation_status"],
                        "ticket_quality": method["ticket_quality"],
                        "result_status": "DELIVERY_FAILURE",
                        "delivery_failure": True,
                        "ticket_evaluations": None,
                        "successful": False,
                        "failure_reason": method["failure_reason"],
                    }
                    continue
                tickets = tuple(tuple(ticket) for ticket in method["generated_tickets"])
                evaluations, successful = shared.score_tickets(tickets, normalized_result)
                methods[model] = {
                    "generation_status": method["generation_status"],
                    "ticket_quality": method["ticket_quality"],
                    "result_status": "SCORED",
                    "delivery_failure": False,
                    "ticket_evaluations": evaluations,
                    "successful": successful,
                    "failure_reason": "",
                }

        score_record: Record = {
            "schema": f"{TASK_ID}.SCORE.V1",
            "classification": record_class,
            "game": GAME,
            "target_draw": draw,
            "target_date": prediction["target"]["date"],
            "score_status": score_status,
            "created_at": previous["created_at"] if previous is not None else _clock_text(clock),
            "scored_at": scored_at,
            "official_result": result_payload,
            "methods": methods,
        }
        _write_json_atomic(destination, score_record)
        return score_record


def _summary_method_counts(packages: Sequence[Record], model: str) -> Record:
    statuses: Counter[str] = Counter(
        str(package["methods"][model]["generation_status"]) for package in packages
    )
    return {
        "generation_status_counts": dict(sorted(statuses.items())),
        "technical_failure_n": statuses["TECHNICAL_FAILURE"],
        "unavailable_n": statuses["UNAVAILABLE"],
        "strategy_rejected_n": statuses["STRATEGY_REJECTED"],
        "invalid_ticket_n": statuses["INVALID_TICKETS"],
        "delivery_failure_n": sum(count for status, count in statuses.items() if status != "OK"),
    }


def build_summary(output_root: Path, record_class: str) -> Record:
    """Aggregate registered one-target records for exactly one classification."""
    _validate_record_class(record_class)
    prediction_dir = output_root / record_class / "predictions"
    score_dir = output_root / record_class / "scores"
    prediction_files = sorted(
        prediction_dir.glob("*.json"),
        key=lambda path: int(path.stem) if path.stem.isdigit() else -1,
    )
    packages: list[Record] = []
    score_by_draw: dict[str, Record] = {}
    pending_n = 0
    known_n = 0
    for path in prediction_files:
        if not path.stem.isascii() or not path.stem.isdigit():
            raise EvaluationError(f"Unexpected prediction filename: {path.name}")
        package = json.loads(path.read_text(encoding="utf-8"))
        if (
            package.get("classification") != record_class
            or package.get("game") != GAME
            or package.get("target", {}).get("draw") != path.stem
        ):
            raise EvaluationError(f"Prediction identity mismatch: {path}")
        packages.append(package)
        score_file = score_dir / path.name
        if not score_file.is_file():
            pending_n += 1
            continue
        score = json.loads(score_file.read_text(encoding="utf-8"))
        if (
            score.get("classification") != record_class
            or score.get("target_draw") != path.stem
            or score.get("target_date") != package.get("target", {}).get("date")
        ):
            raise EvaluationError(f"Score identity mismatch: {score_file}")
        if score.get("score_status") == "PENDING":
            pending_n += 1
        elif score.get("score_status") == "SCORED":
            known_n += 1
            score_by_draw[path.stem] = score
        else:
            raise EvaluationError(f"Unknown score status in {score_file}")

    method_summaries = {model: _summary_method_counts(packages, model) for model in MODELS}
    successful: dict[str, list[bool]] = {model: [] for model in MODELS}
    qualified_successful: dict[str, list[bool]] = {model: [] for model in MODELS}
    qualified_pairs = 0
    pair_states: list[tuple[bool, bool, bool]] = []
    qualified_pair_states: list[tuple[bool, bool]] = []
    for _draw, score in score_by_draw.items():
        values: dict[str, bool] = {}
        qualified: dict[str, bool] = {}
        for model in MODELS:
            score_method = score["methods"][model]
            values[model] = score_method["successful"] is True
            successful[model].append(values[model])
            qualified[model] = score_method["result_status"] == "SCORED"
            if qualified[model]:
                qualified_successful[model].append(values[model])
        pair_states.append((values["M0"], values["M2"], not (qualified["M0"] and qualified["M2"])))
        if qualified["M0"] and qualified["M2"]:
            qualified_pairs += 1
            qualified_pair_states.append((values["M0"], values["M2"]))

    b = sum(m2 and not m0 for m0, m2, _ in pair_states)
    c = sum(m0 and not m2 for m0, m2, _ in pair_states)
    both = sum(m0 and m2 for m0, m2, _ in pair_states)
    neither = len(pair_states) - b - c - both
    delivery_failed_pairs = sum(failed for _, _, failed in pair_states)
    qualified_b = sum(m2 and not m0 for m0, m2 in qualified_pair_states)
    qualified_c = sum(m0 and not m2 for m0, m2 in qualified_pair_states)
    qualified_both = sum(m0 and m2 for m0, m2 in qualified_pair_states)
    qualified_neither = qualified_pairs - qualified_b - qualified_c - qualified_both

    def rate(values: Sequence[bool]) -> float | None:
        return sum(values) / len(values) if values else None

    return {
        "schema": f"{TASK_ID}.SUMMARY.V1",
        "classification": record_class,
        "game": GAME,
        "K": K,
        "event": "At least one ticket wins an official BIG_LOTTO prize under the shared scorer",
        "registered_target_n": len(packages),
        "pending_result_n": pending_n,
        "known_result_n": known_n,
        "methods": {
            model: {
                **method_summaries[model],
                "usable_success_n": sum(successful[model]),
                "usable_hit_rate": rate(successful[model]),
            }
            for model in MODELS
        },
        "paired_known_results": {
            "denominator": len(pair_states),
            "both_success_n": both,
            "both_unsuccessful_n": neither,
            "m2_only_success_b": b,
            "m0_only_success_c": c,
            "difference_percentage_points": 100 * (b - c) / len(pair_states)
            if pair_states
            else None,
            "at_least_one_delivery_failure_n": delivery_failed_pairs,
        },
        "qualified_pair_supplement": {
            "denominator": qualified_pairs,
            "both_success_n": qualified_both,
            "both_unsuccessful_n": qualified_neither,
            "m2_only_success_b": qualified_b,
            "m0_only_success_c": qualified_c,
            "difference_percentage_points": 100 * (qualified_b - qualified_c) / qualified_pairs
            if qualified_pairs
            else None,
            "M0_hit_rate": rate(qualified_successful["M0"]),
            "M2_hit_rate": rate(qualified_successful["M2"]),
        },
        "delivery_failures_remain_distinct_from_legal_misses": True,
        "decision": None,
    }


def summarize_and_write(
    output_root: Path, record_class: str, clock: Clock = _default_clock
) -> Record:
    with _registry_lock(output_root, record_class):
        summary = build_summary(output_root, record_class)
        summary["generated_at"] = _clock_text(clock)
        _write_json_atomic(output_root / record_class / "summary.json", summary)
        return summary


def load_official_result(path: Path) -> Record:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise EvaluationError(f"Invalid JSON result file: {path}") from error
    if not isinstance(value, dict):
        raise EvaluationError("Official result file must contain one JSON object")
    return cast(Record, value)
