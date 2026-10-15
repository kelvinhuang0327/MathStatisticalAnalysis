"""Terminal verification and scientific seal for one orbit-successor journal.

The seal replays a validated dispatcher journal. It never imports the frozen
scan, generator, or official outcome enumerator. An injected recount supplies
the portfolio count for this process; a matching count is not an official
full-universe recount.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Sequence
from typing import Any, cast

from lottolab.research import b649_k20_orbit_successor_dispatcher_r1 as dispatcher

TASK_ID = "B649_K20_ORBIT_SUCCESSOR_TERMINAL_SEAL_R1"
RESULT_SCHEMA = "B649_K20_ORBIT_SUCCESSOR_TERMINAL_RESULT_R1"
REPOSITORY = "kelvinhuang0327/MathStatisticalAnalysis"
BASE_COMMIT = "7aaa5c3bb8f2ab4d18ff946906f81a0c7f418f03"
BASE_TREE = "310449f1b1ee806215c326787dbffd60ad1c49e3"
OFFICIAL_OUTCOME_UNIVERSE = 601_304_088

POOL_SIZE = 49
TICKET_COUNT = 20
TICKET_SIZE = 6

STATUS_SEALED = "COMPLETED_SCIENTIFIC_SEAL"
STATUS_INCOMPLETE = "INCOMPLETE_DURABLE"
CLASS_NO_GAIN = "NO_GAIN"
CLASS_STRICT_GAIN = "STRICT_GAIN"
DISPOSITION_TERMINAL = "TERMINAL_ACCEPTED"
DISPOSITION_PARTIAL = "PARTIAL"
DISPOSITION_INTERRUPTED = "INTERRUPTED"
LAUNCH_REPLACED = "INCUMBENT_REPLACED"
LAUNCH_RETAINED = "INCUMBENT_RETAINED"
NOT_RUN = "NOT RUN"

TERMINAL_VERIFIER_ENTRYPOINT = (
    "lottolab.research.b649_k20_orbit_successor_terminal_seal_r1:seal_orbit_successor_terminal"
)
TERMINAL_SEAL_ENTRYPOINT = TERMINAL_VERIFIER_ENTRYPOINT

_FORBIDDEN_CLAIMS = (
    "NO_STRICT_GAIN_IN_FROZEN_FOUR_TICKET_CYCLE_FAMILY",
    "GLOBAL_K20_OPTIMUM",
)
_COVERAGE_KEYS = (
    "directly_scored_member_count",
    "mathematical_coverage",
    "orbit_member_count",
    "representative_index",
)
_HISTORICAL = "HISTORICALLY_COVERED_BY_SYMMETRY"
_UNVISITED = "UNVISITED"


class TerminalSealError(ValueError):
    """Closed failure. No completed scientific seal is produced."""


def canonical_result_bytes(result: dict[str, Any]) -> bytes:
    """Serialize a seal result with sorted keys, compact separators, and one LF."""

    return _canonical_json_bytes(result)


def certified_coverage_mapping(manifest_bytes: bytes) -> list[dict[str, Any]]:
    """Return the manifest orbit-coverage projection the seal recomputes itself."""

    _plan, document = _load_manifest(manifest_bytes)
    return _coverage_projection(document)


def seal_orbit_successor_terminal(
    manifest_bytes: bytes,
    successor_journal_bytes: bytes,
    historical_journal_bytes: bytes,
    portfolio_tickets: object,
    coverage_mapping: object,
    *,
    evaluator_bytes: bytes,
    recount: Callable[[tuple[tuple[int, ...], ...]], int],
    run_disposition: str,
    source_commit: str,
    source_tree: str,
) -> dict[str, Any]:
    """Seal one terminal journal, or return INCOMPLETE_DURABLE for a valid prefix.

    ``recount`` receives the normalized 20-ticket portfolio and returns its
    exact winning count. This function hashes ``evaluator_bytes`` and does not
    execute that module. ``real_canonical_recount`` stays ``NOT RUN``.
    """

    _bytes(manifest_bytes, "manifest")
    _bytes(successor_journal_bytes, "successor journal")
    _bytes(historical_journal_bytes, "historical journal")
    _bytes(evaluator_bytes, "official evaluator")
    if type(run_disposition) is not str or run_disposition not in {
        DISPOSITION_TERMINAL,
        DISPOSITION_PARTIAL,
        DISPOSITION_INTERRUPTED,
    }:
        raise TerminalSealError("run disposition is not a recognized terminal state")
    if type(source_commit) is not str or type(source_tree) is not str:
        raise TerminalSealError("source identity differs")
    if source_commit != BASE_COMMIT or source_tree != BASE_TREE:
        raise TerminalSealError("source identity differs")
    if not callable(recount):
        raise TerminalSealError("terminal recount must be a callable")

    evaluator_sha256 = _sha256(evaluator_bytes)
    if evaluator_sha256 != dispatcher.EVALUATOR_SHA256:
        raise TerminalSealError("official evaluator SHA-256 differs")
    historical_sha256 = _verify_historical_journal(historical_journal_bytes)
    plan, document = _load_manifest(manifest_bytes)
    _verify_manifest_source(document)
    baseline_tickets, baseline_sha256 = _normalize_portfolio(
        _object(document.get("baseline"), "baseline").get("normalized_tickets"),
        label="manifest baseline portfolio",
    )
    if baseline_sha256 != plan.baseline_identity_sha256:
        raise TerminalSealError("manifest baseline tickets do not recompute to the frozen identity")
    projection = _coverage_projection(document)
    claimed = _claimed_coverage(coverage_mapping)
    if claimed != projection:
        raise TerminalSealError("coverage mapping differs from the certified manifest")

    try:
        state = dispatcher.validate_progress_prefix(successor_journal_bytes, plan)
    except dispatcher.DispatcherError as error:
        raise TerminalSealError(str(error)) from error

    record_count = len(state.records)
    journal_sha256 = _sha256(successor_journal_bytes)
    terminal = (
        run_disposition == DISPOSITION_TERMINAL
        and record_count == dispatcher.PENDING_REPRESENTATIVES
    )
    if not terminal:
        return _incomplete_result(
            run_disposition=run_disposition,
            accepted_prefix_records=record_count,
            successor_journal_sha256=journal_sha256,
        )

    indices = _representative_indices(state.records)
    expected_indices = [item.index for item in plan.representatives]
    ascending = indices == sorted(indices) and len(set(indices)) == len(indices)
    if indices != expected_indices or not ascending:
        raise TerminalSealError("representative indices are not the ascending manifest cover")
    raw_attempts = _raw_attempt_total(state.records)
    if raw_attempts != dispatcher.EXPECTED_NEW_RAW_ATTEMPTS:
        raise TerminalSealError("new raw attempt total differs")
    _require_complete_orbit_cover(projection, indices)

    launch = _launch_incumbent(state.records[0])
    final = state.incumbent
    frozen_comparison = _frozen_baseline_comparison(final.official_count)
    replaced, launch_comparison = _launch_comparison(launch, final)
    portfolio, portfolio_sha256 = _normalize_portfolio(portfolio_tickets, label="sealed portfolio")
    _require_portfolio_identity(
        portfolio,
        portfolio_sha256,
        baseline_tickets=baseline_tickets,
        baseline_sha256=baseline_sha256,
        incumbent_sha256=final.result_identity_sha256,
        frozen_comparison=frozen_comparison,
    )
    recounted = recount(portfolio)
    if type(recounted) is not int or recounted != final.official_count:
        raise TerminalSealError("recount count differs from the journal incumbent")

    payload: dict[str, Any] = {
        "schema": RESULT_SCHEMA,
        "task_id": TASK_ID,
        "status": STATUS_SEALED,
        "completed_scientific_seal": True,
        "run_disposition": run_disposition,
        "source_pins": {
            "repository": REPOSITORY,
            "base_commit": BASE_COMMIT,
            "base_tree": BASE_TREE,
            "manifest_sha256": plan.manifest_sha256,
            "representative_tuples_sha256": plan.representative_tuples_sha256,
            "historical_journal_sha256": historical_sha256,
            "official_evaluator_sha256": evaluator_sha256,
            "predicate_sha256": dispatcher.PREDICATE_SHA256,
            "driver_sha256": dispatcher.DRIVER_SHA256,
            "manifest_source_commit": _text(
                _object(document.get("source_identity"), "source_identity").get("source_commit"),
                "manifest source commit",
            ),
            "manifest_source_tree": _text(
                _object(document.get("source_identity"), "source_identity").get("source_tree"),
                "manifest source tree",
            ),
        },
        "journal_identity": {
            "successor_journal_sha256": journal_sha256,
            "record_count": record_count,
            "representative_indices": indices,
        },
        "orbit_accounting": _orbit_accounting(raw_attempts),
        "portfolio": {
            "tickets": [list(ticket) for ticket in portfolio],
            "normalized_sha256": portfolio_sha256,
            "ticket_count": TICKET_COUNT,
        },
        "exact_count": final.official_count,
        "scientific_classification": frozen_comparison,
        "frozen_baseline": {
            "count": plan.baseline_count,
            "normalized_sha256": baseline_sha256,
            "strict_gain_minimum": dispatcher.STRICT_GAIN_MINIMUM_COUNT,
            "comparison": frozen_comparison,
        },
        "launch_time_incumbent": {
            "count": launch[0],
            "normalized_sha256": launch[1],
            "replaced": replaced,
            "equal_count_replaces_incumbent": False,
            "comparison": launch_comparison,
        },
        "terminal_recount": {
            "interface": "injected_portfolio_count",
            "pinned_official_evaluator_sha256": evaluator_sha256,
            "official_evaluator_executed": False,
            "official_outcome_universe": OFFICIAL_OUTCOME_UNIVERSE,
            "official_universe_enumerated": False,
            "real_canonical_recount": NOT_RUN,
            "real_scientific_execution": NOT_RUN,
            "recount_count": recounted,
            "journal_incumbent_count": final.official_count,
        },
        "synthetic_result_is_not_a_discovered_higher_winning_count": True,
    }
    payload["result_sha256"] = _result_sha256(payload)
    _reject_forbidden_claims(payload)
    return payload


def _incomplete_result(
    *,
    run_disposition: str,
    accepted_prefix_records: int,
    successor_journal_sha256: str,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema": RESULT_SCHEMA,
        "task_id": TASK_ID,
        "status": STATUS_INCOMPLETE,
        "completed_scientific_seal": False,
        "run_disposition": run_disposition,
        "accepted_prefix_records": accepted_prefix_records,
        "required_representative_records": dispatcher.PENDING_REPRESENTATIVES,
        "gain_classification_emitted": False,
        "real_canonical_recount": NOT_RUN,
        "real_scientific_execution": NOT_RUN,
        "successor_journal_sha256": successor_journal_sha256,
    }
    _reject_forbidden_claims(payload)
    encoded = canonical_result_bytes(payload).decode("ascii")
    if CLASS_NO_GAIN in encoded or CLASS_STRICT_GAIN in encoded:
        raise TerminalSealError("incomplete durable result classified a gain state")
    return payload


def _orbit_accounting(raw_attempts: int) -> dict[str, Any]:
    return {
        "total_mathematical_orbits": dispatcher.TOTAL_ORBITS,
        "historical_covered_orbits": dispatcher.HISTORICALLY_COVERED_ORBITS,
        "new_covered_orbits": dispatcher.PENDING_REPRESENTATIVES,
        "historical_directly_scored_quadruples": (
            dispatcher.HISTORICALLY_DIRECTLY_SCORED_QUADRUPLES
        ),
        "new_directly_scored_representatives": dispatcher.PENDING_REPRESENTATIVES,
        "new_raw_attempts": raw_attempts,
        "mathematical_coverage_implies_direct_score": False,
    }


def _frozen_baseline_comparison(official_count: int) -> str:
    if official_count == dispatcher.BASELINE_COUNT:
        return CLASS_NO_GAIN
    if official_count >= dispatcher.STRICT_GAIN_MINIMUM_COUNT:
        return CLASS_STRICT_GAIN
    raise TerminalSealError("final count is below the frozen baseline")


def _launch_comparison(
    launch: tuple[int, str],
    final: dispatcher.Incumbent,
) -> tuple[bool, str]:
    launch_count, launch_identity = launch
    if final.official_count > launch_count:
        return True, LAUNCH_REPLACED
    if final.official_count == launch_count:
        if final.result_identity_sha256 != launch_identity:
            raise TerminalSealError("equal count replaced the launch-time incumbent")
        return False, LAUNCH_RETAINED
    raise TerminalSealError("final count fell below the launch-time incumbent")


def _require_portfolio_identity(
    portfolio: tuple[tuple[int, ...], ...],
    portfolio_sha256: str,
    *,
    baseline_tickets: tuple[tuple[int, ...], ...],
    baseline_sha256: str,
    incumbent_sha256: str,
    frozen_comparison: str,
) -> None:
    if portfolio_sha256 != incumbent_sha256:
        raise TerminalSealError("portfolio normalized SHA-256 differs from the replayed incumbent")
    if frozen_comparison == CLASS_NO_GAIN:
        if portfolio != baseline_tickets or portfolio_sha256 != baseline_sha256:
            raise TerminalSealError("equal count replaced the frozen baseline portfolio")
        return
    if portfolio_sha256 == baseline_sha256 or portfolio == baseline_tickets:
        raise TerminalSealError("strict-gain portfolio identity must be the improvement candidate")


def _launch_incumbent(record: dict[str, Any]) -> tuple[int, str]:
    before = _object(record.get("incumbent_before"), "launch-time incumbent")
    count = before.get("official_count")
    identity = before.get("result_identity_sha256")
    if (
        type(count) is not int
        or count != dispatcher.BASELINE_COUNT
        or type(identity) is not str
        or identity != dispatcher.BASELINE_PORTFOLIO_SHA256
    ):
        raise TerminalSealError("launch-time incumbent differs from the frozen baseline")
    return count, identity


def _require_complete_orbit_cover(
    projection: Sequence[dict[str, Any]], indices: Sequence[int]
) -> None:
    historical = {
        row["representative_index"]
        for row in projection
        if row["mathematical_coverage"] == _HISTORICAL
    }
    unvisited = {
        row["representative_index"]
        for row in projection
        if row["mathematical_coverage"] == _UNVISITED
    }
    covered_now = set(indices)
    if (
        len(historical) != dispatcher.HISTORICALLY_COVERED_ORBITS
        or len(unvisited) != dispatcher.PENDING_REPRESENTATIVES
        or covered_now != unvisited
        or historical & covered_now
        or len(historical | covered_now) != dispatcher.TOTAL_ORBITS
    ):
        raise TerminalSealError("orbit coverage does not account for every mathematical orbit")


def _representative_indices(records: Sequence[dict[str, Any]]) -> list[int]:
    indices: list[int] = []
    for record in records:
        index = record.get("representative_index")
        if type(index) is not int:
            raise TerminalSealError("representative index is not an integer")
        indices.append(index)
    return indices


def _raw_attempt_total(records: Sequence[dict[str, Any]]) -> int:
    total = 0
    for record in records:
        raw_attempts = record.get("raw_attempts")
        if type(raw_attempts) is not int:
            raise TerminalSealError("progress record raw attempt count differs")
        total += raw_attempts
    return total


def _verify_historical_journal(data: bytes) -> str:
    digest = _sha256(data)
    if digest != dispatcher.HISTORICAL_JOURNAL_SHA256:
        raise TerminalSealError("historical journal SHA-256 differs")
    if not data.endswith(b"\n"):
        raise TerminalSealError("historical journal record count differs")
    lines = data.splitlines()
    if len(lines) != dispatcher.HISTORICALLY_DIRECTLY_SCORED_QUADRUPLES or any(
        not line for line in lines
    ):
        raise TerminalSealError("historical journal record count differs")
    return digest


def _verify_manifest_source(document: dict[str, Any]) -> None:
    source = _object(document.get("source_identity"), "source_identity")
    if source.get("repository") != REPOSITORY:
        raise TerminalSealError("source identity differs")


def _load_manifest(manifest_bytes: bytes) -> tuple[dispatcher.ManifestPlan, dict[str, Any]]:
    try:
        plan = dispatcher.load_manifest_plan(manifest_bytes)
    except dispatcher.DispatcherError as error:
        raise TerminalSealError(str(error)) from error
    try:
        parsed = json.loads(manifest_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise TerminalSealError("orbit manifest is not valid JSON") from error
    return plan, _object(parsed, "orbit manifest")


def _coverage_projection(document: dict[str, Any]) -> list[dict[str, Any]]:
    orbits = _list(document.get("orbits"), "orbits")
    if len(orbits) != dispatcher.TOTAL_ORBITS:
        raise TerminalSealError("manifest orbit count differs")
    projection: list[dict[str, Any]] = []
    seen: set[int] = set()
    direct_total = 0
    historical_partial = False
    for position, raw_row in enumerate(orbits):
        row = _object(raw_row, f"orbits[{position}]")
        index = row.get("representative_index")
        state = row.get("mathematical_coverage")
        direct = _list(row.get("directly_scored_member_indices"), "directly scored members")
        journal_ids = _list(row.get("journal_record_indices"), "journal record indices")
        members = _list(row.get("member_indices"), "orbit members")
        if type(index) is not int or index in seen:
            raise TerminalSealError("manifest orbit representative index is invalid")
        if state not in {_HISTORICAL, _UNVISITED}:
            raise TerminalSealError("manifest contains an unknown mathematical coverage state")
        if len(direct) != len(journal_ids):
            raise TerminalSealError("coverage mapping direct-score accounting differs")
        seen.add(index)
        direct_total += len(direct)
        if state == _UNVISITED and direct:
            raise TerminalSealError("unvisited orbit is marked directly scored")
        if state == _HISTORICAL and len(direct) < len(members):
            historical_partial = True
        projection.append(
            {
                "representative_index": index,
                "mathematical_coverage": state,
                "directly_scored_member_count": len(direct),
                "orbit_member_count": len(members),
            }
        )
    projection.sort(key=lambda item: int(item["representative_index"]))
    historical_count = sum(item["mathematical_coverage"] == _HISTORICAL for item in projection)
    unvisited_count = sum(item["mathematical_coverage"] == _UNVISITED for item in projection)
    if (
        historical_count != dispatcher.HISTORICALLY_COVERED_ORBITS
        or unvisited_count != dispatcher.PENDING_REPRESENTATIVES
        or direct_total != dispatcher.HISTORICALLY_DIRECTLY_SCORED_QUADRUPLES
        or not historical_partial
    ):
        raise TerminalSealError("historical orbit coverage is not distinct from direct scores")
    return projection


def _claimed_coverage(mapping: object) -> list[dict[str, Any]]:
    rows = _list(mapping, "coverage mapping")
    claimed: list[dict[str, Any]] = []
    for position, raw_row in enumerate(rows):
        row = _object(raw_row, f"coverage mapping[{position}]")
        if set(row) != set(_COVERAGE_KEYS):
            raise TerminalSealError("coverage mapping entry has unexpected fields")
        index = row.get("representative_index")
        state = row.get("mathematical_coverage")
        direct_count = row.get("directly_scored_member_count")
        member_count = row.get("orbit_member_count")
        if type(index) is not int or type(direct_count) is not int or type(member_count) is not int:
            raise TerminalSealError("coverage mapping entry has a non-integer count")
        if type(state) is not str:
            raise TerminalSealError("coverage mapping entry has an invalid state")
        claimed.append(
            {
                "representative_index": index,
                "mathematical_coverage": state,
                "directly_scored_member_count": direct_count,
                "orbit_member_count": member_count,
            }
        )
    claimed.sort(key=lambda item: int(item["representative_index"]))
    return claimed


def _normalize_portfolio(tickets: object, *, label: str) -> tuple[tuple[tuple[int, ...], ...], str]:
    rows = _list(tickets, label)
    if len(rows) != TICKET_COUNT:
        raise TerminalSealError(f"{label} must contain {TICKET_COUNT} tickets")
    normalized: list[tuple[int, ...]] = []
    for raw_ticket in rows:
        numbers = _list(raw_ticket, f"{label} ticket")
        if len(numbers) != TICKET_SIZE or any(type(number) is not int for number in numbers):
            raise TerminalSealError(f"{label} ticket must contain six integers in 1..49")
        ticket = tuple(sorted(number for number in numbers if type(number) is int))
        distinct = len(set(ticket)) == TICKET_SIZE
        in_pool = all(1 <= number <= POOL_SIZE for number in ticket)
        if not distinct or not in_pool:
            raise TerminalSealError(f"{label} ticket must contain six distinct integers in 1..49")
        normalized.append(ticket)
    canonical = tuple(sorted(normalized))
    if len(set(canonical)) != TICKET_COUNT:
        raise TerminalSealError(f"{label} contains duplicate tickets")
    payload = json.dumps(
        [list(ticket) for ticket in canonical],
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return canonical, _sha256(payload)


def _result_sha256(payload: dict[str, Any]) -> str:
    unsigned = {key: value for key, value in payload.items() if key != "result_sha256"}
    return _sha256(_canonical_json_bytes(unsigned))


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
        raise TerminalSealError("result cannot be serialized as canonical JSON") from error
    return (encoded + "\n").encode("utf-8")


def _reject_forbidden_claims(payload: dict[str, Any]) -> None:
    encoded = canonical_result_bytes(payload).decode("ascii")
    for claim in _FORBIDDEN_CLAIMS:
        if claim in encoded:
            raise TerminalSealError("forbidden scientific claim")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _bytes(value: bytes, label: str) -> bytes:
    if type(value) is not bytes:
        raise TerminalSealError(f"{label} input must be bytes")
    return value


def _object(value: Any, label: str) -> dict[str, Any]:
    if type(value) is not dict:
        raise TerminalSealError(f"{label} must be an object")
    return cast(dict[str, Any], value)


def _list(value: Any, label: str) -> list[Any]:
    if type(value) is not list and type(value) is not tuple:
        raise TerminalSealError(f"{label} must be a list")
    return list(cast(list[Any] | tuple[Any, ...], value))


def _text(value: Any, label: str) -> str:
    if type(value) is not str or not value:
        raise TerminalSealError(f"{label} differs")
    return value
