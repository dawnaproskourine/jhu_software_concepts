Operational Notes
-----------------

This page documents runtime behaviour that is not obvious from the API
reference alone: how the application prevents concurrent writes, how
repeated requests stay safe, and what makes each row unique. A
troubleshooting section at the end covers the most common local and CI
issues.

Busy-State Policy
~~~~~~~~~~~~~~~~~

The Pull Data operation can take several seconds (one HTTP request per
survey page, each separated by a 0.5 s delay). Two mechanisms prevent
overlapping operations from corrupting data or confusing the user.

Client-Side Guard
^^^^^^^^^^^^^^^^^

``dashboard.js`` maintains a module-level ``isPulling`` flag:

1. ``pullData()`` sets ``isPulling = true``, disables both the **Pull
   Data** and **Update Analysis** buttons, and starts the ``POST
   /pull-data`` request.
2. While ``isPulling`` is true, ``updateAnalysis()`` shows a warning
   ("A Pull Data request is still running") and returns without
   reloading the page.
3. When the fetch promise settles (success, server error, or network
   error), the handler resets ``isPulling = false`` and re-enables both
   buttons.

This prevents a page reload from interrupting an in-flight scrape and
stops double-clicks from launching concurrent pulls.

Server-Side Transaction
^^^^^^^^^^^^^^^^^^^^^^^

``pull_data()`` opens a single psycopg connection in **transaction mode**
(the psycopg v3 default -- ``autocommit`` is *not* enabled). All
``INSERT`` statements and cleanup ``UPDATE`` statements run inside one
transaction:

- On success, ``conn.commit()`` makes all changes visible atomically.
- On any error (network, database, or cleanup), ``conn.rollback()``
  discards every uncommitted change before returning a 500 response.

Because Flask's development server is single-threaded by default, two
simultaneous ``/pull-data`` requests are serialized at the WSGI level.
In a multi-worker deployment, PostgreSQL's row-level locking and the
``ON CONFLICT`` clause prevent duplicate inserts even if two workers
scrape the same page concurrently.

Idempotency Strategy
~~~~~~~~~~~~~~~~~~~~

Pressing **Pull Data** multiple times (or resuming after a partial
failure) never creates duplicate rows and never leaves the database in an
inconsistent state.

Insert Idempotency
^^^^^^^^^^^^^^^^^^

Every ``INSERT`` in ``app.insert_row()`` uses:

.. code-block:: sql

   INSERT INTO applicants (...) VALUES (...)
   ON CONFLICT (url) DO NOTHING

If a row with the same ``url`` already exists, PostgreSQL silently skips
the insert and ``cur.rowcount`` returns 0. The caller uses this to
distinguish new rows from duplicates.

Caught-Up Detection
^^^^^^^^^^^^^^^^^^^

After processing each page, ``pull_data()`` checks
``page_inserted == 0``. If an entire page consists of duplicates, the
scraper concludes it has caught up with existing data and breaks out of
the loop. This makes repeated pulls cheap: the first page is fetched,
all rows are duplicates, and the function returns immediately with an
"Already up to date" message.

Cleanup Idempotency
^^^^^^^^^^^^^^^^^^^

The two post-insert cleanup functions are also safe to re-run:

- ``fix_gre_aw(conn)`` sets ``gre_aw = NULL WHERE gre_aw > 6``. Running
  it twice is a no-op because the first run already nullified the invalid
  values.
- ``fix_uc_universities(conn)`` only updates a row when the resolved
  campus name differs from the current value (``new_uni != current_uni``).
  A second run finds no differences and updates zero rows.

Transaction Rollback
^^^^^^^^^^^^^^^^^^^^

If a network or database error occurs partway through a scrape, the
entire transaction is rolled back. No partial set of rows is committed.
The next Pull Data request starts from a clean state and re-scrapes the
same pages, relying on ``ON CONFLICT`` to skip any rows that may have
been committed in a previous successful run.

Uniqueness Keys
~~~~~~~~~~~~~~~

The ``applicants`` table enforces uniqueness at two levels:

