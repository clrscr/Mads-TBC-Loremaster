from __future__ import annotations

import ast
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .lua_table import LuaParseError, parse_lua_table
from .model import MapPoint, QUEST_KEYS, Quest, QuestSource


ENTRY_RE = re.compile(r"^\[(\d+)\]\s*=\s*(\{.*\}),\s*$")
CONSTANT_RE = re.compile(r"^\s*([A-Z][A-Z0-9_]*)\s*=\s*(-?\d+),")
BLACKLIST_ASSIGN_RE = re.compile(r"^\s*\[(\d+)\]\s*=\s*(.*?),\s*(?:--\s*(.*))?$")
QUEST_TAG_RE = re.compile(
    r'^\s*\[(\d+)\]\s*=\s*(?:(.*?)\s+and\s+)?\{(\d+),\s*l10n\("([^"]+)"\)\}'
)

TBC_QUEST_DATABASE = "Database/TBC/tbcQuestDB.lua"
TBC_QUEST_CORRECTIONS = "Database/Corrections/tbcQuestFixes.lua"
TBC_ENTITY_DATABASES = {
    "npc": "Database/TBC/tbcNpcDB.lua",
    "object": "Database/TBC/tbcObjectDB.lua",
    "item": "Database/TBC/tbcItemDB.lua",
}
TBC_ENTITY_CORRECTIONS = {
    "npc": ("Database/Corrections/tbcNPCFixes.lua", "QuestieTBCNpcFixes"),
    "object": ("Database/Corrections/tbcObjectFixes.lua", "QuestieTBCObjectFixes"),
}


class QuestieLayoutError(RuntimeError):
    pass


@dataclass(frozen=True)
class BlacklistDecision:
    quest_id: int
    reason_code: str
    reason: str
    source: str
    available_phase: int | None = None


def resolve_questie_root(path: str | Path) -> Path:
    candidate = Path(path).expanduser().resolve()
    roots = (candidate, candidate / "Questie")
    for root in roots:
        if (root / "Database" / "TBC" / "tbcQuestDB.lua").is_file():
            return root
    raise QuestieLayoutError(
        f"{candidate} is not a Questie checkout/addon containing Database/TBC/tbcQuestDB.lua"
    )


def load_quests(root: Path, context=("Alliance", "HUNTER", "NightElf"), *, legacy_faction_replacement=False) -> dict[int, Quest]:
    database = root / TBC_QUEST_DATABASE
    quests: dict[int, Quest] = {}
    in_data = False
    for line_number, line in enumerate(database.read_text(encoding="utf-8").splitlines(), 1):
        if "QuestieDB.questData = [[return {" in line:
            in_data = True
            continue
        if not in_data:
            continue
        if line.strip() == "}]]":
            break
        match = ENTRY_RE.match(line)
        if not match:
            if line.strip():
                raise QuestieLayoutError(f"unexpected generated database line {database}:{line_number}")
            continue
        quest_id = int(match.group(1))
        try:
            values = parse_lua_table(match.group(2))
        except LuaParseError as error:
            raise QuestieLayoutError(f"failed to parse {database}:{line_number}: {error}") from error
        if not isinstance(values, list):
            raise QuestieLayoutError(f"quest {quest_id} is not a positional table")
        quests[quest_id] = Quest(
            quest_id,
            tuple(values),
            content_era="pre_cataclysm",
            data_sources=(TBC_QUEST_DATABASE,),
        )
    if not quests:
        raise QuestieLayoutError(f"no quests found in {database}")
    _apply_corrections(root, quests, context, legacy_faction_replacement=legacy_faction_replacement)
    return quests


