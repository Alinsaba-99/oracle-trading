# Sprint Renaissance-Parity — Piano di implementazione (BL-739..743)

> **Per agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Stato revisione**: validato da 2 subagent review (architetto + critico, 2026-09-04) — fix applicati: ID registry EF-004 per-dominio; ES escluso dalle gambe 1h (14k barre < min_bars, vedi Task 2); docstring prereg aggiunte a Task 3/4; Task 4 dichiara il precedente NEGATIVO Sprint 2d e richiede CPCV; Task 5 corregge la citazione leva (scelta locale, non ADR-023) e la dipendenza Channel B.

**Goal:** Qualificare 3 nuove famiglie ortogonali non-tecniche (overnight drift, FX carry policy-rate, condizionamento cross-pillar) nel gauntlet esistente della Edge Factory, e consolidare il portafoglio + la documentazione canonica con le direttive Renaissance-parity.

**Architecture:** Nessun modulo nuovo: riusa il pattern consolidato "runner script congelato + gauntlet ADR-017 + registry YAML" degli sprint 1/2 (BL-708, BL-718). Le soglie di gate sono le stesse costanti frozen di Sprint 1/2 (`HAIRCUT_SHARPE_GATE=0`, `DSR_MIN=0.5`, `KILL_MIN_PASSING_SLOTS=2`). I dati sono tutti nel lake esistente (`data/lake/curated/{SYMBOL}_1h.parquet`, `data/ohlcv/ES_1d.parquet`) + FRED (PIT via `analytics/macro/fred.py`).

**Tech Stack:** Python 3.12, pandas/numpy, `analytics/research/factory/*` (registry, ic_screen, haircut_sharpe), `analytics/qualification/dsr.py`, `analytics/metrics/canonical.py` (ADR-021), pytest, uv.

**Spec:** `docs/reports/renaissance-parity-2026-09-04/SYNTHESIS.md` (§4-5: metodo + fasi) e `docs/plans/2026-08-21-edge-research-factory-design.md` (§6: qualificazione pre-registrata). Il piano argomenta dalla spec.

## Global Constraints

- **$0/mese dati** (ADR-020): solo lake esistente + FRED/ALFRED + CFTC/CBOE free. Nessuna nuova fonte a pagamento, mai.
- **Nessun tuning in-sprint**: ogni parametro è frozen dalla letteratura citata nel registry PRIMA del run (prereg). Modificarlo = nuovo prereg.
- **Soglie gate identiche a Sprint 1/2**: `ICIR_HAIRCUT 0.05 / IC_BLOCK_T 2.5 / IC_HAIRCUT_PCT 30.0 / HAIRCUT_SHARPE_GATE 0.0 / DSR_MIN 0.5 / KILL_MIN_PASSING_SLOTS 2`. Nessuna soglia nuova.
- **Walk-forward split unico**: train ≤ `2022-12-31`, test > `2022-12-31` (identico a tutti gli sprint factory).
- **Costi inclusi per-gamba**: FX/metals 1.5 bps/turnover unit; equity-index 1h 10 bps (stessi ordini di grandezza di Sprint 2c/BL-738).
- **Metriche ADR-021 only**: Sharpe/MaxDD/Calmar SOLO via `analytics/metrics/canonical.py`. Mai ricalcoli locali.
- **Nessun risultato silenzioso**: ogni REJECTED produce comunque report committato in `docs/reports/edge-factory/`.
- **Guardrail finanziari (anti-drift, invariati)**: 5%/mese NON è atteso come tendenza centrale sotto paletti funded; envelope documentato canale funded 0.5-1.5%/mese; canale personal vol-target 30% con MaxDD ~30% dichiarato; nessuna eval si paga senza sim canonica pass (ADR-018/023).
- **Registry append-only**: le ipotesi si aggiungono in `scripts/build_edge_factory_registry.py` (deterministico) e si rigenerano gli YAML; gli stati cambiano solo via `HypothesisRegistry.update_status(persist=True)` con motivo + ref.
- Suite: `pytest` verdi sul path toccato, `ruff`, `mypy --strict`. Commit `feat(BL-NNN): ...`.

---

### Task 1: Registry — 3 nuove ipotesi (EF-004 overnight, EF-004 carry, EF-004 conditioning)

**Files:**
- Modify: `scripts/build_edge_factory_registry.py` (aggiunta a `DOMAINS`)
- Regen: `docs/knowledge-base/edge-factory/registry/{10-seasonal,02-macro,13-meta-synthesis}.yaml`
- Test: `tests/unit/test_edge_factory_registry.py` (conteggi/istogrammi aggiornati)

