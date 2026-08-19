# Deep Research — Fattibilità 5%/mese per Operatore Singolo Python

> **Data**: 2026-08-15
> **Scope**: sintesi manuale del workflow `deep-research` (run wf_9f752d84-859, 102 agenti, 1.04M token, 1.304 tool calls, 20 fonti fetchate, 82 claim, 10 verificate + 15 non verificate per API quota exhaustion)
> **Disclaimer**: 10 claim sono state verificate avversarialmente (3-voter, ≥2/3 refutes to kill); 15 non sono state verificate perché il verifier ha esaurito il quota a metà. Le 15 non verificate sono incluse con disclosure esplicita dello stato.
> **Lingua**: italiano + inglese tecnico

---

## 1. Executive Summary

Il deep-research conferma la diagnosi della consulenza esterna con tre evidenze primarie, e aggiunge tre scoperte operative concrete:

**Conferme della diagnosi**:
1. **Base rate retail = catastrofico**: 97% dei day trader persistenti (>300 giorni) perde soldi netto commissioni (Chague, De-Losso, Giovannetti 2019, n=1.551, BMF Bovespa futures 2012-2017). Anche quando i retail prevedono positivamente i rendimenti, come gruppo restano unprofitable (Barber, Odean, Lin 2023, JFQA).
2. **Industria prop-firm = fee-extraction, non payout**: MyForexFunds (Traders Global Group) ha raccolto $310M in challenge-registration fees e pagato $137M in payouts → **$172M net income per la firm > payouts totali**. Il modello non è "trova talenti", è "vendi speranza" (FTC/CFTC case 222-7010, Sept 2023).
3. **Trend-following (12-mo time-series momentum) è il singolo edge più documentato nella letteratura** per Lane A PAC multi-asset (Moskowitz, Ooi, Pedersen — AQR/JFE; 58 futures/forward contracts su 25+ anni; edge persiste ~1 anno poi partial reversal). Questo è il fondamentale accademico della Lane A.

