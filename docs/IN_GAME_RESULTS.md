# Mad's TBC Loremaster standalone in-game results

Release under test: `1.0.0-alpha.1`

The earlier `0.9.0-rc.1` Guidelime module passed one targeted Darkshore level-gating regression and a live 25-slot quest-log observation. Those results do not verify the new standalone runtime.

## Environment

| Field | Result |
|---|---|
| Client build and realm phase | Not tested |
| Questie version | Intended: `11.32.1`; runtime not tested |
| TomTom version | Not installed/tested |
| Guidelime compatibility version | Intended: `5.028`; runtime not tested |
| Tested Alliance characters | None |

## Critical matrix

| Scenario | Expected | Result | Evidence / issue |
|---|---|---|---|
| Standalone load | Dashboard and tracker load without Guidelime or TomTom | Not tested | — |
| First-launch scan | Counts and three route choices appear | Not tested | — |
| Completed-history accuracy | Known completed quests classify correctly | Not tested | — |
| Continue Journey | Coherent level-appropriate zone sweep | Not tested | — |
| Catch Up | Older recoverable quests form zone sweeps | Not tested | — |
| Get Back on Track | Minimal prerequisite bridge reaches frontier | Not tested | — |
| Overleveled cleanup | Gray quests remain routable | Not tested | — |
| Exclusive outcome | Warning appears; locked alternative does not penalize score | Not tested | — |
| Group deferral | Route advances without granting completion | Not tested | — |
| Recurring score | Current and lifetime activity remain separate from permanent score | Not tested | — |
| Progressive disclosure | Minimal, Route, Arc, and Deep Lore render correctly | Not tested | — |
| Questie updates | Accept, objective, turn-in, and abandon refresh state | Not tested | — |
| TomTom absent | Coordinate guidance works without errors | Not tested | — |
| TomTom present | Correct waypoint and arrow update | Not tested | — |
| Phase override | Future quests unlock only at declared phase | Not tested | — |
| Reload persistence | Selected route and position survive `/reload` | Not tested | — |
| Guidelime compatibility | Legacy chapters register when Guidelime is installed | Not tested | — |

## Sign-off

- Static generator/tests: Pass
- Standalone in-game matrix: Not started
- Public release recommendation: **No — development alpha**
