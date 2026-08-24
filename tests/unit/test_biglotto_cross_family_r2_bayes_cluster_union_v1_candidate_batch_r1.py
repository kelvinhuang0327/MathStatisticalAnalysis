from __future__ import annotations

import hashlib
import inspect
import subprocess
import sys
from functools import cache
from pathlib import Path
from types import ModuleType
from typing import cast

import pytest

from lottolab.research import (
    biglotto_cross_family_r2_bayes_cluster_union_v1_candidate_batch_r1 as subject,
)
from lottolab.research import biglotto_multi_ticket_constructors_r1 as constructors
from lottolab.research import (
    biglotto_multiscale_bayes_changepoint_bma_multi_ticket_candidate_batch_r1 as bayes,
)
from lottolab.research import (
    biglotto_multiscale_temporal_profile_cluster_multi_ticket_candidate_batch_r1 as cluster,
)

EXPECTED_AUTHORITY = (
    (
        "BMSGV1_BCU_4e7d61f26f300458",
        "4e7d61f26f3004585a8e90474efff094ef8d4b47b804ecc2c85d7fbc5b526574",
        "LOW_OVERLAP",
        5,
        "BMSGV1_BY_c5baba803a5b02b2",
        "c5baba803a5b02b2237f12396d9704257766bc38c312a895b69bc70c749b874a",
        "BMSGV1_CL_87042665810ec02e",
        "87042665810ec02ec623eb1ac7e797a5bbc2ff3dd470b1554898c8308c58db10",
    ),
    (
        "BMSGV1_BCU_6d1c587273d742e3",
        "6d1c587273d742e33373616914388a03525160144be432a073ea058be246f56a",
        "LOW_OVERLAP",
        10,
        "BMSGV1_BY_2d6a81202848d0dc",
        "2d6a81202848d0dcae17519a570b60fba21e5a7ed894749419f1196850132f4b",
        "BMSGV1_CL_00fcf892ae80281e",
        "00fcf892ae80281e9339e87f1816c38d9605d61f29f93f3aef090d42f1a325c5",
    ),
    (
        "BMSGV1_BCU_7f162cc77d7e46e5",
        "7f162cc77d7e46e59c2a46672dddcca8020d1811c1d5a0a5438adff63279676a",
        "LOW_OVERLAP",
        20,
        "BMSGV1_BY_88b5bf7d96119f7e",
        "88b5bf7d96119f7ebcfd1a02dfce8bb62fab543c4faf332a5b5d665937fa10e9",
        "BMSGV1_CL_921b703832dc3a71",
        "921b703832dc3a715d702b80a6a02e3efd344244bec0f3f3f90cc0eba5064853",
    ),
    (
        "BMSGV1_BCU_5d32cca92cf6c7ea",
        "5d32cca92cf6c7eac0bc16e52b80dc0a185b8a540b33be7f83bdf56ebd49d0cc",
        "EXPOSURE_BALANCED",
        5,
        "BMSGV1_BY_e5cf21a37b8aa958",
        "e5cf21a37b8aa9587603ac8304c6c07077c800de4a144a6d2bfa47e1209b0c60",
        "BMSGV1_CL_7296027ce0f0fc75",
        "7296027ce0f0fc7518eb77c76bf7b25cecc20859adb0ed3ca6250ad495d7e96a",
    ),
    (
        "BMSGV1_BCU_052424120e14ec66",
        "052424120e14ec666a835894eced835ce0410a55e0f82ec46590a23dceeeebba",
        "EXPOSURE_BALANCED",
        10,
        "BMSGV1_BY_7c0307f6bbcd9e11",
        "7c0307f6bbcd9e117ef23955a42c1d9616a3ca4b5f575ab3e8f148dbe81553c7",
        "BMSGV1_CL_d07a0be23e8057a3",
        "d07a0be23e8057a381649a18f3a7ab229175e6c16ff2b5bdb695095cc4e66d3a",
    ),
    (
        "BMSGV1_BCU_d45edd29a192b37d",
        "d45edd29a192b37d73ab125cf6c991bd6d03371b530c72aeea6e1c286aa9db70",
        "EXPOSURE_BALANCED",
        20,
        "BMSGV1_BY_ab3fbabb0bfe27c3",
        "ab3fbabb0bfe27c3e912f63a34205157459461006ac94b1114665da39f8adadd",
        "BMSGV1_CL_2b9226c777b5110d",
        "2b9226c777b5110d9f85f7e5fb410c03556a1943d250f729b68b0e28bf898674",
    ),
    (
        "BMSGV1_BCU_636542e0273b2706",
        "636542e0273b27061a90d9d3e9f84324840aecbc956f899a4d28a26076d8a1ae",
        "HYBRID_DIVERSITY",
        5,
        "BMSGV1_BY_c74d0be13ed84609",
        "c74d0be13ed84609e29192131222ece975729ba4f88d74fd20eab2c128dc6b44",
        "BMSGV1_CL_85ad12e9aea85ca6",
        "85ad12e9aea85ca6b9f56cbf96ddb83e30d3f5d7f90d664f77c1e1225504e387",
    ),
    (
        "BMSGV1_BCU_e57e85d0095f138e",
        "e57e85d0095f138e6b2e249075de9dbee1e2a3520c4d525d74d3b0f53763d44d",
        "HYBRID_DIVERSITY",
        10,
        "BMSGV1_BY_83004ab5716e2b4f",
        "83004ab5716e2b4fcb4222dfeabcfe8c9232bb6f83c01afe3434e8df976db752",
        "BMSGV1_CL_b4b88dc1416e46e9",
        "b4b88dc1416e46e92a46fb6b69fe56697313acd426b9d22dc8428a681e385262",
    ),
    (
        "BMSGV1_BCU_44934fb9b3c30499",
        "44934fb9b3c30499ae36dfe41f11100645c5e5890b3f5edf18bfbc4c52d1d445",
        "HYBRID_DIVERSITY",
        20,
        "BMSGV1_BY_6bfe10141393a016",
        "6bfe10141393a016a1dec3526b2616095607614b5fed9f9cac1afc6a259718f2",
        "BMSGV1_CL_7b825e5de2dd1c4b",
        "7b825e5de2dd1c4be0def6985b7f23e3964573f6626ca07ea8ba91bec2c795e1",
    ),
)


