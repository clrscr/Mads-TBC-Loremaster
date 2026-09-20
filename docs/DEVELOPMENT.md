# Development and WowUp releases

The working checkout is connected to `https://github.com/clrscr/Mads-TBC-Loremaster`. The README is intentionally brief; usage details are in [USAGE.md](USAGE.md).

Push changes to `main` to run the GitHub Actions validation and package workflow. It uses the pinned Questie revision, Python 3.12, and stock Lua 5.1. The workflow publishes a downloadable Actions artifact on successful builds. Branch pushes do not update WowUp.

The Questie source revision pins **build inputs and bundled-data provenance only**. Installed Questie can update normally: there is no required release number or database hash match. Installation checks verify presence and the target interface declaration, recording the observed version for diagnostics. Runtime adapters check the capabilities they use; if Questie changes those APIs, update this addon's adapters. Refreshing bundled quest facts is a separate regeneration and review step.

To ship an update:

1. Update the version consistently in `config/release.json`, `Mads_TBCLoremaster.toc`, `Runtime/Core.lua`, `pyproject.toml`, and the current usage/results documentation. Keep development builds on the alpha channel until the client checklist is complete.
2. Update `docs/RELEASE_NOTES.md` for that version and run the tests and validator described in USAGE.md.
3. Commit and push the changes to `main`.
4. Create and push the matching version tag, for example `git tag v1.0.0-alpha.5` followed by `git push origin v1.0.0-alpha.5`.

The tag workflow verifies that the tag matches the configured version, runs checks, builds the addon ZIP, and uses `gh release create` to publish it with `release.json` metadata. Alpha/beta builds become GitHub prereleases. It uses GitHub's built-in workflow token; no personal token needs to be stored in this repository.

WowUp reads the GitHub repository's tagged release assets. `Mads_TBCLoremaster-<version>-bcc.zip` contains the `Mads_TBCLoremaster` folder at its root. The separate `release.json` identifies the ZIP as flavor `bcc` and interface `20506`, which WowUp maps to the Anniversary client. Keep Questie installed independently. Use the repository URL in WowUp's Install from URL dialog to retain update tracking; a standalone ZIP URL does not provide the same tracking.

The public repository is for personal use. `public_release_ready: false` records that gameplay verification is still outstanding; it does not mean the repository must be private. See [IN_GAME_SMOKE_TEST.md](IN_GAME_SMOKE_TEST.md) before treating a build as stable.
