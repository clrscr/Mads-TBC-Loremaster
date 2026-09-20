# Project guidance

For WoW addon development, use the project-local
[wow-addon-dev skill](.agents/skills/wow-addon-dev/SKILL.md).
Read [the installation review](docs/WOW_ADDON_DEV_SKILL.md) before using its utilities.

- This addon targets **TBC Anniversary**, not Retail. Use the project's TOC,
  `config/client_installation.json`, and verified target-client API information;
  do not apply the skill's Retail/Midnight defaults to this project.
- Preserve the existing architecture and use the validation and packaging workflow
  in `docs/DEVELOPMENT.md` and `./mads-loremaster`.
- The upstream install/package utilities depend on Windows `robocopy.exe`.
  Use the project's tools on macOS. Do not use the upstream interface updater:
  it replaces multi-version lists and its automatic TBC mapping is unsuitable here.
- Treat upstream API examples and interface numbers as reference material that
  needs verification against the target client.
