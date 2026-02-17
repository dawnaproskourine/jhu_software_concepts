"""Tests for app.py error handling paths."""
# pylint: disable=C0116,R0903,W0613,C0415,E1101,R0801,W0212

import uuid
from urllib.error import URLError

import pytest
import psycopg
from psycopg import OperationalError

from conftest import FakeResponse, FakePullConn, NoCloseConn
import app as app_module
import scrape


# =====================================================================
# GET / — database error renders error page
# =====================================================================

@pytest.mark.web
def test_index_db_error_renders_error(monkeypatch):
    def _raise(**kw):
        raise OperationalError("db down")

    monkeypatch.setattr(app_module.psycopg, "connect", _raise)
    test_app = app_module.create_app(testing=True)
    with test_app.test_client() as c:
        resp = c.get("/")
    # App catches OperationalError, logs it, and still renders the page
    assert resp.status_code == 200


# =====================================================================
# POST /pull-data — invalid max_pages defaults
# =====================================================================

@pytest.mark.buttons
def test_pull_data_invalid_max_pages_defaults(monkeypatch):
    fake_html = "<html><body><table><tbody></tbody></table></body></html>"
    monkeypatch.setattr(app_module, "fix_gre_aw", lambda _c: 0)
    monkeypatch.setattr(app_module, "fix_uc_universities", lambda _c: 0)
    monkeypatch.setattr(app_module.psycopg, "connect", lambda **kw: FakePullConn())
    monkeypatch.setattr(app_module, "run_queries", lambda _c: {})
    monkeypatch.setattr(app_module, "fetch_page", lambda url, *a, **kw: fake_html)
    monkeypatch.setattr(app_module, "parse_survey", lambda html: [])
    monkeypatch.setattr(app_module, "get_max_pages", lambda html: 1)

    test_app = app_module.create_app(testing=True)
    with test_app.test_client() as c:
        resp = c.post("/pull-data", json={"max_pages": "not-a-number"})
    assert resp.status_code == 200


# =====================================================================
# POST /pull-data — DB connect failure returns 500
# =====================================================================

@pytest.mark.buttons
def test_pull_data_db_connect_fails_500(monkeypatch):
    monkeypatch.setattr(app_module, "run_queries", lambda _c: {})
    monkeypatch.setattr(
        app_module.psycopg, "connect",
        lambda **kw: (_ for _ in ()).throw(OperationalError("db down")),
    )

    test_app = app_module.create_app(testing=True)
    with test_app.test_client() as c:
        resp = c.post("/pull-data", json={"max_pages": 1})
    assert resp.status_code == 500
    assert "error" in resp.get_json()


# =====================================================================
# POST /pull-data — network error returns 500
# =====================================================================

@pytest.mark.buttons
def test_pull_data_network_error_500(monkeypatch):
    monkeypatch.setattr(app_module, "run_queries", lambda _c: {})
    monkeypatch.setattr(app_module.psycopg, "connect", lambda **kw: FakePullConn())
    monkeypatch.setattr(
        app_module, "fetch_page",
        lambda url, *a, **kw: (_ for _ in ()).throw(URLError("timeout")),
    )

    test_app = app_module.create_app(testing=True)
    with test_app.test_client() as c:
        resp = c.post("/pull-data", json={"max_pages": 1})
    assert resp.status_code == 500
    assert "Network error" in resp.get_json()["error"]


# =====================================================================
# POST /pull-data — DB error during scrape returns 500
# =====================================================================

@pytest.mark.buttons
def test_pull_data_db_error_during_scrape_500(monkeypatch):
    fake_html = "<html><body><table><tbody></tbody></table></body></html>"

    class _ErrorCursor:
        rowcount = 0
        def execute(self, *a, **kw):
            raise psycopg.Error("disk full")

    class _ErrorConn:
        autocommit = True
        def cursor(self):
            return _ErrorCursor()
        def close(self):
            pass
        def commit(self):
            pass
        def rollback(self):
            pass

    monkeypatch.setattr(app_module, "run_queries", lambda _c: {})
    monkeypatch.setattr(app_module.psycopg, "connect", lambda **kw: _ErrorConn())
    monkeypatch.setattr(app_module, "fetch_page", lambda url, *a, **kw: fake_html)
    monkeypatch.setattr(
        app_module, "parse_survey",
        lambda html: [{"url": "x", "program": "y", "comments": "z"}],
    )
    monkeypatch.setattr(app_module, "get_max_pages", lambda html: 1)

    test_app = app_module.create_app(testing=True)
    with test_app.test_client() as c:
        resp = c.post("/pull-data", json={"max_pages": 1})
    assert resp.status_code == 500
    assert "Database error" in resp.get_json()["error"]


