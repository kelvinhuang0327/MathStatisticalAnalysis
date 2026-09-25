# pyright: reportPrivateUsage=false
from __future__ import annotations

import ast
import itertools
import json
import math
import random
import sys
from collections import Counter
from dataclasses import fields
from decimal import Decimal, localcontext
from fractions import Fraction
from pathlib import Path

import numpy as np
import pytest

from lottolab.research import (
    b649_k20_bonferroni_filtered_exhaustive_2ticket_cross_swap_r1 as bonferroni,
)
from lottolab.research import (
    b649_k20_filmus_ward_nonoblivious_r1 as filmus_ward,
)
from lottolab.research.b649_k20_bonferroni_filtered_exhaustive_2ticket_cross_swap_runner import (
    load_and_verify_pinned_incumbent,
)
from lottolab.research.b649_k20_filmus_ward_nonoblivious_r1 import (
    BASE_HEAD,
    HISTOGRAM_CHUNK_SIZE,
    INCUMBENT_PATH,
    INCUMBENT_SHA256,
    MAX_ACCEPTED_SEARCH_MOVES,
    MAX_CANONICAL_EXACT_CALLS,
    MAX_DISTINCT_PROPOSAL_EVALUATIONS,
    MAX_MARGINAL_HISTOGRAM_EVALUATIONS,
    RAW_PROPOSALS_PER_ROUND,
    REQUIRED_PYTHON,
    ROUNDS,
    SEED,
    TOTAL_OFFICIAL_OUTCOMES,
    CandidateEvaluation,
    ExperimentTimeout,
    IncompleteRun,
    RunSummary,
    _accounting_is_within_budget,
    _bonferroni_coefficients,
    _candidate_exact_score_required,
    _canonical_state,
    _certified_e_bounds,
    _check_deadline,
    _claim_candidate_identity,
    _claim_canonical_exact_call,
    _claim_marginal_histogram_evaluation,
    _classify_replacement,
    _compare_certified_a_e_minus_b,
    _coverage_counts_by_colex_rank,
    _evaluate_candidate_components,
    _final_decision,
    _generate_raw_batch,
    _marginal_histogram,
    _potential_difference_pair,
    _random_state_json,
    _select_best_positive_candidate,
    _strict_champion_update,
    _winning_w_count,
)

REPOSITORY = Path(__file__).resolve().parents[2]


def _legal_k20() -> tuple[tuple[int, ...], ...]:
    return tuple(tuple(range(start, start + 6)) for start in range(1, 21))


def _candidate(
    portfolio: tuple[tuple[int, ...], ...],
    *,
    pair: tuple[int, int],
    sign: int,
    u3: int = 0,
    exact: int | None = None,
) -> CandidateEvaluation:
    return CandidateEvaluation(
        portfolio=portfolio,
        portfolio_sha256=bonferroni.portfolio_sha256(portfolio),
        potential_a=pair[0],
        potential_b=pair[1],
        potential_sign=sign,
        u3_outcome_count=u3,
        exact_outcome_count=exact,
        exact_fraction=None,
        raw_record={},
    )


def _official_ticket_wins(
    ticket: tuple[int, ...], main_draw: tuple[int, ...], special: int
) -> bool:
    main_hits = len(set(ticket).intersection(main_draw))
    return main_hits >= 3 or (main_hits == 2 and special in ticket)


def _coverage_ticket_wins(ticket: tuple[int, ...], w_set: tuple[int, ...]) -> bool:
    return len(set(ticket).intersection(w_set)) >= 3


