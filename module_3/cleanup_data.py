"""
Data cleanup script for applicant_data database.

Fixes:
1. Invalid GRE AW scores (> 6) - sets them to NULL
2. Re-normalizes UC university names to specific campuses
"""

import logging
import re

import psycopg
from psycopg import Connection, OperationalError

from query_data import DB_CONFIG
from llm_standardizer import UC_CAMPUS_PATTERNS

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def normalize_uc(name: str) -> str | None:
    """Try to match a UC campus pattern and return canonical name."""
    for pattern, canonical in UC_CAMPUS_PATTERNS:
        if re.fullmatch(pattern, name):
            return canonical
    return None


def fix_gre_aw(conn: Connection) -> int:
    """Set invalid GRE AW scores (> 6) to NULL.

    Returns the number of rows updated.
    """
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM applicants WHERE gre_aw > 6")
    count = cur.fetchone()[0]
    logger.info(f"Found {count} rows with invalid GRE AW scores (> 6)")

    if count > 0:
        cur.execute("UPDATE applicants SET gre_aw = NULL WHERE gre_aw > 6")
        logger.info(f"Set {count} invalid GRE AW values to NULL")

    return count


def fix_uc_universities(conn: Connection) -> int:
    """Re-normalize UC university names using the original program field.

    Returns the number of rows updated.
    """
    cur = conn.cursor()

    cur.execute("""
        SELECT p_id, program, llm_generated_university
        FROM applicants
        WHERE llm_generated_university ILIKE '%University of California%'
           OR llm_generated_university ILIKE '%UC %'
           OR llm_generated_university ILIKE 'Uc %'
    """)
    rows = cur.fetchall()
    logger.info(f"Found {len(rows)} UC-related rows to check")

    updated = 0
    for p_id, program, current_uni in rows:
        new_uni = normalize_uc(program or "")

        if not new_uni:
            new_uni = normalize_uc(current_uni or "")

        if new_uni and new_uni != current_uni:
            cur.execute("""
                UPDATE applicants
                SET llm_generated_university = %s
                WHERE p_id = %s
            """, (new_uni, p_id))
            updated += 1

    logger.info(f"Updated {updated} UC university names to specific campuses")
    return updated


def main() -> None:
    """Run all cleanup operations."""
    try:
        conn = psycopg.connect(**DB_CONFIG)
        conn.autocommit = True
    except OperationalError as e:
        logger.error(f"Database connection failed: {e}")
        return

    logger.info("=== Fixing GRE AW scores ===")
    fix_gre_aw(conn)

    logger.info("\n=== Fixing UC university names ===")
    fix_uc_universities(conn)

    conn.close()
    logger.info("\nCleanup complete!")


if __name__ == "__main__":
    main()