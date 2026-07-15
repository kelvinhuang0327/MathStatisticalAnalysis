"""QuantLab CLI entry point."""

from __future__ import annotations

import platform

import typer

from quantlab import __version__
from quantlab.strategies.catalog import production_catalog

app = typer.Typer(no_args_is_help=True, help="QuantLab — 數理統計分析平台 CLI")


@app.callback()
def root() -> None:
    """QuantLab CLI (keeps sub-command mode even with a single command)."""


@app.command()
def info() -> None:
    """Show runtime and catalog summary."""
    catalog = production_catalog()
    typer.echo(
        f"quantlab={__version__} python={platform.python_version()} strategies={len(catalog)}"
    )


def main() -> None:
    app()
