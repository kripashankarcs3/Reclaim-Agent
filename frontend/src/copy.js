/*
copy.js — sirf DISPLAY-layer translation. Backend rule codes waise hi rehte
hain (audit trail mein raw code hi credible hai) — yahan hum sirf UNKE SAATH
ek plain-language title dikhate hain, taaki koi bhi non-technical viewer bhi
turant samajh jaye "MANDATE_REQUIRED ka matlab kya hai" bina docs padhe.
Koi logic yahan nahi, sirf strings.
*/

// rule code -> {title, blurb}. Raw code hamesha saath (mono badge) dikhta hai.
export const RULE_COPY = {
  RETRY_CAP: {
    title: "Retry limit reached",
    blurb: "NPCI allows at most 4 attempts (1 original + 3 retries).",
  },
  HARD_DECLINE: {
    title: "Hard decline — can't silently retry",
    blurb: "Insufficient funds / blocked card. Needs a customer-initiated payment.",
  },
  MANDATE_REQUIRED: {
    title: "No stored mandate to charge",
    blurb: "One-time payments have no token — the merchant can't silently re-charge them.",
  },
  AFA_THRESHOLD: {
    title: "Needs additional authentication",
    blurb: "Above ₹15,000, a silent debit is not allowed — RBI requires AFA.",
  },
  PRE_DEBIT_NOTICE: {
    title: "Missing 24-hour notice",
    blurb: "A subscription retry requires the pre-debit notice to be sent first.",
  },
  CONTACT_WINDOW: {
    title: "Outside allowed contact hours",
    blurb: "Customers can only be contacted between 8 AM and 7 PM.",
  },
  TRAI_MESSAGING: {
    title: "Messaging not permitted",
    blurb: "No consent on record, or within the 90-day opt-out cooldown.",
  },
  SPEND_CAP: {
    title: "Daily contact limit reached",
    blurb: "This customer has already been contacted the maximum times today.",
  },
};

export function ruleTitle(code) {
  return RULE_COPY[code]?.title || code;
}

// Ek "NAME: full sentence" string ko {code, title, detail} mein todo.
export function parseRule(rule) {
  const i = rule.indexOf(": ");
  const code = i === -1 ? rule : rule.slice(0, i);
  const detail = i === -1 ? "" : rule.slice(i + 2);
  return { code, title: ruleTitle(code), detail };
}

// Timeline ke har stage ke liye: icon key + human title + ek-line "iska matlab".
export const STAGE_COPY = {
  detect: { icon: "search", title: "Detected", blurb: "The failure event arrives from Razorpay." },
  diagnose: { icon: "activity", title: "Diagnosed", blurb: "Root cause is classified automatically." },
  decide: { icon: "gitBranch", title: "Proposed", blurb: "An action is proposed — not yet approved." },
  policy_check: { icon: "shield", title: "Policy check", blurb: "The compliance gate reviews the proposal." },
  execute: { icon: "send", title: "Executed", blurb: "The approved action runs." },
  execute_error: { icon: "alertTriangle", title: "Execution error", blurb: "The live call failed safely, no fake success." },
  notify: { icon: "bell", title: "Notification", blurb: "The customer is (or isn't) messaged." },
  outcome: { icon: "flag", title: "Outcome", blurb: "Where the case landed." },
};

export const OUTCOME_COPY = {
  recovered: { title: "Recovered", blurb: "The customer paid." },
  pending: { title: "Pending", blurb: "Awaiting the customer — link sent, not yet paid." },
  human_review: { title: "Needs a human", blurb: "The gate refused every automated path." },
  not_attempted: { title: "Not attempted", blurb: "" },
};
