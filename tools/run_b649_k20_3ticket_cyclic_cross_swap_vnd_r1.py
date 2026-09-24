"""Run the bounded K20 3-ticket cyclic cross-swap VND."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from lottolab.research.b649_k20_3ticket_cyclic_cross_swap_vnd_r1 import (
    BASE_COMMIT,
    BASE_TREE,
    R4_RUN2_PATH,
    RUN_ID,
    TASK_ID,
    run_task,
)

FABLE_CHECKPOINT_CLI = Path(
    "/Users/kelvin/VibeCoding-WorkSpace/skill/fable-method/scripts/task_checkpoint.rb"
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run-data-dir",
        type=Path,
        default=Path(".task-data") / TASK_ID / RUN_ID,
    )
    parser.add_argument(
        "--canonical-result-path",
        type=Path,
        default=Path("docs/research/b649-k20-3ticket-cyclic-cross-swap-vnd-r1-result.json"),
    )
    parser.add_argument("--resume", action="store_true")
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    repository = Path(__file__).resolve().parents[1]
    run_data_dir = args.run_data_dir
    canonical_result_path = args.canonical_result_path
    if not run_data_dir.is_absolute():
        run_data_dir = repository / run_data_dir
    if not canonical_result_path.is_absolute():
        canonical_result_path = repository / canonical_result_path

    record_root = repository / ".task-data" / TASK_ID
    inner_argv = ["uv", "run", "--with", "numpy", "python", *sys.argv]
    launcher_argv = [
        "ruby",
        str(FABLE_CHECKPOINT_CLI),
        "--run",
        "--repo",
        str(record_root),
        "--worktree",
        str(repository),
        "--task-id",
        TASK_ID,
        "--execution-id",
        RUN_ID,
        "--",
        *inner_argv,
    ]
    result = run_task(
        repository,
        run_data_dir=run_data_dir,
        canonical_result_path=canonical_result_path,
        resume=args.resume,
        command_argv=launcher_argv,
    )
    result["BASE_HEAD"] = BASE_COMMIT
    result["BASE_TREE"] = BASE_TREE
    result["TERMINAL_EVIDENCE_LOCATOR"] = str(R4_RUN2_PATH)
    print(json.dumps(result, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
