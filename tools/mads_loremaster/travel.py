from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


KALIMDOR_ZONES = {
    141, 1657, 148, 331, 406, 17, 15, 400, 405, 357, 16, 440, 490,
    1377, 618, 361, 493, 3524, 3525, 3557,
}
EASTERN_KINGDOMS_ZONES = {
    12, 40, 10, 44, 1, 38, 11, 45, 267, 47, 8, 33, 51, 46, 4, 41,
    28, 139, 1519, 1537,
}
OUTLAND_ZONES = {3483, 3521, 3519, 3703, 3518, 3522, 3523, 3520}
DRAENEI_ISLANDS = {3524, 3525, 3557}
CONTINENT_BY_ZONE = {
    **{zone: "Kalimdor" for zone in KALIMDOR_ZONES},
    **{zone: "Eastern Kingdoms" for zone in EASTERN_KINGDOMS_ZONES},
    **{zone: "Outland" for zone in OUTLAND_ZONES},
}

# Ratchet/Booty Bay is the practical crossing for the southern questing loops;
# northern loops use Auberdine/Menethil Harbor.
SOUTHERN_KALIMDOR_ZONES = {17, 15, 400, 405, 357, 440, 490, 1377}


@dataclass(frozen=True)
class TravelLink:
    id: str
    kind: str
    instruction: str
    evidence: tuple[str, ...]


@dataclass(frozen=True)
class TravelPlan:
    type: str
    instruction: str
    link_ids: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()


def load_travel_network(path: Path) -> dict[str, TravelLink]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise ValueError(f"unsupported travel-network schema in {path}")
    if payload.get("game_version") != "Burning Crusade Classic Anniversary":
        raise ValueError(f"travel network is not pinned to TBC Anniversary: {path}")
    links: dict[str, TravelLink] = {}
    for item in payload.get("links", []):
        evidence = tuple(item.get("evidence", ()))
        if not evidence or any("wowhead.com/tbc/" not in ref for ref in evidence):
            raise ValueError(f"travel link {item.get('id')!r} lacks TBC-specific evidence")
        link = TravelLink(
            id=str(item["id"]),
            kind=str(item["kind"]),
            instruction=str(item["instruction"]),
            evidence=evidence,
        )
        links[link.id] = link
    return links


def continent_for(map_id: int) -> str | None:
    return CONTINENT_BY_ZONE.get(map_id)


def plan_travel(
    origin_map_id: int,
    destination_map_id: int,
    links: dict[str, TravelLink],
) -> TravelPlan:
    origin_continent = continent_for(origin_map_id)
    destination_continent = continent_for(destination_map_id)
    if origin_map_id == destination_map_id:
        return TravelPlan("zone_transition", "Continue within the current zone")
    if not origin_continent or not destination_continent:
        return TravelPlan(
            "zone_transition",
            "Use a known flight path when it saves time; otherwise follow roads and zone connections",
        )
    origin_island = origin_map_id in DRAENEI_ISLANDS
    destination_island = destination_map_id in DRAENEI_ISLANDS
    if origin_continent == destination_continent:
        if origin_island != destination_island:
            link_ids = ("auberdine-exodar",)
        else:
            return TravelPlan(
                "zone_transition",
                "Use a known flight path when it saves time; otherwise follow roads and zone connections",
            )
    elif origin_continent == "Outland":
        link_ids = ("shattrath-alliance-portals",)
    elif destination_continent == "Outland":
        if origin_continent == "Kalimdor":
            crossing = _kalimdor_eastern_crossing(origin_map_id, destination_map_id)
            island_leg = ("auberdine-exodar",) if origin_island else ()
            link_ids = (*island_leg, crossing, "dark-portal")
        else:
            link_ids = ("dark-portal",)
    elif origin_island:
        island_leg = ("auberdine-exodar",)
        if destination_continent == "Eastern Kingdoms":
            link_ids = (*island_leg, _kalimdor_eastern_crossing(origin_map_id, destination_map_id))
        else:
            link_ids = island_leg
    elif destination_island:
        island_leg = ("auberdine-exodar",)
        if origin_continent == "Eastern Kingdoms":
            link_ids = (_kalimdor_eastern_crossing(origin_map_id, destination_map_id), *island_leg)
        else:
            link_ids = island_leg
    elif {origin_continent, destination_continent} == {"Kalimdor", "Eastern Kingdoms"}:
        link_ids = (_kalimdor_eastern_crossing(origin_map_id, destination_map_id),)
    else:
        return TravelPlan(
            "zone_transition",
            "Use a known flight path when it saves time; otherwise follow roads and zone connections",
        )

    selected = tuple(links[link_id] for link_id in link_ids)
    instructions = [link.instruction for link in selected]
    if link_ids == ("shattrath-alliance-portals",) and origin_map_id != 3703:
        instructions[0] = f"Return to Shattrath City and {instructions[0][:1].lower()}{instructions[0][1:]}"
    return TravelPlan(
        "transport",
        instructions[0] + "".join(f"; then {item[:1].lower()}{item[1:]}" for item in instructions[1:]),
        link_ids,
        tuple(ref for link in selected for ref in link.evidence),
    )


def _kalimdor_eastern_crossing(origin_map_id: int, destination_map_id: int) -> str:
    kalimdor_map_id = (
        origin_map_id
        if continent_for(origin_map_id) == "Kalimdor"
        else destination_map_id
    )
    southern = kalimdor_map_id in SOUTHERN_KALIMDOR_ZONES
    return "ratchet-booty-bay" if southern else "auberdine-menethil"
