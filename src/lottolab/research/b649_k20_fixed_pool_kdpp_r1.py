"""One bounded fixed-pool k-DPP study; diversity is not official win probability.

NumPy port of DPPy v0.3.3, commit 0d34dd67deedfed1d66f555636067f8fb2b0aab7,
exact_sampling.py: elementary_symmetric_polynomials, k_dpp_eig_vecs_selector,
and proj_dpp_sampler_eig_GS. Theory: Kulesza/Taskar arXiv:1207.6083v4, §5.
The port uses numpy.linalg.eigh rather than SciPy. It retains the ESP recurrence,
backward selection order, RandomState stream, and GS residual recursion, including
the source's abs(residual)/(rank-it) probability. Added full-matrix, rank,
probability and output checks fail closed; there is no clipping, retry or fallback.
Cross-platform or DPPy/SciPy bitwise agreement is not claimed.

DPPy MIT License, Copyright (c) 2017 CRIStAL-PADR:
Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from fractions import Fraction
from pathlib import Path
from typing import Any, cast

import numpy as np
import numpy.typing as npt

from lottolab.research.b649_k20_bonferroni_filtered_exhaustive_2ticket_cross_swap_r1 import (
    full_u3_components,
)
from lottolab.research.b649_official_any_prize_engine import (
    DrawMasks,
    all_main_draw_masks,
    evaluate_portfolio_with_diagnostics,
)

type FloatArray = npt.NDArray[np.float64]
type Portfolio = tuple[tuple[int, ...], ...]
type Json = dict[str, Any]

TASK_ID = "NUMBER2_B_K20_FIXED_POOL_KDPP_R1"
ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = Path("/Users/kelvin/VibeCoding-WorkSpace/.task-data") / TASK_ID
PIN = "032ce592c3efd0ac4b5b82a813d157224419c794"
POOL_SHA = "d4c4c026df15fe032599bcadf7b029f644a79f95ce96b9ff25a6d93750ae38b4"
INCUMBENT_SHA = "eaed652900d101881b678a1515d2a366bff9de6723dbec2ec9c82fe0d0d7844c"
REFERENCE = 313_263_888
OUTCOMES = 601_304_088
K = 20
EPSILON = 1e-6
SEED = 20261022
LIMIT = 4
BACKEND_ID = "NUMPY_SPECTRAL_KDPP_GS_R1"
SOURCE_DIRECTORY = "docs/research/matrix-native-results/"
SOURCES = (
    (
        "V5",
        "b649-k20-cross-swap-champion-r1.json",
        "TERMINAL_TICKETS",
        "f28280cb66850a04e7b58cc31c71330b10dc04d4",
    ),
    (
        "V6",
        "b649-k20-exact-two-ticket-joint-replacement-terminal-r1.json",
        "TICKETS",
        "8188e3313a8b4e8f85e5a10a1b28baadc27d478a",
    ),
    (
        "V7",
        "b649-k20-12-8-winner-two-ticket-ascent-r1-result.json",
        "FINAL_TICKETS",
        "404e35563564a40bdd228dafa25fdf5b82e45812",
    ),
)
DEPENDENCIES = {
    "b649_k20_bonferroni_filtered_exhaustive_2ticket_cross_swap_r1.py": (
        "75bd253b438f16571cec076cce89681c2aa5b157"
    ),
    "b649_official_any_prize_exact.py": "1e46d228b39026dd6d2f7b2bdcd00094ab0c24c3",
}


def now() -> str:
    return datetime.now(UTC).isoformat()


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git_blob(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def canonicalize(raw: Sequence[Sequence[int]], expected: int | None = None) -> Portfolio:
    if expected is not None and len(raw) != expected:
        raise ValueError("wrong ticket count")
    tickets: list[tuple[int, ...]] = []
    for ticket in raw:
        if (
            len(ticket) != 6
            or any(type(n) is not int or not 1 <= n <= 49 for n in ticket)
            or len(set(ticket)) != 6
        ):
            raise ValueError("illegal six-number ticket")
        tickets.append(tuple(sorted(ticket)))
    if len(set(tickets)) != len(tickets):
        raise ValueError("duplicate ticket")
    return tuple(sorted(tickets))


def canonical_bytes(portfolio: Portfolio) -> bytes:
    return json.dumps(portfolio, separators=(",", ":"), ensure_ascii=True).encode("ascii")


@dataclass(frozen=True)
class FixedPool:
    tickets: Portfolio
    sources: dict[str, Portfolio]
    manifest: Json


def load_fixed_pool(repository: Path = ROOT) -> FixedPool:
    sources: dict[str, Portfolio] = {}
    manifest: Json = {"commit": PIN, "sources": {}}
    for name, filename, field, expected_blob in SOURCES:
        path = SOURCE_DIRECTORY + filename
        data = subprocess.check_output(["git", "show", f"{PIN}:{path}"], cwd=repository)
        if git_blob(data) != expected_blob:
            raise ValueError(f"fixed Git blob mismatch: {name}")
        document = cast(Json, json.loads(data))
        source = canonicalize(cast(Sequence[Sequence[int]], document[field]), K)
        sources[name] = source
        manifest["sources"][name] = {
            "path": path,
            "field": field,
            "git_blob": expected_blob,
            "canonical_sha256": digest(canonical_bytes(source)),
            "ticket_count": len(source),
        }
        if name == "V7" and document["FINAL_COUNT"] != REFERENCE:
            raise ValueError("V7 FINAL_COUNT differs from reference")
    pool = tuple(sorted({ticket for source in sources.values() for ticket in source}))
    intersections = {
        "V5_V6": len(set(sources["V5"]) & set(sources["V6"])),
        "V5_V7": len(set(sources["V5"]) & set(sources["V7"])),
        "V6_V7": len(set(sources["V6"]) & set(sources["V7"])),
    }
    if intersections != {"V5_V6": 14, "V5_V7": 0, "V6_V7": 0}:
        raise ValueError("source intersections differ")
    data = canonical_bytes(pool)
    if len(pool) != 46 or len(data) != 867 or digest(data) != POOL_SHA:
        raise ValueError("fixed canonical pool mismatch")
    if digest(canonical_bytes(sources["V7"])) != INCUMBENT_SHA:
        raise ValueError("incumbent identity differs")
    manifest.update(
        pool_sha256=POOL_SHA,
        pool_bytes=len(data),
        pool_size=46,
        intersections=intersections,
        source_positions=60,
    )
    return FixedPool(pool, sources, manifest)


def fixed_kernel(pool: Portfolio) -> FloatArray:
    canonicalize(pool, 46)
    x = np.zeros((46, 49), dtype=np.float64)
    for i, ticket in enumerate(pool):
        x[i, np.asarray(ticket, dtype=np.int64) - 1] = 1 / np.sqrt(6.0)
    return x @ x.T + EPSILON * np.eye(46, dtype=np.float64)


def elementary_symmetric_polynomials(values: FloatArray, k: int) -> FloatArray:
    e = np.zeros((k + 1, len(values) + 1), dtype=np.float64)
    e[0, :] = 1
    for degree in range(1, k + 1):
        for n in range(1, len(values) + 1):
            e[degree, n] = e[degree, n - 1] + values[n - 1] * e[degree - 1, n - 1]
    if not np.all(np.isfinite(e)) or e[k, -1] <= 0:
        raise ValueError("nonfinite or zero ESP normalizer")
    return e


@dataclass(frozen=True)
class SpectralKDPP:
    values: FloatArray
    vectors: FloatArray
    esp: FloatArray
    k: int
    diagnostics: Json


def prepare_kernel(kernel: FloatArray, k: int) -> SpectralKDPP:
    if (
        kernel.dtype != np.float64
        or kernel.ndim != 2
        or kernel.shape[0] != kernel.shape[1]
        or not 1 <= k <= kernel.shape[0]
    ):
        raise ValueError("kernel must be square float64 with 1<=k<=N")
    if not np.all(np.isfinite(kernel)):
        raise ValueError("nonfinite kernel")
    symmetry_error = float(np.max(np.abs(kernel - kernel.T)))
    if symmetry_error > 1e-12:
        raise ValueError("asymmetric kernel")
    values, vectors = np.linalg.eigh(kernel)
    if not np.all(np.isfinite(values)) or not np.all(np.isfinite(vectors)):
        raise ValueError("nonfinite eigendecomposition")
    if np.any(values <= 0):
        raise ValueError("kernel not strictly positive definite")
    tau = float(values[-1] * len(values) * np.finfo(float).eps)
    rank = int(np.count_nonzero(values > tau))
    if rank < k:
        raise ValueError("numerical rank below k")
    e = elementary_symmetric_polynomials(values, k)
    return SpectralKDPP(
        values,
        vectors,
        e,
        k,
        {
            "dtype": "float64",
            "shape": list(kernel.shape),
            "all_finite": True,
            "max_symmetry_error": symmetry_error,
            "eigenvalue_min": float(values[0]),
            "eigenvalue_max": float(values[-1]),
            "numerical_rank": rank,
            "rank_threshold": tau,
            "condition_number": float(values[-1] / values[0]),
            "esp_normalizer": float(e[k, -1]),
        },
    )


def select_eigenvectors(prepared: SpectralKDPP, rng: np.random.RandomState) -> FloatArray:
    left = prepared.k
    selected = np.zeros(left, dtype=np.int64)
    for n in range(len(prepared.values), 0, -1):
        denominator = float(prepared.esp[left, n])
        if not np.isfinite(denominator) or denominator <= 0:
            raise ValueError("illegal eigenvector-selection denominator")
        probability = float(prepared.values[n - 1] * prepared.esp[left - 1, n - 1] / denominator)
        if not np.isfinite(probability) or not 0 <= probability <= 1:
            raise ValueError("illegal eigenvector-selection probability")
        if rng.rand() < probability:
            left -= 1
            selected[left] = n - 1
            if left == 0:
                break
    if left != 0:
        raise ValueError("eigenvector selection did not fill fixed k")
    return prepared.vectors[:, selected]


def sample_kdpp(prepared: SpectralKDPP, rng: object) -> list[int]:
    if not isinstance(rng, np.random.RandomState):
        raise TypeError("RandomState instance required")
    vectors = select_eigenvectors(prepared, rng)
    n, rank = vectors.shape
    available = np.ones(n, dtype=np.bool_)
    ground = np.arange(n, dtype=np.int64)
    c = np.zeros((n, rank), dtype=np.float64)
    norms = np.einsum("ij,ij->i", vectors, vectors)
    sample: list[int] = []
    for iteration in range(rank):
        residuals = norms[available]
        # DPPy's abs is retained, but material negative residuals are rejected.
        if not np.all(np.isfinite(residuals)) or np.any(residuals < -1e-12):
            raise ValueError("illegal GS residual")
        probabilities = np.abs(residuals) / (rank - iteration)
        if (
            not np.all(np.isfinite(probabilities))
            or np.any(probabilities > 1 + 1e-12)
            or abs(float(probabilities.sum()) - 1) > 1e-8
        ):
            raise ValueError("illegal projection probability")
        chosen = int(rng.choice(ground[available], p=probabilities))
        sample.append(chosen)
        if iteration == rank - 1:
            break
        if norms[chosen] <= 0:
            raise ValueError("nonpositive GS pivot")
        available[chosen] = False
        c[available, iteration] = (
            vectors[available, :] @ vectors[chosen, :]
            - c[available, :iteration] @ c[chosen, :iteration]
        ) / np.sqrt(norms[chosen])
        norms[available] -= c[available, iteration] ** 2
    if len(sample) != prepared.k or len(set(sample)) != prepared.k:
        raise ValueError("sample size or uniqueness failure")
    return sample


def serialize_rng(rng: np.random.RandomState) -> Json:
    algorithm, keys, position, has_gauss, cached_gaussian = rng.get_state()
    return {
        "algorithm": algorithm,
        "keys": keys.tolist(),
        "position": position,
        "has_gauss": has_gauss,
        "cached_gaussian": cached_gaussian,
    }


def restore_rng(state: Json | None) -> np.random.RandomState:
    rng = np.random.RandomState(SEED)
    if state is not None:
        rng.set_state(
            (
                state["algorithm"],
                np.asarray(state["keys"], dtype=np.uint32),
                state["position"],
                state["has_gauss"],
                state["cached_gaussian"],
            )
        )
    return rng


def write_json(path: Path, document: Json) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w") as stream:
        json.dump(document, stream, ensure_ascii=True, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


class IncompleteCall(RuntimeError):
    """A reserved attempt cannot be replayed when its completion is uncertain."""


def validate_receipt(result: Json, candidates: Json) -> None:
    raw_calls = cast(list[Json], result.get("raw_calls", []))
    exact_calls = cast(list[Json], result.get("exact_calls", []))
    if len(raw_calls) > LIMIT or len(exact_calls) > LIMIT:
        raise IncompleteCall("attempt budget exceeded")
    for call in [*raw_calls, *exact_calls]:
        if call["status"] != "COMPLETE":
            raise IncompleteCall("reserved call has uncertain completion; replay forbidden")
    if result.get("RAW_DRAW_ATTEMPTS", 0) != len(raw_calls):
        raise IncompleteCall("raw receipt counter mismatch")
    if result.get("FORMAL_EXACT_ATTEMPTS", 0) != len(exact_calls):
        raise IncompleteCall("Exact receipt counter mismatch")
    if result.get("RAW_DRAW_COMPLETED", 0) != len(raw_calls):
        raise IncompleteCall("raw completion counter mismatch")
    if result.get("FORMAL_EXACT_COMPLETED", 0) != len(exact_calls):
        raise IncompleteCall("Exact completion counter mismatch")
    if len(candidates.get("raw_records", [])) != len(raw_calls):
        raise IncompleteCall("raw receipt/candidate mismatch")
    for ordinal, (call, record) in enumerate(
        zip(raw_calls, candidates.get("raw_records", []), strict=True), start=1
    ):
        if (
            call["ordinal"] != ordinal
            or record["ordinal"] != ordinal
            or call["sha256"] != record["sha256"]
        ):
            raise IncompleteCall("raw call identity mismatch")
        portfolio = canonicalize(record["tickets"], K)
        if digest(canonical_bytes(portfolio)) != record["sha256"]:
            raise IncompleteCall("saved portfolio identity mismatch")
    completed = {
        record["sha256"]
        for record in candidates.get("raw_records", [])
        if record.get("exact_count") is not None
    }
    if {call["sha256"] for call in exact_calls} != completed:
        raise IncompleteCall("Exact receipt/candidate mismatch")
    if len({call["sha256"] for call in exact_calls}) != len(exact_calls):
        raise IncompleteCall("duplicate Exact attempt")


def snapshot_receipt(directory: Path) -> None:
    data = (directory / "result.json").read_bytes()
    number = 1
    while (directory / f"result.before_{number}.json").exists():
        number += 1
    (directory / f"result.before_{number}.json").write_bytes(data)


def run_bounded(
    directory: Path,
    pool: FixedPool,
    sampler: Callable[[np.random.RandomState], list[int]],
    u3_counter: Callable[[Portfolio], tuple[int, int, int]],
    scorer: Callable[[Portfolio], tuple[int, Json]],
    *,
    snapshot: bool = True,
) -> Json:
    """Fixed four attempts, durable reservations, then U3 and one Exact per survivor.

    Injection is for isolated synthetic/mock tests; the production CLI fixes all
    callbacks, source, output path, parameters and seed.
    """
    result = cast(Json, json.loads((directory / "result.json").read_text()))
    candidate_path = directory / "candidates.json"
    candidates: Json = (
        cast(Json, json.loads(candidate_path.read_text()))
        if candidate_path.exists()
        else {"source_manifest": pool.manifest, "raw_records": []}
    )
    if snapshot:
        snapshot_receipt(directory)
    validate_receipt(result, candidates)
    if result.get("phase") == "RESEARCH_COMPLETE":
        return result
    records = cast(list[Json], candidates["raw_records"])
    rng = restore_rng(cast(Json | None, result.get("rng_state")))
    if records and result.get("rng_state") is None:
        raise IncompleteCall("missing continuation RNG state")
    write_json(candidate_path, candidates)
    for ordinal in range(len(records) + 1, LIMIT + 1):
        result["phase"] = "RAW_SAMPLING"
        call = {"ordinal": ordinal, "status": "IN_PROGRESS", "reserved_at": now()}
        result["raw_calls"].append(call)
        result["RAW_DRAW_ATTEMPTS"] = len(result["raw_calls"])
        write_json(directory / "result.json", result)
        indices = sampler(rng)
        if (
            len(indices) != K
            or len(set(indices)) != K
            or any(type(i) is not int or not 0 <= i < len(pool.tickets) for i in indices)
        ):
            raise ValueError("invalid formal raw indices")
        portfolio = canonicalize(tuple(pool.tickets[i] for i in indices), K)
        records.append(
            {
                "ordinal": ordinal,
                "raw_indices": indices,
                "tickets": portfolio,
                "sha256": digest(canonical_bytes(portfolio)),
                "status": "RAW_COMPLETE",
                "s1": None,
                "s2": None,
                "s3": None,
                "u3": None,
                "exact_count": None,
                "exact_fraction": None,
                "delta_win7": None,
                "strict_gain": None,
                "diagnostics": None,
            }
        )
        write_json(candidate_path, candidates)
        call.update(status="COMPLETE", completed_at=now(), sha256=records[-1]["sha256"])
        result["RAW_DRAW_COMPLETED"] = len(records)
        result["rng_state"] = serialize_rng(rng)
        write_json(directory / "result.json", result)
    print("RAW4_PERSISTED", flush=True)
    existing = {digest(canonical_bytes(source)) for source in pool.sources.values()}
    seen: set[str] = set()
    for record in records:
        sha = cast(str, record["sha256"])
        if sha in existing:
            record["status"] = "EXCLUDED_EXISTING"
        elif sha in seen:
            record["status"] = "DUPLICATE"
        else:
            seen.add(sha)
            if record["u3"] is None:
                s1, s2, s3 = u3_counter(canonicalize(record["tickets"], K))
                if any(type(s) is not int for s in (s1, s2, s3)):
                    raise ValueError("U3 components must be Python integers")
                record.update(s1=s1, s2=s2, s3=s3, u3=s1 - s2 + s3)
            if record["exact_count"] is not None:
                record["status"] = "EXACT_COMPLETE"
            else:
                record["status"] = (
                    "SAFE_PRUNED" if cast(int, record["u3"]) <= REFERENCE else "U3_SURVIVOR"
                )
        write_json(candidate_path, candidates)
    result["phase"] = "U3_COMPLETE"
    write_json(directory / "result.json", result)
    print("U3_COMPLETE " + json.dumps([r["u3"] for r in records]), flush=True)
    for record in records:
        if record["status"] != "U3_SURVIVOR":
            continue
        if len(result["exact_calls"]) >= LIMIT:
            raise IncompleteCall("Exact attempt budget exhausted")
        call = {
            "sha256": record["sha256"],
            "ordinal": record["ordinal"],
            "status": "IN_PROGRESS",
            "reserved_at": now(),
        }
        result["exact_calls"].append(call)
        result["FORMAL_EXACT_ATTEMPTS"] = len(result["exact_calls"])
        result["phase"] = "EXACT_SCORING"
        write_json(directory / "result.json", result)
        count, diagnostics = scorer(canonicalize(record["tickets"], K))
        if type(count) is not int or not 0 <= count <= min(record["u3"], OUTCOMES):
            raise ValueError("Exact count outside U3/outcome bounds")
        if (
            diagnostics.get("actual_engine") != "enumeration"
            or diagnostics.get("fallback_reason") is not None
        ):
            raise ValueError("Exact engine contract violated")
        record.update(
            status="EXACT_COMPLETE",
            exact_count=count,
            exact_fraction=str(Fraction(count, OUTCOMES)),
            delta_win7=count - REFERENCE,
            strict_gain=count > REFERENCE,
            diagnostics=diagnostics,
        )
        write_json(candidate_path, candidates)
        call.update(status="COMPLETE", completed_at=now(), exact_count=count)
        result["FORMAL_EXACT_COMPLETED"] = len(result["exact_calls"])
        write_json(directory / "result.json", result)
        print(
            f"EXACT_COMPLETE raw={record['ordinal']} WIN7={count} delta={count - REFERENCE}",
            flush=True,
        )
    result.update(
        phase="RESEARCH_COMPLETE",
        EXCLUDED_EXISTING_COUNT=sum(r["status"] == "EXCLUDED_EXISTING" for r in records),
        DUPLICATE_COUNT=sum(r["status"] == "DUPLICATE" for r in records),
        DISTINCT_NEW_CANDIDATE_COUNT=len(seen),
        U3_PRUNED_COUNT=sum(r["status"] == "SAFE_PRUNED" for r in records),
    )
    scored = [r for r in records if r["exact_count"] is not None]
    best = max(scored, key=lambda r: r["exact_count"]) if scored else None
    result["BEST_NEW_CANDIDATE"] = best
    result["K20_GAIN_ESTABLISHED"] = "YES" if best and best["strict_gain"] else "NO"
    result["BEST_OVERALL"] = (
        best
        if best and best["strict_gain"]
        else {
            "identity": "V7",
            "sha256": INCUMBENT_SHA,
            "exact_count": REFERENCE,
            "tickets": pool.sources["V7"],
            "delta_win7": 0,
        }
    )
    result["raw_records"] = records
    write_json(directory / "result.json", result)
    return result


def environment_manifest() -> Json:
    return {
        "python": sys.version,
        "executable": sys.executable,
        "numpy": np.__version__,
        "platform": platform.platform(),
        "architecture": platform.machine(),
        "numpy_configuration": np.show_config(mode="dicts"),
        "thread_environment": {
            name: os.environ.get(name)
            for name in (
                "OMP_NUM_THREADS",
                "MKL_NUM_THREADS",
                "OPENBLAS_NUM_THREADS",
                "NUMEXPR_NUM_THREADS",
            )
        },
        "uv_lock_sha256": digest((ROOT / "uv.lock").read_bytes()),
    }


def main() -> None:
    if len(sys.argv) != 1:
        raise ValueError("fixed study accepts no tuning or output arguments")
    result_path = EVIDENCE / "result.json"
    if not result_path.exists() or not (EVIDENCE / "packet.md").exists():
        raise ValueError("Packet and initial receipt required")
    manifest = environment_manifest()
    for value in manifest["thread_environment"].values():
        if value != "1":
            raise ValueError("all four BLAS/OpenMP thread limits must equal 1")
    for filename, expected in DEPENDENCIES.items():
        if git_blob((Path(__file__).parent / filename).read_bytes()) != expected:
            raise ValueError(f"dependency blob mismatch: {filename}")
    result = cast(Json, json.loads(result_path.read_text()))
    snapshot_receipt(EVIDENCE)
    prior_candidates = EVIDENCE / "candidates.json"
    validate_receipt(
        result,
        cast(Json, json.loads(prior_candidates.read_text()))
        if prior_candidates.exists()
        else {"raw_records": []},
    )
    code_sha = digest(Path(__file__).read_bytes())
    identity = {
        "implementation_sha256": code_sha,
        "environment": manifest,
        "packet_sha256": digest((EVIDENCE / "packet.md").read_bytes()),
    }
    if result.get("run_identity") not in (None, identity):
        raise IncompleteCall("runtime/source identity changed; continuation refused")
    result.update(
        run_identity=identity,
        TASK_STATUS="IN_PROGRESS",
        ACTUAL_MODEL="GPT-6 family; exact ID unknown",
        IMPLEMENTATION_DEPTH="NORMAL",
        DEPTH_SOURCE="PLANNER_SUPPLIED",
        BACKEND_ID=BACKEND_ID,
        IMPLEMENTATION_SHA256=code_sha,
        PYTHON_AND_NUMPY_VERSIONS=manifest,
        SOURCE_POOL_SHA256=POOL_SHA,
        POOL_SIZE=46,
        REFERENCE_WIN7=REFERENCE,
        PERSISTENT_EVIDENCE_ROOT=str(EVIDENCE),
        PROJECT_BACKTEST="NOT RUN",
        PACKAGE_INSTALLATIONS="NONE",
        COMMIT_PUSH_MERGE="NOT AUTHORIZED",
        RNG_CONTRACT={
            "seed": SEED,
            "type": "RandomState",
            "stream": "single serial instance",
            "raw_limit": LIMIT,
            "exact_limit": LIMIT,
            "refill": False,
        },
        parameters={"N": 46, "K": K, "epsilon": EPSILON, "dtype": "float64"},
        ACTUAL_HEAD_AND_SOURCE_IDENTITIES={
            "head": subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
            ).strip(),
            "tree": subprocess.check_output(
                ["git", "rev-parse", "HEAD^{tree}"], cwd=ROOT, text=True
            ).strip(),
            "dependency_blobs": DEPENDENCIES,
        },
    )
    write_json(result_path, result)
    pool = load_fixed_pool()
    prepared = prepare_kernel(fixed_kernel(pool.tickets), K)
    result.update(NUMERICAL_DIAGNOSTICS=prepared.diagnostics, source_manifest=pool.manifest)
    write_json(result_path, result)
    draws: DrawMasks | None = None

    def u3_counter(portfolio: Portfolio) -> tuple[int, int, int]:
        components = full_u3_components(portfolio)
        return components.s1, components.s2, components.s3

    def scorer(portfolio: Portfolio) -> tuple[int, Json]:
        nonlocal draws
        if draws is None:
            draws = all_main_draw_masks(49, 6)
            draws.flags.writeable = False
        evaluation = evaluate_portfolio_with_diagnostics(
            portfolio,
            pool_size=49,
            draw_size=6,
            outright_matches=3,
            engine="enumeration",
            draws=draws,
        )
        return (
            evaluation.probability.official_any_prize_outcome_count,
            asdict(evaluation.diagnostics),
        )

    try:
        run_bounded(
            EVIDENCE,
            pool,
            lambda rng: sample_kdpp(prepared, rng),
            u3_counter,
            scorer,
            snapshot=False,
        )
    except Exception as error:
        failed = cast(Json, json.loads(result_path.read_text()))
        failed.update(
            TASK_STATUS="BLOCKED",
            current_blocker=repr(error),
            unblock_condition="Resolve the recorded cause without replaying uncertain calls",
            EXACT_REMAINING_WORK="See reserved calls and phase; no automatic retry",
        )
        write_json(result_path, failed)
        raise


if __name__ == "__main__":
    main()
