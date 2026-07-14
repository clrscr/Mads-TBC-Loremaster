# Mad's Loremaster Anniversary Audit and Route Remediation Plan

> Historical note: this ledger describes the legacy `0.9.0-rc.1` Guidelime module. The active product is the `1.0.0-alpha.1` standalone runtime documented in `STANDALONE_ARCHITECTURE.md` and `STATIC_RELEASE_GATE.md`.

## Purpose

This document began as the implementation plan for auditing and remediating the entire `Guidelime_MadsLoremaster` addon against the supplied Burning Crusade Classic Anniversary guidance. It now also serves as the release-gate ledger for the `0.9.0-rc.1` candidate. Completed static work is recorded below; uncompleted human and in-game gates remain binding.

## Implementation status — 2026-07-13

| Work package | Status | Current evidence |
|---|---|---|
| 0 — Freeze and reproduce baseline | Complete | Named checksum/count baseline, compact 36-chapter QA/QC/QT route snapshot, and plain `pytest -q` support |
| 1 — Version and phase | Complete for Phase 2 | Versioned scope/profile, explicit pre-Cataclysm-only policy, runtime blacklist evaluation, phase fixtures, future-phase rejection |
| 2 — Quest evidence model | Complete for static RC | Full Questie fields, precise reason codes/categories, 5,297 endpoints, 2,369 objective entities, 19,177 map-scoped coordinates, official phase and time-limited-event evidence, and risk-based source confidence; authored guide remains comparison-only |
| 3 — Coverage audit | Complete for static RC | All 6,647 rows in JSON, CSV, and split Markdown with source URLs, classifications, confidence, and provenance |
| 4 — Playable route model | Complete for static RC; live feel unverified | Dependency-safe world/optional/choice streams, 376 starter-proximity batches covering 953 quests, nearest-endpoint ordering inside safe batches, 263 mandatory chapter-local route-floor gates, adjacent-zone leveling-work heuristic, active-log simulation with percentile load metrics, explicit guidance for all seven quests held across the Auberdine/Darkshore boundary, per-chapter baseline/revised coordinate proxies, 162 explicit chapter handoffs, and 30 optional cross-verified flight-path pickups |
| 5 — Author and review chapters | Static review complete; live play open | All 171 generated specs pass entry, transition, endpoint, objective, warning, recovery, quest-log reserve, bounded-zone, level-gate, and line-budget checks; authored comparison overlaps 1,043 primary quests at 95.88% relative-order agreement |
| 6 — Rich Guidelime output | Complete for static RC | Every accept/turn-in names its source, all 171 chapters expose verified entry instructions (164 with waypoints; seven instance entries use a map name because no safe entrance coordinate exists), all 75 optional/alternative chapters expose dependency-aware branch-entry guidance, four Start Here lines onboard new users, all 21 alternatives have quest-based names and choice previews, 104 dangerous chapters provide one recovery note, five milestones mark the journey, the one cross-chapter retention instruction names all seven carried quests, 162 adjacent handoffs include 52 reviewed TBC transport routes, 263 level gates, 1,361 objective-target, 188 item-use, 139 scripted-event, and 174 tagged-preparation instructions pass string gates |
| 7 — Automated validation | Complete for modeled invariants | 31 tests plus zero-error validator; every accept follows its chapter-local route-floor gate, route floors never decrease, nearby lower-level work is exhausted before a floor increase, all-of and any-of branch prerequisites remain distinct, every cross-chapter active quest has matching retain guidance, onboarding/choice/recovery/milestone guidance is present and nonblocking, flight-path reminders attach to nearby route operations, every adjacent chapter entry/exit is connected, frozen/revised route metrics cover every chapter and enumerate story-split tradeoffs, 2,627 covered and 40 baseline quests pass pre-Cataclysm provenance, no seasonal/inactive event quest is emitted, zero forbidden source references remain, 9,734 strings pass canonical-name/syntax/clarity gates, route-spec/Lua equality holds, and the longest line is 250 characters |
| 8 — Audit documents | Complete as release-candidate evidence | Six-section audit, full coverage, revised-flow chapters, route issues/metrics, uncertainties |
| 9 — In-game verification | Static installation verified; targeted play started | Anniversary build `2.5.6.68575`, Guidelime `5.028`, and Questie `11.32.1` are detected; the level-13 Darkshore distance-aware gate regression passed after `/reload`, and the screenshot verified the 25-quest client maximum; the remaining gameplay rows stay open |
| 10 — Public release | Blocked only by package 9 | Release config is `0.9.0-rc.1`, `public_release_ready: false`; the in-game matrix is the sole remaining blocker |

