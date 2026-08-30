"""Build the frozen selector-universe lineage supplement without execution.

This builder is intentionally source-only.  It reads the frozen selector
result from the pinned Git object (or an explicitly supplied file), parses the
P638/T539 strategy specifications with :mod:`ast`, and joins only exact
authority-qualified production catalog identities.  It never imports an
adapter, opens a database, reruns a selector, or performs historical replay.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import subprocess
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Literal, cast

type JSONValue = (
    None | bool | int | float | str | list[JSONValue] | dict[str, JSONValue]
)
type ResolutionStatus = Literal[
    "RESOLVED_REPLAY_BINDING",
    "UNRESOLVED_SOURCE_PIN",
    "DYNAMIC_BINDING_UNRESOLVED",
    "SOURCE_CONFLICT",
]

STUDY_ID = "SELECTOR_UNIVERSE_LINEAGE_SUPPLEMENT_R1"
SCHEMA_VERSION = "selector-universe-lineage-supplement/v1"

CURRENT_BASE_HEAD = "0645f31a2bcaf494760d4bc1675bc1c3ed9a076d"
CURRENT_BASE_TREE = "8b9fa40728f1bea3fb585d86f426a36489e0debf"
SELECTOR_COMMIT = "abc367bd6d8b59d01ecc4d79e56c787bbc03cd20"
SELECTOR_TREE = "bf430efd66b7ce1ac38ee04fb0052e8c55cc972c"
SELECTOR_RESULT_RELATIVE_PATH = Path(
    "docs/research/matrix-native-results/"
    "strategy-matrix-causal-rolling-selector-pilot-r1-result.json"
)
SELECTOR_RESULT_SHA256 = "04df0bfdffcf4ecc05d4f2ac3f58cfa1fa301061c5f1c30e549ddc3b5b174157"

T539_R2_FIRST_SOURCE_COMMIT = "c159da43ba79694d91c983f623d567560fe617a6"
T539_R2_REJECTED_SOURCE_COMMIT = "b2ce6a3daaef4925a8e3f15d93a883d173882714"

CATALOG_PATH = Path("src/lottolab/strategies/catalog.py")
T539_RUNNER_PATH = Path("tools/run_daily539_t539_wave1.py")
T539_PORTABLE_PATH = Path("src/lottolab/strategies/adapters/daily539_biglotto_portable.py")
P638_SPEC_PATHS: tuple[Path, ...] = tuple(
    Path(f"src/lottolab/strategies/adapters/powerlotto_wave{i}.py")
    for i in range(1, 7)
)
OUTPUT_PATH = Path(
    "docs/research/matrix-native-results/"
    "selector-universe-lineage-supplement-r1-result.json"
)
REPORT_PATH = Path("docs/research/selector-universe-lineage-supplement-r1.md")

LOTTERY_ORDER: tuple[str, ...] = ("B649", "P638", "T539")
LOTTERY_TO_ENUM: Final = {
    "B649": "BIG_LOTTO",
    "P638": "POWER_LOTTO",
    "T539": "DAILY_539",
}
AUTHORITY_BY_LOTTERY: Final = {
    "B649": "B649_EXACT_NATIVE_K2_K3",
    "P638": "P638_CURRENT_REPLAY_AND_RANKING",
    "T539": "T539_HISTORICAL_SQLITE",
}
EXPECTED_SELECTED_COUNTS: Final = {"B649": 15, "P638": 65, "T539": 55}
EXPECTED_PRODUCTION_COUNTS: Final = {"B649": 15, "P638": 9, "T539": 1}
EXPECTED_SUPPLEMENT_COUNTS: Final = {"B649": 0, "P638": 56, "T539": 54}
ALLOWED_RESOLUTION_STATUSES: tuple[ResolutionStatus, ...] = (
    "RESOLVED_REPLAY_BINDING",
    "UNRESOLVED_SOURCE_PIN",
    "DYNAMIC_BINDING_UNRESOLVED",
    "SOURCE_CONFLICT",
)

_UNRESOLVED = object()


class LineageSupplementError(ValueError):
    """The frozen selector universe cannot be resolved fail-closed."""


class SelectorUniverseCensusDrift(LineageSupplementError):
    """The exact-source selector census differs from the frozen census."""


class SourceAuthorityConflict(LineageSupplementError):
    """A source commit/ref conflicts with the packet's authority pin."""


class UnresolvedSource(LineageSupplementError):
    """A required source or static binding could not be resolved."""


@dataclass(frozen=True, slots=True)
class SymbolReference:
    module_name: str
    symbol: str

    def as_text(self) -> str:
        return f"{self.module_name}:{self.symbol}"


@dataclass(frozen=True, slots=True)
class StaticModule:
    module_name: str
    relative_path: str
    source: str
    tree: ast.Module
    assignments: dict[str, ast.expr]
    functions: dict[str, ast.FunctionDef | ast.AsyncFunctionDef]
    classes: dict[str, ast.ClassDef]
    imported_symbols: dict[str, SymbolReference]
    imported_modules: dict[str, str]


@dataclass(frozen=True, slots=True)
class StaticSpec:
    strategy_id: str
    strategy_version: str
    static_parameters: dict[str, JSONValue]
    callable_expression: str
    callable_expression_node: ast.expr
    source_paths: tuple[str, ...]
    provenance: dict[str, JSONValue]
    spec_locator: str
    helper_locator: str | None
    spec_node: ast.Call
    helper_node: ast.FunctionDef | ast.AsyncFunctionDef | None


@dataclass(frozen=True, slots=True)
class SourceSymbol:
    reference: SymbolReference
    node: ast.AST
    module: StaticModule

    @property
    def locator(self) -> str:
        return _locator(self.module, self.node, self.reference.symbol)


class StaticSourceStore:
    """Lazy AST index for repository Python modules."""

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root.resolve()
        self._modules: dict[str, StaticModule] = {}

    def load_path(self, relative_path: Path) -> StaticModule:
        path = self.repo_root / relative_path
        if not path.is_file():
            raise UnresolvedSource(f"required source path is missing: {relative_path}")
        module_name = _module_name_for_path(relative_path)
        if module_name in self._modules:
            return self._modules[module_name]
        source = path.read_text(encoding="utf-8")
        module = _parse_module(module_name, relative_path.as_posix(), source)
        self._modules[module_name] = module
        return module

    def load_module(self, module_name: str) -> StaticModule:
        module_path = Path("src") / Path(*module_name.split(".")).with_suffix(".py")
        return self.load_path(module_path)

    def symbol(self, reference: SymbolReference) -> SourceSymbol | None:
        try:
            module = self.load_module(reference.module_name)
        except UnresolvedSource:
            return None
        node: ast.AST | None = module.functions.get(reference.symbol)
        if node is None:
            node = module.classes.get(reference.symbol)
        if node is None:
            assignment = module.assignments.get(reference.symbol)
            node = assignment
        return None if node is None else SourceSymbol(reference, node, module)


def canonical_json_bytes(payload: JSONValue) -> bytes:
    """Return stable, UTF-8, sorted-key JSON with one terminal newline."""

    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    ).rstrip("\n")
    return f"{serialized}\n".encode()


def _compact_json_bytes(payload: JSONValue) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        allow_nan=False,
    ).encode("utf-8")


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _stable_digest(payload: JSONValue) -> str:
    return _sha256(_compact_json_bytes(payload))


def _node_digest(node: ast.AST) -> str:
    normalized = ast.dump(node, annotate_fields=True, include_attributes=False)
    return _sha256(normalized.encode("utf-8"))


def _module_name_for_path(relative_path: Path) -> str:
    path = relative_path.with_suffix("")
    parts = path.parts
    if parts and parts[0] == "src":
        parts = parts[1:]
    return ".".join(parts)


def _resolve_import_module(current_module: str, imported: str | None, level: int) -> str:
    if level == 0:
        if imported is None:
            raise LineageSupplementError("absolute import without module")
        return imported
    package = current_module.split(".")[:-1]
    keep = len(package) - level + 1
    if keep < 0:
        raise LineageSupplementError(f"invalid relative import in {current_module}")
    suffix = [] if imported is None else imported.split(".")
    return ".".join(package[:keep] + suffix)


def _assigned_names(node: ast.Assign | ast.AnnAssign) -> tuple[str, ...]:
    targets = node.targets if isinstance(node, ast.Assign) else (node.target,)
    return tuple(target.id for target in targets if isinstance(target, ast.Name))


def _parse_module(module_name: str, relative_path: str, source: str) -> StaticModule:
    tree = ast.parse(source, filename=relative_path)
    assignments: dict[str, ast.expr] = {}
    functions: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = {}
    classes: dict[str, ast.ClassDef] = {}
    imported_symbols: dict[str, SymbolReference] = {}
    imported_modules: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions[node.name] = node
        elif isinstance(node, ast.ClassDef):
            classes[node.name] = node
        elif isinstance(node, (ast.Assign, ast.AnnAssign)) and node.value is not None:
            for name in _assigned_names(node):
                assignments[name] = node.value
        elif isinstance(node, ast.ImportFrom):
            imported_module = _resolve_import_module(module_name, node.module, node.level)
            for alias in node.names:
                if alias.name == "*":
                    continue
                imported_symbols[alias.asname or alias.name] = SymbolReference(
                    imported_module,
                    alias.name,
                )
        elif isinstance(node, ast.Import):
            for alias in node.names:
                local_name = alias.asname or alias.name.split(".", 1)[0]
                imported_modules[local_name] = alias.name
    return StaticModule(
        module_name=module_name,
        relative_path=relative_path,
        source=source,
        tree=tree,
        assignments=assignments,
        functions=functions,
        classes=classes,
        imported_symbols=imported_symbols,
        imported_modules=imported_modules,
    )


