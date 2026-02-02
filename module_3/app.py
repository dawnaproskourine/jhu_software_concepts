"""Flask dashboard for applicant_data analysis."""

from flask import Flask, render_template
import psycopg

app = Flask(__name__)

DB_CONFIG = {
    "dbname": "applicant_data",
    "user": "dawnaproskourine",
    "host": "127.0.0.1",
}


def run_queries():
    """Run all 12 analysis queries and return results as a dict."""
    conn = psycopg.connect(**DB_CONFIG)
    cur = conn.cursor()
    results = {}

    # 1. Fall 2026 count
    cur.execute("SELECT COUNT(*) FROM applicants WHERE term = 'Fall 2026'")
    results["fall_2026_count"] = cur.fetchone()[0]

    # 2. International percentage
    cur.execute("""
        SELECT ROUND(
            100.0 * COUNT(*) FILTER (WHERE us_or_international = 'International')
            / COUNT(*), 2
        ) FROM applicants
    """)
    results["international_pct"] = cur.fetchone()[0]

    # 3. Average GPA, GRE, GRE V, GRE AW
    cur.execute("""
        SELECT
            ROUND(AVG(gpa)::numeric, 2),
            ROUND(AVG(gre)::numeric, 2),
            ROUND(AVG(gre_v)::numeric, 2),
            ROUND(AVG(gre_aw)::numeric, 2)
        FROM applicants
        WHERE gpa IS NOT NULL OR gre IS NOT NULL
              OR gre_v IS NOT NULL OR gre_aw IS NOT NULL
    """)
    row = cur.fetchone()
    results["avg_gpa"] = row[0]
    results["avg_gre"] = row[1]
    results["avg_gre_v"] = row[2]
    results["avg_gre_aw"] = row[3]

    # 4. Average GPA of American students in Fall 2026
    cur.execute("""
        SELECT ROUND(AVG(gpa)::numeric, 2)
        FROM applicants
        WHERE us_or_international = 'American'
          AND term = 'Fall 2026'
          AND gpa IS NOT NULL
    """)
    results["american_gpa_fall2026"] = cur.fetchone()[0]

    # 5. Acceptance percentage for Fall 2026
    cur.execute("""
        SELECT ROUND(
            100.0 * COUNT(*) FILTER (WHERE status ILIKE 'Accepted%%')
            / COUNT(*), 2
        ) FROM applicants
        WHERE term = 'Fall 2026'
    """)
    results["acceptance_pct_fall2026"] = cur.fetchone()[0]

    # 6. Average GPA of accepted applicants in Fall 2026
    cur.execute("""
        SELECT ROUND(AVG(gpa)::numeric, 2)
        FROM applicants
        WHERE term = 'Fall 2026'
          AND status ILIKE 'Accepted%%'
          AND gpa IS NOT NULL
    """)
    results["accepted_gpa_fall2026"] = cur.fetchone()[0]

    # 7. JHU Masters in Computer Science count
    cur.execute("""
        SELECT COUNT(*)
        FROM applicants
        WHERE llm_generated_university ILIKE '%%Johns Hopkins%%'
          AND llm_generated_program ILIKE '%%Computer Science%%'
          AND degree = 'Masters'
    """)
    results["jhu_cs_masters"] = cur.fetchone()[0]

    # 8. PhD CS acceptances (program field)
    cur.execute("""
        SELECT COUNT(*)
        FROM applicants
        WHERE term ILIKE '%%2026'
          AND status ILIKE 'Accepted%%'
          AND degree = 'PhD'
          AND program ILIKE '%%Computer Science%%'
          AND (program ILIKE '%%Georgetown University%%'
            OR program ILIKE '%%Massachusetts Institute of Technology%%'
            OR program ILIKE '%%Stanford University%%'
            OR program ILIKE '%%Carnegie Mellon University%%')
    """)
    results["phd_cs_program"] = cur.fetchone()[0]

    # 9. PhD CS acceptances (llm fields)
    cur.execute("""
        SELECT COUNT(*)
        FROM applicants
        WHERE term ILIKE '%%2026'
          AND status ILIKE 'Accepted%%'
          AND degree = 'PhD'
          AND llm_generated_program ILIKE '%%Computer Science%%'
          AND llm_generated_university IN (
              'Georgetown University',
              'Massachusetts Institute of Technology',
              'Stanford University',
              'Carnegie Mellon University'
          )
    """)
    results["phd_cs_llm"] = cur.fetchone()[0]

    # 10. Top 10 programs
    cur.execute("""
        SELECT llm_generated_program, COUNT(*) AS num_applicants
        FROM applicants
        WHERE llm_generated_program IS NOT NULL AND llm_generated_program != ''
        GROUP BY llm_generated_program
        ORDER BY num_applicants DESC
        LIMIT 10
    """)
    results["top_programs"] = cur.fetchall()

    # 11. Top 10 universities
    cur.execute("""
        SELECT llm_generated_university, COUNT(*) AS num_applicants
        FROM applicants
        WHERE llm_generated_university IS NOT NULL AND llm_generated_university != ''
        GROUP BY llm_generated_university
        ORDER BY num_applicants DESC
        LIMIT 10
    """)
    results["top_universities"] = cur.fetchall()

    # 12a. Acceptance rate by degree type
    cur.execute("""
        SELECT
            degree,
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE status ILIKE 'Accepted%%') AS accepted,
            ROUND(
                100.0 * COUNT(*) FILTER (WHERE status ILIKE 'Accepted%%')
                / COUNT(*), 2
            ) AS acceptance_rate
        FROM applicants
        WHERE degree IN ('PhD', 'Masters')
        GROUP BY degree
        ORDER BY degree
    """)
    results["rate_by_degree"] = cur.fetchall()

    # 12b. Acceptance rate by nationality
    cur.execute("""
        SELECT
            us_or_international,
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE status ILIKE 'Accepted%%') AS accepted,
            ROUND(
                100.0 * COUNT(*) FILTER (WHERE status ILIKE 'Accepted%%')
                / COUNT(*), 2
            ) AS acceptance_rate
        FROM applicants
        WHERE us_or_international IN ('American', 'International')
        GROUP BY us_or_international
        ORDER BY us_or_international
    """)
    results["rate_by_nationality"] = cur.fetchall()

    conn.close()
    return results


@app.route("/")
def index():
    data = run_queries()
    return render_template("index.html", **data)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
