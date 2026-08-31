"""Synthetic/adversarial acceptance for the frozen next-draw 54 replay R2 runner.

No test in this module executes a production adapter, opens the production
database, or starts a real replay campaign.
"""

from __future__ import annotations

import os
import random
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, cast

import pytest
from tools import next_draw_54_replay_r2 as coordinator
from tools import next_draw_54_replay_r2_lib as c
from tools import next_draw_54_replay_r2_runtime as runtime

REPO_ROOT = Path(__file__).resolve().parents[2]
CATALOG = REPO_ROOT / "src/lottolab/strategies/catalog.py"
ZERO_SHA = "0" * 64


@dataclass(frozen=True)
class SyntheticBundle:
    plan: dict[str, Any]
    contexts: list[dict[str, Any]]
    results: list[dict[str, Any]]
    results_b: list[dict[str, Any]]
    run_a: dict[str, Any]
    run_b: dict[str, Any]
    run_a_bytes: bytes
    run_b_bytes: bytes
    acceptance: dict[str, Any]


def _sha(label: str) -> str:
    return c.sha256(label.encode("utf-8"))


def _module_path(name: str) -> str:
    stem = "src/" + name.replace(".", "/")
    return stem + "/__init__.py" if name == "lottolab" else stem + ".py"


def _authority(strategies: dict[str, Any]) -> dict[str, Any]:
    modules = {
        "lottolab",
        "lottolab.application.use_cases.replay_historical_predictions",
        "lottolab.strategies.catalog",
        *(row["adapter_path"].split(":")[0] for row in strategies["records"]),
    }
    paths = {_module_path(name) for name in modules} | {"uv.lock"}
    inventory: list[dict[str, str]] = []
    for path in sorted(paths):
        sha = _sha(path)
        blob = _sha("blob:" + path)[:40]
        if path == "src/lottolab/strategies/catalog.py":
            sha, blob = c.CATALOG_SHA256, c.CATALOG_BLOB
        elif path == "uv.lock":
            sha = c.LOCK_SHA256
        inventory.append({"path": path, "sha256": sha, "git_blob": blob, "mode": "100644"})
    authority = {
        "repository_head": c.HEAD,
        "repository_tree": c.TREE,
        "catalog_git_blob": c.CATALOG_BLOB,
        "catalog_sha256": c.CATALOG_SHA256,
        "uv_lock_sha256": c.LOCK_SHA256,
        "load_bearing_blobs": inventory,
        "source_inventory_sha256": c.digest(inventory),
    }
    c.validate_authority(authority)
    return authority


def _runtime_fingerprint(authority: dict[str, Any]) -> dict[str, Any]:
    bundle = [{"path": "bin/python3.13", "sha256": _sha("python-bundle")}]
    native = [{"path": "_random", "sha256": _sha("native-random")}]
    runners = [
        {"path": path, "sha256": _sha(path)}
        for path in (
            "tools/next_draw_54_replay_r2.py",
            "tools/next_draw_54_replay_r2_lib.py",
            "tools/next_draw_54_replay_r2_runtime.py",
        )
    ]
    float_info = {
        name: "0"
        for name in [
            "max",
            "max_exp",
            "max_10_exp",
            "min",
            "min_exp",
            "min_10_exp",
            "dig",
            "mant_dig",
            "epsilon",
            "radix",
            "rounds",
        ]
    }
    hash_info = {
        name: "0"
        for name in [
            "width",
            "modulus",
            "inf",
            "nan",
            "imag",
            "algorithm",
            "hash_bits",
            "seed_bits",
            "cutoff",
        ]
    }
    result = {
        "schema_version": "NEXT_DRAW_54_REPLAY_RUNTIME_V2",
        "python": {
            "version": "3.13.0 synthetic",
            "version_info": [3, 13, 0, "final", 0],
            "hexversion": 1,
            "implementation": "cpython",
            "cache_tag": "cpython-313",
            "abiflags": "",
            "soabi": "cpython-313-synthetic",
            "build": ["synthetic", "synthetic"],
            "compiler": "synthetic",
            "executable_sha256": _sha("python-executable"),
            "runtime_bundle_sha256": c.digest(bundle),
            "runtime_bundle_files": bundle,
            "stdlib_random_sha256": _sha("stdlib-random"),
            "rng_state_version": 3,
        },
        "platform": {
            "system": "Synthetic",
            "release": "1",
            "version": "1",
            "machine": "synthetic64",
            "processor": "synthetic64",
            "cpu_model": "synthetic",
            "cpu_features": ["synthetic"],
            "byteorder": "little",
            "pointer_bits": 64,
            "libc": "",
            "macos_version": "synthetic",
        },
        "numeric": {
            "float_info": float_info,
            "hash_info": hash_info,
            "native_libraries": native,
            "blas": "NOT_LOADED_FOR_FROZEN_STDLIB_STRATEGIES",
        },
        "distributions": [],
        "installer": {
            "name": "uv",
            "version": "uv synthetic",
            "executable_sha256": _sha("uv"),
        },
        "environment": [
            {"name": key, "value": value} for key, value in sorted(c.ENVIRONMENT.items())
        ],
        "source_inventory_sha256": authority["source_inventory_sha256"],
        "runner_files": runners,
    }
    c.validate_runtime(result)
    return result


