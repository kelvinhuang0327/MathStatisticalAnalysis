"""Focused tests for the sealed COOCCURRENCE + ENTROPY candidate."""

from __future__ import annotations

import ast
import hashlib
import json
from fractions import Fraction
from pathlib import Path
from typing import cast

import pytest

from lottolab.research import (
    biglotto_conditional_cooccurrence_multi_ticket_candidate_batch_r1 as cooccurrence_parent,
)
from lottolab.research import (
    biglotto_l2_pairwise_cooccurrence_entropy_weighted_score_50_candidate_batch_r1 as batch,
)
from lottolab.research import (
    biglotto_l2_pairwise_hot_cold_entropy_weighted_score_50_candidate_batch_r1 as entropy_reference,
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
_AUTHORITY_ROOT_NAME = (
    "ADVANCE_LEVEL2_FRONTIER_AFTER_BMSGV1_L2_PAIRWISE_2507681AD9EF073C_R1"
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
    expected_line = next(
        line
        for line in (authority_root / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
        if line.endswith("completed_v1_semantics.json")
    )
    assert hashlib.sha256(authority_path.read_bytes()).hexdigest() == expected_line.split()[0]

    authority = _authority()
    assert authority["SELECTED_GAP_ID"] == batch.SELECTED_GAP_ID
    assert authority["DESIGN_ID"] == batch.DESIGN_ID
    assert authority["DESIGN_SIGNATURE_SHA256"] == batch.DESIGN_SIGNATURE_SHA256
    assert authority["IMPLEMENTATION_READY"] == "YES"
    semantic_object = authority["CANONICAL_SEMANTIC_OBJECT"]
    assert isinstance(semantic_object, dict)
    canonical = json.dumps(
        semantic_object,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    assert hashlib.sha256(canonical).hexdigest() == batch.DESIGN_SIGNATURE_SHA256


def test_candidate_count_and_identity_layers_are_exactly_one() -> None:
    assert len(batch.CANDIDATE_AUTHORITIES) == 1
    assert batch.CANDIDATE_IDS == (batch.CANDIDATE_ID,)
    assert batch.CANDIDATE_ID == "BMSGV1_L2_PAIRWISE_0ef39f92e3a20b8c"
    assert batch.SELECTED_GAP_ID == batch.CANDIDATE_ID
    assert batch.CANDIDATE_METADATA.DESIGN_ID == batch.DESIGN_ID
    assert (
        batch.CANDIDATE_METADATA.DESIGN_SIGNATURE_SHA256
        == batch.DESIGN_SIGNATURE_SHA256
    )
    assert batch.candidate_id_for_semantics(batch.CANDIDATE_SEMANTICS) == batch.CANDIDATE_ID
    identity = batch.derive_candidate_identity(batch.CANDIDATE_SEMANTICS)
    assert identity.CANDIDATE_ID == batch.CANDIDATE_ID
    assert identity.SIGNATURE_HASH == batch.DESIGN_SIGNATURE_SHA256
    assert not batch.CANDIDATE_ID.endswith(batch.DESIGN_SIGNATURE_SHA256[:16])
    with pytest.raises(ValueError, match="DESIGN_ID"):
        batch.candidate_id_for_semantics({"DESIGN_ID": "wrong"})


def test_authority_controlled_semantics_are_reproduced_exactly() -> None:
    authority_value = _authority()["CANONICAL_SEMANTIC_OBJECT"]
    assert isinstance(authority_value, dict)
    authority = cast(dict[str, object], authority_value)
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


def test_parent_source_blobs_are_present_and_unchanged() -> None:
    repo_root = Path(batch.__file__).resolve().parents[3]
    cooccurrence_source = (
        repo_root
        / (
            "src/lottolab/research/"
            "biglotto_conditional_cooccurrence_multi_ticket_candidate_batch_r1.py"
        )
    )
    entropy_source = repo_root / "src/lottolab/strategies/adapters/biglotto_wave4.py"
    assert _git_blob_id(cooccurrence_source) == batch.PARENT_1_SOURCE_BLOB_ID
    assert _git_blob_id(entropy_source) == batch.PARENT_2_SOURCE_BLOB_ID


def test_conditional_cooccurrence_parent_component_parity_is_exact() -> None:
    history = _history(756)
    raw = batch.calculate_cooccurrence_raw_scores(history, 756)
    components = batch.calculate_cooccurrence_components(history, 756)
    parent_ranking = cooccurrence_parent.rank_numbers_by_window(history, 756, 50)
    assert raw == parent_ranking.SCORES
    assert components == parent_ranking.NORMALIZED_RANKS
    assert parent_ranking.WINDOW == 50
    assert parent_ranking.ESTIMATION_DRAW_COUNT == 50
    assert history[755] == parent_ranking.ANCHOR_DRAW
    assert all(isinstance(value, Fraction) for value in raw)


def test_entropy_parent_component_parity_and_exact_w50_definition() -> None:
    history = _history(751)
    raw = batch.calculate_entropy_raw_scores(history, 751)
    assert raw == _reference_entropy(history)
    assert raw == entropy_reference.calculate_entropy_raw_scores(history, 751)
    assert all(isinstance(value, Fraction) and value > 0 for value in raw)

    older_change = list(history)
    baseline = batch.calculate_entropy_raw_scores(older_change, 751)
    older_change[700] = (9, 10, 11, 12, 13, 14)
    assert batch.calculate_entropy_raw_scores(older_change, 751) == baseline
    window_change = list(history)
    window_change[701] = (9, 10, 11, 12, 13, 14)
    assert batch.calculate_entropy_raw_scores(window_change, 751) != baseline


def test_minimum_history_and_malformed_history_gates() -> None:
    with pytest.raises(batch.InsufficientHistoryError, match="insufficient history"):
        batch.calculate_pairwise_ranking(_history(750), 750)
    accepted = batch.calculate_pairwise_ranking(_history(751), 751)
    assert len(accepted.RANKED_NUMBERS) == 49

    malformed = list(_history(751))
    malformed[10] = (1, 2, 3, 4, 5, 5)
    with pytest.raises(ValueError, match="six unique"):
        batch.calculate_pairwise_ranking(malformed, 751)


def test_target_exclusion_future_suffix_and_input_immutability() -> None:
    prefix = _history(751)
    expected = batch.produce_candidate_portfolio(prefix, 751)
    with_target_and_future = (*prefix, (44, 45, 46, 47, 48, 49), object())
    assert batch.produce_candidate_portfolio(with_target_and_future, 751) == expected

    history = [list(draw) for draw in prefix]
    snapshot = [row.copy() for row in history]
    assert batch.produce_candidate_portfolio(history, 751) == expected
    assert batch.produce_candidate_portfolio(iter(history), 751) == expected
    assert history == snapshot


def test_cooccurrence_window_and_causal_suffix_semantics_are_exact() -> None:
    history = list(_history(751))
    baseline = batch.calculate_cooccurrence_raw_scores(history, 751)
    history[699] = (9, 10, 11, 12, 13, 14)
    assert batch.calculate_cooccurrence_raw_scores(history, 751) == baseline
    history[700] = (9, 10, 11, 12, 13, 14)
    assert batch.calculate_cooccurrence_raw_scores(history, 751) != baseline


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


def test_fusion_weights_formula_and_final_tie_break_are_exact() -> None:
    cooccurrence = [Fraction(0, 1)] * 49
    entropy = [Fraction(0, 1)] * 49
    cooccurrence[0], entropy[0] = Fraction(3, 4), Fraction(0, 1)
    cooccurrence[1], entropy[1] = Fraction(1, 2), Fraction(1, 1)
    ranking = batch.rank_pairwise_scores(cooccurrence, entropy)
    assert Fraction(1, 2) == batch.FUSION_WEIGHT_1
    assert Fraction(1, 2) == batch.FUSION_WEIGHT_2
    assert ranking.pairwise_score(1) == Fraction(3, 8)
    assert ranking.pairwise_score(2) == Fraction(3, 4)
    assert ranking.RANKED_NUMBERS[0] == 2
    assert batch.FUSION_FORMULA == (
        "PAIRWISE_SCORE(n)=1/2*COOCCURRENCE_NORMALIZED_RANK_50(n)+"
        "1/2*ENTROPY_NORMALIZED_RANK_50(n);EXACT_RATIONAL"
    )

    cooccurrence = [Fraction(0, 1)] * 49
    entropy = [Fraction(0, 1)] * 49
    cooccurrence[0], entropy[0] = Fraction(1, 1), Fraction(0, 1)
    cooccurrence[1], entropy[1] = Fraction(3, 4), Fraction(1, 4)
    cooccurrence[2], entropy[2] = Fraction(1, 4), Fraction(3, 4)
    tied = batch.rank_pairwise_scores(cooccurrence, entropy)
    assert tied.pairwise_score(1) == tied.pairwise_score(2)
    assert tied.RANKED_NUMBERS[:3] == (2, 3, 1)


def test_each_parent_can_change_fused_order_and_pair_is_not_singleton() -> None:
    zeros = [Fraction(0, 1)] * 49
    changed_cooccurrence = zeros.copy()
    changed_cooccurrence[4] = Fraction(1, 1)
    changed_entropy = zeros.copy()
    changed_entropy[6] = Fraction(1, 1)
    baseline = batch.rank_pairwise_scores(zeros, zeros)
    assert batch.rank_pairwise_scores(changed_cooccurrence, zeros).RANKED_NUMBERS[0] == 5
    assert batch.rank_pairwise_scores(zeros, changed_entropy).RANKED_NUMBERS[0] == 7
    assert baseline.RANKED_NUMBERS[0] == 1

    cooccurrence = zeros.copy()
    entropy = zeros.copy()
    cooccurrence[0] = Fraction(1, 1)
    cooccurrence[2] = Fraction(3, 4)
    entropy[1] = Fraction(1, 1)
    entropy[2] = Fraction(3, 4)
    pairwise = batch.rank_pairwise_scores(cooccurrence, entropy)
    cooccurrence_only = batch.rank_pairwise_scores(cooccurrence, zeros)
    entropy_only = batch.rank_pairwise_scores(zeros, entropy)
    assert pairwise.RANKED_NUMBERS != cooccurrence_only.RANKED_NUMBERS
    assert pairwise.RANKED_NUMBERS != entropy_only.RANKED_NUMBERS
    assert pairwise.RANKED_NUMBERS[0] == 3


def test_both_parent_callables_feed_pairwise_implementation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    history = _history(751)
    cooccurrence = [Fraction(0, 1)] * 49
    entropy = [Fraction(0, 1)] * 49
    cooccurrence[0] = Fraction(1, 1)
    entropy[1] = Fraction(1, 1)
    calls: list[str] = []

    def fake_cooccurrence(_history: object, _target_index: int) -> tuple[Fraction, ...]:
        calls.append("cooccurrence")
        return tuple(cooccurrence)

    def fake_entropy(_history: object, _target_index: int) -> tuple[Fraction, ...]:
        calls.append("entropy")
        return tuple(entropy)

    monkeypatch.setattr(batch, "calculate_cooccurrence_components", fake_cooccurrence)
    monkeypatch.setattr(batch, "calculate_entropy_components", fake_entropy)
    result = batch.calculate_pairwise_ranking(history, 751)
    assert calls == ["cooccurrence", "entropy"]
    assert result.cooccurrence_component(1) == Fraction(1, 1)
    assert result.entropy_component(2) == Fraction(1, 1)
    assert result.RANKED_NUMBERS[:2] == (1, 2)


def test_ranked_pool_ticket_shape_and_deterministic_regeneration() -> None:
    history = (*(_FILLER for _ in range(750)), _ANCHOR)
    first = batch.produce_candidate_portfolio(history, 751)
    second = batch.produce_candidate_portfolio(history, 751)
    ranking = batch.calculate_pairwise_ranking(history, 751)
    assert first == second
    assert len(first) == batch.NATIVE_TICKET_COUNT == 1
    assert first[0] == ranking.NATIVE_TICKET
    assert len(first[0]) == 6
    assert len(set(first[0])) == 6
    assert tuple(sorted(ranking.RANKED_NUMBERS[:6])) == ranking.NATIVE_TICKET
    assert len(ranking.RANKED_NUMBERS) == 49
    assert set(ranking.RANKED_NUMBERS) == set(range(1, 50))
    assert all(1 <= number <= 49 for number in first[0])
    assert ranking.TICKETS == (ranking.NATIVE_TICKET,)


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
    assert "registry" not in source
    assert "replay" not in source
    assert "TOP_NUMBER_COUNT" not in source
    assert "combinations(" not in source
