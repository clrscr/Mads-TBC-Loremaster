# Personal-use alpha.4 validation ledger

The private-use instruction removes public branding, publication and all-character walkthrough-authoring approvals as implementation gates. It does not establish live-client compatibility. This build remains an alpha until its client behavior is verified.

Static checks cover exact-case TOC paths, generated source-row coverage, historical guide/spec consistency, source provenance, dependency and quest-log simulation, and packaging inputs. The Lua 5.1 behavior harness exercises initialization, migration, classification, compatible counts, action routing, recurring history, UI callbacks and optional dependency handling, including the packaged catalog across 104 supported race/class/level profiles.

The validator distinguishes code/artifact errors from unavailable installed-environment evidence. Missing local WoW and independent authored-route fixtures are warnings in static mode. `--require-environment` makes them errors. Public-ready packaging, if ever enabled, also requires them. Neither mode silently uses historical installation records as proof of a current installation.

The bundled phase profile remains the historical Phase 2 profile. Current phase, event state, UI layout, client-modified Lua/API behavior, combat lockdown, taint, practical travel and runtime performance require the unexecuted [client checklist](IN_GAME_SMOKE_TEST.md).

The catalog is larger than the historical guide scope. Source-backed quest coordinates are not a navigation mesh, and unknown availability is not proof that a quest is impossible. Compatible totals are explicitly provisional when unresolved records or a bounded projection prevent a complete result.

## Executed on 2026-09-04

- `QUESTIE_PATH=/private/tmp/mtl-questie LUA=/private/tmp/mtl-lua/src/lua PYTHONPATH=tools python3 -B -m unittest discover -s tests`: 38 Python tests passed, including 60 Lua behavior cases and the packaged catalog across 104 race/class/level profiles and 52 filtered journeys. The interpreter was stock Lua 5.1.5 built locally from its source archive.
- Lua 5.1 syntax compilation: all 182 TOC-loaded Lua files passed.
- Static CLI validation against the pinned Questie source: zero errors and two explicit environment warnings (missing authored-route installation; unavailable configured WoW installation).
- Generated runtime audit: 6,647 source rows, 6,378 included records and 269 explicit exclusions. Legitimate “Test Flight” and “Test of…” quests are retained.
- `git diff --check`: passed.

These checks did not launch WoW, inspect rendered in-game frames, exercise protected execution, or verify today's realm phase. The configured historical installed-client checks remain unverified.

Category/skip validation also covers overlapping metadata, hard exclusions, allowed prerequisite alternatives, access-only parent/enabling relationships, skipped child work, persistence, malformed preferences, selected subtotals, UI control callbacks and waypoint changes. The generated TOC and static runtime inventory include the shared Selection module. The private ZIP must pass CRC and byte-for-byte comparison against every final TOC-loaded file before delivery.

## Executed on 2026-09-05 — alpha.4

- 39 Python tests passed against the pinned Questie source, including 74 Lua behavior cases, 104 character/level profiles, and 52 filtered journeys.
- All 184 TOC-loaded Lua files compiled with stock Lua 5.1.5.
- Static validation passed with zero errors. Missing independent authored-route and installed-client evidence remain explicit warnings.
- Packaging tests verified a single top-level addon folder, ZIP CRC, byte parity for every loaded Lua file, and WowUp `bcc`/20506 release metadata.
- `git diff --check` passed.

The public GitHub repository and tagged development releases are authorized for personal WowUp installation. Readiness flags remain false because live-client verification has not been performed. Public visibility is independent of that gameplay-readiness status.

## Tracker visibility — alpha.5

The local suite passes 39 Python tests, including 77 Lua behavior cases. Added checks cover quest completion while hidden, hidden-state restoration across reloads, saved minimap position, independent dashboard/tracker clicks, and slash-command recovery without a minimap. The changed Lua modules compile under Lua 5.1. The actual minimap appearance, dragging, and combat interaction still require the client checklist.