def load_quest_sources(
    root: Path,
    quests: dict[int, Quest],
    map_names: dict[int, str],
) -> dict[int, tuple[tuple[QuestSource, ...], tuple[QuestSource, ...], tuple[QuestSource, ...]]]:
    """Resolve Questie's positional starter/finisher references.

    Questie stores endpoint sources as three parallel lists: NPCs, objects, and
    items. Coordinates remain explicitly structured-source-only until a route
    reviewer independently confirms the map, entity, and live client behavior.
    """
    referenced: dict[str, set[int]] = {"npc": set(), "object": set(), "item": set()}
    for quest in quests.values():
        for endpoint in (quest.get("started_by"), quest.get("finished_by")):
            for kind, source_id in _endpoint_ids(endpoint):
                referenced[kind].add(source_id)
        for kind, source_id in _objective_ids(quest.get("objectives")):
            referenced[kind].add(source_id)

    entities: dict[str, dict[int, QuestSource]] = {
        "npc": _load_entity_rows(
            root / "Database" / "TBC" / "tbcNpcDB.lua",
            "QuestieDB.npcData = [[return {",
            "npc",
            referenced["npc"],
            6,
            map_names,
        ),
        "object": _load_entity_rows(
            root / "Database" / "TBC" / "tbcObjectDB.lua",
            "QuestieDB.objectData = [[return {",
            "object",
            referenced["object"],
            3,
            map_names,
        ),
        "item": _load_entity_rows(
            root / "Database" / "TBC" / "tbcItemDB.lua",
            "QuestieDB.itemData = [[return {",
            "item",
            referenced["item"],
            None,
            map_names,
        ),
    }
    for kind in TBC_ENTITY_CORRECTIONS:
        _apply_entity_corrections(root, kind, entities[kind], referenced[kind], map_names)

    result = {}
    for quest_id, quest in quests.items():
        endpoints = []
        for raw in (quest.get("started_by"), quest.get("finished_by")):
            resolved = []
            for kind, source_id in _endpoint_ids(raw):
                resolved.append(
                    entities[kind].get(
                        source_id,
                        QuestSource(
                            kind,
                            source_id,
                            None,
                            data_source=TBC_ENTITY_DATABASES[kind],
                        ),
                    )
                )
            endpoints.append(tuple(resolved))
        objective_sources = tuple(
            entities[kind].get(
                source_id,
                QuestSource(
                    kind,
                    source_id,
                    None,
                    data_source=TBC_ENTITY_DATABASES[kind],
                ),
            )
            for kind, source_id in _objective_ids(quest.get("objectives"))
        )
        result[quest_id] = (endpoints[0], endpoints[1], objective_sources)
    return result


def load_flight_masters(root: Path, map_names: dict[int, str]) -> dict[int, QuestSource]:
    path = root / TBC_ENTITY_DATABASES["npc"]
    result: dict[int, QuestSource] = {}
    in_data = False
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if "QuestieDB.npcData = [[return {" in line:
            in_data = True
            continue
        if not in_data:
            continue
        if line.strip() == "}]]":
            break
        flag_match = re.search(r",(\d+)\},\s*$", line)
        if not flag_match or not int(flag_match.group(1)) & 8192:
            continue
        match = ENTRY_RE.match(line)
        if not match:
            continue
        npc_id = int(match.group(1))
        try:
            values = parse_lua_table(match.group(2))
        except LuaParseError as error:
            raise QuestieLayoutError(f"failed to parse {path}:{line_number}: {error}") from error
        if not isinstance(values, list) or len(values) < 15:
            continue
        friendly = values[12]
        if not isinstance(friendly, str) or "A" not in friendly:
            continue
        result[npc_id] = QuestSource(
            "npc",
            npc_id,
            str(values[0]),
            _map_points(values[6], map_names),
            data_source=TBC_ENTITY_DATABASES["npc"],
        )
    _apply_entity_corrections(root, "npc", result, set(result), map_names)
    return result


def _endpoint_ids(value) -> list[tuple[str, int]]:
    if not isinstance(value, list):
        return []
    result: list[tuple[str, int]] = []
    for index, kind in enumerate(("npc", "object", "item")):
        values = value[index] if index < len(value) else None
        if isinstance(values, list):
            result.extend((kind, int(source_id)) for source_id in values if isinstance(source_id, int))
    return result


