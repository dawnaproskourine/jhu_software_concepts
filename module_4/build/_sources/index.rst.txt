.. module_4 documentation master file, created by
   sphinx-quickstart on Sun Feb  8 21:09:18 2026.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Module 4: Testing and Documentation
====================================

.. contents::
   :local:
   :depth: 2

Overview
--------

A single-page Flask web application that displays analysis results from a
PostgreSQL database of grad school applicant data scraped from thegradcafe.com.
The dashboard renders 13 Q&A-style analysis queries covering applicant counts,
GPA/GRE averages, acceptance rates, and top programs/universities.

New data is pulled from thegradcafe.com via the **Pull Data** button, which
scrapes survey pages, standardizes program and university names using a local
TinyLlama LLM, and inserts rows into PostgreSQL. The **Update Analysis** button
reloads the page to re-run all queries against the current database.

Architecture
------------

The application is organized into three layers: **Web**, **ETL**, and **DB**.

Web Layer
~~~~~~~~~

The web layer is a Flask application (``app.py``) that serves a single-page
dashboard. The ``create_app()`` factory accepts optional ``fetch_page_fn``,
``parse_survey_fn``, and ``get_max_pages_fn`` callables for dependency
injection, allowing tests to supply fake scrapers without monkeypatching
the ``scrape`` module. It handles two routes:

