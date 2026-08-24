"""Focused tests for the sealed BAYESIAN_PROBABILISTIC + SIGNAL_FOURIER candidate."""

from __future__ import annotations

import ast
import hashlib
import json
from fractions import Fraction
from pathlib import Path
from typing import cast

import pytest

from lottolab.research import (
    biglotto_l2_pairwise_bayes_signal_fourier_weighted_score_300_candidate_batch_r1 as batch,
)
from lottolab.research import (
    biglotto_multiscale_bayes_changepoint_bma_multi_ticket_candidate_batch_r1 as bayesian_parent,
)
from lottolab.research import (
    biglotto_multiscale_spectral_concentration_multi_ticket_candidate_batch_r1 as spectral_parent,
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
    "ADVANCE_LEVEL2_FRONTIER_AFTER_BMSGV1_L2_PAIRWISE_8ABBAED2EA78E47F_R1"
)
_BAYES_AUTHORITY_ROOT_NAME = (
    "BIGLOTTO_MULTISCALE_BAYES_CHANGEPOINT_BMA_MULTI_TICKET_CANDIDATE_BATCH_R1"
)
_SPECTRAL_AUTHORITY_ROOT_NAME = (
    "BIGLOTTO_MULTISCALE_SPECTRAL_CONCENTRATION_MULTI_TICKET_CANDIDATE_BATCH_R1"
)


def _history(count: int) -> tuple[Ticket, ...]:
    return tuple(_DRAW_TYPES[index % len(_DRAW_TYPES)] for index in range(count))


def _authority_root(name: str) -> Path:
    for directory in Path(__file__).resolve().parents:
        candidate = directory / ".task-data" / name
        if candidate.is_dir():
            return candidate
    pytest.fail(f"task-data root is unavailable: {name}")


def _authority() -> dict[str, object]:
    return json.loads(
        (_authority_root(_AUTHORITY_ROOT_NAME) / "completed_v1_semantics.json").read_text(
            encoding="utf-8"
        )
    )


