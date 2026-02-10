"""End-to-end integration test.

Exercises the full pipeline: POST /pull-data inserts mocked scraper rows
into a real PostgreSQL database, then GET / renders the dashboard with
live query results from that data.  Everything rolls back via SAVEPOINT.
"""

import uuid

import pytest


# ---------------------------------------------------------------------------
# Connection wrapper that routes app DB calls through the test connection
# ---------------------------------------------------------------------------
class _TestConn:
    """Wraps a real connection for both context-manager and direct usage.

    Suppresses close() and autocommit changes so the SAVEPOINT stays intact.
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

    def __enter__(self):
        return self._conn

    def __exit__(self, *args):
        pass


_LLM_RESULT = {
    "standardized_program": "Computer Science",
    "standardized_university": "Stanford University",
}


def _unique_url():
    return f"https://test.example.com/e2e/{uuid.uuid4()}"


@pytest.mark.integration
def test_pull_then_render(db_conn, monkeypatch):
    """Full cycle: empty table → pull data → verify insert → render page."""
    conn, cur = db_conn
    import app as app_module
    import scrape

    # ---- Phase 0: start with an empty table ----
    cur.execute("DELETE FROM applicants")
    cur.execute("SELECT COUNT(*) FROM applicants")
    assert cur.fetchone()[0] == 0

    # ---- Fake scraper rows ----
    fake_html = "<html><body><table><tbody></tbody></table></body></html>"
    fake_rows = [
        {
            "program": "Computer Science, Stanford University",
            "comments": "Accepted",
            "date_added": "Added on January 15, 2026",
            "url": _unique_url(),
            "status": "Accepted",
            "term": "Fall 2026",
            "US/International": "American",
            "GPA": "GPA 3.85",
            "GRE": "GRE 320",
            "GRE V": "GRE V 160",
            "GRE AW": "GRE AW 4.5",
            "Degree": "Masters",
        },
        {
            "program": "Electrical Engineering, MIT",
            "comments": "Rejected",
            "date_added": "Added on February 1, 2026",
            "url": _unique_url(),
            "status": "Rejected",
            "term": "Fall 2026",
            "US/International": "International",
            "GPA": "GPA 3.60",
            "GRE": "GRE 315",
            "GRE V": "GRE V 155",
            "GRE AW": "GRE AW 4.0",
            "Degree": "PhD",
        },
        {
            "program": "Data Science, Carnegie Mellon University",
            "comments": "Wait listed",
            "date_added": "Added on March 10, 2026",
            "url": _unique_url(),
            "status": "Wait Listed",
            "term": "Fall 2026",
            "US/International": "American",
            "GPA": "GPA 3.92",
            "GRE": "GRE 330",
            "GRE V": "GRE V 165",
            "GRE AW": "GRE AW 5.0",
            "Degree": "Masters",
        },
    ]

    wrapper = _TestConn(conn)
    monkeypatch.setattr(app_module, "llm_standardize", lambda _x: _LLM_RESULT)
    monkeypatch.setattr(app_module, "fix_gre_aw", lambda _conn: 0)
    monkeypatch.setattr(app_module, "fix_uc_universities", lambda _conn: 0)
    monkeypatch.setattr(app_module.psycopg, "connect", lambda **kw: wrapper)
    monkeypatch.setattr(scrape, "fetch_page", lambda url, *a, **kw: fake_html)
    monkeypatch.setattr(scrape, "parse_survey", lambda html: fake_rows)
    monkeypatch.setattr(scrape, "get_max_pages", lambda html: 1)

    app_module.app.config["TESTING"] = True

    with app_module.app.test_client() as client:
        # ---- Phase 1: POST /pull-data ----
        pull_resp = client.post("/pull-data", json={"max_pages": 1})
        assert pull_resp.status_code == 200
        pull_data = pull_resp.get_json()
        assert pull_data["scraped"] == 3
        assert pull_data["inserted"] == 3

        # Verify all rows landed in the database
        cur.execute("SELECT COUNT(*) FROM applicants")
        assert cur.fetchone()[0] == 3

        # ---- Phase 2: GET / renders dashboard from live query data ----
        page_resp = client.get("/")
        assert page_resp.status_code == 200
        html = page_resp.data.decode()

        # Page title
        assert "Grad School Cafe Data Analysis" in html

        # Data from inserted rows appears in rendered output
        assert "Computer Science" in html
        assert "Stanford University" in html
        assert "Fall 2026" in html
        assert "Accepted" in html

        # ---- Phase 3: verify correctly formatted values ----
        # Counts
        assert "3" in html  # total_count and fall_2026_count

        # Percentages formatted as X.XX%
        assert "33.33%" in html  # international_pct and acceptance_pct

        # Averages (from 3 rows: 3.85/3.60/3.92, 320/315/330, etc.)
        assert "3.79" in html   # avg_gpa
        assert "321.67" in html  # avg_gre
        assert "160.00" in html  # avg_gre_v
        assert "4.50" in html   # avg_gre_aw

        # Rate by degree — Masters: 1 accepted / 2 total, PhD: 0 / 1
        assert "Masters" in html
        assert "PhD" in html

        # Rate by nationality — American and International present
        assert "American" in html
        assert "International" in html


@pytest.mark.integration
def test_duplicate_pull_preserves_uniqueness(db_conn, monkeypatch):
    """Two pulls with overlapping data should not create duplicate rows."""
    conn, cur = db_conn
    import app as app_module
    import scrape

    cur.execute("DELETE FROM applicants")

    fake_html = "<html><body><table><tbody></tbody></table></body></html>"

    # Shared URLs so the second pull overlaps with the first
    url_a = _unique_url()
    url_b = _unique_url()
    url_c = _unique_url()

    batch_1 = [
        {
            "program": "Computer Science, Stanford University",
            "comments": "Accepted",
            "date_added": "Added on January 15, 2026",
            "url": url_a,
            "status": "Accepted",
            "term": "Fall 2026",
            "US/International": "American",
            "GPA": "GPA 3.85",
            "GRE": "GRE 320",
            "GRE V": "GRE V 160",
            "GRE AW": "GRE AW 4.5",
            "Degree": "Masters",
        },
        {
            "program": "Electrical Engineering, MIT",
            "comments": "Rejected",
            "date_added": "Added on February 1, 2026",
            "url": url_b,
            "status": "Rejected",
            "term": "Fall 2026",
            "US/International": "International",
            "GPA": "GPA 3.60",
            "GRE": "GRE 315",
            "GRE V": "GRE V 155",
            "GRE AW": "GRE AW 4.0",
            "Degree": "PhD",
        },
    ]

    # Second batch: url_b overlaps, url_c is new
    batch_2 = [
        {
            "program": "Electrical Engineering, MIT",
            "comments": "Rejected",
            "date_added": "Added on February 1, 2026",
            "url": url_b,
            "status": "Rejected",
            "term": "Fall 2026",
            "US/International": "International",
            "GPA": "GPA 3.60",
            "GRE": "GRE 315",
            "GRE V": "GRE V 155",
            "GRE AW": "GRE AW 4.0",
            "Degree": "PhD",
        },
        {
            "program": "Data Science, Carnegie Mellon University",
            "comments": "Wait listed",
            "date_added": "Added on March 10, 2026",
            "url": url_c,
            "status": "Wait Listed",
            "term": "Fall 2026",
            "US/International": "American",
            "GPA": "GPA 3.92",
            "GRE": "GRE 330",
            "GRE V": "GRE V 165",
            "GRE AW": "GRE AW 5.0",
            "Degree": "Masters",
        },
    ]

    wrapper = _TestConn(conn)
    monkeypatch.setattr(app_module, "llm_standardize", lambda _x: _LLM_RESULT)
    monkeypatch.setattr(app_module, "fix_gre_aw", lambda _conn: 0)
    monkeypatch.setattr(app_module, "fix_uc_universities", lambda _conn: 0)
    monkeypatch.setattr(app_module.psycopg, "connect", lambda **kw: wrapper)
    monkeypatch.setattr(scrape, "fetch_page", lambda url, *a, **kw: fake_html)
    monkeypatch.setattr(scrape, "get_max_pages", lambda html: 1)

    app_module.app.config["TESTING"] = True

    with app_module.app.test_client() as client:
        # First pull: 2 new rows
        monkeypatch.setattr(scrape, "parse_survey", lambda html: batch_1)
        resp1 = client.post("/pull-data", json={"max_pages": 1})
        assert resp1.status_code == 200
        assert resp1.get_json()["inserted"] == 2

        cur.execute("SELECT COUNT(*) FROM applicants")
        assert cur.fetchone()[0] == 2

        # Second pull: 1 duplicate (url_b) + 1 new (url_c)
        monkeypatch.setattr(scrape, "parse_survey", lambda html: batch_2)
        resp2 = client.post("/pull-data", json={"max_pages": 1})
        assert resp2.status_code == 200
        data2 = resp2.get_json()
        assert data2["scraped"] == 2
        assert data2["inserted"] == 1  # only url_c is new

        # Total should be 3 unique rows, not 4
        cur.execute("SELECT COUNT(*) FROM applicants")
        assert cur.fetchone()[0] == 3

        # Each URL appears exactly once
        for url in (url_a, url_b, url_c):
            cur.execute("SELECT COUNT(*) FROM applicants WHERE url = %s", (url,))
            assert cur.fetchone()[0] == 1
