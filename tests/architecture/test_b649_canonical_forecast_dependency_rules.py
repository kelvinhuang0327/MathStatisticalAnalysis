"""Architecture rules for the B649 canonical forecast integration."""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DOMAIN = REPO_ROOT / "src/lottolab/domain/b649_canonical_consensus.py"
APPLICATION = REPO_ROOT / "src/lottolab/application/b649_canonical_forecast_materialization.py"
INFRASTRUCTURE = REPO_ROOT / "src/lottolab/infrastructure/b649_canonical_forecast_writer.py"
SCHEDULER = REPO_ROOT / "tools/b649_goalc_local_scheduler.py"
COMPATIBILITY = REPO_ROOT / "tools/materialize_b649_canonical_forecast.py"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imports.add(node.module)
    return imports


def test_domain_is_pure_and_has_no_087_target_constant() -> None:
    imports = _imports(DOMAIN)
    assert not any(name.startswith("lottolab.") for name in imports)
    assert not imports & {
        "pathlib",
        "os",
        "sqlite3",
        "subprocess",
        "socket",
        "requests",
    }
    source = DOMAIN.read_text(encoding="utf-8")
    assert "115000087" not in source
    assert "TARGET_DRAW" not in source
    assert "MAX_DATA_CUTOFF" not in source


def test_application_owns_orchestration_without_infrastructure_or_tool_dependency() -> None:
    imports = _imports(APPLICATION)
    assert not any(
        name.startswith(("lottolab.infrastructure", "lottolab.interfaces", "tools."))
        for name in imports
    )
    assert "115000087" not in APPLICATION.read_text(encoding="utf-8")


def test_infrastructure_writer_does_not_depend_on_application_or_domain() -> None:
    imports = _imports(INFRASTRUCTURE)
    assert not any(name.startswith("lottolab.") for name in imports)


def test_scheduler_consumes_immutable_authority_and_keeps_materializer_standalone() -> None:
    source = SCHEDULER.read_text(encoding="utf-8")
    assert "_load_canonical_forecast_authority" in source
    assert "read_existing_bytes" in source
    assert "materialize_canonical_forecast" in source
    assert "def materialize_predraw_forecast(" in source
    assert "def materialize_forecast(" not in source
    assert "build_canonical_predraw_consensus" not in source
    assert "tools.materialize_b649_canonical_forecast" not in source
    assert "next_draw_rollover_status" in source
    assert "forecast_materialization" in source
    forecast_source = source.split("def _forecast_command(", 1)[1].split(
        "def _status_command(", 1
    )[0]
    assert "materialize_canonical_forecast" not in forecast_source
    assert "inspect_predictions" not in forecast_source
    assert "def materialize_canonical_forecast(" in APPLICATION.read_text(encoding="utf-8")
    assert "materialize_canonical_forecast" in COMPATIBILITY.read_text(encoding="utf-8")


def test_087_constants_are_confined_to_explicit_compatibility_adapter() -> None:
    assert "115000087" in COMPATIBILITY.read_text(encoding="utf-8")
    assert "TARGET_DRAW_NUMBER" in COMPATIBILITY.read_text(encoding="utf-8")
