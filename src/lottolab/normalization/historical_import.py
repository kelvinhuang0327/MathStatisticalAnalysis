"""BLHQ R1: strict raw-JSON verification and normalization for historical results.

``verify_and_normalize_historical_import`` is the only entry point. It returns a
closed :class:`HistoricalImportVerificationResult`; a normalized
:class:`~lottolab.domain.historical_results.HistoricalRunImport` is present only
when the outcome is ``IMPORT_PASS``. Everything here is pure and deterministic:
no filesystem, no database, no clock, no randomness.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Annotated, Any, Literal, cast

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, ValidationError, model_validator

from lottolab.domain.historical_results import (
    HistoricalDatasetDescriptor,
    HistoricalDrawSnapshot,
    HistoricalGovernanceStatus,
    HistoricalIdentityKind,
    HistoricalLotteryType,
    HistoricalPortfolio,
    HistoricalRunImport,
    HistoricalSourceDescriptor,
    HistoricalSourceKind,
    HistoricalStrategyDescriptor,
    HistoricalTicket,
)
from lottolab.evidence import canonical_json

CONTRACT_VERSION = "1.0.0"
PORTFOLIO_TICKET_COUNT = 20
_SYNTHETIC_PREFIX = "SYNTHETIC_"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_GIT_OID = re.compile(r"^[0-9a-f]{40}$")
_CLOSED = ConfigDict(extra="forbid", frozen=True)


class HistoricalImportOutcome(StrEnum):
    """Closed verification outcomes. Superset of the task's required minimum."""

    IMPORT_PASS = "IMPORT_PASS"
    IMPORT_INPUT_UNVERIFIED = "IMPORT_INPUT_UNVERIFIED"
    IMPORT_MANIFEST_HASH_MISMATCH = "IMPORT_MANIFEST_HASH_MISMATCH"
    IMPORT_IDENTITY_HASH_MISMATCH = "IMPORT_IDENTITY_HASH_MISMATCH"
    IMPORT_CAUSAL_VIOLATION = "IMPORT_CAUSAL_VIOLATION"
    IMPORT_TICKET_SHAPE_VIOLATION = "IMPORT_TICKET_SHAPE_VIOLATION"
    IMPORT_HIT_MISMATCH = "IMPORT_HIT_MISMATCH"
    IMPORT_ALIAS_TARGET_ABSENT = "IMPORT_ALIAS_TARGET_ABSENT"
    IMPORT_HASH_MISMATCH = "IMPORT_HASH_MISMATCH"
    IMPORT_STRATEGY_REFERENCE_ABSENT = "IMPORT_STRATEGY_REFERENCE_ABSENT"


@dataclass(frozen=True, slots=True)
class HistoricalImportFinding:
    reason_code: str
    field: str
    message: str


@dataclass(frozen=True, slots=True)
class HistoricalImportVerificationResult:
    """A closed result: PASS carries exactly one normalized import, nothing else."""

    outcome: HistoricalImportOutcome
    findings: tuple[HistoricalImportFinding, ...] = ()
    normalized_import: HistoricalRunImport | None = None

    def __post_init__(self) -> None:
        if self.outcome is HistoricalImportOutcome.IMPORT_PASS:
            if self.findings or self.normalized_import is None:
                raise ValueError("IMPORT_PASS requires a normalized import and no findings")
        elif not self.findings or self.normalized_import is not None:
            raise ValueError("a rejected outcome requires findings and no normalized import")


def _check_sha256(value: str) -> str:
    if _SHA256.fullmatch(value) is None:
        raise ValueError("must be a 64-character lowercase hexadecimal SHA-256 digest")
    return value


def _check_git_oid(value: str) -> str:
    if _GIT_OID.fullmatch(value) is None:
        raise ValueError("must be a 40-character lowercase hexadecimal Git object id")
    return value


Sha256Hex = Annotated[str, AfterValidator(_check_sha256)]
GitOidHex = Annotated[str, AfterValidator(_check_git_oid)]