def _locator(module: StaticModule, node: ast.AST, symbol: str) -> str:
    line = getattr(node, "lineno", None)
    if not isinstance(line, int):
        raise LineageSupplementError(f"{symbol} has no source line")
    return f"{module.relative_path}:{line}:{symbol}"


def _keyword_map(call: ast.Call) -> dict[str, ast.expr]:
    result: dict[str, ast.expr] = {}
    for keyword in call.keywords:
        if keyword.arg is None:
            raise LineageSupplementError("**kwargs cannot be resolved statically")
        if keyword.arg in result:
            raise LineageSupplementError(f"duplicate keyword: {keyword.arg}")
        result[keyword.arg] = keyword.value
    return result


def _static_value(
    expression: ast.expr,
    module: StaticModule,
    bindings: dict[str, ast.expr] | None = None,
    seen: frozenset[str] = frozenset(),
) -> Any:
    local_bindings = {} if bindings is None else bindings
    if isinstance(expression, ast.Constant):
        return expression.value
    if isinstance(expression, ast.Name):
        if expression.id in local_bindings and expression.id not in seen:
            return _static_value(
                local_bindings[expression.id],
                module,
                local_bindings,
                seen | {expression.id},
            )
        assignment = module.assignments.get(expression.id)
        if assignment is not None and expression.id not in seen:
            return _static_value(assignment, module, local_bindings, seen | {expression.id})
        return _UNRESOLVED
    if isinstance(expression, ast.JoinedStr):
        pieces: list[str] = []
        for value in expression.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                pieces.append(value.value)
            elif isinstance(value, ast.FormattedValue):
                formatted = _static_value(value.value, module, local_bindings, seen)
                if formatted is _UNRESOLVED:
                    return _UNRESOLVED
                pieces.append(str(formatted))
            else:
                return _UNRESOLVED
        return "".join(pieces)
    if isinstance(expression, ast.BinOp) and isinstance(expression.op, (ast.Add, ast.Sub)):
        left = _static_value(expression.left, module, local_bindings, seen)
        right = _static_value(expression.right, module, local_bindings, seen)
        if left is _UNRESOLVED or right is _UNRESOLVED:
            return _UNRESOLVED
        try:
            return left + right if isinstance(expression.op, ast.Add) else left - right
        except TypeError:
            return _UNRESOLVED
    if isinstance(expression, ast.UnaryOp) and isinstance(expression.op, (ast.UAdd, ast.USub)):
        value = _static_value(expression.operand, module, local_bindings, seen)
        if type(value) is not int:
            return _UNRESOLVED
        return value if isinstance(expression.op, ast.UAdd) else -value
    if isinstance(expression, (ast.Tuple, ast.List)):
        values = [
            _static_value(item, module, local_bindings, seen) for item in expression.elts
        ]
        return _UNRESOLVED if any(value is _UNRESOLVED for value in values) else tuple(values)
    if isinstance(expression, ast.Dict):
        result: dict[str, Any] = {}
        for key, value_node in zip(expression.keys, expression.values, strict=True):
            if key is None:
                return _UNRESOLVED
            key_value = _static_value(key, module, local_bindings, seen)
            value = _static_value(value_node, module, local_bindings, seen)
            if not isinstance(key_value, str) or value is _UNRESOLVED:
                return _UNRESOLVED
            result[key_value] = value
        return result
    if isinstance(expression, ast.Attribute):
        if expression.attr == "value" and isinstance(expression.value, ast.Attribute):
            return expression.value.attr
        if isinstance(expression.value, ast.Name) and expression.value.id in {
            "LotteryType",
            "ResponseShape",
            "LifecycleStatus",
        }:
            return expression.attr
    return _UNRESOLVED


def _static_string(
    expression: ast.expr,
    module: StaticModule,
    bindings: dict[str, ast.expr] | None = None,
) -> str | None:
    value = _static_value(expression, module, bindings)
    return value if isinstance(value, str) else None


def _static_int(
    expression: ast.expr,
    module: StaticModule,
    bindings: dict[str, ast.expr] | None = None,
) -> int | None:
    value = _static_value(expression, module, bindings)
    return value if type(value) is int else None


def _string_tuple(value: object) -> tuple[str, ...] | None:
    if not isinstance(value, tuple):
        return None
    items = cast(tuple[object, ...], value)
    if not all(isinstance(item, str) for item in items):
        return None
    return cast(tuple[str, ...], items)


def _int_tuple(value: object) -> tuple[int, ...] | None:
    if not isinstance(value, tuple):
        return None
    items = cast(tuple[object, ...], value)
    if not all(type(item) is int for item in items):
        return None
    return cast(tuple[int, ...], items)


def _expression_text(expression: ast.expr) -> str:
    return ast.unparse(expression)


def _call_function_name(expression: ast.expr) -> str | None:
    return expression.id if isinstance(expression, ast.Name) else None


def _bind_call_arguments(
    function: ast.FunctionDef | ast.AsyncFunctionDef,
    call: ast.Call,
) -> dict[str, ast.expr]:
    positional = [*function.args.posonlyargs, *function.args.args]
    bindings: dict[str, ast.expr] = {}
    if len(call.args) > len(positional):
        raise LineageSupplementError(f"too many arguments for {function.name}")
    for parameter, argument in zip(positional, call.args, strict=False):
        bindings[parameter.arg] = argument
    keywords = _keyword_map(call)
    positional_names = {parameter.arg for parameter in positional}
    for parameter in positional:
        if parameter.arg in keywords:
            if parameter.arg in bindings:
                raise LineageSupplementError(f"duplicate argument: {parameter.arg}")
            bindings[parameter.arg] = keywords.pop(parameter.arg)
    for parameter, default in zip(
        function.args.kwonlyargs,
        function.args.kw_defaults,
        strict=True,
    ):
        if parameter.arg in keywords:
            bindings[parameter.arg] = keywords.pop(parameter.arg)
        elif default is not None:
            bindings[parameter.arg] = default
        else:
            raise LineageSupplementError(f"missing keyword-only argument: {parameter.arg}")
    defaults_start = len(positional) - len(function.args.defaults)
    for index, parameter in enumerate(positional):
        if parameter.arg not in bindings and index >= defaults_start:
            bindings[parameter.arg] = function.args.defaults[index - defaults_start]
    if keywords:
        raise LineageSupplementError(
            f"unexpected keyword(s) for {function.name}: {', '.join(sorted(keywords))}"
        )
    del positional_names
    return bindings


def _return_call(
    function: ast.FunctionDef | ast.AsyncFunctionDef,
    expected_name: str,
) -> ast.Call:
    returns = [node for node in ast.walk(function) if isinstance(node, ast.Return)]
    calls = [
        node.value
        for node in returns
        if isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
        and node.value.func.id == expected_name
    ]
    if len(calls) != 1:
        raise LineageSupplementError(
            f"{function.name} must have exactly one static {expected_name} return"
        )
    return calls[0]


def _resolve_spec_call(
    outer_call: ast.Call,
    module: StaticModule,
    expected_name: str,
) -> tuple[ast.Call, dict[str, ast.expr], ast.FunctionDef | ast.AsyncFunctionDef | None]:
    function_name = _call_function_name(outer_call.func)
    if function_name == expected_name:
        return outer_call, {}, None
    if function_name is None or function_name not in module.functions:
        raise LineageSupplementError(
            f"{module.relative_path}:{getattr(outer_call, 'lineno', '?')}: "
            f"cannot resolve {expected_name} factory"
        )
    helper = module.functions[function_name]
    bindings = _bind_call_arguments(helper, outer_call)
    return _return_call(helper, expected_name), bindings, helper


def _dereference_expression(
    expression: ast.expr,
    module: StaticModule,
    bindings: dict[str, ast.expr],
    seen: frozenset[str] = frozenset(),
) -> ast.expr:
    if isinstance(expression, ast.Name) and expression.id in bindings:
        if expression.id in seen:
            return expression
        return _dereference_expression(
            bindings[expression.id], module, bindings, seen | {expression.id}
        )
    return expression


def _reference_from_expression(
    expression: ast.expr,
    module: StaticModule,
    bindings: dict[str, ast.expr],
    seen: frozenset[str] = frozenset(),
) -> SymbolReference | None:
    expression = _dereference_expression(expression, module, bindings, seen)
    if isinstance(expression, ast.Name):
        if expression.id in module.functions or expression.id in module.classes:
            return SymbolReference(module.module_name, expression.id)
        imported = module.imported_symbols.get(expression.id)
        if imported is not None:
            return imported
        assignment = module.assignments.get(expression.id)
        if assignment is not None and expression.id not in seen:
            return _reference_from_expression(
                assignment,
                module,
                bindings,
                seen | {expression.id},
            )
        return None
    if isinstance(expression, ast.Attribute) and isinstance(expression.value, ast.Name):
        imported_module = module.imported_modules.get(expression.value.id)
        if imported_module is not None:
            return SymbolReference(imported_module, expression.attr)
        imported_symbol = module.imported_symbols.get(expression.value.id)
        if imported_symbol is not None:
            # ``from package import module as alias`` is represented in the
            # AST import table as a symbol import, but the alias is used as a
            # module namespace by the source specs.
            return SymbolReference(
                f"{imported_symbol.module_name}.{imported_symbol.symbol}",
                expression.attr,
            )
    return None


