"""Synthetic FULL-history forecast acceptance; no database or live evidence."""

from __future__ import annotations

import json
import random
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from fractions import Fraction

import pytest

from lottolab.application import b649_next_undrawn_forecast as app
from lottolab.application.b649_next_undrawn_forecast import (
    CanonicalNativeTicketGenerator,
    ForecastRequest,
    evaluate_evidence,
    native_generation_config,
    prepare_forecast,
)
from lottolab.domain.b649_next_undrawn_forecast import (
    OUTPUT_BUCKETS,
    CandidateEvidence,
    ClassifiedObservation,
    ExactMetric,
    ForecastContractError,
    ObservationStatus,
    ReplayObservation,
    canonical_json,
    digest,
    history_ref,
    rank_candidates,
    validate_history,
    validate_tickets,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.exact_native_replay import Draw
from lottolab.domain.prospective_observer import (
    ObservationTarget,
    ProducerDependency,
    ProducerFingerprint,
)
from lottolab.domain.strategies import LifecycleStatus, ResponseShape, StrategyDescriptor
from lottolab.strategies.adapters.base import BetAdapter, CausalDrawRow, PortfolioBetAdapter
from lottolab.strategies.catalog import StrategyCatalog, production_catalog

WIN = (1, 2, 7, 8, 9, 10)  # Two main matches plus special: official seventh prize.
LOSE = (1, 2, 8, 9, 10, 11)
NOW = datetime(2099, 1, 6, 15, tzinfo=UTC)
DEADLINE = datetime(2099, 1, 7, 12, 30, tzinfo=UTC)


def descriptor(strategy_id="fixture_a", k=1, min_history=1):
    return StrategyDescriptor(
        strategy_id,
        strategy_id,
        "fixture-v1",
        (LotteryType.BIG_LOTTO,),
        LifecycleStatus.ONLINE,
        True,
        "fixture:ticket_snapshot",
        min_history=min_history,
        response_shape=ResponseShape.SINGLE_TICKET if k == 1 else ResponseShape.PORTFOLIO,
        native_ticket_count=k,
    )


def make_request(descriptors=None, wins=None, *, seed=None, producer=None):
    catalog = tuple(descriptors or (descriptor(),))
    history = tuple(
        Draw(f"{115000080 + i:09d}", date(2099, 1, 1) + timedelta(days=i), (1, 2, 3, 4, 5, 6), 7)
        for i in range(6)
    )
    configs = tuple(native_generation_config(d, history, seed=seed) for d in catalog)
    producer = producer or ProducerFingerprint.create(
        producer_id="fixture-producer",
        producer_version="fixture-v1",
        dependencies=(ProducerDependency("fixture://producer", digest("code"), "fixture code"),),
    )
    observations = []
    for d in catalog:
        for i, draw in enumerate(history):
            if i < d.min_history:
                continue
            won = (wins or {}).get(d.strategy_id, [True] * 6)[i - d.min_history]
            observations.append(
                ReplayObservation(
                    d.strategy_id,
                    d.version,
                    d.native_ticket_count,
                    draw.draw_number,
                    draw.draw_date,
                    history_ref(history[:i]).history_sha256,
                    native_generation_config(d, history[:i], seed=seed).sha256,
                    ObservationStatus.EVALUATED,
                    ((WIN if won else LOSE),) * d.native_ticket_count,
                    producer_fingerprint=producer.digest,
                )
            )
    return ForecastRequest(
        ObservationTarget(LotteryType.BIG_LOTTO, "115000086", date(2099, 1, 7)),
        history,
        history_ref(history),
        digest("fixture schedule"),
        catalog,
        configs,
        tuple(observations),
        producer,
        fixture_only=True,
    )


class Generator:
    def __init__(self, tickets=None, after=None):
        self.tickets = tickets or {}
        self.after = after
        self.calls = []

    def generate(self, descriptor, config, history):
        self.calls.append((descriptor.strategy_id, history))
        if self.after:
            self.after()
        return self.tickets.get(descriptor.strategy_id, (WIN,) * descriptor.native_ticket_count)


def bucket(prepared, k):
    return next(b for b in prepared.bundle.payload()["buckets"] if b["native_k"] == k)


def test_full_official_ranking_uses_special_number_and_diagnostics_cannot_select(monkeypatch):
    request = make_request(
        (descriptor("fixture_a", 2), descriptor("fixture_z", 2)),
        {
            "fixture_a": [True, False, False, False, False],
            "fixture_z": [True, True, True, False, False],
        },
    )
    generator = Generator()
    before = prepare_forecast(request, generator)
    selected = bucket(before, 2)["selected"]
    assert selected["strategy_id"] == "fixture_z"
    assert selected["metric"] == {
        "numerator": 3,
        "denominator": 5,
        "rate": {"numerator": "3", "denominator": "5"},
    }
    monkeypatch.setattr(
        app,
        "_diagnostics",
        lambda c: {
            "RECENT_50": 10**100 if c.descriptor.strategy_id == "fixture_a" else -(10**100),
            "RECENT_300": -999,
            "RECENT_750": 999,
            "baseline_delta": 999,
        },
    )
    after = prepare_forecast(request, Generator())
    assert bucket(after, 2)["selected"] == selected
    assert bucket(after, 2)["tickets"] == bucket(before, 2)["tickets"]
    assert after.bundle.identity == before.bundle.identity
    assert after.bundle.payload_sha256 != before.bundle.payload_sha256
    assert generator.calls[0][0] == "fixture_z"


def test_exact_equal_rates_tie_and_strategy_id_only_selects_display_output():
    request = make_request(
        (descriptor("fixture_z", 2, 4), descriptor("fixture_a", 2, 2)),
        {"fixture_z": [True, False], "fixture_a": [True, False, True, False]},
    )
    result = bucket(prepare_forecast(request, Generator()), 2)
    assert result["selected"]["strategy_id"] == "fixture_a"
    assert result["selected"]["metric"]["numerator"] == 2
    assert result["selected"]["metric"]["denominator"] == 4
    assert result["semantic_tie"] is True
    assert result["tied_strategy_ids"] == ["fixture_a", "fixture_z"]


def test_ranking_preserves_rationals_beyond_binary_float_resolution(monkeypatch):
    a, z = descriptor("fixture_a"), descriptor("fixture_z")
    metrics = {
        a.strategy_id: ExactMetric(2**54 - 1, 2**54),
        z.strategy_id: ExactMetric(2**54, 2**54),
    }
    assert float(metrics[a.strategy_id].rate) == float(metrics[z.strategy_id].rate)
    monkeypatch.setattr(
        CandidateEvidence, "metric", property(lambda c: metrics[c.descriptor.strategy_id])
    )
    cell = ClassifiedObservation("115000085", ObservationStatus.EVALUATED, True)
    ranked = rank_candidates((CandidateEvidence(a, (cell,)), CandidateEvidence(z, (cell,))))
    assert ranked[0].descriptor.strategy_id == "fixture_z"
    assert metrics[a.strategy_id].rate < metrics[z.strategy_id].rate


def test_cross_k_comparison_is_refused():
    request = make_request((descriptor("fixture_a", 1), descriptor("fixture_b", 2)))
    with pytest.raises(ForecastContractError, match="CROSS_K"):
        rank_candidates(evaluate_evidence(request))


@pytest.mark.parametrize("cutoff", ["115000082", "115000084"])
def test_stale_cutoff_cannot_be_represented_as_085(cutoff):
    request = make_request()
    history = tuple(d for d in request.history if d.draw_number <= cutoff)
    with pytest.raises(ForecastContractError, match="STALE_HISTORY"):
        replace(request, history=history, history_authority=history_ref(history))
    with pytest.raises(ForecastContractError, match="STALE_HISTORY"):
        replace(
            request, history=history, history_authority=history_ref(history), required_cutoff=cutoff
        )


def test_085_accepted_and_corrected_main_special_or_date_changes_identity():
    request = make_request()
    validate_history(request.history, request.target, request.history_authority)
    for change in (
        {"main_numbers": (1, 2, 3, 4, 5, 8)},
        {"special_number": 9},
        {"draw_date": date(2098, 12, 31)},
    ):
        corrected = (replace(request.history[0], **change), *request.history[1:])
        with pytest.raises(ForecastContractError, match="HISTORY_IDENTITY_MISMATCH"):
            replace(request, history=corrected)
        changed = replace(request, history=corrected, history_authority=history_ref(corrected))
        assert changed.identity.bundle_id != request.identity.bundle_id
        with pytest.raises(ForecastContractError, match="REPLAY_HISTORY"):
            evaluate_evidence(changed)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda r: (*r.history, Draw("115000086", r.target.draw_date, (1, 2, 3, 4, 5, 6), 7)),
        lambda r: (*r.history[:-1], replace(r.history[-1], draw_date=r.target.draw_date)),
        lambda r: (r.history[1], r.history[0], *r.history[2:]),
        lambda r: (*r.history[:-1], replace(r.history[-1], draw_number="115000087")),
    ],
)
def test_future_rows_reordered_rows_and_target_leakage_rejected(mutate):
    request = make_request()
    draws = mutate(request)
    with pytest.raises(ForecastContractError, match="FUTURE_OR_NONCHRONOLOGICAL"):
        replace(request, history=draws, history_authority=history_ref(draws))


