"""Task-scoped Python audit observer; records no environment or file contents."""
import errno
import json
import os
from pathlib import Path
import sys
import threading
import time


def install(role, config_path, denial_probe=False):
    config = json.loads(Path(config_path).read_text())
    destination = str(Path(config["evidence_root"]) / (role + "-" + str(os.getpid()) + ".jsonl"))
    guard = threading.local()

    def emit(operation, **fields):
        if getattr(guard, "active", False):
            return
        guard.active = True
        try:
            event = {"time_ns": time.time_ns(), "monotonic_ns": time.monotonic_ns(),
                     "pid": os.getpid(), "ppid": os.getppid(), "pgid": os.getpgrp(),
                     "role": role, "operation": operation, **fields}
            fd = os.open(destination, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
            try:
                os.write(fd, (json.dumps(event, sort_keys=True, default=os.fspath) + "\n").encode())
                os.fsync(fd)
            finally:
                os.close(fd)
        finally:
            guard.active = False

    def path(value):
        return os.path.abspath(os.fsdecode(value)) if isinstance(value, (str, bytes)) else str(value)

    def audit(event, args):
        if getattr(guard, "active", False):
            return
        if event == "open":
            target, mode, flags = args
            if (flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)) or (mode and any(c in mode for c in "wax+")):
                emit("file-write-request", audit_event=event, path=path(target), mode=mode, flags=flags)
        elif event in {"os.mkdir", "os.remove", "os.rmdir", "os.rename", "os.link", "os.symlink", "os.chmod", "os.truncate"}:
            emit("filesystem-request", audit_event=event, paths=[path(args[0])],
                 destination=path(args[1]) if event in {"os.rename", "os.link", "os.symlink"} else None)
        elif event == "subprocess.Popen":
            executable, argv, cwd, _environment = args
            emit("spawn-request", executable=str(executable), argv=argv, cwd=cwd)
        elif event in {"socket.connect", "socket.bind"}:
            emit("network-request", audit_event=event)

    sys.addaudithook(audit)
    emit("observer-start", executable=sys.executable, real_executable=os.path.realpath(sys.executable),
         argv=sys.argv, observer_path=__file__, observer_log=destination)
    if denial_probe:
        probe = Path(config["isolated_repo"]) / ".git" / "ac10-python-write-denial-probe"
        try:
            fd = os.open(probe, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except OSError as error:
            emit("sandbox-write-denied", path=str(probe), errno=error.errno,
                 denied=error.errno in (errno.EPERM, errno.EACCES), exists=probe.exists())
            if error.errno not in (errno.EPERM, errno.EACCES) or probe.exists():
                os._exit(126)
        else:
            os.close(fd)
            emit("sandbox-write-denial-FAILED", path=str(probe))
            os._exit(126)
    return emit
