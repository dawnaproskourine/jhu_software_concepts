"""
Author: Dawna Jones Proskourine
"""

import sys
from urllib import parse, robotparser
from urllib.parse import urlparse

# Default user agent for the scraper
DEFAULT_USER_AGENT = "DawnaGradCafeScraper/1.0"
base_url = "https://www.thegradcafe.com/"

class RobotsChecker:

    def __init__(self, base_url, user_agent=DEFAULT_USER_AGENT):
        """Initialize the RobotsChecker class. Check robots.txt file for more information."""
        self.base_url = base_url
        self.user_agent = user_agent
        self.parser = robotparser.RobotFileParser()
        self.crawl_delay = None

        # Build robots.txt URL
        parsed = urlparse(base_url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

        try:
            self.parser.set_url(robots_url)
            self.parser.read()

            # check for crawl delay directive
            self.crawl_delay = self.parser.crawl_delay(user_agent)
        except Exception as e:
            print(f"Warning: Could not fetch robots.txt: {e}", file=sys.stderr)

    def can_fetch(self, url):
        """Check if the given url can be crawled according to the robots.txt file."""
        return self.parser.can_fetch(self.user_agent, url)

    def get_crawl_delay(self, default=0.5):
        """Get the crawl delay from the robots.txt file. Or, default if not specified"""
        return self.crawl_delay if self.crawl_delay is not None else default

