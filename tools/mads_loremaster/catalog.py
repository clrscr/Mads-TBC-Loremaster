from __future__ import annotations

from collections import Counter, defaultdict, deque
from dataclasses import replace
from math import hypot
from pathlib import Path

from .model import Catalog, CatalogEntry, Quest
from .questie import (
    BlacklistDecision,
    load_blacklist,
    load_quest_sources,
    load_quests,
    load_quest_tags,
    load_sort_names,
    load_zones,
    resolve_questie_root,
    source_revision,
)
from .scope import PROJECT_ROOT, load_content_policy, load_scope

NIGHT_ELF = 8
HUNTER = 4
MAX_LEVEL = 70
START_LEVEL = 10

QUEST_FLAG_DAILY = 4096
QUEST_FLAG_WEEKLY = 32768
QUEST_FLAG_MONTHLY = 65536
QUEST_FLAG_RAID = 64
SPECIAL_REPEATABLE = 1
SPECIAL_MONTHLY = 4

ALDOR = 932
SCRYERS = 934

PROFESSION_SORTS = {
    -24, -101, -121, -181, -182, -201, -264, -304, -324, -371, -373, -377,
}
SEASONAL_SORTS = {
    -21, -22, -41, -364, -366, -368, -369, -370, -374, -375, -376, -378, -402, -404,
}
PVP_SORT = -25
HUNTER_SORT = -261
REPUTATION_SORT = -367
LEGENDARY_SORT = -344

RAID_ZONES = {
    1977, 2159, 2677, 2717, 3428, 3429, 3456, 3457, 3606, 3607, 3836,
    3845, 3923, 3959, 4075,
}
# These quests begin from raid-boss trophy items, so their generic quest sort
# must not place them in the solo world route. The pinned TBC item database
# links each item to Onyxia, Nefarian, Hakkar, or Magtheridon respectively.
RAID_TROPHY_QUESTS = {7495, 7781, 8183, 11002}
DUNGEON_ZONES = {
    209, 491, 717, 718, 719, 721, 722, 796, 1176, 1337, 1417, 1477, 1581,
    1583, 1584, 1585, 2017, 2057, 2100, 2366, 2367, 2437, 2557, 3562, 3563,
    3688, 3713, 3714, 3715, 3716, 3717, 3789, 3790, 3791, 3792, 3805, 3847,
    3848, 3849, 3905, 3917, 4131,
}

# Geographic tie-breaker only. Prerequisite edges always take precedence.
ROUTE_ZONES = (
    141, 1657, 148, 331, 406, 17, 15, 400, 405, 357, 16, 440, 490, 1377,
    618, 361, 493, 3524, 3525, 3557, 12, 40, 10, 44, 1, 38, 11, 45, 267,
    47, 8, 33, 51, 46, 4, 41, 28, 139, 1519, 1537, 3483, 3521, 3519, 3703,
    3518, 3522, 3523, 3520, 4080,
)
ROUTE_RANK = {zone: index for index, zone in enumerate(ROUTE_ZONES)}
LOCAL_ROUTE_RADIUS = 1
CATEGORY_RANK = {
    "world": 0,
    "hunter": 1,
    "dungeon": 2,
    "raid": 3,
    "legendary": 4,
    "reputation": 5,
    "pvp": 6,
}
ZONE_NAME_OVERRIDES = {
    8: "Swamp of Sorrows",
    133: "Gnomeregan",
    1941: "Caverns of Time",
    1977: "Zul'Gurub",
    3428: "Ahn'Qiraj",
    3429: "Ruins of Ahn'Qiraj",
    3522: "Blade's Edge Mountains",
    3792: "Mana-Tombs",
    3836: "Magtheridon's Lair",
}


