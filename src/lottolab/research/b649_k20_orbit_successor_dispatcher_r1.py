"""Deterministic dispatch and durable resume for the certified B649 orbit plan.

This module validates the frozen manifest, dispatches its remaining
representatives in original index order, and journals completed group results.
The scoring adapter is injected by a later source-binding layer. It must return
the unique candidate results in the frozen driver's original row order; this
module consumes that order without sorting or importing scientific code.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import os
import re
import stat
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

TASK_ID = "B649_K20_ORBIT_SUCCESSOR_DISPATCHER_R1"
MANIFEST_RELATIVE_PATH = (
    "docs/research/matrix-native-results/b649-k20-four-ticket-certified-orbit-manifest-r1.json"
)

EXPECTED_MANIFEST_SHA256 = "872826017bc1ad59bc9a12d84f1d5eacef31f846a6fc4e890ec19132b2b67025"
EXPECTED_REPRESENTATIVE_TUPLES_SHA256 = (
    "d794d65cca9575a2d47969f43887692f27582a1b142eebbbb2ca77278b52a947"
)
PREDICATE_SHA256 = "97d73e8b9f81969051a03f6b5744d0d7ca0539ff1f70303ce92ddbb760e7134e"
DRIVER_SHA256 = "6348fec9daa839753bf375aa3804a3ca67ed0717fec93c58463d2f01814fd2d7"
EVALUATOR_SHA256 = "92dcb836254cc6dbcd6c2ad907e619a5eb8cf3917197a8f6de3e5f989825cf66"
HISTORICAL_JOURNAL_SHA256 = "818c1c942a99fc5311e712f77e2ef96d3683c39fe55f75d7e8aa1fc3a354eed7"

BASELINE_COUNT = 313_263_888
STRICT_GAIN_MINIMUM_COUNT = 313_263_889
BASELINE_PORTFOLIO_SHA256 = "eaed652900d101881b678a1515d2a366bff9de6723dbec2ec9c82fe0d0d7844c"
TOTAL_QUADRUPLES = 4_845
TOTAL_ORBITS = 670
HISTORICALLY_COVERED_ORBITS = 240
HISTORICALLY_DIRECTLY_SCORED_QUADRUPLES = 623
HISTORICAL_EXECUTED_RAW_ATTEMPTS = 4_844_448
PENDING_REPRESENTATIVES = 430
RAW_ATTEMPTS_PER_REPRESENTATIVE = 7_776
EXPECTED_NEW_RAW_ATTEMPTS = 3_343_680

PROGRESS_SCHEMA = "B649_K20_ORBIT_SUCCESSOR_PROGRESS_R1"
PROGRESS_FILENAME = "progress.jsonl"
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class DispatcherError(ValueError):
    """Raised when manifest authority or durable progress is invalid."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_json_bytes(value: Any) -> bytes:
    try:
        encoded = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
    except (TypeError, ValueError) as error:
        raise DispatcherError("value cannot be serialized as canonical JSON") from error
    return (encoded + "\n").encode("utf-8")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DispatcherError("JSON contains a duplicate object key")
        result[key] = value
    return result


