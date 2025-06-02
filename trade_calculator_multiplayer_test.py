import streamlit as st
import pandas as pd
import requests
from itertools import combinations

DEFAULT_SCORING = {
    "rec": 1.0,              # PPR
    "bonus_rec_te": 0.0,     # TE Premium
    "pass_td": 4.0,          # Passing TDs
    "rush_td": 6.0,          # Rushing TDs
    "rec_td": 6.0,           # Receiving TDs
    "fum": -2.0,             # Fumble lost
    "pass_yd": 0.04,         # 1 per 25
    "rush_yd": 0.1,          # 1 per 10
    "rec_yd": 0.1,           # 1 per 10
    "int": -2.0,             # Interception
    # Add more as needed for your league type!
}

OMIT_SCORING_KEYS = {
    "sack",
    "fgm_40_49",
    "pts_allow_0",
    "pass_2pt",
    "st_td",
    "fgm_30_39",
    "xpmiss",
    "rec_2pt",
    "st_fum_rec",
    "fgmiss",
    "ff",
    "pts_allow_14_20",
    "fgm_0_19",
    "int",
    "def_st_fum_rec",
    "fum_lost",
    "pts_allow_1_6",
    "fgm_20_29",
    "pts_allow_21_27",
    "xpm",
    "rush_2pt",
    "fum_rec",
    "bonus_rec_yd_200",
    "def_st_td",
    "fgm_50p",
    "def_td",
    "safe",
    "blk_kick",
    "fum",
    "pts_allow_28_34",
    "pts_allow_35p",
    "fum_rec_td",
    "def_st_ff",
    "pts_allow_7_13",
    "st_ff"
}

# ---- Pretty labels for only the keys you want to show ----
PRETTY_SCORING_LABELS = {
    "rec": "Points Per Reception (PPR)",
    "bonus_rec_te": "TE Reception Bonus (TEP)",
    "pass_td": "Passing TD",
    "rush_td": "Rushing TD",
    "rec_td": "Receiving TD",
    "fum": "Fumble Lost",
    "fum_lost": "Fumbles Lost",
    "pass_yd": "Passing Yards",
    "rush_yd": "Rushing Yards",
    "rec_yd": "Receiving Yards",
    "bonus_rec_yd_200": "200+ Receiving Yards Bonus",
    "pass_2pt": "2pt Conversion (Pass)",
    "rec_2pt": "2pt Conversion (Reception)",
    "rush_2pt": "2pt Conversion (Rush)",
    # Add more as needed!
}

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
        elif total >= 8500: return 3200
        elif total >= 8000: return 2900
        elif total >= 7500: return 2550
        elif total >= 7000: return 2300
        elif total >= 6500: return 2100
        elif total >= 6000: return 1850
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

        print("✅ running edited file")  # Add this temporarily
        for pid in player_ids:
            if pid in player_pool:
                player_data = player_pool[pid]
                full_name = player_data.get("full_name", pid)
                position = player_data.get("position", "")
                team = player_data.get("team", "")
            elif isinstance(pid, str) and pid.startswith("rookie_"):
                full_name = format_pick_id(pid)
                position = "PICK"
                team = ""
            else:
                continue  # Unknown entry; skip
        
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

    # Inject dummy player data for rookie picks
    for pid in set(sum([roster.get("players", []) for roster in rosters], [])):
        if isinstance(pid, str) and pid.startswith("rookie_"):
            player_pool[pid] = {
                "full_name": format_pick_id(pid),
                "position": "PICK",
                "team": ""
            }

    # Fetch previous league standings to assign rookie picks
    league_info = requests.get(f"https://api.sleeper.app/v1/league/{league_id}").json()
    prev_league_id = league_info.get("previous_league_id")

    pick_order = []
    if prev_league_id:
        prev_rosters = requests.get(f"https://api.sleeper.app/v1/league/{prev_league_id}/rosters").json()
        standings = sorted(prev_rosters, key=lambda x: x.get("settings", {}).get("final_standing", 999))
        pick_order = [r["roster_id"] for r in standings if r.get("settings", {}).get("final_standing")]

    # Assign 2025 1st round picks based on standings
    for idx, roster_id in enumerate(reversed(pick_order)):  # Champion gets 1.12, last gets 1.01
        pick_number = idx + 1
        pick_name = f"2025 Pick 1.{str(pick_number).zfill(2)}"
        pick_id = f"2025_pick_1_{str(pick_number).zfill(2)}"
        owner_name = user_map.get(rosters[roster_id-1]['owner_id'], f"User {roster_id}")
        data.append({
            "Sleeper_Player_ID": pick_id,
            "Player_Sleeper": pick_name,
            "Position": "PICK",
            "Team": "",
            "Team_Owner": owner_name,
            "Roster_ID": roster_id,
            "KTC_Value": 0
        })

    return pd.DataFrame(data), player_pool

