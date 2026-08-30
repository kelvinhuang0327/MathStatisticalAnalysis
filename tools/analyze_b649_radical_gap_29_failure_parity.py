"""Attribute the 29 sealed B649 Radical-gap failures without replaying K2.

The analyzer verifies the existing failure-taxonomy result and its sealed replay
authority, reconstructs only the latest 300 causal draws required by each failed
target, and executes both the retained wave-31 reference and the current adapter.
It never opens a database and never changes strategy semantics.
"""

# pyright: reportPrivateUsage=false

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any, Final, Literal, cast

import lottolab.application.legacy_source_native_portfolios_wave31 as reference_module
import lottolab.strategies.adapters.biglotto_radical_gap as adapter_module
from lottolab.application.legacy_history_native_portfolios import LegacyHistoryDraw
from lottolab.application.legacy_source_native_portfolios_wave31 import (
    RADICAL_BACKTEST_METHOD_ID,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE31_METHOD,
    LegacySourceNativeWave31Request,
    LegacySourceNativeWave31SourceError,
    generate_legacy_source_native_wave31_portfolio,
)
from lottolab.application.strategy_preserving_20_ticket import Ticket
from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import CausalDrawRow, InvalidOutput
from lottolab.strategies.adapters.biglotto_radical_gap import (
    BigLottoRadicalGapBacktestAdapter,
)

TASK_ID = "B649_RADICAL_GAP_29_FAILURE_PARITY_ATTRIBUTION_R1"
SCHEMA_VERSION = "B649_RADICAL_GAP_29_FAILURE_PARITY_ATTRIBUTION_V1"
STRATEGY_ID = "legacy_biglotto__backtest_radical_strategy__e54cc0812bc6"
SOURCE_SHA256 = "e54cc0812bc6fff14a259282a37821810d264c023c4fb87517305b511db08fd9"
CURRENT_ADAPTER = (
    "lottolab.strategies.adapters.biglotto_radical_gap:"
    "BigLottoRadicalGapBacktestAdapter"
)
RETAINED_REFERENCE = (
    "lottolab.application.legacy_source_native_portfolios_wave31:"
    "generate_legacy_source_native_wave31_portfolio"
)
TAXONOMY_SOURCE_HEAD = "1c171c9fbe6398a6af36425cf61d1ba3e6f27532"
TAXONOMY_SOURCE_TREE = "ccb336ed3538834f922db58d4d1b687bc72a3dbc"
TAXONOMY_RESULT_SHA256 = (
    "d70359c611a49f2fb414767145531da35d0ebc33532e5f36d16631fb89901856"
)
TAXONOMY_SCHEMA_VERSION = "B649_K2_FIXED_UNIVERSE_FAILURE_TAXONOMY_V1"
SEALED_RUN_ID = "B649_K2_K3_EXACT_NATIVE_FULL_REPLAY_R1"
SEALED_REPLAY_SOURCE_HEAD = "85d2b4578d437b66bd015c60dd1f9bdc8404e755"
SEALED_REPLAY_SOURCE_TREE = "c6341c36ca210e02b08bac66ff98b7c8be1fc95a"
SEALED_ROW_SCHEMA_VERSION = "B649_EXACT_NATIVE_TARGET_EVIDENCE_V1"
EXPECTED_RADICAL_ROW_COUNT = 750
EXPECTED_FAILURE_COUNT = 29
SOURCE_HISTORY_LIMIT = 300
SEALED_FAILURE_REASON = (
    "InvalidOutput: "
    f"{STRATEGY_ID}: frozen donor emitted fewer than six legal candidates"
)
REFERENCE_CLOSURE_REASON = "FROZEN_SOURCE_EMITTED_INVALID_NATIVE_TICKET"
ADAPTER_CLOSURE_REASON = (
    f"{STRATEGY_ID}: frozen donor emitted fewer than six legal candidates"
)
ENGINE_METHODS = ("deviation", "markov", "frequency")
POSITIONAL_COMPONENTS = (
    ("GAP_01_19", range(1, 20)),
    ("GAP_20_29", range(20, 30)),
)

DONOR_FAITHFUL_SOURCE_CLOSURE = "DONOR_FAITHFUL_SOURCE_CLOSURE"
PORT_REGRESSION = "PORT_REGRESSION"
SOURCE_AUTHORITY_UNRESOLVED = "SOURCE_AUTHORITY_UNRESOLVED"
CLASSIFICATIONS = (
    DONOR_FAITHFUL_SOURCE_CLOSURE,
    PORT_REGRESSION,
    SOURCE_AUTHORITY_UNRESOLVED,
)

EXPECTED_FAILURE_TARGETS = (
    "111000108",
    "112000116",
    "113000024",
    "113000025",
    "113000027",
    "113000028",
    "113000046",
    "113000068",
    "113000088",
    "113000102",
    "113000103",
    "113000109",
    "113000110",
    "113000114",
    "114000006",
    "114000050",
    "114000054",
    "114000058",
    "114000059",
    "114000060",
    "114000065",
    "114000077",
    "114000078",
    "114000096",
    "114000108",
    "115000019",
    "115000039",
    "115000062",
    "115000065",
)

EXPECTED_AUTHORITY_FILES: Final[dict[str, tuple[str, int]]] = {
    "promotion_provenance.json": (
        "63057f07c33d92c18bfc4f35975407624ea6464778bfb7d110576f4589a36632",
        1_182,
    ),
    "ranking.json": (
        "3c09cf4791ac55c83bd7556d4b947cb1f80b762abf767b6b83f075c9d344753f",
        74_122,
    ),
    "sealed_manifest.json": (
        "9b9a9ca35252ff51bf60cf8e04a4e1e0b182a07ca34e2c2f8777f5d587445495",
        63_279,
    ),
    "target_evidence.jsonl": (
        "f4ee7bcd2900c6c066b6aa0255031c97c1ca1a248c605ce68a46f62bfe7820f0",
        52_228_568,
    ),
}

