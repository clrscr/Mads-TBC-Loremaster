from __future__ import annotations

import hashlib
from pathlib import Path

from .guides import ADDON_NAME, toc_all_lua_files
from .scope import load_json_object


def inspect_client_installation(project_root: Path) -> dict:
    config = load_json_object(project_root / "config" / "client_installation.json")
    client_root = Path(config["client_root"]).expanduser().resolve()
    build_info = Path(config["build_info"]).expanduser().resolve()
    addons = client_root / "Interface" / "AddOns"
    installed_addon = addons / ADDON_NAME
    guidelime_toc = addons / "Guidelime" / "Guidelime-TBC.toc"
    questie_toc = addons / "Questie" / "Questie-BCC.toc"
    tomtom_toc = next((path for path in (addons / "TomTom").glob("TomTom*.toc")), None) if (addons / "TomTom").is_dir() else None
    project_runtime = [project_root / f"{ADDON_NAME}.toc", *toc_all_lua_files(project_root)]
    runtime_matches = []
    for source in project_runtime:
        installed = installed_addon / source.relative_to(project_root)
        runtime_matches.append(
            installed.is_file() and _hash(installed) == _hash(source)
        )
    guidelime = _toc_metadata(guidelime_toc)
    questie = _toc_metadata(questie_toc)
    tomtom = _toc_metadata(tomtom_toc) if tomtom_toc else {}
    product = _build_product(build_info, config["product"])
    questie_source = Path(
        load_json_object(project_root / "config" / "source.json")["questie_path"]
    )
    parity_files = [
        Path("Database/TBC/tbcQuestDB.lua"),
        Path("Database/Corrections/ContentPhases/BurningCrusade.lua"),
    ]
    questie_parity = {
        str(relative): (
            (questie_source / relative).is_file()
            and (addons / "Questie" / relative).is_file()
            and _hash(questie_source / relative) == _hash(addons / "Questie" / relative)
        )
        for relative in parity_files
    }
    installed_toc = installed_addon / f"{ADDON_NAME}.toc"
    deployed_at = installed_toc.stat().st_mtime if installed_toc.is_file() else None
    saved_variables = list((client_root / "WTF").rglob(f"{ADDON_NAME}.lua"))
    latest_save = max((path.stat().st_mtime for path in saved_variables), default=None)
    historical_signal = any(
        "MadsTBCLoremasterCharacterDB" in path.read_text(errors="ignore")
        for path in saved_variables
    )
    launched_after_deployment = bool(
        deployed_at is not None and latest_save is not None and latest_save > deployed_at
    )
    checks = {
        "client_product": product.get("Product") == config["product"],
        "client_version": product.get("Version") == config["expected_version"],
        "questie_interface": questie.get("Interface") == config["expected_interface"],
        "questie_version": questie.get("Version") == config["questie_version"],
        "questie_source_parity": all(questie_parity.values()),
    }
    deployment_checks = {
        "installed_runtime_parity": bool(runtime_matches) and all(runtime_matches),
    }
    return {
        "schema_version": 1,
        "client": {
            "product": product.get("Product"),
            "version": product.get("Version"),
            "interface": config["expected_interface"],
        },
        "dependencies": {
            "Questie": questie,
            "TomTom": tomtom or {"status": "not_installed_optional"},
            "Guidelime": guidelime or {"status": "not_installed_optional"},
        },
        "checks": checks,
        "deployment_checks": deployment_checks,
        "questie_parity_files": questie_parity,
        "runtime_files_compared": len(runtime_matches),
        "historical_guidelime_load_signal": historical_signal,
        "launched_after_current_deployment": launched_after_deployment,
        "status": (
            "deployed_and_launched"
            if launched_after_deployment and all(checks.values()) and all(deployment_checks.values())
            else "deployed_not_launched"
            if all(checks.values()) and all(deployment_checks.values())
            else "runtime_not_deployed"
            if all(checks.values())
            else "installation_mismatch"
        ),
        "limitations": [
            "SavedVariables prove only that the standalone addon reached a save cycle.",
            "A post-deployment launch does not prove quest, waypoint, or route behavior without the manual matrix.",
            "No account, realm, or character identifiers are retained in this evidence record.",
        ],
    }


def _toc_metadata(path: Path) -> dict[str, str]:
    result = {}
    if not path.is_file():
        return result
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("## ") or ":" not in line:
            continue
        key, value = line[3:].split(":", 1)
        if key in {"Interface", "Title", "Version"}:
            result[key] = value.strip()
    return result


def _build_product(path: Path, product: str) -> dict[str, str]:
    if not path.is_file():
        return {}
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines:
        return {}
    headers = [field.split("!")[0] for field in lines[0].split("|")]
    for line in lines[1:]:
        values = line.split("|")
        row = dict(zip(headers, values))
        if row.get("Product") == product:
            return row
    return {}


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
