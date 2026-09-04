import { IconSliders, IconShield } from "../icons.jsx";
import { MagnitudeBar, SectionHeading } from "./ui.jsx";
import { RULE_COPY } from "../copy.js";

export default function PolicyConsole({ rules }) {
  if (!rules) {
    return (
      <section className="panel policy-console" aria-label="Policy console">
        <div className="panel__empty">Loading policy console…</div>
      </section>
    );
  }

  const max = Math.max(1, ...rules.map((r) => r.fired_in_batch));

  return (
    <section className="panel policy-console" aria-label="Policy console">
      <div className="panel__head">
        <SectionHeading icon={IconSliders} hint="deterministic — the LLM cannot override any of these">
          Policy console
        </SectionHeading>
      </div>
      <div className="policy-grid">
        {rules.map((r) => {
          const human = RULE_COPY[r.rule];
          return (
            <div key={r.rule} className="policy-card">
              <div className="policy-card__icon"><IconShield size={16} /></div>
              <div className="policy-card__body">
                <div className="policy-card__head">
                  <span className="policy-card__title">{human?.title || r.rule}</span>
                  <span className="mono policy-card__count">{r.fired_in_batch}</span>
                </div>
                <span className="mono policy-card__code">{r.rule}</span>
                <p className="policy-card__desc">{human?.blurb || r.description}</p>
                <MagnitudeBar value={r.fired_in_batch} max={max} />
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
