# pip install mwrogue
from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass

from mwrogue.esports_client import EsportsClient
from mwrogue.auth_credentials import AuthCredentials


def cargo_all(site: EsportsClient, *, limit: int = 500, **query_kwargs):
    """Fetch all Cargo rows via pagination (offset stepping)."""
    out = []
    off = 0
    while True:
        rows = site.cargo_client.query(limit=limit, offset=off, **query_kwargs)
        if not rows:
            break
        out.extend(rows)
        off += limit
        time.sleep(0.1)  # Small delay to avoid rate limiting
    return out


def fetch_active_players(site: EsportsClient):
    """
    Fetch players who have an active contract (Contract date > today).
    Returns a set of player IDs who are currently under contract.
    """
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    
    rows = cargo_all(
        site,
        tables="Players",
        fields="ID, Team, Contract, IsRetired",
        where=f"Contract > '{today}' AND (IsRetired IS NULL OR IsRetired = false)",
    )
    
    return {r["ID"] for r in rows if r.get("ID")}


def fetch_player_places(
    site: EsportsClient,
    *,
    leagues=("LoL Champions Korea", "LoL The Champions"),
    splits=("Spring", "Summer", "Rounds 1-2", "Rounds 3-5"),  # Include 2025 format
    regular_season_only=True,
):
    """
    Join TournamentResults, TournamentPlayers, and Tournaments to get
    player placements in LCK regular seasons.
    Includes:
    - "LoL Champions Korea" (2016+)
    - "LoL The Champions" (2015)
    - 2025+ new format with Rounds 1-2 and Rounds 3-5
    - LCK Regional Finals (under "World Championship" league)
    
    If regular_season_only=False, includes all regional tournaments (playoffs, etc.)
    """
    league_filter = " OR ".join(f"T.League='{l}'" for l in leagues)
    
    # Also include LCK Regional Finals (tracked under World Championship league)
    lck_regional_filter = "(T.League='World Championship' AND TR.OverviewPage LIKE 'LCK/%Regional Finals')"
    
    where_clauses = [
        f"(({league_filter}) OR {lck_regional_filter})",
        "TR.Place_Number IS NOT NULL",
        "TR.Place_Number >= 1",
        "TR.Place_Number <= 10",
    ]
    
    if regular_season_only:
        where_clauses.append(f"T.Split IN ({','.join(repr(s) for s in splits)})")
        # Include regular seasons and 2025 round robin formats
        where_clauses.append("(TR.OverviewPage LIKE '%Season' OR TR.OverviewPage LIKE '%Rounds 1-2' OR TR.OverviewPage LIKE '%Rounds 3-5')")
    
    rows = cargo_all(
        site,
        tables="TournamentResults=TR, TournamentPlayers=TP, Tournaments=T",
        join_on="TR.OverviewPage=TP.OverviewPage, TR.Team=TP.Team, TR.OverviewPage=T.OverviewPage",
        fields=",".join([
            "TP.Player=Player",
            "TR.Place_Number=Place",
            "TR.Team=Team",
            "TR.OverviewPage=OverviewPage",
            "T.Year=Year",
            "T.Split=Split",
            "T.Name=TName",
            "TP.Role=Role",
            "T.League=League",
        ]),
        where=" AND ".join(where_clauses),
        order_by="T.Year ASC, T.Split ASC, TR.Place_Number ASC",
    )
    for r in rows:
        try:
            r["Place"] = int(r["Place"])
        except Exception:
            r["Place"] = None
    return rows


def filter_shared_placements(rows):
    """
    Remove placements where multiple teams share the same place in a tournament.
    (e.g., 3-4 ties in playoffs)
    """
    # Count how many teams have each place in each tournament
    place_counts = defaultdict(lambda: defaultdict(int))
    for r in rows:
        if r.get("Place") is not None:
            place_counts[r["OverviewPage"]][r["Place"]] += 1
    
    # Keep only rows where the place is unique in that tournament
    # (accounting for multiple players per team)
    teams_per_place = defaultdict(lambda: defaultdict(set))
    for r in rows:
        if r.get("Place") is not None:
            teams_per_place[r["OverviewPage"]][r["Place"]].add(r["Team"])
    
    filtered = []
    for r in rows:
        if r.get("Place") is not None:
            tournament = r["OverviewPage"]
            place = r["Place"]
            # If only one team has this place, keep it
            if len(teams_per_place[tournament][place]) == 1:
                filtered.append(r)
    
    return filtered


