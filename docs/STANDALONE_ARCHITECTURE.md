# Adaptive runtime architecture — alpha.4

This is the active private product. The legacy Night Elf Hunter walkthrough generator remains a reproducible historical compatibility surface.

## Load and state flow

The case-sensitive TOC loads `data/QuestManifest.lua`, `data/ZoneManifest.lua`, `data/Lore.lua`, then Core, Character, Eligibility, Selection, Planning, Travel, Router, Navigation, GuideCompat and UI. Legacy guide registration follows those modules. Questie is required; TomTom and Guidelime are optional.

1. `ADDON_LOADED` installs slash commands; `PLAYER_LOGIN` initializes once and unregisters the one-shot event. An unsupported interface gets an explicit status.
2. Core normalizes schema-2 SavedVariables before module initialization. Display preferences are account-wide. Journey intent, completion evidence, recurring history, skipped IDs, observations and choice acknowledgments are per character.
3. Questie's public readiness callback enables scanning. Event bursts coalesce for 150 ms. Invalid completion/log/identity data preserves the last good snapshot and journey, with three bounded retries and later event/manual retries.
4. Character snapshots contain live identity, completion IDs, log entries/objectives, skill ranks, reputation and converted map IDs. Equal objective-only snapshots skip downstream work. No OnUpdate handler runs.
5. Eligibility resolves cached faction/class/Human-specific variants, then produces a state, reason and blocker for each record. Completed and active observations take precedence over speculative source availability.
6. The compatible projection includes dependency-connected choice components and preserves observed work. Its signature cache avoids solving unchanged membership; branch-and-bound is capped at 4,096 attempts per component. Unknown or bounded results are provisional.
7. Router derives actions from journey intent and current state. It bridges all-of/any-of requirements, keeps parents active for child work, reserves two log slots, skips manually skipped work, and retains a useful action across reloads. Completion, objective changes and availability changes rebuild actionable steps.
8. Navigation selects valid endpoint coordinates, converts AreaID to UiMapID only through the adapter, and updates only its own TomTom waypoint when the destination changes. Missing conversion clears the old waypoint without substituting ID types.
9. UI updates the tracker and refreshes the dashboard only when visible. Search is literal; settings and quest selection use ordinary addon frames. Choice warnings are advisory.

## Dependency semantics

The pinned `Database/QuestieDB.lua` defines the behavior used here: `preQuestSingle` takes precedence over `preQuestGroup`; positive group entries allow their source-declared exclusive equivalents; negative entries require that exact quest. `parentQuest` requires an active parent, while `availableStartingWith` permits an active or completed enabling quest. Breadcrumbs, next quests, maximum levels, skills, signed spells and reputation thresholds can close opportunities. Unknown references and cycles remain unresolved.

A source relationship does not prove live availability. Private Questie modules for professions, reputation, events and zone conversion are guarded. An absent module leads to unknown requirements or no waypoint. The addon never expands faction headers to obtain reputation data.

## Catalog versus historical guides

`runtime_catalog.py` builds character-neutral records from raw TBC rows plus common and per-context corrections. It audits every source row, retains legitimate unavailable/conditional content, records all five packaged phase decisions, and emits endpoints, objective facts, relationships and variants. It does not use historical guide inclusion as a coverage filter.

`catalog.py` explicitly requests the historical faction-replacement correction behavior to preserve the 171 existing guide/spec artifacts. New runtime records use field-wise correction composition. This historical replay path is not a live eligibility authority. `MadsTBC.RegisterLegacyGuide` forwards to a real installed Guidelime or stores registrations in the addon namespace; it never creates a fake global Guidelime.

Runtime data is generated into lowercase `data/`, matching the tracked directory and TOC exactly. The source archive used for this implementation carried Git commit `0ad1972cbd54f9aac0a5e202fec9ee6c818fbf44` in its tar PAX comment; the manifest and audit retain that provenance.

## Deliberate limits

The journey is an adaptive heuristic, not a globally optimal travel solver. Endpoint distance applies within a map; observed transport links do not establish every connection. Relative effort scores are not cross-map time estimates. The inherited walkthrough is not generalized to every character. English source instructions and observed client objectives provide the instruction layer where available. Current realm phase, live NPC presence, secure execution/taint behavior and exact-client performance still require client testing.

## Planning and travel — alpha.4

Planning derives a preference-independent forecast after eligibility and builds endpoint-aware departure checklists on demand. Consequence expansion uses eligibility's prerequisite groups, does not propagate past an intact any-of alternative, and preserves completed/active work. Cleanup is a saved journey mode; ordinary category, skip, log reserve, and prerequisite semantics still apply.

Travel adds normalized per-character `travel` memory without replacing schema-2 progress. Flight-map observations save directed CURRENT-to-REACHABLE links, discard DISTANT nodes, and only locate a flight master from a verified current player position. User-confirmed departure/arrival pairs add directed boat, portal, or road edges. The pending pair survives reloads. Malformed points and dangling links are removed during normalization.

Hearth coordinates are captured at binding or the first exact inn-subzone match, then kept stable. A changed bind invalidates the old location. Carried-item and cooldown evidence are required; only one timer per cooldown deadline is scheduled. Riding rank scales local ground effort, without assuming a flying mount. Dijkstra combines same-zone ground transfers with observed directed links and an optional ready-hearth start. The router uses finite travel effort after urgency, retained action, current zone, and active work. Navigation uses the first transport waypoint with checked AreaID-to-UiMapID conversion. Costs have arbitrary relative units, not seconds; boat schedules, fares, terrain, cave entrances, and mount ownership remain outside the model.

API reference checked against the exported [TBC Anniversary taxi UI](https://github.com/Gethe/wow-ui-source/blob/classic_anniversary/Interface/AddOns/Blizzard_UIPanels_Game/Classic/TaxiFrame.lua) and [taxi API declarations](https://github.com/Gethe/wow-ui-source/blob/classic_anniversary/Interface/AddOns/Blizzard_APIDocumentationGenerated/TaxiMapDocumentation.lua). Cooldown return conventions follow the pinned Questie `QuestieCompat.GetItemCooldown` adapter. This source review does not establish exact-client gameplay verification.

## Category selection and skip preferences

`Selection` is shared by routing and UI. It derives overlapping category facets from resolved records and caches them with weak record keys. `categoryPreferences` is an optional per-character map of category key to `include` or `exclude`; missing means Any. Invalid keys/states normalize away. It is separate from replaceable journey intent. The additive field retains SavedVariables schema 2; existing `deferred` boolean IDs remain the persistent skip store. `Skip`, `SkipCurrent`, `Restore`, and `RestoreAll` provide the routing interface; Defer aliases remain compatible.

Selection rebuilds derived membership, selected-category counts and preference checks on route refresh. It does not modify global eligibility or the compatible-outcome projection. Completed or satisfied active prerequisites need no new work; access to an active-parent/enabling quest is distinct from completing that quest's children. Permitted any-of alternatives are tried before a preference block is reported. Explicit goals can focus an allowed quest outside Includes, but never override Exclude or Skip. Required bridges are labeled and included in visible zone listings without inflating category totals.

Preference changes refresh route actions, waypoints and UI without scanning Blizzard or recomputing global choices. Skip applies to the entire quest, including active and turn-in-ready states. The Skipped management filter bypasses category and zone restrictions; restoring a skip does not change category preferences.
