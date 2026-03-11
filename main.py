import streamlit as st
from utils import *
from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta

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
        f"https://www.hltv.org/stats/teams/pistols?startDate={one_year_ago}&endDate={date}{m}&rankingFilter=Top50"
        for m in chosen_maps
    ]

    # st.write(f"**{selected_team_1}** vs **{selected_team_2}** — {number_of_maps_choice}")

    if st.button("Run"):
        for i, link in enumerate(pistol_links, start=1):
            st.write(f"Please go to [this link]({link}) and save the page as 'pistols{i}.html' in the 'data' folder.")
