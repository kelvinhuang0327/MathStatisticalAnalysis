from __future__ import annotations

import copy
import importlib.util
import json

import pytest

from lottolab.domain.b649_next_undrawn_forecast import (
    OBJECTIVE,
    RANKING_POLICY_VERSION,
    digest,
)
from lottolab.domain.prospective_observer import ProducerDependency, ProducerFingerprint
from lottolab.domain.research_live_forecast import NATIVE_STREAM_VERSION, canonical_json

if (
    importlib.util.find_spec("lottolab.infrastructure.b649_v6_native_input_adapter_candidate")
    is not None
):
    from lottolab.infrastructure.b649_v6_native_input_adapter_candidate import (
        adapt_native_input,
    )
else:
    from native_input_adapter_candidate import adapt_native_input

STRATEGIES = [
    {
        "strategy_id": "legacy_biglotto__backtest_big_lotto_orthogonal_5bet__c4dff46c5a5e",
        "strategy_version": "v0.1",
        "native_k": 5,
        "generator_identity": "fixture.orthogonal:Adapter",
        "tickets": [
            [1, 4, 9, 16, 25, 36],
            [2, 8, 14, 23, 35, 47],
            [3, 10, 17, 24, 33, 48],
            [5, 11, 19, 26, 38, 49],
            [6, 13, 20, 29, 41, 46],
        ],
    },
    {
        "strategy_id": "legacy_composite__quick_predict_5bet_ts3_markov_freqort",
        "strategy_version": "v0.1",
        "native_k": 5,
        "generator_identity": "fixture.composite:Adapter",
        "tickets": [
            [1, 4, 9, 16, 25, 36],
            [1, 7, 13, 22, 34, 45],
            [4, 10, 18, 27, 39, 48],
            [5, 12, 21, 30, 37, 49],
            [6, 15, 23, 32, 40, 46],
        ],
    },
    {
        "strategy_id": "legacy_biglotto__predict_5me_115000004__8a1c06ce1bdd",
        "strategy_version": "v0.1",
        "native_k": 5,
        "generator_identity": "fixture.five_me:Adapter",
        "tickets": [
            [1, 4, 9, 16, 25, 36],
            [2, 11, 17, 24, 33, 45],
            [3, 12, 20, 28, 37, 49],
            [5, 13, 22, 31, 39, 47],
            [6, 14, 23, 30, 41, 48],
        ],
    },
]


