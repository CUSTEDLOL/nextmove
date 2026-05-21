"""
Transparent encryption for sensitive DB columns (Google OAuth tokens).

Uses Fernet symmetric encryption (AES-128-CBC + HMAC-SHA256).
The FERNET_KEY env var must be a URL-safe base64-encoded 32-byte key,
generated with:  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

A stable dev-only fallback key is used when FERNET_KEY is not set, with a
warning logged at every use. Set FERNET_KEY in production.
"""
import logging

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import String, TypeDecorator

from app.config import settings

logger = logging.getLogger(__name__)

# Stable key for local development only — never use in production.
_DEV_KEY = b"ZmDfcTF7_60GrrY167zsiPd67pEvs0aGOv2oasOM1Pg="


def _get_fernet() -> Fernet:
    raw = settings.fernet_key.strip() if settings.fernet_key else ""
    key = raw.encode() if raw else _DEV_KEY
    if key == _DEV_KEY:
        logger.warning(
            "Using dev Fernet key for token encryption — "
            "set FERNET_KEY in production to a real key"
        )
    return Fernet(key)


def encrypt_token(value: str | None) -> str | None:
    if value is None:
        return None
    return _get_fernet().encrypt(value.encode()).decode()


def decrypt_token(value: str | None) -> str | None:
    if value is None:
        return None
    return _get_fernet().decrypt(value.encode()).decode()


class EncryptedString(TypeDecorator):
    """
    SQLAlchemy column type that encrypts on write and decrypts on read.
    Drop-in replacement for String on sensitive columns.

    Legacy plaintext values (written before encryption was enabled) are
    returned as-is so existing users aren't immediately locked out.
    A warning is logged so they can be rotated.
    """

    impl = String
    cache_ok = True

    def process_bind_param(self, value: str | None, dialect) -> str | None:
        return encrypt_token(value)

    def process_result_value(self, value: str | None, dialect) -> str | None:
        if value is None:
            return None
        try:
            return decrypt_token(value)
        except (InvalidToken, Exception):
            logger.warning(
                "Token decryption failed — value appears to be legacy plaintext. "
                "Re-auth required to rotate this token."
            )
            return value
