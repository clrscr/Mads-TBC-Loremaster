from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


QUEST_KEYS = (
    "name", "started_by", "finished_by", "required_level", "quest_level",
    "required_races", "required_classes", "objectives_text", "trigger_end",
    "objectives", "source_item_id", "prequest_group", "prequest_single",
    "child_quests", "in_group_with", "exclusive_to", "zone_or_sort",
    "required_skill", "required_min_rep", "required_max_rep",
    "required_source_items", "next_quest_in_chain", "quest_flags",
    "special_flags", "parent_quest", "reputation_reward",
    "breadcrumb_for_quest_id", "breadcrumbs", "extra_objectives",
    "required_spell", "required_specialization", "required_max_level",
    "available_until_completed", "available_starting_with", "required_ranks",
    "disabled_by_quest",
)


@dataclass(frozen=True)
class MapPoint:
    map_id: int
    map_name: str
    x: float
    y: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "map_id": self.map_id,
            "map_name": self.map_name,
            "x": self.x,
            "y": self.y,
            "verification": "questie_structured_source_only",
        }


@dataclass(frozen=True)
class QuestSource:
    kind: str
    id: int
    name: str | None
    locations: tuple[MapPoint, ...] = ()
    content_era: str = "pre_cataclysm"
    data_source: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "id": self.id,
            "name": self.name,
            "locations": [location.to_dict() for location in self.locations],
            "content_era": self.content_era,
            "data_source": self.data_source,
            "verification": "questie_structured_source_only",
        }


@dataclass(frozen=True)
class Quest:
    id: int
    values: tuple[Any, ...]
    tag_id: int | None = None
    tag_name: str | None = None
    starter_sources: tuple[QuestSource, ...] = ()
    finisher_sources: tuple[QuestSource, ...] = ()
    objective_sources: tuple[QuestSource, ...] = ()
    content_era: str = "unknown"
    data_sources: tuple[str, ...] = ()

    def get(self, key: str, default=None):
        try:
            index = QUEST_KEYS.index(key)
        except ValueError as error:
            raise KeyError(key) from error
        return self.values[index] if index < len(self.values) and self.values[index] is not None else default

    @property
    def name(self) -> str:
        return self.get("name", f"Quest {self.id}")

    @property
    def prerequisites_all(self) -> tuple[int, ...]:
        return tuple(self.get("prequest_group", ()))

    @property
    def prerequisites_any(self) -> tuple[int, ...]:
        return tuple(self.get("prequest_single", ()))

    @property
    def exclusive_to(self) -> tuple[int, ...]:
        return tuple(self.get("exclusive_to", ()))

    def to_dict(self) -> dict[str, Any]:
        result = {
            "id": self.id,
            "tag_id": self.tag_id,
            "tag_name": self.tag_name,
            "starter_sources": [source.to_dict() for source in self.starter_sources],
            "finisher_sources": [source.to_dict() for source in self.finisher_sources],
            "objective_sources": [source.to_dict() for source in self.objective_sources],
            "content_era": self.content_era,
            "data_sources": list(self.data_sources),
        }
        for index, key in enumerate(QUEST_KEYS):
            result[key] = self.values[index] if index < len(self.values) else None
        return result


@dataclass
class CatalogEntry:
    quest: Quest
    status: str
    reason: str | None = None
    category: str | None = None
    branch: str | None = None
    order: int | None = None
    reason_code: str | None = None
    available_phase: int | None = None
    conditional_categories: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.quest.id,
            "name": self.quest.name,
            "required_level": self.quest.get("required_level", 0),
            "quest_level": self.quest.get("quest_level", 0),
            "zone_or_sort": self.quest.get("zone_or_sort", 0),
            "status": self.status,
            "reason": self.reason,
            "reason_code": self.reason_code,
            "available_phase": self.available_phase,
            "category": self.category,
            "branch": self.branch,
            "order": self.order,
            "conditional_categories": list(self.conditional_categories),
            "content_era": self.quest.content_era,
            "data_sources": list(self.quest.data_sources),
        }


@dataclass
class Catalog:
    source_path: str
    source_revision: str | None
    scope: dict[str, Any] = field(default_factory=dict)
    phase_profile: dict[str, Any] = field(default_factory=dict)
    content_policy: dict[str, Any] = field(default_factory=dict)
    entries: dict[int, CatalogEntry] = field(default_factory=dict)
    zones: dict[int, str] = field(default_factory=dict)

    def selected(self, *statuses: str) -> list[CatalogEntry]:
        wanted = set(statuses)
        return sorted(
            (entry for entry in self.entries.values() if entry.status in wanted),
            key=lambda entry: (entry.order is None, entry.order or 0, entry.quest.id),
        )
