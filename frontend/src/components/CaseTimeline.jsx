import { Badge, formatRs, outcomeTone } from "./ui.jsx";

const STAGE_LABEL = {
  detect: "Detected",
  diagnose: "Diagnosed",
  decide: "Decided",
  policy_check: "Policy check",
  execute: "Executed",
  execute_error: "Execution error",
  notify: "Notification",
  outcome: "Outcome",
};

/* "RETRY_CAP: NPCI 1+3 cap exhausted (4/4 attempts used)" -> {code, message} */
function splitRule(rule) {
  const i = rule.indexOf(": ");
  return i === -1 ? { code: rule, message: "" } : { code: rule.slice(0, i), message: rule.slice(i + 2) };
}

function KV({ k, v }) {
  if (v === null || v === undefined || v === "") return null;
  return (
    <div className="kv">
      <span className="kv__k">{k}</span>
      <span className="kv__v">{String(v)}</span>
    </div>
  );
}

function DetectStage({ d }) {
  return (
    <>
      <KV k="status" v={d.status} />
      <KV k="amount" v={formatRs(d.amount)} />
      <KV k="error_code" v={d.error_code} />
    </>
  );
}

function DiagnoseStage({ d }) {
  return (
    <>
      <Badge tone="neutral">{d.label}</Badge>
      <p className="stage-prose">{d.explanation}</p>
    </>
  );
}

function DecideStage({ d }) {
  return <KV k="proposed_action" v={d.proposed_action} />;
}

/*
⭐ THE moment: allowed:false -> critical, badged failed rules. Iske chhupne se
poora "the deterministic gate refused, not the LLM" claim khokhla ho jata.
*/
function PolicyCheckStage({ d }) {
  const blocked = d.allowed === false;
  const rules = (d.failed_rules || []).map(splitRule);
  return (
    <>
      <div className="policy-verdict">
        <KV k="action" v={d.action} />
        <span className={`verdict-tag ${blocked ? "verdict-tag--blocked" : "verdict-tag--allowed"}`}>
          {blocked ? "BLOCKED" : "ALLOWED"}
        </span>
      </div>
      {rules.length > 0 && (
        <div className="rule-badges">
          {rules.map((r, i) => (
            <span key={i} className="rule-badge" title={r.message}>
              {r.code}
            </span>
          ))}
        </div>
      )}
    </>
  );
}

function ExecuteStage({ d }) {
  return (
    <>
      <KV k="action" v={d.action} />
      <KV k="outcome" v={d.outcome} />
      {d.live !== undefined && <KV k="mode" v={d.live ? "LIVE (real Razorpay)" : "dry-run"} />}
      {d.artifact?.short_url && (
        <div className="kv">
          <span className="kv__k">link</span>
          <span className="kv__v mono">{d.artifact.short_url}</span>
        </div>
      )}
    </>
  );
}

function ExecuteErrorStage({ d }) {
  return (
    <>
      <KV k="action" v={d.action} />
      <p className="stage-prose stage-prose--error">{d.error}</p>
    </>
  );
}

function NotifyStage({ d }) {
  if (d.suppressed) {
    return (
      <>
        <span className="verdict-tag verdict-tag--blocked">SUPPRESSED</span>
        <div className="rule-badges">
          {(d.reasons || []).map(splitRule).map((r, i) => (
            <span key={i} className="rule-badge" title={r.message}>{r.code}</span>
          ))}
        </div>
      </>
    );
  }
  return (
    <>
      <div className="policy-verdict">
        <KV k="channel" v={d.channel} />
        <KV k="window_check" v={d.window_check} />
        <KV k="consent" v={d.consent} />
      </div>
      <p className="stage-prose stage-prose--quote">{d.template}</p>
    </>
  );
}

function OutcomeStage({ d }) {
  return (
    <>
      <span className={`outcome-chip outcome-chip--${outcomeTone(d.outcome)}`}>{d.outcome}</span>
      {(d.reasons || []).length > 0 && (
        <div className="rule-badges">
          {d.reasons.map(splitRule).map((r, i) => (
            <span key={i} className="rule-badge" title={r.message}>{r.code}</span>
          ))}
        </div>
      )}
      {d.escalated_from && <KV k="escalated_from" v={d.escalated_from} />}
    </>
  );
}

const RENDERERS = {
  detect: DetectStage,
  diagnose: DiagnoseStage,
  decide: DecideStage,
  policy_check: PolicyCheckStage,
  execute: ExecuteStage,
  execute_error: ExecuteErrorStage,
  notify: NotifyStage,
  outcome: OutcomeStage,
};

function StageNode({ entry, index }) {
  const Renderer = RENDERERS[entry.stage] || (() => <pre>{JSON.stringify(entry.detail)}</pre>);
  const blocked = entry.stage === "policy_check" && entry.detail.allowed === false;
  const escalatedFrom = entry.detail.escalated_from;

  return (
    <li className={`stage-node ${blocked ? "stage-node--blocked" : ""}`}>
      <div className="stage-node__rail">
        <span className="stage-node__dot" />
        {index !== -1 && <span className="stage-node__line" />}
      </div>
      <div className="stage-node__card">
        {escalatedFrom && (
          <div className="stage-node__escalation">↳ escalated from: {escalatedFrom}</div>
        )}
        <div className="stage-node__head">{STAGE_LABEL[entry.stage] || entry.stage}</div>
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
        <p className="panel__hint-line">
          AI proposes · the policy gate decides — refused steps in red
        </p>
      </div>
      <ol className="stage-stepper">
        {caseData.timeline.map((entry, i) => (
          <StageNode key={i} entry={entry} index={i === caseData.timeline.length - 1 ? -1 : i} />
        ))}
      </ol>
    </section>
  );
}
