from pydantic import BaseModel, EmailStr, Field

class PaystackPayment(BaseModel):
    email: EmailStr
    amount: int = Field(..., gt=0, description="Amount in naira")
    access_token: str




#class StripePayment(BaseModel):
  #  amount: int = Field(..., gt=0, description="Amount in cents")
   # currency: str = Field(default="usd", min_length=3, max_length=3)
