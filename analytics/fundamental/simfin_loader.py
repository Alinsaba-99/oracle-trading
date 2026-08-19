"""simfin loader integration (BL-504 / Lane B universe).

Wraps the MIT-licensed `simfin` package (https://github.com/SimFin/simfin)
to provide a Python-native, zero-cost fundamental data loader for the
Lane B (turnaround value) universe per ADR-018 (Lane B is for portafoglio
personale operatore, NOT prop-firm).

Key capabilities:
- Download income/balance-sheet/cash-flow statements for US companies
- Daily share prices
- Point-in-time capable (via simfin's bulk + timestamp handling)
- Pandas-native → easy integration with polars via `pl.from_pandas`

References
----------
- SimFin (2026). https://github.com/SimFin/simfin (MIT)
- Deep-research synthesis 2026-08-15 §2.5: `simfin` provides
  "fundamental data (income statements) and daily share prices for US
  companies, loading directly into Pandas DataFrames — providing a
  Python-native, zero-cost loader for building a Lane B value-screening
  universe (Piotroski F-Score, Greenblatt Magic Formula) without
  hand-rolling SEC EDGAR parsers."

Usage
-----
    from analytics.fundamental.simfin_loader import SimFinLoader

    loader = SimFinLoader()
    df = loader.income_statements()  # bulk income statements
    prices = loader.daily_prices()    # bulk daily prices
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

import polars as pl

try:
    import simfin as sf

    _HAS_SIMFIN = True
except ImportError:  # pragma: no cover
    _HAS_SIMFIN = False


DEFAULT_DATA_DIR = Path("data") / "simfin"
DEFAULT_MARKET = "US"


class SimFinLoader:
    """Bulk loader for simfin fundamental + price data.

    Uses simfin's functional API (``sf.load_income``, ``sf.load_shareprices``,
    etc.) rather than the deprecated ``BulkData`` class. Set the data dir
    + API key once in the constructor, then call the load methods.

    Parameters
    ----------
    data_dir : Path, optional
        Local cache directory for bulk data (default ``data/simfin``).
    market : str
        Market identifier (default ``US``). Other options: ``DE``, ``CN``.
    api_key : str, optional
        SimFin API key. Free tier allows bulk download with daily limits.
        If None, simfin reads from ``SIMFIN_API_KEY`` env var.
    """

    def __init__(
        self,
        *,
        data_dir: Path | str = DEFAULT_DATA_DIR,
        market: str = DEFAULT_MARKET,
        api_key: str | None = None,
    ) -> None:
        if not _HAS_SIMFIN:
            raise ImportError("simfin is not installed. Install with: uv add simfin")
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        sf.set_data_dir(str(self.data_dir))
        if api_key is not None:
            sf.set_api_key(api_key=api_key)
        self.market = market
        self._cache: dict[str, pl.DataFrame] = {}

    def _to_polars(self, df_pd: Any) -> pl.DataFrame:
        if isinstance(df_pd, pl.DataFrame):
            return df_pd
        try:
            return pl.from_pandas(df_pd)
        except Exception:
            return pl.DataFrame()

    def income_statements(self, *, refresh: bool = False) -> pl.DataFrame:
        """Bulk income statements (Revenue, Gross Profit, Net Income, etc.)."""
        cache_key = "income"
        if refresh or cache_key not in self._cache:
            df_pd = sf.load_income(variant="quarterly", market=self.market)
            self._cache[cache_key] = self._to_polars(df_pd)
        return self._cache[cache_key]

    def balance_sheets(self, *, refresh: bool = False) -> pl.DataFrame:
        """Bulk balance sheets (Assets, Liabilities, Equity, etc.)."""
        cache_key = "balance"
        if refresh or cache_key not in self._cache:
            df_pd = sf.load_balance(variant="quarterly", market=self.market)
            self._cache[cache_key] = self._to_polars(df_pd)
        return self._cache[cache_key]

    def cash_flows(self, *, refresh: bool = False) -> pl.DataFrame:
        """Bulk cash-flow statements (Operating CF, Capex, FCF, etc.)."""
        cache_key = "cashflow"
        if refresh or cache_key not in self._cache:
            df_pd = sf.load_cashflow(variant="quarterly", market=self.market)
            self._cache[cache_key] = self._to_polars(df_pd)
        return self._cache[cache_key]

    def daily_prices(self, *, refresh: bool = False) -> pl.DataFrame:
        """Bulk daily OHLCV share prices for all US companies.

        SimFin shareprices columns: SimFinId, Open, High, Low, Close,
        Adj. Close, Volume, Dividend, Shares Outstanding, Date.
        We rename ``Date`` → ``date`` for Oracle-internal consistency.
        Also reset_index to expose the Date (which is the pandas index).
        """
        cache_key = "prices"
        if refresh or cache_key not in self._cache:
            df_pd = sf.load_shareprices(variant="daily", market=self.market)
            # SimFin returns pandas with 'Date' as index — reset to column
            if (
                hasattr(df_pd, "index")
                and "Date" not in df_pd.columns
                and "date" not in df_pd.columns
            ):
                df_pd = df_pd.reset_index().rename(columns={"Date": "date"})
                # 'Report Date' or 'Publish Date' could also be the index name
                # try common SimFin names
                if "Report Date" in df_pd.columns:
                    df_pd = df_pd.rename(columns={"Report Date": "date"})
            df_pl = self._to_polars(df_pd)
            # Final fallback: if 'date' still not present, try renaming Date
            if "date" not in df_pl.columns and "Date" in df_pl.columns:
                df_pl = df_pl.rename({"Date": "date"})
            self._cache[cache_key] = df_pl
        return self._cache[cache_key]

    def companies(self, *, refresh: bool = False) -> pl.DataFrame:
        """Bulk company metadata (ticker, sector, industry, etc.)."""
        cache_key = "companies"
        if refresh or cache_key not in self._cache:
            df_pd = sf.load_companies(market=self.market)
            self._cache[cache_key] = self._to_polars(df_pd)
        return self._cache[cache_key]

    def universe(self) -> pl.DataFrame:
        """Return a deduplicated universe of tickers with sector info."""
        companies = self.companies()
        cols = companies.columns
        keep = [c for c in ["Ticker", "Company Name", "Sector", "Industry"] if c in cols]
        if not keep:
            return companies
        return companies.select(keep).unique()

    def filter_universe(
        self, *, sectors: Sequence[str] | None = None, tickers: Sequence[str] | None = None
    ) -> pl.DataFrame:
        """Filter universe by sectors or tickers."""
        u = self.universe()
        if sectors is not None and "Sector" in u.columns:
            u = u.filter(pl.col("Sector").is_in(list(sectors)))
        if tickers is not None and "Ticker" in u.columns:
            u = u.filter(pl.col("Ticker").is_in(list(tickers)))
        return u

    @staticmethod
    def is_available() -> bool:
        """Return True if simfin is installed and importable."""
        return _HAS_SIMFIN


def smoke_test() -> dict[str, Any]:
    """Smoke test: load income + prices, count rows. Returns structure
    without raising (network failures caught and reported as 'error')."""
    if not _HAS_SIMFIN:
        return {"available": False, "error": "simfin not installed"}
    try:
        loader = SimFinLoader()
        result: dict[str, Any] = {
            "available": True,
            "data_dir": str(loader.data_dir),
            "market": loader.market,
        }
        # Don't actually fetch unless data_dir has cached data — fetching
        # requires SIMFIN_API_KEY env var and network access.
        try:
            income = loader.income_statements()
            result["income_rows"] = income.height
            result["income_cols"] = income.columns[:8]
        except Exception as e:
            result["income_error"] = str(e)
        try:
            companies = loader.companies()
            result["companies_rows"] = companies.height
        except Exception as e:
            result["companies_error"] = str(e)
        return result
    except Exception as e:  # pragma: no cover
        return {"available": False, "error": str(e)}


__all__: list[str] = ["SimFinLoader", "smoke_test"]
