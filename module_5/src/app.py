"""
Flask dashboard for applicant_data analysis.

Serves a Q&A-style web page displaying analysis results from the
applicant_data PostgreSQL database. Also provides an endpoint to
scrape new data from thegradcafe.com and insert it into the database.
"""
# pylint: disable=R0801
from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any

from urllib.error import URLError, HTTPError

from flask import Flask, render_template, jsonify, request, Response
import psycopg
from psycopg import OperationalError, sql
from psycopg.cursor import Cursor

from scrape import fetch_page, parse_survey, get_max_pages

from load_data import clean_text, parse_float
from query_data import run_queries, DB_CONFIG
from cleanup_data import fix_gre_aw, fix_uc_universities

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

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

    program_text = clean_text(row.get("program", ""))
    llm_program = ""
    llm_university = ""

    # Insert row; ON CONFLICT (url) DO NOTHING skips duplicates
    _columns = [
        "program", "comments", "date_added", "url", "status", "term",
        "us_or_international", "gpa", "gre", "gre_v", "gre_aw", "degree",
        "llm_generated_program", "llm_generated_university",
    ]
    _param_keys = [
        "program", "comments", "date_added", "url", "status", "term",
        "us_or_international", "gpa", "gre", "gre_v", "gre_aw", "degree",
        "llm_program", "llm_university",
    ]
    query = sql.SQL(
        "INSERT INTO {} ({}) VALUES ({}) ON CONFLICT ({}) DO NOTHING"
    ).format(
        sql.Identifier("applicants"),
        sql.SQL(", ").join(sql.Identifier(c) for c in _columns),
        sql.SQL(", ").join(sql.Placeholder(k) for k in _param_keys),
        sql.Identifier("url"),
    )
    params = {
        "program": program_text,
        "comments": clean_text(row.get("comments", "")),
        "date_added": date_val,
        "url": clean_text(row.get("url", "")),
        "status": clean_text(row.get("status", "")),
        "term": clean_text(row.get("term", "")),
        "us_or_international": clean_text(row.get("US/International", "")),
        "gpa": parse_float(row.get("GPA", ""), "GPA"),
        "gre": parse_float(row.get("GRE", ""), "GRE"),
        "gre_v": parse_float(row.get("GRE V", ""), "GRE V"),
        "gre_aw": parse_float(row.get("GRE AW", ""), "GRE AW"),
        "degree": clean_text(row.get("Degree", "")),
        "llm_program": llm_program,
        "llm_university": llm_university,
    }
    cur.execute(query, params)
    return cur.rowcount > 0


def create_app(testing=False, fetch_page_fn=None,  # pylint: disable=too-many-statements
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
        """Render the dashboard by running all analysis queries.

        :returns: Rendered HTML of the dashboard page.
        :rtype: str
        """
        try:
            with psycopg.connect(**DB_CONFIG) as conn:
                data = run_queries(conn)
            return render_template("index.html", **data)
        except OperationalError as e:
            logger.error("Database connection failed: %s", e)
            return render_template("index.html", error="Database connection failed")

    @application.route("/pull-data", methods=["POST"])
    def pull_data() -> tuple[Response, int] | Response:  # pylint: disable=too-many-locals,too-many-branches,too-many-statements
        """Scrape new data from thegradcafe.com until caught up.

        Scrapes pages one at a time, stopping when a page has all
        duplicates (meaning we've caught up with existing data).
        Accepts a JSON body with an optional ``max_pages`` field
        (default 100) as a safety limit.

        :returns: JSON response with pages scraped, entries processed,
            and new rows inserted, or a tuple of (response, status_code)
            on error.
        :rtype: flask.Response or tuple[flask.Response, int]
        """
        # Dependency injection: use provided callables or module-level imports
        _fetch = fetch_page_fn or fetch_page
        _parse = parse_survey_fn or parse_survey
        _maxpg = get_max_pages_fn or get_max_pages

        # Validate and get max_pages with bounds checking
        raw_max = (request.json.get("max_pages", 100)
                   if request.is_json else 100)
        try:
            max_pages = max(1, min(int(raw_max), 500))
        except (ValueError, TypeError):
            max_pages = 100

        base_url = "https://www.thegradcafe.com/survey/"
        delay = 0.5  # seconds between page fetches

        try:
            conn = psycopg.connect(**DB_CONFIG)
        except OperationalError as e:
            logger.error("Database connection failed: %s", e)
            return jsonify({"error": "Database connection failed"}), 500

        cur = conn.cursor()

        total_scraped = 0
        total_inserted = 0
        pages_fetched = 0

        try:
            # Fetch first page
            html = _fetch(base_url)
            total_pages = _maxpg(html)
            pages_to_check = min(total_pages, max_pages)

            for page_num in range(1, pages_to_check + 1):
                if page_num > 1:
                    time.sleep(delay)
                    page_url = f"{base_url}?page={page_num}"
                    html = _fetch(page_url)

                rows = _parse(html)
                if not rows:
                    break

                # Convert comment lists to strings
                for row in rows:
                    if isinstance(row.get("comments"), list):
                        row["comments"] = " ".join(
                            row["comments"]
                        ).strip()

                pages_fetched += 1
                page_inserted = 0

                for row in rows:
                    total_scraped += 1
                    if insert_row(cur, row):
                        total_inserted += 1
                        page_inserted += 1

                # If no new entries on this page, we've caught up
                if page_inserted == 0:
                    logger.info("Caught up after %d pages", pages_fetched)
                    break

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

        # Run data cleanup if new entries were inserted
        cleaned_gre = 0
        cleaned_uc = 0
        if total_inserted > 0:
            try:
                logger.info("Running data cleanup on new entries...")
                cleaned_gre = fix_gre_aw(conn)
                cleaned_uc = fix_uc_universities(conn)
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
