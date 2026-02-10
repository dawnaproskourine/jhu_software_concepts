.. module_4 documentation master file, created by
   sphinx-quickstart on Sun Feb  8 21:09:18 2026.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Module 4: Testing and Documentation
====================================

.. toctree::
   :maxdepth: 2
   :caption: Contents:

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
dashboard. It handles two routes:

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
  and parses applicant rows from the survey tables. ``RobotsChecker.py``
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
results as a dictionary. Queries include counts, averages, percentages,
top-N rankings, and acceptance rates grouped by degree type and nationality.
All queries use parameterized statements for SQL injection protection.

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

The database connection is configured in ``query_data.py`` via the ``DB_CONFIG``
dictionary:

.. code-block:: python

   DB_CONFIG = {
       "dbname": "applicant_data",
       "user": "dawnaproskourine",
       "host": "127.0.0.1",
   }

Update ``user`` to match your local PostgreSQL user. All modules import
``DB_CONFIG`` from ``query_data.py``.

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

=============  ======  ================================================================
Route          Method  Description
=============  ======  ================================================================
``/``          GET     Renders the dashboard with all 13 analysis queries
``/pull-data`` POST    Scrapes new entries from thegradcafe.com, processes with LLM,
                       and runs cleanup
=============  ======  ================================================================

Running Tests
-------------

The ``tests/`` directory contains a pytest suite organized into five files with
pytest markers for selective execution.

Running All Tests
~~~~~~~~~~~~~~~~~

From ``module_4/``:

.. code-block:: bash

   python3 -m pytest tests/ -v

Running with Coverage
~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   python3 -m pytest tests/ -v --cov=source --cov-report=term-missing

Running by Marker
~~~~~~~~~~~~~~~~~

Each test is marked with one or more of the following markers (registered in
``pytest.ini``):

=============  ===================================================================
Marker         Description
=============  ===================================================================
``web``        Page rendering and Flask app setup tests
``buttons``    Button behavior and POST ``/pull-data`` tests
``analysis``   Analysis output formatting tests
``db``         Database insert, query, and cleanup tests
``integration`` End-to-end integration tests
=============  ===================================================================

Run a specific marker:

.. code-block:: bash

   python3 -m pytest tests/ -m web -v
   python3 -m pytest tests/ -m db -v
   python3 -m pytest tests/ -m integration -v

Test Files
~~~~~~~~~~

================================  =====  =============================================
File                              Tests  What it covers
================================  =====  =============================================
``test_flask_page.py``            19     App setup, page loads, 13 Q&A blocks, buttons,
                                         tables, ordered lists
``test_buttons.py``               11     POST ``/pull-data`` JSON response, onclick
                                         wiring, JS inclusion, isPulling guard
``test_analysis_format.py``       9      Question labels, answer rendering, percentage
                                         formats, all scalar values rendered
``test_db_insert.py``             25     ``clean_text``, ``parse_float``,
                                         ``insert_row``, duplicate handling, column
                                         values, GRE AW cleanup, ``run_queries`` keys
``test_integration_end_to_end.py`` 2     Full pipeline: pull data, insert, render
                                         dashboard; duplicate pull uniqueness
================================  =====  =============================================

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
with lightweight stub classes instead of ``unittest.mock``:

============================  =========================  ============================
What is patched               Patch target               Replacement
============================  =========================  ============================
LLM standardization           ``app.llm_standardize``    Lambda returning a dict with
                                                         ``standardized_program`` and
                                                         ``standardized_university``
Database connection            ``app.psycopg.connect``    ``_FakeConn`` (context
                                                         manager stub) or
                                                         ``_FakePullConn`` (direct
                                                         usage stub)
Scraper fetch                  ``scrape.fetch_page``      Lambda returning fake HTML
Scraper parse                  ``scrape.parse_survey``    Lambda returning a list of
                                                         row dicts (or empty list)
Scraper pagination             ``scrape.get_max_pages``   Lambda returning ``1``
Analysis queries               ``app.run_queries``        Lambda returning
                                                         ``MOCK_QUERY_DATA``
GRE AW cleanup                 ``app.fix_gre_aw``         Lambda returning ``0``
UC campus cleanup              ``app.fix_uc_universities`` Lambda returning ``0``
============================  =========================  ============================

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

RobotsChecker
~~~~~~~~~~~~~~
.. automodule:: RobotsChecker
   :members:

llm_standardizer
~~~~~~~~~~~~~~~~~~
.. automodule:: llm_standardizer
   :members:
