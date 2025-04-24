import streamlit as st
import pandas as pd
import requests
from itertools import combinations

# ✅ MUST be first Streamlit call
# Removed duplicate st.set_page_config to fix Streamlit error

# --------------------
# Custom CSS Styling
# --------------------
st.markdown("""
<style>
/* Title Styling */
#main-title {
    text-align: center;
    font-size: 42px;
    font-weight: 700;
    margin-bottom: 0.5em;
    border-bottom: 3px solid #f63366;
    padding-bottom: 10px;
}

/* Section Spacing */
h3 {
    margin-top: 40px;
}

/* Sticky Sidebar Header */
section[data-testid="stSidebar"] h1 {
    position: sticky;
    top: 0;
    background-color: white;
    padding-top: 10px;
    padding-bottom: 10px;
    z-index: 1;
    border-bottom: 1px solid #ddd;
}

/* Table Styling */
thead tr th, tbody tr td {
    text-align: center !important;
    vertical-align: middle !important;
}

/* Light Background on Trade Suggestions */
[data-testid="stExpander"] > div {
    background-color: #f9f9f9;
    border-radius: 10px;
    padding: 1rem;
    margin-top: 10px;
}

/* Player Image Row Layout */
.player-row {
    display: flex;
    flex-wrap: wrap;
    justify-content: center;
    gap: 15px;
    margin-top: 20px;
}
.player-block {
    text-align: center;
}
</style>
""", unsafe_allow_html=True)

# --------------------
# App Title
# --------------------
st.markdown("""
<div id='main-title'>Sleeper Trade Scout</div>
""", unsafe_allow_html=True)

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
        if total >= 9000: base = 3500
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
# Dud Bonus Function
# --------------------
def dud_bonus(value):
    if value <= 1000: return -800
    elif value <= 1500: return -600
    elif value <= 2000: return -400
    elif value <= 2500: return -250
    return 0

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
    total_bonus = package_bonus(selected_rows["KTC_Value"].tolist()) if len(selected_names) == 1 else 0
    adjusted_total = total_ktc + total_qb_premium  # for 1-for-1 use only
    return selected_rows, total_ktc, total_qb_premium, total_bonus, adjusted_total

# --------------------
# Sleeper League Loader with KTC Matching
# --------------------
# (rest of original code continues here)

# --------------------
# Trade History Helpers
# --------------------
def get_all_trades_from_league(league_id):
    """
    Recursively pulls all trades from the given league and its previous seasons.
    Returns a list of trade transactions.
    """
    all_trades = []
    current_league_id = league_id
    visited = set()

    while current_league_id and current_league_id not in visited:
        visited.add(current_league_id)

        for week in range(0, 19):
            url = f"https://api.sleeper.app/v1/league/{current_league_id}/transactions/{week}"
            response = requests.get(url)
            if response.status_code == 200:
                transactions = response.json()
                trades = [t for t in transactions if t.get("type") == "trade"]
                all_trades.extend(trades)

        league_info = requests.get(f"https://api.sleeper.app/v1/league/{current_league_id}")
        if league_info.status_code == 200:
            current_league_id = league_info.json().get("previous_league_id")
        else:
            break

    return all_trades

def filter_trades_for_player(trades, player_name, player_pool):
    """
    Filters a list of trades to return only those that involve the given player.
    """
    filtered = []
    for trade in trades:
        added = trade.get("adds", {})
        dropped = trade.get("drops", {})
        all_players_involved = list(added.keys()) + list(dropped.keys())
        for player_id in all_players_involved:
            sleeper_name = player_pool.get(player_id, {}).get("full_name", "")
            if sleeper_name.lower() == player_name.lower():
                filtered.append(trade)
                break
    return filtered

# START: Side-by-side player images block example (to insert into your trade UI logic)
st.markdown("<div class='player-row'>", unsafe_allow_html=True)
for name in selected_names:
    selected_id = df[df["Player_Sleeper"] == name].iloc[0]["Sleeper_Player_ID"]
    headshot_url = f"https://sleepercdn.com/content/nfl/players/{selected_id}.jpg"
    st.markdown(
        f"""<div class='player-block'>
                <img src='{headshot_url}' width='120'/><br><small>{name}</small>
            </div>""",
        unsafe_allow_html=True
    )
st.markdown("</div>", unsafe_allow_html=True)
# END

                # START: Trade history viewer
                if st.button("Show Trade History"):
                    with st.spinner("Loading trade history..."):
                        all_trades = get_all_trades_from_league(league_id)
                        for name in selected_names:
                            player_trades = filter_trades_for_player(all_trades, name, player_pool)
                            st.subheader(f"Trade History for {name} ({len(player_trades)} found)")
                            if player_trades:
                                for trade in player_trades:
                                    rosters_involved = trade.get("roster_ids", [])
                                    st.markdown(f"- Week {trade.get('week', '?')} • Rosters: {rosters_involved}")
                            else:
                                st.write("No trades found involving this player.")
                # END: Trade history viewer
