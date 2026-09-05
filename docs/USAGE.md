# Mad's TBC Loremaster

A personal quest-completion addon for Burning Crusade Classic Anniversary. Its goal is one adaptive journey through every available quest for your current character, with progress that updates as you play.

**Development build: `1.0.0-alpha.5`.** Targets interface `20506`, Alliance and Horde, all supported TBC race/class combinations, levels 1–70, Normal PvE and PvP realms. Retail, Era, other Classic expansions and Hardcore are outside this build's scope. Live-client verification of this implementation has not been performed.

## Use

Install the `Mads_TBCLoremaster` directory in the target client's `Interface/AddOns` folder. Enable Questie, the required dependency. TomTom and Guidelime are optional. Log in: the addon waits for Questie's readiness callback and a valid character snapshot, then starts or resumes your journey automatically.

- **Adaptive Journey** retains a useful current action, prioritizes known missable opportunities, and groups work geographically. It includes prerequisites, parent/child quest work, objectives and turn-ins.
- **Catch Up** focuses on unfinished quests below your current level, including gray quests.
- **Get Back on Track** clears the current action preference and selects a fresh useful action from your character's current state.
- **Zone Focus** and **Guide this quest** narrow the journey; prerequisite work may lead outside the selected zone.
- Dungeon, raid, profession, reputation, PvP and recurring quests remain in the catalog. **Skip** leaves a quest unfinished and keeps it in the progress total; restore it from the dashboard when ready.

The dashboard searches quest names or IDs, filters states, shows zone totals, and explains blockers. Select a quest for live objective progress, source instructions, starter/finisher information and conflicting outcomes. Settings control tracker detail, window positions, progress view and a phase override.

```text
/mtl           Toggle dashboard
/mtl scan      Rescan character
/mtl continue  Resume the adaptive journey
/mtl catchup   Focus on lower-level unfinished quests
/mtl back      Select a fresh action (also /mtl track)
/mtl leave     Open the zone departure checklist
/mtl missable  Open the missable-quest forecast
/mtl travel    Open character travel planning
/mtl hide      Hide the mini tracker
/mtl show      Restore the mini tracker
/mtl toggle    Toggle the mini tracker
```

Close the mini tracker with its top-right **X** to reclaim screen space. Your visibility choice survives reloads and logins, and quest progress continues updating while it is hidden. Left-click the book-shaped Loremaster minimap button to show/hide the tracker; right-click it to toggle the dashboard. Questie's supplied minimap library lets you drag the icon around the minimap and remembers its position. Dashboard Settings still includes the tracker visibility toggle. `/mtl show` restores the tracker even if your minimap is hidden by another addon.

## Zone departure, missable forecast, and travel

**Before leaving** is available from the tracker and dashboard. From the dashboard it uses your selected zone, or your current zone when none is selected. It lists local pickups, turn-ins, objectives, unfinished chains, later/travel work, skipped/filtered quests, unknown requirements, and inaccessible quests. Quests with endpoints in the zone are included even when their catalog zone differs. **Guide zone cleanup** builds a journey around this work, preserving Categories and Skip and following necessary prerequisites outside the zone. An empty local action list does not prove the zone is complete.

**Missable forecast** shows known level, breadcrumb, parent-turn-in, choice, reputation, skill, spell, and event conditions before you encounter them. It includes skipped and excluded quests so preferences cannot hide a potential loss. Selecting an entry explains how to preserve it and lists currently reachable dependent quests that could also be lost; a surviving any-of prerequisite prevents a false downstream-loss claim. Held quests do not retain acquisition-level warnings. Forecasts describe source conditions, not an exhaustive live deadline calendar.

**Travel planning** remembers flight connections observed when you open a flight map. Visit flight masters to locate their endpoints; unknown endpoints are not guessed. It maps your hearth when you bind or visit the matching inn subzone, checks for a carried Hearthstone and a known cooldown, and refreshes after the cooldown expires. Riding rank adjusts estimated ground effort. Known connections and a ready hearth influence quest order while current useful work and urgent quests retain priority. TomTom points toward the first transport stop when appropriate.

To teach a reusable boat/zeppelin, portal, or road connection, open Travel planning, choose its type, click **Record departure here**, travel through it, and click **Record arrival here**. Only that direction is recorded; the pending departure and confirmed connections survive reloads. Use permanent public connections rather than temporary player portals. **Cancel recorded departure** discards an unfinished recording.

Travel scores compare relative effort, not elapsed time. There is no terrain mesh, transport timetable, or guaranteed shortest path. Flight riding alone does not establish a usable flying mount. Unrecorded cross-zone roads and transports remain manual; the addon never casts a hearth, boards a transport, or purchases a flight.

## Categories and Skip

Open **Categories** to set **Any**, **Include**, or **Exclude** for each category. Multiple Includes match any selected category; an Exclude always wins. With no Includes, all other categories are allowed. For example, Include Dungeon to focus on dungeon quests, or Exclude Dungeon and Profession to leave those out. A quest can match multiple categories: excluding Profession also excludes a dungeon quest with profession requirements.

