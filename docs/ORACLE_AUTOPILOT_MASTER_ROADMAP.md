# Oracle Autopilot — Capability-Gated Master Roadmap

> Versione: 2.2
> Ultimo aggiornamento: 2026-07-24
> Stato: roadmap canonica
> Modello di avanzamento: capability gate con evidenza, non phase temporali
> Gerarchia fonti: ROADMAP (perché) → STATUS (cosa) → BACKLOG (come) → ADR (decisioni) → report (evidenza).
> La matrice gate/stato fresca è in ORACLE_AUTOPILOT_STATUS.md.

## 1. Risultato atteso

Oracle deve evolvere da piattaforma di ricerca a sistema capace di gestire in
sicurezza un portafoglio futures per uno specifico programma prop-firm.

Il risultato finale richiede contemporaneamente:

- dati point-in-time e specifiche contratto verificati;
- decisioni riproducibili e versionate;
- ledger, OMS e reconciliation durevoli;
- risk kernel deterministico e non bypassabile;
- adapter broker certificato;
- qualificazione economica out-of-sample;
- promozione replay → paper → shadow → evaluation → funded;
- audit, osservabilità, recovery e kill switch operativi.

Non sono obiettivi validi:

- massimizzare il numero di feature o agenti;
- dichiarare completezza perché un modulo o un test isolato esiste;
- usare risultati sintetici come prova di edge;
- usare LLM, GA o dashboard per compensare dati, ledger o risk incompleti;
- garantire profitti, payout o superamento di challenge.

## 2. Fonti canoniche

| Documento | Autorità |
|---|---|
| [PROJECT.md](../PROJECT.md) | Perimetro e stack (informale) |
| [ORACLE_AUTOPILOT_MASTER_ROADMAP.md](ORACLE_AUTOPILOT_MASTER_ROADMAP.md) | Sequenza dei capability gate |
| [ORACLE_AUTOPILOT_STATUS.md](ORACLE_AUTOPILOT_STATUS.md) | **Checkpoint operativo e matrice gate/stato** |
| [ORACLE_AUTOPILOT_BACKLOG.md](ORACLE_AUTOPILOT_BACKLOG.md) | **Task atomiche per gate** |
| [GOVERNANCE.md](GOVERNANCE.md) | **Gerarchia documentale e regole** |
| [PROP_FIRM_READINESS_POLICY.md](PROP_FIRM_READINESS_POLICY.md) | Regole di supporto e certificazione prop-firm |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Architettura corrente, target e confini di autorità |
| [ADR/README.md](ADR/README.md) | Decisioni architetturali e relativo lifecycle |
| [plans/README.md](plans/README.md) | Archivio dei vecchi piani Phase, non eseguibile |

I vecchi piani Phase, il backlog atomico v1 e il backlog v2 sono solo archivio.
Non possono cambiare stato, architettura o priorità del programma.

## 3. Regole di avanzamento

### 3.1 Stati

- NOT_STARTED: nessun lavoro verificato;
- IN_PROGRESS: deliverable parziali con evidenza;
- BLOCKED: blocker esplicito e owner del recupero;
- PASSED: exit gate soddisfatto con verifica fresca;
- REGRESSED: un gate precedentemente passato non è più valido;
- NOT_APPLICABLE: escluso tramite ADR.

### 3.2 Evidenza obbligatoria

Un gate può diventare PASSED soltanto se il report registra:

1. commit o build immutabile;
2. configurazione e dataset versionati;
3. comandi di verifica e risultato;
4. test negativi e failure mode rilevanti;
5. security e dependency scan applicabili;
6. rischi residui e limiti noti;
7. reviewer e data di approvazione.

Un checkbox, una demo o una suite che usa fallback sintetici non sono evidenza
sufficiente.

### 3.3 Politica di regressione

Un gate torna REGRESSED quando cambia uno dei seguenti elementi:

- contratto di dominio o schema dati;
- motore di sizing, risk, OMS o ledger;
- adapter broker o piattaforma;
- regola ufficiale della firm;
- strategia, dataset, cost model o motore di backtest;
- dipendenza con finding high/critical nel percorso interessato.

## 4. Confini non negoziabili

