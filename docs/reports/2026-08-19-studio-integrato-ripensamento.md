# Studio integrato 2026-08-19 — Ripensamento del progetto

> Input: (1) ricerca web su MoonDev (prodotti, reputazione, verifica claim),
> (2) inventario di tutti i repo trading sul PC, (3) ground truth della
> codebase Oracle. Obiettivo: basi fattuali per ripensare il progetto in toto.
> Fonti puntuali nel testo; le risposte D1-D15 in
> `../../knowledge/moondev-repos/RISPOSTE_D1-D15.md`.

---

## 1. MoonDev: chi è, cosa vende, cosa è vero

### 1.1 Identità (verificato via GitHub API, 2026-08-19)
- Account GitHub dal 2022-10-15, 26 repo, ~2.7K follower, ~113K iscritti YouTube.
- Bio: "i believe code is the great equalizer so i share all my quant code on youtube".
- Repo più attivo: **Hyperliquid-Data-Layer-API** (push 2026-08-13, ★114) —
  ci sta lavorando ora. Il "famoso" Harvard-RBI (★448) è fermo ad aprile 2025.
  La direzione del suo business si è spostata su **Hyperliquid + AI battles**.

### 1.2 Prodotti e prezzi

| Prodotto | Cosa è | Prezzo |
|---|---|---|
| **Hyperliquid Data Layer API** | 60+ endpoint (liq, whales, orderflow, HLP, HIP3, Polymarket) | Free tier con cap (whales ≤250, top-traders ≤50); chiavi **Quant Elite** (`_qe`) = risultati pieni (whales 5.000, traders 1.000). Elite incluso nel corso; prezzo standalone non documentato |
| **Quant App / Moon Dev App** | App desktop (Electron) di disciplina: auto SL/TP, max-DD lock, session lock, liquidation intel. Client-side, AES-256, no backend | Gratis (beta) |
| **AI Trading Battles** | 6 modelli frontier (Claude Opus, GPT-5.6, Gemini 3.1, Grok 4.5, Kimi K3, DeepSeek V4) tradeano **$100 reali ciascuno** su BTC perp Hyperliquid, 1x leva, stesso snapshot orario, decisioni+ragionamenti pubblicati | Gratis, pubblico (moondev.com/ai) |
| **Algo Trade Camp** | Corso lifetime: Zoom privati, Discord, vault, bot/agenti GitHub, Quant Elite | **~$1.795** (o 2×$949), 90gg garanzia |
| **Funding program Hyperliquid** | Streami il tuo trading su YouTube → $250 iniziali, scale a $1K+ se consistente, tieni 100% profitti | Gratis (è lui che paga, in cambio di contenuto) |

### 1.3 Claim vs evidenza

| Claim | Verdetto ricerca web |
|---|---|
| "2,610% strategy", "Sharpe 5.37", "192,726% ROI" | **Solo backtest/screenshot**. Nessuna prova live auditata, nessun wallet verificato da terzi. Il 5.37 Sharpe è una strategia HIP-3 "trading only when markets are closed" — mai validata indipendentemente |
| "US Gov BANNED Fable 5" | Evento reale di contesto (direttiva export-control giugno 2026 su Fable 5/Mythos 5 — fonte da confermare indipendentemente), **ma non riguarda i suoi bot**: è titolo acchiappa-click agganciato a un fatto esterno |
| AI Battles = $100 reali | Plausibile (Hyperliquid è on-chain, quindi in linea di principio verificabile), **ma nessuna verifica indipendente dei wallet è emersa dalla ricerca** |
| "how losing 10k taught me" | Ammette perdite reali — arco narrativo onesto, ma nessun track record auditato |

### 1.4 Reputazione (Reddit/Trustpilot/YouTube)
- **Positiva come educatore**: Trustpilot del corso pieno di 5 stelle, community
  Discord apprezzata, r/algotrading lo cita come buon punto di partenza
  ("I learned from Moondev on YouTube. Took his course. It was good").
