"""GradCafe web scraper for applicant survey data."""

import argparse
import json
import os
import re
import sys
import time

from urllib.request import urlopen, Request

from bs4 import BeautifulSoup

import robots_checker


def fetch_page(url, user_agent=robots_checker.DEFAULT_USER_AGENT):
    """Fetch a web page and return its HTML content.

    :param url: The URL to fetch.
    :type url: str
    :param user_agent: The User-Agent header string.
    :type user_agent: str
    :returns: The decoded HTML content of the page.
    :rtype: str
    """
    headers = {'User-Agent': user_agent}
    request = Request(url, headers=headers)
    page = urlopen(request)  # pylint: disable=consider-using-with
    html = page.read().decode("utf-8")
    return html

def parse_survey(html):
    """Parse the GradCafe survey page and return a list of applicant data.

    :param html: The raw HTML content of a survey page.
    :type html: str
    :returns: A list of dictionaries, each containing one applicant's data.
    :rtype: list[dict]
    """
    soup = BeautifulSoup(html, "html.parser")
    results = []

    # Find the main results table
    table = soup.find("table")
    if not table:
        return results

    # Data is stored in tbody
    tbody = table.find("tbody")
    if not tbody:
        return results

    rows = tbody.find_all("tr")

    current_result = None
    for row in rows:
        cells = row.find_all("td")

        if len(cells) == 5:
            # Main data row - save previous result and start new one
            if current_result:
                results.append(current_result)
            current_result = parse_main_row(cells)
        elif len(cells) == 1 and current_result:
            # This could be a detail row or a comment row
            parse_detail_row(cells[0], current_result)

    # Remember the last result
    if current_result:
        results.append(current_result)

    return results


def parse_main_row(cells):
    """Parse a main table row and return a dict of applicant data.

    :param cells: The list of ``<td>`` elements from a main data row.
    :type cells: list[bs4.element.Tag]
    :returns: A dictionary of parsed applicant fields.
    :rtype: dict
    """
    result = {}

    # Cell 0: university name
    school = cells[0].get_text(strip=True)

    # Cell 1: program and degree (eg, "Physics | PhD")
    program_cell = cells[1].get_text(separator=" | ", strip=True)
    program_parts = program_cell.split(" | ")
    program_name = program_parts[0] if program_parts else ""

    # Combine school and program
    result["program"] = f"{program_name}, {school}"
    result["school"] = school
    result["program_name"] = program_name

    # Extract degree from program cell
    if len(program_parts) > 1:
        degree = program_parts[1].strip()
        if "phd" in degree.lower():
            result["Degree"] = "PhD"
        elif ("master" in degree.lower()
              or degree in ["MS", "MA", "MFA", "MBA", "MEng"]):
            result["Degree"] = "Masters"
        else:
            result["Degree"] = degree

    # Cell 2: date added
    date_text = cells[2].get_text(strip=True)
    result["date_added"] = f"Added on {date_text}"

    # Cell 3: decision/status
    result["status"] = cells[3].get_text(strip=True)

    # Cell 4: links - extract URL
    link = cells[4].find("a", href=re.compile(r"/result/"))
    if link:
        href = link.get("href", "")
        if href.startswith("/"):
            result["url"] = f"https://www.thegradcafe.com{href}"
        else:
            result["url"] = href

    # Default GPA/GRE fields
    result["GPA"] = ""
    result["GRE V"] = ""
    result["GRE AW"] = ""
    result["GRE Q"] = ""
    result["GRE"] = ""

    # Initialize comments as empty list to collect multiple comment rows
    result["comments"] = []
    return result

