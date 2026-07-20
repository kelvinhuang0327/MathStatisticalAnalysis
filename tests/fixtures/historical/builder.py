"""Tiny synthetic ``HistoricalResultImportV1`` envelope builder for BLHQ R1 tests.

Deliberately re-derives the canonical hash *payload shapes* independently of
``lottolab.normalization.historical_import`` (rather than importing its
private helpers) so a shared bug is less likely to hide behind a passing
test. It does reuse ``lottolab.evidence.canonical_json`` — that module is
pre-existing, already-trusted infrastructure the task explicitly requires
every hash to be built on top of.

Two real strategy ids are used only as opaque labels (``source_kind`` is
always ``SYNTHETIC_TEST_ONLY`` for every fixture built here); no adapter is
imported or executed.
"""

from __future__ import annotations

import copy
from typing import Any

from lottolab.evidence.canonical_json import canonical_bytes, self_key_removed_sha256, sha256_hex

CONTRACT_VERSION = "1.0.0"
PORTFOLIO_TICKET_COUNT = 20

TARGET_DRAW_NUMBER = 105
CUTOFF_DRAW_NUMBER = 100
TARGET_MAIN_NUMBERS = (1, 2, 3, 4, 5, 6)
TARGET_SPECIAL_NUMBERS = (7,)
CUTOFF_MAIN_NUMBERS = (30, 31, 32, 33, 34, 35)
CUTOFF_SPECIAL_NUMBERS = (36,)

REAL_STRATEGY_IDS = (
    "biglotto_deviation_2bet",
    "biglotto_social_wisdom_anti_popularity",
)


def _ticket_numbers(position: int) -> tuple[tuple[int, ...], tuple[int, ...]]:
    start = ((position - 1) * 3) % 44 + 1
    main = tuple(start + offset for offset in range(6))
    special_candidate = start + 6
    special = (special_candidate if special_candidate <= 49 else 1,)
    return main, special


def _ticket_sha256(payload_source: dict[str, Any]) -> str:
    payload = {
        "portfolio_position": payload_source["portfolio_position"],
        "main_numbers": sorted(payload_source["main_numbers"]),
        "special_numbers": sorted(payload_source["special_numbers"]),
        "main_hit_count": payload_source["main_hit_count"],
        "special_hit": payload_source["special_hit"],
    }
    return sha256_hex(canonical_bytes(payload))


def build_ticket(
    position: int,
    *,
    target_main: tuple[int, ...] = TARGET_MAIN_NUMBERS,
    target_special: tuple[int, ...] = TARGET_SPECIAL_NUMBERS,
) -> dict[str, Any]:
    main, special = _ticket_numbers(position)
    hits = len(set(main) & set(target_main))
    special_hit = bool(set(special) & set(target_special))
    ticket: dict[str, Any] = {
        "portfolio_position": position,
        "main_numbers": list(main),
        "special_numbers": list(special),
        "main_hit_count": hits,
        "special_hit": special_hit,
    }
    ticket["ticket_sha256"] = _ticket_sha256(ticket)
    return ticket


def build_tickets(
    *,
    target_main: tuple[int, ...] = TARGET_MAIN_NUMBERS,
    target_special: tuple[int, ...] = TARGET_SPECIAL_NUMBERS,
) -> list[dict[str, Any]]:
    return [
        build_ticket(position, target_main=target_main, target_special=target_special)
        for position in range(1, PORTFOLIO_TICKET_COUNT + 1)
    ]