def only_valid_seasons(rows):
    """
    Keep only tournaments from valid seasons:
    - 2015 Spring: 8 teams (valid)
    - 2015 Summer onwards: 10 teams (valid)
    - 2025+: Rounds 1-2 (10 team round robin) and Rounds 3-5 (two groups)
    - Exclude 2014 and earlier (different format with 16 teams in groups)
    - Exclude incomplete current year data
    
    For 2025 Rounds 3-5: Legend group places 1-5 map to 1-5, Rise group 1-5 map to 6-10
    """
    max_place = defaultdict(int)
    year_per_tournament = {}
    split_per_tournament = {}
    team_count = defaultdict(set)
    
    for r in rows:
        p = r.get("Place")
        if p is None:
            continue
        t = r["OverviewPage"]
        year_per_tournament[t] = int(r.get("Year", 0))
        split_per_tournament[t] = r.get("Split", "")
        team_count[t].add(r.get("Team"))
        if p > max_place[t]:
            max_place[t] = p
    
    good = set()
    for t, m in max_place.items():
        year = year_per_tournament.get(t, 0)
        split = split_per_tournament.get(t, "")
        teams = len(team_count.get(t, set()))
        
        # Exclude 2014 and earlier (different format)
        if year < 2015:
            continue
        
        # Exclude incomplete seasons (less than 5 teams means data is still being added)
        if teams < 5:
            continue
        
        # 2025+ Rounds formats
        if "Rounds" in split:
            good.add(t)
            continue
            
        # 2015 Spring had 8 teams, all others should have 10
        if m >= 8:
            good.add(t)
    
    return [r for r in rows if r["OverviewPage"] in good]


def adjust_2025_placements(rows):
    """
    For 2025 Rounds 3-5, adjust placements:
    - Legend group (top teams): places 1-5 stay as 1-5
    - Rise group (bottom teams): places 1-5 become 6-10
    
    We detect Rise group by checking if the tournament name contains 'Rise'
    """
    adjusted = []
    for r in rows.copy():
        year = int(r.get("Year", 0))
        split = r.get("Split", "")
        tname = r.get("TName", "")
        overview = r.get("OverviewPage", "")
        
        # Check if this is 2025 Rounds 3-5 Rise group
        if year >= 2025 and "Rounds 3-5" in split:
            # Rise group teams should have their placements offset by 5
            if "Rise" in tname or "Rise" in overview:
                if r["Place"] is not None and r["Place"] <= 5:
                    r = dict(r)  # Make a copy to modify
                    r["Place"] = r["Place"] + 5
        
        adjusted.append(r)
    
    return adjusted


@dataclass(frozen=True)
class PlayerScore:
    player: str
    got: tuple[int, ...]
    missing: tuple[int, ...]
    roles: tuple[str, ...]
    last_year: int
    teams: tuple[str, ...]


def compute_closest(rows, target_places=range(1, 11)):
    target = set(target_places)
    per = defaultdict(set)
    player_roles = defaultdict(set)
    player_last_year = defaultdict(int)
    player_teams = defaultdict(set)

    for r in rows:
        p = r.get("Place")
        role = r.get("Role", "")
        player = r["Player"]
        year_str = r.get("Year", "0") or "0"
        try:
            year = int(year_str)
        except ValueError:
            year = 0
        team = r.get("Team", "")
        
        # Skip empty player names (bad data)
        if not player or not player.strip():
            continue
        
        if p in target:
            per[player].add(p)
        if role:
            # Role can be comma-separated (e.g., "Top,Mid"), split them
            for r in role.split(','):
                r = r.strip()
                if r:
                    player_roles[player].add(r)
        if year > player_last_year[player]:
            player_last_year[player] = year
        if team:
            player_teams[player].add(team)

    scored = []
    for pl, got in per.items():
        got2 = tuple(sorted(got))
        miss = tuple(sorted(target - got))
        roles = tuple(sorted(player_roles.get(pl, set())))
        last_year = player_last_year.get(pl, 0)
        teams = tuple(sorted(player_teams.get(pl, set())))
        scored.append(PlayerScore(pl, got2, miss, roles, last_year, teams))

    scored.sort(key=lambda s: (-len(s.got), len(s.missing), s.missing, s.player.lower()))
    return scored


