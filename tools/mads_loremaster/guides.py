from __future__ import annotations

import json
import re
import shutil
from collections import Counter, defaultdict
from dataclasses import dataclass, field, replace
from math import hypot
from pathlib import Path

from .authored_route import load_authored_routes
from .model import Catalog, CatalogEntry, Quest
from .questie import load_flight_masters
from .scope import load_release
from .travel import load_travel_network, plan_travel
from .runtime_manifest import write_runtime_manifests

ADDON_NAME = "Mads_TBCLoremaster"
PRODUCT_TITLE = "Mad's TBC Loremaster"
GUIDE_GROUP = "Mad's Loremaster Guide"
PRIMARY_GROUP = f"{GUIDE_GROUP} - Primary Route"
ALTERNATIVE_GROUP = f"{GUIDE_GROUP} - Alternative Routes"
OPTIONAL_GROUP = f"{GUIDE_GROUP} - Optional Content"
INTERFACE = "20506"
MAX_LUA_LINES = 300
MAX_STEP_LINES = 270
MIN_CHAPTER_STEP_LINES = 90
MAX_BATCH_STARTER_DISTANCE = 15.0

AUBERDINE_FLIGHT_CHAIN = (6344, 6341, 6342)
AUBERDINE_DEFERRED_RETURN = 6343
AUBERDINE_FIRST_PICKUPS = (958, 983, 984, 1141, 2118, 4740)
QUEST_NAME_CLARIFICATIONS = {
    10766: (
        "Burning Crusade quest — ‘Cataclysm’ is the invasion point's name, "
        "not the later expansion."
    ),
}
CHOICE_STREAM_LABELS = {
    "aldor": "Aldor Alternative",
    "scryer": "Scryer Alternative",
    "scryer_choice_2": "Scryer Signet Alternative",
    "other_choices_1": "Choice Route A",
    "other_choices_2": "Choice Route B",
    "other_choices_3": "Choice Route C",
    "other_choices_4": "Choice Route D",
}
ONBOARDING_INSTRUCTIONS = (
    "Start here: use Primary Route for the main open-world journey; Optional Content holds "
    "group, class, reputation, and PvP chains. [O]",
    "Alternative Routes contain mutually exclusive outcomes. Read each choice preview before "
    "accepting a conflicting quest. [O]",
    "Already completed something? Guidelime hides completed quest steps, so select the chapter "
    "that matches your current progress. [O]",
    "This is a completionist route, not a speed-leveling route. Level gates favor nearby quests "
    "before a short local grind. [O]",
)
ENTRY_LOCATION_OVERRIDES = {
    # Questie's generic sort 25 groups the tier 0.5 dungeon-chain variants.
    # This Alliance branch obtains its component in Stratholme.
    8964: (2017, "Stratholme"),
}

