import { defineConfig } from "@playwright/test";

// Runs against the SAME edge-agent + frontend the Docker Compose stack serves, not a
// separate dev-server-only harness — that's the actual deployed shape (a Vite dev
// server never runs in production), and it's the exact way this project's UI changes
// have been verified by hand throughout development: rebuild the containers, then
// drive the real app. `docker compose up -d --build edge-agent frontend` must already
// be running (see e2e/README.md) — CI brings it up itself; see .github/workflows/ci.yml.
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false, // shared backend state (one facility, one SQLite DB) — specs must not race each other
  workers: 1, // fullyParallel only serializes within a file; this also serializes across files
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["github"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: "http://localhost:5173",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { browserName: "chromium" } }],
});
