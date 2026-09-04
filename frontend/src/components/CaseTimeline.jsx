import { formatRs, outcomeTone, StageIcon } from "./ui.jsx";
import { STAGE_COPY, OUTCOME_COPY, parseRule } from "../copy.js";
import {
  IconShieldCheck, IconShieldAlert, IconCornerDownRight, IconCheckCircle,
  IconClock, IconAlertTriangle, IconFlag,
} from "../icons.jsx";

function KV({ k, v }) {
  if (v === null || v === undefined || v === "") return null;
  return (
    <div className="kv">
      <span className="kv__k">{k}</span>
      <span className="kv__v">{String(v)}</span>
    </div>
  );
}

/* Ek rule string ko badge mein render karo: human title primary, code + full
   sentence secondary — sab VISIBLE, hover ke peeche nahi chupaya. */
function RuleBadge({ rule }) {
  const { code, title, detail } = parseRule(rule);
  return (
    <div className="rule-badge">
      <div className="rule-badge__title">{title}</div>
      <div className="rule-badge__meta">
        <span className="mono rule-badge__code">{code}</span>
        {detail && <span className="rule-badge__detail">{detail}</span>}
      </div>
    </div>
  );
}

function RuleBadgeList({ rules }) {
  if (!rules || rules.length === 0) return null;
  return (
    <div className="rule-badge-list">
      {rules.map((r, i) => <RuleBadge key={i} rule={r} />)}
    </div>
  );
}

function DetectStage({ d }) {
  return (
    <div className="kv-grid">
      <KV k="status" v={d.status} />
      <KV k="amount" v={formatRs(d.amount)} />
      <KV k="error code" v={d.error_code} />
    </div>
  );
}

function DiagnoseStage({ d }) {
  return (
    <>
      <div className="stage-lead">
        <span className="badge badge--neutral">{d.label}</span>
      </div>
      <p className="stage-prose">{d.explanation}</p>
    </>
  );
}

function DecideStage({ d }) {
  return (
    <p className="stage-prose">
      Proposes <span className="mono stage-prose__action">{d.proposed_action}</span> —
      the cheapest tempting action, with no safety logic. That's deliberate: the gate
      is what decides, not this step.
    </p>
  );
}

/* ⭐ THE moment: allowed:false -> critical, badged failed rules, human titles
   visible directly (not behind hover). Iske chhupne se poora "the deterministic
   gate refused, not the LLM" claim khokhla ho jata. */
function PolicyCheckStage({ d }) {
  const blocked = d.allowed === false;
  return (
    <>
      <div className={`verdict-banner ${blocked ? "verdict-banner--blocked" : "verdict-banner--allowed"}`}>
        {blocked ? <IconShieldAlert size={18} /> : <IconShieldCheck size={18} />}
        <span className="verdict-banner__text">
          {blocked ? "Refused by the gate" : "Allowed by the gate"}
        </span>
        <span className="mono verdict-banner__action">{d.action}</span>
      </div>
      <RuleBadgeList rules={d.failed_rules} />
    </>
  );
}

function ExecuteStage({ d }) {
  return (
    <div className="kv-grid">
      <KV k="action" v={d.action} />
      <KV k="outcome" v={d.outcome} />
      {d.live !== undefined && <KV k="mode" v={d.live ? "LIVE (real Razorpay)" : "dry-run"} />}
      {d.artifact?.short_url && <KV k="link" v={d.artifact.short_url} />}
    </div>
  );
}

function ExecuteErrorStage({ d }) {
  return (
    <>
      <div className="kv-grid">
        <KV k="action" v={d.action} />
      </div>
      <p className="stage-prose stage-prose--error">{d.error}</p>
    </>
  );
}

function NotifyStage({ d }) {
  if (d.suppressed) {
    return (
      <>
        <div className="verdict-banner verdict-banner--blocked">
          <IconShieldAlert size={18} />
          <span className="verdict-banner__text">Nudge suppressed</span>
        </div>
        <RuleBadgeList rules={d.reasons} />
      </>
    );
  }
  return (
    <>
      <div className="kv-grid">
        <KV k="channel" v={d.channel} />
        <KV k="window check" v={d.window_check} />
        <KV k="consent" v={d.consent} />
      </div>
      <p className="stage-prose stage-prose--quote">{d.template}</p>
    </>
  );
}

