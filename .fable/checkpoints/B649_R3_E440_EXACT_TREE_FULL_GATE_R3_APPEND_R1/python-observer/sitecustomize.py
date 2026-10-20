"""Task-scoped Python audit observer loaded through the launcher environment overlay."""
import errno, json, os, sys, threading, time, stat
R3 = "/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.fable/checkpoints/B649_R3_E440_EXACT_TREE_FULL_GATE_R3_APPEND_R1"
EXTERNAL = "/private/tmp/mathstat-e440-full-gate-r3-repo"
ROLE = os.environ.get("FABLE_R3_OBSERVER_ROLE", "unclassified")
TAG = os.environ.get("FABLE_R3_RUN_TAG", "unknown")
DEST = os.path.join(R3, f"python-observer-{TAG}-{ROLE}-{os.getpid()}.jsonl")
_guard = threading.local()
_fd = os.open(DEST, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
os.fsync(_fd)

def _path(value):
    if isinstance(value, (str, bytes, os.PathLike)):
        return os.path.abspath(os.fsdecode(value))
    return repr(value)

def emit(operation, **fields):
    if getattr(_guard, "active", False):
        return
    _guard.active = True
    try:
        event = {"time_ns": time.time_ns(), "monotonic_ns": time.monotonic_ns(),
                 "pid": os.getpid(), "ppid": os.getppid(), "role": ROLE,
                 "run_tag": TAG, "operation": operation, **fields}
        os.write(_fd, (json.dumps(event, sort_keys=True, default=os.fspath) + "\n").encode())
    finally:
        _guard.active = False

def _audit(event, args):
    if getattr(_guard, "active", False):
        return
    if event == "open":
        target, mode, flags = args
        if ((isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))
                or (mode and any(c in mode for c in "wax+"))):
            emit("file-write-request", audit_event=event, path=_path(target), mode=mode, flags=flags)
    elif event in {"os.mkdir", "os.remove", "os.rmdir", "os.rename", "os.link", "os.symlink", "os.chmod", "os.truncate"}:
        emit("filesystem-request", audit_event=event, paths=[_path(args[0])],
             destination=_path(args[1]) if event in {"os.rename", "os.link", "os.symlink"} else None)
    elif event == "subprocess.Popen":
        executable, argv, cwd, _environment = args
        emit("subprocess-request", executable=_path(executable), argv=argv, cwd=_path(cwd) if cwd else None)
    elif event in {"socket.connect", "socket.bind"}:
        emit("network-request", audit_event=event)
    elif event in {"os.fork", "os.forkpty"}:
        emit("fork-request", audit_event=event)

sys.addaudithook(_audit)
try:
    lock_stat = os.fstat(10)
    lock_fd = {"open": True, "regular_file": stat.S_ISREG(lock_stat.st_mode),
               "dev": lock_stat.st_dev, "ino": lock_stat.st_ino,
               "mode": format(stat.S_IMODE(lock_stat.st_mode), "04o")}
except OSError as error:
    lock_fd = {"open": False, "errno": error.errno}
emit("observer-start", executable=sys.executable, real_executable=os.path.realpath(sys.executable),
     argv=sys.argv, cwd=os.getcwd(), observer_path=__file__, observer_log=DEST,
     lock_fd10=lock_fd, parent_pid_expected=os.environ.get("FABLE_R3_OBSERVER_ROOT_PID"))
if ROLE == "pytest" and os.getppid() == int(os.environ.get("FABLE_R3_OBSERVER_ROOT_PID", "-1")):
    os.environ["PYTEST_PLUGINS"] = "r3_pytest_collector"
    os.environ["FABLE_R3_NODEIDS_PATH"] = os.path.join(R3, f"pytest-nodeids-{TAG}.json")
    os.environ["FABLE_R3_OUTCOMES_PATH"] = os.path.join(R3, f"pytest-outcomes-{TAG}.json")
    emit("pytest-observer-plugin-enabled", plugin="r3_pytest_collector",
         nodeids_path=os.environ["FABLE_R3_NODEIDS_PATH"], outcomes_path=os.environ["FABLE_R3_OUTCOMES_PATH"])
    probe = os.path.join(EXTERNAL, "src", f".r3-write-denial-{TAG}-{os.getpid()}")
    if os.path.lexists(probe):
        emit("sandbox-probe-invalid-existing-path", path=probe)
        os._exit(126)
    try:
        fd = os.open(probe, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except OSError as error:
        emit("sandbox-write-denial-probe", path=probe, errno=error.errno,
             denied=error.errno in (errno.EPERM, errno.EACCES), exists=os.path.lexists(probe))
        if error.errno not in (errno.EPERM, errno.EACCES) or os.path.lexists(probe):
            os._exit(126)
    else:
        os.close(fd)
        emit("sandbox-write-denial-failed", path=probe)
        os._exit(126)
    os.fsync(_fd)