class _SourceWire(BaseModel):
    model_config = _CLOSED

    source_kind: HistoricalSourceKind
    source_repository: str = Field(min_length=1)
    source_commit_oid: GitOidHex
    source_artifact_sha256: Sha256Hex
    legacy_run_id: str | None = None


class _DatasetWire(BaseModel):
    model_config = _CLOSED

    dataset_identity: str = Field(min_length=1)
    dataset_sha256: Sha256Hex
    lottery_type: HistoricalLotteryType


class _StrategyDescriptorWire(BaseModel):
    model_config = _CLOSED

    strategy_id: str = Field(min_length=1)
    effective_strategy_id: str = Field(min_length=1)
    strategy_version: str = Field(min_length=1)
    replicate: int = Field(ge=1)
    identity_kind: HistoricalIdentityKind
    governance_status: HistoricalGovernanceStatus
    alias_of_strategy_id: str | None = None
    equivalence_group: str | None = None
    nested_prefix_supported: bool
    descriptor_sha256: Sha256Hex

    @model_validator(mode="after")
    def _check_synthetic_prefix(self) -> _StrategyDescriptorWire:
        is_synthetic_id = self.strategy_id.startswith(_SYNTHETIC_PREFIX)
        is_synthetic_kind = self.identity_kind is HistoricalIdentityKind.SYNTHETIC_TEST_ONLY
        if is_synthetic_kind and not is_synthetic_id:
            raise ValueError("a SYNTHETIC_TEST_ONLY strategy_id must start with SYNTHETIC_")
        if not is_synthetic_kind and is_synthetic_id:
            raise ValueError("a non-synthetic strategy_id must not use the SYNTHETIC_ prefix")
        return self


class _DrawSnapshotWire(BaseModel):
    model_config = _CLOSED

    draw_number: int = Field(ge=1)
    draw_date: str = Field(min_length=1)
    main_numbers: tuple[int, ...] = Field(min_length=1)
    special_numbers: tuple[int, ...]
    draw_sha256: Sha256Hex


class _TicketWire(BaseModel):
    model_config = _CLOSED

    portfolio_position: int = Field(ge=1, le=PORTFOLIO_TICKET_COUNT)
    main_numbers: tuple[int, ...] = Field(min_length=1)
    special_numbers: tuple[int, ...]
    main_hit_count: int = Field(ge=0)
    special_hit: bool
    ticket_sha256: Sha256Hex
    legacy_row_id: str | None = None
    legacy_storage_bet_index: int | None = None


class _PortfolioWire(BaseModel):
    model_config = _CLOSED

    strategy_id: str = Field(min_length=1)
    strategy_version: str = Field(min_length=1)
    replicate: int = Field(ge=1)
    target_draw_number: int = Field(ge=1)
    cutoff_draw_number: int = Field(ge=1)
    constructor_identifier: str = Field(min_length=1)
    source_record_locator: str | None = None
    tickets: tuple[_TicketWire, ...] = Field(min_length=1)
    portfolio_sha256: Sha256Hex
    prefix10_sha256: Sha256Hex
    prefix15_sha256: Sha256Hex


