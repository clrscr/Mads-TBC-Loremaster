from __future__ import annotations

import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SCOPE = PROJECT_ROOT / "config" / "scope.json"
DEFAULT_RELEASE = PROJECT_ROOT / "config" / "release.json"
DEFAULT_CONTENT_POLICY = PROJECT_ROOT / "config" / "content_policy.json"


class ScopeConfigurationError(RuntimeError):
    pass


def load_json_object(path: str | Path) -> dict[str, Any]:
    source = Path(path).expanduser().resolve()
    try:
        value = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ScopeConfigurationError(f"unable to read configuration {source}: {error}") from error
    if not isinstance(value, dict):
        raise ScopeConfigurationError(f"configuration {source} must contain a JSON object")
    return value


def load_scope(path: str | Path = DEFAULT_SCOPE) -> tuple[dict[str, Any], dict[str, Any]]:
    scope = load_json_object(path)
    required = {
        "schema_version", "id", "game_version", "interface", "content_phase_profile",
        "realm_rulesets", "faction", "race", "class", "start_level", "max_level",
        "starting_state", "quest_log_policy", "content_policy",
    }
    missing = sorted(required - scope.keys())
    if missing:
        raise ScopeConfigurationError(f"scope is missing required fields: {', '.join(missing)}")
    phase_path = PROJECT_ROOT / str(scope["content_phase_profile"])
    phase = load_json_object(phase_path)
    for key in ("schema_version", "id", "expansion", "phase", "name", "interface", "official_sources"):
        if key not in phase:
            raise ScopeConfigurationError(f"phase profile is missing required field: {key}")
    if scope["interface"] != phase["interface"]:
        raise ScopeConfigurationError(
            f"scope interface {scope['interface']} does not match phase interface {phase['interface']}"
        )
    if not isinstance(phase["phase"], int) or not 1 <= phase["phase"] <= 5:
        raise ScopeConfigurationError("TBC phase must be an integer from 1 through 5")
    if not phase["official_sources"]:
        raise ScopeConfigurationError("phase profile must cite at least one official source")
    return scope, phase


def load_content_policy(path: str | Path = DEFAULT_CONTENT_POLICY) -> dict[str, Any]:
    policy = load_json_object(path)
    required = {
        "schema_version", "id", "rule", "maximum_expansion", "allowed_quest_sources",
        "allowed_entity_sources", "covered_correction_only_allowlist", "forbidden_source_prefixes",
    }
    missing = sorted(required - policy.keys())
    if missing:
        raise ScopeConfigurationError(
            f"content policy is missing required fields: {', '.join(missing)}"
        )
    if policy["rule"] != "pre_cataclysm_only" or policy["maximum_expansion"] != "TBC":
        raise ScopeConfigurationError(
            "content policy must enforce pre_cataclysm_only with TBC as the maximum expansion"
        )
    return policy


def load_release(path: str | Path = DEFAULT_RELEASE) -> dict[str, Any]:
    release = load_json_object(path)
    required = {
        "schema_version", "version", "channel", "static_release_gate_ready",
        "public_release_ready", "release_blockers"
    }
    missing = sorted(required - release.keys())
    if missing:
        raise ScopeConfigurationError(f"release configuration is missing: {', '.join(missing)}")
    if not isinstance(release["public_release_ready"], bool):
        raise ScopeConfigurationError("public_release_ready must be boolean")
    if not isinstance(release["static_release_gate_ready"], bool):
        raise ScopeConfigurationError("static_release_gate_ready must be boolean")
    if release["public_release_ready"] and release["release_blockers"]:
        raise ScopeConfigurationError("a public-ready release cannot retain release blockers")
    return release
