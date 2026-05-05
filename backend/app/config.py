from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    redis_url: str = "redis://localhost:6379"
    openai_api_key: str = ""
    google_client_id: str = ""
    google_client_secret: str = ""
    telegram_bot_token: str = ""
    telegram_bot_username: str = ""
    jwt_secret_key: str = "dev-secret-change-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7  # 7 days
    web_url: str = "http://localhost:3000"
    telegram_webhook_secret: str = ""
    fernet_key: str = ""  # base64 Fernet key; empty = dev default (insecure)

    class Config:
        env_file = ("../.env", ".env")
        extra = "ignore"


settings = Settings()
