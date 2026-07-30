// FastAPI's own validation errors (422) come back as {"detail": [{"msg": "...", ...}]},
// not a plain string — surfacing that array's default toString() would show the user
// "[object Object]" instead of a readable message.
export function formatErrorDetail(detail: unknown, fallback: string): string {
  if (typeof detail === "string" && detail) return detail;
  if (Array.isArray(detail) && detail.length > 0) {
    return detail
      .map((item) => (item && typeof item === "object" && "msg" in item ? String((item as { msg: unknown }).msg) : String(item)))
      .join("; ");
  }
  return fallback;
}
