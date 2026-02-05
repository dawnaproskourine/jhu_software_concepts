"""
Flask dashboard for applicant_data analysis.

Serves a Q&A-style web page displaying analysis results from the
applicant_data PostgreSQL database. Also provides an endpoint to
scrape new data from thegradcafe.com and insert it into the database.
LLM-based standardization populates llm_generated_program and
llm_generated_university fields for newly pulled data.
"""

import logging
import time
from datetime import datetime
from typing import Any

from flask import Flask, render_template, jsonify, request, Response
import psycopg
from psycopg import OperationalError
from psycopg.cursor import Cursor

from load_data import clean_text, parse_float
from query_data import run_queries, DB_CONFIG
from llm_standardizer import standardize as llm_standardize
from cleanup_data import fix_gre_aw, fix_uc_universities

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__,
            template_folder="website/templates",
            static_folder="website/static")


@app.route("/")
def index() -> str:
    """Render the dashboard by running all analysis queries."""
    try:
        conn = psycopg.connect(**DB_CONFIG)
        data = run_queries(conn)
        conn.close()
        return render_template("index.html", **data)
    except OperationalError as e:
        logger.error(f"Database connection failed: {e}")
        return render_template("index.html", error="Database connection failed")


def insert_row(cur: Cursor, row: dict[str, Any]) -> bool:
    """Insert a single row into the database with LLM standardization.

    Returns True if the row was inserted, False if it was a duplicate.
    """
    # Parse the "Added on January 15, 2026" date format
    date_str = clean_text(row.get("date_added", "")).replace("Added on ", "")
    try:
        date_val = datetime.strptime(date_str, "%B %d, %Y").date()
    except ValueError:
        date_val = None

    # Run LLM standardization on the program field
    program_text = clean_text(row.get("program", ""))
    try:
        llm_result = llm_standardize(program_text)
        llm_program = llm_result.get("standardized_program", "")
        llm_university = llm_result.get("standardized_university", "")
    except (KeyError, TypeError, RuntimeError) as e:
        logger.warning(f"LLM standardization failed for '{program_text}': {e}")
        llm_program = ""
        llm_university = ""

    # Insert row; ON CONFLICT (url) DO NOTHING skips duplicates
    cur.execute("""
        INSERT INTO applicants (
            program, comments, date_added, url, status, term,
            us_or_international, gpa, gre, gre_v, gre_aw, degree,
            llm_generated_program, llm_generated_university
        ) VALUES (
            %(program)s, %(comments)s, %(date_added)s, %(url)s,
            %(status)s, %(term)s, %(us_or_international)s,
            %(gpa)s, %(gre)s, %(gre_v)s, %(gre_aw)s, %(degree)s,
            %(llm_program)s, %(llm_university)s
        )
        ON CONFLICT (url) DO NOTHING
    """, {
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
    })
    return cur.rowcount > 0


@app.route("/pull-data", methods=["POST"])
def pull_data() -> tuple[Response, int] | Response:
    """Scrape new data from thegradcafe.com until caught up with database.

    Scrapes pages one at a time, stopping when a page has all duplicates
    (meaning we've caught up with existing data). No gaps are left.

    Accepts JSON body with optional 'max_pages' field (default 100) as safety limit.
    Returns JSON with pages scraped, entries processed, new rows inserted.
    """
    # Lazy imports
    from scrape import fetch_page, parse_survey, get_max_pages
    from urllib.error import URLError, HTTPError

    # Validate and get max_pages with bounds checking
    raw_max_pages = request.json.get("max_pages", 100) if request.is_json else 100
    try:
        max_pages = max(1, min(int(raw_max_pages), 500))  # Clamp between 1 and 500
    except (ValueError, TypeError):
        max_pages = 100

    base_url = "https://www.thegradcafe.com/survey/"
    delay = 0.5  # seconds between page fetches

    try:
        conn = psycopg.connect(**DB_CONFIG)
        conn.autocommit = True
    except OperationalError as e:
        logger.error(f"Database connection failed: {e}")
        return jsonify({"error": "Database connection failed"}), 500

    cur = conn.cursor()

    total_scraped = 0
    total_inserted = 0
    pages_fetched = 0

    try:
        # Fetch first page
        html = fetch_page(base_url)
        total_pages = get_max_pages(html)
        pages_to_check = min(total_pages, max_pages)

        for page_num in range(1, pages_to_check + 1):
            if page_num > 1:
                time.sleep(delay)
                page_url = f"{base_url}?page={page_num}"
                html = fetch_page(page_url)

            rows = parse_survey(html)
            if not rows:
                break

            # Convert comment lists to strings
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

            # If no new entries on this page, we've caught up
            if page_inserted == 0:
                logger.info(f"Caught up after {pages_fetched} pages")
                break

    except (URLError, HTTPError) as e:
        logger.error(f"Network error during scrape: {e}")
        conn.close()
        return jsonify({"error": f"Network error: {e}"}), 500
    except psycopg.Error as e:
        logger.error(f"Database error during scrape: {e}")
        conn.close()
        return jsonify({"error": f"Database error: {e}"}), 500

    # Run data cleanup if new entries were inserted
    cleaned_gre = 0
    cleaned_uc = 0
    if total_inserted > 0:
        logger.info("Running data cleanup on new entries...")
        cleaned_gre = fix_gre_aw(conn)
        cleaned_uc = fix_uc_universities(conn)

    conn.close()

    if total_inserted == 0:
        message = f"Already up to date. Checked {pages_fetched} page(s), no new entries found."
    else:
        message = f"Caught up! Scraped {pages_fetched} page(s), {total_scraped} entries checked, {total_inserted} new rows added."
        if cleaned_gre > 0 or cleaned_uc > 0:
            message += f" Cleaned: {cleaned_gre} GRE AW, {cleaned_uc} UC names."

    logger.info(message)
    return jsonify({
        "pages_fetched": pages_fetched,
        "scraped": total_scraped,
        "inserted": total_inserted,
        "cleaned_gre_aw": cleaned_gre,
        "cleaned_uc": cleaned_uc,
        "message": message,
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)