def parse_detail_row(cell, result):  # pylint: disable=too-many-branches
    """Parse a detail or comment row and update the result dict in place.

    Handles two types of rows:

    1. Detail rows containing structured data (GPA, GRE, status, etc.)
    2. Comment rows containing free-form text.

    :param cell: The single ``<td>`` element from the detail row.
    :type cell: bs4.element.Tag
    :param result: The applicant data dict to update.
    :type result: dict
    """
    text = cell.get_text(separator=" | ", strip=True)

    # Skip empty cells
    if not text:
        return

    parts = [p.strip() for p in text.split(" | ")]

    # Track if we found any structured data
    found_structured_data = False

    # Collect any parts that don't match structured patterns
    comment_parts = []

    for part in parts:
        part_lower = part.lower()

        # Check for term (eg "Fall 2024")
        if re.match(
            r'^(fall|spring|summer|winter)\s+\d{4}$', part_lower
        ):
            result['term'] = part
            found_structured_data = True

        # Check for US/International
        elif part_lower == "international":
            result["US/International"] = "International"
            found_structured_data = True
        elif part_lower == "american":
            result["US/International"] = "American"
            found_structured_data = True

        # Check for GPA (must match "GPA X.XX" pattern)
        elif re.match(r'^gpa\s+\d+(\.\d+)?$', part_lower):
            result["GPA"] = part
            found_structured_data = True

        # Check for GRE
        elif part_lower.startswith("gre v"):
            result["GRE V"] = part
            found_structured_data = True

        elif part_lower.startswith("gre aw"):
            result["GRE AW"] = part
            found_structured_data = True

        elif part_lower.startswith("gre q"):
            result["GRE Q"] = part
            found_structured_data = True

        elif part_lower.startswith("gre"):
            result["GRE"] = part
            found_structured_data = True

        # Check for status if not already set
        elif (any(x in part_lower for x in
                  ["accepted", "rejected", "interview", "wait"])
              and len(part) < 50):
            if "status" not in result or not result["status"]:
                result["status"] = part
                found_structured_data = True

        # Unmatched part - likely a comment
        else:
            comment_parts.append(part)

    # If we have comment parts, add them to the comments list
    if comment_parts:
        comment_text = " ".join(comment_parts)
        result["comments"].append(comment_text)

    # If this entire row had no structured data, it's a pure comment row
    if not found_structured_data and text:
        if text not in result["comments"]:
            result["comments"].append(text)

def get_max_pages(html):
    """Extract the maximum page number from pagination links.

    :param html: The raw HTML content of a survey page.
    :type html: str
    :returns: The highest page number found, or 1 if no pagination.
    :rtype: int
    """
    soup = BeautifulSoup(html, "html.parser")
    max_page = 1

    # Find pagination links
    page_links = soup.find_all("a", href=re.compile(r"\?page=\d+"))
    for link in page_links:
        href = link.get("href", "")
        match = re.search(r"\?page=(\d+)", href)
        if match:
            page_num = int(match.group(1))
            max_page = max(max_page, page_num)

    return max_page

