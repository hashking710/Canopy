import { authHeaders } from "./authToken";
import { formatErrorDetail } from "./errors";
import type { AlertEvent, AlertRule } from "./alertsTypes";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { headers: authHeaders() });
  if (!res.ok) throw new Error(`${path} -> ${res.status}`);
  return res.json() as Promise<T>;
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(formatErrorDetail(detail.detail, `${path} -> ${res.status}`));
  }
  return res.json() as Promise<T>;
}

export const alertsApi = {
  getRules: () => getJson<AlertRule[]>("/api/alert-rules"),
  // Alert rule create/delete are role-gated (role >= "operator", see
  // routers/alerts.py) — every call site now needs to know who's signed in.
  createRule: (body: {
    room_id: string;
    metric: string;
    condition: "gt" | "lt";
    threshold: number;
    severity: string;
    operator_id: string;
  }) => postJson<AlertRule>("/api/alert-rules", body),
  deleteRule: async (id: string, operatorId: string) => {
    const res = await fetch(`${API_BASE}/api/alert-rules/${id}?operator_id=${encodeURIComponent(operatorId)}`, {
      method: "DELETE",
      headers: authHeaders(),
    });
    if (!res.ok) {
      const detail = await res.json().catch(() => ({}));
      throw new Error(formatErrorDetail(detail.detail, `delete rule -> ${res.status}`));
    }
  },
  getEvents: (activeOnly = false) => getJson<AlertEvent[]>(`/api/alert-events?active_only=${activeOnly}`),
  acknowledgeEvent: (id: number, operatorId: string) =>
    postJson<AlertEvent>(`/api/alert-events/${id}/acknowledge`, { operator_id: operatorId }),
};
