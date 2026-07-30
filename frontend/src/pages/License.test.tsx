import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { License } from "./License";

const { getLicenseStatus } = vi.hoisted(() => ({
  getLicenseStatus: vi.fn(),
}));

vi.mock("../api/client", () => ({
  api: {
    getLicenseStatus: (...args: unknown[]) => getLicenseStatus(...args),
  },
}));

function renderPage() {
  return render(
    <MemoryRouter>
      <License />
    </MemoryRouter>,
  );
}

describe("License", () => {
  it("renders the free/unlicensed shape, where features_unlocked is a bare string", async () => {
    getLicenseStatus.mockResolvedValue({
      tier: "unlicensed",
      gate: "AlwaysUnlockedGate",
      features_unlocked: "all",
    });

    renderPage();

    expect(await screen.findByText("unlicensed")).toBeInTheDocument();
    expect(screen.getByText("AlwaysUnlockedGate")).toBeInTheDocument();
    expect(screen.getByText("Features unlocked: all")).toBeInTheDocument();
  });

  it("renders the corporate shape, where features_unlocked is an array and detail fields are listed", async () => {
    getLicenseStatus.mockResolvedValue({
      tier: "corporate",
      gate: "CanopyLicenseGate",
      license_id: "lic_abc123",
      customer_id: "cust_xyz",
      max_devices: 10,
      expires_at: "2027-07-27T20:03:09.079934+00:00",
      hardware_id: "devfallback-a00e781cddc3419d8927a93ccf9aa08e",
      last_checkin_status: "never_checked_in",
      last_successful_checkin: null,
      within_grace_period: false,
      features_unlocked: [],
    });

    renderPage();

    expect(await screen.findByText("corporate")).toBeInTheDocument();
    expect(screen.getByText("Features unlocked: none")).toBeInTheDocument();
    expect(screen.getByText("lic_abc123")).toBeInTheDocument();
    expect(screen.getByText("never_checked_in")).toBeInTheDocument();
    // last_successful_checkin is null and must be skipped, not rendered as "null"
    expect(screen.queryByText("null")).not.toBeInTheDocument();
  });

  it("shows an inline error without crashing when the request fails", async () => {
    getLicenseStatus.mockRejectedValue(new Error("simulated server error"));

    renderPage();

    expect(await screen.findByText(/Failed to load license status/)).toBeInTheDocument();
  });
});
