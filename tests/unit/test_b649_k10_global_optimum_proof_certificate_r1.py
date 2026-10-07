"""Portable certificate checks for the sealed K10 OFFICIAL_ANY_PRIZE proof."""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from typing import cast

from lottolab.research.b649_k10_mass_ge21_sequential_exact_u3_r1 import (
    PRIOR_CLOSED_PROFILES,
    derive_full_support_profiles,
)

ROOT = Path(__file__).resolve().parents[2]
CERTIFICATE_PATH = (
    "docs/research/matrix-native-results/b649-k10-global-optimum-proof-certificate-r1.json"
)
INCUMBENT_COUNT = 176_345_645
PORTFOLIO_SHA256 = "13b1126d5b26ce44c9aba24670142eeab49f4a4b51aaf3bbabe7a7f1659ac673"
CERTIFICATE_FILE_SHA256 = "01593c10632cadb81bd70976aca99faa03320235a15996efde32a720768a77dd"


def _as_dict(value: object) -> dict[str, object]:
    assert isinstance(value, dict)
    return cast(dict[str, object], value)


def _as_list(value: object) -> list[object]:
    assert isinstance(value, list)
    return cast(list[object], value)


def _as_str(value: object) -> str:
    assert isinstance(value, str)
    return value


def _as_int(value: object) -> int:
    assert isinstance(value, int)
    return value


def _read_record(relative_path: str) -> dict[str, object]:
    path = Path(relative_path)
    assert not path.is_absolute()
    assert ".." not in path.parts
    decoded = json.loads((ROOT / path).read_text(encoding="utf-8"))
    return _as_dict(decoded)


