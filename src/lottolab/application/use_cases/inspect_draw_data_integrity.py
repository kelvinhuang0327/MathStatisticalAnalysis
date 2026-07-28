"""Read-only use case: inspect one explicitly supplied draw database.

The reader boundary is defined locally (structural ``Protocol``) rather than
registered in the shared ``application.ports`` registry: this use case has no
factory, no CLI wiring, and no dependency-injection entry anywhere else in the
application layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

from lottolab.domain.draw_data_integrity import DrawDataIntegrityReport


@dataclass(frozen=True, slots=True)
class InspectDrawDataIntegrityRequest:
    """Explicit caller-supplied database path; no default or ambient resolution."""

    database: Path


@runtime_checkable
class DrawDataIntegrityReader(Protocol):
    """Read-only boundary that inspects one explicitly supplied draw database."""

    def inspect(self, database: Path) -> DrawDataIntegrityReport:
        """Return a closed integrity report; never creates or migrates storage."""
        ...


class InspectDrawDataIntegrity:
    """Delegates to a read-only reader; holds no storage knowledge itself."""

    def __init__(self, reader: DrawDataIntegrityReader) -> None:
        self._reader = reader

    def execute(self, request: InspectDrawDataIntegrityRequest) -> DrawDataIntegrityReport:
        return self._reader.inspect(request.database)
