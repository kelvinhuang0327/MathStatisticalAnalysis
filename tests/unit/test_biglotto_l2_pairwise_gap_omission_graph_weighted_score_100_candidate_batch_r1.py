"""Focused acceptance tests for the sealed GAP_OMISSION + GRAPH candidate."""

from __future__ import annotations

import ast
import csv
import hashlib
import json
import subprocess
from fractions import Fraction
from pathlib import Path
from typing import cast

import pytest

from lottolab.research import (
    biglotto_graph_network_multi_ticket_candidate_batch_r1 as graph_parent,
)
from lottolab.research import (
    biglotto_l2_pairwise_gap_omission_entropy_weighted_score_50_candidate_batch_r1,
)
from lottolab.research import (
    biglotto_l2_pairwise_gap_omission_graph_weighted_score_100_candidate_batch_r1 as batch,
)
from lottolab.research import (
    biglotto_l2_pairwise_graph_constraint_weighted_score_100_candidate_batch_r1 as graph_neighbor,
)
from lottolab.research import (
    biglotto_multiscale_omission_pressure_multi_ticket_candidate_batch_r1 as omission_parent,
)

Ticket = tuple[int, int, int, int, int, int]
gap_omission_neighbor = (
    biglotto_l2_pairwise_gap_omission_entropy_weighted_score_50_candidate_batch_r1
)

_AUTHORITY_ROOT = Path(
    "/Users/kelvin/VibeCoding-WorkSpace/.task-data/"
    "ADVANCE_LEVEL2_FRONTIER_AFTER_BMSGV1_L2_PAIRWISE_950AA3B890915ED7_R1"
)
_TASK_DATA_ROOT = Path(
    "/Users/kelvin/VibeCoding-WorkSpace/.task-data/"
    "BIGLOTTO_L2_PAIRWISE_GAP_OMISSION_GRAPH_WEIGHTED_SCORE_100_CANDIDATE_BATCH_R1"
)
_CANDIDATE_SOURCE_PATH = (
    "src/lottolab/research/"
    "biglotto_l2_pairwise_gap_omission_graph_weighted_score_100_candidate_batch_r1.py"
)
_PR187_HEAD = "e4042f4aa56caf37db10f9a426f9ea64cde4284c"
_PR164_HEAD = "80566e798ea1640b6c6d0afaf98a70d503a4cf2d"

_DRAW_TYPES: tuple[Ticket, ...] = (
    (1, 2, 3, 4, 5, 6),
    (2, 7, 13, 19, 31, 43),
    (3, 8, 14, 20, 32, 44),
    (4, 9, 15, 21, 33, 45),
    (5, 10, 16, 22, 34, 46),
    (6, 11, 17, 23, 35, 47),
    (7, 12, 18, 24, 36, 48),
    (8, 13, 19, 25, 37, 49),
    (9, 14, 20, 26, 38, 41),
    (10, 15, 21, 27, 39, 42),
)
_FILLER: Ticket = (1, 2, 3, 4, 5, 6)
_HISTORY: tuple[Ticket, ...] = tuple(
    _DRAW_TYPES[index % len(_DRAW_TYPES)] for index in range(750)
)
_ZERO_INFORMATION_HISTORY: tuple[Ticket, ...] = tuple(
    _FILLER for _ in range(750)
)


def _history(count: int) -> tuple[Ticket, ...]:
    return tuple(_DRAW_TYPES[index % len(_DRAW_TYPES)] for index in range(count))


def _authority() -> dict[str, object]:
    return cast(
        dict[str, object],
        json.loads(
            (_AUTHORITY_ROOT / "implementation_handoff.json").read_text(
                encoding="utf-8"
            )
        ),
    )


def _git_blob_id(path: Path) -> str:
    content = path.read_bytes()
    header = f"blob {len(content)}\0".encode("ascii")
    return hashlib.sha1(header + content, usedforsecurity=False).hexdigest()


def _repo_root() -> Path:
    return Path(batch.__file__).resolve().parents[3]


def _legal_ticket(ticket: object) -> bool:
    if not isinstance(ticket, tuple):
        return False
    numbers = cast(tuple[object, ...], ticket)
    if len(numbers) != 6:
        return False
    if not all(type(number) is int and 1 <= number <= 49 for number in numbers):
        return False
    typed = cast(tuple[int, ...], numbers)
    return len(set(typed)) == 6 and typed == tuple(sorted(typed))