def _canonical_sha256(payload: dict[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256(encoded).hexdigest()


def _file_references(value: object) -> list[dict[str, object]]:
    references: list[dict[str, object]] = []
    if isinstance(value, dict):
        mapping = cast(dict[str, object], value)
        if isinstance(mapping.get("path"), str) and isinstance(mapping.get("sha256"), str):
            references.append(mapping)
        for child in mapping.values():
            references.extend(_file_references(child))
    elif isinstance(value, list):
        for child in cast(list[object], value):
            references.extend(_file_references(child))
    return references


def _certificate() -> tuple[dict[str, object], dict[str, object]]:
    certificate = _read_record(CERTIFICATE_PATH)
    return certificate, _as_dict(certificate["payload"])


def test_certificate_hashes_and_sealed_incumbent_identity() -> None:
    certificate, payload = _certificate()

    certificate_file = ROOT / CERTIFICATE_PATH
    assert sha256(certificate_file.read_bytes()).hexdigest() == CERTIFICATE_FILE_SHA256
    assert certificate["certificate_id"] == "B649_K10_GLOBAL_OPTIMUM_PROOF_CERTIFICATE_R1"
    assert certificate["payload_sha256"] == _canonical_sha256(payload)
    assert payload["K10_GLOBAL_OPTIMUM_STATUS"] == "PROVEN"

    incumbent = _as_dict(payload["incumbent"])
    assert incumbent["ticket_count"] == 10
    assert incumbent["outcome_count"] == INCUMBENT_COUNT
    assert incumbent["portfolio_sha256"] == PORTFOLIO_SHA256
    assert incumbent["official_any_prize_probability"] == "536005/1827672"

    sealed_source = _as_dict(incumbent["sealed_source"])
    source_path = _as_str(sealed_source["path"])
    source = (ROOT / source_path).read_text(encoding="utf-8")
    assert f'portfolio_sha256="{PORTFOLIO_SHA256}"' in source
    assert "official_any_prize_probability=Fraction(536005, 1827672)" in source

    event = _as_dict(payload["event"])
    assert event["name"] == "OFFICIAL_ANY_PRIZE"
    reduction = _as_dict(payload["full_support_reduction"])
    assert reduction["status"] == "PROVED"


def test_all_mass_closure_authorities_resolve_to_portable_files() -> None:
    _, payload = _certificate()
    references = _file_references(payload)
    assert len(references) >= 15
    for reference in references:
        relative_path = _as_str(reference["path"])
        path = Path(relative_path)
        assert not path.is_absolute()
        assert ".." not in path.parts
        target = ROOT / path
        assert target.is_file()
        assert not target.is_symlink()
        assert sha256(target.read_bytes()).hexdigest() == reference["sha256"]

    closure_records = [_as_dict(item) for item in _as_list(payload["closures"])]
    covered_masses: set[int] = set()
    for closure in closure_records:
        assert closure["status"] == "CLOSED"
        bounds = [_as_int(item) for item in _as_list(closure["mass_range"])]
        assert len(bounds) == 2
        lower, upper = bounds
        for mass in range(lower, upper + 1):
            assert mass not in covered_masses
            covered_masses.add(mass)
    assert covered_masses == set(range(11, 49))


def test_mass11_through_mass48_closure_records_are_complete() -> None:
    _, payload = _certificate()
    closures = [_as_dict(item) for item in _as_list(payload["closures"])]
    mass11_12 = next(item for item in closures if item["mass_range"] == [11, 12])
    prior_certificate_ref = _as_dict(_as_list(mass11_12["authorities"])[0])
    prior_certificate = _read_record(_as_str(prior_certificate_ref["path"]))

    incumbent = _as_dict(prior_certificate["incumbent"])
    assert incumbent["outcome_count"] == INCUMBENT_COUNT
    assert incumbent["portfolio_sha256"] == PORTFOLIO_SHA256
    shells = _as_dict(prior_certificate["shells"])
    assert _as_dict(shells["mass_11"])["status"] == "EXHAUSTED_EXACT"
    assert _as_dict(shells["mass_12"])["status"] == "EXHAUSTED_BOUND_SCREEN"

    mass13_20 = next(item for item in closures if item["mass_range"] == [13, 20])
    authorities = [_as_dict(item) for item in _as_list(mass13_20["authorities"])]
    mass13_17 = next(item for item in authorities if item.get("masses") == [13, 14, 15, 16, 17])
    runner = _as_dict(mass13_17["runner"])
    runner_source = (ROOT / _as_str(runner["path"])).read_text(encoding="utf-8")
    expected_modes = {
        "mass13-recheck": "build_mass13_recheck_result",
        "mass14": "build_mass14_result",
        "mass15": "build_mass15_result",
        "mass16": "build_mass16_result",
        "mass17": "build_mass17_result",
    }
    assert mass13_17["modes"] == list(expected_modes)
    assert all(f"def {symbol}(" in runner_source for symbol in expected_modes.values())

    mass18_20 = [item for item in authorities if isinstance(item.get("mass"), int)]
    assert {item["mass"] for item in mass18_20} == {18, 19, 20}
    for authority in mass18_20:
        mass = _as_int(authority["mass"])
        result_ref = _as_dict(authority["result"])
        result = _read_record(_as_str(result_ref["path"]))
        assert result[f"MASS{mass}_STATUS"] == "CLOSED"
        assert result["INCUMBENT_COUNT"] == INCUMBENT_COUNT
        assert result["RESULT_SHA256"] == result_ref["result_payload_sha256"]
        result_payload = {key: value for key, value in result.items() if key != "RESULT_SHA256"}
        assert _canonical_sha256(result_payload) == result["RESULT_SHA256"]
        profile_records = [
            _as_dict(value) for key, value in result.items() if key.startswith("PROFILE_")
        ]
        assert len(profile_records) == result[f"MASS{mass}_PROFILE_COUNT"]
        assert profile_records
        assert all(record["PROFILE_STATUS"] == "CLOSED_BY_EXACT_U3" for record in profile_records)
        assert all(_as_int(record["MAX_LEGAL_U3"]) < INCUMBENT_COUNT for record in profile_records)

    mass21_48 = next(item for item in closures if item["mass_range"] == [21, 48])
    ledger_ref = _as_dict(mass21_48["result_ledger"])
    assert ledger_ref["payload_sha256"] == (
        "5e42412e1d065db8f495756385a58cb3aa625a64e7fe4c2deda265a372790120"
    )
    ledger = _read_record(_as_str(ledger_ref["path"]))
    ledger_payload = {key: value for key, value in ledger.items() if key != "RESULT_PAYLOAD_SHA256"}
    assert _canonical_sha256(ledger_payload) == ledger["RESULT_PAYLOAD_SHA256"]
    assert ledger["RESULT_PAYLOAD_SHA256"] == ledger_ref["payload_sha256"]
    assert ledger["K10_GLOBAL_OPTIMUM_STATUS"] == "PROVEN"

    profile_records = [_as_dict(value) for value in _as_list(ledger["PROFILE_RESULTS"])]
    assert len(profile_records) == mass21_48["profile_result_count"] == 34
    assert all(record["PROFILE_STATUS"] == "CLOSED_BY_EXACT_U3" for record in profile_records)
    assert all(record["INCUMBENT_COUNT"] == INCUMBENT_COUNT for record in profile_records)
    assert all(_as_int(record["MAX_LEGAL_U3"]) < INCUMBENT_COUNT for record in profile_records)

    prior_check = _as_dict(ledger["PRIOR_MASS11_20_PROFILE_SET_CHECK"])
    assert prior_check["STATUS"] == "PASS"
    assert prior_check["CENSUSES_RERUN"] is False
    checks = [_as_dict(value) for value in _as_list(prior_check["MASS_PROFILE_CHECKS"])]
    assert {_as_int(check["MASS"]) for check in checks} == set(range(11, 21))

    # This checks only the full-support profile catalog; it does not run a U3 census.
    derived = set(derive_full_support_profiles())
    prior = {
        (mass, profile) for mass, profiles in PRIOR_CLOSED_PROFILES.items() for profile in profiles
    }
    assert len(derived) == 54
    assert len(prior) == 20
    assert prior == {entry for entry in derived if 11 <= entry[0] <= 20}
    assert {(record["MASS"], tuple(_as_list(record["PROFILE"]))) for record in profile_records} == {
        entry for entry in derived if entry[0] >= 21
    }