def _seed_64921_config() -> filmus_ward.ExecutionConfig:
    return filmus_ward._resolve_execution_config(
        seed=64_921,
        task_id="B649_K20_FILMUS_WARD_NONOBLIVIOUS_S64921",
        execution_id="RUN1_S64921",
        preregistration_path=(
            "docs/research/matrix-native-results/"
            "b649-k20-filmus-ward-nonoblivious-s64921-preregistration.json"
        ),
        task_runtime_root=(
            ".task-data/B649_K20_FILMUS_WARD_NONOBLIVIOUS_S64921/run1"
        ),
        result_path=(
            "docs/research/matrix-native-results/"
            "b649-k20-filmus-ward-nonoblivious-s64921-result.json"
        ),
        report_path=(
            "docs/research/matrix-native-results/"
            "b649-k20-filmus-ward-nonoblivious-s64921-report.md"
        ),
        expected_seal_head="a" * 40,
        expected_seal_tree="b" * 40,
    )


def test_execution_config_defaults_preserve_r1_identity() -> None:
    config = filmus_ward._resolve_execution_config()
    assert config == filmus_ward.ExecutionConfig()
    assert config.compatibility_mode
    assert filmus_ward._resolve_execution_config(compatibility=True) == config
    assert filmus_ward._execution_config_payload(config) == {
        "compatibility_mode": True,
        "seed": 64_920,
        "task_id": filmus_ward.TASK_ID,
        "run_id": "RUN1",
        "execution_id": "RUN1",
        "preregistration_path": filmus_ward.PREREGISTRATION_PATH,
        "task_runtime_root": filmus_ward.EVIDENCE_RELATIVE_PATH,
        "result_path": filmus_ward.RESULT_PATH,
        "report_path": filmus_ward.REPORT_PATH,
        "expected_seal_head": None,
        "expected_seal_tree": None,
    }


def test_execution_config_contains_only_seed_and_identity_fields() -> None:
    config_64920 = filmus_ward.ExecutionConfig()
    config_64921 = _seed_64921_config()
    assert {field.name for field in fields(filmus_ward.ExecutionConfig)} == {
        "seed",
        "task_id",
        "execution_id",
        "preregistration_path",
        "task_runtime_root",
        "result_path",
        "report_path",
        "expected_seal_head",
        "expected_seal_tree",
    }
    assert config_64920.compatibility_mode
    assert not config_64921.compatibility_mode


