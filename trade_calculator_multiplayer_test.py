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
    "fgm_50_59",
    "fgm_60p",
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
    "st_ff",
    "rec_yd",
    "rush_yd",
    "kr_yd",
    "pr_yd",
    "pass_yd"
}

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
    "pass_int": "Pass Int",
    "bonus_pass_yd_400": "400+ Yard Passing Bonus",
    "rush_td_50p": "50+ Yard Rush TD Bonus",
    "pass_td_40p": "40+ Yard Pass TD Bonus",
    "pass_td_50p": "50+ Yard Pass TD Bonus",
    "rec_40p": "40+ Yard Rec Bonus",
    "pass_cmp_40p": "40+ Yard Pass Cmp Bonus",
    "rec_td_40p": "40+ Yard Rec TD Bonus",
    "rec_td_50p": "50+ Yard Rec TD Bonus",
    "bonus_rush_yd_200": "200+ Yard Rushing Game Bonus",
    "rush_40p": "40+ Yard Rush Bonus",
    "rush_td_40p": "40+ Yard Rush TD Bonus",
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

def get_all_trades_from_league(league_id):
    all_trades = []
    current_league_id = league_id
    visited = set()
    pick_owners = {}

    # -- Try fetching users
    try:
        user_response = requests.get(f"https://api.sleeper.app/v1/league/{league_id}/users")
        user_response.raise_for_status()
        league_users = user_response.json()
    except Exception as e:
        print(f"Failed to get league users: {e}")
        return [], {}  # return empty trades and pick map

    user_map = {user["user_id"]: user["display_name"] for user in league_users}

    # -- Now get rosters
    try:
        rosters = requests.get(f"https://api.sleeper.app/v1/league/{league_id}/rosters").json()
    except Exception as e:
        print(f"Failed to get rosters: {e}")
        return [], {}

    roster_map = {str(r["roster_id"]): r["owner_id"] for r in rosters}
    rosters = requests.get(f"https://api.sleeper.app/v1/league/{league_id}/rosters").json()
    for r in rosters:
        roster_map[str(r["roster_id"])] = r["owner_id"]

    while current_league_id and current_league_id not in visited:
        visited.add(current_league_id)
        league_info = requests.get(f"https://api.sleeper.app/v1/league/{current_league_id}").json()
        season = league_info.get("season", "?")

        for week in range(1, 19):
            url = f"https://api.sleeper.app/v1/league/{current_league_id}/transactions/{week}"
            response = requests.get(url)
            if response.status_code == 200:
                transactions = response.json()
                for t in transactions:
                    if t.get("type") == "trade":
                        all_trades.append(t)
                        
                        adds = t.get("adds") or {}
                        for pid, roster_id in adds.items():
                            if pid.startswith("2025_pick_"):
                                owner_id = roster_map.get(str(roster_id))
                                if owner_id and owner_id in user_map:
                                    pick_owners[pid] = user_map[owner_id]
                                elif pid.split("_")[-1] in user_map:
                                    generic_uid = pid.split("_")[-1]
                                    pick_owners[pid] = user_map[generic_uid]

        current_league_id = league_info.get("previous_league_id")

    return all_trades, pick_owners

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
    _, traded_pick_owners = get_all_trades_from_league(league_id)
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
    st.write("Prev season ID:", prev_league_id)

    pick_order = []
    if prev_league_id:
        prev_rosters = requests.get(f"https://api.sleeper.app/v1/league/{prev_league_id}/rosters").json()
        standings = sorted(prev_rosters, key=lambda x: x.get("settings", {}).get("final_standing", 999))
        pick_order = [r["roster_id"] for r in standings if r.get("settings", {}).get("final_standing")]

    # 🧠 If previous season not found, fallback to current roster order
    if not pick_order:
        st.warning("No previous season found — falling back to assigning picks using current rosters.")
        pick_order = [r["roster_id"] for r in rosters]
    
    # ✅ Assign 2025 Round 1 Picks
    for idx, roster_id in enumerate(reversed(pick_order)):  # Champion gets 1.12
        pick_num = idx + 1
        pick_name = f"2025 Pick 1.{str(pick_num).zfill(2)}"
        pick_id = f"2025_pick_1_{str(pick_num).zfill(2)}"
        
        # Check for traded ownership override
        owner_name = traded_pick_owners.get(pick_id)
        if not owner_name:
            owner_name = user_map.get(rosters[roster_id - 1]['owner_id'], f"User {roster_id}")
            
        ktc_row = ktc_df[ktc_df["Player_Sleeper"].str.strip().str.lower() == pick_name.lower()]
        ktc_value = int(ktc_row["KTC_Value"].iloc[0]) if not ktc_row.empty else 0
        
        data.append({
            "Sleeper_Player_ID": pick_id,
            "Player_Sleeper": pick_name,
            "Position": "PICK",
            "Team": "",
            "Team_Owner": owner_name,
            "Roster_ID": roster_id,
            "KTC_Value": ktc_value  # ✅ pull from CSV now
        })
    
    # ✅ Assign 2025 Round 2 Picks
    for idx, roster_id in enumerate(reversed(pick_order)):  # Same order as round 1
        pick_num = idx + 1
        pick_name = f"2025 Pick 2.{str(pick_num).zfill(2)}"
        pick_id = f"2025_pick_2_{str(pick_num).zfill(2)}"
        
        # Check for traded ownership override
        owner_name = traded_pick_owners.get(pick_id)
        if not owner_name:
            owner_name = user_map.get(rosters[roster_id - 1]['owner_id'], f"User {roster_id}")
            
        ktc_row = ktc_df[ktc_df["Player_Sleeper"].str.strip().str.lower() == pick_name.lower()]
        ktc_value = int(ktc_row["KTC_Value"].iloc[0]) if not ktc_row.empty else 0
        
        data.append({
            "Sleeper_Player_ID": pick_id,
            "Player_Sleeper": pick_name,
            "Position": "PICK",
            "Team": "",
            "Team_Owner": owner_name,
            "Roster_ID": roster_id,
            "KTC_Value": ktc_value  # ✅ pull from CSV now
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
                                   help="How much does your league value the QB position? Set to 1500 if trading with McNutted")

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
        st.markdown(
            f"<div style='font-size:22px; font-weight:600; color:#4da6ff; text-align:center;'>{league_desc}</div>", 
            unsafe_allow_html=True
        )
        # Show league_desc in the sidebar under league selection
        st.sidebar.markdown(f"<div style='font-size:16px; font-weight:600; color:#4da6ff; text-align:center;'>{league_desc}</div>", unsafe_allow_html=True)

        ktc_df = pd.read_csv("ktc_values.csv", encoding="utf-8-sig")
        df, player_pool = load_league_data(league_id, ktc_df)
        with st.expander("🧪 DEBUG: All Picks Pulled", expanded=False):
            st.dataframe(df[df["Position"] == "PICK"])
            
         # Sidebar: List custom scoring settings
        non_default_settings = []
        for k, v in scoring.items():
            if k in OMIT_SCORING_KEYS:
                continue
            # The new "skip zero" block goes here
            try:
                if float(v) == 0.0:
                    continue
            except Exception:
                if str(v) == "0" or str(v) == "0.0":
                    continue
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
        
        # ===================
        # Tab Layout
        # ===================
        tabs = st.tabs(["Trade Tool", "League Breakdown", "Player Portfolio"])
        
        with tabs[0]:  # Main trade tool as before!
            if not df.empty:
                top_qbs = df[df["Position"] == "QB"].sort_values("KTC_Value", ascending=False).head(30)["Player_Sleeper"].tolist()
        
                # Sort players by KTC descending
                user_players = df[df["Team_Owner"].str.lower() == username_lower].sort_values("KTC_Value", ascending=False)
                selected_names = []
        
                st.markdown("<h3 style='text-align:center;'>Select player(s) to trade away:</h3>", unsafe_allow_html=True)
                positions = ['QB', 'RB', 'WR', 'TE',]
                with st.expander("Player Selection", expanded=True):  # Change to False if you want collapsed by default
                    display_map = {'QB': 'QB', 'RB': 'RB', 'WR': 'WR', 'TE': 'TE'}
                    selected_names = []
                
                    # Define which positions go in each column
                    col1_positions = ['QB', 'RB']
                    col2_positions = ['WR', 'TE']
                
                    # Create two columns for selection
                    col1, col2 = st.columns(2)
                
                    # First column: QB and RB
                    with col1:
                        for pos in col1_positions:
                            st.markdown(f"**{display_map[pos]}**")
                            pos_players = user_players[user_players["Position"] == pos]
                            for _, row in pos_players.iterrows():
                                key = f"cb_{row['Sleeper_Player_ID']}"
                                name = row['Player_Sleeper']
                                ktc = row['KTC_Value']
                                label = f"{name} (KTC: {ktc})"
                                checked = st.checkbox(label, key=key)
                                if checked:
                                    selected_names.append(name)
                
                    # Second column: WR and TE
                    with col2:
                        for pos in col2_positions:
                            st.markdown(f"**{display_map[pos]}**")
                            pos_players = user_players[user_players["Position"] == pos]
                            for _, row in pos_players.iterrows():
                                key = f"cb_{row['Sleeper_Player_ID']}"
                                name = row['Player_Sleeper']
                                ktc = row['KTC_Value']
                                label = f"{name} (KTC: {ktc})"
                                checked = st.checkbox(label, key=key)
                                if checked:
                                    selected_names.append(name)

                if selected_names:
                    selected_rows, total_ktc, total_qb_premium, total_bonus, adjusted_total = calculate_trade_value(
                        df, selected_names, top_qbs, qb_premium_setting
                    )
                    owner = selected_rows.iloc[0]["Team_Owner"]
                
                    # Side-by-side layout: left=image, right=package details
                    img_col, val_col = st.columns([1, 2], gap="large")

                    with img_col:
                        # Calculate the vertical space to add above the images (adjust as needed)
                        n_images = len(selected_names)
                        image_block_height = n_images * 150  # estimate: image+name ~150px per player
                        value_block_height = 340  # adjust to match your value column (trial/error)
                        top_padding = max(0, (value_block_height - image_block_height) // 2)
                    
                        # Add dynamic vertical spacer
                        st.markdown(f"<div style='height: {top_padding}px;'></div>", unsafe_allow_html=True)
                    
                        for name in selected_names:
                            selected_id = df[df["Player_Sleeper"] == name].iloc[0]["Sleeper_Player_ID"]
                            headshot_url = f"https://sleepercdn.com/content/nfl/players/{selected_id}.jpg"
                            st.markdown(
                                f"""
                                <div style='display: flex; flex-direction: column; align-items: center; margin-bottom: 16px;'>
                                    <img src="{headshot_url}" width="120" style="display:block; margin: 0 auto; border-radius:12px;">
                                    <div style='text-align: center; font-size: 15px; color: #fff; margin-top: 8px;'>{name}</div>
                                </div>
                                """,
                                unsafe_allow_html=True,
                            )
                        st.markdown("</div>", unsafe_allow_html=True)
                
                    with val_col:
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
                            your_side_total = total_ktc + package_bonus(selected_rows["KTC_Value"].tolist())
                            two_low = int(your_side_total * (1 - tolerance / 100))
                            two_high = int(your_side_total * (1 + tolerance / 100))
        
                            results = []
                            other_teams = df[df["Team_Owner"] != owner]["Team_Owner"].unique()
        
                            for team_owner in other_teams:
                                team_players = df[df["Team_Owner"] == team_owner]
                                combos = combinations(team_players.iterrows(), 2)
                                for (i1, p1), (i2, p2) in combos:
                                  if p1["KTC_Value"] > total_ktc or p2["KTC_Value"] > total_ktc:
                                      continue
        
                                  value = p1["KTC_Value"] + p2["KTC_Value"]
                                  if p1["Position"] == "QB" and p1["Player_Sleeper"] in top_qbs:
                                      value += qb_premium_setting
                                  if p2["Position"] == "QB" and p2["Player_Sleeper"] in top_qbs:
                                      value += qb_premium_setting
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
        
        with tabs[1]:
            with st.spinner("Calculating League Statistics..."):
                import time
        
                this_league_users = requests.get(f"https://api.sleeper.app/v1/league/{league_id}/users").json()
                league_breakdown_rows = []
        
                for u in this_league_users:
                    owner = u['display_name']
                    their_user_id = u['user_id']
                    dynasty_lineup = 0
                    dynasty_bestball = 0
                    redraft_lineup = 0
                    redraft_bestball = 0
                    total_count = 0
                    
                    try:
                        owner_leagues_url = f"https://api.sleeper.app/v1/user/{their_user_id}/leagues/nfl/2025"
                        leagues_for_owner = requests.get(owner_leagues_url).json()
                        for lg in leagues_for_owner:
                            lg_type = str(lg.get('settings', {}).get('type', '')).lower()
                            is_dynasty = (lg_type == "dynasty" or lg_type == "2" or "dynasty" in lg.get('name', '').lower())
                            is_bestball = lg.get("settings", {}).get("best_ball", 0) == 1
                    
                            if is_dynasty and is_bestball:
                                dynasty_bestball += 1
                            elif is_dynasty and not is_bestball:
                                dynasty_lineup += 1
                            elif not is_dynasty and is_bestball:
                                redraft_bestball += 1
                            elif not is_dynasty and not is_bestball:
                                redraft_lineup += 1
                    
                        total_count = len(leagues_for_owner)
                        time.sleep(0.10)
                    except Exception:
                        dynasty_lineup = -1
                        dynasty_bestball = -1
                        redraft_lineup = -1
                        redraft_bestball = -1
                        total_count = -1
                    
                    league_breakdown_rows.append({
                        "Owner": owner,
                        "Dynasty Lineup": dynasty_lineup,
                        "Dynasty Best Ball": dynasty_bestball,
                        "Redraft Lineup": redraft_lineup,
                        "Redraft Best Ball": redraft_bestball,
                        "Total": total_count,
                    })
        
                league_breakdown_df = pd.DataFrame(league_breakdown_rows).sort_values("Total", ascending=False)
                league_breakdown_df.replace(-1, "", inplace=True)
        
                st.markdown("<h3 style='text-align:center;'>League Breakdown</h3>", unsafe_allow_html=True)
                st.write("This table shows how many 2025 leagues each owner is in:")
                table_height = max(400, 40 * len(league_breakdown_df) + 60)
                st.dataframe(league_breakdown_df, use_container_width=True, height=table_height)

        with tabs[2]:
            with st.spinner("Calculating Player Ownership..."):
                # Get all owners in the current league
                league_users_url = f"https://api.sleeper.app/v1/league/{league_id}/users"
                league_users = requests.get(league_users_url).json()
                owner_display_map = {u['display_name']: u['user_id'] for u in league_users}
                owner_names = list(owner_display_map.keys())
            
                # Dropdown to select which owner's portfolio to view
                selected_owner = st.selectbox("Select Owner for Player Portfolio", owner_names)
                selected_owner_id = owner_display_map[selected_owner]
            
                # Optional: add league format filter
                filter_option = st.selectbox(
                    "Filter Leagues By Type/Format:",
                    [
                        "All",
                        "Dynasty Lineup",
                        "Dynasty Best Ball",
                        "Redraft Lineup",
                        "Redraft Best Ball"
                    ],
                    index=0
                )
            
                def league_matches_filter(league, option):
                    lg_type = str(league.get('settings', {}).get('type', '')).lower()
                    is_dynasty = (lg_type == "dynasty" or lg_type == "2" or "dynasty" in league.get('name', '').lower())
                    is_bestball = league.get("settings", {}).get("best_ball", 0) == 1
            
                    if option == "All":
                        return True
                    if option == "Dynasty Lineup":
                        return is_dynasty and not is_bestball
                    if option == "Dynasty Best Ball":
                        return is_dynasty and is_bestball
                    if option == "Redraft Lineup":
                        return (not is_dynasty) and not is_bestball
                    if option == "Redraft Best Ball":
                        return (not is_dynasty) and is_bestball
                    return True
            
                try:
                    # Fetch all of the selected owner's leagues (2025)
                    owner_leagues_url = f"https://api.sleeper.app/v1/user/{selected_owner_id}/leagues/nfl/2025"
                    leagues_for_owner = requests.get(owner_leagues_url).json()
                    filtered_leagues = [league for league in leagues_for_owner if league_matches_filter(league, filter_option)]
                    total_leagues = len(filtered_leagues)
                    player_counts = {}
            
                    for league in filtered_leagues:
                        league_id_this = league['league_id']
                        rosters = requests.get(f"https://api.sleeper.app/v1/league/{league_id_this}/rosters").json()
                        my_roster = next((r for r in rosters if r.get("owner_id") == selected_owner_id), None)
                        if not my_roster:
                            continue
                        players_on_roster = my_roster.get("players") or []
                        for pid in players_on_roster:
                            player_counts[pid] = player_counts.get(pid, 0) + 1
            
                    rows = []
                    for pid, count in player_counts.items():
                        player_name = player_pool.get(pid, {}).get("full_name", pid)
                        ownership_pct = (count / total_leagues) * 100 if total_leagues else 0
                        rows.append({
                            "Player": player_name,
                            "Leagues Owned": count,
                            "Ownership %": f"{ownership_pct:.0f}%"
                        })
                    
                    # FIX: Build the DataFrame here BEFORE you use it!
                    portfolio_df = pd.DataFrame(rows).sort_values("Leagues Owned", ascending=False).reset_index(drop=True)
                    
                    # Show league total description
                    if filter_option == "All":
                        league_type_str = "all Leagues"
                    else:
                        league_type_str = f"{filter_option} leagues"
                    st.markdown(
                        f"<div style='margin-bottom:12px; font-size:17px; text-align:left; color:#4da6ff;'>"
                        f"Total number of {league_type_str}: <b>{total_leagues}</b>"
                        "</div>",
                        unsafe_allow_html=True
                    )
                    
                    st.markdown(f"<h3 style='text-align:center;'>Player Portfolio for {selected_owner}</h3>", unsafe_allow_html=True)
                    st.write("This table shows the 2025 ownership % for each player across all their leagues (filtered):")
                    table_height = max(400, 40 * len(portfolio_df) + 60)
                    st.dataframe(portfolio_df, use_container_width=True, height=table_height)
                except Exception as e:
                    st.error(f"Could not calculate player portfolio: {e}")

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
# Pick formatter for rough rookie picks
# --------------------
def ordinal(n):
    return "%d%s" % (n, "tsnrhtdd"[(n//10%10!=1)*(n%10<4)*n%10::4])

# --------------------
# Pick formatter for rookie picks
# --------------------
def format_pick_id(pid):
    if "pick" in pid:
        parts = pid.split("_")  # example: 2025_pick_1_01
        if len(parts) == 4 and parts[1] == "pick":
            return f"{parts[0]} Pick {parts[2]}.{parts[3]}"
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

                
