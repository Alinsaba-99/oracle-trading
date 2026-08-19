# Sintesi Findings + Integrazione Roadmap — 2026-08-15

> **Scope**: consolidare risultati delle 3 fasi (comprehensive report + consulenza esterna + deep-research) e mapparli alla roadmap G0-G14 / BACKLOG BL-NNN esistente. Pronto per decisione operatore su prossimo passo.
> **Date**: 2026-08-15
> **Files di riferimento**:
> - `docs/reports/2026-08-15-oracle-comprehensive-state.md` (28K token, 16 sezioni)
> - `docs/reports/2026-08-15-consultation-observations.md` (consulenza esterna)
> - `docs/reports/2026-08-15-deep-research-synthesis.md` (102 agenti, 20 fonti, 10 verified)

---

## 1. Sintesi Findings (3 fonti, 1 pag)

### Stato attuale (verificato, non goffrato)
- **G0-G4 PASSED**: baseline, autorità/ambienti, ledger/OMS PostgreSQL, hard risk kernel. Architettura safety-critical sana.
- **G5 REJECTED**: median Sharpe −0.251, 0 hard breach, luck p=1.0 → **alpha ≈ 0 netto costi** (beta scambiato per alpha, 0/9 walk-forward).
- **G6 REJECTED**: 30/30 sessioni pass ma 0 trade, 0 P&L, Sharpe 0 (risk adapter blocca tutto).
- **Live DISABLED** fino a G7. Modo autorizzato: RESEARCH/REPLAY/PAPER parziale.
- **3 gap live-readiness CHIUSI** 2026-08-10: FRED vintage PIT (`fred.py:120,154-156,200,209`), pessimistic-fill (`paper.py:374,381`), cvxpy KEEP documentato.
- **`OrderManager` rifiuta `risk_manager=None`** (`manager.py:30` → `ValueError`). BL-040 RISOLTO nel codice.

### Verdetto strategico (consulenza + deep-research)
- **5%/mese NON realistico nel breve** (6-12 mesi). Target = Sharpe 3-5 (Renaissance territory); CTA industry median Sharpe 0.5-0.8 = 6-10%/anno con 12% vol. Gap 5-16× dal soffitto misurato.
- **Target riparametrato onesto**: 6-10%/anno Sharpe 0.7-1.0 dopo 12-24m lavoro focalizzato → €1.000-1.500/mese netti su 2-3 account funded €50-100K.
- **Refactor mirato + redesign strategico della lane**, NON redesign architetturale. I mattoni sono pronti; manca edge + loop chiuso.
- **Modello "5-20 account concorrenti" SBAGLIATO**: correlazione cross-account = blowup simultaneo (stessa strategia, stesso giorno, stesso broker). Usare 1-3 account focused, espansione solo post-250 sessioni paper pass ≥90%.

