# Mad's TBC Loremaster

Mad's TBC Loremaster is a phase-aware Alliance quest-completion addon for Burning Crusade Classic Anniversary. It scans the current character, explains what is completed, recoverable, blocked, recurring, or permanently locked, and builds a route from the character's real state.

This repository began as a Night Elf Hunter Guidelime guide pack. The original 171 reviewed chapters and Questie-backed audit pipeline remain included, but the `1.0.0-alpha.1` product adds an original standalone runtime and no longer requires Guidelime.

> Status: **development alpha**. Static generation and validation pass. Public release remains blocked on the all-Alliance authored review, Guidelime attribution permission for the proposed “Powered by Guidelime” branding, and the standalone in-game verification matrix.

## What the addon does

On first launch, the addon scans Blizzard's completed-quest state, the active quest log, race, class, level, professions, and reputations. It then offers three routes:

- **Continue Journey** chooses a coherent level-appropriate zone sweep.
- **Catch Up on What You Missed** builds zone-by-zone cleanup for recoverable quests below the character's current level. Gray and overleveled quests remain eligible.
- **Get Back on Track** selects a suitable progressive frontier and includes the missing prerequisite bridge needed to reach it.

The dashboard tracks one stable permanent-completion score and a separate recurring/event activity score. Mutually exclusive outcomes that a character can no longer obtain remain visible but do not make 100% impossible. Dungeon, raid, elite, and PvP stops can be pursued or deferred without being marked complete.

Quest progress is per character. Account-wide SavedVariables contain display settings only.

## User experience

- The dashboard shows permanent completion, recurring activity, blockers, locked alternatives, and completion by canonical zone.
- A compact tracker shows the current action, quest state, waypoint, route mode, and zone.
- The tracker uses progressive disclosure: **Minimal**, **Route**, **Arc**, or **Deep Lore**. The alpha includes original story summaries for the major opening and Outland arcs plus safe fallbacks for every other zone.
- Quest choices that conflict with another outcome produce a warning before acceptance.
- Questie supplies live quest-update callbacks and continues to provide its normal map ecosystem.
- TomTom receives the active waypoint when installed. Without TomTom, the dashboard and coordinate guidance continue to work.
- Existing Guidelime users can still load the generated Guidelime-format chapters through the compatibility bridge.

Slash commands:

```text
/mtl                 Toggle the dashboard
/mtl scan            Rescan the current character
/mtl continue        Start Continue Journey
/mtl catchup         Start Catch Up on What You Missed
/mtl track           Start Get Back on Track
```

## Install the alpha

1. Build or unzip the `Mads_TBCLoremaster` package into the Anniversary client's `Interface/AddOns` directory.
2. Install and enable Questie. It is the sole required external addon.
3. Optionally install TomTom and/or Guidelime.
4. Enable **Mad's TBC Loremaster**, log into an Alliance character, and use `/mtl`.

The TOC targets interface `20506`. Horde characters are intentionally classified as outside the v1 product scope.

## Runtime data model

Questie is a build-time source for the compact character-neutral manifest. The generated addon currently exposes 4,269 Alliance-visible pre-Cataclysm quest records, including race/class alternatives, professions, repeatables, events, future-phase entries, exclusions needed to explain blockers, prerequisites, exclusivity, endpoints, and verified coordinates.

At runtime:

- Blizzard's completed-quest table is authoritative for permanent completion.
- Questie’s public readiness and quest-update callbacks trigger incremental rescans.
- Phase manifests determine whether future quests enter the achievable set; Settings provides a bounded manual phase override.
- Each quest has one canonical zone for scoring, even when its objectives cross zone boundaries.
- Generated facts are never treated as proof of live NPC availability; in-game testing remains mandatory.

## Rebuild and validate

Python 3.10 or newer is required. There are no third-party Python dependencies. Supply an unpacked Questie addon or checkout containing `Database/TBC/tbcQuestDB.lua`:

```sh
./mads-loremaster catalog /path/to/Questie
./mads-loremaster generate /path/to/Questie
./mads-loremaster validate /path/to/Questie
./mads-loremaster audit /path/to/Questie
./mads-loremaster package /path/to/Questie
```

Run the reproducible pipeline with:

```sh
./mads-loremaster all /path/to/Questie
pytest -q
```

The validator checks the standalone runtime contract and TOC order, manifest expansion beyond the legacy character scope, phase and provenance boundaries, guide syntax, route semantics, coverage, quest-log capacity, source quality, package inputs, and legacy resume simulations.

## Source and licensing

The standalone runtime and generated routing are original MIT-licensed work. Questie remains a separately installed dependency under its own terms; its full database is not redistributed.

No Guidelime engine source is currently copied into this repository. The compatibility layer accepts the generated guide registration format and defers to a separately installed Guidelime when present. Public use of the proposed **Powered by Guidelime** subtitle remains an attribution/permission release gate rather than a code dependency.
