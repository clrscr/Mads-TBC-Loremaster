# Personal-use alpha.5 client verification

**Not executed for this implementation.** Record client build/interface, realm/region/phase, character faction/race/class/level, Questie version, optional addon versions and results in `IN_GAME_RESULTS.md`. Interface 20506 and Questie 11.32.1 are the pinned evidence baseline, not a claim that they are the newest versions.

1. Back up this addon's SavedVariables with the client closed. Start with no saved settings, then separately try the previous alpha's settings. Login should wait for reliable data, automatically choose a useful action, and retain genuine progress. Reload while following an objective and confirm it resumes.
2. Try representative Alliance and Horde starts, including Draenei and Blood Elf, a level-70 cleanup character, and race/class-specific quests. Other-faction records must not enter the faction score; other race/class records should remain in Completionist but not falsely enter Achievable.
3. Accept a quest, advance each objective, complete it and turn it in. Confirm action, totals, quest detail and waypoint update once without manual rescan. Try an empty and a 23-slot log; preserve the two-slot pickup reserve.
4. Follow a parent quest with active child quests. Children should become the actionable work while the parent remains logged. Test all-of, any-of, exact negative and equivalent prerequisite groups using known chains.
5. Inspect a mutually exclusive branch before accepting it. Check advisory names, compatible totals, the selected branch's descendants, and changes after accepting/abandoning/turning in. The addon must never choose or accept on your behalf.
6. Complete a recurring quest, reload, and revisit after its reset/event return. Its first completion should remain counted once. Select it explicitly for another run. Do not infer pre-installation history the client does not report.
7. Skip a dungeon, raid or PvP quest and a prerequisite. Unfinished totals must remain; the journey should continue elsewhere. Restore selected/all skipped quests and verify they return.
8. Learn/increase a profession, including a secondary skill after empty primary slots; change reputation across a gate. Verify reasons and Achievable totals. Watch for changes that close an opportunity.
9. Compare packaged and manually selected phase decisions against the realm. Check an inactive event and delayed calendar data. Unknown data must not appear as proven permanent loss. Recheck after event data arrives.
10. Test with/without TomTom and Guidelime. Only the addon-owned waypoint should be replaced or cleared. A missing map conversion must not create a waypoint on an unrelated map. The legacy chapters should register only with the real Guidelime.
11. Open, close, drag, search, page and scroll the dashboard; inspect long names and source text at your UI scale. Test tracker detail levels and reset positions. Repeat in combat, with default quest UI, Questie tracker, menus and other usual addons open. Enable Lua errors and inspect taint logs for attributable failures.
12. Play a real local quest loop, then a zone/continent transition. Check whether source destinations and travel hints help. Record missing cave entrances, wrong NPC positions, inaccessible services and unnecessary travel as data/route issues; do not treat static coordinates as verified paths.
13. Observe unrecognized quests and temporary API delays/loading screens. They should remain visible with unknown source details, and a failed scan must preserve the previous journey. `/mtl scan` should recover after data becomes available.

No live-result claim should be inferred from the stock Lua harness or historical installation evidence.

## Tracker visibility and minimap launcher — alpha.5

- Close the tracker with its X. Complete or update a quest, change zones, reload, and log out/in: it should stay hidden while progress continues updating.
- Left-click the Loremaster book minimap icon to restore/hide the tracker. Right-click it to toggle the dashboard without changing tracker visibility.
- Drag the icon around the minimap, then reload. Check that its position persists and it works with your minimap customization addons.
- Try `/mtl hide`, `/mtl show`, `/mtl toggle`, and the Settings tracker toggle, including in combat. Verify hiding the tracker does not skip quests or change routing preferences.
- Check the close button and tracker title at your normal UI scale. Confirm the minimap tooltip explains both clicks.

## Category and skip extension

- Include Dungeon; verify allowed world prerequisites carry their target quest name in dashboard and tracker. Inspect a bridge in another zone and on the Recurring tab.
- Include both Dungeon and Profession, then Exclude Profession. Check an overlapping quest (such as 5306, where eligible); it must respect the exclusion. Try all categories excluded and verify the empty-route explanation and waypoint cleanup.
- Skip available, active, turn-in-ready and recurring quests. Reload and change journey modes: each stays skipped and unfinished until restored. Complete a skipped quest manually and verify only actual completion evidence updates the score.
- Use Skipped management while filtering categories/zones. Restore a category-excluded quest: its skip clears, but it stays out of the route until the exclusion is changed. Reset categories and restore-all independently.
- Verify overall totals stay stable, overlapping categories count once, prerequisite-only additions do not inflate the subtotal, and search/pagination do not redefine it.
- Inspect the enlarged dashboard and category panel at your UI scale, including selected button states, long preference text, escape/close behavior and combat.

These checks have not been executed in WoW for alpha.4.

## Departure, forecast, and travel extension

- Open `/mtl leave` before and after selecting a dashboard zone. Use Current zone, search, pagination, details, and Guide zone cleanup. Compare local starters/finishers to the map, including quests cataloged in another zone. Confirm skipped/excluded work remains visible and never enters cleanup guidance.
- Open `/mtl missable`. Inspect a near-level cutoff, breadcrumb, mutually exclusive choice, and active parent/child chain. Check preservation advice and dependent quests. Complete a prerequisite alternative and confirm it prevents a false dependent-loss warning. Confirm skipped/filtered risks stay visible.
- Open `/mtl travel` and a flight master's map. Check learned stops and connections. Visit another known master to establish both endpoints; confirm a useful flight suggestion and the first-stop TomTom waypoint. Observe no automatic flight purchase. Repeat with no TomTom and with missing map data.
- Bind at an inn, move away, and verify the recorded location stays fixed. Check ready, cooling-down, absent-item, and changed-bind states. Wait for cooldown expiry and verify guidance refreshes. Reload with a known bind. Confirm no automatic hearth use.
- Record a boat/zeppelin, portal, and road departure/arrival. Try arrival before traveling, cancel a departure, and reload during a pending recording. Confirm only the traveled direction is available and a return link requires its own recording.
- Check riding-rank changes, cross-zone routing, and unknown transport endpoints. A riding skill must not generate an invented flight connection. Treat travel scores as approximate effort, not a promised time saving.
- Inspect all three planner views, long quest names, long route descriptions, scroll areas, and footer buttons at your normal UI scale, including combat and Escape/close behavior.
