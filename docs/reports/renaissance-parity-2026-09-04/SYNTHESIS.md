# Pareggiare Renaissance Technologies sotto vincoli prop-firm — Sintesi strategica

> **Data**: 2026-09-04
> **Input**: documentazione completa del progetto + 3 dossier di ricerca web (A: Medallion ground-truth; B: famiglie di strategie replicabili; C: envelope prop-firm 2025-2026). Fonti primarie con URL nei dossier.
> **Domanda dell'operatore**: "cerchiamo un metodo per pareggiare Renaissance Technologies mantenendo comunque i paletti delle prop firm".
> **Metodo**: ogni claim numerico del progetto verificato sui report versionati; ogni claim esterno citato con URL nei dossier A/B/C.

---

## 0. TL;DR — La risposta onesta

**"Pareggiare Renaissance Technologies" nel senso dei rendimenti (66% lordo / 39% netto annuo) non è un obiettivo raggiungibile per nessuno fuori da RenTec — e questo è documentato, non pessimismo.** Ma il *metodo* Medallion è documentato ed è replicabile in scala ridotta, e il progetto Oracle lo sta già applicando: molti segnali deboli ortogonali + sizing Kelly-vol-target + discipline sui costi + capacità limitata. La verifica empirica fatta ieri (BL-737) mostra che questa via produce **SR ~1.2-1.5 saturato, con 5%/mese raggiungibile come mediana solo a vol 30% e MaxDD ~30%** — incompatibile con i paletti prop-firm (DD 3-10%, consistency ≤35-50%).

**La risoluzione del dilemma è il dual-channel che avete già (ADR-023), spinto alle sue conseguenze**: il canale personale (Lane B/IBKR) è dove si "pareggia RenTec in Sharpe-a-vol-pari" (SR 1.4+ a DD gestito), il canale funded è dove si converte quel marchio di qualità in rendimento assoluto via leva della firm (1+1% mese a DD<5%) e si scala per N×firm×conti. E la ricerca ha trovato una famiglia concreta che Oracle non ha ancora in portafoglio e che è la migliore candidata "retail-accessible" documentata per alzare il soffitto: il ramo **overnight/intraday decomposition** (Lou-Polk-Skouras 2019; Boyarchenko-Larsen-Whelan 2023) — si adatta perfettamente al vostro stack (strumenti 24h su MT5/futures, costi bassi, dati free Dukascopy), con meccanismo microstrutturale (offload inventario dealer) non arbitrato dai rendimenti.

---

## 1. Cosa è davvero Renaissance/Medallion (dossier A)

### 1.1 Numeri documentati (Cornell 2020 × Ziemba 2007, incrociati)

| Metrica | Valore | Stato |
|---|---|---|
| Rendimento medio lordo 1988-2018 | **66.07%/anno** | Documentato (Cornell Table 1 = Zuckerman App.1, cross-check Ziemba) |
| Rendimento medio netto | **39.20%/anno** | Documentato |
| Anno in perdita | Solo 1989 (−3.2% netto) | Documentato |
| 2008 | +152.1% lordo / +82.4% netto | Documentato |
| Sharpe | **≈2.0** (lordo, 66.1/31.7) | Documentato (Cornell p.4) — "fino a 7.5" = **leggenda** |
| Beta CRSP | ≈ −1.0 | Documentato |
| Scala | $20M → $10B senza decadimento, Poi **cap** | Documentato |
| Hit rate | ~50.75% su milioni di trade | Citato da Simons |
| Trades/giorno | 150k-300k | Secondaria ma consistente |
| Fee | 5% + 44% (dal 2002) | Documentato |
| 2020: 76%, Sharpe 7.5 | Plausibile ma non primario | **Leggenda** |

### 1.2 Dove sta l'edge (il verdetto delle fonti primarie)

Cornell: "nessun framework accademico lo spiega — una sfida Michelson-Morley all'EMH". L'ipotesi più difendibile (Berlekamp autobiography + Patterson "simple regression" + Brown "science/collaboration/infrastructure/no-interference/time"):

1. **Migliaia di segnali deboli non correlati** (IC appena sopra zero), ognuno "simple regression with one target and one independent variable" (Patterson, primario);
2. Screening statistico rigoroso (pattern anomali → significatività → plausibilità economica);
3. **Gestione straordinaria dei costi di transazione**;
4. **Sizing Kelly** a livello portafoglio (Berlekamp);
5. **Capacity cap ~$10B** — oltre, il segnale non scala (prova RIEF vs Medallion: 2008 RIEF −16% vs Medallion +82%; 2020 −22.6% vs +76%).

