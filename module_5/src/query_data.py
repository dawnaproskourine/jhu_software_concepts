"""Analysis queries on the applicant_data database."""

import logging
import os
from typing import Any
from urllib.parse import urlparse

import psycopg
from psycopg import Connection, OperationalError, sql

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

def _build_db_config():
    """Build database connection config from environment variables.

    Reads the standard 12-factor ``DATABASE_URL`` environment variable
    (e.g. ``postgresql://user:pass@host:5432/dbname``) and parses it
    into the keyword dictionary that ``psycopg.connect()`` expects.

    Falls back to individual environment variables (``DB_NAME``,
    ``DB_USER``, ``DB_HOST``, ``DB_PORT``, ``DB_PASSWORD``) when
    ``DATABASE_URL`` is not set.

    Returns an empty dict when no database environment variables are
    configured; the resulting ``psycopg.connect(**{})`` call will fail
    with ``OperationalError`` at connection time.
    """
    url = os.environ.get("DATABASE_URL")
    if url:
        parsed = urlparse(url)
        return {
            "dbname": parsed.path.lstrip("/"),
            "user": parsed.username or "",
            "host": parsed.hostname or "",
            "port": parsed.port or 5432,
            "password": parsed.password or "",
        }

    dbname = os.environ.get("DB_NAME", "")
    user = os.environ.get("DB_USER", "")
    if not dbname or not user:
        logger.warning(
            "Database environment variables not set. "
            "Set DATABASE_URL or individual variables: "
            "DB_NAME, DB_USER, DB_HOST, DB_PORT, DB_PASSWORD"
        )
        return {}

    return {
        "dbname": dbname,
        "user": user,
        "host": os.environ.get("DB_HOST", ""),
        "port": int(os.environ.get("DB_PORT", "5432")),
        "password": os.environ.get("DB_PASSWORD", ""),
    }


DB_CONFIG: dict[str, Any] = _build_db_config()

MAX_QUERY_LIMIT = 1000

# ---------------------------------------------------------------------------
# Query parameter constants
# ---------------------------------------------------------------------------
_FALL_TERM = "Fall 2026"
_ACCEPTED_PATTERN = "Accepted%"
_AMERICAN = "American"
_INTERNATIONAL = "International"
_MASTERS = "Masters"
_PHD = "PhD"
_PSYD = "PsyD"
_CS_PATTERN = "%Computer Science%"
_HOPKINS_PATTERN = "%Hopkins%"
_TERM_2026 = "%2026"
_EMPTY = ""
_GEORGETOWN_PATTERN = "%Georgetown University%"
_MIT_PATTERN = "%Massachusetts Institute of Technology%"
_STANFORD_PATTERN = "%Stanford University%"
_CMU_PATTERN = "%Carnegie Mellon University%"
_GEORGETOWN = "Georgetown University"
_MIT = "Massachusetts Institute of Technology"
_STANFORD = "Stanford University"
_CMU = "Carnegie Mellon University"


# ---------------------------------------------------------------------------
# Query-group helpers
# ---------------------------------------------------------------------------

def _query_counts(cur, agg_limit):
    """Queries 0-2: total count, fall 2026 count, international pct."""
    q_total = sql.SQL("SELECT COUNT(*) FROM {} LIMIT %s").format(
        sql.Identifier("applicants"),
    )
    cur.execute(q_total, (agg_limit,))
    total_count = cur.fetchone()[0]

    q_fall = sql.SQL(
        "SELECT COUNT(*) FROM {} WHERE {} = %s LIMIT %s"
    ).format(
        sql.Identifier("applicants"),
        sql.Identifier("term"),
    )
    cur.execute(q_fall, (_FALL_TERM, agg_limit))
    fall_2026_count = cur.fetchone()[0]

    q_intl = sql.SQL("""
        SELECT ROUND(
            100.0 * COUNT(*) FILTER (WHERE {} = %s)
            / COUNT(*), 2
        ) FROM {} LIMIT %s
    """).format(
        sql.Identifier("us_or_international"),
        sql.Identifier("applicants"),
    )
    cur.execute(q_intl, (_INTERNATIONAL, agg_limit))
    international_pct = cur.fetchone()[0]

    return {
        "total_count": total_count,
        "fall_2026_count": fall_2026_count,
        "international_pct": international_pct,
    }


