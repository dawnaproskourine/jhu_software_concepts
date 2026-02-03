"""
Flask dashboard for applicant_data analysis.

Serves a Q&A-style web page displaying analysis results from the
applicant_data PostgreSQL database. Also provides an endpoint to
scrape new data from thegradcafe.com and insert it into the database.
LLM-based standardization populates llm_generated_program and
llm_generated_university fields for newly pulled data.
"""

from datetime import datetime
from flask import Flask, render_template, jsonify, request
import psycopg

# clean_text strips NUL bytes; parse_float extracts numeric values from prefixed strings
from load_data import clean_text, parse_float
# run_queries returns all analysis results as a dict; DB_CONFIG holds connection params
from query_data import run_queries, DB_CONFIG
# LLM standardization for program/university names
from llm_standardizer import standardize as llm_standardize

app = Flask(__name__,
            template_folder="website/templates",
            static_folder="website/static")


@app.route("/")
def index():
    """Render the dashboard by running all analysis queries."""
    conn = psycopg.connect(**DB_CONFIG)
    data = run_queries(conn)
    conn.close()
    return render_template("index.html", **data)


@app.route("/pull-data", methods=["POST"])
def pull_data():
    """Scrape new data from thegradcafe.com and insert into the database.

    Accepts JSON body with optional 'pages' field (default 5).
    Returns JSON with scraped count, inserted count, and a message.
    Duplicate URLs are skipped via ON CONFLICT.
    """
    # Lazy import so the scraper is only loaded when this route is called
    from scrape import scrape_data

    # Number of survey pages to scrape (default 5)
    pages = request.json.get("pages", 5) if request.is_json else 5

    try:
        rows = scrape_data(max_pages=pages)
    except Exception as e:
        return jsonify({"error": f"Scrape failed: {e}"}), 500

    if not rows:
        return jsonify({"scraped": 0, "inserted": 0,
                         "message": "No data returned from scraper."})

    conn = psycopg.connect(**DB_CONFIG)
    conn.autocommit = True
    cur = conn.cursor()

    inserted = 0
    for row in rows:
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
        except Exception:
            # If LLM fails, leave fields empty
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
        if cur.rowcount > 0:
            inserted += 1

    conn.close()

    return jsonify({
        "scraped": len(rows),
        "inserted": inserted,
        "message": f"Scraped {len(rows)} entries, {inserted} new rows added to database.",
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)