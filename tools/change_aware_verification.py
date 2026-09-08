"""Change-aware verification preflight CLI and hermeticity scanner.

Automates verification selection and non-hermetic filesystem dependency detection
to prevent application architecture misses and runtime-artifact leakage in CI.
"""

from __future__ import annotations

import argparse
import ast
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]

READ_METHODS: set[str] = {
    "read_bytes",
    "read_text",
    "open",
    "iterdir",
    "glob",
    "rglob",
    "exists",
    "stat",
    "is_file",
    "is_dir",
    "lstat",
}

OS_READ_FUNCTIONS: set[str] = {
    "listdir",
    "scandir",
    "walk",
    "stat",
    "exists",
    "isfile",
    "isdir",
    "getsize",
    "getmtime",
}

SHUTIL_READ_FUNCTIONS: set[str] = {
    "copy",
    "copyfile",
    "copy2",
    "copytree",
}

PERSONAL_ENV_VARS: set[str] = {
    "HOME",
    "USERPROFILE",
    "APPDATA",
    "LOCALAPPDATA",
    "XDG_DATA_HOME",
    "XDG_CONFIG_HOME",
}


@dataclass(frozen=True)
class HermeticityFinding:
    rule_id: str
    file: str
    line: int
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "file": self.file,
            "line": self.line,
            "message": self.message,
        }


@dataclass(frozen=True)
class VerificationPlan:
    changed_paths: list[str]
    recommended_commands: list[str]
    hermeticity_findings: list[HermeticityFinding]
    rules_triggered: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "changed_paths": self.changed_paths,
            "recommended_commands": self.recommended_commands,
            "hermeticity_findings": [f.to_dict() for f in self.hermeticity_findings],
            "rules_triggered": self.rules_triggered,
        }


def _evaluate_expr_tags(node: ast.AST | None, var_tags: dict[str, set[str]]) -> set[str]:
    """Evaluate provenance tags for an AST expression within local dataflow scope."""
    if node is None:
        return set()

    if isinstance(node, ast.Name):
        return set(var_tags.get(node.id, set()))

    if isinstance(node, ast.Constant):
        if isinstance(node.value, str):
            val = node.value
            if val == ".task-data" or val.startswith((".task-data/", ".task-data\\")):
                return {"H001_PATH"}
            if val.startswith(("/Users/", "/home/")):
                return {"H003_PATH"}
            if val.startswith("~"):
                return {"H002_PATH"}
        return set()

    if isinstance(node, ast.BinOp):
        if isinstance(node.op, ast.Div):  # e.g., left / right
            left_tags = _evaluate_expr_tags(node.left, var_tags)
            right_tags = _evaluate_expr_tags(node.right, var_tags)
            if "SAFE_TEMP" in left_tags:
                return {"SAFE_TEMP"}
            combined: set[str] = set()
            if "H001_PATH" in left_tags or "H001_PATH" in right_tags:
                combined.add("H001_PATH")
            if "H002_PATH" in left_tags or "H002_PATH" in right_tags:
                combined.add("H002_PATH")
            if "H003_PATH" in left_tags or "H003_PATH" in right_tags:
                combined.add("H003_PATH")
            if "H004_PATH" in left_tags or "H004_PATH" in right_tags:
                combined.add("H004_PATH")
            return combined
        if isinstance(node.op, ast.Add):  # string concat, e.g. path + "/sub"
            left_tags = _evaluate_expr_tags(node.left, var_tags)
            right_tags = _evaluate_expr_tags(node.right, var_tags)
            if "SAFE_TEMP" in left_tags:
                return {"SAFE_TEMP"}
            return left_tags | right_tags

    if isinstance(node, ast.Call):
        # Path(...)
        if (isinstance(node.func, ast.Name) and node.func.id == "Path") or (
            isinstance(node.func, ast.Attribute) and node.func.attr == "Path"
        ):
            if node.args:
                return _evaluate_expr_tags(node.args[0], var_tags)
            return set()

        if isinstance(node.func, ast.Attribute):
            # Path.home()
            if node.func.attr == "home":
                return {"H002_PATH"}
            # os.path.expanduser(...) or p.expanduser()
            if node.func.attr == "expanduser":
                return {"H002_PATH"}
            # p.resolve(), p.absolute()
            if node.func.attr in ("resolve", "absolute"):
                return _evaluate_expr_tags(node.func.value, var_tags)
            # p.joinpath(...)
            if node.func.attr == "joinpath":
                val_tags = _evaluate_expr_tags(node.func.value, var_tags)
                if "SAFE_TEMP" in val_tags:
                    return {"SAFE_TEMP"}
                combined = set(val_tags)
                for arg in node.args:
                    combined.update(_evaluate_expr_tags(arg, var_tags))
                return combined

        # os.environ.get(...), os.getenv(...)
        if (
            isinstance(node.func, ast.Attribute)
            and node.func.attr in ("get", "getenv")
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
            and node.args[0].value in PERSONAL_ENV_VARS
        ):
            return {"H004_PATH"}

        # os.getenv(...) as Name
        if (
            isinstance(node.func, ast.Name)
            and node.func.id == "getenv"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
            and node.args[0].value in PERSONAL_ENV_VARS
        ):
            return {"H004_PATH"}

        # tempfile constructors
        func_name = ""
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            func_name = node.func.attr
        if func_name in ("TemporaryDirectory", "NamedTemporaryFile", "mkdtemp"):
            return {"SAFE_TEMP"}

    if (
        isinstance(node, ast.Subscript)
        and isinstance(node.value, ast.Attribute)
        and node.value.attr == "environ"
        and isinstance(node.slice, ast.Constant)
        and isinstance(node.slice.value, str)
        and node.slice.value in PERSONAL_ENV_VARS
    ):
        return {"H004_PATH"}

    return set()


