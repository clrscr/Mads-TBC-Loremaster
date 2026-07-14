# Standalone runtime architecture

## Data flow

1. The Python pipeline reads the pinned Questie TBC snapshot, corrections, phase data, entity endpoints, and coordinates.
2. It writes compact Lua quest and zone manifests before the runtime files in the TOC.
3. On login, the runtime waits for `Questie.API.RegisterOnReady`, scans the character, and classifies every visible quest.
4. Route modes consume the same eligibility table and persist only quest IDs and the current index.
5. Questie callbacks and Blizzard quest, skill, reputation, and level events schedule a debounced rescan.

Questie is never mutated. Blizzard completed-quest state remains authoritative.

## Runtime records

- `QuestRecord`: identity, canonical zone, levels, race/class masks, profession/reputation gates, prerequisites, exclusions, recurrence, phase, category, route hint, endpoints, and coordinates.
- `CharacterSnapshot`: faction, race/class masks, level, completed and active quests, professions, and reputations.
- `EligibilityState`: completed, available, active, ready to turn in, blocked, temporarily unavailable, permanently locked, or out of scope.
- `RoutePlan`: mode plus an ordered list of quest IDs. The action and waypoint are derived from the live state.
- `ZoneProgress`: stable permanent denominator and completed count plus available, blocked, locked, and recurring counts.

## Route policies

- Continue selects a level-appropriate authored frontier and completes a coherent canonical-zone sweep.
- Catch Up selects incomplete quests below the current level, groups them by zone, and recursively includes prerequisites.
- Get Back on Track selects the closest level-appropriate frontier and emits its prerequisite bridge plus the destination zone.
- Zone Sweep is an explicit dashboard selection using the same dependency expansion.
- Completed and permanently locked steps collapse automatically. Deferred group/PvP steps remain incomplete.

## Compatibility boundaries

- The standalone runtime is original code and has no Guidelime runtime dependency.
- Generated Guidelime-format chapters remain for existing users. `GuideCompat.lua` captures registration when Guidelime is absent and defers to Guidelime when installed.
- TomTom calls are guarded. A failed or missing adapter never blocks quest tracking.
- Questie’s public readiness and update callbacks are the stable integration. Its private zone converter is used only behind a protected optional call.
