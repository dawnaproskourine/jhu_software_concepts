"""Scraper unit tests — exercise real parse/fetch functions.

Only network I/O (``urlopen``) is stubbed; ``fetch_page``, ``parse_survey``,
``parse_main_row``, ``parse_detail_row``, and ``get_max_pages`` all run for
real against crafted HTML.
"""

import json
import sys

import pytest

from conftest import FakeResponse

from scrape import (
    fetch_page, parse_survey, parse_main_row, parse_detail_row,
    get_max_pages, scrape_data, main,
)
from bs4 import BeautifulSoup
import scrape


# ---------------------------------------------------------------------------
# Sample HTML fixture — GradCafe-style table with 2 applicant entries
# ---------------------------------------------------------------------------

SAMPLE_HTML = """
<html>
<body>
<table>
<tbody>
  <!-- Applicant 1: main row (5 cells) -->
  <tr>
    <td>Stanford University</td>
    <td>Computer Science | PhD</td>
    <td>January 15, 2026</td>
    <td>Accepted</td>
    <td><a href="/result/11111">View</a></td>
  </tr>
  <!-- Applicant 1: detail row (1 cell) -->
  <tr>
    <td>Fall 2026 | American | GPA 3.85 | GRE 320 | GRE V 160 | GRE AW 4.5</td>
  </tr>
  <!-- Applicant 1: comment row (1 cell) -->
  <tr>
    <td>Very happy with this result!</td>
  </tr>

  <!-- Applicant 2: main row (5 cells) -->
  <tr>
    <td>MIT</td>
    <td>Electrical Engineering | Masters</td>
    <td>February 1, 2026</td>
    <td>Rejected</td>
    <td><a href="/result/22222">View</a></td>
  </tr>
  <!-- Applicant 2: detail row (1 cell) -->
  <tr>
    <td>Spring 2026 | International | GPA 3.60 | GRE 315 | GRE V 155 | GRE AW 4.0</td>
  </tr>
</tbody>
</table>

<!-- Pagination links -->
<a href="?page=1">1</a>
<a href="?page=2">2</a>
<a href="?page=3">3</a>
<a href="?page=4">4</a>
<a href="?page=5">5</a>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Helper: build BeautifulSoup cells from the sample HTML
# ---------------------------------------------------------------------------

def _main_cells(index=0):
    """Return the list of <td> elements from the *index*-th 5-cell row."""
    soup = BeautifulSoup(SAMPLE_HTML, "html.parser")
    rows = soup.find("tbody").find_all("tr")
    five_cell_rows = [r for r in rows if len(r.find_all("td")) == 5]
    return five_cell_rows[index].find_all("td")


def _detail_cell(index=0):
    """Return the single <td> from the *index*-th 1-cell row."""
    soup = BeautifulSoup(SAMPLE_HTML, "html.parser")
    rows = soup.find("tbody").find_all("tr")
    one_cell_rows = [r for r in rows if len(r.find_all("td")) == 1]
    return one_cell_rows[index].find_all("td")[0]


# =====================================================================
# parse_main_row tests
# =====================================================================

@pytest.mark.web
def test_parse_main_row_extracts_program_and_school():
    result = parse_main_row(_main_cells(0))
    assert result["program"] == "Computer Science, Stanford University"


@pytest.mark.web
def test_parse_main_row_extracts_degree():
    result = parse_main_row(_main_cells(0))
    assert result["Degree"] == "PhD"


@pytest.mark.web
def test_parse_main_row_extracts_date():
    result = parse_main_row(_main_cells(0))
    assert result["date_added"].startswith("Added on")


@pytest.mark.web
def test_parse_main_row_extracts_status():
    result = parse_main_row(_main_cells(0))
    assert result["status"] == "Accepted"


@pytest.mark.web
def test_parse_main_row_extracts_url():
    result = parse_main_row(_main_cells(0))
    assert "thegradcafe.com" in result["url"]
    assert "/result/11111" in result["url"]


@pytest.mark.web
def test_parse_main_row_defaults_gpa_gre_empty():
    result = parse_main_row(_main_cells(0))
    assert result["GPA"] == ""
    assert result["GRE"] == ""
    assert result["GRE V"] == ""
    assert result["GRE AW"] == ""


# =====================================================================
# parse_detail_row tests
# =====================================================================

@pytest.mark.web
def test_parse_detail_row_sets_term():
    result = parse_main_row(_main_cells(0))
    parse_detail_row(_detail_cell(0), result)
    assert result["term"] == "Fall 2026"


@pytest.mark.web
def test_parse_detail_row_sets_nationality():
    result = parse_main_row(_main_cells(0))
    parse_detail_row(_detail_cell(0), result)
    assert result["US/International"] == "American"


@pytest.mark.web
def test_parse_detail_row_sets_gpa():
    result = parse_main_row(_main_cells(0))
    parse_detail_row(_detail_cell(0), result)
    assert result["GPA"] == "GPA 3.85"


@pytest.mark.web
def test_parse_detail_row_sets_gre_scores():
    result = parse_main_row(_main_cells(0))
    parse_detail_row(_detail_cell(0), result)
    assert result["GRE"] == "GRE 320"
    assert result["GRE V"] == "GRE V 160"
    assert result["GRE AW"] == "GRE AW 4.5"


@pytest.mark.web
def test_parse_detail_row_appends_comments():
    result = parse_main_row(_main_cells(0))
    # detail row (structured data)
    parse_detail_row(_detail_cell(0), result)
    # comment row (free-form text) — 2nd one-cell row in tbody
    parse_detail_row(_detail_cell(1), result)
    assert any("Very happy" in c for c in result["comments"])


# =====================================================================
# parse_survey tests
# =====================================================================

@pytest.mark.web
def test_parse_survey_returns_list_of_dicts():
    results = parse_survey(SAMPLE_HTML)
    assert len(results) == 2
    assert isinstance(results[0], dict)
    assert isinstance(results[1], dict)


@pytest.mark.web
def test_parse_survey_empty_table():
    html = "<html><body><table><tbody></tbody></table></body></html>"
    assert parse_survey(html) == []


@pytest.mark.web
def test_parse_survey_no_table():
    html = "<html><body></body></html>"
    assert parse_survey(html) == []


# =====================================================================
# get_max_pages tests
# =====================================================================

@pytest.mark.web
def test_get_max_pages_with_pagination():
    assert get_max_pages(SAMPLE_HTML) == 5


@pytest.mark.web
def test_get_max_pages_no_pagination():
    html = "<html><body><p>No pagination here</p></body></html>"
    assert get_max_pages(html) == 1


# =====================================================================
# fetch_page test — monkeypatch urlopen at transport level
# =====================================================================

@pytest.mark.web
def test_fetch_page_calls_urlopen_and_decodes(monkeypatch):
    sample = "<html><body>Hello</body></html>"
    monkeypatch.setattr(scrape, "urlopen", lambda req: FakeResponse(sample))
    result = fetch_page("https://example.com")
    assert result == sample


# =====================================================================
# Edge cases — additional branch coverage
# =====================================================================

@pytest.mark.web
def test_parse_survey_table_no_tbody():
    html = "<html><body><table><tr><td>no tbody</td></tr></table></body></html>"
    assert parse_survey(html) == []


@pytest.mark.web
def test_parse_main_row_absolute_href():
    """Href that is already an absolute URL — stored as-is (line 119)."""
    html = """<table><tbody>
    <tr>
        <td>School</td>
        <td>Prog | PhD</td>
        <td>Jan 1, 2026</td>
        <td>Accepted</td>
        <td><a href="https://other.example.com/result/abc">View</a></td>
    </tr>
    </tbody></table>"""
    soup = BeautifulSoup(html, "html.parser")
    cells = soup.find("tr").find_all("td")
    result = parse_main_row(cells)
    assert result["url"] == "https://other.example.com/result/abc"


@pytest.mark.web
def test_parse_main_row_non_matching_href():
    """Href that doesn't match /result/ — url key should not be set."""
    html = """<table><tbody>
    <tr>
        <td>School</td>
        <td>Prog | PhD</td>
        <td>Jan 1, 2026</td>
        <td>Accepted</td>
        <td><a href="/other/path">View</a></td>
    </tr>
    </tbody></table>"""
    soup = BeautifulSoup(html, "html.parser")
    cells = soup.find("tr").find_all("td")
    result = parse_main_row(cells)
    assert "url" not in result


