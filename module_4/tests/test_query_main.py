"""Tests for query_data.main() — console output."""

import pytest
from conftest import MOCK_QUERY_DATA

import query_data

pytestmark = pytest.mark.db


def test_main_prints_results(monkeypatch, capsys):
    class _FakeConn:
        autocommit = True
        def close(self):
            pass

    monkeypatch.setattr(
        query_data.psycopg, "connect", lambda **kw: _FakeConn()
    )
    monkeypatch.setattr(query_data, "run_queries", lambda conn: MOCK_QUERY_DATA)

    query_data.main()
    out = capsys.readouterr().out

    assert "Total applicants:" in out
    assert "Fall 2026 applicants:" in out
    assert "International student percentage:" in out
    assert "Average GPA:" in out
    assert "Top 10 most popular programs:" in out
    assert "Top 10 most popular universities:" in out
    assert "Acceptance rate by degree type:" in out
    assert "Acceptance rate by nationality:" in out


def test_main_db_error(monkeypatch):
    monkeypatch.setattr(
        query_data.psycopg, "connect",
        lambda **kw: (_ for _ in ()).throw(query_data.OperationalError("fail")),
    )
    # Should return without crashing
    query_data.main()


def test_build_db_config_uses_database_url(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://myuser:secret@myhost:5433/mydb")
    config = query_data._build_db_config()
    assert config == {
        "dbname": "mydb",
        "user": "myuser",
        "host": "myhost",
        "port": 5433,
        "password": "secret",
    }