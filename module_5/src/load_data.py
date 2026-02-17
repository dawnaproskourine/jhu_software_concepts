"""Load llm_extended_applicant_data.json into a PostgreSQL applicants table."""
# pylint: disable=R0801
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, date
from typing import Any

import psycopg
from psycopg import Connection, OperationalError, sql

from query_data import DB_CONFIG, MAX_QUERY_LIMIT

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


def main() -> None:  # pylint: disable=too-many-locals
    """Load JSON data into PostgreSQL database.

    Creates the ``applicant_data`` database and ``applicants`` table if they
    do not exist, then inserts all rows from the JSON file. Duplicates are
    skipped via ``ON CONFLICT (url) DO NOTHING``.
    """
    db_name = DB_CONFIG["dbname"]
    db_user = DB_CONFIG["user"]
    db_host = DB_CONFIG.get("host")

    # Connect to admin db and create target database if it doesn't exist
    admin_db = os.environ.get("DB_ADMIN_NAME", "postgres")
    conn = create_connection(admin_db, db_user, db_host)
    if not conn:
        return

    cursor = conn.cursor()
    agg_limit = min(1, MAX_QUERY_LIMIT)
    check_db_query = sql.SQL("SELECT 1 FROM {} WHERE {} = %s LIMIT %s").format(
        sql.Identifier("pg_database"),
        sql.Identifier("datname"),
    )
    cursor.execute(check_db_query, (db_name, agg_limit))
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
    drop_query = sql.SQL("DROP TABLE IF EXISTS {}").format(
        sql.Identifier("applicants"),
    )
    cursor.execute(drop_query)
    col_defs = sql.SQL(", ").join([
        sql.SQL("{} SERIAL PRIMARY KEY").format(sql.Identifier("p_id")),
        sql.SQL("{} TEXT").format(sql.Identifier("program")),
        sql.SQL("{} TEXT").format(sql.Identifier("comments")),
        sql.SQL("{} DATE").format(sql.Identifier("date_added")),
        sql.SQL("{} TEXT UNIQUE").format(sql.Identifier("url")),
        sql.SQL("{} TEXT").format(sql.Identifier("status")),
        sql.SQL("{} TEXT").format(sql.Identifier("term")),
        sql.SQL("{} TEXT").format(sql.Identifier("us_or_international")),
        sql.SQL("{} REAL").format(sql.Identifier("gpa")),
        sql.SQL("{} REAL").format(sql.Identifier("gre")),
        sql.SQL("{} REAL").format(sql.Identifier("gre_v")),
        sql.SQL("{} REAL").format(sql.Identifier("gre_aw")),
        sql.SQL("{} TEXT").format(sql.Identifier("degree")),
        sql.SQL("{} TEXT").format(sql.Identifier("llm_generated_program")),
        sql.SQL("{} TEXT").format(sql.Identifier("llm_generated_university")),
    ])
    create_table_query = sql.SQL("CREATE TABLE {} ({})").format(
        sql.Identifier("applicants"), col_defs,
    )
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

    _columns = [
        "program", "comments", "date_added", "url", "status", "term",
        "us_or_international", "gpa", "gre", "gre_v", "gre_aw",
        "degree", "llm_generated_program", "llm_generated_university",
    ]
    insert_query = sql.SQL(
        "INSERT INTO {} ({}) VALUES ({}) ON CONFLICT ({}) DO NOTHING"
    ).format(
        sql.Identifier("applicants"),
        sql.SQL(", ").join(sql.Identifier(c) for c in _columns),
        sql.SQL(", ").join(sql.Placeholder(c) for c in _columns),
        sql.Identifier("url"),
    )
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
    verify_query = sql.SQL("SELECT COUNT(*) FROM {} LIMIT %s").format(
        sql.Identifier("applicants"),
    )
    cursor.execute(verify_query, (agg_limit,))
    logger.info("Total rows in table: %s", cursor.fetchone()[0])

    conn.close()

if __name__ == "__main__":
    main()
