# Static release gate — 1.0.0-alpha.1

## Environment

- Target: TBC Classic Anniversary, Phase 2 profile, interface `20506`
- Questie: `11.32.1`, pinned revision `0ad1972cbd54f9aac0a5e202fec9ee6c818fbf44`
- Runtime contract: any level 1–70 Alliance race/class and arbitrary prior quest progress
- Dependencies: Questie required; TomTom and Guidelime optional

## Current static results

| Gate | Result | Evidence |
|---|---|---|
| Standalone package contract | PASS | Runtime/data TOC order, SavedVariables, Questie requirement, optional integrations |
| Runtime eligibility manifest | PASS | 4,269 Alliance-visible records, including race/class alternatives, recurring, profession, event, exclusivity, and prerequisite metadata |
| Legacy authored coverage | PASS | 1,910 primary, 577 optional, 140 alternative, and 40 baseline quests |
| Pre-Cataclysm provenance | PASS | Zero post-TBC or correction-only emitted guide quests and zero forbidden source references |
| Dynamic route surface | PASS static | Continue, Catch Up, Get Back on Track, zone sweep, dependency expansion, persistence, and deferral contracts present |
| Completion experience | PASS static | Stable permanent score, separate recurring score, canonical zones, choice warnings, progressive disclosure |
| Navigation adapters | PASS static | Questie readiness/update callbacks and guarded TomTom waypoint adapter present |
| Legacy guide validation | PASS | 171 route specs, 7,881 quest steps, prerequisite order, choice branches, level gates, and resume simulations |
| Automated tests | PASS | `pytest -q`: 33 passed |
| Full validator | PASS | `./mads-loremaster validate /private/tmp/Questie` reports zero errors |
| Installed standalone parity | OPEN | New package has not been deployed and launched in the client |

## Evidence boundaries

- The runtime is original code; no Guidelime engine source is copied. The generated guide-format compatibility layer defers to Guidelime when separately installed.
- Questie’s public callbacks are the stable live integration. The guarded zone-map conversion adapter is optional and must fail safely if Questie changes its private mapping helper.
- The manifest is character-neutral, but the inherited authored route order was reviewed originally on a Night Elf Hunter. Other Alliance starting-race and class flows require live and authored review before public release.
- Static tests cannot prove WoW API signatures, SavedVariables behavior, UI layout, TomTom coordinates, live phase availability, or route quality.

## Remaining public-release gates

- Complete the all-Alliance authored coverage review.
- Complete the standalone matrix in `IN_GAME_RESULTS.md`.
- Record permission for public **Powered by Guidelime** branding, or remove that subtitle while retaining the compatible route format.
