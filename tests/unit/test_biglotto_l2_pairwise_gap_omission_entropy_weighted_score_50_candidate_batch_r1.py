"""Focused tests for the sealed GAP_OMISSION + ENTROPY pairwise candidate."""

from __future__ import annotations

import ast
import hashlib
import json
from fractions import Fraction
from pathlib import Path
from typing import cast

import pytest

from lottolab.research import (
    biglotto_l2_pairwise_gap_omission_entropy_weighted_score_50_candidate_batch_r1 as batch,
)
from lottolab.research import (
    biglotto_l2_pairwise_hot_cold_entropy_weighted_score_50_candidate_batch_r1 as neighbor,
)
from lottolab.research import (
    biglotto_multiscale_omission_pressure_multi_ticket_candidate_batch_r1 as parent,
)

Ticket = tuple[int, int, int, int, int, int]

_DRAW_TYPES: tuple[Ticket, ...] = (
    (1, 2, 3, 4, 5, 6),
    (1, 7, 13, 14, 15, 16),
    (2, 8, 17, 18, 19, 20),
    (30, 31, 32, 33, 34, 35),
    (36, 37, 38, 39, 40, 41),
    (42, 43, 44, 45, 46, 47),
    (44, 45, 46, 47, 48, 49),
)
_FILLER: Ticket = (30, 31, 32, 33, 34, 35)
_ANCHOR: Ticket = (1, 2, 3, 4, 5, 6)
_HISTORY: tuple[Ticket, ...] = tuple(
    _DRAW_TYPES[index % len(_DRAW_TYPES)] for index in range(750)
)
_ZERO_INFORMATION_HISTORY: tuple[Ticket, ...] = (*(_FILLER for _ in range(749)), _ANCHOR)
_AUTHORITY_ROOT_NAME = (
    "BIGLOTTO_L2_PAIRWISE_FRONTIER_ADVANCE_AFTER_BB262C993F3FEFEE_R1"
)


def _history(count: int) -> tuple[Ticket, ...]:
    return tuple(_DRAW_TYPES[index % len(_DRAW_TYPES)] for index in range(count))


def _authority_root() -> Path:
    for directory in Path(__file__).resolve().parents:
        candidate = directory / ".task-data" / _AUTHORITY_ROOT_NAME
        if candidate.is_dir():
            return candidate
    pytest.fail("sealed completed_v1_semantics task-data root is unavailable")


def _authority() -> dict[str, object]:
    return json.loads(
        (_authority_root() / "completed_v1_semantics.json").read_text(
            encoding="utf-8"
        )
    )


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
    int_numbers = cast(tuple[int, ...], numbers)
    return len(set(int_numbers)) == 6 and tuple(sorted(int_numbers)) == int_numbers


def _reference_entropy(history: tuple[Ticket, ...]) -> tuple[Fraction, ...]:
    counts = [0] * 49
    for draw in history[-50:]:
        for number in draw:
            counts[number - 1] += 1
    expected = Fraction(300, 49)
    return tuple(
        Fraction(1, 1)
        / (abs(Fraction(counts[number - 1], 1) - expected) + Fraction(1, 10))
        for number in range(1, 50)
    )


def _git_blob_id(path: Path) -> str:
    content = path.read_bytes()
    header = f"blob {len(content)}\0".encode("ascii")
    return hashlib.sha1(header + content, usedforsecurity=False).hexdigest()


