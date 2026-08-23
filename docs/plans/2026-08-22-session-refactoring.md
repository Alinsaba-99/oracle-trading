# Sessione refactoring 2026-08-22 — Edge Factory Stage 1 + acquisizioni + fixture prop-firm

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Popolare l'Edge Research Factory (registry con ipotesi dai 3 corpus locali + IC screen pre-registrato), acquisire i Tier-1 quantstats/ffn per i report factory, e codificare le fixture prop-firm verificate da BL-720 — tutto dentro i piani già approvati (design factory 2026-08-21, decisioni D1-D5 §10 SISTEMA-PROP-FIRM).

**Architecture:** La factory è una catena a 5 stadi: corpus mining → amplificazione → adapter → qualificazione → dual channel. Questa sessione sblocca la catena dall'inizio (Stage 1: registry YAML per dominio) e a monte della qualificazione (IC screen BL-706 + tearsheet BL-711). In parallelo, la sequenza prop-firm S2 richiede le fixture BL-721 (i numeri verificati §11 esistono già in `docs/firm_sources/`).

**Tech Stack:** Python 3.12, uv, pydantic v2, yaml, pandas/numpy/scipy (già dep), quantstats (Apache-2.0) + ffn (MIT) — nuove da acquisire.

**Spec:** `docs/plans/2026-08-21-edge-research-factory-design.md` (factory) · `trading-os/probe/eval/SISTEMA-PROP-FIRM.md` §10-§11 (prop-firm) · `trading-os/probe/eval/VALUTAZIONE-F.md` §F.4 Tier-1 (acquisizioni).

## Global Constraints

- **$0/mese** (ADR-020): nessuna dipendenza/servizio a pagamento; quantstats+ffn sono OSS $0.
- **ruff + ruff format + mypy --strict** verdi sui path toccati; pre-commit (gitleaks, large-files) attivo.
- Commit: `feat(BL-NNN): …` / `fix(BL-NNN): …` — un commit per BL.
- **Web untrusted**: nessun numero entra nel codice senza snapshot/sha256 in `docs/firm_sources/`.
- **Mai claim non verificati**: risultati negativi documentati; registry append-only.
- Suite baseline: 3019 passed (2026-08-21) — rieseguita in apertura sessione, deve restare verde.
- Le decisioni D1-D5 e il design factory sono **approvati: si esegue, non si ridiscute**.

## Ordine di esecuzione e perché

Raccomandazione: **si parte da BL-701+702 (miner del corpus locale)**. Sono il collo di bottiglia dell'intera catena factory: senza ipotesi nel registry, Stage 2 (amplificazione), 3 (adapter), 4 (qualificazione: BL-706/707/708) e 5 (dual channel, il kill-switch del farm prop-firm D4/D5 dipende da "≥1 segnale che passa IC screen") non hanno input. Costo zero (tutti i corpus sono in casa), zero dipendenze esterne. Subito prima, BL-711 (quantstats+ffn, ~30 min) come quick win: i report BL-708 dovranno produrre tearsheet, e il fumo py3.12 su quantstats (notoriamente fragile con numpy/pandas recenti) è un rischio da bruciare subito.

Dopo: BL-706 (IC screen, TDD, indipendente da Stage 1) → BL-721 (fixture dai dati §11 già verificati) → BL-707 (haircut Sharpe) se resta budget. **Fuori da questa sessione**, ognuno col proprio piano dedicato: BL-704 (amplificazione: batteria search MCP, sessione semi-manuale), BL-705 (dopo 704), BL-703 (P2), BL-722 (governor, dopo 721), BL-723 (spike MT5/Wine), BL-615 residuo (wrapper runner legacy), BL-718 (distillazione + cancellazione repo — distruttiva, sessione dedicata).

---

### Task 1: BL-711 — quantstats + ffn (tearsheet per report factory)

**Files:**
- Modify: `pyproject.toml` (via `uv add quantstats ffn`)
- Create: `analytics/research/factory/tearsheet.py`
- Test: `tests/unit/test_edge_factory_tearsheet.py`

**Interfaces:**
- Consumes: equity curve (`pd.Series` con `DatetimeIndex`) dal runner canonico BL-615.
- Produces: `render_html_tearsheet(equity: pd.Series, out_path: str | Path, title: str) -> Path`; `ffn_stats(equity: pd.Series) -> dict[str, float]` (chiavi: `cagr`, `calmar`, `max_drawdown`, `sharpe`).

