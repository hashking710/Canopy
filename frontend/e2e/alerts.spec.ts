import { expect, test } from "@playwright/test";

test("creating and removing an alert rule round-trips through the rules table", async ({ page }) => {
  await page.goto("/alerts", { waitUntil: "networkidle" });

  const ruleForm = page.locator(".quick-form").filter({ has: page.getByRole("button", { name: "add rule" }) });
  const roomSelect = ruleForm.locator("select").first();
  const options = await roomSelect.locator("option").allTextContents();
  test.skip(options.length <= 1, "no rooms available to attach an alert rule to");

  await roomSelect.selectOption({ index: 1 });
  const metricSelect = ruleForm.locator("select").nth(1);
  await expect(metricSelect).toBeEnabled();
  await metricSelect.selectOption({ index: 1 });
  await ruleForm.getByLabel("threshold").fill("999999"); // implausible value, easy to find/remove uniquely

  await ruleForm.getByRole("button", { name: "add rule" }).click();
  // The success message is a sibling of .quick-form, not nested inside it — check at
  // page level rather than scoped to ruleForm.
  await expect(page.getByText("✓ rule added")).toBeVisible();

  const newRuleRow = page.locator("table.data-table tbody tr", { hasText: "999999" });
  await expect(newRuleRow).toBeVisible();

  await newRuleRow.getByRole("button", { name: "remove" }).click();
  await expect(newRuleRow).not.toBeVisible();
});
