import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { OnboardingWizard } from "./OnboardingWizard";

const { createFacility, getAvailableAdapters } = vi.hoisted(() => ({
  createFacility: vi.fn(),
  getAvailableAdapters: vi.fn(),
}));
vi.mock("../api/client", () => ({
  api: {
    createFacility: (...args: unknown[]) => createFacility(...args),
    getAvailableAdapters: (...args: unknown[]) => getAvailableAdapters(...args),
  },
}));

const { getOperators, createOperator, getStateRules, setStateRules } = vi.hoisted(() => ({
  getOperators: vi.fn(),
  createOperator: vi.fn(),
  getStateRules: vi.fn(),
  setStateRules: vi.fn(),
}));
vi.mock("../api/complianceClient", () => ({
  complianceApi: {
    getOperators: (...args: unknown[]) => getOperators(...args),
    createOperator: (...args: unknown[]) => createOperator(...args),
    getStateRules: (...args: unknown[]) => getStateRules(...args),
    setStateRules: (...args: unknown[]) => setStateRules(...args),
  },
}));

function renderWizard(onFinished = vi.fn()) {
  return { onFinished, ...render(
    <MemoryRouter>
      <OnboardingWizard onFinished={onFinished} />
    </MemoryRouter>,
  ) };
}

describe("OnboardingWizard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getOperators.mockResolvedValue([]);
    getAvailableAdapters.mockResolvedValue([]);
    getStateRules.mockResolvedValue({ active: null, explicitly_set: false, available: [] });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("starts on the facility step", async () => {
    renderWizard();
    expect(await screen.findByText("Set up your facility")).toBeInTheDocument();
  });

  it("advances to the operator step after creating a facility", async () => {
    const user = userEvent.setup();
    createFacility.mockResolvedValue({ id: "facility", title: "Test Farm" });
    renderWizard();

    await user.type(screen.getByPlaceholderText("e.g. Ridgeline Cultivation"), "Test Farm");
    await user.click(screen.getByText("create facility"));

    await waitFor(() => expect(createFacility).toHaveBeenCalledWith({ title: "Test Farm", section: "the facility" }));
    expect(await screen.findByText("Register yourself as an operator")).toBeInTheDocument();
  });

  it("advances to the jurisdiction step once an operator is created", async () => {
    const user = userEvent.setup();
    createFacility.mockResolvedValue({ id: "facility", title: "Test Farm" });
    createOperator.mockResolvedValue({ id: "op-1", name: "Alex", role: "admin", has_pin: false });
    renderWizard();

    await user.type(screen.getByPlaceholderText("e.g. Ridgeline Cultivation"), "Test Farm");
    await user.click(screen.getByText("create facility"));
    await screen.findByText("Register yourself as an operator");

    await user.click(screen.getByText("+ add operator"));
    await user.type(screen.getByPlaceholderText("name"), "Alex");
    await user.click(screen.getByText("save"));

    expect(await screen.findByText("What state are you licensed in?")).toBeInTheDocument();
  });

  it("skipping the jurisdiction step advances straight to the room step", async () => {
    const user = userEvent.setup();
    createFacility.mockResolvedValue({ id: "facility", title: "Test Farm" });
    createOperator.mockResolvedValue({ id: "op-1", name: "Alex", role: "admin", has_pin: false });
    renderWizard();

    await user.type(screen.getByPlaceholderText("e.g. Ridgeline Cultivation"), "Test Farm");
    await user.click(screen.getByText("create facility"));
    await screen.findByText("Register yourself as an operator");
    await user.click(screen.getByText("+ add operator"));
    await user.type(screen.getByPlaceholderText("name"), "Alex");
    await user.click(screen.getByText("save"));
    await screen.findByText("What state are you licensed in?");

    await user.click(screen.getByText("skip for now"));

    expect(await screen.findByText("Add your first room")).toBeInTheDocument();
  });

  it("skipping the room step advances to the license nudge, not straight to the dashboard", async () => {
    const user = userEvent.setup();
    createFacility.mockResolvedValue({ id: "facility", title: "Test Farm" });
    createOperator.mockResolvedValue({ id: "op-1", name: "Alex", role: "admin", has_pin: false });
    const { onFinished } = renderWizard();

    await user.type(screen.getByPlaceholderText("e.g. Ridgeline Cultivation"), "Test Farm");
    await user.click(screen.getByText("create facility"));
    await screen.findByText("Register yourself as an operator");
    await user.click(screen.getByText("+ add operator"));
    await user.type(screen.getByPlaceholderText("name"), "Alex");
    await user.click(screen.getByText("save"));
    await screen.findByText("What state are you licensed in?");
    await user.click(screen.getByText("skip for now"));
    await screen.findByText("Add your first room");

    await user.click(screen.getByText("I'll add a room later"));

    expect(await screen.findByText("One last thing — get a free license")).toBeInTheDocument();
    expect(onFinished).not.toHaveBeenCalled();
  });

  it("the license nudge's link points at the real free checkout, and finishes onboarding on continue", async () => {
    const user = userEvent.setup();
    createFacility.mockResolvedValue({ id: "facility", title: "Test Farm" });
    createOperator.mockResolvedValue({ id: "op-1", name: "Alex", role: "admin", has_pin: false });
    const { onFinished } = renderWizard();

    await user.type(screen.getByPlaceholderText("e.g. Ridgeline Cultivation"), "Test Farm");
    await user.click(screen.getByText("create facility"));
    await screen.findByText("Register yourself as an operator");
    await user.click(screen.getByText("+ add operator"));
    await user.type(screen.getByPlaceholderText("name"), "Alex");
    await user.click(screen.getByText("save"));
    await screen.findByText("What state are you licensed in?");
    await user.click(screen.getByText("skip for now"));
    await screen.findByText("Add your first room");
    await user.click(screen.getByText("I'll add a room later"));
    await screen.findByText("One last thing — get a free license");

    const cta = screen.getByText("Get a free license →");
    expect(cta.closest("a")).toHaveAttribute("href", "https://canopy.hkdev.run/checkout");

    await user.click(screen.getByText("go to dashboard"));

    expect(onFinished).toHaveBeenCalled();
  });
});