**Implicazione critica per "pareggiare"**: il cap di capacità implica che l'edge di Medallion è *scarsità-constrained*. Il piccolo operatore ha una struttura di vincoli **diversa e in parte più favorevole**: zero impact di mercato, spread retail sì, ma latenza retail no. La **metodologia** scala verso il basso; la **magnitudine** no (Sharpe documentato realistico retail: 0.5-2.0).

---

## 2. Cosa dice internet/papers su ciò che è replicabile oggi (dossier B)

### 2.1 Verdetto famiglia per famiglia (retail ≤$1M, MT5-CFD + CME futures, $0 dati, latenza secondi-minuti)

| Famiglia | Sharpe dopo costi retail | Decay | Verdetto per lo stack |
|---|---|---|---|
| **Overnight/intraday decomposition** (LPS 2019, BLW 2023) | ~0.4-0.8 | Persistente 2015-2024 | **#1 candidato — non in portafoglio Oracle** |
| Commodity XSMOM + basis (Fuertes 2015, Szymanowska 2014) | 0.7-1.0 | Persistente | #2 — buono, basket 24-30 commodity |
| Trend/TSM diversificatore (MOP 2012, HOP 2017) | 0.3-0.6 post-2020 | Dimezzato post-2010 (Carver 2025) | #3 — gambe esistenti Lane A già coprono |
| FX carry + commodity basis carry | 0.4-0.7 | Crisi-tail (SNB 2015, COVID 2020) | #4 — G10 + swap-rate proxy |
| Pairs/stat-arb (Zhu 2024 Yale: Sharpe 1.35) | 0.5-1.0 | Robusto se universo ≥100 coppie | #5 — commodity calendar spreads (Sharpe 1.45 doc.) |
| ML meta-labeling (LdP 2018) | 1.0-1.5 OOS | PBO>50% se no CPCV | Overlay di sizing/confidenza, non standalone |
| Reversal/intraday momentum liquid | 0.0-0.3 | Fortemente decaduto (-58% McLean-Pontiff) | Filtro, non gamba |
| Calendar (TOM/DoW) | 0.0-0.3 | Decaduto internazionalmente | Filtro |
| Crypto funding carry (Sharpe 1.8-2.55 doc.) | 1.5-2.5 | In regime-shift possibile (ott-2025 −5%) | Fuori MT5 ma in scope Oracle (EF-006 già GO) |
| VRP short-vol | compresso post-2018 | tail -50/-90% | No su MT5 (niente VIX) |

### 2.2 Le due contraddizioni che contano

1. **Overnight drift su oro/FX non è ancora replicato** — LPS/BLW sono equity-index. È la verifica #1 da fare col lake Dukascopy (XAU 1m dal 2003).
2. **Meta-labeling: real o PBO?** I risultati Sharpe 1.5-2.0 pubblicati raramente superano CPCV. Oracle ha già purgedcv — la disciplina esiste.

---

## 2bis. Il calcolo fondamentale (dal progetto + dossier C)

La matematica del limite, che unisce BL-736/737 e l'envelope prop-firm:

```
5%/mese a DD<10%  →  richiede SR ≥ 4
SR(N) empirico     →  satura a 1.2-1.5 con N≥20 gambe tecniche ortogonali
→ Gap 3-4× non colmabile con "più gambe tecniche" — servono edge NON tecnici
  (microstruttura/execution/dati esclusivi/overnight) oppure leva.
```

L'unica leva rimanente sotto paletti prop-firm è la **combustione del risk budget verso rendimento**: entro DD 4% trailing, a SR 1.4 il rendimento atteso è ~5-6%/anno a vol 4% — e qui entra la geometria multi-farm (dossier C): N×firm×conti con la stessa strategia σ-scaled, dove il reddito deriva dal numero di conti payout-successivi, non dalla profondità del singolo DD.

## 3. L'envelope prop-firm 2025-2026 (dossier C)

### 3.1 Regole attuali (verificate su pagine ufficiali, 2026-09-04)

| Firm | DD max | Consistency | DLL | Payout |
|---|---|---|---|---|
| FTMO 2-Step | 10% static | 50% best-day (1-Step only) | 5%/3% | 80→90%, on-demand dopo 14gg |
| The5ers 2-Step | 10% static | 50% funded | 3% | fino 100% Hyper Growth |
| FundedNext Rapid (futures) | trailing 4% EOD | 40% challenge | none | ogni 3gg, 95/5 |
| Topstep (futures) | trailing 4% intraday→XFA | 50% combine / none funded std | 2% | 100% primi $5K |
| MFFU Pro/Rapid (futures) | trailing 4% EOD | dropped funded | none | ogni 14gg/5 winning days |
| Lucid | trailing 4% EOD | 40% LucidPro funded | none Flex | 90/10, ogni 3gg |
| Apex (futures) | trailing 4% | 12-rule denial framework | none funded | 100% primi $250 |

