import os
import re
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEAMS = os.path.join(BASE_DIR, "data", "teams.html")
PISTOLS1 = os.path.join(BASE_DIR, "data", "pistols1.html")
PISTOLS2 = os.path.join(BASE_DIR, "data", "pistols2.html")
PISTOLS3 = os.path.join(BASE_DIR, "data", "pistols3.html")

MATCHES_URL = "https://danskespil.dk/oddset/sport/977/esports/matches?preselectedFilters=990"

# Known name mismatches between HLTV and Danske Spil
TEAM_NAME_MAP = {
    "The MongolZ": "MongolZ",
    "paiN Academy": "paiN Gaming Academy",
}
# Reverse: Danske Spil name to HLTV name (for pistol data lookup)
TEAM_NAME_MAP_REVERSE = {v: k for k, v in TEAM_NAME_MAP.items()}


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

    names = [TEAM_NAME_MAP.get(name, name) for name in names]
    return names[:50]


def get_pistol_data(file_path: str, team_name1: str, team_name2: str) -> list[dict]:
    if not os.path.exists(file_path):
        print(f"Data file not found: {file_path}")
        return []

    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        html = f.read()

    soup = BeautifulSoup(html, "html.parser")
    data = []
    # Reverse-map Danske Spil names → HLTV names so the file lookup works correctly
    hltv_name1 = TEAM_NAME_MAP_REVERSE.get(team_name1, team_name1)
    hltv_name2 = TEAM_NAME_MAP_REVERSE.get(team_name2, team_name2)
    targets = {hltv_name1.lower(), hltv_name2.lower()}

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


MIN_MATCHES = 20


# ── Maths helpers ─────────────────────────────────────────────────────────────

def parse_winrate(wr_str: str) -> float | None:
    """'55.3%' → 0.553.  Returns None if unparseable."""
    try:
        return float(str(wr_str).strip().rstrip("%")) / 100
    except (ValueError, AttributeError):
        return None


def parse_matches(m_str: str) -> int | None:
    """'22' → 22.  Returns None if unparseable."""
    try:
        return int(str(m_str).strip())
    except (ValueError, AttributeError):
        return None


def remove_vig(odds1: float, odds2: float) -> tuple[float, float]:
    """Strip bookmaker margin. Returns (fair_prob1, fair_prob2)."""
    imp1 = 1 / odds1
    imp2 = 1 / odds2
    total = imp1 + imp2
    return imp1 / total, imp2 / total


def calculate_ev(true_prob: float, odds: float) -> float:
    """EV = true_prob * (odds - 1) - (1 - true_prob)"""
    return true_prob * (odds - 1) - (1 - true_prob)


def calculate_kelly(true_prob: float, odds: float) -> float:
    """f* = (true_prob * odds - 1) / (odds - 1).  Clamped to 0 if negative."""
    val = (true_prob * odds - 1) / (odds - 1)
    return max(val, 0.0)


