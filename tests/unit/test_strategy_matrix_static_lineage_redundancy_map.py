"""Focused tests for the DB-free static strategy-lineage analyzer."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest
from tools import run_strategy_matrix_static_lineage_redundancy_map as lineage


def _descriptor(
    strategy_id: str,
    adapter_path_expression: str,
    *,
    native_ticket_count: int = 1,
) -> str:
    response_shape = (
        "ResponseShape.SINGLE_TICKET"
        if native_ticket_count == 1
        else "ResponseShape.PORTFOLIO"
    )
    return f'''StrategyDescriptor(
        strategy_id={strategy_id!r},
        strategy_name={strategy_id!r},
        version="v1",
        lottery_types=(LotteryType.BIG_LOTTO,),
        lifecycle_status=LifecycleStatus.ONLINE,
        executable=True,
        adapter_path={adapter_path_expression},
        min_history=3,
        response_shape={response_shape},
        native_ticket_count={native_ticket_count},
    )'''


def _catalog(*descriptors: str) -> str:
    return "_PRODUCTION_DESCRIPTORS = (\n" + ",\n".join(descriptors) + ",\n)\n"


def _analyze(catalog: str, module_source: str) -> dict[str, lineage.JSONValue]:
    return lineage.analyze_static_sources(
        catalog,
        {"lottolab.strategies.adapters.fixture": module_source},
    )


def _records(result: dict[str, lineage.JSONValue]) -> list[dict[str, lineage.JSONValue]]:
    value = result["records"]
    assert isinstance(value, list)
    assert all(isinstance(item, dict) for item in value)
    return cast(list[dict[str, lineage.JSONValue]], value)


def _by_id(result: dict[str, lineage.JSONValue]) -> dict[str, dict[str, lineage.JSONValue]]:
    return {cast(str, item["strategy_id"]): item for item in _records(result)}


def test_identical_strategy_bindings_collapse_into_one_exact_group() -> None:
    catalog = _catalog(
        _descriptor("alias_a", '"lottolab.strategies.adapters.fixture:AliasA"'),
        _descriptor("alias_b", '"lottolab.strategies.adapters.fixture:AliasB"'),
    )
    module = '''
class AliasA:
    threshold = 4
    def _predict(self, history, lottery_type):
        return self.threshold

class AliasB:
    threshold = 4
    def _predict(self, history, lottery_type):
        return self.threshold
'''

    result = _analyze(catalog, module)
    records = _by_id(result)

    assert {cast(str, item["classification"]) for item in records.values()} == {
        "IDENTICAL_BINDING"
    }
    assert records["alias_a"]["binding_group_id"] == records["alias_b"][
        "binding_group_id"
    ]
    exact_groups = result["identical_binding_groups"]
    assert isinstance(exact_groups, list)
    assert len(exact_groups) == 1


def test_same_callable_with_changed_static_parameter_is_not_a_duplicate() -> None:
    catalog = _catalog(
        _descriptor("parameter_one", '"lottolab.strategies.adapters.fixture:One"'),
        _descriptor("parameter_two", '"lottolab.strategies.adapters.fixture:Two"'),
    )
    module = '''
class One:
    threshold = 1
    def _predict(self, history, lottery_type):
        return self.threshold

class Two:
    threshold = 2
    def _predict(self, history, lottery_type):
        return self.threshold
'''

    records = _by_id(_analyze(catalog, module))

    assert {cast(str, item["classification"]) for item in records.values()} == {
        "SAME_CALLABLE_DIFFERENT_BINDING"
    }
    assert records["parameter_one"]["callable_family_id"] == records["parameter_two"][
        "callable_family_id"
    ]
    assert records["parameter_one"]["binding_group_id"] != records["parameter_two"][
        "binding_group_id"
    ]


def test_distinct_callable_binding_remains_structurally_distinct() -> None:
    catalog = _catalog(
        _descriptor("first", '"lottolab.strategies.adapters.fixture:First"'),
        _descriptor("second", '"lottolab.strategies.adapters.fixture:Second"'),
    )
    module = '''
class First:
    def _predict(self, history, lottery_type):
        return 1

class Second:
    def _predict(self, history, lottery_type):
        return 2
'''

    records = _by_id(_analyze(catalog, module))

    assert {cast(str, item["classification"]) for item in records.values()} == {
        "DISTINCT_BINDING"
    }
    assert records["first"]["callable_family_id"] != records["second"][
        "callable_family_id"
    ]


def test_ast_digest_ignores_source_formatting_and_comments() -> None:
    compact = "def choose(value):\n    return value + 1\n"
    reformatted = '''
def choose( value ):
    # A comment cannot define implementation identity.
    return value + 1  # neither can a trailing comment
'''

    assert lineage.normalized_ast_digest(compact) == lineage.normalized_ast_digest(
        reformatted
    )


def test_dynamic_binding_fails_open_instead_of_guessing() -> None:
    catalog = _catalog(_descriptor("dynamic", "select_adapter_path()"))

    record = _records(_analyze(catalog, ""))[0]

    assert record["classification"] == "DYNAMIC_OR_UNRESOLVED"
    assert record["resolution_status"] == "DYNAMIC_OR_UNRESOLVED"
    assert record["binding_fingerprint_sha256"] is None
    assert record["unresolved_reason"] == "NON_LITERAL_ADAPTER_PATH"


def test_absolute_worktree_paths_do_not_enter_fingerprints() -> None:
    first_root = Path("/private/tmp/worktree-one")
    second_root = Path("/opt/another/worktree-two")
    first_relative = lineage.relative_source_path(
        first_root,
        first_root / "src/lottolab/strategies/adapters/fixture.py",
    )
    second_relative = lineage.relative_source_path(
        second_root,
        second_root / "src/lottolab/strategies/adapters/fixture.py",
    )
    assert first_relative == second_relative

    catalog = _catalog(
        _descriptor("portable", '"lottolab.strategies.adapters.fixture:Portable"')
    )
    result = lineage.analyze_static_sources(
        catalog,
        {
            "lottolab.strategies.adapters.fixture": (
                "class Portable:\n"
                "    def _predict(self, history, lottery_type):\n"
                "        return 1\n"
            )
        },
        module_paths={"lottolab.strategies.adapters.fixture": first_relative},
    )
    fingerprint = cast(str, _records(result)[0]["binding_fingerprint_sha256"])

    assert str(first_root) not in fingerprint
    assert str(second_root) not in fingerprint


def test_output_ordering_and_bytes_are_deterministic() -> None:
    catalog = _catalog(
        _descriptor("zeta", '"lottolab.strategies.adapters.fixture:Zeta"'),
        _descriptor("alpha", '"lottolab.strategies.adapters.fixture:Alpha"'),
    )
    module = '''
class Zeta:
    def _predict(self, history, lottery_type):
        return 2

class Alpha:
    def _predict(self, history, lottery_type):
        return 1
'''

    first = _analyze(catalog, module)
    second = _analyze(catalog, module)

    assert [item["strategy_id"] for item in _records(first)] == ["alpha", "zeta"]
    assert lineage.canonical_json_bytes(first) == lineage.canonical_json_bytes(second)


def test_duplicate_strategy_ids_fail_closed() -> None:
    catalog = _catalog(
        _descriptor("duplicate", '"lottolab.strategies.adapters.fixture:First"'),
        _descriptor("duplicate", '"lottolab.strategies.adapters.fixture:Second"'),
    )

    with pytest.raises(
        lineage.DuplicateStrategyIdError,
        match="DUPLICATE_STRATEGY_ID_AUTHORITY",
    ):
        _analyze(catalog, "")


def test_same_source_bundle_produces_identical_machine_readable_bytes_twice() -> None:
    catalog = _catalog(
        _descriptor("stable", '"lottolab.strategies.adapters.fixture:Stable"')
    )
    module = '''
class Stable:
    window = 20
    def _predict(self, history, lottery_type):
        return self.window
'''

    first_bytes = lineage.canonical_json_bytes(_analyze(catalog, module))
    second_bytes = lineage.canonical_json_bytes(_analyze(catalog, module))

    assert first_bytes == second_bytes
