# RISPOSTE D1–D15 — Studio trading-os → Oracle

Generato: 2026-08-19. Chiude l'handoff di `DOMANDE_APerte.md` (studio 19 repo
MoonDev fatto su altro PC) verificando tutto contro: (a) il codice dei repo
clonati in `knowledge/moondev-repos/`, (b) la codebase Oracle reale
(`/home/alin/_repos/oracle-trading`), (c) verifiche web mirate (Binance Vision,
API funding, letteratura).

## Premessa fondamentale — cosa è cambiato dalle assunzioni originali

Lo studio originale assumeva un progetto "trading-os" con 6 mesi di dati,
`health_check.py` cancellato, nessun layer execution. **Oracle oggi ha già
molto di quello che trading-os chiedeva**:

| Assunzione trading-os | Realtà Oracle (verificata 2026-08-19) |
|---|---|
| Solo 6 mesi di BTC 1h (~4300 bar) | Lake: **BTCUSDT 1m dal 2017-08-17, 4.7M righe**, tutti i TF (1m/5m/15m/30m/1h/4h/1d) — BL-305 ✅ |
| Nessun walk-forward serio | `analytics/backtest/walk_forward.py` + engine vectorized/nautilus + gate **DSR/PBO/CPCV** (ADR-017, `analytics/qualification/dsr.py`) |
| LightGBM da verificare | Già usato: `analytics/strategy/signals_r1.py` + regime ML |
| Nessun execution layer | `execution/brokers/ccxt_broker.py` (ccxt già dipendenza `>=4.5.64`), paper orchestrator con slippage ledger (BL-OPC-4 ✅); nautilus_trader clonato con **adapter Hyperliquid** (`adapters/hyperliquid/`) |
| Nessun kill switch | G4 hard-risk + `core/kill.py` (molto oltre il `kill_switch` di MoonDev) |
| Dati QQQ da Polygon (pagamento) | **`QQQ\|1d` già nel lake** (fonte yahoo) |
| Research phase da inventare | Convenzione `docs/knowledge-base/` (13 domini, 112 BL-KB items) già pronta ad accoglierla |

**Conseguenza**: le domande D1–D15 non vanno risolte costruendo un progetto
parallelo, ma portando i fattori candidati dentro la machinery Oracle
(`genetics/alpha/factors.py` → IC pre-test → CPCV/DSR/PBO). Il codice
trading-os originale (factors.py 13 fattori, walk-forward LightGBM) non è su
questa macchina, ma è quasi tutto re-implementabile meglio in Oracle.

### Cosa NON esiste ancora in Oracle (i veri gap)

Da verifica diretta di `genetics/alpha/factors.py` (1028 righe, libreria
`CuratedAlphaLibrary`): **non esistono** `bb_squeeze`, `bb_squeeze_release`,
`funding_rate`, `funding_z`, `liq_*`, `cvd_*`, `hour_of_day` (esistono invece
`bb_position`, `bb_width`, `volume_zscore_20`, `day_of_week`, `month_effect`,
e Hurst/variance-ratio nel regime detector BL-012). Questi sono i deliverable.

### Legenda

- 🟢 **ORA, $0** — backtestabile subito con dati già presenti o scaricabili gratis
- 🟡 **ACCUMULO** — iniziare a raccogliere ora, backtest tra 3-6 mesi
- 🔵 **LIVE-ONLY** — solo paper/live, non backtestabile
- ⚫ **SKIP** — scartato con motivazione

---

## D1 — Funding rate: storico ✅ RISOLTO

### D1.1 — L'API MoonDev ha lo storico funding?
**No, realtime only.** `api.py::get_prices` restituisce funding corrente per
224 coin; nessun endpoint `/funding/history` né param `since` (verificato su
api.py + README + `examples/33_btc_funding_oi_comparison.py`, che per lo
storico chiama infatti Binance `/fapi/v1/fundingRate`).

