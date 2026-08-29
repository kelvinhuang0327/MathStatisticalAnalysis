"""Run the sealed Phase 12 paired historical refinement-value evaluation.

The Phase 10/11 seed and terminal portfolios are replayed as immutable,
task-local PORTFOLIO strategies.  Prediction history is still resolved by the
canonical Replay stack, with one strictly-prior draw required for eligibility.
Scientific JSON contains no timestamps, runtime measurements, RNG, inferred
decision threshold, or Power Lotto Zone-2 score.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from fractions import Fraction
from pathlib import Path
from typing import Any, ClassVar, cast

from lottolab.application.ports import DrawHistoryReader
from lottolab.application.use_cases.build_causal_history import (
    BuildCausalHistory,
    BuildCausalHistoryStatus,
)
from lottolab.application.use_cases.generate_bet import (
    GeneratePortfolio,
    GeneratePortfolioStatus,
)
from lottolab.application.use_cases.replay_historical_portfolio_predictions import (
    ReplayHistoricalPortfolioPredictions,
    ReplayHistoricalPortfolioPredictionsInput,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.lottery_rules import (
    BIG_LOTTO_RULE_CONTRACT,
    DAILY_539_RULE_CONTRACT,
    POWER_LOTTO_RULE_CONTRACT,
    LotteryRuleContract,
    score_big_lotto_ticket,
)
from lottolab.domain.prize_evaluation import evaluate_daily_539_ticket
from lottolab.domain.replay_history import ReplayCausalDrawRow
from lottolab.domain.replay_predictions import (
    ReplayPortfolioPredictionSnapshot,
    ReplayTarget,
)
from lottolab.domain.strategies import LifecycleStatus, ResponseShape, StrategyDescriptor
from lottolab.domain.strategy_success_evaluation import (
    BigLottoSuccessCriterion,
    Daily539SuccessCriterion,
    ExactSuccessRate,
    PowerLottoSuccessCriterion,
    PowerLottoZone2Requirement,
    SuccessCriterion,
    WindowKind,
    WindowSuccessSummary,
    evaluate_strategy_success_windows,
)
from lottolab.domain.strategy_success_measurement import (
    DEFAULT_WINDOW_POLICY,
    DEFAULT_WINDOW_POLICY_VERSION,
    BigLottoOutcomeSignature,
    BigLottoPortfolioOutcomeSignature,
    Daily539OutcomeSignature,
    EvidenceStatus,
    MeasurementMode,
    MeasurementProvenance,
    OutcomeEligibility,
    OutcomeSignature,
    PowerLottoOutcomeSignature,
    SelectionIdentity,
    StrategySuccessMeasurement,
)
from lottolab.infrastructure.persistence.draw_schema import (
    LocalDataPaths,
    open_database,
    resolve_local_data_paths,
    verify_schema_read_only,
)
from lottolab.infrastructure.persistence.replay_history_reader import SQLiteDrawHistoryReader
from lottolab.strategies.adapters.base import CausalDrawRow, PortfolioBetAdapter
from lottolab.strategies.catalog import StrategyCatalog

STUDY_ID = "STRATEGY_MATRIX_PHASE12_PAIRED_REFINEMENT_VALUE_GATE_V1"
TASK_ID = "STRATEGY_MATRIX_PHASE12_PAIRED_REFINEMENT_VALUE_GATE_R1"
OWNER_AUTHORIZATION = "AUTHORIZE_PHASE12_PAIRED_REFINEMENT_VALUE_GATE_R1"
PINNED_BASE_COMMIT = "0645f31a2bcaf494760d4bc1675bc1c3ed9a076d"
PINNED_BASE_TREE = "8b9fa40728f1bea3fb585d86f426a36489e0debf"
K_SCOPE = (10, 15, 20)
AGGREGATE_INTERPRETATION = "INCONCLUSIVE"

PHASE10_RESULT_PATH = Path(
    "docs/research/matrix-native-results/"
    "reference-e-iterative-exact-one-exchange-ascent-b649-v1-result.json"
)
PHASE11_RESULT_PATH = Path(
    "docs/research/matrix-native-results/"
    "strategy-matrix-phase11-t539-p638-zone1-"
    "iterative-exact-1exchange-replication-v1-result.json"
)
OUTPUT_PATH = Path(
    "docs/research/matrix-native-results/"
    "strategy-matrix-phase12-paired-refinement-value-gate-v1-result.json"
)

LOCKED_SOURCE_ARTIFACT_SHA256 = {
    PHASE10_RESULT_PATH: "099ca254ff9143c00953bde62329b2b8ae298a1f8e2bcfb757ca1c263119aa2c",
    PHASE11_RESULT_PATH: "c7904f716a61fb6b43df2091664ef55a1972b9212cac3490133d0accd4ae7290",
}

LOCKED_PAIR_SHA256: dict[tuple[str, int], tuple[str, str]] = {
    ("BIG_LOTTO", 10): (
        "4167482d739c59896ad9d50d23ebad89c1d22e787df8a34ae2b6bfd9206a69d5",
        "4167482d739c59896ad9d50d23ebad89c1d22e787df8a34ae2b6bfd9206a69d5",
    ),
    ("BIG_LOTTO", 15): (
        "ba6f516af65c31246550827ddcdcff2fcbf3f588be336e6de959a59dc898d1c8",
        "8057138edd980413fa52607144d66a90372e68d251654998e3a1767fd3d9ce83",
    ),
    ("BIG_LOTTO", 20): (
        "a107d9cb5c7e0def7b19ccf2a6d02306b25bc0efe3443ea9899f3a4755429a4a",
        "bf561d28d26961043f112ba8ed762ba9535666022c7df6bcefe49b8a21412710",
    ),
    ("DAILY_539", 10): (
        "6a938cdc39299fb5545ad95dd6ce893413637acfa95abd2f0c861168c06521cc",
        "6a938cdc39299fb5545ad95dd6ce893413637acfa95abd2f0c861168c06521cc",
    ),
    ("DAILY_539", 15): (
        "2fafb5277e561782b34e82bf8d7eb3b84e99a166cd6256214891beb2330e932b",
        "09734dae0c4c752d797f54ef7cbfa60bedb2e2e5b971bca7188a953da60c2a51",
    ),
    ("DAILY_539", 20): (
        "2015e3f326a136ab34ea8fe2b98f15fd0a519cb44df28f418d488d5b6d6a33f7",
        "2015e3f326a136ab34ea8fe2b98f15fd0a519cb44df28f418d488d5b6d6a33f7",
    ),
    ("POWER_LOTTO_ZONE1", 10): (
        "3a03740b2f1b5ca676bc5abdaba331ed1e5dff22e68155dc74e13c6ec0e6cab1",
        "47b8b68929e3ac99a9fb5029fc4465dafe9cefbbe2202e25c3a2d0b8ab342a57",
    ),
    ("POWER_LOTTO_ZONE1", 15): (
        "365e8552780e46ec2c81e82cc3708a29bc7665b8642d452535e4f78386b06dbc",
        "be4dfc831ba8ccf31b6c85e869970b51f3ea8472d5283e4bbc42b2127d0d755c",
    ),
    ("POWER_LOTTO_ZONE1", 20): (
        "94e969e7c87b8781a9a6fe7f008b68a3098d9587de697eec35556f20dfcfdf57",
        "63ca63cac6a94fc956fe344ff026818d3322f6f3610c9ed7d7004c5eec894728",
    ),
}

LOCKED_CONTRACT_FILE_SHA256 = {
    "src/lottolab/application/use_cases/build_causal_history.py": (
        "0ea3990629890ba18e0d09184275f391b3961f2e7c0df6ec0b887a6fabdd4e81"
    ),
    "src/lottolab/application/use_cases/replay_historical_portfolio_predictions.py": (
        "498e66a99dbbbe7c9185bc778ddbee63979e8efad8b0725997bc723c8d537a15"
    ),
    "src/lottolab/domain/lottery_rules.py": (
        "622e19e926dd74c4145c1e1e70da4c0f13a895b2b17ae61b6545c4c70227aba2"
    ),
    "src/lottolab/domain/prize_evaluation.py": (
        "976c977eee7475ea9b824ff6da2725308df6eef801ae8e257497bdec67ca4228"
    ),
    "src/lottolab/domain/strategy_success_evaluation.py": (
        "93d487233af70bd2cc622ef4f136883bcf421986a8f8a19eb509da6d516233fc"
    ),
    "src/lottolab/domain/strategy_success_measurement.py": (
        "9699fec3899127243ba0640608c408d4aed4adc47875e989645c1e835785fce7"
    ),
    "src/lottolab/infrastructure/persistence/replay_history_reader.py": (
        "fa27892eeb1d73b55dacc242ec4cfd4e3b607826a37e4f2952f3b1ff461ba020"
    ),
}

LOCKED_RULE_CONTRACT_SHA256 = {
    LotteryType.BIG_LOTTO: "481bc001d2a92e6b8b7df7dc5b07d9615383cfb89d2ebe2fb2c8881bd944bfa4",
    LotteryType.DAILY_539: "85c9433220abd26ae6744cca75cac705c8d49e770984dc000da97f06effab9c5",
    LotteryType.POWER_LOTTO: (
        "d40eb754d02e386c1eb7be7bc6a023976c7bba0e5e17fb7d92db2b706e93a565"
    ),
}
LOCKED_WINDOW_POLICY_SHA256 = (
    "1b2422b97c4a96484b86d695f947693b94d060300a654c803b0bed18bf88a87b"
)
LOCKED_CRITERION_SHA256 = {
    LotteryType.BIG_LOTTO: "51595ba035fe85a8f575dffa357854166fdd84e00df3c31a04e225aa63c04235",
    LotteryType.DAILY_539: "a84abde23b761d8274ac8c30df72ac758f49f00c52f8096a16374ea17848520a",
    LotteryType.POWER_LOTTO: (
        "39b5a65e1b7f5ac2fe63d0b273c1b4f4e4aff7b561d4eb2e86f6dbf08a28a533"
    ),
}

Portfolio = tuple[tuple[int, ...], ...]


@dataclass(frozen=True, slots=True)
class FrozenPortfolioMember:
    role: str
    source_field: str
    portfolio: Portfolio
    portfolio_sha256: str

    @property
    def strategy_id(self) -> str:
        return f"phase12_{self.role}_{self.portfolio_sha256}"


@dataclass(frozen=True, slots=True)
class FrozenPortfolioPair:
    structure_id: str
    lottery_type: LotteryType
    zone: str | None
    k: int
    source_artifact_path: Path
    source_artifact_sha256: str
    baseline: FrozenPortfolioMember
    refined: FrozenPortfolioMember


@dataclass(frozen=True, slots=True)
class TargetOutcome:
    lottery_type: LotteryType
    draw_number: str
    draw_date: date
    main_numbers: tuple[int, ...]
    special_number: int | None
    normalized_record_hash: str
    source_name: str | None
    source_reference: str | None
    ingestion_run_id: str

    @property
    def token(self) -> str:
        return f"{self.draw_date.isoformat()}#{self.draw_number}"

    def canonical_source_dict(self) -> dict[str, object]:
        return {
            "draw_date": self.draw_date.isoformat(),
            "draw_number": self.draw_number,
            "ingestion_run_id": self.ingestion_run_id,
            "main_numbers": list(self.main_numbers),
            "normalized_record_hash": self.normalized_record_hash,
            "source_name": self.source_name,
            "source_reference": self.source_reference,
            "special_numbers": (
                [] if self.special_number is None else [self.special_number]
            ),
        }


@dataclass(frozen=True, slots=True)
class DatasetSnapshot:
    paths: LocalDataPaths
    database_sha256: str
    schema_migrations: tuple[dict[str, object], ...]
    targets_by_lottery: dict[LotteryType, tuple[TargetOutcome, ...]]
    partition_metadata: dict[LotteryType, dict[str, object]]


@dataclass(frozen=True, slots=True)
class MemberEvaluation:
    document: dict[str, object]
    observations: tuple[StrategySuccessMeasurement, ...]
    all_target_tokens: tuple[str, ...]
    eligible_target_tokens: tuple[str, ...]
    windows: tuple[WindowSuccessSummary, ...]


def canonical_json_bytes(payload: object) -> bytes:
    return (json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n").encode()


def _canonical_compact_bytes(payload: object) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def portfolio_sha256(portfolio: Portfolio) -> str:
    return _sha256_bytes(json.dumps(portfolio, separators=(",", ":")).encode())


def _git_value(*arguments: str) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def verify_current_base_identity() -> dict[str, str]:
    observed = {
        "commit": _git_value("rev-parse", f"{PINNED_BASE_COMMIT}^{{commit}}"),
        "tree": _git_value("rev-parse", f"{PINNED_BASE_COMMIT}^{{tree}}"),
    }
    if observed != {"commit": PINNED_BASE_COMMIT, "tree": PINNED_BASE_TREE}:
        raise ValueError(f"CANONICAL_BASE_IDENTITY_MISMATCH: {observed}")
    ancestry = subprocess.run(
        ["git", "merge-base", "--is-ancestor", PINNED_BASE_COMMIT, "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    if ancestry.returncode != 0:
        raise ValueError("CANONICAL_BASE_ANCESTRY_MISMATCH")
    return observed


def _verified_json(path: Path, expected_sha256: str) -> dict[str, Any]:
    raw = path.read_bytes()
    actual_sha256 = _sha256_bytes(raw)
    if actual_sha256 != expected_sha256:
        raise ValueError(
            f"SOURCE_ARTIFACT_IDENTITY_MISMATCH {path}: "
            f"expected {expected_sha256}, got {actual_sha256}"
        )
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError(f"source artifact root must be an object: {path}")
    return cast(dict[str, Any], payload)


def _mapping(value: object, locator: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{locator} must be an object")
    return cast(dict[str, Any], value)


def _portfolio(
    value: object,
    *,
    locator: str,
    rule: LotteryRuleContract,
    k: int,
) -> Portfolio:
    if not isinstance(value, list):
        raise ValueError(f"{locator} must be an array")
    tickets: list[tuple[int, ...]] = []
    for index, raw_ticket in enumerate(cast(list[object], value)):
        if not isinstance(raw_ticket, list):
            raise ValueError(f"{locator}[{index}] must be an array")
        raw_numbers = cast(list[object], raw_ticket)
        if not all(type(number) is int for number in raw_numbers):
            raise ValueError(f"{locator}[{index}] must contain exact integers")
        ticket = tuple(cast(list[int], raw_numbers))
        if (
            len(ticket) != rule.main_number_count
            or len(set(ticket)) != rule.main_number_count
            or ticket != tuple(sorted(ticket))
            or any(
                number < rule.main_number_min or number > rule.main_number_max
                for number in ticket
            )
        ):
            raise ValueError(f"{locator}[{index}] is not a canonical legal ticket")
        tickets.append(ticket)
    portfolio = tuple(tickets)
    if len(portfolio) != k or len(set(portfolio)) != k:
        raise ValueError(f"{locator} must contain exactly {k} unique tickets")
    return portfolio


def _member(
    *,
    role: str,
    source_field: str,
    raw_portfolio: object,
    declared_sha256: object,
    expected_sha256: str,
    rule: LotteryRuleContract,
    k: int,
) -> FrozenPortfolioMember:
    portfolio = _portfolio(raw_portfolio, locator=source_field, rule=rule, k=k)
    computed_sha256 = portfolio_sha256(portfolio)
    if declared_sha256 != expected_sha256 or computed_sha256 != expected_sha256:
        raise ValueError(
            f"PAIR_IDENTITY_MISMATCH {source_field}: expected {expected_sha256}, "
            f"declared {declared_sha256}, computed {computed_sha256}"
        )
    return FrozenPortfolioMember(
        role=role,
        source_field=source_field,
        portfolio=portfolio,
        portfolio_sha256=computed_sha256,
    )


def load_frozen_pairs() -> tuple[FrozenPortfolioPair, ...]:
    phase10 = _verified_json(
        PHASE10_RESULT_PATH, LOCKED_SOURCE_ARTIFACT_SHA256[PHASE10_RESULT_PATH]
    )
    phase11 = _verified_json(
        PHASE11_RESULT_PATH, LOCKED_SOURCE_ARTIFACT_SHA256[PHASE11_RESULT_PATH]
    )
    phase10_per_k = _mapping(phase10.get("per_k"), "phase10.per_k")
    phase11_structures = _mapping(phase11.get("structures"), "phase11.structures")
    pairs: list[FrozenPortfolioPair] = []

    for k in K_SCOPE:
        row = _mapping(phase10_per_k.get(str(k)), f"phase10.per_k.{k}")
        expected_baseline, expected_refined = LOCKED_PAIR_SHA256[("BIG_LOTTO", k)]
        pairs.append(
            FrozenPortfolioPair(
                structure_id="BIG_LOTTO",
                lottery_type=LotteryType.BIG_LOTTO,
                zone=None,
                k=k,
                source_artifact_path=PHASE10_RESULT_PATH,
                source_artifact_sha256=LOCKED_SOURCE_ARTIFACT_SHA256[PHASE10_RESULT_PATH],
                baseline=_member(
                    role="baseline",
                    source_field=f"per_k.{k}.phase9_seed_portfolio",
                    raw_portfolio=row.get("phase9_seed_portfolio"),
                    declared_sha256=row.get("phase9_seed_portfolio_sha256"),
                    expected_sha256=expected_baseline,
                    rule=BIG_LOTTO_RULE_CONTRACT,
                    k=k,
                ),
                refined=_member(
                    role="refined",
                    source_field=f"per_k.{k}.terminal_portfolio",
                    raw_portfolio=row.get("terminal_portfolio"),
                    declared_sha256=row.get("terminal_portfolio_sha256"),
                    expected_sha256=expected_refined,
                    rule=BIG_LOTTO_RULE_CONTRACT,
                    k=k,
                ),
            )
        )

    phase11_specs = (
        ("DAILY_539", LotteryType.DAILY_539, None, DAILY_539_RULE_CONTRACT),
        (
            "POWER_LOTTO_ZONE1",
            LotteryType.POWER_LOTTO,
            "ZONE1",
            POWER_LOTTO_RULE_CONTRACT,
        ),
    )
    for structure_id, lottery_type, zone, rule in phase11_specs:
        structure = _mapping(
            phase11_structures.get(structure_id), f"phase11.structures.{structure_id}"
        )
        per_k = _mapping(structure.get("per_k"), f"phase11.structures.{structure_id}.per_k")
        for k in K_SCOPE:
            row = _mapping(per_k.get(str(k)), f"{structure_id}.per_k.{k}")
            expected_baseline, expected_refined = LOCKED_PAIR_SHA256[(structure_id, k)]
            prefix = f"structures.{structure_id}.per_k.{k}"
            pairs.append(
                FrozenPortfolioPair(
                    structure_id=structure_id,
                    lottery_type=lottery_type,
                    zone=zone,
                    k=k,
                    source_artifact_path=PHASE11_RESULT_PATH,
                    source_artifact_sha256=LOCKED_SOURCE_ARTIFACT_SHA256[
                        PHASE11_RESULT_PATH
                    ],
                    baseline=_member(
                        role="baseline",
                        source_field=f"{prefix}.seed_method_e_portfolio",
                        raw_portfolio=row.get("seed_method_e_portfolio"),
                        declared_sha256=row.get("seed_method_e_portfolio_sha256"),
                        expected_sha256=expected_baseline,
                        rule=rule,
                        k=k,
                    ),
                    refined=_member(
                        role="refined",
                        source_field=f"{prefix}.terminal_portfolio",
                        raw_portfolio=row.get("terminal_portfolio"),
                        declared_sha256=row.get("terminal_portfolio_sha256"),
                        expected_sha256=expected_refined,
                        rule=rule,
                        k=k,
                    ),
                )
            )

    if len(pairs) != 9 or {(pair.structure_id, pair.k) for pair in pairs} != set(
        LOCKED_PAIR_SHA256
    ):
        raise ValueError("MISSING_OR_AMBIGUOUS_PAIR_IDENTITY")
    return tuple(pairs)


def criterion_for_lottery(lottery_type: LotteryType) -> SuccessCriterion:
    if lottery_type is LotteryType.BIG_LOTTO:
        return BigLottoSuccessCriterion(
            minimum_main_hits=3,
            require_special_hit=False,
            expected_mode=MeasurementMode.LEGAL_TICKET_PRIZE,
        )
    if lottery_type is LotteryType.DAILY_539:
        return Daily539SuccessCriterion(
            minimum_main_hits=3,
            expected_mode=MeasurementMode.LEGAL_TICKET_PRIZE,
        )
    if lottery_type is LotteryType.POWER_LOTTO:
        return PowerLottoSuccessCriterion(
            minimum_zone1_hits=3,
            zone2_requirement=PowerLottoZone2Requirement.NOT_USED,
            expected_mode=MeasurementMode.LEGAL_TICKET_PRIZE,
        )
    raise ValueError(f"unsupported Phase 12 lottery: {lottery_type.value}")


def verify_contract_authority() -> dict[str, object]:
    file_identities: dict[str, str] = {}
    for raw_path, expected_sha256 in LOCKED_CONTRACT_FILE_SHA256.items():
        actual_sha256 = sha256_file(Path(raw_path))
        if actual_sha256 != expected_sha256:
            raise ValueError(
                f"EVALUATOR_AUTHORITY_IDENTITY_MISMATCH {raw_path}: "
                f"expected {expected_sha256}, got {actual_sha256}"
            )
        file_identities[raw_path] = actual_sha256

    rules = (
        BIG_LOTTO_RULE_CONTRACT,
        DAILY_539_RULE_CONTRACT,
        POWER_LOTTO_RULE_CONTRACT,
    )
    rule_identities: dict[str, object] = {}
    for rule in rules:
        actual_sha256 = _sha256_bytes(rule.canonical_json().encode())
        if actual_sha256 != LOCKED_RULE_CONTRACT_SHA256[rule.lottery_type]:
            raise ValueError(f"SCORING_RULE_AUTHORITY_MISMATCH {rule.lottery_type.value}")
        rule_identities[rule.lottery_type.value] = {
            "canonical_sha256": actual_sha256,
            "contract_version": rule.contract_version,
        }

    window_document = DEFAULT_WINDOW_POLICY.canonical_dict()
    window_sha256 = _sha256_bytes(_canonical_compact_bytes(window_document))
    if window_sha256 != LOCKED_WINDOW_POLICY_SHA256:
        raise ValueError("TARGET_WINDOW_AUTHORITY_MISMATCH")

    criteria: dict[str, object] = {}
    for lottery_type in (
        LotteryType.BIG_LOTTO,
        LotteryType.DAILY_539,
        LotteryType.POWER_LOTTO,
    ):
        criterion = criterion_for_lottery(lottery_type)
        actual_sha256 = _sha256_bytes(criterion.canonical_json().encode())
        if actual_sha256 != LOCKED_CRITERION_SHA256[lottery_type]:
            raise ValueError(f"METRIC_AUTHORITY_MISMATCH {lottery_type.value}")
        criteria[lottery_type.value] = {
            **criterion.canonical_dict(),
            "canonical_sha256": actual_sha256,
        }

    return {
        "contract_file_sha256": file_identities,
        "criteria": criteria,
        "rule_contracts": rule_identities,
        "window_policy": {
            **window_document,
            "canonical_sha256": window_sha256,
        },
    }


def _text(value: object, locator: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{locator} must be non-empty text")
    return value


def _optional_text(value: object, locator: str) -> str | None:
    if value is None:
        return None
    return _text(value, locator)


def _integer(value: object, locator: str) -> int:
    if type(value) is not int:
        raise ValueError(f"{locator} must be an exact integer")
    return value


def _integer_tuple_from_json(value: object, locator: str) -> tuple[int, ...]:
    if not isinstance(value, str):
        raise ValueError(f"{locator} must be JSON text")
    decoded = json.loads(value)
    if not isinstance(decoded, list) or any(
        type(item) is not int for item in cast(list[object], decoded)
    ):
        raise ValueError(f"{locator} must decode to an integer array")
    return tuple(cast(list[int], decoded))


def load_dataset_snapshot(paths: LocalDataPaths, database_sha256: str) -> DatasetSnapshot:
    if verify_schema_read_only(paths) is not True:
        raise ValueError("DATASET_IDENTITY_UNRESOLVED")
    targets_by_lottery: dict[LotteryType, tuple[TargetOutcome, ...]] = {}
    partition_metadata: dict[LotteryType, dict[str, object]] = {}
    with open_database(paths, read_only=True) as connection:
        migration_rows = cast(
            list[tuple[object, ...]],
            connection.execute(
                "SELECT version, name, checksum FROM schema_migrations ORDER BY version"
            ).fetchall(),
        )
        migrations: tuple[dict[str, object], ...] = tuple(
            cast(
                dict[str, object],
                {
                "checksum": _text(row[2], "schema_migrations.checksum"),
                "name": _text(row[1], "schema_migrations.name"),
                    "version": _integer(row[0], "schema_migrations.version"),
                },
            )
            for row in migration_rows
        )

        for lottery_type in (
            LotteryType.BIG_LOTTO,
            LotteryType.DAILY_539,
            LotteryType.POWER_LOTTO,
        ):
            rows = cast(
                list[tuple[object, ...]],
                connection.execute(
                    """
                    SELECT draw_number, draw_date, main_numbers_json,
                           special_numbers_json, normalized_record_hash,
                           source_name, source_reference, ingestion_run_id
                    FROM draws
                    WHERE lottery_type = ?
                    ORDER BY draw_date ASC, CAST(draw_number AS INTEGER) ASC
                    """,
                    (lottery_type.value,),
                ).fetchall(),
            )
            targets: list[TargetOutcome] = []
            for row_index, row in enumerate(rows):
                draw_number = _text(row[0], f"{lottery_type.value}[{row_index}].draw_number")
                draw_date_value = date.fromisoformat(
                    _text(row[1], f"{lottery_type.value}[{row_index}].draw_date")
                )
                main_numbers = _integer_tuple_from_json(
                    row[2], f"{lottery_type.value}[{row_index}].main_numbers_json"
                )
                special_numbers = _integer_tuple_from_json(
                    row[3], f"{lottery_type.value}[{row_index}].special_numbers_json"
                )
                rule = {
                    LotteryType.BIG_LOTTO: BIG_LOTTO_RULE_CONTRACT,
                    LotteryType.DAILY_539: DAILY_539_RULE_CONTRACT,
                    LotteryType.POWER_LOTTO: POWER_LOTTO_RULE_CONTRACT,
                }[lottery_type]
                expected_special_count = 1 if rule.special_number_required else 0
                if len(special_numbers) != expected_special_count:
                    raise ValueError(
                        f"{lottery_type.value}[{row_index}] special-number count mismatch"
                    )
                special_number = special_numbers[0] if special_numbers else None
                ReplayCausalDrawRow(
                    lottery_type=lottery_type,
                    draw_number=draw_number,
                    draw_date=draw_date_value,
                    main_numbers=main_numbers,
                    special_number=special_number,
                )
                targets.append(
                    TargetOutcome(
                        lottery_type=lottery_type,
                        draw_number=draw_number,
                        draw_date=draw_date_value,
                        main_numbers=main_numbers,
                        special_number=special_number,
                        normalized_record_hash=_text(
                            row[4], f"{lottery_type.value}[{row_index}].normalized_record_hash"
                        ),
                        source_name=_optional_text(
                            row[5], f"{lottery_type.value}[{row_index}].source_name"
                        ),
                        source_reference=_optional_text(
                            row[6], f"{lottery_type.value}[{row_index}].source_reference"
                        ),
                        ingestion_run_id=_text(
                            row[7], f"{lottery_type.value}[{row_index}].ingestion_run_id"
                        ),
                    )
                )
            if not targets:
                raise ValueError(f"DATASET_IDENTITY_UNRESOLVED {lottery_type.value}")
            frozen_targets = tuple(targets)
            target_rows = [target.canonical_source_dict() for target in frozen_targets]
            source_counts = Counter(
                "null" if target.source_name is None else target.source_name
                for target in frozen_targets
            )
            targets_by_lottery[lottery_type] = frozen_targets
            partition_metadata[lottery_type] = {
                "canonical_rows_sha256": _sha256_bytes(
                    _canonical_compact_bytes(target_rows)
                ),
                "distinct_ingestion_run_count": len(
                    {target.ingestion_run_id for target in frozen_targets}
                ),
                "draw_count": len(frozen_targets),
                "first_draw": {
                    "draw_date": frozen_targets[0].draw_date.isoformat(),
                    "draw_number": frozen_targets[0].draw_number,
                },
                "last_draw": {
                    "draw_date": frozen_targets[-1].draw_date.isoformat(),
                    "draw_number": frozen_targets[-1].draw_number,
                },
                "source_name_counts": dict(sorted(source_counts.items())),
            }

    return DatasetSnapshot(
        paths=paths,
        database_sha256=database_sha256,
        schema_migrations=migrations,
        targets_by_lottery=targets_by_lottery,
        partition_metadata=partition_metadata,
    )


def _adapter_for(
    member: FrozenPortfolioMember,
    lottery_type: LotteryType,
) -> PortfolioBetAdapter:
    adapter_strategy_id = member.strategy_id
    adapter_strategy_name = f"Phase 12 frozen {member.role} {member.portfolio_sha256}"
    adapter_strategy_version = member.portfolio_sha256
    adapter_lottery_type = lottery_type
    adapter_ticket_count = len(member.portfolio)
    adapter_portfolio = member.portfolio

    class TaskFrozenPortfolioAdapter(PortfolioBetAdapter):
        strategy_id: ClassVar[str] = adapter_strategy_id
        strategy_name: ClassVar[str] = adapter_strategy_name
        strategy_version: ClassVar[str] = adapter_strategy_version
        min_history: ClassVar[int] = 1
        supported_lottery_types: ClassVar[tuple[LotteryType, ...]] = (
            adapter_lottery_type,
        )
        native_ticket_count: ClassVar[int] = adapter_ticket_count

        def _predict_all(
            self,
            history: tuple[CausalDrawRow, ...],
            lottery_type: LotteryType,
        ) -> Portfolio:
            if not history or lottery_type is not adapter_lottery_type:
                raise ValueError("task-local frozen portfolio received invalid causal input")
            return adapter_portfolio

    return TaskFrozenPortfolioAdapter()


def replay_frozen_pairs(
    *,
    lottery_type: LotteryType,
    targets: tuple[TargetOutcome, ...],
    pairs: tuple[FrozenPortfolioPair, ...],
    database_sha256: str,
    reader_factory: Callable[[], DrawHistoryReader],
) -> dict[str, tuple[ReplayPortfolioPredictionSnapshot, ...]]:
    members = tuple(
        member
        for pair in pairs
        for member in (pair.baseline, pair.refined)
    )
    descriptors = tuple(
        StrategyDescriptor(
            strategy_id=member.strategy_id,
            strategy_name=f"Phase 12 frozen {member.role} {member.portfolio_sha256}",
            version=member.portfolio_sha256,
            lottery_types=(lottery_type,),
            lifecycle_status=LifecycleStatus.ONLINE,
            executable=True,
            adapter_path=f"{__name__}:TaskFrozenPortfolioAdapter",
            min_history=1,
            provenance=(
                f"task:{TASK_ID}",
                f"portfolio_sha256:{member.portfolio_sha256}",
            ),
            response_shape=ResponseShape.PORTFOLIO,
            native_ticket_count=len(member.portfolio),
        )
        for member in members
    )
    catalog = StrategyCatalog(descriptors)
    adapters = {member.strategy_id: _adapter_for(member, lottery_type) for member in members}
    replay = ReplayHistoricalPortfolioPredictions(
        BuildCausalHistory(reader_factory),
        GeneratePortfolio(catalog, adapters),
        catalog,
    )
    replayed = replay.execute(
        ReplayHistoricalPortfolioPredictionsInput(
            lottery_type=lottery_type,
            dataset_id="LOTTOLAB_LOCAL_DRAW_DB_V3",
            dataset_version=database_sha256,
            targets=tuple(
                ReplayTarget(draw_number=target.draw_number, draw_date=target.draw_date)
                for target in targets
            ),
            strategy_ids=tuple(member.strategy_id for member in members),
            maximum_history_draws=1,
            minimum_history_draws=1,
        )
    )
    expected_snapshot_count = len(targets) * len(members)
    if len(replayed.snapshots) != expected_snapshot_count:
        raise ValueError(
            f"REPLAY_RESULT_OMISSION: expected {expected_snapshot_count}, "
            f"got {len(replayed.snapshots)}"
        )
    grouped: dict[str, list[ReplayPortfolioPredictionSnapshot]] = {
        member.strategy_id: [] for member in members
    }
    for snapshot in replayed.snapshots:
        grouped[snapshot.strategy_id].append(snapshot)
    result = {strategy_id: tuple(snapshots) for strategy_id, snapshots in grouped.items()}
    if any(len(snapshots) != len(targets) for snapshots in result.values()):
        raise ValueError("REPLAY_RESULT_OMISSION")
    return result


def _target_tokens(snapshots: tuple[ReplayPortfolioPredictionSnapshot, ...]) -> tuple[str, ...]:
    return tuple(
        f"{snapshot.target_draw_date.isoformat()}#{snapshot.target_draw_number}"
        for snapshot in snapshots
    )


def _tokens_sha256(tokens: tuple[str, ...]) -> str:
    return _sha256_bytes(_canonical_compact_bytes(list(tokens)))


def outcome_signature(
    lottery_type: LotteryType,
    portfolio: Portfolio,
    target: TargetOutcome,
) -> OutcomeSignature:
    if lottery_type is LotteryType.BIG_LOTTO:
        if target.special_number is None:
            raise ValueError("BIG_LOTTO target is missing its winning special number")
        return BigLottoPortfolioOutcomeSignature(
            tickets=tuple(
                BigLottoOutcomeSignature(
                    main_hits=(
                        score := score_big_lotto_ticket(
                            predicted_main_numbers=ticket,
                            winning_main_numbers=target.main_numbers,
                            winning_special_number=target.special_number,
                        )
                    ).main_hits,
                    special_hit=score.special_hit,
                )
                for ticket in portfolio
            )
        )
    if lottery_type is LotteryType.DAILY_539:
        maximum_hits = max(
            evaluate_daily_539_ticket(
                predicted_main_numbers=ticket,
                winning_main_numbers=target.main_numbers,
            ).zone1_hits
            for ticket in portfolio
        )
        return Daily539OutcomeSignature(main_hits=maximum_hits)
    if lottery_type is LotteryType.POWER_LOTTO:
        maximum_zone1_hits = max(
            len(set(ticket).intersection(target.main_numbers)) for ticket in portfolio
        )
        return PowerLottoOutcomeSignature(
            zone1_hits=maximum_zone1_hits,
            zone2_hit=None,
            eligibility=OutcomeEligibility.MISSING_PREDICTED_SECOND_ZONE,
        )
    raise ValueError(f"unsupported Phase 12 lottery: {lottery_type.value}")


def _closure_document(snapshot: ReplayPortfolioPredictionSnapshot) -> dict[str, object]:
    return {
        "causal_history_count": snapshot.causal_history_count,
        "cutoff_draw_date": (
            snapshot.cutoff_draw_date.isoformat()
            if snapshot.cutoff_draw_date is not None
            else None
        ),
        "cutoff_draw_number": snapshot.cutoff_draw_number,
        "history_reason_code": snapshot.history_reason_code,
        "history_status": snapshot.history_status,
        "prediction_reason_code": snapshot.prediction_reason_code,
        "prediction_status": snapshot.prediction_status,
        "target_draw_date": snapshot.target_draw_date.isoformat(),
        "target_draw_number": snapshot.target_draw_number,
    }


def _evaluate_member(
    *,
    pair: FrozenPortfolioPair,
    member: FrozenPortfolioMember,
    targets: tuple[TargetOutcome, ...],
    snapshots: tuple[ReplayPortfolioPredictionSnapshot, ...],
) -> MemberEvaluation:
    expected_tokens = tuple(target.token for target in targets)
    actual_tokens = _target_tokens(snapshots)
    if actual_tokens != expected_tokens:
        raise ValueError("UNEQUAL_TARGET_OR_SCORING_CONTRACT: replay target order changed")
    target_by_number = {target.draw_number: target for target in targets}
    criterion = criterion_for_lottery(pair.lottery_type)
    observations: list[StrategySuccessMeasurement] = []
    closures: list[dict[str, object]] = []
    eligible_tokens: list[str] = []

    for snapshot in snapshots:
        if snapshot.strategy_id != member.strategy_id:
            raise ValueError("PAIR_IDENTITY_MISMATCH: replay strategy id changed")
        if (
            snapshot.history_status != BuildCausalHistoryStatus.OK.value
            or snapshot.prediction_status != GeneratePortfolioStatus.OK.value
        ):
            closures.append(_closure_document(snapshot))
            continue
        if (
            snapshot.cutoff_draw_date is None
            or snapshot.cutoff_draw_number is None
            or snapshot.predicted_tickets is None
        ):
            raise ValueError("REPLAY_OK_SNAPSHOT_INCOMPLETE")
        target = target_by_number[snapshot.target_draw_number]
        if snapshot.target_draw_date != target.draw_date:
            raise ValueError("REPLAY_TARGET_IDENTITY_MISMATCH")
        cutoff_key = (snapshot.cutoff_draw_date, int(snapshot.cutoff_draw_number))
        target_key = (snapshot.target_draw_date, int(snapshot.target_draw_number))
        if cutoff_key >= target_key:
            raise ValueError("FUTURE_DATA_LEAKAGE")
        if snapshot.predicted_tickets != member.portfolio:
            raise ValueError("PAIR_IDENTITY_MISMATCH: portfolio order or content changed")

        target_token = target.token
        cutoff_token = (
            f"{snapshot.cutoff_draw_date.isoformat()}#{snapshot.cutoff_draw_number}"
        )
        observations.append(
            StrategySuccessMeasurement(
                mode=MeasurementMode.LEGAL_TICKET_PRIZE,
                selection=SelectionIdentity(
                    lottery=pair.lottery_type,
                    strategy_id=member.strategy_id,
                    strategy_version=member.portfolio_sha256,
                    max_bet_index=pair.k,
                    ticket_count=pair.k,
                ),
                outcome_signature=outcome_signature(
                    pair.lottery_type, member.portfolio, target
                ),
                evidence_status=EvidenceStatus.DESCRIPTIVE_ONLY,
                provenance=MeasurementProvenance(
                    strategy_version=member.portfolio_sha256,
                    parameter_or_config_identity=(
                        f"k={pair.k};portfolio_sha256={member.portfolio_sha256};"
                        f"criterion_sha256={LOCKED_CRITERION_SHA256[pair.lottery_type]}"
                    ),
                    history_cutoff=cutoff_token,
                    target_draw=target_token,
                    window_policy_version=DEFAULT_WINDOW_POLICY_VERSION,
                    game_rule_version={
                        LotteryType.BIG_LOTTO: BIG_LOTTO_RULE_CONTRACT,
                        LotteryType.DAILY_539: DAILY_539_RULE_CONTRACT,
                        LotteryType.POWER_LOTTO: POWER_LOTTO_RULE_CONTRACT,
                    }[pair.lottery_type].contract_version,
                    selection_family_identity=(
                        "ITERATIVE_EXACT_1EXCHANGE_REFINEMENT_V1:"
                        f"{member.role.upper()}"
                    ),
                    source_artifact_identity=(
                        f"{pair.source_artifact_path}@sha256:{pair.source_artifact_sha256}"
                    ),
                ),
                window_policy=DEFAULT_WINDOW_POLICY,
            )
        )
        eligible_tokens.append(target_token)

    if len(observations) + len(closures) != len(targets):
        raise ValueError("REPLAY_RESULT_OMISSION")
    if not observations:
        raise ValueError("NO_ELIGIBLE_PAIRED_TARGETS")
    frozen_observations = tuple(observations)
    windows = evaluate_strategy_success_windows(frozen_observations, criterion)
    return MemberEvaluation(
        document={
            "all_target_count": len(targets),
            "all_target_identities_sha256": _tokens_sha256(actual_tokens),
            "closure_count": len(closures),
            "closures": closures,
            "eligible_target_count": len(eligible_tokens),
            "eligible_target_identities_sha256": _tokens_sha256(tuple(eligible_tokens)),
            "portfolio_sha256": member.portfolio_sha256,
            "source_field": member.source_field,
            "strategy_id": member.strategy_id,
            "ticket_count": len(member.portfolio),
        },
        observations=frozen_observations,
        all_target_tokens=actual_tokens,
        eligible_target_tokens=tuple(eligible_tokens),
        windows=windows,
    )


def _delta(
    baseline: ExactSuccessRate,
    refined: ExactSuccessRate,
) -> dict[str, object]:
    if not baseline.is_available or not refined.is_available:
        return {
            "available": False,
            "denominator": 0,
            "exact": None,
            "numerator": 0,
        }
    value = Fraction(refined.numerator, refined.denominator) - Fraction(
        baseline.numerator, baseline.denominator
    )
    return {
        "available": True,
        "denominator": value.denominator,
        "exact": f"{value.numerator}/{value.denominator}",
        "numerator": value.numerator,
    }


def evaluate_pair(
    *,
    pair: FrozenPortfolioPair,
    targets: tuple[TargetOutcome, ...],
    snapshots_by_strategy: dict[str, tuple[ReplayPortfolioPredictionSnapshot, ...]],
) -> dict[str, object]:
    baseline = _evaluate_member(
        pair=pair,
        member=pair.baseline,
        targets=targets,
        snapshots=snapshots_by_strategy[pair.baseline.strategy_id],
    )
    refined = _evaluate_member(
        pair=pair,
        member=pair.refined,
        targets=targets,
        snapshots=snapshots_by_strategy[pair.refined.strategy_id],
    )
    if (
        baseline.all_target_tokens != refined.all_target_tokens
        or baseline.eligible_target_tokens != refined.eligible_target_tokens
        or len(pair.baseline.portfolio) != len(pair.refined.portfolio)
    ):
        raise ValueError("UNEQUAL_TARGET_OR_SCORING_CONTRACT")

    baseline_windows = {summary.window_kind: summary for summary in baseline.windows}
    refined_windows = {summary.window_kind: summary for summary in refined.windows}
    if (
        set(baseline_windows) != set(WindowKind)
        or set(refined_windows) != set(WindowKind)
    ):
        raise ValueError("TARGET_WINDOW_AUTHORITY_MISMATCH")
    window_documents: dict[str, object] = {}
    for window_kind in WindowKind:
        baseline_summary = baseline_windows[window_kind]
        refined_summary = refined_windows[window_kind]
        if (
            baseline_summary.first_target_draw != refined_summary.first_target_draw
            or baseline_summary.last_target_draw != refined_summary.last_target_draw
            or baseline_summary.source_draw_count != refined_summary.source_draw_count
            or baseline_summary.eligible_draw_count != refined_summary.eligible_draw_count
            or baseline_summary.excluded_draw_count != refined_summary.excluded_draw_count
            or baseline_summary.criterion_identity != refined_summary.criterion_identity
        ):
            raise ValueError("UNEQUAL_TARGET_OR_SCORING_CONTRACT")
        window_documents[window_kind.value] = {
            "baseline": baseline_summary.canonical_dict(),
            "paired_delta_success_rate": _delta(
                baseline_summary.success_rate, refined_summary.success_rate
            ),
            "refined": refined_summary.canonical_dict(),
        }

    return {
        "baseline": baseline.document,
        "criterion": criterion_for_lottery(pair.lottery_type).canonical_dict(),
        "k": pair.k,
        "lottery_type": pair.lottery_type.value,
        "pair_checks": {
            "all_target_identities_equal": True,
            "criterion_and_scoring_equal": True,
            "eligible_target_identities_equal": True,
            "no_result_silently_omitted": True,
            "ticket_count_equal": True,
            "ticket_position_semantics": "SOURCE_ORDER_PRESERVED",
        },
        "refined": refined.document,
        "source_artifact": {
            "path": str(pair.source_artifact_path),
            "sha256": pair.source_artifact_sha256,
        },
        "structure_id": pair.structure_id,
        "windows": window_documents,
        "zone": pair.zone,
    }


def build_result_payload(
    *,
    base_identity: dict[str, str],
    contract_authority: dict[str, object],
    dataset: DatasetSnapshot,
    pairs: tuple[FrozenPortfolioPair, ...],
) -> dict[str, object]:
    per_cell: list[dict[str, object]] = []
    for lottery_type in (
        LotteryType.BIG_LOTTO,
        LotteryType.DAILY_539,
        LotteryType.POWER_LOTTO,
    ):
        lottery_pairs = tuple(pair for pair in pairs if pair.lottery_type is lottery_type)
        targets = dataset.targets_by_lottery[lottery_type]
        snapshots = replay_frozen_pairs(
            lottery_type=lottery_type,
            targets=targets,
            pairs=lottery_pairs,
            database_sha256=dataset.database_sha256,
            reader_factory=lambda: SQLiteDrawHistoryReader(dataset.paths),
        )
        per_cell.extend(
            evaluate_pair(pair=pair, targets=targets, snapshots_by_strategy=snapshots)
            for pair in lottery_pairs
    )
    if len(per_cell) != 9:
        raise ValueError("PHASE12_CELL_COUNT_MISMATCH")
    database_sha256_after = sha256_file(dataset.paths.database)
    if database_sha256_after != dataset.database_sha256:
        raise ValueError(
            "DATABASE_IDENTITY_DRIFT: canonical database changed during Phase 12 replay"
        )

    return {
        "aggregate_interpretation": {
            "classification": AGGREGATE_INTERPRETATION,
            "decision_rule": None,
            "reason": (
                "The canonical evaluator is descriptive and defines no paired "
                "refinement-value decision rule; no Worker-invented threshold was applied."
            ),
        },
        "canonical_base": base_identity,
        "contract_authority": contract_authority,
        "dataset": {
            "access_mode": "READ_ONLY",
            "database_locator": "resolve_local_data_paths()",
            "database_path": str(dataset.paths.database),
            "database_sha256_after": database_sha256_after,
            "database_sha256_before": dataset.database_sha256,
            "partitions": {
                lottery_type.value: dataset.partition_metadata[lottery_type]
                for lottery_type in (
                    LotteryType.BIG_LOTTO,
                    LotteryType.DAILY_539,
                    LotteryType.POWER_LOTTO,
                )
            },
            "schema_migrations": list(dataset.schema_migrations),
        },
        "gate": {
            "all_nine_cells_evaluated": True,
            "database_identity_unchanged": True,
            "phase12_execution_gate": "PASS",
            "refinement_value_classification": AGGREGATE_INTERPRETATION,
        },
        "invariants": {
            "database_writes": "NONE",
            "decision_threshold_added": False,
            "history_policy": "MAXIMUM_1_MINIMUM_1_STRICTLY_PRIOR_DRAW",
            "metric_added": False,
            "monte_carlo": "NONE",
            "p638_zone2": "NOT_RUN",
            "reference_promotion": "NOT_AUTHORIZED",
            "rng": "NONE",
            "runtime_promotion": "NOT_AUTHORIZED",
            "second_or_higher_exchange": "NOT_RUN",
            "source_refresh": "NOT_RUN",
            "window_added": False,
        },
        "owner_authorization": OWNER_AUTHORIZATION,
        "pair_count": len(per_cell),
        "per_cell": per_cell,
        "replay_contract": {
            "causal_history_entrypoint": (
                "lottolab.application.use_cases.build_causal_history.BuildCausalHistory"
            ),
            "portfolio_replay_entrypoint": (
                "lottolab.application.use_cases.replay_historical_portfolio_predictions."
                "ReplayHistoricalPortfolioPredictions"
            ),
            "source_order": "draw_date ASC, CAST(draw_number AS INTEGER) ASC",
            "target_exclusion": "cutoff strictly precedes target by date and numeric draw",
            "typed_first_draw_closure": "INSUFFICIENT_HISTORY",
        },
        "reproduction_policy": {
            "canonical_json": "UTF-8, indent=2, sort_keys=True, LF terminal newline",
            "fresh_process_byte_identity_required": True,
            "non_deterministic_fields_in_payload": [],
            "performance_measurements_in_payload": False,
            "result_self_sha256_in_payload": False,
        },
        "study_id": STUDY_ID,
        "task_id": TASK_ID,
    }


def execute_phase12() -> dict[str, object]:
    base_identity = verify_current_base_identity()
    contract_authority = verify_contract_authority()
    pairs = load_frozen_pairs()
    paths = resolve_local_data_paths()
    database_sha256_before = sha256_file(paths.database)
    dataset = load_dataset_snapshot(paths, database_sha256_before)
    payload = build_result_payload(
        base_identity=base_identity,
        contract_authority=contract_authority,
        dataset=dataset,
        pairs=pairs,
    )
    # Recheck immediately before the only runtime write.
    final_database_sha256 = sha256_file(paths.database)
    if final_database_sha256 != database_sha256_before:
        raise ValueError(
            "DATABASE_IDENTITY_DRIFT: canonical database changed before result write"
        )
    OUTPUT_PATH.write_bytes(canonical_json_bytes(payload))
    result_sha256 = sha256_file(OUTPUT_PATH)
    print(f"Wrote deterministic result: {OUTPUT_PATH}", flush=True)
    print(f"RESULT_SHA256: {result_sha256}", flush=True)
    print(f"DATABASE_SHA256_BEFORE: {database_sha256_before}", flush=True)
    print(f"DATABASE_SHA256_AFTER: {final_database_sha256}", flush=True)
    print("PHASE12_EXECUTION_GATE: PASS", flush=True)
    print(f"AGGREGATE_INTERPRETATION: {AGGREGATE_INTERPRETATION}", flush=True)
    return payload


def main() -> None:
    execute_phase12()


if __name__ == "__main__":
    main()