def _format_finding(
    rule_id: str, file_path: str, lineno: int, prefix: str, call: ast.Call
) -> HermeticityFinding:
    snippet = ast.unparse(call)
    msg = f"{prefix}: {snippet}"
    return HermeticityFinding(rule_id=rule_id, file=file_path, line=lineno, message=msg)


def _check_call_for_violation(
    call: ast.Call, var_tags: dict[str, set[str]], file_path: str
) -> HermeticityFinding | None:
    """Check a single ast.Call node for non-hermetic filesystem access."""
    # Built-in open(...)
    if isinstance(call.func, ast.Name) and call.func.id == "open" and call.args:
        tags = _evaluate_expr_tags(call.args[0], var_tags)
        if "SAFE_TEMP" in tags:
            return None
        if "H001_PATH" in tags:
            return _format_finding(
                "H001",
                file_path,
                call.lineno,
                "Direct repository runtime read from '.task-data' via open()",
                call,
            )
        if "H002_PATH" in tags:
            return _format_finding(
                "H002", file_path, call.lineno, "Direct home-directory access via open()", call
            )
        if "H003_PATH" in tags:
            return _format_finding(
                "H003", file_path, call.lineno, "Absolute home path read via open()", call
            )
        if "H004_PATH" in tags:
            return _format_finding(
                "H004", file_path, call.lineno, "Personal env var path read via open()", call
            )
        return None

    # Path object methods
    if isinstance(call.func, ast.Attribute) and call.func.attr in READ_METHODS:
        tags = _evaluate_expr_tags(call.func.value, var_tags)
        if "SAFE_TEMP" in tags:
            return None
        if "H001_PATH" in tags:
            return _format_finding(
                "H001",
                file_path,
                call.lineno,
                "Direct repository runtime read from '.task-data'",
                call,
            )
        if "H002_PATH" in tags:
            return _format_finding(
                "H002", file_path, call.lineno, "Direct home-directory access", call
            )
        if "H003_PATH" in tags:
            return _format_finding(
                "H003", file_path, call.lineno, "Absolute home path read", call
            )
        if "H004_PATH" in tags:
            return _format_finding(
                "H004", file_path, call.lineno, "Personal env var path read", call
            )

    # os/os.path read functions
    if isinstance(call.func, ast.Attribute) and call.func.attr in OS_READ_FUNCTIONS and call.args:
        tags = _evaluate_expr_tags(call.args[0], var_tags)
        if "SAFE_TEMP" in tags:
            return None
        if "H001_PATH" in tags:
            return _format_finding(
                "H001",
                file_path,
                call.lineno,
                f"Direct repository runtime read from '.task-data' via {call.func.attr}()",
                call,
            )
        if "H002_PATH" in tags:
            return _format_finding(
                "H002",
                file_path,
                call.lineno,
                f"Direct home-directory access via {call.func.attr}()",
                call,
            )
        if "H003_PATH" in tags:
            return _format_finding(
                "H003",
                file_path,
                call.lineno,
                f"Absolute home path read via {call.func.attr}()",
                call,
            )
        if "H004_PATH" in tags:
            return _format_finding(
                "H004",
                file_path,
                call.lineno,
                f"Personal env var path read via {call.func.attr}()",
                call,
            )

    # shutil read functions (first arg is source input)
    if (
        isinstance(call.func, ast.Attribute)
        and call.func.attr in SHUTIL_READ_FUNCTIONS
        and call.args
    ):
        tags = _evaluate_expr_tags(call.args[0], var_tags)
        if "SAFE_TEMP" in tags:
            return None
        if "H001_PATH" in tags:
            return _format_finding(
                "H001",
                file_path,
                call.lineno,
                f"Direct repository runtime read from '.task-data' via shutil.{call.func.attr}()",
                call,
            )
        if "H002_PATH" in tags:
            return _format_finding(
                "H002",
                file_path,
                call.lineno,
                f"Direct home-directory access via shutil.{call.func.attr}()",
                call,
            )
        if "H003_PATH" in tags:
            return _format_finding(
                "H003",
                file_path,
                call.lineno,
                f"Absolute home path read via shutil.{call.func.attr}()",
                call,
            )
        if "H004_PATH" in tags:
            return _format_finding(
                "H004",
                file_path,
                call.lineno,
                f"Personal env var path read via shutil.{call.func.attr}()",
                call,
            )

    return None


