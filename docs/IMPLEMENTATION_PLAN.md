# Combined private-addon implementation plan

Goal: log in and follow one dynamically updated quest journey, tracking every available quest and preserving unfinished work. Scope: both factions and all supported TBC Anniversary race/class combinations, levels 1–70, per-character progress. Public distribution is not intended.

| Work | Implementation | Validation |
|---|---|---|
| Preserve real progress and resume | Schema-2 normalization; valid-snapshot barrier; explicit turn-in evidence; route-position migration as hints | Malformed settings, delayed log rows, callback ordering, reload and coalescing tests |
| Build both-faction coverage | Independent source-row catalog, common/context corrections, phase arrays, endpoints/objectives, audit decisions | Full catalog loading across 104 supported race/class/level profiles; source integration and audit consistency |
| Make totals meaningful | Completionist faction-wide view; compatible Achievable projection; recurring IDs counted once; provisional unknown totals | Exclusive descendants, equivalents, observed conflicts, recurring reset tests |
| Make the journey progress | Dependency-aware accept/objective/turn-in actions; active parent/child work; stable resume; missable priority; log reserve | Goal expansion, parent lifecycle, objective transitions, catch-up, deferred restoration tests |
| Explain and inspect work | Searchable/filterable quests, zone views, reasons/blocker chains, recurring history, source instructions, advisory choices | UI doubles exercise initialization, pages and selection; visual checks remain manual |
| Navigate conservatively | Endpoint selection and same-map distance; checked map conversion; owned waypoint deduplication/cleanup; travel hints | Missing adapters, repeated destination, empty route and map-type tests |
| Preserve interoperability | Guarded Questie adapters; optional TomTom/Guidelime; no fake dependency global; no automated quest actions | Dependency-absence and registration tests; client taint/combat checks remain manual |
| Keep validation reproducible | Lua behavior suite independent of Questie fixture; case-sensitive TOC checks; static versus installed-environment checks | See validation ledger and recorded command results |

Order for further verification: installed-client login and migration, faction/class starting zones, parent/choice/recurring chains, delayed data and phase/event updates, UI/waypoint behavior in combat, then practical travel and longer play sessions.

This plan does not redefine unknown source facts as completed work. Live realm phase, historical recurring completions, uncatalogued quest availability, full localization, comprehensive transport routing and client verification remain explicit limitations. `REMEDIATION_PLAN.md` retains the older guide-pack audit history.

## Category and skip extension — alpha.3

Implemented shared overlapping category rules with Any/Include/Exclude, per-character persistence, dashboard and journey filtering, selected-category subtotals, labeled prerequisite bridges and explicit preference-block reasons. Exclusions always win; allowed alternative prerequisites are considered. Skip replaces Defer in the UI and keeps the same persistent IDs. Skipped management, individual restore, Restore and guide, and restore-all never fabricate completion or reset category exclusions.

The existing global completion scores, client target, phase profile, catalog and completion evidence remain independent of these preferences. Automated behavior and full-catalog profile tests cover the extension. Live UI, combat and reload checks remain part of the manual checklist.

## Departure, forecast, and travel extension — alpha.4

Implemented endpoint-aware zone departure lists and saved cleanup routing; proactive cutoff/choice forecasts with dependency consequences; per-character directed flight/transport memory, confirmed hearth location and cooldown handling, riding-aware relative effort, and first-stop navigation. Dashboard and slash-command access are included. Automated regression cases cover data readiness, preferences, missing APIs, saved-state normalization, cutoff semantics, directed connectivity, and UI callbacks. Client verification remains the outstanding release gate.
