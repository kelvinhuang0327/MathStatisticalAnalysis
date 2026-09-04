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

from lottolab.domain.exact_native_replay import Draw, descriptor_payload
from lottolab.domain.strategies import StrategyDescriptor

EVIDENCE_SCHEMA = "B649_EXACT_NATIVE_TARGET_EVIDENCE_V1"
MANIFEST_SCHEMA = "B649_EXACT_NATIVE_REFRESH_SEALED_MANIFEST_V1"
EVIDENCE_FILENAME = "target_evidence.jsonl"
MANIFEST_FILENAME = "sealed_manifest.json"
METADATA_FILENAME = "metadata.json"

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
    "EVIDENCE_FILENAME",
    "EVIDENCE_SCHEMA",
    "MANIFEST_FILENAME",
    "MANIFEST_SCHEMA",
    "METADATA_FILENAME",
    "build_catalog_universe_payload",
    "build_sealed_manifest",
    "canonical_json_bytes",
    "history_fingerprint",
    "sha256_bytes",
    "sha256_file",
    "write_json_file",
]
