"""Validate the P600A catalog, entrypoint inventory, and migration ledger."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, cast

PINNED_LEGACY_COMMIT = "520c3922a7c8f47e5b6196fb4b0d54716fa5fd9f"
DISPOSITIONS = frozenset(
    {
        "MIGRATE_FIRST",
        "MIGRATE_LATER",
        "KEEP_LEGACY_TEMPORARILY",
        "REPLACE",
        "RETIRE",
        "FREEZE_AS_RESEARCH",
        "UNKNOWN_NEEDS_AUDIT",
    }
)
CAPABILITY_FIELDS = frozenset(
    {
        "capability_id",
        "name",
        "domain",
        "description",
        "entrypoints",
        "current_implementation",
        "public_contracts",
        "data_reads",
        "data_writes",
        "filesystem_side_effects",
        "scheduler_or_runtime_effects",
        "strategy_dependencies",
        "tests",
        "production_status",
        "migration_disposition",
        "target_lottolab_module",
        "compatibility_required",
        "retirement_condition",
        "provenance",
        "verified_legacy_commit",
        "unknowns",
    }
)
PROVENANCE_FIELDS = frozenset(
    {
        "legacy_commit_oid",
        "source_paths",
        "task_ids",
        "PR_numbers",
        "roadmap_paths",
        "wiki_paths",
        "evidence_paths",
        "artifact_hashes_when_available",
    }
)
ENTRYPOINT_KINDS_REQUIRING_COVERAGE = frozenset(
    {
        "api",
        "ui",
        "ui_handler",
        "frontend_api",
        "frontend_http_call",
        "cli",
        "scheduler",
        "hook",
        "job",
        "db_reader",
        "db_writer",
    }
)
LEDGER_PHASES = frozenset(
    {
        "PLANNED",
        "INVENTORIED",
        "MIGRATING",
        "PARITY_VERIFIED",
        "CUTOVER_READY",
        "CUTOVER_COMPLETE",
        "LEGACY_RETIRED",
    }
)
LEDGER_IMPLEMENTATION_STATES = frozenset(
    {
        "IN_PROGRESS",
        "IMPLEMENTED_PENDING_REVIEW",
        "PARITY_VERIFIED",
        "CUTOVER_COMPLETE",
    }
)
LEDGER_PRODUCTION_STATES = frozenset(
    {"NOT_CUTOVER_READY", "CUTOVER_READY_NOT_DEPLOYED", "DEPLOYED"}
)
MIGRATING_IMPLEMENTATION_STATES = frozenset(
    {"IN_PROGRESS", "IMPLEMENTED_PENDING_REVIEW", "PARITY_VERIFIED"}
)
MIGRATING_CONTROL_FIELDS = frozenset(
    {
        "implementation_state",
        "production_state",
        "compatibility_condition",
        "rollback_condition",
    }
)


def load_document(path: Path) -> dict[str, Any]:
    """Load a JSON document stored with a .yaml extension (valid YAML subset)."""
    value: Any = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object")
    return cast(dict[str, Any], value)


def _objects(value: Any, label: str, errors: list[str]) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        errors.append(f"{label} must be a list")
        return []
    result: list[dict[str, Any]] = []
    items = cast(list[Any], value)
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            errors.append(f"{label}[{index}] must be an object")
            continue
        result.append(cast(dict[str, Any], item))
    return result


def _nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _string_list(value: Any) -> bool:
    return isinstance(value, list) and all(
        _nonempty_string(item) for item in cast(list[Any], value)
    )


def _validate_capabilities(catalog: dict[str, Any], errors: list[str]) -> dict[str, dict[str, Any]]:
    if catalog.get("verified_legacy_commit") != PINNED_LEGACY_COMMIT:
        errors.append("catalog verified_legacy_commit does not equal the P600A pin")
    capabilities = _objects(catalog.get("capabilities"), "capabilities", errors)
    by_id: dict[str, dict[str, Any]] = {}
    for index, capability in enumerate(capabilities):
        missing = sorted(CAPABILITY_FIELDS - capability.keys())
        if missing:
            errors.append(f"capabilities[{index}] missing fields: {', '.join(missing)}")
            continue
        capability_id = capability.get("capability_id")
        if not _nonempty_string(capability_id):
            errors.append(f"capabilities[{index}] has invalid capability_id")
            continue
        assert isinstance(capability_id, str)
        if capability_id in by_id:
            errors.append(f"duplicate capability_id: {capability_id}")
        by_id[capability_id] = capability
        if capability.get("verified_legacy_commit") != PINNED_LEGACY_COMMIT:
            errors.append(f"{capability_id}: verified legacy commit is missing or wrong")
        disposition = capability.get("migration_disposition")
        if disposition not in DISPOSITIONS:
            errors.append(f"{capability_id}: invalid migration disposition {disposition!r}")
        if capability.get("domain") != "lottery":
            errors.append(f"{capability_id}: domain must be lottery")
        for field in (
            "current_implementation",
            "public_contracts",
            "data_reads",
            "data_writes",
            "filesystem_side_effects",
            "scheduler_or_runtime_effects",
            "strategy_dependencies",
            "tests",
            "unknowns",
        ):
            if not _string_list(capability.get(field)):
                errors.append(f"{capability_id}: {field} must be a string list")
        provenance = capability.get("provenance")
        if not isinstance(provenance, dict):
            errors.append(f"{capability_id}: provenance must be an object")
        else:
            provenance = cast(dict[str, Any], provenance)
            provenance_missing = sorted(PROVENANCE_FIELDS - provenance.keys())
            if provenance_missing:
                errors.append(
                    f"{capability_id}: provenance missing {', '.join(provenance_missing)}"
                )
            if provenance.get("legacy_commit_oid") != PINNED_LEGACY_COMMIT:
                errors.append(f"{capability_id}: provenance legacy_commit_oid is wrong")
            if not _string_list(provenance.get("source_paths")):
                errors.append(f"{capability_id}: provenance source_paths must be non-empty")
        data_writes = capability.get("data_writes")
        if capability.get("production_status") == "READ_ONLY" and data_writes:
            errors.append(f"{capability_id}: READ_ONLY contradicts declared data_writes")
        if disposition == "RETIRE" and not _nonempty_string(capability.get("retirement_condition")):
            errors.append(f"{capability_id}: RETIRE requires a retirement condition")
        if capability.get("compatibility_required") is True and not _nonempty_string(
            capability.get("retirement_condition")
        ):
            errors.append(f"{capability_id}: compatibility layer lacks a retirement condition")
        unknowns = capability.get("unknowns")
        if disposition == "UNKNOWN_NEEDS_AUDIT" and not unknowns:
            errors.append(f"{capability_id}: UNKNOWN_NEEDS_AUDIT requires explicit unknowns")
    return by_id


def _validate_entrypoints(
    manifest: dict[str, Any],
    capabilities: dict[str, dict[str, Any]],
    errors: list[str],
) -> list[dict[str, Any]]:
    if manifest.get("legacy_commit_oid") != PINNED_LEGACY_COMMIT:
        errors.append("entrypoint manifest commit does not equal the P600A pin")
    entries = _objects(manifest.get("entrypoints"), "entrypoints", errors)
    seen: set[str] = set()
    calculated: dict[str, Counter[str]] = {}
    for index, entry in enumerate(entries):
        entrypoint_id = entry.get("entrypoint_id")
        if not _nonempty_string(entrypoint_id):
            errors.append(f"entrypoints[{index}] has invalid entrypoint_id")
            continue
        assert isinstance(entrypoint_id, str)
        if entrypoint_id in seen:
            errors.append(f"duplicate entrypoint_id: {entrypoint_id}")
        seen.add(entrypoint_id)
        kind = entry.get("kind")
        capability_id = entry.get("capability_id")
        status = entry.get("status")
        if not _nonempty_string(kind):
            errors.append(f"{entrypoint_id}: missing kind")
            continue
        assert isinstance(kind, str)
        if capability_id not in capabilities:
            errors.append(f"{entrypoint_id}: unmapped capability {capability_id!r}")
            continue
        if status not in {"MAPPED", "UNKNOWN_NEEDS_AUDIT"}:
            errors.append(f"{entrypoint_id}: invalid mapping status {status!r}")
            continue
        calculated.setdefault(kind, Counter())["total"] += 1
        calculated[kind]["mapped" if status == "MAPPED" else "unknown"] += 1
        capability = capabilities[str(capability_id)]
        disposition = capability.get("migration_disposition")
        if status == "UNKNOWN_NEEDS_AUDIT":
            if disposition != "UNKNOWN_NEEDS_AUDIT":
                errors.append(
                    f"{entrypoint_id}: unknown entry must map to an UNKNOWN_NEEDS_AUDIT capability"
                )
            if not _nonempty_string(entry.get("unknown_reason")):
                errors.append(f"{entrypoint_id}: unknown entry lacks a reason")
        if status == "MAPPED" and disposition == "UNKNOWN_NEEDS_AUDIT":
            errors.append(f"{entrypoint_id}: mapped status contradicts unknown capability")
        if kind == "db_reader" and not capability.get("data_reads"):
            errors.append(f"{entrypoint_id}: DB reader maps to capability without data_reads")
        if kind == "db_writer" and not capability.get("data_writes"):
            errors.append(f"{entrypoint_id}: DB writer maps to capability without data_writes")
    coverage = manifest.get("coverage")
    if not isinstance(coverage, dict):
        errors.append("entrypoint manifest coverage must be an object")
        return entries
    coverage = cast(dict[str, Any], coverage)
    for kind, counts in calculated.items():
        recorded = coverage.get(kind)
        expected = {name: counts.get(name, 0) for name in ("total", "mapped", "unknown")}
        if recorded != expected:
            errors.append(
                f"coverage mismatch for {kind}: recorded={recorded!r} expected={expected!r}"
            )
    for kind in ENTRYPOINT_KINDS_REQUIRING_COVERAGE:
        if kind not in calculated:
            errors.append(f"required entrypoint kind is absent: {kind}")
    return entries


def _validate_ledger(
    ledger: dict[str, Any], capabilities: dict[str, dict[str, Any]], errors: list[str]
) -> None:
    entries = _objects(ledger.get("entries"), "ledger.entries", errors)
    seen: set[str] = set()
    for index, entry in enumerate(entries):
        capability_id = entry.get("capability_id")
        if not _nonempty_string(capability_id):
            errors.append(f"ledger.entries[{index}] has invalid capability_id")
            continue
        assert isinstance(capability_id, str)
        if capability_id in seen:
            errors.append(f"duplicate ledger capability_id: {capability_id}")
        seen.add(capability_id)
        if capability_id not in capabilities:
            errors.append(f"ledger references unknown capability: {capability_id}")
        phase = entry.get("phase")
        if phase not in LEDGER_PHASES:
            errors.append(f"{capability_id}: invalid ledger phase {phase!r}")
        if phase in {
            "PARITY_VERIFIED",
            "CUTOVER_READY",
            "CUTOVER_COMPLETE",
        } and not _nonempty_string(entry.get("parity_evidence")):
            errors.append(f"{capability_id}: {phase} requires parity_evidence")
        if phase == "CUTOVER_COMPLETE":
            for field in ("deployed_revision", "deployment_target", "rollback_method"):
                if not _nonempty_string(entry.get(field)):
                    errors.append(f"{capability_id}: CUTOVER_COMPLETE requires {field}")
        if phase == "MIGRATING":
            missing_controls = sorted(MIGRATING_CONTROL_FIELDS - entry.keys())
            if missing_controls:
                errors.append(
                    f"{capability_id}: MIGRATING missing controls: {', '.join(missing_controls)}"
                )
        if "implementation_state" in entry and (
            entry.get("implementation_state") not in LEDGER_IMPLEMENTATION_STATES
        ):
            errors.append(
                f"{capability_id}: invalid implementation_state "
                f"{entry.get('implementation_state')!r}"
            )
        if "production_state" in entry and (
            entry.get("production_state") not in LEDGER_PRODUCTION_STATES
        ):
            errors.append(
                f"{capability_id}: invalid production_state {entry.get('production_state')!r}"
            )
        for field in ("compatibility_condition", "rollback_condition"):
            if field in entry and not _nonempty_string(entry.get(field)):
                errors.append(f"{capability_id}: invalid {field}")
        if phase == "MIGRATING" and entry.get("production_state") not in {
            None,
            "NOT_CUTOVER_READY",
        }:
            errors.append(f"{capability_id}: MIGRATING must remain NOT_CUTOVER_READY")
        if phase == "MIGRATING" and entry.get(
            "implementation_state"
        ) not in MIGRATING_IMPLEMENTATION_STATES | {None}:
            errors.append(
                f"{capability_id}: invalid MIGRATING implementation_state "
                f"{entry.get('implementation_state')!r}"
            )
    missing = sorted(set(capabilities) - seen)
    extra = sorted(seen - set(capabilities))
    if missing:
        errors.append(f"ledger missing capabilities: {', '.join(missing)}")
    if extra:
        errors.append(f"ledger has extra capabilities: {', '.join(extra)}")


def validate_documents(
    catalog: dict[str, Any], manifest: dict[str, Any], ledger: dict[str, Any]
) -> list[str]:
    """Return all validation failures; an empty list means the gate passed."""
    errors: list[str] = []
    capabilities = _validate_capabilities(catalog, errors)
    _validate_entrypoints(manifest, capabilities, errors)
    _validate_ledger(ledger, capabilities, errors)
    return errors


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=Path("docs/capabilities/catalog.yaml"))
    parser.add_argument(
        "--entrypoints",
        type=Path,
        default=Path("docs/capabilities/legacy-entrypoints.yaml"),
    )
    parser.add_argument("--ledger", type=Path, default=Path("docs/migration/migration-ledger.yaml"))
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    errors = validate_documents(
        load_document(args.catalog), load_document(args.entrypoints), load_document(args.ledger)
    )
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        print(f"CAPABILITY_CATALOG_VALIDATION_FAILED errors={len(errors)}")
        return 1
    manifest = load_document(args.entrypoints)
    coverage = manifest["coverage"]
    print(
        "CAPABILITY_CATALOG_VALIDATION_PASS "
        f"capabilities={len(load_document(args.catalog)['capabilities'])} "
        f"entrypoints={len(manifest['entrypoints'])} "
        f"coverage={json.dumps(coverage, sort_keys=True)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
