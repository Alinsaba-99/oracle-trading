"""Connect to MetaApi + fetch M5 EURUSD bars. Run after .env is filled.

    .venv/bin/python scripts/metaapi_smoke.py

Requires: METAAPI_TOKEN + METAAPI_ACCOUNT_ID in .env (see .env.example).
"""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import UTC, datetime, timedelta

from dotenv import load_dotenv

from execution.brokers.metaapi_client import MetaApiClient


async def main() -> int:
    load_dotenv()
    token = os.environ.get("METAAPI_TOKEN")
    account_id = os.environ.get("METAAPI_ACCOUNT_ID")
    if not token or not account_id:
        print("Set METAAPI_TOKEN and METAAPI_ACCOUNT_ID in .env")
        return 1

    client = MetaApiClient(token, account_id)
    await client.connect()
    try:
        info = await client.account_info()
        print(
            "Connected:",
            f"balance={info.get('balance')} equity={info.get('equity')}",
            f"currency={info.get('currency')} server={info.get('server')}",
            f"leverage={info.get('leverage')}",
        )

        end = datetime.now(UTC)
        start = end - timedelta(days=2)
        df = await client.historical_candles("EURUSD", "5m", start, end)
        print(f"EURUSD M5: {df.height} bars")
        if df.height:
            print(df.tail(3).to_string())
    finally:
        await client.close()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
