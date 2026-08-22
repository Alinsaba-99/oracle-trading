# Sistema Multi-Portale Prop-Firm — Requisiti, Stato, Gap

> Data: 2026-08-22 · Stato: **NESSUNA DECISIONE PRESA** — documento di
> mappatura per la sessione congiunta. Obiettivo dichiarato dall'utente:
> un sistema che generi profitto (a) dal trading diretto e (b) dai
> portali prop-firm: **FTMO, FundedNext, The5ers, Alpha Capital Group,
> E8 Markets** e altri.
>
> Le regole delle firm in §1 provengono da ricerca web del 2026-08-22
> (Tavily su fonti terze: blog/recensioni). Sono **UNTRUSTED finché non
> verificate sulle pagine ufficiali con snapshot sha256** (disciplina
> `docs/firm_sources/`, pattern BL-095). Ogni tabella riporta la fonte
> e la data; mai fidarsi dei numeri senza quella verifica.

## 0. Il fatto economico (già formalizzato in S0.2)

I pass rate dichiarati dall'industria sono **5-10%**; le fee delle
challenge sono il motore di revenue delle firm. Il sistema deve quindi:
1. simulare la challenge PRIMA di pagarla (paper canonico BL-615 +
   governor);
2. comprare l'eval solo se la strategia è "ITM" sulla simulazione
   (criterio preregistrato, non ottimismo);
3. trattare ogni fee come costo di un'opzione, con EV dichiarato.

## 1. Registro regole 2026-08 (UNTRUSTED — da snapshot ufficiale)

### FTMO (CFD: forex, indici, commodities, stocks, crypto)
| Programma | Target | Daily loss | Max loss | Altro |
|---|---|---|---|---|
| 2-Step Challenge | 10% P1, 5% P2 | 5% (equity, 00:00 CE(S)T) | 10% statico | min 4 giorni/fase, no time limit |
| 1-Step (da feb 2026) | 10% | 3% | 10% **trailing** (reset su withdrawal) | **Best Day Rule 50%**, min 4 giorni |
| Funded | nessun target | 5% | 10% | Standard: **news ±2 min vietato** (aperture/chiusure, SL/TP inclusi); Swing: libero |

- **EA/automation**: permessi (discretionary, algorithmic, EA) — vietati
  loophole/HFT/arbitraggio; account indipendenti, no copia tra account;
  hedging consentito dentro lo stesso account, **vietato tra account**.
- **Max allocazione**: $400K per trader/strategia.
- **EA commerciali**: se altri trader fanno gli stessi trade → flag
  group-trading → payout negato/terminazione.
- Split 80% → 90% scaling; piattaforme MT4/MT5/cTrader (+ altre).
- Fonte: articoli terzi 2026-07-20/lug-ago 2026 — **verificare su
  ftmo.com/trading-objectives**.

### FundedNext (CFD + linea Futures separata)
| Programma | Target | Daily loss | Consistency |
|---|---|---|---|
| CFD (Stellar/altro) | 8-10% | 3-5% | nessuna su CFD |
| Futures Legacy/Bolt/Flex | varia | max loss EOD-based | **40% best day** |
| Futures Rapid | $1.250/3.000/6.000 (25/50/100K) | **nessun daily limit** | nessuna in eval, **40% in funded** |

- **EA**: permessi su **MT4/MT5 con fee aggiuntiva**; **VIETATI su
  cTrader e Match-Trader**. Obbligo: EA customizzato, strategia distinta
  per account, **max $300K per EA/strategia**; vietate app terze
  (Telegram/WhatsApp) dentro l'EA; **blacklist di "challenge-pass EA"**
  (Prop Pilot, Gold OneShot, Forex Flex, X Pass…).
- Copy: solo tra account propri (max $300K combinati); cloud copier vietati
  (richiesto VPS).
- Automation fee + nessuna assistenza tecnica sugli EA.
- Vietati: latency abuse, order flooding, 20+ strategie listate.
- Fonte: help.fundednext.com citato + blog 2026 — **verificare su
  fundednext.com + help center**.

