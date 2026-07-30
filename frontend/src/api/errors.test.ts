import { describe, expect, it } from "vitest";
import { formatErrorDetail } from "./errors";

describe("formatErrorDetail", () => {
  it("returns a plain string detail as-is", () => {
    expect(formatErrorDetail("plant batch not found", "fallback")).toBe("plant batch not found");
  });

  it("joins FastAPI's pydantic validation error array into a readable message", () => {
    const detail = [
      { type: "missing", loc: ["body", "room_id"], msg: "Field required" },
      { type: "greater_than", loc: ["body", "weight_g"], msg: "Input should be greater than 0" },
    ];
    expect(formatErrorDetail(detail, "fallback")).toBe("Field required; Input should be greater than 0");
  });

  it("falls back to the provided fallback for an empty detail", () => {
    expect(formatErrorDetail(undefined, "path -> 500")).toBe("path -> 500");
    expect(formatErrorDetail("", "path -> 500")).toBe("path -> 500");
    expect(formatErrorDetail([], "path -> 500")).toBe("path -> 500");
  });
});
