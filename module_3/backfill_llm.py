"""
Backfill missing llm_generated_program and llm_generated_university fields.

Finds all rows where these fields are NULL or empty, runs the LLM standardizer,
and updates the database.
"""

import logging

import psycopg
from psycopg import OperationalError

from llm_standardizer import standardize as llm_standardize
from query_data import DB_CONFIG

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    """Backfill missing LLM fields in the database."""
    try:
        conn = psycopg.connect(**DB_CONFIG)
        conn.autocommit = True
    except OperationalError as e:
        logger.error(f"Database connection failed: {e}")
        return

    cur = conn.cursor()

    # Find rows with missing LLM fields
    cur.execute("""
        SELECT p_id, program FROM applicants
        WHERE llm_generated_program IS NULL OR llm_generated_program = ''
           OR llm_generated_university IS NULL OR llm_generated_university = ''
    """)
    rows = cur.fetchall()
    logger.info(f"Found {len(rows)} rows to backfill")

    updated = 0
    errors = 0
    for p_id, program in rows:
        try:
            result = llm_standardize(program or "")
            llm_program = result.get("standardized_program", "")
            llm_university = result.get("standardized_university", "")

            cur.execute("""
                UPDATE applicants
                SET llm_generated_program = %s, llm_generated_university = %s
                WHERE p_id = %s
            """, (llm_program, llm_university, p_id))
            updated += 1

            if updated % 10 == 0:
                logger.info(f"Processed {updated}/{len(rows)}...")
        except (KeyError, TypeError) as e:
            logger.warning(f"LLM parsing error on p_id {p_id}: {e}")
            errors += 1
        except psycopg.Error as e:
            logger.warning(f"Database error on p_id {p_id}: {e}")
            errors += 1

    conn.close()
    logger.info(f"Backfill complete. Updated {updated} rows, {errors} errors.")


if __name__ == "__main__":
    main()