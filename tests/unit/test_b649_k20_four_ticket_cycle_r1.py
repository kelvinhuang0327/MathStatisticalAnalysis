"""Focused definition and exact-score checks for the four-ticket 4-cycle pilot."""

from __future__ import annotations

import ast
import hashlib
import itertools
import json
import random
from collections.abc import Sequence
from math import comb
from pathlib import Path
from typing import cast

import pytest

from lottolab.research import b649_k20_four_ticket_cycle_r1 as cycle
from lottolab.research import b649_k20_three_ticket_single_number_cycle_r1 as ttc
from lottolab.research import b649_official_any_prize_exact as canonical
from lottolab.research.b649_official_any_prize_exact import DrawMasks

ROOT = Path(__file__).resolve().parents[2]
POOL_SIZE = 12
PORTFOLIO = ttc.normalize_portfolio(
    (
        (1, 7, 8, 9, 10, 11),
        (2, 6, 8, 9, 11, 12),
        (2, 7, 8, 9, 10, 11),
        (3, 7, 9, 10, 11, 12),
    ),
    pool_size=POOL_SIZE,
)
QUADRUPLE = (0, 1, 2, 3)
FROZEN_ORIENTATIONS = {
    ("(0 1 2 3)", (1, 2, 3, 0)),
    ("(0 3 2 1)", (3, 0, 1, 2)),
    ("(0 1 3 2)", (1, 3, 0, 2)),
    ("(0 2 3 1)", (2, 0, 3, 1)),
    ("(0 2 1 3)", (2, 3, 1, 0)),
    ("(0 3 1 2)", (3, 2, 0, 1)),
}


@pytest.fixture(scope="module")
def draws12() -> DrawMasks:
    return canonical.all_main_draw_masks(POOL_SIZE, 6)


def _count(portfolio: Sequence[Sequence[int]], draws: DrawMasks) -> int:
    return int(
        canonical.evaluate_portfolio(
            portfolio, pool_size=POOL_SIZE, draws=draws
        ).official_any_prize_outcome_count
    )


def _oracle(spec: cycle.RawFourCycleSpec) -> frozenset[frozenset[int]] | None:
    """Use the named cycle and set arithmetic, independent of implementation images."""

    order = tuple(int(slot) for slot in spec.orientation.strip("()").split())
    successor = {order[index]: order[(index + 1) % 4] for index in range(4)}
    predecessor = {target: source for source, target in successor.items()}
    originals = [frozenset(PORTFOLIO[index]) for index in spec.quadruple]
    images = [
        (originals[slot] - {spec.numbers[slot]}) | {spec.numbers[predecessor[slot]]}
        for slot in range(4)
    ]
    if any(
        len(image) != 6 or image == original
        for image, original in zip(images, originals, strict=True)
    ):
        return None
    replaced = [frozenset(ticket) for ticket in PORTFOLIO]
    for index, image in zip(spec.quadruple, images, strict=True):
        replaced[index] = image
    if len(set(replaced)) != len(replaced):
        return None
    original_set = set(map(frozenset, PORTFOLIO))
    if len(original_set - set(replaced)) != 4 or len(set(replaced) - original_set) != 4:
        return None
    return frozenset(replaced)


def test_modules_resolve_to_this_checkout() -> None:
    assert Path(cycle.__file__).resolve().is_relative_to(ROOT / "src")
    assert Path(ttc.__file__).resolve().is_relative_to(ROOT / "src")
    assert Path(canonical.__file__).resolve().is_relative_to(ROOT / "src")


def test_frozen_family_is_exactly_the_six_single_four_cycles() -> None:
    assert cycle.CYCLE_ORIENTATIONS == 6
    assert {(item.name, item.successor) for item in cycle.ORIENTATIONS} == FROZEN_ORIENTATIONS
    assert {successor for _, successor in cycle.EXCLUDED_DOUBLE_TRANSPOSITIONS}.isdisjoint(
        {successor for _, successor in FROZEN_ORIENTATIONS}
    )
    for _, successor in FROZEN_ORIENTATIONS:
        visited = {0}
        position = successor[0]
        while position not in visited:
            visited.add(position)
            position = successor[position]
        assert position == 0 and len(visited) == 4
    assert cycle.raw_attempt_cap(20) == comb(20, 4) * 6**4 * 6 == 37_674_720
    assert cycle.PILOT_SEED == 20260930
    assert cycle.QUADRUPLE_SAMPLE_COUNT == 24
    assert cycle.PILOT_RAW_ATTEMPT_CEILING == 186_624


