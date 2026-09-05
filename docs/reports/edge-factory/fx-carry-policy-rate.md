# BL-740 — FX carry policy-rate basket (EF-004@02-macro)

**Generated**: 2026-09-05T11:33:59.202633+00:00

**Prereg**: basket G10 FROZEN dalla letteratura (LRV 2011 RFS, Menkhoff 2012 JF).
Mapping 7 pairs × 8 currencies; CARRY_LAG_MONTHS=2.
Walk-forward test > 2022-12-31. Costs 1.5 bps/turnover, vol-target 10%, min bars 50,000.

**Verdetto famiglia: `NO_GO`** — 0/7 coppie passano entrambi i gate (haircut SR > 0.0 AND DSR > 0.5); soglia kill = 2.

## Dati

**FRED non disponibile** (FRED_API_KEY / ORACLE_DATA_FRED_KEY assenti): le seguenti coppie sono ESCLUSE e LISTATE qui — nessun silent skip:

| currency | series_id |
|---|---|
| USD | FEDFUNDS |
| EUR | ECBDFR |
| JPY | IRSTCI01JPM156N |
| GBP | IRSTCI01GBM156N |
| CHF | IRSTCI01CHM156N |
| CAD | IRSTCI01CAM156N |
| AUD | IRSTCI01AUM156N |
| NZD | IRSTCI01NZM156N |

**Coppie escluse** (manca almeno una gamba): EURUSD, GBPUSD, USDJPY, USDCHF, USDCAD, AUDUSD, NZDUSD

## Risultati per coppia

| pair | SR | haircut SR | DSR | MaxDD | ann ret | trades | cost drag |
| bars (tot / test) | status |
|---|---|---|---|---|---|---|---|---|---|
| EURUSD | +0.00 | n/a | n/a | 0.0% | +0.0% | 0 | 0.0000 | 0 / 0 | EXCLUDED_NO_RATES |
| GBPUSD | +0.00 | n/a | n/a | 0.0% | +0.0% | 0 | 0.0000 | 0 / 0 | EXCLUDED_NO_RATES |
| USDJPY | +0.00 | n/a | n/a | 0.0% | +0.0% | 0 | 0.0000 | 0 / 0 | EXCLUDED_NO_RATES |
| USDCHF | +0.00 | n/a | n/a | 0.0% | +0.0% | 0 | 0.0000 | 0 / 0 | EXCLUDED_NO_RATES |
| USDCAD | +0.00 | n/a | n/a | 0.0% | +0.0% | 0 | 0.0000 | 0 / 0 | EXCLUDED_NO_RATES |
| AUDUSD | +0.00 | n/a | n/a | 0.0% | +0.0% | 0 | 0.0000 | 0 / 0 | EXCLUDED_NO_RATES |
| NZDUSD | +0.00 | n/a | n/a | 0.0% | +0.0% | 0 | 0.0000 | 0 / 0 | EXCLUDED_NO_RATES |

## Tail-check pre-registrato (sempre presente)

Finestre dedicate: COVID 2020-03 e USD rally 2022. La riga `basket_log_return` è la media cross-pair sull'intero basket dentro la finestra (più negativo = peggio).

| finestra | basket log-return | # coppie nel basket |
|---|---|---|
| 2020-03 COVID FX dislocation (2020-03→2020-04) | +0.0000 | 0 |
| 2022 USD rally (Fed hikes + risk-off) (2022-04→2022-10) | +0.0000 | 0 |

### Tail per coppia (log-return cumulato sulla finestra)

| finestra | EURUSD | GBPUSD | USDJPY | USDCHF | USDCAD | AUDUSD | NZDUSD |
|---|---|---|---|---|---|---|---|
| 2020-03 COVID FX dislocation | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| 2022 USD rally (Fed hikes + risk-off) | n/a | n/a | n/a | n/a | n/a | n/a | n/a |

## Stima informativa swap/roll CFD

Il backtest usa spot 1h (no swap). Su broker CFD/OTC il carry overnight per XAU/cross FX è tipicamente 0.5%-2.0% annuo (dossier C — families carry); qui non viene addebitato ma è dichiarato come costo informativo per portare il basket in produzione su CFD broker.

## Limitazioni oneste

- **CARRY_LAG_MONTHS=2** copre la publication lag OECD IRSTCI01xx ma NON eventuali revisioni tardive (rare per i policy rates).
- **Proxy conservativa**: carry da policy rates ≠ carry da 3M forward swap rates; niente swap rates → edge teorico leggermente sottostimato.
- **Dollar-neutrality by construction**: ogni coppia ha USD su un lato ma i segni sono indipendenti → l'esposizione USD netta può essere +1 o -1 in qualsiasi mese (3 long-USD, 4 short-USD); il basket non è USD-cash-neutral in senso stretto — è *pairwise neutral* contro USD. Questa è la convenzione LRV/Menkhoff e va riportata onestamente.
- **N_trials=8** = 7 pairs + 1 cash-window sensitivity (frozen, prereg).
- **Tail 2020-03 / 2022** sono finestre pre-registrate; se la basket le attraversa senza distruzione, è un punto positivo; se le distrugge, è il failure mode noto della letteratura (Menkhoff compensation).
- **Env requirement**: il runner richiede una chiave FRED valida (32 char alfanumerica) in ``FRED_API_KEY`` (canonical, priorità alta) o ``ORACLE_DATA_FRED_KEY`` (nome del file .env del progetto, fallback). Per ottenere una chiave gratuita: https://fred.stlouisfed.org/docs/api/api_key.html . Senza chiave il runner degrada onestamente a verdict NO_GO con tutte le coppie ESCLUSE_NO_RATES (no crash, no silent skip).

## Verdetto

**`NO_GO`** con 0/7 coppie passanti (nessuna).
