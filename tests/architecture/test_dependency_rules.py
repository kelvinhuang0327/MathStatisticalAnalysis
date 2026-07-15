"""Dependency direction is a contract enforced by CI, not by code review.

domain          → (nothing else in quantlab)
strategies      → domain
application     → domain, strategies
infrastructure  → domain, strategies, application (implements ports)
interfaces      → anything (composition root)
"""

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src" / "quantlab"

FORBIDDEN: dict[str, tuple[str, ...]] = {
    "domain": ("application", "interfaces", "infrastructure", "strategies"),
    "strategies": ("application", "interfaces", "infrastructure"),
    "application": ("interfaces", "infrastructure"),
    "infrastructure": ("interfaces",),
}


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_layer_dependencies() -> None:
    violations: list[str] = []
    for layer, forbidden_layers in FORBIDDEN.items():
        for path in (SRC / layer).rglob("*.py"):
            for module in imported_modules(path):
                for forbidden in forbidden_layers:
                    prefix = f"quantlab.{forbidden}"
                    if module == prefix or module.startswith(prefix + "."):
                        violations.append(f"{path.relative_to(SRC)} imports {module}")
    assert not violations, "layer violations:\n" + "\n".join(violations)
