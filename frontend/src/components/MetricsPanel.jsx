import { useState } from "react";
import {
  IconWallet, IconCheckCircle, IconClock, IconTarget, IconAlertTriangle, IconZap,
} from "../icons.jsx";
import { StatTile, SectionHeading, formatRs, outcomeTone, labelHuman } from "./ui.jsx";
import { ruleTitle, parseRule } from "../copy.js";

const CAUSE_ORDER = ["soft", "hard", "abandoned", "halted"];
const CAUSE_LABEL = { soft: "Transient", hard: "Hard decline", abandoned: "Abandoned", halted: "Halted" };
const CAUSE_COLOR = { soft: "var(--cat-1)", hard: "var(--cat-2)", abandoned: "var(--cat-3)", halted: "var(--cat-4)" };

const ACTION_ORDER = ["retry", "payment_link", "recovery_link", "human_review"];
const ACTION_LABEL = {
  retry: "Smart retry", payment_link: "Payment link",
  recovery_link: "Recovery link", human_review: "Human review",
};

/* Backend ke DEMO_HOURS se match — ye do hi ghante allowed hain. */
const RUN_HOURS = [
  { hour: 14, label: "2:30 PM", hint: "inside 8 AM–7 PM" },
  { hour: 21, label: "9:30 PM", hint: "outside contact window" },
];

function formatClock(iso) {
  if (!iso) return null;
  return new Date(iso).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" });
}

function BatchControl({ batch, totalTxns, onRun, running, error }) {
  // Jab tak user koi ghanta na chune, server ka last-run ghanta hi dikhao.
  const [picked, setPicked] = useState(null);
  const hour = picked ?? batch?.demo_hour ?? 14;
  const setHour = setPicked;

  const ranAt = formatClock(batch?.ran_at);
  const shownHour = RUN_HOURS.find((h) => h.hour === batch?.demo_hour);

  return (
    <div className="batch-control">
      <div className="batch-control__row">
        <div className="segmented" role="radiogroup" aria-label="Batch run time">
          {RUN_HOURS.map((h) => (
            <button
              key={h.hour}
              type="button"
              role="radio"
              aria-checked={hour === h.hour}
              className={`segmented__opt ${hour === h.hour ? "is-active" : ""}`}
              onClick={() => setHour(h.hour)}
              title={h.hint}
              disabled={running}
            >
              {h.label}
            </button>
          ))}
        </div>
        <button
          type="button"
          className="run-batch-btn"
          onClick={() => onRun(hour)}
          disabled={running}
        >
          <IconZap size={13} />
          {running ? "Running…" : "Run batch"}
        </button>
      </div>
      <div className={`batch-control__status ${error ? "is-error" : ""}`}>
        {error
          ? `Run failed: ${error}`
          : `${totalTxns} synthetic txns at ${shownHour?.label ?? "—"} · `
            + (ranAt ? `last run ${ranAt}` : "default run")
            + " · dry-run, no money moves"}
      </div>
    </div>
  );
}

