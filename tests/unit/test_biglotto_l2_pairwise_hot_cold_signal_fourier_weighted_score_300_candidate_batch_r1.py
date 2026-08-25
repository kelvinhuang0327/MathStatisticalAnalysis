"""Focused tests for the sealed HOT_COLD + SIGNAL_FOURIER candidate."""

from __future__ import annotations

import ast
import hashlib
import json
from fractions import Fraction
from pathlib import Path
from typing import cast

import pytest

from lottolab.research import (
    biglotto_l2_pairwise_hot_cold_entropy_weighted_score_50_candidate_batch_r1 as hot_cold_reference,  # noqa: E501
)
from lottolab.research import (
    biglotto_l2_pairwise_hot_cold_signal_fourier_weighted_score_300_candidate_batch_r1 as batch,
)
from lottolab.research import (
    biglotto_multiscale_spectral_concentration_multi_ticket_candidate_batch_r1 as signal_fourier_parent,  # noqa: E501
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
_ALTERNATE: Ticket = (7, 8, 9, 10, 11, 12)
_AUTHORITY_ROOT_NAME = (
    "ADVANCE_LEVEL2_FRONTIER_AFTER_BMSGV1_L2_PAIRWISE_B78B91941E1D6404_R1"
)


def _history(count: int) -> tuple[Ticket, ...]:
    return tuple(_DRAW_TYPES[index % len(_DRAW_TYPES)] for index in range(count))


def _authority_root() -> Path:
    for directory in Path(__file__).resolve().parents:
        candidate = directory / ".task-data" / _AUTHORITY_ROOT_NAME
        if candidate.is_dir():
            return candidate
    pytest.fail("sealed predecessor authority root is unavailable")


def _authority() -> dict[str, object]:
    return cast(
        dict[str, object],
        json.loads(
            (_authority_root() / "implementation_handoff.json").read_text(
                encoding="utf-8"
            )
        ),
    )


def _legal_ticket(ticket: object) -> bool:
    if not isinstance(ticket, tuple):
        return False
    values = cast(tuple[object, ...], ticket)
    return (
        len(values) == 6
        and all(type(number) is int and 1 <= number <= 49 for number in values)
        and len(set(values)) == 6
        and tuple(sorted(cast(tuple[int, ...], values))) == values
    )


def test_authority_identity_signature_and_task_hashes_are_exact() -> None:
    root = _authority_root()
    handoff = _authority()
    for line in (root / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        expected_hash, relative_path = line.split(maxsplit=1)
        assert hashlib.sha256((root / relative_path).read_bytes()).hexdigest() == expected_hash

    assert handoff["CANDIDATE_ID"] == batch.CANDIDATE_ID
    assert handoff["SELECTED_GAP_ID"] == batch.SELECTED_GAP_ID
    assert handoff["DESIGN_ID"] == batch.DESIGN_ID
    assert handoff["DESIGN_SIGNATURE_SHA256"] == batch.DESIGN_SIGNATURE_SHA256
    assert handoff["IMPLEMENTATION_READY"] == "YES"
    assert handoff["EXPECTED_IMPLEMENTATION_MODULE"] == batch.IMPLEMENTATION_MODULE
    assert handoff["EXPECTED_IMPLEMENTATION_SYMBOL"] == batch.IMPLEMENTATION_SYMBOL
    assert handoff["EXPECTED_SOURCE_PATH"] == batch.EXPECTED_SOURCE_PATH
    assert handoff["EXPECTED_FOCUSED_TEST_MODULE"] == batch.EXPECTED_FOCUSED_TEST_MODULE

    authority_semantics = cast(dict[str, object], handoff["DESIGN_SIGNATURE_OBJECT"])
    assert batch.canonicalize_semantic_record(authority_semantics) == (
        batch.canonicalize_semantic_record(batch.CANDIDATE_SEMANTICS)
    )
    assert hashlib.sha256(
        batch.canonicalize_semantic_record(authority_semantics)
    ).hexdigest() == batch.DESIGN_SIGNATURE_SHA256


def test_authority_controlled_semantics_are_reproduced_exactly() -> None:
    authority = cast(dict[str, object], _authority()["DESIGN_SIGNATURE_OBJECT"])
    required = (
        "PARENT_SOURCE_UNIVERSE_ID_1",
        "PARENT_SOURCE_UNIVERSE_ID_2",
        "PARENT_SOURCE_UNIVERSE_VERSION_1",
        "PARENT_SOURCE_UNIVERSE_VERSION_2",
        "PARENT_COMPONENT_RULE_1",
        "PARENT_COMPONENT_RULE_2",
        "PARENT_WINDOW_RULE_1",
        "PARENT_WINDOW_RULE_2",
        "HISTORY_ORDER",
        "MINIMUM_HISTORY",
        "COMPONENT_NORMALIZATION_RULE",
        "COMPONENT_SCORE_DOMAIN_1",
        "COMPONENT_SCORE_DOMAIN_2",
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
        "IMPLEMENTATION_READY",
    )
    for key in required:
        expected = authority[key]
        actual = batch.SOURCE_UNIVERSE_CONTRACT[key]
        if isinstance(expected, list):
            assert actual == tuple(cast(list[object], expected))
        elif key in {"FUSION_WEIGHT_1", "FUSION_WEIGHT_2"}:
            fraction = cast(Fraction, actual)
            assert str(fraction.numerator) + "/" + str(fraction.denominator) == expected
        else:
            assert actual == expected


def test_candidate_identity_and_determinism_layers_are_exactly_one() -> None:
    assert len(batch.CANDIDATE_AUTHORITIES) == 1
    assert batch.CANDIDATE_IDS == (batch.CANDIDATE_ID,)
    assert batch.SELECTED_GAP_ID == batch.CANDIDATE_ID
    assert batch.CANDIDATE_METADATA.IMPLEMENTATION_MODULE == batch.IMPLEMENTATION_MODULE
    assert batch.CANDIDATE_METADATA.IMPLEMENTATION_SYMBOL == batch.IMPLEMENTATION_SYMBOL
    assert batch.CANDIDATE_METADATA.NATIVE_TICKET_COUNT == 1
    assert batch.CANDIDATE_METADATA.PARENT_SOURCE_UNIVERSE_ID_2 == (
        batch.PARENT_SOURCE_UNIVERSE_ID_2
    )
    assert batch.RNG_SEMANTICS == "NONE"
    assert batch.RNG is None
    assert batch.candidate_id_for_semantics(batch.CANDIDATE_SEMANTICS) == batch.CANDIDATE_ID
    with pytest.raises(ValueError, match="DESIGN_ID"):
        batch.candidate_id_for_semantics({"DESIGN_ID": "wrong"})


def test_hot_cold_parent_primitive_parity_is_exact() -> None:
    history = _history(750)
    local_raw = batch.calculate_hot_cold_raw_scores(history, 750)
    reference_raw = hot_cold_reference.calculate_hot_cold_raw_scores(history, 750)
    assert local_raw == reference_raw
    local_ranking = batch.calculate_hot_cold_ranking(history, 750)
    reference_ranking = hot_cold_reference.calculate_hot_cold_ranking(history, 750)
    assert local_ranking.NORMALIZED_RANKS == reference_ranking.NORMALIZED_RANKS
    assert local_ranking.ORDERED_NUMBERS == reference_ranking.ORDERED_NUMBERS
    assert batch.calculate_hot_cold_components(history, 750) == local_ranking.NORMALIZED_RANKS


def test_signal_fourier_w300_parent_parity_and_ties_are_exact() -> None:
    history = _history(750)
    local_window = batch.calculate_signal_fourier_window_ranking(history, 750)
    parent_window = signal_fourier_parent.calculate_window_rankings(history, 750, 300)
    assert local_window == parent_window
    local_ranking = batch.calculate_signal_fourier_ranking(history, 750)
    expected_order = tuple(
        sorted(
            batch.LEGAL_NUMBERS,
            key=lambda number: (
                -parent_window.SPECTRAL_IPRS[number - 1],
                -parent_window.PEAK_NORMALIZED_CIRCULAR_AUTOCORRS[number - 1],
                number,
            ),
        )
    )
    assert local_ranking.RAW_SCORES == parent_window.SPECTRAL_IPRS
    assert expected_order == local_ranking.ORDERED_NUMBERS
    assert local_ranking.NORMALIZED_RANKS == parent_window.NORMALIZED_RANKS

    raw = [Fraction(0, 1)] * 49
    peak = [Fraction(0, 1)] * 49
    raw[0] = raw[1] = Fraction(1, 1)
    peak[0] = Fraction(1, 2)
    assert batch.rank_signal_fourier_scores(raw, peak).RANKED_NUMBERS[:2] == (1, 2)


def test_all49_component_domains_and_normalization_are_exact() -> None:
    zeros = [Fraction(0, 1)] * 49
    hot_cold = batch.rank_hot_cold_scores(zeros)
    signal_fourier = batch.rank_signal_fourier_scores(zeros, zeros)
    assert hot_cold.POOL_NUMBERS == batch.LEGAL_NUMBERS
    assert signal_fourier.POOL_NUMBERS == batch.LEGAL_NUMBERS
    assert hot_cold.ORDERED_NUMBERS == batch.LEGAL_NUMBERS
    assert signal_fourier.ORDERED_NUMBERS == batch.LEGAL_NUMBERS
    assert hot_cold.normalized_rank(1) == Fraction(1, 1)
    assert hot_cold.normalized_rank(49) == Fraction(0, 1)
    assert signal_fourier.normalized_rank(1) == Fraction(1, 1)
    assert signal_fourier.normalized_rank(49) == Fraction(0, 1)


def test_final_fusion_is_exact_and_both_parent_components_participate() -> None:
    history = _history(750)
    result = batch.calculate_pairwise_ranking(history, 750)
    hot_cold = batch.calculate_hot_cold_components(history, 750)
    signal_fourier = batch.calculate_signal_fourier_components(history, 750)
    assert hot_cold != signal_fourier
    assert hot_cold == result.HOT_COLD_COMPONENTS
    assert signal_fourier == result.SIGNAL_FOURIER_COMPONENTS

    for number in batch.LEGAL_NUMBERS:
        assert result.pairwise_score(number) == (
            hot_cold[number - 1] + signal_fourier[number - 1]
        ) / 2

    expected_order = tuple(
        sorted(
            batch.LEGAL_NUMBERS,
            key=lambda number: (
                -result.pairwise_score(number),
                -min(hot_cold[number - 1], signal_fourier[number - 1]),
                -hot_cold[number - 1],
                -signal_fourier[number - 1],
                number,
            ),
        )
    )
    assert expected_order == result.RANKED_NUMBERS


def test_exact_rank_pairwise_ties_and_ticket_shape() -> None:
    hot_cold = [Fraction(0, 1)] * 49
    signal_fourier = [Fraction(0, 1)] * 49
    hot_cold[0] = Fraction(1, 1)
    signal_fourier[1] = Fraction(1, 1)
    ranking = batch.rank_pairwise_scores(hot_cold, signal_fourier)
    assert ranking.RANKED_NUMBERS[:2] == (1, 2)
    assert ranking.pairwise_score(1) == Fraction(1, 2)
    assert ranking.pairwise_score(2) == Fraction(1, 2)
    assert ranking.NATIVE_TICKET == (1, 2, 3, 4, 5, 6)
    assert _legal_ticket(ranking.NATIVE_TICKET)
    with pytest.raises(TypeError, match="exact Fraction"):
        batch.rank_pairwise_scores([0.1] + [Fraction(0, 1)] * 48, signal_fourier)


def test_history_minimum_malformed_and_causal_cutoff() -> None:
    with pytest.raises(batch.InsufficientHistoryError, match="required minimum"):
        batch.calculate_pairwise_ranking(_history(749), 749)
    history = _history(750)
    accepted = batch.calculate_pairwise_ranking(history, 750)
    assert len(accepted.RANKED_NUMBERS) == batch.RANKED_POOL_CARDINALITY

    malformed = list(history)
    malformed[10] = (1, 2, 3, 4, 5, 5)
    with pytest.raises(ValueError, match="duplicate number"):
        batch.calculate_pairwise_ranking(malformed, 750)

    prefix = list(history)
    snapshot = list(prefix)
    expected = batch.produce_candidate_portfolio(prefix, 750)
    with_target_and_future: list[object] = [*prefix, _ALTERNATE, object()]
    assert batch.produce_candidate_portfolio(with_target_and_future, 750) == expected
    with_target_and_future[750] = (44, 45, 46, 47, 48, 49)
    assert batch.produce_candidate_portfolio(with_target_and_future, 750) == expected
    assert batch.produce_candidate_portfolio(iter(prefix), 750) == expected
    assert prefix == snapshot


def test_research_module_isolated_from_runtime_and_empirical_paths() -> None:
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
    assert "registry" not in source
    assert "replay" not in source
    assert "leaderboard" not in source


def test_output_is_one_deterministic_native_ticket() -> None:
    history = _history(750)
    first = batch.produce_candidate_portfolio(history, 750)
    second = batch.produce_candidate_portfolio(history, 750)
    ranking = batch.calculate_pairwise_ranking(history, 750)
    assert first == second == (ranking.NATIVE_TICKET,)
    assert len(first) == batch.NATIVE_TICKET_COUNT == 1
    assert _legal_ticket(first[0])
    assert getattr(batch, batch.IMPLEMENTATION_SYMBOL) is batch.produce_candidate_portfolio
