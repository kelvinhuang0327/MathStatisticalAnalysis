"""Unit tests for offline verified evidence query CLI and API."""
from __future__ import annotations

import io
import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from lottolab.research import (
    b649_k20_three_certificate_composition_r1 as composition,
)
from tools import query_b649_k20_verified_evidence_r1 as query_tool


def test_four_certified_queries_direct_api():
    t249_res = query_tool.query_verified_evidence("T249", "FAMILY")
    assert t249_res["PROFILE_ID"] == composition.T249_PROFILE
    assert t249_res["METHOD_IDENTITY"] == composition.FAMILY_METHOD
    assert t249_res["CERTIFIED_BOUND"] == 313121137
    assert t249_res["SOURCE_COMMIT"] == "e0d27985b87399e47c59840fc0424bde28032885"
    assert t249_res["PROOF_SCOPE"] == f"PROFILE_{composition.T249_PROFILE}_LOCAL_BOUND_ONLY"
    assert t249_res["FULL_FAMILY_CLOSURE"] == "NOT_CLAIMED"
    assert t249_res["GLOBAL_OPTIMUM"] == "NOT_CLAIMED"

    t251_res = query_tool.query_verified_evidence("T251", "FAMILY")
    assert t251_res["PROFILE_ID"] == composition.T251_PROFILE
    assert t251_res["METHOD_IDENTITY"] == composition.FAMILY_METHOD
    assert t251_res["CERTIFIED_BOUND"] == 313142921
    assert t251_res["SOURCE_COMMIT"] == "e0d27985b87399e47c59840fc0424bde28032885"
    assert t251_res["PROOF_SCOPE"] == f"PROFILE_{composition.T251_PROFILE}_LOCAL_BOUND_ONLY"
    assert t251_res["FULL_FAMILY_CLOSURE"] == "NOT_CLAIMED"
    assert t251_res["GLOBAL_OPTIMUM"] == "NOT_CLAIMED"

    ccz_fam_res = query_tool.query_verified_evidence("CCZ236", "FAMILY")
    assert ccz_fam_res["PROFILE_ID"] == composition.CCZ_PROFILE
    assert ccz_fam_res["METHOD_IDENTITY"] == composition.FAMILY_METHOD
    assert ccz_fam_res["CERTIFIED_BOUND"] == 313250644
    assert ccz_fam_res["SOURCE_COMMIT"] == "e0d27985b87399e47c59840fc0424bde28032885"
    assert ccz_fam_res["PROOF_SCOPE"] == f"PROFILE_{composition.CCZ_PROFILE}_LOCAL_BOUND_ONLY"
    assert ccz_fam_res["FULL_FAMILY_CLOSURE"] == "NOT_CLAIMED"
    assert ccz_fam_res["GLOBAL_OPTIMUM"] == "NOT_CLAIMED"

    ccz_bonf_res = query_tool.query_verified_evidence("CCZ236", "BONF64")
    assert ccz_bonf_res["PROFILE_ID"] == composition.CCZ_PROFILE
    assert ccz_bonf_res["METHOD_IDENTITY"] == composition.BONF64_METHOD
    assert ccz_bonf_res["CERTIFIED_BOUND"] == 313091112
    assert ccz_bonf_res["SOURCE_COMMIT"] == "e0d27985b87399e47c59840fc0424bde28032885"
    assert ccz_bonf_res["PROOF_SCOPE"] == f"PROFILE_{composition.CCZ_PROFILE}_LOCAL_BOUND_ONLY"
    assert ccz_bonf_res["FULL_FAMILY_CLOSURE"] == "NOT_CLAIMED"
    assert ccz_bonf_res["GLOBAL_OPTIMUM"] == "NOT_CLAIMED"


