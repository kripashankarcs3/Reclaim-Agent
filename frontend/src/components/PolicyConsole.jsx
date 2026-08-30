import { MagnitudeBar } from "./ui.jsx";

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
        <h2>Policy console</h2>
        <span className="panel__hint">deterministic gate — the LLM cannot override any of these</span>
      </div>
      <div className="policy-grid">
        {rules.map((r) => (
          <div key={r.rule} className="policy-card">
            <div className="policy-card__head">
              <span className="mono policy-card__name">{r.rule}</span>
              <span className="mono policy-card__count">{r.fired_in_batch}</span>
            </div>
            <p className="policy-card__desc">{r.description}</p>
            <MagnitudeBar value={r.fired_in_batch} max={max} />
          </div>
        ))}
      </div>
    </section>
  );
}
