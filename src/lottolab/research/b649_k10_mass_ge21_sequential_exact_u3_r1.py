"""Sequential complete-enumerator exact-U3 closure for K10 masses >= 21."""

from __future__ import annotations

import itertools
import json
import os
import resource
import signal
import sys
import time
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import replace
from hashlib import sha256
from math import comb
from pathlib import Path
from tempfile import NamedTemporaryFile
from types import FrameType
from typing import cast

from lottolab.research.b649_k10_mass14_profiles_exact_u3_r1 import (
    DRAW_SIZE,
    INCUMBENT_COUNT,
    POOL_SIZE,
    TICKET_COUNT,
    ProfileResult,
    ProfileSpec,
    build_profile_result,
    profile_arithmetic,
    reconstruct_portfolio,
)
from lottolab.research.b649_official_any_prize_exact import (
    all_main_draw_masks,
    evaluate_portfolio,
)

type Profile = tuple[int, ...]
type ProfileEntry = tuple[int, Profile]

TASK_ID = "B649_K10_MASS_GE21_SEQUENTIAL_EXACT_U3_R1"
RESULT_PATH = Path(
    "docs/research/matrix-native-results/b649-k10-mass-ge21-sequential-exact-u3-r1.json"
)
TOTAL_CPU_CAP_SECONDS = 18 * 60 * 60
CPU_LIMIT_CLEANUP_GRACE_SECONDS = 60
MAX_EXACT_SCORE_WITNESSES = 4096
REPEATED_SIZES = tuple(range(2, TICKET_COUNT + 1))
REPEATED_INCIDENCE_EXCESS = TICKET_COUNT * DRAW_SIZE - POOL_SIZE

# The full-support profile vectors in masses 11-20 are read-only upstream
# records. They let the new bounded-product/partition derivation be checked
# without repeating any earlier pair-graph or support-orbit census.
PRIOR_CLOSED_PROFILES: dict[int, tuple[Profile, ...]] = {
    11: ((0, 38, 11, 0, 0, 0, 0, 0, 0, 0, 0),),
    12: ((0, 39, 9, 1, 0, 0, 0, 0, 0, 0, 0),),
    13: ((0, 40, 7, 2, 0, 0, 0, 0, 0, 0, 0),),
    14: (
        (0, 40, 8, 0, 1, 0, 0, 0, 0, 0, 0),
        (0, 41, 5, 3, 0, 0, 0, 0, 0, 0, 0),
    ),
    15: (
        (0, 41, 6, 1, 1, 0, 0, 0, 0, 0, 0),
        (0, 42, 3, 4, 0, 0, 0, 0, 0, 0, 0),
    ),
    16: (
        (0, 42, 4, 2, 1, 0, 0, 0, 0, 0, 0),
        (0, 43, 1, 5, 0, 0, 0, 0, 0, 0, 0),
    ),
    17: (
        (0, 41, 7, 0, 0, 1, 0, 0, 0, 0, 0),
        (0, 42, 5, 0, 2, 0, 0, 0, 0, 0, 0),
        (0, 43, 2, 3, 1, 0, 0, 0, 0, 0, 0),
    ),
    18: (
        (0, 42, 5, 1, 0, 1, 0, 0, 0, 0, 0),
        (0, 43, 3, 1, 2, 0, 0, 0, 0, 0, 0),
        (0, 44, 0, 4, 1, 0, 0, 0, 0, 0, 0),
    ),
    19: (
        (0, 43, 3, 2, 0, 1, 0, 0, 0, 0, 0),
        (0, 44, 1, 2, 2, 0, 0, 0, 0, 0, 0),
    ),
    20: (
        (0, 43, 4, 0, 1, 1, 0, 0, 0, 0, 0),
        (0, 44, 1, 3, 0, 1, 0, 0, 0, 0, 0),
        (0, 44, 2, 0, 3, 0, 0, 0, 0, 0, 0),
    ),
}

