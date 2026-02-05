"""Load llm_extended_applicant_data.json into a PostgreSQL applicants table."""

import json
import logging
from datetime import datetime, date
from typing import Any

import psycopg
from psycopg import Connection, OperationalError

from query_data import DB_CONFIG

JSON_PATH = "llm_extended_applicant_data.json"

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def clean_text(value: Any) -> str:
    """Strip NUL bytes that PostgreSQL text fields reject."""
    return (value or "").replace("\x00", "")


def parse_float(value: Any, prefix: str = "") -> float | None:
    """Strip a prefix like 'GPA ' or 'GRE V ' and return a float, or None."""
    s = (value or "").replace(prefix, "", 1).strip()
    try:
        return float(s) if s else None
    except ValueError:
        return None


def parse_date(date_str: Any) -> date | None:
    """Parse 'Added on January 15, 2026' date format, return None if invalid."""
    date_str = clean_text(date_str or "").replace("Added on ", "")
    try:
        return datetime.strptime(date_str, "%B %d, %Y").date()
    except ValueError:
        return None


def create_connection(dbname: str, user: str, host: str | None = None) -> Connection | None:
    """Create a database connection with autocommit enabled."""
    try:
        kwargs = {"dbname": dbname, "user": user}
        if host:
            kwargs["host"] = host
        conn = psycopg.connect(**kwargs)
        conn.autocommit = True
        logger.info(f"Connected to {dbname}")
        return conn
    except OperationalError as e:
        logger.error(f"Connection error: {e}")
        return None


def main() -> None:
    """Load JSON data into PostgreSQL database."""
    db_name = DB_CONFIG["dbname"]
    db_user = DB_CONFIG["user"]
    db_host = DB_CONFIG.get("host")

    # Connect to default db and create applicant_data if it doesn't exist
    conn = create_connection("postgres", db_user, db_host)
    if not conn:
        return

    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_name,))
    if not cursor.fetchone():
        cursor.execute(f'CREATE DATABASE "{db_name}"')
        logger.info(f"Database {db_name} created")
    else:
        logger.info(f"Database {db_name} already exists")
    conn.close()

    # Reconnect to the target database
    conn = create_connection(db_name, db_user, db_host)
    if not conn:
        return

    cursor = conn.cursor()

    # Create table
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
    logger.info("Table 'applicants' ready")

    # Load JSON
    try:
        with open(JSON_PATH, "r", encoding="utf-8") as f:
            rows = json.load(f)
    except FileNotFoundError:
        logger.error(f"JSON file not found: {JSON_PATH}")
        conn.close()
        return
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON: {e}")
        conn.close()
        return

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
            "date_added": parse_date(row.get("date_added", "")),
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

    logger.info(f"Inserted {len(rows)} rows")

    # Verify
    cursor.execute("SELECT COUNT(*) FROM applicants")
    logger.info(f"Total rows in table: {cursor.fetchone()[0]}")

    conn.close()


if __name__ == "__main__":
    main()