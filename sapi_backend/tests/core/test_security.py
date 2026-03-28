from datetime import timedelta

import pytest

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
    get_password_hash,
    verify_password,
)


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------

def test_get_password_hash_returns_string():
    h = get_password_hash("mysecret")
    assert isinstance(h, str)
    assert h != "mysecret"


def test_verify_password_correct():
    h = get_password_hash("correctpassword")
    assert verify_password("correctpassword", h) is True


def test_verify_password_wrong():
    h = get_password_hash("correctpassword")
    assert verify_password("wrongpassword", h) is False


def test_password_hash_is_different_each_time():
    h1 = get_password_hash("same")
    h2 = get_password_hash("same")
    assert h1 != h2  # bcrypt salts are random


# ---------------------------------------------------------------------------
# Access token
# ---------------------------------------------------------------------------

def test_create_and_decode_access_token():
    token = create_access_token(subject="user-123")
    subject = decode_access_token(token)
    assert subject == "user-123"


def test_access_token_with_custom_expiry():
    token = create_access_token(subject="user-abc", expires_delta=timedelta(minutes=5))
    assert decode_access_token(token) == "user-abc"


def test_decode_access_token_invalid_string():
    assert decode_access_token("not.a.valid.token") is None


def test_decode_access_token_rejects_refresh_token():
    """A refresh token must not be accepted by decode_access_token."""
    refresh = create_refresh_token(subject="user-xyz")
    assert decode_access_token(refresh) is None


def test_access_token_expired():
    token = create_access_token(subject="user-exp", expires_delta=timedelta(seconds=-1))
    assert decode_access_token(token) is None


# ---------------------------------------------------------------------------
# Refresh token
# ---------------------------------------------------------------------------

def test_create_and_decode_refresh_token():
    token = create_refresh_token(subject="user-456")
    subject = decode_refresh_token(token)
    assert subject == "user-456"


def test_decode_refresh_token_invalid_string():
    assert decode_refresh_token("not.a.valid.token") is None


def test_decode_refresh_token_rejects_access_token():
    """An access token must not be accepted by decode_refresh_token."""
    access = create_access_token(subject="user-xyz")
    assert decode_refresh_token(access) is None


def test_refresh_token_expired():
    token = create_refresh_token(subject="user-exp", expires_delta=timedelta(seconds=-1))
    assert decode_refresh_token(token) is None