def _query_averages(cur, agg_limit):
    """Query 3: average GPA, GRE, GRE V, GRE AW."""
    q_averages = sql.SQL("""
        SELECT
            ROUND(AVG({gpa})::numeric, 2),
            ROUND(AVG({gre})::numeric, 2),
            ROUND(AVG({gre_v})::numeric, 2),
            ROUND(AVG({gre_aw})::numeric, 2)
        FROM {table}
        WHERE {gpa} IS NOT NULL OR {gre} IS NOT NULL
              OR {gre_v} IS NOT NULL OR {gre_aw} IS NOT NULL
        LIMIT %s
    """).format(
        gpa=sql.Identifier("gpa"),
        gre=sql.Identifier("gre"),
        gre_v=sql.Identifier("gre_v"),
        gre_aw=sql.Identifier("gre_aw"),
        table=sql.Identifier("applicants"),
    )
    cur.execute(q_averages, (agg_limit,))
    row = cur.fetchone()
    return {
        "avg_gpa": row[0],
        "avg_gre": row[1],
        "avg_gre_v": row[2],
        "avg_gre_aw": row[3],
    }


def _query_fall2026_stats(cur, agg_limit):
    """Queries 4-6: American GPA, acceptance pct, accepted GPA for Fall 2026."""
    q_american_gpa = sql.SQL("""
        SELECT ROUND(AVG({gpa})::numeric, 2)
        FROM {table}
        WHERE {nationality} = %s
          AND {term} = %s
          AND {gpa} IS NOT NULL
        LIMIT %s
    """).format(
        gpa=sql.Identifier("gpa"),
        table=sql.Identifier("applicants"),
        nationality=sql.Identifier("us_or_international"),
        term=sql.Identifier("term"),
    )
    cur.execute(q_american_gpa, (_AMERICAN, _FALL_TERM, agg_limit))
    american_gpa = cur.fetchone()[0]

    q_acceptance = sql.SQL("""
        SELECT ROUND(
            100.0 * COUNT(*) FILTER (WHERE {status} ILIKE %s)
            / COUNT(*), 2
        ) FROM {table}
        WHERE {term} = %s
        LIMIT %s
    """).format(
        status=sql.Identifier("status"),
        table=sql.Identifier("applicants"),
        term=sql.Identifier("term"),
    )
    cur.execute(q_acceptance, (_ACCEPTED_PATTERN, _FALL_TERM, agg_limit))
    acceptance_pct = cur.fetchone()[0]

    q_accepted_gpa = sql.SQL("""
        SELECT ROUND(AVG({gpa})::numeric, 2)
        FROM {table}
        WHERE {term} = %s
          AND {status} ILIKE %s
          AND {gpa} IS NOT NULL
        LIMIT %s
    """).format(
        gpa=sql.Identifier("gpa"),
        table=sql.Identifier("applicants"),
        term=sql.Identifier("term"),
        status=sql.Identifier("status"),
    )
    cur.execute(q_accepted_gpa, (_FALL_TERM, _ACCEPTED_PATTERN, agg_limit))
    accepted_gpa = cur.fetchone()[0]

    return {
        "american_gpa_fall2026": american_gpa,
        "acceptance_pct_fall2026": acceptance_pct,
        "accepted_gpa_fall2026": accepted_gpa,
    }


