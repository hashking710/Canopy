import { useState } from "react";
import { complianceApi } from "../api/complianceClient";
import { useSubmitState } from "../hooks/useSubmitState";
import type { NotificationPreferences, NotificationSeverity, Operator, OperatorRole } from "../api/complianceTypes";

const ROLE_OPTIONS: OperatorRole[] = ["viewer", "operator", "admin"];
const SEVERITY_OPTIONS: NotificationSeverity[] = ["warning", "critical"];

// A suggestion only — the backend stores whatever's submitted with no server-side
// role-based defaulting (see routers/operators.py's CreateOperatorRequest). Lets
// "+ add operator" pre-fill something sensible instead of forcing every new
// operator to think through notification prefs from a blank slate, while staying
// fully editable before saving.
function suggestedNotificationDefaults(role: OperatorRole): NotificationPreferences {
  if (role === "admin") {
    return { notify_email: null, notify_on_alerts: true, notify_on_system_errors: true, notify_min_severity: "warning" };
  }
  if (role === "operator") {
    return { notify_email: null, notify_on_alerts: true, notify_on_system_errors: false, notify_min_severity: "critical" };
  }
  return { notify_email: null, notify_on_alerts: false, notify_on_system_errors: false, notify_min_severity: "critical" };
}

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
  const [editingNotifications, setEditingNotifications] = useState(false);
  const [notifyEmail, setNotifyEmail] = useState(operator.notify_email ?? "");
  const [notifyOnAlerts, setNotifyOnAlerts] = useState(operator.notify_on_alerts);
  const [notifyOnSystemErrors, setNotifyOnSystemErrors] = useState(operator.notify_on_system_errors);
  const [notifyMinSeverity, setNotifyMinSeverity] = useState<NotificationSeverity>(operator.notify_min_severity);
  const { submitting, error, run } = useSubmitState();

  const saveNotificationPreferences = () =>
    run(async () => {
      const updated = await complianceApi.updateNotificationPreferences(operator.id, {
        notify_email: notifyEmail || null,
        notify_on_alerts: notifyOnAlerts,
        notify_on_system_errors: notifyOnSystemErrors,
        notify_min_severity: notifyMinSeverity,
      });
      onUpdated(updated as Operator);
      setEditingNotifications(false);
    });

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
      {editingNotifications ? (
        <div className="operator-add-form">
          <input
            value={notifyEmail}
            onChange={(e) => setNotifyEmail(e.target.value)}
            placeholder="email for personal notifications"
            type="email"
          />
          <label className="checkbox-label">
            <input type="checkbox" checked={notifyOnAlerts} onChange={(e) => setNotifyOnAlerts(e.target.checked)} />
            room alerts
          </label>
          {notifyOnAlerts && (
            <select value={notifyMinSeverity} onChange={(e) => setNotifyMinSeverity(e.target.value as NotificationSeverity)}>
              {SEVERITY_OPTIONS.map((s) => (
                <option key={s} value={s}>
                  min severity: {s}
                </option>
              ))}
            </select>
          )}
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={notifyOnSystemErrors}
              onChange={(e) => setNotifyOnSystemErrors(e.target.checked)}
            />
            system errors
          </label>
          <button className="inline-button" onClick={saveNotificationPreferences} disabled={submitting}>
            {submitting ? "saving…" : "save"}
          </button>
          <button className="inline-button" onClick={() => setEditingNotifications(false)}>
            cancel
          </button>
        </div>
      ) : changingRole ? (
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
          <button className="inline-button" onClick={() => setEditingNotifications(true)}>
            notifications
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
  const [notifyPrefs, setNotifyPrefs] = useState<NotificationPreferences>(suggestedNotificationDefaults("operator"));
  const { submitting, error, run } = useSubmitState();

  const currentOperator = operators.find((o) => o.id === currentOperatorId) ?? null;

  // Re-suggests notification defaults for the newly picked role — a suggestion the
  // operator can still freely edit below before saving, not a locked-in rule (see
  // suggestedNotificationDefaults's own comment).
  const changeRoleForNewOperator = (nextRole: OperatorRole) => {
    setRole(nextRole);
    setNotifyPrefs(suggestedNotificationDefaults(nextRole));
  };

  const submit = () =>
    run(async () => {
      const created = await complianceApi.createOperator({
        name, pin: pin || undefined, role,
        notify_email: notifyPrefs.notify_email || null,
        notify_on_alerts: notifyPrefs.notify_on_alerts,
        notify_on_system_errors: notifyPrefs.notify_on_system_errors,
        notify_min_severity: notifyPrefs.notify_min_severity,
      });
      onOperatorCreated(created);
      setName("");
      setPin("");
      setRole("operator");
      setNotifyPrefs(suggestedNotificationDefaults("operator"));
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
          <select value={role} onChange={(e) => changeRoleForNewOperator(e.target.value as OperatorRole)}>
            {ROLE_OPTIONS.map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </select>
          <input
            value={notifyPrefs.notify_email ?? ""}
            onChange={(e) => setNotifyPrefs({ ...notifyPrefs, notify_email: e.target.value })}
            placeholder="notification email (optional)"
            type="email"
          />
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={notifyPrefs.notify_on_alerts}
              onChange={(e) => setNotifyPrefs({ ...notifyPrefs, notify_on_alerts: e.target.checked })}
            />
            room alerts
          </label>
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={notifyPrefs.notify_on_system_errors}
              onChange={(e) => setNotifyPrefs({ ...notifyPrefs, notify_on_system_errors: e.target.checked })}
            />
            system errors
          </label>
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