@pytest.mark.web
def test_parse_main_row_other_degree():
    """Degree that is neither PhD nor Masters variant → stored as-is."""
    html = """<table><tbody>
    <tr>
        <td>School</td>
        <td>Prog | JD</td>
        <td>Jan 1, 2026</td>
        <td>Accepted</td>
        <td><a href="/result/99999">View</a></td>
    </tr>
    </tbody></table>"""
    soup = BeautifulSoup(html, "html.parser")
    cells = soup.find("tr").find_all("td")
    result = parse_main_row(cells)
    assert result["Degree"] == "JD"


@pytest.mark.web
def test_parse_detail_row_gre_q():
    """Detail row with GRE Q score."""
    html = '<td>GRE Q 168</td>'
    soup = BeautifulSoup(html, "html.parser")
    cell = soup.find("td")
    result = parse_main_row(_main_cells(0))
    parse_detail_row(cell, result)
    assert result["GRE Q"] == "GRE Q 168"


@pytest.mark.web
def test_parse_detail_row_status_when_empty():
    """Detail row with status keyword when main status is empty."""
    html = '<td>Accepted via email</td>'
    soup = BeautifulSoup(html, "html.parser")
    cell = soup.find("td")
    result = {"status": "", "comments": [], "GPA": "", "GRE": "",
              "GRE V": "", "GRE AW": "", "GRE Q": ""}
    parse_detail_row(cell, result)
    assert "Accepted via email" in result["status"]