- **Scetticismo di genere**: "course shiller", claim "10000% within one day",
  un commento secco: "moon dev has 0 clue what he's doing". Nessuna accusa di
  scam diffusa.
- **Incentivi**: il revenue viene da corso ($1.795) + ecosistema Hyperliquid
  (funding program, Quant App, API Elite) → **incentivo strutturale a mostrare
  backtest impressionanti**. I suoi numeri vanno letti con questa lente.

### 1.5 Verdetto d'uso per noi

| Uso | Sì/No |
|---|---|
| **Ispirazione fattori** (funding extremum, liq cascade, BB squeeze, RBI) | ✅ SÌ — ipotesi economiche reali, codice ispezionabile |
| **API come fonte dati** (accumulo live, free tier) | ✅ SÌ, con cap free — sufficiente per ricerca |
| **Riferimento metodologico** | ❌ NO — troppo superficiale; Oracle ha già DSR/PBO/CPCV |
| **Claim di rendimento** | ❌ NO — marketing backtest-only |
| **Corso a pagamento / Quant App** | ⚫ NO — $0/mese è hard rule; la Quant App replica ciò che il nostro G4 già fa |

---

## 2. Cosa c'è su questo PC (inventario verificato)

| Repo | Origine | Stato | Ruolo |
|---|---|---|---|
| **oracle-trading** (1.2GB + lake 11GB) | Progetto nostro | attivo 2026-08-19, **242 file non committati** | IL progetto |
| freqtrade | clone upstream | 2026-06-17, pulito | riferimento crypto bot |
| nautilus_trader | clone upstream + 2 note di ispezione nostre | 2026-06-17, pulito | candidato execution engine |
| qlib (Microsoft) | clone upstream | 2026-04-22, pulito | riferimento ML quant |
| TradingAgents (Tauric) | clone upstream + 16 file toccati | 2026-06-14 | base smoke test agenti |
| stratevo, tradesight, inalpha, FinClaw | cloni di terzi | apr-giu 2026 | studio (piani integrazione mai eseguiti) |
| gsd-pi (+presets) | tooling progetti | 2026-06-30 | harness, non trading |
| `.vibe-trading` | sessioni sperimentali nostre | **fermo a giugno 2026** | abbandonato |
| `trading-os/knowledge` + `video-library` | studio MoonDev (altro PC) | 19 repo + 463 trascrizioni | ✅ studiato (D1-D15 chiuso) |

**Fatti chiave**:
1. **Oracle è l'unico progetto di trading nostro**. Tutto il resto sono cloni
   di riferimento quasi intonsi (aggiornati nello stesso sweep di metà giugno).
2. freqtrade/nautilus/qlib sono cloni upstream: non c'è lavoro nostro dentro
   da salvare, solo la scelta di quale framework usare.
3. inalpha/FinClaw/stratevo/tradesight hanno **piani di integrazione scritti
   in docs/ ma mai eseguiti** (plan-integration-inalpha-varrd.md,
   plan-integrazione-kairos-finclaw.md) — debito di ambizione, non asset.
4. `.vibe-trading` (ipotesi EMA-20 momentum su OKX, paper sessions giugno):
   esperimento morto — conferma che il pattern "prototipo veloce fuori da
   Oracle" produce poco; meglio dentro Oracle con la sua disciplina.

---

## 3. Oracle: ground truth (verificato a mano, 2026-08-19)

### 3.1 Cosa c'è davvero
- **Test**: 2.555 funzioni test in 190 file — suite reale e corposa (il claim
  "2903 passed" del backlog è plausibile).
- **Data lake**: 11GB su disco. BTCUSDT 1m dal **2017-08-17** (4.7M righe),
  tutti i TF; EURUSD 1m 2003→; SOL/BNB 1m completi; ES 1h 36K righe;
  futures intraday storici = gap (solo going-forward via IBKR paper, timer
  systemd **non installato** — BL-OPC-6).
- **Report edge**: tutti presenti su disco (lane-b-composite, lane-d-vrp,
  ai-swarm, s0-1/s0-2, multiasset). La cultura dei verdetti negativi è reale.

