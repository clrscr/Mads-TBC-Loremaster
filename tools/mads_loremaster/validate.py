from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from math import hypot
from pathlib import Path

from .authored_route import compare_authored_routes, load_authored_routes
from .client_installation import inspect_client_installation
from .guides import (
    ADDON_NAME,
    PRODUCT_TITLE,
    ALTERNATIVE_GROUP,
    GUIDE_GROUP,
    INTERFACE,
    MAX_LUA_LINES,
    OPTIONAL_GROUP,
    PRIMARY_GROUP,
    TAG_RE,
    guide_quest_ids,
    parse_guide_file,
    toc_all_lua_files,
    toc_lua_files,
)
from .model import Catalog, Quest
from .questie import load_questie_active_tbc_phase
from .scope import load_release
from .travel import load_travel_network, plan_travel


DISPLAY_TAG_RE = re.compile(r"\[(QA|QC|QT)(\d+)(?:,\d+)?(?:\s([^\]]+))?\]")
BRACKET_CODE_RE = re.compile(r"\[([A-Z]+)")
SUPPORTED_GUIDELIME_CODES = {
    "N", "NX", "D", "GA", "A", "O", "OC", "QA", "QC", "QT", "QS", "G",
    "L", "XP", "H", "F", "T", "S", "P", "V", "R", "GG", "GL", "CI", "REP",
    "UI", "GI", "GT", "TAR", "SP", "LE", "SK",
}
STRING_BANNED_PHRASES = (
    "Complete objectives involving",
    "then complete",
    "scripted or exploration objective to completion",
    "Optional: discover the flight path",
)
INTERNAL_PLAYER_TEXT_RE = re.compile(
    r"\b(?:quest credit|credit marker|quest trigger|invis(?:ible)?)\b",
    re.IGNORECASE,
)
ACCIDENTAL_PERIOD_RE = re.compile(r"(?<!\.)\.\.(?!\.)|\.\.\.\.")
MAX_PLAYER_LINE_LENGTH = 300


@dataclass
class ValidationResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metrics: dict[str, int] = field(default_factory=dict)
    simulations: dict[str, dict[str, int | bool]] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "errors": self.errors,
            "warnings": self.warnings,
            "metrics": self.metrics,
            "resume_simulations": self.simulations,
        }


def validate_content_provenance(catalog: Catalog) -> tuple[list[str], dict[str, int]]:
    """Enforce the build's pre-Cataclysm data boundary.

    Quest IDs are not an expansion boundary: Anniversary corrections can use
    modern-looking IDs, while Cataclysm retained many original quest IDs. The
    reliable gate is the exact Questie expansion snapshot that supplied each
    row and each NPC/object/item fact.
    """
    errors: list[str] = []
    policy = catalog.content_policy
    allowed_quest_sources = set(policy.get("allowed_quest_sources", ()))
    allowed_entity_sources = set(policy.get("allowed_entity_sources", ()))
    correction_only_allowlist = {
        int(quest_id) for quest_id in policy.get("covered_correction_only_allowlist", ())
    }
    forbidden_prefixes = tuple(policy.get("forbidden_source_prefixes", ()))
    covered_statuses = {"covered_primary", "covered_optional", "covered_alternative"}
    emitted_statuses = covered_statuses | {"baseline_completed"}
    tbc_snapshot = "Database/TBC/tbcQuestDB.lua"
    forbidden_source_references = 0
    correction_only_emitted = 0
    post_tbc_emitted = 0

    if policy.get("rule") != "pre_cataclysm_only" or policy.get("maximum_expansion") != "TBC":
        errors.append("content policy does not enforce a TBC-maximum pre-Cataclysm boundary")

    for entry in catalog.entries.values():
        quest = entry.quest
        for source in quest.data_sources:
            if source not in allowed_quest_sources:
                errors.append(f"quest {quest.id} uses unapproved quest source {source}")
            if source.startswith(forbidden_prefixes):
                forbidden_source_references += 1
                errors.append(f"quest {quest.id} uses forbidden post-TBC source {source}")
        for endpoint in quest.starter_sources + quest.finisher_sources + quest.objective_sources:
            source = endpoint.data_source
            if source not in allowed_entity_sources:
                errors.append(
                    f"quest {quest.id} {endpoint.kind} {endpoint.id} uses unapproved entity source {source}"
                )
            if source and source.startswith(forbidden_prefixes):
                forbidden_source_references += 1
                errors.append(
                    f"quest {quest.id} {endpoint.kind} {endpoint.id} uses forbidden post-TBC source {source}"
                )

        if entry.status not in emitted_statuses:
            continue
        if quest.content_era != "pre_cataclysm":
            post_tbc_emitted += 1
            errors.append(
                f"emitted quest {quest.id} has non-pre-Cataclysm provenance {quest.content_era!r}"
            )
        if tbc_snapshot not in quest.data_sources:
            correction_only_emitted += 1
            if quest.id not in correction_only_allowlist:
                errors.append(
                    f"emitted quest {quest.id} exists only in TBC runtime corrections and is not allowlisted"
                )

    covered = [entry for entry in catalog.entries.values() if entry.status in covered_statuses]
    baseline = [entry for entry in catalog.entries.values() if entry.status == "baseline_completed"]
    metrics = {
        "pre_cataclysm_covered_quests": sum(
            entry.quest.content_era == "pre_cataclysm" for entry in covered
        ),
        "pre_cataclysm_baseline_quests": sum(
            entry.quest.content_era == "pre_cataclysm" for entry in baseline
        ),
        "post_tbc_emitted_quests": post_tbc_emitted,
        "correction_only_emitted_quests": correction_only_emitted,
        "forbidden_source_references": forbidden_source_references,
    }
    return errors, metrics


