# See LICENSE and NOTICE.
"""Static file references used by Isaac Lab resource configurations."""

import ast
from pathlib import Path
from urllib.parse import urlsplit

from .index import Unresolved

RESOURCE_FIELDS = {
    "usd_path",
    "urdf_path",
    "mjcf_path",
    "mdl_path",
    "mesh_path",
    "texture_file",
    "asset_path",
}


def resource_value(index, mod, node, seen=frozenset()):
    """Evaluate literals, imported constants and the common __file__-relative path idiom."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name) and node.id == "__file__":
        return str(mod.path)
    if isinstance(node, ast.JoinedStr):
        return "".join(
            resource_value(index, mod, v.value if isinstance(v, ast.FormattedValue) else v, seen) for v in node.values
        )
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div | ast.Add):
        left = resource_value(index, mod, node.left, seen)
        right = resource_value(index, mod, node.right, seen)
        return left.rstrip("/") + "/" + right if isinstance(node.op, ast.Div) else left + right
    if isinstance(node, ast.Attribute) and node.attr == "parent":
        return str(Path(resource_value(index, mod, node.value, seen)).parent)
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Attribute) and node.func.attr == "resolve" and not node.args:
            return resource_value(index, mod, node.func.value, seen)
        if len(node.args) == 1 and index.expr(mod, node.func) in {"pathlib.Path", "builtins.str"}:
            return resource_value(index, mod, node.args[0], seen)
    if isinstance(node, ast.Name):
        qualified = f"{mod.name}.{node.id}"
        if qualified in seen:
            raise Unresolved(f"cyclic resource reference {qualified}")
        alias = mod.names.get(node.id)
        if isinstance(alias, ast.expr):
            return resource_value(index, mod, alias, seen | {qualified})
        if isinstance(alias, str):
            module, _, name = alias.rpartition(".")
            if module in index.modules:
                return resource_value(index, index.modules[module], ast.Name(id=name), seen | {qualified})
            if module == "isaaclab.utils.assets" and name in index.official.get(module, []):
                return "isaaclab://assets/" + name
    raise Unresolved(f"cannot resolve resource expression {ast.unparse(node)}")


def check_resource(index, mod, node):
    path = resource_value(index, mod, node)
    if urlsplit(path).scheme in {"http", "https", "omniverse", "isaaclab"}:
        return
    target = (index.root / path).resolve()
    if not target.is_file():
        raise Unresolved(f"missing resource {path}")
