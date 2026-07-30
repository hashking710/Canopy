import { expect, test } from "@playwright/test";

// Regression coverage for a real bug found and fixed this session: RoomDetail had no
// top navigation at all, so the single most-visited page in the app was a dead end —
// the only way anywhere else was back to the facility overview first.
test("room detail page has working top navigation to every other section", async ({ page }) => {
  await page.goto("/", { waitUntil: "networkidle" });
  await page.locator(".room-grid .link-card").first().click();
  await expect(page).toHaveURL(/\/rooms\//);

  await page.getByRole("link", { name: "Compliance" }).click();
  await expect(page).toHaveURL(/\/compliance/);

  await page.getByRole("link", { name: "Alerts" }).click();
  await expect(page).toHaveURL(/\/alerts/);
});

test("deleting a room requires confirmation and can be cancelled", async ({ page }) => {
  await page.goto("/", { waitUntil: "networkidle" });
  await page.locator(".room-grid .link-card").first().click();

  page.once("dialog", (dialog) => dialog.dismiss());
  await page.getByRole("button", { name: "delete room" }).click();

  // dismissing the confirm must leave the room page intact, not navigate away
  await expect(page).toHaveURL(/\/rooms\//);
  await expect(page.getByRole("button", { name: "delete room" })).toBeVisible();
});