class HistoricalResultImportV1(BaseModel):
    """The strict wire contract: closed shape, no extra fields, self-describing hashes."""

    model_config = _CLOSED

    contract_version: Literal["1.0.0"]
    generated_at: str = Field(min_length=1)
    manifest_sha256: Sha256Hex
    import_identity_sha256: Sha256Hex
    source: _SourceWire
    dataset: _DatasetWire
    strategy_descriptors: tuple[_StrategyDescriptorWire, ...] = Field(min_length=1)
    draw_snapshots: tuple[_DrawSnapshotWire, ...] = Field(min_length=1)
    portfolios: tuple[_PortfolioWire, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _check_no_duplicate_identities(self) -> HistoricalResultImportV1:
        strategy_keys = [
            (d.strategy_id, d.strategy_version, d.replicate) for d in self.strategy_descriptors
        ]
        if len(strategy_keys) != len(set(strategy_keys)):
            raise ValueError("strategy_descriptors contains a duplicate (id, version, replicate)")
        draw_numbers = [d.draw_number for d in self.draw_snapshots]
        if len(draw_numbers) != len(set(draw_numbers)):
            raise ValueError("draw_snapshots contains a duplicate draw_number")
        return self


def _reject(
    outcome: HistoricalImportOutcome, *, field: str, message: str
) -> HistoricalImportVerificationResult:
    finding = HistoricalImportFinding(reason_code=outcome.value, field=field, message=message)
    return HistoricalImportVerificationResult(outcome=outcome, findings=(finding,))


def _compute_descriptor_sha256(descriptor: _StrategyDescriptorWire) -> str:
    payload: dict[str, Any] = {
        "strategy_id": descriptor.strategy_id,
        "effective_strategy_id": descriptor.effective_strategy_id,
        "strategy_version": descriptor.strategy_version,
        "replicate": descriptor.replicate,
        "identity_kind": descriptor.identity_kind.value,
        "governance_status": descriptor.governance_status.value,
        "nested_prefix_supported": descriptor.nested_prefix_supported,
    }
    if descriptor.alias_of_strategy_id is not None:
        payload["alias_of_strategy_id"] = descriptor.alias_of_strategy_id
    if descriptor.equivalence_group is not None:
        payload["equivalence_group"] = descriptor.equivalence_group
    return canonical_json.sha256_hex(canonical_json.canonical_bytes(payload))


def _compute_draw_sha256(draw: _DrawSnapshotWire) -> str:
    payload = {
        "draw_number": draw.draw_number,
        "draw_date": draw.draw_date,
        "main_numbers": list(draw.main_numbers),
        "special_numbers": list(draw.special_numbers),
    }
    return canonical_json.sha256_hex(canonical_json.canonical_bytes(payload))


def _compute_ticket_sha256(ticket: _TicketWire) -> str:
    payload = {
        "portfolio_position": ticket.portfolio_position,
        "main_numbers": sorted(ticket.main_numbers),
        "special_numbers": sorted(ticket.special_numbers),
        "main_hit_count": ticket.main_hit_count,
        "special_hit": ticket.special_hit,
    }
    return canonical_json.sha256_hex(canonical_json.canonical_bytes(payload))


def _compute_portfolio_sha256(portfolio: _PortfolioWire, ticket_hashes: list[str]) -> str:
    payload = {
        "strategy_id": portfolio.strategy_id,
        "strategy_version": portfolio.strategy_version,
        "replicate": portfolio.replicate,
        "target_draw_number": portfolio.target_draw_number,
        "cutoff_draw_number": portfolio.cutoff_draw_number,
        "constructor_identifier": portfolio.constructor_identifier,
        "ticket_hashes": ticket_hashes,
    }
    return canonical_json.sha256_hex(canonical_json.canonical_bytes(payload))


def _compute_prefix_sha256(ticket_hashes: list[str]) -> str:
    payload = {"ticket_hashes": ticket_hashes}
    return canonical_json.sha256_hex(canonical_json.canonical_bytes(payload))


def _compute_import_identity_sha256(envelope: HistoricalResultImportV1) -> str:
    strategy_identities = sorted(d.descriptor_sha256 for d in envelope.strategy_descriptors)
    target_numbers = sorted({p.target_draw_number for p in envelope.portfolios})
    pairs = sorted({(p.target_draw_number, p.cutoff_draw_number) for p in envelope.portfolios})
    portfolio_hashes = sorted(p.portfolio_sha256 for p in envelope.portfolios)
    payload = {
        "contract_version": envelope.contract_version,
        "source_kind": envelope.source.source_kind.value,
        "source_repository": envelope.source.source_repository,
        "source_commit_oid": envelope.source.source_commit_oid,
        "source_artifact_sha256": envelope.source.source_artifact_sha256,
        "dataset_identity": envelope.dataset.dataset_identity,
        "dataset_sha256": envelope.dataset.dataset_sha256,
        "strategy_descriptor_identities": strategy_identities,
        "target_draw_numbers": target_numbers,
        "target_cutoff_pairs": [[target, cutoff] for target, cutoff in pairs],
        "portfolio_payload_hashes": portfolio_hashes,
    }
    return canonical_json.sha256_hex(canonical_json.canonical_bytes(payload))


def _build_domain_import(envelope: HistoricalResultImportV1) -> HistoricalRunImport:
    source = HistoricalSourceDescriptor(
        source_kind=envelope.source.source_kind,
        source_repository=envelope.source.source_repository,
        source_commit_oid=envelope.source.source_commit_oid,
        source_artifact_sha256=envelope.source.source_artifact_sha256,
        legacy_run_id=envelope.source.legacy_run_id,
    )
    dataset = HistoricalDatasetDescriptor(
        dataset_identity=envelope.dataset.dataset_identity,
        dataset_sha256=envelope.dataset.dataset_sha256,
        lottery_type=envelope.dataset.lottery_type,
    )
    strategy_descriptors = tuple(
        HistoricalStrategyDescriptor(
            strategy_id=d.strategy_id,
            effective_strategy_id=d.effective_strategy_id,
            strategy_version=d.strategy_version,
            replicate=d.replicate,
            identity_kind=d.identity_kind,
            governance_status=d.governance_status,
            alias_of_strategy_id=d.alias_of_strategy_id,
            equivalence_group=d.equivalence_group,
            nested_prefix_supported=d.nested_prefix_supported,
            descriptor_sha256=d.descriptor_sha256,
        )
        for d in envelope.strategy_descriptors
    )
    draw_snapshots = tuple(
        HistoricalDrawSnapshot(
            draw_number=d.draw_number,
            draw_date=d.draw_date,
            main_numbers=d.main_numbers,
            special_numbers=d.special_numbers,
            draw_sha256=d.draw_sha256,
        )
        for d in envelope.draw_snapshots
    )
    portfolios = tuple(
        HistoricalPortfolio(
            strategy_id=p.strategy_id,
            strategy_version=p.strategy_version,
            replicate=p.replicate,
            target_draw_number=p.target_draw_number,
            cutoff_draw_number=p.cutoff_draw_number,
            constructor_identifier=p.constructor_identifier,
            source_record_locator=p.source_record_locator,
            tickets=tuple(
                HistoricalTicket(
                    portfolio_position=t.portfolio_position,
                    main_numbers=t.main_numbers,
                    special_numbers=t.special_numbers,
                    main_hit_count=t.main_hit_count,
                    special_hit=t.special_hit,
                    ticket_sha256=t.ticket_sha256,
                    legacy_row_id=t.legacy_row_id,
                    legacy_storage_bet_index=t.legacy_storage_bet_index,
                )
                for t in p.tickets
            ),
            portfolio_sha256=p.portfolio_sha256,
            prefix10_sha256=p.prefix10_sha256,
            prefix15_sha256=p.prefix15_sha256,
        )
        for p in envelope.portfolios
    )
    return HistoricalRunImport(
        contract_version=envelope.contract_version,
        generated_at=envelope.generated_at,
        manifest_sha256=envelope.manifest_sha256,
        import_identity_sha256=envelope.import_identity_sha256,
        source=source,
        dataset=dataset,
        strategy_descriptors=strategy_descriptors,
        draw_snapshots=draw_snapshots,
        portfolios=portfolios,
    )


def verify_and_normalize_historical_import(raw: bytes) -> HistoricalImportVerificationResult:
    """Verify ``raw`` against ``HistoricalResultImportV1`` and normalize it.

    Fails closed at the first violation found, in this fixed order: well-typed
    envelope shape, import-identity hash, manifest hash, alias-target
    resolution, independent strategy-descriptor content hash, independent
    draw-snapshot content hash, then per-portfolio causal/ticket-shape/hit/hash
    checks. Descriptor and draw hashes are re-derived from their own content
    fields (never trusted from the declared value) so a stale child hash
    cannot ride through on a self-consistent ``import_identity_sha256`` /
    ``manifest_sha256`` pair; they run after alias-target resolution so an
    unrelated content-hash defect never masks a still-observable
    alias-target-absent violation.
    """

    if type(raw) is not bytes:
        return _reject(
            HistoricalImportOutcome.IMPORT_INPUT_UNVERIFIED,
            field="root",
            message="raw input must be bytes",
        )
    try:
        parsed = canonical_json.loads_canonical(raw)
    except canonical_json.CanonicalizationError as exc:
        return _reject(
            HistoricalImportOutcome.IMPORT_INPUT_UNVERIFIED, field="root", message=str(exc)
        )
    if not isinstance(parsed, dict):
        return _reject(
            HistoricalImportOutcome.IMPORT_INPUT_UNVERIFIED,
            field="root",
            message="the envelope must be a JSON object",
        )
    parsed = cast(dict[str, Any], parsed)
    try:
        envelope = HistoricalResultImportV1.model_validate(parsed)
    except ValidationError as exc:
        return _reject(
            HistoricalImportOutcome.IMPORT_INPUT_UNVERIFIED, field="root", message=str(exc)
        )

    recomputed_identity = _compute_import_identity_sha256(envelope)
    if recomputed_identity != envelope.import_identity_sha256:
        return _reject(
            HistoricalImportOutcome.IMPORT_IDENTITY_HASH_MISMATCH,
            field="import_identity_sha256",
            message="declared import_identity_sha256 does not match independent recomputation",
        )

    recomputed_manifest = canonical_json.self_key_removed_sha256(parsed, "manifest_sha256")
    if recomputed_manifest != envelope.manifest_sha256:
        return _reject(
            HistoricalImportOutcome.IMPORT_MANIFEST_HASH_MISMATCH,
            field="manifest_sha256",
            message="declared manifest_sha256 does not match independent recomputation",
        )

    strategy_ids = {d.strategy_id for d in envelope.strategy_descriptors}
    for descriptor in envelope.strategy_descriptors:
        if (
            descriptor.alias_of_strategy_id is not None
            and descriptor.alias_of_strategy_id not in strategy_ids
        ):
            return _reject(
                HistoricalImportOutcome.IMPORT_ALIAS_TARGET_ABSENT,
                field="strategy_descriptors.alias_of_strategy_id",
                message=f"alias target {descriptor.alias_of_strategy_id!r} is absent",
            )

    for descriptor in envelope.strategy_descriptors:
        recomputed_descriptor_hash = _compute_descriptor_sha256(descriptor)
        if recomputed_descriptor_hash != descriptor.descriptor_sha256:
            return _reject(
                HistoricalImportOutcome.IMPORT_HASH_MISMATCH,
                field="strategy_descriptors.descriptor_sha256",
                message="declared descriptor_sha256 does not match independent recomputation",
            )

    for draw in envelope.draw_snapshots:
        recomputed_draw_hash = _compute_draw_sha256(draw)
        if recomputed_draw_hash != draw.draw_sha256:
            return _reject(
                HistoricalImportOutcome.IMPORT_HASH_MISMATCH,
                field="draw_snapshots.draw_sha256",
                message="declared draw_sha256 does not match independent recomputation",
            )

    strategy_triples = {
        (d.strategy_id, d.strategy_version, d.replicate) for d in envelope.strategy_descriptors
    }
    draws_by_number = {d.draw_number: d for d in envelope.draw_snapshots}

    for portfolio in envelope.portfolios:
        if (portfolio.strategy_id, portfolio.strategy_version, portfolio.replicate) not in (
            strategy_triples
        ):
            return _reject(
                HistoricalImportOutcome.IMPORT_STRATEGY_REFERENCE_ABSENT,
                field="portfolios.strategy_id",
                message="portfolio references a strategy descriptor absent from this manifest",
            )

        target = draws_by_number.get(portfolio.target_draw_number)
        cutoff = draws_by_number.get(portfolio.cutoff_draw_number)
        if (
            target is None
            or cutoff is None
            or portfolio.cutoff_draw_number >= portfolio.target_draw_number
        ):
            return _reject(
                HistoricalImportOutcome.IMPORT_CAUSAL_VIOLATION,
                field="portfolios",
                message="target/cutoff draws must both exist and satisfy cutoff < target",
            )

        tickets = portfolio.tickets
        if len(tickets) != PORTFOLIO_TICKET_COUNT:
            return _reject(
                HistoricalImportOutcome.IMPORT_TICKET_SHAPE_VIOLATION,
                field="portfolios.tickets",
                message=f"a portfolio must contain exactly {PORTFOLIO_TICKET_COUNT} tickets",
            )
        for expected_position, ticket in enumerate(tickets, start=1):
            if ticket.portfolio_position != expected_position:
                return _reject(
                    HistoricalImportOutcome.IMPORT_TICKET_SHAPE_VIOLATION,
                    field="portfolios.tickets.portfolio_position",
                    message="ticket positions must be exactly 1..20 in array order",
                )

        target_main = set(target.main_numbers)
        target_special = set(target.special_numbers)
        for ticket in tickets:
            recomputed_main_hits = len(set(ticket.main_numbers) & target_main)
            recomputed_special_hit = bool(set(ticket.special_numbers) & target_special)
            if (
                recomputed_main_hits != ticket.main_hit_count
                or recomputed_special_hit != ticket.special_hit
            ):
                return _reject(
                    HistoricalImportOutcome.IMPORT_HIT_MISMATCH,
                    field="portfolios.tickets",
                    message="declared hit values do not match recomputation against the target",
                )

        ticket_hashes: list[str] = []
        for ticket in tickets:
            recomputed_ticket_hash = _compute_ticket_sha256(ticket)
            if recomputed_ticket_hash != ticket.ticket_sha256:
                return _reject(
                    HistoricalImportOutcome.IMPORT_HASH_MISMATCH,
                    field="portfolios.tickets.ticket_sha256",
                    message="declared ticket_sha256 does not match independent recomputation",
                )
            ticket_hashes.append(ticket.ticket_sha256)

        recomputed_portfolio_hash = _compute_portfolio_sha256(portfolio, ticket_hashes)
        if recomputed_portfolio_hash != portfolio.portfolio_sha256:
            return _reject(
                HistoricalImportOutcome.IMPORT_HASH_MISMATCH,
                field="portfolios.portfolio_sha256",
                message="declared portfolio_sha256 does not match independent recomputation",
            )
        recomputed_prefix10 = _compute_prefix_sha256(ticket_hashes[:10])
        if recomputed_prefix10 != portfolio.prefix10_sha256:
            return _reject(
                HistoricalImportOutcome.IMPORT_HASH_MISMATCH,
                field="portfolios.prefix10_sha256",
                message="declared prefix10_sha256 does not match independent recomputation",
            )
        recomputed_prefix15 = _compute_prefix_sha256(ticket_hashes[:15])
        if recomputed_prefix15 != portfolio.prefix15_sha256:
            return _reject(
                HistoricalImportOutcome.IMPORT_HASH_MISMATCH,
                field="portfolios.prefix15_sha256",
                message="declared prefix15_sha256 does not match independent recomputation",
            )

    return HistoricalImportVerificationResult(
        outcome=HistoricalImportOutcome.IMPORT_PASS,
        normalized_import=_build_domain_import(envelope),
    )
