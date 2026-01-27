from bs4 import BeautifulSoup
from urllib.request import urlopen, Request
import RobotsChecker
import argparse
import re
import json

from module_2.scrape_ai import scrape_gradcafe
from module_2.tutorial.scraper import results


def fetch_page(url, user_agent = RobotsChecker.DEFAULT_USER_AGENT):
    """Fetch a page and parse its content"""
    headers = {'User-Agent': user_agent}
    request = Request(url, headers=headers)
    page = urlopen(request)
    html = page.read().decode("utf-8")
    return html

def parse_survey(html):
    """Parse the survey page and return a dict of survey data"""
    soup = BeautifulSoup(html, "html.parser")
    results = []

    # find the main results table
    table = soup.find("table")
    if not table:
        return results

    # data is stored in tbody
    tbody = table.find("tbody")
    if not tbody:
        return results

    rows = tbody.find_all("tr")

    current_result = None
    for row in rows:
        cells = row.find_all("td")

        if len(cells) == 5:
            # main data row - save previous result and start new one
            if current_result:
                results.append(current_result)
            current_result = parse_main_row(cells)
        elif len(cells) == 1 and current_result:
            parse_detail_row(cells[0], current_result)

    # Remember the last result
    if current_result:
        results.append(current_result)

    return results


def parse_main_row(cells):
    """Parse the main table row and return a dict of survey data"""
    result = {}

    # cell 0: university name
    school = cells[0].get_text(strip=True)

    # cell 1: program and degree (eg, "Physics | PhD")
    program_cell = cells[1].get_text(separator=" | ", strip=True)
    program_parts = program_cell.split(" | ")
    program_name = program_parts[0] if program_parts else ""

    # combine school and program
    result["program"] = f"{program_name}, {school}"

    # extract degree from program cell
    if len(program_parts) > 1:
        degree = program_parts[1].strip()
        if "phd" in degree.lower():
            result["Degree"] = "PhD"
        elif "master" in degree.lower() or degree in ["MS", "MA", "MFA", "MBA", "MEng"]:
            result["Degree"] = "Masters"
        else:
            result["Degree"] = degree

    # cell 2: date added
    date_text = cells[2].get_text(strip=True)
    result["date_added"] = f"Added on {date_text}"

    # cell 3: decision/status
    result["status"] = cells[3].get_text(strip=True)

    # cell 4: links - extract URL
    link = cells[4].find("a", href=re.compile(r"/result/"))
    if link:
        href = link.get("href", "")
        if href.startswith("/"):
            result["url"] = f"https://www.thegradcafe.com{href}"
        else:
            result["url"] = href

    # initialize comments
    result["comments"] = ""
    return result

def parse_detail_row(cell, result):
    """Parse the detail table row and return a dict of survey data"""

def scrape_gradcafe(
        base_url="https://www.thegradcafe.com/survey/",
        max_pages=None, delay=0.5,
        user_agent = RobotsChecker.DEFAULT_USER_AGENT,
        ignore_robots=False):
    """
    Scrape the gradcafe page and parse its content across multiple pages

    Args:
        base_url: base url for gradcafe survey pages
        max_pages: maximum number of pages to scrape (None to scrape all)
        delay: delay between pages in seconds - to be respectful to the server
        user_agent: user agent to use for requests
        ignore_robots: ignore robots when scraping. if true skip robots.txt check - not recommended

    Returns:
        List of dictionaries containing survey data
    """
    all_results = []

    return all_results

def main():
    """Main function. Scrape the survey page and parse its content. Output JSON file"""
    parser = argparse.ArgumentParser(
        description="Scrape the survey page and parse its content. Return output as JSON"
    )
    args = parser.parse_args()
    results = scrape_gradcafe(
        max_pages=max_pages,
        delay=args.delay,
        user_agent=args.user_agent,
        ignore_robots=args.ignore_robots
    )
    return results


if __name__ == "__main__":

