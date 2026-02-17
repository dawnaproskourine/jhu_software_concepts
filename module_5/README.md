
### Name: Dawna Jones Proskourine
### Hopkins ID: 2356B8
### Course: EN.605.256.82.SP26
### Module 5 - Software Assurance + Secure SQL (SQLi Defense) Assignment

# DESCRIPTION

## Fresh Install

All commands are run from the `module_5/` directory.

### Option A: pip

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Option B: uv

```bash
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"
```

Both methods install the runtime dependencies (Flask, psycopg, beautifulsoup4)
plus dev tools (pytest, pytest-cov, pylint, pydeps).

To install only the runtime dependencies, omit the extras:

```bash
pip install -e .        # pip
uv pip install -e .     # uv
```

## Running from module_5

All source files live under `src/`. Set `DATABASE_URL` first, then run from the `module_5/` directory:

```bash
export DATABASE_URL="postgresql://myuser@localhost:5432/applicant_data"
python3 src/load_data.py
python3 src/app.py
python3 src/query_data.py
python3 src/cleanup_data.py
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
- Database environment variables set (see Database Configuration below)
- Required packages: `pip install -r requirements.txt` (Flask, psycopg, beautifulsoup4, pytest, pylint, pydeps)

### Database Configuration

All modules connect via `DB_CONFIG` from `query_data.py`, which reads connection parameters
exclusively from environment variables. Two configuration methods are supported:

**Option 1: `DATABASE_URL` (12-factor standard)**

```bash
export DATABASE_URL="postgresql://app_user:change_me@localhost:5432/applicant_data"
```

**Option 2: Individual environment variables**

```bash
export DB_NAME="applicant_data"
export DB_USER="app_user"
export DB_HOST="localhost"
export DB_PORT="5432"
export DB_PASSWORD="change_me"
```

`DATABASE_URL` takes precedence when both are set. A warning is logged if no database
environment variables are configured, and database connections will fail at runtime.
No connection parameters are hardcoded in the source code. See `.env.example` for a
template with all supported variables.

### Least-Privilege Database User

The app connects as `app_user`, a restricted database user with only the permissions
the application needs at runtime:

| Permission | Table / Object | Used by |
|------------|---------------|---------|
| `SELECT` | `applicants` | `query_data.run_queries()`, `cleanup_data.fix_uc_universities()` |
| `INSERT` | `applicants` | `app.insert_row()` |
| `UPDATE` | `applicants` | `cleanup_data.fix_gre_aw()`, `cleanup_data.fix_uc_universities()` |
| `USAGE, SELECT` | `applicants_p_id_seq` | SERIAL auto-increment on INSERT |

Permissions **not** granted: `DELETE`, `TRUNCATE`, `DROP`, `ALTER`, `CREATE`.

To create `app_user`, run the setup script as a superuser **after** `load_data.py` has
created the database and table:

```bash
# 1. Initial setup (run once as superuser)
export DATABASE_URL="postgresql://postgres@localhost:5432/applicant_data"
python3 src/load_data.py

# 2. Create the least-privilege user
psql -U postgres -d applicant_data -f src/create_app_user.sql

# 3. Switch to app_user for runtime
export DATABASE_URL="postgresql://app_user:change_me@localhost:5432/applicant_data"
python3 src/app.py
```

### Running

```bash
python3 src/app.py
```

Visit `http://localhost:8080` in a browser.

### Routes

| Route        | Method | Description                                              |
|--------------|--------|----------------------------------------------------------|
| `/`          | GET    | Renders the dashboard with all 13 analysis queries       |
| `/pull-data` | POST   | Scrapes new entries from thegradcafe.com and runs cleanup |

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
entries (stops when a page has all duplicates). This ensures no gaps in data. After inserting, data cleanup
automatically runs to fix invalid GRE AW scores and normalize UC campus names.

- **Update Analysis** (top right) — Refreshes the page to re-run all queries against the current database. Disabled
while a Pull Data request is in progress.

## query_data.py

Shared analysis queries used by both the Flask dashboard and CLI. Exports `DB_CONFIG` for database connection
parameters and `run_queries()` which returns all analysis results as a dictionary.

```bash
python3 src/query_data.py  # Run standalone to print results to console
```

## LLM Standardization — Removed

The project previously included an LLM-based standardization module (`llm_standardizer.py`) that
used TinyLlama (via `llama-cpp-python` and `huggingface-hub`) to parse and normalize
program/university strings during pull-data. This module was removed for the following reasons:

