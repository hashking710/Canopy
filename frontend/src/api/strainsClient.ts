import { authHeaders } from "./authToken";
import { formatErrorDetail } from "./errors";
import type { Strain, StrainType } from "./strainsTypes";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { headers: authHeaders() });
  if (!res.ok) throw new Error(`${path} -> ${res.status}`);
  return res.json() as Promise<T>;
}

async function sendJson<T>(method: "POST" | "PUT", path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(formatErrorDetail(detail.detail, `${path} -> ${res.status}`));
  }
  return res.json() as Promise<T>;
}

export interface StrainFields {
  name: string;
  lineage: string;
  strain_type: StrainType;
  description: string;
  thc_pct_typical: number | null;
  cbd_pct_typical: number | null;
}

export const strainsApi = {
  getStrains: () => getJson<Strain[]>("/api/strains"),
  createStrain: (body: StrainFields & { operator_id: string }) => sendJson<Strain>("POST", "/api/strains", body),
  updateStrain: (id: string, body: Partial<StrainFields> & { operator_id: string }) =>
    sendJson<Strain>("PUT", `/api/strains/${id}`, body),
  deactivateStrain: async (id: string, operatorId: string) => {
    const res = await fetch(`${API_BASE}/api/strains/${id}/deactivate?operator_id=${encodeURIComponent(operatorId)}`, {
      method: "POST",
      headers: authHeaders(),
    });
    if (!res.ok) {
      const detail = await res.json().catch(() => ({}));
      throw new Error(formatErrorDetail(detail.detail, `deactivate strain -> ${res.status}`));
    }
  },
};
