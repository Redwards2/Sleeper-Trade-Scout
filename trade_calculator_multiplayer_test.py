
import streamlit as st
import pandas as pd
import requests
from itertools import combinations


# --------------------
# Package Bonus Function (for multi-player trade away)
# --------------------
def package_bonus(values):
    total = sum(values)
    num_players = len(values)
    
    if num_players == 1:
        if total >= 9000: return 3700
        elif total >= 8500: return 3400
        elif total >= 8000: return 3100
        elif total >= 7500: return 2850
        elif total >= 7000: return 2600
        elif total >= 6500: return 2300
        elif total >= 6000: return 2000
        elif total >= 5000: return 1650
        elif total >= 4000: return 1300
        elif total >= 3000: return 1000
        elif total >= 2000: return 700
        else: return 0
    else:
        penalty = max(0, (num_players - 1) * 400)
        if total >= 9000: base = 3200
        elif total >= 8000: base = 2700
        elif total >= 7000: base = 2200
        elif total >= 6000: base = 1800
        elif total >= 5000: base = 1300
        elif total >= 4000: base = 900
        elif total >= 3000: base = 600
        elif total >= 2000: base = 400
        else: base = 0
        return base - penalty

import streamlit as st
import pandas as pd
import requests
from itertools import combinations

# --------------------
# Sleeper League Loader with KTC Matching
# --------------------
def load_league_data(league_id, ktc_df):
    player_pool_url = "https://api.sleeper.app/v1/players/nfl"
    pool_response = requests.get(player_pool_url)
    player_pool = pool_response.json()

    users_url = f"https://api.sleeper.app/v1/league/{league_id}/users"
    rosters_url = f"https://api.sleeper.app/v1/league/{league_id}/rosters"
    users = requests.get(users_url).json()
    rosters = requests.get(rosters_url).json()

    user_map = {user['user_id']: user['display_name'] for user in users}
    data = []

    for roster in rosters:
        roster_id = roster["roster_id"]
        owner_id = roster["owner_id"]
        owner_name = user_map.get(owner_id, f"User {owner_id}")
        player_ids = roster.get("players", [])

        for pid in player_ids:
            player_data = player_pool.get(pid, {})
            full_name = player_data.get("full_name", pid)
            position = player_data.get("position", "")
            team = player_data.get("team", "")

            ktc_row = ktc_df[ktc_df["Player_Sleeper"].str.strip().str.lower() == full_name.lower()]
            ktc_value = int(ktc_row["KTC_Value"].iloc[0]) if not ktc_row.empty else 0

            data.append({
                "Sleeper_Player_ID": pid,
                "Player_Sleeper": full_name,
                "Position": position,
                "Team": team,
                "Team_Owner": owner_name,
                "Roster_ID": roster_id,
                "KTC_Value": ktc_value
            })

    return pd.DataFrame(data), player_pool

# --------------------
# Stud Bonus Function
# --------------------
def stud_bonus(value):
    if value >= 9000: return 3700
    elif value >= 8500: return 3400
    elif value >= 8000: return 3100
    elif value >= 7500: return 2850
    elif value >= 7000: return 2600
    elif value >= 6500: return 2300
    elif value >= 6000: return 2000
    elif value >= 5000: return 1650
    elif value >= 4000: return 1300
    elif value >= 3000: return 1000
    elif value >= 2000: return 700
    return 0

# --------------------
# Dud Bonus Function
# --------------------
def dud_bonus(value):
    if value <= 1000: return -800
    elif value <= 1500: return -600
    elif value <= 2000: return -400
    elif value <= 2500: return -250
    return 0

# --------------------
# Streamlit UI Setup
# --------------------
st.set_page_config(page_title="KTC Trade Suggest", layout="wide")
st.markdown("""
<style>
thead tr th, tbody tr td {
    text-align: center !important;
    vertical-align: middle !important;
}
</style>
""", unsafe_allow_html=True)

st.sidebar.header("Import Your League")
username = st.sidebar.text_input("Enter your Sleeper username").strip()
username_lower = username.lower()

league_id = None
league_options = {}
df = pd.DataFrame()

