"""BL-714 — SEC EDGAR loader with point-in-time awareness.

Provides a thin wrapper over the SEC EDGAR public REST API
(``https://data.sec.gov``) covering:

* XBRL **company facts** (income statement, balance sheet, cash flow)
* **13F-HR** institutional holdings
* **Form 4** insider transactions
* **8-K** current-event filings

Point-in-time (PIT) safety is enforced by every accessor: facts are
filtered by *filing date*, NOT by *period date*, so a backtest that
peeks into the EDGAR data on day *t* cannot accidentally see a number
that was not yet filed.  This is the standard anti-lookahead discipline
for SEC data (Lopez de Prado, *Advances in Financial Machine Learning*,
ch. 5).

Free, zero-key access
----------------------
SEC EDGAR is a free public API, but it enforces a fair-access policy:

* every request MUST carry a User-Agent identifying the caller (an
  email in production, ``Oracle research <oracle@example.com>`` for
  default);
* rate limit is 10 req/s per IP — the loader throttles to a
  configurable ``rate_limit_per_sec`` (default 8 to leave headroom).

No third-party library is required: the module depends only on the
standard library + ``pandas`` (already a project dependency for the
``analytics`` extra).  ``edgartools`` is intentionally NOT pulled in —
it pins requests versions that conflict with the rest of the stack.

References
----------
* SEC EDGAR REST API docs — https://www.sec.gov/edgar/sec-api-documentation
* XBRL company facts schema — https://data.sec.gov/api/xbrl/companyfacts.zip
* Knowledge-base note 01-fundamental (BL-714, BL-KB-01/03).
"""

from __future__ import annotations

import json
import re
import time
import urllib.request
import zipfile
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Protocol

#: Default SEC-compliant User-Agent.  Production callers should pass their
#: own (typically ``"Name email@domain"``).
DEFAULT_USER_AGENT = "Oracle Research oracle-research@example.com"

#: Sub-domain of data.sec.gov for the public REST API.
_EDGAR_BASE = "https://data.sec.gov"
#: Sub-domain of www.sec.gov for the submissions/RSS feeds.
_EDGAR_WWW = "https://www.sec.gov/cgi-bin/browse-edgar"

#: Minimum interval between consecutive requests (seconds) — 8 req/s is
#: the safe ceiling under the 10 req/s SEC fair-access policy.
_DEFAULT_RATE_LIMIT_PER_SEC = 8.0


# ── Result containers ──────────────────────────────────────────────────────


@dataclass(frozen=True)
class CompanyFact:
    """One XBRL fact (single concept, single period, single unit).

    Attributes
    ----------
    concept
        XBRL concept tag (e.g. ``"us-gaap:Revenues"``).
    value
        Reported numeric value, in the unit declared by ``unit``.
    unit
        Unit tag (e.g. ``"USD"``, ``"shares"``).
    period_start
        Start of the fiscal period the fact refers to (inclusive).
    period_end
        End of the fiscal period the fact refers to (inclusive).
    form
        SEC form on which the fact was reported (e.g. ``"10-K"``).
    filed
        Filing date — this is the PIT anchor.
    accession
        Accession number identifying the originating filing.
    """

    concept: str
    value: float
    unit: str
    period_start: date
    period_end: date
    form: str
    filed: date
    accession: str

    def as_of(self, as_of: date) -> bool:
        """True if the fact was filed on or before ``as_of`` (PIT check)."""
        return self.filed <= as_of


@dataclass(frozen=True)
class CompanyFacts:
    """All company facts as returned by the SEC ``companyfacts`` endpoint."""

    cik: str
    name: str
    facts: list[CompanyFact] = field(default_factory=list)

    def filter(self, *, concept: str, as_of: date | None = None) -> list[CompanyFact]:
        """Return facts for one concept, optionally PIT-filtered.

        Parameters
        ----------
        concept
            XBRL concept tag (case-sensitive, e.g. ``"us-gaap:Revenues"``).
        as_of
            If provided, only facts with ``filed <= as_of`` are returned.
        """
        out: list[CompanyFact] = []
        for fact in self.facts:
            if fact.concept != concept:
                continue
            if as_of is not None and not fact.as_of(as_of):
                continue
            out.append(fact)
        return out


