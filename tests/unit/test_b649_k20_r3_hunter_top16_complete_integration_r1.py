"""Focused acceptance against the real immutable donor topology, without solvers."""

from __future__ import annotations

import copy
import json
import subprocess
from pathlib import Path
from typing import Any, NoReturn, cast

import pytest

from lottolab.research import b649_k20_r3_hunter_top16_complete_integration_r1 as integration


@pytest.fixture(scope="module")
def inputs() -> dict[str, dict[str, Any]]:
    return integration.verify_sources()[1]


def forbidden(*_: object, **__: object) -> NoReturn:
    pytest.fail("forbidden proof, recertification, projection, census or solver")


def test_complete_integration_and_owner_transition(monkeypatch: pytest.MonkeyPatch) -> None:
    for module, names in (
        (integration.r24, ("pinned_r7_census", "run_chase", "replay_stored_result")),
        (integration.base, ("build_result", "adopt_state_certificate")),
        (integration.base.state, ("certify_member", "verify_member_certificate", "build_result")),
        (integration.r14, ("moment_certificate", "s4_child")),
        (integration.tail, ("uniform_certificate", "build_result", "minimizer_realization")),
    ):
        for name in names:
            monkeypatch.setattr(module, name, forbidden)
    result = integration.build_result()
    assert integration.__file__.startswith(str(integration.REPO_ROOT / "src"))
    assert result["STATE_TERM_COUNT"] == 23
    assert result["HUNTER_STATE_NEW_BOUND"] == 355_274_920
    assert result["TOP16_STATE_NEW_BOUND"] == 355_510_148
    assert result["START_COMPLETE_R3_UB"] == 355_722_668
    assert result["FINAL_COMPLETE_R3_UB"] == result["OTHER_STATE_MAX"] == 355_637_030
    assert result["CURRENT_INCUMBENT"] == 313_263_888
    assert result["REMAINING_GAP"] == 42_373_142
    assert result["TAIL_BOUND"] == 354_039_277
    assert result["CLASSIFIED_MAX"] == 355_468_904
    assert result["FINAL_OWNER_IDS"] == ["state:s2-13548976-s3-951748"]
    assert result["OWNER_TRANSITION"] == {
        "before": [integration.HUNTER_STATE],
        "after": ["state:s2-13548976-s3-951748"],
    }
    before = {r["stable_id"]: r["bound"] for r in result["START_STATE_TERMS"]}
    after = {r["stable_id"]: r["bound"] for r in result["FINAL_STATE_TERMS"]}
    assert len(before) == len(after) == 23
    changed = {key for key in before if before[key] != after[key]}
    assert changed == {integration.HUNTER_STATE, integration.TOP16_STATE}
    assert result["OTHER_STATE_TERMS_UNCHANGED"] == len(before.keys() - changed) == 21
    assert result["DUPLICATE_CORRECTIONS"] == 0
    assert result["WITNESS_SOUNDNESS_STATUS"] == "PASS_6_PORTFOLIOS_30_SUPPORT_WITNESSES"
    for key in (
        "HUNTER_THEOREM_REPROOF_CALLS",
        "HUNTER_MINIMIZATION_CALLS",
        "TOP16_PROJECTION_CALLS",
        "NEW_CERTIFICATION_CALLS",
        "R7_CENSUS_REBUILD_CALLS",
    ):
        assert result[key] == 0
    assert result["NEW_HEAVY_SOLVER_STARTED"] == result["R25_STARTED"] == "NO"
    assert result["PRODUCTION_MUTATION"] == "NONE"


def test_donor_reads_ignore_checkout_files(monkeypatch: pytest.MonkeyPatch) -> None:
    original = Path.read_bytes

    def read(path: Path) -> bytes:
        if any(
            stem in path.name for stem in ("hunter", "state_14122976_top16", "state-14122976-top16")
        ):
            pytest.fail("donor checkout bytes were used")
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", read)
    identities, _ = integration.verify_sources()
    assert identities["HUNTER"]["head"] == integration.HUNTER_DONOR_HEAD
    assert identities["TOP16"]["head"] == integration.TOP16_DONOR_HEAD