**Interfaces:**
- Consumes: `_kb(nome, meccanismo, perche, fonti, dati, assets, timeframe, decay, effect, dati_posseduti, hid)` da `build_edge_factory_registry.py:40`; `HypothesisRegistry` da `analytics/research/factory/registry.py`.
- Produces: `EF-004 overnight-drift-dealer-inventory` (stato `da_amplificare` → il Task 2 lo testerà), `EF-004 fx-carry-policy-rate-differential`, `EF-004 cross-pillar-conditioning-overlay`. **Attenzione ID**: gli ID EF sono per-dominio e OGNI dominio ha oggi solo `EF-001..003` (verificato: `02-macro.yaml` e `13-meta-synthesis.yaml` hanno 3 voci ciascuno) → `next_id()` restituirà `EF-004` in TUTTI i domini. Non hardcodare altri numeri: il builder assegna/valida via `_unique_ids`.

- [ ] **Step 1: Verificare gli ID liberi per dominio**

Run: `grep -c "id: EF-" docs/knowledge-base/edge-factory/registry/10-seasonal.yaml docs/knowledge-base/edge-factory/registry/02-macro.yaml docs/knowledge-base/edge-factory/registry/13-meta-synthesis.yaml`
Expected: conteggi attuali; i nuovi ID = successivi a quelli esistenti nel dominio (il builder validà l'unicità via `_unique_ids`).

- [ ] **Step 2: Aggiungere le 3 ipotesi al builder**

In `DOMAINS`, in coda alla lista di `"10-seasonal"`:

```python
_kb(
    nome="overnight-drift-dealer-inventory",
    meccanismo=(
        "decomposizione overnight/intraday: il premium azionario USA si realizza "
        "quasi interamente nella sessione overnight (close→open); su strumenti 24h "
        "l'analogo è hold 20:00→13:30 UTC + finestra concentrata 07:00-08:00 UTC "
        "(02:00-03:00 ET)"
    ),
    perche=(
        "i dealer scaricano l'inventario accumulato nel cash session quando la "
        "liquidità e' minima (Grossman-Miller; Boyarchenko-Larsen-Whelan 2023); "
        "i retail pagano sistematicamente l'open (Berkman et al 2012)"
    ),
    fonti=[
        f"{KB}/10-seasonal/README.md",
        "docs/reports/renaissance-parity-2026-09-04/B-replicable-families.md#4-overnight-vs-intraday-decomposition",
    ],
    dati=["1h OHLCV XAUUSD/XAGUSD/FX majors/ES (lake curated, 2003->)"],
    assets=["XAUUSD", "XAGUSD", "EURUSD", "GBPUSD", "USDJPY", "ES"],
    timeframe=["1h"],
    decay=20.0,
    effect=(
        "100% US equity premium overnight (Lou-Polk-Skouras 2019 JFE); "
        "02:00-03:00 ET concentra il rendimento ES (BLW 2023). NON ancora "
        "replicato su oro/FX: open question dossier B n.7"
    ),
    dati_posseduti=True,
),
```

In coda a `"02-macro"`:

```python
_kb(
    nome="fx-carry-policy-rate-differential",
    meccanismo=(
        "carry G10 basket: segno(dir(policy_A) - dir(policy_USD)) per coppia, "
        "posizione vol-scaled, ribilanciamento mensile, dollar-neutral "
        "(policy rates da FRED PIT con lag 2 mesi anti-lookahead)"
    ),
    perche=(
        "HML FX carry Sharpe ~0.5 (Lustig-Roussanov-Verdelhan 2011 RFS); "
        "compensazione per crash risk (Menkhoff et al 2012 JF) -> "
        "tail-aware reporting obbligatorio (SNB 2015, COVID 2020-03)"
    ),
    fonti=[
        f"{KB}/02-macro/README.md",
        "docs/reports/renaissance-parity-2026-09-04/B-replicable-families.md#7-carry-families-fx-commodity-basis-crypto-funding",
    ],
    dati=["FRED policy rates PIT (FEDFUNDS, ECBDFR, IRSTCI01xx)", "1h FX spot lake curated"],
    assets=["EURUSD", "GBPUSD", "USDJPY", "USDCHF", "USDCAD", "AUDUSD", "NZDUSD"],
    timeframe=["1M rebalance su griglia 1h"],
    decay=30.0,
    effect="HML carry Sharpe ~0.5 in-sample RFS; crisi drawdown documentati",
    dati_posseduti=True,
),
```

In coda a `"13-meta-synthesis"`:

```python
_kb(
    nome="cross-pillar-conditioning-overlay",
    meccanismo=(
        "condizionamento NON direzionale delle gambe qualificate con segnali di "
        "altri pilastri KB: VIX z-score (05-sentiment) e funding-z (11-onchain) "
        "veto/scalano le posizioni trend quando il pilastro segnala rischio "
        "(stessa forma di Sprint 2d: pos *= 1 - clip(|z|,0,2)/2)"
    ),
    perche=(
        "meta-labeling/conditioning separa side da size (Lopez de Prado 2018 "
        "ch.3); l'edge vive nelle interazioni fra pilastri, non nei numeri "
        "singoli (direttiva Renaissance-parity 2026-09-04)"
    ),
    fonti=[
        f"{KB}/13-meta-synthesis/README.md",
        "docs/reports/edge-factory/sprint-2d.md",
    ],
    dati=["VIX daily (sorgente gia' usata da lane_d_vrp)", "funding 1h Binance Vision (backfilled BL-718)"],
    assets=["ES", "BTCUSDT", "ETHUSDT"],
    timeframe=["1d (ES)", "1h (crypto)"],
    decay=30.0,
    effect="+1-2%/yr Sharpe improvement da meta-labeling (LdP 2018, PBO risk >50% senza CPCV)",
    dati_posseduti=True,
),
```

- [ ] **Step 3: Rigenerare gli YAML e verificare il diff**

Run: `uv run python scripts/build_edge_factory_registry.py && git diff --stat docs/knowledge-base/edge-factory/registry/`
Expected: solo i 3 YAML toccati, +1 ipotesi ciascuno, stati esistenti invariati (il builder è deterministico: nessun altro diff).

- [ ] **Step 4: Aggiornare i test dei conteggi**

Localizzare in `tests/unit/test_edge_factory_registry.py` (e/o `test_edge_factory_registry_bl700.py`) le asserzioni su conteggio ipotesi / istogramma stati per i 3 domini toccati; incrementare di 1 i valori attesi (`da_amplificare` +1).

Run: `uv run pytest tests/unit/test_edge_factory_registry.py tests/unit/test_edge_factory_registry_bl700.py -q`
Expected: tutti PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/build_edge_factory_registry.py docs/knowledge-base/edge-factory/registry/ tests/unit/
git commit -m "feat(BL-739a): registry +3 ipotesi (overnight drift, fx carry, cross-pillar conditioning)"
```

---

### Task 2: BL-739 — Runner overnight drift (decomposizione + gambe frozen)

> **Nota dati (review architetto)**: `data/lake/curated/ES_1h.parquet` ha solo ~14.244 barre (2024-03 → 2026-09) — SOTTO qualunque min_bars ragionevole e senza warm-up. ES 1h è quindi **ESCLUSO** dalle gambe 1h di questo sprint; ES resta coperto dal Task 4 su `ES_1d` (6.5k barre, 2015→). La famiglia overnight drift si qualifica su strumenti 24h del lake Dukascopy (XAUUSD/XAGUSD/FX majors, 140k+ barre dal 2003).

**Files:**
- Create: `scripts/run_overnight_drift_sprint.py`
- Create: `tests/unit/test_overnight_drift_sprint.py`
- Output (runtime): `docs/reports/edge-factory/overnight-drift-sprint.{md,json}`

**Interfaces:**
- Consumes: `sharpe_ratio`, `max_drawdown_from_returns` da `analytics/metrics/canonical.py`; `deflated_sharpe_ratio`, `probabilistic_sharpe_ratio` da `analytics/qualification/dsr.py`; `haircut_sharpe_ratio` da `analytics/research/factory/haircut_sharpe.py`; `HypothesisRegistry.update_status` per la transizione di stato.
- Produces: funzioni `_session_mask(index, hour_lo, hour_hi)`, `overnight_leg(close, hour_lo=20, hour_hi=13)`, `window_leg(close, hour=7)`, `load_1h(lake_root, symbol, min_bars=50_000)`, `_result_from_returns(...)` (stessa forma di BL-738); report JSON con verdetto GO/NO_GO per famiglia.

- [ ] **Step 1: Scrivere i test falling (matematica pura, dati sintetici)**

```python
"""Test BL-739 — overnight drift sprint (matematica, no lake)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from scripts.run_overnight_drift_sprint import (
    _apply_costs,
    load_1h,
    overnight_leg,
    window_leg,
)


def _fake_hours(n: int = 48, start: str = "2024-01-01") -> pd.DatetimeIndex:
    return pd.date_range(start, periods=n, freq="h", tz="UTC")


def test_overnight_leg_is_long_only_in_overnight_hours():
    idx = _fake_hours()
    close = pd.Series(100.0, index=idx)
    pos = overnight_leg(close)  # long 20:00->13:30, flat nel cash session
    long_hours = set(range(20, 24)) | set(range(0, 13))
    # posizioni > 0 SOLO in ore overnight
    assert pos[pos > 0].index.hour.isin(long_hours).all()
    cash_hours = set(range(13, 20))
    cash_pos = pos[pos.index.hour.isin(cash_hours)].dropna()
    assert (cash_pos == 0).all()


def test_window_leg_only_hour_seven():
    idx = _fake_hours()
    close = pd.Series(100.0, index=idx)
    pos = window_leg(close, hour=7)
    assert (pos[pos.index.hour == 7] > 0).all()
    assert (pos[pos.index.hour != 7] == 0).all()


def test_apply_costs_charges_turnover():
    idx = _fake_hours(72)
    rets = pd.Series(0.001, index=idx)  # +10bps/h flat
    costs = _apply_costs(rets, cost_bps=1.5)
    # una posizione sempre attiva senza rebalance -> costo 1x per unit turnover
    assert costs < rets.sum()
    assert costs > 0


def test_load_1h_missing_returns_none(tmp_path):
    assert load_1h(tmp_path, "NOTACOIN") is None
```

- [ ] **Step 2: Run test → FAIL (modulo non esiste)**

Run: `uv run pytest tests/unit/test_overnight_drift_sprint.py -q`
Expected: FAIL `ModuleNotFoundError: scripts.run_overnight_drift_sprint`.

- [ ] **Step 3: Implementare il runner (pattern BL-738)**

Struttura del file (frozen, no tuning — docstring cita prereg):

```python
#!/usr/bin/env python3
"""BL-739 — Overnight drift sprint (EF-004 overnight-drift-dealer-inventory).

Prereg: ipotesi EF-004 nel registry 10-seasonal; gambe FROZEN dalla
letteratura (Lou-Polk-Skouras 2019; Boyarchenko-Larsen-Whelan 2023):
1. overnight_hold_close_to_open — long 20:00->13:30 UTC ogni giorno,
   flat nel cash session (analogo close->open LPS).
2. window_0203_hold — long solo 07:00-08:00 UTC (02:00-03:00 ET, BLW).
Più event study: rendimento medio per ora UTC (evidenza, non traded).
Limitazione dichiarata: finestre UTC fisse, drift DST +-1h.
Walk-forward test > 2022-12-31; costi 1.5 bps/turnover (FX/metals),
10 bps (ES). Gates identici Sprint 1/2. Output: overnight-drift-sprint.{md,json}.
"""
```

Costanti: `TEST_SPLIT = pd.Timestamp("2022-12-31", tz="UTC")`, `COST_BPS = {"XAUUSD": 1.5, "XAGUSD": 1.5}` default 1.5, `TARGET_VOL = 0.10`, `VOL_WINDOW_HOURS = 720`, `MIN_BARS = 50_000`, `ASSETS = ("XAUUSD", "XAGUSD", "EURUSD", "GBPUSD", "USDJPY")` (ES escluso, vedi nota dati; event study orario ES può usare `ES_1h` solo descrittivamente, flagged `insufficient_data` nel report). Le gambe: posizione ±1 su bar-orari selezionati, scalata da `_vol_scalar` (rolling std 720h, cap 2x) come BL-738; rendimenti = pos.shift(1) * log_ret; `_apply_costs` su `|Δpos|`. Verdetto famiglia: ≥2 asset-pass (haircut Sharpe > 0 E DSR > 0.5 sul test window) → GO.

- [ ] **Step 4: Run test → PASS**

Run: `uv run pytest tests/unit/test_overnight_drift_sprint.py -q`
Expected: PASS.

- [ ] **Step 5: Eseguire il runner (walk-forward reale)**

Run: `uv run --frozen python scripts/run_overnight_drift_sprint.py`
Expected: report `docs/reports/edge-factory/overnight-drift-sprint.md` con tabella per asset×gamba (SR, haircut SR, DSR, MaxDD, trades) + event study orario + verdetto GO/NO_GO + sezione "limitazioni oneste" (DST, CFD swap/roll overnight non modellato su XAU/FX — dichiarato).

- [ ] **Step 6: Transizione registry (persist) + commit**

```python
# snippet eseguito da scripts/set_registry_state.py (Task 6, Step 1) oppure inline nel runner --update-registry
reg = HypothesisRegistry()
reg.update_status("EF-004@10-seasonal", "APPROVED" if go else "REJECTED",
                  motivo="BL-739 walk-forward > 2022-12-31",
                  ref="docs/reports/edge-factory/overnight-drift-sprint.md", persist=True)
```

```bash
git add scripts/run_overnight_drift_sprint.py tests/unit/test_overnight_drift_sprint.py docs/reports/edge-factory/overnight-drift-sprint.* docs/knowledge-base/edge-factory/registry/10-seasonal.yaml
git commit -m "feat(BL-739): overnight drift sprint — EF-004 {GO/NO_GO} (walk-forward, costi inclusi)"
```

---

### Task 3: BL-740 — Runner FX carry policy-rate (PIT FRED + spot lake)

**Files:**
- Create: `scripts/run_fx_carry_policy_rate.py`
- Create: `tests/unit/test_fx_carry_policy_rate.py`
- Output: `docs/reports/edge-factory/fx-carry-policy-rate.{md,json}`

Docstring prereg obbligatoria (review critico):

```python
#!/usr/bin/env python3
"""BL-740 — FX carry policy-rate basket (EF-004@02-macro fx-carry-policy-rate-differential).

Prereg: ipotesi EF-004 nel registry 02-macro; basket FROZEN dalla letteratura
(Lustig-Roussanov-Verdelhan 2011 RFS; Menkhoff-Sarno-Schmeling-Schrimpf 2012 JF):
- 7 coppie G10, segnale mensile ±1 = segno(tasso_A − tasso_B) con CARRY_LAG_MONTHS=2
  anti-lookahead (il valore FRED PIT pubblicato con certezza 2 mesi dopo);
- dollar-neutral, vol-target 10%, costi 1.5 bps/turnover, walk-forward test > 2022-12-31;
- TAIL-CHECK PRE-REGISTRATO: finestre 2020-03 e 2022-USD-rally riportate come
  righe dedicate SEMPRE (anche se il basket passa);
- limitazione dichiarata: carry da policy rates ≠ carry da 3M forwards (proxy
  conservativa, niente swap rates forward).
Gates identici Sprint 1/2. Output: fx-carry-policy-rate.{md,json}.
"""
```

**Interfaces:**
- Consumes: `fetch_series` da `analytics/macro/fred.py:120` (con `vintage=` PIT); loader 1h da Task 2 (`load_1h`); metriche canoniche + DSR/haircut (identici Task 2).
- Produces: `RATE_SERIES` mapping frozen valuta→serie FRED; `carry_signal(rates: pd.DataFrame) -> pd.Series` (segnale mensile ±1 per coppia); report con tail-check separato (mar-2020, 2022).

- [ ] **Step 1: Mapping frozen + test falling**

```python
RATE_SERIES: dict[str, str] = {
    "USD": "FEDFUNDS",
    "EUR": "ECBDFR",
    "JPY": "IRSTCI01JPM156N",
    "GBP": "IRSTCI01GBM156N",
    "CHF": "IRSTCI01CHM156N",
    "CAD": "IRSTCI01CAM156N",
    "AUD": "IRSTCI01AUM156N",
    "NZD": "IRSTCI01NZM156N",
}
PAIR_CCY = {"EURUSD": ("EUR", "USD"), "GBPUSD": ("GBP", "USD"),
            "USDJPY": ("USD", "JPY"), "USDCHF": ("USD", "CHF"),
            "USDCAD": ("USD", "CAD"), "AUDUSD": ("AUD", "USD"),
            "NZDUSD": ("NZD", "USD")}
CARRY_LAG_MONTHS = 2  # anti-lookahead: valore pubblicato con certezza
```

Test (sintetico): `carry_signal` dà +1 su EURUSD quando rate_EUR > rate_USD con lag; −1 sull'inverso; la griglia 1h riceve il segnale del mese precedente shiftato; una serie mancante → coppia esclusa e LISTATA nel report (nessun silent skip).

- [ ] **Step 2-4: Implementare, verificare FAIL→PASS, ruff/mypy**

Run: `uv run pytest tests/unit/test_fx_carry_policy_rate.py -q` → PASS.

- [ ] **Step 5: Eseguire + report**

Run: `uv run --frozen python scripts/run_fx_carry_policy_rate.py`
Expected: report con basket dollar-neutral vol-scaled 10%, costi 1.5 bps/turnover, split > 2022-12-31; **finestre tail separate** (2020-03, 2022-USD-rally) riportate come righe dedicate; verdetto GO/NO_GO (stessi gates). Se una serie FRED non risponde: la valuta è esclusa e documentata nella sezione "dati" del report. **Includere una stima del costo swap/roll CFD overnight applicabile al canale live (range 0.5-2% annuo su XAU CFD dai broker retail tipici, dossier C) come riga informativa del report — il runner backtest usa spot 1h quindi non lo addebita, ma il report lo dichiara.**

- [ ] **Step 6: Registry + commit**

```bash
git commit -m "feat(BL-740): fx carry policy-rate basket — EF-004@02-macro {GO/NO_GO} (PIT FRED, tail-check separato)"
```

---

### Task 4: BL-741 — Runner condizionamento cross-pillar (VIX × funding-z × gambe qualificate)

> **Precedente NEGATIVO da dichiarare (review critico)**: Sprint 2d (2026-09-03) ha testato lo STESSO meccanismo di veto (`1 − clip(|z|,0,2)/2`) con funding-z e il risultato è stato NEGATIVO (ETHUSDT SR +0.51→+0.46, P(m≥5%) 28.9%→15.8%; BTCUSDT −0.02→−0.52). Il presente Task 4 è un test INDIPENDENTE su pilastro diverso (VIX-z vs funding-z), NON una replica né un retry della stessa pista. **Se anche VIX-z risulta NEGATIVO, la pista conditioning-lite si chiude definitivamente senza retry su altri pilastri** (verdetto nel registry: `morta_per_evidenza`). CPCV (purgedcv, già installato) sul confronto baseline-vs-conditioned è parte del verdetto: `HELPFUL` richiede che entrambi (baseline e conditioned) sopravvivano a CPCV, e l'PBO stimato va riportato.

**Files:**
- Create: `scripts/run_pillar_conditioning_sprint.py`
- Create: `tests/unit/test_pillar_conditioning_sprint.py`
- Output: `docs/reports/edge-factory/pillar-conditioning-sprint.{md,json}`

Docstring prereg obbligatoria:

```python
#!/usr/bin/env python3
"""BL-741 — Cross-pillar conditioning (EF-004@13-meta-synthesis).

Prereg: ipotesi EF-004 nel registry 13-meta-synthesis. Gambe baseline FROZEN
dai report BL-736 (ES_1d ema(20/50) vol-target 10%, ES_1d donchian(20),
ETHUSDT_1h ema(20/50) vol-target 20%). Pilastri di condizionamento: VIX
z-score (rolling 252d, sorgente lane_d_vrp_backtest) e funding-z (BL-718).
Forma: pos *= 1 - clip(|z|,0,2)/2 quando il pilastro è CONTRO la posizione
(identica a Sprint 2d, full_z=2 frozen; NESSUNA ricerca di soglia).

PRECEDENTE: Sprint 2d funding-z = NEGATIVO (sprint-2d.md). Questo è un test
indipendente su pilastro diverso; se NEGATIVO → pista conditioning-lite chiusa.

CPCV (purgedcv) su baseline vs conditioned: HELPFUL richiede ΔSR ≥ +0.10,
turnover ≤ 2× baseline, E sopravvivenza di entrambi a CPCV. PBO riportato
(meta-labeling-lite, PBO risk >50% senza CPCV — Lopez de Prado 2018 ch.3).
Walk-forward > 2022-12-31, costi per gamba come BL-736. Output:
pillar-conditioning-sprint.{md,json}.
"""
```

**Interfaces:**
- Consumes: `load_funding_onto_prices` da `scripts/run_factory_sprint2_qualification.py:82`; helper Sprint 2c/2d (`_apply_costs`, `_result_from_returns`, `_vol_scalar`); `ES_1d` da `data/ohlcv/ES_1d.parquet`.
- Produces: `veto_scale(z: pd.Series, full_z: float = 2.0) -> pd.Series` (forma `1 − clip(|z|,0,2)/2`, identica Sprint 2d); report baseline vs conditioned per (gamba × pilastro).

- [ ] **Step 1: Localizzare la sorgente VIX esistente**

Run: `grep -n "VIX\|vix" analytics/strategy/lane_d_vrp_backtest.py | head -20` e individuare il path dati (usato nel backtest reale 2010-2025). Documentarlo nella docstring del runner.

- [ ] **Step 2: Test falling della veto_scale + fusione PIT**

Test: `veto_scale(z=2.0)=0`, `veto_scale(z=0)=1`, `veto_scale(z=-1)=0.5`; il VIX z-score al giorno T condiziona solo barre > T (shift(1) PIT, stesso pattern `load_funding_onto_prices`).

- [ ] **Step 3: Implementare — 3 gambe baseline × 2 pilastri + combinato**

Gambe baseline (frozen, stesse dei report BL-736): `ES_1d ema(20/50)` vol-target 10%; `ES_1d donchian(20)`; `ETHUSDT_1h ema(20/50)` vol-target 20% (costi 10 bps). Pilastri: `vix_z` (rolling 252d sul VIX daily), `funding_z` (esistente). Condizionata: `pos *= veto_scale(z)` solo quando il segnale pilastro è CONTRO la posizione (stessa regola "crowding against" di Sprint 2d). Verdetto per pilastro: `HELPFUL` se ΔSR ≥ +0.10 senza turnover > 2× baseline; altrimenti `NEUTRAL`/`HARMFUL`. Nessuna ricerca di soglia: `full_z=2` frozen.

- [ ] **Step 4-6: PASS test, run, registry, commit** (`EF-004@13-meta-synthesis`).

---

### Task 5: BL-742 — Portfolio SR-max v2 (integrazione gambe nuove)

**Files:**
- Modify: `scripts/run_portfolio_sr_max.py` (estendere `LEGS` con le famiglie passate ai gates nei Task 2/3)
- Output: `docs/reports/edge-factory/portfolio-sr-max-v2.{md,json}`

**Interfaces:**
- Consumes: definizioni gambe dei Task 2/3 (riusare le funzioni, non duplicare).
- Produces: ladder leva aggiornato + P(m≥5%) + correlazione media portafoglio (evidenza se le nuove famiglie abbassano la correlazione residua → SR(N) sopra 1.4).

- [ ] **Step 1: Se (e solo se) ≥1 famiglia è GO nei Task 2/3**, aggiungerla a `LEGS` in `run_portfolio_sr_max.py` importando dai runner (niente copia-incolla).
- [ ] **Step 2: Run** `uv run --frozen python scripts/run_portfolio_sr_max.py` → report v2.
- [ ] **Step 3: Sezione verdetto onesto nel report**: riga "SR(N) post-integrazione vs 1.40 baseline" e nota che nessuna leva oltre 4× è raccomandata sotto paletti funded. **Nota (correzione review): il cap 4× NON è in ADR-023** (ADR-023 regola consistency ≤0.35 e risk-per-trade, non la leva) — dichiararlo come scelta conservativa locale di questo sprint con rationale: restare sotto DLL 5%/trailing 4% dell'envelope funded (dossier C), coerente con BL-737 che documentava leva ~10× necessaria per 5%/mese a vol 30% (fuori envelope).
- [ ] **Step 4: Dipendenza Channel B (correzione review)**: aggiungere riga al report — la promozione a portafoglio funded passa da `check_dual_channel` ADR-023 (Channel B: 100+ sessioni paper, pass-rate ≥0.60, MC ≥0.60, consistency ≤0.35); SR(N) > 1.40 da solo NON autorizza eval.
- [ ] **Step 5: Commit** `feat(BL-742): portfolio SR-max v2 (+{n} gambe ortogonali)`.

---

### Task 6: BL-743 — Docs canoniche: direttive Renaissance-parity + stato registry

**Files:**
- Create: `scripts/set_registry_state.py` (CLI generica `--hid --stato --motivo --ref`, usa `HypothesisRegistry.update_status(persist=True)`)
- Modify: `ROADMAP.md` (nuova §15), `BACKLOG.md` (BL-739..743), `docs/ORACLE_AUTOPILOT_STATUS.md` (nota sprint, nessun cambio gate)

> Nota: il piano stesso (questo file) NON si auto-modifica in Task 6 — i checkbox dello sprint restano qui e si aggiornano a fine sprint nel commit di chiusura.

- [ ] **Step 1: CLI set_registry_state + test** (10 righe + 3 test: id valido, id inesistente → errore, persist scrive YAML).
- [ ] **Step 2: ROADMAP §15** — testo esatto:

```markdown
## 15. Direttive Renaissance-parity (2026-09-04)

Fonte: ricerca a fonti primarie in
`docs/reports/renaissance-parity-2026-09-04/` (dossier A/B/C + SYNTHESIS).

1. **Benchmark di parità onesto**: RenTec Medallion documentato (Cornell 2020)
   è Sharpe ≈ 2.0 lordo, beta ≈ −1 — non lo "Sharpe 7.5" leggendario.
   Il target di parità del canale personal è **Sharpe 1.8-2.2 a DD dichiarato**;
   il canale funded resta 0.5-1.5%/mese envelope (dossier C). Nessun
   obiettivo di rendimento assoluto nuovo: 5%/mese vale SOLO come mediana
   a vol 30% con MaxDD ~30% nel canale personale (BL-737), mai come promessa.
2. **Famiglie non-tecniche prioritarie**: ogni unità di ricerca della factory
   privilegia famiglie con meccanismo NON price-based (overnight/microstruttura,
   carry/basis, cross-pillar conditioning, positioning, sentiment) — è l'unica
   direzione che alza SR(N) sopra la saturazione 1.2-1.5 misurata (BL-737).
3. **Regola del pilastro**: ogni nuova ipotesi/lega nel registry dichiara il
   pilastro KB (01-13) del suo meccanismo e il decay atteso; le combinazioni
   fra pilastri (conditioning) sono first-class, non accessori. In questo
   sprint NESSUN carry su oro/commodities (Fase 2 dossier B non pianificata:
   curve futures non possedute — follow-up sbloccato da dati, vedi BL-743).
4. **Anti-drift finanziario**: nessuna eval si paga senza sim canonica ITM
   (ADR-018/023); tier funded primario MFFU Pro/Rapid + Topstep Standard +
   FTMO (dossier C §consigli). Il cap leva 4× della BL-742 è scelta locale
   conservativa dello sprint (sotto DLL 5% / trailing 4%), NON soglia ADR.
5. **Prereg invariato**: parametri frozen dalla letteratura PRIMA del run;
   soglie gauntlet identiche a Sprint 1/2; risultati negativi committati.
```

- [ ] **Step 3: BACKLOG** — voci BL-739..743 sotto la sezione factory (stesso formato BL-736/737), con AC puntati a questo piano.
- [ ] **Step 4: STATUS** — append nota "Sprint Renaissance-parity 2026-09-04 in corso: BL-739..741 qualificazione, BL-742 integrazione portafoglio, BL-743 direttive" (G5 resta REJECTED finché le nuove gambe non passano e il portfolio v2 non viene ri-qualificato).
- [ ] **Step 5: Suite completa + commit finale**

Run: `uv run pytest tests/unit -q -k "overnight or carry_policy or pillar_conditioning or registry or prereg" && uv run ruff check scripts/ tests/unit/ && uv run mypy --strict scripts/run_overnight_drift_sprint.py scripts/run_fx_carry_policy_rate.py scripts/run_pillar_conditioning_sprint.py scripts/set_registry_state.py`

```bash
git add ROADMAP.md BACKLOG.md docs/ORACLE_AUTOPILOT_STATUS.md scripts/set_registry_state.py tests/
git commit -m "docs(BL-743): direttive Renaissance-parity ROADMAP §15 + backlog BL-739..743 + registry state"
```

---

## Kill criteria (pre-registrati, ereditati dalla factory §8)

- Se NESSUNA delle 3 famiglie supera i gates → report onesto `sprint-3.md` con verdetto NO-GO complessivo e le famiglie REJECTED nel registry. Non si costruisce nulla attorno a zero edge.
- Se ≥1 famiglia è GO → BL-742 integra e la riqualifica portafoglio definisce se SR(N) sale sopra 1.4 (evidenza, non promessa).
- Le finestre tail (2020-03, 2022) sono riportate SEMPRE, anche quando la famiglia passa.

## Self-review (eseguito alla stesura)

1. **Copertura spec**: SYNTHESIS §5 Fase 1 (overnight) = Task 2; Fase 2 ridotta al carry (commodities XSMOM richiede curve futures non possedute → NON pianificato, dichiarato in BL-743 come follow-up sbloccato da dati); Fase 3 (meta-labeling-lite) = Task 4; Fase 5 (ricalcolo onesto P(m≥5%)) = Task 5. Docs/canon = Task 6. 2. **Placeholders**: nessuno; ogni step ha codice o comando. 3. **Coerenza tipi**: `load_1h(min_bars)`, `veto_scale(z, full_z)`, `carry_signal(rates)` definite una volta e riusate.
