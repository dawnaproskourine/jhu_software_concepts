
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
| `/` | GET | Renders the dashboard with all 12 analysis queries |
| `/pull-data` | POST | Scrapes new entries from thegradcafe.com and inserts them into the database |

### Dashboard Sections

- **Overview Stats** — Fall 2026 applicant count, international student percentage, acceptance percentage
- **GPA & Test Scores** — Average GPA/GRE/GRE V/GRE AW, American student GPA, accepted applicant GPA
- **Specific Queries** — JHU CS Masters applicants, PhD CS acceptances at select universities
- **Top 10 Rankings** — Most popular programs and universities
- **Acceptance Rates** — By degree type (PhD vs Masters) and by nationality (American vs International)

### Controls

- **Pull Data** (top left) — Scrapes a configurable number of pages from thegradcafe.com/survey and inserts new entries
into the database. Duplicate URLs are skipped via `ON CONFLICT`.

- **Update Analysis** (top right) — Refreshes the page to re-run all queries against the current database. Disabled while 
a Pull Data request is in progress.

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