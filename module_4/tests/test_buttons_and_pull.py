"""Requirement (b): button behavior and POST /pull-data tests.

Verifies JSON response from /pull-data, onclick wiring, JS inclusion,
and the isPulling guard in dashboard.js.
"""

import os


# ---------------------------------------------------------------------------
# Lightweight stubs used by pull-data tests to replace psycopg objects
# ---------------------------------------------------------------------------
class _FakeCursor:
    """Minimal stand-in for a psycopg cursor inside pull_data()."""
    rowcount = 0

    def execute(self, *args, **kwargs):
        pass


class _FakePullConn:
    """Minimal stand-in for a psycopg connection inside pull_data()."""
    autocommit = True

    def cursor(self):
        return _FakeCursor()

    def close(self):
        pass


def _patch_pull_data(monkeypatch):
    """Apply all monkeypatches needed to call POST /pull-data safely."""
    import app as app_module
    import scrape

    fake_html = "<html><body><table><tbody></tbody></table></body></html>"

    monkeypatch.setattr(app_module, "llm_standardize", lambda _x: {})
    monkeypatch.setattr(app_module, "fix_gre_aw", lambda _conn: 0)
    monkeypatch.setattr(app_module, "fix_uc_universities", lambda _conn: 0)
    monkeypatch.setattr(app_module.psycopg, "connect", lambda **kw: _FakePullConn())
    monkeypatch.setattr(scrape, "fetch_page", lambda url, *a, **kw: fake_html)
    monkeypatch.setattr(scrape, "parse_survey", lambda html: [])
    monkeypatch.setattr(scrape, "get_max_pages", lambda html: 1)


# ---- POST /pull-data ----

def test_pull_data_returns_200_json(client, monkeypatch):
    _patch_pull_data(monkeypatch)
    resp = client.post("/pull-data", json={"max_pages": 1})
    assert resp.status_code == 200
    assert resp.content_type.startswith("application/json")


def test_pull_data_expected_keys_in_response(client, monkeypatch):
    _patch_pull_data(monkeypatch)
    data = client.post("/pull-data", json={"max_pages": 1}).get_json()
    for key in ("pages_fetched", "scraped", "inserted",
                "cleaned_gre_aw", "cleaned_uc", "message"):
        assert key in data, f"Missing key: {key}"


def test_pull_data_no_new_data_message(client, monkeypatch):
    _patch_pull_data(monkeypatch)
    data = client.post("/pull-data", json={"max_pages": 1}).get_json()
    assert "Already up to date" in data["message"]


# ---- onclick wiring in HTML ----

def test_pull_btn_references_pullData(client):
    html = client.get("/").data.decode()
    assert 'onclick="pullData()"' in html


def test_update_btn_references_updateAnalysis(client):
    html = client.get("/").data.decode()
    assert 'onclick="updateAnalysis()"' in html


# ---- dashboard.js inclusion and content ----

def test_dashboard_js_script_tag(client):
    html = client.get("/").data.decode()
    assert "dashboard.js" in html


def _read_js():
    js_path = os.path.join(
        os.path.dirname(__file__), os.pardir,
        "source", "website", "_static", "dashboard.js",
    )
    with open(js_path) as f:
        return f.read()


def test_dashboard_js_contains_isPulling():
    assert "var isPulling" in _read_js()


def test_dashboard_js_isPulling_guards_updateAnalysis():
    assert "if (isPulling)" in _read_js()


def test_dashboard_js_warning_message():
    assert "A Pull Data request is still running" in _read_js()
