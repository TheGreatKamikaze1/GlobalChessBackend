from pydantic import BaseSettings, AnyHttpUrl

class Settings(BaseSettings):
    PAYSTACK_SECRET_KEY: str
    STRIPE_SECRET_KEY: str
    STRIPE_WEBHOOK_SECRET: str

    PAYSTACK_BASE_URL: AnyHttpUrl = "https://api.paystack.co"

    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