@pytest.mark.web
def test_parse_detail_row_duplicate_comment():
    """Second call adds via comment_parts but dedup prevents extra pure-comment append."""
    html = '<td>I love this program</td>'
    soup = BeautifulSoup(html, "html.parser")
    cell = soup.find("td")
    result = parse_main_row(_main_cells(0))
    parse_detail_row(cell, result)
    parse_detail_row(cell, result)
    # comment_parts path appends unconditionally, but the "text not in comments"
    # guard (line 216) prevents a third copy from the pure-comment path.
    count = sum(1 for c in result["comments"] if "I love this program" in c)
    assert count == 2


@pytest.mark.web
def test_parse_detail_row_pure_comment_with_pipe():
    """Comment with pipe separators hits the pure-comment append (line 217)."""
    html = '<td>good school | nice campus</td>'
    soup = BeautifulSoup(html, "html.parser")
    cell = soup.find("td")
    result = parse_main_row(_main_cells(0))
    parse_detail_row(cell, result)
    # comment_parts joins with space → "good school nice campus"
    # The full text "good school | nice campus" differs, so line 217 appends it too
    assert any("good school | nice campus" in c for c in result["comments"])


@pytest.mark.web
def test_parse_detail_row_empty_cell():
    """Empty detail cell should be skipped."""
    html = '<td>   </td>'
    soup = BeautifulSoup(html, "html.parser")
    cell = soup.find("td")
    result = parse_main_row(_main_cells(0))
    before = dict(result)
    parse_detail_row(cell, result)
    # Comments should not grow
    assert result["comments"] == before["comments"]


# =====================================================================
# scrape_data() tests — mock urlopen and RobotsChecker
# =====================================================================

_SIMPLE_HTML = """<html><body>
<table><tbody>
  <tr>
    <td>School</td><td>CS | PhD</td><td>Jan 1, 2026</td>
    <td>Accepted</td><td><a href="/result/1">V</a></td>
  </tr>
  <tr><td>Fall 2026 | American | GPA 3.80</td></tr>
</tbody></table>
<a href="?page=1">1</a>
</body></html>"""

_TWO_PAGE_HTML_P1 = """<html><body>
<table><tbody>
  <tr>
    <td>School</td><td>CS | PhD</td><td>Jan 1, 2026</td>
    <td>Accepted</td><td><a href="/result/1">V</a></td>
  </tr>
  <tr><td>Fall 2026 | American | GPA 3.80</td></tr>
</tbody></table>
<a href="?page=1">1</a>
<a href="?page=2">2</a>
</body></html>"""

_TWO_PAGE_HTML_P2 = """<html><body>
<table><tbody>
  <tr>
    <td>Other</td><td>EE | Masters</td><td>Feb 1, 2026</td>
    <td>Rejected</td><td><a href="/result/2">V</a></td>
  </tr>
  <tr><td>Fall 2026 | International | GPA 3.60</td></tr>
</tbody></table>
<a href="?page=1">1</a>
<a href="?page=2">2</a>
</body></html>"""


@pytest.mark.web
def test_scrape_data_ignore_robots(monkeypatch):
    monkeypatch.setattr(scrape, "urlopen", lambda req: FakeResponse(_SIMPLE_HTML))
    results = scrape_data(
        base_url="https://example.com/survey/",
        max_pages=1, delay=0, ignore_robots=True,
    )
    assert len(results) == 1
    assert isinstance(results[0]["comments"], str)


@pytest.mark.web
def test_scrape_data_robots_disallows(monkeypatch):
    class _FakeRobots:
        def __init__(self, *a, **kw):
            pass
        def can_fetch(self, url):
            return False
        def get_crawl_delay(self, default):
            return default

    class _FakeModule:
        DEFAULT_USER_AGENT = "FakeAgent"
        RobotsChecker = _FakeRobots

    monkeypatch.setattr(scrape, "robots_checker", _FakeModule)
    results = scrape_data(
        base_url="https://example.com/survey/",
        max_pages=1, delay=0, ignore_robots=False,
    )
    assert results == []