### D1.2 — Da dove prendere lo storico per backtest su OHLCV Binance?
**Binance, due vie (entrambe $0):**
1. **Via maestra — data.binance.vision**: i dump pubblici USDⓈ-M includono
   `fundingRate` (zip mensili e daily, dal **2020-01-01**), senza API key.
   È lo stesso pattern dell'adapter `BinanceVisionHistorical` già fatto in
   Opzione C (Pre-step ✅): va aggiunto come data-type del source adapter.
2. **Fallback — CCXT** (`exchange.fetch_funding_rate_history("BTC/USDT:USDT",
   since=..., limit=1000, params={"paginate": True})`): endpoint
   `/fapi/v1/fundingRate`, max 1000 righe/call, copertura da ~set 2019.
   Per 2 anni = ~2190 righe = **3-5 chiamate totali** (D7.2: banale).

### D1.3 — Allineamento 8h → 1h?
**Forward-fill dal timestamp di settlement, più `shift(1)` conservativo.**
Il funding è un evento discreto noto al settlement: la carry forward è la
semantica corretta ("costo di carry/crowding corrente"). **Non interpolare**:
creerebbe valori intermedi fittizi. Il `shift(1)` evita qualsiasi dibattito di
lookahead sul momento esatto in cui il rate diventa "noto" (il rate del periodo
[t-8h, t] si fissa a t). Warmup: primi 1-2 bar NaN, gestiti nativamente da
LightGBM o esclusi.

### D1.4 — Soglie: quali unità? (trovato un bug di interpretazione)
**Verificato sul CSV reale** (`fund_demand_bot/1019funding_rate.csv`): riga
campione `ETH-USD-dydx, 2.37` / `BTC-USD-dydx, 31.95`. Sono **percentuali
annualizzate** (dYdX ha funding orario). Quindi:
- `funding_rate_threshold = -22` → **-22% annualizzato**, non -0.00022 per-period;
- `short_funding_rate_threshold = 14` → **+14% annualizzato**.

Conversione su Binance (baseline 0.01%/8h ≈ **+10.95% annuo**):
- long (short squeeze): funding 8h ≤ **-0.2%** (= -0.002 ≈ -22% annuo) — evento raro, coda vera;
- short (long overcrowding): funding 8h ≥ **+0.13%** (+14% annuo) — meno raro.

**Raccomandazione**: fissare le soglie a priori in unità annualizzate
(long ≤ -20% ann, short ≥ +25% ann), poi **analisi di sensibilità** (non grid
optimization — è esattamente il data-snooping che ADR-017 vieta). In parallelo
costruire `funding_z` = z-score rolling (window 60d) del rate 8h: scale-free,
più adatto come feature ML della soglia secca.

### D1.5 — Servono i dati perp?
**No.** Il funding si usa come **indicatore di crowding/sentiment esogeno**
affiancato all'OHLCV spot — esattamente come fanno i bot MoonDev (che operano
su dati spot-like + colonna funding). Eventuale secondo fattore futuro: il
perp basis (prezzo perp - spot), ma richiede OHLCV perp (Vision li ha, costo
basso, rimandato).

### D7.2 — Pipeline concreta (chiusa qui)
```
Binance Vision zip fundingRate (BTCUSDT, mensili, 2020→oggi)
  → parse (fundingTime, fundingRate)
  → reindex su griglia 1h del lake, ffill, shift(1)
  → parquet data/lake/.../BTCUSDT/funding/ (lineage + coverage come BL-307 comanda)
  → fattori funding_rate, funding_z in genetics/alpha/factors.py
```
Volume: ~3 righe/giorno → trascurabile. Tempo stimato: mezza giornata compreso
adapter + test.

---

## D2 — BB Squeeze ✅ RISOLTO (regole esatte estratte)

Verificato su `Harvard-Algorithmic-Trading-with-AI/backtest/bb_squeeze_adx.py`
(letto integralmente).

### D2.1 — Feature binaria o filtro?
Nel codice MoonDev è un **filtro/gate**, non una feature: si entra solo su
transizione di rilascio + conferma ADX + rottura di banda.

