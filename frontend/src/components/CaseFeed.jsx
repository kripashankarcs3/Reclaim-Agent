import { Badge, formatRs, outcomeTone, labelTone } from "./ui.jsx";

export default function CaseFeed({ cases, selectedId, onSelect }) {
  return (
    <section className="panel case-feed" aria-label="Case feed">
      <div className="panel__head">
        <h2>Cases</h2>
        <span className="panel__count">{cases.length}</span>
      </div>
      <div className="case-feed__list">
        {cases.map((c) => {
          const flagged = (c.failed_rules || []).length > 0;
          return (
            <button
              key={`${c.source}:${c.id}`}
              className={`case-row ${c.id === selectedId ? "is-selected" : ""}`}
              onClick={() => onSelect(c.id)}
            >
              <div className="case-row__top">
                <span className="mono case-row__id">{c.id}</span>
                <span className={`source-tag source-tag--${c.source}`}>
                  {c.source === "live" ? "LIVE" : "BATCH"}
                </span>
              </div>
              <div className="case-row__mid">
                <Badge tone={labelTone(c.label)}>{c.label ?? "—"}</Badge>
                <span className="case-row__amount mono">{formatRs(c.amount)}</span>
              </div>
              <div className="case-row__bottom">
                <span className="case-row__action">{c.action ?? "—"}</span>
                <span className={`outcome-chip outcome-chip--${outcomeTone(c.outcome)}`}>
                  {c.outcome ?? "—"}
                </span>
                {flagged && (
                  <span className="flag-dot" title={`${c.failed_rules.length} rule(s) fired`} />
                )}
              </div>
            </button>
          );
        })}
      </div>
    </section>
  );
}