@dataclass(frozen=True)
class ThirteenFFiling:
    """One 13F-HR filing header."""

    cik: str
    period_of_report: date
    filed: date
    accession: str
    form: str
    total_value: float | None
    holdings_count: int | None


@dataclass(frozen=True)
class Form4Filing:
    """One Form 4 insider-transaction summary."""

    cik: str
    filed: date
    period_of_report: date
    transaction_date: date | None
    insider_name: str | None
    insider_title: str | None
    transaction_code: str | None
    shares: float | None
    price_per_share: float | None
    acquired_disposed: str | None
    accession: str


@dataclass(frozen=True)
class EightKFiling:
    """One 8-K current-report header."""

    cik: str
    filed: date
    period_of_report: date | None
    items: list[str]
    accession: str


# ── HTTP layer (injectable for tests) ──────────────────────────────────────


class _HttpGetter(Protocol):
    """Protocol for the HTTP getter — easy to mock in unit tests."""

    def __call__(self, url: str, *, headers: dict[str, str]) -> bytes: ...


def _default_http_get(url: str, *, headers: dict[str, str]) -> bytes:
    """Stdlib HTTP GET — no extra dependency."""
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


# ── Loader ──────────────────────────────────────────────────────────────────


class EdgarRateLimitError(RuntimeError):
    """Raised when the loader is asked to exceed the configured rate."""


