# Contributing

## Where to start

- **Writing a new sensor adapter or finishing an existing scaffold?** Read
  [docs/plugin-development.md](docs/plugin-development.md) first — it's the full
  contract plus a tour of real reference implementations. The
  ["Adapters that need your help"](docs/plugin-development.md#adapters-that-need-your-help)
  section links to four open issues (Growlink, Argus, Pulse Grow, Priva) where a real
  vendor account or device is the only thing standing between a scaffold and a
  finished adapter.
- Anything else with a
  [`help wanted`](https://github.com/hashking710/Canopy/labels/help%20wanted) label is
  fair game and doesn't need to be claimed in advance — just open a PR.
- Found a bug or want to propose something bigger? Open an issue first for anything
  that isn't an obvious, contained fix — saves you writing a PR against an approach
  that turns out not to fit.

## This project's honesty standard for hardware/vendor integrations

Every adapter and compliance-sync plugin in this repo draws a hard line between what's
*confirmed* (read directly from a vendor's own official docs, datasheet, or a real
account) and what's *not yet confirmed*. Confirmed parts get real implementations.
Anything unconfirmed raises `NotImplementedError` with a specific, sourced explanation
of what's missing — never a guessed request shape presented as working. Each plugin's
module docstring states this split explicitly; keep that pattern in any PR that touches
one.

## Before opening a PR

- **Tests.** `edge-agent/.venv/Scripts/python.exe -m pytest -q` for the core app; each
  plugin package has its own test suite runnable the same way from `plugins/<name>/`.
  Frontend changes: `npx tsc -b && npx vitest run` from `frontend/`. New behavior needs
  a new test, not just a passing existing suite.
- **Scope.** Keep PRs to one adapter, one bug, or one focused change — easier to review
  and easier to revert if something's wrong.
- **No secrets.** Never commit a real API key, token, or `.env` file, even a test/throwaway
  one used to verify an integration locally.

## Local dev

See the main [README](README.md#running-locally) for getting the full stack running.
