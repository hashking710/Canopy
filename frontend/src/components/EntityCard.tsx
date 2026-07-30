import type { Room } from "../types";
import { Badge } from "./Badge";
import { Card } from "./Card";
import { CardHeader } from "./CardHeader";
import { StatGrid } from "./StatGrid";

export function EntityCard({ room }: { room: Room }) {
  return (
    <Card>
      {room.last_poll_error && (
        <div className="sensor-health-warning" title={room.last_poll_error}>
          <Badge text="sensor offline" variant="danger" />
        </div>
      )}
      <CardHeader subtitle={room.subtitle} title={room.title} badge={room.badge} />
      <StatGrid stats={room.stats} />
      {room.footnote && <p className="card-footnote">{room.footnote}</p>}
    </Card>
  );
}
