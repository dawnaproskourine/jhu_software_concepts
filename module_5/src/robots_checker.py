"""
Robots.txt compliance checker for web scraping.

Fetches and parses a site's robots.txt to determine whether a given
URL may be crawled and what crawl delay to respect.
"""

import sys
from urllib import robotparser
from urllib.parse import urlparse

# Default user agent for the scraper
DEFAULT_USER_AGENT = "DawnaGradCafeScraper/1.0"
BASE_URL = "https://www.thegradcafe.com/"

class RobotsChecker:
    """Check robots.txt permissions for a given site and user agent.

    Parses the robots.txt file at the target site and provides methods
    to check crawl permissions and retrieve crawl delay directives.
    """

    def __init__(self, url, user_agent=DEFAULT_USER_AGENT):
        """Initialize the RobotsChecker by fetching and parsing robots.txt.

        :param url: The base URL of the site to check.
        :type url: str
        :param user_agent: The User-Agent string to check permissions for.
        :type user_agent: str
        """
        self.base_url = url
        self.user_agent = user_agent
        self.parser = robotparser.RobotFileParser()
        self.crawl_delay = None

        # Build robots.txt URL
        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

        try:
            self.parser.set_url(robots_url)
            self.parser.read()

            # check for crawl delay directive
            self.crawl_delay = self.parser.crawl_delay(user_agent)
        except Exception as e:  # pylint: disable=broad-exception-caught
            print(f"Warning: Could not fetch robots.txt: {e}",
                  file=sys.stderr)

    def can_fetch(self, url):
        """Check if the given URL can be crawled according to robots.txt.

        :param url: The URL to check.
        :type url: str
        :returns: ``True`` if crawling is allowed, ``False`` otherwise.
        :rtype: bool
        """
        return self.parser.can_fetch(self.user_agent, url)

    def get_crawl_delay(self, default=0.5):
        """Get the crawl delay from robots.txt, or use a default.

        :param default: Fallback delay in seconds if robots.txt has none.
        :type default: float
        :returns: The crawl delay in seconds.
        :rtype: float
        """
        return self.crawl_delay if self.crawl_delay is not None else default