### Scoperte operative concrete (deep-research, verificate 3-0 o 2-1)
1. **`purgedcv` (eslazarev) MIT-licensed** — scikit-learn-compatible, implementa DSR+PBO+CPCV+PurgedKFold+PSR. Rilasciato 1-ago-2026. Sostituisce `luck_p_value` di ADR-016. Costo 2-4 giorni.
2. **`mnemox-ai/deflated-sharpe` Apache-2.0** — DSR standalone, verificato matematicamente contro Bailey & López de Prado 2014 JPM 40(5):94-107. Zero dipendenze. Costo 1 giorno.
3. **mlfinlab NON è più OSI** — "all rights reserved", repo pubblico è solo bug tracker. NON incorporabile senza licenza commerciale Business/Enterprise.
4. **pysystemtrade (Carver)** maturo (3.4k stars, GPL-3.0, 7-stage pipeline), 4 moduli richiesti esistono come stage. **MA**: scope solo futures, IB integration ha 4 fragilità documentate (#1639, #1580, #1501, #1649). Raccomandazione: **reference NON dipendenza**.

### Conferme esterne (deep-research)
- **97% day trader persistenti perdono soldi netto fee** (Chague-De-Losso-Giovannetti 2019, n=1.551 BMF Bovespa). Solo 0.5% guadagnava >bank teller (~$13K/anno).
- **MyForexFunds = fee-extraction**: $310M challenge fees raccolti, $137M payouts pagati → **$172M net income firm > payouts totali** (FTC/CFTC case 222-7010, Sept 2023). Il modello prop-firm NON è "trova talenti", è "vendi speranza al 97% che fallirà".
- **Retail paradox** (Barber-Odean-Lin 2023 JFQA): retail prevedono rendimenti positivamente ma restano unprofitable come gruppo. Edge documentato ≠ edge catturabile senza vantaggio strutturale.
- **Trend TSM (12-mo Moskowitz-Ooi-Pedersen)** = singolo edge più documentato per Lane A (AQR/JFE, 58 futures/forward, 25+ anni, ~1y persistence poi partial reversal).
- **Lane B turnaround NON compatibile prop-firm** (equities non su MT5/futures) → portafoglio personale operatore, non conto funded.
- **Option selling SPX/ES (VRP)** = canale con edge accademico solido NON esplorato da Oracle. IB options API cablabile via ib_insync. Capitale €25K+.

### Red flags cumulativi
- RF1 diluizione focus operatore singolo (data eng + research + dev 131K LOC + ops + risk + LLM, ~20% research time)
- RF2 burnout 18-24m senza reddito alternativo (mitigazione: reddito part-time €1-2K/mese)
- RF5 illusione "Lane A come salvezza" (6-10%/anno, NON 60%)
- RF6 costo opportunità €150-450K salary foregone (ML engineer/quant developer €60-120K/anno)
- RF8 LLM researcher come distrazione (LLM genera strategie pubbliche = α=0 per definizione di mercato efficiente)
- RF-DR1 mlfinlab "trappola per la effort"
- RF-DR3 prop-firm = structurally negative EV per il trader
- RF-DR5 Lane B NON è prop-firm strategy → portafoglio personale

---

## 2. Nuovi BL-NNN proposti (integrazione roadmap)

> Da aggiungere a `BACKLOG.md` come estensione del workstream S (Safety) + D (Data/Research) + I (Intelligence). Numerazione BL-500+ per evitare conflitti con backlog esistente.

| ID | Priorità | Workstream | Task | AC | Effort | Bloccato da |
|---|---|---|---|---|---|---|
| **BL-500** | **P0** | D (Research integrity) | Installa `purgedcv` + `mnemox-ai/deflated-sharpe`; integra in `analytics/qualification/`. Sostituisci `luck_p_value` in ADR-016 con DSR+PBO+CPCV. | `pip install purgedcv` verde; `analytics/qualification/dsr.py` con `deflated_sharpe_ratio()`, `probability_of_backtest_overfitting()`, `combinatorial_purged_cv()`; test dedicati in `tests/unit/test_dsr.py`; report M31 rerun con DSR | 2-4gg | niente |
| **BL-501** | **P0** | S (Governance) | Scrivi **ADR-017** "Backtest overfitting validation upgrade: DSR + PBO + CPCV mandatory; depreca `luck_p_value` di ADR-016". | ADR-017 ACCEPTED; ADR-016 annotated "deprecated by ADR-017"; STATUS.md aggiornato | 1gg | BL-500 |
| **BL-502** | P1 | D (Lane A backbone) | Implementa 4 moduli Carver (vol target, forecast scaling, IDM, forecast combination) in `analytics/strategy/cta/` come reference pysystemtrade (NON dipendenza). Libri di Carver = specifica. | `analytics/strategy/cta/{vol_target,forecast_scale,forecast_combine,idm}.py`; 4 moduli con test; documentazione "pysystemtrade come reference, non dipendenza" in `docs/ADR/ADR-018-cta-backbone.md` | 2-4 sett | niente |
| **BL-503** | P1 | D (Lane A validation) | Valida Lane A con **trend TSM (12-mo Moskowitz-Ooi-Pedersen)** su 8-12 futures del lake (ES, NQ, GC, CL, YM + FX/metals via yfinance). Walk-forward anti-beta + DSR. | `scripts/run_lane_a_validation.py`; report `docs/reports/lane-a/{validation,walkforward,dsr}.md`; obiettivo onesto Sharpe 0.7-1.0; se Sharpe < 0.5 → REJECTED con DSR + PBO | 1-2 sett | BL-500, BL-502 |
| **BL-504** | P2 | D (Lane B universe) | Espandi universo azionario via `simfin` (MIT, fundamental data + daily prices in Pandas). Aggiungi `sec-edgar` per filing PIT quando serve. | `pip install simfin`; `market/ingestion/sources.py` integra simfin loader; coverage ≥ 500 US equities con fondamentali PIT | 3-5gg | niente (parallelo a BL-502/503) |
| **BL-505** | P2 | I (Lane B catalog) | Implementa Piotroski F-Score (9-point) + Lakonishok value-momentum + Greenblatt Magic Formula in `analytics/strategy/catalog/value/`. | `analytics/strategy/catalog/value/{piotroski,lakonishok,magic_formula}.py`; test su 3 value portfolios storici; report `docs/reports/lane-b/{f_score,lakonishok,magic_formula}.md` | 1 sprint (~2 sett) | BL-504 |
| **BL-506** | P2 | S (Trial ledger) | Pre-registra tesi turnaround in **trial ledger S0.3** (no HARKing): 20-30 titoli in depressione di multipli + catalizzatore identificabile, sizing 2-3%, invalidation predefinita. | `analytics/research/trial_ledger.py` con `register_thesis()`, `evaluate_invalidation()`, `record_outcome()`; tesi template in `docs/research/trial_ledger_template.md` | 2gg | BL-505 |
| **BL-507** | P3 | I (VRP exploration) | Esplora **option selling SPX/ES (VRP)** come lane aggiuntiva. Richiede IB options API (cablabile via ib_insync esistente). | `execution/brokers/ibkr_options.py` (nuovo); `analytics/strategy/vrp/` (nuovo); paper `docs/reports/vrp/{backtest,walkforward}.md`; capital €25K+; post G5+G6 verdi | 1 sprint (~3 sett) | G5+G6 PASSED |
| **BL-508** | P2 | S (Documentation) | Rimuovi/depredica mlfinlab aspirational reference da `docs/integration-blueprint-4-frameworks.md`. Documenta `purgedcv` come sostituto. | commit che aggiorna blueprint; nota "mlfinlab = closed-source; usa purgedcv (MIT)" | 1h | BL-500 |
| **BL-509** | P2 | S (Governance) | Documenta "prop-firm fee-extraction model" (RF-DR3) in `docs/POLICY_ENGINE.md` o **ADR-018** "Prop-firm structurally negative EV: prerequisite for funded capital deployment". | sezione in POLICY_ENGINE.md o ADR-018 ACCEPTED; implica requisito "funded capital deployment gate: ≥250 sessioni paper pass ≥90%" | 2h | niente |
| **BL-510** | P3 | (Operatore decisionale) | Valuta reddito alternativo parallelo per mitigazione burnout RF2. NON è una BL tecnica; è una decisione operatore. | decisione documentata in `PROJECT.md` o `RUNBOOK.md` | n/a | decisione operatore |

---

## 3. BL-NNN esistenti — stato aggiornato

### Confermati P1 (bloccanti G5/G6) — non cambiati
- **BL-024** P1 G6 re-run qualificante con trade reali (10+ finestre trade, P&L > 0, Sharpe non-zero, pass ≥ 0.90, DD ≤ 3%, reconcile 100%). ~1gg.
- **BL-097** P1 Fase A1 Futures intraday via IBKR Client Portal. **BLOCCO: setup manuale operatore** (~1h: Client Portal login, `start_ibkr_gateway.sh`, con_id map estesa MES MNQ RTY 6E ZN ZB + equities per Fase B, roll methodology coerente G2).
- **BL-098** P1 Fase A2 Databento free tier. **BLOCCO: API key gratuita operatore**.
- **BL-099** P1 Fase B Equities/ETF/indici intraday (SPY QQQ DIA IWM TLT GLD + 11 settoriali + ^GSPC ^DJI ^NDX ^RUT ^VIX, 1m/5m 2000→ via IBKR). Post BL-097.

### Confermati P2 (capability nuova)
- **BL-095** P2 Aggiornare fixture prop-firm stale (MFF target $5.000→$3.000=6% 2026; daily loss 5% assente; topstep $5.000→$3.000). ~2h.
- **BL-201** P1 Ensemble multi-segnale v2 (roc_momentum_12 + bollinger_20_2 + donchian_breakout_10) con hysteresys su RegimeAwareEnsemble. AC: mc_pass_rate > 0.45 su 200 sim; DD < 3%. ~1 sessione.
- **BL-202/BL-092** P2 Cross-asset factor timing (port factor catalog da ES a BTC/USDT, EURUSD, GC). ~3gg.

### RISOLTI nel codice (verificati 2026-08-15) — da marcare `[x]`
- **BL-040** P2 `OrderManager` rifiuta `risk_manager=None` → **RISOLTO** in `execution/order_manager/manager.py:30` (`ValueError: risk_manager is required — a missing risk gate is a safety violation`). Aggiornare BACKLOG.md.
- **BL-070** P1 PropFirmOrderRiskAdapter cablato in paper sessions → già `[x]` confermato.

### 3 gap live-readiness — tutti CHIUSI 2026-08-10
- FRED lookahead → RISOLTO (`analytics/macro/fred.py:120,154-156,200,209`)
- cvxpy morto → KEEP documentato (dipendenza viva di `pyportfolioopt`)
- Paper broker fill-on-touch → RISOLTO (`execution/brokers/paper.py:374,381`)

### Deprecati/Supersediati da findings
- **`luck_p_value` in ADR-016** → deprecato da **BL-501/ADR-017** (sostituito da DSR+PBO+CPCV)
- **mlfinlab aspirational reference** in `docs/integration-blueprint-4-frameworks.md` → deprecato da **BL-508** (sostituito da `purgedcv` MIT)
- **"5-20 account concorrenti"** in `s0-2-economic-model.md` → smentito (correlazione cross-account = blowup simultaneo); massimo 1-3 account focused

---

## 4. Priority chain integrata (post-synthesis)

```
[TUTTI I P0 — settimana 1-2]
BL-500 (purgedcv install)  →  BL-501 (ADR-017 DSR mandatory)
                                       │
[TUTTI I P1 — settimane 3-8]            ▼
BL-502 (Carver 4 moduli)  →  BL-503 (Lane A TSM validation)
   │                                 │
   │  [P1 bloccanti]                  │
   ├── BL-024 (G6 re-run trade-producing)  ── richiede Lane A/nuovo segnale
   ├── BL-097 (IBKR gateway) ─── BLOCCO operatore ───┐
   ├── BL-098 (Databento API key) ── BLOCCO operatore ┤
   └── BL-099 (Equities intraday via IBKR) ──────────┘
                                                      │
[TUTTI I P2 — mesi 2-3, parallelo dove indipendente]  │
BL-504 (simfin universe) ──┐                          │
BL-505 (Lane B value catalog) ──┤                    │
BL-506 (trial ledger S0.3) ──────┤                    │
BL-095 (fixture prop-firm stale) │                  │
BL-201 (ensemble multi-segnale v2) │                 │
BL-202/BL-092 (cross-asset factor timing) │         │
BL-508 (mlfinlab deprecation doc) │                 │
BL-509 (ADR-018 prop-firm fee-extraction) │         │
                                              ▼      ▼
[TUTTI I P3 — post G5+G6 PASSED]              │      │
BL-507 (VRP option selling exploration) ◀────┘      │
BL-400..408 (strategy catalog 100+) ◀────────────────┘ (solo se Lane A/B non producono edge)
BL-420..423 (G12 meta-optimizer) ◀───────────────────┘
BL-430..433 (G13 evolution loop) ◀───────────────────┘
BL-440..443 (G14 edge discovery) ◀────────────────────┘
```

**Prerequisiti per G5 verde (Lane A PAC)**:
1. BL-500+501 (DSR/PBO/CPCV mandatory)
2. BL-502 (Carver 4 moduli come reference)
3. BL-503 (Lane A TSM validation con N onesto + DSR)
4. Se Sharpe ≥ 0.5 e DSR > 0 e PBO < 0.5 → G5 PASSED per Lane A

**Prerequisiti per G6 verde (paper trade-producing)**:
1. G5 PASSED per Lane A
2. BL-024 re-run qualificante (10+ finestre trade, pass ≥ 0.90)
3. Setup operatore: BL-097 (IBKR) per dati intraday (opzionale per Lane A daily, obbligatorio per Lane C)

**Prerequisiti per G7 (cert prop-firm)**:
1. G5+G6 PASSED
2. BL-100 scelta firm (candidato: MyFundedFutures AUTO_SUPPORTED, fallback Topstep RESEARCH_ONLY)
3. BL-095 fixture prop-firm stale (sincronizzati a regole 2026)

---

## 5. Decisioni operatore richieste (prima di continuare)

### D1. Setup IBKR gateway (BL-097)
**Cos'è**: login manuale su Client Portal di IBKR paper account, `start_ibkr_gateway.sh` (~1h). Sblocca dati 1m futures (ES/NQ/GC/CL/YM) dal 2010 (~4M barre) + equities 1m dal 2000 (~6M barre).
**Perché serve**: sblocca Lane C intraday + Lane B equities universe. **SENZA questo, Lane A usa solo daily** (sufficienti per Carver PAC multi-asset, ma non per intraday).
**Costo inattività**: Lane A può procedere su daily; Lane B/C bloccate.
**Decisione**: lo fai ora o lo rinvii?

### D2. Setup Databento (BL-098)
**Cos'è**: registrazione gratuita + `DATABENTO_API_KEY`. 1GB/mese free tier (~2 mesi di 1m ES al mese di traffico).
**Perché serve**: ridondanza dati futures CME 1m 2018→; per validazione indipendente vs IBKR.
**Costo inattività**: nessuno se IBKR è attivo. Backup opzionale.
**Decisione**: critica o posticipabile?

### D3. Approccio Lane A vs Lane B
**Lane A** (PAC multi-asset, 6-10%/anno Sharpe 0.7-1.0, profittevole anche senza α perché vol-target+IDM riducono DD): costruibile OGGI su daily esistenti, ~1-2 mesi lavoro. Compatibile con The5ers (MT5/CFD/FX/metals/indices/overnight OK).
**Lane B** (turnaround su paniere azionario, INTC/Xiaomi formalizzato): NON compatibile con prop-firm (equities non su MT5/futures). Per portafoglio personale. Richiede BL-504 (simfin) + BL-505 (value catalog) + BL-506 (trial ledger). ~2-3 mesi.
**Decisione**: procedi Lane A prima (noiosa ma profittevole, prop-firm path), poi Lane B (la tua intuizione, portafoglio personale)? Oppure entrambe in parallelo?

### D4. Obiettivo 5%/mese vs 6-10%/anno
Consulenza + deep-research hanno validato che **5%/mese NON è realistico nel breve** (gap 5-16× dal soffitto misurato). Target onesto = 6-10%/anno Sharpe 0.7-1.0 → €1.000-1.500/mese su 2-3 account funded.
**Decisione**: accetti il target riparametrato? Oppure vuoi mantenere 5%/mese come orizzonte di lungo termine (2-3 anni) con consapevolezza che richiede α netto ≥6% su 250+ sessioni paper pass ≥90%?

### D5. Reddito alternativo (RF2 burnout mitigation)
L'operatore singolo rischia burnout 18-24m senza reddito. Mitigazione: reddito part-time €1-2K/mese per basics.
**Decisione**: hai reddito alternativo (lavoro part-time, freelance, risparmi)? Oppure Oracle deve produrre reddito entro 3-6 mesi (scenario RF2 = NON è il path)?

### D6. Primo passo concreto
Opzioni sul tavolo:
- **Opzione 1**: P0 immediato — install `purgedcv` + `mnemox-ai/deflated-sharpe` (BL-500), scrivi ADR-017 (BL-501). 1-2 settimane. Basso rischio, risolve bug metodologico, prerequisite per qualunque validazione onesta futura.
- **Opzione 2**: Setup operatore prima — BL-097 (IBKR gateway login manuale) per sbloccare dati intraday. ~1h dell'operatore + poi lavoro AI su Lane A con dati completi.
- **Opzione 3**: Lane A backbone — BL-502 (4 moduli Carver) subito, in parallelo a BL-500 (DSR). 2-4 settimane di lavoro strutturale.
- **Opzione 4**: Consulenza umana — invia il report + synthesis a un consulente umano (quant o trader prop-firm esperto) per seconda opinione prima di toccare codice.

---

## 6. Prossimi passi raccomandati (in ordine di priorità + basso rischio)

1. **BL-500 + BL-501** (1-2 sett) — risolve bug metodologico, prerequisite per qualunque verdetto onesto futuro. Basso rischio, alto valore. **Praticabile ora senza decisioni operatore**.
2. **BL-508 + BL-509** (~1h totale) — documentazione mlfinlab deprecation + prop-firm fee-extraction. Igienizza.
3. **BL-502** (2-4 sett) — Carver 4 moduli come reference. Lavoro strutturale, prerequisite per BL-503.
4. **BL-503** (1-2 sett) — Lane A TSM validation con DSR. Verdetto onesto su Lane A.
5. Se Lane A PASSED → BL-024 (G6 re-run) → G7 (cert MFF/The5ers).
6. Se Lane A REJECTED → decisione strategica (Lane B turnaround? Option selling VRP?).
7. **Setup operatore** BL-097 (IBKR) in parallelo quando possibile — sblocca Lane C + dati intraday per validazione più ricca.

---

*Fine synthesis. ~4500 token. Generato 2026-08-15.*
