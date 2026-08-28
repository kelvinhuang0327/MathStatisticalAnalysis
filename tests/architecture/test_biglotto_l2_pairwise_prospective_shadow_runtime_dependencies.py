from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE = (
    REPO_ROOT
    / "src"
    / "lottolab"
    / "application"
    / "biglotto_l2_pairwise_prospective_shadow_runtime.py"
)


def test_nine_candidate_runtime_is_prediction_only_application_wiring() -> None:
    source = MODULE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }

    assert "lottolab.application.biglotto_l2_pairwise_prospective_shadow_capture" in imports
    assert any(module == "lottolab.research" for module in imports)
    assert not any(
        module.startswith(("lottolab.infrastructure", "lottolab.interfaces"))
        for module in imports
    )
    assert all(
        forbidden not in source.casefold()
        for forbidden in ("official_outcome", "score_prediction", "refresh_reporting")
    )