def analyse_pistol_round(
    ct_data: list[dict],
    t_data: list[dict],
    round_odds: dict,
    team_starting_ct: str,
    team_a: str,
    team_b: str,
    round_num: int,
    min_matches: int = MIN_MATCHES,
) -> dict:
    """
    Return a full EV analysis for one pistol round.

    Parameters
    ----------
    ct_data / t_data : from get_pistol_data (rows contain HLTV team names)
    round_odds       : {ds_team_name: odds_str}  — keys are Danske Spil names
    team_starting_ct : DS name of the team that starts on CT in round 1
    team_a / team_b  : DS names (= values from the Streamlit selectboxes)
    round_num        : 1 or 13
    """
    # Sides for this round
    if round_num == 1:
        ct_ds, t_ds = team_starting_ct, (team_b if team_starting_ct == team_a else team_a)
    else:  # round 13 — sides flip
        t_ds, ct_ds = team_starting_ct, (team_b if team_starting_ct == team_a else team_a)

    result: dict = {"round": round_num, "ct_team": ct_ds, "t_team": t_ds,
                    "skipped": False, "skip_reason": None}

    # Reverse-map DS → HLTV for row look-ups
    ct_hltv = TEAM_NAME_MAP_REVERSE.get(ct_ds, ct_ds)
    t_hltv  = TEAM_NAME_MAP_REVERSE.get(t_ds,  t_ds)

    def _find(rows: list[dict], hltv_name: str) -> dict | None:
        for r in rows:
            if r["team"].lower() == hltv_name.lower():
                return r
        return None

    ct_entry = _find(ct_data, ct_hltv)   # CT team's CT side stats
    t_entry  = _find(t_data,  t_hltv)    # T  team's T  side stats

    if not ct_entry:
        result.update(skipped=True, skip_reason=f"No CT data for {ct_ds}"); return result
    if not t_entry:
        result.update(skipped=True, skip_reason=f"No T data for {t_ds}");   return result

    ct_wr      = parse_winrate(ct_entry["winrate"])
    t_wr       = parse_winrate(t_entry["winrate"])
    ct_matches = parse_matches(ct_entry["matches"])
    t_matches  = parse_matches(t_entry["matches"])

    if ct_wr is None or t_wr is None:
        result.update(skipped=True, skip_reason="Could not parse winrate"); return result

    if ct_matches is not None and ct_matches < min_matches:
        result.update(skipped=True,
                      skip_reason=f"{ct_ds} has only {ct_matches} matches (min {min_matches})")
        return result
    if t_matches is not None and t_matches < min_matches:
        result.update(skipped=True,
                      skip_reason=f"{t_ds} has only {t_matches} matches (min {min_matches})")
        return result

    denom = ct_wr + t_wr
    if denom == 0:
        result.update(skipped=True, skip_reason="Both winrates are 0"); return result

    true_prob_ct = ct_wr / denom
    true_prob_t  = 1 - true_prob_ct

    result.update(ct_wr=ct_wr, t_wr=t_wr, ct_matches=ct_matches, t_matches=t_matches,
                  true_prob_ct=true_prob_ct, true_prob_t=true_prob_t)

    # Find odds (case-insensitive DS name match)
    def _odds(ds_name: str) -> float | None:
        for k, v in round_odds.items():
            if k.lower() == ds_name.lower():
                try:    return float(v)
                except: return None
        return None

    odds_ct = _odds(ct_ds)
    odds_t  = _odds(t_ds)

    if odds_ct is None or odds_t is None:
        result.update(skipped=True, skip_reason="Odds not found for one or both teams")
        return result

    fair_prob_ct, fair_prob_t = remove_vig(odds_ct, odds_t)

    result.update(
        odds_ct=odds_ct, odds_t=odds_t,
        fair_prob_ct=fair_prob_ct, fair_prob_t=fair_prob_t,
        ev_ct=calculate_ev(true_prob_ct, odds_ct),
        ev_t=calculate_ev(true_prob_t,  odds_t),
        kelly_ct=calculate_kelly(true_prob_ct, odds_ct),
        kelly_t=calculate_kelly(true_prob_t,  odds_t),
    )
    return result


def find_odds(team_name1: str, team_name2: str) -> dict:

    return {
        team_name1: "1.80",
        team_name2: "2.00",
    }


