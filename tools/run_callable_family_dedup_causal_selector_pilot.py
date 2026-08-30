"""Run the fixed callable-family-dedup causal selector pilot.

The pilot reuses the original selector implementation and its sealed per-target
evaluation authorities.  Candidate families are reduced statically inside each
frozen lottery/ticket-count cell before the original selector tie-break runs.
No prediction strategy is executed and every SQLite authority is opened by the
sealed runner in immutable read-only mode.

This is exploratory historical research.  It does not establish predictive
advantage, profitability, statistical significance, or promotion readiness.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import types
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from decimal import Decimal, localcontext
from fractions import Fraction
from pathlib import Path
from typing import Any, cast

TASK_ID = "CALLABLE_FAMILY_DEDUP_CAUSAL_SELECTOR_PILOT_R1"
STUDY_ID = "CALLABLE_FAMILY_DEDUP_CAUSAL_SELECTOR_PILOT_V1"
SCHEMA_VERSION = "CALLABLE_FAMILY_DEDUP_CAUSAL_SELECTOR_PILOT_RESULT_V1"
PRIMARY_METRIC_ID = "OFFICIAL_ANY_PRIZE_TARGET_RATE"

EXPECTED_BASE_HEAD = "07a5c3479123c03fd91b6f1ae2402046b5f16c2a"
EXPECTED_BASE_TREE = "cff549183e67ad49f12afb5076a11b1f8b712dde"
ORIGINAL_SELECTOR_SOURCE_HEAD = "0645f31a2bcaf494760d4bc1675bc1c3ed9a076d"
ORIGINAL_SELECTOR_SOURCE_TREE = "8b9fa40728f1bea3fb585d86f426a36489e0debf"

WINDOWS: tuple[tuple[str, str, int], ...] = (
    ("W50", "SHORT", 50),
    ("W300", "MEDIUM", 300),
    ("W750", "LONG", 750),
)
REPEATED_POSITIVE_CELL_IDS = (
    "P638:K2",
    "P638:K3",
    "T539:K1",
    "T539:K2",
    "T539:K3",
)
P638_C01_C07_STRATEGY_IDS = (
    "power_c01_recency_decay_1bet",
    "power_c02_gap_overdue_1bet",
    "power_c03_pair_centrality_1bet",
    "power_c04_zone_balanced_1bet",
    "power_c05_dispersion_match_1bet",
    "power_c06_regime_cusum_1bet",
    "power_c07_borda_ensemble_1bet",
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_AUTHORITY_ROOT = Path.home() / "Library" / "Application Support" / "LottoLab"
DEFAULT_B649_AUTHORITY_DIRECTORY = (
    DEFAULT_AUTHORITY_ROOT / "authorities" / "big_lotto" / "exact_native_k2_k3"
)
DEFAULT_T539_AUTHORITY = DEFAULT_AUTHORITY_ROOT / "authorities" / "daily_539" / "historical.sqlite3"
DEFAULT_P638_REPLAY_AUTHORITY = (
    DEFAULT_AUTHORITY_ROOT / "authorities" / "power_lotto" / "current_replay.sqlite3"
)
DEFAULT_P638_RANKING_AUTHORITY = (
    DEFAULT_AUTHORITY_ROOT / "authorities" / "power_lotto" / "current_ranking.sqlite3"
)
DEFAULT_OUTPUT_JSON = (
    REPOSITORY_ROOT / "docs/research/matrix-native-results/"
    "callable-family-dedup-causal-selector-pilot-r1-result.json"
)
DEFAULT_OUTPUT_REPORT = (
    REPOSITORY_ROOT / "docs/research/callable-family-dedup-causal-selector-pilot-r1.md"
)

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")

QualifiedIdentityKey = tuple[str, str, str, str]
CallableFamilyKey = tuple[str, str, int, str]


class PilotDataError(ValueError):
    """A frozen authority cannot support the preregistered comparison."""


@dataclass(frozen=True, slots=True)
class ArtifactSpec:
    """Exact identity for one safe regular blob in Git object storage."""

    key: str
    commit: str
    tree: str
    relative_path: str
    sha256: str
    payload_kind: str


@dataclass(frozen=True, slots=True)
class LoadedArtifact:
    """Verified bytes and metadata for one frozen Git artifact."""

    spec: ArtifactSpec
    blob_oid: str
    data: bytes

    def identity_payload(self) -> dict[str, Any]:
        return {
            "blob_oid": self.blob_oid,
            "commit": self.spec.commit,
            "path": self.spec.relative_path,
            "sha256": self.spec.sha256,
            "size_bytes": len(self.data),
            "tree": self.spec.tree,
        }

    def json_payload(self) -> dict[str, Any]:
        if self.spec.payload_kind != "json":
            raise PilotDataError(f"{self.spec.key} is not a JSON authority")
        try:
            decoded = json.loads(self.data)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise PilotDataError(f"{self.spec.key} is not valid UTF-8 JSON") from exc
        if not isinstance(decoded, dict):
            raise PilotDataError(f"{self.spec.key} top-level JSON must be an object")
        return cast(dict[str, Any], decoded)


@dataclass(frozen=True, slots=True)
class CandidateBinding:
    """One candidate identity bound to one authority-qualified callable."""

    source_authority_id: str
    lottery_id: str
    native_ticket_count: int
    strategy_id: str
    strategy_version: str
    callable_identity: str
    callable_label: str
    resolution_authority: str

    @property
    def identity_key(self) -> QualifiedIdentityKey:
        return (
            self.source_authority_id,
            self.lottery_id,
            self.strategy_id,
            self.strategy_version,
        )

    @property
    def family_key(self) -> CallableFamilyKey:
        return (
            self.source_authority_id,
            self.lottery_id,
            self.native_ticket_count,
            self.callable_identity,
        )


@dataclass(frozen=True, slots=True)
class CallableFamily:
    """A cell-scoped callable family and its fixed static representative."""

    family_key: CallableFamilyKey
    members: tuple[CandidateBinding, ...]
    representative: CandidateBinding

    def as_payload(self) -> dict[str, Any]:
        member_keys = [list(member.identity_key) for member in self.members]
        return {
            "authority_qualified_callable_identity": [
                self.family_key[0],
                self.family_key[1],
                self.family_key[2],
                self.family_key[3],
            ],
            "callable_identity": self.family_key[3],
            "callable_labels": sorted({member.callable_label for member in self.members}),
            "member_count": len(self.members),
            "member_identities": member_keys,
            "removed_sibling_count": len(self.members) - 1,
            "removed_sibling_identities": [
                list(member.identity_key)
                for member in self.members
                if member.identity_key != self.representative.identity_key
            ],
            "representative_identity": list(self.representative.identity_key),
            "representative_rule": ("LEXICOGRAPHIC_MINIMUM_COMPLETE_AUTHORITY_QUALIFIED_IDENTITY"),
            "resolution_authorities": sorted(
                {member.resolution_authority for member in self.members}
            ),
        }


ROLLING_SELECTOR_ARTIFACT = ArtifactSpec(
    key="rolling_selector",
    commit="abc367bd6d8b59d01ecc4d79e56c787bbc03cd20",
    tree="bf430efd66b7ce1ac38ee04fb0052e8c55cc972c",
    relative_path=(
        "docs/research/matrix-native-results/"
        "strategy-matrix-causal-rolling-selector-pilot-r1-result.json"
    ),
    sha256="04df0bfdffcf4ecc05d4f2ac3f58cfa1fa301061c5f1c30e549ddc3b5b174157",
    payload_kind="json",
)
ROLLING_DECOMPOSITION_ARTIFACT = ArtifactSpec(
    key="rolling_decomposition",
    commit="cc9bd1088a9f871618725d0910874283e0318459",
    tree="7d05638845dc553fa20d793ceba8ce1aceff71ee",
    relative_path=(
        "docs/research/matrix-native-results/"
        "rolling-selector-stability-decomposition-r1-result.json"
    ),
    sha256="92ffb4d5678d403322791de1e3cb133d3bdb91c9c911142f67f4f3f4ee8979c9",
    payload_kind="json",
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
    payload_kind="json",
)
WAVE26_ARTIFACT = ArtifactSpec(
    key="wave26_supplement",
    commit="139b3aae0ec52ef947796ee7db68cd38a9bf9f5c",
    tree="8467da3725fb323d21fc647b7d6d02ea953a68a6",
    relative_path=(
        "docs/research/matrix-native-results/wave26-dynamic-binding-resolution-r1-result.json"
    ),
    sha256="193b9301640e5561cb495903ce0d6710c47886b72b5f603542505a82f9218db3",
    payload_kind="json",
)
SELECTOR_UNIVERSE_LINEAGE_ARTIFACT = ArtifactSpec(
    key="selector_universe_lineage",
    commit="39592593126325533d664b57097be280682fe2ab",
    tree="9abc5d50ed9ecbe3dbab4a7e1a6c4bf7fe8a2ee3",
    relative_path=(
        "docs/research/matrix-native-results/selector-universe-lineage-supplement-r1-result.json"
    ),
    sha256="461afd3bd0b7eeca93546562330d03234ad57aa2aa4dff25d4432cc254795f37",
    payload_kind="json",
)
R2_ATTRIBUTION_ARTIFACT = ArtifactSpec(
    key="r2_attribution",
    commit="a264defca63ab64a7f6022f60e2637993c7bdeec",
    tree="7b6e193fa0fa0656fe8e44a48cbfe948bf450349",
    relative_path=(
        "docs/research/matrix-native-results/selector-lineage-diversity-attribution-r2-result.json"
    ),
    sha256="7356bc11a0d7234663b5d2003042410618c2c1064972de5b234438b142e35aa5",
    payload_kind="json",
)
ORIGINAL_SELECTOR_RUNNER_ARTIFACT = ArtifactSpec(
    key="original_selector_runner",
    commit="abc367bd6d8b59d01ecc4d79e56c787bbc03cd20",
    tree="bf430efd66b7ce1ac38ee04fb0052e8c55cc972c",
    relative_path="tools/run_strategy_matrix_causal_rolling_selector_pilot.py",
    sha256="63a90f5eae921ad3553a7a761c47da88a76a30b43cea309eb7d38149ade19b18",
    payload_kind="python",
)

JSON_ARTIFACT_SPECS = (
    ROLLING_SELECTOR_ARTIFACT,
    ROLLING_DECOMPOSITION_ARTIFACT,
    BASE_LINEAGE_ARTIFACT,
    WAVE26_ARTIFACT,
    SELECTOR_UNIVERSE_LINEAGE_ARTIFACT,
    R2_ATTRIBUTION_ARTIFACT,
)


def _source_spec(key: str, relative_path: str, sha256: str) -> ArtifactSpec:
    return ArtifactSpec(
        key=key,
        commit=ORIGINAL_SELECTOR_SOURCE_HEAD,
        tree=ORIGINAL_SELECTOR_SOURCE_TREE,
        relative_path=relative_path,
        sha256=sha256,
        payload_kind="python",
    )


STATIC_SOURCE_SPECS = (
    _source_spec(
        "powerlotto_wave3_source",
        "src/lottolab/strategies/adapters/powerlotto_wave3.py",
        "4c9a57105d70ed1f5bae1c425ea0d2798f646f86dada5eb9c9fca31fcdfd3a4c",
    ),
    _source_spec(
        "powerlotto_wave4_source",
        "src/lottolab/strategies/adapters/powerlotto_wave4.py",
        "000b776bd296f85b941bf0515a4b60b5bc2c5761a283f06fc458c94f0e9cb5aa",
    ),
    _source_spec(
        "powerlotto_wave5_source",
        "src/lottolab/strategies/adapters/powerlotto_wave5.py",
        "bf108af8354f5b60af7c66afdb6ad7ea2037a1ac8a3de396af6b203b7ee81573",
    ),
    _source_spec(
        "daily539_single_legacy_source",
        "src/lottolab/strategies/adapters/daily539_single_legacy.py",
        "769309c73425c98bc3bbfb052497731be46d53ae3e33a1a9ce65aadb12fec1f1",
    ),
    _source_spec(
        "daily539_fourier4_source",
        "src/lottolab/strategies/adapters/daily539_fourier4.py",
        "69748bad8a78f821383b55c931cb445bea87bd19d558c2313f2951141b262c6c",
    ),
    _source_spec(
        "daily539_biglotto_portable_source",
        "src/lottolab/strategies/adapters/daily539_biglotto_portable.py",
        "90ad02c508b2d7e0d161dcd4ee3f8a7fa7558bf7c4c48f9e0d6d537cf365588c",
    ),
)


@dataclass(frozen=True, slots=True)
class StaticSourceBinding:
    callable_label: str
    source_key: str
    symbol_token: str

    @property
    def callable_identity(self) -> str:
        return f"selector-supplement-callable:{self.callable_label}"


STATIC_SOURCE_BINDINGS: Mapping[QualifiedIdentityKey, StaticSourceBinding] = {
    (
        "P638_CURRENT_REPLAY_AND_RANKING",
        "P638",
        "power_biglotto_hot_cooccurrence_1bet",
        "v0.1-p638-wave3",
    ): StaticSourceBinding(
        "lottolab.strategies.adapters.powerlotto_wave3:_hot_cooccurrence_tickets",
        "powerlotto_wave3_source",
        "_hot_cooccurrence_tickets",
    ),
    (
        "P638_CURRENT_REPLAY_AND_RANKING",
        "P638",
        "power_biglotto_hpsb_1bet",
        "v0.1-p638-wave5",
    ): StaticSourceBinding(
        "lottolab.strategies.adapters.powerlotto_wave5:_hpsb_1bet",
        "powerlotto_wave5_source",
        "_hpsb_1bet",
    ),
    (
        "P638_CURRENT_REPLAY_AND_RANKING",
        "P638",
        "power_biglotto_must_hit_top6_1bet",
        "v0.1-p638-wave3",
    ): StaticSourceBinding(
        "lottolab.strategies.adapters.powerlotto_wave3:_must_hit_top6_tickets",
        "powerlotto_wave3_source",
        "_must_hit_top6_tickets",
    ),
    (
        "P638_CURRENT_REPLAY_AND_RANKING",
        "P638",
        "power_biglotto_high_prize_trend_7bet",
        "v0.1-p638-wave4",
    ): StaticSourceBinding(
        "lottolab.strategies.adapters.powerlotto_wave4:_high_prize_trend_7bet",
        "powerlotto_wave4_source",
        "_high_prize_trend_7bet",
    ),
    (
        "T539_HISTORICAL_SQLITE",
        "T539",
        "acb_1bet",
        "v0.1-p31a",
    ): StaticSourceBinding(
        "lottolab.strategies.adapters.daily539_single_legacy:Daily539Acb1BetAdapter.get_one_bet",
        "daily539_single_legacy_source",
        "class Daily539Acb1BetAdapter",
    ),
    (
        "T539_HISTORICAL_SQLITE",
        "T539",
        "markov_1bet_539",
        "v0.1-p36",
    ): StaticSourceBinding(
        "lottolab.strategies.adapters.daily539_single_legacy:Daily539Markov1BetAdapter.get_one_bet",
        "daily539_single_legacy_source",
        "class Daily539Markov1BetAdapter",
    ),
    (
        "T539_HISTORICAL_SQLITE",
        "T539",
        "p0c_539_3bet_f_cold_x2",
        "v0.1-p36",
    ): StaticSourceBinding(
        "lottolab.strategies.adapters.daily539_fourier4:"
        "Daily539P0cFourierColdX2Adapter.get_one_bet",
        "daily539_fourier4_source",
        "class Daily539P0cFourierColdX2Adapter",
    ),
    (
        "T539_HISTORICAL_SQLITE",
        "T539",
        "t539_biglotto_hpsb_1bet",
        "v0.1-t539-cross-lottery-r2",
    ): StaticSourceBinding(
        "lottolab.strategies.adapters.daily539_biglotto_portable:"
        "Daily539BigLottoPortableAdapter.get_bets",
        "daily539_biglotto_portable_source",
        '"t539_biglotto_hpsb_1bet"',
    ),
    (
        "T539_HISTORICAL_SQLITE",
        "T539",
        "t539_biglotto_must_hit_top6_1bet",
        "v0.1-t539-cross-lottery-r2",
    ): StaticSourceBinding(
        "lottolab.strategies.adapters.daily539_biglotto_portable:"
        "Daily539BigLottoPortableAdapter.get_bets",
        "daily539_biglotto_portable_source",
        '"t539_biglotto_must_hit_top6_1bet"',
    ),
    (
        "T539_HISTORICAL_SQLITE",
        "T539",
        "t539_biglotto_zone_balance_5bet",
        "v0.1-t539-cross-lottery-r2",
    ): StaticSourceBinding(
        "lottolab.strategies.adapters.daily539_biglotto_portable:"
        "Daily539BigLottoPortableAdapter.get_bets",
        "daily539_biglotto_portable_source",
        '"t539_biglotto_zone_balance_5bet"',
    ),
}


def canonical_json_bytes(payload: Mapping[str, Any]) -> bytes:
    """Serialize deterministically with sorted keys and one trailing newline."""

    return (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def _as_mapping(value: object, *, context: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise PilotDataError(f"{context} must be an object")
    return cast(Mapping[str, Any], value)


def _as_list(value: object, *, context: str) -> list[Any]:
    if not isinstance(value, list):
        raise PilotDataError(f"{context} must be an array")
    return cast(list[Any], value)


def _as_string(value: object, *, context: str) -> str:
    if not isinstance(value, str) or not value:
        raise PilotDataError(f"{context} must be a nonempty string")
    return value


def _as_nonnegative_int(value: object, *, context: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise PilotDataError(f"{context} must be a nonnegative integer")
    return value


def _git_bytes(repository_root: Path, arguments: Sequence[str]) -> bytes:
    completed = subprocess.run(
        ["git", "-C", str(repository_root), *arguments],
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        raise PilotDataError(f"GIT_OBJECT_RESOLUTION_FAILED: {' '.join(arguments)}: {detail}")
    return completed.stdout


def _git_text(repository_root: Path, arguments: Sequence[str]) -> str:
    return _git_bytes(repository_root, arguments).decode("utf-8").strip()


def _verify_repository(repository_root: Path) -> Path:
    root = repository_root.resolve()
    observed = Path(_git_text(root, ("rev-parse", "--show-toplevel"))).resolve()
    if observed != root:
        raise PilotDataError(f"REPOSITORY_ROOT_MISMATCH: requested {root}, observed {observed}")
    observed_base_tree = _git_text(root, ("rev-parse", f"{EXPECTED_BASE_HEAD}^{{tree}}"))
    if observed_base_tree != EXPECTED_BASE_TREE:
        raise PilotDataError(
            "CANONICAL_BASE_IDENTITY_MISMATCH: "
            f"expected {EXPECTED_BASE_HEAD}/{EXPECTED_BASE_TREE}, observed tree "
            f"{observed_base_tree}"
        )
    ancestry = subprocess.run(
        ["git", "-C", str(root), "merge-base", "--is-ancestor", EXPECTED_BASE_HEAD, "HEAD"],
        check=False,
        capture_output=True,
    )
    if ancestry.returncode != 0:
        raise PilotDataError("CURRENT_HEAD_IS_NOT_A_DESCENDANT_OF_PACKET_BASE")
    return root


def load_frozen_artifact(spec: ArtifactSpec, repository_root: Path) -> LoadedArtifact:
    """Load one exact regular text blob and verify commit, tree, mode, and SHA-256."""

    observed_commit = _git_text(repository_root, ("rev-parse", f"{spec.commit}^{{commit}}"))
    observed_tree = _git_text(repository_root, ("rev-parse", f"{spec.commit}^{{tree}}"))
    if observed_commit != spec.commit or observed_tree != spec.tree:
        raise PilotDataError(
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
        raise PilotDataError(
            f"FROZEN_ARTIFACT_PATH_MISMATCH: {spec.key} resolved {len(entries)} entries"
        )
    try:
        metadata, raw_path = entries[0].split(b"\t", 1)
        mode, object_type, blob_oid = metadata.decode("ascii").split()
        observed_path = raw_path.decode("utf-8")
    except (UnicodeDecodeError, ValueError) as exc:
        raise PilotDataError(f"FROZEN_ARTIFACT_METADATA_INVALID: {spec.key}") from exc
    if mode != "100644" or object_type != "blob" or observed_path != spec.relative_path:
        raise PilotDataError(
            "FROZEN_ARTIFACT_NOT_SAFE_TEXT_BLOB: "
            f"{spec.key} mode={mode} type={object_type} path={observed_path}"
        )
    data = _git_bytes(
        repository_root,
        ("cat-file", "blob", f"{spec.commit}:{spec.relative_path}"),
    )
    observed_sha256 = hashlib.sha256(data).hexdigest()
    if observed_sha256 != spec.sha256 or _SHA256_PATTERN.fullmatch(spec.sha256) is None:
        raise PilotDataError(
            "FROZEN_ARTIFACT_SHA256_MISMATCH: "
            f"{spec.key} expected {spec.sha256}, observed {observed_sha256}"
        )
    return LoadedArtifact(spec=spec, blob_oid=blob_oid, data=data)


def load_frozen_authorities(
    repository_root: Path = REPOSITORY_ROOT,
) -> dict[str, LoadedArtifact]:
    """Load and cross-check the six packet-authorized JSON authorities."""

    root = _verify_repository(repository_root)
    artifacts = {spec.key: load_frozen_artifact(spec, root) for spec in JSON_ARTIFACT_SPECS}
    r2 = artifacts["r2_attribution"].json_payload()
    if r2.get("schema_version") != "SELECTOR_LINEAGE_DIVERSITY_ATTRIBUTION_RESULT_V2":
        raise PilotDataError("R2_ATTRIBUTION_SCHEMA_MISMATCH")
    source_identities = _as_mapping(r2.get("source_identities"), context="r2.source_identities")
    for key in (
        "rolling_selector",
        "rolling_decomposition",
        "base_lineage",
        "wave26_supplement",
        "selector_universe_lineage",
    ):
        observed = _as_mapping(source_identities.get(key), context=f"source_identities.{key}")
        expected = artifacts[key].identity_payload()
        if dict(observed) != expected:
            raise PilotDataError(f"R2_SOURCE_IDENTITY_MISMATCH: {key}")
    return artifacts


def _load_static_source_artifacts(repository_root: Path) -> dict[str, LoadedArtifact]:
    sources = {
        spec.key: load_frozen_artifact(spec, repository_root) for spec in STATIC_SOURCE_SPECS
    }
    for identity_key, binding in STATIC_SOURCE_BINDINGS.items():
        source = sources[binding.source_key].data.decode("utf-8")
        if identity_key[2] not in source or binding.symbol_token not in source:
            raise PilotDataError(f"STATIC_SOURCE_BINDING_EVIDENCE_MISSING: {identity_key[2]}")
    return sources


def load_original_runner(repository_root: Path = REPOSITORY_ROOT) -> types.ModuleType:
    """Load the exact sealed original selector runner without invoking its CLI."""

    module_name = "_sealed_original_causal_selector_runner"
    existing = sys.modules.get(module_name)
    if isinstance(existing, types.ModuleType):
        return existing
    root = _verify_repository(repository_root)
    artifact = load_frozen_artifact(ORIGINAL_SELECTOR_RUNNER_ARTIFACT, root)
    module = types.ModuleType(module_name)
    module.__file__ = str(root / ORIGINAL_SELECTOR_RUNNER_ARTIFACT.relative_path)
    module.__package__ = ""
    sys.modules[module_name] = module
    try:
        source = artifact.data.decode("utf-8")
        exec(compile(source, module.__file__, "exec"), module.__dict__)
    except Exception:
        sys.modules.pop(module_name, None)
        raise
    return module


def _qualified_key(value: object, *, context: str) -> QualifiedIdentityKey:
    items = _as_list(value, context=context)
    if len(items) != 4:
        raise PilotDataError(f"{context} must contain four identity fields")
    return cast(
        QualifiedIdentityKey,
        tuple(_as_string(item, context=context) for item in items),
    )


def _unique_records_by_strategy(value: object, *, context: str) -> dict[str, Mapping[str, Any]]:
    records: dict[str, Mapping[str, Any]] = {}
    for index, item in enumerate(_as_list(value, context=context)):
        record = _as_mapping(item, context=f"{context}[{index}]")
        strategy_id = _as_string(
            record.get("strategy_id"), context=f"{context}[{index}].strategy_id"
        )
        if strategy_id in records:
            raise PilotDataError(f"{context} contains duplicate strategy_id {strategy_id}")
        records[strategy_id] = record
    return records


def _r2_lineage_by_key(
    r2_payload: Mapping[str, Any],
) -> dict[QualifiedIdentityKey, CandidateBinding]:
    merge = _as_mapping(r2_payload.get("lineage_merge"), context="r2.lineage_merge")
    records = _as_list(merge.get("records"), context="r2.lineage_merge.records")
    result: dict[QualifiedIdentityKey, CandidateBinding] = {}
    for index, item in enumerate(records):
        record = _as_mapping(item, context=f"r2.records[{index}]")
        identity_key = _qualified_key(
            record.get("authority_qualified_identity_key"),
            context=f"r2.records[{index}].authority_qualified_identity_key",
        )
        if identity_key in result:
            raise PilotDataError(f"DUPLICATE_LINEAGE_IDENTITY: {identity_key}")
        result[identity_key] = CandidateBinding(
            source_authority_id=identity_key[0],
            lottery_id=identity_key[1],
            native_ticket_count=-1,
            strategy_id=identity_key[2],
            strategy_version=identity_key[3],
            callable_identity=_as_string(
                record.get("callable_identity"),
                context=f"r2.records[{index}].callable_identity",
            ),
            callable_label=_as_string(
                record.get("callable_family_label"),
                context=f"r2.records[{index}].callable_family_label",
            ),
            resolution_authority="R2_AUTHORITY_QUALIFIED_ATTRIBUTION",
        )
    if len(result) != 135:
        raise PilotDataError(f"R2_QUALIFIED_IDENTITY_COUNT_MISMATCH: {len(result)}")
    return result


def _production_callable_resolution(
    *,
    strategy_id: str,
    lottery_id: str,
    base_records: Mapping[str, Mapping[str, Any]],
    wave_records: Mapping[str, Mapping[str, Any]],
) -> tuple[str, str, str] | None:
    base = base_records.get(strategy_id)
    if base is None:
        return None
    games = {
        _as_string(item, context=f"base_lineage.{strategy_id}.game_identities")
        for item in _as_list(
            base.get("game_identities"),
            context=f"base_lineage.{strategy_id}.game_identities",
        )
    }
    if lottery_id not in games:
        return None
    classification = _as_string(
        base.get("classification"), context=f"base_lineage.{strategy_id}.classification"
    )
    if classification != "DYNAMIC_OR_UNRESOLVED":
        module = _as_string(
            base.get("implementation_module"),
            context=f"base_lineage.{strategy_id}.implementation_module",
        )
        symbol = _as_string(
            base.get("callable_or_class_symbol"),
            context=f"base_lineage.{strategy_id}.callable_or_class_symbol",
        )
        return (
            _as_string(
                base.get("callable_family_id"),
                context=f"base_lineage.{strategy_id}.callable_family_id",
            ),
            f"{module}:{symbol}",
            "BASE_PRODUCTION_LINEAGE",
        )
    wave = wave_records.get(strategy_id)
    if wave is None:
        raise PilotDataError(f"WAVE26_RESOLUTION_MISSING: {strategy_id}")
    structural_digest = _as_string(
        wave.get("structural_source_digest_sha256"),
        context=f"wave26.{strategy_id}.structural_source_digest_sha256",
    )
    implementation = _as_mapping(
        wave.get("implementation_class_callable"),
        context=f"wave26.{strategy_id}.implementation_class_callable",
    )
    label = _as_string(
        implementation.get("statically_selected_wave26_callable_locator"),
        context=f"wave26.{strategy_id}.statically_selected_wave26_callable_locator",
    )
    return (
        f"wave26-structural-sha256:{structural_digest}",
        label,
        "WAVE26_DYNAMIC_BINDING_SUPPLEMENT",
    )


def resolve_candidate_bindings(
    selector_payload: Mapping[str, Any],
    *,
    r2_payload: Mapping[str, Any],
    base_lineage_payload: Mapping[str, Any],
    wave26_payload: Mapping[str, Any],
) -> dict[str, tuple[CandidateBinding, ...]]:
    """Resolve every frozen cell candidate to one static callable identity."""

    r2_by_key = _r2_lineage_by_key(r2_payload)
    base_records = _unique_records_by_strategy(
        base_lineage_payload.get("records"), context="base_lineage.records"
    )
    wave_records = _unique_records_by_strategy(
        wave26_payload.get("records"), context="wave26.records"
    )
    result: dict[str, tuple[CandidateBinding, ...]] = {}
    seen_global_keys: set[QualifiedIdentityKey] = set()
    cells = _as_list(selector_payload.get("cells"), context="selector.cells")
    for cell_index, item in enumerate(cells):
        cell = _as_mapping(item, context=f"selector.cells[{cell_index}]")
        cell_id = _as_string(cell.get("cell_id"), context=f"selector.cells[{cell_index}].cell_id")
        source_authority_id = _as_string(
            cell.get("source_authority_id"),
            context=f"selector.cells[{cell_index}].source_authority_id",
        )
        lottery_id = _as_string(
            cell.get("lottery_id"), context=f"selector.cells[{cell_index}].lottery_id"
        )
        ticket_count = _as_nonnegative_int(
            cell.get("native_ticket_count"),
            context=f"selector.cells[{cell_index}].native_ticket_count",
        )
        bindings: list[CandidateBinding] = []
        seen_cell_keys: set[QualifiedIdentityKey] = set()
        candidates = _as_list(
            cell.get("candidate_strategies"),
            context=f"selector.cells[{cell_index}].candidate_strategies",
        )
        for candidate_index, candidate_item in enumerate(candidates):
            candidate = _as_mapping(
                candidate_item,
                context=f"selector.cells[{cell_index}].candidate_strategies[{candidate_index}]",
            )
            strategy_id = _as_string(candidate.get("strategy_id"), context=f"{cell_id}.strategy_id")
            strategy_version = _as_string(
                candidate.get("strategy_version"), context=f"{cell_id}.strategy_version"
            )
            identity_key = (
                source_authority_id,
                lottery_id,
                strategy_id,
                strategy_version,
            )
            if identity_key in seen_cell_keys:
                raise PilotDataError(f"DUPLICATE_CANDIDATE_IDENTITY: {cell_id}:{identity_key}")
            seen_cell_keys.add(identity_key)
            seen_global_keys.add(identity_key)

            r2_binding = r2_by_key.get(identity_key)
            if r2_binding is not None:
                binding = replace(r2_binding, native_ticket_count=ticket_count)
            else:
                production = _production_callable_resolution(
                    strategy_id=strategy_id,
                    lottery_id=lottery_id,
                    base_records=base_records,
                    wave_records=wave_records,
                )
                if production is not None:
                    callable_identity, callable_label, authority = production
                else:
                    static = STATIC_SOURCE_BINDINGS.get(identity_key)
                    if static is None:
                        raise PilotDataError(
                            f"CALLABLE_LINEAGE_COVERAGE_MISSING: {cell_id}:{identity_key}"
                        )
                    callable_identity = static.callable_identity
                    callable_label = static.callable_label
                    authority = "SEALED_SELECTOR_SOURCE_STATIC_RESOLUTION"
                binding = CandidateBinding(
                    source_authority_id=source_authority_id,
                    lottery_id=lottery_id,
                    native_ticket_count=ticket_count,
                    strategy_id=strategy_id,
                    strategy_version=strategy_version,
                    callable_identity=callable_identity,
                    callable_label=callable_label,
                    resolution_authority=authority,
                )
            bindings.append(binding)
        result[cell_id] = tuple(sorted(bindings, key=lambda binding: binding.identity_key))
    if len(seen_global_keys) != 170:
        raise PilotDataError(f"CANDIDATE_IDENTITY_CENSUS_MISMATCH: {len(seen_global_keys)}")
    return result


def group_callable_families(
    bindings: Sequence[CandidateBinding],
) -> tuple[CallableFamily, ...]:
    """Group by authority/lottery/K/callable and choose the fixed lexical minimum."""

    members_by_family: defaultdict[CallableFamilyKey, list[CandidateBinding]] = defaultdict(list)
    seen: set[QualifiedIdentityKey] = set()
    for binding in bindings:
        if binding.identity_key in seen:
            raise PilotDataError(f"DUPLICATE_CANDIDATE_IDENTITY: {binding.identity_key}")
        seen.add(binding.identity_key)
        members_by_family[binding.family_key].append(binding)
    families: list[CallableFamily] = []
    for family_key in sorted(members_by_family):
        members = tuple(
            sorted(members_by_family[family_key], key=lambda binding: binding.identity_key)
        )
        families.append(
            CallableFamily(
                family_key=family_key,
                members=members,
                representative=min(members, key=lambda binding: binding.identity_key),
            )
        )
    return tuple(families)


def representative_identity_keys(
    bindings: Sequence[CandidateBinding],
) -> frozenset[QualifiedIdentityKey]:
    """Return only lexical identity representatives; no outcome is accepted as input."""

    return frozenset(
        family.representative.identity_key for family in group_callable_families(bindings)
    )


def _fraction_payload(value: Fraction) -> dict[str, Any]:
    with localcontext() as context:
        context.prec = 40
        decimal_value = Decimal(value.numerator) / Decimal(value.denominator)
    return {
        "decimal_12": format(decimal_value, ".12f"),
        "denominator": value.denominator,
        "exact": f"{value.numerator}/{value.denominator}",
        "numerator": value.numerator,
    }


def _metric_fraction(metric: object, *, context: str) -> Fraction:
    payload = _as_mapping(metric, context=context)
    success_count = _as_nonnegative_int(
        payload.get("success_count"), context=f"{context}.success_count"
    )
    target_count = _as_nonnegative_int(
        payload.get("target_count"), context=f"{context}.target_count"
    )
    if target_count == 0:
        raise PilotDataError(f"{context}.target_count must be positive")
    value = Fraction(success_count, target_count)
    rate = _as_mapping(payload.get("rate"), context=f"{context}.rate")
    if rate.get("exact") != f"{value.numerator}/{value.denominator}":
        raise PilotDataError(f"{context}.rate exact fraction mismatch")
    return value


def _sign(value: Fraction | None) -> str:
    if value is None:
        return "INCONCLUSIVE"
    if value > 0:
        return "POSITIVE"
    if value < 0:
        return "NEGATIVE"
    return "ZERO"


def _delta_payload(left_metric: object, right_metric: object, *, context: str) -> dict[str, Any]:
    left = _metric_fraction(left_metric, context=f"{context}.left")
    right = _metric_fraction(right_metric, context=f"{context}.right")
    return _fraction_payload(left - right)


def _selection_frequencies(value: object, *, context: str) -> dict[str, int]:
    frequencies = _as_mapping(value, context=context)
    result: dict[str, int] = {}
    for strategy_id, count in frequencies.items():
        result[strategy_id] = _as_nonnegative_int(count, context=f"{context}.{strategy_id}")
    return dict(sorted(result.items()))


def _callable_frequencies(
    strategy_frequencies: Mapping[str, int],
    bindings: Sequence[CandidateBinding],
) -> dict[str, int]:
    by_strategy = {binding.strategy_id: binding for binding in bindings}
    counts: Counter[str] = Counter()
    for strategy_id, count in strategy_frequencies.items():
        binding = by_strategy.get(strategy_id)
        if binding is None:
            raise PilotDataError(f"SELECTION_FREQUENCY_LINEAGE_MISSING: {strategy_id}")
        counts[binding.callable_identity] += count
    return {identity: counts[identity] for identity in sorted(counts)}


def _candidate_identity(
    candidate: Any, source_authority_id: str, lottery_id: str
) -> QualifiedIdentityKey:
    return (
        source_authority_id,
        lottery_id,
        str(candidate.strategy_id),
        str(candidate.strategy_version),
    )


def _validate_replay_authority_parity(
    actual_authorities: Sequence[Any], selector_payload: Mapping[str, Any]
) -> list[dict[str, Any]]:
    observed = [
        {
            "authority_id": str(authority.authority_id),
            "details": dict(cast(Mapping[str, Any], authority.details)),
            "lottery_id": str(authority.lottery_id),
        }
        for authority in actual_authorities
    ]
    expected = _as_list(
        selector_payload.get("source_authorities"), context="selector.source_authorities"
    )
    if observed != expected:
        raise PilotDataError("SEALED_REPLAY_AUTHORITY_PARITY_MISMATCH")
    return observed


def _sealed_cells_by_id(selector_payload: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    for index, item in enumerate(_as_list(selector_payload.get("cells"), context="selector.cells")):
        cell = _as_mapping(item, context=f"selector.cells[{index}]")
        cell_id = _as_string(cell.get("cell_id"), context=f"selector.cells[{index}].cell_id")
        if cell_id in result:
            raise PilotDataError(f"DUPLICATE_SELECTOR_CELL: {cell_id}")
        result[cell_id] = cell
    if len(result) != 22:
        raise PilotDataError(f"SELECTOR_CELL_COUNT_MISMATCH: {len(result)}")
    return result


def _validate_cell_candidates(
    live_cell: Any,
    sealed_cell: Mapping[str, Any],
) -> None:
    sealed_candidates = _as_list(
        sealed_cell.get("candidate_strategies"), context="sealed_cell.candidate_strategies"
    )
    observed = [
        {
            "display_name": str(candidate.display_name),
            "minimum_history": int(candidate.minimum_history),
            "strategy_id": str(candidate.strategy_id),
            "strategy_version": str(candidate.strategy_version),
        }
        for candidate in live_cell.candidates
    ]
    if observed != sealed_candidates:
        raise PilotDataError(f"SEALED_CANDIDATE_UNIVERSE_PARITY_MISMATCH: {sealed_cell['cell_id']}")


def _experiment_record(
    *,
    runner: Any,
    live_cell: Any,
    sealed_cell: Mapping[str, Any],
    bindings: Sequence[CandidateBinding],
    families: Sequence[CallableFamily],
    window_label: str,
    source_window_label: str,
    window: int,
) -> dict[str, Any]:
    experiments = _as_mapping(sealed_cell.get("experiments"), context="sealed_cell.experiments")
    sealed_experiment = _as_mapping(
        experiments.get(source_window_label),
        context=f"sealed_cell.experiments.{source_window_label}",
    )
    original_evaluation = runner.evaluate_cell(
        live_cell,
        label=source_window_label,
        window=window,
    )
    recomputed_original = cast(dict[str, Any], runner.experiment_payload(original_evaluation))
    if recomputed_original != sealed_experiment:
        raise PilotDataError(
            f"SEALED_ORIGINAL_REPLAY_PARITY_MISMATCH: {sealed_cell['cell_id']}:{window_label}"
        )

    representative_keys = {family.representative.identity_key for family in families}
    dedup_candidates = tuple(
        candidate
        for candidate in live_cell.candidates
        if _candidate_identity(
            candidate,
            str(live_cell.source_authority_id),
            str(live_cell.lottery_id),
        )
        in representative_keys
    )
    if len(dedup_candidates) != len(families) or not dedup_candidates:
        raise PilotDataError(f"DEDUPLICATED_CALLABLE_UNIVERSE_INVALID: {sealed_cell['cell_id']}")
    dedup_cell = replace(live_cell, candidates=dedup_candidates)
    dedup_evaluation = runner.evaluate_cell(
        dedup_cell,
        label=source_window_label,
        window=window,
    )
    dedup_experiment = cast(dict[str, Any], runner.experiment_payload(dedup_evaluation))
    if tuple(original_evaluation.rolling_target_ids) != tuple(dedup_evaluation.rolling_target_ids):
        raise PilotDataError(
            f"ORIGINAL_DEDUP_TARGET_SET_MISMATCH: {sealed_cell['cell_id']}:{window_label}"
        )
    if tuple(dedup_evaluation.rolling_target_ids) != tuple(dedup_evaluation.frozen_target_ids):
        raise PilotDataError(
            f"DEDUP_ROLLING_FROZEN_TARGET_SET_MISMATCH: {sealed_cell['cell_id']}:{window_label}"
        )

    original_metric = sealed_experiment.get("rolling_selector_primary_metric_result")
    dedup_metric = dedup_experiment.get("rolling_selector_primary_metric_result")
    dedup_frozen_metric = dedup_experiment.get("frozen_baseline_primary_metric_result")
    original_baseline_metric = sealed_experiment.get("frozen_baseline_primary_metric_result")
    complete = (
        sealed_experiment.get("status") == "COMPLETE"
        and dedup_experiment.get("status") == "COMPLETE"
    )
    if complete and (
        original_metric is None
        or dedup_metric is None
        or dedup_frozen_metric is None
        or original_baseline_metric is None
    ):
        raise PilotDataError("COMPLETE_EXPERIMENT_METRIC_MISSING")

    if complete:
        dedup_vs_original = _delta_payload(
            dedup_metric,
            original_metric,
            context="dedup_vs_original",
        )
        dedup_vs_frozen = _delta_payload(
            dedup_metric,
            dedup_frozen_metric,
            context="dedup_vs_frozen",
        )
        original_vs_frozen = _delta_payload(
            original_metric,
            original_baseline_metric,
            context="original_vs_frozen",
        )
        original_strategy_frequency = _selection_frequencies(
            sealed_experiment.get("rolling_selection_frequency"),
            context="original_selection_frequency",
        )
        dedup_strategy_frequency = _selection_frequencies(
            dedup_experiment.get("rolling_selection_frequency"),
            context="dedup_selection_frequency",
        )
    else:
        dedup_vs_original = None
        dedup_vs_frozen = None
        original_vs_frozen = None
        original_strategy_frequency = {}
        dedup_strategy_frequency = {}

    eligible_target_count = _as_nonnegative_int(
        dedup_experiment.get("eligible_target_count"),
        context="dedup.eligible_target_count",
    )
    original_eligible = _as_nonnegative_int(
        sealed_experiment.get("eligible_target_count"),
        context="original.eligible_target_count",
    )
    if eligible_target_count != original_eligible:
        raise PilotDataError("ORIGINAL_DEDUP_ELIGIBLE_TARGET_COUNT_MISMATCH")

    original_switches = _as_nonnegative_int(
        sealed_experiment.get("rolling_strategy_switch_count"),
        context="original.rolling_strategy_switch_count",
    )
    dedup_switches = _as_nonnegative_int(
        dedup_experiment.get("rolling_strategy_switch_count"),
        context="dedup.rolling_strategy_switch_count",
    )
    return {
        "cell_id": sealed_cell["cell_id"],
        "dedup_frozen_metric": dedup_frozen_metric,
        "dedup_frozen_strategy_id": dedup_experiment.get("frozen_baseline_strategy"),
        "dedup_rolling_metric": dedup_metric,
        "dedup_rolling_vs_dedup_frozen_exact_delta": dedup_vs_frozen,
        "dedup_rolling_vs_dedup_frozen_sign": (
            _sign(Fraction(dedup_vs_frozen["numerator"], dedup_vs_frozen["denominator"]))
            if dedup_vs_frozen is not None
            else "INCONCLUSIVE"
        ),
        "dedup_vs_original_exact_delta": dedup_vs_original,
        "dedup_vs_original_sign": (
            _sign(
                Fraction(
                    dedup_vs_original["numerator"],
                    dedup_vs_original["denominator"],
                )
            )
            if dedup_vs_original is not None
            else "INCONCLUSIVE"
        ),
        "deduplicated_callable_count": len(families),
        "eligible_target_count": eligible_target_count,
        "exclusions": {
            "dedup_exclusion_reason": dedup_experiment.get("exclusion_reason"),
            "dedup_status": dedup_experiment.get("status"),
            "original_exclusion_reason": sealed_experiment.get("exclusion_reason"),
            "original_status": sealed_experiment.get("status"),
        },
        "first_target": dedup_experiment.get("first_evaluated_target"),
        "k": sealed_cell["native_ticket_count"],
        "last_target": dedup_experiment.get("last_evaluated_target"),
        "lottery_id": sealed_cell["lottery_id"],
        "original_candidate_count": len(bindings),
        "original_frozen_metric": original_baseline_metric,
        "original_frozen_strategy_id": sealed_experiment.get("frozen_baseline_strategy"),
        "original_rolling_metric": original_metric,
        "original_rolling_vs_original_frozen_exact_delta": original_vs_frozen,
        "original_rolling_vs_original_frozen_sign": (
            _sign(
                Fraction(
                    original_vs_frozen["numerator"],
                    original_vs_frozen["denominator"],
                )
            )
            if original_vs_frozen is not None
            else "INCONCLUSIVE"
        ),
        "removed_sibling_count": len(bindings) - len(families),
        "selection_frequencies": {
            "dedup_rolling_by_callable": _callable_frequencies(dedup_strategy_frequency, bindings),
            "dedup_rolling_by_strategy": dedup_strategy_frequency,
            "original_rolling_by_callable": _callable_frequencies(
                original_strategy_frequency, bindings
            ),
            "original_rolling_by_strategy": original_strategy_frequency,
        },
        "source_authority_id": sealed_cell["source_authority_id"],
        "switch_counts": {
            "dedup_minus_original": dedup_switches - original_switches,
            "dedup_rolling": dedup_switches,
            "original_rolling": original_switches,
        },
        "target_set_parity": {
            "dedup_rolling_equals_dedup_frozen": True,
            "original_equals_dedup": True,
        },
        "window": window,
        "window_label": window_label,
    }


def _discordant_sign_pairs(signs: Sequence[str]) -> int:
    nonzero = [sign for sign in signs if sign in {"POSITIVE", "NEGATIVE"}]
    return sum(
        left != right for index, left in enumerate(nonzero) for right in nonzero[index + 1 :]
    )


def _w50_opposite_cell_ids(
    experiments: Sequence[Mapping[str, Any]], *, sign_field: str
) -> list[str]:
    by_cell: defaultdict[str, dict[str, str]] = defaultdict(dict)
    for experiment in experiments:
        cell_id = _as_string(experiment.get("cell_id"), context="experiment.cell_id")
        label = _as_string(experiment.get("window_label"), context="experiment.window_label")
        sign = _as_string(experiment.get(sign_field), context=f"experiment.{sign_field}")
        by_cell[cell_id][label] = sign
    result: list[str] = []
    for cell_id, signs in sorted(by_cell.items()):
        short = signs.get("W50")
        if short not in {"POSITIVE", "NEGATIVE"}:
            continue
        if any(
            signs.get(label) in {"POSITIVE", "NEGATIVE"} and signs[label] != short
            for label in ("W300", "W750")
        ):
            result.append(cell_id)
    return result


def _ratio_payload(numerator: int, denominator: int) -> dict[str, Any] | None:
    if denominator <= 0:
        return None
    return _fraction_payload(Fraction(numerator, denominator))


def _build_required_answers(
    experiments: Sequence[Mapping[str, Any]],
    cells: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    comparable = [
        experiment
        for experiment in experiments
        if experiment.get("dedup_vs_original_sign") != "INCONCLUSIVE"
    ]
    comparison_counts = Counter(
        _as_string(
            experiment.get("dedup_vs_original_sign"),
            context="experiment.dedup_vs_original_sign",
        )
        for experiment in comparable
    )
    improves_more = comparison_counts["POSITIVE"] > comparison_counts["NEGATIVE"]

    repeated: list[dict[str, Any]] = []
    original_discordant_total = 0
    dedup_discordant_total = 0
    for cell_id in REPEATED_POSITIVE_CELL_IDS:
        records = sorted(
            (experiment for experiment in experiments if experiment.get("cell_id") == cell_id),
            key=lambda experiment: int(cast(int, experiment["window"])),
        )
        original_signs = [
            _as_string(
                record.get("original_rolling_vs_original_frozen_sign"),
                context="original_sign",
            )
            for record in records
        ]
        dedup_signs = [
            _as_string(
                record.get("dedup_rolling_vs_dedup_frozen_sign"),
                context="dedup_sign",
            )
            for record in records
        ]
        original_discordant = _discordant_sign_pairs(original_signs)
        dedup_discordant = _discordant_sign_pairs(dedup_signs)
        original_discordant_total += original_discordant
        dedup_discordant_total += dedup_discordant
        repeated.append(
            {
                "cell_id": cell_id,
                "dedup_discordant_window_pairs": dedup_discordant,
                "dedup_signs": dict(zip(("W50", "W300", "W750"), dedup_signs, strict=True)),
                "original_discordant_window_pairs": original_discordant,
                "original_signs": dict(zip(("W50", "W300", "W750"), original_signs, strict=True)),
            }
        )

    p638_k1 = sorted(
        (experiment for experiment in experiments if experiment.get("cell_id") == "P638:K1"),
        key=lambda experiment: int(cast(int, experiment["window"])),
    )
    p638_cell = next(cell for cell in cells if cell.get("cell_id") == "P638:K1")
    p638_family = next(
        family
        for family in _as_list(p638_cell.get("callable_families"), context="P638:K1.families")
        if set(
            _as_string(identity[2], context="P638 family strategy")
            for identity in _as_list(
                _as_mapping(family, context="P638 family").get("member_identities"),
                context="P638 family members",
            )
        )
        == set(P638_C01_C07_STRATEGY_IDS)
    )
    p638_sign_changes = [
        _as_string(record.get("window_label"), context="P638 window")
        for record in p638_k1
        if record.get("original_rolling_vs_original_frozen_sign")
        != record.get("dedup_rolling_vs_dedup_frozen_sign")
    ]

    original_w50_reversal_cells = _w50_opposite_cell_ids(
        experiments, sign_field="original_rolling_vs_original_frozen_sign"
    )
    dedup_w50_reversal_cells = _w50_opposite_cell_ids(
        experiments, sign_field="dedup_rolling_vs_dedup_frozen_sign"
    )

    complete_switch_records = [
        experiment for experiment in experiments if experiment.get("eligible_target_count", 0) > 0
    ]
    original_switches = sum(
        int(_as_mapping(record["switch_counts"], context="switch_counts")["original_rolling"])
        for record in complete_switch_records
    )
    dedup_switches = sum(
        int(_as_mapping(record["switch_counts"], context="switch_counts")["dedup_rolling"])
        for record in complete_switch_records
    )
    transitions = sum(
        max(int(cast(int, record["eligible_target_count"])) - 1, 0)
        for record in complete_switch_records
    )
    switch_direction_counts = Counter(
        "DECREASED"
        if int(
            _as_mapping(record["switch_counts"], context="switch_counts")["dedup_minus_original"]
        )
        < 0
        else (
            "INCREASED"
            if int(
                _as_mapping(record["switch_counts"], context="switch_counts")[
                    "dedup_minus_original"
                ]
            )
            > 0
            else "UNCHANGED"
        )
        for record in complete_switch_records
    )

    positive_records = [
        record for record in comparable if record.get("dedup_vs_original_sign") == "POSITIVE"
    ]
    by_lottery = Counter(str(record["lottery_id"]) for record in positive_records)
    by_window = Counter(str(record["window_label"]) for record in positive_records)
    by_cell = Counter(str(record["cell_id"]) for record in positive_records)

    return [
        {
            "answer": "YES" if improves_more else "NO",
            "evidence": {
                "improved": comparison_counts["POSITIVE"],
                "unchanged": comparison_counts["ZERO"],
                "worsened": comparison_counts["NEGATIVE"],
            },
            "question": "Does family dedup improve more cells than it worsens?",
        },
        {
            "answer": (
                "YES"
                if dedup_discordant_total < original_discordant_total
                else ("NO_CHANGE" if dedup_discordant_total == original_discordant_total else "NO")
            ),
            "evidence": {
                "dedup_discordant_window_pairs": dedup_discordant_total,
                "original_discordant_window_pairs": original_discordant_total,
                "per_cell": repeated,
            },
            "question": "Among the five repeated-positive R2 cells, does sign stability improve?",
        },
        {
            "answer": (
                "DESCRIPTIVE_SIGN_CHANGE"
                if p638_sign_changes
                else "EXACT_RESULTS_CHANGED_WITHOUT_SIGN_CHANGE"
            ),
            "evidence": {
                "c01_c07_family": p638_family,
                "materiality_threshold": "NOT_DEFINED_OR_TESTED",
                "per_window": p638_k1,
                "sign_changed_windows": p638_sign_changes,
            },
            "question": "Do P638 K1 results materially change after collapsing the C01-C07 family?",
        },
        {
            "answer": (
                "YES"
                if len(dedup_w50_reversal_cells) < len(original_w50_reversal_cells)
                else (
                    "NO_CHANGE"
                    if len(dedup_w50_reversal_cells) == len(original_w50_reversal_cells)
                    else "NO"
                )
            ),
            "evidence": {
                "dedup_reversal_cell_count": len(dedup_w50_reversal_cells),
                "dedup_reversal_cells": dedup_w50_reversal_cells,
                "original_reversal_cell_count": len(original_w50_reversal_cells),
                "original_reversal_cells": original_w50_reversal_cells,
            },
            "question": "Are W50 sign reversals reduced?",
        },
        {
            "answer": (
                "YES"
                if dedup_switches < original_switches
                else ("NO_CHANGE" if dedup_switches == original_switches else "NO")
            ),
            "evidence": {
                "dedup_switch_frequency": _ratio_payload(dedup_switches, transitions),
                "dedup_switches": dedup_switches,
                "experiment_directions": {
                    key: switch_direction_counts[key]
                    for key in ("DECREASED", "UNCHANGED", "INCREASED")
                },
                "original_switch_frequency": _ratio_payload(original_switches, transitions),
                "original_switches": original_switches,
                "shared_transition_count": transitions,
            },
            "question": "Does switching frequency decrease?",
        },
        {
            "answer": "DESCRIPTIVE_COUNTS_ONLY",
            "evidence": {
                "improvements_by_cell": dict(sorted(by_cell.items())),
                "improvements_by_lottery": dict(sorted(by_lottery.items())),
                "improvements_by_window": dict(sorted(by_window.items())),
                "positive_experiments": [
                    {
                        "cell_id": record["cell_id"],
                        "delta": record["dedup_vs_original_exact_delta"],
                        "window_label": record["window_label"],
                    }
                    for record in positive_records
                ],
            },
            "question": "Are gains concentrated in any lottery/K/window?",
        },
        {
            "answer": (
                "YES"
                if comparison_counts["POSITIVE"] > 0 and comparison_counts["NEGATIVE"] > 0
                else "NO"
            ),
            "evidence": {
                "positive": comparison_counts["POSITIVE"],
                "zero": comparison_counts["ZERO"],
                "negative": comparison_counts["NEGATIVE"],
            },
            "question": "Does the dedup challenger still show mixed outcomes?",
        },
    ]


def build_result(
    *,
    artifacts: Mapping[str, LoadedArtifact],
    source_artifacts: Mapping[str, LoadedArtifact],
    replay_authorities: Sequence[Mapping[str, Any]],
    live_cells: Sequence[Any],
    runner: Any,
) -> dict[str, Any]:
    selector_payload = artifacts["rolling_selector"].json_payload()
    sealed_cells = _sealed_cells_by_id(selector_payload)
    bindings_by_cell = resolve_candidate_bindings(
        selector_payload,
        r2_payload=artifacts["r2_attribution"].json_payload(),
        base_lineage_payload=artifacts["base_lineage"].json_payload(),
        wave26_payload=artifacts["wave26_supplement"].json_payload(),
    )
    cell_payloads: list[dict[str, Any]] = []
    experiment_payloads: list[dict[str, Any]] = []
    resolution_counts: Counter[str] = Counter()
    for live_cell in live_cells:
        cell_id = f"{live_cell.lottery_id}:K{live_cell.native_ticket_count}"
        sealed_cell = sealed_cells.get(cell_id)
        if sealed_cell is None:
            raise PilotDataError(f"LIVE_CELL_NOT_IN_SEALED_SELECTOR: {cell_id}")
        _validate_cell_candidates(live_cell, sealed_cell)
        bindings = bindings_by_cell[cell_id]
        families = group_callable_families(bindings)
        for binding in bindings:
            resolution_counts[binding.resolution_authority] += 1
        experiments = [
            _experiment_record(
                runner=runner,
                live_cell=live_cell,
                sealed_cell=sealed_cell,
                bindings=bindings,
                families=families,
                window_label=window_label,
                source_window_label=source_window_label,
                window=window,
            )
            for window_label, source_window_label, window in WINDOWS
        ]
        experiment_payloads.extend(experiments)
        coverage = _as_mapping(sealed_cell.get("coverage"), context=f"{cell_id}.coverage")
        cell_payloads.append(
            {
                "callable_families": [family.as_payload() for family in families],
                "cell_id": cell_id,
                "coverage": dict(coverage),
                "deduplicated_callable_count": len(families),
                "experiments": experiments,
                "k": int(live_cell.native_ticket_count),
                "lottery_id": str(live_cell.lottery_id),
                "original_candidate_count": len(bindings),
                "removed_sibling_count": len(bindings) - len(families),
                "source_authority_id": str(live_cell.source_authority_id),
            }
        )

    if len(cell_payloads) != 22 or len(experiment_payloads) != 66:
        raise PilotDataError(
            f"OUTPUT_CELL_EXPERIMENT_CENSUS_MISMATCH: {len(cell_payloads)}/"
            f"{len(experiment_payloads)}"
        )
    original_candidate_total = sum(int(cell["original_candidate_count"]) for cell in cell_payloads)
    dedup_callable_total = sum(int(cell["deduplicated_callable_count"]) for cell in cell_payloads)
    removed_total = sum(int(cell["removed_sibling_count"]) for cell in cell_payloads)
    if original_candidate_total - dedup_callable_total != removed_total:
        raise PilotDataError("CALLABLE_FAMILY_COUNT_ACCOUNTING_MISMATCH")

    required_answers = _build_required_answers(experiment_payloads, cell_payloads)
    return {
        "canonical_base": {
            "expected_head": EXPECTED_BASE_HEAD,
            "expected_tree": EXPECTED_BASE_TREE,
        },
        "cells": cell_payloads,
        "claim_boundary": {
            "exploratory_historical_research": True,
            "k2_r2": "NOT_RUN",
            "p638_zone2": "NOT_RUN",
            "predictive_advantage": "NOT_ESTABLISHED",
            "profitability": "NOT_ESTABLISHED",
            "reference_promotion": "NOT_AUTHORIZED",
            "runtime_promotion": "NOT_AUTHORIZED",
            "second_exchange": "NOT_RUN",
            "statistical_significance_rule": "NOT_CALCULATED",
        },
        "dedup_rule": {
            "grouping_scope": (
                "SOURCE_AUTHORITY_ID_X_LOTTERY_ID_X_NATIVE_TICKET_COUNT_X_CALLABLE_IDENTITY"
            ),
            "historical_outcomes_used_for_representative": False,
            "representative_identity_order": [
                "source_authority_id",
                "lottery_id",
                "strategy_id",
                "strategy_version",
            ],
            "representative_rule": ("LEXICOGRAPHIC_MINIMUM_COMPLETE_AUTHORITY_QUALIFIED_IDENTITY"),
            "representative_sweep": "NOT_RUN",
        },
        "invariants": {
            "composite_score": "NOT_USED",
            "database_writes": "NONE",
            "dedup_rolling_frozen_universe": "IDENTICAL",
            "future_target_selection_input": "FORBIDDEN_AND_VALIDATED",
            "original_dedup_target_sets": "IDENTICAL_BY_CONSTRUCTION_AND_CHECKED",
            "selector_tie_break": "ORIGINAL_UNCHANGED_AFTER_UNIVERSE_REDUCTION",
            "strategy_rerun": "NOT_RUN",
            "window_sweep": "NOT_RUN",
        },
        "lineage_resolution": {
            "candidate_binding_count": original_candidate_total,
            "resolution_authority_counts": {
                key: resolution_counts[key] for key in sorted(resolution_counts)
            },
            "unresolved_candidate_binding_count": 0,
        },
        "primary_metric": {
            "id": PRIMARY_METRIC_ID,
            "sample_unit": "DISTINCT_TARGET_DRAW",
            "success_definition": "AT_LEAST_ONE_NATIVE_TICKET_WINS_AN_OFFICIAL_PRIZE",
        },
        "required_answers": required_answers,
        "schema_version": SCHEMA_VERSION,
        "source_authorities": {
            "candidate_source_blobs": [
                source_artifacts[key].identity_payload() for key in sorted(source_artifacts)
            ],
            "frozen_json_artifacts": [
                artifacts[key].identity_payload() for key in sorted(artifacts)
            ],
            "original_selector_runner": load_frozen_artifact(
                ORIGINAL_SELECTOR_RUNNER_ARTIFACT, REPOSITORY_ROOT
            ).identity_payload(),
            "per_target_replay_authorities": list(replay_authorities),
        },
        "study_id": STUDY_ID,
        "task_id": TASK_ID,
        "universe_summary": {
            "cell_count": len(cell_payloads),
            "deduplicated_callable_count_sum_across_cells": dedup_callable_total,
            "experiment_count": len(experiment_payloads),
            "original_candidate_count_sum_across_cells": original_candidate_total,
            "removed_sibling_count_sum_across_cells": removed_total,
        },
        "windows": {window_label: window for window_label, _source, window in WINDOWS},
    }


def _metric_exact(value: object) -> str:
    if value is None:
        return "—"
    metric = _as_mapping(value, context="report.metric")
    rate = _as_mapping(metric.get("rate"), context="report.metric.rate")
    return _as_string(rate.get("exact"), context="report.metric.rate.exact")


def _delta_exact(value: object) -> str:
    if value is None:
        return "—"
    return _as_string(
        _as_mapping(value, context="report.delta").get("exact"),
        context="report.delta.exact",
    )


def render_report(payload: Mapping[str, Any]) -> str:
    """Render the complete deterministic Markdown research report."""

    cells = cast(list[dict[str, Any]], payload["cells"])
    summary = _as_mapping(payload["universe_summary"], context="universe_summary")
    lines = [
        "# Callable-family dedup causal selector pilot R1",
        "",
        "This bounded exploratory pilot compares the sealed original rolling selector, a "
        "callable-family-deduplicated rolling selector, and a frozen baseline selected from "
        "the same deduplicated universe. It is historical evidence only.",
        "",
        "## Fixed rule and authority boundary",
        "",
        "- Grouping scope: source authority x lottery x native ticket-count cell x callable.",
        "- Representative: lexicographically smallest complete `(source_authority_id, "
        "lottery_id, strategy_id, strategy_version)` identity.",
        "- Representative selection uses no historical score, prize, target, future, or "
        "rolling-performance input.",
        "- Windows are fixed at W50, W300, and W750; selection is strictly before target.",
        "- Original, dedup rolling, and dedup frozen use identical target sets.",
        "",
        "## Callable-family accounting",
        "",
        f"- Original candidate count summed across cells: "
        f"{summary['original_candidate_count_sum_across_cells']}",
        f"- Deduplicated callable count summed across cells: "
        f"{summary['deduplicated_callable_count_sum_across_cells']}",
        f"- Removed sibling count summed across cells: "
        f"{summary['removed_sibling_count_sum_across_cells']}",
        "",
        "## Complete lottery x K x window results",
        "",
        "| Lottery | K | Window | Status | Original candidates | Dedup callables | Removed | "
        "Targets | Original rolling | Dedup rolling | Dedup frozen | Dedup-original | "
        "Dedup-frozen | Original switches | Dedup switches | First | Last | Exclusion |",
        "|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|",
    ]
    all_experiments: list[dict[str, Any]] = []
    for cell in cells:
        experiments = cast(list[dict[str, Any]], cell["experiments"])
        all_experiments.extend(experiments)
        for experiment in experiments:
            exclusions = _as_mapping(experiment["exclusions"], context="exclusions")
            switches = _as_mapping(experiment["switch_counts"], context="switch_counts")
            exclusion = exclusions.get("dedup_exclusion_reason") or "—"
            lines.append(
                "| {lottery} | {k} | {window} | {status} | {original_count} | "
                "{dedup_count} | {removed} | {targets} | {original_metric} | "
                "{dedup_metric} | {frozen_metric} | {dedup_original} | {dedup_frozen} | "
                "{original_switches} | {dedup_switches} | {first} | {last} | {exclusion} |".format(
                    lottery=experiment["lottery_id"],
                    k=experiment["k"],
                    window=experiment["window_label"],
                    status=exclusions["dedup_status"],
                    original_count=experiment["original_candidate_count"],
                    dedup_count=experiment["deduplicated_callable_count"],
                    removed=experiment["removed_sibling_count"],
                    targets=experiment["eligible_target_count"],
                    original_metric=_metric_exact(experiment["original_rolling_metric"]),
                    dedup_metric=_metric_exact(experiment["dedup_rolling_metric"]),
                    frozen_metric=_metric_exact(experiment["dedup_frozen_metric"]),
                    dedup_original=_delta_exact(experiment["dedup_vs_original_exact_delta"]),
                    dedup_frozen=_delta_exact(
                        experiment["dedup_rolling_vs_dedup_frozen_exact_delta"]
                    ),
                    original_switches=switches["original_rolling"],
                    dedup_switches=switches["dedup_rolling"],
                    first=experiment["first_target"] or "—",
                    last=experiment["last_target"] or "—",
                    exclusion=exclusion,
                )
            )

    lines.extend(["", "## Required descriptive answers", ""])
    for index, item in enumerate(cast(list[dict[str, Any]], payload["required_answers"]), start=1):
        lines.extend(
            [
                f"### {index}. {item['question']}",
                "",
                f"Answer: `{item['answer']}`",
                "",
                "```json",
                json.dumps(item["evidence"], ensure_ascii=False, indent=2, sort_keys=True),
                "```",
                "",
            ]
        )

    lines.extend(["## Selection-frequency and family detail", ""])
    for cell in cells:
        lines.extend(
            [
                f"### {cell['cell_id']}",
                "",
                f"Original candidates: {cell['original_candidate_count']}; dedup callables: "
                f"{cell['deduplicated_callable_count']}; removed siblings: "
                f"{cell['removed_sibling_count']}.",
                "",
            ]
        )
        for experiment in cast(list[dict[str, Any]], cell["experiments"]):
            frequencies = _as_mapping(
                experiment["selection_frequencies"], context="selection_frequencies"
            )
            lines.extend(
                [
                    f"- {experiment['window_label']} original strategies: "
                    f"`{json.dumps(frequencies['original_rolling_by_strategy'], sort_keys=True)}`",
                    f"- {experiment['window_label']} original callables: "
                    f"`{json.dumps(frequencies['original_rolling_by_callable'], sort_keys=True)}`",
                    f"- {experiment['window_label']} dedup strategies: "
                    f"`{json.dumps(frequencies['dedup_rolling_by_strategy'], sort_keys=True)}`",
                    f"- {experiment['window_label']} dedup callables: "
                    f"`{json.dumps(frequencies['dedup_rolling_by_callable'], sort_keys=True)}`",
                ]
            )
        removed_families = [
            family
            for family in cast(list[dict[str, Any]], cell["callable_families"])
            if int(family["removed_sibling_count"]) > 0
        ]
        lines.extend(
            [
                "- Reduced callable families: "
                f"`{json.dumps(removed_families, ensure_ascii=False, sort_keys=True)}`",
                "",
            ]
        )

    lines.extend(
        [
            "## Scientific and runtime boundaries",
            "",
            "The comparisons are exact historical descriptions of the frozen authorities. "
            "No future-performance, profitability, significance, or promotion conclusion is "
            "authorized.",
            "",
            "```text",
            "PREDICTIVE_ADVANTAGE = NOT ESTABLISHED",
            "PROFITABILITY = NOT ESTABLISHED",
            "REFERENCE_PROMOTION = NOT AUTHORIZED",
            "RUNTIME_PROMOTION = NOT AUTHORIZED",
            "K2_R2 = NOT RUN",
            "P638_ZONE2 = NOT RUN",
            "SECOND_EXCHANGE = NOT RUN",
            "STRATEGY_RERUN = NOT RUN",
            "DB_WRITE = NO",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def run_pilot(
    repository_root: Path = REPOSITORY_ROOT,
) -> tuple[dict[str, Any], bytes, bytes]:
    """Execute the read-only pilot and return deterministic JSON/report bytes."""

    root = _verify_repository(repository_root)
    artifacts = load_frozen_authorities(root)
    source_artifacts = _load_static_source_artifacts(root)
    runner = cast(Any, load_original_runner(root))
    authority_paths = runner.AuthorityPaths(
        b649_directory=DEFAULT_B649_AUTHORITY_DIRECTORY,
        t539_database=DEFAULT_T539_AUTHORITY,
        p638_replay_database=DEFAULT_P638_REPLAY_AUTHORITY,
        p638_ranking_database=DEFAULT_P638_RANKING_AUTHORITY,
    )
    actual_authorities, live_cells = runner.load_authorities(authority_paths)
    selector_payload = artifacts["rolling_selector"].json_payload()
    replay_authorities = _validate_replay_authority_parity(actual_authorities, selector_payload)
    payload = build_result(
        artifacts=artifacts,
        source_artifacts=source_artifacts,
        replay_authorities=replay_authorities,
        live_cells=live_cells,
        runner=runner,
    )
    json_bytes = canonical_json_bytes(payload)
    report_bytes = render_report(payload).encode("utf-8")
    return payload, json_bytes, report_bytes


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-report", type=Path, default=DEFAULT_OUTPUT_REPORT)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    output_json = cast(Path, arguments.output_json)
    output_report = cast(Path, arguments.output_report)
    allowed = {DEFAULT_OUTPUT_JSON.resolve(), DEFAULT_OUTPUT_REPORT.resolve()}
    if output_json.resolve() not in allowed or output_report.resolve() not in allowed:
        raise PilotDataError("OUTPUT_PATH_OUTSIDE_PACKET_ALLOWLIST")
    _payload, json_bytes, report_bytes = run_pilot()
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
                "status": "COMPLETE",
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
