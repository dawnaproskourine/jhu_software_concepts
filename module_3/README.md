
### Name: Dawna Jones Proskourine
### Hopkins ID: 2356B8
### Course: EN.605.256.82.SP26
### Module 3 - Database Queries Assignment Experiment

# DESCRIPTION

## load_data.py

Initial data loader that populates the PostgreSQL `applicants` table from `llm_extended_applicant_data.json`.
Creates the database and table if they don't exist. The script was run once to load the initial dataset
(49,980 rows processed, 49,962 inserted after deduplication).

```bash
python3 load_data.py
```

## app.py — Flask Analysis Dashboard

A single-page Flask web application that displays analysis results from the `applicant_data` PostgreSQL database as a
Q&A-style dashboard. Queries are defined in `query_data.py` and shared between the dashboard and CLI.

### Prerequisites

- Python 3
- PostgreSQL running locally with the `applicant_data` database populated (via `load_data.py`)
- Required packages: `flask`, `psycopg`, `llama-cpp-python`, `huggingface_hub`, `beautifulsoup4`

### Running

```bash
python3 app.py
```

Visit `http://localhost:8080` in a browser.

### Routes

| Route       | Method | Description                                                                    |
|-------------|--------|--------------------------------------------------------------------------------|
| `/`         | GET    | Renders the dashboard with all 13 analysis queries                             |
| `/pull-data`| POST   | Scrapes new entries from thegradcafe.com, processes with LLM, and runs cleanup |

### Analysis Queries

The dashboard displays 13 questions with answers in a Q&A format:

- Total applicant count
- Fall 2026 applicant count
- International student percentage
- Fall 2026 acceptance percentage
- Average GPA, GRE, GRE V, GRE AW
- Average GPA of American students (Fall 2026)
- Average GPA of accepted applicants (Fall 2026)
- JHU Masters in Computer Science applicants (handles misspellings like "John Hopkins")
- PhD CS acceptances at Georgetown, MIT, Stanford, CMU (program field vs LLM field)
- Top 10 most popular programs (Fall 2026)
- Top 10 most popular universities (Fall 2026)
- Acceptance rate by degree type (Masters, PhD, PsyD) (Fall 2026)
- Acceptance rate by nationality (Fall 2026)

### Controls

- **Pull Data** (top left) — Scrapes thegradcafe.com/survey page by page until caught up with existing database
entries (stops when a page has all duplicates). This ensures no gaps in data. Each new row is processed through the
TinyLlama LLM to populate `llm_generated_program` and `llm_generated_university` fields. After inserting, data cleanup
automatically runs to fix invalid GRE AW scores and normalize UC campus names.

- **Update Analysis** (top right) — Refreshes the page to re-run all queries against the current database. Disabled
while a Pull Data request is in progress.

## query_data.py

Shared analysis queries used by both the Flask dashboard and CLI. Exports `DB_CONFIG` for database connection
parameters and `run_queries()` which returns all analysis results as a dictionary.

```bash
python3 query_data.py  # Run standalone to print results to console
```

## llm_standardizer.py

LLM-based standardization module using TinyLlama (via llama_cpp) to parse and standardize program/university strings
from GradCafe data. Features:

- Few-shot prompting for consistent JSON output
- Rule-based fallback parsing if LLM returns invalid JSON
- Fuzzy matching against canonical program and university lists (290 programs, 1000+ universities)
- Automatic abbreviation expansion (e.g., "MIT" → "Massachusetts Institute of Technology")
- UC campus normalization (e.g., "UC Berkeley" → "University of California, Berkeley")

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

**Note:** These cleanup functions are now automatically called after Pull Data inserts new entries. The standalone
script can still be run manually for one-time bulk cleanup:

```bash
python3 cleanup_data.py
```

## scrape.py

GradCafe web scraper that extracts applicant data from thegradcafe.com/survey. Respects robots.txt via
`RobotsChecker.py`. Used by `app.py` for the Pull Data feature.

### Project Structure

```
module_3/
├── app.py                           # Flask application
├── query_data.py                    # Analysis queries (shared by app.py and CLI)
├── load_data.py                     # Initial database loader (JSON → PostgreSQL)
├── backfill_llm.py                  # Backfill missing LLM fields
├── cleanup_data.py                  # Data quality cleanup (GRE AW, UC campuses)
├── llm_standardizer.py              # LLM-based program/university standardization
├── canon_programs.txt               # Canonical program names (290 entries)
├── canon_universities.txt           # Canonical university names (1000+ entries)
├── scrape.py                        # GradCafe web scraper
├── RobotsChecker.py                 # robots.txt compliance checker
├── llm_extended_applicant_data.json # Initial dataset from module_2
├── website/
│   ├── templates/
│   │   └── index.html               # Jinja2 Q&A dashboard template
│   └── static/
│       ├── style.css                # Dashboard styles
│       └── dashboard.js             # Pull Data / Update Analysis logic
└── README.md
```

## Code Quality

All Python files follow these practices:

- **Type hints** — Function signatures include type annotations
- **Logging** — Uses Python `logging` module instead of `print()` for production use
- **Specific exceptions** — Catches specific exception types (e.g., `OperationalError`, `JSONDecodeError`)
- **Input validation** — Validates user inputs (e.g., `max_pages` clamped to 1-500)
- **No duplicate code** — Shared constants imported from single source (e.g., `DB_CONFIG`, `UC_CAMPUS_PATTERNS`)
- **SQL injection protection** — All queries use parameterized statements

# References

* https://realpython.com/python-sql-libraries/
* https://medium.com/dataexplorations/sqlalchemy-orm-a-more-pythonic-way-of-interacting-with-your-database-935b57fd2d4d
* https://flask.palletsprojects.com/
* https://www.psycopg.org/psycopg3/docs/
* https://llama-cpp-python.readthedocs.io/
* https://huggingface.co/docs/huggingface_hub/