- LLM ed ElizaOS sono intelligence e decision support, mai execution authority.
- Nessun output LLM può essere inviato direttamente a un broker.
- Ogni ordine passa da modalità operativa, rule profile, risk kernel e OMS.
- Il ledger riconciliato è la fonte autorevole per account e posizioni.
- NATS è trasporto; non è fonte autorevole di ordini, fill o saldo.
- Redis è cache; una perdita Redis non può perdere stato economico.
- Un dato mancante, stale o non verificabile produce NO_TRADE, PAUSE o FLATTEN.
- Replay, paper, shadow, evaluation e funded sono ambienti e credenziali separati.
- Nessun profilo prop-firm incompleto o scaduto può essere AUTO_SUPPORTED.
- Il percorso safety-critical rimane deterministico e testabile senza LLM.
- Il live trading resta disabilitato finché G7 non è PASSED.

## 5. Workstream

### S — Safety control plane, bloccante

Contratti, ambienti, ledger, OMS, risk, broker, reconciliation, kill switch,
security e audit. È il percorso critico.

### D — Data e research integrity, bloccante per qualificazione

Contract data, point-in-time lineage, backtest, costi, WFA, holdout, stress ed
economics.

### I — Intelligence con feedback loop, non bloccante per la prima verticale sicura

Investment Committee, LLM gateway, Eliza scouts, memoria, debate e GA.
Questi moduli possono migliorare decision quality soltanto dopo aver rispettato
i confini S e D.

**Novità: AI Feedback Loop** (Q3 2026). I moduli I vengono potenziati con
un ciclo chiuso che permette all'agente di imparare dai propri errori:

- **Factor Timing**: i fattori alpha (50+) vengono classificati per Rank IC
  corrente, con decay detection. L'agente vede quelli che funzionano *ora*.
- **Strategy Evolution Loop**: l'agente scrive strategie Python, passano 3
  sandbox, vengono cross-validate (WalkForward / CPCV / Deflated Sharpe),
  e se superiori al baseline vengono promosse a paper live.
- **Research Memory**: ogni decisione è registrata con esito, regime e
  confidence. L'agente calibra la propria confidence sull'accuratezza storica.
- **Regime Ensemble**: HMM + Lorenzian classification + BOCD per rilevare
  transizioni di regime non-lineari e pesare i fattori di conseguenza.
- **Edge Discovery**: l'agente scopre nuovi pattern statisticamente validati
  tramite event study, seguendo il modello VARRD. I nuovi edge entrano
  automaticamente nel factor timing.

### O — Operations e UI, trasversale

API, dashboard, deployment, observability, incident response e runbook.
La UI osserva lo stato autorevole; non lo ricostruisce da artefatti ad hoc.

## 6. Capability gate

I gate sono descritti nei deliverable e exit evidence sottostanti.
**Lo stato attuale di ogni gate è in [ORACLE_AUTOPILOT_STATUS.md](ORACLE_AUTOPILOT_STATUS.md).**

## G0 — Baseline veritiera e riproducibile

**Obiettivo:** repository e CI descrivono esattamente ciò che è costruibile e
verificabile.

**Deliverable minimi:**

- working tree consolidata e artefatti generati esclusi;
- Python 3.12 e Node 24 dichiarati;
- installazione da uv.lock in CI;
- lock Node per ogni applicazione;
- suite, lint, format, typecheck e build verdi;
- audit dependency completo, incluse dev dependency esposte da dev server;
- warning budget e coverage scope espliciti;
- documentazione senza claim non verificati;
- SBOM, secret scan e dependency review pianificati o attivi.

**Exit evidence:**

- build da checkout pulito;
- uv sync --frozen riuscito;
- nessun finding high/critical non accettato;
- report di baseline con commit, comandi e conteggi;
- zero file runtime o credenziali tracciati per errore.

## G1 — Autorità, ambienti e confini applicativi

**Dipendenze:** G0.

**Obiettivo:** nessun percorso pubblico può acquisire autorità live per default.

**Deliverable minimi:**

- enum operativo REPLAY, PAPER, SHADOW, EVALUATION, FUNDED;
- credenziali, account e configurazioni separati per modalità;
- startup fail-closed per ambiente production;
- API authentication obbligatoria fuori dallo sviluppo locale;
- CLI live disabilitata fino a certificazione;
- contratti portfolio/trade spostati in un layer inward, non in agents;
- porte e adapter espliciti per broker, ledger, risk e market data;
- access scope read-only per intelligence e scope execution solo per OMS;
- threat model e matrice dei bypass.

**Exit evidence:**

- test che nessun comando o endpoint senza profilo e credenziali certificate
  possa inviare ordini;
- test di environment crossing;
- test di startup senza segreti;
- dependency graph senza cicli safety-critical.

