from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path

from mwrogue.esports_client import EsportsClient

from leaguepedia import cargo_all, create_site

TOURNAMENT_STYLE_CONFIG: dict[str, dict[str, str]] = {
    "World Championship": {"label": "Worlds", "color": "#2f6df6", "marker": "o"},
    "Mid-Season Invitational": {"label": "MSI", "color": "#ff6b35", "marker": "s"},
    "First Stand": {"label": "First Stand", "color": "#159947", "marker": "^"},
}
DEFAULT_TOURNAMENT_STYLE = {"label": "Other", "color": "#6b7280", "marker": "D"}
HIGHLIGHT_TOURNAMENTS = {"FST 2026", "Worlds 2015", "MSI 2025"}
HIGHLIGHT_OFFSETS: dict[str, tuple[int, int]] = {
    "FST 2026": (10, 12),
    "Worlds 2015": (-18, -18),
    "MSI 2025": (-12, -18),
}


def parse_int(value: object, default: int = 0) -> int:
    if value in (None, ""):
        return default
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return default


def format_tournament_display_name(name: str) -> str:
    if name.startswith("Worlds ") and name.endswith(" Main Event"):
        return name.removesuffix(" Main Event")
    if name.startswith("First Stand "):
        year = name.removeprefix("First Stand ").strip()
        if year.isdigit():
            return f"FST {year}"
    return name


@dataclass(frozen=True)
class SeriesRecord:
    match_id: str
    overview_page: str
    group_key: str
    display_name: str
    league: str
    level: str
    year: int
    team1: str
    team2: str
    team1_score: int
    team2_score: int
    games_played: int
    is_sweep: bool
    date_time_utc: str


@dataclass
class TournamentMetrics:
    group_key: str
    display_name: str
    league: str
    level: str
    year: int
    overview_pages: set[str] = field(default_factory=set)
    series_count: int = 0
    sweep_count: int = 0
    games_played: int = 0
    max_games: int = 0
    latest_date_time_utc: str = ""

    @property
    def sweep_rate(self) -> float:
        if self.series_count == 0:
            return 0.0
        return self.sweep_count / self.series_count

    @property
    def avg_games_per_bo5(self) -> float:
        if self.series_count == 0:
            return 0.0
        return self.games_played / self.series_count


def fetch_international_bo5_series(
    site: EsportsClient,
    *,
    primary_only: bool = False,
) -> tuple[list[SeriesRecord], dict[str, int]]:
    where_clauses = [
        "MS.BestOf=5",
        "MS.Winner IS NOT NULL",
        "(MS.IsNullified IS NULL OR MS.IsNullified = false)",
        "T.Region='International'",
        "T.IsOfficial=1",
        "(T.IsQualifier IS NULL OR T.IsQualifier=0)",
    ]
    if primary_only:
        where_clauses.append("T.TournamentLevel='Primary'")

    rows = cargo_all(
        site,
        tables="MatchSchedule=MS, Tournaments=T",
        join_on="MS.OverviewPage=T.OverviewPage",
        fields=",".join([
            "MS.MatchId=MatchId",
            "MS.OverviewPage=OverviewPage",
            "MS.Team1=Team1",
            "MS.Team2=Team2",
            "MS.Team1Score=Team1Score",
            "MS.Team2Score=Team2Score",
            "MS.Team1Advantage=Team1Advantage",
            "MS.Team2Advantage=Team2Advantage",
            "MS.DateTime_UTC=DateTimeUTC",
            "T.Name=TournamentName",
            "T.StandardName=StandardName",
            "T.BasePage=BasePage",
            "T.League=League",
            "T.TournamentLevel=TournamentLevel",
            "T.Year=Year",
        ]),
        where=" AND ".join(where_clauses),
        order_by="T.Year ASC, MS.DateTime_UTC ASC",
    )

    series_records: list[SeriesRecord] = []
    skipped = {
        "advantage_series": 0,
        "nonstandard_bo5_rows": 0,
        "duplicate_match_ids": 0,
    }
    seen_match_ids: set[str] = set()

    for row in rows:
        match_id = str(row.get("MatchId", "")).strip()
        overview_page = str(row.get("OverviewPage", "")).strip()
        if not match_id or not overview_page:
            skipped["nonstandard_bo5_rows"] += 1
            continue
        if match_id in seen_match_ids:
            skipped["duplicate_match_ids"] += 1
            continue
        seen_match_ids.add(match_id)

        team1_advantage = parse_int(row.get("Team1Advantage"))
        team2_advantage = parse_int(row.get("Team2Advantage"))
        if team1_advantage or team2_advantage:
            skipped["advantage_series"] += 1
            continue

        team1_score = parse_int(row.get("Team1Score"), default=-1)
        team2_score = parse_int(row.get("Team2Score"), default=-1)
        if max(team1_score, team2_score) != 3 or min(team1_score, team2_score) < 0:
            skipped["nonstandard_bo5_rows"] += 1
            continue

        games_played = team1_score + team2_score
        if games_played < 3 or games_played > 5:
            skipped["nonstandard_bo5_rows"] += 1
            continue

        base_page = str(row.get("BasePage", "")).strip()
        tournament_name = str(row.get("TournamentName", "")).strip()
        standard_name = str(row.get("StandardName", "")).strip()
        group_key = base_page or overview_page
        display_name = format_tournament_display_name(
            standard_name or tournament_name or group_key
        )

        series_records.append(
            SeriesRecord(
                match_id=match_id,
                overview_page=overview_page,
                group_key=group_key,
                display_name=display_name,
                league=str(row.get("League", "")).strip(),
                level=str(row.get("TournamentLevel", "")).strip(),
                year=parse_int(row.get("Year")),
                team1=str(row.get("Team1", "")).strip(),
                team2=str(row.get("Team2", "")).strip(),
                team1_score=team1_score,
                team2_score=team2_score,
                games_played=games_played,
                is_sweep=min(team1_score, team2_score) == 0,
                date_time_utc=str(row.get("DateTimeUTC", "")).strip(),
            )
        )

    return series_records, skipped


