from __future__ import annotations

import copy
import json
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import cast

import pytest

from lottolab.research import (
    biglotto_cross_family_redundancy_pruned_ensemble_v1_candidate_batch_r1 as batch,
)

Ticket = tuple[int, int, int, int, int, int]


def _ticket(seed: int) -> Ticket:
    start = ((seed - 1) % 44) + 1
    return cast(Ticket, tuple(range(start, start + 6)))


def _tickets(seed: int, count: int) -> tuple[Ticket, ...]:
    return tuple(_ticket(seed + index) for index in range(count))


def _parent_portfolios(budget: int = 5) -> dict[str, tuple[Ticket, ...]]:
    return {
        "CONDITIONAL_COOCCURRENCE": _tickets(1, budget),
        "GRAPH_NETWORK": _tickets(1, budget),
        "MULTISCALE_FREQUENCY": _tickets(30, budget),
        "MULTISCALE_OMISSION_PRESSURE": _tickets(15, budget),
    }


def _history(length: int = 751) -> tuple[object, ...]:
    return tuple(object() for _ in range(length))


def _copy_snapshot() -> dict[str, object]:
    return copy.deepcopy(dict(batch.DEFAULT_AUTHORITY_SNAPSHOT))


def _sealed_snapshot(mutator: Callable[[dict[str, object]], None]) -> dict[str, object]:
    snapshot = _copy_snapshot()
    mutator(snapshot)
    return batch.seal_authority_snapshot(snapshot)


def test_valid_authority_snapshot_is_complete_and_pinned() -> None:
    binding = batch.bind_authority(batch.DEFAULT_AUTHORITY_SNAPSHOT)

    assert binding.SNAPSHOT_ID == batch.AUTHORITY_SNAPSHOT_ID
    assert binding.SCHEMA_VERSION == batch.AUTHORITY_SCHEMA_VERSION
    assert binding.METHODOLOGY_VERSION == batch.AUTHORITY_METHODOLOGY_VERSION
    assert binding.RETAINED_FAMILIES == (
        "CONDITIONAL_COOCCURRENCE",
        "GRAPH_NETWORK",
        "MULTISCALE_OMISSION_PRESSURE",
    )
    assert binding.PRUNED_FAMILIES == ("MULTISCALE_FREQUENCY",)
    assert len(cast(list[object], binding.SNAPSHOT["CLASSIFICATION_CELLS"])) == 54


def test_missing_authority_fails_closed() -> None:
    with pytest.raises(batch.AuthorityUnavailableError):
        batch.bind_authority(None)
    with pytest.raises(batch.AuthorityUnavailableError):
        batch.produce_candidate_portfolio(
            batch.CANDIDATE_IDS[0],
            _history(),
            751,
            parent_portfolios=_parent_portfolios(),
            authority_snapshot=None,
        )


def test_authority_schema_or_sha_mismatch_fails_closed() -> None:
    wrong_version = _copy_snapshot()
    wrong_version["SCHEMA_VERSION"] = "WRONG_VERSION"
    with pytest.raises(batch.AuthorityMismatchError, match="schema/version"):
        batch.bind_authority(wrong_version)

    wrong_sha = _copy_snapshot()
    wrong_sha["AUTHORITY_SHA256"] = "0" * 64
    with pytest.raises(batch.AuthorityMismatchError, match="semantic SHA"):
        batch.bind_authority(wrong_sha)


def test_retained_family_membership_and_high_redundancy_pruning_are_frozen() -> None:
    assert batch.prune_families() == (
        "CONDITIONAL_COOCCURRENCE",
        "GRAPH_NETWORK",
        "MULTISCALE_OMISSION_PRESSURE",
    )
    assert batch.DEFAULT_AUTHORITY_BINDING.PRUNED_FAMILIES == (
        "MULTISCALE_FREQUENCY",
    )


def test_exact_duplicate_is_a_valid_pruning_classification() -> None:
    def mark_exact(snapshot: dict[str, object]) -> None:
        cells = cast(list[dict[str, object]], snapshot["CLASSIFICATION_CELLS"])
        for cell in cells:
            if {cell["FAMILY_A"], cell["FAMILY_B"]} == {
                "GRAPH_NETWORK",
                "MULTISCALE_FREQUENCY",
            }:
                cell["CLASSIFICATION"] = "EXACT_DUPLICATE"

    snapshot = _sealed_snapshot(mark_exact)
    binding = batch.bind_authority(snapshot)
    assert binding.RETAINED_FAMILIES == batch.DEFAULT_AUTHORITY_BINDING.RETAINED_FAMILIES
    assert binding.PRUNED_FAMILIES == ("MULTISCALE_FREQUENCY",)


