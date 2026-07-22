from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
READ_MODELS = REPO_ROOT / "src/lottolab/application/historical_prefix_queries.py"
USE_CASES = (
    REPO_ROOT / "src/lottolab/application/use_cases/query_historical_prefix_analytics.py"
)
PRODUCTION_PATHS = (READ_MODELS, USE_CASES)

FORBIDDEN_LAYER_PREFIXES = (
    "lottolab.application.ports",
    "lottolab.evidence",
    "lottolab.infrastructure",
    "lottolab.interfaces",
)
FORBIDDEN_MODULES = {
    "fastapi",
    "os",
    "pathlib",
    "pydantic",
    "random",
    "requests",
    "socket",
    "sqlite3",
    "subprocess",
    "time",
    "uuid",
}


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            modules.add(node.module)
    return modules


def test_historical_prefix_query_modules_exist() -> None:
    assert all(path.is_file() for path in PRODUCTION_PATHS)


def test_query_modules_respect_application_dependency_boundary() -> None:
    for path in PRODUCTION_PATHS:
        imports = _imports(path)
        assert not any(
            module == prefix or module.startswith(f"{prefix}.")
            for module in imports
            for prefix in FORBIDDEN_LAYER_PREFIXES
        )
        assert not imports & FORBIDDEN_MODULES


def test_query_modules_have_no_runtime_db_filesystem_or_legacy_hooks() -> None:
    for path in PRODUCTION_PATHS:
        source = path.read_text(encoding="utf-8")
        imports = _imports(path)
        assert not any(module.startswith("tests") for module in imports)
        for forbidden in (
            "LotteryNew",
            "execute_strategy",
            "getenv",
            "open(",
            "sqlite",
        ):
            assert forbidden not in source
