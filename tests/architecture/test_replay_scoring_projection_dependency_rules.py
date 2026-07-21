"""Architecture and protected-shape guards for the Replay-scoring projection."""

from __future__ import annotations

import ast
import dataclasses
import inspect
from pathlib import Path

from lottolab.application.ports import (
    ReplayScoringProjectionReader,
    ReplayScoringProjectionWriter,
)
from lottolab.evidence.replay_scoring_artifact import ReplayScoringArtifact
from lottolab.infrastructure.persistence.replay_scoring_projection_repository import (
    SQLiteReplayScoringProjectionRepository,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src" / "lottolab"
PATHS = {
    "projection_domain": SRC / "domain" / "replay_scoring_projection.py",
    "use_case": SRC / "application" / "use_cases" / "persist_replay_scoring_artifact.py",
    "repository": SRC
    / "infrastructure"
    / "persistence"
    / "replay_scoring_projection_repository.py",
    "schema": SRC / "infrastructure" / "persistence" / "replay_scoring_schema.py",
}


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_all_new_modules_exist() -> None:
    assert all(path.is_file() for path in PATHS.values())


def test_projection_domain_imports_no_other_lottolab_layer() -> None:
    imports = _imports(PATHS["projection_domain"])
    assert not any(module.startswith("lottolab") for module in imports)


def test_use_case_imports_no_infrastructure_or_interfaces() -> None:
    imports = _imports(PATHS["use_case"])
    assert not any(
        module.startswith(("lottolab.infrastructure", "lottolab.interfaces"))
        for module in imports
    )


def test_use_case_does_not_access_sqlite_directly() -> None:
    source = PATHS["use_case"].read_text(encoding="utf-8")
    assert "sqlite3" not in source
    imports = _imports(PATHS["use_case"])
    assert "sqlite3" not in imports


def test_repository_implements_only_the_narrow_writer_and_reader_ports() -> None:
    assert isinstance(SQLiteReplayScoringProjectionRepository, type)
    public_methods = {
        name
        for name, member in inspect.getmembers(SQLiteReplayScoringProjectionRepository)
        if inspect.isfunction(member) and not name.startswith("_")
    }
    writer_methods = {"persist_replay_scoring_artifact"}
    reader_methods = {
        "get_run",
        "get_replay_scoring_artifact",
        "list_scored_predictions",
        "list_strategy_aggregates",
        "get_overall_aggregate",
    }
    assert public_methods == writer_methods | reader_methods
    assert writer_methods <= set(dir(ReplayScoringProjectionWriter))
    assert reader_methods <= set(dir(ReplayScoringProjectionReader))


def test_no_http_cli_or_frontend_dependency_in_new_modules() -> None:
    for name, path in PATHS.items():
        imports = _imports(path)
        assert not any(
            module.startswith(("lottolab.interfaces", "fastapi", "typer", "uvicorn"))
            for module in imports
        ), name


def test_no_cli_router_or_frontend_path_references_the_projection() -> None:
    scanned = (
        *(SRC / "interfaces").rglob("*.py"),
        *(REPO_ROOT / "frontend").rglob("*"),
    )
    for path in scanned:
        if path.is_file():
            text = path.read_text(encoding="utf-8", errors="ignore")
            assert "replay_scoring_projection" not in text
            assert "ReplayScoringProjectionRepository" not in text


def test_new_modules_do_not_import_the_historical_query_domain() -> None:
    forbidden_modules = (
        "historical_queries",
        "historical_repositories",
        "historical_schema",
        "historical_results",
    )
    for name, path in PATHS.items():
        imports = _imports(path)
        assert not any(
            forbidden in module for module in imports for forbidden in forbidden_modules
        ), name
        assert "HistoricalResultQueryRepository" not in path.read_text(encoding="utf-8"), name


def test_persistence_modules_do_not_import_the_prize_resolver() -> None:
    for name in ("repository", "schema"):
        source = PATHS[name].read_text(encoding="utf-8")
        assert "resolve_big_lotto_prize_tier" not in source, name
    # The schema module has zero business-rule coupling; the repository is
    # allowed to import only the *identifier* enums (never the resolver).
    assert "lottery_rules" not in PATHS["schema"].read_text(encoding="utf-8")


def test_repository_does_not_construct_a_duplicate_prize_mapping() -> None:
    source = PATHS["repository"].read_text(encoding="utf-8")
    assert "BigLottoPrizeTier(" not in source
    for signature in ("(6, False)", "(5, True)", "(5, False)", "(4, True)"):
        assert signature not in source


def test_repository_never_opens_a_default_or_canonical_database() -> None:
    for name in ("repository", "schema"):
        source = PATHS[name].read_text(encoding="utf-8")
        assert "os.environ" not in source, name
        assert "resolve_local_data_paths(" not in source, name
        imports = _imports(PATHS[name])
        assert not any("draw_schema" in module for module in imports), name


def test_protected_replay_scoring_artifact_shape_is_unchanged() -> None:
    assert tuple(field.name for field in dataclasses.fields(ReplayScoringArtifact)) == (
        "artifact_schema_version",
        "source_replay_artifact_payload_sha256",
        "dataset_id",
        "dataset_version",
        "lottery_type",
        "target_identities",
        "strategy_identities",
        "scored_predictions",
        "strategy_aggregates",
        "overall_aggregate",
        "scored_record_count",
        "payload_sha256",
    )


def test_no_alternate_canonical_serializer_is_defined() -> None:
    for name in ("repository", "use_case"):
        source = PATHS[name].read_text(encoding="utf-8")
        assert "def serialize_replay_scoring_artifact" not in source
        assert "def canonical_bytes" not in source
        assert "hashlib.sha256(" not in source
