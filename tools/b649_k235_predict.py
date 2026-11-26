"""Executable prediction and quality validation entrypoint for B649 K2/K3/K5.

This tool implements the candidate prediction entry for B649 K2/K3/K5:
1. Verifies that the local runtime environment (Python 3.13, local TARGET_WORKTREE)
   is loaded cleanly with Horizon v0.2.
2. Reads the official database in strict read-only snapshot mode (mode=ro, query_only).
3. Reads frozen Top-3 strategies as of draw 096 from rank_history.json.
4. Generates predictions for the specified target draw (default: 115000098)
   using the validated causal history up to the cutoff draw (default: 115000097).
5. Executes the B649 K235 output quality component (disjointness, shapes, exact coverage).
6. Writes comprehensive JSON predictions and human-readable ticket text files to
   the authorized output directory without silent overwriting.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import platform
import sqlite3
import subprocess
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, cast

# Force local worktree roots onto sys.path before any other imports
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tools"))
sys.path.insert(0, str(REPO_ROOT / "src"))

# Runtime imports from TARGET_WORKTREE
import lottolab.strategies.adapters.biglotto_horizon_minimax as hm  # noqa: E402
from lottolab.application.legacy_source_native_portfolios_wave26 import (  # noqa: E402
    DEFAULT_SOURCE_NATIVE_WAVE26_USER_SEED,
    SOURCE_NATIVE_WAVE26_PROTOCOL,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE26_METHOD,
)
from lottolab.application.use_cases.generate_bet import (  # noqa: E402
    instantiate_portfolio_adapter,
)
from lottolab.domain.b649_next_undrawn_forecast import (  # noqa: E402
    OBJECTIVE,
    RANKING_POLICY_VERSION,
    digest,
)
from lottolab.domain.draws import LotteryType  # noqa: E402
from lottolab.domain.prospective_observer import (  # noqa: E402
    ObservationTarget,
    ProducerDependency,
    ProducerFingerprint,
)
from lottolab.domain.research_live_forecast import (  # noqa: E402
    canonical_json,
)
from lottolab.infrastructure.persistence.project_database_paths import (  # noqa: E402
    project_database_directory,
)
from lottolab.infrastructure.persistence.draw_schema import (  # noqa: E402
    LocalDataPaths,
)
from lottolab.infrastructure.pre_outcome_target_operational import (  # noqa: E402
    OPERATIONAL_CAUSAL_HISTORY_SCHEMA_VERSION,
    SQLitePreOutcomeCausalHistoryAuthority,
)
from lottolab.research.b649_k235_output_quality import (  # noqa: E402
    FAIR_DRAW_EXACT_COVERAGE_FRACTIONS,
    QUALITY_COMPONENT_VERSION,
    partition_k_entries,
)
from lottolab.strategies.adapters.base import CausalDrawRow  # noqa: E402
from lottolab.strategies.catalog import production_catalog  # noqa: E402
from lottolab.strategies.executable_registry import ExecutableRegistry  # noqa: E402

DEFAULT_DB_PATH = project_database_directory() / "lottolab.db"
DEFAULT_RANK_HISTORY = Path(
    "/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.task-data/"
    "BIGLOTTO_115000096_K2_K3_K5_TOP3_115000097_PREDICTION_R1/rank_history.json"
)
DEFAULT_OUTPUT_DIR = REPO_ROOT / ".task-data" / "B649_K235_CANONICAL_ADOPTION_CANDIDATE_R1"

PREDICTION_SCHEMA_VERSION = "B649_K235_DISJOINT_PREDICTION_V1"
PREDICTION_RUN_ID = "B649_K235_CANONICAL_ADOPTION_CANDIDATE_R1"
NATIVE_INPUT_SCHEMA = "NUMBER2_9_B649_NATIVE_PREDICTION_V1"


@dataclass(frozen=True, slots=True)
class Draw:
    """One validated BIG_LOTTO draw from the canonical authority."""

    draw_number: str
    draw_date: date
    main_numbers: tuple[int, ...]
    special_number: int

    @property
    def sort_key(self) -> tuple[date, int]:
        return self.draw_date, int(self.draw_number)

    def causal_row(self) -> CausalDrawRow:
        return CausalDrawRow(
            draw=self.draw_number,
            date=self.draw_date.isoformat(),
            numbers=self.main_numbers,
        )


_WAVE11_SEED_FIELDS: Mapping[str, tuple[str, str, str, str]] = {
    "legacy_biglotto__core_satellite__611284461323": (
        "_RANDOM_NATIVE_PROTOCOL",
        "_CORE_SATELLITE_METHOD_ID",
        "_CORE_SATELLITE_SOURCE_SHA256",
        "_RANDOM_NATIVE_DEFAULT_USER_SEED",
    ),
    "legacy_biglotto__zone_split__b6144f9d479f": (
        "_RANDOM_NATIVE_PROTOCOL",
        "_ZONE_SPLIT_METHOD_ID",
        "_ZONE_SPLIT_SOURCE_SHA256",
        "_RANDOM_NATIVE_DEFAULT_USER_SEED",
    ),
    "legacy_biglotto__big_lotto_exhaustive_audit__694d353b7ca2": (
        "_HISTORY_NATIVE_PROTOCOL",
        "_EXHAUSTIVE_AUDIT_METHOD_ID",
        "_EXHAUSTIVE_AUDIT_SOURCE_SHA256",
        "_HISTORY_NATIVE_DEFAULT_USER_SEED",
    ),
}

_WAVE26_METHODS: Mapping[str, str] = {
    "legacy_biglotto__test_ces__78d17c530ab8": "tools/test_ces.py",
    "legacy_biglotto__test_dms__b63442289bd5": "tools/test_dms.py",
    "legacy_biglotto__test_greedy_optimizer__82df7f878ece": "tools/test_greedy_optimizer.py",
    "legacy_biglotto__test_mwsc__ba37643d6a3b": "tools/test_mwsc.py",
}

_STATISTICAL_MODULES = frozenset(
    {
        "lottolab.strategies.adapters.biglotto_wave3",
        "lottolab.strategies.adapters.biglotto_wave4",
        "lottolab.strategies.adapters.biglotto_wave5",
        "lottolab.strategies.adapters.biglotto_wave6",
        "lottolab.strategies.adapters.biglotto_wave7",
        "lottolab.strategies.adapters.biglotto_wave8",
        "lottolab.strategies.adapters.biglotto_wave9",
        "lottolab.strategies.adapters.biglotto_wave13",
        "lottolab.strategies.adapters.biglotto_wave14",
        "lottolab.strategies.adapters.biglotto_batch15",
    }
)


def _resolve_seed_metadata(
    descriptor: Any,
    history: tuple[CausalDrawRow, ...],
) -> dict[str, object]:
    """Resolve determinism seed metadata for strategy provenance."""
    module_name = (descriptor.adapter_path or "").split(":", 1)[0]
    metadata: dict[str, object] = {
        "behavior": "DETERMINISTIC",
        "seed": None,
        "rng_source": "native_adapter_deterministic",
        "rng_state_rule": "NONE_DETERMINISTIC",
        "configuration": "native_adapter_configuration",
        "prestate_dependency": "causal_history_only",
    }
    if descriptor.strategy_id in _WAVE11_SEED_FIELDS and history:
        module = importlib.import_module(module_name)
        protocol_name, method_name, source_name, user_seed_name = _WAVE11_SEED_FIELDS[
            descriptor.strategy_id
        ]
        target_fn = module._target_after_causal_cutoff
        target_identity = target_fn(history)
        protocol = getattr(module, protocol_name)
        method_id = getattr(module, method_name)
        source_sha = getattr(module, source_name)
        user_seed = getattr(module, user_seed_name)
        material = "|".join((protocol, method_id, source_sha, target_identity, "0", user_seed))
        digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
        metadata.update(
            {
                "behavior": "SEEDED_STOCHASTIC",
                "seed": int(digest, 16),
                "seed_digest": digest,
                "seed_material": material,
                "rng_source": "random.Random(version=2)",
                "rng_state_rule": "random.Random(seed_integer, version=2)",
                "configuration": protocol,
                "prestate_dependency": "last_causal_draw_identity_only",
            }
        )
        return metadata

    if (
        descriptor.strategy_id == "legacy_biglotto__constraint_filter_predictor__3a85b3995002"
        and history
    ):
        module = importlib.import_module(module_name)
        seed_fn = module._seed_integer
        target_fn = module._target_after_causal_cutoff
        seed_integer = seed_fn(history)
        target_identity = target_fn(history)
        protocol = module._HISTORY_NATIVE_WAVE2_PROTOCOL
        method_id = module._CONSTRAINT_FILTER_METHOD_ID
        source_sha = module._CONSTRAINT_FILTER_SOURCE_SHA256
        user_seed = module._HISTORY_NATIVE_WAVE2_DEFAULT_USER_SEED
        material = "|".join((protocol, method_id, source_sha, target_identity, "0", user_seed))
        digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
        metadata.update(
            {
                "behavior": "SEEDED_STOCHASTIC",
                "seed": int(seed_integer),
                "seed_digest": digest,
                "seed_material": material,
                "rng_source": "numpy.random.RandomState + random.Random",
                "rng_state_rule": (
                    "legacy NumPy RandomState(seed % 2**32) + random.Random(seed, version=2)"
                ),
                "configuration": protocol,
                "prestate_dependency": "last_causal_draw_identity_only",
            }
        )
        return metadata

    if descriptor.strategy_id in _WAVE26_METHODS and history:
        method_id = _WAVE26_METHODS[descriptor.strategy_id]
        wave8 = importlib.import_module("lottolab.strategies.adapters.biglotto_wave8")
        target_fn = wave8._target_after_causal_cutoff
        target_identity = target_fn(history)
        source_sha = SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE26_METHOD[method_id]
        material = "|".join(
            (
                SOURCE_NATIVE_WAVE26_PROTOCOL,
                method_id,
                source_sha,
                target_identity,
                "0",
                DEFAULT_SOURCE_NATIVE_WAVE26_USER_SEED,
            )
        )
        digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
        metadata.update(
            {
                "behavior": "SEEDED_STOCHASTIC",
                "seed": int(digest, 16),
                "seed_digest": digest,
                "seed_material": material,
                "rng_source": "wave26.statistical_predictor",
                "rng_state_rule": (
                    "wave26 frozen statistical calls reseed from causal history length"
                ),
                "configuration": SOURCE_NATIVE_WAVE26_PROTOCOL,
                "prestate_dependency": "last_causal_draw_identity_and_causal_history",
            }
        )
        return metadata

    if module_name in _STATISTICAL_MODULES:
        metadata.update(
            {
                "behavior": "SEEDED_STOCHASTIC",
                "seed": len(history),
                "rng_source": "random.Random",
                "rng_state_rule": (
                    "random.Random(len(causal_history)) inside frozen statistical predictor"
                ),
                "configuration": "UNIFIED_STATISTICAL_HISTORY_LENGTH_SEED",
                "prestate_dependency": "causal_history_length_only",
            }
        )
        if descriptor.strategy_id == "legacy_biglotto__test_zdp__e80cc7e95453":
            metadata["rng_state_rule"] = (
                "random.Random(len(causal_history)) for statistical pool; "
                "random.seed(42) before each fallback"
            )
            metadata["fallback_seed"] = 42
        return metadata

    if descriptor.strategy_id == "legacy_biglotto__biglotto_diversified_ensemble_v6__8caaac8fcb5d":
        metadata.update(
            {
                "behavior": "SEEDED_STOCHASTIC",
                "seed": 42,
                "rng_source": "random.Random",
                "rng_state_rule": (
                    "local random.Random(42) per adapter call; NumPy seed is output-inert"
                ),
                "configuration": "DIVERSIFIED_ENSEMBLE_V6_FIXED_SEED",
                "prestate_dependency": "causal_history_only",
            }
        )
    return metadata


def _history_fingerprint(history: Sequence[Draw]) -> str:
    """Compute deterministic SHA-256 fingerprint for causal history draws."""
    payload = [
        {
            "draw_date": draw.draw_date.isoformat(),
            "draw_number": draw.draw_number,
            "main_numbers": list(draw.main_numbers),
            "special_number": draw.special_number,
        }
        for draw in history
    ]
    return hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        + b"\n"
    ).hexdigest()


def _resolve_adapter_source(
    descriptor: Any,
    override_mapping: Mapping[str, Any] | None = None,
) -> tuple[str, str]:
    strategy_id = getattr(descriptor, "strategy_id", "")
    if override_mapping and strategy_id in override_mapping:
        entry = override_mapping[strategy_id]
        return (
            str(entry.get("adapter_source_path", "")),
            str(entry.get("adapter_source_sha256", "")),
        )
    adapter_path_str = getattr(descriptor, "adapter_path", "") or ""
    if ":" in adapter_path_str:
        module_name = adapter_path_str.split(":", 1)[0]
        try:
            mod = importlib.import_module(module_name)
            if hasattr(mod, "__file__") and mod.__file__:
                p = Path(mod.__file__).resolve()
                if p.exists():
                    sha = hashlib.sha256(p.read_bytes()).hexdigest()
                    return str(p), sha
        except Exception:
            pass
    return "", ""


def _resolve_adapter_class_identity(descriptor: Any) -> str:
    """Return the loaded class identity named by an executable catalog descriptor."""
    adapter_path = getattr(descriptor, "adapter_path", None)
    if not isinstance(adapter_path, str) or ":" not in adapter_path:
        raise ValueError("effective adapter class requires a module:class catalog binding")
    module_name, _, class_name = adapter_path.partition(":")
    if not module_name or not class_name:
        raise ValueError("effective adapter class requires a module:class catalog binding")
    module = importlib.import_module(module_name)
    adapter_class = getattr(module, class_name, None)
    if not isinstance(adapter_class, type):
        raise ValueError(f"catalog adapter binding is not a class: {adapter_path}")
    identity = f"{adapter_class.__module__}:{adapter_class.__qualname__}"
    if identity != adapter_path:
        raise ValueError(f"catalog adapter class identity mismatch: {identity} != {adapter_path}")
    return identity


def _resolve_source_execution(
    override: Mapping[str, Any] | None = None,
) -> dict[str, str]:
    if override is not None:
        res = dict(override)
        for key in ("repository", "commit", "tree", "loaded_code_sha256"):
            val = res.get(key)
            if not isinstance(val, str) or not val.strip():
                raise ValueError(f"source execution missing required field: {key}")
        if "pre_draw_proof_status" not in res:
            res["pre_draw_proof_status"] = "LOCAL_ONLY"
        return res

    producer_file = Path(__file__).resolve()
    loaded_code_sha256 = hashlib.sha256(producer_file.read_bytes()).hexdigest()
    repo_path = str(REPO_ROOT)
    commit = ""
    tree = ""
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=str(REPO_ROOT), text=True
        ).strip()
        tree = subprocess.check_output(
            ["git", "rev-parse", "HEAD^{tree}"], cwd=str(REPO_ROOT), text=True
        ).strip()
    except Exception as exc:
        raise ValueError(f"unable to determine source git commit and tree: {exc}") from exc

    if not commit or not tree:
        raise ValueError("source git commit and tree must be non-empty")

    return {
        "repository": repo_path,
        "commit": commit,
        "tree": tree,
        "loaded_code_sha256": loaded_code_sha256,
        "pre_draw_proof_status": "LOCAL_ONLY",
    }


def _resolve_runtime_manifest(
    override: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if override is not None:
        res = dict(override)
        if "sha256" not in res:
            res["sha256"] = digest(res)
        return res

    py_exe = Path(sys.executable).resolve()
    exe_sha = hashlib.sha256(py_exe.read_bytes()).hexdigest() if py_exe.exists() else ("0" * 64)
    producer_file = Path(__file__).resolve()
    producer_sha = hashlib.sha256(producer_file.read_bytes()).hexdigest()
    authority_file = (
        REPO_ROOT / "src/lottolab/infrastructure/pre_outcome_target_operational.py"
    ).resolve()
    authority_sha = hashlib.sha256(authority_file.read_bytes()).hexdigest()
    manifest_material: dict[str, Any] = {
        "python": {
            "implementation": platform.python_implementation(),
            "version": platform.python_version(),
            "executable": str(py_exe),
            "executable_sha256": exe_sha,
        },
        "os": platform.system().lower(),
        "architecture": platform.machine(),
        "dependencies": [
            {
                "name": "tools/b649_k235_predict.py",
                "locator": str(producer_file),
                "versions": {"producer": "v1"},
                "content_sha256": producer_sha,
            },
            {
                "name": "src/lottolab/infrastructure/pre_outcome_target_operational.py",
                "locator": str(authority_file),
                "versions": {"authority": OPERATIONAL_CAUSAL_HISTORY_SCHEMA_VERSION},
                "content_sha256": authority_sha,
            },
        ],
    }
    manifest_material["sha256"] = digest(manifest_material)
    return manifest_material


def _resolve_producer_fingerprint(
    override: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if override is not None:
        return dict(override)

    producer_file = Path(__file__).resolve()
    producer_sha = hashlib.sha256(producer_file.read_bytes()).hexdigest()
    authority_file = (
        REPO_ROOT / "src/lottolab/infrastructure/pre_outcome_target_operational.py"
    ).resolve()
    authority_sha = hashlib.sha256(authority_file.read_bytes()).hexdigest()
    deps = (
        ProducerDependency(
            locator="tools/b649_k235_predict.py",
            source_sha256=producer_sha,
            load_bearing_role="native prediction producer entrypoint",
        ),
        ProducerDependency(
            locator="src/lottolab/infrastructure/pre_outcome_target_operational.py",
            source_sha256=authority_sha,
            load_bearing_role="canonical causal-history snapshot authority",
        ),
    )
    fp = ProducerFingerprint.create(
        producer_id="tools/b649_k235_predict.py",
        producer_version="v1",
        dependencies=deps,
    )
    return fp.canonical_dict()


def build_v6_provenance_output(
    *,
    target_draw: str,
    cutoff_draw: str,
    draws: Sequence[Draw],
    k5_entries: list[dict[str, Any]],
    descriptors_map: Mapping[str, Any],
    schedule_binding: Mapping[str, Any] | None,
    ranking_evidence: Mapping[str, Any] | None,
    generation_started_at: str | None,
    generation_finished_at: str | None,
    task_id: str = "NUMBER2_9_NATIVE_PREDICTION",
    pre_draw_proof_status: str = "LOCAL_ONLY",
    source_locator: str = "canonical-next-undrawn",
    source_execution_override: Mapping[str, Any] | None = None,
    runtime_manifest_override: Mapping[str, Any] | None = None,
    producer_override: Mapping[str, Any] | None = None,
    catalog_override: Mapping[str, Any] | None = None,
    canonical_history_snapshot: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Assemble complete v6 native_result and provenance context from actual execution evidence."""
    if not generation_started_at or not str(generation_started_at).strip():
        raise ValueError("generation_started_at timestamp is required")
    if not generation_finished_at or not str(generation_finished_at).strip():
        raise ValueError("generation_finished_at timestamp is required")

    if not pre_draw_proof_status or pre_draw_proof_status == "UNKNOWN":
        raise ValueError("pre_draw_proof_status cannot be empty or UNKNOWN")

    if schedule_binding is None:
        raise ValueError("schedule binding is required from named input")
    for key in ("schedule_authority_sha256", "scheduled_at", "target_draw_date"):
        val = schedule_binding.get(key)
        if not val or not str(val).strip():
            raise ValueError(f"schedule binding missing required field: {key}")

    sched_sha = str(schedule_binding["schedule_authority_sha256"])
    if len(sched_sha) != 64 or any(c not in "0123456789abcdefABCDEF" for c in sched_sha):
        raise ValueError("schedule_authority_sha256 must be a 64-character SHA-256")

    if ranking_evidence is None:
        raise ValueError("ranking evidence is required from named input")
    if ranking_evidence.get("objective") != OBJECTIVE:
        raise ValueError(f"ranking evidence objective must be {OBJECTIVE}")
    if ranking_evidence.get("ranking_policy_version") != RANKING_POLICY_VERSION:
        raise ValueError(f"ranking evidence policy version must be {RANKING_POLICY_VERSION}")
    if ranking_evidence.get("evaluation_window") != "FULL":
        raise ValueError("ranking evidence evaluation_window must be FULL")

    observations = ranking_evidence.get("observations")
    if not isinstance(observations, list):
        raise ValueError("ranking evidence observations must be a list")
    obs_order = [
        (str(item.get("strategy_id", "")), str(item.get("draw_number", "")))
        for item in observations
        if isinstance(item, dict)
    ]
    if obs_order != sorted(obs_order):
        raise ValueError("ranking observations must use the v6 canonical order")
    obs_digest = digest(observations)
    if ranking_evidence.get("evidence_payload_sha256") != obs_digest:
        raise ValueError("ranking evidence payload SHA mismatch")

    if not draws:
        raise ValueError("complete causal history draws are required")
    if draws[-1].draw_number != cutoff_draw:
        raise ValueError(
            f"causal history last draw {draws[-1].draw_number} does not match cutoff {cutoff_draw}"
        )
    if int(cutoff_draw) >= int(target_draw):
        raise ValueError(f"cutoff {cutoff_draw} must be strictly less than target {target_draw}")

    draws_list = [
        {
            "lottery_type": LotteryType.BIG_LOTTO.value,
            "draw_number": d.draw_number,
            "draw_date": d.draw_date.isoformat(),
            "main_numbers": list(d.main_numbers),
            "special_number": d.special_number,
        }
        for d in draws
    ]
    history_sha = digest(draws_list)
    if not history_sha:
        raise ValueError("causal history SHA is required")

    history_snapshot = {
        "reference": f"research-live-history:sha256:{history_sha}",
        "draws": draws_list,
        "sha256": history_sha,
        "history_fingerprint_sha256": _history_fingerprint(draws),
    }
    if canonical_history_snapshot is not None:
        history_snapshot["verified_canonical"] = dict(canonical_history_snapshot)

    target = {
        "lottery_type": LotteryType.BIG_LOTTO.value,
        "target_draw_number": target_draw,
        "target_draw_date": str(schedule_binding["target_draw_date"]),
        "scheduled_at": str(schedule_binding["scheduled_at"]),
        "timezone": str(schedule_binding.get("timezone", "Asia/Taipei")),
        "data_cutoff": cutoff_draw,
        "forecast_horizon": 1,
        "history_draw_count": len(draws_list),
        "causal_history_sha256": history_sha,
        "schedule_authority_sha256": sched_sha.lower(),
    }

    source_execution = _resolve_source_execution(source_execution_override)
    runtime_manifest = _resolve_runtime_manifest(runtime_manifest_override)
    producer_dict = _resolve_producer_fingerprint(producer_override)

    if len(k5_entries) != 3:
        raise ValueError(f"expected exactly 3 K5 strategies, got {len(k5_entries)}")

    native_strategies: list[dict[str, Any]] = []
    catalog_list: list[dict[str, Any]] = []
    generation_configs: list[dict[str, Any]] = []
    seeds: dict[str, int] = {}
    seen_ids: set[str] = set()
    seen_ranks: set[int] = set()

    causal_history_rows = tuple(d.causal_row() for d in draws)

    for entry in k5_entries:
        strategy_id = entry.get("strategy_id")
        if not isinstance(strategy_id, str) or not strategy_id.strip():
            raise ValueError("strategy_id is required")
        if strategy_id in seen_ids:
            raise ValueError(f"duplicate strategy_id: {strategy_id}")
        seen_ids.add(strategy_id)

        rank = entry.get("rank")
        if type(rank) is not int or rank < 1 or rank in seen_ranks:
            raise ValueError(f"invalid or duplicate rank for {strategy_id}: {rank}")
        seen_ranks.add(rank)

        version = entry.get("strategy_version")
        if not isinstance(version, str) or not version.strip():
            raise ValueError(f"strategy version is required for {strategy_id}")

        native_k = entry.get("native_ticket_count", 5)
        if native_k != 5:
            raise ValueError(f"expected native_k=5 for B649 v6 stream, got {native_k}")

        desc = descriptors_map.get(strategy_id)
        if desc is not None:
            gen_id = getattr(desc, "adapter_path", "") or f"fixture.{strategy_id}:Adapter"
            src_path, src_sha = _resolve_adapter_source(desc, catalog_override)
        else:
            gen_id = entry.get("generator_identity") or f"fixture.{strategy_id}:Adapter"
            if catalog_override and strategy_id in catalog_override:
                src_path = str(catalog_override[strategy_id].get("adapter_source_path", ""))
                src_sha = str(catalog_override[strategy_id].get("adapter_source_sha256", ""))
            else:
                src_path = entry.get("adapter_source_path") or f"fixture://adapters/{strategy_id}"
                src_sha = entry.get("adapter_source_sha256") or digest(src_path)

        if not src_path or not src_sha:
            raise ValueError(f"adapter source path and SHA are required for {strategy_id}")

        rng_semantics = entry.get("determinism_seed")
        if rng_semantics is None and desc is not None:
            rng_semantics = _resolve_seed_metadata(desc, causal_history_rows)
        if (
            rng_semantics is None
            or not isinstance(rng_semantics, dict)
            or "behavior" not in rng_semantics
        ):
            raise ValueError(f"RNG identity is required for {strategy_id}")

        raw_tickets = entry.get("tickets", [])
        if len(raw_tickets) != native_k:
            raise ValueError(
                f"expected {native_k} native tickets for {strategy_id}, got {len(raw_tickets)}"
            )

        formatted_tickets: list[dict[str, Any]] = []
        for pos, t in enumerate(raw_tickets, start=1):
            emitted = t.get("emitted_main_numbers")
            if (
                not isinstance(emitted, list)
                or len(emitted) != 6
                or any(type(n) is not int or not 1 <= n <= 49 for n in emitted)
                or len(set(emitted)) != 6
            ):
                raise ValueError(
                    f"invalid six-number native ticket for {strategy_id} at position {pos}"
                )
            legal = t.get("legal_main_numbers", emitted)
            if legal != emitted:
                raise ValueError(
                    f"emitted/legal ticket mismatch for {strategy_id} at position {pos}"
                )
            formatted_tickets.append(
                {
                    "position": pos,
                    "emitted_main_numbers": emitted,
                    "legal_main_numbers": legal,
                    "predicted_special_number": None,
                }
            )

        native_strategies.append(
            {
                "rank": rank,
                "strategy_id": strategy_id,
                "strategy_version": version,
                "native_k": native_k,
                "generator_identity": gen_id,
                "adapter_source_path": src_path,
                "adapter_source_sha256": src_sha,
                "rng_semantics": rng_semantics,
                "tickets": formatted_tickets,
            }
        )

        catalog_list.append(
            {
                "strategy_id": strategy_id,
                "version": version,
                "native_k": native_k,
                "adapter_path": gen_id,
                "adapter_source_path": src_path,
                "adapter_source_sha256": src_sha,
            }
        )

        generation_configs.append(
            {
                "strategy_id": strategy_id,
                "strategy_version": version,
                "native_k": native_k,
                "parameters": entry.get("parameters", {}),
                "rng_semantics": rng_semantics,
            }
        )

        if rng_semantics.get("behavior") == "SEEDED_STOCHASTIC":
            seed_val = rng_semantics.get("seed")
            if seed_val is None:
                raise ValueError(f"seed required for seeded stochastic strategy {strategy_id}")
            seeds[strategy_id] = int(seed_val)

    catalog_list.sort(key=lambda item: str(item["strategy_id"]))
    generation_configs.sort(key=lambda item: str(item["strategy_id"]))

    effective_rows = []
    for config in generation_configs:
        strategy_id = str(config["strategy_id"])
        descriptor = descriptors_map.get(strategy_id)
        if descriptor is None:
            raise ValueError(f"effective adapter class requires catalog strategy: {strategy_id}")
        effective_rows.append(
            {
                "strategy_id": strategy_id,
                "strategy_version": str(config["strategy_version"]),
                "native_k": int(config["native_k"]),
                "parameters_json": canonical_json(config.get("parameters", {})),
                "generation_config_sha256": digest(config),
                "status": "EXECUTED",
                "constructor_defaults": {},
                "instance_state": {},
                "adapter_class": _resolve_adapter_class_identity(descriptor),
            }
        )
    effective_parameters = {
        "strategies": effective_rows,
        "sha256": digest({"strategies": effective_rows}),
    }

    rng_stages = [
        {
            "strategy_id": str(config["strategy_id"]),
            "stage": "NATIVE_GENERATION",
            "status": "EXECUTED",
            "rng_semantics": config["rng_semantics"],
            "seed_status": (
                "EFFECTIVE_SEED_CAPTURED"
                if config["rng_semantics"].get("behavior") == "SEEDED_STOCHASTIC"
                else "NOT_APPLICABLE"
            ),
            "invocation_identity": f"native-{config['strategy_id']}",
            "replicate": 1,
        }
        for config in generation_configs
    ]
    rng_semantics_dict = {
        "stages": rng_stages,
        "reproducibility_boundary": "FIXED_SYNTHETIC_INPUTS_CODE_RUNTIME_CONFIG",
    }

    total_tickets = len(native_strategies) * 5

    native_result = {
        "schema_version": NATIVE_INPUT_SCHEMA,
        "task_id": task_id,
        "prediction_target": target_draw,
        "generated_at_local": generation_finished_at,
        "pre_draw_proof_status": pre_draw_proof_status,
        "target_rows_selected": False,
        "target_outcome": "UNOBSERVED_NOT_READ",
        "strategy_count_expected": len(native_strategies),
        "strategy_count_generated": len(native_strategies),
        "ticket_count_expected": total_tickets,
        "ticket_count_generated": total_tickets,
        "strategies": native_strategies,
    }

    provenance = {
        "target": target,
        "source_locator": source_locator,
        "source_execution": source_execution,
        "runtime_manifest": runtime_manifest,
        "history_snapshot": history_snapshot,
        "producer": producer_dict,
        "catalog": catalog_list,
        "generation_configs": generation_configs,
        "effective_parameters": effective_parameters,
        "rng_semantics": rng_semantics_dict,
        "ranking_evidence": ranking_evidence,
        "seeds": seeds,
        "generation_started_at": generation_started_at,
        "generation_finished_at": generation_finished_at,
    }

    return {
        "native_result": native_result,
        "provenance": provenance,
    }