def _resolve_callable(
    expression: ast.expr,
    module: StaticModule,
    bindings: dict[str, ast.expr],
) -> dict[str, Any]:
    expression = _dereference_expression(expression, module, bindings)
    if isinstance(expression, ast.Call):
        factory = _reference_from_expression(expression.func, module, bindings)
        wrapped = None
        for argument in expression.args:
            wrapped = _reference_from_expression(argument, module, bindings)
            if wrapped is not None:
                break
        if factory is None or wrapped is None:
            raise UnresolvedSource(
                f"dynamic callable expression is unresolved: {_expression_text(expression)}"
            )
        return {
            "kind": "STATIC_WRAPPER",
            "expression": _expression_text(expression),
            "factory_reference": factory,
            "wrapped_reference": wrapped,
        }
    reference = _reference_from_expression(expression, module, bindings)
    if reference is None:
        raise UnresolvedSource(
            f"dynamic callable expression is unresolved: {_expression_text(expression)}"
        )
    return {
        "kind": "STATIC_SYMBOL",
        "expression": _expression_text(expression),
        "reference": reference,
    }


def _required_field(
    keywords: dict[str, ast.expr],
    name: str,
    module: StaticModule,
    bindings: dict[str, ast.expr],
) -> Any:
    expression = keywords.get(name)
    if expression is None:
        raise LineageSupplementError(f"missing {name} in static strategy spec")
    value = _static_value(expression, module, bindings)
    if value is _UNRESOLVED:
        raise LineageSupplementError(f"{name} is not statically resolvable")
    return value


def _parse_p638_spec(outer_call: ast.Call, module: StaticModule) -> StaticSpec:
    spec_call, bindings, helper = _resolve_spec_call(outer_call, module, "P638StrategySpec")
    keywords = _keyword_map(spec_call)
    strategy_id = _required_field(keywords, "strategy_id", module, bindings)
    strategy_version = _required_field(keywords, "strategy_version", module, bindings)
    native_ticket_count = _required_field(
        keywords, "native_ticket_count", module, bindings
    )
    min_history = _required_field(keywords, "min_history", module, bindings)
    source_paths_value = _required_field(keywords, "source_paths", module, bindings)
    source_paths = _string_tuple(source_paths_value)
    provenance = _required_field(keywords, "provenance", module, bindings)
    predictor = keywords.get("_predictor")
    if predictor is None:
        raise LineageSupplementError(f"{strategy_id}: missing _predictor")
    if (
        not isinstance(strategy_id, str)
        or not isinstance(strategy_version, str)
        or type(native_ticket_count) is not int
        or type(min_history) is not int
        or source_paths is None
        or not isinstance(provenance, str)
    ):
        raise LineageSupplementError(f"{strategy_id}: malformed static P638 spec")
    closure_expression = keywords.get("source_native_closure_ticket_counts")
    if closure_expression is None:
        closure_counts: tuple[int, ...] = ()
    else:
        closure_counts_value = _required_field(
            keywords,
            "source_native_closure_ticket_counts",
            module,
            bindings,
        )
        resolved_closure_counts = _int_tuple(closure_counts_value)
        if resolved_closure_counts is None:
            raise LineageSupplementError(f"{strategy_id}: malformed closure ticket counts")
        closure_counts = resolved_closure_counts
    resolved_predictor = _dereference_expression(predictor, module, bindings)
    provenance_payload: dict[str, JSONValue] = {
        "provenance_text": provenance,
        "declared_source_paths": list(source_paths),
        "donor_archive_sha256": _extract_donor_archive_sha(provenance),
        "donor_identity_alias": False,
    }
    return StaticSpec(
        strategy_id=strategy_id,
        strategy_version=strategy_version,
        static_parameters={
            "native_ticket_count": native_ticket_count,
            "min_history": min_history,
            "source_native_closure_ticket_counts": list(closure_counts),
            "predictor_expression": _expression_text(resolved_predictor),
            "declared_source_paths": list(source_paths),
        },
        callable_expression=_expression_text(resolved_predictor),
        callable_expression_node=resolved_predictor,
        source_paths=source_paths,
        provenance=provenance_payload,
        spec_locator=_locator(
            module,
            outer_call,
            f"{_expression_text(outer_call.func)}[{strategy_id}]",
        ),
        helper_locator=None if helper is None else _locator(module, helper, helper.name),
        spec_node=spec_call,
        helper_node=helper,
    )


def _find_strategy_tuple(module: StaticModule, assignment_name: str) -> ast.Tuple:
    expression = module.assignments.get(assignment_name)
    if not isinstance(expression, ast.Tuple):
        raise LineageSupplementError(
            f"{module.relative_path}: {assignment_name} is not a static tuple"
        )
    return expression


def _p638_specs(store: StaticSourceStore) -> dict[tuple[str, str], tuple[StaticSpec, StaticModule]]:
    result: dict[tuple[str, str], tuple[StaticSpec, StaticModule]] = {}
    for index, path in enumerate(P638_SPEC_PATHS, start=1):
        module = store.load_path(path)
        tuple_node = _find_strategy_tuple(module, f"WAVE{index}_STRATEGIES")
        for element in tuple_node.elts:
            if not isinstance(element, ast.Call):
                raise LineageSupplementError(
                    f"{path}:{getattr(element, 'lineno', '?')}: non-call P638 spec"
                )
            spec = _parse_p638_spec(element, module)
            key = (spec.strategy_id, spec.strategy_version)
            if key in result:
                raise LineageSupplementError(f"duplicate P638 spec: {key}")
            result[key] = (spec, module)
    return result


def _parse_t539_direct_spec(call: ast.Call, module: StaticModule) -> StaticSpec:
    keywords = _keyword_map(call)
    strategy_id = _required_field(keywords, "strategy_id", module, {})
    strategy_version = _required_field(keywords, "strategy_version", module, {})
    strategy_name = _required_field(keywords, "strategy_name", module, {})
    lottery_type = _required_field(keywords, "lottery_type", module, {})
    min_history = _required_field(keywords, "min_history", module, {})
    native_ticket_count = _required_field(keywords, "native_ticket_count", module, {})
    adapter_factory = keywords.get("adapter_factory")
    source_paths_value = _required_field(keywords, "adapter_source_paths", module, {})
    source_paths = _string_tuple(source_paths_value)
    selection_reason = _required_field(keywords, "selection_reason", module, {})
    if (
        not isinstance(strategy_id, str)
        or not isinstance(strategy_version, str)
        or not isinstance(strategy_name, str)
        or not isinstance(lottery_type, str)
        or type(min_history) is not int
        or type(native_ticket_count) is not int
        or adapter_factory is None
        or source_paths is None
        or not isinstance(selection_reason, str)
    ):
        raise LineageSupplementError(f"{strategy_id}: malformed static T539 spec")
    provenance: dict[str, JSONValue] = {
        "selection_reason": selection_reason,
        "declared_adapter_source_paths": list(source_paths),
        "donor_identity_alias": False,
    }
    return StaticSpec(
        strategy_id=strategy_id,
        strategy_version=strategy_version,
        static_parameters={
            "strategy_name": strategy_name,
            "lottery_type": lottery_type,
            "min_history": min_history,
            "native_ticket_count": native_ticket_count,
            "adapter_factory_expression": _expression_text(adapter_factory),
            "declared_adapter_source_paths": list(source_paths),
        },
        callable_expression=_expression_text(adapter_factory),
        callable_expression_node=adapter_factory,
        source_paths=source_paths,
        provenance=provenance,
        spec_locator=_locator(
            module,
            call,
            f"StrategySpec[{strategy_id}]",
        ),
        helper_locator=None,
        spec_node=call,
        helper_node=None,
    )


def _t539_direct_specs(
    store: StaticSourceStore,
) -> dict[tuple[str, str], tuple[StaticSpec, StaticModule]]:
    module = store.load_path(T539_RUNNER_PATH)
    result: dict[tuple[str, str], tuple[StaticSpec, StaticModule]] = {}
    for node in ast.walk(module.tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "StrategySpec"
        ):
            continue
        try:
            spec = _parse_t539_direct_spec(node, module)
        except LineageSupplementError as exc:
            # The R2 comprehension intentionally carries dynamic
            # ``portable_spec`` attributes.  Its concrete rows are resolved
            # from the portable spec source below.
            if any(
                isinstance(keyword.value, ast.Attribute)
                and isinstance(keyword.value.value, ast.Name)
                and keyword.value.value.id == "portable_spec"
                for keyword in node.keywords
            ):
                continue
            raise exc
        key = (spec.strategy_id, spec.strategy_version)
        if key in result:
            raise LineageSupplementError(f"duplicate T539 direct spec: {key}")
        result[key] = (spec, module)
    return result


