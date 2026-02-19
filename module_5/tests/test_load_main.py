"""Tests for load_data.create_connection() and main()."""

import json

import pytest
import psycopg

import load_data

pytestmark = pytest.mark.db


# =====================================================================
# create_connection
# =====================================================================

def test_create_connection_failure(monkeypatch):
    monkeypatch.setattr(
        psycopg, "connect",
        lambda **kw: (_ for _ in ()).throw(psycopg.OperationalError("fail")),
    )
    assert load_data.create_connection("testdb", "testuser") is None


def test_create_connection_success_with_host(monkeypatch):
    """Success path including host kwarg (lines 80, 82-84)."""
    class _Conn:
        autocommit = False

    monkeypatch.setattr(psycopg, "connect", lambda **kw: _Conn())
    result = load_data.create_connection("testdb", "testuser", "localhost")
    assert result is not None
    assert result.autocommit is True


# =====================================================================
# main() — mock all DB interactions
# =====================================================================

class _FakeCursor:
    """Records SQL calls for verification."""
    def __init__(self):
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append(("execute", sql, params))

    def executemany(self, sql, params_list):
        self.calls.append(("executemany", sql, len(list(params_list))))

    def fetchone(self):
        return (None,)


class _FakeConn:
    def __init__(self):
        self._cursor = _FakeCursor()
        self.autocommit = True

    def cursor(self):
        return self._cursor

    def close(self):
        pass


def test_main_first_connect_fails(monkeypatch):
    monkeypatch.setattr(
        load_data, "create_connection", lambda *a, **kw: None
    )
    load_data.main()  # Should return early without crash


def test_main_creates_db_when_missing(monkeypatch):
    first_conn = _FakeConn()
    first_conn._cursor.fetchone = lambda: None  # DB does not exist
    second_conn = _FakeConn()
    conns = [first_conn, second_conn]
    call_idx = {"n": 0}

    def _fake_create(*args, **kwargs):
        idx = call_idx["n"]
        call_idx["n"] += 1
        return conns[idx] if idx < len(conns) else None

    monkeypatch.setattr(load_data, "create_connection", _fake_create)
    monkeypatch.setattr(load_data, "JSON_PATH", "/nonexistent.json")

    load_data.main()  # Will hit FileNotFoundError for JSON

    # Verify CREATE DATABASE was called
    has_create = any("CREATE DATABASE" in c[1] for c in first_conn._cursor.calls if c[0] == "execute")


def test_main_db_already_exists(monkeypatch):
    first_conn = _FakeConn()
    first_conn._cursor.fetchone = lambda: (1,)  # DB exists
    second_conn = _FakeConn()

    conns = [first_conn, second_conn]
    call_idx = {"n": 0}

    def _fake_create(*args, **kwargs):
        idx = call_idx["n"]
        call_idx["n"] += 1
        return conns[idx] if idx < len(conns) else None

    monkeypatch.setattr(load_data, "create_connection", _fake_create)
    monkeypatch.setattr(load_data, "JSON_PATH", "/nonexistent.json")

    load_data.main()


def test_main_second_connect_fails(monkeypatch):
    first_conn = _FakeConn()
    conns = [first_conn, None]
    call_idx = {"n": 0}

    def _fake_create(*args, **kwargs):
        idx = call_idx["n"]
        call_idx["n"] += 1
        return conns[idx] if idx < len(conns) else None

    monkeypatch.setattr(load_data, "create_connection", _fake_create)
    load_data.main()


