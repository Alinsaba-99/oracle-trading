# ADR-020: Zero-cost data strategy — verified free sources only

**Data:** 2026-08-17
**Status:** ACCEPTED
**Deciders:** Alin (operator)
**Supersedes:** —
**Related:** ADR-019 (Lane B SimFin PIT), `no-paid-financial-data` + `data-constraint-zero-cost` + `databento-out` memories

## Context

Oracle mira a conti funded The5ers/Lucid/MFF. L'operatore ha budget **$0/mo per dati finanziari** —
vincolo hard, non negoziabile. Il deep-research synthesis 2026-08-15 raccomandava Databento
(free credits $125) ma la signup richiede carta italiana valida = rifiutata anche con saldo
€4000+. Polygon/Tiingo paid/ORATS/Norgate/CSI/EODHD/Twelve/Tardis/Kibot/FirstRate/IVolatility
sono tutti esclusi dallo stesso vincolo.

Senza strategia esplicita, ogni nuova lane/component tenta di arrangiarsi e finisce per
proporre fonti pago (BL-504 SimFin free tier, BL-505 Lane D VRP senza dati reali, ecc.).
Questo ADR codifica ufficialmente la regola e l'inventario delle fonti verificate.

## Decision drivers

- Budget $0/mo per dati finanziari — HARD RULE dall'operatore, non derogabile;
- Databento free credits richiedono carta valida = escluso in Italia;
- Lake deve essere riproducibile da chiunque abbia lo stesso budget (no lock-in a API pago);
- Gap di copertura (futures 1m going forward, OPRA options chains) dichiarati onestamente
  invece di workaround pago implicito;
- Operator ha già conto paper IBKR ($0 base + $5/mo futures bundle + $1.50/mo OPRA) —
  unica eccezione accettabile perché già attivo come conto paper.

## Options considered

### Option A — Mixed free + paid fallback

Pro: copertura completa (Polygon paid per futures 1m storici, Databento per OPRA).
Contro: viola la hard rule. Rifiutata.

### Option B — Pure free + IBKR paper as futures source

Pro: rispetta $0/mo, sfrutta conto IBKR esistente per futures.
Contro: gap di copertura storica (IBKR dà ~6-12m storico via API, oltre serve capture forward).
Rischio: dipendenza da IBKR Gateway attivo (container `ib-gateway` porta 4002).
Reversibilità: alta — ogni fonte è sostituibile.

### Option C — yfinance + FRED only (no SimFin, no IBKR)

Pro: $0 forever, zero set-up.
Contro: no fundamentals (manca SimFin per Lane B), no futures intraday (manca IBKR per Lane A/D),
OPRA options chains non disponibili.
Rischio: Oracle resta daily-equity only, non prop-firm futures.

## Decision

**Option B** — pure free + IBKR paper. Inventario fonti verificate 2026-08-16:

| Asset class | Fonte | Coverage | Cost |
|---|---|---|---|
| US stocks EOD 30y | Tiingo (free tier) | 1985-2025 | $0 email only |
| US stocks 1m 2y | Massive (free) | 2024-2026 | $0 email only |
| US stocks 1m 7y | Alpaca IEX (free) | 2018-2025 | $0 email only |
| US fundamentals PIT | SimFin (free tier) | 185 tickers US, 2015-2025 | $0 |
| Macro VIX/FRED | FRED + yfinance ^VIX | 1990-2025 daily | $0 |
| Crypto spot | Binance Vision (bulk S3) | 2017-2025 | $0 no auth |
| Crypto live | Binance REST public | real-time | $0 |
| Futures 1m going forward | IBKR Gateway (porta 4002, paper alinsaba99) | 6-12m storico via API + capture forward | $0 (conto paper esistente) |
| Futures 1m ground-truth sample | FirstRate S3 samples | 40 simboli × 5 TF, 2 sett sample | $0 no auth |
| Futures lake esistente | Dukascopy (legacy bulk) | 21 symbols / 169M rows | $0 |
| News RSS scraping | transformers NLP on RSS feeds | last 30 days, qualitativo | $0 |