def _portable_specs(
    store: StaticSourceStore,
) -> dict[tuple[str, str], tuple[StaticSpec, StaticModule]]:
    module = store.load_path(T539_PORTABLE_PATH)
    tuple_node = _find_strategy_tuple(module, "DAILY539_BIGLOTTO_PORTABLE_SPECS")
    result: dict[tuple[str, str], tuple[StaticSpec, StaticModule]] = {}
    for element in tuple_node.elts:
        if not isinstance(element, ast.Call):
            raise LineageSupplementError("non-call portable T539 spec")
        spec_call, bindings, helper = _resolve_spec_call(
            element,
            module,
            "Daily539BigLottoPortableSpec",
        )
        keywords = _keyword_map(spec_call)
        source_strategy_id = _required_field(
            keywords, "source_strategy_id", module, bindings
        )
        strategy_id = _required_field(keywords, "strategy_id", module, bindings)
        strategy_name = _required_field(keywords, "strategy_name", module, bindings)
        strategy_version = _required_field(keywords, "strategy_version", module, bindings)
        native_ticket_count = _required_field(
            keywords, "native_ticket_count", module, bindings
        )
        min_history = _required_field(keywords, "min_history", module, bindings)
        source_paths_value = _required_field(keywords, "source_paths", module, bindings)
        source_paths = _string_tuple(source_paths_value)
        predictor = keywords.get("predictor")
        if predictor is None:
            raise LineageSupplementError(f"{strategy_id}: missing portable predictor")
        if (
            not isinstance(source_strategy_id, str)
            or not isinstance(strategy_id, str)
            or not isinstance(strategy_name, str)
            or not isinstance(strategy_version, str)
            or type(native_ticket_count) is not int
            or type(min_history) is not int
            or source_paths is None
        ):
            raise LineageSupplementError(f"{strategy_id}: malformed portable spec")
        resolved_predictor = _dereference_expression(predictor, module, bindings)
        spec = StaticSpec(
            strategy_id=strategy_id,
            strategy_version=strategy_version,
            static_parameters={
                "source_strategy_id": source_strategy_id,
                "strategy_name": strategy_name,
                "lottery_type": "DAILY_539",
                "min_history": min_history,
                "native_ticket_count": native_ticket_count,
                "predictor_expression": _expression_text(resolved_predictor),
                "declared_source_paths": list(source_paths),
            },
            callable_expression=_expression_text(resolved_predictor),
            callable_expression_node=resolved_predictor,
            source_paths=source_paths,
            provenance={
                "source_strategy_id": source_strategy_id,
                "declared_source_paths": list(source_paths),
                "donor_identity_alias": False,
                "portable_r2_definition": True,
            },
            spec_locator=_locator(
                module,
                element,
                f"{_expression_text(element.func)}[{strategy_id}]",
            ),
            helper_locator=None if helper is None else _locator(module, helper, helper.name),
            spec_node=spec_call,
            helper_node=helper,
        )
        key = (spec.strategy_id, spec.strategy_version)
        if key in result:
            raise LineageSupplementError(f"duplicate portable T539 spec: {key}")
        result[key] = (spec, module)
    return result


def _extract_donor_archive_sha(provenance: str) -> str | None:
    marker = "donor archive "
    if marker not in provenance:
        return None
    candidate = provenance.split(marker, 1)[1].split(";", 1)[0].strip()
    return (
        candidate
        if len(candidate) == 64
        and all(char in "0123456789abcdef" for char in candidate)
        else None
    )


def _source_symbol_for_callable(
    store: StaticSourceStore,
    module: StaticModule,
    expression: ast.expr,
    bindings: dict[str, ast.expr] | None = None,
) -> tuple[dict[str, Any], tuple[SourceSymbol, ...]]:
    resolution = _resolve_callable(expression, module, {} if bindings is None else bindings)
    symbols: list[SourceSymbol] = []
    if resolution["kind"] == "STATIC_SYMBOL":
        reference = cast(SymbolReference, resolution["reference"])
        symbol = store.symbol(reference)
        if symbol is None:
            raise UnresolvedSource(f"callable symbol is missing: {reference.as_text()}")
        symbols.append(symbol)
        return resolution, tuple(symbols)
    factory = cast(SymbolReference, resolution["factory_reference"])
    wrapped = cast(SymbolReference, resolution["wrapped_reference"])
    factory_symbol = store.symbol(factory)
    wrapped_symbol = store.symbol(wrapped)
    if factory_symbol is None or wrapped_symbol is None:
        missing = factory.as_text() if factory_symbol is None else wrapped.as_text()
        raise UnresolvedSource(f"wrapped callable symbol is missing: {missing}")
    symbols.extend((factory_symbol, wrapped_symbol))
    return resolution, tuple(symbols)


