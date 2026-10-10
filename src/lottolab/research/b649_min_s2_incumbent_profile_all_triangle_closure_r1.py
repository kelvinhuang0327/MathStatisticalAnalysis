"""Profile-level closure of the incumbent min-S2 profile 55555555555511111100 over every T.

Claim. Every minimum-S2 fiber portfolio with triple-degree profile 55555555555511111100 has
an official any-prize count of at most 313,263,888, the current incumbent. Such a portfolio
has 20 tickets of six labels and pair overlaps of at most one. Its 22 triple labels and 27
pair labels cover 1..49, its overlap graph has degrees 11^12 7^6 6^2 and W = 816 wedges, and
T counts every triangle of that graph. The 22 triple labels close 22 triangles and
T <= W / 3 = 272. The ranges below are disjoint and cover 22..272.

* T >= 271 is empty. The ledger row's existing cap authority (NB frontier R1) is the least of
  the NB cap 272, R18's induced-P3 class cap 270 and the catalog cap, so T <= 270.
  Independently, an H-L edge carries at least 4 open-wedge arms, so 4c <= 2(W - 3T) <= 6 for
  c = e(H, L). Parity forces c = 0, and c = 0 forces K12 + (K8 - e) with T = 270. The
  committed T270 verifier (10e2ff6c) records the same trace, REALIZABLE_T = [270].
* T = 270 has the exact maximum 313,263,888. This comes from the pinned T270 structural
  closure (five pointed STS(13) classes), re-derived and Judge-verified in 10e2ff6c. Its
  representatives are not rebuilt here.
* 256 <= T <= 269 is empty, cell by cell, by three graph-level certificates:
  - T256..T262: the degree-sequence relaxation theorem;
  - T263..T268: the open-wedge gap;
  - T269: the structural exclusion.
  The T256..T262 theorem alone gives T = 270 or T <= 255 for every graph with these
  degrees, so T263..T269 are covered twice.
* 22 <= T <= 255 is bounded by 313,263,412. That is R32 Route B evaluated at every t in
  22..255 with the row's S4 base.

Authority.
* The five source results and three verifier scripts are archived byte for byte in this tree
  and pinned by SHA-256. Each archive copy is bound to the commit or task directory it came
  from.
* The three T256..T269 verifiers are re-executed from those copies in a scratch directory. Each
  must reproduce its frozen result, apart from resource and path fields.
* The committed T270 verifier runs only its result, archive and arithmetic checks, read-only, in
  its own worktree.
* The load-bearing arithmetic of every range is recomputed here independently.

Ledger.
* The 4,647-row ledger is the 2f709256 split-cap chase ledger. Its zero-solve replay rebuilds
  it, its recorded chase certificates are applied, and the result is checked against its row
  digest.
* Only this profile's row is replaced, and only in a copy. The frozen ledger and every other
  row stay as they are, including improvements recorded elsewhere but not integrated here.

Scope. No solver, portfolio search, outcome enumeration or RUN1 access happens. The claim
covers this one profile only. It bounds neither the min-S2 family nor the global K20 optimum.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from itertools import combinations
from math import comb
from pathlib import Path
from typing import cast

from . import b649_k20_min_s2_nb_degree_cap_frontier_r1 as nb
from . import b649_k20_min_s2_split_cap_current_owner_chase_r1 as chase
from .b649_k20_min_s2_resolved_above_cursor_owner_chase_r20 import decode_profile

split = chase.split
prior = chase.prior
integer = chase.integer
object_row = chase.object_row
rows = chase.rows
text = chase.text

TASK_ID = "B649_MIN_S2_INCUMBENT_PROFILE_ALL_TRIANGLE_CLOSURE_R1"
TASK_BRANCH = "claude/b649-min-s2-incumbent-profile-all-triangle-closure-r1"
BASE_HEAD = "2f70925698cb28758fdf29a62bc5e91028c03a81"
BASE_TREE = "216bd91dee0afa58f8186a38aec52b1d47781ef8"
CHASE_RESULT_SHA256 = "2269cc5e5e3bf08650fa711a240e7d088814e1bcd35d0cb9efcb01a91a2d67f3"
LEDGER_ROWS_SHA256 = "2cf91665b86167e917f47779fdee3cb23b07b1d1b3d2491eae8b3ab42d9307a8"
LEDGER_FAMILY_UB = 313_404_008
LEDGER_OWNER_IDS = ["66666555555311100000"]

PROFILE = "55555555555511111100"
DEGREES = (11,) * 12 + (7,) * 6 + (6,) * 2
H_SIZE, L_SIZE = 12, 8
W = 816
T_MIN = 22
T_MAX = W // 3
T_EXACT = 270
GAP_LOW, GAP_HIGH = 256, 269
LOW_CAP = 255
K12_PLUS_K8_MINUS_E = comb(12, 3) + comb(8, 3) - (8 - 2)
INCUMBENT = chase.INCUMBENT
STRICT_GAIN_THRESHOLD = INCUMBENT + 1
T270_EXACT_MAX = 313_263_888
LEDGER_ROW_BOUND = 313_402_304
LEDGER_ROW_CAP = 270
LEDGER_ROW_SOURCE = "b649-k20-min-s2-nb-degree-cap-frontier-r1-result.json:NB_CERTIFICATES[1732]"
S4_BASE = 112
ROUTE_B_LOW_BOUND = 313_263_412
ROUTE_B_AT_GAP_LOW = 313_272_568

ROOT = split.ROOT
RESULT_DIRECTORY = prior.RESULT_DIRECTORY
RESULT_FILENAME = "b649-min-s2-incumbent-profile-all-triangle-closure-r1-result.json"
RESULT_PATH = ROOT / RESULT_DIRECTORY / RESULT_FILENAME
SOURCE_DIRECTORY = (
    f"{RESULT_DIRECTORY}/b649-min-s2-incumbent-profile-all-triangle-closure-r1-sources"
)

T256_TASK = "B649_K20_FIBER_SAME_PROFILE_T256_T262_GRAPH_BOUND_R1"
T263_TASK = "B649_K20_FIBER_SAME_PROFILE_T263_T268_GRAPH_GAP_R1"
T269_TASK = "B649_K20_FIBER_T269_STRUCTURAL_EXCLUSION_R1"
T270_TASK = "B649_K20_FIBER_INCUMBENT_T270_STRUCTURAL_EXACT_CLOSURE_R1"
SLICE1_TASK = "B649_FIBER_SLICE1_PROVEN_NO_STRICT_GAIN_CLOSURE_R1"
T256_ARCHIVE_COMMIT = "108a72e41d60baecf6b114026ce2ca5db05ec4e0"
T270_ARCHIVE_COMMIT = "2f2054da69a327a5b14a4f39d4e623b364edf321"
T270_VERIFIER_COMMIT = "10e2ff6c8528bace65adea61a781b1f2a1099f3b"
T270_VERIFIER_TREE = "7ce2fcc1154ac83d407bb9409f645d7ef3f233ae"
T270_VERIFIER_MODULE = "src/lottolab/research/b649_fiber_slice1_no_strict_gain_closure.py"
T270_VERIFIER_MODULE_SHA256 = "6d1c2a12ec95cfbb73705710e80784dc47bc9ff6a922bc041b420bee2c90031b"
T270_SCRIPT_SHA256 = "45ee56d3426c363137c74ce76f8762d50e10d180d20220fd994b336c04dfce07"
WORKSPACE = "/Users/kelvin/VibeCoding-WorkSpace"
CODEX = "/Users/kelvin/.codex/worktrees"
T270_VERIFIER_WORKTREE = (
    f"{WORKSPACE}/.worktrees/MathStatisticalAnalysis/B649_FIBER_SLICE1_PROVEN_NO_GAIN_CLOSURE_R1"
)
T256_TASK_DIR = (
    f"{CODEX}/b649-k20-fiber-t256-t262-bound-r1/MathStatisticalAnalysis/.task-data/{T256_TASK}"
)
T263_TASK_DIR = (
    f"{CODEX}/b649-k20-fiber-t263-t268-gap-r1/MathStatisticalAnalysis/.task-data/{T263_TASK}"
)
T269_TASK_DIR = (
    f"{CODEX}/b649-k20-fiber-t269-structural-r1/MathStatisticalAnalysis/.task-data/{T269_TASK}"
)
T270_TASK_DIR = f"{WORKSPACE}/MathStatisticalAnalysis/.task-data/{T270_TASK}"
MATRIX = "docs/research/matrix-native-results"


class ClosureError(RuntimeError):
    """A load-bearing proof input is missing, changed or inconsistent."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ClosureError(f"PROOF_AUTHORITY_INCOMPLETE: {message}")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class Source:
    """One archived proof input and the certificate type it supplies."""

    key: str
    certificate: str
    cells: tuple[int, ...]
    result: str
    result_sha256: str
    script: str | None = None
    script_sha256: str | None = None


