# 1.0.0-alpha.5

The mini tracker can now be hidden without opening Settings, and restored from the minimap.

- Click the tracker's top-right **X** to hide it. It stays hidden across reloads and logins while quest tracking continues.
- Left-click the book-shaped Loremaster minimap button to show/hide the tracker; right-click to toggle the dashboard.
- Drag the minimap button to reposition it; its location is saved using the minimap library already supplied by Questie.
- Use `/mtl show`, `/mtl hide`, or `/mtl toggle` as keyboard alternatives. The Settings toggle also remains available.

Requires Questie; targets TBC Anniversary interface 20506. This remains a development release with in-game verification pending. Existing quest progress and routing preferences are preserved.

Validation: 39 Python tests, including 77 Lua behavior cases and 104 character/level profiles. See the usage and client-checklist documents inside the addon package.

Update from `https://github.com/clrscr/Mads-TBC-Loremaster` in WowUp. Use the Beta/Alpha channel for development updates if needed; WowUp's GitHub provider classifies GitHub prereleases as Beta.
