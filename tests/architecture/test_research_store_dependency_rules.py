"""Architecture contract for the canonical research-store write boundary."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = ROOT / "src" / "lottolab"
SCHEMA = (
    SOURCE_ROOT
    / "infrastructure"
    / "persistence"
    / "research_schema.py"
)
REPOSITORY = (
    SOURCE_ROOT
    / "infrastructure"
    / "persistence"
    / "research_repository.py"
)
CLI = SOURCE_ROOT / "interfaces" / "cli" / "research_store.py"
DOMAIN = SOURCE_ROOT / "domain" / "research.py"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.add(node.module)
    return imported


def _string_value(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return "".join(
            value.value
            for value in node.values
            if isinstance(value, ast.Constant) and isinstance(value.value, str)
        )
    return None


def test_research_modules_exist_in_the_intended_layers() -> None:
    assert SCHEMA.is_file()
    assert REPOSITORY.is_file()
    assert CLI.is_file()
    assert DOMAIN.is_file()


def test_research_schema_is_standalone_from_fragmented_research_schemas() -> None:
    imported = _imports(SCHEMA)

    assert "lottolab.infrastructure.persistence.historical_schema" not in imported
    assert "lottolab.infrastructure.persistence.replay_scoring_schema" not in imported


def test_research_domain_vocabulary_imports_no_other_lottolab_layer() -> None:
    assert all(
        not module.startswith("lottolab.")
        for module in _imports(DOMAIN)
    )


def test_only_schema_and_repository_execute_research_sql_in_production() -> None:
    allowed = {SCHEMA, REPOSITORY}
    violations: list[str] = []
    for path in sorted(SOURCE_ROOT.rglob("*.py")):
        if path in allowed:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr not in {"execute", "executemany", "executescript"}:
                continue
            if not node.args:
                continue
            sql = _string_value(node.args[0])
            if sql is not None and "research_" in sql.casefold():
                violations.append(f"{path.relative_to(ROOT)}:{node.lineno}")

    assert violations == []


def test_cli_is_thin_and_does_not_import_sqlite_or_fragmented_schemas() -> None:
    imported = _imports(CLI)

    assert "sqlite3" not in imported
    assert "lottolab.infrastructure.persistence.historical_schema" not in imported
    assert "lottolab.infrastructure.persistence.replay_scoring_schema" not in imported