## G2 — Verità futures e point-in-time data

**Dipendenze:** G1.

**Obiettivo:** prezzo, P&L, sizing e disponibilità dei dati usano unità e tempo
reali.

**Deliverable minimi:**

- ContractSpec versionato con multiplier, point/tick value, currency e scadenze;
- mapping continuous contract → tradable contract;
- calendari exchange, DST, holiday, maintenance e liquidation deadline;
- roll e back-adjustment policy;
- event_time, published_at, available_at, ingested_at e revision_id;
- raw data immutabile, normalized data e lineage feature;
- provider, licenza, hash e adjustment version;
- duplicate, gap, outlier e stale-data detection.

**Exit evidence:**

- P&L e sizing campione uguali a exchange/broker;
- replay DST, holiday e roll week;
- leakage test su news, macro revision e filing;
- nessun fallback generico di prezzo, point value o contract size.

## G3 — Ledger, OMS e reconciliation durevoli

**Dipendenze:** G1, G2.

**Obiettivo:** lo stato economico sopravvive a retry, restart e disconnessioni.

**Deliverable minimi:**

- PostgreSQL come source of truth production; SQLite solo dev/test;
- ledger double-entry o invarianti equivalenti per balance, equity, P&L,
  commissioni e margin;
- intent, order, fill, position e account snapshot durevoli;
- idempotency key e transactional outbox;
- partial fill, cancel, amend, reject e reversal idempotenti;
- reconciliation startup, periodica e on-demand;
- CLI, API e agent pipeline sullo stesso servizio OMS.

**Exit evidence:**

- restart senza perdita o duplicazione;
- duplicate e out-of-order fill non alterano il ledger;
- mismatch broker/ledger rilevato e bloccante;
- audit reconstruction da intent a saldo finale.

## G4 — Hard risk non bypassabile

**Dipendenze:** G2, G3 e rule profile versionato.

**Obiettivo:** nessun ordine può superare un limite hard.

**Deliverable minimi:**

- risk dependency obbligatoria, mai None, sul percorso eseguibile;
- support mode e rule version verificati;
- daily loss, trailing/static drawdown e contract cap;
- sizing da stop distance e tick value;
- session, news, overnight e liquidation gate;
- stale data, clock drift, reconciliation e profile mismatch circuit breaker;
- cancel + flatten kill switch con verifica broker-side;
- bracket/OCO broker-side quando disponibile.

**Exit evidence:**

- property test dei limiti;
- zero bypass da CLI, API, MAS o adapter;
- replay di breach ufficiali;
- time-travel test;
- fire drill di kill e flatten.

## G5 — Research truth e strategy qualification

**Dipendenze:** G2; G3 per parity paper/live.

**Obiettivo:** i risultati supportano una decisione economica riproducibile.

**Deliverable minimi:**

- motore vectorized solo per discovery veloce;
- un solo motore event-driven certificato per qualification;
- PyBroker deprecato; Nautilus è candidato, non ancora certificato;
- train index, purge, embargo e nested walk-forward reali;
- holdout intatto e strategia preregistrata;
- costi futures, commissioni, slippage, latency e roll;
- sizing identico tra qualification e paper;
- benchmark semplici e leakage probes;
- experiment registry con code, data, config e seed hash;
- policy legale esplicita per Commons Clause, LGPL e altre licenze del percorso.

**Exit evidence:**

- nessuna eccezione o fallback silenzioso nel calcolo delle metriche;
- report IS, validation, OOS e holdout separati;
- parity entro tolleranza;
- stress costi e regime;
- power analysis o numerosità adeguata.

**Nota:** M31 è stato APPROVED per historical replay il 2026-07-19. Lo stato in STATUS può
essere REGRESSED se dataset, motore o configurazione non sono più riproducibili.

## G6 — Paper e shadow operations

**Dipendenze:** G3, G4, G5.

**Obiettivo:** failure reali non producono drift o violazioni.

**Deliverable minimi:**

- paper broker event-driven con quote reali o replay deterministico;
- un solo adapter futures prioritario;
- sandbox contract tests;
- streaming account/order/fill/position;
- deployment riproducibile e non-root;
- metriche, tracing, alert e audit reali;
- chaos test per disconnect, delayed fill, duplicate event e clock drift;
- emergency stop indipendente dal processo principale;
- runbook e incident response.

**Exit evidence (G6 completo):**

