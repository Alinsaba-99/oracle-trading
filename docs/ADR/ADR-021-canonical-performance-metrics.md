# ADR-021 — Semantica canonica dei metrici di performance (P1-A)

> Stato: ACCEPTED
> Data: 2026-08-20
> Relazione: implementa la remediation F-01 del dossier architetturale
> 2026-08-19; si appoggia ad ADR-011 (separazione discovery/qualification)
> e ADR-017 (validazione overfitting) che questi metrici alimentano.

## Contesto

Il codicebase conteneva **cinque implementazioni indipendenti dello
Sharpe** con semantica divergente sugli edge case:

| caso | statistics | execution | walkforward | MetricsCalculator |
|---|---|---|---|---|
| serie vuota | nan | 0.0 | 0.0 | 0.0 |
| 1 osservazione | nan | 0.0 | 0.0 | 0.0 |
| varianza zero, media > 0 | +inf | 0.0 | 0.0 | +inf |
| varianza zero, media < 0 | 0.0 | 0.0 | 0.0 | -inf |
| varianza zero, media = 0 | 0.0 | 0.0 | 0.0 | 0.0 |
| serie mista (ppy=252) | 5.8976… | 5.8976… | 5.8976… | 5.8976… |

(caratterizzato il 2026-08-20, tabella in
`tests/unit/test_metrics_canonical.py`).

Dopo l'incidente R5 (inflazione 31× dello Sharpe) i gate G5/G6 vengono
decisi confrontando numeri prodotti da questi moduli: una divergenza di
semantica su un caso limite produce **verdetti di gate falsi**, il difetto
più costoso che questo repository possa generare. Inoltre
l'annualizzazione era hard-coded a 252 in moduli che ricevono anche serie
mensili/intraday.

## Decisione

1. **Unica implementazione canonica**: `analytics/metrics/canonical.py`
   (Sharpe, Sortino, Calmar, max drawdown). Ogni altro modulo delega.
2. **Golden vectors**: `tests/unit/test_metrics_canonical.py` congela la
   semantica. Qualsiasi modifica richiede un emendamento a questo ADR e la
   riscrittura cosciente dei golden vectors.
3. **Semantica adottata**:
   - `sharpe = mean / std(ddof=1) * sqrt(periods_per_year)`;
   - `n < 2` → `0.0` (indefinito riportato come zero, mai NaN);
   - `std == 0` → segno della media: `+inf` / `-inf` / `0.0`. Una serie a
     rendimento costante positivo ha rendimento corretto per il rischio
     *infinito*; collassarla a 0.0 la nascondeva dai confronti di gate;
   - `periods_per_year` esplicito ai boundary di gate (252 daily, 12
     mensile, …). Il default 252 è comodità per codice di ricerca daily.
4. **Eccezione documentata**: `engines/vectorized.py
   _risk_metrics_from_equity` riceve una curva equity e calcola lo Sharpe
   su log-return con `periods_per_year` float derivato dalla spaziatura
   reale delle barre (fix del 31×). Non delega al modulo canonico per
   natura dell'input, ma la formula `mean/std*sqrt(ppy)` è la stessa.

## Alternative considerate

- **Mantenere lo 0.0 sullo zero-variance** (comportamento execution/
  walkforward): respinto — nasconde i casi degeneri e divergeva già dal
  path MetricsCalculator che i test `test_metrics.py` pinnavano a ±inf.
- **NaN al posto di ±inf**: respinto — NaN si propaga silenziosamente
  nelle comparazioni (`x > 0.5` con NaN = False = rigetto implicito del
  gate), esattamente la classe di errore che questo ADR elimina.
- **Risk-free rate nel Sharpe**: respinto per ora — nessun modulo esistente
  lo sottrae; introdurlo cambierebbe ogni numero storico senza golden
  vectors di riferimento. Se necessario: nuovo ADR + golden vectors nuovi.

## Conseguenze

- Comportamento uniforme su tutti i path (qualification execution,
  walkforward, statistics bootstrap, MetricsCalculator).
- I test che pinnavano il vecchio collasso a 0.0
  (`test_multiasset_walkforward.py::test_constant_returns_zero_std`) sono
  stati aggiornati alla nuova semantica, con riferimento a questo ADR.
- Prossimi passi della migrazione P1-A: `analytics/metrics/robustness.py`
  (point estimate delegato), runner paper canonico (P1-B).

## Emendamento 1 (BL-614, 2026-08-20) — semantica frequency-aware congelata

BL-614 estende i golden vectors al path Polars e congela la tabella di
annualizzazione per frequenza:

- **Tabella canonica** `analytics/backtest/metrics.py::
  FREQ_TO_PERIODS_PER_YEAR` — `1d=252`, `1h=6048`, `30m=12096`,
  `15m=24192`, `5m=72576`, `1m=362880` (252 sessioni × ore/minuti per
  sessione). È l'unica fonte di verità per il mapping freq → ppy;
  aggiungere una frequenza richiede un emendamento a questo ADR.
- **Golden vectors Polars**: `tests/unit/test_metrics_canonical_polars.py`
  pinna Sortino/Calmar attraverso `MetricsCalculator` con gli stessi
  numeri hand-computed del modulo canonico, più vettori su serie oraria
  (6048 punti, seed deterministico) e lo scaling `sqrt(ppy)` su tutta la
  tabella — la classe di bug dell'incidente R5 (annualizzazione errata)
  non è reintroducibile silenziosamente su nessuno dei due path.
- `MetricsCalculator.calmar_ratio` accetta ora `annualization_factor`
  (default 252): la formula canonica già annualizzava il growth composto
  con `periods_per_year`; il path Polars ora può passarlo esplicitamente
  come gli altri metrici.