def build_catalog(questie_path: str | Path) -> Catalog:
    root = resolve_questie_root(questie_path)
    scope, phase_profile = load_scope()
    content_policy = load_content_policy(PROJECT_ROOT / str(scope["content_policy"]))
    quests = load_quests(root, legacy_faction_replacement=True)
    zones = load_zones(root)
    zones.update(load_sort_names(root))
    zones.update(ZONE_NAME_OVERRIDES)
    quest_tags = load_quest_tags(root, int(phase_profile["phase"]))
    quest_sources = load_quest_sources(root, quests, zones)
    quests = {
        quest_id: replace(
            quest,
            tag_id=quest_tags.get(quest_id, (None, None))[0],
            tag_name=quest_tags.get(quest_id, (None, None))[1],
            starter_sources=quest_sources[quest_id][0],
            finisher_sources=quest_sources[quest_id][1],
            objective_sources=quest_sources[quest_id][2],
        )
        for quest_id, quest in quests.items()
    }
    blacklist = load_blacklist(root, int(phase_profile["phase"]))
    catalog = Catalog(
        str(root),
        source_revision(root),
        scope=scope,
        phase_profile=phase_profile,
        content_policy=content_policy,
        zones=zones,
    )

    eligible: set[int] = set()
    for quest_id, quest in quests.items():
        decision = blacklist.get(quest_id)
        if decision and decision.reason_code == "future_phase":
            catalog.entries[quest_id] = CatalogEntry(
                quest,
                "unavailable",
                reason=decision.reason,
                reason_code=decision.reason_code,
                available_phase=decision.available_phase,
            )
            continue
        exclusion = permanent_exclusion(quest)
        if exclusion:
            reason_code, reason = exclusion
            catalog.entries[quest_id] = CatalogEntry(
                quest, "excluded", reason=reason, reason_code=reason_code
            )
        elif decision:
            catalog.entries[quest_id] = CatalogEntry(
                quest,
                "excluded",
                reason=decision.reason,
                reason_code=decision.reason_code,
            )
        else:
            eligible.add(quest_id)

    baseline = derive_baseline(quests, eligible)
    for quest_id in baseline:
        catalog.entries[quest_id] = CatalogEntry(
            quests[quest_id], "baseline_completed",
            reason="assumed Teldrassil level 1-9 completion", reason_code="starting_state"
        )

    candidates = eligible - baseline
    reachable, unreachable = reachable_subset(quests, candidates, baseline)
    for quest_id, reason in unreachable.items():
        catalog.entries[quest_id] = CatalogEntry(
            quests[quest_id], "excluded", reason=reason, reason_code="unreachable_dependency"
        )

    faction = {quest_id: faction_branch(quests[quest_id]) for quest_id in reachable}
    faction_counts = Counter(branch for branch in faction.values() if branch)
    default_faction = "aldor" if faction_counts["aldor"] >= faction_counts["scryer"] else "scryer"
    losing_faction = "scryer" if default_faction == "aldor" else "aldor"

    primary_pool = {quest_id for quest_id in reachable if faction[quest_id] != losing_faction}
    primary_pool = choose_exclusive_defaults(quests, primary_pool)
    default_selection, _ = reachable_subset(quests, primary_pool, baseline)
    optional = optional_dependency_closure(quests, default_selection)
    primary = default_selection - optional
    alternatives = reachable - default_selection

    primary_order = topological_order(quests, primary, baseline)
    for index, quest_id in enumerate(primary_order, 1):
        branch = faction[quest_id]
        catalog.entries[quest_id] = CatalogEntry(
            quests[quest_id],
            "covered_primary",
            category=category_for(quests[quest_id]),
            branch=branch or "default",
            order=index,
        )

    optional_order = topological_order(quests, optional, baseline | primary)
    for index, quest_id in enumerate(optional_order, 1):
        catalog.entries[quest_id] = CatalogEntry(
            quests[quest_id],
            "covered_optional",
            reason="optional content and any descendants that require it",
            reason_code="optional_route",
            category=category_for(quests[quest_id]),
            branch="optional_content",
            order=index,
        )

    alternative_groups: dict[str, set[int]] = defaultdict(set)
    for quest_id in alternatives:
        branch = faction[quest_id] or "other_choices"
        alternative_groups[branch].add(quest_id)

    for faction_name in ("aldor", "scryer"):
        faction_alternatives = alternative_groups.pop(faction_name, set())
        if faction_alternatives:
            for branch, quest_ids in assign_choice_branches(
                quests, faction_alternatives, faction_name
            ).items():
                alternative_groups[branch].update(quest_ids)
    other = alternative_groups.pop("other_choices", set())
    if other:
        for branch, quest_ids in assign_choice_branches(quests, other, "other_choices").items():
            alternative_groups[branch].update(quest_ids)

    alt_counter = 0
    branch_order = sorted(
        alternative_groups,
        key=lambda branch: (
            0 if branch.startswith("aldor") else 1 if branch.startswith("scryer") else 2,
            branch,
        ),
    )
    for branch in branch_order:
        quest_ids = alternative_groups.get(branch, set())
        if not quest_ids:
            continue
        # Shared/default prerequisites are treated as already completed when this
        # selectable stream is entered.
        order = topological_order(quests, quest_ids, baseline | primary)
        for quest_id in order:
            alt_counter += 1
            catalog.entries[quest_id] = CatalogEntry(
                quests[quest_id],
                "covered_alternative",
                reason="mutually exclusive with the default route",
                category=category_for(quests[quest_id]),
                branch=branch,
                order=alt_counter,
            )

    # Defensive classification: every Questie row must be represented.
    for quest_id, quest in quests.items():
            catalog.entries.setdefault(
            quest_id, CatalogEntry(
                quest, "excluded", reason="not reachable after eligibility analysis",
                reason_code="unreachable_dependency"
            )
        )
    for entry in catalog.entries.values():
        entry.conditional_categories = quest_kinds(entry.quest)
    return catalog


