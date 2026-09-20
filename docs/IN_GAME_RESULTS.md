# In-game verification results

Build under test: **1.0.0-alpha.5** (private).

**Not run.** During the 2026-09-20 questing workflow review, the configured TBC Anniversary client was present but not running. An attempt to access it for a smoke test returned “Computer Use was not approved to use Wow.” No in-game, rendering, combat or taint checks were performed. Lua API doubles, syntax checks, catalog generation and static validation do not substitute for those checks.

Use [the client checklist](IN_GAME_SMOKE_TEST.md) and record build, phase, character, dependency versions, observations and failures here after testing. Earlier alpha/legacy installation records under `data/evidence/` are historical and do not establish results for this build.

## Offline questing workflow validation — 2026-09-20

- Full Python suite after the Questie compatibility-policy update: 49 tests passed, including 100 Lua 5.1 behavioral cases. The catalog sweep covers 6,378 records, 104 character/level profiles and 52 filtered journeys. New cases cover live objective-table mutation, turn-in/abandonment events, skipped/excluded held quests, localized search, recurring status, unknown/alternative prerequisites, bounded tracker text, selection and pagination.
- Lua 5.1 syntax: all 184 TOC-loaded Lua files passed. Static validation checks exact file casing/load order, release metadata consistency, manifest coverage and source restrictions; `git diff --check` passed.
- Standard `./mads-loremaster package` validation passed with the verified Questie source revision `0ad1972cbd54f9aac0a5e202fec9ee6c818fbf44`. Development ZIP structure and packaged file parity were checked. No release, installation, or publication was performed.
- Strict environment validation remains incomplete: installed client `2.5.6.69795` differs from the configured client baseline `2.5.6.68575`, and available independent authored-route fixtures do not match the pinned hash. Installed Questie `11.38.0` passes dependency checks under the updated policy; exact Questie version and database parity are no longer requirements. Standard validation retains only the client-version and authored-route warnings. Compatibility metadata and readiness flags remain unchanged.
- UI frames still inherit the game's UI scale and use ordinary, non-secure controls. The changed failure adapter uses the legacy `GetQuestLogTitle` return documented and used by the pinned Questie TBC cache; objective reads retain the existing capability-checked API. These static facts do not prove live rendering or combat behavior. Complete the focused smoke test above before calling the build gameplay-verified.