if username:
    try:
        user_info_url = f"https://api.sleeper.app/v1/user/{username}"
        user_response = requests.get(user_info_url, timeout=10)
        user_response.raise_for_status()
        user_id = user_response.json().get("user_id")

        leagues_url = f"https://api.sleeper.app/v1/user/{user_id}/leagues/nfl/2025"
        response = requests.get(leagues_url)
        response.raise_for_status()
        leagues = response.json()

        league_options = {league['name']: league['league_id'] for league in leagues}
        selected_league_name = st.sidebar.selectbox("Select a league", list(league_options.keys()))
        league_id = league_options[selected_league_name]

        ktc_df = pd.read_csv("ktc_values.csv", encoding="utf-8-sig")
        df, player_pool = load_league_data(league_id, ktc_df)

        if not df.empty:
            top_qbs = df[df["Position"] == "QB"].sort_values("KTC_Value", ascending=False).head(30)["Player_Sleeper"].tolist()

            user_players = df[df["Team_Owner"].str.lower() == username_lower]
            player_list = user_players["Player_Sleeper"].sort_values().unique()

            st.markdown("<h1 style='text-align:center; color:#4da6ff;'>Trade Suggestions (Based off KTC Values)</h1>", unsafe_allow_html=True)
            st.caption("Adding draft picks soon, IDP values coming at a later date as well")

            selected_player = st.selectbox("Select a player to trade away:", player_list)
            if selected_player:
                selected_id = df[df["Player_Sleeper"] == selected_player].iloc[0]["Sleeper_Player_ID"]
                headshot_url = f"https://sleepercdn.com/content/nfl/players/{selected_id}.jpg"
                st.markdown(f"<div style='text-align:center'><img src='{headshot_url}' width='120'/></div>", unsafe_allow_html=True)

            tolerance = st.slider("Match Tolerance (%)", 1, 15, 5)
            st.markdown("**QB Premium**")
            st.caption("How much does your league value QBs?")
            qb_premium_setting = st.slider("QB Premium Bonus", 0, 1500, 300, step=25)

            if selected_player:
                row = df[df["Player_Sleeper"] == selected_player].iloc[0]
                owner = row["Team_Owner"]
                base_value = row["KTC_Value"]
                bonus = stud_bonus(base_value)
                qb_premium = qb_premium_setting if row["Position"] == "QB" and selected_player in top_qbs else 0
                adjusted_value = base_value + bonus + qb_premium

                st.markdown("<h3 style='text-align:center;'>Selected Player Details</h3>", unsafe_allow_html=True)
                st.markdown(f"<ul style='text-align:center; list-style-position: inside;'><strong>Player:</strong> {selected_player}</li>", unsafe_allow_html=True)
                st.markdown(f"<ul style='text-align:center; list-style-position: inside;'><strong>Team Owner:</strong> {owner}</li>", unsafe_allow_html=True)
                st.markdown(f"<ul style='text-align:center; list-style-position: inside;'><strong>Raw KTC Value:</strong> {base_value}</li>", unsafe_allow_html=True)
                st.markdown(f"<ul style='text-align:center; list-style-position: inside;'><strong>Stud Bonus (2-for-1 only):</strong> +{bonus}</li>", unsafe_allow_html=True)
                st.markdown(f"<ul style='text-align:center; list-style-position: inside;'><strong>QB Premium:</strong> +{qb_premium if qb_premium else 0}</li>", unsafe_allow_html=True)
                st.markdown(f"<ul style='text-align:center; list-style-position: inside;'><li><strong>Adjusted 2-for-1 Value:</strong> {adjusted_value}</li></ul>", unsafe_allow_html=True)

                st.markdown("<h3 style='text-align:center;'>1-for-1 Trade Suggestions</h3>", unsafe_allow_html=True)
                one_low = int(base_value * (1 - tolerance / 100))
                one_high = int(base_value * (1 + tolerance / 100))

                one_for_one = df[
                    (df["KTC_Value"] >= one_low) &
                    (df["KTC_Value"] <= one_high) &
                    (df["Team_Owner"] != owner)
                ]

                one_names = set(one_for_one["Player_Sleeper"])

                if not one_for_one.empty:
                    one_for_one['Team'] = one_for_one['Team'].fillna('').apply(lambda abbr: f"<img src='https://a.espncdn.com/i/teamlogos/nfl/500/{abbr}.png' width='30'/> {abbr}" if abbr else abbr)
                    st.markdown(one_for_one[['Player_Sleeper', 'Position', 'Team', 'KTC_Value', 'Team_Owner']].to_html(escape=False, index=False), unsafe_allow_html=True)
                else:
                    st.markdown("No good 1-for-1 trade suggestions found.")

                st.markdown("<h3 style='text-align:center;'>2-for-1 Trade Suggestions</h3>", unsafe_allow_html=True)
                two_low = int(adjusted_value * (1 - tolerance / 100))
                two_high = int(adjusted_value * (1 + tolerance / 100))

                results = []
                for team_owner in df["Team_Owner"].unique():
                    if team_owner == owner:
                        continue
                    team_players = df[df["Team_Owner"] == team_owner]
                    combos = combinations(team_players.iterrows(), 2)
                    for (i1, p1), (i2, p2) in combos:
                        if p1["Player_Sleeper"] in one_names or p2["Player_Sleeper"] in one_names:
                            continue
                        if p1["KTC_Value"] > base_value or p2["KTC_Value"] > base_value:
                            continue
                        total = p1["KTC_Value"] + p2["KTC_Value"]
                        if p1["Position"] == "QB" and p1["Player_Sleeper"] in top_qbs: total += qb_premium_setting
                        if p2["Position"] == "QB" and p2["Player_Sleeper"] in top_qbs: total += qb_premium_setting
                        total += dud_bonus(p1["KTC_Value"]) + dud_bonus(p2["KTC_Value"])
                        if two_low <= total <= two_high:
                            results.append({
                                "Owner": team_owner,
                                "Player 1": f"{p1['Player_Sleeper']} (KTC: {p1['KTC_Value']})",
                                "Player 2": f"{p2['Player_Sleeper']} (KTC: {p2['KTC_Value']})",
                                "Total KTC": total
                            })

                all_names = sorted(set([row['Player 1'].split(' (KTC')[0] for row in results] + [row['Player 2'].split(' (KTC')[0] for row in results]))
                col1, col2 = st.columns([3, 1])
                with col1:
                    player_filter_name = st.selectbox("Filter 2-for-1 Trades by Player Name (Player 1 OR 2)", options=[""] + all_names, key="player_filter").strip().lower()
                with col2:
                    if st.button("Clear Filter"):
                        player_filter_name = ""

                two_low = int(adjusted_value * (1 - tolerance / 100))
                two_high = int(adjusted_value * (1 + tolerance / 100))

                results = []
                for team_owner in df["Team_Owner"].unique():
                    if team_owner == owner:
                        continue
                    team_players = df[df["Team_Owner"] == team_owner]
                    combos = combinations(team_players.iterrows(), 2)
                    for (i1, p1), (i2, p2) in combos:
                        if p1["Player_Sleeper"] in one_names or p2["Player_Sleeper"] in one_names:
                            continue
                        if p1["KTC_Value"] > base_value or p2["KTC_Value"] > base_value:
                            continue
                        total = p1["KTC_Value"] + p2["KTC_Value"]
                        if p1["Position"] == "QB" and p1["Player_Sleeper"] in top_qbs: total += qb_premium_setting
                        if p2["Position"] == "QB" and p2["Player_Sleeper"] in top_qbs: total += qb_premium_setting
                        total += dud_bonus(p1["KTC_Value"]) + dud_bonus(p2["KTC_Value"])
                        if two_low <= total <= two_high:
                            results.append({
                                "Owner": team_owner,
                                "Player 1": f"{p1['Player_Sleeper']} (KTC: {p1['KTC_Value']})",
                                "Player 2": f"{p2['Player_Sleeper']} (KTC: {p2['KTC_Value']})",
                                "Total KTC": total
                            })

                result_df = pd.DataFrame(results)
                if player_filter_name:
                    result_df = result_df[result_df.apply(lambda row: player_filter_name in row['Player 1'].lower() or player_filter_name in row['Player 2'].lower(), axis=1)]

                if not result_df.empty:
                    st.dataframe(result_df)
                else:
                    st.markdown("No good 2-for-1 trade suggestions found.")

    except Exception as e:
        st.error(f"⚠️ Something went wrong: {e}")
