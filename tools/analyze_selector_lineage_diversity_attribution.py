"""Attribute sealed rolling-selector outcomes to authority-qualified structural lineage.

The analyzer reads five exact JSON blobs from Git object storage, never from mutable
source worktrees. It performs no replay, database access, strategy execution, selector
construction, optimization, fuzzy aliasing, or transition-order inference.
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

TASK_ID = "SELECTOR_LINEAGE_DIVERSITY_ATTRIBUTION_R2"
STUDY_ID = "SELECTOR_LINEAGE_DIVERSITY_ATTRIBUTION_V2"
SCHEMA_VERSION = "SELECTOR_LINEAGE_DIVERSITY_ATTRIBUTION_RESULT_V2"

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_JSON = (
    REPOSITORY_ROOT / "docs/research/matrix-native-results/"
    "selector-lineage-diversity-attribution-r2-result.json"
)
DEFAULT_OUTPUT_REPORT = (
    REPOSITORY_ROOT / "docs/research/selector-lineage-diversity-attribution-r2.md"
)

EXPECTED_CANONICAL_STRATEGY_COUNT = 135
EXPECTED_BASE_RESOLVED_STRATEGY_COUNT = 131
EXPECTED_SUPPLEMENTAL_STRATEGY_COUNT = 4
EXPECTED_QUALIFIED_SELECTOR_IDENTITY_COUNT = 135
EXPECTED_RAW_SELECTOR_LABEL_COUNT = 134
EXPECTED_PRODUCTION_EXACT_JOIN_COUNT = 25
EXPECTED_SELECTOR_SUPPLEMENT_ROW_COUNT = 110
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
    "INCONCLUSIVE",
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

QualifiedIdentityKey = tuple[str, str, str, str]


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


@dataclass(frozen=True, slots=True)
class QualifiedLineageIdentity:
    """One selector identity qualified by authority, lottery, raw label, and version."""

    authority_qualified_identity_key: QualifiedIdentityKey
    source_authority_id: str
    lottery_id: str
    strategy_id: str
    strategy_version: str
    source_authority: str
    source_classification: str
    binding_fingerprint_sha256: str
    binding_identity: str
    callable_identity: str
    callable_family_label: str
    implementation_identity: str
    structural_source_digest_sha256: str
    donor_identity_alias: bool
    production_structural_binding_identity: str | None = None
    production_structural_callable_identity: str | None = None
    combined_classification: str = ""

    def as_payload(self) -> dict[str, Any]:
        return {
            "authority_qualified_identity_key": list(
                self.authority_qualified_identity_key
            ),
            "binding_fingerprint_sha256": self.binding_fingerprint_sha256,
            "binding_identity": self.binding_identity,
            "callable_family_label": self.callable_family_label,
            "callable_identity": self.callable_identity,
            "combined_classification": self.combined_classification,
            "donor_identity_alias": self.donor_identity_alias,
            "implementation_identity": self.implementation_identity,
            "lottery_id": self.lottery_id,
            "production_structural_binding_identity": (
                self.production_structural_binding_identity
            ),
            "production_structural_callable_identity": (
                self.production_structural_callable_identity
            ),
            "source_authority": self.source_authority,
            "source_authority_id": self.source_authority_id,
            "source_classification": self.source_classification,
            "strategy_id": self.strategy_id,
            "strategy_version": self.strategy_version,
            "structural_source_digest_sha256": self.structural_source_digest_sha256,
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
SELECTOR_UNIVERSE_LINEAGE_ARTIFACT = ArtifactSpec(
    key="selector_universe_lineage",
    commit="39592593126325533d664b57097be280682fe2ab",
    tree="9abc5d50ed9ecbe3dbab4a7e1a6c4bf7fe8a2ee3",
    relative_path=(
        "docs/research/matrix-native-results/"
        "selector-universe-lineage-supplement-r1-result.json"
    ),
    sha256="461afd3bd0b7eeca93546562330d03234ad57aa2aa4dff25d4432cc254795f37",
)
ARTIFACT_SPECS = (
    SELECTOR_ARTIFACT,
    DECOMPOSITION_ARTIFACT,
    BASE_LINEAGE_ARTIFACT,
    WAVE26_ARTIFACT,
    SELECTOR_UNIVERSE_LINEAGE_ARTIFACT,
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
    """Load only the five packet-authorized immutable Git artifacts."""

    try:
        root = repository_root.resolve()
        observed_root = Path(_git_text(root, ("rev-parse", "--show-toplevel"))).resolve()
        if observed_root != root:
            raise AttributionDataError(
                f"REPOSITORY_ROOT_MISMATCH: requested {root}, observed {observed_root}"
            )
        return {spec.key: load_frozen_artifact(spec, root) for spec in ARTIFACT_SPECS}
    except AttributionDataError as exc:
        raise AttributionDataError(f"SOURCE_AUTHORITY_DRIFT: {exc}") from exc


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


def _qualified_key(value: object, *, context: str) -> QualifiedIdentityKey:
    parts = _as_list(value, context=context)
    if len(parts) != 4:
        raise AttributionDataError(f"{context} must contain exactly four identity fields")
    return cast(
        QualifiedIdentityKey,
        tuple(
            _as_string(part, context=f"{context}[{index}]")
            for index, part in enumerate(parts)
        ),
    )


def _qualified_row_key(
    record: Mapping[str, Any],
    *,
    context: str,
) -> QualifiedIdentityKey:
    key = _qualified_key(
        record.get("authority_qualified_identity_key"),
        context=f"{context}.authority_qualified_identity_key",
    )
    explicit_key = (
        _as_string(record.get("source_authority_id"), context=f"{context}.source_authority_id"),
        _as_string(record.get("lottery_id"), context=f"{context}.lottery_id"),
        _as_string(record.get("strategy_id"), context=f"{context}.strategy_id"),
        _as_string(record.get("strategy_version"), context=f"{context}.strategy_version"),
    )
    if key != explicit_key:
        raise AttributionDataError(
            f"AUTHORITY_QUALIFIED_IDENTITY_CONFLICT: {context} {key} != {explicit_key}"
        )
    return key


def _unique_qualified_records(
    raw_records: object,
    *,
    context: str,
) -> dict[QualifiedIdentityKey, Mapping[str, Any]]:
    records: dict[QualifiedIdentityKey, Mapping[str, Any]] = {}
    for index, raw_record in enumerate(_as_list(raw_records, context=context)):
        record = _as_mapping(raw_record, context=f"{context}[{index}]")
        key = _qualified_row_key(record, context=f"{context}[{index}]")
        if key in records:
            raise AttributionDataError(f"{context} contains duplicate qualified key {key}")
        records[key] = record
    return records


def _require_no_donor_alias(record: Mapping[str, Any], *, context: str) -> None:
    provenance = _as_mapping(
        record.get("donor_provenance_references"),
        context=f"{context}.donor_provenance_references",
    )
    if provenance.get("donor_identity_alias") is not False:
        raise AttributionDataError(f"DONOR_IDENTITY_ALIAS_FORBIDDEN: {context}")


def _qualified_combined_classifications(
    identities: Mapping[QualifiedIdentityKey, QualifiedLineageIdentity],
) -> dict[QualifiedIdentityKey, str]:
    by_binding: defaultdict[str, list[QualifiedIdentityKey]] = defaultdict(list)
    by_callable: defaultdict[str, list[QualifiedIdentityKey]] = defaultdict(list)
    for key, identity in identities.items():
        by_binding[identity.binding_identity].append(key)
        by_callable[identity.callable_identity].append(key)

    classifications: dict[QualifiedIdentityKey, str] = {}
    for key, identity in identities.items():
        if len(by_binding[identity.binding_identity]) > 1:
            classification = "IDENTICAL_BINDING"
        elif len(by_callable[identity.callable_identity]) > 1:
            classification = "SAME_CALLABLE_DIFFERENT_BINDING"
        else:
            classification = "DISTINCT_BINDING"
        classifications[key] = classification
    return classifications


def merge_authority_qualified_lineage(
    selector_universe_lineage: Mapping[str, Any],
    base_lineage: Mapping[str, Any],
    wave26_supplement: Mapping[str, Any],
    production_identities: Mapping[str, LineageIdentity],
    production_summary: Mapping[str, Any],
    *,
    enforce_sealed_shape: bool = True,
) -> tuple[dict[QualifiedIdentityKey, QualifiedLineageIdentity], dict[str, Any]]:
    """Merge 25 exact production joins and 110 selector-supplement rows by qualified key."""

    if selector_universe_lineage.get("study_id") != "SELECTOR_UNIVERSE_LINEAGE_SUPPLEMENT_R1":
        raise AttributionDataError("unexpected selector-universe lineage study_id")
    if (
        selector_universe_lineage.get("schema_version")
        != "selector-universe-lineage-supplement/v1"
    ):
        raise AttributionDataError("unexpected selector-universe lineage schema_version")

    selector_authority = _as_mapping(
        selector_universe_lineage.get("selector_authority"),
        context="selector_universe_lineage.selector_authority",
    )
    expected_selector_authority = {
        "commit": SELECTOR_ARTIFACT.commit,
        "tree": SELECTOR_ARTIFACT.tree,
        "result_path": SELECTOR_ARTIFACT.relative_path,
        "result_sha256": SELECTOR_ARTIFACT.sha256,
    }
    observed_selector_authority = {
        key: selector_authority.get(key) for key in expected_selector_authority
    }
    if observed_selector_authority != expected_selector_authority:
        raise AttributionDataError(
            "SELECTOR_UNIVERSE_AUTHORITY_CONFLICT: "
            f"{observed_selector_authority} != {expected_selector_authority}"
        )

    census = _as_mapping(
        selector_universe_lineage.get("census"),
        context="selector_universe_lineage.census",
    )
    expected_census = {
        "qualified_selector_identities": EXPECTED_QUALIFIED_SELECTOR_IDENTITY_COUNT,
        "raw_selector_labels": EXPECTED_RAW_SELECTOR_LABEL_COUNT,
        "production_exact_joins": EXPECTED_PRODUCTION_EXACT_JOIN_COUNT,
        "supplement_rows": EXPECTED_SELECTOR_SUPPLEMENT_ROW_COUNT,
    }
    if {key: census.get(key) for key in expected_census} != expected_census:
        raise AttributionDataError("SELECTOR_UNIVERSE_CENSUS_MISMATCH")

    accounting = _as_mapping(
        selector_universe_lineage.get("combined_accounting"),
        context="selector_universe_lineage.combined_accounting",
    )
    expected_accounting = {
        "accounted_identities": EXPECTED_QUALIFIED_SELECTOR_IDENTITY_COUNT,
        "accounting_is_complete": True,
        "production_exact_joins": EXPECTED_PRODUCTION_EXACT_JOIN_COUNT,
        "qualified_selector_identities": EXPECTED_QUALIFIED_SELECTOR_IDENTITY_COUNT,
        "supplement_rows": EXPECTED_SELECTOR_SUPPLEMENT_ROW_COUNT,
    }
    if dict(accounting) != expected_accounting:
        raise AttributionDataError("SELECTOR_UNIVERSE_COMBINED_ACCOUNTING_MISMATCH")

    invariants = _as_mapping(
        selector_universe_lineage.get("invariants"),
        context="selector_universe_lineage.invariants",
    )
    expected_key_fields = [
        "source_authority_id",
        "lottery_id",
        "strategy_id",
        "strategy_version",
    ]
    if invariants.get("canonical_identity_key") != expected_key_fields:
        raise AttributionDataError("AUTHORITY_QUALIFIED_KEY_CONTRACT_MISMATCH")
    if (
        invariants.get("raw_label_collision_strategy_id") != "midfreq_fourier_2bet"
        or invariants.get("raw_label_collision_is_two_identities") is not True
        or invariants.get("safe_production_alias_mapping") != "NO"
        or invariants.get("donor_relation_promoted_to_canonical_identity") != "NO"
        or invariants.get("cross_lottery_ports_collapsed") != "NO"
    ):
        raise AttributionDataError("SELECTOR_UNIVERSE_IDENTITY_INVARIANT_MISMATCH")

    contract = _as_mapping(
        selector_universe_lineage.get("classification_contract"),
        context="selector_universe_lineage.classification_contract",
    )
    if (
        contract.get("supplement_success_state") != "RESOLVED_REPLAY_BINDING"
        or contract.get("unresolved_policy") != "FAIL_CLOSED"
    ):
        raise AttributionDataError("SELECTOR_UNIVERSE_CLASSIFICATION_CONTRACT_MISMATCH")
    sealed_binding_fingerprint = _as_sha256(
        selector_universe_lineage.get("binding_fingerprint_sha256"),
        context="selector_universe_lineage.binding_fingerprint_sha256",
    )

    selected_records = _unique_qualified_records(
        selector_universe_lineage.get("qualified_selector_identities"),
        context="selector_universe_lineage.qualified_selector_identities",
    )
    production_rows = _unique_qualified_records(
        selector_universe_lineage.get("production_exact_joins"),
        context="selector_universe_lineage.production_exact_joins",
    )
    supplement_rows = _unique_qualified_records(
        selector_universe_lineage.get("supplement_rows"),
        context="selector_universe_lineage.supplement_rows",
    )
    accounted_keys = set(production_rows) | set(supplement_rows)
    if set(production_rows) & set(supplement_rows) or accounted_keys != set(selected_records):
        raise AttributionDataError("QUALIFIED_SELECTOR_LINEAGE_PARTITION_MISMATCH")

    raw_labels = {key[2] for key in selected_records}
    collision_keys = sorted(key for key in selected_records if key[2] == "midfreq_fourier_2bet")
    expected_collision_keys = sorted(
        (
            (
                "P638_CURRENT_REPLAY_AND_RANKING",
                "P638",
                "midfreq_fourier_2bet",
                "v0.1-p638-wave1",
            ),
            (
                "T539_HISTORICAL_SQLITE",
                "T539",
                "midfreq_fourier_2bet",
                "v0.1",
            ),
        )
    )
    if len(raw_labels) != EXPECTED_RAW_SELECTOR_LABEL_COUNT:
        raise AttributionDataError("RAW_SELECTOR_LABEL_CENSUS_MISMATCH")
    if collision_keys != expected_collision_keys:
        raise AttributionDataError("CROSS_LOTTERY_RAW_LABEL_COLLISION_MISMATCH")

    base_records = _unique_records(base_lineage.get("records"), context="base_lineage.records")
    wave26_records = _unique_records(
        wave26_supplement.get("records"), context="wave26_supplement.records"
    )
    identities: dict[QualifiedIdentityKey, QualifiedLineageIdentity] = {}
    exact_join_source_counts: Counter[str] = Counter()

    for key, row in production_rows.items():
        context = f"production_exact_joins[{key}]"
        if (
            row.get("join_status") != "PRODUCTION_CATALOG_EXACT_JOIN"
            or row.get("resolution_status") != "RESOLVED_REPLAY_BINDING"
        ):
            raise AttributionDataError(f"PRODUCTION_EXACT_JOIN_STATUS_MISMATCH: {key}")
        _require_no_donor_alias(row, context=context)
        strategy_id = key[2]
        production_identity = production_identities.get(strategy_id)
        base_record = base_records.get(strategy_id)
        if production_identity is None or base_record is None:
            raise AttributionDataError(f"PRODUCTION_EXACT_JOIN_MISSING_STATIC_LINEAGE: {key}")
        if key[1] not in production_identity.game_identities:
            raise AttributionDataError(f"PRODUCTION_EXACT_JOIN_GAME_MISMATCH: {key}")

        if base_record.get("classification") == "DYNAMIC_OR_UNRESOLVED":
            wave_record = wave26_records.get(strategy_id)
            if wave_record is None:
                raise AttributionDataError(f"PRODUCTION_EXACT_JOIN_MISSING_WAVE26: {key}")
            expected_implementation = wave_record.get("registry_adapter")
            source_authority = "PRODUCTION_EXACT_JOIN_WAVE26"
        else:
            if strategy_id in wave26_records:
                raise AttributionDataError(f"PRODUCTION_EXACT_JOIN_WAVE26_OVERLAP: {key}")
            expected_implementation = base_record.get("registry_adapter_path")
            if row.get("implementation_module") != base_record.get("implementation_module"):
                raise AttributionDataError(f"PRODUCTION_EXACT_JOIN_MODULE_MISMATCH: {key}")
            source_authority = "PRODUCTION_EXACT_JOIN_STATIC_LINEAGE"
        if row.get("callable_or_class_symbol") != expected_implementation:
            raise AttributionDataError(f"PRODUCTION_EXACT_JOIN_IMPLEMENTATION_MISMATCH: {key}")

        fingerprint = _as_sha256(
            row.get("binding_fingerprint_sha256"),
            context=f"{context}.binding_fingerprint_sha256",
        )
        exact_join_source_counts[source_authority] += 1
        identities[key] = QualifiedLineageIdentity(
            authority_qualified_identity_key=key,
            source_authority_id=key[0],
            lottery_id=key[1],
            strategy_id=strategy_id,
            strategy_version=key[3],
            source_authority=source_authority,
            source_classification=production_identity.source_classification,
            binding_fingerprint_sha256=fingerprint,
            binding_identity=f"authority-qualified-binding-sha256:{fingerprint}",
            callable_identity=production_identity.callable_identity,
            callable_family_label=production_identity.callable_family_label,
            implementation_identity=_as_string(
                row.get("callable_or_class_symbol"),
                context=f"{context}.callable_or_class_symbol",
            ),
            structural_source_digest_sha256=_as_sha256(
                row.get("structural_source_digest_sha256"),
                context=f"{context}.structural_source_digest_sha256",
            ),
            donor_identity_alias=False,
            production_structural_binding_identity=production_identity.binding_identity,
            production_structural_callable_identity=production_identity.callable_identity,
        )

    for key, row in supplement_rows.items():
        context = f"supplement_rows[{key}]"
        if row.get("resolution_status") != "RESOLVED_REPLAY_BINDING":
            raise AttributionDataError(f"SELECTOR_SUPPLEMENT_ROW_UNRESOLVED: {key}")
        _require_no_donor_alias(row, context=context)
        fingerprint = _as_sha256(
            row.get("binding_fingerprint_sha256"),
            context=f"{context}.binding_fingerprint_sha256",
        )
        callable_symbol = _as_string(
            row.get("callable_symbol"), context=f"{context}.callable_symbol"
        )
        identities[key] = QualifiedLineageIdentity(
            authority_qualified_identity_key=key,
            source_authority_id=key[0],
            lottery_id=key[1],
            strategy_id=key[2],
            strategy_version=key[3],
            source_authority="SELECTOR_UNIVERSE_LINEAGE_SUPPLEMENT",
            source_classification="RESOLVED_REPLAY_BINDING",
            binding_fingerprint_sha256=fingerprint,
            binding_identity=f"authority-qualified-binding-sha256:{fingerprint}",
            callable_identity=f"selector-supplement-callable:{callable_symbol}",
            callable_family_label=callable_symbol,
            implementation_identity=_as_string(
                row.get("callable_or_class_symbol"),
                context=f"{context}.callable_or_class_symbol",
            ),
            structural_source_digest_sha256=_as_sha256(
                row.get("structural_source_digest_sha256"),
                context=f"{context}.structural_source_digest_sha256",
            ),
            donor_identity_alias=False,
        )

    combined_classes = _qualified_combined_classifications(identities)
    identities = {
        key: replace(identity, combined_classification=combined_classes[key])
        for key, identity in identities.items()
    }
    if enforce_sealed_shape:
        observed = (
            len(selected_records),
            len(raw_labels),
            len(production_rows),
            len(supplement_rows),
            len(identities),
        )
        expected = (
            EXPECTED_QUALIFIED_SELECTOR_IDENTITY_COUNT,
            EXPECTED_RAW_SELECTOR_LABEL_COUNT,
            EXPECTED_PRODUCTION_EXACT_JOIN_COUNT,
            EXPECTED_SELECTOR_SUPPLEMENT_ROW_COUNT,
            EXPECTED_QUALIFIED_SELECTOR_IDENTITY_COUNT,
        )
        if observed != expected:
            raise AttributionDataError(
                f"AUTHORITY_QUALIFIED_LINEAGE_ACCOUNTING_MISMATCH: {observed} != {expected}"
            )

    combined_counts = Counter(identity.combined_classification for identity in identities.values())
    return identities, {
        "base_production_lineage": dict(production_summary),
        "binding_fingerprint_sha256": sealed_binding_fingerprint,
        "combined_classification_counts": {
            key: combined_counts.get(key, 0)
            for key in (
                "IDENTICAL_BINDING",
                "SAME_CALLABLE_DIFFERENT_BINDING",
                "DISTINCT_BINDING",
            )
        },
        "complete_135_qualified_identity_coverage": (
            len(identities) == EXPECTED_QUALIFIED_SELECTOR_IDENTITY_COUNT
        ),
        "cross_lottery_raw_label_collision_identity_keys": [
            list(key) for key in collision_keys
        ],
        "donor_identity_alias_count": sum(
            identity.donor_identity_alias for identity in identities.values()
        ),
        "production_exact_join_count": len(production_rows),
        "production_exact_join_source_counts": dict(sorted(exact_join_source_counts.items())),
        "qualified_selector_identity_count": len(selected_records),
        "raw_selector_label_count": len(raw_labels),
        "records": [identities[key].as_payload() for key in sorted(identities)],
        "selector_supplement_row_count": len(supplement_rows),
        "total_structurally_accounted": len(identities),
        "unique_binding_fingerprint_count": len(
            {identity.binding_fingerprint_sha256 for identity in identities.values()}
        ),
        "unique_callable_identity_count": len(
            {identity.callable_identity for identity in identities.values()}
        ),
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
    frequencies: Mapping[QualifiedIdentityKey, int],
    identities: Mapping[QualifiedIdentityKey, QualifiedLineageIdentity],
    *,
    identity_attribute: str,
    label_attribute: str | None = None,
) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter()
    strategy_ids: defaultdict[str, list[str]] = defaultdict(list)
    qualified_keys: defaultdict[str, list[QualifiedIdentityKey]] = defaultdict(list)
    labels: defaultdict[str, set[str]] = defaultdict(set)
    for key, count in frequencies.items():
        identity = identities.get(key)
        if identity is None:
            continue
        identity_value = cast(str, getattr(identity, identity_attribute))
        counts[identity_value] += count
        strategy_ids[identity_value].append(identity.strategy_id)
        qualified_keys[identity_value].append(key)
        if label_attribute is not None:
            labels[identity_value].add(cast(str, getattr(identity, label_attribute)))

    output: list[dict[str, Any]] = []
    for identity_value in sorted(counts):
        row: dict[str, Any] = {
            "identity": identity_value,
            "selection_count": counts[identity_value],
            "strategy_ids": sorted(strategy_ids[identity_value]),
            "authority_qualified_identity_keys": [
                list(key) for key in sorted(qualified_keys[identity_value])
            ],
        }
        if label_attribute is not None:
            row["labels"] = sorted(labels[identity_value])
        output.append(row)
    return output


def attribute_selection_diversity(
    frequencies: Mapping[QualifiedIdentityKey, int],
    *,
    switch_count: int,
    lottery_id: str,
    identities: Mapping[QualifiedIdentityKey, QualifiedLineageIdentity],
    available: bool = True,
) -> dict[str, Any]:
    """Classify selected structural diversity without inventing transition order."""

    selected_keys = sorted(frequencies)
    if not available:
        if selected_keys or switch_count != 0:
            raise AttributionDataError("INCONCLUSIVE_EXPERIMENT_CONTAINS_SELECTION_ACTIVITY")
        return {
            "actual_distinct_binding_diversity_selected": False,
            "any_selected_pair_same_callable_different_binding": False,
            "diversity_class": "INCONCLUSIVE",
            "lineage_attribution_applicable": False,
            "lineage_attribution_complete": False,
            "lineage_source_inconsistency_reasons": [],
            "more_than_one_distinct_binding_identity_selected": False,
            "more_than_one_structural_binding_selected": False,
            "parameter_sibling_families_involved": [],
            "same_callable_different_binding_pairs": [],
            "selected_authority_qualified_identities": [],
            "selection_frequency_by_binding_identity": [],
            "selection_frequency_by_callable_family": [],
            "structurally_unresolved_authority_qualified_identity_keys": [],
            "structurally_unresolved_selected_strategy_ids": [],
            "unattributed_selection_frequency": [],
            "unique_authority_qualified_identity_count": 0,
            "unique_binding_fingerprint_count": 0,
            "unique_binding_fingerprints": [],
            "unique_callable_identities": [],
            "unique_callable_identity_count": 0,
            "unique_strategy_id_count": 0,
            "wrong_game_identity_selected_strategy_ids": [],
            "wrong_lottery_identity_keys": [],
        }

    missing_keys = sorted(set(selected_keys) - set(identities))
    resolved = {
        key: identities[key] for key in selected_keys if key in identities
    }
    wrong_lottery_keys = sorted(
        key for key, identity in resolved.items() if lottery_id != identity.lottery_id
    )
    reasons: list[str] = []
    if missing_keys:
        reasons.append("SELECTED_QUALIFIED_IDENTITIES_ABSENT_FROM_COMBINED_LINEAGE")
    if wrong_lottery_keys:
        reasons.append("SELECTED_STRATEGY_LINEAGE_GAME_IDENTITY_MISMATCH")
    if switch_count > 0 and len(selected_keys) < 2:
        reasons.append("NONZERO_SWITCH_COUNT_WITH_FEWER_THAN_TWO_SELECTED_STRATEGY_IDS")
    if switch_count == 0 and len(selected_keys) > 1:
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
        {
            "authority_qualified_identity_key": list(key),
            "selection_count": frequencies[key],
            "strategy_id": key[2],
        }
        for key in missing_keys
    ]
    selected_identity_rows = [
        {
            "authority_qualified_identity_key": list(key),
            "binding_fingerprint_sha256": identity.binding_fingerprint_sha256,
            "callable_family_label": identity.callable_family_label,
            "callable_identity": identity.callable_identity,
            "selection_count": frequencies[key],
            "source_authority_id": identity.source_authority_id,
            "strategy_id": identity.strategy_id,
            "strategy_version": identity.strategy_version,
        }
        for key, identity in sorted(resolved.items())
    ]

    if reasons:
        return {
            "actual_distinct_binding_diversity_selected": None,
            "any_selected_pair_same_callable_different_binding": None,
            "diversity_class": "LINEAGE_SOURCE_INCONSISTENT",
            "lineage_attribution_applicable": True,
            "lineage_attribution_complete": False,
            "lineage_source_inconsistency_reasons": reasons,
            "more_than_one_distinct_binding_identity_selected": None,
            "more_than_one_structural_binding_selected": None,
            "parameter_sibling_families_involved": [],
            "same_callable_different_binding_pairs": [],
            "selected_authority_qualified_identities": selected_identity_rows,
            "selection_frequency_by_binding_identity": binding_buckets,
            "selection_frequency_by_callable_family": callable_buckets,
            "structurally_unresolved_authority_qualified_identity_keys": [
                list(key) for key in missing_keys
            ],
            "structurally_unresolved_selected_strategy_ids": sorted(
                {key[2] for key in missing_keys}
            ),
            "unique_authority_qualified_identity_count": len(selected_keys),
            "unique_binding_fingerprint_count": None,
            "unique_binding_fingerprints": None,
            "unique_callable_identities": None,
            "unique_callable_identity_count": None,
            "unique_strategy_id_count": len({key[2] for key in selected_keys}),
            "unattributed_selection_frequency": unresolved_frequencies,
            "wrong_game_identity_selected_strategy_ids": sorted(
                {key[2] for key in wrong_lottery_keys}
            ),
            "wrong_lottery_identity_keys": [list(key) for key in wrong_lottery_keys],
        }

    binding_ids = {identity.binding_identity for identity in resolved.values()}
    callable_ids = {identity.callable_identity for identity in resolved.values()}
    sibling_pairs: list[dict[str, Any]] = []
    for left_key, right_key in itertools.combinations(selected_keys, 2):
        left = resolved[left_key]
        right = resolved[right_key]
        if (
            left.callable_identity == right.callable_identity
            and left.binding_identity != right.binding_identity
        ):
            sibling_pairs.append(
                {
                    "callable_identity": left.callable_identity,
                    "left_authority_qualified_identity_key": list(left_key),
                    "left_strategy_id": left.strategy_id,
                    "right_authority_qualified_identity_key": list(right_key),
                    "right_strategy_id": right.strategy_id,
                }
            )

    by_callable: defaultdict[str, list[QualifiedIdentityKey]] = defaultdict(list)
    for key, identity in resolved.items():
        by_callable[identity.callable_identity].append(key)
    sibling_families: list[dict[str, Any]] = []
    for callable_identity, keys in sorted(by_callable.items()):
        family_bindings = {resolved[key].binding_identity for key in keys}
        if len(family_bindings) <= 1:
            continue
        sibling_families.append(
            {
                "authority_qualified_identity_keys": [list(key) for key in sorted(keys)],
                "binding_fingerprints": sorted(
                    resolved[key].binding_fingerprint_sha256 for key in keys
                ),
                "callable_family_labels": sorted(
                    {resolved[key].callable_family_label for key in keys}
                ),
                "callable_identity": callable_identity,
                "strategy_ids": sorted(resolved[key].strategy_id for key in keys),
            }
        )

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
        "actual_distinct_binding_diversity_selected": has_distinct_callable,
        "any_selected_pair_same_callable_different_binding": has_sibling_pair,
        "diversity_class": diversity_class,
        "lineage_attribution_applicable": True,
        "lineage_attribution_complete": diversity_class != "LINEAGE_SOURCE_INCONSISTENT",
        "lineage_source_inconsistency_reasons": reasons,
        "more_than_one_distinct_binding_identity_selected": has_distinct_callable,
        "more_than_one_structural_binding_selected": len(binding_ids) > 1,
        "parameter_sibling_families_involved": sibling_families,
        "same_callable_different_binding_pairs": sibling_pairs,
        "selected_authority_qualified_identities": selected_identity_rows,
        "selection_frequency_by_binding_identity": binding_buckets,
        "selection_frequency_by_callable_family": callable_buckets,
        "structurally_unresolved_authority_qualified_identity_keys": [],
        "structurally_unresolved_selected_strategy_ids": [],
        "unique_authority_qualified_identity_count": len(selected_keys),
        "unique_binding_fingerprint_count": len(binding_ids),
        "unique_binding_fingerprints": sorted(
            identity.binding_fingerprint_sha256 for identity in resolved.values()
        ),
        "unique_callable_identities": sorted(callable_ids),
        "unique_callable_identity_count": len(callable_ids),
        "unique_strategy_id_count": len({key[2] for key in selected_keys}),
        "unattributed_selection_frequency": [],
        "wrong_game_identity_selected_strategy_ids": [],
        "wrong_lottery_identity_keys": [],
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
    candidate_identity_keys: Mapping[str, QualifiedIdentityKey],
    raw_experiment: Mapping[str, Any],
    decomposition_window: Mapping[str, Any],
    identities: Mapping[QualifiedIdentityKey, QualifiedLineageIdentity],
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
    if not selected_ids <= set(candidate_identity_keys):
        raise AttributionDataError(
            f"{context} selected IDs outside candidate universe: "
            f"{sorted(selected_ids - set(candidate_identity_keys))}"
        )
    qualified_frequencies = {
        candidate_identity_keys[strategy_id]: count
        for strategy_id, count in frequencies.items()
    }
    switch_count = _as_nonnegative_int(
        raw_experiment.get("rolling_strategy_switch_count"),
        context=f"{context}.rolling_strategy_switch_count",
    )
    if switch_count != decomposition_window.get("switch_count"):
        raise AttributionDataError(f"{context} switch count differs from decomposition")

    raw_available = decomposition_window.get("available")
    if not isinstance(raw_available, bool):
        raise AttributionDataError(f"{context}.available must be boolean")
    available = raw_available
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
    eligible_target_count = _as_nonnegative_int(
        raw_experiment.get("eligible_target_count"),
        context=f"{context}.eligible_target_count",
    )
    expected_target_count = _as_nonnegative_int(
        decomposition_window.get("rolling_selection_target_count"),
        context=f"{context}.rolling_selection_target_count",
    )
    if selection_target_count != expected_target_count:
        raise AttributionDataError(
            f"{context} selection frequency total {selection_target_count} "
            f"!= {expected_target_count}"
        )
    if eligible_target_count != selection_target_count:
        raise AttributionDataError(
            f"{context} eligible target count {eligible_target_count} "
            f"!= selection target count {selection_target_count}"
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
        qualified_frequencies,
        switch_count=switch_count,
        lottery_id=lottery_id,
        identities=identities,
        available=available,
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
        "original_eligible_target_count": eligible_target_count,
        "original_exact_delta": _copy_source_delta(source_delta),
        "original_relative_paired_delta": _copy_source_delta(
            raw_experiment.get("relative_paired_delta")
        ),
        "original_sign": sign,
        "original_switch_count": switch_count,
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
    production_identities: Mapping[str, LineageIdentity],
) -> dict[str, Any]:
    bridge_identities = [
        production_identities[strategy_id] for strategy_id in P638_BRIDGE_STRATEGY_IDS
    ]
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
    p638_experiments = sorted(
        (
            row
            for row in experiments
            if row.get("lottery_id") == "P638" and row.get("available")
        ),
        key=lambda row: (cast(int, row["k"]), cast(int, row["window"])),
    )
    for experiment in p638_experiments:
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
                "cell_id": experiment["cell_id"],
                "historical_sign": experiment["historical_sign"],
                "k": experiment["k"],
                "raw_switch_count": experiment["switch_count"],
                "selection_target_count": total_count,
                "window": experiment["window"],
                "window_label": experiment["window_label"],
            }
        )
    bridge_total = sum(cast(int, row["bridge_family_selection_count"]) for row in rows)
    p638_total = sum(cast(int, row["selection_target_count"]) for row in rows)
    k1_rows = [row for row in rows if row["cell_id"] == "P638:K1"]
    k1_bridge_total = sum(
        cast(int, row["bridge_family_selection_count"]) for row in k1_rows
    )
    k1_total = sum(cast(int, row["selection_target_count"]) for row in k1_rows)
    by_window: list[dict[str, Any]] = []
    for window_label, _source_label, window in WINDOWS:
        window_rows = [row for row in rows if row["window"] == window]
        window_bridge = sum(
            cast(int, row["bridge_family_selection_count"]) for row in window_rows
        )
        window_total = sum(cast(int, row["selection_target_count"]) for row in window_rows)
        by_window.append(
            {
                "bridge_family_selection_count": window_bridge,
                "bridge_family_selection_share": _ratio_payload(window_bridge, window_total),
                "selection_target_count": window_total,
                "window": window,
                "window_label": window_label,
            }
        )
    return {
        "answer": (
            "SELECTION_FREQUENCY_ONLY: the exact share of sealed P638 selections inside "
            "C01-C07 is reported, but exact switches cannot be assigned to the family "
            "because ordered transition endpoints are unavailable."
        ),
        "all_p638_available_experiments": rows,
        "bridge_binding_identity_count": len(binding_ids),
        "bridge_callable_family_identity": next(iter(family_ids)),
        "bridge_strategy_ids": list(P638_BRIDGE_STRATEGY_IDS),
        "by_window": by_window,
        "overall_p638_bridge_selection_count": bridge_total,
        "overall_p638_selection_count": p638_total,
        "overall_p638_selection_share": _ratio_payload(bridge_total, p638_total),
        "p638_k1_bridge_selection_count": k1_bridge_total,
        "p638_k1_selection_count": k1_total,
        "p638_k1_selection_share": _ratio_payload(k1_bridge_total, k1_total),
        "transition_order_available": False,
    }


def _wave26_answer(
    selector_cells: Sequence[Mapping[str, Any]],
    experiments: Sequence[Mapping[str, Any]],
    identities: Mapping[QualifiedIdentityKey, QualifiedLineageIdentity],
    production_identities: Mapping[str, LineageIdentity],
) -> dict[str, Any]:
    wave_ids = sorted(
        strategy_id
        for strategy_id, identity in production_identities.items()
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

    rows: list[dict[str, Any]] = []
    for strategy_id in wave_ids:
        production_identity = production_identities[strategy_id]
        qualified = sorted(
            (
                identity
                for identity in identities.values()
                if identity.strategy_id == strategy_id
            ),
            key=lambda identity: identity.authority_qualified_identity_key,
        )
        rows.append(
            {
                "binding_identity": production_identity.binding_identity,
                "binding_fingerprint_sha256": (
                    production_identity.binding_fingerprint_sha256
                ),
                "callable_family_label": production_identity.callable_family_label,
                "callable_identity": production_identity.callable_identity,
                "combined_classification": production_identity.combined_classification,
                "contributes_to_selected_qualified_lineage": bool(qualified),
                "in_selector_universe": bool(universe_cells[strategy_id]),
                "qualified_selected_identities": [
                    identity.as_payload() for identity in qualified
                ],
                "selected": bool(selected_experiments[strategy_id]),
                "selected_experiments": selected_experiments[strategy_id],
                "selector_universe_cells": sorted(universe_cells[strategy_id]),
                "source_resolution_classification": (
                    production_identity.source_classification
                ),
                "strategy_id": strategy_id,
            }
        )
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
    identities: Mapping[QualifiedIdentityKey, QualifiedLineageIdentity],
    production_identities: Mapping[str, LineageIdentity],
) -> list[dict[str, Any]]:
    switching_active = [row for row in experiments if cast(bool, row.get("switching_active"))]
    sign_labels = ("POSITIVE", "NEGATIVE", "ZERO")
    distinct_classes = {"DISTINCT_BINDING_DIVERSITY", "MIXED_DIVERSITY"}
    sibling_only_class = "PARAMETER_SIBLING_DIVERSITY_ONLY"

    repeated: list[dict[str, Any]] = []
    for cell_id in REPEATED_POSITIVE_CELL_IDS:
        cell_rows = sorted(
            (row for row in experiments if row.get("cell_id") == cell_id),
            key=lambda row: cast(int, row["window"]),
        )
        positive_rows = [row for row in cell_rows if row["historical_sign"] == "POSITIVE"]
        repeated.append(
            {
                "any_positive_window_uses_actual_distinct_binding_diversity": any(
                    row["diversity_class"] in distinct_classes for row in positive_rows
                ),
                "cell_id": cell_id,
                "positive_window_count": len(positive_rows),
                "positive_windows_all_use_actual_distinct_binding_diversity": all(
                    row["diversity_class"] in distinct_classes for row in positive_rows
                ),
                "windows": [
                    {
                        "actual_distinct_binding_diversity_selected": row[
                            "actual_distinct_binding_diversity_selected"
                        ],
                        "diversity_class": row["diversity_class"],
                        "historical_sign": row["historical_sign"],
                        "switch_count": row["switch_count"],
                        "unique_binding_fingerprint_count": row[
                            "unique_binding_fingerprint_count"
                        ],
                        "unique_callable_identity_count": row[
                            "unique_callable_identity_count"
                        ],
                        "window": row["window"],
                        "window_label": row["window_label"],
                    }
                    for row in cell_rows
                ],
            }
        )

    positive = [
        row
        for row in experiments
        if row.get("available") and row.get("historical_sign") == "POSITIVE"
    ]
    positive_counts = Counter(cast(str, row["diversity_class"]) for row in positive)
    positive_total = len(positive)
    largest_positive_count = max(positive_counts.values(), default=0)
    largest_positive_classes = sorted(
        diversity_class
        for diversity_class in DIVERSITY_CLASSES
        if positive_counts.get(diversity_class, 0) == largest_positive_count
        and largest_positive_count > 0
    )

    reversals: list[dict[str, Any]] = []
    for cell_id in sorted({cast(str, row["cell_id"]) for row in experiments}):
        signed_rows = [
            row
            for row in experiments
            if row["cell_id"] == cell_id
            and row["available"]
            and row["historical_sign"] in {"POSITIVE", "NEGATIVE"}
        ]
        signs = {cast(str, row["historical_sign"]) for row in signed_rows}
        if signs != {"POSITIVE", "NEGATIVE"}:
            continue
        classes = {cast(str, row["diversity_class"]) for row in signed_rows}
        distinct_presence = {
            cast(bool, row["actual_distinct_binding_diversity_selected"])
            for row in signed_rows
        }
        reversals.append(
            {
                "cell_id": cell_id,
                "same_actual_distinct_binding_presence": len(distinct_presence) == 1,
                "same_exact_structural_diversity_class": len(classes) == 1,
                "structural_diversity_classes": sorted(classes),
                "windows": [
                    {
                        "diversity_class": row["diversity_class"],
                        "historical_sign": row["historical_sign"],
                        "window": row["window"],
                        "window_label": row["window_label"],
                    }
                    for row in sorted(signed_rows, key=lambda row: cast(int, row["window"]))
                ],
            }
        )

    return [
        {
            "answer": {
                "actual_distinct_binding_diversity_historical_sign_counts": {
                    sign: sum(
                        row["historical_sign"] == sign
                        and row["diversity_class"] in distinct_classes
                        for row in switching_active
                    )
                    for sign in sign_labels
                },
                "by_diversity_class_and_historical_sign": _count_matrix(switching_active),
                "parameter_sibling_diversity_only_historical_sign_counts": {
                    sign: sum(
                        row["historical_sign"] == sign
                        and row["diversity_class"] == sibling_only_class
                        for row in switching_active
                    )
                    for sign in sign_labels
                },
                "switching_active_experiment_count": len(switching_active),
            },
            "question": (
                "Among switching-active experiments, what are POSITIVE / NEGATIVE / ZERO "
                "counts after separating distinct-binding diversity from sibling-only diversity?"
            ),
            "question_id": 1,
        },
        {
            "answer": {"cells": repeated},
            "question": (
                "Do the five repeated-positive cells use actual distinct-binding diversity?"
            ),
            "question_id": 2,
        },
        {
            "answer": _p638_bridge_answer(
                selector_cells, experiments, production_identities
            ),
            "question": (
                "How much of P638 selection remains inside the C01-C07 bridge callable family?"
            ),
            "question_id": 3,
        },
        {
            "answer": {
                "positive_counts_by_diversity_class": {
                    diversity_class: positive_counts.get(diversity_class, 0)
                    for diversity_class in DIVERSITY_CLASSES
                },
                "positive_share_by_diversity_class": {
                    diversity_class: _ratio_payload(
                        positive_counts.get(diversity_class, 0), positive_total
                    )
                    for diversity_class in DIVERSITY_CLASSES
                },
                "largest_positive_count": largest_positive_count,
                "largest_positive_diversity_classes": largest_positive_classes,
                "positive_experiment_count": positive_total,
            },
            "question": "Are historical positive deltas concentrated in a structural class?",
            "question_id": 4,
        },
        {
            "answer": {
                "cells": reversals,
                "same_actual_distinct_binding_presence_cell_ids": [
                    row["cell_id"]
                    for row in reversals
                    if row["same_actual_distinct_binding_presence"]
                ],
                "same_exact_structural_diversity_class_cell_ids": [
                    row["cell_id"]
                    for row in reversals
                    if row["same_exact_structural_diversity_class"]
                ],
            },
            "question": (
                "Which cells reverse sign across windows despite similar structural-diversity "
                "class?"
            ),
            "question_id": 5,
        },
        {
            "answer": _wave26_answer(
                selector_cells, experiments, identities, production_identities
            ),
            "question": (
                "Do CES / DMS / Greedy / MWSC appear, and what structural identities "
                "do they contribute?"
            ),
            "question_id": 6,
        },
    ]


def build_attribution(
    selector: Mapping[str, Any],
    decomposition: Mapping[str, Any],
    base_lineage: Mapping[str, Any],
    wave26_supplement: Mapping[str, Any],
    selector_universe_lineage: Mapping[str, Any],
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
    production_identities, production_summary = merge_lineage_authorities(
        base_lineage,
        wave26_supplement,
        enforce_sealed_shape=enforce_sealed_shape,
    )
    identities, lineage_merge = merge_authority_qualified_lineage(
        selector_universe_lineage,
        base_lineage,
        wave26_supplement,
        production_identities,
        production_summary,
        enforce_sealed_shape=enforce_sealed_shape,
    )
    decomposition_by_experiment = _decomposition_index(
        decomposition, enforce_sealed_shape=enforce_sealed_shape
    )

    raw_source_authorities = _as_list(
        selector.get("source_authorities"), context="selector.source_authorities"
    )
    source_authority_by_lottery: dict[str, str] = {}
    for index, raw_authority in enumerate(raw_source_authorities):
        authority = _as_mapping(raw_authority, context=f"selector.source_authorities[{index}]")
        lottery_id = _as_string(
            authority.get("lottery_id"), context=f"selector.source_authorities[{index}].lottery_id"
        )
        authority_id = _as_string(
            authority.get("authority_id"),
            context=f"selector.source_authorities[{index}].authority_id",
        )
        if lottery_id in source_authority_by_lottery:
            raise AttributionDataError(f"duplicate selector source authority for {lottery_id}")
        source_authority_by_lottery[lottery_id] = authority_id

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
    candidate_universe: set[QualifiedIdentityKey] = set()
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
        source_authority_id = _as_string(
            cell.get("source_authority_id"), context=f"{cell_id}.source_authority_id"
        )
        if source_authority_by_lottery.get(lottery_id) != source_authority_id:
            raise AttributionDataError(
                f"{cell_id} source authority differs from selector authority"
            )
        raw_candidates = _as_list(
            cell.get("candidate_strategies"), context=f"{cell_id}.candidate_strategies"
        )
        candidate_identity_keys: dict[str, QualifiedIdentityKey] = {}
        for candidate_index, raw_candidate in enumerate(raw_candidates):
            candidate = _as_mapping(
                raw_candidate, context=f"{cell_id}.candidate_strategies[{candidate_index}]"
            )
            strategy_id = _as_string(
                candidate.get("strategy_id"),
                context=f"{cell_id}.candidate_strategies[{candidate_index}].strategy_id",
            )
            strategy_version = _as_string(
                candidate.get("strategy_version"),
                context=f"{cell_id}.candidate_strategies[{candidate_index}].strategy_version",
            )
            if strategy_id in candidate_identity_keys:
                raise AttributionDataError(
                    f"{cell_id} contains duplicate candidate ID {strategy_id}"
                )
            candidate_identity_keys[strategy_id] = (
                source_authority_id,
                lottery_id,
                strategy_id,
                strategy_version,
            )
        candidate_universe.update(candidate_identity_keys.values())
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
                    candidate_identity_keys=candidate_identity_keys,
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
        _qualified_key(
            identity["authority_qualified_identity_key"],
            context="experiment.selected_authority_qualified_identity",
        )
        for experiment in experiments
        for identity in cast(
            list[dict[str, Any]], experiment["selected_authority_qualified_identities"]
        )
    }
    selected_raw_labels = {key[2] for key in selected_universe}
    frozen_universe = {
        cast(str, experiment["frozen_baseline_strategy_id"])
        for experiment in experiments
        if experiment["frozen_baseline_strategy_id"] is not None
    }
    candidate_only_keys = sorted(candidate_universe - set(identities))
    missing_selected_keys = sorted(selected_universe - set(identities))
    if missing_selected_keys:
        raise AttributionDataError(
            "SELECTED_QUALIFIED_IDENTITIES_UNRESOLVED: "
            f"{[list(key) for key in missing_selected_keys]}"
        )
    if enforce_sealed_shape and (
        len(selected_universe) != EXPECTED_QUALIFIED_SELECTOR_IDENTITY_COUNT
        or len(selected_raw_labels) != EXPECTED_RAW_SELECTOR_LABEL_COUNT
        or selected_universe != set(identities)
    ):
        raise AttributionDataError(
            "SELECTOR_SELECTED_QUALIFIED_IDENTITY_CENSUS_MISMATCH: "
            f"qualified={len(selected_universe)} raw={len(selected_raw_labels)}"
        )

    expected_selected_records = _unique_qualified_records(
        selector_universe_lineage.get("qualified_selector_identities"),
        context="selector_universe_lineage.qualified_selector_identities",
    )
    observed_cells_by_key: defaultdict[QualifiedIdentityKey, set[str]] = defaultdict(set)
    for experiment in experiments:
        for identity in cast(
            list[dict[str, Any]], experiment["selected_authority_qualified_identities"]
        ):
            key = _qualified_key(
                identity["authority_qualified_identity_key"],
                context="experiment.selected_authority_qualified_identity",
            )
            observed_cells_by_key[key].add(cast(str, experiment["cell_id"]))
    cell_coverage_conflicts: list[dict[str, Any]] = []
    for key, record in expected_selected_records.items():
        expected_cells = sorted(
            _as_string(cell, context=f"{key}.selector_cells")
            for cell in _as_list(record.get("selector_cells"), context=f"{key}.selector_cells")
        )
        observed_cells = sorted(observed_cells_by_key[key])
        if observed_cells != expected_cells:
            cell_coverage_conflicts.append(
                {
                    "authority_qualified_identity_key": list(key),
                    "expected_selector_cells": expected_cells,
                    "observed_selector_cells": observed_cells,
                }
            )
    if cell_coverage_conflicts:
        raise AttributionDataError(
            f"SELECTOR_QUALIFIED_IDENTITY_CELL_COVERAGE_MISMATCH: {cell_coverage_conflicts}"
        )

    available = [row for row in experiments if cast(bool, row["available"])]
    switching_active = [row for row in available if cast(bool, row["switching_active"])]
    inconsistent_available = [
        row for row in available if row["diversity_class"] == "LINEAGE_SOURCE_INCONSISTENT"
    ]
    if inconsistent_available:
        raise AttributionDataError(
            "LINEAGE_SOURCE_INCONSISTENT_AVAILABLE_EXPERIMENTS: "
            f"{[row['cell_id'] + ':' + row['window_label'] for row in inconsistent_available]}"
        )

    required_answers = _required_answers(
        selector_cells=raw_cells,
        experiments=experiments,
        identities=identities,
        production_identities=production_identities,
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
            "ordered_transition_attribution": "NOT_AVAILABLE",
            "p638_zone2": "NOT_RUN",
            "predictive_advantage": "NOT_ESTABLISHED",
            "profitability": "NOT_ESTABLISHED",
            "selector_rerun": "NOT_RUN",
            "semantic_equivalence": "NOT_CLAIMED",
            "significance_testing": "NOT_RUN",
            "strategy_execution": "NOT_RUN",
            "transition_order": ("NOT_AVAILABLE; SOURCE_CONTAINS_FREQUENCIES_AND_TRACE_HASH_ONLY"),
        },
        "definitions": {
            "DISTINCT_BINDING_DIVERSITY": (
                "More than one frozen callable identity is selected and no selected "
                "pair shares one callable identity with different bindings."
            ),
            "LINEAGE_SOURCE_INCONSISTENT": (
                "At least one selected authority-qualified identity is absent from the "
                "combined frozen lineage, has the wrong lottery identity, or source switch "
                "metadata cannot be reconciled with selected identities."
            ),
            "MIXED_DIVERSITY": (
                "The selected set contains both a same-callable/different-binding pair "
                "and more than one frozen callable identity."
            ),
            "NO_SWITCH": (
                "The available source switch count is zero or all selected qualified "
                "identities collapse to one frozen binding identity; raw switch count remains "
                "reported separately."
            ),
            "INCONCLUSIVE": (
                "The sealed selector experiment is unavailable and contains no eligible "
                "selection targets or switch activity."
            ),
            "PARAMETER_SIBLING_DIVERSITY_ONLY": (
                "More than one binding is selected, every resolved selection remains in "
                "one frozen callable family, and a same-callable/different-binding pair "
                "is present."
            ),
            "actual_distinct_binding_diversity_boolean": (
                "actual_distinct_binding_diversity_selected is true exactly when more than "
                "one frozen callable identity is selected."
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
            "candidate_authority_qualified_identity_count": len(candidate_universe),
            "candidate_identities_outside_selected_lineage": [
                list(key) for key in candidate_only_keys
            ],
            "candidate_identities_outside_selected_lineage_count": len(candidate_only_keys),
            "duplicate_selector_cell_id_count": 0,
            "donor_identity_alias_count": lineage_merge["donor_identity_alias_count"],
            "experiment_count": len(experiments),
            "frozen_baseline_strategy_id_count": len(frozen_universe),
            "lineage_attribution_complete_available_experiment_count": sum(
                cast(bool, row["lineage_attribution_complete"]) for row in available
            ),
            "lineage_source_inconsistent_available_experiment_count": sum(
                row["diversity_class"] == "LINEAGE_SOURCE_INCONSISTENT" for row in available
            ),
            "null_or_unavailable_experiment_count": sum(
                not cast(bool, row["available"]) for row in experiments
            ),
            "qualified_selected_identity_count": len(selected_universe),
            "raw_selected_strategy_label_count": len(selected_raw_labels),
            "sealed_outcome_preservation_experiment_count": len(experiments),
            "selected_qualified_identities_absent_from_combined_lineage": [],
            "selected_qualified_identities_absent_from_combined_lineage_count": 0,
            "unexpected_window_count": 0,
        },
        "source_identities": dict(source_identities or {}),
        "study_id": STUDY_ID,
        "task_id": TASK_ID,
    }


def _format_count(count: object) -> str:
    return "—" if count is None else str(count)


def _render_r1_legacy_report(  # pyright: ignore[reportUnusedFunction]
    payload: Mapping[str, Any],
) -> str:
    """Retain the R1 rendering shape as an unused comparison aid."""

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


def _report_exact_delta(value: object) -> str:
    if value is None:
        return "—"
    mapping = _as_mapping(value, context="report exact delta")
    return _as_string(mapping.get("exact"), context="report exact delta.exact")


def _report_code_items(items: Sequence[str]) -> str:
    return "—" if not items else "<br>".join(f"`{item}`" for item in items)


def render_report(payload: Mapping[str, Any]) -> str:
    """Render the deterministic R2 authority-qualified attribution report."""

    lineage = _as_mapping(payload["lineage_merge"], context="lineage_merge")
    quality = _as_mapping(payload["source_data_quality"], context="source_data_quality")
    aggregates = _as_mapping(payload["aggregates"], context="aggregates")
    source_identities = _as_mapping(payload["source_identities"], context="source_identities")
    experiments = cast(list[dict[str, Any]], payload["experiments"])
    answers = {
        cast(int, row["question_id"]): _as_mapping(
            row["answer"], context=f"question {row['question_id']}"
        )
        for row in cast(list[dict[str, Any]], payload["required_answers"])
    }
    base_lineage = _as_mapping(
        lineage["base_production_lineage"], context="base_production_lineage"
    )

    lines = [
        "# Selector lineage diversity attribution R2",
        "",
        "## Outcome",
        "",
        (
            f"All {lineage['qualified_selector_identity_count']} authority-qualified "
            f"selector identities ({lineage['raw_selector_label_count']} raw labels) are "
            f"structurally accounted for as {lineage['production_exact_join_count']} exact "
            f"production joins plus {lineage['selector_supplement_row_count']} selector-"
            "supplement rows."
        ),
        (
            f"All {quality['lineage_attribution_complete_available_experiment_count']} of "
            f"{aggregates['available_experiment_count']} available experiments receive a "
            "complete structural-diversity attribution."
        ),
        "",
        "    LINEAGE_SOURCE_INCONSISTENT_AVAILABLE_EXPERIMENTS = 0",
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
            "## Authority-qualified lineage accounting",
            "",
            f"- Production static rows: {base_lineage['base_record_count']}",
            f"- Production static resolved rows: {base_lineage['base_resolved_record_count']}",
            (
                "- Wave26-resolved production rows: "
                f"{base_lineage['supplemental_record_count']}"
            ),
            f"- Qualified selector identities: {lineage['qualified_selector_identity_count']}",
            f"- Raw selector labels: {lineage['raw_selector_label_count']}",
            f"- Production exact joins: {lineage['production_exact_join_count']}",
            f"- Selector supplement rows: {lineage['selector_supplement_row_count']}",
            f"- Total structurally accounted: {lineage['total_structurally_accounted']}",
            f"- Donor identity aliases: {lineage['donor_identity_alias_count']}",
            "",
            "The raw label `midfreq_fourier_2bet` remains two distinct identities:",
            "",
        ]
    )
    for key in cast(
        list[list[str]], lineage["cross_lottery_raw_label_collision_identity_keys"]
    ):
        lines.append(f"- `{('/'.join(key))}`")

    def append_matrix(title: str, aggregate_key: str) -> None:
        lines.extend(
            [
                "",
                f"## {title}",
                "",
                "| Diversity class | POSITIVE | ZERO | NEGATIVE | INCONCLUSIVE | Total |",
                "|---|---:|---:|---:|---:|---:|",
            ]
        )
        matrix = _as_mapping(aggregates[aggregate_key], context=aggregate_key)
        for diversity_class in DIVERSITY_CLASSES:
            counts = _as_mapping(matrix[diversity_class], context=diversity_class)
            total = sum(
                _as_nonnegative_int(counts[sign], context=f"{diversity_class}.{sign}")
                for sign in HISTORICAL_SIGNS
            )
            lines.append(
                f"| {diversity_class} | {counts['POSITIVE']} | {counts['ZERO']} | "
                f"{counts['NEGATIVE']} | {counts['INCONCLUSIVE']} | {total} |"
            )

    append_matrix(
        "All experiments by structural-diversity class and original sign",
        "all_experiments_by_diversity_class_and_historical_sign",
    )
    append_matrix(
        "Switching-active experiments by structural-diversity class and original sign",
        "switching_active_experiments_by_diversity_class_and_historical_sign",
    )

    lines.extend(
        [
            "",
            "## Per-experiment attribution",
            "",
            (
                "| Lottery | K | Window | Original sign / exact delta | Eligible targets / "
                "switches | Frozen baseline | Selected Strategy IDs/frequencies | Qualified "
                "identities | Binding fingerprints | Callable identities | Parameter-sibling "
                "families | Class |"
            ),
            "|---|---:|---|---|---|---|---|---|---|---|---|---|",
        ]
    )
    for row in experiments:
        raw_frequencies = [
            f"{item['strategy_id']}={item['selection_count']}"
            for item in cast(list[dict[str, Any]], row["selection_frequency_by_strategy_id"])
        ]
        qualified_keys = [
            "/".join(
                _qualified_key(
                    item["authority_qualified_identity_key"],
                    context="report qualified identity",
                )
            )
            for item in cast(
                list[dict[str, Any]], row["selected_authority_qualified_identities"]
            )
        ]
        raw_binding_fingerprints = row["unique_binding_fingerprints"]
        binding_fingerprints = (
            []
            if raw_binding_fingerprints is None
            else cast(list[str], raw_binding_fingerprints)
        )
        raw_callable_identities = row["unique_callable_identities"]
        callable_identities = (
            []
            if raw_callable_identities is None
            else cast(list[str], raw_callable_identities)
        )
        sibling_families = [
            cast(str, family["callable_identity"])
            for family in cast(
                list[dict[str, Any]], row["parameter_sibling_families_involved"]
            )
        ]
        baseline = "—" if row["frozen_baseline_strategy_id"] is None else str(
            row["frozen_baseline_strategy_id"]
        )
        lines.append(
            f"| {row['lottery_id']} | {row['k']} | {row['window_label']} | "
            f"{row['original_sign']} / {_report_exact_delta(row['original_exact_delta'])} | "
            f"{row['original_eligible_target_count']} / {row['original_switch_count']} | "
            f"`{baseline}` | {_report_code_items(raw_frequencies)} | "
            f"{_report_code_items(qualified_keys)} | "
            f"{_report_code_items(binding_fingerprints)} | "
            f"{_report_code_items(callable_identities)} | "
            f"{_report_code_items(sibling_families)} | {row['diversity_class']} |"
        )

    q1 = answers[1]
    q1_distinct = _as_mapping(
        q1["actual_distinct_binding_diversity_historical_sign_counts"],
        context="question 1 distinct",
    )
    q1_sibling = _as_mapping(
        q1["parameter_sibling_diversity_only_historical_sign_counts"],
        context="question 1 sibling",
    )
    lines.extend(
        [
            "",
            "## Required descriptive findings",
            "",
            "### 1. Switching-active sign counts",
            "",
            "| Structural grouping | POSITIVE | NEGATIVE | ZERO |",
            "|---|---:|---:|---:|",
            (
                "| Actual distinct-binding diversity | "
                f"{q1_distinct['POSITIVE']} | {q1_distinct['NEGATIVE']} | "
                f"{q1_distinct['ZERO']} |"
            ),
            (
                "| Parameter-sibling diversity only | "
                f"{q1_sibling['POSITIVE']} | {q1_sibling['NEGATIVE']} | "
                f"{q1_sibling['ZERO']} |"
            ),
            "",
            "### 2. Five repeated-positive cells",
            "",
            (
                "| Cell | Positive windows | All positive windows use actual distinct "
                "binding? | Window classes |"
            ),
            "|---|---:|---|---|",
        ]
    )
    for cell in cast(list[dict[str, Any]], answers[2]["cells"]):
        window_classes = [
            f"{window['window_label']}:{window['historical_sign']}:"
            f"{window['diversity_class']}"
            for window in cast(list[dict[str, Any]], cell["windows"])
        ]
        lines.append(
            f"| {cell['cell_id']} | {cell['positive_window_count']} | "
            f"{cell['positive_windows_all_use_actual_distinct_binding_diversity']} | "
            f"{_report_code_items(window_classes)} |"
        )

    q3 = answers[3]
    overall_share = _as_mapping(
        q3["overall_p638_selection_share"], context="P638 overall share"
    )
    k1_share = _as_mapping(q3["p638_k1_selection_share"], context="P638 K1 share")
    lines.extend(
        [
            "",
            "### 3. P638 C01-C07 bridge callable family",
            "",
            (
                "Across all available P638 experiments, "
                f"{q3['overall_p638_bridge_selection_count']} "
                f"of {q3['overall_p638_selection_count']} selections are inside C01-C07 "
                f"(exact share {overall_share['exact']}, decimal {overall_share['decimal_6']})."
            ),
            (
                f"Within P638 K1, {q3['p638_k1_bridge_selection_count']} of "
                f"{q3['p638_k1_selection_count']} selections are inside the family "
                f"(exact share {k1_share['exact']}, decimal {k1_share['decimal_6']})."
            ),
            "Exact transition-level family switch counts remain unavailable.",
            "",
            "### 4. Positive-delta concentration",
            "",
            "| Diversity class | Positive count | Exact share |",
            "|---|---:|---:|",
        ]
    )
    q4 = answers[4]
    q4_counts = _as_mapping(
        q4["positive_counts_by_diversity_class"], context="positive counts"
    )
    q4_shares = _as_mapping(
        q4["positive_share_by_diversity_class"], context="positive shares"
    )
    for diversity_class in DIVERSITY_CLASSES:
        share = _as_mapping(q4_shares[diversity_class], context=diversity_class)
        lines.append(
            f"| {diversity_class} | {q4_counts[diversity_class]} | {share['exact']} |"
        )
    lines.extend(
        [
            "",
            (
                "Largest observed positive class(es): "
                f"{', '.join(cast(list[str], q4['largest_positive_diversity_classes']))} "
                f"with {q4['largest_positive_count']} of {q4['positive_experiment_count']} "
                "positive experiments. This is descriptive, not a significance result."
            ),
            "",
            "### 5. Sign reversals across windows",
            "",
            (
                "| Cell | Window signs/classes | Same exact class? | Same actual-distinct "
                "presence? |"
            ),
            "|---|---|---|---|",
        ]
    )
    for cell in cast(list[dict[str, Any]], answers[5]["cells"]):
        windows = [
            f"{row['window_label']}:{row['historical_sign']}:{row['diversity_class']}"
            for row in cast(list[dict[str, Any]], cell["windows"])
        ]
        lines.append(
            f"| {cell['cell_id']} | {_report_code_items(windows)} | "
            f"{cell['same_exact_structural_diversity_class']} | "
            f"{cell['same_actual_distinct_binding_presence']} |"
        )

    lines.extend(
        [
            "",
            "### 6. CES / DMS / Greedy / MWSC",
            "",
            (
                "| Strategy ID | In candidate universe | Selected | Contributes qualified "
                "identity | Structural binding | Structural callable |"
            ),
            "|---|---|---|---|---|---|",
        ]
    )
    for row in cast(list[dict[str, Any]], answers[6]["strategies"]):
        lines.append(
            f"| `{row['strategy_id']}` | {row['in_selector_universe']} | "
            f"{row['selected']} | {row['contributes_to_selected_qualified_lineage']} | "
            f"`{row['binding_identity']}` | `{row['callable_identity']}` |"
        )

    lines.extend(
        [
            "",
            "## Scientific and runtime boundary",
            "",
            (
                "Classes describe selected identity sets and frequencies. A trace hash does "
                "not expose ordered transition endpoints, so exact transition-level lineage "
                "counts are not inferred."
            ),
            "",
            "    SELECTOR_RERUN = NOT RUN",
            "    HISTORICAL_REPLAY = NOT RUN",
            "    STRATEGY_EXECUTION = NOT RUN",
            "    DB_ACCESS = NO",
            "    DB_WRITE = NO",
            "    ORDERED_TRANSITION_ATTRIBUTION = NOT AVAILABLE",
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
        artifacts["selector_universe_lineage"].payload,
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