def quest_kinds(quest: Quest) -> tuple[str, ...]:
    flags = int(quest.get("quest_flags", 0))
    special = int(quest.get("special_flags", 0))
    zone = int(quest.get("zone_or_sort", 0))
    kinds: set[str] = {category_for(quest)}
    if special & SPECIAL_REPEATABLE:
        kinds.add("repeatable")
    else:
        kinds.add("one_time")
    if flags & QUEST_FLAG_DAILY:
        kinds.add("daily")
    if flags & QUEST_FLAG_WEEKLY:
        kinds.add("weekly")
    if flags & QUEST_FLAG_MONTHLY or special & SPECIAL_MONTHLY:
        kinds.add("monthly")
    if special & 2:
        kinds.add("scripted_or_event")
    if zone in SEASONAL_SORTS:
        kinds.add("seasonal_or_event")
    if quest.get("required_skill") is not None or quest.get("required_specialization") is not None:
        kinds.add("profession_gated")
    if quest.get("required_min_rep") is not None or quest.get("required_max_rep") is not None:
        kinds.add("reputation_gated")
    started_by = quest.get("started_by")
    if isinstance(started_by, list) and len(started_by) > 2 and started_by[2]:
        kinds.add("item_triggered")
    if quest.get("source_item_id") is not None or quest.get("required_source_items"):
        kinds.add("item_mechanic")
    if quest.tag_name:
        kinds.add(quest.tag_name.lower().replace(" ", "_"))
    if category_for(quest) in {"dungeon", "raid"} or quest.tag_name in {"Elite", "Heroic"}:
        kinds.add("group_content")
    return tuple(sorted(kinds))