def _objective_ids(value) -> list[tuple[str, int]]:
    if not isinstance(value, list):
        return []
    result: list[tuple[str, int]] = []
    for index, kind in enumerate(("npc", "object", "item")):
        entries = value[index] if index < len(value) else None
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if isinstance(entry, list) and entry and isinstance(entry[0], int):
                pair = (kind, int(entry[0]))
                if pair not in result:
                    result.append(pair)
    # Kill-credit objectives can name several interchangeable NPC IDs.
    kill_credits = value[4] if len(value) > 4 else None
    if isinstance(kill_credits, list):
        for entry in kill_credits:
            ids = entry[0] if isinstance(entry, list) and entry else None
            if isinstance(ids, list):
                for source_id in ids:
                    pair = ("npc", int(source_id)) if isinstance(source_id, int) else None
                    if pair and pair not in result:
                        result.append(pair)
    return result


def _load_entity_rows(
    path: Path,
    marker: str,
    kind: str,
    wanted: set[int],
    spawn_index: int | None,
    map_names: dict[int, str],
) -> dict[int, QuestSource]:
    if not path.is_file():
        raise QuestieLayoutError(f"missing Questie {kind} database in {path}")
    result: dict[int, QuestSource] = {}
    in_data = False
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if marker in line:
            in_data = True
            continue
        if not in_data:
            continue
        if line.strip() == "}]]":
            break
        match = ENTRY_RE.match(line)
        if not match or int(match.group(1)) not in wanted:
            continue
        entity_id = int(match.group(1))
        try:
            values = parse_lua_table(match.group(2))
        except LuaParseError as error:
            raise QuestieLayoutError(f"failed to parse {path}:{line_number}: {error}") from error
        if not isinstance(values, list) or not values:
            raise QuestieLayoutError(f"{kind} {entity_id} is not a positional table")
        locations = ()
        if spawn_index is not None and spawn_index < len(values):
            locations = _map_points(values[spawn_index], map_names)
        result[entity_id] = QuestSource(
            kind,
            entity_id,
            str(values[0]),
            locations,
            data_source=TBC_ENTITY_DATABASES[kind],
        )
    return result


def _map_points(value, map_names: dict[int, str]) -> tuple[MapPoint, ...]:
    if not isinstance(value, dict):
        return ()
    result: list[MapPoint] = []
    for map_id, points in value.items():
        if not isinstance(map_id, int) or not isinstance(points, list):
            continue
        for point in points:
            if (
                isinstance(point, list)
                and len(point) >= 2
                and isinstance(point[0], (int, float))
                and isinstance(point[1], (int, float))
                and 0 <= float(point[0]) <= 100
                and 0 <= float(point[1]) <= 100
            ):
                result.append(
                    MapPoint(
                        map_id,
                        map_names.get(map_id, f"Map {map_id}"),
                        float(point[0]),
                        float(point[1]),
                    )
                )
    return tuple(result)


