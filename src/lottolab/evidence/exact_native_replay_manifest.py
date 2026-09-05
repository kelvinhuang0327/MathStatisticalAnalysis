"""Hashing, canonical-JSON bytes, and manifest shaping for the exact-native
BIG_LOTTO replay universe.

Owns content hashing for this replay family, per the established evidence-
layer rule (see :mod:`lottolab.domain.replay_predictions`): "the evidence
layer may depend on domain; domain must never depend on evidence." This
module deliberately does not use :mod:`lottolab.evidence.canonical_json`'s
LCJ-1 dialect -- LCJ-1 forbids JSON ``null``, but the pinned
``B649_EXACT_NATIVE_TARGET_EVIDENCE_V1`` row schema uses ``null`` throughout
(every ineligible/failed replay cell). Byte-identical reproduction of the
existing donor evidence stream requires this schema's own plain dialect
(compact, sorted keys, ``null`` allowed), not LCJ-1.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import cast

from lottolab.domain.exact_native_replay import Draw, descriptor_payload
from lottolab.domain.strategies import StrategyDescriptor

EVIDENCE_SCHEMA = "B649_EXACT_NATIVE_TARGET_EVIDENCE_V1"
MANIFEST_SCHEMA = "B649_EXACT_NATIVE_REFRESH_SEALED_MANIFEST_V1"
AUTHORITY_SCHEMA = "B649_EXACT_NATIVE_REPLAY_AUTHORITY_V1"
EVIDENCE_FILENAME = "target_evidence.jsonl"
MANIFEST_FILENAME = "sealed_manifest.json"
METADATA_FILENAME = "metadata.json"
AUTHORITY_FILENAME = "replay_authority.json"

_CHUNK_SIZE = 1024 * 1024


def canonical_json_bytes(value: object) -> bytes:
    """Compact, sorted-key JSON bytes plus one trailing LF.

    Every fingerprint in this replay family (``causal_history_fingerprint``,
    catalog/universe fingerprints) hashes this exact byte form -- trailing LF
    included -- so this helper must stay the single place that shape is
    produced.
    """

    return (
        json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n"
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(_CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json_file(path: Path, value: object) -> None:
    path.write_bytes(canonical_json_bytes(value))


def history_fingerprint(history: Sequence[Draw]) -> str:
    """SHA-256 over the causal history's canonical JSON (LF included)."""

    payload = [
        {
            "draw_date": draw.draw_date.isoformat(),
            "draw_number": draw.draw_number,
            "main_numbers": list(draw.main_numbers),
            "special_number": draw.special_number,
        }
        for draw in history
    ]
    return sha256_bytes(canonical_json_bytes(payload))


def build_catalog_universe_payload(
    *,
    production_catalog_count: int,
    all_biglotto_descriptors: Sequence[StrategyDescriptor],
    exact_native_by_count: Mapping[int, Sequence[StrategyDescriptor]],
) -> dict[str, object]:
    """Sealed-manifest ``catalog`` section: fingerprints over the frozen universe."""

    all_payload = [descriptor_payload(descriptor) for descriptor in all_biglotto_descriptors]
    universe_payload = {
        f"k{count}": [descriptor_payload(descriptor) for descriptor in descriptors]
        for count, descriptors in exact_native_by_count.items()
    }
    payload: dict[str, object] = {
        "production_catalog_count": production_catalog_count,
        "biglotto_descriptor_count": len(all_biglotto_descriptors),
        "catalog_fingerprint": sha256_bytes(canonical_json_bytes(all_payload)),
        "intersection": [],
        "strategies": universe_payload,
    }
    for count, descriptors in exact_native_by_count.items():
        payload[f"k{count}_count"] = len(descriptors)
        payload[f"k{count}_universe_fingerprint"] = sha256_bytes(
            canonical_json_bytes(universe_payload[f"k{count}"])
        )
    return payload


def build_replay_authority(
    *,
    source: Mapping[str, object],
    ordered_binding_identities: Sequence[Mapping[str, object]],
    binding_count: int,
    run_config: Mapping[str, object],
    draw_authority_identity: Mapping[str, object],
) -> dict[str, object]:
    """Freeze the load-bearing authority a replay root's evidence was produced under.

    Covers exactly the minimum fields a safe resume must re-verify: source
    identity, the ordered strategy-binding universe (identity *and* count, so
    a same-count swap is distinguishable from an unchanged universe), the
    game/ticket/window/cutoff/target-range configuration, the draw-authority
    content identity, and the schema this artifact and its evidence rows obey.
    """

    return {
        "schema_version": AUTHORITY_SCHEMA,
        "evidence_schema_version": EVIDENCE_SCHEMA,
        "source": dict(source),
        "binding_identity": {
            "binding_count": binding_count,
            "ordered_binding_identities": [dict(item) for item in ordered_binding_identities],
        },
        "run_config": dict(run_config),
        "draw_authority_identity": dict(draw_authority_identity),
    }


_MISSING = "__REPLAY_AUTHORITY_FIELD_MISSING__"