- [ ] **Step 1.1: failing test** — `tests/unit/test_edge_factory_tearsheet.py`:

```python
"""BL-711 — quantstats+ffn tearsheet smoke (diagnostic only, ADR-021 canonical metrics stay authoritative)."""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from analytics.research.factory.tearsheet import ffn_stats, render_html_tearsheet


def _synthetic_equity(n: int = 300, seed: int = 11) -> pd.Series:
    idx = pd.date_range("2024-01-01", periods=n, freq="D", name="date")
    rng = np.random.default_rng(seed)
    rets = 0.0008 + 0.010 * rng.standard_normal(n)
    return pd.Series(100.0 * np.cumprod(1.0 + rets), index=idx, name="equity")


def test_html_tearsheet_written(tmp_path: Path) -> None:
    out = render_html_tearsheet(_synthetic_equity(), tmp_path / "t.html", "BL-711 smoke")
    assert out.exists()
    assert out.stat().st_size > 5_000
    html = out.read_text(encoding="utf-8")
    assert "Sharpe" in html


def test_ffn_stats_finite() -> None:
    stats = ffn_stats(_synthetic_equity())
    assert set(stats) == {"cagr", "calmar", "max_drawdown", "sharpe"}
    assert all(math.isfinite(v) for v in stats.values())


def test_tearsheet_does_not_import_canonical_metrics() -> None:
    """AC BL-711: NON sostituisce analytics/metrics/canonical.py."""
    import analytics.research.factory.tearsheet as mod

    src = Path(sys.modules[mod.__name__].__file__ or "").read_text(encoding="utf-8")
    assert "analytics.metrics" not in src
```

- [ ] **Step 1.2: run → FAIL** (`uv run pytest tests/unit/test_edge_factory_tearsheet.py -v` — ModuleNotFoundError).
- [ ] **Step 1.3: acquisizione** — `uv add quantstats ffn`; verificare licenze nei metadati (quantstats Apache-2.0, ffn MIT — LICENSE presente nel wheel); annotare le versioni risolte nel report di commit. Se quantstats rompe su numpy/pandas correnti (rischio noto), documentare l'errore e pinizzare la versione minima che passa lo smoke; se nessuna versione passa → BL-711 documentato bloccato con evidenza, si prosegue col resto (fallback: solo `ffn` + report tabellare).
- [ ] **Step 1.4: implementazione** — `analytics/research/factory/tearsheet.py`:

```python
"""BL-711 — Tearsheet rendering (quantstats + ffn) for edge-factory reports.

quantstats renders the HTML tearsheet; ffn computes the summary stats
table.  Diagnostic layer only: ``analytics/metrics/canonical.py`` (ADR-021)
stays the single source of truth for every qualification number.
"""
from __future__ import annotations

from pathlib import Path

import ffn
import pandas as pd
import quantstats as qs


def _require_datetime_index(equity: pd.Series) -> None:
    if not isinstance(equity.index, pd.DatetimeIndex):
        raise TypeError("equity series must have a DatetimeIndex")


def _to_returns(equity: pd.Series) -> pd.Series:
    _require_datetime_index(equity)
    rets = equity.pct_change().dropna()
    rets.name = "strategy"
    return rets


def render_html_tearsheet(equity: pd.Series, out_path: str | Path, title: str) -> Path:
    """Write a quantstats HTML tearsheet for *equity*; returns the path."""
    rets = _to_returns(equity)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    qs.reports.html(rets, output=str(out), title=title)
    return out


def ffn_stats(equity: pd.Series) -> dict[str, float]:
    """ffn summary stats (diagnostic; canonical metrics live elsewhere)."""
    _require_datetime_index(equity)
    st = ffn.calc_stats(equity)
    return {
        "cagr": float(st.cagr),
        "calmar": float(st.calmar),
        "max_drawdown": float(st.max_drawdown),
        "sharpe": float(st.sharpe),
    }
```

- [ ] **Step 1.5: run → PASS**; poi `ruff check analytics/research/factory/tearsheet.py tests/unit/test_edge_factory_tearsheet.py && ruff format … && uv run mypy analytics/research/factory/tearsheet.py` (strict sul path toccato).
- [ ] **Step 1.6: smoke end-to-end minimo** — script `scripts/smoke_tearsheet_bl711.py` che genera una equity sintetica e scrive `logs/edge-factory/bl711-smoke.html` (logs/ è gitignored: è output, non report). Run verificato exit 0.
- [ ] **Step 1.7: commit** `feat(BL-711): quantstats+ffn tearsheet diagnostico per report factory`.