@pytest.mark.web
def test_scrape_data_crawl_delay_override(monkeypatch):
    class _FakeRobots:
        def __init__(self, *a, **kw):
            pass
        def can_fetch(self, url):
            return True
        def get_crawl_delay(self, default):
            return 99.0  # Different from default

    class _FakeModule:
        DEFAULT_USER_AGENT = "FakeAgent"
        RobotsChecker = _FakeRobots

    monkeypatch.setattr(scrape, "robots_checker", _FakeModule)
    monkeypatch.setattr(scrape, "urlopen", lambda req: FakeResponse(_SIMPLE_HTML))

    delays = []
    monkeypatch.setattr(scrape.time, "sleep", lambda d: delays.append(d))

    results = scrape_data(
        base_url="https://example.com/survey/",
        max_pages=1, delay=0.5, ignore_robots=False,
    )
    assert len(results) == 1


@pytest.mark.web
def test_scrape_data_multi_page(monkeypatch):
    pages = {"n": 0}

    def _urlopen(req):
        pages["n"] += 1
        if pages["n"] == 1:
            return FakeResponse(_TWO_PAGE_HTML_P1)
        return FakeResponse(_TWO_PAGE_HTML_P2)

    monkeypatch.setattr(scrape, "urlopen", _urlopen)
    monkeypatch.setattr(scrape.time, "sleep", lambda d: None)

    results = scrape_data(
        base_url="https://example.com/survey/",
        max_pages=2, delay=0, ignore_robots=True,
    )
    assert len(results) == 2


@pytest.mark.web
def test_scrape_data_page_error_continues(monkeypatch):
    pages = {"n": 0}

    def _urlopen(req):
        pages["n"] += 1
        if pages["n"] == 1:
            return FakeResponse(_TWO_PAGE_HTML_P1)
        raise OSError("Network error on page 2")

    monkeypatch.setattr(scrape, "urlopen", _urlopen)
    monkeypatch.setattr(scrape.time, "sleep", lambda d: None)

    results = scrape_data(
        base_url="https://example.com/survey/",
        max_pages=2, delay=0, ignore_robots=True,
    )
    # Page 1 results should still be present
    assert len(results) >= 1


@pytest.mark.web
def test_scrape_data_per_page_robots_skip(monkeypatch):
    call_count = {"n": 0}

    class _FakeRobots:
        def __init__(self, *a, **kw):
            pass
        def can_fetch(self, url):
            call_count["n"] += 1
            if "page=2" in url:
                return False  # Disallow page 2
            return True
        def get_crawl_delay(self, default):
            return default

    class _FakeModule:
        DEFAULT_USER_AGENT = "FakeAgent"
        RobotsChecker = _FakeRobots

    monkeypatch.setattr(scrape, "robots_checker", _FakeModule)
    monkeypatch.setattr(scrape, "urlopen", lambda req: FakeResponse(_TWO_PAGE_HTML_P1))
    monkeypatch.setattr(scrape.time, "sleep", lambda d: None)

    results = scrape_data(
        base_url="https://example.com/survey/",
        max_pages=2, delay=0, ignore_robots=False,
    )
    # Only page 1 results
    assert len(results) == 1


# =====================================================================
# main() tests — CLI entry point
# =====================================================================

@pytest.mark.web
def test_main_stdout_json(monkeypatch, capsys):
    monkeypatch.setattr(scrape, "urlopen", lambda req: FakeResponse(_SIMPLE_HTML))
    monkeypatch.setattr(
        sys, "argv", ["scrape.py", "--pages", "1", "--ignore_robots"]
    )

    main()
    out = capsys.readouterr().out
    data = json.loads(out)
    assert isinstance(data, list)
    assert len(data) == 1


@pytest.mark.web
def test_main_file_output(monkeypatch, tmp_path):
    monkeypatch.setattr(scrape, "urlopen", lambda req: FakeResponse(_SIMPLE_HTML))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys, "argv", ["scrape.py", "--pages", "1", "--ignore_robots", "-o", "out.json"]
    )

    main()

    outfile = str(tmp_path / "out.json")
    with open(outfile, encoding="utf-8") as f:
        data = json.loads(f.read())
    assert isinstance(data, list)
    assert len(data) == 1


@pytest.mark.web
def test_main_invalid_output_filename(monkeypatch, capsys):
    monkeypatch.setattr(scrape, "urlopen", lambda req: FakeResponse(_SIMPLE_HTML))
    monkeypatch.setattr(
        sys, "argv", ["scrape.py", "--pages", "1", "--ignore_robots", "-o", "/"]
    )

    main()

    err = capsys.readouterr().err
    assert "invalid output filename" in err
