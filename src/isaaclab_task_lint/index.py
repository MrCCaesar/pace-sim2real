# See LICENSE and NOTICE.
"""Resolve local Python names without importing the inspected project."""

import ast
import json
import tokenize
from dataclasses import dataclass, field
from importlib.util import resolve_name
from pathlib import Path


class Unresolved(ValueError):
    """A binding has no unique static target."""


@dataclass
class Module:
    name: str
    path: Path
    tree: ast.Module
    names: dict[str, str | ast.expr] = field(default_factory=dict)
    stars: list[str] = field(default_factory=list)
    exports: set[str] | None = None
    scopes: dict[ast.AST, str] = field(default_factory=dict)


class Index:
    def __init__(self, root: Path):
        self.root = root
        # Generated from the public modules of the official Isaac Lab v3.0.0 release.
        self.official = json.loads(Path(__file__).with_name("official.json").read_text())
        self.modules: dict[str, Module] = {}
        self.defs: dict[str, tuple[Module, ast.AST]] = {}
        self.stub_only: set[str] = set()
        self.packages = {p.name for p in (root / "src").iterdir() if p.is_dir()}
        for path in sorted((root / "src").rglob("*.py*")):
            if path.suffix not in {".py", ".pyi"} or "__pycache__" in path.parts:
                continue
            self.load(path, root / "src")

    def load(self, path: Path, base: Path):
        parts = path.relative_to(base).with_suffix("").parts
        name = ".".join(parts[:-1] if parts[-1] == "__init__" else parts)
        with tokenize.open(path) as stream:
            tree = ast.parse(stream.read(), str(path))
        mod = self.modules.setdefault(name, Module(name, path, tree))
        package = name if path.stem == "__init__" else name.rpartition(".")[0]
        self._symbols(mod, tree, name, package, path.suffix == ".pyi")

    def _symbols(self, mod, scope, name, package, stub):
        # Keep lexical scopes separate: class-body and function-local imports can shadow module-level aliases.
        for node in scope.body:
            for child in ast.walk(node):
                mod.scopes[child] = name
            if isinstance(node, ast.ImportFrom):
                source = resolve_name("." * node.level + (node.module or ""), package)
                for alias in node.names:
                    if alias.name == "*":
                        if source not in mod.stars:
                            mod.stars.append(source)
                    else:
                        local = (name + "." + (alias.asname or alias.name)).removeprefix(mod.name + ".")
                        mod.names[local] = f"{source}.{alias.name}"
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    base_name = alias.name.split(".")[0]
                    local = (name + "." + (alias.asname or base_name)).removeprefix(mod.name + ".")
                    mod.names[local] = alias.name if alias.asname else base_name
            elif isinstance(node, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
                qualified = f"{name}.{node.name}"
                if stub and qualified not in self.defs:
                    self.stub_only.add(qualified)
                self.defs.setdefault(qualified, (mod, node))
                self._symbols(mod, node, qualified, package, stub)
            elif isinstance(node, ast.Assign | ast.AnnAssign):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for target in targets:
                    if isinstance(target, ast.Name) and node.value is not None:
                        local = (name + "." + target.id).removeprefix(mod.name + ".")
                        mod.names[local] = node.value
                        if local == "__all__" and isinstance(node.value, ast.List | ast.Tuple):
                            mod.exports = {e.value for e in node.value.elts if isinstance(e, ast.Constant)}

    def lookup(self, name: str, seen: frozenset[str] = frozenset()) -> str:
        if (name in self.defs and name not in self.stub_only) or name in self.modules:
            return name
        if name in seen:
            raise Unresolved(f"cyclic reference to {name}")
        seen = seen | {name}
        parent, _, member = name.rpartition(".")
        if name in self.official:
            return name
        if parent in self.official:
            if member not in self.official[parent]:
                raise Unresolved(f"missing Isaac Lab 3.0 export {name}")
            return name
        mod = self.modules.get(parent)
        if mod:
            alias = mod.names.get(member)
            if isinstance(alias, str) and alias != name:
                return self.lookup(alias, seen)
            if isinstance(alias, ast.expr):
                return self.expr(mod, alias, seen)
            # Prefer explicit local definitions over upstream wildcard fallbacks.
            candidates = set()
            for source in mod.stars:
                exported = self.modules[source].exports if source in self.modules else None
                if member.startswith("_") or (exported is not None and member not in exported):
                    continue
                try:
                    candidates.add(self.lookup(f"{source}.{member}", seen))
                except Unresolved as exc:
                    if not str(exc).startswith("missing "):
                        raise
            if len(candidates) == 1:
                return candidates.pop()
            if candidates:
                raise Unresolved(f"ambiguous exports for {name}: {sorted(candidates)}")
        if name in self.stub_only:
            raise Unresolved(f"missing runtime definition for stub {name}")
        top = name.split(".")[0]
        if not all(part.isidentifier() for part in name.split(".")):
            raise Unresolved(f"invalid module or symbol {name}")
        if top not in self.packages or (self.root / top).is_dir():
            outside = self.root.joinpath(*name.split("."))
            for path in (outside.with_suffix(".py"), outside / "__init__.py"):
                if path.is_file() and name not in self.modules:
                    self.load(path, self.root)
                    self.packages.add(top)
                    return self.lookup(name)
            if (
                parent
                and parent not in self.modules
                and self.root.joinpath(*parent.split(".")).with_suffix(".py").is_file()
            ):
                self.load(self.root.joinpath(*parent.split(".")).with_suffix(".py"), self.root)
                self.packages.add(top)
                return self.lookup(name)
            if top not in self.packages:
                return name
        raise Unresolved(f"missing local module or definition {name}")

    def expr(self, mod: Module, node: ast.expr, seen: frozenset[str] = frozenset()) -> str:
        if isinstance(node, ast.Name):
            scope = mod.scopes.get(node, mod.name)
            while scope != mod.name:
                key = f"{scope}.{node.id}"
                value = mod.names.get(key.removeprefix(mod.name + "."))
                if key in self.defs:
                    return key
                if key in seen:
                    raise Unresolved(f"cyclic reference to {key}")
                if isinstance(value, str):
                    return self.lookup(value, seen | {key})
                if isinstance(value, ast.expr):
                    return self.expr(mod, value, seen | {key})
                scope = scope.rpartition(".")[0]
            return self.lookup(f"{mod.name}.{node.id}", seen)
        if isinstance(node, ast.Attribute):
            return self.lookup(f"{self.expr(mod, node.value, seen)}.{node.attr}", seen)
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            package = mod.name if mod.path.stem == "__init__" else mod.name.rpartition(".")[0]
            module, sep, symbol = node.value.replace("{DIR}", package).partition(":")
            if sep:
                return self.lookup(f"{module}.{symbol}", seen)
        if isinstance(node, ast.Call):
            raise Unresolved(f"runtime factory {ast.unparse(node.func)}")
        raise Unresolved(f"unsupported expression {ast.unparse(node)}")

    def string(self, mod: Module, node: ast.expr) -> str:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        if isinstance(node, ast.JoinedStr):
            parts = []
            for value in node.values:
                if isinstance(value, ast.Constant):
                    parts.append(value.value)
                elif isinstance(value, ast.FormattedValue) and ast.unparse(value.value) == "__name__":
                    parts.append(mod.name)
                elif isinstance(value, ast.FormattedValue) and isinstance(value.value, ast.Attribute):
                    if value.value.attr != "__name__":
                        raise Unresolved("dynamic registration string")
                    parts.append(self.expr(mod, value.value.value))
                else:
                    raise Unresolved("dynamic registration string")
            return "".join(parts)
        raise Unresolved("expected a static registration string")
