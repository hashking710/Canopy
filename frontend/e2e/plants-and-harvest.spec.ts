import { expect, test } from "@playwright/test";
import { selectOptionContaining } from "./helpers";

const API_BASE = "http://localhost:8000";

test("tagging plants from a batch moves them into the tagged-plants table", async ({ page }) => {
  const batches = await (await page.request.get(`${API_BASE}/api/compliance/plant-batches`)).json();
  const taggable = batches.find((b: { untracked_count: number }) => b.untracked_count > 0);
  test.skip(!taggable, "no batch with untracked plants available to tag right now");

  await page.goto("/plants", { waitUntil: "networkidle" });

  const tagForm = page.locator(".quick-form").filter({ has: page.getByRole("button", { name: "tag plants" }) });
  await tagForm.locator("select").first().selectOption(taggable.id);
  await tagForm.getByLabel("count to tag").fill("1");
  await tagForm.getByRole("button", { name: "tag plants" }).click();

  await expect(tagForm.getByText("✓ tagged")).toBeVisible();
});

test("starting a harvest and packaging it produces a package with a lab-test COA attachment", async ({ page }) => {
  const rooms = await (await page.request.get(`${API_BASE}/api/rooms`)).json();
  const sourceRoom = rooms.find((r: { room_type: string }) => r.room_type !== "facility");
  const suffix = Date.now();
  const harvestName = `E2E-Harvest-${suffix}`;
  const packageName = `E2E Package ${suffix}`;

  await page.goto("/plants/harvests", { waitUntil: "networkidle" });

  const createHarvest = page.locator(".action-subsection", { hasText: "Start a new harvest" });
  await createHarvest.getByPlaceholder("must be unique").fill(harvestName);
  await createHarvest.getByLabel("strain").fill("E2E Test Strain");
  await createHarvest.getByLabel("source room").selectOption(sourceRoom.id);
  await createHarvest.getByRole("button", { name: "start harvest" }).click();
  await expect(createHarvest.getByText("✓ harvest started")).toBeVisible();

  const packageForm = page.locator(".action-subsection", { hasText: "Create a package from a harvest" });
  // Positional, not getByLabel: "production batch"'s own field-hint text happens to
  // contain the substring "from harvest" (as part of "...straight from harvested
  // flower"), which any label-text match — even exact:true, which trips on a
  // whitespace-normalization quirk here — risks picking up instead. "from harvest" is
  // reliably the form's first select.
  await selectOptionContaining(packageForm.locator("select").first(), harvestName);
  await packageForm.getByPlaceholder("e.g. GMO — 3.5g flower").fill(packageName);
  await packageForm.getByLabel("weight (g)").fill("50");
  await packageForm.getByLabel("room").selectOption(sourceRoom.id);
  await packageForm.getByRole("button", { name: "create package" }).click();
  await expect(packageForm.getByText("✓ package created")).toBeVisible();

  await page.goto("/plants/packages", { waitUntil: "networkidle" });
  // Three separate forms on this page all have a bare "package" select (status,
  // lineage, lab test) — scope to the one that also has "lab name", the one field
  // unique to the lab-test form, rather than risking an ambiguous label match.
  const labTestForm = page.locator(".quick-form").filter({ has: page.getByPlaceholder("lab name") });
  await selectOptionContaining(labTestForm.locator("select").first(), packageName);
  await labTestForm.getByPlaceholder("lab name").fill("E2E Test Lab");
  await labTestForm.getByLabel("tested on").fill(new Date().toISOString().slice(0, 10));
  await labTestForm.getByRole("button", { name: "record test" }).click();
  await expect(labTestForm.getByText("✓ test recorded")).toBeVisible();

  const fileInput = page.locator("input[type=file]").first();
  await fileInput.setInputFiles({ name: "coa.pdf", mimeType: "application/pdf", buffer: Buffer.from("%PDF-1.4 e2e fake coa") });
  await expect(page.getByText("view COA").first()).toBeVisible();
});