else:
    st.info("Enter your Sleeper username to get started.")

            selected_players = st.multiselect("Select player(s) to trade away:", options=player_list)

            if selected_players:
                selected_names = [name_map[p] for p in selected_players]
                selected_rows = df[df["Player_Sleeper"].isin(selected_names)]

                total_ktc = selected_rows["KTC_Value"].sum()
                total_qb_premium = selected_rows.apply(
                    lambda row: qb_premium_setting if row["Position"] == "QB" and row["Player_Sleeper"] in top_qbs else 0,
                    axis=1
                ).sum()
                total_bonus = package_bonus(selected_rows["KTC_Value"].tolist())
                adjusted_total = total_ktc + total_bonus + total_qb_premium
                owner = selected_rows.iloc[0]["Team_Owner"]

                st.markdown("<h3 style='text-align:center;'>Selected Player Package</h3>", unsafe_allow_html=True)
                st.markdown(f"<ul style='text-align:center; list-style-position: inside;'><li><strong>Total Raw KTC Value:</strong> {total_ktc}</li>", unsafe_allow_html=True)
                st.markdown(f"<li><strong>Package Bonus:</strong> +{total_bonus}</li>", unsafe_allow_html=True)
                st.markdown(f"<li><strong>QB Premium Total:</strong> +{total_qb_premium}</li>", unsafe_allow_html=True)
                st.markdown(f"<li><strong>Adjusted Trade Value:</strong> {adjusted_total}</li></ul>", unsafe_allow_html=True)

                # Keep using first player ID for display
                selected_id = df[df["Player_Sleeper"] == selected_names[0]].iloc[0]["Sleeper_Player_ID"]
                headshot_url = f"https://sleepercdn.com/content/nfl/players/{selected_id}.jpg"
                st.markdown(f"<div style='text-align:center'><img src='{headshot_url}' width='120'/></div>", unsafe_allow_html=True)

                headshot_url = f"https://sleepercdn.com/content/nfl/players/{selected_id}.jpg"
                st.markdown(f"<div style='text-align:center'><img src='{headshot_url}' width='120'/></div>", unsafe_allow_html=True)

            tolerance = st.slider("Match Tolerance (%)", 1, 15, 5)
            st.markdown("**QB Premium**")
            st.caption("How much does your league value QBs?")
            qb_premium_setting = st.slider("QB Premium Bonus", 0, 1500, 300, step=25)

            if selected_player:
                row = df[df["Player_Sleeper"] == selected_player].iloc[0]
                owner = row["Team_Owner"]
                base_value = row["KTC_Value"]
                bonus = stud_bonus(base_value)
                qb_premium = qb_premium_setting if row["Position"] == "QB" and selected_player in top_qbs else 0
                adjusted_value = base_value + bonus + qb_premium

                st.markdown("<h3 style='text-align:center;'>Selected Player Details</h3>", unsafe_allow_html=True)
                st.markdown(f"<ul style='text-align:center; list-style-position: inside;'><strong>Player:</strong> {selected_player}</li>", unsafe_allow_html=True)
                st.markdown(f"<ul style='text-align:center; list-style-position: inside;'><strong>Team Owner:</strong> {owner}</li>", unsafe_allow_html=True)
                st.markdown(f"<ul style='text-align:center; list-style-position: inside;'><strong>Raw KTC Value:</strong> {base_value}</li>", unsafe_allow_html=True)
                st.markdown(f"<ul style='text-align:center; list-style-position: inside;'><strong>Stud Bonus (2-for-1 only):</strong> +{bonus}</li>", unsafe_allow_html=True)
                st.markdown(f"<ul style='text-align:center; list-style-position: inside;'><strong>QB Premium:</strong> +{qb_premium if qb_premium else 0}</li>", unsafe_allow_html=True)
                st.markdown(f"<ul style='text-align:center; list-style-position: inside;'><li><strong>Adjusted 2-for-1 Value:</strong> {adjusted_value}</li></ul>", unsafe_allow_html=True)

                st.markdown("<h3 style='text-align:center;'>1-for-1 Trade Suggestions</h3>", unsafe_allow_html=True)
                one_low = int(base_value * (1 - tolerance / 100))
                one_high = int(base_value * (1 + tolerance / 100))

                one_for_one = df[
                    (df["KTC_Value"] >= one_low) &
                    (df["KTC_Value"] <= one_high) &
                    (df["Team_Owner"] != owner)
                ]

                one_names = set(one_for_one["Player_Sleeper"])

                if not one_for_one.empty:
                    one_for_one['Team'] = one_for_one['Team'].fillna('').apply(lambda abbr: f"<img src='https://a.espncdn.com/i/teamlogos/nfl/500/{abbr}.png' width='30'/> {abbr}" if abbr else abbr)
                    st.markdown(one_for_one[['Player_Sleeper', 'Position', 'Team', 'KTC_Value', 'Team_Owner']].to_html(escape=False, index=False), unsafe_allow_html=True)
                else:
                    st.markdown("No good 1-for-1 trade suggestions found.")

                st.markdown("<h3 style='text-align:center;'>2-for-1 Trade Suggestions</h3>", unsafe_allow_html=True)
                two_low = int(adjusted_value * (1 - tolerance / 100))
                two_high = int(adjusted_value * (1 + tolerance / 100))

                results = []
                for team_owner in df["Team_Owner"].unique():
                    if team_owner == owner:
                        continue
                    team_players = df[df["Team_Owner"] == team_owner]
                    combos = combinations(team_players.iterrows(), 2)
                    for (i1, p1), (i2, p2) in combos:
                        if p1["Player_Sleeper"] in one_names or p2["Player_Sleeper"] in one_names:
                            continue
                        if p1["KTC_Value"] > base_value or p2["KTC_Value"] > base_value:
                            continue
                        total = p1["KTC_Value"] + p2["KTC_Value"]
                        if p1["Position"] == "QB" and p1["Player_Sleeper"] in top_qbs: total += qb_premium_setting
                        if p2["Position"] == "QB" and p2["Player_Sleeper"] in top_qbs: total += qb_premium_setting
                        total += dud_bonus(p1["KTC_Value"]) + dud_bonus(p2["KTC_Value"])
                        if two_low <= total <= two_high:
                            results.append({
                                "Owner": team_owner,
                                "Player 1": f"{p1['Player_Sleeper']} (KTC: {p1['KTC_Value']})",
                                "Player 2": f"{p2['Player_Sleeper']} (KTC: {p2['KTC_Value']})",
                                "Total KTC": total
                            })

                all_names = sorted(set([row['Player 1'].split(' (KTC')[0] for row in results] + [row['Player 2'].split(' (KTC')[0] for row in results]))
                col1, col2 = st.columns([3, 1])
                with col1:
                    player_filter_name = st.selectbox("Filter 2-for-1 Trades by Player Name (Player 1 OR 2)", options=[""] + all_names, key="player_filter").strip().lower()
                with col2:
                    if st.button("Clear Filter"):
                        player_filter_name = ""

                two_low = int(adjusted_value * (1 - tolerance / 100))
                two_high = int(adjusted_value * (1 + tolerance / 100))

                results = []
                for team_owner in df["Team_Owner"].unique():
                    if team_owner == owner:
                        continue
                    team_players = df[df["Team_Owner"] == team_owner]
                    combos = combinations(team_players.iterrows(), 2)
                    for (i1, p1), (i2, p2) in combos:
                        if p1["Player_Sleeper"] in one_names or p2["Player_Sleeper"] in one_names:
                            continue
                        if p1["KTC_Value"] > base_value or p2["KTC_Value"] > base_value:
                            continue
                        total = p1["KTC_Value"] + p2["KTC_Value"]
                        if p1["Position"] == "QB" and p1["Player_Sleeper"] in top_qbs: total += qb_premium_setting
                        if p2["Position"] == "QB" and p2["Player_Sleeper"] in top_qbs: total += qb_premium_setting
                        total += dud_bonus(p1["KTC_Value"]) + dud_bonus(p2["KTC_Value"])
                        if two_low <= total <= two_high:
                            results.append({
                                "Owner": team_owner,
                                "Player 1": f"{p1['Player_Sleeper']} (KTC: {p1['KTC_Value']})",
                                "Player 2": f"{p2['Player_Sleeper']} (KTC: {p2['KTC_Value']})",
                                "Total KTC": total
                            })

                result_df = pd.DataFrame(results)
                if player_filter_name:
                    result_df = result_df[result_df.apply(lambda row: player_filter_name in row['Player 1'].lower() or player_filter_name in row['Player 2'].lower(), axis=1)]

                if not result_df.empty:
                    st.dataframe(result_df)
                else:
                    st.markdown("No good 2-for-1 trade suggestions found.")

    except Exception as e:
        st.error(f"⚠️ Something went wrong: {e}")
else:
    st.info("Enter your Sleeper username to get started.")