def _fixture() -> tuple[dict[str, object], dict[str, object]]:
    strategy_ids = [str(row["strategy_id"]) for row in STRATEGIES]
    adapter_paths = {
        strategy_id: f"fixture://adapters/{index}"
        for index, strategy_id in enumerate(strategy_ids, start=1)
    }
    adapter_shas = {strategy_id: digest(adapter_paths[strategy_id]) for strategy_id in strategy_ids}

    catalog = [
        {
            "strategy_id": strategy["strategy_id"],
            "version": strategy["strategy_version"],
            "native_k": strategy["native_k"],
            "adapter_source_path": adapter_paths[str(strategy["strategy_id"])],
            "adapter_source_sha256": adapter_shas[str(strategy["strategy_id"])],
        }
        for strategy in STRATEGIES
    ]
    catalog.sort(key=lambda row: str(row["strategy_id"]))

    configs: list[dict[str, object]] = []
    for index, strategy in enumerate(STRATEGIES):
        strategy_id = str(strategy["strategy_id"])
        stochastic = index == 2
        rng = {
            "behavior": "SEEDED_STOCHASTIC" if stochastic else "DETERMINISTIC",
            "seed": 2187 if stochastic else None,
            "rng_source": "fixture.random.Random" if stochastic else "fixture.deterministic",
            "rng_state_rule": "fixture explicit seed" if stochastic else "no RNG state",
            "configuration": "fixture-rng-v1",
            "prestate_dependency": "causal_history_and_explicit_seed"
            if stochastic
            else "causal_history_only",
        }
        configs.append(
            {
                "strategy_id": strategy_id,
                "strategy_version": strategy["strategy_version"],
                "native_k": strategy["native_k"],
                "parameters": {"seed": 2187} if stochastic else {"fixture_mode": "deterministic"},
                "rng_semantics": rng,
            }
        )
        strategy["rng_semantics"] = rng
        strategy["adapter_source_path"] = adapter_paths[strategy_id]
        strategy["adapter_source_sha256"] = adapter_shas[strategy_id]
    configs.sort(key=lambda row: str(row["strategy_id"]))

    history = [
        {
            "lottery_type": "BIG_LOTTO",
            "draw_number": "990000001",
            "draw_date": "2030-01-02",
            "main_numbers": [1, 2, 3, 4, 5, 6],
            "special_number": 7,
        },
        {
            "lottery_type": "BIG_LOTTO",
            "draw_number": "990000002",
            "draw_date": "2030-01-03",
            "main_numbers": [8, 9, 10, 11, 12, 13],
            "special_number": 14,
        },
    ]
    history_sha = digest(history)
    target = {
        "lottery_type": "BIG_LOTTO",
        "target_draw_number": "990000003",
        "target_draw_date": "2030-01-05",
        "scheduled_at": "2030-01-05T20:30:00+08:00",
        "timezone": "Asia/Taipei",
        "data_cutoff": "990000002",
        "forecast_horizon": 1,
        "history_draw_count": 2,
        "causal_history_sha256": history_sha,
        "schedule_authority_sha256": "6" * 64,
    }
    producer = ProducerFingerprint.create(
        producer_id="synthetic-native-input-fixture",
        producer_version="v1",
        dependencies=(
            ProducerDependency(
                "fixture://native-runner",
                "7" * 64,
                "test-only native runner identity",
            ),
        ),
    )
    runtime_material: dict[str, object] = {
        "python": {
            "implementation": "CPython",
            "version": "3.13.8",
            "executable": "/fixture/python",
            "executable_sha256": "8" * 64,
        },
        "os": "fixture-os",
        "architecture": "fixture-arch",
        "dependencies": [
            {
                "name": "fixture-library",
                "locator": "fixture://runtime/library",
                "versions": {"fixture-library": "1"},
                "content_sha256": "9" * 64,
            }
        ],
    }
    runtime = {**runtime_material, "sha256": digest(runtime_material)}
    source_execution = {
        "repository": "fixture://source-repository",
        "commit": "1" * 40,
        "tree": "2" * 40,
        "loaded_code_sha256": "3" * 64,
        "pre_draw_proof_status": "LOCAL_ONLY",
    }
    history_snapshot = {
        "reference": f"research-live-history:sha256:{history_sha}",
        "draws": history,
        "sha256": history_sha,
    }
    effective_rows = [
        {
            "strategy_id": str(config["strategy_id"]),
            "strategy_version": str(config["strategy_version"]),
            "native_k": int(config["native_k"]),
            "parameters_json": canonical_json(config["parameters"]),
            "generation_config_sha256": digest(config),
            "status": "EXECUTED",
            "constructor_defaults": {},
            "instance_state": {},
        }
        for config in configs
    ]
    effective_material = {"strategies": effective_rows}
    effective = {**effective_material, "sha256": digest(effective_material)}
    rng_stages = [
        {
            "strategy_id": str(config["strategy_id"]),
            "stage": "NATIVE_GENERATION",
            "status": "EXECUTED",
            "rng_semantics": config["rng_semantics"],
            "seed_status": "EFFECTIVE_SEED_CAPTURED"
            if config["rng_semantics"]["behavior"] == "SEEDED_STOCHASTIC"
            else "NOT_APPLICABLE",
            "invocation_identity": "synthetic-run-1",
            "replicate": 1,
        }
        for config in configs
    ]
    observations = [
        {
            "strategy_id": str(config["strategy_id"]),
            "strategy_version": str(config["strategy_version"]),
            "native_k": int(config["native_k"]),
            "draw_number": draw["draw_number"],
            "draw_date": draw["draw_date"],
            "causal_history_sha256": digest(history[:index]),
            "generation_config_sha256": digest(config),
            "status": "EVALUATED",
            "producer_fingerprint": producer.digest,
            "tickets": next(
                row["tickets"] for row in STRATEGIES if row["strategy_id"] == config["strategy_id"]
            ),
        }
        for config in configs
        for index, draw in enumerate(history)
    ]
    observations.sort(key=lambda row: (str(row["strategy_id"]), str(row["draw_number"])))
    evidence_sha = digest(observations)
    ranking = {
        "objective": OBJECTIVE,
        "ranking_policy_version": RANKING_POLICY_VERSION,
        "evaluation_window": "FULL",
        "observations": observations,
        "evidence_payload_sha256": evidence_sha,
    }
    rng_semantics = {
        "stages": rng_stages,
        "reproducibility_boundary": "FIXED_SYNTHETIC_INPUTS_CODE_RUNTIME_CONFIG",
    }
    native_strategies = []
    for rank, strategy in enumerate(STRATEGIES, start=1):
        native_strategies.append(
            {
                "rank": rank,
                "strategy_id": strategy["strategy_id"],
                "strategy_version": strategy["strategy_version"],
                "native_k": strategy["native_k"],
                "generator_identity": strategy["generator_identity"],
                "adapter_source_path": strategy["adapter_source_path"],
                "adapter_source_sha256": strategy["adapter_source_sha256"],
                "rng_semantics": strategy["rng_semantics"],
                "tickets": [
                    {
                        "position": position,
                        "emitted_main_numbers": numbers,
                        "legal_main_numbers": numbers,
                        "predicted_special_number": None,
                    }
                    for position, numbers in enumerate(strategy["tickets"], start=1)
                ],
            }
        )
    native: dict[str, object] = {
        "schema_version": "NUMBER2_9_B649_NATIVE_PREDICTION_V1",
        "task_id": "SYNTHETIC_V6_NATIVE_INPUT_FIXTURE",
        "prediction_target": target["target_draw_number"],
        "generated_at_local": "2030-01-05T10:00:01+08:00",
        "pre_draw_proof_status": "LOCAL_ONLY",
        "target_106_source_rows_selected": False,
        "target_outcome": "UNOBSERVED_NOT_READ",
        "strategy_count_expected": 3,
        "strategy_count_generated": 3,
        "ticket_count_expected": 15,
        "ticket_count_generated": 15,
        "strategies": native_strategies,
    }
    context: dict[str, object] = {
        "target": target,
        "source_locator": "canonical-next-undrawn",
        "source_execution": source_execution,
        "runtime_manifest": runtime,
        "history_snapshot": history_snapshot,
        "producer": producer.canonical_dict(),
        "catalog": catalog,
        "generation_configs": configs,
        "effective_parameters": effective,
        "rng_semantics": rng_semantics,
        "ranking_evidence": ranking,
        "seeds": {strategy_ids[2]: 2187},
        "generation_started_at": "2030-01-05T10:00:00.000000Z",
        "generation_finished_at": "2030-01-05T10:00:01.000000Z",
    }
    return native, context


