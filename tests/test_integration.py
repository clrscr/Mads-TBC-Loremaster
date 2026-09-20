import json
import hashlib
import os
import re
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from mads_loremaster.catalog import (
    LOCAL_ROUTE_RADIUS,
    _route_zone_distance,
    build_catalog,
    dependency_edges,
    route_key,
)
from mads_loremaster.guides import (
    ADDON_NAME,
    ALTERNATIVE_GROUP,
    AUBERDINE_DEFERRED_RETURN,
    AUBERDINE_FIRST_PICKUPS,
    AUBERDINE_FLIGHT_CHAIN,
    MAX_LUA_LINES,
    OPTIONAL_GROUP,
    PRIMARY_GROUP,
    parse_guide_file,
    toc_lua_files,
)
from mads_loremaster.questie import (
    TBC_QUEST_DATABASE,
    load_blacklist,
    load_quest_tags,
    resolve_questie_root,
)
from mads_loremaster.validate import validate_addon, validate_content_provenance
from mads_loremaster.travel import load_travel_network, plan_travel
from mads_loremaster.reports import write_route_metrics


PROJECT_ROOT = Path(__file__).resolve().parents[1]
QUESTIE = Path(os.environ.get("QUESTIE_PATH", "/private/tmp/Questie"))


@unittest.skipUnless((QUESTIE / "Database" / "TBC" / "tbcQuestDB.lua").is_file(), "Questie fixture not supplied")
class GeneratedAddonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = build_catalog(resolve_questie_root(QUESTIE))

    def test_every_quest_is_classified(self):
        self.assertGreater(len(self.catalog.entries), 6000)
        self.assertNotIn(None, (entry.status for entry in self.catalog.entries.values()))

    def test_runtime_tbc_corrections_are_applied(self):
        self.assertIn(95455, self.catalog.entries)  # Anniversary correction-only quest
        self.assertEqual(self.catalog.entries[95455].status, "excluded")  # repeatable PvP turn-in
        self.assertEqual(self.catalog.entries[10211].status, "covered_primary")  # City of Light scripted event
        self.assertEqual(self.catalog.entries[10552].branch, "scryer")

    def test_tbc_transport_network_uses_logical_crossings(self):
        links = load_travel_network(PROJECT_ROOT / "config" / "travel_network.json")
        self.assertEqual(plan_travel(3483, 3521, links).type, "zone_transition")
        self.assertEqual(
            plan_travel(3703, 1537, links).link_ids,
            ("shattrath-alliance-portals",),
        )
        self.assertEqual(
            plan_travel(1657, 51, links).link_ids,
            ("auberdine-menethil",),
        )
        self.assertEqual(
            plan_travel(1519, 440, links).link_ids,
            ("ratchet-booty-bay",),
        )
        self.assertEqual(plan_travel(3557, 3525, links).type, "zone_transition")
        self.assertEqual(
            plan_travel(1519, 3525, links).link_ids,
            ("auberdine-menethil", "auberdine-exodar"),
        )

    def test_every_emitted_quest_and_interaction_is_pre_cataclysm(self):
        emitted = self.catalog.selected(
            "covered_primary", "covered_optional", "covered_alternative", "baseline_completed"
        )
        self.assertTrue(emitted)
        self.assertTrue(all(entry.quest.content_era == "pre_cataclysm" for entry in emitted))
        self.assertTrue(all(TBC_QUEST_DATABASE in entry.quest.data_sources for entry in emitted))
        self.assertEqual(self.catalog.entries[10766].quest.name, "Invasion Point: Cataclysm")
        self.assertEqual(self.catalog.entries[10766].quest.content_era, "pre_cataclysm")
        allowed_entity_sources = set(self.catalog.content_policy["allowed_entity_sources"])
        self.assertFalse(
            any(
                source.data_source not in allowed_entity_sources
                for entry in self.catalog.entries.values()
                for source in (
                    entry.quest.starter_sources
                    + entry.quest.finisher_sources
                    + entry.quest.objective_sources
                )
            )
        )
        errors, metrics = validate_content_provenance(self.catalog)
        self.assertEqual(errors, [])
        self.assertEqual(metrics["post_tbc_emitted_quests"], 0)
        self.assertEqual(metrics["correction_only_emitted_quests"], 0)
        self.assertEqual(metrics["forbidden_source_references"], 0)
        stasis_chamber = next(
            source
            for source in self.catalog.entries[10977].quest.objective_sources
            if source.id == 185519
        )
        self.assertEqual(stasis_chamber.name, "Mana-Tombs Stasis Chamber")
        self.assertEqual(stasis_chamber.data_source, "Database/Corrections/tbcObjectFixes.lua")

    def test_cataclysm_provenance_is_a_hard_failure(self):
        entry = self.catalog.entries[10211]
        original = entry.quest
        entry.quest = replace(
            original,
            content_era="cataclysm",
            data_sources=("Database/Cata/cataQuestDB.lua",),
        )
        try:
            errors, metrics = validate_content_provenance(self.catalog)
        finally:
            entry.quest = original
        self.assertTrue(any("forbidden post-TBC source" in error for error in errors))
        self.assertTrue(any("non-pre-Cataclysm provenance" in error for error in errors))
        self.assertEqual(metrics["post_tbc_emitted_quests"], 1)
        self.assertEqual(metrics["forbidden_source_references"], 1)

    def test_phase_and_conditional_blacklists_match_tbc_phase_2(self):
        phase_2 = load_blacklist(resolve_questie_root(QUESTIE), 2)
        self.assertNotIn(2358, phase_2)  # explicitly available in TBC Anniversary
        self.assertIn(403, phase_2)  # removed with TBC
        self.assertNotIn(8367, phase_2)  # enabled in TBC Phase 2
        self.assertNotIn(11004, phase_2)  # Ogri'la content is live in Phase 2
        self.assertEqual(phase_2[11063].reason_code, "future_phase")
        self.assertEqual(phase_2[11063].available_phase, 3)
        self.assertEqual(phase_2[9524].available_phase, 4)

    def test_phase_profile_changes_produce_reviewable_deltas(self):
        root = resolve_questie_root(QUESTIE)
        phase_1 = load_blacklist(root, 1)
        phase_2 = load_blacklist(root, 2)
        self.assertIn(8367, phase_1)
        self.assertNotIn(8367, phase_2)
        self.assertIn(11004, phase_1)
        self.assertNotIn(11004, phase_2)
        self.assertIn(11063, phase_2)

    def test_tbc_runtime_quest_tags_are_applied(self):
        tags = load_quest_tags(resolve_questie_root(QUESTIE), 2)
        self.assertEqual(tags[10866], (1, "Elite"))
        self.assertEqual(tags[10884], (85, "Heroic"))
        self.assertEqual(tags[1222], (84, "Escort"))
        heroic = self.catalog.entries[10884]
        self.assertTrue({"dungeon", "heroic", "group_content"} <= set(heroic.conditional_categories))

    def test_starter_and_finisher_sources_have_map_scoped_coordinates(self):
        quest = self.catalog.entries[983].quest
        self.assertEqual(quest.starter_sources[0].name, "Wizbang Cranktoggle")
        self.assertEqual(quest.finisher_sources[0].kind, "object")
        self.assertEqual(quest.finisher_sources[0].name, "Buzzbox 827")
        point = quest.finisher_sources[0].locations[0]
        self.assertEqual((point.map_id, point.map_name), (148, "Darkshore"))
        self.assertAlmostEqual(point.x, 36.64)
        self.assertAlmostEqual(point.y, 46.26)
        plagued = self.catalog.entries[2118].quest
        self.assertEqual(plagued.objective_sources[0].name, "Captured Rabid Thistle Bear")

    def test_player_facing_zone_names_are_canonical(self):
        self.assertEqual(self.catalog.zones[133], "Gnomeregan")
        self.assertEqual(self.catalog.zones[3522], "Blade's Edge Mountains")
        self.assertEqual(self.catalog.zones[1977], "Zul'Gurub")
        self.assertEqual(self.catalog.zones[3836], "Magtheridon's Lair")

    def test_correction_only_entities_keep_explicit_source_provenance(self):
        corrected = next(source for source in self.catalog.entries[9685].quest.starter_sources
                         if source.id == 178420)
        self.assertEqual(corrected.name, "Magister Astalor Bloodsworn")
        self.assertEqual(corrected.data_source, "Database/Corrections/tbcNPCFixes.lua")
        self.assertEqual(
            corrected.to_dict()["verification"],
            "questie_structured_source_only",
        )

    def test_generated_addon_validates(self):
        validation = validate_addon(self.catalog, PROJECT_ROOT)
        self.assertTrue(validation.ok, "\n".join(validation.errors))
        self.assertEqual(validation.metrics["unexpectedly_missing"], 0)
        self.assertLessEqual(max(value for key, value in validation.metrics.items() if key.startswith("max_active_")), 23)
        self.assertGreater(validation.metrics["batched_accept_groups"], 350)
        self.assertGreater(validation.metrics["batched_quests"], 900)
        self.assertGreater(validation.metrics["item_use_instructions"], 100)
        self.assertGreater(validation.metrics["scripted_objective_instructions"], 50)
        self.assertGreater(validation.metrics["tagged_preparation_instructions"], 100)
        self.assertGreater(validation.metrics["objective_target_instructions"], 1000)
        self.assertEqual(validation.metrics["string_quality_violations"], 0)
        self.assertEqual(validation.metrics["unresolved_endpoint_names"], 0)
        self.assertEqual(validation.metrics["unresolved_objective_names"], 0)
        self.assertEqual(validation.metrics["post_tbc_emitted_quests"], 0)
        self.assertEqual(validation.metrics["correction_only_emitted_quests"], 0)
        self.assertEqual(validation.metrics["forbidden_source_references"], 0)
        self.assertEqual(
            validation.metrics["pre_cataclysm_covered_quests"],
            validation.metrics["covered_primary"]
            + validation.metrics["covered_optional"]
            + validation.metrics["covered_alternative"],
        )
        self.assertLessEqual(validation.metrics["longest_guide_line"], 300)
        self.assertGreaterEqual(validation.metrics["flight_path_instructions"], 25)
        self.assertEqual(
            validation.metrics["route_semantic_steps"],
            validation.metrics["flight_path_instructions"]
            + validation.metrics["chapter_entry_instructions"]
            + validation.metrics["level_gate_instructions"]
            + validation.metrics["zone_transition_instructions"]
            + validation.metrics["transport_instructions"]
            + validation.metrics["retention_instructions"]
            + validation.metrics["branch_entry_instructions"]
            + validation.metrics["onboarding_instructions"]
            + validation.metrics["choice_preview_instructions"]
            + validation.metrics["recovery_instructions"]
            + validation.metrics["milestone_instructions"],
        )
        self.assertEqual(validation.metrics["retention_instructions"], 1)
        self.assertEqual(validation.metrics["onboarding_instructions"], 4)
        self.assertEqual(validation.metrics["milestone_instructions"], 5)
        specs = [
            json.loads(path.read_text(encoding="utf-8"))
            for path in sorted((PROJECT_ROOT / "data" / "route" / "chapters").glob("*.json"))
        ]
        branch_count = len({spec["branch"] for spec in specs})
        non_primary_chapters = sum(spec["branch"] != "primary" for spec in specs)
        self.assertEqual(
            validation.metrics["branch_entry_instructions"],
            non_primary_chapters,
        )
        alternative_chapters = sum(
            spec["branch"] not in {"primary", "optional_content"} for spec in specs
        )
        self.assertEqual(
            validation.metrics["choice_preview_instructions"],
            alternative_chapters,
        )
        self.assertEqual(
            validation.metrics["zone_transition_instructions"]
            + validation.metrics["transport_instructions"],
            validation.metrics["lua_files"] - branch_count,
        )
        self.assertGreater(validation.metrics["transport_instructions"], 40)
        self.assertEqual(validation.metrics["chapter_entry_instructions"], validation.metrics["lua_files"])
        self.assertGreaterEqual(validation.metrics["chapter_entry_waypoints"], 160)
        self.assertLessEqual(
            validation.metrics["chapter_entry_waypoints"],
            validation.metrics["chapter_entry_instructions"],
        )
        self.assertGreater(validation.metrics["level_gate_instructions"], 50)
        self.assertEqual(validation.metrics["static_reviewed_chapters"], validation.metrics["lua_files"])
        self.assertGreater(validation.metrics["normalized_objective_sources"], 2000)
        if validation.metrics["authored_route_sources"]:
            self.assertGreater(validation.metrics["authored_route_primary_overlap"], 1000)
        else:
            self.assertTrue(any("authored route" in warning for warning in validation.warnings))
        if validation.metrics["client_installation_checks"] != validation.metrics["client_installation_checks_passed"]:
            self.assertTrue(any("client installation" in warning for warning in validation.warnings))
        self.assertGreater(validation.metrics["covered_optional"], 500)
        self.assertEqual(validation.metrics["runtime_files"], 13)
        self.assertGreater(validation.metrics["runtime_manifest_quests"], 4000)

    def test_standalone_runtime_surface_is_packaged_before_legacy_guides(self):
        toc = (PROJECT_ROOT / f"{ADDON_NAME}.toc").read_text(encoding="utf-8")
        self.assertIn("## Title: Mad's TBC Loremaster", toc)
        self.assertIn("## RequiredDeps: Questie", toc)
        self.assertIn("## OptionalDeps: TomTom, Guidelime", toc)
        self.assertLess(toc.index("data\\QuestManifest.lua"), toc.index("Runtime\\Core.lua"))
        self.assertLess(toc.index("Runtime\\UI.lua"), toc.index("Guides\\primary"))
        for relative in (
            "Runtime/Core.lua",
            "Runtime/Character.lua",
            "Runtime/Eligibility.lua",
            "Runtime/Router.lua",
            "Runtime/Navigation.lua",
            "Runtime/UI.lua",
        ):
            self.assertTrue((PROJECT_ROOT / relative).is_file(), relative)
    def test_runtime_manifest_expands_to_alliance_character_specific_content(self):
        manifest = (PROJECT_ROOT / "data" / "QuestManifest.lua").read_text(encoding="utf-8")
        emitted = {int(value) for value in re.findall(r"^\s*\[(\d+)\]\s*=", manifest, re.MULTILINE)}
        legacy = {
            entry.quest.id
            for entry in self.catalog.entries.values()
            if entry.status.startswith("covered") or entry.status == "baseline_completed"
        }
        other_race = next(
            entry.quest.id
            for entry in self.catalog.entries.values()
            if entry.reason_code == "other_race"
            and int(entry.quest.get("required_races", 0)) & (1 | 4 | 8 | 64 | 1024)
        )
        other_class = next(
            entry.quest.id
            for entry in self.catalog.entries.values()
            if entry.reason_code == "other_class"
        )
        recurring = next(
            entry.quest.id
            for entry in self.catalog.entries.values()
            if entry.reason_code in {"recurring", "repeatable"}
            and int(entry.quest.get("required_races", 0)) in {0, 1, 4, 8, 64, 1024}
        )
        self.assertGreater(len(emitted), len(legacy))
        self.assertIn(other_race, emitted)
        self.assertIn(other_class, emitted)
        self.assertIn(recurring, emitted)
        self.assertIn("recurrence=", manifest)
        self.assertIn("exclusiveTo=", manifest)
        self.assertIn("prerequisitesAll=", manifest)

    def test_runtime_manifest_preserves_profession_gate_and_geographic_zone(self):
        manifest = (PROJECT_ROOT / "data" / "QuestManifest.lua").read_text(encoding="utf-8")
        alchemy = re.search(r"^\s*\[1581\]\s*=\s*\{.*$", manifest, re.MULTILINE)
        self.assertIsNotNone(alchemy)
        row = alchemy.group(0)
        self.assertIn("questSort=-181", row)
        self.assertIn("canonicalZone=141", row)
        self.assertIn('zoneName="Teldrassil"', row)
        self.assertIn("requiredSkill={171,20}", row)
        self.assertIn('category="profession"', row)
        self.assertIn("geographic=true", row)

    def test_runtime_manifest_retains_restriction_evidence_for_both_factions(self):
        manifest = (PROJECT_ROOT / "data" / "QuestManifest.lua").read_text(encoding="utf-8")
        for quest_id in (2338, 2318):
            self.assertRegex(manifest, rf"(?m)^\s*\[{quest_id}\]\s*=")
        self.assertIn("requiredRanks={{762,-3},{762,-4},{762,-5}}", manifest)
        self.assertIn("hordeRaceMask = 690", manifest)
        self.assertIn("availabilityByPhase=", manifest)
        self.assertIn("variants=", manifest)

    def test_branch_prerequisites_preserve_any_of_semantics(self):
        specs = [
            json.loads(path.read_text(encoding="utf-8"))
            for path in sorted((PROJECT_ROOT / "data" / "route" / "chapters").glob("*.json"))
        ]
        scryer = next(spec for spec in specs if spec["branch"] == "scryer_choice_2")
        self.assertIn([10552], scryer["external_prerequisite_any_groups"])
        self.assertNotIn(10551, scryer["external_prerequisite_all_quest_ids"])
        guidance = next(
            step["instruction"] for step in scryer["steps"] if step["type"] == "branch_entry"
        )
        self.assertIn("Allegiance to the Scryers", guidance)
        self.assertNotIn("Allegiance to the Aldor or Allegiance to the Scryers", guidance)
        for spec in specs:
            required_all = set(spec["external_prerequisite_all_quest_ids"])
            for quest_id in required_all:
                conflicts = set(self.catalog.entries[quest_id].quest.exclusive_to)
                self.assertFalse(conflicts & required_all, spec["title"])

    def test_player_experience_guidance_is_clear_and_nonblocking(self):
        specs = [
            json.loads(path.read_text(encoding="utf-8"))
            for path in sorted((PROJECT_ROOT / "data" / "route" / "chapters").glob("*.json"))
        ]
        first_primary = next(spec for spec in specs if spec["branch"] == "primary")
        onboarding = [
            step for step in first_primary["steps"] if step["type"] == "onboarding"
        ]
        self.assertEqual(len(onboarding), 4)
        self.assertTrue(
            all(step["optional"] and "[O]" in step["instruction"] for step in onboarding)
        )

        alternatives = [
            spec for spec in specs
            if spec["branch"] not in {"primary", "optional_content"}
        ]
        self.assertTrue(alternatives)
        for spec in alternatives:
            self.assertNotIn("Mutually Exclusive Choices", spec["title"])
            self.assertNotIn("Other Choices", spec["title"])
            previews = [
                step for step in spec["steps"] if step["type"] == "choice_preview"
            ]
            self.assertEqual(len(previews), 1, spec["title"])
            self.assertIn("Choice preview:", previews[0]["instruction"])

        recovery_count = 0
        for spec in specs:
            dangerous = any(
                step["type"] == "complete"
                and (
                    step.get("quest_tag") in {"Elite", "Escort", "Heroic"}
                    or step.get("category") in {"dungeon", "raid"}
                )
                for step in spec["steps"]
            )
            recovery = [step for step in spec["steps"] if step["type"] == "recovery"]
            self.assertEqual(len(recovery), int(dangerous), spec["title"])
            recovery_count += len(recovery)
        self.assertGreater(recovery_count, 25)

        milestones = [
            step
            for spec in specs
            for step in spec["steps"]
            if step["type"] == "milestone"
        ]
        self.assertEqual(len(milestones), 5)
        milestone_text = " ".join(step["instruction"] for step in milestones)
        self.assertIn("welcome to Outland", milestone_text)
        self.assertIn("Shattrath", milestone_text)
        self.assertIn("level 70", milestone_text)
        self.assertIn("Final primary-route turn-in", milestone_text)

    def test_chapter_line_limit(self):
        for path in toc_lua_files(PROJECT_ROOT):
            self.assertLessEqual(len(path.read_text(encoding="utf-8").splitlines()), MAX_LUA_LINES, path)

    def test_primary_chapters_are_not_arbitrary_multi_zone_chunks(self):
        for path in toc_lua_files(PROJECT_ROOT):
            title, _, group, tags = parse_guide_file(path)
            if group != PRIMARY_GROUP or title.startswith("01 Auberdine"):
                continue
            zones = {
                int(self.catalog.entries[quest_id].quest.get("zone_or_sort", 0))
                for tag, quest_id in tags
                if tag == "QA"
            }
            self.assertLessEqual(len(zones), 2, f"{title}: {sorted(zones)}")

    def test_auberdine_is_the_primary_opening_pickup_chapter(self):
        first = next(
            path
            for path in toc_lua_files(PROJECT_ROOT)
            if parse_guide_file(path)[2] == PRIMARY_GROUP
        )
        title, _, _, tags = parse_guide_file(first)
        expected = []
        for quest_id in AUBERDINE_FLIGHT_CHAIN:
            expected.extend((tag, quest_id) for tag in ("QA", "QC", "QT"))
        expected.append(("QA", AUBERDINE_DEFERRED_RETURN))
        expected.extend(("QA", quest_id) for quest_id in AUBERDINE_FIRST_PICKUPS)
        self.assertEqual(title, "01 Auberdine - Arrival & First Pickups")
        self.assertEqual(tags, expected)

    def test_guidelime_picker_order_matches_primary_navigation(self):
        primary = []
        alternatives = []
        for toc_index, path in enumerate(toc_lua_files(PROJECT_ROOT)):
            title, _, group, _ = parse_guide_file(path)
            match = re.search(r"\[N(\d+)-(\d+)\s", path.read_text(encoding="utf-8"))
            row = (
                int(match.group(1)) if match else 0,
                int(match.group(2)) if match else 0,
                title,
                toc_index,
            )
            if group == PRIMARY_GROUP:
                primary.append(row)
            elif group == ALTERNATIVE_GROUP:
                alternatives.append(row)
        self.assertEqual([row[3] for row in sorted(primary)], [row[3] for row in primary])
        self.assertTrue(alternatives)
        self.assertTrue(all(row[0] == row[1] == 0 for row in alternatives))

    def test_primary_route_contains_only_permanent_world_content(self):
        self.assertTrue(self.catalog.selected("covered_optional"))
        self.assertTrue(all(entry.category == "world" for entry in self.catalog.selected("covered_primary")))
        optional_categories = {entry.category for entry in self.catalog.selected("covered_optional")}
        self.assertTrue({"hunter", "dungeon", "raid", "reputation", "pvp"} <= optional_categories)
        optional_guides = [
            path for path in toc_lua_files(PROJECT_ROOT)
            if parse_guide_file(path)[2] == OPTIONAL_GROUP
        ]
        self.assertTrue(optional_guides)
        self.assertIn(
            "Optional completionist route. Enter after the relevant primary prerequisites",
            optional_guides[0].read_text(encoding="utf-8"),
        )
        self.assertFalse(any("Other Choices" in parse_guide_file(path)[0] for path in toc_lua_files(PROJECT_ROOT)))

    def test_inactive_scourge_invasion_is_audit_only(self):
        invasion = [
            entry
            for entry in self.catalog.entries.values()
            if int(entry.quest.get("zone_or_sort", 0)) == -368
        ]
        self.assertTrue(invasion)
        self.assertTrue(
            all(
                entry.status in {"excluded", "unavailable"}
                for entry in invasion
            )
        )
        self.assertTrue(
            all(
                entry.reason_code in {
                    "event", "repeatable", "missing_starter", "unavailable", "other_race"
                }
                for entry in invasion
            )
        )

    def test_legendary_item_trigger_is_optional(self):
        entry = self.catalog.entries[7785]
        self.assertEqual(entry.quest.name, "Examine the Vessel")
        self.assertEqual(entry.status, "covered_optional")
        self.assertEqual(entry.category, "legendary")

    def test_raid_trophy_item_triggers_are_optional(self):
        expected = {
            7495: "Victory for the Alliance",
            7781: "The Lord of Blackrock",
            8183: "The Heart of Hakkar",
            11002: "The Fall of Magtheridon",
        }
        for quest_id, name in expected.items():
            entry = self.catalog.entries[quest_id]
            self.assertEqual(entry.quest.name, name)
            self.assertEqual(entry.status, "covered_optional")
            self.assertEqual(entry.category, "raid")

    def test_primary_route_avoids_level_sort_zone_thrashing(self):
        primary = self.catalog.selected("covered_primary")
        zones = [int(entry.quest.get("zone_or_sort", 0)) for entry in primary]
        transitions = sum(left != right for left, right in zip(zones, zones[1:]))
        self.assertLess(transitions, 300)

    def test_frozen_route_metrics_are_reproducible_and_regression_bounded(self):
        snapshot = json.loads(
            (PROJECT_ROOT / "data" / "evidence" / "pre-remediation-route.json")
            .read_text(encoding="utf-8")
        )
        canonical = json.dumps(
            snapshot["chapters"], separators=(",", ":"), sort_keys=True
        ).encode("utf-8")
        self.assertEqual(snapshot["chapter_count"], 36)
        self.assertEqual(snapshot["quest_state_steps"], 7665)
        self.assertEqual(snapshot["accepted_quests"], 2555)
        self.assertEqual(
            snapshot["canonical_chapters_sha256"], hashlib.sha256(canonical).hexdigest()
        )

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "route-metrics.json"
            write_route_metrics(self.catalog, validate_addon(self.catalog, PROJECT_ROOT), output, PROJECT_ROOT)
            metrics = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(len(metrics["baseline"]["route_metrics"]["chapter_metrics"]), 36)
        self.assertEqual(
            len(metrics["revised"]["route_metrics"]["chapter_metrics"]),
            len(list((PROJECT_ROOT / "data" / "route" / "chapters").glob("*.json"))),
        )
        comparison = metrics["comparison"]
        self.assertGreater(comparison["shared_primary_quests"], 1900)
        for key in (
            "accepted_quest_zone_transitions",
            "repeated_accepted_quest_zone_visits",
            "continent_transitions",
            "map_transitions",
        ):
            self.assertLess(comparison["revised"][key], comparison["baseline"][key])
        self.assertGreater(comparison["revised_delta_percent"]["same_map_proxy_distance"], 0)
        self.assertLess(comparison["revised_delta_percent"]["same_map_proxy_distance"], 10)
        self.assertIn("reported rather than hidden", comparison["regression_justification"])
        revised = metrics["revised"]
        self.assertEqual(
            len(revised["quests_held_across_chapter_details"]),
            revised["quests_held_across_chapters"],
        )
        self.assertTrue(
            all(item["guidance"] for item in revised["quests_held_across_chapter_details"])
        )
        self.assertEqual(
            len(revised["story_chain_split_details"]),
            revised["story_chain_splits"],
        )
        self.assertTrue(all(item["tradeoff"] for item in revised["story_chain_split_details"]))
        self.assertEqual(revised["active_quest_load"]["primary"]["maximum"], 8)
        self.assertLessEqual(
            revised["active_quest_load"]["primary"]["p95"],
            revised["active_quest_load"]["primary"]["maximum"],
        )

    def test_primary_floor_rises_only_after_nearby_lower_level_work(self):
        primary = self.catalog.selected("covered_primary")
        quests = {entry.quest.id: entry.quest for entry in primary}
        quest_ids = set(quests)
        edges = dependency_edges(quests, quest_ids)
        indegree = {quest_id: 0 for quest_id in quest_ids}
        for targets in edges.values():
            for target in targets:
                indegree[target] += 1
        ready = {quest_id for quest_id, degree in indegree.items() if degree == 0}
        current_zone = None
        for entry in primary:
            quest_id = entry.quest.id
            self.assertIn(quest_id, ready)
            chosen_level = route_key(entry.quest)[0]
            for candidate in ready:
                if route_key(quests[candidate])[0] >= chosen_level:
                    continue
                candidate_zone = int(quests[candidate].get("zone_or_sort", 0))
                self.assertGreater(
                    _route_zone_distance(candidate_zone, current_zone),
                    LOCAL_ROUTE_RADIUS,
                    f"quest {quest_id} raised the floor before nearby lower-level quest {candidate}",
                )
            ready.remove(quest_id)
            current_zone = int(entry.quest.get("zone_or_sort", 0))
            for target in edges.get(quest_id, ()):
                indegree[target] -= 1
                if indegree[target] == 0:
                    ready.add(target)

    def test_human_readable_quest_tags_remain_machine_parseable(self):
        first = toc_lua_files(PROJECT_ROOT)[0]
        source = first.read_text(encoding="utf-8")
        self.assertIn("Accept [QA6344 Nessa Shadowsong] from Mydrannul", source)
        self.assertIn("Turn in [QT6344 Nessa Shadowsong] to Nessa Shadowsong", source)
        self.assertIn("Leave at least two quest-log slots open. [O]", source)
        _, _, _, tags = parse_guide_file(first)
        self.assertIn(("QA", 6344), tags)
        self.assertIn(("QC", 6344), tags)
        self.assertIn(("QT", 6344), tags)

    def test_tbc_quest_named_cataclysm_is_explained_to_players(self):
        source = next(
            path.read_text(encoding="utf-8")
            for path in toc_lua_files(PROJECT_ROOT)
            if "[QA10766 Invasion Point: Cataclysm]" in path.read_text(encoding="utf-8")
        )
        self.assertIn(
            "Burning Crusade quest — ‘Cataclysm’ is the invasion point's name, not the later expansion.",
            source,
        )

    def test_level_gates_precede_every_higher_level_accept(self):
        self.assertLess(
            self.catalog.entries[953].order,
            self.catalog.entries[730].order,
            "level-10 Darkshore content should precede the level-14 breadcrumb",
        )
        self.assertLess(
            self.catalog.entries[953].order,
            self.catalog.entries[729].order,
            "lower-level Darkshore content should precede the level-15 prospector chain",
        )
        floor_by_branch = {}
        saw_quest_729 = False
        for spec_path in sorted((PROJECT_ROOT / "data" / "route" / "chapters").glob("*.json")):
            payload = json.loads(spec_path.read_text(encoding="utf-8"))
            branch = payload["branch"]
            gated = 10
            floor = floor_by_branch.get(branch, 10)
            for step in payload["steps"]:
                if step["type"] == "level_gate":
                    self.assertFalse(step["optional"])
                    self.assertGreater(step["required_level"], gated)
                    self.assertIn(f"[XP{step['required_level']} ", step["instruction"])
                    gated = step["required_level"]
                elif step["type"] == "accept":
                    actual_required = max(
                        10,
                        int(self.catalog.entries[step["quest_id"]].quest.get("required_level", 0)),
                    )
                    self.assertGreaterEqual(step["required_level"], actual_required)
                    self.assertEqual(step["required_level"], gated, (spec_path, step))
                    self.assertGreaterEqual(step["required_level"], floor)
                    floor = step["required_level"]
                    if step["quest_id"] == 729:
                        saw_quest_729 = True
                        self.assertGreaterEqual(gated, 15)
            floor_by_branch[branch] = floor
        self.assertTrue(saw_quest_729)

    def test_player_facing_instructions_use_wow_native_language(self):
        source = "\n".join(
            path.read_text(encoding="utf-8") for path in toc_lua_files(PROJECT_ROOT)
        )
        self.assertIn(
            "Collect or use the required item: Wool Cloth. [QC10352 A Donation of Wool]",
            source,
        )
        chapter_entries = []
        for spec_path in sorted((PROJECT_ROOT / "data" / "route" / "chapters").glob("*.json")):
            payload = json.loads(spec_path.read_text(encoding="utf-8"))
            chapter_entries.extend(
                step for step in payload["steps"] if step["type"] == "chapter_entry"
            )
        self.assertTrue(chapter_entries)
        for step in chapter_entries:
            if step["x"] is not None and step["y"] is not None:
                self.assertIn(
                    f"[G{step['x']:.2f},{step['y']:.2f} {step['map_name']}]",
                    step["instruction"],
                )
        self.assertIn(
            "Use the quest item [UI7586-] as directed; complete the required NPC or creature "
            "objective: Captured Rabid Thistle Bear. [QC2118 Plagued Lands]",
            source,
        )
        self.assertIn("Optional: learn the flight path from", source)
        thyssiana_guide = next(
            path.read_text(encoding="utf-8")
            for path in toc_lua_files(PROJECT_ROOT)
            if "learn the flight path from Thyssiana" in path.read_text(encoding="utf-8")
        )
        self.assertLess(
            thyssiana_guide.index("[QC1059 Reclaiming the Charred Vale]"),
            thyssiana_guide.index("learn the flight path from Thyssiana"),
        )
        self.assertLess(
            thyssiana_guide.index("learn the flight path from Thyssiana"),
            thyssiana_guide.index("[QT1059 Reclaiming the Charred Vale]"),
        )
        self.assertNotIn("Complete objectives involving", source)
        self.assertNotIn("then complete", source)
        self.assertNotRegex(
            source,
            r"(?i)\b(?:quest credit|credit marker|quest trigger|invis(?:ible)?)\b",
        )


if __name__ == "__main__":
    unittest.main()