def _scan_block_statements(
    stmts: list[ast.stmt],
    var_tags: dict[str, set[str]],
    file_path: str,
    findings: list[HermeticityFinding],
) -> None:
    """Scan a sequence of statements sequentially tracking local dataflow."""
    for stmt in stmts:
        # Check all calls inside the statement for violations
        for node in ast.walk(stmt):
            if isinstance(node, ast.Call):
                finding = _check_call_for_violation(node, var_tags, file_path)
                if finding:
                    findings.append(finding)

        # Track assignment dataflow
        if isinstance(stmt, ast.Assign):
            tags = _evaluate_expr_tags(stmt.value, var_tags)
            for target in stmt.targets:
                if isinstance(target, ast.Name):
                    var_tags[target.id] = set(tags)
        elif isinstance(stmt, ast.AnnAssign):
            if stmt.value is not None:
                tags = _evaluate_expr_tags(stmt.value, var_tags)
                if isinstance(stmt.target, ast.Name):
                    var_tags[stmt.target.id] = set(tags)
        elif isinstance(stmt, ast.With):
            for item in stmt.items:
                if isinstance(item.context_expr, ast.Call):
                    func_name = ""
                    if isinstance(item.context_expr.func, ast.Name):
                        func_name = item.context_expr.func.id
                    elif isinstance(item.context_expr.func, ast.Attribute):
                        func_name = item.context_expr.func.attr
                    if (
                        func_name in ("TemporaryDirectory", "NamedTemporaryFile")
                        and item.optional_vars
                        and isinstance(item.optional_vars, ast.Name)
                    ):
                        var_tags[item.optional_vars.id] = {"SAFE_TEMP"}
            _scan_block_statements(stmt.body, var_tags, file_path, findings)
        elif isinstance(stmt, (ast.If, ast.For, ast.While)):
            _scan_block_statements(stmt.body, var_tags, file_path, findings)
            if stmt.orelse:
                _scan_block_statements(stmt.orelse, var_tags, file_path, findings)
        elif isinstance(stmt, ast.Try):
            _scan_block_statements(stmt.body, var_tags, file_path, findings)
            for handler in stmt.handlers:
                _scan_block_statements(handler.body, var_tags, file_path, findings)
            if stmt.orelse:
                _scan_block_statements(stmt.orelse, var_tags, file_path, findings)
            if stmt.finalbody:
                _scan_block_statements(stmt.finalbody, var_tags, file_path, findings)


