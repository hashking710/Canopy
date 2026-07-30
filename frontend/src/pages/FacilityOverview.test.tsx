import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { FacilityOverview } from "./FacilityOverview";
import type { Room } from "../types";

const { getFacility, getRooms, connectLiveUpdates } = vi.hoisted(() => ({
  getFacility: vi.fn(),
  getRooms: vi.fn(),
  connectLiveUpdates: vi.fn((..._args: unknown[]) => () => {}),
}));

vi.mock("../api/client", async () => {
  const actual = await vi.importActual<typeof import("../api/client")>("../api/client");
  return {
    ...actual,
    api: {
      ...actual.api,
      getFacility: (...args: unknown[]) => getFacility(...args),
      getRooms: (...args: unknown[]) => getRooms(...args),
    },
    connectLiveUpdates: (...args: unknown[]) => connectLiveUpdates(...args),
  };
});

const facility: Room = {
  id: "facility",
  room_type: "facility",
  path: "~/facility",
  subtitle: "",
  title: "",
  badge: "",
  footnote: "",
  section: "the facility",
  tag_count: 0,
  stats: [],
  last_poll_at: null,
  last_poll_error: null,
};

function renderPage() {
  return render(
    <MemoryRouter>
      <FacilityOverview />
    </MemoryRouter>,
  );
}

describe("FacilityOverview — live connection notice", () => {
  beforeEach(() => {
    connectLiveUpdates.mockClear();
    getFacility.mockResolvedValue(facility);
    getRooms.mockResolvedValue([]);
  });

  it("stays hidden while connected, and appears when the connection drops", async () => {
    renderPage();
    await screen.findByText("the facility");

    expect(screen.queryByText(/Live updates disconnected/)).not.toBeInTheDocument();

    const onStatusChange = connectLiveUpdates.mock.calls[0][1] as (connected: boolean) => void;
    onStatusChange(false);
    expect(await screen.findByText(/Live updates disconnected/)).toBeInTheDocument();

    onStatusChange(true);
    await waitFor(() => expect(screen.queryByText(/Live updates disconnected/)).not.toBeInTheDocument());
  });
});
