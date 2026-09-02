import { useEffect, useState } from "react";
import { api } from "../api/client";
import { complianceApi } from "../api/complianceClient";
import type { StateComplianceRules } from "../api/complianceTypes";
import { AddRoomForm } from "./AddRoomForm";
import { Card } from "./Card";
import { OperatorPicker } from "./OperatorPicker";
import { useCurrentOperator } from "../hooks/useCurrentOperator";
import { useSubmitState } from "../hooks/useSubmitState";
import type { Room } from "../types";

type Step = "facility" | "operator" | "jurisdiction" | "room" | "license" | "done";

// The guided first-run flow: create a facility, register yourself, pick your
// compliance jurisdiction, add your first room. Every step reuses the real,
// already-built form/API for that action (AddRoomForm, OperatorPicker, the same
// state-rules call the Compliance page uses) — this component is purely about
// sequencing and gating those existing pieces into one flow for a brand-new
// install, not a reimplementation of any of them.
function FacilityStep({ onCreated }: { onCreated: (facility: Room) => void }) {
  const [title, setTitle] = useState("");
  const [section, setSection] = useState("the facility");
  const { submitting, error, run } = useSubmitState();

  const submit = () =>
    run(async () => {
      const facility = await api.createFacility({ title, section });
      onCreated(facility);
    });

  return (
    <Card>
      <p className="card-subtitle">Step 1 of 4 — Welcome to Canopy</p>
      <h3 className="card-title">Set up your facility</h3>
      <p className="stat-label" style={{ margin: "8px 0 16px" }}>
        One Pi, one or two tents? This is all you need. Running multiple Pis across
        several sites instead? See the "Which setup do I need?" section in the
        project README for the optional multi-site control panel — nothing below
        changes either way.
      </p>
      <div className="quick-form">
        <label>
          facility name
          <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Ridgeline Cultivation" />
        </label>
        <label>
          section label
          <input value={section} onChange={(e) => setSection(e.target.value)} />
        </label>
        <button disabled={submitting || !title} onClick={submit}>
          {submitting ? "creating…" : "create facility"}
        </button>
      </div>
      {error && <p className="form-error" role="alert">{error}</p>}
    </Card>
  );
}

function JurisdictionStep({ onDone, onSkip }: { onDone: () => void; onSkip: () => void }) {
  const [stateCode, setStateCode] = useState("");
  const [available, setAvailable] = useState<StateComplianceRules[]>([]);
  const [loaded, setLoaded] = useState(false);
  const {
    operators,
    currentOperatorId,
    currentOperator,
    changeCurrentOperator,
    handleOperatorCreated,
    handleOperatorUpdated,
    handleOperatorDeactivated,
  } = useCurrentOperator();
  const { submitting, error, run } = useSubmitState();

  useEffect(() => {
    complianceApi.getStateRules().then((r) => {
      setAvailable(r.available);
      setLoaded(true);
    });
  }, []);

  const submit = () =>
    run(async () => {
      if (!currentOperator || !stateCode) return;
      await complianceApi.setStateRules({ state_code: stateCode, operator_id: currentOperator.id });
      onDone();
    });

  return (
    <Card>
      <p className="card-subtitle">Step 3 of 4 (optional)</p>
      <h3 className="card-title">What state are you licensed in?</h3>
      <p className="stat-label" style={{ margin: "8px 0 16px" }}>
        Sets which state's waste-reporting deadlines, testing requirements, and
        purchase limits the Compliance page computes from. Only matters for licensed
        commercial cultivation — skip this if you're a home/medical grower.
      </p>
      <OperatorPicker
        operators={operators}
        currentOperatorId={currentOperatorId}
        onChange={changeCurrentOperator}
        onOperatorCreated={handleOperatorCreated}
        onOperatorUpdated={handleOperatorUpdated}
        onOperatorDeactivated={handleOperatorDeactivated}
      />
      <div className="quick-form" style={{ marginTop: 12 }}>
        <label>
          jurisdiction
          <select value={stateCode} onChange={(e) => setStateCode(e.target.value)} disabled={!loaded}>
            <option value="">select a state…</option>
            {available.map((s) => (
              <option key={s.state_code} value={s.state_code}>
                {s.state_name}
              </option>
            ))}
          </select>
        </label>
        <button disabled={submitting || !currentOperator || !stateCode} onClick={submit}>
          {submitting ? "saving…" : "set jurisdiction"}
        </button>
        <button className="inline-button" onClick={onSkip}>
          skip for now
        </button>
      </div>
      {error && <p className="form-error" role="alert">{error}</p>}
    </Card>
  );
}