### 3.2 Cosa passa davvero (dati empirici)

- **0.5-1.5%/mese netto** è il rendimento sostenibile documentato per un trader sistematico top-decile su conto funded singolo (consensus TSB/QuantVPS/TradeZella + Topstep 2025: 33.3% dei funded riceve payout; 0.71% raggiunge Live Funded).
- **Il lever dominante è il risk-per-trade, non il win rate**: breach-prob del trailing DD a 0.5R edge su 150 trade = 63% a 1% risk vs ~14% a 00.25% risk (Elite Trader Funding RoR calc, dossier C).
- **Consistency gates payouts, not accounts**: la best-day rule estende il target, non ammazza il conto (Topstep/MFFU/FundedNext). Il rischio vero è il pattern di negazione payout (position-size variance, cross-account timing <30s, hedging cross-account).
- **Strategia che sopravvive**: intraday mean-rev/ORB 2-5 trade/giorno, WR 55-70%, R:R 1.3-1.8, risk/trade 0.25-0.75%, holding <4h, best-day naturalmente <30% (rule non binding).

### 3.3 Tier prop-firm per il setup Oracle (futures-primary, kill-switch, multi-farm)

- **Primario**: MFFU Pro/Rapid (no DLL, no consistency funded, payout ogni 14gg/5 winning days), Topstep Standard (100% primi $5K), FTMO 2-Step (scaling $2M).
- **Ponte/test**: Apex EOD (trial gratis).
- **Da evitare come primari**: CFD B-book firm per la qualità esecuzione (le futures-funded route su CME reale).

---

## 4. Il metodo — "Medallion-lite per prop-firm" in 5 principi

Riassumo la traduzione operativa del §1.2 in principi Oracle:

1. **Ampiezza (breadth) prima del singolo edge.** Kelly + legge dei grandi numeri su molte scommesse piccole. Oracle lo fa (46+ ipotesi registry, SR(N) saturato 1.2-1.5). Il limite non è N, è la **correlazione residua fra famiglie**. Ergo: aggiungere famiglie NON-tecniche.
2. **Kelly/vol-target sizing, mai flat sizing.** Berlekamp-size le gambe al vol-target del canale (30-40% personal, σ-scaled per funded).
2b. **Leva = moltiplicatore della SR, non generatore di alpha.** BL-736: leva 4× → 16.6%/yr a SR invariato 1.40. Leva su SR 1.4 è matematica sana; leva su SR 0.3 è "amplifica il rumore".
3. **Costi come disciplina di prima classe.** Patterson: "simple regression" + costi ben gestiti. Oracle: costi per-gamba già nei runner (10-15bps/turnover) — tenerlo.
4. **Capacity cap auto-imposto.** Sotto $1M non è vincolo di mercato (zero impact) ma di **capacità di attenzione**: cap su N gambe per canale, cap su N conti.
5. **Doppio canale come struttura portante (ADR-023).** Personal = ricerca a vol alto; funded = monetizzazione σ-scaled sotto envelope. Promozione per-canale, indipendente.

---

## 5. Piano d'azione (6-12 mesi)

**Tronco comune**: finire il paper runner (BL-732) e portare la Lane B composite (già APPROVED BL-727: DSR 0.999, haircut Sharpe 0.67) in paper 24/7. È il primo asset "trade-producing" del progetto.

