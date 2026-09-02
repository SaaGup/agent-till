from slowapi import Limiter
from slowapi.util import get_remote_address

# Public endpoints that spend money (Razorpay orders) or tokens (Claude calls) are rate
# limited per-IP so a live public demo URL can't be used to burn the account's budget.
limiter = Limiter(key_func=get_remote_address, default_limits=["120/minute"])

CHAT_LIMIT = "10/minute"
PAYMENT_LIMIT = "20/minute"