def scrape_data(  # pylint: disable=too-many-locals
        base_url="https://www.thegradcafe.com/survey/",
        max_pages=None, delay=0.5,
        user_agent=robots_checker.DEFAULT_USER_AGENT,
        ignore_robots=False):
    """Scrape the GradCafe survey across multiple pages.

    :param base_url: Base URL for GradCafe survey pages.
    :type base_url: str
    :param max_pages: Maximum number of pages to scrape, or ``None``.
    :type max_pages: int or None
    :param delay: Delay between page fetches in seconds.
    :type delay: float
    :param user_agent: User-Agent header string for requests.
    :type user_agent: str
    :param ignore_robots: If ``True``, skip the robots.txt check.
    :type ignore_robots: bool
    :returns: A list of dictionaries containing applicant survey data.
    :rtype: list[dict]
    """
    all_results = []

    # Check robots.txt
    if not ignore_robots:
        print(f"Checking robots.txt for user-agent: {user_agent}",
              file=sys.stderr)
        robots = robots_checker.RobotsChecker(base_url, user_agent)

        if not robots.can_fetch(base_url):
            print(f"Error: robots.txt disallows access to "
                  f"{base_url} for {user_agent}",
                  file=sys.stderr)
            print("Use --ignore_robots option to ignore robots.txt "
                  "check (not recommended)", file=sys.stderr)
            return all_results

         # Use crawl-delay from robots.txt if specified
        robots_delay = robots.get_crawl_delay(delay)
        if robots_delay != delay:
            print(f"Using crawl delay from robots.txt: "
                  f"{robots_delay}s", file=sys.stderr)
            delay = robots_delay

    # Fetch first page to determine total pages
    html = fetch_page(base_url, user_agent)
    results = parse_survey(html)

    # Convert comment lists to strings before adding to results
    for result in results:
        if isinstance(result.get("comments"), list):
            result["comments"] = " ".join(result["comments"]).strip()

    all_results.extend(results)

    total_pages = get_max_pages(html)
    pages_to_fetch = (min(total_pages, max_pages)
                      if max_pages else total_pages)

    print(f"Found {total_pages} total pages. "
          f"Fetching {pages_to_fetch} pages...", file=sys.stderr)
    print(f"Page 1/{pages_to_fetch} - {len(results)} results",
          file=sys.stderr)

    # Fetch remaining pages
    for page_num in range(2, pages_to_fetch + 1):
        time.sleep(delay)  # being respectful to the server

        page_url = f"{base_url}?page={page_num}"

        # Check robots.txt for each page URL
        if not ignore_robots and not robots.can_fetch(page_url):
            print(f"Skipping page {page_num}: disallowed by robots.txt",
                  file=sys.stderr)
            continue

        try:
            html = fetch_page(page_url, user_agent)
            results = parse_survey(html)

            # Convert comment lists to strings
            for result in results:
                if isinstance(result.get("comments"), list):
                    result["comments"] = " ".join(
                        result["comments"]
                    ).strip()

            all_results.extend(results)
            print(f"Page {page_num}/{pages_to_fetch} - "
                  f"{len(results)} results", file=sys.stderr)
        except (OSError, ValueError, UnicodeDecodeError) as e:
            print(f"Error fetching page {page_num}: {e}",
                  file=sys.stderr)
            continue

    print(f"Total results: {len(all_results)}", file=sys.stderr)
    return all_results

def main():
    """Scrape the survey page and output results as JSON.

    Parses CLI arguments for page count, delay, output file, user agent,
    and robots.txt handling. Writes results to a file or stdout.
    """
    parser = argparse.ArgumentParser(
        description="Scrape the survey page and parse its content. "
                    "Return output as JSON"
    )
    parser.add_argument(
        "--pages", "-p",
        type=int,
        default=5,
        help="number of pages to scrape (default: 5, use 0 for all)"
    )
    parser.add_argument(
        "--delay", "-d",
        type=float,
        default=0.5,
        help="delay between pages in seconds (default: 0.5)"
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        help="output JSON file (default: stdout)"
    )
    parser.add_argument(
        "--user_agent", "-u",
        type=str,
        default=robots_checker.DEFAULT_USER_AGENT,
        help=("User agent string to use for requests "
              f"(default: {robots_checker.DEFAULT_USER_AGENT})")
    )
    parser.add_argument(
        "--ignore_robots",
        action="store_true",
        help="ignore robots.txt check (not recommended) (default: False)"
    )
    args = parser.parse_args()
    max_pages = args.pages if args.pages > 0 else None
    results = scrape_data(
        max_pages=max_pages,
        delay=args.delay,
        user_agent=args.user_agent,
        ignore_robots=args.ignore_robots
    )

    # Output as formatted JSON
    json_output = json.dumps(results, indent=2, ensure_ascii=False)
    if args.output:
        filename = os.path.basename(args.output)
        if not filename:
            print("Error: invalid output filename",
                  file=sys.stderr)
            return results
        safe_path = os.path.join(os.getcwd(), filename)
        with open(safe_path, "w", encoding="utf-8") as f:
            f.write(json_output)
        print(f"Results saved to {safe_path}", file=sys.stderr)
    else:
        print(json_output)

    return results


if __name__ == "__main__":
    main()