def scan_test_source_hermeticity(
    source: str, file_path: str = "<test>"
) -> list[HermeticityFinding]:
    """Scan Python test source for non-hermetic filesystem access patterns."""
    findings: list[HermeticityFinding] = []
    try:
        tree = ast.parse(source, filename=file_path)
    except SyntaxError:
        return findings

    # Module-level statements
    module_var_tags: dict[str, set[str]] = {}

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            func_var_tags = dict(module_var_tags)
            for arg in node.args.args:
                if arg.arg in ("tmp_path", "tmpdir", "tmp_path_factory"):
                    func_var_tags[arg.arg] = {"SAFE_TEMP"}
            _scan_block_statements(node.body, func_var_tags, file_path, findings)
        elif isinstance(node, ast.ClassDef):
            class_var_tags = dict(module_var_tags)
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    method_var_tags = dict(class_var_tags)
                    for arg in item.args.args:
                        if arg.arg in ("tmp_path", "tmpdir", "tmp_path_factory"):
                            method_var_tags[arg.arg] = {"SAFE_TEMP"}
                    _scan_block_statements(item.body, method_var_tags, file_path, findings)
                else:
                    _scan_block_statements([item], class_var_tags, file_path, findings)
        else:
            _scan_block_statements([node], module_var_tags, file_path, findings)

    findings.sort(key=lambda f: (f.file, f.line, f.rule_id, f.message))
    return findings


def scan_test_file_hermeticity(file_path: Path) -> list[HermeticityFinding]:
    """Read and scan a unit test file on disk for hermeticity violations."""
    if not file_path.is_file():
        return []
    try:
        content = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    return scan_test_source_hermeticity(content, file_path=str(file_path))


def generate_verification_plan(
    changed_paths: list[str],
    repo_root: Path | None = None,
) -> VerificationPlan:
    """Generate a verification plan and run hermeticity checks on changed paths."""
    if repo_root is None:
        repo_root = REPO_ROOT

    # Normalize changed paths to deterministic relative POSIX strings
    normalized_set: set[str] = set()
    for raw in changed_paths:
        p = Path(raw)
        if p.is_absolute():
            try:
                rel = p.resolve().relative_to(repo_root.resolve()).as_posix()
            except ValueError:
                rel = p.as_posix()
        else:
            rel = p.as_posix()
        # Clean leading ./
        if rel.startswith("./"):
            rel = rel[2:]
        if rel:
            normalized_set.add(rel)

    sorted_changed_paths = sorted(normalized_set)

    recommended_commands: list[str] = []
    rules_triggered: set[str] = set()
    hermeticity_findings: list[HermeticityFinding] = []

    # Rule V001: Application architecture
    has_app_change = any(
        p.startswith("src/lottolab/application/") and p.endswith(".py")
        for p in sorted_changed_paths
    )
    if has_app_change:
        rules_triggered.add("V001")
        recommended_commands.append("uv run pytest -q tests/architecture/test_dependency_rules.py")

    # Rule V002 & V005: Changed and adjacent unit tests
    unit_tests_to_run: set[str] = set()
    for p in sorted_changed_paths:
        # V002: changed unit tests
        if p.startswith("tests/unit/") and Path(p).name.startswith("test_") and p.endswith(".py"):
            unit_tests_to_run.add(p)
            rules_triggered.add("V002")

        # V005: adjacent direct unit test for changed application module
        if p.startswith("src/lottolab/application/") and p.endswith(".py"):
            stem = Path(p).stem
            candidate = f"tests/unit/test_{stem}.py"
            if (repo_root / candidate).is_file():
                unit_tests_to_run.add(candidate)
                rules_triggered.add("V005")

    if unit_tests_to_run:
        sorted_unit_tests = sorted(unit_tests_to_run)
        recommended_commands.append(f"uv run pytest -q {' '.join(sorted_unit_tests)}")

    # Rule V003: Python Ruff scope (canonical source/tool/test paths)
    canonical_roots = ("src/", "tools/", "tests/")
    ruff_targets = [
        p
        for p in sorted_changed_paths
        if p.endswith(".py")
        and any(p.startswith(root) for root in canonical_roots)
        and (repo_root / p).is_file()
    ]
    if ruff_targets:
        rules_triggered.add("V003")
        recommended_commands.append(f"uv run ruff check {' '.join(sorted(ruff_targets))}")

    # Rule V004: Python typecheck scope (implementation and tool paths)
    pyright_roots = ("src/", "tools/")
    pyright_targets = [
        p
        for p in sorted_changed_paths
        if p.endswith(".py")
        and any(p.startswith(root) for root in pyright_roots)
        and (repo_root / p).is_file()
    ]
    if pyright_targets:
        rules_triggered.add("V004")
        recommended_commands.append(f"uv run pyright {' '.join(sorted(pyright_targets))}")

    # Hermeticity scanner on changed unit tests
    for p in sorted_changed_paths:
        if p.startswith("tests/unit/") and Path(p).name.startswith("test_") and p.endswith(".py"):
            target_path = repo_root / p
            if target_path.is_file():
                file_findings = scan_test_file_hermeticity(target_path)
                for f in file_findings:
                    hermeticity_findings.append(f)
                    rules_triggered.add(f.rule_id)

    hermeticity_findings.sort(key=lambda f: (f.file, f.line, f.rule_id, f.message))
    sorted_rules_triggered = sorted(rules_triggered)

    return VerificationPlan(
        changed_paths=sorted_changed_paths,
        recommended_commands=recommended_commands,
        hermeticity_findings=hermeticity_findings,
        rules_triggered=sorted_rules_triggered,
    )