def build_tournament_metrics(
    series_records: list[SeriesRecord],
    *,
    min_series: int = 1,
) -> list[TournamentMetrics]:
    grouped: dict[str, TournamentMetrics] = {}

    for series in series_records:
        metrics = grouped.get(series.group_key)
        if metrics is None:
            metrics = TournamentMetrics(
                group_key=series.group_key,
                display_name=series.display_name,
                league=series.league,
                level=series.level,
                year=series.year,
            )
            grouped[series.group_key] = metrics

        metrics.overview_pages.add(series.overview_page)
        metrics.series_count += 1
        metrics.sweep_count += int(series.is_sweep)
        metrics.games_played += series.games_played
        metrics.max_games += 5
        if series.date_time_utc > metrics.latest_date_time_utc:
            metrics.latest_date_time_utc = series.date_time_utc

    tournaments = [metrics for metrics in grouped.values() if metrics.series_count >= min_series]
    tournaments.sort(
        key=lambda item: (
            item.avg_games_per_bo5,
            -item.sweep_rate,
            -item.series_count,
            item.year,
            item.display_name.lower(),
        )
    )
    return tournaments


def build_rank_index(
    tournaments: list[TournamentMetrics],
    *,
    sort_key,
) -> dict[str, int]:
    ranked = sorted(tournaments, key=sort_key)
    return {tournament.group_key: idx + 1 for idx, tournament in enumerate(ranked)}


def compute_recency_alpha(year: int, min_year: int, max_year: int) -> float:
    if min_year >= max_year:
        return 0.9
    normalized = (year - min_year) / (max_year - min_year)
    return 0.25 + (0.95 - 0.25) * normalized


def style_for_tournament(tournament: TournamentMetrics) -> dict[str, str]:
    return TOURNAMENT_STYLE_CONFIG.get(tournament.league, DEFAULT_TOURNAMENT_STYLE)


def compute_plot_positions(
    tournaments: list[TournamentMetrics],
) -> dict[str, tuple[float, float]]:
    groups: dict[tuple[float, float], list[TournamentMetrics]] = {}
    positions: dict[str, tuple[float, float]] = {}

    for tournament in tournaments:
        key = (round(tournament.avg_games_per_bo5, 6), round(tournament.sweep_rate, 6))
        groups.setdefault(key, []).append(tournament)

    for (x_value, y_value), group in groups.items():
        if len(group) == 1:
            positions[group[0].group_key] = (x_value, y_value)
            continue

        ordered_group = sorted(group, key=lambda item: (item.year, item.display_name))
        midpoint = (len(ordered_group) - 1) / 2
        for idx, tournament in enumerate(ordered_group):
            x_offset = (idx - midpoint) * 0.025
            shifted_x = min(5.0, max(3.0, x_value + x_offset))
            positions[tournament.group_key] = (shifted_x, y_value)

    return positions


