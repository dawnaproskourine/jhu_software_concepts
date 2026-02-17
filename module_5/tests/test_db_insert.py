"""Requirement (d): database insert tests.

Unit tests for clean_text / parse_float (no DB required).
Integration tests for insert_row, duplicate handling, column values,
and cleanup routines (real PostgreSQL with SAVEPOINT rollback).
"""
# pylint: disable=C0116,R0903,W0613,C0415,E1101,R0801,C0115,W0612,R0914

import uuid
from datetime import date

import pytest

from conftest import FakeResponse, NoCloseConn
from load_data import clean_text, parse_float, parse_date


# =====================================================================
# Unit tests – clean_text
# =====================================================================

@pytest.mark.db
class TestCleanText:
    def test_strips_nul_byte(self):
        assert clean_text("hel\x00lo") == "hello"

    def test_handles_none(self):
        assert clean_text(None) == ""

    def test_empty_string(self):
        assert clean_text("") == ""

    def test_multiple_nuls(self):
        assert clean_text("\x00a\x00b\x00") == "ab"

    def test_no_nuls_unchanged(self):
        assert clean_text("normal text") == "normal text"


# =====================================================================
# Unit tests – parse_float
# =====================================================================

@pytest.mark.db
class TestParseFloat:
    def test_plain_float(self):
        assert parse_float("3.75") == 3.75

    def test_plain_int_string(self):
        assert parse_float("320") == 320.0

    def test_gpa_prefix(self):
        assert parse_float("GPA 3.85", "GPA") == 3.85

    def test_gre_prefix(self):
        assert parse_float("GRE 320", "GRE") == 320.0

    def test_gre_v_prefix(self):
        assert parse_float("GRE V 160", "GRE V") == 160.0

    def test_gre_aw_prefix(self):
        assert parse_float("GRE AW 4.5", "GRE AW") == 4.5

    def test_none_value(self):
        assert parse_float(None) is None

    def test_empty_string(self):
        assert parse_float("") is None

    def test_invalid_text(self):
        assert parse_float("n/a") is None

    def test_whitespace_only(self):
        assert parse_float("   ") is None


# =====================================================================
# Unit tests – parse_date
# =====================================================================

@pytest.mark.db
class TestParseDate:
    def test_parse_date_valid_format(self):
        assert parse_date("Added on January 15, 2026") == date(2026, 1, 15)

    def test_parse_date_without_prefix(self):
        assert parse_date("January 15, 2026") == date(2026, 1, 15)

    def test_parse_date_invalid_string(self):
        assert parse_date("bad date") is None

    def test_parse_date_none_input(self):
        assert parse_date(None) is None

    def test_parse_date_empty_string(self):
        assert parse_date("") is None


# =====================================================================
# DB integration tests – require real PostgreSQL (auto-skip if absent)
# =====================================================================

def _unique_url():
    """Return a unique URL so tests never collide with real data."""
    return f"https://test.example.com/result/{uuid.uuid4()}"


def _sample_row(**overrides):
    """Return a minimal scraped-row dict suitable for insert_row."""
    row = {
        "program": "Computer Science, Stanford University",
        "comments": "Great program",
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
    }
    row.update(overrides)
    return row


@pytest.mark.db
def test_insert_row_returns_true_for_new_row(db_conn):
    conn, cur = db_conn
    from app import insert_row
    assert insert_row(cur, _sample_row()) is True


@pytest.mark.db
def test_duplicate_url_returns_false(db_conn):
    conn, cur = db_conn
    from app import insert_row
    row = _sample_row()
    url = row["url"]
    insert_row(cur, row)
    assert insert_row(cur, row) is False

    cur.execute("SELECT COUNT(*) FROM applicants WHERE url = %s", (url,))
    assert cur.fetchone()[0] == 1


@pytest.mark.db
def test_all_columns_populated(db_conn):
    conn, cur = db_conn
    from app import insert_row

    row = _sample_row()
    url = row["url"]
    insert_row(cur, row)

    cur.execute("""
        SELECT program, comments, date_added, url, status, term,
               us_or_international, gpa, gre, gre_v, gre_aw, degree,
               llm_generated_program, llm_generated_university
        FROM applicants WHERE url = %s
    """, (url,))
    result = cur.fetchone()
    assert result is not None
    (program, comments, date_added, db_url, status, term,
     us_intl, gpa, gre, gre_v, gre_aw, degree,
     llm_prog, llm_uni) = result

    assert program == "Computer Science, Stanford University"
    assert comments == "Great program"
    assert str(date_added) == "2026-01-15"
    assert db_url == url
    assert status == "Accepted"
    assert term == "Fall 2026"
    assert us_intl == "American"
    assert abs(gpa - 3.85) < 0.01
    assert abs(gre - 320) < 0.01
    assert abs(gre_v - 160) < 0.01
    assert abs(gre_aw - 4.5) < 0.01
    assert degree == "Masters"
    assert llm_prog == ""
    assert llm_uni == ""


