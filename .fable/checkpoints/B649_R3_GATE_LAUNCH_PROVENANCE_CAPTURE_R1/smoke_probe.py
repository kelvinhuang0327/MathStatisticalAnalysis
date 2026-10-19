"""Controlled smoke: stdlib/metadata reads plus one task-owned umask probe."""
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import stat
import sys
import time

child_started_ns = time.time_ns()
assert sys.version_info[:2] == (3, 13)
expected_exit = int(sys.argv[1])
assert expected_exit in (0, 23)
launch_path = Path(os.environ["GATE_LAUNCH_RECEIPT"])
launch_bytes = launch_path.read_bytes()
launch_sha = hashlib.sha256(launch_bytes).hexdigest()
assert launch_sha == os.environ["GATE_LAUNCH_SHA256"]
launch = json.loads(launch_bytes)
assert launch["stage"] == "BEFORE_CHILD_SPAWN"
assert launch_path.stat().st_mtime_ns <= child_started_ns
assert launch["cwd"] == os.getcwd()
assert launch["argv"] == [sys.executable, "-B", *sys.argv]
assert launch["python"]["executable"] == sys.executable
assert launch["python"]["pytest"] == importlib.metadata.version("pytest")
assert launch["process"]["pid"] == os.getppid()
effective_umask = os.umask(0o077)
os.umask(effective_umask)
assert effective_umask == 0o077
runtime = Path(os.environ["GATE_RUNTIME_ROOT"]).resolve()
for directory in (runtime, Path(os.environ["LOTTOLAB_DATA_DIR"]), Path(os.environ["GATE_BASETEMP"])):
    assert stat.S_IMODE(directory.stat().st_mode) == 0o700
    assert directory.stat().st_uid == os.getuid()
    assert directory.resolve().is_relative_to(runtime)
probe = runtime / "work" / "umask-probe.txt"
with probe.open("x") as stream:
    stream.write("controlled smoke umask probe\n")
assert stat.S_IMODE(probe.stat().st_mode) == 0o600
assert sys.dont_write_bytecode and os.environ["PYTHONDONTWRITEBYTECODE"] == "1"
assert not os.environ.get("PYTHONPATH")
print(json.dumps({"smoke": "normal" if expected_exit == 0 else "negative", "observed_pid": os.getpid(),
    "observed_ppid": os.getppid(), "observed_pgid": os.getpgrp(), "child_started_ns": child_started_ns,
    "launch_receipt_exists_before_child": True, "launch_path": str(launch_path), "launch_sha256": launch_sha,
    "launch_mtime_ns": launch_path.stat().st_mtime_ns, "observed_cwd": os.getcwd(),
    "observed_python": sys.executable, "observed_version": sys.version, "observed_pytest": importlib.metadata.version("pytest"),
    "observed_appdata": os.environ["LOTTOLAB_DATA_DIR"], "observed_appdata_mode": "0700",
    "observed_umask": format(effective_umask, "04o"), "observed_basetemp": os.environ["GATE_BASETEMP"],
    "observed_bytecode_disabled": sys.dont_write_bytecode, "probe_path": str(probe), "probe_mode": "0600",
    "expected_exit": expected_exit}), flush=True)
print("normal-smoke-stderr" if expected_exit == 0 else "negative-smoke-stderr", file=sys.stderr, flush=True)
sys.exit(expected_exit)
