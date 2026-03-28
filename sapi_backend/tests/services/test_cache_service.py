"""
Unit tests for CacheService (app/services/cache_service.py).

All tests patch the Redis client so no real Redis is required.
"""
from unittest.mock import MagicMock, patch
import json
import pytest

import app.services.cache_service as cache_module
from app.services.cache_service import CacheService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_redis():
    """Returns a MagicMock that looks like a connected redis.Redis client."""
    mock = MagicMock()
    mock.ping.return_value = True
    return mock


def _reset_singleton():
    """Clears the module-level _redis_client so each test starts fresh."""
    cache_module._redis_client = None


# ---------------------------------------------------------------------------
# _get_redis
# ---------------------------------------------------------------------------

def test_get_redis_returns_none_when_unavailable():
    _reset_singleton()
    with patch("app.services.cache_service.redis.from_url", side_effect=Exception("no redis")):
        client = cache_module._get_redis()
    assert client is None


def test_get_redis_caches_client():
    _reset_singleton()
    mock_client = _make_mock_redis()
    with patch("app.services.cache_service.redis.from_url", return_value=mock_client):
        c1 = cache_module._get_redis()
        c2 = cache_module._get_redis()
    assert c1 is c2  # same instance returned on second call


def test_get_redis_ping_failure_returns_none():
    _reset_singleton()
    mock_client = _make_mock_redis()
    mock_client.ping.side_effect = Exception("ping failed")
    with patch("app.services.cache_service.redis.from_url", return_value=mock_client):
        client = cache_module._get_redis()
    assert client is None


# ---------------------------------------------------------------------------
# CacheService.get
# ---------------------------------------------------------------------------

def test_cache_get_returns_none_when_no_redis():
    _reset_singleton()
    svc = CacheService()
    with patch("app.services.cache_service._get_redis", return_value=None):
        result = svc.get("any_key")
    assert result is None


def test_cache_get_returns_deserialized_value():
    _reset_singleton()
    mock_client = _make_mock_redis()
    mock_client.get.return_value = json.dumps({"foo": "bar"})
    svc = CacheService()
    with patch("app.services.cache_service._get_redis", return_value=mock_client):
        result = svc.get("my_key")
    assert result == {"foo": "bar"}


def test_cache_get_returns_none_when_key_missing():
    _reset_singleton()
    mock_client = _make_mock_redis()
    mock_client.get.return_value = None
    svc = CacheService()
    with patch("app.services.cache_service._get_redis", return_value=mock_client):
        result = svc.get("missing_key")
    assert result is None


def test_cache_get_handles_exception():
    _reset_singleton()
    mock_client = _make_mock_redis()
    mock_client.get.side_effect = Exception("redis error")
    svc = CacheService()
    with patch("app.services.cache_service._get_redis", return_value=mock_client):
        result = svc.get("bad_key")
    assert result is None


# ---------------------------------------------------------------------------
# CacheService.set
# ---------------------------------------------------------------------------

def test_cache_set_does_nothing_when_no_redis():
    _reset_singleton()
    svc = CacheService()
    with patch("app.services.cache_service._get_redis", return_value=None):
        svc.set("key", "value")  # should not raise


def test_cache_set_calls_setex():
    _reset_singleton()
    mock_client = _make_mock_redis()
    svc = CacheService()
    with patch("app.services.cache_service._get_redis", return_value=mock_client):
        svc.set("key", {"data": 1}, ttl=60)
    mock_client.setex.assert_called_once_with("key", 60, json.dumps({"data": 1}, default=str))


def test_cache_set_handles_exception():
    _reset_singleton()
    mock_client = _make_mock_redis()
    mock_client.setex.side_effect = Exception("write error")
    svc = CacheService()
    with patch("app.services.cache_service._get_redis", return_value=mock_client):
        svc.set("key", "value")  # should not raise


# ---------------------------------------------------------------------------
# CacheService.delete
# ---------------------------------------------------------------------------

def test_cache_delete_does_nothing_when_no_redis():
    _reset_singleton()
    svc = CacheService()
    with patch("app.services.cache_service._get_redis", return_value=None):
        svc.delete("key")  # should not raise


def test_cache_delete_calls_delete():
    _reset_singleton()
    mock_client = _make_mock_redis()
    svc = CacheService()
    with patch("app.services.cache_service._get_redis", return_value=mock_client):
        svc.delete("mykey")
    mock_client.delete.assert_called_once_with("mykey")


def test_cache_delete_handles_exception():
    _reset_singleton()
    mock_client = _make_mock_redis()
    mock_client.delete.side_effect = Exception("delete error")
    svc = CacheService()
    with patch("app.services.cache_service._get_redis", return_value=mock_client):
        svc.delete("key")  # should not raise


# ---------------------------------------------------------------------------
# CacheService.delete_pattern
# ---------------------------------------------------------------------------

def test_cache_delete_pattern_does_nothing_when_no_redis():
    _reset_singleton()
    svc = CacheService()
    with patch("app.services.cache_service._get_redis", return_value=None):
        svc.delete_pattern("prefix:*")  # should not raise


def test_cache_delete_pattern_deletes_matching_keys():
    _reset_singleton()
    mock_client = _make_mock_redis()
    mock_client.keys.return_value = ["prefix:a", "prefix:b"]
    svc = CacheService()
    with patch("app.services.cache_service._get_redis", return_value=mock_client):
        svc.delete_pattern("prefix:*")
    mock_client.delete.assert_called_once_with("prefix:a", "prefix:b")


def test_cache_delete_pattern_no_keys_found():
    _reset_singleton()
    mock_client = _make_mock_redis()
    mock_client.keys.return_value = []
    svc = CacheService()
    with patch("app.services.cache_service._get_redis", return_value=mock_client):
        svc.delete_pattern("prefix:*")
    mock_client.delete.assert_not_called()


def test_cache_delete_pattern_handles_exception():
    _reset_singleton()
    mock_client = _make_mock_redis()
    mock_client.keys.side_effect = Exception("pattern error")
    svc = CacheService()
    with patch("app.services.cache_service._get_redis", return_value=mock_client):
        svc.delete_pattern("prefix:*")  # should not raise
