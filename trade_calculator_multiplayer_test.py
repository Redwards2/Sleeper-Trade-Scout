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

# --------------------
# Trade Value Calculator
# --------------------
def calculate_trade_value(players_df, selected_names, top_qbs, qb_premium_setting):
    selected_rows = players_df[players_df["Player_Sleeper"].isin(selected_names)]
    total_ktc = selected_rows["KTC_Value"].sum()
    total_qb_premium = selected_rows.apply(
        lambda row: qb_premium_setting if row["Position"] == "QB" and row["Player_Sleeper"] in top_qbs else 0,
        axis=1
    ).sum()
    total_bonus = package_bonus(selected_rows["KTC_Value"].tolist())
    adjusted_total = total_ktc + total_bonus + total_qb_premium
    return selected_rows, total_ktc, total_qb_premium, total_bonus, adjusted_total

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

with st.sidebar:
    st.markdown("---")
    st.subheader("Trade Settings")
    tolerance = st.slider("Match Tolerance (%)", 1, 15, 5)
    qb_premium_setting = st.slider("QB Premium Bonus", 0, 1500, 300, step=25,
                                   help="Extra value added to QBs for trade calculations.")

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
            user_players = user_players.sort_values("Player_Sleeper")
            player_list = [f"{row['Player_Sleeper']} (KTC: {row['KTC_Value']})" for _, row in user_players.iterrows()]
            name_map = {f"{row['Player_Sleeper']} (KTC: {row['KTC_Value']})": row['Player_Sleeper'] for _, row in user_players.iterrows()}

            st.markdown("<h1 style='text-align:center; color:#4da6ff;'>Trade Suggestions (Based off KTC Values)</h1>", unsafe_allow_html=True)
            st.caption("Adding draft picks soon, IDP values coming at a later date as well")

            selected_names = []
            st.markdown("<h3>Select player(s) to trade away:</h3>", unsafe_allow_html=True)
            cols = st.columns(2)
            for idx, (_, row) in enumerate(user_players.iterrows()):
                label = f"{row['Player_Sleeper']} (KTC: {row['KTC_Value']})"
                if cols[idx % 2].checkbox(label, key=row['Player_Sleeper']):
                selected_names.append(row['Player_Sleeper'])

            if selected_names:
                # name_map mapping already provides correct names, selected_names is already correct list
                selected_rows, total_ktc, total_qb_premium, total_bonus, adjusted_total = calculate_trade_value(
                    df, selected_names, top_qbs, qb_premium_setting
                )
                owner = selected_rows.iloc[0]["Team_Owner"]

                st.markdown("<h3 style='text-align:center;'>Selected Player Package</h3>", unsafe_allow_html=True)
                st.markdown(f"<ul style='text-align:center; list-style-position: inside;'><li><strong>Total Raw KTC Value:</strong> {total_ktc}</li>", unsafe_allow_html=True)
                st.markdown(f"<li><strong>Package Bonus:</strong> +{total_bonus}</li>", unsafe_allow_html=True)
                st.markdown(f"<li><strong>QB Premium Total:</strong> +{total_qb_premium}</li>", unsafe_allow_html=True)
                st.markdown(f"<li><strong>Adjusted Trade Value:</strong> {adjusted_total}</li></ul>", unsafe_allow_html=True)

                selected_id = df[df["Player_Sleeper"] == selected_names[0]].iloc[0]["Sleeper_Player_ID"]
                headshot_url = f"https://sleepercdn.com/content/nfl/players/{selected_id}.jpg"
                st.markdown(f"<div style='text-align:center'><img src='{headshot_url}' width='120'/></div>", unsafe_allow_html=True)

    except Exception as e:
        st.error(f"⚠️ Something went wrong: {e}")
else:
    st.info("Enter your Sleeper username to get started.")
