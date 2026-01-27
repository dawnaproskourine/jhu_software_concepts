import sys
import time

from bs4 import BeautifulSoup
from urllib.request import urlopen, Request
import RobotsChecker
import argparse
import re
import json

from module_2.scrape_ai import scrape_gradcafe, get_max_pages
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
    text = cell.get_text(separator=" | ", strip=True)
    parts = [p.strip() for p in text.split(" | ")]

    for part in parts:
        part_lower = part.lower()

        # check for term (eg "Fall 2024")
        if re.match(r'^(fall|spring|summer|winter)\s+\d{4}$', part_lower):
            result['term'] = part

        # Check for US/International
        elif part_lower == "international":
            result["US/International"] = "International"
        elif part_lower == "american":
            result["US/International"] = "American"

        # check for GPA
        elif part_lower.startswith("gpa"):
            result["GPA"] = part

        # check for status if not already set of if this is more detailed
        elif any(x in part_lower for x in ["accepted", "rejected", "interview", "wait"]):
            # only update if this looks like a status and we don't have one
            if "status" not in result or not result["status"]:
                result["status"] = part

        # otherwise treat as comment
        else:
            if result["comments"]:
                result["comments"] += " " + part
            else:
                result["comments"] = part



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

    # check robots.txt
    if not ignore_robots:
        print(f"Checking robots.txt for user-agent: {user_agent}", file=sys.stderr)
        robots = RobotsChecker.RobotsChecker(base_url, user_agent)

        if not robots.can_fetch(base_url):
            print(f"Error: robots.txt disallows access to {base_url} for {user_agent}", file=sys.stderr)
            print("Use --ignore_robots option to ignore robots.txt check (not recommended)", file=sys.stderr)
            return all_results

         # use crawl-delay from robots.txt if specified, otherwise use provided delay
        robots_delay = robots.get_crawl_delay(delay)
        if robots_delay != delay:
            print(f"Using crawl delay from robots.txt: {robots_delay}s", file=sys.stderr)
            delay = robots_delay

    # fetch first page to determine total pages
    html = fetch_page(base_url, user_agent)
    results = parse_survey(html)
    all_results.extend(results)

    total_pages = get_max_pages(html)
    pages_to_fetch = min(total_pages, max_pages) if max_pages else total_pages

    print(f"Found {total_pages} total pages. Fetching {pages_to_fetch} pages...", file=sys.stderr)
    print(f"Page 1/{pages_to_fetch} - {len(results)} results", file=sys.stderr)

    # fetch remaining pages
    for page_num in range(2, pages_to_fetch + 1):
        time.sleep(delay) # being respectful to the server

        page_url = f"{base_url}?page={page_num}"

        # check robots.txt for each page URL
        if not ignore_robots and not robots.can_fetch(page_url):
            print(f"Skipping page {page_num}: disallowed by robots.txt", file=sys.stderr)
            continue

        try:
            html = fetch_page(page_url, user_agent)
            results = parse_survey(html)
            all_results.extend(results)
            print(f"Page {page_num}/{pages_to_fetch} - {len(results)} results", file=sys.stderr)
        except Exception as e:
            print(f"Error fetching page {page_num}: {e}", file=sys.stderr)
            continue

    print(f"Total results: {len(all_results)}", file=sys.stderr)
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
    main()
