import { IconList, IconArrowRight, IconZap } from "../icons.jsx";
import { Badge, SectionHeading, formatRs, outcomeTone, labelTone, labelHuman } from "./ui.jsx";

export default function CaseFeed({ cases, selectedId, onSelect }) {
  return (
    <section className="panel case-feed" aria-label="Case feed">
      <div className="panel__head">
        <SectionHeading icon={IconList}>Cases</SectionHeading>
        <span className="panel__count">{cases.length}</span>
      </div>
      <div className="case-feed__list">
        {cases.map((c) => {
          const flagged = (c.failed_rules || []).length > 0;
          const tone = outcomeTone(c.outcome);
          const selected = c.id === selectedId;
          return (
            <button
              key={`${c.source}:${c.id}`}
              className={`case-row case-row--${tone} ${selected ? "is-selected" : ""}`}
              onClick={() => onSelect(c.id)}
            >
              <span className="case-row__accent" />
              <div className="case-row__main">
                <div className="case-row__top">
                  <span className="mono case-row__id">{c.id}</span>
                  {c.source === "live" ? (
                    <span className="source-tag source-tag--live"><IconZap size={10} />LIVE</span>
                  ) : (
                    <span className="source-tag source-tag--batch">BATCH</span>
                  )}
                </div>
                <div className="case-row__mid">
                  <Badge tone={labelTone(c.label)}>{labelHuman(c.label)}</Badge>
                  <span className="case-row__amount mono">{formatRs(c.amount)}</span>
                </div>
                <div className="case-row__flow">
                  <span className="case-row__action">{c.action ?? "—"}</span>
                  <IconArrowRight size={11} className="case-row__flow-arrow" />
                  <span className={`outcome-chip outcome-chip--${tone}`}>{c.outcome ?? "—"}</span>
                  {flagged && (
                    <span className="flag-badge" title={`${c.failed_rules.length} rule(s) fired`}>
                      {c.failed_rules.length}
                    </span>
                  )}
                </div>
              </div>
            </button>
          );
        })}
      </div>
    </section>
  );
}