# =====================================================================
# Integration: run_queries returns dict with expected keys
# =====================================================================

EXPECTED_QUERY_KEYS = [
    "total_count", "fall_2026_count", "international_pct",
    "avg_gpa", "avg_gre", "avg_gre_v", "avg_gre_aw",
    "american_gpa_fall2026", "acceptance_pct_fall2026",
    "accepted_gpa_fall2026", "jhu_cs_masters",
    "phd_cs_program", "phd_cs_llm",
    "top_programs", "top_universities",
    "rate_by_degree", "rate_by_nationality",
]


@pytest.mark.db
def test_run_queries_returns_expected_keys(db_conn):
    conn, cur = db_conn
    from app import insert_row
    from query_data import run_queries

    # Insert a row so queries have data to work with
    insert_row(cur, _sample_row())

    result = run_queries(conn)
    assert isinstance(result, dict)
    for key in EXPECTED_QUERY_KEYS:
        assert key in result, f"Missing key: {key}"


@pytest.mark.db
def test_null_date_for_invalid_format(db_conn):
    conn, cur = db_conn
    from app import insert_row

    row = _sample_row(date_added="bad date string")
    url = row["url"]
    insert_row(cur, row)

    cur.execute("SELECT date_added FROM applicants WHERE url = %s", (url,))
    assert cur.fetchone()[0] is None


@pytest.mark.db
def test_null_gpa_for_missing_value(db_conn):
    conn, cur = db_conn
    from app import insert_row

    row = _sample_row(**{"GPA": ""})
    url = row["url"]
    insert_row(cur, row)

    cur.execute("SELECT gpa FROM applicants WHERE url = %s", (url,))
    assert cur.fetchone()[0] is None


@pytest.mark.db
def test_nul_bytes_cleaned_from_program(db_conn):
    conn, cur = db_conn
    from app import insert_row

    row = _sample_row(program="CS\x00, MIT")
    url = row["url"]
    insert_row(cur, row)

    cur.execute("SELECT program FROM applicants WHERE url = %s", (url,))
    assert cur.fetchone()[0] == "CS, MIT"


@pytest.mark.db
def test_gre_aw_greater_than_6_set_to_null(db_conn):
    conn, cur = db_conn
    from app import insert_row

    row = _sample_row(**{"GRE AW": "GRE AW 165"})
    url = row["url"]
    insert_row(cur, row)

    from cleanup_data import fix_gre_aw
    fix_gre_aw(conn)

    cur.execute("SELECT gre_aw FROM applicants WHERE url = %s", (url,))
    assert cur.fetchone()[0] is None


# =====================================================================
# Integration: POST /pull-data inserts rows into a real DB
# =====================================================================


def _build_pull_html(test_href):
    """Build a GradCafe-style HTML page with one applicant row."""
    return f"""<html><body>
<table><tbody>
  <tr>
    <td>Stanford University</td>
    <td>Computer Science | PhD</td>
    <td>January 15, 2026</td>
    <td>Accepted</td>
    <td><a href="{test_href}">View</a></td>
  </tr>
  <tr>
    <td>Fall 2026 | American | GPA 3.85 | GRE 320 | GRE V 160 | GRE AW 4.5</td>
  </tr>
</tbody></table>
<a href="?page=1">1</a>
</body></html>"""


@pytest.mark.db
@pytest.mark.integration
def test_pull_data_inserts_into_empty_table(db_conn, monkeypatch):
    conn, cur = db_conn
    import app as app_module
    import scrape

    # Confirm table starts empty for this test's scope
    cur.execute("DELETE FROM applicants")
    cur.execute("SELECT COUNT(*) FROM applicants")
    assert cur.fetchone()[0] == 0

    test_href = f"/result/{uuid.uuid4()}"
    test_url = f"https://www.thegradcafe.com{test_href}"
    html = _build_pull_html(test_href)

    wrapper = NoCloseConn(conn)
    monkeypatch.setattr(app_module, "run_queries", lambda _conn: {})
    monkeypatch.setattr(app_module.psycopg, "connect", lambda **kw: wrapper)
    monkeypatch.setattr(scrape, "urlopen", lambda req: FakeResponse(html))

    test_app = app_module.create_app(testing=True)
    with test_app.test_client() as client:
        resp = client.post("/pull-data", json={"max_pages": 1})

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["inserted"] >= 1

    # Verify row exists with required non-null fields
    cur.execute("""
        SELECT program, status, term, degree,
               llm_generated_program, llm_generated_university
        FROM applicants WHERE url = %s
    """, (test_url,))
    result = cur.fetchone()
    assert result is not None
    program, status, term, degree, llm_prog, llm_uni = result
    assert program is not None
    assert status is not None
    assert term is not None
    assert degree is not None
    assert llm_prog == ""
    assert llm_uni == ""
