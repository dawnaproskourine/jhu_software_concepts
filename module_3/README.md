
### Name: Dawna Jones Proskourine
### Hopkins ID: 2356B8
### Course: EN.605.256.82.SP26
### Module 3 - Databases & Analysis Dashboard

# DESCRIPTION

## load_data.py

Loads `llm_extended_applicant_data.json` into a PostgreSQL `applicants` table.
The script ran successfully. 49,980 rows were processed, and 49,962 ended up in the table (18 had duplicate URLs and
were skipped by ON CONFLICT).

## app.py — Flask Analysis Dashboard

A single-page Flask web application that displays analysis results from the `applicant_data` PostgreSQL database as a
Q&A-style dashboard. Queries are defined in `query_data.py` and shared between the dashboard and CLI.

### Prerequisites

- Python 3
- PostgreSQL running locally with the `applicant_data` database populated (via `load_data.py`)
- `flask` and `psycopg` packages installed

### Running

```bash
python3 app.py
```

Visit `http://localhost:8080` in a browser.

### Routes

| Route | Method | Description |
|-------|--------|-------------|
| `/` | GET | Renders the dashboard with all 13 analysis queries |
| `/pull-data` | POST | Scrapes new entries from thegradcafe.com and inserts them into the database |

### Analysis Queries

The dashboard displays 13 questions with answers in a Q&A format:

- Total applicant count
- Fall 2026 applicant count
- International student percentage
- Fall 2026 acceptance percentage
- Average GPA, GRE, GRE V, GRE AW
- Average GPA of American students (Fall 2026)
- Average GPA of accepted applicants (Fall 2026)
- JHU Masters in Computer Science applicants
- PhD CS acceptances at Georgetown, MIT, Stanford, CMU (program field vs LLM field)
- Top 10 most popular programs
- Top 10 most popular universities
- Acceptance rate by degree type
- Acceptance rate by nationality

### Controls

- **Pull Data** (bottom left) — Scrapes a configurable number of pages from thegradcafe.com/survey and inserts new
entries into the database. Duplicate URLs are skipped via `ON CONFLICT`.

- **Update Analysis** (bottom right) — Refreshes the page to re-run all queries against the current database. Disabled
while a Pull Data request is in progress.

### Project Structure

```
module_3/
├── app.py                  # Flask application
├── query_data.py           # Analysis queries (shared by app.py and CLI)
├── load_data.py            # Database loader (JSON → PostgreSQL)
├── scrape.py               # GradCafe scraper (from module_2)
├── RobotsChecker.py        # robots.txt checker (from module_2)
├── templates/
│   └── index.html          # Jinja2 Q&A dashboard template
├── static/
│   ├── style.css           # Dashboard styles
│   └── dashboard.js        # Pull Data / Update Analysis logic
└── README.md
```

# References
* https://realpython.com/python-sql-libraries/
* https://medium.com/dataexplorations/sqlalchemy-orm-a-more-pythonic-way-of-interacting-with-your-database-935b57fd2d4d
* https://flask.palletsprojects.com/
* https://www.psycopg.org/psycopg3/docs/