def _class_execution_symbol(
    store: StaticSourceStore,
    reference: SymbolReference,
) -> tuple[SourceSymbol, SourceSymbol | None]:
    class_symbol = store.symbol(reference)
    if class_symbol is None or not isinstance(class_symbol.node, ast.ClassDef):
        raise UnresolvedSource(f"adapter class is missing: {reference.as_text()}")
    class_node = class_symbol.node
    methods: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = {
        node.name: node
        for node in class_node.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    for method_name in ("get_bets", "get_one_bet", "predict_tickets", "get_bet"):
        method = methods.get(method_name)
        if method is not None:
            return class_symbol, SourceSymbol(
                reference=SymbolReference(
                    reference.module_name,
                    f"{reference.symbol}.{method_name}",
                ),
                node=method,
                module=class_symbol.module,
            )
    for base in class_node.bases:
        base_reference: SymbolReference | None = None
        if isinstance(base, ast.Name):
            if base.id in class_symbol.module.classes:
                base_reference = SymbolReference(reference.module_name, base.id)
            else:
                base_reference = class_symbol.module.imported_symbols.get(base.id)
        if base_reference is not None:
            try:
                return class_symbol, _class_execution_symbol(store, base_reference)[1]
            except UnresolvedSource:
                continue
    return class_symbol, None


def _json_reference(reference: SymbolReference) -> str:
    return reference.as_text()


def _path_exists(repo_root: Path, relative_path: str) -> bool:
    return (repo_root / relative_path).is_file()


def _current_source_paths(
    repo_root: Path,
    paths: tuple[str, ...],
    extra_paths: tuple[str, ...] = (),
) -> tuple[str, ...]:
    candidates = set(extra_paths)
    for path in paths:
        if path.startswith("src/") or path.startswith("tools/"):
            candidates.add(path)
    current = tuple(sorted(path for path in candidates if _path_exists(repo_root, path)))
    if not current:
        raise UnresolvedSource("no current source file was resolvable")
    return current


def _source_blob_digests(repo_root: Path, paths: tuple[str, ...]) -> tuple[dict[str, str], ...]:
    records: list[dict[str, str]] = []
    for path in paths:
        file_path = repo_root / path
        if not file_path.is_file():
            raise UnresolvedSource(f"required implementation source is missing: {path}")
        records.append({"path": path, "sha256": _sha256(file_path.read_bytes())})
    return tuple(records)


def _source_components(
    spec: StaticSpec,
    callable_symbols: tuple[SourceSymbol, ...],
    extra_components: tuple[dict[str, str], ...] = (),
) -> tuple[dict[str, str], ...]:
    components: list[dict[str, str]] = [
        {
            "locator": spec.spec_locator,
            "normalized_ast_sha256": _node_digest(spec.spec_node),
        }
    ]
    if spec.helper_node is not None and spec.helper_locator is not None:
        components.append(
            {
                "locator": spec.helper_locator,
                "normalized_ast_sha256": _node_digest(spec.helper_node),
            }
        )
    for symbol in callable_symbols:
        components.append(
            {
                "locator": symbol.locator,
                "normalized_ast_sha256": _node_digest(symbol.node),
            }
        )
    components.extend(extra_components)
    return tuple(sorted(components, key=lambda item: item["locator"]))


def _source_authority(
    lottery_id: str,
    *,
    t539_r2: bool = False,
) -> dict[str, JSONValue]:
    if t539_r2:
        validate_t539_r2_source_pin(T539_R2_FIRST_SOURCE_COMMIT)
        return {
            "authority_kind": "T539_R2_FIRST_SOURCE_AND_CANONICAL_IMPLEMENTATION",
            "source_commit": T539_R2_FIRST_SOURCE_COMMIT,
            "source_ref": T539_R2_FIRST_SOURCE_COMMIT,
            "first_definition_commit": T539_R2_FIRST_SOURCE_COMMIT,
            "canonical_implementation_commit": CURRENT_BASE_HEAD,
            "rejected_source_commit": T539_R2_REJECTED_SOURCE_COMMIT,
            "rejection_reason": (
                "b2ce6a3 predates the portable R2 definitions and is not an "
                "implementation source for T539 R2."
            ),
        }
    return {
        "authority_kind": "PACKET_CURRENT_BASE_SOURCE_TREE",
        "source_commit": CURRENT_BASE_HEAD,
        "source_ref": "CURRENT_BASE_HEAD",
        "source_lottery_id": lottery_id,
    }


def validate_t539_r2_source_pin(source_commit: str) -> None:
    """Reject the superseded T539 R2 source and require the c159 pin."""

    if source_commit == T539_R2_REJECTED_SOURCE_COMMIT or source_commit.startswith("b2ce6a3"):
        raise SourceAuthorityConflict(
            "T539 R2 source conflict: b2ce6a3 is forbidden; use c159da43"
        )
    if source_commit != T539_R2_FIRST_SOURCE_COMMIT:
        raise SourceAuthorityConflict(
            f"T539 R2 requires {T539_R2_FIRST_SOURCE_COMMIT}, got {source_commit}"
        )


def authority_qualified_key(
    source_authority_id: str,
    lottery_id: str,
    strategy_id: str,
    strategy_version: str,
) -> tuple[str, str, str, str]:
    return source_authority_id, lottery_id, strategy_id, strategy_version


def _identity_sort_key(identity: dict[str, Any]) -> tuple[int, str, str, str]:
    return (
        LOTTERY_ORDER.index(cast(str, identity["lottery_id"])),
        cast(str, identity["strategy_id"]),
        cast(str, identity["strategy_version"]),
        cast(str, identity["source_authority_id"]),
    )


def extract_selected_identities(selector: dict[str, object]) -> tuple[dict[str, Any], ...]:
    """Extract the qualified selector identities from rolling frequencies."""

    by_key: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    cells_value = selector.get("cells", [])
    if not isinstance(cells_value, list):
        raise SelectorUniverseCensusDrift("selector cells are malformed")
    for cell_value in cast(list[object], cells_value):
        if not isinstance(cell_value, dict):
            raise SelectorUniverseCensusDrift("selector cell is not an object")
        cell = cast(dict[str, object], cell_value)
        authority = cell.get("source_authority_id")
        lottery = cell.get("lottery_id")
        candidates = cell.get("candidate_strategies")
        experiments = cell.get("experiments")
        if not isinstance(authority, str) or not isinstance(lottery, str):
            raise SelectorUniverseCensusDrift("selector cell authority/lottery is malformed")
        if (
            lottery not in LOTTERY_ORDER
            or not isinstance(candidates, list)
            or not isinstance(experiments, dict)
        ):
            raise SelectorUniverseCensusDrift(f"malformed selector cell: {authority}/{lottery}")
        candidate_versions: dict[str, str] = {}
        for candidate_value in cast(list[object], candidates):
            if not isinstance(candidate_value, dict):
                raise SelectorUniverseCensusDrift("selector candidate is not an object")
            candidate = cast(dict[str, object], candidate_value)
            strategy_id = candidate.get("strategy_id")
            strategy_version = candidate.get("strategy_version")
            if not isinstance(strategy_id, str) or not isinstance(strategy_version, str):
                raise SelectorUniverseCensusDrift("selector candidate identity is malformed")
            if (
                strategy_id in candidate_versions
                and candidate_versions[strategy_id] != strategy_version
            ):
                raise SelectorUniverseCensusDrift(f"candidate version conflict: {strategy_id}")
            candidate_versions[strategy_id] = strategy_version
        selected_ids: set[str] = set()
        for experiment_value in cast(dict[str, object], experiments).values():
            if not isinstance(experiment_value, dict):
                raise SelectorUniverseCensusDrift("selector experiment is not an object")
            experiment = cast(dict[str, object], experiment_value)
            frequency = experiment.get("rolling_selection_frequency")
            if frequency is None:
                continue
            if not isinstance(frequency, dict):
                raise SelectorUniverseCensusDrift("rolling selection frequency is malformed")
            for selected_id in cast(dict[object, object], frequency):
                if not isinstance(selected_id, str):
                    raise SelectorUniverseCensusDrift(
                        "rolling selection frequency is malformed"
                    )
                selected_ids.add(selected_id)
        for strategy_id in sorted(selected_ids):
            strategy_version = candidate_versions.get(strategy_id)
            if strategy_version is None:
                raise SelectorUniverseCensusDrift(
                    f"selected strategy is absent from candidate list: {strategy_id}"
                )
            key = authority_qualified_key(authority, lottery, strategy_id, strategy_version)
            record = by_key.setdefault(
                key,
                {
                    "source_authority_id": authority,
                    "lottery_id": lottery,
                    "strategy_id": strategy_id,
                    "strategy_version": strategy_version,
                    "selector_cells": [],
                },
            )
            cell_id = cell.get("cell_id")
            if not isinstance(cell_id, str):
                raise SelectorUniverseCensusDrift("selector cell_id is malformed")
            cast(list[str], record["selector_cells"]).append(cell_id)
    selected = list(by_key.values())
    for record in selected:
        record["selector_cells"] = sorted(set(cast(list[str], record["selector_cells"])))
    return tuple(sorted(selected, key=_identity_sort_key))


def _check_frozen_selector_source(
    repo_root: Path,
    selector_result_path: Path | None,
) -> tuple[dict[str, object], str]:
    tree_process = subprocess.run(
        ["git", "rev-parse", f"{SELECTOR_COMMIT}^{{tree}}"],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    if tree_process.returncode != 0 or tree_process.stdout.strip() != SELECTOR_TREE:
        raise SelectorUniverseCensusDrift(
            f"selector authority tree drift: {tree_process.stdout.strip()} != {SELECTOR_TREE}"
        )
    if selector_result_path is None:
        result_process = subprocess.run(
            ["git", "show", f"{SELECTOR_COMMIT}:{SELECTOR_RESULT_RELATIVE_PATH.as_posix()}"],
            cwd=repo_root,
            check=False,
            capture_output=True,
        )
        if result_process.returncode != 0:
            raise UnresolvedSource("frozen selector result Git object is unavailable")
        raw = result_process.stdout
        source_locator = f"{SELECTOR_COMMIT}:{SELECTOR_RESULT_RELATIVE_PATH.as_posix()}"
    else:
        path = selector_result_path.resolve()
        if not path.is_file():
            raise UnresolvedSource(f"selector result file is missing: {path}")
        raw = path.read_bytes()
        source_locator = path.as_posix()
    if _sha256(raw) != SELECTOR_RESULT_SHA256:
        raise SelectorUniverseCensusDrift(
            f"selector result hash drift: {_sha256(raw)} != {SELECTOR_RESULT_SHA256}"
        )
    try:
        selector_value: object = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SelectorUniverseCensusDrift("frozen selector result is not JSON") from exc
    if not isinstance(selector_value, dict):
        raise SelectorUniverseCensusDrift("frozen selector result is not an object")
    return cast(dict[str, object], selector_value), source_locator


def _catalog_descriptors(store: StaticSourceStore) -> tuple[dict[str, Any], ...]:
    module = store.load_path(CATALOG_PATH)
    tuple_node = _find_strategy_tuple(module, "_PRODUCTION_DESCRIPTORS")
    descriptors: list[dict[str, Any]] = []
    for element in tuple_node.elts:
        if (
            not isinstance(element, ast.Call)
            or not isinstance(element.func, ast.Name)
            or element.func.id != "StrategyDescriptor"
        ):
            raise LineageSupplementError("production catalog contains a non-descriptor row")
        keywords = _keyword_map(element)
        strategy_id = _required_field(keywords, "strategy_id", module, {})
        version = _required_field(keywords, "version", module, {})
        adapter_path_expression = keywords.get("adapter_path")
        adapter_path = (
            None
            if adapter_path_expression is None
            else _static_string(adapter_path_expression, module, {})
        )
        min_history_expression = keywords.get("min_history")
        min_history = (
            None
            if min_history_expression is None
            else _static_int(min_history_expression, module, {})
        )
        native_ticket_count_expression = keywords.get("native_ticket_count")
        native_ticket_count = (
            None
            if native_ticket_count_expression is None
            else _static_int(native_ticket_count_expression, module, {})
        )
        lottery_expression = keywords.get("lottery_types")
        lottery_types: list[str] = []
        if isinstance(lottery_expression, (ast.Tuple, ast.List)):
            for item in lottery_expression.elts:
                if not isinstance(item, ast.Attribute):
                    raise LineageSupplementError(f"{strategy_id}: dynamic catalog lottery type")
                enum_name = _static_value(item, module, {})
                if not isinstance(enum_name, str):
                    raise LineageSupplementError(f"{strategy_id}: malformed catalog lottery type")
                lottery_types.append(enum_name)
        else:
            raise LineageSupplementError(f"{strategy_id}: catalog lottery types are not static")
        response_shape_expression = keywords.get("response_shape")
        response_shape = (
            None
            if response_shape_expression is None
            else _static_value(response_shape_expression, module, {})
        )
        provenance_expression = keywords.get("provenance")
        provenance_value = (
            ()
            if provenance_expression is None
            else _static_value(provenance_expression, module, {})
        )
        provenance = _string_tuple(provenance_value)
        if (
            not isinstance(strategy_id, str)
            or not isinstance(version, str)
            or (min_history is not None and type(min_history) is not int)
            or (native_ticket_count is not None and type(native_ticket_count) is not int)
            or not isinstance(response_shape, (str, type(None)))
            or provenance is None
        ):
            raise LineageSupplementError(f"{strategy_id}: malformed production catalog row")
        descriptors.append(
            {
                "strategy_id": strategy_id,
                "strategy_version": version,
                "lottery_types": tuple(lottery_types),
                "adapter_path": adapter_path,
                "min_history": min_history,
                "native_ticket_count": native_ticket_count,
                "response_shape": response_shape,
                "provenance": provenance,
                "catalog_locator": _locator(module, element, f"StrategyDescriptor[{strategy_id}]"),
            }
        )
    return tuple(descriptors)


def _production_match(
    identity: dict[str, Any],
    descriptors: tuple[dict[str, Any], ...],
) -> dict[str, Any] | None:
    lottery_enum = LOTTERY_TO_ENUM[cast(str, identity["lottery_id"])]
    matches = [
        descriptor
        for descriptor in descriptors
        if descriptor["strategy_id"] == identity["strategy_id"]
        and descriptor["strategy_version"] == identity["strategy_version"]
        and lottery_enum in descriptor["lottery_types"]
    ]
    if len(matches) > 1:
        raise LineageSupplementError(
            f"multiple exact production catalog matches: {identity['strategy_id']}"
        )
    return None if not matches else matches[0]


def _binding_identity_fields(identity: dict[str, Any]) -> dict[str, JSONValue]:
    return {
        "source_authority_id": cast(str, identity["source_authority_id"]),
        "lottery_id": cast(str, identity["lottery_id"]),
        "strategy_id": cast(str, identity["strategy_id"]),
        "strategy_version": cast(str, identity["strategy_version"]),
        "authority_qualified_identity_key": list(
            authority_qualified_key(
                cast(str, identity["source_authority_id"]),
                cast(str, identity["lottery_id"]),
                cast(str, identity["strategy_id"]),
                cast(str, identity["strategy_version"]),
            )
        ),
    }


def _fingerprinted_row(
    identity: dict[str, Any],
    *,
    replay_spec_source_locator: str,
    source_authority: dict[str, JSONValue],
    implementation_module: str,
    implementation_path: str,
    callable_or_class_symbol: str,
    callable_symbol: str,
    static_parameters: dict[str, JSONValue],
    source_blob_digests: tuple[dict[str, str], ...],
    structural_components: tuple[dict[str, str], ...],
    donor_provenance_references: dict[str, JSONValue],
    extra_fields: dict[str, JSONValue] | None = None,
) -> dict[str, JSONValue]:
    source_blob_digest = _stable_digest(
        [cast(dict[str, JSONValue], item) for item in source_blob_digests]
    )
    structural_digest = _stable_digest(
        [cast(dict[str, JSONValue], item) for item in structural_components]
    )
    fingerprint_payload: dict[str, JSONValue] = {
        **_binding_identity_fields(identity),
        "replay_spec_source_locator": replay_spec_source_locator,
        "source_commit_ref_authority": source_authority,
        "implementation_module": implementation_module,
        "implementation_path": implementation_path,
        "callable_or_class_symbol": callable_or_class_symbol,
        "callable_symbol": callable_symbol,
        "canonicalized_static_binding_parameters": static_parameters,
        "source_blob_digest_sha256": source_blob_digest,
        "structural_source_digest_sha256": structural_digest,
    }
    fingerprint = _stable_digest(fingerprint_payload)
    row: dict[str, JSONValue] = {
        **_binding_identity_fields(identity),
        "replay_spec_source_locator": replay_spec_source_locator,
        "source_commit_ref_authority": source_authority,
        "source_commit": source_authority.get("source_commit"),
        "source_ref": source_authority.get("source_ref"),
        "implementation_module": implementation_module,
        "implementation_path": implementation_path,
        "callable_or_class_symbol": callable_or_class_symbol,
        "callable_symbol": callable_symbol,
        "canonicalized_static_binding_parameters": static_parameters,
        "source_blob_digests": [cast(dict[str, JSONValue], item) for item in source_blob_digests],
        "source_blob_digest_sha256": source_blob_digest,
        "structural_source_components": [
            cast(dict[str, JSONValue], item) for item in structural_components
        ],
        "structural_source_digest_sha256": structural_digest,
        "binding_fingerprint": f"sha256:{fingerprint}",
        "binding_fingerprint_sha256": fingerprint,
        "donor_provenance_references": donor_provenance_references,
        "resolution_status": "RESOLVED_REPLAY_BINDING",
        "unresolved_reason": None,
    }
    if extra_fields:
        row.update(extra_fields)
    return row


def _build_production_row(
    identity: dict[str, Any],
    descriptor: dict[str, Any],
    store: StaticSourceStore,
) -> dict[str, JSONValue]:
    adapter_path = descriptor.get("adapter_path")
    if not isinstance(adapter_path, str) or adapter_path.count(":") != 1:
        raise UnresolvedSource(f"{identity['strategy_id']}: production adapter path unresolved")
    module_name, class_name = adapter_path.split(":", 1)
    class_reference = SymbolReference(module_name, class_name)
    class_symbol, execution_symbol = _class_execution_symbol(store, class_reference)
    implementation_path = class_symbol.module.relative_path
    current_paths = _current_source_paths(
        store.repo_root,
        (implementation_path, CATALOG_PATH.as_posix()),
    )
    blobs = _source_blob_digests(store.repo_root, current_paths)
    components = (
        {
            "locator": descriptor["catalog_locator"],
            "normalized_ast_sha256": _stable_digest(descriptor),
        },
        {"locator": class_symbol.locator, "normalized_ast_sha256": _node_digest(class_symbol.node)},
    )
    callable_symbol = (
        execution_symbol.reference.as_text()
        if execution_symbol is not None
        else class_reference.as_text()
    )
    static_parameters: dict[str, JSONValue] = {
        "catalog_contract": {
            "lottery_types": list(cast(tuple[str, ...], descriptor["lottery_types"])),
            "min_history": descriptor["min_history"],
            "native_ticket_count": descriptor["native_ticket_count"],
            "response_shape": descriptor["response_shape"],
        },
        "adapter_factory": adapter_path,
    }
    return _fingerprinted_row(
        identity,
        replay_spec_source_locator=cast(str, descriptor["catalog_locator"]),
        source_authority=_source_authority(cast(str, identity["lottery_id"])),
        implementation_module=module_name,
        implementation_path=implementation_path,
        callable_or_class_symbol=class_reference.as_text(),
        callable_symbol=callable_symbol,
        static_parameters=static_parameters,
        source_blob_digests=blobs,
        structural_components=components,
        donor_provenance_references={
            "catalog_provenance": list(cast(tuple[str, ...], descriptor["provenance"])),
            "donor_identity_alias": False,
        },
        extra_fields={"join_status": "PRODUCTION_CATALOG_EXACT_JOIN"},
    )


def _build_p638_row(
    identity: dict[str, Any],
    spec: StaticSpec,
    module: StaticModule,
    store: StaticSourceStore,
) -> dict[str, JSONValue]:
    resolution, symbols = _source_symbol_for_callable(
        store,
        module,
        spec.callable_expression_node,
    )
    callable_symbol = cast(
        SymbolReference,
        resolution.get("reference", resolution.get("factory_reference")),
    )
    callable_text = callable_symbol.as_text()
    implementation_module = module.module_name
    implementation_path = module.relative_path
    current_paths = _current_source_paths(
        store.repo_root,
        spec.source_paths,
        (implementation_path, *(symbol.module.relative_path for symbol in symbols)),
    )
    blobs = _source_blob_digests(store.repo_root, current_paths)
    components = _source_components(spec, symbols)
    static_parameters = dict(spec.static_parameters)
    static_parameters["callable_resolution"] = {
        "kind": resolution["kind"],
        "expression": resolution["expression"],
    }
    extra: dict[str, JSONValue] = {}
    if resolution["kind"] == "STATIC_WRAPPER":
        extra["wrapped_callable_symbol"] = _json_reference(
            cast(SymbolReference, resolution["wrapped_reference"])
        )
        extra["wrapper_symbol"] = _json_reference(
            cast(SymbolReference, resolution["factory_reference"])
        )
    return _fingerprinted_row(
        identity,
        replay_spec_source_locator=spec.spec_locator,
        source_authority=_source_authority(cast(str, identity["lottery_id"])),
        implementation_module=implementation_module,
        implementation_path=implementation_path,
        callable_or_class_symbol=callable_text,
        callable_symbol=callable_text,
        static_parameters=static_parameters,
        source_blob_digests=blobs,
        structural_components=components,
        donor_provenance_references=spec.provenance,
        extra_fields=extra,
    )


def _t539_r2_assignment_locator(module: StaticModule) -> tuple[str, dict[str, str]]:
    expression = module.assignments.get("BIGLOTTO68_TO_T539_CROSS_LOTTERY_R2_STRATEGY_SPECS")
    if expression is None:
        raise UnresolvedSource("T539 R2 strategy-spec assignment is missing")
    locator = _locator(
        module,
        expression,
        "BIGLOTTO68_TO_T539_CROSS_LOTTERY_R2_STRATEGY_SPECS",
    )
    return (
        locator,
        {
            "locator": locator,
            "normalized_ast_sha256": _node_digest(expression),
        },
    )


def _build_t539_native_row(
    identity: dict[str, Any],
    spec: StaticSpec,
    module: StaticModule,
    store: StaticSourceStore,
) -> dict[str, JSONValue]:
    resolution, symbols = _source_symbol_for_callable(
        store,
        module,
        spec.callable_expression_node,
    )
    factory = cast(SymbolReference, resolution.get("reference"))
    class_symbol, execution_symbol = _class_execution_symbol(store, factory)
    implementation_path = class_symbol.module.relative_path
    current_paths = _current_source_paths(
        store.repo_root,
        spec.source_paths,
        (T539_RUNNER_PATH.as_posix(), implementation_path),
    )
    blobs = _source_blob_digests(store.repo_root, current_paths)
    components = _source_components(spec, (class_symbol, *(symbols)), extra_components=())
    callable_text = (
        execution_symbol.reference.as_text()
        if execution_symbol is not None
        else factory.as_text()
    )
    static_parameters = dict(spec.static_parameters)
    static_parameters["adapter_class"] = factory.as_text()
    return _fingerprinted_row(
        identity,
        replay_spec_source_locator=spec.spec_locator,
        source_authority=_source_authority(cast(str, identity["lottery_id"])),
        implementation_module=factory.module_name,
        implementation_path=implementation_path,
        callable_or_class_symbol=factory.as_text(),
        callable_symbol=callable_text,
        static_parameters=static_parameters,
        source_blob_digests=blobs,
        structural_components=components,
        donor_provenance_references=spec.provenance,
    )


def _build_t539_r2_row(
    identity: dict[str, Any],
    spec: StaticSpec,
    store: StaticSourceStore,
) -> dict[str, JSONValue]:
    runner_module = store.load_path(T539_RUNNER_PATH)
    portable_module = store.load_path(T539_PORTABLE_PATH)
    portable_class = SymbolReference(
        "lottolab.strategies.adapters.daily539_biglotto_portable",
        "Daily539BigLottoPortableAdapter",
    )
    class_symbol, execution_symbol = _class_execution_symbol(store, portable_class)
    _resolution, predictor_symbols = _source_symbol_for_callable(
        store,
        portable_module,
        spec.callable_expression_node,
    )
    r2_locator, r2_component = _t539_r2_assignment_locator(runner_module)
    current_paths = _current_source_paths(
        store.repo_root,
        spec.source_paths,
        (
            T539_RUNNER_PATH.as_posix(),
            portable_module.relative_path,
            class_symbol.module.relative_path,
            *(symbol.module.relative_path for symbol in predictor_symbols),
        ),
    )
    blobs = _source_blob_digests(store.repo_root, current_paths)
    components = _source_components(
        spec,
        (class_symbol, *(predictor_symbols)),
        extra_components=(r2_component,),
    )
    execution_callable = (
        execution_symbol.reference.as_text()
        if execution_symbol is not None
        else portable_class.as_text()
    )
    static_parameters = dict(spec.static_parameters)
    static_parameters.update(
        {
            "adapter_class": portable_class.as_text(),
            "r2_replay_spec_composition": r2_locator,
            "target_game_spec": "DAILY_539",
        }
    )
    donor = dict(spec.provenance)
    donor["donor_relation_is_canonical_identity"] = False
    return _fingerprinted_row(
        identity,
        replay_spec_source_locator=f"{r2_locator}; {spec.spec_locator}",
        source_authority=_source_authority(cast(str, identity["lottery_id"]), t539_r2=True),
        implementation_module=portable_class.module_name,
        implementation_path=portable_module.relative_path,
        callable_or_class_symbol=portable_class.as_text(),
        callable_symbol=execution_callable,
        static_parameters=static_parameters,
        source_blob_digests=blobs,
        structural_components=components,
        donor_provenance_references=donor,
        extra_fields={
            "predictor_symbol": spec.callable_expression,
            "t539_r2_source_pin_correction": {
                "first_definition_commit": T539_R2_FIRST_SOURCE_COMMIT,
                "rejected_commit": T539_R2_REJECTED_SOURCE_COMMIT,
                "rejection_reason": (
                    "b2ce6a3 predates the R2 portable definitions and is not "
                    "accepted as their implementation source."
                ),
            },
        },
    )


def _combined_accounting(
    selected: tuple[dict[str, Any], ...],
    production_rows: tuple[dict[str, JSONValue], ...],
    supplement_rows: tuple[dict[str, JSONValue], ...],
) -> dict[str, JSONValue]:
    selected_keys = {
        tuple(cast(list[str], identity["authority_qualified_identity_key"]))
        for identity in selected
    }
    accounted_keys = {
        tuple(cast(list[str], row["authority_qualified_identity_key"]))
        for row in (*production_rows, *supplement_rows)
    }
    if selected_keys != accounted_keys:
        missing = sorted(selected_keys - accounted_keys)
        extra = sorted(accounted_keys - selected_keys)
        raise LineageSupplementError(
            f"combined accounting mismatch; missing={missing}; extra={extra}"
        )
    return {
        "qualified_selector_identities": len(selected_keys),
        "production_exact_joins": len(production_rows),
        "supplement_rows": len(supplement_rows),
        "accounted_identities": len(accounted_keys),
        "accounting_is_complete": len(selected_keys) == len(accounted_keys) == 135,
    }


def build_result(
    repo_root: Path,
    selector_result_path: Path | None = None,
) -> dict[str, JSONValue]:
    """Build the supplement result from frozen selector and exact source ASTs."""

    repo_root = repo_root.resolve()
    selector, selector_locator = _check_frozen_selector_source(repo_root, selector_result_path)
    selected = extract_selected_identities(selector)
    if selector.get("source_authorities") is None:
        raise SelectorUniverseCensusDrift("selector source authorities are absent")
    selected_counts = Counter(cast(str, identity["lottery_id"]) for identity in selected)
    if dict(selected_counts) != EXPECTED_SELECTED_COUNTS:
        raise SelectorUniverseCensusDrift(
            f"selected census drift: {dict(selected_counts)} != {EXPECTED_SELECTED_COUNTS}"
        )
    raw_labels = {cast(str, identity["strategy_id"]) for identity in selected}
    if len(raw_labels) != 134:
        raise SelectorUniverseCensusDrift(f"raw label drift: {len(raw_labels)} != 134")
    collision_rows = [
        identity
        for label in sorted(raw_labels)
        if sum(cast(str, identity["strategy_id"]) == label for identity in selected) > 1
        for identity in selected
        if identity["strategy_id"] == label
    ]
    collision_ids = sorted({cast(str, row["strategy_id"]) for row in collision_rows})
    if collision_ids != ["midfreq_fourier_2bet"]:
        raise SelectorUniverseCensusDrift(f"raw-label collision drift: {collision_ids}")

    store = StaticSourceStore(repo_root)
    p638_specs = _p638_specs(store)
    t539_specs = _t539_direct_specs(store)
    portable_specs = _portable_specs(store)
    t539_specs.update(portable_specs)
    descriptors = _catalog_descriptors(store)

    production_rows: list[dict[str, JSONValue]] = []
    supplement_rows: list[dict[str, JSONValue]] = []
    unresolved: list[dict[str, Any]] = []
    for identity in selected:
        lottery = cast(str, identity["lottery_id"])
        key = (cast(str, identity["strategy_id"]), cast(str, identity["strategy_version"]))
        descriptor = _production_match(identity, descriptors)
        if descriptor is not None:
            production_rows.append(_build_production_row(identity, descriptor, store))
            continue
        try:
            if lottery == "P638":
                spec_and_module = p638_specs.get(key)
                if spec_and_module is None:
                    raise UnresolvedSource(f"missing P638 spec: {key}")
                spec, module = spec_and_module
                supplement_rows.append(_build_p638_row(identity, spec, module, store))
            elif lottery == "T539":
                spec_and_module = t539_specs.get(key)
                if spec_and_module is None:
                    raise UnresolvedSource(f"missing T539 spec: {key}")
                spec, module = spec_and_module
                if key in portable_specs:
                    supplement_rows.append(_build_t539_r2_row(identity, spec, store))
                else:
                    supplement_rows.append(_build_t539_native_row(identity, spec, module, store))
            else:
                raise UnresolvedSource(f"unexpected supplement lottery: {lottery}")
        except (LineageSupplementError, KeyError) as exc:
            unresolved.append({
                **_binding_identity_fields(identity),
                "resolution_status": "UNRESOLVED_SOURCE_PIN",
                "unresolved_reason": str(exc),
            })
    if unresolved:
        raise UnresolvedSource(
            "unresolved supplement rows: "
            + ", ".join(
                cast(str, item["strategy_id"]) + ":" + cast(str, item["unresolved_reason"])
                for item in unresolved
            )
        )

    production_rows_tuple = tuple(sorted(production_rows, key=_identity_sort_key))
    supplement_rows_tuple = tuple(sorted(supplement_rows, key=_identity_sort_key))
    if len(production_rows_tuple) != 25 or len(supplement_rows_tuple) != 110:
        raise SelectorUniverseCensusDrift(
            "join/supplement count drift: "
            f"{len(production_rows_tuple)}/{len(supplement_rows_tuple)}"
        )
    by_lottery: dict[str, dict[str, int]] = {}
    for lottery in LOTTERY_ORDER:
        by_lottery[lottery] = {
            "selected": sum(row["lottery_id"] == lottery for row in selected),
            "production_exact_joins": sum(
                row["lottery_id"] == lottery for row in production_rows_tuple
            ),
            "supplement_rows": sum(row["lottery_id"] == lottery for row in supplement_rows_tuple),
        }
        if by_lottery[lottery] != {
            "selected": EXPECTED_SELECTED_COUNTS[lottery],
            "production_exact_joins": EXPECTED_PRODUCTION_COUNTS[lottery],
            "supplement_rows": EXPECTED_SUPPLEMENT_COUNTS[lottery],
        }:
            raise SelectorUniverseCensusDrift(f"{lottery} census drift: {by_lottery[lottery]}")

    selected_json: list[dict[str, JSONValue]] = []
    for identity in selected:
        selected_json.append({
            **_binding_identity_fields(identity),
            "selector_cells": cast(list[JSONValue], identity["selector_cells"]),
        })
    all_rows = (*production_rows_tuple, *supplement_rows_tuple)
    binding_fingerprint = _stable_digest(
        [
            {
                "identity": row["authority_qualified_identity_key"],
                "resolution_status": row["resolution_status"],
                "binding_fingerprint_sha256": row["binding_fingerprint_sha256"],
            }
            for row in all_rows
        ]
    )
    collision_identity_keys = [
        row["authority_qualified_identity_key"]
        for row in selected_json
        if row["strategy_id"] == "midfreq_fourier_2bet"
    ]
    by_lottery_json: dict[str, JSONValue] = {
        lottery: cast(dict[str, JSONValue], counts)
        for lottery, counts in by_lottery.items()
    }
    result: dict[str, JSONValue] = {
        "schema_version": SCHEMA_VERSION,
        "study_id": STUDY_ID,
        "scope": {
            "purpose": (
                "Static lineage supplement for selector identities absent from "
                "production catalog"
            ),
            "selector_rerun": "NOT RUN",
            "historical_replay": "NOT RUN",
            "database_access": "NO",
            "predictive_advantage": "NOT CLAIMED",
        },
        "selector_authority": {
            "commit": SELECTOR_COMMIT,
            "tree": SELECTOR_TREE,
            "result_path": SELECTOR_RESULT_RELATIVE_PATH.as_posix(),
            "result_sha256": SELECTOR_RESULT_SHA256,
            "observed_input_locator": selector_locator,
        },
        "source_authority": {
            "p638_spec_paths": [path.as_posix() for path in P638_SPEC_PATHS],
            "t539_runner_path": T539_RUNNER_PATH.as_posix(),
            "t539_r2_portable_spec_path": T539_PORTABLE_PATH.as_posix(),
            "current_base_head": CURRENT_BASE_HEAD,
            "current_base_tree": CURRENT_BASE_TREE,
            "t539_r2_first_definition_commit": T539_R2_FIRST_SOURCE_COMMIT,
            "t539_r2_rejected_commit": T539_R2_REJECTED_SOURCE_COMMIT,
        },
        "census": {
            "qualified_selector_identities": len(selected),
            "raw_selector_labels": len(raw_labels),
            "production_exact_joins": len(production_rows_tuple),
            "supplement_rows": len(supplement_rows_tuple),
            "by_lottery": by_lottery_json,
        },
        "qualified_selector_identities": cast(list[JSONValue], selected_json),
        "production_exact_joins": cast(list[JSONValue], list(production_rows_tuple)),
        "supplement_rows": cast(list[JSONValue], list(supplement_rows_tuple)),
        "combined_accounting": _combined_accounting(
            tuple(selected_json),
            production_rows_tuple,
            supplement_rows_tuple,
        ),
        "invariants": {
            "canonical_identity_key": [
                "source_authority_id",
                "lottery_id",
                "strategy_id",
                "strategy_version",
            ],
            "raw_label_collision_strategy_id": "midfreq_fourier_2bet",
            "raw_label_collision_identity_keys": collision_identity_keys,
            "raw_label_collision_is_two_identities": len(collision_identity_keys) == 2,
            "safe_production_alias_mapping": "NO",
            "donor_relation_promoted_to_canonical_identity": "NO",
            "cross_lottery_ports_collapsed": "NO",
            "t539_r2_source_pin_correction": {
                "accepted": T539_R2_FIRST_SOURCE_COMMIT,
                "rejected": T539_R2_REJECTED_SOURCE_COMMIT,
            },
        },
        "classification_contract": {
            "allowed_row_states": list(ALLOWED_RESOLUTION_STATUSES),
            "supplement_success_state": "RESOLVED_REPLAY_BINDING",
            "unresolved_policy": "FAIL_CLOSED",
        },
        "binding_fingerprint_sha256": binding_fingerprint,
    }
    return result


def _row_table(rows: list[dict[str, JSONValue]]) -> str:
    lines = [
        "| Lottery | Strategy ID | Version | Implementation | Callable | Status |",
        "|---|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            (
                "| {lottery} | `{strategy}` | `{version}` | `{module}` | "
                "`{callable}` | `{status}` |"
            ).format(
                lottery=row["lottery_id"],
                strategy=row["strategy_id"],
                version=row["strategy_version"],
                module=row["implementation_module"],
                callable=row["callable_symbol"],
                status=row["resolution_status"],
            )
        )
    return "\n".join(lines)


def render_markdown(result: dict[str, JSONValue], result_sha256: str, result_bytes: int) -> str:
    census = cast(dict[str, Any], result["census"])
    source = cast(dict[str, Any], result["source_authority"])
    invariants = cast(dict[str, Any], result["invariants"])
    production = cast(list[dict[str, JSONValue]], result["production_exact_joins"])
    supplement = cast(list[dict[str, JSONValue]], result["supplement_rows"])
    selector_commit = source.get("selector_commit", SELECTOR_COMMIT)
    selector_tree = source.get("selector_tree", SELECTOR_TREE)
    lines = [
        "# Selector universe lineage supplement R1",
        "",
        "Status: SEALED static deterministic supplement.",
        "",
        "This artifact accounts for selector identities that are not exact joins "
        "to the production StrategyDescriptor catalog. It reads frozen selector "
        "JSON and exact source specifications with ASTs only; it does not run a "
        "selector, historical replay, database access, or strategy implementation.",
        "",
        "## Frozen authority and census",
        "",
        f"- Selector commit/tree: `{selector_commit}` / `{selector_tree}`",
        f"- Selector result SHA-256: `{SELECTOR_RESULT_SHA256}`",
        f"- Result bytes: `{result_bytes}`",
        f"- Result SHA-256: `{result_sha256}`",
        f"- P638 spec sources: `{', '.join(cast(list[str], source['p638_spec_paths']))}`",
        f"- T539 replay-spec source: `{source['t539_runner_path']}`",
        f"- T539 R2 portable spec source: `{source['t539_r2_portable_spec_path']}`",
        "",
        "| Lottery | Qualified selected | Production exact joins | Supplement rows |",
        "|---|---:|---:|---:|",
    ]
    for lottery in LOTTERY_ORDER:
        counts = cast(dict[str, int], census["by_lottery"][lottery])
        lines.append(
            f"| {lottery} | {counts['selected']} | "
            f"{counts['production_exact_joins']} | {counts['supplement_rows']} |"
        )
    lines.extend(
        [
            "| **Total** | **135** | **25** | **110** |",
            "",
            f"- Raw selector labels: **{census['raw_selector_labels']}**.",
            "- The raw-label collision is `midfreq_fourier_2bet`; its P638 and T539 "
            "authority-qualified keys remain two separate identities.",
            "- Safe production alias mapping: **NO**.",
            "- Donor relation promoted to canonical identity: **NO**.",
            "",
            "## T539 R2 source-pin correction",
            "",
            f"R2 portable definitions first appear at `{T539_R2_FIRST_SOURCE_COMMIT}`. "
            f"`{T539_R2_REJECTED_SOURCE_COMMIT}` (`b2ce6a3…`) is explicitly rejected "
            "as the T539 R2 implementation source. The canonical implementation "
            f"tree is pinned to `{CURRENT_BASE_HEAD}`.",
            "",
            "## Supplement bindings",
            "",
            _row_table(supplement),
            "",
            "## Production exact joins",
            "",
            _row_table(production),
            "",
            "## Explicit handoff facts",
            "",
            "```text",
            "QUALIFIED_SELECTOR_IDENTITIES = 135",
            "RAW_SELECTOR_LABELS = 134",
            "PRODUCTION_EXACT_JOINS = 25",
            "SUPPLEMENT_ROWS = 110",
            "P638_SUPPLEMENT_ROWS = 56",
            "T539_SUPPLEMENT_ROWS = 54",
            "SAFE_PRODUCTION_ALIAS_MAPPING = NO",
            "SELECTOR_RERUN = NOT RUN",
            "HISTORICAL_REPLAY = NOT RUN",
            "DB_ACCESS = NO",
            "PREDICTIVE_ADVANTAGE = NOT CLAIMED",
            "```",
            "",
            "Combined accounting is 135/135, and every supplement row is "
            "`RESOLVED_REPLAY_BINDING`.",
            "",
        ]
    )
    del invariants
    return "\n".join(lines)


def write_artifacts(
    repo_root: Path,
    selector_result_path: Path | None = None,
    *,
    output_path: Path = OUTPUT_PATH,
    report_path: Path = REPORT_PATH,
) -> tuple[str, int, str]:
    result = build_result(repo_root, selector_result_path)
    result_bytes = canonical_json_bytes(result)
    result_sha256 = _sha256(result_bytes)
    report = render_markdown(result, result_sha256, len(result_bytes))
    output_file = repo_root / output_path
    report_file = repo_root / report_path
    output_file.parent.mkdir(parents=True, exist_ok=True)
    report_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_bytes(result_bytes)
    report_file.write_text(report, encoding="utf-8")
    return result_sha256, len(result_bytes), _sha256(report.encode("utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--selector-result", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--report", type=Path, default=REPORT_PATH)
    args = parser.parse_args()
    result_sha256, result_bytes, report_sha256 = write_artifacts(
        args.repo_root,
        args.selector_result,
        output_path=args.output,
        report_path=args.report,
    )
    print(f"result_sha256={result_sha256}")
    print(f"result_bytes={result_bytes}")
    print(f"report_sha256={report_sha256}")
    print("selector_rerun=NOT RUN")
    print("historical_replay=NOT RUN")
    print("db_access=NO")


if __name__ == "__main__":
    main()
