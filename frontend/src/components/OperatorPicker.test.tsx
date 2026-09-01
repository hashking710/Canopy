import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { OperatorPicker } from "./OperatorPicker";
import type { Operator } from "../api/complianceTypes";

const { resetOperatorPin, deactivateOperator, createOperator, setOperatorRole } = vi.hoisted(() => ({
  resetOperatorPin: vi.fn(),
  deactivateOperator: vi.fn(),
  createOperator: vi.fn(),
  setOperatorRole: vi.fn(),
}));

vi.mock("../api/complianceClient", () => ({
  complianceApi: {
    resetOperatorPin: (...args: unknown[]) => resetOperatorPin(...args),
    deactivateOperator: (...args: unknown[]) => deactivateOperator(...args),
    createOperator: (...args: unknown[]) => createOperator(...args),
    setOperatorRole: (...args: unknown[]) => setOperatorRole(...args),
  },
}));

const notifyPrefsDefaults = {
  notify_email: null, notify_on_alerts: false, notify_on_system_errors: false, notify_min_severity: "critical" as const,
};

const operators: Operator[] = [
  { id: "op-1", name: "Alex Rivera", role: "admin", has_pin: true, ...notifyPrefsDefaults },
  { id: "op-2", name: "Jordan Lee", role: "operator", has_pin: false, ...notifyPrefsDefaults },
];

describe("OperatorPicker", () => {
  it("lists operators with their role and marks who has a PIN", () => {
    render(
      <OperatorPicker
        operators={operators}
        currentOperatorId="op-1"
        onChange={vi.fn()}
        onOperatorCreated={vi.fn()}
      />,
    );
    expect(screen.getByText(/Alex Rivera — admin \(PIN\)/)).toBeInTheDocument();
    expect(screen.getByText(/Jordan Lee — operator/)).toBeInTheDocument();
  });

  it("does not show a manage button when the deactivate/update callbacks aren't provided", () => {
    render(
      <OperatorPicker operators={operators} currentOperatorId="op-1" onChange={vi.fn()} onOperatorCreated={vi.fn()} />,
    );
    expect(screen.queryByText("manage")).not.toBeInTheDocument();
  });

  it("creates a new operator (defaulting to the operator role) and reports it via onOperatorCreated", async () => {
    const user = userEvent.setup();
    createOperator.mockResolvedValue({ id: "op-3", name: "New Tech", role: "operator", has_pin: false });
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

    expect(createOperator).toHaveBeenCalledWith({
      name: "New Tech", pin: undefined, role: "operator",
      notify_email: null, notify_on_alerts: true, notify_on_system_errors: false, notify_min_severity: "critical",
    });
    expect(onOperatorCreated).toHaveBeenCalledWith({ id: "op-3", name: "New Tech", role: "operator", has_pin: false });
  });

  it("resets the current operator's PIN through the manage panel", async () => {
    const user = userEvent.setup();
    resetOperatorPin.mockResolvedValue({ id: "op-1", name: "Alex Rivera", role: "admin", has_pin: true });
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
    expect(onOperatorUpdated).toHaveBeenCalledWith({ id: "op-1", name: "Alex Rivera", role: "admin", has_pin: true });
  });

  it("changes the current operator's role through the manage panel", async () => {
    const user = userEvent.setup();
    setOperatorRole.mockResolvedValue({ id: "op-1", name: "Alex Rivera", role: "viewer", has_pin: true });
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
    await user.click(screen.getByText("change role (admin)"));
    // Alex Rivera has a PIN (see the `operators` fixture) — a role change is
    // PIN-gated the same way secrets/destruction actions are, so the picker must
    // collect and send it, not just the operator's id (see the security-review
    // fix on set_operator_role: an id alone isn't proof of identity).
    await user.type(screen.getByPlaceholderText("your PIN"), "1234");
    await user.click(screen.getByText("viewer"));

    // Self-service: whoever's currently signed in is both the target and the
    // acting operator — the backend itself checks the acting operator holds
    // admin AND presents the correct PIN (see routers/operators.py's
    // set_operator_role).
    expect(setOperatorRole).toHaveBeenCalledWith("op-1", "viewer", "op-1", "1234");
    expect(onOperatorUpdated).toHaveBeenCalledWith({ id: "op-1", name: "Alex Rivera", role: "viewer", has_pin: true });
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
