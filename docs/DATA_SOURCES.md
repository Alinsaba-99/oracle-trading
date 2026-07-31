# Oracle Data Sources — Coverage Matrix

> Aggiornato: 2026-07-31 (post BL-304 futures intraday a tappeto)

## Coverage Reale del Data Lake

```
ASSET CLASS    TF     Stato      Copertura                Fonte
─────────────────────────────────────────────────────────────────────
FUTURES CME   1m     🟡 parziale 2010+ (Databento key)    Databento/IBKR
(35 simboli)  1h     ✅ 35/35    2024-03 → oggi (13.7K)   yfinance
              1d     ✅ 35/35    2000 → oggi (6.5K)       yfinance/stooq

FX majors     1m     ✅ 9/9      2003 → oggi (8.6M)       Dukascopy
+ crosses     1h     ✅ 28/28    2003 → oggi (140K)       Dukascopy
              4h     ✅ 24/24    2003 → oggi (37K)        Dukascopy
              1d     ✅ 28/28    2003 → oggi (7K)         Dukascopy/histdata

Crypto       1m     ✅ 2/2      BTC/ETH 2017 → (4.7M)    Binance REST
              1h     ✅ 4/4      BTC/ETH/SOL/BNB          Binance REST
              4h     ✅ 2/2      BTC/ETH                  Binance REST
              1d     ✅ 4/4      BTC/ETH/SOL/BNB          Binance REST

Equities/ETF  1d     ✅ 11       SPY/QQQ/AAPL/MSFT/TLT/
                              GLD/DBA/DIA/IWM/...         yfinance
              1m     🟡 IBKR TWS/Gateway (non attivo)    IBKR

Metalli FX    1m     ✅ XAU/XAG  2003 → oggi (7.9M)      Dukascopy
```

## 35 Futures CME Coperti (1h + 1d)

| Gruppo | Simboli |
|--------|---------|
| Index | ES, NQ, YM, RTY, MES, MNQ, MYM |
| Energy | CL, NG, RB, HO, MCL |
| Metals | GC, SI, HG, PL, PA, MGC |
| Rates | ZN, ZB, ZF, ZT |
| Grains | ZC, ZW, ZS, ZM, ZL |
| FX | 6E, 6J, 6B, 6A, 6C, 6N, 6S, M6E |

## Gap Residui (per parità col forex 1m dal 2003)

| Gap | Fonte necessaria | Costo | Stato |
|-----|-----------------|-------|-------|
| Futures 1m 2010+ | Databento free tier | 0$ (1GB/mese) | 🔴 serve API key |
| Futures 1m 2010+ | IBKR TWS/Gateway | 0$ (paper) | 🔴 serve login browser |
| Futures 1h pre-2024 | Databento / IBKR | 0$ | 🔴 come sopra |
| Equities 1m | Polygon | $29/mo | opzionale |

## Fonti e Rate Limits

| Fonte | Asset | TF | Profondità | Auth |
|-------|-------|----|-----------|------|
| **yfinance** | Futures, EQ, FX | 1h max 730gg; 1d max | 2000+ daily | nessuna |
| **Dukascopy** | FX 28 coppie, XAU/XAG | 1m/5m/15m/30m/1h/4h/1d | 2003+ | nessuna |
| **Binance REST** | Crypto spot | 1m..1d | 2017+ | nessuna |
| **Databento** | CME futures | 1m..1d | 2010+ (free 1GB/mo) | API key gratis |
| **IBKR REST** | Futures, EQ | 1m..1d | ~1 anno | login browser |
| **Stooq** | Futures | 1d | 1990+ | nessuna |
| **HistData** | FX | 1m..1d | 2003+ | nessuna |

## Continuous Contracts

- Le serie yfinance (`ES=F`) sono **continuous proxy**: roll e adjustment
  fatti dal provider (documentato in provenance)
- `scripts/build_curated_contracts.py` consolida le partizioni Hive in
  `data/lake/curated/<SYMBOL>_<TF>.parquet` con validazione continuità
- Roll esplicito per contract month (ESU26→ESZ26): `market/roll.py`
  (serve dati per contract month da Databento)