Preferences affect both the dashboard and journey and are saved per character. Required quests outside Includes appear as **Required prerequisite for [quest]**, including across zone boundaries. Explicit exclusions and skipped quests are never automatically bypassed; a blocked chain names the preference preventing progress. General questing is the fallback outside the specific content categories; Group/Elite includes dungeons and raids. Ordinary scripted quests are not automatically seasonal events.

The **Selected categories** subtotal follows your chosen progress view and counts each matching quest once. Prerequisite-only additions do not inflate it. Overall completion totals stay unchanged. Search, status filters and pagination do not redefine this category subtotal; zone rows show the same selection within each zone.

**Skip** removes the entire quest from guidance until you restore it—even after a reload or login. It never abandons the quest or marks it complete. Use the **Skipped** status filter to find skipped quests across all categories and zones, then **Restore** or **Restore and guide**. Excluded categories still apply after restoration. Settings offers **Restore all skipped quests**; **Reset categories** changes only category preferences. Old Defer choices are preserved as skips.

## What the progress numbers mean

**Completionist** counts the whole packaged current-faction catalog: other races/classes and incompatible outcomes remain visible. Every recurring quest ID counts once. This view need not be finishable by one character.

**Achievable** projects a compatible set for this character's race, class, professions, choices, phase and known availability. Recoverable level, skill-rank and reputation blockers remain unfinished. Unknown requirements are identified separately; the displayed percentage is provisional when the source cannot establish a complete total. Mutually exclusive branches are evaluated with their dependencies, rather than counted independently. The calculation has a bounded search budget and labels an incomplete projection provisional.

Blizzard completion evidence and observed turn-ins establish progress. Old saved route positions never establish completion. Recurring quests retain their first observed completion across resets; select one explicitly to pursue further runs. Historical recurring completions that Blizzard no longer reports cannot be reconstructed automatically. Progress is per character; only display settings are shared.

## Compatibility and evidence limits

The packaged facts come from [Questie revision `0ad1972cbd54f9aac0a5e202fec9ee6c818fbf44`](https://github.com/Questie/Questie/tree/0ad1972cbd54f9aac0a5e202fec9ee6c818fbf44), version 11.32.1, including common and character-dependent TBC quest corrections. The source-row audit is [runtime-coverage.json](../data/evidence/runtime-coverage.json). The 171 inherited Night Elf Hunter chapters are a separate historical Guidelime compatibility corpus, not the coverage authority for the adaptive journey.

The bundled **Phase 2 profile is historical evidence**, not a claim about the live phase in September 2026. Choose a phase override only after checking your realm. Event activity uses the ready Questie event snapshot; missing readiness/data remains unknown. Questie private profession, reputation, event and map adapters are capability-checked; changes to these interfaces require verification.

Coordinates are source-backed quest destinations or observed travel endpoints, not a verified navigation mesh. The addon does not know every road, cave entrance, transport connection, flight path, or live NPC phase. Hearth planning requires a mapped bind and available cooldown data. Missing instructions and destinations are shown explicitly. Unknown quests observed in your log remain visible without fabricated starters. English source text has not been fully localized; active quest titles/objectives use client text where available.

No quest is accepted, completed, abandoned, or chosen automatically. There are no addon messages, chat broadcasts, external communication or purchase actions. Public GitHub development releases are provided for personal installation through WowUp. The readiness flags describe unverified live behavior, not repository visibility.

## Development and validation

Python 3.10+ runs the source tooling without third-party packages. A stock Lua 5.1 interpreter runs the behavioral harness independently of Questie or WoW:

```sh
PYTHONPATH=tools LUA=/path/to/lua5.1 python3 -B -m unittest discover -s tests
QUESTIE_PATH=/path/to/Questie PYTHONPATH=tools LUA=/path/to/lua5.1 python3 -B -m unittest discover -s tests
./mads-loremaster validate /path/to/Questie
./mads-loremaster package /path/to/Questie
```

Without `QUESTIE_PATH`, source integration tests explicitly skip. Without `LUA`, the runtime behavior test explicitly skips. `validate` checks static artifacts; missing installed-client and authored-route fixtures produce explicit warnings. Add `--require-environment` to require those checks too. Public-ready builds always require them.

`generate` rebuilds the historical chapters and the independent runtime manifests. `catalog` and `audit` still describe the historical Night Elf Hunter route; use `data/evidence/runtime-coverage.json` for both-faction runtime coverage. Supply a Git checkout for automatic commit provenance, or `--source-revision <full SHA>` for an archive whose commit you have independently verified.

See [architecture](STANDALONE_ARCHITECTURE.md), [implementation plan](IMPLEMENTATION_PLAN.md), [validation limits](STATIC_RELEASE_GATE.md), and the [unexecuted client checklist](IN_GAME_SMOKE_TEST.md). The root license applies to original project code; upstream sources retain their own terms and provenance. No Guidelime engine is bundled.
