import type { Room } from "../types";
import { connectWithReconnect } from "../lib/reconnectingWebSocket";

const MASTER_API_BASE = import.meta.env.VITE_MASTER_API_BASE ?? "http://localhost:9100";
const MASTER_WS_BASE = MASTER_API_BASE.replace(/^http/, "ws");

// Separate from the edge-agent's VITE_API_TOKEN — this is the "master admin" credential
// for the aggregated cross-site view (see canopy_master/auth.py's CANOPY_MASTER_TOKEN).
const MASTER_TOKEN: string | undefined = import.meta.env.VITE_MASTER_API_TOKEN;

function authHeaders(): HeadersInit {
  return MASTER_TOKEN ? { Authorization: `Bearer ${MASTER_TOKEN}` } : {};
}

function withTokenQuery(url: string): string {
  return MASTER_TOKEN ? `${url}?token=${encodeURIComponent(MASTER_TOKEN)}` : url;
}

export interface SiteSummary {
  site_id: string;
  room_count: number;
  online: boolean;
}

export interface MasterRoomUpdateMessage {
  type: "room_update";
  site_id: string;
  room: Room;
}

export interface RelayedAuditEntry {
  id: number;
  site_id: string;
  origin_device_id: string;
  origin_entry_id: number;
  entity_type: string;
  entity_id: string;
  action: string;
  actor: string;
  room_id: string | null;
  details: Record<string, unknown>;
  occurred_at: string;
  entry_hash: string;
  received_at: string;
}

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${MASTER_API_BASE}${path}`, { headers: authHeaders() });
  if (!res.ok) throw new Error(`${path} -> ${res.status}`);
  return res.json() as Promise<T>;
}

export const masterApi = {
  getSites: () => getJson<SiteSummary[]>("/api/sites"),
  getSiteRooms: (siteId: string) => getJson<Room[]>(`/api/sites/${siteId}/rooms`),
  getAuditLog: (siteId?: string, limit = 100) =>
    getJson<RelayedAuditEntry[]>(`/api/audit-log?limit=${limit}${siteId ? `&site_id=${encodeURIComponent(siteId)}` : ""}`),
};

export function connectMasterLiveUpdates(
  onMessage: (msg: MasterRoomUpdateMessage) => void,
  onStatusChange?: (connected: boolean) => void,
): () => void {
  return connectWithReconnect<MasterRoomUpdateMessage>(() => withTokenQuery(`${MASTER_WS_BASE}/ws/live`), {
    onMessage: (msg) => {
      if (msg.type === "room_update") onMessage(msg);
    },
    onStatusChange,
  });
}
