# See LICENSE and NOTICE.
import argparse
import sys
import tomllib
from pathlib import Path

from .check import Check


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Check Isaac Lab 3.0 external task and component organization.")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--package", help="override the task import package inferred from project.name")
    args = parser.parse_args(argv)
    try:
        root = args.root.resolve()
        with (root / "pyproject.toml").open("rb") as stream:
            config = tomllib.load(stream)
        metadata = config.get("project", {})
        if not isinstance(metadata, dict) or not isinstance(metadata.get("entry-points", {}), dict):
            raise ValueError("expected project and project.entry-points tables")
        project_name = metadata.get("name")
        if not args.package and not isinstance(project_name, str):
            raise ValueError("expected a project.name string or --package NAME")
        package = args.package or project_name.replace("-", "_")
        if not package.isidentifier() or not (root / "src" / package).is_dir():
            raise ValueError(f"missing or invalid Python package src/{package}")
        check = Check(root, package)
        check.run()
        entries = metadata.get("entry-points", {}).get("isaaclab.tasks", {})
        if not isinstance(entries, dict):
            raise ValueError("expected a table of isaaclab.tasks entry points")
        check.task_entries(entries, root / "pyproject.toml")
        roots = {package, package + "_isaaclabs"}
        if not entries and not any(n.partition(".")[0] in roots for n in check.index.modules):
            raise ValueError(f"no readable task or extension modules for {package}")
    except (OSError, SyntaxError, ValueError, KeyError, ImportError) as exc:
        print(f"isaaclab-task-lint: {exc}", file=sys.stderr)
        return 2
    counts = {"violations": 0, "unresolved": 0, "missing_rules": 0}
    for path, line, column, rule, message in sorted(check.diagnostics):
        print(f"{path}:{line}:{column}: {rule} {message}")
        counts[{"ORG005": "unresolved", "ORG008": "missing_rules"}.get(rule, "violations")] += 1
    summary = " ".join(f"{label}={count}" for label, count in counts.items())
    print(
        f"registrations={len(check.registrations)} environments={len(check.environments)} "
        f"components={len(check.components)} {summary}"
    )
    return int(bool(check.diagnostics))


if __name__ == "__main__":
    raise SystemExit(main())
