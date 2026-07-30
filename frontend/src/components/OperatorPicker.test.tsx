import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { OperatorPicker } from "./OperatorPicker";
import type { Operator } from "../api/complianceTypes";

const { resetOperatorPin, deactivateOperator, createOperator } = vi.hoisted(() => ({
  resetOperatorPin: vi.fn(),
  deactivateOperator: vi.fn(),
  createOperator: vi.fn(),
}));

vi.mock("../api/complianceClient", () => ({
  complianceApi: {
    resetOperatorPin: (...args: unknown[]) => resetOperatorPin(...args),
    deactivateOperator: (...args: unknown[]) => deactivateOperator(...args),
    createOperator: (...args: unknown[]) => createOperator(...args),
  },
}));

const operators: Operator[] = [
  { id: "op-1", name: "Alex Rivera", has_pin: true },
  { id: "op-2", name: "Jordan Lee", has_pin: false },
];

describe("OperatorPicker", () => {
  it("lists operators and marks who has a PIN", () => {
    render(
      <OperatorPicker
        operators={operators}
        currentOperatorId="op-1"
        onChange={vi.fn()}
        onOperatorCreated={vi.fn()}
      />,
    );
    expect(screen.getByText(/Alex Rivera \(PIN\)/)).toBeInTheDocument();
    expect(screen.getByText("Jordan Lee")).toBeInTheDocument();
  });

  it("does not show a manage button when the deactivate/update callbacks aren't provided", () => {
    render(
      <OperatorPicker operators={operators} currentOperatorId="op-1" onChange={vi.fn()} onOperatorCreated={vi.fn()} />,
    );
    expect(screen.queryByText("manage")).not.toBeInTheDocument();
  });

  it("creates a new operator and reports it via onOperatorCreated", async () => {
    const user = userEvent.setup();
    createOperator.mockResolvedValue({ id: "op-3", name: "New Tech", has_pin: false });
    const onOperatorCreated = vi.fn();

    render(
      <OperatorPicker
        operators={operators}
        currentOperatorId="op-1"
        onChange={vi.fn()}
        onOperatorCreated={onOperatorCreated}
      />,
    );

    await user.click(screen.getByText("+ add operator"));
    await user.type(screen.getByPlaceholderText("name"), "New Tech");
    await user.click(screen.getByText("save"));

    expect(createOperator).toHaveBeenCalledWith({ name: "New Tech", pin: undefined });
    expect(onOperatorCreated).toHaveBeenCalledWith({ id: "op-3", name: "New Tech", has_pin: false });
  });

  it("resets the current operator's PIN through the manage panel", async () => {
    const user = userEvent.setup();
    resetOperatorPin.mockResolvedValue({ id: "op-1", name: "Alex Rivera", has_pin: true });
    const onOperatorUpdated = vi.fn();

    render(
      <OperatorPicker
        operators={operators}
        currentOperatorId="op-1"
        onChange={vi.fn()}
        onOperatorCreated={vi.fn()}
        onOperatorUpdated={onOperatorUpdated}
        onOperatorDeactivated={vi.fn()}
      />,
    );

    await user.click(screen.getByText("manage"));
    await user.click(screen.getByText("reset PIN"));
    await user.type(screen.getByPlaceholderText("new PIN (blank to remove)"), "4242");
    await user.click(screen.getByText("save"));

    expect(resetOperatorPin).toHaveBeenCalledWith("op-1", "4242");
    expect(onOperatorUpdated).toHaveBeenCalledWith({ id: "op-1", name: "Alex Rivera", has_pin: true });
  });

  it("requires an explicit confirmation before deactivating an operator", async () => {
    const user = userEvent.setup();
    deactivateOperator.mockResolvedValue({ id: "op-1", name: "Alex Rivera", active: false });
    const onOperatorDeactivated = vi.fn();

    render(
      <OperatorPicker
        operators={operators}
        currentOperatorId="op-1"
        onChange={vi.fn()}
        onOperatorCreated={vi.fn()}
        onOperatorUpdated={vi.fn()}
        onOperatorDeactivated={onOperatorDeactivated}
      />,
    );

    await user.click(screen.getByText("manage"));
    await user.click(screen.getByText("deactivate"));
    // clicking "deactivate" alone must not have deactivated anyone yet
    expect(deactivateOperator).not.toHaveBeenCalled();

    await user.click(screen.getByText("confirm deactivate"));
    expect(deactivateOperator).toHaveBeenCalledWith("op-1");
    expect(onOperatorDeactivated).toHaveBeenCalledWith("op-1");
  });
});