def optional_dependency_closure(quests: dict[int, Quest], selected: set[int]) -> set[int]:
    """Keep optional content out of the default world route without breaking chains.

    A world quest moves with an optional chain when it has a hard dependency on
    that chain. Any-of dependencies remain on the primary route when at least
    one selected non-optional prerequisite is available.
    """
    optional = {quest_id for quest_id in selected if category_for(quests[quest_id]) != "world"}
    changed = True
    while changed:
        changed = False
        # Questie's parentQuest relationship means the parent must remain active
        # while the child runs. Move that parent into the same optional stream.
        for quest_id in tuple(optional):
            parent = quests[quest_id].get("parent_quest")
            if parent in selected and parent not in optional:
                optional.add(parent)
                changed = True
        for quest_id in selected - optional:
            quest = quests[quest_id]
            hard = set(quest.prerequisites_all)
            hard.update(
                dependency
                for dependency in (
                    quest.get("available_starting_with"),
                )
                if dependency
            )
            any_selected = {dependency for dependency in quest.prerequisites_any if dependency in selected}
            if hard & optional or (any_selected and any_selected <= optional):
                optional.add(quest_id)
                changed = True
    return optional


def assign_choice_branches(
    quests: dict[int, Quest], alternatives: set[int], prefix: str
) -> dict[str, set[int]]:
    """Color mutually exclusive alternative families into compatible streams.

    Direct conflicts receive different colors; non-conflicting descendants
    inherit a prerequisite's color where possible. Independent families can
    safely share the same selectable stream.
    """
    conflicts: dict[int, set[int]] = defaultdict(set)
    for quest_id in alternatives:
        for other in quests[quest_id].exclusive_to:
            if other not in alternatives:
                continue
            conflicts[quest_id].add(other)
            conflicts[other].add(quest_id)

    colors: dict[int, int] = {}
    for quest_id in sorted(alternatives, key=lambda value: (-len(conflicts[value]), value)):
        if not conflicts[quest_id]:
            continue
        used = {colors[other] for other in conflicts[quest_id] if other in colors}
        color = 1
        while color in used:
            color += 1
        colors[quest_id] = color

    # Non-conflicting descendants follow an already colored alternative
    # prerequisite when possible. Shared prerequisites default to stream 1 and
    # can be completed before selecting a later choice stream.
    for quest_id in topological_order(quests, alternatives, set()):
        if quest_id in colors:
            continue
        quest = quests[quest_id]
        prerequisites = list(quest.prerequisites_all) + list(quest.prerequisites_any)
        inherited = [colors[value] for value in prerequisites if value in colors]
        colors[quest_id] = inherited[0] if inherited else 1
    result: dict[str, set[int]] = defaultdict(set)
    for quest_id in alternatives:
        color = colors[quest_id]
        branch = (
            f"{prefix}_{color}"
            if prefix == "other_choices"
            else prefix if color == 1 else f"{prefix}_choice_{color}"
        )
        result[branch].add(quest_id)
    return result


def permanent_exclusion(quest: Quest) -> tuple[str, str] | None:
    if not quest.name or quest.name.startswith(("BETA ", "TEST ")):
        return "test_or_internal", "test or placeholder quest"
    if quest.get("started_by") is None:
        return "missing_starter", "no quest starter in Questie TBC data"
    required_level = int(quest.get("required_level", 0))
    if required_level > MAX_LEVEL:
        return "above_max_level", "requires a level above 70"
    max_level = quest.get("required_max_level")
    if max_level is not None and int(max_level) < START_LEVEL:
        return "below_starting_state", "no longer obtainable at level 10"
    races = int(quest.get("required_races", 0))
    if races and not races & NIGHT_ELF:
        return "other_race", "not available to Night Elves"
    classes = int(quest.get("required_classes", 0))
    if classes and not classes & HUNTER:
        return "other_class", "not available to Hunters"
    quest_flags = int(quest.get("quest_flags", 0))
    if quest_flags & (QUEST_FLAG_DAILY | QUEST_FLAG_WEEKLY | QUEST_FLAG_MONTHLY):
        return "recurring", "daily, weekly, or monthly quest"
    special_flags = int(quest.get("special_flags", 0))
    if special_flags & SPECIAL_REPEATABLE:
        return "repeatable", "repeatable quest"
    # Bit 2 marks quests with a scripted event objective (for example the
    # always-available City of Light escort), not a seasonal availability gate.
    # Seasonal availability comes from Questie's blacklist and quest sort.
    if special_flags & SPECIAL_MONTHLY:
        return "monthly", "monthly quest"
    zone_or_sort = int(quest.get("zone_or_sort", 0))
    if zone_or_sort in SEASONAL_SORTS:
        return "event", "seasonal or world-event quest"
    if zone_or_sort in PROFESSION_SORTS:
        return "profession", "profession-gated quest"
    if quest.get("required_skill") is not None or quest.get("required_specialization") is not None:
        return "profession", "profession skill or specialization required"
    if quest.get("required_ranks") is not None:
        return "profession", "profession rank required"
    return None