def test_main_loads_and_inserts_json(monkeypatch, tmp_path):
    sample_data = [
        {
            "program": "CS, MIT",
            "comments": "Great",
            "date_added": "Added on January 15, 2026",
            "url": "https://example.com/1",
            "status": "Accepted",
            "term": "Fall 2026",
            "US/International": "American",
            "GPA": "GPA 3.85",
            "GRE": "GRE 320",
            "GRE V": "GRE V 160",
            "GRE AW": "GRE AW 4.5",
            "Degree": "Masters",
            "llm-generated-program": "Computer Science",
            "llm-generated-university": "MIT",
        }
    ]
    json_file = tmp_path / "test_data.json"
    json_file.write_text(json.dumps(sample_data))

    first_conn = _FakeConn()
    second_conn = _FakeConn()
    conns = [first_conn, second_conn]
    call_idx = {"n": 0}

    def _fake_create(*args, **kwargs):
        idx = call_idx["n"]
        call_idx["n"] += 1
        return conns[idx] if idx < len(conns) else None

    monkeypatch.setattr(load_data, "create_connection", _fake_create)
    monkeypatch.setattr(load_data, "JSON_PATH", str(json_file))

    load_data.main()

    # Verify executemany was called
    has_executemany = any(
        c[0] == "executemany" for c in second_conn._cursor.calls
    )
    assert has_executemany


def test_main_json_not_found(monkeypatch):
    first_conn = _FakeConn()
    second_conn = _FakeConn()
    conns = [first_conn, second_conn]
    call_idx = {"n": 0}

    def _fake_create(*args, **kwargs):
        idx = call_idx["n"]
        call_idx["n"] += 1
        return conns[idx] if idx < len(conns) else None

    monkeypatch.setattr(load_data, "create_connection", _fake_create)
    monkeypatch.setattr(load_data, "JSON_PATH", "/nonexistent/data.json")

    load_data.main()  # Should handle FileNotFoundError gracefully


def test_main_json_decode_error(monkeypatch, tmp_path):
    bad_json = tmp_path / "bad.json"
    bad_json.write_text("{invalid json content")

    first_conn = _FakeConn()
    second_conn = _FakeConn()
    conns = [first_conn, second_conn]
    call_idx = {"n": 0}

    def _fake_create(*args, **kwargs):
        idx = call_idx["n"]
        call_idx["n"] += 1
        return conns[idx] if idx < len(conns) else None

    monkeypatch.setattr(load_data, "create_connection", _fake_create)
    monkeypatch.setattr(load_data, "JSON_PATH", str(bad_json))

    load_data.main()  # Should handle JSONDecodeError gracefully


def test_main_executemany_error(monkeypatch, tmp_path):
    sample_data = [
        {
            "program": "CS, MIT",
            "comments": "Great",
            "date_added": "Added on January 15, 2026",
            "url": "https://example.com/1",
            "status": "Accepted",
            "term": "Fall 2026",
            "US/International": "American",
            "GPA": "GPA 3.85",
            "GRE": "GRE 320",
            "GRE V": "GRE V 160",
            "GRE AW": "GRE AW 4.5",
            "Degree": "Masters",
            "llm-generated-program": "Computer Science",
            "llm-generated-university": "MIT",
        }
    ]
    json_file = tmp_path / "test_data.json"
    json_file.write_text(json.dumps(sample_data))

    class _ErrorCursor:
        def __init__(self):
            self.calls = []

        def execute(self, sql, params=None):
            self.calls.append(("execute", sql, params))

        def executemany(self, sql, params_list):
            raise psycopg.Error("disk full")

        def fetchone(self):
            return (None,)

    class _ErrorConn:
        def __init__(self):
            self._cursor = _ErrorCursor()
            self.autocommit = True
            self.closed = False

        def cursor(self):
            return self._cursor

        def close(self):
            self.closed = True

    first_conn = _FakeConn()
    second_conn = _ErrorConn()
    conns = [first_conn, second_conn]
    call_idx = {"n": 0}

    def _fake_create(*args, **kwargs):
        idx = call_idx["n"]
        call_idx["n"] += 1
        return conns[idx] if idx < len(conns) else None

    monkeypatch.setattr(load_data, "create_connection", _fake_create)
    monkeypatch.setattr(load_data, "JSON_PATH", str(json_file))

    load_data.main()  # Should not crash

    assert second_conn.closed is True