def test_authority_checksum_identity_and_semantic_signature_are_exact() -> None:
    authority_root = _authority_root()
    authority_path = authority_root / "completed_v1_semantics.json"
    checksum_line = next(
        line
        for line in (authority_root / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
        if line.endswith("completed_v1_semantics.json")
    )
    assert hashlib.sha256(authority_path.read_bytes()).hexdigest() == checksum_line.split()[0]

    authority = _authority()
    assert authority["SELECTED_GAP_ID"] == batch.SELECTED_GAP_ID
    assert authority["DESIGN_ID"] == batch.DESIGN_ID
    assert authority["DESIGN_SIGNATURE_SHA256"] == batch.DESIGN_SIGNATURE_SHA256
    assert authority["IMPLEMENTATION_READY"] == "YES"
    assert authority["selected_gap_id"] == batch.SELECTED_GAP_ID
    assert authority["design_id"] == batch.DESIGN_ID
    assert authority["design_signature_sha256"] == batch.DESIGN_SIGNATURE_SHA256
    assert authority["implementation_ready"] == "YES"
    assert authority["performance_roots_read"] == 0
    assert authority["performance_values_accessed"] == "NO"
    assert authority["replay_executed"] == "NO"

    semantic_object = authority["canonical_semantic_object"]
    assert isinstance(semantic_object, dict)
    assert semantic_object["SELECTED_GAP_ID"] == batch.SELECTED_GAP_ID
    assert semantic_object["DESIGN_ID"] == batch.DESIGN_ID
    assert semantic_object["IMPLEMENTATION_READY"] == "YES"
    canonical = json.dumps(
        semantic_object,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    assert hashlib.sha256(canonical).hexdigest() == batch.DESIGN_SIGNATURE_SHA256


def test_parent_source_blobs_are_present_and_unchanged() -> None:
    source_root = _repo_root() / "src"
    omission_source = (
        source_root
        / "lottolab"
        / "research"
        / "biglotto_multiscale_omission_pressure_multi_ticket_candidate_batch_r1.py"
    )
    entropy_source = (
        source_root / "lottolab" / "strategies" / "adapters" / "biglotto_wave4.py"
    )
    assert _git_blob_id(omission_source) == (
        batch.PARENT_1_SOURCE_BLOB_ID
    )
    assert _git_blob_id(entropy_source) == (
        batch.PARENT_2_SOURCE_BLOB_ID
    )


def test_gap_omission_parent_component_parity_and_window_semantics() -> None:
    actual = batch.calculate_gap_omission_ranking(_HISTORY, 750)
    frozen = parent.calculate_fused_number_ranking(_HISTORY, 750)
    assert actual.RAW_SCORES == frozen.MEAN_RANKS
    assert actual.ORDERED_NUMBERS == frozen.ORDERED_NUMBERS
    assert actual.ROBUSTNESS == frozen.ROBUSTNESS
    assert tuple(
        Fraction(49 - position, 48)
        for position in actual.POSITIONS
    ) == actual.NORMALIZED_RANKS

    window_rankings = parent.calculate_window_rankings(_HISTORY, 750)
    assert tuple(item.WINDOW for item in window_rankings) == (50, 300, 750)
    assert tuple(item.WINDOW_DRAW_COUNT for item in window_rankings) == (50, 300, 750)

    fallback = parent.calculate_window_rankings(_ZERO_INFORMATION_HISTORY, 750)
    for ranking in fallback:
        assert ranking.current_gap(49) == ranking.WINDOW
        assert ranking.occurrence_count(49) == 0
        assert ranking.omission_pressure(49) == Fraction(ranking.WINDOW, ranking.WINDOW + 1)


def test_entropy_parent_component_parity_and_exact_w50_definition() -> None:
    assert batch.calculate_entropy_raw_scores(_HISTORY, 750) == _reference_entropy(
        _HISTORY
    )
    assert all(
        isinstance(value, Fraction)
        for value in batch.calculate_entropy_raw_scores(_HISTORY, 750)
    )
    history = list(_HISTORY)
    baseline = batch.calculate_entropy_raw_scores(history, 750)
    history[0] = (9, 10, 11, 12, 13, 14)
    assert batch.calculate_entropy_raw_scores(history, 750) == baseline
    history[700] = (9, 10, 11, 12, 13, 14)
    assert batch.calculate_entropy_raw_scores(history, 750) != baseline


def test_minimum_history_and_malformed_history_gates() -> None:
    with pytest.raises(batch.InsufficientHistoryError, match="insufficient history"):
        batch.calculate_pairwise_ranking(_history(749), 749)
    accepted = batch.calculate_pairwise_ranking(_history(750), 750)
    assert len(accepted.RANKED_NUMBERS) == 49

    malformed = list(_HISTORY)
    malformed[10] = (1, 2, 3, 4, 5, 5)
    with pytest.raises(ValueError, match="six unique"):
        batch.calculate_pairwise_ranking(malformed, 750)


def test_target_exclusion_future_suffix_invariance_and_input_immutability() -> None:
    expected = batch.produce_candidate_portfolio(_HISTORY, 750)
    with_target_and_future = (*_HISTORY, (44, 45, 46, 47, 48, 49), object())
    assert batch.produce_candidate_portfolio(with_target_and_future, 750) == expected

    history = [list(draw) for draw in _HISTORY]
    snapshot = [row.copy() for row in history]
    assert batch.produce_candidate_portfolio(history, 750) == expected
    assert history == snapshot

    assert batch.produce_candidate_portfolio(iter(history), 750) == expected


def test_component_normalization_is_exact_and_tie_deterministic() -> None:
    raw = [Fraction(0, 1)] * 49
    raw[0] = Fraction(1, 1)
    raw[1] = Fraction(1, 1)
    ranking = batch.rank_entropy_scores(raw)
    assert ranking.ORDERED_NUMBERS[:2] == (1, 2)
    assert ranking.position(1) == 1
    assert ranking.position(2) == 2
    assert ranking.normalized_rank(1) == Fraction(48, 48)
    assert ranking.normalized_rank(2) == Fraction(47, 48)
    assert ranking.normalized_rank(49) == Fraction(0, 1)
    assert all(isinstance(value, Fraction) for value in ranking.NORMALIZED_RANKS)

    with pytest.raises(TypeError, match="exact Fraction"):
        batch.rank_pairwise_scores(
            [0.1] + [Fraction(0, 1)] * 48,
            [Fraction(0, 1)] * 49,
        )


def test_fusion_weights_hand_fixture_and_final_tie_break_are_exact() -> None:
    gap = [Fraction(0, 1)] * 49
    entropy = [Fraction(0, 1)] * 49
    gap[0], entropy[0] = Fraction(3, 4), Fraction(0, 1)
    gap[1], entropy[1] = Fraction(1, 2), Fraction(1, 1)
    ranking = batch.rank_pairwise_scores(gap, entropy)
    assert Fraction(1, 2) == batch.FUSION_WEIGHT_1
    assert Fraction(1, 2) == batch.FUSION_WEIGHT_2
    assert ranking.pairwise_score(1) == Fraction(3, 8)
    assert ranking.pairwise_score(2) == Fraction(3, 4)
    assert ranking.RANKED_NUMBERS[0] == 2

    gap = [Fraction(0, 1)] * 49
    entropy = [Fraction(0, 1)] * 49
    gap[0], entropy[0] = Fraction(1, 1), Fraction(0, 1)
    gap[1], entropy[1] = Fraction(3, 4), Fraction(1, 4)
    gap[2], entropy[2] = Fraction(1, 4), Fraction(3, 4)
    tied = batch.rank_pairwise_scores(gap, entropy)
    assert tied.pairwise_score(1) == tied.pairwise_score(2)
    assert tied.RANKED_NUMBERS[:3] == (2, 3, 1)


def test_each_parent_can_change_fused_order_and_pair_is_not_singleton() -> None:
    zeros = [Fraction(0, 1)] * 49
    changed_gap = zeros.copy()
    changed_gap[4] = Fraction(1, 1)
    changed_entropy = zeros.copy()
    changed_entropy[6] = Fraction(1, 1)
    baseline = batch.rank_pairwise_scores(zeros, zeros)
    assert batch.rank_pairwise_scores(changed_gap, zeros).RANKED_NUMBERS[0] == 5
    assert batch.rank_pairwise_scores(zeros, changed_entropy).RANKED_NUMBERS[0] == 7
    assert baseline.RANKED_NUMBERS[0] == 1

    gap = zeros.copy()
    entropy = zeros.copy()
    gap[0] = Fraction(1, 1)
    gap[2] = Fraction(3, 4)
    entropy[1] = Fraction(1, 1)
    entropy[2] = Fraction(3, 4)
    pairwise = batch.rank_pairwise_scores(gap, entropy)
    gap_only = batch.rank_pairwise_scores(gap, zeros)
    entropy_only = batch.rank_pairwise_scores(zeros, entropy)
    assert pairwise.RANKED_NUMBERS != gap_only.RANKED_NUMBERS
    assert pairwise.RANKED_NUMBERS != entropy_only.RANKED_NUMBERS
    assert pairwise.RANKED_NUMBERS[0] == 3


def test_both_parent_component_callables_feed_pairwise_implementation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gap = [Fraction(0, 1)] * 49
    entropy = [Fraction(0, 1)] * 49
    gap[0] = Fraction(1, 1)
    entropy[1] = Fraction(1, 1)
    calls: list[str] = []

    def fake_gap(_history: object, _target_index: int) -> tuple[Fraction, ...]:
        calls.append("gap_omission")
        return tuple(gap)

    def fake_entropy(_history: object, _target_index: int) -> tuple[Fraction, ...]:
        calls.append("entropy")
        return tuple(entropy)

    monkeypatch.setattr(batch, "calculate_gap_omission_components", fake_gap)
    monkeypatch.setattr(batch, "calculate_entropy_components", fake_entropy)
    result = batch.calculate_pairwise_ranking(_HISTORY, 750)
    assert calls == ["gap_omission", "entropy"]
    assert result.gap_omission_component(1) == Fraction(1, 1)
    assert result.entropy_component(2) == Fraction(1, 1)


def test_ranked_pool_ticket_shape_and_deterministic_regeneration() -> None:
    first = batch.produce_candidate_portfolio(_ZERO_INFORMATION_HISTORY, 750)
    second = batch.produce_candidate_portfolio(_ZERO_INFORMATION_HISTORY, 750)
    ranking = batch.calculate_pairwise_ranking(_ZERO_INFORMATION_HISTORY, 750)
    assert first == second
    assert len(first) == batch.NATIVE_TICKET_COUNT == 1
    assert first[0] == ranking.NATIVE_TICKET
    assert _legal_ticket(first[0])
    assert len(ranking.RANKED_NUMBERS) == batch.RANKED_POOL_CARDINALITY == 49
    assert set(ranking.RANKED_NUMBERS) == set(range(1, 50))
    assert tuple(sorted(ranking.RANKED_NUMBERS[:6])) == ranking.NATIVE_TICKET
    assert ranking.TICKETS == (ranking.NATIVE_TICKET,)


def test_identity_count_and_relevant_live_neighbor_are_distinct() -> None:
    assert len(batch.CANDIDATE_AUTHORITIES) == 1
    assert batch.CANDIDATE_IDS == (batch.CANDIDATE_ID,)
    assert len(set(batch.CANDIDATE_IDS)) == 1
    assert batch.CANDIDATE_METADATA.CANDIDATE_ID == batch.CANDIDATE_ID
    assert batch.CANDIDATE_METADATA.DESIGN_ID == batch.DESIGN_ID
    assert (
        batch.CANDIDATE_METADATA.DESIGN_SIGNATURE_SHA256
        == batch.DESIGN_SIGNATURE_SHA256
    )
    assert batch.CANDIDATE_ID not in neighbor.CANDIDATE_IDS
    assert batch.DESIGN_SIGNATURE_SHA256 not in neighbor.CANDIDATE_SIGNATURE_HASHES.values()
    assert batch.candidate_id_for_semantics(batch.CANDIDATE_SEMANTICS) == batch.CANDIDATE_ID
    with pytest.raises(ValueError, match="DESIGN_ID"):
        batch.candidate_id_for_semantics({"DESIGN_ID": "wrong"})


def test_public_contract_freezes_required_semantics() -> None:
    contract = batch.SOURCE_UNIVERSE_CONTRACT
    authority = cast(dict[str, object], _authority()["canonical_semantic_object"])
    required = (
        "CANDIDATE_ID",
        "SELECTED_GAP_ID",
        "DESIGN_ID",
        "DESIGN_SIGNATURE_SHA256",
        "FEATURE_1",
        "FEATURE_2",
        "PARENT_SOURCE_UNIVERSE_ID_1",
        "PARENT_SOURCE_UNIVERSE_ID_2",
        "PARENT_COMPONENT_RULE_1",
        "PARENT_COMPONENT_RULE_2",
        "PARENT_WINDOW_RULE_1",
        "PARENT_WINDOW_RULE_2",
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
        "MINIMUM_HISTORY",
        "CAUSAL_CUTOFF_RULE",
        "FALLBACK_RULE",
        "PARAMETER_SELECTION_RULE",
        "DETERMINISM_CLASS",
        "RNG_SEMANTICS",
        "IMPLEMENTATION_MODULE",
        "IMPLEMENTATION_SYMBOL",
    )
    for key in required:
        assert key in contract
        if key not in authority:
            continue
        authority_value = authority[key]
        if key in {
            "COMPONENT_NORMALIZATION_RULE",
            "NUMBER_RANKING_RULE",
            "NUMBER_TIE_BREAK_RULE",
        }:
            assert tuple(cast(list[str], authority_value)) == contract[key]
        else:
            assert contract[key] == authority_value
    assert getattr(batch, batch.IMPLEMENTATION_SYMBOL) is batch.produce_candidate_portfolio


def test_research_module_has_no_external_runtime_or_random_imports() -> None:
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
    assert "production_catalog" not in source
    assert "replay" not in source
    assert "database" not in source


def test_candidate_ticket_is_not_an_intermediate_top_k_pool() -> None:
    source = Path(batch.__file__).read_text(encoding="utf-8")
    assert "NO_INTERMEDIATE_TOP_K_POOL" in source
    assert "TOP_NUMBER_COUNT" not in source
    assert "combinations(" not in source