**Gap dichiarati onestamente**:
1. Futures 1m storico > 2 anni — solo IBKR 6-12m via API. Going forward via cron (Step 6 Opzione C);
2. OPRA options chains (per Lane D VRP real) — non disponibili free. Lane D backtest usa Black-Scholes synthetic da VIX;
3. News sentiment fine-grained (AlphaAI free tier 100 req/day, insufficient per 50-ticker swarm);
4. Sector ETF intraday — yfinance delayed, sufficient per Lane B quarterly rebalance;
5. Pre-market / post-market — non necessari per i timeframe Oracle (1m+).

**Fonti escluse (mai proporle)**:
- Databento (carta italiana rifiutata — vedi `databento-out` memory);
- Polygon paid, Tiingo paid, ORATS, Norgate, CSI, EODHD, Twelve, Tardis, Kibot, FirstRate paid, IVolatility;
- Qualsiasi servizio che richieda CC anche per free trial.

## Consequences

### Positive

- Lake riproducibile $0 chiunque;
- Nessun lock-in a provider pago;
- SimFin + yfinance + Binance + FRED + IBKR = coverage sufficiente per Lane B (value) +
  Lane D (VRP synthetic) + AI swarm + dystopian stress;
- Gap dichiarati = nessuna aspettativa falsa su futures storici pre-2025.

### Negative

- Futures 1m storico going-forward richiede 5 anni di cattura per accumulare 5y di ES 1m
  (Step 6 Opzione C cron, non copre backtest storico pre-2025);
- OPRA options reali non disponibili → Lane D VRP è BS-synthetic, non real Greeks
  (vedi `lane-d-vrp-backtest-real-2026-08-17`: Sharpe -0.08 = edge assente anche con synthetic,
  per validare serve OPRA real che non possiamo avere gratis);
- News sentiment fine-grained mancante → AI swarm SentimentAnalyst ritorna 0 articoli
  su tickers minori (vedi `ai-swarm-historical-50tickers-2026-08-17`).

### Failure modes

- IBKR Gateway down → futures lane A/D bloccata. Mitigazione: container `ib-gateway` auto-restart,
  alerting su `docker logs ib-gateway`;
- SimFin bulk cached stale > 30 giorni → fundamentals PIT non aggiornati. Mitigazione:
  cron di refresh su `data/simfin/`;
- yfinance rate-limit → retry con backoff. Mitigazione: cache su `~/.cache/py-yfinance/`;
- Binance Vision S3 rate-limit → scaricare bulk offline, non streaming.

## Enforcement

- `tests/unit/test_data_sources_free_only.py` (TODO): asserisce che nessuna fonte in
  `analytics/` o `market/ingestion/` importi da `polygon`, `tiingo`, `databento`,
  `norgate`, `csidata`, `eodhd`, `twelvedata`, `tardis`, `kibot`, `firstrate` (paid),
  `ivolatility`;
- Pre-commit hook `grep -rE "import (polygon|tiingo|databento)" analytics/ market/` → blocca
  se trova (TODO: integrare in `.pre-commit-config.yaml`);
- `data/lake/metadata/coverage.json` (esiste già) deve elencare solo fonti da inventario ADR-020;
- Nuove lane in BACKLOG con dipendenza dati NON verificate → marcature BLOCKED-ADR-020.

## Follow-up

- **Step 6 Opzione C**: `scripts/backfill_1m_ibkr_paper.py` + systemd timer — cron quotidiano
  per accumulare futures 1m going forward;
- Refresh mensile SimFin bulk (`scripts/refresh_simfin_bulk.py` TODO);
- `chrome-devtools-mcp` one-shot per bypass 403 su fonti finanziari per ricerca (vedi
  `chrome-devtools-mcp-403-bypass` memory);
- Validazione Step 1 AI swarm 2022 bear market (per controllare bull-bias).
