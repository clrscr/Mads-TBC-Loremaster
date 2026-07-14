from __future__ import annotations

import argparse
import json
from pathlib import Path

from .catalog import build_catalog
from .guides import generate_addon
from .reports import build_zip, release_archive_name, write_audit, write_catalog
from .validate import validate_addon


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="mads-loremaster")
    result.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[2])
    commands = result.add_subparsers(dest="command", required=True)
    for name in ("catalog", "generate", "validate", "audit", "package", "all"):
        command = commands.add_parser(name)
        command.add_argument("questie", type=Path, help="Questie addon directory or checkout")
        if name == "catalog":
            command.add_argument("--output", type=Path)
        if name == "package":
            command.add_argument("--output", type=Path)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    project_root = args.project_root.expanduser().resolve()
    catalog = build_catalog(args.questie)
    reports = project_root / "reports"

    if args.command == "catalog":
        output = (args.output or reports / "catalog.json").resolve()
        write_catalog(catalog, output)
        print(output)
        return 0
    if args.command in {"generate", "all"}:
        guides = generate_addon(catalog, project_root)
        print(f"generated {len(guides)} Lua chapters")
        if args.command == "generate":
            return 0
    if args.command in {"validate", "audit", "package", "all"}:
        validation = validate_addon(catalog, project_root)
        print(json.dumps(validation.to_dict(), indent=2, sort_keys=True))
        if args.command in {"audit", "all"}:
            write_catalog(catalog, reports / "catalog.json")
            write_audit(catalog, validation, project_root, reports)
            print(reports / "AUDIT.md")
        if args.command in {"package", "all"} and validation.ok:
            output = getattr(args, "output", None) or project_root / "dist" / release_archive_name(project_root)
            print(build_zip(project_root, output.resolve()))
        return 0 if validation.ok else 1
    return 2