def export_scatter_chart_png(
    tournaments: list[TournamentMetrics],
    output_path: str,
    *,
    title: str,
) -> None:
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    from matplotlib.ticker import PercentFormatter

    if not tournaments:
        raise ValueError("No tournaments available to plot.")

    years = [tournament.year for tournament in tournaments]
    min_year = min(years)
    max_year = max(years)
    plot_positions = compute_plot_positions(tournaments)

    fig, ax = plt.subplots(figsize=(12, 8), dpi=200)
    fig.patch.set_facecolor("#f6f1e8")
    ax.set_facecolor("#fffdf8")

    for tournament in tournaments:
        style = style_for_tournament(tournament)
        alpha = compute_recency_alpha(tournament.year, min_year, max_year)
        plot_x, plot_y = plot_positions[tournament.group_key]
        ax.scatter(
            plot_x,
            plot_y,
            s=170,
            marker=style["marker"],
            color=style["color"],
            alpha=alpha,
            edgecolors="white",
            linewidths=1.2,
            zorder=3,
        )

        if tournament.display_name in HIGHLIGHT_TOURNAMENTS:
            offset_x, offset_y = HIGHLIGHT_OFFSETS.get(
                tournament.display_name,
                (10, 10),
            )
            horizontal_alignment = "right" if offset_x < 0 else "left"
            ax.annotate(
                tournament.display_name,
                (plot_x, plot_y),
                xytext=(offset_x, offset_y),
                textcoords="offset points",
                ha=horizontal_alignment,
                va="center",
                fontsize=11,
                fontweight="bold",
                color="#1f2937",
                bbox={
                    "boxstyle": "round,pad=0.28",
                    "facecolor": "#fffdf8",
                    "edgecolor": "#d1d5db",
                    "linewidth": 0.9,
                },
                arrowprops={
                    "arrowstyle": "-",
                    "color": "#9ca3af",
                    "linewidth": 1.0,
                },
                zorder=4,
            )

    legend_entries: list[Line2D] = []
    seen_labels: set[str] = set()
    for tournament in tournaments:
        style = style_for_tournament(tournament)
        legend_label = style["label"]
        if legend_label in seen_labels:
            continue
        seen_labels.add(legend_label)
        legend_entries.append(
            Line2D(
                [0],
                [0],
                marker=style["marker"],
                color="none",
                markerfacecolor=style["color"],
                markeredgecolor="white",
                markeredgewidth=1.1,
                markersize=10,
                label=legend_label,
            )
        )

    ax.legend(
        handles=legend_entries,
        loc="upper left",
        frameon=True,
        framealpha=0.95,
        facecolor="white",
        edgecolor="#d1d5db",
    )

    ax.set_title(title, fontsize=19, fontweight="bold", loc="left", pad=18)
    ax.text(
        0.0,
        1.0,
        "Darker points are more recent tournaments. Only official international tournaments with at least 7 Bo5 series are included.",
        transform=ax.transAxes,
        fontsize=11,
        color="#4b5563",
        ha="left",
        va="bottom",
    )

    ax.set_xlabel("Avg Games / Bo5", fontsize=12)
    ax.set_ylabel("% Bo5s Ending 3-0", fontsize=12)
    ax.xaxis.set_major_formatter(lambda value, _: f"{value:.1f}")
    ax.yaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
    ax.set_xlim(3.0, 5.0)
    ax.set_ylim(0.00, 1.00)
    ax.set_xticks([3.0, 3.5, 4.0, 4.5, 5.0])
    ax.set_yticks([i / 10 for i in range(0, 11)])
    ax.grid(True, linestyle="--", linewidth=0.7, color="#d1d5db", alpha=0.8)
    ax.set_axisbelow(True)

    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    ax.spines["left"].set_color("#9ca3af")
    ax.spines["bottom"].set_color("#9ca3af")

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(output, bbox_inches="tight")
    plt.close(fig)


