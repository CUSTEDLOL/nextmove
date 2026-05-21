"""
Tests for token encryption (C-5).
All tests run without a DB — the TypeDecorator and helpers are pure Python.
"""
import pytest


def test_encrypt_decrypt_roundtrip():
    """Encrypting then decrypting a token returns the original value."""
    from app.services.crypto import encrypt_token, decrypt_token
    original = "ya29.a0AfH6SMBx_real_google_access_token"
    encrypted = encrypt_token(original)
    assert decrypt_token(encrypted) == original


def test_encrypted_value_does_not_contain_plaintext():
    """The stored value must not contain the raw token string."""
    from app.services.crypto import encrypt_token
    token = "ya29.sensitive_access_token"
    encrypted = encrypt_token(token)
    assert token not in encrypted


def test_encrypt_produces_different_ciphertext_each_call():
    """Fernet uses a random IV — same plaintext must not produce same ciphertext."""
    from app.services.crypto import encrypt_token
    token = "ya29.same_token"
    assert encrypt_token(token) != encrypt_token(token)


def test_encrypt_none_returns_none():
    from app.services.crypto import encrypt_token
    assert encrypt_token(None) is None


def test_decrypt_none_returns_none():
    from app.services.crypto import decrypt_token
    assert decrypt_token(None) is None


def test_encrypted_string_type_roundtrip():
    """EncryptedString TypeDecorator encrypts on bind and decrypts on result."""
    from app.services.crypto import EncryptedString
    col = EncryptedString()
    plaintext = "refresh_token_secret"
    stored = col.process_bind_param(plaintext, dialect=None)
    assert stored != plaintext
    recovered = col.process_result_value(stored, dialect=None)
    assert recovered == plaintext


def test_encrypted_string_type_handles_none():
    from app.services.crypto import EncryptedString
    col = EncryptedString()
    assert col.process_bind_param(None, dialect=None) is None
    assert col.process_result_value(None, dialect=None) is None


def test_encrypted_string_falls_back_on_legacy_plaintext():
    """
    Values written before encryption was enabled (plaintext) must be returned
    as-is so existing users aren't locked out immediately after deployment.
    """
    from app.services.crypto import EncryptedString
    col = EncryptedString()
    legacy_plaintext = "ya29.legacy_token_not_yet_encrypted"
    # process_result_value receives the raw DB string (plaintext here)
    recovered = col.process_result_value(legacy_plaintext, dialect=None)
    assert recovered == legacy_plaintext