def test_config_resolution_does_not_construct_or_consume_rng(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    constructed_seeds: list[int] = []
    original_random = random.Random

    class RecordingRandom(original_random):
        def __init__(self, seed: int) -> None:
            constructed_seeds.append(seed)
            super().__init__(seed)

    monkeypatch.setattr(filmus_ward.random, "Random", RecordingRandom)
    assert filmus_ward._resolve_execution_config().seed == 64_920
    assert _seed_64921_config().seed == 64_921
    assert constructed_seeds == []


def test_explicit_seed_64921_routes_to_one_dedicated_random(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected_state = random.Random(64_921).getstate()
    constructed_seeds: list[int] = []
    original_random = random.Random

    class RecordingRandom(original_random):
        def __init__(self, seed: int) -> None:
            constructed_seeds.append(seed)
            super().__init__(seed)

    monkeypatch.setattr(filmus_ward.random, "Random", RecordingRandom)
    rng = filmus_ward._new_search_rng(_seed_64921_config())
    assert constructed_seeds == [64_921]
    assert rng.getstate() == expected_state


def test_parameterized_identity_routes_to_payloads_and_report() -> None:
    config = _seed_64921_config()
    payload = filmus_ward._execution_config_payload(config)
    summary_payload = filmus_ward._summary_payload(RunSummary(), config)
    report = filmus_ward._report_text(RunSummary(), config)
    assert payload["task_id"] == "B649_K20_FILMUS_WARD_NONOBLIVIOUS_S64921"
    assert payload["execution_id"] == "RUN1_S64921"
    assert payload["preregistration_path"] == config.preregistration_path
    assert payload["task_runtime_root"] == config.task_runtime_root
    assert payload["result_path"] == config.result_path
    assert payload["report_path"] == config.report_path
    assert payload["expected_seal_head"] == "a" * 40
    assert payload["expected_seal_tree"] == "b" * 40
    assert summary_payload["task_id"] == config.task_id
    assert summary_payload["run_id"] == config.execution_id
    assert summary_payload["execution_id"] == config.execution_id
    assert summary_payload["seed"] == 64_921
    assert "Task / execution:** B649_K20_FILMUS_WARD_NONOBLIVIOUS_S64921 / RUN1_S64921" in report
    assert "Seed / interpreter:** 64921 / CPython 3.13.8" in report
    assert f"{config.task_runtime_root}/provenance.json" in report


def test_preregistration_identity_and_seed_must_match_execution_config() -> None:
    compatibility_preregistration = json.loads(
        (REPOSITORY / filmus_ward.PREREGISTRATION_PATH).read_text(encoding="utf-8")
    )
    filmus_ward._validate_preregistration_payload(
        compatibility_preregistration, filmus_ward.ExecutionConfig()
    )

    config = _seed_64921_config()
    future_preregistration = {
        "task_id": config.task_id,
        "run_id": config.execution_id,
        "rng_and_proposals": {
            "rng": "one dedicated random.Random(64921) search RNG"
        },
    }
    filmus_ward._validate_preregistration_payload(future_preregistration, config)
    with pytest.raises(IncompleteRun, match="task_id"):
        filmus_ward._validate_preregistration_payload(
            compatibility_preregistration, config
        )


def test_invalid_or_conflicting_execution_identity_fails_closed() -> None:
    with pytest.raises(ValueError, match="distinct value"):
        filmus_ward._resolve_execution_config(seed=64_921)
    with pytest.raises(ValueError, match="supplied together"):
        filmus_ward._resolve_execution_config(
            seed=64_921,
            task_id="B649_K20_FILMUS_WARD_NONOBLIVIOUS_S64921",
            execution_id="RUN1_S64921",
            preregistration_path=(
                "docs/research/matrix-native-results/future-preregistration.json"
            ),
            task_runtime_root=".task-data/future/run1",
            result_path="docs/research/matrix-native-results/future-result.json",
            report_path="docs/research/matrix-native-results/future-report.md",
            expected_seal_head="a" * 40,
        )
    with pytest.raises(ValueError, match="compatibility mode"):
        filmus_ward._resolve_execution_config(seed=64_921, compatibility=True)


def test_r1_outputs_are_not_reused_by_a_new_execution_configuration() -> None:
    protected_hashes = {
        path: filmus_ward._sha256_file(REPOSITORY / path)
        for path in (filmus_ward.RESULT_PATH, filmus_ward.REPORT_PATH)
    }
    with pytest.raises(ValueError, match="R1 preregistration/result/report path"):
        filmus_ward._resolve_execution_config(
            seed=64_921,
            task_id="B649_K20_FILMUS_WARD_NONOBLIVIOUS_S64921",
            execution_id="RUN1_S64921",
            preregistration_path=(
                "docs/research/matrix-native-results/"
                "b649-k20-filmus-ward-nonoblivious-s64921-preregistration.json"
            ),
            task_runtime_root=".task-data/B649_K20_FILMUS_WARD_NONOBLIVIOUS_S64921/run1",
            result_path=filmus_ward.REPORT_PATH,
            report_path="docs/research/matrix-native-results/future-report.md",
            expected_seal_head="a" * 40,
            expected_seal_tree="b" * 40,
        )
    assert protected_hashes == {
        path: filmus_ward._sha256_file(REPOSITORY / path)
        for path in (filmus_ward.RESULT_PATH, filmus_ward.REPORT_PATH)
    }


def test_seed_64921_config_resolution_is_dry(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config = _seed_64921_config()

    def fail_if_search_starts(
        repository: Path,
        deadline: float,
        summary: RunSummary,
        execution_config: filmus_ward.ExecutionConfig,
    ) -> None:
        pytest.fail("config resolution must not start scientific search")

    monkeypatch.setattr(filmus_ward, "_run_search", fail_if_search_starts)
    result = REPOSITORY / config.result_path
    report = REPOSITORY / config.report_path
    runtime = REPOSITORY / config.task_runtime_root
    assert not result.exists()
    assert not report.exists()
    assert not runtime.exists()

    exit_code = filmus_ward.main(
        [
            "--resolve-config",
            "--seed",
            str(config.seed),
            "--task-id",
            config.task_id,
            "--execution-id",
            config.execution_id,
            "--preregistration-path",
            config.preregistration_path,
            "--task-runtime-root",
            config.task_runtime_root,
            "--result-path",
            config.result_path,
            "--report-path",
            config.report_path,
            "--expected-seal-head",
            config.expected_seal_head or "",
            "--expected-seal-tree",
            config.expected_seal_tree or "",
        ]
    )
    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert output == filmus_ward._execution_config_payload(config)
    assert not result.exists()
    assert not report.exists()
    assert not runtime.exists()


def test_pinned_incumbent_identity_and_exact_score() -> None:
    validated = load_and_verify_pinned_incumbent(
        REPOSITORY,
        source_commit=BASE_HEAD,
        source_path=INCUMBENT_PATH,
        artifact_sha256=INCUMBENT_SHA256,
    )
    assert validated.artifact_blob == (
        "a5bc9a73d5c31cf44a4c79cafb69b0af3d9fc5d5"
    )
    assert validated.artifact_sha256 == (
        "5a2839db8fe5cd38f03366968cc6a024a5aa378ab360d4d049b9b45baa8e84df"
    )
    assert validated.incumbent.portfolio_sha256 == (
        "4343a4aa699050f71d5913d26d59b138d637c8aad3528111d9bcf6d69593546b"
    )
    assert validated.exact.official_any_prize_outcome_count == 312_867_226
    assert str(validated.exact.official_any_prize) == "519713/998844"
    assert validated.exact.main_draw_count * validated.exact.special_count == (
        TOTAL_OFFICIAL_OUTCOMES
    )


def test_k20_normalization_preserves_only_legal_set_invariants() -> None:
    portfolio = _legal_k20()
    reversed_portfolio = tuple(
        tuple(reversed(ticket)) for ticket in reversed(portfolio)
    )
    normalized = _canonical_state(reversed_portfolio)
    assert len(normalized) == 20
    assert normalized == portfolio
    assert len(set(normalized)) == 20
    assert all(len(ticket) == 6 and len(set(ticket)) == 6 for ticket in normalized)
    assert all(1 <= number <= 49 for ticket in normalized for number in ticket)
    assert bonferroni.normalize_portfolio(portfolio) == normalized


def test_official_outcomes_reduce_to_seven_number_coverage() -> None:
    pool_size = 8
    draw_size = 4
    tickets = ((1, 2, 3, 4), (2, 3, 5, 6), (1, 5, 7, 8))
    main_draws = tuple(itertools.combinations(range(1, pool_size + 1), draw_size))
    outcome_w_counts: Counter[frozenset[int]] = Counter()
    official_union_count = 0
    for main_draw in main_draws:
        for special in set(range(1, pool_size + 1)) - set(main_draw):
            w_set = frozenset((*main_draw, special))
            outcome_w_counts[w_set] += 1
            official_union_count += any(
                _official_ticket_wins(ticket, main_draw, special)
                for ticket in tickets
            )

    coverage_union_count = sum(
        draw_size + 1
        for w_set in itertools.combinations(range(1, pool_size + 1), draw_size + 1)
        if any(_coverage_ticket_wins(ticket, w_set) for ticket in tickets)
    )
    assert set(outcome_w_counts.values()) == {draw_size + 1}
    assert len(outcome_w_counts) == math.comb(pool_size, draw_size + 1)
    assert official_union_count == coverage_union_count
    assert official_union_count <= TOTAL_OFFICIAL_OUTCOMES
    assert _winning_w_count(6, 49, 7, 3) == 2_658_776


def test_small_universe_marginals_match_direct_histograms_above_multiplicity_three() -> None:
    pool_size = 8
    w_size = 5
    portfolio = tuple(itertools.combinations(range(1, 6), 4))
    removed_ticket = portfolio[0]
    added_ticket = (5, 6, 7, 8)
    coverage = _coverage_counts_by_colex_rank(
        portfolio,
        pool_size=pool_size,
        w_size=w_size,
        minimum_hits=3,
        chunk_size=7,
    )
    assert coverage.dtype == np.uint8
    assert coverage.size == math.comb(pool_size, w_size)

    def direct_histogram(measured_ticket: tuple[int, ...]) -> list[int]:
        counts = [0] * len(portfolio)
        residual_portfolio = tuple(
            ticket for ticket in portfolio if ticket != removed_ticket
        )
        for w_set in itertools.combinations(range(1, pool_size + 1), w_size):
            if len(set(measured_ticket).intersection(w_set)) < 3:
                continue
            multiplicity = sum(
                len(set(ticket).intersection(w_set)) >= 3
                for ticket in residual_portfolio
            )
            counts[multiplicity] += 1
        return counts

    removed_histogram = _marginal_histogram(
        coverage,
        removed_ticket=removed_ticket,
        measured_ticket=removed_ticket,
        portfolio_size=len(portfolio),
        pool_size=pool_size,
        w_size=w_size,
        minimum_hits=3,
        chunk_size=7,
    )
    added_histogram = _marginal_histogram(
        coverage,
        removed_ticket=removed_ticket,
        measured_ticket=added_ticket,
        portfolio_size=len(portfolio),
        pool_size=pool_size,
        w_size=w_size,
        minimum_hits=3,
        chunk_size=7,
    )
    assert removed_histogram.tolist() == direct_histogram(removed_ticket)
    assert added_histogram.tolist() == direct_histogram(added_ticket)
    assert removed_histogram[4] >= 1
    assert removed_histogram.size == 5


def test_coverage_storage_is_the_chunked_seven_set_universe() -> None:
    module_path = REPOSITORY / (
        "src/lottolab/research/b649_k20_filmus_ward_nonoblivious_r1.py"
    )
    module = ast.parse(module_path.read_text(encoding="utf-8"))
    function = next(
        node
        for node in module.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "_coverage_counts_by_colex_rank"
    )
    referenced_names = {
        node.id for node in ast.walk(function) if isinstance(node, ast.Name)
    }
    assert "TOTAL_OFFICIAL_OUTCOMES" not in referenced_names
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "itertools"
        and node.func.attr == "combinations"
        for node in ast.walk(function)
    )
    assert HISTOGRAM_CHUNK_SIZE == 65_536


def test_filmus_ward_integer_coefficients_match_the_frozen_formula() -> None:
    assert _bonferroni_coefficients(4) == (1, 2, 5, 16, 65)
    assert _potential_difference_pair(
        added_histogram=np.array([0, 0, 0, 0, 10]),
        removed_histogram=np.zeros(5, dtype=int),
    ) == (1_680, 4_550)


@pytest.mark.parametrize(
    ("coefficient_a", "coefficient_b"),
    ((1, 2), (1, 3), (-7, -20), (13, 30), (0, 0), (0, 4), (0, -4)),
)
def test_certified_sign_agrees_with_high_precision_reference(
    coefficient_a: int, coefficient_b: int
) -> None:
    with localcontext() as context:
        context.prec = 100
        reference = (
            Decimal(coefficient_a) * Decimal(1).exp() - Decimal(coefficient_b)
        )
    expected = (reference > 0) - (reference < 0)
    assert _compare_certified_a_e_minus_b(coefficient_a, coefficient_b) == expected


def test_certified_comparison_escalates_from_n64_to_n128(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []
    original = _certified_e_bounds

    def observed_bounds(order: int) -> tuple[Fraction, Fraction]:
        calls.append(order)
        return original(order)

    monkeypatch.setattr(
        "lottolab.research.b649_k20_filmus_ward_nonoblivious_r1._certified_e_bounds",
        observed_bounds,
    )
    lower_64, _ = original(64)
    coefficient_a = 128 * math.factorial(64)
    coefficient_b = int(coefficient_a * lower_64) + 1
    assert _compare_certified_a_e_minus_b(coefficient_a, coefficient_b) == 1
    assert calls == [64, 128]


def test_unresolved_n128_comparison_is_not_given_a_tolerance_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[int] = []
    original = _certified_e_bounds

    def observed_bounds(order: int) -> tuple[Fraction, Fraction]:
        calls.append(order)
        return original(order)

    monkeypatch.setattr(
        "lottolab.research.b649_k20_filmus_ward_nonoblivious_r1._certified_e_bounds",
        observed_bounds,
    )
    lower_128, _ = original(128)
    coefficient_a = 256 * math.factorial(128)
    coefficient_b = int(coefficient_a * lower_128) + 1
    assert _compare_certified_a_e_minus_b(coefficient_a, coefficient_b) is None
    assert calls == [64, 128]
    assert _final_decision("BOUNDED_INCOMPLETE", 312_867_226, 312_867_226) == (
        "BOUNDED_INCOMPLETE"
    )


def test_proposal_order_and_rng_replay_under_required_cpython() -> None:
    assert sys.implementation.name == "cpython"
    assert sys.version_info[:3] == REQUIRED_PYTHON == (3, 13, 8)
    assert SEED == 64_920
    portfolio = _legal_k20()
    rng = filmus_ward._new_search_rng(filmus_ward.ExecutionConfig())
    replay_rng = random.Random(SEED)
    generated_slots: list[int] = []
    proposals = _generate_raw_batch(
        rng, portfolio, on_generated=lambda proposal: generated_slots.append(proposal.slot)
    )
    assert len(proposals) == RAW_PROPOSALS_PER_ROUND == 32
    assert generated_slots == list(range(32))

    expected: list[tuple[object, ...]] = []
    for slot in range(32):
        state_before = _random_state_json(replay_rng)
        ticket_index = replay_rng.randrange(20)
        old_ticket = portfolio[ticket_index]
        old_set = set(old_ticket)
        if slot < 16:
            removed = tuple(replay_rng.sample(sorted(old_ticket), 1))
            complement = [number for number in range(1, 50) if number not in old_set]
            added = tuple(replay_rng.sample(complement, 1))
            sample_order = removed + added
        elif slot < 24:
            removed = tuple(replay_rng.sample(sorted(old_ticket), 2))
            complement = [number for number in range(1, 50) if number not in old_set]
            added = tuple(replay_rng.sample(complement, 2))
            sample_order = removed + added
        else:
            sample_order = tuple(replay_rng.sample(list(range(1, 50)), 6))
            removed = old_ticket
            added = sample_order
        new_ticket = tuple(sorted((old_set - set(removed)) | set(added)))
        expected.append(
            (
                slot,
                ticket_index,
                old_ticket,
                removed,
                added,
                sample_order,
                new_ticket,
                state_before,
                _random_state_json(replay_rng),
            )
        )

    assert [
        (
            item.slot,
            item.ticket_index,
            item.old_ticket,
            item.removed_sample,
            item.added_sample,
            item.sample_order,
            item.new_ticket,
            item.rng_state_before,
            item.rng_state_after,
        )
        for item in proposals
    ] == expected
    assert rng.getstate() == replay_rng.getstate()


def test_noop_duplicate_and_repeated_candidate_consume_existing_slots() -> None:
    portfolio = _legal_k20()
    first_disposition, first = _classify_replacement(portfolio, 0, portfolio[0])
    duplicate_disposition, duplicate = _classify_replacement(
        portfolio, 0, portfolio[1]
    )
    unique_ticket = (30, 31, 32, 33, 34, 35)
    unique_disposition, candidate = _classify_replacement(
        portfolio, 0, unique_ticket
    )
    repeated_disposition, repeated = _classify_replacement(
        portfolio, 0, unique_ticket
    )
    assert (first_disposition, first) == ("NO_OP", None)
    assert (duplicate_disposition, duplicate) == ("DUPLICATE_TICKET", None)
    assert unique_disposition == "UNIQUE_CANDIDATE_PENDING"
    assert candidate is not None
    assert repeated_disposition == "UNIQUE_CANDIDATE_PENDING"
    assert repeated == candidate
    seen: dict[tuple[tuple[int, ...], ...], int] = {}
    assert _claim_candidate_identity(candidate, 3, seen) == ("FIRST_CANDIDATE", None)
    assert _claim_candidate_identity(candidate, 9, seen) == ("REPEATED_CANDIDATE", 3)

    generated_slots: list[int] = []
    batch = _generate_raw_batch(
        random.Random(SEED),
        portfolio,
        on_generated=lambda proposal: generated_slots.append(proposal.slot),
    )
    assert len(batch) == 32
    assert generated_slots == list(range(32))


def test_u3_screen_never_suppresses_potential_and_safe_candidate_can_move() -> None:
    calls: list[str] = []

    def exact_score() -> int:
        calls.append("exact")
        return 9

    def potential() -> tuple[int, int]:
        calls.append("potential")
        return (1, 2)

    exact, pair, disposition = _evaluate_candidate_components(
        u3_outcome_count=100,
        champion_outcome_count=100,
        exact_score=exact_score,
        potential_pair=potential,
    )
    assert (exact, pair, disposition) == (None, (1, 2), "SAFE_EXCLUDED")
    assert calls == ["potential"]

    calls.clear()
    exact, pair, disposition = _evaluate_candidate_components(
        u3_outcome_count=101,
        champion_outcome_count=100,
        exact_score=exact_score,
        potential_pair=potential,
    )
    assert (exact, pair, disposition) == (9, (1, 2), "CANONICAL_EXACT_REQUIRED")
    assert calls == ["exact", "potential"]

    origin = _legal_k20()
    candidate = _canonical_state((*origin[:-1], (30, 31, 32, 33, 34, 35)))
    positive = _candidate(candidate, pair=(1, 2), sign=1, u3=100, exact=None)
    assert _select_best_positive_candidate([positive]) is positive
    assert _candidate_exact_score_required(100, 100, selected_search_move=True)
    assert not _candidate_exact_score_required(
        100, 100, selected_search_move=True, already_scored=True
    )


def test_exact_champion_updates_are_independent_of_surrogate_move_selection() -> None:
    origin = _legal_k20()
    objective_winner = _canonical_state((*origin[:-1], (30, 31, 32, 33, 34, 35)))
    search_move = _canonical_state((*origin[:-1], (31, 32, 33, 34, 35, 36)))

    champion, count, updated = _strict_champion_update(
        origin, 100, objective_winner, 105
    )
    assert (champion, count, updated) == (objective_winner, 105, True)

    selected = _select_best_positive_candidate(
        [
            _candidate(objective_winner, pair=(1, 3), sign=-1, exact=105),
            _candidate(search_move, pair=(1, 2), sign=1, exact=90),
        ]
    )
    assert selected is not None
    assert selected.portfolio == search_move
    assert selected.exact_outcome_count == 90
    assert selected.exact_outcome_count < 100
    assert champion == objective_winner
    assert count == 105

    for exact_count in (None, 99, 100):
        retained, retained_count, changed = _strict_champion_update(
            origin, 100, search_move, exact_count
        )
        assert (retained, retained_count, changed) == (origin, 100, False)


def test_exact_score_trigger_coverage_and_budget_statuses() -> None:
    assert not _candidate_exact_score_required(100, 100)
    assert _candidate_exact_score_required(101, 100)
    assert _candidate_exact_score_required(
        100, 100, selected_search_move=True
    )
    assert not _candidate_exact_score_required(
        101, 100, selected_search_move=True, already_scored=True
    )
    assert _accounting_is_within_budget(
        raw_proposals=ROUNDS * RAW_PROPOSALS_PER_ROUND,
        distinct_proposals=MAX_DISTINCT_PROPOSAL_EVALUATIONS,
        accepted_moves=MAX_ACCEPTED_SEARCH_MOVES,
        marginal_evaluations=MAX_MARGINAL_HISTOGRAM_EVALUATIONS,
        exact_calls=MAX_CANONICAL_EXACT_CALLS,
    )
    assert not _accounting_is_within_budget(
        raw_proposals=ROUNDS * RAW_PROPOSALS_PER_ROUND + 1,
        distinct_proposals=0,
        accepted_moves=0,
        marginal_evaluations=0,
        exact_calls=0,
    )
    assert _final_decision("COMPLETE", 100, 101) == "STRICT_IMPROVEMENT_FOUND"
    assert _final_decision("COMPLETE", 100, 100) == "DIRECT_OBJECTIVE_BOUNDED_NEGATIVE"
    assert _final_decision("BOUNDED_INCOMPLETE", 100, 100) == "BOUNDED_INCOMPLETE"
    with pytest.raises(ExperimentTimeout):
        _check_deadline(10.0, now=10.0)


def test_exact_and_marginal_calls_are_reserved_before_work() -> None:
    exact_summary = RunSummary(canonical_exact_call_count=MAX_CANONICAL_EXACT_CALLS - 1)
    _claim_canonical_exact_call(exact_summary, "SELECTED_SEARCH_MOVE")
    assert exact_summary.canonical_exact_call_count == MAX_CANONICAL_EXACT_CALLS
    assert exact_summary.exact_call_reasons == {"SELECTED_SEARCH_MOVE": 1}
    with pytest.raises(IncompleteRun, match="exact-call budget"):
        _claim_canonical_exact_call(exact_summary, "TERMINAL_SEARCH_STATE")
    assert exact_summary.canonical_exact_call_count == MAX_CANONICAL_EXACT_CALLS

    marginal_summary = RunSummary(
        marginal_histogram_evaluation_count=MAX_MARGINAL_HISTOGRAM_EVALUATIONS - 1
    )
    _claim_marginal_histogram_evaluation(marginal_summary)
    assert (
        marginal_summary.marginal_histogram_evaluation_count
        == MAX_MARGINAL_HISTOGRAM_EVALUATIONS
    )
    with pytest.raises(IncompleteRun, match="marginal-histogram budget"):
        _claim_marginal_histogram_evaluation(marginal_summary)
    assert (
        marginal_summary.marginal_histogram_evaluation_count
        == MAX_MARGINAL_HISTOGRAM_EVALUATIONS
    )


def test_search_code_has_no_result_dependent_data_inputs() -> None:
    module_path = REPOSITORY / (
        "src/lottolab/research/b649_k20_filmus_ward_nonoblivious_r1.py"
    )
    module = ast.parse(module_path.read_text(encoding="utf-8"))
    function = next(
        node
        for node in module.body
        if isinstance(node, ast.FunctionDef) and node.name == "_run_search"
    )
    argument_names = [argument.arg for argument in function.args.args]
    assert argument_names == ["repository", "deadline", "summary", "config"]
    referenced_names = {
        node.id for node in ast.walk(function) if isinstance(node, ast.Name)
    }
    assert not referenced_names.intersection(
        {
            "historical_draws",
            "historical_results",
            "future_outcomes",
            "prediction_results",
            "posthoc_performance",
            "previous_random_runs",
            "apply_cross_swap",
            "generate_move_groups",
            "incremental_u3_components",
        }
    )