def _verify_sha256sums(root: Path) -> None:
    for line in (root / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        expected, filename = line.split(maxsplit=1)
        filename = filename.removeprefix("*")
        assert hashlib.sha256((root / filename).read_bytes()).hexdigest() == expected


def _git_blob_id(path: Path) -> str:
    content = path.read_bytes()
    header = f"blob {len(content)}\0".encode("ascii")
    return hashlib.sha1(header + content, usedforsecurity=False).hexdigest()


def _component_fixture(
    bayesian_number_1: Fraction = Fraction(0, 1),
    bayesian_number_2: Fraction = Fraction(0, 1),
    spectral_number_1: Fraction = Fraction(0, 1),
    spectral_number_2: Fraction = Fraction(0, 1),
) -> tuple[list[Fraction], list[Fraction]]:
    bayesian = [Fraction(0, 1)] * 49
    spectral = [Fraction(0, 1)] * 49
    bayesian[0] = bayesian_number_1
    bayesian[1] = bayesian_number_2
    spectral[0] = spectral_number_1
    spectral[1] = spectral_number_2
    return bayesian, spectral


def test_authority_checksum_identity_and_semantic_signature_are_exact() -> None:
    authority_root = _authority_root(_AUTHORITY_ROOT_NAME)
    _verify_sha256sums(authority_root)
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
    assert batch.signature_hash_for_semantics(batch.CANDIDATE_SEMANTICS) == (
        batch.DESIGN_SIGNATURE_SHA256
    )


def test_candidate_count_and_identity_layers_are_exactly_one() -> None:
    assert len(batch.CANDIDATE_AUTHORITIES) == 1
    assert batch.CANDIDATE_IDS == (batch.CANDIDATE_ID,)
    assert batch.CANDIDATE_ID == "BMSGV1_L2_PAIRWISE_04da0231c3998f63"
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
    semantic_object = _authority()["CANONICAL_SEMANTIC_OBJECT"]
    assert isinstance(semantic_object, dict)
    authority = cast(dict[str, object], semantic_object)
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


def test_parent_authority_roots_and_source_blobs_are_verified() -> None:
    _verify_sha256sums(_authority_root(_BAYES_AUTHORITY_ROOT_NAME))
    _verify_sha256sums(_authority_root(_SPECTRAL_AUTHORITY_ROOT_NAME))
    repo_root = Path(batch.__file__).resolve().parents[3]
    bayes_source = repo_root / (
        "src/lottolab/research/"
        "biglotto_multiscale_bayes_changepoint_bma_multi_ticket_candidate_batch_r1.py"
    )
    spectral_source = repo_root / (
        "src/lottolab/research/"
        "biglotto_multiscale_spectral_concentration_multi_ticket_candidate_batch_r1.py"
    )
    assert _git_blob_id(bayes_source) == batch.PARENT_1_SOURCE_BLOB_ID
    assert _git_blob_id(spectral_source) == batch.PARENT_2_SOURCE_BLOB_ID


def test_bayesian_parent_component_parity_and_frozen_bma_semantics() -> None:
    history = _history(756)
    raw = batch.calculate_bayesian_raw_scores(history, 756)
    components = batch.calculate_bayesian_components(history, 756)
    parent_ranking = bayesian_parent.rank_numbers_by_window(history, 756, 300)
    assert raw == parent_ranking.BMA_PREDICTIVE
    assert components == parent_ranking.NORMALIZED_RANKS
    assert batch.calculate_bayesian_ranking(history, 756).ORDERED_NUMBERS == (
        parent_ranking.ORDERED_NUMBERS
    )
    assert parent_ranking.WINDOW == 300
    assert parent_ranking.WINDOW_DRAW_COUNT == 300
    assert parent_ranking.OLDER_DRAW_COUNT == 150
    assert parent_ranking.RECENT_DRAW_COUNT == 150
    assert all(isinstance(value, Fraction) for value in raw)
    assert bayesian_parent.PRIOR_ALPHA == 6
    assert bayesian_parent.PRIOR_BETA == 43
    assert Fraction(1, 2) == bayesian_parent.MODEL_PRIOR_M0
    assert Fraction(1, 2) == bayesian_parent.MODEL_PRIOR_M1
    assert bayesian_parent.BAYES_WINDOWS == (50, 300, 750)
    assert bayesian_parent.GLOBAL_RENORMALIZATION_RULE == "NONE"

    m0 = bayesian_parent.beta_evidence(6, 43, 20, 300)
    m1 = bayesian_parent.beta_evidence(6, 43, 10, 150) ** 2
    posterior_m1 = m1 / (m0 + m1)
    predictive_m0 = Fraction(6 + 20, 49 + 300)
    predictive_m1 = Fraction(6 + 10, 49 + 150)
    expected = (1 - posterior_m1) * predictive_m0 + posterior_m1 * predictive_m1
    assert bayesian_parent.calculate_bma_predictive(
        (1 - posterior_m1,) * 49,
        (posterior_m1,) * 49,
        (predictive_m0,) * 49,
        (predictive_m1,) * 49,
    )[0] == expected


def test_bayesian_parent_tie_break_is_posterior_then_predictive_then_number() -> None:
    raw = [Fraction(0, 1)] * 49
    posterior = [Fraction(0, 1)] * 49
    predictive = [Fraction(0, 1)] * 49
    raw[0] = raw[1] = Fraction(1, 1)
    posterior[0] = Fraction(1, 4)
    posterior[1] = Fraction(3, 4)
    ranking = batch.rank_bayesian_scores(raw, posterior, predictive)
    assert ranking.ORDERED_NUMBERS[:2] == (2, 1)

    posterior[0] = posterior[1] = Fraction(1, 4)
    predictive[0] = Fraction(1, 2)
    predictive[1] = Fraction(3, 4)
    ranking = batch.rank_bayesian_scores(raw, posterior, predictive)
    assert ranking.ORDERED_NUMBERS[:2] == (2, 1)


def test_spectral_parent_300_component_parity_and_exact_formula_are_preserved() -> None:
    history = _history(756)
    raw = batch.calculate_signal_fourier_raw_scores(history, 756)
    components = batch.calculate_signal_fourier_components(history, 756)
    parent_ranking = spectral_parent.calculate_window_rankings(history, 756, 300)
    assert raw == parent_ranking.SPECTRAL_IPRS
    assert components == parent_ranking.NORMALIZED_RANKS
    assert batch.calculate_signal_fourier_ranking(history, 756).ORDERED_NUMBERS == (
        parent_ranking.ORDERED_NUMBERS
    )
    assert parent_ranking.WINDOW == 300
    assert parent_ranking.WINDOW_DRAW_COUNT == 300
    assert all(isinstance(value, Fraction) for value in raw)
    autocorrelation = (Fraction(2, 1), Fraction(0, 1), Fraction(-2, 1), Fraction(0, 1))
    assert spectral_parent.spectral_ipr_from_circular_autocorrelation(autocorrelation) == (
        Fraction(1, 2)
    )
    assert batch.COMPONENT_SCORE_DOMAIN_2.endswith("NONNEGATIVE")


def test_spectral_ties_use_peak_autocorrelation_then_number() -> None:
    raw = [Fraction(0, 1)] * 49
    peaks = [Fraction(0, 1)] * 49
    raw[0] = raw[1] = Fraction(1, 1)
    peaks[0] = Fraction(1, 4)
    peaks[1] = Fraction(3, 4)
    ranking = batch.rank_signal_fourier_scores(raw, peaks)
    assert ranking.ORDERED_NUMBERS[:2] == (2, 1)
    assert ranking.normalized_rank(2) == Fraction(48, 48)
    assert all(isinstance(value, Fraction) for value in ranking.NORMALIZED_RANKS)


def test_minimum_history_and_malformed_history_gates() -> None:
    with pytest.raises(batch.InsufficientHistoryError, match="insufficient history"):
        batch.calculate_pairwise_ranking(_history(750), 750)
    accepted = batch.calculate_pairwise_ranking(_history(751), 751)
    assert len(accepted.RANKED_NUMBERS) == 49

    malformed = list(_history(751))
    malformed[10] = (1, 2, 3, 4, 5, 5)
    with pytest.raises(ValueError, match="six unique"):
        batch.calculate_pairwise_ranking(malformed, 751)


def test_target_row_future_suffix_and_caller_history_are_excluded() -> None:
    prefix = _history(751)
    expected = batch.produce_candidate_portfolio(prefix, 751)
    with_target_and_future = (*prefix, (44, 45, 46, 47, 48, 49), object())
    with_different_target_and_future = (*prefix, (7, 8, 9, 10, 11, 12), _FILLER)
    assert batch.produce_candidate_portfolio(with_target_and_future, 751) == expected
    assert (
        batch.produce_candidate_portfolio(with_different_target_and_future, 751)
        == expected
    )

    history = [list(draw) for draw in prefix]
    snapshot = [row.copy() for row in history]
    assert batch.produce_candidate_portfolio(history, 751) == expected
    assert batch.produce_candidate_portfolio(iter(history), 751) == expected
    assert history == snapshot


def test_parent_window_ends_at_target_and_no_short_history_fallback_exists() -> None:
    history = list(_history(751))
    bayesian_baseline = batch.calculate_bayesian_raw_scores(history, 751)
    history[450] = (9, 10, 11, 12, 13, 14)
    assert batch.calculate_bayesian_raw_scores(history, 751) == bayesian_baseline
    history[451] = (9, 10, 11, 12, 13, 14)
    assert batch.calculate_bayesian_raw_scores(history, 751) != bayesian_baseline

    with pytest.raises(ValueError, match="target_index must not exceed"):
        batch.calculate_pairwise_ranking(_history(751), 752)


def test_component_normalization_is_exact_and_parent_ties_are_deterministic() -> None:
    raw = [Fraction(0, 1)] * 49
    raw[0] = raw[1] = Fraction(1, 1)
    bayesian_ranking = batch.rank_bayesian_scores(raw)
    assert bayesian_ranking.ORDERED_NUMBERS[:2] == (1, 2)
    assert bayesian_ranking.position(1) == 1
    assert bayesian_ranking.position(2) == 2
    assert bayesian_ranking.normalized_rank(1) == Fraction(48, 48)
    assert bayesian_ranking.normalized_rank(2) == Fraction(47, 48)
    assert bayesian_ranking.normalized_rank(49) == Fraction(0, 1)
    assert all(isinstance(value, Fraction) for value in bayesian_ranking.NORMALIZED_RANKS)

    with pytest.raises(TypeError, match="exact Fraction"):
        batch.rank_pairwise_scores(
            [0.1] + [Fraction(0, 1)] * 48,
            [Fraction(0, 1)] * 49,
        )


def test_fusion_weights_formula_and_final_tie_break_are_exact() -> None:
    bayesian, spectral = _component_fixture(
        bayesian_number_1=Fraction(3, 4),
        bayesian_number_2=Fraction(1, 2),
        spectral_number_1=Fraction(0, 1),
        spectral_number_2=Fraction(1, 1),
    )
    ranking = batch.rank_pairwise_scores(bayesian, spectral)
    assert Fraction(1, 2) == batch.FUSION_WEIGHT_1
    assert Fraction(1, 2) == batch.FUSION_WEIGHT_2
    assert ranking.pairwise_score(1) == Fraction(3, 8)
    assert ranking.pairwise_score(2) == Fraction(3, 4)
    assert ranking.RANKED_NUMBERS[0] == 2
    assert batch.FUSION_FORMULA == (
        "PAIRWISE_SCORE(n)=1/2*BAYESIAN_BMA_NORMALIZED_RANK_300(n)+"
        "1/2*SIGNAL_FOURIER_NORMALIZED_RANK_300(n);EXACT_RATIONAL"
    )

    bayesian = [Fraction(0, 1)] * 49
    spectral = [Fraction(0, 1)] * 49
    bayesian[0], spectral[0] = Fraction(1, 1), Fraction(0, 1)
    bayesian[1], spectral[1] = Fraction(3, 4), Fraction(1, 4)
    bayesian[2], spectral[2] = Fraction(1, 4), Fraction(3, 4)
    tied = batch.rank_pairwise_scores(bayesian, spectral)
    assert tied.pairwise_score(1) == tied.pairwise_score(2)
    assert tied.RANKED_NUMBERS[:3] == (2, 3, 1)


def test_each_parent_can_change_fused_order_and_pair_is_not_singleton() -> None:
    zeros = [Fraction(0, 1)] * 49
    changed_bayesian = zeros.copy()
    changed_bayesian[4] = Fraction(1, 1)
    changed_spectral = zeros.copy()
    changed_spectral[6] = Fraction(1, 1)
    baseline = batch.rank_pairwise_scores(zeros, zeros)
    assert batch.rank_pairwise_scores(changed_bayesian, zeros).RANKED_NUMBERS[0] == 5
    assert batch.rank_pairwise_scores(zeros, changed_spectral).RANKED_NUMBERS[0] == 7
    assert baseline.RANKED_NUMBERS[0] == 1

    bayesian = zeros.copy()
    spectral = zeros.copy()
    bayesian[0] = Fraction(1, 1)
    bayesian[2] = Fraction(3, 4)
    spectral[1] = Fraction(1, 1)
    spectral[2] = Fraction(3, 4)
    pairwise = batch.rank_pairwise_scores(bayesian, spectral)
    bayesian_only = batch.rank_pairwise_scores(bayesian, zeros)
    spectral_only = batch.rank_pairwise_scores(zeros, spectral)
    assert pairwise.RANKED_NUMBERS != bayesian_only.RANKED_NUMBERS
    assert pairwise.RANKED_NUMBERS != spectral_only.RANKED_NUMBERS
    assert pairwise.RANKED_NUMBERS[0] == 3


def test_both_parent_callables_feed_pairwise_implementation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    history = _history(751)
    bayesian, spectral = _component_fixture(
        bayesian_number_1=Fraction(1, 1),
        spectral_number_2=Fraction(1, 1),
    )
    calls: list[str] = []

    def fake_bayesian(_history: object, _target_index: int) -> tuple[Fraction, ...]:
        calls.append("bayesian")
        return tuple(bayesian)

    def fake_spectral(_history: object, _target_index: int) -> tuple[Fraction, ...]:
        calls.append("signal_fourier")
        return tuple(spectral)

    monkeypatch.setattr(batch, "calculate_bayesian_components", fake_bayesian)
    monkeypatch.setattr(batch, "calculate_signal_fourier_components", fake_spectral)
    result = batch.calculate_pairwise_ranking(history, 751)
    assert calls == ["bayesian", "signal_fourier"]
    assert result.bayesian_component(1) == Fraction(1, 1)
    assert result.signal_fourier_component(2) == Fraction(1, 1)
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
