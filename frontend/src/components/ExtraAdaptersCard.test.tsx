import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ExtraAdaptersCard } from "./ExtraAdaptersCard";
import type { AdapterInfo, RoomConfig } from "../api/client";
import type { Operator } from "../api/complianceTypes";

const testOperator: Operator = {
  id: "op-1",
  name: "Test Operator",
  role: "admin",
  has_pin: false,
  notify_email: null,
  notify_on_alerts: false,
  notify_on_system_errors: false,
  notify_min_severity: "critical",
};

const { getRoomConfig, getAvailableAdapters, addRoomAdapter, removeRoomAdapter } = vi.hoisted(() => ({
  getRoomConfig: vi.fn(),
  getAvailableAdapters: vi.fn(),
  addRoomAdapter: vi.fn(),
  removeRoomAdapter: vi.fn(),
}));

vi.mock("../api/client", async () => {
  const actual = await vi.importActual<typeof import("../api/client")>("../api/client");
  return {
    ...actual,
    api: {
      ...actual.api,
      getRoomConfig: (...args: unknown[]) => getRoomConfig(...args),
      getAvailableAdapters: (...args: unknown[]) => getAvailableAdapters(...args),
      addRoomAdapter: (...args: unknown[]) => addRoomAdapter(...args),
      removeRoomAdapter: (...args: unknown[]) => removeRoomAdapter(...args),
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
    supports_discovery: false,
    ...overrides,
  };
}

const baseConfig: RoomConfig = {
  adapter_type: "mock",
  metric_config: {},
  adapter_config: {},
  extra_adapters: [],
};

describe("ExtraAdaptersCard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getAvailableAdapters.mockResolvedValue([adapter({}), adapter({ adapter_type: "aranet4", plugin_name: "Aranet4", category: "bluetooth" })]);
  });

  it("shows a real empty state when the room has no extra sensors", async () => {
    getRoomConfig.mockResolvedValue(baseConfig);
    render(<ExtraAdaptersCard roomId="greenhouse-a" currentOperator={testOperator} />);

    expect(await screen.findByText("No extra sensors on this room yet.")).toBeInTheDocument();
  });

  it("lists existing extra adapters with a remove action", async () => {
    getRoomConfig.mockResolvedValue({
      ...baseConfig,
      extra_adapters: [{ id: 7, adapter_type: "aranet4", adapter_config: { address: "AA:BB" } }],
    });
    render(<ExtraAdaptersCard roomId="greenhouse-a" currentOperator={testOperator} />);

    expect(await screen.findByText("aranet4")).toBeInTheDocument();
    expect(screen.getByText("remove")).toBeInTheDocument();
  });

  it("adds a new extra sensor and refreshes the list", async () => {
    const user = userEvent.setup();
    getRoomConfig.mockResolvedValueOnce(baseConfig);
    addRoomAdapter.mockResolvedValue({ id: 9, adapter_type: "aranet4", adapter_config: {} });
    render(<ExtraAdaptersCard roomId="greenhouse-a" currentOperator={testOperator} />);
    await screen.findByText("No extra sensors on this room yet.");

    await user.click(screen.getByText("+ add sensor"));
    await screen.findByLabelText("sensor adapter");
    await user.selectOptions(screen.getByLabelText("sensor adapter"), "aranet4");

    getRoomConfig.mockResolvedValue({
      ...baseConfig,
      extra_adapters: [{ id: 9, adapter_type: "aranet4", adapter_config: {} }],
    });
    await user.click(screen.getByText("add sensor"));

    await waitFor(() =>
      expect(addRoomAdapter).toHaveBeenCalledWith("greenhouse-a", {
        adapter_type: "aranet4",
        adapter_config: {},
        operator_id: "op-1",
      }),
    );
    expect(await screen.findByText("aranet4")).toBeInTheDocument();
  });

  it("removes an extra sensor after confirmation", async () => {
    const user = userEvent.setup();
    vi.spyOn(window, "confirm").mockReturnValue(true);
    getRoomConfig.mockResolvedValueOnce({
      ...baseConfig,
      extra_adapters: [{ id: 7, adapter_type: "aranet4", adapter_config: {} }],
    });
    removeRoomAdapter.mockResolvedValue({ id: 7, deleted: true });
    render(<ExtraAdaptersCard roomId="greenhouse-a" currentOperator={testOperator} />);
    await screen.findByText("aranet4");

    getRoomConfig.mockResolvedValue(baseConfig);
    await user.click(screen.getByText("remove"));

    await waitFor(() => expect(removeRoomAdapter).toHaveBeenCalledWith("greenhouse-a", 7, "op-1"));
    expect(await screen.findByText("No extra sensors on this room yet.")).toBeInTheDocument();
  });

  it("does not remove when the confirmation is declined", async () => {
    const user = userEvent.setup();
    vi.spyOn(window, "confirm").mockReturnValue(false);
    getRoomConfig.mockResolvedValue({
      ...baseConfig,
      extra_adapters: [{ id: 7, adapter_type: "aranet4", adapter_config: {} }],
    });
    render(<ExtraAdaptersCard roomId="greenhouse-a" currentOperator={testOperator} />);
    await screen.findByText("aranet4");

    await user.click(screen.getByText("remove"));

    expect(removeRoomAdapter).not.toHaveBeenCalled();
  });

  it("shows an error instead of adding when no operator is signed in", async () => {
    const user = userEvent.setup();
    getRoomConfig.mockResolvedValue(baseConfig);
    render(<ExtraAdaptersCard roomId="greenhouse-a" currentOperator={null} />);
    await screen.findByText("No extra sensors on this room yet.");

    await user.click(screen.getByText("+ add sensor"));
    await screen.findByLabelText("sensor adapter");
    await user.click(screen.getByText("add sensor"));

    expect(await screen.findByText(/pick who you are/)).toBeInTheDocument();
    expect(addRoomAdapter).not.toHaveBeenCalled();
  });
});