def _apply_entity_corrections(
    root: Path,
    kind: str,
    entities: dict[int, QuestSource],
    wanted: set[int],
    map_names: dict[int, str],
) -> None:
    """Compose the common TBC name/spawn overrides without executing Lua.

    Faction and Darkmoon loaders need live character/calendar context and are
    deliberately not folded into this character-neutral snapshot. Likewise,
    phase-conditioned points are omitted rather than treated as always visible.
    Empty spawn tables replace stale database points; they are not a fallback.
    """
    relative, module = TBC_ENTITY_CORRECTIONS[kind]
    path = root / relative
    if not path.is_file():
        return
    source = _strip_lua_comments(path.read_text(encoding="utf-8"))
    marker = f"function {module}:Load()"
    start = source.find(marker)
    if start < 0:
        raise QuestieLayoutError(f"missing TBC entity correction loader in {path}")
    return_start = source.find("return", start + len(marker))
    table = _balanced_table(source, source.find("{", return_start))
    constants = _named_constants(root / "Database/Zones/data/zoneIds.lua", "zoneIDs")
    cursor = 1
    while cursor < len(table) - 1:
        separator = re.match(r"[\s,;]*", table[cursor:])
        cursor += separator.end()
        if cursor == len(table) - 1:
            break
        entry = re.match(r"\[(\d+)\]\s*=\s*", table[cursor:])
        if not entry:
            raise QuestieLayoutError(f"unsupported TBC entity correction entry in {path}")
        entity_id = int(entry.group(1))
        cursor += entry.end()
        row = _balanced_table(table, cursor)
        cursor += len(row)
        if entity_id not in wanted:
            continue
        fields = {}
        for field in ("name", "spawns"):
            assignment = re.search(rf"\[\s*{kind}Keys\.{field}\s*\]\s*=\s*", row)
            if not assignment:
                continue
            raw = _entity_correction_literal(row[assignment.end():], path)
            if raw == "nil":
                continue  # A nil-valued field is absent from the Lua override table.
            if field == "spawns":
                for name, value in constants.items():
                    raw = re.sub(rf"\b{re.escape(name)}\b", str(value), raw)
                raw = re.sub(r"\bphases\.[A-Z0-9_]+\b", '"conditional_spawn"', raw)
            try:
                value = parse_lua_table(raw)
            except LuaParseError as error:
                raise QuestieLayoutError(f"failed to parse {kind} {entity_id} {field} in {path}: {error}") from error
            if field == "name" and not isinstance(value, str):
                raise QuestieLayoutError(f"invalid {kind} {entity_id} name correction in {path}")
            if field == "spawns":
                if not isinstance(value, dict) and value != []:
                    raise QuestieLayoutError(f"invalid {kind} {entity_id} spawn correction in {path}")
                value = {
                    area: [point for point in points
                           if isinstance(point, list) and (len(point) < 3 or point[2] is None)]
                    for area, points in (value.items() if isinstance(value, dict) else ())
                    if isinstance(points, list)
                }
            fields[field] = value
        if not fields:
            continue
        existing = entities.get(entity_id)
        entities[entity_id] = QuestSource(
            kind,
            entity_id,
            fields.get("name", existing.name if existing else None),
            _map_points(fields["spawns"], map_names) if "spawns" in fields
            else existing.locations if existing else (),
            data_source=relative,
        )


def _entity_correction_literal(source: str, path: Path) -> str:
    if source.startswith("{"):
        literal = _balanced_table(source, 0)
    else:
        match = re.match(r'''(?:"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|nil\b)''', source, re.DOTALL)
        if not match:
            raise QuestieLayoutError(f"unsupported TBC entity correction value in {path}")
        literal = match.group(0)
    if source[len(literal):].lstrip()[:1] not in {",", ";", "}"}:
        raise QuestieLayoutError(f"unsupported TBC entity correction expression in {path}")
    return literal


LUA_QUEST_KEYS = (
    "name", "startedBy", "finishedBy", "requiredLevel", "questLevel",
    "requiredRaces", "requiredClasses", "objectivesText", "triggerEnd",
    "objectives", "sourceItemId", "preQuestGroup", "preQuestSingle",
    "childQuests", "inGroupWith", "exclusiveTo", "zoneOrSort",
    "requiredSkill", "requiredMinRep", "requiredMaxRep",
    "requiredSourceItems", "nextQuestInChain", "questFlags", "specialFlags",
    "parentQuest", "reputationReward", "breadcrumbForQuestId", "breadcrumbs",
    "extraObjectives", "requiredSpell", "requiredSpecialization",
    "requiredMaxLevel", "availableUntilCompleted", "availableStartingWith",
    "requiredRanks", "disabledByQuest",
)


