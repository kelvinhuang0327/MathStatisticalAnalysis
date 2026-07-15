"""Dependency direction is a contract enforced by CI, not by code review.

domain          → (nothing else in lottolab)
strategies      → domain
application     → domain, strategies
infrastructure  → domain, strategies, application (implements ports)
interfaces      → anything (composition root)
"""

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src" / "lottolab"

FORBIDDEN: dict[str, tuple[str, ...]] = {
    "domain": ("application", "interfaces", "infrastructure", "strategies"),
    "strategies": ("application", "interfaces", "infrastructure"),
    "application": ("interfaces", "infrastructure"),
    "infrastructure": ("interfaces",),
}


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_layer_dependencies() -> None:
    violations: list[str] = []
    for layer, forbidden_layers in FORBIDDEN.items():
        for path in (SRC / layer).rglob("*.py"):
            for module in imported_modules(path):
                for forbidden in forbidden_layers:
                    prefix = f"lottolab.{forbidden}"
                    if module == prefix or module.startswith(prefix + "."):
                        violations.append(f"{path.relative_to(SRC)} imports {module}")
    assert not violations, "layer violations:\n" + "\n".join(violations)


def _lottolab_module_path(module: str) -> Path | None:
    if module == "lottolab":
        return SRC / "__init__.py"
    if not module.startswith("lottolab."):
        return None
    relative = Path(*module.removeprefix("lottolab.").split("."))
    module_file = (SRC / relative).with_suffix(".py")
    if module_file.is_file():
        return module_file
    package_file = SRC / relative / "__init__.py"
    return package_file if package_file.is_file() else None


def _transitive_imports(start: str) -> set[str]:
    pending = [start]
    visited: set[str] = set()
    found: set[str] = set()
    while pending:
        module = pending.pop()
        if module in visited:
            continue
        visited.add(module)
        path = _lottolab_module_path(module)
        if path is None:
            continue
        imports = imported_modules(path)
        found.update(imports)
        pending.extend(item for item in imports if item.startswith("lottolab"))
    return found


def test_strategy_catalog_request_path_has_no_database_dependency() -> None:
    imports = _transitive_imports("lottolab.interfaces.api.strategy_catalog")
    assert "sqlite3" not in imports
    assert not any(module.startswith("lottolab.infrastructure") for module in imports)


def test_catalog_does_not_import_adapters() -> None:
    imports = imported_modules(SRC / "strategies" / "catalog.py")
    assert "importlib" not in imports
    assert "lottolab.strategies.executable_registry" not in imports
    assert not any("adapter" in module for module in imports)


def test_production_code_does_not_import_legacy_or_migration_fixtures() -> None:
    violations: list[str] = []
    for path in SRC.rglob("*.py"):
        for module in imported_modules(path):
            if module.startswith(("lottery_api", "tests", "tools")):
                violations.append(f"{path.relative_to(SRC)} imports {module}")
    assert not violations, "production import violations:\n" + "\n".join(violations)


def test_local_runtime_path_has_no_database_or_execution_dependency() -> None:
    forbidden_fragments = (
        "sqlite",
        "lotterynew",
        "generation",
        "prediction",
        "replay",
        "evaluation",
        "scheduler",
        "fixture",
        "artifact",
    )
    for module in (
        "lottolab.application.local_runtime",
        "lottolab.infrastructure.local_runtime",
    ):
        imports = _transitive_imports(module)
        lowered = {imported.lower() for imported in imports}
        assert not any(
            fragment in imported for imported in lowered for fragment in forbidden_fragments
        ), module


def test_local_runtime_cli_contains_no_process_or_network_supervisor_logic() -> None:
    imports = imported_modules(SRC / "interfaces" / "cli" / "main.py")
    assert imports.isdisjoint(
        {
            "fcntl",
            "json",
            "os",
            "signal",
            "socket",
            "subprocess",
            "tempfile",
            "urllib",
            "urllib.request",
        }
    )


def test_local_runtime_policy_does_not_import_infrastructure() -> None:
    imports = imported_modules(SRC / "application" / "local_runtime.py")
    assert not any(module.startswith("lottolab.infrastructure") for module in imports)