function RoomStep({ onDone, onSkip }: { onDone: () => void; onSkip: () => void }) {
  const { currentOperator } = useCurrentOperator();

  return (
    <Card>
      <p className="card-subtitle">Step 4 of 4</p>
      <h3 className="card-title">Add your first room</h3>
      <p className="stat-label" style={{ margin: "8px 0 16px" }}>
        A room can be as simple as a single tent with one sensor, or a full
        greenhouse bay — you can always add more, edit, or remove rooms later.
      </p>
      <AddRoomForm currentOperator={currentOperator} onCreated={onDone} />
      <button className="inline-button" style={{ marginTop: 12 }} onClick={onSkip}>
        I'll add a room later
      </button>
    </Card>
  );
}

// Not a numbered step (unlike the four required/skippable ones above) — a brief
// nudge shown exactly once, after setup, rather than a gate anything else depends
// on. Same pitch and same link as the License page's own "unlicensed" card;
// duplicated intentionally rather than shared, since the two live in genuinely
// different contexts (a first-run wizard vs. a settled dashboard) and diverging
// later shouldn't require untangling a shared component.
function LicenseStep({ onDone }: { onDone: () => void }) {
  return (
    <Card>
      <p className="card-subtitle">You're set up</p>
      <h3 className="card-title">One last thing — get a free license</h3>
      <p className="stat-label" style={{ margin: "8px 0 16px" }}>
        Nothing in Canopy is gated — everything you just set up works with no
        license at all. Registering a free license (two devices, no card required)
        is still worth doing: it gives this installation a real customer record,
        and if you ever add a third device, upgrading later is a one-file swap
        instead of a fresh setup.
      </p>
      <div className="quick-form">
        <a
          href="https://canopy.hkdev.run/checkout"
          target="_blank"
          rel="noreferrer"
          className="inline-button"
        >
          Get a free license →
        </a>
        <button onClick={onDone}>go to dashboard</button>
      </div>
    </Card>
  );
}

export function OnboardingWizard({ onFinished }: { onFinished: () => void }) {
  const [step, setStep] = useState<Step>("facility");

  if (step === "facility") {
    return <FacilityStep onCreated={() => setStep("operator")} />;
  }

  if (step === "operator") {
    return (
      <Card>
        <p className="card-subtitle">Step 2 of 4</p>
        <h3 className="card-title">Register yourself as an operator</h3>
        <p className="stat-label" style={{ margin: "8px 0 16px" }}>
          Attributes every action you take to a real name instead of "anonymous" —
          the first operator you register is always given the admin role, so you
          can manage everything else from here. You can add more operators (and
          PINs, roles, notification preferences) any time from the picker on any
          page.
        </p>
        <OperatorPickerStep onDone={() => setStep("jurisdiction")} />
      </Card>
    );
  }

  if (step === "jurisdiction") {
    return <JurisdictionStep onDone={() => setStep("room")} onSkip={() => setStep("room")} />;
  }

  if (step === "room") {
    return <RoomStep onDone={() => setStep("license")} onSkip={() => setStep("license")} />;
  }

  if (step === "license") {
    return <LicenseStep onDone={onFinished} />;
  }

  return null;
}

// A thin wrapper so the "register yourself" step can detect the moment an operator
// gets created and advance automatically, without duplicating OperatorPicker's own
// create-operator form.
function OperatorPickerStep({ onDone }: { onDone: () => void }) {
  const {
    operators,
    currentOperatorId,
    changeCurrentOperator,
    handleOperatorCreated,
    handleOperatorUpdated,
    handleOperatorDeactivated,
  } = useCurrentOperator();

  return (
    <>
      <OperatorPicker
        operators={operators}
        currentOperatorId={currentOperatorId}
        onChange={changeCurrentOperator}
        onOperatorCreated={(operator) => {
          handleOperatorCreated(operator);
          onDone();
        }}
        onOperatorUpdated={handleOperatorUpdated}
        onOperatorDeactivated={handleOperatorDeactivated}
      />
      {operators.length > 0 && (
        <button className="inline-button" style={{ marginTop: 12 }} onClick={onDone}>
          continue
        </button>
      )}
    </>
  );
}
