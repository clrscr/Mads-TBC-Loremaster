import os
from pathlib import Path
import tempfile
import unittest

from mads_loremaster.model import Quest
from mads_loremaster.questie import (
    QuestieLayoutError,
    load_flight_masters,
    load_quest_sources,
    load_quests,
    load_zones,
)


class EntityCorrectionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.write("Database/TBC/tbcNpcDB.lua", '''QuestieDB.npcData = [[return {
[1] = {"Old name",nil,nil,nil,nil,nil,{[357]={{46.39,18.24}}}},
[2] = {"Removed spawn",nil,nil,nil,nil,nil,{[357]={{10,20}}}},
[4] = {"Unchanged NPC",nil,nil,nil,nil,nil,{[357]={{30,40}}}},
}]]
''')
        self.write("Database/TBC/tbcObjectDB.lua", '''QuestieDB.objectData = [[return {
[5] = {"Old object",nil,nil,{[357]={{50,60}}}},
}]]
''')
        self.write("Database/TBC/tbcItemDB.lua", "QuestieDB.itemData = [[return {\n}]]\n")
        self.write("Database/Zones/data/zoneIds.lua", '''ZoneDB.zoneIDs = {
    DESOLACE = 405,
    FERALAS = 357,
}
''')
        self.npc_path = "Database/Corrections/tbcNPCFixes.lua"
        self.write(self.npc_path, '''function QuestieTBCNpcFixes:Load()
    return {
        [1] = {
            [npcKeys.name] = "Corrected name -- literal",
            [npcKeys.spawns] = {[zoneIDs.DESOLACE]={{25.6,70.0}}},
        },
        [2] = {[npcKeys.spawns] = {}},
        [3] = {
            [npcKeys.name] = "Correction-only NPC",
            [npcKeys.spawns] = {[zoneIDs.DESOLACE]={{12,34}}},
        },
        [4] = {[npcKeys.questStarts] = {999}},
    }
end
function QuestieTBCNpcFixes:LoadFactionFixes()
    return {[1] = {[npcKeys.spawns] = {[357]={{1,2}}}}}
end
''')
        self.write("Database/Corrections/tbcObjectFixes.lua", '''function QuestieTBCObjectFixes:Load()
    return {
        [5] = {
            [objectKeys.name] = "Corrected object",
            [objectKeys.spawns] = {[zoneIDs.DESOLACE]={{-1,-1}}},
        },
    }
end
''')
        self.quests = {10: Quest(10, ("Test quest", [[1, 2, 3, 4], [5]], [[1], [5]]))}
        self.maps = {405: "Desolace", 357: "Feralas"}

    def write(self, relative, source):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source)

    def sources(self):
        return load_quest_sources(self.root, self.quests, self.maps)[10]

    def test_tbc_overrides_replace_names_and_locations_and_add_missing_entities(self):
        starters, finishers, _ = self.sources()
        corrected, removed, added, unchanged, obj = starters
        self.assertEqual(corrected.name, "Corrected name -- literal")
        point = corrected.locations[0]
        self.assertEqual((point.map_id, point.x, point.y), (405, 25.6, 70.0))
        self.assertEqual(corrected.data_source, self.npc_path)
        self.assertEqual(removed.locations, ())
        self.assertEqual(removed.name, "Removed spawn")
        self.assertEqual(added.name, "Correction-only NPC")
        self.assertEqual(added.locations[0].map_id, 405)
        self.assertEqual(unchanged.locations[0].map_id, 357)
        self.assertEqual(unchanged.data_source, "Database/TBC/tbcNpcDB.lua")
        self.assertEqual(obj.name, "Corrected object")
        self.assertEqual(obj.locations, ())
        self.assertEqual(obj.data_source, "Database/Corrections/tbcObjectFixes.lua")
        self.assertEqual(finishers, (corrected, obj))

    def test_does_not_emit_character_phase_points_as_unconditional_locations(self):
        self.write(self.npc_path, '''function QuestieTBCNpcFixes:Load()
    return {[1] = {[npcKeys.spawns] = {[405]={{1,2,phases.EXAMPLE},{3,4},{5,6,42}}}}}
end
''')
        point, = self.sources()[0][0].locations
        self.assertEqual((point.x, point.y), (3, 4))

    def test_existing_flight_master_uses_same_corrected_endpoint(self):
        self.write("Database/TBC/tbcNpcDB.lua", '''QuestieDB.npcData = [[return {
[1] = {"Old name",nil,nil,nil,nil,nil,{[357]={{46.39,18.24}}},nil,357,nil,nil,nil,"A",nil,8192},
}]]
''')
        flight_masters = load_flight_masters(self.root, self.maps)
        self.assertEqual(set(flight_masters), {1})
        self.assertEqual(flight_masters[1], self.sources()[0][0])

    def test_nil_override_leaves_the_existing_field_unchanged(self):
        self.write(self.npc_path, '''function QuestieTBCNpcFixes:Load()
    return {[1] = {[npcKeys.name] = nil, [npcKeys.spawns] = nil}}
end
''')
        source = self.sources()[0][0]
        self.assertEqual(source.name, "Old name")
        self.assertEqual(source.locations[0].map_id, 357)
        self.assertEqual(source.data_source, "Database/TBC/tbcNpcDB.lua")

    def test_unknown_entities_remain_explicit_unverified_sources(self):
        self.quests[10] = Quest(10, ("Unresolved endpoints", [[987654], [987655]], [[987656]]))
        starters, finishers, _ = self.sources()
        for source in (*starters, *finishers):
            self.assertIsNone(source.name)
            self.assertEqual(source.locations, ())
            self.assertEqual(source.to_dict()["verification"], "questie_structured_source_only")
            self.assertEqual(source.data_source, f"Database/TBC/tbc{source.kind.capitalize()}DB.lua")

    def test_rejects_executable_expressions_in_imported_fields(self):
        for value in ('os.execute("nope")', '{} or os.execute("nope")'):
            with self.subTest(value=value):
                self.write(self.npc_path, '''function QuestieTBCNpcFixes:Load()
    return {[1] = {[npcKeys.spawns] = ''' + value + '''}}
end
''')
                with self.assertRaises(QuestieLayoutError):
                    self.sources()


QUESTIE = Path(os.environ.get("QUESTIE_PATH", "/private/tmp/Questie"))


@unittest.skipUnless((QUESTIE / "Database/TBC/tbcQuestDB.lua").is_file(), "Questie fixture not supplied")
class PinnedEntityCorrectionTests(unittest.TestCase):
    def test_rokaro_and_correction_only_astalor_use_tbc_locations(self):
        quests = load_quests(QUESTIE, context=None)
        selected = {quest_id: quests[quest_id] for quest_id in (6567, 6568, 9685, 10977)}
        sources = load_quest_sources(QUESTIE, selected, load_zones(QUESTIE))
        rokaro = sources[6567][1][0]
        self.assertEqual(rokaro.name, "Rokaro")
        point, = rokaro.locations
        self.assertEqual((point.map_id, point.x, point.y), (405, 25.6, 70.0))
        self.assertEqual(sources[6568][0][0], rokaro)
        astalor = next(source for source in sources[9685][0] if source.id == 178420)
        self.assertEqual(astalor.name, "Magister Astalor Bloodsworn")
        self.assertEqual(astalor.locations[0].map_id, 3487)
        chamber = next(source for source in sources[10977][2] if source.id == 185519)
        self.assertEqual(chamber.name, "Mana-Tombs Stasis Chamber")
        self.assertEqual(chamber.locations, ())


if __name__ == "__main__":
    unittest.main()
