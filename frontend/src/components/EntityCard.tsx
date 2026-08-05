import type { Room } from "../types";
import { Badge } from "./Badge";
import { Card } from "./Card";
import { CardHeader } from "./CardHeader";
import { StatGrid } from "./StatGrid";

export function EntityCard({ room }: { room: Room }) {
  return (
    <Card>
      {room.last_poll_error && (
        <div className="sensor-health-warning">
          <Badge text="sensor offline" variant="danger" />
          {/* Shown inline, not just as a hover title — a title-only tooltip is
              invisible on touch devices, and this is exactly the kind of message
              (e.g. "requires CANOPY_GOVEE_API_KEY to be set") a non-technical user
              needs to actually see to fix it. */}
          <p className="sensor-health-detail">{room.last_poll_error}</p>
        </div>
      )}
      <CardHeader subtitle={room.subtitle} title={room.title} badge={room.badge} />
      <StatGrid stats={room.stats} />
      {room.footnote && <p className="card-footnote">{room.footnote}</p>}
    </Card>
  );
}
