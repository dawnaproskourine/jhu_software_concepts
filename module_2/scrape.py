from bs4 import BeautifulSoup
from urllib.request import urlopen

def parse():
    url = "https://www.thegradcafe.com/survey/"

    page = urlopen(url)
    html = page.read().decode("utf-8")
    soup = BeautifulSoup(html, "html.parser")

    tables = soup.find_all("table")
    header = None
    for table in tables:
        for table_elem in table:
            if table_elem.name == "thead":
                header = parse_header(table_elem)
                continue
            if table_elem.name == "tbody":
                body = parse_body(header, table_elem)
                continue
            print(table_elem)

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

def parse_body(header, body):
    print(body)


if __name__ == "__main__":
    parse()