def test_every_observation_is_classified_and_incomplete_cannot_shrink_denominator():
    request = make_request()
    rows = request.observations
    request = replace(
        request,
        observations=(
            rows[0],
            replace(
                rows[2],
                status=ObservationStatus.FAILURE,
                tickets=(),
                failure_code="ADAPTER_TIMEOUT",
            ),
            replace(rows[3], status=ObservationStatus.METRIC_UNAVAILABLE, tickets=()),
            rows[4],
        ),
    )
    result = prepare_forecast(request, Generator())
    k1 = bucket(result, 1)
    candidate = k1["candidates"][0]
    counts = candidate["coverage"]["counts"]
    assert counts == {
        "ELIGIBLE_EVALUATED": 2,
        "CANONICAL_WARMUP_EXCLUSION": 1,
        "MISSING_OBSERVATION": 1,
        "REPLAY_GENERATION_FAILURE": 1,
        "METRIC_UNAVAILABLE": 1,
    }
    assert candidate["metric"]["denominator"] == 2
    assert candidate["coverage"]["eligible_expected"] == 5
    assert candidate["coverage"]["requested"] == sum(counts.values()) == 6
    assert candidate["rankable"] is False
    assert k1["status"] == "INCOMPLETE_EVIDENCE"
    assert k1["selected"] is None and k1["tickets"] == []
    assert result.bundle.payload()["latest_data_ranking_complete"] is False


