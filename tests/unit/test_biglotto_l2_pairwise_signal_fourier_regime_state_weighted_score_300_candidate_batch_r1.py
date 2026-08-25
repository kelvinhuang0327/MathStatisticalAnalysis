"""Focused tests for the sealed SIGNAL_FOURIER + REGIME_STATE candidate."""

from __future__ import annotations

import ast
import hashlib
import json
from fractions import Fraction
from pathlib import Path
from typing import cast

import pytest

from lottolab.research import (
    biglotto_l2_pairwise_signal_fourier_regime_state_weighted_score_300_candidate_batch_r1,
    biglotto_multiscale_spectral_concentration_multi_ticket_candidate_batch_r1,
    biglotto_renyi2_regime_switched_multi_ticket_candidate_batch_r1,
)

batch = (
    biglotto_l2_pairwise_signal_fourier_regime_state_weighted_score_300_candidate_batch_r1
)
regime_parent = biglotto_renyi2_regime_switched_multi_ticket_candidate_batch_r1
signal_fourier_parent = (
    biglotto_multiscale_spectral_concentration_multi_ticket_candidate_batch_r1
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
_AUTHORITY_ROOT_NAME = (
    "ADVANCE_LEVEL2_FRONTIER_AFTER_BMSGV1_L2_PAIRWISE_61FF59870C8C57AF_R1"
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
    return json.loads(
        (_authority_root() / "implementation_handoff.json").read_text(
            encoding="utf-8"
        )
    )


def _verify_sha256sums(root: Path) -> None:
    for line in (root / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        expected, relative_path = line.split(maxsplit=1)
        assert hashlib.sha256((root / relative_path).read_bytes()).hexdigest() == expected


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


def test_authority_identity_signature_and_paths_are_exact() -> None:
    root = _authority_root()
    _verify_sha256sums(root)
    handoff = _authority()
    assert handoff["SELECTED_GAP_ID"] == batch.SELECTED_GAP_ID
    assert handoff["CANDIDATE_ID"] == batch.CANDIDATE_ID
    assert handoff["DESIGN_ID"] == batch.DESIGN_ID
    assert handoff["DESIGN_SIGNATURE_SHA256"] == batch.DESIGN_SIGNATURE_SHA256
    assert handoff["IMPLEMENTATION_READY"] == "YES"
    assert handoff["EXPECTED_IMPLEMENTATION_MODULE"] == batch.IMPLEMENTATION_MODULE
    assert handoff["EXPECTED_FOCUSED_TEST_MODULE"] == (
        "tests/unit/"
        "test_biglotto_l2_pairwise_signal_fourier_regime_state_weighted_score_300_candidate_batch_r1.py"
    )

    signature_object = cast(dict[str, object], handoff["DESIGN_SIGNATURE_OBJECT"])
    canonical = json.dumps(
        signature_object,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    assert hashlib.sha256(canonical).hexdigest() == batch.DESIGN_SIGNATURE_SHA256
    assert batch.signature_hash_for_semantics(batch.CANDIDATE_SEMANTICS) == (
        batch.DESIGN_SIGNATURE_SHA256
    )


def test_authority_controlled_semantics_are_reproduced() -> None:
    authority = cast(dict[str, object], _authority()["DESIGN_SIGNATURE_OBJECT"])
    required = (
        "PARENT_SOURCE_UNIVERSE_ID_1",
        "PARENT_SOURCE_UNIVERSE_ID_2",
        "PARENT_COMPONENT_RULE_1",
        "PARENT_COMPONENT_RULE_2",
        "PARENT_WINDOW_RULE_1",
        "PARENT_WINDOW_RULE_2",
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
    )
    for key in required:
        expected = authority[key]
        actual = batch.SOURCE_UNIVERSE_CONTRACT[key]
        if isinstance(expected, list):
            assert actual == tuple(cast(list[object], expected))
        else:
            assert actual == expected


def test_candidate_identity_and_determinism_layers_are_exactly_one() -> None:
    assert len(batch.CANDIDATE_AUTHORITIES) == 1
    assert batch.CANDIDATE_IDS == (batch.CANDIDATE_ID,)
    assert batch.CANDIDATE_ID == "BMSGV1_L2_PAIRWISE_8d97214ab08c8169"
    assert batch.SELECTED_GAP_ID == batch.CANDIDATE_ID
    assert batch.CANDIDATE_METADATA.IMPLEMENTATION_MODULE == batch.IMPLEMENTATION_MODULE
    assert batch.CANDIDATE_METADATA.IMPLEMENTATION_SYMBOL == batch.IMPLEMENTATION_SYMBOL
    assert batch.CANDIDATE_METADATA.NATIVE_TICKET_COUNT == 1
    assert batch.RNG_SEMANTICS == "NONE"
    assert batch.RNG is None
    assert batch.candidate_id_for_semantics(batch.CANDIDATE_SEMANTICS) == batch.CANDIDATE_ID
    with pytest.raises(ValueError, match="DESIGN_ID"):
        batch.candidate_id_for_semantics({"DESIGN_ID": "wrong"})


def test_regime_parent_state_and_ordered_source_parity_are_exact() -> None:
    history = _history(751)
    local_state = batch.calculate_regime_state(history, 751)
    parent_state = regime_parent.calculate_regime_state(history, 751)
    assert local_state == parent_state
    assert batch.calculate_collision_concentrations(history, 751) == (
        regime_parent.calculate_collision_concentrations(history, 751)
    )

    local_source = batch.produce_regime_source_ticket_universe(history, 751)
    parent_source = regime_parent.produce_b649_renyi2_regime_switched_ranked_pool_v1(
        history, 751
    )
    assert local_source == parent_source
    assert len(local_source) == 210
    assert len(set(local_source)) == 210
    assert all(_legal_ticket(ticket) for ticket in local_source)

    expected_counts = [0] * 49
    for ticket in parent_source:
        for number in ticket:
            expected_counts[number - 1] += 1
    assert batch.calculate_regime_state_raw_scores(history, 751) == tuple(
        Fraction(count, 1) for count in expected_counts
    )


def test_regime_support_ties_are_number_ascending_and_exact() -> None:
    raw = [Fraction(0, 1)] * 49
    raw[0] = raw[1] = Fraction(12, 1)
    ranking = batch.rank_regime_state_scores(raw)
    assert ranking.ORDERED_NUMBERS[:2] == (1, 2)
    assert ranking.normalized_rank(1) == Fraction(48, 48)
    assert ranking.normalized_rank(49) == Fraction(0, 1)
    with pytest.raises(TypeError, match="exact Fraction"):
        batch.rank_regime_state_scores([0.1] + [Fraction(0, 1)] * 48)


def test_signal_fourier_parent_component_parity_and_formula_are_exact() -> None:
    history = _history(751)
    raw = batch.calculate_signal_fourier_raw_scores(history, 751)
    components = batch.calculate_signal_fourier_components(history, 751)
    parent = signal_fourier_parent.calculate_window_rankings(history, 751, 300)
    assert raw == parent.SPECTRAL_IPRS
    assert components == parent.NORMALIZED_RANKS
    assert batch.calculate_signal_fourier_ranking(history, 751).ORDERED_NUMBERS == (
        parent.ORDERED_NUMBERS
    )
    assert parent.WINDOW == parent.WINDOW_DRAW_COUNT == 300
    assert all(isinstance(value, Fraction) for value in raw)
    autocorrelation = (Fraction(2, 1), Fraction(0, 1), Fraction(-2, 1), Fraction(0, 1))
    assert signal_fourier_parent.spectral_ipr_from_circular_autocorrelation(
        autocorrelation
    ) == Fraction(1, 2)


def test_signal_fourier_ties_use_peak_autocorrelation_then_number() -> None:
    raw = [Fraction(0, 1)] * 49
    peaks = [Fraction(0, 1)] * 49
    raw[0] = raw[1] = Fraction(1, 1)
    peaks[0], peaks[1] = Fraction(1, 4), Fraction(3, 4)
    ranking = batch.rank_signal_fourier_scores(raw, peaks)
    assert ranking.ORDERED_NUMBERS[:2] == (2, 1)
    assert ranking.normalized_rank(2) == Fraction(48, 48)


def test_minimum_history_malformed_and_causal_cutoff() -> None:
    with pytest.raises(batch.InsufficientHistoryError, match="insufficient history"):
        batch.calculate_pairwise_ranking(_history(750), 750)
    accepted = batch.calculate_pairwise_ranking(_history(751), 751)
    assert len(accepted.RANKED_NUMBERS) == 49

    malformed = list(_history(751))
    malformed[10] = (1, 2, 3, 4, 5, 5)
    with pytest.raises(ValueError, match="six unique"):
        batch.calculate_pairwise_ranking(malformed, 751)

    prefix = list(_history(751))
    snapshot = [draw for draw in prefix]
    expected = batch.produce_candidate_portfolio(prefix, 751)
    with_target_and_future = [*prefix, (44, 45, 46, 47, 48, 49), object()]
    assert batch.produce_candidate_portfolio(with_target_and_future, 751) == expected
    with_target_and_future[751] = (7, 8, 9, 10, 11, 12)
    assert batch.produce_candidate_portfolio(with_target_and_future, 751) == expected
    assert batch.produce_candidate_portfolio(iter(prefix), 751) == expected
    assert prefix == snapshot


def test_signal_fourier_window_ends_at_target() -> None:
    history = list(_history(751))
    baseline = batch.calculate_signal_fourier_raw_scores(history, 751)
    history[450] = (9, 10, 11, 12, 13, 14)
    assert batch.calculate_signal_fourier_raw_scores(history, 751) == baseline
    history[451] = (9, 10, 11, 12, 13, 14)
    assert batch.calculate_signal_fourier_raw_scores(history, 751) != baseline


def _component_fixture(
    signal_number_1: Fraction = Fraction(0, 1),
    signal_number_2: Fraction = Fraction(0, 1),
    regime_number_1: Fraction = Fraction(0, 1),
    regime_number_2: Fraction = Fraction(0, 1),
) -> tuple[list[Fraction], list[Fraction]]:
    signal = [Fraction(0, 1)] * 49
    regime = [Fraction(0, 1)] * 49
    signal[0], signal[1] = signal_number_1, signal_number_2
    regime[0], regime[1] = regime_number_1, regime_number_2
    return signal, regime


def test_fusion_weights_formula_and_final_tie_break_are_exact() -> None:
    signal, regime = _component_fixture(
        signal_number_1=Fraction(3, 4),
        signal_number_2=Fraction(1, 2),
        regime_number_1=Fraction(0, 1),
        regime_number_2=Fraction(1, 1),
    )
    ranking = batch.rank_pairwise_scores(signal, regime)
    assert ranking.pairwise_score(1) == Fraction(3, 8)
    assert ranking.pairwise_score(2) == Fraction(3, 4)
    assert ranking.RANKED_NUMBERS[0] == 2
    assert batch.FUSION_WEIGHT_1 == batch.FUSION_WEIGHT_2 == Fraction(1, 2)
    assert batch.FUSION_FORMULA == (
        "PAIRWISE_SCORE(n)=1/2*SIGNAL_FOURIER_NORMALIZED_RANK_300(n)+"
        "1/2*REGIME_STATE_NORMALIZED_SUPPORT_RANK_300(n);EXACT_RATIONAL"
    )

    signal = [Fraction(0, 1)] * 49
    regime = [Fraction(0, 1)] * 49
    signal[0], regime[0] = Fraction(1, 1), Fraction(0, 1)
    signal[1], regime[1] = Fraction(3, 4), Fraction(1, 4)
    signal[2], regime[2] = Fraction(1, 4), Fraction(3, 4)
    tied = batch.rank_pairwise_scores(signal, regime)
    assert tied.pairwise_score(1) == tied.pairwise_score(2)
    assert tied.RANKED_NUMBERS[:3] == (2, 3, 1)


def test_each_parent_can_change_fused_order_and_pair_is_not_singleton() -> None:
    zeros = [Fraction(0, 1)] * 49
    changed_signal = zeros.copy()
    changed_signal[4] = Fraction(1, 1)
    changed_regime = zeros.copy()
    changed_regime[6] = Fraction(1, 1)
    baseline = batch.rank_pairwise_scores(zeros, zeros)
    assert batch.rank_pairwise_scores(changed_signal, zeros).RANKED_NUMBERS[0] == 5
    assert batch.rank_pairwise_scores(zeros, changed_regime).RANKED_NUMBERS[0] == 7
    assert baseline.RANKED_NUMBERS[0] == 1

    signal = zeros.copy()
    regime = zeros.copy()
    signal[0], signal[2] = Fraction(1, 1), Fraction(3, 4)
    regime[1], regime[2] = Fraction(1, 1), Fraction(3, 4)
    pairwise = batch.rank_pairwise_scores(signal, regime)
    signal_only = batch.rank_pairwise_scores(signal, zeros)
    regime_only = batch.rank_pairwise_scores(zeros, regime)
    assert pairwise.RANKED_NUMBERS != signal_only.RANKED_NUMBERS
    assert pairwise.RANKED_NUMBERS != regime_only.RANKED_NUMBERS
    assert pairwise.RANKED_NUMBERS[0] == 3


def test_both_parent_callables_feed_pairwise_implementation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    history = _history(751)
    signal = [Fraction(0, 1)] * 49
    regime = [Fraction(0, 1)] * 49
    signal[0] = Fraction(1, 1)
    regime[1] = Fraction(1, 1)
    calls: list[str] = []

    def fake_signal(_history: object, _target_index: int) -> tuple[Fraction, ...]:
        calls.append("signal_fourier")
        return tuple(signal)

    def fake_regime(_history: object, _target_index: int) -> tuple[Fraction, ...]:
        calls.append("regime_state")
        return tuple(regime)

    monkeypatch.setattr(batch, "calculate_signal_fourier_components", fake_signal)
    monkeypatch.setattr(batch, "calculate_regime_state_components", fake_regime)
    result = batch.calculate_pairwise_ranking(history, 751)
    assert calls == ["signal_fourier", "regime_state"]
    assert result.signal_fourier_component(1) == Fraction(1, 1)
    assert result.regime_state_component(2) == Fraction(1, 1)


def test_ranked_pool_ticket_shape_and_deterministic_regeneration() -> None:
    history = (*(_FILLER for _ in range(750)), _DRAW_TYPES[0])
    first = batch.produce_candidate_portfolio(history, 751)
    second = batch.produce_candidate_portfolio(history, 751)
    ranking = batch.calculate_pairwise_ranking(history, 751)
    assert first == second == (ranking.NATIVE_TICKET,)
    assert len(first) == batch.NATIVE_TICKET_COUNT == 1
    assert _legal_ticket(first[0])
    assert len(ranking.RANKED_NUMBERS) == 49
    assert set(ranking.RANKED_NUMBERS) == set(range(1, 50))
    assert tuple(sorted(ranking.RANKED_NUMBERS[:6])) == ranking.NATIVE_TICKET


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
        {
            "sqlite3",
            "socket",
            "subprocess",
            "time",
            "urllib",
            "requests",
            "random",
            "numpy",
            "scipy",
        }
    )
    assert "production_catalog" not in source
    assert "registry" not in source
    assert "replay" not in source
    assert "TOP_NUMBER_COUNT" not in source
    assert "combinations(" not in source
    assert batch.RNG_SEMANTICS == "NONE"
    assert batch.RNG is None
