"""Focused tests for source-only Wave 26 injected binding resolution."""

from __future__ import annotations

import hashlib
import importlib
import sqlite3
from pathlib import Path

import pytest
from tools import resolve_wave26_dynamic_bindings as resolution

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_static_injected_dependency_resolves_concrete_implementation() -> None:
    source = '''
def implementation(value):
    return value

def authority(value):
    return implementation(value)

def compose(adapter_factory):
    return adapter_factory(wave26_authority=authority)
'''

    result = resolution.resolve_injected_provider_source(source)

    assert result.classification == "RESOLVED_STATIC_IMPLEMENTATION"
    assert result.binding_kind == "DIRECT_STATIC_PROVIDER"
    assert result.provider_locator == "fixture/composition.py:5:authority"
    assert result.provider_target_locator == "fixture/composition.py:2:implementation"
    assert result.runtime_data_effect == "NO"


def test_runtime_factory_identity_is_resolved_without_claiming_returned_callable() -> None:
    source = '''
def build_authority(configuration):
    return lambda value: (configuration, value)

def compose(adapter_factory, configuration):
    return adapter_factory(
        wave26_authority=build_authority(configuration),
    )
'''

    result = resolution.resolve_injected_provider_source(source)

    assert result.classification == "RESOLVED_RUNTIME_FACTORY_IDENTITY"
    assert result.binding_kind == "STATIC_RUNTIME_FACTORY"
    assert result.provider_locator == "fixture/composition.py:2:build_authority"
    assert result.provider_target_locator is None
    assert result.runtime_data_effect == "YES"


def test_runtime_data_dependent_provider_remains_unresolved() -> None:
    source = '''
def compose(adapter_factory, providers, strategy_id):
    return adapter_factory(wave26_authority=providers[strategy_id])
'''

    result = resolution.resolve_injected_provider_source(source)

    assert result.classification == "REMAINS_RUNTIME_DATA_DEPENDENT"
    assert result.binding_kind == "RUNTIME_PROVIDER_EXPRESSION"
    assert result.provider_locator is None
    assert result.runtime_data_effect == "YES"


def test_multiple_distinct_providers_are_ambiguous() -> None:
    source = '''
def first(value):
    return value

def second(value):
    return value

def compose(adapter_factory, choose_first):
    if choose_first:
        return adapter_factory(wave26_authority=first)
    return adapter_factory(wave26_authority=second)
'''

    result = resolution.resolve_injected_provider_source(source)

    assert result.classification == "AMBIGUOUS_BINDING"
    assert result.binding_kind == "MULTIPLE_DISTINCT_INJECTION_EXPRESSIONS"
    assert len(result.injection_locators) == 2
    assert result.runtime_data_effect == "UNKNOWN"


def test_actual_source_analysis_never_imports_runtime_or_materializes_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden_connect(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("database materialization is forbidden")

    def forbidden_import(name: str, package: str | None = None) -> None:
        del name, package
        raise AssertionError("runtime module import is forbidden")

    monkeypatch.setattr(sqlite3, "connect", forbidden_connect)
    monkeypatch.setattr(importlib, "import_module", forbidden_import)

    result = resolution.analyze_source_tree(REPO_ROOT)
    records = result["records"]

    assert isinstance(records, list)
    assert len(records) == 4
    assert all(
        isinstance(record, dict)
        and record["final_resolution_classification"]
        == "RESOLVED_STATIC_IMPLEMENTATION"
        and record["runtime_data_contents_affect_implementation_identity"] == "NO"
        for record in records
    )


def test_structural_source_fingerprints_are_deterministic_and_distinct() -> None:
    first = resolution.analyze_source_tree(REPO_ROOT)
    second = resolution.analyze_source_tree(REPO_ROOT)
    first_records = first["records"]
    second_records = second["records"]

    assert isinstance(first_records, list)
    assert isinstance(second_records, list)
    assert first_records == second_records
    fingerprints: set[str] = set()
    source_digests: set[str] = set()
    for record in first_records:
        assert isinstance(record, dict)
        fingerprint = record["supplemental_binding_fingerprint_sha256"]
        source_digest = record["structural_source_digest_sha256"]
        assert isinstance(fingerprint, str)
        assert isinstance(source_digest, str)
        fingerprints.add(fingerprint)
        source_digests.add(source_digest)
    assert len(fingerprints) == 4
    assert len(source_digests) == 4


def test_canonical_result_and_report_output_are_deterministic() -> None:
    first = resolution.analyze_source_tree(REPO_ROOT)
    second = resolution.analyze_source_tree(REPO_ROOT)
    first_bytes = resolution.canonical_json_bytes(first)
    second_bytes = resolution.canonical_json_bytes(second)

    assert first_bytes == second_bytes
    result_sha256 = hashlib.sha256(first_bytes).hexdigest()
    assert resolution.render_markdown(first, result_sha256) == resolution.render_markdown(
        second,
        result_sha256,
    )


def test_original_result_is_referenced_and_not_reclassified_in_place() -> None:
    result = resolution.analyze_source_tree(REPO_ROOT)
    original = result["original_lineage_result"]
    records = result["records"]

    assert isinstance(original, dict)
    assert original["sha256"] == (
        "f2f7d1fd5e08083124aaeb43dfe889f96012f6020b9daafae49f6368f832bfad"
    )
    assert isinstance(records, list)
    assert all(
        isinstance(record, dict)
        and isinstance(record["original_resolution"], dict)
        and record["original_resolution"]["classification"] == "DYNAMIC_OR_UNRESOLVED"
        for record in records
    )


def test_checked_in_supplemental_artifacts_match_fresh_generation() -> None:
    result = resolution.analyze_source_tree(REPO_ROOT)
    result_bytes = resolution.canonical_json_bytes(result)
    result_sha256 = hashlib.sha256(result_bytes).hexdigest()
    report = resolution.render_markdown(result, result_sha256)

    assert (REPO_ROOT / resolution.OUTPUT_PATH).read_bytes() == result_bytes
    assert (REPO_ROOT / resolution.REPORT_PATH).read_text(encoding="utf-8") == report
