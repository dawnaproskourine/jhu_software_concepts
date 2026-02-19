"""
Flask dashboard for applicant_data analysis.

Serves a Q&A-style web page displaying analysis results from the
applicant_data PostgreSQL database. Also provides an endpoint to
scrape new data from thegradcafe.com and insert it into the database.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any

from urllib.error import URLError, HTTPError

from flask import Flask, render_template, jsonify, request, Response
import psycopg
from psycopg import OperationalError
from psycopg.cursor import Cursor

from scrape import fetch_page, parse_survey, get_max_pages

from load_data import clean_text, build_score_params, build_insert_query
from query_data import run_queries, DB_CONFIG
from cleanup_data import fix_gre_aw, fix_uc_universities

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

_INSERT_PARAM_KEYS = [
    "program", "comments", "date_added", "url", "status", "term",
    "us_or_international", "gpa", "gre", "gre_v", "gre_aw", "degree",
    "llm_program", "llm_university",
]


def insert_row(cur: Cursor, row: dict[str, Any]) -> bool:
    """Insert a single row into the database.

    Parses dates and inserts into the ``applicants`` table.
    Duplicates are skipped via ``ON CONFLICT (url) DO NOTHING``.

    :param cur: An open database cursor.
    :type cur: psycopg.cursor.Cursor
    :param row: A dictionary of scraped applicant data.
    :type row: dict[str, Any]
    :returns: ``True`` if the row was inserted, ``False`` if it was a duplicate.
    :rtype: bool
    """
    # Parse the "Added on January 15, 2026" date format
    date_str = clean_text(row.get("date_added", "")).replace("Added on ", "")
    try:
        date_val = datetime.strptime(date_str, "%B %d, %Y").date()
    except ValueError:
        date_val = None

    query = build_insert_query(param_keys=_INSERT_PARAM_KEYS)
    params = {
        "program": clean_text(row.get("program", "")),
        "comments": clean_text(row.get("comments", "")),
        "date_added": date_val,
        "url": clean_text(row.get("url", "")),
        "status": clean_text(row.get("status", "")),
        "term": clean_text(row.get("term", "")),
        "us_or_international": clean_text(row.get("US/International", "")),
        **build_score_params(row),
        "llm_program": clean_text(row.get("program_name", "")),
        "llm_university": clean_text(row.get("school", "")),
    }
    cur.execute(query, params)
    return cur.rowcount > 0


def _parse_max_pages(req):
    """Validate and clamp ``max_pages`` from the request body.

    :returns: An integer between 1 and 500 (default 100).
    :rtype: int
    """
    raw_max = (req.json.get("max_pages", 100)
               if req.is_json else 100)
    try:
        return max(1, min(int(raw_max), 500))
    except (ValueError, TypeError):
        return 100


def _scrape_pages(conn, _fetch, _parse, _maxpg, base_url, max_pages, delay):
    """Fetch and insert pages until caught up or limit reached.

    :returns: ``(pages_fetched, total_scraped, total_inserted)``
    :rtype: tuple[int, int, int]
    """
    cur = conn.cursor()
    total_scraped = 0
    total_inserted = 0
    pages_fetched = 0

    html = _fetch(base_url)
    pages_to_check = min(_maxpg(html), max_pages)

    for page_num in range(1, pages_to_check + 1):
        if page_num > 1:
            time.sleep(delay)
            html = _fetch(f"{base_url}?page={page_num}")

        rows = _parse(html)
        if not rows:
            break

        for row in rows:
            if isinstance(row.get("comments"), list):
                row["comments"] = " ".join(row["comments"]).strip()

        pages_fetched += 1
        page_inserted = 0

        for row in rows:
            total_scraped += 1
            if insert_row(cur, row):
                total_inserted += 1
                page_inserted += 1

        if page_inserted == 0:
            logger.info("Caught up after %d pages", pages_fetched)
            break

    return pages_fetched, total_scraped, total_inserted


def _run_cleanup(conn, total_inserted):
    """Run data-cleanup routines when new rows were inserted.

    :returns: ``(cleaned_gre, cleaned_uc)``
    :rtype: tuple[int, int]
    """
    if total_inserted == 0:
        return 0, 0
    logger.info("Running data cleanup on new entries...")
    return fix_gre_aw(conn), fix_uc_universities(conn)


def _handle_index():
    """Core logic for the ``/`` route."""
    try:
        with psycopg.connect(**DB_CONFIG) as conn:
            data = run_queries(conn)
        return render_template("index.html", **data)
    except OperationalError as e:
        logger.error("Database connection failed: %s", e)
        return render_template("index.html", error="Database connection failed")


def _handle_pull_data(_fetch, _parse, _maxpg):
    """Core logic for the ``/pull-data`` route.

    :returns: A Flask JSON response (possibly with a status code tuple).
    """
    max_pages = _parse_max_pages(request)
    base_url = "https://www.thegradcafe.com/survey/"
    delay = 0.5

    try:
        conn = psycopg.connect(**DB_CONFIG)
    except OperationalError as e:
        logger.error("Database connection failed: %s", e)
        return jsonify({"error": "Database connection failed"}), 500

    try:
        pages_fetched, total_scraped, total_inserted = _scrape_pages(
            conn, _fetch, _parse, _maxpg, base_url, max_pages, delay,
        )
    except (URLError, HTTPError) as e:
        logger.error("Network error during scrape: %s", e)
        conn.rollback()
        conn.close()
        return jsonify({"error": "Network error during scrape"}), 500
    except psycopg.Error as e:
        logger.error("Database error during scrape: %s", e)
        conn.rollback()
        conn.close()
        return jsonify({"error": "Database error during scrape"}), 500

    try:
        cleaned_gre, cleaned_uc = _run_cleanup(conn, total_inserted)
    except psycopg.Error as e:
        logger.error("Cleanup error: %s", e)
        conn.rollback()
        conn.close()
        return jsonify({"error": "Cleanup error"}), 500

    conn.commit()
    conn.close()

    message = _build_pull_message(
        pages_fetched, total_scraped, total_inserted,
        cleaned_gre, cleaned_uc,
    )
    logger.info(message)
    return jsonify({
        "pages_fetched": pages_fetched,
        "scraped": total_scraped,
        "inserted": total_inserted,
        "cleaned_gre_aw": cleaned_gre,
        "cleaned_uc": cleaned_uc,
        "message": message,
    })


def create_app(testing=False, fetch_page_fn=None,
               parse_survey_fn=None, get_max_pages_fn=None):
    """Application factory for the Flask dashboard.

    :param testing: If ``True``, enables Flask's TESTING config flag.
    :type testing: bool
    :param fetch_page_fn: Optional callable replacing ``scrape.fetch_page``.
    :param parse_survey_fn: Optional callable replacing ``scrape.parse_survey``.
    :param get_max_pages_fn: Optional callable replacing ``scrape.get_max_pages``.
    :returns: Configured Flask application with routes registered.
    :rtype: Flask
    """
    application = Flask(__name__,
                        template_folder="website/_templates",
                        static_folder="website/_static")
    if testing:
        application.config["TESTING"] = True

    @application.route("/")
    def index() -> str:
        """Render the dashboard."""
        return _handle_index()

    @application.route("/pull-data", methods=["POST"])
    def pull_data() -> tuple[Response, int] | Response:
        """Scrape new data from thegradcafe.com until caught up."""
        _fetch = fetch_page_fn or fetch_page
        _parse = parse_survey_fn or parse_survey
        _maxpg = get_max_pages_fn or get_max_pages
        return _handle_pull_data(_fetch, _parse, _maxpg)

    return application


def _build_pull_message(pages_fetched, total_scraped,
                        total_inserted, cleaned_gre, cleaned_uc):
    """Build the human-readable status message for pull_data response."""
    if total_inserted == 0:
        return (f"Already up to date. Checked {pages_fetched} "
                f"page(s), no new entries found.")
    msg = (f"Caught up! Scraped {pages_fetched} page(s), "
           f"{total_scraped} entries checked, "
           f"{total_inserted} new rows added.")
    if cleaned_gre > 0 or cleaned_uc > 0:
        msg += (f" Cleaned: {cleaned_gre} GRE AW, "
                f"{cleaned_uc} UC names.")
    return msg


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)