1. **Security vulnerability (CVE-2025-69872)** — `llama-cpp-python` pulls in `diskcache` as a
   transitive dependency, which has a high-severity deserialization vulnerability with no patched
   version available. Removing the dependency eliminates the vulnerability at its source rather
   than relying on a `.snyk` policy ignore.

2. **Minimal runtime impact** — The `llm_generated_program` and `llm_generated_university` database
   columns remain intact. All 49,962 existing rows retain their pre-computed LLM values (loaded
   via `load_data.py` from `llm_extended_applicant_data.json`). Only newly pulled rows receive
   empty strings in those columns, which is the same behavior the previous code produced when the
   LLM failed.

3. **Reduced complexity** — Removing the LLM dependency eliminates a ~1 GB model download,
   simplifies the test harness (no more `llama_cpp`/`huggingface_hub` module stubs in
   `conftest.py`), and removes the need to mock `llm_standardize` across every test file.

The UC campus normalization patterns formerly defined in `llm_standardizer.py` have been moved
directly into `cleanup_data.py`, which is the only module that uses them.

## cleanup_data.py

Data quality cleanup script that fixes:

1. **Invalid GRE AW scores** — Sets values > 6 to NULL (GRE AW is scored 0-6; 146 rows had incorrect values)
2. **UC campus normalization** — Re-normalizes generic "University of California" entries to specific campuses
   (e.g., UCLA, Berkeley, San Diego) by extracting campus info from the original program field (532 rows updated)

**Note:** These cleanup functions are now automatically called after Pull Data inserts new entries. The standalone
script can still be run manually for one-time bulk cleanup:

```bash
python3 src/cleanup_data.py
```

## scrape.py

GradCafe web scraper that extracts applicant data from thegradcafe.com/survey. Respects robots.txt via
`robots_checker.py`. Used by `app.py` for the Pull Data feature.

### Project Structure

```
module_5/
├── .env.example                            # Environment variable template (not committed)
├── README.md
├── requirements.txt
├── pytest.ini                              # pytest configuration (markers, coverage)
├── setup.cfg                               # Coverage exclusions (__main__ guards)
├── tests/
│   ├── conftest.py                         # Shared fixtures (client, db_conn)
│   ├── test_flask_page.py                  # Page rendering tests
│   ├── test_buttons.py                     # Button behavior tests
│   ├── test_analysis_format.py             # Analysis output formatting tests
│   ├── test_db_insert.py                   # DB insert, query, and cleanup tests
│   ├── test_integration_end_to_end.py      # End-to-end integration tests
│   ├── test_scrape.py                      # Scraper unit tests
│   ├── test_cleanup.py                     # Cleanup function tests
│   ├── test_cleanup_main.py                # cleanup_data.main() tests
│   ├── test_robots_checker.py              # robots_checker tests
│   ├── test_query_main.py                  # query_data.main() tests
│   ├── test_load_main.py                   # load_data.main() tests
│   └── test_app_errors.py                  # App error handling tests
├── src/
│   ├── app.py                              # Flask application
│   ├── query_data.py                       # Analysis queries (shared by app.py and CLI)
│   ├── load_data.py                        # Initial database loader (JSON → PostgreSQL)
│   ├── cleanup_data.py                     # Data quality cleanup (GRE AW, UC campuses)
│   ├── canon_programs.txt                  # Canonical program names (290 entries)
│   ├── canon_universities.txt              # Canonical university names (1000+ entries)
│   ├── scrape.py                           # GradCafe web scraper
│   ├── robots_checker.py                   # robots.txt compliance checker
│   ├── create_app_user.sql                 # Least-privilege DB user setup script
│   ├── llm_extended_applicant_data.json    # Initial dataset from module_2
│   └── website/
│       ├── _templates/
│       │   └── index.html                  # Jinja2 Q&A dashboard template
│       └── _static/
│           ├── style.css                   # Dashboard styles
│           └── dashboard.js                # Pull Data / Update Analysis logic
```

## Testing

The `tests/` directory contains 150 pytest tests across twelve files with markers for selective execution.

