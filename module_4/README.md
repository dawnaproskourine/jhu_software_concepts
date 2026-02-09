
### Name: Dawna Jones Proskourine
### Hopkins ID: 2356B8
### Course: EN.605.256.82.SP26
### Module 4 - Testing and Documentation Experiment Assignment

# DESCRIPTION

## Sphinx Documentation

Module 4 adds Sphinx-based documentation and a `tests/` directory. Sphinx configuration lives in `source/conf.py`
and the documentation entry point is `source/index.rst`.

### Building Docs

From `module_4/`:

```bash
make html
```

Output is generated in the `build/` directory.

## Running from module_4

All source files live under `source/`. Scripts are run from the `module_4/` directory:

```bash
python3 source/load_data.py
python3 source/app.py
python3 source/query_data.py
python3 source/cleanup_data.py
```

## load_data.py

Initial data loader that populates the PostgreSQL `applicants` table from `llm_extended_applicant_data.json`.
Creates the database and table if they don't exist. The script was run once to load the initial dataset
(49,980 rows processed, 49,962 inserted after deduplication).

## app.py — Flask Analysis Dashboard

A single-page Flask web application that displays analysis results from the `applicant_data` PostgreSQL database as a
Q&A-style dashboard. Queries are defined in `query_data.py` and shared between the dashboard and CLI.

### Prerequisites

- Python 3
- PostgreSQL running locally with the `applicant_data` database populated (via `load_data.py`)
- Required packages: `flask`, `psycopg`, `llama-cpp-python`, `huggingface_hub`, `beautifulsoup4`

### Running

```bash
python3 source/app.py
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
python3 source/query_data.py  # Run standalone to print results to console
```

## llm_standardizer.py

LLM-based standardization module using TinyLlama (via llama_cpp) to parse and standardize program/university strings
from GradCafe data. Features:

- Few-shot prompting for consistent JSON output
- Rule-based fallback parsing if LLM returns invalid JSON
- Fuzzy matching against canonical program and university lists (290 programs, 1000+ universities)
- Automatic abbreviation expansion (e.g., "MIT" → "Massachusetts Institute of Technology")
- UC campus normalization (e.g., "UC Berkeley" → "University of California, Berkeley")

## cleanup_data.py

Data quality cleanup script that fixes:

1. **Invalid GRE AW scores** — Sets values > 6 to NULL (GRE AW is scored 0-6; 146 rows had incorrect values)
2. **UC campus normalization** — Re-normalizes generic "University of California" entries to specific campuses
   (e.g., UCLA, Berkeley, San Diego) by extracting campus info from the original program field (532 rows updated)

**Note:** These cleanup functions are now automatically called after Pull Data inserts new entries. The standalone
script can still be run manually for one-time bulk cleanup:

```bash
python3 source/cleanup_data.py
```

## scrape.py

GradCafe web scraper that extracts applicant data from thegradcafe.com/survey. Respects robots.txt via
`RobotsChecker.py`. Used by `app.py` for the Pull Data feature.

### Project Structure

```
module_4/
├── Makefile                                # Sphinx build commands
├── make.bat                                # Sphinx build commands (Windows)
├── README.md
├── requirements.txt
├── build/                                  # Sphinx-generated documentation output
├── tests/                                  # Test files
├── source/
│   ├── conf.py                             # Sphinx configuration
│   ├── index.rst                           # Sphinx documentation entry point
│   ├── app.py                              # Flask application
│   ├── query_data.py                       # Analysis queries (shared by app.py and CLI)
│   ├── load_data.py                        # Initial database loader (JSON → PostgreSQL)
│   ├── cleanup_data.py                     # Data quality cleanup (GRE AW, UC campuses)
│   ├── llm_standardizer.py                 # LLM-based program/university standardization
│   ├── canon_programs.txt                  # Canonical program names (290 entries)
│   ├── canon_universities.txt              # Canonical university names (1000+ entries)
│   ├── scrape.py                           # GradCafe web scraper
│   ├── RobotsChecker.py                    # robots.txt compliance checker
│   ├── llm_extended_applicant_data.json    # Initial dataset from module_2
│   ├── models/                             # LLM model files (TinyLlama)
│   └── website/
│       ├── _templates/
│       │   └── index.html                  # Jinja2 Q&A dashboard template
│       └── _static/
│           ├── style.css                   # Dashboard styles
│           └── dashboard.js                # Pull Data / Update Analysis logic
```

## Testing

The `tests/` directory contains a pytest suite covering four areas:

| File | Tests | What it covers |
|------|-------|----------------|
| `test_page_renders.py` | 14 | Page loads, 13 Q&A blocks, buttons, tables, ordered lists |
| `test_buttons_and_pull.py` | 9 | POST `/pull-data` JSON response, onclick wiring, JS inclusion, isPulling guard |
| `test_analysis_formatting.py` | 14 | Question labels, percentage formats (X.XX%), average values, all scalars rendered |
| `test_db_inserts.py` | 23 | `clean_text`, `parse_float`, `insert_row`, duplicate handling, column values, GRE AW cleanup |

### Running Tests

```bash
python3 -m pytest tests/ -v
python3 -m pytest tests/ -v --cov=source --cov-report=term-missing   # with coverage
```

DB integration tests require a running PostgreSQL instance and skip automatically if unavailable.

### Coverage Summary

| File | Coverage | Notes |
|------|----------|-------|
| `app.py` | 61% | `index()`, `insert_row()`, partial `pull_data()` |
| `cleanup_data.py` | 40% | `fix_gre_aw()` tested; `fix_uc_universities()` and `main()` not |
| `RobotsChecker.py` | 39% | Not directly tested (out of scope) |
| `llm_standardizer.py` | 36% | Intentionally mocked (668MB model) |
| `load_data.py` | 31% | `clean_text()` and `parse_float()` tested; `main()` loader not |
| `query_data.py` | 13% | Mocked in template tests; only `DB_CONFIG` import hit |
| `scrape.py` | 9% | Mocked to avoid HTTP requests |
| **TOTAL** | **29%** | |

Heavy modules (`scrape.py`, `llm_standardizer.py`, `query_data.py`) are intentionally mocked to avoid
network calls, loading a 668MB LLM model, and requiring live database queries during testing.

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
* https://realpython.com/pytest-python-testing/
* https://www.docslikecode.com/learn/01-sphinx-python-rtd/
* https://www.sphinx-doc.org/en/master/