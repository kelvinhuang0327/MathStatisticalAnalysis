"""Build the deterministic, DB-free strategy binding lineage map.

The analyzer deliberately parses source with :mod:`ast`; it never imports a
LottoLab module or instantiates an adapter.  Classification is structural:
normalized hook source identifies one callable family inside one source
module, while the catalog contract and statically declared class/constructor
bindings identify a concrete binding.  No historical behavior or semantic
equivalence is inferred.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

type JSONValue = (
    None | bool | int | str | Sequence[JSONValue] | Mapping[str, JSONValue]
)
type Classification = Literal[
    "IDENTICAL_BINDING",
    "SAME_CALLABLE_DIFFERENT_BINDING",
    "DISTINCT_BINDING",
    "DYNAMIC_OR_UNRESOLVED",
]
type ClassReference = tuple[str, str]

STUDY_ID = "STRATEGY_MATRIX_STATIC_LINEAGE_REDUNDANCY_MAP_R1"
SCHEMA_VERSION = "strategy-matrix-static-lineage-redundancy-map/v1"
CATALOG_RELATIVE_PATH = Path("src/lottolab/strategies/catalog.py")
EXECUTABLE_REGISTRY_LOCATOR = (
    "src/lottolab/strategies/executable_registry.py:ExecutableRegistry"
)
OUTPUT_PATH = Path(
    "docs/research/matrix-native-results/"
    "strategy-matrix-static-lineage-redundancy-map-r1-result.json"
)
REPORT_PATH = Path("docs/research/strategy-matrix-static-lineage-redundancy-map-r1.md")

CLASSIFICATIONS: tuple[Classification, ...] = (
    "IDENTICAL_BINDING",
    "SAME_CALLABLE_DIFFERENT_BINDING",
    "DISTINCT_BINDING",
    "DYNAMIC_OR_UNRESOLVED",
)
LOTTERY_TO_GAME = {
    "BIG_LOTTO": "B649",
    "DAILY_539": "T539",
    "POWER_LOTTO": "P638",
}
GAME_ORDER = ("B649", "T539", "P638")
HOOK_NAMES = frozenset({"_predict", "_predict_all"})
NON_BINDING_CLASS_ATTRIBUTES = frozenset(
    {
        "strategy_id",
        "strategy_name",
        "strategy_version",
    }
)
DYNAMIC_EXPRESSION_NODES = (
    ast.Await,
    ast.Call,
    ast.DictComp,
    ast.GeneratorExp,
    ast.Lambda,
    ast.ListComp,
    ast.NamedExpr,
    ast.SetComp,
    ast.Yield,
    ast.YieldFrom,
)


class StaticCatalogError(ValueError):
    """The canonical strategy universe could not be read fail-closed."""


class DuplicateStrategyIdError(StaticCatalogError):
    """The static canonical catalog declared one Strategy ID more than once."""


@dataclass(frozen=True, slots=True)
class CatalogEntry:
    strategy_id: str
    lottery_types: tuple[str, ...]
    adapter_path: str | None
    min_history: int
    response_shape: str
    native_ticket_minimum: int
    native_ticket_maximum: int
    catalog_locator: str
    catalog_unresolved_reason: str | None


@dataclass(frozen=True, slots=True)
class ModuleInfo:
    module_name: str
    relative_path: str
    tree: ast.Module
    classes: dict[str, ast.ClassDef]
    functions: dict[str, ast.FunctionDef | ast.AsyncFunctionDef]
    assignments: dict[str, ast.expr]
    imported_symbols: dict[str, ClassReference]
    imported_modules: dict[str, str]
    duplicate_symbols: frozenset[str]


@dataclass(frozen=True, slots=True)
class ClassNode:
    module: ModuleInfo
    definition: ast.ClassDef


@dataclass(frozen=True, slots=True)
class ResolvedBinding:
    entry: CatalogEntry
    adapter_module: str
    adapter_class_symbol: str
    implementation_module: str
    implementation_path: str
    implementation_owner_symbol: str
    callable_symbol: str
    implementation_source_digest: str
    callable_family_id: str
    static_binding_parameters: dict[str, JSONValue]
    binding_fingerprint: str
    binding_group_id: str


@dataclass(frozen=True, slots=True)
class UnresolvedBinding:
    entry: CatalogEntry
    reason: str
    adapter_module: str | None
    adapter_class_symbol: str | None
    implementation_path: str | None


class SourceIndex:
    """Parsed source modules keyed by their import identity."""

    def __init__(
        self,
        module_sources: Mapping[str, str],
        module_paths: Mapping[str, str] | None = None,
    ) -> None:
        paths = {} if module_paths is None else dict(module_paths)
        self._modules: dict[str, ModuleInfo] = {}
        for module_name in sorted(module_sources):
            relative_path = paths.get(
                module_name,
                f"src/{module_name.replace('.', '/')}.py",
            )
            if Path(relative_path).is_absolute():
                raise ValueError(f"module path must be repository-relative: {relative_path}")
            self._modules[module_name] = _parse_module(
                module_name,
                relative_path,
                module_sources[module_name],
            )

    def module(self, module_name: str) -> ModuleInfo | None:
        return self._modules.get(module_name)

    def class_node(self, reference: ClassReference) -> ClassNode | None:
        module = self.module(reference[0])
        if module is None or reference[1] in module.duplicate_symbols:
            return None
        definition = module.classes.get(reference[1])
        if definition is None:
            return None
        return ClassNode(module=module, definition=definition)

    def resolve_base(
        self,
        owner: ModuleInfo,
        expression: ast.expr,
    ) -> ClassReference | None:
        if isinstance(expression, ast.Name):
            if expression.id in owner.classes:
                return owner.module_name, expression.id
            return owner.imported_symbols.get(expression.id)
        if (
            isinstance(expression, ast.Attribute)
            and isinstance(expression.value, ast.Name)
            and expression.value.id in owner.imported_modules
        ):
            return owner.imported_modules[expression.value.id], expression.attr
        return None


def canonical_json_bytes(payload: JSONValue) -> bytes:
    """Return stable UTF-8 JSON with a terminal newline."""

    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ).rstrip("\n")
    return f"{serialized}\n".encode()


def _compact_canonical_bytes(payload: JSONValue) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _stable_digest(payload: JSONValue) -> str:
    return _sha256(_compact_canonical_bytes(payload))


def normalized_ast_digest(source: str) -> str:
    """Hash Python structure while ignoring formatting and comments."""

    tree = ast.parse(source)
    return _node_digest(tree)


def _node_digest(node: ast.AST) -> str:
    normalized = ast.dump(node, annotate_fields=True, include_attributes=False)
    return _sha256(normalized.encode())


def relative_source_path(source_root: Path, source_path: Path) -> str:
    """Return a portable source locator and reject paths outside the source root."""

    root = source_root.resolve()
    resolved = source_path.resolve()
    try:
        relative = resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"source path is outside source root: {source_path}") from exc
    return relative.as_posix()


def _target_names(node: ast.Assign | ast.AnnAssign) -> tuple[str, ...]:
    targets: Sequence[ast.expr]
    targets = node.targets if isinstance(node, ast.Assign) else (node.target,)
    return tuple(target.id for target in targets if isinstance(target, ast.Name))


def _resolve_import_module(current_module: str, imported: str | None, level: int) -> str:
    if level == 0:
        if imported is None:
            raise StaticCatalogError("absolute import is missing a module")
        return imported
    package_parts = current_module.split(".")[:-1]
    keep = len(package_parts) - level + 1
    if keep < 0:
        raise StaticCatalogError(f"invalid relative import in {current_module}")
    suffix = [] if imported is None else imported.split(".")
    return ".".join(package_parts[:keep] + suffix)


def _parse_module(module_name: str, relative_path: str, source: str) -> ModuleInfo:
    tree = ast.parse(source, filename=relative_path)
    classes: dict[str, ast.ClassDef] = {}
    functions: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = {}
    assignments: dict[str, ast.expr] = {}
    imported_symbols: dict[str, ClassReference] = {}
    imported_modules: dict[str, str] = {}
    bound_names: Counter[str] = Counter()

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            bound_names[node.name] += 1
            classes[node.name] = node
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            bound_names[node.name] += 1
            functions[node.name] = node
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            value = node.value
            for name in _target_names(node):
                bound_names[name] += 1
                if value is not None:
                    assignments[name] = value
        elif isinstance(node, ast.ImportFrom):
            imported_module = _resolve_import_module(module_name, node.module, node.level)
            for alias in node.names:
                local_name = alias.asname or alias.name
                bound_names[local_name] += 1
                imported_symbols[local_name] = (imported_module, alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                local_name = alias.asname or alias.name.split(".", 1)[0]
                bound_names[local_name] += 1
                imported_modules[local_name] = alias.name

    return ModuleInfo(
        module_name=module_name,
        relative_path=relative_path,
        tree=tree,
        classes=classes,
        functions=functions,
        assignments=assignments,
        imported_symbols=imported_symbols,
        imported_modules=imported_modules,
        duplicate_symbols=frozenset(name for name, count in bound_names.items() if count > 1),
    )


def _keyword_map(call: ast.Call) -> dict[str, ast.expr]:
    result: dict[str, ast.expr] = {}
    for keyword in call.keywords:
        if keyword.arg is None:
            raise StaticCatalogError("StrategyDescriptor may not use **kwargs")
        if keyword.arg in result:
            raise StaticCatalogError(f"duplicate descriptor keyword: {keyword.arg}")
        result[keyword.arg] = keyword.value
    return result


def _static_string(node: ast.expr) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _static_string(node.left)
        right = _static_string(node.right)
        return None if left is None or right is None else left + right
    return None


def _required_string(keywords: Mapping[str, ast.expr], name: str) -> str:
    node = keywords.get(name)
    value = None if node is None else _static_string(node)
    if value is None:
        raise StaticCatalogError(f"{name} must be a static string")
    return value


def _required_bool(keywords: Mapping[str, ast.expr], name: str) -> bool:
    node = keywords.get(name)
    if isinstance(node, ast.Constant) and isinstance(node.value, bool):
        return node.value
    raise StaticCatalogError(f"{name} must be a static bool")


def _static_int(node: ast.expr | None, *, default: int | None = None) -> int:
    if node is None and default is not None:
        return default
    if isinstance(node, ast.Constant) and type(node.value) is int:
        return node.value
    raise StaticCatalogError("ticket cardinality and min_history must be static integers")


def _optional_static_int(node: ast.expr | None) -> int | None:
    if node is None or (isinstance(node, ast.Constant) and node.value is None):
        return None
    return _static_int(node)


def _enum_member(node: ast.expr, *, field: str) -> str:
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
        return node.attr
    raise StaticCatalogError(f"{field} must contain static enum members")


def _lottery_types(node: ast.expr | None) -> tuple[str, ...]:
    if not isinstance(node, ast.Tuple) or not node.elts:
        raise StaticCatalogError("lottery_types must be a non-empty static tuple")
    return tuple(_enum_member(item, field="lottery_types") for item in node.elts)


def _response_shape(node: ast.expr | None) -> str:
    if node is None:
        return "SINGLE_TICKET"
    return _enum_member(node, field="response_shape")


def _production_descriptor_tuple(tree: ast.Module) -> ast.Tuple:
    matches: list[ast.expr] = []
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if any(
            isinstance(target, ast.Name) and target.id == "_PRODUCTION_DESCRIPTORS"
            for target in node.targets
        ):
            matches.append(node.value)
    if len(matches) != 1 or not isinstance(matches[0], ast.Tuple):
        raise StaticCatalogError(
            "canonical _PRODUCTION_DESCRIPTORS must be one literal tuple"
        )
    return matches[0]


def parse_catalog_source(
    catalog_source: str,
    *,
    catalog_relative_path: str = CATALOG_RELATIVE_PATH.as_posix(),
) -> tuple[CatalogEntry, ...]:
    """Read the canonical executable universe without importing the catalog."""

    if Path(catalog_relative_path).is_absolute():
        raise ValueError("catalog path must be repository-relative")
    tree = ast.parse(catalog_source, filename=catalog_relative_path)
    descriptors = _production_descriptor_tuple(tree)
    rows: list[CatalogEntry] = []
    all_ids: list[str] = []

    for node in descriptors.elts:
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "StrategyDescriptor"
        ):
            raise StaticCatalogError(
                "_PRODUCTION_DESCRIPTORS contains a non-StrategyDescriptor expression"
            )
        keywords = _keyword_map(node)
        strategy_id = _required_string(keywords, "strategy_id")
        all_ids.append(strategy_id)
        executable = _required_bool(keywords, "executable")
        if not executable:
            continue

        adapter_node = keywords.get("adapter_path")
        adapter_path = None if adapter_node is None else _static_string(adapter_node)
        unresolved_reason: str | None = None
        if adapter_path is None:
            unresolved_reason = "NON_LITERAL_ADAPTER_PATH"
        elif adapter_path.count(":") != 1 or not all(adapter_path.split(":")):
            unresolved_reason = "MALFORMED_ADAPTER_PATH"

        native_maximum = _static_int(keywords.get("native_ticket_count"), default=1)
        native_minimum = _optional_static_int(keywords.get("minimum_native_ticket_count"))
        explicit_maximum = _optional_static_int(keywords.get("maximum_native_ticket_count"))
        rows.append(
            CatalogEntry(
                strategy_id=strategy_id,
                lottery_types=_lottery_types(keywords.get("lottery_types")),
                adapter_path=adapter_path,
                min_history=_static_int(keywords.get("min_history"), default=1),
                response_shape=_response_shape(keywords.get("response_shape")),
                native_ticket_minimum=(
                    native_maximum if native_minimum is None else native_minimum
                ),
                native_ticket_maximum=(
                    native_maximum if explicit_maximum is None else explicit_maximum
                ),
                catalog_locator=f"{catalog_relative_path}:{node.lineno}",
                catalog_unresolved_reason=unresolved_reason,
            )
        )

    duplicate_ids = sorted(
        strategy_id for strategy_id, count in Counter(all_ids).items() if count > 1
    )
    if duplicate_ids:
        raise DuplicateStrategyIdError(
            "DUPLICATE_STRATEGY_ID_AUTHORITY: " + ", ".join(duplicate_ids)
        )
    return tuple(rows)


def _class_assignments(class_node: ClassNode) -> dict[str, ast.expr]:
    assignments: dict[str, ast.expr] = {}
    for node in class_node.definition.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)) or node.value is None:
            continue
        for name in _target_names(node):
            assignments[name] = node.value
    return assignments


def _direct_methods(
    class_node: ClassNode,
    names: frozenset[str],
) -> tuple[ast.FunctionDef | ast.AsyncFunctionDef, ...]:
    return tuple(
        node
        for node in class_node.definition.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names
    )


def _self_attribute_reads(node: ast.AST) -> frozenset[str]:
    return frozenset(
        child.attr
        for child in ast.walk(node)
        if isinstance(child, ast.Attribute)
        and isinstance(child.ctx, ast.Load)
        and isinstance(child.value, ast.Name)
        and child.value.id in {"self", "cls"}
    )


def _expression_is_dynamic(
    module: ModuleInfo,
    expression: ast.expr,
    *,
    seen_constants: frozenset[str] = frozenset(),
) -> bool:
    if any(isinstance(node, DYNAMIC_EXPRESSION_NODES) for node in ast.walk(expression)):
        return True
    referenced_constants = {
        node.id
        for node in ast.walk(expression)
        if isinstance(node, ast.Name)
        and isinstance(node.ctx, ast.Load)
        and node.id in module.assignments
    }
    for name in sorted(referenced_constants - seen_constants):
        if _expression_is_dynamic(
            module,
            module.assignments[name],
            seen_constants=seen_constants | {name},
        ):
            return True
    return False


def _binding_expression(module: ModuleInfo, expression: ast.expr) -> dict[str, JSONValue]:
    return {
        "declared_in_module": module.module_name,
        "expression_ast": ast.dump(
            expression,
            annotate_fields=True,
            include_attributes=False,
        ),
    }


def _constructor_binding(
    lineage: Sequence[ClassNode],
) -> tuple[dict[str, JSONValue] | None, str | None]:
    constructor_owner: ClassNode | None = None
    constructor: ast.FunctionDef | ast.AsyncFunctionDef | None = None
    for class_node in lineage:
        matches = _direct_methods(class_node, frozenset({"__init__"}))
        if matches:
            if len(matches) != 1:
                return None, "AMBIGUOUS_CONSTRUCTOR_BINDING"
            constructor_owner = class_node
            constructor = matches[0]
            break

    if constructor_owner is None or constructor is None:
        return {"kind": "IMPLICIT_NO_ARGUMENT_CONSTRUCTOR"}, None

    positional = constructor.args.posonlyargs + constructor.args.args
    first_default = len(positional) - len(constructor.args.defaults)
    required_positional = [
        argument.arg
        for index, argument in enumerate(positional)
        if index > 0 and index < first_default
    ]
    required_keyword_only = [
        argument.arg
        for argument, default in zip(
            constructor.args.kwonlyargs,
            constructor.args.kw_defaults,
            strict=True,
        )
        if default is None
    ]
    required = required_positional + required_keyword_only
    if required:
        return None, "CONSTRUCTOR_REQUIRES_RUNTIME_ARGUMENTS:" + ",".join(required)

    defaults: dict[str, JSONValue] = {}
    default_names = positional[first_default:]
    for argument, default in zip(default_names, constructor.args.defaults, strict=True):
        if _expression_is_dynamic(constructor_owner.module, default):
            return None, f"DYNAMIC_CONSTRUCTOR_DEFAULT:{argument.arg}"
        defaults[argument.arg] = _binding_expression(constructor_owner.module, default)
    for argument, default in zip(
        constructor.args.kwonlyargs,
        constructor.args.kw_defaults,
        strict=True,
    ):
        if default is None:
            continue
        if _expression_is_dynamic(constructor_owner.module, default):
            return None, f"DYNAMIC_CONSTRUCTOR_DEFAULT:{argument.arg}"
        defaults[argument.arg] = _binding_expression(constructor_owner.module, default)

    return (
        {
            "defaults": defaults,
            "kind": "STATIC_NO_ARGUMENT_CONSTRUCTOR",
            "source_digest_sha256": _node_digest(constructor),
            "source_locator": (
                f"{constructor_owner.module.relative_path}:"
                f"{constructor_owner.definition.name}.__init__"
            ),
        },
        None,
    )


def _unresolved(
    entry: CatalogEntry,
    reason: str,
    *,
    adapter_module: str | None = None,
    adapter_class_symbol: str | None = None,
    implementation_path: str | None = None,
) -> UnresolvedBinding:
    return UnresolvedBinding(
        entry=entry,
        reason=reason,
        adapter_module=adapter_module,
        adapter_class_symbol=adapter_class_symbol,
        implementation_path=implementation_path,
    )


def _resolve_class_binding(
    entry: CatalogEntry,
    index: SourceIndex,
    adapter_module: str,
    adapter_symbol: str,
) -> ResolvedBinding | UnresolvedBinding:
    reference = (adapter_module, adapter_symbol)
    lineage: list[ClassNode] = []
    seen: set[ClassReference] = set()
    hook: ast.FunctionDef | ast.AsyncFunctionDef | None = None
    hook_owner: ClassNode | None = None

    while hook is None:
        if reference in seen:
            return _unresolved(
                entry,
                "CYCLIC_CLASS_LINEAGE",
                adapter_module=adapter_module,
                adapter_class_symbol=adapter_symbol,
            )
        seen.add(reference)
        class_node = index.class_node(reference)
        if class_node is None:
            return _unresolved(
                entry,
                f"CLASS_SYMBOL_NOT_UNIQUELY_RESOLVED:{reference[0]}:{reference[1]}",
                adapter_module=adapter_module,
                adapter_class_symbol=adapter_symbol,
            )
        if class_node.definition.decorator_list or class_node.definition.keywords:
            return _unresolved(
                entry,
                f"DYNAMIC_CLASS_DECORATION_OR_METACLASS:{reference[0]}:{reference[1]}",
                adapter_module=adapter_module,
                adapter_class_symbol=adapter_symbol,
                implementation_path=class_node.module.relative_path,
            )
        lineage.append(class_node)
        hooks = _direct_methods(class_node, HOOK_NAMES)
        if len(hooks) > 1:
            return _unresolved(
                entry,
                f"AMBIGUOUS_EXECUTION_HOOK:{reference[0]}:{reference[1]}",
                adapter_module=adapter_module,
                adapter_class_symbol=adapter_symbol,
                implementation_path=class_node.module.relative_path,
            )
        if hooks:
            hook = hooks[0]
            hook_owner = class_node
            break
        if len(class_node.definition.bases) != 1:
            return _unresolved(
                entry,
                f"EXECUTION_HOOK_NOT_STATICALLY_INHERITED:{reference[0]}:{reference[1]}",
                adapter_module=adapter_module,
                adapter_class_symbol=adapter_symbol,
                implementation_path=class_node.module.relative_path,
            )
        parent = index.resolve_base(class_node.module, class_node.definition.bases[0])
        if parent is None:
            return _unresolved(
                entry,
                f"DYNAMIC_BASE_CLASS:{reference[0]}:{reference[1]}",
                adapter_module=adapter_module,
                adapter_class_symbol=adapter_symbol,
                implementation_path=class_node.module.relative_path,
            )
        reference = parent

    if hook_owner is None:
        raise AssertionError("hook owner must be assigned with the resolved hook")
    if hook.decorator_list:
        return _unresolved(
            entry,
            "DYNAMIC_EXECUTION_HOOK_DECORATOR",
            adapter_module=adapter_module,
            adapter_class_symbol=adapter_symbol,
            implementation_path=hook_owner.module.relative_path,
        )

    base_chain: list[JSONValue] = []
    for class_node in lineage:
        if len(class_node.definition.bases) > 1:
            return _unresolved(
                entry,
                f"MULTIPLE_INHERITANCE_UNRESOLVED:{class_node.definition.name}",
                adapter_module=adapter_module,
                adapter_class_symbol=adapter_symbol,
                implementation_path=class_node.module.relative_path,
            )
        if not class_node.definition.bases:
            continue
        base = index.resolve_base(class_node.module, class_node.definition.bases[0])
        if base is None:
            return _unresolved(
                entry,
                f"DYNAMIC_BASE_CLASS:{class_node.definition.name}",
                adapter_module=adapter_module,
                adapter_class_symbol=adapter_symbol,
                implementation_path=class_node.module.relative_path,
            )
        base_chain.append({"module": base[0], "symbol": base[1]})

    referenced_attributes = _self_attribute_reads(hook) - NON_BINDING_CLASS_ATTRIBUTES
    effective_assignments: dict[str, tuple[ModuleInfo, ast.expr]] = {}
    for class_node in reversed(lineage):
        for name, expression in _class_assignments(class_node).items():
            if name in referenced_attributes:
                effective_assignments[name] = (class_node.module, expression)

    adapter_parameters: dict[str, JSONValue] = {}
    for name in sorted(effective_assignments):
        module, expression = effective_assignments[name]
        if _expression_is_dynamic(module, expression):
            return _unresolved(
                entry,
                f"DYNAMIC_CLASS_BINDING:{name}",
                adapter_module=adapter_module,
                adapter_class_symbol=adapter_symbol,
                implementation_path=hook_owner.module.relative_path,
            )
        adapter_parameters[name] = _binding_expression(module, expression)

    constructor, constructor_reason = _constructor_binding(lineage)
    if constructor is None:
        return _unresolved(
            entry,
            constructor_reason or "CONSTRUCTOR_BINDING_UNRESOLVED",
            adapter_module=adapter_module,
            adapter_class_symbol=adapter_symbol,
            implementation_path=hook_owner.module.relative_path,
        )

    source_digest = _node_digest(hook)
    callable_identity: dict[str, JSONValue] = {
        "implementation_module_path": hook_owner.module.relative_path,
        "normalized_callable_source_digest_sha256": source_digest,
    }
    callable_digest = _stable_digest(callable_identity)
    callable_family_id = f"callable-sha256:{callable_digest}"
    static_binding_parameters: dict[str, JSONValue] = {
        "adapter_class_parameters": adapter_parameters,
        "catalog_contract": {
            "lottery_types": list(entry.lottery_types),
            "min_history": entry.min_history,
            "native_ticket_cardinality": {
                "maximum": entry.native_ticket_maximum,
                "minimum": entry.native_ticket_minimum,
            },
            "response_shape": entry.response_shape,
        },
        "constructor": constructor,
        "execution_base_chain": base_chain,
    }
    binding_payload: dict[str, JSONValue] = {
        "callable_identity": callable_identity,
        "static_binding_parameters": static_binding_parameters,
    }
    binding_fingerprint = _stable_digest(binding_payload)
    return ResolvedBinding(
        entry=entry,
        adapter_module=adapter_module,
        adapter_class_symbol=adapter_symbol,
        implementation_module=hook_owner.module.module_name,
        implementation_path=hook_owner.module.relative_path,
        implementation_owner_symbol=hook_owner.definition.name,
        callable_symbol=hook.name,
        implementation_source_digest=source_digest,
        callable_family_id=callable_family_id,
        static_binding_parameters=static_binding_parameters,
        binding_fingerprint=binding_fingerprint,
        binding_group_id=f"binding-sha256:{binding_fingerprint}",
    )


def _resolve_entry(
    entry: CatalogEntry,
    index: SourceIndex,
) -> ResolvedBinding | UnresolvedBinding:
    if entry.catalog_unresolved_reason is not None or entry.adapter_path is None:
        return _unresolved(entry, entry.catalog_unresolved_reason or "ADAPTER_PATH_UNRESOLVED")
    adapter_module, adapter_symbol = entry.adapter_path.split(":", 1)
    module = index.module(adapter_module)
    if module is None:
        return _unresolved(
            entry,
            f"IMPLEMENTATION_MODULE_NOT_FOUND:{adapter_module}",
            adapter_module=adapter_module,
            adapter_class_symbol=adapter_symbol,
        )
    if adapter_symbol in module.duplicate_symbols:
        return _unresolved(
            entry,
            f"IMPLEMENTATION_SYMBOL_REBOUND:{adapter_module}:{adapter_symbol}",
            adapter_module=adapter_module,
            adapter_class_symbol=adapter_symbol,
            implementation_path=module.relative_path,
        )
    function = module.functions.get(adapter_symbol)
    if function is not None:
        if function.decorator_list:
            return _unresolved(
                entry,
                "DYNAMIC_FUNCTION_DECORATOR",
                adapter_module=adapter_module,
                adapter_class_symbol=adapter_symbol,
                implementation_path=module.relative_path,
            )
        source_digest = _node_digest(function)
        callable_identity: dict[str, JSONValue] = {
            "implementation_module_path": module.relative_path,
            "normalized_callable_source_digest_sha256": source_digest,
        }
        callable_digest = _stable_digest(callable_identity)
        static_binding_parameters: dict[str, JSONValue] = {
            "catalog_contract": {
                "lottery_types": list(entry.lottery_types),
                "min_history": entry.min_history,
                "native_ticket_cardinality": {
                    "maximum": entry.native_ticket_maximum,
                    "minimum": entry.native_ticket_minimum,
                },
                "response_shape": entry.response_shape,
            },
            "function_registry_binding": "DIRECT_SYMBOL_WITHOUT_BOUND_ARGUMENTS",
        }
        binding_payload: dict[str, JSONValue] = {
            "callable_identity": callable_identity,
            "static_binding_parameters": static_binding_parameters,
        }
        binding_fingerprint = _stable_digest(binding_payload)
        return ResolvedBinding(
            entry=entry,
            adapter_module=adapter_module,
            adapter_class_symbol=adapter_symbol,
            implementation_module=adapter_module,
            implementation_path=module.relative_path,
            implementation_owner_symbol=adapter_symbol,
            callable_symbol=adapter_symbol,
            implementation_source_digest=source_digest,
            callable_family_id=f"callable-sha256:{callable_digest}",
            static_binding_parameters=static_binding_parameters,
            binding_fingerprint=binding_fingerprint,
            binding_group_id=f"binding-sha256:{binding_fingerprint}",
        )
    return _resolve_class_binding(entry, index, adapter_module, adapter_symbol)


def _game_identities(lottery_types: Sequence[str]) -> list[str]:
    return sorted(LOTTERY_TO_GAME.get(value, value) for value in lottery_types)


def _record_json(
    binding: ResolvedBinding,
    *,
    classification: Classification,
    classification_group_id: str,
    exact_siblings: Sequence[str],
    callable_siblings: Sequence[str],
) -> dict[str, JSONValue]:
    entry = binding.entry
    return {
        "adapter_class_symbol": binding.adapter_class_symbol,
        "binding_fingerprint_sha256": binding.binding_fingerprint,
        "binding_group_id": binding.binding_group_id,
        "callable_family_id": binding.callable_family_id,
        "callable_or_class_symbol": (
            f"{binding.implementation_owner_symbol}.{binding.callable_symbol}"
        ),
        "classification": classification,
        "classification_group_id": classification_group_id,
        "declared_native_ticket_cardinality": {
            "maximum": entry.native_ticket_maximum,
            "minimum": entry.native_ticket_minimum,
            "response_shape": entry.response_shape,
        },
        "exact_binding_sibling_strategy_ids": list(exact_siblings),
        "game_identities": _game_identities(entry.lottery_types),
        "implementation_module": binding.implementation_module,
        "implementation_path": binding.implementation_path,
        "implementation_source_digest_scope": "NORMALIZED_EFFECTIVE_ADAPTER_HOOK_AST",
        "implementation_source_digest_sha256": binding.implementation_source_digest,
        "lottery_identities": list(entry.lottery_types),
        "registry_adapter_module": binding.adapter_module,
        "registry_adapter_path": entry.adapter_path,
        "registry_catalog_locator": entry.catalog_locator,
        "resolution_status": "RESOLVED",
        "sibling_strategy_ids": list(callable_siblings),
        "static_binding_parameters": binding.static_binding_parameters,
        "strategy_id": entry.strategy_id,
        "unresolved_reason": None,
    }


def _unresolved_record_json(binding: UnresolvedBinding) -> dict[str, JSONValue]:
    entry = binding.entry
    unresolved_digest = _stable_digest(
        {
            "catalog_locator": entry.catalog_locator,
            "reason": binding.reason,
            "strategy_id": entry.strategy_id,
        }
    )
    unresolved_group_id = f"unresolved-sha256:{unresolved_digest}"
    return {
        "adapter_class_symbol": binding.adapter_class_symbol,
        "binding_fingerprint_sha256": None,
        "binding_group_id": unresolved_group_id,
        "callable_family_id": None,
        "callable_or_class_symbol": binding.adapter_class_symbol,
        "classification": "DYNAMIC_OR_UNRESOLVED",
        "classification_group_id": unresolved_group_id,
        "declared_native_ticket_cardinality": {
            "maximum": entry.native_ticket_maximum,
            "minimum": entry.native_ticket_minimum,
            "response_shape": entry.response_shape,
        },
        "exact_binding_sibling_strategy_ids": [],
        "game_identities": _game_identities(entry.lottery_types),
        "implementation_module": binding.adapter_module,
        "implementation_path": binding.implementation_path,
        "implementation_source_digest_scope": None,
        "implementation_source_digest_sha256": None,
        "lottery_identities": list(entry.lottery_types),
        "registry_adapter_module": binding.adapter_module,
        "registry_adapter_path": entry.adapter_path,
        "registry_catalog_locator": entry.catalog_locator,
        "resolution_status": "DYNAMIC_OR_UNRESOLVED",
        "sibling_strategy_ids": [],
        "static_binding_parameters": {},
        "strategy_id": entry.strategy_id,
        "unresolved_reason": binding.reason,
    }


def _largest_group(
    groups: Sequence[tuple[str, Sequence[str]]],
) -> dict[str, JSONValue]:
    if not groups:
        return {"group_id": "NONE", "size": 0, "strategy_ids": []}
    group_id, strategy_ids = min(
        groups,
        key=lambda item: (-len(item[1]), item[0]),
    )
    return {
        "group_id": group_id,
        "size": len(strategy_ids),
        "strategy_ids": sorted(strategy_ids),
    }


def _summary(
    resolved: Sequence[ResolvedBinding],
    unresolved: Sequence[UnresolvedBinding],
) -> dict[str, JSONValue]:
    by_binding: dict[str, list[str]] = defaultdict(list)
    by_callable: dict[str, list[ResolvedBinding]] = defaultdict(list)
    for binding in resolved:
        by_binding[binding.binding_group_id].append(binding.entry.strategy_id)
        by_callable[binding.callable_family_id].append(binding)

    exact_groups = [
        (group_id, sorted(strategy_ids))
        for group_id, strategy_ids in by_binding.items()
        if len(strategy_ids) > 1
    ]
    parameterized_families = [
        (family_id, sorted(item.entry.strategy_id for item in family))
        for family_id, family in by_callable.items()
        if len({item.binding_group_id for item in family}) > 1
    ]
    exact_ids = {strategy_id for _, strategy_ids in exact_groups for strategy_id in strategy_ids}
    distinct_binding_ids = {
        binding.binding_group_id
        for binding in resolved
        if len(by_binding[binding.binding_group_id]) == 1
        and len(
            {
                sibling.binding_group_id
                for sibling in by_callable[binding.callable_family_id]
            }
        )
        == 1
    }
    resolved_ids = sorted(item.entry.strategy_id for item in resolved)
    unresolved_ids = sorted(item.entry.strategy_id for item in unresolved)
    return {
        "distinct_binding_identities": len(distinct_binding_ids),
        "identical_binding_group_count": len(exact_groups),
        "largest_exact_binding_group": _largest_group(exact_groups),
        "largest_parameterized_sibling_family": _largest_group(parameterized_families),
        "resolved_strategy_id_count": len(resolved_ids),
        "resolved_strategy_ids": resolved_ids,
        "same_callable_different_binding_family_count": len(parameterized_families),
        "strategy_ids_in_exact_identical_groups": len(exact_ids),
        "total_executable_strategy_ids_discovered": len(resolved) + len(unresolved),
        "unresolved_count": len(unresolved_ids),
        "unresolved_strategy_id_count": len(unresolved_ids),
        "unresolved_strategy_ids": unresolved_ids,
        "unique_resolved_binding_fingerprint_count": len(by_binding),
    }


def analyze_static_sources(
    catalog_source: str,
    module_sources: Mapping[str, str],
    *,
    module_paths: Mapping[str, str] | None = None,
    catalog_relative_path: str = CATALOG_RELATIVE_PATH.as_posix(),
) -> dict[str, JSONValue]:
    """Analyze an in-memory source bundle and return a deterministic artifact."""

    entries = parse_catalog_source(
        catalog_source,
        catalog_relative_path=catalog_relative_path,
    )
    index = SourceIndex(module_sources, module_paths)
    resolved: list[ResolvedBinding] = []
    unresolved: list[UnresolvedBinding] = []
    for entry in entries:
        outcome = _resolve_entry(entry, index)
        if isinstance(outcome, ResolvedBinding):
            resolved.append(outcome)
        else:
            unresolved.append(outcome)

    by_binding: dict[str, list[ResolvedBinding]] = defaultdict(list)
    by_callable: dict[str, list[ResolvedBinding]] = defaultdict(list)
    for binding in resolved:
        by_binding[binding.binding_group_id].append(binding)
        by_callable[binding.callable_family_id].append(binding)

    records: list[dict[str, JSONValue]] = []
    for binding in sorted(resolved, key=lambda item: item.entry.strategy_id):
        exact_family = by_binding[binding.binding_group_id]
        callable_family = by_callable[binding.callable_family_id]
        exact_siblings = sorted(
            item.entry.strategy_id
            for item in exact_family
            if item.entry.strategy_id != binding.entry.strategy_id
        )
        callable_siblings = sorted(
            item.entry.strategy_id
            for item in callable_family
            if item.entry.strategy_id != binding.entry.strategy_id
        )
        distinct_bindings_in_family = {
            item.binding_group_id for item in callable_family
        }
        classification: Classification
        classification_group_id: str
        if len(exact_family) > 1:
            classification = "IDENTICAL_BINDING"
            classification_group_id = binding.binding_group_id
        elif len(distinct_bindings_in_family) > 1:
            classification = "SAME_CALLABLE_DIFFERENT_BINDING"
            classification_group_id = binding.callable_family_id
        else:
            classification = "DISTINCT_BINDING"
            classification_group_id = binding.binding_group_id
        records.append(
            _record_json(
                binding,
                classification=classification,
                classification_group_id=classification_group_id,
                exact_siblings=exact_siblings,
                callable_siblings=callable_siblings,
            )
        )
    records.extend(
        _unresolved_record_json(binding)
        for binding in sorted(unresolved, key=lambda item: item.entry.strategy_id)
    )
    records.sort(key=lambda item: cast(str, item["strategy_id"]))

    exact_group_rows: list[JSONValue] = []
    for group_id, family in sorted(by_binding.items()):
        if len(family) <= 1:
            continue
        exact_group_rows.append(
            {
                "binding_group_id": group_id,
                "lottery_identities": sorted(
                    {lottery for item in family for lottery in item.entry.lottery_types}
                ),
                "size": len(family),
                "strategy_ids": sorted(item.entry.strategy_id for item in family),
            }
        )

    parameterized_rows: list[JSONValue] = []
    for family_id, family in sorted(by_callable.items()):
        binding_ids = sorted({item.binding_group_id for item in family})
        if len(binding_ids) <= 1:
            continue
        first = min(family, key=lambda item: item.entry.strategy_id)
        parameterized_rows.append(
            {
                "binding_group_ids": binding_ids,
                "callable_family_id": family_id,
                "callable_source_digest_sha256": first.implementation_source_digest,
                "implementation_module": first.implementation_module,
                "implementation_path": first.implementation_path,
                "size": len(family),
                "strategy_ids": sorted(item.entry.strategy_id for item in family),
            }
        )

    by_lottery: dict[str, JSONValue] = {}
    for game in GAME_ORDER:
        lottery = next(key for key, value in LOTTERY_TO_GAME.items() if value == game)
        game_resolved = [item for item in resolved if lottery in item.entry.lottery_types]
        game_unresolved = [item for item in unresolved if lottery in item.entry.lottery_types]
        game_summary = _summary(game_resolved, game_unresolved)
        game_summary["game_identity"] = game
        game_summary["lottery_identity"] = lottery
        by_lottery[game] = game_summary

    strategy_mapping: list[JSONValue] = [
        {
            "binding_group_id": record["binding_group_id"],
            "classification": record["classification"],
            "strategy_id": record["strategy_id"],
        }
        for record in records
    ]
    classification_counts = Counter(
        cast(str, record["classification"]) for record in records
    )
    return {
        "classification_contract": {
            "allowed_values": list(CLASSIFICATIONS),
            "distinct_binding_boundary": (
                "Structural binding difference only; not statistical independence or "
                "semantic orthogonality."
            ),
            "identity_rule": (
                "Same repository-relative implementation module and normalized effective "
                "hook AST digest, plus identical canonical static binding payload."
            ),
            "source_digest_boundary": (
                "Normalized effective adapter hook AST; it is structural identity, not a "
                "claim of semantic equivalence or identical historical behavior."
            ),
            "unresolved_policy": "Fail open; dynamic or ambiguous bindings are never guessed.",
        },
        "classification_counts": {
            value: classification_counts.get(value, 0) for value in CLASSIFICATIONS
        },
        "identical_binding_groups": exact_group_rows,
        "records": records,
        "schema_version": SCHEMA_VERSION,
        "scope": {
            "canonical_catalog_locator": (
                f"{catalog_relative_path}:_PRODUCTION_DESCRIPTORS"
            ),
            "database_access": "NO",
            "database_write": "NO",
            "executable_registry_locator": EXECUTABLE_REGISTRY_LOCATOR,
            "historical_replay": "NOT_RUN",
            "lottery_game_aliases": dict(sorted(LOTTERY_TO_GAME.items())),
            "method": "STATIC_SOURCE_AST_ONLY",
            "network_refresh": "NOT_RUN",
            "p638_zone2": "NOT_RUN",
            "predictive_advantage": "NOT_CLAIMED",
            "profitability": "NOT_CLAIMED",
        },
        "same_callable_different_binding_families": parameterized_rows,
        "strategy_mapping": strategy_mapping,
        "study_id": STUDY_ID,
        "summary": {
            "by_lottery": by_lottery,
            "overall": _summary(resolved, unresolved),
        },
    }


def _source_bundle(source_root: Path) -> tuple[str, dict[str, str], dict[str, str]]:
    catalog_path = source_root / CATALOG_RELATIVE_PATH
    catalog_source = catalog_path.read_text(encoding="utf-8")
    strategy_root = source_root / "src/lottolab/strategies"
    module_sources: dict[str, str] = {}
    module_paths: dict[str, str] = {}
    for path in sorted(strategy_root.rglob("*.py")):
        relative = Path(relative_source_path(source_root, path))
        module_parts = relative.with_suffix("").parts[1:]
        if module_parts[-1] == "__init__":
            module_parts = module_parts[:-1]
        module_name = ".".join(module_parts)
        module_sources[module_name] = path.read_text(encoding="utf-8")
        module_paths[module_name] = relative.as_posix()
    return catalog_source, module_sources, module_paths


def analyze_source_tree(source_root: Path) -> dict[str, JSONValue]:
    catalog_source, module_sources, module_paths = _source_bundle(source_root)
    return analyze_static_sources(
        catalog_source,
        module_sources,
        module_paths=module_paths,
    )


def _as_object(value: JSONValue, *, locator: str) -> dict[str, JSONValue]:
    if not isinstance(value, dict):
        raise TypeError(f"{locator} must be an object")
    return value


def _as_array(value: JSONValue, *, locator: str) -> list[JSONValue]:
    if not isinstance(value, list):
        raise TypeError(f"{locator} must be an array")
    return value


def _as_int(value: JSONValue, *, locator: str) -> int:
    if type(value) is not int:
        raise TypeError(f"{locator} must be an integer")
    return value


def _as_str(value: JSONValue, *, locator: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{locator} must be a string")
    return value


def _string_array(value: JSONValue, *, locator: str) -> list[str]:
    items = _as_array(value, locator=locator)
    if not all(isinstance(item, str) for item in items):
        raise TypeError(f"{locator} must contain only strings")
    return cast(list[str], items)


def render_markdown(result: dict[str, JSONValue], result_sha256: str) -> str:
    """Render the deterministic human-readable research boundary report."""

    summary = _as_object(result["summary"], locator="summary")
    overall = _as_object(summary["overall"], locator="summary.overall")
    by_lottery = _as_object(summary["by_lottery"], locator="summary.by_lottery")
    lines = [
        "# Strategy Matrix static lineage and redundancy map R1",
        "",
        "## Scope and interpretation",
        "",
        "This is a deterministic, DB-free static-source classification of the canonical",
        "registered executable strategy universe. It evaluates implementation diversity only.",
        "It does not evaluate historical behavior, statistical independence, predictive",
        "advantage, prize probability, profitability, or production promotion.",
        "",
        f"- Study: `{STUDY_ID}`",
        f"- Catalog: `{CATALOG_RELATIVE_PATH.as_posix()}:_PRODUCTION_DESCRIPTORS`",
        f"- Executable registry: `{EXECUTABLE_REGISTRY_LOCATOR}`",
        "- Method: Python AST/static declarations only; LottoLab modules are not imported",
        "- DB access/write: `NO` / `NO`",
        "- Historical replay: `NOT RUN`",
        f"- Result SHA-256: `{result_sha256}`",
        "",
        "## Aggregate summary",
        "",
        "| Scope | Total | Resolved | Unresolved | Exact groups | IDs in exact groups | "
        "Parameterized families | DISTINCT_BINDING identities |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]

    summary_rows: list[tuple[str, dict[str, JSONValue]]] = [("Overall", overall)]
    for game in GAME_ORDER:
        summary_rows.append(
            (game, _as_object(by_lottery[game], locator=f"summary.by_lottery.{game}"))
        )
    for label, row in summary_rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    label,
                    str(_as_int(row["total_executable_strategy_ids_discovered"], locator=label)),
                    str(_as_int(row["resolved_strategy_id_count"], locator=label)),
                    str(_as_int(row["unresolved_strategy_id_count"], locator=label)),
                    str(_as_int(row["identical_binding_group_count"], locator=label)),
                    str(
                        _as_int(
                            row["strategy_ids_in_exact_identical_groups"],
                            locator=label,
                        )
                    ),
                    str(
                        _as_int(
                            row["same_callable_different_binding_family_count"],
                            locator=label,
                        )
                    ),
                    str(_as_int(row["distinct_binding_identities"], locator=label)),
                ]
            )
            + " |"
        )

    exact_groups = _as_array(result["identical_binding_groups"], locator="exact groups")
    lines.extend(["", "## Exact identical bindings", ""])
    if not exact_groups:
        lines.append("No exact-identical binding group was statically established.")
    else:
        for value in exact_groups:
            group = _as_object(value, locator="exact group")
            group_id = _as_str(group["binding_group_id"], locator="binding group")
            strategy_ids = _string_array(group["strategy_ids"], locator="strategy ids")
            lines.append(f"- `{group_id}`: " + ", ".join(f"`{item}`" for item in strategy_ids))

    parameterized = _as_array(
        result["same_callable_different_binding_families"],
        locator="parameterized families",
    )
    lines.extend(["", "## Same callable, different static bindings", ""])
    if not parameterized:
        lines.append("No parameterized sibling family was statically established.")
    else:
        for value in parameterized:
            family = _as_object(value, locator="parameterized family")
            family_id = _as_str(family["callable_family_id"], locator="callable family")
            strategy_ids = _string_array(family["strategy_ids"], locator="strategy ids")
            lines.append(
                f"- `{family_id}` ({len(strategy_ids)} IDs): "
                + ", ".join(f"`{item}`" for item in strategy_ids)
            )

    unresolved_ids = _string_array(
        overall["unresolved_strategy_ids"], locator="unresolved strategy ids"
    )
    unresolved_reasons: dict[str, str] = {}
    for value in _as_array(result["records"], locator="records"):
        record = _as_object(value, locator="record")
        if record["classification"] != "DYNAMIC_OR_UNRESOLVED":
            continue
        strategy_id = _as_str(record["strategy_id"], locator="strategy id")
        reason = _as_str(record["unresolved_reason"], locator="unresolved reason")
        unresolved_reasons[strategy_id] = reason
    lines.extend(["", "## Dynamic or unresolved", ""])
    if not unresolved_ids:
        lines.append("No executable Strategy ID remained dynamically unresolved.")
    else:
        lines.extend(
            f"- `{strategy_id}`: `{unresolved_reasons[strategy_id]}`"
            for strategy_id in unresolved_ids
        )

    lines.extend(
        [
            "",
            "## Scientific boundary",
            "",
            "`IDENTICAL_BINDING` means identical structural source binding and static payload.",
            "`SAME_CALLABLE_DIFFERENT_BINDING` identifies parameter/configuration siblings and",
            "does not call them duplicates. `DISTINCT_BINDING` means only that structural",
            "binding identities differ. Normalized AST equality is not semantic equivalence,",
            "historical-behavior equality, or statistical independence.",
            "",
        ]
    )
    return "\n".join(lines)


def write_artifacts(
    result: dict[str, JSONValue],
    *,
    output_path: Path,
    report_path: Path,
) -> tuple[int, str]:
    result_bytes = canonical_json_bytes(result)
    result_sha256 = _sha256(result_bytes)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(result_bytes)
    report_path.write_text(render_markdown(result, result_sha256), encoding="utf-8")
    return len(result_bytes), result_sha256


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--report", type=Path, default=REPORT_PATH)
    return parser


def main() -> None:
    args = _parser().parse_args()
    source_root = cast(Path, args.source_root)
    output_path = cast(Path, args.output)
    report_path = cast(Path, args.report)
    result = analyze_source_tree(source_root)
    result_bytes, result_sha256 = write_artifacts(
        result,
        output_path=output_path,
        report_path=report_path,
    )
    overall = _as_object(
        _as_object(result["summary"], locator="summary")["overall"],
        locator="summary.overall",
    )
    print(f"result_path={output_path.as_posix()}")
    print(f"result_bytes={result_bytes}")
    print(f"result_sha256={result_sha256}")
    print(
        "resolved="
        f"{_as_int(overall['resolved_strategy_id_count'], locator='resolved')} "
        "unresolved="
        f"{_as_int(overall['unresolved_strategy_id_count'], locator='unresolved')}"
    )


if __name__ == "__main__":
    main()
