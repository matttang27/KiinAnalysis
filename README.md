# 🏆 LCK Placement Collection Challenge

**Who has achieved placements from 1st to 10th in LCK?**

This script analyzes player placement data from Korea's top League of Legends league (LCK) to find which players have achieved every possible regular season finish—from 1st place champions to 10th place.

## 📊 Key Findings

### The "Complete Collection" Players

Only **2 people** have finished in all 10 placement positions across LCK history:

| Player | Role | How They Did It |
|:-------|:-----|:----------------|
| **Edgar** | Coach | 10/10 in Regular Season |
| **Kiin** | Top | 10/10 including Playoffs |

### Closest Active Players to Completing the Challenge

| Player | Progress | Role | Missing Placements |
|:-------|:---------|:-----|:-------------------|
| Kiin | 9/10 | Top | 4th |
| Ucal | 8/10 | Mid | 2nd, 4th |
| Kingen | 8/10 | Top | 2nd, 7th |
| Bdd | 8/10 | Mid | 6th, 7th |
| Lehends | 8/10 | Support | 7th, 10th |
| Kellin | 8/10 | Support | 8th, 9th |
| Aiming | 8/10 | Bot | 9th, 10th |

> Faker has only 6/10 placements - he's never finished 6th, 8th, 9th, or 10th.

## 🔧 How It Works

The script queries the [Leaguepedia](https://lol.fandom.com/) API to:

1. Fetch all LCK tournament results (2015–present)
2. Join player rosters with team placements
3. Track unique placement positions per player
4. Check current contract status

### Requirements

```bash
pip install mwrogue
```

### Usage

```bash
python KiinAnalysis.py
```

You'll need to create a `wiki_account_me.json` file with your Leaguepedia credentials:

```json
{
    "username": "your_username",
    "password": "your_password"
}
```

## 📈 Data Coverage

| Metric | Value |
|:-------|:------|
| Years Covered | 2015–2025 |
| Regular Seasons | 22 |
| Total Tournaments | 60+ |
| Unique Players (Regular) | 446 |
| Unique Players (All) | 499 |

### Regular Seasons Included

- **2015:** Champions Spring/Summer
- **2016–2024:** LCK Spring/Summer
- **2025:** LCK Rounds 1-2 & Rounds 3-5 (new format)

### Playoffs & Other Tournaments Included

<details>
<summary>View all 33 tournaments</summary>

- Champions/2012 Season/Spring
- Champions/2012 Season/Summer
- Champions/2013 Season/Spring
- Champions/2013 Season/Summer
- Champions/2013 Season/Winter
- Champions/2014 Season/Spring Season
- Champions/2014 Season/Summer Season
- Champions/2014 Season/Winter Season
- Champions/2015 Season/Spring Playoffs
- Champions/2015 Season/Spring Preseason
- Champions/2015 Season/Summer Playoffs
- LCK/2016 Season/Spring Playoffs
- LCK/2016 Season/Summer Playoffs
- LCK/2017 Season/Spring Playoffs
- LCK/2017 Season/Summer Playoffs
- LCK/2018 Season/Spring Playoffs
- LCK/2018 Season/Summer Playoffs
- LCK/2019 Season/Spring Playoffs
- LCK/2019 Season/Summer Playoffs
- LCK/2020 Season/Spring Playoffs
- LCK/2020 Season/Summer Playoffs
- LCK/2021 Season/Spring Playoffs
- LCK/2021 Season/Summer Playoffs
- LCK/2022 Season/Spring Playoffs
- LCK/2022 Season/Summer Playoffs
- LCK/2023 Season/Spring Playoffs
- LCK/2023 Season/Summer Playoffs
- LCK/2024 Season/Spring Playoffs
- LCK/2024 Season/Summer Playoffs
- LCK/2025 Season/Cup
- LCK/2025 Season/Road to MSI
- LCK/2025 Season/Season Play-In
- LCK/2025 Season/Season Playoffs

</details>

---

*Data sourced from [Leaguepedia API](https://lol.fandom.com/)*