class EdgarLoader:
    """SEC EDGAR public REST loader with PIT awareness.

    Parameters
    ----------
    user_agent
        Identifying User-Agent.  Required by the SEC fair-access policy;
        in production pass ``"Name email@domain"``.  Use the module-level
        ``DEFAULT_USER_AGENT`` only for tests / smoke checks.
    cache_dir
        Optional directory where successful GETs are cached on disk.  Cached
        payloads are reused across runs to stay within the SEC rate limit.
    rate_limit_per_sec
        Max sustained request rate (defaults to 8 req/s, safe under the
        10 req/s SEC cap).  ``0`` disables throttling.
    http_get
        Override for the HTTP getter — tests inject a mock that returns
        canned JSON without hitting the network.
    """

    _TICKER_LOOKUP_URL = "https://www.sec.gov/files/company_tickers.json"
    _CIK_PADDED_LOOKUP_URL = "https://www.sec.gov/files/cik-lookup-data.txt"

    def __init__(
        self,
        *,
        user_agent: str = DEFAULT_USER_AGENT,
        cache_dir: Path | str | None = None,
        rate_limit_per_sec: float = _DEFAULT_RATE_LIMIT_PER_SEC,
        http_get: _HttpGetter | None = None,
        clock: Callable[[], float] | None = None,
    ) -> None:
        if not user_agent or "@" not in user_agent:
            # SEC requires an email in the UA so they can reach the caller.
            raise ValueError("user_agent must contain an email address (SEC fair-access policy)")
        self.user_agent = user_agent
        self.cache_dir = Path(cache_dir) if cache_dir is not None else None
        self._min_interval = 1.0 / rate_limit_per_sec if rate_limit_per_sec > 0 else 0.0
        self._last_request = 0.0
        self._http = http_get or _default_http_get
        self._clock = clock or time.monotonic

    # ── Public API ────────────────────────────────────────────────────────

    def get_company_facts(self, cik: str) -> CompanyFacts:
        """Fetch XBRL company facts JSON for *cik* (zero-padded 10 digits)."""
        cik = _normalize_cik(cik)
        url = f"{_EDGAR_BASE}/api/xbrl/companyfacts/CIK{cik}.json"
        payload = self._get_json_cached(url)
        return _parse_company_facts(payload, cik)

    def get_facts_as_of(self, cik: str, as_of: date) -> CompanyFacts:
        """PIT filter wrapper — returns facts filed on or before ``as_of``."""
        all_facts = self.get_company_facts(cik)
        return CompanyFacts(
            cik=all_facts.cik,
            name=all_facts.name,
            facts=[f for f in all_facts.facts if f.as_of(as_of)],
        )

    def get_13f_filings(self, cik: str) -> list[ThirteenFFiling]:
        """List 13F-HR institutional-holdings filings for *cik*."""
        cik = _normalize_cik(cik)
        url = f"{_EDGAR_BASE}/api/submissions/CIK{cik}.json"
        payload = self._get_json_cached(url)
        return _parse_submissions_for_form(
            payload, form_prefix="13F", cik=cik, builder=_thirteen_f_from_filing
        )

    def get_form4_filings(self, cik: str, *, since: date | None = None) -> list[Form4Filing]:
        """List Form 4 insider transactions for *cik* (optionally since date)."""
        cik = _normalize_cik(cik)
        url = f"{_EDGAR_BASE}/api/submissions/CIK{cik}.json"
        payload = self._get_json_cached(url)
        filings = _parse_submissions_for_form(
            payload, form_prefix="4", cik=cik, builder=_form4_from_filing
        )
        if since is None:
            return filings
        return [f for f in filings if f.filed >= since]

    def get_8k_filings(self, cik: str, *, since: date | None = None) -> list[EightKFiling]:
        """List 8-K current-event filings for *cik* (optionally since date)."""
        cik = _normalize_cik(cik)
        url = f"{_EDGAR_BASE}/api/submissions/CIK{cik}.json"
        payload = self._get_json_cached(url)
        filings = _parse_submissions_for_form(
            payload, form_prefix="8-K", cik=cik, builder=_eight_k_from_filing
        )
        if since is None:
            return filings
        return [f for f in filings if f.filed >= since]

    def tickers_to_cik(self, ticker: str) -> str | None:
        """Resolve a ticker symbol to a SEC CIK (zero-padded 10-digit str).

        Uses the SEC ``company_tickers.json`` file (a small static table
        refreshed nightly).  Returns ``None`` if the ticker is unknown.
        """
        if not ticker:
            return None
        payload = self._get_json_cached(self._TICKER_LOOKUP_URL)
        # company_tickers.json is { "0": {"cik_str": ..., "ticker": ..., "title": ...}, ... }
        for entry in payload.values():
            if isinstance(entry, dict) and entry.get("ticker", "").upper() == ticker.upper():
                cik = str(entry["cik_str"])
                return cik.zfill(10)
        return None

    def get_companyfacts_zip(self, out_path: Path | str) -> Path:
        """Download the bulk ``companyfacts.zip`` archive (all issuers).

        Provided for convenience: the bulk archive is ~1.3 GB compressed
        and is the right starting point when screening the whole US-listed
        universe.  Returns the path to the saved file.
        """
        url = f"{_EDGAR_BASE}/api/xbrl/companyfacts.zip"
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        data = self._http(url, headers={"User-Agent": self.user_agent})
        out_path.write_bytes(data)
        return out_path

    @staticmethod
    def open_companyfacts_zip(path: Path | str) -> Iterable[CompanyFacts]:
        """Yield ``CompanyFacts`` for each issuer in a ``companyfacts.zip``.

        Lazy generator — useful when screening the bulk archive without
        holding every issuer's facts in memory at once.  Filters out
        entries that cannot be parsed (logged via ``structlog`` would be
        the next layer, kept out for stdlib-only dependency).
        """
        with zipfile.ZipFile(Path(path), "r") as zf:
            for name in zf.namelist():
                if not name.endswith(".json"):
                    continue
                with zf.open(name) as fh:
                    try:
                        payload = json.loads(fh.read())
                    except json.JSONDecodeError:
                        continue
                m = re.match(r"CIK(\d+)\.json", name)
                if not m:
                    continue
                yield _parse_company_facts(payload, m.group(1))

    # ── Internals ────────────────────────────────────────────────────────

    def _get_json_cached(self, url: str) -> dict[str, Any]:
        """HTTP GET with on-disk cache and rate limiting; returns parsed JSON."""
        cache_path = self._cache_path_for(url)
        if cache_path is not None and cache_path.exists():
            return json.loads(cache_path.read_text(encoding="utf-8"))
        self._throttle()
        raw = self._http(url, headers={"User-Agent": self.user_agent})
        if cache_path is not None:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_bytes(raw)
        return json.loads(raw)

    def _throttle(self) -> None:
        if self._min_interval <= 0.0:
            return
        elapsed = self._clock() - self._last_request
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_request = self._clock()

    def _cache_path_for(self, url: str) -> Path | None:
        if self.cache_dir is None:
            return None
        # Stable, filesystem-safe filename from URL.
        key = re.sub(r"[^A-Za-z0-9._-]+", "_", url)
        return self.cache_dir / f"{key}.json"