The generated RC has completed its static release gate and is ready for the documented in-game matrix. Its emitted quest and interaction facts are restricted to Questie's pinned TBC snapshots; Cataclysm and all other post-TBC sources are hard failures. It is not a verified public 1.0 release until that matrix passes.

The independent authored route is used only to compare quest placement and to corroborate
flight-path acquisition points. It is not a phase authority or a substitute for Questie facts.
Likewise, the client-installation probe proves file and dependency identity, not live guide
behavior. This separation keeps static evidence from being overstated as gameplay proof.

## Target outcome

The completed remediation must produce a phase-correct, source-backed, playable Guidelime route for an Alliance Night Elf Hunter from level 10 through 70 on Burning Crusade Classic Anniversary realms. It must account for every verified quest in scope, keep conditional content separate, preserve prerequisites and story chains, reduce avoidable travel, respect the verified quest-log limit, and explain every unresolved uncertainty.

The final audit must contain the six sections required by the guidance:

1. Anniversary Scope and Version
2. Executive Assessment
3. Quest Coverage Audit
4. Routing and Story-Flow Issues
5. Revised Optimal Anniversary Flow
6. Remaining Uncertainties

The final addon and final audit are separate deliverables. A green addon validator is not a substitute for the human-readable audit, and a complete audit is not a substitute for a valid in-game addon.

## Current evidence snapshot

This snapshot records the state inspected on 2026-07-13. It is evidence for planning, not a claim that the addon is already correct.

| Item | Current evidence | Planning consequence |
|---|---|---|
| Client family | `Guidelime_MadsLoremaster.toc` targets interface `20506`; Questie `Questie-BCC.toc` at the pinned revision also targets `20506` | Treat the addon as Burning Crusade Classic Anniversary, not Classic Era Anniversary |
| Live content state | Blizzard's Phase 2 announcement says Overlords of Outland went live on 2026-05-14; current Questie source sets `ContentPhases.activePhases.TBC = 2` | Phase 2 is the default audit profile until a newer official phase is verified |
| Realm ruleset | Blizzard states Anniversary Normal PvE and PvP realms progressed to TBC; Hardcore realms did not | Target Normal PvE and PvP. Exclude Hardcore mechanics, with PvP-world-risk notes where routing differs |
| Character | README and `[GA NightElf,Hunter]` tags specify Alliance Night Elf Hunter | Race- and class-ineligible quests remain outside the playable route but must be classified in the audit |
| Level and baseline | Level 10–70 with 40 Teldrassil quests assumed complete in `config/baseline_teldrassil_1_9.json` | The baseline must be independently audited and exposed as an explicit starting-state contract |
| Questie source | `/private/tmp/Questie`, revision `0ad1972cbd54f9aac0a5e202fec9ee6c818fbf44`, Questie version `11.32.1` | Keep the exact revision in every generated artifact; never report “current Questie” without a commit |
| Current catalog | 6,647 Questie rows: 2,422 primary, 133 alternative, 40 baseline, 4,052 excluded | Every row needs a precise, phase-aware classification; every in-scope quest needs source provenance |
| Current guide output | 36 Lua files and 7,665 quest-state steps | Remediation must preserve addon structural limits while replacing ID-only sequencing with a playable route |
| Current automated result | `PYTHONPATH=tools pytest -q`: 8 passed. Existing `reports/validation.json`: zero errors and zero warnings | Preserve these structural checks, but add new evidence, phase, route, clarity, and in-game gates |
| Unconfigured test entry point | Plain `pytest -q` fails because `tools/` is not on `sys.path` | Standardize a reproducible test command as part of tooling work |

Current authoritative external references:

