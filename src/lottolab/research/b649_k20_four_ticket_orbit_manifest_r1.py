"""Generate and verify the frozen B649 four-ticket orbit execution manifest.

This module performs only structural orbit reduction. It never imports the
scientific predicate as executable code and never scores a candidate. The
manifest is built from the byte-verified predicate, driver, evaluator,
historical journal, and immutable baseline result.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import os
import stat
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Sequence


TASK_ID = "B649_K20_313263888_FOUR_TICKET_CYCLE_FULL_FAMILY_R1"
SOURCE_COMMIT = "046c67d1f28559da21b41962a53d680d90b5a674"
SOURCE_TREE = "780f89e5063792b2b0df0ae120904ee7bea1b7a9"
PREDICATE_SHA256 = "97d73e8b9f81969051a03f6b5744d0d7ca0539ff1f70303ce92ddbb760e7134e"
DRIVER_SHA256 = "6348fec9daa839753bf375aa3804a3ca67ed0717fec93c58463d2f01814fd2d7"
EVALUATOR_SHA256 = "92dcb836254cc6dbcd6c2ad907e619a5eb8cf3917197a8f6de3e5f989825cf66"
JOURNAL_SHA256 = "818c1c942a99fc5311e712f77e2ef96d3683c39fe55f75d7e8aa1fc3a354eed7"
UNIVERSE_SHA256 = "1bdd82d6dde10780b720aab6980411981c80cf7b1c3d3de52a7eb6d374eb96ab"

BASELINE_COUNT = 313_263_888
STRICT_GAIN_MINIMUM_COUNT = 313_263_889
BASELINE_PORTFOLIO_SHA256 = "eaed652900d101881b678a1515d2a366bff9de6723dbec2ec9c82fe0d0d7844c"
BASELINE_EXACT_FRACTION = "1864666/3579191"
BASELINE_RESULT_COMMIT = "032ce592c3efd0ac4b5b82a813d157224419c794"
BASELINE_RESULT_BLOB = "404e35563564a40bdd228dafa25fdf5b82e45812"
BASELINE_RESULT_PATH = (
    "docs/research/matrix-native-results/"
    "b649-k20-12-8-winner-two-ticket-ascent-r1-result.json"
)
BASELINE_RESULT_SHA256 = "3d5d3f8f2389b66a9b2c45b0e345b81a0d9dc59d08ca9223519be70a055e5a00"
BASELINE_RESULT_TASK_ID = "B649_K20_12_8_WINNER_TWO_TICKET_ASCENT_R1"

POOL_SIZE = 49
TICKET_COUNT = 20
TICKET_SIZE = 6
QUADRUPLE_SIZE = 4
EXPECTED_AUTOMORPHISM_COUNT = 288
EXPECTED_ORBIT_COUNT = 670
EXPECTED_COVERED_ORBITS = 240
EXPECTED_REMAINING_ORBITS = 430
ATTEMPTS_PER_QUADRUPLE = 7_776
EXPECTED_REMAINING_RAW_ATTEMPTS = 3_343_680
EXPECTED_REMAINING_TUPLE_SHA256 = (
    "d794d65cca9575a2d47969f43887692f27582a1b142eebbbb2ca77278b52a947"
)
EXPECTED_UNCOVERED_MIXED_SIDE_ORBITS = 308
HISTORICAL_JOURNAL_RECORD_COUNT = 623

BASE_REPOSITORY = Path("/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis")
BASE_RUN_ROOT = (
    BASE_REPOSITORY / ".task-data" / TASK_ID / "run1"
)
DEFAULT_MANIFEST_RELATIVE_PATH = Path(
    "docs/research/matrix-native-results/"
    "b649-k20-four-ticket-certified-orbit-manifest-r1.json"
)


class ManifestError(ValueError):
    """Raised when an authority, identity, partition, or manifest check fails."""


@dataclass(frozen=True, order=True)
class Automorphism:
    """A full baseline automorphism.

    ``slots[i]`` is the image of normalized ticket slot ``i``. ``numbers[n-1]``
    is the image of number ``n``. Applying the number permutation to ticket
    ``i`` must produce ticket ``slots[i]``.
    """

    slots: tuple[int, ...]
    numbers: tuple[int, ...]


@dataclass(frozen=True)
class SourcePaths:
    repository: Path
    predicate: Path
    driver: Path
    evaluator: Path
    journal: Path
    baseline_artifact: Optional[Path] = None


@dataclass(frozen=True)
class AuthorityInputs:
    paths: SourcePaths
    predicate: bytes
    driver: bytes
    evaluator: bytes
    journal: bytes
    baseline_artifact: bytes


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode(
        "utf-8"
    )


def _compact_json_bytes(value: Any) -> bytes:
    return json.dumps(value, separators=(",", ":")).encode("utf-8")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ManifestError("JSON contains a duplicate object key")
        result[key] = value
    return result


def _json_object(data: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(data, object_pairs_hook=_unique_object)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ManifestError("%s is not valid JSON" % label) from error
    if not isinstance(value, dict):
        raise ManifestError("%s must be a JSON object" % label)
    return value


def _read_stable(path: Path, label: str) -> bytes:
    if not path.is_absolute():
        raise ManifestError("%s path must be absolute" % label)
    try:
        before = path.lstat()
        if not stat.S_ISREG(before.st_mode) or path.is_symlink():
            raise ManifestError("%s must be a regular non-symlink file" % label)
        if path.resolve(strict=True) != path:
            raise ManifestError("%s resolves through a symlink" % label)
        with path.open("rb") as stream:
            data = stream.read()
        after = path.lstat()
    except OSError as error:
        raise ManifestError("cannot read %s: %s" % (label, path)) from error
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
        raise ManifestError("%s changed while being read" % label)
    return data


def _git(repository: Path, *arguments: str) -> bytes:
    try:
        result = subprocess.run(
            ["git", "-C", str(repository), *arguments],
            check=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise ManifestError("cannot resolve frozen Git authority") from error
    return result.stdout


def default_source_paths(repository: Optional[Path] = None) -> SourcePaths:
    repo = (repository or Path(__file__).resolve().parents[3]).resolve(strict=True)
    return SourcePaths(
        repository=repo,
        predicate=BASE_RUN_ROOT / "predicate-source.snapshot.py",
        driver=BASE_RUN_ROOT / "driver.py",
        evaluator=repo / "src/lottolab/research/b649_official_any_prize_exact.py",
        journal=BASE_RUN_ROOT / "attempt-results.jsonl",
    )


def _read_baseline_blob(paths: SourcePaths) -> bytes:
    commit_blob = _git(
        paths.repository,
        "rev-parse",
        "%s:%s" % (BASELINE_RESULT_COMMIT, BASELINE_RESULT_PATH),
    ).decode("ascii").strip()
    if commit_blob != BASELINE_RESULT_BLOB:
        raise ManifestError("baseline Git blob identity differs")
    try:
        data = _git(paths.repository, "cat-file", "blob", BASELINE_RESULT_BLOB)
    except ManifestError as error:
        raise ManifestError("baseline result blob is unavailable") from error
    if _sha256(data) != BASELINE_RESULT_SHA256:
        raise ManifestError("baseline result file SHA-256 differs")
    return data


def _verify_git_authority(repository: Path) -> None:
    top = Path(_git(repository, "rev-parse", "--show-toplevel").decode("utf-8").strip())
    if top.resolve(strict=True) != repository.resolve(strict=True):
        raise ManifestError("repository root does not match the manifest worktree")
    tree = _git(repository, "rev-parse", "%s^{tree}" % SOURCE_COMMIT).decode("ascii").strip()
    if tree != SOURCE_TREE:
        raise ManifestError("frozen source commit tree differs")


def _verify_input_hashes(inputs: AuthorityInputs) -> None:
    expected = (
        ("predicate", inputs.predicate, PREDICATE_SHA256),
        ("driver", inputs.driver, DRIVER_SHA256),
        ("evaluator", inputs.evaluator, EVALUATOR_SHA256),
        ("journal", inputs.journal, JOURNAL_SHA256),
        ("baseline result", inputs.baseline_artifact, BASELINE_RESULT_SHA256),
    )
    for label, data, digest in expected:
        actual = _sha256(data)
        if actual != digest:
            raise ManifestError("%s SHA-256 differs from frozen authority" % label)


def load_authority_inputs(paths: Optional[SourcePaths] = None) -> AuthorityInputs:
    selected = paths or default_source_paths()
    _verify_git_authority(selected.repository)
    baseline = (
        _read_stable(selected.baseline_artifact, "baseline result")
        if selected.baseline_artifact is not None
        else _read_baseline_blob(selected)
    )
    inputs = AuthorityInputs(
        paths=selected,
        predicate=_read_stable(selected.predicate, "predicate snapshot"),
        driver=_read_stable(selected.driver, "scientific driver"),
        evaluator=_read_stable(selected.evaluator, "official evaluator"),
        journal=_read_stable(selected.journal, "historical journal"),
        baseline_artifact=baseline,
    )
    _verify_input_hashes(inputs)
    return inputs


def _baseline_tickets(data: bytes) -> tuple[tuple[int, ...], ...]:
    payload = _json_object(data, "baseline result")
    required = {
        "TASK_ID": BASELINE_RESULT_TASK_ID,
        "TASK_STATUS": "COMPLETE",
        "START_COUNT": BASELINE_COUNT,
        "FINAL_COUNT": BASELINE_COUNT,
        "START_NORMALIZED_ENGINE_SHA256": BASELINE_PORTFOLIO_SHA256,
        "FINAL_SHA256": BASELINE_PORTFOLIO_SHA256,
        "FINAL_ENGINE_NORMALIZED_SHA256": BASELINE_PORTFOLIO_SHA256,
        "FINAL_EXACT_FRACTION": BASELINE_EXACT_FRACTION,
    }
    for key, expected in required.items():
        if payload.get(key) != expected:
            raise ManifestError("baseline result field differs: %s" % key)
    rows = payload.get("FINAL_TICKETS")
    if not isinstance(rows, list) or len(rows) != TICKET_COUNT:
        raise ManifestError("baseline FINAL_TICKETS has the wrong shape")
    tickets: list[tuple[int, ...]] = []
    for row in rows:
        if (
            not isinstance(row, list)
            or len(row) != TICKET_SIZE
            or any(type(number) is not int or not 1 <= number <= POOL_SIZE for number in row)
            or len(set(row)) != TICKET_SIZE
        ):
            raise ManifestError("baseline ticket is invalid")
        tickets.append(tuple(sorted(row)))
    normalized = tuple(sorted(tickets))
    if len(set(normalized)) != TICKET_COUNT:
        raise ManifestError("baseline contains duplicate tickets")
    if payload.get("SEARCH_START_TICKETS") != [list(ticket) for ticket in normalized]:
        raise ManifestError("baseline search ticket order is not canonical")
    if _sha256(_compact_json_bytes([list(ticket) for ticket in normalized])) != (
        BASELINE_PORTFOLIO_SHA256
    ):
        raise ManifestError("normalized baseline portfolio SHA-256 differs")
    return normalized


def _number_incidence(tickets: Sequence[Sequence[int]]) -> dict[int, frozenset[int]]:
    incidence: dict[int, set[int]] = {number: set() for number in range(1, POOL_SIZE + 1)}
    for slot, ticket in enumerate(tickets):
        for number in ticket:
            incidence[number].add(slot)
    return {number: frozenset(slots) for number, slots in incidence.items()}


def _apply_numbers(numbers: Sequence[int], ticket: Sequence[int]) -> tuple[int, ...]:
    return tuple(sorted(numbers[number - 1] for number in ticket))


def _is_automorphism(
    tickets: Sequence[Sequence[int]], element: Automorphism
) -> bool:
    if sorted(element.slots) != list(range(TICKET_COUNT)):
        return False
    if sorted(element.numbers) != list(range(1, POOL_SIZE + 1)):
        return False
    return all(
        _apply_numbers(element.numbers, tickets[slot]) == tickets[element.slots[slot]]
        for slot in range(TICKET_COUNT)
    )


def _compose(first: Automorphism, second: Automorphism) -> Automorphism:
    return Automorphism(
        tuple(second.slots[slot] for slot in first.slots),
        tuple(second.numbers[number - 1] for number in first.numbers),
    )


def automorphism_group(
    portfolio: Sequence[Sequence[int]],
) -> tuple[Automorphism, ...]:
    """Enumerate the full ticket and number relabeling group deterministically.

    Pairwise ticket overlaps are at most one in the frozen baseline. This lets
    the search prune each partial ticket permutation by the unique shared-number
    mapping it induces. At completion the full 49-number incidence action is
    reconstructed and checked directly.
    """

    tickets = tuple(tuple(sorted(ticket)) for ticket in portfolio)
    if len(tickets) != TICKET_COUNT or len(set(tickets)) != TICKET_COUNT:
        raise ManifestError("baseline must contain 20 distinct tickets")
    if any(
        len(ticket) != TICKET_SIZE
        or len(set(ticket)) != TICKET_SIZE
        or any(type(number) is not int or not 1 <= number <= POOL_SIZE for number in ticket)
        for ticket in tickets
    ):
        raise ManifestError("baseline ticket shape is invalid")

    incidence = _number_incidence(tickets)
    if any(not slots for slots in incidence.values()):
        raise ManifestError("baseline does not use all 49 numbers")
    owner = {slots: number for number, slots in incidence.items()}
    if len(owner) != POOL_SIZE:
        raise ManifestError("baseline number-incidence profiles are not unique")

    ticket_sets = [frozenset(ticket) for ticket in tickets]
    common: dict[tuple[int, int], int] = {}
    for first, second in itertools.combinations(range(TICKET_COUNT), 2):
        shared = ticket_sets[first] & ticket_sets[second]
        if len(shared) > 1:
            raise ManifestError("baseline tickets share more than one number")
        if shared:
            (number,) = shared
            common[(first, second)] = number
            common[(second, first)] = number
    invariants = [
        tuple(sorted(len(incidence[number]) for number in ticket)) for ticket in tickets
    ]

    found: list[Automorphism] = []
    image = [-1] * TICKET_COUNT
    used = [False] * TICKET_COUNT
    number_image: dict[int, int] = {}
    number_preimage: dict[int, int] = {}

    def extend(slot: int) -> None:
        if slot == TICKET_COUNT:
            number_map: list[int] = []
            for number in range(1, POOL_SIZE + 1):
                target = frozenset(image[index] for index in incidence[number])
                if target not in owner:
                    return
                number_map.append(owner[target])
            element = Automorphism(tuple(image), tuple(number_map))
            if _is_automorphism(tickets, element):
                found.append(element)
            return

        for target_slot in range(TICKET_COUNT):
            if used[target_slot] or invariants[target_slot] != invariants[slot]:
                continue
            added: list[int] = []
            consistent = True
            for previous in range(slot):
                source_number = common.get((slot, previous))
                target_number = common.get((target_slot, image[previous]))
                if (source_number is None) != (target_number is None):
                    consistent = False
                    break
                if source_number is None or target_number is None:
                    continue
                if source_number in number_image or target_number in number_preimage:
                    if (
                        number_image.get(source_number) != target_number
                        or number_preimage.get(target_number) != source_number
                    ):
                        consistent = False
                        break
                    continue
                number_image[source_number] = target_number
                number_preimage[target_number] = source_number
                added.append(source_number)
            if consistent:
                image[slot] = target_slot
                used[target_slot] = True
                extend(slot + 1)
                used[target_slot] = False
                image[slot] = -1
            for source_number in added:
                del number_preimage[number_image.pop(source_number)]

    extend(0)
    group = tuple(sorted(found))
    members = set(group)
    identity = Automorphism(tuple(range(TICKET_COUNT)), tuple(range(1, POOL_SIZE + 1)))
    if identity not in members:
        raise ManifestError("automorphism group lacks identity")
    for first in group:
        for second in group:
            if _compose(first, second) not in members:
                raise ManifestError("automorphism set is not closed under composition")
    if len(group) != EXPECTED_AUTOMORPHISM_COUNT:
        raise ManifestError("automorphism group order differs from 288")
    return group


def _ticket_side(ticket: Sequence[int]) -> str:
    if max(ticket) <= 26:
        return "H"
    if min(ticket) >= 27:
        return "U"
    raise ManifestError("baseline ticket mixes the frozen H/U number supports")


def _parse_journal(
    data: bytes,
    combinations: Sequence[tuple[int, ...]],
) -> tuple[dict[tuple[int, ...], list[int]], int]:
    if not data.endswith(b"\n"):
        raise ManifestError("historical journal has an incomplete final line")
    lines = data.splitlines(keepends=True)
    if len(lines) != HISTORICAL_JOURNAL_RECORD_COUNT:
        raise ManifestError("historical journal record count differs")
    directly_scored: dict[tuple[int, ...], list[int]] = {}
    for record_index, line in enumerate(lines):
        if not line.endswith(b"\n") or line.endswith(b"\r\n"):
            raise ManifestError("historical journal line ending is not canonical LF")
        record = _json_object(line[:-1], "historical journal record")
        expected_quadruple = combinations[record_index]
        expected_fields = {
            "RECORD_TYPE": "QUADRUPLE_COMPLETE",
            "TASK_ID": TASK_ID,
            "QUADRUPLE_INDEX": record_index,
            "QUADRUPLE": list(expected_quadruple),
            "PREVIOUS_COMPLETED_RAW_ATTEMPTS": record_index * ATTEMPTS_PER_QUADRUPLE,
            "COMPLETED_RAW_ATTEMPTS": (record_index + 1) * ATTEMPTS_PER_QUADRUPLE,
            "RAW": ATTEMPTS_PER_QUADRUPLE,
            "SOURCE_SHA256": PREDICATE_SHA256,
            "BASELINE_SHA256": BASELINE_PORTFOLIO_SHA256,
            "UNIVERSE_SHA256": UNIVERSE_SHA256,
            "REBIND_COUNT": BASELINE_COUNT,
        }
        for key, expected in expected_fields.items():
            if record.get(key) != expected:
                raise ManifestError(
                    "historical journal record %d differs at %s" % (record_index, key)
                )
        directly_scored.setdefault(expected_quadruple, []).append(record_index)
    return directly_scored, len(lines) * ATTEMPTS_PER_QUADRUPLE


def _orbit_partition(
    combinations: Sequence[tuple[int, ...]],
    group: Sequence[Automorphism],
) -> tuple[list[dict[str, Any]], dict[tuple[int, ...], tuple[int, ...]]]:
    index_of = {quadruple: index for index, quadruple in enumerate(combinations)}
    if len(index_of) != len(combinations):
        raise ManifestError("lexicographic search order contains duplicates")
    unseen = set(combinations)
    orbits: list[dict[str, Any]] = []
    representative_for: dict[tuple[int, ...], tuple[int, ...]] = {}
    while unseen:
        seed = min(unseen)
        members = {
            tuple(sorted(element.slots[slot] for slot in seed)) for element in group
        }
        if not members or not members.issubset(unseen):
            raise ManifestError("automorphism action does not form a disjoint orbit partition")
        representative = min(members)
        if representative != seed:
            raise ManifestError("orbit representative is not the exact lexicographic minimum")
        for member in members:
            representative_for[member] = representative
        unseen.difference_update(members)
        orbits.append(
            {
                "representative_index": index_of[representative],
                "representative": list(representative),
                "member_indices": sorted(index_of[member] for member in members),
                "members": [list(member) for member in sorted(members)],
            }
        )
    if len(representative_for) != len(combinations):
        raise ManifestError("orbit partition does not cover all quadruples")
    return orbits, representative_for


def _side_class(
    quadruple: Sequence[int], tickets: Sequence[Sequence[int]]
) -> tuple[str, ...]:
    return tuple(sorted({_ticket_side(tickets[slot]) for slot in quadruple}))


def _representative_tuple_digest(representatives: Sequence[Sequence[int]]) -> str:
    payload = (json.dumps(representatives, separators=(",", ":")) + "\n").encode("utf-8")
    return _sha256(payload)


def build_manifest(inputs: AuthorityInputs) -> dict[str, Any]:
    """Reconstruct and validate every source identity, automorphism and orbit."""

    _verify_input_hashes(inputs)
    tickets = _baseline_tickets(inputs.baseline_artifact)
    group = automorphism_group(tickets)
    search_order = list(itertools.combinations(range(TICKET_COUNT), QUADRUPLE_SIZE))
    if len(search_order) != 4_845:
        raise ManifestError("lexicographic quadruple universe differs from 4,845")
    search_index = {quadruple: index for index, quadruple in enumerate(search_order)}
    directly_scored, historical_attempts = _parse_journal(inputs.journal, search_order)
    orbits, representative_for = _orbit_partition(search_order, group)
    for orbit in orbits:
        member_sides = {_side_class(member, tickets) for member in orbit["members"]}
        if len(member_sides) != 1:
            raise ManifestError("an automorphism orbit mixes distinct baseline sides")
        orbit["mixed_side"] = len(next(iter(member_sides))) == 2
        executed = [
            member
            for member in orbit["members"]
            if tuple(member) in directly_scored
        ]
        orbit["directly_scored_member_indices"] = sorted(
            search_index[tuple(member)] for member in executed
        )
        orbit["journal_record_indices"] = sorted(
            record_index
            for member in executed
            for record_index in directly_scored[tuple(member)]
        )
        orbit["mathematical_coverage"] = (
            "HISTORICALLY_COVERED_BY_SYMMETRY" if executed else "UNVISITED"
        )

    covered_representatives = {
        orbit["representative_index"]
        for orbit in orbits
        if orbit["mathematical_coverage"] == "HISTORICALLY_COVERED_BY_SYMMETRY"
    }
    all_representatives = sorted(
        (orbit["representative_index"], tuple(orbit["representative"])) for orbit in orbits
    )
    remaining = [
        {"index": index, "quadruple": list(representative)}
        for index, representative in all_representatives
        if index not in covered_representatives
    ]
    remaining_tuples = [item["quadruple"] for item in remaining]
    remaining_digest = _representative_tuple_digest(remaining_tuples)
    covered_count = len(covered_representatives)
    remaining_count = len(remaining)
    remaining_raw_attempts = remaining_count * ATTEMPTS_PER_QUADRUPLE
    mixed_uncovered = sum(
        1
        for item in remaining
        if len(_side_class(item["quadruple"], tickets)) == 2
    )

    if len(group) != EXPECTED_AUTOMORPHISM_COUNT:
        raise ManifestError("automorphism group acceptance failed")
    if len(orbits) != EXPECTED_ORBIT_COUNT or len(representative_for) != 4_845:
        raise ManifestError("full 4,845-quadruple orbit partition acceptance failed")
    if covered_count != EXPECTED_COVERED_ORBITS:
        raise ManifestError("historical journal does not cover exactly 240 orbits")
    if remaining_count != EXPECTED_REMAINING_ORBITS:
        raise ManifestError("remaining representative count differs from 430")
    if remaining_raw_attempts != EXPECTED_REMAINING_RAW_ATTEMPTS:
        raise ManifestError("remaining raw attempt count differs")
    if remaining_digest != EXPECTED_REMAINING_TUPLE_SHA256:
        raise ManifestError("remaining representative tuple-list SHA-256 differs")
    if mixed_uncovered != EXPECTED_UNCOVERED_MIXED_SIDE_ORBITS:
        raise ManifestError("uncovered mixed-side orbit count differs")

    ordered_quads_sha = _sha256(
        (json.dumps([list(q) for q in search_order], separators=(",", ":")) + "\n").encode(
            "utf-8"
        )
    )
    manifest: dict[str, Any] = {
        "schema": "B649_FOUR_TICKET_CERTIFIED_ORBIT_MANIFEST_R1",
        "source_identity": {
            "repository": "kelvinhuang0327/MathStatisticalAnalysis",
            "source_commit": SOURCE_COMMIT,
            "source_tree": SOURCE_TREE,
            "predicate": {
                "path": str(inputs.paths.predicate),
                "sha256": PREDICATE_SHA256,
            },
            "driver": {"path": str(inputs.paths.driver), "sha256": DRIVER_SHA256},
            "evaluator": {
                "path": str(inputs.paths.evaluator),
                "sha256": EVALUATOR_SHA256,
            },
            "historical_journal": {
                "path": str(inputs.paths.journal),
                "sha256": JOURNAL_SHA256,
                "record_count": HISTORICAL_JOURNAL_RECORD_COUNT,
                "completed_raw_attempts": historical_attempts,
            },
        },
        "baseline": {
            "official_outcome_count": BASELINE_COUNT,
            "strict_gain_minimum_official_count": STRICT_GAIN_MINIMUM_COUNT,
            "normalized_portfolio_sha256": BASELINE_PORTFOLIO_SHA256,
            "result_task_id": BASELINE_RESULT_TASK_ID,
            "result_commit": BASELINE_RESULT_COMMIT,
            "result_blob": BASELINE_RESULT_BLOB,
            "result_path": BASELINE_RESULT_PATH,
            "result_file_sha256": BASELINE_RESULT_SHA256,
            "normalized_tickets": [list(ticket) for ticket in tickets],
        },
        "search_order": {
            "kind": "lexicographic combinations",
            "expression": "itertools.combinations(range(20), 4)",
            "index_base": 0,
            "quadruple_count": len(search_order),
            "first_quadruple": list(search_order[0]),
            "last_quadruple": list(search_order[-1]),
            "ordered_quadruples_sha256": ordered_quads_sha,
        },
        "tie_policy": {
            "frozen_driver_sha256": DRIVER_SHA256,
            "incumbent_update_condition": "candidate_official_count > current_best_count",
            "equal_count_replaces_incumbent": False,
            "strict_gain_condition": "exact_official_count >= 313263889",
        },
        "group_action": {
            "automorphism_count": len(group),
            "ticket_permutation_convention": "slots[i] is the image of normalized ticket index i",
            "number_permutation_convention": "numbers[n-1] is the image of number n",
            "automorphisms": [
                {"slots": list(element.slots), "numbers": list(element.numbers)}
                for element in group
            ],
        },
        "coverage": {
            "quadruple_count": len(search_order),
            "orbit_count": len(orbits),
            "historically_covered_orbits": covered_count,
            "unvisited_orbits": remaining_count,
            "remaining_raw_attempts": remaining_raw_attempts,
            "uncovered_mixed_side_orbits": mixed_uncovered,
        },
        "execution": {
            "new_scientific_execution": "NOT_RUN",
            "directly_scored_quadruple_count": len(directly_scored),
            "historically_executed_raw_attempts": historical_attempts,
            "mathematical_coverage_does_not_imply_each_member_was_scored": True,
        },
        "orbits": orbits,
        "remaining_representatives": remaining,
        "remaining_representative_tuple_sha256": remaining_digest,
        "manifest_sha256_scope": (
            "SHA256 of compact sorted-key JSON with manifest_content_sha256 omitted, followed by LF"
        ),
    }
    manifest["manifest_content_sha256"] = _sha256(_canonical_json_bytes(manifest))
    return manifest


def verify_manifest_object(manifest: dict[str, Any], inputs: AuthorityInputs) -> str:
    """Verify self-hash and independently reconstruct the exact manifest."""

    content_digest = manifest.get("manifest_content_sha256")
    if not isinstance(content_digest, str):
        raise ManifestError("manifest content SHA-256 is missing")
    without_digest = {key: value for key, value in manifest.items() if key != "manifest_content_sha256"}
    if _sha256(_canonical_json_bytes(without_digest)) != content_digest:
        raise ManifestError("manifest content SHA-256 differs")
    expected = build_manifest(inputs)
    if manifest != expected:
        raise ManifestError("manifest differs from deterministic authority reconstruction")
    return _sha256(_canonical_json_bytes(manifest))


def verify_manifest_file(path: Path, inputs: AuthorityInputs) -> str:
    data = _read_stable(path, "orbit manifest")
    manifest = _json_object(data, "orbit manifest")
    if not data.endswith(b"\n") or _canonical_json_bytes(manifest) != data:
        raise ManifestError("manifest serialization is not canonical compact JSON plus LF")
    return verify_manifest_object(manifest, inputs)


def write_manifest(path: Path, inputs: AuthorityInputs) -> str:
    """Write one deterministic manifest without replacing any existing path."""

    if not path.is_absolute():
        raise ManifestError("manifest output path must be absolute")
    if path.exists() or path.is_symlink():
        raise ManifestError("manifest output already exists")
    payload = _canonical_json_bytes(build_manifest(inputs))
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    except OSError as error:
        raise ManifestError("cannot create manifest output: %s" % path) from error
    try:
        view = memoryview(payload)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise ManifestError("manifest write made no progress")
            view = view[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    return _sha256(payload)


def _cli_paths(args: argparse.Namespace, repository: Path) -> SourcePaths:
    defaults = default_source_paths(repository)
    return SourcePaths(
        repository=repository,
        predicate=args.predicate or defaults.predicate,
        driver=args.driver or defaults.driver,
        evaluator=args.evaluator or defaults.evaluator,
        journal=args.journal or defaults.journal,
        baseline_artifact=args.baseline_artifact,
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("generate", "verify"):
        child = subparsers.add_parser(command)
        child.add_argument("--repository", type=Path, default=Path(__file__).resolve().parents[3])
        child.add_argument("--predicate", type=Path)
        child.add_argument("--driver", type=Path)
        child.add_argument("--evaluator", type=Path)
        child.add_argument("--journal", type=Path)
        child.add_argument("--baseline-artifact", type=Path)
        default_output = Path(__file__).resolve().parents[3] / DEFAULT_MANIFEST_RELATIVE_PATH
        if command == "generate":
            child.add_argument("--output", type=Path, default=default_output)
        else:
            child.add_argument("--manifest", type=Path, default=default_output)
    args = parser.parse_args(argv)
    repository = args.repository.resolve(strict=True)
    paths = _cli_paths(args, repository)
    try:
        inputs = load_authority_inputs(paths)
        if args.command == "generate":
            digest = write_manifest(args.output, inputs)
            print("MANIFEST_PATH=%s" % args.output)
            print("MANIFEST_SHA256=%s" % digest)
        else:
            digest = verify_manifest_file(args.manifest, inputs)
            print("MANIFEST_PATH=%s" % args.manifest)
            print("MANIFEST_SHA256=%s" % digest)
        print("AUTOMORPHISMS=%d" % EXPECTED_AUTOMORPHISM_COUNT)
        print("ORBITS=%d" % EXPECTED_ORBIT_COUNT)
        print("COVERED_ORBITS=%d" % EXPECTED_COVERED_ORBITS)
        print("REMAINING_REPRESENTATIVES=%d" % EXPECTED_REMAINING_ORBITS)
        return 0
    except ManifestError as error:
        print("ERROR: %s" % error, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
