import { expect, test } from "@playwright/test";
import { selectOptionContaining } from "./helpers";

test("changing the compliance jurisdiction updates the retail rules shown", async ({ page }) => {
  await page.goto("/compliance", { waitUntil: "networkidle" });

  const jurisdictionForm = page.locator(".action-subsection").filter({ has: page.getByText("set jurisdiction") });
  await jurisdictionForm.locator("select").selectOption({ label: "Colorado" });
  await jurisdictionForm.getByRole("button", { name: "set jurisdiction" }).click();
  await expect(jurisdictionForm.getByText("✓ jurisdiction updated")).toBeVisible();

  await expect(page.getByText("Retail/dispensary rules for Colorado")).toBeVisible();
});

test("the physical-count form shows the room's live system count once a room is picked", async ({ page }) => {
  await page.goto("/compliance", { waitUntil: "networkidle" });

  const reconciliationRow = page.locator("table.data-table tbody tr").first();
  const roomName = (await reconciliationRow.locator("td").first().innerText()).trim();
  const systemCount = (await reconciliationRow.locator("td").nth(1).innerText()).trim();

  // Scope to the "record count" button's own container rather than trying to
  // disambiguate a bare "room" label — several other forms on this page have one too.
  const countForm = page.locator(".quick-form").filter({ has: page.getByRole("button", { name: "record count" }) });
  await selectOptionContaining(countForm.locator("select"), roomName);

  await expect(page.getByText(new RegExp(`system currently shows ${systemCount}`))).toBeVisible();
});