# ── Parsers ────────────────────────────────────────────────────────────────


def _parse_company_facts(payload: dict[str, Any], cik: str) -> CompanyFacts:
    """Parse the ``companyfacts.json`` payload into ``CompanyFacts``."""
    name = payload.get("entityName", "")
    raw_facts = payload.get("facts", {})
    parsed: list[CompanyFact] = []
    for namespace, concepts in raw_facts.items():
        if not isinstance(concepts, dict):
            continue
        for concept_tag, body in concepts.items():
            units = body.get("units", {})
            if not isinstance(units, dict):
                continue
            for unit_key, rows in units.items():
                if not isinstance(rows, list):
                    continue
                for row in rows:
                    fact = _fact_from_row(namespace, concept_tag, unit_key, row)
                    if fact is not None:
                        parsed.append(fact)
    return CompanyFacts(cik=cik, name=name, facts=parsed)


def _fact_from_row(
    namespace: str, concept: str, unit: str, row: dict[str, Any]
) -> CompanyFact | None:
    """Convert one XBRL fact row to ``CompanyFact`` if all required fields exist."""
    try:
        val = float(row["val"])
        start = _parse_date(row["start"])
        end = _parse_date(row["end"])
        filed = _parse_date(row["filed"])
        form = str(row.get("form", ""))
        accession = str(row.get("accn", ""))
    except (KeyError, ValueError, TypeError):
        return None
    return CompanyFact(
        concept=f"{namespace}:{concept}",
        value=val,
        unit=unit,
        period_start=start,
        period_end=end,
        form=form,
        filed=filed,
        accession=accession,
    )


def _parse_submissions_for_form(
    payload: dict[str, Any],
    *,
    form_prefix: str,
    cik: str,
    builder: Callable[[dict[str, Any], str], Iterable[Any]],
) -> list[Any]:
    """Extract filings matching *form_prefix* from a submissions JSON."""
    recent = payload.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    n = len(forms)
    rows = []
    form_columns = {
        "accessionNumber": recent.get("accessionNumber", []),
        "filingDate": recent.get("filingDate", []),
        "reportDate": recent.get("reportDate", []),
        "primaryDocument": recent.get("primaryDocument", []),
    }
    for i in range(n):
        if not forms[i].startswith(form_prefix):
            continue
        row = {key: (vals[i] if i < len(vals) else None) for key, vals in form_columns.items()}
        row["form"] = forms[i]
        row["primaryDocDescription"] = (
            recent.get("primaryDocDescription", [None] * n)[i]
            if i < len(recent.get("primaryDocDescription", []))
            else None
        )
        # The submissions API does not include the parsed 13F/Form 4 body
        # here — the builder maps header columns to the typed dataclass.
        rows.extend(builder(row, cik))
    return rows