| File | Tests | Marker | What it covers |
|------|-------|--------|----------------|
| `test_flask_page.py` | 19 | `web` | App setup, page loads, 13 Q&A blocks, buttons, tables, ordered lists |
| `test_buttons.py` | 13 | `buttons` | POST `/pull-data` JSON response, onclick wiring, JS inclusion, isPulling guard |
| `test_analysis_format.py` | 9 | `analysis` | Question labels, answer rendering, percentage formats, all scalar values rendered |
| `test_db_insert.py` | 29 | `db` | `clean_text`, `parse_float`, `parse_date`, `insert_row`, duplicate handling, column values, GRE AW cleanup, `run_queries` keys |
| `test_integration_end_to_end.py` | 3 | `integration` | Full pipeline: pull data, insert, render dashboard; duplicate pull uniqueness; update analysis reload |
| `test_scrape.py` | 34 | `web` | `parse_main_row`, `parse_detail_row`, `parse_survey`, `get_max_pages`, `fetch_page`, `scrape_data`, `main`; edge cases for absolute URLs, empty cells, pipe-separated comments, multi-page fetching |
| `test_cleanup.py` | 9 | `db` | `normalize_uc` (pure), `fix_gre_aw` and `fix_uc_universities` (DB integration) |
| `test_cleanup_main.py` | 2 | `db` | `cleanup_data.main()` happy path and DB connection error |
| `test_robots_checker.py` | 5 | `web` | `RobotsChecker` init, exception handling, `can_fetch`, `get_crawl_delay` |
| `test_query_main.py` | 6 | `db` | `query_data.main()` output, DB error, `DATABASE_URL` config parsing, individual env var config, missing env vars, dependency-injected scraper test |
| `test_load_main.py` | 10 | `db` | `create_connection` success/failure, `main()` DB creation, JSON loading, error paths (missing file, bad JSON, executemany failure) |
| `test_app_errors.py` | 11 | `buttons` | Index DB error, invalid `max_pages`, DB connect failure, network error, DB error during scrape, caught-up break, cleanup message, multi-page, network error page 2 rollback, cleanup error, insert error rollback |

### Running Tests

Set `DATABASE_URL` before running tests so DB tests can connect:

```bash
export DATABASE_URL="postgresql://myuser@localhost:5432/applicant_data"
python3 -m pytest tests/ -v
python3 -m pytest tests/ -v --cov=src --cov-report=term-missing   # with coverage
python3 -m pytest tests/ -m web -v                                    # by marker
```

Non-DB tests (`web`, `buttons`, `analysis`) run without `DATABASE_URL`.
DB and integration tests require a running PostgreSQL instance and skip automatically if unavailable.

### Coverage

Coverage is configured in `pytest.ini` and `setup.cfg`. The suite enforces **100% statement coverage**
(`--cov-fail-under=100`). Untestable lines (`if __name__ == "__main__"` guards) are excluded.

| File | Coverage |
|------|----------|
| `app.py` | 100% |
| `cleanup_data.py` | 100% |
| `robots_checker.py` | 100% |
| `load_data.py` | 100% |
| `query_data.py` | 100% |
| `scrape.py` | 100% |
| **TOTAL** | **100%** |

Scraper functions (`fetch_page`, `parse_survey`, `get_max_pages`) and cleanup functions
(`fix_gre_aw`, `fix_uc_universities`) run for real — network I/O is intercepted at the
transport level by patching `scrape.urlopen` with a `FakeResponse` stub.

## Code Quality

### Pylint

All Python files (source and tests) score **10.00/10** with pylint. From `module_5/`:

```bash
PYTHONPATH=src pylint src/*.py tests/*.py
```

Output:

```
--------------------------------------------------------------------
Your code has been rated at 10.00/10
```

### Snyk Vulnerability Scan

`snyk test` passes clean with no known vulnerabilities. The previous high-severity
`diskcache` vulnerability (CVE-2025-69872) was eliminated by removing the `llama-cpp-python`
dependency entirely (see [LLM Standardization — Removed](#llm-standardization--removed)).

### Practices

All Python files follow these practices:

- **Type hints** — Function signatures include type annotations
- **Logging** — Uses Python `logging` module with lazy `%` formatting (not f-strings)
- **Specific exceptions** — Catches specific exception types (e.g., `OperationalError`, `JSONDecodeError`)
- **Input validation** — Validates user inputs (e.g., `max_pages` clamped to 1-500)
- **No duplicate code** — Shared constants imported from single source (e.g., `DB_CONFIG`)
- **SQL injection protection** — All queries use parameterized statements (`%s` placeholders with parameter tuples); dynamic identifiers use `psycopg.sql.Identifier()`; SQL construction is separated from execution

# References

* https://realpython.com/python-sql-libraries/
* https://medium.com/dataexplorations/sqlalchemy-orm-a-more-pythonic-way-of-interacting-with-your-database-935b57fd2d4d
* https://flask.palletsprojects.com/
* https://www.psycopg.org/psycopg3/docs/
* https://realpython.com/pytest-python-testing/