def main():
    creds = AuthCredentials(user_file="me")
    site = EsportsClient("lol", credentials=creds)

    leagues = ("LoL Champions Korea", "LoL The Champions")  # Include 2015 name
    splits = ("Spring", "Summer", "Rounds 1-2", "Rounds 3-5")  # Include 2025 format
    target_places = range(1, 11)

    # === FETCH REGULAR SEASON DATA ===
    print("Fetching LCK regular season player placements...")
    rows_regular = fetch_player_places(site, leagues=leagues, splits=splits, regular_season_only=True)
    print(f"Fetched {len(rows_regular)} raw regular season records")

    rows_regular = only_valid_seasons(rows_regular)
    print(f"After filtering to valid seasons (2015+): {len(rows_regular)} records")

    # Adjust 2025 Rounds 3-5 placements (Rise group 1-5 -> 6-10)
    rows_regular = adjust_2025_placements(rows_regular)

    # === FETCH ALL TOURNAMENTS DATA ===
    print("\nFetching ALL LCK tournament placements (including playoffs)...")
    rows_all = fetch_player_places(site, leagues=leagues, splits=splits, regular_season_only=False)
    print(f"Fetched {len(rows_all)} raw records from all tournaments")
    
    # Filter out shared placements (3-4 ties, etc.)
    rows_all = filter_shared_placements(rows_all)
    print(f"After filtering shared placements: {len(rows_all)} records")

    # === DATA VALIDATION (Regular Season) ===
    print("\n" + "=" * 60)
    print("DATA VALIDATION - Regular Seasons Included")
    print("=" * 60)
    
    # Group by tournament to see what's included
    tournaments = defaultdict(lambda: {"teams": set(), "players": set()})
    for r in rows_regular:
        key = r["OverviewPage"]
        tournaments[key]["teams"].add(r["Team"])
        tournaments[key]["players"].add(r["Player"])
        tournaments[key]["year"] = r["Year"]
        tournaments[key]["split"] = r["Split"]
    
    # Sort by year and split
    sorted_tournaments = sorted(tournaments.items(), key=lambda x: (x[1]["year"], x[1]["split"]))
    
    print(f"\nFound {len(sorted_tournaments)} regular seasons with 10 teams:\n")
    print(f"{'Year':<6} {'Split':<8} {'Teams':<6} {'Players':<8} Tournament")
    print("-" * 70)
    for key, data in sorted_tournaments:
        print(f"{data['year']:<6} {data['split']:<8} {len(data['teams']):<6} {len(data['players']):<8} {key}")
    
    # Summary by year
    print("\n" + "-" * 70)
    years_covered = sorted(set(t[1]["year"] for t in sorted_tournaments))
    print(f"Years covered: {years_covered[0]} - {years_covered[-1]} ({len(years_covered)} years)")
    print(f"Total seasons: {len(sorted_tournaments)}")
    
    # Check for expected seasons (LCK started 10-team format around 2015)
    expected_years = set(range(2015, 2025))  # 2015-2024 should have Spring/Summer
    actual_years = set(int(y) for y in years_covered)
    missing_years = expected_years - actual_years
    if missing_years:
        print(f"⚠️  Potentially missing years: {sorted(missing_years)}")
    else:
        print("✅ All expected years (2015-2024) are present")
    
    # Check splits per year
    splits_per_year = defaultdict(list)
    for key, data in sorted_tournaments:
        splits_per_year[data["year"]].append(data["split"])
    
    incomplete_years = [(y, s) for y, s in splits_per_year.items() if len(s) < 2]
    if incomplete_years:
        print(f"\n⚠️  Years with fewer than 2 splits:")
        for y, s in incomplete_years:
            print(f"   {y}: {s}")
    else:
        print("✅ All years have both Spring and Summer splits")
    
    print("=" * 60 + "\n")

    # Compute scores for both datasets
    scored_regular = compute_closest(rows_regular, target_places=target_places)
    scored_all = compute_closest(rows_all, target_places=target_places)
    print(f"Regular season: {len(scored_regular)} unique players")
    print(f"All tournaments: {len(scored_all)} unique players")

    # Fetch active players (those with current contracts)
    print("Fetching player contract data...")
    active_players = fetch_active_players(site)
    print(f"Found {len(active_players)} players with active contracts\n")

    # Helper functions
    def show(pl_name: str, scored_list):
        for s in scored_list:
            if s.player.lower() == pl_name.lower():
                return s
        return None

    def format_roles(roles):
        """Format roles, noting if player is/was a coach."""
        # Deduplicate and categorize
        playing_roles = {'Top', 'Jungle', 'Mid', 'Bot', 'Support'}
        unique_roles = set(roles)  # Deduplicate first
        playing = sorted(r for r in unique_roles if r in playing_roles)
        staff = sorted(r for r in unique_roles if r and r not in playing_roles)
        
        parts = []
        if playing:
            parts.append('/'.join(playing))
        if staff:
            if playing:
                parts.append(f"(also {', '.join(staff)})")
            else:
                # Staff only (e.g., coach)
                parts.append(', '.join(staff))
        return ' '.join(parts) if parts else 'Unknown'

    def is_active(s, active_players):
        """Check if player has a current contract."""
        return s.player in active_players

    def status_emoji(s, active_players):
        """Return status indicator."""
        if is_active(s, active_players):
            return "🟢"  # Active (has contract)
        return "⚪"  # Inactive/No contract

    def places_visual(got, missing):
        """Create a visual representation of places achieved."""
        result = []
        for i in range(1, 11):
            if i in got:
                result.append(f"**{i}**")
            else:
                result.append(f"~~{i}~~")
        return " ".join(result)

    # Reddit-formatted output
    print("=" * 60)
    print("# 🏆 LCK Placement Collection Challenge")
    print("=" * 60)
    print()
    print("*Who has achieved placements from 1st to 10th in LCK?*")
    print()
    print("Legend: 🟢 = Has active contract | ⚪ = No active contract")
    print()
    print("---")
    print()

    # === REGULAR SEASON TABLE ===
    top_players_regular = [s for s in scored_regular if len(s.got) >= 8]
    faker_regular = show("Faker", scored_regular)
    
    print("## 🏅 Regular Season Only")
    print()
    print(f"*{len(scored_regular)} unique players across {len(sorted_tournaments)} regular seasons (2015-2025)*")
    print()
    print("| Player | Progress | Role | Status | Missing |")
    print("|:--|:--|:--|:--|:--|")
    
    for s in top_players_regular:
        status = status_emoji(s, active_players)
        missing_str = ', '.join(map(str, s.missing)) if s.missing else "✅ None!"
        print(f"| **{s.player}** | {len(s.got)}/10 | {format_roles(s.roles)} | {status} | {missing_str} |")
    
    # Honorary Faker row
    if faker_regular and faker_regular not in top_players_regular:
        print(f"| **Faker** | {len(faker_regular.got)}/10 | {format_roles(faker_regular.roles)} | {status_emoji(faker_regular, active_players)} | {', '.join(map(str, faker_regular.missing))} |")
    
    print()
    print("---")
    print()
    
    # === ALL TOURNAMENTS TABLE ===
    top_players_all = [s for s in scored_all if len(s.got) >= 8]
    faker_all = show("Faker", scored_all)
    
    # Count unique tournaments in all data
    all_tournaments = set(r["OverviewPage"] for r in rows_all)
    
    print("## 🏆 All Regional Tournaments (incl. Playoffs)")
    print()
    print(f"*{len(scored_all)} unique players across {len(all_tournaments)} tournaments (excludes shared placements like 3-4)*")
    print()
    print("| Player | Progress | Role | Status | Missing |")
    print("|:--|:--|:--|:--|:--|")
    
    for s in top_players_all:
        status = status_emoji(s, active_players)
        missing_str = ', '.join(map(str, s.missing)) if s.missing else "✅ None!"
        print(f"| **{s.player}** | {len(s.got)}/10 | {format_roles(s.roles)} | {status} | {missing_str} |")
    
    # Honorary Faker row
    if faker_all and faker_all not in top_players_all:
        print(f"| **Faker** | {len(faker_all.got)}/10 | {format_roles(faker_all.roles)} | {status_emoji(faker_all, active_players)} | {', '.join(map(str, faker_all.missing))} |")
    
    print()
    print("---")
    print()
    
    # === LIST ALL TOURNAMENTS ===
    print("## 📋 Tournaments Included")
    print()
    
    # Group tournaments by type
    regular_tournaments = sorted(set(r["OverviewPage"] for r in rows_regular))
    all_tournament_list = sorted(all_tournaments)
    playoff_tournaments = sorted(all_tournaments - set(regular_tournaments))
    
    print(f"### Regular Seasons ({len(regular_tournaments)})")
    print()
    for t in regular_tournaments:
        print(f"- {t}")
    print()
    
    print(f"### Playoffs & Other ({len(playoff_tournaments)})")
    print()
    for t in playoff_tournaments:
        print(f"- {t}")
    
    print()
    print("---")
    print()
    print("*Data sourced from Leaguepedia API.*")
    print()
    print("*Legend: 🟢 = Has active contract | ⚪ = No active contract*")


if __name__ == "__main__":
    main()
