import { afterEach, describe, expect, it } from "vitest";
import { formatDate, formatDateTime, formatTime } from "./formatDateTime";
import { TIMEZONE_KEY } from "../hooks/useSettings";

const SAMPLE_ISO = "2026-03-15T18:30:00.000Z";

describe("formatDateTime", () => {
  afterEach(() => {
    localStorage.removeItem(TIMEZONE_KEY);
  });

  it("formats in UTC when the timezone setting is explicitly UTC", () => {
    localStorage.setItem(TIMEZONE_KEY, "UTC");
    expect(formatTime(SAMPLE_ISO)).toMatch(/6:30/);
    expect(formatDate(SAMPLE_ISO)).toContain("2026");
    expect(formatDateTime(SAMPLE_ISO)).toContain("2026");
  });

  it("falls back to the browser default when no timezone is set", () => {
    // No localStorage entry — must not throw, and must still produce real output
    // (Intl.DateTimeFormat treats an undefined timeZone option as "use runtime default").
    expect(() => formatDateTime(SAMPLE_ISO)).not.toThrow();
    expect(formatDateTime(SAMPLE_ISO).length).toBeGreaterThan(0);
  });

  it("produces a different clock time in a different explicit timezone", () => {
    localStorage.setItem(TIMEZONE_KEY, "Pacific/Honolulu");
    const honolulu = formatTime(SAMPLE_ISO);
    localStorage.setItem(TIMEZONE_KEY, "UTC");
    const utc = formatTime(SAMPLE_ISO);
    expect(honolulu).not.toBe(utc);
  });
});
