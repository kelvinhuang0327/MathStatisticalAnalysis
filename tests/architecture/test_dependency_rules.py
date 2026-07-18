"""Dependency direction is a contract enforced by CI, not by code review.

domain          → (nothing else in lottolab)
strategies      → domain
application     → domain, strategies
infrastructure  → domain, strategies, application (implements ports)
evidence        → domain (stdlib and Pydantic only otherwise; no data path, no runtime)
normalization   → domain, evidence models/canonical JSON
interfaces      → anything (composition root)
"""

import ast
import os
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src" / "lottolab"

FORBIDDEN: dict[str, tuple[str, ...]] = {
    "domain": ("application", "interfaces", "infrastructure", "strategies", "evidence"),
    "strategies": ("application", "interfaces", "infrastructure"),
    "application": ("interfaces", "infrastructure"),
    "infrastructure": ("interfaces",),
    "evidence": ("application", "interfaces", "infrastructure", "strategies"),
    "normalization": ("application", "interfaces", "infrastructure", "strategies"),
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


def test_strategy_adapters_are_target_native_db_free_and_offline() -> None:
    """Inspect declared project dependencies, never incidental ``sys.modules`` state."""

    imports: set[str] = set()
    for module in (
        "lottolab.strategies.adapters",
        "lottolab.strategies.adapters.base",
        "lottolab.strategies.adapters.biglotto_selected",
    ):
        imports.update(_transitive_imports(module))

    forbidden_exact = {
        "http.client",
        "importlib",
        "os",
        "pathlib",
        "socket",
        "sqlite3",
        "subprocess",
        "time",
        "urllib",
        "urllib.request",
    }
    forbidden_prefixes = (
        "lottery_api",
        "number_pattern_research",
        "lottolab.application",
        "lottolab.infrastructure",
        "lottolab.interfaces",
    )
    forbidden_project_fragments = (".database", ".db_", ".persistence")
    violations = sorted(
        module
        for module in imports
        if module in forbidden_exact
        or module.startswith(forbidden_prefixes)
        or (
            module.startswith("lottolab.")
            and any(fragment in module.casefold() for fragment in forbidden_project_fragments)
        )
    )
    assert not violations, "adapter dependency violations:\n" + "\n".join(violations)


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


def test_domain_has_no_database_api_or_frontend_dependency() -> None:
    forbidden = {"sqlite3", "fastapi", "pydantic"}
    for path in (SRC / "domain").rglob("*.py"):
        imports = imported_modules(path)
        assert imports.isdisjoint(forbidden), path
        assert not any(
            module.startswith(("lottolab.infrastructure", "lottolab.interfaces"))
            for module in imports
        ), path


def test_application_owns_draw_data_ports_and_use_cases() -> None:
    ports = (SRC / "application" / "ports.py").read_text(encoding="utf-8")
    assert "class DrawRepository(Protocol)" in ports
    assert "class DrawImportRepository(Protocol)" in ports
    assert "class IngestionRunRepository(Protocol)" in ports
    assert "apply_valid_import" in ports
    for use_case in ("draw_imports.py", "draw_history.py"):
        imports = imported_modules(SRC / "application" / "use_cases" / use_case)
        assert not any(module.startswith("lottolab.infrastructure") for module in imports)


def test_api_adapters_contain_no_sql_or_sqlite_calls() -> None:
    sql = re.compile(r"\b(?:SELECT|INSERT\s+INTO|UPDATE|DELETE\s+FROM|PRAGMA)\b")
    for path in (SRC / "interfaces" / "api").rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        imports = imported_modules(path)
        assert "sqlite3" not in imports, path
        assert sql.search(source) is None, path


def test_frontend_knows_api_contract_not_sqlite_schema_or_raw_html() -> None:
    frontend = SRC.parents[1] / "frontend" / "src"
    forbidden = (
        "main_numbers_json",
        "schema_migrations",
        "sqlite3",
        "v-html",
    )
    for path in frontend.rglob("*"):
        if path.suffix not in {".ts", ".vue"}:
            continue
        lowered = path.read_text(encoding="utf-8").casefold()
        assert not any(fragment.casefold() in lowered for fragment in forbidden), path

    data_center = (frontend / "features" / "data-center" / "DataCenterPage.vue").read_text(
        encoding="utf-8"
    )
    assert not any(
        storage in data_center for storage in ("localStorage", "sessionStorage", "indexedDB")
    )


def test_evidence_imports_no_infrastructure_or_sqlite() -> None:
    for path in (SRC / "evidence").rglob("*.py"):
        imports = imported_modules(path)
        assert "sqlite3" not in imports, path
        assert not any(
            module.startswith(
                (
                    "lottolab.infrastructure",
                    "lottolab.interfaces",
                    "lottolab.application",
                    "lottolab.strategies",
                )
            )
            for module in imports
        ), path


def test_evidence_transitively_imports_no_sqlite_or_forbidden_layer() -> None:
    for module in (
        "lottolab.evidence.canonical_json",
        "lottolab.evidence.models",
        "lottolab.evidence.validator",
        "lottolab.evidence.comparability",
    ):
        imports = _transitive_imports(module)
        assert "sqlite3" not in imports, module
        assert not any(
            imported.startswith(
                (
                    "lottolab.infrastructure",
                    "lottolab.interfaces",
                    "lottolab.application",
                    "lottolab.strategies",
                )
            )
            for imported in imports
        ), module


def test_normalization_imports_only_domain_and_evidence_contract_layers() -> None:
    for path in (SRC / "normalization").rglob("*.py"):
        imports = imported_modules(path)
        assert "sqlite3" not in imports, path
        assert not any(
            module.startswith(
                (
                    "lottolab.application",
                    "lottolab.infrastructure",
                    "lottolab.interfaces",
                    "lottolab.strategies",
                )
            )
            for module in imports
        ), path


def test_evidence_does_not_import_normalization() -> None:
    for path in (SRC / "evidence").rglob("*.py"):
        assert not any(
            module.startswith("lottolab.normalization") for module in imported_modules(path)
        ), path


def test_normalization_does_not_import_tolerant_csv_or_effectful_modules() -> None:
    imports = _transitive_imports("lottolab.normalization.normalizer")
    assert "lottolab.infrastructure.imports.csv_draws" not in imports
    assert imports.isdisjoint(
        {
            "csv",
            "http.client",
            "httpx",
            "os",
            "random",
            "requests",
            "socket",
            "sqlite3",
            "subprocess",
            "time",
            "urllib",
            "urllib.request",
        }
    )


def test_evidence_provenance_git_boundary_is_read_only_db_free_and_offline() -> None:
    from lottolab.evidence import validator

    imports = imported_modules(SRC / "evidence" / "validator.py")
    assert imports.isdisjoint(
        {
            "http.client",
            "httpx",
            "requests",
            "socket",
            "sqlite3",
            "urllib",
            "urllib.request",
        }
    )
    allowed_subcommands: object = vars(validator)["_READ_ONLY_GIT_SUBCOMMANDS"]
    assert frozenset({"cat-file", "merge-base", "rev-parse"}) == allowed_subcommands


def _run_isolated(code: str, data_dir: Path) -> None:
    env = {**os.environ, "LOTTOLAB_DATA_DIR": str(data_dir)}
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert not data_dir.exists(), f"{data_dir} was created as a side effect"


def test_importing_evidence_creates_no_data_directory(tmp_path: Path) -> None:
    data_dir = tmp_path / "nonexistent-data"
    _run_isolated(
        "import lottolab.evidence.canonical_json\n"
        "import lottolab.evidence.models\n"
        "import lottolab.evidence.validator\n"
        "import lottolab.evidence.comparability\n",
        data_dir,
    )


def test_schema_generation_creates_no_data_directory(tmp_path: Path) -> None:
    data_dir = tmp_path / "nonexistent-data"
    env = {**os.environ, "LOTTOLAB_DATA_DIR": str(data_dir)}
    result = subprocess.run(
        [sys.executable, "tools/generate_evidence_schemas.py", "--check"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert not data_dir.exists()


def test_cli_validation_creates_no_data_directory_or_db(tmp_path: Path) -> None:
    data_dir = tmp_path / "nonexistent-data"
    env = {**os.environ, "LOTTOLAB_DATA_DIR": str(data_dir)}
    result = subprocess.run(
        [
            sys.executable,
            "tools/validate_evaluation_evidence.py",
            "tests/fixtures/evidence/synthetic/evaluation_evidence.json",
            "--dataset",
            "tests/fixtures/evidence/synthetic/dataset_snapshot.json",
        ],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert not data_dir.exists(), "CLI validation must never create a database or data directory"