### The5ers (CFD: forex, metals, indices, oil, crypto)
| Programma | Target | Daily | Max loss | Scaling |
|---|---|---|---|---|
| Bootcamp | 6% ×3 step | 3% pause (funded) | 5%/step, 4% funded | ×2 ogni 5% fino $4M, split 50→100% |
| High Stakes (New) | 10% + 5% | 5% **termina** | 10% statico | fino $500K, split 80→100% |
| Hyper Growth | 10% 1-step | 3% **pause** | 6% stop-out | ×2 ogni 10% fino $4M |
| Pro Growth | 10% 1-step | 3% **termina** | 6% | incrementale $500K, 75→100% |

- **EA**: permessi su tutti i programmi; **vietati tick scalping, HFT,
  arbitraggio, emulatori** (account cancellato senza rimborso). **VPS
  supportato** (tra le più algo-friendly).
- High Stakes: min **3 giorni profittevoli**/fase (giorno profittevole =
  ≥0.5% closed profit); news ±2 min su high-impact limitata.
- Daily loss anchor: il più alto tra starting balance ed equity a
  mezzanotte MT5 server time.
- USA esclusi.
- Fonte: recensioni giugno-ago 2026 — **verificare su the5ers.com**.

### Alpha Capital Group (UK, CFD)
| Programma | Target | Daily loss | Max loss |
|---|---|---|---|
| Alpha One (1-step) | 10% | 4% | 6% **trailing** (lock a initial dopo +6%) |
| Alpha Pro (2-step, 6/8/10%) | 8-10% | 5% | 6-10% statico |
| Alpha Swing | 10%+5% | 5% | statico |
| Alpha Three (3-step) | 8/4/4% | 5% | — |

- **⚠️ CONTRADDIZIONE NELLE FONTI, DA RISOLVERE**: una fonte terza dice
  "EA e automated trading permessi"; il sito della firm (citato) dice
  **EA solo risk-management/trade-assistance, NON fully-automated
  execution senza supervisione umana**; EA solo MT5 (no cTrader/DXtrade/
  TradeLocker) con **pre-approvazione del file .ex5 via email**.
- **Anti-HFT duro**: durata media trade >2 min; ≥50% del profitto da
  trade >2 min.
- **40% Best Day Rule** sui payout on-demand; ≥2% gross profit minimo;
  max allocazione $400K; split 80%.
- Hard breach (arbitraggio, group trading, HFT): cancellazione +
  forfeit profitti. Soft breach: esclusione profitti dei trade violanti.
- Fonte: alphacapitalgroup.uk (citato) + luxalgo — **la policy EA va
  verificata come PRIMA cosa** (decide se il canale è automatizzabile).

### E8 Markets
| Programma | Consistency | Note |
|---|---|---|
| E8 One | **40%** | 40% net profit > 50% del daily drawdown; buffer su payout |
| E8 Signature | **35%** | payout dedicati |
| E8 Pro | nessuna | payout daily, min 1% profit |
| Trader Stage | — | 5 giorni profittevoli ≥0.3% per payout; buffer = EOD trailing |

- **Anti-HFT**: max 50% dei trade sotto 1 minuto; rischio limitato
  all'1% per trade idea se pratiche proibite rilevate.
