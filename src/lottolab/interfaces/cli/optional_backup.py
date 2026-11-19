"""Create optional full SQLite backups with a destination-volume space guard."""

from __future__ import annotations

import os
import shutil
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path
from typing import Annotated

import typer

MIN_FREE_BYTES = 15 * 1024**3


def optional_backup_command(
    source: Annotated[Path, typer.Argument(help="Source SQLite database")],
    destination: Annotated[Path, typer.Argument(help="New backup file; parent must exist")],
) -> None:
    """Create an optional full SQLite backup without replacing an existing file."""
    try:
        source = source.resolve(strict=True)
        parent = destination.absolute().parent.resolve(strict=True)
        destination = parent / destination.name
        free = shutil.disk_usage(parent).free
        if free < MIN_FREE_BYTES:
            raise ValueError(
                f"optional backup refused: destination has {free} bytes free; "
                f"at least {MIN_FREE_BYTES} bytes required"
            )
        # mode=ro prevents SQLite from creating or writing the source database.
        with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as src:
            src.execute("SELECT count(*) FROM sqlite_master").fetchone()
            # Publish only a complete backup, using a same-volume hard link that
            # fails if the requested destination already exists (even a symlink).
            with tempfile.TemporaryDirectory(prefix=".optional-backup-", dir=parent) as tmp:
                temporary = Path(tmp) / "backup.sqlite3"
                fd = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                os.close(fd)
                with closing(sqlite3.connect(temporary)) as dst:
                    src.backup(dst)
                os.link(temporary, destination)
    except (OSError, sqlite3.Error, ValueError) as exc:
        typer.echo(f"optional backup error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"Optional backup created: {destination}")