def find_and_click_match(team_name1: str, team_name2: str, url: str = MATCHES_URL) -> str | None:
    targets = {team_name1.lower(), team_name2.lower()}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        print(f"Navigating to {url}...")
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        _accept_cookies(page)
        page.wait_for_selector('[data-testid="selectable-event-wrapper-anchor"]', timeout=15000)

        # Scroll down repeatedly until no new cards load
        prev_count = 0
        while True:
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(1000)
            curr_count = page.locator('[data-testid="selectable-event-wrapper-anchor"]').count()
            if curr_count == prev_count:
                break
            prev_count = curr_count

        # Parse the fully rendered HTML with BeautifulSoup
        soup = BeautifulSoup(page.content(), "html.parser")

        # The <a> anchor is empty — team names are in a sibling div.
        # Search from the parent container (EventItemLink div) instead.
        event_name_divs = soup.select('[data-testid="event-card-name"]')

        match_url = None
        for event_name in event_name_divs:
            name_a_tag = event_name.select_one('[data-testid="event-card-team-name-a"]')
            name_b_tag = event_name.select_one('[data-testid="event-card-team-name-b"]')

            if not name_a_tag or not name_b_tag:
                continue

            name_a = name_a_tag.get_text(strip=True)
            name_b = name_b_tag.get_text(strip=True)

            if {name_a.lower(), name_b.lower()} == targets:
                container = event_name.parent.parent.parent.parent
                anchor = container.find('a', {'data-testid': 'selectable-event-wrapper-anchor'})
                href = anchor.get('href', '') if anchor else ''
                match_url = f"https://danskespil.dk{href}" if href.startswith("/") else href
                print(f"Match found: {name_a} vs {name_b} — {match_url}")
                page.goto(match_url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(2000)
                break
        else:
            print(f"No match found for '{team_name1}' vs '{team_name2}'.")

        browser.close()

    return match_url


def _accept_cookies(page) -> None:
    """Click the cookie accept button if present."""
    try:
        btn = page.get_by_role("button", name=re.compile(r"accepter", re.I)).first
        btn.wait_for(timeout=5000)
        btn.click()
        page.wait_for_timeout(800)
        print("Cookie banner accepted.")
    except Exception:
        pass  # No cookie banner found — continue


def _parse_odds_texts(texts: list) -> dict:
    """Parse odds from button text like 'Keyd Stars 1,67' or 'M80 1,80'.
    Match odds at the END of the string to avoid merging team digits with odds."""
    odds = {}
    for text in texts:
        # Match odds value at end of string (e.g. '1,67', '10,50')
        odds_match = re.search(r'(\d+,\d+)\s*$', text)
        if not odds_match:
            continue
        odds_value = f"{float(odds_match.group(1).replace(',', '.')):.2f}"
        team_name = text[:odds_match.start()].strip()
        if team_name:
            odds[team_name] = odds_value
    return odds


def get_pistol_odds(match_url: str, num_maps: int) -> dict:
    result = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        page.goto(match_url, wait_until="domcontentloaded", timeout=30000)
        _accept_cookies(page)
        page.wait_for_timeout(2000)

        for map_num in range(1, num_maps + 1):
            # Click the Map X tab
            page.get_by_text(f"Map {map_num}", exact=True).first.click()
            page.wait_for_timeout(1500)

            map_odds = {}
            for round_num in [1, 13]:
                section_title = f"Map {map_num} {round_num}. runde - Vinder"
                escaped_title = section_title.replace("'", "\\'")

                try:
                    # Use JS to find the section header and extract nearby button texts
                    button_texts = page.evaluate(f"""
                        () => {{
                            const all = Array.from(document.querySelectorAll('*'));
                            const header = all.find(el =>
                                el.children.length === 0 &&
                                el.textContent.trim() === '{escaped_title}'
                            );
                            if (!header) return [];

                            // Walk up until we find a container with >= 2 buttons
                            let container = header.parentElement;
                            for (let i = 0; i < 8; i++) {{
                                if (!container) break;
                                const btns = container.querySelectorAll('button, [role="button"]');
                                if (btns.length >= 2) {{
                                    return Array.from(btns).map(b => {{
                                        // Join child element texts with a space to avoid
                                        // digit team names (e.g. M80) merging with odds (1,80)
                                        const parts = Array.from(b.children)
                                            .map(c => c.innerText || c.textContent)
                                            .map(t => t.trim())
                                            .filter(t => t.length > 0);
                                        return parts.length > 0
                                            ? parts.join(' ')
                                            : b.textContent.trim();
                                    }});
                                }}
                                container = container.parentElement;
                            }}
                            return [];
                        }}
                    """)

                    map_odds[f"round{round_num}"] = _parse_odds_texts(button_texts)
                    print(f"  {section_title}: {map_odds[f'round{round_num}']}")

                except Exception as e:
                    print(f"Error extracting '{section_title}': {e}")
                    map_odds[f"round{round_num}"] = {}

            result[f"map{map_num}"] = map_odds

        browser.close()

    return result


