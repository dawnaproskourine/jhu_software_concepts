# Description

1. Write a web scraper for Grad Cafe Links to an external site. data about recent applicants and parse applicant data:
   1. Confirm the robot.txt file permits scraping.
   2. Use urllib3 to request data from Grad Cafe.
   3. Use beautifulSoup/regex/string search methods to find admissions data.
   4. Clean the data using an LLM
   5. Structure the data as a clean, formatted JSON data object.
2. Submit associated deliverables on time and with the appropriate structure.

# Installation

```
pip install -r requirements.txt
```

# Execution and usage

```
python3 scrape.py --pages 2 --output applicant_data.json
```

# Used technology


* Python 3.14

# References
* https://realpython.com/python-web-scraping-practical-introduction/
* https://realpython.com/beautiful-soup-web-scraper-python/
