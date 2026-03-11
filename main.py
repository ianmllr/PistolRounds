import subprocess
import sys
import streamlit as st
from utils import *
from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta
import os
import json

today = datetime.today()
date = today.strftime('%Y-%m-%d')
one_year_ago = (today - relativedelta(years=1)).strftime('%Y-%m-%d')

# HLTV updates rankings every monday
last_monday = today - timedelta(days=today.weekday())  # weekday(): Mon=0, Sun=6
ranking_day = last_monday.day
ranking_month = last_monday.strftime('%B').lower()
ranking_year = last_monday.year

teams = get_teams_from_file()
maps = ["Ancient", "Anubis", "Dust2", "Inferno", "Mirage", "Nuke", "Overpass", ] # active duty maps as of 11/3/26

st.title("CS2 pistol round bet helper")
st.markdown("Select two teams and the maps and find out if there's a good bet to be made.")
st.markdown(f"Please download the latest teams.html file from [here](https://www.hltv.org/ranking/teams/{ranking_year}/{ranking_month}/{ranking_day}) and place them in the 'data' folder to get started.")

if not teams or not maps:
    st.warning("No teams found. Please download teams.html")
else:
    sorted_teams = sorted(teams)
    selected_team_1 = st.selectbox("Team 1", sorted_teams, key="team1")
    selected_team_2 = st.selectbox("Team 2", sorted_teams, key="team2")

    number_of_maps_choice = st.radio("BO3 or BO1?", ["BO3", "BO1"])

    selected_map_1 = selected_map_2 = selected_map_3 = None

    if number_of_maps_choice == "BO3":
        selected_map_1 = st.selectbox("Map 1", maps, key="map1")
        selected_map_2 = st.selectbox("Map 2", maps, key="map2")
        selected_map_3 = st.selectbox("Map 3", maps, key="map3")
    elif number_of_maps_choice == "BO1":
        selected_map_1 = st.selectbox("Map", maps, key="map1_bo1")

    team_starting_ct = st.radio("Which team starts CT?", [selected_team_1, selected_team_2], key="starting_ct")

    chosen_maps = []
    if number_of_maps_choice == "BO3":
        chosen_maps = [f"&maps=de_{selected_map_1.lower()}", f"&maps=de_{selected_map_2.lower()}", f"&maps=de_{selected_map_3.lower()}"]
    elif number_of_maps_choice == "BO1":
        chosen_maps = [f"&maps=de_{selected_map_1.lower()}"]

    pistol_links = [
        {
            "ct": f"https://www.hltv.org/stats/teams/pistols?startDate={one_year_ago}&endDate={date}{m}&side=COUNTER_TERRORIST&rankingFilter=Top50",
            "t":  f"https://www.hltv.org/stats/teams/pistols?startDate={one_year_ago}&endDate={date}{m}&side=TERRORIST&rankingFilter=Top50",
        }
        for m in chosen_maps
    ]

    if "step" not in st.session_state:
        st.session_state.step = 0
    if "match_url" not in st.session_state:
        st.session_state.match_url = None
    if "odds" not in st.session_state:
        st.session_state.odds = None


    # Step 0 → Step 1: show links
    if st.button("Continue", key="btn_step0", disabled=st.session_state.step > 0):
        st.session_state.step = 1
        st.rerun()

    # Step 1: show links, then Continue to show tables
    if st.session_state.step >= 1:
        for i, links in enumerate(pistol_links, start=1):
            st.write(f"Map {i} — [CT side]({links['ct']}) | [T side]({links['t']})")
            st.write(f"Save them as pistols{i}_ct.html and pistols{i}_t.html in the data folder.")

        if st.button("Continue", key="btn_step1", disabled=st.session_state.step > 1):
            st.session_state.step = 2
            st.rerun()

    # Step 2: show tables, then Continue to search Oddset
    if st.session_state.step >= 2:
        if len(chosen_maps) == 0:
            st.warning("Please select at least one map.")
        else:
            for i in range(1, len(chosen_maps) + 1):
                ct_data = get_pistol_data(os.path.join(BASE_DIR, "data", f"pistols{i}_ct.html"), selected_team_1, selected_team_2)
                t_data  = get_pistol_data(os.path.join(BASE_DIR, "data", f"pistols{i}_t.html"),  selected_team_1, selected_team_2)
                st.write(f"### Map {i} — CT side")
                st.table(ct_data)
                st.write(f"### Map {i} — T side")
                st.table(t_data)

        if st.button("Continue", key="btn_step2", disabled=st.session_state.step > 2):
            st.session_state.step = 3
            st.rerun()


    if st.session_state.step == 3:
        with st.spinner("Opening browser and fetching odds from Danske Spil..."):
            proc = subprocess.run(
                [sys.executable, os.path.join(BASE_DIR, "run_playwright.py"),
                 selected_team_1, selected_team_2, str(len(chosen_maps))],
                capture_output=True, text=True, cwd=BASE_DIR
            )

        try:
            output = json.loads(proc.stdout.strip().splitlines()[-1])
            st.session_state.match_url = output.get("match_url")
            st.session_state.odds = output.get("odds", {})
        except Exception:
            st.session_state.match_url = None
            st.session_state.odds = {}

        st.session_state.step = 4

    if st.session_state.step >= 4:
        if st.session_state.match_url:
            st.success(f"Match found: {st.session_state.match_url}")
        else:
            st.warning(f"Match not found on Danske Spil for {selected_team_1} vs {selected_team_2}.")

        odds = st.session_state.odds or {}

        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            min_matches_ui = st.slider("Min matches (sample size guard)", 5, 50, 20, step=5)
        with col2:
            min_edge_ui = st.slider("Min edge to recommend a bet (%)", 0, 15, 3) / 100

        for i in range(1, len(chosen_maps) + 1):
            map_key = f"map{i}"
            map_data = odds.get(map_key, {})
            st.write(f"### Map {i}")

            ct_data = get_pistol_data(
                os.path.join(BASE_DIR, "data", f"pistols{i}_ct.html"),
                selected_team_1, selected_team_2,
            )
            t_data = get_pistol_data(
                os.path.join(BASE_DIR, "data", f"pistols{i}_t.html"),
                selected_team_1, selected_team_2,
            )

            for round_num in [1, 13]:
                round_data = map_data.get(f"round{round_num}", {})
                st.write(f"**Round {round_num}**")

                if round_data:
                    st.table([{"Team": t, "Odds": v} for t, v in round_data.items()])
                else:
                    st.write("*No odds found on Danske Spil for this round.*")

                analysis = analyse_pistol_round(
                    ct_data=ct_data,
                    t_data=t_data,
                    round_odds=round_data,
                    team_starting_ct=team_starting_ct,
                    team_a=selected_team_1,
                    team_b=selected_team_2,
                    round_num=round_num,
                    min_matches=min_matches_ui,
                )

                if analysis["skipped"]:
                    st.info(f"⚠️ Analysis skipped — {analysis['skip_reason']}")
                else:
                    rows = []
                    for side in ("CT", "T"):
                        team_ds     = analysis["ct_team"]   if side == "CT" else analysis["t_team"]
                        true_prob   = analysis["true_prob_ct"] if side == "CT" else analysis["true_prob_t"]
                        fair_prob   = analysis["fair_prob_ct"] if side == "CT" else analysis["fair_prob_t"]
                        ev          = analysis["ev_ct"]   if side == "CT" else analysis["ev_t"]
                        kelly       = analysis["kelly_ct"] if side == "CT" else analysis["kelly_t"]
                        wr          = analysis["ct_wr"]   if side == "CT" else analysis["t_wr"]
                        matches     = analysis["ct_matches"] if side == "CT" else analysis["t_matches"]
                        o           = analysis["odds_ct"] if side == "CT" else analysis["odds_t"]
                        edge        = true_prob - fair_prob
                        recommend   = ev > 0 and edge >= min_edge_ui
                        rows.append({
                            "Team (side)":          f"{team_ds} ({side})",
                            "Pistol WR":            f"{wr:.1%}",
                            "Matches":              matches,
                            "True prob":            f"{true_prob:.1%}",
                            "Fair prob (no vig)":   f"{fair_prob:.1%}",
                            "Edge":                 f"{edge:+.1%}",
                            "Odds":                 f"{o:.2f}",
                            "EV":                   f"{ev:+.3f}",
                            "Kelly %":              f"{kelly:.1%}",
                            "Bet?":                 "Yes" if recommend else "❌ No",
                        })

                    st.table(rows)

                    for row in rows:
                        if row["Bet?"] == "Yes":
                            st.success(
                                f"**Bet on {row['Team (side)']}** — "
                                f"EV: {row['EV']}  |  Edge: {row['Edge']}  |  Kelly: {row['Kelly %']}"
                            )