def _snapshot() -> dict[str, Any]:
    first = date(2020, 1, 1)
    rows = [
        {
            "source_row_id": index + 1,
            "draw_date": (first + timedelta(days=index)).isoformat(),
            "draw_number": f"{index + 1:09d}",
            "main_numbers": [1, 2, 3, 4, 5, 6],
            "special_number": 7,
        }
        for index in range(1_000)
    ]
    return {
        "snapshot_schema_version": "NEXT_DRAW_54_SOURCE_SNAPSHOT_V2",
        "kind": c.SYNTHETIC_DATA,
        "lottery_type": "BIG_LOTTO",
        "draws": rows,
    }


def _source_integrity(plan: dict[str, Any], identity: dict[str, Any]) -> dict[str, Any]:
    lookup = {row["path"]: row["sha256"] for row in plan["authority"]["load_bearing_blobs"]}
    names = sorted(
        {
            "lottolab",
            "lottolab.application.use_cases.replay_historical_predictions",
            "lottolab.strategies.catalog",
            identity["adapter_path"].split(":")[0],
        }
    )
    modules = [
        {"module": name, "path": _module_path(name), "sha256": lookup[_module_path(name)]}
        for name in names
    ]
    return {
        "repository_head": c.HEAD,
        "repository_tree": c.TREE,
        "source_inventory_sha256_before": plan["authority"]["source_inventory_sha256"],
        "source_inventory_sha256_after": plan["authority"]["source_inventory_sha256"],
        "source_draw_db_sha256_before": plan["dataset"]["source_db"]["sha256"],
        "source_draw_db_sha256_after": plan["dataset"]["source_db"]["sha256"],
        "import_anchor_verified": True,
        "imported_modules": modules,
    }


def _strategy_result(
    plan: dict[str, Any],
    contexts: list[dict[str, Any]],
    identity: dict[str, Any],
    *,
    first_ticket: list[int] | None = None,
) -> dict[str, Any]:
    seed = c.seed_record(plan["common_manifest_sha256"], identity)
    state = c.seeded_state_digest(seed)
    cells = [
        c.make_cell(
            plan,
            identity,
            context,
            first_ticket if index == 0 and first_ticket is not None else [1, 2, 3, 4, 5, 6],
            sorted(first_ticket) if index == 0 and first_ticket is not None else [1, 2, 3, 4, 5, 6],
            state,
            state,
        )
        for index, context in enumerate(contexts)
    ]
    return c.make_strategy_result(
        plan,
        identity,
        cells,
        _source_integrity(plan, identity),
        state,
        state,
    )


def _timestamp(value: datetime) -> str:
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")


def _operational(results: list[dict[str, Any]], label: str, day_offset: int) -> dict[str, Any]:
    base = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(days=day_offset)
    attempts = [
        {
            "attempt_id": f"{label}-{index + 1:02d}-01",
            "strategy_id": result["strategy_identity"]["strategy_id"],
            "ordinal": 1,
            "pid": 1000 + index,
            "started_at_utc": _timestamp(base + timedelta(seconds=index)),
            "ended_at_utc": _timestamp(base + timedelta(seconds=index)),
            "elapsed_ns": 1,
            "exit_status": 0,
            "status": "SUCCEEDED",
            "failure_kind": "",
            "previous_attempt_id": "",
            "result_sha256": result["strategy_output_sha256"],
            "partial_output_sha256": "",
            "bootstrap_before_sha256": ZERO_SHA,
            "bootstrap_after_sha256": ZERO_SHA,
        }
        for index, result in enumerate(results)
    ]
    return {
        "run_id": label,
        "output_root": f"/synthetic/{label}",
        "source_root": "/synthetic/source",
        "source_db_path": "/synthetic/source.sqlite3",
        "host_label": "synthetic-host",
        "started_at_utc": _timestamp(base),
        "ended_at_utc": _timestamp(base + timedelta(seconds=len(results) + 1)),
        "elapsed_ns": (len(results) + 1) * 1_000_000_000,
        "attempts": attempts,
    }


