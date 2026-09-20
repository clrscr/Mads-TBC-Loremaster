# wow-addon-dev installation review

Installed on 2026-09-20 from
[TheMizeGuy/wow-addon-dev](https://github.com/TheMizeGuy/wow-addon-dev),
revision [`f928572a9428d29327a96c2549b0068101961c4e`](https://github.com/TheMizeGuy/wow-addon-dev/tree/f928572a9428d29327a96c2549b0068101961c4e).

The unmodified upstream package, including its MIT license, lives in
`.agents/skills/wow-addon-dev/`. This is a
[Codex project-local skill location](https://learn.chatgpt.com/docs/build-skills#where-codex-loads-local-skills).
Invoke it with `$wow-addon-dev`, or let Codex select it for matching addon tasks.
If it does not appear after installation, restart Codex.

## Review findings

The entry point, seven PowerShell utilities, package layout, and selected references
were inspected statically. No network download or dynamic execution commands were
found in the utility scripts. This was not an exhaustive verification of the WoW API
guidance or an in-game test.

- **Platform mismatch:** `install-addon.ps1` and `package-addon.ps1` call
  `robocopy.exe`; installing PowerShell alone does not make them work on macOS.
  The client-version scripts also inspect Windows executables.
- **Destructive installation order:** `install-addon.ps1` deletes an existing
  destination after overwrite confirmation (or with `-Force`) before invoking
  the copy utility. A missing or failing utility can leave the addon absent.
- **Interface updater defects:** `set-interface-version.ps1` replaces the entire
  `## Interface:` value despite claiming to preserve comma-separated lists.
  Its auto mode maps `_TBC` to `classic_era` and defaults an unsuffixed TOC to Retail.
  Do not use it for this project's TBC Anniversary TOC.
- **Edition assumptions:** the skill emphasizes Retail/Midnight;
  `list-installed-addons.ps1` searches Mainline/Standard TOCs even when given a
  Classic edition. Verify edition-specific information before applying it here.

Use the existing project validation and packaging commands documented in
[DEVELOPMENT.md](DEVELOPMENT.md). The project's `build_zip` function explicitly
selects release files, so this skill and its example addons are not included in
release archives. `AGENTS.md` records the project-specific usage guidance.

## Verification and updates

Installation used the bundled skill-installer with the full revision above,
`--path . --name wow-addon-dev`, and this project's `.agents/skills` destination.
The installed files were compared byte-for-byte against the reviewed checkout;
the skill metadata and referenced local resources were checked.
PowerShell is not installed here, so the utilities were not executed.

For updates, review the new upstream revision and utilities before replacing this
copy. Preserve the upstream license and update the recorded revision and findings.