SOURCES: tuple[Source, ...] = (
    Source(
        "T256_T262",
        "GRAPH_LEVEL_DEGREE_SEQUENCE_RELAXATION_THEOREM",
        tuple(range(256, 263)),
        "t256-t262/result.json",
        "fa6f77604d6df14e0af41f92dd3116d9782db83ab557619ce06a5abfccbf1293",
        "t256-t262/t256_t262_graph_bound.py.txt",
        "ba67e397fe90d514cf458fec9d7345f4000158f646f0bfcf780c63a3f295f4ff",
    ),
    Source(
        "T263_T268",
        "GRAPH_LEVEL_OPEN_WEDGE_GAP_THEOREM",
        tuple(range(263, 269)),
        "t263-t268/result.json",
        "8ad5419f57ff23342a6503a1579631b133a5d7aa19a8026b63792f7480550e3e",
        "t263-t268/t263_t268_graph_gap.py.txt",
        "2c392887d74de685afc8d88629c8ccd2fa6aeceee21709ff13667976a7fabe87",
    ),
    Source(
        "T269",
        "GRAPH_LEVEL_STRUCTURAL_EXCLUSION_THEOREM",
        (269,),
        "t269/result.json",
        "3bb366d7f53cf3ec922dc806932e28ec8780ae4f3c89bad2149716b171159180",
        "t269/t269_structural_exclusion.py.txt",
        "57cd0ac838e2da3e1a7cd35e7e63f5975dabc443d20ce91cd101d9f29dd96d5d",
    ),
    Source(
        "T270",
        "EXACT_STRUCTURAL_CLASSIFICATION_FIVE_STS13_CLASSES_EXACT_COUNTS",
        (270,),
        "t270/result.json",
        "cd136425601d69c4cf1f437ea11a2c2bd25ff9d295e2cc2f670092aeb20176b8",
    ),
    Source(
        "T270_COMMITTED_VERIFIER",
        "COMMITTED_JUDGE_VERIFIED_T270_REDERIVATION_OUTPUT",
        (270,),
        "t270/slice1-closure-result.json",
        "a53eab695a54ccf44aa2b80803ca9aca2367399e8096904159751d71456de27f",
    ),
)
SOURCE_BY_KEY = {source.key: source for source in SOURCES}

# (source key, commit or absolute task directory, path there, archived file)
ORIGINS: tuple[tuple[str, str, str, str], ...] = (
    ("T256_T262", T256_ARCHIVE_COMMIT, f"research-archive/{T256_TASK}/result.json",
     "t256-t262/result.json"),
    ("T256_T262", T256_ARCHIVE_COMMIT, f"research-archive/{T256_TASK}/t256_t262_graph_bound.py",
     "t256-t262/t256_t262_graph_bound.py.txt"),
    ("T256_T262", T256_TASK_DIR, "result.json", "t256-t262/result.json"),
    ("T256_T262", T256_TASK_DIR, "t256_t262_graph_bound.py",
     "t256-t262/t256_t262_graph_bound.py.txt"),
    ("T263_T268", T263_TASK_DIR, "result.json", "t263-t268/result.json"),
    ("T263_T268", T263_TASK_DIR, "t263_t268_graph_gap.py", "t263-t268/t263_t268_graph_gap.py.txt"),
    ("T269", T269_TASK_DIR, "result.json", "t269/result.json"),
    ("T269", T269_TASK_DIR, "t269_structural_exclusion.py",
     "t269/t269_structural_exclusion.py.txt"),
    ("T270", T270_VERIFIER_COMMIT,
     f"{MATRIX}/b649-fiber-t270-structural-exact-closure-r1-result.json",
     "t270/result.json"),
    ("T270", T270_ARCHIVE_COMMIT, f"research-archive/{T270_TASK}/result.json", "t270/result.json"),
    ("T270", T270_TASK_DIR, "result.json", "t270/result.json"),
    ("T270_COMMITTED_VERIFIER", T270_VERIFIER_COMMIT,
     f"{MATRIX}/b649-fiber-slice1-no-strict-gain-closure-r1-result.json",
     "t270/slice1-closure-result.json"),
)  # fmt: skip

DOMAIN_SUPPORT = {"PAIR_LABELS": 27, "TRIPLE_LABELS": 22}


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=ROOT, stderr=subprocess.DEVNULL)


def archived_bytes(root: Path, name: str) -> bytes:
    path = root / SOURCE_DIRECTORY / name
    require(path.is_file(), f"archived source {name} is missing")
    return path.read_bytes()


def load_sources(root: Path = ROOT) -> dict[str, dict[str, object]]:
    """Every archived result and script at its pinned SHA-256, results parsed."""

    out: dict[str, dict[str, object]] = {}
    for source in SOURCES:
        raw = archived_bytes(root, source.result)
        require(sha256(raw) == source.result_sha256, f"{source.key} result differs from its pin")
        if source.script is not None:
            script = archived_bytes(root, source.script)
            require(sha256(script) == source.script_sha256, f"{source.key} script differs from pin")
        out[source.key] = object_row(json.loads(raw))
    return out


def _same(seen: object, expected: object) -> bool:
    return type(seen) is type(expected) and seen == expected


def _expect(key: str, pairs: Sequence[tuple[object, object]]) -> None:
    for index, (seen, expected) in enumerate(pairs):
        require(_same(seen, expected), f"{key} claim {index} is not the pinned statement")


