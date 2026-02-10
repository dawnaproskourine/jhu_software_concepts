"""End-to-end integration test.

Exercises the full pipeline: POST /pull-data inserts scraped rows into a
real PostgreSQL database, then GET / renders the dashboard with live
query results from that data.  Everything rolls back via SAVEPOINT.

Only ``llm_standardize`` and ``psycopg.connect`` are mocked. The scraper
functions (``fetch_page``, ``parse_survey``, ``get_max_pages``) run for
real against crafted HTML fed through a transport-level ``urlopen`` stub.
The cleanup functions (``fix_gre_aw``, ``fix_uc_universities``) run for
real against the SAVEPOINT-protected database.
"""

import uuid

import pytest

from conftest import FakeResponse, NoCloseConn


_LLM_RESULT = {
    "standardized_program": "Computer Science",
    "standardized_university": "Stanford University",
}


def _unique_url():
    return f"/result/{uuid.uuid4()}"


def _build_test_html(rows):
    """Build a GradCafe-style HTML page from a list of row specifications.

    Each row is a dict with: school, program, degree, date_text, status,
    href, detail (detail text like "Fall 2026 | American | GPA 3.85 ...").
    Pagination link is set to ``?page=1`` so ``get_max_pages`` returns 1.
    """
    tbody_rows = []
    for r in rows:
        # Main row (5 cells)
        tbody_rows.append(f"""  <tr>
    <td>{r['school']}</td>
    <td>{r['program']} | {r['degree']}</td>
    <td>{r['date_text']}</td>
    <td>{r['status']}</td>
    <td><a href="{r['href']}">View</a></td>
  </tr>""")
        # Detail row (1 cell)
        tbody_rows.append(f"""  <tr>
    <td>{r['detail']}</td>
  </tr>""")

    tbody = "\n".join(tbody_rows)
    return f"""<html><body>
<table><tbody>
{tbody}
</tbody></table>
<a href="?page=1">1</a>
</body></html>"""


@pytest.mark.integration
def test_pull_then_render(db_conn, monkeypatch):
    """Full cycle: empty table -> pull data -> verify insert -> render page."""
    conn, cur = db_conn
    import app as app_module
    import scrape

    # ---- Phase 0: start with an empty table ----
    cur.execute("DELETE FROM applicants")
    cur.execute("SELECT COUNT(*) FROM applicants")
    assert cur.fetchone()[0] == 0

    # ---- Build test HTML with 3 applicant entries ----
    url_a = _unique_url()
    url_b = _unique_url()
    url_c = _unique_url()

    rows = [
        {
            "school": "Stanford University",
            "program": "Computer Science",
            "degree": "Masters",
            "date_text": "January 15, 2026",
            "status": "Accepted",
            "href": url_a,
            "detail": "Fall 2026 | American | GPA 3.85 | GRE 320 | GRE V 160 | GRE AW 4.5",
        },
        {
            "school": "MIT",
            "program": "Electrical Engineering",
            "degree": "PhD",
            "date_text": "February 1, 2026",
            "status": "Rejected",
            "href": url_b,
            "detail": "Fall 2026 | International | GPA 3.60 | GRE 315 | GRE V 155 | GRE AW 4.0",
        },
        {
            "school": "Carnegie Mellon University",
            "program": "Data Science",
            "degree": "Masters",
            "date_text": "March 10, 2026",
            "status": "Wait Listed",
            "href": url_c,
            "detail": "Fall 2026 | American | GPA 3.92 | GRE 330 | GRE V 165 | GRE AW 5.0",
        },
    ]
    html = _build_test_html(rows)

    wrapper = NoCloseConn(conn)
    monkeypatch.setattr(app_module, "llm_standardize", lambda _x: _LLM_RESULT)
    monkeypatch.setattr(app_module.psycopg, "connect", lambda **kw: wrapper)
    monkeypatch.setattr(scrape, "urlopen", lambda req: FakeResponse(html))

    test_app = app_module.create_app(testing=True)

    with test_app.test_client() as client:
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
        html_out = page_resp.data.decode()

        # Page title
        assert "Grad School Cafe Data Analysis" in html_out

        # Data from inserted rows appears in rendered output
        assert "Computer Science" in html_out
        assert "Stanford University" in html_out
        assert "Fall 2026" in html_out
        assert "Accepted" in html_out

        # ---- Phase 3: verify correctly formatted values ----
        # Counts
        assert "3" in html_out  # total_count and fall_2026_count

        # Percentages formatted as X.XX%
        assert "33.33%" in html_out  # international_pct and acceptance_pct

        # Averages (from 3 rows: 3.85/3.60/3.92, 320/315/330, etc.)
        assert "3.79" in html_out   # avg_gpa
        assert "321.67" in html_out  # avg_gre
        assert "160.00" in html_out  # avg_gre_v
        assert "4.50" in html_out   # avg_gre_aw

        # Rate by degree — Masters: 1 accepted / 2 total, PhD: 0 / 1
        assert "Masters" in html_out
        assert "PhD" in html_out

        # Rate by nationality — American and International present
        assert "American" in html_out
        assert "International" in html_out


