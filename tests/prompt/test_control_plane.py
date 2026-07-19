from __future__ import annotations

import copy
import hashlib
import json
import re
import runpy
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import pytest

REPO = Path(__file__).resolve().parents[2]
CONTROL_PLANE = REPO / "prompt" / "control-plane-v1"
TOOL = CONTROL_PLANE / "prototype" / "promptctl.py"
COMPILED = CONTROL_PLANE / "compiled"
STATUS = "DRAFT_FOR_OWNER_REVIEW"
L23 = "L23_UNSAFE_OWNER_STATEMENT_REFERENCE"
L24 = "L24_WORKTREE_REQUIRED_FOR_REPOSITORY_WRITES"
L25 = "L25_AUTHORIZATION_REQUIRED_BEFORE_RENDER"
L25_FAILURE = (
    f"{L25}: required authorization must be PRESENT with a safe "
    "OWNER_MESSAGE_REF before rendering"
)
ROLE_FILES = (
    "HANDOFF_REPORTER.compiled.md",
    "CEO_DECISION_REVIEW.compiled.md",
    "CTO_TECHNICAL_REVIEW.compiled.md",
    "PLANNER_COMPILER.compiled.md",
)
LEGACY_BYTES = {
    "HANDOFF_REPORTER.compiled.md": 11_830,
    "CEO_DECISION_REVIEW.compiled.md": 16_679,
    "CTO_TECHNICAL_REVIEW.compiled.md": 14_041,
    "PLANNER_COMPILER.compiled.md": 29_226,
}


def run_tool(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(TOOL), *args],
        cwd=REPO,
        check=check,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def marked_block(text: str, label: str) -> str:
    start = f"<!-- {label}:START -->"
    end = f"<!-- {label}:END -->"
    return text[text.index(start) : text.index(end) + len(end)]


def load_example(filename: str) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        json.loads(
            (CONTROL_PLANE / "examples" / filename).read_text(encoding="utf-8")
        ),
    )


