"""
Helper script called by main.py via subprocess to run Playwright
outside of Streamlit's event loop. Outputs JSON with match URL and odds.
Usage: python run_playwright.py "Team 1" "Team 2" <num_maps>
"""
import sys
import json
from utils import find_and_click_match, get_pistol_odds

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python run_playwright.py <team1> <team2> <num_maps>")
        sys.exit(1)

    team1 = sys.argv[1]
    team2 = sys.argv[2]
    num_maps = int(sys.argv[3])

    match_url = find_and_click_match(team1, team2)
    if not match_url:
        print(json.dumps({"error": f"Match not found for {team1} vs {team2}"}))
        sys.exit(0)

    odds = get_pistol_odds(match_url, num_maps)

    print(json.dumps({"match_url": match_url, "odds": odds}))
