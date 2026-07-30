import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { PlantsBatches } from "./PlantsBatches";
import type { Operator, Plant } from "../api/complianceTypes";

const { getPlantBatches, getPlants, getHarvests, getOperators, destroyPlant } = vi.hoisted(() => ({
  getPlantBatches: vi.fn(),
  getPlants: vi.fn(),
  getHarvests: vi.fn(),
  getOperators: vi.fn(),
  destroyPlant: vi.fn(),
}));

vi.mock("../api/complianceClient", () => ({
  complianceApi: {
    getPlantBatches: (...args: unknown[]) => getPlantBatches(...args),
    getPlants: (...args: unknown[]) => getPlants(...args),
    getHarvests: (...args: unknown[]) => getHarvests(...args),
    getOperators: (...args: unknown[]) => getOperators(...args),
    destroyPlant: (...args: unknown[]) => destroyPlant(...args),
  },
}));

const { getRooms } = vi.hoisted(() => ({ getRooms: vi.fn() }));
vi.mock("../api/client", () => ({
  api: { getRooms: (...args: unknown[]) => getRooms(...args) },
}));

const operator: Operator = { id: "op-1", name: "Alex Rivera", has_pin: false };
const plant: Plant = {
  id: "tag-001",
  batch_id: null,
  strain: "GMO",
  room_id: "room-1",
  growth_phase: "Flowering",
  planted_date: "2026-01-01",
  tagged_date: "2026-01-10",
  status: "active",
};

describe("PlantsBatches — destroy plant confirmation", () => {
  beforeEach(() => {
    getPlantBatches.mockResolvedValue([]);
    getPlants.mockResolvedValue([plant]);
    getHarvests.mockResolvedValue([]);
    getOperators.mockResolvedValue([operator]);
    getRooms.mockResolvedValue([]);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("does not call destroyPlant when the confirmation is declined", async () => {
    const user = userEvent.setup();
    vi.spyOn(window, "confirm").mockReturnValue(false);

    render(
      <MemoryRouter initialEntries={["/plants"]}>
        <PlantsBatches />
      </MemoryRouter>,
    );

    const destroyForm = (await screen.findByText("destroy plant")).closest(".quick-form") as HTMLElement;
    await user.selectOptions(destroyForm.querySelector("select")!, "tag-001");
    await user.type(destroyForm.querySelector("input[type=number]")!, "5");
    await user.click(screen.getByText("destroy plant"));

    expect(window.confirm).toHaveBeenCalled();
    expect(destroyPlant).not.toHaveBeenCalled();
  });

  it("calls destroyPlant once the confirmation is accepted", async () => {
    const user = userEvent.setup();
    vi.spyOn(window, "confirm").mockReturnValue(true);
    destroyPlant.mockResolvedValue({});

    render(
      <MemoryRouter initialEntries={["/plants"]}>
        <PlantsBatches />
      </MemoryRouter>,
    );

    const destroyForm = (await screen.findByText("destroy plant")).closest(".quick-form") as HTMLElement;
    await user.selectOptions(destroyForm.querySelector("select")!, "tag-001");
    await user.type(destroyForm.querySelector("input[type=number]")!, "5");
    await user.click(screen.getByText("destroy plant"));

    await waitFor(() => expect(destroyPlant).toHaveBeenCalledWith("tag-001", expect.objectContaining({ weight_g: 5 })));
  });
});

describe("PlantsBatches — plant search", () => {
  const gmoPlant: Plant = { ...plant, id: "GMO-tag-001", strain: "GMO", room_id: "room-1" };
  const jellyPlant: Plant = { ...plant, id: "JB-tag-002", strain: "Jelly Breath", room_id: "room-2" };

  beforeEach(() => {
    getPlantBatches.mockResolvedValue([]);
    getPlants.mockResolvedValue([gmoPlant, jellyPlant]);
    getHarvests.mockResolvedValue([]);
    getOperators.mockResolvedValue([operator]);
    getRooms.mockResolvedValue([
      { id: "room-1", title: "Greenhouse A" },
      { id: "room-2", title: "Greenhouse B" },
    ]);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("shows both plants with no search text", async () => {
    render(
      <MemoryRouter initialEntries={["/plants"]}>
        <PlantsBatches />
      </MemoryRouter>,
    );
    expect(await screen.findByText("GMO-tag-001")).toBeInTheDocument();
    expect(screen.getByText("JB-tag-002")).toBeInTheDocument();
  });

  it("filters by tag", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/plants"]}>
        <PlantsBatches />
      </MemoryRouter>,
    );
    await screen.findByText("GMO-tag-001");

    await user.type(screen.getByPlaceholderText("search by tag, strain, or room…"), "JB-tag");
    expect(screen.queryByText("GMO-tag-001")).not.toBeInTheDocument();
    expect(screen.getByText("JB-tag-002")).toBeInTheDocument();
  });

  it("filters by strain, case-insensitively", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/plants"]}>
        <PlantsBatches />
      </MemoryRouter>,
    );
    await screen.findByText("GMO-tag-001");

    await user.type(screen.getByPlaceholderText("search by tag, strain, or room…"), "jelly");
    expect(screen.queryByText("GMO-tag-001")).not.toBeInTheDocument();
    expect(screen.getByText("JB-tag-002")).toBeInTheDocument();
  });

  it("filters by room label", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/plants"]}>
        <PlantsBatches />
      </MemoryRouter>,
    );
    await screen.findByText("GMO-tag-001");

    await user.type(screen.getByPlaceholderText("search by tag, strain, or room…"), "Greenhouse B");
    expect(screen.queryByText("GMO-tag-001")).not.toBeInTheDocument();
    expect(screen.getByText("JB-tag-002")).toBeInTheDocument();
  });

  it("shows a no-match message when nothing matches, without hiding the empty-state distinction", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/plants"]}>
        <PlantsBatches />
      </MemoryRouter>,
    );
    await screen.findByText("GMO-tag-001");

    await user.type(screen.getByPlaceholderText("search by tag, strain, or room…"), "nonexistent-strain-xyz");
    expect(screen.queryByText("GMO-tag-001")).not.toBeInTheDocument();
    expect(screen.getByText(/no plants match/)).toBeInTheDocument();
  });
});
