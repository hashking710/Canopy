import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Genetics } from "./Genetics";

const { getStrains, createStrain, deactivateStrain } = vi.hoisted(() => ({
  getStrains: vi.fn(),
  createStrain: vi.fn(),
  deactivateStrain: vi.fn(),
}));

vi.mock("../api/strainsClient", () => ({
  strainsApi: {
    getStrains: (...args: unknown[]) => getStrains(...args),
    createStrain: (...args: unknown[]) => createStrain(...args),
    deactivateStrain: (...args: unknown[]) => deactivateStrain(...args),
  },
}));

const { getOperators } = vi.hoisted(() => ({ getOperators: vi.fn() }));
vi.mock("../api/complianceClient", () => ({
  complianceApi: { getOperators: (...args: unknown[]) => getOperators(...args) },
}));

const operator = { id: "op-1", name: "Alex Rivera", role: "operator", has_pin: false };

function renderPage() {
  return render(
    <MemoryRouter>
      <Genetics />
    </MemoryRouter>,
  );
}

describe("Genetics", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getOperators.mockResolvedValue([operator]);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("shows a message when no strains are registered", async () => {
    getStrains.mockResolvedValue([]);
    renderPage();
    expect(await screen.findByText("no strains registered yet")).toBeInTheDocument();
  });

  it("lists registered strains with their type and typical potency", async () => {
    getStrains.mockResolvedValue([
      {
        id: "strain-1", name: "GMO", lineage: "Chemdog x GSC", strain_type: "hybrid", description: "",
        thc_pct_typical: 24.5, cbd_pct_typical: 0.3, active: true, created_at: "2026-01-01T00:00:00Z",
      },
    ]);
    renderPage();

    expect(await screen.findByText("GMO")).toBeInTheDocument();
    expect(screen.getByText("hybrid", { selector: "span" })).toBeInTheDocument();
    expect(screen.getByText("Chemdog x GSC")).toBeInTheDocument();
    expect(screen.getByText("24.5% THC / 0.3% CBD")).toBeInTheDocument();
  });

  it("creates a new strain and refreshes the list", async () => {
    const user = userEvent.setup();
    getStrains.mockResolvedValue([]);
    createStrain.mockResolvedValue({
      id: "strain-1", name: "Jelly Breath", lineage: "", strain_type: "hybrid", description: "",
      thc_pct_typical: null, cbd_pct_typical: null, active: true, created_at: "2026-01-01T00:00:00Z",
    });
    renderPage();
    await screen.findByText("no strains registered yet");

    await user.type(screen.getByPlaceholderText("e.g. GMO"), "Jelly Breath");
    getStrains.mockResolvedValue([
      {
        id: "strain-1", name: "Jelly Breath", lineage: "", strain_type: "hybrid", description: "",
        thc_pct_typical: null, cbd_pct_typical: null, active: true, created_at: "2026-01-01T00:00:00Z",
      },
    ]);
    await user.click(screen.getByText("add strain"));

    await waitFor(() =>
      expect(createStrain).toHaveBeenCalledWith(
        expect.objectContaining({ name: "Jelly Breath", operator_id: "op-1" }),
      ),
    );
    expect(await screen.findByText("Jelly Breath")).toBeInTheDocument();
  });

  it("deactivates a strain", async () => {
    const user = userEvent.setup();
    getStrains.mockResolvedValue([
      {
        id: "strain-1", name: "GMO", lineage: "", strain_type: "hybrid", description: "",
        thc_pct_typical: null, cbd_pct_typical: null, active: true, created_at: "2026-01-01T00:00:00Z",
      },
    ]);
    deactivateStrain.mockResolvedValue(undefined);
    renderPage();
    await screen.findByText("GMO");

    getStrains.mockResolvedValue([]);
    await user.click(screen.getByText("deactivate"));

    await waitFor(() => expect(deactivateStrain).toHaveBeenCalledWith("strain-1", "op-1"));
    expect(await screen.findByText("no strains registered yet")).toBeInTheDocument();
  });
});
