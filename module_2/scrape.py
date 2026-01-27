from bs4 import BeautifulSoup
from urllib.request import urlopen, Request
import RobotsChecker
import re
import json

def fetch_page(url, user_agent = RobotsChecker.DEFAULT_USER_AGENT):
    """Fetch a page and parse its content"""
    headers = {'User-Agent': user_agent}
    request = Request(url, headers=headers)
    page = urlopen(request)
    html = page.read().decode("utf-8")
    return html

def parse():
    url = "https://www.thegradcafe.com/survey/"

    page = urlopen(url)
    html = page.read().decode("utf-8")
    soup = BeautifulSoup(html, "html.parser")

    tables = soup.find_all("table")
    header = None
    body = None
    for table in tables:
        for table_elem in table:
            if table_elem.name == "thead":
                header = parse_header(table_elem)
                continue
            if table_elem.name == "tbody":
                body = parse_body(header, table_elem)
                continue
            print(table_elem)
    return header, body

def parse_header(header):
    parsed_header = []
    for row in header:
        if row.name != "tr":
            continue
        for cell in row:
            if cell.name != "th":
                continue
            cell = cell.text.strip()
            parsed_header.append(cell)
        break
    return parsed_header


def extract_text(elem):
    return elem.text.strip() if hasattr(elem, "text") else ''

def parse_body(header, body):
    fields = []
    for row in body:
        texts = [extract_text(child) for child in row]
        for text in texts:
             if text:
                fields.append(text)
    return fields


if __name__ == "__main__":
    parse()