def test_missing_candidate_prevents_complete_bucket_even_when_another_has_complete_evidence():
    request = make_request((descriptor("fixture_a"), descriptor("fixture_z")))
    request = replace(
        request, observations=tuple(o for o in request.observations if o.strategy_id == "fixture_a")
    )
    k1 = bucket(prepare_forecast(request, Generator()), 1)
    assert k1["rankable_count"] == 1 and k1["excluded_count"] == 1
    assert k1["ranking_complete"] is False and k1["selected"] is None


def test_all_warmup_is_known_unavailable_and_never_divides_by_zero():
    request = make_request((descriptor(min_history=20),))
    k1 = bucket(prepare_forecast(request, Generator()), 1)
    assert k1["status"] == "UNAVAILABLE_NO_ELIGIBLE_EVIDENCE"
    assert k1["candidates"][0]["metric"]["rate"] is None
    assert k1["candidates"][0]["coverage"]["counts"]["MISSING_OBSERVATION"] == 0


@pytest.mark.parametrize(
    "mutation",
    [
        {"strategy_version": "wrong"},
        {"native_k": 2, "tickets": (WIN, WIN)},
        {"draw_date": date(2099, 1, 7)},
        {"causal_history_sha256": "a" * 64},
        {"generation_config_sha256": "b" * 64},
        {"draw_number": "115000086"},
        {"strategy_id": "outside_catalog"},
    ],
)
def test_replay_identity_mismatches_and_future_observations_rejected(mutation):
    request = make_request()
    rows = (replace(request.observations[0], **mutation), *request.observations[1:])
    with pytest.raises(ForecastContractError):
        evaluate_evidence(replace(request, observations=rows))


