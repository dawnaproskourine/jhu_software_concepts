import requests
from bs4 import BeautifulSoup

URL = "https://realpython.github.io/fake-jobs/"
page = requests.get(URL)

#print(page.text)

soup = BeautifulSoup(page.content, "html.parser")
results = soup.find(id="ResultsContainer")
#print(results.prettify())

job_cards = results.find_all("div", class_="card-content")
python_jobs = results.find_all("h2", string=lambda text: "python" in text.lower())
python_job_cards = [h2_element.parent.parent.parent for h2_element in python_jobs]
for job_card in python_job_cards:
    title_element = job_card.find("h2", class_="title")
    company_element = job_card.find("h3", class_="company")
    location_element = job_card.find("p", class_="location")
    link_url = job_card.find_all("a")[1]["href"]
    print(title_element.text.strip())
    print(company_element.text.strip())
    print(location_element.text.strip())
    print(f"Apply here: {link_url}\n")
    print()


