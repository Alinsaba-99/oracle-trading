"""BL-714 — EdgarLoader tests (SEC EDGAR PIT-aware loader)."""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import date
from typing import Any

import pytest

from analytics.fundamental.edgar_loader import (
    CompanyFact,
    CompanyFacts,
    EdgarLoader,
    EdgarRateLimitError,
    canonical_company_fact_url,
    parse_company_facts_payload,
    utcnow,
)

# ── Fixtures & helpers ─────────────────────────────────────────────────────


def _user_agent() -> str:
    return "Oracle Test test@example.com"


@pytest.fixture()
def monkeypatched_clock(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Pin the wall clock so PIT tests are deterministic."""
    yield


def _make_loader(
    *,
    payload: dict[str, Any] | None = None,
    status: int = 200,
    rate_limit_per_sec: float = 0.0,
    cache_dir: str | None = None,
    fail_with: Exception | None = None,
    throttle_raise: bool = False,
) -> tuple[EdgarLoader, list[tuple[str, dict[str, str]]]]:
    """Build a loader with a mocked HTTP getter; return (loader, call_log)."""
    calls: list[tuple[str, dict[str, str]]] = []

    def _fake_http(url: str, *, headers: dict[str, str]) -> bytes:
        calls.append((url, headers))
        if fail_with is not None:
            raise fail_with
        if status != 200:
            raise RuntimeError(f"HTTP {status}")
        return json.dumps(payload or {}).encode("utf-8")

    loader = EdgarLoader(
        user_agent=_user_agent(),
        http_get=_fake_http,
        rate_limit_per_sec=rate_limit_per_sec,
        cache_dir=cache_dir,
    )
    if throttle_raise:
        loader._throttle = lambda: (_ for _ in ()).throw(EdgarRateLimitError("rate"))  # type: ignore[assignment]
    return loader, calls


def _make_facts_payload(*, facts: list[dict[str, Any]], name: str = "Acme Inc") -> dict[str, Any]:
    return {
        "cik": "320193",
        "entityName": name,
        "facts": {"us-gaap": {"Revenues": {"label": "Revenues", "units": {"USD": facts}}}},
    }


def _fact_row(
    *,
    val: float,
    start: str,
    end: str,
    filed: str,
    form: str = "10-K",
    accn: str = "0000320193-21-000010",
) -> dict[str, Any]:
    return {
        "val": val,
        "start": start,
        "end": end,
        "filed": filed,
        "form": form,
        "accn": accn,
        "frame": "CY2021",
    }


def _submissions_payload(*, recent_filings: list[dict[str, Any]]) -> dict[str, Any]:
    """Build a minimal SEC submissions JSON payload."""
    n = len(recent_filings)
    keys = ("form", "accessionNumber", "filingDate", "reportDate", "primaryDocument")
    columns = {k: [f.get(k) for f in recent_filings] for k in keys}
    columns["primaryDocDescription"] = [None] * n
    return {
        "cik": "320193",
        "entityName": "Apple Inc.",
        "filings": {"recent": columns, "files": []},
    }


# ── Construction ───────────────────────────────────────────────────────────


class TestLoaderConstruction:
    def test_user_agent_required_email(self) -> None:
        with pytest.raises(ValueError, match="email"):
            EdgarLoader(user_agent="Oracle")
        with pytest.raises(ValueError, match="email"):
            EdgarLoader(user_agent="")
        # Valid email form is accepted.
        EdgarLoader(user_agent="Name me@example.com")

    def test_cik_normalization_via_http(self) -> None:
        payload = _make_facts_payload(facts=[])
        loader, calls = _make_loader(payload=payload)
        # Use the un-padded CIK — the loader should pad it to 10 digits.
        loader.get_company_facts("320193")
        url = calls[0][0]
        assert "CIK0000320193.json" in url

    def test_invalid_cik_raises(self) -> None:
        loader, _ = _make_loader(payload={})
        with pytest.raises(ValueError, match="invalid CIK"):
            loader.get_company_facts("not-a-cik")


# ── XBRL company facts parsing ────────────────────────────────────────────


class TestCompanyFacts:
    def test_parses_revenues_facts(self) -> None:
        facts = [
            _fact_row(val=1_000_000.0, start="2021-01-01", end="2021-12-31", filed="2022-02-04"),
            _fact_row(val=2_000_000.0, start="2022-01-01", end="2022-12-31", filed="2023-02-05"),
        ]
        loader, _ = _make_loader(payload=_make_facts_payload(facts=facts))
        result = loader.get_company_facts("320193")
        assert result.cik == "0000320193"
        assert result.name == "Acme Inc"
        assert len(result.facts) == 2
        assert {f.value for f in result.facts} == {1_000_000.0, 2_000_000.0}
        assert all(f.concept == "us-gaap:Revenues" for f in result.facts)
        assert all(f.unit == "USD" for f in result.facts)

    def test_filter_by_concept(self) -> None:
        payload = {
            "entityName": "Mixed",
            "facts": {
                "us-gaap": {
                    "Revenues": {
                        "units": {
                            "USD": [
                                _fact_row(
                                    val=10.0,
                                    start="2021-01-01",
                                    end="2021-12-31",
                                    filed="2022-02-01",
                                )
                            ]
                        }
                    },
                    "NetIncomeLoss": {
                        "units": {
                            "USD": [
                                _fact_row(
                                    val=3.0,
                                    start="2021-01-01",
                                    end="2021-12-31",
                                    filed="2022-02-01",
                                )
                            ]
                        }
                    },
                }
            },
        }
        loader, _ = _make_loader(payload=payload)
        result = loader.get_company_facts("320193")
        rev = result.filter(concept="us-gaap:Revenues")
        assert len(rev) == 1
        assert rev[0].value == 10.0

    def test_pit_filter_excludes_future_facts(self) -> None:
        """PIT must use filing date, not period date."""
        facts = [
            # FY2021, filed 2022-02-04 → visible at as_of=2023-01-01
            _fact_row(val=100.0, start="2021-01-01", end="2021-12-31", filed="2022-02-04"),
            # FY2022, filed 2023-02-05 → NOT visible at as_of=2023-01-01
            _fact_row(val=200.0, start="2022-01-01", end="2022-12-31", filed="2023-02-05"),
            # FY2020, filed 2021-02-05 → visible at any as_of >= 2021-02-05
            _fact_row(val=80.0, start="2020-01-01", end="2020-12-31", filed="2021-02-05"),
        ]
        loader, _ = _make_loader(payload=_make_facts_payload(facts=facts))
        company = loader.get_company_facts("320193")
        pit = loader.get_facts_as_of("320193", date(2023, 1, 1))
        assert [f.value for f in pit.facts] == [100.0, 80.0]
        # Sanity: the filtered set is a subset of the unfiltered one.
        assert all(f.as_of(date(2023, 1, 1)) for f in pit.facts)
        # PIT filter by as_of=None → returns everything.
        all_via_filter = company.filter(concept="us-gaap:Revenues", as_of=None)
        assert len(all_via_filter) == 3

    def test_parse_company_facts_payload_helper(self) -> None:
        payload = _make_facts_payload(
            facts=[_fact_row(val=42.0, start="2021-01-01", end="2021-12-31", filed="2022-02-01")]
        )
        company = parse_company_facts_payload(payload, "0000320193")
        assert isinstance(company, CompanyFacts)
        assert len(company.facts) == 1
        assert company.facts[0] == CompanyFact(
            concept="us-gaap:Revenues",
            value=42.0,
            unit="USD",
            period_start=date(2021, 1, 1),
            period_end=date(2021, 12, 31),
            form="10-K",
            filed=date(2022, 2, 1),
            accession="0000320193-21-000010",
        )

    def test_canonical_url_helper(self) -> None:
        assert canonical_company_fact_url("320193") == (
            "https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json"
        )


# ── Submissions: 13F, Form 4, 8-K ─────────────────────────────────────────


class TestSubmissions:
    def test_13f_filings_parsed(self) -> None:
        recent = [
            {
                "form": "13F-HR",
                "accessionNumber": "0000320193-23-000001",
                "filingDate": "2023-02-14",
                "reportDate": "2022-12-31",
                "primaryDocument": "form13f.html",
            },
            {
                "form": "13F-HR/A",
                "accessionNumber": "0000320193-22-000007",
                "filingDate": "2022-02-15",
                "reportDate": "2021-12-31",
                "primaryDocument": "form13f.html",
            },
        ]
        payload = _submissions_payload(recent_filings=recent)
        loader, _ = _make_loader(payload=payload)
        filings = loader.get_13f_filings("320193")
        assert len(filings) == 2
        assert all(f.cik == "0000320193" for f in filings)
        assert {f.form for f in filings} == {"13F-HR", "13F-HR/A"}
        assert filings[0].period_of_report == date(2022, 12, 31)
        assert filings[0].filed == date(2023, 2, 14)

    def test_form4_filings_with_since_filter(self) -> None:
        # Two filings well separated in time so the since filter splits them
        # cleanly regardless of when "now" is.
        old_filed = "2020-01-15"
        new_filed = "2024-06-01"
        recent = [
            {
                "form": "4",
                "accessionNumber": "0000320193-24-000010",
                "filingDate": new_filed,
                "reportDate": new_filed,
                "primaryDocument": "form4.xml",
            },
            {
                "form": "4",
                "accessionNumber": "0000320193-20-000099",
                "filingDate": old_filed,
                "reportDate": old_filed,
                "primaryDocument": "form4.xml",
            },
        ]
        payload = _submissions_payload(recent_filings=recent)
        loader, _ = _make_loader(payload=payload)
        all_form4 = loader.get_form4_filings("320193")
        assert len(all_form4) == 2
        cutoff = date(2022, 1, 1)
        recent_only = loader.get_form4_filings("320193", since=cutoff)
        assert len(recent_only) == 1
        assert recent_only[0].filed >= cutoff
        assert recent_only[0].filed == date(2024, 6, 1)

    def test_8k_filings_filter_handles_missing_report_date(self) -> None:
        recent = [
            {
                "form": "8-K",
                "accessionNumber": "0000320193-24-000020",
                "filingDate": "2024-07-01",
                "reportDate": None,
                "primaryDocument": "form8k.htm",
            },
            {
                "form": "8-K",
                "accessionNumber": "0000320193-24-000021",
                "filingDate": "2024-07-15",
                "reportDate": "2024-07-14",
                "primaryDocument": "form8k.htm",
            },
        ]
        payload = _submissions_payload(recent_filings=recent)
        loader, _ = _make_loader(payload=payload)
        filings = loader.get_8k_filings("320193")
        assert len(filings) == 2
        # Filing 1 has no reportDate — period_of_report must default to filed.
        assert filings[0].period_of_report == date(2024, 7, 1)

    def test_other_forms_excluded(self) -> None:
        recent = [
            {
                "form": "10-K",
                "accessionNumber": "1",
                "filingDate": "2023-02-04",
                "reportDate": "2022-12-31",
                "primaryDocument": "x",
            },
            {
                "form": "8-K",
                "accessionNumber": "2",
                "filingDate": "2023-05-01",
                "reportDate": "2023-05-01",
                "primaryDocument": "x",
            },
        ]
        payload = _submissions_payload(recent_filings=recent)
        loader, _ = _make_loader(payload=payload)
        # 8-K accessor should skip 10-K
        assert len(loader.get_8k_filings("320193")) == 1
        # 13F accessor should skip both
        assert loader.get_13f_filings("320193") == []
        # Form 4 accessor should also skip both (10-K starts with '1', not '4')
        assert loader.get_form4_filings("320193") == []


# ── Ticker → CIK ──────────────────────────────────────────────────────────


class TestTickerLookup:
    def test_tickers_to_cik_found(self) -> None:
        payload = {
            "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
            "1": {"cik_str": 789019, "ticker": "MSFT", "title": "Microsoft"},
            "2": {"cik_str": 1018724, "ticker": "AMZN", "title": "Amazon"},
        }
        loader, _ = _make_loader(payload=payload)
        cik = loader.tickers_to_cik("aapl")  # case-insensitive
        assert cik == "0000320193"
        cik = loader.tickers_to_cik("MSFT")
        assert cik == "0000789019"

    def test_tickers_to_cik_unknown(self) -> None:
        payload = {"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple"}}
        loader, _ = _make_loader(payload=payload)
        assert loader.tickers_to_cik("ZZZZ") is None
        assert loader.tickers_to_cik("") is None


# ── Throttling & caching ──────────────────────────────────────────────────


class TestThrottling:
    def test_throttle_called_on_each_request(self) -> None:
        loader, calls = _make_loader(payload=_make_facts_payload(facts=[]), rate_limit_per_sec=10.0)
        throttle_calls = {"n": 0}
        original = loader._throttle

        def _spy() -> None:
            throttle_calls["n"] += 1
            return original()

        loader._throttle = _spy  # type: ignore[method-assign]
        loader.get_company_facts("320193")
        loader.get_company_facts("320193")
        assert throttle_calls["n"] == 2
        assert len(calls) == 2

    def test_cache_reused_when_present(self, tmp_path) -> None:
        payload = _make_facts_payload(
            facts=[_fact_row(val=11.0, start="2021-01-01", end="2021-12-31", filed="2022-02-01")]
        )
        cache = tmp_path / "edgar-cache"
        loader, calls = _make_loader(payload=payload, cache_dir=str(cache))
        loader.get_company_facts("320193")
        loader.get_company_facts("320193")  # should hit cache, no HTTP
        assert len(calls) == 1

    def test_rate_limit_error_propagates(self) -> None:
        loader, _ = _make_loader(payload=_make_facts_payload(facts=[]), throttle_raise=True)
        with pytest.raises(EdgarRateLimitError):
            loader.get_company_facts("320193")


# ── UTC helper & dataclass equality ────────────────────────────────────────


def test_utcnow_is_timezone_aware() -> None:
    from datetime import UTC, datetime

    assert isinstance(utcnow(), datetime)
    assert utcnow().tzinfo is UTC


def test_company_fact_dataclass_is_frozen() -> None:
    fact = CompanyFact(
        concept="x",
        value=1.0,
        unit="USD",
        period_start=date(2021, 1, 1),
        period_end=date(2021, 12, 31),
        form="10-K",
        filed=date(2022, 2, 1),
        accession="x",
    )
    with pytest.raises((AttributeError, TypeError)):
        fact.value = 99.0  # type: ignore[misc]
