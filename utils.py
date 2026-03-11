import os
from bs4 import BeautifulSoup

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "data", "teams.html")

def get_teams_from_file(file_path: str = DATA_FILE) -> list[str]:
    if not os.path.exists(file_path):
        print(f"Data file not found: {file_path}")
        return []

    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        html = f.read()

    soup = BeautifulSoup(html, "html.parser")
    names = [el.get_text(strip=True) for el in soup.select("div.ranked-team.standard-box span.name")]

    if not names:
        print("No team names found in local data file.")
        return []

    return names[:50]