- Payout: **mai prelevare tutto il profitto** (va lasciato il drawdown
  buffer, o l'account chiude).
- Dynamic/EOD trailing drawdown; EA permessi (cap 5-10% citato).
- Fonte: video/recensioni 2026 — **verificare su e8markets.com**.

## 2. Le 7 clausole che uccidono i bot (comuni a quasi tutte)

1. **Drawdown su EQUITY, non balance**: le posizioni aperte contano;
   un bot con floating DD profondo passa il challenge e muore sul funded.
   Ogni firm ha un anchor diverso (balance vs equity, 00:00 CET vs MT5
   server time, EOD vs intraday trailing). → il nostro governor ha già
   `daily_loss_basis`/`overall_loss_basis`/`dd_mode`: vanno riempiti per
   ogni programma.
2. **Consistency rule (35-50% best day)**: i rendimenti "lumpy" (il
   profilo tipico degli EA aggressivi) passano l'eval e poi falliscono
   il payout. → serve un modulo sizing che distribuisca il profitto.
3. **Group trading**: EA commerciale = stessi trade di migliaia di
   altri = terminazione. → il sistema DEVE generare varianza
   proprietaria (entry timing, sizing, strumenti).
4. **Durata minima trade** (Alpha ≥2 min, E8 ≤50% sotto 1 min): lo
   scalping sub-minute è fuori in metà dei portali.
5. **News window** (FTMO funded Standard, The5ers HS): serve calendario
   macro economico (BL-103 aperto) + blackout enforcement.
6. **"Challenge-pass EA" vietati per nome** (FundedNext blacklist):
   la strategia deve essere genuina, non un trucco per l'eval.
7. **Cap di allocazione per strategia** ($300-400K): la crescita oltre
   richiede firm/strategie multiple.

## 3. Lato tecnico — cosa serve al sistema

| Componente | Stato in casa | Gap |
|---|---|---|
| Catalogo profili firm versionato (ADR-013) | ✅ `policy/prop_firm/profile.py` (FirmProgramProfile con dd_mode, basis, consistency, news_blackout, contract_cap, scaling) | mancano i programmi CFD: FTMO 1/2-Step, E8, Alpha Capital, The5ers 2026, FundedNext CFD |
| Governor fail-closed | ✅ `PropFirmRiskGovernor` (daily/overall, check_new_order, breach, rollover) | **consistency in tempo reale**, news blackout, daily *pause* vs *terminate* (The5ers HG), durata trade (anti-HFT), buffer payout |
| Catena paper canonica | ✅ BL-615 runner + manifest + fault suite (BL-616) | serve una modalità "challenge simulator" che usi il profilo firm come gate invece dei criteri G6 generici |
| Engine segnali real-time | 🟡 regime detector + factor timing (I-01) + research memory | performance registry per (strategia, asset, regime) (BL-420), signal blender regime-aware (BL-421), decay detection (BL-422) |
| Execution | 🟡 IBKR futures + ccxt crypto | **manca MT4/MT5/cTrader** = le piattaforme dei 5 portali |
| Kill switch / G4 | ✅ core/kill.py + risk non bypassabile | cablarlo sul bridge MT5 quando esisterà |

**"Strategia solida che tende alla perfezione in tempo reale"** —
traduzione onesta in requisiti: (1) edge qualificato prima del deploy
(factory BL-700..); (2) blender che pesa i segnali per regime corrente;
(3) decay detection che azzera i segnali degradati; (4) riqualificazione
periodica automatica; (5) nessun intervento discrezionale nell'hot path.
Nessuno di questi punti promette "perfezione": promette adattamento
misurato e preregistrato.

## 4. Lato infrastrutturale

| Tema | Requisito | Stato/decisioni aperte |
|---|---|---|
| **Bridge MT5 su Linux** | obbligatorio per FTMO/FN/5ers/E8/Alpha | 3 vie: (a) MetaApi cloud (API key = costo, da quantificare — contro ADR-020 se mensile); (b) mt5linux + Wine ($0, fragile); (c) VPS Windows nativo (costo VPS). **Non deciso** |
| VPS policy | The5ers: VPS supportato; FundedNext: VPS richiesto per copy; FTMO: da verificare; Alpha: allowed | va messo in ogni profilo firm |
| Clock/timezone | reset daily 00:00 CE(S)T (FTMO) vs MT5 server time (The5ers) vs America/Chicago (futures) | il governor ha il campo, serve test per fuso |
| Latency | sufficiente, MA niente latency arb (vietato ovunque) | il design deve ESSERE lento-per-design sull'esecuzione |
| Ops | systemd timer, heartbeat/watchtower, recovery restart | pattern già in casa (IBKR cron) |
| Multi-account | allocation per strategia, conti propri soli | policy di portafoglio multi-firm da definire |

## 5. Lato dati

| Dato | Serve a | Stato lake |
|---|---|---|
| FX major 1m/5m storici | backtest canale CFD | ✅ EURUSD 1m 2003→ (Dukascopy) + 58 cross 1m; manca profondità su tutte le coppie e su indici/commodity CFD |
| Indici/commodity CFD (US500, XAUUSD…) | idem | ⚠️ solo futures lake; CFD ≈ futures + spread, accettabile come proxy dichiarato |
| Calendario macro | news blackout | ❌ BL-103 aperto (3 eventi → servono 500+) |
| Spread/fee realistici per firm | simulazione challenge | ❌ da raccogliere per programma (fonti: siti firm) |
| Feed live del broker firm | esecuzione | il bridge MT5 espone il feed; ritardi/stop da gestire |
| Regime dati 24/5 (CFD chiude weekend) | gap handling | session guards esistenti |

## 6. Lato regolamentare (compliance)

1. **ToS come contratto machine-readable**: già il nostro approccio
   (ADR-013 + snapshot sha256 in `docs/firm_sources/`). Va esteso ai 5
   portali con la stessa disciplina di BL-095 (snapshot HTML + sha256).
2. **Le regole cambiano spesso** (FTMO ha lanciato il 1-Step a feb 2026):
   serve un monitor periodico delle pagine ufficiali (cron + diff +
   alert) prima di ogni nuova eval.
3. **Restrizioni geografiche**: The5ers esclude USA; noi operiamo
   dall'Italia → verificare giurisdizione per ogni firm (FTMO CZ,
   Alpha UK, E8 ?).
