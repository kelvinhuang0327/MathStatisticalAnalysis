"""Parser-only coverage for the opt-in lineage successor commands."""

from __future__ import annotations

import pytest
from b649_lineage_path_guard import install_path_guard
from tools import b649_protected_cutover as protected


@pytest.fixture(autouse=True)
def isolate_lineage_successor_cli_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    install_path_guard(monkeypatch)


def _plan_args(action: str) -> list[str]:
    return [
        action,
        "--for",
        "apply",
        "--source-worktree",
        "/isolated/source",
        "--expected-head",
        "1" * 40,
        "--expected-tree",
        "2" * 40,
        "--legacy-head",
        "3" * 40,
        "--legacy-tree",
        "4" * 40,
        "--plan-file",
        "/isolated/plan.json",
        "--lineage-successor-request",
        "/isolated/request.json",
    ]


def _lookup_args(action: str) -> list[str]:
    return [
        action,
        "--for",
        "apply",
        "--source-worktree",
        "/isolated/source",
        "--expected-head",
        "1" * 40,
        "--expected-tree",
        "2" * 40,
    ]


def test_lineage_draft_and_prepare_require_explicit_plan_binding() -> None:
    for action in ("lineage-successor-draft", "lineage-successor-prepare"):
        args = protected.parser().parse_args(_plan_args(action))
        assert args.action == action
        assert args.target_action == "apply"
        assert args.plan_file == "/isolated/plan.json"
        assert args.lineage_successor_request == "/isolated/request.json"


def test_lineage_record_release_requires_explicit_evidence_path() -> None:
    args = protected.parser().parse_args(
        [
            *_lookup_args("lineage-successor-record-release"),
            "--lineage-successor-evidence",
            "/isolated/evidence.json",
        ]
    )
    assert args.action == "lineage-successor-record-release"
    assert args.lineage_successor_evidence == "/isolated/evidence.json"


def test_lineage_status_is_explicit_and_read_only_route() -> None:
    args = protected.parser().parse_args(
        [
            *_lookup_args("lineage-successor-status"),
            "--lineage-successor-evidence",
            "/isolated/evidence.json",
        ]
    )
    assert args.action == "lineage-successor-status"
    assert args.lineage_successor_evidence == "/isolated/evidence.json"


def test_authorize_accepts_transition_evidence_binding() -> None:
    args = protected.parser().parse_args(
        [
            *_lookup_args("authorize"),
            "--reservation-id",
            "reservation",
            "--operation-id",
            "operation",
            "--control-head",
            "5" * 40,
            "--control-tree",
            "6" * 40,
            "--target-source-worktree",
            "/isolated/target",
            "--target-head",
            "7" * 40,
            "--target-tree",
            "8" * 40,
            "--transition-evidence-sha256",
            "9" * 64,
            "--lineage-successor-evidence",
            "/isolated/evidence.json",
        ]
    )
    assert args.action == "authorize"
    assert args.transition_evidence_sha256 == "9" * 64
    assert args.lineage_successor_evidence == "/isolated/evidence.json"


def test_existing_apply_cli_keeps_opt_in_evidence_optional() -> None:
    args = protected.parser().parse_args(
        [
            "apply",
            "--source-worktree",
            "/isolated/source",
            "--expected-head",
            "1" * 40,
            "--expected-tree",
            "2" * 40,
            "--legacy-worktree",
            "/isolated/legacy",
            "--legacy-head",
            "3" * 40,
            "--legacy-tree",
            "4" * 40,
            "--plan-file",
            "/isolated/plan.json",
        ]
    )
    assert args.action == "apply"
    assert args.lineage_successor_evidence is None
