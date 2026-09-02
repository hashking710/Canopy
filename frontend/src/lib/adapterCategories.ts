import type { AdapterInfo } from "../api/client";

// Groups the adapter picker by connection type (driven by each adapter's own
// `category`, see adapters/base.py) instead of one flat list of ~20 similarly-terse
// names — someone with a Govee sensor can go straight to "Cloud account" instead of
// scanning the whole list. Order is deliberate: real-hardware categories first,
// mock/testing last since it's not what most people are looking for. Shared between
// AddRoomForm (a room's primary adapter) and ExtraAdaptersCard (additional sensors
// on an existing room) — both need the identical grouped picker.
export const CATEGORY_LABELS: Record<string, string> = {
  cloud: "Cloud account",
  local: "Local network",
  bluetooth: "Bluetooth",
  hardware: "Direct-attached (Pi GPIO/I2C)",
  testing: "Testing",
  other: "Other",
};
export const CATEGORY_ORDER = ["cloud", "local", "bluetooth", "hardware", "testing", "other"];

export function groupAdaptersByCategory(adapters: AdapterInfo[]): [string, AdapterInfo[]][] {
  const groups = new Map<string, AdapterInfo[]>();
  for (const adapter of adapters) {
    const category = adapter.category || "other";
    if (!groups.has(category)) groups.set(category, []);
    groups.get(category)!.push(adapter);
  }
  return CATEGORY_ORDER.filter((c) => groups.has(c)).map((c) => [c, groups.get(c)!]);
}