def check_t256(data: Mapping[str, object]) -> dict[str, object]:
    domain = object_row(data["DOMAIN"])
    tail = object_row(data["OUTER_M_TAIL"])
    preds = object_row(data["PREDECESSOR_CHECKS"])
    table = object_row(data["BOUNDED_CASE_ACCOUNTING"])
    m0 = object_row(table["0"])
    proved = {m: integer(object_row(table[str(m)])["PROVED_BOUND"]) for m in range(1, 13)}
    cells = SOURCE_BY_KEY["T256_T262"].cells
    _expect(
        "T256_T262",
        [
            (data.get("TASK_ID"), T256_TASK),
            (data.get("TASK_STATUS"), "COMPLETE"),
            (data.get("MATHEMATICAL_IDENTITY"), "PROVED"),
            (data.get("EQUALITY_M1"), "PROVED"),
            (data.get("EQUALITY_M12"), "PROVED"),
            (data.get("UNRESOLVED_CELLS"), []),
            (data.get("STRONGEST_PROVED_TRIANGLE_BOUND"),
             "T=270 (m=0) or T<=255 (m>=1); 255 attained by a legal graph"),
            (domain.get("PROFILE"), PROFILE),
            (domain.get("DEGREES"), list(DEGREES)),
            (domain.get("W"), W),
            (domain.get("TARGET_T"), list(cells)),
            ([data.get(f"T{t}_STATUS") for t in cells], ["PROVED_EMPTY"] * len(cells)),
            (tail.get("M_MIN"), 13),
            (tail.get("T_UPPER_BOUND"), 254),
            ((m0.get("M"), m0.get("PROVED_T"), m0.get("EXACT")), (0, T_EXACT, True)),
            (max(proved.values()), LOW_CAP),
            (data.get("SCRIPT_SHA256"), SOURCE_BY_KEY["T256_T262"].script_sha256),
            (object_row(preds["T270"]).get("SHA256"), SOURCE_BY_KEY["T270"].result_sha256),
            (object_row(preds["T269"]).get("SHA256"), SOURCE_BY_KEY["T269"].result_sha256),
            (object_row(preds["T263_T268"]).get("SHA256"),
             SOURCE_BY_KEY["T263_T268"].result_sha256),
        ],
    )  # fmt: skip
    return {"CELLS": list(cells), "PROVED_BOUND_BY_M": {str(m): b for m, b in proved.items()},
            "GRAPH_THEOREM": "T=270 (m=0) or T<=255 (m>=1)", "STATUS": "PASS"}  # fmt: skip


def check_t263(data: Mapping[str, object]) -> dict[str, object]:
    domain = object_row(data["CELL_DOMAIN"])
    pred = object_row(data["PREDECESSOR"])
    cells = SOURCE_BY_KEY["T263_T268"].cells
    _expect(
        "T263_T268",
        [
            (data.get("TASK_ID"), T263_TASK),
            (data.get("TASK_STATUS"), "PROVED_EMPTY_T263_T268_CELLS"),
            (data.get("GRAPH_GAP_PROOF_STATUS"), "PROVED"),
            (data.get("UNRESOLVED_CELLS"), []),
            (data.get("UNPROVED_ITEMS"), []),
            (data.get("COUNTEREXAMPLE_IF_ANY"), None),
            ([data.get(f"T{t}_STATUS") for t in cells], ["PROVED_EMPTY"] * len(cells)),
            (domain.get("TRIPLE_DEGREE_PROFILE"), PROFILE),
            (domain.get("T_VALUES"), list(cells)),
            (domain.get("T_MEANING"), "ALL_OVERLAP_GRAPH_TRIANGLES"),
            (domain.get("W"), W),
            (domain.get("MAX_PAIRWISE_OVERLAP"), 1),
            (domain.get("SUPPORT"), DOMAIN_SUPPORT),
            (data.get("SCRIPT_SHA256"), SOURCE_BY_KEY["T263_T268"].script_sha256),
            (pred.get("T270_RESULT_SHA256"), SOURCE_BY_KEY["T270"].result_sha256),
            (pred.get("T269_RESULT_SHA256"), SOURCE_BY_KEY["T269"].result_sha256),
        ],
    )  # fmt: skip
    proof = object_row(object_row(data["GRAPH_GAP_PROOF"])["PHASE1_ARITHMETIC_AND_CASES"])
    bounds = {int(c): integer(object_row(v)["O_LOWER_BOUND"])
              for c, v in object_row(proof["CASE_BOUNDS"]).items()}  # fmt: skip
    floors = {str(c): bounds[c] for c in sorted(bounds)}
    return {"CELLS": list(cells), "CASE_O_LOWER_BOUNDS": floors,
            "STATUS": "PASS"}  # fmt: skip


def check_t269(data: Mapping[str, object]) -> dict[str, object]:
    domain = object_row(data["EXACT_CELL_DOMAIN"])
    proof = object_row(data["STRUCTURAL_EXCLUSION_PROOF"])
    phase = object_row(proof["PHASE1_ARITHMETIC"])
    _expect(
        "T269",
        [
            (data.get("TASK_ID"), T269_TASK),
            (data.get("TASK_STATUS"), "PROVED_EMPTY_T269_CELL"),
            (data.get("T269_CELL_STATUS"), "PROVED_EMPTY"),
            (data.get("STRICT_GAIN"), "NO"),
            (data.get("UNPROVED_ITEMS"), []),
            (proof.get("STATUS"), "PROVED"),
            (phase.get("C_FEASIBLE_AFTER_PARITY"), [0, 2, 4]),
            (phase.get("OPEN_WEDGES_O"), W - 3 * 269),
            (domain.get("TRIPLE_DEGREE_PROFILE"), PROFILE),
            (domain.get("OVERLAP_GRAPH_TRIANGLES_T_ALL_TRIANGLES"), 269),
            (domain.get("MAX_PAIRWISE_OVERLAP"), 1),
            (domain.get("SUPPORT"), DOMAIN_SUPPORT),
            (data.get("SCRIPT_SHA256"), SOURCE_BY_KEY["T269"].script_sha256),
            (object_row(data["PREDECESSOR"]).get("T270_RESULT_SHA256"),
             SOURCE_BY_KEY["T270"].result_sha256),
        ],
    )  # fmt: skip
    return {"CELLS": [269], "C_FEASIBLE": [0, 2, 4], "STATUS": "PASS"}


def check_t270(data: Mapping[str, object], slice1: Mapping[str, object]) -> dict[str, object]:
    """The pinned T270 closure and the committed verifier's Judge-verified re-derivation of it."""

    domain = object_row(data["EXACT_CELL_DOMAIN"])
    deps = object_row(data["DEPENDENCY_SHA256"])
    proof = object_row(data["STRUCTURAL_COMPLETENESS_PROOF"])
    closure = object_row(slice1["T270_EXACT_CLOSURE"])
    arithmetic = object_row(closure["STRUCTURAL_ARITHMETIC"])
    reps = [object_row(r) for r in rows(closure["REPRESENTATIVES"])]
    counts = sorted(integer(r["OFFICIAL_EXACT_COUNT"]) for r in reps)
    trace = {integer(object_row(r)["T"]): rows(object_row(r)["ADMITTED_C"])
             for r in rows(arithmetic["T_TRACE"])}  # fmt: skip
    _expect(
        "T270",
        [
            (data.get("TASK_ID"), T270_TASK),
            (data.get("TASK_STATUS"), "PROVED_NO_STRICT_GAIN_WITHIN_DEFINED_PROFILE_T270_CELL"),
            (proof.get("STATUS"), "PROVED"),
            (data.get("EXACT_CELL_MAX"), T270_EXACT_MAX),
            (data.get("STRICT_GAIN"), "NO"),
            (data.get("UNPROVED_ITEMS"), []),
            (domain.get("TRIPLE_DEGREE_PROFILE"), PROFILE),
            (domain.get("OVERLAP_GRAPH_TRIANGLES_T_ALL_TRIANGLES"), T_EXACT),
            (domain.get("MAX_PAIRWISE_OVERLAP"), 1),
            (domain.get("SUPPORT"), DOMAIN_SUPPORT),
            (deps.get("SCRIPT"), T270_SCRIPT_SHA256),
            (slice1.get("TASK_ID"), SLICE1_TASK),
            (slice1.get("SLICE1_SCIENTIFIC_NO_STRICT_GAIN"), "PROVED"),
            (closure.get("CELL"), [PROFILE, T_EXACT]),
            (closure.get("RESULT_SHA256"), SOURCE_BY_KEY["T270"].result_sha256),
            (closure.get("EXACT_CELL_MAX"), T270_EXACT_MAX),
            (closure.get("ISOMORPHISM_CLASS_COUNT"), 5),
            (closure.get("RECORDED_CLASS_TABLE_MATCHES"), True),
            (len(reps), 5),
            (counts[-1], T270_EXACT_MAX),
            (arithmetic.get("W"), W),
            (arithmetic.get("REALIZABLE_T"), [T_EXACT]),
            (arithmetic.get("CELL_AT_LEAST_CAP_EQUALS_CELL_AT_CAP"), True),
            (sorted(trace), list(range(T_EXACT, T_MAX + 1))),
            ([len(trace[t]) for t in range(T_EXACT + 1, T_MAX + 1)], [0] * (T_MAX - T_EXACT)),
            (trace[T_EXACT], [0]),
        ],
    )  # fmt: skip
    return {
        "CELL": [PROFILE, T_EXACT],
        "EXACT_CELL_MAX": T270_EXACT_MAX,
        "CLASS_COUNTS": counts,
        "COMMITTED_TRACE_ADMITTED_C_COUNT_ABOVE_270": {
            str(t): 0 for t in range(T_EXACT + 1, T_MAX + 1)
        },
        "STS_REPRESENTATIVES_REBUILT_HERE": False,
        "STATUS": "PASS",
    }


