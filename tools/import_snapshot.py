"""Verify a hash-pinned snapshot exported from the legacy system.

Usage:
    uv run python tools/import_snapshot.py verify data/manifests/<name>.yaml

Manifest format (committed to git; payloads under data/ are not):
    source_repo: /Users/kelvin/Kelvin-WorkSpace/LotteryNew
    source_commit: <git commit hash at export time>
    exported_at: <ISO-8601>
    root: data/<snapshot-dir>
    files:
      - {path: draws_daily539.parquet, sha256: <hex>}
"""

from __future__ import annotations

from pathlib import Path

import typer
import yaml

from quantlab.infrastructure.persistence.snapshot import SnapshotEntry, verify_snapshot

app = typer.Typer(no_args_is_help=True)


@app.command()
def verify(manifest_path: Path) -> None:
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    root = Path(manifest["root"])
    entries = tuple(
        SnapshotEntry(relative_path=item["path"], sha256=item["sha256"])
        for item in manifest["files"]
    )
    verify_snapshot(root, entries)
    typer.echo(f"OK: {len(entries)} files verified against {manifest_path}")


if __name__ == "__main__":
    app()