def _query_school_counts(cur, agg_limit):
    """Queries 7-9: JHU CS Masters, PhD CS program/llm counts."""
    q_jhu = sql.SQL("""
        SELECT COUNT(*)
        FROM {table}
        WHERE {llm_uni} ILIKE %s
          AND {llm_prog} ILIKE %s
          AND {degree} = %s
        LIMIT %s
    """).format(
        table=sql.Identifier("applicants"),
        llm_uni=sql.Identifier("llm_generated_university"),
        llm_prog=sql.Identifier("llm_generated_program"),
        degree=sql.Identifier("degree"),
    )
    cur.execute(q_jhu, (_HOPKINS_PATTERN, _CS_PATTERN, _MASTERS, agg_limit))
    jhu_cs_masters = cur.fetchone()[0]

    q_phd_program = sql.SQL("""
        SELECT COUNT(*)
        FROM {table}
        WHERE {term} ILIKE %s
          AND {status} ILIKE %s
          AND {degree} = %s
          AND {program} ILIKE %s
          AND ({program} ILIKE %s
            OR {program} ILIKE %s
            OR {program} ILIKE %s
            OR {program} ILIKE %s)
        LIMIT %s
    """).format(
        table=sql.Identifier("applicants"),
        term=sql.Identifier("term"),
        status=sql.Identifier("status"),
        degree=sql.Identifier("degree"),
        program=sql.Identifier("program"),
    )
    cur.execute(q_phd_program, (
        _TERM_2026, _ACCEPTED_PATTERN, _PHD, _CS_PATTERN,
        _GEORGETOWN_PATTERN, _MIT_PATTERN, _STANFORD_PATTERN, _CMU_PATTERN,
        agg_limit,
    ))
    phd_cs_program = cur.fetchone()[0]

    q_phd_llm = sql.SQL("""
        SELECT COUNT(*)
        FROM {table}
        WHERE {term} ILIKE %s
          AND {status} ILIKE %s
          AND {degree} = %s
          AND {llm_prog} ILIKE %s
          AND {llm_uni} IN (%s, %s, %s, %s)
        LIMIT %s
    """).format(
        table=sql.Identifier("applicants"),
        term=sql.Identifier("term"),
        status=sql.Identifier("status"),
        degree=sql.Identifier("degree"),
        llm_prog=sql.Identifier("llm_generated_program"),
        llm_uni=sql.Identifier("llm_generated_university"),
    )
    cur.execute(q_phd_llm, (
        _TERM_2026, _ACCEPTED_PATTERN, _PHD, _CS_PATTERN,
        _GEORGETOWN, _MIT, _STANFORD, _CMU,
        agg_limit,
    ))
    phd_cs_llm = cur.fetchone()[0]

    return {
        "jhu_cs_masters": jhu_cs_masters,
        "phd_cs_program": phd_cs_program,
        "phd_cs_llm": phd_cs_llm,
    }


def _query_top_lists(cur):
    """Queries 10-11: top 10 programs and universities for Fall 2026."""
    top_limit = min(10, MAX_QUERY_LIMIT)

    q_top_programs = sql.SQL("""
        SELECT {llm_prog}, COUNT(*) AS {alias}
        FROM {table}
        WHERE {llm_prog} IS NOT NULL
          AND {llm_prog} != %s
          AND {term} = %s
        GROUP BY {llm_prog}
        ORDER BY {alias} DESC
        LIMIT %s
    """).format(
        llm_prog=sql.Identifier("llm_generated_program"),
        alias=sql.Identifier("num_applicants"),
        table=sql.Identifier("applicants"),
        term=sql.Identifier("term"),
    )
    cur.execute(q_top_programs, (_EMPTY, _FALL_TERM, top_limit))
    top_programs = cur.fetchall()

    q_top_unis = sql.SQL("""
        SELECT {llm_uni}, COUNT(*) AS {alias}
        FROM {table}
        WHERE {llm_uni} IS NOT NULL
          AND {llm_uni} != %s
          AND {term} = %s
        GROUP BY {llm_uni}
        ORDER BY {alias} DESC
        LIMIT %s
    """).format(
        llm_uni=sql.Identifier("llm_generated_university"),
        alias=sql.Identifier("num_applicants"),
        table=sql.Identifier("applicants"),
        term=sql.Identifier("term"),
    )
    cur.execute(q_top_unis, (_EMPTY, _FALL_TERM, top_limit))
    top_universities = cur.fetchall()

    return {
        "top_programs": top_programs,
        "top_universities": top_universities,
    }


