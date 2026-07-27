"""Architecture guards for the ordered candidate emission core."""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src" / "lottolab"
DOMAIN_MODULE = SRC / "domain" / "ordered_candidate_emission.py"
APPLICATION_MODULE = (
    SRC / "application" / "use_cases" / "generate_ordered_candidate_emission.py"
)
EVIDENCE_MODULE = SRC / "evidence" / "ordered_candidate_emission_artifact.py"
MODULES = (DOMAIN_MODULE, APPLICATION_MODULE, EVIDENCE_MODULE)


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def _imports(path: Path) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_ordered_candidate_emission_modules_exist_and_parse() -> None:
    assert all(path.is_file() for path in MODULES)
    assert all(isinstance(_tree(path), ast.Module) for path in MODULES)


def test_domain_module_depends_only_on_stdlib_and_domain_contracts() -> None:
    imports = _imports(DOMAIN_MODULE)

    assert imports <= {
        "__future__",
        "dataclasses",
        "enum",
        "lottolab.domain.draws",
        "lottolab.domain.ordered_candidate_evidence",
        "re",
    }


def test_application_module_never_depends_on_evidence_or_outer_layers() -> None:
    imports = _imports(APPLICATION_MODULE)

    assert not any(
        module.startswith(
            (
                "lottolab.evidence",
                "lottolab.infrastructure",
                "lottolab.interfaces",
            )
        )
        for module in imports
    )


def test_evidence_module_reuses_lcj1_and_never_depends_on_application() -> None:
    imports = _imports(EVIDENCE_MODULE)

    assert "lottolab.evidence.canonical_json" in imports
    assert "hashlib" not in imports
    assert "json" not in imports
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
    )


def test_core_modules_have_no_runtime_or_external_side_effect_dependencies() -> None:
    forbidden_roots = {
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
    for path in MODULES:
        imports = _imports(path)
        assert not {name.partition(".")[0] for name in imports} & forbidden_roots
        called_names: set[str] = set()
        for node in ast.walk(_tree(path)):
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Name):
                called_names.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                called_names.add(node.func.attr)
        assert not called_names & forbidden_calls


def test_artifact_module_contains_no_external_source_identity_fields() -> None:
    source = EVIDENCE_MODULE.read_text(encoding="utf-8")

    for forbidden in (
        '"repository"',
        '"commit_oid"',
        '"path"',
        '"artifact_sha256"',
        '"final_serialized_bytes_sha256"',
    ):
        assert forbidden not in source
