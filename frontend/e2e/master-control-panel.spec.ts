import { expect, test } from "@playwright/test";

// Requires the multi-site profile (mosquitto + master) to actually be running —
// `docker compose --profile multi-site up -d mosquitto master` — since this is an
// opt-in mesh, not part of the default single-site stack. Skips itself if master
// genuinely isn't reachable, mirroring the same "isn't part of a multi-site setup"
// case the page itself already handles gracefully.
test("the master control panel shows sites and the cross-device audit trail", async ({ page }) => {
  const masterReachable = await fetch("http://localhost:9100/api/health").then((r) => r.ok).catch(() => false);
  test.skip(!masterReachable, "master isn't running (multi-site profile not up) — see this spec's own comment");

  await page.goto("/master", { waitUntil: "networkidle" });

  await expect(page.getByText("Sites reporting in over MQTT")).toBeVisible();
  await expect(page.getByText("Audit trail (all sites)")).toBeVisible();
  // Either real content or the honest "nothing yet" explainer — never a blank gap.
  await expect(
    page.getByText(/rooms/).or(page.getByText("No sites have reported in yet")),
  ).toBeVisible();
});