def test_warmup_is_only_canonical_min_history_and_duplicates_are_not_deduplicated():
    request = make_request()
    warmup = replace(request.observations[0], status=ObservationStatus.WARMUP, tickets=())
    with pytest.raises(ForecastContractError, match="NONCANONICAL_WARMUP"):
        evaluate_evidence(replace(request, observations=(warmup, *request.observations[1:])))
    with pytest.raises(ForecastContractError, match="DUPLICATE_OBSERVATION"):
        evaluate_evidence(
            replace(request, observations=(*request.observations, request.observations[0]))
        )


def test_all_six_buckets_native_ticket_cardinality_and_truthful_k20():
    request = make_request(tuple(descriptor(f"fixture_k{k}", k) for k in OUTPUT_BUCKETS if k != 20))
    generator = Generator()
    prepared = prepare_forecast(request, generator)
    assert [b["native_k"] for b in prepared.bundle.payload()["buckets"]] == list(OUTPUT_BUCKETS)
    assert len(generator.calls) == 5
    for k in OUTPUT_BUCKETS[:-1]:
        b = bucket(prepared, k)
        assert b["status"] == "AVAILABLE" and len(b["tickets"]) == k
        assert b["tickets"] == [list(WIN)] * k
        assert b["baseline"]["candidate_sizes"] == [6] * k
        assert len(b["entry_identity"]) == 4
    k20 = bucket(prepared, 20)
    assert k20["status"] == "UNAVAILABLE_NO_CANONICAL_NATIVE_K20_STRATEGY"
    assert k20["candidate_count"] == 0 and k20["tickets"] == []
    assert k20["selected"] is None and len(k20["entry_identity"]) == 2
    assert all(
        d.native_ticket_count != 20 or d.native_ticket_count_bounds != (20, 20)
        for d in production_catalog()
        if d.executable
    )


@pytest.mark.parametrize("bad_output", [(WIN,), (WIN,) * 4, ((1, 2, 3, 4, 5, 50),) * 3])
def test_native_output_is_never_truncated_padded_or_replaced_by_runner_up(bad_output):
    request = make_request((descriptor("fixture_a", 3), descriptor("fixture_z", 3)))
    generator = Generator({"fixture_a": bad_output})
    k3 = bucket(prepare_forecast(request, generator), 3)
    assert k3["status"] == "UNAVAILABLE_GENERATION_FAILURE" and k3["tickets"] == []
    assert k3["selected"]["strategy_id"] == "fixture_a"
    assert [call[0] for call in generator.calls] == ["fixture_a"]


class FixtureSingle(BetAdapter):
    strategy_id = strategy_name = "fixture_single"
    strategy_version = "fixture-v1"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)

    def _predict(self, history: tuple[CausalDrawRow, ...], lottery_type: LotteryType):
        return tuple(reversed(WIN))


class FixturePortfolio(PortfolioBetAdapter):
    strategy_id = strategy_name = "fixture_portfolio"
    strategy_version = "fixture-v1"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)
    native_ticket_count = 3

    def _predict_all(self, history: tuple[CausalDrawRow, ...], lottery_type: LotteryType):
        return WIN, LOSE, WIN