def _module_sha256(module: ModuleType) -> str:
    return hashlib.sha256(Path(inspect.getfile(module)).read_bytes()).hexdigest()


@cache
def _generated_portfolios() -> tuple[subject.CandidatePortfolio, ...]:
    history = subject.build_synthetic_non_outcome_history()
    return tuple(
        subject.build_candidate_portfolio(candidate_id, history, len(history))
        for candidate_id in subject.CANDIDATE_IDS
    )


def _ticket(start: int) -> subject.Ticket:
    return cast(subject.Ticket, tuple(range(start, start + 6)))


def test_exact_nine_candidate_authority_and_parent_bindings() -> None:
    actual = tuple(
        (
            metadata.CANDIDATE_ID,
            metadata.SIGNATURE_HASH,
            metadata.CONSTRUCTOR,
            metadata.MATCHED_K,
            metadata.PARENT_A_CANDIDATE_ID,
            metadata.PARENT_A_SIGNATURE_HASH,
            metadata.PARENT_B_CANDIDATE_ID,
            metadata.PARENT_B_SIGNATURE_HASH,
        )
        for metadata in subject.CANDIDATE_AUTHORITIES
    )
    assert actual == EXPECTED_AUTHORITY
    assert len(subject.CANDIDATE_IDS) == 9
    assert len(set(subject.CANDIDATE_IDS)) == 9
    assert subject.SEMANTIC_VERSION == "B649_BAYES_CLUSTER_UNION_V1_41e6eefa2cbe0006"
    assert subject.CARDINALITY_MODE == "FULL_DEDUPLICATED_UNION"


def test_parent_support_is_byte_exact_authoritative_source() -> None:
    assert _module_sha256(constructors) == subject.SHARED_CONSTRUCTOR_SHA256
    assert _module_sha256(bayes) == subject.BAYES_PARENT_PRODUCER_SHA256
    assert _module_sha256(cluster) == subject.CLUSTER_PARENT_PRODUCER_SHA256
    assert bayes.MINIMUM_HISTORY == cluster.MINIMUM_HISTORY == subject.MINIMUM_HISTORY == 750
    subject.validate_frozen_parent_authority()


def test_all_nine_generations_preserve_full_union_contract() -> None:
    portfolios = _generated_portfolios()
    assert len(portfolios) == 9
    for metadata, portfolio in zip(
        subject.CANDIDATE_AUTHORITIES, portfolios, strict=True
    ):
        assert portfolio.CANDIDATE_ID == metadata.CANDIDATE_ID
        assert portfolio.SIGNATURE_HASH == metadata.SIGNATURE_HASH
        assert portfolio.MATCHED_K == metadata.MATCHED_K
        assert type(portfolio.PARENT_A_TICKETS) is tuple
        assert type(portfolio.PARENT_B_TICKETS) is tuple
        assert type(portfolio.TICKETS) is tuple
        assert len(portfolio.PARENT_A_TICKETS) == metadata.MATCHED_K
        assert len(portfolio.PARENT_B_TICKETS) == metadata.MATCHED_K
        assert len(set(portfolio.PARENT_A_TICKETS)) == metadata.MATCHED_K
        assert len(set(portfolio.PARENT_B_TICKETS)) == metadata.MATCHED_K
        assert tuple(
            sorted(set(portfolio.PARENT_A_TICKETS) | set(portfolio.PARENT_B_TICKETS))
        ) == portfolio.TICKETS
        assert metadata.MATCHED_K <= portfolio.FINAL_CARDINALITY <= 2 * metadata.MATCHED_K
        assert (
            len(set(portfolio.PARENT_A_TICKETS) & set(portfolio.PARENT_B_TICKETS))
        ) == portfolio.EXACT_DUPLICATE_COUNT
        assert len(portfolio.PROVENANCE) == portfolio.FINAL_CARDINALITY
        assert tuple(item.TICKET for item in portfolio.PROVENANCE) == portfolio.TICKETS
        assert all(type(ticket) is tuple for ticket in portfolio.TICKETS)
        assert all(type(number) is int for ticket in portfolio.TICKETS for number in ticket)
    assert subject.TRUNCATION == "NONE"
    assert subject.PADDING == "NONE"
    assert subject.RNG == "NONE"


