"""Corrected K20 analytical authority; no portfolio search or solver execution.

Old certificates and their source manifest remain historical byte identities.
Source revisions below explicitly distinguish those bytes from repaired code.
Only current analytical expressions are admitted; archived CP-SAT evidence is
not translated or reused. The incumbent is reused from sealed K20 v8.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from math import comb
from pathlib import Path
from typing import Any

from lottolab.application.b649_sealed_geometry_portfolio import (
    SEALED_GEOMETRY_PORTFOLIOS,
    verify_sealed_geometry_portfolio,
)
from lottolab.research.b649_k1_k8_global_optimality import (
    OFFICIAL_ANY_PRIZE_DENOMINATOR,
    OFFICIAL_ANY_PRIZE_SINGLE_OUTCOMES,
)
from lottolab.research.b649_k20_heavy_pair_defect_global_bound_r2 import (
    c_wedge_certificate,
    triple_profile_table_sha256,
)
from lottolab.research.b649_k20_heavy_pair_r3plus_global_bound_r3 import family_a_result_record
from lottolab.research.b649_k20_min_s2_higher_order_closure_r2 import (
    k20_min_s2_family_official_any_prize_upper_bound,
)
from lottolab.research.b649_k20_multi_r2_defect_global_bound_r3 import defect_bound_certificates
from lottolab.research.b649_k20_outside_min_s2_global_penalty_bound_r1 import (
    PORTFOLIO_S1,
    SINGLE_TICKET_OUTCOMES,
    outside_min_s2_bounds,
    pair_intersection_table,
)
from lottolab.research.b649_official_any_prize_exact import evaluate_single_ticket_closed_form

ROOT = Path(__file__).resolve().parents[3]
TASK_ID = "B649_K20_CANONICAL_SINGLE_COUNT_RECONCILIATION_R1"
FROZEN_SOURCE_COMMIT = "9b0dc98b10623dac7727f50aa4e47f14f68dcf6d"
RESULT_DIR = "docs/research/matrix-native-results/"
RECORD = RESULT_DIR + "b649-k20-canonical-single-count-reconciliation-r1.json"
PRIOR_AUTHORITY = RESULT_DIR + "b649-branch3-k20-proof-authority-consolidation-r1.json"
PRIOR_MANIFEST = RESULT_DIR + "b649-branch3-k20-proof-authority-consolidation-r1-sources.json"
OUTSIDE_RECORD = RESULT_DIR + "b649-k20-outside-min-s2-global-penalty-bound-r1.json"
C_RECORD = RESULT_DIR + "b649-k20-heavy-pair-defect-global-bound-r2-result.json"
A_RECORD = RESULT_DIR + "b649-k20-heavy-pair-r3plus-global-bound-r3-result.json"
B_RECORD = RESULT_DIR + "b649-k20-multi-r2-defect-global-bound-r3-result.json"
WINNER_RECORD = RESULT_DIR + "b649-k20-12-8-winner-two-ticket-ascent-r1-result.json"
REVISED_FROZEN_PATHS = frozenset(
    f"{directory}/{prefix}{name}.py"
    for directory, prefix in (("src/lottolab/research", ""), ("tests/unit", "test_"))
    for name in (
        "b649_k20_outside_min_s2_global_penalty_bound_r1",
        "b649_k20_heavy_pair_defect_global_bound_r2",
        "b649_k20_heavy_pair_r3plus_global_bound_r3",
        "b649_k20_multi_r2_defect_global_bound_r3",
    )
)
CURRENT_IMPLEMENTATION_PATHS = (
    *sorted(REVISED_FROZEN_PATHS),
    "src/lottolab/research/b649_k1_k8_global_optimality.py",
    "src/lottolab/research/b649_official_any_prize_exact.py",
    "src/lottolab/application/b649_sealed_geometry_portfolio.py",
    "src/lottolab/research/b649_k20_min_s2_higher_order_closure_r2.py",
    "src/lottolab/research/b649_k20_canonical_single_count_reconciliation_r1.py",
    "tests/unit/test_b649_k20_canonical_single_count_reconciliation_r1.py",
    "tests/unit/test_b649_branch3_k20_proof_authority_consolidation_r1.py",
)
ARCHIVED_RECORD_PATHS = (
    PRIOR_AUTHORITY,
    PRIOR_MANIFEST,
    OUTSIDE_RECORD,
    C_RECORD,
    A_RECORD,
    B_RECORD,
    WINNER_RECORD,
)


def file_identity(root: Path, path: str) -> dict[str, Any]:
    content = (root / path).read_bytes()
    return {"path": path, "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()}


def _read(root: Path, path: str) -> dict[str, Any]:
    return json.loads((root / path).read_text(encoding="utf-8"))


def build_authority_record(root: Path = ROOT) -> dict[str, Any]:
    """Recompute analytical certificates and bind both historical/current bytes."""
    entry = SEALED_GEOMETRY_PORTFOLIOS[20]
    verify_sealed_geometry_portfolio(entry)
    incumbent = entry.official_any_prize_probability * OFFICIAL_ANY_PRIZE_DENOMINATOR
    if incumbent.denominator != 1:
        raise AssertionError("sealed incumbent does not resolve to an integer numerator")
    incumbent_count = int(incumbent)
    winner = _read(root, WINNER_RECORD)
    if winner["FINAL_COUNT"] != incumbent_count or winner["FINAL_SHA256"] != entry.portfolio_sha256:
        raise AssertionError("sealed incumbent and archived exact authority disagree")

    counts = pair_intersection_table()
    closed_form = evaluate_single_ticket_closed_form() * OFFICIAL_ANY_PRIZE_DENOMINATOR
    seven_set = 7 * sum(comb(6, hits) * comb(43, 7 - hits) for hits in range(3, 7))
    if not (
        SINGLE_TICKET_OUTCOMES
        == OFFICIAL_ANY_PRIZE_SINGLE_OUTCOMES
        == counts[6]
        == closed_form
        == seven_set
        == 18_611_432
    ):
        raise AssertionError("canonical single-ticket cross-invariant failed")
    if PORTFOLIO_S1 != 20 * SINGLE_TICKET_OUTCOMES:
        raise AssertionError("K20 S1 must equal twenty canonical single-ticket numerators")

    outside = outside_min_s2_bounds(incumbent=incumbent_count)
    family_a = family_a_result_record(incumbent=incumbent_count)
    family_b = defect_bound_certificates(incumbent=incumbent_count)
    family_c = asdict(c_wedge_certificate())
    bounds = {
        "MIN_S2": k20_min_s2_family_official_any_prize_upper_bound(),
        "OUTSIDE_PAIR_LE1": int(outside["LOW_OVERLAP_FAMILY_UPPER_BOUND"]),
        "FAMILY_A": family_a["FAMILY_A_BOUND"],
        "FAMILY_B": family_b["FAMILY_B_BOUND"],
        "FAMILY_C": family_c["upper_bound"],
    }
    family_summaries = {
        name: {
            "upper_bound": bound,
            "status": "CLOSED" if bound <= incumbent_count else "OPEN",
            "gap_to_incumbent": bound - incumbent_count,
        }
        for name, bound in bounds.items()
    }
    historical = _read(root, PRIOR_AUTHORITY)
    historical_b = _read(root, B_RECORD)["CERTIFICATES"]
    historical_s1 = _read(root, OUTSIDE_RECORD)["S1"]
    transitions = {
        "OUTSIDE_PAIR_LE1": (historical["K20_OUTSIDE_PAIR_LE1_BOUND"], bounds["OUTSIDE_PAIR_LE1"]),
        "FAMILY_C": (historical["K20_FAMILY_C_BOUND"], bounds["FAMILY_C"]),
        "TWO_SHARED_VERTEX": (
            historical_b["SHARED_VERTEX_R2_BOUND"],
            family_b["SHARED_VERTEX_R2_BOUND"],
        ),
        "TWO_DISJOINT": (historical_b["DISJOINT_R2_BOUND"], family_b["DISJOINT_R2_BOUND"]),
        "THREE_OR_MORE_AT_MASS_93": (
            historical_b["MULTI_MASS_93_WITNESS"]["upper_bound"],
            family_b["MULTI_MASS_93_WITNESS"]["upper_bound"],
        ),
    }
    manifest = _read(root, PRIOR_MANIFEST)
    frozen_sources = {item["path"]: item for item in manifest["COPIED_FILES"]}
    revisions = [
        {
            "path": path,
            "before_sha256": frozen_sources[path]["sha256"],
            "before_bytes": frozen_sources[path]["bytes"],
            "after_sha256": file_identity(root, path)["sha256"],
            "after_bytes": file_identity(root, path)["bytes"],
        }
        for path in sorted(REVISED_FROZEN_PATHS)
    ]
    return {
        "SCHEMA_VERSION": 1,
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "COMPLETE_ANALYTICAL_RECONCILIATION",
        "AUTHORITY_ROLE": "Corrected OFFICIAL_ANY_PRIZE K20 analytical bounds and closure states",
        "SUPERSEDES_K20_COUNT_DEPENDENT_CLAIMS_IN": PRIOR_AUTHORITY,
        "FROZEN_SOURCE_COMMIT": FROZEN_SOURCE_COMMIT,
        "EVENT": "OFFICIAL_ANY_PRIZE",
        "K": 20,
        "DENOMINATOR": OFFICIAL_ANY_PRIZE_DENOMINATOR,
        "INCUMBENT_EXACT_COUNT": incumbent_count,
        "INCUMBENT_PORTFOLIO_SHA256": entry.portfolio_sha256,
        "INCUMBENT_SOURCE": WINNER_RECORD,
        "HISTORICAL_COMPARISON_INCUMBENT": historical["K20_INCUMBENT"],
        "CANONICAL_SINGLE_OUTCOMES": SINGLE_TICKET_OUTCOMES,
        "CROSS_INVARIANTS": {
            "closed_form": int(closed_form),
            "identical_ticket_intersection": counts[6],
            "seven_set_formula": seven_set,
            "K20_S1": PORTFOLIO_S1,
        },
        "S1_CORRECTION": {
            "historical": historical_s1,
            "corrected": PORTFOLIO_S1,
            "difference": PORTFOLIO_S1 - historical_s1,
        },
        "FAMILY_BOUNDS": family_summaries,
        "K20_GLOBAL_CERTIFIED_BOUND": max(bounds.values()),
        "K20_REMAINING_GAP": max(bounds.values()) - incumbent_count,
        "GLOBAL_K20_OPTIMUM": "UNKNOWN",
        "CLOSED_SCOPE_TRANSITIONS": {
            name: {
                "historical_upper_bound": old,
                "corrected_upper_bound": new,
                "current_status": "CLOSED" if new <= incumbent_count else "OPEN",
            }
            for name, (old, new) in transitions.items()
        },
        "MASS_93_SUBFAMILIES_BY_HEAVY_COUNT": {
            h: {
                "upper_bound": row["upper_bound"],
                "status": "CLOSED" if row["upper_bound"] <= incumbent_count else "OPEN",
                "gap_to_incumbent": row["upper_bound"] - incumbent_count,
            }
            for h, row in family_b["MINIMUM_MASS_MULTI_BOUNDS_BY_HEAVY_COUNT"].items()
        },
        "ANALYTICAL_CERTIFICATES": {
            "OUTSIDE_MIN_S2": outside,
            "FAMILY_A": family_a,
            "FAMILY_B": family_b,
            "FAMILY_C_WEDGE": family_c,
        },
        "PAIR_INTERSECTION_TABLE": list(counts),
        "TRIPLE_PROFILE_TABLE_SHA256": triple_profile_table_sha256(),
        "SOURCE_REVISIONS": revisions,
        "CURRENT_IMPLEMENTATION_FILES": [
            file_identity(root, path) for path in CURRENT_IMPLEMENTATION_PATHS
        ],
        "PRESERVED_HISTORICAL_RECORDS": [
            file_identity(root, path) for path in ARCHIVED_RECORD_PATHS
        ],
        "HISTORICAL_POLICY": (
            "Preserve original certificates/manifests/receipts; source revisions are explicit"
        ),
        "CP_SAT_EVIDENCE_POLICY": (
            "NOT_REVALIDATED_NOT_ADMITTED; no archived solver bound translated"
        ),
        "CP_SAT": "NOT_RUN",
        "PILOT": "NOT_RUN",
        "NEW_FULL_EXACT_EVALUATIONS": 0,
        "NEW_PORTFOLIO_SEARCH": "NOT_RUN",
        "PRODUCTION_ADOPTION": "NOT_RUN",
    }
