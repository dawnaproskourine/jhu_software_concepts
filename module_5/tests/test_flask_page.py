"""Requirement (a): page rendering tests.

Verifies that a testable Flask app is created with the required routes,
the dashboard loads, contains all 13 Q&A blocks, buttons, tables, and
ordered lists.
"""

import pytest
from bs4 import BeautifulSoup


def _soup(client):
    """GET / and return a BeautifulSoup object."""
    resp = client.get("/")
    return BeautifulSoup(resp.data.decode(), "html.parser")


# ---- Flask app setup ----

@pytest.mark.web
def test_app_is_testing(client):
    import app as app_module
    test_app = app_module.create_app(testing=True)
    assert test_app.config["TESTING"] is True


@pytest.mark.web
def test_app_has_index_route(client):
    import app as app_module
    test_app = app_module.create_app(testing=True)
    rules = [rule.rule for rule in test_app.url_map.iter_rules()]
    assert "/" in rules


@pytest.mark.web
def test_app_has_pull_data_route(client):
    import app as app_module
    test_app = app_module.create_app(testing=True)
    rules = [rule.rule for rule in test_app.url_map.iter_rules()]
    assert "/pull-data" in rules


@pytest.mark.web
def test_pull_data_route_accepts_post(client):
    import app as app_module
    test_app = app_module.create_app(testing=True)
    for rule in test_app.url_map.iter_rules():
        if rule.rule == "/pull-data":
            assert "POST" in rule.methods


@pytest.mark.web
def test_index_route_accepts_get(client):
    import app as app_module
    test_app = app_module.create_app(testing=True)
    for rule in test_app.url_map.iter_rules():
        if rule.rule == "/":
            assert "GET" in rule.methods


# ---- basic status ----

@pytest.mark.web
def test_index_returns_200(client):
    resp = client.get("/")
    assert resp.status_code == 200


@pytest.mark.web
def test_page_title_present(client):
    html = client.get("/").data.decode()
    assert "Grad School Cafe Data Analysis" in html


# ---- Q&A blocks ----

@pytest.mark.web
def test_thirteen_qa_blocks(client):
    soup = _soup(client)
    assert len(soup.find_all("div", class_="qa")) == 13


@pytest.mark.web
def test_each_qa_has_question_div(client):
    soup = _soup(client)
    for qa in soup.find_all("div", class_="qa"):
        assert qa.find("div", class_="question") is not None


@pytest.mark.web
def test_each_qa_has_answer_div(client):
    soup = _soup(client)
    for qa in soup.find_all("div", class_="qa"):
        assert qa.find("div", class_="answer") is not None


# ---- buttons ----

@pytest.mark.web
def test_pull_btn_present(client):
    soup = _soup(client)
    assert soup.find(attrs={"data-testid": "pull-data-btn"}) is not None


@pytest.mark.web
def test_update_btn_present(client):
    soup = _soup(client)
    assert soup.find(attrs={"data-testid": "update-analysis-btn"}) is not None


# ---- averages table ----

@pytest.mark.web
def test_averages_table_has_four_metrics(client):
    html = client.get("/").data.decode()
    for metric in ("GPA", "GRE", "GRE Verbal", "GRE Analytical Writing"):
        assert metric in html


# ---- PhD CS table ----

@pytest.mark.web
def test_phd_cs_table_has_program_and_llm_rows(client):
    html = client.get("/").data.decode()
    assert "Program field" in html
    assert "LLM-generated field" in html


# ---- rate by degree ----

@pytest.mark.web
def test_rate_by_degree_table_renders(client):
    html = client.get("/").data.decode()
    assert "Degree" in html
    assert "Rate" in html


# ---- rate by nationality ----

@pytest.mark.web
def test_rate_by_nationality_table_renders(client):
    html = client.get("/").data.decode()
    assert "Nationality" in html


# ---- ordered lists ----

@pytest.mark.web
def test_top_programs_ordered_list(client):
    soup = _soup(client)
    qa_blocks = soup.find_all("div", class_="qa")
    # Q10 (0-indexed 9): top programs
    ol = qa_blocks[9].find("ol")
    assert ol is not None
    assert len(ol.find_all("li")) == 10


@pytest.mark.web
def test_top_universities_ordered_list(client):
    soup = _soup(client)
    qa_blocks = soup.find_all("div", class_="qa")
    # Q11 (0-indexed 10): top universities
    ol = qa_blocks[10].find("ol")
    assert ol is not None
    assert len(ol.find_all("li")) == 10


@pytest.mark.web
def test_top_programs_contains_expected_entries(client):
    soup = _soup(client)
    qa_blocks = soup.find_all("div", class_="qa")
    first_li = qa_blocks[9].find("ol").find("li")
    assert "Computer Science" in first_li.get_text()
