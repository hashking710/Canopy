import { useState } from "react";
import { complianceApi } from "../api/complianceClient";
import { useSubmitState } from "../hooks/useSubmitState";
import type { Operator, OperatorRole } from "../api/complianceTypes";

const ROLE_OPTIONS: OperatorRole[] = ["viewer", "operator", "admin"];

function ManageCurrentOperator({
  operator,
  onUpdated,
  onDeactivated,
}: {
  operator: Operator;
  onUpdated: (operator: Operator) => void;
  onDeactivated: (id: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [resettingPin, setResettingPin] = useState(false);
  const [newPin, setNewPin] = useState("");
  const [changingRole, setChangingRole] = useState(false);
  const [rolePin, setRolePin] = useState("");
  const [confirmingDeactivate, setConfirmingDeactivate] = useState(false);
  const { submitting, error, run } = useSubmitState();

  const resetPin = () =>
    run(async () => {
      const updated = await complianceApi.resetOperatorPin(operator.id, newPin || undefined);
      onUpdated(updated as Operator);
      setNewPin("");
      setResettingPin(false);
    });

  const changeRole = (role: OperatorRole) =>
    // Self-service: the change-role endpoint itself checks that whoever is
    // currently signed in (this operator) actually holds admin — a non-admin
    // just gets a clear 403 from useSubmitState's error display, same as any
    // other role-gated action, rather than the picker trying to hide the
    // control and getting that wrong in some edge case. Role changes are
    // PIN-gated the same way secrets/destruction actions are: an id alone isn't
    // proof of identity, so this operator's own PIN (if they have one) is
    // required to grant a role, not just cited by id.
    run(async () => {
      const updated = await complianceApi.setOperatorRole(operator.id, role, operator.id, rolePin || undefined);
      onUpdated(updated as Operator);
      setRolePin("");
      setChangingRole(false);
    });

  const deactivate = () =>
    run(async () => {
      await complianceApi.deactivateOperator(operator.id);
      onDeactivated(operator.id);
    });

  if (!open) {
    return (
      <button className="inline-button" onClick={() => setOpen(true)}>
        manage
      </button>
    );
  }

  return (
    <div className="operator-manage">
      {changingRole ? (
        <div className="operator-add-form">
          {operator.has_pin && (
            <input
              value={rolePin}
              onChange={(e) => setRolePin(e.target.value)}
              placeholder="your PIN"
              type="password"
            />
          )}
          {ROLE_OPTIONS.map((role) => (
            <button
              key={role}
              className="inline-button"
              disabled={submitting || role === operator.role}
              onClick={() => changeRole(role)}
            >
              {role}
              {role === operator.role ? " (current)" : ""}
            </button>
          ))}
          <button className="inline-button" onClick={() => setChangingRole(false)}>
            cancel
          </button>
        </div>
      ) : resettingPin ? (
        <div className="operator-add-form">
          <input
            value={newPin}
            onChange={(e) => setNewPin(e.target.value)}
            placeholder="new PIN (blank to remove)"
            type="password"
          />
          <button className="inline-button" onClick={resetPin} disabled={submitting}>
            {submitting ? "saving…" : "save"}
          </button>
          <button className="inline-button" onClick={() => setResettingPin(false)}>
            cancel
          </button>
        </div>
      ) : confirmingDeactivate ? (
        <div className="operator-add-form">
          <span className="stat-label">Deactivate {operator.name}? They'll no longer appear as a signed-in option.</span>
          <button className="inline-button" onClick={deactivate} disabled={submitting}>
            {submitting ? "deactivating…" : "confirm deactivate"}
          </button>
          <button className="inline-button" onClick={() => setConfirmingDeactivate(false)}>
            cancel
          </button>
        </div>
      ) : (
        <div className="operator-add-form">
          <button className="inline-button" onClick={() => setResettingPin(true)}>
            reset PIN
          </button>
          <button className="inline-button" onClick={() => setChangingRole(true)}>
            change role ({operator.role})
          </button>
          <button className="inline-button" onClick={() => setConfirmingDeactivate(true)}>
            deactivate
          </button>
          <button className="inline-button" onClick={() => setOpen(false)}>
            done
          </button>
        </div>
      )}
      {error && <p className="form-error" role="alert">{error}</p>}
    </div>
  );
}

export function OperatorPicker({
  operators,
  currentOperatorId,
  onChange,
  onOperatorCreated,
  onOperatorUpdated,
  onOperatorDeactivated,
}: {
  operators: Operator[];
  currentOperatorId: string;
  onChange: (id: string) => void;
  onOperatorCreated: (operator: Operator) => void;
  onOperatorUpdated?: (operator: Operator) => void;
  onOperatorDeactivated?: (id: string) => void;
}) {
  const [adding, setAdding] = useState(false);
  const [name, setName] = useState("");
  const [pin, setPin] = useState("");
  const [role, setRole] = useState<OperatorRole>("operator");
  const { submitting, error, run } = useSubmitState();

  const currentOperator = operators.find((o) => o.id === currentOperatorId) ?? null;

  const submit = () =>
    run(async () => {
      const created = await complianceApi.createOperator({ name, pin: pin || undefined, role });
      onOperatorCreated(created);
      setName("");
      setPin("");
      setRole("operator");
      setAdding(false);
    });

  return (
    <div className="operator-picker">
      <label>
        signed in as
        <select value={currentOperatorId} onChange={(e) => onChange(e.target.value)}>
          {operators.length === 0 && <option value="">no operators registered</option>}
          {operators.map((op) => (
            <option key={op.id} value={op.id}>
              {op.name} — {op.role}
              {op.has_pin ? " (PIN)" : ""}
            </option>
          ))}
        </select>
      </label>
      {currentOperator && onOperatorUpdated && onOperatorDeactivated && (
        <ManageCurrentOperator operator={currentOperator} onUpdated={onOperatorUpdated} onDeactivated={onOperatorDeactivated} />
      )}
      {adding ? (
        <div className="operator-add-form">
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="name" />
          <input value={pin} onChange={(e) => setPin(e.target.value)} placeholder="PIN (optional)" type="password" />
          <select value={role} onChange={(e) => setRole(e.target.value as OperatorRole)}>
            {ROLE_OPTIONS.map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </select>
          <button className="inline-button" onClick={submit} disabled={!name || submitting}>
            {submitting ? "saving…" : "save"}
          </button>
          <button className="inline-button" onClick={() => setAdding(false)}>
            cancel
          </button>
        </div>
      ) : (
        <button className="inline-button" onClick={() => setAdding(true)}>
          + add operator
        </button>
      )}
      {error && <p className="form-error" role="alert">{error}</p>}
    </div>
  );
}
