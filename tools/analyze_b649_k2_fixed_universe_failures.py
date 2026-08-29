"""Attribute B649 K2 fixed-universe blockage from sealed execution evidence.

This tool is intentionally read-only with respect to the sealed authority.  It
does not execute strategies, open a database, regenerate replay evidence, or
change the canonical strategy universe.  Its only writes are the deterministic
JSON and Markdown artifacts requested by the task packet.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, cast

TASK_ID = "B649_K2_FIXED_UNIVERSE_FAILURE_TAXONOMY_R1"
SCHEMA_VERSION = "B649_K2_FIXED_UNIVERSE_FAILURE_TAXONOMY_V1"
EXPECTED_RUN_ID = "B649_K2_K3_EXACT_NATIVE_FULL_REPLAY_R1"
EXPECTED_ROW_SCHEMA = "B649_EXACT_NATIVE_TARGET_EVIDENCE_V1"
EXPECTED_K2_STRATEGY_COUNT = 19
EXPECTED_TARGET_COUNT = 750
EXPECTED_TOTAL_ROW_COUNT = 28_500
EXPECTED_K2_ROW_COUNT = EXPECTED_K2_STRATEGY_COUNT * EXPECTED_TARGET_COUNT

ROLLING_SELECTOR_SOURCE_COMMIT = "abc367bd6d8b59d01ecc4d79e56c787bbc03cd20"
ROLLING_SELECTOR_SOURCE_TREE = "bf430efd66b7ce1ac38ee04fb0052e8c55cc972c"
SEALED_REPLAY_SOURCE_HEAD = "85d2b4578d437b66bd015c60dd1f9bdc8404e755"
SEALED_REPLAY_SOURCE_TREE = "c6341c36ca210e02b08bac66ff98b7c8be1fc95a"
CANONICAL_RELATIVE_EVIDENCE_PATH = (
    "authorities/big_lotto/exact_native_k2_k3/target_evidence.jsonl"
)

EXPECTED_AUTHORITY_HASHES: dict[str, str] = {
    "promotion_provenance.json": (
        "63057f07c33d92c18bfc4f35975407624ea6464778bfb7d110576f4589a36632"
    ),
    "ranking.json": "3c09cf4791ac55c83bd7556d4b947cb1f80b762abf767b6b83f075c9d344753f",
    "sealed_manifest.json": (
        "9b9a9ca35252ff51bf60cf8e04a4e1e0b182a07ca34e2c2f8777f5d587445495"
    ),
    "target_evidence.jsonl": (
        "f4ee7bcd2900c6c066b6aa0255031c97c1ca1a248c605ce68a46f62bfe7820f0"
    ),
}
EXPECTED_AUTHORITY_SIZES: dict[str, int] = {
    "promotion_provenance.json": 1_182,
    "ranking.json": 74_122,
    "sealed_manifest.json": 63_279,
    "target_evidence.jsonl": 52_228_568,
}
EXPECTED_WAVE26_AUTHORITY_LINEAGE_IDS = (
    "legacy_biglotto__test_ces__78d17c530ab8",
    "legacy_biglotto__test_dms__b63442289bd5",
    "legacy_biglotto__test_greedy_optimizer__82df7f878ece",
    "legacy_biglotto__test_mwsc__ba37643d6a3b",
)
WAVE26_NATIVE_HELPER_PROVENANCE = (
    "native_helper:lottolab.application.legacy_source_native_portfolios_wave26"
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
DEFAULT_OUTPUT_JSON = Path(
    "docs/research/matrix-native-results/"
    "b649-k2-fixed-universe-failure-taxonomy-r1-result.json"
)
DEFAULT_OUTPUT_REPORT = Path(
    "docs/research/b649-k2-fixed-universe-failure-taxonomy-r1.md"
)

JsonObject = dict[str, Any]


class FailureTaxonomyError(ValueError):
    """The sealed authority or failure accounting violates the task contract."""


@dataclass(frozen=True, slots=True)
class AuthorityPaths:
    """Exact files in the sealed B649 K2/K3 authority."""

    directory: Path

    def file(self, name: str) -> Path:
        return self.directory / name

    @property
    def ordered_files(self) -> tuple[Path, ...]:
        return tuple(self.file(name) for name in sorted(EXPECTED_AUTHORITY_HASHES))


@dataclass(frozen=True, slots=True)
class StrategyMetadata:
    strategy_id: str
    display_name: str
    version: str
    adapter_path: str
    implementation_family: str
    provenance: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EvidenceRow:
    strategy_id: str
    strategy_version: str
    display_name: str
    target_draw_number: str
    target_draw_date: str
    replay_status: str
    reason: str | None

    @property
    def chronological_key(self) -> tuple[date, int]:
        try:
            parsed_date = date.fromisoformat(self.target_draw_date)
            parsed_draw = int(self.target_draw_number)
        except ValueError as exc:
            raise FailureTaxonomyError(
                "INVALID_TARGET_IDENTITY: "
                f"{self.target_draw_number}/{self.target_draw_date}"
            ) from exc
        return parsed_date, parsed_draw


@dataclass(frozen=True, slots=True)
class LoadedEvidence:
    k2_rows: tuple[EvidenceRow, ...]
    total_row_count: int
    row_count_by_native_ticket_count: dict[int, int]
    row_schema_variant_count: int


def _require_object(value: object, locator: str) -> JsonObject:
    if not isinstance(value, dict):
        raise FailureTaxonomyError(f"{locator} must be an object")
    return cast(JsonObject, value)


def _require_list(value: object, locator: str) -> list[Any]:
    if not isinstance(value, list):
        raise FailureTaxonomyError(f"{locator} must be an array")
    return cast(list[Any], value)


def _require_str(value: object, locator: str) -> str:
    if not isinstance(value, str) or not value:
        raise FailureTaxonomyError(f"{locator} must be a non-empty string")
    return value


def _require_int(value: object, locator: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise FailureTaxonomyError(f"{locator} must be an integer")
    return value


def _optional_str(value: object, locator: str) -> str | None:
    if value is None:
        return None
    return _require_str(value, locator)


def canonical_json_bytes(payload: Mapping[str, Any]) -> bytes:
    """Return stable UTF-8 JSON with deterministic key ordering and newline."""

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


def require_sha256(task_file: Path, expected_sha256: str) -> dict[str, int | str]:
    """Fail closed unless one file matches its exact expected SHA-256."""

    if not task_file.is_file():
        raise FailureTaxonomyError(f"SEALED_B649_K2_EVIDENCE_UNAVAILABLE: {task_file}")
    observed_sha256 = sha256_file(task_file)
    if observed_sha256 != expected_sha256:
        raise FailureTaxonomyError(
            "SEALED_B649_K2_EVIDENCE_UNAVAILABLE: "
            f"SHA-256 mismatch for {task_file}: "
            f"expected {expected_sha256}, observed {observed_sha256}"
        )
    return {
        "sha256": observed_sha256,
        "size_bytes": task_file.stat().st_size,
    }


def verify_authority_files(paths: AuthorityPaths) -> dict[str, dict[str, int | str]]:
    """Verify every file identity recorded by the pinned rolling-selector source."""

    verified: dict[str, dict[str, int | str]] = {}
    for name in sorted(EXPECTED_AUTHORITY_HASHES):
        details = require_sha256(paths.file(name), EXPECTED_AUTHORITY_HASHES[name])
        if details["size_bytes"] != EXPECTED_AUTHORITY_SIZES[name]:
            raise FailureTaxonomyError(
                "SEALED_B649_K2_EVIDENCE_UNAVAILABLE: "
                f"size mismatch for {paths.file(name)}"
            )
        verified[name] = details
    return verified


def _load_json_object(task_file: Path) -> JsonObject:
    try:
        parsed: object = json.loads(task_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FailureTaxonomyError(f"invalid JSON authority: {task_file}") from exc
    return _require_object(parsed, str(task_file))


def _validate_authority_contract(
    provenance: JsonObject,
    manifest: JsonObject,
    ranking: JsonObject,
) -> None:
    expected_values: tuple[tuple[object, object, str], ...] = (
        (
            provenance.get("schema_version"),
            "B649_EXACT_NATIVE_EVIDENCE_PROMOTION_PROVENANCE_V1",
            "provenance schema",
        ),
        (
            provenance.get("source_head"),
            SEALED_REPLAY_SOURCE_HEAD,
            "provenance source HEAD",
        ),
        (
            provenance.get("source_tree"),
            SEALED_REPLAY_SOURCE_TREE,
            "provenance source tree",
        ),
        (
            provenance.get("replay_sha256"),
            EXPECTED_AUTHORITY_HASHES["target_evidence.jsonl"],
            "provenance replay SHA-256",
        ),
        (
            provenance.get("ranking_sha256"),
            EXPECTED_AUTHORITY_HASHES["ranking.json"],
            "provenance ranking SHA-256",
        ),
        (
            provenance.get("manifest_sha256"),
            EXPECTED_AUTHORITY_HASHES["sealed_manifest.json"],
            "provenance manifest SHA-256",
        ),
        (provenance.get("replay_rows"), EXPECTED_TOTAL_ROW_COUNT, "provenance replay rows"),
        (provenance.get("metric"), "OFFICIAL_ANY_PRIZE", "provenance metric"),
        (
            provenance.get("canonical_relative_path"),
            CANONICAL_RELATIVE_EVIDENCE_PATH,
            "canonical evidence path",
        ),
        (manifest.get("run_id"), EXPECTED_RUN_ID, "manifest run ID"),
        (ranking.get("run_id"), EXPECTED_RUN_ID, "ranking run ID"),
    )
    for observed, expected, locator in expected_values:
        if observed != expected:
            raise FailureTaxonomyError(
                f"SEALED_AUTHORITY_CONTRACT_MISMATCH: {locator}: "
                f"expected {expected!r}, observed {observed!r}"
            )

    source = _require_object(manifest.get("source"), "manifest.source")
    if source.get("head") != SEALED_REPLAY_SOURCE_HEAD:
        raise FailureTaxonomyError("SEALED_AUTHORITY_CONTRACT_MISMATCH: manifest source HEAD")
    if source.get("tree") != SEALED_REPLAY_SOURCE_TREE:
        raise FailureTaxonomyError("SEALED_AUTHORITY_CONTRACT_MISMATCH: manifest source tree")
    if source.get("status") != "clean":
        raise FailureTaxonomyError("SEALED_AUTHORITY_CONTRACT_MISMATCH: manifest source status")

    execution_contract = _require_object(
        manifest.get("execution_contract"), "manifest.execution_contract"
    )
    if execution_contract.get("target_outcome_excluded") is not True:
        raise FailureTaxonomyError(
            "SEALED_AUTHORITY_CONTRACT_MISMATCH: target outcome exclusion"
        )
    ranking_contract = _require_object(
        ranking.get("ranking_contract"), "ranking.ranking_contract"
    )
    if ranking_contract.get("primary_metric") != "OFFICIAL_ANY_PRIZE_RATE":
        raise FailureTaxonomyError(
            "SEALED_AUTHORITY_CONTRACT_MISMATCH: ranking primary metric"
        )
    if ranking_contract.get("success_unit") != "distinct_target_draw":
        raise FailureTaxonomyError(
            "SEALED_AUTHORITY_CONTRACT_MISMATCH: ranking success unit"
        )


def _metadata_from_descriptor(raw: object, *, expected_ticket_count: int) -> StrategyMetadata:
    descriptor = _require_object(raw, "manifest catalog strategy")
    strategy_id = _require_str(descriptor.get("strategy_id"), "strategy_id")
    ticket_count = _require_int(descriptor.get("native_ticket_count"), "native_ticket_count")
    if ticket_count != expected_ticket_count:
        raise FailureTaxonomyError(
            f"SEALED_CATALOG_TICKET_COUNT_MISMATCH: {strategy_id}: {ticket_count}"
        )
    adapter_path = _require_str(descriptor.get("adapter_path"), "adapter_path")
    adapter_module = adapter_path.partition(":")[0]
    implementation_family = adapter_module.rsplit(".", maxsplit=1)[-1]
    provenance_values = _require_list(descriptor.get("provenance"), "provenance")
    provenance = tuple(
        _require_str(value, f"{strategy_id}.provenance") for value in provenance_values
    )
    return StrategyMetadata(
        strategy_id=strategy_id,
        display_name=_require_str(descriptor.get("display_name"), "display_name"),
        version=_require_str(descriptor.get("version"), "version"),
        adapter_path=adapter_path,
        implementation_family=implementation_family,
        provenance=provenance,
    )


def load_manifest_strategy_metadata(
    manifest: JsonObject,
) -> tuple[dict[str, StrategyMetadata], tuple[str, ...]]:
    """Load K2 families and derive the four wave26 authority IDs from provenance."""

    catalog = _require_object(manifest.get("catalog"), "manifest.catalog")
    strategy_groups = _require_object(catalog.get("strategies"), "manifest.catalog.strategies")
    k2_descriptors = _require_list(strategy_groups.get("k2"), "manifest.catalog.strategies.k2")
    k3_descriptors = _require_list(strategy_groups.get("k3"), "manifest.catalog.strategies.k3")

    metadata: dict[str, StrategyMetadata] = {}
    for raw_descriptor in k2_descriptors:
        item = _metadata_from_descriptor(raw_descriptor, expected_ticket_count=2)
        if item.strategy_id in metadata:
            raise FailureTaxonomyError(
                f"DUPLICATE_SEALED_CATALOG_STRATEGY: {item.strategy_id}"
            )
        metadata[item.strategy_id] = item
    if len(metadata) != EXPECTED_K2_STRATEGY_COUNT:
        raise FailureTaxonomyError(
            "SEALED_K2_STRATEGY_COUNT_MISMATCH: "
            f"expected {EXPECTED_K2_STRATEGY_COUNT}, observed {len(metadata)}"
        )

    wave26_ids: list[str] = []
    for raw_descriptor in k3_descriptors:
        item = _metadata_from_descriptor(raw_descriptor, expected_ticket_count=3)
        if WAVE26_NATIVE_HELPER_PROVENANCE in item.provenance:
            wave26_ids.append(item.strategy_id)
    derived_wave26_ids = tuple(sorted(wave26_ids))
    if derived_wave26_ids != EXPECTED_WAVE26_AUTHORITY_LINEAGE_IDS:
        raise FailureTaxonomyError(
            "SEALED_WAVE26_AUTHORITY_LINEAGE_MISMATCH: "
            f"expected {EXPECTED_WAVE26_AUTHORITY_LINEAGE_IDS}, "
            f"observed {derived_wave26_ids}"
        )

    universe = _require_object(manifest.get("universe"), "manifest.universe")
    raw_k2_ids = _require_list(universe.get("k2_strategy_ids"), "manifest.universe.k2_strategy_ids")
    universe_k2_ids = tuple(sorted(_require_str(value, "K2 strategy ID") for value in raw_k2_ids))
    if universe_k2_ids != tuple(sorted(metadata)):
        raise FailureTaxonomyError("SEALED_K2_UNIVERSE_IDENTITY_MISMATCH")
    return dict(sorted(metadata.items())), derived_wave26_ids


def load_evidence_rows(evidence_file: Path) -> LoadedEvidence:
    """Read all sealed rows while retaining only the K2 fields needed for attribution."""

    k2_rows: list[EvidenceRow] = []
    row_count_by_ticket: Counter[int] = Counter()
    schema_shapes: set[tuple[str, ...]] = set()
    total_rows = 0
    try:
        stream = evidence_file.open(encoding="utf-8")
    except OSError as exc:
        raise FailureTaxonomyError(
            f"SEALED_B649_K2_EVIDENCE_UNAVAILABLE: {evidence_file}"
        ) from exc

    with stream:
        for line_number, line in enumerate(stream, start=1):
            try:
                parsed: object = json.loads(line)
            except json.JSONDecodeError as exc:
                raise FailureTaxonomyError(
                    f"INVALID_SEALED_JSONL_ROW: line {line_number}"
                ) from exc
            row = _require_object(parsed, f"target evidence line {line_number}")
            total_rows += 1
            schema_shapes.add(tuple(sorted(row)))
            if row.get("schema_version") != EXPECTED_ROW_SCHEMA:
                raise FailureTaxonomyError(
                    f"SEALED_ROW_SCHEMA_MISMATCH: line {line_number}"
                )
            if row.get("run_id") != EXPECTED_RUN_ID:
                raise FailureTaxonomyError(f"SEALED_RUN_ID_MISMATCH: line {line_number}")
            ticket_count = _require_int(
                row.get("native_ticket_count"), f"line {line_number}.native_ticket_count"
            )
            row_count_by_ticket[ticket_count] += 1
            if ticket_count != 2:
                continue
            if row.get("target_outcome_excluded") is not True:
                raise FailureTaxonomyError(
                    f"CAUSAL_HISTORY_LEAKAGE: line {line_number}"
                )
            status = _require_str(row.get("replay_status"), f"line {line_number}.replay_status")
            reason = _optional_str(row.get("reason"), f"line {line_number}.reason")
            if status == "COMPLETE":
                if reason is not None:
                    raise FailureTaxonomyError(
                        f"COMPLETE_ROW_HAS_FAILURE_REASON: line {line_number}"
                    )
                if not isinstance(row.get("official_any_prize"), bool):
                    raise FailureTaxonomyError(
                        f"COMPLETE_ROW_MISSING_BOOLEAN_OUTCOME: line {line_number}"
                    )
                ticket_rows = _require_list(
                    row.get("ticket_evaluations"), f"line {line_number}.ticket_evaluations"
                )
                if len(ticket_rows) != 2:
                    raise FailureTaxonomyError(
                        f"COMPLETE_ROW_TICKET_COUNT_MISMATCH: line {line_number}"
                    )
            elif status == "EXECUTION_FAILURE":
                if reason is None:
                    raise FailureTaxonomyError(
                        f"EXECUTION_FAILURE_REASON_MISSING: line {line_number}"
                    )
            else:
                raise FailureTaxonomyError(
                    f"UNSUPPORTED_K2_REPLAY_STATUS: line {line_number}: {status}"
                )
            k2_rows.append(
                EvidenceRow(
                    strategy_id=_require_str(
                        row.get("strategy_id"), f"line {line_number}.strategy_id"
                    ),
                    strategy_version=_require_str(
                        row.get("strategy_version"),
                        f"line {line_number}.strategy_version",
                    ),
                    display_name=_require_str(
                        row.get("display_name"), f"line {line_number}.display_name"
                    ),
                    target_draw_number=_require_str(
                        row.get("target_draw_number"),
                        f"line {line_number}.target_draw_number",
                    ),
                    target_draw_date=_require_str(
                        row.get("target_draw_date"),
                        f"line {line_number}.target_draw_date",
                    ),
                    replay_status=status,
                    reason=reason,
                )
            )
    return LoadedEvidence(
        k2_rows=tuple(k2_rows),
        total_row_count=total_rows,
        row_count_by_native_ticket_count=dict(sorted(row_count_by_ticket.items())),
        row_schema_variant_count=len(schema_shapes),
    )


def _fraction_record(numerator: int, denominator: int) -> dict[str, int | float | str]:
    if denominator <= 0:
        return {"decimal": 0.0, "denominator": denominator, "exact": "0/0", "numerator": numerator}
    return {
        "decimal": round(numerator / denominator, 12),
        "denominator": denominator,
        "exact": f"{numerator}/{denominator}",
        "numerator": numerator,
    }


def _failure_category(reason: str) -> str:
    return reason.partition(":")[0].strip()


def _failure_runs(
    failure_targets: Sequence[str],
    target_index: Mapping[str, int],
) -> tuple[tuple[str, ...], ...]:
    if not failure_targets:
        return ()
    ordered = sorted(failure_targets, key=target_index.__getitem__)
    runs: list[list[str]] = [[ordered[0]]]
    for target_draw_number in ordered[1:]:
        if target_index[target_draw_number] == target_index[runs[-1][-1]] + 1:
            runs[-1].append(target_draw_number)
        else:
            runs.append([target_draw_number])
    return tuple(tuple(run) for run in runs)


def minimum_failure_cover_sets(
    failure_sets: Mapping[str, frozenset[str]],
    blocked_targets: frozenset[str],
) -> tuple[tuple[str, ...], ...]:
    """Return every lexically ordered minimum-cardinality diagnostic cover."""

    if not blocked_targets:
        return ((),)
    candidates = tuple(
        strategy_id
        for strategy_id in sorted(failure_sets)
        if failure_sets[strategy_id]
    )
    for cardinality in range(1, len(candidates) + 1):
        covers: list[tuple[str, ...]] = []
        for candidate_set in itertools.combinations(candidates, cardinality):
            covered: set[str] = set()
            for strategy_id in candidate_set:
                covered.update(failure_sets[strategy_id])
            if covered >= blocked_targets:
                covers.append(candidate_set)
        if covers:
            return tuple(covers)
    raise FailureTaxonomyError("FAILURE_TARGET_UNION_HAS_NO_STRATEGY_COVER")


def build_failure_taxonomy(
    rows: Iterable[EvidenceRow],
    strategy_metadata: Mapping[str, StrategyMetadata],
    wave26_authority_lineage_ids: Sequence[str],
    *,
    expected_target_count: int | None = None,
    expected_strategy_ids: Sequence[str] | None = None,
) -> JsonObject:
    """Build deterministic K2 strategy/target/family failure attribution."""

    rows_by_strategy: dict[str, dict[str, EvidenceRow]] = defaultdict(dict)
    target_dates: dict[str, str] = {}
    for row in rows:
        prior = rows_by_strategy[row.strategy_id].get(row.target_draw_number)
        if prior is not None:
            raise FailureTaxonomyError(
                "DUPLICATE_K2_STRATEGY_TARGET_ROW: "
                f"{row.strategy_id}/{row.target_draw_number}"
            )
        prior_date = target_dates.setdefault(row.target_draw_number, row.target_draw_date)
        if prior_date != row.target_draw_date:
            raise FailureTaxonomyError(
                f"K2_TARGET_DATE_DRIFT: {row.target_draw_number}"
            )
        rows_by_strategy[row.strategy_id][row.target_draw_number] = row

    observed_strategy_ids = tuple(sorted(rows_by_strategy))
    required_strategy_ids = (
        tuple(sorted(expected_strategy_ids))
        if expected_strategy_ids is not None
        else tuple(sorted(strategy_metadata))
    )
    if observed_strategy_ids != required_strategy_ids:
        raise FailureTaxonomyError(
            "K2_STRATEGY_UNIVERSE_MISMATCH: "
            f"expected {required_strategy_ids}, observed {observed_strategy_ids}"
        )
    if set(strategy_metadata) != set(required_strategy_ids):
        raise FailureTaxonomyError("K2_STRATEGY_METADATA_UNIVERSE_MISMATCH")

    ordered_targets = tuple(
        sorted(
            target_dates,
            key=lambda target: (
                date.fromisoformat(target_dates[target]),
                int(target),
            ),
        )
    )
    if expected_target_count is not None and len(ordered_targets) != expected_target_count:
        raise FailureTaxonomyError(
            "K2_TARGET_COUNT_MISMATCH: "
            f"expected {expected_target_count}, observed {len(ordered_targets)}"
        )
    expected_target_set = set(ordered_targets)
    for strategy_id in required_strategy_ids:
        target_set = set(rows_by_strategy[strategy_id])
        if target_set != expected_target_set:
            missing = sorted(expected_target_set - target_set)
            extra = sorted(target_set - expected_target_set)
            raise FailureTaxonomyError(
                f"K2_STRATEGY_TARGET_SET_MISMATCH: {strategy_id}: "
                f"missing={missing}, extra={extra}"
            )
        metadata = strategy_metadata[strategy_id]
        for row in rows_by_strategy[strategy_id].values():
            if row.display_name != metadata.display_name:
                raise FailureTaxonomyError(f"K2_DISPLAY_NAME_DRIFT: {strategy_id}")
            if row.strategy_version != metadata.version:
                raise FailureTaxonomyError(f"K2_STRATEGY_VERSION_DRIFT: {strategy_id}")

    target_index = {target: index for index, target in enumerate(ordered_targets)}
    failure_sets: dict[str, frozenset[str]] = {}
    for strategy_id in required_strategy_ids:
        failure_sets[strategy_id] = frozenset(
            target
            for target, row in rows_by_strategy[strategy_id].items()
            if row.replay_status == "EXECUTION_FAILURE"
        )
    blocked_target_values: set[str] = set()
    for strategy_failures in failure_sets.values():
        blocked_target_values.update(strategy_failures)
    blocked_targets = frozenset(blocked_target_values)

    failing_ids_by_target: dict[str, tuple[str, ...]] = {}
    for target in ordered_targets:
        failing_ids_by_target[target] = tuple(
            strategy_id
            for strategy_id in required_strategy_ids
            if target in failure_sets[strategy_id]
        )

    per_target_rows = [
        {
            "failing_strategy_count": len(failing_ids_by_target[target]),
            "failing_strategy_ids": list(failing_ids_by_target[target]),
            "target_draw_date": target_dates[target],
            "target_draw_number": target,
        }
        for target in ordered_targets
    ]
    per_target_distribution = Counter(
        len(failing_ids_by_target[target]) for target in ordered_targets
    )

    strategy_matrix: list[JsonObject] = []
    for strategy_id in required_strategy_ids:
        metadata = strategy_metadata[strategy_id]
        strategy_rows = rows_by_strategy[strategy_id]
        failures = tuple(sorted(failure_sets[strategy_id], key=target_index.__getitem__))
        complete_count = sum(
            row.replay_status == "COMPLETE" for row in strategy_rows.values()
        )
        reason_counts = Counter(
            cast(str, strategy_rows[target].reason) for target in failures
        )
        category_counts = Counter(
            _failure_category(cast(str, strategy_rows[target].reason))
            for target in failures
        )
        runs = _failure_runs(failures, target_index)
        isolated_targets = tuple(run[0] for run in runs if len(run) == 1)
        if not failures:
            failure_pattern = "NO_FAILURE"
        elif len(failures) == len(ordered_targets):
            failure_pattern = "PERSISTENT"
        elif len(runs) == 1:
            failure_pattern = "ISOLATED" if len(failures) == 1 else "CONTIGUOUS"
        else:
            failure_pattern = "INTERMITTENT"
        exclusive_targets = tuple(
            target
            for target in failures
            if failing_ids_by_target[target] == (strategy_id,)
        )
        strategy_matrix.append(
            {
                "adapter_path": metadata.adapter_path,
                "blockage_coverage_fraction": _fraction_record(
                    len(failures), len(ordered_targets)
                ),
                "complete_target_count": complete_count,
                "display_name": metadata.display_name,
                "evaluated_target_count": len(strategy_rows),
                "exclusive_blockage_fraction": _fraction_record(
                    len(exclusive_targets), len(ordered_targets)
                ),
                "exclusive_blockage_target_count": len(exclusive_targets),
                "execution_failure_count": len(failures),
                "failure_categories": dict(sorted(category_counts.items())),
                "failure_pattern": failure_pattern,
                "failure_reason_counts": dict(sorted(reason_counts.items())),
                "failure_run_count": len(runs),
                "failure_runs": [
                    {
                        "first_target": run[0],
                        "last_target": run[-1],
                        "target_count": len(run),
                        "targets": list(run),
                    }
                    for run in runs
                ],
                "failure_targets": list(failures),
                "first_failure_target": failures[0] if failures else None,
                "first_failure_target_date": (
                    target_dates[failures[0]] if failures else None
                ),
                "implementation_family": metadata.implementation_family,
                "isolated_failure_target_count": len(isolated_targets),
                "isolated_failure_targets": list(isolated_targets),
                "last_failure_target": failures[-1] if failures else None,
                "last_failure_target_date": (
                    target_dates[failures[-1]] if failures else None
                ),
                "single_strategy_resolution_restored_target_count": len(
                    exclusive_targets
                ),
                "strategy_id": strategy_id,
                "strategy_version": metadata.version,
                "successful_target_count": complete_count,
            }
        )

    pattern_targets: dict[tuple[str, ...], list[str]] = defaultdict(list)
    for target in ordered_targets:
        pattern_targets[failing_ids_by_target[target]].append(target)
    intersection_patterns = [
        {
            "failing_strategy_count": len(strategy_ids),
            "failing_strategy_ids": list(strategy_ids),
            "target_count": len(targets),
            "targets": targets,
        }
        for strategy_ids, targets in sorted(
            pattern_targets.items(), key=lambda item: (len(item[0]), item[0])
        )
    ]

    failing_strategy_ids = tuple(
        row["strategy_id"]
        for row in strategy_matrix
        if cast(int, row["execution_failure_count"]) > 0
    )
    pairwise_intersections: list[JsonObject] = []
    for left, right in itertools.combinations(failing_strategy_ids, 2):
        targets = tuple(
            sorted(failure_sets[left] & failure_sets[right], key=target_index.__getitem__)
        )
        if targets:
            pairwise_intersections.append(
                {
                    "left_strategy_id": left,
                    "right_strategy_id": right,
                    "target_count": len(targets),
                    "targets": list(targets),
                }
            )

    family_strategy_ids: dict[str, list[str]] = defaultdict(list)
    for strategy_id in required_strategy_ids:
        family_strategy_ids[strategy_metadata[strategy_id].implementation_family].append(
            strategy_id
        )
    family_matrix: list[JsonObject] = []
    for family in sorted(family_strategy_ids):
        family_ids = tuple(sorted(family_strategy_ids[family]))
        family_failure_target_values: set[str] = set()
        for strategy_id in family_ids:
            family_failure_target_values.update(failure_sets[strategy_id])
        family_failure_targets = frozenset(family_failure_target_values)
        failure_occurrences = sum(len(failure_sets[strategy_id]) for strategy_id in family_ids)
        family_matrix.append(
            {
                "blockage_coverage_fraction": _fraction_record(
                    len(family_failure_targets), len(ordered_targets)
                ),
                "failing_strategy_count": sum(
                    bool(failure_sets[strategy_id]) for strategy_id in family_ids
                ),
                "failure_occurrence_count": failure_occurrences,
                "failure_target_union_count": len(family_failure_targets),
                "implementation_family": family,
                "strategy_count": len(family_ids),
                "strategy_ids": list(family_ids),
            }
        )

    cover_sets = minimum_failure_cover_sets(failure_sets, blocked_targets)
    persistent_strategy_ids = tuple(
        cast(str, row["strategy_id"])
        for row in strategy_matrix
        if row["failure_pattern"] == "PERSISTENT"
    )
    strategies_with_isolated_failures = [
        {
            "isolated_failure_target_count": row["isolated_failure_target_count"],
            "isolated_failure_targets": row["isolated_failure_targets"],
            "strategy_id": row["strategy_id"],
        }
        for row in strategy_matrix
        if cast(int, row["isolated_failure_target_count"]) > 0
    ]

    wave26_ids = tuple(sorted(wave26_authority_lineage_ids))
    k2_wave26_ids = tuple(sorted(set(required_strategy_ids) & set(wave26_ids)))
    failing_wave26_ids = tuple(sorted(set(failing_strategy_ids) & set(wave26_ids)))

    recommended_strategy_id: str | None = None
    if failing_strategy_ids:
        recommended_strategy_id = min(
            failing_strategy_ids,
            key=lambda strategy_id: (-len(failure_sets[strategy_id]), strategy_id),
        )
    recommended_row = next(
        (
            row
            for row in strategy_matrix
            if row["strategy_id"] == recommended_strategy_id
        ),
        None,
    )
    recommended_restoration = (
        cast(int, recommended_row["single_strategy_resolution_restored_target_count"])
        if recommended_row is not None
        else 0
    )
    recommended_reason = (
        next(iter(cast(dict[str, int], recommended_row["failure_reason_counts"])), None)
        if recommended_row is not None
        else None
    )

    return {
        "answers": {
            "1_persistent_or_few": {
                "answer": "YES_ONE_PERSISTENT_PRIMARY",
                "evidence": (
                    f"{persistent_strategy_ids[0]} fails all {len(ordered_targets)} targets."
                    if persistent_strategy_ids
                    else "No strategy fails every target."
                ),
            },
            "2_distributed_failures": {
                "answer": "NO_NOT_PRIMARY_CAUSE",
                "evidence": (
                    f"{len(failing_strategy_ids)} strategies fail at least once; "
                    f"{len(persistent_strategy_ids)} persistent strategy covers the full blockage."
                ),
            },
            "3_family_concentration": {
                "answer": "YES_PRIMARY_BLOCKAGE_CONCENTRATED",
                "evidence": (
                    f"{recommended_row['implementation_family']} covers "
                    f"{len(failure_sets[recommended_strategy_id])}/"
                    f"{len(ordered_targets)} blocked targets."
                    if recommended_row is not None and recommended_strategy_id is not None
                    else "No failing family."
                ),
            },
            "4_wave26_involvement": {
                "answer": "NO",
                "evidence": (
                    "The four sealed-manifest wave26 provenance IDs are K3-only; "
                    "their K2 and K2-failure intersections are empty."
                ),
            },
            "5_one_bounded_rca_target": {
                "answer": "YES",
                "evidence": (
                    f"RCA of {recommended_strategy_id} could restore "
                    f"{recommended_restoration}/{len(ordered_targets)} complete-universe "
                    "targets if that failure alone were resolved."
                ),
            },
            "6_full_restoration_scope": {
                "answer": "MULTIPLE_STRATEGY_CHANGES_REQUIRED_FOR_ALL_750",
                "evidence": (
                    f"All {len(failing_strategy_ids)} failing strategy implementations "
                    "must have their distinct failure rows resolved for full coverage."
                ),
            },
        },
        "blocked_target_union": {
            "first_target": (
                min(blocked_targets, key=target_index.__getitem__)
                if blocked_targets
                else None
            ),
            "last_target": (
                max(blocked_targets, key=target_index.__getitem__)
                if blocked_targets
                else None
            ),
            "target_count": len(blocked_targets),
            "targets": sorted(blocked_targets, key=target_index.__getitem__),
        },
        "diagnostic_cover_sets": {
            "meaning": (
                "strategy failure-set union covers every blocked target; "
                "not an exclusion authorization"
            ),
            "minimum_cardinality": len(cover_sets[0]),
            "strategy_sets": [list(cover) for cover in cover_sets],
        },
        "failure_intersection_patterns": intersection_patterns,
        "failing_strategy_ids": list(failing_strategy_ids),
        "fixed_universe": {
            "blocked_target_count": len(blocked_targets),
            "complete_target_count": len(ordered_targets) - len(blocked_targets),
            "strategy_count": len(required_strategy_ids),
            "target_count": len(ordered_targets),
        },
        "full_coverage_restoration_diagnostic": {
            "requires_all_failing_strategy_ids": list(failing_strategy_ids),
            "strategy_count": len(failing_strategy_ids),
        },
        "implementation_family_failure_matrix": family_matrix,
        "pairwise_failure_intersections": pairwise_intersections,
        "per_strategy_failure_matrix": strategy_matrix,
        "per_target_failing_strategy_count": per_target_rows,
        "per_target_failing_strategy_count_distribution": {
            str(count): target_count
            for count, target_count in sorted(per_target_distribution.items())
        },
        "recommended_next_task": {
            "repair_authorized": False,
            "recommended_rca_target": recommended_strategy_id,
            "failure_reason": recommended_reason,
            "implementation_family": (
                recommended_row["implementation_family"]
                if recommended_row is not None
                else None
            ),
            "rationale": (
                f"Persistent failure covers all {len(ordered_targets)} blocked targets; "
                f"resolving it alone could restore {recommended_restoration} complete targets."
            ),
            "task_shape": "BOUNDED_IMPLEMENTATION_RCA_ONLY",
        },
        "strategies_failing_every_target": list(persistent_strategy_ids),
        "strategies_with_isolated_failures": strategies_with_isolated_failures,
        "wave26_authority_lineage": {
            "involved_in_k2_failure_set": list(failing_wave26_ids),
            "involved_in_k2_universe": list(k2_wave26_ids),
            "strategy_ids": list(wave26_ids),
        },
    }


def _validate_loaded_evidence(loaded: LoadedEvidence) -> None:
    if loaded.total_row_count != EXPECTED_TOTAL_ROW_COUNT:
        raise FailureTaxonomyError(
            "SEALED_REPLAY_ROW_COUNT_MISMATCH: "
            f"expected {EXPECTED_TOTAL_ROW_COUNT}, observed {loaded.total_row_count}"
        )
    if len(loaded.k2_rows) != EXPECTED_K2_ROW_COUNT:
        raise FailureTaxonomyError(
            "SEALED_K2_ROW_COUNT_MISMATCH: "
            f"expected {EXPECTED_K2_ROW_COUNT}, observed {len(loaded.k2_rows)}"
        )
    if loaded.row_count_by_native_ticket_count != {2: 14_250, 3: 14_250}:
        raise FailureTaxonomyError(
            "SEALED_NATIVE_TICKET_COUNT_DISTRIBUTION_MISMATCH: "
            f"{loaded.row_count_by_native_ticket_count}"
        )
    if loaded.row_schema_variant_count != 1:
        raise FailureTaxonomyError(
            "SEALED_ROW_SCHEMA_SHAPE_DRIFT: "
            f"{loaded.row_schema_variant_count} variants"
        )


def validate_ranking_cross_check(taxonomy: JsonObject, ranking: JsonObject) -> JsonObject:
    """Cross-check the independent row recount against sealed RECENT_750 coverage."""

    coverage = _require_object(ranking.get("coverage"), "ranking.coverage")
    k2_coverage = _require_object(coverage.get("K2"), "ranking.coverage.K2")
    matrix = _require_list(
        taxonomy.get("per_strategy_failure_matrix"),
        "taxonomy.per_strategy_failure_matrix",
    )
    observed_ids: list[str] = []
    for raw_matrix_row in matrix:
        matrix_row = _require_object(raw_matrix_row, "per-strategy matrix row")
        strategy_id = _require_str(matrix_row.get("strategy_id"), "matrix strategy ID")
        observed_ids.append(strategy_id)
        strategy_coverage = _require_object(
            k2_coverage.get(strategy_id), f"ranking.coverage.K2.{strategy_id}"
        )
        recent_750 = _require_object(
            strategy_coverage.get("RECENT_750"),
            f"ranking.coverage.K2.{strategy_id}.RECENT_750",
        )
        expected_counts = {
            "COMPLETE": _require_int(
                matrix_row.get("complete_target_count"), "matrix complete count"
            ),
            "EXECUTION_FAILURE": _require_int(
                matrix_row.get("execution_failure_count"), "matrix failure count"
            ),
        }
        expected_counts = {key: value for key, value in expected_counts.items() if value}
        raw_status_counts = _require_object(
            recent_750.get("status_counts"), f"{strategy_id} status counts"
        )
        observed_counts = {
            key: _require_int(value, f"{strategy_id}.{key}")
            for key, value in sorted(raw_status_counts.items())
        }
        if observed_counts != expected_counts:
            raise FailureTaxonomyError(
                f"SEALED_RANKING_CROSS_CHECK_MISMATCH: {strategy_id}: "
                f"expected {expected_counts}, observed {observed_counts}"
            )
        if recent_750.get("observations") != matrix_row.get("complete_target_count"):
            raise FailureTaxonomyError(
                f"SEALED_RANKING_OBSERVATION_MISMATCH: {strategy_id}"
            )
    if tuple(sorted(observed_ids)) != tuple(sorted(k2_coverage)):
        raise FailureTaxonomyError("SEALED_RANKING_K2_UNIVERSE_MISMATCH")
    return {
        "status": "PASS",
        "strategy_count": len(observed_ids),
        "window": "RECENT_750",
    }


def analyze_authority(authority_directory: Path) -> JsonObject:
    """Verify, load, recount, cross-check, and attribute the exact sealed authority."""

    paths = AuthorityPaths(authority_directory)
    before_hashes = verify_authority_files(paths)
    provenance = _load_json_object(paths.file("promotion_provenance.json"))
    manifest = _load_json_object(paths.file("sealed_manifest.json"))
    ranking = _load_json_object(paths.file("ranking.json"))
    _validate_authority_contract(provenance, manifest, ranking)
    metadata, wave26_ids = load_manifest_strategy_metadata(manifest)
    loaded = load_evidence_rows(paths.file("target_evidence.jsonl"))
    _validate_loaded_evidence(loaded)
    taxonomy = build_failure_taxonomy(
        loaded.k2_rows,
        metadata,
        wave26_ids,
        expected_target_count=EXPECTED_TARGET_COUNT,
        expected_strategy_ids=tuple(metadata),
    )
    ranking_cross_check = validate_ranking_cross_check(taxonomy, ranking)
    after_hashes = verify_authority_files(paths)
    if after_hashes != before_hashes:
        raise FailureTaxonomyError("SEALED_AUTHORITY_CHANGED_DURING_ANALYSIS")

    fixed_universe = _require_object(taxonomy.get("fixed_universe"), "fixed_universe")
    if fixed_universe.get("complete_target_count") != 0:
        raise FailureTaxonomyError("B649_K2_ZERO_FIXED_UNIVERSE_NOT_REPRODUCED")

    return {
        "boundaries": {
            "B649_K2_REPAIR": "NOT RUN",
            "CANONICAL_STRATEGY_EXCLUSION": "NOT AUTHORIZED",
            "DB_ACCESS": "NO",
            "NEW_HISTORICAL_REPLAY": "NOT RUN",
        },
        "data_quality": {
            "duplicate_strategy_target_row_count": 0,
            "k2_row_count": len(loaded.k2_rows),
            "null_required_field_count": 0,
            "ranking_cross_check": ranking_cross_check,
            "row_count_by_native_ticket_count": {
                str(key): value
                for key, value in sorted(loaded.row_count_by_native_ticket_count.items())
            },
            "row_schema_variant_count": loaded.row_schema_variant_count,
            "target_identity_drift_count": 0,
            "total_row_count": loaded.total_row_count,
        },
        "schema_version": SCHEMA_VERSION,
        "source_identity": {
            "authority_directory": str(authority_directory.resolve()),
            "authority_files": before_hashes,
            "canonical_relative_evidence_path": CANONICAL_RELATIVE_EVIDENCE_PATH,
            "hash_verified_before_after_load": True,
            "rolling_selector_source_commit": ROLLING_SELECTOR_SOURCE_COMMIT,
            "rolling_selector_source_tree": ROLLING_SELECTOR_SOURCE_TREE,
            "run_id": EXPECTED_RUN_ID,
            "sealed_replay_source_head": SEALED_REPLAY_SOURCE_HEAD,
            "sealed_replay_source_tree": SEALED_REPLAY_SOURCE_TREE,
        },
        "study_scope": {
            "failure_attribution_only": True,
            "lottery_id": "B649",
            "native_ticket_count": 2,
            "strategy_count": EXPECTED_K2_STRATEGY_COUNT,
            "target_count": EXPECTED_TARGET_COUNT,
        },
        "task_id": TASK_ID,
        "taxonomy": taxonomy,
    }


def _markdown_escape(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def render_markdown(result: JsonObject) -> str:
    """Render a deterministic human-readable report from the JSON result."""

    source = _require_object(result.get("source_identity"), "result.source_identity")
    quality = _require_object(result.get("data_quality"), "result.data_quality")
    taxonomy = _require_object(result.get("taxonomy"), "result.taxonomy")
    fixed = _require_object(taxonomy.get("fixed_universe"), "taxonomy.fixed_universe")
    matrix = _require_list(
        taxonomy.get("per_strategy_failure_matrix"),
        "taxonomy.per_strategy_failure_matrix",
    )
    distribution = _require_object(
        taxonomy.get("per_target_failing_strategy_count_distribution"),
        "taxonomy target distribution",
    )
    cover = _require_object(taxonomy.get("diagnostic_cover_sets"), "taxonomy cover")
    answers = _require_object(taxonomy.get("answers"), "taxonomy.answers")
    wave26 = _require_object(
        taxonomy.get("wave26_authority_lineage"), "taxonomy.wave26_authority_lineage"
    )
    recommended = _require_object(
        taxonomy.get("recommended_next_task"), "taxonomy.recommended_next_task"
    )
    ranking_cross_check = _require_object(
        quality["ranking_cross_check"], "ranking cross-check"
    )
    cover_sets_text = json.dumps(
        cover["strategy_sets"], ensure_ascii=False, sort_keys=True
    )

    lines = [
        "# B649 K2 fixed-universe failure taxonomy R1",
        "",
        "## Outcome",
        "",
        (
            "B649 K2 has zero complete fixed-universe targets because "
            "`legacy_biglotto__quick_ml_predict__8b7ba0b52e2d` fails all 750 targets. "
            "A second strategy, `legacy_biglotto__backtest_radical_strategy__e54cc0812bc6`, "
            "fails intermittently on 29 of those same targets."
        ),
        "",
        (
            "This is failure attribution only. No strategy was repaired or excluded, no replay "
            "was regenerated, and no database was accessed."
        ),
        "",
        "## Source identity and data quality",
        "",
        (
            f"- Rolling-selector source: `{source['rolling_selector_source_commit']}` / "
            f"`{source['rolling_selector_source_tree']}`"
        ),
        (
            f"- Sealed replay source: `{source['sealed_replay_source_head']}` / "
            f"`{source['sealed_replay_source_tree']}`"
        ),
        f"- Target evidence SHA-256: `{EXPECTED_AUTHORITY_HASHES['target_evidence.jsonl']}`",
        f"- Authority directory: `{source['authority_directory']}`",
        f"- Hash stability before/after load: `{source['hash_verified_before_after_load']}`",
        f"- Rows: {quality['total_row_count']} total; {quality['k2_row_count']} K2",
        (
            f"- K2 universe: {fixed['strategy_count']} strategies x "
            f"{fixed['target_count']} targets"
        ),
        f"- Duplicate strategy-target rows: {quality['duplicate_strategy_target_row_count']}",
        f"- Sealed ranking RECENT_750 cross-check: `{ranking_cross_check['status']}`",
        "",
        "## Per-strategy failure matrix",
        "",
        (
            "| Strategy ID | Family | Evaluated | Complete | EXECUTION_FAILURE | "
            "Pattern | First failure | Last failure | Blockage share | "
            "Exclusive targets | Reason/category |"
        ),
        "|---|---:|---:|---:|---:|---|---|---|---:|---:|---|",
    ]
    for raw_row in matrix:
        row = _require_object(raw_row, "strategy matrix row")
        reasons = _require_object(row.get("failure_reason_counts"), "failure reasons")
        reason_text = "; ".join(f"{key} x {value}" for key, value in reasons.items()) or "—"
        fraction = _require_object(row.get("blockage_coverage_fraction"), "blockage fraction")
        lines.append(
            "| "
            + " | ".join(
                _markdown_escape(value)
                for value in (
                    f"`{row['strategy_id']}`",
                    f"`{row['implementation_family']}`",
                    row["evaluated_target_count"],
                    row["complete_target_count"],
                    row["execution_failure_count"],
                    row["failure_pattern"],
                    row["first_failure_target"] or "—",
                    row["last_failure_target"] or "—",
                    fraction["exact"],
                    row["exclusive_blockage_target_count"],
                    reason_text,
                )
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Target-level blockage",
            "",
            (
                f"- Union of failure targets: **{fixed['blocked_target_count']}/"
                f"{fixed['target_count']}**"
            ),
            f"- Complete fixed-universe targets: **{fixed['complete_target_count']}**",
            f"- Targets with one failing strategy: **{distribution.get('1', 0)}**",
            f"- Targets with two failing strategies: **{distribution.get('2', 0)}**",
            (
                "- Exact per-target failing-strategy rows and the full 750-target "
                "union are in the JSON artifact."
            ),
            "",
            "### Dual-failure targets",
            "",
        ]
    )
    patterns = _require_list(
        taxonomy.get("failure_intersection_patterns"), "failure intersection patterns"
    )
    dual_targets: list[str] = []
    for raw_pattern in patterns:
        pattern = _require_object(raw_pattern, "failure intersection pattern")
        if pattern.get("failing_strategy_count") == 2:
            dual_targets = [
                _require_str(value, "dual-failure target")
                for value in _require_list(pattern.get("targets"), "dual targets")
            ]
    lines.append(", ".join(f"`{target}`" for target in dual_targets) if dual_targets else "None.")

    lines.extend(
        [
            "",
            "## Intersection, isolation, and cover diagnostics",
            "",
            "- `quick_ml_predict` failure set: 750 targets (persistent, one contiguous run).",
            "- `backtest_radical_strategy` failure set: 29 targets (intermittent).",
            (
                "- Pairwise intersection: 29 targets; the radical failure set is a "
                "strict subset of the QuickML failure set."
            ),
            f"- Minimum diagnostic failure cover cardinality: **{cover['minimum_cardinality']}**.",
            f"- Minimum cover set(s): `{cover_sets_text}`.",
            "- A cover set is descriptive only and does not authorize strategy removal.",
            "",
            "## Implementation-family concentration",
            "",
            (
                "The primary blockage is concentrated in `biglotto_wave12`: its "
                "QuickML strategy fails all 750 targets with `Wave12FrozenSourceError: "
                "FROZEN_SOURCE_PATTERN_SLICE_INDEX_ERROR`. The separate "
                "`biglotto_radical_gap` family adds 29 overlapping `InvalidOutput` "
                "failures and no exclusive blocked targets."
            ),
            "",
            "## Wave26 authority lineage",
            "",
        ]
    )
    for strategy_id in _require_list(wave26.get("strategy_ids"), "wave26 IDs"):
        lines.append(f"- `{strategy_id}`")
    lines.extend(
        [
            "",
            (
                "All four are K3-only in the sealed manifest. Their intersection "
                "with the K2 universe and K2 failure set is empty."
            ),
            "",
            "## Required questions",
            "",
        ]
    )
    for index, key in enumerate(sorted(answers), start=1):
        answer = _require_object(answers[key], f"answer {key}")
        lines.append(f"{index}. **{answer['answer']}** — {answer['evidence']}")

    lines.extend(
        [
            "",
            "## Recommended bounded next task",
            "",
            (
                f"Run implementation RCA only for "
                f"`{recommended['recommended_rca_target']}` in "
                f"`{recommended['implementation_family']}`, focused on "
                f"`{recommended['failure_reason']}`. If that persistent failure were "
                "resolved, 721/750 targets would become complete-universe comparable; "
                "full 750-target restoration would still require a separate RCA/"
                "remediation decision for the 29 radical-gap failures."
            ),
            "",
            "No repair is authorized or performed by this task.",
            "",
            "## Explicit boundaries",
            "",
            "B649_K2_REPAIR = NOT RUN",
            "",
            "DB_ACCESS = NO",
            "",
            "NEW_HISTORICAL_REPLAY = NOT RUN",
            "",
            "CANONICAL_STRATEGY_EXCLUSION = NOT AUTHORIZED",
            "",
        ]
    )
    return "\n".join(lines)


def _parse_arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--authority-directory",
        type=Path,
        default=DEFAULT_AUTHORITY_DIRECTORY,
    )
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-report", type=Path, default=DEFAULT_OUTPUT_REPORT)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parse_arguments(argv)
    authority_directory = cast(Path, arguments.authority_directory)
    output_json = cast(Path, arguments.output_json)
    output_report = cast(Path, arguments.output_report)
    if not output_json.parent.is_dir() or not output_report.parent.is_dir():
        raise FailureTaxonomyError("OUTPUT_PARENT_DIRECTORY_MISSING")

    result = analyze_authority(authority_directory)
    result_bytes = canonical_json_bytes(result)
    report_bytes = render_markdown(result).encode("utf-8")
    output_json.write_bytes(result_bytes)
    output_report.write_bytes(report_bytes)
    print(
        json.dumps(
            {
                "output_json": str(output_json),
                "output_json_sha256": hashlib.sha256(result_bytes).hexdigest(),
                "output_report": str(output_report),
                "output_report_sha256": hashlib.sha256(report_bytes).hexdigest(),
                "status": "PASS",
                "task_id": TASK_ID,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
