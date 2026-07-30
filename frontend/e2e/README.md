# End-to-end tests

Drives the real app in a real browser — not dev servers, the same containers the
Docker Compose stack serves. These specs assume `edge-agent` + `frontend` are already
up and reachable at `localhost:8000` / `localhost:5173`.

```
docker compose up -d --build edge-agent frontend
npm run e2e
```

Specs share one running facility/database rather than each getting a fresh one, so
they avoid depending on exact pre-existing data where possible (creating their own
rooms/harvests/rules with unique, timestamped names) and skip themselves gracefully
when a precondition genuinely isn't there (e.g. no untracked plants to tag right now).

`fullyParallel` is off in `playwright.config.ts` for this reason — specs mutate shared
state (one facility, one SQLite DB), so running them concurrently would make them
interfere with each other.

## `accessibility.spec.ts`

Runs axe-core (`@axe-core/playwright`) against every page in both light and dark
theme, plus a scripted keyboard-only walkthrough and an explicit check that the theme
toggle works via keyboard. This is the strongest automated approximation available
here — it catches a real, wide slice of WCAG 2 A/AA issues (missing labels, contrast,
ARIA misuse, unreachable scrollable regions) — but it is not a substitute for an
actual screen-reader pass (NVDA/JAWS/VoiceOver) before a real release; axe cannot
verify that a screen reader announces something *sensibly*, only that the markup
isn't structurally broken.