def test_every_raw_attempt_matches_the_independent_four_ticket_definition() -> None:
    raw = emitted = 0
    for spec in cycle.iter_quadruple_specs(PORTFOLIO, QUADRUPLE, pool_size=POOL_SIZE):
        raw += 1
        expected = _oracle(spec)
        actual = cycle.emit_spec(PORTFOLIO, spec, pool_size=POOL_SIZE)
        if expected is None:
            assert actual is None, spec
            continue
        assert actual is not None, spec
        emitted += 1
        assert frozenset(map(frozenset, actual.portfolio)) == expected
        assert actual.tickets_changed == len(actual.added) == 4
        assert set(actual.removed) == set(PORTFOLIO) - set(actual.portfolio)
        assert set(actual.added) == set(actual.portfolio) - set(PORTFOLIO)
    assert raw == 7776
    assert emitted > 0


def test_residual_scores_every_local_unique_candidate_and_matches_canonical_samples(
    draws12: DrawMasks,
) -> None:
    residual = cycle.build_subset_residual(PORTFOLIO, QUADRUPLE, pool_size=POOL_SIZE, draws=draws12)
    assert residual.outcome_count(PORTFOLIO) == _count(PORTFOLIO, draws12)
    assert residual.rest_won_draws + int(residual.pattern_draws.sum()) == comb(POOL_SIZE, 6)
    start = ttc.StartBinding(
        PORTFOLIO,
        POOL_SIZE,
        ttc.portfolio_sha256(PORTFOLIO, pool_size=POOL_SIZE),
        _count(PORTFOLIO, draws12),
    )
    scan = cycle.scan_quadruple(start, residual, QUADRUPLE)
    rows = cast(list[cycle.CandidateRow], scan["ROWS"])
    rejected = cast(dict[str, int], scan["REJECTED"])
    assert scan["RAW"] == 7776
    assert scan["LEGAL"] == len(rows) + cast(int, scan["LOCAL_DUPLICATES"])
    assert scan["RAW"] == cast(int, scan["LEGAL"]) + sum(rejected.values())
    assert len({row[0] for row in rows}) == len(rows)
    assert len(rows) > 20
    for sha, numbers, orientation, count in random.Random(20260930).sample(rows, 20):
        emission = cycle.emit_spec(
            PORTFOLIO,
            cycle.RawFourCycleSpec(QUADRUPLE, numbers, orientation),
            pool_size=POOL_SIZE,
        )
        assert emission is not None and emission.sha256 == sha
        assert count == _count(emission.portfolio, draws12)


def test_parity_sampling_is_deterministic_and_canonical_at_small_pool(
    draws12: DrawMasks,
) -> None:
    count = _count(PORTFOLIO, draws12)
    start = ttc.StartBinding(
        PORTFOLIO, POOL_SIZE, ttc.portfolio_sha256(PORTFOLIO, pool_size=POOL_SIZE), count
    )
    residual = cycle.build_subset_residual(PORTFOLIO, QUADRUPLE, pool_size=POOL_SIZE, draws=draws12)
    first = cycle.parity_quadruple(start, residual, QUADRUPLE, draws=draws12)
    second = cycle.parity_quadruple(start, residual, QUADRUPLE, draws=draws12)
    assert first == second
    assert first["START_MATCH"] is True
    samples = cast(list[dict[str, object]], first["SAMPLES"])
    assert len(samples) == 3
    assert all(sample["MATCH"] is True for sample in samples)


def test_frozen_quadruple_sample_is_distinct_and_reproducible() -> None:
    first = cycle.select_pilot_quadruples()
    assert first == cycle.select_pilot_quadruples()
    assert len(first) == len(set(first)) == 24
    assert all(0 <= i < j < k < fourth < 20 for i, j, k, fourth in first)
    assert first == tuple(
        random.Random(20260930).sample(list(itertools.combinations(range(20), 4)), 24)
    )