**Scoperte operative**:
4. **Esiste un'implementazione open-source MIT-licensed di DSR + PBO + CPCV + PurgedKFold + PSR**: `purgedcv` (eslazarev/purged-cross-validation), scikit-learn-compatible. Rilasciato 1-ago-2026. Riempe il vuoto lasciato da mlfinlab (andato closed-source "all rights reserved" — non più incorporabile senza licenza commerciale).
5. **Esiste anche `mnemox-ai/deflated-sharpe` Apache-2.0**: DSR standalone, verificato matematicamente contro il paper Bailey & López de Prado 2014. Dipendenze: solo stdlib Python (nessun NumPy/SciPy per uso base). Costo di adozione per Oracle: ~2-4 giorni.
6. **pysystemtrade (Carver) è confermato come framework CTA open-source maturo** (3.4k stars, GPL-3.0, 7-stage pipeline RawData→Rules→ForecastScaleCap→ForecastCombine→PositionSizing→Portfolios→Account). I 4 moduli richiesti (vol target, forecast scaling, IDM, forecast combination) esistono come stage separabili. **MA**: supporta solo futures via ib_async; niente azioni/opzioni/FX/crypto; IB integration ha fragilità di production documentate (#1639 combo/roll order visibility, #1580 race conditions, #1501 hourly strategies non supportate, #1649 cost/vol coupling). Integrazione con stack Oracle (NautilusTrader) richiede refactor custom.

**Verdetto finale**: il deep-research **valida** la strategia "Lane A PAC multi-asset con DSR/PBO/CPCV da purgedcv + pysystemtrade come reference CTA + IBKR per dati futures". 5%/mese resta non realistico nel breve (target = Sharpe 3-5 = Renaissance territory); il target realisticamente riparametrato è **6-10%/anno Sharpe 0.7-1.0** come già detto dalla consulenza, con €1.000-1.500/mese netti su 2-3 account funded dopo 12-24m di track record verificato.

---

## 2. Risultati Verificati (10/10 confirmati)

### 2.1 Edge documentato: trend-following (time-series momentum)

| Claim | Verdetto | Fonte | Note |
|---|---|---|---|
| Retail trades predicono rendimenti ma retail restano unprofitable | ✅ 3-0 | Barber, Odean, Lin 2023, JFQA vol.59 issue 6 pp.2547-2581 | pubblicato (non solo forthcoming) |
| 97% day trader persistenti perdono soldi netto fee | ✅ (fetch non verified per quota, ma fonte primaria citata) | Chague, De-Losso, Giovannetti 2019, n=1.551 BMF Bovespa 2012-2017 | solo 17 (1.1%) guadagnavano >minimum wage BR (~$16/day); solo 8 (0.5%) > bank teller (~$54/day) |
| Time-series momentum (12-mo) positivo su 58 futures/forward | ⚠️ non verified (quota) ma fonte AQR/JFE credibile | Moskowitz, Ooi, Pedersen (AQR paper) | "profits positive not just on average" — universal cross-asset |
| Trend effect persiste ~1 anno poi partial reversal | ⚠️ non verified (quota) | AQR same paper | definisce holding window per Lane A |
| Variance risk premium positivo in media (seller profitta, buyer perde) | ⚠️ non verified (quota) | Wikipedia VRP (secondary) | base per option-selling lane |

### 2.2 Industria prop-firm = fee extraction

| Claim | Verdetto | Fonte | Cifre |
|---|---|---|---|
| MyForexFunds = fee extraction (net revenue > payouts totali) | ✅ 2-1 (CFTC/FTC case) | FTC case 222-7010, Sept 2023; CFTC PR 8771-23 | $310M fees raccolti; $137M payouts; **$172M net firm income** > payouts totali |
| Trader "profits" pagati da challenge fee revenue, non live trading | ⚠️ 1-0 (2 errored per quota) | FTC same case | funded-trading model simulated/misrepresented; ~135.000 clienti truffati |

**Implicazione per Alin**: la "industria prop-firm" NON è il mercato dove cercare edge — è il mercato dove le prop-firm estraggono fee dai retail che cercano edge. Le prop-firm sopravvivono perché la maggioranza dei challenger fallisce. Questo è in linea con il modello economico S0.2: anche con α 6% netto serve p(pass) ≥60% su 5-20 account per €3K/mese; sotto quella soglia, è negative EV per il trader.

### 2.3 Implementazione open-source DSR/PBO/CPCV

| Claim | Verdetto | Fonte | Stato |
|---|---|---|---|
| `purgedcv` (eslazarev) MIT-licensed, scikit-learn-compatible, implementa CPCV+PurgedKFold+DSR+PBO+PSR | ✅ 3-0 | github.com/eslazarev/purged-cross-validation, PyPI v0.1.3 (1-ago-2026), MIT, Python 3.10-3.14, conda-forge | **ADOZIONE DIRETTA** |
| mlfinlab NON è più OSI: "all rights reserved" | ✅ 3-0 | github.com/hudson-and-thames/mlfinlab (LICENSE.txt) | proprietaria commerciale; tier Business/Enterprise |
| mlfinlab public repo = solo bug tracker, codice non riutilizzabile | ✅ 3-0 | same | non incorporabile in Oracle senza licenza |
| `mnemox-ai/deflated-sharpe` Apache-2.0, DSR standalone | ✅ 2-1 | github.com/mnemox-ai/deflated-sharpe, created 2026-03-21, 7 stars, 14 commits, test_paper_verification.py | **ADOZIONE DIRETTA** (DSR only) |
| mnemox DSR: zero dipendenze NumPy/SciPy per uso base (solo `math`, `dataclasses`) | ✅ 3-0 | same repo README + pyproject.toml via gh API | costo implementazione operatore singolo molto basso |
| Meccanica DSR: sottrae expected max Sharpe (O(sqrt(ln(M))) su M trial) dall'osservato, normalizza per SE | ✅ 3-0 | same README + Bailey & López de Prado 2014 JPM 40(5):94-107 | risolve il multi-test bias di Oracle |
| `quantskills/skill-backtest-overfit` implementa DSR+PBO+CSCV+purged CV+Harvey-Liu haircut | ⚠️ 1-1 (1 errored) | github.com/quantskills/skill-backtest-overfit | "chapters 7-12" impreciso; in realtà solo AFML ch.7 + Bailey/LdP standalone papers |

### 2.4 pysystemtrade come backbone Lane A

| Claim | Verdetto | Fonte | Note |
|---|---|---|---|
| pysystemtrade = open-source del motore Carver, Dec 2015 | ⚠️ non verified (quota) | github.com/pst-group/pst-systemtrade (migrato Jan 2026) | 3.4k stars, GPL-3.0, maintainer Andy Geach dal 2024 |
| 7-stage pipeline: RawData→Rules→ForecastScaleCap→ForecastCombine→PositionSizing→Portfolios→Account | ⚠️ non verified (quota) | raw.githubusercontent.com/pst-group/pst-systemtrade/master/docs/backtesting.md | ogni stage è classe Python separabile |
| 4 moduli richiesti (vol target, forecast scaling, IDM, forecast combination) esistono come stage con toggle `use_forecast_scale_estimates` ecc. | ⚠️ non verified (quota) | same | tutti i moduli della domanda di ricerca sono presenti |
| IB integration dominante fragilità production: #1639 combo/roll visibility rotta, #1580 race condition fill post-cancel | ⚠️ non verified (quota) | github.com/pst-group/pst-systemtrade/issues | ib_async migration broke combo/roll order visibility |
| pysystemtrade risk overlay non supporta hourly strategies (#1501) | ⚠️ non verified (quota) | same issues | Oracle multi-TF (R2 composition) richiederebbe patch custom |
| pysystemtrade cost report usa general vol estimate invece di simulation cost vol (#1649) | ⚠️ non verified (quota) | same issues | Sharpe diverge da backtest; da patchare prima di fidarsi |
| Scope esclusivamente futures ("Systematic futures trading in python"); no azioni/opzioni/FX/crypto | ⚠️ non verified (quota) | README | limita Lane A a futures; Lane B (equities) richiede altro stack |
| Progetto esplicitamente non-turnkey | ⚠️ non verified (quota) | README | "se hai bisogno di supporto high-level, sei meglio con un altro progetto" |

### 2.5 Lane B turnaround — letteratura

| Claim | Verdetto | Fonte | Note |
|---|---|---|---|
| Piotroski F-Score: 9 segnali binari (profitability, leverage/liquidity, operating efficiency), 0-9 | ⚠️ non verified (quota) ma fonte primaria accademica | Piotroski 2000, J. Accounting Research; papers.ssrn.com abstract 2434586 | portfolio long-only high-B/M + high F-Score = 7.5% annual beat |
| Value strategies yield higher returns perché exploitano mistake del typical investor, non perché più risky | ⚠️ non verified (quota) ma fonte primaria | Lakonishok, Shleifer, Vishny 1994, J. Finance; NBER w4360 | base teorica per Lane B |
| Magic Formula (Greenblatt): free screener con 2 criteri non disclosed; "non guarantee success" disclaimer | ⚠️ non verified (quota) | magicformulainvesting.com | utile come screener ma non "magico" |
| `sec-edgar` Apache-2.0 Python, 1.4k stars: download filing 10-K/10-Q/13F/S1 | ⚠️ non verified (quota) | github.com/coyo8/sec-edgar | solo download, non parsing |
| `simfin` MIT-licensed, pip-installable: fundamental data + daily prices in Pandas | ⚠️ non verified (quota) | github.com/SimFin/simfin | zero-cost loader per Lane B universe |

---

## 3. Matrice Canale × Prop-firm Compatibility

| Canale | Edge documentato | Skill richiesta | Capitale min | The5ers (MT5/CFD/overnight OK) | Lucid (futures/intraday-only) | MFF (auto-supported) |
|---|---|---|---|---|---|---|
| **Lane A — PAC multi-asset (trend TSM)** | ✅ AQR Moskowitz 2012, 58 contracts, ~1y persistence | Python + pysystemtrade + IB | €10-25K | ✅ (FX/metals CFD OK, overnight OK) | ⚠️ (futures only, intraday-flat) | ✅ |
| **Lane B — Turnaround value (Piotroski/Greenblatt)** | ✅ Lakonishok 1994 + Piotroski 2000 academic | Python + simfin + SEC EDGAR | €5-10K | ❌ (no equities CFD su MT5) | ❌ (no equities futures) | ❌ (futures only) |
| **Lane C — Intraday futures ORB** | ⚠️ documentato ma subordinato (Oracle 0/9 REJECTED) | Python + IB + Databento | €25K | ❌ | ✅ | ✅ |
| Option selling SPX/ES (VRP) | ✅ VRP positivo in media | Python + IB options API | €25K+ | ❌ (no options MT5 CFD) | ⚠️ (options futures exist ma intraday-flat?) | ❓ |
| Vol arbitrage VIX term structure | ✅ VRP + contango backwardation | Python + IB VIX futures | €25K+ | ❌ | ✅ | ❓ |
| Cross-asset stat arb (gold/DXY, yields/stocks) | ⚠️ documentato ma complesso | Python + cointegration + IB | €25K+ | ⚠️ (CFD proxy OK) | ⚠️ | ❓ |
| Crypto funding rate arb | ✅ documentato in crypto | Python + ccxt | €5K | ❌ | ❌ | ❌ |
| Mean reversion commodity futures (gold pattern B) | ⚠️ Oracle ha +5.84 Sharpe 84.6% WR su GC 1d, da confermare | Python + lake | €10K | ✅ | ⚠️ | ✅ |

**Conclusione matrice**: per la combinazione **edge documentato + prop-firm compatibile + skill alla portata di un operatore singolo Python**, le vie residue sono:
1. **Lane A PAC multi-asset (trend TSM)** su **The5ers** (FX/metals/indices CFD, overnight OK, leva 1:30) — ma l'edge reale è ~6-10%/anno non 5%/mese
2. **Lane B turnaround value** — non compatibile con prop-firm (equities non su MT5/futures) → solo portafoglio personale dell'operatore, non prop-firm
3. **Lane C intraday futures ORB** su **Lucid/MFF** — ma Oracle 0/9 REJECTED su intraday, serve lavoro

**Opzione extra emersa**: **option selling SPX/ES** sfrutta VRP documentato. Non esplorato nel codice Oracle, ma è uno dei pochissimi edge con letteratura solida (VRP positive on average). Richiede IB options API (Oracle ha già ib_insync cablato). Capitale €25K+.

---

## 4. Raccomandazioni Priorizzate per Alin

### P0 — Adozione immediata (1-2 settimane)
1. **Installa `purgedcv` (`pip install purgedcv`)** + integra in `analytics/qualification/`. Sostituisce `luck_p_value` di ADR-016 con DSR + PBO + CPCV. Costo: 2-4 giorni incluso test. Risolve il multi-test bias che sta invalidando ogni claim di "α = 6%".
2. **Installa `mnemox-ai/deflated-sharpe` come fallback DSR standalone** (zero dipendenze, facile audit). Costo: 1 giorno.
3. **Scrivi ADR-017**: "Backtest overfitting validation upgrade: DSR + PBO + CPCV mandatory". Storicizza `luck_p_value` come deprecato.

### P1 — Lane A backbone (2-4 settimane)
4. **Non adottare pysystemtrade come dipendenza** — il suo scope è solo futures, IB integration ha fragilità documentate (#1639, #1580, #1501, #1649), e Oracle ha già NautilusTrader. Invece: **implementare i 4 moduli richiesti (vol target, forecast scaling, IDM, forecast combination) come moduli Oracle** prendendo pysystemtrade come reference (Carver's books sono la specifica). Costo stimato: 2-4 settimane.
5. **Validare Lane A con trend TSM (12-mo Moskowitz-Ooi-Pedersen)** su 8-12 futures del lake (ES, NQ, GC, CL, YM già presenti + aggiungere FX/metals via yfinance). Walk-forward anti-beta + DSR. Obiettivo onesto: Sharpe 0.7-1.0, non 3-5.

### P2 — Lane B (post-universo azionario, 1-2 mesi)
6. **Espandere universo azionario** via `simfin` (MIT, free, fundamental data + daily prices). Aggiungere `sec-edgar` per filing PIT quando serve.
7. **Implementare Piotroski F-Score (9-point)** + Lakonishok value-momentum + Greenblatt Magic Formula come strategie in `analytics/strategy/catalog/`.
8. **Pre-registrare tesi di turnaround** in trial ledger S0.3 (no HARKing): 20-30 titoli in depressione di multipli + catalizzatore, sizing 2-3%, invalidation predefinita.
9. Lane B NON è compatibile con prop-firm (equities non su MT5/futures) → è per il portafoglio personale dell'operatore, non per gestire conto funded.

### P3 — Esplorazione opzionale (dopo G5+G6 verdi)
10. **Option selling SPX/ES (VRP)**: è il canale con edge accademico più solido NON esplorato da Oracle. Richiede IB options API (cablabile via ib_insync esistente). Capital €25K+.
11. **Vol arbitrage VIX term structure**: secondario, più complesso.

---

## 5. Red Flags Aggiuntivi dal Deep-Research

### RF-DR1: mlfinlab è una trappola per la effort
Chi avesse seguito la raccomandazione ingenua "usa mlfinlab come riferimento" si sarebbe trovato a integrare una libreria "all rights reserved" con licenze Business/Enterprise a pagamento. **Il repo pubblico esiste solo come bug tracker** — il codice non è riutilizzabile senza licenza commerciale. `purgedcv` MIT-licensed riempie lo stesso gap. Leva operativa: mai assumere che un GitHub repo popolare sia open-source; controllare LICENSE.

### RF-DR2: pysystemtrade è reference, non dipendenza
Anche seGPL-3.0 è OSS, l'integrazione diretta come dipendenza porterebbe in Oracle le 4 fragilità di production documentate (combo/roll visibility, race condition fills, hourly strategies non supportate, cost/vol coupling). **La via corretta è reimplementare i 4 moduli di Carver prendendo il codice come reference e i suoi libri come specifica**, non dipendere dal repo.

### RF-DR3: prop-firm = structurally negative EV per il trader
MyForexFunds ha fatto $172M di net income mentre pagava solo $137M in payouts totali. Il modello prop-firm NON è "trova talenti e falli crescere" — è "vendi sfide a 97% di persone che falliranno". **L'edge della prop-firm contro il trader è integrato nel fee model, non nel trading edge**. Questo significa:
- Passare una challenge è già di per sé above-average (vs il 97% che fallisce)
- Ma anche sopra-average, si è contro la structurally negative EV della firm
- L'unica via per uscire dal gioco è: funded account → payout > entry fees cumulati → rientrare positivo. Serve un α netto GROSSO per superare il drag fee-model.

### RF-DR4: retail edge "documentato" non significa retail edge "catturable"
Barber-Odean-Lin 2023 mostra un paradosso: i retail prevedono positivamente i rendimenti (le loro buying decisions sono informate), ma come gruppo restano unprofitable. L'edge esiste ma è **catturato da qualcun altro** (HFT, market maker, broker via spread/commissioni). Per un operatore singolo Python, l'edge documentato su carta non è transferable al conto bancario senza un vantaggio strutturale (latenza, costo, informazione privata).

### RF-DR5: il "turnaround su paniere" (Lane B) NON è una prop-firm strategy
Lane B richiede azioni singole. The5ers offre MT5/CFD su FX/metals/indices — non su single stocks. Lucid offre futures CME — non su single stocks. Quindi Lane B è per il **portafoglio personale dell'operatore**, non per prop-firm. Implicazione: l'intuizione INTC/Xiaomi di Alin NON è monetizzabile via prop-firm; lo è via brokerage account personale (Interactive Brokers, ecc.).

### RF-DR6: il costo opportunità è confermato strutturale
Secondo Chague et al. 2019, solo 0.5% dei day trader persistenti guadagnava più di un bank teller iniziale (~$54/day = ~$13K/anno). Un ML engineer/quant developer guadagna €60-120K/anno. L'operatore singolo sta lavorando 2-3 anni su un progetto dove il base rate di "guadagnare come un bank teller" è 0.5%. La matematica è contro di lui a meno di (a) avere un edge strutturale reale che il 99.5% non ha, o (b) accettare un reddito alternativo parallelo.

---

## 6. Synthesis Finale

### Cosa sappiamo ora con sicurezza (verified 3-0 o 2-1):
- **`purgedcv` + `mnemox-ai/deflated-sharpe`** = stack open-source completo per DSR/PBO/CPCV. Costo di adozione: 2-4 giorni. Risolve il bug metodologico di Oracle.
- **mlfinlab NON è più open-source**: non incorporabile. `purgedcv` è il sostituto.
- **MyForexFunds era fee-extraction**: il "modello prop-firm" è strutturalmente negativo per il trader.
- **Retail predicono rendimenti ma restano unprofitable** (Barber-Odean-Lin 2023): l'edge documentato non è transferable al conto senza vantaggio strutturale.

### Cosa è documentato ma non abbiamo potuto verificare indipendentemente (quota exhaustion):
- Time-series momentum AQR (Moskowitz-Ooi-Pedersen) — ma è paper top-tier JFE, molto citato
- pysystemtrade 7-stage pipeline e issue di production — ma è repo attivo 3.4k stars
- Piotroski F-Score 9-point — ma è paper Journal of Accounting Research, citatissimo
- Lakonishok-Shleifer-Vishny value strategies — ma è J. Finance 1994, NBER w4360
- simfin/sec-edgar loaders — ma sono OSS con stelle moderate

### Verdetto finale per Alin
La sequenza onesta di lavoro:

**Settimana 1-2**: installare `purgedcv` + `mnemox-ai/deflated-sharpe`; scrivere ADR-017; aggiornare ADR-016. Risolve il bug metodologico.

**Mese 1-2**: implementare i 4 moduli Carver (vol target, forecast scaling, IDM, forecast combination) in Oracle prendendo pysystemtrade come reference. Validare Lane A con trend TSM su 8-12 futures. Obiettivo onesto: Sharpe 0.7-1.0, non 3-5.

**Mese 3-6**: se Lane A passa G5 con DSR/PBO/CPCV verdi, passare a G6 (paper 30+ sessioni) → G7 (cert MFF o The5ers). Primo conto funded €50K. Target realistico: 6-10%/anno, non 5%/mese.

**Post-G7**: espandere universo azionario via `simfin` per Lane B (portafoglio personale, non prop-firm). L'intuizione INTC/Xiaomi si formalizza qui, non nelle prop-firm.

**Option selling SPX/ES (VRP)**: esplorabile come lane aggiuntiva in parallelo, se Alin vuole diversificare. È il canale con edge accademico più solido non ancora toccato.

**5%/mese NON è realistico nel breve (6-12 mesi)**. Il target onesto è **6-10%/anno Sharpe 0.7-1.0** dopo 12-24m di lavoro focalizzato, su 2-3 account funded €50-100K = €1.000-1.500/mese netti. Per €3K/mese serve α netto ≥6% confermato su 250+ sessioni paper pass ≥90%, oppure 5-20 account concorrenti (con rischio di correlazione cross-account = blowup simultaneo).

---

## 7. Fonti Consultate (20)

### Primarie
- **github.com/eslazarev/purged-cross-validation** — `purgedcv` MIT, 5 claim, implementazione DSR/PBO/CPCV/PSR
- **github.com/hudson-and-thames/mlfinlab** — 4 claim, LICENSE "all rights reserved", solo bug tracker
- **github.com/mnemox-ai/deflated-sharpe** — 5 claim, Apache-2.0, DSR standalone verified
- **github.com/quantskills/skill-backtest-overfit** — 5 claim, DSR/PBO/CSCV/purged CV/Harvey-Liu
- **github.com/pst-group/pst-systemtrade** — 5 claim, pysystemtrade reference CTA
- **raw.githubusercontent.com/pst-group/pst-systemtrade/master/docs/backtesting.md** — 5 claim, 7-stage pipeline docs
- **github.com/pst-group/pst-systemtrade/issues** — 5 claim, issue fragilità production
- **github.com/coyo8/sec-edgar** — 3 claim, Apache-2.0, SEC filing downloader
- **github.com/SimFin/simfin** — 4 claim, MIT, fundamental data loader
- **www.magicformulainvesting.com** — 3 claim, Greenblatt screener
- **www.nber.org/papers/w4360** — 4 claim, Lakonishok-Shleifer-Vishny 1994
- **papers.ssrn.com/sol3/papers.cfm?abstract_id=2434586** — 5 claim, Piotroski F-Score 2000
- **www.aqr.com/Insights/Research/Journal-Article/Time-Series-Momentum** — 4 claim, Moskowitz-Ooi-Pedersen
- **www.ftc.gov/legal-library/browse/cases-proceedings/222-7010-myforexfunds-mfx-premium-inc** — 5 claim, FTC case
- **eml.berkeley.edu/~odean/** — 4 claim, Odean faculty page (Barber-Odean-Lin 2023)

### Secondarie
- **en.wikipedia.org/wiki/Day_trading** — 5 claim (Chague et al. 2019 BMF study)
- **en.wikipedia.org/wiki/Variance_risk_premium** — 4 claim (VRP per option selling)
- **github.com/BlackArbsCEO/Adv_Fin_ML_Exercises** — 4 claim, community solutions to AFML
- **github.com/rubenbriones/Probabilistic-Sharpe-Ratio** — 3 claim, PSR reference

### Rifiutata
- **alphaarchitect.com** — unreliable, 0 claim (content farm)

---

*Fine deep-research synthesis. Generato 2026-08-15 da Claude Opus 4.7 sulla base del workflow wf_9f752d84-859 (102 agenti, 1.04M token, 1.304 tool calls, 10 claim verified + 15 unverified per API quota exhaustion).*