def derive_baseline(quests: dict[int, Quest], eligible: set[int]) -> set[int]:
    baseline = {
        quest_id
        for quest_id in eligible
        if int(quests[quest_id].get("zone_or_sort", 0)) in {141, 1657}
        and int(quests[quest_id].get("required_level", 0)) < START_LEVEL
    }
    # Keep only prerequisites that themselves meet the same level/race/class
    # assumptions; this makes the manifest explicit without silently importing
    # remote-zone chains.
    changed = True
    while changed:
        changed = False
        for quest_id in tuple(baseline):
            quest = quests[quest_id]
            for prerequisite in quest.prerequisites_all:
                if prerequisite in eligible and prerequisite not in baseline:
                    prerequisite_quest = quests[prerequisite]
                    if int(prerequisite_quest.get("required_level", 0)) < START_LEVEL:
                        baseline.add(prerequisite)
                        changed = True
            if quest.prerequisites_any and not any(q in baseline for q in quest.prerequisites_any):
                choices = [q for q in quest.prerequisites_any if q in eligible]
                if choices:
                    baseline.add(min(choices))
                    changed = True
    return baseline


def prerequisite_failure(quest: Quest, available: set[int], completed: set[int]) -> str | None:
    known = available | completed
    missing_all = [quest_id for quest_id in quest.prerequisites_all if quest_id not in known]
    if missing_all:
        return "unreachable required prerequisite: " + ", ".join(map(str, missing_all))
    if quest.prerequisites_any and not any(quest_id in known for quest_id in quest.prerequisites_any):
        return "no reachable alternative prerequisite: " + ", ".join(map(str, quest.prerequisites_any))
    parent = quest.get("parent_quest")
    if parent and parent not in known:
        return f"unreachable parent quest: {parent}"
    starting = quest.get("available_starting_with")
    if starting and starting not in known:
        return f"unreachable enabling quest: {starting}"
    return None


def reachable_subset(
    quests: dict[int, Quest], candidates: set[int], completed: set[int]
) -> tuple[set[int], dict[int, str]]:
    available = set(candidates)
    reasons: dict[int, str] = {}
    changed = True
    while changed:
        changed = False
        for quest_id in tuple(available):
            reason = prerequisite_failure(quests[quest_id], available, completed)
            if reason:
                available.remove(quest_id)
                reasons[quest_id] = reason
                changed = True
    return available, reasons


def _reputation_factions(quest: Quest) -> set[int]:
    factions: set[int] = set()
    for key in ("required_min_rep", "required_max_rep"):
        pair = quest.get(key)
        if isinstance(pair, list) and pair:
            factions.add(int(pair[0]))
    rewards = quest.get("reputation_reward", ())
    if isinstance(rewards, list):
        for pair in rewards:
            if isinstance(pair, list) and pair:
                factions.add(int(pair[0]))
    return factions


def faction_branch(quest: Quest) -> str | None:
    factions = _reputation_factions(quest)
    if ALDOR in factions and SCRYERS not in factions:
        return "aldor"
    if SCRYERS in factions and ALDOR not in factions:
        return "scryer"
    if quest.id == 10551:
        return "aldor"
    if quest.id == 10552:
        return "scryer"
    return None


