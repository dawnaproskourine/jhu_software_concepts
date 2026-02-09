"""Requirement (d): database insert tests.

Unit tests for clean_text / parse_float (no DB required).
Integration tests for insert_row, duplicate handling, column values,
and cleanup routines (real PostgreSQL with SAVEPOINT rollback).
"""

import uuid

from load_data import clean_text, parse_float


# =====================================================================
# Unit tests – clean_text
# =====================================================================

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
# DB integration tests – require real PostgreSQL (auto-skip if absent)
# =====================================================================

_LLM_RESULT_FULL = {
    "standardized_program": "Computer Science",
    "standardized_university": "Stanford University",
}


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


def test_insert_row_returns_true_for_new_row(db_conn, monkeypatch):
    conn, cur = db_conn
    import app as app_module
    monkeypatch.setattr(app_module, "llm_standardize", lambda _x: _LLM_RESULT_FULL)
    from app import insert_row
    assert insert_row(cur, _sample_row()) is True


def test_duplicate_url_returns_false(db_conn, monkeypatch):
    conn, cur = db_conn
    import app as app_module
    monkeypatch.setattr(app_module, "llm_standardize", lambda _x: _LLM_RESULT_FULL)
    from app import insert_row
    row = _sample_row()
    insert_row(cur, row)
    assert insert_row(cur, row) is False


def test_all_columns_populated(db_conn, monkeypatch):
    conn, cur = db_conn
    import app as app_module
    monkeypatch.setattr(app_module, "llm_standardize", lambda _x: _LLM_RESULT_FULL)
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
    assert llm_prog == "Computer Science"
    assert llm_uni == "Stanford University"


def test_null_date_for_invalid_format(db_conn, monkeypatch):
    conn, cur = db_conn
    import app as app_module
    monkeypatch.setattr(app_module, "llm_standardize", lambda _x: {})
    from app import insert_row

    row = _sample_row(date_added="bad date string")
    url = row["url"]
    insert_row(cur, row)

    cur.execute("SELECT date_added FROM applicants WHERE url = %s", (url,))
    assert cur.fetchone()[0] is None


def test_null_gpa_for_missing_value(db_conn, monkeypatch):
    conn, cur = db_conn
    import app as app_module
    monkeypatch.setattr(app_module, "llm_standardize", lambda _x: {})
    from app import insert_row

    row = _sample_row(**{"GPA": ""})
    url = row["url"]
    insert_row(cur, row)

    cur.execute("SELECT gpa FROM applicants WHERE url = %s", (url,))
    assert cur.fetchone()[0] is None


def test_nul_bytes_cleaned_from_program(db_conn, monkeypatch):
    conn, cur = db_conn
    import app as app_module
    monkeypatch.setattr(app_module, "llm_standardize", lambda _x: {})
    from app import insert_row

    row = _sample_row(program="CS\x00, MIT")
    url = row["url"]
    insert_row(cur, row)

    cur.execute("SELECT program FROM applicants WHERE url = %s", (url,))
    assert cur.fetchone()[0] == "CS, MIT"


def test_gre_aw_greater_than_6_set_to_null(db_conn, monkeypatch):
    conn, cur = db_conn
    import app as app_module
    monkeypatch.setattr(app_module, "llm_standardize", lambda _x: {})
    from app import insert_row

    row = _sample_row(**{"GRE AW": "GRE AW 165"})
    url = row["url"]
    insert_row(cur, row)

    from cleanup_data import fix_gre_aw
    fix_gre_aw(conn)

    cur.execute("SELECT gre_aw FROM applicants WHERE url = %s", (url,))
    assert cur.fetchone()[0] is None


def test_valid_gre_aw_not_changed(db_conn, monkeypatch):
    conn, cur = db_conn
    import app as app_module
    monkeypatch.setattr(app_module, "llm_standardize", lambda _x: {})
    from app import insert_row

    row = _sample_row(**{"GRE AW": "GRE AW 4.5"})
    url = row["url"]
    insert_row(cur, row)

    from cleanup_data import fix_gre_aw
    fix_gre_aw(conn)

    cur.execute("SELECT gre_aw FROM applicants WHERE url = %s", (url,))
    assert abs(cur.fetchone()[0] - 4.5) < 0.01