def format_text_output(plan: VerificationPlan) -> str:
    """Format verification plan and hermeticity findings as human-readable text."""
    lines: list[str] = []

    lines.append("CHANGED_PATHS")
    if plan.changed_paths:
        for p in plan.changed_paths:
            lines.append(f"  {p}")
    else:
        lines.append("  (none)")
    lines.append("")

    lines.append("RECOMMENDED_CHECKS")
    if plan.recommended_commands:
        for cmd in plan.recommended_commands:
            lines.append(f"  {cmd}")
    else:
        lines.append("  (none)")
    lines.append("")

    lines.append("HERMETICITY_FINDINGS")
    if plan.hermeticity_findings:
        for f in plan.hermeticity_findings:
            lines.append(f"  {f.file}:{f.line} [{f.rule_id}] {f.message}")
    else:
        lines.append("  None")

    return "\n".join(lines)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Change-aware verification preflight and hermeticity check.",
    )
    parser.add_argument(
        "--changed-path",
        action="append",
        dest="changed_paths",
        default=[],
        help="Explicit changed path (repeatable for Mode A).",
    )
    parser.add_argument(
        "--base-ref",
        default=None,
        help="Git base ref for range diff (Mode B).",
    )
    parser.add_argument(
        "--head-ref",
        default=None,
        help="Git head ref for range diff (Mode B).",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text).",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Optional override for repository root.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    repo_root = args.repo_root or REPO_ROOT

    has_explicit = bool(args.changed_paths)
    has_base = args.base_ref is not None
    has_head = args.head_ref is not None

    if has_explicit and (has_base or has_head):
        sys.stderr.write(
            "Usage error: Cannot mix --changed-path with --base-ref/--head-ref.\n"
        )
        return 64

    if (has_base and not has_head) or (has_head and not has_base):
        sys.stderr.write(
            "Usage error: Both --base-ref and --head-ref are required for Git range mode.\n"
        )
        return 64

    if not has_explicit and not (has_base and has_head):
        sys.stderr.write(
            "Usage error: Provide repeatable --changed-path or both --base-ref and --head-ref.\n"
        )
        return 64

    changed_paths: list[str] = []

    if has_explicit:
        changed_paths = list(args.changed_paths)
    else:
        # Git range mode
        cmd = [
            "git",
            "diff",
            "--name-only",
            "--diff-filter=ACMRT",
            f"{args.base_ref}...{args.head_ref}",
        ]
        proc = subprocess.run(
            cmd,
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            # Fallback to direct two-arg diff if range syntax fails
            fallback_cmd = [
                "git",
                "diff",
                "--name-only",
                "--diff-filter=ACMRT",
                args.base_ref,
                args.head_ref,
            ]
            fallback_proc = subprocess.run(
                fallback_cmd,
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=False,
            )
            if fallback_proc.returncode != 0:
                sys.stderr.write(f"git diff failed ({proc.returncode}): {proc.stderr}\n")
                return 1
            proc = fallback_proc

        changed_paths = [line.strip() for line in proc.stdout.splitlines() if line.strip()]

    plan = generate_verification_plan(changed_paths, repo_root=repo_root)

    if args.format == "json":
        print(json.dumps(plan.to_dict(), indent=2))
    else:
        print(format_text_output(plan))

    if plan.hermeticity_findings:
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
