"""Shared fixtures and mock data for module_4 tests."""

import os
import sys
from decimal import Decimal

import pytest

# ---------------------------------------------------------------------------
# Path setup – make ``module_4/source/`` importable
# ---------------------------------------------------------------------------
SOURCE_DIR = os.path.join(os.path.dirname(__file__), os.pardir, "source")
SOURCE_DIR = os.path.abspath(SOURCE_DIR)
if SOURCE_DIR not in sys.path:
    sys.path.insert(0, SOURCE_DIR)

from query_data import DB_CONFIG  # noqa: E402

# ---------------------------------------------------------------------------
# Mock query data (Decimal values match what psycopg returns from ROUND)
# ---------------------------------------------------------------------------
MOCK_QUERY_DATA = {
    "total_count": 50000,
    "fall_2026_count": 12000,
    "international_pct": Decimal("32.17"),
    "avg_gpa": Decimal("3.52"),
    "avg_gre": Decimal("318.45"),
    "avg_gre_v": Decimal("157.23"),
    "avg_gre_aw": Decimal("3.98"),
    "american_gpa_fall2026": Decimal("3.61"),
    "acceptance_pct_fall2026": Decimal("24.53"),
    "accepted_gpa_fall2026": Decimal("3.74"),
    "jhu_cs_masters": 42,
    "phd_cs_program": 5,
    "phd_cs_llm": 8,
    "top_programs": [
        ("Computer Science", 1200),
        ("Electrical Engineering", 800),
        ("Mechanical Engineering", 600),
        ("Data Science", 550),
        ("Biology", 500),
        ("Physics", 480),
        ("Chemistry", 450),
        ("Mathematics", 430),
        ("Psychology", 400),
        ("Economics", 380),
    ],
    "top_universities": [
        ("Stanford University", 300),
        ("MIT", 280),
        ("Harvard University", 270),
        ("UC Berkeley", 250),
        ("Carnegie Mellon University", 240),
        ("Georgia Tech", 230),
        ("University of Michigan", 220),
        ("Columbia University", 210),
        ("Cornell University", 200),
        ("UCLA", 190),
    ],
    "rate_by_degree": [
        ("Masters", 5000, 1238, Decimal("24.76")),
        ("PhD", 3000, 600, Decimal("20.00")),
        ("PsyD", 420, 130, Decimal("30.95")),
    ],
    "rate_by_nationality": [
        ("American", 4500, 1135, Decimal("25.23")),
        ("International", 7500, 1748, Decimal("23.30")),
    ],
}


# ---------------------------------------------------------------------------
# Shared stubs — imported by test files via ``from conftest import ...``
# ---------------------------------------------------------------------------

class FakeResponse:
    """Stub for ``urllib.request.urlopen`` return value."""
    def __init__(self, html):
        self._data = html.encode("utf-8")

    def read(self):
        return self._data


class NoCloseConn:
    """Wraps a real connection for both context-manager and direct usage.

    Suppresses ``close()`` and ``autocommit`` changes so the SAVEPOINT
    stays intact during tests.
    """
    def __init__(self, real_conn):
        self._conn = real_conn

    @property
    def autocommit(self):
        return self._conn.autocommit

    @autocommit.setter
    def autocommit(self, value):
        pass

    def cursor(self):
        return self._conn.cursor()

    def close(self):
        pass

    def commit(self):
        pass

    def rollback(self):
        pass

    def __enter__(self):
        return self._conn

    def __exit__(self, *args):
        pass


class FakeCursor:
    """Cursor stub that reports ``rowcount=0`` (duplicate / no-op)."""
    rowcount = 0

    def execute(self, *args, **kwargs):
        pass


class FakeInsertCursor:
    """Cursor stub that reports ``rowcount=1`` (successful insert)."""
    rowcount = 1

    def execute(self, *args, **kwargs):
        pass


class FakePullConn:
    """Connection stub returning ``FakeCursor`` (rowcount=0)."""
    autocommit = True

    def cursor(self):
        return FakeCursor()

    def close(self):
        pass

    def commit(self):
        pass

    def rollback(self):
        pass


class FakeInsertConn:
    """Connection stub returning ``FakeInsertCursor`` (rowcount=1)."""
    autocommit = True

    def cursor(self):
        return FakeInsertCursor()

    def close(self):
        pass

    def commit(self):
        pass

    def rollback(self):
        pass


# ---------------------------------------------------------------------------
# Lightweight stub used by the client fixture to satisfy psycopg.connect
# in the index() route (which uses ``with psycopg.connect(...) as conn:``)
# ---------------------------------------------------------------------------
class _FakeConn:
    """Minimal context-manager stand-in for a psycopg connection."""
    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


@pytest.fixture()
def client(monkeypatch):
    """Flask test client with run_queries and psycopg.connect mocked."""
    import app as app_module

    monkeypatch.setattr(app_module, "run_queries", lambda _conn: MOCK_QUERY_DATA)
    monkeypatch.setattr(app_module.psycopg, "connect", lambda **kw: _FakeConn())

    test_app = app_module.create_app(testing=True)
    with test_app.test_client() as c:
        yield c


@pytest.fixture()
def db_conn():
    """Real PostgreSQL connection wrapped in a SAVEPOINT for rollback.

    Yields ``(conn, cur)``.  Rolls back on teardown so tests leave no trace.
    Skips automatically when the database is unavailable.
    """
    import psycopg
    try:
        conn = psycopg.connect(**DB_CONFIG)
    except psycopg.OperationalError:
        pytest.skip("PostgreSQL not available")
        return

    conn.autocommit = False
    cur = conn.cursor()
    cur.execute("SAVEPOINT test_sp")

    yield conn, cur

    cur.execute("ROLLBACK TO SAVEPOINT test_sp")
    conn.close()
