"""
Data cleanup script for applicant_data database.

Fixes:
1. Invalid GRE AW scores (> 6) - sets them to NULL
2. Re-normalizes UC university names to specific campuses
"""
from __future__ import annotations

import logging
import re

import psycopg
from psycopg import Connection, OperationalError, sql

from query_data import DB_CONFIG, MAX_QUERY_LIMIT

# UC campus normalization patterns (regex pattern -> canonical name)
UC_CAMPUS_PATTERNS = [
    (r"(?i).*\b(ucla|los\s*angeles)\b.*",
     "University of California, Los Angeles"),
    (r"(?i).*\b(ucb|uc\s*berkeley|berkeley)\b.*",
     "University of California, Berkeley"),
    (r"(?i).*\b(ucsd|san\s*diego)\b.*",
     "University of California, San Diego"),
    (r"(?i).*\b(ucsb|santa\s*barbara)\b.*",
     "University of California, Santa Barbara"),
    (r"(?i).*\b(uci|irvine?n?e?)\b.*",
     "University of California, Irvine"),
    (r"(?i).*\b(ucd|uc\s*davis|davis)\b.*",
     "University of California, Davis"),
    (r"(?i).*\b(ucsc|santa\s*cruz)\b.*",
     "University of California, Santa Cruz"),
    (r"(?i).*\b(ucr|riverside)\b.*",
     "University of California, Riverside"),
    (r"(?i).*\b(ucm|merced)\b.*",
     "University of California, Merced"),
    (r"(?i).*\b(ucsf|san\s*francisco)\b.*",
     "University of California, San Francisco"),
]

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def normalize_uc(name: str) -> str | None:
    """Try to match a UC campus pattern and return the canonical name.

    :param name: The university name string to check.
    :type name: str
    :returns: The canonical UC campus name, or ``None`` if no match.
    :rtype: str or None
    """
    for pattern, canonical in UC_CAMPUS_PATTERNS:
        if re.fullmatch(pattern, name):
            return canonical
    return None


def fix_gre_aw(conn: Connection) -> int:
    """Set invalid GRE AW scores (> 6) to NULL.

    GRE Analytical Writing is scored on a 0--6 scale. Any value above 6
    is treated as invalid and set to ``NULL``.

    :param conn: An open PostgreSQL database connection.
    :type conn: psycopg.Connection
    :returns: The number of rows updated.
    :rtype: int
    """
    cur = conn.cursor()

    gre_aw_max = 6
    agg_limit = min(1, MAX_QUERY_LIMIT)
    count_query = sql.SQL(
        "SELECT COUNT(*) FROM {} WHERE {} > %s LIMIT %s"
    ).format(sql.Identifier("applicants"), sql.Identifier("gre_aw"))
    cur.execute(count_query, (gre_aw_max, agg_limit))
    count = cur.fetchone()[0]
    logger.info("Found %d rows with invalid GRE AW scores (> 6)", count)

    if count > 0:
        fix_query = sql.SQL(
            "UPDATE {} SET {} = NULL WHERE {} > %s"
        ).format(
            sql.Identifier("applicants"),
            sql.Identifier("gre_aw"),
            sql.Identifier("gre_aw"),
        )
        cur.execute(fix_query, (gre_aw_max,))

    return count


def fix_uc_universities(conn: Connection) -> int:
    """Re-normalize UC university names using the original program field.

    Finds rows with generic "University of California" names and attempts
    to resolve them to specific campuses (e.g., UCLA, Berkeley).

    :param conn: An open PostgreSQL database connection.
    :type conn: psycopg.Connection
    :returns: The number of rows updated.
    :rtype: int
    """
    cur = conn.cursor()

    uc_pattern1 = "%University of California%"
    uc_pattern2 = "%UC %"
    uc_pattern3 = "Uc %"
    select_query = sql.SQL("""
        SELECT {p_id}, {program}, {llm_uni}
        FROM {table}
        WHERE {llm_uni} ILIKE %s
           OR {llm_uni} ILIKE %s
           OR {llm_uni} ILIKE %s
    """).format(
        p_id=sql.Identifier("p_id"),
        program=sql.Identifier("program"),
        llm_uni=sql.Identifier("llm_generated_university"),
        table=sql.Identifier("applicants"),
    )
    cur.execute(select_query, (uc_pattern1, uc_pattern2, uc_pattern3))
    rows = cur.fetchall()
    logger.info("Found %d UC-related rows to check", len(rows))

    updated = 0
    for p_id, program, current_uni in rows:
        new_uni = normalize_uc(program or "")

        if not new_uni:
            new_uni = normalize_uc(current_uni or "")

        if new_uni and new_uni != current_uni:
            update_query = sql.SQL("""
                UPDATE {table}
                SET {llm_uni} = %s
                WHERE {p_id} = %s
            """).format(
                table=sql.Identifier("applicants"),
                llm_uni=sql.Identifier("llm_generated_university"),
                p_id=sql.Identifier("p_id"),
            )
            cur.execute(update_query, (new_uni, p_id))
            updated += 1

    logger.info("Updated %d UC university names to specific campuses",
                updated)
    return updated


def main() -> None:
    """Run all cleanup operations.

    Connects to the database and runs GRE AW and UC university fixes.
    """
    try:
        conn = psycopg.connect(**DB_CONFIG)
        conn.autocommit = True
    except OperationalError as e:
        logger.error("Database connection failed: %s", e)
        return

    logger.info("=== Fixing GRE AW scores ===")
    fix_gre_aw(conn)

    logger.info("\n=== Fixing UC university names ===")
    fix_uc_universities(conn)

    conn.close()
    logger.info("\nCleanup complete!")


if __name__ == "__main__":
    main()
