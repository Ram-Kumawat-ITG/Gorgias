# Application configuration — reads from .env via pydantic-settings
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    mongodb_url: str
    mongodb_db_name: str = "helpdesk"
    # Seniors' chatbot database (Database B) — optional
    mongodb_b_url: str = ""
    mongodb_b_name: str = "chatbot"
    shopify_api_key: str = ""
    shopify_api_secret: str = ""
    shopify_store_domain: str = ""
    shopify_access_token: str = ""
    openai_api_key: str = ""
    groq_api_key: str = ""
    secret_key: str  # required — no default; app will refuse to start if unset
    cors_origins: str = ""  # comma-separated list e.g. "https://app.example.com,https://admin.example.com"
    mailgun_api_key: str = ""
    mailgun_domain: str = ""
    mailgun_webhook_signing_key: str = ""
    meta_app_secret: str = ""
    meta_verify_token: str = "helpdesk_ig_verify"
    meta_page_access_token: str = ""
    # WhatsApp Cloud API (Meta)
    whatsapp_app_id: str = ""
    whatsapp_app_secret: str = ""
    whatsapp_access_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_waba_id: str = ""
    whatsapp_verify_token: str = ""
    # Instagram Messenger API (Meta)
    instagram_page_id: str = ""
    instagram_access_token: str = ""
    instagram_app_secret: str = ""
    instagram_verify_token: str = ""
    # Twitter / X API
    twitter_api_key: str = ""
    twitter_api_secret: str = ""
    twitter_access_token: str = ""
    twitter_access_token_secret: str = ""
    twitter_bearer_token: str = ""
    twitter_env_name: str = "production"

    class Config:
        env_file = ".env"


settings = Settings()
