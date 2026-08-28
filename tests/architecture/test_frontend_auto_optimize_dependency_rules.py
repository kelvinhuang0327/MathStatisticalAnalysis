"""Architecture proof for the local AutoOptimize orchestration boundary."""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ADAPTER = (
    REPO_ROOT
    / "src"
    / "lottolab"
    / "strategies"
    / "adapters"
    / "biglotto_frontend_auto_optimize.py"
)


def _tree() -> ast.Module:
    return ast.parse(ADAPTER.read_text(encoding="utf-8"))


def _imports() -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(_tree()):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            modules.add(node.module)
    return modules


def _called_names() -> set[str]:
    names: set[str] = set()
    for node in ast.walk(_tree()):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name):
            names.add(node.func.id)
        elif isinstance(node.func, ast.Attribute):
            names.add(node.func.attr)
    return names


def test_adapter_exists_only_in_strategy_layer() -> None:
    assert ADAPTER.is_file()


def test_adapter_uses_only_local_or_existing_strategy_dependencies() -> None:
    imports = _imports()
    assert imports.isdisjoint(
        {
            "numpy",
            "scipy",
            "sqlite3",
            "sqlalchemy",
            "subprocess",
            "socket",
            "requests",
            "httpx",
        }
    )
    assert not any(
        module.startswith(
            (
                "lottolab.application",
                "lottolab.infrastructure",
                "lottolab.interfaces",
            )
        )
        for module in imports
    )
    source = ADAPTER.read_text(encoding="utf-8")
    assert "auto_optimizer_alpha" not in source
    assert "tools/auto_optimizer_alpha.py" not in source


def test_adapter_has_no_persistence_network_or_outer_layer_call_surface() -> None:
    calls = _called_names()
    assert calls.isdisjoint(
        {
            "connect",
            "execute",
            "executemany",
            "commit",
            "rollback",
            "open",
            "write_text",
            "write_bytes",
            "request",
            "urlopen",
        }
    )


def test_candidate_order_validation_and_local_rng_contract_are_frozen() -> None:
    source = ADAPTER.read_text(encoding="utf-8")
    expected_order = (
        "frequency",
        "trend",
        "bayesian",
        "montecarlo",
        "markov",
        "deviation",
        "ensemble_weighted",
        "ensemble_boosting",
        "ensemble_features",
        "ml_forest",
        "collaborative_hybrid",
        "hot_cold",
        "sum_range",
        "statistical",
    )
    assert "_CANDIDATE_ORDER: Final" in source
    assert source.index('"frequency"') < source.index('"statistical"')
    for candidate in expected_order:
        assert f'"{candidate}"' in source
    for expert in (
        "Frequency",
        "Trend",
        "Combined",
        "Bayesian",
        "Deviation",
        "MonteCarlo",
        "Markov",
        "CoOccurrence",
        "FeatureWeighted",
        "RandomForest",
        "GeneticAlgorithm",
    ):
        assert f'"{expert}"' in source
    assert "Promise.allSettled" in source
    assert "deque" in source
    assert "_MAX_DATA_SIZE: Final = 500" in source
    assert "_MIN_HISTORY: Final = 30" in source
    assert "def __init__(self, rng: _RandomSource | None = None)" in source
    assert "rng.random()" in source
    assert "random.seed(" not in source
    assert "GenerateOneBetInput.seed" not in source


def test_no_generic_score_probability_or_rng_contract_was_added() -> None:
    public_api = (
        REPO_ROOT / "src" / "lottolab" / "strategies" / "adapters" / "base.py"
    ).read_text(encoding="utf-8")
    assert "class Score" not in public_api
    assert "class Probability" not in public_api
    assert "class RandomSource" not in public_api