def check_claims(parsed: Mapping[str, Mapping[str, object]]) -> dict[str, object]:
    return {
        "T256_T262": check_t256(parsed["T256_T262"]),
        "T263_T268": check_t263(parsed["T263_T268"]),
        "T269": check_t269(parsed["T269"]),
        "T270": check_t270(parsed["T270"], parsed["T270_COMMITTED_VERIFIER"]),
    }


# Independent arithmetic of every range ----------------------------------------------------


def arm_term_minimum(light_degrees: Sequence[int] = (7, 6)) -> int:
    """Least open-wedge arm count of an H-L edge hx: (10 - k) + (deg x - 1 - k), k <= deg x - 1.

    For an edge uv the open wedges with arm uv number (deg u - 1 - k) + (deg v - 1 - k) with
    k = |N(u) & N(v)|, and every open wedge has two arms, so these terms sum to 2 * open.
    """

    return min((10 - k) + (dx - 1 - k) for dx in light_degrees for k in range(dx))


def degree_identities() -> dict[str, int]:
    """Profile degrees, edges, wedges, the H/L degree sums and the c = 0 structure."""

    profile = decode_profile(PROFILE)
    require(tuple(6 + d for d in profile) == DEGREES, "graph degrees are not 6 + triple degree")
    require(sum(profile) == 3 * 22 and sum(DEGREES) == 2 * (3 * 22 + 27), "edge count is not 93")
    require(sum(comb(g, 2) for g in DEGREES) == W, "W is not 816")
    heavy, light = sum(DEGREES[:H_SIZE]), sum(DEGREES[H_SIZE:])
    # c = 0: e(H) = 132 / 2 = C(12, 2) and e(L) = 54 / 2 = C(8, 2) - 1, the missing pair joining
    # the two degree-6 tickets, so G = K12 + (K8 - e).
    require(heavy == 2 * comb(H_SIZE, 2) and light == 2 * (comb(L_SIZE, 2) - 1), "c=0 not forced")
    require(K12_PLUS_K8_MINUS_E == T_EXACT, "K12 + (K8 - e) does not have 270 triangles")
    return {"EDGES": sum(DEGREES) // 2, "W": W, "H_DEGREE_SUM": heavy, "L_DEGREE_SUM": light,
            "ARM_TERM_MIN": arm_term_minimum(), "C0_TRIANGLES": K12_PLUS_K8_MINUS_E}  # fmt: skip