4. **Fiscale**: i payout prop-firm per trader italiani hanno un regime
   da chiarire con un commercialista (non è consulenza che il sistema
   può dare; va messo nel RUNBOOK come obbligo umano).
5. **Divieti trasversali da rispettare nel design**: niente hedging
   cross-account, niente copy tra trader, niente app terze negli EA,
   strategia "propria e distinguibile".

## 7. Gap sintetico vs l'obiettivo

```
CANALE FUTURES (Topstep/MFFU/Apex/TPT):   modello COMPLETO in casa
CANALE CFD/FOREX (FTMO/FN/5ers/E8/Alpha): profili=0, bridge=0,
    dati FX=parziale, calendario=assente
STRATEGIA REAL-TIME:                       factory+blender+decay da fare
DIRETTO (personal book):                   Lane B/crypto track (già in roadmap)
```

## 8. Decisioni aperte (nessuna presa)

1. **Canale**: CFD/forex (dove vivono i 5 portali) vs futures (già
   modellato) vs entrambi?
2. **Bridge MT5**: MetaApi (costo) vs Wine ($0) vs VPS Windows (costo)?
   — in tensione con ADR-020 ($0/mese).
3. **Alpha Capital**: se la policy EA è davvero "solo risk-tools +
   supervisione umana", serve una modalità **human-in-the-loop**
   (nuovo SupportMode: ASSISTED_ONLY) — accettabile?
4. **Multi-firm**: stessa strategia su più firm (varianza proprietaria
   obbligatoria) o strategie diverse per firm?
5. **Ordine dei portali**: quali per primi in base a (fee, regole più
   compatibili col nostro stile di edge, payout split)?

## 9. Prossimi passi eseguibili (proposti, NON approvati)

| BL | Cosa | Nota |
|---|---|---|
| BL-720 | Snapshot ufficiali delle pagine regole di FTMO, FundedNext, The5ers, Alpha Capital, E8 (HTML + sha256 in `docs/firm_sources/`) | trasforma §1 da UNTRUSTED a VERIFIED |
| BL-721 | Fixture dei programmi CFD verificati in `policy/prop_firm/fixtures.py` | dopo BL-720 |
| BL-722 | Governor: consistency rule + news blackout + pause-vs-terminate + durata trade + test | codice, indipendente dal canale |
| BL-723 | Spike fattibilità bridge MT5 su Linux (MetaApi vs Wine vs VPS) con costi reali | decision-doc, non codice |
| BL-724 | Calendario macro (unione con BL-103) | prereq news blackout |
| BL-725 | Cron monitor regole firm (diff pagine ufficiali) | prereq operatività continuativa |

---

## 10. Decisioni prese (2026-08-22, approvate dall'utente)

