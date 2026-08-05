import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { EntityCard } from "./EntityCard";
import type { Room } from "../types";

function room(overrides: Partial<Room>): Room {
  return {
    id: "greenhouse-a",
    room_type: "greenhouse",
    path: "~/greenhouse-a",
    subtitle: "",
    title: "GMO",
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

describe("EntityCard — sensor health", () => {
  it("shows nothing extra when the room is healthy", () => {
    render(<EntityCard room={room({})} />);
    expect(screen.queryByText("sensor offline")).not.toBeInTheDocument();
  });

  it("shows the actual error text inline, not just as a hover-only title", () => {
    render(
      <EntityCard
        room={room({ last_poll_error: "govee adapter requires CANOPY_GOVEE_API_KEY to be set" })}
      />,
    );
    expect(screen.getByText("sensor offline")).toBeInTheDocument();
    // The old behavior only put this in a `title` attribute, invisible without
    // hovering (and on touch devices, invisible entirely) — this must be real,
    // visible text content instead.
    expect(
      screen.getByText("govee adapter requires CANOPY_GOVEE_API_KEY to be set"),
    ).toBeInTheDocument();
  });
});
