"""Resolve the four Wave 26 injected bindings without importing LottoLab.

The original static-lineage study deliberately stopped when an adapter
constructor required ``wave26_authority``.  This supplemental analyzer follows
that dependency through the canonical composition root using Python ASTs only.
It never imports a LottoLab module, opens a database, or executes a strategy.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal, cast

type JSONValue = None | bool | int | str | list[JSONValue] | dict[str, JSONValue]
type ResolutionClassification = Literal[
    "RESOLVED_STATIC_IMPLEMENTATION",
    "RESOLVED_RUNTIME_FACTORY_IDENTITY",
    "REMAINS_RUNTIME_DATA_DEPENDENT",
    "AMBIGUOUS_BINDING",
]
type RuntimeDataEffect = Literal["NO", "YES", "UNKNOWN"]

STUDY_ID = "WAVE26_DYNAMIC_BINDING_RESOLUTION_R1"
SCHEMA_VERSION = "wave26-dynamic-binding-resolution/v1"
ORIGINAL_STUDY_ID = "STRATEGY_MATRIX_STATIC_LINEAGE_REDUNDANCY_MAP_R1"
AUTHORITY_PARAMETER = "wave26_authority"

CATALOG_PATH = Path("src/lottolab/strategies/catalog.py")
REGISTRY_PATH = Path("src/lottolab/strategies/executable_registry.py")
ADAPTER_PATH = Path("src/lottolab/strategies/adapters/biglotto_wave8.py")
COMPOSITION_PATH = Path("src/lottolab/application/use_cases/generate_bet.py")
WAVE26_IMPLEMENTATION_PATH = Path(
    "src/lottolab/application/legacy_source_native_portfolios_wave26.py"
)
ORIGINAL_RESULT_PATH = Path(
    "docs/research/matrix-native-results/"
    "strategy-matrix-static-lineage-redundancy-map-r1-result.json"
)
OUTPUT_PATH = Path(
    "docs/research/matrix-native-results/"
    "wave26-dynamic-binding-resolution-r1-result.json"
)
REPORT_PATH = Path("docs/research/wave26-dynamic-binding-resolution-r1.md")

TARGET_STRATEGY_IDS: Final = (
    "legacy_biglotto__test_ces__78d17c530ab8",
    "legacy_biglotto__test_dms__b63442289bd5",
    "legacy_biglotto__test_greedy_optimizer__82df7f878ece",
    "legacy_biglotto__test_mwsc__ba37643d6a3b",
)
ALLOWED_CLASSIFICATIONS: Final[tuple[ResolutionClassification, ...]] = (
    "RESOLVED_STATIC_IMPLEMENTATION",
    "RESOLVED_RUNTIME_FACTORY_IDENTITY",
    "REMAINS_RUNTIME_DATA_DEPENDENT",
    "AMBIGUOUS_BINDING",
)


class StaticBindingResolutionError(ValueError):
    """Required source wiring is absent, malformed, or contradictory."""


@dataclass(frozen=True, slots=True)
class SymbolReference:
    module_name: str
    symbol: str


@dataclass(frozen=True, slots=True)
class AssignmentInfo:
    node: ast.Assign | ast.AnnAssign
    value: ast.expr


@dataclass(frozen=True, slots=True)
class SourceModule:
    module_name: str
    relative_path: str
    source: str
    tree: ast.Module
    classes: dict[str, ast.ClassDef]
    functions: dict[str, ast.FunctionDef | ast.AsyncFunctionDef]
    assignments: dict[str, AssignmentInfo]
    imported_symbols: dict[str, SymbolReference]
    imported_modules: dict[str, str]


@dataclass(frozen=True, slots=True)
class SourceComponent:
    locator: str
    normalized_ast_sha256: str

    def as_json(self) -> dict[str, JSONValue]:
        return {
            "locator": self.locator,
            "normalized_ast_sha256": self.normalized_ast_sha256,
        }


@dataclass(frozen=True, slots=True)
class DescriptorBinding:
    strategy_id: str
    adapter_path: str
    locator: str
    node: ast.Call


@dataclass(frozen=True, slots=True)
class AdapterBinding:
    adapter_class_locator: str
    execution_callable_locator: str
    constructor_locator: str
    authority_type_name: str
    authority_type_expression: str
    authority_type_locator: str
    legacy_method_id: str
    components: tuple[SourceComponent, ...]


@dataclass(frozen=True, slots=True)
class ProviderResolution:
    classification: ResolutionClassification
    binding_kind: str
    injection_locators: tuple[str, ...]
    provider_locator: str | None
    provider_target_locator: str | None
    provider_target_reference: SymbolReference | None
    runtime_data_effect: RuntimeDataEffect
    reason: str
    components: tuple[SourceComponent, ...]


@dataclass(frozen=True, slots=True)
class _InjectionCandidate:
    owner: ast.FunctionDef | ast.AsyncFunctionDef
    call: ast.Call
    expression: ast.expr


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _node_digest(node: ast.AST) -> str:
    normalized = ast.dump(node, annotate_fields=True, include_attributes=False)
    return _sha256(normalized.encode("utf-8"))


def _compact_canonical_bytes(payload: JSONValue) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def canonical_json_bytes(payload: JSONValue) -> bytes:
    """Return deterministic, sorted, newline-terminated JSON bytes."""

    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ).rstrip("\n")
    return f"{serialized}\n".encode()


def _stable_digest(payload: JSONValue) -> str:
    return _sha256(_compact_canonical_bytes(payload))


def _assigned_names(node: ast.Assign | ast.AnnAssign) -> tuple[str, ...]:
    targets = node.targets if isinstance(node, ast.Assign) else (node.target,)
    return tuple(target.id for target in targets if isinstance(target, ast.Name))


def _resolve_import_module(current_module: str, imported: str | None, level: int) -> str:
    if level == 0:
        if imported is None:
            raise StaticBindingResolutionError("absolute import is missing a module")
        return imported
    package = current_module.split(".")[:-1]
    keep = len(package) - level + 1
    if keep < 0:
        raise StaticBindingResolutionError(
            f"invalid relative import in {current_module}"
        )
    suffix = [] if imported is None else imported.split(".")
    return ".".join(package[:keep] + suffix)


def parse_source_module(
    module_name: str,
    relative_path: str,
    source: str,
) -> SourceModule:
    """Parse one source module without importing or executing it."""

    if Path(relative_path).is_absolute():
        raise ValueError("source module paths must be repository-relative")
    tree = ast.parse(source, filename=relative_path)
    classes: dict[str, ast.ClassDef] = {}
    functions: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = {}
    assignments: dict[str, AssignmentInfo] = {}
    imported_symbols: dict[str, SymbolReference] = {}
    imported_modules: dict[str, str] = {}
    bound_names: Counter[str] = Counter()

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            bound_names[node.name] += 1
            classes[node.name] = node
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            bound_names[node.name] += 1
            functions[node.name] = node
        elif isinstance(node, (ast.Assign, ast.AnnAssign)) and node.value is not None:
            for name in _assigned_names(node):
                bound_names[name] += 1
                assignments[name] = AssignmentInfo(node=node, value=node.value)
        elif isinstance(node, ast.ImportFrom):
            imported_module = _resolve_import_module(
                module_name,
                node.module,
                node.level,
            )
            for alias in node.names:
                local_name = alias.asname or alias.name
                bound_names[local_name] += 1
                imported_symbols[local_name] = SymbolReference(
                    imported_module,
                    alias.name,
                )
        elif isinstance(node, ast.Import):
            for alias in node.names:
                local_name = alias.asname or alias.name.split(".", 1)[0]
                bound_names[local_name] += 1
                imported_modules[local_name] = alias.name

    duplicates = sorted(name for name, count in bound_names.items() if count > 1)
    if duplicates:
        raise StaticBindingResolutionError(
            f"duplicate top-level bindings in {relative_path}: {', '.join(duplicates)}"
        )
    return SourceModule(
        module_name=module_name,
        relative_path=relative_path,
        source=source,
        tree=tree,
        classes=classes,
        functions=functions,
        assignments=assignments,
        imported_symbols=imported_symbols,
        imported_modules=imported_modules,
    )


def _locator(module: SourceModule, node: ast.AST, symbol: str) -> str:
    line = getattr(node, "lineno", None)
    if not isinstance(line, int):
        raise StaticBindingResolutionError(f"{symbol} has no source line")
    return f"{module.relative_path}:{line}:{symbol}"


def _component(module: SourceModule, node: ast.AST, symbol: str) -> SourceComponent:
    return SourceComponent(
        locator=_locator(module, node, symbol),
        normalized_ast_sha256=_node_digest(node),
    )


def _static_string(
    expression: ast.expr,
    module: SourceModule,
    *,
    seen: frozenset[str] = frozenset(),
) -> str | None:
    if isinstance(expression, ast.Constant) and isinstance(expression.value, str):
        return expression.value
    if isinstance(expression, ast.BinOp) and isinstance(expression.op, ast.Add):
        left = _static_string(expression.left, module, seen=seen)
        right = _static_string(expression.right, module, seen=seen)
        return None if left is None or right is None else left + right
    if isinstance(expression, ast.Name) and expression.id not in seen:
        assignment = module.assignments.get(expression.id)
        if assignment is not None:
            return _static_string(
                assignment.value,
                module,
                seen=seen | {expression.id},
            )
    return None


def _keyword_map(call: ast.Call) -> dict[str, ast.expr]:
    keywords: dict[str, ast.expr] = {}
    for keyword in call.keywords:
        if keyword.arg is None:
            raise StaticBindingResolutionError("**kwargs are not statically resolvable")
        if keyword.arg in keywords:
            raise StaticBindingResolutionError(
                f"duplicate keyword in static call: {keyword.arg}"
            )
        keywords[keyword.arg] = keyword.value
    return keywords


def parse_target_descriptors(
    catalog: SourceModule,
    strategy_ids: tuple[str, ...] = TARGET_STRATEGY_IDS,
) -> dict[str, DescriptorBinding]:
    """Read only the requested StrategyDescriptor rows from the catalog AST."""

    descriptor_tuple: ast.Tuple | None = None
    for node in catalog.tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if any(
            isinstance(target, ast.Name) and target.id == "_PRODUCTION_DESCRIPTORS"
            for target in node.targets
        ):
            if descriptor_tuple is not None or not isinstance(node.value, ast.Tuple):
                raise StaticBindingResolutionError(
                    "_PRODUCTION_DESCRIPTORS must be one literal tuple"
                )
            descriptor_tuple = node.value
    if descriptor_tuple is None:
        raise StaticBindingResolutionError("_PRODUCTION_DESCRIPTORS was not found")

    wanted = frozenset(strategy_ids)
    found: dict[str, DescriptorBinding] = {}
    for expression in descriptor_tuple.elts:
        if not (
            isinstance(expression, ast.Call)
            and isinstance(expression.func, ast.Name)
            and expression.func.id == "StrategyDescriptor"
        ):
            continue
        keywords = _keyword_map(expression)
        strategy_node = keywords.get("strategy_id")
        if strategy_node is None:
            continue
        strategy_id = _static_string(strategy_node, catalog)
        if strategy_id not in wanted:
            continue
        if strategy_id in found:
            raise StaticBindingResolutionError(
                f"duplicate target StrategyDescriptor: {strategy_id}"
            )
        adapter_node = keywords.get("adapter_path")
        adapter_path = (
            None if adapter_node is None else _static_string(adapter_node, catalog)
        )
        if adapter_path is None or adapter_path.count(":") != 1:
            raise StaticBindingResolutionError(
                f"{strategy_id}: adapter_path is not one static module:symbol binding"
            )
        found[strategy_id] = DescriptorBinding(
            strategy_id=strategy_id,
            adapter_path=adapter_path,
            locator=_locator(catalog, expression, f"StrategyDescriptor[{strategy_id}]"),
            node=expression,
        )

    missing = sorted(wanted - found.keys())
    if missing:
        raise StaticBindingResolutionError(
            "target descriptors are missing: " + ", ".join(missing)
        )
    return found


def _direct_method(
    class_node: ast.ClassDef,
    name: str,
) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    matches = [
        node
        for node in class_node.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == name
    ]
    if len(matches) > 1:
        raise StaticBindingResolutionError(
            f"{class_node.name} declares {name} more than once"
        )
    return None if not matches else matches[0]


def _class_lineage(module: SourceModule, class_name: str) -> tuple[ast.ClassDef, ...]:
    lineage: list[ast.ClassDef] = []
    seen: set[str] = set()
    current = class_name
    while current in module.classes:
        if current in seen:
            raise StaticBindingResolutionError(f"cyclic class lineage at {current}")
        seen.add(current)
        class_node = module.classes[current]
        lineage.append(class_node)
        local_bases = [
            base.id
            for base in class_node.bases
            if isinstance(base, ast.Name) and base.id in module.classes
        ]
        if not local_bases:
            break
        if len(class_node.bases) != 1 or len(local_bases) != 1:
            raise StaticBindingResolutionError(
                f"{current}: local implementation lineage is ambiguous"
            )
        current = local_bases[0]
    return tuple(lineage)


def _class_assignment(class_node: ast.ClassDef, name: str) -> ast.expr | None:
    matches: list[ast.expr] = []
    for node in class_node.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)) or node.value is None:
            continue
        if name in _assigned_names(node):
            matches.append(node.value)
    if len(matches) > 1:
        raise StaticBindingResolutionError(
            f"{class_node.name}.{name} is assigned more than once"
        )
    return None if not matches else matches[0]


def _argument_annotation(
    function: ast.FunctionDef | ast.AsyncFunctionDef,
    parameter: str,
) -> ast.expr | None:
    arguments = [
        *function.args.posonlyargs,
        *function.args.args,
        *function.args.kwonlyargs,
    ]
    matches = [argument.annotation for argument in arguments if argument.arg == parameter]
    if len(matches) > 1:
        raise StaticBindingResolutionError(
            f"{function.name}.{parameter} is declared more than once"
        )
    return None if not matches else matches[0]


def resolve_adapter_binding(
    descriptor: DescriptorBinding,
    adapter: SourceModule,
) -> AdapterBinding:
    """Resolve the adapter hook, constructor injection type, and row binding."""

    adapter_module, adapter_class_name = descriptor.adapter_path.split(":", 1)
    if adapter_module != adapter.module_name:
        raise StaticBindingResolutionError(
            f"{descriptor.strategy_id}: unexpected adapter module {adapter_module}"
        )
    lineage = _class_lineage(adapter, adapter_class_name)
    if not lineage:
        raise StaticBindingResolutionError(
            f"{descriptor.strategy_id}: adapter class {adapter_class_name} was not found"
        )

    hook_owner: ast.ClassDef | None = None
    hook: ast.FunctionDef | ast.AsyncFunctionDef | None = None
    constructor_owner: ast.ClassDef | None = None
    constructor: ast.FunctionDef | ast.AsyncFunctionDef | None = None
    method_expression: ast.expr | None = None
    for class_node in lineage:
        if hook is None:
            hook = _direct_method(class_node, "_predict_all")
            if hook is not None:
                hook_owner = class_node
        if constructor is None:
            constructor = _direct_method(class_node, "__init__")
            if constructor is not None:
                constructor_owner = class_node
        if method_expression is None:
            method_expression = _class_assignment(class_node, "legacy_method_id")
    if hook is None or hook_owner is None:
        raise StaticBindingResolutionError(
            f"{descriptor.strategy_id}: _predict_all is not statically inherited"
        )
    if constructor is None or constructor_owner is None:
        raise StaticBindingResolutionError(
            f"{descriptor.strategy_id}: injected constructor was not found"
        )
    if method_expression is None:
        raise StaticBindingResolutionError(
            f"{descriptor.strategy_id}: legacy_method_id was not found"
        )
    legacy_method_id = _static_string(method_expression, adapter)
    if legacy_method_id is None:
        raise StaticBindingResolutionError(
            f"{descriptor.strategy_id}: legacy_method_id is runtime-dependent"
        )

    annotation = _argument_annotation(constructor, AUTHORITY_PARAMETER)
    if not isinstance(annotation, ast.Name):
        raise StaticBindingResolutionError(
            f"{descriptor.strategy_id}: {AUTHORITY_PARAMETER} type is not one static alias"
        )
    authority_assignment = adapter.assignments.get(annotation.id)
    if authority_assignment is None:
        raise StaticBindingResolutionError(
            f"{descriptor.strategy_id}: authority alias {annotation.id} was not found"
        )

    adapter_class = lineage[0]
    components = (
        _component(adapter, adapter_class, adapter_class.name),
        _component(
            adapter,
            hook,
            f"{hook_owner.name}.{hook.name}",
        ),
        _component(
            adapter,
            constructor,
            f"{constructor_owner.name}.{constructor.name}",
        ),
        _component(
            adapter,
            authority_assignment.node,
            annotation.id,
        ),
    )
    return AdapterBinding(
        adapter_class_locator=_locator(adapter, adapter_class, adapter_class.name),
        execution_callable_locator=_locator(
            adapter,
            hook,
            f"{hook_owner.name}.{hook.name}",
        ),
        constructor_locator=_locator(
            adapter,
            constructor,
            f"{constructor_owner.name}.{constructor.name}",
        ),
        authority_type_name=annotation.id,
        authority_type_expression=ast.unparse(authority_assignment.value),
        authority_type_locator=_locator(
            adapter,
            authority_assignment.node,
            annotation.id,
        ),
        legacy_method_id=legacy_method_id,
        components=components,
    )


def resolve_registry_loader(registry: SourceModule) -> SourceComponent:
    registry_class = registry.classes.get("ExecutableRegistry")
    if registry_class is None:
        raise StaticBindingResolutionError("ExecutableRegistry was not found")
    loader = _direct_method(registry_class, "load_adapter")
    if loader is None:
        raise StaticBindingResolutionError("ExecutableRegistry.load_adapter was not found")
    has_adapter_path = any(
        isinstance(node, ast.Attribute) and node.attr == "adapter_path"
        for node in ast.walk(loader)
    )
    has_module_import = any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "importlib"
        and node.func.attr == "import_module"
        for node in ast.walk(loader)
    )
    has_symbol_lookup = any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "getattr"
        for node in ast.walk(loader)
    )
    if not (has_adapter_path and has_module_import and has_symbol_lookup):
        raise StaticBindingResolutionError(
            "ExecutableRegistry.load_adapter no longer has one static adapter-path loader"
        )
    return _component(
        registry,
        loader,
        "ExecutableRegistry.load_adapter",
    )


def _function_imported_symbols(
    module: SourceModule,
    function: ast.FunctionDef | ast.AsyncFunctionDef,
) -> dict[str, SymbolReference]:
    imports = dict(module.imported_symbols)
    for node in ast.walk(function):
        if not isinstance(node, ast.ImportFrom):
            continue
        imported_module = _resolve_import_module(
            module.module_name,
            node.module,
            node.level,
        )
        for alias in node.names:
            imports[alias.asname or alias.name] = SymbolReference(
                imported_module,
                alias.name,
            )
    return imports


def _reference_from_expression(
    expression: ast.expr,
    module: SourceModule,
    owner: ast.FunctionDef | ast.AsyncFunctionDef,
    *,
    seen_assignments: frozenset[str] = frozenset(),
) -> SymbolReference | None:
    imports = _function_imported_symbols(module, owner)
    if isinstance(expression, ast.Name):
        if expression.id in module.functions:
            return SymbolReference(module.module_name, expression.id)
        imported = imports.get(expression.id)
        if imported is not None:
            return imported
        assignment = module.assignments.get(expression.id)
        if assignment is not None and expression.id not in seen_assignments:
            return _reference_from_expression(
                assignment.value,
                module,
                owner,
                seen_assignments=seen_assignments | {expression.id},
            )
        return None
    if (
        isinstance(expression, ast.Attribute)
        and isinstance(expression.value, ast.Name)
        and expression.value.id in module.imported_modules
    ):
        return SymbolReference(
            module.imported_modules[expression.value.id],
            expression.attr,
        )
    return None


class _ReturnCollector(ast.NodeVisitor):
    def __init__(self, root: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self._root = root
        self.returns: list[ast.Return] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        if node is self._root:
            self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        if node is self._root:
            self.generic_visit(node)

    def visit_Lambda(self, node: ast.Lambda) -> None:
        del node

    def visit_Return(self, node: ast.Return) -> None:
        self.returns.append(node)


def _returned_call(expression: ast.expr | None) -> ast.Call | None:
    current = expression
    while isinstance(current, (ast.Attribute, ast.Await)):
        current = current.value
    return current if isinstance(current, ast.Call) else None


def _provider_target(
    module: SourceModule,
    function: ast.FunctionDef | ast.AsyncFunctionDef,
) -> tuple[SymbolReference | None, bool]:
    collector = _ReturnCollector(function)
    collector.visit(function)
    references: set[SymbolReference] = set()
    saw_dynamic_return = False
    for returned in collector.returns:
        call = _returned_call(returned.value)
        if call is None:
            saw_dynamic_return = True
            continue
        reference = _reference_from_expression(call.func, module, function)
        if reference is None:
            saw_dynamic_return = True
        else:
            references.add(reference)
    if len(references) == 1 and not saw_dynamic_return:
        return next(iter(references)), False
    if not references and not collector.returns:
        return SymbolReference(module.module_name, function.name), False
    return None, True


def _symbol_node(
    reference: SymbolReference,
    modules: Mapping[str, SourceModule],
) -> tuple[SourceModule, ast.AST] | None:
    module = modules.get(reference.module_name)
    if module is None:
        return None
    function = module.functions.get(reference.symbol)
    if function is not None:
        return module, function
    class_node = module.classes.get(reference.symbol)
    if class_node is not None:
        return module, class_node
    assignment = module.assignments.get(reference.symbol)
    if assignment is not None:
        return module, assignment.node
    return None


def _symbol_locator(
    reference: SymbolReference,
    modules: Mapping[str, SourceModule],
) -> str:
    resolved = _symbol_node(reference, modules)
    if resolved is None:
        return f"{reference.module_name}:{reference.symbol}"
    module, node = resolved
    return _locator(module, node, reference.symbol)


def resolve_injected_provider_source(
    source: str,
    *,
    module_name: str = "fixture.composition",
    relative_path: str = "fixture/composition.py",
    authority_parameter: str = AUTHORITY_PARAMETER,
    provider_modules: Mapping[str, SourceModule] | None = None,
) -> ProviderResolution:
    """Classify one injected provider from source, failing open on uncertainty."""

    composition = parse_source_module(module_name, relative_path, source)
    modules = dict(provider_modules or {})
    modules[module_name] = composition
    candidates: list[_InjectionCandidate] = []
    for function in composition.functions.values():
        for node in ast.walk(function):
            if not isinstance(node, ast.Call):
                continue
            for keyword in node.keywords:
                if keyword.arg == authority_parameter:
                    candidates.append(
                        _InjectionCandidate(
                            owner=function,
                            call=node,
                            expression=keyword.value,
                        )
                    )
    if not candidates:
        return ProviderResolution(
            classification="AMBIGUOUS_BINDING",
            binding_kind="NO_INJECTION_SITE",
            injection_locators=(),
            provider_locator=None,
            provider_target_locator=None,
            provider_target_reference=None,
            runtime_data_effect="UNKNOWN",
            reason=f"no {authority_parameter} injection site was found",
            components=(),
        )

    expression_keys = {
        ast.dump(
            candidate.expression,
            annotate_fields=True,
            include_attributes=False,
        )
        for candidate in candidates
    }
    injection_locators = tuple(
        sorted(
            _locator(
                composition,
                candidate.call,
                f"{candidate.owner.name}[{authority_parameter}]",
            )
            for candidate in candidates
        )
    )
    injection_components = tuple(
        _component(
            composition,
            candidate.call,
            f"{candidate.owner.name}[{authority_parameter}]",
        )
        for candidate in sorted(candidates, key=lambda item: item.call.lineno)
    )
    if len(expression_keys) > 1:
        return ProviderResolution(
            classification="AMBIGUOUS_BINDING",
            binding_kind="MULTIPLE_DISTINCT_INJECTION_EXPRESSIONS",
            injection_locators=injection_locators,
            provider_locator=None,
            provider_target_locator=None,
            provider_target_reference=None,
            runtime_data_effect="UNKNOWN",
            reason=(
                f"{authority_parameter} has multiple distinct source providers; "
                "one binding cannot be selected statically"
            ),
            components=injection_components,
        )

    candidate = candidates[0]
    expression = candidate.expression
    if isinstance(expression, ast.Call):
        factory_reference = _reference_from_expression(
            expression.func,
            composition,
            candidate.owner,
        )
        if factory_reference is None:
            return ProviderResolution(
                classification="REMAINS_RUNTIME_DATA_DEPENDENT",
                binding_kind="DYNAMIC_FACTORY_SELECTION",
                injection_locators=injection_locators,
                provider_locator=None,
                provider_target_locator=None,
                provider_target_reference=None,
                runtime_data_effect="YES",
                reason=(
                    f"{authority_parameter} is returned by a factory whose identity "
                    "depends on runtime data"
                ),
                components=injection_components,
            )
        factory_locator = _symbol_locator(factory_reference, modules)
        factory_node = _symbol_node(factory_reference, modules)
        components = list(injection_components)
        if factory_node is not None:
            owner_module, node = factory_node
            components.append(_component(owner_module, node, factory_reference.symbol))
        return ProviderResolution(
            classification="RESOLVED_RUNTIME_FACTORY_IDENTITY",
            binding_kind="STATIC_RUNTIME_FACTORY",
            injection_locators=injection_locators,
            provider_locator=factory_locator,
            provider_target_locator=None,
            provider_target_reference=None,
            runtime_data_effect="YES",
            reason=(
                f"{authority_parameter} is created by one statically identified "
                "runtime factory; only the factory identity is source-resolved"
            ),
            components=tuple(components),
        )

    provider_reference = _reference_from_expression(
        expression,
        composition,
        candidate.owner,
    )
    if provider_reference is None:
        return ProviderResolution(
            classification="REMAINS_RUNTIME_DATA_DEPENDENT",
            binding_kind="RUNTIME_PROVIDER_EXPRESSION",
            injection_locators=injection_locators,
            provider_locator=None,
            provider_target_locator=None,
            provider_target_reference=None,
            runtime_data_effect="YES",
            reason=(
                f"{authority_parameter} is selected by a runtime expression rather "
                "than one static callable reference"
            ),
            components=injection_components,
        )

    provider_locator = _symbol_locator(provider_reference, modules)
    components = list(injection_components)
    provider_node = _symbol_node(provider_reference, modules)
    target_reference: SymbolReference | None = None
    if provider_node is not None:
        provider_module, node = provider_node
        components.append(_component(provider_module, node, provider_reference.symbol))
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            target_reference, target_is_dynamic = _provider_target(provider_module, node)
            if target_is_dynamic:
                return ProviderResolution(
                    classification="REMAINS_RUNTIME_DATA_DEPENDENT",
                    binding_kind="STATIC_PROVIDER_WITH_DYNAMIC_TARGET",
                    injection_locators=injection_locators,
                    provider_locator=provider_locator,
                    provider_target_locator=None,
                    provider_target_reference=None,
                    runtime_data_effect="YES",
                    reason=(
                        f"the injected {provider_reference.symbol} provider is static, "
                        "but its returned implementation target is runtime-dependent"
                    ),
                    components=tuple(components),
                )
    if target_reference is None:
        target_reference = provider_reference
    target_locator = _symbol_locator(target_reference, modules)
    target_node = _symbol_node(target_reference, modules)
    if target_node is not None and target_reference != provider_reference:
        target_module, node = target_node
        components.append(_component(target_module, node, target_reference.symbol))
    return ProviderResolution(
        classification="RESOLVED_STATIC_IMPLEMENTATION",
        binding_kind="DIRECT_STATIC_PROVIDER",
        injection_locators=injection_locators,
        provider_locator=provider_locator,
        provider_target_locator=target_locator,
        provider_target_reference=target_reference,
        runtime_data_effect="NO",
        reason=(
            f"{authority_parameter} is bound to one named callable and that provider "
            "returns one statically named implementation target"
        ),
        components=tuple(components),
    )


def _compare_static_string(
    expression: ast.expr,
    module: SourceModule,
) -> str | None:
    if not (
        isinstance(expression, ast.Compare)
        and len(expression.ops) == 1
        and isinstance(expression.ops[0], ast.Eq)
        and len(expression.comparators) == 1
    ):
        return None
    return _static_string(expression.comparators[0], module)


def resolve_static_dispatch_callable(
    module: SourceModule,
    target_symbol: str,
    static_dispatch_value: str,
) -> SymbolReference | None:
    """Resolve a fixed string dispatch branch to its local implementation callable."""

    target = module.functions.get(target_symbol)
    if target is None:
        return None
    for node in ast.walk(target):
        if not isinstance(node, ast.If):
            continue
        if _compare_static_string(node.test, module) != static_dispatch_value:
            continue
        local_calls = {
            child.func.id
            for statement in node.body
            for child in ast.walk(statement)
            if isinstance(child, ast.Call)
            and isinstance(child.func, ast.Name)
            and child.func.id in module.functions
        }
        if len(local_calls) == 1:
            return SymbolReference(module.module_name, next(iter(local_calls)))
        return None
    return None


def _load_module(source_root: Path, module_name: str, relative_path: Path) -> SourceModule:
    if relative_path.is_absolute():
        raise ValueError("source paths must be repository-relative")
    root = source_root.resolve()
    path = (root / relative_path).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"source path escapes source root: {relative_path}") from exc
    return parse_source_module(
        module_name,
        relative_path.as_posix(),
        path.read_text(encoding="utf-8"),
    )


def _as_object(value: object, *, locator: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise StaticBindingResolutionError(f"{locator} must be a string-keyed object")
    object_mapping = cast(dict[object, object], value)
    if not all(isinstance(key, str) for key in object_mapping):
        raise StaticBindingResolutionError(f"{locator} must be a string-keyed object")
    return cast(dict[str, object], object_mapping)


def _as_array(value: object, *, locator: str) -> list[object]:
    if not isinstance(value, list):
        raise StaticBindingResolutionError(f"{locator} must be an array")
    return cast(list[object], value)


def _as_string(value: object, *, locator: str) -> str:
    if not isinstance(value, str):
        raise StaticBindingResolutionError(f"{locator} must be a string")
    return value


def _original_rows(
    original_bytes: bytes,
) -> tuple[str, dict[str, dict[str, object]]]:
    raw = cast(object, json.loads(original_bytes))
    payload = _as_object(raw, locator="original result")
    study_id = _as_string(payload.get("study_id"), locator="original study_id")
    if study_id != ORIGINAL_STUDY_ID:
        raise StaticBindingResolutionError(
            f"unexpected original study_id: {study_id}"
        )
    records = _as_array(payload.get("records"), locator="original records")
    by_id: dict[str, dict[str, object]] = {}
    for index, item in enumerate(records):
        record = _as_object(item, locator=f"original records[{index}]")
        strategy_id = record.get("strategy_id")
        if isinstance(strategy_id, str) and strategy_id in TARGET_STRATEGY_IDS:
            if strategy_id in by_id:
                raise StaticBindingResolutionError(
                    f"duplicate original target row: {strategy_id}"
                )
            by_id[strategy_id] = record
    missing = sorted(set(TARGET_STRATEGY_IDS) - by_id.keys())
    if missing:
        raise StaticBindingResolutionError(
            "original result is missing target rows: " + ", ".join(missing)
        )
    for strategy_id, record in by_id.items():
        classification = record.get("classification")
        reason = record.get("unresolved_reason")
        if classification != "DYNAMIC_OR_UNRESOLVED" or reason != (
            f"CONSTRUCTOR_REQUIRES_RUNTIME_ARGUMENTS:{AUTHORITY_PARAMETER}"
        ):
            raise StaticBindingResolutionError(
                f"{strategy_id}: original result no longer has the expected unresolved state"
            )
    return study_id, by_id


def _record_reason(
    adapter: AdapterBinding,
    provider: ProviderResolution,
    selected_callable_locator: str | None,
) -> str:
    if provider.classification != "RESOLVED_STATIC_IMPLEMENTATION":
        return provider.reason
    if selected_callable_locator is None:
        return (
            f"{provider.reason}; the Wave 26 implementation branch for "
            f"{adapter.legacy_method_id} could not be selected statically"
        )
    return (
        "The descriptor names one concrete adapter class; its inherited constructor "
        f"requires {AUTHORITY_PARAMETER}:{adapter.authority_type_name}; the canonical "
        f"instantiator injects the single named provider {provider.provider_locator}; "
        f"the adapter's static legacy_method_id={adapter.legacy_method_id!r} selects "
        f"{selected_callable_locator}. Runtime request/history contents affect computed "
        "tickets, not the selected class/provider/callable identity."
    )


def analyze_source_tree(source_root: Path) -> dict[str, JSONValue]:
    """Build the deterministic supplemental result from exact source files."""

    catalog = _load_module(
        source_root,
        "lottolab.strategies.catalog",
        CATALOG_PATH,
    )
    registry = _load_module(
        source_root,
        "lottolab.strategies.executable_registry",
        REGISTRY_PATH,
    )
    adapter_module = _load_module(
        source_root,
        "lottolab.strategies.adapters.biglotto_wave8",
        ADAPTER_PATH,
    )
    composition = _load_module(
        source_root,
        "lottolab.application.use_cases.generate_bet",
        COMPOSITION_PATH,
    )
    implementation = _load_module(
        source_root,
        "lottolab.application.legacy_source_native_portfolios_wave26",
        WAVE26_IMPLEMENTATION_PATH,
    )
    original_path = source_root.resolve() / ORIGINAL_RESULT_PATH
    original_bytes = original_path.read_bytes()
    original_sha256 = _sha256(original_bytes)
    original_study_id, original_rows = _original_rows(original_bytes)

    descriptors = parse_target_descriptors(catalog)
    registry_component = resolve_registry_loader(registry)
    provider = resolve_injected_provider_source(
        composition.source,
        module_name=composition.module_name,
        relative_path=composition.relative_path,
        provider_modules={implementation.module_name: implementation},
    )
    if provider.classification != "RESOLVED_STATIC_IMPLEMENTATION":
        raise StaticBindingResolutionError(
            "the live Wave 26 provider is not a single static implementation: "
            f"{provider.reason}"
        )

    records: list[JSONValue] = []
    for strategy_id in sorted(TARGET_STRATEGY_IDS):
        descriptor = descriptors[strategy_id]
        adapter = resolve_adapter_binding(descriptor, adapter_module)
        selected_reference: SymbolReference | None = None
        if provider.provider_target_reference is not None:
            target_module = (
                implementation
                if provider.provider_target_reference.module_name
                == implementation.module_name
                else None
            )
            if target_module is not None:
                selected_reference = resolve_static_dispatch_callable(
                    target_module,
                    provider.provider_target_reference.symbol,
                    adapter.legacy_method_id,
                )

        final_classification: ResolutionClassification
        runtime_data_effect: RuntimeDataEffect
        selected_locator: str | None
        selected_component: SourceComponent | None = None
        if selected_reference is None:
            final_classification = "REMAINS_RUNTIME_DATA_DEPENDENT"
            runtime_data_effect = "YES"
            selected_locator = None
        else:
            final_classification = provider.classification
            runtime_data_effect = "NO"
            selected_locator = _symbol_locator(
                selected_reference,
                {implementation.module_name: implementation},
            )
            selected_node = _symbol_node(
                selected_reference,
                {implementation.module_name: implementation},
            )
            if selected_node is None:
                raise StaticBindingResolutionError(
                    f"{strategy_id}: selected Wave 26 callable source is absent"
                )
            selected_module, node = selected_node
            selected_component = _component(
                selected_module,
                node,
                selected_reference.symbol,
            )

        components = [
            _component(
                catalog,
                descriptor.node,
                f"StrategyDescriptor[{strategy_id}]",
            ),
            registry_component,
            *adapter.components,
            *provider.components,
        ]
        if selected_component is not None:
            components.append(selected_component)
        components.sort(key=lambda item: item.locator)
        component_payload: list[JSONValue] = [item.as_json() for item in components]
        structural_payload: dict[str, JSONValue] = {
            "components": component_payload,
            "provider_binding_kind": provider.binding_kind,
            "registry_adapter": descriptor.adapter_path,
            "static_binding_parameters": {
                "legacy_method_id": adapter.legacy_method_id,
            },
        }
        structural_digest = (
            _stable_digest(structural_payload)
            if final_classification
            in {
                "RESOLVED_STATIC_IMPLEMENTATION",
                "RESOLVED_RUNTIME_FACTORY_IDENTITY",
            }
            else None
        )
        fingerprint = (
            _stable_digest(
                {
                    "classification": final_classification,
                    "original_result_sha256": original_sha256,
                    "schema_version": SCHEMA_VERSION,
                    "strategy_id": strategy_id,
                    "structural_source_digest_sha256": structural_digest,
                }
            )
            if structural_digest is not None
            else None
        )
        original = original_rows[strategy_id]
        source_provider_lineage: list[JSONValue] = [
            descriptor.locator,
            registry_component.locator,
            adapter.adapter_class_locator,
            adapter.constructor_locator,
            adapter.authority_type_locator,
            *provider.injection_locators,
        ]
        if provider.provider_locator is not None:
            source_provider_lineage.append(provider.provider_locator)
        if provider.provider_target_locator is not None:
            source_provider_lineage.append(provider.provider_target_locator)
        if selected_locator is not None:
            source_provider_lineage.append(selected_locator)

        record: dict[str, JSONValue] = {
            "descriptor_locator": descriptor.locator,
            "exact_reason": _record_reason(adapter, provider, selected_locator),
            "factory_provider_locator": provider.provider_locator,
            "final_resolution_classification": final_classification,
            "implementation_class_callable": {
                "adapter_class_locator": adapter.adapter_class_locator,
                "authority_provider_callable_locator": provider.provider_locator,
                "execution_callable_locator": adapter.execution_callable_locator,
                "provider_target_callable_locator": provider.provider_target_locator,
                "statically_selected_wave26_callable_locator": selected_locator,
            },
            "injected_authority": {
                "constructor_locator": adapter.constructor_locator,
                "parameter": AUTHORITY_PARAMETER,
                "type_expression": adapter.authority_type_expression,
                "type_interface": adapter.authority_type_name,
                "type_locator": adapter.authority_type_locator,
            },
            "original_resolution": {
                "binding_group_id": cast(str, original["binding_group_id"]),
                "classification": cast(str, original["classification"]),
                "unresolved_reason": cast(str, original["unresolved_reason"]),
            },
            "registry_adapter": descriptor.adapter_path,
            "runtime_data_contents_affect_implementation_identity": runtime_data_effect,
            "source_provider_lineage": source_provider_lineage,
            "static_binding_parameters": {
                "legacy_method_id": adapter.legacy_method_id,
            },
            "strategy_id": strategy_id,
            "structural_source_components": component_payload,
            "structural_source_digest_scope": (
                "NORMALIZED_AST_OF_DESCRIPTOR_REGISTRY_ADAPTER_CONSTRUCTOR_HOOK_"
                "AUTHORITY_INJECTION_PROVIDER_TARGET_AND_STATICALLY_SELECTED_WAVE26_CALLABLE"
            ),
            "structural_source_digest_sha256": structural_digest,
            "supplemental_binding_fingerprint_sha256": fingerprint,
        }
        records.append(record)

    resolved_fingerprints: list[JSONValue] = [
        {
            "strategy_id": cast(dict[str, JSONValue], item)["strategy_id"],
            "supplemental_binding_fingerprint_sha256": cast(
                dict[str, JSONValue], item
            )["supplemental_binding_fingerprint_sha256"],
        }
        for item in records
    ]
    supplemental_fingerprint = _stable_digest(
        {
            "original_result_sha256": original_sha256,
            "record_fingerprints": resolved_fingerprints,
            "schema_version": SCHEMA_VERSION,
        }
    )
    classification_counts = Counter(
        cast(str, cast(dict[str, JSONValue], item)["final_resolution_classification"])
        for item in records
    )
    return {
        "classification_contract": {
            "allowed_values": list(ALLOWED_CLASSIFICATIONS),
            "resolution_boundary": (
                "Structural source/provider identity only; runtime outputs, historical "
                "behavior, statistical independence, and semantic equivalence are outside scope."
            ),
            "unresolved_policy": (
                "Runtime-selected or multiply bound providers fail open and are never guessed."
            ),
        },
        "original_lineage_result": {
            "path": ORIGINAL_RESULT_PATH.as_posix(),
            "sha256": original_sha256,
            "study_id": original_study_id,
        },
        "records": records,
        "schema_version": SCHEMA_VERSION,
        "scope": {
            "database_access": "NO",
            "database_write": "NO",
            "executable_registry_locator": registry_component.locator,
            "historical_replay": "NOT_RUN",
            "method": "STATIC_SOURCE_AST_ONLY",
            "original_result_rewritten": "NO",
            "production_runtime_start": "NOT_RUN",
            "semantic_equivalence": "NOT_CLAIMED",
            "target_strategy_ids": list(TARGET_STRATEGY_IDS),
        },
        "study_id": STUDY_ID,
        "summary": {
            "classification_counts": {
                classification: classification_counts.get(classification, 0)
                for classification in ALLOWED_CLASSIFICATIONS
            },
            "resolved_strategy_id_count": sum(
                classification_counts.get(classification, 0)
                for classification in (
                    "RESOLVED_STATIC_IMPLEMENTATION",
                    "RESOLVED_RUNTIME_FACTORY_IDENTITY",
                )
            ),
            "target_strategy_id_count": len(TARGET_STRATEGY_IDS),
        },
        "supplemental_binding_fingerprint_sha256": supplemental_fingerprint,
    }


def _record_objects(result: Mapping[str, JSONValue]) -> list[dict[str, JSONValue]]:
    records = result.get("records")
    if not isinstance(records, list):
        raise TypeError("records must be an array")
    objects: list[dict[str, JSONValue]] = []
    for index, item in enumerate(records):
        if not isinstance(item, dict):
            raise TypeError(f"records[{index}] must be an object")
        objects.append(item)
    return objects


def _json_string(value: JSONValue, *, locator: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{locator} must be a string")
    return value


def _json_object(value: JSONValue, *, locator: str) -> dict[str, JSONValue]:
    if not isinstance(value, dict):
        raise TypeError(f"{locator} must be an object")
    return value


def render_markdown(result: dict[str, JSONValue], result_sha256: str) -> str:
    """Render the human-readable supplemental resolution report."""

    original = _json_object(
        result["original_lineage_result"],
        locator="original_lineage_result",
    )
    fingerprint = _json_string(
        result["supplemental_binding_fingerprint_sha256"],
        locator="supplemental_binding_fingerprint_sha256",
    )
    lines = [
        "# Wave 26 dynamic binding resolution R1",
        "",
        "## Scope and historical reference",
        "",
        (
            "This is a deterministic, DB-free supplemental source analysis. It preserves "
            "the original lineage result as historical evidence and follows only the four "
            "previously unresolved `wave26_authority` bindings through the canonical "
            "composition root."
        ),
        "",
        f"- Original result: `{_json_string(original['path'], locator='original path')}`",
        f"- Original result SHA-256: `{_json_string(original['sha256'], locator='original sha')}`",
        f"- Supplemental result SHA-256: `{result_sha256}`",
        f"- Supplemental binding fingerprint SHA-256: `{fingerprint}`",
        "- Method: Python AST/static source declarations only; LottoLab modules are not imported",
        "- Original lineage result rewritten: `NO`",
        "",
        "## Four-row resolution",
        "",
        (
            "| Strategy ID | Descriptor locator | Registry adapter | Implementation "
            "callable | Injected authority | Factory/provider locator | Runtime data "
            "changes identity? | Structural source digest | Final classification |"
        ),
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for record in _record_objects(result):
        implementation = _json_object(
            record["implementation_class_callable"],
            locator="implementation_class_callable",
        )
        authority = _json_object(
            record["injected_authority"],
            locator="injected_authority",
        )
        selected = _json_string(
            implementation["statically_selected_wave26_callable_locator"],
            locator="selected callable",
        )
        runtime_effect = _json_string(
            record["runtime_data_contents_affect_implementation_identity"],
            locator="runtime effect",
        )
        source_digest = _json_string(
            record["structural_source_digest_sha256"],
            locator="source digest",
        )
        classification = _json_string(
            record["final_resolution_classification"],
            locator="classification",
        )
        lines.append(
            "| "
            f"`{_json_string(record['strategy_id'], locator='strategy_id')}` | "
            f"`{_json_string(record['descriptor_locator'], locator='descriptor_locator')}` | "
            f"`{_json_string(record['registry_adapter'], locator='registry_adapter')}` | "
            f"`{selected}` | "
            f"`{_json_string(authority['type_interface'], locator='authority type')}` | "
            f"`{_json_string(record['factory_provider_locator'], locator='provider')}` | "
            f"`{runtime_effect}` | "
            f"`{source_digest}` | "
            f"`{classification}` |"
        )

    lines.extend(
        [
            "",
            "## Source/provider lineage and exact reasons",
            "",
        ]
    )
    for record in _record_objects(result):
        strategy_id = _json_string(record["strategy_id"], locator="strategy_id")
        lineage = record["source_provider_lineage"]
        if not isinstance(lineage, list) or not all(isinstance(item, str) for item in lineage):
            raise TypeError(f"{strategy_id}: source_provider_lineage must be strings")
        lines.extend(
            [
                f"### `{strategy_id}`",
                "",
                "`" + "` → `".join(cast(list[str], lineage)) + "`",
                "",
                _json_string(record["exact_reason"], locator="exact_reason"),
                "",
                (
                    "Supplemental binding fingerprint: `"
                    + _json_string(
                        record["supplemental_binding_fingerprint_sha256"],
                        locator="record fingerprint",
                    )
                    + "`"
                ),
                "",
            ]
        )

    lines.extend(
        [
            "## Scientific and runtime boundary",
            "",
            "- `DB_ACCESS = NO`",
            "- `DB_WRITE = NO`",
            "- `HISTORICAL_REPLAY = NOT RUN`",
            "- `PRODUCTION_RUNTIME_START = NOT RUN`",
            "- `SEMANTIC_EQUIVALENCE = NOT CLAIMED`",
            "",
            (
                "The static `legacy_method_id` values resolve which Wave 26 row callable "
                "is selected. History and target-draw contents still affect computed "
                "tickets; this supplement establishes structural implementation identity "
                "only."
            ),
            "",
        ]
    )
    return "\n".join(lines)


def write_artifacts(
    source_root: Path,
    *,
    output_path: Path = OUTPUT_PATH,
    report_path: Path = REPORT_PATH,
) -> tuple[str, str, str]:
    """Write the artifacts and return result, report, and binding digests."""

    result = analyze_source_tree(source_root)
    result_bytes = canonical_json_bytes(result)
    result_sha256 = _sha256(result_bytes)
    report = render_markdown(result, result_sha256)
    absolute_output = source_root / output_path
    absolute_report = source_root / report_path
    absolute_output.write_bytes(result_bytes)
    absolute_report.write_text(report, encoding="utf-8")
    fingerprint = _json_string(
        result["supplemental_binding_fingerprint_sha256"],
        locator="supplemental binding fingerprint",
    )
    return result_sha256, _sha256(report.encode("utf-8")), fingerprint


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Resolve Wave 26 injected bindings using source ASTs only."
    )
    parser.add_argument(
        "--source-root",
        type=Path,
        default=Path.cwd(),
        help="Repository source root (default: current directory).",
    )
    args = parser.parse_args()
    result_sha256, report_sha256, fingerprint = write_artifacts(
        args.source_root.resolve()
    )
    print(f"result_sha256={result_sha256}")
    print(f"report_sha256={report_sha256}")
    print(f"supplemental_binding_fingerprint_sha256={fingerprint}")


if __name__ == "__main__":
    main()