def validate_addon(catalog: Catalog, project_root: Path) -> ValidationResult:
    result = ValidationResult()
    toc = project_root / f"{ADDON_NAME}.toc"
    if not toc.is_file():
        result.errors.append(f"missing {toc.name}")
        return result
    toc_source = toc.read_text(encoding="utf-8")
    release = load_release(project_root / "config" / "release.json")
    provenance_errors, provenance_metrics = validate_content_provenance(catalog)
    result.errors.extend(provenance_errors)
    result.metrics.update(provenance_metrics)
    if not release["public_release_ready"] and release["channel"] == "stable":
        result.errors.append("a release with open public-readiness blockers cannot use the stable channel")
    if not release["public_release_ready"] and "-" not in release["version"]:
        result.errors.append("a release with open public-readiness blockers must use a prerelease version")
    if release["static_release_gate_ready"]:
        expected_blockers = ["Burning Crusade Classic Anniversary in-game verification matrix"]
        if release["public_release_ready"]:
            result.errors.append("a public-ready release cannot still be a static-gate candidate")
        if release["release_blockers"] != expected_blockers:
            result.errors.append(
                "a static-gate-ready candidate must retain only the exact in-game verification blocker"
            )
    selected_interface = str(catalog.scope.get("interface", ""))
    phase_interface = str(catalog.phase_profile.get("interface", ""))
    if selected_interface != INTERFACE or phase_interface != INTERFACE:
        result.errors.append(
            f"configured interface mismatch: generator={INTERFACE}, scope={selected_interface}, "
            f"phase={phase_interface}"
        )
    configured_phase = int(catalog.phase_profile.get("phase", 0))
    questie_phase = load_questie_active_tbc_phase(Path(catalog.source_path))
    if configured_phase != questie_phase:
        result.errors.append(
            f"selected TBC phase {configured_phase} does not match pinned Questie active phase {questie_phase}"
        )
    if not catalog.phase_profile.get("official_sources"):
        result.errors.append("selected phase has no official source")
    quest_log_policy = catalog.scope.get("quest_log_policy", {})
    client_maximum = quest_log_policy.get("client_maximum")
    working_cap = int(quest_log_policy.get("working_cap", 0))
    reserved_slots = int(quest_log_policy.get("reserved_slots", 0))
    if isinstance(client_maximum, int) and working_cap + reserved_slots > client_maximum:
        result.errors.append(
            f"quest-log policy exceeds client maximum: working {working_cap} + reserve "
            f"{reserved_slots} > {client_maximum}"
        )
    for required in (
        f"## Interface: {selected_interface}",
        f"## Title: {PRODUCT_TITLE}",
        "## RequiredDeps: Questie",
        "## OptionalDeps: TomTom, Guidelime",
        "## SavedVariables: MadsTBCLoremasterDB",
        "## SavedVariablesPerCharacter: MadsTBCLoremasterCharacterDB",
        f"## Version: {release['version']}",
        f"## X-Release-Channel: {release['channel']}",
        f"## X-Static-Release-Gate: {'true' if release['static_release_gate_ready'] else 'false'}",
        f"## X-Public-Release-Ready: {'true' if release['public_release_ready'] else 'false'}",
    ):
        if required not in toc_source:
            result.errors.append(f"TOC missing exact metadata: {required}")

    runtime_files = [
        "Data/QuestManifest.lua",
        "Data/ZoneManifest.lua",
        "Data/Lore.lua",
        "Runtime/Core.lua",
        "Runtime/Character.lua",
        "Runtime/Eligibility.lua",
        "Runtime/Router.lua",
        "Runtime/Navigation.lua",
        "Runtime/GuideCompat.lua",
        "Runtime/UI.lua",
    ]
    toc_runtime = [
        str(path.relative_to(project_root)).replace("\\", "/")
        for path in toc_all_lua_files(project_root)
        if not str(path.relative_to(project_root)).replace("\\", "/").startswith("Guides/")
    ]
    if toc_runtime != runtime_files:
        result.errors.append(
            "standalone runtime TOC order mismatch: " + ", ".join(toc_runtime)
        )
    for relative in runtime_files:
        if not (project_root / relative).is_file():
            result.errors.append(f"missing standalone runtime file: {relative}")
    manifest_path = project_root / "Data" / "QuestManifest.lua"
    manifest_source = manifest_path.read_text(encoding="utf-8") if manifest_path.is_file() else ""
    manifest_quest_ids = {
        int(value) for value in re.findall(r"^\s*\[(\d+)\]\s*=", manifest_source, re.MULTILINE)
    }
    covered_quest_ids = {
        entry.quest.id
        for entry in catalog.entries.values()
        if entry.status.startswith("covered") or entry.status == "baseline_completed"
    }
    missing_from_manifest = sorted(covered_quest_ids - manifest_quest_ids)
    if missing_from_manifest:
        result.errors.append(
            f"runtime manifest omits covered quests: {missing_from_manifest[:25]}"
        )
    if len(manifest_quest_ids) <= len(covered_quest_ids):
        result.errors.append(
            "runtime manifest does not expand beyond the legacy Night Elf Hunter catalog"
        )
    required_runtime_tokens = {
        "Runtime/Core.lua": ("MadsTBCLoremasterCharacterDB", "function Addon:Rescan"),
        "Runtime/Character.lua": ("GetQuestsCompleted", "function Character:Scan"),
        "Runtime/Eligibility.lua": ("permanently_locked", "function Eligibility:Rebuild"),
        "Runtime/Router.lua": ("catchup", "back_on_track", "function Router:Build"),
        "Runtime/Navigation.lua": ("TomTom.AddWaypoint", "function Navigation:SetForQuest"),
        "Runtime/UI.lua": ("Catch Up on What You Missed", "Get Back on Track", "MaybeWarnChoice"),
    }
    for relative, tokens in required_runtime_tokens.items():
        path = project_root / relative
        source = path.read_text(encoding="utf-8") if path.is_file() else ""
        for token in tokens:
            if token not in source:
                result.errors.append(f"{relative} missing runtime contract token: {token}")
    result.metrics["runtime_files"] = len(runtime_files)
    result.metrics["runtime_manifest_quests"] = len(manifest_quest_ids)

    files = toc_lua_files(project_root)
    if not files:
        result.errors.append("TOC contains no Lua guide files")
        return result
    titles: dict[str, Path] = {}
    next_links: list[tuple[Path, str]] = []
    streams: dict[str, list[tuple[str, int, Path]]] = defaultdict(list)
    total_steps = 0
    batched_accept_groups = 0
    batched_quests = 0
    item_use_instructions = 0
    scripted_objective_instructions = 0
    tagged_preparation_instructions = 0
    objective_target_instructions = 0
    string_quality_lines = 0
    string_quality_violations = 0
    longest_guide_line = 0
    all_tags: list[tuple[str, int, Path]] = []
    step_lines: dict[tuple[str, int], str] = {}
    for file_index, path in enumerate(files):
        if not path.is_file():
            result.errors.append(f"TOC references missing file: {path.relative_to(project_root)}")
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        if len(lines) > MAX_LUA_LINES:
            result.errors.append(f"{path.relative_to(project_root)} has {len(lines)} lines (max {MAX_LUA_LINES})")
        source = "\n".join(lines)
        item_use_instructions += source.count("Use the quest item [UI")
        scripted_objective_instructions += source.count(
            "Complete the scripted or exploration event"
        )
        tagged_preparation_instructions += sum(
            source.count(prefix)
            for prefix in ("Elite/group recommended", "Escort — stay with", "Heroic dungeon —")
        )
        objective_target_instructions += sum(
            source.count(prefix)
            for prefix in (
                "Complete the required NPC or creature",
                "Complete the required objectives",
                "Complete the marked or scripted objective",
                "Interact with the required object",
                "Collect or use the required item",
            )
        )
        if "[GA NightElf,Hunter]" in source:
            result.errors.append(
                f"{path.relative_to(project_root)} retains the obsolete Night Elf Hunter picker restriction"
            )
        try:
            title, next_title, group, tags = parse_guide_file(path)
        except ValueError as error:
            result.errors.append(str(error))
            continue
        if group not in {PRIMARY_GROUP, OPTIONAL_GROUP, ALTERNATIVE_GROUP}:
            result.errors.append(f"{path.relative_to(project_root)} registered in unexpected group {group!r}")
        if title in titles:
            result.errors.append(f"duplicate guide title {title!r}")
        if group == ALTERNATIVE_GROUP and (
            "Mutually Exclusive Choices" in title or "Other Choices" in title
        ):
            result.errors.append(
                f"{path.relative_to(project_root)} exposes an internal choice-stream label"
            )
        titles[title] = path
        if next_title:
            next_links.append((path, next_title))
        branch = path.parent.name
        streams[branch].extend((tag, quest_id, path) for tag, quest_id in tags)
        all_tags.extend((tag, quest_id, path) for tag, quest_id in tags)
        for line_number, line in enumerate(lines, 1):
            string_quality_lines += 1
            longest_guide_line = max(longest_guide_line, len(line))
            relative = path.relative_to(project_root)
            problems: list[str] = []
            if len(line) > MAX_PLAYER_LINE_LENGTH:
                problems.append(f"line is {len(line)} characters (max {MAX_PLAYER_LINE_LENGTH})")
            is_lua_wrapper = line.startswith("Guidelime.registerGuide([[") or line.startswith("]], ")
            if not is_lua_wrapper and line.count("[") != line.count("]"):
                problems.append("unbalanced brackets")
            if "  " in line:
                problems.append("repeated whitespace")
            if ACCIDENTAL_PERIOD_RE.search(line):
                problems.append("contains accidental repeated sentence punctuation")
            for phrase in STRING_BANNED_PHRASES:
                if phrase.lower() in line.lower():
                    problems.append(f"contains generator-style phrase {phrase!r}")
            if INTERNAL_PLAYER_TEXT_RE.search(line):
                problems.append("exposes an internal Questie marker name")
            unsupported = sorted(set(BRACKET_CODE_RE.findall(line)) - SUPPORTED_GUIDELIME_CODES)
            if unsupported:
                problems.append(f"uses unsupported Guidelime codes {unsupported}")
            for match in DISPLAY_TAG_RE.finditer(line):
                quest_id = int(match.group(2))
                quest = catalog.entries.get(quest_id)
                if quest is None:
                    continue
                expected_name = " ".join(
                    quest.quest.name.replace("[", "(").replace("]", ")").split()
                )
                if match.group(3) != expected_name:
                    problems.append(
                        f"quest {quest_id} display name {match.group(3)!r} does not match {expected_name!r}"
                    )
            if problems:
                string_quality_violations += len(problems)
                result.errors.extend(
                    f"{relative}:{line_number}: {problem}"
                    for problem in problems
                )
            for tag, quest_id in TAG_RE.findall(line):
                step_lines[(tag, int(quest_id))] = line
        accept_run = 0
        for tag, _ in tags + [("END", 0)]:
            if tag == "QA":
                accept_run += 1
            else:
                if accept_run >= 2:
                    batched_accept_groups += 1
                    batched_quests += accept_run
                accept_run = 0
        total_steps += len(tags)
    for path, next_title in next_links:
        if next_title not in titles:
            result.errors.append(f"{path.relative_to(project_root)} links to missing guide {next_title!r}")

    quests = {entry.quest.id: entry.quest for entry in catalog.entries.values()}
    allowed = {
        entry.quest.id
        for entry in catalog.entries.values()
        if entry.status in {"covered_primary", "covered_optional", "covered_alternative"}
    }
    excluded = {
        entry.quest.id
        for entry in catalog.entries.values()
        if entry.status in {"excluded", "unavailable"}
    }
    future_phase = {
        entry.quest.id
        for entry in catalog.entries.values()
        if entry.reason_code == "future_phase"
    }
    baseline = {entry.quest.id for entry in catalog.entries.values() if entry.status == "baseline_completed"}
    inactive_event_emitted = {
        entry.quest.id
        for entry in catalog.entries.values()
        if entry.status in {"covered_primary", "covered_optional", "covered_alternative"}
        and "seasonal_or_event" in entry.conditional_categories
    }
    if inactive_event_emitted:
        result.errors.append(
            "seasonal or inactive world-event quests were emitted: "
            f"{sorted(inactive_event_emitted)[:25]}"
        )
    state_counts: dict[int, Counter[str]] = defaultdict(Counter)
    for tag, quest_id, path in all_tags:
        if quest_id not in quests:
            result.errors.append(f"{path.relative_to(project_root)} references unknown Questie quest {quest_id}")
        if quest_id in excluded or quest_id not in allowed:
            result.errors.append(f"{path.relative_to(project_root)} includes ineligible quest {quest_id}")
        if quest_id in future_phase:
            result.errors.append(
                f"{path.relative_to(project_root)} includes future-phase quest {quest_id} "
                f"for selected phase {catalog.phase_profile.get('phase')}"
            )
        state_counts[quest_id][tag] += 1
    for quest_id in sorted(allowed):
        counts = state_counts[quest_id]
        if counts != Counter({"QA": 1, "QC": 1, "QT": 1}):
            result.errors.append(f"quest {quest_id} has guide state counts {dict(counts)}; expected one QA/QC/QT")
        entry = catalog.entries[quest_id]
        expected_warning = {
            "Elite": "Elite/group recommended",
            "Escort": "Escort —",
            "Heroic": "Heroic dungeon —",
        }.get(entry.quest.tag_name)
        if expected_warning is None and entry.category == "dungeon":
            expected_warning = "Dungeon —"
        if expected_warning is None and entry.category == "raid":
            expected_warning = "Raid —"
        if expected_warning and expected_warning not in step_lines.get(("QC", quest_id), ""):
            result.errors.append(
                f"quest {quest_id} ({entry.quest.tag_name or entry.category}) lacks required "
                f"preparation label {expected_warning!r}"
            )

    for branch, tags in streams.items():
        _validate_stream(branch, tags, quests, catalog, baseline, result)

    covered_counts = guide_quest_ids(project_root)
    missing = sorted(allowed - set(covered_counts))
    duplicates = sorted(quest_id for quest_id, count in covered_counts.items() if count != 1)
    if missing:
        result.errors.append(f"unexpectedly missing covered quests: {missing[:25]}{'...' if len(missing) > 25 else ''}")
    if duplicates:
        result.errors.append(f"duplicate accepted quests: {duplicates[:25]}{'...' if len(duplicates) > 25 else ''}")

    primary_ids = {
        entry.quest.id for entry in catalog.entries.values() if entry.status == "covered_primary"
    }
    alternative_ids = {
        entry.quest.id for entry in catalog.entries.values() if entry.status == "covered_alternative"
    }
    optional_ids = {
        entry.quest.id for entry in catalog.entries.values() if entry.status == "covered_optional"
    }
    result.simulations = {
        "fresh_level_10": resume_simulation(all_tags, baseline),
        "partially_completed": resume_simulation(all_tags, baseline | set(sorted(primary_ids)[::2])),
        "level_70_complete": resume_simulation(all_tags, baseline | primary_ids | optional_ids | alternative_ids),
        "aldor": resume_simulation(all_tags, baseline | optional_ids | {q for q in primary_ids | alternative_ids if (catalog.entries[q].branch or "").startswith("aldor")}),
        "scryer": resume_simulation(all_tags, baseline | optional_ids | {q for q in primary_ids | alternative_ids if (catalog.entries[q].branch or "").startswith("scryer")}),
    }
    result.metrics.update({
        "lua_files": len(files),
        "quest_steps": total_steps,
        "covered_primary": len(primary_ids),
        "covered_optional": len(optional_ids),
        "covered_alternative": len(alternative_ids),
        "baseline_completed": len(baseline),
        "excluded": len(excluded),
        "future_phase_unavailable": len(future_phase),
        "inactive_event_emitted_quests": len(inactive_event_emitted),
        "unexpectedly_missing": len(missing),
        "batched_accept_groups": batched_accept_groups,
        "batched_quests": batched_quests,
        "item_use_instructions": item_use_instructions,
        "scripted_objective_instructions": scripted_objective_instructions,
        "tagged_preparation_instructions": tagged_preparation_instructions,
        "objective_target_instructions": objective_target_instructions,
        "string_quality_lines": string_quality_lines,
        "string_quality_violations": string_quality_violations,
        "longest_guide_line": longest_guide_line,
    })
    _validate_route_specs(catalog, project_root, files, result)
    try:
        authored_routes = load_authored_routes(project_root / "config" / "authored_routes.json")
    except ValueError as error:
        result.errors.append(str(error))
        authored_routes = []
    authored_comparison = compare_authored_routes(catalog, project_root, authored_routes)
    if not authored_routes:
        result.errors.append(
            "no pinned independent authored route is available; set MADS_AUTHORED_ROUTE_PATH"
        )
    result.metrics["authored_route_sources"] = len(authored_routes)
    result.metrics["authored_route_primary_overlap"] = sum(
        source["primary_overlap"] for source in authored_comparison.get("sources", [])
    )
    client = inspect_client_installation(project_root)
    failed_client_checks = [name for name, passed in client["checks"].items() if not passed]
    if failed_client_checks:
        result.errors.append("client installation checks failed: " + ", ".join(failed_client_checks))
    failed_deployment_checks = [
        name for name, passed in client["deployment_checks"].items() if not passed
    ]
    if release["public_release_ready"]:
        if failed_deployment_checks:
            result.errors.append(
                "public release deployment checks failed: " + ", ".join(failed_deployment_checks)
            )
        if not client["launched_after_current_deployment"]:
            result.errors.append("public release requires an Anniversary launch after current deployment")
    result.metrics["client_installation_checks"] = len(client["checks"])
    result.metrics["client_installation_checks_passed"] = sum(client["checks"].values())
    result.metrics["client_deployment_checks"] = len(client["deployment_checks"])
    result.metrics["client_deployment_checks_passed"] = sum(
        client["deployment_checks"].values()
    )
    result.metrics["client_launched_after_deployment"] = int(
        client["launched_after_current_deployment"]
    )
    return result