### D2.2 — Serve `bb_squeeze_release`?
**Sì, ed è il cuore del segnale.** Regole esatte:
```python
squeeze = (upper_bb < upper_kc) & (lower_bb > lower_kc)   # BB dentro Keltner
# release: squeeze[-2] == True AND squeeze[-1] == False   (transizione ON→OFF)
# entry long:  released AND adx[-1] > 25 AND close > upper_bb
# entry short: released AND adx[-1] > 25 AND close < lower_bb
# exit: TP 5% / SL 3% fissi
```

### D2.3 — Come combinare con ADX?
MoonDev fa: release (trigger) → ADX>25 (filtro forza) → banda (direzione).
Nel modello ML: `bb_squeeze` (stato) + `bb_squeeze_release` (transizione) come
feature distinte; l'interazione release×ADX si lascia imparare all'albero.
Nota onesta: lo squeeze identifica **compressione, non direzione** — da solo
IC≈0 atteso; il valore è nella combinazione.

### D2.4 — Parametri
Confermati: `bb_window=20, bb_std=2.0, keltner_window=20, kc_mult=1.5,
adx_period=14, adx_threshold=25`. Il file fa anche `bt.optimize()` ma con
griglia stretta (e con range discutibili tipo `bb_window=range(10,15,5)` → solo
10!). **Decisione**: partiamo dai parametri MoonDev fissati a priori (RBI),
niente ottimizzazione prima dell'IC test. Da notare: questo script usa TA-Lib,
non le funzioni hand-rolled (quelle stanno in battle_core, vedi D10.1).

**In Oracle**: implementare `bb_squeeze` + `bb_squeeze_release` in
`genetics/alpha/factors.py` (mancano; `bb_position`/`bb_width` già ci sono),
registrare in `CuratedAlphaLibrary`, poi IC test sul lake intero. Corrisponde
alla strategia #25 "Volatility Squeeze" del catalogo G10 (BL-402).

---

## D3 — MoonDev API: key e limiti 🟡 PARZIALMENTE VERIFICATO

### D3.1 — La key è gratuita?
Il README dice: *"Visit https://moondev.com to get your free API key"* —
**free tier esiste**. MA i docs Polymarket rivelano **access tier**:
key standard = top 25 trader, key `_qe` ("Quant Elite") = lista completa.
Quindi: **free sì, ma alcuni endpoint/depth sono gated**. Non ho fatto probe
live della API in questo studio (no chiamata reale): **TODO** = registrarsi
(free) e verificare quali endpoint rispondono davvero con la key base.

### D3.2 — Storico vs realtime (verdetto per endpoint) — CORREZIONE IMPORTANTE
L'agente di ricerca iniziale era ottimista; la lettura diretta del README dice:
- **Liquidations multi-exchange**: live 10m/1h/4h/12h/24h/2d/5d + **archivi
  7d/14d/30d.json** → **storico massimo 30 giorni**, non di più.
- **Ticks/bars/candles**: `start_time`/`end_time` supportati, ma la profondità
  è "stored tick history" lato server, **non documentata** → trattare come
  storico breve (settimane, non anni).
- **HLP sentiment, smart money signals**: realtime only → 🔵 LIVE-ONLY.
- **Position snapshots**: 1-min cadenza, lookback default 24h → breve.

**Verdetto corretto**: MoonDev **non** sblocca backtest profondi. Il suo valore
è: (1) accumulo going-forward da iniziare ora, (2) integrazione live/paper.
Per backtest pluriennali la fonte è **Binance Vision** (vedi D4/D5).

### D3.3 — Rate limits
Dichiarati nel README: **market data (prices/orderbook/candles/ticks/bars) =
"NO RATE LIMITS"** (instradati dal loro nodo); altri endpoint con limiti
standard (gestione 429 negli example). Per 4300 barre 1h: irrilevante.

