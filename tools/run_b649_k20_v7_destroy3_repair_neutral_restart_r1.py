#!/usr/bin/env python3
"""Freeze destroy3 best-count ties, then exhaust 16 complete cycle families."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import itertools
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from lottolab.research import b649_k20_three_ticket_single_number_cycle_r1 as cycle


TASK_ID = "B649_K20_V7_DESTROY3_REPAIR_NEUTRAL_RESTART_R1"
BASE_HEAD = "594c36b573c53b77583be555e9ba9787da0d111c"
BRANCH = "codex/b649-k20-v7-destroy3-repair-neutral-restart-r1"
SOURCE_COMMIT = "c5c2c704f20ae1be3588355ed0ca9e6ece1a2ba2"
SOURCE_PATH = (
    "docs/research/matrix-native-results/"
    "b649-k20-v7-destroy3-global-pool-exhaustive-r1-result.json"
)
ROOT_COUNT = 313239661
ROOT_SHA256 = "0045ac8837fc82e9a585d812173341ac12e05c5de201af7f8fedeacafa19e1ff"
START_COUNT = 16
EXPECTED_TRIPLES = 1140
EXPECTED_RAW_ATTEMPTS = 492480
FAMILY_NAME = "THREE_TICKET_SINGLE_NUMBER_CYCLE"
OUTPUT_DIR = Path("docs/research/matrix-native-results")
STEM = "b649-k20-v7-destroy3-repair-neutral-restart-r1"
STARTS_NAME = f"{STEM}-neutral-starts.json"
STATE_NAME = f"{STEM}-state.json"
JOURNAL_NAME = f"{STEM}-family-results.jsonl"
RESULT_NAME = f"{STEM}-result.json"
THREAD_ENV = {
    "PYTHONDONTWRITEBYTECODE": "1",
    "OMP_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    "OPENBLAS_NUM_THREADS": "1",
    "NUMEXPR_NUM_THREADS": "1",
    "VECLIB_MAXIMUM_THREADS": "1",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def pretty_json(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode(
        "utf-8"
    )


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    with temporary.open("wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)
    directory_fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


class SingleWriter:
    """A nonblocking process lock scoped to this result directory."""

    def __init__(self, output_dir: Path) -> None:
        self.path = output_dir / f".{STEM}.writer.lock"
        self.fd: int | None = None

    def __enter__(self) -> SingleWriter:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.fd = os.open(self.path, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            os.close(self.fd)
            self.fd = None
            raise RuntimeError("another neutral-restart writer holds the run lock") from exc
        os.ftruncate(self.fd, 0)
        os.write(self.fd, f"pid={os.getpid()} task={TASK_ID}\n".encode())
        os.fsync(self.fd)
        return self

    def __exit__(self, *_exc: object) -> None:
        if self.fd is not None:
            fcntl.flock(self.fd, fcntl.LOCK_UN)
            os.close(self.fd)
            self.fd = None


def load_source_result(repo_root: Path) -> tuple[dict[str, Any], bytes]:
    spec = f"{SOURCE_COMMIT}:{SOURCE_PATH}"
    completed = subprocess.run(
        ["git", "show", spec],
        cwd=repo_root,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return json.loads(completed.stdout), completed.stdout


def validate_source_result(source: dict[str, Any]) -> tuple[cycle.Portfolio, dict[str, cycle.Portfolio]]:
    if source.get("TASK_STATUS") != "COMPLETE":
        raise RuntimeError("pinned destroy3 result is not COMPLETE")
    if source.get("DESTROY_TRIPLES_COMPLETED") != EXPECTED_TRIPLES:
        raise RuntimeError("pinned destroy3 result does not contain all 1140 triples")
    if source.get("DESTROY_TRIPLES_EXPECTED") != EXPECTED_TRIPLES:
        raise RuntimeError("pinned destroy3 expected triple count drifted")
    if source.get("BEST_COUNT") != ROOT_COUNT or source.get("START_COUNT") != ROOT_COUNT:
        raise RuntimeError("pinned destroy3 result count differs from the authorized root")
    if source.get("START_SHA256") != ROOT_SHA256 or source.get("BEST_SHA256") != ROOT_SHA256:
        raise RuntimeError("pinned destroy3 result SHA differs from the authorized root")
    if source.get("BEST_CANONICAL_RECOUNT_STATUS") != "PASS":
        raise RuntimeError("pinned destroy3 root canonical recount is not PASS")

    contract = source.get("EXECUTION_CONTRACT")
    if not isinstance(contract, dict):
        raise RuntimeError("pinned destroy3 result has no execution contract")
    root = cycle.normalize_portfolio(contract["START_PORTFOLIO"], pool_size=49, expected_ticket_count=20)
    if cycle.portfolio_sha256(root, pool_size=49) != ROOT_SHA256:
        raise RuntimeError("pinned execution-contract root hash does not match")

    ties = source.get("GLOBAL_BEST_TIES")
    if not isinstance(ties, list) or len(ties) != 5246:
        raise RuntimeError("pinned result does not expose all 5246 best-tie occurrences")
    unique: dict[str, cycle.Portfolio] = {}
    for row in ties:
        if row.get("CANONICAL_COUNT") != ROOT_COUNT:
            raise RuntimeError("a recorded best-tie occurrence has a different count")
        portfolio = cycle.normalize_portfolio(row["PORTFOLIO"], pool_size=49, expected_ticket_count=20)
        digest = cycle.portfolio_sha256(portfolio, pool_size=49)
        if digest != row.get("PORTFOLIO_SHA256"):
            raise RuntimeError("a recorded tie portfolio SHA does not match its normalized tickets")
        previous = unique.setdefault(digest, portfolio)
        if previous != portfolio:
            raise RuntimeError("one tie SHA maps to conflicting portfolios")
    if len(unique) != source.get("BEST_TIE_UNIQUE_PORTFOLIO_COUNT"):
        raise RuntimeError("deduplicated source tie count does not match the result record")
    if len(unique) != 327 or unique.get(ROOT_SHA256) != root:
        raise RuntimeError("deduplicated tie universe does not contain the expected 327 portfolios")
    return root, unique


def ticket_distance(first: cycle.Portfolio, second: cycle.Portfolio) -> int:
    return len(set(first).symmetric_difference(second))


def residual_coverage_signature(portfolio: cycle.Portfolio) -> frozenset[tuple[int, int, int]]:
    """Exact hit-pattern signature: every distinct 3-number pattern in a ticket.

    A 7-number outcome is covered exactly when it contains one of these
    patterns. The complement is the residual 3-pattern signature. Hamming
    distance on C(49,3) patterns is therefore the specified signature metric.
    """

    return frozenset(pattern for ticket in portfolio for pattern in itertools.combinations(ticket, 3))


def signature_distance(
    first: frozenset[tuple[int, int, int]], second: frozenset[tuple[int, int, int]]
) -> int:
    return len(first.symmetric_difference(second))


def build_selection_document(source: dict[str, Any], source_bytes: bytes) -> dict[str, Any]:
    root, unique = validate_source_result(source)
    root_signature = residual_coverage_signature(root)
    signatures = {digest: residual_coverage_signature(p) for digest, p in unique.items()}
    eligible = sorted(digest for digest in unique if digest != ROOT_SHA256)
    selected: list[str] = []
    steps: list[dict[str, Any]] = []

    for step_number in range(1, START_COUNT + 1):
        max_root_distance = max(ticket_distance(unique[digest], root) for digest in eligible)
        tier1 = [
            digest for digest in eligible if ticket_distance(unique[digest], root) == max_root_distance
        ]
        if selected:
            ticket_minima = {
                digest: min(ticket_distance(unique[digest], unique[chosen]) for chosen in selected)
                for digest in tier1
            }
            maximin_ticket = max(ticket_minima.values())
            tier2 = [digest for digest in tier1 if ticket_minima[digest] == maximin_ticket]
        else:
            ticket_minima = {digest: None for digest in tier1}
            maximin_ticket = None
            tier2 = tier1

        anchors = [ROOT_SHA256, *selected]
        signature_minima = {
            digest: min(
                signature_distance(signatures[digest], root_signature if anchor == ROOT_SHA256 else signatures[anchor])
                for anchor in anchors
            )
            for digest in tier2
        }
        maximin_signature = max(signature_minima.values())
        tier3 = [digest for digest in tier2 if signature_minima[digest] == maximin_signature]
        chosen = min(tier3)
        selected.append(chosen)
        eligible.remove(chosen)
        steps.append(
            {
                "NUMBER": step_number,
                "PORTFOLIO_SHA256": chosen,
                "COUNT": ROOT_COUNT,
                "ROOT_TICKET_SET_SYMMETRIC_DIFFERENCE": max_root_distance,
                "MAXIMIN_TICKET_SET_DISTANCE_TO_SELECTED": maximin_ticket,
                "MAXIMIN_RESIDUAL_COVERAGE_SIGNATURE_DISTANCE": maximin_signature,
                "TIE_BREAK": "lowest portfolio SHA256",
                "PORTFOLIO": [list(ticket) for ticket in unique[chosen]],
            }
        )

    unsigned: dict[str, Any] = {
        "SCHEMA_VERSION": "B649_K20_V7_DESTROY3_REPAIR_NEUTRAL_RESTART_STARTS_V1",
        "TASK_ID": TASK_ID,
        "SOURCE_RESULT_COMMIT": SOURCE_COMMIT,
        "SOURCE_RESULT_PATH": SOURCE_PATH,
        "SOURCE_RESULT_SHA256": sha256_bytes(source_bytes),
        "ROOT_COUNT": ROOT_COUNT,
        "ROOT_SHA256": ROOT_SHA256,
        "NEUTRAL_UNIQUE_CANDIDATES": len(unique) - 1,
        "NEUTRAL_STARTS_SELECTED": START_COUNT,
        "SELECTION_ORDER": [
            "maximum ticket-set symmetric difference from ROOT",
            "maximum minimum ticket-set distance to already-selected starts",
            "maximum minimum residual-coverage-signature distance to ROOT and selected starts",
            "lowest portfolio SHA256",
        ],
        "RESIDUAL_COVERAGE_SIGNATURE": {
            "DOMAIN": "C(49,3) distinct three-number patterns",
            "PORTFOLIO_SIGNATURE": "patterns contained in at least one of its 20 tickets",
            "RESIDUAL_SIGNATURE": "complement of those patterns",
            "DISTANCE": "Hamming distance, equal to symmetric-difference cardinality",
            "COVERAGE_RELATION": "a 7-number outcome is covered iff it contains a signature pattern",
        },
        "SOURCE_TIE_OCCURRENCES": len(source["GLOBAL_BEST_TIES"]),
        "SOURCE_UNIQUE_BEST_TIE_PORTFOLIOS": len(unique),
        "STARTS": steps,
    }
    return {**unsigned, "SELECTION_SHA256": sha256_bytes(canonical_json(unsigned))}


def prepare_selection(repo_root: Path) -> tuple[dict[str, Any], str]:
    source, source_bytes = load_source_result(repo_root)
    expected = build_selection_document(source, source_bytes)
    path = repo_root / OUTPUT_DIR / STARTS_NAME
    encoded = pretty_json(expected)
    if path.exists():
        current = path.read_bytes()
        if current != encoded:
            raise RuntimeError("existing neutral-start selection differs; refusing to replace it")
    else:
        atomic_write(path, encoded)
    return expected, sha256_bytes(encoded)


def validate_selection_file(path: Path, expected: dict[str, Any]) -> tuple[dict[str, Any], str]:
    if not path.is_file():
        raise RuntimeError("neutral-starts.json must be frozen before scientific execution")
    raw = path.read_bytes()
    document = json.loads(raw)
    if raw != pretty_json(expected) or document != expected:
        raise RuntimeError("frozen neutral-starts.json differs from deterministic source selection")
    unsigned = {key: value for key, value in document.items() if key != "SELECTION_SHA256"}
    if document.get("SELECTION_SHA256") != sha256_bytes(canonical_json(unsigned)):
        raise RuntimeError("neutral-start selection SHA256 does not validate")
    return document, sha256_bytes(raw)


def seal_record(body: dict[str, Any]) -> dict[str, Any]:
    return {**body, "RECORD_SHA256": sha256_bytes(canonical_json(body))}


def validate_record(record: dict[str, Any], expected_sequence: int, expected_start: str) -> None:
    body = {key: value for key, value in record.items() if key != "RECORD_SHA256"}
    if record.get("RECORD_SHA256") != sha256_bytes(canonical_json(body)):
        raise RuntimeError("family journal record SHA256 mismatch")
    if record.get("SEQUENCE") != expected_sequence:
        raise RuntimeError("family journal sequence is discontinuous")
    if record.get("START_SHA256") != expected_start:
        raise RuntimeError("family journal does not follow the frozen start order")
    if record.get("FAMILY_STATUS") != "COMPLETE":
        raise RuntimeError("journal includes an incomplete family")
    if record.get("TRIPLES_COMPLETED") != EXPECTED_TRIPLES:
        raise RuntimeError("journal family did not complete all 1140 triples")
    if record.get("RAW_ATTEMPTS_EXECUTED") != EXPECTED_RAW_ATTEMPTS:
        raise RuntimeError("journal family did not execute all 492480 raw attempts")
    if record.get("EXACT_CANDIDATES_SCORED") != record.get("UNIQUE_LEGAL_PORTFOLIOS"):
        raise RuntimeError("journal family candidate accounting is inconsistent")
    if record.get("PRUNED_CANDIDATES") != 0 or record.get("SAMPLING") != "NONE":
        raise RuntimeError("journal family used pruning or sampling")


def parse_journal(data: bytes) -> list[dict[str, Any]]:
    if not data:
        return []
    if not data.endswith(b"\n"):
        raise RuntimeError("family journal has a partial trailing record")
    records: list[dict[str, Any]] = []
    for line in data.splitlines():
        if not line:
            raise RuntimeError("family journal contains an empty record")
        record = json.loads(line)
        if not isinstance(record, dict):
            raise RuntimeError("family journal row is not an object")
        records.append(record)
    return records


def run_id_for(selection_sha: str) -> str:
    return sha256_bytes(f"{TASK_ID}\n{BASE_HEAD}\n{SOURCE_COMMIT}\n{selection_sha}".encode())


def new_state(selection: dict[str, Any], starts_file_sha: str) -> dict[str, Any]:
    return {
        "SCHEMA_VERSION": "B649_K20_V7_DESTROY3_REPAIR_NEUTRAL_RESTART_STATE_V1",
        "TASK_ID": TASK_ID,
        "RUN_ID": run_id_for(selection["SELECTION_SHA256"]),
        "BASE_HEAD": BASE_HEAD,
        "BRANCH": BRANCH,
        "SOURCE_RESULT_COMMIT": SOURCE_COMMIT,
        "SOURCE_RESULT_SHA256": selection["SOURCE_RESULT_SHA256"],
        "SELECTION_SHA256": selection["SELECTION_SHA256"],
        "SELECTION_FILE_SHA256": starts_file_sha,
        "COMPLETED_START_SHA256S": [],
        "JOURNAL_PREFIX_BYTES": 0,
        "JOURNAL_PREFIX_SHA256": sha256_bytes(b""),
        "IMPROVEMENT_CANONICAL_RECOUNTS": {},
        "CREATED_AT_UTC": utc_now(),
        "UPDATED_AT_UTC": utc_now(),
    }


def write_state(path: Path, state: dict[str, Any], journal_bytes: bytes) -> dict[str, Any]:
    updated = dict(state)
    updated["JOURNAL_PREFIX_BYTES"] = len(journal_bytes)
    updated["JOURNAL_PREFIX_SHA256"] = sha256_bytes(journal_bytes)
    updated["UPDATED_AT_UTC"] = utc_now()
    atomic_write(path, pretty_json(updated))
    return updated


def reconcile_run_state(
    repo_root: Path, selection: dict[str, Any], starts_file_sha: str
) -> tuple[list[dict[str, Any]], dict[str, Any], bytes]:
    journal_path = repo_root / OUTPUT_DIR / JOURNAL_NAME
    state_path = repo_root / OUTPUT_DIR / STATE_NAME
    journal_bytes = journal_path.read_bytes() if journal_path.exists() else b""
    state = json.loads(state_path.read_text("utf-8")) if state_path.exists() else new_state(selection, starts_file_sha)
    expected_state = new_state(selection, starts_file_sha)
    for key in (
        "SCHEMA_VERSION",
        "TASK_ID",
        "RUN_ID",
        "BASE_HEAD",
        "BRANCH",
        "SOURCE_RESULT_COMMIT",
        "SOURCE_RESULT_SHA256",
        "SELECTION_SHA256",
        "SELECTION_FILE_SHA256",
    ):
        if state.get(key) != expected_state.get(key):
            raise RuntimeError(f"state.json identity mismatch at {key}")

    prefix_size = int(state.get("JOURNAL_PREFIX_BYTES", 0))
    if prefix_size < 0 or prefix_size > len(journal_bytes):
        raise RuntimeError("state journal prefix length exceeds the current journal")
    prefix = journal_bytes[:prefix_size]
    if sha256_bytes(prefix) != state.get("JOURNAL_PREFIX_SHA256"):
        raise RuntimeError("state journal prefix SHA256 does not match family-results.jsonl")
    records = parse_journal(prefix)
    completed = [row.get("START_SHA256") for row in records]
    if completed != state.get("COMPLETED_START_SHA256S", []):
        raise RuntimeError("state completed starts do not match its verified journal prefix")

    starts = selection["STARTS"]
    for index, record in enumerate(records):
        validate_record(record, index + 1, starts[index]["PORTFOLIO_SHA256"])
    trailing = parse_journal(journal_bytes[prefix_size:])
    for record in trailing:
        index = len(records)
        if index >= len(starts):
            raise RuntimeError("family journal contains more starts than authorized")
        validate_record(record, index + 1, starts[index]["PORTFOLIO_SHA256"])
        records.append(record)

    if len(records) > len(starts):
        raise RuntimeError("family journal exceeds the frozen start count")
    if len(records) != len(completed):
        state = dict(state)
        state["COMPLETED_START_SHA256S"] = [row["START_SHA256"] for row in records]
        state = write_state(state_path, state, journal_bytes)
        print(
            json.dumps(
                {"EVENT": "RECOVERED_COMPLETE_JOURNAL_RECORDS", "COUNT": len(records) - len(completed)},
                sort_keys=True,
            ),
            flush=True,
        )
    elif not state_path.exists():
        state["COMPLETED_START_SHA256S"] = [row["START_SHA256"] for row in records]
        state = write_state(state_path, state, journal_bytes)
    return records, state, journal_bytes


def scan_complete_family(
    start: dict[str, Any],
    *,
    sequence: int,
    selection_sha: str,
    repo_root: Path,
    draws: Any,
) -> dict[str, Any]:
    portfolio = cycle.normalize_portfolio(start["PORTFOLIO"], pool_size=49, expected_ticket_count=20)
    start_sha = start["PORTFOLIO_SHA256"]
    if cycle.portfolio_sha256(portfolio, pool_size=49) != start_sha:
        raise RuntimeError("frozen start portfolio does not match its SHA256")
    if start.get("COUNT") != ROOT_COUNT:
        raise RuntimeError("frozen start count differs from the root count")

    raw_attempts = legal_emissions = exact_scored = duplicate_emissions = 0
    seen: set[str] = set()
    improvements: dict[str, dict[str, Any]] = {}
    per_triple: list[dict[str, Any]] = []
    best_count = ROOT_COUNT
    best_sha = start_sha
    best_portfolio = portfolio
    began = time.perf_counter()
    triples = itertools.combinations(range(20), 3)

    print(
        json.dumps(
            {"EVENT": "START_BEGIN", "SEQUENCE": sequence, "START_SHA256": start_sha},
            sort_keys=True,
        ),
        flush=True,
    )
    for triple_number, indices in enumerate(triples, start=1):
        residual = cycle.build_triple_residual(portfolio, indices, pool_size=49, draws=draws)
        original = tuple(portfolio[index] for index in indices)
        reproduced_start = residual.outcome_count(original)
        if reproduced_start != ROOT_COUNT:
            raise RuntimeError(
                f"residual start reproduction mismatch for {start_sha} {indices}: {reproduced_start}"
            )

        triple_raw = triple_legal = triple_scored = 0
        triple_best: int | None = None
        for spec in cycle.iter_triple_cycle_specs(portfolio, indices, pool_size=49):
            raw_attempts += 1
            triple_raw += 1
            emission = cycle._emit_spec_normalized(portfolio, spec, pool_size=49)
            if emission is None:
                continue
            legal_emissions += 1
            triple_legal += 1
            if emission.sha256 in seen:
                duplicate_emissions += 1
                continue
            seen.add(emission.sha256)
            outcome_count = residual.outcome_count(emission.added)
            exact_scored += 1
            triple_scored += 1
            triple_best = outcome_count if triple_best is None else max(triple_best, outcome_count)
            if outcome_count > ROOT_COUNT:
                previous = improvements.setdefault(
                    emission.sha256,
                    {
                        "SHA256": emission.sha256,
                        "COUNT": outcome_count,
                        "PORTFOLIO": [list(ticket) for ticket in emission.portfolio],
                        "FIRST_START_SHA256": start_sha,
                        "FIRST_TRIPLE": list(indices),
                        "FIRST_NUMBERS": list(spec.numbers),
                        "FIRST_DIRECTION": spec.direction,
                    },
                )
                if previous["COUNT"] != outcome_count or previous["PORTFOLIO"] != [
                    list(ticket) for ticket in emission.portfolio
                ]:
                    raise RuntimeError("candidate SHA maps to conflicting exact scores or portfolios")
            if outcome_count > best_count or (outcome_count == best_count and emission.sha256 < best_sha):
                best_count = outcome_count
                best_sha = emission.sha256
                best_portfolio = emission.portfolio

        per_triple.append(
            {
                "INDICES": list(indices),
                "RESIDUAL_PATTERN_COUNT": residual.pattern_count,
                "START_REPRODUCTION_COUNT": reproduced_start,
                "RAW_ATTEMPTS": triple_raw,
                "LEGAL_EMISSIONS": triple_legal,
                "EXACT_CANDIDATES_SCORED": triple_scored,
                "DUPLICATE_EMISSIONS": triple_legal - triple_scored,
                "BEST_CANDIDATE_COUNT": triple_best,
            }
        )
        if triple_number % 25 == 0 or triple_number == EXPECTED_TRIPLES:
            print(
                json.dumps(
                    {
                        "EVENT": "START_PROGRESS",
                        "SEQUENCE": sequence,
                        "START_SHA256": start_sha,
                        "TRIPLES_COMPLETED": triple_number,
                        "RAW_ATTEMPTS": raw_attempts,
                        "EXACT_CANDIDATES_SCORED": exact_scored,
                        "ELAPSED_SECONDS": round(time.perf_counter() - began, 3),
                    },
                    sort_keys=True,
                ),
                flush=True,
            )

    if len(per_triple) != EXPECTED_TRIPLES or raw_attempts != EXPECTED_RAW_ATTEMPTS:
        raise RuntimeError("cycle family terminated before all 1140 triples / 492480 attempts")
    if legal_emissions != exact_scored + duplicate_emissions:
        raise RuntimeError("candidate accounting identity failed")
    if exact_scored != len(seen):
        raise RuntimeError("exact score count differs from unique legal candidate count")
    if sum(row["RAW_ATTEMPTS"] for row in per_triple) != EXPECTED_RAW_ATTEMPTS:
        raise RuntimeError("per-triple raw-attempt accounting failed")
    if any(row["RAW_ATTEMPTS"] != 432 for row in per_triple):
        raise RuntimeError("a triple did not enumerate all 432 directed number cycles")

    body = {
        "SCHEMA_VERSION": "B649_K20_V7_NEUTRAL_RESTART_FAMILY_RESULT_V1",
        "TASK_ID": TASK_ID,
        "RUN_ID": run_id_for(selection_sha),
        "SEQUENCE": sequence,
        "FAMILY_STATUS": "COMPLETE",
        "FAMILY_NAME": FAMILY_NAME,
        "START_SHA256": start_sha,
        "START_COUNT": ROOT_COUNT,
        "START_REPRODUCTION_CHECKS": len(per_triple),
        "START_REPRODUCTION_MISMATCHES": 0,
        "TRIPLES_EXPECTED": EXPECTED_TRIPLES,
        "TRIPLES_COMPLETED": len(per_triple),
        "RAW_ATTEMPTS_EXPECTED": EXPECTED_RAW_ATTEMPTS,
        "RAW_ATTEMPTS_EXECUTED": raw_attempts,
        "LEGAL_EMISSIONS": legal_emissions,
        "UNIQUE_LEGAL_PORTFOLIOS": len(seen),
        "DUPLICATE_EMISSIONS": duplicate_emissions,
        "EXACT_CANDIDATES_SCORED": exact_scored,
        "PRUNED_CANDIDATES": 0,
        "PRUNING": "NONE",
        "SAMPLING": "NONE",
        "ADAPTIVE_CHANGES": "NONE",
        "BEST_COUNT_INCLUDING_START": best_count,
        "BEST_SHA256_INCLUDING_START": best_sha,
        "BEST_PORTFOLIO_INCLUDING_START": [list(ticket) for ticket in best_portfolio],
        "STRICT_IMPROVEMENTS": sorted(improvements.values(), key=lambda row: row["SHA256"]),
        "TRIPLE_RESULTS": per_triple,
        "ELAPSED_SECONDS": round(time.perf_counter() - began, 3),
    }
    return seal_record(body)


def append_complete_record(
    repo_root: Path,
    record: dict[str, Any],
    records: list[dict[str, Any]],
    state: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any], bytes]:
    journal_path = repo_root / OUTPUT_DIR / JOURNAL_NAME
    state_path = repo_root / OUTPUT_DIR / STATE_NAME
    new_records = [*records, record]
    journal_bytes = b"".join(canonical_json(row) + b"\n" for row in new_records)
    atomic_write(journal_path, journal_bytes)
    new_state_value = dict(state)
    new_state_value["COMPLETED_START_SHA256S"] = [row["START_SHA256"] for row in new_records]
    new_state_value = write_state(state_path, new_state_value, journal_bytes)
    return new_records, new_state_value, journal_bytes


def collect_improvements(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    candidates: dict[str, dict[str, Any]] = {}
    for family in records:
        for row in family["STRICT_IMPROVEMENTS"]:
            previous = candidates.setdefault(row["SHA256"], row)
            if previous["COUNT"] != row["COUNT"] or previous["PORTFOLIO"] != row["PORTFOLIO"]:
                raise RuntimeError("same candidate SHA has inconsistent family records")
    return candidates


def canonical_recount_improvements(
    repo_root: Path,
    selection: dict[str, Any],
    starts_file_sha: str,
    records: list[dict[str, Any]],
    state: dict[str, Any],
    journal_bytes: bytes,
    draws: Any,
) -> dict[str, Any]:
    state_path = repo_root / OUTPUT_DIR / STATE_NAME
    recounts = dict(state.get("IMPROVEMENT_CANONICAL_RECOUNTS", {}))
    candidates = collect_improvements(records)
    for digest in sorted(candidates):
        if digest in recounts:
            continue
        row = candidates[digest]
        canonical_count = cycle.official_any_prize_outcome_count(
            row["PORTFOLIO"], pool_size=49, draws=draws
        )
        recounts[digest] = {
            "SHA256": digest,
            "RESIDUAL_COUNT": row["COUNT"],
            "CANONICAL_COUNT": canonical_count,
            "MATCH": canonical_count == row["COUNT"],
        }
        state = dict(state)
        state["IMPROVEMENT_CANONICAL_RECOUNTS"] = recounts
        state = write_state(state_path, state, journal_bytes)
        print(
            json.dumps(
                {
                    "EVENT": "CANONICAL_RECOUNT",
                    "SHA256": digest,
                    "RESIDUAL_COUNT": row["COUNT"],
                    "CANONICAL_COUNT": canonical_count,
                    "MATCH": canonical_count == row["COUNT"],
                },
                sort_keys=True,
            ),
            flush=True,
        )
    if set(recounts) != set(candidates):
        raise RuntimeError("canonical recount ledger does not cover every strict candidate")
    return recounts


def terminal_result(
    repo_root: Path,
    selection: dict[str, Any],
    starts_file_sha: str,
    records: list[dict[str, Any]],
    state: dict[str, Any],
    journal_bytes: bytes,
    recounts: dict[str, Any],
) -> dict[str, Any]:
    improvements = collect_improvements(records)
    recounts_ok = all(item.get("MATCH") is True for item in recounts.values())
    if improvements and recounts_ok:
        best_row = min(improvements.values(), key=lambda row: (-row["COUNT"], row["SHA256"]))
        best_count = int(recounts[best_row["SHA256"]]["CANONICAL_COUNT"])
        best_sha = best_row["SHA256"]
        best_recount_status = "PASS_ALL_STRICT_CANDIDATES_RECOUNTED"
    elif improvements:
        best_row = min(improvements.values(), key=lambda row: (-row["COUNT"], row["SHA256"]))
        best_count = int(best_row["COUNT"])
        best_sha = best_row["SHA256"]
        best_recount_status = "FAIL_RESIDUAL_CANONICAL_MISMATCH"
    else:
        best_count = ROOT_COUNT
        best_sha = ROOT_SHA256
        best_recount_status = "PASS_PINNED_ROOT_CANONICAL_RECOUNT"

    full_families = len(records)
    exact_scored = sum(int(row["EXACT_CANDIDATES_SCORED"]) for row in records)
    raw_total = sum(int(row["RAW_ATTEMPTS_EXECUTED"]) for row in records)
    escaped = bool(improvements) and recounts_ok and best_count > ROOT_COUNT
    decision = (
        "REPAIR_NEUTRAL_ESCAPE_ESTABLISHED"
        if escaped
        else "NO_IMPROVEMENT_IN_16_REPAIR_NEUTRAL_RESTARTS"
        if full_families == START_COUNT and not improvements
        else "CANONICAL_RECOUNT_MISMATCH"
    )
    result = {
        "SCHEMA_VERSION": "B649_K20_V7_DESTROY3_REPAIR_NEUTRAL_RESTART_RESULT_V1",
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "COMPLETE" if full_families == START_COUNT and recounts_ok else "FAILED_VERIFICATION",
        "RUN_ID": run_id_for(selection["SELECTION_SHA256"]),
        "BASE_HEAD": BASE_HEAD,
        "BRANCH": BRANCH,
        "WORKTREE_PATH": str(repo_root.resolve()),
        "SOURCE_RESULT_COMMIT": SOURCE_COMMIT,
        "SOURCE_RESULT_PATH": SOURCE_PATH,
        "SOURCE_RESULT_SHA256": selection["SOURCE_RESULT_SHA256"],
        "ROOT_COUNT": ROOT_COUNT,
        "ROOT_SHA256": ROOT_SHA256,
        "NEUTRAL_UNIQUE_CANDIDATES": selection["NEUTRAL_UNIQUE_CANDIDATES"],
        "NEUTRAL_STARTS_SELECTED": len(selection["STARTS"]),
        "NEUTRAL_STARTS_PATH": str((OUTPUT_DIR / STARTS_NAME).as_posix()),
        "SELECTION_SHA256": selection["SELECTION_SHA256"],
        "SELECTION_FILE_SHA256": starts_file_sha,
        "RESIDUAL_COVERAGE_SIGNATURE_DEFINITION": selection["RESIDUAL_COVERAGE_SIGNATURE"],
        "FULL_FAMILIES_COMPLETED": full_families,
        "TRIPLES_PER_FAMILY": EXPECTED_TRIPLES,
        "RAW_ATTEMPTS_PER_FAMILY": EXPECTED_RAW_ATTEMPTS,
        "RAW_ATTEMPTS_TOTAL": raw_total,
        "EXACT_CANDIDATES_SCORED": exact_scored,
        "STRICT_UNIQUE_CANDIDATES_CANONICALLY_RECOUNTED": len(recounts),
        "CANONICAL_RECOUNTS": [recounts[key] for key in sorted(recounts)],
        "BEST_COUNT": best_count,
        "BEST_DELTA": best_count - ROOT_COUNT,
        "BEST_SHA256": best_sha,
        "BEST_CANONICAL_RECOUNT_STATUS": best_recount_status,
        "REPAIR_NEUTRAL_ESCAPE_ESTABLISHED": "YES" if escaped else "NO",
        "TERMINAL_DECISION": decision,
        "ALL_NEUTRAL_TIES_EXHAUSTED": "NO",
        "FAMILY_RESULTS_PATH": str((OUTPUT_DIR / JOURNAL_NAME).as_posix()),
        "FAMILY_RESULTS_JOURNAL_PREFIX_SHA256": sha256_bytes(journal_bytes),
        "STATE_PATH": str((OUTPUT_DIR / STATE_NAME).as_posix()),
        "PROJECT_MEMORY_WRITE": "NO",
        "PUSH": "NO",
        "PR": "NO",
        "MERGE": "NO",
        "PRODUCTION_CHANGE": "NONE",
        "TERMINAL_AT_UTC": utc_now(),
    }
    path = repo_root / OUTPUT_DIR / RESULT_NAME
    if path.exists():
        previous = json.loads(path.read_text("utf-8"))
        if (
            previous.get("TASK_STATUS") == "STOPPED_INSUFFICIENT_STABLE_DISK_SPACE"
            and result["FULL_FAMILIES_COMPLETED"] == START_COUNT
        ):
            atomic_write(path, pretty_json(result))
        else:
            result["TERMINAL_AT_UTC"] = previous.get(
                "TERMINAL_AT_UTC", result["TERMINAL_AT_UTC"]
            )
            if previous != result:
                raise RuntimeError("existing terminal result differs from the resumed run")
    else:
        atomic_write(path, pretty_json(result))
    return result


def run_science(repo_root: Path) -> dict[str, Any]:
    source, source_bytes = load_source_result(repo_root)
    expected_selection = build_selection_document(source, source_bytes)
    selection_path = repo_root / OUTPUT_DIR / STARTS_NAME
    selection, starts_file_sha = validate_selection_file(selection_path, expected_selection)
    records, state, journal_bytes = reconcile_run_state(repo_root, selection, starts_file_sha)
    family_path = repo_root / OUTPUT_DIR / JOURNAL_NAME
    state_path = repo_root / OUTPUT_DIR / STATE_NAME

    print(
        json.dumps(
            {
                "EVENT": "RUN_RESUME_STATE",
                "RUN_ID": run_id_for(selection["SELECTION_SHA256"]),
                "COMPLETED_STARTS": len(records),
                "TOTAL_STARTS": len(selection["STARTS"]),
                "JOURNAL_PREFIX_SHA256": sha256_bytes(journal_bytes),
            },
            sort_keys=True,
        ),
        flush=True,
    )
    if len(records) < START_COUNT:
        draws = cycle.load_draws(49)
        for index in range(len(records), START_COUNT):
            record = scan_complete_family(
                selection["STARTS"][index],
                sequence=index + 1,
                selection_sha=selection["SELECTION_SHA256"],
                repo_root=repo_root,
                draws=draws,
            )
            validate_record(record, index + 1, selection["STARTS"][index]["PORTFOLIO_SHA256"])
            records, state, journal_bytes = append_complete_record(
                repo_root, record, records, state
            )
            print(
                json.dumps(
                    {
                        "EVENT": "START_CHECKPOINTED",
                        "SEQUENCE": index + 1,
                        "START_SHA256": record["START_SHA256"],
                        "FULL_FAMILIES_COMPLETED": len(records),
                        "EXACT_CANDIDATES_SCORED": record["EXACT_CANDIDATES_SCORED"],
                        "JOURNAL_PREFIX_SHA256": sha256_bytes(journal_bytes),
                    },
                    sort_keys=True,
                ),
                flush=True,
            )
    else:
        draws = cycle.load_draws(49)

    if len(records) != START_COUNT:
        raise RuntimeError("all 16 frozen starts must finish before terminal result creation")
    recounts = canonical_recount_improvements(
        repo_root, selection, starts_file_sha, records, state, journal_bytes, draws
    )
    state = json.loads(state_path.read_text("utf-8"))
    result = terminal_result(
        repo_root, selection, starts_file_sha, records, state, journal_bytes, recounts
    )
    print(
        json.dumps(
            {
                "EVENT": "RUN_TERMINAL",
                "TASK_STATUS": result["TASK_STATUS"],
                "FULL_FAMILIES_COMPLETED": result["FULL_FAMILIES_COMPLETED"],
                "EXACT_CANDIDATES_SCORED": result["EXACT_CANDIDATES_SCORED"],
                "BEST_COUNT": result["BEST_COUNT"],
                "BEST_DELTA": result["BEST_DELTA"],
                "BEST_SHA256": result["BEST_SHA256"],
                "REPAIR_NEUTRAL_ESCAPE_ESTABLISHED": result["REPAIR_NEUTRAL_ESCAPE_ESTABLISHED"],
            },
            sort_keys=True,
        ),
        flush=True,
    )
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--prepare-selection", action="store_true")
    group.add_argument("--run", action="store_true")
    args = parser.parse_args(argv)
    repo_root = Path(__file__).resolve().parents[1]
    output_dir = repo_root / OUTPUT_DIR
    with SingleWriter(output_dir):
        if args.prepare_selection:
            selection, file_sha = prepare_selection(repo_root)
            print(
                json.dumps(
                    {
                        "EVENT": "NEUTRAL_STARTS_FROZEN",
                        "NEUTRAL_UNIQUE_CANDIDATES": selection["NEUTRAL_UNIQUE_CANDIDATES"],
                        "NEUTRAL_STARTS_SELECTED": len(selection["STARTS"]),
                        "SELECTION_SHA256": selection["SELECTION_SHA256"],
                        "SELECTION_FILE_SHA256": file_sha,
                        "PATH": str((OUTPUT_DIR / STARTS_NAME).as_posix()),
                    },
                    sort_keys=True,
                ),
                flush=True,
            )
            return 0
        result = run_science(repo_root)
        return 0 if result["TASK_STATUS"] == "COMPLETE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