---

### Task 2: BL-701 — KB miner (13 domini → registry)

**Files:**
- Create: `docs/knowledge-base/edge-factory/registry/<dominio>.yaml` × 13 (slugs = directory KB: `01-fundamental` … `13-meta-synthesis`)
- Test: `tests/unit/test_edge_factory_corpus.py`
- Read (input, non si modifica): `docs/knowledge-base/<dominio>/{README,edge,literature}.md`, `docs/knowledge-base/AUDIT-2026-08-17.md` (gap BL-KB-99..115 = ipotesi già triaged — priorità).

**Interfaces:**
- Consumes: `analytics.research/factory/registry.py` (BL-700: `Hypothesis`, `DomainRegistry`, `save_registry`, `load_registry`) — invariato.
- Produces: 13 YAML con `schema_version: 1`, `domain: <slug>`, ipotesi `EF-001…` stato `da_amplificare`, `origine: kb`, `evidenza[0].tipo == "miner"` con ref al file KB di origine.

Procedura (il "miner" è curato LLM-in-the-loop, conforme a Modo A: l'estrazione leggendo la KB è il lavoro; il codice valida):
- [ ] **Step 2.1: failing test** — `tests/unit/test_edge_factory_corpus.py`:

```python
"""BL-701/702 — corpus registry invariants (mining output validation)."""
from __future__ import annotations

from pathlib import Path

import pytest

from analytics.research.factory.registry import load_registry

REGISTRY_DIR = Path("docs/knowledge-base/edge-factory/registry")

KB_DOMAINS = [
    "01-fundamental", "02-macro", "03-quant", "04-order-flow",
    "05-sentiment", "06-positioning", "07-news", "08-intermarket",
    "09-cyclical", "10-seasonal", "11-onchain", "12-behavioral",
    "13-meta-synthesis",
]
ALL_DOMAINS = KB_DOMAINS + ["crypto-microstructure"]


def test_registry_files_match_expected_domains() -> None:
    found = sorted(p.stem for p in REGISTRY_DIR.glob("*.yaml"))
    assert found == sorted(ALL_DOMAINS)


@pytest.mark.parametrize("domain", ALL_DOMAINS)
def test_min_one_hypothesis_per_domain(domain: str) -> None:
    reg = load_registry(REGISTRY_DIR / f"{domain}.yaml")
    assert len(reg.hypotheses) >= 1
    for h in reg.hypotheses:
        assert len(h.meccanismo) >= 10
        assert h.dati_richiesti, f"{h.id}: dati_richiesti vuoto"
        assert h.stato == "da_amplificare"
        assert h.evidenza and h.evidenza[0].tipo == "miner"


def test_kb_total_hypotheses_at_least_26() -> None:
    """AC: ≥1/dominio; target di sessione: media ≥2/dominio sui 13 KB."""
    total = 0
    for d in KB_DOMAINS:
        total += len(load_registry(REGISTRY_DIR / f"{d}.yaml").hypotheses)
    assert total >= 26
```

- [ ] **Step 2.2: run → FAIL** (nessun YAML presente).
- [ ] **Step 2.3: estrazione** — dispatch di 4 subagent paralleli (3-4 domini ciascuno). Ogni subagent legge i file KB del dominio assegnato e restituisce 2-4 ipotesi in YAML valido per lo schema. Campi obbligatori e onesti: `meccanismo` (economico, non tautologico), `perche_esiste`, `dati_richiesti` (solo fonti $0 possedute o ottenibili: lake parquet, Binance Vision, FRED vintage, SimFin, IBKR going-forward), `asset_candidati`, `timeframe`, `decay_atteso_pct` (default 30; 40+ se il fattore è famoso/crowded), `fonti` (path KB specifici), `effect_size_dichiarata` (dal paper, o `non_quantificata`). Priorità dall'audit: BL-KB-102 VPIN (04), BL-KB-103 V&M everywhere (01/12), BL-KB-99..106. Le ipotesi che richiedono dati paywalled (es. L2 US) vanno incluse con `dati_posseduti: false` e note su cosa le sblocca (VPIN su L1 è la riscrittura consentita).
- [ ] **Step 2.4: merge + validazione** — per ogni dominio: `DomainRegistry(domain=<slug>)`, `add(Hypothesis(...))` con `evidenza=[Evidence.now("miner", "estratta da <file>", ref="<path KB>")]`, `save_registry("docs/knowledge-base/edge-factory/registry/<slug>.yaml", …)`. Run test → PASS.
- [ ] **Step 2.5: lint/type** sui path toccati (solo il test file nuovo: ruff + mypy strict).
- [ ] **Step 2.6: commit** `feat(BL-701): KB miner — 13 domini → registry ipotesi (N entry totali)`.

---

### Task 3: BL-702 — MoonDev miner (practitioner → registry)

**Files:**
- Create: `docs/knowledge-base/edge-factory/registry/crypto-microstructure.yaml`
- Modify: `tests/unit/test_edge_factory_corpus.py` (test specifici practitioner)

**Interfaces:**
- Consumes: stesso registry BL-700.
- Produces: il dominio `crypto-microstructure` con i 5 fattori triaged: `funding-extremum-reversal`, `liquidation-cascade-reversal`, `bb-squeeze-release`, `cvd-divergence`, `session-seasonality` (+ eventuali altri da RISPOSTE_D1-D15).

- [ ] **Step 3.1: failing test** (appendere a `test_edge_factory_corpus.py`):

```python
MOONDEV_TRIAGED = {
    "funding-extremum-reversal",
    "liquidation-cascade-reversal",
    "bb-squeeze-release",
    "cvd-divergence",
    "session-seasonality",
}


def test_moondev_five_triaged_factors_present() -> None:
    reg = load_registry(REGISTRY_DIR / "crypto-microstructure.yaml")
    names = {h.nome for h in reg.hypotheses}
    assert MOONDEV_TRIAGED <= names


def test_practitioner_entries_carry_conservative_haircut() -> None:
    reg = load_registry(REGISTRY_DIR / "crypto-microstructure.yaml")
    practitioners = [h for h in reg.hypotheses if h.origine == "practitioner"]
    assert practitioners, "at least one practitioner entry expected"
    for h in practitioners:
        assert h.decay_atteso_pct >= 40.0
        assert any("moondev-repos" in (e.ref or "") for e in h.evidenza)
```

(nota: fixare l'apostrofo/typo cinese prima del commit — la riga `assert practitioners, "至少 one…"` va scritta `"at least one practitioner entry expected"`.)

- [ ] **Step 3.2: run → FAIL**.
- [ ] **Step 3.3: estrazione** — leggere `trading-os/knowledge/moondev-repos/RISPOSTE_D1-D15.md`, `NOTES.md`, `INDEX.md`; codificare i 5 fattori (meccanismo + perche_esiste + dati $0 Binance Vision: fundingRate, liq snapshot, OHLCV 1m/1h; flag `origine: practitioner`, `decay_atteso_pct: 40-50`, evidenza miner con ref ai file). Esempio conforme (dal design spec §3.1):

```yaml
schema_version: 1
domain: crypto-microstructure
hypotheses:
  - id: EF-001
    nome: funding-extremum-reversal
    meccanismo: funding rate estremo indica posizioni long affollate e costose da tenere → spinta al reversal
    perche_esiste: il costo del carry spinge i marginal trader fuori dalla posizione affollata
    origine: practitioner
    fonti: ["trading-os/knowledge/moondev-repos/RISPOSTE_D1-D15.md"]
    effect_size_dichiarata: non_quantificata
    decay_atteso_pct: 40
    dati_richiesti: ["fundingRate 8h", "OHLCV 1h"]
    dati_posseduti: true
    asset_candidati: [BTCUSDT, ETHUSDT, SOLUSDT]
    timeframe: [1h, 4h]
    stato: da_amplificare
    evidenza:
      - data: "2026-08-22T00:00:00+00:00"
        tipo: miner
        testo: fattore triaged MoonDev D1, claim di rendimento NON verificato
        ref: trading-os/knowledge/moondev-repos/RISPOSTE_D1-D15.md
```

- [ ] **Step 3.4: validazione + PASS**; lint/type; **Step 3.5: commit** `feat(BL-702): MoonDev miner — 5 fattori practitioner → registry crypto-microstructure`.

---

### Task 4: BL-706 — IC screen pre-registrato (Spearman + block bootstrap)

**Files:**
- Create: `analytics/research/factory/ic_screen.py`
- Test: `tests/unit/test_edge_factory_ic_screen.py`

**Interfaces:**
- Consumes: `pd.Series` fattore e prezzi (stesso indice temporale).
- Produces: `screen_factor(factor, prices, horizon=5, window=63, block_len=5, n_boot=1000, seed=42, haircut_pct=30.0, icir_threshold=0.05, t_threshold=2.5) -> ICResult`; `ICResult` frozen dataclass con `n_windows, ic_mean, ic_std, icir, t_block, icir_haircut, passes, haircut_pct, icir_threshold, t_threshold`.

Criteri pre-registrati (design §6, dallo studio 2026-08-19 §5): ICIR > 0.05 su orizzonti non sovrapposti, t-block > 2.5, haircut 30% applicato all'ICIR prima del verdetto. Direzione: ipotesi unica long-factor → passa solo con ICIR positivo; IC negativo = fail (non si scava post-hoc il segno).

- [ ] **Step 4.1: failing test**:

```python
"""BL-706 — IC screen: golden behaviour su serie sintetiche a potatura nota."""
from __future__ import annotations

import numpy as np
import pandas as pd

from analytics.research.factory.ic_screen import screen_factor


def _market(n: int, seed: int) -> tuple[pd.Series, pd.Series]:
    """Prices from seeded returns; factor = signal on next-return + noise."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2020-01-01", periods=n, freq="h", name="ts")
    rets = rng.standard_normal(n) * 0.001
    prices = pd.Series(100.0 * np.cumprod(1.0 + rets), index=idx, name="price")
    next_ret = pd.Series(rets, index=idx, name="next_ret")
    return prices, next_ret


def _factor_with_ic(next_ret: pd.Series, strength: float, seed: int) -> pd.Series:
    rng = np.random.default_rng(seed)
    noise = rng.standard_normal(len(next_ret))
    return (strength * next_ret + noise).rename("factor")


def test_planted_signal_passes() -> None:
    prices, nxt = _market(2000, seed=3)
    res = screen_factor(_factor_with_ic(nxt, 0.35, seed=9), prices, horizon=1, window=100)
    assert res.n_windows >= 15
    assert res.ic_mean > 0.05
    assert res.passes is True


def test_pure_noise_fails() -> None:
    prices, nxt = _market(2000, seed=3)
    res = screen_factor(_factor_with_ic(nxt, 0.0, seed=9), prices, horizon=1, window=100)
    assert res.passes is False


def test_haircut_applied_to_icir() -> None:
    prices, nxt = _market(2000, seed=3)
    res = screen_factor(_factor_with_ic(nxt, 0.35, seed=9), prices, horizon=1, window=100)
    assert res.icir_haircut == pytest.approx(res.icir * 0.70)


def test_deterministic_given_seed() -> None:
    prices, nxt = _market(1500, seed=5)
    f = _factor_with_ic(nxt, 0.2, seed=4)
    a = screen_factor(f, prices, horizon=1, window=75)
    b = screen_factor(f, prices, horizon=1, window=75)
    assert a == b


def test_insufficient_data_fails_closed() -> None:
    prices, nxt = _market(200, seed=1)
    res = screen_factor(_factor_with_ic(nxt, 0.9, seed=2), prices, horizon=1, window=100)
    assert res.n_windows < 4
    assert res.passes is False
```

(aggiungere `import pytest` in testa nel file reale — serve per `pytest.approx`.)

- [ ] **Step 4.2: run → FAIL** (ModuleNotFoundError: ic_screen non esiste).
- [ ] **Step 4.3: implementazione** — `analytics/research/factory/ic_screen.py`:

```python
"""BL-706 — Pre-registered IC screen for factor hypotheses.

Spearman rank IC computed on non-overlapping windows of (factor, forward
return) pairs; significance via moving-block bootstrap over the window-IC
series.  Criteria pre-registered (design spec §6): ICIR > 0.05,
block-bootstrap t > 2.5, with a 30% post-publication haircut applied to
the measured ICIR before the verdict.  Direction is fixed (long-factor):
a negative-IC factor FAILS, it is never sign-flipped post-hoc.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats

_MIN_WINDOWS = 4


@dataclass(frozen=True)
class ICResult:
    n_windows: int
    ic_mean: float
    ic_std: float
    icir: float
    t_block: float
    icir_haircut: float
    passes: bool
    haircut_pct: float
    icir_threshold: float
    t_threshold: float


def _forward_returns(prices: pd.Series, horizon: int) -> pd.Series:
    return (prices.shift(-horizon) / prices - 1.0).rename("fwd_ret")


def _window_ics(factor: pd.Series, fwd: pd.Series, window: int) -> list[float]:
    df = pd.concat([factor.rename("factor"), fwd], axis=1).dropna()
    ics: list[float] = []
    for start in range(0, len(df) - window + 1, window):
        chunk = df.iloc[start : start + window]
        if chunk["factor"].nunique() < 3 or chunk["fwd_ret"].nunique() < 3:
            continue
        ic, _ = stats.spearmanr(chunk["factor"], chunk["fwd_ret"])
        ics.append(float(ic))
    return ics


def _block_bootstrap_t(ics: np.ndarray, block_len: int, n_boot: int, seed: int) -> float:
    """t-stat of mean IC under a moving-block bootstrap of the IC series."""
    rng = np.random.default_rng(seed)
    n = len(ics)
    if n < 2 or block_len > n:
        return float("nan")
    n_blocks = int(np.ceil(n / block_len))
    max_start = n - block_len
    starts = rng.integers(0, max_start + 1, size=(n_boot, n_blocks))
    means = np.array(
        [np.concatenate([ics[s : s + block_len] for s in row])[:n].mean() for row in starts]
    )
    denom = means.std(ddof=1)
    if not np.isfinite(denom) or denom == 0.0:
        return float("inf") if ics.mean() > 0 else (float("-inf") if ics.mean() < 0 else 0.0)
    return float(ics.mean() / denom)


def screen_factor(
    factor: pd.Series,
    prices: pd.Series,
    horizon: int = 5,
    window: int = 63,
    block_len: int = 5,
    n_boot: int = 1_000,
    seed: int = 42,
    haircut_pct: float = 30.0,
    icir_threshold: float = 0.05,
    t_threshold: float = 2.5,
) -> ICResult:
    fwd = _forward_returns(prices, horizon)
    ics = np.asarray(_window_ics(factor, fwd, window), dtype=float)
    if len(ics) < _MIN_WINDOWS:
        return ICResult(
            n_windows=int(len(ics)), ic_mean=float("nan"), ic_std=float("nan"),
            icir=float("nan"), t_block=float("nan"), icir_haircut=float("nan"),
            passes=False, haircut_pct=haircut_pct,
            icir_threshold=icir_threshold, t_threshold=t_threshold,
        )
    ic_mean = float(ics.mean())
    ic_std = float(ics.std(ddof=1))
    icir = ic_mean / ic_std if ic_std > 0 else float("nan")
    t_block = _block_bootstrap_t(ics, block_len, n_boot, seed)
    icir_haircut = icir * (1.0 - haircut_pct / 100.0) if np.isfinite(icir) else float("nan")
    passes = bool(
        np.isfinite(icir_haircut)
        and np.isfinite(t_block)
        and icir_haircut > icir_threshold
        and t_block > t_threshold
    )
    return ICResult(
        n_windows=int(len(ics)), ic_mean=ic_mean, ic_std=ic_std, icir=icir,
        t_block=t_block, icir_haircut=icir_haircut, passes=passes,
        haircut_pct=haircut_pct, icir_threshold=icir_threshold,
        t_threshold=t_threshold,
    )
```

- [ ] **Step 4.4: run → PASS** (se `test_planted_signal_passes` fallisse per rumore nel seed scelto, alzare `strength` o allungare la serie — ma prima verificare che non sia un bug: aggiustare i parametri del test è consentito solo mantenendo la semantica "segnale piantato forte passa / rumore fallisce").
- [ ] **Step 4.5: golden vector** — aggiungere `test_golden_vectors`: eseguire `screen_factor` sulle serie seeded e hardcodare i valori prodotti (characterization: dopo il primo run verde, incollare icir/t_block attesi come costanti e assert equality) — la riproducibilità esatta è l'AC "golden vector".
- [ ] **Step 4.6: lint + mypy strict; commit** `feat(BL-706): IC screen pre-registrato — Spearman + block bootstrap + haircut 30%`.

---

### Task 5: BL-721 — Fixture programmi verificati (da §11 / docs/firm_sources)

**Files:**
- Modify: `policy/prop_firm/profile.py` (enum + campo)
- Modify: `policy/prop_firm/fixtures.py` (nuovi profili)
- Modify: `policy/prop_firm/__init__.py` (export)
- Test: `tests/policy/test_prop_firm_golden.py` (estendere)

**Interfaces:**
- Consumes: `FirmProgramProfile`, `DrawdownMode`, `SessionRule`, `SupportMode`, `NewsBlackout` (profile.py esistente); snapshot `docs/firm_sources/{ftmo,the5ers,alpha-capital,e8,fundednext}/` + `SNAPSHOTS.tsv` (sha256).
- Produces: `DailyLossAction(StrEnum)` {TERMINATE, PAUSE} + campo `daily_loss_action: DailyLossAction = TERMINATE` su `FirmProgramProfile`; `DrawdownMode.TRAILING_CLOSED` (floor sale solo sui profitti chiusi — E8). L'enforcement nel governor è **BL-722, NON questo task**: qui si codifica solo la superficie dei profili.
- Nuovi profili (solo numeri presenti negli snapshot verificati; dove mancano → declared gap nel commento, nessun numero inventato):
  - `FTMO_1_STEP` — target 10%, daily 3%, overall 10% TRAILING_EOD su midnight-max (only increases, never decreases; reset al withdrawal), basis equity (balance+open P/L±swap−commissioni), reset 00:00 CE(S)T → `Europe/Prague`. Best Day ≤ 50% dei positive-days profit: NON è breach → **non modellato** (gap dichiarato, stessa convenzione Topstep BL-095).
  - `FTMO_2_STEP_P1` / `FTMO_2_STEP_P2` — target 10%/5%, daily 5%, overall 10% STATIC, min 4 trading days/fase, no time limit.
  - `THE5ERS_BOOTCAMP_STEP` (× step: target 6%, overall 5%) + `THE5ERS_BOOTCAMP_FUNDED` (overall 4%, scaling target 5%) — estrarre i dettagli da `docs/firm_sources/the5ers/*.txt`.
  - `THE5ERS_HIGH_STAKES_P1/P2` — target 10%/5%, daily 5% **TERMINATE**, overall 10%.
  - `THE5ERS_PRO_GROWTH` — daily 3% TERMINATE (numeri residui dallo snapshot).
  - `THE5ERS_HYPER_GROWTH` — daily 3% **PAUSE** (`daily_loss_action=PAUSE`).
  - `ALPHA_CAPITAL_*` — da T&C: news ±5 min (`NewsBlackout(5,5)`), anti-HFT (durata media > 2 min, ≥50% profitto da trade > 2 min — solo flag/documentati, enforcement BL-722), Max Risk Rule open-DD per asset 3%/2%. Economia dei programmi (target/DD) solo se presente nello snapshot T&C, altrimenti gap → seconda passata BL-720.
  - `E8_ONE` — `dd_mode=DrawdownMode.TRAILING_CLOSED`; target/DD default solo se nello snapshot `e8/*.txt` (customizzabili al checkout → gap dichiarato se il default non è snapshot-pato); challenge: nessuna consistency, nessun profit cap.
  - FundedNext CFD/Rapid: numeri programma NON verificati (gap §11) → **nessuna fixture nuova**; si tiene la `FUNDEDNEXT_FLEX` futures esistente. Da completare dopo la seconda passata BL-720.

- [ ] **Step 5.1: estrarre i numeri** — leggere i `.txt` estratti in `docs/firm_sources/*/` per i programmi sopra; per ogni numero citato annotare file+sha256 (da `SNAPSHOTS.tsv`). Regola: un campo entra nella fixture solo se presente nello snapshot; altrimenti gap commentato.
- [ ] **Step 5.2: failing test** — estendere `tests/policy/test_prop_firm_golden.py` con una classe per profilo (pattern delle esistenti: `test_profile_basics` sui numeri + `test_daily_breach_at_<cash>` al limite + `test_pass_on_target` + controllo `daily_loss_action`/`dd_mode` distintivi). Esempio FTMO 1-Step:

```python
class TestFTMO_1_STEP:  # noqa: N801
    def test_profile_basics(self):
        assert FTMO_1_STEP.firm == "FTMO"
        assert FTMO_1_STEP.account_size == 100_000
        assert FTMO_1_STEP.profit_target_pct == 0.10
        assert FTMO_1_STEP.max_daily_loss_pct == 0.03
        assert FTMO_1_STEP.max_overall_loss_pct == 0.10
        assert FTMO_1_STEP.dd_mode is DrawdownMode.TRAILING_EOD
        assert FTMO_1_STEP.daily_loss_reset_timezone == "Europe/Prague"
        assert FTMO_1_STEP.rule_version == "2026-08-22"

    def test_daily_breach_at_three_thousand(self):
        gov = _make_gov(FTMO_1_STEP)
        gov.update(balance=100_000.0, equity=97_000.0)
        breaches = {b.type for b in gov.evaluate()}
        assert BreachType.DAILY_LOSS in breaches

    def test_pass_on_target(self):
        gov = _make_gov(FTMO_1_STEP, balance=100_000.0)
        gov.record_trade(10_100.0)
        gov.rollover()
        assert gov.challenge_outcome() is ChallengeStatus.PASSED
```

(adattare i valori limite al semantics del governor: verificare `_daily_reference`/`overall_floor` prima di fissare i numeri del test — la boundary deve essere quella del profilo, non quella dell'implementazione).

- [ ] **Step 5.3: run → FAIL** (import error sui nuovi nomi).
- [ ] **Step 5.4: implementazione** — enum + campo in `profile.py` (default `TERMINATE` = back-compat: i profili esistenti non cambiano comportamento); fixture in `fixtures.py` con `source_url` + `source_checked_at="2026-08-22"` + commento con path snapshot e sha256; export in `__init__.py`.
- [ ] **Step 5.5: run → PASS**; `ruff` + `mypy --strict` sui 3 file; suite policy completa verde.
- [ ] **Step 5.6: commit** `feat(BL-721): fixture programmi verificati FTMO/The5ers/Alpha/E8 da snapshot ufficiali (+DailyLossAction, TRAILING_CLOSED)`.

---

### Task 6 (se resta budget): BL-707 — Haircut Sharpe (BL-KB-99)

**Files:** Create `analytics/research/factory/haircut_sharpe.py`, test `tests/unit/test_edge_factory_haircut.py`. Formula Bailey-López de Prado 2018 (*The Right Way to Select Investments*): HSR = SR·√((1 − γ₃·SR + (γ₄−1)/4·SR²)/2) con γ₃ skewness e γ₄ kurtosis del campione. TDD: simmetria (skew 0, kurt 3 → HSR ≈ SR·√((1+(3−1)/4·SR²)/2) leggermente < SR per kurt>3), monotonia in kurtosis, determinismo. AC: integrato nei report di qualificazione = usato da `ic_screen`/report BL-708 (per ora: funzione + test; il wiring ai report avviene con BL-708).

---

### Task 7: Chiusura — BACKLOG/STATUS + verification-before-completion

- [ ] **Step 7.1:** suite completa `uv run pytest tests/ -q` verde; conteggio aggiornato.
- [ ] **Step 7.2:** BACKLOG.md — spuntare `[x]`/`[~]` i BL eseguiti con annotazione data; STATUS — baseline §2 (nuovo conteggio) + nota sezione factory/prop-firm.
- [ ] **Step 7.3:** commit docs `docs(status): sessione 2026-08-22 — BL-711/701/702/706/721 eseguiti`.
- [ ] **Step 7.4:** verificare con `superpowers:verification-before-completion`: ogni claim del report finale ha un comando runnato come evidenza.

## Fuori perimetro questa sessione (perché)

| BL | Perché fuori |
|---|---|
| BL-704 amplificazione | batteria 5 search MCP per ipotesi — sessione semi-manuale dedicata, dopo che il registry è popolato (da questa sessione) |
| BL-705 adapter | richiede output BL-704 |
| BL-703 transcript miner | P2; 835 file, dedup infra; dopo BL-701/702 collaudati |
| BL-710 alphalens | Tier-1 ma "secondo parere" su BL-706: dopo che l'IC screen esiste ed è usato |
| BL-714 edgartools / BL-716 cryptofeed / BL-712/713/715/717 | acquisizioni indipendenti P1/P2: prossima sessione acquisizioni (stesso pattern Task 1) |
| BL-722 governor | dipende dalle fixture BL-721 di questa sessione; enforcement news-blackout/pause/min-duration + test per ogni DrawdownMode/basis |
| BL-723 spike MT5/Wine | ambiente Wine + demo: sessione dedicata |
| BL-615 residuo | migrazione meccanica 5 runner legacy → wrapper; priorità sotto la catena factory |
| BL-718 distillazione | distruttiva (cancella repo MoonDev): piano dedicato con verifica "nessun parametro perso" |
| BL-720 seconda passata | browser automation (FTMO FAQ JS-rendered, pagine prodotto FN/E8): sessione dedicata |
| BL-724/725 | P2, dopo BL-722 |

## Decisioni che restano all'utente (non prese qui)

- **Lane B**: variante unica pre-registrata vs pivot crypto factors — chiusura a verbale richiesta dallo STATUS §7 (la factory la sostituisce di fatto, ma va formalizzato).
- Nessuna nuova decisione strategica è stata presa in questa sessione.
