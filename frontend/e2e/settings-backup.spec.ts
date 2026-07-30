import { expect, test } from "@playwright/test";

test("triggering a backup updates the status card with a fresh timestamp", async ({ page }) => {
  await page.goto("/settings", { waitUntil: "networkidle" });

  await page.getByRole("button", { name: "back up now" }).click();
  await expect(page.getByText(/Last backup:/)).toBeVisible({ timeout: 15000 });
  await expect(page.getByText(/\d+ kept/)).toBeVisible();
});
