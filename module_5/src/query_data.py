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


def run_queries(conn: Connection) -> dict[str, Any]:  # pylint: disable=too-many-locals,too-many-statements
    """Run all 13 analysis queries and return results as a dict.

    :param conn: An open PostgreSQL database connection.
    :type conn: psycopg.Connection
    :returns: A dictionary of query result keys and their values.
    :rtype: dict[str, Any]
    """
    cur = conn.cursor()
    results: dict[str, Any] = {}

    # 0. Total applicant count
    q_total = sql.SQL("SELECT COUNT(*) FROM {}").format(
        sql.Identifier("applicants"),
    )
    cur.execute(q_total)
    results["total_count"] = cur.fetchone()[0]

    # 1. Fall 2026 count
    fall_term = "Fall 2026"
    q_fall = sql.SQL("SELECT COUNT(*) FROM {} WHERE {} = %s").format(
        sql.Identifier("applicants"),
        sql.Identifier("term"),
    )
    cur.execute(q_fall, (fall_term,))
    results["fall_2026_count"] = cur.fetchone()[0]

    # 2. International percentage
    international = "International"
    q_intl = sql.SQL("""
        SELECT ROUND(
            100.0 * COUNT(*) FILTER (WHERE {} = %s)
            / COUNT(*), 2
        ) FROM {}
    """).format(
        sql.Identifier("us_or_international"),
        sql.Identifier("applicants"),
    )
    cur.execute(q_intl, (international,))
    results["international_pct"] = cur.fetchone()[0]

    # 3. Average GPA, GRE, GRE V, GRE AW
    q_averages = sql.SQL("""
        SELECT
            ROUND(AVG({gpa})::numeric, 2),
            ROUND(AVG({gre})::numeric, 2),
            ROUND(AVG({gre_v})::numeric, 2),
            ROUND(AVG({gre_aw})::numeric, 2)
        FROM {table}
        WHERE {gpa} IS NOT NULL OR {gre} IS NOT NULL
              OR {gre_v} IS NOT NULL OR {gre_aw} IS NOT NULL
    """).format(
        gpa=sql.Identifier("gpa"),
        gre=sql.Identifier("gre"),
        gre_v=sql.Identifier("gre_v"),
        gre_aw=sql.Identifier("gre_aw"),
        table=sql.Identifier("applicants"),
    )
    cur.execute(q_averages)
    row = cur.fetchone()
    results["avg_gpa"] = row[0]
    results["avg_gre"] = row[1]
    results["avg_gre_v"] = row[2]
    results["avg_gre_aw"] = row[3]

    # 4. Average GPA of American students in Fall 2026
    american = "American"
    q_american_gpa = sql.SQL("""
        SELECT ROUND(AVG({gpa})::numeric, 2)
        FROM {table}
        WHERE {nationality} = %s
          AND {term} = %s
          AND {gpa} IS NOT NULL
    """).format(
        gpa=sql.Identifier("gpa"),
        table=sql.Identifier("applicants"),
        nationality=sql.Identifier("us_or_international"),
        term=sql.Identifier("term"),
    )
    cur.execute(q_american_gpa, (american, fall_term))
    results["american_gpa_fall2026"] = cur.fetchone()[0]

    # 5. Acceptance percentage for Fall 2026
    accepted_pattern = "Accepted%"
    q_acceptance = sql.SQL("""
        SELECT ROUND(
            100.0 * COUNT(*) FILTER (WHERE {status} ILIKE %s)
            / COUNT(*), 2
        ) FROM {table}
        WHERE {term} = %s
    """).format(
        status=sql.Identifier("status"),
        table=sql.Identifier("applicants"),
        term=sql.Identifier("term"),
    )
    cur.execute(q_acceptance, (accepted_pattern, fall_term))
    results["acceptance_pct_fall2026"] = cur.fetchone()[0]

    # 6. Average GPA of accepted applicants in Fall 2026
    q_accepted_gpa = sql.SQL("""
        SELECT ROUND(AVG({gpa})::numeric, 2)
        FROM {table}
        WHERE {term} = %s
          AND {status} ILIKE %s
          AND {gpa} IS NOT NULL
    """).format(
        gpa=sql.Identifier("gpa"),
        table=sql.Identifier("applicants"),
        term=sql.Identifier("term"),
        status=sql.Identifier("status"),
    )
    cur.execute(q_accepted_gpa, (fall_term, accepted_pattern))
    results["accepted_gpa_fall2026"] = cur.fetchone()[0]

    # 7. JHU Masters in Computer Science count
    hopkins_pattern = "%Hopkins%"
    cs_pattern = "%Computer Science%"
    masters = "Masters"
    q_jhu = sql.SQL("""
        SELECT COUNT(*)
        FROM {table}
        WHERE {llm_uni} ILIKE %s
          AND {llm_prog} ILIKE %s
          AND {degree} = %s
    """).format(
        table=sql.Identifier("applicants"),
        llm_uni=sql.Identifier("llm_generated_university"),
        llm_prog=sql.Identifier("llm_generated_program"),
        degree=sql.Identifier("degree"),
    )
    cur.execute(q_jhu, (hopkins_pattern, cs_pattern, masters))
    results["jhu_cs_masters"] = cur.fetchone()[0]

    # 8. PhD CS acceptances (program field)
    term_2026 = "%2026"
    phd = "PhD"
    georgetown_pattern = "%Georgetown University%"
    mit_pattern = "%Massachusetts Institute of Technology%"
    stanford_pattern = "%Stanford University%"
    cmu_pattern = "%Carnegie Mellon University%"
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
    """).format(
        table=sql.Identifier("applicants"),
        term=sql.Identifier("term"),
        status=sql.Identifier("status"),
        degree=sql.Identifier("degree"),
        program=sql.Identifier("program"),
    )
    cur.execute(q_phd_program, (
        term_2026, accepted_pattern, phd, cs_pattern,
        georgetown_pattern, mit_pattern, stanford_pattern, cmu_pattern,
    ))
    results["phd_cs_program"] = cur.fetchone()[0]

    # 9. PhD CS acceptances (llm fields)
    georgetown = "Georgetown University"
    mit = "Massachusetts Institute of Technology"
    stanford = "Stanford University"
    cmu = "Carnegie Mellon University"
    q_phd_llm = sql.SQL("""
        SELECT COUNT(*)
        FROM {table}
        WHERE {term} ILIKE %s
          AND {status} ILIKE %s
          AND {degree} = %s
          AND {llm_prog} ILIKE %s
          AND {llm_uni} IN (%s, %s, %s, %s)
    """).format(
        table=sql.Identifier("applicants"),
        term=sql.Identifier("term"),
        status=sql.Identifier("status"),
        degree=sql.Identifier("degree"),
        llm_prog=sql.Identifier("llm_generated_program"),
        llm_uni=sql.Identifier("llm_generated_university"),
    )
    cur.execute(q_phd_llm, (
        term_2026, accepted_pattern, phd, cs_pattern,
        georgetown, mit, stanford, cmu,
    ))
    results["phd_cs_llm"] = cur.fetchone()[0]

    # 10. Top 10 programs for Fall 2026
    empty = ""
    top_limit = 10
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
    cur.execute(q_top_programs, (empty, fall_term, top_limit))
    results["top_programs"] = cur.fetchall()

    # 11. Top 10 universities for Fall 2026
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
    cur.execute(q_top_unis, (empty, fall_term, top_limit))
    results["top_universities"] = cur.fetchall()

    # 12a. Acceptance rate by degree type for Fall 2026
    psyd = "PsyD"
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
        accepted_pattern, accepted_pattern,
        masters, phd, psyd, fall_term,
    ))
    results["rate_by_degree"] = cur.fetchall()

    # 12b. Acceptance rate by nationality for Fall 2026
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
        accepted_pattern, accepted_pattern,
        american, international, fall_term,
    ))
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