def _json_object(data: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(data.decode("utf-8"), object_pairs_hook=_unique_object)
    except (UnicodeDecodeError, json.JSONDecodeError, DispatcherError) as error:
        raise DispatcherError(f"{label} is not valid unambiguous JSON") from error
    if type(value) is not dict:
        raise DispatcherError(f"{label} must be a JSON object")
    return value


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if type(value) is not dict:
        raise DispatcherError(f"{label} must be an object")
    return value


def _list(value: Any, label: str) -> list[Any]:
    if type(value) is not list:
        raise DispatcherError(f"{label} must be a list")
    return value


def _integer(value: Any, label: str, *, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise DispatcherError(f"{label} must be an integer >= {minimum}")
    return value


def _digest(value: Any, label: str) -> str:
    if type(value) is not str or _SHA256_PATTERN.fullmatch(value) is None:
        raise DispatcherError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _quadruple(value: Any, label: str) -> tuple[int, int, int, int]:
    items = _list(value, label)
    if len(items) != 4 or any(type(slot) is not int or not 0 <= slot < 20 for slot in items):
        raise DispatcherError(f"{label} must contain four ticket indices in [0, 19]")
    if len(set(items)) != 4:
        raise DispatcherError(f"{label} contains a repeated ticket index")
    return tuple(items)  # type: ignore[return-value]


@dataclass(frozen=True, slots=True)
class Representative:
    index: int
    quadruple: tuple[int, int, int, int]


@dataclass(frozen=True, slots=True)
class ManifestPlan:
    manifest_sha256: str
    representative_tuples_sha256: str
    representatives: tuple[Representative, ...]
    total_orbits: int
    historically_covered_orbits: int
    historical_directly_scored_quadruples: int
    historical_executed_raw_attempts: int
    raw_attempts_per_representative: int
    expected_new_raw_attempts: int
    baseline_count: int
    baseline_identity_sha256: str


def _validate_pending_mapping(
    remaining: Iterable[Representative], unvisited_orbits: Iterable[Representative]
) -> None:
    expected = tuple(sorted(unvisited_orbits, key=lambda item: item.index))
    if tuple(remaining) != expected:
        raise DispatcherError("remaining representatives differ from unvisited orbit rows")


def _manifest_plan_from_object(document: dict[str, Any], *, manifest_sha256: str) -> ManifestPlan:
    """Validate parsed manifest content; kept separate for controlled tests."""

    _digest(manifest_sha256, "manifest SHA-256")
    content_digest = _digest(document.get("manifest_content_sha256"), "manifest content SHA-256")
    unsigned = {key: value for key, value in document.items() if key != "manifest_content_sha256"}
    if _sha256(_canonical_json_bytes(unsigned)) != content_digest:
        raise DispatcherError("manifest content SHA-256 differs")
    if document.get("schema") != "B649_FOUR_TICKET_CERTIFIED_ORBIT_MANIFEST_R1":
        raise DispatcherError("manifest schema differs from frozen authority")

    source = _mapping(document.get("source_identity"), "source_identity")
    if source.get("repository") != "kelvinhuang0327/MathStatisticalAnalysis":
        raise DispatcherError("manifest repository identity differs")
    source_hashes = {
        "predicate": PREDICATE_SHA256,
        "driver": DRIVER_SHA256,
        "evaluator": EVALUATOR_SHA256,
        "historical_journal": HISTORICAL_JOURNAL_SHA256,
    }
    for source_name, expected in source_hashes.items():
        source_record = _mapping(source.get(source_name), "source_identity." + source_name)
        if source_record.get("sha256") != expected:
            raise DispatcherError(f"manifest {source_name} identity differs")
    journal_source = _mapping(
        source.get("historical_journal"), "source_identity.historical_journal"
    )
    if (
        journal_source.get("record_count") != HISTORICALLY_DIRECTLY_SCORED_QUADRUPLES
        or journal_source.get("completed_raw_attempts") != HISTORICAL_EXECUTED_RAW_ATTEMPTS
    ):
        raise DispatcherError("manifest historical journal accounting differs")

    baseline = _mapping(document.get("baseline"), "baseline")
    if baseline.get("official_outcome_count") != BASELINE_COUNT:
        raise DispatcherError("manifest baseline count differs")
    if baseline.get("strict_gain_minimum_official_count") != STRICT_GAIN_MINIMUM_COUNT:
        raise DispatcherError("manifest strict-gain boundary differs")
    baseline_identity = _digest(
        baseline.get("normalized_portfolio_sha256"), "baseline portfolio identity"
    )
    if baseline_identity != BASELINE_PORTFOLIO_SHA256:
        raise DispatcherError("manifest baseline portfolio identity differs")

    search_order = _mapping(document.get("search_order"), "search_order")
    combinations = list(itertools.combinations(range(20), 4))
    ordered_digest = _sha256(
        (json.dumps([list(row) for row in combinations], separators=(",", ":")) + "\n").encode(
            "utf-8"
        )
    )
    if (
        search_order.get("kind") != "lexicographic combinations"
        or search_order.get("expression") != "itertools.combinations(range(20), 4)"
        or search_order.get("index_base") != 0
        or search_order.get("quadruple_count") != TOTAL_QUADRUPLES
        or search_order.get("first_quadruple") != list(combinations[0])
        or search_order.get("last_quadruple") != list(combinations[-1])
        or search_order.get("ordered_quadruples_sha256") != ordered_digest
    ):
        raise DispatcherError("manifest original quadruple order differs")

    tie_policy = _mapping(document.get("tie_policy"), "tie_policy")
    expected_tie_policy = {
        "frozen_driver_sha256": DRIVER_SHA256,
        "incumbent_update_condition": "candidate_official_count > current_best_count",
        "equal_count_replaces_incumbent": False,
        "strict_gain_condition": "exact_official_count >= 313263889",
    }
    if tie_policy != expected_tie_policy:
        raise DispatcherError("frozen tie policy differs from authority")

    coverage = _mapping(document.get("coverage"), "coverage")
    expected_coverage = {
        "quadruple_count": TOTAL_QUADRUPLES,
        "orbit_count": TOTAL_ORBITS,
        "historically_covered_orbits": HISTORICALLY_COVERED_ORBITS,
        "unvisited_orbits": PENDING_REPRESENTATIVES,
        "remaining_raw_attempts": EXPECTED_NEW_RAW_ATTEMPTS,
    }
    for key, expected in expected_coverage.items():
        if coverage.get(key) != expected:
            raise DispatcherError(f"manifest coverage field differs: {key}")

    execution = _mapping(document.get("execution"), "execution")
    if (
        execution.get("new_scientific_execution") != "NOT_RUN"
        or execution.get("directly_scored_quadruple_count")
        != HISTORICALLY_DIRECTLY_SCORED_QUADRUPLES
        or execution.get("historically_executed_raw_attempts") != HISTORICAL_EXECUTED_RAW_ATTEMPTS
        or execution.get("mathematical_coverage_does_not_imply_each_member_was_scored") is not True
    ):
        raise DispatcherError("manifest historical execution accounting differs")

    orbit_rows = _list(document.get("orbits"), "orbits")
    if len(orbit_rows) != TOTAL_ORBITS:
        raise DispatcherError("manifest orbit count differs")
    orbit_indices: set[int] = set()
    unvisited: list[Representative] = []
    covered_count = 0
    for position, raw_row in enumerate(orbit_rows):
        row = _mapping(raw_row, f"orbits[{position}]")
        index = _integer(row.get("representative_index"), "representative index")
        if index >= TOTAL_QUADRUPLES:
            raise DispatcherError("orbit representative index is outside the quadruple universe")
        quadruple = _quadruple(row.get("representative"), "orbit representative")
        state = row.get("mathematical_coverage")
        if index in orbit_indices:
            raise DispatcherError("manifest contains a duplicate representative index")
        orbit_indices.add(index)
        direct_indices = _list(
            row.get("directly_scored_member_indices"), "directly_scored_member_indices"
        )
        journal_indices = _list(row.get("journal_record_indices"), "journal_record_indices")
        for member_index in direct_indices:
            _integer(member_index, "directly scored member index")
        for journal_index in journal_indices:
            _integer(journal_index, "journal record index")
        if state == "HISTORICALLY_COVERED_BY_SYMMETRY":
            covered_count += 1
        elif state == "UNVISITED":
            if direct_indices or journal_indices:
                raise DispatcherError("unvisited orbit is incorrectly marked directly scored")
            unvisited.append(Representative(index, quadruple))
        else:
            raise DispatcherError("manifest contains an unknown mathematical coverage state")
    if covered_count != HISTORICALLY_COVERED_ORBITS:
        raise DispatcherError("manifest historical orbit coverage differs")
    if len(unvisited) != PENDING_REPRESENTATIVES:
        raise DispatcherError("manifest pending orbit count differs")

    raw_remaining = _list(document.get("remaining_representatives"), "remaining_representatives")
    remaining: list[Representative] = []
    for position, raw_item in enumerate(raw_remaining):
        item = _mapping(raw_item, f"remaining_representatives[{position}]")
        if set(item) != {"index", "quadruple"}:
            raise DispatcherError("remaining representative item has unexpected fields")
        remaining.append(
            Representative(
                _integer(item.get("index"), "remaining representative index"),
                _quadruple(item.get("quadruple"), "remaining representative quadruple"),
            )
        )
    if len(remaining) != PENDING_REPRESENTATIVES:
        raise DispatcherError("manifest remaining representative count differs")
    indices = [item.index for item in remaining]
    if indices != sorted(indices):
        raise DispatcherError("remaining representatives are not in ascending index order")
    if len(indices) != len(set(indices)):
        raise DispatcherError("manifest contains duplicate pending representative indices")
    if len({item.quadruple for item in remaining}) != len(remaining):
        raise DispatcherError("manifest contains duplicate pending representative tuples")
    _validate_pending_mapping(remaining, unvisited)

    tuple_payload = [list(item.quadruple) for item in remaining]
    representative_digest = _sha256(
        (json.dumps(tuple_payload, separators=(",", ":")) + "\n").encode("utf-8")
    )
    if representative_digest != EXPECTED_REPRESENTATIVE_TUPLES_SHA256:
        raise DispatcherError("remaining representative tuple SHA-256 differs")
    if document.get("remaining_representative_tuple_sha256") != representative_digest:
        raise DispatcherError("manifest representative tuple SHA-256 differs")

    return ManifestPlan(
        manifest_sha256=manifest_sha256,
        representative_tuples_sha256=representative_digest,
        representatives=tuple(remaining),
        total_orbits=TOTAL_ORBITS,
        historically_covered_orbits=HISTORICALLY_COVERED_ORBITS,
        historical_directly_scored_quadruples=HISTORICALLY_DIRECTLY_SCORED_QUADRUPLES,
        historical_executed_raw_attempts=HISTORICAL_EXECUTED_RAW_ATTEMPTS,
        raw_attempts_per_representative=RAW_ATTEMPTS_PER_REPRESENTATIVE,
        expected_new_raw_attempts=EXPECTED_NEW_RAW_ATTEMPTS,
        baseline_count=BASELINE_COUNT,
        baseline_identity_sha256=baseline_identity,
    )


def load_manifest_plan(data: bytes) -> ManifestPlan:
    """Validate exact manifest bytes and return its pending dispatch plan."""

    if type(data) is not bytes:
        raise DispatcherError("manifest input must be bytes")
    actual_manifest_sha256 = _sha256(data)
    if actual_manifest_sha256 != EXPECTED_MANIFEST_SHA256:
        raise DispatcherError("manifest SHA-256 differs from frozen authority")
    if not data.endswith(b"\n"):
        raise DispatcherError("manifest is not newline terminated")
    document = _json_object(data, "orbit manifest")
    if _canonical_json_bytes(document) != data:
        raise DispatcherError("manifest serialization is not canonical")
    return _manifest_plan_from_object(document, manifest_sha256=actual_manifest_sha256)


def is_strict_gain(official_count: int) -> bool:
    """Return true only above the frozen baseline count."""

    count = _integer(official_count, "official outcome count")
    return count > BASELINE_COUNT


@dataclass(frozen=True, slots=True)
class CandidateOutcome:
    official_count: int
    result_identity_sha256: str


@dataclass(frozen=True, slots=True)
class RepresentativeEvaluation:
    raw_attempts: int
    candidate_results: Iterable[CandidateOutcome]


@dataclass(frozen=True, slots=True)
class SelectedCandidate:
    official_count: int
    result_identity_sha256: str
    candidate_ordinal: int
    candidate_count: int


def select_representative_result(
    candidate_results: Iterable[CandidateOutcome],
) -> SelectedCandidate:
    """Select the first highest-count result from the supplied frozen order."""

    selected: SelectedCandidate | None = None
    seen_identities: set[str] = set()
    count = 0
    for ordinal, candidate in enumerate(candidate_results):
        if not isinstance(candidate, CandidateOutcome):
            raise DispatcherError("candidate source returned an invalid result type")
        official_count = _integer(candidate.official_count, "official outcome count")
        identity = _digest(candidate.result_identity_sha256, "candidate result identity")
        if identity in seen_identities:
            raise DispatcherError("candidate source returned a duplicate result identity")
        seen_identities.add(identity)
        count += 1
        if selected is None or official_count > selected.official_count:
            selected = SelectedCandidate(official_count, identity, ordinal, 0)
    if selected is None:
        raise DispatcherError("candidate source returned no scored candidates")
    return SelectedCandidate(
        selected.official_count,
        selected.result_identity_sha256,
        selected.candidate_ordinal,
        count,
    )


@dataclass(frozen=True, slots=True)
class Incumbent:
    official_count: int
    result_identity_sha256: str
    representative_index: int | None
    candidate_ordinal: int | None


def _incumbent_payload(value: Incumbent) -> dict[str, Any]:
    return {
        "official_count": value.official_count,
        "result_identity_sha256": value.result_identity_sha256,
        "representative_index": value.representative_index,
        "candidate_ordinal": value.candidate_ordinal,
    }


def _baseline_incumbent(plan: ManifestPlan) -> Incumbent:
    return Incumbent(
        plan.baseline_count,
        plan.baseline_identity_sha256,
        None,
        None,
    )


def _parse_incumbent(value: Any, label: str) -> Incumbent:
    record = _mapping(value, label)
    if set(record) != {
        "official_count",
        "result_identity_sha256",
        "representative_index",
        "candidate_ordinal",
    }:
        raise DispatcherError(f"{label} has unexpected fields")
    count = _integer(record.get("official_count"), label + ".official_count")
    identity = _digest(record.get("result_identity_sha256"), label + ".identity")
    representative_index = record.get("representative_index")
    candidate_ordinal = record.get("candidate_ordinal")
    if representative_index is None:
        if candidate_ordinal is not None:
            raise DispatcherError("baseline incumbent has a candidate ordinal")
    else:
        _integer(representative_index, label + ".representative_index")
        _integer(candidate_ordinal, label + ".candidate_ordinal")
    return Incumbent(count, identity, representative_index, candidate_ordinal)


class ProgressJournal(Protocol):
    """Append-only journal interface; test and source bindings may inject stores."""

    def read_bytes(self) -> bytes: ...

    def append_line(self, expected_previous: bytes, line: bytes) -> None: ...


class JsonlProgressJournal:
    """File-backed journal rooted in the successor-specific durable directory.

    The directory must be created by the separately authorized run binding.
    This adapter never creates the directory or chooses a runtime output path.
    """

    def __init__(self, successor_directory: Path | str) -> None:
        directory = Path(successor_directory)
        if not directory.is_absolute() or directory.name != TASK_ID:
            raise DispatcherError(
                "journal directory must be the absolute successor-specific task directory"
            )
        if Path(os.path.normpath(str(directory))) != directory:
            raise DispatcherError("journal directory must be normalized")
        self.directory = directory
        self.path = directory / PROGRESS_FILENAME

    def read_bytes(self) -> bytes:
        try:
            directory_before = self.directory.lstat()
        except FileNotFoundError:
            return b""
        if not stat.S_ISDIR(directory_before.st_mode) or self.directory.is_symlink():
            raise DispatcherError("journal directory is not a regular directory")
        if self.directory.resolve(strict=True) != self.directory:
            raise DispatcherError("journal directory resolves through a symlink")
        try:
            before = self.path.lstat()
        except FileNotFoundError:
            return b""
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or self.path.is_symlink():
            raise DispatcherError("progress journal is not a regular non-symlink file")
        try:
            data = self.path.read_bytes()
            after = self.path.lstat()
        except OSError as error:
            raise DispatcherError("cannot read progress journal") from error
        before_identity = (
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
            before.st_ctime_ns,
        )
        after_identity = (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        )
        if before_identity != after_identity or len(data) != after.st_size:
            raise DispatcherError("progress journal changed while being read")
        return data

    def append_line(self, expected_previous: bytes, line: bytes) -> None:
        if type(line) is not bytes or not line.endswith(b"\n") or line.count(b"\n") != 1:
            raise DispatcherError("progress append must contain exactly one JSONL record")
        try:
            directory_stat = self.directory.lstat()
        except OSError as error:
            raise DispatcherError("successor-specific journal directory is unavailable") from error
        if not stat.S_ISDIR(directory_stat.st_mode) or self.directory.is_symlink():
            raise DispatcherError("journal directory is not a regular directory")
        if self.directory.resolve(strict=True) != self.directory:
            raise DispatcherError("journal directory resolves through a symlink")
        if self.read_bytes() != expected_previous:
            raise DispatcherError("progress journal changed before append")
        flags = os.O_WRONLY | os.O_APPEND | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(self.path, flags, 0o600)
        except OSError as error:
            raise DispatcherError("cannot append progress journal") from error
        created = False
        try:
            file_stat = os.fstat(descriptor)
            if not stat.S_ISREG(file_stat.st_mode) or file_stat.st_nlink != 1:
                raise DispatcherError("progress journal is not a regular file")
            created = file_stat.st_size == 0 and expected_previous == b""
            view = memoryview(line)
            while view:
                written = os.write(descriptor, view)
                if written <= 0:
                    raise DispatcherError("progress journal append made no progress")
                view = view[written:]
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        if created:
            try:
                directory_descriptor = os.open(self.directory, os.O_RDONLY)
                try:
                    os.fsync(directory_descriptor)
                finally:
                    os.close(directory_descriptor)
            except OSError as error:
                raise DispatcherError("cannot sync successor journal directory") from error
        if self.read_bytes() != expected_previous + line:
            raise DispatcherError("progress journal read-after-write verification differs")


@dataclass(frozen=True, slots=True)
class ProgressState:
    records: tuple[dict[str, Any], ...]
    incumbent: Incumbent
    last_record_sha256: str | None
    raw_bytes: bytes


def validate_progress_prefix(data: bytes, plan: ManifestPlan) -> ProgressState:
    """Validate a complete, ordered journal prefix and rebuild its incumbent."""

    if type(data) is not bytes:
        raise DispatcherError("progress journal input must be bytes")
    if data and not data.endswith(b"\n"):
        raise DispatcherError("progress journal has a truncated final record")
    records: list[dict[str, Any]] = []
    incumbent = _baseline_incumbent(plan)
    previous_digest: str | None = None
    lines = data.splitlines(keepends=True)
    if any(not line or line == b"\n" for line in lines):
        raise DispatcherError("progress journal contains an empty record")
    for sequence, line in enumerate(lines):
        record = _json_object(line[:-1], "progress record")
        if _canonical_json_bytes(record) != line:
            raise DispatcherError("progress record is not canonical JSON")
        required_keys = {
            "schema",
            "sequence",
            "manifest_sha256",
            "representative_tuples_sha256",
            "representative_index",
            "quadruple",
            "raw_attempts",
            "candidate_count",
            "representative_result",
            "incumbent_before",
            "incumbent_after",
            "previous_record_sha256",
            "record_sha256",
        }
        if set(record) != required_keys:
            raise DispatcherError("progress record has unexpected fields")
        record_digest = _digest(record.get("record_sha256"), "progress record SHA-256")
        unsigned = {key: value for key, value in record.items() if key != "record_sha256"}
        if _sha256(_canonical_json_bytes(unsigned)) != record_digest:
            raise DispatcherError("progress record SHA-256 differs")
        if record.get("schema") != PROGRESS_SCHEMA:
            raise DispatcherError("progress record schema differs")
        if record.get("manifest_sha256") != plan.manifest_sha256:
            raise DispatcherError("progress record manifest identity differs")
        if record.get("representative_tuples_sha256") != plan.representative_tuples_sha256:
            raise DispatcherError("progress record representative identity differs")
        if sequence >= len(plan.representatives):
            raise DispatcherError("progress journal exceeds the manifest dispatch plan")
        representative = plan.representatives[sequence]
        if (
            record.get("sequence") != sequence
            or type(record.get("sequence")) is not int
            or record.get("representative_index") != representative.index
            or type(record.get("representative_index")) is not int
            or record.get("quadruple") != list(representative.quadruple)
        ):
            raise DispatcherError("progress journal is not an ordered manifest prefix")
        if (
            record.get("raw_attempts") != RAW_ATTEMPTS_PER_REPRESENTATIVE
            or type(record.get("raw_attempts")) is not int
        ):
            raise DispatcherError("progress record raw attempt count differs")
        candidate_count = _integer(record.get("candidate_count"), "candidate_count", minimum=1)
        representative_result = _mapping(
            record.get("representative_result"), "representative_result"
        )
        if set(representative_result) != {
            "official_count",
            "result_identity_sha256",
            "candidate_ordinal",
        }:
            raise DispatcherError("representative result has unexpected fields")
        group_count = _integer(
            representative_result.get("official_count"), "representative result count"
        )
        group_identity = _digest(
            representative_result.get("result_identity_sha256"),
            "representative result identity",
        )
        candidate_ordinal = _integer(
            representative_result.get("candidate_ordinal"), "candidate ordinal"
        )
        if candidate_ordinal >= candidate_count:
            raise DispatcherError("representative result candidate ordinal is out of range")
        if record.get("previous_record_sha256") != previous_digest:
            raise DispatcherError("progress journal hash chain differs")
        before = _parse_incumbent(record.get("incumbent_before"), "incumbent_before")
        if before != incumbent:
            raise DispatcherError("progress journal incumbent prefix differs")
        if group_count > incumbent.official_count:
            expected_after = Incumbent(
                group_count,
                group_identity,
                representative.index,
                candidate_ordinal,
            )
        else:
            expected_after = incumbent
        after = _parse_incumbent(record.get("incumbent_after"), "incumbent_after")
        if after != expected_after:
            raise DispatcherError("progress journal strict tie policy differs")
        records.append(record)
        incumbent = after
        previous_digest = record_digest
    return ProgressState(tuple(records), incumbent, previous_digest, data)


@dataclass(frozen=True, slots=True)
class DispatchSummary:
    total_orbits: int
    mathematically_covered_orbits: int
    historical_directly_scored_quadruples: int
    historical_executed_raw_attempts: int
    pending_representatives_total: int
    completed_representative_indices: tuple[int, ...]
    directly_scored_representative_indices: tuple[int, ...]
    unexecuted_representative_indices: tuple[int, ...]
    new_raw_attempts_completed: int
    expected_new_raw_attempts: int
    incumbent: Incumbent


def _make_summary(plan: ManifestPlan, state: ProgressState) -> DispatchSummary:
    completed = tuple(record["representative_index"] for record in state.records)
    pending = tuple(item.index for item in plan.representatives[len(completed) :])
    return DispatchSummary(
        total_orbits=plan.total_orbits,
        mathematically_covered_orbits=plan.historically_covered_orbits,
        historical_directly_scored_quadruples=plan.historical_directly_scored_quadruples,
        historical_executed_raw_attempts=plan.historical_executed_raw_attempts,
        pending_representatives_total=len(plan.representatives),
        completed_representative_indices=completed,
        directly_scored_representative_indices=completed,
        unexecuted_representative_indices=pending,
        new_raw_attempts_completed=len(completed) * plan.raw_attempts_per_representative,
        expected_new_raw_attempts=plan.expected_new_raw_attempts,
        incumbent=state.incumbent,
    )


def summarize_progress(manifest_bytes: bytes, journal_bytes: bytes) -> DispatchSummary:
    """Return coverage and execution accounting without scoring or writing."""

    plan = load_manifest_plan(manifest_bytes)
    return _make_summary(plan, validate_progress_prefix(journal_bytes, plan))


def run_dispatch(
    manifest_bytes: bytes,
    *,
    journal: ProgressJournal,
    score_representative: Callable[[Representative], RepresentativeEvaluation],
) -> DispatchSummary:
    """Run or resume the manifest prefix using an injected ordered score source.

    A representative is appended only after all 7,776 raw attempts have
    completed and at least one unique candidate result was supplied. If scoring
    is interrupted within a representative, that representative is not
    journaled and will be replayed on resume.
    """

    plan = load_manifest_plan(manifest_bytes)
    state = validate_progress_prefix(journal.read_bytes(), plan)
    records = list(state.records)
    incumbent = state.incumbent
    current_bytes = state.raw_bytes
    previous_digest = state.last_record_sha256
    for representative in plan.representatives[len(records) :]:
        evaluation = score_representative(representative)
        if not isinstance(evaluation, RepresentativeEvaluation):
            raise DispatcherError("scoring adapter returned an invalid representative result")
        if type(evaluation.raw_attempts) is not int or (
            evaluation.raw_attempts != plan.raw_attempts_per_representative
        ):
            raise DispatcherError("representative raw attempt count differs from 7,776")
        selected = select_representative_result(evaluation.candidate_results)
        if selected.official_count > incumbent.official_count:
            next_incumbent = Incumbent(
                selected.official_count,
                selected.result_identity_sha256,
                representative.index,
                selected.candidate_ordinal,
            )
        else:
            next_incumbent = incumbent
        body: dict[str, Any] = {
            "schema": PROGRESS_SCHEMA,
            "sequence": len(records),
            "manifest_sha256": plan.manifest_sha256,
            "representative_tuples_sha256": plan.representative_tuples_sha256,
            "representative_index": representative.index,
            "quadruple": list(representative.quadruple),
            "raw_attempts": evaluation.raw_attempts,
            "candidate_count": selected.candidate_count,
            "representative_result": {
                "official_count": selected.official_count,
                "result_identity_sha256": selected.result_identity_sha256,
                "candidate_ordinal": selected.candidate_ordinal,
            },
            "incumbent_before": _incumbent_payload(incumbent),
            "incumbent_after": _incumbent_payload(next_incumbent),
            "previous_record_sha256": previous_digest,
        }
        record = dict(body)
        record["record_sha256"] = _sha256(_canonical_json_bytes(body))
        line = _canonical_json_bytes(record)
        journal.append_line(current_bytes, line)
        current_bytes += line
        records.append(record)
        incumbent = next_incumbent
        previous_digest = record["record_sha256"]
    final_state = ProgressState(tuple(records), incumbent, previous_digest, current_bytes)
    return _make_summary(plan, final_state)
