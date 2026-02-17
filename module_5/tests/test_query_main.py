"""Tests for query_data.main() — console output."""
# pylint: disable=C0116,R0903,W0613,C0415,E1101,R0801,W0212

import pytest

from conftest import MOCK_QUERY_DATA
import query_data

pytestmark = pytest.mark.db


def test_main_prints_results(monkeypatch, capsys):
    class _FakeConn:
        autocommit = True
        def close(self):
            pass

    monkeypatch.setattr(
        query_data.psycopg, "connect", lambda **kw: _FakeConn()
    )
    monkeypatch.setattr(query_data, "run_queries", lambda conn: MOCK_QUERY_DATA)

    query_data.main()
    out = capsys.readouterr().out

    assert "Total applicants:" in out
    assert "Fall 2026 applicants:" in out
    assert "International student percentage:" in out
    assert "Average GPA:" in out
    assert "Top 10 most popular programs:" in out
    assert "Top 10 most popular universities:" in out
    assert "Acceptance rate by degree type:" in out
    assert "Acceptance rate by nationality:" in out


def test_main_db_error(monkeypatch):
    monkeypatch.setattr(
        query_data.psycopg, "connect",
        lambda **kw: (_ for _ in ()).throw(query_data.OperationalError("fail")),
    )
    # Should return without crashing
    query_data.main()


@pytest.mark.buttons
def test_pull_data_with_injected_scrapers(monkeypatch):
    """Dependency-injected scrapers bypass the network without monkeypatching scrape."""
    import app as app_module
    from conftest import FakePullConn

    monkeypatch.setattr(app_module, "llm_standardize", lambda _x: {})
    monkeypatch.setattr(app_module, "fix_gre_aw", lambda _c: 0)
    monkeypatch.setattr(app_module, "fix_uc_universities", lambda _c: 0)
    monkeypatch.setattr(app_module.psycopg, "connect", lambda **kw: FakePullConn())

    fake_html = "<html><body><table><tbody></tbody></table></body></html>"
    test_app = app_module.create_app(
        testing=True,
        fetch_page_fn=lambda url: fake_html,
        parse_survey_fn=lambda html: [],
        get_max_pages_fn=lambda html: 1,
    )

    with test_app.test_client() as c:
        resp = c.post("/pull-data", json={"max_pages": 1})
    assert resp.status_code == 200
    assert "Already up to date" in resp.get_json()["message"]


def test_build_db_config_uses_database_url(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://myuser:secret@myhost:5433/mydb")
    config = query_data._build_db_config()
    assert config == {
        "dbname": "mydb",
        "user": "myuser",
        "host": "myhost",
        "port": 5433,
        "password": "secret",
    }


def test_build_db_config_missing_url_returns_empty(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("DB_NAME", raising=False)
    monkeypatch.delenv("DB_USER", raising=False)
    assert not query_data._build_db_config()


def test_build_db_config_individual_env_vars(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("DB_NAME", "testdb")
    monkeypatch.setenv("DB_USER", "testuser")
    monkeypatch.setenv("DB_HOST", "dbhost")
    monkeypatch.setenv("DB_PORT", "5433")
    monkeypatch.setenv("DB_PASSWORD", "secret")
    config = query_data._build_db_config()
    assert config == {
        "dbname": "testdb",
        "user": "testuser",
        "host": "dbhost",
        "port": 5433,
        "password": "secret",
    }
