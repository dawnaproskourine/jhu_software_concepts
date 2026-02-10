"""Tests for app.py error handling paths."""

import uuid
from urllib.error import URLError

import pytest
import psycopg
from psycopg import OperationalError

import app as app_module
import scrape


class _FakeResponse:
    def __init__(self, html):
        self._data = html.encode("utf-8")

    def read(self):
        return self._data


class _FakePullConn:
    autocommit = True

    def cursor(self):
        return _FakeCursor()

    def close(self):
        pass


class _FakeCursor:
    rowcount = 0

    def execute(self, *a, **kw):
        pass


# =====================================================================
# GET / — database error renders error page
# =====================================================================

@pytest.mark.web
def test_index_db_error_renders_error(monkeypatch):
    def _raise(**kw):
        raise OperationalError("db down")

    monkeypatch.setattr(app_module.psycopg, "connect", _raise)
    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as c:
        resp = c.get("/")
    # App catches OperationalError, logs it, and still renders the page
    assert resp.status_code == 200


# =====================================================================
# insert_row — LLM exception still inserts with empty LLM fields
# =====================================================================

@pytest.mark.db
def test_insert_row_llm_exception_still_inserts(db_conn, monkeypatch):
    conn, cur = db_conn

    monkeypatch.setattr(
        app_module, "llm_standardize",
        lambda _x: (_ for _ in ()).throw(RuntimeError("LLM crashed")),
    )

    from app import insert_row
    row = {
        "program": "CS, MIT",
        "comments": "Test",
        "date_added": "Added on January 15, 2026",
        "url": f"https://test.example.com/result/{uuid.uuid4()}",
        "status": "Accepted",
        "term": "Fall 2026",
        "US/International": "American",
        "GPA": "GPA 3.80",
        "GRE": "GRE 320",
        "GRE V": "GRE V 160",
        "GRE AW": "GRE AW 4.5",
        "Degree": "PhD",
    }

    assert insert_row(cur, row) is True

    cur.execute(
        "SELECT llm_generated_program, llm_generated_university FROM applicants WHERE url = %s",
        (row["url"],)
    )
    result = cur.fetchone()
    assert result[0] == ""
    assert result[1] == ""


# =====================================================================
# POST /pull-data — invalid max_pages defaults
# =====================================================================

@pytest.mark.buttons
def test_pull_data_invalid_max_pages_defaults(monkeypatch):
    fake_html = "<html><body><table><tbody></tbody></table></body></html>"
    monkeypatch.setattr(app_module, "llm_standardize", lambda _x: {})
    monkeypatch.setattr(app_module, "fix_gre_aw", lambda _c: 0)
    monkeypatch.setattr(app_module, "fix_uc_universities", lambda _c: 0)
    monkeypatch.setattr(app_module.psycopg, "connect", lambda **kw: _FakePullConn())
    monkeypatch.setattr(app_module, "run_queries", lambda _c: {})
    monkeypatch.setattr(scrape, "fetch_page", lambda url, *a, **kw: fake_html)
    monkeypatch.setattr(scrape, "parse_survey", lambda html: [])
    monkeypatch.setattr(scrape, "get_max_pages", lambda html: 1)

    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as c:
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

    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as c:
        resp = c.post("/pull-data", json={"max_pages": 1})
    assert resp.status_code == 500
    assert "error" in resp.get_json()


# =====================================================================
# POST /pull-data — network error returns 500
# =====================================================================

@pytest.mark.buttons
def test_pull_data_network_error_500(monkeypatch):
    monkeypatch.setattr(app_module, "run_queries", lambda _c: {})
    monkeypatch.setattr(app_module.psycopg, "connect", lambda **kw: _FakePullConn())
    monkeypatch.setattr(
        scrape, "fetch_page",
        lambda url, *a, **kw: (_ for _ in ()).throw(URLError("timeout")),
    )

    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as c:
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

    monkeypatch.setattr(app_module, "run_queries", lambda _c: {})
    monkeypatch.setattr(app_module.psycopg, "connect", lambda **kw: _ErrorConn())
    monkeypatch.setattr(scrape, "fetch_page", lambda url, *a, **kw: fake_html)
    monkeypatch.setattr(scrape, "parse_survey", lambda html: [{"url": "x", "program": "y", "comments": "z"}])
    monkeypatch.setattr(scrape, "get_max_pages", lambda html: 1)

    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as c:
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

    class _TestConn:
        def __init__(self, real):
            self._conn = real

        @property
        def autocommit(self):
            return self._conn.autocommit

        @autocommit.setter
        def autocommit(self, v):
            pass

        def cursor(self):
            return self._conn.cursor()

        def close(self):
            pass

        def __enter__(self):
            return self._conn

        def __exit__(self, *a):
            pass

    wrapper = _TestConn(conn)
    monkeypatch.setattr(app_module, "llm_standardize", lambda _x: {
        "standardized_program": "Computer Science",
        "standardized_university": "MIT",
    })
    monkeypatch.setattr(app_module.psycopg, "connect", lambda **kw: wrapper)
    monkeypatch.setattr(scrape, "urlopen", lambda req: _FakeResponse(html))

    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as c:
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

    monkeypatch.setattr(app_module, "llm_standardize", lambda _x: {})
    monkeypatch.setattr(app_module, "fix_gre_aw", lambda _c: 0)
    monkeypatch.setattr(app_module, "fix_uc_universities", lambda _c: 0)
    monkeypatch.setattr(app_module, "run_queries", lambda _c: {})
    monkeypatch.setattr(app_module.psycopg, "connect", lambda **kw: _DupConn())
    monkeypatch.setattr(scrape, "fetch_page", lambda url, *a, **kw: fake_html)
    monkeypatch.setattr(scrape, "get_max_pages", lambda html: 2)
    monkeypatch.setattr(scrape, "parse_survey", lambda html: [{"url": "u", "program": "p", "comments": "c"}])
    monkeypatch.setattr(app_module, "time", type("T", (), {"sleep": staticmethod(lambda d: None)})())

    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as c:
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

    monkeypatch.setattr(app_module, "llm_standardize", lambda _x: {})
    monkeypatch.setattr(app_module, "fix_gre_aw", lambda _c: 0)
    monkeypatch.setattr(app_module, "fix_uc_universities", lambda _c: 0)
    monkeypatch.setattr(app_module, "run_queries", lambda _c: {})
    monkeypatch.setattr(app_module.psycopg, "connect", lambda **kw: _InsertConn())
    monkeypatch.setattr(scrape, "fetch_page", _fake_fetch)
    monkeypatch.setattr(scrape, "get_max_pages", lambda html: 2)
    monkeypatch.setattr(scrape, "parse_survey", lambda html: [{"url": f"u{call_n['n']}", "program": "p", "comments": "c"}])
    monkeypatch.setattr(app_module, "time", type("T", (), {"sleep": staticmethod(lambda d: None)})())

    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as c:
        resp = c.post("/pull-data", json={"max_pages": 2})
    data = resp.get_json()
    assert data["pages_fetched"] == 2