- almeno 30 sessioni paper indipendenti (non sovrapposte) senza policy breach;
- almeno 20 sessioni shadow riconciliate;
- recovery da restart di processo, rete e broker;
- kill-to-flat entro SLO;
- nessuna credenziale statica o porta dati pubblica.

**G6-I — Intelligence Feedback Loop** (parallelo, non bloccante per G6 ops).

Obiettivo: chiudere il loop tra agenti, backtest e paper trading creando
un sistema che impara e migliora autonomamente.

| Milestone | Cosa | Riferimento |
|:---------:|------|:-----------:|
| I-01 | Factor Timing — 50 fattori classificati per Rank IC corrente | `plan-integration-inalpha-varrd.md §3` |
| I-02 | Research Memory — decisioni registrate, confidence calibrata | `plan-integration-inalpha-varrd.md §5` |
| I-03 | HMM + Lorenzian Ensemble — regime detection ibrida | `plan-integration-inalpha-varrd.md §6` |
| I-04 | Strategy Evolution Loop — LLM scrive strategie, 3 sandbox, cross-val | `plan-integration-inalpha-varrd.md §4` |
| I-05 | Edge Discovery — event study per nuovi pattern (VARRD) | `plan-integration-inalpha-varrd.md §7` |
| I-06 | Three-step Orders — propose→approve→execute con token | `plan-integration-inalpha-varrd.md §4` |

**Nota:** M32 "rolling paper replay" (60 finestre sovrapposte su storico) è diagnostico,
non costituisce le 30 sessioni paper indipendenti richieste da G6.

## G7 — Certificazione di uno specifico programma

**Dipendenze:** G6 e policy di [PROP_FIRM_READINESS_POLICY.md](PROP_FIRM_READINESS_POLICY.md).

**Obiettivo:** promuovere un solo firm/program/stage/platform/account profile.

**Exit evidence:**

- automazione consentita da fonte ufficiale e vincoli operativi rispettati;
- rule profile immutabile e fonti fresche;
- adapter e piattaforma certificati;
- replay, stress, paper e shadow passati;
- expected value netto positivo con intervallo di confidenza;
- support mode approvato;
- manifest con versioni di codice, dati, regole, strategia e adapter.

Il superamento di G7 autorizza soltanto la smallest evaluation esplicitamente
approvata.

## G8 — Funded limited rollout

**Dipendenze:** G7 e evaluation senza policy breach.

**Obiettivo:** usare il minimo capitale/risk budget e dimostrare operatività
controllata.

**Exit evidence:**

- payout e costi reali verificati;
- nessun incident high irrisolto;
- rischio iniziale non oltre il 25% del budget consentito;
- rollback e demotion testati;
- review umana prima di ogni aumento di account, strategia o size.

## G9 — Continuous operations

**Dipendenze:** G8.

**Obiettivo:** regole, strategie, modelli e dipendenze restano aggiornati.

Richiede review periodiche di risk, reconciliation, firm rules, broker,
dipendenze, modelli, prompt, strategie, DR e incidenti. G9 non termina: una
regressione riapre il gate interessato.

## 7. Lane intelligence

Le lane seguenti non possono bloccare G2-G4 e non acquisiscono autorità:

| Lane | Entry | Gate proprio |
|---|---|---|
| Investment Committee LLM | G1 | output strutturato, versionato, scadibile e riproducibile |
| ElizaOS scouts | G1 + provenance G2 | observation firmate, read-only, allowlist e injection defense |
| Debate e memory | G5 | beneficio incrementale misurato OOS, nessun simulated reward presentato come reale |
| Genetic research | G5 | holdout intatto, compute budget e promotion policy |
| Dashboard | G0 | legge API/ledger autorevoli, nessuna ricostruzione operativa da file locali |

## 8. Sequenza minima

```
G0 → G1 → G2 → G3 → G4
G2 → G5
G3 → G6
G4 → G6
G5 → G6 → G7 → G8 → G9

G1 → I[LLM ed Eliza read-only]
G5 → R[GA e research avanzata]
I → G6
R → G7
```

LLM, Eliza e GA possono essere rimossi senza rendere insicuro il control plane.
Non vale il contrario.

## 9. Stop condition

L'Autopilot non è completo quando "funziona una demo". È completo per un
programma soltanto quando G7 è PASSED e la smallest evaluation autorizzata è
stata completata senza policy breach. Il funded rollout richiede inoltre G8.

Qualunque dubbio su dati, regole, ledger, risk, broker o licenza mantiene il
sistema in RESEARCH_ONLY, PAPER o ASSISTED_ONLY.
