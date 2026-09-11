"""Preflight, promote, or inspect the Authority B canonical consensus."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from lottolab.infrastructure.b649_consensus_promotion import (
    BLOCKER_SCHEDULE_AUTHORITY_MISSING,
    CONSENSUS_SCOPE,
    CanonicalConsensusCandidate,
    CanonicalConsensusEligibilityGate,
    CanonicalEligibilityError,
    ConsensusCandidateError,
    PromotionRequest,
    load_consensus_candidate,
    promote_consensus_candidate,
)
from lottolab.infrastructure.persistence.draw_schema import (
    LocalDataError,
    LocalDataPaths,
    resolve_local_data_paths,
)
from lottolab.infrastructure.persistence.research_repository import (
    LiveForecastCurrentResult,
    ResearchRepositoryError,
    SQLiteResearchRepository,
)
from lottolab.infrastructure.persistence.research_schema import (
    CURRENT_SCHEMA_VERSION,
    V4_MIGRATION_CHECKSUM,
    ResearchDataError,
    ResearchDataPaths,
    ResearchSchemaError,
    verify_schema_read_only,
)


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "preflight":
            result = _preflight(args)
        elif args.command == "promote":
            result = _promote(args)
        else:
            result = _current(args)
    except (
        ConsensusCandidateError,
        CanonicalEligibilityError,
        LocalDataError,
        ResearchDataError,
        ResearchSchemaError,
        ResearchRepositoryError,
        ValueError,
    ) as exc:
        result = {
            "command": args.command,
            "status": "NOT_READY",
            "blockers": [str(exc)],
        }
        _print_json(result)
        return 1
    _print_json(result)
    return 0 if result.get("status") in {"READY", "CURRENT", "EMPTY"} else 1


def _preflight(args: argparse.Namespace) -> dict[str, object]:
    candidate, candidate_blockers = _load_candidate_for_cli(args)
    database, database_blockers = _database_report(Path(args.database))
    blockers = [*candidate_blockers, *database_blockers]
    current: dict[str, object] = {"version": 0, "present": False}
    eligibility: dict[str, object] = {
        "eligible": False,
        "blockers": [BLOCKER_SCHEDULE_AUTHORITY_MISSING],
    }
    if candidate is not None:
        target = candidate.target
        if args.schedule_authority_sha256 is not None:
            target["schedule_authority_sha256"] = args.schedule_authority_sha256
        gate = CanonicalConsensusEligibilityGate(_draw_paths(args.draw_database))
        eligibility_result = gate.check(target)
        eligibility = eligibility_result.as_dict()
        blockers.extend(eligibility_result.blockers)
    if database is not None:
        try:
            repository = SQLiteResearchRepository(
                _research_paths(Path(args.database)), initialize=False
            )
            selected = repository.read_current_consensus()
            if selected is not None:
                current = _current_dict(selected)
            expected = int(args.expected_current_version)
            actual = 0 if selected is None else selected.version
            if expected != actual:
                blockers.append("EXPECTED_CURRENT_VERSION_MISMATCH")
        except ResearchRepositoryError as exc:
            blockers.append(str(exc))
    blockers.extend(_request_blockers(args, require_activation=False))
    return {
        "command": "preflight",
        "status": "READY" if not blockers else "NOT_READY",
        "blockers": list(dict.fromkeys(blockers)),
        "database": database,
        "candidate": None if candidate is None else _candidate_dict(candidate),
        "current": current,
        "eligibility": eligibility,
        "scope": list(CONSENSUS_SCOPE),
    }


def _promote(args: argparse.Namespace) -> dict[str, object]:
    candidate = load_consensus_candidate(
        args.candidate,
        candidate_sha256=args.candidate_sha256,
        source_root=args.source_root,
    )
    request = _request(args)
    draw_paths = _draw_paths(args.draw_database)
    gate = CanonicalConsensusEligibilityGate(draw_paths)
    result = promote_consensus_candidate(
        Path(args.database),
        candidate,
        request,
        eligibility_gate=gate,
    )
    return {
        "command": "promote",
        "status": "READY",
        "blockers": [],
        "result": {
            "idempotent": result.idempotent,
            "payload_sha256": result.payload_sha256,
            "pointer_advanced": result.pointer_advanced,
            "provenance_envelope_sha256": result.provenance_envelope_sha256,
            "run_id": result.run_id,
            "version": result.version,
        },
        "scope": list(CONSENSUS_SCOPE),
    }


def _current(args: argparse.Namespace) -> dict[str, object]:
    database_path = Path(args.database)
    database, database_blockers = _database_report(database_path)
    if database_blockers:
        return {
            "command": "current",
            "status": "NOT_READY",
            "blockers": database_blockers,
            "database": database,
            "current": None,
        }
    repository = SQLiteResearchRepository(_research_paths(database_path), initialize=False)
    selected = repository.read_current_consensus()
    eligibility = CanonicalConsensusEligibilityGate(_draw_paths(args.draw_database)).check(
        None if selected is None else selected.forecast.target
    )
    if selected is None:
        return {
            "command": "current",
            "status": "EMPTY",
            "blockers": [],
            "database": database,
            "current": None,
            "eligibility": eligibility.as_dict(),
            "scope": list(CONSENSUS_SCOPE),
        }
    return {
        "command": "current",
        "status": "CURRENT",
        "blockers": [],
        "database": database,
        "current": _current_dict(selected),
        "eligibility": eligibility.as_dict(),
        "scope": list(CONSENSUS_SCOPE),
    }


def _load_candidate_for_cli(
    args: argparse.Namespace,
) -> tuple[CanonicalConsensusCandidate | None, list[str]]:
    try:
        return (
            load_consensus_candidate(
                args.candidate,
                candidate_sha256=args.candidate_sha256,
                source_root=args.source_root,
            ),
            [],
        )
    except ConsensusCandidateError as exc:
        return None, [str(exc)]


def _database_report(path: Path) -> tuple[dict[str, object] | None, list[str]]:
    try:
        paths = _research_paths(path)
        if not verify_schema_read_only(paths):
            return None, ["RESEARCH_DATABASE_MISSING"]
        report = SQLiteResearchRepository(paths, initialize=False).verify_store()
        if report.schema_version != CURRENT_SCHEMA_VERSION:
            return report.as_dict(), ["RESEARCH_SCHEMA_VERSION_MISMATCH"]
        if report.migration_checksum != V4_MIGRATION_CHECKSUM:
            return report.as_dict(), ["RESEARCH_SCHEMA_CHECKSUM_MISMATCH"]
        if not report.healthy:
            return report.as_dict(), ["RESEARCH_STORE_UNHEALTHY"]
        return report.as_dict(), []
    except (ResearchDataError, ResearchSchemaError, ResearchRepositoryError, ValueError) as exc:
        return None, [str(exc)]


def _request(args: argparse.Namespace) -> PromotionRequest:
    blockers = _request_blockers(args, require_activation=True)
    if blockers:
        raise ValueError(blockers[0])
    return PromotionRequest(
        request_id=args.request_id,
        request_sha256=args.request_sha256,
        expected_current_version=int(args.expected_current_version),
        schedule_authority_sha256=args.schedule_authority_sha256,
        authorization_evidence_reference=args.authorization_reference,
        promotion_executor_identity=args.executor_identity,
        execution_source_id=args.execution_source_id,
        execution_source_version=args.execution_source_version,
    )


def _request_blockers(args: argparse.Namespace, *, require_activation: bool) -> list[str]:
    try:
        if not isinstance(args.request_id, str) or not args.request_id.strip():
            raise ValueError("request_id must be non-empty text")
        if (
            not isinstance(args.request_sha256, str)
            or len(args.request_sha256) != 64
            or any(character not in "0123456789abcdef" for character in args.request_sha256)
        ):
            raise ValueError("request_sha256 must be a lowercase SHA-256 digest")
        if type(args.expected_current_version) is not int or args.expected_current_version < 0:
            raise ValueError("expected_current_version must be a non-negative integer")
        for name in ("execution_source_id", "execution_source_version"):
            if not isinstance(getattr(args, name), str) or not getattr(args, name).strip():
                raise ValueError(f"{name} must be non-empty text")
        schedule_hash = getattr(args, "schedule_authority_sha256", None)
        if schedule_hash is None and require_activation:
            raise ValueError("schedule_authority_sha256 is required for promotion")
        if schedule_hash is not None and (
            len(schedule_hash) != 64
            or any(character not in "0123456789abcdef" for character in schedule_hash)
        ):
            raise ValueError("schedule_authority_sha256 must be a lowercase SHA-256 digest")
        if require_activation:
            for name in ("authorization_reference", "executor_identity"):
                if not isinstance(getattr(args, name), str) or not getattr(args, name).strip():
                    raise ValueError(f"{name} must be non-empty text")
    except (AttributeError, TypeError, ValueError) as exc:
        return [str(exc)]
    return []


def _research_paths(path: Path) -> ResearchDataPaths:
    if not path.is_absolute() or path.name != "lottolab_research.db":
        raise ValueError("database path must be the explicit research database")
    return ResearchDataPaths(path.parent, path)


def _draw_paths(value: str | None) -> LocalDataPaths:
    if value is None:
        return resolve_local_data_paths()
    path = Path(value)
    if not path.is_absolute() or path.name != "lottolab.db":
        raise ValueError("draw database path must be the explicit canonical draw database")
    return LocalDataPaths(path.parent, path)


def _candidate_dict(candidate: CanonicalConsensusCandidate) -> dict[str, object]:
    payload = candidate.payload
    return {
        "candidate_locator": str(candidate.candidate_locator),
        "candidate_sha256": candidate.candidate_sha256,
        "source_root": str(candidate.source_root),
        "schema_version": payload["schema_version"],
        "method_id": payload["aggregation_method_id"],
        "method_version": payload["aggregation_method_version"],
        "target": candidate.target,
        "stream_count": len(candidate.stream_inputs),
        "stream_input_manifest_sha256": payload["stream_input_manifest_sha256"],
        "implementation_commit": payload["implementation_commit"],
        "implementation_tree": payload["implementation_tree"],
    }


def _current_dict(selected: LiveForecastCurrentResult) -> dict[str, object]:
    forecast = selected.forecast
    return {
        "version": selected.version,
        "run_id": selected.run_id,
        "request_id": selected.request_id,
        "request_sha256": selected.request_sha256,
        "payload_sha256": selected.payload_sha256,
        "provenance_class": selected.provenance_class,
        "forecast_stream_id": selected.forecast_stream_id,
        "forecast_stream_version": selected.forecast_stream_version,
        "candidate_locator": selected.source_locator,
        "source_locator": selected.source_locator,
        "schedule_authority_sha256": selected.schedule_authority_sha256,
        "target": forecast.target,
        "pointer_advanced": selected.pointer_advanced,
    }


def _print_json(value: Mapping[str, object]) -> None:
    print(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    preflight = subparsers.add_parser("preflight")
    _add_database(preflight)
    _add_candidate(preflight)
    _add_request(preflight)
    _add_execution_identity(preflight)
    _add_schedule_hash(preflight, required=False)
    preflight.set_defaults(command="preflight")

    promote = subparsers.add_parser("promote")
    _add_database(promote)
    _add_candidate(promote)
    _add_request(promote)
    _add_execution_identity(promote)
    _add_schedule_hash(promote, required=True)
    promote.add_argument("--authorization-reference", required=True)
    promote.add_argument("--executor-identity", required=True)
    promote.set_defaults(command="promote")

    current = subparsers.add_parser("current")
    _add_database(current)
    current.set_defaults(command="current")
    return parser


def _add_database(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--database", required=True)
    parser.add_argument("--draw-database")


def _add_candidate(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--candidate-sha256", required=True)
    parser.add_argument("--source-root")


def _add_request(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--expected-current-version", required=True, type=int)
    parser.add_argument("--request-id", required=True)
    parser.add_argument("--request-sha256", required=True)


def _add_execution_identity(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--execution-source-id", required=True)
    parser.add_argument("--execution-source-version", required=True)


def _add_schedule_hash(parser: argparse.ArgumentParser, *, required: bool) -> None:
    parser.add_argument("--schedule-authority-sha256", required=required)


if __name__ == "__main__":
    raise SystemExit(main())
