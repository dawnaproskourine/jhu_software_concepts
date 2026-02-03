"""
Data cleanup script for applicant_data database.

Fixes:
1. Invalid GRE AW scores (> 6) - sets them to NULL
2. Re-normalizes UC university names to specific campuses
"""

import re
import psycopg
from query_data import DB_CONFIG

# UC campus patterns for normalization
UC_CAMPUS_PATTERNS = [
    (r"(?i).*\b(ucla|los\s*angeles)\b.*", "University of California, Los Angeles"),
    (r"(?i).*\b(ucb|uc\s*berkeley|berkeley)\b.*", "University of California, Berkeley"),
    (r"(?i).*\b(ucsd|san\s*diego)\b.*", "University of California, San Diego"),
    (r"(?i).*\b(ucsb|santa\s*barbara)\b.*", "University of California, Santa Barbara"),
    (r"(?i).*\b(uci|irvine?n?e?)\b.*", "University of California, Irvine"),
    (r"(?i).*\b(ucd|uc\s*davis|davis)\b.*", "University of California, Davis"),
    (r"(?i).*\b(ucsc|santa\s*cruz)\b.*", "University of California, Santa Cruz"),
    (r"(?i).*\b(ucr|riverside)\b.*", "University of California, Riverside"),
    (r"(?i).*\b(ucm|merced)\b.*", "University of California, Merced"),
    (r"(?i).*\b(ucsf|san\s*francisco)\b.*", "University of California, San Francisco"),
]


def normalize_uc(name: str) -> str | None:
    """Try to match a UC campus pattern and return canonical name."""
    for pattern, canonical in UC_CAMPUS_PATTERNS:
        if re.fullmatch(pattern, name):
            return canonical
    return None


def fix_gre_aw(conn):
    """Set invalid GRE AW scores (> 6) to NULL."""
    cur = conn.cursor()

    # Count invalid scores
    cur.execute("SELECT COUNT(*) FROM applicants WHERE gre_aw > 6")
    count = cur.fetchone()[0]
    print(f"Found {count} rows with invalid GRE AW scores (> 6)")

    if count > 0:
        cur.execute("UPDATE applicants SET gre_aw = NULL WHERE gre_aw > 6")
        print(f"Set {count} invalid GRE AW values to NULL")


def fix_uc_universities(conn):
    """Re-normalize UC university names using the original program field."""
    cur = conn.cursor()

    # Find rows where llm_generated_university is generic "University of California"
    # or has typos, and try to extract campus from the original program field
    cur.execute("""
        SELECT p_id, program, llm_generated_university
        FROM applicants
        WHERE llm_generated_university ILIKE '%University of California%'
           OR llm_generated_university ILIKE '%UC %'
           OR llm_generated_university ILIKE 'Uc %'
    """)
    rows = cur.fetchall()
    print(f"Found {len(rows)} UC-related rows to check")

    updated = 0
    for p_id, program, current_uni in rows:
        # Try to extract campus from original program field
        new_uni = normalize_uc(program or "")

        # If couldn't get from program, try from current llm_generated_university
        if not new_uni:
            new_uni = normalize_uc(current_uni or "")

        # Update if we found a specific campus and it's different
        if new_uni and new_uni != current_uni:
            cur.execute("""
                UPDATE applicants
                SET llm_generated_university = %s
                WHERE p_id = %s
            """, (new_uni, p_id))
            updated += 1

    print(f"Updated {updated} UC university names to specific campuses")


def main():
    conn = psycopg.connect(**DB_CONFIG)
    conn.autocommit = True

    print("=== Fixing GRE AW scores ===")
    fix_gre_aw(conn)

    print("\n=== Fixing UC university names ===")
    fix_uc_universities(conn)

    conn.close()
    print("\nCleanup complete!")


if __name__ == "__main__":
    main()