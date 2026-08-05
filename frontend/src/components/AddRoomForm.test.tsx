import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AddRoomForm } from "./AddRoomForm";
import type { AdapterInfo } from "../api/client";

const { getAvailableAdapters } = vi.hoisted(() => ({
  getAvailableAdapters: vi.fn(),
}));

vi.mock("../api/client", async () => {
  const actual = await vi.importActual<typeof import("../api/client")>("../api/client");
  return {
    ...actual,
    api: {
      ...actual.api,
      getAvailableAdapters: (...args: unknown[]) => getAvailableAdapters(...args),
    },
  };
});

function adapter(overrides: Partial<AdapterInfo>): AdapterInfo {
  return {
    adapter_type: "mock",
    plugin_name: "Mock (built-in)",
    plugin_description: "",
    category: "testing",
    config_schema: {},
    required_env_vars: {},
    default_metric_config: {},
    ...overrides,
  };
}

const govee = adapter({
  adapter_type: "govee",
  plugin_name: "Govee (Cloud API)",
  category: "cloud",
  config_schema: { sku: "Device model", device: "Device id" },
  required_env_vars: { CANOPY_GOVEE_API_KEY: "API key" },
  default_metric_config: {
    temp_f: { label: "temp", unit: "°F", decimals: 1 },
    rh_pct: { label: "RH", unit: "%", decimals: 1 },
  },
});

const modbus = adapter({
  adapter_type: "modbus",
  plugin_name: "Modbus TCP/RTU",
  category: "local",
  config_schema: { registers: "list of register definitions" },
});

async function openForm() {
  render(<AddRoomForm onCreated={() => {}} />);
  await userEvent.click(screen.getByRole("button", { name: "+ add room" }));
}

describe("AddRoomForm — adapter-driven metric pre-fill", () => {
  beforeEach(() => {
    getAvailableAdapters.mockReset();
    getAvailableAdapters.mockResolvedValue([adapter({}), govee, modbus]);
  });

  it("pre-fills metric rows from the selected adapter's default_metric_config", async () => {
    await openForm();
    await waitFor(() => expect(getAvailableAdapters).toHaveBeenCalled());

    await userEvent.selectOptions(screen.getByLabelText("sensor adapter"), "govee");

    await waitFor(() => {
      expect(screen.getByDisplayValue("temp_f")).toBeInTheDocument();
      expect(screen.getByDisplayValue("rh_pct")).toBeInTheDocument();
    });
    expect(screen.getByText(/Pre-filled for Govee \(Cloud API\)/)).toBeInTheDocument();
  });

  it("leaves existing metric rows alone when switching to an adapter with no default_metric_config", async () => {
    await openForm();
    await waitFor(() => expect(getAvailableAdapters).toHaveBeenCalled());

    await userEvent.selectOptions(screen.getByLabelText("sensor adapter"), "govee");
    await waitFor(() => expect(screen.getByDisplayValue("temp_f")).toBeInTheDocument());

    await userEvent.selectOptions(screen.getByLabelText("sensor adapter"), "modbus");

    // Govee's pre-filled rows are still there — modbus has nothing to offer instead,
    // so nothing should have been cleared.
    expect(screen.getByDisplayValue("temp_f")).toBeInTheDocument();
    expect(screen.getByDisplayValue("rh_pct")).toBeInTheDocument();
  });

  it("groups adapters into optgroups by category", async () => {
    await openForm();
    await waitFor(() => expect(getAvailableAdapters).toHaveBeenCalled());

    const select = screen.getByLabelText("sensor adapter") as HTMLSelectElement;
    const groups = within(select).getAllByRole("group") as HTMLOptGroupElement[];
    const labels = groups.map((g) => g.label);

    expect(labels).toEqual(["Cloud account", "Local network", "Testing"]);
    expect(within(groups[0]).getByRole("option", { name: "Govee (Cloud API)" })).toBeInTheDocument();
    expect(within(groups[1]).getByRole("option", { name: "Modbus TCP/RTU" })).toBeInTheDocument();
  });
});
