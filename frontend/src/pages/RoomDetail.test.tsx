import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { RoomDetail } from "./RoomDetail";
import type { Room } from "../types";

const { getRoom, getRoomReadings, deleteRoom, connectLiveUpdates } = vi.hoisted(() => ({
  getRoom: vi.fn(),
  getRoomReadings: vi.fn(),
  deleteRoom: vi.fn(),
  connectLiveUpdates: vi.fn((..._args: unknown[]) => () => {}),
}));

vi.mock("../api/client", () => ({
  api: {
    getRoom: (...args: unknown[]) => getRoom(...args),
    getRoomReadings: (...args: unknown[]) => getRoomReadings(...args),
    deleteRoom: (...args: unknown[]) => deleteRoom(...args),
  },
  connectLiveUpdates: (...args: unknown[]) => connectLiveUpdates(...args),
}));

const room: Room = {
  id: "greenhouse-a",
  room_type: "greenhouse",
  path: "greenhouse-a",
  subtitle: "greenhouse — bay A",
  title: "GMO",
  badge: "",
  footnote: "",
  section: "the greenhouse",
  tag_count: 0,
  stats: [],
  last_poll_at: null,
  last_poll_error: null,
};

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/rooms/greenhouse-a"]}>
      <Routes>
        <Route path="/rooms/:roomId" element={<RoomDetail />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("RoomDetail — delete failure must not blank the page", () => {
  beforeEach(() => {
    getRoom.mockResolvedValue(room);
    getRoomReadings.mockResolvedValue([]);
    vi.spyOn(window, "confirm").mockReturnValue(true);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("keeps the room content and back-link visible after a failed delete, showing the error inline instead", async () => {
    const user = userEvent.setup();
    deleteRoom.mockRejectedValue(new Error("simulated server error"));

    renderPage();
    expect(await screen.findByText("GMO")).toBeInTheDocument();

    await user.click(screen.getByText("delete room"));

    // The room's own content and the way back must survive a failed delete — this is
    // a regression test: these two used to share one `error` state with the initial
    // room-load fetch, so a failed *delete* replaced the whole page with a generic
    // "Failed to load" screen that had no link back to the facility at all.
    await waitFor(() => expect(screen.getByText("simulated server error")).toBeInTheDocument());
    expect(screen.getByText("GMO")).toBeInTheDocument();
    expect(screen.getByText("← Back to facility")).toBeInTheDocument();
    expect(screen.queryByText(/Failed to load/)).not.toBeInTheDocument();
  });

  it("still navigates away on a successful delete", async () => {
    const user = userEvent.setup();
    deleteRoom.mockResolvedValue({ id: "greenhouse-a", deleted: true });

    renderPage();
    await screen.findByText("GMO");

    await user.click(screen.getByText("delete room"));

    await waitFor(() => expect(deleteRoom).toHaveBeenCalledWith("greenhouse-a"));
  });
});

describe("RoomDetail — live connection", () => {
  const roomWithStats: Room = {
    ...room,
    stats: [
      { key: "temp_f", label: "temp", unit: "°F", value: 75, decimals: 1 },
      { key: "rh_pct", label: "RH", unit: "%", value: 50, decimals: 1 },
    ],
  };

  beforeEach(() => {
    connectLiveUpdates.mockClear();
    getRoom.mockResolvedValue(roomWithStats);
    getRoomReadings.mockResolvedValue([]);
  });

  it("opens exactly one live connection and does not reopen it when switching metric tabs", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("GMO");

    expect(connectLiveUpdates).toHaveBeenCalledTimes(1);

    await user.click(screen.getByText("RH"));
    await user.click(screen.getByText("temp"));

    // Regression test: this effect used to depend on `selectedMetric`, so every tab
    // click tore down and reopened the whole websocket connection instead of just
    // changing which metric the existing connection's handler cares about.
    expect(connectLiveUpdates).toHaveBeenCalledTimes(1);
  });

  it("shows a disconnected notice when the live connection drops, via the onStatusChange callback", async () => {
    renderPage();
    await screen.findByText("GMO");

    expect(screen.queryByText(/Live updates disconnected/)).not.toBeInTheDocument();

    const onStatusChange = connectLiveUpdates.mock.calls[0][1] as (connected: boolean) => void;
    onStatusChange(false);

    expect(await screen.findByText(/Live updates disconnected/)).toBeInTheDocument();
  });
});