@pytest.mark.parametrize("name", ["HUNTER", "TOP16"])
@pytest.mark.parametrize("kind", ["source", "result"])
@pytest.mark.parametrize("failure", ["tampered", "missing"])
def test_bad_donor_objects_rejected(
    name: str, kind: str, failure: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = integration.git_bytes
    head = integration.SOURCE_PINS[name][0]
    path = integration.source_paths(name)[kind == "result"]

    def changed(*args: str) -> bytes:
        if args == ("show", f"{head}:{path}"):
            if failure == "missing":
                raise subprocess.CalledProcessError(128, ["git", *args])
            return original(*args) + b" "
        return original(*args)

    monkeypatch.setattr(integration, "git_bytes", changed)
    with pytest.raises(AssertionError, match=r"SHA mismatch|missing immutable object"):
        integration.verify_sources()


@pytest.mark.parametrize("kind", ["tree", "ancestry", "shared_science"])
def test_incompatible_authority_rejected(kind: str, monkeypatch: pytest.MonkeyPatch) -> None:
    original = integration.git_bytes
    scientific = "src/lottolab/research/b649_k20_r3_anchor_incidence_bound_r5.py"

    def changed(*args: str) -> bytes:
        if kind == "tree" and args == ("rev-parse", f"{integration.HUNTER_DONOR_HEAD}^{{tree}}"):
            return b"wrong tree\n"
        if kind == "ancestry" and args == (
            "merge-base",
            integration.BASE_HEAD,
            integration.HUNTER_DONOR_HEAD,
        ):
            return b"wrong common ancestor\n"
        if kind == "shared_science" and args == ("show", f"{integration.R24_HEAD}:{scientific}"):
            return original(*args) + b" "
        return original(*args)

    monkeypatch.setattr(integration, "git_bytes", changed)
    with pytest.raises(
        AssertionError, match=r"tree identity|common ancestry|common R24 scientific"
    ):
        integration.verify_sources()


def test_complete_member_coverage_and_preservation(inputs: dict[str, dict[str, Any]]) -> None:
    hunter = integration.adopt_hunter(inputs["HUNTER"], inputs["SIBLING"], inputs["R24"])
    top = integration.adopt_top16(inputs["TOP16"], inputs["BASE"])
    assert (hunter["compressed_members"], hunter["represented_vectors"]) == (582, 633)
    assert (top["compressed_members"], top["represented_vectors"]) == (214, 221)
    assert hunter["adopted_member_certificates"] == 6
    assert top["adopted_member_certificates"] == 16
    assert hunter["carried_members"] == 576
    assert top["carried_members"] == 198
    assert (
        sum(r["final_bound"] == r["prior_valid_bound"] for r in hunter["complete_region_members"])
        == 576
    )
    assert (
        sum(r["final_bound"] == r["prior_valid_bound"] for r in top["complete_region_members"])
        == 198
    )
    assert hunter["legal_portfolio_witnesses_validated"] == 6
    assert top["support_witnesses_validated"] == 30
    compressed = [r for r in top["complete_region_members"] if len(r["represented_vectors"]) == 2]
    assert len(compressed) == 7
    assert any(min(r["represented_vectors"]) != r["member"]["witness_counts"] for r in compressed)
    assert all(
        integration.r24.sparse(min(integration.dense(v) for v in r["represented_vectors"]))
        == r["member"]["witness_counts"]
        for r in compressed
    )
    assert all(r["final_bound"] == r["prior_valid_bound"] for r in compressed)


@pytest.mark.parametrize(
    "kind",
    [
        "missing_region_member",
        "missing_certificate",
        "member_counts",
        "sum_credit",
        "illegal_witness",
        "compressed_bound",
    ],
)
def test_hunter_tampering_rejected(kind: str, inputs: dict[str, dict[str, Any]]) -> None:
    donor, authority = copy.deepcopy(inputs["HUNTER"]), copy.deepcopy(inputs["R24"])
    region = next(
        r
        for r in authority["STATE_REGION_CERTIFICATES"]
        if r["owner_id"] == integration.HUNTER_STATE
    )
    record = donor["MEMBER_CERTIFICATES"]["[0,13][5,5]"]
    if kind == "missing_region_member":
        region["complete_region_members"].pop()
    elif kind == "missing_certificate":
        donor["MEMBER_CERTIFICATES"].pop("[0,13][5,5]")
    elif kind == "member_counts":
        record["MEMBER_COUNTS"] = [[0, 12], [5, 6]]
    elif kind == "sum_credit":
        terms = record["CORRECTIONS"]
        terms["CERTIFIED_CORRECTION"] = terms["R5_FOREST"] + terms["HUNTER_CLASS_SPLIT"]
    elif kind == "illegal_witness":
        record["WITNESS"]["RESIDUAL_TICKETS"][0][0] = 50
    else:
        row = next(
            r for r in region["complete_region_members"] if r["represented_vector_count"] > 1
        )
        row["final_bound"] -= 1
    with pytest.raises(
        AssertionError, match=r"identity|completeness|arithmetic|illegal|preservation"
    ):
        integration.adopt_hunter(donor, inputs["SIBLING"], authority)


@pytest.mark.parametrize(
    "kind",
    [
        "missing_member",
        "missing_certificate",
        "duplicate_certificate",
        "duplicate_vector",
        "remainder_credit",
        "sum_credit",
        "wrong_dual",
        "illegal_witness",
        "compression",
        "wrong_base",
    ],
)
def test_top16_tampering_rejected(kind: str, inputs: dict[str, dict[str, Any]]) -> None:
    donor = copy.deepcopy(inputs["TOP16"])
    record = donor["NEW_MEMBER_CERTIFICATES"][0]
    rows = donor["COMPLETE_REGION_MEMBERS"]
    if kind == "missing_member":
        rows.pop()
    elif kind == "missing_certificate":
        donor["NEW_MEMBER_CERTIFICATES"].pop()
    elif kind == "duplicate_certificate":
        donor["NEW_MEMBER_CERTIFICATES"][-1] = copy.deepcopy(record)
    elif kind == "duplicate_vector":
        rows[-1]["represented_vectors"] = rows[-2]["represented_vectors"]
    elif kind == "remainder_credit":
        next(r for r in rows if r["final_bound"] == r["prior_valid_bound"])["final_bound"] -= 1
    elif kind == "sum_credit":
        record["member_certified_correction"] += record["prior_applied_correction"]
    elif kind == "wrong_dual":
        record["vector_certificates"][0]["multiplicity_cap"] = 17
    elif kind == "illegal_witness":
        record["support_witnesses"][0]["support_witness"][0][0] = 50
    elif kind == "compression":
        next(r for r in rows if len(r["represented_vectors"]) == 2)["member"][
            "represented_vector_count"
        ] = 1
    else:
        donor["BASE_STATE_TERMS"][0]["bound"] -= 1
    with pytest.raises(
        AssertionError, match=r"identity|coverage|preservation|arithmetic|illegal|compression"
    ):
        integration.adopt_top16(donor, inputs["BASE"])


def test_weakest_compressed_vector_correction() -> None:
    assert integration.effective_correction(20, (25, 40)) == 25
    assert integration.effective_correction(30, (25, 40)) == 30
    assert integration.effective_correction(20, (40, 25)) == 25
    with pytest.raises(AssertionError, match="missing or invalid"):
        integration.effective_correction(20, ())


def test_full_result_deterministic_reproduction() -> None:
    saved = cast(dict[str, Any], json.loads(integration.RESULT_PATH.read_text()))
    assert integration.verify_result(saved) == {"status": "PASS"}
    assert integration.encode(saved).encode() == integration.RESULT_PATH.read_bytes()


@pytest.mark.parametrize(
    "key", ["FINAL_COMPLETE_R3_UB", "FINAL_OWNER_IDS", "FINAL_STATE_TERMS", "TOP16_ADOPTION"]
)
def test_result_tampering_rejected(key: str, monkeypatch: pytest.MonkeyPatch) -> None:
    saved = cast(dict[str, Any], json.loads(integration.RESULT_PATH.read_text()))
    changed = copy.deepcopy(saved)
    changed[key] = "tampered"
    monkeypatch.setattr(integration, "build_result", lambda: saved)
    with pytest.raises(AssertionError, match="reproduce deterministically"):
        integration.verify_result(changed)
