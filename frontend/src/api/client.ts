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
  category: string;
  config_schema: Record<string, string>;
  required_env_vars: Record<string, string>;
  default_metric_config: Record<string, unknown>;
  supports_discovery: boolean;
}

export interface DiscoveredDevice {
  address: string;
  name: string | null;
  rssi?: number;
  [key: string]: unknown;
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
  operator_id: string;
}

export type UpdateRoomBody = Partial<CreateRoomBody> & { operator_id: string };

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

export interface SecretInfo {
  key: string;
  description: string;
  is_set: boolean;
  set_via_dashboard: boolean;
}

export interface MenuSyncProvider {
  type: string;
  plugin_name: string;
  plugin_description: string;
}

export interface MenuSyncStatus {
  active_provider: string;
  available_providers: MenuSyncProvider[];
  last_synced_at: string | null;
  last_result: { pushed?: number; skipped?: number } & Record<string, unknown>;
  last_error: string | null;
}

export const api = {
  getFacility: () => getJson<Room>("/api/facility"),
  createFacility: (body: CreateFacilityBody) => sendJson<Room>("POST", "/api/facility", body),
  getRooms: () => getJson<Room[]>("/api/rooms"),
  getRoom: (id: string) => getJson<Room>(`/api/rooms/${id}`),
  getRoomConfig: (id: string) => getJson<RoomConfig>(`/api/rooms/${id}/config`),
  getRoomReadings: (id: string, metric?: string) =>
    getJson<ReadingPoint[]>(`/api/rooms/${id}/readings${metric ? `?metric=${metric}` : ""}`),
  // Room CRUD is role-gated (role >= "operator", see routers/rooms.py) — every
  // call site now needs to know who's signed in.
  createRoom: (body: CreateRoomBody) => sendJson<Room>("POST", "/api/rooms", body),
  updateRoom: (id: string, body: UpdateRoomBody) => sendJson<Room>("PUT", `/api/rooms/${id}`, body),
  deleteRoom: (id: string, operatorId: string) =>
    sendJson<{ id: string; deleted: boolean }>(
      "DELETE",
      `/api/rooms/${id}?operator_id=${encodeURIComponent(operatorId)}`,
    ),
  getAvailableAdapters: () => getJson<AdapterInfo[]>("/api/rooms/adapters/available"),
  discoverAdapterDevices: (adapterType: string) =>
    sendJson<DiscoveredDevice[]>("POST", `/api/rooms/adapters/${adapterType}/discover`),
  getLicenseStatus: () => getJson<LicenseStatus>("/api/license/status"),
  getBackupStatus: () => getJson<BackupStatus>("/api/backup/status"),
  runBackupNow: () => sendJson<BackupEntry>("POST", "/api/backup/run"),
  getSecrets: () => getJson<SecretInfo[]>("/api/secrets"),
  // Credentials are facility-settings-tier sensitive — routers/secrets.py requires
  // an operator with role >= admin (and their PIN, if they have one) to set or
  // clear one, same as canopy_agent's other role-gated actions.
  setSecret: (key: string, value: string, operatorId: string, pin?: string) =>
    sendJson<{ key: string; is_set: boolean }>("PUT", `/api/secrets/${key}`, { value, operator_id: operatorId, pin }),
  clearSecret: (key: string, operatorId: string, pin?: string) =>
    sendJson<{ key: string; is_set: boolean }>("DELETE", `/api/secrets/${key}`, { operator_id: operatorId, pin }),
  getMenuSyncStatus: () => getJson<MenuSyncStatus>("/api/menu-sync/status"),
  // Menu sync is role-gated (role >= "operator", see routers/menu_sync.py).
  runMenuSyncNow: (operatorId: string) =>
    sendJson<{ pushed: number; skipped: number }>(
      "POST",
      `/api/menu-sync/run?operator_id=${encodeURIComponent(operatorId)}`,
    ),
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
