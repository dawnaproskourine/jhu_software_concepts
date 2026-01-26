from urllib import parse, robotparser

agent = "Dawna/1.0"
url = "https://www.thegradcafe.com/"


# set up parser with website
parser = robotparser.RobotFileParser(url)
parser.set_url(parse.urljoin(url, 'robots.txt'))
parser.read()

paths = [
    "/",
    "/cgi-bin",
    "/admin",
    "/survey/?program=Computer+Science"
]

for path in paths:
    print(f"{parser.can_fetch(agent, path), path}")