def test_four_certified_queries_cli_main(monkeypatch):
    test_cases = [
        ("T249", "FAMILY", 313121137, composition.FAMILY_METHOD),
        ("T251", "FAMILY", 313142921, composition.FAMILY_METHOD),
        ("CCZ236", "FAMILY", 313250644, composition.FAMILY_METHOD),
        ("CCZ236", "BONF64", 313091112, composition.BONF64_METHOD),
    ]

    for profile, method, expected_bound, expected_method in test_cases:
        buf = io.StringIO()
        monkeypatch.setattr(sys, "stdout", buf)
        exit_code = query_tool.main(["--profile", profile, "--method", method])
        assert exit_code == 0
        parsed = json.loads(buf.getvalue())
        assert parsed["CERTIFIED_BOUND"] == expected_bound
        assert parsed["METHOD_IDENTITY"] == expected_method
        assert parsed["SOURCE_COMMIT"] == "e0d27985b87399e47c59840fc0424bde28032885"
        assert parsed["FULL_FAMILY_CLOSURE"] == "NOT_CLAIMED"
        assert parsed["GLOBAL_OPTIMUM"] == "NOT_CLAIMED"


def test_all_profile_and_method_aliases():
    aliases = [
        ("T249", "FAMILY", 313121137),
        ("65555555555541000000", "FAMILY", 313121137),
        ("T249", "FAMILY_BOUND", 313121137),
        ("T251", "FAMILY", 313142921),
        ("66555555555531000000", "FAMILY", 313142921),
        ("T251", "FAMILY_BOUND", 313142921),
        ("CCZ", "FAMILY", 313250644),
        ("CCZ236", "FAMILY", 313250644),
        ("55555555555551000000", "FAMILY", 313250644),
        ("CCZ236", "FAMILY_BOUND", 313250644),
        ("CCZ", "BONF64", 313091112),
        ("CCZ236", "BONF64", 313091112),
        ("55555555555551000000", "BONF64", 313091112),
        ("CCZ236", "BONF64_BOUND", 313091112),
        ("CCZ236", composition.BONF64_METHOD, 313091112),
    ]

    for p, m, expected in aliases:
        res = query_tool.query_verified_evidence(p, m)
        assert res["CERTIFIED_BOUND"] == expected


def test_method_isolation_ccz():
    evidence = composition.build_verified_evidence_set()
    ccz_family = query_tool.query_verified_evidence("CCZ236", "FAMILY", evidence_set=evidence)
    ccz_bonf64 = query_tool.query_verified_evidence("CCZ236", "BONF64", evidence_set=evidence)

    assert ccz_family["CERTIFIED_BOUND"] == 313250644
    assert ccz_bonf64["CERTIFIED_BOUND"] == 313091112
    assert ccz_family["CERTIFIED_BOUND"] != ccz_bonf64["CERTIFIED_BOUND"]
    assert ccz_family["METHOD_IDENTITY"] == composition.FAMILY_METHOD
    assert ccz_bonf64["METHOD_IDENTITY"] == composition.BONF64_METHOD
    assert evidence.family_maximum == 313263888