def _verify_runtime_integrity() -> None:
    """AC2 verification: verify runtime bindings and file locations."""
    expected_hm_path = (
        REPO_ROOT / "src/lottolab/strategies/adapters/biglotto_horizon_minimax.py"
    ).resolve()
    actual_hm_path = Path(hm.__file__).resolve()
    if actual_hm_path != expected_hm_path:
        raise RuntimeError(
            f"Horizon module loaded from unexpected path: {actual_hm_path} != {expected_hm_path}"
        )

    adapter_cls = hm.BigLottoHorizonMinimaxDisagreementAdapter
    if adapter_cls.strategy_version != "v0.2":
        raise RuntimeError(
            f"Horizon adapter version must be v0.2, got {adapter_cls.strategy_version}"
        )

    catalog = production_catalog()
    descriptor = catalog.get("b649_new_horizon_minimax_disagreement_r1")
    if descriptor.version != "v0.2":
        raise RuntimeError(
            f"Horizon catalog descriptor version must be v0.2, got {descriptor.version}"
        )


def _load_causal_draws(
    db_path: Path,
    cutoff_draw: str,
    target_draw: str,
    harness: Any = None,
) -> tuple[tuple[Draw, ...], tuple[CausalDrawRow, ...]]:
    """Read BIG_LOTTO draws up to cutoff_draw using strict mode=ro and query_only."""
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found at {db_path}")

    cutoff_int = int(cutoff_draw)
    target_int = int(target_draw)
    if cutoff_int >= target_int:
        raise ValueError(
            f"Causal violation: cutoff draw {cutoff_draw} "
            f"must be strictly less than target draw {target_draw}"
        )

    uri = f"file:{db_path.resolve()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as conn:
        conn.execute("PRAGMA query_only = ON;")
        cursor = conn.execute(
            "SELECT draw_number, draw_date, main_numbers_json, special_numbers_json "
            "FROM draws WHERE lottery_type='BIG_LOTTO' "
            "ORDER BY draw_date, CAST(draw_number AS INTEGER)"
        )
        rows = cursor.fetchall()

    filtered_rows = [r for r in rows if int(r[0]) <= cutoff_int]

    # Verify target draw or any future draw is not in the causal history
    if any(int(r[0]) >= target_int for r in filtered_rows):
        raise RuntimeError(
            f"Causal violation: target draw {target_draw} "
            "or future draw leaked into causal history!"
        )
    if any(int(r[0]) > cutoff_int for r in filtered_rows):
        raise RuntimeError(
            f"Causal violation: draw beyond cutoff {cutoff_draw} present in causal history!"
        )

    last_id = filtered_rows[-1][0] if filtered_rows else "empty"
    if not filtered_rows or last_id != cutoff_draw:
        raise RuntimeError(
            f"Causal history does not end at cutoff draw {cutoff_draw} (last is {last_id})"
        )

    draw_factory = getattr(harness, "Draw", Draw) if harness is not None else Draw
    draws = tuple(
        draw_factory(
            draw_number=r[0],
            draw_date=date.fromisoformat(r[1]),
            main_numbers=tuple(json.loads(r[2])),
            special_number=json.loads(r[3])[0],
        )
        for r in filtered_rows
    )
    causal_history = tuple(d.causal_row() for d in draws)
    return draws, causal_history


