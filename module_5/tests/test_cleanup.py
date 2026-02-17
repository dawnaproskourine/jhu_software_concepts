"""Cleanup unit and integration tests — exercise real cleanup functions.

``normalize_uc`` runs purely in-memory. ``fix_gre_aw`` and
``fix_uc_universities`` run against the SAVEPOINT-protected DB.
"""
# pylint: disable=C0116,R0903,W0613,C0415,E1101,R0801

import uuid

import pytest

from cleanup_data import normalize_uc, fix_gre_aw, fix_uc_universities


# =====================================================================
# normalize_uc — pure function tests (no DB)
# =====================================================================

@pytest.mark.db
def test_normalize_uc_matches_ucla():
    assert normalize_uc("CS, UCLA") == "University of California, Los Angeles"


@pytest.mark.db
def test_normalize_uc_matches_berkeley():
    assert normalize_uc("Physics, UC Berkeley") == "University of California, Berkeley"


@pytest.mark.db
def test_normalize_uc_matches_san_diego():
    assert normalize_uc("Biology, UCSD") == "University of California, San Diego"


@pytest.mark.db
def test_normalize_uc_no_match():
    assert normalize_uc("MIT") is None


@pytest.mark.db
def test_normalize_uc_empty_string():
    assert normalize_uc("") is None


# =====================================================================
# fix_uc_universities — integration (real DB with SAVEPOINT rollback)
# =====================================================================

def _unique_url():
    return f"https://test.example.com/cleanup/{uuid.uuid4()}"


def _insert_raw_row(cur, url, program, llm_university):
    """Insert a row directly (bypasses app.insert_row) for cleanup tests."""
    cur.execute("""
        INSERT INTO applicants (
            program, comments, date_added, url, status, term,
            us_or_international, gpa, gre, gre_v, gre_aw, degree,
            llm_generated_program, llm_generated_university
        ) VALUES (
            %s, '', NULL, %s, 'Accepted', 'Fall 2026',
            'American', 3.80, 320, 160, 4.5, 'Masters',
            'Computer Science', %s
        )
    """, (program, url, llm_university))


@pytest.mark.db
def test_fix_uc_universities_updates_generic_uc(db_conn):
    conn, cur = db_conn
    url = _unique_url()
    _insert_raw_row(cur, url, "Computer Science, UCLA", "University of California")
    updated = fix_uc_universities(conn)
    assert updated >= 1

    cur.execute(
        "SELECT llm_generated_university FROM applicants WHERE url = %s", (url,)
    )
    assert cur.fetchone()[0] == "University of California, Los Angeles"


@pytest.mark.db
def test_fix_uc_universities_fallback_to_current_uni(db_conn):
    """Line 89: program has no UC pattern, so normalize_uc falls back to current_uni."""
    conn, cur = db_conn
    url = _unique_url()
    # program="Computer Science" → normalize_uc returns None
    # llm_university="UC Berkeley" → SQL LIKE matches, fallback normalize_uc succeeds
    _insert_raw_row(cur, url, "Computer Science", "UC Berkeley")
    updated = fix_uc_universities(conn)
    assert updated >= 1

    cur.execute(
        "SELECT llm_generated_university FROM applicants WHERE url = %s", (url,)
    )
    assert cur.fetchone()[0] == "University of California, Berkeley"


@pytest.mark.db
def test_fix_uc_universities_skips_non_uc(db_conn):
    conn, cur = db_conn
    url = _unique_url()
    _insert_raw_row(cur, url, "Computer Science, MIT", "MIT")

    fix_uc_universities(conn)

    cur.execute(
        "SELECT llm_generated_university FROM applicants WHERE url = %s", (url,)
    )
    assert cur.fetchone()[0] == "MIT"


# =====================================================================
# fix_gre_aw — integration (real DB with SAVEPOINT rollback)
# =====================================================================

@pytest.mark.db
def test_fix_gre_aw_returns_count(db_conn):
    conn, cur = db_conn
    url_invalid = _unique_url()
    url_valid = _unique_url()

    # Row with invalid GRE AW (> 6)
    cur.execute("""
        INSERT INTO applicants (
            program, comments, date_added, url, status, term,
            us_or_international, gpa, gre, gre_v, gre_aw, degree,
            llm_generated_program, llm_generated_university
        ) VALUES (
            'CS, MIT', '', NULL, %s, 'Accepted', 'Fall 2026',
            'American', 3.80, 320, 160, 165.0, 'Masters',
            'Computer Science', 'MIT'
        )
    """, (url_invalid,))

    # Row with valid GRE AW
    cur.execute("""
        INSERT INTO applicants (
            program, comments, date_added, url, status, term,
            us_or_international, gpa, gre, gre_v, gre_aw, degree,
            llm_generated_program, llm_generated_university
        ) VALUES (
            'CS, Stanford', '', NULL, %s, 'Accepted', 'Fall 2026',
            'American', 3.90, 330, 165, 4.5, 'PhD',
            'Computer Science', 'Stanford University'
        )
    """, (url_valid,))

    count = fix_gre_aw(conn)
    assert count >= 1

    cur.execute("SELECT gre_aw FROM applicants WHERE url = %s", (url_invalid,))
    assert cur.fetchone()[0] is None

    cur.execute("SELECT gre_aw FROM applicants WHERE url = %s", (url_valid,))
    assert abs(cur.fetchone()[0] - 4.5) < 0.01
