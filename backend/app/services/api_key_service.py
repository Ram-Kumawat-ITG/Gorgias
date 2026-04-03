# API key generation and verification for external merchant authentication.
# Keys use the format: ghd_live_<40 hex chars> (prefix "ghd" = Gorgias Helpdesk)
# Only the SHA-256 hash is stored — the raw key is shown once at creation time.
import hashlib
import secrets


PREFIX = "ghd_live_"


def generate_api_key() -> str:
    """Generate a secure, unique API key with the ghd_live_ prefix."""
    random_part = secrets.token_hex(20)  # 40 hex chars
    return f"{PREFIX}{random_part}"


def hash_api_key(raw_key: str) -> str:
    """Hash an API key using SHA-256 for storage."""
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def verify_api_key(raw_key: str, stored_hash: str) -> bool:
    """Verify a raw API key against a stored SHA-256 hash."""
    return secrets.compare_digest(hash_api_key(raw_key), stored_hash)


def get_key_prefix(raw_key: str) -> str:
    """Return the first 16 characters of the key for identification."""
    return raw_key[:16] + "..."