# Public alias for testing and verification
load_causal_draws = _load_causal_draws


def _load_verified_causal_draws(
    db_path: Path,
    cutoff_draw: str,
    target_draw: str,
    target_draw_date: str,
    harness: Any = None,
) -> tuple[tuple[Draw, ...], tuple[CausalDrawRow, ...], dict[str, Any]]:
    """Load Native v6 numbers and canonical identity from one verified snapshot."""
    resolved_db = db_path.resolve(strict=True)
    paths = LocalDataPaths(resolved_db.parent, resolved_db)
    target_date = date.fromisoformat(target_draw_date)
    target = ObservationTarget(LotteryType.BIG_LOTTO, target_draw, target_date)
    authority = SQLitePreOutcomeCausalHistoryAuthority(paths)
    with authority.open_verified_snapshot(
        target,
        history_cutoff_draw=cutoff_draw,
    ) as (_, snapshot):
        draw_factory = getattr(harness, "Draw", Draw) if harness is not None else Draw
        draws_list: list[Draw] = []
        for row in snapshot.draws:
            if len(row.special_numbers) != 1:
                raise ValueError(
                    f"canonical draw {row.draw_number} must have one special number"
                )
            draws_list.append(
                draw_factory(
                    draw_number=row.draw_number,
                    draw_date=row.draw_date,
                    main_numbers=row.main_numbers,
                    special_number=row.special_numbers[0],
                )
            )
        draws = tuple(draws_list)
        causal_history = tuple(draw.causal_row() for draw in draws)
        canonical_history_snapshot: dict[str, Any] = {
            "authority": "SQLitePreOutcomeCausalHistoryAuthority.open_verified_snapshot",
            "schema_version": OPERATIONAL_CAUSAL_HISTORY_SCHEMA_VERSION,
            "target": target.canonical_dict(),
            "history_ref": snapshot.ref.canonical_dict(),
            "normalized_records": [
                {
                    "draw_number": row.draw_number,
                    "draw_date": row.draw_date.isoformat(),
                    "normalized_record_hash": row.normalized_record_hash,
                }
                for row in snapshot.draws
            ],
        }
    return draws, causal_history, canonical_history_snapshot