def above_exact_trace(arm: int | None = None) -> list[dict[str, object]]:
    """T >= 271: 4c <= 2 * open leaves c <= 1, parity leaves c = 0, and c = 0 means T = 270."""

    term = arm_term_minimum() if arm is None else arm
    out: list[dict[str, object]] = []
    for t in range(T_EXACT + 1, T_MAX + 1):
        open_wedges = W - 3 * t
        even = [c for c in range(2 * open_wedges // term + 1) if c % 2 == 0]
        require(even == [0] and t != K12_PLUS_K8_MINUS_E, f"T={t} is not excluded")
        out.append({"T": t, "OPEN_WEDGES": open_wedges, "EVEN_C": even,
                    "C0_FORCED_T": K12_PLUS_K8_MINUS_E, "REALIZABLE": False})  # fmt: skip
    return out


def erdos_gallai(seq: Sequence[int]) -> bool:
    n = len(seq)
    return sum(seq) % 2 == 0 and all(
        sum(seq[:k]) <= k * (k - 1) + sum(min(d, k) for d in seq[k:]) for k in range(1, n + 1)
    )


def graphic_sequences(edges: int, n: int, cap: int) -> list[tuple[int, ...]]:
    """Positive parts of every simple-graph degree sequence: `edges` edges, n vertices, max cap."""

    found: list[tuple[int, ...]] = []

    def extend(prefix: tuple[int, ...], remaining: int, top: int) -> None:
        if remaining == 0:
            if erdos_gallai(prefix + (0,) * (n - len(prefix))):
                found.append(prefix)
            return
        if len(prefix) == n:
            return
        for part in range(min(remaining, top), 0, -1):
            extend((*prefix, part), remaining - part, part)

    extend((), 2 * edges, min(cap, n - 1))
    return found


def relaxation_table() -> dict[int, dict[str, int]]:
    """T <= 270 - 20m + U_F(m) + V_M(m + 1) for m = 1..12 (the T256..T262 relaxation)."""

    table: dict[int, dict[str, int]] = {}
    for m in range(1, 13):
        u_f = max(sum(d * d for d in p) for p in graphic_sequences(m, H_SIZE, L_SIZE))
        v_m = max(
            sum(d * d for d in p) - p[-1] - p[-2]
            for p in graphic_sequences(m + 1, L_SIZE, L_SIZE - 1)
        )
        table[m] = {"U_F": u_f, "V_M": v_m, "RELAXED_BOUND": T_EXACT - 20 * m + u_f + v_m}
    return table


def graph_theorem(
    table: Mapping[int, Mapping[str, int]], source: Mapping[str, object]
) -> dict[str, object]:
    """Every graph with degrees 11^12 7^6 6^2 has T = 270 (m = 0) or T <= 255 (m >= 1)."""

    recorded = object_row(source["BOUNDED_CASE_ACCOUNTING"])
    for m, row in table.items():
        seen = object_row(recorded[str(m)])
        require(all(_same(seen.get(k), v) for k, v in row.items()), f"m={m} relaxation differs")
    equality = [m for m, row in table.items() if row["RELAXED_BOUND"] >= GAP_LOW]
    require(
        equality == [1, 12] and all(table[m]["RELAXED_BOUND"] == GAP_LOW for m in equality),
        "the relaxation reaches 256 outside the two proved equality cases",
    )
    require(
        source.get("EQUALITY_M1") == "PROVED" and source.get("EQUALITY_M12") == "PROVED",
        "an equality-case contradiction is not proved",
    )
    proved = {m: LOW_CAP if m in equality else row["RELAXED_BOUND"] for m, row in table.items()}
    tail_m = 13  # O >= 4m from 8m = 4c <= 2 * open; T >= 256 means open <= 48, so m <= 12
    tail = (W - 4 * tail_m) // 3
    ceiling = max([*proved.values(), tail])
    require(ceiling == LOW_CAP and tail == 254, "the non-270 ceiling is not 255")
    return {
        "RELAXED_TABLE_RECOMPUTED": {str(m): dict(row) for m, row in table.items()},
        "EQUALITY_CASES_256_TO_255": equality,
        "PROVED_BOUND_BY_M": {str(m): b for m, b in proved.items()},
        "M_AT_LEAST_13_T_MAX": tail,
        "M0_T": K12_PLUS_K8_MINUS_E,
        "NON_270_CEILING": ceiling,
        "STATUS": "PASS",
    }


def gap_case_bounds() -> dict[int, int]:
    """Lemma A/B/C open-wedge floors for c = e(H, L) = 2..12 (T263..T268 step S9)."""

    out: dict[int, int] = {}
    for c in range(2, 13, 2):
        m = c // 2
        mixed = 2 * 10 if c == 2 else c * (5 - m) if c in (4, 6) else 0
        out[c] = m * (11 - m) + mixed
    return out


def gap_cells(recorded: Mapping[str, object], arm: int | None = None) -> dict[str, object]:
    term = arm_term_minimum() if arm is None else arm
    bounds = gap_case_bounds()
    require({str(c): b for c, b in bounds.items()} == recorded, "T263..T268 case floors differ")
    cells: dict[str, object] = {}
    for t in SOURCE_BY_KEY["T263_T268"].cells:
        open_wedges = W - 3 * t
        even = [c for c in range(2 * open_wedges // term + 1) if c % 2 == 0]
        require(all(c in bounds or c == 0 for c in even), f"T={t} admits an unproved c")
        require(
            t != K12_PLUS_K8_MINUS_E and all(bounds[c] > open_wedges for c in even if c),
            f"T={t} is not excluded",
        )
        cells[str(t)] = {"OPEN_WEDGES": open_wedges, "EVEN_C": even}
    return {"CASE_O_LOWER_BOUNDS": {str(c): b for c, b in bounds.items()}, "CELLS": cells,
            "STATUS": "PASS"}  # fmt: skip


def h_internal_open_wedges(missing: Sequence[tuple[int, int]]) -> int:
    """Open wedges x-w-y inside K12 minus `missing`: x, y non-adjacent, w adjacent to both."""

    gone = {frozenset(pair) for pair in missing}

    def adjacent(a: int, b: int) -> bool:
        return frozenset((a, b)) not in gone

    return sum(
        1
        for x, y in combinations(range(H_SIZE), 2)
        if not adjacent(x, y)
        for w in range(H_SIZE)
        if w not in (x, y) and adjacent(w, x) and adjacent(w, y)
    )


def t269_cases(arm: int | None = None, open_wedges: int = W - 3 * 269) -> dict[str, object]:
    """T = 269 leaves 9 open wedges; c = 2 and c = 4 force at least 10 and 18 inside H."""

    term = arm_term_minimum() if arm is None else arm
    even = [c for c in range(2 * open_wedges // term + 1) if c % 2 == 0]
    floors = {
        2: h_internal_open_wedges([(0, 1)]),
        4: min(h_internal_open_wedges([(0, 1), (0, 2)]), h_internal_open_wedges([(0, 1), (2, 3)])),
    }
    require(even == [0, 2, 4] and K12_PLUS_K8_MINUS_E != 269, "T269 c set changed")
    require(all(floors[c] > open_wedges for c in (2, 4)), "T269 is not excluded")
    return {"OPEN_WEDGES": open_wedges, "EVEN_C": even,
            "H_INTERNAL_OPEN_WEDGE_FLOOR": {str(c): f for c, f in floors.items()},
            "STATUS": "PASS"}  # fmt: skip


def route_b_summary() -> dict[str, object]:
    """R32 Route B at every t in 22..255, plus the ledger cap and the T=256 teeth."""

    p = split.profile_values(PROFILE)
    low = split.route_b_terms(p, LOW_CAP, S4_BASE)
    ledger = split.route_b_terms(p, LEDGER_ROW_CAP, S4_BASE)
    gap = split.route_b_terms(p, GAP_LOW, S4_BASE)
    best = max(low, key=lambda term: (term[1], term[0]))
    require([term[0] for term in low] == list(range(T_MIN, LOW_CAP + 1)), "Route B misses a t")
    require(ledger[: len(low)] == low, "the cap-255 envelope is not the all-t formula prefix")
    require(best[1] == ROUTE_B_LOW_BOUND < STRICT_GAIN_THRESHOLD, "T<=255 bound changed")
    require(max(term[1] for term in ledger) == LEDGER_ROW_BOUND, "ledger row bound changed")
    require(max(term[1] for term in gap) == ROUTE_B_AT_GAP_LOW > INCUMBENT, "T=256 teeth changed")
    t, bound, k4, contained, s4, s3 = best
    return {
        "CAP": LOW_CAP,
        "S4_BASE": S4_BASE,
        "TERM_COUNT": len(low),
        "ARGMAX": {"T": t, "BOUND": bound, "K4": k4, "CONTAINED_K4": contained, "S4": s4,
                   "S3": s3},
        "ALL_T_MAX_BOUND": bound,
        "MARGIN_BELOW_INCUMBENT": INCUMBENT - bound,
        "INTEGER_AND_RATIONAL": "PASS",
        "ROUTE_B_AT_CAP_270_REPRODUCES_LEDGER_ROW": LEDGER_ROW_BOUND,
        "ROUTE_B_AT_CAP_256_ABOVE_INCUMBENT": ROUTE_B_AT_GAP_LOW,
    }  # fmt: skip


def existing_cap(row_cap: int = LEDGER_ROW_CAP) -> dict[str, object]:
    """The ledger row's cap authority: min(NB cap, R18 class cap, catalog cap) = 270."""

    profile = decode_profile(PROFILE)
    wedges, floor, nb_cap = nb.profile_nb_cap(profile)
    r18 = nb.r18_cap(profile)
    combined = nb.combined_triangle_cap(nb_cap, r18, row_cap)
    require(wedges == W and combined == LEDGER_ROW_CAP == r18, "existing triangle cap changed")
    return {"NB_OPEN_WEDGE_FLOOR": floor, "NB_CAP": nb_cap, "R18_CLASS_CAP": r18,
            "LEDGER_ROW_CAP": row_cap, "COMBINED_CAP": combined, "STATUS": "PASS"}  # fmt: skip


# The profile-level partition ---------------------------------------------------------------


@dataclass(frozen=True)
class Range:
    low: int
    high: int
    status: str
    bound: int | None
    authority: tuple[str, ...]


def partition() -> list[Range]:
    return [
        Range(T_MIN, LOW_CAP, "UPPER_BOUND", ROUTE_B_LOW_BOUND, ("R32_ROUTE_B_ALL_T_CAP_255",)),
        Range(256, 262, "EMPTY", None, ("T256_T262",)),
        Range(263, 268, "EMPTY", None, ("T263_T268", "T256_T262")),
        Range(269, 269, "EMPTY", None, ("T269", "T256_T262")),
        Range(T_EXACT, T_EXACT, "EXACT_MAX", T270_EXACT_MAX, ("T270", "T270_COMMITTED_VERIFIER")),
        Range(T_EXACT + 1, T_MAX, "EMPTY", None,
              ("LEDGER_ROW_CAP_NB_R18", "T270_COMMITTED_VERIFIER", "INDEPENDENT_ARM_PARITY",
               "T256_T262")),
    ]  # fmt: skip


def coverage(ranges: Sequence[Range]) -> dict[str, object]:
    """The ranges cover 22..272 exactly once; each empty gap range is a proved source cell."""

    values = [t for r in ranges for t in range(r.low, r.high + 1)]
    require(values == list(range(T_MIN, T_MAX + 1)), "ranges are not a disjoint cover of 22..272")
    for r in ranges:
        require((r.status == "EMPTY") == (r.bound is None), "a range has an inconsistent status")
        if r.status == "EMPTY" and r.low <= GAP_HIGH:
            cells = SOURCE_BY_KEY[r.authority[0]].cells
            require(set(range(r.low, r.high + 1)) <= set(cells), "a gap range is not a source cell")
    gap = sorted(t for r in ranges if r.status == "EMPTY" and r.low <= GAP_HIGH
                 for t in range(r.low, r.high + 1))  # fmt: skip
    require(gap == list(range(GAP_LOW, GAP_HIGH + 1)), "256..269 is not covered by empty cells")
    bound = max(r.bound for r in ranges if r.bound is not None)
    return {
        "T_DOMAIN": [T_MIN, T_MAX],
        "DISJOINT_AND_COVERING": True,
        "RANGES": [{"T_LOW": r.low, "T_HIGH": r.high, "STATUS": r.status, "BOUND": r.bound,
                    "AUTHORITY": list(r.authority)} for r in ranges],
        "PROFILE_OFFICIAL_MAX_UB": bound,
    }  # fmt: skip


# The 4,647-row ledger and the single-profile replacement --------------------------------


def chase_result(root: Path = ROOT) -> dict[str, object]:
    raw = (root / RESULT_DIRECTORY / chase.RESULT_FILENAME).read_bytes()
    require(sha256(raw) == CHASE_RESULT_SHA256, "split-cap chase result differs from its pin")
    return object_row(json.loads(raw))


def rows_digest(ledger: Mapping[str, chase.Row]) -> str:
    serialized = [{"PROFILE_ID": pid, "CURRENT_BOUND": ledger[pid].bound} for pid in sorted(ledger)]
    return sha256(json.dumps(serialized, sort_keys=True).encode())


def frozen_ledger(authority: chase.Authority, result: Mapping[str, object]) -> dict[str, chase.Row]:
    """The 2f709256 final ledger: the replayed rows plus each recorded TIGHTENED certificate."""

    ledger = dict(authority.ledger)
    for index, raw in enumerate(rows(result["CERTIFICATES"])):
        cert = object_row(raw)
        if cert["STATUS"] != chase.TIGHTENED:
            continue
        pid = text(cert["PROFILE_ID"])
        old = ledger[pid]
        cap, bound = integer(cert["TRIANGLE_CAP"]), integer(cert["ALL_T_MAX_BOUND"])
        terms = split.route_b_terms(split.profile_values(pid), cap, old.s4_base)
        require(
            integer(cert["S4_BASE"]) == old.s4_base and max(t[1] for t in terms) == bound,
            f"recorded chase certificate for {pid} does not reproduce",
        )
        locator = f"{chase.RESULT_FILENAME}:CERTIFICATES[{index}]"
        ledger[pid] = replace(old, bound=bound, cap=cap, source=locator)
    family, owners = chase.family_state(ledger)
    require(
        len(ledger) == chase.RESOLVED_COUNT
        and rows_digest(ledger) == LEDGER_ROWS_SHA256 == result["FINAL_RESOLVED_ROWS_SHA256"]
        and (family, owners) == (LEDGER_FAMILY_UB, LEDGER_OWNER_IDS)
        and result["FINAL_COMPLETE_FAMILY_UB"] == family,
        "rebuilt ledger differs from the 2f709256 final ledger",
    )
    return ledger


def ranked(ledger: Mapping[str, chase.Row]) -> tuple[int, list[str], int, list[str]]:
    """Family maximum over every row and the cursor, its owners, and the next level, by sorting."""

    terms = [(row.bound, pid) for pid, row in ledger.items()]
    terms.append((prior.CURSOR_BOUND, prior.CURSOR_ID))
    levels = sorted({bound for bound, _ in terms}, reverse=True)
    top, nxt = levels[0], levels[1]
    return (
        top,
        sorted(p for b, p in terms if b == top),
        nxt,
        sorted(p for b, p in terms if b == nxt),
    )


def single_profile_update(ledger: Mapping[str, chase.Row], profile_ub: int) -> dict[str, object]:
    row = ledger[PROFILE]
    require(
        (row.bound, row.cap, row.s4_base, row.source)
        == (LEDGER_ROW_BOUND, LEDGER_ROW_CAP, S4_BASE, LEDGER_ROW_SOURCE),
        "the profile's ledger row is not the pinned R32 row",
    )
    require(profile_ub < row.bound, "the profile closure does not tighten its row")
    before_digest = rows_digest(ledger)
    updated = dict(ledger)
    updated[PROFILE] = replace(row, bound=profile_ub, source=f"{RESULT_FILENAME}:PROFILE_CLOSURE")
    out: dict[str, object] = {"ROW_COUNT": len(updated), "PROFILE_ID": PROFILE}
    for name, state in (("BEFORE", ledger), ("AFTER", updated)):
        family, owners, nxt, next_ids = ranked(state)
        reused, reused_owners = chase.family_state(state)
        require(reused == family and sorted(reused_owners) == owners, "family recompute differs")
        out[f"PROFILE_ROW_{name}"] = state[PROFILE].bound
        out[f"LEDGER_MAX_{name}"] = max(r.bound for r in state.values())
        out[f"FAMILY_UB_{name}"] = family
        out[f"FAMILY_OWNER_IDS_{name}"] = owners
        out[f"NEXT_COMPETING_BOUND_{name}"] = nxt
        out[f"NEXT_COMPETING_IDS_{name}"] = next_ids
        out[f"ROWS_ABOVE_INCUMBENT_{name}"] = sum(r.bound > INCUMBENT for r in state.values())
        out[f"ROWS_SHA256_{name}"] = rows_digest(state)
    changed = sorted(pid for pid in ledger if ledger[pid] != updated[pid])
    require(changed == [PROFILE] and rows_digest(ledger) == before_digest, "other rows changed")
    out["CHANGED_ROW_IDS"] = changed
    out["CURSOR"] = {"PROFILE_ID": prior.CURSOR_ID, "BOUND": prior.CURSOR_BOUND}
    out["FROZEN_LEDGER_MUTATED"] = False
    return out


# Not integrated here: recorded elsewhere, observed read-only on 2026-10-10.
UNINTEGRATED: tuple[tuple[str, str, str, str], ...] = (
    ("66666555555311100000", "Y/L isolation triangle cap 246 for the current ledger owner",
     f"{WORKSPACE}/.worktrees/MathStatisticalAnalysis/B649_MIN_S2_TOP_OWNER_YL_CAP246_CERT_R1",
     "branch codex/b649-min-s2-top-owner-yl-cap246-formal-cert-r1 at the base head, no change"),
    ("66666555555311100000", "T264 quartet-motif S4 credit, owner bound 313,394,852",
     f"{WORKSPACE}/.worktrees/MathStatisticalAnalysis/B649_K20_MIN_S2_T264_MOTIF_CREDIT_CERTIFICATE_R1"
     f"/{MATRIX}/b649-k20-min-s2-t264-motif-credit-certificate-r1-result.json",
     "untracked; sha256 9a8d287aa66da466e33fc7604d4799c6b0a78bbfb3e1ba93aea2b16314c953dc"),
    ("66666655544411100000", "block-isolation triangle cap 236, Bonferroni-3 bound 313,235,048",
     f"{CODEX}/b649-k20-next-fixed-profile-bound-r1/MathStatisticalAnalysis/.task-data/"
     "B649_K20_NEXT_UNCOVERED_FIXED_PROFILE_BOUND_R1/result.json",
     "gitignored; sha256 447518b2cf7428acb31c29c839bb29db2d16f8c9d9ad9f7744b62dcfaa7b853d"),
)  # fmt: skip


def unintegrated(ledger: Mapping[str, chase.Row]) -> list[dict[str, object]]:
    return [
        {"PROFILE_ID": pid, "CLAIM": claim, "LOCATOR": locator, "OBSERVED": observed,
         "LEDGER_ROW_BOUND_KEPT": ledger[pid].bound, "APPLIED_HERE": False}
        for pid, claim, locator, observed in UNINTEGRATED
    ]  # fmt: skip


# Re-execution, the committed T270 verifier and origin binding ---------------------------

VOLATILE: dict[str, frozenset[str]] = {
    "T256_T262": frozenset(
        {"CPU_SECONDS", "CPU_MICROSECONDS", "PEAK_RSS_BYTES", "OBSERVED_NICE", "SCRIPT_PATH",
         "RESULT_PATH", "WORKTREE_STATUS"}
    ),
    "T263_T268": frozenset({"RESOURCE"}),
    "T269": frozenset({"RESOURCE"}),
}  # fmt: skip
VERIFIER_ARGS: dict[str, tuple[str, ...]] = {
    "T256_T262": ("--write-result",),
    "T263_T268": (),
    "T269": (),
}


def differing_paths(left: object, right: object, path: str = "") -> list[str]:
    if type(left) is not type(right):
        return [path or "/"]
    if isinstance(left, dict):
        a, b = object_row(cast(object, left)), object_row(right)
        out: list[str] = []
        for key in sorted(set(a) | set(b)):
            if key in a and key in b:
                out.extend(differing_paths(a[key], b[key], f"{path}/{key}"))
            else:
                out.append(f"{path}/{key}")
        return out
    if isinstance(left, list):
        a_rows, b_rows = rows(cast(object, left)), rows(right)
        if len(a_rows) != len(b_rows):
            return [path or "/"]
        return [
            p
            for i, (x, y) in enumerate(zip(a_rows, b_rows, strict=True))
            for p in differing_paths(x, y, f"{path}[{i}]")
        ]
    return [] if left == right else [path or "/"]


def reproduce_verifiers(root: Path, work: Path) -> dict[str, object]:
    """Re-run each archived T256..T269 verifier in a fresh directory; outputs must match."""

    out: dict[str, object] = {}
    for key, args in VERIFIER_ARGS.items():
        source = SOURCE_BY_KEY[key]
        require(source.script is not None, f"{key} has no archived verifier")
        directory = work / key
        directory.mkdir(parents=True)
        script = directory / Path(str(source.script)).name.removesuffix(".txt")
        script.write_bytes(archived_bytes(root, str(source.script)))
        command = ["nice", "-n", "15", sys.executable, "-I", "-B", script.name, *args]
        done = subprocess.run(
            command, cwd=directory, capture_output=True, text=True, timeout=300, check=False
        )
        require(
            done.returncode == 0, f"{key} verifier exited {done.returncode}: {done.stderr[-300:]}"
        )
        produced = object_row(json.loads((directory / "result.json").read_text(encoding="utf-8")))
        frozen = object_row(json.loads(archived_bytes(root, source.result)))
        volatile = VOLATILE[key]
        diff = differing_paths(
            {k: v for k, v in frozen.items() if k not in volatile},
            {k: v for k, v in produced.items() if k not in volatile},
        )
        require(not diff and set(frozen) == set(produced), f"{key} re-execution differs: {diff}")
        out[key] = {
            "COMMAND": " ".join(["nice -n 15 <python> -I -B", script.name, *args]),
            "SCRIPT_SHA256": source.script_sha256,
            "FROZEN_RESULT_SHA256": source.result_sha256,
            "EXCLUDED_VOLATILE_KEYS": sorted(volatile),
            "COMPARED_KEY_COUNT": len(set(frozen) - volatile),
            "DIFFERING_PATHS": diff,
            "NORMALIZED_EQUAL": True,
        }
    return out


T270_PROBE = """
import json, sys
from pathlib import Path
root = Path(sys.argv[1]).resolve()
from lottolab.research import b649_fiber_slice1_no_strict_gain_closure as closure
from lottolab.research import b649_k20_fiber_near_top_s3_census as census
for module in (closure, census):
    assert Path(module.__file__).resolve().is_relative_to(root / "src"), module.__file__
data, raw = closure.load_t270(root)
archive = closure.t270_archive(root, raw)
profile = census.decode_profile(closure.INCUMBENT_PROFILE)
arithmetic = closure.structural_arithmetic(profile, closure.INCUMBENT_T)
out = {"EXACT_CELL_MAX": data["EXACT_CELL_MAX"], "ARCHIVE": archive, "ARITHMETIC": arithmetic}
print(json.dumps(out, sort_keys=True))
"""


def committed_t270_verifier(slice1: Mapping[str, object]) -> dict[str, object]:
    """Run the committed verifier's load, archive and arithmetic checks in its own worktree."""

    worktree = Path(T270_VERIFIER_WORKTREE)
    require(worktree.is_dir(), "the committed T270 verifier worktree is absent")
    identity = subprocess.check_output(
        ["git", "-C", str(worktree), "rev-parse", "HEAD", "HEAD^{tree}"]
    ).split()
    require(
        [i.decode() for i in identity] == [T270_VERIFIER_COMMIT, T270_VERIFIER_TREE],
        "verifier worktree is not at 10e2ff6c",
    )
    tracked = subprocess.check_output(
        ["git", "-C", str(worktree), "status", "--porcelain", "--untracked-files=no"]
    )
    module = (worktree / T270_VERIFIER_MODULE).read_bytes()
    require(
        tracked == b""
        and sha256(module) == T270_VERIFIER_MODULE_SHA256
        and module == git("show", f"{T270_VERIFIER_COMMIT}:{T270_VERIFIER_MODULE}"),
        "verifier worktree source differs from the commit",
    )
    env = {**os.environ, "PYTHONPATH": str(worktree / "src"), "PYTHONDONTWRITEBYTECODE": "1"}
    done = subprocess.run(
        [sys.executable, "-P", "-B", "-c", T270_PROBE, str(worktree)],
        cwd=worktree, env=env, capture_output=True, text=True, timeout=300, check=False,
    )  # fmt: skip
    require(done.returncode == 0, f"committed T270 verifier failed: {done.stderr[-300:]}")
    seen = object_row(json.loads(done.stdout))
    closure = object_row(slice1["T270_EXACT_CLOSURE"])
    require(
        seen["EXACT_CELL_MAX"] == T270_EXACT_MAX
        and seen["ARCHIVE"] == closure["ARCHIVE"]
        and seen["ARITHMETIC"] == closure["STRUCTURAL_ARITHMETIC"],
        "committed T270 verifier output differs from its committed result",
    )
    return {
        "COMMIT": T270_VERIFIER_COMMIT,
        "TREE": T270_VERIFIER_TREE,
        "MODULE": T270_VERIFIER_MODULE,
        "MODULE_SHA256": T270_VERIFIER_MODULE_SHA256,
        "CALLED": ["load_t270", "t270_archive", "structural_arithmetic"],
        "NOT_CALLED": "t270_closure, which rebuilds and recounts the five STS(13) representatives",
        "OUTPUT_MATCHES_COMMITTED_RESULT": True,
        "STATUS": "PASS",
    }


def origin_binding(root: Path = ROOT) -> list[dict[str, object]]:
    """Each archived file equals the bytes at the commit or task directory it was taken from."""

    out: list[dict[str, object]] = []
    for key, locator, path, archived in ORIGINS:
        data = archived_bytes(root, archived)
        if locator.startswith("/"):
            origin = Path(locator) / path
            require(origin.is_file(), f"{key} origin {origin} is absent")
            seen, kind = origin.read_bytes(), "UNCOMMITTED_TASK_DIRECTORY"
        else:
            try:
                seen = git("show", f"{locator}:{path}")
            except subprocess.CalledProcessError as error:
                raise ClosureError(f"PROOF_AUTHORITY_INCOMPLETE: {locator}:{path}") from error
            kind = "LOCAL_COMMIT"
        require(seen == data, f"{key} archive differs from {locator}/{path}")
        out.append({"SOURCE": key, "KIND": kind, "LOCATOR": locator, "PATH": path,
                    "ARCHIVED": archived, "SHA256": sha256(data),
                    "STATUS": "BYTE_IDENTICAL"})  # fmt: skip
    tree = git("rev-parse", f"{T270_VERIFIER_COMMIT}^{{tree}}").decode().strip()
    require(tree == T270_VERIFIER_TREE, "10e2ff6c tree differs")
    return out


def external_inputs_present() -> bool:
    try:
        origin_binding()
    except ClosureError:
        return False
    return Path(T270_VERIFIER_WORKTREE).is_dir()


# Result ---------------------------------------------------------------------------------

SUMMARY_KEYS = (
    "TASK_STATUS",
    "PROOF_T_GT_270",
    "PROOF_T256_TO_T269",
    "T270_EXACT_MAX",
    "T_LE_255_BOUND",
    "INCUMBENT_PROFILE_OFFICIAL_MAX_UB",
    "FULL_PROFILE_NO_STRICT_GAIN",
    "LEDGER_BOUND_BEFORE",
    "LEDGER_BOUND_AFTER_SINGLE_PROFILE_UPDATE",
    "FAMILY_BOUND_AFTER_SINGLE_PROFILE_UPDATE",
)


def compute_result(
    authority: chase.Authority | None = None, work: Path | None = None
) -> dict[str, object]:
    parsed = load_sources(ROOT)
    claims = check_claims(parsed)
    identities = degree_identities()
    above = above_exact_trace()
    cap = existing_cap()
    theorem = graph_theorem(relaxation_table(), parsed["T256_T262"])
    gap = gap_cells(object_row(object_row(claims["T263_T268"])["CASE_O_LOWER_BOUNDS"]))
    t269 = t269_cases()
    route = route_b_summary()
    cover = coverage(partition())
    profile_ub = integer(cover["PROFILE_OFFICIAL_MAX_UB"])
    require(profile_ub == T270_EXACT_MAX == INCUMBENT < STRICT_GAIN_THRESHOLD, "profile UB changed")
    origins = origin_binding(ROOT)
    verifier = committed_t270_verifier(parsed["T270_COMMITTED_VERIFIER"])
    if work is None:
        with tempfile.TemporaryDirectory(prefix="b649-profile-closure-") as scratch:
            reproduction = reproduce_verifiers(ROOT, Path(scratch))
    else:
        reproduction = reproduce_verifiers(ROOT, work)
    auth = chase.load_authority() if authority is None else authority
    ledger = frozen_ledger(auth, chase_result())
    update = single_profile_update(ledger, profile_ub)
    return {
        "TASK_ID": TASK_ID,
        "TASK_BRANCH": TASK_BRANCH,
        "TASK_STATUS": "COMPLETE",
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "PROOF": __doc__,
        "TARGET_PROFILE": PROFILE,
        "CURRENT_ACCEPTED_BEST": INCUMBENT,
        "STRICT_GAIN_THRESHOLD": STRICT_GAIN_THRESHOLD,
        "DOMAIN": {"GRAPH_DEGREES": "11^12, 7^6, 6^2", "MAX_PAIRWISE_OVERLAP": 1,
                   "SUPPORT": DOMAIN_SUPPORT, "T_MEANING": "ALL_OVERLAP_GRAPH_TRIANGLES",
                   **identities},
        "SOURCES": [{"KEY": s.key, "CERTIFICATE": s.certificate, "CELLS": list(s.cells),
                     "ARCHIVED_RESULT": f"{SOURCE_DIRECTORY}/{s.result}",
                     "RESULT_SHA256": s.result_sha256,
                     "ARCHIVED_SCRIPT": None if s.script is None
                     else f"{SOURCE_DIRECTORY}/{s.script}",
                     "SCRIPT_SHA256": s.script_sha256} for s in SOURCES],
        "SOURCE_CLAIMS": claims,
        "ORIGIN_BINDING": origins,
        "SOURCE_REEXECUTION": reproduction,
        "COMMITTED_T270_VERIFIER": verifier,
        "INDEPENDENT_ARITHMETIC": {"T_GT_270": above, "T256_TO_T262_GRAPH_THEOREM": theorem,
                                   "T263_TO_T268": gap, "T269": t269},
        "EXISTING_TRIANGLE_CAP": cap,
        "R32_ROUTE_B_CAP_255": route,
        "PARTITION": cover,
        "PROOF_T_GT_270": "PASS",
        "PROOF_T256_TO_T269": "PASS",
        "T270_EXACT_MAX": T270_EXACT_MAX,
        "T_LE_255_BOUND": ROUTE_B_LOW_BOUND,
        "INCUMBENT_PROFILE_OFFICIAL_MAX_UB": profile_ub,
        "FULL_PROFILE_NO_STRICT_GAIN": "PASS",
        "LEDGER_SINGLE_PROFILE_UPDATE": update,
        "LEDGER_BOUND_BEFORE": update["LEDGER_MAX_BEFORE"],
        "LEDGER_BOUND_AFTER_SINGLE_PROFILE_UPDATE": update["LEDGER_MAX_AFTER"],
        "FAMILY_BOUND_AFTER_SINGLE_PROFILE_UPDATE": update["FAMILY_UB_AFTER"],
        "UNINTEGRATED_PROFILE_IMPROVEMENTS": unintegrated(ledger),
        "SCOPE": {"CLAIM": "INCUMBENT_PROFILE_OFFICIAL_MAX <= 313263888 for profile " + PROFILE,
                  "MIN_S2_FAMILY": "NOT_CLAIMED", "GLOBAL_K20_OPTIMUM": "NOT_CLAIMED",
                  "OTHER_PROFILES": "UNCHANGED"},
        "SOLVER_CALLS": 0,
        "PORTFOLIO_SEARCH": "NONE",
        "OUTCOME_ENUMERATIONS": 0,
        "STS_REPRESENTATIVES_REBUILT": False,
        "RUN1_ACCESS": "NONE",
        "PRODUCTION_MUTATION": "NONE",
    }  # fmt: skip


def render(result: Mapping[str, object]) -> str:
    return json.dumps(result, indent=2, sort_keys=True) + "\n"


def main() -> None:
    result = compute_result()
    RESULT_PATH.write_text(render(result), encoding="utf-8")
    print(json.dumps({k: result[k] for k in SUMMARY_KEYS}, indent=2))


if __name__ == "__main__":
    main()
