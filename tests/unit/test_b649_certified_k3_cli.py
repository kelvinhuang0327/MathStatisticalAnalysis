"""Focused contracts for the explicitly selected certified K3 CLI."""

from __future__ import annotations

import hashlib
import json

import pytest
from typer.testing import CliRunner

from lottolab.interfaces.cli.b649_certified_k3 import (
    CERTIFICATE_ID,
    CERTIFICATE_RESULT_SHA256,
    EXACT_PROBABILITY_FRACTION,
    EXACT_WIN7,
    GENERATOR_VERSION,
    PRODUCER_SOURCE_SHA256,
    PRODUCER_TASK_ID,
    STRATEGY_ID,
    build_certified_k3,
    build_cli_payload,
)
from lottolab.interfaces.cli.main import app

runner = CliRunner()
SAMPLE_TARGET_ID = "115000099"
SAMPLE_TICKETS = (
    (8, 12, 20, 23, 37, 40),
    (6, 16, 17, 30, 38, 45),
    (3, 7, 9, 19, 21, 39),
)


def _independent_oracle(target_id: str) -> tuple[tuple[int, ...], ...]:
    ranked = sorted(
        range(1, 50),
        key=lambda number: (
            hashlib.sha256(f"K3_CERTIFIED_R1|{target_id}|{number:02d}".encode()).digest(),
            number,
        ),
    )
    return tuple(
        tuple(sorted(ranked[start : start + 6]))
        for start in (0, 6, 12)
    )


def test_sample_matches_original_certified_producer_output() -> None:
    assert build_certified_k3(SAMPLE_TARGET_ID) == SAMPLE_TICKETS


def test_other_target_matches_independent_sha256_ordering_oracle() -> None:
    target_id = "115000100"
    assert build_certified_k3(target_id) == _independent_oracle(target_id)


def test_payload_preserves_fixed_identity_and_exact_math_contract() -> None:
    payload = build_cli_payload(SAMPLE_TARGET_ID)

    assert set(payload) == {
        "TARGET_ID",
        "STRATEGY_ID",
        "GENERATOR_VERSION",
        "TICKETS",
        "K",
        "COST_NTD",
        "EXACT_WIN7",
        "EXACT_PROBABILITY_FRACTION",
    }
    assert payload["STRATEGY_ID"] == STRATEGY_ID
    assert payload["GENERATOR_VERSION"] == GENERATOR_VERSION == "K3_CERTIFIED_R1"
    assert payload["K"] == 3
    assert payload["COST_NTD"] == 150
    assert payload["EXACT_WIN7"] == EXACT_WIN7 == 7_930_128
    assert payload["EXACT_PROBABILITY_FRACTION"] == EXACT_PROBABILITY_FRACTION
    assert EXACT_PROBABILITY_FRACTION == "7930128/85900584"
    assert PRODUCER_TASK_ID == "NUMBER2_C_K3_CERTIFIED_TICKET_PRODUCER_R1"
    assert PRODUCER_SOURCE_SHA256 == (
        "05753a903dfbdbdd21722f39256aabbfd7e79051983dd48494f6d44c5aa04327"
    )
    assert CERTIFICATE_ID == "NUMBER2_D_K3_GLOBAL_GEOMETRY_CERTIFICATE_R1"
    assert CERTIFICATE_RESULT_SHA256 == (
        "0c4f7e225975daec4ea3357b49d952f816313097e52064b8e3c120a6b4a17723"
    )


def test_tickets_are_legal_pairwise_disjoint_six_number_sets() -> None:
    tickets = build_certified_k3(SAMPLE_TARGET_ID)

    assert len(tickets) == 3
    assert all(len(ticket) == 6 for ticket in tickets)
    assert all(tuple(sorted(ticket)) == ticket for ticket in tickets)
    assert all(all(1 <= number <= 49 for number in ticket) for ticket in tickets)
    assert len({number for ticket in tickets for number in ticket}) == 18


def test_same_target_replays_identically() -> None:
    assert build_cli_payload(SAMPLE_TARGET_ID) == build_cli_payload(SAMPLE_TARGET_ID)


def test_registered_cli_outputs_required_json_for_sample_target() -> None:
    result = runner.invoke(app, ["b649-certified-k3", "--target-id", SAMPLE_TARGET_ID])
    repeated = runner.invoke(app, ["b649-certified-k3", "--target-id", SAMPLE_TARGET_ID])

    assert result.exit_code == 0, result.output
    assert repeated.exit_code == 0, repeated.output
    assert repeated.stdout == result.stdout
    payload = json.loads(result.stdout)
    assert payload["TARGET_ID"] == SAMPLE_TARGET_ID
    assert payload["TICKETS"] == [list(ticket) for ticket in SAMPLE_TICKETS]
    assert payload["EXACT_WIN7"] == 7_930_128
    assert payload["EXACT_PROBABILITY_FRACTION"] == "7930128/85900584"


@pytest.mark.parametrize(
    "target_id",
    [
        "11500009",
        "1150000990",
        "11500009x",
        "\uff11\uff11\uff15\uff10\uff10\uff10\uff10\uff19\uff19",
    ],
)
def test_cli_rejects_non_nine_ascii_digit_target_ids(target_id: str) -> None:
    result = runner.invoke(app, ["b649-certified-k3", "--target-id", target_id])

    assert result.exit_code == 2
    assert result.stdout == ""
    assert "exactly nine ASCII digits" in result.stderr


def test_root_cli_keeps_existing_commands_and_default_help_behavior() -> None:
    no_arguments = runner.invoke(app, [])
    help_result = runner.invoke(app, ["--help"])

    assert no_arguments.exit_code == 2
    assert "Usage:" in no_arguments.stdout
    assert help_result.exit_code == 0
    for command in (
        "b649-certified-k3",
        "info",
        "generate-bet",
        "generate-bet-portfolio",
        "t539-p638-schedule-certificate",
    ):
        assert command in help_result.stdout