def render_report(
    tournaments: list[TournamentMetrics],
    *,
    skipped: dict[str, int],
    primary_only: bool,
    min_series: int,
) -> None:
    if not tournaments:
        print("No tournaments matched the current filters.")
        return

    played_ranks = build_rank_index(
        tournaments,
        sort_key=lambda item: (
            item.avg_games_per_bo5,
            -item.sweep_rate,
            -item.series_count,
            item.year,
            item.display_name.lower(),
        ),
    )
    sweep_ranks = build_rank_index(
        tournaments,
        sort_key=lambda item: (
            -item.sweep_rate,
            item.avg_games_per_bo5,
            -item.series_count,
            item.year,
            item.display_name.lower(),
        ),
    )

    latest_tournament = max(tournaments, key=lambda item: item.latest_date_time_utc)
    first_stand_tournaments = [
        tournament for tournament in tournaments if tournament.league == "First Stand"
    ]

    print("=" * 72)
    print("# International Bo5 Sweep Investigation (v1)")
    print("=" * 72)
    print()
    print(
        "*Official international best-of-five series only. "
        "Metrics: % Bo5s Ending 3-0 = 3-0 series / total series; "
        "avg games / Bo5 = total games played / total Bo5 series.*"
    )
    print()
    print(f"*Filters: primary_only={primary_only}, min_series={min_series}*")
    print(
        f"*Skipped series: advantage={skipped['advantage_series']}, "
        f"nonstandard_bo5_rows={skipped['nonstandard_bo5_rows']}, "
        f"duplicate_match_ids={skipped['duplicate_match_ids']}*"
    )
    print(
        "*Nonstandard Bo5 rows are old team-relay or showmatch formats stored as "
        "BestOf=5 but not resolved as a standard 3-x series.*"
    )
    print()
    print(
        f"*Included tournaments: {len(tournaments)} | "
        f"Included Bo5 series: {sum(t.series_count for t in tournaments)}*"
    )
    print()

    print("## Spotlight")
    print()
    print(
        f"- Most recent tournament: **{latest_tournament.display_name}** "
        f"({latest_tournament.year}, {latest_tournament.level})"
    )
    print(
        f"- Most recent tournament ranks: "
        f"avg games / Bo5 #{played_ranks[latest_tournament.group_key]}/{len(tournaments)}, "
        f"% Bo5s Ending 3-0 #{sweep_ranks[latest_tournament.group_key]}/{len(tournaments)}"
    )
    print(
        f"- Most recent tournament metrics: "
        f"{latest_tournament.sweep_count}/{latest_tournament.series_count} sweeps "
        f"({latest_tournament.sweep_rate:.1%}), "
        f"{latest_tournament.games_played}/{latest_tournament.max_games} games "
        f"({latest_tournament.avg_games_per_bo5:.2f} avg games / Bo5)"
    )
    if first_stand_tournaments:
        for tournament in sorted(first_stand_tournaments, key=lambda item: item.year):
            print(
                f"- {tournament.display_name}: "
                f"avg games / Bo5 #{played_ranks[tournament.group_key]}/{len(tournaments)}, "
                f"% Bo5s Ending 3-0 #{sweep_ranks[tournament.group_key]}/{len(tournaments)}"
            )
    print()

    print("## Tournament Table")
    print()
    print(
        "| Rank | Tournament | League | Level | Series | Sweeps | % Bo5s Ending 3-0 | Games | Avg Games / Bo5 |"
    )
    print(
        "|:--|:--|:--|:--|--:|--:|--:|--:|--:|"
    )
    for idx, tournament in enumerate(tournaments, start=1):
        games_str = f"{tournament.games_played}/{tournament.max_games}"
        print(
            f"| {idx} | **{tournament.display_name}** | {tournament.league} | {tournament.level} | "
            f"{tournament.series_count} | {tournament.sweep_count} | {tournament.sweep_rate:.1%} | "
            f"{games_str} | {tournament.avg_games_per_bo5:.2f} |"
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Investigate sweep-heavy international best-of-five tournaments."
    )
    parser.add_argument(
        "--primary-only",
        action="store_true",
        help="Only include tournaments with TournamentLevel=Primary.",
    )
    parser.add_argument(
        "--min-series",
        type=int,
        default=1,
        help="Only show tournaments with at least this many Bo5 series.",
    )
    parser.add_argument(
        "--user-file",
        default="me",
        help="Credentials suffix for wiki_account_<user_file>.json.",
    )
    parser.add_argument(
        "--export-png",
        help="Write a static scatter chart PNG.",
    )
    parser.add_argument(
        "--chart-title",
        default="International % Bo5s Ending 3-0 vs Avg Games / Bo5",
        help="Title for the exported scatter chart.",
    )
    args = parser.parse_args()

    site = create_site(user_file=args.user_file)
    series_records, skipped = fetch_international_bo5_series(
        site,
        primary_only=args.primary_only,
    )
    tournaments = build_tournament_metrics(
        series_records,
        min_series=max(1, args.min_series),
    )
    render_report(
        tournaments,
        skipped=skipped,
        primary_only=args.primary_only,
        min_series=max(1, args.min_series),
    )
    if args.export_png:
        export_scatter_chart_png(
            tournaments,
            args.export_png,
            title=args.chart_title,
        )
        print()
        print(f"Chart PNG written to {args.export_png}")


if __name__ == "__main__":
    main()