### Fase 1 (0-2 mesi) — Validare il candidato #1 mancante: overnight drift
- **Ipot: overnight-hold su strumenti 24h** (XAU, FX majors, ES/NQ futures): entra a close, hold 02:00-03:00 ET, exit prima del cash open. Meccanismo: offload inventario dealer + attenzione retail.
- Dati già posseduti: Dukascopy XAU/FX 1m dal 2003 + ES 1h. **Costo zero**. Registriamo l'ipotesi nel registry (dominio 04/08, nuova EF).
- Gate: IC screen + gauntlet ADR-017 standard, haircut 30%.
- **Nota onesta**: LPS/BLW è su equity index; la replicazione su gold/FX è open question documentata (dossier B §contradictions #7). Se passa → nuova famiglia ortogonale non-tecnica → alza il soffitto SR della pool.

### Fase 2 (2-4 mesi) — Commodities + carry: le due famiglie #2/#4 mancanti
- XSMOM + basis su 24-30 commodity (Fuertes 2015): dati free (S&P GSCI proxies o futuri daily dal lake + roll). La basi richiedono futures curve — verificare coverage lake (BL-301).
- FX carry G10 con policy-rate proxy (tassi free: FRED/BIS PIT). Chiude il gap dichiarato in fx-orthogonal-legs.md.
- Calendar spreads su commodity (Sharpe 1.45 doc. Quantitativo 2024) come stat-arb quantitativamente pulito.

### Fase 3 (3-6 mesi) — La macchina meta: meta-labeling su CPCV
- Meta-modello di sizing/confidenza sopra le gambe qualificate (LdP 2018 ch.3). Pre-requisito: purgedcv già installato. Test con CPCV, PBO<0.1.
- Se funziona: +SR sul portafoglio esistente senza nuove gambe.

### Fase 4 (4-6 mesi) — First funded attempt
- Variante σ-scaled della best leg portafoglio sotto MFFU Pro/Rapid o Topstep Standard (i due envelope più permissivi, dossier C §3.3). Eval pagata solo se BL-728 sim pass ≥60% su 100+ sessioni (ADR-023 Channel B: consistency ≤35%, DSR ≥0.95, hard-risk compliant).
- 1 conto → 2 → N, multi-firm, con jitter temporale (D4: UNA strategia × N firm × conti piccoli).

### Fase 4b (parallel) — Execution edge personale
- Il dossier B identifica la session-overlap filter come "free alpha" esecutivo (spread più stretti London-NY overlap). Cablarlo nel live loop.

### Fase 5 (6-12 mesi) — Rivalutare 5%/mese con onestà
- A fine Fase 4, ricalcolare P(m≥5%) del portafoglio multi-canale (personal 30% vol + funded N conti). La matematica dice: P(m≥5%) serve SR≥4 a vol 30% o N grande × 1%/mese. Documentare il gap onesto, di nuovo.

---

## 6. Perché questo è "pareggiare RenTec" nel senso giusto

Il benchmark onesto non è 66%/anno. È:
- **Sharpe-a-vol-pari**: Medallion gross ≈ 2.0. Oracle portfolio attuale ≈ 1.4 walk-forward. Con le famiglie nuove (overnight + commodity + carry + stat-arb) il target è **SR 1.8-2.2 nel canale personale** — l'ordine di grandezza RenTec-documentato (non leggenda).
- **Rendimento assoluto via leva strutturale**: Medallion usava basket-options leverage 10-20×. Il povero equivalents sono la leva brokerage (IBKR) + la leva prop-firm (conto 50K = €500 di fee per controllare $50K).
- **Sopravvivenza come KPI**: 30 anni di Medallion senza perdite annue (quasi). Il KPI prop-firm è passare cicli di payout con DD<4%: il "no losing year" del povero.

E il fondamento metodologico è lo stesso: molti segnali deboli ortogonali, screening rigoroso, costi, Kelly, capacity cap. **La differenza sarà il fattore di scala (~1000× in dollari) e la purezza dei dati — non il metodo.**

---

## 6bis. Cosa NON fare (le trappole documentate)

1. **Non inseguire Sharpe 7.5 leggendari** — non esistono come numeri primari. Il documented è ≈2.0.
2. **Non trattare l'overnight drift come acquisito** su gold/FX: è documentato su equity index, la replicazione sul vostro strumentario è open question — prima preregistrare e testare.
3. **Non comprare eval** senza simulazione canonica ITM (ADR-018/023).
4. **Non scalare N conti** senza jitter e senza tracker di payout-denial (12-rule framework, dossier C).
5. **Non credere a "Medallion-clone" retail 60-100%/anno** — nessuna verifica primaria esiste.
5b. **Non dimenticare la mortalità dell'industria**: 80-100 prop-firm cessate feb-2024→2025 (Track360). Le fee pagate sono opzioni scritte a breve: diversificare anche fra firm.

---

## 7. Fonti
- Dossier A — Medallion ground-truth (483 righe, 70+ fonti primarie): `docs/reports/renaissance-parity-2026-09-04/A-medallion-ground-truth.md`
- Dossier B — Replicable families (555 righe, 70+ fonti): `docs/reports/renaissance-parity-2026-09-04/B-replicable-families.md`
- Dossier C — Prop-firm envelope (389 righe, matrice regole + matematica): `docs/reports/renaissance-parity-2026-09-04/C-propfirm-envelope.md`
- Documentazione progetto: `docs/reports/2026-08-15-oracle-comprehensive-state.md`, `docs/reports/edge-factory/*`, ADR-017/018/021/022/023, `docs/PROP_FIRM_READINESS_ROADMAP.md`, BACKLOG.md (BL-726..737).
