import { Fragment, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { connectMasterLiveUpdates, masterApi } from "../api/masterClient";
import { EntityCard } from "../components/EntityCard";
import { TopNav } from "../components/TopNav";
import type { Room } from "../types";

function errorMessage(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}

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

export function MasterSiteRooms() {
  const { siteId } = useParams<{ siteId: string }>();
  const [rooms, setRooms] = useState<Room[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!siteId) return;
    masterApi
      .getSiteRooms(siteId)
      .then(setRooms)
      .catch((err) => setError(errorMessage(err)));
  }, [siteId]);

  useEffect(() => {
    if (!siteId) return;
    const disconnect = connectMasterLiveUpdates((msg) => {
      if (msg.site_id !== siteId) return;
      setRooms((prev) => {
        if (!prev) return prev;
        const exists = prev.some((r) => r.id === msg.room.id);
        return exists ? prev.map((r) => (r.id === msg.room.id ? msg.room : r)) : [...prev, msg.room];
      });
    });
    return disconnect;
  }, [siteId]);

  if (error) return <div className="page-status">Failed to load site: {error}</div>;
  if (!rooms) return <div className="page-status">Loading…</div>;

  const sections = groupBySection(rooms);

  return (
    <div className="page">
      <TopNav />
      <Link to="/master" className="back-link">
        ← Back to sites
      </Link>
      {sections.map((section) => (
        <Fragment key={section.label}>
          <div className="section-label">{section.label}</div>
          <div className="room-grid">
            {section.rooms.map((room) => (
              <EntityCard key={room.id} room={room} />
            ))}
          </div>
        </Fragment>
      ))}
    </div>
  );
}
