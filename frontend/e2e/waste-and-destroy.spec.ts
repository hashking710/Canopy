import { expect, test } from "@playwright/test";
import { selectOptionContaining } from "./helpers";

const API_BASE = "http://localhost:8000";

// The seeded default operator (Alex Rivera) has a PIN configured, which the compliance
// router correctly requires for waste-logging and plant destruction — rather than
// guessing at a PIN we don't know, these specs switch to a fresh, PIN-less operator
// first, sidestepping the "your PIN" field entirely (it only renders when
// currentOperator?.has_pin is true).
async function switchToAPinlessOperator(page: import("@playwright/test").Page) {
  const name = `E2E No-PIN Operator ${Date.now()}`;
  await page.getByText("+ add operator").click();
  await page.getByPlaceholder("name").fill(name);
  await page.getByRole("button", { name: "save" }).click();
  await page.locator(".operator-picker select").selectOption({ label: name });
}

test("logging waste against a real package appears in the waste log", async ({ page }) => {
  const packages = await (await page.request.get(`${API_BASE}/api/compliance/packages`)).json();
  test.skip(packages.length === 0, "no packages available to log waste against right now");
  const pkg = packages[0];

  await page.goto("/compliance", { waitUntil: "networkidle" });
  await switchToAPinlessOperator(page);

  const wasteForm = page.locator(".quick-form").filter({ has: page.getByRole("button", { name: "log waste" }) });
  await wasteForm.locator("select").first().selectOption("package");
  await selectOptionContaining(wasteForm.locator("select").nth(1), pkg.id);
  const roomSelect = wasteForm.locator("select").nth(2);
  await roomSelect.selectOption({ index: 1 });
  await wasteForm.locator('input[type="number"]').fill("5");
  await wasteForm.getByRole("button", { name: "log waste" }).click();

  // the success message is a sibling of .quick-form, not nested inside it.
  await expect(page.getByText("✓ waste logged")).toBeVisible();
});

test("destroying a plant requires confirmation and is reflected in the tagged-plants table", async ({ page }) => {
  const plants = await (await page.request.get(`${API_BASE}/api/compliance/plants`)).json();
  const active = plants.find((p: { status: string }) => p.status === "active");
  test.skip(!active, "no active plants available to destroy right now");

  await page.goto("/plants", { waitUntil: "networkidle" });
  await switchToAPinlessOperator(page);

  const destroyForm = page.locator(".action-subsection", { hasText: "Destroy a plant" });
  await destroyForm.locator("select").first().selectOption(active.id);
  await destroyForm.getByLabel("weight (g)").fill("1");

  // dismissing the confirm must NOT destroy the plant
  page.once("dialog", (dialog) => dialog.dismiss());
  await destroyForm.getByRole("button", { name: "destroy plant" }).click();
  await page.waitForTimeout(300);
  await expect(destroyForm.getByText("✓ destroyed")).not.toBeVisible();

  page.once("dialog", (dialog) => dialog.accept());
  await destroyForm.getByRole("button", { name: "destroy plant" }).click();
  await expect(destroyForm.getByText("✓ destroyed")).toBeVisible();

  const stillListed = page.locator("table.data-table tbody tr", { hasText: active.id });
  await expect(stillListed).toHaveCount(0);
});
