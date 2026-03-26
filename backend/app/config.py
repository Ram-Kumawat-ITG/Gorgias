# Application configuration — reads from .env via pydantic-settings
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    mongodb_url: str
    mongodb_db_name: str = "helpdesk"
    shopify_api_key: str = ""
    shopify_api_secret: str = ""
    shopify_store_domain: str = ""
    shopify_access_token: str = ""
    openai_api_key: str = ""
    secret_key: str = "default-dev-secret-change-in-production-minimum-32-chars"
    mailgun_api_key: str = ""
    mailgun_domain: str = ""

    class Config:
        env_file = ".env"


settings = Settings()
