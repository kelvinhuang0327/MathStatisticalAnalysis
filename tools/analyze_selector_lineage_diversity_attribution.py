"""Attribute sealed rolling-selector outcomes to frozen structural lineage identities.

The analyzer reads four exact JSON blobs from Git object storage, never from mutable
source worktrees. It performs no replay, database access, strategy execution, selector
construction, optimization, or semantic-equivalence inference.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import itertools
import json
import re
import subprocess
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from fractions import Fraction
from pathlib import Path
from typing import Any, cast

TASK_ID = "SELECTOR_LINEAGE_DIVERSITY_ATTRIBUTION_R1"
STUDY_ID = "SELECTOR_LINEAGE_DIVERSITY_ATTRIBUTION_V1"
SCHEMA_VERSION = "SELECTOR_LINEAGE_DIVERSITY_ATTRIBUTION_RESULT_V1"

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_JSON = (
    REPOSITORY_ROOT / "docs/research/matrix-native-results/"
    "selector-lineage-diversity-attribution-r1-result.json"
)
DEFAULT_OUTPUT_REPORT = (
    REPOSITORY_ROOT / "docs/research/selector-lineage-diversity-attribution-r1.md"
)

EXPECTED_CANONICAL_STRATEGY_COUNT = 135
EXPECTED_BASE_RESOLVED_STRATEGY_COUNT = 131
EXPECTED_SUPPLEMENTAL_STRATEGY_COUNT = 4
EXPECTED_CELL_COUNT = 22
EXPECTED_EXPERIMENT_COUNT = 66

WINDOWS: tuple[tuple[str, str, int], ...] = (
    ("W50", "SHORT", 50),
    ("W300", "MEDIUM", 300),
    ("W750", "LONG", 750),
)
HISTORICAL_SIGNS = ("POSITIVE", "ZERO", "NEGATIVE", "INCONCLUSIVE")
DIVERSITY_CLASSES = (
    "NO_SWITCH",
    "PARAMETER_SIBLING_DIVERSITY_ONLY",
    "DISTINCT_BINDING_DIVERSITY",
    "MIXED_DIVERSITY",
    "LINEAGE_SOURCE_INCONSISTENT",
)
REPEATED_POSITIVE_CELL_IDS = (
    "P638:K2",
    "P638:K3",
    "T539:K1",
    "T539:K2",
    "T539:K3",
)
P638_BRIDGE_STRATEGY_IDS = (
    "power_c01_recency_decay_1bet",
    "power_c02_gap_overdue_1bet",
    "power_c03_pair_centrality_1bet",
    "power_c04_zone_balanced_1bet",
    "power_c05_dispersion_match_1bet",
    "power_c06_regime_cusum_1bet",
    "power_c07_borda_ensemble_1bet",
)

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class AttributionDataError(ValueError):
    """A frozen source cannot support the requested fail-closed attribution."""


@dataclass(frozen=True, slots=True)
class ArtifactSpec:
    """Immutable Git identity for one sealed JSON authority."""

    key: str
    commit: str
    tree: str
    relative_path: str
    sha256: str


@dataclass(frozen=True, slots=True)
class LoadedArtifact:
    """One verified JSON authority and its observed immutable metadata."""

    spec: ArtifactSpec
    blob_oid: str
    size_bytes: int
    payload: dict[str, Any]

    def identity_payload(self) -> dict[str, Any]:
        return {
            "blob_oid": self.blob_oid,
            "commit": self.spec.commit,
            "path": self.spec.relative_path,
            "sha256": self.spec.sha256,
            "size_bytes": self.size_bytes,
            "tree": self.spec.tree,
        }


@dataclass(frozen=True, slots=True)
class LineageIdentity:
    """A normalized read-only identity from the two frozen lineage authorities."""

    strategy_id: str
    source_authority: str
    source_classification: str
    binding_fingerprint_sha256: str
    binding_identity: str
    callable_identity: str
    callable_family_label: str
    game_identities: tuple[str, ...]
    combined_classification: str = ""

    def as_payload(self) -> dict[str, Any]:
        return {
            "binding_fingerprint_sha256": self.binding_fingerprint_sha256,
            "binding_identity": self.binding_identity,
            "callable_family_label": self.callable_family_label,
            "callable_identity": self.callable_identity,
            "combined_classification": self.combined_classification,
            "game_identities": list(self.game_identities),
            "source_authority": self.source_authority,
            "source_classification": self.source_classification,
            "strategy_id": self.strategy_id,
        }


SELECTOR_ARTIFACT = ArtifactSpec(
    key="rolling_selector",
    commit="abc367bd6d8b59d01ecc4d79e56c787bbc03cd20",
    tree="bf430efd66b7ce1ac38ee04fb0052e8c55cc972c",
    relative_path=(
        "docs/research/matrix-native-results/"
        "strategy-matrix-causal-rolling-selector-pilot-r1-result.json"
    ),
    sha256="04df0bfdffcf4ecc05d4f2ac3f58cfa1fa301061c5f1c30e549ddc3b5b174157",
)
DECOMPOSITION_ARTIFACT = ArtifactSpec(
    key="rolling_decomposition",
    commit="cc9bd1088a9f871618725d0910874283e0318459",
    tree="7d05638845dc553fa20d793ceba8ce1aceff71ee",
    relative_path=(
        "docs/research/matrix-native-results/"
        "rolling-selector-stability-decomposition-r1-result.json"
    ),
    sha256="92ffb4d5678d403322791de1e3cb133d3bdb91c9c911142f67f4f3f4ee8979c9",
)
BASE_LINEAGE_ARTIFACT = ArtifactSpec(
    key="base_lineage",
    commit="b78eda6a2c9858413c6d1a4cb182ac1083fe9454",
    tree="2656632e9681e075151a6687414a02a84440bfa3",
    relative_path=(
        "docs/research/matrix-native-results/"
        "strategy-matrix-static-lineage-redundancy-map-r1-result.json"
    ),
    sha256="f2f7d1fd5e08083124aaeb43dfe889f96012f6020b9daafae49f6368f832bfad",
)
WAVE26_ARTIFACT = ArtifactSpec(
    key="wave26_supplement",
    commit="139b3aae0ec52ef947796ee7db68cd38a9bf9f5c",
    tree="8467da3725fb323d21fc647b7d6d02ea953a68a6",
    relative_path=(
        "docs/research/matrix-native-results/wave26-dynamic-binding-resolution-r1-result.json"
    ),
    sha256="193b9301640e5561cb495903ce0d6710c47886b72b5f603542505a82f9218db3",
)
ARTIFACT_SPECS = (
    SELECTOR_ARTIFACT,
    DECOMPOSITION_ARTIFACT,
    BASE_LINEAGE_ARTIFACT,
    WAVE26_ARTIFACT,
)


def canonical_json_bytes(payload: Mapping[str, Any]) -> bytes:
    """Serialize a result with deterministic ordering and one trailing newline."""

    return (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def _as_mapping(value: object, *, context: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise AttributionDataError(f"{context} must be an object")
    return cast(Mapping[str, Any], value)


def _as_list(value: object, *, context: str) -> list[Any]:
    if not isinstance(value, list):
        raise AttributionDataError(f"{context} must be an array")
    return cast(list[Any], value)


def _as_string(value: object, *, context: str) -> str:
    if not isinstance(value, str) or not value:
        raise AttributionDataError(f"{context} must be a nonempty string")
    return value


def _as_optional_string(value: object, *, context: str) -> str | None:
    if value is None:
        return None
    return _as_string(value, context=context)


def _as_nonnegative_int(value: object, *, context: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise AttributionDataError(f"{context} must be a nonnegative integer")
    return value


def _as_positive_int(value: object, *, context: str) -> int:
    number = _as_nonnegative_int(value, context=context)
    if number == 0:
        raise AttributionDataError(f"{context} must be positive")
    return number


def _as_sha256(value: object, *, context: str) -> str:
    digest = _as_string(value, context=context)
    if _SHA256_PATTERN.fullmatch(digest) is None:
        raise AttributionDataError(f"{context} must be a lowercase SHA-256")
    return digest


def _git_bytes(repository_root: Path, arguments: Sequence[str]) -> bytes:
    command = ["git", "-C", str(repository_root), *arguments]
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        raise AttributionDataError(f"GIT_OBJECT_RESOLUTION_FAILED: {' '.join(arguments)}: {detail}")
    return completed.stdout


def _git_text(repository_root: Path, arguments: Sequence[str]) -> str:
    return _git_bytes(repository_root, arguments).decode("utf-8").strip()


def load_frozen_artifact(spec: ArtifactSpec, repository_root: Path) -> LoadedArtifact:
    """Resolve and verify one regular JSON blob from an exact Git commit."""

    observed_commit = _git_text(repository_root, ("rev-parse", f"{spec.commit}^{{commit}}"))
    observed_tree = _git_text(repository_root, ("rev-parse", f"{spec.commit}^{{tree}}"))
    if observed_commit != spec.commit or observed_tree != spec.tree:
        raise AttributionDataError(
            "FROZEN_GIT_IDENTITY_MISMATCH: "
            f"{spec.key} expected {spec.commit}/{spec.tree}, "
            f"observed {observed_commit}/{observed_tree}"
        )

    metadata_bytes = _git_bytes(
        repository_root,
        ("ls-tree", "-z", spec.commit, "--", spec.relative_path),
    )
    entries = [entry for entry in metadata_bytes.split(b"\0") if entry]
    if len(entries) != 1:
        raise AttributionDataError(
            f"FROZEN_ARTIFACT_PATH_MISMATCH: {spec.key} resolved {len(entries)} entries"
        )
    try:
        metadata, observed_path = entries[0].split(b"\t", 1)
        mode, object_type, blob_oid = metadata.decode("ascii").split()
        decoded_path = observed_path.decode("utf-8")
    except (UnicodeDecodeError, ValueError) as exc:
        raise AttributionDataError(f"FROZEN_ARTIFACT_METADATA_INVALID: {spec.key}") from exc
    if mode != "100644" or object_type != "blob" or decoded_path != spec.relative_path:
        raise AttributionDataError(
            "FROZEN_ARTIFACT_NOT_SAFE_TEXT_BLOB: "
            f"{spec.key} mode={mode} type={object_type} path={decoded_path}"
        )

    artifact_bytes = _git_bytes(
        repository_root,
        ("cat-file", "blob", f"{spec.commit}:{spec.relative_path}"),
    )
    actual_sha256 = hashlib.sha256(artifact_bytes).hexdigest()
    if actual_sha256 != spec.sha256:
        raise AttributionDataError(
            "FROZEN_ARTIFACT_SHA256_MISMATCH: "
            f"{spec.key} expected {spec.sha256}, observed {actual_sha256}"
        )
    try:
        decoded = json.loads(artifact_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AttributionDataError(f"{spec.key} is not valid UTF-8 JSON") from exc
    if not isinstance(decoded, dict):
        raise AttributionDataError(f"{spec.key} top-level JSON must be an object")
    return LoadedArtifact(
        spec=spec,
        blob_oid=blob_oid,
        size_bytes=len(artifact_bytes),
        payload=cast(dict[str, Any], decoded),
    )


def load_all_frozen_artifacts(
    repository_root: Path = REPOSITORY_ROOT,
) -> dict[str, LoadedArtifact]:
    """Load only the four packet-authorized immutable Git artifacts."""

    root = repository_root.resolve()
    observed_root = Path(_git_text(root, ("rev-parse", "--show-toplevel"))).resolve()
    if observed_root != root:
        raise AttributionDataError(
            f"REPOSITORY_ROOT_MISMATCH: requested {root}, observed {observed_root}"
        )
    return {spec.key: load_frozen_artifact(spec, root) for spec in ARTIFACT_SPECS}


def _unique_records(
    raw_records: object,
    *,
    context: str,
) -> dict[str, Mapping[str, Any]]:
    records: dict[str, Mapping[str, Any]] = {}
    for index, raw_record in enumerate(_as_list(raw_records, context=context)):
        record = _as_mapping(raw_record, context=f"{context}[{index}]")
        strategy_id = _as_string(
            record.get("strategy_id"),
            context=f"{context}[{index}].strategy_id",
        )
        if strategy_id in records:
            raise AttributionDataError(f"{context} contains duplicate strategy_id {strategy_id}")
        records[strategy_id] = record
    return records


def _base_lineage_identity(record: Mapping[str, Any]) -> LineageIdentity:
    strategy_id = _as_string(record.get("strategy_id"), context="base strategy_id")
    fingerprint = _as_sha256(
        record.get("binding_fingerprint_sha256"),
        context=f"{strategy_id}.binding_fingerprint_sha256",
    )
    binding_identity = _as_string(
        record.get("binding_group_id"), context=f"{strategy_id}.binding_group_id"
    )
    if binding_identity != f"binding-sha256:{fingerprint}":
        raise AttributionDataError(f"{strategy_id} binding group does not match its fingerprint")
    callable_identity = _as_string(
        record.get("callable_family_id"), context=f"{strategy_id}.callable_family_id"
    )
    implementation_module = _as_string(
        record.get("implementation_module"), context=f"{strategy_id}.implementation_module"
    )
    callable_symbol = _as_string(
        record.get("callable_or_class_symbol"),
        context=f"{strategy_id}.callable_or_class_symbol",
    )
    games = tuple(
        sorted(
            _as_string(item, context=f"{strategy_id}.game_identities")
            for item in _as_list(
                record.get("game_identities"), context=f"{strategy_id}.game_identities"
            )
        )
    )
    if not games:
        raise AttributionDataError(f"{strategy_id} has no game identity")
    return LineageIdentity(
        strategy_id=strategy_id,
        source_authority="BASE_LINEAGE",
        source_classification=_as_string(
            record.get("classification"), context=f"{strategy_id}.classification"
        ),
        binding_fingerprint_sha256=fingerprint,
        binding_identity=binding_identity,
        callable_identity=callable_identity,
        callable_family_label=f"{implementation_module}:{callable_symbol}",
        game_identities=games,
    )


def _supplemental_lineage_identity(
    record: Mapping[str, Any],
    base_unresolved_record: Mapping[str, Any],
) -> LineageIdentity:
    strategy_id = _as_string(record.get("strategy_id"), context="supplement strategy_id")
    original = _as_mapping(
        record.get("original_resolution"), context=f"{strategy_id}.original_resolution"
    )
    expected_original = {
        "binding_group_id": base_unresolved_record.get("binding_group_id"),
        "classification": base_unresolved_record.get("classification"),
        "unresolved_reason": base_unresolved_record.get("unresolved_reason"),
    }
    observed_original = {
        "binding_group_id": original.get("binding_group_id"),
        "classification": original.get("classification"),
        "unresolved_reason": original.get("unresolved_reason"),
    }
    if observed_original != expected_original:
        raise AttributionDataError(
            f"LINEAGE_AUTHORITY_CONFLICT: {strategy_id} original resolution differs"
        )
    final_classification = _as_string(
        record.get("final_resolution_classification"),
        context=f"{strategy_id}.final_resolution_classification",
    )
    if final_classification not in {
        "RESOLVED_STATIC_IMPLEMENTATION",
        "RESOLVED_RUNTIME_FACTORY_IDENTITY",
    }:
        raise AttributionDataError(
            f"LINEAGE_SUPPLEMENT_UNRESOLVED: {strategy_id}={final_classification}"
        )

    fingerprint = _as_sha256(
        record.get("supplemental_binding_fingerprint_sha256"),
        context=f"{strategy_id}.supplemental_binding_fingerprint_sha256",
    )
    structural_digest = _as_sha256(
        record.get("structural_source_digest_sha256"),
        context=f"{strategy_id}.structural_source_digest_sha256",
    )
    implementation = _as_mapping(
        record.get("implementation_class_callable"),
        context=f"{strategy_id}.implementation_class_callable",
    )
    selected_callable = _as_string(
        implementation.get("statically_selected_wave26_callable_locator"),
        context=f"{strategy_id}.statically_selected_wave26_callable_locator",
    )
    games = tuple(
        sorted(
            _as_string(item, context=f"{strategy_id}.game_identities")
            for item in _as_list(
                base_unresolved_record.get("game_identities"),
                context=f"{strategy_id}.game_identities",
            )
        )
    )
    return LineageIdentity(
        strategy_id=strategy_id,
        source_authority="WAVE26_SUPPLEMENT",
        source_classification=final_classification,
        binding_fingerprint_sha256=fingerprint,
        binding_identity=f"binding-sha256:{fingerprint}",
        callable_identity=f"wave26-structural-sha256:{structural_digest}",
        callable_family_label=selected_callable,
        game_identities=games,
    )


def _combined_lineage_classifications(
    identities: Mapping[str, LineageIdentity],
) -> dict[str, str]:
    by_binding: defaultdict[str, list[str]] = defaultdict(list)
    by_callable: defaultdict[str, list[str]] = defaultdict(list)
    for identity in identities.values():
        by_binding[identity.binding_identity].append(identity.strategy_id)
        by_callable[identity.callable_identity].append(identity.strategy_id)

    classifications: dict[str, str] = {}
    for strategy_id, identity in identities.items():
        if len(by_binding[identity.binding_identity]) > 1:
            classification = "IDENTICAL_BINDING"
        elif len(by_callable[identity.callable_identity]) > 1:
            classification = "SAME_CALLABLE_DIFFERENT_BINDING"
        else:
            classification = "DISTINCT_BINDING"
        classifications[strategy_id] = classification
    return classifications


def merge_lineage_authorities(
    base_lineage: Mapping[str, Any],
    wave26_supplement: Mapping[str, Any],
    *,
    enforce_sealed_shape: bool = True,
) -> tuple[dict[str, LineageIdentity], dict[str, Any]]:
    """Merge 131 resolved base rows with four supplemental resolutions."""

    base_records = _unique_records(base_lineage.get("records"), context="base_lineage.records")
    supplement_records = _unique_records(
        wave26_supplement.get("records"), context="wave26_supplement.records"
    )
    base_resolved = {
        strategy_id: record
        for strategy_id, record in base_records.items()
        if record.get("classification") != "DYNAMIC_OR_UNRESOLVED"
    }
    base_unresolved = {
        strategy_id: record
        for strategy_id, record in base_records.items()
        if record.get("classification") == "DYNAMIC_OR_UNRESOLVED"
    }

    overlap_with_resolved = sorted(set(supplement_records) & set(base_resolved))
    if overlap_with_resolved:
        raise AttributionDataError(
            "LINEAGE_AUTHORITY_CONFLICT: supplemental rows overlap already-resolved "
            f"base identities {overlap_with_resolved}"
        )
    if set(supplement_records) != set(base_unresolved):
        missing = sorted(set(base_unresolved) - set(supplement_records))
        extra = sorted(set(supplement_records) - set(base_unresolved))
        raise AttributionDataError(
            "LINEAGE_AUTHORITY_COVERAGE_MISMATCH: "
            f"missing supplemental IDs={missing}; extra supplemental IDs={extra}"
        )

    identities: dict[str, LineageIdentity] = {
        strategy_id: _base_lineage_identity(record) for strategy_id, record in base_resolved.items()
    }
    for strategy_id, record in supplement_records.items():
        identities[strategy_id] = _supplemental_lineage_identity(
            record, base_unresolved[strategy_id]
        )

    combined_classes = _combined_lineage_classifications(identities)
    identities = {
        strategy_id: replace(identity, combined_classification=combined_classes[strategy_id])
        for strategy_id, identity in identities.items()
    }

    changed_base_classes = sorted(
        strategy_id
        for strategy_id, record in base_resolved.items()
        if record.get("classification") != combined_classes[strategy_id]
    )
    if changed_base_classes:
        raise AttributionDataError(
            "LINEAGE_AUTHORITY_CONFLICT: supplemental identities change frozen base "
            f"classifications for {changed_base_classes}"
        )

    if enforce_sealed_shape:
        observed = (
            len(base_records),
            len(base_resolved),
            len(base_unresolved),
            len(supplement_records),
            len(identities),
        )
        expected = (
            EXPECTED_CANONICAL_STRATEGY_COUNT,
            EXPECTED_BASE_RESOLVED_STRATEGY_COUNT,
            EXPECTED_SUPPLEMENTAL_STRATEGY_COUNT,
            EXPECTED_SUPPLEMENTAL_STRATEGY_COUNT,
            EXPECTED_CANONICAL_STRATEGY_COUNT,
        )
        if observed != expected:
            raise AttributionDataError(
                f"LINEAGE_135_ID_COVERAGE_MISMATCH: expected {expected}, observed {observed}"
            )

    combined_counts = Counter(identity.combined_classification for identity in identities.values())
    return identities, {
        "base_record_count": len(base_records),
        "base_resolved_record_count": len(base_resolved),
        "base_unresolved_replaced_count": len(base_unresolved),
        "combined_classification_counts": {
            key: combined_counts.get(key, 0)
            for key in (
                "IDENTICAL_BINDING",
                "SAME_CALLABLE_DIFFERENT_BINDING",
                "DISTINCT_BINDING",
            )
        },
        "combined_record_count": len(identities),
        "complete_135_id_coverage": len(identities) == EXPECTED_CANONICAL_STRATEGY_COUNT,
        "records": [identities[strategy_id].as_payload() for strategy_id in sorted(identities)],
        "supplemental_record_count": len(supplement_records),
    }


def _validated_fraction(payload: object, *, context: str) -> Fraction:
    mapping = _as_mapping(payload, context=context)
    numerator_raw = mapping.get("numerator")
    denominator_raw = mapping.get("denominator")
    if isinstance(numerator_raw, bool) or not isinstance(numerator_raw, int):
        raise AttributionDataError(f"{context}.numerator must be an integer")
    if isinstance(denominator_raw, bool) or not isinstance(denominator_raw, int):
        raise AttributionDataError(f"{context}.denominator must be an integer")
    if denominator_raw <= 0:
        raise AttributionDataError(f"{context}.denominator must be positive")
    value = Fraction(numerator_raw, denominator_raw)
    exact = _as_string(mapping.get("exact"), context=f"{context}.exact")
    if exact != f"{value.numerator}/{value.denominator}":
        raise AttributionDataError(f"{context}.exact is not canonical")
    return value


def _selector_sign(experiment: Mapping[str, Any], *, context: str) -> str:
    status = _as_string(experiment.get("status"), context=f"{context}.status")
    delta = experiment.get("absolute_paired_delta")
    if status != "COMPLETE":
        if delta is not None:
            raise AttributionDataError(f"{context} is excluded but contains a delta")
        return "INCONCLUSIVE"
    if delta is None:
        raise AttributionDataError(f"{context} is complete but lacks a delta")
    value = _validated_fraction(delta, context=f"{context}.absolute_paired_delta")
    if value > 0:
        return "POSITIVE"
    if value < 0:
        return "NEGATIVE"
    return "ZERO"


def _selection_frequencies(value: object, *, context: str) -> dict[str, int]:
    mapping = _as_mapping(value, context=context)
    frequencies: dict[str, int] = {}
    for raw_strategy_id, raw_count in mapping.items():
        strategy_id = _as_string(raw_strategy_id, context=f"{context} strategy_id")
        frequencies[strategy_id] = _as_positive_int(raw_count, context=f"{context}[{strategy_id}]")
    return frequencies


def _frequency_buckets(
    frequencies: Mapping[str, int],
    identities: Mapping[str, LineageIdentity],
    *,
    identity_attribute: str,
    label_attribute: str | None = None,
) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter()
    strategy_ids: defaultdict[str, list[str]] = defaultdict(list)
    labels: defaultdict[str, set[str]] = defaultdict(set)
    for strategy_id, count in frequencies.items():
        identity = identities.get(strategy_id)
        if identity is None:
            continue
        identity_value = cast(str, getattr(identity, identity_attribute))
        counts[identity_value] += count
        strategy_ids[identity_value].append(strategy_id)
        if label_attribute is not None:
            labels[identity_value].add(cast(str, getattr(identity, label_attribute)))

    output: list[dict[str, Any]] = []
    for identity_value in sorted(counts):
        row: dict[str, Any] = {
            "identity": identity_value,
            "selection_count": counts[identity_value],
            "strategy_ids": sorted(strategy_ids[identity_value]),
        }
        if label_attribute is not None:
            row["labels"] = sorted(labels[identity_value])
        output.append(row)
    return output


def attribute_selection_diversity(
    frequencies: Mapping[str, int],
    *,
    switch_count: int,
    lottery_id: str,
    identities: Mapping[str, LineageIdentity],
) -> dict[str, Any]:
    """Classify selected structural diversity without inventing transition order."""

    selected_ids = sorted(frequencies)
    missing_ids = sorted(set(selected_ids) - set(identities))
    resolved = {
        strategy_id: identities[strategy_id]
        for strategy_id in selected_ids
        if strategy_id in identities
    }
    wrong_game_ids = sorted(
        strategy_id
        for strategy_id, identity in resolved.items()
        if lottery_id not in identity.game_identities
    )
    reasons: list[str] = []
    if missing_ids:
        reasons.append("SELECTED_STRATEGY_IDS_ABSENT_FROM_COMBINED_LINEAGE")
    if wrong_game_ids:
        reasons.append("SELECTED_STRATEGY_LINEAGE_GAME_IDENTITY_MISMATCH")
    if switch_count > 0 and len(selected_ids) < 2:
        reasons.append("NONZERO_SWITCH_COUNT_WITH_FEWER_THAN_TWO_SELECTED_STRATEGY_IDS")
    if switch_count == 0 and len(selected_ids) > 1:
        reasons.append("ZERO_SWITCH_COUNT_WITH_MULTIPLE_SELECTED_STRATEGY_IDS")

    binding_buckets = _frequency_buckets(
        frequencies,
        resolved,
        identity_attribute="binding_identity",
    )
    callable_buckets = _frequency_buckets(
        frequencies,
        resolved,
        identity_attribute="callable_identity",
        label_attribute="callable_family_label",
    )
    unresolved_frequencies = [
        {"selection_count": frequencies[strategy_id], "strategy_id": strategy_id}
        for strategy_id in missing_ids
    ]

    if reasons:
        return {
            "any_selected_pair_same_callable_different_binding": None,
            "diversity_class": "LINEAGE_SOURCE_INCONSISTENT",
            "lineage_attribution_complete": False,
            "lineage_source_inconsistency_reasons": reasons,
            "more_than_one_distinct_binding_identity_selected": None,
            "same_callable_different_binding_pairs": [],
            "selection_frequency_by_binding_identity": binding_buckets,
            "selection_frequency_by_callable_family": callable_buckets,
            "structurally_unresolved_selected_strategy_ids": missing_ids,
            "unique_binding_fingerprint_count": None,
            "unique_callable_identity_count": None,
            "unique_strategy_id_count": len(selected_ids),
            "unattributed_selection_frequency": unresolved_frequencies,
            "wrong_game_identity_selected_strategy_ids": wrong_game_ids,
        }

    binding_ids = {identity.binding_identity for identity in resolved.values()}
    callable_ids = {identity.callable_identity for identity in resolved.values()}
    sibling_pairs: list[dict[str, str]] = []
    for left_id, right_id in itertools.combinations(selected_ids, 2):
        left = resolved[left_id]
        right = resolved[right_id]
        if (
            left.callable_identity == right.callable_identity
            and left.binding_identity != right.binding_identity
        ):
            sibling_pairs.append({"left_strategy_id": left_id, "right_strategy_id": right_id})

    has_sibling_pair = bool(sibling_pairs)
    has_distinct_callable = len(callable_ids) > 1
    if switch_count == 0 or len(binding_ids) <= 1:
        diversity_class = "NO_SWITCH"
    elif has_sibling_pair and has_distinct_callable:
        diversity_class = "MIXED_DIVERSITY"
    elif has_sibling_pair:
        diversity_class = "PARAMETER_SIBLING_DIVERSITY_ONLY"
    elif has_distinct_callable:
        diversity_class = "DISTINCT_BINDING_DIVERSITY"
    else:
        diversity_class = "LINEAGE_SOURCE_INCONSISTENT"
        reasons.append("MULTIPLE_BINDINGS_WITHOUT_A_RESOLVABLE_DIVERSITY_RELATION")

    return {
        "any_selected_pair_same_callable_different_binding": has_sibling_pair,
        "diversity_class": diversity_class,
        "lineage_attribution_complete": diversity_class != "LINEAGE_SOURCE_INCONSISTENT",
        "lineage_source_inconsistency_reasons": reasons,
        "more_than_one_distinct_binding_identity_selected": has_distinct_callable,
        "same_callable_different_binding_pairs": sibling_pairs,
        "selection_frequency_by_binding_identity": binding_buckets,
        "selection_frequency_by_callable_family": callable_buckets,
        "structurally_unresolved_selected_strategy_ids": [],
        "unique_binding_fingerprint_count": len(binding_ids),
        "unique_callable_identity_count": len(callable_ids),
        "unique_strategy_id_count": len(selected_ids),
        "unattributed_selection_frequency": [],
        "wrong_game_identity_selected_strategy_ids": [],
    }


def _decomposition_index(
    decomposition: Mapping[str, Any],
    *,
    enforce_sealed_shape: bool,
) -> dict[tuple[str, str], Mapping[str, Any]]:
    index: dict[tuple[str, str], Mapping[str, Any]] = {}
    raw_cells = _as_list(decomposition.get("cells"), context="decomposition.cells")
    for cell_index, raw_cell in enumerate(raw_cells):
        cell = _as_mapping(raw_cell, context=f"decomposition.cells[{cell_index}]")
        cell_id = _as_string(cell.get("cell_id"), context="decomposition cell_id")
        for window_index, raw_window in enumerate(
            _as_list(cell.get("windows"), context=f"{cell_id}.windows")
        ):
            window = _as_mapping(raw_window, context=f"{cell_id}.windows[{window_index}]")
            source_label = _as_string(window.get("source_label"), context=f"{cell_id}.source_label")
            key = (cell_id, source_label)
            if key in index:
                raise AttributionDataError(f"duplicate decomposition experiment {key}")
            index[key] = window
    if enforce_sealed_shape and (
        len(raw_cells) != EXPECTED_CELL_COUNT or len(index) != EXPECTED_EXPERIMENT_COUNT
    ):
        raise AttributionDataError(
            f"DECOMPOSITION_SHAPE_MISMATCH: cells={len(raw_cells)} experiments={len(index)}"
        )
    return index


def _validate_decomposition_source_identity(decomposition: Mapping[str, Any]) -> None:
    source = _as_mapping(
        decomposition.get("source_identity"), context="decomposition.source_identity"
    )
    expected = {
        "result_head": SELECTOR_ARTIFACT.commit,
        "result_path": SELECTOR_ARTIFACT.relative_path,
        "result_sha256": SELECTOR_ARTIFACT.sha256,
        "result_tree": SELECTOR_ARTIFACT.tree,
    }
    observed = {key: source.get(key) for key in expected}
    if observed != expected:
        raise AttributionDataError(
            f"SELECTOR_DECOMPOSITION_AUTHORITY_CONFLICT: {observed} != {expected}"
        )


def _copy_source_delta(value: object) -> Any:
    return copy.deepcopy(value)


def _build_experiment(
    *,
    cell_id: str,
    lottery_id: str,
    k: int,
    source_label: str,
    expected_window: int,
    candidate_ids: set[str],
    raw_experiment: Mapping[str, Any],
    decomposition_window: Mapping[str, Any],
    identities: Mapping[str, LineageIdentity],
) -> dict[str, Any]:
    context = f"{cell_id}.{source_label}"
    if raw_experiment.get("label") != source_label:
        raise AttributionDataError(f"{context}.label mismatch")
    if raw_experiment.get("window") != expected_window:
        raise AttributionDataError(f"{context}.window mismatch")
    sign = _selector_sign(raw_experiment, context=context)
    decomposition_sign = _as_string(
        decomposition_window.get("classification"),
        context=f"{context}.decomposition.classification",
    )
    if sign != decomposition_sign:
        raise AttributionDataError(
            f"SEALED_SIGN_PRESERVATION_CONFLICT: {context} {sign} != {decomposition_sign}"
        )

    frequencies = _selection_frequencies(
        raw_experiment.get("rolling_selection_frequency"),
        context=f"{context}.rolling_selection_frequency",
    )
    selected_ids = set(frequencies)
    if not selected_ids <= candidate_ids:
        raise AttributionDataError(
            f"{context} selected IDs outside candidate universe: "
            f"{sorted(selected_ids - candidate_ids)}"
        )
    switch_count = _as_nonnegative_int(
        raw_experiment.get("rolling_strategy_switch_count"),
        context=f"{context}.rolling_strategy_switch_count",
    )
    if switch_count != decomposition_window.get("switch_count"):
        raise AttributionDataError(f"{context} switch count differs from decomposition")

    available = bool(decomposition_window.get("available"))
    if available != (raw_experiment.get("status") == "COMPLETE"):
        raise AttributionDataError(f"{context} availability differs from selector status")
    frozen_baseline = _as_optional_string(
        raw_experiment.get("frozen_baseline_strategy"),
        context=f"{context}.frozen_baseline_strategy",
    )
    if frozen_baseline != decomposition_window.get("frozen_strategy_identity"):
        raise AttributionDataError(f"{context} frozen baseline differs from decomposition")

    source_delta = raw_experiment.get("absolute_paired_delta")
    decomposition_delta = decomposition_window.get("rolling_minus_frozen_exact_delta")
    if source_delta is None:
        if decomposition_delta is not None:
            raise AttributionDataError(f"{context} decomposition invents a delta")
    else:
        source_fraction = _validated_fraction(
            source_delta, context=f"{context}.absolute_paired_delta"
        )
        decomposition_fraction = _validated_fraction(
            decomposition_delta,
            context=f"{context}.rolling_minus_frozen_exact_delta",
        )
        if source_fraction != decomposition_fraction:
            raise AttributionDataError(f"{context} exact delta differs from decomposition")

    selection_target_count = sum(frequencies.values())
    expected_target_count = _as_nonnegative_int(
        decomposition_window.get("rolling_selection_target_count"),
        context=f"{context}.rolling_selection_target_count",
    )
    if selection_target_count != expected_target_count:
        raise AttributionDataError(
            f"{context} selection frequency total {selection_target_count} "
            f"!= {expected_target_count}"
        )
    if available:
        metric = _as_mapping(
            raw_experiment.get("rolling_selector_primary_metric_result"),
            context=f"{context}.rolling_selector_primary_metric_result",
        )
        metric_target_count = _as_nonnegative_int(
            metric.get("target_count"), context=f"{context}.metric_target_count"
        )
        if metric_target_count != selection_target_count:
            raise AttributionDataError(f"{context} metric target count mismatch")
    elif frequencies:
        raise AttributionDataError(f"{context} unavailable experiment has selections")

    diversity = attribute_selection_diversity(
        frequencies,
        switch_count=switch_count,
        lottery_id=lottery_id,
        identities=identities,
    )
    window_label = _as_string(
        decomposition_window.get("window_label"),
        context=f"{context}.window_label",
    )
    expected_window_label = next(
        label
        for label, source, value in WINDOWS
        if source == source_label and value == expected_window
    )
    if window_label != expected_window_label:
        raise AttributionDataError(f"{context} output window label mismatch")

    return {
        "available": available,
        "cell_id": cell_id,
        "frozen_baseline_strategy_id": frozen_baseline,
        "historical_sign": sign,
        "k": k,
        "lottery_id": lottery_id,
        "original_absolute_paired_delta": _copy_source_delta(source_delta),
        "original_relative_paired_delta": _copy_source_delta(
            raw_experiment.get("relative_paired_delta")
        ),
        "selected_strategy_ids": sorted(frequencies),
        "selection_frequency_by_strategy_id": [
            {"selection_count": frequencies[strategy_id], "strategy_id": strategy_id}
            for strategy_id in sorted(frequencies)
        ],
        "selection_target_count": selection_target_count,
        "selection_trace_order_available": False,
        "selection_trace_sha256": raw_experiment.get("selection_trace_sha256"),
        "source_conclusion": raw_experiment.get("conclusion"),
        "source_status": raw_experiment.get("status"),
        "switch_count": switch_count,
        "switching_active": available and switch_count > 0,
        "window": expected_window,
        "window_label": window_label,
        **diversity,
    }


def _count_matrix(experiments: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, int]]:
    return {
        diversity_class: {
            sign: sum(
                row.get("diversity_class") == diversity_class and row.get("historical_sign") == sign
                for row in experiments
            )
            for sign in HISTORICAL_SIGNS
        }
        for diversity_class in DIVERSITY_CLASSES
    }


def _ratio_payload(numerator: int, denominator: int) -> dict[str, Any]:
    if denominator <= 0:
        return {"decimal_6": None, "exact": None}
    value = Fraction(numerator, denominator)
    return {
        "decimal_6": f"{float(value):.6f}",
        "exact": f"{value.numerator}/{value.denominator}",
    }


def _p638_bridge_answer(
    selector_cells: Sequence[Mapping[str, Any]],
    experiments: Sequence[Mapping[str, Any]],
    identities: Mapping[str, LineageIdentity],
) -> dict[str, Any]:
    bridge_identities = [identities[strategy_id] for strategy_id in P638_BRIDGE_STRATEGY_IDS]
    family_ids = {identity.callable_identity for identity in bridge_identities}
    binding_ids = {identity.binding_identity for identity in bridge_identities}
    if len(family_ids) != 1 or len(binding_ids) != len(P638_BRIDGE_STRATEGY_IDS):
        raise AttributionDataError("P638_BRIDGE_FROZEN_LINEAGE_IDENTITY_MISMATCH")

    p638_k1 = next(cell for cell in selector_cells if cell.get("cell_id") == "P638:K1")
    universe_ids = {
        _as_string(
            _as_mapping(candidate, context="P638:K1 candidate").get("strategy_id"),
            context="P638:K1 candidate strategy_id",
        )
        for candidate in _as_list(p638_k1.get("candidate_strategies"), context="P638:K1 candidates")
    }
    if not set(P638_BRIDGE_STRATEGY_IDS) <= universe_ids:
        raise AttributionDataError("P638_BRIDGE_SELECTOR_UNIVERSE_COVERAGE_MISMATCH")

    rows: list[dict[str, Any]] = []
    for experiment in sorted(
        (row for row in experiments if row.get("cell_id") == "P638:K1"),
        key=lambda row: cast(int, row["window"]),
    ):
        raw_frequencies = cast(
            list[dict[str, Any]], experiment["selection_frequency_by_strategy_id"]
        )
        frequency_by_id = {
            cast(str, row["strategy_id"]): cast(int, row["selection_count"])
            for row in raw_frequencies
        }
        bridge_frequency = {
            strategy_id: frequency_by_id[strategy_id]
            for strategy_id in P638_BRIDGE_STRATEGY_IDS
            if strategy_id in frequency_by_id
        }
        bridge_count = sum(bridge_frequency.values())
        total_count = cast(int, experiment["selection_target_count"])
        rows.append(
            {
                "bridge_family_selected_strategy_count": len(bridge_frequency),
                "bridge_family_selection_count": bridge_count,
                "bridge_family_selection_frequency_by_strategy_id": [
                    {
                        "selection_count": bridge_frequency[strategy_id],
                        "strategy_id": strategy_id,
                    }
                    for strategy_id in sorted(bridge_frequency)
                ],
                "bridge_family_selection_share": _ratio_payload(bridge_count, total_count),
                "historical_sign": experiment["historical_sign"],
                "raw_switch_count": experiment["switch_count"],
                "selection_target_count": total_count,
                "window": experiment["window"],
                "window_label": experiment["window_label"],
            }
        )
    return {
        "answer": (
            "NOT_ATTRIBUTABLE_FROM_FREQUENCY_ONLY: C01-C07 are seven distinct "
            "bindings in one frozen callable family, but the sealed result exposes "
            "selection frequencies and a trace hash, not transition order. Exact "
            "switches cannot be assigned to this family without inventing transitions."
        ),
        "bridge_binding_identity_count": len(binding_ids),
        "bridge_callable_family_identity": next(iter(family_ids)),
        "bridge_strategy_ids": list(P638_BRIDGE_STRATEGY_IDS),
        "substantial_threshold_defined": False,
        "transition_order_available": False,
        "windows": rows,
    }


def _wave26_answer(
    selector_cells: Sequence[Mapping[str, Any]],
    experiments: Sequence[Mapping[str, Any]],
    identities: Mapping[str, LineageIdentity],
) -> dict[str, Any]:
    wave_ids = sorted(
        strategy_id
        for strategy_id, identity in identities.items()
        if identity.source_authority == "WAVE26_SUPPLEMENT"
    )
    universe_cells: defaultdict[str, list[str]] = defaultdict(list)
    for cell in selector_cells:
        cell_id = _as_string(cell.get("cell_id"), context="selector cell_id")
        candidate_ids = {
            _as_string(
                _as_mapping(candidate, context=f"{cell_id} candidate").get("strategy_id"),
                context=f"{cell_id} candidate strategy_id",
            )
            for candidate in _as_list(
                cell.get("candidate_strategies"), context=f"{cell_id} candidates"
            )
        }
        for strategy_id in wave_ids:
            if strategy_id in candidate_ids:
                universe_cells[strategy_id].append(cell_id)

    selected_experiments: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for experiment in experiments:
        frequency_rows = cast(
            list[dict[str, Any]], experiment["selection_frequency_by_strategy_id"]
        )
        for frequency in frequency_rows:
            strategy_id = cast(str, frequency["strategy_id"])
            if strategy_id in wave_ids:
                selected_experiments[strategy_id].append(
                    {
                        "cell_id": experiment["cell_id"],
                        "historical_sign": experiment["historical_sign"],
                        "selection_count": frequency["selection_count"],
                        "window": experiment["window"],
                        "window_label": experiment["window_label"],
                    }
                )

    rows = [
        {
            "binding_identity": identities[strategy_id].binding_identity,
            "callable_identity": identities[strategy_id].callable_identity,
            "combined_classification": identities[strategy_id].combined_classification,
            "in_selector_universe": bool(universe_cells[strategy_id]),
            "selected": bool(selected_experiments[strategy_id]),
            "selected_experiments": selected_experiments[strategy_id],
            "selector_universe_cells": sorted(universe_cells[strategy_id]),
            "source_resolution_classification": identities[strategy_id].source_classification,
            "strategy_id": strategy_id,
        }
        for strategy_id in wave_ids
    ]
    return {
        "appears_in_selector_universe_count": sum(
            cast(bool, row["in_selector_universe"]) for row in rows
        ),
        "appears_in_selection_count": sum(cast(bool, row["selected"]) for row in rows),
        "strategies": rows,
    }


def _required_answers(
    *,
    selector_cells: Sequence[Mapping[str, Any]],
    experiments: Sequence[Mapping[str, Any]],
    identities: Mapping[str, LineageIdentity],
) -> list[dict[str, Any]]:
    switching_active = [row for row in experiments if cast(bool, row.get("switching_active"))]
    exact_distinct = [
        row
        for row in switching_active
        if row.get("diversity_class") == "DISTINCT_BINDING_DIVERSITY"
    ]
    repeated = [
        {
            "cell_id": cell_id,
            "windows": [
                {
                    "diversity_class": row["diversity_class"],
                    "historical_sign": row["historical_sign"],
                    "lineage_attribution_complete": row["lineage_attribution_complete"],
                    "structurally_unresolved_selected_strategy_ids": row[
                        "structurally_unresolved_selected_strategy_ids"
                    ],
                    "switch_count": row["switch_count"],
                    "window": row["window"],
                    "window_label": row["window_label"],
                }
                for row in sorted(
                    (
                        experiment
                        for experiment in experiments
                        if experiment.get("cell_id") == cell_id
                    ),
                    key=lambda experiment: cast(int, experiment["window"]),
                )
            ],
        }
        for cell_id in REPEATED_POSITIVE_CELL_IDS
    ]

    positive = [
        row
        for row in experiments
        if row.get("available") and row.get("historical_sign") == "POSITIVE"
    ]
    positive_counts = Counter(cast(str, row["diversity_class"]) for row in positive)
    without_distinct_classes = {"NO_SWITCH", "PARAMETER_SIBLING_DIVERSITY_ONLY"}
    contains_distinct_classes = {"DISTINCT_BINDING_DIVERSITY", "MIXED_DIVERSITY"}
    return [
        {
            "answer": {
                "historical_sign_counts": {
                    sign: sum(row.get("historical_sign") == sign for row in exact_distinct)
                    for sign in ("POSITIVE", "NEGATIVE", "ZERO")
                },
                "switching_active_distinct_binding_diversity_count": len(exact_distinct),
            },
            "question": (
                "Among switching-active experiments, how many POSITIVE, NEGATIVE, and "
                "ZERO use actual DISTINCT_BINDING_DIVERSITY?"
            ),
            "question_id": 1,
        },
        {
            "answer": {
                "parameter_sibling_diversity_only_count": sum(
                    row.get("diversity_class") == "PARAMETER_SIBLING_DIVERSITY_ONLY"
                    for row in switching_active
                )
            },
            "question": (
                "How many switching-active experiments only move within parameterized "
                "sibling families?"
            ),
            "question_id": 2,
        },
        {
            "answer": {"cells": repeated},
            "question": (
                "What implementation-diversity class occurs in each window for the "
                "five repeated-positive candidates?"
            ),
            "question_id": 3,
        },
        {
            "answer": _p638_bridge_answer(selector_cells, experiments, identities),
            "question": (
                "Does the P638 C01-C07 bridge family account for substantial switching "
                "while remaining within one callable family?"
            ),
            "question_id": 4,
        },
        {
            "answer": {
                "positive_counts_by_diversity_class": {
                    diversity_class: positive_counts.get(diversity_class, 0)
                    for diversity_class in DIVERSITY_CLASSES
                },
                (
                    "positive_present_in_classifiable_experiments_"
                    "containing_distinct_binding_diversity"
                ): any(row.get("diversity_class") in contains_distinct_classes for row in positive),
                (
                    "positive_present_in_classifiable_experiments_"
                    "without_distinct_binding_diversity"
                ): any(row.get("diversity_class") in without_distinct_classes for row in positive),
                "positive_with_lineage_source_inconsistent_count": positive_counts.get(
                    "LINEAGE_SOURCE_INCONSISTENT", 0
                ),
            },
            "question": (
                "Are positive historical deltas still present when experiments without "
                "distinct-binding diversity are separated out?"
            ),
            "question_id": 5,
        },
        {
            "answer": _wave26_answer(selector_cells, experiments, identities),
            "question": (
                "Do the four formerly unresolved Wave26 strategies appear in any "
                "evaluated selector universe or selection, and how are they classified?"
            ),
            "question_id": 6,
        },
    ]


def build_attribution(
    selector: Mapping[str, Any],
    decomposition: Mapping[str, Any],
    base_lineage: Mapping[str, Any],
    wave26_supplement: Mapping[str, Any],
    *,
    source_identities: Mapping[str, Mapping[str, Any]] | None = None,
    enforce_sealed_shape: bool = True,
) -> dict[str, Any]:
    """Build the deterministic attribution from already-verified source payloads."""

    if selector.get("task_id") != "STRATEGY_MATRIX_CAUSAL_ROLLING_SELECTOR_PILOT_R1":
        raise AttributionDataError("unexpected selector task_id")
    if decomposition.get("task_id") != "ROLLING_SELECTOR_STABILITY_DECOMPOSITION_R1":
        raise AttributionDataError("unexpected decomposition task_id")
    _validate_decomposition_source_identity(decomposition)
    identities, lineage_merge = merge_lineage_authorities(
        base_lineage,
        wave26_supplement,
        enforce_sealed_shape=enforce_sealed_shape,
    )
    decomposition_by_experiment = _decomposition_index(
        decomposition, enforce_sealed_shape=enforce_sealed_shape
    )

    raw_cells = [
        _as_mapping(raw_cell, context=f"selector.cells[{index}]")
        for index, raw_cell in enumerate(_as_list(selector.get("cells"), context="selector.cells"))
    ]
    cell_ids = [_as_string(cell.get("cell_id"), context="selector cell_id") for cell in raw_cells]
    if len(cell_ids) != len(set(cell_ids)):
        raise AttributionDataError("selector contains duplicate cell IDs")
    if enforce_sealed_shape and len(raw_cells) != EXPECTED_CELL_COUNT:
        raise AttributionDataError(f"selector cell count {len(raw_cells)} != 22")

    experiments: list[dict[str, Any]] = []
    candidate_universe: set[str] = set()
    for cell in sorted(
        raw_cells,
        key=lambda item: (
            _as_string(item.get("lottery_id"), context="lottery_id"),
            _as_nonnegative_int(item.get("native_ticket_count"), context="native_ticket_count"),
        ),
    ):
        cell_id = _as_string(cell.get("cell_id"), context="cell_id")
        lottery_id = _as_string(cell.get("lottery_id"), context=f"{cell_id}.lottery_id")
        k = _as_positive_int(
            cell.get("native_ticket_count"), context=f"{cell_id}.native_ticket_count"
        )
        if cell_id != f"{lottery_id}:K{k}":
            raise AttributionDataError(f"{cell_id} does not match lottery/K identity")
        candidate_ids = {
            _as_string(
                _as_mapping(candidate, context=f"{cell_id} candidate").get("strategy_id"),
                context=f"{cell_id} candidate strategy_id",
            )
            for candidate in _as_list(
                cell.get("candidate_strategies"), context=f"{cell_id}.candidate_strategies"
            )
        }
        if len(candidate_ids) != len(
            _as_list(cell.get("candidate_strategies"), context=f"{cell_id}.candidate_strategies")
        ):
            raise AttributionDataError(f"{cell_id} contains duplicate candidate IDs")
        candidate_universe.update(candidate_ids)
        raw_experiments = _as_mapping(cell.get("experiments"), context=f"{cell_id}.experiments")
        if set(raw_experiments) != {source for _, source, _ in WINDOWS}:
            raise AttributionDataError(f"{cell_id} does not contain the three frozen windows")
        for _window_label, source_label, window in WINDOWS:
            raw_experiment = _as_mapping(
                raw_experiments[source_label], context=f"{cell_id}.{source_label}"
            )
            key = (cell_id, source_label)
            if key not in decomposition_by_experiment:
                raise AttributionDataError(f"decomposition is missing {key}")
            experiments.append(
                _build_experiment(
                    cell_id=cell_id,
                    lottery_id=lottery_id,
                    k=k,
                    source_label=source_label,
                    expected_window=window,
                    candidate_ids=candidate_ids,
                    raw_experiment=raw_experiment,
                    decomposition_window=decomposition_by_experiment[key],
                    identities=identities,
                )
            )

    experiments.sort(
        key=lambda row: (
            cast(str, row["lottery_id"]),
            cast(int, row["k"]),
            cast(int, row["window"]),
        )
    )
    if enforce_sealed_shape and len(experiments) != EXPECTED_EXPERIMENT_COUNT:
        raise AttributionDataError(
            f"selector experiment count {len(experiments)} != {EXPECTED_EXPERIMENT_COUNT}"
        )

    selected_universe = {
        strategy_id
        for experiment in experiments
        for strategy_id in cast(list[str], experiment["selected_strategy_ids"])
    }
    frozen_universe = {
        cast(str, experiment["frozen_baseline_strategy_id"])
        for experiment in experiments
        if experiment["frozen_baseline_strategy_id"] is not None
    }
    missing_candidate_ids = sorted(candidate_universe - set(identities))
    missing_selected_ids = sorted(selected_universe - set(identities))
    missing_frozen_ids = sorted(frozen_universe - set(identities))
    available = [row for row in experiments if cast(bool, row["available"])]
    switching_active = [row for row in available if cast(bool, row["switching_active"])]

    required_answers = _required_answers(
        selector_cells=raw_cells,
        experiments=experiments,
        identities=identities,
    )
    return {
        "aggregates": {
            "all_experiments_by_diversity_class_and_historical_sign": _count_matrix(experiments),
            "available_experiment_count": len(available),
            "available_experiments_by_diversity_class_and_historical_sign": _count_matrix(
                available
            ),
            "diversity_class_counts": {
                diversity_class: sum(
                    row["diversity_class"] == diversity_class for row in experiments
                )
                for diversity_class in DIVERSITY_CLASSES
            },
            "experiment_count": len(experiments),
            "historical_sign_counts": {
                sign: sum(row["historical_sign"] == sign for row in experiments)
                for sign in HISTORICAL_SIGNS
            },
            "switching_active_experiment_count": len(switching_active),
            "switching_active_experiments_by_diversity_class_and_historical_sign": (
                _count_matrix(switching_active)
            ),
        },
        "boundaries": {
            "composite_score": "NOT_CREATED",
            "database_access": "NO",
            "database_write": "NO",
            "historical_replay": "NOT_RUN",
            "new_selector": "NOT_IMPLEMENTED",
            "optimization": "NOT_RUN",
            "p638_zone2": "NOT_RUN",
            "predictive_advantage": "NOT_ESTABLISHED",
            "profitability": "NOT_ESTABLISHED",
            "semantic_equivalence": "NOT_CLAIMED",
            "significance_testing": "NOT_RUN",
            "transition_order": ("NOT_AVAILABLE; SOURCE_CONTAINS_FREQUENCIES_AND_TRACE_HASH_ONLY"),
        },
        "definitions": {
            "DISTINCT_BINDING_DIVERSITY": (
                "More than one frozen callable identity is selected and no selected "
                "pair shares one callable identity with different bindings."
            ),
            "LINEAGE_SOURCE_INCONSISTENT": (
                "At least one selected Strategy ID is absent from the combined frozen "
                "lineage, has the wrong frozen game identity, or source switch metadata "
                "cannot be reconciled with selected identities."
            ),
            "MIXED_DIVERSITY": (
                "The selected set contains both a same-callable/different-binding pair "
                "and more than one frozen callable identity."
            ),
            "NO_SWITCH": (
                "The source switch count is zero or all selected Strategy IDs collapse "
                "to one frozen binding identity; raw Strategy-ID switch count remains "
                "reported separately."
            ),
            "PARAMETER_SIBLING_DIVERSITY_ONLY": (
                "More than one binding is selected, every resolved selection remains in "
                "one frozen callable family, and a same-callable/different-binding pair "
                "is present."
            ),
            "distinct_binding_boolean": (
                "more_than_one_distinct_binding_identity_selected is true exactly when "
                "more than one frozen callable identity is selected."
            ),
            "transition_boundary": (
                "Classes describe the set and frequencies of selected identities; they "
                "do not assert an unobserved transition order."
            ),
        },
        "experiments": experiments,
        "lineage_merge": lineage_merge,
        "required_answers": required_answers,
        "schema_version": SCHEMA_VERSION,
        "source_data_quality": {
            "candidate_strategy_id_count": len(candidate_universe),
            "candidate_strategy_ids_absent_from_combined_lineage": missing_candidate_ids,
            "candidate_strategy_ids_absent_from_combined_lineage_count": len(missing_candidate_ids),
            "duplicate_selector_cell_id_count": 0,
            "experiment_count": len(experiments),
            "frozen_baseline_strategy_id_count": len(frozen_universe),
            "frozen_baseline_strategy_ids_absent_from_combined_lineage": missing_frozen_ids,
            "frozen_baseline_strategy_ids_absent_from_combined_lineage_count": len(
                missing_frozen_ids
            ),
            "lineage_attribution_complete_available_experiment_count": sum(
                cast(bool, row["lineage_attribution_complete"]) for row in available
            ),
            "lineage_source_inconsistent_available_experiment_count": sum(
                row["diversity_class"] == "LINEAGE_SOURCE_INCONSISTENT" for row in available
            ),
            "null_or_unavailable_experiment_count": sum(
                not cast(bool, row["available"]) for row in experiments
            ),
            "selected_strategy_id_count": len(selected_universe),
            "selected_strategy_ids_absent_from_combined_lineage": missing_selected_ids,
            "selected_strategy_ids_absent_from_combined_lineage_count": len(missing_selected_ids),
            "unexpected_window_count": 0,
        },
        "source_identities": dict(source_identities or {}),
        "study_id": STUDY_ID,
        "task_id": TASK_ID,
    }


def _format_count(count: object) -> str:
    return "—" if count is None else str(count)


def render_report(payload: Mapping[str, Any]) -> str:
    """Render the deterministic human-readable attribution report."""

    lineage = _as_mapping(payload["lineage_merge"], context="lineage_merge")
    quality = _as_mapping(payload["source_data_quality"], context="source_data_quality")
    aggregates = _as_mapping(payload["aggregates"], context="aggregates")
    source_identities = _as_mapping(payload["source_identities"], context="source_identities")
    answers = cast(list[dict[str, Any]], payload["required_answers"])
    experiments = cast(list[dict[str, Any]], payload["experiments"])

    lines = [
        "# Selector lineage diversity attribution R1",
        "",
        "## Outcome",
        "",
        (
            f"The two frozen lineage authorities merge to "
            f"{lineage['combined_record_count']} canonical Strategy IDs "
            f"({lineage['base_resolved_record_count']} base-resolved plus "
            f"{lineage['supplemental_record_count']} Wave26 supplements)."
        ),
        (
            f"The selector contains {quality['selected_strategy_id_count']} unique selected "
            f"Strategy IDs; {quality['selected_strategy_ids_absent_from_combined_lineage_count']} "
            "are absent from that canonical lineage authority. Those experiments fail closed as "
            "LINEAGE_SOURCE_INCONSISTENT; no name-based or semantic alias inference is used."
        ),
        "",
        "## Frozen source identities",
        "",
        "| Authority | Commit | Tree | SHA-256 | Bytes | Path |",
        "|---|---|---|---|---:|---|",
    ]
    for key in sorted(source_identities):
        identity = _as_mapping(source_identities[key], context=f"source {key}")
        lines.append(
            f"| {key} | {identity['commit']} | {identity['tree']} | "
            f"{identity['sha256']} | {identity['size_bytes']} | {identity['path']} |"
        )

    lines.extend(
        [
            "",
            "## Lineage merge",
            "",
            f"- Base result rows: {lineage['base_record_count']}",
            f"- Base resolved rows retained: {lineage['base_resolved_record_count']}",
            (
                "- Base unresolved rows replaced read-only: "
                f"{lineage['base_unresolved_replaced_count']}"
            ),
            f"- Wave26 supplemental rows: {lineage['supplemental_record_count']}",
            f"- Combined canonical IDs: {lineage['combined_record_count']}",
            f"- Complete 135-ID coverage: {lineage['complete_135_id_coverage']}",
            "",
            "## Experiment counts by diversity class and historical sign",
            "",
            "| Diversity class | POSITIVE | ZERO | NEGATIVE | INCONCLUSIVE | Total |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    matrix = cast(
        dict[str, dict[str, int]],
        aggregates["all_experiments_by_diversity_class_and_historical_sign"],
    )
    for diversity_class in DIVERSITY_CLASSES:
        counts = matrix[diversity_class]
        lines.append(
            f"| {diversity_class} | {counts['POSITIVE']} | {counts['ZERO']} | "
            f"{counts['NEGATIVE']} | {counts['INCONCLUSIVE']} | {sum(counts.values())} |"
        )

    lines.extend(
        [
            "",
            "## Per-experiment attribution",
            "",
            "| Cell | Window | Sign | Raw switches | Class | Unique strategies | "
            "Unique bindings | Unique callables |",
            "|---|---:|---|---:|---|---:|---:|---:|",
        ]
    )
    for row in experiments:
        lines.append(
            f"| {row['cell_id']} | {row['window_label']} | {row['historical_sign']} | "
            f"{row['switch_count']} | {row['diversity_class']} | "
            f"{row['unique_strategy_id_count']} | "
            f"{_format_count(row['unique_binding_fingerprint_count'])} | "
            f"{_format_count(row['unique_callable_identity_count'])} |"
        )

    q1 = cast(dict[str, Any], answers[0]["answer"])
    q1_counts = cast(dict[str, int], q1["historical_sign_counts"])
    q2 = cast(dict[str, Any], answers[1]["answer"])
    q3 = cast(dict[str, Any], answers[2]["answer"])
    q4 = cast(dict[str, Any], answers[3]["answer"])
    q5 = cast(dict[str, Any], answers[4]["answer"])
    q6 = cast(dict[str, Any], answers[5]["answer"])
    lines.extend(
        [
            "",
            "## Required answers",
            "",
            (
                "1. Switching-active exact DISTINCT_BINDING_DIVERSITY: "
                f"POSITIVE={q1_counts['POSITIVE']}, NEGATIVE={q1_counts['NEGATIVE']}, "
                f"ZERO={q1_counts['ZERO']}."
            ),
            "",
            (
                "2. Switching-active PARAMETER_SIBLING_DIVERSITY_ONLY: "
                f"{q2['parameter_sibling_diversity_only_count']}."
            ),
            "",
            "3. Five repeated-positive candidates:",
            "",
            "| Cell | Window | Sign | Switches | Diversity class |",
            "|---|---:|---|---:|---|",
        ]
    )
    for cell in cast(list[dict[str, Any]], q3["cells"]):
        for row in cast(list[dict[str, Any]], cell["windows"]):
            lines.append(
                f"| {cell['cell_id']} | {row['window_label']} | "
                f"{row['historical_sign']} | {row['switch_count']} | "
                f"{row['diversity_class']} |"
            )

    bridge = q4
    lines.extend(
        [
            "",
            f"4. P638 C01-C07 bridge family: {bridge['answer']}",
            "",
            "| Window | Sign | Raw switches | Bridge selections | Total selections | Share |",
            "|---|---|---:|---:|---:|---:|",
        ]
    )
    for row in cast(list[dict[str, Any]], bridge["windows"]):
        share = cast(dict[str, Any], row["bridge_family_selection_share"])
        lines.append(
            f"| {row['window_label']} | {row['historical_sign']} | "
            f"{row['raw_switch_count']} | {row['bridge_family_selection_count']} | "
            f"{row['selection_target_count']} | {share['decimal_6']} |"
        )

    q5_counts = cast(dict[str, int], q5["positive_counts_by_diversity_class"])
    positive_with_distinct = q5[
        "positive_present_in_classifiable_experiments_containing_distinct_binding_diversity"
    ]
    positive_without_distinct = q5[
        "positive_present_in_classifiable_experiments_without_distinct_binding_diversity"
    ]
    lines.extend(
        [
            "",
            (
                "5. Positive historical deltas after separation: "
                "classifiable experiments containing distinct-binding diversity="
                f"{positive_with_distinct}; "
                "classifiable experiments without distinct-binding diversity="
                f"{positive_without_distinct}; "
                "LINEAGE_SOURCE_INCONSISTENT positives="
                f"{q5_counts['LINEAGE_SOURCE_INCONSISTENT']}."
            ),
            "",
            (
                "6. Wave26 involvement: "
                f"{q6['appears_in_selector_universe_count']} of 4 appear in a selector "
                f"universe and {q6['appears_in_selection_count']} of 4 are selected."
            ),
            "",
            "| Wave26 Strategy ID | In universe | Selected | Combined class |",
            "|---|---|---|---|",
        ]
    )
    for row in cast(list[dict[str, Any]], q6["strategies"]):
        lines.append(
            f"| {row['strategy_id']} | {row['in_selector_universe']} | "
            f"{row['selected']} | {row['combined_classification']} |"
        )

    lines.extend(
        [
            "",
            "## Interpretation and runtime boundary",
            "",
            "The report is descriptive. Selection frequency does not expose transition order, "
            "so it cannot assign a switch count to a particular family. Missing selector-to-"
            "canonical lineage IDs are reported as source inconsistency rather than inferred.",
            "",
            "    NEW_HISTORICAL_REPLAY = NOT RUN",
            "    DB_ACCESS = NO",
            "    NEW_SELECTOR = NOT IMPLEMENTED",
            "    SEMANTIC_EQUIVALENCE = NOT CLAIMED",
            "    PREDICTIVE_ADVANTAGE = NOT ESTABLISHED",
            "    PROFITABILITY = NOT ESTABLISHED",
            "",
        ]
    )
    return "\n".join(lines)


def run_analysis(
    repository_root: Path = REPOSITORY_ROOT,
) -> tuple[dict[str, Any], bytes, bytes]:
    """Load exact Git authorities and return the result and report in memory."""

    artifacts = load_all_frozen_artifacts(repository_root)
    payload = build_attribution(
        artifacts["rolling_selector"].payload,
        artifacts["rolling_decomposition"].payload,
        artifacts["base_lineage"].payload,
        artifacts["wave26_supplement"].payload,
        source_identities={key: artifacts[key].identity_payload() for key in sorted(artifacts)},
        enforce_sealed_shape=True,
    )
    json_bytes = canonical_json_bytes(payload)
    report_bytes = render_report(payload).encode("utf-8")
    return payload, json_bytes, report_bytes


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, default=REPOSITORY_ROOT)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    repository_root = cast(Path, arguments.repository_root)
    _payload, json_bytes, report_bytes = run_analysis(repository_root)
    DEFAULT_OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    DEFAULT_OUTPUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    DEFAULT_OUTPUT_JSON.write_bytes(json_bytes)
    DEFAULT_OUTPUT_REPORT.write_bytes(report_bytes)
    print(
        json.dumps(
            {
                "output_json": str(DEFAULT_OUTPUT_JSON),
                "output_json_sha256": hashlib.sha256(json_bytes).hexdigest(),
                "output_report": str(DEFAULT_OUTPUT_REPORT),
                "output_report_sha256": hashlib.sha256(report_bytes).hexdigest(),
                "status": "COMPLETE",
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