PRIOR_PROFILE_EVIDENCE: dict[str, str] = {
    "11-12": (
        "docs/research/matrix-native-results/"
        "b649-k10-overlap-mass11-mass12-proof-certificate-r1.json"
    ),
    "13-17": (
        "src/lottolab/research/b649_k10_mass14_profiles_exact_u3_r1.py and its durable captures"
    ),
    "18": "docs/research/matrix-native-results/b649-k10-mass18-profiles-exact-u3-r1.json",
    "19": "docs/research/matrix-native-results/b649-k10-mass19-profiles-exact-u3-r1.json",
    "20": "docs/research/matrix-native-results/b649-k10-mass20-profiles-exact-u3-r1.json",
}


def _log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


class CpuCapReached(RuntimeError):
    """Raised by SIGXCPU so the current incomplete profile is not recorded."""


def _profile_from_repeated_counts(counts: Sequence[int]) -> Profile | None:
    """Build one multiplicity vector and reject profiles outside full support."""

    if len(counts) != len(REPEATED_SIZES):
        raise ValueError("repeated-support multiplicities have the wrong width")
    profile = [0] * (TICKET_COUNT + 1)
    for size, count in zip(REPEATED_SIZES, counts, strict=True):
        profile[size] = count
    profile[1] = POOL_SIZE - sum(profile[2:])
    result = tuple(profile)
    if profile[1] <= 0:
        return None
    if (
        sum(result) != POOL_SIZE
        or sum(size * count for size, count in enumerate(result)) != TICKET_COUNT * DRAW_SIZE
        or sum(comb(size, 2) * count for size, count in enumerate(result)) < 11
    ):
        return None
    return result


def _mass_of_profile(profile: Profile) -> int:
    return sum(comb(size, 2) * count for size, count in enumerate(profile) if size >= 2)


