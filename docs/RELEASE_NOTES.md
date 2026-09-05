# 1.0.0-alpha.4

Adds a zone departure checklist with cleanup guidance, a proactive missable-quest forecast with dependent-quest consequences, and character-aware travel planning.

- Open `/mtl leave`, `/mtl missable`, or `/mtl travel`, or use the dashboard buttons.
- Flight maps teach directed flight connections. Hearth planning requires a mapped bind, a carried Hearthstone, and available cooldown data. Riding rank affects relative ground effort.
- Record reusable boat/zeppelin, portal, and road connections with the departure/arrival buttons. TomTom can guide you to the first transport stop.
- Existing quest progress, category preferences, and skipped quests are preserved.

Requires Questie. Targets TBC Classic Anniversary interface 20506; TomTom and Guidelime are optional. This is a development release: automated checks pass, but this build has not yet been tested inside WoW. The packaged phase profile is historical; use the correct phase override for your realm.

Validation: 39 Python tests, including 74 Lua behavior cases and 104 character/level profiles; all 184 loaded Lua files compiled; static validation passed. See [usage](USAGE.md) and [development](DEVELOPMENT.md) documentation for details.

In WowUp, select your TBC Anniversary client, choose **Get Addons → Install from URL**, and enter `https://github.com/clrscr/Mads-TBC-Loremaster`. The GitHub release includes a packaged addon ZIP and TBC metadata. Use the Beta/Alpha channel for development updates if needed; WowUp's GitHub provider classifies GitHub prereleases as Beta.
