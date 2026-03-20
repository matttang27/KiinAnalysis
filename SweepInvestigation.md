# SweepInvestigation

International best-of-five analysis focused on how one-sided major events have been.

The current version of `SweepInvestigation.py` compares official international Bo5 tournaments using:

- `% Bo5s Ending 3-0`
- `Avg Games / Bo5`

The main comparison filter used for the current writeup is:

- official international events only
- primary events only
- standard Bo5 rows only
- tournaments with at least `7` Bo5s

## What It Does

`SweepInvestigation.py`:

1. fetches international Bo5 match data from Leaguepedia
2. removes nonstandard team-relay/showmatch `BestOf=5` rows
3. groups series by tournament
4. computes tournament-level Bo5 stomp metrics
5. exports a static scatter chart when requested

## Current Headline Result

With the `--primary-only --min-series 7` filter:

- `FST 2026` currently has the highest `% Bo5s Ending 3-0`
- `Worlds 2015` is the next-closest comparison
- `MSI 2025` stands out on the opposite end with a much higher `Avg Games / Bo5`

## Usage

Text report:

```bash
python SweepInvestigation.py --primary-only --min-series 7
```

PNG chart export:

```bash
python SweepInvestigation.py --primary-only --min-series 7 --export-png sweep_scatter.png
```

## Output Notes

The scatter chart currently uses:

- `Avg Games / Bo5` on the x-axis
- `% Bo5s Ending 3-0` on the y-axis
- color and marker shape by tournament type
- opacity by recency
- labels only for `FST 2026`, `Worlds 2015`, and `MSI 2025`

## Related Files

- `SweepInvestigation.py`
- `leaguepedia.py`
- [Overview.md](/c:/Users/mattt/Documents/MatthewPrograms/KiinAnalysis/Overview.md)
