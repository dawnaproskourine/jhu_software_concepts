
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
- `flask`, `psycopg`, `llama-cpp-python`, and `huggingface_hub` packages installed

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

- **Pull Data** (bottom left) — Scrapes thegradcafe.com/survey page by page until caught up with existing database
entries (stops when a page has all duplicates). This ensures no gaps in data. Each new row is processed through the
TinyLlama LLM to populate `llm_generated_program` and `llm_generated_university` fields.

- **Update Analysis** (bottom right) — Refreshes the page to re-run all queries against the current database. Disabled
while a Pull Data request is in progress.

### LLM Standardization

The `llm_standardizer.py` module uses TinyLlama (via llama_cpp) to parse and standardize program/university strings
from GradCafe data. Features:

- Few-shot prompting for consistent JSON output
- Rule-based fallback parsing if LLM returns invalid JSON
- Fuzzy matching against canonical program and university lists
- Automatic abbreviation expansion (e.g., "MIT" → "Massachusetts Institute of Technology")

## backfill_llm.py

Backfills missing `llm_generated_program` and `llm_generated_university` fields for existing database rows. Finds all
rows where these fields are NULL or empty, runs the LLM standardizer on each, and updates the database.

```bash
python3 backfill_llm.py
```

This script was run once to populate 211 rows that were missing LLM fields from the original data load.

## cleanup_data.py

Data quality cleanup script that fixes:

1. **Invalid GRE AW scores** — Sets values > 6 to NULL (GRE AW is scored 0-6; 146 rows had incorrect values)
2. **UC campus normalization** — Re-normalizes generic "University of California" entries to specific campuses
   (e.g., UCLA, Berkeley, San Diego) by extracting campus info from the original program field (532 rows updated)

### Project Structure

```
module_3/
├── app.py                  # Flask application
├── query_data.py           # Analysis queries (shared by app.py and CLI)
├── load_data.py            # Database loader (JSON → PostgreSQL)
├── backfill_llm.py         # Backfill missing LLM fields in existing rows
├── cleanup_data.py         # Fix GRE AW scores and normalize UC campuses
├── llm_standardizer.py     # LLM-based program/university standardization
├── canon_programs.txt      # Canonical program names for fuzzy matching
├── canon_universities.txt  # Canonical university names for fuzzy matching
├── scrape.py               # GradCafe scraper (from module_2)
├── RobotsChecker.py        # robots.txt checker (from module_2)
├── website/
│   ├── templates/
│   │   └── index.html      # Jinja2 Q&A dashboard template
│   └── static/
│       ├── style.css       # Dashboard styles
│       └── dashboard.js    # Pull Data / Update Analysis logic
└── README.md
```

# References
* https://realpython.com/python-sql-libraries/
* https://medium.com/dataexplorations/sqlalchemy-orm-a-more-pythonic-way-of-interacting-with-your-database-935b57fd2d4d
* https://flask.palletsprojects.com/
* https://www.psycopg.org/psycopg3/docs/