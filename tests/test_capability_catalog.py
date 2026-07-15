"""P600A machine-verifiable capability inventory gates."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from tools.validate_capability_catalog import load_document, validate_documents

ROOT = Path(__file__).resolve().parents[1]


def _documents() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    return (
        load_document(ROOT / "docs/capabilities/catalog.yaml"),
        load_document(ROOT / "docs/capabilities/legacy-entrypoints.yaml"),
        load_document(ROOT / "docs/migration/migration-ledger.yaml"),
    )


def test_committed_inventory_passes() -> None:
    assert validate_documents(*_documents()) == []


def test_duplicate_capability_id_is_rejected() -> None:
    catalog, entrypoints, ledger = _documents()
    duplicate = deepcopy(catalog["capabilities"][0])
    catalog["capabilities"].append(duplicate)
    errors = validate_documents(catalog, entrypoints, ledger)
    assert any("duplicate capability_id" in error for error in errors)


def test_missing_provenance_is_rejected() -> None:
    catalog, entrypoints, ledger = _documents()
    del catalog["capabilities"][0]["provenance"]
    errors = validate_documents(catalog, entrypoints, ledger)
    assert any("missing fields: provenance" in error for error in errors)


def test_missing_migration_disposition_is_rejected() -> None:
    catalog, entrypoints, ledger = _documents()
    del catalog["capabilities"][0]["migration_disposition"]
    errors = validate_documents(catalog, entrypoints, ledger)
    assert any("migration_disposition" in error for error in errors)


def test_wrong_verified_legacy_commit_is_rejected() -> None:
    catalog, entrypoints, ledger = _documents()
    catalog["capabilities"][0]["verified_legacy_commit"] = "0" * 40
    errors = validate_documents(catalog, entrypoints, ledger)
    assert any("verified legacy commit" in error for error in errors)


def test_unmapped_api_entrypoint_is_rejected() -> None:
    catalog, entrypoints, ledger = _documents()
    api = next(entry for entry in entrypoints["entrypoints"] if entry["kind"] == "api")
    api["capability_id"] = "lottery.missing"
    errors = validate_documents(catalog, entrypoints, ledger)
    assert any("unmapped capability" in error for error in errors)


def test_read_only_capability_cannot_claim_a_db_writer() -> None:
    catalog, entrypoints, ledger = _documents()
    writer = next(entry for entry in entrypoints["entrypoints"] if entry["kind"] == "db_writer")
    writer["capability_id"] = "lottery.strategy_catalog.list"
    writer["status"] = "MAPPED"
    errors = validate_documents(catalog, entrypoints, ledger)
    assert any("DB writer maps to capability without data_writes" in error for error in errors)


def test_retire_disposition_requires_a_condition() -> None:
    catalog, entrypoints, ledger = _documents()
    capability = catalog["capabilities"][0]
    capability["migration_disposition"] = "RETIRE"
    capability["retirement_condition"] = None
    errors = validate_documents(catalog, entrypoints, ledger)
    assert any("RETIRE requires a retirement condition" in error for error in errors)


def test_migrating_ledger_entry_requires_control_fields() -> None:
    catalog, entrypoints, ledger = _documents()
    migrating = next(entry for entry in ledger["entries"] if entry["phase"] == "MIGRATING")
    del migrating["rollback_condition"]
    errors = validate_documents(catalog, entrypoints, ledger)
    assert any("MIGRATING missing controls: rollback_condition" in error for error in errors)


def test_migrating_ledger_entry_rejects_cutover_claim() -> None:
    catalog, entrypoints, ledger = _documents()
    migrating = next(entry for entry in ledger["entries"] if entry["phase"] == "MIGRATING")
    migrating["production_state"] = "CUTOVER_READY_NOT_DEPLOYED"
    errors = validate_documents(catalog, entrypoints, ledger)
    assert any("must remain NOT_CUTOVER_READY" in error for error in errors)


def test_migrating_ledger_entry_rejects_completed_implementation_state() -> None:
    catalog, entrypoints, ledger = _documents()
    migrating = next(entry for entry in ledger["entries"] if entry["phase"] == "MIGRATING")
    migrating["implementation_state"] = "CUTOVER_COMPLETE"
    errors = validate_documents(catalog, entrypoints, ledger)
    assert any("invalid MIGRATING implementation_state" in error for error in errors)
