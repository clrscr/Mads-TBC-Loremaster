#!/usr/bin/env python3
"""Capture the old generated route as a compact, reviewable metric fixture."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


STEP_RE = re.compile(r"^\[(QA|QC|QT)(\d+)")
TITLE_RE = re.compile(r"^\[N(?:\d+-\d+)?\s*(.+)]$")


def snapshot(source: Path) -> dict:
    guides = source / "Guides"
    chapters = []
    for guide in sorted(guides.rglob("*.lua")):
        text = guide.read_text(encoding="utf-8")
        title = guide.stem
        steps = []
        for line in text.splitlines():
            title_match = TITLE_RE.match(line)
            if title_match and not line.startswith("[NX"):
                title = title_match.group(1)
            step_match = STEP_RE.match(line)
            if step_match:
                steps.append(f"{step_match.group(1)[1]}{step_match.group(2)}")
        chapters.append(
            {
                "path": guide.relative_to(source).as_posix(),
                "branch": guide.relative_to(guides).parts[0],
                "title": title,
                "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "steps": steps,
            }
        )
    canonical = json.dumps(chapters, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return {
        "schema_version": 1,
        "captured_date": "2026-07-13",
        "description": (
            "Ordered QA/QC/QT tags from the frozen pre-remediation addon. "
            "Quest facts and coordinates are resolved from the pinned Questie TBC snapshot."
        ),
        "chapter_count": len(chapters),
        "quest_state_steps": sum(len(chapter["steps"]) for chapter in chapters),
        "accepted_quests": sum(
            step.startswith("A") for chapter in chapters for step in chapter["steps"]
        ),
        "canonical_chapters_sha256": hashlib.sha256(canonical).hexdigest(),
        "chapters": chapters,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path, help="Root of the frozen addon")
    parser.add_argument("output", type=Path, help="Snapshot JSON to write")
    args = parser.parse_args()
    payload = snapshot(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
