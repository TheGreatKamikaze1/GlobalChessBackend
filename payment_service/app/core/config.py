from pydantic import AnyHttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str

    PAYSTACK_SECRET_KEY: str
    PAYSTACK_BASE_URL: AnyHttpUrl = "https://api.paystack.co"

  
    # CORE_API_BASE_URL="https://globalchessbackend-production.up.railway.app"
    CORE_API_BASE_URL: AnyHttpUrl | None = None

   
    STRIPE_SECRET_KEY: str | None = None
    STRIPE_WEBHOOK_SECRET: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


settings = Settings()