DEFAULT_TAXONOMY_RESULT = (
    Path.home()
    / "VibeCoding-WorkSpace"
    / ".worktrees"
    / "MathStatisticalAnalysis"
    / "B649_K2_FIXED_UNIVERSE_FAILURE_TAXONOMY_R1"
    / "docs"
    / "research"
    / "matrix-native-results"
    / "b649-k2-fixed-universe-failure-taxonomy-r1-result.json"
)
DEFAULT_AUTHORITY_DIRECTORY = (
    Path.home()
    / "Library"
    / "Application Support"
    / "LottoLab"
    / "authorities"
    / "big_lotto"
    / "exact_native_k2_k3"
)
OUTPUT_JSON = Path(
    "docs/research/matrix-native-results/"
    "b649-radical-gap-29-failure-parity-r1-result.json"
)
OUTPUT_REPORT = Path("docs/research/b649-radical-gap-29-failure-parity-r1.md")

JsonObject = dict[str, Any]
OutcomeStatus = Literal["EMITTED", "CLOSED", "UNRESOLVED"]
ComponentStatus = Literal["OK", "ERROR"]


class ParityAttributionError(ValueError):
    """The sealed authority or parity attribution cannot be trusted."""


@dataclass(frozen=True, slots=True)
class SealedTargetRow:
    """One Radical-gap row retained in the sealed K2/K3 target evidence."""

    target_draw_number: str
    target_draw_date: str
    main_numbers: Ticket
    special_number: int
    replay_status: str
    reason: str | None
    causal_cutoff_draw_number: str
    causal_cutoff_date: str
    causal_history_length: int
    causal_history_fingerprint: str

    @property
    def chronological_key(self) -> tuple[date, int]:
        try:
            return date.fromisoformat(self.target_draw_date), int(self.target_draw_number)
        except ValueError as exc:
            raise ParityAttributionError(
                "SEALED_RADICAL_FAILURE_AUTHORITY_UNAVAILABLE: invalid target identity "
                f"{self.target_draw_number}/{self.target_draw_date}"
            ) from exc

    def causal_row(self) -> CausalDrawRow:
        return CausalDrawRow(
            draw=self.target_draw_number,
            date=self.target_draw_date,
            numbers=self.main_numbers,
        )

    def legacy_row(self) -> LegacyHistoryDraw:
        return LegacyHistoryDraw(
            draw_number=self.target_draw_number,
            numbers=self.main_numbers,
        )


@dataclass(frozen=True, slots=True)
class ComponentObservation:
    """Normalized output or failure from one frozen Unified component."""

    method_name: str
    status: ComponentStatus
    ticket: tuple[int, ...] | None
    error_type: str | None
    error_message: str | None

    @property
    def effective_key(self) -> tuple[str, tuple[int, ...] | None]:
        return self.status, self.ticket

    def canonical_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class PathObservation:
    """Normalized retained-reference or current-adapter execution path."""

    components: tuple[ComponentObservation, ...]
    candidate_pools: tuple[tuple[int, ...], ...]
    outcome_status: OutcomeStatus
    tickets: tuple[tuple[int, ...], ...] | None
    closure_reason: str | None
    exception_type: str | None
    exception_message: str | None

    def canonical_dict(self) -> dict[str, object]:
        return {
            "candidate_pools": [list(pool) for pool in self.candidate_pools],
            "closure_reason": self.closure_reason,
            "components": [component.canonical_dict() for component in self.components],
            "exception_message": self.exception_message,
            "exception_type": self.exception_type,
            "outcome_status": self.outcome_status,
            "tickets": (
                None if self.tickets is None else [list(ticket) for ticket in self.tickets]
            ),
        }


def _require_object(value: object, locator: str) -> JsonObject:
    if not isinstance(value, dict):
        raise ParityAttributionError(
            f"SEALED_RADICAL_FAILURE_AUTHORITY_UNAVAILABLE: {locator} must be an object"
        )
    return cast(JsonObject, value)


def _require_list(value: object, locator: str) -> list[Any]:
    if not isinstance(value, list):
        raise ParityAttributionError(
            f"SEALED_RADICAL_FAILURE_AUTHORITY_UNAVAILABLE: {locator} must be an array"
        )
    return cast(list[Any], value)


def _require_str(value: object, locator: str) -> str:
    if not isinstance(value, str) or not value:
        raise ParityAttributionError(
            f"SEALED_RADICAL_FAILURE_AUTHORITY_UNAVAILABLE: "
            f"{locator} must be a non-empty string"
        )
    return value


def _require_int(value: object, locator: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ParityAttributionError(
            f"SEALED_RADICAL_FAILURE_AUTHORITY_UNAVAILABLE: {locator} must be an integer"
        )
    return value


def _optional_str(value: object, locator: str) -> str | None:
    if value is None:
        return None
    return _require_str(value, locator)


def canonical_json_bytes(payload: Mapping[str, object]) -> bytes:
    """Serialize one deterministic, human-readable JSON artifact."""

    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ).rstrip("\n")
    return f"{serialized}\n".encode()


def sha256_file(task_file: Path) -> str:
    digest = hashlib.sha256()
    with task_file.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_digest(observed: str, expected: str, locator: str) -> None:
    """Fail closed on any source-authority digest mismatch."""

    if observed != expected:
        raise ParityAttributionError(
            "SEALED_RADICAL_FAILURE_AUTHORITY_UNAVAILABLE: "
            f"SHA-256 mismatch for {locator}: expected {expected}, observed {observed}"
        )


def require_sha256_file(task_file: Path, expected: str) -> dict[str, int | str]:
    if not task_file.is_file():
        raise ParityAttributionError(
            f"SEALED_RADICAL_FAILURE_AUTHORITY_UNAVAILABLE: missing {task_file}"
        )
    observed = sha256_file(task_file)
    require_digest(observed, expected, str(task_file))
    return {"sha256": observed, "size_bytes": task_file.stat().st_size}