def _build_synthetic_bundle() -> SyntheticBundle:
    strategies = c.strategy_manifest(CATALOG.read_bytes())
    authority = _authority(strategies)
    snapshot = _snapshot()
    plan = c.make_plan(
        authority=authority,
        dataset=c.dataset_manifest(snapshot, _sha("synthetic-db"), 1),
        strategies=strategies,
        runtime=_runtime_fingerprint(authority),
    )
    contexts = c.target_contexts(plan)
    results = [
        _strategy_result(plan, contexts, identity) for identity in plan["strategies"]["records"]
    ]
    results_b = [
        _strategy_result(plan, contexts, identity) for identity in plan["strategies"]["records"]
    ]
    run_a = c.make_run(plan, results, _operational(results, "run-a", 0), "SYNTHETIC_A")
    run_b = c.make_run(plan, results_b, _operational(results_b, "run-b", 1), "SYNTHETIC_B")
    run_a_bytes, run_b_bytes = c.file_bytes(run_a), c.file_bytes(run_b)
    acceptance = c.make_acceptance(plan, run_a_bytes, run_b_bytes)
    return SyntheticBundle(
        plan=plan,
        contexts=contexts,
        results=results,
        results_b=results_b,
        run_a=run_a,
        run_b=run_b,
        run_a_bytes=run_a_bytes,
        run_b_bytes=run_b_bytes,
        acceptance=acceptance,
    )


@pytest.fixture(scope="module")
def synthetic() -> SyntheticBundle:
    return _build_synthetic_bundle()


def test_r2_plan_run_acceptance_v2_and_repeated_synthetic_bytes(
    synthetic: SyntheticBundle,
) -> None:
    assert synthetic.plan["manifest_schema_version"] == c.PLAN_SCHEMA
    assert synthetic.run_a["manifest_schema_version"] == c.RUN_SCHEMA
    assert synthetic.acceptance["manifest_schema_version"] == c.ACCEPTANCE_SCHEMA
    assert synthetic.results == synthetic.results_b
    assert synthetic.results is not synthetic.results_b
    assert all(
        left is not right
        for left, right in zip(synthetic.results, synthetic.results_b, strict=True)
    )
    assert synthetic.run_a_bytes != synthetic.run_b_bytes
    assert c.canonical_bytes(synthetic.run_a["deterministic_payload"]) == c.canonical_bytes(
        synthetic.run_b["deterministic_payload"]
    )
    assert c.file_bytes(
        c.make_acceptance(synthetic.plan, synthetic.run_a_bytes, synthetic.run_b_bytes)
    ) == c.file_bytes(synthetic.acceptance)


def test_only_r2_protocol_is_accepted() -> None:
    c.protocol(c.PROTOCOL)
    for token in c.SUPERSEDED:
        with pytest.raises(c.ProtocolError, match="only R2"):
            c.protocol(token)


def test_seed_is_manifest_bound_deterministic_and_nul_free(
    synthetic: SyntheticBundle,
) -> None:
    identity = synthetic.plan["strategies"]["records"][0]
    first = c.seed_record(synthetic.plan["common_manifest_sha256"], identity)
    second = c.seed_record(synthetic.plan["common_manifest_sha256"], dict(identity))
    assert first == second
    assert first["seed_integer"] == str(int(first["seed_digest"], 16))
    with pytest.raises(c.ProtocolError, match="NUL"):
        c.seed_record(
            synthetic.plan["common_manifest_sha256"],
            {**identity, "adapter_path": identity["adapter_path"] + "\x00"},
        )


