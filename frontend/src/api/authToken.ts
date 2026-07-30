// Simple shared-secret auth (see edge-agent's canopy_agent/auth.py). Baked in at build
// time via VITE_API_TOKEN — this dashboard is a local-network appliance UI, not a
// multi-user app with logins, so "who can load the page" is the access boundary.
const API_TOKEN: string | undefined = import.meta.env.VITE_API_TOKEN;

export function authHeaders(): HeadersInit {
  return API_TOKEN ? { Authorization: `Bearer ${API_TOKEN}` } : {};
}

export function withTokenQuery(url: string): string {
  return API_TOKEN ? `${url}${url.includes("?") ? "&" : "?"}token=${encodeURIComponent(API_TOKEN)}` : url;
}
