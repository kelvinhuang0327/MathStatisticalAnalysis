from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DOMAIN = REPO_ROOT / "src/lottolab/domain/historical_prefix_analytics.py"
APPLICATION = REPO_ROOT / "src/lottolab/application/use_cases/analyze_historical_prefixes.py"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            modules.add(node.module)
    return modules


def test_historical_prefix_production_modules_exist() -> None:
    assert DOMAIN.is_file()
    assert APPLICATION.is_file()


def test_domain_imports_only_domain_modules_and_safe_standard_library() -> None:
    imports = _imports(DOMAIN)
    assert not any(
        module.startswith(
            (
                "lottolab.application",
                "lottolab.infrastructure",
                "lottolab.interfaces",
                "lottolab.evidence",
            )
        )
        for module in imports
    )
    assert not imports & {"os", "pathlib", "sqlite3", "subprocess", "socket", "requests"}


def test_application_imports_no_infrastructure_or_interfaces() -> None:
    imports = _imports(APPLICATION)
    assert not any(
        module.startswith(("lottolab.infrastructure", "lottolab.interfaces")) for module in imports
    )


def test_production_has_no_test_legacy_execution_or_outcome_advice_imports() -> None:
    for path in (DOMAIN, APPLICATION):
        source = path.read_text(encoding="utf-8")
        imports = _imports(path)
        assert not any(module.startswith("tests") for module in imports)
        assert "LotteryNew" not in source
        assert "number-pattern-research" not in source
        assert "execute_strategy" not in source
        assert "ROI" not in source
        assert "expected_value" not in source