def dependency_edges(quests: dict[int, Quest], quest_ids: set[int]) -> dict[int, set[int]]:
    edges: dict[int, set[int]] = defaultdict(set)
    for quest_id in quest_ids:
        quest = quests[quest_id]
        predecessors = list(quest.prerequisites_all)
        if quest.prerequisites_any:
            choices = [value for value in quest.prerequisites_any if value in quest_ids]
            if choices:
                predecessors.append(min(choices, key=lambda value: route_key(quests[value])))
        parent = quest.get("parent_quest")
        if parent:
            predecessors.append(parent)
        starting = quest.get("available_starting_with")
        if starting:
            predecessors.append(starting)
        for predecessor in predecessors:
            if predecessor in quest_ids and predecessor != quest_id:
                edges[predecessor].add(quest_id)
        target = quest.get("breadcrumb_for_quest_id")
        if target in quest_ids:
            edges[quest_id].add(target)
        for child in quest.get("child_quests", ()):
            if child in quest_ids and child != quest_id:
                edges[quest_id].add(child)
        target = quest.get("next_quest_in_chain")
        if target in quest_ids:
            edges[quest_id].add(target)
        target = quest.get("available_until_completed")
        if target in quest_ids:
            edges[quest_id].add(target)
        target = quest.get("disabled_by_quest")
        if target in quest_ids:
            edges[quest_id].add(target)
    # A parent quest must stay active while its child quests run. Any successor
    # that requires the parent to be turned in therefore also depends on those
    # children, not merely on the parent's acceptance.
    for parent in quest_ids:
        child_ids = {
            child for child in quests[parent].get("child_quests", ()) if child in quest_ids
        }
        child_ids.update(
            quest_id
            for quest_id in quest_ids
            if quests[quest_id].get("parent_quest") == parent
        )
        if not child_ids:
            continue
        successors = set(edges.get(parent, ())) - child_ids
        for child in child_ids:
            edges[child].update(successors)
    return edges


def choose_exclusive_defaults(quests: dict[int, Quest], candidates: set[int]) -> set[int]:
    adjacency: dict[int, set[int]] = defaultdict(set)
    for quest_id in candidates:
        for other in quests[quest_id].exclusive_to:
            if other in candidates:
                adjacency[quest_id].add(other)
                adjacency[other].add(quest_id)
    edges = dependency_edges(quests, candidates)
    descendant_score = {quest_id: _descendant_count(quest_id, edges) for quest_id in candidates}
    selected = set(candidates)
    seen: set[int] = set()
    for start in sorted(adjacency):
        if start in seen:
            continue
        component: set[int] = set()
        queue = [start]
        while queue:
            current = queue.pop()
            if current in component:
                continue
            component.add(current)
            queue.extend(adjacency[current])
        seen.update(component)
        winner = max(component, key=lambda q: (descendant_score[q], -route_key(quests[q])[0], -q))
        selected.difference_update(component - {winner})
    return selected


def _descendant_count(start: int, edges: dict[int, set[int]]) -> int:
    seen: set[int] = set()
    queue = deque(edges.get(start, ()))
    while queue:
        current = queue.popleft()
        if current in seen:
            continue
        seen.add(current)
        queue.extend(edges.get(current, ()))
    return len(seen)


def category_for(quest: Quest) -> str:
    zone = int(quest.get("zone_or_sort", 0))
    flags = int(quest.get("quest_flags", 0))
    classes = int(quest.get("required_classes", 0))
    if quest.id in RAID_TROPHY_QUESTS:
        return "raid"
    if quest.tag_id in {81, 85}:
        return "dungeon"
    if quest.tag_id in {62, 88, 89}:
        return "raid"
    if zone == HUNTER_SORT or classes == HUNTER:
        return "hunter"
    if zone == LEGENDARY_SORT:
        return "legendary"
    if zone == PVP_SORT:
        return "pvp"
    if flags & QUEST_FLAG_RAID or zone in RAID_ZONES:
        return "raid"
    if zone in DUNGEON_ZONES:
        return "dungeon"
    if zone == REPUTATION_SORT or quest.get("required_min_rep") is not None or quest.get("required_max_rep") is not None:
        return "reputation"
    return "world"


