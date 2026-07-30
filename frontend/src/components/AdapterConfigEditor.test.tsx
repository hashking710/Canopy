import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { AdapterConfigEditor } from "./AdapterConfigEditor";

const MODBUS_SCHEMA = {
  host: "TCP only: device IP/hostname",
  registers: "list of {metric, address, register_type, data_type, word_order, scale, offset}",
};

describe("AdapterConfigEditor", () => {
  it("renders nothing for an adapter with no config keys (e.g. mock)", () => {
    const { container } = render(<AdapterConfigEditor schema={{}} values={{}} onChange={vi.fn()} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders a plain text input for a scalar config key, using its description as a placeholder", () => {
    render(<AdapterConfigEditor schema={MODBUS_SCHEMA} values={{}} onChange={vi.fn()} />);
    expect(screen.getByPlaceholderText("TCP only: device IP/hostname")).toBeInTheDocument();
  });

  it("renders a labeled textarea for a 'list of ...' config key instead of a text input", () => {
    render(<AdapterConfigEditor schema={MODBUS_SCHEMA} values={{}} onChange={vi.fn()} />);
    expect(screen.getByText(/registers —/)).toBeInTheDocument();
    expect(screen.queryByPlaceholderText(MODBUS_SCHEMA.registers)).not.toBeInTheDocument();
  });

  it("reports an updated value for the changed key only", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<AdapterConfigEditor schema={MODBUS_SCHEMA} values={{ host: "" }} onChange={onChange} />);

    await user.type(screen.getByPlaceholderText("TCP only: device IP/hostname"), "1");
    expect(onChange).toHaveBeenLastCalledWith({ host: "1" });
  });
});
