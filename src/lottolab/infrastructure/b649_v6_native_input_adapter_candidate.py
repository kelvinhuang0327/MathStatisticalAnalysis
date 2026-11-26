"""Task-local adapter candidate for complete B649 native prediction inputs.

This module deliberately stops at LiveForecastInput.validate(); it has no
repository or Scheduler dependency and cannot issue or commit a forecast.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from datetime import date
from typing import cast

from lottolab.domain.b649_next_undrawn_forecast import (
    OBJECTIVE,
    RANKING_POLICY_VERSION,
    ForecastIdentity,
    digest,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.prospective_observer import (
    ObservationTarget,
    ProducerDependency,
    ProducerFingerprint,
)
from lottolab.domain.research_live_forecast import (
    NATIVE_STREAM,
    NATIVE_STREAM_VERSION,
    ORIGINAL_FIELDS,
    LiveForecastInput,
    canonical_json,
    sha256,
)

NATIVE_INPUT_SCHEMA = "NUMBER2_9_B649_NATIVE_PREDICTION_V1"


def _json_clone(value: object, label: str) -> object:
    try:
        return json.loads(json.dumps(value, ensure_ascii=False, allow_nan=False))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be JSON-compatible") from exc


def _object(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return cast(dict[str, object], value)


def _array(value: object, label: str) -> list[object]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be an array")
    return value


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} is required")
    return value


def _sha(value: object, label: str) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ValueError(f"{label} must be a SHA-256")
    return value


def _producer(value: object) -> ProducerFingerprint:
    raw = _object(value, "producer")
    dependencies_raw = _array(raw.get("dependencies"), "producer.dependencies")
    dependencies: list[ProducerDependency] = []
    for index, item in enumerate(dependencies_raw):
        dependency = _object(item, f"producer.dependencies[{index}]")
        dependencies.append(
            ProducerDependency(
                _text(dependency.get("locator"), "producer dependency locator"),
                _sha(dependency.get("source_sha256"), "producer dependency source_sha256"),
                _text(dependency.get("load_bearing_role"), "producer dependency role"),
            )
        )
    return ProducerFingerprint(
        schema_version=_text(raw.get("schema_version"), "producer.schema_version"),
        producer_id=_text(raw.get("producer_id"), "producer.producer_id"),
        producer_version=_text(raw.get("producer_version"), "producer.producer_version"),
        dependencies=tuple(dependencies),
        digest=_sha(raw.get("digest"), "producer.digest"),
    )


def _require_history_binding(target: dict[str, object], history: dict[str, object]) -> list[object]:
    draws = _array(history.get("draws"), "history_snapshot.draws")
    if not draws:
        raise ValueError("complete causal history is required")
    history_sha = _sha(target.get("causal_history_sha256"), "target causal history SHA")
    if history.get("sha256") != history_sha or digest(draws) != history_sha:
        raise ValueError("history snapshot SHA does not match target binding")
    if type(target.get("history_draw_count")) is not int or target["history_draw_count"] != len(
        draws
    ):
        raise ValueError("history snapshot count does not match target binding")
    cutoff = _text(target.get("data_cutoff"), "target data_cutoff")
    target_number = _text(target.get("target_draw_number"), "target target_draw_number")
    previous_number = None
    previous_date: date | None = None
    target_date = date.fromisoformat(_text(target.get("target_draw_date"), "target date"))
    for index, item in enumerate(draws):
        row = _object(item, f"history_snapshot.draws[{index}]")
        if row.get("lottery_type") != LotteryType.BIG_LOTTO.value:
            raise ValueError("history snapshot contains a non-BIG_LOTTO draw")
        draw_number = _text(row.get("draw_number"), "history draw number")
        draw_date = date.fromisoformat(_text(row.get("draw_date"), "history draw date"))
        if int(draw_number) >= int(target_number) or draw_date >= target_date:
            raise ValueError("causal history includes the target or a later draw")
        if previous_number is not None and int(draw_number) <= int(previous_number):
            raise ValueError("history draws must be in strictly increasing issue order")
        if previous_date is not None and draw_date <= previous_date:
            raise ValueError("history dates must be strictly increasing")
        previous_number = draw_number
        previous_date = draw_date
    if previous_number != cutoff or int(cutoff) >= int(target_number):
        raise ValueError("cutoff must be the final causal draw before target")
    return draws


def _native_rows(
    native: dict[str, object],
    catalog: list[object],
    configs: list[object],
) -> tuple[list[dict[str, object]], list[list[dict[str, object]]]]:
    strategies_raw = _array(native.get("strategies"), "native strategies")
    if not strategies_raw:
        raise ValueError("native strategies are required")
    catalog_by_id = {
        str(_object(item, "catalog strategy").get("strategy_id")): _object(item, "catalog strategy")
        for item in catalog
    }
    config_by_id = {
        str(_object(item, "generation config").get("strategy_id")): _object(
            item, "generation config"
        )
        for item in configs
    }
    if len(catalog_by_id) != len(catalog) or len(config_by_id) != len(configs):
        raise ValueError("duplicate catalog or generation-config identity")
    output: list[dict[str, object]] = []
    bucket_positions: list[list[dict[str, object]]] = []
    seen: set[str] = set()
    seen_ranks: set[int] = set()
    total_tickets = 0
    for strategy_index, raw_item in enumerate(strategies_raw):
        raw = _object(raw_item, f"strategies[{strategy_index}]")
        strategy_id = _text(raw.get("strategy_id"), "strategy_id")
        version = _text(raw.get("strategy_version"), "strategy_version")
        if strategy_id in seen:
            raise ValueError(f"duplicate strategy identity: {strategy_id}")
        seen.add(strategy_id)
        source_rank = raw.get("rank")
        if type(source_rank) is not int or source_rank < 1 or source_rank in seen_ranks:
            raise ValueError(f"invalid or duplicate source strategy rank: {strategy_id}")
        seen_ranks.add(source_rank)
        native_k = raw.get("native_k")
        if type(native_k) is not int or native_k < 1:
            raise ValueError(f"invalid native_k for {strategy_id}")
        catalog_row = catalog_by_id.get(strategy_id)
        config_row = config_by_id.get(strategy_id)
        if catalog_row is None or config_row is None:
            raise ValueError(
                f"strategy identity not present in supplied catalog/config: {strategy_id}"
            )
        for label, row in (("catalog", catalog_row), ("generation config", config_row)):
            if row.get("version", row.get("strategy_version")) != version:
                raise ValueError(f"strategy identity mismatch in {label}: {strategy_id}")
            if row.get("native_k", row.get("native_ticket_count", native_k)) != native_k:
                raise ValueError(f"native_k mismatch in {label}: {strategy_id}")
        config_rng = _object(config_row.get("rng_semantics"), f"{strategy_id} RNG config")
        if raw.get("rng_semantics") != config_rng:
            raise ValueError(f"strategy RNG identity mismatch: {strategy_id}")
        adapter_path = _text(raw.get("adapter_source_path"), f"{strategy_id} adapter source path")
        adapter_sha = _sha(raw.get("adapter_source_sha256"), f"{strategy_id} adapter source SHA")
        if catalog_row.get("adapter_source_path", adapter_path) != adapter_path:
            raise ValueError(f"strategy adapter path mismatch: {strategy_id}")
        if catalog_row.get("adapter_path", raw.get("generator_identity")) != raw.get(
            "generator_identity"
        ):
            raise ValueError(f"strategy generator identity mismatch: {strategy_id}")
        if catalog_row.get("adapter_source_sha256", adapter_sha) != adapter_sha:
            raise ValueError(f"strategy adapter SHA mismatch: {strategy_id}")
        tickets_raw = _array(raw.get("tickets"), f"{strategy_id} tickets")
        if len(tickets_raw) != native_k:
            raise ValueError(f"native ticket count mismatch: {strategy_id}")
        positions: list[dict[str, object]] = []
        tickets: list[list[int]] = []
        for expected_position, ticket_item in enumerate(tickets_raw, start=1):
            ticket = _object(ticket_item, f"{strategy_id} ticket {expected_position}")
            if ticket.get("position") != expected_position:
                raise ValueError(f"native ticket position gap or reorder: {strategy_id}")
            numbers = ticket.get("emitted_main_numbers")
            if (
                not isinstance(numbers, list)
                or len(numbers) != 6
                or any(type(number) is not int or not 1 <= number <= 49 for number in numbers)
                or len(set(numbers)) != 6
            ):
                raise ValueError(
                    f"invalid six-number native ticket: {strategy_id}/{expected_position}"
                )
            if ticket.get("legal_main_numbers", numbers) != numbers:
                raise ValueError(
                    f"emitted/legal ticket mismatch: {strategy_id}/{expected_position}"
                )
            if ticket.get("predicted_special_number") is not None:
                raise ValueError("BIG_LOTTO native ticket cannot include a special number")
            kept_numbers = cast(list[int], numbers)
            positions.append({"position": expected_position, "numbers": kept_numbers})
            tickets.append(kept_numbers)
        total_tickets += len(tickets)
        output.append(
            {
                "strategy_id": strategy_id,
                "strategy_version": version,
                "native_k": native_k,
                "source_rank": source_rank,
                "generator_identity": _text(
                    raw.get("generator_identity"), f"{strategy_id} generator identity"
                ),
                "adapter_source_path": adapter_path,
                "adapter_source_sha256": adapter_sha,
                "native_positions": positions,
            }
        )
        bucket_positions.append(positions)
    for name, observed in (
        ("strategy_count_expected", len(output)),
        ("strategy_count_generated", len(output)),
        ("ticket_count_expected", total_tickets),
        ("ticket_count_generated", total_tickets),
    ):
        if type(native.get(name)) is not int or native[name] != observed:
            raise ValueError(f"native result {name} does not match its rows")
    if seen != set(catalog_by_id) or seen != set(config_by_id):
        raise ValueError("native, catalog and generation-config inventories differ")
    return output, bucket_positions


def adapt_native_input(
    native_result: Mapping[str, object],
    provenance: Mapping[str, object] | None,
) -> LiveForecastInput:
    """Map a complete native result plus its supplied execution record to v6.

    All load-bearing provenance is required from ``provenance``. This function
    never discovers source identity, fills missing history, infers RNG state,
    or assigns issuance/commit timestamps.
    """

    native = _object(_json_clone(native_result, "native_result"), "native_result")
    if native.get("schema_version") != NATIVE_INPUT_SCHEMA:
        raise ValueError("unsupported native input schema")
    if provenance is None:
        raise ValueError("complete v6 provenance context is required")
    context = _object(_json_clone(provenance, "provenance"), "provenance")
    required_context = {
        "target",
        "source_locator",
        "source_execution",
        "runtime_manifest",
        "history_snapshot",
        "producer",
        "catalog",
        "generation_configs",
        "effective_parameters",
        "rng_semantics",
        "ranking_evidence",
        "seeds",
        "generation_started_at",
        "generation_finished_at",
    }
    missing_context = sorted(required_context - context.keys())
    if missing_context:
        raise ValueError("missing v6 provenance context: " + ",".join(missing_context))
    if native.get("target_outcome") != "UNOBSERVED_NOT_READ":
        raise ValueError("target outcome must remain unobserved")
    rows_selected = native.get(
        "target_rows_selected", native.get("target_106_source_rows_selected")
    )
    if rows_selected is not False:
        raise ValueError("target outcome rows must be explicitly unselected")
    proof_status = _text(native.get("pre_draw_proof_status"), "pre_draw_proof_status")
    target = _object(context["target"], "target")
    target_required = {
        "lottery_type",
        "target_draw_number",
        "target_draw_date",
        "scheduled_at",
        "timezone",
        "data_cutoff",
        "forecast_horizon",
        "history_draw_count",
        "causal_history_sha256",
        "schedule_authority_sha256",
    }
    if missing := sorted(target_required - target.keys()):
        raise ValueError("missing target binding: " + ",".join(missing))
    if target["lottery_type"] != LotteryType.BIG_LOTTO.value or target["forecast_horizon"] != 1:
        raise ValueError("B649 one-draw target required")
    if native.get("prediction_target") != target["target_draw_number"]:
        raise ValueError("native result and target binding disagree")
    if target.get("schedule_authority_sha256") is None:
        raise ValueError("schedule binding is required")

    source_execution = _object(context["source_execution"], "source_execution")
    for key in ("repository", "commit", "tree", "loaded_code_sha256"):
        _text(source_execution.get(key), f"source execution {key}")
    runtime = _object(context["runtime_manifest"], "runtime_manifest")
    history = _object(context["history_snapshot"], "history_snapshot")
    _require_history_binding(target, history)
    producer = _producer(context["producer"])
    catalog = _array(context["catalog"], "catalog")
    configs = _array(context["generation_configs"], "generation_configs")
    effective = _object(context["effective_parameters"], "effective_parameters")
    rng = _object(context["rng_semantics"], "rng_semantics")
    ranking = _object(context["ranking_evidence"], "ranking_evidence")
    observations = _array(ranking.get("observations"), "ranking evidence observations")
    for index, item in enumerate(observations):
        _object(item, f"ranking evidence observations[{index}]")
    observation_order = [
        (
            str(_object(item, "ranking observation").get("strategy_id", "")),
            str(_object(item, "ranking observation").get("draw_number", "")),
        )
        for item in observations
    ]
    if observation_order != sorted(observation_order):
        raise ValueError("ranking observations must use the v6 canonical order")
    seeds = _object(context["seeds"], "seeds")
    if any(not isinstance(key, str) or type(value) is not int for key, value in seeds.items()):
        raise ValueError("seed inventory must map strategy IDs to exact integers")
    config_rows_by_id = {
        str(_object(item, "generation config")["strategy_id"]): _object(item, "generation config")
        for item in configs
    }
    if set(seeds) - set(config_rows_by_id):
        raise ValueError("seed inventory contains a strategy outside the supplied config")
    for strategy_id, config_row in config_rows_by_id.items():
        rng_config = _object(config_row.get("rng_semantics"), f"{strategy_id} RNG config")
        if rng_config.get("behavior") == "SEEDED_STOCHASTIC":
            if seeds.get(strategy_id) != rng_config.get("seed"):
                raise ValueError(f"effective RNG seed mismatch: {strategy_id}")
        elif strategy_id in seeds:
            raise ValueError(f"unexpected effective RNG seed: {strategy_id}")
    source_locator = _text(context["source_locator"], "source_locator")
    started = _text(context["generation_started_at"], "generation_started_at")
    finished = _text(context["generation_finished_at"], "generation_finished_at")

    native_strategies, native_positions = _native_rows(native, catalog, configs)
    catalog_ids = [
        str(_object(item, "catalog strategy").get("strategy_id", "")) for item in catalog
    ]
    config_ids = [
        str(_object(item, "generation config").get("strategy_id", "")) for item in configs
    ]
    if catalog_ids != sorted(catalog_ids) or config_ids != sorted(config_ids):
        raise ValueError("catalog and generation configs must use the v6 canonical order")
    catalog_sha = digest(catalog)
    config_sha = digest({"fixture_only": False, "strategies": configs})
    identity = ForecastIdentity(
        target=ObservationTarget(
            LotteryType.BIG_LOTTO,
            _text(target["target_draw_number"], "target draw number"),
            date.fromisoformat(_text(target["target_draw_date"], "target draw date")),
        ),
        schedule_authority_sha256=_sha(
            target["schedule_authority_sha256"], "schedule authority SHA"
        ),
        history_cutoff=_text(target["data_cutoff"], "target cutoff"),
        history_payload_sha256=_sha(target["causal_history_sha256"], "target history SHA"),
        producer=producer,
        catalog_universe_sha256=catalog_sha,
        generation_config_sha256=config_sha,
    )
    if (
        history.get("reference")
        != f"research-live-history:sha256:{identity.history_payload_sha256}"
    ):
        raise ValueError("history reference does not bind the supplied history SHA")
    if ranking.get("objective") != OBJECTIVE:
        raise ValueError("ranking objective does not match v6")
    if ranking.get("ranking_policy_version") != RANKING_POLICY_VERSION:
        raise ValueError("ranking policy does not match v6")
    if ranking.get("evaluation_window") != "FULL":
        raise ValueError("ranking evidence must cover the full declared window")
    evidence_sha = _sha(ranking.get("evidence_payload_sha256"), "ranking evidence SHA")
    if digest(observations) != evidence_sha:
        raise ValueError("ranking evidence SHA mismatch")

    observation_rows = sorted(
        observations,
        key=lambda row: (
            str(_object(row, "ranking observation").get("strategy_id", "")),
            str(_object(row, "ranking observation").get("draw_number", "")),
        ),
    )
    request_sha = digest(
        {
            "operation": "native-repredict",
            "observations": observation_rows,
            "seeds": seeds,
            "stream": NATIVE_STREAM_VERSION,
        }
    )
    source_identity = {
        "commit": source_execution["commit"],
        "tree": source_execution["tree"],
        "loaded_code_sha256": source_execution["loaded_code_sha256"],
    }
    request_id = "native-input:" + digest(
        {"forecast_bundle_id": identity.bundle_id, "source_execution": source_identity}
    )

    buckets: list[dict[str, object]] = []
    lineage: list[dict[str, object]] = []
    configs_by_id = config_rows_by_id
    for strategy, positions in zip(native_strategies, native_positions, strict=True):
        strategy_id = cast(str, strategy["strategy_id"])
        strategy_version = cast(str, strategy["strategy_version"])
        native_k = cast(int, strategy["native_k"])
        config = configs_by_id[strategy_id]
        tickets = [cast(list[int], row["numbers"]) for row in positions]
        candidate = {
            "strategy_id": strategy_id,
            "strategy_version": strategy_version,
            "native_k": native_k,
            "adapter_source_sha256": strategy["adapter_source_sha256"],
        }
        bucket = {
            "bucket": f"K{native_k}:{strategy_id}",
            "native_k": native_k,
            "status": "AVAILABLE",
            "entry_identity": [identity.bundle_id, native_k, strategy_id, strategy_version],
            "ranking_complete": True,
            "selected": {"strategy_id": strategy_id, "strategy_version": strategy_version},
            "tickets": tickets,
            "native_positions": positions,
            "generation_status": "COMPLETE",
            "display_tie_break": "strategy_id ASCENDING",
            "candidates": [candidate],
        }
        buckets.append(bucket)
        rng_config = _object(config.get("rng_semantics"), f"{strategy_id} RNG config")
        lineage.append(
            {
                "native_k": native_k,
                "status": "AVAILABLE",
                "tickets": tickets,
                "selected_strategy": strategy_id,
                "selector_status": "EXECUTED",
                "selection_rule": NATIVE_STREAM_VERSION,
                "tie_break": bucket["display_tie_break"],
                "candidate_binding_sha256": digest(bucket["candidates"]),
                "evidence_payload_sha256": evidence_sha,
                "constructor_status": "EXECUTED",
                "adapter_locator": strategy["adapter_source_path"],
                "adapter_version": strategy_version,
                "adapter_source_sha256": strategy["adapter_source_sha256"],
                "generation_config_sha256": digest(config),
                "rng_binding_sha256": digest(rng_config),
            }
        )
    # The v6 payload contract has an explicit unavailable K20 authority row.
    # It is structural metadata, not a generated or filled ticket.
    k20_bucket = {
        "bucket": "K20",
        "native_k": 20,
        "status": "UNAVAILABLE_NO_CANONICAL_NATIVE_K20_STRATEGY",
        "selected": None,
        "tickets": [],
        "display_tie_break": "strategy_id ASCENDING",
        "candidates": [],
    }
    buckets.append(k20_bucket)
    lineage.append(
        {
            "native_k": 20,
            "status": k20_bucket["status"],
            "tickets": [],
            "selected_strategy": None,
            "selector_status": "NOT_RUN",
            "selection_rule": NATIVE_STREAM_VERSION,
            "tie_break": k20_bucket["display_tie_break"],
            "candidate_binding_sha256": digest([]),
            "evidence_payload_sha256": evidence_sha,
            "constructor_status": "NOT_EXECUTED",
        }
    )
    payload = {
        "bundle_id": identity.bundle_id,
        "identity": identity.payload(),
        "forecast_output_semantics": "STRATEGY_NATIVE_POSITIONS",
        "evaluation_window": "FULL",
        "fixture_only": False,
        "source_proof_status": proof_status,
        "source_task_id": _text(native.get("task_id"), "native task_id"),
        "source_execution_identity": source_identity,
        "history": {"reference": history["reference"], "sha256": history["sha256"]},
        "catalog": catalog,
        "generation_configs": configs,
        "evidence_payload_sha256": evidence_sha,
        "native_strategies": native_strategies,
        "buckets": buckets,
    }
    payload_bytes = canonical_json(payload).encode("utf-8")
    original: dict[str, object] = {
        "producer_json": canonical_json(producer.canonical_dict()),
        "source_execution_json": canonical_json(source_execution),
        "runtime_manifest_json": canonical_json(runtime),
        "history_snapshot_json": canonical_json(history),
        "catalog_json": canonical_json(
            {"strategies": catalog, "catalog_universe_sha256": identity.catalog_universe_sha256}
        ),
        "generation_configs_json": canonical_json(
            {"strategies": configs, "generation_config_sha256": identity.generation_config_sha256}
        ),
        "effective_parameters_json": canonical_json(effective),
        "rng_semantics_json": canonical_json(rng),
        "ranking_evidence_json": canonical_json(ranking),
        "ticket_lineage_json": canonical_json(
            {"buckets": lineage, "upstream_payload_sha256": sha256(payload_bytes)}
        ),
        "generation_started_at": started,
        "generation_finished_at": finished,
    }
    if set(original) != set(ORIGINAL_FIELDS):
        raise ValueError("adapter original-execution field inventory mismatch")
    forecast = LiveForecastInput(
        request_id=request_id,
        request_sha256=request_sha,
        provenance_class="NATIVE_GENERATED",
        forecast_stream_id=NATIVE_STREAM,
        forecast_stream_version=NATIVE_STREAM_VERSION,
        target_json=canonical_json(target),
        payload_bytes=payload_bytes,
        source_locator=f"{source_locator}:{identity.bundle_id}",
        original_execution_json=canonical_json(original),
        missing_provenance_json="{}",
    )
    forecast.validate()
    return forecast
