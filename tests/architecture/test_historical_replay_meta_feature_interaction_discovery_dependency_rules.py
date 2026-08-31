"""Architecture and forbidden-surface guards for R2 interaction discovery."""

from __future__ import annotations

import ast
import hashlib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CORE = (
    REPO_ROOT
    / "src"
    / "lottolab"
    / "research"
    / "historical_replay_meta_feature_interaction_discovery.py"
)
ADAPTER = (
    REPO_ROOT
    / "src"
    / "lottolab"
    / "infrastructure"
    / "historical_replay_meta_feature_interaction_corpus.py"
)
REPOSITORY = (
    REPO_ROOT / "src" / "lottolab" / "infrastructure" / "persistence" / "research_repository.py"
)
NATIVE_STUDY = REPO_ROOT / "src" / "lottolab" / "research" / "native_study.py"
NATIVE_STUDY_BASE_SHA256 = "582410f9b6ada482835ad43aaa30a79b0ac17c6b90251e58000d2fa2b522f41d"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    result: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            result.add(node.module)
    return result


def test_native_study_engine_is_byte_unchanged_from_the_pinned_base() -> None:
    assert hashlib.sha256(NATIVE_STUDY.read_bytes()).hexdigest() == NATIVE_STUDY_BASE_SHA256


def test_pure_core_has_no_database_filesystem_optimizer_or_random_dependency() -> None:
    imports = _imports(CORE)
    forbidden_roots = {
        "numpy",
        "optuna",
        "ortools",
        "os",
        "pathlib",
        "random",
        "scipy",
        "sklearn",
        "sqlite3",
    }

    assert not {item.partition(".")[0] for item in imports} & forbidden_roots
    assert not any(item.startswith("lottolab.infrastructure") for item in imports)


def test_storage_adapter_is_explicitly_read_only_and_has_no_sql_mutation() -> None:
    source = ADAPTER.read_text(encoding="utf-8")
    upper = source.upper()

    assert "mode=ro" in source
    assert "PRAGMA query_only = ON" in source
    for forbidden in ("INSERT INTO", "UPDATE ", "DELETE FROM", "CREATE TABLE", "DROP TABLE"):
        assert forbidden not in upper


def test_repository_query_caps_every_label_bearing_surface_at_discovery() -> None:
    source = REPOSITORY.read_text(encoding="utf-8")
    function = source[source.index("def fetch_historical_replay_discovery_corpus_rows(") :]

    assert function.count("last_target_draw_date") >= 7
    assert function.count("last_target_draw_number") >= 4
    assert "result.main_hit_count" in function
    assert "target.target_draw_date < ?" in function
    assert "CAST(target.target_draw_number AS INTEGER) <= ?" in function


def test_core_contains_no_binary_float_authority_or_confirmed_signal_claim() -> None:
    source = CORE.read_text(encoding="utf-8")
    tree = ast.parse(source)

    assert "CONFIRMED_SIGNAL" not in source
    assert not any(
        isinstance(node, ast.Constant) and type(node.value) is float for node in ast.walk(tree)
    )