def test_canonical_single_ticket_and_portfolio_type_paths_preserve_exact_emission():
    one = replace(descriptor("fixture_single"), adapter_path=f"{__name__}:FixtureSingle")
    many = replace(descriptor("fixture_portfolio", 3), adapter_path=f"{__name__}:FixturePortfolio")
    request = make_request((one, many))
    generator = CanonicalNativeTicketGenerator(StrategyCatalog(request.catalog))
    prepared = prepare_forecast(request, generator)
    assert bucket(prepared, 1)["tickets"] == [list(WIN)]
    assert bucket(prepared, 1)["selected"]["response_shape"] == "SINGLE_TICKET"
    assert bucket(prepared, 3)["tickets"] == [list(WIN), list(LOSE), list(WIN)]


def test_bundle_identity_is_deterministic_and_binds_every_load_bearing_input():
    request = make_request((descriptor("fixture_a"), descriptor("fixture_z", 2)))
    original = request.identity.bundle_id
    reordered = replace(
        request,
        catalog=tuple(reversed(request.catalog)),
        generation_configs=tuple(reversed(request.generation_configs)),
        observations=tuple(reversed(request.observations)),
    )
    assert (
        prepare_forecast(request, Generator()).bundle
        == prepare_forecast(reordered, Generator()).bundle
    )
    assert original == digest(request.identity.payload())
    assert request.identity.payload()["objective"] == "OFFICIAL_ANY_PRIZE"
    changed_producer = ProducerFingerprint.create(
        producer_id=request.producer.producer_id,
        producer_version="fixture-v2",
        dependencies=request.producer.dependencies,
    )
    config = request.generation_configs[0]
    changes = [
        replace(request, producer=changed_producer),
        replace(
            request,
            generation_configs=(
                replace(config, parameters_json=canonical_json({"seed": 2})),
                *request.generation_configs[1:],
            ),
        ),
        replace(
            request,
            generation_configs=(
                replace(config, rng_semantics_json=canonical_json({"seed": 2})),
                *request.generation_configs[1:],
            ),
        ),
        replace(
            request, catalog=(replace(request.catalog[0], min_history=2), *request.catalog[1:])
        ),
        replace(request, schedule_authority_sha256=digest("corrected schedule")),
        replace(request, target=replace(request.target, draw_date=date(2099, 1, 8))),
    ]
    assert all(r.identity.bundle_id != original for r in changes)


def test_partial_or_fixture_catalog_cannot_claim_canonical_forecast_authority():
    with pytest.raises(ForecastContractError, match="CANONICAL_CATALOG_UNIVERSE_MISMATCH"):
        replace(make_request(), fixture_only=False)


def test_unknown_parameters_are_unavailable_not_silently_ignored():
    one = replace(descriptor("fixture_single"), adapter_path=f"{__name__}:FixtureSingle")
    request = make_request((one,))
    config = replace(request.generation_configs[0], parameters_json=canonical_json({"ignored": 42}))
    generator = CanonicalNativeTicketGenerator(StrategyCatalog(request.catalog))
    with pytest.raises(app.ForecastGenerationError, match="CONFIGURATION_MISMATCH"):
        generator.generate(one, config, request.history)


def test_invalid_tickets_are_rejected_without_coercion():
    for ticket in ((True, 2, 3, 4, 5, 6), (1, 1, 2, 3, 4, 5), (6, 5, 4, 3, 2, 1)):
        with pytest.raises(ForecastContractError):
            validate_tickets((ticket,), 1)
    assert ExactMetric(2, 4).rate == Fraction(1, 2)


