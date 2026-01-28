# Description

1. Write a web scraper for Grad Cafe Links to an external site. data about recent applicants and parse applicant data:
   1. Confirm the robot.txt file permits scraping.
   2. Use urllib3 to request data from Grad Cafe.
   3. Use beautifulSoup/regex/string search methods to find admissions data.
   4. Clean the data using an LLM
   5. Structure the data as a clean, formatted JSON data object.
2. Submit associated deliverables on time and with the appropriate structure.

The scraper handles three types of rows
1. Main rows with 5 cells: University, Program, Date, Status, Link
2. Detail rows in 1 cell: structured data like GPA, GRE scores, term, nationality
3. Comment rows in 1 cell: free form text that doesn't match structured patterns

##Features
- Scrapes admission results including program, status, GPA, GRE scores and user comments
- Respects Robots.txt by default
- Configurable delay between page requests
- outputs data in JSON format
- scraps multiple pages depending on user input
- custom user agent support
- captures user comments from multiple rows




# Installation

```
pip install -r requirements.txt
```

# Execution and usage

```
python3 scrape.py --pages 20 --output applicant_data.json
```
### Command Line Options
| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--pages` | `-p` | Number of pages to scrape (0 for all pages) | 5 |
| `--delay` | `-d` | Delay between requests in seconds | 0.5 |
| `--output` | `-o` | Output JSON file path | stdout |
| `--user_agent` | `-u` | Custom user agent string | RobotsChecker default |
| `--ignore_robots` | | Ignore robots.txt (not recommended) | False |

# Used technology
- Python 3.14
- BeautifulSoup4
- RobotsChecker (custom module)
## Output Format

The scraper outputs JSON with the following structure:

```json
[
  {
    "program": "Computer Science, Stanford University",
    "Degree": "PhD",
    "date_added": "Added on December 23, 2025",
    "status": "Accepted on 15 Dec",
    "url": "https://www.thegradcafe.com/result/987654",
    "term": "Fall 2026",
    "US/International": "International",
    "GPA": "GPA 3.85",
    "GRE V": "GRE V 165",
    "GRE Q": "GRE Q 170",
    "GRE AW": "GRE AW 4.5",
    "comments": "Two years research experience. Published 3 papers. Interview was very friendly and lasted about 45 minutes."
  }
]
```


# References
* https://realpython.com/python-web-scraping-practical-introduction/
* https://realpython.com/beautiful-soup-web-scraper-python/
