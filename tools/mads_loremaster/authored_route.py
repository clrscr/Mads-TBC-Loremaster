from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

from .model import Catalog
from .scope import load_json_object


TAG_RE = re.compile(r"\[(QA|QC|QT)(\d+)(?:,\d+)?(?:\s[^\]]*)?\]")
GOTO_RE = re.compile(r"\[G\s*([\d.]+)\s*,\s*([\d.]+)\s*([^\]]*)\]")
APPLIES_RE = re.compile(r"\[A\s*([^\]]+)\]")


@dataclass(frozen=True)
class AuthoredRoute:
    id: str
    name: str
    path: Path
    version: str
    interface: str
    sha256: str
    version_limitation: str
    quest_sequence: tuple[int, ...]
    quest_chapters: dict[int, tuple[str, ...]]
    chapter_count: int
    semantic_counts: dict[str, int]
    flight_points: tuple[dict, ...]


def load_authored_routes(config_path: Path) -> list[AuthoredRoute]:
    config = load_json_object(config_path)
    result = []
    for source in config.get("sources", []):
        root = Path(os.environ.get("MADS_AUTHORED_ROUTE_PATH", source["path"])).expanduser().resolve()
        toc = root / "GuideLime_TUGs_TBC.toc"
        if not toc.is_file():
            continue
        toc_source = toc.read_text(encoding="utf-8")
        alliance_files = []
        for raw in toc_source.splitlines():
            relative = raw.strip().replace("\\", "/")
            if relative.startswith("TUGs/Alliance/") and relative.endswith(".lua"):
                path = root / relative
                if path.is_file():
                    alliance_files.append(path)
        digest = _source_hash(root, [toc, *alliance_files])
        expected = source.get("expected_sha256")
        if expected and digest != expected:
            raise ValueError(
                f"authored route {source['id']} hash mismatch: expected {expected}, found {digest}"
            )
        excluded = set(source.get("excluded_character_starts", []))
        sequence = []
        chapters: dict[int, list[str]] = {}
        semantic_counts = {"coordinates": 0, "flight": 0, "flight_path": 0, "hearth": 0}
        flight_points = []
        selected_files = [path for path in alliance_files if path.name not in excluded]
        for path in selected_files:
            text = path.read_text(encoding="utf-8")
            for tag, quest_id in TAG_RE.findall(text):
                if tag != "QA":
                    continue
                value = int(quest_id)
                sequence.append(value)
                chapters.setdefault(value, []).append(path.name)
            semantic_counts["coordinates"] += len(re.findall(r"\[G(?=[\d\s,])", text))
            semantic_counts["flight"] += len(re.findall(r"\[F(?=[\s\]])", text))
            semantic_counts["flight_path"] += len(re.findall(r"\[P(?=[\s\]])", text))
            semantic_counts["hearth"] += len(re.findall(r"\[H(?=[\s\]])", text))
            for line_number, line in enumerate(text.splitlines(), 1):
                if "[P]" not in line:
                    continue
                goto = GOTO_RE.search(line)
                if not goto or not goto.group(3).strip():
                    continue
                applies = tuple(
                    part.strip() for match in APPLIES_RE.findall(line)
                    for part in match.split(",") if part.strip()
                )
                flight_points.append({
                    "x": float(goto.group(1)),
                    "y": float(goto.group(2)),
                    "map_name": goto.group(3).strip(),
                    "applies_to": applies,
                    "source_chapter": path.name,
                    "source_line": line_number,
                })
        result.append(
            AuthoredRoute(
                id=source["id"],
                name=source["name"],
                path=root,
                version=str(source["version"]),
                interface=str(source["interface"]),
                sha256=digest,
                version_limitation=source["version_limitation"],
                quest_sequence=tuple(sequence),
                quest_chapters={key: tuple(dict.fromkeys(value)) for key, value in chapters.items()},
                chapter_count=len(selected_files),
                semantic_counts=semantic_counts,
                flight_points=tuple(flight_points),
            )
        )
    return result


def compare_authored_routes(
    catalog: Catalog, project_root: Path, routes: list[AuthoredRoute]
) -> dict:
    from .guides import PRIMARY_GROUP, parse_guide_file, toc_lua_files
    generated_chapters = []
    generated_sequence = []
    for path in toc_lua_files(project_root):
        title, _, group, tags = parse_guide_file(path)
        if group != PRIMARY_GROUP:
            continue
        quest_ids = [quest_id for tag, quest_id in tags if tag == "QA"]
        generated_sequence.extend(quest_ids)
        generated_chapters.append((path, title, quest_ids))
    generated_positions = {quest_id: index for index, quest_id in enumerate(generated_sequence)}
    sources = []
    quest_sources: dict[int, list[str]] = {}
    chapter_comparisons: dict[str, list[dict]] = {}
    for route in routes:
        authored_unique = tuple(dict.fromkeys(route.quest_sequence))
        authored_positions = {quest_id: index for index, quest_id in enumerate(authored_unique)}
        overlap = set(generated_positions) & set(authored_positions)
        for quest_id in overlap:
            quest_sources.setdefault(quest_id, []).append(route.id)
        sources.append({
            "id": route.id,
            "name": route.name,
            "version": route.version,
            "interface": route.interface,
            "path": str(route.path),
            "sha256": route.sha256,
            "version_limitation": route.version_limitation,
            "selected_chapters": route.chapter_count,
            "accepted_quest_steps": len(route.quest_sequence),
            "unique_quests": len(authored_unique),
            "primary_overlap": len(overlap),
            "relative_order_agreement": _relative_order_agreement(
                [quest_id for quest_id in generated_sequence if quest_id in overlap],
                authored_positions,
            ),
            "semantic_counts": route.semantic_counts,
        })
        for path, title, quest_ids in generated_chapters:
            common = [quest_id for quest_id in quest_ids if quest_id in authored_positions]
            source_chapters = sorted({
                chapter
                for quest_id in common
                for chapter in route.quest_chapters.get(quest_id, ())
            })
            chapter_comparisons.setdefault(path.name, []).append({
                "source_id": route.id,
                "overlapping_quests": len(set(common)),
                "generated_quests": len(set(quest_ids)),
                "relative_order_agreement": _relative_order_agreement(common, authored_positions),
                "source_chapters": source_chapters,
                "review_status": "automated_sequence_comparison_complete",
            })
    return {
        "schema_version": 1,
        "status": "available" if sources else "missing",
        "scope": catalog.scope.get("id"),
        "sources": sources,
        "quest_source_ids": {str(key): value for key, value in sorted(quest_sources.items())},
        "chapter_comparisons": chapter_comparisons,
        "interpretation": (
            "Authored routes support route-order comparison only. They do not independently verify "
            "Anniversary phase availability, quest facts, or coordinates."
        ),
    }


def _source_hash(root: Path, files: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in files:
        digest.update(str(path.relative_to(root)).encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _relative_order_agreement(sequence: list[int], reference: dict[int, int]) -> float | None:
    unique = list(dict.fromkeys(value for value in sequence if value in reference))
    pairs = 0
    agreeing = 0
    for left_index, left in enumerate(unique):
        for right in unique[left_index + 1:]:
            pairs += 1
            agreeing += int(reference[left] < reference[right])
    return round(agreeing / pairs, 4) if pairs else None
