# Unreleased fixes

- Questie may update independently: installation validation no longer requires an exact Questie version or database hash match. Observed versions remain diagnostic information; runtime capability checks handle API availability. The bundled catalog retains reproducible source provenance.
- Added a Journey view in route order and a Quest log view that retains skipped, excluded and newly discovered held quests. Catalog remains available for broader completion review.
- Quest rows now show status and zone, current/selected cues, full-title hover text, pagination counts, and actionable empty states. Active client titles are searchable.
- The bounded, scrollable tracker shows objective progress, the next distinct route quest, and a Details shortcut. Quest details expose source destinations, prerequisite alternatives and related next quests without claiming unknown availability.
- Objective snapshots are copied so reused client tables cannot conceal progress changes. World entry retries character scanning; legacy TBC failure evidence is matched by quest ID.
- Profession rank gates now use Questie's trained-rank checks. Learning to Fly remains available with Journeyman Riding until a flying rank is learned.
- Parent quest guidance selects a compatible child path; skipping an alternative no longer blocks a permitted path.
- Generated quest destinations include common TBC NPC and object name/location corrections, including Rokaro in Desolace.
- Objective navigation distinguishes overlapping creature names and leaves ambiguous targets without a waypoint.
- The Categories window stops moving when its drag ends.

Existing progress and preferences are preserved. In-game verification of these fixes is pending.

# 1.0.0-alpha.5

The mini tracker can now be hidden without opening Settings, and restored from the minimap.

- Click the tracker's top-right **X** to hide it. It stays hidden across reloads and logins while quest tracking continues.
- Left-click the book-shaped Loremaster minimap button to show/hide the tracker; right-click to toggle the dashboard.
- Drag the minimap button to reposition it; its location is saved using the minimap library already supplied by Questie.
- Use `/mtl show`, `/mtl hide`, or `/mtl toggle` as keyboard alternatives. The Settings toggle also remains available.

Requires Questie; targets TBC Anniversary interface 20506. This remains a development release with in-game verification pending. Existing quest progress and routing preferences are preserved.

Validation: 39 Python tests, including 77 Lua behavior cases and 104 character/level profiles. See the usage and client-checklist documents inside the addon package.

Update from `https://github.com/clrscr/Mads-TBC-Loremaster` in WowUp. Use the Beta/Alpha channel for development updates if needed; WowUp's GitHub provider classifies GitHub prereleases as Beta.
