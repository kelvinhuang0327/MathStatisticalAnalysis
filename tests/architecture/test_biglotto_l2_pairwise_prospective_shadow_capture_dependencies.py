from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE = (
    REPO_ROOT
    / "src"
    / "lottolab"
    / "application"
    / "biglotto_l2_pairwise_prospective_shadow_capture.py"
)

FORBIDDEN_LATER_STAGE_NAMES = {
    "read_current_outcome",
    "refresh_reporting",
    "rescore_target",
    "resolve_official_outcome",
    "score_prediction",
    "update_outcome",
}


def _tree() -> ast.Module:
    return ast.parse(MODULE.read_text(encoding="utf-8"))


def _imports() -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(_tree()):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_capture_module_uses_inner_contracts_and_no_outer_runtime_layer() -> None:
    imports = _imports()

    assert "lottolab.evidence.canonical_json" in imports
    assert "lottolab.domain.ordered_candidate_emission" in imports
    assert "lottolab.domain.pre_outcome_target" in imports
    assert not any(
        module.startswith(("lottolab.infrastructure", "lottolab.interfaces"))
        for module in imports
    )


def test_capture_service_has_no_later_stage_port_or_call() -> None:
    tree = _tree()
    service = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "ProspectiveShadowCaptureService"
    )
    public_methods = {
        node.name
        for node in service.body
        if isinstance(node, ast.FunctionDef) and not node.name.startswith("_")
    }
    called_names = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }

    assert public_methods == {"capture", "seal"}
    assert called_names.isdisjoint(FORBIDDEN_LATER_STAGE_NAMES)
    assert "ForwardAutoCycleCore" not in MODULE.read_text(encoding="utf-8")