def _apply_corrections(root: Path, quests: dict[int, Quest], context=("Alliance", "HUNTER", "NightElf"), *, legacy_faction_replacement=False) -> None:
    path = root / TBC_QUEST_CORRECTIONS
    if not path.is_file():
        return
    source = _strip_lua_comments(path.read_text(encoding="utf-8"))
    main_start = source.find("function QuestieTBCQuestFixes:Load()")
    if main_start < 0:
        raise QuestieLayoutError(f"missing TBC correction loader in {path}")
    return_start = source.find("return", main_start)
    main_table_start = source.find("{", return_start)
    main_table = _balanced_table(source, main_table_start)
    corrections = _parse_correction_table(main_table, root)

    alliance_marker = "local questFixes" + (context[0] if context else "Unused") + " ="
    alliance_start = source.find(alliance_marker)
    if alliance_start >= 0:
        alliance_table_start = source.find("{", alliance_start + len(alliance_marker))
        alliance_table = _balanced_table(source, alliance_table_start)
        for quest_id, fields in _parse_correction_table(alliance_table, root, context=context).items():
            if legacy_faction_replacement:
                # Reproduce the frozen 171-chapter historical guide corpus. The
                # adaptive catalog always uses field-wise composition below.
                corrections[quest_id] = fields
            else:
                corrections.setdefault(quest_id, {}).update(fields)

    for quest_id, overrides in corrections.items():
        if not isinstance(quest_id, int) or not isinstance(overrides, dict):
            continue
        existing = quests.get(quest_id)
        values = list(existing.values) if existing else []
        if len(values) < len(QUEST_KEYS):
            values.extend([None] * (len(QUEST_KEYS) - len(values)))
        for key, value in overrides.items():
            if isinstance(key, int) and 1 <= key <= len(QUEST_KEYS):
                values[key - 1] = value
        data_sources = existing.data_sources if existing else ()
        quests[quest_id] = Quest(
            quest_id,
            tuple(values),
            content_era=(
                existing.content_era if existing else "tbc_runtime_supplement"
            ),
            data_sources=tuple(dict.fromkeys((*data_sources, TBC_QUEST_CORRECTIONS))),
        )


def _parse_correction_table(source: str, root: Path, alliance: bool = False, context=None) -> dict:
    transformed = source
    if alliance or context:
        context = context or ("Alliance", "HUNTER", "NightElf")
        class_pattern = re.compile(r"\(\{(.*?)\}\)\[playerClass\]", re.DOTALL)

        def hunter_value(match: re.Match) -> str:
            hunter = re.search(r'\[\s*"' + re.escape(context[1]) + r'"\s*\]\s*=\s*(\d+)', match.group(1))
            if not hunter:
                raise QuestieLayoutError("unable to resolve class faction correction: " + context[1])
            return hunter.group(1)

        transformed = class_pattern.sub(hunter_value, transformed)
        transformed = re.sub(
            r'playerRace\s*==\s*"Human"\s*and\s*(\d+)\s*or\s*(\d+)',
            lambda match: match.group(1 if context[2] == "Human" else 2),
            transformed,
        )
    transformed = re.sub(
        r'l10n\(("(?:\\.|[^"\\])*")\)', lambda match: match.group(1), transformed
    )
    constants = _correction_constants(root)
    for name in sorted(constants, key=len, reverse=True):
        transformed = re.sub(rf"(?<![A-Za-z0-9_]){re.escape(name)}(?![A-Za-z0-9_])", str(constants[name]), transformed)

    arithmetic = re.compile(r"(?<![A-Za-z0-9_.])(-?\d+(?:\s*[+-]\s*\d+)+)(?=\s*[,}\]])")

    def calculate(match: re.Match) -> str:
        tokens = re.findall(r"[+-]?\s*\d+", match.group(1).replace(" ", ""))
        return str(sum(int(token) for token in tokens))

    transformed = arithmetic.sub(calculate, transformed)
    try:
        parsed = parse_lua_table(transformed)
    except LuaParseError as error:
        raise QuestieLayoutError(f"failed to parse TBC corrections: {error}") from error
    if not isinstance(parsed, dict):
        raise QuestieLayoutError("TBC correction root is not a keyed table")
    return parsed