def test_rejection_accounting_accepts_missing_zero_categories_but_not_wrong_counts() -> None:
    recorded = {
        cycle.REJECT_ILLEGAL_TICKET: 48_418,
        cycle.REJECT_UNCHANGED_TICKET: 8_668,
        cycle.REJECT_DUPLICATE_TICKET: 0,
        cycle.REJECT_FEWER_THAN_FOUR_CHANGED: 0,
    }
    generator = {
        cycle.REJECT_ILLEGAL_TICKET: 48_418,
        cycle.REJECT_UNCHANGED_TICKET: 8_668,
    }
    assert cycle.rejection_counts_match(recorded, generator)
    assert not cycle.rejection_counts_match(
        recorded, {**generator, cycle.REJECT_ILLEGAL_TICKET: 48_419}
    )
    assert not cycle.rejection_counts_match(recorded, {**generator, "UNKNOWN": 0})


FIXTURES = ROOT / "tests/fixtures/b649_four_ticket_incumbents_r1"


def _payload(label: str) -> dict[str, object]:
    return cast(dict[str, object], json.loads((FIXTURES / f"{label}.json").read_bytes()))


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fixture_start(label: str, draws: DrawMasks) -> cycle.StartBinding:
    artifact = FIXTURES / f"{label}.json"
    return cycle.load_start(
        cycle.START_PRIMARY,
        ROOT,
        draws=draws,
        incumbent_artifact=artifact,
        incumbent_artifact_sha256=_digest(artifact),
    )


def _changed_artifact(tmp_path: Path, label: str, **changes: object) -> tuple[Path, str]:
    artifact = tmp_path / f"{label}.json"
    artifact.write_text(json.dumps({**_payload(label), **changes}), encoding="utf-8")
    return artifact, _digest(artifact)


@pytest.fixture(scope="module")
def draws49() -> DrawMasks:
    return canonical.all_main_draw_masks(49, 6)


@pytest.fixture(scope="module")
def current_start(draws49: DrawMasks) -> cycle.StartBinding:
    return _fixture_start("current", draws49)


def test_current_incumbent_exact_load(current_start: cycle.StartBinding) -> None:
    assert len(current_start.portfolio) == 20
    assert current_start.pool_size == 49
    assert current_start.outcome_count == 313_263_888
    assert current_start.sha256 == _payload("compatibility")["CURRENT_NORMALIZED_SHA256"]
    # The durable source used artifact order; the unchanged runner normalizes ticket positions.
    assert _payload("current")["BEST_PORTFOLIO_SHA256"] == (
        "10d4ef5102ad824fb2c96503501694bef3f878504c8c164698c86f2f1ce35a3b"
    )
    source = cast(dict[str, str], _payload("current")["SOURCE_AUTHORITY"])
    assert source["COMMIT"] == "82e88ada111bf6d0999ac9c0c167a160a6ae5df8"
    assert source["FILE_SHA256"] == (
        "0d948aa4556e9493e0c55d9fb8436c7b0aaaa9f2744bb9ecf85f16405c23cc1c"
    )


@pytest.mark.parametrize(
    "label,field",
    [
        ("current", "BEST_PORTFOLIO_SHA256"),
        ("historical", "BEST_SHA256"),
    ],
)
def test_wrong_portfolio_sha_blocks(
    label: str,
    field: str,
    draws49: DrawMasks,
    tmp_path: Path,
) -> None:
    artifact, digest = _changed_artifact(tmp_path, label, **{field: "0" * 64})
    with pytest.raises(cycle.CycleError, match=r"sha256|start hash"):
        cycle.load_incumbent_start(
            ROOT,
            artifact,
            incumbent_artifact_sha256=digest,
            draws=draws49,
        )


def test_caller_authority_pin_blocks_substituted_artifact(draws49: DrawMasks) -> None:
    with pytest.raises(cycle.CycleError, match=r"caller.*authority"):
        cycle.load_incumbent_start(
            ROOT,
            FIXTURES / "historical.json",
            incumbent_artifact_sha256=_digest(FIXTURES / "current.json"),
            draws=draws49,
        )


def test_wrong_exact_count_blocks(draws49: DrawMasks, tmp_path: Path) -> None:
    artifact, digest = _changed_artifact(tmp_path, "current", BEST_COUNT=313_263_887)
    with pytest.raises(cycle.CycleError, match="canonical count 313263888 != expected 313263887"):
        cycle.load_incumbent_start(
            ROOT,
            artifact,
            incumbent_artifact_sha256=digest,
            draws=draws49,
        )


