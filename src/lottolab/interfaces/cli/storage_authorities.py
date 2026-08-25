"""CLI inspection commands for the canonical storage-authority registry."""

from __future__ import annotations

import typer

from lottolab.infrastructure.persistence.storage_authorities import (
    StorageAuthorityError,
    StorageAuthorityRegistry,
    StorageAuthorityResolver,
    StorageAuthorityVerification,
)

storage_authorities_app = typer.Typer(
    no_args_is_help=True,
    help="Inspect the named LottoLab storage authorities without mutating them.",
)


def _resolver() -> StorageAuthorityResolver:
    return StorageAuthorityResolver(StorageAuthorityRegistry.from_file())


def _format(result: StorageAuthorityVerification) -> str:
    authority = result.authority
    resolution = "UNRESOLVED" if result.path is None else "RESOLVED"
    exists = "YES" if result.exists else "NO"
    schema = "PASS" if result.schema_valid is True else (
        "FAIL" if result.schema_valid is False else "N/A"
    )
    sha = "PASS" if result.sha_match is True else (
        "FAIL" if result.sha_match is False else "N/A"
    )
    query_only = "YES" if result.query_only is True else (
        "NO" if result.query_only is False else "N/A"
    )
    outcome = "PASS" if result.passed is True else (
        "UNRESOLVED" if result.passed is None else "FAIL"
    )
    error = f" error={result.error}" if result.error else ""
    return (
        f"{authority.capability} authority={authority.authority_id} "
        f"status={authority.status} resolution={resolution} exists={exists} "
        f"schema={schema} sha256={sha} query_only={query_only} outcome={outcome}{error}"
    )


@storage_authorities_app.command("status")
def storage_authorities_status() -> None:
    """Report registry status, resolution, schema, and digest state."""

    try:
        resolver = _resolver()
        results = resolver.status()
    except (OSError, StorageAuthorityError) as exc:
        typer.echo(f"storage-authorities status error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(
        f"STORAGE_AUTHORITY_REGISTRY version={resolver.registry.version} "
        f"authorities={len(results)} registry={resolver.registry.registry_path}"
    )
    for result in results:
        typer.echo(_format(result))


@storage_authorities_app.command("verify")
def storage_authorities_verify() -> None:
    """Deep-verify every immutable authority using read-only SQLite probes."""

    try:
        resolver = _resolver()
        results = resolver.verify_all()
        unresolved_results = tuple(
            result for result in resolver.status() if result.passed is None
        )
    except (OSError, StorageAuthorityError) as exc:
        typer.echo(f"storage-authorities verify error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    failures = 0
    for result in results:
        typer.echo(_format(result))
        if result.passed is False:
            failures += 1
    for result in unresolved_results:
        typer.echo(_format(result))
    typer.echo(
        f"VERIFIED={len(results) - failures} FAILURES={failures} "
        f"UNRESOLVED={len(unresolved_results)}"
    )
    if failures:
        raise typer.Exit(code=1)


__all__ = ["storage_authorities_app"]