def _correction_constants(root: Path) -> dict[str, int]:
    constants: dict[str, int] = {}
    for index, name in enumerate(LUA_QUEST_KEYS, 1):
        constants[f"questKeys.{name}"] = index
    constants.update({
        "raceIDs.NONE": 0, "raceIDs.HUMAN": 1, "raceIDs.ORC": 2,
        "raceIDs.DWARF": 4, "raceIDs.NIGHT_ELF": 8, "raceIDs.UNDEAD": 16,
        "raceIDs.TAUREN": 32, "raceIDs.GNOME": 64, "raceIDs.TROLL": 128,
        "raceIDs.BLOOD_ELF": 512, "raceIDs.DRAENEI": 1024,
        "raceIDs.ALL_ALLIANCE": 1101, "raceIDs.ALL_HORDE": 690,
        "classIDs.NONE": 0, "classIDs.WARRIOR": 1, "classIDs.PALADIN": 2,
        "classIDs.HUNTER": 4, "classIDs.ROGUE": 8, "classIDs.PRIEST": 16,
        "classIDs.SHAMAN": 64, "classIDs.MAGE": 128, "classIDs.WARLOCK": 256,
        "classIDs.DRUID": 1024, "classIDs.ALL_CLASSES": 1503,
        "questFlags.RAID": 64, "questFlags.MONTHLY": 65536,
        "specialFlags.NONE": 0, "specialFlags.REPEATABLE": 1,
        "profKeys.HERBALISM": 182, "profKeys.MINING": 186,
        "profKeys.RIDING": 762, "profKeys.SKINNING": 393,
        # Questie requiredRanks uses trained-tier indices, not skill points.
        "rankKeys.EXPERT": 3, "rankKeys.ARTISAN": 4, "rankKeys.MASTER": 5,
    })
    for icon in ("EVENT", "INTERACT", "LOOT", "NODE_FISH", "OBJECT", "SLAY", "TALK"):
        constants[f"Questie.ICON_TYPE_{icon}"] = 0
    constants.update(_named_constants(root / "Database" / "Zones" / "data" / "zoneIds.lua", "zoneIDs"))
    constants.update(_named_constants(root / "Database" / "Constants.lua", "sortKeys"))
    constants.update(_named_constants(root / "Database" / "questDB.lua", "factionIDs"))
    return constants


def _named_constants(path: Path, prefix: str) -> dict[str, int]:
    result: dict[str, int] = {}
    if not path.is_file():
        return result
    in_table = False
    marker = f".{prefix} = {{"
    for line in path.read_text(encoding="utf-8").splitlines():
        if marker in line:
            in_table = True
            continue
        if in_table and line.strip() == "}":
            break
        if in_table and (match := CONSTANT_RE.match(line)):
            result[f"{prefix}.{match.group(1)}"] = int(match.group(2))
    return result


def _strip_lua_comments(source: str) -> str:
    result: list[str] = []
    index = 0
    quote: str | None = None
    while index < len(source):
        char = source[index]
        if quote:
            result.append(char)
            if char == "\\" and index + 1 < len(source):
                index += 1
                result.append(source[index])
            elif char == quote:
                quote = None
            index += 1
            continue
        if char in "\"'":
            quote = char
            result.append(char)
            index += 1
            continue
        if source.startswith("--[[", index):
            end = source.find("]]", index + 4)
            index = len(source) if end < 0 else end + 2
            continue
        if source.startswith("--", index):
            end = source.find("\n", index + 2)
            if end < 0:
                break
            result.append("\n")
            index = end + 1
            continue
        result.append(char)
        index += 1
    return "".join(result)


def _balanced_table(source: str, start: int) -> str:
    if start < 0 or source[start] != "{":
        raise QuestieLayoutError("unable to locate correction table")
    depth = 0
    quote: str | None = None
    index = start
    while index < len(source):
        char = source[index]
        if quote:
            if char == "\\":
                index += 2
                continue
            if char == quote:
                quote = None
        elif source.startswith("--[[", index):
            end = source.find("]]", index + 4)
            if end < 0:
                raise QuestieLayoutError("unterminated Lua block comment")
            index = end + 2
            continue
        elif source.startswith("--", index):
            end = source.find("\n", index + 2)
            if end < 0:
                raise QuestieLayoutError("unterminated correction table")
            index = end + 1
            continue
        elif char in "\"'":
            quote = char
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[start:index + 1]
        index += 1
    raise QuestieLayoutError("unterminated correction table")


