import { describe, expect, it } from "vitest";
import { roomLabel } from "./roomLabel";
import type { Room } from "../types";

function makeRoom(overrides: Partial<Room>): Room {
  return {
    id: "room-1",
    room_type: "greenhouse",
    path: "",
    subtitle: "",
    title: "",
    badge: "",
    footnote: "",
    section: null,
    tag_count: 0,
    stats: [],
    last_poll_at: null,
    last_poll_error: null,
    ...overrides,
  };
}

describe("roomLabel", () => {
  it("prefers the room's title", () => {
    const rooms = [makeRoom({ id: "greenhouse-a", title: "GMO", subtitle: "greenhouse — bay A" })];
    expect(roomLabel(rooms, "greenhouse-a")).toBe("GMO");
  });

  // Regression: seeded rooms like "vault" and "tissue-culture" have an empty title
  // (no single active named crop) — the dropdown/label helpers used to render them
  // blank because `??` doesn't fall through on an empty string, only null/undefined.
  it("falls back to subtitle when title is an empty string", () => {
    const rooms = [makeRoom({ id: "vault", title: "", subtitle: "vault / secure storage" })];
    expect(roomLabel(rooms, "vault")).toBe("vault / secure storage");
  });

  it("falls back to the raw id when both title and subtitle are empty", () => {
    const rooms = [makeRoom({ id: "unlabeled-room", title: "", subtitle: "" })];
    expect(roomLabel(rooms, "unlabeled-room")).toBe("unlabeled-room");
  });

  it("falls back to the raw id when the room isn't found in the list", () => {
    expect(roomLabel([], "missing-room")).toBe("missing-room");
  });

  it("renders an em dash for a null/undefined room id", () => {
    expect(roomLabel([], null)).toBe("—");
    expect(roomLabel([], undefined)).toBe("—");
  });
});