def test_manifest_schema_is_closed_and_self_hash_is_load_bearing(
    synthetic: SyntheticBundle,
) -> None:
    extra_plan = {**synthetic.plan, "unexpected": True}
    missing_plan = {key: value for key, value in synthetic.plan.items() if key != "execution"}
    tampered_plan = {**synthetic.plan, "common_manifest_sha256": ZERO_SHA}
    for candidate in (extra_plan, missing_plan, tampered_plan):
        with pytest.raises(c.ProtocolError):
            c.validate_plan(candidate)

    extra_run = {**synthetic.run_a, "unexpected": True}
    missing_run = {key: value for key, value in synthetic.run_a.items() if key != "campaign_label"}
    for candidate in (extra_run, missing_run):
        with pytest.raises(c.ProtocolError, match="unknown or missing"):
            c.validate_run(synthetic.plan, candidate)

    extra_acceptance = {**synthetic.acceptance, "unexpected": True}
    with pytest.raises(c.ProtocolError, match="unknown or missing"):
        c.validate_acceptance(
            synthetic.plan,
            extra_acceptance,
            synthetic.run_a_bytes,
            synthetic.run_b_bytes,
        )


def test_manifest_files_require_exactly_one_lf(synthetic: SyntheticBundle) -> None:
    raw = c.file_bytes(synthetic.plan)
    assert c.parse_file(raw) == synthetic.plan
    for invalid in (raw[:-1], raw + b"\n", raw[:-1] + b"\r\n", raw + b"trailing"):
        with pytest.raises(c.ProtocolError):
            c.parse_file(invalid)


def test_runner_lcj1_bytes_match_the_repository_codec() -> None:
    from lottolab.evidence import canonical_json

    value = {
        "alpha": [True, -9_007_199_254_740_991, "臺灣"],
        "nested_value": {"maximum": 9_007_199_254_740_991, "text": "R2"},
    }
    assert c.canonical_bytes(value) == canonical_json.canonical_bytes(value)
    assert c.file_bytes(value) == canonical_json.canonical_file_bytes(value)


def test_frozen_text_target_order_reverses_exactly_once() -> None:
    rows = [
        {"draw_date": "2026-01-01", "draw_number": "2", "source_row_id": 1},
        {"draw_date": "2026-01-01", "draw_number": "9", "source_row_id": 2},
        {"draw_date": "2026-01-01", "draw_number": "10", "source_row_id": 3},
    ]
    assert [row["draw_number"] for row in c.frozen_targets(rows)] == ["10", "2", "9"]


def test_evaluation_contract_uses_frozen_base_semantics_and_counts(
    synthetic: SyntheticBundle,
) -> None:
    assert synthetic.plan["evaluation"] == {
        "metric_contract": "M3_PLUS",
        "evaluator_version": "base_method_evaluation/1.0.0",
        "window_order": ["WINDOW_50", "WINDOW_300", "WINDOW_750", "FULL_HISTORY"],
        "random_reference": {"numerator": "4654", "denominator": "249711"},
    }
    payload = synthetic.run_a["deterministic_payload"]
    expected_windows = ["WINDOW_50", "WINDOW_300", "WINDOW_750", "FULL_HISTORY"]
    expected_counts = [50, 300, 750, 800]
    for evaluation in payload["evaluation_records"]:
        assert [window["window"] for window in evaluation["windows"]] == expected_windows
        assert [window["eligible_draw_count"] for window in evaluation["windows"]] == (
            expected_counts
        )
    artifact = payload["artifact"]
    assert artifact["evaluator_version"] == "base_method_evaluation/1.0.0"
    assert artifact["window_order"] == expected_windows
    assert len(artifact["records"]) == 55
    assert artifact["records"][18]["strategy_id"] == c.EXCLUDED
    evaluated = [record for record in artifact["records"] if record["status"] == "EVALUATED"]
    assert len(evaluated) == 54
    for record in evaluated:
        assert [window["window_kind"] for window in record["windows"]] == expected_windows
        assert [window["eligible_draw_count"] for window in record["windows"]] == expected_counts
    assert synthetic.acceptance["comparison_results"] == {
        "equal": True,
        "run_a_accepted_cell_count": 43_200,
        "run_b_accepted_cell_count": 43_200,
        "total_empirical_cell_count": 86_400,
        "evaluated_strategy_count": 54,
        "source_db_unchanged": True,
        "artifact_bytes_equal": True,
    }


def test_exec_capture_separates_diagnostics_from_stdout() -> None:
    output = runtime.exec_capture(
        [
            sys.executable,
            "-c",
            "import sys; sys.stdout.write('payload'); sys.stderr.write('diagnostic')",
        ]
    )
    assert output == b"payload"
    with pytest.raises(c.ProtocolError, match="synthetic failure"):
        runtime.exec_capture(
            [
                sys.executable,
                "-c",
                "import sys; sys.stderr.write('synthetic failure'); raise SystemExit(7)",
            ]
        )


