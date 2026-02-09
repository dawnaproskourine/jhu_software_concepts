"""Requirement (a): page rendering tests.

Verifies that a testable Flask app is created with the required routes,
the dashboard loads, contains all 13 Q&A blocks, buttons, tables, and
ordered lists.
"""

from bs4 import BeautifulSoup


def _soup(client):
    """GET / and return a BeautifulSoup object."""
    resp = client.get("/")
    return BeautifulSoup(resp.data.decode(), "html.parser")


# ---- Flask app setup ----

def test_app_is_testing(client):
    from app import app
    assert app.config["TESTING"] is True


def test_app_has_index_route(client):
    from app import app
    rules = [rule.rule for rule in app.url_map.iter_rules()]
    assert "/" in rules


def test_app_has_pull_data_route(client):
    from app import app
    rules = [rule.rule for rule in app.url_map.iter_rules()]
    assert "/pull-data" in rules


def test_pull_data_route_accepts_post(client):
    from app import app
    for rule in app.url_map.iter_rules():
        if rule.rule == "/pull-data":
            assert "POST" in rule.methods


def test_index_route_accepts_get(client):
    from app import app
    for rule in app.url_map.iter_rules():
        if rule.rule == "/":
            assert "GET" in rule.methods


# ---- basic status ----

def test_index_returns_200(client):
    resp = client.get("/")
    assert resp.status_code == 200


def test_page_title_present(client):
    html = client.get("/").data.decode()
    assert "Grad School Cafe Data Analysis" in html


# ---- Q&A blocks ----

def test_thirteen_qa_blocks(client):
    soup = _soup(client)
    assert len(soup.find_all("div", class_="qa")) == 13


def test_each_qa_has_question_div(client):
    soup = _soup(client)
    for qa in soup.find_all("div", class_="qa"):
        assert qa.find("div", class_="question") is not None


def test_each_qa_has_answer_div(client):
    soup = _soup(client)
    for qa in soup.find_all("div", class_="qa"):
        assert qa.find("div", class_="answer") is not None


# ---- buttons ----

def test_pull_btn_present(client):
    soup = _soup(client)
    assert soup.find(id="pull-btn") is not None


def test_update_btn_present(client):
    soup = _soup(client)
    assert soup.find(id="update-btn") is not None


# ---- averages table ----

def test_averages_table_has_four_metrics(client):
    html = client.get("/").data.decode()
    for metric in ("GPA", "GRE", "GRE Verbal", "GRE Analytical Writing"):
        assert metric in html


# ---- PhD CS table ----

def test_phd_cs_table_has_program_and_llm_rows(client):
    html = client.get("/").data.decode()
    assert "Program field" in html
    assert "LLM-generated field" in html


# ---- rate by degree ----

def test_rate_by_degree_table_renders(client):
    html = client.get("/").data.decode()
    assert "Degree" in html
    assert "Rate" in html


# ---- rate by nationality ----

def test_rate_by_nationality_table_renders(client):
    html = client.get("/").data.decode()
    assert "Nationality" in html


# ---- ordered lists ----

def test_top_programs_ordered_list(client):
    soup = _soup(client)
    qa_blocks = soup.find_all("div", class_="qa")
    # Q10 (0-indexed 9): top programs
    ol = qa_blocks[9].find("ol")
    assert ol is not None
    assert len(ol.find_all("li")) == 10


def test_top_universities_ordered_list(client):
    soup = _soup(client)
    qa_blocks = soup.find_all("div", class_="qa")
    # Q11 (0-indexed 10): top universities
    ol = qa_blocks[10].find("ol")
    assert ol is not None
    assert len(ol.find_all("li")) == 10


def test_top_programs_contains_expected_entries(client):
    soup = _soup(client)
    qa_blocks = soup.find_all("div", class_="qa")
    first_li = qa_blocks[9].find("ol").find("li")
    assert "Computer Science" in first_li.get_text()