def test_canonical_k10_history_length_rng_reuses_only_the_exact_causal_configuration():
    canonical = production_catalog().get(
        "legacy_biglotto__backtest_10bet_biglotto__054e85b088be"
    )
    request = make_request((canonical,))  # Metadata only; never runs the native adapter.
    prefix_configs = tuple(
        native_generation_config(canonical, request.history[:i]) for i in range(1, 6)
    )
    assert [json.loads(c.rng_semantics_json)["seed"] for c in prefix_configs] == [1, 2, 3, 4, 5]
    assert json.loads(request.generation_configs[0].rng_semantics_json)["seed"] == 6
    assert [o.generation_config_sha256 for o in request.observations] == [
        c.sha256 for c in prefix_configs
    ]
    evidence = evaluate_evidence(request)
    assert evidence == evaluate_evidence(replace(request, observations=tuple(request.observations)))
    assert evidence[0].complete and evidence[0].rankable
    assert evidence[0].metric == ExactMetric(5, 5)
    assert len({o.generation_identity_sha256 for o in request.observations}) == 5
    relabeled = tuple(
        replace(o, generation_config_sha256=request.generation_configs[0].sha256)
        for o in request.observations
    )
    generator = Generator()
    with pytest.raises(ForecastContractError, match="REPLAY_HISTORY_OR_GENERATION"):
        prepare_forecast(replace(request, observations=relabeled), generator)
    assert generator.calls == []


@pytest.mark.parametrize("field", ["parameters_json", "rng_semantics_json"])
def test_changed_generation_contract_cannot_relabel_old_evidence_into_compatibility(field):
    request = make_request()
    config = request.generation_configs[0]
    original = json.loads(getattr(config, field))
    changed = replace(config, **{field: canonical_json({**original, "changed_contract": True})})
    assert changed.sha256 != config.sha256
    altered = replace(request, generation_configs=(changed,))
    assert altered.identity.bundle_id != request.identity.bundle_id
    for rows in (
        request.observations,
        tuple(replace(o, generation_config_sha256=changed.sha256) for o in request.observations),
    ):
        with pytest.raises(ForecastContractError, match="REQUEST_GENERATION_CONFIGURATION"):
            evaluate_evidence(replace(altered, observations=rows))


class FixtureSeededPortfolio(FixturePortfolio):
    strategy_id = strategy_name = "fixture_seeded"

    def with_seed(self, seed):
        result = FixtureSeededPortfolio()
        result.seed = seed
        return result

    def _predict_all(self, history, lottery_type):
        rng = random.Random(self.seed)
        return tuple(tuple(sorted(rng.sample(range(1, 50), 6))) for _ in range(3))


def test_applicable_explicit_seed_change_requires_new_observation_identity():
    d = replace(descriptor("fixture_seeded", 3), adapter_path=f"{__name__}:FixtureSeededPortfolio")
    first = make_request((d,), seed=41)
    second = make_request((d,), seed=42)
    assert first.history == second.history
    assert first.generation_configs[0].sha256 != second.generation_configs[0].sha256
    assert first.observations[0].generation_identity_sha256 != (
        second.observations[0].generation_identity_sha256
    )
    assert evaluate_evidence(first)[0].metric == ExactMetric(5, 5)
    assert evaluate_evidence(second)[0].metric == ExactMetric(5, 5)
    with pytest.raises(ForecastContractError, match="REPLAY_HISTORY_OR_GENERATION"):
        evaluate_evidence(replace(second, observations=first.observations))
    generator = CanonicalNativeTicketGenerator(StrategyCatalog((d,)))
    prepared = prepare_forecast(first, generator)
    assert prepared.bundle == prepare_forecast(make_request((d,), seed=41), generator).bundle
    assert prepared.bundle.identity.bundle_id != second.identity.bundle_id
    assert bucket(prepared, 3)["status"] == "AVAILABLE"
    with pytest.raises(ForecastContractError, match="EXPLICIT_GENERATION_SEED_REQUIRED"):
        native_generation_config(d, first.history)