def test_complete_synthetic_input_executes_adapter_and_passes_v6_validator() -> None:
    native, context = _fixture()
    forecast = adapt_native_input(native, context)
    forecast.validate()
    assert forecast.provenance_class == "NATIVE_GENERATED"
    assert forecast.forecast_stream_id == "B649_NEXT_UNDRAWN_FORECAST"
    assert forecast.forecast_stream_version == NATIVE_STREAM_VERSION
    assert forecast.missing_provenance_json == "{}"
    assert forecast.original["generation_started_at"] == context["generation_started_at"]
    assert forecast.original["generation_finished_at"] == context["generation_finished_at"]
    assert forecast.target["target_draw_number"] == "990000003"
    assert forecast.target["data_cutoff"] == "990000002"
    source_execution = json.loads(forecast.original["source_execution_json"])
    assert source_execution["commit"] == "1" * 40
    assert source_execution["tree"] == "2" * 40
    payload = json.loads(forecast.payload_bytes)
    assert payload["source_proof_status"] == "LOCAL_ONLY"
    assert payload["fixture_only"] is False
    assert len(payload["native_strategies"]) == 3
    assert [row["strategy_id"] for row in payload["native_strategies"]] == [
        row["strategy_id"] for row in native["strategies"]
    ]
    assert [row["source_rank"] for row in payload["native_strategies"]] == [1, 2, 3]
    k5_buckets = [row for row in payload["buckets"] if row["native_k"] == 5]
    assert len(k5_buckets) == 3
    assert [len(row["tickets"]) for row in k5_buckets] == [5, 5, 5]
    copied_positions = [
        (
            strategy["strategy_id"],
            strategy["strategy_version"],
            position["position"],
            position["numbers"],
        )
        for strategy in payload["native_strategies"]
        for position in strategy["native_positions"]
    ]
    source_positions = [
        (
            strategy["strategy_id"],
            strategy["strategy_version"],
            ticket["position"],
            ticket["emitted_main_numbers"],
        )
        for strategy in native["strategies"]
        for ticket in strategy["tickets"]
    ]
    assert copied_positions == source_positions
    assert len(copied_positions) == 15
    assert sum(position[3] == source_positions[0][3] for position in copied_positions) == 3
    assert all(
        len(numbers) == 6 and len(set(numbers)) == 6 for _, _, _, numbers in copied_positions
    )
    assert "issued_at" not in payload and "committed_at" not in payload
    assert "issued_at" not in forecast.target and "committed_at" not in forecast.target


