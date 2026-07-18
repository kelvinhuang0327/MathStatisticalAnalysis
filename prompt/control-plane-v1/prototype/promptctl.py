#!/usr/bin/env python3
"""Deterministic compiler, linter, and Worker Prompt renderer for control-plane v1."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, cast

STATUS = "DRAFT_FOR_OWNER_REVIEW"
ROOT = Path(__file__).resolve().parents[1]
COMPILED_DIR = ROOT / "compiled"

DURABLE_SOURCES = (
    "AGENT_CORE.md",
    "ROLE_PROFILES.md",
    "ROUTING_AND_LIFECYCLE.md",
    "TASK_MANIFEST.schema.yaml",
    "WORKER_TASK_TEMPLATE.md",
)

ROLE_SPECS = {
    "HANDOFF_REPORTER": (
        "Handoff Reporter",
        "HANDOFF_REPORTER.compiled.md",
    ),
    "CEO_DECISION_REVIEW": (
        "CEO Decision Reviewer",
        "CEO_DECISION_REVIEW.compiled.md",
    ),
    "CTO_TECHNICAL_REVIEW": (
        "CTO Technical Reviewer",
        "CTO_TECHNICAL_REVIEW.compiled.md",
    ),
    "PLANNER_COMPILER": (
        "Planner / Task Compiler",
        "PLANNER_COMPILER.compiled.md",
    ),
}


class ControlPlaneError(RuntimeError):
    """Raised when a deterministic control-plane gate fails."""


def _read_text(path: Path) -> str:
    try:
        raw = path.read_bytes()
        text = raw.decode("utf-8", errors="strict")
    except (OSError, UnicodeDecodeError) as exc:
        raise ControlPlaneError(f"cannot read strict UTF-8 {path}: {exc}") from exc
    if text.startswith("\ufeff"):
        raise ControlPlaneError(f"UTF-8 BOM is not allowed: {path}")
    if "\r" in text:
        raise ControlPlaneError(f"non-LF line ending found: {path}")
    return text


def _marked_block(text: str, label: str) -> str:
    start_marker = f"<!-- {label}:START -->"
    end_marker = f"<!-- {label}:END -->"
    start = text.find(start_marker)
    end = text.find(end_marker)
    if start < 0 or end < 0 or end <= start:
        raise ControlPlaneError(f"missing or invalid marker pair: {label}")
    end += len(end_marker)
    return text[start:end].strip() + "\n"


def _durable_texts() -> dict[str, str]:
    return {name: _read_text(ROOT / name) for name in DURABLE_SOURCES}


def durable_source_fingerprint(texts: dict[str, str] | None = None) -> str:
    source_texts = texts or _durable_texts()
    digest = hashlib.sha256()
    for name in DURABLE_SOURCES:
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(source_texts[name].encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


def _route_table(texts: dict[str, str] | None = None) -> dict[str, dict[str, Any]]:
    source_texts = texts or _durable_texts()
    block = _marked_block(source_texts["ROUTING_AND_LIFECYCLE.md"], "ROUTE_TABLE")
    match = re.search(r"```json\n(?P<payload>.*?)\n```", block, flags=re.DOTALL)
    if match is None:
        raise ControlPlaneError("ROUTE_TABLE must contain one fenced JSON object")
    payload: Any = json.loads(match.group("payload"))
    if not isinstance(payload, dict):
        raise ControlPlaneError("ROUTE_TABLE must be an object")
    return cast(dict[str, dict[str, Any]], payload)


def compile_role(role: str, texts: dict[str, str] | None = None) -> bytes:
    if role not in ROLE_SPECS:
        raise ControlPlaneError(f"unknown role: {role}")
    source_texts = texts or _durable_texts()
    title, _ = ROLE_SPECS[role]
    core = _marked_block(source_texts["AGENT_CORE.md"], "SHARED_CORE")
    role_block = _marked_block(source_texts["ROLE_PROFILES.md"], f"ROLE:{role}")
    shared_routing = _marked_block(
        source_texts["ROUTING_AND_LIFECYCLE.md"], "SHARED_ROUTING"
    )
    fingerprint = durable_source_fingerprint(source_texts)
    parts = [
        f"# {title} — Compiled Control Plane v1\n",
        f"Document status: `{STATUS}`\n",
        "Generated artifact: do not edit manually.\n",
        f"Durable-source fingerprint: `sha256:{fingerprint}`\n",
        "This prompt is standalone; embedded rules require no source-file access.\n",
        core,
        role_block,
        shared_routing,
    ]
    if role == "PLANNER_COMPILER":
        planner_routing = _marked_block(
            source_texts["ROUTING_AND_LIFECYCLE.md"], "PLANNER_ROUTING"
        )
        parts.extend(
            [
                planner_routing,
                "## Embedded Task Manifest Schema\n\n"
                "The following JSON-compatible YAML schema is normative for compilation.\n\n"
                "```yaml\n"
                f"{source_texts['TASK_MANIFEST.schema.yaml'].rstrip()}\n"
                "```\n",
                "## Embedded Worker Task Template\n\n"
                f"{source_texts['WORKER_TASK_TEMPLATE.md'].rstrip()}\n",
            ]
        )
    result = "\n".join(part.rstrip() for part in parts) + "\n"
    return result.encode("utf-8")


def generated_outputs(texts: dict[str, str] | None = None) -> dict[str, bytes]:
    source_texts = texts or _durable_texts()
    return {
        filename: compile_role(role, source_texts)
        for role, (_, filename) in ROLE_SPECS.items()
    }


def _json_yaml(path: Path) -> Any:
    text = _read_text(path)
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ControlPlaneError(
            f"{path} must use deterministic JSON-compatible YAML: {exc}"
        ) from exc


def _matches_type(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "null":
        return value is None
    return False


def _schema_errors(value: Any, schema: dict[str, Any], path: str = "$") -> list[str]:
    errors: list[str] = []
    if "const" in schema and value != schema["const"]:
        errors.append(f"{path}: expected constant {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: expected one of {schema['enum']!r}")

    expected_type = schema.get("type")
    if isinstance(expected_type, str) and not _matches_type(value, expected_type):
        return [f"{path}: expected {expected_type}, got {type(value).__name__}"]

    if isinstance(value, dict):
        object_value = cast(dict[str, Any], value)
        required = cast(list[str], schema.get("required", []))
        for key in required:
            if key not in object_value:
                errors.append(f"{path}: missing required property {key!r}")
        properties_value = schema.get("properties", {})
        if isinstance(properties_value, dict):
            properties = cast(dict[str, Any], properties_value)
            for key, child_schema in properties.items():
                if key in object_value and isinstance(child_schema, dict):
                    typed_child = cast(dict[str, Any], child_schema)
                    errors.extend(
                        _schema_errors(object_value[key], typed_child, f"{path}.{key}")
                    )
            if schema.get("additionalProperties") is False:
                extras = sorted(set(object_value) - set(properties))
                for key in extras:
                    errors.append(f"{path}: unexpected property {key!r}")

    if isinstance(value, list):
        list_value = cast(list[Any], value)
        minimum = schema.get("minItems")
        maximum = schema.get("maxItems")
        if isinstance(minimum, int) and len(list_value) < minimum:
            errors.append(f"{path}: requires at least {minimum} items")
        if isinstance(maximum, int) and len(list_value) > maximum:
            errors.append(f"{path}: allows at most {maximum} items")
        if schema.get("uniqueItems") is True:
            canonical = [
                json.dumps(item, sort_keys=True, ensure_ascii=False) for item in list_value
            ]
            if len(canonical) != len(set(canonical)):
                errors.append(f"{path}: items must be unique")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            typed_item_schema = cast(dict[str, Any], item_schema)
            for index, item in enumerate(list_value):
                errors.extend(_schema_errors(item, typed_item_schema, f"{path}[{index}]"))

    if isinstance(value, str):
        minimum_length = schema.get("minLength")
        if isinstance(minimum_length, int) and len(value) < minimum_length:
            errors.append(f"{path}: requires at least {minimum_length} characters")
        pattern = schema.get("pattern")
        if isinstance(pattern, str) and re.search(pattern, value) is None:
            errors.append(f"{path}: does not match {pattern!r}")

    all_of = cast(list[Any], schema.get("allOf", []))
    for child in all_of:
        if isinstance(child, dict):
            errors.extend(_schema_errors(value, cast(dict[str, Any], child), path))
    condition = schema.get("if")
    consequence = schema.get("then")
    if (
        isinstance(condition, dict)
        and isinstance(consequence, dict)
        and not _schema_errors(value, cast(dict[str, Any], condition), path)
    ):
        errors.extend(_schema_errors(value, cast(dict[str, Any], consequence), path))
    return errors


def validate_manifest(manifest: Any, schema: dict[str, Any], routes: dict[str, Any]) -> list[str]:
    errors = _schema_errors(manifest, schema)
    if errors or not isinstance(manifest, dict):
        return errors

    manifest_object = cast(dict[str, Any], manifest)
    routing = cast(dict[str, Any], manifest_object["routing"])
    route_name = routing["path"]
    route = cast(dict[str, Any] | None, routes.get(cast(str, route_name)))
    if route is None:
        return [f"$.routing.path: route {route_name!r} is absent from the route table"]
    risk = cast(dict[str, Any], manifest_object["risk"])
    authorization = cast(dict[str, Any], manifest_object["authorization"])
    if risk["level"] != route.get("risk"):
        errors.append("$.risk.level: does not match the selected route")
    if authorization["class"] != route.get("authorization"):
        errors.append("$.authorization.class: does not match the selected route")
    if routing["stages"] != route.get("stages"):
        errors.append("$.routing.stages: must exactly match the selected route")

    if authorization["class"] == "NONE":
        if authorization["state"] != "NOT_REQUIRED":
            errors.append("$.authorization.state: NONE requires NOT_REQUIRED")
        if authorization["owner_statement_ref"] != "NOT_APPLICABLE":
            errors.append("$.authorization.owner_statement_ref: NONE requires NOT_APPLICABLE")
    elif authorization["state"] != "PRESENT":
        errors.append("$.authorization.state: required authorization must be PRESENT")

    context = cast(dict[str, Any], manifest_object["context"])
    worktree = cast(dict[str, Any], context["worktree"])
    if worktree["mode"] == "NOT_APPLICABLE" and worktree["path"] != "NOT_APPLICABLE":
        errors.append("$.context.worktree.path: NOT_APPLICABLE mode requires NOT_APPLICABLE")
    if worktree["mode"] != "NOT_APPLICABLE" and worktree["path"] == "NOT_APPLICABLE":
        errors.append("$.context.worktree.path: selected mode requires an exact path")

    if risk["level"] == "LOW":
        scope = cast(dict[str, Any], manifest_object["scope"])
        if scope["allowed_writes"]:
            errors.append("$.scope.allowed_writes: LOW read-only route must have no writes")
        if worktree["mode"] != "NOT_APPLICABLE":
            errors.append("$.context.worktree.mode: LOW read-only route requires NOT_APPLICABLE")
    return errors


def _markdown_errors(path: Path, text: str) -> list[str]:
    errors: list[str] = []
    if STATUS not in text:
        errors.append(f"{path}: missing {STATUS}")
    if not re.search(r"^# ", text, flags=re.MULTILINE):
        errors.append(f"{path}: missing level-one Markdown heading")
    if text.count("```") % 2:
        errors.append(f"{path}: unbalanced fenced code block")
    return errors


def _forbidden_operational_terms() -> tuple[str, ...]:
    return (
        "Lottery" + "New",
        "number-pattern" + "-research",
        "lottery_" + "v2.db",
        "P" + "541",
        "/Users/" + "kelvin/Kelvin-WorkSpace/" + "Lottery" + "New",
    )


def _public_safety_text_errors(label: str, text: str) -> list[str]:
    errors: list[str] = []
    for term in _forbidden_operational_terms():
        if term in text:
            errors.append(f"{label}: forbidden consumer-specific term {term!r}")
    if re.search(r"\bAUTHORIZE_[A-Z0-9_]+\b", text):
        errors.append(f"{label}: real-looking authorization token is forbidden")
    if re.search(r"/Users/[A-Za-z0-9._-]+/", text):
        errors.append(f"{label}: user-specific absolute path is forbidden")
    credential_patterns = {
        "private key": r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
        "Git hosting token": r"\bgh[pousr]_[A-Za-z0-9]{20,}\b",
        "API secret": r"\bsk-[A-Za-z0-9]{20,}\b",
        "cloud access key": r"\bAKIA[0-9A-Z]{16}\b",
    }
    for kind, pattern in credential_patterns.items():
        if re.search(pattern, text):
            errors.append(f"{label}: real-looking {kind} is forbidden")
    return errors


def _public_safety_errors(paths: list[Path]) -> list[str]:
    errors: list[str] = []
    for path in paths:
        errors.extend(_public_safety_text_errors(str(path), _read_text(path)))
    return errors


def _role_boundary_errors(outputs: dict[str, bytes]) -> list[str]:
    errors: list[str] = []
    decoded = {name: payload.decode("utf-8") for name, payload in outputs.items()}
    planner_name = ROLE_SPECS["PLANNER_COMPILER"][1]
    for name, text in decoded.items():
        has_template = "## Embedded Worker Task Template" in text
        if has_template != (name == planner_name):
            errors.append(f"{name}: embedded Worker Prompt template boundary is invalid")

    required_capabilities = {
        "HANDOFF_REPORTER.compiled.md": ("REPORT_HANDOFF", "PROPOSE_MEMORY_CANDIDATE"),
        "CEO_DECISION_REVIEW.compiled.md": ("REVIEW_VALUE", "REVIEW_CTO", "PRIORITIZE"),
        "CTO_TECHNICAL_REVIEW.compiled.md": (
            "REVIEW_ARCHITECTURE",
            "REVIEW_CORRECTNESS",
            "REVIEW_TESTABILITY",
        ),
        "PLANNER_COMPILER.compiled.md": (
            "RESOLVE_ROUTING",
            "COMPILE_MANIFEST",
            "LINT_MANIFEST",
            "RENDER_WORKER_PROMPT",
        ),
    }
    for name, capabilities in required_capabilities.items():
        for capability in capabilities:
            if capability not in decoded[name]:
                errors.append(f"{name}: missing capability {capability}")
    for name in decoded:
        if name != planner_name and "RENDER_WORKER_PROMPT" in decoded[name]:
            errors.append(f"{name}: non-Planner role can render Worker Prompts")

    core_blocks = {
        _marked_block(text, "SHARED_CORE") for text in decoded.values()
    }
    if len(core_blocks) != 1:
        errors.append("compiled roles do not contain byte-identical Shared Core blocks")
    route_blocks = {
        _marked_block(text, "ROUTE_TABLE") for text in decoded.values()
    }
    if len(route_blocks) != 1:
        errors.append("compiled roles do not contain byte-identical route tables")
    return errors


def repository_lint(manifest_path: Path | None = None) -> list[str]:
    errors: list[str] = []
    texts = _durable_texts()
    schema = _json_yaml(ROOT / "TASK_MANIFEST.schema.yaml")
    if not isinstance(schema, dict):
        errors.append("TASK_MANIFEST.schema.yaml: root must be an object")
        return errors
    schema_object = cast(dict[str, Any], schema)
    if schema_object.get("x-document-status") != STATUS:
        errors.append("TASK_MANIFEST.schema.yaml: incorrect document status")

    routes = _route_table(texts)
    expected_routes = {
        "LOW_READ_ONLY",
        "MEDIUM_IMPLEMENTATION",
        "TECHNICAL",
        "STRATEGIC_HIGH",
    }
    if set(routes) != expected_routes:
        errors.append("ROUTE_TABLE: route inventory mismatch")

    markdown_paths = [ROOT / name for name in DURABLE_SOURCES if name.endswith(".md")]
    markdown_paths.extend(sorted((ROOT / "examples").rglob("*.md")))
    markdown_paths.append(ROOT / "README.md")
    for path in markdown_paths:
        text = _read_text(path)
        errors.extend(_markdown_errors(path, text))

    example_manifests = sorted((ROOT / "examples").glob("*.task.yaml"))
    for path in example_manifests:
        manifest = _json_yaml(path)
        errors.extend(
            f"{path}: {error}"
            for error in validate_manifest(manifest, schema_object, routes)
        )

    profile_path = ROOT / "examples" / "agent-profile.example.yaml"
    profile = _json_yaml(profile_path)
    if not isinstance(profile, dict):
        errors.append(f"{profile_path}: root must be an object")
    else:
        profile_object = cast(dict[str, Any], profile)
        for key in ("document_status", "profile_version", "project", "paths", "restrictions"):
            if key not in profile_object:
                errors.append(f"{profile_path}: missing {key!r}")
        if profile_object.get("document_status") != STATUS:
            errors.append(f"{profile_path}: incorrect document status")

    if manifest_path is not None:
        manifest = _json_yaml(manifest_path)
        errors.extend(
            f"{manifest_path}: {error}"
            for error in validate_manifest(manifest, schema_object, routes)
        )

    outputs = generated_outputs(texts)
    errors.extend(_role_boundary_errors(outputs))
    for filename, payload in outputs.items():
        text = payload.decode("utf-8", errors="strict")
        errors.extend(_markdown_errors(COMPILED_DIR / filename, text))
        errors.extend(_public_safety_text_errors(f"generated:{filename}", text))
    operational_paths = [ROOT / name for name in DURABLE_SOURCES]
    operational_paths.extend(markdown_paths)
    operational_paths.extend(example_manifests)
    operational_paths.append(profile_path)
    errors.extend(_public_safety_errors(sorted(set(operational_paths))))
    return errors


def _bullets(values: list[str]) -> str:
    if not values:
        return "- `NONE`"
    return "\n".join(f"- {value}" for value in values)


def _numbered(values: list[str]) -> str:
    return "\n".join(f"{index}. {value}" for index, value in enumerate(values, start=1))


def render_worker(manifest: dict[str, Any]) -> bytes:
    template = _read_text(ROOT / "WORKER_TASK_TEMPLATE.md")
    replacements = {
        "TASK_ID": manifest["task"]["id"],
        "TASK_TITLE": manifest["task"]["title"],
        "TASK_GOAL": manifest["task"]["goal"],
        "TASK_STEPS": _numbered(manifest["task"]["steps"]),
        "PROJECT_IDENTITY": manifest["project"]["identity"],
        "CANONICAL_REPO": manifest["project"]["canonical_repo"],
        "CANONICAL_BRANCH": manifest["project"]["canonical_branch"],
        "PROFILE_PATH": manifest["project"]["profile_path"],
        "BASE_SHA": manifest["context"]["base_sha"],
        "HEAD_SHA": manifest["context"]["head_sha"],
        "WORKTREE_MODE": manifest["context"]["worktree"]["mode"],
        "WORKTREE_PATH": manifest["context"]["worktree"]["path"],
        "ALLOWED_READS": _bullets(manifest["scope"]["allowed_reads"]),
        "ALLOWED_WRITES": _bullets(manifest["scope"]["allowed_writes"]),
        "PROTECTED_PATHS": _bullets(manifest["scope"]["protected_paths"]),
        "FORBIDDEN_ACTIONS": _bullets(manifest["scope"]["forbidden_actions"]),
        "RISK_LEVEL": manifest["risk"]["level"],
        "AUTHORIZATION_CLASS": manifest["authorization"]["class"],
        "AUTHORIZATION_STATE": manifest["authorization"]["state"],
        "OWNER_STATEMENT_REF": manifest["authorization"]["owner_statement_ref"],
        "ROUTING_PATH": manifest["routing"]["path"],
        "ROUTING_STAGES_INLINE": " -> ".join(manifest["routing"]["stages"]),
        "VERIFICATION_COMMANDS": _bullets(manifest["verification"]["commands"]),
        "EXPECTED_OBSERVATIONS": _bullets(
            manifest["verification"]["expected_observations"]
        ),
        "LIFECYCLE_INTEGRATION": manifest["lifecycle"]["integration"],
        "LIFECYCLE_CLEANUP": manifest["lifecycle"]["cleanup"],
        "MEMORY_READ": manifest["memory"]["read"],
        "MEMORY_WRITE": manifest["memory"]["write"],
        "HANDOFF_FIELDS": _bullets(manifest["handoff"]["required_fields"]),
    }
    for key, value in replacements.items():
        template = template.replace("{{" + key + "}}", str(value))
    unresolved = sorted(set(re.findall(r"{{[A-Z0-9_]+}}", template)))
    if unresolved:
        raise ControlPlaneError(f"unresolved template fields: {', '.join(unresolved)}")
    return (template.rstrip() + "\n").encode("utf-8")


def _write_outputs(outputs: dict[str, bytes], directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for filename, payload in outputs.items():
        (directory / filename).write_bytes(payload)


def _freshness_errors(outputs: dict[str, bytes], directory: Path = COMPILED_DIR) -> list[str]:
    errors: list[str] = []
    for filename, payload in outputs.items():
        path = directory / filename
        if not path.is_file():
            errors.append(f"missing compiled output: {path}")
        elif path.read_bytes() != payload:
            errors.append(f"stale compiled output: {path}")
    extras = sorted(
        path.name for path in directory.glob("*.compiled.md") if path.name not in outputs
    )
    for name in extras:
        errors.append(f"unexpected compiled output: {directory / name}")
    return errors


def _print_errors(errors: list[str]) -> int:
    for error in errors:
        print(f"FAIL {error}", file=sys.stderr)
    return 1 if errors else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    compile_parser = subparsers.add_parser("compile", help="generate the four role prompts")
    compile_parser.add_argument("--check", action="store_true", help="compare without writing")
    compile_parser.add_argument("--output-dir", type=Path, help="write to an alternate directory")

    lint_parser = subparsers.add_parser("lint", help="lint sources, examples, and role boundaries")
    lint_parser.add_argument("--manifest", type=Path, help="also validate one manifest")

    render_parser = subparsers.add_parser("render", help="render one Worker Prompt")
    render_parser.add_argument("--manifest", type=Path, required=True)
    render_parser.add_argument("--output", type=Path)

    subparsers.add_parser("check", help="run lint, determinism, and freshness gates")
    subparsers.add_parser("fingerprint", help="print the durable-source fingerprint")

    args = parser.parse_args(argv)
    try:
        if args.command == "compile":
            outputs = generated_outputs()
            if args.check:
                errors = _freshness_errors(outputs, args.output_dir or COMPILED_DIR)
                if errors:
                    return _print_errors(errors)
                print(f"PASS compiled outputs are fresh count={len(outputs)}")
                return 0
            output_dir = args.output_dir or COMPILED_DIR
            _write_outputs(outputs, output_dir)
            print(f"PASS compiled outputs written count={len(outputs)} directory={output_dir}")
            return 0

        if args.command == "lint":
            errors = repository_lint(args.manifest)
            if errors:
                return _print_errors(errors)
            print("PASS control-plane lint")
            return 0

        if args.command == "render":
            schema = _json_yaml(ROOT / "TASK_MANIFEST.schema.yaml")
            manifest = _json_yaml(args.manifest)
            errors = validate_manifest(manifest, schema, _route_table())
            if errors:
                return _print_errors([f"{args.manifest}: {error}" for error in errors])
            payload = render_worker(manifest)
            if args.output:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_bytes(payload)
                print(f"PASS Worker Prompt rendered output={args.output}")
            else:
                sys.stdout.buffer.write(payload)
            return 0

        if args.command == "check":
            errors = repository_lint()
            first = generated_outputs()
            second = generated_outputs()
            if first != second:
                errors.append("repeated generation is not byte-identical")
            errors.extend(_freshness_errors(first))
            if errors:
                return _print_errors(errors)
            fingerprint = durable_source_fingerprint()
            print(
                "PASS control-plane check "
                f"roles={len(first)} deterministic_runs=2 fingerprint={fingerprint}"
            )
            return 0

        if args.command == "fingerprint":
            print(durable_source_fingerprint())
            return 0
    except (ControlPlaneError, json.JSONDecodeError, KeyError, TypeError) as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        return 1
    raise AssertionError(f"unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