@pytest.mark.integration
def test_duplicate_pull_preserves_uniqueness(db_conn, monkeypatch):
    """Two pulls with overlapping data should not create duplicate rows."""
    conn, cur = db_conn
    import app as app_module
    import scrape

    cur.execute("DELETE FROM applicants")

    # Shared URLs so the second pull overlaps with the first
    url_a = _unique_url()
    url_b = _unique_url()
    url_c = _unique_url()

    batch_1_rows = [
        {
            "school": "Stanford University",
            "program": "Computer Science",
            "degree": "Masters",
            "date_text": "January 15, 2026",
            "status": "Accepted",
            "href": url_a,
            "detail": "Fall 2026 | American | GPA 3.85 | GRE 320 | GRE V 160 | GRE AW 4.5",
        },
        {
            "school": "MIT",
            "program": "Electrical Engineering",
            "degree": "PhD",
            "date_text": "February 1, 2026",
            "status": "Rejected",
            "href": url_b,
            "detail": "Fall 2026 | International | GPA 3.60 | GRE 315 | GRE V 155 | GRE AW 4.0",
        },
    ]

    batch_2_rows = [
        {
            "school": "MIT",
            "program": "Electrical Engineering",
            "degree": "PhD",
            "date_text": "February 1, 2026",
            "status": "Rejected",
            "href": url_b,  # duplicate
            "detail": "Fall 2026 | International | GPA 3.60 | GRE 315 | GRE V 155 | GRE AW 4.0",
        },
        {
            "school": "Carnegie Mellon University",
            "program": "Data Science",
            "degree": "Masters",
            "date_text": "March 10, 2026",
            "status": "Wait Listed",
            "href": url_c,  # new
            "detail": "Fall 2026 | American | GPA 3.92 | GRE 330 | GRE V 165 | GRE AW 5.0",
        },
    ]

    html_1 = _build_test_html(batch_1_rows)
    html_2 = _build_test_html(batch_2_rows)

    call_count = {"n": 0}

    def _urlopen_switch(req):
        """Return batch_1 HTML on first pull, batch_2 on second."""
        call_count["n"] += 1
        if call_count["n"] <= 1:
            return FakeResponse(html_1)
        return FakeResponse(html_2)

    wrapper = NoCloseConn(conn)
    monkeypatch.setattr(app_module, "llm_standardize", lambda _x: _LLM_RESULT)
    monkeypatch.setattr(app_module.psycopg, "connect", lambda **kw: wrapper)
    monkeypatch.setattr(scrape, "urlopen", _urlopen_switch)

    test_app = app_module.create_app(testing=True)

    with test_app.test_client() as client:
        # First pull: 2 new rows
        resp1 = client.post("/pull-data", json={"max_pages": 1})
        assert resp1.status_code == 200
        assert resp1.get_json()["inserted"] == 2

        cur.execute("SELECT COUNT(*) FROM applicants")
        assert cur.fetchone()[0] == 2

        # Second pull: 1 duplicate (url_b) + 1 new (url_c)
        resp2 = client.post("/pull-data", json={"max_pages": 1})
        assert resp2.status_code == 200
        data2 = resp2.get_json()
        assert data2["scraped"] == 2
        assert data2["inserted"] == 1  # only url_c is new

        # Total should be 3 unique rows, not 4
        cur.execute("SELECT COUNT(*) FROM applicants")
        assert cur.fetchone()[0] == 3

        # Each URL appears exactly once (parse_main_row prepends domain)
        for href in (url_a, url_b, url_c):
            full_url = f"https://www.thegradcafe.com{href}"
            cur.execute("SELECT COUNT(*) FROM applicants WHERE url = %s", (full_url,))
            assert cur.fetchone()[0] == 1


@pytest.mark.integration
def test_update_analysis_reload_reflects_new_data(db_conn, monkeypatch):
    """Update Analysis (location.reload) re-renders the page with current DB data."""
    conn, cur = db_conn
    import app as app_module
    import scrape

    cur.execute("DELETE FROM applicants")

    url_a = _unique_url()
    url_b = _unique_url()
    rows = [
        {
            "school": "Stanford University",
            "program": "Computer Science",
            "degree": "Masters",
            "date_text": "January 15, 2026",
            "status": "Accepted",
            "href": url_a,
            "detail": "Fall 2026 | American | GPA 3.85 | GRE 320 | GRE V 160 | GRE AW 4.5",
        },
        {
            "school": "MIT",
            "program": "Electrical Engineering",
            "degree": "PhD",
            "date_text": "February 1, 2026",
            "status": "Rejected",
            "href": url_b,
            "detail": "Fall 2026 | International | GPA 3.60 | GRE 315 | GRE V 155 | GRE AW 4.0",
        },
    ]
    html = _build_test_html(rows)

    wrapper = NoCloseConn(conn)
    monkeypatch.setattr(app_module, "llm_standardize", lambda _x: _LLM_RESULT)
    monkeypatch.setattr(app_module.psycopg, "connect", lambda **kw: wrapper)
    monkeypatch.setattr(scrape, "urlopen", lambda req: FakeResponse(html))

    test_app = app_module.create_app(testing=True)

    with test_app.test_client() as client:
        # Pull data into DB
        pull_resp = client.post("/pull-data", json={"max_pages": 1})
        assert pull_resp.status_code == 200
        assert pull_resp.get_json()["inserted"] == 2

        # Simulate Update Analysis button (location.reload → GET /)
        reload_resp = client.get("/")
        assert reload_resp.status_code == 200
        html_out = reload_resp.data.decode()

        # Reload reflects the newly inserted data
        assert "Computer Science" in html_out
        assert "Stanford University" in html_out
        assert "Accepted" in html_out
        assert 'data-testid="update-analysis-btn"' in html_out
