import os
from dotenv import load_dotenv

load_dotenv() 

PAYSTACK_SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY")
PAYSTACK_BASE_URL = os.getenv("PAYSTACK_BASE_URL", "https://api.paystack.co")
REDIS_URL = os.getenv(
    "REDIS_URL",
    "redis://default:TnDyjVnpzCrLseOHGSfqSKwioHUhfdcL@redis.railway.internal:6379"
)