def _require_v6_history_binding(
    *,
    target_draw: str,
    cutoff_draw: str,
    schedule_binding: Mapping[str, Any] | None,
    ranking_evidence: Mapping[str, Any] | None,
) -> str:
    if schedule_binding is None:
        raise ValueError("schedule binding is required from named input")
    if ranking_evidence is None:
        raise ValueError("ranking evidence is required from named input")
    bound_target = schedule_binding.get("target_draw_number")
    if bound_target != target_draw:
        raise ValueError("schedule target issue does not match Producer target")
    target_date = schedule_binding.get("target_draw_date")
    if not isinstance(target_date, str) or not target_date.strip():
        raise ValueError("schedule binding missing required field: target_draw_date")
    try:
        parsed_target_date = date.fromisoformat(target_date)
    except ValueError as exc:
        raise ValueError("schedule binding target_draw_date must be an ISO date") from exc
    if parsed_target_date.isoformat() != target_date:
        raise ValueError("schedule binding target_draw_date must be canonical ISO date")
    if ranking_evidence.get("history_cutoff_draw") != cutoff_draw:
        raise ValueError("ranking evidence cutoff does not match Producer cutoff")
    return target_date


def _format_tickets_text(
    target_draw: str,
    cutoff_draw: str,
    history_count: int,
    ranking_selection: str,
    categories_data: Mapping[str, Mapping[str, Any]],
    overall_pipeline_status: str = "COMPLETE",
) -> str:
    lines: list[str] = [
        "=" * 80,
        f"B649 K2/K3/K5 DISJOINT PREDICTION — TARGET {target_draw} (CUTOFF {cutoff_draw})",
        f"Runtime: {REPO_ROOT}",
    ]
    if overall_pipeline_status != "COMPLETE":
        lines.append(f"Pipeline Status: {overall_pipeline_status}")
    lines.extend(
        [
            f"Ranking Selection: {ranking_selection} (Cutoff 115000096)",
            f"Causal History Draws: {history_count}",
            "Horizon Execution Version: v0.2 (zero cross-ticket overlap)",
            f"Quality Component: {QUALITY_COMPONENT_VERSION}",
            "=" * 80,
            "",
        ]
    )

    for cat_name in ("k2", "k3", "k5"):
        cdata = categories_data[cat_name]
        k_val = int(cat_name[1:])
        num, den = FAIR_DRAW_EXACT_COVERAGE_FRACTIONS[k_val]
        pct = (num / den) * 100.0

        accepted = cdata["accepted_entries"]
        rejected = cdata["rejected_entries"]
        is_avail = cdata.get("is_available", len(accepted) > 0)

        if not is_avail:
            cat_title = (
                f"[{cat_name.upper()}] — {k_val} Tickets per Strategy "
                f"[STATUS: UNAVAILABLE - NO QUALIFIED CANDIDATES]"
            )
        else:
            cat_title = (
                f"[{cat_name.upper()}] — {k_val} Tickets per Strategy "
                f"(Fair-Draw Any-Prize Coverage: {num}/{den} = {pct:.4f}%)"
            )
        lines.append(cat_title)
        lines.append(f"  Accepted Candidates ({len(accepted)}):")
        if not accepted:
            lines.append("    (None)")
        for e in accepted:
            sid = e["strategy_id"]
            dname = e["display_name"]
            ver = e["strategy_version"]
            lines.append(f"    Rank {e['rank']}: {sid} ({dname}) [version: {ver}]")
            for idx, t in enumerate(e["tickets"], start=1):
                nums_str = " ".join(f"{n:02d}" for n in t["emitted_main_numbers"])
                lines.append(f"      Ticket {idx}: {nums_str}")

        lines.append(f"  Rejected Candidates ({len(rejected)}):")
        if not rejected:
            lines.append("    (None)")
        for e in rejected:
            sid = e["strategy_id"]
            dname = e["display_name"]
            ver = e["strategy_version"]
            reasons_str = "; ".join(e["rejection_reasons"])
            lines.append(f"    Rank {e['rank']}: {sid} ({dname}) [version: {ver}]")
            lines.append(f"      Rejection Reasons: {reasons_str}")
            for idx, t in enumerate(e["tickets"], start=1):
                nums_str = " ".join(f"{n:02d}" for n in t["emitted_main_numbers"])
                lines.append(f"      Raw Ticket {idx}: {nums_str}")
        lines.append("")

    return "\n".join(lines)


