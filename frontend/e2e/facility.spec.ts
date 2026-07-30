import { expect, test } from "@playwright/test";

test.describe("Facility overview", () => {
  test("loads with real room cards and no console errors", async ({ page }) => {
    const consoleErrors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") consoleErrors.push(msg.text());
    });

    await page.goto("/", { waitUntil: "networkidle" });

    await expect(page.locator(".room-grid .link-card").first()).toBeVisible();
    expect(consoleErrors).toEqual([]);
  });

  test("adding a room makes it appear on the overview immediately", async ({ page }) => {
    // Title (not just id) carries the timestamp too — repeated runs otherwise leave
    // same-titled rooms behind, and a plain getByText match would collide with them.
    const suffix = Date.now();
    const roomId = `e2e-room-${suffix}`;
    const roomTitle = `E2E Test Room ${suffix}`;

    await page.goto("/", { waitUntil: "networkidle" });
    await page.getByText("+ add room").click();
    await page.getByPlaceholder("e.g. greenhouse-c").fill(roomId);
    await page.getByPlaceholder("strain / room name").fill(roomTitle);
    await page.getByRole("button", { name: "create room" }).click();

    await expect(page.getByText(roomTitle)).toBeVisible();
  });
});
