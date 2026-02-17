"""Load llm_extended_applicant_data.json into a PostgreSQL applicants table."""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, date
from typing import Any

import psycopg
from psycopg import Connection, OperationalError, sql

from query_data import DB_CONFIG

_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_PATH = os.path.join(_DIR, "llm_extended_applicant_data.json")

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def clean_text(value: Any) -> str:
    """Strip NUL bytes that PostgreSQL text fields reject.

    :param value: The input value to clean.
    :type value: Any
    :returns: The cleaned string with NUL bytes removed.
    :rtype: str
    """
    return (value or "").replace("\x00", "")


def parse_float(value: Any, prefix: str = "") -> float | None:
    """Strip a prefix like 'GPA ' or 'GRE V ' and return a float, or None.

    :param value: The raw value containing a numeric string.
    :type value: Any
    :param prefix: A prefix to strip before parsing (e.g., ``"GPA"``).
    :type prefix: str
    :returns: The parsed float value, or ``None`` if parsing fails.
    :rtype: float or None
    """
    s = (value or "").replace(prefix, "", 1).strip()
    try:
        return float(s) if s else None
    except ValueError:
        return None


def parse_date(date_str: Any) -> date | None:
    """Parse 'Added on January 15, 2026' date format, return ``None`` if invalid.

    :param date_str: The raw date string from GradCafe.
    :type date_str: Any
    :returns: The parsed date, or ``None`` if the format is invalid.
    :rtype: datetime.date or None
    """
    date_str = clean_text(date_str or "").replace("Added on ", "")
    try:
        return datetime.strptime(date_str, "%B %d, %Y").date()
    except ValueError:
        return None


def create_connection(
    dbname: str, user: str, host: str | None = None
) -> Connection | None:
    """Create a database connection with autocommit enabled.

    :param dbname: The name of the PostgreSQL database.
    :type dbname: str
    :param user: The database user.
    :type user: str
    :param host: The database host address, or ``None`` for local socket.
    :type host: str or None
    :returns: An open connection with autocommit, or ``None`` on failure.
    :rtype: psycopg.Connection or None
    """
    try:
        kwargs = {"dbname": dbname, "user": user}
        if host:
            kwargs["host"] = host
        conn = psycopg.connect(**kwargs)
        conn.autocommit = True
        logger.info("Connected to %s", dbname)
        return conn
    except OperationalError as e:
        logger.error("Connection error: %s", e)
        return None


def main() -> None:
    """Load JSON data into PostgreSQL database.

    Creates the ``applicant_data`` database and ``applicants`` table if they
    do not exist, then inserts all rows from the JSON file. Duplicates are
    skipped via ``ON CONFLICT (url) DO NOTHING``.
    """
    db_name = DB_CONFIG["dbname"]
    db_user = DB_CONFIG["user"]
    db_host = DB_CONFIG.get("host")

    # Connect to default db and create applicant_data if it doesn't exist
    conn = create_connection("postgres", db_user, db_host)
    if not conn:
        return

    cursor = conn.cursor()
    check_db_query = "SELECT 1 FROM pg_database WHERE datname = %s"
    cursor.execute(check_db_query, (db_name,))
    if not cursor.fetchone():
        create_db_query = sql.SQL("CREATE DATABASE {}").format(
            sql.Identifier(db_name)
        )
        cursor.execute(create_db_query)
        logger.info("Database %s created", db_name)
    else:
        logger.info("Database %s already exists", db_name)
    conn.close()

    # Reconnect to the target database
    conn = create_connection(db_name, db_user, db_host)
    if not conn:
        return

    cursor = conn.cursor()
    # Create table
    drop_query = "DROP TABLE IF EXISTS applicants"
    cursor.execute(drop_query)
    create_table_query = """
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
    """
    cursor.execute(create_table_query)
    logger.info("Table 'applicants' ready")

    # Load JSON
    try:
        with open(JSON_PATH, "r", encoding="utf-8") as f:
            rows = json.load(f)
    except FileNotFoundError:
        logger.error("JSON file not found: %s", JSON_PATH)
        conn.close()
        return
    except json.JSONDecodeError as e:
        logger.error("Invalid JSON: %s", e)
        conn.close()
        return

    insert_query = """
        INSERT INTO applicants (
            program, comments, date_added, url, status, term,
            us_or_international, gpa, gre, gre_v, gre_aw,
            degree, llm_generated_program, llm_generated_university
        ) VALUES (
            %(program)s, %(comments)s, %(date_added)s, %(url)s,
            %(status)s, %(term)s, %(us_or_international)s,
            %(gpa)s, %(gre)s, %(gre_v)s, %(gre_aw)s,
            %(degree)s, %(llm_generated_program)s,
            %(llm_generated_university)s
        )
        ON CONFLICT (url) DO NOTHING
    """
    params_list = [
        {
                "program": clean_text(row.get("program", "")),
                "comments": clean_text(row.get("comments", "")),
                "date_added": parse_date(row.get("date_added", "")),
                "url": clean_text(row.get("url", "")),
                "status": clean_text(row.get("status", "")),
                "term": clean_text(row.get("term", "")),
                "us_or_international": clean_text(
                    row.get("US/International", "")
                ),
                "gpa": parse_float(row.get("GPA", ""), "GPA"),
                "gre": parse_float(row.get("GRE", ""), "GRE"),
                "gre_v": parse_float(row.get("GRE V", ""), "GRE V"),
                "gre_aw": parse_float(row.get("GRE AW", ""), "GRE AW"),
                "degree": clean_text(row.get("Degree", "")),
                "llm_generated_program": clean_text(
                    row.get("llm-generated-program", "")
                ),
                "llm_generated_university": clean_text(
                    row.get("llm-generated-university", "")
                ),
            }
            for row in rows
    ]
    try:
        cursor.executemany(insert_query, params_list)
    except psycopg.Error as e:
        logger.error("Database error during insert: %s", e)
        conn.close()
        return

    logger.info("Inserted %d rows", len(rows))

    # Verify
    verify_query = "SELECT COUNT(*) FROM applicants"
    cursor.execute(verify_query)
    logger.info("Total rows in table: %s", cursor.fetchone()[0])

    conn.close()

if __name__ == "__main__":
    main()
