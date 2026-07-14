# Standalone in-game smoke-test checklist

Use this matrix for `1.0.0-alpha.1`. Record results in `IN_GAME_RESULTS.md`. Static validation is necessary but cannot prove live WoW API, UI, quest, or waypoint behavior.

## Setup

- Install the generated `Mads_TBCLoremaster` folder beside Questie in the TBC Anniversary client.
- Test once without Guidelime or TomTom, then repeat navigation with TomTom enabled.
- Confirm the addon title is **Mad's TBC Loremaster**, `/mtl` opens the dashboard, and no Lua error occurs.
- Record client, realm phase, Questie, TomTom, race, class, level, professions, and reputation state.

## First-launch and completion scan

- Test a fresh Alliance character and a progressed Alliance character from different starting races.
- Confirm the first dashboard shows permanent completed/total, available, blocked, locked, and recurring counts before a route is chosen.
- Compare at least ten known completed and ten known incomplete quest IDs with the dashboard classification.
- Confirm a completed mutually exclusive outcome removes its locked alternative from the achievable denominator.
- Confirm gray quests remain recoverable on an overleveled character.
- Confirm profession and reputation quests enter or leave the achievable set when their gates change.
- Log into a Horde character and confirm it is clearly outside the supported completion scope.

## Route modes

- **Continue Journey:** confirm it selects a coherent level-appropriate zone and advances after quest events.
- **Catch Up on What You Missed:** confirm it selects older incomplete quests, groups them by zone, and includes required prerequisites.
- **Get Back on Track:** confirm it builds a prerequisite bridge to a level-appropriate frontier rather than replaying every old zone.
- Reload during each route and confirm mode, quest list, and current position persist.
- Abandon and reacquire a test quest; confirm the route recomputes without marking it complete.
- Complete the final quest in a route and confirm the tracker returns to the no-route state cleanly.

## Choices, groups, and scoring

- Open a mutually exclusive quest and confirm the pre-acceptance warning names conflicting outcomes.
- Test a dungeon, raid, elite, and PvP stop. Confirm **Defer** advances the route while leaving the quest incomplete.
- Use Settings → **Restore Deferred** and confirm the deferred quest can enter a new route again.
- Complete a daily or repeatable and confirm current-cycle and lifetime recurring history update without changing permanent completion.
- Confirm an inactive seasonal quest is visible as unavailable rather than routable.

## Tracker, lore, and navigation

- Confirm Minimal shows one action and waypoint; Route adds routing context; Arc adds a spoiler-light summary; Deep Lore adds the longer note or reviewed fallback.
- For accept, active, and turn-in states, confirm the tracker chooses the correct starter, objective, or finisher point.
- Without TomTom, confirm coordinate guidance remains readable and the addon does not error.
- With TomTom, confirm the waypoint appears on the correct map and the arrow updates after quest state changes.
- Test a cross-zone quest and confirm it affects only its canonical home-zone percentage.

## Phase handling and legacy compatibility

- Confirm Automatic uses the packaged phase profile.
- Change the manual phase override and confirm future-phase quests enter the eligible graph only at their declared phase.
- With Guidelime installed, confirm the legacy guide chapters still register without breaking the standalone dashboard.
- Without Guidelime installed, confirm the compatibility bridge prevents errors while the standalone routes remain usable.

## Release evidence

- Save exact Lua errors, quest IDs, character state, and screenshots for failures.
- A systemic failure reopens every scenario using that code path.
- Before a public beta, run `./mads-loremaster all /path/to/Questie` and `pytest -q`, rebuild the archive, and repeat all critical rows on the packaged files.