### 3.2 Il bilancio onesto degli edge (dai suoi stessi documenti)

| Lane/edge | Verdetto | Stato validazione |
|---|---|---|
| ES daily RSI mean-rev | **MORTO** (beta scambiato per alpha; €3K/mese richiede 5-16× il soffitto misurato) | chiuso onestamente |
| Family trend (donchian/trend_filtered/ema) su ES/SPY/BTC | **REJECTED** (0/9 battono buy&hold; alpha residuo +2-6% = beta) | chiuso |
| Lane D VRP | **Sharpe -0.08** (vs claim deep-research 7.36 = 95× inflato) | chiuso, non tradabile senza regime filter |
| AI swarm REDUCE_SIZE | 66.7% beat SPY **solo bull 2020-21** | validazione 2022-bear = TODO (BL-OPC-8) |
| **Lane B composite** | **Sharpe 0.93, alpha +59%** — unico edge reale | **NON ancora qualificato** DSR/PBO/CPCV (BL-OPC-12 pendente) |

### 3.3 I rischi veri
1. **242 file non committati**: tutto il pivot Opzione C (ADR-017..020, Lane
   A/B/D, AI swarm, paper orchestrator, knowledge base 13 domini) esiste solo
   nel working tree. **Un disco che muore e si perde il lavoro di agosto.**
   BL-OPC-11 è il task più importante del backlog, ancora aperto.
2. **Un solo edge candidato, non validato**: l'intero valore del progetto
   poggia su Lane B composite prima che passi DSR/PBO/CPCV.
3. **Genetics fermo dal 2-ago**; timer IBKR non installato (nessun 1m nuovo
   dal 17-ago).
4. **Canale economico in discussione**: il loro stesso modello S0.2 dice che
   €3K/mese su prop-firm richiede alpha 30-120%/anno; obiettivo onesto
   €1-1.5K/mese con 2-3 account. La domanda "ne vale la pena vs trading
   conto proprio crypto" è legittima e non è mai stata formalizzata.

---

## 4. Le quattro domande del ripensamento

### Q1 — Il canale: prop-firm futures o crypto conto proprio?
- **Prop-firm futures**: missione originale, policy G7 già modellata (Topstep,
  MyFundedFutures), MA economics debole (S0.2) e dati intraday futures
  costosi/parziali (gap dichiarato in ADR-020).
- **Crypto conto proprio**: dati gratis e profondi (9 anni di 1m nel lake),
  mercato 24/7 adatto all'automazione, fattori microstrutturali reali
  (funding, liquidazioni) che sui futures non ci sono. Svantaggi: niente leva
  prop-firm, rischio capitale proprio.
- Il lavoro MoonDev/trading-os punta tutto crypto. La risposta non è tecnica:
  è una scelta di obiettivo. **Va decisa prima di scrivere altro codice.**

### Q2 — Quanta architettura serve prima dell'edge?
Oracle ha già: gate G0-G4 (safety), OMS/ledger, risk kernel, paper
orchestrator, qualification DSR/PBO/CPCV, AI plane. La roadmap Mutageno
(G10-G14, 100+ strategie, evolution loop) è ambiziosa ma **presuppone edge
che non esistono ancora**. Il collo di bottiglia dichiarato da mesi è sempre
lo stesso: l'edge. Ogni modulo costruito prima dell'edge è debito.

### Q3 — Cosa prendere da MoonDev?
Solo due cose, già documentate in RISPOSTE_D1-D15.md:
1. **Ipotesi di fattore con meccanismo economico**: funding extremum,
   liquidation cascade reversal, BB squeeze release, CVD divergence,
   session seasonality. Tutte testabili a $0 (Binance Vision).