def _derive_by_bounded_products() -> set[ProfileEntry]:
    """Enumerate the bounded multiplicity box from the two defining equations."""

    bounds = tuple(range(REPEATED_INCIDENCE_EXCESS // (size - 1) + 1) for size in REPEATED_SIZES)
    entries: set[ProfileEntry] = set()
    for counts in itertools.product(*bounds):
        if sum((size - 1) * count for size, count in zip(REPEATED_SIZES, counts, strict=True)) != (
            REPEATED_INCIDENCE_EXCESS
        ):
            continue
        profile = _profile_from_repeated_counts(counts)
        if profile is not None:
            entries.add((_mass_of_profile(profile), profile))
    return entries


def _derive_by_incidence_partitions() -> set[ProfileEntry]:
    """Independently enumerate partitions of the repeated-incidence excess."""

    entries: set[ProfileEntry] = set()

    def visit(remaining: int, largest_part: int, parts: tuple[int, ...]) -> None:
        if remaining == 0:
            counts = [0] * len(REPEATED_SIZES)
            for part in parts:
                counts[part - 1] += 1
            profile = _profile_from_repeated_counts(counts)
            if profile is not None:
                entries.add((_mass_of_profile(profile), profile))
            return
        for part in range(min(largest_part, remaining, TICKET_COUNT - 1), 0, -1):
            visit(remaining - part, part, (*parts, part))

    visit(REPEATED_INCIDENCE_EXCESS, TICKET_COUNT - 1, ())
    return entries


def derive_full_support_profiles() -> tuple[ProfileEntry, ...]:
    """Return all full-support K10 profiles, ordered by mass then histogram."""

    bounded = _derive_by_bounded_products()
    partitioned = _derive_by_incidence_partitions()
    if bounded != partitioned:
        raise ValueError(
            "independent full-support profile derivations disagree: "
            f"{sorted(bounded)} != {sorted(partitioned)}"
        )
    entries = tuple(sorted(bounded))
    if any(
        sum(profile) != POOL_SIZE
        or sum(size * count for size, count in enumerate(profile)) != TICKET_COUNT * DRAW_SIZE
        or profile[1] <= 0
        or _mass_of_profile(profile) != mass
        for mass, profile in entries
    ):
        raise ValueError("derived profile violates full-support K10 multiplicity equations")
    return entries


def derive_remaining_full_support_profiles() -> tuple[ProfileEntry, ...]:
    """Return the exact mass-21-and-higher suffix of the derived profile set."""

    return tuple(entry for entry in derive_full_support_profiles() if entry[0] >= 21)


def validate_prior_closed_profile_sets(
    profiles: Sequence[ProfileEntry] | None = None,
) -> dict[str, object]:
    """Check masses 11-20 against prior vectors without running any census."""

    entries = derive_full_support_profiles() if profiles is None else tuple(profiles)
    actual: dict[int, set[Profile]] = defaultdict(set)
    for mass, profile in entries:
        if 11 <= mass <= 20:
            actual[mass].add(profile)
    checks: list[dict[str, object]] = []
    for mass in range(11, 21):
        observed = actual[mass]
        expected = set(PRIOR_CLOSED_PROFILES[mass])
        if observed != expected:
            raise ValueError(
                f"derived mass-{mass} profiles differ from prior records: "
                f"{sorted(observed)} != {sorted(expected)}"
            )
        checks.append(
            {
                "MASS": mass,
                "PROFILE_COUNT": len(observed),
                "PROFILE_SET_SHA256": sha256(
                    json.dumps(sorted(observed), separators=(",", ":")).encode("utf-8")
                ).hexdigest(),
            }
        )
    return {
        "STATUS": "PASS",
        "CENSUSES_RERUN": False,
        "EVIDENCE": PRIOR_PROFILE_EVIDENCE,
        "MASS_PROFILE_CHECKS": checks,
    }


def build_remaining_profile_specs() -> tuple[ProfileSpec, ...]:
    """Translate remaining histograms into the complete support-census model."""

    entries = derive_remaining_full_support_profiles()
    profiles_by_mass: dict[int, list[Profile]] = defaultdict(list)
    for mass, profile in entries:
        profiles_by_mass[mass].append(profile)
    specs: list[ProfileSpec] = []
    for mass in sorted(profiles_by_mass):
        for index, profile in enumerate(sorted(profiles_by_mass[mass])):
            higher_counts = tuple(
                (size, profile[size]) for size in range(3, TICKET_COUNT + 1) if profile[size]
            )
            if len(profile) != TICKET_COUNT + 1 or not higher_counts:
                raise ValueError(
                    f"mass-{mass} profile has no higher-support multiplicities: {profile}"
                )
            base_size, base_count = higher_counts[0]
            spec = ProfileSpec(
                name=f"MASS{mass}_PROFILE_{chr(ord('A') + index)}",
                profile=profile,
                pair_label_count=profile[2],
                support_size=base_size,
                higher_label_count=base_count,
                extra_higher_support_counts=higher_counts[1:],
            )
            if profile_arithmetic(spec)["overlap_mass"] != mass:
                raise ValueError(f"{spec.name}: support multiplicities changed overlap mass")
            specs.append(spec)
    return tuple(specs)


def _canonical_payload_sha256(payload: dict[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256(encoded).hexdigest()


def _seal_payload(payload: dict[str, object]) -> dict[str, object]:
    sealed = dict(payload)
    sealed["RESULT_PAYLOAD_SHA256"] = _canonical_payload_sha256(payload)
    return sealed


def _write_checkpoint(payload: dict[str, object], result_path: Path) -> dict[str, object]:
    """Atomically persist the completed-profile ledger and its payload digest."""

    result_path.parent.mkdir(parents=True, exist_ok=True)
    sealed = _seal_payload(payload)
    temporary_path: Path | None = None
    try:
        with NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=result_path.parent,
            prefix=f".{result_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary_path = Path(stream.name)
            stream.write(json.dumps(sealed, sort_keys=True, indent=2) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, result_path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()
    return sealed


def _load_checkpoint(result_path: Path, entries: Sequence[ProfileEntry]) -> dict[str, object]:
    """Load a prior run only when its seal and completed-profile prefix agree."""

    raw = cast(dict[str, object], json.loads(result_path.read_text(encoding="utf-8")))
    supplied_digest = raw.get("RESULT_PAYLOAD_SHA256")
    payload = {key: value for key, value in raw.items() if key != "RESULT_PAYLOAD_SHA256"}
    if supplied_digest != _canonical_payload_sha256(payload):
        raise ValueError(f"checkpoint payload digest mismatch: {result_path}")
    if raw.get("TASK_ID") != TASK_ID:
        raise ValueError(f"checkpoint task identity mismatch: {result_path}")
    raw_records = raw.get("PROFILE_RESULTS")
    if not isinstance(raw_records, list):
        raise ValueError(f"checkpoint profile ledger is invalid: {result_path}")
    records = cast(list[object], raw_records)
    if len(records) > len(entries):
        raise ValueError(f"checkpoint profile ledger is invalid: {result_path}")
    for index, raw_record in enumerate(records):
        if not isinstance(raw_record, dict):
            raise ValueError(f"checkpoint profile row {index} is invalid: {result_path}")
        record = cast(dict[str, object], raw_record)
        expected_mass, expected_profile = entries[index]
        if record.get("MASS") != expected_mass or record.get("PROFILE") != list(expected_profile):
            raise ValueError(f"checkpoint is not the exact ordered profile prefix: {result_path}")
    return raw


def _summary_payload(
    *,
    records: list[dict[str, object]],
    entries: Sequence[ProfileEntry],
    next_index: int,
    status: str,
    cpu_seconds_used: float,
    prior_profile_check: dict[str, object],
) -> dict[str, object]:
    closed = [record for record in records if record.get("PROFILE_STATUS") == "CLOSED_BY_EXACT_U3"]
    survivors = [record for record in records if record.get("PROFILE_STATUS") == "SURVIVES_U3"]
    first_survivor = survivors[0] if survivors else None
    exact_scores: list[dict[str, object]] = []
    if first_survivor is not None:
        raw_scores = first_survivor.get("EXACT_SCORE_RESULTS", [])
        if isinstance(raw_scores, list):
            for raw_score in cast(list[object], raw_scores):
                if isinstance(raw_score, dict):
                    exact_scores.append(cast(dict[str, object], raw_score))
    exact_values: list[int] = []
    for score in exact_scores:
        score_value = score.get("official_any_prize_outcome_count")
        if isinstance(score_value, int):
            exact_values.append(score_value)
    global_status = "PROVEN" if status == "ALL_REMAINING_PROFILES_CLOSED" else "UNKNOWN"
    next_profile = list(entries[next_index][1]) if next_index < len(entries) else None
    if first_survivor is not None or status == "ALL_REMAINING_PROFILES_CLOSED":
        next_profile = None
    payload: dict[str, object] = {
        "TASK_ID": TASK_ID,
        "INCUMBENT_COUNT": INCUMBENT_COUNT,
        "TOTAL_REMAINING_PROFILE_COUNT": len(entries),
        "PROFILES_COMPLETED_THIS_RUN": len(records),
        "FIRST_MASS_PROCESSED": entries[0][0] if entries else None,
        "LAST_MASS_COMPLETED": records[-1].get("MASS") if records else None,
        "NEWLY_CLOSED_PROFILE_COUNT": len(closed),
        "SURVIVING_PROFILE_COUNT": len(survivors),
        "FIRST_SURVIVING_MASS": (
            first_survivor.get("MASS") if first_survivor is not None else None
        ),
        "FIRST_SURVIVING_PROFILE": (
            first_survivor.get("PROFILE") if first_survivor is not None else None
        ),
        "MAX_LEGAL_U3": (
            first_survivor.get("MAX_LEGAL_U3") if first_survivor is not None else None
        ),
        "GAP_VS_INCUMBENT": (
            first_survivor.get("GAP_VS_INCUMBENT") if first_survivor is not None else None
        ),
        "EXACT_WITNESS_BEST": max(exact_values) if exact_values else None,
        "K10_GLOBAL_OPTIMUM_STATUS": global_status,
        "RESULT_STATUS": status,
        "NEXT_UNRESOLVED_PROFILE": next_profile,
        "TOTAL_CPU_CAP_SECONDS": TOTAL_CPU_CAP_SECONDS,
        "TOTAL_CPU_SECONDS_USED": round(cpu_seconds_used, 3),
        "PRIOR_MASS11_20_PROFILE_SET_CHECK": prior_profile_check,
        "PROFILE_RESULTS": records,
    }
    return payload


def _exact_score_all_maximizers(outcome: ProfileResult) -> ProfileResult:
    """Exact-score every surviving maximizer when the requested cap permits."""

    witness_count = len(outcome.maximizing_systems)
    if outcome.status != "SURVIVES_U3" or witness_count > MAX_EXACT_SCORE_WITNESSES:
        return outcome
    if len(outcome.exact_scores) == witness_count:
        return outcome
    draws = all_main_draw_masks(POOL_SIZE, DRAW_SIZE)
    exact_scores: list[dict[str, object]] = []
    best_exact_count: int | None = None
    for system in outcome.maximizing_systems:
        score = evaluate_portfolio(
            reconstruct_portfolio(system, outcome.spec), draws=draws
        ).official_any_prize_outcome_count
        if score > outcome.max_legal_u3:
            raise ValueError("exact score exceeded its third-order Bonferroni upper bound")
        best_exact_count = score if best_exact_count is None else max(best_exact_count, score)
        exact_scores.append(
            {"class_id": system.class_id, "official_any_prize_outcome_count": score}
        )
    return replace(
        outcome,
        exact_scores=tuple(exact_scores),
        best_exact_count=best_exact_count,
    )


def _cpu_cap_handler(_signum: int, _frame: FrameType | None) -> None:
    raise CpuCapReached("18-hour CPU limit reached")


def _install_cpu_cap(remaining_seconds: float) -> int:
    """Apply the remaining CPU budget, reserving its tail for checkpoint cleanup."""

    if not hasattr(resource, "RLIMIT_CPU") or not hasattr(signal, "SIGXCPU"):
        raise RuntimeError("this platform cannot enforce the requested CPU cap")
    soft_limit, hard_limit = resource.getrlimit(resource.RLIMIT_CPU)
    requested = max(1, int(remaining_seconds))
    finite_limits = [limit for limit in (soft_limit, hard_limit) if limit != resource.RLIM_INFINITY]
    total_cap = min((requested, *finite_limits)) if finite_limits else requested
    cleanup_reserve = min(CPU_LIMIT_CLEANUP_GRACE_SECONDS, max(0, total_cap - 1))
    soft_effective = total_cap - cleanup_reserve
    signal.signal(signal.SIGXCPU, _cpu_cap_handler)
    resource.setrlimit(resource.RLIMIT_CPU, (soft_effective, total_cap))
    return total_cap


def run_sequential_census(
    *, result_path: Path = RESULT_PATH, progress: bool = True
) -> dict[str, object]:
    """Process profiles serially, atomically checkpointing each completed one."""

    all_profiles = derive_full_support_profiles()
    prior_profile_check = validate_prior_closed_profile_sets(all_profiles)
    entries = tuple(entry for entry in all_profiles if entry[0] >= 21)
    specs = build_remaining_profile_specs()
    specified_entries_list: list[ProfileEntry] = []
    for spec in specs:
        overlap_mass = profile_arithmetic(spec)["overlap_mass"]
        if not isinstance(overlap_mass, int):
            raise ValueError(f"{spec.name}: overlap mass arithmetic is not an integer")
        specified_entries_list.append((overlap_mass, spec.profile))
    specified_entries = tuple(specified_entries_list)
    if entries != specified_entries:
        raise ValueError("profile derivation and support specifications differ")

    records: list[dict[str, object]] = []
    prior_cpu_seconds = 0.0
    if result_path.exists():
        loaded = _load_checkpoint(result_path, entries)
        raw_records = loaded.get("PROFILE_RESULTS")
        if not isinstance(raw_records, list):
            raise ValueError("checkpoint has no profile ledger")
        records = cast(list[dict[str, object]], raw_records)
        prior_cpu = loaded.get("TOTAL_CPU_SECONDS_USED", 0.0)
        if isinstance(prior_cpu, (int, float)):
            prior_cpu_seconds = float(prior_cpu)
        if loaded.get("RESULT_STATUS") in {
            "RESOURCE_CAP_INCOMPLETE",
            "SURVIVOR_FOUND",
            "ALL_REMAINING_PROFILES_CLOSED",
        }:
            return loaded

    next_index = len(records)
    cpu_limit = TOTAL_CPU_CAP_SECONDS - prior_cpu_seconds
    if cpu_limit <= 0:
        payload = _summary_payload(
            records=records,
            entries=entries,
            next_index=next_index,
            status="RESOURCE_CAP_INCOMPLETE",
            cpu_seconds_used=prior_cpu_seconds,
            prior_profile_check=prior_profile_check,
        )
        return _write_checkpoint(payload, result_path)

    effective_cpu_limit = _install_cpu_cap(cpu_limit)
    process_start = time.process_time()
    initial_status = "RUNNING" if next_index < len(entries) else "ALL_REMAINING_PROFILES_CLOSED"
    initial = _summary_payload(
        records=records,
        entries=entries,
        next_index=next_index,
        status=initial_status,
        cpu_seconds_used=prior_cpu_seconds,
        prior_profile_check=prior_profile_check,
    )
    initial["ACTIVE_PROCESS_CPU_LIMIT_SECONDS"] = effective_cpu_limit
    _write_checkpoint(initial, result_path)

    for index in range(next_index, len(entries)):
        mass, profile = entries[index]
        spec = specs[index]
        try:
            _log(f"START {spec.name} MASS={mass} PROFILE={profile}")
            outcome = build_profile_result(spec, progress=progress)
            outcome = _exact_score_all_maximizers(outcome)
            row = outcome.as_record()
            row["MASS"] = mass
            row["PROFILE_NAME"] = spec.name
            row["PROFILE"] = list(profile)
            row["MAXIMIZING_WITNESS_COUNT"] = len(outcome.maximizing_systems)
            records.append(row)
            has_survivor = outcome.status == "SURVIVES_U3"
            next_index = index + 1
            if has_survivor:
                status = "SURVIVOR_FOUND"
            else:
                status = (
                    "ALL_REMAINING_PROFILES_CLOSED" if next_index == len(entries) else "RUNNING"
                )
            used = prior_cpu_seconds + time.process_time() - process_start
            payload = _summary_payload(
                records=records,
                entries=entries,
                next_index=next_index,
                status=status,
                cpu_seconds_used=used,
                prior_profile_check=prior_profile_check,
            )
            sealed = _write_checkpoint(payload, result_path)
            _log(
                f"COMPLETE {spec.name} PAIR_GRAPH_CLASS_COUNT={outcome.pair_graph_class_count} "
                f"LEGAL_SUPPORT_CLASS_COUNT={outcome.legal_class_count} "
                f"MAX_LEGAL_U3={outcome.max_legal_u3} GAP_VS_INCUMBENT={outcome.gap} "
                f"PROFILE_STATUS={outcome.status}"
            )
        except CpuCapReached:
            signal.signal(signal.SIGXCPU, signal.SIG_IGN)
            used = prior_cpu_seconds + time.process_time() - process_start
            current_profile_completed = bool(
                records and records[-1].get("PROFILE") == list(profile)
            )
            payload = _summary_payload(
                records=records,
                entries=entries,
                next_index=index + 1 if current_profile_completed else index,
                status="RESOURCE_CAP_INCOMPLETE",
                cpu_seconds_used=used,
                prior_profile_check=prior_profile_check,
            )
            sealed = _write_checkpoint(payload, result_path)
            _log(f"RESOURCE_CAP_INCOMPLETE NEXT_PROFILE={profile}")
            return sealed
        if has_survivor or status == "ALL_REMAINING_PROFILES_CLOSED":
            return sealed

    raise AssertionError("sequential census exited without a terminal condition")


def main(argv: Sequence[str] | None = None) -> None:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments:
        raise SystemExit(f"unknown arguments: {' '.join(arguments)}")
    nice_level = os.getpriority(os.PRIO_PROCESS, 0)
    if nice_level < 15:
        raise SystemExit(f"process nice level must be at least 15; observed {nice_level}")
    result = run_sequential_census()
    summary = {
        key: result.get(key)
        for key in (
            "RESULT_STATUS",
            "TOTAL_REMAINING_PROFILE_COUNT",
            "PROFILES_COMPLETED_THIS_RUN",
            "FIRST_MASS_PROCESSED",
            "LAST_MASS_COMPLETED",
            "NEWLY_CLOSED_PROFILE_COUNT",
            "SURVIVING_PROFILE_COUNT",
            "FIRST_SURVIVING_MASS",
            "FIRST_SURVIVING_PROFILE",
            "MAX_LEGAL_U3",
            "GAP_VS_INCUMBENT",
            "EXACT_WITNESS_BEST",
            "K10_GLOBAL_OPTIMUM_STATUS",
            "RESULT_PAYLOAD_SHA256",
        )
    }
    summary["RESULT_FILE"] = str(RESULT_PATH)
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
