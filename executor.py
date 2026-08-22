"""
executor.py — Razorpay test-mode calls. Abhi DRY-RUN; Phase 4 mein wire karo.

IMPORTANT (honesty): Standard Payment Links test mode mein chalte hain;
UPI Payment Links SIRF live mode — demo test-mode primitives pe design karo.

Real razorpay wiring (uncomment after `pip install razorpay` + keys in .env):

    import razorpay
    client = razorpay.Client(auth=(KEY_ID, KEY_SECRET))

    def create_payment_link(txn):
        return client.payment_link.create({
            "amount": txn.amount * 100, "currency": "INR",
            "description": f"Recovery for {txn.order_id}",
            "reference_id": txn.order_id,
            "callback_url": "https://yourapp/callback", "callback_method": "get",
        })
    def fetch_payments():
        return client.payment.all()
    def refund(payment_id, amount):
        return client.payment.refund(payment_id, {"amount": amount * 100})

Ideal: in calls ko Razorpay MCP server (mcp.razorpay.com/sse) ke through wire
karo — on-brand (Agent Studio bhi agent SDK pe hai).
"""


def create_payment_link(txn) -> dict:
    # DRY-RUN placeholder
    return {"id": f"plink_{txn.id}", "status": "created",
            "short_url": f"https://rzp.io/i/mock-{txn.id}"}


def retry_charge(txn) -> dict:
    # DRY-RUN placeholder (real: client.subscription retry / re-attempt)
    return {"id": f"pay_retry_{txn.id}", "status": "attempted"}


def refund(payment_id: str, amount: int) -> dict:
    return {"id": f"rfnd_{payment_id}", "status": "processed"}