def run_prediction(
    *,
    db_path: Path = DEFAULT_DB_PATH,
    rank_history_path: Path = DEFAULT_RANK_HISTORY,
    cutoff_draw: str = "115000097",
    target_draw: str = "115000098",
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    overwrite: bool = False,
    raw_predictions_override: dict[str, Any] | None = None,
    emit_v6_provenance: bool = False,
    schedule_binding: Mapping[str, Any] | None = None,
    ranking_evidence: Mapping[str, Any] | None = None,
    source_execution_override: Mapping[str, Any] | None = None,
    runtime_manifest_override: Mapping[str, Any] | None = None,
    producer_override: Mapping[str, Any] | None = None,
    catalog_override: Mapping[str, Any] | None = None,
    task_id: str = "NUMBER2_9_NATIVE_PREDICTION",
    pre_draw_proof_status: str = "LOCAL_ONLY",
    source_locator: str = "canonical-next-undrawn",
    **_kwargs: Any,
) -> dict[str, Any]:
    """Execute prediction generation and quality validation pipeline."""

    _verify_runtime_integrity()

    cutoff_int = int(cutoff_draw)
    target_int = int(target_draw)
    ranking_cutoff = "115000096"
    if cutoff_int >= target_int:
        raise ValueError(
            f"Causal violation: cutoff draw {cutoff_draw} "
            f"must be strictly less than target draw {target_draw}"
        )
    if int(ranking_cutoff) > cutoff_int:
        raise ValueError(
            f"Causal violation: frozen ranking cutoff {ranking_cutoff} "
            f"must not exceed prediction cutoff {cutoff_draw}"
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"predictions_{target_draw}.json"
    txt_path = output_dir / f"tickets_{target_draw}.txt"

    # 1. Load the v6 history and its canonical identity from the same snapshot.
    canonical_history_snapshot: dict[str, Any] | None = None
    if emit_v6_provenance:
        target_draw_date = _require_v6_history_binding(
            target_draw=target_draw,
            cutoff_draw=cutoff_draw,
            schedule_binding=schedule_binding,
            ranking_evidence=ranking_evidence,
        )
        draws, causal_history, canonical_history_snapshot = _load_verified_causal_draws(
            db_path,
            cutoff_draw,
            target_draw,
            target_draw_date,
        )
    else:
        draws, causal_history = _load_causal_draws(db_path, cutoff_draw, target_draw)

    # 2. Load ranking selection (FROZEN_TOP3_AS_OF_096)
    if not rank_history_path.exists():
        raise FileNotFoundError(f"rank_history.json not found at {rank_history_path}")
    rank_history = json.loads(rank_history_path.read_text(encoding="utf-8"))

    catalog = production_catalog()
    registry = ExecutableRegistry(catalog)
    descriptors = tuple(catalog.list(lottery_type=LotteryType.BIG_LOTTO))
    dmap = {d.strategy_id: d for d in descriptors}

    slots: dict[str, list[dict[str, Any]]] = {}
    for k_val in (2, 3, 5):
        hist_k = rank_history["hist"][ranking_cutoff][str(k_val)][:3]
        slots[f"K{k_val}"] = [
            {
                "rank": item[0],
                "strategy_id": item[1],
                "display_name": rank_history["ids"][item[1]][1],
                "strategy_version": dmap[item[1]].version,
                "rank_at_recent_750": None,
                "rank_at_recent_300": None,
                "rank_at_recent_50": None,
            }
            for item in hist_k
        ]

    # 3. Generate raw predictions (or override for testing)
    generation_started_at = datetime.now(UTC).isoformat()
    if raw_predictions_override is not None:
        raw_predictions = raw_predictions_override
    else:
        raw_predictions = {}
        for k_count in (2, 3, 5):
            cat_name = f"k{k_count}"
            entries: list[dict[str, Any]] = []
            for slot in slots[f"K{k_count}"]:
                strategy_id = cast(str, slot["strategy_id"])
                desc = dmap[strategy_id]
                entry: dict[str, Any] = {
                    "rank": slot["rank"],
                    "strategy_id": strategy_id,
                    "display_name": slot["display_name"],
                    "strategy_version": slot["strategy_version"],
                    "native_ticket_count": k_count,
                    "ranking_basis": "FULL",
                    "rank_at_recent_750": slot.get("rank_at_recent_750"),
                    "rank_at_recent_300": slot.get("rank_at_recent_300"),
                    "rank_at_recent_50": slot.get("rank_at_recent_50"),
                    "determinism_seed": _resolve_seed_metadata(desc, causal_history),
                    "status": "TYPED_FAILURE",
                    "tickets": [],
                    "failure_type": None,
                    "detail": None,
                    "duplicate_ticket_positions": [],
                }
                try:
                    adapter_cls = registry.load_adapter(strategy_id)
                    impl = instantiate_portfolio_adapter(strategy_id, adapter_cls)
                    first = impl.get_bets_with_emission(causal_history, LotteryType.BIG_LOTTO)
                    second = impl.get_bets_with_emission(causal_history, LotteryType.BIG_LOTTO)
                    if first != second:
                        raise RuntimeError(
                            "same causal history did not reproduce identical native output"
                        )
                    if type(first) is not tuple or len(first) != k_count:
                        raise RuntimeError(f"expected {k_count} native tickets, got {len(first)}")
                    tickets = [
                        {
                            "emitted_main_numbers": list(b.emitted_main_numbers),
                            "legal_main_numbers": list(b.legal_main_numbers),
                            "predicted_special_number": b.special_number,
                        }
                        for b in first
                    ]
                    legal_tickets: list[tuple[int, ...]] = [b.legal_main_numbers for b in first]
                    duplicates = [
                        idx + 1 for idx, t in enumerate(legal_tickets) if t in legal_tickets[:idx]
                    ]
                    entry.update(
                        {
                            "status": "OK",
                            "tickets": tickets,
                            "failure_type": None,
                            "detail": None,
                            "duplicate_ticket_positions": duplicates,
                        }
                    )
                except Exception as exc:
                    entry["failure_type"] = type(exc).__name__
                    entry["detail"] = str(exc)
                entries.append(entry)
            raw_predictions[cat_name] = {"entries": entries}

    generation_finished_at = datetime.now(UTC).isoformat()

    # 4. Execute quality evaluation per K
    categories_output: dict[str, dict[str, Any]] = {}
    accepted_counts: dict[str, int] = {}
    rejected_counts: dict[str, int] = {}

    for cat_name in ("k2", "k3", "k5"):
        k_val = int(cat_name[1:])
        raw_entries = cast(list[dict[str, Any]], raw_predictions[cat_name]["entries"])
        accepted, rejected = partition_k_entries(raw_entries, k_val)

        accepted_counts[cat_name] = len(accepted)
        rejected_counts[cat_name] = len(rejected)
        is_avail = len(accepted) > 0

        num, den = FAIR_DRAW_EXACT_COVERAGE_FRACTIONS[k_val]
        categories_output[cat_name] = {
            "category": cat_name.upper(),
            "expected_strategy_count": 3,
            "expected_ticket_count_per_strategy": k_val,
            "generated_strategy_count": sum(e["status"] == "OK" for e in raw_entries),
            "accepted_strategy_count": len(accepted),
            "rejected_strategy_count": len(rejected),
            "has_qualified_candidates": is_avail,
            "is_available": is_avail,
            "availability_status": "AVAILABLE" if is_avail else "UNAVAILABLE",
            "fair_draw_exact_coverage_fraction": f"{num}/{den}" if is_avail else None,
            "fair_draw_coverage_probability": (num / den) if is_avail else None,
            "accepted_entries": accepted,
            "rejected_entries": rejected,
            "all_raw_entries": raw_entries,
        }

    qualified_k_count = sum(1 for c in categories_output.values() if c["is_available"])
    all_k_available = qualified_k_count == len(categories_output)
    has_any_qualified = qualified_k_count > 0

    if all_k_available:
        overall_status = "COMPLETE"
    elif has_any_qualified:
        overall_status = "PARTIAL_QUALIFIED"
    else:
        overall_status = "NO_QUALIFIED_PREDICTIONS"

    v6_bundle: dict[str, Any] | None = None
    if emit_v6_provenance:
        v6_bundle = build_v6_provenance_output(
            target_draw=target_draw,
            cutoff_draw=cutoff_draw,
            draws=draws,
            k5_entries=raw_predictions["k5"]["entries"],
            descriptors_map=dmap,
            schedule_binding=schedule_binding,
            ranking_evidence=ranking_evidence,
            generation_started_at=generation_started_at,
            generation_finished_at=generation_finished_at,
            task_id=task_id,
            pre_draw_proof_status=pre_draw_proof_status,
            source_locator=source_locator,
            source_execution_override=source_execution_override,
            runtime_manifest_override=runtime_manifest_override,
            producer_override=producer_override,
            catalog_override=catalog_override,
            canonical_history_snapshot=canonical_history_snapshot,
        )

    # 5. Build final prediction document
    result_document: dict[str, Any] = {
        "schema_version": PREDICTION_SCHEMA_VERSION,
        "prediction_run_id": PREDICTION_RUN_ID,
        "target_draw_number": target_draw,
        "prediction_cutoff_draw_number": cutoff_draw,
        "causal_history_length": len(draws),
        "causal_history_last_draw_number": draws[-1].draw_number,
        "causal_history_fingerprint": _history_fingerprint(draws),
        "ranking_selection": "FROZEN_TOP3_AS_OF_096",
        "ranking_cutoff_draw_number": ranking_cutoff,
        "runtime_source_path": str(REPO_ROOT),
        "actual_imported_horizon_path": str(Path(hm.__file__).resolve()),
        "actual_imported_horizon_version": (
            hm.BigLottoHorizonMinimaxDisagreementAdapter.strategy_version
        ),
        "quality_component_version": QUALITY_COMPONENT_VERSION,
        "future_data_used": "NO",
        "future_data_leakage": "NO",
        "cross_k_deduplication": False,
        "all_k_available": all_k_available,
        "has_any_qualified_prediction": has_any_qualified,
        "available_k_categories": [
            cat.upper() for cat, c in categories_output.items() if c["is_available"]
        ],
        "unavailable_k_categories": [
            cat.upper() for cat, c in categories_output.items() if not c["is_available"]
        ],
        "accepted_counts_by_k": accepted_counts,
        "rejected_counts_by_k": rejected_counts,
        "overall_pipeline_status": overall_status,
        "k2": categories_output["k2"],
        "k3": categories_output["k3"],
        "k5": categories_output["k5"],
    }

    if emit_v6_provenance and v6_bundle is not None:
        result_document["v6_provenance"] = v6_bundle
        result_document["native_result"] = v6_bundle["native_result"]
        result_document["provenance"] = v6_bundle["provenance"]

    # 6. Write JSON and TXT artifacts safely (AC1 / AC7 contract)
    ticket_text = _format_tickets_text(
        target_draw=target_draw,
        cutoff_draw=cutoff_draw,
        history_count=len(draws),
        ranking_selection="FROZEN_TOP3_AS_OF_096",
        categories_data=categories_output,
        overall_pipeline_status=overall_status,
    )

    new_json_bytes = (json.dumps(result_document, ensure_ascii=False, indent=2) + "\n").encode(
        "utf-8"
    )
    new_txt_bytes = ticket_text.encode("utf-8")

    json_exists = json_path.exists()
    txt_exists = txt_path.exists()

    if (json_exists or txt_exists) and not overwrite:
        # Check if existing files are identical (idempotent case)
        json_matches = False
        txt_matches = False
        if json_exists:
            try:
                existing_doc = json.loads(json_path.read_text(encoding="utf-8"))
                json_matches = existing_doc == result_document
            except Exception:
                json_matches = False

        if txt_exists:
            try:
                txt_matches = txt_path.read_bytes() == new_txt_bytes
            except Exception:
                txt_matches = False

        if json_exists and txt_exists and json_matches and txt_matches:
            # Idempotent: outputs already exist with identical content; preserve without rewrite
            return result_document

        # Conflicting content or incomplete files without overwrite -> explicit rejection
        conflicts: list[str] = []
        if json_exists and not json_matches:
            conflicts.append(f"JSON {json_path}")
        if txt_exists and not txt_matches:
            conflicts.append(f"TXT {txt_path}")
        if not json_exists and txt_exists:
            conflicts.append(f"missing JSON alongside existing TXT {txt_path}")
        if json_exists and not txt_exists:
            conflicts.append(f"missing TXT alongside existing JSON {json_path}")

        conflict_msg = "; ".join(conflicts) if conflicts else "existing output file"
        raise FileExistsError(
            "Output file already exists with conflicting or non-identical content "
            f"({conflict_msg}). Specify overwrite=True or --overwrite to replace."
        )

    json_path.write_bytes(new_json_bytes)
    txt_path.write_bytes(new_txt_bytes)

    if emit_v6_provenance and v6_bundle is not None:
        v6_path = output_dir / f"v6_native_prediction_{target_draw}.json"
        v6_bytes = (json.dumps(v6_bundle, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        if v6_path.exists() and not overwrite:
            try:
                existing_v6 = json.loads(v6_path.read_text(encoding="utf-8"))
                if existing_v6 != v6_bundle:
                    raise FileExistsError(
                        f"Output file {v6_path} already exists with conflicting content."
                    )
            except Exception as exc:
                if isinstance(exc, FileExistsError):
                    raise
                raise FileExistsError(
                    f"Output file {v6_path} already exists. Specify overwrite=True to replace."
                ) from exc
        v6_path.write_bytes(v6_bytes)

    return result_document


def produce_v6_native_prediction(
    *,
    db_path: Path = DEFAULT_DB_PATH,
    rank_history_path: Path = DEFAULT_RANK_HISTORY,
    cutoff_draw: str = "115000097",
    target_draw: str = "115000098",
    schedule_binding: Mapping[str, Any],
    ranking_evidence: Mapping[str, Any],
    output_dir: Path | None = None,
    overwrite: bool = False,
    raw_predictions_override: dict[str, Any] | None = None,
    source_execution_override: Mapping[str, Any] | None = None,
    runtime_manifest_override: Mapping[str, Any] | None = None,
    producer_override: Mapping[str, Any] | None = None,
    catalog_override: Mapping[str, Any] | None = None,
    task_id: str = "NUMBER2_9_NATIVE_PREDICTION",
    pre_draw_proof_status: str = "LOCAL_ONLY",
    source_locator: str = "canonical-next-undrawn",
    harness: Any = None,
) -> dict[str, Any]:
    """Execute native prediction and return complete v6 native_result and provenance pair.

    The returned dict contains:
    - 'native_result': schema NUMBER2_9_B649_NATIVE_PREDICTION_V1 mapping
    - 'provenance': complete v6 provenance context mapping
    which can be passed directly as adapt_native_input(**bundle) or
    adapt_native_input(bundle['native_result'], bundle['provenance']).
    """
    _verify_runtime_integrity()

    cutoff_int = int(cutoff_draw)
    target_int = int(target_draw)
    ranking_cutoff = "115000096"
    if cutoff_int >= target_int:
        raise ValueError(
            f"Causal violation: cutoff draw {cutoff_draw} "
            f"must be strictly less than target draw {target_draw}"
        )
    if int(ranking_cutoff) > cutoff_int:
        raise ValueError(
            f"Causal violation: frozen ranking cutoff {ranking_cutoff} "
            f"must not exceed prediction cutoff {cutoff_draw}"
        )

    target_draw_date = _require_v6_history_binding(
        target_draw=target_draw,
        cutoff_draw=cutoff_draw,
        schedule_binding=schedule_binding,
        ranking_evidence=ranking_evidence,
    )
    draws, causal_history, canonical_history_snapshot = _load_verified_causal_draws(
        db_path,
        cutoff_draw,
        target_draw,
        target_draw_date,
        harness=harness,
    )

    if not rank_history_path.exists():
        raise FileNotFoundError(f"rank_history.json not found at {rank_history_path}")
    rank_history = json.loads(rank_history_path.read_text(encoding="utf-8"))

    catalog = production_catalog()
    registry = ExecutableRegistry(catalog)
    descriptors = tuple(catalog.list(lottery_type=LotteryType.BIG_LOTTO))
    dmap = {d.strategy_id: d for d in descriptors}

    hist_k5 = rank_history["hist"][ranking_cutoff]["5"][:3]
    k5_slots = [
        {
            "rank": item[0],
            "strategy_id": item[1],
            "display_name": rank_history["ids"][item[1]][1],
            "strategy_version": dmap[item[1]].version if item[1] in dmap else "v0.1",
        }
        for item in hist_k5
    ]

    generation_started_at = datetime.now(UTC).isoformat()
    if raw_predictions_override is not None and "k5" in raw_predictions_override:
        k5_entries = raw_predictions_override["k5"]["entries"]
    else:
        k5_entries = []
        for slot in k5_slots:
            strategy_id = cast(str, slot["strategy_id"])
            desc = dmap[strategy_id]
            entry: dict[str, Any] = {
                "rank": slot["rank"],
                "strategy_id": strategy_id,
                "display_name": slot["display_name"],
                "strategy_version": slot["strategy_version"],
                "native_ticket_count": 5,
                "ranking_basis": "FULL",
                "determinism_seed": _resolve_seed_metadata(desc, causal_history),
                "status": "TYPED_FAILURE",
                "tickets": [],
                "failure_type": None,
                "detail": None,
                "duplicate_ticket_positions": [],
            }
            try:
                adapter_cls = registry.load_adapter(strategy_id)
                impl = instantiate_portfolio_adapter(strategy_id, adapter_cls)
                first = impl.get_bets_with_emission(causal_history, LotteryType.BIG_LOTTO)
                second = impl.get_bets_with_emission(causal_history, LotteryType.BIG_LOTTO)
                if first != second:
                    raise RuntimeError(
                        "same causal history did not reproduce identical native output"
                    )
                if type(first) is not tuple or len(first) != 5:
                    raise RuntimeError(f"expected 5 native tickets, got {len(first)}")
                tickets = [
                    {
                        "emitted_main_numbers": list(b.emitted_main_numbers),
                        "legal_main_numbers": list(b.legal_main_numbers),
                        "predicted_special_number": b.special_number,
                    }
                    for b in first
                ]
                entry.update(
                    {
                        "status": "OK",
                        "tickets": tickets,
                        "failure_type": None,
                        "detail": None,
                    }
                )
            except Exception as exc:
                entry["failure_type"] = type(exc).__name__
                entry["detail"] = str(exc)
            k5_entries.append(entry)

    generation_finished_at = datetime.now(UTC).isoformat()

    bundle = build_v6_provenance_output(
        target_draw=target_draw,
        cutoff_draw=cutoff_draw,
        draws=draws,
        k5_entries=k5_entries,
        descriptors_map=dmap,
        schedule_binding=schedule_binding,
        ranking_evidence=ranking_evidence,
        generation_started_at=generation_started_at,
        generation_finished_at=generation_finished_at,
        task_id=task_id,
        pre_draw_proof_status=pre_draw_proof_status,
        source_locator=source_locator,
        source_execution_override=source_execution_override,
        runtime_manifest_override=runtime_manifest_override,
        producer_override=producer_override,
        catalog_override=catalog_override,
        canonical_history_snapshot=canonical_history_snapshot,
    )

    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        v6_path = output_dir / f"v6_native_prediction_{target_draw}.json"
        v6_bytes = (json.dumps(bundle, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        if v6_path.exists() and not overwrite:
            try:
                existing = json.loads(v6_path.read_text(encoding="utf-8"))
                if existing != bundle:
                    raise FileExistsError(
                        f"Output file {v6_path} already exists with conflicting content."
                    )
            except Exception as exc:
                if isinstance(exc, FileExistsError):
                    raise
                raise FileExistsError(
                    f"Output file {v6_path} already exists. Specify overwrite=True to replace."
                ) from exc
        v6_path.write_bytes(v6_bytes)

    return bundle


def main() -> None:
    parser = argparse.ArgumentParser(
        description="B649 K2/K3/K5 Disjoint Prediction & Quality Validation Pipeline"
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=DEFAULT_DB_PATH,
        help="Path to lottolab.db (read-only SQLite)",
    )
    parser.add_argument(
        "--rank-history-path",
        type=Path,
        default=DEFAULT_RANK_HISTORY,
        help="Path to rank_history.json",
    )
    parser.add_argument(
        "--cutoff-draw",
        type=str,
        default="115000097",
        help="Prediction cutoff draw number (default: 115000097)",
    )
    parser.add_argument(
        "--target-draw",
        type=str,
        default="115000098",
        help="Prediction target draw number (default: 115000098)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Output directory for predictions and tickets",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing output files if present",
    )
    parser.add_argument(
        "--emit-v6-provenance",
        action="store_true",
        help="Emit complete v6 provenance and native result output",
    )
    parser.add_argument(
        "--schedule-binding-json",
        type=Path,
        default=None,
        help="Path to JSON file containing schedule binding",
    )
    parser.add_argument(
        "--ranking-evidence-json",
        type=Path,
        default=None,
        help="Path to JSON file containing ranking evidence",
    )
    parser.add_argument(
        "--task-id",
        type=str,
        default="NUMBER2_9_NATIVE_PREDICTION",
        help="Task ID for provenance output",
    )
    parser.add_argument(
        "--pre-draw-proof-status",
        type=str,
        default="LOCAL_ONLY",
        help="Pre-draw proof status for provenance output",
    )

    args, _unknown = parser.parse_known_args()

    sched_binding = None
    if args.schedule_binding_json:
        sched_binding = json.loads(args.schedule_binding_json.read_text(encoding="utf-8"))

    rank_ev = None
    if args.ranking_evidence_json:
        rank_ev = json.loads(args.ranking_evidence_json.read_text(encoding="utf-8"))

    try:
        doc = run_prediction(
            db_path=args.db_path,
            rank_history_path=args.rank_history_path,
            cutoff_draw=args.cutoff_draw,
            target_draw=args.target_draw,
            output_dir=args.output_dir,
            overwrite=args.overwrite,
            emit_v6_provenance=args.emit_v6_provenance,
            schedule_binding=sched_binding,
            ranking_evidence=rank_ev,
            task_id=args.task_id,
            pre_draw_proof_status=args.pre_draw_proof_status,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"STATUS: {doc['overall_pipeline_status']}")
    print(f"ALL_K_AVAILABLE: {doc['all_k_available']}")
    print(f"AVAILABLE_K: {doc['available_k_categories']}")
    print(f"UNAVAILABLE_K: {doc['unavailable_k_categories']}")
    print(f"TARGET: {doc['target_draw_number']}, CUTOFF: {doc['prediction_cutoff_draw_number']}")
    print(f"CAUSAL_HISTORY_LENGTH: {doc['causal_history_length']}")
    print(f"ACCEPTED_COUNTS: {doc['accepted_counts_by_k']}")
    print(f"REJECTED_COUNTS: {doc['rejected_counts_by_k']}")
    out_json = args.output_dir / f"predictions_{args.target_draw}.json"
    out_txt = args.output_dir / f"tickets_{args.target_draw}.txt"
    print(f"PREDICTION_JSON: {out_json}")
    print(f"TICKETS_TXT: {out_txt}")
    if args.emit_v6_provenance:
        out_v6 = args.output_dir / f"v6_native_prediction_{args.target_draw}.json"
        print(f"V6_NATIVE_PREDICTION_JSON: {out_v6}")

    if doc["overall_pipeline_status"] == "NO_QUALIFIED_PREDICTIONS":
        print(
            "ERROR: No qualified predictions available across any K category.",
            file=sys.stderr,
        )
        sys.exit(2)


if __name__ == "__main__":
    main()
