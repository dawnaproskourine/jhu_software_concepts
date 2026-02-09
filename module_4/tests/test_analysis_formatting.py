"""Requirement (c): analysis output formatting tests.

Verifies question labels, percentage formatting (X.XX%),
and that all mock scalar values appear in the rendered HTML.
"""

import re
from decimal import Decimal

from conftest import MOCK_QUERY_DATA


# ---- question labels ----

def test_all_13_questions_have_labels(client):
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(client.get("/").data.decode(), "html.parser")
    questions = soup.find_all("div", class_="question")
    assert len(questions) == 13
    for q in questions:
        assert q.get_text(strip=True), "Empty question label found"


EXPECTED_TOPICS = [
    "total applicant",
    "Fall 2026",
    "international",
    "acceptance",
    "average GPA",
    "American",
    "accepted applicants",
    "JHU",
    "PhD CS",
    "top 10 most popular programs",
    "top 10 most popular universities",
    "acceptance rate by degree",
    "acceptance rate by nationality",
]


def test_each_expected_question_topic_present(client):
    html = client.get("/").data.decode().lower()
    for topic in EXPECTED_TOPICS:
        assert topic.lower() in html, f"Topic not found: {topic}"


# ---- percentage formats ----

def test_international_pct_format(client):
    html = client.get("/").data.decode()
    assert "32.17%" in html


def test_acceptance_pct_fall2026_format(client):
    html = client.get("/").data.decode()
    assert "24.53%" in html


def test_rate_by_degree_percentages(client):
    html = client.get("/").data.decode()
    for pct in ("24.76%", "20.00%", "30.95%"):
        assert pct in html, f"Missing degree rate: {pct}"


def test_rate_by_nationality_percentages(client):
    html = client.get("/").data.decode()
    for pct in ("25.23%", "23.30%"):
        assert pct in html, f"Missing nationality rate: {pct}"


def test_percentages_have_exactly_two_decimals(client):
    html = client.get("/").data.decode()
    for match in re.findall(r"(\d+\.\d+)%", html):
        decimals = match.split(".")[1]
        assert len(decimals) == 2, f"Bad decimal places in {match}%"


# ---- average value formats ----

def test_avg_gpa_format(client):
    html = client.get("/").data.decode()
    assert "3.52" in html


def test_avg_gre_format(client):
    html = client.get("/").data.decode()
    assert "318.45" in html


def test_avg_gre_v_format(client):
    html = client.get("/").data.decode()
    assert "157.23" in html


def test_avg_gre_aw_format(client):
    html = client.get("/").data.decode()
    assert "3.98" in html


def test_american_gpa_fall2026_format(client):
    html = client.get("/").data.decode()
    assert "3.61" in html


def test_accepted_gpa_fall2026_format(client):
    html = client.get("/").data.decode()
    assert "3.74" in html


# ---- all scalar mock values rendered ----

def test_all_scalar_values_appear_in_html(client):
    html = client.get("/").data.decode()
    scalars = {
        k: v for k, v in MOCK_QUERY_DATA.items()
        if isinstance(v, (int, float, Decimal))
    }
    for key, val in scalars.items():
        assert str(val) in html, f"Value for {key} ({val}) not in HTML"