# =====================================================================
# POST /pull-data — cleanup message with counts
# =====================================================================

@pytest.mark.integration
def test_pull_data_cleanup_message_with_counts(db_conn, monkeypatch):
    conn, cur = db_conn
    cur.execute("DELETE FROM applicants")

    test_href = f"/result/{uuid.uuid4()}"
    html = f"""<html><body>
<table><tbody>
  <tr>
    <td>School</td><td>CS | PhD</td><td>Jan 1, 2026</td>
    <td>Accepted</td><td><a href="{test_href}">V</a></td>
  </tr>
  <tr><td>Fall 2026 | American | GPA 3.80 | GRE 320 | GRE V 160 | GRE AW 165</td></tr>
</tbody></table>
<a href="?page=1">1</a>
</body></html>"""

    wrapper = NoCloseConn(conn)
    monkeypatch.setattr(app_module.psycopg, "connect", lambda **kw: wrapper)
    monkeypatch.setattr(scrape, "urlopen", lambda req: FakeResponse(html))

    test_app = app_module.create_app(testing=True)
    with test_app.test_client() as c:
        resp = c.post("/pull-data", json={"max_pages": 1})

    data = resp.get_json()
    assert data["inserted"] >= 1
    assert data["cleaned_gre_aw"] >= 1
    assert "Cleaned:" in data["message"]


# =====================================================================
# POST /pull-data — multi-page fetching
# =====================================================================

@pytest.mark.buttons
def test_pull_data_caught_up_breaks(monkeypatch):
    """All rows are duplicates (rowcount=0) → caught up after 1 page (lines 187-188)."""
    fake_html = """<html><body>
<table><tbody>
  <tr><td>S</td><td>CS | PhD</td><td>Jan 1, 2026</td><td>Accepted</td>
      <td><a href="/result/dup1">V</a></td></tr>
  <tr><td>Fall 2026 | American</td></tr>
</tbody></table>
<a href="?page=1">1</a><a href="?page=2">2</a>
</body></html>"""

    class _DupCursor:
        rowcount = 0  # All inserts are duplicates
        def execute(self, *a, **kw):
            pass

    class _DupConn:
        autocommit = True
        def cursor(self):
            return _DupCursor()
        def close(self):
            pass
        def commit(self):
            pass
        def rollback(self):
            pass

    monkeypatch.setattr(app_module, "fix_gre_aw", lambda _c: 0)
    monkeypatch.setattr(app_module, "fix_uc_universities", lambda _c: 0)
    monkeypatch.setattr(app_module, "run_queries", lambda _c: {})
    monkeypatch.setattr(app_module.psycopg, "connect", lambda **kw: _DupConn())
    monkeypatch.setattr(app_module, "fetch_page", lambda url, *a, **kw: fake_html)
    monkeypatch.setattr(app_module, "get_max_pages", lambda html: 2)
    monkeypatch.setattr(
        app_module, "parse_survey",
        lambda html: [{"url": "u", "program": "p", "comments": "c"}],
    )
    monkeypatch.setattr(
        app_module, "time",
        type("T", (), {"sleep": staticmethod(lambda d: None)})(),
    )

    test_app = app_module.create_app(testing=True)
    with test_app.test_client() as c:
        resp = c.post("/pull-data", json={"max_pages": 2})
    data = resp.get_json()
    # Caught up after page 1, never fetched page 2
    assert data["pages_fetched"] == 1