@pytest.mark.parametrize("drift", ["producer_version", "generator_source"])
def test_producer_or_generator_fingerprint_drift_invalidates_prior_evidence(drift):
    request = make_request()
    producer = ProducerFingerprint.create(
        producer_id=request.producer.producer_id,
        producer_version="fixture-v2" if drift == "producer_version" else "fixture-v1",
        dependencies=(
            ProducerDependency(
                "fixture://producer",
                digest("new generator" if drift == "generator_source" else "code"),
                "fixture code",
            ),
        ),
    )
    changed = replace(request, producer=producer)
    assert changed.identity.bundle_id != request.identity.bundle_id
    assert request.observations[0].generation_identity_sha256 != replace(
        request.observations[0], producer_fingerprint=producer.digest
    ).generation_identity_sha256
    generator = Generator()
    with pytest.raises(ForecastContractError, match="REPLAY_HISTORY_OR_GENERATION"):
        prepare_forecast(changed, generator)
    assert generator.calls == []


def test_one_incompatible_row_prevents_partial_ranking_and_denominator_shrinkage(monkeypatch):
    request = make_request((descriptor("fixture_a"), descriptor("fixture_z")))
    request = replace(
        request,
        observations=(
            *request.observations[:-1],
            replace(request.observations[-1], producer_fingerprint=digest("other generator")),
        ),
    )

    def forbidden(*args, **kwargs):
        pytest.fail("incompatible evidence reached prize scoring or ranking")

    monkeypatch.setattr(app, "evaluate_lottery_prize", forbidden)
    monkeypatch.setattr(app, "rank_candidates", forbidden)
    with pytest.raises(ForecastContractError, match="REPLAY_HISTORY_OR_GENERATION"):
        prepare_forecast(request, Generator())


def test_deterministic_contract_ignores_non_effective_seed_and_descriptive_metadata():
    d = descriptor()
    request = make_request((d,))
    baseline = native_generation_config(d, request.history)
    assert baseline == native_generation_config(d, request.history, seed=1234)
    descriptive = replace(d, strategy_name="Display label", provenance=("note:documentation",))
    assert baseline == native_generation_config(descriptive, request.history, seed=9876)
    semantics = json.loads(baseline.rng_semantics_json)
    assert semantics["behavior"] == "DETERMINISTIC"
    assert semantics["rng_state_rule"] == "NONE_DETERMINISTIC"
    assert semantics["seed"] is None
    assert "explicit_portfolio_seed" not in semantics
    assert "seed" not in json.loads(baseline.parameters_json)
    other = make_request((d,), seed=999)
    assert request.observations == other.observations
    assert (
        prepare_forecast(request, Generator()).bundle
        == prepare_forecast(other, Generator()).bundle
    )
    observation = request.observations[0]
    assert observation.generation_identity_sha256 == replace(
        observation, status=ObservationStatus.METRIC_UNAVAILABLE, tickets=()
    ).generation_identity_sha256


def test_canonical_unseeded_stream_cannot_be_misrepresented_as_deterministic_evidence():
    d = next(
        d
        for d in production_catalog().list(lottery_type=LotteryType.BIG_LOTTO)
        if d.min_history == 1
        and "randomness:PROCESS_GLOBAL_UNSEEDED_MATH_RANDOM_EQUIVALENT" in d.provenance
    )
    request = make_request((d,))
    semantics = json.loads(request.generation_configs[0].rng_semantics_json)
    assert semantics["behavior"] == "UNSEEDED_STOCHASTIC"
    assert semantics["seed"] is None
    with pytest.raises(ForecastContractError, match="RNG_STATE_UNAVAILABLE_REGENERATION_REQUIRED"):
        evaluate_evidence(request)


def test_observation_requires_explicit_valid_producer_provenance():
    request = make_request()
    with pytest.raises(ForecastContractError, match="SHA-256"):
        replace(request.observations[0], producer_fingerprint="")
