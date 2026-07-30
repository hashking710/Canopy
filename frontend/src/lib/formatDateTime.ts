import { TIMEZONE_KEY } from "../hooks/useSettings";

// Reads localStorage directly rather than threading the setting through every
// call site as a hook value — these are plain formatting calls made at render
// time, not stateful UI that needs to re-render when the setting changes elsewhere
// on the same page (Settings.tsx is the only place that changes it, and it's a
// full page navigation away from anywhere these are used).
function currentTimezone(): string | undefined {
  return localStorage.getItem(TIMEZONE_KEY) || undefined;
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { timeZone: currentTimezone() });
}

export function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString(undefined, { timeZone: currentTimezone() });
}

export function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString(undefined, { timeZone: currentTimezone() });
}