def _git_path_exists(ref: str, path: str) -> bool:
    result = subprocess.run(
        ["git", "cat-file", "-e", f"{ref}:{path}"],
        cwd=_repo_root(),
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def test_predecessor_authority_checksum_identity_and_paths_are_exact() -> None:
    assert _AUTHORITY_ROOT.is_dir()
    for line in (_AUTHORITY_ROOT / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        expected_hash, relative_path = line.split(maxsplit=1)
        actual_hash = hashlib.sha256(
            (_AUTHORITY_ROOT / relative_path).read_bytes()
        ).hexdigest()
        assert actual_hash == expected_hash

    authority_path = _AUTHORITY_ROOT / "implementation_handoff.json"
    assert hashlib.sha256(authority_path.read_bytes()).hexdigest() == (
        batch.DESIGN_AUTHORITY_SHA256
    )
    authority = _authority()
    assert authority["SELECTED_GAP_ID"] == batch.SELECTED_GAP_ID
    assert authority["DESIGN_ID"] == batch.DESIGN_ID
    assert authority["DESIGN_SIGNATURE_SHA256"] == batch.DESIGN_SIGNATURE_SHA256
    assert authority["FEATURE_1"] == batch.FEATURE_1
    assert authority["FEATURE_2"] == batch.FEATURE_2
    assert authority["WINDOW"] == batch.WINDOW
    assert authority["FUSION"] == batch.FUSION
    assert authority["IMPLEMENTATION_READY"] == "YES"
    assert authority["EXPECTED_IMPLEMENTATION_MODULE"] == batch.IMPLEMENTATION_MODULE
    assert authority["EXPECTED_IMPLEMENTATION_SYMBOL"] == batch.IMPLEMENTATION_SYMBOL
    assert authority["EXPECTED_FOCUSED_TEST_MODULE"] == (
        "tests/unit/test_biglotto_l2_pairwise_gap_omission_graph_weighted_score_100_candidate_batch_r1.py"
    )
    assert authority["IMPLEMENTATION_PATHS_FROZEN_EXACTLY"] == "YES"
    assert authority["PERFORMANCE_EVIDENCE_USED"] == "NO"
    assert authority["PERFORMANCE_ROOTS_READ"] == 0
    assert authority["PERFORMANCE_VALUES_ACCESSED"] == "NO"
    assert authority["REPLAY_EXECUTED"] == "NO"

    signature_object = cast(dict[str, object], authority["DESIGN_SIGNATURE_OBJECT"])
    assert json.loads(batch.canonical_semantic_json(batch.CANDIDATE_SEMANTICS)) == (
        signature_object
    )
    assert batch.signature_hash_for_semantics(batch.CANDIDATE_SEMANTICS) == (
        batch.DESIGN_SIGNATURE_SHA256
    )


def test_task_data_outputs_are_complete_singleton_and_checksum_verified() -> None:
    required = (
        "source_universe_contract.json",
        "candidate_authority.csv",
        "candidate_validation_handoff.csv",
        "candidate_batch_manifest.json",
        "SHA256SUMS",
    )
    assert all((_TASK_DATA_ROOT / name).is_file() for name in required)
    checksum_lines = (
        (_TASK_DATA_ROOT / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
    )
    assert {line.split(maxsplit=1)[1] for line in checksum_lines} == set(required[:-1])
    for line in checksum_lines:
        expected_hash, relative_path = line.split(maxsplit=1)
        actual_hash = hashlib.sha256(
            (_TASK_DATA_ROOT / relative_path).read_bytes()
        ).hexdigest()
        assert actual_hash == expected_hash

    contract = cast(
        dict[str, object],
        json.loads(
            (_TASK_DATA_ROOT / "source_universe_contract.json").read_text(
                encoding="utf-8"
            )
        ),
    )
    for key in (
        "CANDIDATE_ID",
        "DESIGN_ID",
        "DESIGN_SIGNATURE_SHA256",
        "FEATURE_1",
        "FEATURE_2",
        "WINDOW",
        "PARENT_COMPONENT_RULE_1",
        "PARENT_COMPONENT_RULE_2",
        "PARENT_WINDOW_RULE_1",
        "PARENT_WINDOW_RULE_2",
        "MINIMUM_HISTORY",
        "COMPONENT_NORMALIZATION_RULE",
        "FUSION",
        "FUSION_WEIGHT_1",
        "FUSION_WEIGHT_2",
        "FUSION_FORMULA",
        "NUMBER_RANKING_RULE",
        "NUMBER_TIE_BREAK_RULE",
        "RANKED_POOL_DOMAIN",
        "RANKED_POOL_CARDINALITY",
        "CANDIDATE_CONSTRUCTION_RULE",
        "TICKET_CONSTRUCTION",
        "TICKET_SELECTION_RULE",
        "NATIVE_TICKET_COUNT",
        "CAUSAL_CUTOFF_RULE",
        "FALLBACK_RULE",
        "PARAMETER_SELECTION_RULE",
        "DETERMINISM_CLASS",
        "RNG_SEMANTICS",
        "IMPLEMENTATION_MODULE",
        "IMPLEMENTATION_SYMBOL",
    ):
        contract_value = contract[key]
        expected_value = batch.SOURCE_UNIVERSE_CONTRACT[key]
        if key in {"COMPONENT_NORMALIZATION_RULE", "NUMBER_RANKING_RULE", "NUMBER_TIE_BREAK_RULE"}:
            assert tuple(cast(list[str], contract_value)) == expected_value
        else:
            assert contract_value == expected_value

    authority_rows = list(
        csv.DictReader(
            (_TASK_DATA_ROOT / "candidate_authority.csv").open(
                newline="", encoding="utf-8"
            )
        )
    )
    assert len(authority_rows) == 1
    assert authority_rows[0]["CANDIDATE_ID"] == batch.CANDIDATE_ID
    assert authority_rows[0]["DESIGN_ID"] == batch.DESIGN_ID
    assert authority_rows[0]["NATIVE_TICKET_COUNT"] == "1"

    validation_rows = list(
        csv.DictReader(
            (_TASK_DATA_ROOT / "candidate_validation_handoff.csv").open(
                newline="", encoding="utf-8"
            )
        )
    )
    assert len(validation_rows) == 1
    assert validation_rows[0]["TECHNICAL_IMPLEMENTATION_STATUS"] == (
        "TECHNICAL_IMPLEMENTATION_COMPLETE"
    )
    assert validation_rows[0]["CATALOG_STATUS"] == "NOT_CATALOG_WIRED"
    assert validation_rows[0]["PERFORMANCE_VALIDATION_STATUS"] == "NOT_RUN"
    assert validation_rows[0]["REPLAY_STATUS"] == "NOT_RUN"
    assert validation_rows[0]["PERFORMANCE_CONTAMINATION_STATUS"] == (
        "TASK_SPECIFIC_CLEAN_WITH_PREEXISTING_UNRELATED_CONTEXT"
    )

    manifest = cast(
        dict[str, object],
        json.loads(
            (_TASK_DATA_ROOT / "candidate_batch_manifest.json").read_text(
                encoding="utf-8"
            )
        ),
    )
    assert manifest["CANDIDATE_COUNT"] == 1
    assert manifest["CANDIDATE_IDS"] == [batch.CANDIDATE_ID]
    assert manifest["LIVE_MAIN_EXACT_DUPLICATE_COUNT"] == 0
    assert manifest["OPEN_PR_EXACT_DUPLICATE_COUNT"] == 0
    assert manifest["CATALOG_STATUS"] == "NOT_CATALOG_WIRED"
    assert manifest["PERFORMANCE_VALIDATION_STATUS"] == "NOT_RUN"
    assert manifest["REPLAY_STATUS"] == "NOT_RUN"


def test_candidate_identity_is_exactly_one_and_live_exact_duplicates_are_zero() -> None:
    assert len(batch.CANDIDATE_AUTHORITIES) == 1
    assert batch.CANDIDATE_IDS == (batch.CANDIDATE_ID,)
    assert batch.CANDIDATE_ID == "BMSGV1_L2_PAIRWISE_5b92df6e42366e6b"
    assert batch.SELECTED_GAP_ID == batch.CANDIDATE_ID
    assert batch.CANDIDATE_METADATA.DESIGN_ID == batch.DESIGN_ID
    assert batch.CANDIDATE_METADATA.DESIGN_SIGNATURE_SHA256 == (
        batch.DESIGN_SIGNATURE_SHA256
    )
    assert batch.candidate_id_for_semantics(batch.CANDIDATE_SEMANTICS) == (
        batch.CANDIDATE_ID
    )
    assert batch.CANDIDATE_ID not in gap_omission_neighbor.CANDIDATE_IDS
    assert batch.CANDIDATE_ID not in graph_neighbor.CANDIDATE_IDS
    assert batch.DESIGN_SIGNATURE_SHA256 not in (
        *gap_omission_neighbor.CANDIDATE_SIGNATURE_HASHES.values(),
        *graph_neighbor.CANDIDATE_SIGNATURE_HASHES.values(),
    )
    with pytest.raises(ValueError, match="DESIGN_ID"):
        batch.candidate_id_for_semantics({"DESIGN_ID": "wrong"})

    assert not _git_path_exists("origin/main", _CANDIDATE_SOURCE_PATH)
    assert not _git_path_exists(_PR187_HEAD, _CANDIDATE_SOURCE_PATH)
    assert not _git_path_exists(_PR164_HEAD, _CANDIDATE_SOURCE_PATH)
    assert _TASK_DATA_ROOT.joinpath("candidate_batch_manifest.json").is_file()
    manifest = json.loads(
        (_TASK_DATA_ROOT / "candidate_batch_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    assert manifest["PR187_SEMANTIC_CLASSIFICATION"] == (
        "STOCHASTIC_FRONTEND_MONTE_CARLO_NOT_EQUIVALENT"
    )
    assert manifest["PR187_EXACT_DUPLICATE"] == "NO"


def test_parent_source_blobs_and_exact_parent_parity_are_preserved() -> None:
    root = _repo_root()
    omission_source = root / batch.PARENT_SOURCE_PATH_1
    graph_source = root / batch.PARENT_SOURCE_PATH_2
    assert _git_blob_id(omission_source) == batch.PARENT_1_SOURCE_BLOB_ID
    assert _git_blob_id(graph_source) == batch.PARENT_2_SOURCE_BLOB_ID
    assert hashlib.sha256(omission_source.read_bytes()).hexdigest() == (
        batch.PARENT_1_SOURCE_SHA256
    )
    assert hashlib.sha256(graph_source.read_bytes()).hexdigest() == (
        batch.PARENT_2_SOURCE_SHA256
    )

    history = _HISTORY
    actual_omission_windows = batch.calculate_gap_omission_window_rankings(
        history, 750
    )
    expected_omission_windows = omission_parent.calculate_window_rankings(history, 750)
    assert actual_omission_windows == expected_omission_windows
    assert batch.calculate_gap_omission_parent_ranking(history, 750) == (
        omission_parent.calculate_fused_number_ranking(history, 750)
    )

    actual_graph_windows = batch.calculate_graph_window_rankings(history, 750)
    expected_graph_windows = graph_parent.calculate_window_rankings(history, 750)
    assert actual_graph_windows == expected_graph_windows
    assert batch.calculate_graph_parent_ranking(history, 750) == (
        graph_parent.calculate_fused_number_ranking(history, 750)
    )
    assert all(
        isinstance(value, Fraction)
        for window in actual_graph_windows
        for value in window.PAGERANKS
    )
    assert all(
        sum(window.PAGERANKS, Fraction(0, 1)) == Fraction(1, 1)
        for window in actual_graph_windows
    )
    assert batch.OMISSION_WINDOWS == (50, 300, 750)
    assert batch.GRAPH_WINDOWS == (50, 300, 750)
    assert Fraction(17, 20) == graph_parent.PAGERANK_DAMPING
    assert graph_parent.PAGERANK_ITERATIONS == 20
    assert graph_parent.PAGERANK_INITIALIZATION == "UNIFORM_1_OVER_49"
    assert graph_parent.PAGERANK_DANGLING_RULE == "UNIFORM_REDISTRIBUTION"


def test_minimum_history_causality_and_caller_history_immutability() -> None:
    with pytest.raises(batch.InsufficientHistoryError, match="at least 750"):
        batch.calculate_pairwise_ranking(_history(batch.MINIMUM_HISTORY - 1), 749)

    history = list(_HISTORY)
    snapshot = history.copy()
    baseline = batch.produce_candidate_portfolio(history, 750)
    with_target_and_future: list[object] = [*history, object(), _DRAW_TYPES[0]]
    assert batch.produce_candidate_portfolio(with_target_and_future, 750) == baseline
    with_target_and_future[750] = (2, 4, 6, 8, 10, 12)
    assert batch.produce_candidate_portfolio(with_target_and_future, 750) == baseline
    assert history == snapshot

    malformed = history.copy()
    malformed[10] = (1, 2, 3, 4, 5, 5)
    with pytest.raises(ValueError, match="six unique"):
        batch.calculate_pairwise_ranking(malformed, 750)


def test_gap_omission_parent_restriction_and_exact_rank_normalization() -> None:
    pool = tuple(range(1, 11))
    ranking = batch.calculate_gap_omission_ranking(_HISTORY, 750, pool)
    parent_ranking = omission_parent.calculate_fused_number_ranking(_HISTORY, 750)
    expected_order = tuple(number for number in parent_ranking.ORDERED_NUMBERS if number in pool)
    assert expected_order == ranking.ORDERED_NUMBERS
    assert pool == ranking.POOL_NUMBERS
    assert tuple(parent_ranking.mean_rank(number) for number in pool) == ranking.RAW_SCORES
    assert tuple(
        Fraction(10 - ranking.position(number), 9) for number in pool
    ) == ranking.NORMALIZED_RANKS
    assert all(isinstance(value, Fraction) for value in ranking.NORMALIZED_RANKS)

    zero_information = omission_parent.calculate_window_rankings(
        _ZERO_INFORMATION_HISTORY, 750
    )
    for window in zero_information:
        assert window.current_gap(49) == window.WINDOW
        assert window.occurrence_count(49) == 0
        assert window.omission_pressure(49) == Fraction(
            window.WINDOW, window.WINDOW + 1
        )


def test_graph_derived_pool_is_authoritative_and_not_numeric_or_pagerank_rebuilt() -> None:
    ranking = batch.calculate_pairwise_ranking(_HISTORY, 750)
    graph_parent_ranking = graph_parent.calculate_fused_number_ranking(_HISTORY, 750)
    pool = graph_parent_ranking.TOP_NUMBERS
    assert len(graph_parent_ranking.ORDERED_NUMBERS) == 49
    assert pool == graph_parent_ranking.ORDERED_NUMBERS[:10]
    assert batch.produce_graph_traversal_pool(_HISTORY, 750) == pool
    assert pool == ranking.GRAPH_POOL
    assert pool == ranking.GRAPH_TRAVERSAL_POOL
    assert pool == ranking.GRAPH_RANKING.ORDERED_NUMBERS
    assert pool == ranking.GAP_OMISSION_RANKING.POOL_NUMBERS
    assert len(ranking.RANKED_NUMBERS) == batch.RANKED_POOL_CARDINALITY == 10
    assert set(ranking.RANKED_NUMBERS) == set(pool)
    assert tuple(
        Fraction(10 - position, 9) for position in range(1, 11)
    ) == ranking.GRAPH_COMPONENTS
    assert len(set(pool)) == 10
    assert all(1 <= number <= 49 for number in pool)


def test_exact_pool_ties_equal_weight_fusion_and_pairwise_dependence() -> None:
    pool = tuple(range(1, 11))
    tied = batch.rank_pool_component_scores(pool, (0,) * 10)
    assert pool == tied.ORDERED_NUMBERS
    assert tied.position(1) == 1
    assert tied.position(10) == 10
    assert tied.normalized_rank(1) == Fraction(9, 9)
    assert tied.normalized_rank(10) == Fraction(0, 9)

    one_high = (0,) * 9 + (1,)
    one_high_ranking = batch.rank_pool_component_scores(pool, one_high)
    assert one_high_ranking.ORDERED_NUMBERS[:3] == (10, 1, 2)
    assert one_high_ranking.normalized_rank(10) == Fraction(9, 9)
    with pytest.raises(TypeError, match="exact Fraction"):
        batch.rank_pool_component_scores(pool, (0.1,) + (Fraction(0),) * 9)

    descending = tuple(Fraction(10 - position, 9) for position in range(1, 11))
    ascending = tuple(Fraction(position - 1, 9) for position in range(1, 11))
    fused = batch.rank_pairwise_scores(
        descending, ascending, pool_numbers=pool
    )
    assert all(score == Fraction(1, 2) for score in fused.PAIRWISE_SCORES)
    assert all(isinstance(score, Fraction) for score in fused.PAIRWISE_SCORES)
    assert (
        batch.FUSION_WEIGHT_1 * descending[0]
        + batch.FUSION_WEIGHT_2 * ascending[0]
    ) == fused.SCORES[0].PAIRWISE_SCORE

    zeros = (Fraction(0),) * 10
    gap = list(zeros)
    graph = list(zeros)
    gap[0] = Fraction(1)
    gap[1] = Fraction(3, 4)
    graph[1] = Fraction(3, 4)
    graph[2] = Fraction(1)
    pairwise = batch.rank_pairwise_scores(tuple(gap), tuple(graph), pool_numbers=pool)
    gap_only = batch.rank_pairwise_scores(tuple(gap), zeros, pool_numbers=pool)
    graph_only = batch.rank_pairwise_scores(zeros, tuple(graph), pool_numbers=pool)
    assert pairwise.RANKED_NUMBERS[0] == 2
    assert pairwise.RANKED_NUMBERS != gap_only.RANKED_NUMBERS
    assert pairwise.RANKED_NUMBERS != graph_only.RANKED_NUMBERS
    gap_change = list(zeros)
    gap_change[9] = Fraction(1)
    graph_change = list(zeros)
    graph_change[9] = Fraction(1)
    baseline_order = batch.rank_pairwise_scores(
        zeros, zeros, pool_numbers=pool
    ).RANKED_NUMBERS
    assert baseline_order != batch.rank_pairwise_scores(
        tuple(gap_change), zeros, pool_numbers=pool
    ).RANKED_NUMBERS
    assert baseline_order != batch.rank_pairwise_scores(
        zeros, tuple(graph_change), pool_numbers=pool
    ).RANKED_NUMBERS


def test_both_parent_callables_feed_pairwise_implementation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_gap = batch.calculate_gap_omission_parent_ranking
    real_graph = batch.calculate_graph_parent_ranking
    calls: list[str] = []

    def wrapped_gap(history: object, target_index: int) -> object:
        calls.append("gap_omission")
        return real_gap(cast(batch.HistoryInput, history), target_index)

    def wrapped_graph(history: object, target_index: int) -> object:
        calls.append("graph")
        return real_graph(cast(batch.HistoryInput, history), target_index)

    monkeypatch.setattr(batch, "calculate_gap_omission_parent_ranking", wrapped_gap)
    monkeypatch.setattr(batch, "calculate_graph_parent_ranking", wrapped_graph)
    result = batch.calculate_pairwise_ranking(_HISTORY, 750)
    assert calls == ["graph", "gap_omission"]
    assert result.GRAPH_PARENT_RANKING is not None
    assert result.GAP_OMISSION_PARENT_RANKING is not None


def test_single_ticket_shape_determinism_and_no_external_wiring() -> None:
    first = batch.produce_candidate_portfolio(_HISTORY, 750)
    second = batch.produce_candidate_portfolio(_HISTORY, 750)
    ranking = batch.calculate_pairwise_ranking(_HISTORY, 750)
    assert first == second == (ranking.NATIVE_TICKET,)
    assert len(first) == batch.NATIVE_TICKET_COUNT == 1
    assert _legal_ticket(first[0])
    assert tuple(sorted(ranking.RANKED_NUMBERS[:6])) == ranking.NATIVE_TICKET
    assert ranking.TICKETS == (ranking.NATIVE_TICKET,)

    source = Path(batch.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_roots.add(node.module.split(".", 1)[0])
    assert not imported_roots.intersection(
        {"sqlite3", "socket", "subprocess", "time", "urllib", "requests", "random"}
    )
    assert "lottolab.strategies.catalog" not in source
    assert "sqlite" not in source.lower()
    assert "import random" not in source.lower()
    assert "replay" not in source.lower()
    assert "TOP_NUMBER_COUNT" not in source
    assert "combinations(" not in source
    assert batch.DETERMINISM_CLASS == "PURE_DETERMINISTIC_NO_RNG"
    assert batch.RNG_SEMANTICS == "NONE"
    assert batch.RNG is None


def test_no_parent_or_production_paths_are_modified() -> None:
    result = subprocess.run(
        ["git", "diff", "--name-only", "27f0bb4022c859112275e3e54ae48fc5c10d7984"],
        cwd=_repo_root(),
        capture_output=True,
        text=True,
        check=True,
    )
    changed = set(result.stdout.splitlines())
    assert changed <= {
        _CANDIDATE_SOURCE_PATH,
        "tests/unit/test_biglotto_l2_pairwise_gap_omission_graph_weighted_score_100_candidate_batch_r1.py",
    }
