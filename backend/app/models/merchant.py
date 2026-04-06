# Merchant model — stores per-merchant email and Shopify configuration
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
import uuid


class MerchantCreate(BaseModel):
    name: str
    support_email: str
    mailgun_api_key: str
    mailgun_domain: str
    shopify_store_domain: Optional[str] = ""
    shopify_access_token: Optional[str] = ""
    # WhatsApp config (per-merchant)
    whatsapp_phone_number_id: Optional[str] = ""
    whatsapp_waba_id: Optional[str] = ""
    whatsapp_access_token: Optional[str] = ""
    whatsapp_verify_token: Optional[str] = ""
    whatsapp_app_secret: Optional[str] = ""
    # Instagram config (per-merchant) — disabled
    # instagram_page_id: Optional[str] = ""
    # instagram_access_token: Optional[str] = ""
    # instagram_app_secret: Optional[str] = ""
    # instagram_verify_token: Optional[str] = ""
    # Twitter config (per-merchant) — disabled
    # twitter_api_key: Optional[str] = ""
    # twitter_api_secret: Optional[str] = ""
    # twitter_access_token: Optional[str] = ""
    # twitter_access_token_secret: Optional[str] = ""
    # twitter_bearer_token: Optional[str] = ""
    # twitter_env_name: Optional[str] = "production"
    # twitter_user_id: Optional[str] = ""


class MerchantUpdate(BaseModel):
    name: Optional[str] = None
    support_email: Optional[str] = None
    mailgun_api_key: Optional[str] = None
    mailgun_domain: Optional[str] = None
    shopify_store_domain: Optional[str] = None
    shopify_access_token: Optional[str] = None
    is_active: Optional[bool] = None
    # WhatsApp config
    whatsapp_phone_number_id: Optional[str] = None
    whatsapp_waba_id: Optional[str] = None
    whatsapp_access_token: Optional[str] = None
    whatsapp_verify_token: Optional[str] = None
    whatsapp_app_secret: Optional[str] = None
    # Instagram config — disabled
    # instagram_page_id: Optional[str] = None
    # instagram_access_token: Optional[str] = None
    # instagram_app_secret: Optional[str] = None
    # instagram_verify_token: Optional[str] = None
    # Twitter config — disabled
    # twitter_api_key: Optional[str] = None
    # twitter_api_secret: Optional[str] = None
    # twitter_access_token: Optional[str] = None
    # twitter_access_token_secret: Optional[str] = None
    # twitter_bearer_token: Optional[str] = None
    # twitter_env_name: Optional[str] = None
    # twitter_user_id: Optional[str] = None


class MerchantInDB(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    support_email: str
    mailgun_api_key: str
    mailgun_domain: str
    shopify_store_domain: str = ""
    shopify_access_token: str = ""
    # WhatsApp config
    whatsapp_phone_number_id: str = ""
    whatsapp_waba_id: str = ""
    whatsapp_access_token: str = ""
    whatsapp_verify_token: str = ""
    whatsapp_app_secret: str = ""
    # Instagram config — disabled
    # instagram_page_id: str = ""
    # instagram_access_token: str = ""
    # instagram_app_secret: str = ""
    # instagram_verify_token: str = ""
    # Twitter config — disabled
    # twitter_api_key: str = ""
    # twitter_api_secret: str = ""
    # twitter_access_token: str = ""
    # twitter_access_token_secret: str = ""
    # twitter_bearer_token: str = ""
    # twitter_env_name: str = "production"
    # twitter_user_id: str = ""
    # API key authentication fields
    api_key_hash: str = ""
    api_key_prefix: str = ""
    permissions: List[str] = ["create_ticket"]
    rate_limit: int = 100  # requests per minute
    created_by: Optional[str] = None
    last_used_at: Optional[datetime] = None
    app_name: str = ""
    installed_at: Optional[datetime] = None
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
