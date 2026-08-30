# ReclaimAgent — Ops Console (Phase 7)

Read-only dashboard over the FastAPI backend's `/api/*` endpoints. It never writes
anything — no mutation, no POST/PUT/DELETE, no webhook triggering from the UI.

## Run it

Two processes, backend first:

```bash
# from the repo root
uvicorn main:app --port 8000
```

```bash
# from frontend/
npm install
npm run dev
```

Open **http://localhost:5173**. The Vite dev server proxies nothing itself — the
dashboard calls `http://127.0.0.1:8000` directly, which is why `main.py` allows CORS
from `localhost:5173` / `127.0.0.1:5173` specifically (`GET` only, no wildcard).

The star panel defaults to `txn_046` on load — the three-rule
`RETRY_CAP` + `HARD_DECLINE` + `AFA_THRESHOLD` block, the clearest single proof that
the policy engine refuses.

## What each panel shows

- **Case Audit Timeline (star)** — a case's full `detect → diagnose → decide →
  policy_check(s) → outcome` sequence as a vertical stepper. A `policy_check` with
  `allowed: false` renders with a critical-red left border and each failed rule as a
  badge (code + full message on hover). When a case is re-gated after a block, the
  next `policy_check` shows "↳ escalated from: …" so the escalation reads as one
  sequence, not disconnected entries. `LIVE` cases (from a real webhook) and `BATCH`
  cases (from the synthetic run) are tagged distinctly.
- **Cases** — all 54 batch cases plus any real webhook deliveries, each with a red dot
  if a rule fired against it. Click a row to load it into the star panel.
- **Metrics** — *recovered* and *actioned* are two separate stat tiles, never summed
  anywhere in this code — that distinction is enforced by not writing a combined total,
  not by a UI convention. Plus by-cause breakdown, diagnoser precision, false-positive
  cost, and the escalation/nudge counts.
- **Policy console** — the 8 guardrail rules, descriptions read directly from
  `policy_engine.py`'s own docstrings (not copied by hand), with how many times each
  fired in the batch.

## Notes

- No component library, no Tailwind — hand-written CSS in `src/index.css` against the
  design tokens in `src/tokens.css`, so the look is chosen rather than templated.
- Polls `/api/cases`, `/api/metrics`, `/api/policy-stats` every 6s; a selected case's
  timeline is fetched once on click, not polled.
- `frontend-design` (a skill the build was asked to consult) does not exist in this
  environment — checked directly, nothing by that name is registered. The `dataviz`
  skill's color/form guidance was used instead (status colors, categorical order,
  stat-tile-vs-chart choice), plus ordinary design judgment for layout and type.
