"""Freeze the outcome-free T539 prospective evaluation protocol R1.

The sole research input is the already frozen callable-family-dedup shadow
manifest authenticated by exact SHA-256 and rule fingerprint.  This builder
does not read a draw source, outcome record, database, replay, or strategy.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, cast

PROTOCOL_SCHEMA_VERSION = "T539_PROSPECTIVE_EVALUATION_PROTOCOL_V1"
PROTOCOL_ID = "T539_PROSPECTIVE_EVALUATION_PROTOCOL_R1"
FREEZE_SCHEMA_VERSION = "T539_CALLABLE_FAMILY_DEDUP_PROSPECTIVE_SHADOW_FREEZE_V1"
FREEZE_ID = "T539_CALLABLE_FAMILY_DEDUP_PROSPECTIVE_SHADOW_FREEZE_R1"
FREEZE_PATH = Path(
    "docs/research/matrix-native-results/"
    "t539-callable-family-dedup-prospective-shadow-freeze-r1.json"
)
EXPECTED_FREEZE_SHA256 = "f1b299ace019393440bce8bd2768f6618b2362d220d81b4cc14151a5080908a8"
EXPECTED_RULE_FINGERPRINT = "eb4eb89082cd782041c240e80858efd8453c3bbf08edec3b76e98e2e8051f446"
FREEZE_BOUNDARY = "115000186"
PRIMARY_METRIC_ID = "OFFICIAL_ANY_PRIZE_TARGET_RATE"

EXPECTED_TICKET_COUNTS: tuple[int, ...] = (1, 2, 3, 4, 5, 7, 10, 11, 12, 25)
EXPECTED_WINDOWS: tuple[tuple[str, int], ...] = (
    ("W50", 50),
    ("W300", 300),
    ("W750", 750),
)
ARM_BINDINGS: tuple[tuple[str, str], ...] = (
    ("A", "ORIGINAL_ROLLING"),
    ("B", "CALLABLE_FAMILY_DEDUP_ROLLING"),
    ("C", "CALLABLE_FAMILY_DEDUP_FROZEN_BASELINE"),
)
COMPARISON_IDS: tuple[str, ...] = ("B_MINUS_A", "B_MINUS_C")
EXPECTED_EXPERIMENT_IDS: tuple[str, ...] = tuple(
    f"T539:K{ticket_count}:{window_label}"
    for ticket_count in EXPECTED_TICKET_COUNTS
    for window_label, _ in EXPECTED_WINDOWS
)

TechnicalExclusion = Literal[
    "MISSED_PRETARGET_SEAL",
    "PRETARGET_SNAPSHOT_INVALID",
    "RULE_FINGERPRINT_MISMATCH",
    "TARGET_IDENTITY_MISMATCH",
    "OUTCOME_AUTHORITY_UNAVAILABLE",
    "INCOMPLETE_FROZEN_EXPERIMENT_SURFACE",
]
TECHNICAL_EXCLUSIONS: tuple[TechnicalExclusion, ...] = (
    "MISSED_PRETARGET_SEAL",
    "PRETARGET_SNAPSHOT_INVALID",
    "RULE_FINGERPRINT_MISMATCH",
    "TARGET_IDENTITY_MISMATCH",
    "OUTCOME_AUTHORITY_UNAVAILABLE",
    "INCOMPLETE_FROZEN_EXPERIMENT_SURFACE",
)

ProspectiveClassification = Literal[
    "VALID_PROSPECTIVE",
    "INELIGIBLE_AT_OR_BEFORE_FREEZE_BOUNDARY",
    "MISSED_PRETARGET_SEAL",
    "PRETARGET_SNAPSHOT_INVALID",
    "RULE_FINGERPRINT_MISMATCH",
    "TARGET_IDENTITY_MISMATCH",
    "OUTCOME_AUTHORITY_UNAVAILABLE",
    "INCOMPLETE_FROZEN_EXPERIMENT_SURFACE",
]

JSON_OUTPUT_PATH = Path(
    "docs/research/matrix-native-results/t539-prospective-evaluation-protocol-r1.json"
)
MARKDOWN_OUTPUT_PATH = Path("docs/research/t539-prospective-evaluation-protocol-r1.md")
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
_TARGET_IDENTITY = re.compile(r"[0-9]{1,32}", flags=re.ASCII)


class ProtocolContractError(RuntimeError):
    """The frozen authority or prospective protocol violates its contract."""


@dataclass(frozen=True)
class ProspectiveMetadata:
    """Outcome-free metadata used to classify one future target."""

    target_identity: str
    pretarget_snapshot_exists: bool
    pretarget_snapshot_sealed_before_outcome: bool
    pretarget_snapshot_valid: bool
    snapshot_rule_fingerprint: str | None
    snapshot_target_identity: str | None
    outcome_authority_available: bool
    outcome_target_identity: str | None
    complete_experiment_ids: tuple[str, ...]


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _mapping(value: object, *, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ProtocolContractError(f"{context} must be a JSON object")
    return cast(dict[str, Any], value)


def _list(value: object, *, context: str) -> list[Any]:
    if not isinstance(value, list):
        raise ProtocolContractError(f"{context} must be a JSON array")
    return cast(list[Any], value)


def _text(value: object, *, context: str) -> str:
    if type(value) is not str or not value:
        raise ProtocolContractError(f"{context} must be non-empty text")
    return value


def _integer(value: object, *, context: str) -> int:
    if type(value) is not int:
        raise ProtocolContractError(f"{context} must be an exact integer")
    return value


def _identity(value: object, *, context: str) -> list[str]:
    identity = _list(value, context=context)
    if len(identity) != 4 or any(type(item) is not str or not item for item in identity):
        raise ProtocolContractError(f"{context} must be one complete four-field identity")
    return cast(list[str], identity)


def validate_frozen_authority(freeze: Mapping[str, Any]) -> None:
    """Validate the sealed identity and all protocol-defining authority fields."""

    if (
        freeze.get("schema_version") != FREEZE_SCHEMA_VERSION
        or freeze.get("freeze_id") != FREEZE_ID
    ):
        raise ProtocolContractError("FREEZE_IDENTITY_DRIFT: freeze identity changed")

    fingerprint = _mapping(
        freeze.get("immutable_rule_fingerprint"),
        context="immutable_rule_fingerprint",
    )
    if fingerprint.get("sha256") != EXPECTED_RULE_FINGERPRINT:
        raise ProtocolContractError("FREEZE_IDENTITY_DRIFT: rule fingerprint mismatch")

    boundary = _mapping(freeze.get("freeze_boundary"), context="freeze_boundary")
    if boundary.get("target_identity") != FREEZE_BOUNDARY:
        raise ProtocolContractError("FREEZE_IDENTITY_DRIFT: freeze boundary changed")

    selector = _mapping(freeze.get("selector_contract"), context="selector_contract")
    if selector.get("primary_metric_id") != PRIMARY_METRIC_ID:
        raise ProtocolContractError("PRIMARY_METRIC_AUTHORITY_UNRESOLVED")

    surface = _mapping(freeze.get("surface"), context="surface")
    if surface.get("lottery_id") != "T539":
        raise ProtocolContractError("FREEZE_IDENTITY_DRIFT: lottery changed")
    if surface.get("included_native_ticket_counts") != list(EXPECTED_TICKET_COUNTS):
        raise ProtocolContractError("FREEZE_IDENTITY_DRIFT: K surface changed")
    if surface.get("included_cell_count") != len(EXPECTED_TICKET_COUNTS):
        raise ProtocolContractError("FREEZE_IDENTITY_DRIFT: cell count changed")
    expected_windows = [
        {"label": label, "size": size} for label, size in EXPECTED_WINDOWS
    ]
    if surface.get("windows") != expected_windows:
        raise ProtocolContractError("FREEZE_IDENTITY_DRIFT: window surface changed")

    integrity = _mapping(freeze.get("freeze_integrity"), context="freeze_integrity")
    if (
        integrity.get("future_outcome_access") != "NO"
        or integrity.get("prospective_observations") != 0
        or integrity.get("prospective_observation_records") != []
        or integrity.get("post_freeze_outcome_records") != []
    ):
        raise ProtocolContractError("PROSPECTIVE_PROTOCOL_CONTAMINATED")


def load_frozen_authority(repository_root: Path = REPOSITORY_ROOT) -> dict[str, Any]:
    """Load only the exact local freeze manifest; never resolve an outcome source."""

    freeze_path = repository_root / FREEZE_PATH
    try:
        payload = freeze_path.read_bytes()
    except OSError as error:
        raise ProtocolContractError(f"frozen authority unavailable: {FREEZE_PATH}") from error
    observed_sha256 = _sha256(payload)
    if observed_sha256 != EXPECTED_FREEZE_SHA256:
        raise ProtocolContractError(
            "FREEZE_IDENTITY_DRIFT: freeze SHA-256 mismatch: "
            f"expected {EXPECTED_FREEZE_SHA256}, observed {observed_sha256}"
        )
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError as error:
        raise ProtocolContractError("frozen authority is not valid JSON") from error
    freeze = _mapping(parsed, context="frozen authority")
    validate_frozen_authority(freeze)
    return freeze


def is_prospective_target(target_identity: str) -> bool:
    """Return whether a canonical target is strictly after the freeze boundary."""

    if type(target_identity) is not str or _TARGET_IDENTITY.fullmatch(target_identity) is None:
        raise ProtocolContractError("target_identity must contain 1-32 ASCII decimal digits")
    return int(target_identity) > int(FREEZE_BOUNDARY)


def validate_technical_exclusion(
    reason: str,
    *,
    depends_on_arm_performance: bool = False,
) -> TechnicalExclusion:
    """Reject any exclusion outside the frozen technical-only vocabulary."""

    if depends_on_arm_performance:
        raise ProtocolContractError("performance-dependent exclusion is forbidden")
    if reason not in TECHNICAL_EXCLUSIONS:
        raise ProtocolContractError(f"non-technical exclusion is forbidden: {reason}")
    return reason


def classify_prospective_metadata(
    metadata: ProspectiveMetadata,
) -> ProspectiveClassification:
    """Apply the fixed outcome-independent cohort inclusion decision."""

    if not is_prospective_target(metadata.target_identity):
        return "INELIGIBLE_AT_OR_BEFORE_FREEZE_BOUNDARY"
    if (
        not metadata.pretarget_snapshot_exists
        or not metadata.pretarget_snapshot_sealed_before_outcome
    ):
        return "MISSED_PRETARGET_SEAL"
    if not metadata.pretarget_snapshot_valid:
        return "PRETARGET_SNAPSHOT_INVALID"
    if metadata.snapshot_rule_fingerprint != EXPECTED_RULE_FINGERPRINT:
        return "RULE_FINGERPRINT_MISMATCH"
    if metadata.snapshot_target_identity != metadata.target_identity:
        return "TARGET_IDENTITY_MISMATCH"
    if not metadata.outcome_authority_available:
        return "OUTCOME_AUTHORITY_UNAVAILABLE"
    if metadata.outcome_target_identity != metadata.target_identity:
        return "TARGET_IDENTITY_MISMATCH"
    observed_experiments = metadata.complete_experiment_ids
    if (
        len(observed_experiments) != len(EXPECTED_EXPERIMENT_IDS)
        or len(set(observed_experiments)) != len(observed_experiments)
        or set(observed_experiments) != set(EXPECTED_EXPERIMENT_IDS)
    ):
        return "INCOMPLETE_FROZEN_EXPERIMENT_SURFACE"
    return "VALID_PROSPECTIVE"


def _arm_definitions(freeze: Mapping[str, Any]) -> list[dict[str, Any]]:
    comparators = [
        _mapping(item, context=f"comparators[{index}]")
        for index, item in enumerate(_list(freeze.get("comparators"), context="comparators"))
    ]
    if [item.get("id") for item in comparators] != [item[1] for item in ARM_BINDINGS]:
        raise ProtocolContractError("FREEZE_IDENTITY_DRIFT: frozen arms changed")

    arms: list[dict[str, Any]] = []
    for (arm_id, frozen_arm_id), comparator in zip(
        ARM_BINDINGS,
        comparators,
        strict=True,
    ):
        definition: dict[str, Any] = {
            "arm_id": arm_id,
            "frozen_arm_id": frozen_arm_id,
            "selection_mode": _text(
                comparator.get("selection_mode"),
                context=f"{frozen_arm_id}.selection_mode",
            ),
            "universe_reference": _text(
                comparator.get("universe_reference"),
                context=f"{frozen_arm_id}.universe_reference",
            ),
            "universe_sha256_field": _text(
                comparator.get("universe_sha256_field"),
                context=f"{frozen_arm_id}.universe_sha256_field",
            ),
        }
        if arm_id == "C":
            definition["baseline_identity_field"] = _text(
                comparator.get("baseline_identity_field"),
                context=f"{frozen_arm_id}.baseline_identity_field",
            )
        arms.append(definition)
    return arms


def _experiments(freeze: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw_cells = _list(freeze.get("cells"), context="cells")
    cells_by_k: dict[int, dict[str, Any]] = {}
    for index, raw_cell in enumerate(raw_cells):
        cell = _mapping(raw_cell, context=f"cells[{index}]")
        ticket_count = _integer(
            cell.get("native_ticket_count"),
            context=f"cells[{index}].native_ticket_count",
        )
        if ticket_count in cells_by_k:
            raise ProtocolContractError(f"duplicate frozen K cell: {ticket_count}")
        cells_by_k[ticket_count] = cell
    if set(cells_by_k) != set(EXPECTED_TICKET_COUNTS):
        raise ProtocolContractError("FREEZE_IDENTITY_DRIFT: frozen K cells changed")

    experiments: list[dict[str, Any]] = []
    for ticket_count in EXPECTED_TICKET_COUNTS:
        cell = cells_by_k[ticket_count]
        cell_id = f"T539:K{ticket_count}"
        if cell.get("cell_id") != cell_id or cell.get("lottery_id") != "T539":
            raise ProtocolContractError(f"FREEZE_IDENTITY_DRIFT: {cell_id} identity changed")
        original_sha256 = _text(
            cell.get("original_candidate_universe_sha256"),
            context=f"{cell_id}.original_candidate_universe_sha256",
        )
        dedup_sha256 = _text(
            cell.get("callable_reduced_universe_sha256"),
            context=f"{cell_id}.callable_reduced_universe_sha256",
        )
        windows_by_label: dict[str, dict[str, Any]] = {}
        for index, raw_window in enumerate(
            _list(cell.get("windows"), context=f"{cell_id}.windows")
        ):
            window = _mapping(raw_window, context=f"{cell_id}.windows[{index}]")
            label = _text(window.get("label"), context=f"{cell_id}.windows[{index}].label")
            if label in windows_by_label:
                raise ProtocolContractError(f"{cell_id} contains duplicate window {label}")
            windows_by_label[label] = window
        if set(windows_by_label) != {label for label, _ in EXPECTED_WINDOWS}:
            raise ProtocolContractError(f"FREEZE_IDENTITY_DRIFT: {cell_id} windows changed")

        for window_label, window_size in EXPECTED_WINDOWS:
            window = windows_by_label[window_label]
            if window.get("size") != window_size:
                raise ProtocolContractError(
                    f"FREEZE_IDENTITY_DRIFT: {cell_id}.{window_label} size changed"
                )
            baseline_identity = _identity(
                window.get("callable_family_dedup_frozen_baseline_identity"),
                context=f"{cell_id}.{window_label}.baseline_identity",
            )
            experiments.append(
                {
                    "arm_ids": [arm_id for arm_id, _ in ARM_BINDINGS],
                    "cell_id": cell_id,
                    "comparison_ids": list(COMPARISON_IDS),
                    "experiment_id": f"{cell_id}:{window_label}",
                    "native_ticket_count": ticket_count,
                    "source_freeze_binding": {
                        "callable_family_dedup_frozen_baseline_identity": baseline_identity,
                        "callable_reduced_universe_sha256": dedup_sha256,
                        "original_candidate_universe_sha256": original_sha256,
                    },
                    "window": {"label": window_label, "size": window_size},
                }
            )
    if tuple(item["experiment_id"] for item in experiments) != EXPECTED_EXPERIMENT_IDS:
        raise ProtocolContractError("deterministic experiment ordering changed")
    return experiments


def _paired_comparisons() -> list[dict[str, str]]:
    return [
        {
            "comparison_id": "B_MINUS_A",
            "delta_denominator": "VALID_TARGET_COUNT",
            "delta_formula": "(B_SUCCESS_COUNT - A_SUCCESS_COUNT) / VALID_TARGET_COUNT",
            "delta_numerator": "B_SUCCESS_COUNT - A_SUCCESS_COUNT",
            "minuend_arm_id": "B",
            "subtrahend_arm_id": "A",
        },
        {
            "comparison_id": "B_MINUS_C",
            "delta_denominator": "VALID_TARGET_COUNT",
            "delta_formula": "(B_SUCCESS_COUNT - C_SUCCESS_COUNT) / VALID_TARGET_COUNT",
            "delta_numerator": "B_SUCCESS_COUNT - C_SUCCESS_COUNT",
            "minuend_arm_id": "B",
            "subtrahend_arm_id": "C",
        },
    ]


def build_protocol(freeze: Mapping[str, Any]) -> dict[str, Any]:
    """Derive the deterministic prospective measurement contract."""

    validate_frozen_authority(freeze)
    experiments = _experiments(freeze)
    arms = _arm_definitions(freeze)
    if len(experiments) != 30:
        raise ProtocolContractError("expected exactly 30 K x window experiments")

    return {
        "accumulation_contract": {
            "chronological_target_order": "ASCENDING_NUMERIC_TARGET_IDENTITY",
            "per_experiment_required_report_fields": [
                "valid_target_count",
                "arm_success_counts",
                "exact_arm_rate_numerators_and_denominator",
                "exact_paired_rate_deltas",
                "chronological_target_identities",
                "technical_exclusions",
            ],
            "raw_target_level_outcomes": "RETAIN",
            "raw_target_record_required_fields": [
                "target_identity",
                "pretarget_snapshot_identity",
                "snapshot_rule_fingerprint",
                "outcome_authority_identity",
                "experiment_id",
                "A_success_indicator",
                "B_success_indicator",
                "C_success_indicator",
            ],
            "success_indicator_domain": [0, 1],
            "technical_exclusions_reported_separately": True,
        },
        "arms": arms,
        "authority": {
            "freeze_boundary": FREEZE_BOUNDARY,
            "freeze_id": FREEZE_ID,
            "freeze_path": str(FREEZE_PATH),
            "freeze_sha256": EXPECTED_FREEZE_SHA256,
            "primary_metric_field": "selector_contract.primary_metric_id",
            "rule_fingerprint": EXPECTED_RULE_FINGERPRINT,
        },
        "frozen_surface": {
            "experiment_count": len(experiments),
            "experiments": experiments,
            "lottery_id": "T539",
            "native_ticket_counts": list(EXPECTED_TICKET_COUNTS),
            "windows": [
                {"label": label, "size": size} for label, size in EXPECTED_WINDOWS
            ],
        },
        "inferential_guardrails": {
            "best_window_selection": "FORBIDDEN",
            "composite_score": "NOT_DEFINED",
            "cross_k_rank": "FORBIDDEN",
            "cross_window_rank": "FORBIDDEN",
            "early_stopping_winner_rule": "FORBIDDEN",
            "materiality_threshold": "NOT_DEFINED",
            "promotion_threshold": "NOT_DEFINED",
            "p_value_threshold": "NOT_DEFINED",
            "significance_claim": "NOT_DEFINED",
            "weighted_score": "NOT_DEFINED",
        },
        "integrity": {
            "database_access": "NO",
            "future_outcome_access": "NO",
            "historical_replay": "NOT_RUN",
            "post_freeze_outcome_records": [],
            "predictive_advantage": "NOT_ESTABLISHED",
            "profitability": "NOT_ESTABLISHED",
            "promotion_rule": "NOT_DEFINED",
            "prospective_observation_records": [],
            "prospective_observations": 0,
            "significance_rule": "NOT_DEFINED",
            "strategy_execution": "NOT_RUN",
        },
        "measurement_contract": {
            "aggregation_scope": "ONE_K_X_WINDOW_EXPERIMENT_AT_A_TIME",
            "arm_rate": {
                "denominator": "VALID_TARGET_COUNT",
                "exact_fraction_required": True,
                "numerator": "ARM_SUCCESS_COUNT",
            },
            "paired_comparisons": _paired_comparisons(),
            "primary_metric_id": PRIMARY_METRIC_ID,
            "target_level_measurement": "OFFICIAL_ANY_PRIZE_BINARY_SUCCESS_INDICATOR",
            "unit_of_analysis": "TARGET",
        },
        "prospective_inclusion": {
            "all_conditions_required": [
                "TARGET_IDENTITY_STRICTLY_AFTER_115000186",
                "COMPLETE_PRETARGET_SNAPSHOT_SEALED_BEFORE_OUTCOME_AVAILABILITY",
                "SNAPSHOT_RULE_FINGERPRINT_MATCHES_FROZEN_RULE",
                "OUTCOME_AUTHORITY_MATCHES_THE_SAME_TARGET_IDENTITY",
                "OBSERVATION_IS_OTHERWISE_TECHNICALLY_VALID",
            ],
            "historical_reconstruction_policy": (
                "SEPARATE_ONLY_NEVER_RELABEL_AS_PROSPECTIVE"
            ),
            "included_status": "VALID_PROSPECTIVE",
            "missed_pretarget_seal": {
                "backfill": "FORBIDDEN",
                "performance_classification": "NEITHER_POSITIVE_NOR_NEGATIVE",
                "status": "MISSED_PRETARGET_SEAL",
            },
            "target_predicate": "int(target_identity) > 115000186",
        },
        "protocol_id": PROTOCOL_ID,
        "schema_version": PROTOCOL_SCHEMA_VERSION,
        "selection_guards": {
            "cross_k_aggregation": "FORBIDDEN",
            "cross_window_aggregation": "FORBIDDEN",
            "historical_performance_filtering": "FORBIDDEN",
        },
        "technical_exclusion_contract": {
            "allowed_reasons": list(TECHNICAL_EXCLUSIONS),
            "arm_performance_dependency": "FORBIDDEN",
            "input_domain": "TECHNICAL_METADATA_ONLY",
        },
    }


def _code(value: object) -> str:
    return f"`{str(value).replace('`', '')}`"


def render_markdown(
    protocol: Mapping[str, Any],
    *,
    json_sha256: str,
    json_size_bytes: int,
) -> bytes:
    surface = _mapping(protocol.get("frozen_surface"), context="frozen_surface")
    experiments = _list(surface.get("experiments"), context="experiments")
    lines = [
        "# T539 prospective evaluation protocol R1",
        "",
        "> Deterministic preregistration only. No post-freeze outcome is consumed or evaluated.",
        "",
        "## Frozen authority",
        "",
        f"- Freeze source: {_code(FREEZE_PATH)}",
        f"- Freeze SHA-256: {_code(EXPECTED_FREEZE_SHA256)}",
        f"- Rule fingerprint: {_code(EXPECTED_RULE_FINGERPRINT)}",
        f"- Freeze boundary: {_code(FREEZE_BOUNDARY)}",
        f"- Primary metric: {_code(PRIMARY_METRIC_ID)}",
        f"- Protocol JSON SHA-256: {_code(json_sha256)} ({json_size_bytes} bytes)",
        "",
        "## Frozen experiment surface",
        "",
        "- K values: `K1`, `K2`, `K3`, `K4`, `K5`, `K7`, `K10`, `K11`, `K12`, `K25`",
        "- Windows: `W50`, `W300`, `W750`",
        "- Experiments: `30`, measured independently",
        "- Arm A: `ORIGINAL_ROLLING`",
        "- Arm B: `CALLABLE_FAMILY_DEDUP_ROLLING`",
        "- Arm C: `CALLABLE_FAMILY_DEDUP_FROZEN_BASELINE`",
        "",
        "| Experiment | K | Window | Arms | Comparisons |",
        "|---|---:|---|---|---|",
    ]
    for raw_experiment in experiments:
        experiment = _mapping(raw_experiment, context="experiment")
        window = _mapping(experiment.get("window"), context="experiment.window")
        lines.append(
            f"| {_code(experiment['experiment_id'])} | {experiment['native_ticket_count']} | "
            f"{_code(window['label'])} | A, B, C | B minus A; B minus C |"
        )

    lines.extend(
        [
            "",
            "## Prospective inclusion",
            "",
            "A target enters the cohort only when `target_identity > 115000186`, a complete "
            "PRETARGET snapshot for that exact target was sealed before outcome availability, "
            "its rule fingerprint matches, the outcome authority matches the same target, and "
            "the full observation is technically valid.",
            "",
            "`MISSED_PRETARGET_SEAL` is never backfilled and is classified as neither positive "
            "nor negative. Historical reconstruction must remain separate and may never be "
            "relabeled prospective.",
            "",
            "## Technical-only exclusions",
            "",
        ]
    )
    lines.extend(f"- {_code(reason)}" for reason in TECHNICAL_EXCLUSIONS)
    lines.extend(
        [
            "",
            "Exclusions may not depend on whether any arm won or lost.",
            "",
            "## Measurement and accumulation",
            "",
            "Each K x window experiment retains chronological raw target-level A/B/C binary "
            "success indicators. Reports preserve the valid target count, each arm's exact "
            "success numerator over that common denominator, B-A and B-C exact paired rate "
            "deltas, chronological target identities, and technical exclusions separately.",
            "",
            "There is no cross-K/window aggregation, composite or weighted score, rank, best-"
            "window selection, early-stopping winner, materiality threshold, p-value threshold, "
            "significance claim, or promotion threshold.",
            "",
            "## Integrity",
            "",
            "```text",
            "FUTURE_OUTCOME_ACCESS = NO",
            "PROSPECTIVE_OBSERVATIONS = 0",
            "HISTORICAL_REPLAY = NOT RUN",
            "STRATEGY_EXECUTION = NOT RUN",
            "DB_ACCESS = NO",
            "SIGNIFICANCE_RULE = NOT DEFINED",
            "PROMOTION_RULE = NOT DEFINED",
            "PREDICTIVE_ADVANTAGE = NOT ESTABLISHED",
            "PROFITABILITY = NOT ESTABLISHED",
            "```",
            "",
        ]
    )
    return "\n".join(lines).encode("utf-8")


def build_artifact_bytes(
    repository_root: Path = REPOSITORY_ROOT,
) -> tuple[dict[str, Any], bytes, bytes]:
    freeze = load_frozen_authority(repository_root)
    protocol = build_protocol(freeze)
    json_bytes = canonical_json_bytes(protocol)
    markdown_bytes = render_markdown(
        protocol,
        json_sha256=_sha256(json_bytes),
        json_size_bytes=len(json_bytes),
    )
    return protocol, json_bytes, markdown_bytes


def write_artifacts(repository_root: Path = REPOSITORY_ROOT) -> dict[str, str | int]:
    _, json_bytes, markdown_bytes = build_artifact_bytes(repository_root)
    json_path = repository_root / JSON_OUTPUT_PATH
    markdown_path = repository_root / MARKDOWN_OUTPUT_PATH
    if not json_path.parent.is_dir() or not markdown_path.parent.is_dir():
        raise ProtocolContractError("authorized output parent directory is missing")
    json_path.write_bytes(json_bytes)
    markdown_path.write_bytes(markdown_bytes)
    return {
        "json_bytes": len(json_bytes),
        "json_sha256": _sha256(json_bytes),
        "markdown_bytes": len(markdown_bytes),
        "markdown_sha256": _sha256(markdown_bytes),
    }


def check_artifacts(repository_root: Path = REPOSITORY_ROOT) -> dict[str, str | int]:
    _, expected_json, expected_markdown = build_artifact_bytes(repository_root)
    json_path = repository_root / JSON_OUTPUT_PATH
    markdown_path = repository_root / MARKDOWN_OUTPUT_PATH
    if not json_path.is_file() or json_path.read_bytes() != expected_json:
        raise ProtocolContractError(f"{JSON_OUTPUT_PATH} is missing or stale")
    if not markdown_path.is_file() or markdown_path.read_bytes() != expected_markdown:
        raise ProtocolContractError(f"{MARKDOWN_OUTPUT_PATH} is missing or stale")
    return {
        "json_bytes": len(expected_json),
        "json_sha256": _sha256(expected_json),
        "markdown_bytes": len(expected_markdown),
        "markdown_sha256": _sha256(expected_markdown),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify both authorized artifacts without writing",
    )
    arguments = parser.parse_args()
    result = check_artifacts() if arguments.check else write_artifacts()
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