def require_exact_failure_targets(targets: Sequence[str]) -> tuple[str, ...]:
    """Require the exact ordered 29-target taxonomy set."""

    observed = tuple(targets)
    if observed != EXPECTED_FAILURE_TARGETS:
        raise ParityAttributionError(
            "SEALED_RADICAL_FAILURE_AUTHORITY_UNAVAILABLE: exact 29-target accounting "
            f"changed: expected {EXPECTED_FAILURE_TARGETS}, observed {observed}"
        )
    return observed


def _load_json_object(task_file: Path) -> JsonObject:
    try:
        parsed: object = json.loads(task_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ParityAttributionError(
            f"SEALED_RADICAL_FAILURE_AUTHORITY_UNAVAILABLE: invalid JSON {task_file}"
        ) from exc
    return _require_object(parsed, str(task_file))


def verify_taxonomy_result(task_file: Path) -> tuple[str, ...]:
    """Verify the exact existing taxonomy artifact and return its Radical targets."""

    require_sha256_file(task_file, TAXONOMY_RESULT_SHA256)
    payload = _load_json_object(task_file)
    if payload.get("schema_version") != TAXONOMY_SCHEMA_VERSION:
        raise ParityAttributionError(
            "SEALED_RADICAL_FAILURE_AUTHORITY_UNAVAILABLE: taxonomy schema changed"
        )
    source_identity = _require_object(payload.get("source_identity"), "source_identity")
    expected_source_values = (
        (
            source_identity.get("sealed_replay_source_head"),
            SEALED_REPLAY_SOURCE_HEAD,
            "sealed replay source HEAD",
        ),
        (
            source_identity.get("sealed_replay_source_tree"),
            SEALED_REPLAY_SOURCE_TREE,
            "sealed replay source tree",
        ),
        (source_identity.get("run_id"), SEALED_RUN_ID, "sealed replay run ID"),
    )
    for observed, expected, locator in expected_source_values:
        if observed != expected:
            raise ParityAttributionError(
                "SEALED_RADICAL_FAILURE_AUTHORITY_UNAVAILABLE: "
                f"{locator} changed: expected {expected}, observed {observed}"
            )

    authority_files = _require_object(
        source_identity.get("authority_files"), "source_identity.authority_files"
    )
    for name, (expected_sha256, expected_size) in EXPECTED_AUTHORITY_FILES.items():
        details = _require_object(authority_files.get(name), f"authority_files.{name}")
        if details.get("sha256") != expected_sha256 or details.get("size_bytes") != expected_size:
            raise ParityAttributionError(
                "SEALED_RADICAL_FAILURE_AUTHORITY_UNAVAILABLE: "
                f"taxonomy provenance changed for {name}"
            )

    taxonomy = _require_object(payload.get("taxonomy"), "taxonomy")
    matrix = _require_list(
        taxonomy.get("per_strategy_failure_matrix"),
        "taxonomy.per_strategy_failure_matrix",
    )
    matching: list[JsonObject] = []
    for raw_value in matrix:
        value = _require_object(cast(object, raw_value), "per_strategy_failure_matrix row")
        if value.get("strategy_id") == STRATEGY_ID:
            matching.append(value)
    if len(matching) != 1:
        raise ParityAttributionError(
            "SEALED_RADICAL_FAILURE_AUTHORITY_UNAVAILABLE: Radical strategy row changed"
        )
    radical = matching[0]
    if radical.get("execution_failure_count") != EXPECTED_FAILURE_COUNT:
        raise ParityAttributionError(
            "SEALED_RADICAL_FAILURE_AUTHORITY_UNAVAILABLE: expected 29 Radical failures"
        )
    reasons = _require_object(radical.get("failure_reason_counts"), "failure_reason_counts")
    if reasons != {SEALED_FAILURE_REASON: EXPECTED_FAILURE_COUNT}:
        raise ParityAttributionError(
            "SEALED_RADICAL_FAILURE_AUTHORITY_UNAVAILABLE: sealed failure reason changed"
        )
    raw_targets = _require_list(radical.get("failure_targets"), "failure_targets")
    return require_exact_failure_targets(
        tuple(_require_str(value, "failure target") for value in raw_targets)
    )


def verify_authority_files(directory: Path) -> dict[str, dict[str, int | str]]:
    """Hash- and size-verify all files pinned by the existing taxonomy."""

    details_by_name: dict[str, dict[str, int | str]] = {}
    for name in sorted(EXPECTED_AUTHORITY_FILES):
        expected_sha256, expected_size = EXPECTED_AUTHORITY_FILES[name]
        details = require_sha256_file(directory / name, expected_sha256)
        if details["size_bytes"] != expected_size:
            raise ParityAttributionError(
                "SEALED_RADICAL_FAILURE_AUTHORITY_UNAVAILABLE: "
                f"size mismatch for {directory / name}"
            )
        details_by_name[name] = details
    return details_by_name


def _validate_authority_contract(directory: Path) -> tuple[str, ...]:
    provenance = _load_json_object(directory / "promotion_provenance.json")
    manifest = _load_json_object(directory / "sealed_manifest.json")
    expected_values = (
        (provenance.get("source_head"), SEALED_REPLAY_SOURCE_HEAD, "provenance HEAD"),
        (provenance.get("source_tree"), SEALED_REPLAY_SOURCE_TREE, "provenance tree"),
        (provenance.get("replay_rows"), 28_500, "provenance replay rows"),
        (manifest.get("run_id"), SEALED_RUN_ID, "manifest run ID"),
    )
    for observed, expected, locator in expected_values:
        if observed != expected:
            raise ParityAttributionError(
                "SEALED_RADICAL_FAILURE_AUTHORITY_UNAVAILABLE: "
                f"{locator} changed: expected {expected}, observed {observed}"
            )
    source = _require_object(manifest.get("source"), "manifest.source")
    if (
        source.get("head") != SEALED_REPLAY_SOURCE_HEAD
        or source.get("tree") != SEALED_REPLAY_SOURCE_TREE
        or source.get("status") != "clean"
    ):
        raise ParityAttributionError(
            "SEALED_RADICAL_FAILURE_AUTHORITY_UNAVAILABLE: manifest source changed"
        )
    draw_authority = _require_object(manifest.get("draw_authority"), "draw_authority")
    if (
        draw_authority.get("sha256_before")
        != provenance.get("draw_authority_sha256")
        or draw_authority.get("sha256_after")
        != provenance.get("draw_authority_sha256")
        or draw_authority.get("draw_payload_sha256")
        != "781e018d69da3ede8ed47e40dee70b79c1173f9ca64adeefcb4457fe135e125c"
    ):
        raise ParityAttributionError(
            "SEALED_RADICAL_FAILURE_AUTHORITY_UNAVAILABLE: draw authority identity changed"
        )
    windows = _require_object(manifest.get("target_windows"), "target_windows")
    recent_750 = _require_object(windows.get("RECENT_750"), "target_windows.RECENT_750")
    raw_targets = _require_list(recent_750.get("draw_numbers"), "RECENT_750.draw_numbers")
    targets = tuple(_require_str(value, "RECENT_750 target") for value in raw_targets)
    if len(targets) != EXPECTED_RADICAL_ROW_COUNT or len(set(targets)) != len(targets):
        raise ParityAttributionError(
            "SEALED_RADICAL_FAILURE_AUTHORITY_UNAVAILABLE: RECENT_750 target set changed"
        )
    return targets


def _parse_ticket(value: object, locator: str) -> Ticket:
    raw = _require_list(value, locator)
    if len(raw) != 6 or not all(type(number) is int for number in raw):
        raise ParityAttributionError(
            f"SEALED_RADICAL_FAILURE_AUTHORITY_UNAVAILABLE: invalid ticket at {locator}"
        )
    numbers = cast(list[int], raw)
    ticket = cast(Ticket, tuple(numbers))
    if (
        ticket != tuple(sorted(ticket))
        or len(set(ticket)) != 6
        or any(not 1 <= number <= 49 for number in ticket)
    ):
        raise ParityAttributionError(
            f"SEALED_RADICAL_FAILURE_AUTHORITY_UNAVAILABLE: invalid ticket at {locator}"
        )
    return ticket


def _parse_sealed_row(payload: JsonObject) -> SealedTargetRow:
    if (
        payload.get("schema_version") != SEALED_ROW_SCHEMA_VERSION
        or payload.get("run_id") != SEALED_RUN_ID
        or payload.get("strategy_id") != STRATEGY_ID
        or payload.get("native_ticket_count") != 2
        or payload.get("target_outcome_excluded") is not True
    ):
        raise ParityAttributionError(
            "SEALED_RADICAL_FAILURE_AUTHORITY_UNAVAILABLE: Radical row contract changed"
        )
    special_number = _require_int(payload.get("actual_special_number"), "special number")
    main_numbers = _parse_ticket(payload.get("actual_main_numbers"), "actual_main_numbers")
    if special_number in main_numbers or not 1 <= special_number <= 49:
        raise ParityAttributionError(
            "SEALED_RADICAL_FAILURE_AUTHORITY_UNAVAILABLE: invalid special number"
        )
    fingerprint = _require_str(
        payload.get("causal_history_fingerprint"), "causal_history_fingerprint"
    )
    if len(fingerprint) != 64 or any(
        character not in "0123456789abcdef" for character in fingerprint
    ):
        raise ParityAttributionError(
            "SEALED_RADICAL_FAILURE_AUTHORITY_UNAVAILABLE: invalid history fingerprint"
        )
    return SealedTargetRow(
        target_draw_number=_require_str(payload.get("target_draw_number"), "target draw"),
        target_draw_date=_require_str(payload.get("target_draw_date"), "target date"),
        main_numbers=main_numbers,
        special_number=special_number,
        replay_status=_require_str(payload.get("replay_status"), "replay status"),
        reason=_optional_str(payload.get("reason"), "reason"),
        causal_cutoff_draw_number=_require_str(
            payload.get("causal_cutoff_draw_number"), "causal cutoff draw"
        ),
        causal_cutoff_date=_require_str(
            payload.get("causal_cutoff_date"), "causal cutoff date"
        ),
        causal_history_length=_require_int(
            payload.get("causal_history_length"), "causal history length"
        ),
        causal_history_fingerprint=fingerprint,
    )


def load_radical_rows(
    evidence_path: Path,
    expected_target_order: Sequence[str],
) -> tuple[SealedTargetRow, ...]:
    """Load only the 750 Radical rows from the already-sealed replay stream."""

    rows: list[SealedTargetRow] = []
    strategy_marker = f'"strategy_id":"{STRATEGY_ID}"'
    try:
        with evidence_path.open(encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, start=1):
                if strategy_marker not in line:
                    continue
                try:
                    parsed: object = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ParityAttributionError(
                        "SEALED_RADICAL_FAILURE_AUTHORITY_UNAVAILABLE: "
                        f"invalid evidence JSON at line {line_number}"
                    ) from exc
                rows.append(_parse_sealed_row(_require_object(parsed, "target evidence row")))
    except OSError as exc:
        raise ParityAttributionError(
            f"SEALED_RADICAL_FAILURE_AUTHORITY_UNAVAILABLE: cannot read {evidence_path}"
        ) from exc

    ordered = tuple(sorted(rows, key=lambda row: row.chronological_key))
    observed_targets = tuple(row.target_draw_number for row in ordered)
    if (
        len(ordered) != EXPECTED_RADICAL_ROW_COUNT
        or len(set(observed_targets)) != len(observed_targets)
        or observed_targets != tuple(expected_target_order)
    ):
        raise ParityAttributionError(
            "SEALED_RADICAL_FAILURE_AUTHORITY_UNAVAILABLE: Radical RECENT_750 rows changed"
        )
    failures = tuple(
        row.target_draw_number for row in ordered if row.replay_status == "EXECUTION_FAILURE"
    )
    require_exact_failure_targets(failures)
    for row in ordered:
        if row.replay_status == "EXECUTION_FAILURE":
            if row.reason != SEALED_FAILURE_REASON:
                raise ParityAttributionError(
                    "SEALED_RADICAL_FAILURE_AUTHORITY_UNAVAILABLE: failure reason changed"
                )
        elif row.replay_status != "COMPLETE" or row.reason is not None:
            raise ParityAttributionError(
                "SEALED_RADICAL_FAILURE_AUTHORITY_UNAVAILABLE: non-failure row changed"
            )
    return ordered


def _component_ok(method_name: str, ticket: Sequence[int]) -> ComponentObservation:
    return ComponentObservation(
        method_name=method_name,
        status="OK",
        ticket=tuple(ticket),
        error_type=None,
        error_message=None,
    )


def _component_error(method_name: str, exc: Exception) -> ComponentObservation:
    return ComponentObservation(
        method_name=method_name,
        status="ERROR",
        ticket=None,
        error_type=type(exc).__name__,
        error_message=str(exc).replace("\n", " ").strip(),
    )


def inspect_retained_reference(
    history: tuple[LegacyHistoryDraw, ...],
    target_draw_number: str,
) -> PathObservation:
    """Execute the retained donor-faithful wave-31 path and its intermediates."""

    source_history = tuple(reversed(history))[:SOURCE_HISTORY_LIMIT]
    components: list[ComponentObservation] = []
    for method_name in ENGINE_METHODS:
        try:
            components.append(
                _component_ok(
                    method_name,
                    reference_module._engine_ticket(method_name, source_history),
                )
            )
        except Exception as exc:  # The frozen donor intentionally skips failures.
            components.append(_component_error(method_name, exc))
    pools: tuple[tuple[int, ...], ...] = ()
    try:
        pools = tuple(
            reference_module._weighted_candidates(
                source_history,
                exclusion,
                cold_bonus=False,
                strict_primary_methods=False,
            )
            for _, exclusion in POSITIONAL_COMPONENTS
        )
        result = generate_legacy_source_native_wave31_portfolio(
            LegacySourceNativeWave31Request(
                legacy_method_id=RADICAL_BACKTEST_METHOD_ID,
                target_draw_number=target_draw_number,
                history=history,
            )
        )
    except LegacySourceNativeWave31SourceError as exc:
        return PathObservation(
            components=tuple(components),
            candidate_pools=pools,
            outcome_status="CLOSED",
            tickets=None,
            closure_reason=exc.reason_code,
            exception_type=type(exc).__name__,
            exception_message=str(exc),
        )
    except Exception as exc:
        return PathObservation(
            components=tuple(components),
            candidate_pools=pools,
            outcome_status="UNRESOLVED",
            tickets=None,
            closure_reason=None,
            exception_type=type(exc).__name__,
            exception_message=str(exc).replace("\n", " ").strip(),
        )
    return PathObservation(
        components=tuple(components),
        candidate_pools=pools,
        outcome_status="EMITTED",
        tickets=tuple(tuple(ticket) for ticket in result.tickets),
        closure_reason=None,
        exception_type=None,
        exception_message=None,
    )


def inspect_current_adapter(
    history: tuple[CausalDrawRow, ...],
) -> PathObservation:
    """Execute the current adapter without the historical replay harness."""

    source_history = tuple(reversed(history))[:SOURCE_HISTORY_LIMIT]
    components: list[ComponentObservation] = []
    for method_name in ENGINE_METHODS:
        try:
            components.append(
                _component_ok(
                    method_name,
                    adapter_module._engine_ticket(method_name, source_history),
                )
            )
        except Exception as exc:  # The adapter preserves donor skip semantics.
            components.append(_component_error(method_name, exc))
    pools: tuple[tuple[int, ...], ...] = ()
    try:
        pools = tuple(
            adapter_module._weighted_candidates(source_history, exclusion)
            for _, exclusion in POSITIONAL_COMPONENTS
        )
        tickets = BigLottoRadicalGapBacktestAdapter().get_bets(
            history,
            LotteryType.BIG_LOTTO,
        )
    except InvalidOutput as exc:
        return PathObservation(
            components=tuple(components),
            candidate_pools=pools,
            outcome_status="CLOSED",
            tickets=None,
            closure_reason=str(exc),
            exception_type=type(exc).__name__,
            exception_message=str(exc),
        )
    except Exception as exc:
        return PathObservation(
            components=tuple(components),
            candidate_pools=pools,
            outcome_status="UNRESOLVED",
            tickets=None,
            closure_reason=None,
            exception_type=type(exc).__name__,
            exception_message=str(exc).replace("\n", " ").strip(),
        )
    return PathObservation(
        components=tuple(components),
        candidate_pools=pools,
        outcome_status="EMITTED",
        tickets=tuple(tuple(ticket) for ticket in tickets),
        closure_reason=None,
        exception_type=None,
        exception_message=None,
    )


def first_divergent_intermediate(
    reference: PathObservation,
    adapter: PathObservation,
) -> str | None:
    """Return the first normalized source/port divergence in execution order."""

    if len(reference.components) != len(adapter.components):
        return "component_count"
    for source_component, adapter_component in zip(
        reference.components, adapter.components, strict=True
    ):
        if source_component.method_name != adapter_component.method_name:
            return "component_order"
        if source_component.effective_key != adapter_component.effective_key:
            return f"component:{source_component.method_name}"
    if len(reference.candidate_pools) != len(adapter.candidate_pools):
        return "candidate_pool_count"
    for index, (source_pool, adapter_pool) in enumerate(
        zip(reference.candidate_pools, adapter.candidate_pools, strict=True)
    ):
        if source_pool != adapter_pool:
            return f"candidate_pool:{POSITIONAL_COMPONENTS[index][0]}"
    if reference.outcome_status != adapter.outcome_status:
        return "outcome_status"
    if reference.outcome_status == "EMITTED" and reference.tickets != adapter.tickets:
        return "emitted_tickets"
    if reference.outcome_status == "CLOSED":
        if reference.closure_reason != REFERENCE_CLOSURE_REASON:
            return "retained_source_closure_reason"
        if adapter.closure_reason != ADAPTER_CLOSURE_REASON:
            return "adapter_closure_reason"
    return None


def classify_observations(
    reference: PathObservation,
    adapter: PathObservation,
) -> tuple[str, str | None]:
    """Classify one sealed failure using normalized intermediate parity."""

    if reference.outcome_status == "UNRESOLVED":
        return SOURCE_AUTHORITY_UNRESOLVED, None
    if reference.outcome_status != "CLOSED":
        return SOURCE_AUTHORITY_UNRESOLVED, "retained_source_did_not_close"
    if (
        reference.closure_reason != REFERENCE_CLOSURE_REASON
        or not reference.candidate_pools
        or not any(len(pool) < 6 for pool in reference.candidate_pools)
    ):
        return SOURCE_AUTHORITY_UNRESOLVED, "retained_source_closure_not_load_bearing"
    divergence = first_divergent_intermediate(reference, adapter)
    if divergence is not None:
        return PORT_REGRESSION, divergence
    return DONOR_FAITHFUL_SOURCE_CLOSURE, None


def inspect_execution_paths(
    history: tuple[SealedTargetRow, ...],
    target_draw_number: str,
) -> tuple[PathObservation, PathObservation]:
    """Execute both paths for a directly necessary causal history."""

    return (
        inspect_retained_reference(
            tuple(row.legacy_row() for row in history),
            target_draw_number,
        ),
        inspect_current_adapter(tuple(row.causal_row() for row in history)),
    )


def _direct_history_sha256(history: Sequence[SealedTargetRow]) -> str:
    payload: dict[str, object] = {
        "history": [
            {
                "draw_date": row.target_draw_date,
                "draw_number": row.target_draw_number,
                "main_numbers": list(row.main_numbers),
                "special_number": row.special_number,
            }
            for row in history
        ]
    }
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def _path_payload(observation: PathObservation) -> dict[str, object]:
    payload = observation.canonical_dict()
    payload["candidate_pool_details"] = [
        {
            "candidate_count": len(pool),
            "candidates": list(pool),
            "fewer_than_six_legal_candidates": len(pool) < 6,
            "positional_component": POSITIONAL_COMPONENTS[index][0],
        }
        for index, pool in enumerate(observation.candidate_pools)
    ]
    return payload


def attribute_failure_rows(rows: Sequence[SealedTargetRow]) -> list[dict[str, object]]:
    """Classify the exact 29 failures from 750 chronologically ordered rows."""

    index_by_target = {row.target_draw_number: index for index, row in enumerate(rows)}
    results: list[dict[str, object]] = []
    for target in EXPECTED_FAILURE_TARGETS:
        index = index_by_target.get(target)
        if index is None or index < SOURCE_HISTORY_LIMIT:
            raise ParityAttributionError(
                "SEALED_RADICAL_FAILURE_AUTHORITY_UNAVAILABLE: "
                f"target {target} lacks a sealed 300-row causal runway"
            )
        row = rows[index]
        history = tuple(rows[index - SOURCE_HISTORY_LIMIT : index])
        cutoff = history[-1]
        if (
            cutoff.target_draw_number != row.causal_cutoff_draw_number
            or cutoff.target_draw_date != row.causal_cutoff_date
        ):
            raise ParityAttributionError(
                "SEALED_RADICAL_FAILURE_AUTHORITY_UNAVAILABLE: "
                f"target {target} causal cutoff changed"
            )
        reference, adapter = inspect_execution_paths(history, target)
        classification, divergence = classify_observations(reference, adapter)
        deficient_reference = tuple(
            POSITIONAL_COMPONENTS[position][0]
            for position, pool in enumerate(reference.candidate_pools)
            if len(pool) < 6
        )
        deficient_adapter = tuple(
            POSITIONAL_COMPONENTS[position][0]
            for position, pool in enumerate(adapter.candidate_pools)
            if len(pool) < 6
        )
        failed_engines = tuple(
            component.method_name
            for component in reference.components
            if component.status == "ERROR"
        )
        condition_key = (
            f"deficient={'+'.join(deficient_reference) or 'NONE'};"
            f"failed_engines={'+'.join(failed_engines) or 'NONE'};"
            f"pool_sizes={','.join(str(len(pool)) for pool in reference.candidate_pools)}"
        )
        results.append(
            {
                "classification": classification,
                "current_adapter": _path_payload(adapter),
                "deficient_current_adapter_positional_components": list(deficient_adapter),
                "deficient_retained_source_positional_components": list(deficient_reference),
                "direct_causal_history": {
                    "draw_count": len(history),
                    "first_draw_date": history[0].target_draw_date,
                    "first_draw_number": history[0].target_draw_number,
                    "last_draw_date": cutoff.target_draw_date,
                    "last_draw_number": cutoff.target_draw_number,
                    "sha256": _direct_history_sha256(history),
                },
                "exact_load_bearing_closure": (
                    reference.outcome_status == "CLOSED"
                    and reference.closure_reason == REFERENCE_CLOSURE_REASON
                    and bool(deficient_reference)
                ),
                "failed_retained_source_engine_components": list(failed_engines),
                "first_divergent_intermediate": divergence,
                "frozen_input_condition_key": condition_key,
                "retained_source": _path_payload(reference),
                "sealed_causal_history_fingerprint": row.causal_history_fingerprint,
                "sealed_causal_history_length": row.causal_history_length,
                "sealed_failure_reason": row.reason,
                "target_draw_date": row.target_draw_date,
                "target_draw_number": row.target_draw_number,
            }
        )
    return results


def _build_clusters(rows: Sequence[dict[str, object]]) -> list[dict[str, object]]:
    grouped: defaultdict[str, list[str]] = defaultdict(list)
    for row in rows:
        grouped[cast(str, row["frozen_input_condition_key"])].append(
            cast(str, row["target_draw_number"])
        )
    return [
        {
            "condition": condition,
            "target_count": len(targets),
            "targets": targets,
        }
        for condition, targets in sorted(grouped.items())
    ]


def _positional_answer(rows: Sequence[dict[str, object]]) -> str:
    patterns = {
        tuple(cast(list[str], row["deficient_retained_source_positional_components"]))
        for row in rows
    }
    if len(patterns) > 1:
        return "VARYING_POSITIONAL_COMPONENTS"
    only = next(iter(patterns))
    if len(only) == 2:
        return "BOTH_POSITIONAL_COMPONENTS"
    if len(only) == 1:
        return f"ONE_POSITIONAL_COMPONENT:{only[0]}"
    return "SOURCE_AUTHORITY_UNRESOLVED"


def build_result(
    *,
    taxonomy_result: Path,
    authority_directory: Path,
) -> dict[str, object]:
    """Build the deterministic parity-attribution payload in memory."""

    taxonomy_targets = verify_taxonomy_result(taxonomy_result)
    if taxonomy_targets != EXPECTED_FAILURE_TARGETS:
        raise ParityAttributionError(
            "SEALED_RADICAL_FAILURE_AUTHORITY_UNAVAILABLE: taxonomy target drift"
        )
    if SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE31_METHOD.get(RADICAL_BACKTEST_METHOD_ID) != (
        SOURCE_SHA256
    ):
        raise ParityAttributionError(
            "SEALED_RADICAL_FAILURE_AUTHORITY_UNAVAILABLE: retained donor SHA changed"
        )
    before = verify_authority_files(authority_directory)
    target_order = _validate_authority_contract(authority_directory)
    sealed_rows = load_radical_rows(
        authority_directory / "target_evidence.jsonl",
        target_order,
    )
    after = verify_authority_files(authority_directory)
    if before != after:
        raise ParityAttributionError(
            "SEALED_RADICAL_FAILURE_AUTHORITY_UNAVAILABLE: authority changed during load"
        )
    attributed_rows = attribute_failure_rows(sealed_rows)
    classification_counts = Counter(
        cast(str, row["classification"]) for row in attributed_rows
    )
    classification_summary = {
        classification: classification_counts[classification]
        for classification in CLASSIFICATIONS
    }
    positional_counts = Counter(
        "+".join(
            cast(list[str], row["deficient_retained_source_positional_components"])
        )
        for row in attributed_rows
    )
    all_donor_faithful = (
        classification_counts[DONOR_FAITHFUL_SOURCE_CLOSURE] == EXPECTED_FAILURE_COUNT
    )
    all_exact_closures = all(
        cast(bool, row["exact_load_bearing_closure"]) for row in attributed_rows
    )
    clusters = _build_clusters(attributed_rows)
    port_regression_count = classification_counts[PORT_REGRESSION]
    unresolved_count = classification_counts[SOURCE_AUTHORITY_UNRESOLVED]
    if unresolved_count:
        repair_answer = "UNKNOWN_SOURCE_AUTHORITY_UNRESOLVED"
        lineage_answer = "UNKNOWN_SOURCE_AUTHORITY_UNRESOLVED"
        disposition = "Resolve retained source authority before any semantics decision."
    elif port_regression_count:
        repair_answer = "YES_RESTORE_DONOR_PARITY_ONLY"
        lineage_answer = "NO_FOR_PORT_PARITY_RESTORATION"
        disposition = (
            "Restore only the first divergent adapter intermediate to retained donor parity; "
            "do not infer a strategy redesign."
        )
    else:
        repair_answer = "NO"
        lineage_answer = "YES"
        disposition = (
            "Keep the current donor-faithful adapter unchanged. Any attempt to emit tickets "
            "for these closures requires a corrected successor/new lineage decision."
        )

    return {
        "boundaries": {
            "canonical_semantics_changed": False,
            "database_access": "NO",
            "historical_replay": "NOT_RUN",
            "repair_implemented": False,
            "strategy_exclusion": "NOT_RUN",
            "successor_created": False,
        },
        "classification_counts": classification_summary,
        "frozen_input_condition_clusters": clusters,
        "questions": {
            "1_are_all_29_failures_donor_faithful": all_donor_faithful,
            "2_current_port_regression_count": port_regression_count,
            "3_fewer_than_six_is_exact_load_bearing_closure_for_each_donor_faithful_row": (
                all_exact_closures
            ),
            "4_positional_component_attribution": _positional_answer(attributed_rows),
            "5_clustered_around_identifiable_frozen_input_conditions": (
                len(clusters) < EXPECTED_FAILURE_COUNT
            ),
            "6_semantics_preserving_adapter_repair": repair_answer,
            "7_corrected_successor_or_new_lineage_required_to_change_closures": (
                lineage_answer
            ),
        },
        "recommended_next_technical_disposition": disposition,
        "rows": attributed_rows,
        "schema_version": SCHEMA_VERSION,
        "source_identity": {
            "authority_directory": str(authority_directory),
            "authority_files": before,
            "authority_hash_stable_before_after_load": True,
            "current_adapter": CURRENT_ADAPTER,
            "donor_path": RADICAL_BACKTEST_METHOD_ID,
            "donor_sha256": SOURCE_SHA256,
            "retained_reference": RETAINED_REFERENCE,
            "sealed_replay_run_id": SEALED_RUN_ID,
            "sealed_replay_source_head": SEALED_REPLAY_SOURCE_HEAD,
            "sealed_replay_source_tree": SEALED_REPLAY_SOURCE_TREE,
            "taxonomy_result_path": str(taxonomy_result),
            "taxonomy_result_sha256": TAXONOMY_RESULT_SHA256,
            "taxonomy_source_head": TAXONOMY_SOURCE_HEAD,
            "taxonomy_source_tree": TAXONOMY_SOURCE_TREE,
        },
        "summary": {
            "all_failures_donor_faithful": all_donor_faithful,
            "exact_failure_target_count": len(attributed_rows),
            "port_regression_count": port_regression_count,
            "positional_component_counts": dict(sorted(positional_counts.items())),
            "source_authority_unresolved_count": unresolved_count,
        },
        "task_id": TASK_ID,
    }


def _markdown_list(values: object) -> str:
    items = cast(list[str], values)
    return ", ".join(f"`{item}`" for item in items) if items else "none"


def render_report(payload: Mapping[str, object], result_sha256: str) -> str:
    """Render the exact row-level attribution and disposition as Markdown."""

    summary = cast(dict[str, object], payload["summary"])
    questions = cast(dict[str, object], payload["questions"])
    rows = cast(list[dict[str, object]], payload["rows"])
    clusters = cast(list[dict[str, object]], payload["frozen_input_condition_clusters"])
    classification_counts = cast(dict[str, int], payload["classification_counts"])
    lines = [
        "# B649 Radical-gap 29-failure parity attribution R1",
        "",
        "## Outcome",
        "",
        (
            f"All **{summary['exact_failure_target_count']}** sealed Radical-gap failures "
            f"classified as `{DONOR_FAITHFUL_SOURCE_CLOSURE}`: "
            f"**{classification_counts[DONOR_FAITHFUL_SOURCE_CLOSURE]}**. "
            f"Current-port regressions: **{summary['port_regression_count']}**. "
            f"Source-authority unresolved rows: "
            f"**{summary['source_authority_unresolved_count']}**."
        ),
        "",
        f"Result JSON SHA-256: `{result_sha256}`",
        "",
        "The analysis reconstructed only each target's directly necessary sealed "
        "300-draw window. It did not open a database or rerun K2.",
        "",
        "## Required questions",
        "",
        (
            "1. Are all 29 failures donor-faithful? "
            f"**{questions['1_are_all_29_failures_donor_faithful']}**."
        ),
        (
            "2. Current-port regressions: "
            f"**{questions['2_current_port_regression_count']}**."
        ),
        (
            "3. Is `fewer than six legal candidates` load-bearing for every "
            "donor-faithful row? "
            f"**{questions['3_fewer_than_six_is_exact_load_bearing_closure_for_each_donor_faithful_row']}**."
        ),
        (
            "4. Positional component attribution: "
            f"**{questions['4_positional_component_attribution']}**."
        ),
        (
            "5. Identifiable frozen-input clustering: "
            f"**{questions['5_clustered_around_identifiable_frozen_input_conditions']}**."
        ),
        (
            "6. Semantics-preserving adapter repair: "
            f"**{questions['6_semantics_preserving_adapter_repair']}**."
        ),
        (
            "7. Corrected successor/new lineage required to change the closures: "
            f"**{questions['7_corrected_successor_or_new_lineage_required_to_change_closures']}**."
        ),
        "",
        "## Exact 29-row classification",
        "",
        (
            "| Target | Date | Classification | Retained candidate counts | "
            "Load-bearing positional closure | Failed frozen engines | First divergence |"
        ),
        "|---|---|---|---:|---|---|---|",
    ]
    for row in rows:
        retained = cast(dict[str, object], row["retained_source"])
        pools = cast(list[dict[str, object]], retained["candidate_pool_details"])
        pool_counts = "/".join(str(pool["candidate_count"]) for pool in pools)
        lines.append(
            "| "
            f"`{row['target_draw_number']}` | {row['target_draw_date']} | "
            f"`{row['classification']}` | {pool_counts} | "
            f"{_markdown_list(row['deficient_retained_source_positional_components'])} | "
            f"{_markdown_list(row['failed_retained_source_engine_components'])} | "
            f"{row['first_divergent_intermediate'] or 'none'} |"
        )
    lines.extend(
        [
            "",
            "For every row above, the retained source closes with "
            f"`{REFERENCE_CLOSURE_REASON}` and the current adapter closes with "
            f"`{ADAPTER_CLOSURE_REASON}`. Exact candidates, component outputs/errors, "
            "history-window hashes, and sealed causal fingerprints are retained in the JSON.",
            "",
            "## Frozen-input condition clusters",
            "",
            "| Condition | Targets | Exact target IDs |",
            "|---|---:|---|",
        ]
    )
    for cluster in clusters:
        lines.append(
            f"| `{cluster['condition']}` | {cluster['target_count']} | "
            f"{_markdown_list(cluster['targets'])} |"
        )
    lines.extend(
        [
            "",
            "## Disposition",
            "",
            cast(str, payload["recommended_next_technical_disposition"]),
            "",
            "No strategy behavior, catalog entry, registry, replay, database, QuickML "
            "surface, K2 R2, or successor lineage was changed by this task.",
            "",
        ]
    )
    return "\n".join(lines)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--taxonomy-result",
        type=Path,
        default=DEFAULT_TAXONOMY_RESULT,
        help="Exact existing B649 K2 failure-taxonomy result artifact",
    )
    parser.add_argument(
        "--authority-directory",
        type=Path,
        default=DEFAULT_AUTHORITY_DIRECTORY,
        help="Hash-sealed exact-native K2/K3 authority directory",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    taxonomy_result = cast(Path, args.taxonomy_result)
    authority_directory = cast(Path, args.authority_directory)
    try:
        payload = build_result(
            taxonomy_result=taxonomy_result,
            authority_directory=authority_directory,
        )
    except ParityAttributionError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    result_bytes = canonical_json_bytes(payload)
    result_sha256 = hashlib.sha256(result_bytes).hexdigest()
    report = render_report(payload, result_sha256)
    OUTPUT_JSON.write_bytes(result_bytes)
    OUTPUT_REPORT.write_text(report, encoding="utf-8")
    print(
        json.dumps(
            {
                "classification_counts": payload["classification_counts"],
                "result_json": str(OUTPUT_JSON),
                "result_sha256": result_sha256,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
