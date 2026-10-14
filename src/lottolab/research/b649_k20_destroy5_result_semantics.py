"""Dual-threshold result semantics for the B649 K20 Destroy5 campaign."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

FROZEN_START_COUNT = 313_239_661
INITIAL_VERIFIED_INCUMBENT_COUNT = 313_263_888
INITIAL_VERIFIED_INCUMBENT_SHA256 = (
    "eaed652900d101881b678a1515d2a366bff9de6723dbec2ec9c82fe0d0d7844c"
)
INITIAL_VERIFIED_INCUMBENT_SOURCE_COMMIT = (
    "032ce592c3efd0ac4b5b82a813d157224419c794"
)
INITIAL_VERIFIED_INCUMBENT_ARTIFACT_LOCATOR = (
    "git:032ce592c3efd0ac4b5b82a813d157224419c794:"
    "docs/research/matrix-native-results/"
    "b649-k20-12-8-winner-two-ticket-ascent-r1-result.json"
)


@dataclass(frozen=True)
class IncumbentEvidence:
    """A proposed launch-time incumbent replacement from a terminal result."""

    count: int
    sha256: str
    artifact_locator: str
    source_commit: str
    terminal: bool
    canonical_verified: bool
    directly_comparable: bool
    newer: bool


@dataclass(frozen=True)
class IncumbentAuthority:
    count: int
    sha256: str
    artifact_locator: str
    source_commit: str


INITIAL_INCUMBENT_AUTHORITY = IncumbentAuthority(
    count=INITIAL_VERIFIED_INCUMBENT_COUNT,
    sha256=INITIAL_VERIFIED_INCUMBENT_SHA256,
    artifact_locator=INITIAL_VERIFIED_INCUMBENT_ARTIFACT_LOCATOR,
    source_commit=INITIAL_VERIFIED_INCUMBENT_SOURCE_COMMIT,
)


def _valid_count(value: int, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field} must be a non-negative integer")
    return value


def _valid_sha256(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _valid_commit(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{40}", value) is not None


def _valid_source_identity(artifact_locator: object, source_commit: object) -> bool:
    if not isinstance(artifact_locator, str) or not _valid_commit(source_commit):
        return False
    if not artifact_locator.startswith("git:"):
        return False
    parts = artifact_locator.split(":", maxsplit=2)
    return (
        len(parts) == 3
        and parts[1] == source_commit
        and _valid_commit(parts[1])
        and bool(parts[2].strip())
        and not parts[2].startswith("/")
    )


def resolve_launch_time_incumbent(
    candidates: Iterable[IncumbentEvidence] = (),
) -> IncumbentAuthority:
    """Keep the initial incumbent unless a higher terminal result is verified.

    A higher claimed count that lacks any required evidence fails closed. The
    caller must build each evidence record from a directly observed terminal
    artifact and its canonical recount.
    """

    current = INITIAL_INCUMBENT_AUTHORITY
    execution_authority_fields(current)
    for candidate in candidates:
        count = _valid_count(candidate.count, field="candidate count")
        if count <= INITIAL_VERIFIED_INCUMBENT_COUNT:
            continue
        if not (
            candidate.terminal is True
            and candidate.canonical_verified is True
            and candidate.directly_comparable is True
            and candidate.newer is True
            and _valid_sha256(candidate.sha256)
            and _valid_source_identity(
                candidate.artifact_locator, candidate.source_commit
            )
        ):
            raise ValueError("CURRENT_INCUMBENT_UNRESOLVED")
        if count > current.count:
            current = IncumbentAuthority(
                count=count,
                sha256=candidate.sha256,
                artifact_locator=candidate.artifact_locator,
                source_commit=candidate.source_commit,
            )
    return current


def execution_authority_fields(authority: IncumbentAuthority) -> dict[str, int | str]:
    """Fields to persist in execution authority, outside the frozen manifest."""

    if not isinstance(authority, IncumbentAuthority):
        raise ValueError("CURRENT_INCUMBENT_UNRESOLVED")
    _valid_count(authority.count, field="launch-time incumbent count")
    if not (
        authority.count >= INITIAL_VERIFIED_INCUMBENT_COUNT
        and _valid_sha256(authority.sha256)
        and _valid_source_identity(
            authority.artifact_locator, authority.source_commit
        )
    ):
        raise ValueError("CURRENT_INCUMBENT_UNRESOLVED")
    return {
        "LAUNCH_TIME_CURRENT_VERIFIED_INCUMBENT_COUNT": authority.count,
        "LAUNCH_TIME_CURRENT_VERIFIED_INCUMBENT_SHA256": authority.sha256,
        "LAUNCH_TIME_CURRENT_VERIFIED_INCUMBENT_ARTIFACT_LOCATOR": (
            authority.artifact_locator
        ),
        "LAUNCH_TIME_CURRENT_VERIFIED_INCUMBENT_SOURCE_COMMIT": (
            authority.source_commit
        ),
    }


def classify_candidate(
    count: int, launch_time_incumbent: IncumbentAuthority
) -> dict[str, int | str]:
    """Return local and global deltas for one completed candidate."""

    execution_authority_fields(launch_time_incumbent)
    count = _valid_count(count, field="candidate count")
    incumbent_count = _valid_count(
        launch_time_incumbent.count, field="launch-time incumbent count"
    )
    return {
        "DELTA_FROM_FROZEN_START": count - FROZEN_START_COUNT,
        "DELTA_FROM_CURRENT_VERIFIED_INCUMBENT": count - incumbent_count,
        "LOCAL_GAIN_VS_FROZEN_START": (
            "YES" if count > FROZEN_START_COUNT else "NO"
        ),
        "GLOBAL_STRICT_GAIN": "YES" if count > incumbent_count else "NO",
    }


def terminal_scientific_result(
    *,
    best_canonically_verified_count: int,
    launch_time_incumbent: IncumbentAuthority,
    sets_completed: int,
    sample_count: int,
) -> str | None:
    """Return a terminal result only for a strict gain or a completed campaign."""

    execution_authority_fields(launch_time_incumbent)
    best_count = _valid_count(
        best_canonically_verified_count, field="best verified count"
    )
    sets_completed = _valid_count(sets_completed, field="sets completed")
    sample_count = _valid_count(sample_count, field="sample count")
    if sample_count == 0 or sets_completed > sample_count:
        raise ValueError("invalid campaign completion counts")
    if best_count > launch_time_incumbent.count:
        return "IMPROVED_VS_CURRENT_VERIFIED_INCUMBENT"
    if sets_completed == sample_count:
        return "NO_GLOBAL_IMPROVEMENT_IN_V7_DESTROY5_2048_CAMPAIGN"
    return None
