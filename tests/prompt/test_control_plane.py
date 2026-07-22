from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CONTROL_PLANE = REPO / "prompt" / "control-plane-v1"
TOOL = CONTROL_PLANE / "prototype" / "promptctl.py"
COMPILED = CONTROL_PLANE / "compiled"
STATUS = "DRAFT_FOR_OWNER_REVIEW"
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
        "owner_statement_ref": "NOT_APPLICABLE",
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
    assert "$.authorization.state: expected constant 'PRESENT'" in result.stderr


def test_renderer_is_deterministic_and_complete(tmp_path: Path) -> None:
    manifest = CONTROL_PLANE / "examples" / "medium-implementation.task.yaml"
    first = tmp_path / "worker-1.md"
    second = tmp_path / "worker-2.md"
    run_tool("render", "--manifest", str(manifest), "--output", str(first))
    run_tool("render", "--manifest", str(manifest), "--output", str(second))
    assert first.read_bytes() == second.read_bytes()
    text = first.read_text(encoding="utf-8")
    assert "{{" not in text
    assert STATUS in text
    assert "SINGLE_PROMPT" in text
    assert "REUSABLE_AGENT_WORKTREE" in text


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