# --------------------
# Streamlit UI Setup
# --------------------
st.sidebar.header("Import Your League")
username = st.sidebar.text_input("Enter your Sleeper username").strip()
username_lower = username.lower()

with st.sidebar:
    st.markdown("---")
    st.subheader("Trade Settings")
    tolerance = st.slider("Match Tolerance (%)", 1, 15, 5)
    qb_premium_setting = st.slider("QB Premium Bonus", 0, 1500, 750, step=50,
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
        selected_league_name = st.sidebar.selectbox("Select a League", list(league_options.keys()))
        league_id = league_options[selected_league_name]

        # Find the selected league's info object
        league_info = requests.get(f"https://api.sleeper.app/v1/league/{league_id}").json()

        # Number of Teams
        num_teams = league_info.get("total_rosters", "?")
        
        # Dynasty or Redraft, check both settings and name
        settings_type = league_info.get("settings", {}).get("type", None)
        if str(settings_type).lower() == "dynasty" or str(settings_type) == "2":
            league_type = "Dynasty"
        elif "dynasty" in league_info.get('name', '').lower():
            league_type = "Dynasty"
        else:
            league_type = "Redraft"
        # Best Ball or Lineup
        if league_info.get("settings", {}).get("best_ball", 0) == 1:
            format_type = "Best Ball"
        else:
            format_type = "Lineup"

        # Get the roster positions list (starting lineup)
        positions = league_info.get("roster_positions", [])
        
        # Only count spots before first bench slot for starters
        bench_tags = {"BN", "BE", "IR", "TAXI"}
        try:
            first_bench_index = next(i for i, pos in enumerate(positions) if pos in bench_tags)
            starting_lineup = positions[:first_bench_index]
        except StopIteration:
            starting_lineup = positions
        
        # QB Format
        if "QB" in starting_lineup and "SUPER_FLEX" in starting_lineup:
            qb_format = "Superflex"
        elif starting_lineup.count("QB") > 1:
            qb_format = "2QB"
        else:
            qb_format = "1QB"
        
        # Start X (number of starting spots)
        start_x = len(starting_lineup)
        
       # Scoring settings (PPR and TEP)
        scoring = league_info.get("scoring_settings", {})
        rec = float(scoring.get("rec", 1.0))
        rec_te = float(scoring.get("bonus_rec_te", 0))
        
        # PPR label
        if rec == 1.0:
            ppr_type = "PPR"
        elif rec == 0.5:
            ppr_type = "Half PPR"
        else:
            ppr_type = f"{rec:.2f} PPR".rstrip('0').rstrip('.')
        
        # TEP label (always display)
        tep_str = f"{rec_te:.2f} TEP".rstrip('0').rstrip('.')
        
        # Build and show description
        league_desc = f"{num_teams} Team {league_type} {qb_format} {ppr_type} {tep_str} {format_type} Start {start_x}"
        st.markdown(f"<div style='font-size:20px; font-weight:600; color:#4da6ff'>{league_desc}</div>", unsafe_allow_html=True)
        # Show league_desc in sidebar
        st.sidebar.markdown(f"<div style='font-size:16px; font-weight:600; color:#4da6ff'>{league_desc}</div>", unsafe_allow_html=True)
        
        # Sidebar: List custom scoring settings
        non_default_settings = []
        for k, v in scoring.items():
            if k in OMIT_SCORING_KEYS:
                continue  # Skip any omitted keys
            default_val = DEFAULT_SCORING.get(k)
            try:
                if default_val is None or float(v) != float(default_val):
                    non_default_settings.append((k, v))
            except Exception:
                if default_val is None or v != default_val:
                    non_default_settings.append((k, v))
        
        if non_default_settings:
            st.sidebar.markdown("**Custom Scoring Settings:**")
            for k, v in non_default_settings:
                pretty_k = PRETTY_SCORING_LABELS.get(k, k.replace("_", " ").title())
                st.sidebar.markdown(f"<span style='color: #39d353; font-weight: bold'>{pretty_k}: {v}</span>", unsafe_allow_html=True)

        ktc_df = pd.read_csv("ktc_values.csv", encoding="utf-8-sig")
        df, player_pool = load_league_data(league_id, ktc_df)

        if not df.empty:
            top_qbs = df[df["Position"] == "QB"].sort_values("KTC_Value", ascending=False).head(30)["Player_Sleeper"].tolist()

            # Sort players by KTC descending
            user_players = df[df["Team_Owner"].str.lower() == username_lower].sort_values("KTC_Value", ascending=False)
            selected_names = []
            
            st.markdown("<h3 style='text-align:center;'>Select player(s) to trade away:</h3>", unsafe_allow_html=True)
            
            positions = ['QB', 'RB', 'WR', 'TE', 'PICK']
            display_map = {'QB': 'QB', 'RB': 'RB', 'WR': 'WR', 'TE': 'TE', 'PICK': 'Draft Picks'}
            position_columns = st.columns(len(positions))
            selected_names = []  # 👈 this is now used directly downstream
            
            for idx, pos in enumerate(positions):
                with position_columns[idx]:
                    st.markdown(f"**{display_map[pos]}**")
                    pos_players = user_players[user_players["Position"] == pos]
            
                    for _, row in pos_players.iterrows():
                        key = f"cb_{row['Sleeper_Player_ID']}"
                        name = row['Player_Sleeper']
                        ktc = row['KTC_Value']
            
                        # Label styling
                        label_html = f"<strong>{name}</strong><br><small>(KTC: {ktc})</small>"
            
                        with st.container():
                            col_cb, col_lbl = st.columns([1, 4])
                            with col_cb:
                                checked = st.checkbox(" ", key=key)
                            with col_lbl:
                                st.markdown(label_html, unsafe_allow_html=True)
            
                            if checked:
                                selected_names.append(name)  # 👈 now tied to the actual trade logic

            if selected_names:
                selected_rows, total_ktc, total_qb_premium, total_bonus, adjusted_total = calculate_trade_value(
                    df, selected_names, top_qbs, qb_premium_setting
                )
                owner = selected_rows.iloc[0]["Team_Owner"]

                st.markdown("<h3 style='text-align:center;'>Selected Player Package</h3>", unsafe_allow_html=True)
                st.markdown(f"<ul style='text-align:center; list-style-position: inside;'><strong>Total Raw KTC Value:</strong> {total_ktc}</li>", unsafe_allow_html=True)
                st.markdown(f"<ul style='text-align:center; list-style-position: inside;'><strong>Package Bonus:</strong> +{total_bonus}</li>", unsafe_allow_html=True)
                st.markdown(f"<ul style='text-align:center; list-style-position: inside;'><strong>QB Premium Total:</strong> +{total_qb_premium}</li>", unsafe_allow_html=True)
                st.markdown(f"<ul style='text-align:center; list-style-position: inside;'><strong>Adjusted Trade Value:</strong> {adjusted_total}</li></ul>", unsafe_allow_html=True)

                try:
                    with st.expander(f"📈 {len(selected_names)}-for-1 Trade Suggestions"):
                        one_low = int(adjusted_total * (1 - tolerance / 100))
                        one_high = int(adjusted_total * (1 + tolerance / 100))

                        one_for_one = df[
                           ((df["KTC_Value"] + df.apply(
                                lambda row: package_bonus([row["KTC_Value"]]) if len(selected_names) > 1 else 0, axis=1
                            )) >= one_low) &
                            ((df["KTC_Value"] + df.apply(
                              lambda row: package_bonus([row["KTC_Value"]]) if len(selected_names) > 1 else 0, axis=1
                            )) <= one_high) &
                            (df["Team_Owner"] != owner)
                       ][["Player_Sleeper", "Position", "Team", "KTC_Value", "Team_Owner"]]

                        if not one_for_one.empty:
                            st.dataframe(one_for_one.sort_values("KTC_Value", ascending=False).reset_index(drop=True))
                        else:
                            st.write("No 1-for-1 trades found in that range.")

                    with st.expander(f"👥 {len(selected_names)}-for-2 Trade Suggestions"):
                        # START: Corrected 1-for-2 package bonus calculation
                        your_side_total = total_ktc + package_bonus(selected_rows["KTC_Value"].tolist())
                        two_low = int(your_side_total * (1 - tolerance / 100))
                        two_high = int(your_side_total * (1 + tolerance / 100))
                        # END


                        results = []
                        other_teams = df[df["Team_Owner"] != owner]["Team_Owner"].unique()

                        for team_owner in other_teams:
                            team_players = df[df["Team_Owner"] == team_owner]
                            combos = combinations(team_players.iterrows(), 2)
                            for (i1, p1), (i2, p2) in combos:
                              # 🚫 Skip if either player alone has higher raw KTC than your selected package
                              if p1["KTC_Value"] > total_ktc or p2["KTC_Value"] > total_ktc:
                                  continue

                              value = p1["KTC_Value"] + p2["KTC_Value"]
                              if p1["Position"] == "QB" and p1["Player_Sleeper"] in top_qbs:
                                  value += qb_premium_setting
                              if p2["Position"] == "QB" and p2["Player_Sleeper"] in top_qbs:
                                  value += qb_premium_setting
                              # 🚫 No package bonus added to 2-for-1 side
                              if two_low <= value <= two_high:
                                  results.append({
                                      "Team_Owner": team_owner,
                                      "Player 1": f"{p1['Player_Sleeper']} (KTC: {p1['KTC_Value']})",
                                      "Player 2": f"{p2['Player_Sleeper']} (KTC: {p2['KTC_Value']})",
                                     "Total Value": value
                                  })


                        if results:
                            st.dataframe(pd.DataFrame(results).sort_values("Total Value", ascending=False).reset_index(drop=True))
                        else:
                            st.write("No 2-for-1 trades found in that range.")
                except Exception as trade_error:
                    st.error(f"⚠️ Trade suggestion error: {trade_error}")

    except Exception as e:
        st.error(f"⚠️ Something went wrong: {e}")
else:
    st.info("Enter your Sleeper username to get started.")

# --------------------
# Inject rookie picks into player_pool once function is available
if 'league_id' in locals():
    try:
        all_trades_preview = get_all_trades_from_league(league_id)
        all_ids_preview = set()
        for trade in all_trades_preview:
            all_ids_preview.update((trade.get("adds") or {}).keys())
            all_ids_preview.update((trade.get("drops") or {}).keys())
        for pid in all_ids_preview:
            if isinstance(pid, str) and pid.startswith("rookie_") and pid not in player_pool:
                player_pool[pid] = {
                    "full_name": format_pick_id(pid),
                    "position": "PICK",
                    "team": ""
                }
    except:
        pass

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

        league_info = requests.get(f"https://api.sleeper.app/v1/league/{current_league_id}")
        if league_info.status_code == 200:
            season = league_info.json().get("season")
        else:
            break

        for week in range(0, 19):
            url = f"https://api.sleeper.app/v1/league/{current_league_id}/transactions/{week}"
            response = requests.get(url)
            if response.status_code == 200:
                transactions = response.json()
                trades = [
                    dict(t, week=week, season=season)
                    for t in transactions if t.get("type") == "trade"
                ]
                all_trades.extend(trades)

        if league_info.status_code == 200:
            current_league_id = league_info.json().get("previous_league_id")
        else:
            break

    all_ids = set()
    for trade in all_trades:
        all_ids.update((trade.get("adds") or {}).keys())
        all_ids.update((trade.get("drops") or {}).keys())

    for pid in all_ids:
        if isinstance(pid, str) and pid.startswith("rookie_") and pid not in player_pool:
            player_pool[pid] = {
                "full_name": format_pick_id(pid),
                "position": "PICK",
                "team": ""
            }

    return all_trades

# --------------------
# Pick formatter for rough rookie picks
# --------------------
def ordinal(n):
    return "%d%s" % (n, "tsnrhtdd"[(n//10%10!=1)*(n%10<4)*n%10::4])

# --------------------
# Pick formatter for rookie picks
# --------------------
def format_pick_id(pid):
    if pid.startswith("rookie_"):
        parts = pid.split("_")  # example: rookie_1_04
        if len(parts) == 3:
            return f"{2025 if int(parts[1]) <= 4 else 2026} Round {parts[1]}.{parts[2]} Pick"
    return pid


def filter_trades_for_player(trades, player_name, player_pool):
    """
    Filters a list of trades to return only those that involve the given player.
    """
    filtered = []
    for trade in trades:
        added = trade.get("adds") or {}
        dropped = trade.get("drops") or {}
        all_players_involved = list(added.keys()) + list(dropped.keys())
        for player_id in all_players_involved:
            sleeper_name = player_pool.get(player_id, {}).get("full_name", "")
            if sleeper_name.lower() == player_name.lower():
                filtered.append(trade)
                break
    return filtered

# START: Side-by-side player images + trade history viewer
if "selected_names" in locals() and selected_names:

    # Images
    num_players = len(selected_names)
    cols = st.columns(num_players)
    for i, name in enumerate(selected_names):
        selected_id = df[df["Player_Sleeper"] == name].iloc[0]["Sleeper_Player_ID"]
        headshot_url = f"https://sleepercdn.com/content/nfl/players/{selected_id}.jpg"
        with cols[i]:
            st.image(headshot_url, width=120)
            st.caption(name)

    # Trade History Viewer
    if st.button("Show Trade History"):
        with st.spinner("Loading trade history..."):
            all_trades = get_all_trades_from_league(league_id)

            # Inject rookie picks into player_pool if missing
            all_ids = set()
            for trade in all_trades:
                all_ids.update((trade.get("adds") or {}).keys())
                all_ids.update((trade.get("drops") or {}).keys())

            for pid in all_ids:
                if isinstance(pid, str) and pid.startswith("rookie_") and pid not in player_pool:
                    player_pool[pid] = {
                        "full_name": format_pick_id(pid),
                        "position": "PICK",
                        "team": ""
                    }
            for name in selected_names:
                player_trades = filter_trades_for_player(all_trades, name, player_pool)
                st.subheader(f"Trade History for {name} ({len(player_trades)} found)")
                if player_trades:
                    for trade in player_trades:
                        rosters_involved = trade.get("roster_ids", [])
                        adds = trade.get("adds") or {}
                        drops = trade.get("drops") or {}
                        season = trade.get("season", "?")
                        added_items = [player_pool.get(pid, {}).get("full_name") or format_pick_id(pid) for pid in adds.keys()]
                        dropped_items = [player_pool.get(pid, {}).get("full_name", pid) for pid in drops.keys()]

                                                # Build a descriptive sentence about the trade
                        added_by = trade.get("adds", {})
                        dropped_by = trade.get("drops", {})
                        roster_ids = trade.get("roster_ids", [])

                        # Reverse lookup for roster_id to team name
                        owner_lookup = {int(row["Roster_ID"]): row["Team_Owner"] for _, row in df.iterrows()}
                        teams = [owner_lookup.get(rid, f"Team {rid}") for rid in roster_ids]

                        added_names = [player_pool.get(pid, {}).get("full_name", pid) for pid in added_by.keys()]
                        dropped_names = [player_pool.get(pid, {}).get("full_name", pid) for pid in dropped_by.keys()]

                        # Build a descriptive sentence using adds/drops by roster
                        adds = trade.get("adds") or {}
                        drops = trade.get("drops") or {}
                        season = trade.get("season", "?")
                        week = trade.get("week", "?")
                        roster_ids = trade.get("roster_ids", [])

                        owner_lookup = {int(row["Roster_ID"]): row["Team_Owner"] for _, row in df.iterrows()}

                        give_by_roster = {}
                        receive_by_roster = {}

                        for rid in roster_ids:
                            give_by_roster[rid] = []
                            receive_by_roster[rid] = []

                        for pid, rid in (drops or {}).items():
                            give_by_roster[rid].append(player_pool.get(pid, {}).get("full_name") or format_pick_id(pid))
                        for pid, rid in (adds or {}).items():
                            receive_by_roster[rid].append(player_pool.get(pid, {}).get("full_name") or format_pick_id(pid))

                        st.markdown(f"<strong>Season:</strong> {season} &nbsp; <strong>Week:</strong> {week}", unsafe_allow_html=True)
                        for rid in roster_ids:
                            giver = owner_lookup.get(rid, f"Team {rid}")
                            received = ", ".join(receive_by_roster[rid]) or "nothing"
                            given = ", ".join(give_by_roster[rid]) or "nothing"
                            st.markdown(f"<strong>{giver}</strong> gave: {given} &nbsp;|&nbsp; received: {received}", unsafe_allow_html=True)
                        st.markdown("<hr>", unsafe_allow_html=True)
                else:
                    st.write("No trades found involving this player.")
# END

                