2. **Disciplina RBI**: research → backtest → implement, con preregistrazione.
   (Oracle ce l'ha già in forma più rigorosa; va applicata, non ricostruita.)
Tutto il resto (corso, Quant App, ROI claim) non ci serve.

### Q4 — Che fare dei framework clonati (nautilus, freqtrade, qlib)?
- **nautilus_trader**: unico con senso come futuro execution engine
  (adapter Hyperliquid già incluso, Rust core). Ma Oracle lo ha già dichiarato
  "candidato non certificato" e la certification costerebbe mesi. Non ora.
- **freqtrade**: ottimo crypto bot standalone, ma duplicherebbe Oracle. Solo
  come riferimento API Binance.
- **qlib**: ML factor research; il nostro `genetics/` + IC screen copre il caso
  d'uso con meno dipendenze.
- Verdetto: **nessuno di questi giustifica un rebuild**. Oracle ha già tutto
  ciò che serve per la fase attuale; il problema non è il framework.

---

## 5. Proposta: da "costruire piattaforma" a "Edge Factory"

Ristrutturare il progetto attorno a un unico obiettivo misurabile:
**produrre 1-3 fattori/strategie con edge validato entro un orizzonte fissato**,
usando ciò che esiste già.

### Cosa congelare
- Roadmap Mutageno G10-G14 (100 strategie, evolution loop) → riprendere SOLO
  dopo edge validato.
- Nuovi piani di integrazione (inalpha/finclaw/stratevo) → archiviare.
- Qualsiasi nuovo modulo infrastructure.

### Cosa eseguire (sequenza)
1. **BL-OPC-11 — committare i 242 file** (igiene, non negoziabile, 1 sessione).
2. **BL-OPC-12 — qualificare Lane B composite** (DSR/PBO/CPCV): l'unico edge
   candidato va promosso o ucciso con evidenza. Esito binario.
3. **Track crypto fattori (nuovo, da RISPOSTE_D1-D15)**:
   a. `scripts/ic_screen.py` (Spearman IC, orizzonti non sovrapposti, block bootstrap);
   b. fattori `bb_squeeze`/`bb_squeeze_release` + `hour_of_day` in genetics/alpha/factors.py;
   c. adapter Binance Vision per `fundingRate` → `funding_rate`/`funding_z`;
   d. IC screen su BTCUSDT 1h 2017→ (78K barre); preregistrazione per ogni fattore;
   e. adapter Vision `liquidationSnapshot` → event study cascate (se IC b/c promette).
4. **Decisione canale** (Q1) dopo i risultati di 2+3: se Lane B passa E ≥2
   fattori crypto passano l'IC → paper crypto conto proprio. Se nulla passa →
   stop onesto e rivalutazione (anche "il progetto ha dato tutto ciò che poteva").
5. MoonDev API free key: registrazione + accumulo going-forward
   (liquidations 30d, orderflow) — costo zero, valore futuro per paper/live.

### Criteri di successo pre-registrati (anti-autoinganno)
- Lane B: DSR ≥ 0.95, PBO < 0.1, CPCV OOS Sharpe ≥ 0.5 (2022 bear separato).
- Fattore crypto: ICIR > 0.05, t-block > 2.5, sopravvive a haircut 30%
  post-pubblicazione (McLean-Pontiff).
- Orizzonte: 4 settimane per punti 2-3, poi go/no-go scritto.

### Cosa NON è questa proposta
- Non è un rebuild: nessuna riscrittura, nessun nuovo framework.
- Non è "diventare MoonDev": nessun live non autorizzato, nessun claim di ROI.
- È la stessa filosofia Oracle (verdetti documentati, risultati negativi come
  artefatti di prima classe) applicata finalmente al collo di bottiglia reale.

---

## 6. Limiti dichiarati di questo studio

- Ricerca web: i prezzi (corso $1.795, cap free API) provengono da fetch del
  subagente e non sono stati verificati su pagina di checkout; il "Fable 5
  ban" è riportato con fonte da confermare.
- AI Trading Battles: non abbiamo verificato i wallet on-chain noi stessi.
- Le 463 trascrizioni video non sono state minate in questa sessione (agent
  dedicato fallito); restano materiale consultabile.
- Inventario PC: `Scaricati/` è un data dump non organizzato; potrebbero
  esistere materiale pertinente non rilevato.
