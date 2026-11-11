"""Five-policy research cohort composition over the pre-outcome guard.

The caller must supply authenticated schedule, history, presence and clock
authorities. A filesystem prediction is create-once, but its local timestamp
is not independent proof of pre-draw existence; external timestamping must be
verified separately before calling it a prospective seal.
"""

from __future__ import annotations

import hashlib
import json
import math
import platform
import ssl
import sys
import sysconfig
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from lottolab.application.k3_predraw_guard import (
    GREEDY_K3,
    K3HistoryRow,
    K3Policy,
    generate_guarded_k3,
)
from lottolab.application.prospective_observer import (
    PredictionPhaseService,
    PredictionSyncResult,
    ProspectiveObservationStore,
    repository_game_contracts,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.pre_outcome_target import (
    OutcomePresenceAttestation,
    PreOutcomeTargetRegistration,
)
from lottolab.domain.prospective_observer import (
    FrozenCohortRef,
    MatchedBaselineRef,
    OutcomePresenceAtPrediction,
    PredictionContext,
    PredictionDraft,
    PredictionEntryDraft,
    PredictionPhaseRequest,
    ProducerDependency,
    ProducerFingerprint,
    ProspectiveSelection,
    TemporalProvenance,
)

COHORT_ID = "k3-primary797-four-policies-and-greedy"
COHORT_VERSION = "research-cohort-v1"
MEMBERS = (
    K3Policy.EXHAUSTIVE.value,
    K3Policy.ANALYZE_CANDIDATE.value,
    K3Policy.BACKTEST_STRATEGY_1.value,
    K3Policy.OPTIMIZED_ENSEMBLE.value,
    "GREEDY",
)
MANIFEST_SCHEMA = "K3_PROSPECTIVE_CODE_ENVIRONMENT_V1"


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def capture_version_manifest(repo: Path) -> dict[str, object]:
    """Capture the full application source tree and runtime for fail-closed drift checks."""
    root = repo.resolve(strict=True)
    source_root = root / "src" / "lottolab"
    if not source_root.is_dir() or not (root / "pyproject.toml").is_file():
        raise ValueError("repo must identify the project checkout")
    files = sorted(path for path in source_root.rglob("*.py") if path.is_file())
    files.append(root / "pyproject.toml")
    if (root / "uv.lock").is_file():
        files.append(root / "uv.lock")
    modules = {path.relative_to(root).as_posix(): _hash(path.read_bytes()) for path in files}
    if not modules or sys.version_info[:2] != (3, 13):
        raise ValueError("complete project sources and Python 3.13 are required")
    executable = Path(sys.executable).resolve(strict=True)
    math_module = Path(math.__file__).resolve(strict=True)
    return {
        "schema_version": MANIFEST_SCHEMA,
        "cohort_id": COHORT_ID,
        "cohort_version": COHORT_VERSION,
        "members": list(MEMBERS),
        "policy": "native-prefix-k3-greedy-supplement; analyze-prefix3-dedup-first",
        "greedy": [list(ticket) for ticket in GREEDY_K3],
        "source_files_sha256": modules,
        "runtime": {
            "python": platform.python_version(),
            "implementation": platform.python_implementation(),
            "soabi": sysconfig.get_config_var("SOABI"),
            "platform": platform.platform(),
            "executable_sha256": _hash(executable.read_bytes()),
            "math_extension_sha256": _hash(math_module.read_bytes()),
            "openssl": ssl.OPENSSL_VERSION,
        },
    }


def version_fingerprint(manifest: dict[str, object]) -> ProducerFingerprint:
    """Bind the entire manifest as a producer dependency."""
    if manifest.get("schema_version") != MANIFEST_SCHEMA:
        raise ValueError("unexpected version manifest")
    return ProducerFingerprint.create(
        producer_id=COHORT_ID,
        producer_version=COHORT_VERSION,
        dependencies=(
            ProducerDependency(
                locator="lottolab://k3/full-source-and-runtime-manifest",
                source_sha256=_hash(_canonical(manifest)),
                load_bearing_role="all project Python sources, policy and runtime identity",
            ),
        ),
    )


def make_cohort(manifest: dict[str, object], *, frozen_at: datetime) -> FrozenCohortRef:
    fingerprint = version_fingerprint(manifest)
    return FrozenCohortRef(
        lottery_type=LotteryType.BIG_LOTTO,
        cohort_id=COHORT_ID,
        cohort_version=COHORT_VERSION,
        authority_sha256=fingerprint.digest,
        frozen_at=frozen_at,
        member_ids=MEMBERS,
        checkpoint_sizes=(1,),
        checkpoint_provenance=(TemporalProvenance.POST_FREEZE_DATE_PROSPECTIVE,),
    )


@dataclass(frozen=True, slots=True)
class GuardedK3CohortProducer:
    repo: Path
    manifest: dict[str, object]
    registration: PreOutcomeTargetRegistration
    history: tuple[K3HistoryRow, ...]
    absence: OutcomePresenceAttestation
    clock: Callable[[], datetime]

    def predict(self, context: PredictionContext) -> PredictionDraft:
        """Generate every member only after a shared target and history bind."""
        if capture_version_manifest(self.repo) != self.manifest:
            raise ValueError("frozen source or runtime drifted")
        if (
            context.target != self.registration.target
            or context.causal_history != self.registration.causal_history
            or context.producer_fingerprint != version_fingerprint(self.manifest)
            or context.cohort.member_ids != MEMBERS
            or context.cohort.authority_sha256 != context.producer_fingerprint.digest
        ):
            raise ValueError("cohort context does not match registered frozen authority")
        baseline = MatchedBaselineRef(
            lottery_type=LotteryType.BIG_LOTTO,
            baseline_id="fixed-greedy-k3",
            baseline_version="fixed-greedy-k3-v1",
            authority_sha256=_hash(_canonical(GREEDY_K3)),
            ticket_count=3,
            candidate_sizes=(6, 6, 6),
        )
        entries: list[PredictionEntryDraft] = []
        for policy in (
            K3Policy.EXHAUSTIVE,
            K3Policy.ANALYZE_CANDIDATE,
            K3Policy.BACKTEST_STRATEGY_1,
            K3Policy.OPTIMIZED_ENSEMBLE,
        ):
            result = generate_guarded_k3(
                policy=policy,
                registration=self.registration,
                history=self.history,
                absence=self.absence,
                clock=self.clock,
            )
            entries.append(
                PredictionEntryDraft.available(
                    member_id=policy.value,
                    selections=tuple(ProspectiveSelection(ticket) for ticket in result.tickets),
                    matched_baseline=baseline,
                )
            )
        entries.append(
            PredictionEntryDraft.available(
                member_id="GREEDY",
                selections=tuple(ProspectiveSelection(ticket) for ticket in GREEDY_K3),
                matched_baseline=baseline,
            )
        )
        if capture_version_manifest(self.repo) != self.manifest:
            raise ValueError("frozen source or runtime drifted during prediction")
        return PredictionDraft(tuple(entries))


def create_local_prediction(
    *,
    store: ProspectiveObservationStore,
    producer: GuardedK3CohortProducer,
    cohort: FrozenCohortRef,
) -> PredictionSyncResult:
    """Use the existing create-once store; a trusted external seal is still required."""
    registration = producer.registration
    context = PredictionContext(
        target=registration.target,
        cohort=cohort,
        producer_fingerprint=version_fingerprint(producer.manifest),
        causal_history=registration.causal_history,
    )
    return PredictionPhaseService(
        store=store,
        producer=producer,
        game_contracts=repository_game_contracts(),
        clock=producer.clock,
    ).sync(
        PredictionPhaseRequest(
            context=context,
            outcome_presence_at_start=OutcomePresenceAtPrediction.ABSENT,
        )
    )