### D3.4 — Formato → Series 1h
- Liquidations: lista di dict `{symbol, side, value_usd, timestamp(ms)}` →
  `groupby(floor(ts, 1h)).value_usd.sum()`.
- Orderflow: `{by_coin, windows, cumulative_delta}` → prendere `cumulative_delta`.
- Ticks: `{p, sz, side, t}` → delta = `sz * (side==B ? +1 : -1)`, resample 1h.

---

## D4 — Liquidation cascade 🟢 PARZIALMENTE ORA + 🟡 ACCUMULO

### D4.1 — Letteratura: edge reale?
Il **meccanismo** è supportato: le vendite forzate creano overshoot poi
reversion (price impact classico). Accademico di riferimento trovato:
*"Fragmentation, Price Formation and Cross-Impact in Bitcoin Markets"*
(European J. Finance 2022) — le cascate di liquidazioni sono indicate come
concausa delle fat tails nei rendimenti BTC; più Alexander et al. (2019/2020)
su price impact dei derivati crypto. **Ma**: la soglia tradabile "compra dopo
cascata 10x" è roba da practitioner, non c'è un paper che la prescriva.
→ Si tratta come **ipotesi da preregistrare** (template D13.1), non come edge
acquisito. Coerente con la filosofia Oracle: i risultati negativi sono
artefatti di prima classe.

### D4.2 — Dati gratuiti? SÌ, meglio del previsto
**Binance Vision pubblica `liquidationSnapshot` daily per USDⓈ-M** (verificato:
è tra i data-type ufficiali dei dump, dal ~2020) — gratis, no key, stesso
pattern adapter esistente. MoonDev `all_liquidations` arriva a 30 giorni
(buono per cross-check e accumulo live). Coinglass free tier: limitato, non
necessario.

### D4.3 — Quanti eventi in 6 mesi?
Ordine di grandezza su BTC: giornate di cascata maggiore ($1B+): ~3-6 al
trimestre; eventi 1h significativi (>10× mediana del volume liquidato orario):
~20-60 in 6 mesi. **Sufficienti per un event study** (bucket pre/durante/post
come BL-440), **non** sufficienti per un modello supervisionato. Con 5 anni di
Vision (2020→) si arriva a centinaia di eventi: fattibile.

### D4.4 — Allineamento
Dati di eventi, non di stato: `liq_volume_1h = Σ(qty×price)` nel bucket
orario; nessun ffill. Fattori: `liq_volume_z` (z vs mediana rolling 30d),
`liq_ls_ratio` (rapporto long/short liquidati).

---

## D5 — CVD / Order flow 🟢 (via Vision aggTrades, pesante)

### D5.1/D5.2 — Serve tick data, confermato
Il CVD scanner MoonDev (`examples/28`) calcola il delta dai tick col tick rule.
Da OHLCV **non** si ricostruisce il CVD vero. Esistono proxy (signed volume =
`volume × sign(close−open)`, tick rule sul close): correlazione col CVD reale
bassa e dipendente dal path intra-bar → usabili solo come fattore grezzo,
etichettato come proxy.

### D5.3 — Costo dei tick storici Binance
**Binance Vision fornisce aggTrades mensili per simbolo, gratis.** Stima BTCUSDT:
~50-200 MB/mese compressi → **1 anno ≈ 1-2.5 GB**, 2 anni gestibili su disco.
Download: minuti/pochi ore. Poi aggregazione tick→CVD_1h una tantum. È il path
pulito per backtestare D5.4 sul serio.