def test_renyi2_is_not_an_independent_family() -> None:
    assert batch.EXCLUDED_REFERENCE_FAMILY not in batch.INDEPENDENT_FAMILIES
    assert all(
        batch.EXCLUDED_REFERENCE_FAMILY not in family
        for family in batch.DEFAULT_AUTHORITY_BINDING.RETAINED_FAMILIES
    )
    parents = _parent_portfolios()
    parents[batch.EXCLUDED_REFERENCE_FAMILY] = _tickets(40, 5)  # type: ignore[index]
    with pytest.raises(batch.RequiredParentUnavailableError):
        batch.produce_candidate_portfolio(
            batch.CANDIDATE_IDS[0], _history(), 751, parent_portfolios=parents
        )


def test_no_within_cohort_refresh_is_allowed() -> None:
    binding = batch.DEFAULT_AUTHORITY_BINDING

    def alter_membership(snapshot: dict[str, object]) -> None:
        cells = cast(list[dict[str, object]], snapshot["CLASSIFICATION_CELLS"])
        for cell in cells:
            if {cell["FAMILY_A"], cell["FAMILY_B"]} == {
                "GRAPH_NETWORK",
                "MULTISCALE_FREQUENCY",
            }:
                cell["CLASSIFICATION"] = "PARTIAL_REDUNDANCY"
        snapshot["RETAINED_FAMILIES"] = list(batch.INDEPENDENT_FAMILIES)
        snapshot["PRUNED_FAMILIES"] = []
        snapshot["PRUNED_CLUSTERS"] = []

    changed = _sealed_snapshot(alter_membership)
    with pytest.raises(batch.AuthorityMismatchError):
        batch.assert_authority_unchanged(binding, changed)


def test_parent_union_deduplicates_exact_tickets_and_computes_cardinality() -> None:
    parents = _parent_portfolios(5)
    portfolio = batch.union_native_ticket_sets(
        parents,
        batch.DEFAULT_AUTHORITY_BINDING.RETAINED_FAMILIES,
        5,
    )

    assert len(portfolio) == 10
    assert len(portfolio) == len(set(portfolio))
    assert portfolio[:5] == parents["CONDITIONAL_COOCCURRENCE"]
    assert portfolio[5:] == parents["MULTISCALE_OMISSION_PRESSURE"]
    assert all(
        len(ticket) == 6
        and ticket == tuple(sorted(ticket))
        and len(set(ticket)) == 6
        and all(1 <= number <= 49 for number in ticket)
        for ticket in portfolio
    )


def test_candidate_output_is_valid_deterministic_and_excludes_pruned_parent() -> None:
    parents = _parent_portfolios(5)
    first = batch.produce_candidate_portfolio(
        batch.candidate_id_for(batch.CONSTRUCTOR_IDS[0], 5),
        _history(),
        751,
        parent_portfolios=parents,
    )
    second = batch.produce_candidate_portfolio(
        batch.candidate_id_for(batch.CONSTRUCTOR_IDS[0], 5),
        _history(),
        751,
        parent_portfolios=parents,
    )

    assert first == second
    assert len(first) == 10
    assert all(ticket not in parents["MULTISCALE_FREQUENCY"] for ticket in first)


def test_future_target_and_pruned_family_are_not_passed_to_parent_producers() -> None:
    calls: list[tuple[str, int, int]] = []
    parents = _parent_portfolios(5)
    providers: dict[str, object] = {}
    for family in batch.INDEPENDENT_FAMILIES:
        def provider(
            prefix: tuple[object, ...],
            target_index: int,
            constructor_id: str,
            budget: int,
            *,
            _family: str = family,
        ) -> tuple[Ticket, ...]:
            calls.append((_family, len(prefix), target_index))
            assert constructor_id == batch.CONSTRUCTOR_IDS[0]
            assert budget == 5
            return parents[_family]

        providers[family] = provider

    history = (*_history(), object(), ("unreadable",))
    result = batch.produce_candidate_portfolio(
        batch.candidate_id_for(batch.CONSTRUCTOR_IDS[0], 5),
        history,
        751,
        providers,
    )

    assert len(result) == 10
    assert calls == [
        (family, 751, 751)
        for family in batch.DEFAULT_AUTHORITY_BINDING.RETAINED_FAMILIES
    ]


