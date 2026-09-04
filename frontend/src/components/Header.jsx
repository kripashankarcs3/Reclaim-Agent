import { IconZap, IconShield } from "../icons.jsx";
import { StatusDot } from "./ui.jsx";

export default function Header({ webhookConfigured, lastLiveCase }) {
  return (
    <header className="app-header">
      <div className="app-header__brand">
        <span className="app-header__mark-icon"><IconShield size={20} /></span>
        <div className="app-header__brand-text">
          <span className="app-header__mark">ReclaimAgent</span>
          <span className="app-header__tagline">
            The LLM proposes. A deterministic policy engine decides.
          </span>
        </div>
      </div>

      <div className="app-header__status">
        <span className="app-header__last-event">
          {lastLiveCase ? (
            <>
              <IconZap size={13} className="app-header__event-icon" />
              Last live event <span className="mono">{lastLiveCase.id}</span> ·{" "}
              {lastLiveCase.label ?? "unclassified"} · {lastLiveCase.outcome ?? "…"}
            </>
          ) : (
            "No live webhook events yet — showing the synthetic batch"
          )}
        </span>

        <span className={`webhook-pill ${webhookConfigured ? "is-live" : "is-off"}`}>
          <StatusDot status={webhookConfigured ? "good" : "warning"} />
          {webhookConfigured ? "Webhook live-capable" : "Webhook secret not set"}
        </span>
      </div>
    </header>
  );
}