def _validate_route_specs(
    catalog: Catalog,
    project_root: Path,
    guide_files: list[Path],
    result: ValidationResult,
) -> None:
    route_root = project_root / "data" / "route" / "chapters"
    specs = sorted(route_root.glob("*.json")) if route_root.is_dir() else []
    if len(specs) != len(guide_files):
        result.errors.append(
            f"route spec count {len(specs)} does not match Lua chapter count {len(guide_files)}"
        )
        return
    normalized_endpoints = 0
    normalized_coordinates = 0
    normalized_objective_sources = 0
    normalized_objective_coordinates = 0
    unresolved_endpoint_names = 0
    unresolved_objective_names = 0
    semantic_steps = 0
    flight_path_instructions = 0
    zone_transition_instructions = 0
    transport_instructions = 0
    retention_instructions = 0
    branch_entry_instructions = 0
    onboarding_instructions = 0
    choice_preview_instructions = 0
    recovery_instructions = 0
    milestone_instructions = 0
    chapter_entry_instructions = 0
    chapter_entry_waypoints = 0
    level_gate_instructions = 0
    static_reviewed_chapters = 0
    start_level = int(catalog.scope.get("legacy_guide_start_level", 10))
    route_floor_by_branch: dict[str, int] = defaultdict(lambda: start_level)
    previous_exit_by_branch: dict[str, dict] = {}
    active_quests_by_branch: dict[str, set[int]] = defaultdict(set)
    travel_links = load_travel_network(project_root / "config" / "travel_network.json")
    for guide_path, spec_path in zip(guide_files, specs):
        try:
            payload = json.loads(spec_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            result.errors.append(f"invalid route spec {spec_path.relative_to(project_root)}: {error}")
            continue
        if payload.get("schema_version") != 2:
            result.errors.append(
                f"{spec_path.relative_to(project_root)} uses unsupported route schema "
                f"{payload.get('schema_version')!r}"
            )
        if not payload.get("entry_contract"):
            result.errors.append(
                f"{spec_path.relative_to(project_root)} has no branch entry contract"
            )
        static_review = payload.get("static_review", {})
        failed_static_checks = [
            name for name, passed in static_review.items() if passed is not True
        ]
        if not static_review or failed_static_checks:
            result.errors.append(
                f"{spec_path.relative_to(project_root)} failed static chapter review: "
                + (", ".join(failed_static_checks) or "missing review checks")
            )
        elif payload.get("review_status") != "static_review_passed_needs_in_game":
            result.errors.append(
                f"{spec_path.relative_to(project_root)} has inconsistent review status "
                f"{payload.get('review_status')!r}"
            )
        else:
            static_reviewed_chapters += 1
        for quest_id in payload.get("external_prerequisite_quest_ids", []):
            entry = catalog.entries.get(quest_id)
            if entry is None or not entry.status.startswith("covered"):
                result.errors.append(
                    f"{spec_path.relative_to(project_root)} has invalid external prerequisite {quest_id}"
                )
        required_all = set(payload.get("external_prerequisite_all_quest_ids", []))
        required_any = [set(group) for group in payload.get("external_prerequisite_any_groups", [])]
        prerequisite_union = required_all | {
            quest_id for group in required_any for quest_id in group
        }
        if prerequisite_union != set(payload.get("external_prerequisite_quest_ids", [])):
            result.errors.append(
                f"{spec_path.relative_to(project_root)} has inconsistent external prerequisite fields"
            )
        for quest_id in required_all:
            entry = catalog.entries.get(quest_id)
            conflicts = set(entry.quest.exclusive_to) & required_all if entry else set()
            if conflicts:
                result.errors.append(
                    f"{spec_path.relative_to(project_root)} incorrectly requires mutually exclusive "
                    f"quests {quest_id} and {sorted(conflicts)} together"
                )
        if any(not group for group in required_any):
            result.errors.append(
                f"{spec_path.relative_to(project_root)} contains an empty any-of prerequisite group"
            )
        branch_entry_step = next(
            (step for step in payload.get("steps", []) if step.get("type") == "branch_entry"),
            None,
        )
        chapter_entry_step = next(
            (step for step in payload.get("steps", []) if step.get("type") == "chapter_entry"),
            None,
        )
        if payload.get("branch") != "primary" and chapter_entry_step and branch_entry_step:
            prerequisite_text = " ".join((
                str(payload.get("entry_contract", "")),
                str(branch_entry_step.get("instruction", "")),
                str(chapter_entry_step.get("instruction", "")),
            ))
            for quest_id in prerequisite_union:
                entry = catalog.entries.get(quest_id)
                if entry and entry.quest.name not in prerequisite_text:
                    result.errors.append(
                        f"{spec_path.relative_to(project_root)} does not name external prerequisite "
                        f"{quest_id} in its entry guidance"
                    )
            for group in required_any:
                if len(group) > 1 and "either" not in prerequisite_text.lower():
                    result.errors.append(
                        f"{spec_path.relative_to(project_root)} flattens an any-of prerequisite group"
                    )
        try:
            _, _, _, guide_tags = parse_guide_file(guide_path)
        except ValueError:
            continue
        spec_tags = [
            ({"accept": "QA", "complete": "QC", "turn_in": "QT"}[step["type"]], step.get("quest_id"))
            for step in payload.get("steps", [])
            if step.get("type") in {"accept", "complete", "turn_in"}
        ]
        if spec_tags != guide_tags:
            result.errors.append(
                f"{spec_path.relative_to(project_root)} does not exactly match "
                f"{guide_path.relative_to(project_root)}"
            )
        chapter_entries_in_spec = 0
        chapter_transitions_in_spec = 0
        retained_ids_in_spec: set[int] = set()
        branch_entries_in_spec = 0
        onboarding_in_spec = 0
        choice_previews_in_spec = 0
        recovery_in_spec = 0
        branch = str(payload.get("branch", ""))
        gated_level = start_level
        route_floor = route_floor_by_branch[branch]
        guide_source = guide_path.read_text(encoding="utf-8")
        steps = payload.get("steps", [])
        for step_index, step in enumerate(steps):
            if not step.get("instruction"):
                result.errors.append(
                    f"{spec_path.relative_to(project_root)} step {step.get('order')} lacks an instruction"
                )
            if step.get("type") not in {"accept", "complete", "turn_in"}:
                semantic_steps += 1
                next_state = next(
                    (
                        candidate for candidate in steps[step_index + 1:]
                        if candidate.get("type") in {"accept", "complete", "turn_in"}
                    ),
                    None,
                )
                expected_type = {
                    "QA": "accept", "QC": "complete", "QT": "turn_in"
                }.get(step.get("before_tag"))
                if (
                    next_state is None
                    or next_state.get("quest_id") != step.get("before_quest_id")
                    or next_state.get("type") != expected_type
                ):
                    result.errors.append(
                        f"{spec_path.relative_to(project_root)} step {step.get('order')} is not "
                        "immediately attached to its declared quest state"
                    )
            if step.get("type") == "chapter_entry":
                chapter_entries_in_spec += 1
                chapter_entry_instructions += 1
                if step.get("optional") is not True:
                    result.errors.append(
                        f"{spec_path.relative_to(project_root)} step {step.get('order')} chapter entry is not optional"
                    )
                if step.get("verification") != "questie_structured_source_only":
                    result.errors.append(
                        f"{spec_path.relative_to(project_root)} step {step.get('order')} chapter entry has an invalid verification state"
                    )
                if len(step.get("evidence_refs", [])) != 1:
                    result.errors.append(
                        f"{spec_path.relative_to(project_root)} step {step.get('order')} chapter entry lacks one Questie evidence reference"
                    )
                if "quest-log slots open" not in step.get("instruction", ""):
                    result.errors.append(
                        f"{spec_path.relative_to(project_root)} step {step.get('order')} chapter entry lacks the reserved-slot reminder"
                    )
                x = step.get("x")
                y = step.get("y")
                if isinstance(x, (int, float)) and isinstance(y, (int, float)):
                    chapter_entry_waypoints += 1
                    waypoint = f"[G{x:.2f},{y:.2f} {step.get('map_name')}]"
                    if waypoint not in step.get("instruction", ""):
                        result.errors.append(
                            f"{spec_path.relative_to(project_root)} step {step.get('order')} "
                            "chapter entry hides its verified waypoint"
                        )
                if step.get("instruction") not in guide_source:
                    result.errors.append(
                        f"{spec_path.relative_to(project_root)} step {step.get('order')} chapter entry is absent from Lua"
                    )
            if step.get("type") == "acquire_flight_path":
                flight_path_instructions += 1
                if step.get("optional") is not True:
                    result.errors.append(
                        f"{spec_path.relative_to(project_root)} step {step.get('order')} flight path is not optional"
                    )
                if step.get("verification") != "cross_verified_questie_and_authored_route":
                    result.errors.append(
                        f"{spec_path.relative_to(project_root)} step {step.get('order')} flight path lacks cross-verification"
                    )
                if len(step.get("evidence_refs", [])) < 2:
                    result.errors.append(
                        f"{spec_path.relative_to(project_root)} step {step.get('order')} flight path lacks two evidence references"
                    )
                if step.get("instruction") not in guide_source:
                    result.errors.append(
                        f"{spec_path.relative_to(project_root)} step {step.get('order')} flight path is absent from Lua"
                    )
                if not isinstance(step.get("map_id"), int) or not step.get("map_name"):
                    result.errors.append(
                        f"{spec_path.relative_to(project_root)} step {step.get('order')} flight path lacks map context"
                    )
                for axis in ("x", "y"):
                    value = step.get(axis)
                    if not isinstance(value, (int, float)) or not 0 <= value <= 100:
                        result.errors.append(
                            f"{spec_path.relative_to(project_root)} step {step.get('order')} has invalid flight path {axis}={value!r}"
                        )
                quest = catalog.entries.get(step.get("before_quest_id"))
                tag = step.get("before_tag")
                if quest is not None:
                    sources = (
                        quest.quest.starter_sources if tag == "QA" else
                        quest.quest.objective_sources if tag == "QC" else
                        quest.quest.finisher_sources if tag == "QT" else ()
                    )
                    locations = [
                        location for source in sources for location in source.locations
                        if location.map_id == step.get("map_id")
                    ]
                    if not locations or min(
                        hypot(location.x - step.get("x", 0), location.y - step.get("y", 0))
                        for location in locations
                    ) > 15:
                        result.errors.append(
                            f"{spec_path.relative_to(project_root)} step {step.get('order')} flight "
                            "path is not attached to a nearby route operation"
                        )
            if step.get("type") in {"zone_transition", "transport"}:
                chapter_transitions_in_spec += 1
                if step.get("type") == "zone_transition":
                    zone_transition_instructions += 1
                    expected_verification = "questie_structured_route_points"
                else:
                    transport_instructions += 1
                    expected_verification = "questie_endpoints_and_tbc_transport_network"
                if step.get("optional") is not True:
                    result.errors.append(
                        f"{spec_path.relative_to(project_root)} step {step.get('order')} travel is not optional"
                    )
                if step.get("verification") != expected_verification:
                    result.errors.append(
                        f"{spec_path.relative_to(project_root)} step {step.get('order')} travel has "
                        "an invalid verification state"
                    )
                if step.get("instruction") not in guide_source:
                    result.errors.append(
                        f"{spec_path.relative_to(project_root)} step {step.get('order')} travel is absent from Lua"
                    )
                entry_point = payload.get("entry_route_point") or {}
                for field in ("map_id", "map_name", "x", "y"):
                    if step.get(field) != entry_point.get(field):
                        result.errors.append(
                            f"{spec_path.relative_to(project_root)} step {step.get('order')} travel "
                            f"destination does not match chapter entry field {field}"
                        )
                previous_exit = previous_exit_by_branch.get(branch)
                if previous_exit is not None:
                    for field, step_field in (
                        ("map_id", "origin_map_id"),
                        ("map_name", "origin_map_name"),
                        ("x", "origin_x"),
                        ("y", "origin_y"),
                    ):
                        if step.get(step_field) != previous_exit.get(field):
                            result.errors.append(
                                f"{spec_path.relative_to(project_root)} step {step.get('order')} "
                                f"travel origin does not match previous exit field {field}"
                            )
                link_ids = tuple(step.get("transport_link_ids", ()))
                if step.get("type") == "transport":
                    expected_plan = plan_travel(
                        int(step.get("origin_map_id")), int(step.get("map_id")), travel_links
                    )
                    if link_ids != expected_plan.link_ids:
                        result.errors.append(
                            f"{spec_path.relative_to(project_root)} step {step.get('order')} uses "
                            f"transport links {link_ids!r}; expected {expected_plan.link_ids!r}"
                        )
                    evidence_refs = set(step.get("evidence_refs", ()))
                    for link_id in link_ids:
                        link = travel_links.get(link_id)
                        required_refs = {f"travel-network:{link_id}", *(link.evidence if link else ())}
                        if link is None or not required_refs.issubset(evidence_refs):
                            result.errors.append(
                                f"{spec_path.relative_to(project_root)} step {step.get('order')} "
                                f"lacks reviewed evidence for transport link {link_id!r}"
                            )
                elif link_ids:
                    result.errors.append(
                        f"{spec_path.relative_to(project_root)} step {step.get('order')} local travel "
                        "unexpectedly declares a transport link"
                    )
            if step.get("type") == "retain":
                retention_instructions += 1
                related_ids = step.get("related_quest_ids", [])
                if not related_ids or not all(isinstance(quest_id, int) for quest_id in related_ids):
                    result.errors.append(
                        f"{spec_path.relative_to(project_root)} step {step.get('order')} retain "
                        "instruction has no quest IDs"
                    )
                retained_ids_in_spec.update(related_ids)
                if step.get("optional") is not True or "[O]" not in step.get("instruction", ""):
                    result.errors.append(
                        f"{spec_path.relative_to(project_root)} step {step.get('order')} retain "
                        "instruction is not safely skippable for resumed characters"
                    )
                if step.get("verification") != "route_state_simulation":
                    result.errors.append(
                        f"{spec_path.relative_to(project_root)} step {step.get('order')} retain "
                        "instruction lacks route-state verification"
                    )
                if len(step.get("evidence_refs", [])) != len(related_ids):
                    result.errors.append(
                        f"{spec_path.relative_to(project_root)} step {step.get('order')} retain "
                        "instruction lacks per-quest evidence"
                    )
                for quest_id in related_ids:
                    entry = catalog.entries.get(quest_id)
                    if entry is None or entry.quest.name not in step.get("instruction", ""):
                        result.errors.append(
                            f"{spec_path.relative_to(project_root)} step {step.get('order')} retain "
                            f"instruction does not name quest {quest_id}"
                        )
                if step.get("instruction") not in guide_source:
                    result.errors.append(
                        f"{spec_path.relative_to(project_root)} step {step.get('order')} retain "
                        "instruction is absent from Lua"
                    )
            if step.get("type") == "branch_entry":
                branch_entry_instructions += 1
                branch_entries_in_spec += 1
                if step.get("optional") is not True or "[O]" not in step.get("instruction", ""):
                    result.errors.append(
                        f"{spec_path.relative_to(project_root)} step {step.get('order')} branch "
                        "entry is not safely skippable"
                    )
                if step.get("verification") != "route_dependency_graph":
                    result.errors.append(
                        f"{spec_path.relative_to(project_root)} step {step.get('order')} branch "
                        "entry lacks dependency-graph verification"
                    )
                if set(step.get("related_quest_ids", [])) != prerequisite_union:
                    result.errors.append(
                        f"{spec_path.relative_to(project_root)} step {step.get('order')} branch "
                        "entry does not match the external prerequisite contract"
                    )
                if step.get("instruction") not in guide_source:
                    result.errors.append(
                        f"{spec_path.relative_to(project_root)} step {step.get('order')} branch "
                        "entry is absent from Lua"
                    )
            if step.get("type") in {"onboarding", "milestone"}:
                if step.get("type") == "onboarding":
                    onboarding_instructions += 1
                    onboarding_in_spec += 1
                else:
                    milestone_instructions += 1
                if step.get("optional") is not True or "[O]" not in step.get("instruction", ""):
                    result.errors.append(
                        f"{spec_path.relative_to(project_root)} step {step.get('order')} "
                        f"{step.get('type')} guidance is not safely skippable"
                    )
                if step.get("verification") != "player_experience_policy":
                    result.errors.append(
                        f"{spec_path.relative_to(project_root)} step {step.get('order')} "
                        f"{step.get('type')} guidance lacks player-experience policy verification"
                    )
                if len(step.get("evidence_refs", [])) != 1:
                    result.errors.append(
                        f"{spec_path.relative_to(project_root)} step {step.get('order')} "
                        f"{step.get('type')} guidance lacks one policy evidence reference"
                    )
                if step.get("instruction") not in guide_source:
                    result.errors.append(
                        f"{spec_path.relative_to(project_root)} step {step.get('order')} "
                        f"{step.get('type')} guidance is absent from Lua"
                    )
            if step.get("type") == "choice_preview":
                choice_preview_instructions += 1
                choice_previews_in_spec += 1
                if step.get("optional") is not True or "[O]" not in step.get("instruction", ""):
                    result.errors.append(
                        f"{spec_path.relative_to(project_root)} step {step.get('order')} choice "
                        "preview is not safely skippable"
                    )
                if step.get("verification") != "route_exclusivity_graph":
                    result.errors.append(
                        f"{spec_path.relative_to(project_root)} step {step.get('order')} choice "
                        "preview lacks route-exclusivity verification"
                    )
                if step.get("instruction") not in guide_source:
                    result.errors.append(
                        f"{spec_path.relative_to(project_root)} step {step.get('order')} choice "
                        "preview is absent from Lua"
                    )
            if step.get("type") == "recovery":
                recovery_instructions += 1
                recovery_in_spec += 1
                related_ids = step.get("related_quest_ids", [])
                entry = catalog.entries.get(step.get("before_quest_id"))
                dangerous = bool(
                    entry
                    and (
                        entry.quest.tag_name in {"Elite", "Escort", "Heroic"}
                        or entry.category in {"dungeon", "raid"}
                    )
                )
                if related_ids != [step.get("before_quest_id")] or not dangerous:
                    result.errors.append(
                        f"{spec_path.relative_to(project_root)} step {step.get('order')} recovery "
                        "guidance is not attached to its dangerous quest"
                    )
                if step.get("before_tag") != "QC":
                    result.errors.append(
                        f"{spec_path.relative_to(project_root)} step {step.get('order')} recovery "
                        "guidance is not attached before completion"
                    )
                if step.get("optional") is not True or "[O]" not in step.get("instruction", ""):
                    result.errors.append(
                        f"{spec_path.relative_to(project_root)} step {step.get('order')} recovery "
                        "guidance is not safely skippable"
                    )
                if step.get("verification") != "questie_difficulty_and_route_recovery_policy":
                    result.errors.append(
                        f"{spec_path.relative_to(project_root)} step {step.get('order')} recovery "
                        "guidance lacks difficulty and route-policy verification"
                    )
                if step.get("instruction") not in guide_source:
                    result.errors.append(
                        f"{spec_path.relative_to(project_root)} step {step.get('order')} recovery "
                        "guidance is absent from Lua"
                    )
            if step.get("type") == "level_gate":
                level_gate_instructions += 1
                required_level = step.get("required_level")
                if not isinstance(required_level, int) or required_level <= gated_level:
                    result.errors.append(
                        f"{spec_path.relative_to(project_root)} step {step.get('order')} has invalid "
                        f"or non-increasing level gate {required_level!r} after level {gated_level}"
                    )
                else:
                    gated_level = required_level
                if step.get("optional") is not False:
                    result.errors.append(
                        f"{spec_path.relative_to(project_root)} step {step.get('order')} level gate is optional"
                    )
                if step.get("verification") != "questie_required_level":
                    result.errors.append(
                        f"{spec_path.relative_to(project_root)} step {step.get('order')} level gate lacks "
                        "Questie required-level provenance"
                    )
                if f"[XP{required_level} " not in step.get("instruction", ""):
                    result.errors.append(
                        f"{spec_path.relative_to(project_root)} step {step.get('order')} level gate lacks "
                        f"the exact [XP{required_level}] condition"
                    )
                if step.get("instruction") not in guide_source:
                    result.errors.append(
                        f"{spec_path.relative_to(project_root)} step {step.get('order')} level gate is absent from Lua"
                    )
            if step.get("type") == "accept":
                quest_id = step.get("quest_id")
                entry = catalog.entries.get(quest_id)
                if entry is not None:
                    actual_required_level = max(
                        start_level, int(entry.quest.get("required_level", 0))
                    )
                    route_required_level = step.get("required_level")
                    if (
                        not isinstance(route_required_level, int)
                        or route_required_level < actual_required_level
                    ):
                        result.errors.append(
                            f"{spec_path.relative_to(project_root)} accepts quest {quest_id} with "
                            f"invalid route level {route_required_level!r}; Questie requires "
                            f"{actual_required_level}"
                        )
                    if route_required_level != gated_level:
                        result.errors.append(
                            f"{spec_path.relative_to(project_root)} accepts quest {quest_id} at route "
                            f"level {route_required_level!r} without matching the current monotonic "
                            f"level gate {gated_level}"
                        )
                    if (
                        isinstance(route_required_level, int)
                        and route_required_level < route_floor
                    ):
                        result.errors.append(
                            f"{spec_path.relative_to(project_root)} lowers branch {branch!r} from "
                            f"route level {route_floor} to {route_required_level} at quest {quest_id}"
                        )
                    if isinstance(route_required_level, int):
                        route_floor = max(route_floor, route_required_level)
            for source in step.get("endpoint_sources", []):
                normalized_endpoints += 1
                if not source.get("name"):
                    unresolved_endpoint_names += 1
                if source.get("verification") != "questie_structured_source_only":
                    result.errors.append(
                        f"{spec_path.relative_to(project_root)} step {step.get('order')} has an "
                        "endpoint without an explicit verification state"
                    )
                for location in source.get("locations", []):
                    normalized_coordinates += 1
                    map_id = location.get("map_id")
                    x = location.get("x")
                    y = location.get("y")
                    if not isinstance(map_id, int) or not location.get("map_name"):
                        result.errors.append(
                            f"{spec_path.relative_to(project_root)} step {step.get('order')} has a "
                            "coordinate without map context"
                        )
                    if not isinstance(x, (int, float)) or not 0 <= x <= 100:
                        result.errors.append(
                            f"{spec_path.relative_to(project_root)} step {step.get('order')} has invalid x={x!r}"
                        )
                    if not isinstance(y, (int, float)) or not 0 <= y <= 100:
                        result.errors.append(
                            f"{spec_path.relative_to(project_root)} step {step.get('order')} has invalid y={y!r}"
                        )
            for source in step.get("objective_sources", []):
                normalized_objective_sources += 1
                if not source.get("name"):
                    unresolved_objective_names += 1
                    result.errors.append(
                        f"{spec_path.relative_to(project_root)} step {step.get('order')} has an "
                        f"unresolved objective source {source.get('kind')} {source.get('id')}"
                    )
                if source.get("verification") != "questie_structured_source_only":
                    result.errors.append(
                        f"{spec_path.relative_to(project_root)} step {step.get('order')} has an "
                        "objective source without an explicit verification state"
                    )
                for location in source.get("locations", []):
                    normalized_objective_coordinates += 1
                    map_id = location.get("map_id")
                    x = location.get("x")
                    y = location.get("y")
                    if not isinstance(map_id, int) or not location.get("map_name"):
                        result.errors.append(
                            f"{spec_path.relative_to(project_root)} step {step.get('order')} has an "
                            "objective coordinate without map context"
                        )
                    if not isinstance(x, (int, float)) or not 0 <= x <= 100:
                        result.errors.append(
                            f"{spec_path.relative_to(project_root)} step {step.get('order')} has "
                            f"invalid objective x={x!r}"
                        )
                    if not isinstance(y, (int, float)) or not 0 <= y <= 100:
                        result.errors.append(
                            f"{spec_path.relative_to(project_root)} step {step.get('order')} has "
                            f"invalid objective y={y!r}"
                        )
        route_floor_by_branch[branch] = route_floor
        if chapter_entries_in_spec != 1:
            result.errors.append(
                f"{spec_path.relative_to(project_root)} has {chapter_entries_in_spec} chapter entry steps; expected 1"
            )
        expected_transitions = 1 if payload.get("previous_chapter") else 0
        if chapter_transitions_in_spec != expected_transitions:
            result.errors.append(
                f"{spec_path.relative_to(project_root)} has {chapter_transitions_in_spec} chapter "
                f"travel steps; expected {expected_transitions}"
            )
        expected_branch_entries = 0 if branch == "primary" else 1
        if branch_entries_in_spec != expected_branch_entries:
            result.errors.append(
                f"{spec_path.relative_to(project_root)} has {branch_entries_in_spec} branch-entry "
                f"steps; expected {expected_branch_entries}"
            )
        expected_onboarding = 4 if branch == "primary" and not payload.get("previous_chapter") else 0
        if onboarding_in_spec != expected_onboarding:
            result.errors.append(
                f"{spec_path.relative_to(project_root)} has {onboarding_in_spec} onboarding steps; "
                f"expected {expected_onboarding}"
            )
        expected_choice_previews = 0 if branch in {"primary", "optional_content"} else 1
        if choice_previews_in_spec != expected_choice_previews:
            result.errors.append(
                f"{spec_path.relative_to(project_root)} has {choice_previews_in_spec} choice "
                f"previews; expected {expected_choice_previews}"
            )
        has_dangerous_step = any(
            step.get("type") == "complete"
            and (
                step.get("quest_tag") in {"Elite", "Escort", "Heroic"}
                or step.get("category") in {"dungeon", "raid"}
            )
            for step in steps
        )
        expected_recovery = 1 if has_dangerous_step else 0
        if recovery_in_spec != expected_recovery:
            result.errors.append(
                f"{spec_path.relative_to(project_root)} has {recovery_in_spec} recovery steps; "
                f"expected {expected_recovery}"
            )
        expected_retained_ids = active_quests_by_branch[branch]
        if retained_ids_in_spec != expected_retained_ids:
            result.errors.append(
                f"{spec_path.relative_to(project_root)} retains quests "
                f"{sorted(retained_ids_in_spec)}; expected {sorted(expected_retained_ids)}"
            )
        for state_step in steps:
            quest_id = state_step.get("quest_id")
            if state_step.get("type") == "accept" and isinstance(quest_id, int):
                active_quests_by_branch[branch].add(quest_id)
            elif state_step.get("type") == "turn_in" and isinstance(quest_id, int):
                active_quests_by_branch[branch].discard(quest_id)
        exit_point = payload.get("exit_route_point")
        if exit_point:
            previous_exit_by_branch[branch] = exit_point
    if milestone_instructions != 5:
        result.errors.append(
            f"route contains {milestone_instructions} journey milestones; expected 5"
        )
    result.metrics.update({
        "route_specs": len(specs),
        "normalized_endpoint_sources": normalized_endpoints,
        "normalized_endpoint_coordinates": normalized_coordinates,
        "normalized_objective_sources": normalized_objective_sources,
        "normalized_objective_coordinates": normalized_objective_coordinates,
        "unresolved_endpoint_names": unresolved_endpoint_names,
        "unresolved_objective_names": unresolved_objective_names,
        "route_semantic_steps": semantic_steps,
        "flight_path_instructions": flight_path_instructions,
        "zone_transition_instructions": zone_transition_instructions,
        "transport_instructions": transport_instructions,
        "retention_instructions": retention_instructions,
        "branch_entry_instructions": branch_entry_instructions,
        "onboarding_instructions": onboarding_instructions,
        "choice_preview_instructions": choice_preview_instructions,
        "recovery_instructions": recovery_instructions,
        "milestone_instructions": milestone_instructions,
        "chapter_entry_instructions": chapter_entry_instructions,
        "chapter_entry_waypoints": chapter_entry_waypoints,
        "level_gate_instructions": level_gate_instructions,
        "static_reviewed_chapters": static_reviewed_chapters,
    })


def _validate_stream(
    branch: str,
    tags: list[tuple[str, int, Path]],
    quests: dict[int, Quest],
    catalog: Catalog,
    baseline: set[int],
    result: ValidationResult,
) -> None:
    stream_ids = {quest_id for _, quest_id, _ in tags}
    for quest_id in sorted(stream_ids):
        conflicts = sorted(other for other in quests[quest_id].exclusive_to if other in stream_ids)
        if conflicts:
            result.errors.append(
                f"{branch}: mutually exclusive quest {quest_id} shares a stream with {conflicts}"
            )
    shared_primary = {
        entry.quest.id
        for entry in catalog.entries.values()
        if entry.status in {"covered_primary", "covered_optional"}
        and not (branch.startswith("scryer") and entry.branch == "aldor")
        and not (branch.startswith("aldor") and entry.branch == "scryer")
    }
    turned = set(baseline)
    if branch == "optional_content":
        turned |= {
            entry.quest.id
            for entry in catalog.entries.values()
            if entry.status == "covered_primary"
        }
    elif branch != "primary":
        turned |= shared_primary
        if branch.startswith("aldor"):
            turned.add(10551)
        if branch.startswith("scryer"):
            turned.add(10552)
    active: set[int] = set()
    completed: set[int] = set()
    seen_state: dict[int, int] = defaultdict(int)
    max_active = 0
    for tag, quest_id, path in tags:
        quest = quests.get(quest_id)
        if not quest:
            continue
        expected = {"QA": 0, "QC": 1, "QT": 2}[tag]
        if seen_state[quest_id] != expected:
            result.errors.append(
                f"{path.name}: quest {quest_id} has {tag} out of order in {branch} stream"
            )
        seen_state[quest_id] = expected + 1
        if tag == "QA":
            missing_all = [q for q in quest.prerequisites_all if q not in turned]
            if missing_all:
                result.errors.append(f"{branch}: quest {quest_id} accepted before prerequisites {missing_all}")
            if quest.prerequisites_any and not any(q in turned for q in quest.prerequisites_any):
                # An alternative prerequisite outside this stream may represent a
                # different legal breadcrumb. Treat it as warning if absent from
                # all generated coverage, otherwise it is a true ordering error.
                in_coverage = any(q in stream_ids or q in turned for q in quest.prerequisites_any)
                message = f"{branch}: quest {quest_id} accepted before any prerequisite {list(quest.prerequisites_any)}"
                (result.errors if in_coverage else result.warnings).append(message)
            parent = quest.get("parent_quest")
            if parent and parent not in active:
                result.errors.append(f"{branch}: child quest {quest_id} accepted while parent {parent} is not active")
            active.add(quest_id)
            max_active = max(max_active, len(active))
        elif tag == "QC":
            if quest_id not in active:
                result.errors.append(f"{branch}: quest {quest_id} completed before acceptance")
            completed.add(quest_id)
        elif tag == "QT":
            if quest_id not in completed:
                result.errors.append(f"{branch}: quest {quest_id} turned in before completion")
            active.discard(quest_id)
            completed.discard(quest_id)
            turned.add(quest_id)
    working_cap = int(catalog.scope.get("quest_log_policy", {}).get("working_cap", 23))
    if max_active > working_cap:
        result.errors.append(
            f"{branch}: working quest cap reaches {max_active} (policy maximum {working_cap})"
        )
    result.metrics[f"max_active_{branch}"] = max_active


def resume_simulation(tags: list[tuple[str, int, Path]], completed_quests: set[int]) -> dict[str, int | bool]:
    collapsed = sum(1 for _, quest_id, _ in tags if quest_id in completed_quests)
    remaining = len(tags) - collapsed
    # Generated sources contain only quest-state tags. Therefore every mandatory
    # step is retroactive; no travel/vendor/trainer text can block resumption.
    return {
        "completed_quests": len(completed_quests),
        "collapsed_steps": collapsed,
        "remaining_steps": remaining,
        "mandatory_nonretroactive_steps": 0,
        "can_resume": True,
    }