.. list-table::
   :header-rows: 1
   :widths: 20 20 60

   * - Column
     - Constraint
     - Purpose
   * - ``p_id``
     - ``SERIAL PRIMARY KEY``
     - Auto-incrementing surrogate key. Used internally for joins and
       updates (e.g., ``fix_uc_universities`` updates by ``p_id``).
   * - ``url``
     - ``UNIQUE``
     - Natural key derived from the GradCafe result page URL
       (e.g., ``https://www.thegradcafe.com/result/12345``). This is the
       column referenced by ``ON CONFLICT (url) DO NOTHING``.

The ``url`` column is the deduplication key for both ``app.insert_row()``
(live scraping) and ``load_data.main()`` (initial bulk load). As long as
GradCafe assigns a distinct URL to each survey submission, no two rows
can represent the same applicant entry.

``load_data.main()`` uses ``cursor.executemany()`` with the same
``ON CONFLICT (url) DO NOTHING`` clause, so re-running the initial load
is also idempotent.

Troubleshooting
~~~~~~~~~~~~~~~

Local Development
^^^^^^^^^^^^^^^^^

**PostgreSQL not running or database missing**

.. code-block:: text

   psycopg.OperationalError: connection to server ... failed

Ensure PostgreSQL is running and the ``applicant_data`` database exists.
Create it manually if needed:

.. code-block:: bash

   createdb applicant_data

Or run the initial loader, which creates the database automatically:

.. code-block:: bash

   python3 source/load_data.py

**DB tests skipped locally**

Tests marked ``db`` or ``integration`` call ``psycopg.connect()`` in the
``db_conn`` fixture. If the connection fails, the fixture calls
``pytest.skip("PostgreSQL not available")``. This is expected when
running tests without a local PostgreSQL instance -- the non-DB tests
(``web``, ``buttons``, ``analysis``) still run and pass.

**DATABASE_URL not set**

``query_data._build_db_config()`` requires the ``DATABASE_URL``
environment variable. If it is missing, a warning is logged and
``DB_CONFIG`` is set to an empty dict. Any subsequent
``psycopg.connect(**DB_CONFIG)`` call will fail with
``OperationalError``. Set it before running the app or tests:

.. code-block:: bash

   export DATABASE_URL="postgresql://myuser@localhost:5432/applicant_data"

**Coverage below 100 %**

``pytest.ini`` sets ``--cov-fail-under=100``. If you add new source code
without corresponding tests, the suite fails with:

.. code-block:: text

   FAIL Required test coverage of 100% not reached.

Add tests to cover the new lines. Check which lines are uncovered with:

.. code-block:: bash

   python3 -m pytest tests/ -v --cov=source --cov-report=term-missing

CI (GitHub Actions)
^^^^^^^^^^^^^^^^^^^

**llama_cpp / huggingface_hub ImportError**

The CI workflow installs only lightweight dependencies from
``requirements.txt`` (which excludes ``llama_cpp_python`` and
``huggingface_hub``). ``conftest.py`` injects stub modules into
``sys.modules`` when these packages are not installed. If a new import
from either package is added outside ``llm_standardizer.py``, the stub
will not cover it. Fix by either:

- Adding the new import to the stub block in ``conftest.py``, or
- Lazy-importing the package inside the function that uses it.

**PostgreSQL service container not ready**

The workflow uses a ``postgres:16`` service container with health checks.
If tests fail with connection errors, the health check interval
(``--health-interval 10s``, 5 retries) may need to be increased. The
``Create applicants table`` step runs *after* the health check passes,
so a healthy container should always have the table ready.

**Table schema mismatch**

The ``Create applicants table`` step in the workflow uses
``CREATE TABLE IF NOT EXISTS`` with a hardcoded schema. If columns are
added or renamed in ``load_data.py``, the workflow schema must be updated
to match. Symptoms: ``psycopg.errors.UndefinedColumn`` in DB tests.

**pytest.ini coverage path**

``pytest.ini`` uses ``--cov=source``, which resolves relative to
``working-directory: module_4`` set in the workflow. If the working
directory changes, coverage collection will silently report 0 % and the
``--cov-fail-under=100`` check will fail.
