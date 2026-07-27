"""Dependency and side-effect guards for the Candidate-K evaluation core."""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DOMAIN_MODULE = (
    REPO_ROOT / "src" / "lottolab" / "domain" / "ordered_candidate_evidence.py"
)
APPLICATION_MODULE = (
    REPO_ROOT / "src" / "lottolab" / "application" / "candidate_success_matrix.py"
)
MODULES = (DOMAIN_MODULE, APPLICATION_MODULE)


def _syntax_tree(module: Path) -> ast.Module:
    return ast.parse(module.read_text(encoding="utf-8"))


def _imports(module: Path) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(_syntax_tree(module)):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_candidate_core_modules_exist_and_parse() -> None:
    assert all(module.is_file() for module in MODULES)
    assert all(isinstance(_syntax_tree(module), ast.Module) for module in MODULES)


def test_domain_imports_only_stdlib_and_domain_draw_identity() -> None:
    assert _imports(DOMAIN_MODULE) <= {
        "__future__",
        "dataclasses",
        "enum",
        "json",
        "lottolab.domain.draws",
        "re",
        "types",
        "typing",
    }


def test_application_imports_only_stdlib_and_domain_contracts() -> None:
    imports = _imports(APPLICATION_MODULE)
    assert imports <= {
        "__future__",
        "dataclasses",
        "enum",
        "fractions",
        "json",
        "lottolab.domain.draws",
        "lottolab.domain.ordered_candidate_evidence",
        "lottolab.domain.strategy_success_evaluation",
        "lottolab.domain.strategy_success_measurement",
        "math",
    }
    assert not any(module.startswith("lottolab.infrastructure") for module in imports)
    assert not any(module.startswith("lottolab.interfaces") for module in imports)


def test_candidate_core_has_no_random_filesystem_db_network_clock_or_runtime_dependency() -> None:
    forbidden_imports = {
        "datetime",
        "http",
        "os",
        "pathlib",
        "random",
        "requests",
        "secrets",
        "socket",
        "sqlite3",
        "subprocess",
        "time",
        "urllib",
    }
    forbidden_calls = {
        "connect",
        "getenv",
        "now",
        "open",
        "read_bytes",
        "read_text",
        "time",
        "today",
        "urlopen",
        "utcnow",
        "write_bytes",
        "write_text",
    }
    for module in MODULES:
        imports = _imports(module)
        assert not {item.partition(".")[0] for item in imports} & forbidden_imports
        called_names: set[str] = set()
        for node in ast.walk(_syntax_tree(module)):
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Name):
                called_names.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                called_names.add(node.func.attr)
        assert not called_names & forbidden_calls


def test_candidate_core_has_no_binary_float_or_external_lifecycle_logic() -> None:
    forbidden_tokens = (
        "APIRouter",
        "ExecutableRegistry",
        "FastAPI",
        "deploy(",
        "publish(",
        "sqlite",
        "uvicorn",
    )
    for module in MODULES:
        tree = _syntax_tree(module)
        source = module.read_text(encoding="utf-8")
        assert not any(token in source for token in forbidden_tokens)
        assert not any(
            isinstance(node, ast.Constant) and type(node.value) is float
            for node in ast.walk(tree)
        )
        assert not any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "float"
            for node in ast.walk(tree)
        )


def test_donor_scripts_are_provenance_only_and_never_imported() -> None:
    imports: set[str] = set()
    for module in MODULES:
        imports.update(_imports(module))
    forbidden_prefixes = ("analysis", "lottery_api", "number_pattern_research")
    assert not any(
        imported.startswith(forbidden)
        for imported in imports
        for forbidden in forbidden_prefixes
    )