> Derivazione: "mettersi nei panni di chi è infinitamente tecnico e con
> fame di soldi". I due ribaltamenti fondativi:
>
> 1. **Le regole della firm sono la specifica di ottimizzazione, non
>    l'ostacolo.** Consistency rule + equity-based DD + durata minima
>    premiano una macchina che vince poco ogni giorno ("mietitore", non
>    "cecchino"). La strategia va ottimizzata per la *forma* del
>    rendimento (best-day < 35%, profitto distribuito su ≥5 giorni), non
>    solo per Sharpe.
> 2. **La challenge fee è il premio di un'opzione** (fail = −$19-100;
>    pass = conto funded 80-100% split). Convessità positiva, MA solo
>    con edge: comprare eval senza edge è una macchina per perdere
>    soldi (base rate 5-10%). Ogni eval si compra solo se la simulazione
>    canonica (BL-615 + profilo firm come gate) risulta ITM.

### D1 — Canale: futures come testa di ponte, CFD finanziato dai profitti
Il canale CFD/forex è dove vivono le 5 firm, ma si entra dal lato
**futures** (infrastruttura già completa in casa) partendo da
**FundedNext Rapid futures**: unica eval del lotto **senza daily-loss
limit** (il killer n.1 dei bot non c'è). Il primo conto funded paga
l'apertura del canale CFD. Non "uno o l'altro": sequenza.

### D2 — Bridge MT5: unico, generico, $0 finché non c'è edge
Tutte e 5 le firm girano su MT5 → **un solo bridge = attacco a N firm**
(è il moltiplicatore, il fossato). Ordine di esecuzione:
1. **Wine + `mt5linux` + conto demo gratuito** di un broker forex
   qualsiasi (IC Markets/Pepperstone: il "testnet" di MT5, nessun conto
   prop necessario) — $0;
2. MetaApi cloud solo se Wine si rompe;
3. VPS Windows solo con conto funded reale da servire.

### D3 — Alpha Capital: tecnicamente sì (heartbeat), strategicamente ultima
Se la policy EA è "solo risk-tools + supervisione umana" (contraddizione
da risolvere, BL-720), si implementa un **dashboard di supervisione con
heartbeat**: il bot propone, l'umano è un deadman-switch. È supervisione
legittima. Ma: babysitting non scala su N account → Alpha è ultima in
coda, non prima.

### D4 — Multi-firm: UNA strategia proprietaria × N firm × conti piccoli
La regola group-trading vieta EA *commerciali*; la nostra è nostra →
girarla su più firm contemporaneamente è legittimo. Due obblighi
tecnici: (a) **jitter** su timing/sizing/order-split per firm (fill non
identici, nessuna impronta condivisa); (b) **tanti account piccoli**
(10×$25k > 1×$250k): consistency più facile da rispettare sul piccolo,
breach non correlati, scaling cap per-account. Il farm è un insieme di
rubinetti di cassa piccoli e indipendenti, non una balena.

### D5 — Ordine dei portali
1. **FundedNext futures Rapid** — nessun daily limit in eval, è futures
   (= casa nostra), split 90% su Rapid Pro;
2. **The5ers Bootcamp** — $22, la più algo-friendly, VPS supportato,
   scaling a $4M: laboratorio a basso costo;
3. **FTMO** — payout più affidabile del settore, ma news-ban funded;
4. **E8 Markets**;
5. **Alpha Capital** (vedi D3).

### Sequenza di build approvata

| # | Step | Dipendenza |
|---|---|---|
| S1 | Il "mietitore": strategia a distribuzione costante nella factory (vincolo di forma: best-day < 35%, ≥5 giorni profittevoli) | factory BL-700.. |
| S2 | Simulazione challenge nel runner canonico con profilo firm come gate; eval si compra solo se ITM | BL-615 + BL-720/721 |
| S3 | Bridge MT5 generico ($0: Wine + demo) | BL-723 spike |
| S4 | Prima eval reale: FundedNext futures Rapid; poi The5ers Bootcamp | S1-S3 verdi |
| S5 | Col primo payout: più account, più firm, apertura canale CFD | S4 |

### Kill-switch (non negoziabile)
Se la factory non produce almeno un segnale che (a) passa l'IC screen e
(b) sta dentro la consistency rule in simulazione, **il farm non si
compra**. Finché non c'è edge il lavoro è gratis (costruire), mai a
pagamento (comprare eval).
