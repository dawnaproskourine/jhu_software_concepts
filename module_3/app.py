"""Flask dashboard for applicant_data analysis."""

from datetime import datetime
from flask import Flask, render_template, jsonify, request
import psycopg

from load_data import clean_text, parse_float
from query_data import run_queries, DB_CONFIG

app = Flask(__name__)


@app.route("/")
def index():
    conn = psycopg.connect(**DB_CONFIG)
    data = run_queries(conn)
    conn.close()
    return render_template("index.html", **data)


@app.route("/pull-data", methods=["POST"])
def pull_data():
    """Scrape new data from thegradcafe.com and insert into the database."""
    from scrape import scrape_data

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
        date_str = clean_text(row.get("date_added", "")).replace("Added on ", "")
        try:
            date_val = datetime.strptime(date_str, "%B %d, %Y").date()
        except ValueError:
            date_val = None

        cur.execute("""
            INSERT INTO applicants (
                program, comments, date_added, url, status, term,
                us_or_international, gpa, gre, gre_v, gre_aw, degree
            ) VALUES (
                %(program)s, %(comments)s, %(date_added)s, %(url)s,
                %(status)s, %(term)s, %(us_or_international)s,
                %(gpa)s, %(gre)s, %(gre_v)s, %(gre_aw)s, %(degree)s
            )
            ON CONFLICT (url) DO NOTHING
        """, {
            "program": clean_text(row.get("program", "")),
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