def write_manifest(path: Path, manifest: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def standalone_manifest() -> dict[str, Any]:
    manifest = load_example("medium-implementation.task.yaml")
    risk = cast(dict[str, Any], manifest["risk"])
    authorization = cast(dict[str, Any], manifest["authorization"])
    routing = cast(dict[str, Any], manifest["routing"])
    risk["level"] = "HIGH"
    authorization["class"] = "STANDALONE"
    routing["path"] = "STRATEGIC_HIGH"
    routing["stages"] = [
        "CTO",
        "CEO",
        "OWNER_DECISION",
        "PLANNER",
        "WORKER",
        "REVIEW",
    ]
    return manifest


def stable_diagnostic_codes(stderr: str) -> set[str]:
    return set(re.findall(r"\bL\d+_[A-Z0-9_]+\b", stderr))


def control_plane_snapshot() -> dict[str, bytes]:
    return {
        str(path.relative_to(CONTROL_PLANE)): path.read_bytes()
        for path in sorted(CONTROL_PLANE.rglob("*"))
        if path.is_file()
    }


def assert_manifest_rejected(
    manifest: dict[str, Any], tmp_path: Path, filename: str, lint_code: str
) -> None:
    manifest_path = tmp_path / filename
    output_path = tmp_path / f"{manifest_path.stem}.worker.md"
    write_manifest(manifest_path, manifest)
    before = control_plane_snapshot()

    lint = run_tool("lint", "--manifest", str(manifest_path), check=False)
    assert lint.returncode == 1
    assert lint_code in lint.stderr
    assert stable_diagnostic_codes(lint.stderr) == {lint_code}
    assert lint.stdout == ""

    render = run_tool(
        "render",
        "--manifest",
        str(manifest_path),
        "--output",
        str(output_path),
        check=False,
    )
    assert render.returncode == 1
    assert lint_code in render.stderr
    assert stable_diagnostic_codes(render.stderr) == {lint_code}
    assert render.stdout == ""
    assert not output_path.exists()
    assert control_plane_snapshot() == before


def assert_render_blocked(
    manifest_path: Path, tmp_path: Path, output_name: str = "blocked.worker.md"
) -> None:
    output_path = tmp_path / output_name
    before = control_plane_snapshot()

    lint = run_tool("lint", "--manifest", str(manifest_path), check=False)
    assert lint.returncode == 0
    assert lint.stderr == ""

    render_stdout = run_tool("render", "--manifest", str(manifest_path), check=False)
    render_file = run_tool(
        "render",
        "--manifest",
        str(manifest_path),
        "--output",
        str(output_path),
        check=False,
    )
    for result in (render_stdout, render_file):
        assert result.returncode == 1
        assert result.stderr == f"FAIL {L25_FAILURE}\n"
        assert stable_diagnostic_codes(result.stderr) == {L25}
        assert result.stdout == ""
        for partial in (
            "# Executable Worker Task",
            "## Goal",
            "## Allowed writes",
            "## Execution",
            "## Memory and lifecycle",
        ):
            assert partial not in result.stdout
    assert not output_path.exists()
    assert control_plane_snapshot() == before


def test_control_plane_check_passes() -> None:
    result = run_tool("check")
    assert "PASS control-plane check roles=4 deterministic_runs=2" in result.stdout


def test_generation_is_byte_identical_across_fresh_directories(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    run_tool("compile", "--output-dir", str(first))
    run_tool("compile", "--output-dir", str(second))
    assert {path.name: path.read_bytes() for path in first.iterdir()} == {
        path.name: path.read_bytes() for path in second.iterdir()
    }


def test_fresh_generation_equals_committed_outputs() -> None:
    result = run_tool("compile", "--check")
    assert "PASS compiled outputs are fresh count=4" in result.stdout


def test_only_planner_embeds_worker_prompt_generation() -> None:
    for filename in ROLE_FILES:
        text = (COMPILED / filename).read_text(encoding="utf-8")
        is_planner = filename == "PLANNER_COMPILER.compiled.md"
        assert ("## Embedded Worker Task Template" in text) is is_planner
        assert ("{{TASK_ID}}" in text) is is_planner
        assert ("RENDER_WORKER_PROMPT" in text) is is_planner


def test_shared_evidence_precedence_and_routes_are_byte_identical() -> None:
    texts = [(COMPILED / filename).read_text(encoding="utf-8") for filename in ROLE_FILES]
    core_blocks = {marked_block(text, "SHARED_CORE") for text in texts}
    route_tables = {marked_block(text, "ROUTE_TABLE") for text in texts}
    assert len(core_blocks) == 1
    assert len(route_tables) == 1
    core = next(iter(core_blocks))
    for state in ("PASS", "FAIL", "NOT_RUN", "UNKNOWN", "STALE", "OUTDATED"):
        assert f"`{state}`" in core
    assert "1. live observed state;" in core
    assert "2. current-head-bound evidence;" in core
    assert "3. current task handoff;" in core
    assert "4. historical memory." in core


def test_role_capability_boundaries_are_explicit() -> None:
    handoff = (COMPILED / ROLE_FILES[0]).read_text(encoding="utf-8")
    ceo = (COMPILED / ROLE_FILES[1]).read_text(encoding="utf-8")
    cto = (COMPILED / ROLE_FILES[2]).read_text(encoding="utf-8")
    planner = (COMPILED / ROLE_FILES[3]).read_text(encoding="utf-8")
    assert "REPORT_HANDOFF,PROPOSE_MEMORY_CANDIDATE" in handoff
    assert "REVIEW_VALUE,REVIEW_CTO,PRIORITIZE,ESCALATE_OWNER_DECISION" in ceo
    assert "REVIEW_ARCHITECTURE,REVIEW_CORRECTNESS,REVIEW_TESTABILITY" in cto
    assert "COMPILE_MANIFEST,LINT_MANIFEST,RENDER_WORKER_PROMPT" in planner
    assert "Do not create or authorize work, compile or validate a Task Manifest" in handoff
    assert "Do not implement, edit source, create a complete Worker Prompt" in ceo
    assert "Do not implement, produce a complete Worker Prompt, authorize" in cto


def test_examples_lint_and_invalid_authorization_is_rejected(tmp_path: Path) -> None:
    run_tool("lint")
    source = CONTROL_PLANE / "examples" / "medium-implementation.task.yaml"
    manifest = json.loads(source.read_text(encoding="utf-8"))
    manifest["authorization"] = {
        "class": "NONE",
        "state": "NOT_REQUIRED",
        "owner_statement_ref": "NOT_REQUIRED",
    }
    invalid = tmp_path / "invalid.task.yaml"
    invalid.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    result = run_tool("lint", "--manifest", str(invalid), check=False)
    assert result.returncode == 1
    assert "$.authorization.class: expected constant 'SINGLE_PROMPT'" in result.stderr


def test_l23_safe_reference_grammar_and_metadata_rendering(tmp_path: Path) -> None:
    low = CONTROL_PLANE / "examples" / "low-readonly.task.yaml"
    pending = CONTROL_PLANE / "examples" / "medium-implementation.task.yaml"
    run_tool("lint", "--manifest", str(low))
    run_tool("lint", "--manifest", str(pending))

    confirmed = load_example("medium-implementation.task.yaml")
    authorization = cast(dict[str, Any], confirmed["authorization"])
    authorization["state"] = "PRESENT"
    authorization["owner_statement_ref"] = "OWNER_MESSAGE_REF:msg-123_example"
    confirmed_path = tmp_path / "confirmed-external.task.yaml"
    output_path = tmp_path / "confirmed-external.worker.md"
    write_manifest(confirmed_path, confirmed)

    run_tool("lint", "--manifest", str(confirmed_path))
    run_tool(
        "render",
        "--manifest",
        str(confirmed_path),
        "--output",
        str(output_path),
    )
    rendered = output_path.read_text(encoding="utf-8")
    assert "Owner statement reference: `OWNER_MESSAGE_REF:msg-123_example`" in rendered
    assert "evidence metadata only" in rendered
    assert "does not independently authorize" in rendered
    assert "Exact task branch: `task/catalog-ordering`" in rendered


def test_l25_allows_none_with_the_valid_none_envelope(tmp_path: Path) -> None:
    manifest_path = CONTROL_PLANE / "examples" / "low-readonly.task.yaml"
    output_path = tmp_path / "low-readonly.worker.md"

    run_tool("lint", "--manifest", str(manifest_path))
    run_tool(
        "render",
        "--manifest",
        str(manifest_path),
        "--output",
        str(output_path),
    )

    rendered = output_path.read_text(encoding="utf-8")
    assert "Authorization class: `NONE`" in rendered
    assert "Authorization state: `NOT_REQUIRED`" in rendered
    assert "Owner statement reference: `NOT_REQUIRED`" in rendered


def test_l25_allows_standalone_present_with_safe_metadata(tmp_path: Path) -> None:
    manifest = standalone_manifest()
    authorization = cast(dict[str, Any], manifest["authorization"])
    authorization["state"] = "PRESENT"
    authorization["owner_statement_ref"] = "OWNER_MESSAGE_REF:decision-456"
    manifest_path = tmp_path / "standalone-present.task.yaml"
    output_path = tmp_path / "standalone-present.worker.md"
    write_manifest(manifest_path, manifest)

    run_tool("lint", "--manifest", str(manifest_path))
    run_tool(
        "render",
        "--manifest",
        str(manifest_path),
        "--output",
        str(output_path),
    )

    rendered = output_path.read_text(encoding="utf-8")
    assert "Authorization class: `STANDALONE`" in rendered
    assert "Authorization state: `PRESENT`" in rendered
    assert "OWNER_MESSAGE_REF:decision-456" in rendered
    assert "AUTHORIZE_" not in rendered


@pytest.mark.parametrize(
    "opaque_id",
    [pytest.param("a", id="length-1"), pytest.param("a" * 128, id="length-128")],
)
def test_l23_accepts_owner_message_reference_boundaries(tmp_path: Path, opaque_id: str) -> None:
    manifest = load_example("medium-implementation.task.yaml")
    authorization = cast(dict[str, Any], manifest["authorization"])
    authorization["state"] = "PRESENT"
    authorization["owner_statement_ref"] = f"OWNER_MESSAGE_REF:{opaque_id}"
    manifest_path = tmp_path / f"owner-ref-{len(opaque_id)}.task.yaml"
    output_path = tmp_path / f"owner-ref-{len(opaque_id)}.worker.md"
    write_manifest(manifest_path, manifest)

    run_tool("lint", "--manifest", str(manifest_path))
    run_tool(
        "render",
        "--manifest",
        str(manifest_path),
        "--output",
        str(output_path),
    )
    assert f"OWNER_MESSAGE_REF:{opaque_id}" in output_path.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("example", "auth_class", "state", "reference"),
    [
        (
            "medium-implementation.task.yaml",
            "SINGLE_PROMPT",
            "PRESENT",
            "AUTHORIZE_EXAMPLE_TOKEN_123",
        ),
        (
            "medium-implementation.task.yaml",
            "SINGLE_PROMPT",
            "PRESENT",
            "Owner approved this task",
        ),
        (
            "medium-implementation.task.yaml",
            "SINGLE_PROMPT",
            "PRESENT",
            "Owner approved\nthis task",
        ),
        (
            "medium-implementation.task.yaml",
            "SINGLE_PROMPT",
            "PRESENT",
            "Bearer abc123",
        ),
        (
            "medium-implementation.task.yaml",
            "SINGLE_PROMPT",
            "PRESENT",
            "token=abc123",
        ),
        (
            "medium-implementation.task.yaml",
            "SINGLE_PROMPT",
            "PRESENT",
            "secret:abc123",
        ),
        (
            "medium-implementation.task.yaml",
            "SINGLE_PROMPT",
            "PRESENT",
            "cookie=session123",
        ),
        (
            "medium-implementation.task.yaml",
            "SINGLE_PROMPT",
            "PRESENT",
            "password=hunter2",
        ),
        (
            "medium-implementation.task.yaml",
            "SINGLE_PROMPT",
            "PRESENT",
            "-----BEGIN PRIVATE KEY-----abc",
        ),
        (
            "medium-implementation.task.yaml",
            "SINGLE_PROMPT",
            "PRESENT",
            "OWNER_MESSAGE_REF:",
        ),
        (
            "medium-implementation.task.yaml",
            "SINGLE_PROMPT",
            "PRESENT",
            "OWNER_MESSAGE_REF:" + "a" * 129,
        ),
        (
            "medium-implementation.task.yaml",
            "SINGLE_PROMPT",
            "PRESENT",
            "",
        ),
        (
            "medium-implementation.task.yaml",
            "SINGLE_PROMPT",
            "PRESENT",
            "https://example.invalid/owner/123",
        ),
        (
            "low-readonly.task.yaml",
            "NONE",
            "NOT_REQUIRED",
            "PENDING_OWNER_REFERENCE",
        ),
        (
            "low-readonly.task.yaml",
            "NONE",
            "NOT_REQUIRED",
            "OWNER_MESSAGE_REF:msg-123",
        ),
        (
            "medium-implementation.task.yaml",
            "SINGLE_PROMPT",
            "NOT_REQUIRED",
            "NOT_REQUIRED",
        ),
    ],
)
def test_l23_rejects_unsafe_authorization_references_without_output(
    tmp_path: Path,
    example: str,
    auth_class: str,
    state: str,
    reference: str,
) -> None:
    manifest = load_example(example)
    authorization = cast(dict[str, Any], manifest["authorization"])
    authorization.update(
        {
            "class": auth_class,
            "state": state,
            "owner_statement_ref": reference,
        }
    )
    assert_manifest_rejected(
        manifest,
        tmp_path,
        "external-l23.task.yaml",
        "L23_UNSAFE_OWNER_STATEMENT_REFERENCE",
    )


def test_external_manifest_bytes_receive_l23_sensitive_text_scan(
    tmp_path: Path,
) -> None:
    manifest = load_example("medium-implementation.task.yaml")
    task = cast(dict[str, Any], manifest["task"])
    task["goal"] = f"{task['goal']} Bearer abc123"
    assert_manifest_rejected(
        manifest,
        tmp_path,
        "external-sensitive-bytes.task.yaml",
        "L23_UNSAFE_OWNER_STATEMENT_REFERENCE",
    )


def test_l23_rejects_present_authorization_without_owner_reference(
    tmp_path: Path,
) -> None:
    manifest = load_example("medium-implementation.task.yaml")
    authorization = cast(dict[str, Any], manifest["authorization"])
    authorization["state"] = "PRESENT"
    del authorization["owner_statement_ref"]

    assert_manifest_rejected(
        manifest,
        tmp_path,
        "external-missing-owner-ref.task.yaml",
        L23,
    )


@pytest.mark.parametrize(
    "auth_class",
    [
        pytest.param("SINGLE_PROMPT", id="single-prompt-missing-pending-reference"),
        pytest.param("STANDALONE", id="standalone-missing-pending-reference"),
    ],
)
def test_l25_blocks_lint_valid_unresolved_required_authorization(
    tmp_path: Path, auth_class: str
) -> None:
    manifest = (
        standalone_manifest()
        if auth_class == "STANDALONE"
        else load_example("medium-implementation.task.yaml")
    )
    manifest_path = tmp_path / f"{auth_class.lower()}-unresolved.task.yaml"
    write_manifest(manifest_path, manifest)

    assert_render_blocked(manifest_path, tmp_path)


def test_l25_pending_medium_example_cannot_emit_any_worker_prompt(
    tmp_path: Path,
) -> None:
    manifest_path = CONTROL_PLANE / "examples" / "medium-implementation.task.yaml"
    assert_render_blocked(manifest_path, tmp_path, "pending-example.worker.md")


def test_l25_direct_renderer_call_cannot_bypass_readiness_gate(
    capsys: pytest.CaptureFixture[str],
) -> None:
    namespace = runpy.run_path(str(TOOL), run_name="promptctl_test")
    renderer = cast(Callable[[dict[str, Any]], bytes], namespace["render_worker"])
    control_plane_error = namespace["ControlPlaneError"]
    before = control_plane_snapshot()

    with pytest.raises(control_plane_error) as exc_info:
        renderer(load_example("medium-implementation.task.yaml"))

    captured = capsys.readouterr()
    assert str(exc_info.value) == L25_FAILURE
    assert captured.out == ""
    assert captured.err == ""
    assert control_plane_snapshot() == before


def test_l24_accepts_read_only_and_write_capable_worktree_envelopes(
    tmp_path: Path,
) -> None:
    cases: list[tuple[str, dict[str, Any]]] = []
    cases.append(("low-readonly", load_example("low-readonly.task.yaml")))

    medium_readonly = load_example("medium-implementation.task.yaml")
    medium_readonly_scope = cast(dict[str, Any], medium_readonly["scope"])
    medium_readonly_context = cast(dict[str, Any], medium_readonly["context"])
    medium_readonly_scope["allowed_writes"] = []
    medium_readonly_context["worktree"] = {
        "mode": "NOT_APPLICABLE",
        "path": "NOT_APPLICABLE",
        "branch": "NOT_APPLICABLE",
    }
    cases.append(("medium-readonly", medium_readonly))

    reusable = load_example("medium-implementation.task.yaml")
    cases.append(("medium-reusable", reusable))

    isolated = copy.deepcopy(reusable)
    isolated_context = cast(dict[str, Any], isolated["context"])
    isolated_context["worktree"] = {
        "mode": "EPHEMERAL_TASK_WORKTREE",
        "path": "/workspace/neutral-catalog-isolated",
        "branch": "task/catalog-ordering-isolated",
    }
    cases.append(("medium-isolated", isolated))

    for name, manifest in cases:
        manifest_path = tmp_path / f"{name}.task.yaml"
        write_manifest(manifest_path, manifest)
        run_tool("lint", "--manifest", str(manifest_path))


@pytest.mark.parametrize(
    "case",
    [
        "medium-writes-not-applicable",
        "low-writes-not-applicable",
        "missing-path",
        "missing-branch",
        "empty-path",
        "placeholder-path",
        "empty-branch",
        "placeholder-branch",
    ],
)
def test_l24_rejects_repository_writes_without_exact_worktree_envelope(
    tmp_path: Path, case: str
) -> None:
    if case == "low-writes-not-applicable":
        manifest = load_example("low-readonly.task.yaml")
        scope = cast(dict[str, Any], manifest["scope"])
        scope["allowed_writes"] = ["src/catalog/order.py"]
    else:
        manifest = load_example("medium-implementation.task.yaml")

    context = cast(dict[str, Any], manifest["context"])
    worktree = cast(dict[str, Any], context["worktree"])
    if case == "medium-writes-not-applicable":
        context["worktree"] = {
            "mode": "NOT_APPLICABLE",
            "path": "NOT_APPLICABLE",
            "branch": "NOT_APPLICABLE",
        }
    elif case == "missing-path":
        del worktree["path"]
    elif case == "missing-branch":
        del worktree["branch"]
    elif case == "empty-path":
        worktree["path"] = ""
    elif case == "placeholder-path":
        worktree["path"] = "UNKNOWN"
    elif case == "empty-branch":
        worktree["branch"] = ""
    elif case == "placeholder-branch":
        worktree["branch"] = "PENDING"

    assert_manifest_rejected(
        manifest,
        tmp_path,
        f"external-{case}.task.yaml",
        "L24_WORKTREE_REQUIRED_FOR_REPOSITORY_WRITES",
    )


def test_renderer_is_deterministic_and_complete(tmp_path: Path) -> None:
    manifest = load_example("medium-implementation.task.yaml")
    authorization = cast(dict[str, Any], manifest["authorization"])
    authorization["state"] = "PRESENT"
    authorization["owner_statement_ref"] = "OWNER_MESSAGE_REF:msg-123_example"
    manifest_path = tmp_path / "authorized-external.task.yaml"
    first = tmp_path / "worker-1.md"
    second = tmp_path / "worker-2.md"
    write_manifest(manifest_path, manifest)

    run_tool("lint", "--manifest", str(manifest_path))
    run_tool("render", "--manifest", str(manifest_path), "--output", str(first))
    run_tool("render", "--manifest", str(manifest_path), "--output", str(second))

    namespace = runpy.run_path(str(TOOL), run_name="promptctl_test")
    direct_renderer = cast(Callable[[dict[str, Any]], bytes], namespace["render_worker"])
    assert first.read_bytes() == second.read_bytes()
    assert first.read_bytes() == direct_renderer(manifest)
    text = first.read_text(encoding="utf-8")
    assert "{{" not in text
    assert STATUS in text
    assert "SINGLE_PROMPT" in text
    assert "REUSABLE_AGENT_WORKTREE" in text
    assert "PRESENT" in text
    assert "OWNER_MESSAGE_REF:msg-123_example" in text
    assert "PENDING_OWNER_REFERENCE" not in text
    assert "AUTHORIZE_" not in text
    assert "task/catalog-ordering" in text


def test_public_safety_and_web_portability_scan() -> None:
    forbidden = (
        "Lottery" + "New",
        "number-pattern" + "-research",
        "lottery_" + "v2.db",
        "P" + "541",
        "/Users/" + "kelvin/Kelvin-WorkSpace/" + "Lottery" + "New",
    )
    operational = [
        CONTROL_PLANE / "AGENT_CORE.md",
        CONTROL_PLANE / "ROLE_PROFILES.md",
        CONTROL_PLANE / "ROUTING_AND_LIFECYCLE.md",
        CONTROL_PLANE / "TASK_MANIFEST.schema.yaml",
        CONTROL_PLANE / "WORKER_TASK_TEMPLATE.md",
        *(COMPILED / filename for filename in ROLE_FILES),
    ]
    for path in operational:
        text = path.read_text(encoding="utf-8")
        assert all(term not in text for term in forbidden)
        assert "AUTHORIZE_" not in text
        assert "/Users/" not in text
        assert "../" not in text


@pytest.mark.parametrize(
    "unsafe_text, expected_kind",
    (
        ("AUTHORIZE_" + "OWNER_REVIEW_123", "authorization token"),
        ("token=" + "examplecredential123", "credential assignment"),
        ("-----BEGIN " + "PRIVATE KEY-----", "private key"),
        ("/Users/" + "example/consumer/repository", "user-specific absolute path"),
        ("./consumer/memory/session.json", "consumer memory path"),
        ("./consumer/data.sqlite", "database path"),
    ),
)
def test_public_safety_scanner_rejects_required_categories(
    unsafe_text: str, expected_kind: str
) -> None:
    namespace = runpy.run_path(str(TOOL), run_name="promptctl_test")
    scanner = cast(
        Callable[[str, str], list[str]], namespace["_public_safety_text_errors"]
    )
    errors = scanner("synthetic fixture", unsafe_text)
    assert any(expected_kind in error for error in errors)


def test_compiled_prompts_are_materially_shorter_than_legacy_sources() -> None:
    for filename, legacy_size in LEGACY_BYTES.items():
        compiled_size = (COMPILED / filename).stat().st_size
        assert compiled_size <= int(legacy_size * 0.85), (filename, compiled_size, legacy_size)


def test_all_artifacts_are_strict_utf8_markdown_or_json_compatible_yaml() -> None:
    artifact_paths = [
        *CONTROL_PLANE.glob("*.md"),
        *CONTROL_PLANE.glob("*.yaml"),
        *(CONTROL_PLANE / "compiled").glob("*.md"),
        *(CONTROL_PLANE / "examples").glob("*.md"),
        *(CONTROL_PLANE / "examples").glob("*.yaml"),
    ]
    for path in artifact_paths:
        raw = path.read_bytes()
        text = raw.decode("utf-8", errors="strict")
        assert not text.startswith("\ufeff")
        assert "\r" not in text
        assert STATUS in text
        if path.suffix == ".yaml":
            assert isinstance(json.loads(text), dict)
        else:
            assert text.count("```") % 2 == 0


def test_durable_source_fingerprint_is_embedded_and_reproducible() -> None:
    source_names = (
        "AGENT_CORE.md",
        "ROLE_PROFILES.md",
        "ROUTING_AND_LIFECYCLE.md",
        "TASK_MANIFEST.schema.yaml",
        "WORKER_TASK_TEMPLATE.md",
    )
    digest = hashlib.sha256()
    for name in source_names:
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        digest.update((CONTROL_PLANE / name).read_bytes())
        digest.update(b"\0")
    fingerprint = digest.hexdigest()
    result = run_tool("fingerprint")
    assert result.stdout.strip() == fingerprint
    for filename in ROLE_FILES:
        assert f"sha256:{fingerprint}" in (COMPILED / filename).read_text(encoding="utf-8")