def test_unavailable_required_parent_fails_closed() -> None:
    parents = _parent_portfolios(5)
    del parents["MULTISCALE_OMISSION_PRESSURE"]
    with pytest.raises(batch.RequiredParentUnavailableError, match="missing"):
        batch.produce_candidate_portfolio(
            batch.CANDIDATE_IDS[0], _history(), 751, parent_portfolios=parents
        )


def test_retained_only_parent_map_is_executable() -> None:
    parents = _parent_portfolios(5)
    retained_only = {
        family: parents[family]
        for family in batch.DEFAULT_AUTHORITY_BINDING.RETAINED_FAMILIES
    }

    result = batch.produce_candidate_portfolio(
        batch.CANDIDATE_IDS[0],
        _history(),
        751,
        parent_portfolios=retained_only,
    )

    assert result == batch.produce_candidate_portfolio(
        batch.CANDIDATE_IDS[0],
        _history(),
        751,
        parent_portfolios=parents,
    )


def test_default_concrete_parent_registry_is_exactly_retained() -> None:
    producers = batch.concrete_parent_producers()

    assert tuple(producers) == batch.DEFAULT_AUTHORITY_BINDING.RETAINED_FAMILIES
    assert all(callable(provider) for provider in producers.values())


def test_insufficient_history_fails_before_parent_execution() -> None:
    with pytest.raises(batch.InsufficientHistoryError):
        batch.produce_candidate_portfolio(
            batch.CANDIDATE_IDS[0], _history(750), 750, parent_portfolios=_parent_portfolios()
        )


def test_candidate_identity_matrix_is_exact_and_semantically_stable() -> None:
    authorities_a = batch.build_candidate_authorities()
    authorities_b = batch.build_candidate_authorities()

    assert authorities_a == authorities_b
    assert len(authorities_a) == 9
    assert len({item.CANDIDATE_ID for item in authorities_a}) == 9
    assert len({item.SIGNATURE_HASH for item in authorities_a}) == 9
    assert all(item.CANDIDATE_ID.startswith("BMSGV1_XF_") for item in authorities_a)
    for metadata in authorities_a:
        identity = batch.derive_candidate_identity(metadata.SEMANTICS)
        assert identity.CANDIDATE_ID == metadata.CANDIDATE_ID
        assert identity.SIGNATURE_HASH == metadata.SIGNATURE_HASH

    changed = dict(authorities_a[0].SEMANTICS)
    changed["REQUESTED_BUDGET"] = 10
    assert batch.signature_hash_for_semantics(changed) != authorities_a[0].SIGNATURE_HASH


def test_authority_snapshot_can_be_rebuilt_from_frozen_classification_rows() -> None:
    rows = cast(
        Sequence[Mapping[str, object]],
        batch.DEFAULT_AUTHORITY_SNAPSHOT["CLASSIFICATION_CELLS"],
    )
    rebuilt = batch.build_authority_snapshot_from_classification_rows(rows)
    assert batch.bind_authority(rebuilt).SNAPSHOT_SHA256 == (
        batch.DEFAULT_AUTHORITY_BINDING.SNAPSHOT_SHA256
    )


def test_artifact_generation_is_exactly_repeatable(tmp_path: Path) -> None:
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    batch.write_candidate_batch_artifacts(first_root)
    batch.write_candidate_batch_artifacts(second_root)

    names = {
        "source_universe_contract.json",
        "redundancy_authority_snapshot.json",
        "candidate_authority.csv",
        "candidate_validation_handoff.csv",
        "candidate_batch_manifest.json",
        "SHA256SUMS",
    }
    assert {path.name for path in first_root.iterdir()} == names
    assert {path.name for path in second_root.iterdir()} == names
    assert {
        name: (first_root / name).read_bytes() for name in names
    } == {name: (second_root / name).read_bytes() for name in names}

    manifest = json.loads(
        (first_root / "candidate_batch_manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["CANDIDATE_MATRIX"]["COUNT"] == 9
    assert manifest["HISTORICAL_VALIDATION"] == "NOT_RUN_BY_DESIGN"
    assert manifest["AUTHORITY"]["WITHIN_COHORT_REFRESH_ALLOWED"] is False
