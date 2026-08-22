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

# --- Cap ke liye "CONTACT" ka matlab kya hai? (policy definition) -------------
# Ye cap kis nuksan se bacha raha hai? CUSTOMER KO BAAR-BAAR PARESHAAN KARNE se.
# Yaani jo cheez customer ko DIKHTI hai, wahi ginni chahiye.
#
#   retry  -> customer ko kuch nahi dikhta. Ye ek silent backend re-presentment
#             hai mandate ke against — na SMS, na screen, na koi awaaz. Uska
#             apna alag, sakht cap already hai: NPCI 1+3 (rule_retry_cap).
#             Isko contact-cap mein ginna do baar saza dena hai, aur usse ek
#             asli nuksan hota hai: ek failed retry customer ka "contact budget"
#             kha jata hai, jisse hum use wo link BATA hi nahi paate jo humne
#             abhi banaya. Cap ka maqsad ulta ho jata hai.
#
#   payment_link / recovery_link -> customer-facing hai. Ye ek payment REQUEST
#             hai jo customer ko address ki gayi hai (Razorpay khud isko notify
#             kar sakta hai — hum wo off rakhte hain), aur iske saath hamesha ek
#             nudge propose hota hai. Isliye ye ginta hai.
#
#   nudge  -> asli message. Definitely ginta hai.
#
# Note: ye Phase 3.5 wale "link banana koi contact nahi hai" se ulta NAHI hai.
# Wahan sawaal TRAI/consent ka tha — wo MESSAGE pe lagta hai, link object pe
# nahi. Yahan sawaal alag hai: ek din mein customer ki taraf kitni recovery
# attempts bheji. Link ek attempt hai; silent retry nahi.
SPEND_CAP_COUNTS_CONTACTS_ONLY = True
CONTACT_ACTIONS = {"payment_link", "recovery_link", "nudge"}

# --- Mandate requirement for silent re-presentment (Phase 3.6) ---------------
# Ek ONE-TIME payment ko merchant chupchap dobara charge nahi kar sakta — koi
# stored mandate/token hai hi nahi. Silent retry SIRF mandate-backed txn pe
# possible hai (Subscriptions / e-mandate / UPI Autopay), kyunki wahan customer
# ne pehle se ek registered mandate ke against debit karne ki permission di hai.
# Bina mandate ke recovery ka ekmatra compliant rasta = customer-initiated
# payment link, jahan customer khud authenticate karta hai.
#
# Ye sirf compliance nahi, PLUMBING ki sacchai hai: bina token ke koi debit API
# hai hi nahi. Isliye ye rule metrics ko bhi honest karta hai — pehle hum
# one-time failures ko "retry se recover" maan rahe the, jo real duniya mein
# hota hi nahi.
RETRY_REQUIRES_MANDATE = True

# --- Escalation policy (Phase 3.5) -------------------------------------------
# Gate ne proposed DEBIT block kar diya -> kya ek automated fallback
# (customer-initiated payment link) allowed hai, ya seedha human review?
# Ye decision bhi rules-as-code hai, ad-hoc nahi.
#
# FALLBACK_ELIGIBLE: defect IS DEBIT ATTEMPT ka hai. Mandate re-presentment ka
# rasta band hai, par customer khud pay kar sakta hai -> payment link bhejna
# textbook dunning hai. (Customer-initiated link pe na mandate cap lagta hai,
# na 24-hour pre-debit notice — kyunki wo silent debit hai hi nahi.)
FALLBACK_ELIGIBLE_RULES = {"RETRY_CAP", "HARD_DECLINE", "PRE_DEBIT_NOTICE",
                           "MANDATE_REQUIRED"}

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
