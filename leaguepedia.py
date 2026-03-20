from __future__ import annotations

import time
from datetime import datetime
from typing import Any

from mwrogue.auth_credentials import AuthCredentials
from mwrogue.esports_client import EsportsClient

CargoValue = Any
CargoRow = dict[str, CargoValue]


def create_site(game: str = "lol", *, user_file: str = "me") -> EsportsClient:
    """Create an authenticated Leaguepedia client."""
    creds = AuthCredentials(user_file=user_file)
    return EsportsClient(game, credentials=creds)


def cargo_all(
    site: EsportsClient,
    *,
    limit: int = 500,
    **query_kwargs: Any,
) -> list[CargoRow]:
    """Fetch all Cargo rows via pagination."""
    out: list[CargoRow] = []
    off = 0
    while True:
        rows: list[CargoRow] = site.cargo_client.query(
            limit=limit,
            offset=off,
            **query_kwargs,
        )
        if not rows:
            break
        out.extend(rows)
        off += limit
        time.sleep(0.1)
    return out


def fetch_active_players(site: EsportsClient) -> set[str]:
    """Fetch player IDs with active contracts and no retirement flag."""
    today = datetime.now().strftime("%Y-%m-%d")
    rows = cargo_all(
        site,
        tables="Players",
        fields="ID, Team, Contract, IsRetired",
        where=f"Contract > '{today}' AND (IsRetired IS NULL OR IsRetired = false)",
    )
    return {row["ID"] for row in rows if row.get("ID")}
