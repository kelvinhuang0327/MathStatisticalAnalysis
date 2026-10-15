"""Synthetic terminal seal for the orbit successor. No official universe is scored."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from lottolab.research import b649_k20_four_ticket_orbit_manifest_r1 as orbit_manifest
from lottolab.research import b649_k20_orbit_successor_dispatcher_r1 as dispatcher
from lottolab.research import b649_k20_orbit_successor_terminal_seal_r1 as seal

ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = ROOT / dispatcher.MANIFEST_RELATIVE_PATH
EVALUATOR_PATH = ROOT / "src/lottolab/research/b649_official_any_prize_exact.py"
HISTORICAL_JOURNAL_PATH = orbit_manifest.BASE_RUN_ROOT / "attempt-results.jsonl"
FORBIDDEN = (
    "NO_STRICT_GAIN_IN_FROZEN_FOUR_TICKET_CYCLE_FAMILY",
    "GLOBAL_K20_OPTIMUM",
)


class MemoryJournal:
    def __init__(self) -> None:
        self.data = b""

    def read_bytes(self) -> bytes:
        return self.data

    def append_line(self, expected_previous: bytes, line: bytes) -> None:
        if self.data != expected_previous:
            raise dispatcher.DispatcherError("synthetic journal compare failed")
        self.data += line


class SyntheticInterruption(Exception):
    pass


def _independent_sha256(tickets: list[list[int]]) -> str:
    normalized = tuple(sorted(tuple(sorted(ticket)) for ticket in tickets))
    payload = orbit_manifest._compact_json_bytes([list(ticket) for ticket in normalized])
    return orbit_manifest._sha256(payload)


def _dummy_identity(representative: dispatcher.Representative) -> str:
    return hashlib.sha256(f"tie-{representative.index}".encode("ascii")).hexdigest()


def _evaluation(
    representative: dispatcher.Representative, count: int, identity: str
) -> dispatcher.RepresentativeEvaluation:
    return dispatcher.RepresentativeEvaluation(
        dispatcher.RAW_ATTEMPTS_PER_REPRESENTATIVE,
        (dispatcher.CandidateOutcome(count, identity),),
    )


def _dispatch(manifest_bytes: bytes, score: object) -> bytes:
    journal = MemoryJournal()
    dispatcher.run_dispatch(
        manifest_bytes,
        journal=journal,
        score_representative=score,  # type: ignore[arg-type]
    )
    return journal.data


def _prefix(manifest_bytes: bytes, plan: dispatcher.ManifestPlan, completed_count: int) -> bytes:
    stop_index = plan.representatives[completed_count].index

    def score(representative: dispatcher.Representative) -> dispatcher.RepresentativeEvaluation:
        if representative.index == stop_index:
            raise SyntheticInterruption
        return _evaluation(
            representative, dispatcher.BASELINE_COUNT, _dummy_identity(representative)
        )

    journal = MemoryJournal()
    with pytest.raises(SyntheticInterruption):
        dispatcher.run_dispatch(manifest_bytes, journal=journal, score_representative=score)
    return journal.data


@pytest.fixture(scope="module")
def manifest_bytes() -> bytes:
    return MANIFEST_PATH.read_bytes()


@pytest.fixture(scope="module")
def plan(manifest_bytes: bytes) -> dispatcher.ManifestPlan:
    return dispatcher.load_manifest_plan(manifest_bytes)


@pytest.fixture(scope="module")
def historical_journal() -> bytes:
    return HISTORICAL_JOURNAL_PATH.read_bytes()


@pytest.fixture(scope="module")
def evaluator_bytes() -> bytes:
    return EVALUATOR_PATH.read_bytes()


@pytest.fixture(scope="module")
def coverage_mapping(manifest_bytes: bytes) -> list[dict[str, object]]:
    return seal.certified_coverage_mapping(manifest_bytes)


@pytest.fixture(scope="module")
def baseline_tickets(manifest_bytes: bytes) -> list[list[int]]:
    document = json.loads(manifest_bytes)
    tickets = document["baseline"]["normalized_tickets"]
    assert _independent_sha256(tickets) == dispatcher.BASELINE_PORTFOLIO_SHA256
    return tickets


@pytest.fixture(scope="module")
def improvement_tickets(baseline_tickets: list[list[int]]) -> list[list[int]]:
    tickets = copy.deepcopy(baseline_tickets)
    replacement = [6, 4, 3, 2, 21, 1]
    assert tuple(sorted(replacement)) not in {tuple(ticket) for ticket in tickets}
    tickets[0] = replacement
    assert _independent_sha256(tickets) != dispatcher.BASELINE_PORTFOLIO_SHA256
    return tickets


@pytest.fixture(scope="module")
def no_gain_journal(manifest_bytes: bytes, improvement_tickets: list[list[int]]) -> bytes:
    identity = _independent_sha256(improvement_tickets)

    def score(representative: dispatcher.Representative) -> dispatcher.RepresentativeEvaluation:
        return _evaluation(representative, dispatcher.BASELINE_COUNT, identity)

    return _dispatch(manifest_bytes, score)


@pytest.fixture(scope="module")
def strict_journal(
    manifest_bytes: bytes,
    plan: dispatcher.ManifestPlan,
    improvement_tickets: list[list[int]],
) -> bytes:
    identity = _independent_sha256(improvement_tickets)
    first = plan.representatives[0].index

    def score(representative: dispatcher.Representative) -> dispatcher.RepresentativeEvaluation:
        if representative.index == first:
            return _evaluation(representative, dispatcher.STRICT_GAIN_MINIMUM_COUNT, identity)
        return _evaluation(
            representative, dispatcher.BASELINE_COUNT, _dummy_identity(representative)
        )

    return _dispatch(manifest_bytes, score)


def _seal(
    manifest_bytes: bytes,
    journal: bytes,
    historical_journal: bytes,
    tickets: object,
    coverage_mapping: object,
    evaluator_bytes: bytes,
    recount: object,
    *,
    disposition: str = seal.DISPOSITION_TERMINAL,
    source_commit: str = seal.BASE_COMMIT,
    source_tree: str = seal.BASE_TREE,
) -> dict[str, object]:
    return seal.seal_orbit_successor_terminal(
        manifest_bytes,
        journal,
        historical_journal,
        tickets,
        coverage_mapping,
        evaluator_bytes=evaluator_bytes,
        recount=recount,  # type: ignore[arg-type]
        run_disposition=disposition,
        source_commit=source_commit,
        source_tree=source_tree,
    )


def _replay_identity(manifest_bytes: bytes, journal: bytes) -> tuple[int, str]:
    plan = dispatcher.load_manifest_plan(manifest_bytes)
    state = dispatcher.validate_progress_prefix(journal, plan)
    return state.incumbent.official_count, state.incumbent.result_identity_sha256


def test_1_complete_records_produce_orbit_coverage_summary(
    manifest_bytes: bytes,
    no_gain_journal: bytes,
    historical_journal: bytes,
    baseline_tickets: list[list[int]],
    coverage_mapping: list[dict[str, object]],
    evaluator_bytes: bytes,
    plan: dispatcher.ManifestPlan,
) -> None:
    calls: list[int] = []

    def recount(_tickets: tuple[tuple[int, ...], ...]) -> int:
        calls.append(dispatcher.BASELINE_COUNT)
        return dispatcher.BASELINE_COUNT

    result = _seal(
        manifest_bytes,
        no_gain_journal,
        historical_journal,
        baseline_tickets,
        coverage_mapping,
        evaluator_bytes,
        recount,
    )
    accounting = result["orbit_accounting"]
    assert isinstance(accounting, dict)
    assert accounting["total_mathematical_orbits"] == 670
    assert accounting["historical_covered_orbits"] == 240
    assert accounting["new_covered_orbits"] == 430
    assert accounting["historical_directly_scored_quadruples"] == 623
    assert accounting["new_directly_scored_representatives"] == 430
    assert accounting["new_raw_attempts"] == 3_343_680
    assert accounting["mathematical_coverage_implies_direct_score"] is False
    assert (
        accounting["historical_directly_scored_quadruples"]
        != (accounting["historical_covered_orbits"])
    )
    journal_identity = result["journal_identity"]
    assert isinstance(journal_identity, dict)
    expected_indices = [item.index for item in plan.representatives]
    assert journal_identity["representative_indices"] == expected_indices
    assert journal_identity["representative_indices"] == sorted(expected_indices)
    assert len(set(journal_identity["representative_indices"])) == 430
    assert result["status"] == seal.STATUS_SEALED
    pins = result["source_pins"]
    assert isinstance(pins, dict)
    assert pins["repository"] == "kelvinhuang0327/MathStatisticalAnalysis"
    assert pins["base_commit"] == seal.BASE_COMMIT == "7aaa5c3bb8f2ab4d18ff946906f81a0c7f418f03"
    assert pins["base_tree"] == seal.BASE_TREE == "310449f1b1ee806215c326787dbffd60ad1c49e3"
    assert pins["manifest_sha256"] == dispatcher.EXPECTED_MANIFEST_SHA256
    assert pins["representative_tuples_sha256"] == dispatcher.EXPECTED_REPRESENTATIVE_TUPLES_SHA256
    assert pins["historical_journal_sha256"] == hashlib.sha256(historical_journal).hexdigest()
    assert pins["official_evaluator_sha256"] == hashlib.sha256(evaluator_bytes).hexdigest()
    journal_sha = hashlib.sha256(no_gain_journal).hexdigest()
    assert journal_identity["successor_journal_sha256"] == journal_sha
    assert calls == [dispatcher.BASELINE_COUNT]
    encoded = seal.canonical_result_bytes(result).decode("ascii")
    for claim in FORBIDDEN:
        assert claim not in encoded


def test_2_short_prefix_is_not_terminal_complete(
    manifest_bytes: bytes,
    plan: dispatcher.ManifestPlan,
    historical_journal: bytes,
    baseline_tickets: list[list[int]],
    coverage_mapping: list[dict[str, object]],
    evaluator_bytes: bytes,
    improvement_tickets: list[list[int]],
) -> None:
    journal = _prefix(manifest_bytes, plan, 429)

    def recount(_tickets: tuple[tuple[int, ...], ...]) -> int:
        raise AssertionError("recount called on an incomplete journal")

    result = _seal(
        manifest_bytes,
        journal,
        historical_journal,
        baseline_tickets,
        coverage_mapping,
        evaluator_bytes,
        recount,
    )
    assert result["status"] == "INCOMPLETE_DURABLE"
    assert result["completed_scientific_seal"] is False
    assert result["accepted_prefix_records"] == 429
    assert "result_sha256" not in result
    encoded = seal.canonical_result_bytes(result).decode("ascii")
    assert "NO_GAIN" not in encoded
    assert "STRICT_GAIN" not in encoded
    for claim in FORBIDDEN:
        assert claim not in encoded

    identity = _independent_sha256(improvement_tickets)
    first = plan.representatives[0].index

    def strict_then_stop(
        representative: dispatcher.Representative,
    ) -> dispatcher.RepresentativeEvaluation:
        if representative.index != first:
            raise SyntheticInterruption
        return _evaluation(representative, dispatcher.STRICT_GAIN_MINIMUM_COUNT, identity)

    partial_gain = MemoryJournal()
    with pytest.raises(SyntheticInterruption):
        dispatcher.run_dispatch(
            manifest_bytes, journal=partial_gain, score_representative=strict_then_stop
        )
    partial = _seal(
        manifest_bytes,
        partial_gain.data,
        historical_journal,
        improvement_tickets,
        coverage_mapping,
        evaluator_bytes,
        recount,
    )
    partial_text = seal.canonical_result_bytes(partial).decode("ascii")
    assert partial["status"] == "INCOMPLETE_DURABLE"
    assert "STRICT_GAIN" not in partial_text
    assert "NO_GAIN" not in partial_text


def test_3_duplicate_or_missing_representative_fails_closed(
    manifest_bytes: bytes,
    plan: dispatcher.ManifestPlan,
    historical_journal: bytes,
    baseline_tickets: list[list[int]],
    coverage_mapping: list[dict[str, object]],
    evaluator_bytes: bytes,
) -> None:
    prefix = _prefix(manifest_bytes, plan, 3)
    lines = prefix.splitlines(keepends=True)
    duplicate = lines[0] + lines[0] + lines[2]
    record = json.loads(lines[1])
    record["representative_index"] = plan.representatives[2].index
    record["quadruple"] = list(plan.representatives[2].quadruple)
    unsigned = {key: value for key, value in record.items() if key != "record_sha256"}
    record["record_sha256"] = dispatcher._sha256(dispatcher._canonical_json_bytes(unsigned))
    gap = lines[0] + dispatcher._canonical_json_bytes(record)

    def recount(_tickets: tuple[tuple[int, ...], ...]) -> int:
        raise AssertionError("recount called on a rejected journal")

    for journal in (duplicate, gap):
        with pytest.raises(seal.TerminalSealError, match="ordered manifest prefix"):
            _seal(
                manifest_bytes,
                journal,
                historical_journal,
                baseline_tickets,
                coverage_mapping,
                evaluator_bytes,
                recount,
            )


def test_4_baseline_count_classifies_no_gain(
    manifest_bytes: bytes,
    no_gain_journal: bytes,
    historical_journal: bytes,
    baseline_tickets: list[list[int]],
    coverage_mapping: list[dict[str, object]],
    evaluator_bytes: bytes,
) -> None:
    result = _seal(
        manifest_bytes,
        no_gain_journal,
        historical_journal,
        baseline_tickets,
        coverage_mapping,
        evaluator_bytes,
        lambda _tickets: dispatcher.BASELINE_COUNT,
    )
    assert result["exact_count"] == 313_263_888
    assert result["scientific_classification"] == "NO_GAIN"
    frozen = result["frozen_baseline"]
    launch = result["launch_time_incumbent"]
    portfolio = result["portfolio"]
    assert isinstance(frozen, dict)
    assert isinstance(launch, dict)
    assert isinstance(portfolio, dict)
    assert frozen["comparison"] == "NO_GAIN"
    assert launch["comparison"] == "INCUMBENT_RETAINED"
    assert launch["replaced"] is False
    assert launch["equal_count_replaces_incumbent"] is False
    assert portfolio["normalized_sha256"] == dispatcher.BASELINE_PORTFOLIO_SHA256
    assert portfolio["normalized_sha256"] == _independent_sha256(baseline_tickets)
    assert portfolio["tickets"] == baseline_tickets
    assert result["terminal_recount"] == {
        "interface": "injected_portfolio_count",
        "pinned_official_evaluator_sha256": dispatcher.EVALUATOR_SHA256,
        "official_evaluator_executed": False,
        "official_outcome_universe": 601_304_088,
        "official_universe_enumerated": False,
        "real_canonical_recount": "NOT RUN",
        "real_scientific_execution": "NOT RUN",
        "recount_count": 313_263_888,
        "journal_incumbent_count": 313_263_888,
    }


def test_5_minimum_strict_count_classifies_strict_gain(
    manifest_bytes: bytes,
    strict_journal: bytes,
    historical_journal: bytes,
    improvement_tickets: list[list[int]],
    coverage_mapping: list[dict[str, object]],
    evaluator_bytes: bytes,
) -> None:
    observed: list[tuple[tuple[int, ...], ...]] = []

    def recount(tickets: tuple[tuple[int, ...], ...]) -> int:
        observed.append(tickets)
        return dispatcher.STRICT_GAIN_MINIMUM_COUNT

    result = _seal(
        manifest_bytes,
        strict_journal,
        historical_journal,
        improvement_tickets,
        coverage_mapping,
        evaluator_bytes,
        recount,
    )
    assert result["exact_count"] == 313_263_889
    assert result["scientific_classification"] == "STRICT_GAIN"
    assert result["synthetic_result_is_not_a_discovered_higher_winning_count"] is True
    launch = result["launch_time_incumbent"]
    frozen = result["frozen_baseline"]
    assert isinstance(launch, dict)
    assert isinstance(frozen, dict)
    assert frozen["comparison"] == "STRICT_GAIN"
    assert launch["comparison"] == "INCUMBENT_REPLACED"
    assert launch["replaced"] is True
    normalized = tuple(sorted(tuple(sorted(ticket)) for ticket in improvement_tickets))
    assert observed == [normalized]
    recount_record = result["terminal_recount"]
    assert isinstance(recount_record, dict)
    assert recount_record["real_canonical_recount"] == "NOT RUN"
    assert recount_record["official_universe_enumerated"] is False


def test_6_equal_count_portfolio_does_not_replace_incumbent(
    manifest_bytes: bytes,
    no_gain_journal: bytes,
    historical_journal: bytes,
    baseline_tickets: list[list[int]],
    improvement_tickets: list[list[int]],
    coverage_mapping: list[dict[str, object]],
    evaluator_bytes: bytes,
) -> None:
    retained = _seal(
        manifest_bytes,
        no_gain_journal,
        historical_journal,
        baseline_tickets,
        coverage_mapping,
        evaluator_bytes,
        lambda _tickets: dispatcher.BASELINE_COUNT,
    )
    portfolio = retained["portfolio"]
    assert isinstance(portfolio, dict)
    assert portfolio["normalized_sha256"] == dispatcher.BASELINE_PORTFOLIO_SHA256
    records = [json.loads(line) for line in no_gain_journal.splitlines()]
    assert records[0]["representative_result"]["official_count"] == dispatcher.BASELINE_COUNT
    assert (
        records[0]["representative_result"]["result_identity_sha256"]
        != dispatcher.BASELINE_PORTFOLIO_SHA256
    )
    assert retained["launch_time_incumbent"]["replaced"] is False  # type: ignore[index]
    with pytest.raises(seal.TerminalSealError, match="replayed incumbent"):
        _seal(
            manifest_bytes,
            no_gain_journal,
            historical_journal,
            improvement_tickets,
            coverage_mapping,
            evaluator_bytes,
            lambda _tickets: dispatcher.BASELINE_COUNT,
        )


def test_7_strict_gain_identity_is_the_improvement_candidate(
    manifest_bytes: bytes,
    strict_journal: bytes,
    historical_journal: bytes,
    baseline_tickets: list[list[int]],
    improvement_tickets: list[list[int]],
    coverage_mapping: list[dict[str, object]],
    evaluator_bytes: bytes,
) -> None:
    replay_count, replay_identity = _replay_identity(manifest_bytes, strict_journal)
    expected = _independent_sha256(improvement_tickets)
    assert replay_count == 313_263_889
    assert replay_identity == expected
    assert expected != dispatcher.BASELINE_PORTFOLIO_SHA256
    result = _seal(
        manifest_bytes,
        strict_journal,
        historical_journal,
        list(reversed(improvement_tickets)),
        coverage_mapping,
        evaluator_bytes,
        lambda _tickets: 313_263_889,
    )
    portfolio = result["portfolio"]
    assert isinstance(portfolio, dict)
    assert portfolio["normalized_sha256"] == expected
    assert portfolio["normalized_sha256"] != dispatcher.BASELINE_PORTFOLIO_SHA256
    normalized_tickets = [
        list(ticket) for ticket in sorted(tuple(sorted(row)) for row in improvement_tickets)
    ]
    assert portfolio["tickets"] == normalized_tickets
    mutated = copy.deepcopy(improvement_tickets)
    mutated[1] = [1, 2, 3, 4, 5, 7]
    with pytest.raises(seal.TerminalSealError, match=r"replayed incumbent|improvement candidate"):
        _seal(
            manifest_bytes,
            strict_journal,
            historical_journal,
            mutated,
            coverage_mapping,
            evaluator_bytes,
            lambda _tickets: 313_263_889,
        )
    with pytest.raises(seal.TerminalSealError, match=r"replayed incumbent|improvement candidate"):
        _seal(
            manifest_bytes,
            strict_journal,
            historical_journal,
            baseline_tickets,
            coverage_mapping,
            evaluator_bytes,
            lambda _tickets: 313_263_889,
        )


def test_8_recount_mismatch_fails_closed(
    manifest_bytes: bytes,
    no_gain_journal: bytes,
    strict_journal: bytes,
    historical_journal: bytes,
    baseline_tickets: list[list[int]],
    improvement_tickets: list[list[int]],
    coverage_mapping: list[dict[str, object]],
    evaluator_bytes: bytes,
) -> None:
    with pytest.raises(seal.TerminalSealError, match="recount count differs"):
        _seal(
            manifest_bytes,
            no_gain_journal,
            historical_journal,
            baseline_tickets,
            coverage_mapping,
            evaluator_bytes,
            lambda _tickets: dispatcher.BASELINE_COUNT + 1,
        )
    with pytest.raises(seal.TerminalSealError, match="recount count differs"):
        _seal(
            manifest_bytes,
            strict_journal,
            historical_journal,
            improvement_tickets,
            coverage_mapping,
            evaluator_bytes,
            lambda _tickets: dispatcher.BASELINE_COUNT,
        )


def test_9_manifest_or_historical_digest_mismatch_fails_closed(
    manifest_bytes: bytes,
    no_gain_journal: bytes,
    historical_journal: bytes,
    baseline_tickets: list[list[int]],
    coverage_mapping: list[dict[str, object]],
    evaluator_bytes: bytes,
) -> None:
    altered_manifest = manifest_bytes.replace(b'"orbit_count":670', b'"orbit_count":671', 1)
    assert altered_manifest != manifest_bytes
    with pytest.raises(seal.TerminalSealError, match="manifest SHA-256 differs"):
        _seal(
            altered_manifest,
            no_gain_journal,
            historical_journal,
            baseline_tickets,
            coverage_mapping,
            evaluator_bytes,
            lambda _tickets: dispatcher.BASELINE_COUNT,
        )
    with pytest.raises(seal.TerminalSealError, match="historical journal SHA-256 differs"):
        _seal(
            manifest_bytes,
            no_gain_journal,
            historical_journal + b"\n",
            baseline_tickets,
            coverage_mapping,
            evaluator_bytes,
            lambda _tickets: dispatcher.BASELINE_COUNT,
        )


def test_10_tampered_coverage_mapping_fails_closed(
    manifest_bytes: bytes,
    no_gain_journal: bytes,
    historical_journal: bytes,
    baseline_tickets: list[list[int]],
    coverage_mapping: list[dict[str, object]],
    evaluator_bytes: bytes,
) -> None:
    tampered = copy.deepcopy(coverage_mapping)
    historical = next(
        row
        for row in tampered
        if row["mathematical_coverage"] == "HISTORICALLY_COVERED_BY_SYMMETRY"
    )
    historical["mathematical_coverage"] = "UNVISITED"
    with pytest.raises(seal.TerminalSealError, match="coverage mapping differs"):
        _seal(
            manifest_bytes,
            no_gain_journal,
            historical_journal,
            baseline_tickets,
            tampered,
            evaluator_bytes,
            lambda _tickets: dispatcher.BASELINE_COUNT,
        )


def test_interrupted_or_partial_disposition_stays_incomplete(
    manifest_bytes: bytes,
    no_gain_journal: bytes,
    historical_journal: bytes,
    baseline_tickets: list[list[int]],
    coverage_mapping: list[dict[str, object]],
    evaluator_bytes: bytes,
) -> None:
    def recount(_tickets: tuple[tuple[int, ...], ...]) -> int:
        raise AssertionError("recount called without a terminal acceptance")

    for disposition in (seal.DISPOSITION_INTERRUPTED, seal.DISPOSITION_PARTIAL):
        result = _seal(
            manifest_bytes,
            no_gain_journal,
            historical_journal,
            baseline_tickets,
            coverage_mapping,
            evaluator_bytes,
            recount,
            disposition=disposition,
        )
        encoded = seal.canonical_result_bytes(result).decode("ascii")
        assert result == {
            "schema": seal.RESULT_SCHEMA,
            "task_id": seal.TASK_ID,
            "status": "INCOMPLETE_DURABLE",
            "completed_scientific_seal": False,
            "run_disposition": disposition,
            "accepted_prefix_records": 430,
            "required_representative_records": 430,
            "gain_classification_emitted": False,
            "real_canonical_recount": "NOT RUN",
            "real_scientific_execution": "NOT RUN",
            "successor_journal_sha256": hashlib.sha256(no_gain_journal).hexdigest(),
        }
        assert "NO_GAIN" not in encoded
        for claim in FORBIDDEN:
            assert claim not in encoded


def test_corrupt_journal_fails_closed(
    manifest_bytes: bytes,
    no_gain_journal: bytes,
    historical_journal: bytes,
    baseline_tickets: list[list[int]],
    coverage_mapping: list[dict[str, object]],
    evaluator_bytes: bytes,
) -> None:
    corrupted = no_gain_journal.replace(b'"candidate_count":1', b'"candidate_count":2', 1)
    assert corrupted != no_gain_journal
    with pytest.raises(seal.TerminalSealError, match="SHA-256 differs"):
        _seal(
            manifest_bytes,
            corrupted,
            historical_journal,
            baseline_tickets,
            coverage_mapping,
            evaluator_bytes,
            lambda _tickets: dispatcher.BASELINE_COUNT,
        )
    with pytest.raises(seal.TerminalSealError, match="truncated final record"):
        _seal(
            manifest_bytes,
            no_gain_journal[:-1],
            historical_journal,
            baseline_tickets,
            coverage_mapping,
            evaluator_bytes,
            lambda _tickets: dispatcher.BASELINE_COUNT,
        )


def test_result_sha256_is_deterministic(
    manifest_bytes: bytes,
    strict_journal: bytes,
    historical_journal: bytes,
    improvement_tickets: list[list[int]],
    coverage_mapping: list[dict[str, object]],
    evaluator_bytes: bytes,
) -> None:
    kwargs = {
        "manifest": manifest_bytes,
        "journal": strict_journal,
    }

    def recount(_tickets: tuple[tuple[int, ...], ...]) -> int:
        return 313_263_889

    first = _seal(
        kwargs["manifest"],
        kwargs["journal"],
        historical_journal,
        improvement_tickets,
        coverage_mapping,
        evaluator_bytes,
        recount,
    )
    second = _seal(
        kwargs["manifest"],
        kwargs["journal"],
        historical_journal,
        improvement_tickets,
        coverage_mapping,
        evaluator_bytes,
        recount,
    )
    assert first == second
    assert isinstance(first["result_sha256"], str)
    assert len(first["result_sha256"]) == 64
    unsigned = {key: value for key, value in first.items() if key != "result_sha256"}
    digest = hashlib.sha256(seal.canonical_result_bytes(unsigned)).hexdigest()
    assert digest == first["result_sha256"]
    assert seal.canonical_result_bytes(first) == seal.canonical_result_bytes(second)


def test_source_and_portfolio_pins_fail_closed(
    manifest_bytes: bytes,
    no_gain_journal: bytes,
    historical_journal: bytes,
    baseline_tickets: list[list[int]],
    coverage_mapping: list[dict[str, object]],
    evaluator_bytes: bytes,
) -> None:
    assert hashlib.sha256(historical_journal).hexdigest() == dispatcher.HISTORICAL_JOURNAL_SHA256
    assert hashlib.sha256(evaluator_bytes).hexdigest() == dispatcher.EVALUATOR_SHA256
    assert hashlib.sha256(manifest_bytes).hexdigest() == dispatcher.EXPECTED_MANIFEST_SHA256
    common = (
        manifest_bytes,
        no_gain_journal,
        historical_journal,
        baseline_tickets,
        coverage_mapping,
        evaluator_bytes,
    )
    with pytest.raises(seal.TerminalSealError, match="source identity differs"):
        _seal(*common, lambda _tickets: dispatcher.BASELINE_COUNT, source_commit="0" * 40)
    with pytest.raises(seal.TerminalSealError, match="official evaluator SHA-256 differs"):
        _seal(
            manifest_bytes,
            no_gain_journal,
            historical_journal,
            baseline_tickets,
            coverage_mapping,
            evaluator_bytes + b"x",
            lambda _tickets: dispatcher.BASELINE_COUNT,
        )
    duplicate = copy.deepcopy(baseline_tickets)
    duplicate[1] = list(duplicate[0])
    with pytest.raises(seal.TerminalSealError, match="duplicate tickets"):
        _seal(
            manifest_bytes,
            no_gain_journal,
            historical_journal,
            duplicate,
            coverage_mapping,
            evaluator_bytes,
            lambda _tickets: dispatcher.BASELINE_COUNT,
        )
    illegal = copy.deepcopy(baseline_tickets)
    illegal[0] = [1, 2, 3, 4, 5, 50]
    with pytest.raises(seal.TerminalSealError, match=r"1\.\.49"):
        _seal(
            manifest_bytes,
            no_gain_journal,
            historical_journal,
            illegal,
            coverage_mapping,
            evaluator_bytes,
            lambda _tickets: dispatcher.BASELINE_COUNT,
        )
    module_source = Path(seal.__file__).read_text(encoding="utf-8")
    assert "official_any_prize_outcome_count" not in module_source
    assert "all_main_draw_masks" not in module_source


def test_above_minimum_count_is_strict_gain_and_not_baseline_identity(
    manifest_bytes: bytes,
    plan: dispatcher.ManifestPlan,
    historical_journal: bytes,
    improvement_tickets: list[list[int]],
    coverage_mapping: list[dict[str, object]],
    evaluator_bytes: bytes,
) -> None:
    identity = _independent_sha256(improvement_tickets)
    count = dispatcher.STRICT_GAIN_MINIMUM_COUNT + 5

    def score(representative: dispatcher.Representative) -> dispatcher.RepresentativeEvaluation:
        if representative.index == plan.representatives[0].index:
            return _evaluation(representative, count, identity)
        return _evaluation(
            representative, dispatcher.BASELINE_COUNT, _dummy_identity(representative)
        )

    journal = _dispatch(manifest_bytes, score)
    result = _seal(
        manifest_bytes,
        journal,
        historical_journal,
        improvement_tickets,
        coverage_mapping,
        evaluator_bytes,
        lambda _tickets: count,
    )
    portfolio = result["portfolio"]
    assert isinstance(portfolio, dict)
    assert result["scientific_classification"] == "STRICT_GAIN"
    assert result["exact_count"] == count
    assert portfolio["normalized_sha256"] == identity
    assert portfolio["normalized_sha256"] != dispatcher.BASELINE_PORTFOLIO_SHA256
    recount_record = result["terminal_recount"]
    assert isinstance(recount_record, dict)
    assert recount_record["real_canonical_recount"] == "NOT RUN"
    assert recount_record["real_scientific_execution"] == "NOT RUN"
