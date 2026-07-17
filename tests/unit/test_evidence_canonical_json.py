"""Adversarial tests for LCJ-1 canonicalization and hashing (canonical_json.py).

The "committed contract JSON is canonical bytes plus one LF" and "every
embedded/raw-file hash independently recomputes" checks deliberately
reserialize/rehash using plain ``json``/``hashlib`` calls rather than
``lottolab.evidence.canonical_json`` itself, so the check is independent of
the module under test.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from lottolab.evidence import canonical_json

REPO_ROOT = Path(__file__).resolve().parents[2]

COMMITTED_CONTRACT_JSON_FILES = (
    REPO_ROOT / "contracts/evidence/canonical_evidence_registry.json",
    REPO_ROOT / "contracts/evidence/approved_ranking_policy_registry.json",
    REPO_ROOT / "contracts/evidence/metric_definitions/d3.json",
    REPO_ROOT / "contracts/evidence/strategy_evaluation_evidence.schema.json",
    REPO_ROOT / "contracts/evidence/dataset_snapshot.schema.json",
    REPO_ROOT / "contracts/evidence/ranking_policy.schema.json",
    REPO_ROOT / "contracts/evidence/metric_definition.schema.json",
    REPO_ROOT / "tests/fixtures/evidence/synthetic/dataset_snapshot.json",
    REPO_ROOT / "tests/fixtures/evidence/synthetic/evaluation_evidence.json",
    REPO_ROOT / "tests/fixtures/evidence/synthetic/historical_replay_evidence.json",
    REPO_ROOT / "tests/fixtures/evidence/synthetic/ranking_policy_draft.json",
    REPO_ROOT / "tests/fixtures/evidence/synthetic/metric_definition_hit_rate.json",
)


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_bytes())


def test_reordered_object_keys_hash_identically():
    a = {"b": 1, "a": 2, "nested": {"y": True, "x": "hi"}}
    b = {"nested": {"x": "hi", "y": True}, "a": 2, "b": 1}
    assert canonical_json.canonical_bytes(a) == canonical_json.canonical_bytes(b)
    assert canonical_json.sha256_hex(
        canonical_json.canonical_bytes(a)
    ) == canonical_json.sha256_hex(canonical_json.canonical_bytes(b))


def test_float_rejected():
    with pytest.raises(canonical_json.CanonicalizationError):
        canonical_json.validate_value_domain({"x": 1.5})


def test_nan_and_infinity_rejected():
    for text in ("NaN", "Infinity", "-Infinity"):
        with pytest.raises(canonical_json.CanonicalizationError):
            canonical_json.loads_canonical(f'{{"x": {text}}}')


def test_null_rejected():
    with pytest.raises(canonical_json.CanonicalizationError):
        canonical_json.validate_value_domain({"x": None})
    with pytest.raises(canonical_json.CanonicalizationError):
        canonical_json.loads_canonical('{"x": null}')


def test_bool_and_integer_both_accepted_and_distinguished():
    canonical_json.validate_value_domain({"flag": True, "n": 1})
    assert canonical_json.canonical_bytes({"x": True}) != canonical_json.canonical_bytes({"x": 1})


def test_integer_over_safe_bound_rejected():
    with pytest.raises(canonical_json.CanonicalizationError):
        canonical_json.validate_value_domain({"x": canonical_json.MAX_SAFE_INTEGER + 1})
    canonical_json.validate_value_domain({"x": canonical_json.MAX_SAFE_INTEGER})


def test_object_key_pattern_enforced():
    with pytest.raises(canonical_json.CanonicalizationError):
        canonical_json.validate_value_domain({"BadKey": 1})
    with pytest.raises(canonical_json.CanonicalizationError):
        canonical_json.validate_value_domain({"a-b": 1})
    with pytest.raises(canonical_json.CanonicalizationError):
        canonical_json.validate_value_domain({"": 1})
    canonical_json.validate_value_domain({"a_b2": 1})


def test_duplicate_key_rejected_during_parse():
    with pytest.raises(canonical_json.CanonicalizationError):
        canonical_json.loads_canonical('{"a": 1, "a": 2}')


def test_malformed_json_rejected_with_sanitized_error_and_preserved_cause():
    with pytest.raises(canonical_json.CanonicalizationError) as exc_info:
        canonical_json.loads_canonical(b'{"secret":"RAW_INPUT_MUST_NOT_LEAK",')

    assert str(exc_info.value) == "$: input is not valid UTF-8 JSON"
    assert isinstance(exc_info.value.__cause__, json.JSONDecodeError)
    assert "RAW_INPUT_MUST_NOT_LEAK" not in str(exc_info.value)


def test_invalid_utf8_rejected_with_sanitized_error_and_preserved_cause():
    with pytest.raises(canonical_json.CanonicalizationError) as exc_info:
        canonical_json.loads_canonical(b'\xff{"secret":"RAW_BYTES_MUST_NOT_LEAK"}')

    assert str(exc_info.value) == "$: input is not valid UTF-8 JSON"
    assert isinstance(exc_info.value.__cause__, UnicodeDecodeError)
    assert "RAW_BYTES_MUST_NOT_LEAK" not in str(exc_info.value)


def test_unknown_keys_rejected_where_contracts_are_closed():
    # closed-schema enforcement itself is a Pydantic (models.py) concern;
    # this only proves the LCJ-1 layer imposes no permissive key rewriting
    # that could mask an unexpected key from that later check.
    value = {"a": 1, "unexpected": 2}
    reparsed = canonical_json.loads_canonical(canonical_json.canonical_bytes(value))
    assert set(reparsed) == {"a", "unexpected"}


def test_self_key_removed_hash_exclusion_is_load_bearing():
    draft = {"a": 1, "b": 2, "self_hash": "0" * 64}
    naive_hash_including_self = canonical_json.sha256_hex(canonical_json.canonical_bytes(draft))
    excluded_hash = canonical_json.self_key_removed_sha256(draft, "self_hash")
    assert naive_hash_including_self != excluded_hash

    # changing the excluded field's own stored value must not change the hash
    draft_with_different_self_value = {**draft, "self_hash": "1" * 64}
    assert (
        canonical_json.self_key_removed_sha256(draft_with_different_self_value, "self_hash")
        == excluded_hash
    )

    # changing any other field must change the hash
    draft_with_changed_payload = {**draft, "a": 999}
    assert (
        canonical_json.self_key_removed_sha256(draft_with_changed_payload, "self_hash")
        != excluded_hash
    )


def test_self_key_removed_hash_requires_key_present():
    with pytest.raises(canonical_json.CanonicalizationError):
        canonical_json.self_key_removed_sha256({"a": 1}, "missing_key")


@pytest.mark.parametrize("path", COMMITTED_CONTRACT_JSON_FILES, ids=lambda p: p.name)
def test_committed_contract_json_is_canonical_bytes_plus_one_lf(path: Path):
    raw = path.read_bytes()
    assert raw.endswith(b"\n")
    assert not raw.endswith(b"\r\n")
    assert raw.count(b"\n") == 1
    assert b"\x00" not in raw  # no BOM/binary garbage
    body = raw[:-1]
    value = json.loads(body)
    reserialized = json.dumps(
        value, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    assert body == reserialized


def test_dataset_sha256_independently_recomputes():
    doc = _load(REPO_ROOT / "tests/fixtures/evidence/synthetic/dataset_snapshot.json")
    reduced = {k: v for k, v in doc.items() if k != "dataset_sha256"}
    reencoded = json.dumps(
        reduced, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    assert hashlib.sha256(reencoded).hexdigest() == doc["dataset_sha256"]


def test_artifact_content_sha256_independently_recomputes():
    doc = _load(REPO_ROOT / "tests/fixtures/evidence/synthetic/evaluation_evidence.json")
    reduced = {k: v for k, v in doc.items() if k != "artifact_content_sha256"}
    reencoded = json.dumps(
        reduced, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    assert hashlib.sha256(reencoded).hexdigest() == doc["artifact_content_sha256"]


def test_record_sha256_independently_recomputes_for_every_record():
    doc = _load(REPO_ROOT / "tests/fixtures/evidence/synthetic/evaluation_evidence.json")
    for record in doc["records"]:
        reduced = {k: v for k, v in record.items() if k != "record_sha256"}
        reencoded = json.dumps(
            reduced, ensure_ascii=False, separators=(",", ":"), sort_keys=True
        ).encode("utf-8")
        assert hashlib.sha256(reencoded).hexdigest() == record["record_sha256"]


def test_rule_parameters_sha256_independently_recomputes():
    doc = _load(REPO_ROOT / "tests/fixtures/evidence/synthetic/evaluation_evidence.json")
    rule_parameters = doc["rule_parameters"]
    reduced = {k: v for k, v in rule_parameters.items() if k != "rule_parameters_sha256"}
    reencoded = json.dumps(
        reduced, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    assert hashlib.sha256(reencoded).hexdigest() == rule_parameters["rule_parameters_sha256"]


def test_parameters_sha256_independently_recomputes():
    doc = _load(REPO_ROOT / "tests/fixtures/evidence/synthetic/evaluation_evidence.json")
    reencoded = json.dumps(
        doc["parameters"], ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    assert hashlib.sha256(reencoded).hexdigest() == doc["parameters_sha256"]


def test_feature_definition_sha256_matches_exact_committed_bytes():
    doc = _load(REPO_ROOT / "tests/fixtures/evidence/synthetic/evaluation_evidence.json")
    referenced = REPO_ROOT / doc["feature_definition_path"]
    assert hashlib.sha256(referenced.read_bytes()).hexdigest() == doc["feature_definition_sha256"]


def test_metric_definition_sha256_matches_exact_committed_bytes():
    doc = _load(REPO_ROOT / "tests/fixtures/evidence/synthetic/evaluation_evidence.json")
    for result in doc["metric_results"]:
        referenced = REPO_ROOT / result["metric_definition_path"]
        assert (
            hashlib.sha256(referenced.read_bytes()).hexdigest()
            == result["metric_definition_sha256"]
        )