- [Blizzard: Burning Crusade Classic Anniversary Edition Now Live](https://worldofwarcraft.blizzard.com/en-us/news/24242436)
- [Blizzard: Phase 2 / Overlords of Outland Now Live](https://worldofwarcraft.blizzard.com/en-us/news/24276751)
- [Blizzard: Anniversary realm rules and Hardcore non-progression](https://worldofwarcraft.blizzard.com/en-us/news/24156594/)
- [Questie revision used by the addon](https://github.com/Questie/Questie/tree/0ad1972cbd54f9aac0a5e202fec9ee6c818fbf44)
- [Questie TBC phase definitions at the pinned revision](https://github.com/Questie/Questie/blob/0ad1972cbd54f9aac0a5e202fec9ee6c818fbf44/Database/Corrections/ContentPhases/BurningCrusade.lua)
- [Wowhead's TBC Anniversary phase roadmap](https://www.wowhead.com/tbc/guide/the-burning-crusade-classic-anniversary-phase-release-roadmap), used as secondary context rather than the phase authority

## Confirmed pre-remediation gaps (historical baseline)

These findings describe the frozen pre-remediation baseline and explain the work packages below.
They are retained for traceability; the implementation-status table and generated audit are the
authority for current closure state.

### 1. Phase filtering is incomplete

`tools/mads_loremaster/questie.py::load_hard_blacklist` reads only literal `questId = true` lines from `QuestieQuestBlacklist.lua`. It does not evaluate:

- Questie's `BlacklistTbcQuestsByPhase` table;
- conditional blacklist expressions based on expansion or active phase;
- Anniversary-TBC runtime conditions;
- event activation state.

The current Phase 2 addon consequently includes 15 Phase 3 quest IDs and one Phase 4 quest ID declared future content by the pinned Questie revision. The known Phase 3 IDs are `11063`, `11064`, `11067`–`11071`, and `11107`–`11114`; Phase 4 includes `9524`. These appear in the final primary and alternative guide files.

The first implementation gate must make phase evaluation correct before any new coverage count is accepted.

### 2. “Complete” currently means complete against one parsed dataset

The present audit uses one Questie snapshot. It does not record a field-by-field comparison with Blizzard, Wowhead TBC, another addon dataset, archived evidence, or in-game observations. `reports/audit.json` has no supporting URLs, retrieved dates, source versions, disagreement records, or confidence state.

The final completeness claim must be based on a source matrix, not only on absence from one database.

### 3. Exclusion categories are too broad

The current “Questie hard blacklist” reason merges unavailable, duplicate, event, entitlement, and other cases. The guidance requires those states to be distinguishable. Repeatable, daily, seasonal, profession, class, dungeon, raid, PvP, reputation, attunement, and event quests also need separate audit categories even when omitted from the main route.

### 4. The generated sequence is not a practical route model

`route_key` sorts first by minimum level, then by a single zone rank. `plan_operations` normally emits `[QA]`, `[QC]`, and `[QT]` for one quest before moving to the next. It does not represent:

- simultaneous pickups at a hub;
- shared objective loops;
- starter, objective, and turn-in coordinates;
- road, cave, elevation, ship, zeppelin, portal, or flight-path travel;
- hearth binding or cooldown;
- mount and flying access;
- quest retention or postponed turn-ins;
- item-use mechanics;
- group, elite, escort, timed, dungeon, or raid preparation;
- story-continuity tradeoffs.

The current maximum of eight active quests is evidence that the structural simulator is conservative; it is not evidence of an efficient quest route.

### 5. Guide instructions are intentionally sparse

The README says the guide contains only quest-state tags and relies on Questie/Guidelime to display names, objectives, and pins. The supplied guidance requires explicit instructions when an item use, cave entrance, elevation change, escort, dangerous step, group requirement, transport action, conditional branch, retention decision, or ambiguous location matters. Those details need a verified instruction layer.

### 6. Existing validation does not prove the requested outcome

Current validation proves ID existence, state order, prerequisites, exclusivity, file registration, line limits, and a simulated active-quest maximum. It explicitly does not prove phase behavior, NPC availability, map pins, or waypoint quality. Resume simulation is always successful because the current guide has no mandatory non-quest steps.

New validators must cover source provenance, phase availability, route structure, step clarity, quest-log state at every step, branch entry requirements, and travel/story regressions.

### 7. The smoke-test checklist is not phase-scoped

The checklist asks the tester to inspect a Sunwell/Isle of Quel'Danas quest “in the fully unlocked phase,” while the current live Anniversary target is Phase 2. Smoke tests must be generated from the selected phase profile and must separately test future-phase rejection.

## Scope contract to approve before remediation

The default contract below is derived from the current addon and current official realm state. Any change must be made in a versioned scope file and reflected in all reports.

| Dimension | Planned default |
|---|---|
| Game version | Burning Crusade Classic Anniversary Edition |
| Content phase | Phase 2, Overlords of Outland, verified at build time |
| Realm rulesets | Normal PvE and PvP; no Hardcore |
| Region | Region-neutral unless a quest/event schedule is region-dependent |
| Faction | Alliance |
| Race | Night Elf |
| Class | Hunter |
| Level range | Start at level 10, progress through level 70 |
| Starting state | The explicitly verified Teldrassil 1–9 baseline only |
| Primary route | Permanent, non-repeatable world quests available to the character in the selected phase |
| Main optional branches | Hunter, dungeon, heroic dungeon, raid, attunement, reputation, one-time PvP, mutually exclusive choices, Aldor/Scryer |
| Audit-only categories | Repeatable, daily, weekly, monthly, seasonal, event, profession, other-class, other-race, other-faction, unavailable, future-phase, promotional/entitlement, obsolete/test/duplicate |
| Profession assumption | None; profession-gated quests stay in a separate conditional appendix |
| Reputation assumption | No pre-earned reputation except what the route itself can establish; external reputation requirements become explicit gates |
| Dungeon/raid assumption | Optional branches, never silently required to continue the permanent solo/world route unless a verified chain dependency makes that unavoidable |
| Aldor/Scryer | Neither silently assumed before the choice; both branches audited, with one clearly identified default only after route comparison |
| PvP | One-time PvP quests may be included; repeatable PvP is audit-only unless scope is explicitly expanded |

Questions that must be resolved at the scope gate if the defaults are not acceptable:

1. Should the release remain pinned to Phase 2, or should the tool generate separate Phase 1–5 profiles for archival and future use?
2. Should the main route optimize for a fresh level-10 character, a level-70 completionist cleaning old zones, or publish two route modes? The recommended design supports both without mixing their step order.
3. Is “every quest” intended to include profession and live event routes as selectable addon chapters, or only as complete audit appendices?
4. Should one Aldor/Scryer side remain the default, or should both be equal top-level choices?

## Source and evidence policy

### Source priority

Use sources in this order for each factual field:

1. Blizzard announcements, patch notes, and in-game behavior for phase/ruleset availability.
2. Questie data and runtime corrections matching the selected Anniversary client, phase, faction, race, and class.
3. A version-appropriate Wowhead TBC quest page or database record.
4. A second compatible structured source such as BtWQuests/BtWGuides, Guidelime route data, or another maintained addon dataset.
5. Zygor or another authored route for routing comparison where legally accessible.
6. Archived databases and community reports only when higher-priority sources are incomplete; label their version limitations.
7. In-game verification for conflicts, dynamic availability, waypoint behavior, or fields that cannot be established from static sources.

Retail, Classic Era, Season of Discovery, original 2019 Classic, original 2021 TBC Classic, Wrath Classic, private servers, and later expansions are disallowed as direct evidence unless a record explicitly proves an Anniversary-equivalent mechanic. Such use must be labelled as equivalence evidence, not as Anniversary evidence.

### Evidence record

Create one normalized evidence record per quest and per contested field. At minimum, retain:

- quest ID and canonical name;
- source URL or local source identifier;
- source revision/version and retrieval date;
- game version, phase, faction, race, class, and realm applicability;
- the exact field(s) supported: availability, prerequisite, starter, finisher, objective, coordinate, restriction, mechanics, or route advice;
- whether the evidence is primary, structured secondary, authored route, community, or in-game;
- agreement, disagreement, or unresolved state;
- confidence and reviewer note;
- licensing/provenance note when data is imported rather than cited.

Do not copy large amounts of proprietary guide text. Store facts, source pointers, and original route wording.

### Minimum evidence gate

Before a quest is marked verified:

- Questie or another phase-aware structured dataset must establish the row and dependency metadata.
- Official Blizzard evidence must establish the selected release phase and activation state.
- A second source is required for version-sensitive conflicts, emitted travel coordinates, and factual route changes whose safety depends on the disputed field.
- Independent authored-route placement is recorded where available, but it is not treated as a phase authority or required for every low-risk/excluded catalog row.
- Any field used to change the route must have supporting evidence.
- Any conflicting field must have a conflict record and resolution rationale.
- Coordinates are emitted only when the map, NPC/object, and version are verified.
- Unresolved Anniversary specificity is labelled `Unverified`; it is not silently inferred from TBC 2007 or TBC Classic 2021.

This risk-based policy is versioned in `config/source_policy.json`. It avoids pretending that a
community route is an independent quest database while preserving stronger gates where an error
would change phase availability, travel behavior, or player safety.

## Planned data and artifact layout

Exact names may be adjusted during implementation, but the separation of concerns is required.

| Artifact | Purpose |
|---|---|
| `config/scope.json` | Versioned character, level, realm, category, and starting-state contract |
| `config/phases/tbc_anniversary_phase_2.json` | Phase name, activation date, official sources, available/unavailable content gates |
| `config/source_policy.json` | Source priority and minimum verification rules |
| `data/evidence/quests.jsonl` | Normalized quest facts and source records |
| `data/evidence/conflicts.jsonl` | Source disagreements, selected interpretation, and uncertainty |
| `data/route/chapters/*.json` | Human-reviewable hub/loop/story chapter specifications |
| `reports/anniversary-audit/quest-coverage.csv` | Complete machine-readable coverage table for all catalogued quests |
| `reports/anniversary-audit/quest-coverage/*.md` | Split human-readable tables so every verified in-scope quest is visible without an unmanageable single file |
| `reports/anniversary-audit/route-issues.md` | Current sequence, issue, correction, improvement, log/travel implications, and tradeoff |
| `reports/anniversary-audit/revised-flow/*.md` | Numbered route chapters matching the generated addon |
| `reports/anniversary-audit/AUDIT.md` | Assembled six-section audit required by the guidance |
| `reports/anniversary-audit/uncertainties.json` | Machine-checkable unresolved claims |
| `reports/route-metrics.json` | Baseline/revised travel, backtracking, batching, active-log, and branch metrics |

Generated Lua remains under `Guides/`, but the route specification must be the reviewable source of truth. Generated Lua must not become the only place where routing intent exists.

## Ordered implementation work

### Work package 0 — Freeze and reproduce the baseline

1. Record checksums for the current addon, generated reports, package, Questie revision, and Questie version.
2. Add a single documented test command that works from a clean checkout/environment.
3. Re-run catalog, validation, audit, and tests without changing the selected source revision.
4. Preserve the current reports as a named pre-remediation baseline for metric comparison.

Exit gate:

- A clean rebuild reproduces all current counts or explains every difference.
- The pinned Questie revision is available and recorded.
- No current generated output is used as an undocumented input later.

### Work package 1 — Make version and phase explicit

1. Implement the scope and phase configuration artifacts.
2. Parse or faithfully model Questie's TBC content-phase blacklist and conditional blacklist semantics for the selected client state.
3. Apply the same Alliance/Night Elf/Hunter context Questie applies at runtime.
4. Model event activation separately from permanent phase availability.
5. Classify future-phase quests as `Unavailable` with their release phase; do not merge them into a generic blacklist.
6. Add regression fixtures for the 16 currently observed future-phase leaks.
7. Add positive Phase 2 fixtures for content Blizzard says is live, including Ogri'la and Sha'tari Skyguard eligibility where character restrictions permit it.

Exit gate:

- No Phase 3–5 quest is emitted in a Phase 2 route.
- Changing the phase profile produces intentional, reviewable coverage deltas.
- The audit states its selected phase and official evidence.

### Work package 2 — Build the complete quest evidence model

1. Preserve all relevant Questie quest fields rather than reducing report rows to name, level, zone, status, branch, and order.
2. Normalize all prerequisite forms: all-of, any-of, parent/child, breadcrumb, next-chain, disabled-by, available-until, and available-starting-with.
3. Normalize starter and finisher NPC/object/item sources and their map coordinates.
4. Normalize objectives, required/source items, item-use triggers, extra objectives, and scripted/timed mechanics.
5. Model restrictions separately: faction, race, class, profession, reputation, attunement, level, max level, riding/flying, dungeon difficulty, raid, PvP, event, and phase.
6. Model quest kind separately: permanent, optional, repeatable, daily/weekly/monthly, seasonal/event, item-triggered, dungeon, raid, group, elite, escort, PvP, class, profession, reputation, and attunement.
7. Replace conflated exclusion reasons with precise statuses and reason codes.
8. Attach source records and conflicts to the exact fields they support.

Exit gate:

- All Questie rows have one primary audit status and zero or more explicit conditional categories.
- Every covered quest has enough data to explain why it is in scope and available.
- Every excluded or conditional quest has a non-conflated reason.
- No source disagreement is lost during normalization.

### Work package 3 — Complete the quest coverage audit

Audit in deterministic slices so progress and review are measurable:

1. Teldrassil baseline and level-10 entry.
2. Kalimdor world zones through level 30.
3. Eastern Kingdoms world zones through level 30.
4. Kalimdor and Eastern Kingdoms level 30–45.
5. Kalimdor and Eastern Kingdoms level 45–58.
6. Hellfire Peninsula and Zangarmarsh.
7. Terokkar Forest and Nagrand.
8. Blade's Edge Mountains, Netherstorm, and Shadowmoon Valley.
9. Hunter class quests.
10. Dungeon and heroic-dungeon quests.
11. Raid and attunement quests available in the selected phase.
12. Reputation and Aldor/Scryer branches.
13. One-time PvP quests.
14. Audit-only categories: profession, repeatable, daily, seasonal/event, other class/race/faction, promotional/entitlement, unavailable, obsolete/test/duplicate, and future phase.

For each quest, produce the required table columns:

- guide section or step;
- quest name;
- verified quest ID or `Unverified`;
- status: Present, Missing, Misordered, Duplicate, Conditional, Unavailable, or Unverified;
- Anniversary version/phase applicability;
- prerequisite or restriction;
- recommended correction;
- supporting source links.

Exit gate:

- Every verified quest within scope appears in the audit, including quests with no problem.
- The union of primary, optional/conditional, baseline, unavailable, and excluded categories equals the normalized catalog.
- Missing, duplicate, misordered, and unverified lists are explicit and non-empty only when supported by evidence.

### Work package 4 — Define a playable route model

Replace the single quest-order list with a constrained route plan.

The route planner must treat these as hard constraints:

- version and phase availability;
- faction/race/class and other restrictions;
- prerequisite and breadcrumb order;
- mutually exclusive choices;
- parent quests that must remain active;
- quest level and access requirements;
- verified quest-log capacity;
- dungeon, heroic, raid, group, reputation, attunement, riding, and flying gates.

It must optimize among currently legal steps using these soft goals:

- collect all nearby pickups before leaving a hub;
- group shared mobs, objects, items, caves, and objective areas;
- finish a geographic loop before returning to a hub;
- minimize continent changes and isolated cross-zone trips;
- acquire flight paths on first practical arrival;
- use ships, zeppelins, portals, hearths, and zone transitions intentionally;
- bind and use the hearth only when the later benefit exceeds the setup travel;
- delay turn-ins only when the next loop benefits and quest-log pressure stays safe;
- keep connected story chains together unless travel savings clearly justify a split;
- avoid dangerous, elite, escort, or low-drop steps without preparation notes;
- preserve room in the quest log for incidental/class/dungeon quests.

The route specification needs semantic step types for:

- accept;
- complete one or more objectives;
- turn in;
- retain/postpone;
- abandon/skip;
- travel/zone transition;
- acquire/use flight path;
- bind/use hearth;
- ship/zeppelin/portal;
- use item or perform special mechanic;
- group/elite/escort/timed warning;
- dungeon/raid preparation;
- branch choice and branch re-entry.

Before enforcing a numeric quest-log cap, verify it in the intended Anniversary client. Treat the current 23-quest “working cap” as an unverified safety policy, not a client fact. Record both the client maximum and the route's reserved-slot policy.

Exit gate:

- Every route step is legal in a stateful simulation.
- No step exceeds the verified log cap or reserved-slot policy.
- Every intentional story split or travel regression has a documented tradeoff.
- Baseline and revised travel metrics exist for every chapter.

### Work package 5 — Author and review route chapters

Author the route as hub loops and story chapters, not arbitrary 270-operation chunks. Within each coverage slice:

1. Establish the entry location, expected level, hearth state, flight paths, and free quest-log slots.
2. Batch hub pickups.
3. Order objective loops by terrain and shared objectives.
4. Place turn-ins and collect follow-ups before departure.
5. Move dungeon/raid/group work into clearly linked optional preparation chapters.
6. Keep long-distance breadcrumb and story chains coherent.
7. Add only verified NPC names and coordinates.
8. Add cave entrances, elevation, item-use, escort, timed, elite, contested, and low-drop warnings where needed.
9. Add safe resumption points for partially completed and level-70 characters.
10. Review the chapter against at least one independent authored route where available, without copying its prose.

Each chapter review must answer:

- Does it contain every in-scope quest for the covered hub/zone?
- Are conditional quests clearly branched?
- Are objectives combined wherever practical?
- Are all prerequisites and story links preserved?
- Is the quest log safe at every step?
- Can a player understand every non-obvious action without relying on Retail behavior?
- Are travel and danger assumptions appropriate for the expected level and mount state?

Exit gate:

- A reviewer can play the chapter from its declared entry state without inferring missing actions.
- Chapter boundaries correspond to actual hubs, loops, dungeons, or story arcs.
- No chapter title is merely the zone of its first quest when the body spans unrelated content.

### Work package 6 — Generate rich Guidelime output

1. Extend the internal operation model to carry semantic route steps and evidence references.
2. Map only supported Guidelime syntax after verifying it against the installed/current Guidelime version.
3. Preserve Questie/Guidelime quest-state automation for `[QA]`, `[QC]`, and `[QT]`.
4. Emit original concise text for travel, special mechanics, warnings, retention, and choices.
5. Make non-retroactive travel steps conditional or safely skippable for existing characters.
6. Generate chapter names, level ranges, next links, groups, and branch entry notes from the route specification.
7. Preserve the Lua line limit and addon load order.
8. Record the scope version, phase, source revisions, and generation timestamp in reports and package metadata.

Exit gate:

- Generated Lua matches the reviewed route specification exactly.
- Every emitted quest ID and coordinate has evidence.
- Existing-character resumption never blocks on a travel instruction that is already satisfied or irrelevant.
- Alternative routes state their prerequisites and do not assume hidden completion.

### Work package 7 — Expand automated validation

Keep all current structural checks and add:

#### Version and evidence gates

- selected interface and game version match;
- selected phase has an official source and activation state;
- no future-phase quest appears;
- all version-sensitive rows have source provenance;
- unresolved facts are reported, never silently accepted.

#### Coverage gates

- every normalized quest has exactly one audit status;
- every in-scope quest appears exactly once in the appropriate route/branch;
- every conditional category is reported separately;
- exclusions use precise reason codes;
- coverage reports and generated Lua agree.

#### Graph and state gates

- all prerequisite variants and breadcrumb order hold;
- parent/child active-state requirements hold;
- exclusive and faction branches never conflict;
- item-, reputation-, level-, riding-, dungeon-, and phase-gated steps cannot occur early;
- accepted, completed, retained, abandoned, and turned-in state remains consistent.

#### Route gates

- active quest count and reserved slots at every step;
- all accepted quests are eventually resolved or intentionally retained across a named boundary;
- no objective occurs before acceptance;
- shared-objective batches are not accidentally split without rationale;
- chapter entry/exit travel is connected;
- every hearth/transport action has a legal origin and destination;
- no mandatory route depends on an optional branch unless documented.

#### Clarity gates

- special item-use objectives require an instruction;
- dungeon/raid/group/elite/escort/timed flags require a warning or reviewed exemption;
- coordinates include a verified map context;
- retain/postpone/abandon/skip decisions are explicit;
- ambiguous branch entry and future-phase language is rejected.

#### Regression gates

- fresh level 10;
- partial completion at multiple chapter boundaries;
- level 70 cleanup mode;
- Aldor and Scryer;
- PvE and PvP travel-note variants where applicable;
- phase upgrade/downgrade;
- phase-unavailable quest rejection;
- clean package load and all next-chapter links.

Exit gate:

- The expanded suite passes from a documented clean command.
- Failures name the quest, chapter, state, and violated invariant.
- Route-quality metrics are compared with the frozen baseline and regressions require written justification.

### Work package 8 — Produce the required audit documents

Generate the final six-section audit from the normalized evidence and reviewed route.

The Executive Assessment must explicitly answer whether the guide is complete, phase-valid, correctly ordered, practical, efficient, and narratively coherent.

Every routing issue must include:

- current sequence;
- why it fails or underperforms;
- recommended sequence;
- expected improvement;
- quest-log implications;
- travel/hearth/transport/dungeon/group considerations;
- story-versus-efficiency tradeoff.

Every revised-flow step must include, when applicable:

- accepts;
- objectives completed together;
- turn-ins;
- retain/postpone/abandon/skip decisions;
- NPC names and verified coordinates;
- flight path, hearth, ship, zeppelin, portal, and zone transitions;
- conditional branches;
- group, elite, escort, dungeon, raid, reputation, and attunement requirements;
- quest-log capacity;
- reasons for deliberate delays.

Exit gate:

- The assembled Markdown and machine-readable reports agree.
- All source links resolve or are preserved as dated archival references.
- All unresolved claims appear in Remaining Uncertainties and the machine-readable uncertainty file.

### Work package 9 — In-game Anniversary verification

Run against the exact intended TBC Anniversary client, current Questie, and current Guidelime.

Minimum matrix:

- fresh/representative level-10 Night Elf Hunter opening;
- at least one complete chapter in each level band;
- every cross-continent and transport pattern;
- every branch type;
- Hunter class chain;
- dungeon and heroic-dungeon preparation;
- raid/attunement content available in Phase 2;
- Aldor and Scryer selection;
- Ogri'la and Sha'tari Skyguard Phase 2 availability;
- item-use, cave/elevation, escort, timed, elite/group, and low-drop examples;
- partial-completion resume;
- level-70 cleanup resume;
- future-phase quest absence;
- PvE and PvP realms where route risk differs.

Capture:

- client build and region;
- realm ruleset;
- phase/date;
- Questie and Guidelime versions;
- character state;
- chapter and step;
- quest ID;
- screenshot/log/NPC dialogue when resolving a conflict;
- result and follow-up issue.

Exit gate:

- All critical paths pass.
- Any untested low-risk repetition is explicitly bounded and justified.
- Any failed or contradictory observation reopens its evidence and route review.
- The final audit lists all remaining in-game uncertainties.

### Work package 10 — Release and phase-maintenance gate

1. Rebuild all guides, reports, and the package from pinned inputs.
2. Verify no stale generated files remain.
3. Run the complete automated and in-game release checklists.
4. Publish source revisions, selected phase, known limitations, and upgrade instructions.
5. Treat a phase change as a new audited release: update official phase evidence, regenerate deltas, review newly available chains, rerun route integration, and repeat targeted in-game checks.

Exit gate:

- Package contents match validated generated output.
- The selected Anniversary phase is visible to users before they start the route.
- Future phase content is neither silently shown nor silently discarded.

## Route-quality measurement plan

The route cannot be declared “optimized” only because it is topologically valid. Record at least these metrics for the current and revised route:

- number of continent transitions;
- number of zone transitions;
- repeated hub visits;
- isolated pickup/objective/turn-in trips;
- objective clusters completed per travel loop;
- flight paths acquired before first use;
- hearth binds and uses;
- transport waits/crossings;
- total proxy travel distance using verified coordinates and transport edges;
- maximum and percentile active quest counts;
- quests held across chapter boundaries;
- story-chain splits;
- optional-content dependencies in the primary route;
- dangerous/group steps without preparation buffers.

Do not set an arbitrary percentage target before the baseline is measured. The acceptance standard is:

- every avoidable backtrack identified by the audit is removed or justified;
- revised chapters do not improve local distance by creating worse later travel or quest-log pressure;
- aggregate travel metrics improve materially;
- any metric regression has a documented story, access, safety, or prerequisite reason;
- manual play review agrees that the route is practical.

## Completion evidence matrix

| Guidance success criterion | Evidence required before completion |
|---|---|
| 1. Version-appropriate Anniversary information only | Versioned scope, official phase source, phase-aware catalog tests, prohibited-source review, in-game client record |
| 2. Every verified quest in scope | Complete normalized catalog, coverage CSV/Markdown tables, set-equality validator, reviewed category slices |
| 3. Conditional categories separated | Precise reason/category model, separate audit sections/branches, no conflated hard-blacklist reason |
| 4. Prerequisites and story chains preserved | Dependency graph, stateful route simulation, breadcrumb/parent/exclusive tests, chapter story review |
| 5. Playable under travel, danger, groups, and quest-log limits | Verified client limit, route simulator, semantic instructions, manual Anniversary play matrix |
| 6. Avoidable travel/backtracking substantially reduced | Frozen baseline metrics, revised metrics, issue-by-issue closure, documented tradeoffs |
| 7. Complete revised step-by-step route | Reviewed route specs, matching Lua, revised-flow documents, chapter entry/exit checks |
| 8. Corrections sourced and uncertainties labelled | Per-field evidence records, links in coverage table, conflict log, Remaining Uncertainties, in-game evidence |

The remediation is not complete if any row has missing, indirect, stale, or contradictory evidence.

## Risks and controls

| Risk | Control |
|---|---|
| The live phase changes during work | Pin a phase per release; re-check Blizzard and Questie before final generation |
| Questie runtime Lua semantics differ from the parser | Add fixtures from actual Questie source and compare parsed results with in-game Questie behavior |
| Wowhead or another site is ambiguous or inaccessible | Record URL/version limitation, use another independent source, and escalate to in-game verification |
| Authored guides disagree on routing | Treat them as route evidence only; preserve factual dependencies from verified data and document the tradeoff |
| Proprietary source text is copied | Store factual metadata and original wording only; keep source pointers and licensing notes |
| Complete quest coverage creates an unplayable linear route | Separate primary progression from optional completionist chapters and provide explicit branch/re-entry rules |
| Added travel text blocks existing characters | Use conditional/skippable travel steps and test partial/level-70 resume states |
| Quest-log capacity is assumed incorrectly | Verify client maximum in game and separately configure a safety reserve |
| Coordinate data uses the wrong map/version | Require map-context and version provenance; omit uncertain coordinates |
| The scope is too large for one review pass | Review deterministic slices with set-equality gates; never declare global completion from a sampled slice |

## Recommended execution order

The critical path is:

1. Freeze baseline.
2. Approve scope.
3. Correct version/phase modeling.
4. Build evidence and conflict records.
5. Complete the quest coverage audit.
6. Build the route model and metrics.
7. Author/review route slices.
8. Generate richer Lua and reports.
9. Run expanded automated validation.
10. Run in-game Anniversary verification.
11. Package only after every completion-evidence row passes.

Route rewriting before steps 2–5 would risk optimizing quests that are unavailable, missing, misclassified, or tied to the wrong branch. Packaging before in-game verification would repeat the current gap where static validity is stronger than live playability evidence.

## Definition of done

The remediation can be called complete only when all of the following are true:

- the scope and phase are explicit and current for the release;
- every catalogued quest has a precise audit status;
- every verified in-scope quest is present exactly once in the correct route or branch;
- future, optional, repeatable, class, profession, reputation, dungeon, raid, PvP, event, and other conditional content is clearly separated;
- all dependencies and mutually exclusive choices are preserved;
- every route chapter is a practical hub/loop/story unit with complete instructions;
- quest-log, transport, mount, danger, group, and special-mechanic constraints are validated;
- travel metrics and issue closure show material improvement without hidden downstream regressions;
- every factual correction has version-appropriate supporting links;
- every disagreement or unverifiable claim remains visibly uncertain;
- automated tests, generated reports, Lua validation, packaging checks, and the in-game Anniversary matrix all pass;
- the final package, final audit, and pinned inputs are mutually consistent.