def build_portfolio(
    *,
    strategy_id: str,
    strategy_version: str = "v1",
    replicate: int = 1,
    target_draw_number: int = TARGET_DRAW_NUMBER,
    cutoff_draw_number: int = CUTOFF_DRAW_NUMBER,
    constructor_identifier: str = "blhq_r1_synthetic_constructor",
    source_record_locator: str | None = None,
    tickets: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    tickets = build_tickets() if tickets is None else tickets
    ticket_hashes = [ticket["ticket_sha256"] for ticket in tickets]
    portfolio: dict[str, Any] = {
        "strategy_id": strategy_id,
        "strategy_version": strategy_version,
        "replicate": replicate,
        "target_draw_number": target_draw_number,
        "cutoff_draw_number": cutoff_draw_number,
        "constructor_identifier": constructor_identifier,
    }
    if source_record_locator is not None:
        portfolio["source_record_locator"] = source_record_locator
    portfolio["tickets"] = tickets
    portfolio["portfolio_sha256"] = sha256_hex(
        canonical_bytes(
            {
                "strategy_id": strategy_id,
                "strategy_version": strategy_version,
                "replicate": replicate,
                "target_draw_number": target_draw_number,
                "cutoff_draw_number": cutoff_draw_number,
                "constructor_identifier": constructor_identifier,
                "ticket_hashes": ticket_hashes,
            }
        )
    )
    portfolio["prefix10_sha256"] = sha256_hex(
        canonical_bytes({"ticket_hashes": ticket_hashes[:10]})
    )
    portfolio["prefix15_sha256"] = sha256_hex(
        canonical_bytes({"ticket_hashes": ticket_hashes[:15]})
    )
    return portfolio


def build_draw_snapshot(
    *,
    draw_number: int,
    draw_date: str,
    main_numbers: tuple[int, ...],
    special_numbers: tuple[int, ...],
) -> dict[str, Any]:
    draw = {
        "draw_number": draw_number,
        "draw_date": draw_date,
        "main_numbers": list(main_numbers),
        "special_numbers": list(special_numbers),
    }
    draw["draw_sha256"] = sha256_hex(canonical_bytes(draw))
    return draw


def build_strategy_descriptor(
    *,
    strategy_id: str,
    strategy_version: str = "v1",
    replicate: int = 1,
    identity_kind: str = "SYNTHETIC_TEST_ONLY",
    governance_status: str = "UNKNOWN",
    alias_of_strategy_id: str | None = None,
    equivalence_group: str | None = None,
    nested_prefix_supported: bool = False,
    effective_strategy_id: str | None = None,
) -> dict[str, Any]:
    descriptor: dict[str, Any] = {
        "strategy_id": strategy_id,
        "effective_strategy_id": effective_strategy_id or strategy_id,
        "strategy_version": strategy_version,
        "replicate": replicate,
        "identity_kind": identity_kind,
        "governance_status": governance_status,
        "nested_prefix_supported": nested_prefix_supported,
    }
    if alias_of_strategy_id is not None:
        descriptor["alias_of_strategy_id"] = alias_of_strategy_id
    if equivalence_group is not None:
        descriptor["equivalence_group"] = equivalence_group
    descriptor["descriptor_sha256"] = sha256_hex(canonical_bytes(dict(descriptor)))
    return descriptor


def _import_identity_payload(envelope: dict[str, Any]) -> dict[str, Any]:
    strategy_identities = sorted(d["descriptor_sha256"] for d in envelope["strategy_descriptors"])
    target_numbers = sorted({p["target_draw_number"] for p in envelope["portfolios"]})
    pairs = sorted(
        {(p["target_draw_number"], p["cutoff_draw_number"]) for p in envelope["portfolios"]}
    )
    portfolio_hashes = sorted(p["portfolio_sha256"] for p in envelope["portfolios"])
    source = envelope["source"]
    dataset = envelope["dataset"]
    return {
        "contract_version": envelope["contract_version"],
        "source_kind": source["source_kind"],
        "source_repository": source["source_repository"],
        "source_commit_oid": source["source_commit_oid"],
        "source_artifact_sha256": source["source_artifact_sha256"],
        "dataset_identity": dataset["dataset_identity"],
        "dataset_sha256": dataset["dataset_sha256"],
        "strategy_descriptor_identities": strategy_identities,
        "target_draw_numbers": target_numbers,
        "target_cutoff_pairs": [[target, cutoff] for target, cutoff in pairs],
        "portfolio_payload_hashes": portfolio_hashes,
    }


def recompute_envelope_hashes(envelope: dict[str, Any]) -> dict[str, Any]:
    """Recompute ``import_identity_sha256`` and ``manifest_sha256`` from current content.

    Use this after mutating anything *other than* the two hash fields
    themselves, so the mutation is isolated to whichever downstream check it
    is meant to exercise instead of being masked by an incidental top-level
    hash mismatch.
    """

    updated = dict(envelope)
    updated["import_identity_sha256"] = sha256_hex(
        canonical_bytes(_import_identity_payload(updated))
    )
    updated["manifest_sha256"] = self_key_removed_sha256(updated, "manifest_sha256")
    return updated


def build_envelope(
    *,
    strategy_descriptors: list[dict[str, Any]],
    draw_snapshots: list[dict[str, Any]],
    portfolios: list[dict[str, Any]],
    source_kind: str = "SYNTHETIC_TEST_ONLY",
    source_repository: str = "github.com/kelvinhuang0327/MathStatisticalAnalysis",
    source_commit_oid: str = "a" * 40,
    source_artifact_sha256: str = "b" * 64,
    legacy_run_id: str | None = None,
    dataset_identity: str = "blhq_r1_synthetic_dataset",
    dataset_sha256: str = "c" * 64,
    generated_at: str = "2026-07-20T00:00:00.000000Z",
) -> dict[str, Any]:
    source: dict[str, Any] = {
        "source_kind": source_kind,
        "source_repository": source_repository,
        "source_commit_oid": source_commit_oid,
        "source_artifact_sha256": source_artifact_sha256,
    }
    if legacy_run_id is not None:
        source["legacy_run_id"] = legacy_run_id
    dataset = {
        "dataset_identity": dataset_identity,
        "dataset_sha256": dataset_sha256,
        "lottery_type": "BIG_LOTTO",
    }
    envelope: dict[str, Any] = {
        "contract_version": CONTRACT_VERSION,
        "generated_at": generated_at,
        "manifest_sha256": "0" * 64,
        "import_identity_sha256": "0" * 64,
        "source": source,
        "dataset": dataset,
        "strategy_descriptors": strategy_descriptors,
        "draw_snapshots": draw_snapshots,
        "portfolios": portfolios,
    }
    return recompute_envelope_hashes(envelope)


def build_baseline_envelope() -> dict[str, Any]:
    """A full, valid, self-consistent envelope exercising every descriptor kind.

    Two REAL descriptors (opaque strategy-id labels only), a SYNTHETIC_
    descriptor with two replicates, and a SYNTHETIC_ alias pointing at it.
    """

    draw_snapshots = [
        build_draw_snapshot(
            draw_number=CUTOFF_DRAW_NUMBER,
            draw_date="2026-01-01",
            main_numbers=CUTOFF_MAIN_NUMBERS,
            special_numbers=CUTOFF_SPECIAL_NUMBERS,
        ),
        build_draw_snapshot(
            draw_number=TARGET_DRAW_NUMBER,
            draw_date="2026-01-10",
            main_numbers=TARGET_MAIN_NUMBERS,
            special_numbers=TARGET_SPECIAL_NUMBERS,
        ),
    ]
    strategy_descriptors = [
        build_strategy_descriptor(
            strategy_id=REAL_STRATEGY_IDS[0], identity_kind="REAL", governance_status="UNKNOWN"
        ),
        build_strategy_descriptor(
            strategy_id=REAL_STRATEGY_IDS[1], identity_kind="REAL", governance_status="UNKNOWN"
        ),
        build_strategy_descriptor(
            strategy_id="SYNTHETIC_BASE_A",
            replicate=1,
            governance_status="CANDIDATE",
            equivalence_group="synthetic_group_1",
            nested_prefix_supported=True,
        ),
        build_strategy_descriptor(
            strategy_id="SYNTHETIC_BASE_A",
            replicate=2,
            governance_status="CANDIDATE",
            equivalence_group="synthetic_group_1",
            nested_prefix_supported=True,
        ),
        build_strategy_descriptor(
            strategy_id="SYNTHETIC_ALIAS_B",
            alias_of_strategy_id="SYNTHETIC_BASE_A",
            governance_status="CANDIDATE",
        ),
    ]
    portfolios = [
        build_portfolio(strategy_id=REAL_STRATEGY_IDS[0]),
        build_portfolio(strategy_id=REAL_STRATEGY_IDS[1]),
        build_portfolio(strategy_id="SYNTHETIC_BASE_A", replicate=1),
        build_portfolio(strategy_id="SYNTHETIC_BASE_A", replicate=2),
        build_portfolio(strategy_id="SYNTHETIC_ALIAS_B"),
    ]
    return build_envelope(
        strategy_descriptors=strategy_descriptors,
        draw_snapshots=draw_snapshots,
        portfolios=portfolios,
    )


def build_small_envelope() -> dict[str, Any]:
    """A structurally different (fewer-strategy) valid envelope for identity-distinctness tests."""

    draw_snapshots = [
        build_draw_snapshot(
            draw_number=CUTOFF_DRAW_NUMBER,
            draw_date="2026-01-01",
            main_numbers=CUTOFF_MAIN_NUMBERS,
            special_numbers=CUTOFF_SPECIAL_NUMBERS,
        ),
        build_draw_snapshot(
            draw_number=TARGET_DRAW_NUMBER,
            draw_date="2026-01-10",
            main_numbers=TARGET_MAIN_NUMBERS,
            special_numbers=TARGET_SPECIAL_NUMBERS,
        ),
    ]
    strategy_descriptors = [
        build_strategy_descriptor(
            strategy_id=REAL_STRATEGY_IDS[0], identity_kind="REAL", governance_status="UNKNOWN"
        ),
    ]
    portfolios = [build_portfolio(strategy_id=REAL_STRATEGY_IDS[0])]
    return build_envelope(
        strategy_descriptors=strategy_descriptors,
        draw_snapshots=draw_snapshots,
        portfolios=portfolios,
    )


def envelope_bytes(envelope: dict[str, Any]) -> bytes:
    return canonical_bytes(envelope)


def deep_copy(envelope: dict[str, Any]) -> dict[str, Any]:
    return copy.deepcopy(envelope)