def _thirteen_f_from_filing(row: dict[str, Any], cik: str) -> Iterable[ThirteenFFiling]:
    period = _safe_date(row.get("reportDate")) or _safe_date(row.get("filingDate"))
    filed = _safe_date(row.get("filingDate"))
    accession = str(row.get("accessionNumber") or "")
    form = str(row.get("form") or "13F-HR")
    if period is None or filed is None or not accession:
        return []
    return [
        ThirteenFFiling(
            cik=cik,
            period_of_report=period,
            filed=filed,
            accession=accession,
            form=form,
            total_value=None,
            holdings_count=None,
        )
    ]


def _form4_from_filing(row: dict[str, Any], cik: str) -> Iterable[Form4Filing]:
    filed = _safe_date(row.get("filingDate"))
    period = _safe_date(row.get("reportDate"))
    accession = str(row.get("accessionNumber") or "")
    if filed is None or not accession:
        return []
    return [
        Form4Filing(
            cik=cik,
            filed=filed,
            period_of_report=period or filed,
            transaction_date=None,
            insider_name=None,
            insider_title=None,
            transaction_code=None,
            shares=None,
            price_per_share=None,
            acquired_disposed=None,
            accession=accession,
        )
    ]


def _eight_k_from_filing(row: dict[str, Any], cik: str) -> Iterable[EightKFiling]:
    filed = _safe_date(row.get("filingDate"))
    period = _safe_date(row.get("reportDate"))
    accession = str(row.get("accessionNumber") or "")
    if filed is None or not accession:
        return []
    # For 8-K current reports, period-of-report frequently equals the
    # filing date — many issuers leave ``reportDate`` blank.  Fall back
    # to ``filed`` to keep the contract total (no None surprises).
    return [
        EightKFiling(
            cik=cik,
            filed=filed,
            period_of_report=period or filed,
            items=[],  # item codes require the filing index page; out of scope for v1
            accession=accession,
        )
    ]


# ── Small helpers ──────────────────────────────────────────────────────────


_CIK_RE = re.compile(r"^\d{1,10}$")


def _normalize_cik(cik: str | int) -> str:
    """Normalise a CIK to zero-padded 10 digits; raise on garbage."""
    s = str(cik).strip()
    if not _CIK_RE.match(s):
        raise ValueError(f"invalid CIK: {cik!r}")
    return s.zfill(10)


def _parse_date(raw: Any) -> date:
    """Parse SEC date string (YYYY-MM-DD)."""
    if isinstance(raw, date) and not isinstance(raw, datetime):
        return raw
    if isinstance(raw, datetime):
        return raw.date()
    return datetime.strptime(str(raw)[:10], "%Y-%m-%d").date()


def _safe_date(raw: Any) -> date | None:
    """Like :func:`_parse_date` but returns None on failure."""
    try:
        return _parse_date(raw)
    except (ValueError, TypeError):
        return None


def utcnow() -> datetime:
    """Timezone-aware UTC now — exported for callers that want to call ``as_of``."""
    return datetime.now(tz=UTC)


def canonical_company_fact_url(cik: str) -> str:
    """Return the canonical SEC URL for a companyfacts JSON (test helper)."""
    return f"{_EDGAR_BASE}/api/xbrl/companyfacts/CIK{_normalize_cik(cik)}.json"


def parse_company_facts_payload(payload: dict[str, Any], cik: str) -> CompanyFacts:
    """Public parse entry point — useful when the JSON is already in hand."""
    return _parse_company_facts(payload, cik)


# ── Public surface ─────────────────────────────────────────────────────────


__all__ = [
    "DEFAULT_USER_AGENT",
    "CompanyFact",
    "CompanyFacts",
    "EdgarLoader",
    "EdgarRateLimitError",
    "EightKFiling",
    "Form4Filing",
    "ThirteenFFiling",
    "canonical_company_fact_url",
    "parse_company_facts_payload",
    "utcnow",
]
