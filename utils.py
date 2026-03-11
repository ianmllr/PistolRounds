import os
from bs4 import BeautifulSoup

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEAMS = os.path.join(BASE_DIR, "data", "teams.html")
PISTOLS1 = os.path.join(BASE_DIR, "data", "pistols1.html")
PISTOLS2 = os.path.join(BASE_DIR, "data", "pistols2.html")
PISTOLS3 = os.path.join(BASE_DIR, "data", "pistols3.html")

def get_teams_from_file(file_path: str = TEAMS) -> list[str]:
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

def get_pistol_data(file_path: str, team_name1: str, team_name2: str) -> list[dict]:
    if not os.path.exists(file_path):
        print(f"Data file not found: {file_path}")
        return []

    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        html = f.read()

    soup = BeautifulSoup(html, "html.parser")
    data = []
    targets = {team_name1.lower(), team_name2.lower()}

    for row in soup.select("tr"):
        team_tag = row.select_one("td.factor-team")
        if not team_tag:
            continue

        team_name = team_tag.get_text(strip=True)
        if team_name.lower() not in targets:
            continue

        matches_tag = row.select_one("td.statsDetail")
        matches = matches_tag.get_text(strip=True) if matches_tag else "N/A"

        # Single selector returns first matching td in document order = pistol win %
        winrate_tag = row.select_one(
            "td.center.great, td.center.good, td.center.above_average, "
            "td.center.average, td.center.below_average, td.center.bad, "
            "td.center.abysmal, td.center.terrible"
        )
        winrate = winrate_tag.get_text(strip=True) if winrate_tag else "N/A"

        data.append({
            "team": team_name,
            "winrate": winrate,
            "matches": matches,
        })

    return data