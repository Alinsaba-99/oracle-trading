# BOM Greenfield — Distillazione `trading-os/`

> Scritto il 2026-08-21 come se si dovesse **distillare tutto
> `trading-os/` e ripartire da zero con un progetto greenfield**.
> La domanda: cosa serve davvero, cosa è minerale grezzo, cosa è scarto?
>
> **Budget di distillazione: 821 MB → < 5 MB di essenza committata.**
> Il progetto greenfield non eredita codice: eredita **conoscenza
> strutturata**. Ogni artefatto distillato (D1-D8) è autoportante:
> potrebbe bootstrappare un repo nuovo domani, o alimentare l'Edge
> Research Factory di Oracle oggi (BL-700..709). Destinazione finale
> raccomandata: Oracle (lo studio 2026-08-19 §2 ha già stabilito che un
> progetto parallelo produce poco) — ma il kit è progettato per essere
> valido anche standalone.
>
> Legenda: **KEEP** (resta com'è) · **DISTILL** (→ artefatto Dx) ·
> **DROP** (cancellabile dopo distillazione).

---

## 0. Inventario (verificato con du, 2026-08-21)

| Componente | Size | Stato git | Verdetto |
|---|---|---|---|
| `knowledge/*.md` (5 file studio) | 68 KB | ✅ tracked | **KEEP** — è già distillato |
| `Harvard-Algorithmic-Trading-with-AI/` | 8.8 MB | ignored | **DISTILL** → D1, D5, D6 |
| `Trading-Algos/` (19 strategie + CSV) | 81 MB | ignored | **DISTILL** → D3 |
| `Hyperliquid-Data-Layer-API/` | 2.1 MB | ignored | **DISTILL** → D4 |
| `Moon-Dev-Code/` (3 PDF accademici) | 7.7 MB | ignored | **DISTILL** → D8 |
| Bot minori (Battles, Hibachi, Extended, short-bot, housecoin, Polymarket, Limitless) | ~2.5 MB | ignored | **DISTILL** → D7 (pattern già in NOTES), poi DROP |
| `custom-crypto-addresses/` | **560 MB** | ignored | **DROP** — vanity Solana, zero conoscenza |
| `learn-typescript-from-python/` | 60 MB | ignored | **DROP** — consultazione, non trading |
| `prize-picks-bot/` | 9 MB | ignored | **DROP** — sports, fuori tesi |
| Tool junk (vowels, espn, cleaner, bulk-delete) | ~650 KB | ignored | **DROP** |
| `video-library/transcripts/` (835 file) | 90 MB | ignored | **MATERIA GREZZA ESTERNA** — non entra nel greenfield; il miner BL-703 la legge da path configurato |
| `video-library/` (plan, manifest, TSV, script) | ~1 MB | ✅ tracked | **KEEP** |

**Riepilogo: 629 MB di junk immediato + ~100 MB di repo da distillare
e poi rilasciare. Sopravvive: < 5 MB.**

---

## 1. KEEP — ciò che è già distillato (non si tocca)

1. **I 5 file di studio** (`knowledge/moondev-repos/`): INDEX, NOTES,
   RISPOSTE_D1-D15, TASKS, DOMANDE_APerte. Sono il 90% del valore
   intellettuale: ogni regola esatta, ogni soglia, ogni verdetto è già
   scritto lì. Il greenfield parte da questi.
2. **`video-library/reading_plan.json`** (103 video triaged: RBI 50,
   BEGIN 18, FABLE 13, DATA 12, ARCH 10) + `moondev_videos.tsv` (355)
   + `transcripts_manifest.csv` + gli script di manutenzione. Sono la
   mappa della miniera; i transcripts restano fuori.
3. **`.gitignore` pattern**: i repo grezzi e i transcripts DEVONO
   restare ignored nel greenfield (mai più blob pesanti in history —
   lezione BL-607).

## 2. DISTILL — gli 8 artefatti del kit greenfield

Formato target: YAML/Markdown versionati, schema compatibile con il
**registry della Edge Research Factory** (BL-700: ogni strategia diventa
una `Hypothesis` con meccanismo, origine=practitioner, decay_atteso,
dati richiesti). Nessuna dipendenza dal codice originale.

### D1 — Factor Spec: BB Squeeze (da `backtest/bb_squeeze_adx.py`)
Regole esatte già estratte in RISPOSTE §D2:
```yaml
factor: bb_squeeze
  squeeze: (upper_bb < upper_kc) & (lower_bb > lower_kc)
  release: squeeze.shift(1) & ~squeeze
  entry_long: released & adx.shift(1) > 25 & close > upper_bb
  entry_short: released & adx.shift(1) > 25 & close < lower_bb
  exit: {tp_pct: 5, sl_pct: 3}
params: {bb_window: 20, bb_std: 2.0, keltner_window: 20,
         kc_mult: 1.5, adx_period: 14, adx_threshold: 25}
dati: OHLCV (nessun dato esterno)
nota: "compressione ≠ direzione: IC≈0 atteso da solo; valore
       nell'interazione release×ADX — preregistrare così"
```

### D2 — Factor Spec: Funding Extremum (da `fund_demand_bot` + D1.4)
```yaml
factor: funding_extremum
  unita: percentuale annualizzata (BUG ORIGINALE CORRETTO: i -22/+14
         del bot sono % annue, non per-period)
  long: funding_8h <= -0.2%   (~ -22% annuo, coda rara)
  short: funding_8h >= +0.13% (~ +14% annuo)
  funding_z: z-score rolling 60d del rate 8h (feature ML preferita)
  allineamento: reindex 1h, ffill dal settlement, shift(1) — MAI
                interpolare (D1.3)
  soglie_preregistrate: long <= -20%/ann, short >= +25%/ann,
                poi analisi di sensibilità (no grid optimization:
                è data-snooping vietato da ADR-017)
dati: Binance Vision fundingRate zip mensili 2020→ ($0, no key)
      fallback CCXT fetch_funding_rate_history paginate
```

### D3 — Hypothesis Registry: le 19 strategie Trading-Algos
Seed del registry factory. Verdetto per strategia (da NOTES.md):

| # | Strategia | Fattore | Verdetto → stato registry |
|---|---|---|---|
| 1 | funding_arbitrage | funding spread | ✅ `da_amplificare` (★) |
| 2 | fund_demand_bot | funding extremum | ✅ `da_amplificare` (★) |
| 3 | liquidation_bot | liq cascade reversal | ✅ `da_amplificare` (★) |
| 4 | HL arb.py | funding spread cross-coin | ✅ `da_amplificare` (★) |
| 5 | first_hr_breakout | session cross-asset | ✅ `da_amplificare` |
| 6 | capitulation_trade | volume spike → mean rev | 🟡 `da_amplificare` (prior bassa) |
| 7 | buy_the_dip | drawdown from high | 🟡 idem |
| 8 | first_vs_lasthr | session momentum | 🟡 idem |
| 9 | demand_zone_vol | support + volume | 🟡 idem |
| 10 | futures_open | seasonality domenicale | 🟡 curiosità preregistrata |
| 11-19 | trend_is_fren, breakout_wick, quant_gpt, lowcapgem, btc_etf, mexc, coinglass-fetcher… | — | ⚫ `morta` (pseudocode rotto / già coperto / non è un fattore) con motivazione append-only |

Ogni entry porta: meccanismo economico, dati richiesti, fonte
(file+riga del repo originale), `decay_atteso_pct: 40` (practitioner
→ haircut conservativo, spec factory §4).

### D4 — Data Source Spec (da `Hyperliquid-Data-Layer-API` + D3/D4/D5)
```yaml
binance_vision:            # $0, no key — la fonte maestra
  fundingRate: zip mensili dal 2020-01-01
  liquidationSnapshot: daily USDⓈ-M dal ~2020 (event study cascate)
  aggTrades: mensili, ~1-2.5 GB/anno BTCUSDT (per CVD vero)
  bookTicker: spread reale per slippage modeling
ccxt: fetch_funding_rate_history paginate (fallback, ~3-5 call/2anni)
moondev_api:
  costo: free key (tier base); `_qe` = gated
  storico_massimo: liquidazioni 30 GIORNI (non di più — D3.2 corretto)
  uso: solo accumulo going-forward + paper/live, MAI backtest profondi
  rate_limits: market data "no limits", resto standard (429 handling)
coinglass: free tier limitato — non necessario
microverse: L2 21 exchange free (BOM-P2 BL-717, per il futuro)
```

### D5 — Interface Contract: nice_funcs (da RBI + tutti i bot)
Il pattern ricorrente in 6+ repo, estratto come contratto per il
futuro `exchange_client` (NON codice, interfaccia):
`ask_bid(sym)`, `get_ohlcv2(sym, tf, n)`, `get_position(sym)`,
`limit_order(sym, side, sz, px)`, `adjust_leverage_usd_size(usd)`,
`get_sz_px_decimals(sym)`, `cancel_all_orders()`, `pnl_close()`,
`kill_switch()`. Oracle lo realizza già meglio col broker adapter
layer — il greenfield riceve il contratto, non l'implementazione.

### D6 — Methodology: RBI + preregistrazione (il cuore)
- Flusso **R → B → I** obbligatorio: research documentata prima del
  backtest, backtest prima dell'implement.
- Template fattore D13.1 (ipotesi economica, fonte $0, formula,
  IC atteso, preregistrazione test, condizioni di invalidazione).
- **IC = Spearman su orizzonti NON sovrapposti** + block-bootstrap;
  gate: ICIR > 0.05, t-block > 2.5, haircut 30% (Harvey-Liu-Zhu /
  McLean-Pontiff). Poi CPCV/DSR/PBO.
- Dati: storia intera del lake (78K barre 1h BTC), mai 6 mesi.
- DRL prematuro finché < 3 fattori passano IC (D12.2).
- LLM mai nell'execution path; feature deterministiche separate.

### D7 — Harness Spec: AI Battles pattern
battle_core condiviso + indicatori **hand-rolled** (riproducibilità
cross-machine, no TA-Lib nel path), heartbeat 5s + watchtower
esterno, preflight 6-check prima del go-live, snapshot identico a N
modelli. Nel greenfield: è il blueprint dell'harness di valutazione
offline per segnali LLM (battaglie su paper, mai capitale reale).

### D8 — Literature Notes (i 3 PDF, distillati in note)
1. Kyriazis 2019 (jrfm-12-00067): EMH crypto — l'edge esiste ma
   **svanisce nel tempo** (R/S, DFA, Hurst, GARCH) → walk-forward e
   decay monitoring obbligatori.
2. Sattarov 2020 (applsci-10-01506): DRL golden/death cross +14.4%/mese
   BTC — risultato dichiarato non replicato da noi; DRL resta prematuro.
3. Delfabbro 2021: psicologia (FOMO, overconfidence, 24/7) → nota per
   i vincoli di risk umani, non per codice.
I PDF originali: **DROP** dopo la nota (citazione + DOI sopravvivono).

## 3. DROP — la lista di cancellazione

| Quando | Cosa | MB liberati |
|---|---|---|
| Subito | custom-crypto-addresses, learn-typescript, prize-picks, 4 tool junk | 629 |
| Dopo D1/D5/D6 | Harvard-RBI | 8.8 |
| Dopo D3 | Trading-Algos (codice; 7 CSV con ":" nei nomi = artefatto Windows, nessun valore) | 81 |
| Dopo D4 | Hyperliquid-Data-Layer-API | 2.1 |
| Dopo D8 | Moon-Dev-Code | 7.7 |
| Dopo D7 | tutti i bot minori | 2.5 |
| Mai nel greenfield | transcripts/ (90 MB) — archivio esterno, accesso via path | — |

**Post-distillazione: `trading-os/` ≈ 2-3 MB** (5 docs + kit D1-D8 +
video metadata), interamente committabile, history pulita.

## 4. Skeleton del progetto greenfield

```
trading-os/                     (post-distill, tutto in git)
├── DISTILL-BOM.md              ← questo documento
├── knowledge/
│   ├── moondev-repos/*.md      (5 file studio, KEEP)
│   └── kit/
│       ├── factors/bb_squeeze.yaml          (D1)
│       ├── factors/funding_extremum.yaml    (D2)
│       ├── registry/trading-algos-seed.yaml (D3, schema factory BL-700)
│       ├── data-sources.yaml                (D4)
│       ├── exchange-client-contract.md      (D5)
│       ├── methodology-rbi.md               (D6)
│       ├── battle-harness-spec.md           (D7)
│       └── literature-notes.md              (D8)
└── video-library/              (plan + manifest + script, no transcripts)
```

Regole del greenfield:
1. Nessun file > 1 MB committato (hook large-files già attivo).
2. Ogni ipotesi entra solo via schema registry (mai prosa libera).
3. Ogni claim esterno: `claim_non_verificato` finché non auditato.
4. $0/mese sempre (ADR-020 ereditato come principio).

## 5. Definition of Done della distillazione (BL-718)

- [ ] D1-D8 scritti in `knowledge/kit/` e committati
- [ ] Ogni parametro/soglia presente nei repo originali compare in un
      artefatto (nessuna regola persa)
- [ ] Repo originali cancellati dal disco (821 → ~3 MB)
- [ ] README greenfield aggiornato con lo skeleton §4
- [ ] Suite factory (BL-700) carica il seed D3 senza errori di schema

## 6. Gap dichiarati

1. **Transcripts non minati**: 835 file restano materia grezza esterna;
   il miner BL-703 li consumerà senza spostarli nel greenfield.
2. **MoonDev API key mai probata** (D3.1/D8.1): free tier e profondità
   reale dello storico restano da verificare live prima dell'uso.
3. **CSV originali dei bot**: unici dati non riprodotti (funding sample
   dYdX, ETH 15m 2023) — ricreabili da Binance Vision/CCXT; non vale la
   pena tenerli (uno ha anche il nome invalido).
4. La distillazione **perde il codice eseguibile** dei bot per scelta:
   se un giorno servisse, i repo originali sono su GitHub
   (moondevonyt) — il kit tiene i permalink.