def _load_constants(path: Path) -> dict[int, str]:
    result: dict[int, str] = {}
    if not path.is_file():
        return result
    for line in path.read_text(encoding="utf-8").splitlines():
        match = CONSTANT_RE.match(line)
        if match:
            result[int(match.group(2))] = _humanize(match.group(1))
    return result


def load_zones(root: Path) -> dict[int, str]:
    return _load_constants(root / "Database" / "Zones" / "data" / "zoneIds.lua")


def load_sort_names(root: Path) -> dict[int, str]:
    return _load_constants(root / "Database" / "Constants.lua")


def load_hard_blacklist(root: Path, content_phase: int = 2) -> dict[int, BlacklistDecision]:
    path = root / "Database" / "Corrections" / "QuestieQuestBlacklist.lua"
    if not path.is_file():
        return {}
    source = path.read_text(encoding="utf-8")
    marker = "local questsToBlacklist ="
    start = source.find(marker)
    table_start = source.find("{", start + len(marker)) if start >= 0 else -1
    table = _balanced_table(source, table_start)
    result: dict[int, BlacklistDecision] = {}
    for line_number, line in enumerate(table.splitlines(), 1):
        match = BLACKLIST_ASSIGN_RE.match(line)
        if not match:
            continue
        quest_id = int(match.group(1))
        expression = match.group(2).strip()
        comment = (match.group(3) or "").strip()
        value = _evaluate_blacklist_expression(expression, content_phase)
        if value is True:
            code = _blacklist_reason_code(comment)
            reason = comment or "Questie marks this quest unavailable for the selected client"
            result[quest_id] = BlacklistDecision(
                quest_id, code, reason, f"{path.name}:Load table line {line_number}"
            )
        elif value not in (False, "HIDE_ON_MAP"):
            raise QuestieLayoutError(
                f"unsupported Questie blacklist value for quest {quest_id}: {value!r}"
            )
    return result


def load_tbc_phase_blacklist(root: Path, content_phase: int) -> dict[int, BlacklistDecision]:
    path = root / "Database" / "Corrections" / "ContentPhases" / "BurningCrusade.lua"
    if not path.is_file():
        raise QuestieLayoutError(f"missing TBC phase definitions in {path}")
    source = _strip_lua_comments(path.read_text(encoding="utf-8"))
    marker = "local questsToBlacklistByPhase ="
    start = source.find(marker)
    table_start = source.find("{", start + len(marker)) if start >= 0 else -1
    table = _balanced_table(source, table_start)
    try:
        phases = parse_lua_table(table)
    except LuaParseError as error:
        raise QuestieLayoutError(f"failed to parse TBC phase definitions: {error}") from error
    if not isinstance(phases, dict):
        raise QuestieLayoutError("TBC phase definitions are not a keyed table")
    result: dict[int, BlacklistDecision] = {}
    for phase, quests in phases.items():
        if not isinstance(phase, int) or not isinstance(quests, dict) or phase <= content_phase:
            continue
        for quest_id, enabled in quests.items():
            if enabled is True and isinstance(quest_id, int):
                prior = result.get(quest_id)
                if prior is None or phase < (prior.available_phase or phase):
                    result[quest_id] = BlacklistDecision(
                        quest_id,
                        "future_phase",
                        f"available starting in TBC content phase {phase}; selected phase is {content_phase}",
                        f"{path.name}:questsToBlacklistByPhase[{phase}]",
                        phase,
                    )
    return result


