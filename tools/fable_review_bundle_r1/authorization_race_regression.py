"""Synthetic regression for close-time Fable authorization changes.

This reproduces the focused case already run during FABLE_EVIDENCE_FEEDBACK_AND_STORAGE_OPTIMIZATION_R1.
It is preserved for independent review; it was not rerun while sealing this bundle.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path


HELPER_PATH = Path(__file__).parent / "fable-method" / "scripts" / "fable_artifact_controls.py"
SPEC = importlib.util.spec_from_file_location("fable_artifact_controls_race_test", HELPER_PATH)
if SPEC is None or SPEC.loader is None:
    raise SystemExit("unable to load the bundled Fable helper")
HELPER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = HELPER
SPEC.loader.exec_module(HELPER)


def main() -> int:
    canonical_tmp = str(Path(tempfile.gettempdir()).resolve(strict=True))
    with tempfile.TemporaryDirectory(prefix="fable-close-auth-race-", dir=canonical_tmp) as temporary:
        root = Path(temporary)
        repo = root / "repo"
        repo.mkdir()
        HELPER._run_git_for_test(repo, "init", "--initial-branch=main")
        HELPER._run_git_for_test(repo, "config", "user.name", "Fable Race Test")
        HELPER._run_git_for_test(repo, "config", "user.email", "fable-race-test@example.invalid")
        source = repo / "base.txt"
        source.write_text("base\n", encoding="utf-8")
        HELPER._run_git_for_test(repo, "add", "base.txt")
        HELPER._run_git_for_test(repo, "commit", "-m", "base")

        worktree = root / "temporary-worktree"
        task_id = "SYNTHETIC_AUTHORIZATION_RACE_R1"
        branch = "codex/synthetic-auth-race"
        HELPER.prepare_temporary_worktree(
            str(repo), str(worktree), "main", branch, task_id,
            auto_close_authorized=True,
        )
        HELPER._run_git_for_test(repo, "worktree", "add", "-b", branch, str(worktree), "main")
        HELPER.bind_temporary_worktree(str(repo), str(worktree), "main", branch, task_id)

        evidence = root / "formal-result.json"
        evidence.write_text('{"proof":"fixture"}\n', encoding="utf-8")
        manifest = root / "manifest.json"
        manifest.write_text(json.dumps({
            "files": [{"path": str(evidence), "sha256": hashlib.sha256(evidence.read_bytes()).hexdigest()}]
        }), encoding="utf-8")

        marker = HELPER._lifecycle_marker_path(repo, worktree, create=False)
        original_sleep = HELPER.time.sleep

        def replace_authorization(_seconds: float) -> None:
            changed = json.loads(marker.read_text(encoding="utf-8"))
            changed["state"] = "REVOKED_DURING_CLOSE"
            replacement = marker.with_suffix(".replacement")
            replacement.write_text(
                json.dumps(changed, sort_keys=True, separators=(",", ":")) + "\n",
                encoding="utf-8",
            )
            os.replace(replacement, marker)

        HELPER.time.sleep = replace_authorization
        blocked = False
        try:
            HELPER.close_temporary_worktree(
                str(repo), str(worktree), "main", str(manifest), task_id,
                auto_close_authorized=True, task_complete=True,
                agents_quiescent=True, runtime_quiescent=True, scheduler_quiescent=True,
            )
        except HELPER.ControlError as exc:
            blocked = "changed before the removal claim" in str(exc)
        finally:
            HELPER.time.sleep = original_sleep

        current = json.loads(marker.read_text(encoding="utf-8"))
        registered = worktree.resolve() in HELPER._parse_worktree_list(repo)
        claim_dirs = list(marker.parent.glob(f".{marker.name}.closing.*"))
        preserved = (
            blocked
            and worktree.is_dir()
            and registered
            and current["state"] == "REVOKED_DURING_CLOSE"
            and not claim_dirs
        )
        if not preserved:
            print(json.dumps({
                "status": "FAIL",
                "blocked": blocked,
                "worktree_exists": worktree.is_dir(),
                "worktree_registered": registered,
                "marker_state": current.get("state"),
                "claim_dirs": [str(path) for path in claim_dirs],
            }, indent=2))
            return 1

        print(json.dumps({
            "status": "PASS",
            "authorization_change_between_validation_and_remove": "BLOCKED",
            "worktree_preserved": True,
            "changed_marker_preserved": True,
            "claim_artifacts_cleaned_or_restored": True,
            "temporary_fixture_cleanup": "TemporaryDirectory",
        }, indent=2))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