@pytest.mark.buttons
def test_pull_data_fetches_multiple_pages(monkeypatch):
    page1 = """<html><body>
<table><tbody>
  <tr><td>S</td><td>CS | PhD</td><td>Jan 1, 2026</td><td>Accepted</td>
      <td><a href="/result/a1">V</a></td></tr>
  <tr><td>Fall 2026 | American</td></tr>
</tbody></table>
<a href="?page=1">1</a><a href="?page=2">2</a>
</body></html>"""

    page2 = """<html><body>
<table><tbody>
  <tr><td>S</td><td>EE | Masters</td><td>Feb 1, 2026</td><td>Rejected</td>
      <td><a href="/result/b2">V</a></td></tr>
  <tr><td>Fall 2026 | International</td></tr>
</tbody></table>
<a href="?page=1">1</a><a href="?page=2">2</a>
</body></html>"""

    call_n = {"n": 0}

    def _fake_fetch(url, *a, **kw):
        call_n["n"] += 1
        return page1 if call_n["n"] == 1 else page2

    class _InsertCursor:
        rowcount = 1
        def execute(self, *a, **kw):
            pass

    class _InsertConn:
        autocommit = True
        def cursor(self):
            return _InsertCursor()
        def close(self):
            pass
        def commit(self):
            pass
        def rollback(self):
            pass

    monkeypatch.setattr(app_module, "fix_gre_aw", lambda _c: 0)
    monkeypatch.setattr(app_module, "fix_uc_universities", lambda _c: 0)
    monkeypatch.setattr(app_module, "run_queries", lambda _c: {})
    monkeypatch.setattr(
        app_module.psycopg, "connect",
        lambda **kw: _InsertConn(),
    )
    monkeypatch.setattr(app_module, "fetch_page", _fake_fetch)
    monkeypatch.setattr(app_module, "get_max_pages", lambda html: 2)
    monkeypatch.setattr(
        app_module, "parse_survey",
        lambda html: [
            {"url": f"u{call_n['n']}", "program": "p", "comments": "c"}
        ],
    )
    monkeypatch.setattr(
        app_module, "time",
        type("T", (), {"sleep": staticmethod(lambda d: None)})(),
    )

    test_app = app_module.create_app(testing=True)
    with test_app.test_client() as c:
        resp = c.post("/pull-data", json={"max_pages": 2})
    data = resp.get_json()
    assert data["pages_fetched"] == 2


# =====================================================================
# POST /pull-data — network error on page 2 triggers rollback
# =====================================================================

@pytest.mark.buttons
def test_pull_data_network_error_page2_rolls_back(monkeypatch):
    page1 = """<html><body>
<table><tbody>
  <tr><td>S</td><td>CS | PhD</td><td>Jan 1, 2026</td><td>Accepted</td>
      <td><a href="/result/net1">V</a></td></tr>
  <tr><td>Fall 2026 | American</td></tr>
</tbody></table>
<a href="?page=1">1</a><a href="?page=2">2</a>
</body></html>"""

    call_n = {"n": 0}

    def _fake_fetch(url, *a, **kw):
        call_n["n"] += 1
        if call_n["n"] == 1:
            return page1
        raise URLError("timeout on page 2")

    class _TrackCursor:
        rowcount = 1
        def execute(self, *a, **kw):
            pass

    class _TrackConn:
        autocommit = True
        rolled_back = False
        def cursor(self):
            return _TrackCursor()
        def close(self):
            pass
        def commit(self):
            pass
        def rollback(self):
            _TrackConn.rolled_back = True

    _TrackConn.rolled_back = False

    monkeypatch.setattr(app_module, "fix_gre_aw", lambda _c: 0)
    monkeypatch.setattr(app_module, "fix_uc_universities", lambda _c: 0)
    monkeypatch.setattr(app_module, "run_queries", lambda _c: {})
    monkeypatch.setattr(
        app_module.psycopg, "connect",
        lambda **kw: _TrackConn(),
    )
    monkeypatch.setattr(app_module, "fetch_page", _fake_fetch)
    monkeypatch.setattr(app_module, "get_max_pages", lambda html: 2)
    monkeypatch.setattr(
        app_module, "parse_survey",
        lambda html: [{"url": "u", "program": "p", "comments": "c"}],
    )
    monkeypatch.setattr(
        app_module, "time",
        type("T", (), {"sleep": staticmethod(lambda d: None)})(),
    )

    test_app = app_module.create_app(testing=True)
    with test_app.test_client() as c:
        resp = c.post("/pull-data", json={"max_pages": 2})
    assert resp.status_code == 500
    assert "Network error" in resp.get_json()["error"]
    assert _TrackConn.rolled_back is True