def diff_replay_authority(
    frozen: Mapping[str, object], current: Mapping[str, object]
) -> dict[str, dict[str, object]]:
    """Field-level differences between a frozen and a currently-resolved authority.

    Empty when the two are identical. Every differing leaf is reported under
    its dotted path as ``{"frozen": ..., "current": ...}``; a key present on
    only one side reports the absent side as :data:`_MISSING`. Callers must
    normalize both arguments through a canonical JSON round-trip first (e.g.
    ``json.loads(canonical_json_bytes(value))``) so tuples and dicts compare
    the same way plain-JSON-loaded data would.
    """

    differences: dict[str, dict[str, object]] = {}
    _diff_into(frozen, current, "", differences)
    return differences


def _diff_into(
    frozen: object, current: object, path: str, out: dict[str, dict[str, object]]
) -> None:
    if isinstance(frozen, Mapping) and isinstance(current, Mapping):
        frozen_map = cast(Mapping[str, object], frozen)
        current_map = cast(Mapping[str, object], current)
        for key in sorted(set(frozen_map) | set(current_map)):
            child_path = f"{path}.{key}" if path else key
            if key not in frozen_map:
                out[child_path] = {"frozen": _MISSING, "current": current_map[key]}
            elif key not in current_map:
                out[child_path] = {"frozen": frozen_map[key], "current": _MISSING}
            else:
                _diff_into(frozen_map[key], current_map[key], child_path, out)
        return
    if isinstance(frozen, list) and isinstance(current, list):
        frozen_list = cast(list[object], frozen)
        current_list = cast(list[object], current)
        if len(frozen_list) != len(current_list):
            out[path or "$"] = {"frozen": frozen_list, "current": current_list}
            return
        for index, (frozen_item, current_item) in enumerate(
            zip(frozen_list, current_list, strict=True)
        ):
            _diff_into(frozen_item, current_item, f"{path}[{index}]", out)
        return
    if frozen != current:
        out[path or "$"] = {"frozen": frozen, "current": current}


def build_sealed_manifest(
    *,
    run_id: str,
    source: Mapping[str, object],
    catalog: Mapping[str, object],
    draw_authority: Mapping[str, object],
    max_visible_draw: str,
    later_draws_present_in_authority: bool,
    visible_draw_count: int,
    target_windows: Mapping[str, object],
    shard_count: int,
    shard_boundaries: Sequence[Mapping[str, object]],
    evidence_sha256: str,
    evidence_byte_size: int,
    evidence_record_count: int,
    evidence_status_counts: Mapping[str, int],
    universe: Mapping[str, object],
) -> dict[str, object]:
    """Assemble the sealed manifest for one exact-native replay run."""

    return {
        "schema_version": MANIFEST_SCHEMA,
        "run_id": run_id,
        "source": dict(source),
        "catalog": dict(catalog),
        "draw_authority": dict(draw_authority),
        "max_visible_draw": max_visible_draw,
        "later_draws_present_in_authority": later_draws_present_in_authority,
        "visible_draw_count": visible_draw_count,
        "target_windows": dict(target_windows),
        "execution_contract": {
            "lottery_type": "BIG_LOTTO",
            "history_order": "ASCENDING_DRAW_DATE_THEN_NUMERIC_DRAW_NUMBER",
            "target_outcome_excluded": True,
            "causal_rule": "all history rows have sort_key strictly less than target sort_key",
            "portfolio_contract": (
                "exact descriptor native_ticket_count; no truncation, extension, "
                "duplication, or padding"
            ),
            "primary_metric": "OFFICIAL_ANY_PRIZE at distinct target-draw level",
            "ranking_tie_break": [
                "OFFICIAL_ANY_PRIZE_DESC",
                "CANONICAL_OFFICIAL_RANDOM_BASELINE_DELTA_DESC",
                "COVERAGE_DESC",
                "STRATEGY_ID_ASC",
            ],
            "deterministic_replay": "native adapter-owned seed/state rules recorded per target row",
            "parallel_sharding": {
                "shard_count": shard_count,
                "sharding_dimension": "OUTER_TARGET_INDEX_RANGE",
                "inner_binding_order_preserved": True,
                "shard_boundaries": [dict(boundary) for boundary in shard_boundaries],
            },
        },
        "evidence": {
            "file": EVIDENCE_FILENAME,
            "schema_version": EVIDENCE_SCHEMA,
            "writer_closed_before_seal": True,
            "sha256": evidence_sha256,
            "byte_size": evidence_byte_size,
            "record_count": evidence_record_count,
            "status_counts": dict(sorted(evidence_status_counts.items())),
        },
        "universe": dict(universe),
        "seal": {
            "sealed_before_ranking": True,
            "ranking_reopened_read_only": True,
            "production_research_store_promotion": "NOT_RUN",
        },
    }


__all__ = [
    "AUTHORITY_FILENAME",
    "AUTHORITY_SCHEMA",
    "EVIDENCE_FILENAME",
    "EVIDENCE_SCHEMA",
    "MANIFEST_FILENAME",
    "MANIFEST_SCHEMA",
    "METADATA_FILENAME",
    "build_catalog_universe_payload",
    "build_replay_authority",
    "build_sealed_manifest",
    "canonical_json_bytes",
    "diff_replay_authority",
    "history_fingerprint",
    "sha256_bytes",
    "sha256_file",
    "write_json_file",
]
