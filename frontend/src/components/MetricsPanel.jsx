import { StatTile, formatRs } from "./ui.jsx";

const CAUSE_ORDER = ["soft", "hard", "abandoned", "halted"];
const CAUSE_COLOR = { soft: "var(--cat-1)", hard: "var(--cat-2)", abandoned: "var(--cat-3)", halted: "var(--cat-4)" };

function ByCauseBar({ byCause }) {
  const maxValue = Math.max(1, ...Object.values(byCause).map((c) => c.value));
  return (
    <div className="by-cause">
      {CAUSE_ORDER.filter((k) => byCause[k]).map((k) => {
        const c = byCause[k];
        const pct = Math.max(4, Math.round((c.value / maxValue) * 100));
        return (
          <div key={k} className="by-cause__row">
            <span className="by-cause__label">{k}</span>
            <div className="by-cause__track">
              <div className="by-cause__fill" style={{ width: `${pct}%`, background: CAUSE_COLOR[k] }} />
            </div>
            <span className="by-cause__value mono">
              {c.count} · {formatRs(c.value)}
            </span>
          </div>
        );
      })}
    </div>
  );
}

export default function MetricsPanel({ metrics }) {
  if (!metrics) {
    return (
      <section className="panel metrics-panel" aria-label="Metrics">
        <div className="panel__empty">Loading metrics…</div>
      </section>
    );
  }

  return (
    <section className="panel metrics-panel" aria-label="Metrics">
      <div className="panel__head">
        <h2>Metrics</h2>
      </div>

      {/*
        Recovered vs actioned: TWO physically separate cards, no combined
        total anywhere on this panel. That is the enforcement mechanism —
        the numbers cannot be summed because nothing here ever adds them.
      */}
      <div className="stat-stack">
        <StatTile
          tone="good"
          label="Recovered (customer paid)"
          value={formatRs(metrics.recovered_value)}
          sublabel={`${metrics.recovery_rate_pct}% of at-risk value`}
        />
        <StatTile
          tone="info"
          label="At-risk actioned (links pending)"
          value={formatRs(metrics.at_risk_actioned)}
          sublabel={`${metrics.at_risk_actioned_pct}% of at-risk value`}
          caption="— not yet paid"
        />
      </div>

      <div className="stat-row">
        <StatTile tone="neutral" label="Diagnoser precision" value={`${metrics.diagnoser_precision_pct}%`} />
        <StatTile tone="warning" label="False-positive cost" value={metrics.wrong_actions_false_positive} />
      </div>

      <div className="panel__subhead">Recovery by root cause</div>
      <ByCauseBar byCause={metrics.by_cause} />

      <div className="stat-row stat-row--tight">
        <StatTile tone="neutral" label="Blocked debit → link" value={metrics.escalated_to_link} />
        <StatTile tone="neutral" label="Failed retry → link" value={metrics.retry_failed_to_link} />
      </div>
      <div className="stat-row stat-row--tight">
        <StatTile tone="good" label="Nudges sent" value={metrics.nudges_sent} />
        <StatTile tone="warning" label="Nudges suppressed" value={metrics.nudges_suppressed} />
      </div>
    </section>
  );
}
