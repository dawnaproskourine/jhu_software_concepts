

### Name: Dawna Jones Proskourine
### Hopkins ID: 2356B8
### Course: EN.605.256.82.SP26
### Module 2 - Web Scraping

# Approach

 scrape.py is a web scraper for https://www.thegradcafe.com/survey/, a site where graduate school applicants self-report
 admissions decisions. It collects structured data from the site's survey results table and outputs it as JSON.                                 
                                                                                                                                                                                                                                                                         
## High-level flow                                                                                                                                                                                                                                                        
                                                                                                                                                                                                                                                                         
  1. main() (line 290) parses CLI arguments (--pages, --delay, --output, --user_agent, --ignore_robots) and calls 
scrape_data(), then writes the results as formatted JSON to a file or stdout.                                                                          
  2. scrape_data() (line 208) orchestrates the multi-page crawl:                                                                                                                                                                                                         
    - Checks robots.txt via the RobotsChecker module to respect the site's crawling policies, including any crawl-delay directive.                                                                                                                                       
    - Fetches the first page to determine the total number of pages from pagination links (get_max_pages()).                                                                                                                                                             
    - Iterates through pages with a configurable delay between requests, collecting results from each.                                                                                                                                                                   
    - Converts the internal comments list on each row to a single joined string before returning.                                                                                                                                                                        
  3. fetch_page() (line 15) makes an HTTP request with a configurable User-Agent header and returns the decoded HTML.                                                                                                                                                    
                                                                                                                                                                                                                                                                         
## Parsing logic                                                                                                                                                                                                                                                          
                                                                                                                                                                                                                                                                         
  The HTML table has two kinds of rows:                                                                                                                                                                                                                                  
                                                                                                                                                                                                                                                                         
  - Main rows (5 cells) — parsed by parse_main_row() (line 60). Extracts:                                                                                                                                                                                                
    - program: program name + university combined into one string (e.g., "Physics, MIT")                                                                                                                                                                                 
    - Degree: normalized to "PhD", "Masters", or the raw text                                                                                                                                                                                                            
    - date_added: prefixed with "Added on "                                                                                                                                                                                                                              
    - status: the admission decision text                                                                                                                                                                                                                                
    - url: full link to the individual result page on thegradcafe.com                                                                                                                                                                                                    
    - Default empty-string values for GPA, GRE V, GRE AW, GRE Q, and GRE so every row always has these keys                                                                                                                                                              
  - Detail/comment rows (1 cell) — parsed by parse_detail_row() (line 112). These follow a main row and contain a mix of 
    structured data and free-text comments, separated by " | ". Each part is matched against patterns:                                              
    - Term: e.g., "Fall 2024" (regex match for season + year)                                                                                                                                                                                                            
    - Nationality: "International" or "American"                                                                                                                                                                                                                         
    - GPA: must match "GPA X.XX" format                                                                                                                                                                                                                                  
    - GRE scores: "GRE V...", "GRE AW...", "GRE Q...", or generic "GRE..."                                                                                                                                                                                               
    - Status updates: short strings containing keywords like accepted, rejected, interview, wait                                                                                                                                                                         
    - Anything that doesn't match a known pattern is collected as a comment                                                                                                                                                                                              
                                                                                                                                                                                                                                                                         
  The parser uses a current_result pattern: it accumulates detail rows onto the most recent main row, then appends the
  completed result when the next main row is encountered.                                                                                           
                                                                                                                                                                                                                                                                         
  ## Output format                                                                                                                                                                                                                                                          
                                                                                                                                                                                                                                                                         
  A JSON array of objects, each with keys like:                                                                                                                                                                                                                          
                                                                                                                                                                                                                                                                         
  {                                                                                                                                                                                                                                                                      
    "program": "Information Studies, McGill University",                                                                                                                                                                                                                 
    "Degree": "Masters",                                                                                                                                                                                                                                                 
    "date_added": "Added on March 31, 2024",                                                                                                                                                                                                                             
    "status": "Wait listed",                                                                                                                                                                                                                                             
    "url": "https://www.thegradcafe.com/result/935454",                                                                                                                                                                                                                  
    "GPA": "GPA 3.88",                                                                                                                                                                                                                                                   
    "GRE V": "",                                                                                                                                                                                                                                                         
    "GRE AW": "",                                                                                                                                                                                                                                                        
    "GRE Q": "",                                                                                                                                                                                                                                                         
    "GRE": "",                                                                                                                                                                                                                                                           
    "term": "Fall 2024",                                                                                                                                                                                                                                                 
    "US/International": "International",                                                                                                                                                                                                                                 
    "comments": "Some applicant comment text"                                                                                                                                                                                                                            
  }                                                                                                                                                                                                                                                                      
                                                                                                                                                                                                                                                                         
  GPA and GRE fields are always present; they're empty strings when the applicant didn't report them.   

The scraper handles three types of rows
1. Main rows with 5 cells: University, Program, Date, Status, Link
2. Detail rows in 1 cell: structured data like GPA, GRE scores, term, nationality
3. Comment rows in 1 cell: free form text that doesn't match structured patterns

## Features
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

# References
* https://realpython.com/python-web-scraping-practical-introduction/
* https://realpython.com/beautiful-soup-web-scraper-python/
* https://docs.python.org/3/tutorial/inputoutput.html
* https://scrapfly.io/blog/posts/python-requests-headers-guide
* https://www.crummy.com/software/BeautifulSoup/bs4/doc/
* https://docs.python.org/3/library/argparse.html