function ByCauseBar({ byCause }) {
  const maxValue = Math.max(1, ...Object.values(byCause).map((c) => c.value));
  return (
    <div className="by-cause">
      {CAUSE_ORDER.filter((k) => byCause[k]).map((k) => {
        const c = byCause[k];
        const pct = Math.max(4, Math.round((c.value / maxValue) * 100));
        return (
          <div key={k} className="by-cause__row">
            <span className="by-cause__label">{CAUSE_LABEL[k]}</span>
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

/* Har intervention: ek stacked bar (count ke hisaab se) — kitne recovered,
   kitne pending, kitne human review. recovered aur pending kabhi jode nahi jaate. */
function ByIntervention({ byIntervention }) {
  const keys = [
    ...ACTION_ORDER.filter((k) => byIntervention[k]),
    ...Object.keys(byIntervention).filter((k) => !ACTION_ORDER.includes(k)),
  ];
  return (
    <div className="by-int">
      <div className="by-int__legend">
        <span><i style={{ background: "var(--status-good)" }} />recovered</span>
        <span><i style={{ background: "var(--status-warning)" }} />pending</span>
        <span><i style={{ background: "var(--status-critical)" }} />human review</span>
      </div>
      {keys.map((k) => {
        const b = byIntervention[k];
        const seg = (n) => `${(n / b.count) * 100}%`;
        return (
          <div key={k} className="by-int__row">
            <div className="by-int__top">
              <span className="by-int__label">{ACTION_LABEL[k] || k}</span>
              <span className="by-int__value mono">
                {b.count} · {formatRs(b.value)}
                {b.recovered_value > 0 && (
                  <span className="by-int__rec"> · {formatRs(b.recovered_value)} paid</span>
                )}
              </span>
            </div>
            <div className="by-int__track" role="img"
              aria-label={`${b.recovered} recovered, ${b.pending} pending, ${b.human_review} human review`}>
              <div style={{ width: seg(b.recovered), background: "var(--status-good)" }} />
              <div style={{ width: seg(b.pending), background: "var(--status-warning)" }} />
              <div style={{ width: seg(b.human_review), background: "var(--status-critical)" }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}

function ExceptionList({ items, onSelectCase }) {
  if (items.length === 0) {
    return <p className="exc-empty">Every case found an automated, compliant path.</p>;
  }
  return (
    <ul className="exc-list">
      {items.map((ex) => (
        <li key={ex.txn}>
          <button type="button" className="exc-item" onClick={() => onSelectCase(ex.txn)}
            title="Open this case's audit timeline">
            <div className="exc-item__top">
              <span className="mono exc-item__id">{ex.txn}</span>
              <span className="exc-item__label">{labelHuman(ex.label)}</span>
              <span className="mono exc-item__amount">{formatRs(ex.amount)}</span>
              <span className={`outcome-chip outcome-chip--${outcomeTone(ex.outcome)}`}>
                {ex.outcome}
              </span>
            </div>
            {ex.reasons?.length > 0 && (
              <div className="exc-item__rules">
                {ex.reasons.map((r, i) => {
                  const { code } = parseRule(r);
                  return <span key={i} className="exc-rule" title={r}>{ruleTitle(code)}</span>;
                })}
              </div>
            )}
          </button>
        </li>
      ))}
    </ul>
  );
}

export default function MetricsPanel({ metrics, onSelectCase, onRunBatch, batchRunning, batchError }) {
  if (!metrics) {
    return (
      <section className="panel metrics-panel" aria-label="Metrics">
        <div className="panel__empty">Loading metrics…</div>
      </section>
    );
  }

  const exceptions = metrics.exception_list || [];

  return (
    <section className="panel metrics-panel" aria-label="Metrics">
      <div className="panel__head">
        <SectionHeading icon={IconWallet}>Metrics</SectionHeading>
      </div>

      <BatchControl
        batch={metrics.batch}
        totalTxns={metrics.total_txns}
        onRun={onRunBatch}
        running={batchRunning}
        error={batchError}
      />

      {/*
        Recovered vs actioned: TWO physically separate cards, no combined
        total anywhere on this panel. That is the enforcement mechanism —
        the numbers cannot be summed because nothing here ever adds them.
      */}
      <div className="stat-stack">
        <StatTile
          tone="good" icon={IconCheckCircle} size="hero"
          label="Recovered — customer paid"
          value={formatRs(metrics.recovered_value)}
          sublabel={`${metrics.recovery_rate_pct}% of at-risk value`}
        />
        <StatTile
          tone="info" icon={IconClock} size="hero"
          label="At-risk actioned — links pending"
          value={formatRs(metrics.at_risk_actioned)}
          sublabel={`${metrics.at_risk_actioned_pct}% of at-risk value`}
          caption="not yet paid — never summed with recovered"
        />
      </div>

      <div className="stat-row">
        <StatTile tone="neutral" icon={IconTarget} label="Diagnoser precision" value={`${metrics.diagnoser_precision_pct}%`} />
        <StatTile tone="warning" icon={IconAlertTriangle} label="False-positive cost" value={metrics.wrong_actions_false_positive} />
      </div>

      <SectionHeading standalone hint={`${exceptions.length} of ${metrics.total_txns}`}>
        Exception list
      </SectionHeading>
      <p className="metrics-note">Cases the agent could not auto-recover — click one to see why.</p>
      <ExceptionList items={exceptions} onSelectCase={onSelectCase} />

      <SectionHeading standalone>Recovery by intervention</SectionHeading>
      {metrics.by_intervention && <ByIntervention byIntervention={metrics.by_intervention} />}

      <SectionHeading standalone>Recovery by root cause</SectionHeading>
      <ByCauseBar byCause={metrics.by_cause} />

      <SectionHeading standalone>Escalation & outreach</SectionHeading>
      <div className="stat-grid-4">
        <StatTile tone="neutral" label="Blocked debit → link" value={metrics.escalated_to_link} />
        <StatTile tone="neutral" label="Failed retry → link" value={metrics.retry_failed_to_link} />
        <StatTile tone="good" label="Nudges sent" value={metrics.nudges_sent} />
        <StatTile tone="warning" label="Nudges suppressed" value={metrics.nudges_suppressed} />
      </div>
    </section>
  );
}
