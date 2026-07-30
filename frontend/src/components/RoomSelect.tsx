import { roomLabel } from "../lib/roomLabel";
import type { Room } from "../types";

export function RoomSelect({
  rooms,
  value,
  onChange,
  allowNone,
}: {
  rooms: Room[];
  value: string;
  onChange: (id: string) => void;
  allowNone?: string;
}) {
  return (
    <select value={value} onChange={(e) => onChange(e.target.value)}>
      <option value="">{allowNone ?? "select a room…"}</option>
      {rooms.map((room) => (
        <option key={room.id} value={room.id}>
          {roomLabel(rooms, room.id)}
        </option>
      ))}
    </select>
  );
}