def _query_acceptance_rates(cur):
    """Queries 12a-12b: acceptance rate by degree and nationality."""
    group_limit = min(10, MAX_QUERY_LIMIT)

    q_rate_degree = sql.SQL("""
        SELECT
            {degree},
            COUNT(*) AS {total},
            COUNT(*) FILTER (WHERE {status} ILIKE %s) AS {accepted},
            ROUND(
                100.0 * COUNT(*) FILTER (WHERE {status} ILIKE %s)
                / COUNT(*), 2
            ) AS {rate}
        FROM {table}
        WHERE {degree} IN (%s, %s, %s)
          AND {term} = %s
        GROUP BY {degree}
        ORDER BY {degree}
        LIMIT %s
    """).format(
        degree=sql.Identifier("degree"),
        total=sql.Identifier("total"),
        accepted=sql.Identifier("accepted"),
        status=sql.Identifier("status"),
        rate=sql.Identifier("acceptance_rate"),
        table=sql.Identifier("applicants"),
        term=sql.Identifier("term"),
    )
    cur.execute(q_rate_degree, (
        _ACCEPTED_PATTERN, _ACCEPTED_PATTERN,
        _MASTERS, _PHD, _PSYD, _FALL_TERM,
        group_limit,
    ))
    rate_by_degree = cur.fetchall()

    q_rate_nationality = sql.SQL("""
        SELECT
            {nationality},
            COUNT(*) AS {total},
            COUNT(*) FILTER (WHERE {status} ILIKE %s) AS {accepted},
            ROUND(
                100.0 * COUNT(*) FILTER (WHERE {status} ILIKE %s)
                / COUNT(*), 2
            ) AS {rate}
        FROM {table}
        WHERE {nationality} IN (%s, %s)
          AND {term} = %s
        GROUP BY {nationality}
        ORDER BY {nationality}
        LIMIT %s
    """).format(
        nationality=sql.Identifier("us_or_international"),
        total=sql.Identifier("total"),
        accepted=sql.Identifier("accepted"),
        status=sql.Identifier("status"),
        rate=sql.Identifier("acceptance_rate"),
        table=sql.Identifier("applicants"),
        term=sql.Identifier("term"),
    )
    cur.execute(q_rate_nationality, (
        _ACCEPTED_PATTERN, _ACCEPTED_PATTERN,
        _AMERICAN, _INTERNATIONAL, _FALL_TERM,
        group_limit,
    ))
    rate_by_nationality = cur.fetchall()

    return {
        "rate_by_degree": rate_by_degree,
        "rate_by_nationality": rate_by_nationality,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_queries(conn: Connection) -> dict[str, Any]:
    """Run all 13 analysis queries and return results as a dict.

    :param conn: An open PostgreSQL database connection.
    :type conn: psycopg.Connection
    :returns: A dictionary of query result keys and their values.
    :rtype: dict[str, Any]
    """
    cur = conn.cursor()
    agg_limit = min(1, MAX_QUERY_LIMIT)
    results: dict[str, Any] = {}
    results.update(_query_counts(cur, agg_limit))
    results.update(_query_averages(cur, agg_limit))
    results.update(_query_fall2026_stats(cur, agg_limit))
    results.update(_query_school_counts(cur, agg_limit))
    results.update(_query_top_lists(cur))
    results.update(_query_acceptance_rates(cur))
    return results


def main() -> None:
    """Print all analysis results to the console.

    Connects to the database, runs all queries, and prints formatted
    results to stdout.
    """
    try:
        conn = psycopg.connect(**DB_CONFIG)
    except OperationalError as e:
        logger.error("Database connection failed: %s", e)
        return

    results = run_queries(conn)
    conn.close()
    logger.info("Total applicants: %s", results['total_count'])
    logger.info("Fall 2026 applicants: %s", results['fall_2026_count'])
    logger.info("International student percentage: %s%%",
                results['international_pct'])
    logger.info("Average GPA: %s", results['avg_gpa'])
    logger.info("Average GRE: %s", results['avg_gre'])
    logger.info("Average GRE V: %s", results['avg_gre_v'])
    logger.info("Average GRE AW: %s", results['avg_gre_aw'])
    logger.info("Average GPA of American students (Fall 2026): %s",
                results['american_gpa_fall2026'])
    logger.info("Fall 2026 acceptance percentage: %s%%",
                results['acceptance_pct_fall2026'])
    logger.info("Average GPA of accepted applicants (Fall 2026): %s",
                results['accepted_gpa_fall2026'])
    logger.info("JHU Masters in Computer Science applicants: %s",
                results['jhu_cs_masters'])
    logger.info("2026 PhD CS acceptances (Georgetown, MIT, Stanford, CMU) "
                "[program]: %s", results['phd_cs_program'])
    logger.info("2026 PhD CS acceptances (Georgetown, MIT, Stanford, CMU) "
                "[llm]: %s", results['phd_cs_llm'])

    logger.info("Top 10 most popular programs:")
    for i, (program, count) in enumerate(results["top_programs"], 1):
        logger.info("  %d. %s: %s", i, program, count)

    logger.info("Top 10 most popular universities:")
    for i, (university, count) in enumerate(results["top_universities"], 1):
        logger.info("  %d. %s: %s", i, university, count)

    logger.info("Acceptance rate by degree type:")
    for degree, total, accepted, rate in results["rate_by_degree"]:
        logger.info("  %s: %s/%s (%s%%)", degree, accepted, total, rate)

    logger.info("Acceptance rate by nationality:")
    for nationality, total, accepted, rate in results["rate_by_nationality"]:
        logger.info("  %s: %s/%s (%s%%)", nationality, accepted, total, rate)


if __name__ == "__main__":
    main()