def test_cli_subprocess_execution():
    tool_path = Path(query_tool.__file__).resolve()
    repo_root = tool_path.parents[1]

    cmd = [
        sys.executable,
        str(tool_path),
        "--profile",
        "CCZ236",
        "--method",
        "BONF64",
    ]
    proc = subprocess.run(
        cmd,
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    parsed = json.loads(proc.stdout)
    assert parsed["PROFILE_ID"] == "55555555555551000000"
    assert parsed["CERTIFIED_BOUND"] == 313091112
    assert parsed["METHOD_IDENTITY"] == composition.BONF64_METHOD


def test_fail_closed_unknown_profile(monkeypatch):
    with pytest.raises(query_tool.VerifiedEvidenceQueryError, match="UNKNOWN_PROFILE"):
        query_tool.query_verified_evidence("55555555555551999999", "FAMILY")

    with pytest.raises(query_tool.VerifiedEvidenceQueryError, match="UNKNOWN_PROFILE"):
        query_tool.query_verified_evidence("UNKNOWN_PROFILE", "FAMILY")

    buf = io.StringIO()
    monkeypatch.setattr(sys, "stderr", buf)
    code = query_tool.main(["--profile", "UNKNOWN_PROFILE", "--method", "FAMILY"])
    assert code != 0
    assert "UNKNOWN_PROFILE" in buf.getvalue()


def test_fail_closed_unknown_method(monkeypatch):
    with pytest.raises(query_tool.VerifiedEvidenceQueryError, match="UNKNOWN_METHOD"):
        query_tool.query_verified_evidence("T249", "UNAPPROVED_METHOD")

    buf = io.StringIO()
    monkeypatch.setattr(sys, "stderr", buf)
    code = query_tool.main(["--profile", "T249", "--method", "UNAPPROVED_METHOD"])
    assert code != 0
    assert "UNKNOWN_METHOD" in buf.getvalue()


def test_fail_closed_wrong_profile_method_mapping(monkeypatch):
    with pytest.raises(query_tool.VerifiedEvidenceQueryError, match="WRONG_PROFILE_METHOD_MAPPING"):
        query_tool.query_verified_evidence("T249", "BONF64")

    with pytest.raises(query_tool.VerifiedEvidenceQueryError, match="WRONG_PROFILE_METHOD_MAPPING"):
        query_tool.query_verified_evidence("T251", "BONF64")

    buf = io.StringIO()
    monkeypatch.setattr(sys, "stderr", buf)
    code = query_tool.main(["--profile", "T249", "--method", "BONF64"])
    assert code != 0
    assert "WRONG_PROFILE_METHOD_MAPPING" in buf.getvalue()


def test_fail_closed_bonf64_as_family(monkeypatch):
    # If CCZ family bound is tampered to equal bonf64 bound, query fails
    monkeypatch.setattr(composition, "CCZ_FAMILY_BOUND", composition.CCZ_BONF64_BOUND)
    with pytest.raises((query_tool.VerifiedEvidenceQueryError, composition.CompositionValidationError)):
        query_tool.query_verified_evidence("CCZ236", "FAMILY")


def test_fail_closed_third_family_override(monkeypatch):
    real_overlay = composition.overlay.build_verified_overlay()
    tampered = replace(
        real_overlay,
        _overrides=real_overlay._overrides
        + (("55555555555551000000", composition.CCZ_BONF64_BOUND),),
    )
    monkeypatch.setattr(
        composition.overlay, "build_verified_overlay", lambda: tampered
    )

    with pytest.raises((query_tool.VerifiedEvidenceQueryError, composition.CompositionValidationError)):
        query_tool.query_verified_evidence("T249", "FAMILY")


def test_fail_closed_wrong_ccz_source_role(monkeypatch):
    monkeypatch.setattr(composition, "CCZ_RESULT_SHA256", "0" * 64)
    with pytest.raises((query_tool.VerifiedEvidenceQueryError, composition.CompositionValidationError)):
        query_tool.query_verified_evidence("CCZ236", "BONF64")


def test_fail_closed_wrong_bound(monkeypatch):
    monkeypatch.setattr(
        composition,
        "query_certified_bound",
        lambda p, m: 999999999,
    )
    with pytest.raises(query_tool.VerifiedEvidenceQueryError, match="WRONG_BOUND"):
        query_tool.query_verified_evidence("T249", "FAMILY")


def test_fail_closed_false_family_closure(monkeypatch):
    real_build = composition.build_verified_evidence_set
    def mock_build():
        es = real_build()
        # Mock full_family_closure property
        class FakeEvidenceSet:
            def __getattr__(self, name):
                return getattr(es, name)
            @property
            def full_family_closure(self):
                return "PROVED"
            @property
            def family_maximum(self):
                return es.family_maximum
            def query_certified_bound(self, p, m):
                return es.query_certified_bound(p, m)
        return FakeEvidenceSet()

    monkeypatch.setattr(composition, "build_verified_evidence_set", mock_build)
    with pytest.raises(query_tool.VerifiedEvidenceQueryError, match="FALSE_FAMILY_CLOSURE"):
        query_tool.query_verified_evidence("T249", "FAMILY")


def test_frozen_inputs_and_provenance_integrity():
    assert query_tool.FROZEN_FAMILY_HEAD == "e6fee5ebbfb972a1432bbc10ab5a337feac38478"
    assert query_tool.FROZEN_FAMILY_RESULT_SHA256 == "fef709c5168afa6da26ce18e0be78c40a12c6a711dec364e42659e1bb309d7b6"
    assert query_tool.VERIFIED_SOURCE_COMMIT == "e0d27985b87399e47c59840fc0424bde28032885"
    assert query_tool.FAMILY_MAXIMUM == 313263888