@pytest.mark.parametrize(
    "artifact,digest",
    [
        (None, None),
        (Path("current.json"), None),
        (None, "0" * 64),
    ],
)
def test_missing_incumbent_blocks(
    artifact: Path | None,
    digest: str | None,
    draws49: DrawMasks,
) -> None:
    with pytest.raises(cycle.CycleError, match="explicit incumbent"):
        cycle.load_start(
            cycle.START_PRIMARY,
            ROOT,
            draws=draws49,
            incumbent_artifact=artifact,
            incumbent_artifact_sha256=digest,
        )


@pytest.mark.parametrize("argv", [[], ["--incumbent-artifact", "current.json"]])
def test_cli_requires_explicit_incumbent_and_authority_pin(argv: list[str]) -> None:
    with pytest.raises(SystemExit) as error:
        cycle.main(argv)
    assert error.value.code == 2


@pytest.mark.parametrize("defect", ["K19", "DUPLICATE", "OUT_OF_RANGE", "BOOLEAN"])
def test_invalid_k20_blocks_before_recount(
    defect: str,
    draws49: DrawMasks,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tickets = cast(list[list[int]], _payload("current")["BEST_PORTFOLIO"])
    if defect == "K19":
        tickets.pop()
    elif defect == "DUPLICATE":
        tickets[1] = tickets[0]
    elif defect == "OUT_OF_RANGE":
        tickets[0][0] = 50
    else:
        tickets[0][0] = True
    artifact, digest = _changed_artifact(tmp_path, "current", BEST_PORTFOLIO=tickets)

    def forbidden_recount(*args: object, **kwargs: object) -> int:
        pytest.fail("invalid structure reached the canonical evaluator")

    monkeypatch.setattr(ttc, "official_any_prize_outcome_count", forbidden_recount)
    with pytest.raises(cycle.CycleError):
        cycle.load_incumbent_start(
            ROOT,
            artifact,
            incumbent_artifact_sha256=digest,
            draws=draws49,
        )


def test_conflicting_sha_conventions_block(draws49: DrawMasks, tmp_path: Path) -> None:
    artifact, digest = _changed_artifact(tmp_path, "current", BEST_SHA256="0" * 64)
    with pytest.raises(cycle.CycleError, match=r"exactly one.*convention"):
        cycle.load_incumbent_start(
            ROOT,
            artifact,
            incumbent_artifact_sha256=digest,
            draws=draws49,
        )


def test_other_objective_blocks(draws49: DrawMasks, tmp_path: Path) -> None:
    artifact, digest = _changed_artifact(tmp_path, "current", EVENT="M3_PLUS")
    with pytest.raises(cycle.CycleError, match="OFFICIAL_ANY_PRIZE"):
        cycle.load_incumbent_start(
            ROOT,
            artifact,
            incumbent_artifact_sha256=digest,
            draws=draws49,
        )


def test_historical_exact_state_and_deterministic_proposal_prefix(draws49: DrawMasks) -> None:
    start = _fixture_start("historical", draws49)
    assert start.outcome_count == 313_239_661
    assert start.sha256 == "0045ac8837fc82e9a585d812173341ac12e05c5de201af7f8fedeacafa19e1ff"
    assert start.portfolio == ttc.normalize_portfolio(
        cast(list[list[int]], _payload("historical")["BEST_PORTFOLIO"]),
        pool_size=49,
    )
    prefix: list[list[object]] = []
    for quadruple in cycle.select_pilot_quadruples()[:2]:
        for spec in itertools.islice(
            cycle.iter_quadruple_specs(start.portfolio, quadruple, pool_size=49),
            64,
        ):
            emission = cycle.emit_spec(start.portfolio, spec, pool_size=49)
            prefix.append(
                [
                    list(quadruple),
                    list(spec.numbers),
                    spec.orientation,
                    None if emission is None else emission.sha256,
                ]
            )
    metadata = _payload("compatibility")
    assert len(prefix) == metadata["HISTORICAL_PREFIX_ATTEMPTS"] == 128
    assert (
        hashlib.sha256(json.dumps(prefix, separators=(",", ":")).encode()).hexdigest()
        == (metadata["HISTORICAL_PREFIX_SHA256"])
    )


def test_search_and_checkpoint_definitions_are_byte_unchanged_from_donor() -> None:
    source = Path(cycle.__file__).read_text(encoding="utf-8")
    frozen = cast(dict[str, str], _payload("compatibility")["FROZEN_DEFINITIONS_SHA256"])
    actual: dict[str, str] = {}
    for node in ast.parse(source).body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in frozen:
            segment = ast.get_source_segment(source, node)
            assert segment is not None
            actual[node.name] = hashlib.sha256(segment.encode()).hexdigest()
    assert actual == frozen
    assert "313_239_661" not in source and "313_263_888" not in source


@pytest.mark.parametrize("delta", [-1, 0, 1])
def test_promotion_and_result_identity_use_only_supplied_incumbent(
    delta: int,
    current_start: cycle.StartBinding,
    draws49: DrawMasks,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact = FIXTURES / "current.json"
    digest = _digest(artifact)
    best_count = current_start.outcome_count + delta

    def supplied_start(*args: object, **kwargs: object) -> cycle.StartBinding:
        assert kwargs["incumbent_artifact_sha256"] == digest
        return current_start

    def scan_stub(*args: object, **kwargs: object) -> dict[str, object]:
        # No worker pool, parity tasks or search is started in this binding test.
        assert args[0] == cycle.START_PRIMARY
        assert kwargs["incumbent_artifact"] == artifact
        assert kwargs["incumbent_artifact_sha256"] == digest
        best: dict[str, object] = {
            "COUNT": best_count,
            "SHA256": "1" * 64,
            "DELTA_VS_START": delta,
            "EXACT_PROBABILITY": "test",
            "QUADRUPLE": [0, 1, 2, 3],
            "NUMBERS": [1, 2, 3, 4],
            "ORIENTATION": cycle.FORWARD.name,
            "REMOVED": [],
            "ADDED": [],
        }
        return {
            "STATUS": "COMPLETE",
            "START_COUNT": current_start.outcome_count,
            "START_SHA256": current_start.sha256,
            "PILOT_WALL_SECONDS": 1.0,
            "PRECOMPUTE_CPU_SECONDS": 0.0,
            "SCORING_CPU_SECONDS": 0.0,
            "PER_QUADRUPLE": [None] * 24,
            "BEST": best,
            "BEST_TIE_COUNT": 1,
            "PARITY": {"SAMPLE_COUNT": 72, "MISMATCHES": 0},
            "RAW_ATTEMPTS": 1,
            "LEGAL": 1,
            "DEDUPLICATED": 1,
            "EXACT_SCORED": 1,
            "CANDIDATES_PER_SECOND": 1,
            "BEST_CANONICAL_RECOUNT_STATUS": "PASS",
        }

    def write_stub(*args: object) -> None:
        return None

    monkeypatch.setattr(cycle, "load_incumbent_start", supplied_start)

    def draw_stub(_: int) -> DrawMasks:
        return draws49

    monkeypatch.setattr(ttc, "load_draws", draw_stub)
    monkeypatch.setattr(cycle, "run_start", scan_stub)
    monkeypatch.setattr(cycle, "_write_json_atomically", write_stub)
    record = cycle.run_pilot(
        ROOT,
        incumbent_artifact=artifact,
        incumbent_artifact_sha256=digest,
        result_path=ROOT / ".task-data/binding-test-result.json",
        runtime_dir=tmp_path,
        control_wall_budget_seconds=0,
    )
    assert record["BASELINE_OUTCOMES"] == current_start.outcome_count
    assert record["BASELINE_SHA"] == current_start.sha256
    assert record["INCUMBENT_ARTIFACT_SHA256"] == digest
    assert record["STRICT_GAIN"] == ("YES" if delta > 0 else "NO")
    assert record["EVENT"] == record["PROMOTION_AUTHORITY"] == "OFFICIAL_ANY_PRIZE"


def test_launch_rejects_bad_count_before_owner_or_pilot(
    draws49: DrawMasks,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact, digest = _changed_artifact(tmp_path, "current", BEST_COUNT=313_263_889)

    def draw_stub(_: int) -> DrawMasks:
        return draws49

    monkeypatch.setattr(ttc, "load_draws", draw_stub)
    with pytest.raises(cycle.CycleError, match="canonical count"):
        cycle.main(
            [
                "--repo-root",
                str(tmp_path),
                "--incumbent-artifact",
                str(artifact),
                "--incumbent-artifact-sha256",
                digest,
                "--result-path",
                "result.json",
                "--runtime-dir",
                "runtime",
                "--owner-conversation-id",
                "binding-test",
            ]
        )
    assert not (tmp_path / cycle.OWNER_RECORD_PATH).exists()
    assert not (tmp_path / "runtime").exists()
    assert not (tmp_path / "result.json").exists()