def route_key(quest: Quest) -> tuple[int, int, int, int]:
    category = category_for(quest)
    zone = int(quest.get("zone_or_sort", 0))
    return (
        max(START_LEVEL, int(quest.get("required_level", 0))),
        ROUTE_RANK.get(zone, 10_000 + abs(zone)),
        CATEGORY_RANK[category],
        quest.id,
    )


def topological_order(quests: dict[int, Quest], quest_ids: set[int], completed: set[int]) -> list[int]:
    del completed  # documented input; external prerequisites create no in-set edge
    edges = dependency_edges(quests, quest_ids)
    indegree = {quest_id: 0 for quest_id in quest_ids}
    for targets in edges.values():
        for target in targets:
            if target in indegree:
                indegree[target] += 1
    ready = {quest_id for quest_id, degree in indegree.items() if degree == 0}
    result: list[int] = []
    current_zone: int | None = None
    current_location: tuple[int, float, float] | None = None
    while ready:
        minimum_level = min(route_key(quests[quest_id])[0] for quest_id in ready)
        # Look a few adjacent route zones ahead for lower-level work before
        # raising the floor. This keeps useful local questing ahead of a grind
        # gate without sending the player across a continent for isolated
        # cleanup quests. Dependency edges still override this preference.
        progression_window = {
            quest_id
            for quest_id in ready
            if route_key(quests[quest_id])[0] <= minimum_level + 5
        }
        nearby = {
            quest_id
            for quest_id in progression_window
            if _route_zone_distance(
                int(quests[quest_id].get("zone_or_sort", 0)), current_zone
            ) <= LOCAL_ROUTE_RADIUS
        }
        candidates = nearby or progression_window
        quest_id = min(
            candidates,
            key=lambda value: (
                route_key(quests[value]),
                _source_distance(current_location, quests[value].starter_sources),
            ),
        )
        ready.remove(quest_id)
        result.append(quest_id)
        current_zone = int(quests[quest_id].get("zone_or_sort", 0))
        current_location = _nearest_source_point(
            current_location,
            quests[quest_id].finisher_sources or quests[quest_id].objective_sources
            or quests[quest_id].starter_sources,
        )
        for target in edges.get(quest_id, ()):
            indegree[target] -= 1
            if indegree[target] == 0:
                ready.add(target)
    if len(result) != len(quest_ids):
        # Questie has a few historical chain loops. Preserve deterministic output
        # and let the audit expose them instead of silently losing coverage.
        result.extend(sorted(quest_ids - set(result), key=lambda value: route_key(quests[value])))
    return result


def _route_zone_distance(left: int, right: int | None) -> float:
    if right is None:
        return float("inf")
    if left == right:
        return 0
    left_rank = ROUTE_RANK.get(left)
    right_rank = ROUTE_RANK.get(right)
    if left_rank is None or right_rank is None:
        return float("inf")
    return abs(left_rank - right_rank)


def _source_distance(current, sources) -> float:
    if current is None:
        return float("inf")
    map_id, x, y = current
    distances = [
        hypot(location.x - x, location.y - y)
        for source in sources
        for location in source.locations
        if location.map_id == map_id
    ]
    return min(distances, default=float("inf"))


def _nearest_source_point(current, sources) -> tuple[int, float, float] | None:
    points = [
        (location.map_id, location.x, location.y)
        for source in sources
        for location in source.locations
    ]
    if not points:
        return current
    if current is None:
        return points[0]
    same_map = [point for point in points if point[0] == current[0]]
    if not same_map:
        return points[0]
    return min(same_map, key=lambda point: hypot(point[1] - current[1], point[2] - current[2]))