REGISTER_RE = re.compile(
    r"Guidelime\.registerGuide\(\[\[(.*?)\]\],\s*[\"'](.*?)[\"']\s*\)", re.DOTALL
)
TAG_RE = re.compile(r"\[(QA|QC|QT)(\d+)(?:,\d+)?(?:\s[^\]]*)?\]")
NAME_RE = re.compile(r"\[N(?:\d+(?:-\d+)?)?\s*(.*?)\]")
NEXT_RE = re.compile(r"\[NX(?:\d+(?:-\d+)?)?\s*(.*?)\]")
INTERNAL_ENTITY_RE = re.compile(
    r"\b(?:quest credit|credit marker|quest trigger|invis(?:ible)?)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Operation:
    tag: str
    quest_id: int
    category: str
    quest_name: str
    item_use_id: int | None = None
    scripted_objective: bool = False
    quest_tag: str | None = None
    objective_hint: str | None = None
    endpoint_names: tuple[str, ...] = ()
    required_level: int = 10

    @property
    def line(self) -> str:
        name = _safe_player_text(self.quest_name)
        quest_tag = f"[{self.tag}{self.quest_id} {name}]"
        prefix = {
            "QA": "Accept",
            "QC": "Complete",
            "QT": "Turn in",
        }[self.tag]
        if self.tag == "QA":
            suffix = f" from {_format_choices(self.endpoint_names)}" if self.endpoint_names else ""
            clarification = QUEST_NAME_CLARIFICATIONS.get(self.quest_id)
            note = f" {clarification}" if clarification else ""
            return f"{_end_sentence(f'{prefix} {quest_tag}{suffix}')}{note}".rstrip()
        if self.tag == "QT":
            suffix = f" to {_format_choices(self.endpoint_names)}" if self.endpoint_names else ""
            return f"{prefix} {quest_tag}{suffix}"
        warning = ""
        if self.tag == "QC" and self.quest_tag == "Elite":
            warning = "Elite/group recommended — "
        elif self.tag == "QC" and self.quest_tag == "Escort":
            warning = "Escort — stay with the NPC. "
        elif self.tag == "QC" and self.quest_tag == "Heroic":
            warning = "Heroic dungeon — "
        elif self.tag == "QC" and self.category == "dungeon":
            warning = "Dungeon — "
        elif self.tag == "QC" and self.category == "raid":
            warning = "Raid — "
        if self.tag == "QC" and self.item_use_id:
            detail = f"Use the quest item [UI{self.item_use_id}-] as directed"
            if self.objective_hint:
                detail += f"; {_lower_first(self.objective_hint)}"
            return warning + detail + f". {quest_tag}"
        if self.tag == "QC" and self.scripted_objective:
            detail = "Complete the scripted or exploration event"
            if self.objective_hint:
                detail += f"; {_lower_first(self.objective_hint)}"
            return warning + detail + f". {quest_tag}"
        if self.tag == "QC" and self.objective_hint:
            return warning + f"{self.objective_hint}. {quest_tag}"
        return warning + f"{prefix} {quest_tag}"


@dataclass
class GuideFile:
    path: Path
    title: str
    next_title: str | None
    branch: str
    category: str
    operations: list[Operation]
    group: str
    minimum: int | None = None
    maximum: int | None = None
    semantic_steps: list["SemanticStep"] = field(default_factory=list)


@dataclass(frozen=True)
class SemanticStep:
    before_quest_id: int
    before_tag: str
    type: str
    instruction: str
    map_id: int
    map_name: str
    x: float | None
    y: float | None
    evidence_refs: tuple[str, ...]
    verification: str
    optional: bool = True
    required_level: int | None = None
    origin_map_id: int | None = None
    origin_map_name: str | None = None
    origin_x: float | None = None
    origin_y: float | None = None
    transport_link_ids: tuple[str, ...] = ()
    related_quest_ids: tuple[int, ...] = ()


def plan_operations(entries: list[CatalogEntry]) -> list[Operation]:
    selected = {entry.quest.id for entry in entries}
    order = {entry.quest.id: index for index, entry in enumerate(entries)}
    quests = {entry.quest.id: entry.quest for entry in entries}
    categories = {entry.quest.id: entry.category or "world" for entry in entries}
    names = {entry.quest.id: entry.quest.name for entry in entries}
    children: dict[int, set[int]] = defaultdict(set)
    for quest in quests.values():
        parent = quest.get("parent_quest")
        if parent in selected:
            children[parent].add(quest.id)
        for child in quest.get("child_quests", ()):
            if child in selected:
                children[quest.id].add(child)

    operations: list[Operation] = []
    accepted: set[int] = set()
    turned_in: set[int] = set()

    def operation(tag: str, quest_id: int) -> Operation:
        quest = quests[quest_id]
        item_use_id = None
        if tag == "QC" and _requires_item_instruction(quest):
            item_use_id = quest.get("source_item_id")
            if item_use_id is None:
                required = quest.get("required_source_items", ())
                if isinstance(required, list) and required:
                    item_use_id = required[0]
        return Operation(
            tag,
            quest_id,
            categories[quest_id],
            names[quest_id],
            int(item_use_id) if item_use_id is not None else None,
            tag == "QC" and bool(int(quest.get("special_flags", 0)) & 2),
            quest.tag_name,
            _objective_hint(quest) if tag == "QC" else None,
            _endpoint_names(
                quest.starter_sources if tag == "QA" else
                quest.finisher_sources if tag == "QT" else ()
            ),
            max(10, int(quest.get("required_level", 0))),
        )

    def accept(quest_id: int) -> None:
        if quest_id not in accepted:
            operations.append(operation("QA", quest_id))
            accepted.add(quest_id)

    def close_ready_parents() -> None:
        changed = True
        while changed:
            changed = False
            for parent in sorted(accepted - turned_in, key=lambda q: order[q], reverse=True):
                if not children.get(parent):
                    continue
                if all(child in turned_in for child in children[parent]):
                    operations.append(operation("QC", parent))
                    operations.append(operation("QT", parent))
                    turned_in.add(parent)
                    changed = True

    for entry in entries:
        quest_id = entry.quest.id
        if quest_id in turned_in:
            continue
        parent = entry.quest.get("parent_quest")
        if parent in selected:
            accept(parent)
        accept(quest_id)
        if not children.get(quest_id):
            operations.append(operation("QC", quest_id))
            operations.append(operation("QT", quest_id))
            turned_in.add(quest_id)
        close_ready_parents()

    # Malformed/cyclic child metadata must not make the generated guide incomplete.
    for quest_id in reversed([entry.quest.id for entry in entries]):
        if quest_id in accepted and quest_id not in turned_in:
            operations.append(operation("QC", quest_id))
            operations.append(operation("QT", quest_id))
            turned_in.add(quest_id)
    return _batch_independent_triplets(operations, quests)


def _requires_item_instruction(quest: Quest) -> bool:
    text = " ".join(str(value) for value in quest.get("objectives_text", ())).lower()
    mechanic = any(
        phrase in text
        for phrase in ("use ", "using ", "place ", "apply ", "plant ", "capture ", "release ", "summon ")
    )
    has_item = quest.get("source_item_id") is not None or bool(quest.get("required_source_items"))
    return mechanic and has_item


def _objective_hint(quest: Quest) -> str | None:
    grouped: dict[str, list[str]] = defaultdict(list)
    for source in quest.objective_sources:
        name = _player_facing_entity_name(source.name, source.kind)
        if name and name not in grouped[source.kind]:
            grouped[source.kind].append(name)
    present = [kind for kind in ("npc", "object", "item") if grouped[kind]]
    if not present:
        if quest.objective_sources:
            noun = "objective" if len(quest.objective_sources) == 1 else "objectives"
            return f"Complete the marked or scripted {noun}"
        return None
    if len(present) == 1:
        kind = present[0]
        names = grouped[kind]
        noun = "objective" if len(names) == 1 else "objectives"
        if kind == "npc":
            return f"Complete the required NPC or creature {noun}: {_format_names(names)}"
        if kind == "object":
            return f"Interact with the required {'object' if len(names) == 1 else 'objects'}: {_format_names(names)}"
        return f"Collect or use the required {'item' if len(names) == 1 else 'items'}: {_format_names(names)}"

    labels = {
        "npc": "NPCs or creatures",
        "object": "objects",
        "item": "items",
    }
    parts: list[str] = []
    for kind in ("npc", "object", "item"):
        names = grouped[kind]
        if not names:
            continue
        parts.append(f"{labels[kind]}: {_format_names(names)}")
    return "Complete the required objectives — " + "; ".join(parts)


def _safe_player_text(value: str) -> str:
    return " ".join(value.replace("[", "(").replace("]", ")").split())


def _player_facing_entity_name(value: str | None, kind: str) -> str | None:
    if not value:
        return None
    name = _safe_player_text(value)
    if kind != "item" and INTERNAL_ENTITY_RE.search(name):
        return None
    return name


def _format_names(names: list[str], maximum_names: int = 3, maximum_chars: int = 120) -> str:
    shown: list[str] = []
    for name in names:
        candidate = ", ".join([*shown, name])
        if shown and len(candidate) > maximum_chars:
            break
        shown.append(name)
        if len(shown) == maximum_names:
            break
    if not shown:
        shown.append(names[0][:maximum_chars].rstrip())
    remaining = len(names) - len(shown)
    result = ", ".join(shown)
    if remaining:
        result += f", plus {remaining} more"
    return result


def _format_player_list(names: list[str]) -> str:
    if len(names) <= 1:
        return names[0] if names else ""
    if len(names) == 2:
        return f"{names[0]} and {names[1]}"
    return ", ".join(names[:-1]) + f", and {names[-1]}"


def _endpoint_names(sources) -> tuple[str, ...]:
    result = []
    for source in sources:
        name = _player_facing_entity_name(source.name, source.kind)
        if name and name not in result:
            result.append(name)
    return tuple(result)


def _format_choices(names: tuple[str, ...], maximum_names: int = 2) -> str:
    shown = list(names[:maximum_names])
    if len(shown) == 1:
        return shown[0]
    if len(shown) == 2:
        result = f"{shown[0]} or {shown[1]}"
        if len(names) > maximum_names:
            result += f" (plus {len(names) - maximum_names} other source"
            result += "s)" if len(names) - maximum_names != 1 else ")"
        return result
    return ""


def _lower_first(value: str) -> str:
    return value[:1].lower() + value[1:]


def _upper_first(value: str) -> str:
    return value[:1].upper() + value[1:]


def _end_sentence(value: str) -> str:
    return value if value.endswith((".", "!", "?")) else value + "."


def _batch_independent_triplets(
    operations: list[Operation], quests: dict[int, Quest], maximum_batch: int = 6
) -> list[Operation]:
    """Batch adjacent independent quests while preserving the proven quest order.

    This is intentionally conservative: only complete QA/QC/QT triplets in the
    same Questie zone/category are grouped. Chain, parent, and phase ordering is
    unchanged, while hub sections gain useful multi-pickup/objective batches.
    """
    result: list[Operation] = []
    index = 0
    while index < len(operations):
        first = operations[index:index + 3]
        if not _is_triplet(first):
            result.append(operations[index])
            index += 1
            continue
        group = [first]
        zone = int(quests[first[0].quest_id].get("zone_or_sort", 0))
        cursor = index + 3
        while len(group) < maximum_batch:
            candidate = operations[cursor:cursor + 3]
            if not _is_triplet(candidate):
                break
            candidate_id = candidate[0].quest_id
            candidate_quest = quests[candidate_id]
            if candidate[0].category != first[0].category:
                break
            if int(candidate_quest.get("zone_or_sort", 0)) != zone:
                break
            grouped_ids = {triplet[0].quest_id for triplet in group}
            dependencies = set(candidate_quest.prerequisites_all) | set(candidate_quest.prerequisites_any)
            dependencies.update(
                value for value in (
                    candidate_quest.get("parent_quest"),
                    candidate_quest.get("available_starting_with"),
                ) if value
            )
            if dependencies & grouped_ids:
                break
            if not _starters_share_hub(
                [quests[triplet[0].quest_id] for triplet in group], candidate_quest
            ):
                break
            group.append(candidate)
            cursor += 3
        if len(group) == 1:
            result.extend(first)
        else:
            accepts = [triplet[0] for triplet in group]
            completes = [triplet[1] for triplet in group]
            turn_ins = [triplet[2] for triplet in group]
            result.extend(accepts)
            prior = _last_operation_point(accepts, quests)
            completes, prior = _nearest_endpoint_order(completes, quests, prior)
            turn_ins, _ = _nearest_endpoint_order(turn_ins, quests, prior)
            result.extend(completes)
            result.extend(turn_ins)
        index = cursor if len(group) > 1 else index + 3
    return result


def _operation_points(operation: Operation, quests: dict[int, Quest]) -> list:
    quest = quests[operation.quest_id]
    sources = (
        quest.starter_sources if operation.tag == "QA" else
        quest.objective_sources if operation.tag == "QC" else
        quest.finisher_sources
    )
    return [location for source in sources for location in source.locations]


def _nearest_point(points: list, prior):
    if not points:
        return None
    if prior is None:
        return min(points, key=lambda point: (point.map_id, point.x, point.y))
    same_map = [point for point in points if point.map_id == prior.map_id]
    if same_map:
        return min(
            same_map,
            key=lambda point: hypot(point.x - prior.x, point.y - prior.y),
        )
    return min(points, key=lambda point: (point.map_id, point.x, point.y))


def _last_operation_point(operations: list[Operation], quests: dict[int, Quest]):
    prior = None
    for operation in operations:
        point = _nearest_point(_operation_points(operation, quests), prior)
        if point is not None:
            prior = point
    return prior


def _nearest_endpoint_order(
    operations: list[Operation], quests: dict[int, Quest], prior
) -> tuple[list[Operation], object]:
    """Order independent batch operations by the closest structured endpoint."""
    remaining = list(enumerate(operations))
    ordered = []
    while remaining:
        ranked = []
        for original_index, operation in remaining:
            point = _nearest_point(_operation_points(operation, quests), prior)
            if point is None:
                key = (2, 0.0, original_index)
            elif prior is not None and point.map_id == prior.map_id:
                key = (0, hypot(point.x - prior.x, point.y - prior.y), original_index)
            else:
                key = (1, 0.0, original_index)
            ranked.append((key, original_index, operation, point))
        _, chosen_index, chosen, point = min(ranked, key=lambda item: item[0])
        ordered.append(chosen)
        remaining = [item for item in remaining if item[0] != chosen_index]
        if point is not None:
            prior = point
    return ordered, prior


def _is_triplet(operations: list[Operation]) -> bool:
    return (
        len(operations) == 3
        and [operation.tag for operation in operations] == ["QA", "QC", "QT"]
        and len({operation.quest_id for operation in operations}) == 1
    )


def _starters_share_hub(group: list[Quest], candidate: Quest) -> bool:
    existing = [
        location
        for quest in group
        for source in quest.starter_sources
        for location in source.locations
    ]
    incoming = [
        location
        for source in candidate.starter_sources
        for location in source.locations
    ]
    if not existing or not incoming:
        return True
    return any(
        left.map_id == right.map_id
        and hypot(left.x - right.x, left.y - right.y) <= MAX_BATCH_STARTER_DISTANCE
        for left in existing
        for right in incoming
    )


def _chunk_operations(
    operations: list[Operation],
    quests: dict[int, Quest],
    maximum_zones: int = 2,
    minimum_chapter_step_lines: int | None = MIN_CHAPTER_STEP_LINES,
) -> list[tuple[str, list[Operation]]]:
    chunks: list[tuple[str, list[Operation]]] = []
    current: list[Operation] = []
    zones: set[int] = set()

    def close() -> None:
        if not current:
            return
        categories = Counter(operation.category for operation in current if operation.tag == "QA")
        category = categories.most_common(1)[0][0] if categories else "world"
        chunks.append((category, list(current)))
        current.clear()
        zones.clear()

    for operation in operations:
        zone = int(quests[operation.quest_id].get("zone_or_sort", 0))
        if (
            operation.tag == "QA"
            and current
            and current[-1].tag == "QT"
            and (
                len(current) >= MAX_STEP_LINES
                or (zone not in zones and len(zones) >= maximum_zones)
                or (
                    minimum_chapter_step_lines is not None
                    and zone not in zones
                    and len(current) >= minimum_chapter_step_lines
                )
            )
        ):
            close()
        current.append(operation)
        if operation.tag == "QA":
            zones.add(zone)
        if len(current) >= MAX_STEP_LINES and operation.tag == "QT":
            close()
    close()
    return chunks


def _level_range(operations: list[Operation], quests: dict[int, Quest]) -> tuple[int, int]:
    levels = [max(10, int(quests[operation.quest_id].get("required_level", 0))) for operation in operations]
    return (min(levels, default=10), max(levels, default=70))


def _chapter_label(operations: list[Operation], quests: dict[int, Quest], catalog: Catalog) -> str:
    first_zone = next(
        (
            int(quests[operation.quest_id].get("zone_or_sort", 0))
            for operation in operations
            if operation.tag == "QA"
        ),
        None,
    )
    first_name = catalog.zones.get(first_zone, "") if first_zone is not None else ""
    zones = Counter(
        int(quests[operation.quest_id].get("zone_or_sort", 0))
        for operation in operations
        if operation.tag == "QA"
    )
    named = [
        (catalog.zones.get(zone, ""), count)
        for zone, count in zones.most_common()
        if catalog.zones.get(zone)
    ]
    if named:
        total = sum(zones.values())
        if len(named) == 1 or named[0][1] >= total * 0.6:
            if first_name and first_name != named[0][0]:
                return f"{first_name} & {named[0][0]}"
            return named[0][0]
        return f"{named[0][0]} & {named[1][0]}"
    categories = Counter(operation.category for operation in operations if operation.tag == "QA")
    return (categories.most_common(1)[0][0] if categories else "quests").replace("_", " ").title()


def _choice_anchor_names(
    operations: list[Operation],
    quests: dict[int, Quest],
) -> list[str]:
    names: list[str] = []
    for operation in operations:
        if operation.tag != "QA" or not quests[operation.quest_id].exclusive_to:
            continue
        name = _safe_player_text(operation.quest_name)
        if name not in names:
            names.append(name)
    return names


def _choice_chapter_label(
    operations: list[Operation],
    quests: dict[int, Quest],
    catalog: Catalog,
) -> str:
    anchors = _choice_anchor_names(operations, quests)
    if not anchors:
        return _chapter_label(operations, quests, catalog)
    selected = anchors[:2]
    label = " & ".join(selected)
    if len(anchors) > len(selected):
        label += " + More Choices"
    return label


def _extract_auberdine_opening(operations: list[Operation]) -> tuple[list[Operation], list[Operation]]:
    by_state = {(operation.quest_id, operation.tag): operation for operation in operations}
    opening: list[Operation] = []
    required_states = []
    for quest_id in AUBERDINE_FLIGHT_CHAIN:
        required_states.extend((quest_id, tag) for tag in ("QA", "QC", "QT"))
    required_states.append((AUBERDINE_DEFERRED_RETURN, "QA"))
    required_states.extend((quest_id, "QA") for quest_id in AUBERDINE_FIRST_PICKUPS)
    missing = [state for state in required_states if state not in by_state]
    if missing:
        raise ValueError(f"Auberdine opening quests are not on the primary route: {missing}")
    for quest_id in AUBERDINE_FLIGHT_CHAIN:
        opening.extend(by_state[(quest_id, tag)] for tag in ("QA", "QC", "QT"))
    opening.append(by_state[(AUBERDINE_DEFERRED_RETURN, "QA")])
    opening.extend(by_state[(quest_id, "QA")] for quest_id in AUBERDINE_FIRST_PICKUPS)
    extracted = {(operation.quest_id, operation.tag) for operation in opening}
    remaining = [
        operation
        for operation in operations
        if (operation.quest_id, operation.tag) not in extracted
    ]
    return opening, remaining


def generate_addon(catalog: Catalog, project_root: Path) -> list[GuideFile]:
    release = load_release(project_root / "config" / "release.json")
    guides_root = project_root / "Guides"
    if guides_root.exists():
        shutil.rmtree(guides_root)
    guides_root.mkdir(parents=True)

    primary = catalog.selected("covered_primary")
    optional = catalog.selected("covered_optional")
    alternatives: dict[str, list[CatalogEntry]] = defaultdict(list)
    for entry in catalog.selected("covered_alternative"):
        alternatives[entry.branch or "other_choices"].append(entry)

    streams: list[tuple[str, str, str, list[CatalogEntry]]] = [
        ("Primary", "primary", PRIMARY_GROUP, primary),
        ("Optional Content", "optional_content", OPTIONAL_GROUP, optional),
    ]
    branch_order = sorted(
        alternatives,
        key=lambda branch: (
            0 if branch.startswith("aldor") else 1 if branch.startswith("scryer") else 2,
            branch,
        ),
    )
    for branch in branch_order:
        label = CHOICE_STREAM_LABELS.get(branch, branch.replace("_", " ").title())
        streams.append((label, branch, ALTERNATIVE_GROUP, alternatives[branch]))

    all_guides: list[GuideFile] = []
    quests = {entry.quest.id: entry.quest for entry in catalog.entries.values()}
    sequence = 0
    for stream_label, branch, group, entries in streams:
        operations = plan_operations(entries)
        opening: list[Operation] | None = None
        if branch == "primary":
            opening, operations = _extract_auberdine_opening(operations)
        chunks = _chunk_operations(
            operations,
            quests,
            maximum_zones=2 if branch == "primary" else 3,
            minimum_chapter_step_lines=MIN_CHAPTER_STEP_LINES if branch == "primary" else None,
        )
        if opening:
            chunks.insert(0, ("world", opening))
        stream_guides: list[GuideFile] = []
        for part, (category, chunk) in enumerate(chunks, 1):
            sequence += 1
            label = (
                "Auberdine - Arrival & First Pickups"
                if branch == "primary" and part == 1
                else _choice_chapter_label(chunk, quests, catalog)
                if branch.startswith("other_choices_")
                else _chapter_label(chunk, quests, catalog)
            )
            title = (
                f"{part:02d} {label}"
                if branch == "primary"
                else f"{stream_label} {part:02d} - {label}"
            )
            relative = Path("Guides") / branch / f"{sequence:03d}_{category}_{part:02d}.lua"
            stream_guides.append(
                GuideFile(project_root / relative, title, None, branch, category, chunk, group)
            )
        if branch == "primary":
            previous_minimum = 10
            previous_maximum = 10
            for guide in stream_guides:
                actual_minimum, actual_maximum = _level_range(guide.operations, quests)
                guide.minimum = max(previous_minimum, actual_minimum)
                guide.maximum = max(guide.minimum, actual_maximum)
                if guide.minimum == previous_minimum:
                    guide.maximum = max(previous_maximum, guide.maximum)
                previous_minimum = guide.minimum
                previous_maximum = guide.maximum
        for index, guide in enumerate(stream_guides[:-1]):
            guide.next_title = stream_guides[index + 1].title
        all_guides.extend(stream_guides)

    _attach_chapter_entry_steps(catalog, all_guides, quests)
    _attach_travel_transition_steps(catalog, project_root, all_guides, quests)
    _attach_retention_steps(catalog, all_guides, quests)
    _attach_flight_path_steps(catalog, project_root, all_guides, quests)
    _assign_route_required_levels(catalog, all_guides, quests)
    _attach_player_experience_steps(catalog, all_guides, quests)
    _attach_level_gate_steps(catalog, all_guides, quests)

    # Primary navigation is linear through all default content. Alternative
    # streams are deliberately selectable and only link within their branch.
    for guide in all_guides:
        guide.path.parent.mkdir(parents=True, exist_ok=True)
        if guide.branch == "primary":
            description = (
                "Main solo and open-world completion route. Start after the documented level 1-9 "
                "Teldrassil baseline."
            )
        elif guide.branch == "optional_content":
            description = (
                "Optional completionist route. Enter after the relevant primary prerequisites; "
                "dungeon, raid, class, reputation, and PvP gates are explicit."
            )
        else:
            description = (
                "Mutually exclusive alternative. Choose before completing its conflicting "
                "default outcome and satisfy any listed primary or optional prerequisites."
            )
        lines = [
            "Guidelime.registerGuide([[",
            f"[D Mad's Phase {catalog.phase_profile.get('phase')} {catalog.phase_profile.get('name')} "
            f"Loremaster route. {description}]",
        ]
        if guide.minimum is not None and guide.maximum is not None:
            lines.append(f"[N{guide.minimum}-{guide.maximum} {guide.title}]")
        else:
            lines.append(f"[N {guide.title}]")
        if guide.next_title:
            next_guide = next(item for item in all_guides if item.title == guide.next_title)
            if next_guide.minimum is not None and next_guide.maximum is not None:
                lines.append(f"[NX{next_guide.minimum}-{next_guide.maximum} {guide.next_title}]")
            else:
                lines.append(f"[NX {guide.next_title}]")
        semantic_by_operation: dict[tuple[int, str], list[SemanticStep]] = defaultdict(list)
        for semantic in guide.semantic_steps:
            semantic_by_operation[(semantic.before_quest_id, semantic.before_tag)].append(semantic)
        for operation in guide.operations:
            lines.extend(
                semantic.instruction
                for semantic in semantic_by_operation[(operation.quest_id, operation.tag)]
            )
            lines.append(operation.line)
        lines.append(f"]], \"{guide.group}\")")
        guide.path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    _write_route_specs(catalog, project_root, all_guides, quests)
    runtime_manifests = write_runtime_manifests(catalog, project_root)

    toc_lines = [
        f"## Interface: {INTERFACE}",
        f"## Title: {PRODUCT_TITLE}",
        "## Author: Mad",
        f"## Version: {release['version']}",
        f"## Notes: Phase-aware Alliance quest completion, catch-up, routing, and lore for TBC Anniversary.",
        "## RequiredDeps: Questie",
        "## OptionalDeps: TomTom, Guidelime",
        "## SavedVariables: MadsTBCLoremasterDB",
        "## SavedVariablesPerCharacter: MadsTBCLoremasterCharacterDB",
        f"## X-Release-Channel: {release['channel']}",
        f"## X-Static-Release-Gate: {'true' if release['static_release_gate_ready'] else 'false'}",
        f"## X-Public-Release-Ready: {'true' if release['public_release_ready'] else 'false'}",
        "## X-Questie-Required: true",
        "## X-TomTom-Optional: true",
        "",
    ]
    for manifest in runtime_manifests:
        toc_lines.append(str(manifest.relative_to(project_root)).replace("/", "\\"))
    toc_lines.extend([
        "Data\\Lore.lua",
        "Runtime\\Core.lua",
        "Runtime\\Character.lua",
        "Runtime\\Eligibility.lua",
        "Runtime\\Router.lua",
        "Runtime\\Navigation.lua",
        "Runtime\\GuideCompat.lua",
        "Runtime\\UI.lua",
    ])
    for guide in all_guides:
        toc_lines.append(str(guide.path.relative_to(project_root)).replace("/", "\\"))
    (project_root / f"{ADDON_NAME}.toc").write_text("\n".join(toc_lines) + "\n", encoding="utf-8")

    baseline = [entry.to_dict() for entry in catalog.selected("baseline_completed")]
    config = project_root / "config"
    config.mkdir(exist_ok=True)
    (config / "baseline_teldrassil_1_9.json").write_text(
        json.dumps({"assumption": "ordinary Night Elf Teldrassil level 1-9 quests completed", "quests": baseline}, indent=2) + "\n",
        encoding="utf-8",
    )
    (config / "source.json").write_text(
        json.dumps({"questie_path": catalog.source_path, "questie_revision": catalog.source_revision}, indent=2) + "\n",
        encoding="utf-8",
    )
    return all_guides


def _external_prerequisites(
    guide: GuideFile,
    branch_ids: set[int],
    catalog: Catalog,
    quests: dict[int, Quest],
) -> tuple[set[int], list[tuple[int, ...]]]:
    required_all: set[int] = set()
    required_any: list[tuple[int, ...]] = []
    for operation in guide.operations:
        quest = quests[operation.quest_id]
        hard_dependencies = set(quest.prerequisites_all)
        hard_dependencies.update(
            dependency
            for dependency in (
                quest.get("parent_quest"),
                quest.get("available_starting_with"),
            )
            if dependency
        )
        required_all.update(
            dependency
            for dependency in hard_dependencies
            if dependency not in branch_ids
            and dependency in catalog.entries
            and catalog.entries[dependency].status.startswith("covered")
        )
        any_dependencies = set(quest.prerequisites_any)
        if not any_dependencies or any_dependencies & branch_ids:
            continue
        group = tuple(sorted(
            dependency
            for dependency in any_dependencies
            if dependency in catalog.entries
            and catalog.entries[dependency].status.startswith("covered")
        ))
        if set(group) == {10551, 10552}:
            if guide.branch.startswith("aldor"):
                group = (10551,)
            elif guide.branch.startswith("scryer"):
                group = (10552,)
        if group and group not in required_any:
            required_any.append(group)
    required_any = [
        tuple(dependency for dependency in group if dependency not in required_all)
        for group in required_any
    ]
    required_any = [group for group in required_any if group]
    required_any = [
        group
        for group in required_any
        if not any(set(other) < set(group) for other in required_any)
    ]
    return required_all, required_any


def _format_prerequisite_clause(
    required_all: set[int],
    required_any: list[tuple[int, ...]],
    quests: dict[int, Quest],
) -> str:
    clauses = []
    if required_all:
        names = list(dict.fromkeys(
            _safe_player_text(quests[quest_id].name) for quest_id in sorted(required_all)
        ))
        clauses.append(f"complete {_format_player_list(names)}")
    for group in required_any:
        names = list(dict.fromkeys(
            _safe_player_text(quests[quest_id].name) for quest_id in group
        ))
        clauses.append(
            f"complete either available version of {names[0]}"
            if len(names) == 1 and len(group) > 1
            else f"complete {names[0]}" if len(names) == 1
            else f"complete either {' or '.join(names)}"
        )
    return "; ".join(clauses) if clauses else "complete the relevant shared prerequisites"


def _attach_chapter_entry_steps(
    catalog: Catalog,
    guides: list[GuideFile],
    quests: dict[int, Quest],
) -> None:
    branch_quest_ids: dict[str, set[int]] = defaultdict(set)
    for item in guides:
        branch_quest_ids[item.branch].update(
            operation.quest_id for operation in item.operations
        )
    for guide in guides:
        first_accept = next(
            (operation for operation in guide.operations if operation.tag == "QA"),
            None,
        )
        if first_accept is None:
            continue
        quest = quests[first_accept.quest_id]
        starter_locations = [
            location
            for source in quest.starter_sources
            for location in source.locations
        ]
        finisher_locations = [
            location
            for source in quest.finisher_sources
            for location in source.locations
        ]
        objective_locations = [
            location
            for source in quest.objective_sources
            for location in source.locations
        ]
        location_kind = "starter"
        locations = starter_locations
        if not locations:
            location_kind = "finisher"
            locations = finisher_locations
        if not locations:
            location_kind = "objective"
            locations = objective_locations
        location = locations[0] if locations else None
        override = ENTRY_LOCATION_OVERRIDES.get(quest.id)
        map_id = location.map_id if location is not None else (
            override[0] if override else int(quest.get("zone_or_sort", 0))
        )
        map_name = catalog.zones.get(
            map_id,
            location.map_name if location is not None else (
                override[1] if override else f"Map or sort {map_id}"
            ),
        )
        waypoint = (
            f"[G{location.x:.2f},{location.y:.2f} {map_name}]"
            if location is not None else map_name
        )
        required_all, required_any = _external_prerequisites(
            guide,
            branch_quest_ids[guide.branch],
            catalog,
            quests,
        )
        prerequisite_clause = _format_prerequisite_clause(
            required_all,
            required_any,
            quests,
        )
        if guide.branch != "primary":
            if guide.branch == "optional_content":
                branch_instruction = (
                    f"Optional entry requirements: {prerequisite_clause}. [O]"
                )
            else:
                branch_instruction = (
                    f"Alternative entry requirements: {prerequisite_clause}. Choose this branch "
                    "before its conflicting default. [O]"
                )
            related_ids = tuple(sorted(
                required_all | {
                    dependency for group in required_any for dependency in group
                }
            ))
            guide.semantic_steps.append(
                SemanticStep(
                    first_accept.quest_id,
                    "QA",
                    "branch_entry",
                    branch_instruction,
                    map_id,
                    map_name,
                    location.x if location is not None else None,
                    location.y if location is not None else None,
                    tuple(
                        f"questie:{catalog.source_revision or 'local'}:quest:{quest_id}:dependency"
                        for quest_id in related_ids
                    ) or (f"route-branch:{guide.branch}",),
                    "route_dependency_graph",
                    related_quest_ids=related_ids,
                )
            )
        if guide.branch == "primary" and guide.title.startswith("01 "):
            instruction = (
                f"Begin in {map_name} at {waypoint} after completing the documented level 1-9 "
                "Teldrassil baseline. Leave at least two quest-log slots open. [O]"
            )
        elif guide.branch == "primary" and location_kind == "starter":
            instruction = (
                f"Before you begin: travel to {map_name} and meet the first quest giver at "
                f"{waypoint}. Leave at least two quest-log slots open. [O]"
            )
        elif guide.branch == "primary":
            instruction = (
                f"Before you begin: travel to {map_name} and continue from the first verified "
                f"route point at {waypoint}. Leave at least two quest-log slots open. [O]"
            )
        elif guide.branch == "optional_content" and location is not None:
            instruction = (
                f"Optional chapter: travel to {map_name} and begin at {waypoint}. Leave at least "
                "two quest-log "
                "slots open. [O]"
            )
        elif guide.branch == "optional_content":
            instruction = (
                f"Optional chapter: enter {map_name}. "
                "Leave at least two quest-log slots open. [O]"
            )
        elif location is not None:
            instruction = (
                f"Alternative chapter: travel to {map_name} and begin at {waypoint}. Leave at "
                "least two quest-log slots open. [O]"
            )
        else:
            instruction = (
                f"Alternative chapter: enter {map_name}. Leave at least two quest-log slots "
                "open. [O]"
            )
        guide.semantic_steps.append(
            SemanticStep(
                first_accept.quest_id,
                "QA",
                "chapter_entry",
                instruction,
                map_id,
                map_name,
                location.x if location is not None else None,
                location.y if location is not None else None,
                (f"questie:{catalog.source_revision or 'local'}:quest:{quest.id}:{location_kind}",),
                "questie_structured_source_only",
            )
        )


def _attach_travel_transition_steps(
    catalog: Catalog,
    project_root: Path,
    guides: list[GuideFile],
    quests: dict[int, Quest],
) -> None:
    """Connect adjacent chapters without blocking resumed characters.

    Questie supplies the route endpoints. Cross-continent methods come from the
    reviewed TBC transport network; local travel remains conditional on the
    character's known flight paths and current position.
    """
    links = load_travel_network(project_root / "config" / "travel_network.json")
    previous_by_branch: dict[str, GuideFile] = {}
    for guide in guides:
        previous = previous_by_branch.get(guide.branch)
        previous_by_branch[guide.branch] = guide
        if previous is None or not guide.operations:
            continue
        chapter_entry = next(
            (step for step in guide.semantic_steps if step.type == "chapter_entry"),
            None,
        )
        if chapter_entry is None:
            continue
        origin_operation, origin = _last_mapped_operation(previous, quests)
        if origin_operation is not None and origin is not None:
            origin_map_id = origin.map_id
            origin_map_name = origin.map_name
            origin_x = origin.x
            origin_y = origin.y
            origin_evidence = (
                f"questie:{catalog.source_revision or 'local'}:quest:"
                f"{origin_operation.quest_id}:{origin_operation.tag}",
            )
        else:
            previous_entry = next(
                (step for step in previous.semantic_steps if step.type == "chapter_entry"),
                None,
            )
            if previous_entry is None:
                continue
            origin_map_id = previous_entry.map_id
            origin_map_name = previous_entry.map_name
            origin_x = previous_entry.x
            origin_y = previous_entry.y
            origin_evidence = previous_entry.evidence_refs
        travel = plan_travel(origin_map_id, chapter_entry.map_id, links)
        destination = (
            f"[G{chapter_entry.x:.2f},{chapter_entry.y:.2f} {chapter_entry.map_name}]"
            if chapter_entry.x is not None and chapter_entry.y is not None
            else chapter_entry.map_name
        )
        if travel.type == "transport":
            instruction = (
                f"Travel from {origin_map_name} to {chapter_entry.map_name}: "
                f"{travel.instruction}. Continue to {destination}. [O]"
            )
            verification = "questie_endpoints_and_tbc_transport_network"
        elif origin_map_id == chapter_entry.map_id:
            instruction = (
                f"Continue within {chapter_entry.map_name} to the next route hub at "
                f"{destination}. [O]"
            )
            verification = "questie_structured_route_points"
        else:
            instruction = (
                f"Travel from {origin_map_name} to {chapter_entry.map_name}. "
                f"{travel.instruction}. Continue to {destination}. [O]"
            )
            verification = "questie_structured_route_points"
        first_operation = guide.operations[0]
        evidence_refs = (
            *origin_evidence,
            *chapter_entry.evidence_refs,
            *(f"travel-network:{link_id}" for link_id in travel.link_ids),
            *travel.evidence,
        )
        guide.semantic_steps.insert(
            0,
            SemanticStep(
                first_operation.quest_id,
                first_operation.tag,
                travel.type,
                instruction,
                chapter_entry.map_id,
                chapter_entry.map_name,
                chapter_entry.x,
                chapter_entry.y,
                evidence_refs,
                verification,
                origin_map_id=origin_map_id,
                origin_map_name=origin_map_name,
                origin_x=origin_x,
                origin_y=origin_y,
                transport_link_ids=travel.link_ids,
            ),
        )


def _last_mapped_operation(
    guide: GuideFile,
    quests: dict[int, Quest],
):
    for operation in reversed(guide.operations):
        quest = quests[operation.quest_id]
        sources = (
            quest.starter_sources if operation.tag == "QA" else
            quest.objective_sources if operation.tag == "QC" else
            quest.finisher_sources
        )
        locations = [location for source in sources for location in source.locations]
        if locations:
            return operation, locations[0]
    return None, None


def _attach_retention_steps(
    catalog: Catalog,
    guides: list[GuideFile],
    quests: dict[int, Quest],
) -> None:
    """Name every quest intentionally carried across a chapter boundary."""
    by_branch: dict[str, list[GuideFile]] = defaultdict(list)
    for guide in guides:
        by_branch[guide.branch].append(guide)
    for branch_guides in by_branch.values():
        accepted_in: dict[int, int] = {}
        turned_in: dict[int, int] = {}
        for guide_index, guide in enumerate(branch_guides):
            for operation in guide.operations:
                if operation.tag == "QA":
                    accepted_in[operation.quest_id] = guide_index
                elif operation.tag == "QT":
                    turned_in[operation.quest_id] = guide_index
        retained_by_guide: dict[int, list[int]] = defaultdict(list)
        for quest_id, accepted_index in accepted_in.items():
            turn_in_index = turned_in.get(quest_id, accepted_index)
            for guide_index in range(accepted_index + 1, turn_in_index + 1):
                retained_by_guide[guide_index].append(quest_id)
        for guide_index, quest_ids in retained_by_guide.items():
            guide = branch_guides[guide_index]
            if not guide.operations:
                continue
            chapter_entry = next(
                (step for step in guide.semantic_steps if step.type == "chapter_entry"),
                None,
            )
            if chapter_entry is None:
                continue
            quest_ids = sorted(quest_ids, key=lambda quest_id: accepted_in[quest_id])
            names = [_safe_player_text(quests[quest_id].name) for quest_id in quest_ids]
            instruction = (
                "Keep these quests in your log; they continue in this chapter: "
                f"{_format_player_list(names)}. [O]"
            )
            first_operation = guide.operations[0]
            guide.semantic_steps.append(
                SemanticStep(
                    first_operation.quest_id,
                    first_operation.tag,
                    "retain",
                    instruction,
                    chapter_entry.map_id,
                    chapter_entry.map_name,
                    chapter_entry.x,
                    chapter_entry.y,
                    tuple(
                        f"questie:{catalog.source_revision or 'local'}:quest:{quest_id}:route-state"
                        for quest_id in quest_ids
                    ),
                    "route_state_simulation",
                    related_quest_ids=tuple(quest_ids),
                )
            )


def _choice_preview(
    guide: GuideFile,
    catalog: Catalog,
    quests: dict[int, Quest],
) -> tuple[str, tuple[int, ...]]:
    if guide.branch == "aldor":
        return (
            "Choice preview: this chapter continues the Aldor outcome selected by the primary "
            "route and excludes Scryer-only quests. [O]",
            (10551,),
        )
    if guide.branch == "scryer":
        return (
            "Choice preview: this route chooses the Scryers instead of the primary route's Aldor "
            "outcome. Select it before accepting Allegiance to the Aldor. [O]",
            (10551, 10552),
        )
    if guide.branch == "scryer_choice_2":
        return (
            "Choice preview: this Scryer-only signet outcome replaces the Aldor version. Complete "
            "Allegiance to the Scryers first. [O]",
            (10551, 10552, 10824),
        )

    choices: list[tuple[int, str, list[str]]] = []
    seen_names: set[str] = set()
    for operation in guide.operations:
        quest = quests[operation.quest_id]
        name = _safe_player_text(quest.name)
        if operation.tag != "QA" or not quest.exclusive_to or name in seen_names:
            continue
        conflict_names = list(dict.fromkeys(
            _safe_player_text(quests[quest_id].name)
            for quest_id in quest.exclusive_to
            if quest_id in quests
        ))
        choices.append((quest.id, name, conflict_names))
        seen_names.add(name)
    if not choices:
        return (
            "Choice preview: this chapter contains an alternative outcome. Complete it only if "
            "you intend to replace the conflicting default. [O]",
            (),
        )

    first_id, first_name, conflicts = choices[0]
    if conflicts and all(name == first_name for name in conflicts):
        first_clause = f"this version of {first_name} replaces its other available versions"
    elif len(conflicts) == 1:
        first_clause = f"{first_name} replaces {conflicts[0]}"
    elif conflicts:
        first_clause = f"{first_name} replaces one of its alternate quest outcomes"
    else:
        first_clause = f"{first_name} replaces its conflicting default"
    remaining = [name for _, name, _ in choices[1:3]]
    if remaining:
        remaining_clause = f" Also included: {', '.join(remaining)}"
        extra = len(choices) - 1 - len(remaining)
        if extra:
            remaining_clause += f", plus {extra} more mutually exclusive outcome"
            if extra != 1:
                remaining_clause += "s"
        remaining_clause = " " + _end_sentence(remaining_clause.strip())
    else:
        remaining_clause = ""
    instruction = (
        f"Choice preview: {first_clause}.{remaining_clause} Choose only the outcomes you want. [O]"
    )
    related_ids = tuple(dict.fromkeys(
        [
            quest_id
            for selected_id, _, _ in choices
            for quest_id in (selected_id, *quests[selected_id].exclusive_to)
            if quest_id in catalog.entries
        ]
    ))
    return instruction, related_ids


def _semantic_context(
    catalog: Catalog,
    guide: GuideFile,
    operation: Operation,
    quests: dict[int, Quest],
) -> tuple[int, str, float | None, float | None]:
    quest = quests[operation.quest_id]
    sources = (
        quest.starter_sources if operation.tag == "QA" else
        quest.objective_sources if operation.tag == "QC" else
        quest.finisher_sources
    )
    locations = [location for source in sources for location in source.locations]
    if locations:
        location = locations[0]
        return location.map_id, location.map_name, location.x, location.y
    chapter_entry = next(
        (step for step in guide.semantic_steps if step.type == "chapter_entry"),
        None,
    )
    if chapter_entry is not None:
        return chapter_entry.map_id, chapter_entry.map_name, chapter_entry.x, chapter_entry.y
    map_id = int(quest.get("zone_or_sort", 0))
    return map_id, catalog.zones.get(map_id, f"Map or sort {map_id}"), None, None


def _attach_player_experience_steps(
    catalog: Catalog,
    guides: list[GuideFile],
    quests: dict[int, Quest],
) -> None:
    """Add optional clarity and encouragement without blocking route resumption."""
    primary_guides = [guide for guide in guides if guide.branch == "primary"]
    if not primary_guides:
        return

    first_guide = primary_guides[0]
    first_operation = first_guide.operations[0]
    map_id, map_name, x, y = _semantic_context(
        catalog, first_guide, first_operation, quests
    )
    onboarding = [
        SemanticStep(
            first_operation.quest_id,
            first_operation.tag,
            "onboarding",
            instruction,
            map_id,
            map_name,
            x,
            y,
            (f"ux-policy:onboarding:{index}",),
            "player_experience_policy",
        )
        for index, instruction in enumerate(ONBOARDING_INSTRUCTIONS, 1)
    ]
    first_guide.semantic_steps[0:0] = onboarding

    for guide in guides:
        first_accept = next(
            (operation for operation in guide.operations if operation.tag == "QA"),
            None,
        )
        if first_accept is None:
            continue
        if guide.branch not in {"primary", "optional_content"}:
            instruction, related_ids = _choice_preview(guide, catalog, quests)
            map_id, map_name, x, y = _semantic_context(
                catalog, guide, first_accept, quests
            )
            guide.semantic_steps.append(
                SemanticStep(
                    first_accept.quest_id,
                    first_accept.tag,
                    "choice_preview",
                    instruction,
                    map_id,
                    map_name,
                    x,
                    y,
                    tuple(
                        f"questie:{catalog.source_revision or 'local'}:quest:{quest_id}:exclusiveTo"
                        for quest_id in related_ids
                    ) or (f"route-branch:{guide.branch}:choice-preview",),
                    "route_exclusivity_graph",
                    related_quest_ids=related_ids,
                )
            )

        dangerous = [
            operation
            for operation in guide.operations
            if operation.tag == "QC"
            and (
                operation.quest_tag in {"Elite", "Escort", "Heroic"}
                or operation.category in {"dungeon", "raid"}
            )
        ]
        if dangerous:
            first_danger = dangerous[0]
            has_escort = any(operation.quest_tag == "Escort" for operation in dangerous)
            has_group = any(operation.quest_tag != "Escort" for operation in dangerous)
            if has_group and has_escort:
                instruction = (
                    "Group content unavailable? Switch chapters and return later; keep the quest "
                    "and any active parent quest. If an escort fails, wait for the NPC to reset "
                    "before retrying. [O]"
                )
            elif has_escort:
                instruction = (
                    "Escort failed or still resetting? Wait for the NPC to return, or switch "
                    "chapters and retry later; keep the quest and any active parent quest. [O]"
                )
            else:
                instruction = (
                    "No group available? Switch chapters and return later; keep the quest and any "
                    "active parent quest in your log. [O]"
                )
            map_id, map_name, x, y = _semantic_context(
                catalog, guide, first_danger, quests
            )
            guide.semantic_steps.append(
                SemanticStep(
                    first_danger.quest_id,
                    first_danger.tag,
                    "recovery",
                    instruction,
                    map_id,
                    map_name,
                    x,
                    y,
                    (
                        f"questie:{catalog.source_revision or 'local'}:quest:"
                        f"{first_danger.quest_id}:difficulty",
                        "ux-policy:recoverable-group-content",
                    ),
                    "questie_difficulty_and_route_recovery_policy",
                    related_quest_ids=(first_danger.quest_id,),
                )
            )

    chapter_entries = {
        id(guide): next(
            (step for step in guide.semantic_steps if step.type == "chapter_entry"),
            None,
        )
        for guide in primary_guides
    }
    outland_guide = next(
        (
            guide for guide in primary_guides
            if chapter_entries[id(guide)] is not None
            and chapter_entries[id(guide)].map_name == "Hellfire Peninsula"
        ),
        None,
    )
    shattrath_guide = next(
        (
            guide for guide in primary_guides
            if chapter_entries[id(guide)] is not None
            and chapter_entries[id(guide)].map_name == "Shattrath City"
        ),
        None,
    )
    level_70_guide = next(
        (guide for guide in primary_guides if (guide.minimum or 0) >= 70),
        None,
    )
    milestone_targets = [
        (
            "journey-start",
            first_guide,
            first_guide.operations[0],
            "Milestone: your completionist journey begins here. Follow Primary Route in order, "
            "and visit Optional Content whenever you want a side path. [O]",
        ),
        (
            "outland",
            outland_guide,
            outland_guide.operations[0] if outland_guide else None,
            "Milestone: welcome to Outland. Hellfire Peninsula begins the next leg of the journey "
            "beyond the Dark Portal. [O]",
        ),
        (
            "shattrath",
            shattrath_guide,
            shattrath_guide.operations[0] if shattrath_guide else None,
            "Milestone: Shattrath is your central Outland hub. Primary Route chooses the Aldor; "
            "choose Scryer Alternative before accepting Allegiance to the Aldor if you prefer "
            "the Scryers. [O]",
        ),
        (
            "level-70",
            level_70_guide,
            level_70_guide.operations[0] if level_70_guide else None,
            "Milestone: level 70 begins the final primary chapters. Optional group and reputation "
            "routes remain available whenever you want them. [O]",
        ),
        (
            "primary-finale",
            primary_guides[-1],
            primary_guides[-1].operations[-1],
            "Final primary-route turn-in ahead. After it, open Optional Content and Alternative "
            "Routes for remaining one-time group chains and mutually exclusive outcomes. [O]",
        ),
    ]
    for milestone_id, guide, operation, instruction in milestone_targets:
        if guide is None or operation is None:
            raise ValueError(f"unable to place player milestone {milestone_id}")
        map_id, map_name, x, y = _semantic_context(catalog, guide, operation, quests)
        guide.semantic_steps.append(
            SemanticStep(
                operation.quest_id,
                operation.tag,
                "milestone",
                instruction,
                map_id,
                map_name,
                x,
                y,
                (f"ux-policy:milestone:{milestone_id}",),
                "player_experience_policy",
            )
        )


def _attach_flight_path_steps(
    catalog: Catalog,
    project_root: Path,
    guides: list[GuideFile],
    quests: dict[int, Quest],
) -> None:
    routes = load_authored_routes(project_root / "config" / "authored_routes.json")
    flight_masters = load_flight_masters(Path(catalog.source_path), catalog.zones)
    candidates = []
    sequence = 0
    for guide in guides:
        if guide.branch != "primary":
            continue
        for operation in guide.operations:
            sequence += 1
            quest = quests[operation.quest_id]
            sources = (
                quest.starter_sources if operation.tag == "QA" else
                quest.objective_sources if operation.tag == "QC" else
                quest.finisher_sources
            )
            locations = [
                location
                for source in sources
                for location in source.locations
            ]
            candidates.append((sequence, guide, operation.quest_id, operation.tag, locations))

    matched_masters: set[int] = set()
    for route in routes:
        for point in route.flight_points:
            if not _flight_point_applies(point.get("applies_to", ())):
                continue
            master_match = _match_flight_master(point, flight_masters)
            if master_match is None:
                continue
            master_id, master, location = master_match
            if master_id in matched_masters:
                continue
            same_map = [
                item for item in candidates
                if any(candidate.map_id == location.map_id for candidate in item[4])
            ]
            if not same_map:
                continue

            def distance(item) -> float:
                return min(
                    (
                        hypot(candidate.x - location.x, candidate.y - location.y)
                        for candidate in item[4]
                        if candidate.map_id == location.map_id
                    ),
                    default=float("inf"),
                )

            nearby = [item for item in same_map if distance(item) <= 15]
            _, guide, quest_id, before_tag, _ = min(
                nearby or same_map, key=lambda item: (distance(item), item[0])
            )
            map_name = catalog.zones.get(location.map_id, location.map_name)
            instruction = (
                f"Optional: learn the flight path from {_safe_player_text(master.name)}. "
                f"[P][G{location.x:.2f},{location.y:.2f} {map_name}][O]"
            )
            guide.semantic_steps.append(
                SemanticStep(
                    quest_id,
                    before_tag,
                    "acquire_flight_path",
                    instruction,
                    location.map_id,
                    map_name,
                    location.x,
                    location.y,
                    (
                        f"questie:{catalog.source_revision or 'local'}:npc:{master_id}",
                        f"authored-route:{route.id}:{point['source_chapter']}:{point['source_line']}",
                    ),
                    "cross_verified_questie_and_authored_route",
                )
            )
            matched_masters.add(master_id)


def _attach_level_gate_steps(
    catalog: Catalog,
    guides: list[GuideFile],
    quests: dict[int, Quest],
) -> None:
    """Make every increase in the playable minimum level explicit.

    Guidelime exposes Questie's requiredLevel in its editor, but it does not use
    that value when deciding whether an accept step is currently available.
    A separate XP step is therefore required before the first quest at each new
    minimum level. Gates are tracked per selectable stream so no route can
    present an impossible quest accept to an under-level character.
    """
    start_level = int(catalog.scope.get("legacy_guide_start_level", 10))
    for guide in guides:
        gated_level = start_level
        for operation in guide.operations:
            if operation.tag != "QA":
                continue
            quest = quests[operation.quest_id]
            required_level = operation.required_level
            if required_level <= gated_level:
                continue
            locations = [
                location
                for source in quest.starter_sources
                for location in source.locations
            ]
            location = locations[0] if locations else None
            map_id = (
                location.map_id if location is not None
                else int(quest.get("zone_or_sort", 0))
            )
            map_name = catalog.zones.get(
                map_id,
                location.map_name if location is not None else f"Map or sort {map_id}",
            )
            quest_name = _safe_player_text(quest.name)
            guide.semantic_steps.append(
                SemanticStep(
                    operation.quest_id,
                    "QA",
                    "level_gate",
                    f"{_end_sentence(f'Reach level {required_level} before accepting {quest_name}')} "
                    f"[XP{required_level} Level {required_level}]",
                    map_id,
                    map_name,
                    location.x if location is not None else None,
                    location.y if location is not None else None,
                    (
                        f"questie:{catalog.source_revision or 'local'}:quest:"
                        f"{quest.id}:requiredLevel",
                    ),
                    "questie_required_level",
                    optional=False,
                    required_level=required_level,
                )
            )
            gated_level = required_level


def _assign_route_required_levels(
    catalog: Catalog,
    guides: list[GuideFile],
    quests: dict[int, Quest],
) -> None:
    """Propagate a monotonic effective level through each selectable stream.

    Some Blizzard chains unlock a quest whose raw requiredLevel is lower than
    its prerequisite's. The character cannot lose levels, so those descendants
    inherit the stream's current gate. This also covers the custom Auberdine
    opening, which is moved after the catalog order has been computed.
    """
    start_level = int(catalog.scope.get("legacy_guide_start_level", 10))
    current_by_branch: dict[str, int] = defaultdict(lambda: start_level)
    quest_level_by_branch: dict[str, dict[int, int]] = defaultdict(dict)
    for guide in guides:
        updated: list[Operation] = []
        for operation in guide.operations:
            if operation.tag == "QA":
                actual = max(
                    start_level,
                    int(quests[operation.quest_id].get("required_level", 0)),
                )
                current_by_branch[guide.branch] = max(
                    current_by_branch[guide.branch], actual
                )
                quest_level_by_branch[guide.branch][operation.quest_id] = (
                    current_by_branch[guide.branch]
                )
            required_level = quest_level_by_branch[guide.branch].get(
                operation.quest_id,
                current_by_branch[guide.branch],
            )
            updated.append(replace(operation, required_level=required_level))
        guide.operations = updated
        if guide.branch == "primary":
            levels = [
                operation.required_level
                for operation in guide.operations
                if operation.tag == "QA"
            ]
            guide.minimum = min(levels, default=start_level)
            guide.maximum = max(levels, default=guide.minimum)


def _flight_point_applies(applies_to) -> bool:
    values = {str(value).lower().replace(" ", "") for value in applies_to}
    if values & {"aldor", "scryer", "scryers"}:
        return False
    character_filters = values & {
        "human", "dwarf", "gnome", "nightelf", "draenei", "hunter", "warrior",
        "paladin", "rogue", "priest", "shaman", "mage", "warlock", "druid",
    }
    return not character_filters or bool(character_filters & {"nightelf", "hunter"})


def _match_flight_master(point: dict, flight_masters):
    wanted_map = _normalize_map_name(point["map_name"])
    matches = []
    for master_id, master in flight_masters.items():
        for location in master.locations:
            if _normalize_map_name(location.map_name) != wanted_map:
                continue
            distance = hypot(location.x - point["x"], location.y - point["y"])
            if distance <= 5:
                matches.append((distance, master_id, master, location))
    if not matches:
        return None
    _, master_id, master, location = min(matches)
    return master_id, master, location


def _normalize_map_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _write_route_specs(
    catalog: Catalog,
    project_root: Path,
    guides: list[GuideFile],
    quests: dict[int, Quest],
) -> None:
    root = project_root / "data" / "route" / "chapters"
    root.mkdir(parents=True, exist_ok=True)
    for old in root.glob("*.json"):
        old.unlink()
    branch_quest_ids: dict[str, set[int]] = defaultdict(set)
    for guide in guides:
        branch_quest_ids[guide.branch].update(operation.quest_id for operation in guide.operations)
    previous_by_guide: dict[int, str | None] = {}
    last_title_by_branch: dict[str, str] = {}
    for guide in guides:
        previous_by_guide[id(guide)] = last_title_by_branch.get(guide.branch)
        last_title_by_branch[guide.branch] = guide.title
    for index, guide in enumerate(guides, 1):
        first_quest = quests[guide.operations[0].quest_id] if guide.operations else None
        steps = []
        semantic_by_operation: dict[tuple[int, str], list[SemanticStep]] = defaultdict(list)
        for semantic in guide.semantic_steps:
            semantic_by_operation[(semantic.before_quest_id, semantic.before_tag)].append(semantic)
        for operation in guide.operations:
            quest = quests[operation.quest_id]
            for semantic in semantic_by_operation[(operation.quest_id, operation.tag)]:
                steps.append({
                    "type": semantic.type,
                    "instruction": semantic.instruction,
                    "optional": semantic.optional,
                    "map_id": semantic.map_id,
                    "map_name": semantic.map_name,
                    "x": semantic.x,
                    "y": semantic.y,
                    "verification": semantic.verification,
                    "evidence_refs": list(semantic.evidence_refs),
                    "required_level": semantic.required_level,
                    "before_quest_id": semantic.before_quest_id,
                    "before_tag": semantic.before_tag,
                    "origin_map_id": semantic.origin_map_id,
                    "origin_map_name": semantic.origin_map_name,
                    "origin_x": semantic.origin_x,
                    "origin_y": semantic.origin_y,
                    "transport_link_ids": list(semantic.transport_link_ids),
                    "related_quest_ids": list(semantic.related_quest_ids),
                })
            endpoint_sources = (
                quest.starter_sources if operation.tag == "QA" else
                quest.finisher_sources if operation.tag == "QT" else ()
            )
            step = {
                "type": {"QA": "accept", "QC": "complete", "QT": "turn_in"}[operation.tag],
                "quest_id": operation.quest_id,
                "quest_name": operation.quest_name,
                "category": operation.category,
                "zone_or_sort": quest.get("zone_or_sort", 0),
                "zone_or_sort_name": catalog.zones.get(
                    int(quest.get("zone_or_sort", 0)),
                    f"Map or sort {quest.get('zone_or_sort', 0)}",
                ),
                "quest_tag": operation.quest_tag,
                "required_level": operation.required_level,
                "conditional_categories": list(
                    catalog.entries[operation.quest_id].conditional_categories
                ),
                "instruction": operation.line,
                "item_use_id": operation.item_use_id,
                "scripted_objective": operation.scripted_objective,
                "objective_hint": operation.objective_hint,
                "endpoint_sources": [source.to_dict() for source in endpoint_sources],
                "objective_sources": [
                    source.to_dict() for source in quest.objective_sources
                    if operation.tag == "QC"
                ],
                "evidence_refs": [
                    f"questie:{catalog.source_revision or 'local'}:quest:{operation.quest_id}"
                ],
            }
            steps.append(step)
        for order, step in enumerate(steps, 1):
            step["order"] = order
        branch_ids = branch_quest_ids[guide.branch]
        required_all, required_any = _external_prerequisites(
            guide,
            branch_ids,
            catalog,
            quests,
        )
        external_prerequisites = required_all | {
            dependency for group in required_any for dependency in group
        }
        prerequisite_clause = _format_prerequisite_clause(
            required_all,
            required_any,
            quests,
        )
        chapter_entry = next(
            (step for step in guide.semantic_steps if step.type == "chapter_entry"),
            None,
        )
        chapter_transition = next(
            (step for step in guide.semantic_steps if step.type in {"zone_transition", "transport"}),
            None,
        )
        first_accept = next(
            (operation for operation in guide.operations if operation.tag == "QA"),
            None,
        )
        entry_location = chapter_entry.map_name if chapter_entry else catalog.zones.get(
            int(first_quest.get("zone_or_sort", 0)) if first_quest else 0,
            "the chapter entry zone",
        )
        entry_source = (
            _format_choices(first_accept.endpoint_names)
            if first_accept and first_accept.endpoint_names else None
        )
        entry_target = f"Begin in {entry_location}"
        if entry_source:
            entry_target += f" with {entry_source}"
        previous_title = previous_by_guide[id(guide)]
        if guide.branch == "primary" and previous_title is None:
            entry_contract = (
                "Complete the documented level 1-9 Teldrassil baseline. "
                f"{entry_target}. Leave at least two quest-log slots open."
            )
        elif guide.branch == "primary":
            entry_contract = (
                f"Continue from {previous_title}, or select this chapter on a partially completed "
                f"character. {entry_target}. Leave at least two quest-log slots open."
            )
        elif guide.branch == "optional_content":
            entry_contract = (
                f"{_upper_first(prerequisite_clause)}. {entry_target}. Leave at least two quest-log "
                "slots open; group and reputation gates remain explicit."
            )
        else:
            entry_contract = (
                f"{_upper_first(prerequisite_clause)}, then choose this branch before its conflicting "
                f"default. {entry_target}. Leave at least two quest-log slots open."
            )
        zones = {
            int(quests[operation.quest_id].get("zone_or_sort", 0))
            for operation in guide.operations
            if operation.tag == "QA"
        }
        expected_warning = lambda operation: (
            operation.quest_tag in {"Elite", "Escort", "Heroic"}
            or operation.category in {"dungeon", "raid"}
        )
        static_review = {
            "chapter_entry_instruction": chapter_entry is not None,
            "chapter_transition_instruction": previous_title is None or chapter_transition is not None,
            "endpoint_names_on_accept_and_turn_in": all(
                operation.endpoint_names
                for operation in guide.operations
                if operation.tag in {"QA", "QT"}
            ),
            "objective_instruction_coverage": all(
                operation.objective_hint or operation.item_use_id or operation.scripted_objective
                for operation in guide.operations
                if operation.tag == "QC" and quests[operation.quest_id].objective_sources
            ),
            "preparation_warning_coverage": all(
                not expected_warning(operation)
                or any(
                    marker in operation.line
                    for marker in (
                        "Elite/group recommended", "Escort —", "Heroic dungeon —",
                        "Dungeon —", "Raid —",
                    )
                )
                for operation in guide.operations
                if operation.tag == "QC"
            ),
            "reserved_quest_log_slots": chapter_entry is not None
            and "quest-log slots open" in chapter_entry.instruction,
            "bounded_zone_scope": len(zones) <= (2 if guide.branch == "primary" else 3),
            "lua_line_budget": len(
                guide.path.read_text(encoding="utf-8").splitlines()
            ) <= MAX_LUA_LINES,
        }
        review_status = (
            "static_review_passed_needs_in_game"
            if all(static_review.values())
            else "static_review_failed"
        )
        exit_operation, exit_location = _last_mapped_operation(guide, quests)
        if exit_location is not None:
            exit_route_point = {
                "quest_id": exit_operation.quest_id if exit_operation else None,
                "tag": exit_operation.tag if exit_operation else None,
                "map_id": exit_location.map_id,
                "map_name": exit_location.map_name,
                "x": exit_location.x,
                "y": exit_location.y,
                "basis": "last_mapped_operation",
            }
        elif chapter_entry is not None:
            exit_route_point = {
                "quest_id": None,
                "tag": None,
                "map_id": chapter_entry.map_id,
                "map_name": chapter_entry.map_name,
                "x": chapter_entry.x,
                "y": chapter_entry.y,
                "basis": "chapter_entry_fallback_no_mapped_operation",
            }
        else:
            exit_route_point = None
        payload = {
            "schema_version": 2,
            "id": f"{index:03d}-{guide.branch}-{guide.title.lower().replace(' ', '-')}",
            "title": guide.title,
            "branch": guide.branch,
            "group": guide.group,
            "phase_profile": catalog.phase_profile.get("id"),
            "minimum_level": guide.minimum,
            "maximum_level": guide.maximum,
            "entry_zone_or_sort": first_quest.get("zone_or_sort", 0) if first_quest else None,
            "next_chapter": guide.next_title,
            "previous_chapter": previous_title,
            "entry_contract": entry_contract,
            "entry_route_point": {
                "map_id": chapter_entry.map_id,
                "map_name": chapter_entry.map_name,
                "x": chapter_entry.x,
                "y": chapter_entry.y,
            } if chapter_entry else None,
            "exit_route_point": exit_route_point,
            "external_prerequisite_quest_ids": sorted(external_prerequisites),
            "external_prerequisite_all_quest_ids": sorted(required_all),
            "external_prerequisite_any_groups": [list(group) for group in required_any],
            "review_status": review_status,
            "static_review": static_review,
            "guide_file": str(guide.path.relative_to(project_root)).replace("\\", "/"),
            "steps": steps,
        }
        (root / f"{index:03d}.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )


def parse_guide_file(path: Path) -> tuple[str, str | None, str, list[tuple[str, int]]]:
    source = path.read_text(encoding="utf-8")
    match = REGISTER_RE.search(source)
    if not match:
        raise ValueError(f"{path}: not a Guidelime.registerGuide long-string module")
    body, group = match.groups()
    name_match = NAME_RE.search(body)
    if not name_match:
        raise ValueError(f"{path}: missing [N] metadata")
    next_match = NEXT_RE.search(body)
    tags = [(tag, int(quest_id)) for tag, quest_id in TAG_RE.findall(body)]
    return name_match.group(1).strip(), next_match.group(1).strip() if next_match else None, group, tags


def toc_all_lua_files(project_root: Path) -> list[Path]:
    toc = project_root / f"{ADDON_NAME}.toc"
    if not toc.is_file():
        return []
    files = []
    for raw in toc.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and line.lower().endswith(".lua"):
            files.append(project_root / line.replace("\\", "/"))
    return files


def toc_lua_files(project_root: Path) -> list[Path]:
    return [
        path for path in toc_all_lua_files(project_root)
        if path.relative_to(project_root).parts[0] == "Guides"
    ]


def guide_quest_ids(project_root: Path) -> Counter[int]:
    result: Counter[int] = Counter()
    for path in toc_lua_files(project_root):
        _, _, _, tags = parse_guide_file(path)
        result.update(quest_id for tag, quest_id in tags if tag == "QA")
    return result
