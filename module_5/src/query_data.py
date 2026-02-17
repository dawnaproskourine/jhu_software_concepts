"""Analysis queries on the applicant_data database."""

import logging
import os
from typing import Any
from urllib.parse import urlparse

import psycopg
from psycopg import Connection, OperationalError

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

def _build_db_config():
    """Build database connection config from ``DATABASE_URL``.

    Reads the standard 12-factor ``DATABASE_URL`` environment variable
    (e.g. ``postgresql://user:pass@host:5432/dbname``) and parses it
    into the keyword dictionary that ``psycopg.connect()`` expects.

    Returns an empty dict when ``DATABASE_URL`` is not set; the
    resulting ``psycopg.connect(**{})`` call will fail with
    ``OperationalError`` at connection time.
    """
    url = os.environ.get("DATABASE_URL")
    if not url:
        logger.warning(
            "DATABASE_URL environment variable is not set. "
            "Example: export DATABASE_URL="
            '"postgresql://user:pass@localhost:5432/applicant_data"'
        )
        return {}
    parsed = urlparse(url)
    return {
        "dbname": parsed.path.lstrip("/") or "applicant_data",
        "user": parsed.username or "",
        "host": parsed.hostname or "127.0.0.1",
        "port": parsed.port or 5432,
        "password": parsed.password or "",
    }


DB_CONFIG: dict[str, Any] = _build_db_config()


