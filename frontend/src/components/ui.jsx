/*
ui.jsx — chhote, reusable pieces. Koi business logic nahi, sirf presentation.
*/

export function StatusDot({ status }) {
  return <span className={`status-dot status-dot--${status}`} aria-hidden="true" />;
}

export function Badge({ tone = "neutral", children }) {
  return <span className={`badge badge--${tone}`}>{children}</span>;
}

/* value + label ka contract — dataviz skill: "single current value -> stat tile" */
export function StatTile({ label, value, sublabel, tone = "neutral", caption }) {
  return (
    <div className={`stat-tile stat-tile--${tone}`}>
      <div className="stat-tile__label">{label}</div>
      <div className="stat-tile__value">{value}</div>
      {sublabel && <div className="stat-tile__sublabel">{sublabel}</div>}
      {caption && <div className="stat-tile__caption">{caption}</div>}
    </div>
  );
}

/* sequential magnitude bar — policy fire-counts ke liye (ek hue, more = darker/longer) */
export function MagnitudeBar({ value, max }) {
  const pct = max > 0 ? Math.max(4, Math.round((value / max) * 100)) : 0;
  return (
    <div className="magnitude-bar" role="img" aria-label={`${value} of ${max}`}>
      <div className="magnitude-bar__fill" style={{ width: `${pct}%` }} />
    </div>
  );
}

export function formatRs(amount) {
  if (amount === null || amount === undefined) return "—";
  return `₹${amount.toLocaleString("en-IN")}`;
}

export function outcomeTone(outcome) {
  if (outcome === "recovered") return "good";
  if (outcome === "human_review") return "critical";
  if (outcome === "pending") return "warning";
  return "neutral";
}

export function labelTone(label) {
  const map = { soft: "cat-1", hard: "cat-2", abandoned: "cat-3", halted: "cat-4" };
  return map[label] || "neutral";
}
