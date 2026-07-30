import type { ReadingPoint, ReadingUpdateMessage, Room } from "../types";
import { authHeaders, withTokenQuery } from "./authToken";
import { formatErrorDetail } from "./errors";
import { connectWithReconnect } from "../lib/reconnectingWebSocket";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";
const WS_BASE = API_BASE.replace(/^http/, "ws");

export class ApiError extends Error {
  status: number;

  constructor(status: number, path: string, detail?: string) {
    super(detail ?? `${path} -> ${status}`);
    this.status = status;
  }
}

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { headers: authHeaders() });
  if (!res.ok) throw new ApiError(res.status, path);
  return res.json() as Promise<T>;
}

async function sendJson<T>(method: "POST" | "PUT" | "DELETE", path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new ApiError(res.status, path, formatErrorDetail(detail.detail, `${path} -> ${res.status}`));
  }
  return res.json() as Promise<T>;
}

export interface AdapterInfo {
  adapter_type: string;
  plugin_name: string;
  plugin_description: string;
  config_schema: Record<string, string>;
  required_env_vars: Record<string, string>;
}

export interface CreateFacilityBody {
  title?: string;
  subtitle?: string;
  badge?: string;
  footnote?: string;
  section?: string;
}

export interface CreateRoomBody {
  id: string;
  room_type: string;
  title?: string;
  subtitle?: string;
  badge?: string;
  footnote?: string;
  section?: string | null;
  sort_order?: number;
  metric_config?: Record<string, unknown>;
  adapter_type?: string;
  adapter_config?: Record<string, unknown>;
}

export type UpdateRoomBody = Partial<CreateRoomBody>;

export interface RoomConfig {
  adapter_type: string;
  metric_config: Record<string, unknown>;
  adapter_config: Record<string, unknown>;
}

// Deliberately loose: AlwaysUnlockedGate and CanopyLicenseGate return differently
// shaped status dicts (e.g. features_unlocked is a bare string "all" on the former,
// a string array on the latter) — see canopy_agent/licensing/*_gate.py. Only `tier`
// and `gate` are guaranteed present across every gate implementation.
export interface LicenseStatus {
  tier: string;
  gate: string;
  features_unlocked: string | string[];
  [key: string]: unknown;
}

export interface BackupEntry {
  filename: string;
  size_bytes: number;
  created_at: string;
}

export interface BackupStatus {
  count: number;
  latest: BackupEntry | null;
  backups: BackupEntry[];
}

export const api = {
  getFacility: () => getJson<Room>("/api/facility"),
  createFacility: (body: CreateFacilityBody) => sendJson<Room>("POST", "/api/facility", body),
  getRooms: () => getJson<Room[]>("/api/rooms"),
  getRoom: (id: string) => getJson<Room>(`/api/rooms/${id}`),
  getRoomConfig: (id: string) => getJson<RoomConfig>(`/api/rooms/${id}/config`),
  getRoomReadings: (id: string, metric?: string) =>
    getJson<ReadingPoint[]>(`/api/rooms/${id}/readings${metric ? `?metric=${metric}` : ""}`),
  createRoom: (body: CreateRoomBody) => sendJson<Room>("POST", "/api/rooms", body),
  updateRoom: (id: string, body: UpdateRoomBody) => sendJson<Room>("PUT", `/api/rooms/${id}`, body),
  deleteRoom: (id: string) => sendJson<{ id: string; deleted: boolean }>("DELETE", `/api/rooms/${id}`),
  getAvailableAdapters: () => getJson<AdapterInfo[]>("/api/rooms/adapters/available"),
  getLicenseStatus: () => getJson<LicenseStatus>("/api/license/status"),
  getBackupStatus: () => getJson<BackupStatus>("/api/backup/status"),
  runBackupNow: () => sendJson<BackupEntry>("POST", "/api/backup/run"),
};

export function connectLiveUpdates(
  onMessage: (msg: ReadingUpdateMessage) => void,
  onStatusChange?: (connected: boolean) => void,
): () => void {
  return connectWithReconnect<ReadingUpdateMessage>(() => withTokenQuery(`${WS_BASE}/ws/live`), {
    onMessage: (msg) => {
      if (msg.type === "reading_update") onMessage(msg);
    },
    onStatusChange,
  });
}