def run_queries(conn: Connection) -> dict[str, Any]:  # pylint: disable=too-many-locals
    """Run all 13 analysis queries and return results as a dict.

    :param conn: An open PostgreSQL database connection.
    :type conn: psycopg.Connection
    :returns: A dictionary of query result keys and their values.
    :rtype: dict[str, Any]
    """
    cur = conn.cursor()
    results: dict[str, Any] = {}

    # 0. Total applicant count
    q_total = "SELECT COUNT(*) FROM applicants"
    cur.execute(q_total)
    results["total_count"] = cur.fetchone()[0]

    # 1. Fall 2026 count
    q_fall = "SELECT COUNT(*) FROM applicants WHERE term = 'Fall 2026'"
    cur.execute(q_fall)
    results["fall_2026_count"] = cur.fetchone()[0]

    # 2. International percentage
    q_intl = """
        SELECT ROUND(
            100.0 * COUNT(*) FILTER (WHERE us_or_international = 'International')
            / COUNT(*), 2
        ) FROM applicants
    """
    cur.execute(q_intl)
    results["international_pct"] = cur.fetchone()[0]

    # 3. Average GPA, GRE, GRE V, GRE AW
    q_averages = """
        SELECT
            ROUND(AVG(gpa)::numeric, 2),
            ROUND(AVG(gre)::numeric, 2),
            ROUND(AVG(gre_v)::numeric, 2),
            ROUND(AVG(gre_aw)::numeric, 2)
        FROM applicants
        WHERE gpa IS NOT NULL OR gre IS NOT NULL
              OR gre_v IS NOT NULL OR gre_aw IS NOT NULL
    """
    cur.execute(q_averages)
    row = cur.fetchone()
    results["avg_gpa"] = row[0]
    results["avg_gre"] = row[1]
    results["avg_gre_v"] = row[2]
    results["avg_gre_aw"] = row[3]

    # 4. Average GPA of American students in Fall 2026
    q_american_gpa = """
        SELECT ROUND(AVG(gpa)::numeric, 2)
        FROM applicants
        WHERE us_or_international = 'American'
          AND term = 'Fall 2026'
          AND gpa IS NOT NULL
    """
    cur.execute(q_american_gpa)
    results["american_gpa_fall2026"] = cur.fetchone()[0]

    # 5. Acceptance percentage for Fall 2026
    q_acceptance = """
        SELECT ROUND(
            100.0 * COUNT(*) FILTER (WHERE status ILIKE 'Accepted%%')
            / COUNT(*), 2
        ) FROM applicants
        WHERE term = 'Fall 2026'
    """
    cur.execute(q_acceptance)
    results["acceptance_pct_fall2026"] = cur.fetchone()[0]

    # 6. Average GPA of accepted applicants in Fall 2026
    q_accepted_gpa = """
        SELECT ROUND(AVG(gpa)::numeric, 2)
        FROM applicants
        WHERE term = 'Fall 2026'
          AND status ILIKE 'Accepted%%'
          AND gpa IS NOT NULL
    """
    cur.execute(q_accepted_gpa)
    results["accepted_gpa_fall2026"] = cur.fetchone()[0]

    # 7. JHU Masters in Computer Science count
    q_jhu = """
        SELECT COUNT(*)
        FROM applicants
        WHERE llm_generated_university ILIKE '%%Hopkins%%'
          AND llm_generated_program ILIKE '%%Computer Science%%'
          AND degree = 'Masters'
    """
    cur.execute(q_jhu)
    results["jhu_cs_masters"] = cur.fetchone()[0]

    # 8. PhD CS acceptances (program field)
    q_phd_program = """
        SELECT COUNT(*)
        FROM applicants
        WHERE term ILIKE '%%2026'
          AND status ILIKE 'Accepted%%'
          AND degree = 'PhD'
          AND program ILIKE '%%Computer Science%%'
          AND (program ILIKE '%%Georgetown University%%'
            OR program ILIKE '%%Massachusetts Institute of Technology%%'
            OR program ILIKE '%%Stanford University%%'
            OR program ILIKE '%%Carnegie Mellon University%%')
    """
    cur.execute(q_phd_program)
    results["phd_cs_program"] = cur.fetchone()[0]

    # 9. PhD CS acceptances (llm fields)
    q_phd_llm = """
        SELECT COUNT(*)
        FROM applicants
        WHERE term ILIKE '%%2026'
          AND status ILIKE 'Accepted%%'
          AND degree = 'PhD'
          AND llm_generated_program ILIKE '%%Computer Science%%'
          AND llm_generated_university IN (
              'Georgetown University',
              'Massachusetts Institute of Technology',
              'Stanford University',
              'Carnegie Mellon University'
          )
    """
    cur.execute(q_phd_llm)
    results["phd_cs_llm"] = cur.fetchone()[0]

    # 10. Top 10 programs for Fall 2026
    q_top_programs = """
        SELECT llm_generated_program, COUNT(*) AS num_applicants
        FROM applicants
        WHERE llm_generated_program IS NOT NULL
          AND llm_generated_program != ''
          AND term = 'Fall 2026'
        GROUP BY llm_generated_program
        ORDER BY num_applicants DESC
        LIMIT 10
    """
    cur.execute(q_top_programs)
    results["top_programs"] = cur.fetchall()

    # 11. Top 10 universities for Fall 2026
    q_top_unis = """
        SELECT llm_generated_university, COUNT(*) AS num_applicants
        FROM applicants
        WHERE llm_generated_university IS NOT NULL
          AND llm_generated_university != ''
          AND term = 'Fall 2026'
        GROUP BY llm_generated_university
        ORDER BY num_applicants DESC
        LIMIT 10
    """
    cur.execute(q_top_unis)
    results["top_universities"] = cur.fetchall()

    # 12a. Acceptance rate by degree type for Fall 2026
    q_rate_degree = """
        SELECT
            degree,
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE status ILIKE 'Accepted%%') AS accepted,
            ROUND(
                100.0 * COUNT(*) FILTER (WHERE status ILIKE 'Accepted%%')
                / COUNT(*), 2
            ) AS acceptance_rate
        FROM applicants
        WHERE degree IN ('Masters', 'PhD', 'PsyD')
          AND term = 'Fall 2026'
        GROUP BY degree
        ORDER BY degree
    """
    cur.execute(q_rate_degree)
    results["rate_by_degree"] = cur.fetchall()

    # 12b. Acceptance rate by nationality for Fall 2026
    q_rate_nationality = """
        SELECT
            us_or_international,
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE status ILIKE 'Accepted%%') AS accepted,
            ROUND(
                100.0 * COUNT(*) FILTER (WHERE status ILIKE 'Accepted%%')
                / COUNT(*), 2
            ) AS acceptance_rate
        FROM applicants
        WHERE us_or_international IN ('American', 'International')
          AND term = 'Fall 2026'
        GROUP BY us_or_international
        ORDER BY us_or_international
    """
    cur.execute(q_rate_nationality)
    results["rate_by_nationality"] = cur.fetchall()

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
    print(f"Total applicants: {results['total_count']}")
    print(f"Fall 2026 applicants: {results['fall_2026_count']}")
    print(f"International student percentage: "
          f"{results['international_pct']}%")
    print(f"Average GPA: {results['avg_gpa']}")
    print(f"Average GRE: {results['avg_gre']}")
    print(f"Average GRE V: {results['avg_gre_v']}")
    print(f"Average GRE AW: {results['avg_gre_aw']}")
    print(f"Average GPA of American students (Fall 2026): "
          f"{results['american_gpa_fall2026']}")
    print(f"Fall 2026 acceptance percentage: "
          f"{results['acceptance_pct_fall2026']}%")
    print(f"Average GPA of accepted applicants (Fall 2026): "
          f"{results['accepted_gpa_fall2026']}")
    print(f"JHU Masters in Computer Science applicants: "
          f"{results['jhu_cs_masters']}")
    print("2026 PhD CS acceptances (Georgetown, MIT, Stanford, CMU) "
          f"[program]: {results['phd_cs_program']}")
    print("2026 PhD CS acceptances (Georgetown, MIT, Stanford, CMU) "
          f"[llm]: {results['phd_cs_llm']}")

    print("\nTop 10 most popular programs:")
    for i, (program, count) in enumerate(results["top_programs"], 1):
        print(f"  {i}. {program}: {count}")

    print("\nTop 10 most popular universities:")
    for i, (university, count) in enumerate(results["top_universities"], 1):
        print(f"  {i}. {university}: {count}")

    print("\nAcceptance rate by degree type:")
    for degree, total, accepted, rate in results["rate_by_degree"]:
        print(f"  {degree}: {accepted}/{total} ({rate}%)")

    print("\nAcceptance rate by nationality:")
    for nationality, total, accepted, rate in results["rate_by_nationality"]:
        print(f"  {nationality}: {accepted}/{total} ({rate}%)")


if __name__ == "__main__":
    main()
