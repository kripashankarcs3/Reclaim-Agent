/*
api.js — thin fetch wrappers over the FastAPI dashboard endpoints.

READ-ONLY: har function ek GET hai. Ye file kabhi POST/PUT/DELETE nahi karti
— dashboard ka poora point hai ki ye sirf DEKHTA hai, kuch badalta nahi.
*/
const BASE = "http://127.0.0.1:8000";

async function getJSON(path) {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `${path} -> HTTP ${res.status}`);
  }
  return res.json();
}

export const fetchMetrics = () => getJSON("/api/metrics");
export const fetchCases = () => getJSON("/api/cases");
export const fetchCase = (txnId) => getJSON(`/api/case/${encodeURIComponent(txnId)}`);
export const fetchPolicyStats = () => getJSON("/api/policy-stats");
export const fetchHealth = () => getJSON("/health");