# =====================================================================
# POST /pull-data — cleanup exception returns 500 and rollback
# =====================================================================

@pytest.mark.buttons
def test_pull_data_cleanup_error_returns_500(monkeypatch):
    fake_html = """<html><body>
<table><tbody>
  <tr><td>S</td><td>CS | PhD</td><td>Jan 1, 2026</td><td>Accepted</td>
      <td><a href="/result/cl1">V</a></td></tr>
  <tr><td>Fall 2026 | American</td></tr>
</tbody></table>
<a href="?page=1">1</a>
</body></html>"""

    class _CleanCursor:
        rowcount = 1
        def execute(self, *a, **kw):
            pass

    class _CleanConn:
        autocommit = True
        rolled_back = False
        def cursor(self):
            return _CleanCursor()
        def close(self):
            pass
        def commit(self):
            pass
        def rollback(self):
            _CleanConn.rolled_back = True

    _CleanConn.rolled_back = False

    monkeypatch.setattr(app_module, "fix_gre_aw",
                        lambda _c: (_ for _ in ()).throw(psycopg.Error("cleanup boom")))
    monkeypatch.setattr(app_module, "fix_uc_universities", lambda _c: 0)
    monkeypatch.setattr(app_module, "run_queries", lambda _c: {})
    monkeypatch.setattr(
        app_module.psycopg, "connect",
        lambda **kw: _CleanConn(),
    )
    monkeypatch.setattr(
        app_module, "fetch_page",
        lambda url, *a, **kw: fake_html,
    )
    monkeypatch.setattr(
        app_module, "parse_survey",
        lambda html: [{"url": "u", "program": "p", "comments": "c"}],
    )
    monkeypatch.setattr(app_module, "get_max_pages", lambda html: 1)

    test_app = app_module.create_app(testing=True)
    with test_app.test_client() as c:
        resp = c.post("/pull-data", json={"max_pages": 1})
    assert resp.status_code == 500
    assert "Cleanup error" in resp.get_json()["error"]
    assert _CleanConn.rolled_back is True


# =====================================================================
# POST /pull-data — DB error mid-insert triggers rollback
# =====================================================================

@pytest.mark.buttons
def test_pull_data_insert_error_rolls_back(monkeypatch):
    fake_html = """<html><body>
<table><tbody>
  <tr><td>S</td><td>CS | PhD</td><td>Jan 1, 2026</td><td>Accepted</td>
      <td><a href="/result/ie1">V</a></td></tr>
  <tr><td>Fall 2026 | American</td></tr>
</tbody></table>
<a href="?page=1">1</a>
</body></html>"""

    class _BombCursor:
        rowcount = 1
        _call_count = 0
        def execute(self, *a, **kw):
            _BombCursor._call_count += 1
            if _BombCursor._call_count >= 3:
                raise psycopg.Error("disk full on 3rd execute")

    class _BombConn:
        autocommit = True
        rolled_back = False
        def cursor(self):
            return _BombCursor()
        def close(self):
            pass
        def commit(self):
            pass
        def rollback(self):
            _BombConn.rolled_back = True

    _BombCursor._call_count = 0
    _BombConn.rolled_back = False

    monkeypatch.setattr(app_module, "fix_gre_aw", lambda _c: 0)
    monkeypatch.setattr(app_module, "fix_uc_universities", lambda _c: 0)
    monkeypatch.setattr(app_module, "run_queries", lambda _c: {})
    monkeypatch.setattr(app_module.psycopg, "connect", lambda **kw: _BombConn())
    monkeypatch.setattr(app_module, "fetch_page", lambda url, *a, **kw: fake_html)
    monkeypatch.setattr(app_module, "parse_survey", lambda html: [
        {"url": "u1", "program": "p", "comments": "c"},
        {"url": "u2", "program": "p", "comments": "c"},
        {"url": "u3", "program": "p", "comments": "c"},
    ])
    monkeypatch.setattr(app_module, "get_max_pages", lambda html: 1)

    test_app = app_module.create_app(testing=True)
    with test_app.test_client() as c:
        resp = c.post("/pull-data", json={"max_pages": 1})
    assert resp.status_code == 500
    assert "Database error" in resp.get_json()["error"]
    assert _BombConn.rolled_back is True