def load_questie_active_tbc_phase(root: Path) -> int:
    path = root / "Database" / "Corrections" / "ContentPhases" / "ContentPhases.lua"
    if not path.is_file():
        raise QuestieLayoutError(f"missing Questie active phase configuration in {path}")
    match = re.search(r"^\s*TBC\s*=\s*(\d+)\s*,", path.read_text(encoding="utf-8"), re.MULTILINE)
    if not match:
        raise QuestieLayoutError(f"unable to read active TBC phase from {path}")
    return int(match.group(1))


def load_quest_tags(root: Path, content_phase: int = 2) -> dict[int, tuple[int, str]]:
    path = root / "Database" / "Corrections" / "questTagInfoCorrections.lua"
    if not path.is_file():
        raise QuestieLayoutError(f"missing Questie quest-tag corrections in {path}")
    result: dict[int, tuple[int, str]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = QUEST_TAG_RE.match(line)
        if not match:
            continue
        quest_id = int(match.group(1))
        condition = match.group(2)
        if condition and _evaluate_blacklist_expression(condition.strip(), content_phase) is not True:
            continue
        result[quest_id] = (int(match.group(3)), match.group(4))
    return result


def load_blacklist(root: Path, content_phase: int = 2) -> dict[int, BlacklistDecision]:
    result = load_hard_blacklist(root, content_phase)
    # Phase unavailability is more actionable than a generic static-blacklist reason.
    result.update(load_tbc_phase_blacklist(root, content_phase))
    return result


def _evaluate_blacklist_expression(expression: str, content_phase: int):
    replacements = {
        "Expansions.Current": "2",
        "Expansions.Era": "1",
        "Expansions.Tbc": "2",
        "Expansions.Wotlk": "3",
        "Expansions.Cata": "4",
        "Expansions.MoP": "5",
        "ContentPhases.activePhases.TBC": str(content_phase),
        "Questie.IsChinaRegion": "False",
        "Questie.IsTitanReforged": "False",
        "Questie.IsTBC": "True",
        "Questie.IsAnniversaryTBC": "True",
        "HIDE_ON_MAP": '"HIDE_ON_MAP"',
    }
    transformed = expression
    for old in sorted(replacements, key=len, reverse=True):
        transformed = transformed.replace(old, replacements[old])
    transformed = re.sub(r"\btrue\b", "True", transformed)
    transformed = re.sub(r"\bfalse\b", "False", transformed)
    transformed = transformed.replace("~=", "!=")
    try:
        tree = ast.parse(transformed, mode="eval")
    except SyntaxError as error:
        raise QuestieLayoutError(f"unsupported Questie blacklist expression {expression!r}") from error
    allowed = (
        ast.Expression, ast.BoolOp, ast.And, ast.Or, ast.UnaryOp, ast.Not,
        ast.Compare, ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE,
        ast.Constant, ast.Load,
    )
    for node in ast.walk(tree):
        if not isinstance(node, allowed):
            raise QuestieLayoutError(
                f"unsupported node {type(node).__name__} in Questie blacklist expression {expression!r}"
            )
    return eval(compile(tree, "<questie-blacklist>", "eval"), {"__builtins__": {}}, {})


def _blacklist_reason_code(comment: str) -> str:
    lowered = comment.lower()
    if "duplicate" in lowered or "replaced with" in lowered:
        return "duplicate"
    if "event" in lowered or "holiday" in lowered:
        return "event_inactive"
    if "collector" in lowered or "promotion" in lowered or "entitlement" in lowered:
        return "entitlement"
    if "test" in lowered or "gm " in lowered or "gm island" in lowered:
        return "test_or_internal"
    if "removed" in lowered or "deprecated" in lowered or "old]" in lowered:
        return "obsolete"
    if "not in the game" in lowered or "not available" in lowered or "only implemented" in lowered:
        return "unavailable"
    return "unavailable"


def source_revision(root: Path) -> str | None:
    try:
        return subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _humanize(value: str) -> str:
    special = {"OGRILA": "Ogri'la", "AHN_QIRAJ": "Ahn'Qiraj", "UN_GORO_CRATER": "Un'Goro Crater"}
    if value in special:
        return special[value]
    return " ".join(word.capitalize() for word in value.split("_"))
