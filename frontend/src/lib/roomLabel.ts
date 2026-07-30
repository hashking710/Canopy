import type { Room } from "../types";

// Some rooms (e.g. generic infrastructure like a vault or tissue-culture area with no
// single active named crop) legitimately have an empty `title` — falls through to
// `subtitle`, then the raw id, rather than rendering blank. `||` (not `??`) is
// deliberate: an empty string must fall through too, not just null/undefined.
export function roomLabel(rooms: Room[], roomId: string | null | undefined): string {
  if (!roomId) return "—";
  const room = rooms.find((r) => r.id === roomId);
  return room?.title || room?.subtitle || roomId;
}
