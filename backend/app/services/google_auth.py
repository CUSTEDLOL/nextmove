"""
Server-side Google OAuth2 authorization-code exchange.

The frontend sends the authorization code it received from Google.
This module exchanges it for tokens using our client secret (never
exposed to the browser), then verifies the id_token so the email
is cryptographically confirmed — not self-reported by the caller.
"""
import logging

from google.auth.exceptions import GoogleAuthError
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from google_auth_oauthlib.flow import Flow

from app.config import settings

logger = logging.getLogger(__name__)

_SCOPES = [
    "openid",
    "email",
    "profile",
    "https://www.googleapis.com/auth/calendar",
]

_CLIENT_CONFIG = {
    "web": {
        "client_id": None,          # filled lazily from settings
        "client_secret": None,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": [],
    }
}


def exchange_code_for_user_info(code: str, redirect_uri: str) -> dict:
    """
    Exchange an authorization code for verified user info.

    Returns:
        {
            "email": str,           # verified by Google id_token
            "name": str | None,
            "access_token": str,
            "refresh_token": str | None,
        }

    Raises:
        ValueError: if the code is invalid, expired, or the id_token
                    cannot be verified.
    """
    client_config = {
        "web": {
            **_CLIENT_CONFIG["web"],
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "redirect_uris": [redirect_uri],
        }
    }

    try:
        flow = Flow.from_client_config(
            client_config,
            scopes=_SCOPES,
            redirect_uri=redirect_uri,
        )
        flow.fetch_token(code=code)
        credentials = flow.credentials
    except Exception as exc:
        logger.warning("Google code exchange failed: %s", exc)
        raise ValueError(f"Google code exchange failed: {exc}") from exc

    try:
        id_info = google_id_token.verify_oauth2_token(
            credentials.id_token,
            google_requests.Request(),
            settings.google_client_id,
        )
    except (GoogleAuthError, ValueError) as exc:
        logger.warning("Google id_token verification failed: %s", exc)
        raise ValueError(f"Could not verify Google identity: {exc}") from exc

    return {
        "email": id_info["email"],
        "name": id_info.get("name"),
        "access_token": credentials.token,
        "refresh_token": credentials.refresh_token,
    }
