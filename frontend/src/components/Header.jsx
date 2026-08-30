import { StatusDot } from "./ui.jsx";

export default function Header({ webhookConfigured, lastLiveCase }) {
  return (
    <header className="app-header">
      <div className="app-header__brand">
        <span className="app-header__mark">ReclaimAgent</span>
        <span className="app-header__tagline">payments recovery — ops console</span>
      </div>

      <div className="app-header__status">
        <span className={`webhook-pill ${webhookConfigured ? "is-live" : "is-off"}`}>
          <StatusDot status={webhookConfigured ? "good" : "warning"} />
          {webhookConfigured ? "Webhook: LIVE-CAPABLE" : "Webhook: secret not configured"}
        </span>

        <span className="app-header__last-event">
          {lastLiveCase ? (
            <>
              Last live event:{" "}
              <span className="mono">{lastLiveCase.id}</span> ·{" "}
              {lastLiveCase.label ?? "unclassified"} · {lastLiveCase.outcome ?? "…"}
            </>
          ) : (
            "No live webhook events yet"
          )}
        </span>
      </div>
    </header>
  );
}
