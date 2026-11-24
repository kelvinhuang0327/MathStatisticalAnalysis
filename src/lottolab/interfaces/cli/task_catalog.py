"""Typer CLI interface for task catalog operations."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, cast

import typer

from lottolab.infrastructure.persistence.project_database_paths import canonical_project_root
from lottolab.infrastructure.task_catalog import build_catalog, find_in_catalog

app = typer.Typer(
    no_args_is_help=True,
    help="Read-only catalog for task receipts, stage manifests, and tombstones.",
)


def _default_formal_db(project_root: Path) -> Path:
    config_path = project_root / "data" / "databases" / "database-locations.json"
    default_name = "replay-backfill.sqlite3"
    if config_path.is_file():
        try:
            with open(config_path, encoding="utf-8") as f:
                data: object = json.load(f)
            if isinstance(data, dict):
                data_dict = cast(dict[str, object], data)
                read_dbs = data_dict.get("read_databases")
                if isinstance(read_dbs, dict):
                    read_dbs_dict = cast(dict[str, object], read_dbs)
                    target = read_dbs_dict.get("LOTTOLAB_REPLAY_BACKFILL_DB")
                    if isinstance(target, str):
                        default_name = target
        except Exception:
            pass
    return project_root / "data" / "databases" / default_name


@app.command("build")
def build_command(
    root: Annotated[
        list[Path] | None,
        typer.Option(
            "--root", help="Root directory containing task folders. Can specify multiple."
        ),
    ] = None,
    output_dir: Annotated[
        Path | None,
        typer.Option("--output-dir", help="Output directory for generated catalog files."),
    ] = None,
    formal_db: Annotated[
        Path | None,
        typer.Option("--formal-db", help="Path to formal replay-backfill sqlite3 database."),
    ] = None,
    no_formal_lookup: Annotated[
        bool,
        typer.Option("--no-formal-lookup", help="Skip querying formal replay-backfill database."),
    ] = False,
) -> None:
    """Rebuild derived index into tasks.jsonl, stages.jsonl, and tombstones.jsonl."""
    project_root = canonical_project_root()
    roots = root if root else [project_root / ".task-data", project_root.parent / ".task-data"]
    out_dir = output_dir if output_dir is not None else project_root / ".task-data" / "_catalog"
    formal_db_p = formal_db if formal_db is not None else _default_formal_db(project_root)

    result = build_catalog(
        roots=roots,
        output_dir=out_dir,
        formal_db_path=formal_db_p,
        no_formal_lookup=no_formal_lookup,
    )
    typer.echo(
        f"status=BUILT tasks={result.tasks_count} stages={result.stages_count} "
        f"tombstones={result.tombstones_count} formal_lookup={result.formal_db_info['lookup']}"
    )


@app.command("find")
def find_command(
    query: Annotated[str, typer.Argument(help="Case-insensitive substring query.")],
    kind: Annotated[
        str,
        typer.Option(
            "--kind", help="Kind of catalog records to search: tasks|stages|tombstones|all"
        ),
    ] = "all",
    catalog_dir: Annotated[
        Path | None,
        typer.Option("--catalog-dir", help="Catalog directory containing JSONL files."),
    ] = None,
) -> None:
    """Find query in catalog files and print matches to stdout."""
    project_root = canonical_project_root()
    cat_dir = catalog_dir if catalog_dir is not None else project_root / ".task-data" / "_catalog"

    try:
        count, matches = find_in_catalog(query=query, kind=kind, catalog_dir=cat_dir)
    except (FileNotFoundError, ValueError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    for matched_kind, matched_line in matches:
        typer.echo(f"{matched_kind}\t{matched_line}")

    typer.echo(f"matched={count}", err=True)
