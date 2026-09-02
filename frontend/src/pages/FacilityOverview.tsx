import { Fragment, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError, connectLiveUpdates } from "../api/client";
import { complianceApi } from "../api/complianceClient";
import { AddRoomForm } from "../components/AddRoomForm";
import { EntityCard } from "../components/EntityCard";
import { FacilitySummary } from "../components/FacilitySummary";
import { LiveConnectionNotice } from "../components/LiveConnectionNotice";
import { OnboardingWizard } from "../components/OnboardingWizard";
import { OperatorPicker } from "../components/OperatorPicker";
import { TopNav } from "../components/TopNav";
import { useCurrentOperator } from "../hooks/useCurrentOperator";
import type { Room } from "../types";

interface Section {
  label: string;
  rooms: Room[];
}

function groupBySection(rooms: Room[]): Section[] {
  const sections: Section[] = [];
  for (const room of rooms) {
    const label = room.section ?? "other";
    const current = sections[sections.length - 1];
    if (current && current.label === label) {
      current.rooms.push(room);
    } else {
      sections.push({ label, rooms: [room] });
    }
  }
  return sections;
}

export function FacilityOverview() {
  const [facility, setFacility] = useState<Room | null>(null);
  const [rooms, setRooms] = useState<Room[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [notSetUp, setNotSetUp] = useState(false);
  const [liveConnected, setLiveConnected] = useState(true);
  const [jurisdictionSet, setJurisdictionSet] = useState(true); // optimistic until loaded — avoids a flash of the nudge
  const {
    operators,
    currentOperatorId,
    currentOperator,
    changeCurrentOperator,
    handleOperatorCreated,
    handleOperatorUpdated,
    handleOperatorDeactivated,
  } = useCurrentOperator();

  const load = () => {
    Promise.all([api.getFacility(), api.getRooms()])
      .then(([facilityData, roomsData]) => {
        setFacility(facilityData);
        setRooms(roomsData);
        setNotSetUp(false);
      })
      .catch((err) => {
        if (err instanceof ApiError && err.status === 404) {
          setNotSetUp(true);
        } else {
          setError(String(err));
        }
      });
  };

  useEffect(load, []);

  useEffect(() => {
    complianceApi.getStateRules().then((r) => setJurisdictionSet(r.explicitly_set));
  }, []);

  useEffect(() => {
    const disconnect = connectLiveUpdates((msg) => {
      setRooms((prev) => prev.map((room) => (room.id === msg.room_id ? { ...room, stats: msg.stats } : room)));
    }, setLiveConnected);
    return disconnect;
  }, []);

  if (error) return <div className="page-status">Failed to load: {error}</div>;
  if (notSetUp) {
    return (
      <div className="page">
        <TopNav />
        <div className="section-label">Get started</div>
        <OnboardingWizard onFinished={load} />
      </div>
    );
  }
  if (!facility) return <div className="page-status">Loading…</div>;

  const sections = groupBySection(rooms);

  return (
    <div className="page">
      <TopNav />
      <LiveConnectionNotice connected={liveConnected} />
      {(operators.length === 0 || !jurisdictionSet) && (
        <p className="card-footnote" role="note" style={{ margin: "0 0 16px" }}>
          Still finishing setup?
          {operators.length === 0 && " Register yourself as an operator below so actions can be attributed to you."}
          {operators.length === 0 && !jurisdictionSet && " "}
          {!jurisdictionSet && (
            <>
              Set your compliance jurisdiction on the <Link to="/compliance">Compliance</Link> page if you're a
              licensed commercial grower.
            </>
          )}
        </p>
      )}

      <div className="section-label">{facility.section ?? "The facility"}</div>
      <FacilitySummary facility={facility} />

      {sections.map((section) => (
        <Fragment key={section.label}>
          <div className="section-label">{section.label}</div>
          <div className="room-grid">
            {section.rooms.map((room) => (
              <Link key={room.id} to={`/rooms/${room.id}`} className="link-card">
                <EntityCard room={room} />
              </Link>
            ))}
          </div>
        </Fragment>
      ))}

      <div className="section-label">Add a room</div>
      <OperatorPicker
        operators={operators}
        currentOperatorId={currentOperatorId}
        onChange={changeCurrentOperator}
        onOperatorCreated={handleOperatorCreated}
        onOperatorUpdated={handleOperatorUpdated}
        onOperatorDeactivated={handleOperatorDeactivated}
      />
      <AddRoomForm currentOperator={currentOperator} onCreated={load} />
    </div>
  );
}