def test_runtime_inventory_accepts_only_contained_directory_symlinks(tmp_path: Path) -> None:
    root = tmp_path / "runtime"
    target = root / "include/python3.13"
    target.mkdir(parents=True)
    (target / "Python.h").write_text("/* synthetic */\n", encoding="utf-8")
    (root / "Headers").symlink_to("include/python3.13", target_is_directory=True)
    assert runtime.runtime_file_inventory(root) == [
        {"path": "include/python3.13/Python.h", "sha256": c.sha256(b"/* synthetic */\n")}
    ]

    outside = tmp_path / "outside"
    outside.mkdir()
    (root / "Escapes").symlink_to(outside, target_is_directory=True)
    with pytest.raises(c.ProtocolError, match="escapes"):
        runtime.runtime_file_inventory(root)


def test_capture_runtime_succeeds_in_fresh_required_interpreter() -> None:
    script = (
        "from tools import next_draw_54_replay_r2_runtime as r; "
        "value=r.capture_runtime({'source_inventory_sha256':'0'*64}); "
        "print(value['schema_version'], len(value['python']['runtime_bundle_files']), "
        "len(value['platform']['cpu_features']))"
    )
    environment = {**os.environ, **c.ENVIRONMENT}
    environment.update(
        {
            "PYTHONPATH": str(REPO_ROOT),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONNOUSERSITE": "1",
        }
    )
    completed = subprocess.run(
        [sys.executable, "-B", "-s", "-P", "-c", script],
        cwd=REPO_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    schema, file_count, feature_count = completed.stdout.strip().split()
    assert schema == "NEXT_DRAW_54_REPLAY_RUNTIME_V2"
    assert int(file_count) > 0
    assert int(feature_count) > 0


def test_verify_source_succeeds_for_clean_pinned_fixture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source"
    catalog = source / "src/lottolab/strategies/catalog.py"
    package = source / "src/lottolab/__init__.py"
    lock = source / "uv.lock"
    project = source / "pyproject.toml"
    catalog.parent.mkdir(parents=True)
    package.parent.mkdir(parents=True, exist_ok=True)
    package.write_text("\n", encoding="utf-8")
    catalog.write_text("CATALOG = ()\n", encoding="utf-8")
    lock.write_text("version = 1\n", encoding="utf-8")
    project.write_text("[project]\nname = 'synthetic-source'\n", encoding="utf-8")

    def git(*arguments: str) -> str:
        completed = subprocess.run(
            ["git", *arguments],
            cwd=source,
            check=False,
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 0, completed.stderr
        return completed.stdout.strip()

    git("init", "-q")
    git("add", "src/lottolab", "uv.lock", "pyproject.toml")
    git(
        "-c",
        "user.name=R2 Fixture",
        "-c",
        "user.email=r2-fixture@example.invalid",
        "commit",
        "-q",
        "-m",
        "fixture",
    )
    head = git("rev-parse", "HEAD")
    tree = git("rev-parse", "HEAD^{tree}")
    catalog_blob = git("rev-parse", "HEAD:src/lottolab/strategies/catalog.py")
    monkeypatch.setattr(c, "HEAD", head)
    monkeypatch.setattr(c, "TREE", tree)
    monkeypatch.setattr(c, "CATALOG_BLOB", catalog_blob)
    monkeypatch.setattr(c, "CATALOG_SHA256", runtime.file_hash(catalog))
    monkeypatch.setattr(c, "LOCK_SHA256", runtime.file_hash(lock))

    authority = runtime.verify_source(source, runner_root=REPO_ROOT)
    assert authority["repository_head"] == head
    assert authority["repository_tree"] == tree
    assert {row["path"] for row in authority["load_bearing_blobs"]} == {
        "pyproject.toml",
        "src/lottolab/__init__.py",
        "src/lottolab/strategies/catalog.py",
        "uv.lock",
    }


def test_spawn_child_successfully_captures_one_fresh_process(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = tmp_path / "synthetic_r2_child.py"
    module.write_text(
        "import sys\nsys.stdout.buffer.write(b'synthetic-child-ok\\n')\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(coordinator, "MODULE", module.stem)
    monkeypatch.setattr(runtime, "RUNNER_ROOT", tmp_path)
    outcome = coordinator.spawn_child(
        tmp_path / "plan.json",
        tmp_path / "source",
        tmp_path / "source.sqlite3",
        "synthetic-strategy",
    )
    assert outcome.exit_status == 0
    assert outcome.pid > 0
    assert outcome.raw == b"synthetic-child-ok\n"


def test_import_anchor_rejects_source_hash_mismatch(tmp_path: Path) -> None:
    source = tmp_path / "src/lottolab"
    source.mkdir(parents=True)
    module = source / "__init__.py"
    module.write_text("VALUE = 1\n", encoding="utf-8")
    authority = {
        "load_bearing_blobs": [{"path": "src/lottolab/__init__.py", "sha256": _sha("different")}]
    }
    anchor = runtime.ImportAnchor(tmp_path, authority)
    spec = anchor.find_spec("lottolab")
    assert spec is not None and spec.loader is not None
    with pytest.raises(c.ProtocolError, match="import-source hash"):
        cast(Any, spec.loader).get_code("lottolab")


def test_child_database_verification_never_queries_sqlite(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    raw = b"synthetic sealed database bytes"
    database = tmp_path / "source.sqlite3"
    database.write_bytes(raw)
    plan = {
        "dataset": {
            "source_db": {
                "sha256": c.sha256(raw),
                "size_bytes": len(raw),
            }
        }
    }

    def reject_connect(*_args: Any, **_kwargs: Any) -> None:
        pytest.fail("child database verification must not query SQLite")

    monkeypatch.setattr(runtime.sqlite3, "connect", reject_connect)
    runtime.verify_database_file(database, plan)


def _prepared(
    plan: dict[str, Any],
    strategy_id: str,
    *,
    execute: Callable[[], None] = lambda: None,
    cache: object | None = None,
) -> runtime.PreparedReplay:
    return runtime.PreparedReplay(
        execute=execute,
        strategy_ids=(strategy_id,),
        targets=plan["targets"]["vector"],
        cache=cache,
    )


def test_post_import_seed_guard_cache_none_and_partial_output(
    synthetic: SyntheticBundle,
) -> None:
    identity = synthetic.plan["strategies"]["records"][0]
    state = random.getstate()
    try:
        with pytest.raises(c.ProtocolError, match="bootstrap RNG drift"):
            runtime.execute_seeded(
                synthetic.plan,
                [identity["strategy_id"]],
                lambda _ledger: (
                    random.random(),
                    _prepared(synthetic.plan, identity["strategy_id"]),
                )[1],
            )
    finally:
        random.setstate(state)

    try:
        with pytest.raises(c.ProtocolError, match="cache=None"):
            runtime.execute_seeded(
                synthetic.plan,
                [identity["strategy_id"]],
                lambda _ledger: _prepared(synthetic.plan, identity["strategy_id"], cache=object()),
            )
    finally:
        random.setstate(state)

    try:
        with pytest.raises(c.ProtocolError, match="partial output"):
            runtime.execute_seeded(
                synthetic.plan,
                [identity["strategy_id"]],
                lambda _ledger: _prepared(synthetic.plan, identity["strategy_id"]),
            )
    finally:
        random.setstate(state)


def test_execute_seeded_successfully_observes_all_800_cells(
    synthetic: SyntheticBundle,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    identity = synthetic.plan["strategies"]["records"][0]
    rows = synthetic.plan["dataset"]["snapshot"]["draws"]
    events: list[str] = []
    original_seed = random.seed
    original_random = random.Random

    def observed_seed(value: int, version: int = 2) -> None:
        events.append("module_seed")
        original_seed(value, version=version)

    def observed_private_random(value: int) -> random.Random:
        events.append("private_random")
        return original_random(value)

    monkeypatch.setattr(random, "seed", observed_seed)
    monkeypatch.setattr(random, "Random", observed_private_random)

    def factory(ledger: runtime.CellLedger) -> runtime.PreparedReplay:
        def execute() -> None:
            for context in ledger.contexts:
                history = [row for row in rows if c.draw_key(row) < c.draw_key(context["target"])]
                ledger.before([c.adapter_row(row) for row in history])
                random.random()
                ledger.after([1, 2, 3, 4, 5, 6], [1, 2, 3, 4, 5, 6])

        return _prepared(synthetic.plan, identity["strategy_id"], execute=execute)

    state = random.getstate()
    try:
        observation = runtime.execute_seeded(
            synthetic.plan,
            [identity["strategy_id"]],
            factory,
        )
    finally:
        random.setstate(state)
    assert len(observation["cells"]) == c.TARGET_COUNT
    assert observation["post_seed_rng_sha256"] != observation["final_rng_sha256"]
    assert observation["bootstrap_before_sha256"] == observation["bootstrap_after_sha256"]
    assert events[-1] == "module_seed"


def test_run_campaign_succeeds_with_synthetic_child_transport(
    synthetic: SyntheticBundle,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan_path = tmp_path / "plan.json"
    plan_path.write_bytes(c.file_bytes(synthetic.plan))
    source_root = tmp_path / "source"
    source_root.mkdir()
    source_db = tmp_path / "source.sqlite3"
    source_db.write_bytes(b"synthetic sealed DB")
    result_by_id = {
        result["strategy_identity"]["strategy_id"]: result for result in synthetic.results
    }
    monkeypatch.setattr(c, "REAL_DATA", c.SYNTHETIC_DATA)

    def verified_source(_root: Path) -> dict[str, Any]:
        return synthetic.plan["authority"]

    def verified_database(_path: Path, _plan: dict[str, Any]) -> None:
        return None

    def fingerprint(_authority: dict[str, Any]) -> dict[str, Any]:
        return synthetic.plan["runtime_fingerprint"]

    monkeypatch.setattr(runtime, "verify_source", verified_source)
    monkeypatch.setattr(runtime, "verify_database", verified_database)
    monkeypatch.setattr(runtime, "capture_runtime", fingerprint)
    clock_index = 0
    launch_index = 0

    def clock() -> str:
        nonlocal clock_index
        value = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(microseconds=clock_index)
        clock_index += 1
        return _timestamp(value)

    def launch(
        _plan_path: Path,
        _source_root: Path,
        _source_db: Path,
        strategy_id: str,
    ) -> coordinator.SpawnOutcome:
        nonlocal launch_index
        child = c.make_child_result(result_by_id[strategy_id], ZERO_SHA, ZERO_SHA)
        launch_index += 1
        return coordinator.SpawnOutcome(
            7000 + launch_index,
            0,
            clock(),
            clock(),
            1,
            c.file_bytes(child),
        )

    monkeypatch.setattr(coordinator, "utc_now", clock)
    monkeypatch.setattr(coordinator, "spawn_child", launch)
    path, manifest = coordinator.run_campaign(
        plan_path,
        source_root,
        source_db,
        tmp_path / "campaign",
        "SYNTHETIC_COORDINATOR",
    )
    assert path.read_bytes() == c.file_bytes(manifest)
    assert len(manifest["deterministic_payload"]["strategy_results"]) == c.STRATEGY_COUNT
    assert len(manifest["operational_envelope"]["attempts"]) == c.STRATEGY_COUNT


def test_one_strategy_per_child_concurrency_one_zone_exclusion_and_old84_false(
    synthetic: SyntheticBundle,
) -> None:
    identities = synthetic.plan["strategies"]["records"]
    with pytest.raises(c.ProtocolError, match="exactly one strategy"):
        c.child_identity(
            synthetic.plan, [identities[0]["strategy_id"], identities[1]["strategy_id"]]
        )
    with pytest.raises(c.ProtocolError, match="zone-momentum"):
        c.child_identity(synthetic.plan, [c.EXCLUDED])
    with pytest.raises(c.ProtocolError, match="concurrency"):
        coordinator.validate_concurrency(2)
    assert synthetic.plan["execution"]["max_concurrency"] == 1
    assert synthetic.plan["execution"]["old_84_reuse"] is False
    assert synthetic.run_a["deterministic_payload"]["old_84_reuse"] is False
    assert synthetic.acceptance["old_84_reuse_attestation"] is False

    old84 = {
        **synthetic.plan,
        "execution": {**synthetic.plan["execution"], "old_84_reuse": True},
    }
    with pytest.raises(c.ProtocolError, match="execution contract"):
        c.validate_plan(c.seal(old84, "plan_manifest_sha256"))


def test_exact_five_private_rng_exceptions_and_frozen_zone_record(
    synthetic: SyntheticBundle,
) -> None:
    assert tuple(row["strategy_id"] for row in c.private_exceptions()) == c.PRIVATE_IDS
    assert len(c.private_exceptions()) == 5
    excluded = synthetic.plan["strategies"]["excluded"]
    assert excluded == {
        "strategy_id": c.EXCLUDED,
        "strategy_name": excluded["strategy_name"],
        "filtered_catalog_ordinal": 19,
        "status": "DRIVER_ERROR",
        "windows": [],
    }
    assert all(row["strategy_id"] != c.EXCLUDED for row in synthetic.plan["strategies"]["records"])

    bad_runtime = {
        **synthetic.plan["runtime_fingerprint"],
        "runner_files": [
            *synthetic.plan["runtime_fingerprint"]["runner_files"],
            {"path": "tools/unapproved_runner.py", "sha256": _sha("unapproved")},
        ],
    }
    with pytest.raises(c.ProtocolError, match="exact runner file inventory"):
        c.validate_runtime(bad_runtime)


def test_unclassified_private_rng_and_global_rewind_are_rejected() -> None:
    with pytest.raises(c.ProtocolError, match="forbidden"), runtime.ExecutionGuard():
        random.Random(1)
    with pytest.raises(c.ProtocolError, match="forbidden"), runtime.ExecutionGuard():
        random.setstate(random.getstate())
    with runtime.ExecutionGuard(allow_private_random=True):
        random.Random(1)


def test_whole_strategy_restart_records_failed_attempt_lineage(
    synthetic: SyntheticBundle,
) -> None:
    identity = synthetic.plan["strategies"]["records"][0]
    child = c.make_child_result(synthetic.results[0], ZERO_SHA, ZERO_SHA)
    base = datetime(2026, 1, 1, tzinfo=UTC)
    outcomes = iter(
        (
            coordinator.SpawnOutcome(
                pid=9001,
                exit_status=1,
                started_at_utc=_timestamp(base),
                ended_at_utc=_timestamp(base),
                elapsed_ns=1,
                raw=b"partial child output",
            ),
            coordinator.SpawnOutcome(
                pid=9002,
                exit_status=0,
                started_at_utc=_timestamp(base + timedelta(microseconds=1)),
                ended_at_utc=_timestamp(base + timedelta(microseconds=1)),
                elapsed_ns=1,
                raw=c.file_bytes(child),
            ),
        )
    )
    result, lineage = coordinator.execute_strategy_with_restarts(
        synthetic.plan,
        identity,
        run_id="lineage",
        strategy_index=1,
        max_attempts=2,
        launch=lambda _strategy_id: next(outcomes),
    )
    assert result == synthetic.results[0]
    assert [attempt["status"] for attempt in lineage] == ["FAILED", "SUCCEEDED"]
    assert lineage[0]["result_sha256"] == ""
    assert lineage[0]["partial_output_sha256"] == c.sha256(b"partial child output")
    assert lineage[1]["ordinal"] == 2
    assert lineage[1]["previous_attempt_id"] == lineage[0]["attempt_id"]

    envelope = {
        **synthetic.run_a["operational_envelope"],
        "attempts": [*lineage, *synthetic.run_a["operational_envelope"]["attempts"][1:]],
    }
    c.validate_operational(synthetic.plan, envelope, synthetic.results)


def test_partial_child_result_is_rejected(synthetic: SyntheticBundle) -> None:
    identity = synthetic.plan["strategies"]["records"][0]
    partial_result = c.seal(
        {
            **synthetic.results[0],
            "adapter_invocation_count": c.TARGET_COUNT - 1,
            "cells": synthetic.results[0]["cells"][:-1],
        },
        "strategy_output_sha256",
    )
    child = c.make_child_result(partial_result, ZERO_SHA, ZERO_SHA)
    with pytest.raises(c.ProtocolError, match=r"800 adapter invocations|partial child output"):
        c.validate_child_result(synthetic.plan, identity, child)


def test_operational_metadata_is_ignored_but_payload_mismatch_is_rejected(
    synthetic: SyntheticBundle,
) -> None:
    assert synthetic.run_a["operational_envelope"] != synthetic.run_b["operational_envelope"]
    assert synthetic.acceptance["comparison_results"]["equal"] is True

    identity = synthetic.plan["strategies"]["records"][0]
    alternate_results = [
        _strategy_result(
            synthetic.plan,
            synthetic.contexts,
            identity,
            first_ticket=[7, 8, 9, 10, 11, 12],
        ),
        *synthetic.results[1:],
    ]
    alternate_run = c.make_run(
        synthetic.plan,
        alternate_results,
        _operational(alternate_results, "run-alt", 2),
        "SYNTHETIC_ALT",
    )
    alternate_bytes = c.file_bytes(alternate_run)
    assert c.canonical_bytes(alternate_run["deterministic_payload"]) != c.canonical_bytes(
        synthetic.run_a["deterministic_payload"]
    )
    with pytest.raises(c.ProtocolError, match="two-campaign byte comparison"):
        c.make_acceptance(synthetic.plan, synthetic.run_a_bytes, alternate_bytes)
