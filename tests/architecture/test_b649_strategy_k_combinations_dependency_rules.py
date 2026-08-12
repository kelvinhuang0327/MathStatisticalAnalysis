"""Architecture guards for the sealed, read-only B649 analytics vertical."""

# pyright: reportUnknownArgumentType=false, reportUnknownMemberType=false
# pyright: reportUnknownVariableType=false

from __future__ import annotations

import ast
from pathlib import Path

from lottolab.interfaces.api.app import create_app

ROOT = Path(__file__).resolve().parents[2]
APPLICATION = ROOT / "src/lottolab/application/b649_strategy_k_combinations.py"
READER = ROOT / "src/lottolab/infrastructure/b649_analytics_artifact_reader.py"
ROUTER = ROOT / "src/lottolab/interfaces/api/b649_strategy_k_combinations.py"
PREFIX = "/api/v1/b649-strategy-k-combinations"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    result: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            result.add(node.module)
    return result


def test_application_contract_has_no_infrastructure_or_interface_dependency() -> None:
    imports = _imports(APPLICATION)
    assert not any(name.startswith("lottolab.infrastructure") for name in imports)
    assert not any(name.startswith("lottolab.interfaces") for name in imports)


def test_reader_has_no_recomputation_database_network_or_strategy_dependency() -> None:
    imports = _imports(READER)
    source = READER.read_text(encoding="utf-8").casefold()

    assert not any(name.startswith("lottolab.strategies") for name in imports)
    assert not any("candidate_success_matrix" in name for name in imports)
    assert not any(
        name in imports for name in ("gzip", "requests", "sqlite3", "subprocess", "urllib")
    )
    assert not any(
        token in source
        for token in (
            ".write_",
            'open("w',
            "open('w",
        )
    )


def test_api_is_get_only_and_has_no_execution_or_mutation_path() -> None:
    paths = create_app().openapi()["paths"]
    matching = {path: operations for path, operations in paths.items() if path.startswith(PREFIX)}

    assert len(matching) == 5
    assert all(set(operations) == {"get"} for operations in matching.values())
    assert not any(
        token in path
        for path in matching
        for token in ("execute", "generate", "recompute", "rerank", "write")
    )


def test_browser_contract_never_contains_the_local_authority_root() -> None:
    frontend = ROOT / "frontend/src"
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in frontend.rglob("*")
        if path.is_file() and path.suffix in {".ts", ".vue"}
    )
    assert "/Users/kelvin/" not in source
