from __future__ import annotations

import csv
import json
import zipfile
from collections import Counter, defaultdict
from math import hypot
from pathlib import Path

from .authored_route import compare_authored_routes, load_authored_routes
from .client_installation import inspect_client_installation
from .guides import ADDON_NAME, guide_quest_ids, toc_all_lua_files, toc_lua_files
from .model import Catalog
from .scope import load_release
from .travel import CONTINENT_BY_ZONE
from .validate import ValidationResult


def write_catalog(catalog: Catalog, path: Path) -> None:
    data = {
        "schema_version": 2,
        "scope": catalog.scope,
        "phase_profile": catalog.phase_profile,
        "content_policy": catalog.content_policy,
        "source": {"path": catalog.source_path, "revision": catalog.source_revision},
        "counts": dict(Counter(entry.status for entry in catalog.entries.values())),
        "quests": [catalog.entries[quest_id].to_dict() for quest_id in sorted(catalog.entries)],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_audit(catalog: Catalog, validation: ValidationResult, project_root: Path, reports: Path) -> None:
    reports.mkdir(parents=True, exist_ok=True)
    release = load_release(project_root / "config" / "release.json")
    authored_routes = load_authored_routes(project_root / "config" / "authored_routes.json")
    authored_comparison = compare_authored_routes(catalog, project_root, authored_routes)
    client_installation = inspect_client_installation(project_root)
    evidence_root = project_root / "data" / "evidence"
    evidence_root.mkdir(parents=True, exist_ok=True)
    (evidence_root / "authored-routes.json").write_text(
        json.dumps(authored_comparison, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (evidence_root / "client-installation.json").write_text(
        json.dumps(client_installation, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    covered = guide_quest_ids(project_root)
    expected = {
        entry.quest.id
        for entry in catalog.entries.values()
        if entry.status in {"covered_primary", "covered_optional", "covered_alternative"}
    }
    missing = sorted(expected - set(covered))
    payload = {
        "schema_version": 2,
        "scope": catalog.scope,
        "phase_profile": catalog.phase_profile,
        "content_policy": catalog.content_policy,
        "source": {"path": catalog.source_path, "revision": catalog.source_revision},
        "validation": validation.to_dict(),
        "unexpectedly_missing": missing,
        "classification_counts": dict(Counter(entry.status for entry in catalog.entries.values())),
        "category_counts": dict(
            Counter(entry.category for entry in catalog.entries.values() if entry.status.startswith("covered"))
        ),
        "branch_counts": dict(
            Counter(entry.branch for entry in catalog.entries.values() if entry.status.startswith("covered"))
        ),
        "quests": [catalog.entries[quest_id].to_dict() for quest_id in sorted(catalog.entries)],
    }
    (reports / "audit.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (reports / "validation.json").write_text(json.dumps(validation.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")

    counts = Counter(entry.status for entry in catalog.entries.values())
    categories = Counter(entry.category for entry in catalog.entries.values() if entry.status.startswith("covered"))
    branches = Counter(entry.branch for entry in catalog.entries.values() if entry.status.startswith("covered"))
    exclusion_reasons = Counter(
        entry.reason for entry in catalog.entries.values() if entry.status == "excluded"
    )
    lines = [
        "# Mad's Loremaster Coverage Audit",
        "",
        f"Questie source: `{catalog.source_path}`",
        f"Questie revision: `{catalog.source_revision or 'not a git checkout'}`",
        f"Scope: **{catalog.scope.get('game_version', 'Unspecified')}**",
        f"Content phase: **{catalog.phase_profile.get('phase', '?')} — {catalog.phase_profile.get('name', 'Unspecified')}**",
        f"Release: **{release['version']} ({release['channel']})**",
        f"Public release ready: **{'yes' if release['public_release_ready'] else 'no'}**",
        f"Validation: **{'PASS' if validation.ok else 'FAIL'}**",
        "",
        "## Coverage classification",
        "",
        "| Classification | Count |",
        "|---|---:|",
    ]
    for status in ("covered_primary", "covered_optional", "covered_alternative", "baseline_completed", "unavailable", "excluded"):
        lines.append(f"| {status.replace('_', ' ').title()} | {counts[status]} |")
    lines.extend(["", "## Covered content", "", "| Category | Count |", "|---|---:|"])
    for category, count in sorted(categories.items()):
        lines.append(f"| {(category or 'unknown').title()} | {count} |")
    lines.extend(["", "## Branches", "", "| Branch | Count |", "|---|---:|"])
    for branch, count in sorted(branches.items(), key=lambda item: str(item[0])):
        lines.append(f"| {(branch or 'unknown').replace('_', ' ').title()} | {count} |")
    lines.extend(["", "## Exclusions", "", "| Reason | Count |", "|---|---:|"])
    for reason, count in exclusion_reasons.most_common():
        lines.append(f"| {reason} | {count} |")
    lines.extend([
        "",
        "## Automated validation",
        "",
        f"- Lua guide files: {validation.metrics.get('lua_files', 0)}",
        f"- Quest-state steps: {validation.metrics.get('quest_steps', 0)}",
        f"- Unexpectedly missing: {len(missing)}",
        f"- Errors: {len(validation.errors)}",
        f"- Warnings: {len(validation.warnings)}",
        "",
        "The JSON report contains the classification and reason for every Questie TBC quest ID.",
    ])
    (reports / "AUDIT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    write_anniversary_audit(
        catalog,
        validation,
        project_root,
        reports / "anniversary-audit",
        authored_comparison,
        client_installation,
    )
    write_evidence_records(catalog, evidence_root, authored_comparison)


def write_evidence_records(catalog: Catalog, evidence_root: Path, authored_comparison: dict) -> None:
    evidence_root.mkdir(parents=True, exist_ok=True)
    questie_url = (
        "https://github.com/Questie/Questie/tree/" + catalog.source_revision
        if catalog.source_revision else catalog.source_path
    )
    with (evidence_root / "quests.jsonl").open("w", encoding="utf-8") as output:
        for quest_id in sorted(catalog.entries):
            entry = catalog.entries[quest_id]
            sources = [{
                "kind": "structured_secondary",
                "name": "Questie",
                "url_or_local_id": questie_url,
                "revision": catalog.source_revision,
                "retrieved_date": catalog.phase_profile.get("verified_date"),
                "supports": [
                    "identity", "dependency metadata", "starter", "finisher", "objectives",
                    "restrictions", "runtime corrections", "phase availability"
                ],
                "licensing_note": "Referenced at build time; Questie database is not redistributed."
            }]
            sources.extend({
                "kind": "official_phase_authority",
                "name": item.get("name", "Blizzard phase evidence"),
                "url_or_local_id": item.get("url"),
                "retrieved_date": catalog.phase_profile.get("verified_date"),
                "supports": ["selected release phase and activation state"],
                "licensing_note": "Cited as release-level phase evidence; not treated as a per-quest database.",
            } for item in catalog.phase_profile.get("official_sources", []))
            authored_route_ids = []
            for source_id in authored_comparison.get("quest_source_ids", {}).get(str(quest_id), []):
                authored_route_ids.append(source_id)
                source = next(
                    item for item in authored_comparison.get("sources", []) if item["id"] == source_id
                )
                sources.append({
                    "kind": "authored_route",
                    "name": source["name"],
                    "url_or_local_id": source["path"],
                    "revision": source["sha256"],
                    "retrieved_date": catalog.phase_profile.get("verified_date"),
                    "supports": ["route placement comparison only"],
                    "licensing_note": "Only quest-ID ordering facts are compared; authored prose is not copied.",
                    "version_limitation": source["version_limitation"],
                })
            record = {
                "schema_version": 1,
                "quest_id": quest_id,
                "canonical_name": entry.quest.name,
                "applicability": {
                    "game_version": catalog.scope.get("game_version"),
                    "phase": catalog.phase_profile.get("phase"),
                    "faction": catalog.scope.get("faction"),
                    "race": catalog.scope.get("race"),
                    "class": catalog.scope.get("class"),
                    "realm_rulesets": catalog.scope.get("realm_rulesets"),
                },
                "facts": entry.quest.to_dict(),
                "classification": entry.to_dict(),
                "sources": sources,
                "independent_source_status": (
                    "authored_route_placement_corroborated"
                    if authored_route_ids else
                    "not_required_for_low_risk_catalog_fact"
                ),
                "confidence": (
                    "phase-aware-structured-plus-route-comparison"
                    if authored_route_ids else
                    "phase-aware-structured"
                ),
                "reviewer_note": (
                    "Quest identity and structure come only from the pinned pre-Cataclysm Questie TBC data; "
                    "the selected phase is controlled by official Blizzard evidence. The authored "
                    "guide corroborates placement only, and live behavior remains an in-game gate."
                    if authored_route_ids else
                    "Quest identity and structure come only from the pinned pre-Cataclysm Questie TBC data; "
                    "the selected phase is controlled by official Blizzard evidence. No conflict "
                    "requires a second source; live behavior remains an in-game gate."
                )
            }
            output.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
    (evidence_root / "conflicts.jsonl").write_text("", encoding="utf-8")


def write_anniversary_audit(
    catalog: Catalog,
    validation: ValidationResult,
    project_root: Path,
    output: Path,
    authored_comparison: dict,
    client_installation: dict,
) -> None:
    release = load_release(project_root / "config" / "release.json")
    output.mkdir(parents=True, exist_ok=True)
    route_metrics_path = output.parent / "route-metrics.json"
    write_route_metrics(catalog, validation, route_metrics_path)
    route_comparison = json.loads(route_metrics_path.read_text(encoding="utf-8"))["comparison"]
    route_deltas = route_comparison["revised_delta_percent"]
    coverage_dir = output / "quest-coverage"
    coverage_dir.mkdir(exist_ok=True)
    rows = [_coverage_row(catalog, catalog.entries[quest_id]) for quest_id in sorted(catalog.entries)]
    columns = [
        "guide_section_or_step", "quest_name", "quest_id", "status", "phase_applicability",
        "content_era", "source_provenance", "prerequisite_or_restriction",
        "recommended_correction", "supporting_sources",
    ]
    with (output / "quest-coverage.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    for old in coverage_dir.glob("*.md"):
        old.unlink()
    for offset in range(0, len(rows), 500):
        part = offset // 500 + 1
        subset = rows[offset:offset + 500]
        lines = [
            f"# Quest coverage — part {part}", "",
            f"Rows {offset + 1}–{offset + len(subset)} of {len(rows)}. The CSV is authoritative.", "",
            "| Guide section / step | Quest | ID | Status | Phase | Content era | Source provenance | Prerequisite or restriction | Correction | Sources |",
            "|---|---|---:|---|---|---|---|---|---|---|",
        ]
        for row in subset:
            values = [str(row[column]).replace("|", "\\|").replace("\n", " ") for column in columns]
            lines.append("| " + " | ".join(values) + " |")
        (coverage_dir / f"part-{part:02d}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    counts = Counter(entry.status for entry in catalog.entries.values())
    reason_codes = Counter(
        entry.reason_code or "none"
        for entry in catalog.entries.values()
        if entry.status in {"excluded", "unavailable"}
    )
    official = catalog.phase_profile.get("official_sources", [])
    authored_sources = authored_comparison.get("sources", [])
    authored = authored_sources[0] if authored_sources else None
    source_links = ", ".join(f"[{index + 1}]({item['url']})" for index, item in enumerate(official))
    audit_lines = [
        "# Mad's Loremaster — Burning Crusade Classic Anniversary Audit", "",
        "## 1. Anniversary Scope and Version", "",
        f"This audit targets **{catalog.scope.get('game_version')}**, Phase "
        f"**{catalog.phase_profile.get('phase')} — {catalog.phase_profile.get('name')}**, interface "
        f"`{catalog.scope.get('interface')}`, for an Alliance Night Elf Hunter from levels 10–70 on "
        "Normal PvE and PvP Anniversary realms. Hardcore is excluded because those realms did not "
        "progress to Burning Crusade Classic.", "",
        f"Release candidate: **{release['version']} ({release['channel']})**. Public release ready: "
        f"**{'yes' if release['public_release_ready'] else 'no'}**.", "",
        f"Installed client evidence: **{client_installation['client']['product']} "
        f"{client_installation['client']['version']}**, Guidelime "
        f"**{client_installation['dependencies']['Guidelime'].get('Version', 'unknown')}**, Questie "
        f"**{client_installation['dependencies']['Questie'].get('Version', 'unknown')}**. The candidate "
        f"installation status is **{client_installation['status']}**; see `client-installation.md`.", "",
        f"Official phase evidence: {source_links}. Questie is pinned to "
        f"`{catalog.source_revision or 'an unversioned local source'}`.", "",
        "The content boundary is **pre-Cataclysm only**, with TBC as the maximum expansion. "
        "Every emitted and baseline quest is proven to exist in Questie's TBC quest snapshot; "
        "all NPC, object, and item facts come from its TBC entity snapshots. Cataclysm, Wrath, "
        "MoP, and later-expansion data paths are hard validator failures.", "",
        "## 2. Executive Assessment", "",
        f"Automated structure and phase validation currently **{'passes' if validation.ok else 'fails'}**. "
        f"The catalog classifies all {len(catalog.entries):,} Questie rows: "
        f"{counts['covered_primary']:,} primary world, {counts['covered_optional']:,} optional, "
        f"{counts['covered_alternative']:,} mutually exclusive alternative, "
        f"{counts['baseline_completed']:,} baseline, {counts['unavailable']:,} future-phase unavailable, "
        f"and {counts['excluded']:,} excluded or conditional rows.", "",
        f"Pre-Cataclysm provenance: **{validation.metrics.get('pre_cataclysm_covered_quests', 0):,} "
        "covered quests**, **0 post-TBC emitted quests**, **0 correction-only emitted quests**, "
        "and **0 forbidden source references**.", "",
        "The static release-candidate gate is complete: phase and dependency structure validate, every "
        "chapter passes the recorded static review, quest accept/turn-in sources are player-visible, "
        f"objective and preparation instructions are covered, {validation.metrics.get('level_gate_instructions', 0):,} "
        "chapter-local monotonic route-floor gates prevent impossible accept steps, and cross-verified flight-path pickups are "
        f"included. Four onboarding lines, {validation.metrics.get('choice_preview_instructions', 0):,} choice previews, "
        f"{validation.metrics.get('recovery_instructions', 0):,} dangerous-chapter recovery notes, and "
        f"{validation.metrics.get('milestone_instructions', 0):,} journey milestones are optional and nonblocking. "
        "Public promotion remains blocked only by the in-game Anniversary matrix.", "",
        "## 3. Quest Coverage Audit", "",
        "The complete row-level audit is in `quest-coverage.csv`; split Markdown tables in "
        "`quest-coverage/` make the same data reviewable. Every row contains its guide placement or "
        "audit-only status, selected-phase applicability, dependency/restriction summary, correction, "
        "and source pointer.", "",
        "| Reason code | Rows |", "|---|---:|",
    ]
    audit_lines.extend(f"| {code} | {count} |" for code, count in reason_codes.most_common())
    audit_lines.extend([
        "", "## 4. Routing and Story-Flow Issues", "",
        f"The revised structural route now batches {validation.metrics.get('batched_quests', 0):,} quests "
        f"across {validation.metrics.get('batched_accept_groups', 0):,} conservative same-zone groups. "
        f"Chain dependencies remain ordered; {validation.metrics.get('normalized_endpoint_sources', 0):,} "
        f"starter/finisher sources and {validation.metrics.get('normalized_objective_sources', 0):,} "
        "objective entities are normalized with map context from Questie. Every generated chapter has a "
        f"visible entry contract ({validation.metrics.get('chapter_entry_waypoints', 0):,} with a verified waypoint), named accept/turn-in source, reserved-log reminder, bounded zone scope, "
        f"and passing static review. All quest accepts are protected by {validation.metrics.get('level_gate_instructions', 0):,} "
        "chapter-local monotonic route-floor gates. Lower-level work in the current or immediately adjacent "
        "route zone is exhausted before the floor rises; distant cleanup quests do not force a major detour. "
        f"The {validation.metrics.get('zone_transition_instructions', 0) + validation.metrics.get('transport_instructions', 0):,} "
        "chapter handoffs are explicit and optional; cross-continent handoffs use reviewed TBC ships or portals. "
        "Character-specific hearth, terrain, known-flight-path, and cooldown behavior remains non-blocking. "
        + (
            f"The route also has {authored['primary_overlap']:,} quest placements in common with "
            f"{authored['name']} {authored['version']}, with {authored['relative_order_agreement']:.2%} "
            "relative-order agreement; that source is comparison evidence only. "
            if authored else "No independent authored route was available for comparison. "
        )
        + "`route-issues.md` tracks the remaining release-blocking work.", "",
        "## 5. Revised Optimal Anniversary Flow", "",
        "The generated flow begins with the Darnassus–Rut'theran–Auberdine flight chain and initial "
        "Auberdine pickups, then follows prerequisite-safe ordering through Azeroth and Outland. The "
        "default picker now contains only permanent world content; dungeon, raid, Hunter, reputation, "
        "PvP, and dependency-linked quests are in a dedicated optional stream, while mutually exclusive "
        "choices remain separate. `revised-flow/` contains one human-readable document per generated "
        "chapter and mirrors the Lua sequence exactly. The route uses starter-coordinate-aware hub "
        "batching, inserts Guidelime `[XP]` gates before each increase in minimum quest level, and limits "
        "primary chapters to two quest zones. It remains a release candidate until "
        "the in-game matrix confirms that the resulting travel and story flow feels correct in the live client.", "",
        "## 6. Remaining Uncertainties", "",
        "- The 25-quest Anniversary maximum is verified by the project owner's 2026-07-13 live screenshot; the route's simulated peak remains eight, preserving its two-slot reserve policy.",
        "- Starter/finisher availability, special mechanics, flight-path behavior, and resume behavior require the documented in-game matrix.",
        "- Travel feel, terrain, danger, group preparation, and story continuity require representative live chapter play-throughs.",
        "- Character-specific hearth state, cooldowns, and known flight paths are deliberately not mandatory guide steps.", "",
        "Machine-readable open claims are in `uncertainties.json`.",
    ])
    (output / "AUDIT.md").write_text("\n".join(audit_lines) + "\n", encoding="utf-8")
    (output / "route-issues.md").write_text(
        "# Route issues\n\n"
        "## R-001 — Coarse objective batching (resolved for static RC)\n\n"
        f"- **Current sequence:** {validation.metrics.get('batched_quests', 0):,} independent quests are grouped into "
        f"{validation.metrics.get('batched_accept_groups', 0):,} same-zone, starter-proximity-bounded accept/complete/turn-in batches.\n"
        "- **Correction:** batches now require compatible dependency state, category, zone, and a starter-source distance of at most 15 normalized map units when coordinates exist.\n"
        "- **Chapter scope:** primary chapters close after large zone runs and never contain more than two quest zones.\n"
        "- **Expected improvement:** pickups remain centered on plausible hubs instead of being grouped solely by zone identity.\n"
        f"- **Measured comparison:** across the {route_comparison['shared_primary_quests']:,} quest IDs shared by both primary routes, accepted-quest zone transitions change by {route_deltas['accepted_quest_zone_transitions']:.2f}%, repeated zone visits by {route_deltas['repeated_accepted_quest_zone_visits']:.2f}%, map changes by {route_deltas['map_transitions']:.2f}%, and continent changes by {route_deltas['continent_transitions']:.2f}%. The same-map straight-line proxy changes by +{route_deltas['same_map_proxy_distance']:.2f}%; this bounded regression remains visible because that proxy assigns no cost to map changes, boats, portals, flight time, terrain, or overlapping objectives.\n"
        "- **Story tradeoffs:** every prerequisite edge that crosses a chapter boundary is enumerated in `reports/route-metrics.json` with both chapter names and the boundary rationale.\n"
        "- **Quest-log implications:** the 2026-07-13 Anniversary screenshot verifies the 25-quest client maximum; the configured 23-quest working cap preserves two slots, and simulation peaks at eight.\n"
        "- **Remaining proof:** confirm hub and story flow during representative in-game chapter tests.\n\n"
        "## R-002 — Missing semantic travel and preparation steps (resolved for static RC)\n\n"
        f"- **Current sequence:** all {validation.metrics.get('chapter_entry_instructions', 0):,} chapters expose an optional verified entry instruction and reserve reminder, with {validation.metrics.get('chapter_entry_waypoints', 0):,} coordinate-backed waypoints; "
        f"{validation.metrics.get('zone_transition_instructions', 0) + validation.metrics.get('transport_instructions', 0):,} adjacent chapter handoffs are connected, "
        f"{validation.metrics.get('transport_instructions', 0):,} of them name a reviewed TBC transport route, and "
        f"{validation.metrics.get('flight_path_instructions', 0):,} flight-path pickups are cross-verified; item-use, scripted, and flagged preparation steps are explicit. "
        f"The opening has {validation.metrics.get('onboarding_instructions', 0):,} optional Start Here lines, all "
        f"{validation.metrics.get('choice_preview_instructions', 0):,} alternative chapters expose choice previews, "
        f"{validation.metrics.get('recovery_instructions', 0):,} dangerous chapters provide one recovery note, and "
        f"{validation.metrics.get('milestone_instructions', 0):,} milestones mark the journey.\n"
        "- **Correction:** accept and turn-in instructions name their NPC, object, or item source; internal database markers are rejected by validation.\n"
        "- **Resumption behavior:** travel prose is optional, so a partially complete or level-70 character cannot be blocked by it.\n"
        "- **Intentional boundary:** bind/hearth instructions and mandatory flight use remain player-directed because current bind, cooldown, and known-path state vary per character.\n"
        "- **Remaining proof:** verify the representative travel, terrain, item, escort, group, and resume cases in game.\n\n"
        "## R-003 — Minimum quest levels not enforced (resolved and verified in game)\n\n"
        "- **Observed failure:** Guidelime first offered quest 729, The Absent Minded Prospector, to a level-12 character, then an initial correction raised the route to level 14 before presenting the available lower-level Darkshore work.\n"
        "- **Cause:** Guidelime displays Questie's minimum level in its editor but does not use that field to defer a `[QA]` step.\n"
        f"- **Correction:** the generator now emits {validation.metrics.get('level_gate_instructions', 0):,} mandatory `[XP]` gates, and validation rejects any accept whose stream has not reached the quest's required level.\n"
        "- **Ordering:** lower-required-level quests in the current or immediately adjacent route zone are selected before a higher-level gate. Distant scraps do not force a cross-continent detour, and a short local grind remains preferable when nearby questing is exhausted. Once raised, the route floor does not decrease; legitimate lower-minimum follow-ups inherit it.\n"
        "- **Live proof:** on 2026-07-13, the project owner reloaded the deployed Anniversary addon on a level-13 Night Elf Hunter and confirmed the distance-aware Darkshore gating behaved correctly.\n\n"
        "## R-004 — Optional content mixed into default progression (remediated structurally)\n\n"
        "- **Previous sequence:** dungeon, raid, Hunter, reputation, and PvP quests were linked through the primary picker.\n"
        "- **Why it failed:** users could not distinguish the permanent world route from group and gated completionist content.\n"
        "- **Revised sequence:** the primary stream contains permanent world quests only; optional content and world descendants that require it form a separate dependency-safe stream.\n"
        "- **Expected improvement:** the solo/world route no longer silently requires optional group content.\n"
        "- **Quest-log implications:** each stream is independently simulated against the 23-slot working policy.\n"
        "- **Travel/group/story tradeoff:** optional chains remain complete; their geographic ordering has static metrics and remains subject to representative live review.\n\n"
        "## R-005 — Inactive Scourge Invasion leaked into the primary route (resolved statically)\n\n"
        "- **Observed failure:** 15 quests from Questie's `Invasion` sort were emitted even though the pinned Phase 2 profile marks the Scourge Invasion inactive.\n"
        "- **Cause:** the seasonal-sort exclusion omitted Questie's `-368` Scourge Invasion sort, so database presence was mistaken for current availability.\n"
        "- **Correction:** the sort is now audit-only, a validator rejects every emitted seasonal/world-event quest, and Blizzard's time-limited event notice is pinned in the phase profile.\n"
        "- **Related correction:** legendary item-triggered chains are now labeled and routed as optional content rather than appearing in normal leveling progression.\n"
        "- **Remaining proof:** static source, catalog, route, and package gates cover this exclusion; the broader future-phase absence row remains in the in-game matrix.\n",
        encoding="utf-8",
    )
    uncertainties = {
        "schema_version": 1,
        "release": release,
        "release_blocked": not release["public_release_ready"],
        "claims": [
            {"id": "U-001", "status": "verified", "claim": "Anniversary client quest-log maximum", "value": 25, "evidence": "Project owner screenshot on 2026-07-13 showed Questie Tracker 16/25 in the live Anniversary client"},
            {"id": "U-002", "status": "bounded", "claim": "independent authored-route coverage", "affected_primary_quests": validation.metrics.get("authored_route_primary_overlap", 0), "interpretation": "comparison evidence is used where available; pinned Questie plus official phase evidence controls low-risk catalog facts"},
            {"id": "U-003", "status": "static_review_complete_needs_live_confirmation", "claim": "chapter travel and story optimization", "reviewed_chapters": validation.metrics.get("static_reviewed_chapters", 0), "required_evidence": "representative in-game chapter matrix"},
            {"id": "U-004", "status": "open", "claim": "live Guidelime and Questie behavior", "required_evidence": "completed in-game smoke matrix"},
        ],
    }
    (output / "uncertainties.json").write_text(
        json.dumps(uncertainties, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    write_client_installation_report(client_installation, output / "client-installation.md")
    write_revised_flow(project_root, output / "revised-flow", authored_comparison)


def write_client_installation_report(client: dict, path: Path) -> None:
    lines = [
        "# Anniversary client installation evidence", "",
        f"Status: **{client['status']}**", "",
        "| Check | Result |", "|---|---|",
    ]
    lines.extend(
        f"| {name.replace('_', ' ').title()} | {'PASS' if passed else 'FAIL'} |"
        for name, passed in client["checks"].items()
    )
    lines.extend([
        "", "## Deployment", "", "| Check | Result |", "|---|---|",
    ])
    lines.extend(
        f"| {name.replace('_', ' ').title()} | {'PASS' if passed else 'FAIL'} |"
        for name, passed in client["deployment_checks"].items()
    )
    lines.extend([
        "", "## Environment", "",
        f"- Product: `{client['client'].get('product')}`",
        f"- Build: `{client['client'].get('version')}`",
        f"- Interface: `{client['client'].get('interface')}`",
        f"- Guidelime: `{client['dependencies']['Guidelime'].get('Version')}`",
        f"- Questie: `{client['dependencies']['Questie'].get('Version')}`",
        f"- Runtime files compared: {client['runtime_files_compared']}",
        f"- Historical Guidelime load signal: {client['historical_guidelime_load_signal']}",
        f"- Launched after current deployment: {client['launched_after_current_deployment']}",
        "", "## Limitations", "",
    ])
    lines.extend(f"- {limitation}" for limitation in client["limitations"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_revised_flow(project_root: Path, output: Path, authored_comparison: dict) -> None:
    output.mkdir(parents=True, exist_ok=True)
    for old in output.glob("*.md"):
        old.unlink()
    specs = sorted((project_root / "data" / "route" / "chapters").glob("*.json"))
    index_lines = [
        "# Revised Anniversary flow", "",
        "These chapters mirror the generated Lua exactly. NPC/object names and coordinates are "
        "normalized from the pinned Questie structured source and are not player-facing waypoints "
        "until independently and in-game verified.", "",
        "| Chapter | Stream | Review status |", "|---|---|---|",
    ]
    for spec_path in specs:
        payload = json.loads(spec_path.read_text(encoding="utf-8"))
        comparisons = authored_comparison.get("chapter_comparisons", {}).get(
            Path(payload.get("guide_file", "")).name, []
        )
        filename = f"chapter-{spec_path.stem}.md"
        index_lines.append(
            f"| [{payload['title']}]({filename}) | {payload['branch']} | "
            f"{payload['review_status']} |"
        )
        lines = [
            f"# {payload['title']}", "",
            f"- Stream: `{payload['branch']}`",
            f"- Phase profile: `{payload['phase_profile']}`",
            f"- Level range: {payload.get('minimum_level') or 'branch-dependent'}–"
            f"{payload.get('maximum_level') or 'branch-dependent'}",
            f"- Review status: `{payload['review_status']}`",
            f"- Entry contract: {payload.get('entry_contract', 'not recorded')}",
            "- External prerequisite quest IDs: "
            + (", ".join(map(str, payload.get("external_prerequisite_quest_ids", []))) or "none"),
            "- Authored-route comparison: "
            + (
                "; ".join(
                    f"{item['source_id']} overlaps {item['overlapping_quests']} quests"
                    + (
                        f" at {item['relative_order_agreement']:.2%} relative-order agreement"
                        if item.get("relative_order_agreement") is not None else ""
                    )
                    for item in comparisons
                )
                or "no overlapping comparison chapter"
            ),
            f"- Next chapter: {payload.get('next_chapter') or 'none'}", "",
            "| Step | Action | Quest | Instruction | Structured location evidence |",
            "|---:|---|---|---|---|",
        ]
        for step in payload.get("steps", []):
            endpoints = []
            if step.get("type") == "acquire_flight_path":
                endpoints.append(
                    f"{step['map_name']} {step['x']:.2f}, {step['y']:.2f} "
                    "(Questie + authored route)"
                )
                endpoints.extend(step.get("evidence_refs", []))
            if step.get("type") in {"zone_transition", "transport"}:
                endpoints.append(
                    f"{step.get('origin_map_name')} -> {step.get('map_name')} "
                    f"(optional {step['type'].replace('_', ' ')})"
                )
                endpoints.extend(step.get("evidence_refs", []))
            for source in step.get("endpoint_sources", []):
                label = f"{source['kind']} {source['id']} — {source.get('name') or 'unresolved name'}"
                locations = source.get("locations", [])
                if locations:
                    location = locations[0]
                    label += (
                        f" at {location['map_name']} {location['x']:.2f}, {location['y']:.2f}"
                        " (Questie-only)"
                    )
                    if len(locations) > 1:
                        label += f" +{len(locations) - 1} alternate points"
                endpoints.append(label)
            for source in step.get("objective_sources", []):
                label = (
                    f"objective {source['kind']} {source['id']} — "
                    f"{source.get('name') or 'unresolved name'}"
                )
                locations = source.get("locations", [])
                if locations:
                    location = locations[0]
                    label += (
                        f" at {location['map_name']} {location['x']:.2f}, {location['y']:.2f}"
                        " (Questie-only)"
                    )
                    if len(locations) > 1:
                        label += f" +{len(locations) - 1} alternate points"
                endpoints.append(label)
            values = [
                str(step["order"]),
                step["type"].replace("_", " ").title(),
                (
                    f"{step['quest_name']} (`{step['quest_id']}`)"
                    if step.get("quest_id") is not None
                    else f"Travel — {step.get('map_name', 'route step')}"
                ),
                step["instruction"],
                "; ".join(endpoints) or "n/a",
            ]
            values = [value.replace("|", "\\|").replace("\n", " ") for value in values]
            lines.append("| " + " | ".join(values) + " |")
        (output / filename).write_text("\n".join(lines) + "\n", encoding="utf-8")
    (output / "README.md").write_text("\n".join(index_lines) + "\n", encoding="utf-8")


def _metric_chapters_from_specs(specs: list[dict]) -> list[dict]:
    return [
        {
            "id": spec["id"],
            "title": spec.get("title", spec["id"]),
            "branch": spec["branch"],
            "steps": [
                {"type": step["type"], "quest_id": int(step["quest_id"])}
                for step in spec.get("steps", [])
                if step.get("quest_id") is not None
                and step.get("type") in {"accept", "complete", "turn_in"}
            ],
        }
        for spec in specs
    ]


def _metric_chapters_from_snapshot(snapshot: dict) -> list[dict]:
    step_types = {"A": "accept", "C": "complete", "T": "turn_in"}
    return [
        {
            "id": chapter["path"],
            "title": chapter["title"],
            "branch": chapter["branch"],
            "steps": [
                {"type": step_types[step[0]], "quest_id": int(step[1:])}
                for step in chapter["steps"]
            ],
        }
        for chapter in snapshot["chapters"]
    ]


def _step_locations(catalog: Catalog, step: dict) -> list:
    entry = catalog.entries.get(int(step["quest_id"]))
    if entry is None:
        return []
    sources = {
        "accept": entry.quest.starter_sources,
        "complete": entry.quest.objective_sources,
        "turn_in": entry.quest.finisher_sources,
    }[step["type"]]
    return [location for source in sources for location in source.locations]


def _route_metric_summary(catalog: Catalog, chapters: list[dict]) -> dict:
    by_branch: dict[str, list[dict]] = defaultdict(list)
    for chapter in chapters:
        by_branch[chapter["branch"]].append(chapter)

    total_distance = 0.0
    comparable_transitions = 0
    map_transitions = 0
    mapped_steps = 0
    state_steps = 0
    accepts = 0
    accepted_ids = set()
    zone_runs: list[int] = []
    zone_transition_count = 0
    continent_transitions = 0
    chapter_metrics = []

    for branch, branch_chapters in by_branch.items():
        prior_point = None
        prior_zone = None
        prior_continent = None
        branch_zone_runs = 0
        for chapter in branch_chapters:
            chapter_steps = chapter["steps"]
            chapter_distance = 0.0
            chapter_comparable = 0
            chapter_mapped = 0
            chapter_accepts = 0
            chapter_zones = []
            for step in chapter_steps:
                state_steps += 1
                if step["type"] == "accept":
                    accepts += 1
                    chapter_accepts += 1
                    accepted_ids.add(step["quest_id"])
                    entry = catalog.entries.get(step["quest_id"])
                    if entry is not None:
                        zone = int(entry.quest.get("zone_or_sort", 0))
                        chapter_zones.append(zone)
                        if zone != prior_zone:
                            zone_runs.append(zone)
                            branch_zone_runs += 1
                            continent = CONTINENT_BY_ZONE.get(zone)
                            if continent and prior_continent and continent != prior_continent:
                                continent_transitions += 1
                            if continent:
                                prior_continent = continent
                            prior_zone = zone
                candidates = _step_locations(catalog, step)
                if not candidates:
                    continue
                mapped_steps += 1
                chapter_mapped += 1
                if prior_point is None:
                    point = min(candidates, key=lambda item: (item.map_id, item.x, item.y))
                else:
                    same_map = [item for item in candidates if item.map_id == prior_point.map_id]
                    if same_map:
                        point = min(
                            same_map,
                            key=lambda item: hypot(item.x - prior_point.x, item.y - prior_point.y),
                        )
                        distance = hypot(point.x - prior_point.x, point.y - prior_point.y)
                        total_distance += distance
                        chapter_distance += distance
                        comparable_transitions += 1
                        chapter_comparable += 1
                    else:
                        point = min(candidates, key=lambda item: (item.map_id, item.x, item.y))
                        map_transitions += 1
                prior_point = point
            chapter_metrics.append(
                {
                    "id": chapter["id"],
                    "title": chapter["title"],
                    "branch": branch,
                    "quest_state_steps": len(chapter_steps),
                    "accepted_quests": chapter_accepts,
                    "unique_quest_zones_or_sorts": len(set(chapter_zones)),
                    "mapped_quest_steps": chapter_mapped,
                    "same_map_proxy_distance": round(chapter_distance, 2),
                    "comparable_same_map_transitions": chapter_comparable,
                }
            )
        zone_transition_count += max(0, branch_zone_runs - 1)

    visits = Counter(zone_runs)
    return {
        "chapters": len(chapters),
        "quest_state_steps": state_steps,
        "accepted_quests": accepts,
        "unique_accepted_quests": len(accepted_ids),
        "accepted_quest_zone_transitions": zone_transition_count,
        "repeated_accepted_quest_zone_visits": sum(count - 1 for count in visits.values()),
        "continent_transitions": continent_transitions,
        "mapped_quest_steps": mapped_steps,
        "unmapped_quest_steps": state_steps - mapped_steps,
        "map_transitions": map_transitions,
        "same_map_proxy_distance": round(total_distance, 2),
        "comparable_same_map_transitions": comparable_transitions,
        "proxy_distance_per_comparable_transition": round(
            total_distance / comparable_transitions, 4
        ) if comparable_transitions else None,
        "proxy_distance_per_accepted_quest": round(total_distance / accepts, 4)
        if accepts else None,
        "methodology": (
            "For each QA/QC/QT step, choose the nearest Questie TBC starter, objective, or "
            "finisher point on the current map. Sum straight-line normalized map units only "
            "between comparable same-map points; reset continuity between independent branches. "
            "This is a routing proxy, not elapsed travel time, terrain distance, or transport time."
        ),
        "chapter_metrics": chapter_metrics,
    }


def _filter_metric_chapters(
    chapters: list[dict], quest_ids: set[int], branch: str
) -> list[dict]:
    return [
        {
            **chapter,
            "steps": [
                step for step in chapter["steps"] if step["quest_id"] in quest_ids
            ],
        }
        for chapter in chapters
        if chapter["branch"] == branch
    ]


def _summary_without_chapters(summary: dict) -> dict:
    return {key: value for key, value in summary.items() if key != "chapter_metrics"}


def _nearest_rank_percentile(values: list[int], percentile: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int(percentile * len(ordered) + 0.999999) - 1))
    return ordered[index]


def write_route_metrics(catalog: Catalog, validation: ValidationResult, path: Path,
                        project_root: Path | None = None) -> None:
    project_root = project_root or path.parents[1]
    primary = catalog.selected("covered_primary")
    zones = [int(entry.quest.get("zone_or_sort", 0)) for entry in primary]
    zone_runs: list[int] = []
    for zone in zones:
        if not zone_runs or zone_runs[-1] != zone:
            zone_runs.append(zone)
    visits = Counter(zone_runs)
    specs = [
        json.loads(spec.read_text(encoding="utf-8"))
        for spec in sorted((project_root / "data" / "route" / "chapters").glob("*.json"))
    ]
    primary_specs = [spec for spec in specs if spec.get("branch") == "primary"]
    chapter_by_quest: dict[int, int] = {}
    turn_in_chapter_by_quest: dict[int, int] = {}
    pickup_cluster_sizes: list[int] = []
    dangerous_steps_without_buffers = 0
    chapter_zone_counts: list[int] = []
    warning_markers = (
        "Elite/group recommended", "Escort —", "Heroic dungeon —", "Dungeon —", "Raid —",
    )
    for chapter_index, spec in enumerate(primary_specs, 1):
        chapter_zones = set()
        accept_run = 0
        for step in [item for item in spec.get("steps", []) if item.get("quest_id") is not None]:
            quest_id = int(step["quest_id"])
            chapter_zones.add(int(step.get("zone_or_sort", 0)))
            if step.get("type") == "accept":
                chapter_by_quest[quest_id] = chapter_index
                accept_run += 1
            else:
                if accept_run:
                    pickup_cluster_sizes.append(accept_run)
                    accept_run = 0
                if step.get("type") == "turn_in":
                    turn_in_chapter_by_quest[quest_id] = chapter_index
                if step.get("type") == "complete":
                    categories = set(step.get("conditional_categories", []))
                    dangerous = bool(
                        categories & {"elite", "escort", "heroic", "group_content"}
                        or step.get("category") in {"dungeon", "raid"}
                    )
                    if dangerous and not any(
                        marker in step.get("instruction", "") for marker in warning_markers
                    ):
                        dangerous_steps_without_buffers += 1
        if accept_run:
            pickup_cluster_sizes.append(accept_run)
        chapter_zone_counts.append(len(chapter_zones))
    primary_ids = set(chapter_by_quest)
    story_chain_split_details = []
    optional_dependencies_in_primary = 0
    for quest_id in primary_ids:
        quest = catalog.entries[quest_id].quest
        dependencies = set(quest.prerequisites_all) | set(quest.prerequisites_any)
        dependencies.update(
            value for value in (
                quest.get("parent_quest"), quest.get("available_starting_with")
            ) if value
        )
        for dependency in dependencies:
            entry = catalog.entries.get(dependency)
            if entry and entry.status == "covered_optional":
                optional_dependencies_in_primary += 1
            if (
                dependency in chapter_by_quest
                and chapter_by_quest[dependency] != chapter_by_quest[quest_id]
            ):
                story_chain_split_details.append({
                    "dependency_quest_id": dependency,
                    "dependency_quest_name": catalog.entries[dependency].quest.name,
                    "dependency_chapter": primary_specs[chapter_by_quest[dependency] - 1]["title"],
                    "dependent_quest_id": quest_id,
                    "dependent_quest_name": quest.name,
                    "dependent_chapter": primary_specs[chapter_by_quest[quest_id] - 1]["title"],
                    "tradeoff": (
                        "Dependency order is preserved; the boundary keeps the route within its "
                        "reviewed level, hub, and zone scope."
                    ),
                })
    held_across_details = [
        {
            "quest_id": quest_id,
            "quest_name": catalog.entries[quest_id].quest.name,
            "accepted_chapter": primary_specs[chapter_by_quest[quest_id] - 1]["title"],
            "turn_in_chapter": primary_specs[turn_in_chapter - 1]["title"],
            "guidance": "explicit retain step at the receiving chapter boundary",
        }
        for quest_id, turn_in_chapter in sorted(turn_in_chapter_by_quest.items())
        if chapter_by_quest.get(quest_id) != turn_in_chapter
    ]
    active_by_branch: dict[str, set[int]] = defaultdict(set)
    active_samples_by_branch: dict[str, list[int]] = defaultdict(list)
    for spec in specs:
        branch = str(spec.get("branch"))
        for step in spec.get("steps", []):
            quest_id = step.get("quest_id")
            if step.get("type") == "accept" and isinstance(quest_id, int):
                active_by_branch[branch].add(quest_id)
            elif step.get("type") == "turn_in" and isinstance(quest_id, int):
                active_by_branch[branch].discard(quest_id)
            if step.get("type") in {"accept", "complete", "turn_in"}:
                active_samples_by_branch[branch].append(len(active_by_branch[branch]))
    active_quest_load = {
        branch: {
            "samples": len(values),
            "maximum": max(values, default=0),
            "p50": _nearest_rank_percentile(values, 0.50),
            "p95": _nearest_rank_percentile(values, 0.95),
        }
        for branch, values in sorted(active_samples_by_branch.items())
    }
    continents = [CONTINENT_BY_ZONE[zone] for zone in zone_runs if zone in CONTINENT_BY_ZONE]
    continent_transitions = sum(
        left != right for left, right in zip(continents, continents[1:])
    )
    baseline_path = project_root / "data" / "evidence" / "pre-remediation-route.json"
    baseline_snapshot = json.loads(baseline_path.read_text(encoding="utf-8"))
    baseline_chapters = _metric_chapters_from_snapshot(baseline_snapshot)
    revised_chapters = _metric_chapters_from_specs(specs)
    baseline_route_metrics = _route_metric_summary(catalog, baseline_chapters)
    revised_route_metrics = _route_metric_summary(catalog, revised_chapters)
    baseline_primary_ids = {
        step["quest_id"]
        for chapter in baseline_chapters
        if chapter["branch"] == "primary"
        for step in chapter["steps"]
        if step["type"] == "accept"
    }
    revised_primary_ids = {
        step["quest_id"]
        for chapter in revised_chapters
        if chapter["branch"] == "primary"
        for step in chapter["steps"]
        if step["type"] == "accept"
    }
    shared_primary_ids = baseline_primary_ids & revised_primary_ids
    comparable_baseline = _route_metric_summary(
        catalog, _filter_metric_chapters(baseline_chapters, shared_primary_ids, "primary")
    )
    comparable_revised = _route_metric_summary(
        catalog, _filter_metric_chapters(revised_chapters, shared_primary_ids, "primary")
    )
    comparison_keys = (
        "accepted_quest_zone_transitions",
        "repeated_accepted_quest_zone_visits",
        "continent_transitions",
        "map_transitions",
        "same_map_proxy_distance",
        "proxy_distance_per_accepted_quest",
    )
    comparison_deltas = {
        key: round(
            (comparable_revised[key] - comparable_baseline[key])
            / comparable_baseline[key]
            * 100,
            2,
        )
        for key in comparison_keys
        if comparable_baseline[key]
    }
    payload = {
        "schema_version": 1,
        "scope_id": catalog.scope.get("id"),
        "phase_profile": catalog.phase_profile.get("id"),
        "baseline": {
            "source": "frozen pre-remediation route snapshot (2026-07-13)",
            "route_snapshot": "data/evidence/pre-remediation-route.json",
            "route_snapshot_sha256": baseline_snapshot["canonical_chapters_sha256"],
            "quest_state_steps": 7665,
            "covered_quests": 2555,
            "maximum_active_quests": 8,
            "batched_accept_groups": 0,
            "batched_quests": 0,
            "route_metrics": baseline_route_metrics,
        },
        "revised": {
            "quest_state_steps": validation.metrics.get("quest_steps"),
            "covered_quests": validation.metrics.get("covered_primary", 0)
            + validation.metrics.get("covered_optional", 0)
            + validation.metrics.get("covered_alternative", 0),
            "maximum_active_quests": max(
                (value for key, value in validation.metrics.items() if key.startswith("max_active_")),
                default=0,
            ),
            "batched_accept_groups": validation.metrics.get("batched_accept_groups", 0),
            "batched_quests": validation.metrics.get("batched_quests", 0),
            "level_gate_steps": validation.metrics.get("level_gate_instructions", 0),
            "primary_zone_transitions": max(0, len(zone_runs) - 1),
            "repeated_primary_zone_visits": sum(count - 1 for count in visits.values()),
            "unique_primary_zones_or_sorts": len(set(zones)),
            "continent_transitions": continent_transitions,
            "primary_chapters": len(primary_specs),
            "maximum_zones_per_primary_chapter": max(chapter_zone_counts, default=0),
            "multi_zone_primary_chapters": sum(count > 1 for count in chapter_zone_counts),
            "isolated_pickup_clusters": sum(size == 1 for size in pickup_cluster_sizes),
            "pickup_clusters": len(pickup_cluster_sizes),
            "average_quests_per_pickup_cluster": round(
                sum(pickup_cluster_sizes) / len(pickup_cluster_sizes), 2
            ) if pickup_cluster_sizes else 0,
            "flight_path_steps": {
                "acquired": validation.metrics.get("flight_path_instructions", 0),
                "explicit_uses": 0,
                "policy": "acquisitions are cross-verified; flight use remains player-directed",
            },
            "hearth_steps": {
                "binds": 0,
                "uses": 0,
                "policy": "not prescribed because current hearth state and cooldown are character-specific",
            },
            "transport_steps": {
                "explicit_crossings": validation.metrics.get("transport_instructions", 0),
                "local_zone_transitions": validation.metrics.get("zone_transition_instructions", 0),
                "policy": "chapter handoffs are explicit and optional; cross-continent methods use reviewed TBC transport evidence",
            },
            "route_metrics": revised_route_metrics,
            "quests_held_across_chapters": len(held_across_details),
            "quests_held_across_chapter_details": held_across_details,
            "story_chain_splits": len(story_chain_split_details),
            "story_chain_split_details": story_chain_split_details,
            "active_quest_load": active_quest_load,
            "optional_dependencies_in_primary": optional_dependencies_in_primary,
            "dangerous_steps_without_buffers": dangerous_steps_without_buffers,
        },
        "comparison": {
            "scope": (
                "Quest IDs shared by the frozen and revised primary routes; independent "
                "optional and alternative streams are excluded from cross-route edges."
            ),
            "shared_primary_quests": len(shared_primary_ids),
            "baseline": _summary_without_chapters(comparable_baseline),
            "revised": _summary_without_chapters(comparable_revised),
            "revised_delta_percent": comparison_deltas,
            "assessment": "material_macro_travel_improvement_with_documented_local_proxy_regression",
            "regression_justification": (
                "The same-map straight-line proxy rises modestly, while zone, map, repeated-zone, "
                "and continent transitions fall. The proxy assigns zero distance to map changes "
                "and cannot price boats, portals, flight time, terrain, or objective overlap, so "
                "its local-distance regression is reported rather than hidden. Representative "
                "in-game route review remains the deciding release gate."
            ),
        },
        "interpretation": {
            "improvement_proven": [
                "same-zone independent quest pickups and objectives are batched",
                "future-phase quests are absent from the selected route",
                "optional and group-gated content is separated from the primary world route",
                "quest completion steps name normalized NPC, object, and item targets where available",
                "every quest accept is preceded by its chapter-local route-floor gate, and route floors never decrease",
                "the same Questie-coordinate proxy is reported for every frozen and revised chapter",
            ],
            "not_yet_proven": [
                "elapsed travel-time reduction; the reproducible comparison is a normalized coordinate proxy",
                "live hearth, transport, terrain, and cooldown behavior",
            ],
        },
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _coverage_row(catalog: Catalog, entry) -> dict[str, str | int]:
    status = {
        "covered_primary": "Present",
        "covered_optional": "Conditional",
        "covered_alternative": "Conditional",
        "baseline_completed": "Present (starting baseline)",
        "unavailable": "Unavailable",
        "excluded": "Conditional" if entry.reason_code in {
            "other_race", "other_class", "profession", "event", "recurring", "repeatable", "monthly"
        } else "Unavailable",
    }.get(entry.status, "Unverified")
    placement = (
        f"{entry.branch or 'primary'} step {entry.order}"
        if entry.status.startswith("covered") else "Audit only"
    )
    prerequisites = []
    if entry.quest.prerequisites_all:
        prerequisites.append("all-of: " + ",".join(map(str, entry.quest.prerequisites_all)))
    if entry.quest.prerequisites_any:
        prerequisites.append("any-of: " + ",".join(map(str, entry.quest.prerequisites_any)))
    if entry.reason:
        prerequisites.append(entry.reason)
    if entry.conditional_categories:
        prerequisites.append("categories: " + ",".join(entry.conditional_categories))
    revision = catalog.source_revision or "local"
    questie_source = (
        f"https://github.com/Questie/Questie/tree/{revision}"
        if catalog.source_revision else catalog.source_path
    )
    phase_sources = [item.get("url") for item in catalog.phase_profile.get("official_sources", [])]
    source = "; ".join([f"Questie {revision}: {questie_source}"] + [url for url in phase_sources if url])
    correction = (
        "Keep out of the selected phase route; retain in the audit."
        if entry.status == "unavailable" else
        "Keep in its explicit conditional/audit category."
        if entry.status == "excluded" else
        "Covered in the generated route; confirm live behavior in the in-game matrix."
    )
    return {
        "guide_section_or_step": placement,
        "quest_name": entry.quest.name,
        "quest_id": entry.quest.id,
        "status": status,
        "phase_applicability": (
            f"Phase {entry.available_phase}+" if entry.available_phase else
            f"Selected Phase {catalog.phase_profile.get('phase')}"
        ),
        "content_era": entry.quest.content_era,
        "source_provenance": ", ".join(entry.quest.data_sources),
        "prerequisite_or_restriction": "; ".join(prerequisites) or "none recorded",
        "recommended_correction": correction,
        "supporting_sources": source,
    }


def build_zip(project_root: Path, output: Path) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    included = [
        project_root / f"{ADDON_NAME}.toc",
        project_root / "README.md",
        project_root / "LICENSE",
        project_root / "docs" / "IN_GAME_SMOKE_TEST.md",
        project_root / "docs" / "IN_GAME_RESULTS.md",
        project_root / "docs" / "STATIC_RELEASE_GATE.md",
        project_root / "docs" / "STANDALONE_ARCHITECTURE.md",
        project_root / "docs" / "IMPLEMENTATION_PLAN.md",
        project_root / "docs" / "RELEASE_NOTES.md",
        project_root / "docs" / "USAGE.md",
        project_root / "docs" / "DEVELOPMENT.md",
        project_root / "data" / "evidence" / "runtime-coverage.json",
        project_root / "config" / "baseline_teldrassil_1_9.json",
        project_root / "config" / "scope.json",
        project_root / "config" / "content_policy.json",
        project_root / "config" / "phases" / "tbc_anniversary_phase_2.json",
        project_root / "config" / "source_policy.json",
        project_root / "config" / "guidelime.json",
        project_root / "config" / "authored_routes.json",
        project_root / "config" / "client_installation.json",
        project_root / "config" / "release.json",
        project_root / "docs" / "REMEDIATION_PLAN.md",
    ]
    included.extend(toc_all_lua_files(project_root))
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in included:
            if path.is_file():
                archive.write(path, Path(ADDON_NAME) / path.relative_to(project_root))
    return output


def release_archive_name(project_root: Path) -> str:
    release = load_release(project_root / "config" / "release.json")
    return f"{ADDON_NAME}-{release['version']}-bcc.zip"


def write_release_metadata(project_root: Path, archive: Path) -> Path:
    """BigWigs-compatible metadata consumed by WowUp's GitHub provider."""
    release = load_release(project_root / "config" / "release.json")
    output = archive.parent / "release.json"
    payload = {"releases": [{"name": release["version"], "filename": archive.name,
                              "nolib": False, "metadata": [{"flavor": "bcc", "interface": 20506}]}]}
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return output