const OUTCOME_ICON = { recovered: IconCheckCircle, pending: IconClock, human_review: IconAlertTriangle };

function OutcomeStage({ d }) {
  const Icon = OUTCOME_ICON[d.outcome] || IconFlag;
  const copy = OUTCOME_COPY[d.outcome] || { title: d.outcome, blurb: "" };
  return (
    <>
      <div className={`verdict-banner verdict-banner--${outcomeTone(d.outcome)}`}>
        <Icon size={18} />
        <span className="verdict-banner__text">{copy.title}</span>
      </div>
      {copy.blurb && <p className="stage-prose">{copy.blurb}</p>}
      <RuleBadgeList rules={d.reasons} />
    </>
  );
}

const RENDERERS = {
  detect: DetectStage, diagnose: DiagnoseStage, decide: DecideStage,
  policy_check: PolicyCheckStage, execute: ExecuteStage,
  execute_error: ExecuteErrorStage, notify: NotifyStage, outcome: OutcomeStage,
};

function StageNode({ entry, isLast }) {
  const Renderer = RENDERERS[entry.stage] || (() => <pre>{JSON.stringify(entry.detail)}</pre>);
  const blocked = entry.stage === "policy_check" && entry.detail.allowed === false;
  const copy = STAGE_COPY[entry.stage] || { icon: "activity", title: entry.stage, blurb: "" };
  const escalatedFrom = entry.detail.escalated_from;

  return (
    <li className={`stage-node ${blocked ? "stage-node--blocked" : ""}`}>
      <div className="stage-node__rail">
        <span className={`stage-node__badge ${blocked ? "stage-node__badge--blocked" : ""}`}>
          <StageIcon name={copy.icon} size={15} />
        </span>
        {!isLast && <span className="stage-node__line" />}
      </div>
      <div className="stage-node__card">
        {escalatedFrom && (
          <div className="escalation-chip">
            <IconCornerDownRight size={13} />
            escalated from <span className="mono">{escalatedFrom}</span>
          </div>
        )}
        <div className="stage-node__head">
          <span className="stage-node__title">{copy.title}</span>
          <span className="stage-node__blurb">{copy.blurb}</span>
        </div>
        <div className="stage-node__body">
          <Renderer d={entry.detail} />
        </div>
      </div>
    </li>
  );
}

export default function CaseTimeline({ caseData, loading, error }) {
  if (loading) {
    return (
      <section className="panel timeline-panel" aria-label="Case audit timeline">
        <div className="panel__empty">Loading case…</div>
      </section>
    );
  }
  if (error) {
    return (
      <section className="panel timeline-panel" aria-label="Case audit timeline">
        <div className="panel__empty panel__empty--error">{error}</div>
      </section>
    );
  }
  if (!caseData) {
    return (
      <section className="panel timeline-panel" aria-label="Case audit timeline">
        <div className="panel__empty">Select a case from the feed to see its audit timeline.</div>
      </section>
    );
  }

  return (
    <section className="panel timeline-panel" aria-label="Case audit timeline">
      <div className="panel__head panel__head--stacked">
        <div className="panel__head-row">
          <h2>
            Case Audit Timeline <span className="mono panel__head-id">{caseData.txn_id}</span>
          </h2>
          <span className={`source-tag source-tag--${caseData.source}`}>
            {caseData.source === "live" ? "LIVE" : "BATCH"}
          </span>
        </div>
        <div className="timeline-legend">
          <span className="timeline-legend__item timeline-legend__item--allowed">
            <IconShieldCheck size={13} /> Gate allowed
          </span>
          <span className="timeline-legend__item timeline-legend__item--blocked">
            <IconShieldAlert size={13} /> Gate refused
          </span>
          <span className="timeline-legend__note">
            Every refusal below comes from the policy engine, never the LLM.
          </span>
        </div>
      </div>
      <ol className="stage-stepper">
        {caseData.timeline.map((entry, i) => (
          <StageNode key={i} entry={entry} isLast={i === caseData.timeline.length - 1} />
        ))}
      </ol>
    </section>
  );
}
