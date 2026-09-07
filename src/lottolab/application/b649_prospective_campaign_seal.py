"""Reusable BIG_LOTTO prospective campaign seal runner for ordinals 2..104.

This application module composes the existing generic prospective seal contracts
(RunnablePredictionSealService, FileSystemProspectiveObservationStore,
PreOutcomeTargetOperationalService, repository_game_contracts) around the frozen
campaign authority for TABU7_FIXED_K10_VS_10BET_PROSPECTIVE_104DRAW_R1.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final, Protocol, cast, runtime_checkable
from zoneinfo import ZoneInfo

from lottolab.application.future_draw_identity import ScheduledDrawOutcomeState
from lottolab.application.pre_outcome_target import OutcomeAlreadyAvailableError
from lottolab.application.pre_outcome_target_operational import (
    OperationalRegistrationResult,
    OperationalRegistrationStatus,
    PreOutcomeTargetOperationalService,
)
from lottolab.application.prospective_observer import (
    PredictionConflictError,
    PredictionProducer,
    ProspectiveObservationStore,
    big_lotto_game_contract,
)
from lottolab.application.prospective_prediction_seal import (
    PredictionSealCausalityError,
    RunnablePredictionSealService,
    RunnablePredictionSealStatus,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.pre_outcome_target import TargetAnnouncement
from lottolab.domain.prospective_observer import (
    FrozenCohortRef,
    MatchedBaselineRef,
    PredictionContext,
    PredictionDraft,
    PredictionEntryDraft,
    ProducerDependency,
    ProducerFingerprint,
    ProspectiveSelection,
    TemporalProvenance,
)
from lottolab.strategies.adapters.base import CausalDrawRow
from lottolab.strategies.adapters.biglotto_wave6 import BigLottoTenBetBacktestAdapter

_TAIPEI_TZ: Final = ZoneInfo("Asia/Taipei")
_SHA256_RE: Final = re.compile(r"[0-9a-f]{64}", flags=re.ASCII)

EXPECTED_CAMPAIGN_SPEC_SHA256: Final = (
    "6d85c93ba7171628a21d28a96a63a6ceedb79287864f507e8ff65670b9bd0a68"
)
EXPECTED_CAMPAIGN_ID: Final = "TABU7_FIXED_K10_VS_10BET_PROSPECTIVE_104DRAW_R1"
EXPECTED_FROZEN_RESEARCH_SOURCE_HEAD: Final = (
    "0c60866e4d70f07126dba4eea30a7489934496b9"
)
EXPECTED_ORDINAL_1_SEAL_SHA256: Final = (
    "8edc33ac0a95c5df101e1e206b0786f3e041912a672e64fa6a5197c29ee36247"
)
EXPECTED_START_TARGET_DRAW: Final = "115000086"
EXPECTED_TARGET_DRAW_COUNT: Final = 104
EXPECTED_CANDIDATE_ID: Final = "TABU7_FIXED_K10_BRIDGE_R1"
EXPECTED_CANDIDATE_SHIFT: Final = "SHIFT_0"
EXPECTED_BASELINE_METHOD: Final = "10bet"
EXPECTED_BASELINE_STRATEGY_ID: Final = (
    "legacy_biglotto__backtest_10bet_biglotto__054e85b088be"
)
EXPECTED_BASELINE_ADAPTER_IDENTITY: Final = (
    "lottolab.strategies.adapters.biglotto_wave6.BigLottoTenBetBacktestAdapter"
)
EXPECTED_PRIMARY_METRIC: Final = "M3_PLUS v1"
EXPECTED_BASELINE_ADAPTER_SOURCE_SHA256: Final = (
    "ef805d78d480758bd6104f5bab7219c38b8d85b11257e79c45cbbd16fe4007db"
)

MIN_CAMPAIGN_ORDINAL: Final = 2
MAX_CAMPAIGN_ORDINAL: Final = 104


class CampaignSealRunnerError(RuntimeError):
    """Base class for all campaign seal runner errors."""


class CampaignSpecAuthorityError(CampaignSealRunnerError):
    """Campaign spec is missing, malformed, or invalid."""


class CampaignSpecShaMismatchError(CampaignSpecAuthorityError):
    """Campaign spec bytes do not match the expected SHA-256."""


class CampaignIdMismatchError(CampaignSpecAuthorityError):
    """Campaign ID does not match expected campaign authority."""


class CampaignOrdinalRangeError(CampaignSealRunnerError):
    """Requested campaign ordinal is outside the supported 2..104 range."""


class CampaignSequenceError(CampaignSealRunnerError):
    """Campaign draw sequence or preceding seal continuity is violated."""


class CampaignTargetMismatchError(CampaignSealRunnerError):
    """Supplied target does not match the canonical target authority."""


class CampaignBaselineDriftError(CampaignSealRunnerError):
    """Baseline adapter implementation has drifted from frozen semantics."""


class CampaignPreOutcomeGateError(CampaignSealRunnerError):
    """Target fails pre-outcome checks (e.g. outcome already available or late)."""


@runtime_checkable
class B649PersistencePort(Protocol):
    """Port interface decoupling campaign seal application logic from persistence infrastructure."""

    @property
    def history_authority_locator(self) -> str:
        """Return the locator string for the causal history database/store."""
        ...

    def is_outcome_present(
        self,
        lottery_type: LotteryType,
        draw_number: str,
    ) -> bool:
        """Return True if draw outcome is already present in persistent storage."""
        ...

    def query_causal_history_rows(
        self,
        lottery_type: LotteryType,
        history_cutoff_draw: str,
    ) -> tuple[CausalDrawRow, ...]:
        """Query causal draw rows up to history_cutoff_draw without database writes."""
        ...

    def verify_read_only_integrity(self) -> bool:
        """Verify that the database/schema remains in a read-only valid state."""
        ...


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def _canonical_json_dumps(payload: object) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _format_asia_taipei(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    taipei_dt = dt.astimezone(_TAIPEI_TZ)
    return taipei_dt.isoformat()


def _as_dict(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise CampaignSpecAuthorityError(f"{label} must be a JSON object")
    return cast(dict[str, object], value)


def _as_str(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise CampaignSpecAuthorityError(f"{label} must be a non-empty string")
    return value


def _as_int(value: object, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise CampaignSpecAuthorityError(f"{label} must be an integer")
    return value


@dataclass(frozen=True, slots=True)
class CampaignSpec:
    campaign_id: str
    frozen_source_head: str
    start_target_draw: str
    target_draw_count: int
    candidate_id: str
    candidate_shift: str
    candidate_portfolio: tuple[tuple[int, ...], ...]
    baseline_method: str
    baseline_strategy_id: str
    baseline_adapter_identity: str
    baseline_source_authority: str
    baseline_k_ticket: int
    primary_metric: str
    ordinal_1_target_draw: str
    ordinal_1_history_cutoff_draw: str
    ordinal_1_seal_locator: str
    ordinal_1_seal_sha256: str
    draw_seals_directory: Path
    created_at_iso: str
    raw_spec_sha256: str


def load_and_validate_campaign_spec(
    spec_path: Path,
    *,
    expected_sha256: str = EXPECTED_CAMPAIGN_SPEC_SHA256,
) -> CampaignSpec:
    """Load and validate the frozen campaign specification artifact."""
    if not spec_path.is_file():
        raise CampaignSpecAuthorityError(f"campaign spec file not found at {spec_path}")

    raw_bytes = spec_path.read_bytes()
    computed_sha256 = _sha256_bytes(raw_bytes)
    if computed_sha256 != expected_sha256:
        raise CampaignSpecShaMismatchError(
            f"campaign spec SHA-256 mismatch: expected {expected_sha256}, got {computed_sha256}"
        )

    try:
        raw_obj = json.loads(raw_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CampaignSpecAuthorityError("campaign spec is not valid JSON") from exc

    data = _as_dict(raw_obj, "campaign spec root")

    campaign_id = _as_str(data.get("campaign_id"), "campaign_id")
    if campaign_id != EXPECTED_CAMPAIGN_ID:
        raise CampaignIdMismatchError(
            f"campaign_id mismatch: expected {EXPECTED_CAMPAIGN_ID!r}, got {campaign_id!r}"
        )

    frozen_head = _as_str(data.get("frozen_source_head"), "frozen_source_head")
    if frozen_head != EXPECTED_FROZEN_RESEARCH_SOURCE_HEAD:
        raise CampaignSpecAuthorityError(
            f"frozen_source_head mismatch: expected {EXPECTED_FROZEN_RESEARCH_SOURCE_HEAD!r}, "
            f"got {frozen_head!r}"
        )

    start_target = _as_str(data.get("start_target_draw"), "start_target_draw")
    if start_target != EXPECTED_START_TARGET_DRAW:
        raise CampaignSpecAuthorityError(
            f"start_target_draw mismatch: expected {EXPECTED_START_TARGET_DRAW!r}, "
            f"got {start_target!r}"
        )

    target_count = _as_int(data.get("target_draw_count"), "target_draw_count")
    if target_count != EXPECTED_TARGET_DRAW_COUNT:
        raise CampaignSpecAuthorityError(
            f"target_draw_count mismatch: expected {EXPECTED_TARGET_DRAW_COUNT}, got {target_count}"
        )

    candidate = _as_dict(data.get("candidate"), "candidate")
    candidate_id = _as_str(candidate.get("candidate_id"), "candidate.candidate_id")
    if candidate_id != EXPECTED_CANDIDATE_ID:
        raise CampaignSpecAuthorityError(
            f"candidate_id mismatch: expected {EXPECTED_CANDIDATE_ID!r}, got {candidate_id!r}"
        )

    shift = _as_str(candidate.get("shift"), "candidate.shift")
    if shift != EXPECTED_CANDIDATE_SHIFT:
        raise CampaignSpecAuthorityError(
            f"candidate shift mismatch: expected {EXPECTED_CANDIDATE_SHIFT!r}, got {shift!r}"
        )

    raw_portfolio_obj = candidate.get("portfolio")
    if not isinstance(raw_portfolio_obj, list):
        raise CampaignSpecAuthorityError("candidate portfolio must contain exactly 10 tickets")
    raw_portfolio = cast(list[object], raw_portfolio_obj)
    if len(raw_portfolio) != 10:
        raise CampaignSpecAuthorityError("candidate portfolio must contain exactly 10 tickets")

    validated_candidate_portfolio: list[tuple[int, ...]] = []
    for idx, t_obj in enumerate(raw_portfolio):
        if not isinstance(t_obj, list):
            raise CampaignSpecAuthorityError(
                f"candidate ticket {idx} must contain exactly 6 numbers"
            )
        t = cast(list[object], t_obj)
        if len(t) != 6:
            raise CampaignSpecAuthorityError(
                f"candidate ticket {idx} must contain exactly 6 numbers"
            )
        ticket_nums = tuple(int(cast(int, x)) for x in t)
        if any(x < 1 or x > 49 for x in ticket_nums):
            raise CampaignSpecAuthorityError(
                f"candidate ticket {idx} contains out-of-range numbers"
            )
        if len(set(ticket_nums)) != 6:
            raise CampaignSpecAuthorityError(f"candidate ticket {idx} contains duplicates")
        if ticket_nums != tuple(sorted(ticket_nums)):
            raise CampaignSpecAuthorityError(f"candidate ticket {idx} must be sorted ascending")
        validated_candidate_portfolio.append(ticket_nums)

    baseline = _as_dict(data.get("baseline"), "baseline")
    baseline_method = _as_str(baseline.get("method"), "baseline.method")
    if baseline_method != EXPECTED_BASELINE_METHOD:
        raise CampaignSpecAuthorityError(
            f"baseline method mismatch: expected {EXPECTED_BASELINE_METHOD!r}, "
            f"got {baseline_method!r}"
        )

    baseline_strategy_id = _as_str(baseline.get("strategy_id"), "baseline.strategy_id")
    if baseline_strategy_id != EXPECTED_BASELINE_STRATEGY_ID:
        raise CampaignSpecAuthorityError(
            f"baseline strategy_id mismatch: expected {EXPECTED_BASELINE_STRATEGY_ID!r}, "
            f"got {baseline_strategy_id!r}"
        )

    baseline_adapter_identity = _as_str(
        baseline.get("adapter_identity"), "baseline.adapter_identity"
    )
    if baseline_adapter_identity != EXPECTED_BASELINE_ADAPTER_IDENTITY:
        raise CampaignSpecAuthorityError(
            f"baseline adapter_identity mismatch: expected {EXPECTED_BASELINE_ADAPTER_IDENTITY!r}, "
            f"got {baseline_adapter_identity!r}"
        )

    baseline_source_auth = _as_str(
        baseline.get("source_authority"), "baseline.source_authority"
    )
    if baseline_source_auth != EXPECTED_FROZEN_RESEARCH_SOURCE_HEAD:
        raise CampaignSpecAuthorityError(
            f"baseline source_authority mismatch: "
            f"expected {EXPECTED_FROZEN_RESEARCH_SOURCE_HEAD!r}, "
            f"got {baseline_source_auth!r}"
        )

    baseline_k = _as_int(baseline.get("k_ticket"), "baseline.k_ticket")
    if baseline_k != 10:
        raise CampaignSpecAuthorityError(
            f"baseline k_ticket mismatch: expected 10, got {baseline_k}"
        )

    primary_endpoint = _as_dict(data.get("primary_endpoint"), "primary_endpoint")
    primary_metric = _as_str(primary_endpoint.get("metric"), "primary_endpoint.metric")
    if primary_metric != EXPECTED_PRIMARY_METRIC:
        raise CampaignSpecAuthorityError(
            f"primary metric mismatch: expected {EXPECTED_PRIMARY_METRIC!r}, got {primary_metric!r}"
        )

    ordinal_1 = _as_dict(data.get("ordinal_1"), "ordinal_1")
    ord1_target = _as_str(ordinal_1.get("target_draw"), "ordinal_1.target_draw")
    ord1_history_cutoff = _as_str(
        ordinal_1.get("history_cutoff_draw"), "ordinal_1.history_cutoff_draw"
    )
    ord1_locator = _as_str(ordinal_1.get("seal_locator"), "ordinal_1.seal_locator")
    ord1_sha = _as_str(ordinal_1.get("seal_sha256"), "ordinal_1.seal_sha256")
    if (
        ord1_target != "115000086"
        or ord1_history_cutoff != "115000085"
        or _SHA256_RE.fullmatch(ord1_sha) is None
    ):
        raise CampaignSpecAuthorityError("ordinal_1 configuration is invalid or tampered")
    if (
        expected_sha256 == EXPECTED_CAMPAIGN_SPEC_SHA256
        and ord1_sha != EXPECTED_ORDINAL_1_SEAL_SHA256
    ):
        raise CampaignSpecAuthorityError("ordinal_1 configuration is invalid or tampered")

    path_conventions = _as_dict(data.get("path_conventions"), "path_conventions")
    raw_draw_seals_dir = _as_str(
        path_conventions.get("draw_seals_directory"),
        "path_conventions.draw_seals_directory",
    )

    created_at_iso = _as_str(data.get("created_at"), "created_at")

    return CampaignSpec(
        campaign_id=campaign_id,
        frozen_source_head=frozen_head,
        start_target_draw=start_target,
        target_draw_count=target_count,
        candidate_id=candidate_id,
        candidate_shift=shift,
        candidate_portfolio=tuple(validated_candidate_portfolio),
        baseline_method=baseline_method,
        baseline_strategy_id=baseline_strategy_id,
        baseline_adapter_identity=baseline_adapter_identity,
        baseline_source_authority=baseline_source_auth,
        baseline_k_ticket=baseline_k,
        primary_metric=primary_metric,
        ordinal_1_target_draw=ord1_target,
        ordinal_1_history_cutoff_draw=ord1_history_cutoff,
        ordinal_1_seal_locator=ord1_locator,
        ordinal_1_seal_sha256=ord1_sha,
        draw_seals_directory=Path(raw_draw_seals_dir),
        created_at_iso=created_at_iso,
        raw_spec_sha256=computed_sha256,
    )


def verify_baseline_adapter_frozen_semantics(
    repo_root: Path | None = None,
) -> None:
    """Verify that BigLottoTenBetBacktestAdapter matches frozen source authority."""
    adapter = BigLottoTenBetBacktestAdapter()
    if adapter.strategy_id != EXPECTED_BASELINE_STRATEGY_ID:
        raise CampaignBaselineDriftError(
            f"adapter strategy_id drifted: expected {EXPECTED_BASELINE_STRATEGY_ID!r}, "
            f"got {adapter.strategy_id!r}"
        )
    if adapter.native_ticket_count != 10:
        raise CampaignBaselineDriftError(
            f"adapter ticket count drifted: expected 10, got {adapter.native_ticket_count}"
        )
    if adapter.supported_lottery_types != (LotteryType.BIG_LOTTO,):
        raise CampaignBaselineDriftError("adapter supported lottery types drifted")

    if repo_root is not None:
        adapter_source = (
            repo_root / "src/lottolab/strategies/adapters/biglotto_wave6.py"
        )
        if adapter_source.is_file():
            source_sha = _sha256_file(adapter_source)
            if source_sha != EXPECTED_BASELINE_ADAPTER_SOURCE_SHA256:
                raise CampaignBaselineDriftError(
                    f"adapter source file drifted: expected SHA-256 "
                    f"{EXPECTED_BASELINE_ADAPTER_SOURCE_SHA256}, got {source_sha}"
                )


@dataclass(frozen=True, slots=True)
class B649CampaignSealResult:
    status: RunnablePredictionSealStatus
    campaign_id: str
    campaign_ordinal: int
    target_draw: str
    history_cutoff_draw: str
    seal_path: Path
    seal_sha256: str
    canonical_prediction_record_sha256: str
    wrapper_payload: dict[str, object]


class _B649CampaignProducer:
    def __init__(
        self,
        *,
        candidate_id: str,
        candidate_selections: tuple[ProspectiveSelection, ...],
        baseline_strategy_id: str,
        baseline_version: str,
        baseline_authority_sha256: str,
        draft_id: str,
    ) -> None:
        self.candidate_id = candidate_id
        self.candidate_selections = candidate_selections
        self.baseline_strategy_id = baseline_strategy_id
        self.baseline_version = baseline_version
        self.baseline_authority_sha256 = baseline_authority_sha256
        self.draft_id = draft_id

    def predict(self, context: PredictionContext) -> PredictionDraft:
        matched_baseline = MatchedBaselineRef(
            lottery_type=LotteryType.BIG_LOTTO,
            baseline_id=self.baseline_strategy_id,
            baseline_version=self.baseline_version,
            authority_sha256=self.baseline_authority_sha256,
            ticket_count=len(self.candidate_selections),
            candidate_sizes=tuple(
                len(sel.main_numbers) for sel in self.candidate_selections
            ),
        )
        entry = PredictionEntryDraft.available(
            member_id=self.candidate_id,
            selections=self.candidate_selections,
            matched_baseline=matched_baseline,
        )
        return PredictionDraft((entry,))


class _B649RegistrationAdapter:
    """Thin adapter binding B649 schedule authority digest to RunnablePredictionSealService."""

    def __init__(
        self,
        service: PreOutcomeTargetOperationalService,
        fallback_schedule_hash: str,
    ) -> None:
        self._service = service
        self._fallback_schedule_hash = fallback_schedule_hash

    def register_earliest(
        self,
        lottery_type: LotteryType,
    ) -> OperationalRegistrationResult:
        res = self._service.register_earliest(lottery_type)
        if res.announcement is None or res.status not in {
            OperationalRegistrationStatus.CREATED,
            OperationalRegistrationStatus.EXACT_IDEMPOTENT_NO_OP,
        }:
            return res
        if res.immutable_schedule_sha256 is not None:
            return res
        return OperationalRegistrationResult(
            status=res.status,
            announcement=res.announcement,
            causal_history=res.causal_history,
            registration=res.registration,
            immutable_schedule_sha256=self._fallback_schedule_hash,
        )


def _load_ordinal_seal(seal_path: Path) -> dict[str, object]:
    if not seal_path.is_file():
        raise CampaignSequenceError(f"seal file not found at {seal_path}")
    try:
        raw: object = json.loads(seal_path.read_text(encoding="utf-8"))
        return _as_dict(raw, f"seal at {seal_path}")
    except Exception as exc:
        raise CampaignSequenceError(f"failed to read seal at {seal_path}: {exc}") from exc


def _find_seal_for_ordinal(
    draw_seals_dir: Path,
    spec: CampaignSpec,
    ordinal: int,
    base_dir: Path,
) -> tuple[Path, dict[str, object]]:
    """Find the seal file for a specific campaign ordinal."""
    if ordinal == 1:
        ord1_path = Path(spec.ordinal_1_seal_locator)
        if not ord1_path.is_absolute():
            ord1_path = (base_dir / ord1_path).resolve()
        if not ord1_path.is_file():
            raise CampaignSequenceError(
                f"ordinal 1 seal not found at locator {ord1_path}"
            )
        sha = _sha256_file(ord1_path)
        if sha != spec.ordinal_1_seal_sha256:
            raise CampaignSequenceError(
                f"ordinal 1 seal SHA mismatch: expected {spec.ordinal_1_seal_sha256}, got {sha}"
            )
        return ord1_path, _load_ordinal_seal(ord1_path)

    if not draw_seals_dir.is_dir():
        raise CampaignSequenceError(
            f"draw seals directory does not exist: {draw_seals_dir}"
        )

    for item in sorted(draw_seals_dir.glob("*.json")):
        if item.name == "prediction.json":
            continue
        try:
            raw_content: object = json.loads(item.read_text(encoding="utf-8"))
            if isinstance(raw_content, dict):
                seal_dict = cast(dict[str, object], raw_content)
                if seal_dict.get("campaign_ordinal") == ordinal:
                    return item, seal_dict
        except Exception:
            continue

    raise CampaignSequenceError(
        f"preceding campaign ordinal {ordinal} has not been sealed"
    )


def _atomic_write_wrapper_seal(target_path: Path, content: str) -> None:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path_str = tempfile.mkstemp(
        prefix="seal_tmp_",
        suffix=".json",
        dir=target_path.parent,
    )
    tmp_path = Path(tmp_path_str)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        tmp_path.replace(target_path)
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink()
        raise


def execute_b649_prospective_campaign_seal(
    *,
    campaign_id: str,
    campaign_ordinal: int,
    target_draw: str,
    campaign_spec_path: Path,
    draw_seals_dir: Path,
    repo_root: Path,
    registration_service: PreOutcomeTargetOperationalService,
    observation_store: ProspectiveObservationStore,
    persistence_port: B649PersistencePort,
    clock: Callable[[], datetime] | None = None,
    expected_campaign_spec_sha256: str = EXPECTED_CAMPAIGN_SPEC_SHA256,
) -> B649CampaignSealResult:
    """Execute one prospective prediction seal for campaign ordinals 2..104.

    Fails closed on:
    - campaign spec SHA mismatch or ID mismatch;
    - campaign ordinal < 2 or > 104;
    - ordinal 1 attempted rewrite;
    - target draw sequence or ordinal mismatch;
    - preceding official draw incomplete;
    - target outcome already available;
    - late execution (current time >= target scheduled_at);
    - baseline adapter or source authority drift;
    - conflicting content on rerun.
    """
    selected_clock = (lambda: datetime.now(UTC)) if clock is None else clock
    cycle_started_at = selected_clock()
    if cycle_started_at.tzinfo is not UTC:
        raise PredictionSealCausalityError("clock must return a timezone-aware UTC datetime")

    # 1. Load and validate campaign spec
    spec = load_and_validate_campaign_spec(
        campaign_spec_path,
        expected_sha256=expected_campaign_spec_sha256,
    )
    if campaign_id != spec.campaign_id:
        raise CampaignIdMismatchError(
            f"supplied campaign_id {campaign_id!r} does not match spec {spec.campaign_id!r}"
        )

    # 2. Validate ordinal range
    if campaign_ordinal == 1:
        raise CampaignOrdinalRangeError(
            "ordinal 1 is sealed externally and cannot be rewritten by this runner"
        )
    if (
        campaign_ordinal < MIN_CAMPAIGN_ORDINAL
        or campaign_ordinal > MAX_CAMPAIGN_ORDINAL
    ):
        raise CampaignOrdinalRangeError(
            f"campaign_ordinal must be in range [{MIN_CAMPAIGN_ORDINAL}..{MAX_CAMPAIGN_ORDINAL}], "
            f"got {campaign_ordinal}"
        )

    resolved_repo_root = repo_root.resolve()
    resolved_draw_seals_dir = draw_seals_dir.resolve()

    # 3. Verify baseline adapter frozen semantics
    verify_baseline_adapter_frozen_semantics(resolved_repo_root)

    # 4. Resolve preceding campaign ordinal authority
    prev_ordinal = campaign_ordinal - 1
    _prev_seal_path, prev_seal = _find_seal_for_ordinal(
        resolved_draw_seals_dir,
        spec,
        prev_ordinal,
        resolved_repo_root,
    )
    expected_prev_target = str(prev_seal["target_draw"])

    # 5. Check target in schedule authority
    reader = registration_service.future_draw_identity_reader
    scheduled_record = reader.get_scheduled_draw(LotteryType.BIG_LOTTO, target_draw)
    if scheduled_record is None:
        raise CampaignTargetMismatchError(
            f"target draw {target_draw} not found in canonical schedule authority"
        )
    if scheduled_record.outcome_state is not ScheduledDrawOutcomeState.NOT_POPULATED:
        raise OutcomeAlreadyAvailableError(
            f"target draw {target_draw} outcome is already populated in schedule authority"
        )

    announcement = scheduled_record.announcement
    # Strict causality gate
    if cycle_started_at >= announcement.scheduled_at:
        raise PredictionSealCausalityError(
            f"prediction execution began at {cycle_started_at.isoformat()}, "
            f"which is not strictly before scheduled_at {announcement.scheduled_at.isoformat()}"
        )

    # 6. Check outcome presence in persistence
    if persistence_port.is_outcome_present(LotteryType.BIG_LOTTO, target_draw):
        raise OutcomeAlreadyAvailableError(
            f"target draw {target_draw} outcome is already present in draws table"
        )

    # 7. Resolve causal history and verify predecessor continuity
    causal_history_authority = registration_service.causal_history_authority
    causal_history = causal_history_authority.resolve(announcement.target)
    causal_history.validate_against(announcement.target)

    if causal_history.last_draw_number is None:
        raise CampaignSequenceError(
            f"causal history contains no draws for target {target_draw}"
        )

    if causal_history.last_draw_number != expected_prev_target:
        raise CampaignSequenceError(
            f"causal history ends at draw {causal_history.last_draw_number}, but campaign ordinal "
            f"{campaign_ordinal} requires preceding draw {expected_prev_target}"
        )

    # 8. Query causal draw rows and generate baseline tickets
    history_rows = persistence_port.query_causal_history_rows(
        LotteryType.BIG_LOTTO,
        causal_history.last_draw_number,
    )
    if len(history_rows) != causal_history.draw_count:
        raise CampaignSequenceError(
            f"history row count mismatch: persistence has {len(history_rows)}, "
            f"causal_history declares {causal_history.draw_count}"
        )

    adapter = BigLottoTenBetBacktestAdapter()
    baseline_tickets_raw = adapter.get_bets(history_rows, LotteryType.BIG_LOTTO)
    if len(baseline_tickets_raw) != 10:
        raise CampaignBaselineDriftError(
            f"baseline adapter produced {len(baseline_tickets_raw)} tickets instead of 10"
        )
    baseline_tickets = tuple(tuple(int(x) for x in t) for t in baseline_tickets_raw)

    baseline_authority_sha256 = hashlib.sha256(
        _canonical_json_dumps([list(t) for t in baseline_tickets]).encode("utf-8")
    ).hexdigest()

    # 9. Prepare candidate selections (static SHIFT_0 from spec)
    candidate_selections = tuple(
        ProspectiveSelection(ticket) for ticket in spec.candidate_portfolio
    )

    # 10. Compose and invoke generic prospective seal service
    cohort = FrozenCohortRef(
        lottery_type=LotteryType.BIG_LOTTO,
        cohort_id=spec.campaign_id,
        cohort_version="v1",
        authority_sha256=spec.raw_spec_sha256,
        frozen_at=datetime.fromisoformat(spec.created_at_iso).astimezone(UTC),
        member_ids=(spec.candidate_id,),
        checkpoint_sizes=(EXPECTED_TARGET_DRAW_COUNT,),
        checkpoint_provenance=(TemporalProvenance.POST_FREEZE_DATE_PROSPECTIVE,),
    )
    base_fingerprint = ProducerFingerprint.create(
        producer_id=spec.candidate_id,
        producer_version="v1",
        dependencies=(
            ProducerDependency(
                locator="campaign://spec",
                source_sha256=spec.raw_spec_sha256,
                load_bearing_role="frozen campaign authority",
            ),
            ProducerDependency(
                locator="adapter://biglotto_wave6/BigLottoTenBetBacktestAdapter",
                source_sha256=EXPECTED_BASELINE_ADAPTER_SOURCE_SHA256,
                load_bearing_role="frozen 10bet baseline adapter",
            ),
        ),
    )

    draft_id = f"{spec.campaign_id}-ord{campaign_ordinal:03d}-{target_draw}"
    producer = _B649CampaignProducer(
        candidate_id=spec.candidate_id,
        candidate_selections=candidate_selections,
        baseline_strategy_id=spec.baseline_strategy_id,
        baseline_version=adapter.strategy_version,
        baseline_authority_sha256=baseline_authority_sha256,
        draft_id=draft_id,
    )

    def producer_factory(
        announcement: TargetAnnouncement,
        reference_time: datetime,
    ) -> PredictionProducer:
        return producer

    registration_adapter = _B649RegistrationAdapter(
        registration_service,
        scheduled_record.normalized_announcement_hash,
    )
    seal_service = RunnablePredictionSealService(
        lottery_type=LotteryType.BIG_LOTTO,
        registration_service=registration_adapter,
        store=observation_store,
        producer_factory=producer_factory,
        cohort=cohort,
        base_producer_fingerprint=base_fingerprint,
        game_contracts={LotteryType.BIG_LOTTO: big_lotto_game_contract()},
        clock=selected_clock,
    )

    seal_result = seal_service.seal_earliest()
    if seal_result.prediction is None:
        raise CampaignSealRunnerError(
            f"seal service returned no prediction (status={seal_result.status})"
        )
    if seal_result.registration is None:
        raise CampaignSealRunnerError("seal service returned no target registration")
    if seal_result.registration.target.draw_number != target_draw:
        raise CampaignTargetMismatchError(
            f"earliest registered target draw {seal_result.registration.target.draw_number} "
            f"does not match requested target draw {target_draw}"
        )

    # 11. Build and persist campaign per-draw seal wrapper
    wrapper_dict: dict[str, object] = {
        "baseline_adapter_identity": spec.baseline_adapter_identity,
        "baseline_method": spec.baseline_method,
        "baseline_portfolio": [list(t) for t in baseline_tickets],
        "baseline_strategy_id": spec.baseline_strategy_id,
        "campaign_id": spec.campaign_id,
        "campaign_ordinal": campaign_ordinal,
        "candidate_id": spec.candidate_id,
        "candidate_portfolio": [list(t) for t in spec.candidate_portfolio],
        "database_writes": "none",
        "frozen_source_head": spec.frozen_source_head,
        "history_authority_identity": (
            f"causal_history_sha256:{causal_history.history_sha256};"
            f"last_draw:{causal_history.last_draw_number};"
            f"count:{causal_history.draw_count}"
        ),
        "history_authority_locator": persistence_port.history_authority_locator,
        "history_cutoff_draw": causal_history.last_draw_number,
        "seal_created_at_asia_taipei": _format_asia_taipei(cycle_started_at),
        "target_draw": target_draw,
        "target_outcome_read": False,
    }

    wrapper_file_path = (
        resolved_draw_seals_dir / f"draw_{target_draw}_prediction_seal.json"
    )

    final_status = seal_result.status

    if wrapper_file_path.is_file():
        existing_bytes = wrapper_file_path.read_bytes()
        try:
            raw_existing = json.loads(existing_bytes.decode("utf-8"))
            existing_data = _as_dict(raw_existing, "existing seal")
        except Exception as exc:
            raise PredictionConflictError(
                f"existing seal file at {wrapper_file_path} is corrupt"
            ) from exc

        # Check content match (ignoring seal_created_at_asia_taipei for idempotent rerun)
        mismatched_keys: list[str] = []
        for key in (
            "campaign_id",
            "campaign_ordinal",
            "target_draw",
            "history_cutoff_draw",
            "frozen_source_head",
            "candidate_id",
            "candidate_portfolio",
            "baseline_method",
            "baseline_strategy_id",
            "baseline_adapter_identity",
            "baseline_portfolio",
            "target_outcome_read",
            "database_writes",
        ):
            if existing_data.get(key) != wrapper_dict.get(key):
                mismatched_keys.append(key)

        if mismatched_keys:
            raise PredictionConflictError(
                f"existing seal file at {wrapper_file_path} conflicts on fields: {mismatched_keys}"
            )

        final_status = RunnablePredictionSealStatus.EXACT_IDEMPOTENT_NO_OP
        final_sha256 = _sha256_bytes(existing_bytes)
        final_payload = existing_data
    else:
        content_str = _canonical_json_dumps(wrapper_dict) + "\n"
        _atomic_write_wrapper_seal(wrapper_file_path, content_str)
        final_status = RunnablePredictionSealStatus.CREATED
        final_sha256 = _sha256_bytes(content_str.encode("utf-8"))
        final_payload = wrapper_dict

    # 12. Verify read-only data integrity
    if not persistence_port.verify_read_only_integrity():
        raise CampaignSealRunnerError("database schema is not in read-only valid state")

    return B649CampaignSealResult(
        status=final_status,
        campaign_id=spec.campaign_id,
        campaign_ordinal=campaign_ordinal,
        target_draw=target_draw,
        history_cutoff_draw=causal_history.last_draw_number,
        seal_path=wrapper_file_path,
        seal_sha256=final_sha256,
        canonical_prediction_record_sha256=seal_result.prediction.prediction_hash,
        wrapper_payload=final_payload,
    )


__all__ = [
    "EXPECTED_BASELINE_ADAPTER_IDENTITY",
    "EXPECTED_BASELINE_ADAPTER_SOURCE_SHA256",
    "EXPECTED_BASELINE_METHOD",
    "EXPECTED_BASELINE_STRATEGY_ID",
    "EXPECTED_CAMPAIGN_ID",
    "EXPECTED_CAMPAIGN_SPEC_SHA256",
    "EXPECTED_CANDIDATE_ID",
    "EXPECTED_CANDIDATE_SHIFT",
    "EXPECTED_FROZEN_RESEARCH_SOURCE_HEAD",
    "EXPECTED_ORDINAL_1_SEAL_SHA256",
    "EXPECTED_PRIMARY_METRIC",
    "EXPECTED_START_TARGET_DRAW",
    "EXPECTED_TARGET_DRAW_COUNT",
    "MAX_CAMPAIGN_ORDINAL",
    "MIN_CAMPAIGN_ORDINAL",
    "B649CampaignSealResult",
    "B649PersistencePort",
    "CampaignBaselineDriftError",
    "CampaignIdMismatchError",
    "CampaignOrdinalRangeError",
    "CampaignPreOutcomeGateError",
    "CampaignSealRunnerError",
    "CampaignSequenceError",
    "CampaignSpec",
    "CampaignSpecAuthorityError",
    "CampaignSpecShaMismatchError",
    "CampaignTargetMismatchError",
    "execute_b649_prospective_campaign_seal",
    "load_and_validate_campaign_spec",
    "verify_baseline_adapter_frozen_semantics",
]
