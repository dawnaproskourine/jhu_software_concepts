"""Load llm_extended_applicant_data.json into a PostgreSQL applicants table."""

import json
from datetime import datetime
import psycopg
from psycopg import OperationalError

DB_NAME = "applicant_data"
DB_USER = "dawnaproskourine"
JSON_PATH = "../module_2/llm_extended_applicant_data.json"

# --- helpers ---

def clean_text(value):
    """Strip NUL bytes that PostgreSQL text fields reject."""
    return (value or "").replace("\x00", "")

def parse_float(value, prefix=""):
    """Strip a prefix like 'GPA ' or 'GRE V ' and return a float, or None."""
    s = (value or "").replace(prefix, "", 1).strip()
    try:
        return float(s) if s else None
    except ValueError:
        return None
def create_connection(dbname, user):
    try:
        conn = psycopg.connect(dbname=dbname, user=user)
        conn.autocommit = True
        print(f"Connected to {dbname}")
        return conn
    except OperationalError as e:
        print(f"The error '{e}' occurred")
        return None


def main():
    # --- setup database ---

    # connect to default db and create applicant_data if it doesn't exist
    conn = create_connection("postgres", DB_USER)
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (DB_NAME,))
    if not cursor.fetchone():
        cursor.execute(f'CREATE DATABASE "{DB_NAME}"')
        print(f"Database {DB_NAME} created")
    else:
        print(f"Database {DB_NAME} already exists")
    conn.close()

    # reconnect to the new database
    conn = create_connection(DB_NAME, DB_USER)
    cursor = conn.cursor()

    # --- create table ---

    cursor.execute("DROP TABLE IF EXISTS applicants")
    cursor.execute("""
        CREATE TABLE applicants (
            p_id SERIAL PRIMARY KEY,
            program TEXT,
            comments TEXT,
            date_added DATE,
            url TEXT UNIQUE,
            status TEXT,
            term TEXT,
            us_or_international TEXT,
            gpa REAL,
            gre REAL,
            gre_v REAL,
            gre_aw REAL,
            degree TEXT,
            llm_generated_program TEXT,
            llm_generated_university TEXT
        )
    """)
    print("Table 'applicants' ready")

    # --- load JSON ---

    with open(JSON_PATH, "r", encoding="utf-8") as f:
        rows = json.load(f)

    cursor.executemany("""
        INSERT INTO applicants (
            program, comments, date_added, url, status, term,
            us_or_international, gpa, gre, gre_v, gre_aw,
            degree, llm_generated_program, llm_generated_university
        ) VALUES (
            %(program)s, %(comments)s, %(date_added)s, %(url)s, %(status)s, %(term)s,
            %(us_or_international)s, %(gpa)s, %(gre)s, %(gre_v)s, %(gre_aw)s,
            %(degree)s, %(llm_generated_program)s, %(llm_generated_university)s
        )
        ON CONFLICT (url) DO NOTHING
    """, [
        {
            "program": clean_text(row.get("program", "")),
            "comments": clean_text(row.get("comments", "")),
            "date_added": datetime.strptime(clean_text(row.get("date_added", "")).replace("Added on ", ""), "%B %d, %Y").date() if row.get("date_added") else None,
            "url": clean_text(row.get("url", "")),
            "status": clean_text(row.get("status", "")),
            "term": clean_text(row.get("term", "")),
            "us_or_international": clean_text(row.get("US/International", "")),
            "gpa": parse_float(row.get("GPA", ""), "GPA"),
            "gre": parse_float(row.get("GRE", ""), "GRE"),
            "gre_v": parse_float(row.get("GRE V", ""), "GRE V"),
            "gre_aw": parse_float(row.get("GRE AW", ""), "GRE AW"),
            "degree": clean_text(row.get("Degree", "")),
            "llm_generated_program": clean_text(row.get("llm-generated-program", "")),
            "llm_generated_university": clean_text(row.get("llm-generated-university", "")),
        }
        for row in rows
    ])

    print(f"Inserted {len(rows)} rows")

    # verify
    cursor.execute("SELECT COUNT(*) FROM applicants")
    print(f"Total rows in table: {cursor.fetchone()[0]}")

    conn.close()


if __name__ == "__main__":
    main()