import pytest
from app.services.auth import (
    hash_password, verify_password, create_access_token, decode_token
)


def test_hash_and_verify_password():
    password = "mypassword123"
    hashed = hash_password(password)
    assert hashed != password
    assert verify_password(password, hashed)
    assert not verify_password("wrongpassword", hashed)


def test_create_and_decode_token():
    token = create_access_token({"sub": "user-uuid-123"})
    payload = decode_token(token)
    assert payload["sub"] == "user-uuid-123"


def test_decode_invalid_token():
    with pytest.raises(ValueError):
        decode_token("not.a.real.token")
