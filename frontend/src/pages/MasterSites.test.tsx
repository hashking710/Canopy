import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { MasterSites } from "./MasterSites";

const { getSites, getAuditLog } = vi.hoisted(() => ({
  getSites: vi.fn(),
  getAuditLog: vi.fn(),
}));

vi.mock("../api/masterClient", () => ({
  masterApi: {
    getSites: (...args: unknown[]) => getSites(...args),
    getAuditLog: (...args: unknown[]) => getAuditLog(...args),
  },
}));

function renderPage() {
  return render(
    <MemoryRouter>
      <MasterSites />
    </MemoryRouter>,
  );
}

describe("MasterSites", () => {
  it("shows a friendly explainer instead of a raw error when master isn't running", async () => {
    getSites.mockRejectedValue(new Error("Failed to fetch"));

    renderPage();

    expect(await screen.findByText("This facility isn't part of a multi-site setup")).toBeInTheDocument();
    expect(screen.queryByText(/^Failed to load master service:/)).not.toBeInTheDocument();
  });

  it("renders the real site list when master responds normally", async () => {
    getSites.mockResolvedValue([{ site_id: "site-1", room_count: 3, online: true }]);
    getAuditLog.mockResolvedValue([]);

    renderPage();

    expect(await screen.findByText("site-1")).toBeInTheDocument();
  });

  it("shows relayed audit entries from every site once they exist", async () => {
    getSites.mockResolvedValue([{ site_id: "site-1", room_count: 1, online: true }]);
    getAuditLog.mockResolvedValue([
      {
        id: 1, site_id: "site-1", origin_device_id: "pi-veg", origin_entry_id: 42,
        entity_type: "plant", entity_id: "plant-abc", action: "moved", actor: "Alex Rivera",
        room_id: "greenhouse-a", details: {}, occurred_at: "2026-07-30T00:00:00Z",
        entry_hash: "abc123", received_at: "2026-07-30T00:00:05Z",
      },
    ]);

    renderPage();

    expect(await screen.findByText(/plant\/plant-abc/)).toBeInTheDocument();
    expect(screen.getByText("Alex Rivera")).toBeInTheDocument();
  });

  it("shows an explainer instead of an empty list when nothing has relayed yet", async () => {
    getSites.mockResolvedValue([{ site_id: "site-1", room_count: 1, online: true }]);
    getAuditLog.mockResolvedValue([]);

    renderPage();

    expect(await screen.findByText(/No relayed audit events yet/)).toBeInTheDocument();
  });
});
