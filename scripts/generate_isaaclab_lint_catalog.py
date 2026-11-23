# See LICENSE and NOTICE.
"""Refresh the offline symbol inventory from the official Isaac Lab v3.0.0 release."""

import argparse
import ast
import io
import json
import subprocess
import tarfile
from pathlib import Path

# Peeled commit of the official v3.0.0 tag.
RELEASE = "e3f7d9ff1f5d7f8280de3ece9000b7117f66bcf4"


def public_names(source, path):
    names = set()
    for node in ast.parse(source, str(path)).body:
        if isinstance(node, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            names.add(node.name)
        elif isinstance(node, ast.Import | ast.ImportFrom):
            names.update(alias.asname or alias.name.split(".")[0] for alias in node.names if alias.name != "*")
        elif isinstance(node, ast.Assign | ast.AnnAssign):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
                    if target.id == "__all__" and isinstance(node.value, ast.Tuple | ast.List):
                        names.update(e.value for e in node.value.elts if isinstance(e, ast.Constant))
                    # isaaclab.sim exposes backend compatibility names via module __getattr__.
                    if (
                        "_FORWARDS" in target.id
                        and isinstance(node.value, ast.Call)
                        and ast.unparse(node.value.func) == "frozenset"
                        and node.value.args
                        and isinstance(node.value.args[0], ast.Set)
                    ):
                        names.update(e.value for e in node.value.args[0].elts if isinstance(e, ast.Constant))
    return {name for name in names if isinstance(name, str) and not name.startswith("_")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkout", type=Path)
    args = parser.parse_args()
    command = ["git", "-C", str(args.checkout), "archive", "--format=tar.gz", RELEASE, "source"]
    archive = subprocess.check_output(command)
    modules = {}
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as files:
        for member in files:
            path = Path(member.name)
            if not member.isfile() or path.suffix not in {".py", ".pyi"}:
                continue
            parts = path.with_suffix("").parts
            if len(parts) < 4 or not parts[1].startswith("isaaclab") or parts[1] != parts[2]:
                continue
            module = ".".join(parts[2:-1] if parts[-1] == "__init__" else parts[2:])
            with files.extractfile(member) as stream:
                modules.setdefault(module, set()).update(public_names(stream.read(), path))
    entries = [json.dumps(k) + ":" + json.dumps(sorted(v), separators=(",", ":")) for k, v in sorted(modules.items())]
    catalog = Path(__file__).resolve().parents[1] / "src/isaaclab_task_lint/official.json"
    catalog.write_text("{\n" + ",\n".join(entries) + "\n}\n")


if __name__ == "__main__":
    main()