### D5.4 — CVD divergence su crypto 24/7
Letteratura accademica scarsa (molto practitioner: "price up + CVD down =
divergenza → reversal"). → Ipotesi da preregistrare e testare con event study,
stesso regime di D4.

---

## D6 — Session seasonality 🟢 (testabile a costo zero)

### D6.1 — `futures_open` ha senso su crypto?
Codice verificato: domenica 20:45 long BTC → 23:45 close (sì, lo hanno scritto
proprio su dati BTC 15m, non solo CME). È un backtest ingenuo (file singolo,
zero risultati riportati). **Verdetto**: prior bassa, ma testarlo sul nostro
lake costa ~0 → si fa come curiosità preregistrata, non come priorità.

### D6.2 — `first_hr_breakout` (QQQ prima ora → BTC)
Regole verificate dal codice: breakout sopra/sotto il range della prima ora di
QQQ (9:30-10:30 ET) → long/flat BTC. Il codice usa CSV Polygon (pagamento) —
ma per noi: **`QQQ|1d` è già nel lake**; il QQQ **1h** non c'è. Opzioni $0:
Stooq intraday (limitato), IBKR paper 1m going-forward (BL-OPC-6, già in
piano), oppure — raccomandato come primo passo — la variante **BTC-only**
(hour-of-day, D6.3) che non richiede nessun dato nuovo.

### D6.3 — hour_of_day come feature
LightGBM gestisce categoriche nativamente (o target encoding). Rischi: bias
orario instabile tra regimi; crypto 24/7 ha "sessioni" solo come sovrapposizione
US/EU. → Inserire `hour_of_day` (UTC) + `day_of_week` (già in libreria) come
feature condizionanti, mai come edge standalone. Test di stabilità OOS via CPCV.

### D6.4 — Evidenza di stagionalità intraday crypto
Gli effetti day-of-week su crypto si sono attenuati post-2018 (mercato più
efficiente — coerente con Kyriazis 2019 già in NOTES.md); effetti orari attorno
all'open US documentati ma deboli/instabili. Trattare onestamente: probabilità
di edge standalone bassa, valore come feature di contesto.

---

## D7 — Walk-forward ✅ RISOLTO (cambia completamente scala)

### D7.1 — NaN nei nuovi fattori
LightGBM gestisce NaN nativamente; i fold boundary non cambiano. Regola: il
warmup del fattore (prime ~168 barre per funding, ~60 per hurst/squeeze) resta
NaN — si esclude dal training, e il calcolo rolling **non deve attraversare i
fold** (si calcola sul serie intera punto-a-punto, è già causalmente corretto
se ogni valore usa solo passato — come tutti i fattori Polars di Oracle).

### D7.2 — Pipeline funding → vedi D1.

### D7.3 — Walk-forward solo bb_squeeze per primo?
Sì, era il test più rapido — ma **non a 4300 barre**: vedi D7.4. E non con un
walk-forward artigianale: il fattore entra in `CuratedAlphaLibrary` → IC
pre-test → gate CPCV/DSR/PBO di ADR-017.

### D7.4 — 4300 barre bastano? **NO. Ma il problema non esiste più.**
Risposta onesta: 4 fold su 6 mesi di 1h = stima di Sharpe instabile, OOS
efficace ~800-1000 barre/fold → non pubblicabile, rischio overfitting alto
(coerente con KB-03: CPCV vuole più dati). **Ma**: il lake ha BTCUSDT 1m dal
2017 → resample 1h = **~78.000 barre su 9 anni** (`scripts/resample_lake.py`
esiste già). Questo è un campione credibile, con 2+ cicli bull/bear (2018,
2020-21, 2022, 2024-25). **Tutti gli esperimenti vanno fatti sulla storia
intera del lake, non sui 6 mesi.**

---

## D8 — HLP Sentiment / Smart money 🔵 LIVE-ONLY, confermato

### D8.1 — Semantica HLP z-score
Dal README: HLP è il vault market-maker di Hyperliquid; il tracker registra i
flip long↔short. La convenzione esatta del segno dello z-score **richiede probe
live con la key** (TODO insieme a D3.1).

### D8.2 — Come usarlo come fattore
I ranking smart-money sono per wallet: come fattore di mercato servirebbe
un'aggregazione (es. % dei top-100 wallet long su BTC). Fattibile solo live.

### D8.3 — Conferma: non backtestabile
Nessun endpoint storico nel README → **solo paper/live**. Piano: quando si
attiva un paper crypto, iniziare lo snapshot giornaliero (accumulo).

---

## D9 — Execution layer ✅ GIÀ PIÙ AVANZATO DI MOONDEV

### D9.1 — Collegamento MoonDev/NautilusTrader
Risposto dai fatti: `nautilus_trader` (clonato in `_repos`) ha
**`adapters/hyperliquid/`** (data + execution). In Oracle c'è già
`execution/brokers/ccxt_broker.py` e ccxt tra le dipendenze. Quindi:
ricerca/paper → ccxt; eventuale produzione crypto → adapter nautilus
Hyperliquid (da certificare come gli altri adapter, gate G6/G7). Le
`nice_funcs` di MoonDev sono script usa-e-getta: il nostro equivalente
architetturale è il broker adapter layer, già progettato meglio.

### D9.2 — Slippage
Oracle: `paper_orchestrator.py` ha già lo slippage ledger (BL-OPC-4 ✅).
MoonDev usa ordini LIMIT; nel paper crypto: assunzione post-only/limit +
spread reale da `bookTicker` — anche questo è un dump Binance Vision gratuito.

### D9.3 — Heartbeat/watchtower
Pattern trasferibile: systemd timer + alert Telegram — è esattamente il pattern
del backfill IBKR (`systemd/oracle-ibkr-backfill.timer`, il cui mancato
install è peraltro il gap aperto BL-OPC-6).

### D9.4 — Kill switch / risk gates
Il `kill_switch` MoonDev (chiudi tutto) in Oracle esiste già ed è più forte:
G4 hard-risk non bypassabile + `core/kill.py` + modalità PAUSE/FLATTEN.
Niente da costruire; solo da cablare sull'eventuale adapter crypto.

---

## D10 — AI Trading Battles / riproducibilità

### D10.1 — Indicatori hand-rolled
Confermato in `battle_core.py`: `_sma`/`_rsi` scritti a mano **per
riproducibilità cross-machine** (TA-Lib può variare tra build). Oracle fa già
la stessa cosa: tutti i fattori sono Polars puro in `factors.py`, nessuna
dipendenza TA-Lib nel percorso GA. L'Hurst R/S di trading-os è comparabile in
spirito all'Hurst/variance-ratio del regime detector (BL-012) — estimatori
diversi, stesso scopo.

### D10.2 — Il pattern "battle" è trasferibile?
Sì, come **harness di valutazione offline** per segnali LLM: stesso snapshot a
N modelli, chi decide meglio. È concettualmente il nostro AI swarm (Opzione C
Step 1, REDUCE_SIZE 66.7% beat SPY su bull 2020-21). Vincolo Oracle: nessun
capitale reale finché i gate non passano — il battle resta offline/paper.

### D10.3 — Come presentare i dati a un LLM
MoonDev: 72 candele + bid/ask + RSI/SMA nel prompt. Per noi: tabella CSV
compatta (ultimi N bar) + valori dei fattori deterministici già calcolati,
con l'LLM che motiva la decisione strutturata. Regola non negoziabile Oracle:
feature deterministiche separate dal giudizio LLM; l'LLM non tocca mai
l'execution path.

---

## D11 — Dati: gap e qualità

### D11.1 — Più storia? Già risolta per OHLCV
BTCUSDT 1m dal 2017 nel lake. Mancano e vanno aggiunti: **funding** (Vision,
D1), **liquidationSnapshot** (Vision, D4), **aggTrades** (Vision, D5),
verificare copertura ETH completa (ETHUSDT presente in coverage, da auditare
alla stessa maniera di BL-307).

### D11.2 — Data quality check
Spec pronta (coerente col pattern `audit_lake_metadata.py`):
1. duplicati timestamp → errore;
2. gap > 2 barre attese → warning + registrazione (1h crypto: mercato 24/7,
   nessun weekend da giustificare — più semplice che su FX);
3. barre volume zero consecutive > soglia → flag;
4. spike prezzo > 5σ (z robusto su rendimenti 1h) → verifica manuale;
5. monotonicità timestamp + hash lineage (già disciplina BL-307).

### D11.3 — I 7 CSV con ":" nel nome
Artefatto dello script di download (nomi tipo `ETH-USD-15m-2018-1-02T00:00.csv`
— i due punti sono legali su Linux, illegali su Windows). Non è corruzione dei
dati. Fix: normalizzazione del nome in ingestione; su questa macchina non
rompe nulla.

---

## D12 — Modelli

### D12.1 — LightGBM: è colpa del modello o dei fattori?
Principio primo: **nessun modello fabbrica edge da fattori senza edge**.
LightGBM è già in Oracle (`signals_r1.py`) — il collo di bottiglia è l'IC dei
fattori, non la capacità del modello. Sequenza corretta: IC pre-test per ogni
fattore nuovo (D13), poi modello. Se 0 fattori passano l'IC, cambiare modello
non serve.

### D12.2 — DRL (FinRL)?
**Prematuro.** Aggiunge sample inefficiency e non-stazionarietà a un problema
che non ha ancora fattori con edge. Anche il README research di RBI prescrive:
research → backtest → implement, non scorciatoie. Rimandare a: ≥3 fattori con
IC preregistrato superato (o un fattore forte).

### D12.3 — LLM come generatore di segnali?
Già sperimentato in Oracle: AI swarm 50 ticker (REDUCE_SIZE 66.7% beat SPY,
ma su bull market 2020-21 + sintesi Haiku ~30% vuote). È un edge condizionale
con validazione 2022-bear già in backlog (**BL-OPC-8**). Non serve reinventare:
si continua quella lane, con l'LLM fuori dall'hot path.

---

## D13 — Processo di research ✅ TEMPLATE PRONTO

### D13.1 — Template per fattore (compatibile con docs/knowledge-base/)
```markdown
# Factor: <nome> (data preregistrazione)
## Ipotesi economica      — una frase + regime atteso
## Fonte dati             — URL/comando, coverage YYYY-MM→, costo ($0 obbligatorio)
## Formula                — codice Polars (stile factors.py)
## IC atteso              — valore + minimum detectable effect
## Preregistrazione test  — split CPCV (embargo N barre), gate: DSR≥0.95,
                            PBO<0.1, CPCV OOS Sharpe; criterio di kill
## Condizioni di invalidazione — cosa lo falsifica
```
Va in `docs/knowledge-base/04-order-flow/` o dominio pertinente, con BL-KB item.

### D13.2 — IC: definizione operativa
**IC = Spearman(fattore_t, forward_return[t→t+h])** su orizzonti
**non sovrapposti** (per 1h: h=24 → blocchi giornalieri indipendenti; il
sovrapporsi dei rendimenti 1h gonfia l'autocorrelazione — Lopez de Prado,
*Advances in Financial Machine Learning*, cap. 7-8). Significatività:
block-bootstrap o Newey-West. Report: IC medio, std, **ICIR = media/dev**,
p-value. Script dedicato da creare: `scripts/ic_screen.py`.

### D13.3 — Soglie per giustificare un walk-forward
Coerente con Harvey-Liu-Zhu (t>3 dopo haircut; il nostro KB-01 misura ~30% di
decay post-pubblicazione, in linea con McLean-Pontiff 32%):
- **1 fattore**: ICIR > 0.05 e t-block > 2.5 → procede a CPCV;
- **run walk-forward completo**: giustificato con ≥3 fattori preregistrati
  che passano, oppure 1 fattore che passa nettamente.

### D13.4 — Monitoring decay
Rolling IC 90d su finestra espansiva; alert se rolling IC < 50% dello storico
per 2 trimestri consecutivi; ri-qualificazione automatica al trigger. È
esattamente il modulo I-E "Factor Timing" già fatto (I-01: Rank IC corrente +
decay detection) — i nuovi fattori ci entrano dentro, non serve altro.

---

## D14 — Polymarket / Prediction market ⚫ SKIP (con un pattern da tenere)

### D14.1
Asset class diversa (contratti binari su eventi), non pertinente al core
crypto-perp. Non va mescolato.

### D14.2 — `docs/polymarket-profitable-traders.md` (letto)
Endpoint che ranka i wallet profittevoli (soglia $300+ P&L 7d; free = top 25,
key `_qe` = lista completa — conferma il freemium di D3.1). **Pattern
trasferibile**: "classifica wallet profittevoli → segnale di positioning" su
Hyperliquid (dove `get_smart_money` esiste già) — live-only, semmai in fase
paper. Nessun contenuto strategico da rubare oggi.

---

## D15 — TypeScript / tooling ⚫ SKIP

### D15.1
`learn-typescript-from-python` (2433 file): solo consultazione. Serve soltanto
se un giorno toccherà l'SK Polymarket (TS). Skip.

### D15.2
Endpoint AI chat di MoonDev (OpenAI-compatible): Oracle ha già il provider
vsllm/claude-haiku via OmniRoute locale a $0. Nessun vantaggio, nuova
dipendenza esterna → skip.

---

## Matrice finale

| Fattore | Dati | Stato | Priorità |
|---|---|---|---|
| `funding_rate`/`funding_z` | Vision zip 2020→, $0 | 🟢 ORA | **1** |
| `bb_squeeze`/`bb_squeeze_release` | OHLCV già nel lake | 🟢 ORA | **2** |
| `hour_of_day`/`day_of_week` | già nel lake | 🟢 ORA | **3** |
| `liq_volume_z`/`liq_ls_ratio` | Vision liquidationSnapshot 2020→ | 🟢 ORA (event study) | **4** |
| `cvd`/`cvd_divergence` | Vision aggTrades (~1-2.5 GB/anno) | 🟢 ORA (pesante) | 5 |
| MoonDev liquidations/orderflow 30d | API free | 🟡 ACCUMULO | 6 |
| HLP sentiment, smart money | API free, realtime | 🔵 LIVE-ONLY (paper) | 7 |
| `first_hr_breakout` (QQQ 1h→BTC) | QQQ 1h non nel lake | 🟡 (IBKR going-forward) | 8 |
| Polymarket, DRL, MoonDev chat | — | ⚫ SKIP | — |

## Sequenza raccomandata (prossima sessione operativa)

0. **Prerequisito ignorato da troppo tempo**: `BL-OPC-11` — committare il
   working tree (242 file sporchi, tutto il pivot Opzione C non è in git).
   Qualsiasi lavoro nuovo va sopra questo.
1. Template D13.1 come documento in `docs/knowledge-base/` (30 min).
2. `scripts/ic_screen.py` (IC Spearman non sovrapposto + block bootstrap).
3. `bb_squeeze` + `bb_squeeze_release` + `hour_of_day` in `factors.py` →
   IC screen su BTCUSDT 1h 2017→ (78K barre). Costo: zero dati nuovi.
4. Adapter Vision `fundingRate` → `funding_rate`/`funding_z` → IC screen.
5. Adapter Vision `liquidationSnapshot` → event study cascate.
6. Solo ciò che supera i gate preregistrati va in CPCV/DSR/PBO (ADR-017) e poi
   eventualmente nel paper orchestrator.

### Limiti dichiarati di questo studio
- Nessun probe live della API moondev.com (key da registrare; D3.1/D8.1 restano
  da confermare empiricamente).
- Profondità reale dello "stored tick history" MoonDev non documentata.
- L'analisi delle 463 trascrizioni video non ha prodotto un'estrazione
  utilizzabile in questa sessione: le risposte vengono da codice, README e
  verifiche web. Le trascrizioni restano consultabili per approfondimenti.
- Stime dimensioni aggTrades e conteggi eventi cascata sono ordini di grandezza,
  da confermare al primo download reale.