def test_exact_ticket_dedup_and_parent_a_then_parent_b_provenance() -> None:
    tickets = tuple(_ticket(start) for start in (1, 7, 13, 19, 25, 31, 37, 43))
    parent_a = tickets[:5]
    parent_b = (tickets[3], tickets[4], tickets[5], tickets[6], tickets[7])
    union, provenance = subject.compose_full_deduplicated_union(parent_a, parent_b, 5)
    assert union == tickets
    assert len(union) == 8
    provenance_by_ticket = {item.TICKET: item.PARENTS for item in provenance}
    assert provenance_by_ticket[tickets[3]] == (
        "PARENT_A_BAYESIAN",
        "PARENT_B_CLUSTERING",
    )
    assert provenance_by_ticket[tickets[0]] == ("PARENT_A_BAYESIAN",)
    assert provenance_by_ticket[tickets[7]] == ("PARENT_B_CLUSTERING",)


def test_parent_contract_rejects_non_tuple_duplicate_and_noncanonical_tickets() -> None:
    tickets = tuple(_ticket(start) for start in (1, 7, 13, 19, 25))
    with pytest.raises(ValueError, match="immutable tuple"):
        subject.compose_full_deduplicated_union(list(tickets), tickets, 5)
    with pytest.raises(ValueError, match="exactly K unique"):
        subject.compose_full_deduplicated_union(
            (tickets[0], tickets[0], *tickets[2:]), tickets, 5
        )
    malformed = cast(subject.Ticket, (1, 2, 3, 4, 5, True))
    with pytest.raises(ValueError, match="built-in integers"):
        subject.compose_full_deduplicated_union(
            (malformed, *tickets[1:]), tickets, 5
        )


def test_unknown_identity_and_minimum_history_fail_closed() -> None:
    history = subject.build_synthetic_non_outcome_history()
    with pytest.raises(KeyError, match="unknown frozen candidate ID"):
        subject.produce_candidate_portfolio("BMSGV1_BCU_UNKNOWN", history, len(history))
    with pytest.raises(subject.InsufficientHistoryError, match="at least 750"):
        subject.produce_candidate_portfolio(subject.CANDIDATE_IDS[0], history[:749], 749)


def test_target_and_later_elements_are_not_read() -> None:
    history = subject.build_synthetic_non_outcome_history()
    expected = _generated_portfolios()[0].TICKETS
    history_with_invalid_target = (*history, object())
    actual = subject.produce_candidate_portfolio(
        subject.CANDIDATE_IDS[0], history_with_invalid_target, len(history)
    )
    assert actual == expected


def test_one_shot_history_is_materialized_once_for_identical_parent_input() -> None:
    history = subject.build_synthetic_non_outcome_history()
    expected = _generated_portfolios()[0].TICKETS
    actual = subject.produce_candidate_portfolio(
        subject.CANDIDATE_IDS[0], iter(history), len(history)
    )
    assert actual == expected


def test_parent_authority_mismatch_fails_before_generation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(bayes, "MINIMUM_HISTORY", 749)
    with pytest.raises(subject.AuthorityMismatchError, match="minimum history mismatch"):
        subject.validate_frozen_parent_authority()


def test_independent_process_double_generation_is_byte_equal() -> None:
    repository_root = Path(__file__).resolve().parents[2]
    command = [sys.executable, "-m", subject.IMPLEMENTATION_MODULE]
    first = subprocess.run(
        command,
        cwd=repository_root,
        check=False,
        capture_output=True,
        timeout=30,
    )
    second = subprocess.run(
        command,
        cwd=repository_root,
        check=False,
        capture_output=True,
        timeout=30,
    )
    expected = subject.canonical_synthetic_candidate_batch_bytes()
    assert first.returncode == second.returncode == 0
    assert first.stderr == second.stderr == b""
    assert first.stdout == second.stdout == expected
    assert hashlib.sha256(first.stdout).hexdigest() == (
        subject.canonical_synthetic_candidate_batch_sha256()
    )
