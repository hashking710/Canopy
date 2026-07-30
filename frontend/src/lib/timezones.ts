// A short curated list, not all ~400 IANA zones — the ones a US cultivation
// operator is actually likely to be in, plus UTC as a neutral fallback.
export const TIMEZONE_OPTIONS: { value: string; label: string }[] = [
  { value: "", label: "Use browser default" },
  { value: "America/Los_Angeles", label: "Pacific (Los Angeles)" },
  { value: "America/Denver", label: "Mountain (Denver)" },
  { value: "America/Phoenix", label: "Mountain, no DST (Phoenix)" },
  { value: "America/Chicago", label: "Central (Chicago)" },
  { value: "America/New_York", label: "Eastern (New York)" },
  { value: "America/Anchorage", label: "Alaska (Anchorage)" },
  { value: "Pacific/Honolulu", label: "Hawaii (Honolulu)" },
  { value: "UTC", label: "UTC" },
];
