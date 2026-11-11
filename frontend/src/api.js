/*
api.js — thin fetch wrappers over the FastAPI dashboard endpoints.

Sab GET hain, sirf ek exception: runBatch() — wo synthetic 54-txn batch ko
DRY-RUN mein dobara chalata hai (koi paisa nahi hilta, koi message nahi jaata).
Dashboard kabhi koi real money action trigger nahi karta.
*/
// Local dev talks to uvicorn on :8000; in production (Vercel) the API is
// served from the same origin, so relative /api paths are used.
const BASE = import.meta.env.VITE_API_URL ?? (import.meta.env.DEV ? "http://127.0.0.1:8000" : "");

async function getJSON(path) {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `${path} -> HTTP ${res.status}`);
  }
  return res.json();
}

export async function runBatch(demoHour) {
  const res = await fetch(`${BASE}/api/run-batch`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ demo_hour: demoHour }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `run-batch -> HTTP ${res.status}`);
  }
  return res.json();
}

export const fetchMetrics = () => getJSON("/api/metrics");
export const fetchCases = () => getJSON("/api/cases");
export const fetchCase = (txnId) => getJSON(`/api/case/${encodeURIComponent(txnId)}`);
export const fetchPolicyStats = () => getJSON("/api/policy-stats");
export const fetchHealth = () => getJSON("/health");