- **GET /** renders the dashboard by calling ``run_queries()`` against
  PostgreSQL and passing the results to a Jinja2 template
  (``website/_templates/index.html``).
- **POST /pull-data** triggers the ETL pipeline and returns a JSON summary
  of pages fetched, rows scraped, and rows inserted.

Client-side behavior is handled by ``website/_static/dashboard.js``, which
wires the Pull Data and Update Analysis buttons, manages the ``isPulling``
guard to prevent concurrent operations, and reloads the page after analysis
updates.

ETL Layer
~~~~~~~~~

The ETL (Extract, Transform, Load) layer handles data ingestion:

- **Extract** -- ``scrape.py`` fetches HTML pages from thegradcafe.com/survey
  and parses applicant rows from the survey tables. ``robots_checker.py``
  enforces robots.txt compliance before fetching.
- **Transform** -- ``llm_standardizer.py`` sends raw program/university
  strings through a local TinyLlama LLM (via llama_cpp) with few-shot
  prompting to produce standardized names. It falls back to rule-based
  parsing if the LLM returns invalid output, and applies fuzzy matching
  against canonical name lists (290 programs, 1000+ universities).
- **Load** -- ``app.insert_row()`` parses dates, runs LLM standardization,
  and inserts into the ``applicants`` table using ``ON CONFLICT (url) DO
  NOTHING`` to skip duplicates. ``cleanup_data.py`` runs post-insert fixes
  for invalid GRE AW scores (values > 6 set to NULL) and UC campus
  normalization.

The initial dataset is loaded by ``load_data.py``, which reads from
``llm_extended_applicant_data.json`` and bulk-inserts into PostgreSQL.

DB Layer
~~~~~~~~

The database layer uses PostgreSQL (via psycopg v3) with a single
``applicants`` table containing 14 columns: ``program``, ``comments``,
``date_added``, ``url`` (unique), ``status``, ``term``,
``us_or_international``, ``gpa``, ``gre``, ``gre_v``, ``gre_aw``,
``degree``, ``llm_generated_program``, and ``llm_generated_university``.

``query_data.py`` defines ``DB_CONFIG`` (shared by all modules) and
``run_queries()``, which executes 13 parameterized SQL queries and returns
results as a dictionary. ``DB_CONFIG`` is built by ``_build_db_config()``,
which parses the ``DATABASE_URL`` environment variable (standard 12-factor
pattern, e.g. ``postgresql://user:pass@host:5432/dbname``). A
warning is logged if the variable is not set. Queries include
counts, averages, percentages, top-N rankings, and acceptance rates grouped
by degree type and nationality. All queries use parameterized statements for
SQL injection protection.

Setup
-----

Prerequisites
~~~~~~~~~~~~~

- Python 3.10+
- PostgreSQL running locally with the ``applicant_data`` database created
- Required Python packages (install from ``module_4/``):

.. code-block:: bash

   pip install -r requirements.txt

Database Configuration
~~~~~~~~~~~~~~~~~~~~~~

All modules connect via the ``DB_CONFIG`` dictionary exported by
``query_data.py``. It is built at import time by ``_build_db_config()``,
which reads the ``DATABASE_URL`` environment variable (standard 12-factor
pattern). The variable **must** be set before running the app or tests:

.. code-block:: bash

   export DATABASE_URL="postgresql://myuser:secret@localhost:5432/applicant_data"

The URL is parsed into component keys (``dbname``, ``user``, ``host``,
``port``, ``password``) so all downstream code works unchanged.
A warning is logged if ``DATABASE_URL`` is not set, and database
connections will fail at runtime.

To populate the database with the initial dataset:

.. code-block:: bash

   python3 source/load_data.py

Running the App
~~~~~~~~~~~~~~~

From the ``module_4/`` directory:

.. code-block:: bash

   python3 source/app.py

Visit ``http://localhost:8080`` in a browser.

Routes
~~~~~~

================  ======  =============================================================
Route             Method  Description
================  ======  =============================================================
``/``             GET     Renders the dashboard with all 13 analysis queries
``/pull-data``    POST    Scrapes new entries from thegradcafe.com, processes with LLM,
                          and runs cleanup
================  ======  =============================================================

Running Tests
-------------

The ``tests/`` directory contains a pytest suite organized into thirteen files
with pytest markers for selective execution.

Running All Tests
~~~~~~~~~~~~~~~~~

From ``module_4/``:

.. code-block:: bash

   python3 -m pytest tests/ -v

Running with Coverage
~~~~~~~~~~~~~~~~~~~~~

Coverage is configured in ``pytest.ini`` (via ``--cov=source
--cov-config=.coveragerc --cov-fail-under=100``) and ``.coveragerc``, which
omits ``conf.py`` and excludes ``if __name__ == "__main__"`` guard lines.
The suite enforces **100 % statement coverage**.

.. code-block:: bash

   python3 -m pytest tests/ -v --cov=source --cov-report=term-missing

Running by Marker
~~~~~~~~~~~~~~~~~

Each test is marked with one or more of the following markers (registered in
``pytest.ini``):

===============  =================================================================
Marker           Description
===============  =================================================================
``web``          Page rendering and Flask app setup tests
``buttons``      Button behavior and POST ``/pull-data`` tests
``analysis``     Analysis output formatting tests
``db``           Database insert, query, and cleanup tests
``integration``  End-to-end integration tests
===============  =================================================================

Run a specific marker:

.. code-block:: bash

   python3 -m pytest tests/ -m web -v
   python3 -m pytest tests/ -m db -v
   python3 -m pytest tests/ -m integration -v

Test Files
~~~~~~~~~~

====================================  =====  =============================================
File                                  Tests  What it covers
====================================  =====  =============================================
``test_flask_page.py``                19     App setup, page loads, 13 Q&A blocks, buttons,
                                             tables, ordered lists
``test_buttons.py``                   11     POST ``/pull-data`` JSON response, onclick
                                             wiring, JS inclusion, isPulling guard
``test_analysis_format.py``           9      Question labels, answer rendering, percentage
                                             formats, all scalar values rendered
``test_db_insert.py``                 30     ``clean_text``, ``parse_float``,
                                             ``parse_date``, ``insert_row``, duplicate
                                             handling, column values, GRE AW cleanup,
                                             ``run_queries`` keys
``test_integration_end_to_end.py``    2      Full pipeline: pull data, insert, render
                                             dashboard; duplicate pull uniqueness
``test_scrape.py``                    34     ``parse_main_row``, ``parse_detail_row``,
                                             ``parse_survey``, ``get_max_pages``,
                                             ``fetch_page``, ``scrape_data``, ``main``;
                                             edge cases for absolute URLs, empty cells,
                                             pipe-separated comments, multi-page fetching
``test_cleanup.py``                   8      ``normalize_uc`` (pure), ``fix_gre_aw`` and
                                             ``fix_uc_universities`` (DB integration)
``test_cleanup_main.py``              2      ``cleanup_data.main()`` happy path and DB
                                             connection error
``test_robots_checker.py``            5      ``RobotsChecker`` init, exception handling,
                                             ``can_fetch``, ``get_crawl_delay``
``test_llm_standardizer.py``          25     ``_read_lines``, ``_split_fallback``,
                                             ``_best_match``, ``_post_normalize_program``,
                                             ``_post_normalize_university``, ``_load_llm``
                                             singleton, ``standardize`` with mocked LLM
``test_query_main.py``                5      ``query_data.main()`` output, DB error,
                                             ``DATABASE_URL`` config parsing,
                                             missing ``DATABASE_URL`` error,
                                             dependency-injected scraper test
``test_load_main.py``                 10     ``create_connection`` success/failure,
                                             ``main()`` DB creation, JSON loading, and
                                             error paths (missing file, bad JSON,
                                             executemany failure)
``test_app_errors.py``                12     Index DB error, ``insert_row`` LLM exception,
                                             invalid ``max_pages``, DB connect failure,
                                             network error, DB error during scrape,
                                             caught-up break, cleanup message, multi-page,
                                             network error page 2 rollback, cleanup error,
                                             insert error rollback
====================================  =====  =============================================

Database tests require a running PostgreSQL instance and skip automatically if
unavailable.

Expected HTML Selectors
~~~~~~~~~~~~~~~~~~~~~~~

Tests use BeautifulSoup to assert on the following HTML structure rendered by
the Jinja2 template:

==========================  =================================================
Selector                    Expected content
==========================  =================================================
``div.qa``                  13 Q&A blocks, one per analysis query
``div.question``            Non-empty question label inside each Q&A block
``div.answer``              Non-empty rendered answer inside each Q&A block
``#pull-btn``               Pull Data button with ``onclick="pullData()"``
``#update-btn``             Update Analysis button with
                            ``onclick="updateAnalysis()"``
``ol > li``                 Ordered lists with 10 items for top programs
                            (Q10) and top universities (Q11)
==========================  =================================================

Fixtures
~~~~~~~~

Two shared fixtures are defined in ``conftest.py``:

**client**
   A Flask test client with ``app.run_queries`` and ``app.psycopg.connect``
   patched via ``monkeypatch``. ``run_queries`` returns ``MOCK_QUERY_DATA``,
   a dictionary of deterministic ``Decimal`` values matching what psycopg
   returns from ``ROUND()`` queries. ``psycopg.connect`` returns a lightweight
   ``_FakeConn`` stub so no real database is needed. Used by the ``web``,
   ``buttons``, and ``analysis`` marked tests.

**db_conn**
   A real PostgreSQL connection with ``autocommit=False``. Issues a
   ``SAVEPOINT`` before the test and ``ROLLBACK TO SAVEPOINT`` on teardown,
   so tests leave no trace in the database. Yields ``(conn, cur)``. Calls
   ``pytest.skip()`` automatically if PostgreSQL is unavailable. Used by
   ``db`` and ``integration`` marked tests.

Test Doubles
~~~~~~~~~~~~

Tests avoid loading the 668 MB TinyLlama model, making network requests,
and requiring a live database (for non-DB tests) by using ``monkeypatch``
with lightweight stub classes instead of ``unittest.mock``.

Only ``llm_standardize`` (the LLM call) is mocked in all test suites.
Scraper functions (``fetch_page``, ``parse_survey``, ``get_max_pages``)
and cleanup functions (``fix_gre_aw``, ``fix_uc_universities``) run for
real — network I/O is intercepted at the transport level by patching
``scrape.urlopen`` with a ``_FakeResponse`` stub.

.. list-table::
   :header-rows: 1
   :widths: 25 30 45

   * - What is patched
     - Patch target
     - Replacement
   * - LLM standardization
     - ``app.llm_standardize``
     - Lambda returning a dict with ``standardized_program`` and
       ``standardized_university``
   * - Database connection
     - ``app.psycopg.connect``
     - ``_FakeConn`` (context manager stub) or ``_TestConn`` (direct usage
       wrapper)
   * - Network I/O (transport)
     - ``scrape.urlopen``
     - ``_FakeResponse`` stub returning crafted HTML
   * - Analysis queries
     - ``app.run_queries``
     - Lambda returning ``MOCK_QUERY_DATA``
   * - Robots.txt checker
     - ``scrape.robots_checker``
     - Fake module namespace with inner ``RobotsChecker`` class and
       ``DEFAULT_USER_AGENT``
   * - LLM model loading
     - ``llm._load_llm``
     - Lambda returning a ``FakeLLM`` with ``create_chat_completion``
   * - Robot parser I/O
     - ``robotparser.read()``
     - Monkeypatched to no-op or raise for exception tests

**No longer mocked** in integration and DB tests — these run for real:

- ``scrape.fetch_page`` — builds ``Request``, calls ``urlopen``, decodes
- ``scrape.parse_survey`` — parses HTML with BeautifulSoup
- ``scrape.get_max_pages`` — extracts pagination from HTML
- ``cleanup_data.fix_gre_aw`` — runs against SAVEPOINT-protected DB
- ``cleanup_data.fix_uc_universities`` — runs against SAVEPOINT-protected DB

Button behavior tests (``test_buttons.py``) still mock at the function level
because they verify JSON response structure and button wiring, not scraping
logic.

Integration tests (``test_db_insert.py`` and ``test_integration_end_to_end.py``)
use a ``_NoCloseConn`` / ``_TestConn`` wrapper that routes the app's
``psycopg.connect`` calls through the test's SAVEPOINT-protected connection,
suppressing ``close()`` and ``autocommit`` changes so the rollback stays intact.

API Reference
-------------

app
~~~~~
.. automodule:: app
   :members:

load_data
~~~~~~~~~~
.. automodule:: load_data
   :members:

query_data
~~~~~~~~~~~
.. automodule:: query_data
   :members:

cleanup_data
~~~~~~~~~~~~~
.. automodule:: cleanup_data
   :members:

scrape
~~~~~~~
.. automodule:: scrape
   :members:

robots_checker
~~~~~~~~~~~~~~~~
.. automodule:: robots_checker
   :members:

llm_standardizer
~~~~~~~~~~~~~~~~~~
.. automodule:: llm_standardizer
   :members:

.. toctree::
   :maxdepth: 2

   operations
