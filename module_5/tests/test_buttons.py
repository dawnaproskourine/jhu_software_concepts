"""Requirement (b): button behavior and POST /pull-data tests.

Verifies JSON response from /pull-data, onclick wiring, JS inclusion,
and the isPulling guard in dashboard.js.
"""
# pylint: disable=C0116,R0903,W0613,C0415,E1101,R0801,C0103

import os

import pytest

from conftest import FakePullConn, FakeInsertConn


def _patch_pull_data(monkeypatch):
    """Apply all monkeypatches needed to call POST /pull-data safely."""
    import app as app_module
    import scrape

    fake_html = "<html><body><table><tbody></tbody></table></body></html>"

    monkeypatch.setattr(app_module, "llm_standardize", lambda _x: {})
    monkeypatch.setattr(app_module, "fix_gre_aw", lambda _conn: 0)
    monkeypatch.setattr(app_module, "fix_uc_universities", lambda _conn: 0)
    monkeypatch.setattr(app_module.psycopg, "connect", lambda **kw: FakePullConn())
    monkeypatch.setattr(scrape, "fetch_page", lambda url, *a, **kw: fake_html)
    monkeypatch.setattr(scrape, "parse_survey", lambda html: [])
    monkeypatch.setattr(scrape, "get_max_pages", lambda html: 1)


# ---- POST /pull-data ----

@pytest.mark.buttons
def test_pull_data_returns_200_json(client, monkeypatch):
    _patch_pull_data(monkeypatch)
    resp = client.post("/pull-data", json={"max_pages": 1})
    assert resp.status_code == 200
    assert resp.content_type.startswith("application/json")


@pytest.mark.buttons
def test_pull_data_expected_keys_in_response(client, monkeypatch):
    _patch_pull_data(monkeypatch)
    data = client.post("/pull-data", json={"max_pages": 1}).get_json()
    for key in ("pages_fetched", "scraped", "inserted",
                "cleaned_gre_aw", "cleaned_uc", "message"):
        assert key in data, f"Missing key: {key}"


@pytest.mark.buttons
def test_pull_data_no_new_data_message(client, monkeypatch):
    _patch_pull_data(monkeypatch)
    data = client.post("/pull-data", json={"max_pages": 1}).get_json()
    assert "Already up to date" in data["message"]


@pytest.mark.buttons
def test_pull_data_triggers_loader_with_scraped_rows(client, monkeypatch):
    import app as app_module
    import scrape

    fake_html = "<html><body><table><tbody></tbody></table></body></html>"
    fake_row = {
        "program": "Computer Science, MIT",
        "comments": "Accepted!",
        "date_added": "Added on January 15, 2026",
        "url": "https://www.thegradcafe.com/result/12345",
        "status": "Accepted",
        "term": "Fall 2026",
        "us_or_international": "American",
        "gpa": "3.80",
        "gre": "320",
        "gre_v": "160",
        "gre_aw": "4.5",
        "degree": "PhD",
    }

    monkeypatch.setattr(app_module, "llm_standardize", lambda _x: {
        "standardized_program": "Computer Science",
        "standardized_university": "Massachusetts Institute of Technology",
    })
    monkeypatch.setattr(app_module, "fix_gre_aw", lambda _conn: 0)
    monkeypatch.setattr(app_module, "fix_uc_universities", lambda _conn: 0)
    monkeypatch.setattr(app_module.psycopg, "connect", lambda **kw: FakeInsertConn())
    monkeypatch.setattr(scrape, "fetch_page", lambda url, *a, **kw: fake_html)
    monkeypatch.setattr(scrape, "parse_survey", lambda html: [fake_row])
    monkeypatch.setattr(scrape, "get_max_pages", lambda html: 1)

    resp = client.post("/pull-data", json={"max_pages": 1})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["scraped"] >= 1
    assert data["inserted"] >= 1


# ---- onclick wiring in HTML ----

@pytest.mark.buttons
def test_pull_btn_references_pullData(client):
    html = client.get("/").data.decode()
    assert 'onclick="pullData()"' in html


@pytest.mark.buttons
def test_update_btn_references_updateAnalysis(client):
    html = client.get("/").data.decode()
    assert 'onclick="updateAnalysis()"' in html


# ---- dashboard.js inclusion and content ----

@pytest.mark.buttons
def test_dashboard_js_script_tag(client):
    html = client.get("/").data.decode()
    assert "dashboard.js" in html


def _read_js():
    js_path = os.path.join(
        os.path.dirname(__file__), os.pardir,
        "src", "website", "_static", "dashboard.js",
    )
    with open(js_path, encoding="utf-8") as f:
        return f.read()


@pytest.mark.buttons
def test_dashboard_js_contains_isPulling():
    assert "var isPulling" in _read_js()


@pytest.mark.buttons
def test_dashboard_js_isPulling_guards_updateAnalysis():
    assert "if (isPulling)" in _read_js()


@pytest.mark.buttons
def test_dashboard_js_warning_message():
    assert "A Pull Data request is still running" in _read_js()


@pytest.mark.buttons
def test_pull_btn_disabled_during_isPulling():
    js = _read_js()
    assert "btn.disabled = true" in js


@pytest.mark.buttons
def test_update_btn_disabled_during_isPulling():
    js = _read_js()
    assert 'document.getElementById("update-btn").disabled = true' in js


@pytest.mark.buttons
def test_update_analysis_reloads_page():
    js = _read_js()
    assert "location.reload()" in js
