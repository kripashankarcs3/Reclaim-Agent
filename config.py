"""
config.py — ReclaimAgent ke saare compliance constants ek jagah.

Har constant ke saath uska "kyun" likha hai — yahi interview ammunition hai.
Rule kabhi prompt mein hardcode mat karo; runtime constant rakho taaki
policy_engine deterministically enforce kare (LLM override na kar paaye).
"""

# --- NPCI UPI Autopay retry cap ---------------------------------------------
# 1 original attempt + max 3 retries = total 4 attempts.
# Effective 1 August 2025. Cap cross karna = non-compliant + customer irritation
# = false-positive cost.
MAX_RETRIES = 3          # retries ALLOWED after the 1 original attempt
MAX_TOTAL_ATTEMPTS = 4   # 1 + 3

# --- RBI e-mandate framework (E-mandate Framework, 2026; dated 22 Apr 2026) --
# Is amount se upar silent recurring debit allowed nahi — Additional Factor of
# Authentication (AFA) chahiye. (MF/insurance/CC bills ke liye 1,00,000.)
AFA_THRESHOLD = 15000            # INR
AFA_THRESHOLD_SPECIAL = 100000   # MF subscriptions, insurance premiums, CC bills

# --- RBI 24-hour pre-debit notification --------------------------------------
# Recurring debit se kam se kam 24 ghante pehle customer ko notify karna
# mandatory (amount, debit date, mandate ref, opt-out).
PRE_DEBIT_NOTICE_HOURS = 24

# --- RBI fair-practices contact window ---------------------------------------
# 8 AM - 7 PM. Technically NBFCs/lenders pe binding; hum ise SAFE DEFAULT bana
# rahe hain (ye nuance khud ek strong interview signal hai).
CONTACT_WINDOW_START = 8   # 08:00
CONTACT_WINDOW_END = 19    # 19:00 (7 PM)

# --- TRAI TCCCPR messaging ----------------------------------------------------
# Nudge sirf DLT-registered transactional template se; opt-out ke 90 din tak
# dobara solicit nahi.
OPT_OUT_COOLDOWN_DAYS = 90

# --- Per-customer spend / attempt cap (over-contact rokne ke liye) ------------
MAX_RECOVERY_ATTEMPTS_PER_CUSTOMER_PER_DAY = 2

# --- Escalation policy (Phase 3.5) -------------------------------------------
# Gate ne proposed DEBIT block kar diya -> kya ek automated fallback
# (customer-initiated payment link) allowed hai, ya seedha human review?
# Ye decision bhi rules-as-code hai, ad-hoc nahi.
#
# FALLBACK_ELIGIBLE: defect IS DEBIT ATTEMPT ka hai. Mandate re-presentment ka
# rasta band hai, par customer khud pay kar sakta hai -> payment link bhejna
# textbook dunning hai. (Customer-initiated link pe na mandate cap lagta hai,
# na 24-hour pre-debit notice — kyunki wo silent debit hai hi nahi.)
FALLBACK_ELIGIBLE_RULES = {"RETRY_CAP", "HARD_DECLINE", "PRE_DEBIT_NOTICE"}

# HUMAN_ESCALATION: defect AUTHORIZATION ya CONTACT-PERMISSION ka hai.
#   AFA_THRESHOLD  -> itni badi value unattended recover nahi karni (merchant
#                     policy; AFA customer ke saamne hona chahiye).
#   CONTACT_WINDOW / TRAI_MESSAGING / SPEND_CAP -> abhi customer ko contact
#                     karne ki ijazat hi nahi. Aise mein link+nudge wala
#                     fallback EXACTLY wahi hai jo nahi karna chahiye.
HUMAN_ESCALATION_RULES = {"AFA_THRESHOLD", "CONTACT_WINDOW",
                          "TRAI_MESSAGING", "SPEND_CAP"}

# --- Currency ----------------------------------------------------------------
CURRENCY = "INR"
