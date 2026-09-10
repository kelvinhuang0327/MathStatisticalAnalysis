"""Change-aware verification preflight CLI and hermeticity scanner.

Automates verification selection and non-hermetic filesystem dependency detection
to prevent application architecture misses and runtime-artifact leakage in CI.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

REPO_ROOT = Path(__file__).resolve().parents[1]

CANONICAL_CURRENT_AUTHORITY_PATH = "docs/research/cross_lottery_research_ledger_r1.json"
PINNED_SOURCE_REFRESH_RULE = "PINNED_SOURCE_AUTHORITY_REFRESH_REQUIRED"
CURRENT_AUTHORITY_PIN_KINDS = ("source_files", "correctness_evidence")
STRUCTURAL_VERIFICATION_COMMAND = (
    "uv run pytest -q tests/contract/test_strategy_matrix_structural_api.py "
    "tests/unit/test_strategy_matrix_structural_projection_builder.py "
    "tests/unit/test_strategy_matrix_structural_reader.py"
)

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
class PinnedSourceConsumer:
    source_path: str
    consumer_path: str
    consumer_id: str
    pin_kind: str
    status: str
    pinned_sha256: str | None
    snapshot_sha256: str | None
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_path": self.source_path,
            "consumer_path": self.consumer_path,
            "consumer_id": self.consumer_id,
            "pin_kind": self.pin_kind,
            "status": self.status,
            "pinned_sha256": self.pinned_sha256,
            "snapshot_sha256": self.snapshot_sha256,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class VerificationPlan:
    changed_paths: list[str]
    recommended_commands: list[str]
    hermeticity_findings: list[HermeticityFinding]
    rules_triggered: list[str]
    pinned_source_consumers: list[PinnedSourceConsumer]

    def to_dict(self) -> dict[str, Any]:
        return {
            "changed_paths": self.changed_paths,
            "recommended_commands": self.recommended_commands,
            "hermeticity_findings": [f.to_dict() for f in self.hermeticity_findings],
            "rules_triggered": self.rules_triggered,
            "pinned_source_consumers": [h.to_dict() for h in self.pinned_source_consumers],
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


def _normalize_repo_relpath(raw: str) -> str | None:
    rel = Path(raw).as_posix()
    if rel.startswith("./"):
        rel = rel[2:]
    if not rel or rel.startswith("/") or ".." in Path(rel).parts:
        return None
    return rel


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _is_sha256_hex(value: object) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    return all(char in "0123456789abcdefABCDEF" for char in value)


def _read_snapshot_bytes(
    repo_root: Path,
    relative_path: str,
    snapshot_ref: str | None,
) -> bytes | None:
    rel = _normalize_repo_relpath(relative_path)
    if rel is None:
        return None
    if snapshot_ref is None:
        path = repo_root / rel
        try:
            if path.is_symlink() or not path.is_file():
                return None
            return path.read_bytes()
        except OSError:
            return None
    proc = subprocess.run(
        ["git", "show", f"{snapshot_ref}:{rel}"],
        cwd=repo_root,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        return None
    return proc.stdout


def _parse_git_name_status(stdout: str) -> list[str]:
    paths: set[str] = set()
    for raw_line in stdout.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) == 1:
            normalized = _normalize_repo_relpath(parts[0])
            if normalized:
                paths.add(normalized)
            continue
        for part in parts[1:]:
            normalized = _normalize_repo_relpath(part)
            if normalized:
                paths.add(normalized)
    return sorted(paths)


def _git_diff_name_status_cmd(base_ref: str, head_ref: str, range_syntax: bool) -> list[str]:
    cmd = ["git", "diff", "--name-status", "--diff-filter=ACDMRT"]
    if range_syntax:
        cmd.append(f"{base_ref}...{head_ref}")
    else:
        cmd.extend([base_ref, head_ref])
    return cmd


def _as_object_map(value: object) -> dict[str, object] | None:
    if not isinstance(value, dict):
        return None
    mapped: dict[str, object] = {}
    for key, item in cast(dict[object, object], value).items():
        if not isinstance(key, str):
            return None
        mapped[key] = item
    return mapped


def _as_object_list(value: object) -> list[object] | None:
    if not isinstance(value, list):
        return None
    return list(cast(list[object], value))


def _authority_error_hit(status: str, detail: str) -> PinnedSourceConsumer:
    return PinnedSourceConsumer(
        source_path="",
        consumer_path=CANONICAL_CURRENT_AUTHORITY_PATH,
        consumer_id="",
        pin_kind="",
        status=status,
        pinned_sha256=None,
        snapshot_sha256=None,
        detail=detail,
    )


def _load_current_authority_methods(
    repo_root: Path,
    snapshot_ref: str | None,
) -> tuple[list[object] | None, PinnedSourceConsumer | None]:
    raw = _read_snapshot_bytes(repo_root, CANONICAL_CURRENT_AUTHORITY_PATH, snapshot_ref)
    if raw is None:
        return None, None
    loaded: object
    try:
        loaded = json.loads(raw)
    except (TypeError, ValueError, UnicodeDecodeError):
        return None, _authority_error_hit(
            "unreadable",
            "current-authority JSON is unreadable",
        )
    payload = _as_object_map(loaded)
    if payload is None:
        return None, _authority_error_hit(
            "unsupported",
            "current-authority JSON is not an object",
        )
    matrix = _as_object_map(payload.get("imported_optimizer_matrix"))
    if matrix is None:
        return None, _authority_error_hit(
            "unsupported",
            "imported_optimizer_matrix is missing or unsupported",
        )
    methods = _as_object_list(matrix.get("methods"))
    if methods is None:
        return None, _authority_error_hit(
            "unsupported",
            "imported_optimizer_matrix.methods is missing or unsupported",
        )
    return methods, None


def _collect_pinned_source_consumers(
    changed_paths: list[str],
    repo_root: Path,
    snapshot_ref: str | None,
) -> tuple[list[PinnedSourceConsumer], list[str]]:
    methods, load_error = _load_current_authority_methods(repo_root, snapshot_ref)
    if load_error is not None:
        return [load_error], [STRUCTURAL_VERIFICATION_COMMAND]
    if methods is None:
        return [], []

    changed_set = set(changed_paths)
    hits: list[PinnedSourceConsumer] = []
    evidence_by_consumer: dict[str, set[str]] = {}

    for index, method_raw in enumerate(methods):
        method = _as_object_map(method_raw)
        if method is None:
            if changed_paths:
                hits.append(
                    _authority_error_hit(
                        "unsupported",
                        f"imported_optimizer_matrix.methods[{index}] is not an object",
                    )
                )
            continue
        consumer_id_value = method.get("strategy_id")
        consumer_id = (
            consumer_id_value
            if isinstance(consumer_id_value, str) and consumer_id_value
            else f"method[{index}]"
        )
        evidence_paths = evidence_by_consumer.setdefault(consumer_id, set())
        for pin_kind in CURRENT_AUTHORITY_PIN_KINDS:
            entries_value = method.get(pin_kind)
            if entries_value is None:
                continue
            entries = _as_object_list(entries_value)
            if entries is None:
                if changed_paths:
                    hits.append(
                        PinnedSourceConsumer(
                            source_path="",
                            consumer_path=CANONICAL_CURRENT_AUTHORITY_PATH,
                            consumer_id=consumer_id,
                            pin_kind=pin_kind,
                            status="unsupported",
                            pinned_sha256=None,
                            snapshot_sha256=None,
                            detail=f"{pin_kind} is not a list",
                        )
                    )
                continue
            for entry_raw in entries:
                entry = _as_object_map(entry_raw)
                if entry is None:
                    if changed_paths:
                        hits.append(
                            PinnedSourceConsumer(
                                source_path="",
                                consumer_path=CANONICAL_CURRENT_AUTHORITY_PATH,
                                consumer_id=consumer_id,
                                pin_kind=pin_kind,
                                status="unsupported",
                                pinned_sha256=None,
                                snapshot_sha256=None,
                                detail=f"{pin_kind} entry is not an object",
                            )
                        )
                    continue
                raw_path = entry.get("path")
                if not isinstance(raw_path, str):
                    continue
                source_path = _normalize_repo_relpath(raw_path)
                if source_path is None:
                    if raw_path in changed_set or raw_path in changed_paths:
                        hits.append(
                            PinnedSourceConsumer(
                                source_path=raw_path,
                                consumer_path=CANONICAL_CURRENT_AUTHORITY_PATH,
                                consumer_id=consumer_id,
                                pin_kind=pin_kind,
                                status="unsupported",
                                pinned_sha256=None,
                                snapshot_sha256=None,
                                detail="pinned path is unsupported",
                            )
                        )
                    continue
                if pin_kind == "correctness_evidence":
                    evidence_paths.add(source_path)
                if source_path not in changed_set:
                    continue
                pinned_sha = entry.get("sha256")
                if not isinstance(pinned_sha, str) or not _is_sha256_hex(pinned_sha):
                    hits.append(
                        PinnedSourceConsumer(
                            source_path=source_path,
                            consumer_path=CANONICAL_CURRENT_AUTHORITY_PATH,
                            consumer_id=consumer_id,
                            pin_kind=pin_kind,
                            status="unsupported",
                            pinned_sha256=pinned_sha if isinstance(pinned_sha, str) else None,
                            snapshot_sha256=None,
                            detail="pinned sha256 is missing or unsupported",
                        )
                    )
                    continue
                snapshot_bytes = _read_snapshot_bytes(repo_root, source_path, snapshot_ref)
                snapshot_sha = None if snapshot_bytes is None else _sha256_hex(snapshot_bytes)
                pinned_sha_norm = pinned_sha.lower()
                if snapshot_sha is not None and snapshot_sha == pinned_sha_norm:
                    status = "affected"
                    detail = "current-authority consumer pins this changed path"
                else:
                    status = "confirmed_mismatch"
                    detail = (
                        "pinned sha256 does not match snapshot bytes"
                        if snapshot_sha is not None
                        else "pinned path has no snapshot bytes"
                    )
                hits.append(
                    PinnedSourceConsumer(
                        source_path=source_path,
                        consumer_path=CANONICAL_CURRENT_AUTHORITY_PATH,
                        consumer_id=consumer_id,
                        pin_kind=pin_kind,
                        status=status,
                        pinned_sha256=pinned_sha_norm,
                        snapshot_sha256=snapshot_sha,
                        detail=detail,
                    )
                )

    hits.sort(
        key=lambda hit: (
            hit.status,
            hit.source_path,
            hit.consumer_path,
            hit.consumer_id,
            hit.pin_kind,
            hit.detail,
        )
    )

    extra_commands: list[str] = []
    if hits:
        extra_commands.append(STRUCTURAL_VERIFICATION_COMMAND)
        evidence_targets: set[str] = set()
        for hit in hits:
            if hit.status in {"affected", "confirmed_mismatch"}:
                evidence_targets.update(evidence_by_consumer.get(hit.consumer_id, set()))
        if evidence_targets:
            extra_commands.append(f"uv run pytest -q {' '.join(sorted(evidence_targets))}")
    return hits, extra_commands


def generate_verification_plan(
    changed_paths: list[str],
    repo_root: Path | None = None,
    snapshot_ref: str | None = None,
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

    pinned_hits, pinned_commands = _collect_pinned_source_consumers(
        sorted_changed_paths,
        repo_root,
        snapshot_ref,
    )
    if any(hit.status == "confirmed_mismatch" for hit in pinned_hits):
        rules_triggered.add(PINNED_SOURCE_REFRESH_RULE)
    for command in pinned_commands:
        if command not in recommended_commands:
            recommended_commands.append(command)

    sorted_rules_triggered = sorted(rules_triggered)

    return VerificationPlan(
        changed_paths=sorted_changed_paths,
        recommended_commands=recommended_commands,
        hermeticity_findings=hermeticity_findings,
        rules_triggered=sorted_rules_triggered,
        pinned_source_consumers=pinned_hits,
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
    lines.append("")

    lines.append("PINNED_SOURCE_CONSUMERS")
    if plan.pinned_source_consumers:
        for hit in plan.pinned_source_consumers:
            source = hit.source_path or hit.consumer_path
            snapshot = hit.snapshot_sha256 or "missing"
            pinned = hit.pinned_sha256 or "missing"
            lines.append(
                f"  {source} -> {hit.consumer_path} [{hit.status}] "
                f"consumer_id={hit.consumer_id or '-'} pin_kind={hit.pin_kind or '-'} "
                f"pinned_sha256={pinned} snapshot_sha256={snapshot}"
            )
            if hit.detail:
                lines.append(f"    detail={hit.detail}")
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
    snapshot_ref: str | None = None

    if has_explicit:
        changed_paths = list(args.changed_paths)
    else:
        # Git range mode: include deletions and rename old paths; bind later
        # source/authority reads to the range head snapshot.
        cmd = _git_diff_name_status_cmd(args.base_ref, args.head_ref, range_syntax=True)
        proc = subprocess.run(
            cmd,
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            fallback_cmd = _git_diff_name_status_cmd(
                args.base_ref,
                args.head_ref,
                range_syntax=False,
            )
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

        changed_paths = _parse_git_name_status(proc.stdout)
        snapshot_ref = args.head_ref

    plan = generate_verification_plan(
        changed_paths,
        repo_root=repo_root,
        snapshot_ref=snapshot_ref,
    )

    if args.format == "json":
        print(json.dumps(plan.to_dict(), indent=2))
    else:
        print(format_text_output(plan))

    if plan.hermeticity_findings:
        return 2
    blocking_pin_statuses = {"confirmed_mismatch", "unreadable", "unsupported"}
    if any(hit.status in blocking_pin_statuses for hit in plan.pinned_source_consumers):
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
