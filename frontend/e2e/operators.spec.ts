import { expect, test } from "@playwright/test";

test("adding an operator, resetting their PIN, and deactivating them all round-trip", async ({ page }) => {
  const name = `E2E Operator ${Date.now()}`;

  await page.goto("/compliance", { waitUntil: "networkidle" });

  await page.getByText("+ add operator").click();
  await page.getByPlaceholder("name").fill(name);
  await page.getByPlaceholder("PIN (optional)").fill("1234");
  await page.getByRole("button", { name: "save" }).click();

  const picker = page.locator(".operator-picker select");
  await expect(picker.locator("option", { hasText: name })).toHaveCount(1);
  await picker.selectOption({ label: `${name} (PIN)` });

  await page.getByRole("button", { name: "manage" }).click();
  await page.getByRole("button", { name: "reset PIN" }).click();
  await page.getByPlaceholder("new PIN (blank to remove)").fill("5678");
  await page.getByRole("button", { name: "save" }).click();
  // resetting the PIN returns to the manage panel (reset PIN / deactivate / done),
  // not back out to the closed "manage" button — no need to re-open it.
  await expect(page.getByRole("button", { name: "deactivate" })).toBeVisible();

  await page.getByRole("button", { name: "deactivate" }).click();
  await expect(page.getByText(new RegExp(`Deactivate ${name}\\?`))).toBeVisible();
  await page.getByRole("button", { name: "confirm deactivate" }).click();

  await expect(picker.locator("option", { hasText: name })).toHaveCount(0);
});
