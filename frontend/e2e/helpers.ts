import type { Locator } from "@playwright/test";

export const API_BASE = process.env.CANOPY_E2E_API_BASE_URL ?? "http://localhost:8000";
export const MASTER_API_BASE = process.env.CANOPY_E2E_MASTER_API_BASE_URL ?? "http://localhost:9100";

// Playwright's selectOption({ label }) requires an exact match against the option's
// full text, but option text in this app is usually "<name> — <detail>" — this finds
// the option containing the given substring and selects it by its real value instead.
export async function selectOptionContaining(select: Locator, text: string) {
  const value = await select.locator("option", { hasText: text }).first().getAttribute("value");
  await select.selectOption(value!);
}
