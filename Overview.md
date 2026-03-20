# KiinAnalysis Project

This project contains Leaguepedia-based analysis scripts for League of Legends esports. (Sorry I used AI to write everything)

## Files

- `leaguepedia.py`
  Shared Leaguepedia client and Cargo query helpers.
- `KiinAnalysis.py`
  LCK placement analysis for players who have collected different finish positions.
- `SweepInvestigation.py`
  International best-of-five analysis focused on `% Bo5s Ending 3-0` and `Avg Games / Bo5`.

## Setup

Install the Python dependency:

```bash
pip install mwrogue
```

Create a `wiki_account_me.json` file with bot credentials. Fandom's instructions for third-party tool login are here:

https://help.fandom.com/wiki/Logging_in_to_third-party_tools

Example:

```json
{
    "username": "your_username",
    "password": "your_password"
}
```

## Analysis Docs

- [KiinAnalysis.md](/c:/Users/mattt/Documents/MatthewPrograms/KiinAnalysis/KiinAnalysis.md)
- [SweepInvestigation.md](/c:/Users/mattt/Documents/MatthewPrograms/KiinAnalysis/SweepInvestigation.md)