def test_real_pred106_artifact_without_complete_context_is_rejected() -> None:
    from pathlib import Path

    source = Path(
        "/Users/kelvin/VibeCoding-WorkSpace/.task-data/20261117/NUMBER2_9_B649_CUTOFF105_K5_TOP3_NATIVE_PRED106_20261117_R1/pred106_native_k5_top3.json"
    )
    native = json.loads(source.read_text(encoding="utf-8"))
    with pytest.raises(ValueError, match="complete v6 provenance context is required"):
        adapt_native_input(native, None)
    assert native["prediction_target"] == "115000106"
    assert native["pre_draw_proof_status"] == "LOCAL_ONLY"


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("source_tree", "source execution tree is required"),
        ("history_sha", "missing target binding: causal_history_sha256"),
        ("schedule", "missing target binding: schedule_authority_sha256"),
        ("rng", "missing RNG execution provenance: rng_source"),
        ("strategy", "strategy identity mismatch in catalog"),
        ("short_ticket", "native ticket count mismatch"),
        ("duplicate_number", "invalid six-number native ticket"),
        ("generation_time", "generation timestamps reversed"),
    ],
)
def test_invalid_inputs_are_observably_rejected(mutation: str, message: str) -> None:
    native, context = _fixture()
    native = copy.deepcopy(native)
    context = copy.deepcopy(context)
    if mutation == "source_tree":
        context["source_execution"].pop("tree")
    elif mutation == "history_sha":
        context["target"].pop("causal_history_sha256")
    elif mutation == "schedule":
        context["target"].pop("schedule_authority_sha256")
    elif mutation == "rng":
        for config in context["generation_configs"]:
            config["rng_semantics"].pop("rng_source")
        for strategy in native["strategies"]:
            strategy["rng_semantics"].pop("rng_source")
        for row in context["effective_parameters"]["strategies"]:
            config = next(
                item
                for item in context["generation_configs"]
                if item["strategy_id"] == row["strategy_id"]
            )
            row["generation_config_sha256"] = digest(config)
        context["effective_parameters"]["sha256"] = digest(
            {"strategies": context["effective_parameters"]["strategies"]}
        )
        for stage in context["rng_semantics"]["stages"]:
            config = next(
                item
                for item in context["generation_configs"]
                if item["strategy_id"] == stage["strategy_id"]
            )
            stage["rng_semantics"] = config["rng_semantics"]
    elif mutation == "strategy":
        native["strategies"][0]["strategy_version"] = "wrong-version"
    elif mutation == "short_ticket":
        native["strategies"][0]["tickets"].pop()
        native["ticket_count_generated"] -= 1
    elif mutation == "duplicate_number":
        native["strategies"][0]["tickets"][0]["emitted_main_numbers"] = [1, 1, 3, 4, 5, 6]
    elif mutation == "generation_time":
        context["generation_started_at"] = "2030-01-05T10:00:02.000000Z"
    with pytest.raises(ValueError, match=message):
        adapt_native_input(native, context)


def test_identity_and_effective_payload_digest_are_stable_and_scope_bound() -> None:
    native, context = _fixture()
    first = adapt_native_input(native, context)
    replay = adapt_native_input(copy.deepcopy(native), copy.deepcopy(context))
    assert (first.request_id, first.request_sha256, first.payload_sha256) == (
        replay.request_id,
        replay.request_sha256,
        replay.payload_sha256,
    )

    other_scope_native = copy.deepcopy(native)
    other_scope_context = copy.deepcopy(context)
    other_scope_context["target"]["target_draw_number"] = "990000004"
    other_scope_context["target"]["target_draw_date"] = "2030-01-06"
    other_scope_context["target"]["scheduled_at"] = "2030-01-06T20:30:00+08:00"
    other_scope_native["prediction_target"] = "990000004"
    other_scope = adapt_native_input(other_scope_native, other_scope_context)
    assert other_scope.target["target_draw_number"] != first.target["target_draw_number"]
    assert (other_scope.request_id, other_scope.payload_sha256) != (
        first.request_id,
        first.payload_sha256,
    )

    other_source_context = copy.deepcopy(context)
    other_source_context["source_execution"]["tree"] = "4" * 40
    other_source = adapt_native_input(copy.deepcopy(native), other_source_context)
    assert json.loads(other_source.original["source_execution_json"])["tree"] == "4" * 40
    assert (other_source.request_id, other_source.payload_sha256) != (
        first.request_id,
        first.payload_sha256,
    )


def test_source_proof_status_is_preserved_without_retroactive_timestamps() -> None:
    native, context = _fixture()
    forecast = adapt_native_input(native, context)
    payload = json.loads(forecast.payload_bytes)
    assert payload["source_proof_status"] == "LOCAL_ONLY"
    assert forecast.original["generation_started_at"] == context["generation_started_at"]
    assert forecast.original["generation_finished_at"] == context["generation_finished_at"]
    assert not any(key in payload for key in ("issued_at", "committed_at"))
