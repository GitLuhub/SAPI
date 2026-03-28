"""Tests for db.session and deps get_db generators."""
from unittest.mock import MagicMock, patch

import pytest


def test_session_get_db_closes_on_exit():
    """Verifies that session.get_db yields a session and closes it in the finally block."""
    mock_db = MagicMock()
    with patch("app.db.session.SessionLocal", return_value=mock_db):
        import app.db.session as session_module
        gen = session_module.get_db()
        result = next(gen)
        assert result is mock_db
        try:
            next(gen)
        except StopIteration:
            pass
    mock_db.close.assert_called_once()


def test_deps_get_db_closes_on_exit():
    """Verifies that deps.get_db yields a session and closes it in the finally block."""
    mock_db = MagicMock()
    with patch("app.api.v1.deps.SessionLocal", return_value=mock_db):
        import app.api.v1.deps as deps_module
        gen = deps_module.get_db()
        result = next(gen)
        assert result is mock_db
        try:
            next(gen)
        except StopIteration:
            pass
    mock_db.close.assert_called_once()
