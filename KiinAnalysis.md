# KiinAnalysis

LCK placement analysis for players who have collected finish positions from `1st` through `10th`.

I also posted the original results on [reddit](https://www.reddit.com/r/leagueoflegends/comments/1qbzdo5/the_closest_players_to_achieving_the_kiin_placing/).

## What It Does

`KiinAnalysis.py` queries Leaguepedia to:

1. fetch LCK tournament placement data
2. join placements with player rosters
3. normalize recent LCK format changes
4. measure which players are closest to collecting every placement
5. check which players still have active contracts

## Key Findings

Only `2` people have completed the full `1st` through `10th` placement collection:

| Player | Role | How They Did It |
|:--|:--|:--|
| Edgar | Coach | 10/10 in regular season |
| Kiin | Top | 10/10 including playoffs |

Closest active players:

| Player | Progress | Role | Missing Placements |
|:--|:--|:--|:--|
| Kiin | 9/10 | Top | 4th |
| Ucal | 8/10 | Mid | 2nd, 4th |
| Kingen | 8/10 | Top | 2nd, 7th |
| Bdd | 8/10 | Mid | 6th, 7th |
| Lehends | 8/10 | Support | 7th, 10th |
| Kellin | 8/10 | Support | 8th, 9th |
| Aiming | 8/10 | Bot | 9th, 10th |

`Faker` has `6/10`; he has never finished `6th`, `8th`, `9th`, or `10th`.

## Usage

```bash
python KiinAnalysis.py
```

## Coverage

| Metric | Value |
|:--|:--|
| Years Covered | 2015-2025 |
| Regular Seasons | 22 |
| Total Tournaments | 60+ |
| Unique Players (Regular) | 446 |
| Unique Players (All) | 499 |

Regular seasons included:

- 2015 Champions Spring/Summer
- 2016-2024 LCK Spring/Summer
- 2025 LCK Rounds 1-2 and Rounds 3-5

## Related Files

- `KiinAnalysis.py`
- `leaguepedia.py`
- [Overview.md](/c:/Users/mattt/Documents/MatthewPrograms/KiinAnalysis/Overview.md)
