import { useCallback, useEffect, useRef, useState } from "react";
import Header from "./components/Header.jsx";
import CaseFeed from "./components/CaseFeed.jsx";
import CaseTimeline from "./components/CaseTimeline.jsx";
import MetricsPanel from "./components/MetricsPanel.jsx";
import PolicyConsole from "./components/PolicyConsole.jsx";
import { fetchMetrics, fetchCases, fetchCase, fetchPolicyStats, fetchHealth } from "./api.js";

const POLL_MS = 6000;
/* txn_046: the three-rule RETRY_CAP + HARD_DECLINE + AFA_THRESHOLD block —
   the clearest single proof that the gate refuses. Default view on load. */
const DEFAULT_CASE_ID = "txn_046";

export default function App() {
  const [health, setHealth] = useState(null);
  const [cases, setCases] = useState([]);
  const [metrics, setMetrics] = useState(null);
  const [policyStats, setPolicyStats] = useState(null);

  const [selectedId, setSelectedId] = useState(DEFAULT_CASE_ID);
  const [caseData, setCaseData] = useState(null);
  const [caseLoading, setCaseLoading] = useState(true);
  const [caseError, setCaseError] = useState(null);

  const hasLoadedOnce = useRef(false);

  const refreshLists = useCallback(async () => {
    try {
      const [h, c, m, p] = await Promise.all([
        fetchHealth(), fetchCases(), fetchMetrics(), fetchPolicyStats(),
      ]);
      setHealth(h);
      setCases(c.cases);
      setMetrics(m);
      setPolicyStats(p.rules);
    } catch (err) {
      // Poll-tick failure ko silently drop karo — UI purani (stale but valid)
      // state pe rahe, crash na ho. Agla tick apne aap retry karega.
      console.error("dashboard refresh failed:", err);
    } finally {
      hasLoadedOnce.current = true;
    }
  }, []);

  useEffect(() => {
    refreshLists();
    const id = setInterval(refreshLists, POLL_MS);
    return () => clearInterval(id);
  }, [refreshLists]);

  const selectCase = useCallback((txnId) => {
    setSelectedId(txnId);
    setCaseLoading(true);
    setCaseError(null);
    fetchCase(txnId)
      .then((d) => setCaseData(d))
      .catch((err) => setCaseError(err.message))
      .finally(() => setCaseLoading(false));
  }, []);

  useEffect(() => {
    selectCase(DEFAULT_CASE_ID);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const liveCases = cases.filter((c) => c.source === "live");
  const lastLiveCase = liveCases.length ? liveCases[liveCases.length - 1] : null;

  return (
    <div className="app-shell">
      <Header
        webhookConfigured={health?.webhook_secret_configured ?? false}
        lastLiveCase={lastLiveCase}
      />
      <main className="app-grid">
        <CaseFeed cases={cases} selectedId={selectedId} onSelect={selectCase} />
        <CaseTimeline caseData={caseData} loading={caseLoading} error={caseError} />
        <MetricsPanel metrics={metrics} />
      </main>
      <PolicyConsole rules={policyStats} />
    </div>
  );
}
