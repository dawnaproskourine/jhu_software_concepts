"""Tests for cleanup_data.main()."""

import pytest
import psycopg

import cleanup_data

pytestmark = pytest.mark.db


class _FakeConn:
    autocommit = True

    def close(self):
        pass


def test_main_runs_both_fixes(monkeypatch):
    conn = _FakeConn()
    monkeypatch.setattr(
        psycopg, "connect", lambda **kw: conn
    )

    calls = []
    monkeypatch.setattr(
        cleanup_data, "fix_gre_aw", lambda c: (calls.append("gre"), 2)[1]
    )
    monkeypatch.setattr(
        cleanup_data, "fix_uc_universities", lambda c: (calls.append("uc"), 1)[1]
    )

    cleanup_data.main()
    assert "gre" in calls
    assert "uc" in calls


def test_main_db_error(monkeypatch):
    monkeypatch.setattr(
        psycopg, "connect",
        lambda **kw: (_ for _ in ()).throw(psycopg.OperationalError("fail")),
    )
    cleanup_data.main()  # Should return without crash