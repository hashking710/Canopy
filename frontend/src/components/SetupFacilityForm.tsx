import { useState } from "react";
import { api } from "../api/client";
import { useSubmitState } from "../hooks/useSubmitState";
import type { Room } from "../types";

export function SetupFacilityForm({ onCreated }: { onCreated: (facility: Room) => void }) {
  const [title, setTitle] = useState("");
  const [section, setSection] = useState("the facility");
  const { submitting, error, run } = useSubmitState();

  const submit = () =>
    run(async () => {
      const facility = await api.createFacility({ title, section });
      onCreated(facility);
    });

  return (
    <div className="card">
      <div className="card-body">
        <p className="card-subtitle">First-run setup</p>
        <h3 className="card-title">Set up your facility</h3>
        <p className="stat-label" style={{ margin: "8px 0 16px" }}>
          One Pi, one or two tents? This is all you need — just create a facility and
          start adding rooms below. Running multiple Pis across several sites under
          one operator instead? See the "Which setup do I need?" section in the
          project README for the optional multi-site control panel.
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
          <button disabled={submitting} onClick={submit}>
            {submitting ? "creating…" : "create facility"}
          </button>
        </div>
        {error && <p className="form-error" role="alert">{error}</p>}
      </div>
    </div>
  );
}
